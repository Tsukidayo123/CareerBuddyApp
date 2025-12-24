# ui_qt/calendar.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

import sqlite3

from PySide6.QtCore import Qt, QDate, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QCalendarWidget, QListWidget, QListWidgetItem, QMessageBox,
    QDialog, QLineEdit, QTextEdit, QComboBox, QTabWidget
)

from services.db import DB_FILE
from ui_qt.base import palette
from ui_qt.analytics import log_activity


@dataclass
class Event:
    id: int
    title: str
    description: str
    date: str
    time: str
    category: str


CATEGORIES = ["Interview", "Call", "Assessment", "Deadline", "Other"]

# Suit + color mapping (card themed)
CAT_SUIT = {
    "Interview": "♥",
    "Call": "♦",
    "Assessment": "♣",
    "Deadline": "♠",
    "Other": "🃏",
}
CAT_COLOR = {
    "Interview": "#E74C3C",   # red
    "Call": "#E7C35B",        # gold
    "Assessment": "#49C6B6",  # teal
    "Deadline": "#111111",    # black
    "Other": palette.get("muted", "#9FB6AE"),
}


class EventDialog(QDialog):
    """
    IMPORTANT: don't store `self.event = ...` because QDialog already has event().
    Use self._event_data instead.
    """
    def __init__(self, parent: QWidget, event: Optional[Event] = None):
        super().__init__(parent)
        self._event_data = event

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
            QPushButton#ghostBtn:hover {{
                background: rgba(255,255,255,0.16);
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


