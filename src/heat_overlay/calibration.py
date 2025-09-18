"""Calibration wizard utilities."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .config import AppConfig, VisionOptions

LOGGER = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = Path("assets/buff_template_captured.png")


class SelectionOverlay(QtWidgets.QWidget):
    """Full-screen overlay used to capture rectangular selections."""

    selection_made = QtCore.Signal(QtCore.QRect)
    canceled = QtCore.Signal()

    def __init__(self, pixmap: QtGui.QPixmap, instructions: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self._instructions = instructions
        self._start_pos: Optional[QtCore.QPoint] = None
        self._current_rect: Optional[QtCore.QRect] = None
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setWindowState(QtCore.Qt.WindowState.WindowFullScreen)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # pragma: no cover - GUI heavy
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 80))
        if self._current_rect:
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.yellow, 2))
            painter.drawRect(self._current_rect)
        painter.setPen(QtCore.Qt.GlobalColor.white)
        font = painter.font()
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(
            40,
            60,
            self._instructions,
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # pragma: no cover - GUI heavy
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._current_rect = QtCore.QRect(self._start_pos, QtCore.QSize())
            self.update()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.canceled.emit()
            self.close()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # pragma: no cover - GUI heavy
        if self._start_pos is None:
            return
        self._current_rect = QtCore.QRect(self._start_pos, event.pos()).normalized()
        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # pragma: no cover - GUI heavy
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._current_rect:
            self.selection_made.emit(self._current_rect.normalized())
            self.close()


@dataclass
class CalibrationResult:
    template_path: Path
    buff_bar_region: QtCore.QRect
    ocr_relative_rect: tuple[float, float, float, float]


class CalibrationWizard(QtCore.QObject):
    """Interactive calibration wizard."""

    def __init__(self, app: QtWidgets.QApplication, config: AppConfig) -> None:
        super().__init__()
        self._app = app
        self._config = config
        self._screen = QtWidgets.QApplication.primaryScreen()
        if self._screen is None:
            raise RuntimeError("No primary screen detected for calibration")

    def run_full(self) -> Optional[CalibrationResult]:
        LOGGER.info("Starting full calibration wizard")
        screenshot = self._screen.grabWindow(0)
        icon_rect = self._run_selection(screenshot, "Sélectionnez l'icône Rapid Shot (clic gauche, clic droit pour annuler)")
        if icon_rect is None:
            return None
        template_path = self._capture_template(screenshot, icon_rect)

        buff_rect = self._run_selection(screenshot, "Sélectionnez la bande des buffs")
        if buff_rect is None:
            return None

        ocr_rect = self._run_selection(screenshot, "Sélectionnez la zone du chiffre sous l'icône")
        if ocr_rect is None:
            return None

        relative_rect = self._compute_relative_rect(icon_rect, ocr_rect)
        result = CalibrationResult(
            template_path=template_path,
            buff_bar_region=buff_rect,
            ocr_relative_rect=relative_rect,
        )
        self._apply_result(result)
        return result

    def capture_icon(self) -> Optional[Path]:
        screenshot = self._screen.grabWindow(0)
        rect = self._run_selection(screenshot, "Sélectionnez l'icône Rapid Shot")
        if rect is None:
            return None
        template_path = self._capture_template(screenshot, rect)
        self._config.vision.template_path = template_path
        self._config.save()
        return template_path

    def capture_buff_bar(self) -> Optional[QtCore.QRect]:
        screenshot = self._screen.grabWindow(0)
        rect = self._run_selection(screenshot, "Sélectionnez la bande des buffs")
        if rect is None:
            return None
        self._config.vision.buff_bar_region = (rect.x(), rect.y(), rect.width(), rect.height())
        self._config.save()
        return rect

    def capture_ocr_zone(self) -> Optional[tuple[float, float, float, float]]:
        if not self._config.vision.template_path:
            QtWidgets.QMessageBox.warning(None, "Calibration", "Capturez d'abord l'icône Rapid Shot.")
            return None
        screenshot = self._screen.grabWindow(0)
        icon_rect = self._run_selection(screenshot, "Sélectionnez à nouveau l'icône pour référence")
        if icon_rect is None:
            return None
        ocr_rect = self._run_selection(screenshot, "Sélectionnez la zone du chiffre sous l'icône")
        if ocr_rect is None:
            return None
        relative = self._compute_relative_rect(icon_rect, ocr_rect)
        self._config.vision.ocr_relative_rect = relative
        self._config.save()
        return relative

    def _run_selection(self, pixmap: QtGui.QPixmap, message: str) -> Optional[QtCore.QRect]:
        selection = SelectionOverlay(pixmap, message)
        loop = QtCore.QEventLoop()
        result: dict[str, Optional[QtCore.QRect]] = {"rect": None}

        def on_selection(rect: QtCore.QRect) -> None:
            result["rect"] = rect
            loop.quit()

        def on_cancel() -> None:
            result["rect"] = None
            loop.quit()

        selection.selection_made.connect(on_selection)
        selection.canceled.connect(on_cancel)
        selection.show()
        loop.exec()
        selection.deleteLater()
        return result["rect"]

    def _capture_template(self, pixmap: QtGui.QPixmap, rect: QtCore.QRect) -> Path:
        template_path = self._config.vision.template_path or DEFAULT_TEMPLATE_PATH
        template_path.parent.mkdir(parents=True, exist_ok=True)
        crop = pixmap.copy(rect)
        crop.save(str(template_path), "PNG")
        self._config.vision.template_path = template_path
        self._config.save()
        LOGGER.info("Template saved to %s", template_path)
        return template_path

    def _compute_relative_rect(self, icon_rect: QtCore.QRect, ocr_rect: QtCore.QRect) -> tuple[float, float, float, float]:
        if icon_rect.width() == 0 or icon_rect.height() == 0:
            raise ValueError("Icon rect must have non-zero size")
        ox_rel = (ocr_rect.x() - icon_rect.x()) / icon_rect.width()
        oy_rel = (ocr_rect.y() - icon_rect.y()) / icon_rect.height()
        w_rel = ocr_rect.width() / icon_rect.width()
        h_rel = ocr_rect.height() / icon_rect.height()
        relative = (ox_rel, oy_rel, w_rel, h_rel)
        self._config.vision.ocr_relative_rect = relative
        self._config.save()
        LOGGER.info("OCR relative rect computed: %s", relative)
        return relative

    def _apply_result(self, result: CalibrationResult) -> None:
        vision = self._config.vision
        vision.template_path = result.template_path
        vision.buff_bar_region = (
            result.buff_bar_region.x(),
            result.buff_bar_region.y(),
            result.buff_bar_region.width(),
            result.buff_bar_region.height(),
        )
        vision.ocr_relative_rect = result.ocr_relative_rect
        self._config.save()
        LOGGER.info("Calibration complete")
