"""Lucide-style SVG icons for the UI, colourised for the active theme."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

from graphmatrix.ui import theme


_LUCIDE = {
    "database": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>',
    "folder": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
    "file-text": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5M10 9H8M16 13H8M16 17H8"/></svg>',
    "columns": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M12 3v18"/></svg>',
    "line-chart": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/></svg>',
}


def _icon_color(kind: str) -> str:
    dark = theme.is_dark() if hasattr(theme, "is_dark") else False
    palette = {
        "project": "#7aa2f7" if dark else "#3b5bdb",
        "workbook": "#e0af68" if dark else "#b8860b",
        "sheet": "#9ece6a" if dark else "#2f7d32",
        "column": "#bb9af7" if dark else "#6a4c93",
        "graph": "#f7768e" if dark else "#c2185b",
    }
    return palette.get(kind, "#9aa0a6" if dark else "#5f6368")


def lucide_icon(name: str, kind: str | None = None, size: int = 16) -> QIcon:
    """Build a QIcon from an embedded Lucide SVG, coloured for the theme."""
    template = _LUCIDE[name]
    color = _icon_color(kind) if kind else ("#9aa0a6" if theme.is_dark() else "#5f6368")
    svg = template.format(color=color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
