"""Application entry point and CLI handling."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .calibration import CalibrationWizard
from .config import AppConfig, DEFAULT_CONFIG_PATH, GaugeTheme
from .overlay import OverlayWindow
from .providers import HeatProvider, SimulatedHeatProvider, VisionHeatProvider

LOGGER = logging.getLogger(__name__)

THEMES = {
    "default": GaugeTheme(),
    "dark": GaugeTheme(
        start_color="#ffe082",
        end_color="#ff6d00",
        tick_color="#f0f0f0",
        halo_color="#ff174488",
        background_color="#ffffff22",
        text_color="#f0f0f0ff",
    ),
    "neo": GaugeTheme(
        start_color="#00e5ff",
        end_color="#00bfa5",
        tick_color="#e0f7fa",
        halo_color="#00e5ff55",
        background_color="#001f2a55",
        text_color="#ffffff",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rapid Shot Heat overlay")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Chemin du fichier config")
    parser.add_argument("--mode", choices=["center", "cursor"], help="Mode d'affichage de la jauge")
    parser.add_argument("--size", type=int, help="Diamètre de la jauge")
    parser.add_argument("--ring", type=int, help="Largeur de l'anneau")
    parser.add_argument("--gap", type=float, help="Angle du gap (degrés)")
    parser.add_argument("--threshold", type=int, help="Seuil du halo d'alerte")
    parser.add_argument("--max", type=int, help="Valeur maximale de la jauge")
    parser.add_argument("--ticks", type=str, help="Liste de ticks séparés par des virgules")
    parser.add_argument("--cursor-offset", type=str, help="Décalage curseur X,Y")
    parser.add_argument("--debug", action="store_true", help="Afficher la valeur numérique")
    parser.add_argument("--theme", choices=list(THEMES.keys()), help="Thème de la jauge")
    parser.add_argument("--provider", choices=["sim", "cv"], default="cv", help="Source des données de Heat")
    parser.add_argument("--template", type=Path, help="Chemin vers le template d'icône")
    parser.add_argument("--buffbar", type=str, help="Zone de la barre de buffs (x,y,w,h)")
    parser.add_argument("--ocrp", type=str, help="Zone OCR relative (ox,oy,w,h)")
    parser.add_argument(
        "--tesseract",
        type=Path,
        help="Chemin de l'exécutable Tesseract (sinon détection automatique)",
    )
    parser.add_argument("--log-level", default="INFO", help="Niveau de log")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )


def apply_overrides(config: AppConfig, args: argparse.Namespace) -> None:
    overlay = config.overlay
    if args.mode:
        overlay.mode = args.mode
    if args.size:
        overlay.size = args.size
    if args.ring:
        overlay.ring_width = args.ring
    if args.gap:
        overlay.gap_angle = args.gap
    if args.threshold:
        overlay.threshold = args.threshold
    if args.max:
        overlay.maximum = args.max
    if args.ticks:
        overlay.ticks = tuple(int(x.strip()) for x in args.ticks.split(",") if x.strip())
    if args.cursor_offset:
        try:
            x_str, y_str = args.cursor_offset.split(",")
            overlay.cursor_offset = (int(x_str), int(y_str))
        except Exception as exc:
            raise SystemExit(f"--cursor-offset doit être 'x,y': {exc}") from exc
    if args.debug:
        overlay.show_text = True
    if args.theme:
        overlay.theme = THEMES[args.theme]

    vision = config.vision
    if args.template:
        vision.template_path = args.template
    if args.buffbar:
        parts = [p.strip() for p in args.buffbar.split(",") if p.strip()]
        if len(parts) != 4:
            raise SystemExit("--buffbar doit contenir 4 valeurs x,y,w,h")
        vision.buff_bar_region = tuple(int(v) for v in parts)  # type: ignore[assignment]
    if args.ocrp:
        parts = [p.strip() for p in args.ocrp.split(",") if p.strip()]
        if len(parts) != 4:
            raise SystemExit("--ocrp doit contenir 4 valeurs relatives")
        vision.ocr_relative_rect = tuple(float(v) for v in parts)  # type: ignore[assignment]
    if args.tesseract:
        config.tesseract_cmd = args.tesseract


def _iter_tesseract_candidates() -> list[Path]:
    """Return a list of directories that may contain a bundled Tesseract."""

    candidates: list[Path] = []
    module_dir = Path(__file__).resolve().parent
    candidates.append(module_dir)
    parent = module_dir.parent
    if parent != module_dir:
        candidates.append(parent)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass).resolve())
    # Remove duplicates while preserving order
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def _find_bundled_tesseract() -> Optional[Path]:
    """Search for a packaged Tesseract executable relative to the app."""

    possible_names = [
        Path("tesseract") / "tesseract.exe",
        Path("Tesseract-OCR") / "tesseract.exe",
        Path("tesseract.exe"),
        Path("tesseract") / "tesseract",
        Path("Tesseract-OCR") / "tesseract",
        Path("tesseract"),
    ]
    for base_dir in _iter_tesseract_candidates():
        for relative in possible_names:
            candidate = base_dir / relative
            if candidate.exists():
                return candidate.resolve()
    return None


def auto_configure_tesseract(config: AppConfig) -> None:
    """Populate the Tesseract path if a bundled version is available."""

    current = config.tesseract_cmd
    if current and current.exists():
        LOGGER.debug("Tesseract déjà configuré: %s", current)
        return
    if current and not current.exists():
        LOGGER.warning("Chemin Tesseract configuré introuvable: %s", current)
    detected = _find_bundled_tesseract()
    if detected:
        config.tesseract_cmd = detected
        LOGGER.info("Utilisation de Tesseract packagé: %s", detected)
    elif not current:
        LOGGER.debug("Aucun Tesseract packagé détecté")


class AppController(QtCore.QObject):
    """High level controller hooking UI, provider and calibration together."""

    def __init__(self, app: QtWidgets.QApplication, config: AppConfig, provider: HeatProvider, overlay: OverlayWindow) -> None:
        super().__init__()
        self._app = app
        self._config = config
        self._provider = provider
        self._overlay = overlay
        self._wizard = CalibrationWizard(app, config)
        self._setup_shortcuts()

    def start(self) -> None:
        self._overlay.start()

    def stop(self) -> None:
        self._overlay.stop()

    def _setup_shortcuts(self) -> None:
        shortcuts = {
            "Ctrl+K": self._run_full_wizard,
            "Ctrl+I": self._capture_icon,
            "Ctrl+B": self._capture_buff,
            "Ctrl+O": self._capture_ocr,
        }
        for combo, handler in shortcuts.items():
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(combo), self._overlay)
            shortcut.activated.connect(handler)

    def _reload_provider(self) -> None:
        try:
            if isinstance(self._provider, VisionHeatProvider):
                self._provider.stop()
                new_provider = VisionHeatProvider(self._config)
                self._provider = new_provider
                self._overlay.set_provider(new_provider)
            else:
                self._provider.start()
        except Exception:
            LOGGER.exception("Impossible de redémarrer le provider Vision")

    def _run_full_wizard(self) -> None:
        LOGGER.info("Ctrl+K: relance du wizard complet")
        self._overlay.hide()
        self._provider.stop()
        try:
            result = self._wizard.run_full()
            LOGGER.info("Wizard terminé: %s", result)
        except Exception:
            LOGGER.exception("Erreur durant le wizard complet")
        finally:
            self._reload_provider()
            self._overlay.show()

    def _capture_icon(self) -> None:
        LOGGER.info("Ctrl+I: recalibrage icône")
        self._overlay.hide()
        self._provider.stop()
        try:
            self._wizard.capture_icon()
        except Exception:
            LOGGER.exception("Erreur durant la capture d'icône")
        finally:
            self._reload_provider()
            self._overlay.show()

    def _capture_buff(self) -> None:
        LOGGER.info("Ctrl+B: recalibrage barre de buffs")
        self._overlay.hide()
        self._provider.stop()
        try:
            self._wizard.capture_buff_bar()
        except Exception:
            LOGGER.exception("Erreur durant la capture de la bande de buffs")
        finally:
            self._reload_provider()
            self._overlay.show()

    def _capture_ocr(self) -> None:
        LOGGER.info("Ctrl+O: recalibrage zone OCR")
        self._overlay.hide()
        self._provider.stop()
        try:
            self._wizard.capture_ocr_zone()
        except Exception:
            LOGGER.exception("Erreur durant la capture OCR")
        finally:
            self._reload_provider()
            self._overlay.show()


def build_provider(config: AppConfig, provider_name: str) -> HeatProvider:
    if provider_name == "sim":
        LOGGER.warning("Utilisation du provider simulé - pas de vision réelle")
        return SimulatedHeatProvider(maximum=config.overlay.maximum)
    if provider_name == "cv":
        return VisionHeatProvider(config)
    raise SystemExit(f"Provider non supporté: {provider_name}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    config = AppConfig.load(args.config)
    apply_overrides(config, args)
    auto_configure_tesseract(config)
    config.save(args.config)

    qt_args = sys.argv if argv is None else [sys.argv[0], *argv]
    app = QtWidgets.QApplication(qt_args)

    try:
        provider = build_provider(config, args.provider)
    except Exception as exc:
        LOGGER.error("Impossible d'initialiser le provider %s: %s", args.provider, exc)
        return 1

    overlay = OverlayWindow(config, provider)
    controller = AppController(app, config, provider, overlay)
    controller.start()

    exit_code = app.exec()
    controller.stop()
    return exit_code


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
