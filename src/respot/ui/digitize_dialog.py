"""Digitize a curve from an image: pick anchors, extract points.

The dialog is a thin shell over :func:`respot.core.analysis.digitize.digitize_curve`.
Click four calibration points on the image in order (X1, X2, Y1, Y2), type the data
value each corresponds to, then Extract. The pixel coordinates are also editable, so
you can nudge an anchor without re-clicking.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from respot.core.analysis.digitize import digitize_curve

_ANCHOR_LABELS = ("X1", "X2", "Y1", "Y2")
_ANCHOR_COLORS = ("#1f77b4", "#17becf", "#2ca02c", "#ff7f0e")


class _ImageCanvas(QLabel):
    """Shows an image scaled to fit and reports clicks in image-pixel coordinates."""

    clicked = Signal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #202020;")
        self._pixmap: QPixmap | None = None
        self._markers: list[tuple[float, float, str, str]] = []

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._markers = []
        self.update()

    def set_markers(self, markers: list[tuple[float, float, str, str]]) -> None:
        self._markers = markers
        self.update()

    @property
    def image_size(self) -> tuple[int, int]:
        if self._pixmap is None:
            return (0, 0)
        return (self._pixmap.width(), self._pixmap.height())

    def _placement(self) -> tuple[float, float, float, float, float]:
        assert self._pixmap is not None
        available_w, available_h = self.width(), self.height()
        image_w, image_h = self._pixmap.width(), self._pixmap.height()
        scale = min(available_w / image_w, available_h / image_h)
        drawn_w, drawn_h = image_w * scale, image_h * scale
        offset_x, offset_y = (available_w - drawn_w) / 2, (available_h - drawn_h) / 2
        return scale, offset_x, offset_y, drawn_w, drawn_h

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().paintEvent(event)
        if self._pixmap is None:
            return
        scale, offset_x, offset_y, drawn_w, drawn_h = self._placement()
        painter = QPainter(self)
        painter.drawPixmap(QRectF(offset_x, offset_y, drawn_w, drawn_h), self._pixmap,
                           QRectF(self._pixmap.rect()))
        for px, py, label, color in self._markers:
            cx = offset_x + px * scale
            cy = offset_y + py * scale
            pen = QPen(QColor(color), 2)
            painter.setPen(pen)
            painter.drawLine(int(cx - 7), int(cy), int(cx + 7), int(cy))
            painter.drawLine(int(cx), int(cy - 7), int(cx), int(cy + 7))
            painter.setPen(QPen(QColor(color)))
            painter.drawText(int(cx + 8), int(cy - 8), label)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._pixmap is None:
            return
        scale, offset_x, offset_y, _w, _h = self._placement()
        if scale <= 0:
            return
        position = event.position()
        image_x = (position.x() - offset_x) / scale
        image_y = (position.y() - offset_y) / scale
        image_x = max(0.0, min(self._pixmap.width() - 1, image_x))
        image_y = max(0.0, min(self._pixmap.height() - 1, image_y))
        self.clicked.emit(image_x, image_y)


class DigitizeDialog(QDialog):
    """Collects anchors + options; :meth:`run` returns the digitized curve."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Digitize Curve from Image")
        self.resize(820, 640)
        self._image_path: Path | None = None
        self._click_index = 0

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.load_button = QPushButton("Load Image…")
        self.load_button.clicked.connect(self._choose_image)
        self.reset_button = QPushButton("Reset Anchors")
        self.reset_button.clicked.connect(self._reset_anchors)
        self.hint = QLabel("Load an image, then click the calibration points in order: X1, X2, Y1, Y2.")
        top.addWidget(self.load_button)
        top.addWidget(self.reset_button)
        top.addWidget(self.hint, 1)
        layout.addLayout(top)

        self.canvas = _ImageCanvas()
        self.canvas.clicked.connect(self._on_click)
        layout.addWidget(self.canvas, 1)

        anchors = QGridLayout()
        anchors.addWidget(QLabel("Point"), 0, 0)
        anchors.addWidget(QLabel("Pixel"), 0, 1)
        anchors.addWidget(QLabel("Value"), 0, 2)
        self._pixel_spins: list[QSpinBox] = []
        self._value_spins: list[QDoubleSpinBox] = []
        for row, label in enumerate(_ANCHOR_LABELS, start=1):
            anchors.addWidget(QLabel(label), row, 0)
            pixel = QSpinBox()
            pixel.setRange(0, 100000)
            value = QDoubleSpinBox()
            value.setRange(-1e9, 1e9)
            value.setDecimals(6)
            value.setValue(float(row))
            self._pixel_spins.append(pixel)
            self._value_spins.append(value)
            anchors.addWidget(pixel, row, 1)
            anchors.addWidget(value, row, 2)
        layout.addLayout(anchors)

        options = QFormLayout()
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.0, 1.0)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.5)
        options.addRow("Darkness threshold:", self.threshold)

        self.invert = QCheckBox("Curve is lighter than the background")
        options.addRow("", self.invert)

        self.aggregate = QComboBox()
        self.aggregate.addItems(["median", "mean", "top", "bottom"])
        options.addRow("Column sample:", self.aggregate)

        color_row = QHBoxLayout()
        self.use_color = QCheckBox("Isolate colour")
        self.color = QLineEdit("#ff0000")
        self.color.setMaximumWidth(90)
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setRange(0.0, 1.0)
        self.tolerance.setSingleStep(0.02)
        self.tolerance.setValue(0.12)
        color_row.addWidget(self.use_color)
        color_row.addWidget(self.color)
        color_row.addWidget(QLabel("tolerance"))
        color_row.addWidget(self.tolerance)
        color_row.addStretch(1)
        options.addRow("", color_row)
        layout.addLayout(options)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Extract")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- anchors -------------------------------------------------------------
    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All files (*)"
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self._image_path = Path(path)
        self.canvas.set_image(pixmap)
        width, height = self.canvas.image_size
        self._pixel_spins[1].setValue(max(0, width - 1))
        self._pixel_spins[3].setValue(max(0, height - 1))
        self._click_index = 0
        self._refresh_markers()

    def _reset_anchors(self) -> None:
        self._click_index = 0
        for spin in self._pixel_spins:
            spin.setValue(0)
        self._refresh_markers()

    def _on_click(self, x: float, y: float) -> None:
        index = min(self._click_index, 3)
        if index < 2:
            self._pixel_spins[index].setValue(int(round(x)))
        else:
            self._pixel_spins[index].setValue(int(round(y)))
        self._click_index = min(self._click_index + 1, 4)
        self._refresh_markers()

    def _markers(self) -> list[tuple[float, float, str, str]]:
        markers = []
        for index, label in enumerate(_ANCHOR_LABELS):
            pixel = float(self._pixel_spins[index].value())
            if index < 2:
                markers.append((pixel, 0.0, label, _ANCHOR_COLORS[index]))
            else:
                markers.append((0.0, pixel, label, _ANCHOR_COLORS[index]))
        return markers

    def _refresh_markers(self) -> None:
        self.canvas.set_markers(self._markers())

    # -- extraction ----------------------------------------------------------
    def _trace_color(self) -> tuple[float, float, float] | None:
        if not self.use_color.isChecked():
            return None
        color = QColor(self.color.text().strip())
        if not color.isValid():
            return None
        return (color.redF(), color.greenF(), color.blueF())

    def run(self):
        if self._image_path is None:
            raise ValueError("Load an image before extracting.")
        x_anchors = ((float(self._pixel_spins[0].value()), self._value_spins[0].value()),
                     (float(self._pixel_spins[1].value()), self._value_spins[1].value()))
        y_anchors = ((float(self._pixel_spins[2].value()), self._value_spins[2].value()),
                     (float(self._pixel_spins[3].value()), self._value_spins[3].value()))
        return digitize_curve(
            self._image_path,
            x_anchors=x_anchors,
            y_anchors=y_anchors,
            threshold=self.threshold.value(),
            invert=self.invert.isChecked(),
            color=self._trace_color(),
            tolerance=self.tolerance.value(),
            aggregate=self.aggregate.currentText(),
        )

    def sheet(self):
        return None


__all__ = ["DigitizeDialog"]
