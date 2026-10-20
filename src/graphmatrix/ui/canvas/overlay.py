"""Chrome drawn on top of a plot canvas — tools, panel marker, data readout.

Everything in here is a plain Qt widget, never a matplotlib artist. That is the
whole point: the readout and the tool buttons are *interface*, not figure
content, so they can never leak into an exported file (the exporter renders
the matplotlib figure, not the widget tree).

The canvas is split in two parts:

* :class:`CanvasTools` - the zoom / fit / readout buttons. They live on the
  *workspace* around the figure, so they never cover the plot and never
  hide part of the figure (and they always work: they are ordinary widgets).
* :class:`CanvasOverlay` - the panel marker ("Panel 2 / 4"), the readout of
  the point under the pointer and the frame around the panel being edited.
  It floats over the figure and is transparent for the mouse, so the canvas
  keeps every click.

There is deliberately **no crosshair**: a cross that spans the whole figure
pretends that a stack, a twin or a grid of panels is one single plot.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from graphmatrix.ui import theme
from graphmatrix.ui.icons import ui_icon

#: How long the overlay stays visible after the pointer leaves the canvas.
FADE_DELAY_MS = 1200


def _chrome(dark: bool) -> dict[str, str]:
    """The colours of the floating chrome, for the dark or the light theme."""
    if dark:
        return {
            "bg": "rgba(20,21,25,215)",
            "solid": "rgb(20,21,25)",
            "fg": "#d7dae0",
            "border": "rgba(255,255,255,28)",
            "hover": "rgba(255,255,255,30)",
            "checked": "rgba(76,141,255,70)",
        }
    return {
        "bg": "rgba(255,255,255,235)",
        "solid": "rgb(255,255,255)",
        "fg": "#3a3f47",
        "border": "rgba(0,0,0,45)",
        "hover": "rgba(0,0,0,25)",
        "checked": "rgba(47,111,235,45)",
    }


def tools_qss() -> str:
    """Style sheet of the tool strip, drawn in the current theme's colours."""
    c = _chrome(theme.is_dark())
    return (
        f"QFrame {{ background: {c['bg']}; border: 1px solid {c['border']};"
        " border-radius: 6px; }"
        f"QToolButton {{ background: transparent; border: none; padding: 2px 6px;"
        f" color: {c['fg']}; font-size: 12pt; }}"
        f"QToolButton:hover {{ background: {c['hover']}; border-radius: 4px; }}"
        f"QToolButton:checked {{ background: {c['checked']}; border-radius: 4px; }}"
    )


