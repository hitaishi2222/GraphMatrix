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

from PySide6.QtGui import QColor, QPalette

from graphmatrix.ui.settings import app_settings as _settings

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

# shadcn/ui: near-monochrome surfaces, hairline borders, one near-black (light)
# or near-white (dark) *primary*, and 10px radii. Token mapping: window =
# background, base = card, alt = secondary, accent = primary, accent_text =
# primary-foreground, hover = the muted surface shadcn uses for hover/selection.
# Keeping the primary neutral is the point: shadcn has no coloured accent.
_SHADCN_LIGHT = {
    "window": "#fafafa",
    "panel": "#ffffff",
    "base": "#ffffff",
    "alt": "#f5f5f5",
    "border": "#e5e5e5",
    "text": "#0a0a0a",
    "muted": "#737373",
    "accent": "#171717",
    "accent_text": "#fafafa",
    "hover": "#f5f5f5",
    "disabled": "#a1a1a1",
    "canvas_bg": "#ffffff",
    "canvas_fg": "#0a0a0a",
    "canvas_grid": "0.10",
    "danger": "#e7000b",
}

_SHADCN_DARK = {
    "window": "#0a0a0a",
    "panel": "#171717",
    "base": "#0a0a0a",
    "alt": "#262626",
    "border": "#262626",
    "text": "#fafafa",
    "muted": "#a1a1a1",
    "accent": "#fafafa",
    "accent_text": "#171717",
    "hover": "#262626",
    "disabled": "#525252",
    "canvas_bg": "#0a0a0a",
    "canvas_fg": "#fafafa",
    "canvas_grid": "0.10",
    "danger": "#ff6467",
}

PRESETS: dict[str, ThemePreset] = {
    "classic-dark": ThemePreset(
        "classic-dark",
        "Classic Dark",
        "The default dark colour scheme.",
        True,
        "classic",
        _CLASSIC_DARK,
    ),
    "classic-light": ThemePreset(
        "classic-light",
        "Classic Light",
        "A bright, neutral colour scheme.",
        False,
        "classic",
        _CLASSIC_LIGHT,
    ),
    "modern-dark": ThemePreset(
        "modern-dark",
        "Modern Dark",
        "Deeper surfaces, indigo accent, rounded and compact.",
        True,
        "modern",
        _MODERN_DARK,
    ),
    "modern-light": ThemePreset(
        "modern-light",
        "Modern Light",
        "Airy surfaces, indigo accent, rounded and compact.",
        False,
        "modern",
        _MODERN_LIGHT,
    ),
    "shadcn-dark": ThemePreset(
        "shadcn-dark",
        "shadcn Dark",
        "Neutral surfaces, hairline borders, near-white primary.",
        True,
        "shadcn",
        _SHADCN_DARK,
    ),
    "shadcn-light": ThemePreset(
        "shadcn-light",
        "shadcn Light",
        "Neutral surfaces, hairline borders, near-black primary.",
        False,
        "shadcn",
        _SHADCN_LIGHT,
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
    """Return ``(background, foreground, grid_alpha)`` for the plot canvas.

    The values come from :mod:`graphmatrix.core.plot_themes` so the canvas and
    the exporter cannot drift apart.
    """
    from graphmatrix.core.plot_themes import APP_CANVAS_THEMES, DEFAULT_APP_THEME

    key = preset_id or _current_preset
    return APP_CANVAS_THEMES.get(key, APP_CANVAS_THEMES[DEFAULT_APP_THEME])


# --- persistence ------------------------------------------------------------
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
    # Flush now: the choice must survive a kill, not only a clean quit.
    settings.sync()


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

/* ---- worksheet header “add column” button ---- */
QPushButton#headerAddButton {
    background: $alt; color: $text; border: 1px solid $border;
    border-radius: 4px; padding: 0; font-weight: 600;
}
QPushButton#headerAddButton:hover { background: $accent; color: $accent_text; border-color: $accent; }
QPushButton#headerAddButton:pressed { background: $accent; color: $accent_text; border-color: $accent; }

/* ---- recent projects (welcome page) ---- */
QPushButton#recentProject {
    background: transparent; border: 1px solid transparent; color: $text;
    text-align: left; padding: 6px 9px; border-radius: 6px; font-weight: 400;
}
QPushButton#recentProject:hover { background: $hover; border-color: $border; }

/* ---- status bar information ---- */
QLabel#statusInfo { color: $muted; padding-right: 8px; }

/* ---- key chips (welcome page) ---- */
QLabel#keyChip {
    background: $alt; color: $text; border: 1px solid $border;
    border-radius: 5px; padding: 2px 9px;
    font-family: monospace; font-weight: 600;
}

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
QPushButton:focus { border-color: $accent; }

