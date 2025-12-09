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
# Job detail popup (classic dialog – still available if needed)
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
# Job Card (card-style with ranks, suits, drag + overlay details)
# ------------------------------------------------------------
class JobCard(ctk.CTkFrame):
    def __init__(self, parent, job_data, tracker, on_delete, on_open):
        self.job_data = job_data
        self.tracker = tracker

        job_id, company, role, status, notes, date_added = job_data

        super().__init__(
            parent,
            fg_color="#F8F4EC",
            corner_radius=18,
            border_width=2,
            border_color=KANBAN_COLORS.get(status),
        )

        # RANK + SUIT (CARD IDENTITY)
        SUITS = {
            "To Apply": "♣",
            "Applied": "♦",
            "Interviewing": "♥",
            "Offer": "♠",
            "Rejected": "🃏",
        }

        RANKS = {
            "To Apply": "10",
            "Applied": "J",
            "Interviewing": "Q",
            "Offer": "K",
            "Rejected": "✖",
        }

        # Top-left rank & suit
        ctk.CTkLabel(
            self,
            text=f"{RANKS[status]}  {SUITS[status]}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#111",
        ).pack(anchor="w", padx=10, pady=(6, 0))

        # Header (company + delete)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))

        # Company – brighter & centered
        ctk.CTkLabel(
            header,
            text=company,
            text_color=theme("accent"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            header,
            text="×",
            width=24,
            command=lambda: on_delete(job_id),
            fg_color="transparent",
            hover_color="#e74c3c",
        ).pack(side="right")

        # Role (centered)
        role_label = ctk.CTkLabel(
            self,
            text=role,
            text_color="#555",
            anchor="center",
            justify="center",
        )
        role_label.pack(fill="x", padx=10, pady=(0, 4))

        # Bottom-right rank & suit in its own bar so it can hug the right edge
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=6, pady=(0, 4))

        ctk.CTkLabel(
            bottom_bar,
            text=f"{SUITS[status]}  {RANKS[status]}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#111",
        ).pack(side="right")


        # DRAG HANDLE (BOTTOM EDGE)
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

        # Right-click drag only from handle
        drag_handle.bind("<ButtonPress-3>", self._start_drag)
        drag_handle.bind("<ButtonRelease-3>", self._drop)

        self.on_open = on_open  # kept for compatibility if needed

        # Make entire card clickable (including children) → overlay details
        self.bind("<Button-1>", self._flip_open)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._flip_open)

        # Fade rejected cards after all children exist
        if status == "Rejected":
            self.configure(fg_color="#444")
            for widget in self.winfo_children():
                try:
                    widget.configure(text_color="#888")
                except Exception:
                    pass

    # ---------------- Drag & Ghost Preview -----------------
    def _start_drag(self, event):
        self.lift()
        self.tracker.dragged_job_id = self.job_data[0]

        # destroy any previous ghost
        if self.tracker.drag_ghost is not None:
            self.tracker.drag_ghost.destroy()
            self.tracker.drag_ghost = None

        company = self.job_data[1]

        # create drag ghost attached to toplevel
        ghost = ctk.CTkLabel(
            self.tracker.winfo_toplevel(),
            text=f"Moving: {company}",
            fg_color=theme("accent"),
            text_color=theme("bg_dark"),
            corner_radius=12,
            padx=12,
            pady=6,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.tracker.drag_ghost = ghost

        root = self.tracker.winfo_toplevel()
        # initial placement where the drag starts
        ghost.place(
            x=event.x_root - root.winfo_rootx() - 120,
            y=event.y_root - root.winfo_rooty() - 20,
        )

        # follow the mouse while dragging – bind on the toplevel
        root.bind("<Motion>", self.tracker._move_ghost)

    def _drop(self, event):
        col = self.tracker.get_column_from_pointer(event)
        if col:
            self.tracker.move_job(self.job_data[0], col)

        # reset drag state so clicks work again
        self.tracker.dragged_job_id = None

    # ---------------- Overlay "Flip" (smooth, no janky resize) -----------------
    def _flip_open(self, event):
        # Prevent triggering while dragging
        if self.tracker.dragged_job_id:
            return
        self._open_overlay_card()

    def _open_overlay_card(self):
        root = self.tracker.winfo_toplevel()

        # Dark overlay (solid; CTk doesn't like alpha hex)
        overlay = ctk.CTkFrame(root, fg_color="#000000")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.tracker.overlay = overlay

        # Floating card container in center
        card = ctk.CTkFrame(root, fg_color="#F8F4EC", corner_radius=20)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.configure(width=460, height=540)
        self.tracker.active_card = card

        # Fill it with job details
        self._build_detail_view()

    def _build_detail_view(self):
        card = self.tracker.active_card

        job_id, company, role, status, notes, date_added = self.job_data

        link = ""
        if "Link:" in (notes or ""):
            parts = notes.split("Link:")
            notes = parts[0].strip()
            link = parts[1].strip()

        ctk.CTkLabel(
            card,
            text=f"{role}\n@ {company}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#111",
            justify="center",
            wraplength=380,
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            card,
            text=f"Status: {status}",
            text_color=KANBAN_COLORS.get(status),
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            card,
            text=f"Added: {date_added}",
            text_color="#666",
        ).pack(pady=6)

        if link:
            link_lbl = ctk.CTkLabel(
                card,
                text=f"🔗 {link}",
                text_color=theme("accent"),
                cursor="hand2",
            )
            link_lbl.pack(pady=10)
            link_lbl.bind("<Button-1>", lambda e: webbrowser.open(link))

        notes_box = ctk.CTkTextbox(card, height=160)
        notes_box.pack(fill="x", padx=30, pady=10)
        notes_box.insert("0.0", notes if notes else "No notes added.")
        notes_box.configure(state="disabled")

        ctk.CTkButton(
            card,
            text="✏️ Edit Job",
            fg_color=theme("accent"),
            command=lambda: self._edit_from_overlay(job_id),
        ).pack(pady=(6, 4))

        ctk.CTkButton(
            card,
            text="✖ Close",
            fg_color=theme("warning"),
            command=self._flip_close,
        ).pack(pady=12)

    def _edit_from_overlay(self, job_id):
        # Close overlay first
        self._flip_close()
        # Open edit dialog using tracker (true edit)
        self.tracker._edit_job(job_id)

    def _flip_close(self):
        if getattr(self.tracker, "active_card", None):
            self.tracker.active_card.destroy()
            self.tracker.active_card = None
        if getattr(self.tracker, "overlay", None):
            self.tracker.overlay.destroy()
            self.tracker.overlay = None


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
# Edit Job Dialog (true edit, not add)
# ------------------------------------------------------------
class EditJobDialog(ctk.CTkToplevel):
    def __init__(self, master, job_id: int, db: CareerDB, on_save=None):
        super().__init__(master)
        self.db = db
        self.job_id = job_id
        self.on_save = on_save

        self.title("Edit Job")
        self.geometry("480x540")
        self.configure(fg_color=theme("bg_dark"))
        self.grab_set()

        # Load current job values
        with db._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT company, role, status, notes FROM jobs WHERE id=?",
                (job_id,),
            )
            row = cur.fetchone()

        if not row:
            messagebox.showerror("Error", "Job not found.")
            self.destroy()
            return

        company, role, status, notes = row

        link = ""
        base_notes = notes or ""
        if "Link:" in base_notes:
            parts = base_notes.split("Link:")
            base_notes = parts[0].strip()
            link = parts[1].strip()

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(frm, text="Company", text_color=theme("text")).pack(anchor="w")
        self.ent_company = ctk.CTkEntry(frm)
        self.ent_company.insert(0, company)
        self.ent_company.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Job Title", text_color=theme("text")).pack(anchor="w")
        self.ent_role = ctk.CTkEntry(frm)
        self.ent_role.insert(0, role)
        self.ent_role.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Status", text_color=theme("text")).pack(anchor="w")
        self.cmb_status = ctk.CTkComboBox(frm, values=list(KANBAN_COLORS.keys()))
        self.cmb_status.set(status)
        self.cmb_status.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Job Link", text_color=theme("text")).pack(anchor="w")
        self.ent_link = ctk.CTkEntry(frm)
        self.ent_link.insert(0, link)
        self.ent_link.pack(fill="x", pady=5)

        ctk.CTkLabel(frm, text="Description / Notes", text_color=theme("text")).pack(anchor="w")
        self.txt_notes = ctk.CTkTextbox(frm, height=140)
        self.txt_notes.pack(fill="x", pady=5)
        self.txt_notes.insert("0.0", base_notes)

        ctk.CTkButton(
            self,
            text="💾 Save Changes",
            fg_color=theme("success"),
            command=self._save_changes,
        ).pack(pady=20)

    def _save_changes(self):
        company = self.ent_company.get().strip()
        role = self.ent_role.get().strip()
        status = self.cmb_status.get()
        link = self.ent_link.get().strip()
        notes = self.txt_notes.get("0.0", "end").strip()

        if not company or not role:
            messagebox.showwarning("Missing", "Company and Job Title are required.")
            return

        full_notes = f"{notes}\n\nLink: {link}" if link else notes

        self.db.edit_job(self.job_id, company, role, status, full_notes)

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
        self.drag_ghost = None
        self.overlay = None
        self.active_card = None

        # Instruction banner
        tip = ctk.CTkLabel(
            self,
            text="🖱️ Right-click and drag the BOTTOM EDGE of a card to move it between columns",
            text_color=theme("accent"),
        )
        tip.pack(pady=10)

        # Thicker Job Deck header
        hdr = ctk.CTkFrame(
            self,
            fg_color=theme("secondary"),
            corner_radius=22,
            height=64,
        )
        hdr.pack(fill="x", padx=20)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🃏 Job Deck",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=24)

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
        # Card rank + suit mapping for headers
        CARD_SYMBOLS = {
            "To Apply": "♣ 10  To Apply",
            "Applied": "♦ J  Applied",
            "Interviewing": "♥ Q  Interviewing",
            "Offer": "♠ K  Offer",
            "Rejected": "🃏 Joker  Rejected",
        }

        col = ctk.CTkFrame(parent, fg_color=theme("bg_medium"), corner_radius=16)

        # Card style header with rank + suit
        ctk.CTkLabel(
            col,
            text=CARD_SYMBOLS.get(title, title),
            fg_color=KANBAN_COLORS.get(title),
            text_color="white",
            corner_radius=14,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(fill="x", padx=10, pady=10)

        # Auto-growing container for cards
        body = ctk.CTkFrame(col, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=6, pady=6)

        col.body = body
        return col

    # ---------------- Drag ghost positioning ----------------
    def _move_ghost(self, event):
        if not self.drag_ghost:
            return

        root = self.winfo_toplevel()
        self.drag_ghost.place(
            x=event.x_root - root.winfo_rootx() - 120,
            y=event.y_root - root.winfo_rooty() - 20,
        )

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

        # Remove drag ghost after drop
        root = self.winfo_toplevel()
        if self.drag_ghost:
            self.drag_ghost.destroy()
            self.drag_ghost = None
        root.unbind("<Motion>")

    def load_data(self):
        for col in self.columns.values():
            for child in col.body.winfo_children():
                child.destroy()

        jobs = self.db.get_all_jobs()
        for job in jobs:
            self._add_card(job[3], job)

        # Resize all columns after loading
        for col in self.columns.values():
            self._resize_column(col)

    def _add_card(self, status, job_data):
        col = self.columns.get(status)
        card = JobCard(col.body, job_data, self, self._delete_job, self._open_details)
        card.pack(fill="x", padx=6, pady=6)
        self._resize_column(col)

    def _resize_column(self, col):
        cards = col.body.winfo_children()
        card_height = 110   # approximate height per card
        padding = 14

        total_height = len(cards) * (card_height + padding) + 80
        col.configure(height=total_height)

    def _open_details(self, job_data):
        JobDetailDialog(self, job_data, on_edit=self._edit_job)

    def _delete_job(self, job_id):
        self.db.delete_job(job_id)
        self.load_data()

    def _edit_job(self, job_id):
        EditJobDialog(self, job_id, self.db, on_save=self.load_data)

    def open_add_dialog(self):
        AddJobDialog(self, self.db, on_save=self.load_data)
