"""Application theming: named presets, each a Fusion palette plus a QSS layer.

A preset bundles three things: a **colour scheme** (dark or light), a **design
language** ("classic" or the flatter, rounder "modern"), and the palette tokens
that both the widgets and the plot canvas read from.

``apply_theme(app, preset=...)`` sets the style, palette, and stylesheet in one
call. Non-widget code (the pyqtgraph canvas, the graph view) uses
``current_preset()`` / ``is_dark()`` / ``canvas_colors()`` to pick matching
colours. The chosen preset can be persisted across runs with ``save_preset()`` /
``load_saved_preset()``.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette

SETTINGS_KEY = "appearance/preset"


@dataclass(frozen=True)
class ThemePreset:
    """A complete look: colour scheme + design language + palette tokens."""

    id: str
    label: str
    description: str
    dark: bool
    style: str  # "classic" | "modern"
    palette: dict[str, str]

    @property
    def modern(self) -> bool:
        return self.style == "modern"


# --- palette tokens ---------------------------------------------------------
# Keys are shared by every preset so the QSS template and the code can rely on
# them. ``canvas_*`` feeds the pyqtgraph backend.
_CLASSIC_DARK = {
    "window": "#1e1f22",
    "panel": "#26282d",
    "base": "#23252a",
    "alt": "#2c2f35",
    "border": "#3a3d42",
    "text": "#e8eaed",
    "muted": "#9aa0a6",
    "accent": "#4c8dff",
    "accent_text": "#ffffff",
    "hover": "#33373e",
    "disabled": "#5b6068",
    "canvas_bg": "#191a1d",
    "canvas_fg": "#d7dae0",
    "canvas_grid": "0.16",
    "danger": "#e5534b",
}

_CLASSIC_LIGHT = {
    "window": "#f4f5f7",
    "panel": "#e9ebef",
    "base": "#ffffff",
    "alt": "#f0f2f5",
    "border": "#c9cdd4",
    "text": "#1f2328",
    "muted": "#5f6570",
    "accent": "#2f6feb",
    "accent_text": "#ffffff",
    "hover": "#dfe3e9",
    "disabled": "#a6abb4",
    "canvas_bg": "#ffffff",
    "canvas_fg": "#202124",
    "canvas_grid": "0.25",
    "danger": "#c0392b",
}

# Modern: deeper surfaces, an indigo accent, and softer line work. The matching
# QSS layer (below) rounds corners and tightens spacing.
_MODERN_DARK = {
    "window": "#12141a",
    "panel": "#1a1d25",
    "base": "#171a21",
    "alt": "#20242e",
    "border": "#2c313d",
    "text": "#eef1f6",
    "muted": "#8b93a3",
    "accent": "#7c8cff",
    "accent_text": "#ffffff",
    "hover": "#262b37",
    "disabled": "#565d6c",
    "canvas_bg": "#0e1015",
    "canvas_fg": "#dde1ea",
    "canvas_grid": "0.14",
    "danger": "#f0616a",
}

_MODERN_LIGHT = {
    "window": "#f7f8fc",
    "panel": "#eef0f7",
    "base": "#ffffff",
    "alt": "#f2f4fa",
    "border": "#dcdfec",
    "text": "#1b1e2b",
    "muted": "#626a80",
    "accent": "#5b62e8",
    "accent_text": "#ffffff",
    "hover": "#e6e9f5",
    "disabled": "#a9afc2",
    "canvas_bg": "#ffffff",
    "canvas_fg": "#1b1e2b",
    "canvas_grid": "0.2",
    "danger": "#d64550",
}

PRESETS: dict[str, ThemePreset] = {
    "classic-dark": ThemePreset(
        "classic-dark", "Classic Dark", "The default dark colour scheme.", True, "classic", _CLASSIC_DARK
    ),
    "classic-light": ThemePreset(
        "classic-light", "Classic Light", "A bright, neutral colour scheme.", False, "classic", _CLASSIC_LIGHT
    ),
    "modern-dark": ThemePreset(
        "modern-dark", "Modern Dark", "Deeper surfaces, indigo accent, rounded and compact.", True, "modern", _MODERN_DARK
    ),
    "modern-light": ThemePreset(
        "modern-light", "Modern Light", "Airy surfaces, indigo accent, rounded and compact.", False, "modern", _MODERN_LIGHT
    ),
}

DEFAULT_PRESET = "classic-dark"

_current_preset = DEFAULT_PRESET


def preset(preset_id: str | None = None) -> ThemePreset:
    """Return a preset by id, falling back to the default for unknown ids."""
    if preset_id is None:
        preset_id = _current_preset
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def presets() -> list[ThemePreset]:
    """All presets, in display order."""
    return list(PRESETS.values())


def current_preset() -> str:
    return _current_preset


def set_preset(preset_id: str) -> str:
    """Record the active preset (no Qt objects touched). Returns the id used."""
    global _current_preset
    _current_preset = preset_id if preset_id in PRESETS else DEFAULT_PRESET
    return _current_preset


def is_dark() -> bool:
    return preset().dark


def is_modern() -> bool:
    return preset().modern


def colors(preset_id: str | None = None) -> dict[str, str]:
    return preset(preset_id).palette


def canvas_colors(preset_id: str | None = None) -> tuple[str, str, float]:
    """Return ``(background, foreground, grid_alpha)`` for the plot canvas."""
    c = colors(preset_id)
    return c["canvas_bg"], c["canvas_fg"], float(c["canvas_grid"])


# --- persistence ------------------------------------------------------------
def _settings() -> QSettings | None:
    """A QSettings bound to the app, or None when there is no named app.

    Guarding on the organization name keeps headless tests (which construct a
    bare ``QApplication``) from writing to a stray "Unknown Organization" file.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None or not app.organizationName():
        return None
    return QSettings()


