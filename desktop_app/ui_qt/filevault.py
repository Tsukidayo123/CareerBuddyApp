# ui_qt/filevault.py
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from datetime import datetime

from PySide6.QtCore import Qt, QUrl, QSize, QRect, QPoint, Signal, QTimer
from PySide6.QtGui import QDesktopServices, QCursor, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QComboBox, QMessageBox, QScrollArea, QSizePolicy, QLayout,
    QLayoutItem
)

from ui_qt.base import palette


CATEGORIES = ["All", "CV", "Cover Letters", "Certificates", "Applications", "Other"]

CATEGORY_SUIT = {
    "CV": "♠",
    "Cover Letters": "♥",
    "Certificates": "♦",
    "Applications": "♣",
    "Other": "•",
    "All": "•",
}


def normalize_category(cat: str) -> str:
    c = (cat or "").strip()
    if c.lower() in ("cv/resume", "cv_resume", "cv-resume", "cv/resumé", "cv/resumé"):
        return "CV"
    # if your DB ever stores "CV/Resume" etc, normalize it here
    return c


SORT_OPTIONS = [
    "Newest",
    "Oldest",
    "Name A–Z",
    "Name Z–A",
    "Category",
]

# Option B: PyMuPDF for PDF thumbnails
try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except Exception:
    fitz = None  # type: ignore
    _HAS_PYMUPDF = False


def _safe_date_key(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime.min


def infer_category_from_filename(name: str, ext: str) -> str:
    """
    Smarter inference:
    - Images default to Other unless filename has STRONG keywords.
    - PDFs/docs inferred more freely.
    """
    s = (name or "").lower()

    def has_any(words: List[str]) -> bool:
        return any(w in s for w in words)

    is_image = ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

    if is_image:
        if has_any(["resume", "résumé", "cv_", "_cv", " cv ", "curriculum vitae"]):
            return "CV"
        if has_any(["cover letter", "coverletter", "cl_"]):
            return "Cover Letters"
        if has_any(["certificate", "certification", "cert_"]):
            return "Certificates"
        if has_any(["application", "appl_"]):
            return "Applications"
        return "Other"

    if "cover" in s and ("letter" in s or "coverletter" in s or "cl" in s):
        return "Cover Letters"
    if "cover letter" in s:
        return "Cover Letters"
    if "certificate" in s or "certification" in s or "cert" in s:
        return "Certificates"
    if "application" in s or "appl" in s:
        return "Applications"
    if "resume" in s or "résumé" in s or "cv" in s:
        return "CV"

    return "Other"


# -----------------------------
# FlowLayout (wrap grid)
# -----------------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=12):
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)

        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        space_x = self.spacing()
        space_y = self.spacing()

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()

            next_x = x + w + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + w + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))

            x = next_x
            line_height = max(line_height, h)

        total_height = (y + line_height) - rect.y() + bottom
        return total_height


