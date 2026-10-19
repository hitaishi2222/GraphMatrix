"""Chrome drawn on top of a plot canvas — tools, panel marker, data readout.

Everything in here is a plain Qt widget, never a matplotlib artist. That is the
whole point: the readout, the crosshair and the tool buttons are *interface*,
not figure content, so they can never leak into an exported file (the
exporter renders the matplotlib figure, not the widget tree).

The overlay is a child of the canvas container and floats above the plot:

* top right — zoom in / zoom out / fit / readout toggle;
* top left — which panel you are editing ("Panel 2 / 4");
* bottom left — the hover readout;
* a thin accent frame around the panel that is currently being edited.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

#: How long the overlay stays visible after the pointer leaves the canvas.
FADE_DELAY_MS = 1200


class CanvasOverlay(QWidget):
    """Floating, themed chrome for a plot canvas."""

    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_requested = Signal()
    hover_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The overlay itself must never swallow pointer events meant for the
        # plot; its buttons stay interactive because they are child widgets.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._bg = "#191a1d"
        self._fg = "#d7dae0"
        self._accent = "#4c8dff"
        self._panel_rect: QRect | None = None
        self._panel_text = ""
        self._readout_text = ""
        self._crosshair: QPoint | None = None
        self._hover_enabled = True
        self._user_visible = True

        # -- tool buttons ---------------------------------------------------
        self._tools = QFrame(self)
        self._tools.setObjectName("canvasTools")
        self._tools.setStyleSheet(
            "QFrame { background: rgba(20,21,25,215); border: 1px solid rgba(255,255,255,28);"
            " border-radius: 6px; }"
            "QToolButton { background: transparent; border: none; padding: 2px 6px;"
            " color: #d7dae0; font-size: 12pt; }"
            "QToolButton:hover { background: rgba(255,255,255,30); border-radius: 4px; }"
            "QToolButton:checked { background: rgba(76,141,255,70); border-radius: 4px; }"
        )
        row = QHBoxLayout(self._tools)
        row.setContentsMargins(3, 1, 3, 1)
        row.setSpacing(1)
        self._zoom_in = self._tool_button("＋", "Zoom in", self.zoom_in_requested.emit)
        self._zoom_out = self._tool_button("－", "Zoom out", self.zoom_out_requested.emit)
        self._fit = self._tool_button("⤢", "Fit the data to the panel", self.fit_requested.emit)
        self._hover = self._tool_button("✛", "Data readout", self._toggle_hover)
        self._hover.setCheckable(True)
        self._hover.setChecked(True)
        for button in (self._zoom_in, self._zoom_out, self._fit, self._hover):
            row.addWidget(button)

        # -- labels ---------------------------------------------------------
        self._panel_label = QLabel(self)
        self._panel_label.setStyleSheet(
            "background: rgba(20,21,25,200); color: #d7dae0; border-radius: 4px;"
            " padding: 1px 6px; font-size: 10pt;"
        )
        self._panel_label.hide()

        self._readout_label = QLabel(self)
        self._readout_label.setStyleSheet(
            "background: rgba(20,21,25,215); color: #e8eaed; border-radius: 4px;"
            " padding: 2px 7px; font-size: 10pt;"
        )
        self._readout_label.hide()

        # -- opacity (fade in/out) ------------------------------------------
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setDuration(160)
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.setInterval(FADE_DELAY_MS)
        self._fade_timer.timeout.connect(self._fade_out)

    # -- public API ----------------------------------------------------------
    def set_colors(self, background: str, foreground: str, accent: str = "") -> None:
        """Adopt the canvas theme colours."""
        self._bg = background
        self._fg = foreground
        if accent:
            self._accent = accent
        self._readout_label.setStyleSheet(
            f"background: rgba(20,21,25,215); color: {foreground}; border-radius: 4px;"
            " padding: 2px 7px; font-size: 10pt;"
        )
        self._panel_label.setStyleSheet(
            f"background: rgba(20,21,25,200); color: {foreground}; border-radius: 4px;"
            " padding: 1px 6px; font-size: 10pt;"
        )
        self.update()

    def set_panel(self, index: int, total: int, rect: QRect | None = None) -> None:
        """Mark the panel being edited.

        ``index`` is 0-based; with a single panel nothing is shown. ``rect`` is
        the panel's area in widget pixels and gets a thin accent frame.
        """
        if total <= 1:
            self._panel_text = ""
            self._panel_rect = None
        else:
            self._panel_text = f"Panel {index + 1} / {total}"
            self._panel_rect = rect
        self._panel_label.setText(self._panel_text)
        self._panel_label.setVisible(bool(self._panel_text) and self.isVisible())
        self.update()

    def set_readout(self, text: str) -> None:
        """Show the hover readout (an empty string hides it)."""
        self._readout_text = text or ""
        self._readout_label.setText(self._readout_text)
        self._readout_label.setVisible(
            bool(self._readout_text) and self._hover_enabled and self.isVisible()
        )

    def set_crosshair(self, point: QPoint | None) -> None:
        """Position the crosshair (widget pixels) or hide it with ``None``."""
        self._crosshair = point
        self.update()

    def set_hover_enabled(self, enabled: bool) -> None:
        """Turn the readout (and its crosshair) on or off."""
        self._hover_enabled = bool(enabled)
        self._hover.setChecked(self._hover_enabled)
        if not self._hover_enabled:
            self._readout_text = ""
            self._crosshair = None
            self._readout_label.hide()
            self.update()

    def set_user_visible(self, visible: bool) -> None:
        """Show or hide the whole overlay (used when the pointer leaves)."""
        self._user_visible = bool(visible)
        if visible:
            self._fade_in()
        else:
            self._fade_timer.start()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self._panel_rect is not None:
            pen = QPen(QColor(self._accent))
            pen.setWidth(1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            # Inset a little so the frame hugs the panel without touching the
            # neighbouring axes' labels.
            painter.drawRect(self._panel_rect.adjusted(1, 1, -2, -2))
        if self._crosshair is not None and self._hover_enabled:
            pen = QPen(QColor(self._fg))
            pen.setWidth(1)
            painter.setPen(pen)
            x, y = self._crosshair.x(), self._crosshair.y()
            painter.drawLine(x, 0, x, self.height())
            painter.drawLine(0, y, self.width(), y)
        painter.end()

    # -- geometry ------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._layout_children()

    def _layout_children(self) -> None:
        margin = 8
        tools = self._tools.sizeHint()
        self._tools.move(self.width() - tools.width() - margin, margin)
        if self._panel_label.text():
            self._panel_label.adjustSize()
            self._panel_label.move(margin, margin)
        self._readout_label.adjustSize()
        self._readout_label.move(margin, max(0, self.height() - self._readout_label.height() - margin))

    # -- helpers -------------------------------------------------------------
    def _tool_button(self, text: str, tip: str, slot) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _toggle_hover(self) -> None:
        enabled = self._hover.isChecked()
        self._hover_enabled = enabled
        if not enabled:
            self._readout_text = ""
            self._readout_label.hide()
            self._crosshair = None
            self.update()
        self.hover_toggled.emit(enabled)

    def _fade_in(self) -> None:
        self._fade_timer.stop()
        self.show()
        self._animation.stop()
        self._animation.setStartValue(float(self._effect.opacity()))
        self._animation.setEndValue(1.0)
        self._animation.start()
        self._panel_label.setVisible(bool(self._panel_text))
        self._readout_label.setVisible(
            bool(self._readout_text) and self._hover_enabled
        )

    def _fade_out(self) -> None:
        if not self._user_visible:
            return
        self._animation.stop()
        self._animation.setStartValue(float(self._effect.opacity()))
        self._animation.setEndValue(0.0)
        self._animation.start()
        self._panel_label.hide()
        self._readout_label.hide()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._layout_children()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().hideEvent(event)
        self._panel_label.hide()
        self._readout_label.hide()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(self.width(), self.height())


class _ContainerWatcher(QObject):
    """Keeps the overlay sized and visible in step with its container."""

    def __init__(self, overlay: CanvasOverlay, parent: QObject) -> None:
        super().__init__(parent)
        self._overlay = overlay

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        kind = event.type()
        if kind == QEvent.Type.Resize:
            self._overlay.setGeometry(obj.rect())
        elif kind == QEvent.Type.Enter:
            self._overlay.set_user_visible(True)
        elif kind == QEvent.Type.Leave:
            self._overlay.set_user_visible(False)
        return False


def watch_container(container: QWidget, overlay: CanvasOverlay) -> _ContainerWatcher:
    """Attach an overlay to a container: sized with it, shown on hover."""
    watcher = _ContainerWatcher(overlay, container)
    container.installEventFilter(watcher)
    overlay.setGeometry(container.rect())
    return watcher


__all__ = ["FADE_DELAY_MS", "CanvasOverlay", "watch_container"]