def load_saved_preset() -> str:
    settings = _settings()
    if settings is None:
        return _current_preset
    value = settings.value(SETTINGS_KEY, DEFAULT_PRESET)
    return value if value in PRESETS else DEFAULT_PRESET


def save_preset(preset_id: str) -> None:
    settings = _settings()
    if settings is None:
        return
    settings.setValue(SETTINGS_KEY, preset_id)


_QSS = """
QMainWindow, QDialog { background: $window; }
QWidget { color: $text; }
QToolTip {
    background: $panel; color: $text; border: 1px solid $border;
    padding: 4px 7px; border-radius: 4px;
}

/* ---- menu bar / menus ---- */
QMenuBar { background: $panel; color: $text; border-bottom: 1px solid $border; }
QMenuBar::item { padding: 5px 11px; background: transparent; border-radius: 5px; }
QMenuBar::item:selected { background: $hover; }
QMenuBar::item:pressed { background: $accent; color: $accent_text; }
QMenu { background: $panel; color: $text; border: 1px solid $border; padding: 5px; }
QMenu::item { padding: 6px 28px 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: $accent; color: $accent_text; }
QMenu::item:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $border; margin: 5px 9px; }
QMenu::indicator { width: 14px; height: 14px; left: 6px; }

/* ---- toolbar ---- */
QToolBar { background: $panel; border: none; border-bottom: 1px solid $border; spacing: 3px; padding: 5px 7px; }
QToolBar::separator { background: $border; width: 1px; margin: 5px 6px; }
QToolButton { background: transparent; color: $text; border: 1px solid transparent; border-radius: 6px; padding: 5px 10px; }
QToolButton:hover { background: $hover; }
QToolButton:pressed, QToolButton:checked { background: $accent; color: $accent_text; }
QToolButton:disabled { color: $disabled; }

/* ---- status bar ---- */
QStatusBar { background: $panel; color: $muted; border-top: 1px solid $border; }
QStatusBar::item { border: none; }

/* ---- dock widgets ---- */
QDockWidget { color: $text; }
QDockWidget::title {
    background: $panel; padding: 7px 11px;
    border-bottom: 1px solid $border; font-weight: 600;
}
QDockWidget::close-button, QDockWidget::float-button { background: transparent; border: none; padding: 1px; }
QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: $hover; border-radius: 4px; }

/* ---- central tabs ---- */
QTabWidget::pane { border: 1px solid $border; background: $base; }
QTabBar::tab {
    background: $window; color: $muted; padding: 7px 15px;
    border: 1px solid transparent; border-bottom: 2px solid transparent;
    margin-right: 2px;
}
QTabBar::tab:selected { background: $base; color: $text; border-bottom: 2px solid $accent; }
QTabBar::tab:hover:!selected { color: $text; background: $hover; }

/* ---- group boxes ---- */
QGroupBox {
    border: 1px solid $border; border-radius: 8px;
    margin-top: 16px; padding: 10px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; top: 1px; padding: 0 5px;
    color: $muted; font-weight: 600;
}

/* ---- buttons ---- */
QPushButton {
    background: $alt; color: $text; border: 1px solid $border;
    border-radius: 6px; padding: 6px 15px;
}
QPushButton:hover { background: $hover; border-color: $accent; }
QPushButton:pressed { background: $accent; color: $accent_text; border-color: $accent; }
QPushButton:default { border-color: $accent; }
QPushButton:disabled { color: $disabled; background: $window; border-color: $border; }
QPushButton:checked { background: $accent; color: $accent_text; }

/* ---- text inputs and item views ---- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QListWidget, QTreeWidget, QTreeView, QTableView, QTableWidget {
    background: $base; color: $text; border: 1px solid $border;
    border-radius: 6px; selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border-color: $accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: $disabled; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; width: 0; height: 0; margin-right: 8px;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid $muted;
}
QComboBox::down-arrow:hover { border-top-color: $accent; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; width: 16px; background: transparent; border: none;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid $muted;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid $muted;
}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover { border-bottom-color: $accent; }
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover { border-top-color: $accent; }
QComboBox QAbstractItemView {
    background: $panel; color: $text; border: 1px solid $border;
    selection-background-color: $accent; selection-color: $accent_text; outline: 0;
}
QPlainTextEdit, QTextEdit { padding: 4px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 2px 8px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button { width: 14px; }

QHeaderView::section {
    background: $panel; color: $muted; padding: 6px 9px;
    border: none; border-right: 1px solid $border; border-bottom: 1px solid $border;
    font-weight: 600;
}
QTableView::item, QTreeView::item, QListView::item { padding: 3px 5px; }
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {
    background: $accent; color: $accent_text;
}
QTreeView::branch { background: transparent; }

/* ---- scrollbars ---- */
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- splitter ---- */
QSplitter::handle { background: $border; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QSplitter::handle:hover { background: $accent; }

/* ---- misc ---- */
QLabel { background: transparent; }
QCheckBox, QRadioButton { color: $text; spacing: 7px; }
QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; }
QProgressBar { border: 1px solid $border; border-radius: 6px; text-align: center; background: $base; }
QProgressBar::chunk { background: $accent; border-radius: 5px; }
"""

