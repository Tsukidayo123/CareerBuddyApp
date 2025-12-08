# careerbuddy/ui/filevault.py
import os
import shutil
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from services.db import CareerDB
from ui.base import BaseCTkFrame
from config.theme import get as theme

FILES_DIR = os.path.join(os.getcwd(), "career_buddy_files")
os.makedirs(FILES_DIR, exist_ok=True)


class FileStorageFrame(BaseCTkFrame):
    """File storage for CVs, cover letters, and other documents."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db
        self.categories = ["All", "CV/Resume", "Cover Letter", "Portfolio", "Certificates", "Other"]
        self.current_filter = tk.StringVar(value="All")
        self._setup_ui()
        self._load_files()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="📁 File Storage",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        # Upload button
        self.btn_upload = ctk.CTkButton(
            hdr,
            text="+ Upload File",
            fg_color=theme("success"),
            hover_color="#3db389",
            corner_radius=8,
            command=self._upload_file,
        )
        self.btn_upload.pack(side="right", padx=20, pady=12)

        # Category filter (button group)
        filter_frm = ctk.CTkFrame(self, fg_color="transparent")
        filter_frm.pack(fill="x", **self.padded())

        ctk.CTkLabel(filter_frm, text="Filter:", text_color=theme("text")).pack(side="left", padx=(0, 10))

        self.category_buttons = {}
        for cat in self.categories[1:]:   # skip “All”
            btn = ctk.CTkButton(
                filter_frm,
                text=cat,
                width=120,
                height=30,
                fg_color=theme("secondary") if cat != "Other" else theme("accent"),
                hover_color=theme("accent_hover"),
                corner_radius=6,
                command=lambda c=cat: self._apply_filter(c),
            )
            btn.pack(side="left", padx=4, pady=2)
            self.category_buttons[cat] = btn

        # Highlight the default ("Other")
        self._highlight_category("Other")

        # Main content area (scrollable list of files)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        self.scroll.pack(fill="both", expand=True, **self.padded())

    # ------------------------------------------------------------------
    def _apply_filter(self, cat: str):
        self.current_filter.set(cat)
        self._highlight_category(cat)
        self._load_files()

    def _highlight_category(self, active_cat: str):
        for cat, btn in self.category_buttons.items():
            if cat == active_cat:
                btn.configure(fg_color=theme("accent"))
            else:
                btn.configure(fg_color=theme("secondary"))

    # ------------------------------------------------------------------
    def _upload_file(self):
        filetypes = [
            ("All supported", "*.pdf *.doc *.docx *.txt *.png *.jpg *.jpeg"),
            ("PDF", "*.pdf"),
            ("Word", "*.doc *.docx"),
            ("Images", "*.png *.jpg *.jpeg"),
            ("All files", "*.*"),
        ]
        src = filedialog.askopenfilename(title="Select a file", filetypes=filetypes)
        if not src:
            return

        # Choose a category (default = Other)
        cat = self.current_filter.get() or "Other"

        # Copy into internal folder with timestamped name
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.basename(src)
        stored_name = f"{ts}_{fname}"
        dest = os.path.join(FILES_DIR, stored_name)

        try:
            shutil.copy2(src, dest)
            self.db.add_file(stored_name, fname, cat)
            self._load_files()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save file: {exc}")

    # ------------------------------------------------------------------
    def _load_files(self):
        # Clear previous list
        for child in self.scroll.winfo_children():
            child.destroy()

        cat = self.current_filter.get()
        rows = self.db.list_files(category=None if cat == "All" else cat)

        if not rows:
            ctk.CTkLabel(
                self.scroll,
                text="No files yet. Upload something!",
                text_color="#666",
                font=ctk.CTkFont(size=13),
            ).pack(pady=30)
            return

        for fid, filename, original, category, date_added in rows:
            card = ctk.CTkFrame(self.scroll, fg_color="#2a2a4a", corner_radius=10, height=60)
            card.pack(fill="x", pady=4, padx=4)

            # Icon based on extension
            ext = os.path.splitext(original)[1].lower()
            icon = {
                ".pdf": "📄",
                ".doc": "📝",
                ".docx": "📝",
                ".png": "🖼️",
                ".jpg": "🖼️",
                ".jpeg": "🖼️",
                ".txt": "📃",
            }.get(ext, "📁")

            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=24), width=50).pack(side="left", padx=5)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=8)

            ctk.CTkLabel(
                info,
                text=original[:45] + ("…" if len(original) > 45 else ""),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme("text"),
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info,
                text=f"📅 {date_added}",
                font=ctk.CTkFont(size=10),
                text_color="#888",
                anchor="w",
            ).pack(anchor="w")

            # Open button
            open_btn = ctk.CTkButton(
                card,
                text="Open",
                width=60,
                height=30,
                fg_color=theme("secondary"),
                hover_color="#1a4a7a",
                corner_radius=6,
                command=lambda f=filename: self._open_file(f),
            )
            open_btn.pack(side="right", padx=5)

            # Delete button
            del_btn = ctk.CTkButton(
                card,
                text="🗑",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color="#e74c3c",
                text_color="#888",
                command=lambda fid=fid, fn=filename: self._delete_file(fid, fn),
            )
            del_btn.pack(side="right", padx=5)

    # ------------------------------------------------------------------
    def _open_file(self, filename: str):
        path = os.path.join(FILES_DIR, filename)
        if not os.path.exists(path):
            messagebox.showerror("Missing", "File not found on disk.")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open file: {exc}")

    # ------------------------------------------------------------------
    def _delete_file(self, fid: int, filename: str):
        if not messagebox.askyesno("Delete", "Remove this file?"):
            return
        self.db.delete_file(fid)
        try:
            os.remove(os.path.join(FILES_DIR, filename))
        except OSError:
            pass
        self._load_files()
