# ui/tracker.py
from typing import Tuple
import webbrowser

import customtkinter as ctk
from tkinter import messagebox

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


# ------------------------------------------------------------
# Job detail popup
# ------------------------------------------------------------
class JobDetailDialog(ctk.CTkToplevel):
    def __init__(self, master, job_data, on_edit):
        super().__init__(master)
        self.title("Job Details")
        self.geometry("450x520")
        self.configure(fg_color=theme("bg_dark"))
        self.grab_set()

        job_id, company, role, status, notes, date_added = job_data

        link = ""
        description = notes or ""
        if "Link:" in description:
            parts = description.split("Link:")
            description = parts[0].strip()
            link = parts[1].strip()

        ctk.CTkLabel(
            self,
            text=f"{role}\n@ {company}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
            wraplength=380,
            justify="center",
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            self,
            text=f"Status: {status}",
            text_color=KANBAN_COLORS.get(status),
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            self,
            text=f"Added: {date_added}",
            text_color="#888",
        ).pack(pady=6)

        if link:
            link_lbl = ctk.CTkLabel(
                self,
                text=f"🔗 {link}",
                text_color=theme("accent"),
                cursor="hand2",
            )
            link_lbl.pack(pady=10)
            link_lbl.bind("<Button-1>", lambda e: webbrowser.open(link))

        ctk.CTkLabel(self, text="Notes", text_color=theme("text")).pack(pady=(10, 2))

        notes_box = ctk.CTkTextbox(self, height=180)
        notes_box.pack(fill="x", padx=25)
        notes_box.insert("0.0", description if description else "No notes added.")
        notes_box.configure(state="disabled")

        ctk.CTkButton(
            self,
            text="✏️ Edit Job",
            command=lambda: on_edit(job_id),
        ).pack(pady=20)


# ------------------------------------------------------------
# Job Card (with DRAG HANDLE)
# ------------------------------------------------------------
class JobCard(ctk.CTkFrame):
    def __init__(self, parent, job_data, tracker, on_delete, on_open):
        self.job_data = job_data
        self.tracker = tracker

        job_id, company, role, status, notes, date_added = job_data

        super().__init__(
            parent,
            fg_color=theme("bg_dark"),
            corner_radius=18,
            border_width=2,
            border_color=KANBAN_COLORS.get(status),
        )

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            header,
            text=company,
            text_color=theme("text"),
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            header,
            text="×",
            width=24,
            command=lambda: on_delete(job_id),
            fg_color="transparent",
            hover_color="#e74c3c",
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text=role,
            text_color="#aaa",
        ).pack(anchor="w", padx=10)

        # ✅ DRAG HANDLE (BOTTOM EDGE)
        drag_handle = ctk.CTkFrame(
            self,
            height=10,
            fg_color=theme("accent"),
            corner_radius=6,
        )
        drag_handle.pack(fill="x", side="bottom", padx=6, pady=6)

        ctk.CTkLabel(
            drag_handle,
            text="⇅ DRAG",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=theme("bg_dark"),
        ).pack()

        # ✅ Right-click drag only from handle
        drag_handle.bind("<ButtonPress-3>", self._start_drag)
        drag_handle.bind("<ButtonRelease-3>", self._drop)

        # ✅ Click anywhere else = open details
        self.bind("<Button-1>", lambda e: on_open(self.job_data))

    def _start_drag(self, event):
        self.lift()
        self.tracker.dragged_job_id = self.job_data[0]

    def _drop(self, event):
        col = self.tracker.get_column_from_pointer(event)
        if col:
            self.tracker.move_job(self.job_data[0], col)


