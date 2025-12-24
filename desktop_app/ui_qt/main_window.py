# ui_qt/main_window.py
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSizePolicy
)
from fastapi import background

from ui_qt.base import palette
from ui_qt.tracker import JobTrackerPage

# Your existing pages (keep these imports if the files exist)
from ui_qt.filevault import FileVaultPage
from ui_qt.whiteboard import WhiteboardPage
from ui_qt.notepad import NotepadPage
from ui_qt.coverletter import CoverLetterPage
from ui_qt.analytics import AnalyticsPage
from ui_qt.calendar import CalendarPage

APP_NAME = "CareerBuddy"


def _placeholder(title: str) -> QWidget:
    w = QFrame()
    w.setObjectName("panel")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(18, 16, 18, 18)
    lay.setSpacing(10)
    lab = QLabel(title)
    lab.setStyleSheet("color:white;font-size:18px;font-weight:900;")
    sub = QLabel("Coming soon.")
    sub.setStyleSheet(f"color:{palette['muted']};font-weight:700;")
    lay.addWidget(lab)
    lay.addWidget(sub)
    lay.addStretch(1)
    return w


class SidebarButton(QPushButton):
    def __init__(self, icon_text: str, text: str, key: str):
        super().__init__(f"{icon_text}  {text}")
        self.key = key
        self.icon_text = icon_text
        self.full_text = text
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("navBtn")
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_collapsed(self, collapsed: bool):
        if collapsed:
            self.setText(self.icon_text)
            self.setToolTip(self.full_text)
        else:
            self.setText(f"{self.icon_text}  {self.full_text}")
            self.setToolTip("")


class Sidebar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")

        self.setMinimumWidth(72)
        self.setMaximumWidth(250)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self._collapsed = False
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.setDuration(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("CareerBuddy 🃏")
        title.setObjectName("appTitle")
        head.addWidget(title)
        head.addStretch(1)

        self.btn_toggle = QPushButton("⫶")
        self.btn_toggle.setObjectName("collapseBtn")
        self.btn_toggle.setFixedSize(34, 34)
        self.btn_toggle.clicked.connect(self.toggle)
        head.addWidget(self.btn_toggle)
        lay.addLayout(head)

        self.btn_minimise = QPushButton("⬇ Minimise to Card")
        self.btn_minimise.setObjectName("ghostBtn")
        self.btn_minimise.setMinimumHeight(36)
        lay.addWidget(self.btn_minimise)

        self.buttons: Dict[str, SidebarButton] = {}
        nav_def = [
            ("📋", "Job Tracker", "job_deck"),
            ("📅", "Calendar", "calendar"),
            ("📊", "Analytics", "analytics"),
            ("✉️", "Cover Letter", "cover_letter"),
            ("📁", "File Vault", "file_vault"),
            ("🎨", "Whiteboard", "whiteboard"),
            ("📝", "Notepad", "notepad"),
            ("🤖", "AI Buddy", "ai_buddy"),
        ]
        for icon_text, label, key in nav_def:
            b = SidebarButton(icon_text, label, key)
            lay.addWidget(b)
            self.buttons[key] = b

        lay.addStretch(1)

        footer = QLabel("v6 • Qt Edition ✨")
        footer.setStyleSheet(f"color:{palette['muted']};font-weight:700;")
        lay.addWidget(footer)

    def toggle(self):
        self._collapsed = not self._collapsed

        start = self.maximumWidth()
        end = 72 if self._collapsed else 250

        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

        for b in self.buttons.values():
            b.set_collapsed(self._collapsed)

        self.btn_minimise.setText("⬇" if self._collapsed else "⬇ Minimise to Card")


class MainWindow(QMainWindow):
    def __init__(self, db, vault_dir: str):
        super().__init__()
        self.db = db

        self.setWindowTitle(APP_NAME)
        self.resize(1200, 780)

        root = QWidget()
        self.setCentralWidget(root)

        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.sidebar = Sidebar()
        main.addWidget(self.sidebar)

        content = QFrame()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 16)
        content_layout.setSpacing(10)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        main.addWidget(content, 1)

        # Pages
        self.page_job_deck = JobTrackerPage(self.db)
        self.page_calendar = CalendarPage(self.db)
        self.page_analytics = AnalyticsPage(self.db)
        self.page_cover_letter = CoverLetterPage()
        self.page_file_vault = FileVaultPage(self.db, vault_dir)
        self.page_whiteboard = WhiteboardPage()
        self.page_notepad = NotepadPage(self.db)
        self.page_ai = _placeholder("🤖 AI Buddy")

        self.pages: Dict[str, int] = {
            "job_deck": self.stack.addWidget(self.page_job_deck),
            "calendar": self.stack.addWidget(self.page_calendar),
            "analytics": self.stack.addWidget(self.page_analytics),
            "cover_letter": self.stack.addWidget(self.page_cover_letter),
            "file_vault": self.stack.addWidget(self.page_file_vault),
            "whiteboard": self.stack.addWidget(self.page_whiteboard),
            "notepad": self.stack.addWidget(self.page_notepad),
            "ai_buddy": self.stack.addWidget(self.page_ai),
        }

        for key, btn in self.sidebar.buttons.items():
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))

        self.sidebar.btn_minimise.clicked.connect(self.minimise_to_card)

        self.show_page("job_deck")

        self.setStyleSheet(f"""
            QMainWindow {{
                background: {palette["bg_dark"]};
            }}
            QFrame#content {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,0.04),
                    stop:1 rgba(0,0,0,0.14)
                );
            }}
            QFrame#sidebar {{
                background: {palette["bg_medium"]};
                border-right: 1px solid {palette["border_soft"]};
            }}
            QLabel#appTitle {{
                color: white;
                font-size: 18px;
                font-weight: 900;
            }}
            QPushButton#collapseBtn {{
                background: rgba(255,255,255,0.10);
                color: {palette["text"]};
                font-weight: 900;
                border-radius: 10px;
            }}
            QPushButton#collapseBtn:hover {{
                background: rgba(255,255,255,0.16);
            }}
            QPushButton#navBtn {{
                text-align: left;
                padding: 10px 12px;
                border-radius: 14px;
                background: rgba(255,255,255,0.06);
                color: {palette["text"]};
                font-weight: 850;
            }}
            QPushButton#navBtn:hover {{
                background: rgba(255,255,255,0.12);
            }}
            QPushButton#navBtn[active="true"] {{
                background: rgba(231,195,91,0.22);
                border: 1px solid rgba(231,195,91,0.35);
            }}
            QPushButton#ghostBtn {{
                background: rgba(255,255,255,0.10);
                color: {palette["text"]};
                font-weight: 850;
                padding: 10px 12px;
                border-radius: 14px;
            }}
            QPushButton#ghostBtn:hover {{
                background: rgba(255,255,255,0.16);
            }}
            QFrame#panel {{
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
            }}
        """)

    def show_page(self, key: str):
        for k, btn in self.sidebar.buttons.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        idx = self.pages.get(key)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()


    def minimise_to_card(self):
        self.hide()
