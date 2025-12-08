# careerbuddy/ui/analytics.py
import tkinter as tk
from typing import Tuple

import customtkinter as ctk
from services.db import CareerDB
from ui.base import BaseCTkFrame
from config.theme import get as theme

KANBAN_COLORS = {
    "To Apply": "#3498db",
    "Applied": "#f39c12",
    "Interviewing": "#9b59b6",
    "Offer": "#27ae60",
    "Rejected": "#e74c3c",
}


class AnalyticsDashboardFrame(BaseCTkFrame):
    """Shows a few high‑level numbers and a simple bar chart."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db

        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("purple"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="📊 Analytics Dashboard",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        self.btn_refresh = ctk.CTkButton(
            hdr,
            text="↻ Refresh",
            width=100,
            fg_color=theme("success"),
            hover_color="#3db389",
            corner_radius=8,
            command=self.refresh,
        )
        self.btn_refresh.pack(side="right", padx=20, pady=12)

        # ----- Stat cards (row of 5) ---------------------------------
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="x", **self.padded())
        for i in range(5):
            self.cards_frame.grid_columnconfigure(i, weight=1, uniform="stats")

        # Create placeholders – we'll fill them in `refresh()`
        self.stat_labels = {}
        keys = [
            ("total", "Total Apps", "📋"),
            ("applied", "Applied", "📤"),
            ("interviewing", "Interviewing", "🎤"),
            ("offers", "Offers", "🎉"),
            ("rejected", "Rejected", "❌"),
        ]
        for col, (key, title, emoji) in enumerate(keys):
            card = ctk.CTkFrame(self.cards_frame, fg_color=theme("bg_medium"), corner_radius=12)
            card.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)

            ctk.CTkLabel(card, text=emoji, font=ctk.CTkFont(size=24)).pack(pady=(10, 4))
            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=13),
                text_color="#888",
            ).pack()
            value_lbl = ctk.CTkLabel(
                card,
                text="0",
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=theme("accent"),
            )
            value_lbl.pack(pady=(4, 12))
            self.stat_labels[key] = value_lbl

        # ----- Simple bar chart (status breakdown) -------------------
        self.chart_frame = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        self.chart_frame.pack(fill="both", expand=True, **self.padded())

        ctk.CTkLabel(
            self.chart_frame,
            text="📈 Status Breakdown",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(10, 5))

        self.bars_container = ctk.CTkFrame(self.chart_frame, fg_color="transparent")
        self.bars_container.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh()   # initial load

    # ------------------------------------------------------------------
    def refresh(self):
        # Gather counts from the DB
        rows = self.db.get_all_jobs()
        total = len(rows)

        # Count per status
        counts = {status: 0 for status in KANBAN_COLORS}
        for _, _, _, status, _, _ in rows:
            if status in counts:
                counts[status] += 1

        # Update stat cards
        self.stat_labels["total"].configure(text=str(total))
        self.stat_labels["applied"].configure(text=str(counts.get("Applied", 0)))
        self.stat_labels["interviewing"].configure(text=str(counts.get("Interviewing", 0)))
        self.stat_labels["offers"].configure(text=str(counts.get("Offer", 0)))
        self.stat_labels["rejected"].configure(text=str(counts.get("Rejected", 0)))

        # ---- Build a very simple vertical bar chart -----------------
        for child in self.bars_container.winfo_children():
            child.destroy()

        max_cnt = max(counts.values()) if counts else 1
        for status, colour in KANBAN_COLORS.items():
            cnt = counts[status]
            bar_height = int((cnt / max_cnt) * 150) if max_cnt else 0

            row = ctk.CTkFrame(self.bars_container, fg_color="transparent")
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(row, text=status, width=100, anchor="w", text_color=theme("text")).pack(side="left")
            bar = ctk.CTkFrame(
                row,
                fg_color=colour,
                width=30,
                height=bar_height,
                corner_radius=4,
            )
            bar.pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(cnt), width=30, anchor="e", text_color=theme("text")).pack(side="right")
