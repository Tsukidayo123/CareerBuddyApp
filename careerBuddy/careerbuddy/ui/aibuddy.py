# careerbuddy/ui/aibuddy.py
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from careerbuddy.services.gemini import LLMClient
from careerbuddy.ui.base import BaseCTkFrame
from careerbuddy.config.theme import get as theme


class AIBuddyFrame(BaseCTkFrame):
    """Chat UI that talks to Gemini (or local Ollama if no API key)."""
    def __init__(self, master):
        super().__init__(master)
        self.llm = LLMClient()
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=theme("purple"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🤖 AI Career Buddy",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=20, pady=15)

        self.status_lbl = ctk.CTkLabel(
            hdr,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#ddd",
        )
        self.status_lbl.pack(side="right", padx=20, pady=15)

        # Chat display (read‑only)
        self.chat_disp = ctk.CTkTextbox(
            self,
            font=("Segoe UI", 12),
            wrap="word",
            fg_color="#1e1e2e",
            text_color=theme("text"),
            state="disabled",
            corner_radius=8,
        )
        self.chat_disp.pack(fill="both", expand=True, **self.padded())

        # Input line
        entry_frame = ctk.CTkFrame(self, fg_color=theme("bg_medium"), height=50, corner_radius=12)
        entry_frame.pack(fill="x", **self.padded())
        entry_frame.pack_propagate(False)

        self.entry = ctk.CTkEntry(entry_frame, placeholder_text="Ask a career‑related question...", height=38)
        self.entry.pack(side="left", fill="x", expand=True, padx=10, pady=6)
        self.entry.bind("<Return>", lambda e: self._send())

        send_btn = ctk.CTkButton(
            entry_frame,
            text="Send →",
            fg_color=theme("purple"),
            hover_color=theme("purple_hover"),
            width=80,
            corner_radius=8,
            command=self._send,
        )
        send_btn.pack(side="right", padx=10, pady=6)

        # Welcome / fallback message
        if self.llm._use_gemini:
            self._append("Buddy", "👋 Hi! I'm CareerBuddy, your AI career advisor! Ask me anything about resumes, interviews, job search, etc.")
        else:
            self._append(
                "System",
                "⚡ Running locally with Ollama (model phi:2.7b). No API key required.",
            )

    # ------------------------------------------------------------------
    def _append(self, speaker: str, msg: str):
        self.chat_disp.configure(state="normal")
        prefix = "🤖 " if speaker == "Buddy" else ("🧑 " if speaker == "You" else "")
        self.chat_disp.insert("end", f"{prefix}[{speaker}]: {msg}\n\n")
        self.chat_disp.configure(state="disabled")
        self.chat_disp.see("end")

    # ------------------------------------------------------------------
    def _send(self):
        user_msg = self.entry.get().strip()
        if not user_msg:
            return
        self.entry.delete(0, "end")
        self._append("You", user_msg)
        self.status_lbl.configure(text="Thinking…")
        self.after(10, lambda: threading.Thread(target=self._query_ai, args=(user_msg,), daemon=True).start())

    # ------------------------------------------------------------------
    def _query_ai(self, prompt: str):
        try:
            reply = self.llm.generate(prompt, max_tokens=400, temperature=0.7)
            self.after(0, lambda: self._display_reply(reply))
        except Exception as exc:
            self.after(0, lambda: self._display_error(str(exc)))

    # ------------------------------------------------------------------
    def _display_reply(self, text: str):
        self._append("Buddy", text)
        self.status_lbl.configure(text="")

    def _display_error(self, err: str):
        # Show the error in the chat window – makes debugging obvious
        self._append("System", f"❗ {err}")
        self.status_lbl.configure(text="Error")
