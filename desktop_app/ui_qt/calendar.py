# ui_qt/calendar.py
from __future__ import annotations
from ui_qt.analytics import log_activity

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QCalendarWidget, QListWidget, QListWidgetItem, QMessageBox,
    QDialog, QLineEdit, QTextEdit, QComboBox
)

from ui_qt.base import palette


@dataclass
class Event:
    id: int
    title: str
    description: str
    date: str
    time: str
    category: str


CATEGORIES = ["Interview", "Call", "Assessment", "Deadline", "Other"]


class EventDialog(QDialog):
    def __init__(self, parent: QWidget, event: Optional[Event] = None, prefill_date: str = ""):
        super().__init__(parent)
        self.event_data = event
        self._prefill_date = prefill_date

        self.setModal(True)
        self.setFixedSize(520, 520)
        self.setWindowTitle("Add Event" if event is None else "Edit Event")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        title = QLabel("Add Event" if event is None else "Edit Event")
        title.setStyleSheet("font-size:18px;font-weight:900;color:white;")
        root.addWidget(title)

        self.ent_title = QLineEdit()
        self.ent_title.setPlaceholderText("Title (e.g., Amazon interview)")
        self.ent_time = QLineEdit()
        self.ent_time.setPlaceholderText("Time (e.g., 14:00) optional")
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(CATEGORIES)

        self.ent_link = QLineEdit()
        self.ent_link.setPlaceholderText("Link (optional)")

        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Details / agenda / notes...")

        root.addWidget(self.ent_title)
        row = QHBoxLayout()
        row.addWidget(self.ent_time, 1)
        row.addWidget(self.cmb_cat, 1)
        root.addLayout(row)
        root.addWidget(self.ent_link)
        root.addWidget(self.txt_desc, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("accentBtn")
        self.btn_cancel.setObjectName("ghostBtn")
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        root.addLayout(btns)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.accept)

        if event:
            self.ent_title.setText(event.title)
            self.ent_time.setText(event.time or "")
            self.cmb_cat.setCurrentText(event.category or "Other")
            link, desc = self._split_link(event.description or "")
            self.ent_link.setText(link)
            self.txt_desc.setPlainText(desc)

        self.setStyleSheet(f"""
            QDialog {{
                background: {palette["bg_dark"]};
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px;
                padding: 10px;
                color: {palette["text"]};
                font-weight: 650;
            }}
            QPushButton#accentBtn {{
                background: {palette["accent"]};
                color: #111;
                font-weight: 900;
                padding: 10px 14px;
                border-radius: 12px;
            }}
            QPushButton#ghostBtn {{
                background: rgba(255,255,255,0.10);
                color: {palette["text"]};
                font-weight: 850;
                padding: 10px 12px;
                border-radius: 12px;
            }}
        """)

    def _split_link(self, text: str):
        if "Link:" in text:
            a, b = text.split("Link:", 1)
            return b.strip(), a.strip()
        return "", text.strip()

    def values(self) -> tuple[str, str, str, str]:
        title = self.ent_title.text().strip()
        time = self.ent_time.text().strip()
        cat = self.cmb_cat.currentText()
        link = self.ent_link.text().strip()
        desc = self.txt_desc.toPlainText().strip()
        if link:
            desc = f"{desc}\n\nLink: {link}".strip()
        return title, time, cat, desc


class CalendarPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.selected_date = datetime.now().strftime("%Y-%m-%d")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Left: Calendar
        left = QFrame(); left.setObjectName("panel")
        ll = QVBoxLayout(left); ll.setContentsMargins(14, 12, 14, 12); ll.setSpacing(10)

        title = QLabel("📅 Calendar")
        title.setStyleSheet("font-size:20px;font-weight:900;color:white;")
        ll.addWidget(title)

        self.cal = QCalendarWidget()
        self.cal.setGridVisible(True)
        self.cal.clicked.connect(self._on_date_clicked)
        self.cal.activated.connect(self._on_date_activated)  # double click / enter
        self.cal.activated.connect(
            lambda d: (self._on_date_clicked(d), self._add_event())
         )
        
        self.cal.setObjectName("cal")
        ll.addWidget(self.cal, 1)

        # Month nav (scroll-like)
        nav = QHBoxLayout()
        btn_prev = QPushButton("◀")
        btn_next = QPushButton("▶")
        btn_prev.setObjectName("ghostBtn")
        btn_next.setObjectName("ghostBtn")
        btn_today = QPushButton("Today")
        btn_today.setObjectName("ghostBtn")
        nav.addWidget(btn_prev)
        nav.addWidget(btn_today)
        nav.addWidget(btn_next)
        nav.addStretch(1)
        ll.addLayout(nav)

        btn_prev.clicked.connect(lambda: self.cal.showPreviousMonth())
        btn_next.clicked.connect(lambda: self.cal.showNextMonth())
        btn_today.clicked.connect(self._go_today)

        root.addWidget(left, 2)

        # Right: Events list
        right = QFrame(); right.setObjectName("panel")
        rl = QVBoxLayout(right); rl.setContentsMargins(14, 12, 14, 12); rl.setSpacing(10)

        self.lbl_day = QLabel("Events")
        self.lbl_day.setStyleSheet("font-weight:900;color:white;")
        rl.addWidget(self.lbl_day)

        self.list = QListWidget()
        self.list.setObjectName("evList")
        rl.addWidget(self.list, 1)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Delete")
        self.btn_add.setObjectName("accentBtn")
        self.btn_edit.setObjectName("ghostBtn")
        self.btn_del.setObjectName("ghostBtn")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        rl.addLayout(btns)

        self.btn_add.clicked.connect(self._add_event)
        self.btn_edit.clicked.connect(self._edit_event)
        self.btn_del.clicked.connect(self._delete_event)

        root.addWidget(right, 3)

        self.setStyleSheet(f"""
            QFrame#panel {{
                background: {palette["panel"]};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }}
            QCalendarWidget#cal QWidget {{
                color: {palette["text"]};
                font-weight: 700;
            }}
            QListWidget#evList {{
                background: rgba(0,0,0,0.12);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                color: {palette["text"]};
            }}
            QPushButton#accentBtn {{
                background: {palette["accent"]};
                color: #111;
                font-weight: 900;
                padding: 10px 14px;
                border-radius: 12px;
            }}
            QPushButton#ghostBtn {{
                background: rgba(255,255,255,0.10);
                color: {palette["text"]};
                font-weight: 850;
                padding: 10px 12px;
                border-radius: 12px;
            }}
            QPushButton#ghostBtn:hover {{
                background: rgba(255,255,255,0.16);
            }}
        """)

        self._refresh_list()

    def _go_today(self):
        d = QDate.currentDate()
        self.cal.setSelectedDate(d)
        self._on_date_clicked(d)

    def _on_date_clicked(self, date: QDate):
        self.selected_date = date.toString("yyyy-MM-dd")
        pretty = date.toString("ddd dd MMM yyyy")
        self.lbl_day.setText(f"Events — {pretty}")
        self._refresh_list()

    def _fetch_for_selected(self) -> List[Event]:
        rows = self.db.list_reminders_for_date(self.selected_date)
        events: list[Event] = []
        for r in rows:
            rid, title, desc, date, time, cat = r
            events.append(Event(rid, title, desc or "", date, time or "", cat or "Other"))
        events.sort(key=lambda e: e.time)
        return events


    def _refresh_list(self):
        self.list.clear()
        events = self._fetch_for_selected()
        if not events:
            it = QListWidgetItem("No events for this day.")
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
            return

        for ev in events:
            label = f"{ev.time + '  ' if ev.time else ''}{ev.title}  •  {ev.category}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ev)
            self.list.addItem(item)

    def _add_event(self):
        dlg = EventDialog(self, None)
        if dlg.exec() != QDialog.Accepted:
            return

        title, time, cat, desc = dlg.values()
        if not title:
            QMessageBox.warning(self, "Missing", "Please enter a title.")
            return

        # log globally
        self.db.add_reminder(title, desc, self.selected_date, time, cat)
        pretty = QDate.fromString(self.selected_date, "yyyy-MM-dd").toString("dd MMM")
        log_activity(f"Added event → {title} ({cat}) on {pretty}")

        self._refresh_list()

    def _get_selected_event(self) -> Optional[Event]:
        item = self.list.currentItem()
        if not item:
            return None
        ev = item.data(Qt.UserRole)
        return ev if isinstance(ev, Event) else None

    def _edit_event(self):
        ev = self._get_selected_event()
        if not ev:
            return

        dlg = EventDialog(self, ev)
        if dlg.exec() != QDialog.Accepted:
            return

        title, time, cat, desc = dlg.values()
        if not title:
            QMessageBox.warning(self, "Missing", "Please enter a title.")
            return

        # use CareerDB instead of raw sqlite
        self.db.update_reminder(
            ev.id,
            title,
            desc,
            self.selected_date,
            time,
            cat,
        )

        log_activity(f"Edited event → {title} ({cat})")
        self._refresh_list()

    def _on_date_activated(self, date: QDate): # Activated fires on double click (and Enter)
        self._on_date_clicked(date)  # keep selection consistent
        self._add_event()            # open add dialog for that selected date


    def _delete_event(self):
        ev = self._get_selected_event()
        if not ev:
            return

        if QMessageBox.question(self, "Delete", f"Delete '{ev.title}'?") != QMessageBox.Yes:
            return

        self.db.delete_reminder(ev.id)
        log_activity(f"Deleted event → {ev.title} ({ev.category})")
        self._refresh_list()