class PipsCalendar(QCalendarWidget):
    """
    Month grid with suit pips on days that contain events (up to 3).
    Also provides hover tooltip with quick summary.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events_by_date: Dict[str, List[str]] = {}  # "YYYY-MM-DD" -> [category, ...]
        self.setMouseTracking(True)

        # Make cells feel less "default Qt"
        self.setGridVisible(True)

    def set_events_map(self, events_by_date: Dict[str, List[str]]):
        self._events_by_date = events_by_date
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, date: QDate):
        super().paintCell(painter, rect, date)

        key = date.toString("yyyy-MM-dd")
        cats = self._events_by_date.get(key, [])
        if not cats:
            return

        # draw up to 3 suit pips bottom-right
        max_pips = 3
        show = cats[:max_pips]

        painter.save()

        # small font for pips
        f = QFont(self.font())
        f.setPointSize(max(7, f.pointSize() - 2))
        f.setBold(True)
        painter.setFont(f)

        # layout pips: right aligned, slight padding
        pad = 4
        x = rect.right() - pad
        y = rect.bottom() - pad

        # each pip ~10px wide
        step = 12

        for i, cat in enumerate(reversed(show)):
            suit = CAT_SUIT.get(cat, "🃏")
            col = CAT_COLOR.get(cat, palette.get("muted", "#9FB6AE"))
            painter.setPen(QPen(QColor(col)))
            painter.drawText(x - (i * step) - 10, y - 2, suit)

        painter.restore()

    def mouseMoveEvent(self, event):
        # Hover tooltip: try to infer date under cursor.
        d = self._date_from_pos(event.position().toPoint())
        if d.isValid():
            key = d.toString("yyyy-MM-dd")
            cats = self._events_by_date.get(key, [])
            if cats:
                # tooltip: "3 events: Interview, Call, Deadline"
                uniq = []
                for c in cats:
                    if c not in uniq:
                        uniq.append(c)
                msg = f"{len(cats)} event{'s' if len(cats) != 1 else ''}: " + ", ".join(uniq[:4])
                self.setToolTip(msg)
            else:
                self.setToolTip("")
        else:
            self.setToolTip("")
        super().mouseMoveEvent(event)

    def _date_from_pos(self, pos: QPoint) -> QDate:
        """
        Best-effort mapping from mouse pos to date without relying on private Qt APIs.
        Works well enough for tooltip behaviour.
        """
        # QCalendarWidget contains an internal table; map position into it.
        table = self.findChild(type(self).findChild)  # dummy line to keep linters calm

        # More reliable: the viewport is the biggest child table-like widget.
        # We'll search for the first child that has `indexAt`.
        table_candidate = None
        for ch in self.findChildren(QWidget):
            if hasattr(ch, "indexAt") and hasattr(ch, "model"):
                table_candidate = ch
                break

        if table_candidate is None:
            return QDate()  # invalid

        # Convert to table viewport coordinates
        local = table_candidate.mapFrom(self, pos)
        if not hasattr(table_candidate, "indexAt"):
            return QDate()

        idx = table_candidate.indexAt(local)  # type: ignore[attr-defined]
        if not idx.isValid():
            return QDate()

        day = idx.data()
        if not isinstance(day, int):
            try:
                day = int(str(day))
            except Exception:
                return QDate()

        year = self.yearShown()
        month = self.monthShown()

        # heuristic: determine if day belongs to prev/next month
        # (top row with large day numbers = previous month)
        row = idx.row()
        if row == 0 and day > 20:
            # previous month
            m = month - 1
            y = year
            if m == 0:
                m = 12
                y -= 1
            return QDate(y, m, day)

        if row >= 4 and day < 15:
            # next month
            m = month + 1
            y = year
            if m == 13:
                m = 1
                y += 1
            return QDate(y, m, day)

        return QDate(year, month, day)


class CalendarPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.selected_date = datetime.now().strftime("%Y-%m-%d")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Left: Calendar
        left = QFrame()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 12, 14, 12)
        ll.setSpacing(10)

        title = QLabel("📅 Calendar")
        title.setStyleSheet("font-size:20px;font-weight:900;color:white;")
        ll.addWidget(title)

        self.cal = PipsCalendar()
        self.cal.setObjectName("cal")
        self.cal.clicked.connect(self._on_date_clicked)
        self.cal.activated.connect(self._on_date_activated)  # double click = add
        self.cal.currentPageChanged.connect(self._on_month_changed)
        ll.addWidget(self.cal, 1)

        # Month nav
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

        # Right: Day / Week tabs
        right = QFrame()
        right.setObjectName("panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 12, 14, 12)
        rl.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("tabs")

        # --- Day tab ---
        day_tab = QWidget()
        day_lay = QVBoxLayout(day_tab)
        day_lay.setContentsMargins(0, 0, 0, 0)
        day_lay.setSpacing(10)

        self.lbl_day = QLabel("Events")
        self.lbl_day.setStyleSheet("font-weight:900;color:white;")
        day_lay.addWidget(self.lbl_day)

        self.list_day = QListWidget()
        self.list_day.setObjectName("evList")
        day_lay.addWidget(self.list_day, 1)

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
        day_lay.addLayout(btns)

        self.btn_add.clicked.connect(self._add_event)
        self.btn_edit.clicked.connect(self._edit_event)
        self.btn_del.clicked.connect(self._delete_event)

        # --- Week tab ---
        week_tab = QWidget()
        week_lay = QVBoxLayout(week_tab)
        week_lay.setContentsMargins(0, 0, 0, 0)
        week_lay.setSpacing(10)

        self.lbl_week = QLabel("Week Agenda")
        self.lbl_week.setStyleSheet("font-weight:900;color:white;")
        week_lay.addWidget(self.lbl_week)

        self.list_week = QListWidget()
        self.list_week.setObjectName("evList")
        week_lay.addWidget(self.list_week, 1)

        self.tabs.addTab(day_tab, "Day")
        self.tabs.addTab(week_tab, "Week")

        rl.addWidget(self.tabs, 1)
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
            QTabWidget#tabs::pane {{
                border: 0px;
            }}
            QTabBar::tab {{
                background: rgba(255,255,255,0.06);
                color: {palette["text"]};
                padding: 8px 12px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                margin-right: 6px;
                font-weight: 800;
            }}
            QTabBar::tab:selected {{
                background: rgba(231,195,91,0.18);
                border: 1px solid rgba(231,195,91,0.30);
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

        # initialize pips + lists
        self._refresh_pips_for_visible_month()
        self._on_date_clicked(self.cal.selectedDate())

    # --------------------
    # Month / day selection
    # --------------------
    def _go_today(self):
        d = QDate.currentDate()
        self.cal.setSelectedDate(d)
        self._on_date_clicked(d)

    def _on_month_changed(self, year: int, month: int):
        self._refresh_pips_for_visible_month()

    def _on_date_clicked(self, date: QDate):
        self.selected_date = date.toString("yyyy-MM-dd")
        pretty = date.toString("ddd dd MMM yyyy")
        self.lbl_day.setText(f"Events — {pretty}")
        self._refresh_day_list()
        self._refresh_week_agenda()

    def _on_date_activated(self, date: QDate):
        # double click day -> add event for that day
        self._on_date_clicked(date)
        self._add_event()

    # --------------------
    # Data fetching
    # --------------------
    def _fetch_events_in_range(self, start: str, end: str) -> List[Event]:
        """
        Fetch reminders between [start, end] inclusive.
        """
        conn = sqlite3.connect(DB_FILE)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, description, date, time, category
                FROM reminders
                WHERE date >= ? AND date <= ?
                ORDER BY date, time
                """,
                (start, end),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        out: List[Event] = []
        for rid, title, desc, date, time, cat in rows:
            out.append(Event(rid, title, desc or "", date, time or "", cat or "Other"))
        return out

    def _refresh_pips_for_visible_month(self):
        # visible month range (pad by 1 week either side to cover prev/next month days in grid)
        y = self.cal.yearShown()
        m = self.cal.monthShown()

        first = QDate(y, m, 1)
        start = first.addDays(-14)
        end = first.addMonths(1).addDays(14)

        events = self._fetch_events_in_range(
            start.toString("yyyy-MM-dd"),
            end.toString("yyyy-MM-dd"),
        )

        by_date: Dict[str, List[str]] = {}
        for ev in events:
            by_date.setdefault(ev.date, []).append(ev.category or "Other")

        self.cal.set_events_map(by_date)

    def _fetch_for_selected(self) -> List[Event]:
        # just the selected day
        events = self._fetch_events_in_range(self.selected_date, self.selected_date)
        # sort by time
        events.sort(key=lambda e: e.time)
        return events

    # --------------------
    # Day list + Week agenda
    # --------------------
    def _refresh_day_list(self):
        self.list_day.clear()
        events = self._fetch_for_selected()
        if not events:
            it = QListWidgetItem("No events for this day.")
            it.setFlags(Qt.NoItemFlags)
            self.list_day.addItem(it)
            return

        for ev in events:
            suit = CAT_SUIT.get(ev.category, "🃏")
            label = f"{ev.time + '  ' if ev.time else ''}{suit} {ev.title}  •  {ev.category}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ev)
            self.list_day.addItem(item)

    def _refresh_week_agenda(self):
        self.list_week.clear()

        d = QDate.fromString(self.selected_date, "yyyy-MM-dd")
        if not d.isValid():
            return

        # Monday start
        offset = d.dayOfWeek() - 1  # Monday=1
        week_start = d.addDays(-offset)
        week_end = week_start.addDays(6)

        self.lbl_week.setText(
            f"Week Agenda — {week_start.toString('dd MMM')} to {week_end.toString('dd MMM')}"
        )

        events = self._fetch_events_in_range(
            week_start.toString("yyyy-MM-dd"),
            week_end.toString("yyyy-MM-dd"),
        )

        # group by date
        grouped: Dict[str, List[Event]] = {}
        for ev in events:
            grouped.setdefault(ev.date, []).append(ev)
        for k in grouped:
            grouped[k].sort(key=lambda e: e.time)

        # render
        for i in range(7):
            day = week_start.addDays(i)
            key = day.toString("yyyy-MM-dd")
            pretty = day.toString("ddd dd MMM")
            header = QListWidgetItem(f"— {pretty} —")
            header.setFlags(Qt.NoItemFlags)
            header.setForeground(QColor(palette["muted"]))
            self.list_week.addItem(header)

            day_events = grouped.get(key, [])
            if not day_events:
                none = QListWidgetItem("   (no events)")
                none.setFlags(Qt.NoItemFlags)
                none.setForeground(QColor(palette["muted"]))
                self.list_week.addItem(none)
                continue

            for ev in day_events:
                suit = CAT_SUIT.get(ev.category, "🃏")
                col = CAT_COLOR.get(ev.category, palette.get("muted", "#9FB6AE"))
                txt = f"  {ev.time + ' ' if ev.time else ''}{suit} {ev.title}  •  {ev.category}"
                it = QListWidgetItem(txt)
                it.setForeground(QColor(col))
                self.list_week.addItem(it)

    # --------------------
    # CRUD actions
    # --------------------
    def _add_event(self):
        dlg = EventDialog(self, event=None)
        if dlg.exec() != QDialog.Accepted:
            return

        title, time, cat, desc = dlg.values()
        if not title:
            QMessageBox.warning(self, "Missing", "Please enter a title.")
            return

        self.db.add_reminder(title, desc, self.selected_date, time, cat)
        log_activity(f"Added event → {title} ({cat})")

        self._refresh_pips_for_visible_month()
        self._refresh_day_list()
        self._refresh_week_agenda()

    def _get_selected_event(self) -> Optional[Event]:
        item = self.list_day.currentItem()
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

        conn = sqlite3.connect(DB_FILE)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE reminders SET title=?, description=?, time=?, category=? WHERE id=?",
                (title, desc, time, cat, ev.id),
            )
            conn.commit()
        finally:
            conn.close()

        log_activity(f"Edited event → {title} ({cat})")

        self._refresh_pips_for_visible_month()
        self._refresh_day_list()
        self._refresh_week_agenda()

    def _delete_event(self):
        ev = self._get_selected_event()
        if not ev:
            return

        if QMessageBox.question(self, "Delete", f"Delete '{ev.title}'?") != QMessageBox.Yes:
            return

        self.db.delete_reminder(ev.id)
        log_activity(f"Deleted event → {ev.title} ({ev.category})")

        self._refresh_pips_for_visible_month()
        self._refresh_day_list()
        self._refresh_week_agenda()

    # allow main_window refresh()
    def refresh(self):
        self._refresh_pips_for_visible_month()
        self._refresh_day_list()
        self._refresh_week_agenda()
