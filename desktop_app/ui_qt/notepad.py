# ui_qt/notepad.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit, QMessageBox
)

from ui_qt.base import palette


@dataclass
class NoteItem:
    id: int
    title: str
    content: str
    updated_at: str


class NotepadPage(QWidget):
    """
    Notion-ish:
    - Left: list of notes
    - Right: title + editor
    - Autosave (debounced)
    Stored inside your existing career_buddy.db as table note_items.
    """

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._ensure_schema()

        self._current_id: Optional[int] = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._commit_save)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Left panel (deck)
        left = QFrame()
        left.setStyleSheet("background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(12, 12, 12, 12)
        left_l.setSpacing(10)

        hdr = QHBoxLayout()
        lab = QLabel("📝 Notes")
        lab.setStyleSheet("font-size:18px; font-weight:900;")
        hdr.addWidget(lab)
        hdr.addStretch(1)

        btn_new = QPushButton("＋ New")
        btn_new.setStyleSheet(f"background:{palette['accent']}; color:#111; padding:8px 12px; border-radius:12px; font-weight:900;")
        btn_new.clicked.connect(self.new_note)
        hdr.addWidget(btn_new)
        left_l.addLayout(hdr)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes…")
        self.search.textChanged.connect(self.reload)
        self.search.setFixedHeight(36)
        left_l.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemClicked.connect(self._select_note)
        left_l.addWidget(self.list, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("background: rgba(231,76,60,0.25); border: 1px solid rgba(231,76,60,0.45); padding: 10px 14px; border-radius:12px; font-weight:900;")
        self.btn_delete.clicked.connect(self.delete_note)
        btns.addWidget(self.btn_delete)
        left_l.addLayout(btns)

        # Right panel (editor)
        right = QFrame()
        right.setStyleSheet("background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(12, 12, 12, 12)
        right_l.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("📄 Editor")
        title.setStyleSheet("font-size:18px; font-weight:900;")
        top.addWidget(title)
        top.addStretch(1)

        self.status = QLabel("Saved")
        self.status.setStyleSheet(f"color:{palette['muted']}; font-weight:800;")
        top.addWidget(self.status)
        right_l.addLayout(top)

        self.ent_title = QLineEdit()
        self.ent_title.setPlaceholderText("Note title")
        self.ent_title.setFixedHeight(40)
        self.ent_title.textChanged.connect(self._schedule_save)
        right_l.addWidget(self.ent_title)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Start typing…")
        self.editor.textChanged.connect(self._schedule_save)
        right_l.addWidget(self.editor, 1)

        root.addWidget(left, 0)
        root.addWidget(right, 1)

        self.setStyleSheet(f"""
            QLabel {{ color: {palette["text"]}; }}
            QLineEdit {{
                background: #F8F4EC;
                color: #111;
                border-radius: 12px;
                padding: 10px;
                font-weight: 800;
            }}
            QTextEdit {{
                background: #F8F4EC;
                color: #111;
                border-radius: 12px;
                padding: 12px;
                font-weight: 650;
            }}
            QListWidget {{
                background: rgba(0,0,0,0.18);
                color: {palette["text"]};
                border-radius: 12px;
                padding: 6px;
            }}
        """)

        self.reload()
        self._open_first_or_create()

    # ---------- DB helpers ----------
    def _conn(self):
        return sqlite3.connect(self.db.db_path)

    def _ensure_schema(self):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS note_items(
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
                );
            """)
            conn.commit()

    def _list_notes(self, q: str = "") -> List[NoteItem]:
        with self._conn() as conn:
            cur = conn.cursor()
            if q.strip():
                like = f"%{q.strip()}%"
                cur.execute("""
                    SELECT id, title, content, updated_at
                    FROM note_items
                    WHERE title LIKE ? OR content LIKE ?
                    ORDER BY updated_at DESC
                """, (like, like))
            else:
                cur.execute("""
                    SELECT id, title, content, updated_at
                    FROM note_items
                    ORDER BY updated_at DESC
                """)
            rows = cur.fetchall()
            return [NoteItem(*r) for r in rows]

    def _get_note(self, note_id: int) -> Optional[NoteItem]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, content, updated_at FROM note_items WHERE id=?", (note_id,))
            r = cur.fetchone()
            return NoteItem(*r) if r else None

    def _insert_note(self, title: str, content: str) -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO note_items(title, content) VALUES(?,?)", (title, content))
            conn.commit()
            return int(cur.lastrowid)

    def _update_note(self, note_id: int, title: str, content: str):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE note_items
                SET title=?, content=?, updated_at=strftime('%Y-%m-%d %H:%M:%S','now')
                WHERE id=?
            """, (title, content, note_id))
            conn.commit()

    def _delete_note(self, note_id: int):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM note_items WHERE id=?", (note_id,))
            conn.commit()

    # ---------- UI ----------
    def reload(self):
        q = self.search.text()
        notes = self._list_notes(q)

        self.list.blockSignals(True)
        self.list.clear()
        for n in notes:
            item = QListWidgetItem(n.title if n.title.strip() else "Untitled")
            item.setData(Qt.UserRole, n.id)
            self.list.addItem(item)
        self.list.blockSignals(False)

        # keep selection if possible
        if self._current_id is not None:
            for i in range(self.list.count()):
                it = self.list.item(i)
                if int(it.data(Qt.UserRole)) == self._current_id:
                    self.list.setCurrentItem(it)
                    break

    def _open_first_or_create(self):
        if self.list.count() == 0:
            self.new_note()
            return
        first = self.list.item(0)
        self.list.setCurrentItem(first)
        self._select_note(first)

    def new_note(self):
        note_id = self._insert_note("New note", "")
        self._current_id = note_id
        self.reload()

        # select it
        for i in range(self.list.count()):
            it = self.list.item(i)
            if int(it.data(Qt.UserRole)) == note_id:
                self.list.setCurrentItem(it)
                break

        self.ent_title.setText("New note")
        self.editor.setPlainText("")
        self.status.setText("Saved")

    def delete_note(self):
        if self._current_id is None:
            return
        if QMessageBox.question(self, "Delete note", "Delete this note?") != QMessageBox.Yes:
            return

        self._delete_note(self._current_id)
        self._current_id = None
        self.reload()
        self._open_first_or_create()

    def _select_note(self, item: QListWidgetItem):
        note_id = int(item.data(Qt.UserRole))
        note = self._get_note(note_id)
        if not note:
            return

        self._current_id = note.id

        # block to avoid triggering autosave while loading
        self.ent_title.blockSignals(True)
        self.editor.blockSignals(True)

        self.ent_title.setText(note.title)
        self.editor.setPlainText(note.content)

        self.ent_title.blockSignals(False)
        self.editor.blockSignals(False)

        self.status.setText("Saved")

    def _schedule_save(self):
        if self._current_id is None:
            return
        self.status.setText("Typing…")
        self._save_timer.start(450)

    def _commit_save(self):
        if self._current_id is None:
            return
        title = self.ent_title.text().strip() or "Untitled"
        content = self.editor.toPlainText()
        self._update_note(self._current_id, title, content)
        self.status.setText("Saved")
        self.reload()
