# careerbuddy/ui/calendar.py
import datetime
import calendar
import tkinter as tk
from tkinter import messagebox
import threading

import customtkinter as ctk
from services.db import CareerDB
from services.notifier import notify_user
from ui.base import BaseCTkFrame
from config.theme import get as theme


class CalendarFrame(BaseCTkFrame):
    """Calendar with reminders for job‑related events."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db
        self.current_date = datetime.date.today()
        self.selected_date: datetime.date | None = None

        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="📅 Calendar & Reminders",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        # Add reminder button
        self.btn_add = ctk.CTkButton(
            hdr,
            text="+ Add Reminder",
            fg_color=theme("success"),
            hover_color="#3db389",
            corner_radius=8,
            command=self._open_add_dialog,
        )
        self.btn_add.pack(side="right", padx=20, pady=12)

        # Main container (grid: calendar on left, reminders on right)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, **self.padded())
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # ----- Calendar side -------------------------------------------
        self.cal_frame = ctk.CTkFrame(main, fg_color=theme("bg_medium"), corner_radius=12)
        self.cal_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

        # Navigation (prev / month / next / today)
        nav = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        nav.pack(fill="x", padx=15, pady=15)

        self.btn_prev = ctk.CTkButton(
            nav, text="◀", width=40, height=35,
            fg_color=theme("secondary"),
            hover_color="#1a4a7a",
            corner_radius=8,
            command=self._prev_month,
        )
        self.btn_prev.pack(side="left")

        self.month_lbl = ctk.CTkLabel(
            nav,
            text=self.current_date.strftime("%B %Y"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        )
        self.month_lbl.pack(side="left", expand=True)

        self.btn_next = ctk.CTkButton(
            nav, text="▶", width=40, height=35,
            fg_color=theme("secondary"),
            hover_color="#1a4a7a",
            corner_radius=8,
            command=self._next_month,
        )
        self.btn_next.pack(side="right")

        # Today button
        self.btn_today = ctk.CTkButton(
            nav, text="Today", width=80, height=35,
            fg_color=theme("accent"),
            hover_color=theme("accent_hover"),
            corner_radius=8,
            command=self._go_to_today,
        )
        self.btn_today.pack(side="right", padx=10)

        # Days header (Mon…Sun)
        days_hdr = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        days_hdr.pack(fill="x", padx=15)
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            ctk.CTkLabel(
                days_hdr, text=d, width=50,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#888",
            ).pack(side="left", expand=True)

        # Calendar grid – will be rebuilt on each month change
        self.grid_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        # ----- Reminders side -----------------------------------------
        self.reminder_box = ctk.CTkScrollableFrame(
            main, fg_color=theme("bg_medium"), corner_radius=12,
            scrollbar_button_color="#444",
            scrollbar_button_hover_color="#555",
        )
        self.reminder_box.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        ctk.CTkLabel(
            self.reminder_box,
            text="📋 Upcoming Reminders",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(15, 10))

        self.reminders_scroll = ctk.CTkScrollableFrame(
            self.reminder_box,
            fg_color="transparent",
            scrollbar_button_color="#444",
        )
        self.reminders_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        # Build the UI for the first month and load reminders
        self._build_calendar()
        self._load_upcoming_reminders()

        # Start background reminder checker (runs every minute)
        self.after(60_000, self._check_due_reminders)

    # ------------------------------------------------------------------
    def _build_calendar(self):
        """Redraw the whole month – called after any navigation change."""
        # Clear previous day buttons
        for child in self.grid_frame.winfo_children():
            child.destroy()

        # Update month label
        self.month_lbl.configure(text=self.current_date.strftime("%B %Y"))

        cal = calendar.Calendar(firstweekday=0)  # Monday = 0
        month_days = cal.monthdayscalendar(self.current_date.year, self.current_date.month)

        # Determine which dates have at least one reminder (dot indicator)
        reminder_dates = self._fetch_reminder_dates()

        for wk, week in enumerate(month_days):
            row = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            for d, day in enumerate(week):
                if day == 0:
                    # Empty cell
                    btn = ctk.CTkLabel(row, text="", width=4)
                else:
                    date_str = f"{self.current_date.year}-{self.current_date.month:02d}-{day:02d}"
                    has_rem = date_str in reminder_dates
                    btn = ctk.CTkButton(
                        row,
                        text=str(day),
                        width=4,
                        height=30,
                        fg_color="#2a2a4a" if not has_rem else theme("accent"),
                        hover_color=theme("accent_hover"),
                        corner_radius=6,
                        command=lambda d=day: self._select_date(d),
                    )
                btn.grid(row=wk, column=d, padx=2, pady=2, sticky="nsew")

        # Make columns and rows expand equally
        for i in range(7):
            self.grid_frame.grid_columnconfigure(i, weight=1)
        for i in range(len(month_days)):
            self.grid_frame.grid_rowconfigure(i, weight=1)

    # ------------------------------------------------------------------
    def _fetch_reminder_dates(self) -> set[str]:
        """Return a set of date strings (YYYY‑MM‑DD) that have any reminder."""
        rows = self.db.list_upcoming_reminders(limit=1000)
        return {row[3] for row in rows}  # row[3] = date column

    # ------------------------------------------------------------------
    def _select_date(self, day: int):
        self.selected_date = datetime.date(self.current_date.year, self.current_date.month, day)
        self._open_add_dialog()

    # ------------------------------------------------------------------
    def _open_add_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Add Reminder")
        dlg.geometry("400x450")
        dlg.configure(fg_color=theme("bg_dark"))
        dlg.grab_set()

        ctk.CTkLabel(
            dlg,
            text="Add Reminder",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(20, 15))

        frm = ctk.CTkFrame(dlg, fg_color="transparent")
        frm.pack(fill="x", padx=30)

        # Title
        ctk.CTkLabel(frm, text="Title", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        e_title = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_title.pack(fill="x", pady=(0, 5))

        # Date (prefill)
        ctk.CTkLabel(frm, text="Date (YYYY‑MM‑DD)", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        e_date = ctk.CTkEntry(frm, height=38, corner_radius=8)
        prefill = (self.selected_date or datetime.date.today()).strftime("%Y-%m-%d")
        e_date.insert(0, prefill)
        e_date.pack(fill="x", pady=(0, 5))

        # Time
        ctk.CTkLabel(frm, text="Time (HH:MM, 24‑h)", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        e_time = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_time.insert(0, "09:00")
        e_time.pack(fill="x", pady=(0, 5))

        # Category
        ctk.CTkLabel(frm, text="Category", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        e_cat = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_cat.pack(fill="x", pady=(0, 5))

        # Description
        ctk.CTkLabel(frm, text="Description (optional)", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        e_desc = ctk.CTkTextbox(frm, height=80, corner_radius=8)
        e_desc.pack(fill="x", pady=(0, 10))

        def save():
            title = e_title.get().strip()
            date = e_date.get().strip()
            time = e_time.get().strip()
            cat = e_cat.get().strip()
            desc = e_desc.get("0.0", "end").strip()
            if not title or not date:
                messagebox.showwarning("Missing", "Title and date are required.")
                return
            self.db.add_reminder(title, desc, date, time, cat)
            dlg.destroy()
            self._load_upcoming_reminders()
            self._build_calendar()

        ctk.CTkButton(
            dlg,
            text="💾 Save",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            command=save,
        ).pack(pady=20)

    # ------------------------------------------------------------------
    def _load_upcoming_reminders(self):
        """Populate the right‑hand scrollable list."""
        for child in self.reminders_scroll.winfo_children():
            child.destroy()

        rows = self.db.list_upcoming_reminders(limit=15)
        if not rows:
            ctk.CTkLabel(
                self.reminders_scroll,
                text="No upcoming reminders.\nAdd one with the + button!",
                text_color="#666",
                font=ctk.CTkFont(size=13),
                justify="center",
            ).pack(pady=30)
            return

        for rid, title, desc, date, time, cat in rows:
            card = ctk.CTkFrame(self.reminders_scroll, fg_color="#2a2a4a", corner_radius=8)
            card.pack(fill="x", pady=4, padx=5)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme("text"),
                anchor="w",
            ).pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkLabel(
                card,
                text=f"📅 {date} ⏰ {time}",
                font=ctk.CTkFont(size=10),
                text_color="#aaa",
                anchor="w",
            ).pack(fill="x", padx=8)

            del_btn = ctk.CTkButton(
                card,
                text="×",
                width=24,
                height=24,
                fg_color="transparent",
                hover_color="#e74c3c",
                text_color="#888",
                corner_radius=12,
                command=lambda r=rid: self._delete_reminder(r),
            )
            del_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)

    # ------------------------------------------------------------------
    def _delete_reminder(self, rid: int):
        if messagebox.askyesno("Delete", "Remove this reminder?"):
            self.db.delete_reminder(rid)
            self._load_upcoming_reminders()
            self._build_calendar()

    # ------------------------------------------------------------------
    def _prev_month(self):
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month - 1)
        self._build_calendar()

    def _next_month(self):
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month + 1)
        self._build_calendar()

    def _go_to_today(self):
        self.current_date = datetime.date.today()
        self._build_calendar()

    # ------------------------------------------------------------------
    def _check_due_reminders(self):
        """Fire a desktop notification for any reminder that is due in the next minute."""
        now = datetime.datetime.now()
        rows = self.db.list_upcoming_reminders(limit=100)
        for rid, title, desc, date, time, cat in rows:
            try:
                due = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            delta = (due - now).total_seconds()
            if 0 <= delta <= 60:
                notify_user(
                    title=f"⏰ Reminder: {title}",
                    message=desc or f"At {time} on {date}",
                )
                self.db.mark_notified(rid)
        # schedule next check
        self.after(60_000, self._check_due_reminders)
