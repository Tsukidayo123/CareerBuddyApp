# ui_qt/tracker.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QMimeData, QPoint
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QDialog,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QMessageBox,
)

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


@dataclass
class Job:
    id: int
    company: str
    role: str
    status: str
    link: str
    notes: str
    date_added: str


class AddJobDialog(QDialog):
    def __init__(self, parent: QWidget, db, job: Optional[Job] = None):
        super().__init__(parent)
        self.db = db
        self.job = job

        self.setWindowTitle("Add Job" if job is None else "Edit Job")
        self.setModal(True)
        self.setFixedSize(520, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        title = QLabel("Add a Job" if job is None else "Edit Job")
        title.setStyleSheet("font-size:18px;font-weight:800;")
        root.addWidget(title)

        self.ent_company = QLineEdit()
        self.ent_company.setPlaceholderText("Company")

        self.ent_role = QLineEdit()
        self.ent_role.setPlaceholderText("Job Title")

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(KANBAN)

        self.ent_link = QLineEdit()
        self.ent_link.setPlaceholderText("Job Link (optional)")

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Description / notes...")

        for w in [self.ent_company, self.ent_role, self.cmb_status, self.ent_link]:
            w.setFixedHeight(38)

        root.addWidget(self.ent_company)
        root.addWidget(self.ent_role)
        root.addWidget(self.cmb_status)
        root.addWidget(self.ent_link)
        root.addWidget(self.txt_notes, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_save = QPushButton("Save")
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._save)

        if job is not None:
            self.ent_company.setText(job.company)
            self.ent_role.setText(job.role)
            self.cmb_status.setCurrentText(job.status)
            self.ent_link.setText(job.link or "")
            self.txt_notes.setPlainText(job.notes or "")

        # readable inputs
        self.setStyleSheet(f"""
            QDialog {{
                background: {palette["bg_dark"]};
                color: {palette["text"]};
                border-radius: 18px;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background: #F8F4EC;
                color: #111;
                border: 1px solid rgba(0,0,0,0.15);
                border-radius: 12px;
                padding: 10px;
                font-weight: 650;
            }}
            QTextEdit {{
                padding: 12px;
            }}
            QComboBox QAbstractItemView {{
                background: #F8F4EC;
                color: #111;
                selection-background-color: {palette["accent"]};
                selection-color: #111;
            }}
            QPushButton {{
                padding: 10px 14px;
                border-radius: 12px;
                font-weight: 800;
            }}
        """)
        btn_save.setStyleSheet(f"background:{palette['accent']}; color:#111;")
        btn_cancel.setStyleSheet(f"background:{palette['panel']}; color:{palette['text']};")

    def _save(self):
        company = self.ent_company.text().strip()
        role = self.ent_role.text().strip()
        status = self.cmb_status.currentText()
        link = self.ent_link.text().strip()
        notes = self.txt_notes.toPlainText().strip()

        if not company or not role:
            QMessageBox.warning(self, "Missing", "Company and Job Title are required.")
            return

        if self.job is None:
            self.db.add_job(company, role, status, link=link, notes=notes)
        else:
            self.db.edit_job(self.job.id, company, role, status, notes, link=link)

        self.accept()


class JobCard(QFrame):
    """
    Click vs drag threshold:
    - release without dragging => open/edit
    - drag => ghost preview + drop
    """

    def __init__(self, job: Job, on_open, on_delete):
        super().__init__()
        self.job = job
        self.on_open = on_open
        self.on_delete = on_delete

        self.setObjectName("JobCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setAcceptDrops(False)
        self.setCursor(Qt.PointingHandCursor)

        self._press_pos: Optional[QPoint] = None
        self._drag_started = False
        self._drag_threshold = 8

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        rank = QLabel(f"{RANKS[job.status]} {SUITS[job.status]}")
        rank.setStyleSheet("font-weight:900; font-size:14px; color:#111;")
        top.addWidget(rank)
        top.addStretch(1)

        btn_x = QPushButton("×")
        btn_x.setFixedSize(28, 28)
        btn_x.setStyleSheet("background:transparent; border:none; font-size:18px; color:#444;")
        btn_x.clicked.connect(lambda: self.on_delete(self.job))
        top.addWidget(btn_x)
        root.addLayout(top)

        company = QLabel(job.company)
        company.setAlignment(Qt.AlignCenter)
        company.setStyleSheet("font-weight:900; font-size:14px; color:#111;")

        role = QLabel(job.role)
        role.setAlignment(Qt.AlignCenter)
        role.setWordWrap(True)
        role.setStyleSheet("color:#333; font-weight:650;")

        root.addWidget(company)
        root.addWidget(role)

        bot = QHBoxLayout()
        bot.addStretch(1)
        br = QLabel(f"{SUITS[job.status]} {RANKS[job.status]}")
        br.setStyleSheet("font-weight:900; font-size:12px; color:#111;")
        bot.addWidget(br)
        root.addLayout(bot)

        handle = QLabel("⇅ DRAG")
        handle.setAlignment(Qt.AlignCenter)
        handle.setObjectName("DragHandle")
        handle.setFixedHeight(18)
        root.addWidget(handle)

        border = COLORS.get(job.status, "#555")
        bg = "#F8F4EC"

        if job.status == "Rejected":
            bg = "#3b3b3b"
            company.setStyleSheet("font-weight:900; font-size:14px; color:#CFCFCF;")
            role.setStyleSheet("color:#BDBDBD; font-weight:650;")
            rank.setStyleSheet("font-weight:900; font-size:14px; color:#CFCFCF;")
            br.setStyleSheet("font-weight:900; font-size:12px; color:#CFCFCF;")
            btn_x.setStyleSheet("background:transparent; border:none; font-size:18px; color:#9a9a9a;")

        self.setStyleSheet(f"""
            QFrame#JobCard {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 18px;
            }}
            QLabel#DragHandle {{
                background: {palette["accent2"]};
                color: #0f1115;
                border-radius: 10px;
                font-weight: 900;
                font-size: 10px;
            }}
        """)

    def _begin_drag(self):
        mime = QMimeData()
        mime.setText(str(self.job.id))

        drag = QDrag(self)
        drag.setMimeData(mime)

        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())

        drag.exec(Qt.MoveAction)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self._drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return super().mouseMoveEvent(event)
        if not (event.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(event)

        cur = event.position().toPoint()
        delta = cur - self._press_pos

        if not self._drag_started and (abs(delta.x()) > self._drag_threshold or abs(delta.y()) > self._drag_threshold):
            self._drag_started = True
            self._begin_drag()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._drag_started:
                self.on_open(self.job)
            self._press_pos = None
            self._drag_started = False
        super().mouseReleaseEvent(event)


class DropColumn(QFrame):
    def __init__(self, status: str, on_drop_job_id):
        super().__init__()
        self.status = status
        self.on_drop_job_id = on_drop_job_id

        self.setAcceptDrops(True)
        self.setObjectName("DropColumn")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel(f"{SUITS[status]} {RANKS[status]}  {status}")
        header.setObjectName("ColHeader")
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(44)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.cards_container)

        root.addWidget(header)
        root.addWidget(scroll, 1)

        self.setStyleSheet(f"""
            QFrame#DropColumn {{
                background: {palette["bg_medium"]};
                border-radius: 18px;
            }}
            QLabel#ColHeader {{
                background: {COLORS[status]};
                color: white;
                border-radius: 14px;
                font-weight: 900;
            }}
        """)

    def clear_cards(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def add_card(self, card: JobCard):
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        job_id_txt = event.mimeData().text().strip()
        if job_id_txt.isdigit():
            self.on_drop_job_id(int(job_id_txt), self.status)
        event.acceptProposedAction()


class JobTrackerPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        tip = QLabel("Tip: Click a card to edit. Click + drag to move it (ghost preview).")
        tip.setStyleSheet(f"color:{palette['accent']}; padding: 6px 2px; font-weight:900;")
        root.addWidget(tip)

        header_row = QHBoxLayout()
        title = QLabel("🃏 Job Deck")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        btn_add = QPushButton("+ Add Job")
        btn_add.setStyleSheet(f"background:{palette['accent']}; color:#111; padding:10px 14px; border-radius:12px; font-weight:900;")
        btn_add.clicked.connect(self.add_job)
        header_row.addWidget(btn_add)
        root.addLayout(header_row)

        self.columns_row = QHBoxLayout()
        self.columns_row.setSpacing(12)

        self.columns: dict[str, DropColumn] = {}
        for st in KANBAN:
            col = DropColumn(st, self.on_drop_job)
            self.columns[st] = col
            self.columns_row.addWidget(col, 1)

        wrap = QWidget()
        wrap.setLayout(self.columns_row)
        root.addWidget(wrap, 1)

        self.reload()

    def _fetch_jobs(self) -> list[Job]:
        rows = self.db.get_all_jobs()
        jobs: list[Job] = []
        for r in rows:
            job_id, company, role, status, notes, date_added = r
            # Your current get_all_jobs() doesn't return link, so we keep link empty here.
            # If you want link on cards, update get_all_jobs to SELECT link too.
            jobs.append(Job(job_id, company, role, status, link="", notes=notes or "", date_added=date_added or ""))
        return jobs

    def reload(self):
        for col in self.columns.values():
            col.clear_cards()

        for job in self._fetch_jobs():
            card = JobCard(job, on_open=self.open_details, on_delete=self.delete_job)
            self.columns[job.status].add_card(card)

    def add_job(self):
        dlg = AddJobDialog(self, self.db, job=None)
        if dlg.exec() == QDialog.Accepted:
            self.reload()

    def open_details(self, job: Job):
        dlg = AddJobDialog(self, self.db, job=job)
        if dlg.exec() == QDialog.Accepted:
            self.reload()

    def delete_job(self, job: Job):
        self.db.delete_job(job.id)
        self.reload()

    def on_drop_job(self, job_id: int, new_status: str):
        self.db.update_job_status(job_id, new_status)
        self.reload()
