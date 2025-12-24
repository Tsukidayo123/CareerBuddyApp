# ui_qt/analytics.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QListWidget,
    QListWidgetItem, QSizePolicy
)

from services.db import DB_FILE
from ui_qt.base import palette


KANBAN = ["To Apply", "Applied", "Interviewing", "Offer", "Rejected"]

COLORS = {
    "To Apply": "#3498db",
    "Applied": "#f39c12",
    "Interviewing": "#9b59b6",
    "Offer": "#27ae60",
    "Rejected": "#e74c3c",
}

SUITS = {
    "To Apply": "♣",
    "Applied": "♦",
    "Interviewing": "♥",
    "Offer": "♠",
    "Rejected": "🃏",
}
RANKS = {
    "To Apply": "10",
    "Applied": "J",
    "Interviewing": "Q",
    "Offer": "K",
    "Rejected": "✖",
}


def _ensure_activity_table() -> None:
    """Create a lightweight activity table if missing (no DB migration needed)."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS activity(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                message TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def log_activity(message: str) -> None:
    """Call from other pages (tracker) to record moves."""
    _ensure_activity_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO activity (ts, message) VALUES (?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_recent_activity(limit: int = 30) -> List[Tuple[str, str]]:
    _ensure_activity_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ts, message FROM activity ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()
    finally:
        conn.close()


class StatCard(QFrame):
    def __init__(self, title: str, value: str, badge: str, accent: str):
        super().__init__()
        self.setObjectName("statCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        pill = QLabel(badge)
        pill.setObjectName("badge")
        pill.setAlignment(Qt.AlignCenter)
        pill.setFixedHeight(28)
        pill.setMinimumWidth(60)
        pill.setStyleSheet(
            f"background:{accent}; color:#111; border-radius:12px; font-weight:900;"
        )

        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{palette['muted']}; font-weight:850;")
        top.addWidget(pill, 0)
        top.addSpacing(8)
        top.addWidget(lbl, 1)
        lay.addLayout(top)

        val = QLabel(value)
        val.setStyleSheet("color:white; font-weight:950; font-size:22px;")
        lay.addWidget(val)

        self.setStyleSheet(f"""
            QFrame#statCard {{
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
            }}
        """)


class AnalyticsPage(QWidget):
    """
    Redesigned Analytics:
    - Hand of 4 stat cards
    - Status distribution bars
    - Recent Moves activity log (no deck duplication)
    """

    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("📊 Analytics")
        title.setStyleSheet("font-size:20px; font-weight:950; color:white;")
        subtitle = QLabel("Overview + momentum (not a second tracker).")
        subtitle.setStyleSheet(f"color:{palette['muted']}; font-weight:750;")
        title_row.addWidget(title)
        title_row.addSpacing(10)
        title_row.addWidget(subtitle, 1)
        root.addLayout(title_row)

        # Top stats (hand of cards)
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(12)

        self.card_total = StatCard("Total Jobs", "0", "♠ A", palette["accent"])
        self.card_interviews = StatCard("Interviews", "0", "♥ Q", COLORS["Interviewing"])
        self.card_offers = StatCard("Offers", "0", "♠ K", COLORS["Offer"])
        self.card_reject = StatCard("Rejection Rate", "0%", "🃏", COLORS["Rejected"])

        self.stats_row.addWidget(self.card_total, 1)
        self.stats_row.addWidget(self.card_interviews, 1)
        self.stats_row.addWidget(self.card_offers, 1)
        self.stats_row.addWidget(self.card_reject, 1)
        root.addLayout(self.stats_row)

        # Middle: Distribution + Recent Moves
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Distribution panel
        self.panel_dist = QFrame()
        self.panel_dist.setObjectName("panel")
        dist_lay = QVBoxLayout(self.panel_dist)
        dist_lay.setContentsMargins(14, 12, 14, 12)
        dist_lay.setSpacing(10)

        dist_title = QLabel("Status Distribution")
        dist_title.setStyleSheet("color:white; font-weight:950;")
        dist_lay.addWidget(dist_title)

        self.dist_rows_container = QVBoxLayout()
        self.dist_rows_container.setSpacing(10)
        dist_lay.addLayout(self.dist_rows_container, 1)

        # Recent moves panel
        self.panel_moves = QFrame()
        self.panel_moves.setObjectName("panel")
        moves_lay = QVBoxLayout(self.panel_moves)
        moves_lay.setContentsMargins(14, 12, 14, 12)
        moves_lay.setSpacing(10)

        moves_title = QLabel("Recent Moves")
        moves_title.setStyleSheet("color:white; font-weight:950;")
        moves_lay.addWidget(moves_title)

        self.moves_list = QListWidget()
        self.moves_list.setObjectName("movesList")
        moves_lay.addWidget(self.moves_list, 1)

        mid.addWidget(self.panel_dist, 3)
        mid.addWidget(self.panel_moves, 2)
        root.addLayout(mid, 1)

        self.setStyleSheet(f"""
            QFrame#panel {{
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
            }}
            QListWidget#movesList {{
                background: rgba(0,0,0,0.12);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                color: {palette["text"]};
                font-weight: 650;
            }}
        """)

        self.refresh()

    # --------------------------
    # Data + UI building
    # --------------------------
    def refresh(self):
        jobs = self.db.get_all_jobs()  # (id, company, role, status, notes, date_added)
        total = len(jobs)

        counts: Dict[str, int] = {k: 0 for k in KANBAN}
        for _id, _company, _role, status, _notes, _date in jobs:
            if status in counts:
                counts[status] += 1

        interviews = counts.get("Interviewing", 0)
        offers = counts.get("Offer", 0)
        rejected = counts.get("Rejected", 0)
        reject_rate = int(round((rejected / total) * 100)) if total else 0

        # Update stat cards
        self._set_stat_value(self.card_total, str(total))
        self._set_stat_value(self.card_interviews, str(interviews))
        self._set_stat_value(self.card_offers, str(offers))
        self._set_stat_value(self.card_reject, f"{reject_rate}%")

        # Distribution rows
        self._rebuild_distribution(counts, total)

        # Recent moves
        self._rebuild_moves()

    def _set_stat_value(self, stat_card: StatCard, value: str):
        # the value label is the 2nd widget in stat_card layout
        lay = stat_card.layout()
        val_widget = lay.itemAt(1).widget()
        if isinstance(val_widget, QLabel):
            val_widget.setText(value)

    def _rebuild_distribution(self, counts: Dict[str, int], total: int):
        # Clear current rows
        while self.dist_rows_container.count():
            item = self.dist_rows_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for st in KANBAN:
            row = QFrame()
            r = QHBoxLayout(row)
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(10)

            left = QLabel(f"{SUITS[st]} {RANKS[st]}  {st}")
            left.setStyleSheet("color:white; font-weight:850;")
            left.setMinimumWidth(160)

            count = counts.get(st, 0)
            pct = (count / total) if total else 0

            bar_shell = QFrame()
            bar_shell.setStyleSheet(
                "background: rgba(255,255,255,0.08); border-radius: 10px;"
            )
            bar_shell.setFixedHeight(18)

            bar = QFrame(bar_shell)
            bar.setStyleSheet(f"background: {COLORS[st]}; border-radius: 10px;")

            # Use fixed width relative to shell width after layout
            # We'll set it on showEvent-ish via a lambda to avoid 0 width.
            def _apply_width(shell=bar_shell, inner=bar, p=pct):
                w = shell.width()
                inner.setGeometry(0, 0, int(w * p), shell.height())

            bar_shell.resizeEvent = lambda _e, f=_apply_width: f()

            right = QLabel(f"{count}")
            right.setStyleSheet(f"color:{palette['muted']}; font-weight:900;")
            right.setMinimumWidth(30)
            right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            r.addWidget(left)
            r.addWidget(bar_shell, 1)
            r.addWidget(right)

            self.dist_rows_container.addWidget(row)

    def _rebuild_moves(self):
        self.moves_list.clear()
        rows = fetch_recent_activity(limit=30)
        if not rows:
            it = QListWidgetItem("No activity yet. Move a job to see history here.")
            it.setFlags(Qt.NoItemFlags)
            self.moves_list.addItem(it)
            return

        for ts, msg in rows:
            item = QListWidgetItem(f"{ts}  •  {msg}")
            self.moves_list.addItem(item)
