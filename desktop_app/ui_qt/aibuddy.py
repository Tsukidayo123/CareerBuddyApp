# ui_qt/aibuddy.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unicodedata import name

from PySide6.QtCore import Qt, Signal, QThread, QTimer, QEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTextEdit, QScrollArea, QSizePolicy, QComboBox, QMessageBox, QFileDialog
)

from ui_qt.base import palette
from services.ollama_client import OllamaClient
from services.file_extract import extract_text_from_file


# -----------------------------
# Worker thread for streaming
# -----------------------------
class OllamaStreamWorker(QThread):
    token = Signal(str)
    done = Signal(str)         # full_text
    error = Signal(str)

    def __init__(self, client: OllamaClient, model: str, system: str, messages: List[Dict[str, str]]):
        super().__init__()
        self.client = client
        self.model = model
        self.system = system
        self.messages = messages
        self._full = ""

    def run(self):
        try:
            for t in self.client.chat_stream(
                model=self.model,
                system=self.system,
                messages=self.messages,
                options={
                    "temperature": 0.7,
                    "num_ctx": 4096,
                },
            ):
                self._full += t
                self.token.emit(t)
            self.done.emit(self._full)
        except Exception as e:
            self.error.emit(str(e))


# -----------------------------
# Simple message bubble widget
# -----------------------------
class ChatBubble(QFrame):
    def __init__(self, role: str, text: str):
        super().__init__()
        self.setObjectName("bubble")
        self.setProperty("role", role)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr = QLabel("You" if role == "user" else "CareerBuddy AI")
        hdr.setObjectName("bubbleHeader")

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setObjectName("bubbleBody")

        lay.addWidget(hdr)
        lay.addWidget(body)

        from PySide6.QtWidgets import QApplication

        self._body = body  # BEFORE creating the copy button

        from PySide6.QtWidgets import QApplication
        if role != "user":
            btn_copy = QPushButton("Copy")
            btn_copy.setObjectName("copyBtn")
            btn_copy.setFixedHeight(28)
            btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self._body.text()))
            lay.addWidget(btn_copy, alignment=Qt.AlignRight)


        self.style().unpolish(self)
        self.style().polish(self)

    def set_text(self, text: str):
        self._body.setText(text)


@dataclass
class Attachment:
    path: str
    name: str
    label: str     # PDF/DOCX/TEXT/UNKNOWN
    text: str      # extracted
    added_at: str