/* The readout switch is a switch, not a call to action: it only lights up
   while it is on, and it never spans the whole panel. */
QToolButton#readoutToggle {
    background: transparent; border: 1px solid $border; border-radius: 6px;
    padding: 4px 12px; color: $muted;
}
QToolButton#readoutToggle:hover { background: $hover; color: $text; }
QToolButton#readoutToggle:checked {
    background: $accent; color: $accent_text; border-color: $accent;
}

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


# Appended for the "shadcn" design language: flat surfaces, a hairline border,
# muted hover/selection surfaces, and 10px radii. Only primary actions (default
# buttons, checked toggles) and the tab underline use the near-black/near-white
# accent fill, which is how shadcn separates primary from everything else.
_SHADCN_QSS = """
/* ---- shadcn design language ---- */
QToolBar { background: $window; border-bottom: 1px solid $border; padding: 6px 8px; spacing: 2px; }
QToolButton { border-radius: 8px; padding: 6px 10px; }
QToolButton:hover { background: $hover; border-color: transparent; }
QToolButton:pressed, QToolButton:checked {
    background: $hover; color: $text; border-color: $border;
}

QMenuBar { background: $window; border-bottom: 1px solid $border; }
QMenuBar::item { border-radius: 8px; padding: 6px 12px; }
QMenuBar::item:pressed { background: $accent; color: $accent_text; }
QMenu { border-radius: 12px; padding: 4px; }
QMenu::item { border-radius: 6px; padding: 6px 26px 6px 20px; }
QMenu::item:selected { background: $hover; color: $text; }
QMenu::separator { margin: 4px 6px; }
QToolTip { border-radius: 8px; padding: 5px 8px; }

QDockWidget::title { background: $window; padding: 8px 12px; border-bottom: 1px solid $border; }

QTabWidget::pane { border: none; border-top: 1px solid $border; background: $base; }
QTabBar::tab {
    background: transparent; color: $muted; border: none; border-radius: 0;
    border-bottom: 2px solid transparent; padding: 8px 14px; margin-right: 4px;
}
QTabBar::tab:hover:!selected { background: $hover; color: $text; border-radius: 8px 8px 0 0; }
QTabBar::tab:selected { background: transparent; color: $text; border-bottom: 2px solid $accent; }

QGroupBox { border-radius: 12px; margin-top: 18px; padding: 12px 10px 8px 10px; }

/* Outline buttons by default; only a dialog's default button is filled. */
QPushButton { background: transparent; border-radius: 9px; padding: 7px 16px; }
QPushButton:hover { background: $hover; border-color: $border; }
QPushButton:default { background: $accent; color: $accent_text; border-color: $accent; }
QPushButton:default:disabled { background: transparent; color: $disabled; border-color: $border; }
QPushButton:checked { background: $accent; color: $accent_text; border-color: $accent; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QListWidget, QTreeWidget, QTreeView, QTableView, QTableWidget {
    background: $window; border-radius: 9px;
    selection-background-color: $hover; selection-color: $text;
}
QHeaderView::section {
    background: transparent; color: $muted; padding: 8px 10px;
    border: none; border-bottom: 1px solid $border;
}
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {
    background: $hover; color: $text;
}

QStatusBar { background: $window; border-top: 1px solid $border; }

QScrollBar:vertical { width: 8px; margin: 2px; }
QScrollBar:horizontal { height: 8px; margin: 2px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: $border; border-radius: 4px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: $muted; }
QProgressBar, QProgressBar::chunk { border-radius: 999px; }
QSplitter::handle:hover { background: $border; }
"""

#: Design-language layers appended to the classic base, keyed by ``style``.
_STYLE_LAYERS = {"modern": _MODERN_QSS, "shadcn": _SHADCN_QSS}


def _stylesheet(p: ThemePreset) -> str:
    qss = _QSS + _STYLE_LAYERS.get(p.style, "")
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
    # shadcn keeps its primary (near-black/near-white) apart from its selection
    # surface, which is the muted token. QPalette.Highlight *is* a selection
    # surface (tree indents, input selection), so it must follow `hover` there.
    selection, selection_text = (
        (c["hover"], c["text"])
        if p.style == "shadcn"
        else (c["accent"], c["accent_text"])
    )
    pal.setColor(role.Highlight, QColor(selection))
    pal.setColor(role.HighlightedText, QColor(selection_text))
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
    "DEFAULT_PRESET",
    "PRESETS",
    "SETTINGS_KEY",
    "ThemePreset",
    "apply_theme",
    "canvas_colors",
    "colors",
    "current_preset",
    "is_dark",
    "is_modern",
    "load_saved_preset",
    "preset",
    "presets",
    "save_preset",
    "set_preset",
]