# Appended for the "modern" design language. Later rules win, so this reshapes
# the classic base into something rounder, flatter, and a touch more compact.
_MODERN_QSS = """
/* ---- modern design language ---- */
QToolBar { padding: 6px 8px; spacing: 4px; border-bottom: 1px solid $border; }
QToolButton { border-radius: 8px; padding: 6px 12px; }
QToolButton:hover { background: $hover; border-color: $border; }
QToolButton:pressed, QToolButton:checked { background: $accent; color: $accent_text; border-color: $accent; }

QMenuBar::item { border-radius: 7px; padding: 6px 12px; }
QMenu { border-radius: 10px; padding: 6px; }
QMenu::item { border-radius: 7px; padding: 7px 30px 7px 24px; }
QToolTip { border-radius: 7px; }

QTabWidget::pane { border-radius: 10px; top: -1px; }
QTabBar::tab { border-radius: 10px 10px 0 0; padding: 8px 17px; margin-right: 3px; }
QTabBar::tab:selected { border-bottom: 2px solid $accent; }

QGroupBox { border-radius: 11px; margin-top: 18px; padding: 12px 8px 8px 8px; }

QPushButton { border-radius: 9px; padding: 7px 17px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QListWidget, QTreeWidget, QTreeView, QTableView, QTableWidget { border-radius: 9px; }

QDockWidget::title { padding: 8px 12px; }
QHeaderView::section { padding: 7px 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { border-radius: 6px; }
QProgressBar, QProgressBar::chunk { border-radius: 8px; }
"""


def _stylesheet(p: ThemePreset) -> str:
    qss = _QSS + (_MODERN_QSS if p.modern else "")
    # Replace longer tokens first so "$accent_text" isn't clobbered by "$accent".
    for key in sorted(p.palette, key=len, reverse=True):
        qss = qss.replace(f"${key}", p.palette[key])
    return qss


def _palette(p: ThemePreset) -> QPalette:
    c = p.palette
    pal = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    pal.setColor(role.Window, QColor(c["window"]))
    pal.setColor(role.WindowText, QColor(c["text"]))
    pal.setColor(role.Base, QColor(c["base"]))
    pal.setColor(role.AlternateBase, QColor(c["alt"]))
    pal.setColor(role.Text, QColor(c["text"]))
    pal.setColor(role.Button, QColor(c["alt"]))
    pal.setColor(role.ButtonText, QColor(c["text"]))
    pal.setColor(role.BrightText, QColor(c["accent_text"]))
    pal.setColor(role.Highlight, QColor(c["accent"]))
    pal.setColor(role.HighlightedText, QColor(c["accent_text"]))
    pal.setColor(role.ToolTipBase, QColor(c["panel"]))
    pal.setColor(role.ToolTipText, QColor(c["text"]))
    pal.setColor(role.PlaceholderText, QColor(c["muted"]))
    pal.setColor(role.Link, QColor(c["accent"]))
    pal.setColor(role.Mid, QColor(c["border"]))
    pal.setColor(role.Shadow, QColor("#000000"))
    for disabled_role in (role.Text, role.WindowText, role.ButtonText):
        pal.setColor(group.Disabled, disabled_role, QColor(c["disabled"]))
    return pal


def apply_theme(app, preset: str | None = None) -> str:
    """Apply a preset's style, palette, and stylesheet to ``app``.

    Returns the resolved preset id (unknown ids fall back to the default).
    """
    resolved = set_preset(preset if preset is not None else _current_preset)
    active = PRESETS[resolved]
    app.setStyle("Fusion")
    app.setPalette(_palette(active))
    app.setStyleSheet(_stylesheet(active))
    return resolved


__all__ = [
    "ThemePreset",
    "PRESETS",
    "DEFAULT_PRESET",
    "SETTINGS_KEY",
    "apply_theme",
    "preset",
    "presets",
    "current_preset",
    "set_preset",
    "is_dark",
    "is_modern",
    "colors",
    "canvas_colors",
    "load_saved_preset",
    "save_preset",
]
