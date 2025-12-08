# careerbuddy/ui/tracker.py
import datetime
from typing import Tuple, List

import customtkinter as ctk
from tkinter import messagebox
from services.db import CareerDB
from ui.base import BaseCTkFrame
from config.theme import get as theme

# ----------------------------------------------------------------------
# Colours for each column status
# ----------------------------------------------------------------------
KANBAN_COLORS = {
    "To Apply": "#3498db",
    "Applied": "#f39c12",
    "Interviewing": "#9b59b6",
    "Offer": "#27ae60",
    "Rejected": "#e74c3c",
}


# ----------------------------------------------------------------------
# Small draggable job card that lives inside a column
# ----------------------------------------------------------------------
class JobCard(ctk.CTkFrame):
    """A single job entry shown on a Kanban column."""
    def __init__(
        self,
        parent,
        job_data: Tuple[int, str, str, str, str, str],
        on_delete,
        on_edit,
        on_drop,
    ):
        super().__init__(
            parent,
            fg_color="#2a2a4a",
            corner_radius=10,
            border_width=2,
            border_color=KANBAN_COLORS.get(job_data[3], "#555"),
        )
        self.job_id, self.company, self.role, self.status, self.notes, self.date_added = job_data
        self.on_delete = on_delete
        self.on_edit = on_edit
        self.on_drop = on_drop

        # ---- Header (company + delete) -------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        self.company_lbl = ctk.CTkLabel(
            header,
            text=self.company[:18] + ("…" if len(self.company) > 18 else ""),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme("text"),
        )
        self.company_lbl.pack(side="left", fill="x", expand=True)

        del_btn = ctk.CTkButton(
            header,
            text="×",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#e74c3c",
            text_color="#888",
            corner_radius=12,
            command=self._delete,
        )
        del_btn.pack(side="right")

        # ---- Role ----------------------------------------------------
        role_lbl = ctk.CTkLabel(
            self,
            text=self.role[:25] + ("…" if len(self.role) > 25 else ""),
            font=ctk.CTkFont(size=11),
            text_color="#aaa",
            anchor="w",
        )
        role_lbl.pack(fill="x", padx=8, pady=(0, 4))

        # ---- Date ----------------------------------------------------
        date_lbl = ctk.CTkLabel(
            self,
            text=f"📅 {self.date_added}",
            font=ctk.CTkFont(size=10),
            text_color="#666",
            anchor="w",
        )
        date_lbl.pack(fill="x", padx=8, pady=(0, 8))

        # ---- Drag handling (double‑click to edit) --------------------
        self.bind("<Double-Button-1>", lambda e: self._edit())
        self.company_lbl.bind("<Double-Button-1>", lambda e: self._edit())
        self.role = self.role  # noqa: B018 (keep reference for linters)

    def _delete(self):
        if self.on_delete:
            self.on_delete(self.job_id)

    def _edit(self):
        if self.on_edit:
            self.on_edit(self.job_id)


