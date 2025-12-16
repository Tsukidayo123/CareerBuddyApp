# ui_qt/base.py
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton

palette = {
    "bg_dark": "#0f1115",
    "bg_medium": "#171a21",
    "panel": "#1e2230",
    "accent": "#d8b45c",        # warm “gold”
    "accent2": "#7c4dff",       # purple highlight
    "text": "#eaeaea",
    "muted": "#b8b8b8",
    "danger": "#e74c3c",
    "success": "#2ecc71",
    "warning": "#f1c40f",
}


def style_app(app: QApplication):
    app.setFont(QFont("Segoe UI", 10))

    app.setStyleSheet(f"""
    QMainWindow {{
        background: {palette["bg_dark"]};
        color: {palette["text"]};
    }}

    #Sidebar {{
        background: {palette["bg_medium"]};
        border-radius: 18px;
    }}

    #SidebarTitle {{
        font-size: 18px;
        font-weight: 700;
        padding: 6px;
    }}

    #MinBtn {{
        background: {palette["panel"]};
        padding: 10px 12px;
        border-radius: 12px;
        text-align: left;
    }}
    #MinBtn:hover {{
        background: {palette["accent2"]};
    }}

    QPushButton {{
        background: transparent;
        padding: 10px 12px;
        border-radius: 12px;
        text-align: left;
        color: {palette["text"]};
    }}
    QPushButton:hover {{
        background: {palette["panel"]};
    }}

    #Placeholder {{
        color: {palette["muted"]};
        font-size: 16px;
    }}

    /* Card widget hover glow + idle pulse */
    QLabel#CardLabel[glow="true"] {{
        background: {palette["panel"]};
        border-radius: 14px;
    }}
    QLabel#CardLabel[pulse="true"] {{
        background: {palette["accent2"]};
        border-radius: 14px;
    }}
    """)


def make_sidebar_button(text: str, on_click) -> QPushButton:
    b = QPushButton(text)
    b.clicked.connect(on_click)
    return b
