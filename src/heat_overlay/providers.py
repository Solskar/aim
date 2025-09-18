"""Heat provider implementations."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread, Lock
from time import perf_counter, sleep
from typing import Callable, Optional, Tuple
import logging

from .config import AppConfig

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy might be unavailable in docs/tests
    np = None  # type: ignore

try:  # pragma: no cover - optional runtime dependency
    import cv2
except Exception:
    cv2 = None  # type: ignore

try:  # pragma: no cover - optional runtime dependency
    import pytesseract
except Exception:
    pytesseract = None  # type: ignore

try:  # pragma: no cover - optional runtime dependency
    import dxcam
except Exception:
    dxcam = None  # type: ignore

try:  # pragma: no cover - optional runtime dependency
    import mss
except Exception:
    mss = None  # type: ignore


LOGGER = logging.getLogger(__name__)


CaptureRegion = Optional[Tuple[int, int, int, int]]


class _CaptureBackend:
    """Abstract screen capture backend."""

    def start(self, region: CaptureRegion) -> None:
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - simple default
        pass

    def get_latest_frame(self) -> Optional["np.ndarray"]:
        raise NotImplementedError


class _DXCamCapture(_CaptureBackend):
    """dxcam-based capture backend optimized for DirectX."""

    def __init__(self) -> None:
        if dxcam is None:
            raise RuntimeError("dxcam module is not available")
        self._camera = dxcam.create(output_color="BGR")
        self._running = False

    def start(self, region: CaptureRegion) -> None:
        self._camera.start(target_fps=30, video_mode=True, region=region)
        self._running = True

    def stop(self) -> None:  # pragma: no cover - hardware resource cleanup
        if self._running:
            try:
                self._camera.stop()
            finally:
                self._running = False

    def get_latest_frame(self) -> Optional["np.ndarray"]:
        return self._camera.get_latest_frame()


class _MSSCapture(_CaptureBackend):
    """Capture backend relying on MSS (works with Vulkan and general rendering)."""

    def __init__(self) -> None:
        if mss is None:
            raise RuntimeError("mss module is not available")
        if np is None:
            raise RuntimeError("numpy is required for MSS capture")
        self._sct: Optional["mss.base.MSSBase"] = None
        self._region: CaptureRegion = None

    def start(self, region: CaptureRegion) -> None:
        self._region = region
        if self._sct is None:
            self._sct = mss.mss()

    def stop(self) -> None:  # pragma: no cover - hardware resource cleanup
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
        self._sct = None
        self._region = None

    def _ensure_instance(self) -> "mss.base.MSSBase":
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def get_latest_frame(self) -> Optional["np.ndarray"]:
        assert np is not None
        sct = self._ensure_instance()
        region = self._region
        if region is None:
            monitor = sct.monitors[0]
            left = int(monitor.get("left", 0))
            top = int(monitor.get("top", 0))
            width = int(monitor.get("width", 0))
            height = int(monitor.get("height", 0))
        else:
            left, top, width, height = (int(v) for v in region)
        if width <= 0 or height <= 0:
            LOGGER.debug("Capture backend received non-positive region size: %s", region)
            return None
        bbox = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        }
        shot = sct.grab(bbox)
        frame = np.asarray(shot, dtype=np.uint8)
        if frame.shape[2] >= 3:
            frame = frame[:, :, :3]
        return frame


class HeatProvider:
    """Abstract interface used by the overlay."""

    def start(self) -> None:
        """Start acquisition."""

    def stop(self) -> None:
        """Stop acquisition."""

    def get_heat(self) -> Optional[int]:  # pragma: no cover - simple passthrough
        """Return latest heat value."""
        raise NotImplementedError


@dataclass
class SimulatedHeatProvider(HeatProvider):
    """Simple provider useful for development and demos."""

    minimum: int = 0
    maximum: int = 60
    period: float = 5.0

    def __post_init__(self) -> None:
        self._start_time = perf_counter()

    def start(self) -> None:  # pragma: no cover - trivial start
        self._start_time = perf_counter()

    def stop(self) -> None:  # pragma: no cover - trivial stop
        pass

    def get_heat(self) -> int:
        elapsed = (perf_counter() - self._start_time) % self.period
        ratio = elapsed / self.period
        value = self.minimum + (self.maximum - self.minimum) * abs(1 - 2 * ratio)
        return int(round(value))


class VisionHeatProvider(HeatProvider):
    """Vision-based provider using template matching and OCR."""

    def __init__(self, config: AppConfig, callback: Optional[Callable[[int], None]] = None) -> None:
        if cv2 is None or pytesseract is None or np is None:
            raise RuntimeError(
                "VisionHeatProvider requires numpy, cv2 and pytesseract to be installed"
            )
        self._config = config
        self._vision = config.vision
        self._callback = callback
        self._capture, backend_name = self._build_capture_backend(self._vision.capture_backend)
        self._capture_backend_name = backend_name
        LOGGER.info("Backend de capture sélectionné: %s", backend_name)
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._heat_lock = Lock()
        self._heat_value: Optional[int] = None
        self._last_position: Optional[tuple[int, int, int, int]] = None
        self._template_cache: Optional["np.ndarray"] = None
        self._template_mtime: Optional[float] = None

        if config.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = str(config.tesseract_cmd)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="VisionHeatProvider", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._capture.stop()

    def get_heat(self) -> Optional[int]:
        with self._heat_lock:
            return self._heat_value

    def _loop(self) -> None:  # pragma: no cover - requires realtime hardware
        region = self._vision.buff_bar_region
        try:
            self._capture.start(region)
        except Exception:
            LOGGER.exception(
                "Impossible de démarrer le backend %s", self._capture_backend_name
            )
            return
        try:
            while not self._stop_event.is_set():
                frame = self._capture.get_latest_frame()
                if frame is None:
                    sleep(0.01)
                    continue
                try:
                    heat = self._process_frame(frame)
                except Exception:  # pragma: no cover - safety net
                    LOGGER.exception("Failed to process frame")
                    heat = None
                if heat is not None:
                    with self._heat_lock:
                        self._heat_value = heat
                    if self._callback:
                        self._callback(heat)
                sleep(0.03)
        finally:
            self._capture.stop()

    def _build_capture_backend(
        self, requested: Optional[str]
    ) -> tuple[_CaptureBackend, str]:
        backend = (requested or "auto").lower()
        if backend == "vulkan":
            backend = "mss"
        candidates = ["dxcam", "mss"] if backend == "auto" else [backend]
        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                capture = self._create_capture_backend(candidate)
            except Exception as exc:
                LOGGER.warning(
                    "Échec d'initialisation du backend %s: %s", candidate, exc
                )
                last_error = exc
                continue
            return capture, candidate
        raise RuntimeError(
            f"Aucun backend de capture disponible ({backend})"
        ) from last_error

    def _create_capture_backend(self, backend: str) -> _CaptureBackend:
        if backend == "dxcam":
            return _DXCamCapture()
        if backend == "mss":
            return _MSSCapture()
        raise RuntimeError(f"Backend de capture inconnu: {backend}")

    def _process_frame(self, frame: "np.ndarray") -> Optional[int]:
        assert cv2 is not None and np is not None and pytesseract is not None
        template = self._load_template()
        if template is None:
            return None

        match_location, match_scale = self._match_template(frame, template)
        if match_location is None:
            return None
        x, y = match_location
        scale = match_scale or 1.0
        template_h = int(template.shape[0] * scale)
        template_w = int(template.shape[1] * scale)

        rel_rect = self._vision.ocr_relative_rect
        if rel_rect is None:
            LOGGER.debug("OCR rect not configured")
            return None
        ox_rel, oy_rel, w_rel, h_rel = rel_rect
        ocr_x = int(x + template_w * ox_rel)
        ocr_y = int(y + template_h * oy_rel)
        ocr_w = max(1, int(template_w * w_rel))
        ocr_h = max(1, int(template_h * h_rel))
        frame_h, frame_w = frame.shape[:2]
        ocr_x = max(0, min(frame_w - 1, ocr_x))
        ocr_y = max(0, min(frame_h - 1, ocr_y))
        if ocr_x + ocr_w > frame_w:
            ocr_w = frame_w - ocr_x
        if ocr_y + ocr_h > frame_h:
            ocr_h = frame_h - ocr_y
        roi = frame[ocr_y : ocr_y + ocr_h, ocr_x : ocr_x + ocr_w]
        if roi.size == 0:
            LOGGER.debug("OCR ROI empty")
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            11,
            2,
        )
        _, binary = cv2.threshold(thresh, self._vision.ocr_threshold, 255, cv2.THRESH_BINARY)
        config = f"--psm {self._vision.ocr_psm} -c tessedit_char_whitelist=0123456789"
        text = pytesseract.image_to_string(binary, config=config)
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            LOGGER.debug("OCR produced no digits from %r", text)
            return None
        try:
            value = int(digits)
        except ValueError:
            LOGGER.debug("Failed to parse OCR digits: %s", digits)
            return None
        return value

    def _load_template(self) -> Optional["np.ndarray"]:
        assert cv2 is not None and np is not None
        template_path = self._vision.template_path
        if not template_path or not template_path.exists():
            LOGGER.warning("Template path missing: %s", template_path)
            return None
        try:
            mtime = template_path.stat().st_mtime
        except OSError:
            mtime = None
        if self._template_cache is not None and mtime and self._template_mtime == mtime:
            return self._template_cache
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template is None:
            LOGGER.error("Failed to load template from %s", template_path)
            return None
        self._template_cache = template
        self._template_mtime = mtime
        return template

    def _match_template(
        self,
        frame: "np.ndarray",
        template: "np.ndarray",
    ) -> tuple[Optional[tuple[int, int]], Optional[float]]:
        assert cv2 is not None and np is not None
        if frame.ndim == 3:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_gray = frame
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        def _search(area: "np.ndarray", offset: tuple[int, int]) -> Optional[tuple[tuple[int, int], float, float]]:
            best: Optional[tuple[tuple[int, int], float, float]] = None
            for step in range(self._vision.search_scale_steps):
                scale = 1.0 + self._vision.search_scale_factor * (
                    step - (self._vision.search_scale_steps // 2)
                )
                resized = cv2.resize(
                    template_gray,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC,
                )
                if area.shape[0] < resized.shape[0] or area.shape[1] < resized.shape[1]:
                    continue
                res = cv2.matchTemplate(area, resized, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                if max_val >= self._vision.match_threshold:
                    loc = (max_loc[0] + offset[0], max_loc[1] + offset[1])
                    if not best or max_val > best[2]:
                        best = (loc, scale, max_val)
            return best

        best_match: Optional[tuple[tuple[int, int], float, float]] = None
        if self._last_position is not None:
            lx, ly, lw, lh = self._last_position
            margin = self._vision.search_margin
            x0 = max(lx - margin, 0)
            y0 = max(ly - margin, 0)
            x1 = min(lx + lw + margin, frame_gray.shape[1])
            y1 = min(ly + lh + margin, frame_gray.shape[0])
            area = frame_gray[y0:y1, x0:x1]
            best_match = _search(area, (x0, y0))

        if best_match is None:
            best_match = _search(frame_gray, (0, 0))

        if best_match is None:
            self._last_position = None
            return None, None

        (x, y), scale, _score = best_match
        tw = int(template_gray.shape[1] * scale)
        th = int(template_gray.shape[0] * scale)
        self._last_position = (x, y, tw, th)
        return (x, y), scale

