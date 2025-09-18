"""Configuration models and persistence helpers for the heat overlay."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json

DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class GaugeTheme:
    """Visual theme used by the gauge overlay."""

    start_color: str = "#ffdd00"
    end_color: str = "#ff3300"
    tick_color: str = "#ffffff"
    halo_color: str = "#ff000088"
    background_color: str = "#00000000"
    text_color: str = "#ffffffff"


@dataclass
class OverlayOptions:
    """General overlay options."""

    mode: str = "center"  # center or cursor
    size: int = 320
    ring_width: int = 18
    gap_angle: float = 40.0
    show_text: bool = False
    ticks: Tuple[int, int, int] = (15, 30, 45)
    threshold: int = 45
    maximum: int = 60
    cursor_offset: Tuple[int, int] = (32, 32)
    theme: GaugeTheme = field(default_factory=GaugeTheme)


@dataclass
class VisionOptions:
    """Options required by the computer vision pipeline."""

    template_path: Optional[Path] = None
    buff_bar_region: Optional[Tuple[int, int, int, int]] = None
    ocr_relative_rect: Optional[Tuple[float, float, float, float]] = None
    capture_backend: str = "auto"
    search_margin: int = 16
    search_scale_steps: int = 3
    search_scale_factor: float = 0.12
    match_threshold: float = 0.75
    ocr_psm: int = 7
    ocr_threshold: int = 150


@dataclass
class AppConfig:
    """Top level configuration."""

    overlay: OverlayOptions = field(default_factory=OverlayOptions)
    vision: VisionOptions = field(default_factory=VisionOptions)
    template_library: Dict[str, str] = field(default_factory=dict)
    tesseract_cmd: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        def _convert(value: Any) -> Any:
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, tuple):
                return list(value)
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if dataclass_is_instance(value):
                result = asdict(value)
                return {
                    key: _convert(val)
                    for key, val in result.items()
                }
            if isinstance(value, dict):
                return {key: _convert(val) for key, val in value.items()}
            return value

        return _convert(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        overlay_data = data.get("overlay", {})
        theme_data = overlay_data.get("theme", {})
        overlay = OverlayOptions(
            mode=overlay_data.get("mode", "center"),
            size=overlay_data.get("size", 320),
            ring_width=overlay_data.get("ring_width", 18),
            gap_angle=overlay_data.get("gap_angle", 40.0),
            show_text=overlay_data.get("show_text", False),
            ticks=tuple(overlay_data.get("ticks", (15, 30, 45))),
            threshold=overlay_data.get("threshold", 45),
            maximum=overlay_data.get("maximum", 60),
            cursor_offset=tuple(overlay_data.get("cursor_offset", (32, 32))),
            theme=GaugeTheme(**theme_data),
        )
        vision_data = data.get("vision", {})
        vision = VisionOptions(
            template_path=_maybe_path(vision_data.get("template_path")),
            buff_bar_region=_maybe_tuple(vision_data.get("buff_bar_region")),
            ocr_relative_rect=_maybe_tuple(vision_data.get("ocr_relative_rect")),
            capture_backend=vision_data.get("capture_backend", "auto"),
            search_margin=vision_data.get("search_margin", 16),
            search_scale_steps=vision_data.get("search_scale_steps", 3),
            search_scale_factor=vision_data.get("search_scale_factor", 0.12),
            match_threshold=vision_data.get("match_threshold", 0.75),
            ocr_psm=vision_data.get("ocr_psm", 7),
            ocr_threshold=vision_data.get("ocr_threshold", 150),
        )
        template_library = {
            key: val for key, val in data.get("template_library", {}).items()
        }
        tesseract_cmd = _maybe_path(data.get("tesseract_cmd"))
        return cls(
            overlay=overlay,
            vision=vision,
            template_library=template_library,
            tesseract_cmd=tesseract_cmd,
        )

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data)

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)


def _maybe_path(value: Optional[str]) -> Optional[Path]:
    if value:
        return Path(value)
    return None


def _maybe_tuple(value: Optional[Any]) -> Optional[Tuple[Any, ...]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return tuple(value)
    raise TypeError(f"Expected list/tuple, got {type(value)!r}")


def dataclass_is_instance(value: Any) -> bool:
    try:
        from dataclasses import is_dataclass

        return is_dataclass(value)
    except Exception:
        return False