# -----------------------------
# File Card (A4 style + preview)
# -----------------------------
class FileCard(QFrame):
    clicked = Signal(int, str)         # file_id, stored_name
    doubleClicked = Signal(int, str)   # file_id, stored_name

    def __init__(
        self,
        file_id: int,
        stored_name: str,
        title: str,
        category: str,
        date_added: str,
        full_path: Path,
        thumb_cache: Dict[str, QPixmap],
        parent=None
    ):
        super().__init__(parent)
        self.file_id = int(file_id)
        self.stored_name = stored_name
        self.title_text = title
        self.category = category
        self.date_added = date_added
        self.full_path = full_path
        self.thumb_cache = thumb_cache

        self.setObjectName("fileCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # A4-ish
        self.setFixedSize(178, 252)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # top row
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        suit = CATEGORY_SUIT.get(category, "•")

        self.lbl_suit = QLabel(suit)
        self.lbl_suit.setObjectName("cardSuit")
        self.lbl_suit.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.pill = QLabel(category if category else "Other")
        self.pill.setObjectName("cardPill")
        self.pill.setAlignment(Qt.AlignCenter)

        top.addWidget(self.lbl_suit)
        top.addStretch(1)
        top.addWidget(self.pill)
        lay.addLayout(top)

        # preview
        self.preview = QLabel()
        self.preview.setObjectName("cardPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(155)
        lay.addWidget(self.preview)

        # dark scrim to make hover text clearer
        self.preview_scrim = QFrame(self.preview)
        self.preview_scrim.setObjectName("previewScrim")
        self.preview_scrim.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.preview_scrim.hide()

        # footer
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)

        self.lbl_date = QLabel(date_added)
        self.lbl_date.setObjectName("cardDate")
        self.lbl_date.setAlignment(Qt.AlignLeft)

        self.lbl_hint = QLabel("Double-click to open")
        self.lbl_hint.setObjectName("cardHint")
        self.lbl_hint.setAlignment(Qt.AlignRight)

        footer.addWidget(self.lbl_date, 1)
        footer.addWidget(self.lbl_hint, 1)
        lay.addLayout(footer)

        # hover sheet
        self.hover_sheet = QFrame(self)
        self.hover_sheet.setObjectName("hoverSheet")
        self.hover_sheet.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hover_sheet.hide()

        hs_l = QVBoxLayout(self.hover_sheet)
        hs_l.setContentsMargins(12, 10, 12, 10)
        hs_l.setSpacing(4)

        self.hs_title = QLabel(title)
        self.hs_title.setObjectName("hoverTitle")
        self.hs_title.setWordWrap(True)

        self.hs_type = QLabel(f"{suit}  {category}")
        self.hs_type.setObjectName("hoverType")

        hs_l.addWidget(self.hs_title)
        hs_l.addWidget(self.hs_type)

        # selection ring overlay (more visible than QSS border)
        self.sel_ring = QFrame(self)
        self.sel_ring.setObjectName("selRing")
        self.sel_ring.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.sel_ring.hide()

        self.set_selected(False)
        self.setToolTip(f"{self.title_text}\n{self.category}")

        QTimer.singleShot(0, self._load_preview)

    def _cache_key(self) -> str:
        try:
            mtime = self.full_path.stat().st_mtime
        except Exception:
            mtime = 0
        return f"{self.full_path}|{mtime}"

    def _load_preview(self):
        key = self._cache_key()
        if key in self.thumb_cache:
            self._set_preview_pixmap(self.thumb_cache[key])
            return

        pix = self._make_preview_pixmap()
        if pix and not pix.isNull():
            self.thumb_cache[key] = pix
        self._set_preview_pixmap(pix)

    def _set_preview_pixmap(self, pix: Optional[QPixmap]):
        if pix and not pix.isNull():
            self.preview.setPixmap(pix)
            return

        suit = CATEGORY_SUIT.get(self.category, "•")
        self.preview.setText(suit)
        self.preview.setObjectName("cardPreviewFallback")
        self.preview.setAlignment(Qt.AlignCenter)

        self.preview.style().unpolish(self.preview)
        self.preview.style().polish(self.preview)
        self.preview.update()

    def _make_preview_pixmap(self) -> Optional[QPixmap]:
        if not self.full_path.exists():
            return None

        ext = self.full_path.suffix.lower()
        target = QSize(154, 155)

        # images
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            pix = QPixmap(str(self.full_path))
            if pix.isNull():
                return None
            return pix.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        # pdfs via PyMuPDF
        if ext == ".pdf" and _HAS_PYMUPDF and fitz is not None:
            try:
                doc = fitz.open(str(self.full_path))
                if doc.page_count <= 0:
                    return None
                page = doc.load_page(0)
                mat = fitz.Matrix(2.0, 2.0)
                pm = page.get_pixmap(matrix=mat, alpha=False)

                if pm.n >= 4:
                    pm = fitz.Pixmap(fitz.csRGB, pm)

                img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888)
                img = img.copy()  # detach from PyMuPDF buffer
                pix = QPixmap.fromImage(img)
                return pix.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            except Exception:
                return None

        return None

    def resizeEvent(self, e):
        super().resizeEvent(e)

        # scrim covers preview
        self.preview_scrim.setGeometry(0, 0, self.preview.width(), self.preview.height())

        # ring sits just inside edge
        self.sel_ring.setGeometry(1, 1, self.width() - 2, self.height() - 2)

        # bottom sheet anchored
        sheet_h = 72
        self.hover_sheet.setGeometry(10, self.height() - sheet_h - 10, self.width() - 20, sheet_h)

    def enterEvent(self, e):
        self.hover_sheet.show()
        self.preview_scrim.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_sheet.hide()
        self.preview_scrim.hide()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.file_id, self.stored_name)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.file_id, self.stored_name)
        super().mouseDoubleClickEvent(e)

    def set_selected(self, selected: bool):
        self.sel_ring.setVisible(selected)
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# -----------------------------
# Main Page
# -----------------------------
class FileVaultPage(QWidget):
    def __init__(self, db, vault_dir: str):
        super().__init__()
        self.db = db
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        self._selected: Optional[Tuple[int, str]] = None
        self._selected_card: Optional[FileCard] = None
        self._thumb_cache: Dict[str, QPixmap] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("📁 File Vault")
        title.setStyleSheet("font-size:20px; font-weight:900;")
        header.addWidget(title)
        header.addStretch(1)

        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems(SORT_OPTIONS)
        self.cmb_sort.setFixedHeight(36)
        self.cmb_sort.currentTextChanged.connect(self.reload)

        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(CATEGORIES)
        self.cmb_cat.setFixedHeight(36)
        self.cmb_cat.currentTextChanged.connect(self.reload)

        btn_add = QPushButton("➕ Import File")
        btn_add.setStyleSheet(
            f"background:{palette['accent']}; color:#111; padding:10px 14px;"
            f" border-radius:12px; font-weight:900;"
        )
        btn_add.clicked.connect(self.import_file)

        header.addWidget(self.cmb_sort)
        header.addWidget(self.cmb_cat)
        header.addWidget(btn_add)
        root.addLayout(header)

        # Panel
        card = QFrame()
        card.setObjectName("panel")
        card.setStyleSheet(
            "background: rgba(255,255,255,0.04);"
            "border: 1px solid rgba(255,255,255,0.08);"
            "border-radius: 16px;"
        )
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(12, 12, 12, 12)
        card_l.setSpacing(10)

        # Headings strip (kept)
        headings = QFrame()
        headings.setObjectName("vaultHeadings")
        head_l = QHBoxLayout(headings)
        head_l.setContentsMargins(10, 8, 10, 8)
        head_l.setSpacing(10)

        for txt, stretch in (("Name", 2), ("Category", 1), ("Date Added", 1), ("Stored As", 2)):
            lbl = QLabel(txt)
            lbl.setObjectName("vaultHeadingLbl")
            head_l.addWidget(lbl, stretch)

        card_l.addWidget(headings)

        # Scroll + FlowLayout
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_host = QWidget()
        self.flow = FlowLayout(self.grid_host, margin=6, spacing=14)
        self.grid_host.setLayout(self.flow)
        self.scroll.setWidget(self.grid_host)

        card_l.addWidget(self.scroll, 1)

        # Bottom actions
        btns = QHBoxLayout()
        btns.addStretch(1)

        self.btn_open = QPushButton("Open")
        self.btn_open.setFixedHeight(38)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_open.setStyleSheet(
            "background: rgba(255,255,255,0.10); padding: 10px 14px; border-radius:12px; font-weight:900;"
        )

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setFixedHeight(38)
        self.btn_delete.setStyleSheet(
            "background: rgba(231,76,60,0.25);"
            "border: 1px solid rgba(231,76,60,0.45);"
            "padding: 10px 14px;"
            "border-radius:12px;"
            "font-weight:900;"
        )
        self.btn_delete.clicked.connect(self.delete_selected)

        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_delete)
        card_l.addLayout(btns)

        root.addWidget(card, 1)

        # Styles
        self.setStyleSheet(f"""
            QLabel {{ color: {palette["text"]}; }}

            QComboBox {{
                background: #F8F4EC;
                color: #111;
                border-radius: 10px;
                padding: 6px;
                font-weight: 800;
                min-width: 140px;
            }}

            QScrollArea {{ background: transparent; }}

            QFrame#vaultHeadings {{
                background: rgba(0,0,0,0.35);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
            }}
            QLabel#vaultHeadingLbl {{
                font-weight: 900;
                color: {palette["text"]};
            }}

            /* Card base */
            QFrame#fileCard {{
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
            }}
            QFrame#fileCard:hover {{
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.18);
            }}

            /* Optional: subtle selected fill (ring is handled by selRing overlay) */
            QFrame#fileCard[selected="true"] {{
                background: rgba(255,255,255,0.07);
            }}

            /* Selection ring overlay */
            QFrame#selRing {{
                border: 2px solid rgba(231,195,91,0.95);
                border-radius: 18px;
                background: transparent;
            }}

            QLabel#cardSuit {{
                font-size: 18px;
                font-weight: 950;
                color: rgba(231,195,91,0.98);
            }}
            QLabel#cardPill {{
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 900;
                color: rgba(255,255,255,0.85);
            }}

            QLabel#cardPreview {{
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
            }}
            QLabel#cardPreviewFallback {{
                font-size: 72px;
                font-weight: 950;
                color: rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
            }}

            /* Darken thumbnail behind hover text */
            QFrame#previewScrim {{
                background: rgba(0,0,0,0.55);
                border-radius: 14px;
            }}

            QLabel#cardDate {{
                font-size: 11px;
                font-weight: 800;
                color: rgba(255,255,255,0.75);
            }}
            QLabel#cardHint {{
                font-size: 10px;
                font-weight: 800;
                color: rgba(255,255,255,0.45);
            }}

            /* High-contrast hover sheet */
            QFrame#hoverSheet {{
                background: rgba(255,255,255,0.88);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 14px;
            }}
            QLabel#hoverTitle {{
                font-size: 13px;
                font-weight: 950;
                color: rgba(0,0,0,0.92);
            }}
            QLabel#hoverType {{
                font-size: 11px;
                font-weight: 900;
                color: rgba(0,0,0,0.70);
            }}
        """)

        self.reload()

    # ---------- helpers ----------
    def _clear_flow(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item:
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()

    def _set_selected(self, file_id: int, stored_name: str, card: FileCard):
        if self._selected_card and self._selected_card is not card:
            self._selected_card.set_selected(False)

        self._selected = (int(file_id), stored_name)
        self._selected_card = card
        self._selected_card.set_selected(True)

    def _selected_file(self) -> Optional[Tuple[int, str]]:
        return self._selected

    def _sorted_rows(self, rows):
        mode = self.cmb_sort.currentText()

        if mode == "Newest":
            return sorted(rows, key=lambda r: _safe_date_key(str(r[4])), reverse=True)
        if mode == "Oldest":
            return sorted(rows, key=lambda r: _safe_date_key(str(r[4])), reverse=False)
        if mode == "Name A–Z":
            return sorted(rows, key=lambda r: str(r[2]).lower())
        if mode == "Name Z–A":
            return sorted(rows, key=lambda r: str(r[2]).lower(), reverse=True)
        if mode == "Category":
            return sorted(rows, key=lambda r: str(r[3]).lower())

        return rows

    # ---------- data ----------
    def reload(self):
        self._selected = None
        if self._selected_card:
            self._selected_card.set_selected(False)
        self._selected_card = None

        selected_cat = self.cmb_cat.currentText()

        # Always load everything from DB first
        rows = self.db.list_files("All")

        # Normalize category names from DB
        rows = [(fid, fn, on, normalize_category(cat), da) for (fid, fn, on, cat, da) in rows]

        # Apply category filter locally
        if selected_cat != "All":
            rows = [r for r in rows if r[3] == selected_cat]

        # Apply sort
        rows = self._sorted_rows(rows)

        self._clear_flow()

        for (file_id, filename, original_name, category, date_added) in rows:
            full_path = self.vault_dir / str(filename)

            c = FileCard(
                file_id=int(file_id),
                stored_name=str(filename),
                title=str(original_name),
                category=str(category),
                date_added=str(date_added),
                full_path=full_path,
                thumb_cache=self._thumb_cache,
            )
            c.clicked.connect(lambda fid, sname, card=c: self._set_selected(fid, sname, card))
            c.doubleClicked.connect(lambda fid, sname: self._open_by_ids(fid, sname))
            self.flow.addWidget(c)

        if not rows:
            empty = QLabel("No files yet. Import your CVs, cover letters, certificates, and applications.")
            empty.setStyleSheet("color: rgba(255,255,255,0.55); font-weight:800; padding: 18px;")
            wrap = QFrame()
            wrap.setStyleSheet(
                "background: rgba(0,0,0,0.10);"
                "border: 1px dashed rgba(255,255,255,0.10);"
                "border-radius: 14px;"
            )
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(14, 14, 14, 14)
            wl.addWidget(empty)
            self.flow.addWidget(wrap)

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import file")
        if not path:
            return

        src = Path(path)
        ext = src.suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        dst = self.vault_dir / stored_name

        cat = self.cmb_cat.currentText()
        if cat == "All":
            cat = infer_category_from_filename(src.name, ext)

        try:
            shutil.copy2(src, dst)
            self.db.add_file(filename=stored_name, original_name=src.name, category=cat)
            self.reload()
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))

    # ---------- actions ----------
    def _open_by_ids(self, file_id: int, stored_name: str):
        full_path = self.vault_dir / stored_name
        if not full_path.exists():
            QMessageBox.warning(self, "Missing file", "This file no longer exists on disk.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))

    def open_selected(self):
        sel = self._selected_file()
        if not sel:
            return
        _file_id, stored_name = sel
        self._open_by_ids(_file_id, stored_name)

    def delete_selected(self):
        sel = self._selected_file()
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
