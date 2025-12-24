# ui_qt/app_qt.py
from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QSize, QEvent, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizeGrip
)

from services.db import CareerDB
from ui_qt.base import palette
from ui_qt.main_window import MainWindow

APP_NAME = "CareerBuddy"
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "card_state.json")


def _load_card_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_card_state(x: int, y: int, w: int, h: int) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"x": x, "y": y, "w": w, "h": h}, f)
    except Exception:
        pass


class CardWidget(QMainWindow):
    """
    Floating mini-card launcher:
    - Drag with left mouse (threshold so you don’t accidentally open)
    - Click to open full app
    - Resizable via QSizeGrip
    """

    def __init__(self, on_open_full):
        super().__init__()
        self.on_open_full = on_open_full

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._press_pos: Optional[QPoint] = None
        self._start_pos: Optional[QPoint] = None
        self._dragging = False
        self._press_time = 0.0

        st = _load_card_state()
        w = int(st.get("w", 180))
        h = int(st.get("h", 260))
        self.resize(w, h)
        self.setMinimumSize(QSize(150, 210))

        if "x" in st and "y" in st:
            self.move(int(st["x"]), int(st["y"]))

        shell = QFrame()
        shell.setObjectName("cardShell")
        lay = QVBoxLayout(shell)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top = QHBoxLayout()
        badge = QLabel("🃏")
        badge.setStyleSheet("color:white;font-size:18px;font-weight:900;")
        top.addWidget(badge)
        top.addStretch(1)

        close_btn = QPushButton("×")
        close_btn.setObjectName("tinyBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        lay.addLayout(top)

        title = QLabel("CareerBuddy")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:white;font-size:16px;font-weight:900;")
        lay.addWidget(title)

        hint = QLabel("Click to open\nDrag to move")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color:{palette['muted']};font-weight:800;")
        lay.addWidget(hint)

        lay.addStretch(1)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip = QSizeGrip(shell)
        grip.setObjectName("grip")
        grip_row.addWidget(grip)
        lay.addLayout(grip_row)

        self.setCentralWidget(shell)
        shell.installEventFilter(self)

        self.setStyleSheet(f"""
            QFrame#cardShell {{
                background: rgba(0,0,0,0.62);
                border: 1px solid {palette["border"]};
                border-radius: 18px;
            }}
            QPushButton#tinyBtn {{
                background: rgba(255,255,255,0.10);
                color: {palette["text"]};
                font-weight: 900;
                border-radius: 8px;
            }}
            QPushButton#tinyBtn:hover {{
                background: rgba(255,255,255,0.16);
            }}
        """)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._start_pos = self.pos()
            self._dragging = False
            self._press_time = time.time()
            return True

        if event.type() == QEvent.MouseMove and self._press_pos is not None and self._start_pos is not None:
            cur = event.globalPosition().toPoint()
            delta = cur - self._press_pos

            # Threshold prevents accidental open
            if not self._dragging and (abs(delta.x()) > 7 or abs(delta.y()) > 7):
                self._dragging = True

            if self._dragging:
                self.move(self._start_pos + delta)
                _save_card_state(self.x(), self.y(), self.width(), self.height())
            return True

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if not self._dragging:
                self.on_open_full()
            self._press_pos = None
            self._start_pos = None
            self._dragging = False
            _save_card_state(self.x(), self.y(), self.width(), self.height())
            return True

        return super().eventFilter(obj, event)


def main():
    app = QApplication(sys.argv)

    # Persisted DB
    db = CareerDB()

    # Vault directory (same idea as before)
    base = os.path.dirname(os.path.dirname(__file__))  # desktop_app/
    vault_dir = os.path.join(base, "career_buddy_files")
    os.makedirs(vault_dir, exist_ok=True)

    win = MainWindow(db, vault_dir=vault_dir)

    card: Optional[CardWidget] = None

    def open_full():
        nonlocal card
        win.show()
        win.raise_()
        win.activateWindow()
        if card and card.isVisible():
            card.hide()

    card = CardWidget(open_full)

    # Sync: if main hides (minimise to card), show the card
    def sync():
        if win.isVisible():
            if card.isVisible():
                card.hide()
        else:
            if not card.isVisible():
                card.show()

    t = QTimer()
    t.timeout.connect(sync)
    t.start(160)

    # Start in card mode
    card.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