def _data_point_icon(size: int = 14, color: str = "#d7dae0") -> QIcon:
    """A small drawn data point (a dot in a ring), for the readout toggle."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidth(1)
    painter.setPen(pen)
    mid = size / 2.0
    painter.drawEllipse(
        int(mid - size / 2.0) + 1,
        int(mid - size / 2.0) + 1,
        size - 2,
        size - 2,
    )
    painter.setBrush(QColor(color))
    painter.drawEllipse(
        int(mid - size / 6.0),
        int(mid - size / 6.0),
        int(size / 3.0),
        int(size / 3.0),
    )
    painter.end()
    return QIcon(pixmap)


class CanvasTools(QFrame):
    """The zoom / fit / readout buttons of a canvas.

    They are ordinary widgets: whatever they are placed on stays clickable,
    and they never cover the figure itself.
    """

    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_requested = Signal()
    hover_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("canvasTools")
        self.refresh_theme()
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 1, 3, 1)
        row.setSpacing(1)
        self._zoom_in = self._tool_button(
            ui_icon("zoom-in"), "Zoom in (Ctrl++)", self.zoom_in_requested.emit
        )
        self._zoom_out = self._tool_button(
            ui_icon("zoom-out"), "Zoom out (Ctrl+-)", self.zoom_out_requested.emit
        )
        self._fit = self._tool_button(
            ui_icon("scan"),
            "Fit the data to the panel (Ctrl+0)",
            self.fit_requested.emit,
        )
        # The current zoom, shown as a button: clicking it fits the data
        # again, so the number is also the way back.
        self._zoom_label = QToolButton(self)
        self._zoom_label.setText("100%")
        self._zoom_label.setToolTip(
            "Current zoom of the panel. Click to fit the data to it."
        )
        self._zoom_label.setAutoRaise(True)
        self._zoom_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._zoom_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_label.clicked.connect(self.fit_requested.emit)
        self._hover = self._tool_button(
            ui_icon("crosshair"), "Data readout (hover a point)", self._toggle_hover
        )
        self._hover.setCheckable(True)
        self._hover.setChecked(True)
        for button in (
            self._zoom_in,
            self._zoom_out,
            self._fit,
            self._zoom_label,
            self._hover,
        ):
            row.addWidget(button)

    def refresh_theme(self) -> None:
        """Re-draw the strip in the colours of the current theme."""
        self.setStyleSheet(tools_qss())

    def _tool_button(self, icon: QIcon, tip: str, slot) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def set_zoom_level(self, factor: float) -> None:
        """Show how far the panel is zoomed in (``1.0`` = the data's own range)."""
        try:
            percent = int(round(float(factor) * 100))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            percent = 100
        self._zoom_label.setText(f"{percent}%")
        self._zoom_label.setToolTip(
            f"Zoom: {percent}% of the data range. Click to fit the data to the panel."
        )

    def _toggle_hover(self) -> None:
        self.hover_toggled.emit(self._hover.isChecked())

    def set_hover_checked(self, checked: bool) -> None:
        """Show the readout toggle in the state the canvas is in."""
        self._hover.setChecked(bool(checked))

    def place(self, container: QWidget, *, margin: int = 8, top: bool = True) -> None:
        """Put the strip in a corner of ``container``."""
        size = self.sizeHint()
        self.resize(size)
        x = max(0, container.width() - size.width() - margin)
        y = margin if top else max(0, container.height() - size.height() - margin)
        self.move(x, y)


class CanvasOverlay(QWidget):
    """Floating, themed chrome for a plot canvas."""

    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_requested = Signal()
    hover_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The overlay floats over the whole figure, so it must not swallow the
        # pointer events meant for the canvas (hover readout, point picking).
        # It has no interactive children any more, so the transparent
        # attribute is exactly right here.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._bg = "#191a1d"
        self._fg = "#d7dae0"
        self._accent = "#4c8dff"
        self._panel_rect: QRect | None = None
        self._panel_text = ""
        self._readout_text = ""
        self._hover_enabled = True
        self._user_visible = True

        # -- labels ---------------------------------------------------------
        self._panel_label = QLabel(self)
        self._panel_label.hide()

        self._readout_label = QLabel(self)
        self._readout_label.hide()
        self._apply_label_styles()

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
        self._apply_label_styles()
        self.update()

    def _apply_label_styles(self) -> None:
        """Draw the floating labels in the colours of the current theme."""
        c = _chrome(theme.is_dark())
        text = self._fg or c["fg"]
        self._readout_label.setStyleSheet(
            f"background: {c['bg']}; color: {text}; border-radius: 4px;"
            " padding: 2px 7px; font-size: 10pt;"
        )
        self._panel_label.setStyleSheet(
            f"background: {c['bg']}; color: {text}; border-radius: 4px;"
            " padding: 1px 6px; font-size: 10pt;"
        )

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
        self._layout_children()
        self.update()

    def set_readout(self, text: str, force: bool = False) -> None:
        """Show the hover readout (an empty string hides it).

        ``force`` keeps the text up even when the readout is switched off -
        that is how the values of a clicked point stay visible.
        """
        self._readout_text = text or ""
        self._readout_label.setText(self._readout_text)
        self._readout_label.setVisible(
            bool(self._readout_text)
            and (self._hover_enabled or force)
            and self.isVisible()
        )
        # The text is longer than the placeholder, so the label has to be
        # measured and placed again - otherwise it stays one character wide.
        self._layout_children()

    def set_hover_enabled(self, enabled: bool) -> None:
        """Turn the readout on or off."""
        self._hover_enabled = bool(enabled)
        if not self._hover_enabled:
            self._readout_text = ""
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
        painter.end()


    # -- geometry ------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._layout_children()

    def _layout_children(self) -> None:
        margin = 8
        if self._panel_label.text():
            self._panel_label.adjustSize()
            self._panel_label.move(margin, margin)
        self._readout_label.adjustSize()
        self._readout_label.move(margin, max(0, self.height() - self._readout_label.height() - margin))

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

    def __init__(
        self,
        overlay: CanvasOverlay,
        parent: QObject,
        tools: CanvasTools | None = None,
    ) -> None:
        super().__init__(parent)
        self._overlay = overlay
        self._tools = tools

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        kind = event.type()
        if kind == QEvent.Type.Resize:
            self._overlay.setGeometry(obj.rect())
            if self._tools is not None:
                self._tools.place(obj)
        elif kind == QEvent.Type.Enter:
            self._overlay.set_user_visible(True)
        elif kind == QEvent.Type.Leave:
            self._overlay.set_user_visible(False)
        return False


def watch_container(
    container: QWidget,
    overlay: CanvasOverlay,
    tools: CanvasTools | None = None,
) -> _ContainerWatcher:
    """Attach an overlay to a container: sized with it, shown on hover."""
    watcher = _ContainerWatcher(overlay, container, tools)
    container.installEventFilter(watcher)
    overlay.setGeometry(container.rect())
    if tools is not None:
        tools.place(container)
    return watcher


__all__ = [
    "FADE_DELAY_MS",
    "CanvasOverlay",
    "CanvasTools",
    "watch_container",
]
