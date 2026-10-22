"""User preferences: a small persisted store and the dialog that edits it.

Everything here is a *setting the user can change* and that the application
actually honours - there are no decorative switches. The values live in
``QSettings`` (next to the theme preset), so they survive a restart.

The store is deliberately tiny and framework-free: :func:`get` and
:func:`set` are enough for the rest of the UI, and a missing or unreadable
setting falls back to its default instead of raising.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.ui import theme

#: Preference key -> default value. The keys are the stored names.
DEFAULTS: dict[str, Any] = {
    # Export
    "export/format": "pdf",
    "export/dpi": 300,
    "export/width_mm": 100.0,
    "export/height_mm": 75.0,
    # Worksheet
    # -1 means "use the general number format"; 0..12 fix the decimals of
    # newly created columns.
    "worksheet/new_column_decimals": -1,
    # Canvas
    "canvas/wheel_zoom": True,
    # General
    "general/warn_on_discard": True,
}


def _settings() -> QSettings | None:
    """The settings store, or None when the app has no name (headless tests)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None or not app.organizationName():
        return None
    return QSettings()


def get(key: str, default: Any = None) -> Any:
    """Read a preference, falling back to its default."""
    if key not in DEFAULTS:
        return default
    fallback = DEFAULTS[key] if default is None else default
    settings = _settings()
    if settings is None:
        return fallback
    value = settings.value(f"preferences/{key}", fallback)
    if isinstance(fallback, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if isinstance(fallback, int) and not isinstance(fallback, bool):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
    if isinstance(fallback, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
    return value


def set_value(key: str, value: Any) -> None:
    """Store a preference (no-op without a settings store)."""
    settings = _settings()
    if settings is None:
        return
    settings.setValue(f"preferences/{key}", value)


def reset() -> None:
    """Put every preference back to its default."""
    settings = _settings()
    if settings is None:
        return
    for key in DEFAULTS:
        settings.remove(f"preferences/{key}")


def new_column_decimals() -> int | None:
    """The decimals a new column should get, or None for the general format."""
    value = int(get("worksheet/new_column_decimals", -1))
    return None if value < 0 else value


#: The file formats the export dialog offers.
EXPORT_FORMATS = ("pdf", "svg", "eps", "png", "tif", "jpg")


class PreferencesDialog(QDialog):
    """Edits the preferences and applies them when the dialog is accepted."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(520, 480)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._appearance_tab(), "Appearance")
        self.tabs.addTab(self._worksheet_tab(), "Worksheet")
        self.tabs.addTab(self._canvas_tab(), "Canvas")
        self.tabs.addTab(self._export_tab(), "Export")
        self.tabs.addTab(self._general_tab(), "General")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
        layout.addWidget(buttons)

    # -- tabs ---------------------------------------------------------------
    def _appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.theme_combo = QComboBox()
        for preset in theme.presets():
            self.theme_combo.addItem(preset.label, preset.id)
            self.theme_combo.setItemData(
                self.theme_combo.count() - 1,
                preset.description,
                Qt.ItemDataRole.ToolTipRole,
            )
        current = theme.current_preset()
        index = self.theme_combo.findData(current)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        form.addRow("Theme:", self.theme_combo)
        hint = QLabel(
            "The theme also sets the colours of the plot canvas, so the "
            "screen and the exported figure match."
        )
        hint.setWordWrap(True)
        hint.setEnabled(False)
        form.addRow(hint)
        return page

    def _worksheet_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.decimals_combo = QComboBox()
        self.decimals_combo.addItem("General format", -1)
        for value in range(13):
            self.decimals_combo.addItem(f"{value} decimals", value)
        decimals = int(get("worksheet/new_column_decimals", -1))
        index = self.decimals_combo.findData(decimals)
        self.decimals_combo.setCurrentIndex(max(0, index))
        form.addRow("New columns:", self.decimals_combo)
        hint = QLabel(
            "How many decimals a newly created column shows. "
            "'General format' keeps the shortest exact number."
        )
        hint.setWordWrap(True)
        hint.setEnabled(False)
        form.addRow(hint)
        return page

    def _canvas_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.wheel_zoom = QCheckBox("Zoom the panel with Ctrl + mouse wheel")
        self.wheel_zoom.setChecked(bool(get("canvas/wheel_zoom", True)))
        self.wheel_zoom.setToolTip(
            "The pointer stays on the same data point while you zoom."
        )
        form.addRow(self.wheel_zoom)
        hint = QLabel(
            "The tool strip above the figure always offers zoom in, zoom out "
            "and fit; the wheel is an extra shortcut."
        )
        hint.setWordWrap(True)
        hint.setEnabled(False)
        form.addRow(hint)
        return page

    def _export_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.format_combo = QComboBox()
        for fmt in EXPORT_FORMATS:
            self.format_combo.addItem(fmt, fmt)
        index = self.format_combo.findData(get("export/format", "pdf"))
        self.format_combo.setCurrentIndex(max(0, index))
        form.addRow("Default format:", self.format_combo)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setSuffix(" dpi")
        self.dpi_spin.setValue(int(get("export/dpi", 300)))
        form.addRow("Resolution:", self.dpi_spin)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10, 500)
        self.width_spin.setSuffix(" mm")
        self.width_spin.setValue(float(get("export/width_mm", 100.0)))
        form.addRow("Width:", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10, 500)
        self.height_spin.setSuffix(" mm")
        self.height_spin.setValue(float(get("export/height_mm", 75.0)))
        form.addRow("Height:", self.height_spin)
        return page

    def _general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.warn_on_discard = QCheckBox("Ask before discarding unsaved changes")
        self.warn_on_discard.setChecked(bool(get("general/warn_on_discard", True)))
        form.addRow(self.warn_on_discard)
        return page

    # -- applying -----------------------------------------------------------
    def _restore_defaults(self) -> None:
        """Put every preference back to its default and close the dialog."""
        reset()
        self._load_values()
        self.accept()

    def _load_values(self) -> None:
        """Fill the widgets from the stored preferences."""
        index = self.theme_combo.findData(theme.current_preset())
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        index = self.decimals_combo.findData(
            int(get("worksheet/new_column_decimals", -1))
        )
        self.decimals_combo.setCurrentIndex(max(0, index))
        self.wheel_zoom.setChecked(bool(get("canvas/wheel_zoom", True)))
        self.warn_on_discard.setChecked(bool(get("general/warn_on_discard", True)))
        index = self.format_combo.findData(get("export/format", "pdf"))
        self.format_combo.setCurrentIndex(max(0, index))
        self.dpi_spin.setValue(int(get("export/dpi", 300)))
        self.width_spin.setValue(float(get("export/width_mm", 100.0)))
        self.height_spin.setValue(float(get("export/height_mm", 75.0)))

    def accept(self) -> None:
        self._apply()
        super().accept()

    def _apply(self) -> None:
        """Write the preferences and let the application pick them up."""
        set_value("worksheet/new_column_decimals", self.decimals_combo.currentData())
        set_value("canvas/wheel_zoom", self.wheel_zoom.isChecked())
        set_value("general/warn_on_discard", self.warn_on_discard.isChecked())
        set_value("export/format", self.format_combo.currentData())
        set_value("export/dpi", self.dpi_spin.value())
        set_value("export/width_mm", self.width_spin.value())
        set_value("export/height_mm", self.height_spin.value())

        preset_id = self.theme_combo.currentData()
        parent = self.parent()
        apply_theme = getattr(parent, "_action_set_theme", None)
        if apply_theme is not None and preset_id != theme.current_preset():
            apply_theme(preset_id)
        else:
            theme.save_preset(preset_id)
        warn = getattr(parent, "confirm_on_close", None)
        if warn is not None:
            parent.confirm_on_close = self.warn_on_discard.isChecked()


__all__ = [
    "DEFAULTS",
    "EXPORT_FORMATS",
    "PreferencesDialog",
    "get",
    "new_column_decimals",
    "reset",
    "set_value",
]