# ----------------------------------------------------------------------
#   Add‑Job dialog (modal)
# ----------------------------------------------------------------------
class AddJobDialog(ctk.CTkToplevel):
    """Modal dialog for inserting a new job."""
    def __init__(self, master, db: CareerDB, prefill_status: str = "To Apply", on_save=None):
        super().__init__(master)
        self.db = db
        self.on_save = on_save
        self.title("Add Job")
        self.geometry("460x420")
        self.configure(fg_color=theme("bg_dark"))
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Add New Job",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(20, 10))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=30)

        # Company
        ctk.CTkLabel(frm, text="Company", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.ent_company = ctk.CTkEntry(frm, height=38, corner_radius=8)
        self.ent_company.pack(fill="x", pady=(0, 5))

        # Role
        ctk.CTkLabel(frm, text="Role", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.ent_role = ctk.CTkEntry(frm, height=38, corner_radius=8)
        self.ent_role.pack(fill="x", pady=(0, 5))

        # Status
        ctk.CTkLabel(frm, text="Status", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.cmb_status = ctk.CTkComboBox(
            frm,
            values=["To Apply", "Applied", "Interviewing", "Offer", "Rejected"],
            height=38,
            corner_radius=8,
        )
        self.cmb_status.set(prefill_status)
        self.cmb_status.pack(fill="x", pady=(0, 5))

        # Notes
        ctk.CTkLabel(frm, text="Notes (optional)", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.txt_notes = ctk.CTkTextbox(frm, height=80, corner_radius=8)
        self.txt_notes.pack(fill="x", pady=(0, 10))

        # Save button
        ctk.CTkButton(
            self,
            text="💾 Save",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_job,
        ).pack(pady=20)

    def _save_job(self):
        company = self.ent_company.get().strip()
        role = self.ent_role.get().strip()
        status = self.cmb_status.get()
        notes = self.txt_notes.get("0.0", "end").strip()

        if not company or not role:
            messagebox.showwarning("Missing", "Company and Role cannot be empty.")
            return

        self.db.add_job(company, role, status, notes=notes)
        if self.on_save:
            self.on_save()
        self.destroy()


# ----------------------------------------------------------------------
#   Edit‑Job dialog (modal)
# ----------------------------------------------------------------------
class EditJobDialog(ctk.CTkToplevel):
    """Modal dialog for editing an existing job."""
    def __init__(self, master, job_id: int, db: CareerDB, on_save=None):
        super().__init__(master)
        self.db = db
        self.job_id = job_id
        self.on_save = on_save
        self.title("Edit Job")
        self.geometry("460x460")
        self.configure(fg_color=theme("bg_dark"))
        self.grab_set()

        # Load current values
        with db._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT company, role, status, notes FROM jobs WHERE id=?", (job_id,)
            )
            row = cur.fetchone()
        if not row:
            messagebox.showerror("Error", "Job not found.")
            self.destroy()
            return
        company, role, status, notes = row

        ctk.CTkLabel(
            self,
            text="Edit Job",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(20, 10))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=30)

        # Company
        ctk.CTkLabel(frm, text="Company", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.ent_company = ctk.CTkEntry(frm, height=38, corner_radius=8)
        self.ent_company.insert(0, company)
        self.ent_company.pack(fill="x", pady=(0, 5))

        # Role
        ctk.CTkLabel(frm, text="Role", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.ent_role = ctk.CTkEntry(frm, height=38, corner_radius=8)
        self.ent_role.insert(0, role)
        self.ent_role.pack(fill="x", pady=(0, 5))

        # Status
        ctk.CTkLabel(frm, text="Status", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.cmb_status = ctk.CTkComboBox(
            frm,
            values=["To Apply", "Applied", "Interviewing", "Offer", "Rejected"],
            height=38,
            corner_radius=8,
        )
        self.cmb_status.set(status)
        self.cmb_status.pack(fill="x", pady=(0, 5))

        # Notes
        ctk.CTkLabel(frm, text="Notes (optional)", text_color=theme("text")).pack(fill="x", pady=(10, 2))
        self.txt_notes = ctk.CTkTextbox(frm, height=80, corner_radius=8)
        self.txt_notes.insert("0.0", notes if notes else "")
        self.txt_notes.pack(fill="x", pady=(0, 10))

        # Save button
        ctk.CTkButton(
            self,
            text="💾 Save Changes",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_changes,
        ).pack(pady=20)

    def _save_changes(self):
        company = self.ent_company.get().strip()
        role = self.ent_role.get().strip()
        status = self.cmb_status.get()
        notes = self.txt_notes.get("0.0", "end").strip()

        if not company or not role:
            messagebox.showwarning("Missing", "Company and Role cannot be empty.")
            return

        self.db.edit_job(self.job_id, company, role, status, notes)
        if self.on_save:
            self.on_save()
        self.destroy()


# ----------------------------------------------------------------------
# Main Kanban view (embedded in the app)
# ----------------------------------------------------------------------
class JobTrackerFrame(BaseCTkFrame):
    """Kanban board for job applications."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db
        self.statuses = list(KANBAN_COLORS)          # order matters
        self.columns: dict[str, ctk.CTkFrame] = {}

        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="📋 Job Pipeline",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        self.btn_add = ctk.CTkButton(
            hdr,
            text="+ Add Job",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=42,
            corner_radius=8,
            command=self.open_add_dialog,
        )
        self.btn_add.pack(side="right", padx=20, pady=12)

        # ----- Columns container ---------------------------------------
        board = ctk.CTkFrame(self, fg_color="transparent")
        board.pack(fill="both", expand=True, **self.padded())
        board.grid_rowconfigure(0, weight=1)

        for i, status in enumerate(self.statuses):
            col = self._make_column(board, status, KANBAN_COLORS[status])
            col.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            board.grid_columnconfigure(i, weight=1, uniform="col")
            self.columns[status] = col

        # Load everything from the DB
        self.load_data()

    # ------------------------------------------------------------------
    def _make_column(self, parent, title: str, color: str) -> ctk.CTkFrame:
        col = ctk.CTkFrame(parent, fg_color=theme("bg_medium"), corner_radius=12)
        header = ctk.CTkFrame(col, fg_color=color, height=40, corner_radius=8)
        header.pack(fill="x", padx=8, pady=(8, 4))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(weight="bold"),
            text_color="white",
        ).pack(side="left", padx=12)

        count_lbl = ctk.CTkLabel(
            header,
            text="0",
            font=ctk.CTkFont(weight="bold"),
            text_color="white",
            bg_color="#333333",
            corner_radius=10,
            width=28,
        )
        count_lbl.pack(side="right", padx=8)
        col.count_lbl = count_lbl

        scroll = ctk.CTkScrollableFrame(col, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        col.scroll = scroll
        return col

    # ------------------------------------------------------------------
    def load_data(self):
        """Clear every column and repopulate from the DB."""
        for col in self.columns.values():
            for child in col.scroll.winfo_children():
                child.destroy()
            col.count_lbl.configure(text="0")

        jobs = self.db.get_all_jobs()
        for job in jobs:
            job_id, company, role, status, notes, date_added = job
            if status not in self.columns:
                status = "To Apply"
            self._add_card(status, job)

    # ------------------------------------------------------------------
    def _add_card(self, status: str, job_data: Tuple):
        col = self.columns[status]
        card = JobCard(
            col.scroll,
            job_data,
            on_delete=self._delete_job,
            on_edit=self._edit_job,
            on_drop=self._move_job,
        )
        card.pack(fill="x", padx=4, pady=4)
        col.count_lbl.configure(text=str(len(col.scroll.winfo_children())))

    # ------------------------------------------------------------------
    # Callback helpers -------------------------------------------------
    def _delete_job(self, job_id: int):
        self.db.delete_job(job_id)
        self.load_data()

    def _move_job(self, job_id: int, new_status: str):
        self.db.update_job_status(job_id, new_status)
        self.load_data()

    def _edit_job(self, job_id: int):
        EditJobDialog(self, job_id, self.db, on_save=self.load_data)

    # ------------------------------------------------------------------
    def open_add_dialog(self):
        AddJobDialog(self, self.db, prefill_status="To Apply", on_save=self.load_data)
