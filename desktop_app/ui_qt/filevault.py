# ui_qt/filevault.py
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QComboBox, QTableWidget, QTableWidgetItem, QMessageBox
)

from ui_qt.base import palette


CATEGORIES = ["All", "CV", "Cover Letters", "Certificates", "Applications", "Other"]


class FileVaultPage(QWidget):
    def __init__(self, db, vault_dir: str):
        super().__init__()
        self.db = db
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("📁 File Vault")
        title.setStyleSheet("font-size:20px; font-weight:900;")
        header.addWidget(title)
        header.addStretch(1)

        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(CATEGORIES)
        self.cmb_cat.setFixedHeight(36)
        self.cmb_cat.currentTextChanged.connect(self.reload)

        btn_add = QPushButton("➕ Import File")
        btn_add.setStyleSheet(f"background:{palette['accent']}; color:#111; padding:10px 14px; border-radius:12px; font-weight:900;")
        btn_add.clicked.connect(self.import_file)

        header.addWidget(self.cmb_cat)
        header.addWidget(btn_add)
        root.addLayout(header)

        # Table
        card = QFrame()
        card.setStyleSheet(f"background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;")
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(12, 12, 12, 12)
        card_l.setSpacing(10)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Category", "Date Added", "Stored As"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.open_selected)

        btns = QHBoxLayout()
        btns.addStretch(1)

        self.btn_open = QPushButton("Open")
        self.btn_open.clicked.connect(self.open_selected)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("background: rgba(231,76,60,0.25); border: 1px solid rgba(231,76,60,0.45); padding: 10px 14px; border-radius:12px; font-weight:900;")
        self.btn_delete.clicked.connect(self.delete_selected)

        for b in (self.btn_open, self.btn_delete):
            b.setFixedHeight(38)
            b.setStyleSheet(b.styleSheet() or "background: rgba(255,255,255,0.10); padding: 10px 14px; border-radius:12px; font-weight:900;")
        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_delete)

        card_l.addWidget(self.table, 1)
        card_l.addLayout(btns)

        root.addWidget(card, 1)

        self.setStyleSheet(f"""
            QLabel {{ color: {palette["text"]}; }}
            QComboBox {{
                background: #F8F4EC;
                color: #111;
                border-radius: 10px;
                padding: 6px;
                font-weight: 800;
            }}
            QTableWidget {{
                background: rgba(0,0,0,0.18);
                color: {palette["text"]};
                border: none;
                border-radius: 12px;
                gridline-color: rgba(255,255,255,0.08);
            }}
            QHeaderView::section {{
                background: rgba(0,0,0,0.35);
                color: {palette["text"]};
                font-weight: 900;
                border: none;
                padding: 8px;
            }}
        """)

        self.reload()

    def reload(self):
        cat = self.cmb_cat.currentText()
        rows = self.db.list_files(cat)

        self.table.setRowCount(0)
        for (file_id, filename, original_name, category, date_added) in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)

            self.table.setItem(r, 0, QTableWidgetItem(original_name))
            self.table.setItem(r, 1, QTableWidgetItem(category))
            self.table.setItem(r, 2, QTableWidgetItem(date_added))
            self.table.setItem(r, 3, QTableWidgetItem(filename))

            # stash file_id in first cell
            self.table.item(r, 0).setData(Qt.UserRole, int(file_id))

        self.table.resizeColumnsToContents()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import file")
        if not path:
            return

        # pick category
        cat = self.cmb_cat.currentText()
        if cat == "All":
            cat = "Other"

        src = Path(path)
        ext = src.suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        dst = self.vault_dir / stored_name

        try:
            shutil.copy2(src, dst)
            self.db.add_file(filename=stored_name, original_name=src.name, category=cat)
            self.reload()
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))

    def _selected_row_file(self) -> Optional[tuple[int, str]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item0 = self.table.item(row, 0)
        stored_item = self.table.item(row, 3)
        if not item0 or not stored_item:
            return None
        file_id = int(item0.data(Qt.UserRole))
        stored_name = stored_item.text()
        return file_id, stored_name

    def open_selected(self):
        sel = self._selected_row_file()
        if not sel:
            return
        _file_id, stored_name = sel
        full_path = self.vault_dir / stored_name
        if not full_path.exists():
            QMessageBox.warning(self, "Missing file", "This file no longer exists on disk.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))

    def delete_selected(self):
        sel = self._selected_row_file()
        if not sel:
            return
        file_id, stored_name = sel

        if QMessageBox.question(self, "Delete", "Delete this file from the vault?") != QMessageBox.Yes:
            return

        full_path = self.vault_dir / stored_name
        try:
            self.db.delete_file(file_id)
            if full_path.exists():
                full_path.unlink()
            self.reload()
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))
