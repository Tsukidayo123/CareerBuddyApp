# careerbuddy/ui/catcher.py
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk
from careerbuddy.services.db import CareerDB
from careerbuddy.ui.base import BaseCTkFrame
from careerbuddy.config.theme import get as theme


class JobCatcherFrame(BaseCTkFrame):
    """Paste job details (or use the bookmarklet) and turn them into a DB entry."""
    def __init__(self, master, db: CareerDB):
        super().__init__(master)
        self.db = db

        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🎣 Job Catcher",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        # ----- Main content -------------------------------------------
        main = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        main.pack(fill="both", expand=True, **self.padded())

        ctk.CTkLabel(
            main,
            text="📋 Paste job details below (or use the bookmarklet).",
            font=ctk.CTkFont(size=13),
            text_color=theme("text"),
        ).pack(pady=(15, 5), anchor="w")

        self.txt = ctk.CTkTextbox(
            main,
            fg_color="#1e1e2e",
            text_color=theme("text"),
            font=("Segoe UI", 11),
            height=200,
        )
        self.txt.pack(fill="both", expand=True, pady=(0, 10))
        self.txt.insert("0.0", "Paste job description or the generated bookmarklet text here...")

        btn = ctk.CTkButton(
            main,
            text="✨ Parse & Add Job",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._parse_and_add,
        )
        btn.pack(pady=5)

        # ----- Bookmarklet snippet (copy‑to‑clipboard) ----------------
        snippet = (
            "javascript:(function(){"
            "var t=document.title||'';var c='';var r='';var l=window.location.href;"
            "if(l.includes('indeed.com')){c=document.querySelector('[data-company]')?.innerText||"
            "document.querySelector('.jobsearch-CompanyInfoWithoutHeaderImage')?.innerText||'';"
            "r=document.querySelector('[data-testid=\"jobsearch-JobInfoHeader-title\"]')?.innerText||"
            "document.querySelector('.jobsearch-JobInfoHeader-title')?.innerText||t;}"
            "else if(l.includes('linkedin.com')){c=document.querySelector('.job-details-jobs-unified-top-card__company-name')?.innerText||'';"
            "r=document.querySelector('.job-details-jobs-unified-top-card__job-title')?.innerText||t;}"
            "else{c=t.split('-')[1]?.trim()||'';r=t.split('-')[0]?.trim()||t;}"
            "var d='CAREERBUDDY_JOB:\\nCompany: '+c+'\\nRole: '+r+'\\nURL: '+l;"
            "prompt('Copy this and paste in CareerBuddy Job Catcher:',d);})();"
        )
        ctk.CTkButton(
            main,
            text="📎 Copy Bookmarklet Code",
            fg_color=theme("accent"),
            hover_color=theme("accent_hover"),
            height=35,
            corner_radius=6,
            command=lambda: self._copy_to_clipboard(snippet),
        ).pack(pady=5)

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Bookmarklet code copied to clipboard!")

    # ------------------------------------------------------------------
    def _parse_and_add(self):
        raw = self.txt.get("0.0", "end").strip()
        if not raw:
            messagebox.showwarning("Empty", "Paste something first.")
            return

        # Very simple parsing – look for lines that start with "Company:" / "Role:"
        company = role = url = ""
        for line in raw.splitlines():
            line = line.strip()
            if line.lower().startswith("company:"):
                company = line.split(":", 1)[1].strip()
            elif line.lower().startswith("role:"):
                role = line.split(":", 1)[1].strip()
            elif line.lower().startswith("url:"):
                url = line.split(":", 1)[1].strip()

        # Fallback: if we didn't find anything, just use the whole text as notes
        notes = raw if not (company and role) else ""

        # Show a tiny dialog to confirm / edit before saving
        self._show_confirm_dialog(company, role, notes, url)

    # ------------------------------------------------------------------
    def _show_confirm_dialog(self, company, role, notes, url):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirm Job Details")
        dlg.geometry("460x420")
        dlg.configure(fg_color=theme("bg_dark"))
        dlg.grab_set()

        ctk.CTkLabel(
            dlg,
            text="Confirm / edit the fields before saving:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme("text"),
        ).pack(pady=(15, 10))

        frm = ctk.CTkFrame(dlg, fg_color="transparent")
        frm.pack(fill="x", padx=25)

        # Company
        ctk.CTkLabel(frm, text="Company:", text_color=theme("text")).pack(fill="x", pady=(5, 2))
        e_company = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_company.insert(0, company)
        e_company.pack(fill="x", pady=(0, 5))

        # Role
        ctk.CTkLabel(frm, text="Role:", text_color=theme("text")).pack(fill="x", pady=(5, 2))
        e_role = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_role.insert(0, role)
        e_role.pack(fill="x", pady=(0, 5))

        # Status (default = To Apply)
        ctk.CTkLabel(frm, text="Status:", text_color=theme("text")).pack(fill="x", pady=(5, 2))
        cb_status = ctk.CTkComboBox(
            frm,
            values=["To Apply", "Applied", "Interviewing", "Offer", "Rejected"],
            height=38,
            corner_radius=8,
        )
        cb_status.set("To Apply")
        cb_status.pack(fill="x", pady=(0, 5))

        # Notes / URL
        ctk.CTkLabel(frm, text="Notes / URL:", text_color=theme("text")).pack(fill="x", pady=(5, 2))
        e_notes = ctk.CTkEntry(frm, height=38, corner_radius=8)
        e_notes.insert(0, notes if notes else url)
        e_notes.pack(fill="x", pady=(0, 15))

        def save():
            comp = e_company.get().strip() or "Unknown"
            rl = e_role.get().strip() or "Unknown"
            st = cb_status.get()
            nt = e_notes.get().strip()
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            self.db.add_job(comp, rl, st, link="", notes=nt, date_added=today)
            dlg.destroy()
            messagebox.showinfo("Saved", f"Added '{rl}' at '{comp}' to the tracker.")

        ctk.CTkButton(
            dlg,
            text="💾 Save Job",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            command=save,
        ).pack(pady=15)
