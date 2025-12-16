# ui_qt/app_qt.py
from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

from PySide6.QtCore import (
    Qt,
    QPoint,
    QSize,
    QEvent,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QHBoxLayout,
    QSizeGrip,
)

from services.db import CareerDB
from ui_qt.main_window import MainWindow

APP_NAME = "CareerBuddy"
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "card_state.json")


# ------------------------------
# Card state save/load
# ------------------------------
def save_card_state(x: int, y: int, w: int, h: int) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"x": x, "y": y, "w": w, "h": h}, f)
    except Exception:
        pass


def load_card_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "x": int(d.get("x", 80)),
                    "y": int(d.get("y", 80)),
                    "w": int(d.get("w", 180)),
                    "h": int(d.get("h", 260)),
                }
    except Exception:
        pass
    return {"x": 80, "y": 80, "w": 180, "h": 260}


# ------------------------------
# Floating Card Widget (mini mode)
# ------------------------------
class CardWidget(QMainWindow):
    """
    Small draggable/resizable widget.
    - Drag: click+move beyond threshold
    - Click: open full mode
    """

    def __init__(self, on_open_full):
        super().__init__()
        self.on_open_full = on_open_full

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._press_pos: Optional[QPoint] = None
        self._drag_start: Optional[QPoint] = None
        self._dragging = False

        state = load_card_state()
        self.resize(state["w"], state["h"])
        self.setMinimumSize(QSize(140, 200))

        outer = QFrame()
        outer.setObjectName("cardShell")

        lay = QVBoxLayout(outer)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        top = QHBoxLayout()
        lab = QLabel("🃏")
        lab.setStyleSheet("color: white; font-size: 18px; font-weight: 900;")
        top.addWidget(lab)
        top.addStretch(1)

        xbtn = QPushButton("×")
        xbtn.setObjectName("tinyBtn")
        xbtn.setFixedSize(28, 28)
        xbtn.clicked.connect(self.close)
        top.addWidget(xbtn)

        lay.addLayout(top)

        title = QLabel("CareerBuddy")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: 900;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        hint = QLabel("Click to open\nDrag to move")
        hint.setStyleSheet("color: rgba(255,255,255,0.70); font-weight: 700;")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

        lay.addStretch(1)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip = QSizeGrip(outer)
        grip.setObjectName("grip")
        grip_row.addWidget(grip)
        lay.addLayout(grip_row)

        self.setCentralWidget(outer)

        # Event filter for click vs drag
        outer.installEventFilter(self)

        # Start position
        self.move(state["x"], state["y"])

        # Small fade polish
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setEasingCurve(QEasingCurve.InOutCubic)
        self.setWindowOpacity(0.0)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)

        self.setStyleSheet("""
            QFrame#cardShell {
                background: rgba(0,0,0,0.62);
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.14);
            }
            QPushButton#tinyBtn {
                background: rgba(255,255,255,0.10);
                color: rgba(255,255,255,0.92);
                font-weight: 900;
                border-radius: 8px;
            }
            QPushButton#tinyBtn:hover {
                background: rgba(255,255,255,0.16);
            }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.start()

    def moveEvent(self, event):
        # persist position as you move
        st = load_card_state()
        save_card_state(self.x(), self.y(), st["w"], st["h"])
        super().moveEvent(event)

    def resizeEvent(self, event):
        # persist size as you resize
        st = load_card_state()
        save_card_state(st["x"], st["y"], self.width(), self.height())
        super().resizeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_start = self.pos()
            self._dragging = False
            return True

        if event.type() == QEvent.MouseMove and self._press_pos is not None:
            cur = event.globalPosition().toPoint()
            delta = cur - self._press_pos

            # threshold so a tiny move doesn't count as a drag
            if not self._dragging and (abs(delta.x()) > 6 or abs(delta.y()) > 6):
                self._dragging = True

            if self._dragging and self._drag_start is not None:
                self.move(self._drag_start + delta)
            return True

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if not self._dragging:
                self.on_open_full()
            self._press_pos = None
            self._drag_start = None
            self._dragging = False
            return True

        return super().eventFilter(obj, event)


# ------------------------------
# App Runner
# ------------------------------
def main():
    app = QApplication(sys.argv)

    # Existing DB (jobs/files/etc persist)
    db = CareerDB()

    # base folder is desktop_app/
    base = os.path.dirname(os.path.dirname(__file__))
    vault_dir = os.path.join(base, "career_buddy_files")

    win = MainWindow(db, vault_dir=vault_dir)

    # Floating card launcher
    def open_full():
        card.hide()
        win.show()
        win.raise_()
        win.activateWindow()

    card = CardWidget(open_full)

    # Sync: if main hidden -> show card, else hide card
    def sync_windows():
        if win.isVisible():
            if card.isVisible():
                card.hide()
        else:
            if not card.isVisible():
                card.show()

    timer = QTimer()
    timer.timeout.connect(sync_windows)
    timer.start(200)

    # Start in card mode
    card.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
