# ui_qt/cover_letter.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QComboBox
)

from ui_qt.base import palette


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _read_docx(path: str) -> str:
    # optional; works if python-docx is installed
    try:
        import docx  # type: ignore
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return ""


def _read_pdf(path: str) -> str:
    # optional; works if pdfminer.six is installed
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        return extract_text(path) or ""
    except Exception:
        return ""


def load_cv_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return _read_text_file(path)
    if ext == ".docx":
        return _read_docx(path)
    if ext == ".pdf":
        return _read_pdf(path)
    return ""


def normalize_spaces(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_keywords(text: str) -> List[str]:
    text = text.lower()
    # pull “skill-like” words; keep it simple and predictable
    raw = re.findall(r"[a-z][a-z\+\#\-]{2,}", text)
    stop = {
        "the","and","with","that","this","from","your","you","for","are","our","role",
        "will","have","has","was","were","into","over","within","using","use","used",
        "able","work","team","teams","skills","skill","experience","experiences",
        "job","company","position","developer","engineer","data"
    }
    out = []
    for w in raw:
        if w in stop:
            continue
        if len(w) > 22:
            continue
        out.append(w)
    # de-dup preserving order
    seen = set()
    uniq = []
    for w in out:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq[:60]


def score_matches(cv_text: str, job_text: str) -> List[Tuple[str, int]]:
    cv = cv_text.lower()
    keys = extract_keywords(job_text)
    scored = []
    for k in keys:
        # small boost if keyword exists in CV
        scored.append((k, 2 if k in cv else 0))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def generate_cover_letter(
    your_name: str,
    email: str,
    phone: str,
    job_title: str,
    company: str,
    location: str,
    job_link: str,
    job_desc: str,
    cv_text: str,
    tone: str,
) -> str:
    today = datetime.now().strftime("%d %B %Y")
    cv_text = normalize_spaces(cv_text)
    job_desc = normalize_spaces(job_desc)

    matches = score_matches(cv_text, job_desc)
    present = [k for k, s in matches if s > 0][:10]
    missing = [k for k, s in matches if s == 0][:6]

    # “evidence” bullets: try to pull 2–3 strong CV lines
    cv_lines = [ln.strip() for ln in cv_text.split("\n") if ln.strip()]
    strong = [ln for ln in cv_lines if any(x in ln.lower() for x in ("built", "developed", "designed", "led", "implemented", "deployed", "improved", "reduced", "increased", "achieved"))]
    strong = strong[:3]

    if tone == "Confident":
        opener = f"I’m excited to apply for the {job_title} role at {company}."
    elif tone == "Friendly":
        opener = f"I’d love to be considered for the {job_title} position at {company}."
    else:
        opener = f"I’m writing to apply for the {job_title} role at {company}."

    keyword_line = ""
    if present:
        keyword_line = "In particular, I’m well aligned with your needs around " + ", ".join(present[:6]) + "."

    gap_line = ""
    if missing:
        gap_line = "I’m also keen to deepen my knowledge in " + ", ".join(missing[:3]) + " as part of the role."

    evidence = ""
    if strong:
        evidence = "\n".join([f"• {ln}" for ln in strong])
    else:
        evidence = "• Built and delivered multiple projects end-to-end, focusing on clean UX and reliable data handling.\n• Comfortable owning features from UI through persistence/testing, and iterating quickly based on feedback."

    loc_line = f"Location: {location}\n" if location else ""
    link_line = f"Job link: {job_link}\n" if job_link else ""

    letter = f"""\
{your_name}
{email} | {phone}
{loc_line}{link_line}
{today}

Hiring Manager
{company}

Dear Hiring Manager,

{opener} {keyword_line}

From my CV, here are a few highlights that map closely to what you’re looking for:
{evidence}

What attracts me to {company} is the chance to contribute to a team that values quality and ownership. {gap_line}

I’d welcome the opportunity to discuss how I can contribute as a {job_title}. Thank you for your time and consideration.

Kind regards,
{your_name}
"""
    return normalize_spaces(letter)


class CoverLetterPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("panel")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 12, 14, 12)

        title = QLabel("✉️ Cover Letter Generator")
        title.setStyleSheet("font-size:20px; font-weight:900; color:white;")
        hl.addWidget(title)
        hl.addStretch(1)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setObjectName("accentBtn")
        hl.addWidget(self.btn_generate)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setObjectName("ghostBtn")
        hl.addWidget(self.btn_copy)

        root.addWidget(header)

        # Inputs row
        form = QFrame()
        form.setObjectName("panel")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(14, 12, 14, 12)
        fl.setSpacing(10)

        row1 = QHBoxLayout()
        self.ent_name = QLineEdit(); self.ent_name.setPlaceholderText("Your name")
        self.ent_email = QLineEdit(); self.ent_email.setPlaceholderText("Email")
        self.ent_phone = QLineEdit(); self.ent_phone.setPlaceholderText("Phone")
        row1.addWidget(self.ent_name, 2)
        row1.addWidget(self.ent_email, 2)
        row1.addWidget(self.ent_phone, 1)
        fl.addLayout(row1)

        row2 = QHBoxLayout()
        self.ent_role = QLineEdit(); self.ent_role.setPlaceholderText("Job title (e.g., Software Engineer Intern)")
        self.ent_company = QLineEdit(); self.ent_company.setPlaceholderText("Company")
        self.ent_location = QLineEdit(); self.ent_location.setPlaceholderText("Location (optional)")
        row2.addWidget(self.ent_role, 2)
        row2.addWidget(self.ent_company, 2)
        row2.addWidget(self.ent_location, 1)
        fl.addLayout(row2)

        row3 = QHBoxLayout()
        self.ent_link = QLineEdit(); self.ent_link.setPlaceholderText("Job link (optional)")
        self.cmb_tone = QComboBox()
        self.cmb_tone.addItems(["Professional", "Confident", "Friendly"])
        row3.addWidget(self.ent_link, 3)
        row3.addWidget(QLabel("Tone:"), 0)
        row3.addWidget(self.cmb_tone, 1)
        fl.addLayout(row3)

        root.addWidget(form)

        # CV + Job Description + Output
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Left: CV
        cv_box = QFrame(); cv_box.setObjectName("panel")
        cv_l = QVBoxLayout(cv_box); cv_l.setContentsMargins(14, 12, 14, 12); cv_l.setSpacing(8)

        cv_title = QLabel("📄 Your CV (upload or paste)")
        cv_title.setStyleSheet("font-weight:900; color:white;")
        cv_l.addWidget(cv_title)

        cv_btn_row = QHBoxLayout()
        self.btn_upload_cv = QPushButton("Upload CV")
        self.btn_upload_cv.setObjectName("ghostBtn")
        self.lbl_cv_path = QLabel("No file selected")
        self.lbl_cv_path.setStyleSheet(f"color:{palette['muted']}; font-weight:700;")
        cv_btn_row.addWidget(self.btn_upload_cv)
        cv_btn_row.addWidget(self.lbl_cv_path, 1)
        cv_l.addLayout(cv_btn_row)

        self.txt_cv = QTextEdit()
        self.txt_cv.setPlaceholderText("Paste your CV text here (works offline).")
        cv_l.addWidget(self.txt_cv, 1)

        # Middle: Job description
        jd_box = QFrame(); jd_box.setObjectName("panel")
        jd_l = QVBoxLayout(jd_box); jd_l.setContentsMargins(14, 12, 14, 12); jd_l.setSpacing(8)

        jd_title = QLabel("🧾 Job description / requirements")
        jd_title.setStyleSheet("font-weight:900; color:white;")
        jd_l.addWidget(jd_title)

        self.txt_job = QTextEdit()
        self.txt_job.setPlaceholderText("Paste the job description here.")
        jd_l.addWidget(self.txt_job, 1)

        # Right: Output
        out_box = QFrame(); out_box.setObjectName("panel")
        out_l = QVBoxLayout(out_box); out_l.setContentsMargins(14, 12, 14, 12); out_l.setSpacing(8)

        out_title = QLabel("📝 Generated cover letter")
        out_title.setStyleSheet("font-weight:900; color:white;")
        out_l.addWidget(out_title)

        self.txt_out = QTextEdit()
        self.txt_out.setPlaceholderText("Click Generate…")
        out_l.addWidget(self.txt_out, 1)

        mid.addWidget(cv_box, 1)
        mid.addWidget(jd_box, 1)
        mid.addWidget(out_box, 1)

        root.addLayout(mid, 1)

        # Wiring
        self.btn_upload_cv.clicked.connect(self._upload_cv)
        self.btn_generate.clicked.connect(self._generate)
        self.btn_copy.clicked.connect(self._copy)

        # Styling
        self.setStyleSheet(f"""
            QFrame#panel {{
                background: {palette["panel"]};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
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
            QPushButton#accentBtn:hover {{
                background: {palette["accent_hover"]};
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

    def _upload_cv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV file",
            "",
            "Documents (*.pdf *.docx *.txt *.md);;All Files (*.*)",
        )
        if not path:
            return

        self.lbl_cv_path.setText(os.path.basename(path))
        text = load_cv_text(path)
        if not text.strip():
            QMessageBox.information(
                self,
                "Couldn’t read file",
                "I couldn’t extract text from that file type on your setup.\n\nTip: export your CV as .txt or paste the CV text into the box.",
            )
            return
        self.txt_cv.setPlainText(text)

    def _generate(self):
        name = self.ent_name.text().strip() or "Your Name"
        email = self.ent_email.text().strip() or "you@email.com"
        phone = self.ent_phone.text().strip() or "07xxx xxx xxx"
        role = self.ent_role.text().strip()
        company = self.ent_company.text().strip()
        location = self.ent_location.text().strip()
        link = self.ent_link.text().strip()
        tone = self.cmb_tone.currentText()

        if not role or not company:
            QMessageBox.warning(self, "Missing", "Please enter Job title and Company.")
            return

        cv_text = self.txt_cv.toPlainText().strip()
        job_text = self.txt_job.toPlainText().strip()

        if len(cv_text) < 80:
            QMessageBox.warning(self, "Missing CV", "Please upload/paste your CV text first.")
            return
        if len(job_text) < 80:
            QMessageBox.warning(self, "Missing Job Description", "Please paste the job description.")
            return

        out = generate_cover_letter(
            your_name=name,
            email=email,
            phone=phone,
            job_title=role,
            company=company,
            location=location,
            job_link=link,
            job_desc=job_text,
            cv_text=cv_text,
            tone=tone,
        )
        self.txt_out.setPlainText(out)

    def _copy(self):
        txt = self.txt_out.toPlainText().strip()
        if not txt:
            return
        QApplication = self.window().windowHandle().screen().context().instance()  # no-op safe fallback
        # Proper clipboard:
        from PySide6.QtWidgets import QApplication as QApp
        QApp.clipboard().setText(txt)
