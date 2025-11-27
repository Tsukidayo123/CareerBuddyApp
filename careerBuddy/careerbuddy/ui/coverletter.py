# careerbuddy/ui/coverletter.py
import datetime
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from careerbuddy.services.gemini import LLMClient
from careerbuddy.ui.base import BaseCTkFrame
from careerbuddy.config.theme import get as theme


class CoverLetterFrame(BaseCTkFrame):
    """Ask the LLM to write a cover letter based on a job description."""
    def __init__(self, master):
        super().__init__(master)
        self.llm = LLMClient()          # automatically picks Gemini or Ollama
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("purple"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="✉️ Cover Letter Generator",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=20, pady=15)

        # ----- Main panes (left = input, right = output) ---------------
        main = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        main.pack(fill="both", expand=True, **self.padded())
        main.grid_columnconfigure(0, weight=1, uniform="col")
        main.grid_columnconfigure(1, weight=1, uniform="col")

        # ----- Left: job description + optional name/skills ----------
        left = ctk.CTkFrame(main, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(
            left,
            text="📄 Job Description",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme("text"),
        ).pack(anchor="w")

        self.txt_job = ctk.CTkTextbox(
            left,
            height=250,
            fg_color="#1e1e2e",
            text_color=theme("text"),
            font=("Segoe UI", 11),
        )
        self.txt_job.pack(fill="both", expand=True, pady=(5, 15))

        # Name & Skills
        ctk.CTkLabel(left, text="Your Name", text_color=theme("text")).pack(anchor="w")
        self.ent_name = ctk.CTkEntry(left, height=38, corner_radius=8)
        self.ent_name.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(left, text="Key Skills (comma separated)", text_color=theme("text")).pack(anchor="w")
        self.ent_skills = ctk.CTkEntry(left, height=38, corner_radius=8)
        self.ent_skills.pack(fill="x", pady=(0, 8))

        # Generate button
        self.btn_generate = ctk.CTkButton(
            left,
            text="✨ Generate Cover Letter",
            fg_color=theme("success"),
            hover_color="#3db389",
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            command=self._start_generation,
        )
        self.btn_generate.pack(pady=10)

        # ----- Right: output -----------------------------------------
        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(
            right,
            text="📝 Generated Letter",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme("text"),
        ).pack(anchor="w")

        self.txt_output = ctk.CTkTextbox(
            right,
            height=350,
            fg_color="#1e1e2e",
            text_color=theme("text"),
            font=("Segoe UI", 11),
        )
        self.txt_output.pack(fill="both", expand=True, pady=(5, 0))
        self.txt_output.insert("0.0", "Your cover letter will appear here…")

        # ----- Copy button (bottom of right pane) --------------------
        self.btn_copy = ctk.CTkButton(
            right,
            text="📋 Copy",
            width=80,
            height=30,
            fg_color=theme("secondary"),
            hover_color="#1a4a7a",
            corner_radius=6,
            command=self._copy_to_clipboard,
        )
        self.btn_copy.pack(pady=5, anchor="e")

    # ------------------------------------------------------------------
    def _start_generation(self):
        job_desc = self.txt_job.get("0.0", "end").strip()
        name = self.ent_name.get().strip() or "Your Name"
        skills = self.ent_skills.get().strip() or "relevant skills"

        if len(job_desc) < 50:
            messagebox.showwarning("Too short", "Please paste a more complete job description.")
            return

        # Disable UI while we wait
        self.btn_generate.configure(state="disabled", text="Generating…")
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", "Thinking...")

        # Run the LLM call in a background thread
        threading.Thread(
            target=self._call_llm,
            args=(job_desc, name, skills),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    def _call_llm(self, job_desc: str, name: str, skills: str):
        prompt = f"""Write a concise, professional cover letter for the following job description.
Include the applicant name (“{name}”) and weave in these skills: {skills}.
Keep it between 300‑400 words, friendly but formal.
Job description:
{job_desc}
"""
        try:
            reply = self.llm.generate(prompt, max_tokens=500, temperature=0.7)
        except Exception as exc:
            reply = f"❌ Error contacting LLM: {exc}"

        # Update UI on the main thread
        self.after(0, lambda: self._show_result(reply))

    # ------------------------------------------------------------------
    def _show_result(self, text: str):
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", text)
        self.btn_generate.configure(state="normal", text="✨ Generate Cover Letter")

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self):
        content = self.txt_output.get("0.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.btn_copy.configure(text="✓ Copied!")
            self.after(1500, lambda: self.btn_copy.configure(text="📋 Copy"))