# -----------------------------
# Main AI Buddy Page
# -----------------------------
class AIBuddyPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        self.client = OllamaClient()
        self.default_model = "deepseek-r1:8b"

        self._conversation_id: Optional[int] = None
        self._assistant_bubble: Optional[ChatBubble] = None
        self._assistant_buffer: str = ""
        self._worker: Optional[OllamaStreamWorker] = None

        self._attachments: List[Attachment] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🤖 AI Buddy")
        title.setStyleSheet("font-size:20px; font-weight:900;")
        header.addWidget(title)

        header.addStretch(1)

        self.lbl_status = QLabel("Checking Ollama…")
        self.lbl_status.setObjectName("aiStatus")

        self.btn_new = QPushButton("New Chat")
        self.btn_new.setObjectName("ghostBtn")
        self.btn_new.setFixedHeight(36)
        self.btn_new.clicked.connect(self.new_chat)

        self.btn_cmds = QPushButton("Commands")
        self.btn_cmds.setObjectName("ghostBtn")
        self.btn_cmds.setFixedHeight(36)
        self.btn_cmds.clicked.connect(self.show_commands_menu)


        self.cmb_model = QComboBox()
        self.cmb_model.setFixedHeight(36)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("ghostBtn")
        btn_refresh.setFixedHeight(36)
        btn_refresh.clicked.connect(self.refresh_models)

        header.addWidget(self.lbl_status)
        header.addWidget(self.btn_new)
        header.addWidget(self.btn_cmds)
        header.addWidget(self.cmb_model)
        header.addWidget(btn_refresh)
        root.addLayout(header)

        # Chat panel
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(
            "background: rgba(255,255,255,0.04);"
            "border: 1px solid rgba(255,255,255,0.08);"
            "border-radius: 16px;"
        )
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(10)

        # Attachment strip
        self.attach_strip = QFrame()
        self.attach_strip.setObjectName("attachStrip")
        asl = QHBoxLayout(self.attach_strip)
        asl.setContentsMargins(10, 8, 10, 8)
        asl.setSpacing(8)

        self.btn_clear_attach = QPushButton("Clear")
        self.btn_clear_attach.setObjectName("ghostBtn")
        self.btn_clear_attach.setFixedHeight(32)
        self.btn_clear_attach.clicked.connect(self.clear_attachments)

        self.attach_row = QHBoxLayout()
        self.attach_row.setContentsMargins(0, 0, 0, 0)
        self.attach_row.setSpacing(8)

        self.attach_row_host = QFrame()
        self.attach_row_host.setObjectName("attachRowHost")
        self.attach_row_host.setLayout(self.attach_row)

        asl.addWidget(self.attach_row_host, 1)
        asl.addWidget(self.btn_clear_attach)

        pl.addWidget(self.attach_strip)

        # Scroll chat
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_host = QWidget()
        self.chat_l = QVBoxLayout(self.chat_host)
        self.chat_l.setContentsMargins(6, 6, 6, 6)
        self.chat_l.setSpacing(10)
        self.chat_l.addStretch(1)

        self.scroll.setWidget(self.chat_host)
        pl.addWidget(self.scroll, 1)

        # Composer
        composer = QFrame()
        composer.setObjectName("composer")
        cl = QHBoxLayout(composer)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.setSpacing(10)

        self.btn_upload = QPushButton("Upload")
        self.btn_upload.setObjectName("ghostBtn")
        self.btn_upload.setFixedHeight(44)
        self.btn_upload.clicked.connect(self.upload_file)

        self.btn_cover = QPushButton("Cover Letter")
        self.btn_cover.setObjectName("ghostBtn")
        self.btn_cover.setFixedHeight(44)
        self.btn_cover.clicked.connect(self.start_cover_letter_mode)
        cl.addWidget(self.btn_cover)

        self.txt = QTextEdit()
        self.txt.setPlaceholderText(
            "Ask CareerBuddy…\n"
            "Tip: /remember <fact>, /memories, /pin <id>, /forget <id>, /new"
        )
        self.txt.setFixedHeight(76)

        self.txt.installEventFilter(self)

        self.btn_send = QPushButton("Send")
        self.btn_send.setFixedHeight(44)
        self.btn_send.setStyleSheet(
            f"background:{palette['accent']}; color:#111; padding:10px 16px; border-radius:12px; font-weight:900;"
        )
        self.btn_send.clicked.connect(self.send)

        cl.addWidget(self.btn_upload)
        cl.addWidget(self.txt, 1)
        cl.addWidget(self.btn_send)
        pl.addWidget(composer)

        root.addWidget(panel, 1)
        

        # Styles
        self.setStyleSheet(f"""
            QLabel {{ color: {palette["text"]}; }}

            QLabel#aiStatus {{
                color: rgba(255,255,255,0.75);
                font-weight: 800;
            }}

            QComboBox {{
                background: #F8F4EC;
                color: #111;
                border-radius: 10px;
                padding: 6px;
                font-weight: 800;
                min-width: 180px;
            }}

            QFrame#attachStrip {{
                background: rgba(0,0,0,0.16);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
            }}
            QLabel#attachLabel {{
                font-weight: 850;
                color: rgba(255,255,255,0.78);
            }}

            QTextEdit {{
                background: rgba(0,0,0,0.18);
                color: {palette["text"]};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 10px;
                font-weight: 700;
            }}

            QFrame#composer {{
                background: rgba(0,0,0,0.14);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }}

            /* Bubble base */
            QFrame#bubble {{
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            QFrame#bubble[role="user"] {{
                background: rgba(255,255,255,0.06);
            }}
            QFrame#bubble[role="assistant"] {{
                background: rgba(0,0,0,0.18);
            }}

            QLabel#bubbleHeader {{
                font-size: 11px;
                font-weight: 950;
                color: rgba(231,195,91,0.95);
            }}
            QLabel#bubbleBody {{
                font-size: 13px;
                font-weight: 750;
                color: rgba(255,255,255,0.92);
            }}

            QPushButton#ghostBtn {{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.14);
                color: rgba(255,255,255,0.92);
                padding: 8px 12px;
                border-radius: 12px;
                font-weight: 900;
            }}
            QPushButton#ghostBtn:hover {{
                background: rgba(255,255,255,0.14);
            }}
            QPushButton#attachChip {{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.16);
                color: rgba(255,255,255,0.92);
                padding: 4px 10px;
                border-radius: 12px;
                font-weight: 900;
            }}

            QPushButton#attachChip:hover {{
                background: rgba(255,255,255,0.14);
            }}

            QPushButton#attachChipX {{
                background: rgba(231,76,60,0.22);
                border: 1px solid rgba(231,76,60,0.38);
                color: rgba(255,255,255,0.92);
                border-radius: 14px;
                font-weight: 950;
            }}

            QPushButton#attachChipX:hover {{
                background: rgba(231,76,60,0.30);
            }}
            QMenu#cmdMenu {{
                background: rgba(0,0,0,0.88);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                padding: 8px;
            }}

            QMenu#cmdMenu::item {{
                padding: 10px 14px;
                border-radius: 10px;
                color: rgba(255,255,255,0.92);
                font-weight: 800;
            }}

            QMenu#cmdMenu::item:selected {{
                background: rgba(231,195,91,0.18);
            }}
            QPushButton#copyBtn {{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.14);
                color: rgba(255,255,255,0.90);
                padding: 6px 10px;
                border-radius: 10px;
                font-weight: 900;
            }}
            QPushButton#copyBtn:hover {{
                background: rgba(255,255,255,0.14);
            }}
        """)

        QTimer.singleShot(0, self._init_chat)

    # ----------------------------
    # Init & load history
    # ----------------------------
    def _init_chat(self):
        self.refresh_models()

        # reuse latest conversation if exists
        convs = self.db.ai_list_conversations(1)
        if convs:
            self._conversation_id = int(convs[0][0])
        else:
            self._conversation_id = int(self.db.ai_create_conversation("AI Buddy"))

        self._load_history()
        self._refresh_attach_label()

        if not self.client.is_running():
            QMessageBox.information(
                self,
                "Ollama not running",
                "CareerBuddy couldn't connect to Ollama.\n\n"
                "Start Ollama, then click Refresh.\n"
                "Ollama should be available at http://localhost:11434",
            )

    def new_chat(self):
        if self._worker and self._worker.isRunning():
            return

        self._conversation_id = int(self.db.ai_create_conversation("AI Buddy"))

        # clear UI bubbles
        while self.chat_l.count() > 1:
            item = self.chat_l.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._add_bubble("assistant", "New chat started. How can I help?")

    def _load_history(self):
        # clear bubbles (leave stretch at end)
        while self.chat_l.count() > 1:
            item = self.chat_l.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._conversation_id:
            return

        rows = self.db.ai_get_messages(self._conversation_id, limit=40)  # (role, content, ts)
        for role, content, _ts in rows:
            self._add_bubble(str(role), str(content))

        self._scroll_to_bottom()

    # ----------------------------
    # Models
    # ----------------------------
    def refresh_models(self):
        if self.client.is_running():
            self.lbl_status.setText("Ollama: Connected")
            try:
                models = self.client.list_models()
            except Exception:
                models = []
        else:
            self.lbl_status.setText("Ollama: Not running")
            models = []

        self.cmb_model.blockSignals(True)
        self.cmb_model.clear()

        if not models:
            self.cmb_model.addItem(self.default_model)
            self.cmb_model.setEnabled(False)
        else:
            self.cmb_model.setEnabled(True)
            # Prefer deepseek if installed
            if self.default_model in models:
                models = [self.default_model] + [m for m in models if m != self.default_model]
            for m in models:
                self.cmb_model.addItem(m)

        self.cmb_model.blockSignals(False)

    # ----------------------------
    # Attachments (CV/JD files)
    # ----------------------------
    def upload_file(self):
        if self._worker and self._worker.isRunning():
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload CV / Job Description",
            "",
            "Documents (*.pdf *.docx *.txt *.md *.csv *.log *.rtf);;All Files (*.*)",
        )
        if not path:
            return

        label, text = extract_text_from_file(path, max_chars=25_000)
        name = Path(path).name

        if not text:
            QMessageBox.information(
                self,
                "Could not read file",
                f"I couldn't extract text from:\n\n{name}\n\n"
                f"Type detected: {label}\n\n"
                "PDF text extraction requires PyMuPDF (fitz).\n"
                "DOCX extraction requires python-docx.\n\n"
                "You can still paste the text manually if needed.",
            )

        att = Attachment(
            path=path,
            name=name,
            label=label,
            text=text,
            added_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        self._attachments.append(att)
        self._refresh_attach_label()

        # tiny confirmation bubble
        self._add_bubble("assistant", f"Attached: {name} ({label})")
        self._scroll_to_bottom()

    def clear_attachments(self):
        self._attachments.clear()
        self._refresh_attach_label()

    def remove_attachment(self, index: int):
        if 0 <= index < len(self._attachments):
            self._attachments.pop(index)
        self._refresh_attach_label()

    def _refresh_attach_label(self):
        # Clear current chips
        while self.attach_row.count():
            item = self.attach_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._attachments:
            lbl = QLabel("Attachments: none")
            lbl.setObjectName("attachLabel")
            self.attach_row.addWidget(lbl)
            self.attach_row.addStretch(1)
            return

        for idx, a in enumerate(self._attachments):
            chip = QPushButton(a.name)
            chip.setObjectName("attachChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFixedHeight(28)

            btn_x = QPushButton("✕")
            btn_x.setObjectName("attachChipX")
            btn_x.setCursor(Qt.PointingHandCursor)
            btn_x.setFixedSize(28, 28)

            wrap = QFrame()
            wrap.setObjectName("attachChipWrap")
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(8, 0, 6, 0)
            wl.setSpacing(6)
            wl.addWidget(chip)
            wl.addWidget(btn_x)

            btn_x.clicked.connect(lambda _=None, i=idx: self.remove_attachment(i))

            self.attach_row.addWidget(wrap)

        self.attach_row.addStretch(1)

    def _attachments_context(self) -> str:
        if not self._attachments:
            return ""

        lines = []
        lines.append("Attached documents below are available to you as text. Use them directly as ground truth.")
        for a in self._attachments[-3:]:  # keep prompt light
            if a.text.strip():
                lines.append(f"\n--- {a.name} ({a.label}) ---\n{a.text.strip()}")
            else:
                lines.append(f"\n--- {a.name} ({a.label}) ---\n[No extracted text available]")
        return "\n".join(lines).strip()

    # ----------------------------
    # Chat UI helpers
    # ----------------------------
    def _add_bubble(self, role: str, text: str) -> ChatBubble:
        b = ChatBubble(role, text)
        self.chat_l.insertWidget(self.chat_l.count() - 1, b)
        return b

    def _scroll_to_bottom(self, force: bool = False):
        if not force and not self._should_autoscroll():
            return
        QTimer.singleShot(
            0,
            lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        )

    # ----------------------------
    # Memory + App Context
    # ----------------------------
    def _memory_context(self, user_text: str) -> str:
        # pinned memories
        pinned = self.db.ai_list_memories(pinned_first=True, limit=50)
        # relevant memories by keyword match
        relevant = self.db.ai_search_memories(user_text, limit=20) if user_text.strip() else []

        pinned_lines = []
        for mid, _ts, mem_type, content, _imp, pinned_flag in pinned:
            if int(pinned_flag) == 1:
                pinned_lines.append(f"- [#{mid}] ({mem_type}) {content}")

        rel_lines = []
        # avoid duplicating pinned items
        pinned_ids = {int(m[0]) for m in pinned if int(m[5]) == 1}
        for mid, _ts, mem_type, content, _imp, _p in relevant:
            if int(mid) in pinned_ids:
                continue
            rel_lines.append(f"- [#{mid}] ({mem_type}) {content}")

        if not pinned_lines and not rel_lines:
            return ""

        lines = []
        lines.append("User memory context:")
        if pinned_lines:
            lines.append("\nPinned:")
            lines.extend(pinned_lines)
        if rel_lines:
            lines.append("\nRelevant:")
            lines.extend(rel_lines)

        return "\n".join(lines).strip()

    def _app_context(self) -> str:
        # Lightweight read-only context. This makes it feel integrated.
        lines = []
        lines.append("CareerBuddy app context (read-only):")

        # Jobs
        try:
            jobs = self.db.get_all_jobs()[:10]
        except Exception:
            jobs = []

        if jobs:
            lines.append("\nRecent job applications:")
            for jid, company, role, status, notes, date_added in jobs:
                company = company or ""
                role = role or ""
                status = status or ""
                date_added = date_added or ""
                lines.append(f"- #{jid}: {company} — {role} ({status}) added {date_added}")
        else:
            lines.append("\nRecent job applications: none")

        # Reminders (next 7 days)
        rem_lines = []
        try:
            today = datetime.now().date()
            for i in range(0, 7):
                d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
                rs = self.db.list_reminders_for_date(d)
                for rid, title, desc, date, time, category in rs:
                    rem_lines.append(f"- {date} {time} — {title} [{category}]")
        except Exception:
            rem_lines = []

        if rem_lines:
            lines.append("\nUpcoming reminders (7 days):")
            lines.extend(rem_lines[:12])
        else:
            lines.append("\nUpcoming reminders (7 days): none")

        # Files
        try:
            files = self.db.list_files("All")[:10]
        except Exception:
            files = []

        if files:
            lines.append("\nRecent File Vault items:")
            for fid, filename, original_name, category, date_added in files:
                lines.append(f"- #{fid}: {original_name} [{category}] added {date_added}")
        else:
            lines.append("\nRecent File Vault items: none")

        return "\n".join(lines).strip()

    # ----------------------------
    # System prompt
    # ----------------------------
    def _system_prompt(self) -> str:
        return (
            "You are CareerBuddy AI, a helpful career assistant inside a desktop app.\n"
            "Style rules:\n"
            "- Be concise and practical.\n"
            "- Ask only for missing info.\n"
            "- Use user memory + app context when relevant.\n"
            "- Do NOT invent facts from the CV; only use what the user provided.\n\n"
            "- Do not use Markdown formatting.\n"
            "- Do not use asterisks (*), double asterisks (**), underscores, or bullet symbols like • unless the user asks.\n"
            "- Write in plain text with normal paragraphs.\n"
            "Attachment behavior:\n"
            "- If attachments are present, you DO have access to their extracted text inside this chat.\n"
            "- Never claim you cannot access the uploaded file if it was attached in this session.\n"
            "- If attachment text is empty (e.g. scanned PDF), say you couldn't extract text and ask user to paste it.\n\n"
            "Cover letter behavior:\n"
            "- If the user asks for a cover letter or CV summary, use attached CV/JD text first.\n"
            "- If only CV is attached, ask for job description.\n"
            "- If only JD is attached, ask for CV.\n"

        )

    # ----------------------------
    # Message building (history + memory + context + attachments)
    # ----------------------------
    def _build_messages(self, user_text: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = []

        # 1) app context
        app_ctx = self._app_context()
        if app_ctx:
            msgs.append({"role": "system", "content": app_ctx})

        # 2) memory context
        mem_ctx = self._memory_context(user_text)
        if mem_ctx:
            msgs.append({"role": "system", "content": mem_ctx})

        # 3) attachments context (CV/JD)
        att_ctx = self._attachments_context()
        if att_ctx:
            msgs.append({"role": "system", "content": att_ctx})

        # 4) short recent history
        if self._conversation_id:
            rows = self.db.ai_get_messages(self._conversation_id, limit=16)
            for role, content, _ts in rows:
                r = str(role)
                if r not in ("user", "assistant"):
                    continue
                msgs.append({"role": r, "content": str(content)})

        # 5) current message
        msgs.append({"role": "user", "content": user_text})
        return msgs

    # ----------------------------
    # Slash commands (memory control)
    # ----------------------------
    def _handle_command(self, text: str) -> bool:
        t = text.strip()
        if not t.startswith("/"):
            return False

        parts = t.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ("/new", "/reset"):
            self.new_chat()
            return True

        if cmd in ("/memories", "/memory"):
            mems = self.db.ai_list_memories(pinned_first=True, limit=50)
            if not mems:
                self._add_bubble("assistant", "No memories saved yet.\nUse: /remember <text>")
                return True

            lines = ["Saved memories (use /pin <id>, /unpin <id>, /forget <id>):"]
            for mid, _ts, mem_type, content, imp, pinned in mems:
                pin = "📌" if int(pinned) == 1 else " "
                lines.append(f"{pin} #{mid} ({mem_type}, imp={imp}) — {content}")
            self._add_bubble("assistant", "\n".join(lines))
            self._scroll_to_bottom()
            return True

        if cmd == "/remember":
            if len(parts) < 2:
                self._add_bubble("assistant", "Usage: /remember <something to remember>")
                return True
            content = t[len("/remember"):].strip()
            self.db.ai_add_memory("fact", content, importance=6, pinned=0)
            self._add_bubble("assistant", f"Saved memory ✅\n\n“{content}”\n\nTip: /pin <id> to keep it always included.")
            self._scroll_to_bottom()
            return True

        if cmd == "/pin":
            if len(parts) < 2:
                self._add_bubble("assistant", "Usage: /pin <memory_id>")
                return True
            try:
                mid = int(parts[1])
                self.db.ai_set_memory_pinned(mid, 1)
                self._add_bubble("assistant", f"Pinned memory #{mid} 📌")
            except Exception:
                self._add_bubble("assistant", "Could not pin that memory id.")
            self._scroll_to_bottom()
            return True

        if cmd == "/unpin":
            if len(parts) < 2:
                self._add_bubble("assistant", "Usage: /unpin <memory_id>")
                return True
            try:
                mid = int(parts[1])
                self.db.ai_set_memory_pinned(mid, 0)
                self._add_bubble("assistant", f"Unpinned memory #{mid}")
            except Exception:
                self._add_bubble("assistant", "Could not unpin that memory id.")
            self._scroll_to_bottom()
            return True

        if cmd in ("/forget", "/delete_memory"):
            if len(parts) < 2:
                self._add_bubble("assistant", "Usage: /forget <memory_id>")
                return True
            try:
                mid = int(parts[1])
                self.db.ai_delete_memory(mid)
                self._add_bubble("assistant", f"Deleted memory #{mid}")
            except Exception:
                self._add_bubble("assistant", "Could not delete that memory id.")
            self._scroll_to_bottom()
            return True

        # unknown command
        self._add_bubble(
            "assistant",
            "Unknown command.\n\n"
            "Commands:\n"
            "- /remember <text>\n"
            "- /memories\n"
            "- /pin <id>\n"
            "- /unpin <id>\n"
            "- /forget <id>\n"
            "- /new",
        )
        self._scroll_to_bottom()
        return True

    # ----------------------------
    # Send + streaming
    # ----------------------------
    def send(self):
        if self._worker and self._worker.isRunning():
            return

        text = self.txt.toPlainText().strip()
        if not text:
            return

        # commands first
        if self._handle_command(text):
            self.txt.clear()
            return
        
        # If user asks about CV and none attached, auto-load from File Vault
        if ("cv" in text.lower() or "resume" in text.lower()) and not self._attachments:
            self.attach_cv_from_vault()


        if not self._conversation_id:
            self._conversation_id = int(self.db.ai_create_conversation("AI Buddy"))

        # Save user message
        self.db.ai_add_message(self._conversation_id, "user", text)

        # Add bubbles
        self._add_bubble("user", text)
        self._assistant_buffer = ""
        self._assistant_bubble = self._add_bubble("assistant", "…")
        self._scroll_to_bottom()

        self.txt.clear()
        self.btn_send.setEnabled(False)
        self.btn_upload.setEnabled(False)

        model = self.cmb_model.currentText().strip() or self.default_model
        system = self._system_prompt()
        messages = self._build_messages(text)

        self._worker = OllamaStreamWorker(self.client, model=model, system=system, messages=messages)
        self._worker.token.connect(self._on_token)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_token(self, t: str):
        self._assistant_buffer += t
        if self._assistant_bubble:
            self._assistant_bubble.set_text(self._clean_ai_text(self._assistant_buffer))
        self._scroll_to_bottom(force=False)


    def _clean_ai_text(self, s: str) -> str:
        s = (s or "")
        # remove common markdown emphasis
        s = s.replace("**", "")
        s = s.replace("__", "")
        s = s.replace("*", "")
        s = s.replace("`", "")
        return s


    def _on_done(self, full_text: str):
        self.btn_send.setEnabled(True)
        self.btn_upload.setEnabled(True)

        final = self._clean_ai_text((full_text or "").strip()) or "…"
        if self._assistant_bubble:
            self._assistant_bubble.set_text(final)

        if self._conversation_id:
            self.db.ai_add_message(self._conversation_id, "assistant", final)

        self._scroll_to_bottom()

    def _on_error(self, msg: str):
        self.btn_send.setEnabled(True)
        self.btn_upload.setEnabled(True)

        if self._assistant_bubble:
            self._assistant_bubble.set_text(f"⚠️ Ollama error:\n{msg}")
        self._scroll_to_bottom()

    def start_cover_letter_mode(self):
        if not any(a.label in ("PDF", "DOCX", "TEXT") and a.text.strip() for a in self._attachments):
            self._add_bubble("assistant", "Upload your CV first (PDF/DOCX/TXT), then click Cover Letter again.")
            self._scroll_to_bottom()
            return

        self._add_bubble("assistant",
            "Cover Letter Mode ✅\n\n"
            "1) Paste the job description in your next message.\n"
            "2) I’ll generate a tailored cover letter using your uploaded CV.\n\n"
            "Tip: include company name + role title if possible."
        )
        self._scroll_to_bottom()

    def _vault_find_best_cv(self) -> Optional[Tuple[int, str, str, str, str]]:
        """
        Returns best match from DB: (file_id, filename, original_name, category, date_added)
        """
        rows = self.db.list_files("All")
        if not rows:
            return None

        # Prefer category = CV first
        cvs = [r for r in rows if str(r[3]).strip().lower() in ("cv", "cv/resume", "resume")]
        if cvs:
            # newest first by date_added
            return sorted(cvs, key=lambda r: str(r[4]), reverse=True)[0]

        # fallback: keyword search in original name
        keywords = ("cv", "resume", "résumé")
        for r in rows:
            name = str(r[2]).lower()
            if any(k in name for k in keywords):
                return r  # full (id, filename, original_name, category, date_added)

        return None

    def attach_cv_from_vault(self) -> bool:
        best = self._vault_find_best_cv()
        if not best:
            self._add_bubble("assistant", "I couldn't find a CV in your File Vault. Upload one first.")
            self._scroll_to_bottom()
            return False

        file_id, stored_name, original_name, category, _date_added = best
        full_path = Path(self.db.db_path).resolve().parents[1] / "career_buddy_files" / str(stored_name)

        label, text = extract_text_from_file(str(full_path), max_chars=25_000)

        if not text.strip():
            self._add_bubble(
                "assistant",
                f"I found your CV in File Vault: {original_name}, but I couldn't extract text from it.\n"
                "Try uploading a text-based PDF/DOCX, or paste your CV text here."
            )
            self._scroll_to_bottom()
            return False

        att = Attachment(
            path=str(full_path),
            name=str(original_name),
            label=label,
            text=text,
            added_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        self._attachments.append(att)
        self._refresh_attach_label()

        self._add_bubble("assistant", f"Loaded from File Vault ✅ {original_name} ({label})")
        self._scroll_to_bottom()
        return True

    def show_commands_menu(self):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setObjectName("cmdMenu")

        items = [
            ("🧠 /remember <text>", "Store a long-term memory.\nExample: /remember My name is Ilham"),
            ("📌 /pin <message_id>", "Pin a specific assistant/user message.\nExample: /pin 3"),
            ("🧹 /forget <key/phrase>", "Remove a memory.\nExample: /forget my name"),
            ("🗂 /usevault <query>", "Load a file from File Vault into attachments.\nExample: /usevault cv"),
            ("📎 /attachclear", "Clear all attachments.\nExample: /attachclear"),
            ("🆕 /new", "Start a new chat.\nExample: /new"),
            ("❓ /help", "Show this help menu.\nExample: /help"),
        ]

        for title, tip in items:
            act = QAction(title, self)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, t=title: self._insert_command(t))
            menu.addAction(act)

        menu.popup(self.btn_cmds.mapToGlobal(self.btn_cmds.rect().bottomLeft()))

    def _insert_command(self, cmd_label: str):
        cmd = cmd_label.split(" ", 1)[1] if " " in cmd_label else cmd_label
        self.txt.setPlainText(cmd + " ")
        self.txt.setFocus()
        c = self.txt.textCursor()
        c.movePosition(QTextCursor.End)
        self.txt.setTextCursor(c)

    def _should_autoscroll(self) -> bool:
        sb = self.scroll.verticalScrollBar()
        # if user is within 60px of bottom, keep auto-scrolling
        return (sb.maximum() - sb.value()) <= 60

    def eventFilter(self, obj, event):
        if obj is self.txt and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False  # newline
                self.send()
                return True
        return super().eventFilter(obj, event)


