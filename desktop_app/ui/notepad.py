# careerbuddy/ui/notepad.py
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from services.db import CareerDB
from ui.base import BaseCTkFrame
from config.theme import get as theme


class NotepadFrame(BaseCTkFrame):
    """A simple multi‑line notepad that persists to the DB."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db
        self._setup_ui()
        self._load_content()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="📝 Quick Notes",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        self.btn_save = ctk.CTkButton(
            hdr,
            text="💾 Save",
            fg_color=theme("success"),
            hover_color="#3db389",
            corner_radius=8,
            command=self._save,
        )
        self.btn_save.pack(side="right", padx=20, pady=12)

        # Text area
        txt_container = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        txt_container.pack(fill="both", expand=True, **self.padded())

        self.textbox = ctk.CTkTextbox(
            txt_container,
            font=("Consolas", 14),
            wrap="word",
            fg_color="#1e1e2e",
            text_color=theme("text"),
            corner_radius=8,
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)

    # ------------------------------------------------------------------
    def _load_content(self):
        content = self.db.load_notes()
        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", content)

    # ------------------------------------------------------------------
    def _save(self):
        txt = self.textbox.get("0.0", "end")
        self.db.save_notes(txt)
        self.btn_save.configure(fg_color="#2ecc71", text="✓ Saved!")
        self.after(1500, lambda: self.btn_save.configure(fg_color=theme("success"), text="💾 Save"))