# ------------------------------------------------------------
# Add Job Dialog (FULL INPUT)
# ------------------------------------------------------------
class AddJobDialog(ctk.CTkToplevel):
    def __init__(self, master, db: CareerDB, prefill_status="To Apply", on_save=None):
        super().__init__(master)
        self.db = db
        self.on_save = on_save
        self.title("Add Job")
        self.geometry("480x520")
        self.configure(fg_color=theme("bg_dark"))
        self.grab_set()

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(frm, text="Company", text_color=theme("text")).pack(anchor="w")
        self.ent_company = ctk.CTkEntry(frm)
        self.ent_company.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Job Title", text_color=theme("text")).pack(anchor="w")
        self.ent_role = ctk.CTkEntry(frm)
        self.ent_role.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Status", text_color=theme("text")).pack(anchor="w")
        self.cmb_status = ctk.CTkComboBox(frm, values=list(KANBAN_COLORS.keys()))
        self.cmb_status.set(prefill_status)
        self.cmb_status.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Job Link", text_color=theme("text")).pack(anchor="w")
        self.ent_link = ctk.CTkEntry(frm)
        self.ent_link.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Description / Notes", text_color=theme("text")).pack(anchor="w")
        self.txt_notes = ctk.CTkTextbox(frm, height=120)
        self.txt_notes.pack(fill="x", pady=5)

        ctk.CTkButton(
            self,
            text="💾 Save Job",
            fg_color=theme("success"),
            command=self._save,
        ).pack(pady=20)

    def _save(self):
        company = self.ent_company.get().strip()
        role = self.ent_role.get().strip()
        status = self.cmb_status.get()
        link = self.ent_link.get().strip()
        notes = self.txt_notes.get("0.0", "end").strip()

        if not company or not role:
            messagebox.showwarning("Missing", "Company and Job Title are required.")
            return

        full_notes = f"{notes}\n\nLink: {link}" if link else notes

        self.db.add_job(company, role, status, notes=full_notes)

        if self.on_save:
            self.on_save()

        self.destroy()


# ------------------------------------------------------------
# Main Board (with instruction banner)
# ------------------------------------------------------------
class JobTrackerFrame(BaseCTkFrame):
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db
        self.statuses = list(KANBAN_COLORS)
        self.columns = {}
        self.dragged_job_id = None

        # ✅ INSTRUCTION BANNER
        tip = ctk.CTkLabel(
            self,
            text="🖱️ Right-click and drag the BOTTOM EDGE of a card to move it between columns",
            text_color=theme("accent"),
        )
        tip.pack(pady=10)

        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=16)
        hdr.pack(fill="x", padx=20)

        ctk.CTkLabel(
            hdr,
            text="🃏 Job Deck",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20)

        ctk.CTkButton(
            hdr,
            text="+ Add Job",
            fg_color=theme("success"),
            command=self.open_add_dialog,
        ).pack(side="right", padx=20)

        board = ctk.CTkFrame(self, fg_color="transparent")
        board.pack(fill="both", expand=True, padx=20, pady=20)

        for i, status in enumerate(self.statuses):
            col = self._make_column(board, status)
            col.grid(row=0, column=i, sticky="nsew", padx=6)
            board.grid_columnconfigure(i, weight=1)
            self.columns[status] = col

        self.load_data()

    def _make_column(self, parent, title):
        col = ctk.CTkFrame(parent, fg_color=theme("bg_medium"), corner_radius=16)

        ctk.CTkLabel(
            col,
            text=title,
            fg_color=KANBAN_COLORS.get(title),
            text_color="white",
            corner_radius=12,
            height=36,
        ).pack(fill="x", padx=10, pady=10)

        scroll = ctk.CTkScrollableFrame(col)
        scroll.pack(fill="both", expand=True)
        col.scroll = scroll
        return col

    def get_column_from_pointer(self, event):
        for status, col in self.columns.items():
            x1, y1 = col.winfo_rootx(), col.winfo_rooty()
            x2, y2 = x1 + col.winfo_width(), y1 + col.winfo_height()
            if x1 < event.x_root < x2 and y1 < event.y_root < y2:
                return status
        return None

    def move_job(self, job_id, new_status):
        self.db.update_job_status(job_id, new_status)
        self.load_data()

    def load_data(self):
        for col in self.columns.values():
            for child in col.scroll.winfo_children():
                child.destroy()

        jobs = self.db.get_all_jobs()
        for job in jobs:
            self._add_card(job[3], job)

    def _add_card(self, status, job_data):
        col = self.columns.get(status)
        card = JobCard(col.scroll, job_data, self, self._delete_job, self._open_details)
        card.pack(fill="x", padx=6, pady=6)

    def _open_details(self, job_data):
        JobDetailDialog(self, job_data, on_edit=self._edit_job)

    def _delete_job(self, job_id):
        self.db.delete_job(job_id)
        self.load_data()

    def _edit_job(self, job_id):
        AddJobDialog(self, self.db, on_save=self.load_data)

    def open_add_dialog(self):
        AddJobDialog(self, self.db, on_save=self.load_data)
