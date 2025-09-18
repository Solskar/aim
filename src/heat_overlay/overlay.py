"""Overlay window and gauge rendering."""
from __future__ import annotations

import logging
import math
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .config import AppConfig, GaugeTheme, OverlayOptions
from .providers import HeatProvider

LOGGER = logging.getLogger(__name__)


class GaugeWidget(QtWidgets.QWidget):
    """Custom widget rendering the circular gauge."""

    def __init__(self, options: OverlayOptions, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._options = options
        self._value = 0
        self._maximum = max(options.maximum, 1)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(options.size, options.size)

    def set_value(self, value: int) -> None:
        value = max(0, min(self._maximum, value))
        if value != self._value:
            self._value = value
            self.update()

    def set_maximum(self, maximum: int) -> None:
        self._maximum = max(1, maximum)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # pragma: no cover - GUI
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height())
        margin = self._options.ring_width // 2 + 4
        rect = QtCore.QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        start_angle = 90 + self._options.gap_angle / 2
        span_angle = 360 - self._options.gap_angle
        progress = min(1.0, self._value / float(self._maximum))
        span_progress = span_angle * progress

        pen = QtGui.QPen(QtGui.QColor(self._options.theme.background_color))
        pen.setWidth(self._options.ring_width)
        painter.setPen(pen)
        painter.drawArc(rect, int(start_angle * 16), int(-span_angle * 16))

        gradient = QtGui.QConicalGradient(rect.center(), start_angle - span_progress)
        gradient.setColorAt(0.0, QtGui.QColor(self._options.theme.end_color))
        gradient.setColorAt(1.0, QtGui.QColor(self._options.theme.start_color))
        pen.setColor(QtGui.QColor(self._options.theme.start_color))
        pen.setBrush(gradient)
        painter.setPen(pen)
        painter.drawArc(rect, int(start_angle * 16), int(-span_progress * 16))

        painter.setPen(QtGui.QPen(QtGui.QColor(self._options.theme.tick_color), 2))
        for tick_value in self._options.ticks:
            angle_ratio = min(1.0, max(0.0, tick_value / float(self._maximum)))
            tick_angle = start_angle - span_angle * angle_ratio
            painter.drawLine(
                self._point_on_circle(rect.center(), rect.width() / 2, tick_angle),
                self._point_on_circle(rect.center(), rect.width() / 2 - self._options.ring_width, tick_angle),
            )

        if self._value >= self._options.threshold:
            halo = QtGui.QColor(self._options.theme.halo_color)
            halo_pen = QtGui.QPen(halo)
            halo_pen.setWidth(self._options.ring_width + 6)
            painter.setPen(halo_pen)
            painter.drawArc(rect.adjusted(-6, -6, 6, 6), int(start_angle * 16), int(-span_progress * 16))

        if self._options.show_text:
            painter.setPen(QtGui.QColor(self._options.theme.text_color))
            font = painter.font()
            font.setPointSize(max(10, self.width() // 10))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, str(self._value))

    @staticmethod
    def _point_on_circle(center: QtCore.QPointF, radius: float, angle_degrees: float) -> QtCore.QPointF:
        rad = angle_degrees * 3.14159265 / 180.0
        return QtCore.QPointF(
            center.x() + radius * math.cos(rad),
            center.y() - radius * math.sin(rad),
        )


class OverlayWindow(QtWidgets.QWidget):
    """Main overlay window that is transparent and click-through."""

    heat_updated = QtCore.Signal(int)

    def __init__(self, config: AppConfig, provider: HeatProvider) -> None:
        super().__init__(None, QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self._config = config
        self._provider = provider
        self._options = config.overlay
        self._gauge = GaugeWidget(self._options)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._update_heat)
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._gauge, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlag(QtCore.Qt.WindowType.Tool)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowFlag(QtCore.Qt.WindowType.NoDropShadowWindowHint)
        self.setWindowTitle("Rapid Shot Heat Overlay")
        self.resize(self._options.size, self._options.size)
        self._cursor_timer: Optional[QtCore.QTimer] = None
        self._setup_cursor_tracking()
        self.heat_updated.connect(self._gauge.set_value)

    def start(self) -> None:
        self._provider.start()
        self._timer.start()
        if self._options.mode == "cursor" and self._cursor_timer:
            self._cursor_timer.start()
        self.show()
        self._reposition()

    def stop(self) -> None:
        self._timer.stop()
        self._provider.stop()
        if self._cursor_timer:
            self._cursor_timer.stop()

    def set_provider(self, provider: HeatProvider) -> None:
        if provider is self._provider:
            return
        self.stop()
        self._provider = provider
        self.start()

    def _setup_cursor_tracking(self) -> None:
        if self._options.mode == "cursor":
            self._cursor_timer = QtCore.QTimer(self)
            self._cursor_timer.setInterval(30)
            self._cursor_timer.timeout.connect(self._follow_cursor)
            self._cursor_timer.start()
        else:
            self._cursor_timer = None

    def _follow_cursor(self) -> None:
        cursor_pos = QtGui.QCursor.pos()
        offset = self._options.cursor_offset
        new_pos = QtCore.QPoint(cursor_pos.x() + offset[0], cursor_pos.y() + offset[1])
        self.move(new_pos)

    def _update_heat(self) -> None:
        value = self._provider.get_heat()
        if value is not None:
            self.heat_updated.emit(int(value))
        if self._options.mode == "center":
            self._reposition()

    def _reposition(self) -> None:
        if self._options.mode != "center":
            return
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen:
            return
        geometry = screen.availableGeometry()
        x = geometry.center().x() - self.width() // 2
        y = geometry.center().y() - self.height() // 2
        self.move(x, y)
