import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
import calendar
import random
import threading
import os
import shutil
import time
from plyer import notification

# --- Gemini AI Setup ---
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

APP_NAME = "CareerBuddy"
DB_NAME = "career_buddy.db"
FILES_FOLDER = "career_buddy_files"

# Ensure files folder exists
if not os.path.exists(FILES_FOLDER):
    os.makedirs(FILES_FOLDER)

# Color Palette
COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_medium": "#16213e",
    "accent": "#e94560",
    "accent_hover": "#c73e54",
    "secondary": "#0f3460",
    "text": "#eaeaea",
    "success": "#4ecca3",
    "warning": "#ffc107",
    "purple": "#7b2cbf",
    "purple_hover": "#5a189a",
}

# System prompt for the AI
CAREER_BUDDY_SYSTEM_PROMPT = """You are CareerBuddy, a friendly and supportive AI career advisor designed specifically for students and recent graduates looking for jobs and internships.

Your personality:
- Encouraging and positive, but realistic
- Knowledgeable about job searching, CVs, cover letters, interviews, and career development
- Empathetic when users face rejection or feel discouraged
- Practical and actionable in your advice

Your expertise includes:
- CV/Resume writing and optimization
- Cover letter crafting
- Interview preparation (behavioral, technical, case studies)
- Job search strategies
- LinkedIn optimization
- Networking tips
- Salary negotiation
- Career planning and goal setting
- Industry-specific advice
- Dealing with rejection and staying motivated

Guidelines:
- Keep responses concise but helpful (2-4 paragraphs max unless more detail is needed)
- Use emojis sparingly to keep things friendly 🎯
- When giving advice, be specific and actionable
- If asked about something outside career advice, gently redirect to career topics
- Celebrate wins and provide encouragement during tough times
- Suggest using the app's features (Job Tracker, Whiteboard, Notes) when relevant

Remember: You're talking to students who may be anxious about their future. Be supportive!"""

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Job Table
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY, 
                  company TEXT, 
                  role TEXT, 
                  status TEXT, 
                  link TEXT, 
                  notes TEXT,
                  date_added TEXT)''')
    # Notes Table
    c.execute('''CREATE TABLE IF NOT EXISTS notes
                 (id INTEGER PRIMARY KEY, content TEXT)''')
    # Settings Table for API key
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # Files Table
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id INTEGER PRIMARY KEY,
                  filename TEXT,
                  original_name TEXT,
                  category TEXT,
                  date_added TEXT)''')
    # Reminders Table
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY,
                  title TEXT,
                  description TEXT,
                  date TEXT,
                  time TEXT,
                  category TEXT,
                  notified INTEGER DEFAULT 0)''')
    
    # Check if notes exist, if not create default
    c.execute("SELECT count(*) FROM notes")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO notes (content) VALUES ('')")
        
    conn.commit()
    conn.close()

def get_api_key():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='gemini_api_key'")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def save_api_key(api_key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gemini_api_key', ?)", (api_key,))
    conn.commit()
    conn.close()

# --- Custom Widgets ---

class DraggablePostIt(ctk.CTkFrame):
    """A Post-it note that can be dragged around on the whiteboard."""
    def __init__(self, parent, text="New Task", x=50, y=50, color="#fdfd96", on_delete=None):
        super().__init__(parent, fg_color=color, corner_radius=12, border_width=2, border_color="#333333")
        self.parent = parent
        self.on_delete = on_delete
        self.note_color = color
        
        # Header with drag handle and delete button
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.header.pack(fill="x", padx=4, pady=(4, 0))
        
        # Drag handle indicator
        self.drag_label = ctk.CTkLabel(self.header, text="⋮⋮", font=("Arial", 10), text_color="#666666", width=20)
        self.drag_label.pack(side="left")
        
        # Delete button
        self.btn_delete = ctk.CTkButton(
            self.header, text="×", width=20, height=20, 
            fg_color="#cc4444", hover_color="#ff3333",
            text_color="white", font=("Arial", 14, "bold"),
            corner_radius=10, command=self.delete_note
        )
        self.btn_delete.pack(side="right")
        
        # Text Area
        self.textbox = ctk.CTkTextbox(
            self, width=140, height=90, 
            fg_color="#f5f5f5", text_color="#1a1a1a", 
            font=("Segoe UI", 12), corner_radius=6,
            border_width=0
        )
        self.textbox.insert("0.0", text)
        self.textbox.pack(padx=6, pady=(2, 6))
        
        # Place initially
        self.place(x=x, y=y)
        
        # Bind dragging events to header and drag label
        self.header.bind("<Button-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.drag_label.bind("<Button-1>", self.start_move)
        self.drag_label.bind("<B1-Motion>", self.do_move)

        self._drag_data = {"x": 0, "y": 0}

    def start_move(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self.lift()

    def do_move(self, event):
        x = self.winfo_x() - self._drag_data["x"] + event.x
        y = self.winfo_y() - self._drag_data["y"] + event.y
        self.place(x=x, y=y)
    
    def delete_note(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()

class ColorButton(ctk.CTkButton):
    """A circular color picker button."""
    def __init__(self, parent, color, command, selected=False, **kwargs):
        super().__init__(
            parent, text="", width=28, height=28,
            fg_color=color, hover_color=color,
            corner_radius=14, border_width=3 if selected else 0,
            border_color="white", command=command, **kwargs
        )
        self.color = color
    
    def set_selected(self, selected):
        self.configure(border_width=3 if selected else 0)

# Kanban column colors
KANBAN_COLORS = {
    "To Apply": "#3498db",      # Blue
    "Applied": "#f39c12",       # Orange
    "Interviewing": "#9b59b6",  # Purple
    "Offer": "#27ae60",         # Green
    "Rejected": "#e74c3c",      # Red
}

class JobCard(ctk.CTkFrame):
    """A draggable job card for the Kanban board."""
    def __init__(self, parent, job_data, on_delete=None, on_drop=None, on_edit=None, tracker=None):
        self.job_id, self.company, self.role, self.status, self.notes, self.date_added = job_data
        
        super().__init__(
            parent, fg_color="#2a2a4a", corner_radius=10, 
            border_width=2, border_color=KANBAN_COLORS.get(self.status, "#555")
        )
        
        self.on_delete = on_delete
        self.on_drop = on_drop
        self.on_edit = on_edit
        self.tracker = tracker
        self.parent_column = parent
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
        self._ghost = None
        
        # Header with company name and menu
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=8, pady=(8, 4))
        
        # Drag handle
        self.drag_handle = ctk.CTkLabel(
            self.header, text="⋮⋮", font=("Arial", 12), 
            text_color="#666", width=20, cursor="fleur"
        )
        self.drag_handle.pack(side="left", padx=(0, 4))
        
        self.company_label = ctk.CTkLabel(
            self.header, text=self.company[:18] + ("..." if len(self.company) > 18 else ""),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"], anchor="w"
        )
        self.company_label.pack(side="left", fill="x", expand=True)
        
        # Delete button
        self.btn_delete = ctk.CTkButton(
            self.header, text="×", width=24, height=24,
            fg_color="transparent", hover_color="#e74c3c",
            text_color="#888", font=("Arial", 14, "bold"),
            corner_radius=12, command=self.delete_card
        )
        self.btn_delete.pack(side="right")
        
        # Role
        self.role_label = ctk.CTkLabel(
            self, text=self.role[:25] + ("..." if len(self.role) > 25 else ""),
            font=ctk.CTkFont(size=11),
            text_color="#aaa", anchor="w"
        )
        self.role_label.pack(fill="x", padx=8, pady=(0, 4))
        
        # Date
        self.date_label = ctk.CTkLabel(
            self, text=f"📅 {self.date_added}",
            font=ctk.CTkFont(size=10),
            text_color="#666", anchor="w"
        )
        self.date_label.pack(fill="x", padx=8, pady=(0, 8))
        
        # Bind drag events to drag handle
        self.drag_handle.bind("<Button-1>", self.start_drag)
        self.drag_handle.bind("<B1-Motion>", self.do_drag)
        self.drag_handle.bind("<ButtonRelease-1>", self.end_drag)
        
        # Double-click to edit
        self.bind("<Double-Button-1>", lambda e: self.edit_card())
        self.company_label.bind("<Double-Button-1>", lambda e: self.edit_card())
        self.role_label.bind("<Double-Button-1>", lambda e: self.edit_card())
    
    def start_drag(self, event):
        self._drag_data["dragging"] = True
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root
        
        # Highlight this card
        self.configure(border_color="#ffffff", border_width=3)
        
        # Notify tracker to show drop zones
        if self.tracker:
            self.tracker.show_drop_zones(self.status)
    
    def do_drag(self, event):
        if not self._drag_data["dragging"]:
            return
        
        # Update tracker's highlight based on mouse position
        if self.tracker:
            self.tracker.highlight_column_at(event.x_root, event.y_root)
    
    def end_drag(self, event):
        if not self._drag_data["dragging"]:
            return
        
        self._drag_data["dragging"] = False
        self.configure(border_color=KANBAN_COLORS.get(self.status, "#555"), border_width=2)
        
        # Find which column we're over
        if self.tracker:
            new_status = self.tracker.get_column_at(event.x_root, event.y_root)
            self.tracker.hide_drop_zones()
            
            if new_status and new_status != self.status:
                if self.on_drop:
                    self.on_drop(self.job_id, new_status)
    
    def delete_card(self):
        if self.on_delete:
            self.on_delete(self.job_id)
    
    def edit_card(self):
        if self.on_edit:
            self.on_edit(self.job_id)

class KanbanColumn(ctk.CTkFrame):
    """A column in the Kanban board."""
    def __init__(self, parent, status, color, on_delete=None, on_drop=None, on_edit=None, tracker=None):
        super().__init__(parent, fg_color=COLORS["bg_medium"], corner_radius=12)
        
        self.status = status
        self.color = color
        self.on_delete = on_delete
        self.on_drop = on_drop
        self.on_edit = on_edit
        self.tracker = tracker
        self.cards = []
        self._original_border = 0
        
        # Column header
        self.header = ctk.CTkFrame(self, fg_color=color, corner_radius=8, height=40)
        self.header.pack(fill="x", padx=8, pady=(8, 4))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text=status,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white"
        )
        self.title_label.pack(side="left", padx=12, pady=8)
        
        self.count_label = ctk.CTkLabel(
            self.header, text="0",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white", width=28,
            fg_color="#333333", corner_radius=10
        )
        self.count_label.pack(side="right", padx=8, pady=8)
        
        # Drop zone indicator (hidden by default)
        self.drop_indicator = ctk.CTkFrame(self, fg_color="transparent", height=4)
        self.drop_indicator.pack(fill="x", padx=8)
        
        # Scrollable card container
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#444",
            scrollbar_button_hover_color="#555"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=4, pady=4)
    
    def add_card(self, job_data):
        card = JobCard(
            self.scroll_frame, job_data,
            on_delete=self.on_delete,
            on_drop=self.on_drop,
            on_edit=self.on_edit,
            tracker=self.tracker
        )
        card.pack(fill="x", padx=4, pady=4)
        self.cards.append(card)
        self.update_count()
    
    def clear_cards(self):
        for card in self.cards:
            card.destroy()
        self.cards = []
        self.update_count()
    
    def update_count(self):
        self.count_label.configure(text=str(len(self.cards)))
    
    def highlight(self, active=True):
        if active:
            self.configure(border_width=3, border_color="#4ecca3")
            self.drop_indicator.configure(fg_color="#4ecca3")
        else:
            self.configure(border_width=0)
            self.drop_indicator.configure(fg_color="transparent")
    
    def show_drop_zone(self):
        self.configure(border_width=2, border_color="#555")
    
    def hide_drop_zone(self):
        self.configure(border_width=0)

class JobTrackerFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.statuses = ["To Apply", "Applied", "Interviewing", "Offer", "Rejected"]
        self.columns = {}
        self._current_drag_source = None
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="📋 Job Pipeline", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Drag hint
        self.hint_label = ctk.CTkLabel(
            self.header, text="⋮⋮ Drag cards to move", 
            font=ctk.CTkFont(size=11),
            text_color="#888"
        )
        self.hint_label.pack(side="left", padx=20, pady=15)
        
        # Add Job button in header
        self.btn_add = ctk.CTkButton(
            self.header, text="+ Add Job", 
            fg_color=COLORS["success"], hover_color="#3db389",
            font=ctk.CTkFont(weight="bold"), corner_radius=8,
            command=self.open_add_dialog
        )
        self.btn_add.pack(side="right", padx=20, pady=12)
        
        # Kanban board container
        self.board_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.board_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Configure grid for equal column widths
        for i in range(5):
            self.board_frame.grid_columnconfigure(i, weight=1, uniform="column")
        self.board_frame.grid_rowconfigure(0, weight=1)
        
        # Create columns
        for i, status in enumerate(self.statuses):
            column = KanbanColumn(
                self.board_frame, status, 
                KANBAN_COLORS[status],
                on_delete=self.delete_job,
                on_drop=self.drop_job,
                on_edit=self.edit_job,
                tracker=self
            )
            column.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            self.columns[status] = column
        
        self.load_data()
    
    def show_drop_zones(self, source_status):
        """Show drop zone indicators on all columns except source."""
        self._current_drag_source = source_status
        for status, column in self.columns.items():
            if status != source_status:
                column.show_drop_zone()
    
    def hide_drop_zones(self):
        """Hide all drop zone indicators."""
        self._current_drag_source = None
        for column in self.columns.values():
            column.hide_drop_zone()
            column.highlight(False)
    
    def highlight_column_at(self, x_root, y_root):
        """Highlight the column under the cursor."""
        for status, column in self.columns.items():
            if status == self._current_drag_source:
                continue
            
            # Get column's screen coordinates
            try:
                col_x = column.winfo_rootx()
                col_y = column.winfo_rooty()
                col_w = column.winfo_width()
                col_h = column.winfo_height()
                
                if col_x <= x_root <= col_x + col_w and col_y <= y_root <= col_y + col_h:
                    column.highlight(True)
                else:
                    column.highlight(False)
            except:
                pass
    
    def get_column_at(self, x_root, y_root):
        """Get the status of the column at the given screen coordinates."""
        for status, column in self.columns.items():
            try:
                col_x = column.winfo_rootx()
                col_y = column.winfo_rooty()
                col_w = column.winfo_width()
                col_h = column.winfo_height()
                
                if col_x <= x_root <= col_x + col_w and col_y <= y_root <= col_y + col_h:
                    return status
            except:
                pass
        return None
    
    def drop_job(self, job_id, new_status):
        """Handle dropping a job card into a new column."""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
        conn.commit()
        conn.close()
        self.load_data()

    def load_data(self):
        # Clear all columns
        for column in self.columns.values():
            column.clear_cards()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, company, role, status, notes, date_added FROM jobs")
        rows = c.fetchall()
        conn.close()
        
        for row in rows:
            status = row[3]
            if status in self.columns:
                self.columns[status].add_card(row)

    def open_add_dialog(self, prefill_status="To Apply"):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Job Application")
        dialog.geometry("450x500")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, text="Add New Application", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 15))
        
        form_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        form_frame.pack(fill="x", padx=30)
        
        ctk.CTkLabel(form_frame, text="Company", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_company = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_company.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Role", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_role = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_role.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Status", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        combo_status = ctk.CTkComboBox(
            form_frame, values=self.statuses, height=38, corner_radius=8
        )
        combo_status.set(prefill_status)
        combo_status.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Notes", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_notes = ctk.CTkTextbox(form_frame, height=80, corner_radius=8)
        entry_notes.pack(fill="x", pady=(0, 10))

        def save():
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            dt = datetime.datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO jobs (company, role, status, link, notes, date_added) VALUES (?,?,?,?,?,?)",
                      (entry_company.get(), entry_role.get(), combo_status.get(), "", entry_notes.get("0.0", "end").strip(), dt))
            conn.commit()
            conn.close()
            self.load_data()
            dialog.destroy()

        ctk.CTkButton(
            dialog, text="Save Application", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=42, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save
        ).pack(pady=20)

    def edit_job(self, job_id):
        # Fetch job data
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT company, role, status, notes FROM jobs WHERE id=?", (job_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Job Application")
        dialog.geometry("450x500")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, text="Edit Application", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 15))
        
        form_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        form_frame.pack(fill="x", padx=30)
        
        ctk.CTkLabel(form_frame, text="Company", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_company = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_company.insert(0, row[0])
        entry_company.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Role", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_role = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_role.insert(0, row[1])
        entry_role.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Status", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        combo_status = ctk.CTkComboBox(form_frame, values=self.statuses, height=38, corner_radius=8)
        combo_status.set(row[2])
        combo_status.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Notes", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_notes = ctk.CTkTextbox(form_frame, height=80, corner_radius=8)
        entry_notes.insert("0.0", row[3] if row[3] else "")
        entry_notes.pack(fill="x", pady=(0, 10))

        def save():
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE jobs SET company=?, role=?, status=?, notes=? WHERE id=?",
                      (entry_company.get(), entry_role.get(), combo_status.get(), entry_notes.get("0.0", "end").strip(), job_id))
            conn.commit()
            conn.close()
            self.load_data()
            dialog.destroy()

        ctk.CTkButton(
            dialog, text="Save Changes", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=42, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save
        ).pack(pady=20)

    def delete_job(self, job_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
        conn.close()
        self.load_data()

class WhiteboardFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="🎨 Whiteboard", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Tools Frame
        self.tool_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12, height=70)
        self.tool_frame.pack(fill="x", padx=20, pady=5)
        self.tool_frame.pack_propagate(False)
        
        self.mode_var = tk.StringVar(value="pinboard")
        
        # Left side - Mode buttons
        self.mode_frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        self.mode_frame.pack(side="left", padx=10, pady=10)
        
        self.btn_pinmode = ctk.CTkButton(
            self.mode_frame, text="📌 Pinboard", 
            fg_color=COLORS["warning"], hover_color="#e6ac00", text_color="#1a1a1a",
            corner_radius=8, width=110, font=ctk.CTkFont(weight="bold"),
            command=lambda: self.set_mode("pinboard")
        )
        self.btn_pinmode.pack(side="left", padx=2)

        self.btn_drawmode = ctk.CTkButton(
            self.mode_frame, text="✏️ Draw", 
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=8, width=90,
            command=lambda: self.set_mode("draw")
        )
        self.btn_drawmode.pack(side="left", padx=2)
        
        self.btn_eraser = ctk.CTkButton(
            self.mode_frame, text="🧹 Eraser", 
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=8, width=90,
            command=lambda: self.set_mode("eraser")
        )
        self.btn_eraser.pack(side="left", padx=2)
        
        # Separator
        self.sep1 = ctk.CTkFrame(self.tool_frame, fg_color="#555555", width=2)
        self.sep1.pack(side="left", fill="y", padx=10, pady=15)
        
        # Color picker for drawing
        self.color_frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        self.color_frame.pack(side="left", padx=5, pady=10)
        
        ctk.CTkLabel(self.color_frame, text="Pen:", text_color=COLORS["text"], font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 5))
        
        self.pen_colors = ["#ffffff", "#ff6b6b", "#4ecdc4", "#ffe66d", "#95e1d3", "#f38181", "#aa96da", "#fcbad3"]
        self.color_buttons = []
        self.draw_color = "#ffffff"
        
        for color in self.pen_colors:
            btn = ColorButton(
                self.color_frame, color, 
                command=lambda c=color: self.select_color(c),
                selected=(color == self.draw_color)
            )
            btn.pack(side="left", padx=2)
            self.color_buttons.append(btn)
        
        # Separator
        self.sep2 = ctk.CTkFrame(self.tool_frame, fg_color="#555555", width=2)
        self.sep2.pack(side="left", fill="y", padx=10, pady=15)
        
        # Brush size
        self.size_frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        self.size_frame.pack(side="left", padx=5, pady=10)
        
        ctk.CTkLabel(self.size_frame, text="Size:", text_color=COLORS["text"], font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 5))
        
        self.brush_size = 3
        self.size_slider = ctk.CTkSlider(
            self.size_frame, from_=1, to=20, number_of_steps=19,
            width=100, height=16, button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            command=self.set_brush_size
        )
        self.size_slider.set(3)
        self.size_slider.pack(side="left", padx=5)
        
        self.size_label = ctk.CTkLabel(self.size_frame, text="3px", text_color=COLORS["text"], width=35)
        self.size_label.pack(side="left")
        
        # Right side - Add note button
        self.btn_add_note = ctk.CTkButton(
            self.tool_frame, text="+ Add Note", 
            fg_color=COLORS["success"], hover_color="#3db389",
            corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=self.add_postit
        )
        self.btn_add_note.pack(side="right", padx=10, pady=10)
        
        # Note color picker
        self.note_color_frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        self.note_color_frame.pack(side="right", padx=5, pady=10)
        
        ctk.CTkLabel(self.note_color_frame, text="Note:", text_color=COLORS["text"], font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 5))
        
        self.note_colors = ["#fdfd96", "#ff9a9a", "#9ad0ff", "#c8ff9a", "#ffb899", "#d9b3ff"]
        self.note_color_buttons = []
        self.selected_note_color = "#fdfd96"
        
        for color in self.note_colors:
            btn = ColorButton(
                self.note_color_frame, color,
                command=lambda c=color: self.select_note_color(c),
                selected=(color == self.selected_note_color)
            )
            btn.pack(side="left", padx=2)
            self.note_color_buttons.append(btn)

        # Canvas Area
        self.canvas_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.canvas_frame.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#2d2d44", highlightthickness=0, cursor="arrow")
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Drawing Logic Variables
        self.old_x = None
        self.old_y = None
        self.eraser_size = 20
        
        # Bindings
        self.canvas.bind('<Button-1>', self.start_draw)
        self.canvas.bind('<B1-Motion>', self.draw)
        self.canvas.bind('<ButtonRelease-1>', self.reset_draw)
        
        # List to keep track of postits
        self.postits = []
    
    def select_color(self, color):
        self.draw_color = color
        for btn in self.color_buttons:
            btn.set_selected(btn.color == color)
    
    def select_note_color(self, color):
        self.selected_note_color = color
        for btn in self.note_color_buttons:
            btn.set_selected(btn.color == color)
    
    def set_brush_size(self, value):
        self.brush_size = int(value)
        self.size_label.configure(text=f"{self.brush_size}px")

    def set_mode(self, mode):
        self.mode_var.set(mode)
        # Reset all buttons
        self.btn_pinmode.configure(fg_color=COLORS["secondary"])
        self.btn_drawmode.configure(fg_color=COLORS["secondary"])
        self.btn_eraser.configure(fg_color=COLORS["secondary"])
        
        if mode == "draw":
            self.btn_drawmode.configure(fg_color=COLORS["accent"])
            self.canvas.config(cursor="pencil")
        elif mode == "eraser":
            self.btn_eraser.configure(fg_color=COLORS["purple"])
            self.canvas.config(cursor="circle")
        else:  # pinboard
            self.btn_pinmode.configure(fg_color=COLORS["warning"])
            self.canvas.config(cursor="arrow")

    def add_postit(self):
        if self.mode_var.get() not in ["pinboard"]:
            self.set_mode("pinboard")
            
        rx = random.randint(50, 400)
        ry = random.randint(50, 300)
        
        note = DraggablePostIt(
            self.canvas, x=rx, y=ry, 
            color=self.selected_note_color,
            on_delete=self.remove_postit
        )
        self.postits.append(note)
    
    def remove_postit(self, note):
        if note in self.postits:
            self.postits.remove(note)

    # --- Drawing Logic ---
    def start_draw(self, event):
        mode = self.mode_var.get()
        if mode == "draw":
            self.old_x = event.x
            self.old_y = event.y
        elif mode == "eraser":
            self.erase(event)

    def draw(self, event):
        mode = self.mode_var.get()
        if mode == "draw" and self.old_x:
            self.canvas.create_line(
                self.old_x, self.old_y, event.x, event.y, 
                width=self.brush_size, fill=self.draw_color,
                capstyle=tk.ROUND, smooth=True, tags="drawing"
            )
            self.old_x = event.x
            self.old_y = event.y
        elif mode == "eraser":
            self.erase(event)

    def erase(self, event):
        # Find and delete items near the cursor
        x, y = event.x, event.y
        size = self.eraser_size
        items = self.canvas.find_overlapping(x - size, y - size, x + size, y + size)
        for item in items:
            tags = self.canvas.gettags(item)
            if "drawing" in tags:
                self.canvas.delete(item)

    def reset_draw(self, event):
        self.old_x, self.old_y = None, None

class NotepadFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="📝 Quick Notes", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        self.btn_save = ctk.CTkButton(
            self.header, text="💾 Save", 
            fg_color=COLORS["success"], hover_color="#3db389",
            corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=self.save_notes
        )
        self.btn_save.pack(side="right", padx=20, pady=12)
        
        # Text area container
        self.text_container = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.text_container.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        
        self.text_area = ctk.CTkTextbox(
            self.text_container, 
            font=("Consolas", 14), wrap="word",
            fg_color="#1e1e2e", corner_radius=8,
            text_color=COLORS["text"]
        )
        self.text_area.pack(expand=True, fill="both", padx=10, pady=10)
        
        self.load_notes()
        
    def load_notes(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT content FROM notes WHERE id=1")
        content = c.fetchone()[0]
        conn.close()
        self.text_area.insert("0.0", content)
        
    def save_notes(self):
        content = self.text_area.get("0.0", "end")
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE notes SET content = ? WHERE id=1", (content,))
        conn.commit()
        conn.close()
        
        # Flash button to indicate save
        self.btn_save.configure(fg_color="#2ecc71", text="✓ Saved!")
        self.after(1500, lambda: self.btn_save.configure(fg_color=COLORS["success"], text="💾 Save"))

class FileStorageFrame(ctk.CTkFrame):
    """File storage for CVs, cover letters, and other documents."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.categories = ["All", "CV/Resume", "Cover Letter", "Portfolio", "Certificates", "Other"]
        self.current_category = "All"
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="📁 File Storage", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Upload button
        self.btn_upload = ctk.CTkButton(
            self.header, text="+ Upload File", 
            fg_color=COLORS["success"], hover_color="#3db389",
            font=ctk.CTkFont(weight="bold"), corner_radius=8,
            command=self.upload_file
        )
        self.btn_upload.pack(side="right", padx=20, pady=12)
        
        # Category filter
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        ctk.CTkLabel(
            self.filter_frame, text="Filter:", 
            text_color=COLORS["text"], font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 10))
        
        self.category_buttons = {}
        for cat in self.categories:
            btn = ctk.CTkButton(
                self.filter_frame, text=cat, 
                fg_color=COLORS["accent"] if cat == "All" else COLORS["secondary"],
                hover_color=COLORS["accent_hover"] if cat == "All" else "#1a4a7a",
                corner_radius=8, height=32, width=90,
                font=ctk.CTkFont(size=11),
                command=lambda c=cat: self.filter_by_category(c)
            )
            btn.pack(side="left", padx=3)
            self.category_buttons[cat] = btn
        
        # Main content area
        self.content_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Drop zone
        self.drop_zone = ctk.CTkFrame(
            self.content_frame, fg_color="#1e1e3a", corner_radius=12,
            border_width=2, border_color="#444"
        )
        self.drop_zone.pack(fill="x", padx=15, pady=15)
        
        self.drop_label = ctk.CTkLabel(
            self.drop_zone, 
            text="📥 Drag & Drop files here or click 'Upload File'\n\nSupported: PDF, DOC, DOCX, TXT, PNG, JPG",
            font=ctk.CTkFont(size=13),
            text_color="#888", justify="center"
        )
        self.drop_label.pack(pady=30)
        
        # Make drop zone clickable
        self.drop_zone.bind("<Button-1>", lambda e: self.upload_file())
        self.drop_label.bind("<Button-1>", lambda e: self.upload_file())
        
        # Files list
        self.files_scroll = ctk.CTkScrollableFrame(
            self.content_frame, fg_color="transparent",
            scrollbar_button_color="#444",
            scrollbar_button_hover_color="#555"
        )
        self.files_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.file_widgets = []
        self.load_files()
    
    def filter_by_category(self, category):
        self.current_category = category
        # Update button styles
        for cat, btn in self.category_buttons.items():
            if cat == category:
                btn.configure(fg_color=COLORS["accent"])
            else:
                btn.configure(fg_color=COLORS["secondary"])
        self.load_files()
    
    def upload_file(self):
        filetypes = [
            ("All supported", "*.pdf *.doc *.docx *.txt *.png *.jpg *.jpeg"),
            ("PDF files", "*.pdf"),
            ("Word documents", "*.doc *.docx"),
            ("Text files", "*.txt"),
            ("Images", "*.png *.jpg *.jpeg"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Select file to upload",
            filetypes=filetypes
        )
        
        if filepath:
            self.save_file(filepath)
    
    def save_file(self, filepath):
        # Open category selection dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Categorize File")
        dialog.geometry("350x250")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        filename = os.path.basename(filepath)
        
        ctk.CTkLabel(
            dialog, text="Categorize File", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog, text=f"File: {filename[:40]}{'...' if len(filename) > 40 else ''}", 
            font=ctk.CTkFont(size=12),
            text_color="#aaa"
        ).pack(pady=(0, 15))
        
        ctk.CTkLabel(dialog, text="Category:", text_color=COLORS["text"]).pack(anchor="w", padx=30)
        combo_category = ctk.CTkComboBox(
            dialog, values=self.categories[1:],  # Exclude "All"
            height=38, corner_radius=8, width=290
        )
        combo_category.set("Other")
        combo_category.pack(pady=(5, 20))
        
        def save():
            category = combo_category.get()
            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = os.path.splitext(filename)[1]
            new_filename = f"{timestamp}_{filename}"
            dest_path = os.path.join(FILES_FOLDER, new_filename)
            
            # Copy file
            try:
                shutil.copy2(filepath, dest_path)
                
                # Save to database
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO files (filename, original_name, category, date_added) VALUES (?,?,?,?)",
                    (new_filename, filename, category, datetime.datetime.now().strftime("%Y-%m-%d"))
                )
                conn.commit()
                conn.close()
                
                dialog.destroy()
                self.load_files()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {str(e)}")
        
        ctk.CTkButton(
            dialog, text="Save", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=40, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save
        ).pack(pady=10)
    
    def load_files(self):
        # Clear existing
        for widget in self.file_widgets:
            widget.destroy()
        self.file_widgets = []
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        if self.current_category == "All":
            c.execute("SELECT id, filename, original_name, category, date_added FROM files ORDER BY date_added DESC")
        else:
            c.execute("SELECT id, filename, original_name, category, date_added FROM files WHERE category=? ORDER BY date_added DESC", 
                     (self.current_category,))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            empty_label = ctk.CTkLabel(
                self.files_scroll, text="No files yet. Upload your first file!",
                text_color="#666", font=ctk.CTkFont(size=13)
            )
            empty_label.pack(pady=30)
            self.file_widgets.append(empty_label)
            return
        
        for row in rows:
            file_id, filename, original_name, category, date_added = row
            card = self.create_file_card(file_id, filename, original_name, category, date_added)
            self.file_widgets.append(card)
    
    def create_file_card(self, file_id, filename, original_name, category, date_added):
        # Determine icon based on extension
        ext = os.path.splitext(original_name)[1].lower()
        if ext == ".pdf":
            icon = "📄"
        elif ext in [".doc", ".docx"]:
            icon = "📝"
        elif ext in [".png", ".jpg", ".jpeg"]:
            icon = "🖼️"
        elif ext == ".txt":
            icon = "📃"
        else:
            icon = "📎"
        
        # Category colors
        cat_colors = {
            "CV/Resume": "#3498db",
            "Cover Letter": "#9b59b6",
            "Portfolio": "#e67e22",
            "Certificates": "#27ae60",
            "Other": "#95a5a6"
        }
        
        card = ctk.CTkFrame(self.files_scroll, fg_color="#2a2a4a", corner_radius=10, height=60)
        card.pack(fill="x", pady=4)
        card.pack_propagate(False)
        
        # Icon
        icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=24), width=50)
        icon_label.pack(side="left", padx=(15, 10))
        
        # File info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=8)
        
        name_label = ctk.CTkLabel(
            info_frame, 
            text=original_name[:45] + ("..." if len(original_name) > 45 else ""),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"], anchor="w"
        )
        name_label.pack(anchor="w")
        
        meta_label = ctk.CTkLabel(
            info_frame, 
            text=f"📅 {date_added}",
            font=ctk.CTkFont(size=10),
            text_color="#666", anchor="w"
        )
        meta_label.pack(anchor="w")
        
        # Category badge
        cat_badge = ctk.CTkLabel(
            card, text=category,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color=cat_colors.get(category, "#555"),
            corner_radius=6, width=80
        )
        cat_badge.pack(side="right", padx=10)
        
        # Open button
        btn_open = ctk.CTkButton(
            card, text="Open", width=60, height=30,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=6, font=ctk.CTkFont(size=11),
            command=lambda: self.open_file(filename)
        )
        btn_open.pack(side="right", padx=5)
        
        # Delete button
        btn_delete = ctk.CTkButton(
            card, text="🗑", width=30, height=30,
            fg_color="transparent", hover_color="#e74c3c",
            corner_radius=6, text_color="#888",
            command=lambda: self.delete_file(file_id, filename)
        )
        btn_delete.pack(side="right", padx=5)
        
        return card
    
    def open_file(self, filename):
        filepath = os.path.join(FILES_FOLDER, filename)
        if os.path.exists(filepath):
            os.startfile(filepath)  # Windows
        else:
            messagebox.showerror("Error", "File not found!")
    
    def delete_file(self, file_id, filename):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this file?"):
            # Delete from filesystem
            filepath = os.path.join(FILES_FOLDER, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Delete from database
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("DELETE FROM files WHERE id=?", (file_id,))
            conn.commit()
            conn.close()
            
            self.load_files()


class CalendarFrame(ctk.CTkFrame):
    """Calendar with reminders for job-related events."""
    def __init__(self, master, app=None):
        super().__init__(master, fg_color="transparent")
        
        self.app = app
        self.current_date = datetime.date.today()
        self.selected_date = None
        self.day_buttons = {}
        self.reminder_categories = ["Interview", "Deadline", "Follow-up", "Networking", "Other"]
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="📅 Calendar & Reminders", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Add reminder button
        self.btn_add = ctk.CTkButton(
            self.header, text="+ Add Reminder", 
            fg_color=COLORS["success"], hover_color="#3db389",
            font=ctk.CTkFont(weight="bold"), corner_radius=8,
            command=self.add_reminder_dialog
        )
        self.btn_add.pack(side="right", padx=20, pady=12)
        
        # Export to calendar button
        self.btn_export = ctk.CTkButton(
            self.header, text="📤 Export .ics", 
            fg_color=COLORS["purple"], hover_color=COLORS["purple_hover"],
            corner_radius=8, width=100,
            command=self.export_to_ics
        )
        self.btn_export.pack(side="right", padx=5, pady=12)
        
        # Main content
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.content_frame.grid_columnconfigure(0, weight=2)
        self.content_frame.grid_columnconfigure(1, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # Left side - Calendar
        self.calendar_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.calendar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        # Month navigation
        self.nav_frame = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=15, pady=15)
        
        self.btn_prev = ctk.CTkButton(
            self.nav_frame, text="◀", width=40, height=35,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=8, command=self.prev_month
        )
        self.btn_prev.pack(side="left")
        
        self.month_label = ctk.CTkLabel(
            self.nav_frame, text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.month_label.pack(side="left", expand=True)
        
        self.btn_next = ctk.CTkButton(
            self.nav_frame, text="▶", width=40, height=35,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=8, command=self.next_month
        )
        self.btn_next.pack(side="right")
        
        # Today button
        self.btn_today = ctk.CTkButton(
            self.nav_frame, text="Today", width=60, height=35,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            corner_radius=8, command=self.go_to_today
        )
        self.btn_today.pack(side="right", padx=10)
        
        # Days header
        self.days_header = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        self.days_header.pack(fill="x", padx=15)
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in days:
            lbl = ctk.CTkLabel(
                self.days_header, text=day,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#888", width=50
            )
            lbl.pack(side="left", expand=True)
        
        # Calendar grid
        self.grid_frame = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        
        # Right side - Reminders list
        self.reminders_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.reminders_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        
        self.reminders_title = ctk.CTkLabel(
            self.reminders_frame, text="📋 Upcoming Reminders",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        )
        self.reminders_title.pack(pady=(15, 10))
        
        self.reminders_scroll = ctk.CTkScrollableFrame(
            self.reminders_frame, fg_color="transparent",
            scrollbar_button_color="#444"
        )
        self.reminders_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 15))
        
        self.build_calendar()
        self.load_reminders()
        
        # Start reminder checker thread
        self.start_reminder_checker()
    
    def build_calendar(self):
        # Clear existing
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.day_buttons = {}
        
        # Update month label
        self.month_label.configure(
            text=self.current_date.strftime("%B %Y")
        )
        
        # Get calendar data
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self.current_date.year, self.current_date.month)
        
        # Get reminders for this month
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        month_start = f"{self.current_date.year}-{self.current_date.month:02d}-01"
        month_end = f"{self.current_date.year}-{self.current_date.month:02d}-31"
        c.execute("SELECT date FROM reminders WHERE date >= ? AND date <= ?", (month_start, month_end))
        reminder_dates = set([row[0] for row in c.fetchall()])
        conn.close()
        
        today = datetime.date.today()
        
        for week_idx, week in enumerate(month_days):
            week_frame = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
            week_frame.pack(fill="x", pady=2)
            
            for day_idx, day in enumerate(week):
                if day == 0:
                    # Empty cell
                    btn = ctk.CTkButton(
                        week_frame, text="", width=45, height=40,
                        fg_color="transparent", state="disabled"
                    )
                else:
                    date_str = f"{self.current_date.year}-{self.current_date.month:02d}-{day:02d}"
                    is_today = (self.current_date.year == today.year and 
                               self.current_date.month == today.month and 
                               day == today.day)
                    has_reminder = date_str in reminder_dates
                    
                    # Determine colors
                    if is_today:
                        fg = COLORS["accent"]
                        hover = COLORS["accent_hover"]
                    elif has_reminder:
                        fg = COLORS["success"]
                        hover = "#3db389"
                    else:
                        fg = "#2a2a4a"
                        hover = "#3a3a5a"
                    
                    btn = ctk.CTkButton(
                        week_frame, text=str(day), width=45, height=40,
                        fg_color=fg, hover_color=hover,
                        corner_radius=8,
                        font=ctk.CTkFont(size=12, weight="bold" if is_today or has_reminder else "normal"),
                        command=lambda d=day: self.select_date(d)
                    )
                    
                    # Add indicator dot for reminders
                    if has_reminder and not is_today:
                        btn.configure(text=f"{day}•")
                    
                    self.day_buttons[day] = btn
                
                btn.pack(side="left", expand=True, padx=1)
    
    def select_date(self, day):
        self.selected_date = datetime.date(self.current_date.year, self.current_date.month, day)
        self.add_reminder_dialog(prefill_date=self.selected_date)
    
    def prev_month(self):
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month - 1)
        self.build_calendar()
    
    def next_month(self):
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month + 1)
        self.build_calendar()
    
    def go_to_today(self):
        self.current_date = datetime.date.today()
        self.build_calendar()
    
    def add_reminder_dialog(self, prefill_date=None):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Reminder")
        dialog.geometry("400x450")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, text="Add Reminder", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 15))
        
        form_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        form_frame.pack(fill="x", padx=30)
        
        # Title
        ctk.CTkLabel(form_frame, text="Title", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_title = ctk.CTkEntry(form_frame, height=38, corner_radius=8, placeholder_text="e.g., Google Interview")
        entry_title.pack(fill="x", pady=(0, 5))
        
        # Date
        ctk.CTkLabel(form_frame, text="Date", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_date = ctk.CTkEntry(form_frame, height=38, corner_radius=8, placeholder_text="YYYY-MM-DD")
        if prefill_date:
            entry_date.insert(0, prefill_date.strftime("%Y-%m-%d"))
        else:
            entry_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        entry_date.pack(fill="x", pady=(0, 5))
        
        # Time
        ctk.CTkLabel(form_frame, text="Time", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_time = ctk.CTkEntry(form_frame, height=38, corner_radius=8, placeholder_text="HH:MM (24hr)")
        entry_time.insert(0, "09:00")
        entry_time.pack(fill="x", pady=(0, 5))
        
        # Category
        ctk.CTkLabel(form_frame, text="Category", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        combo_category = ctk.CTkComboBox(form_frame, values=self.reminder_categories, height=38, corner_radius=8)
        combo_category.set("Interview")
        combo_category.pack(fill="x", pady=(0, 5))
        
        # Description
        ctk.CTkLabel(form_frame, text="Description (optional)", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_desc = ctk.CTkEntry(form_frame, height=38, corner_radius=8, placeholder_text="Additional notes...")
        entry_desc.pack(fill="x", pady=(0, 10))
        
        def save():
            title = entry_title.get().strip()
            date = entry_date.get().strip()
            time_val = entry_time.get().strip()
            category = combo_category.get()
            desc = entry_desc.get().strip()
            
            if not title or not date:
                messagebox.showwarning("Warning", "Please enter a title and date")
                return
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO reminders (title, description, date, time, category) VALUES (?,?,?,?,?)",
                (title, desc, date, time_val, category)
            )
            conn.commit()
            conn.close()
            
            dialog.destroy()
            self.build_calendar()
            self.load_reminders()
        
        ctk.CTkButton(
            dialog, text="Save Reminder", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=42, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save
        ).pack(pady=20)
    
    def load_reminders(self):
        # Clear existing
        for widget in self.reminders_scroll.winfo_children():
            widget.destroy()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        today = datetime.date.today().strftime("%Y-%m-%d")
        c.execute("SELECT id, title, description, date, time, category FROM reminders WHERE date >= ? ORDER BY date, time LIMIT 15", (today,))
        reminders = c.fetchall()
        conn.close()
        
        if not reminders:
            ctk.CTkLabel(
                self.reminders_scroll, text="No upcoming reminders.\nClick a date to add one!",
                text_color="#666", font=ctk.CTkFont(size=12)
            ).pack(pady=30)
            return
        
        cat_colors = {
            "Interview": "#9b59b6",
            "Deadline": "#e74c3c",
            "Follow-up": "#f39c12",
            "Networking": "#3498db",
            "Other": "#95a5a6"
        }
        
        for rem_id, title, desc, date, time_val, category in reminders:
            card = ctk.CTkFrame(self.reminders_scroll, fg_color="#2a2a4a", corner_radius=8)
            card.pack(fill="x", pady=4)
            
            # Color indicator
            indicator = ctk.CTkFrame(card, fg_color=cat_colors.get(category, "#555"), width=4, corner_radius=2)
            indicator.pack(side="left", fill="y", padx=(0, 8), pady=5)
            
            # Content
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, pady=8)
            
            ctk.CTkLabel(
                content, text=title[:25] + ("..." if len(title) > 25 else ""),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS["text"], anchor="w"
            ).pack(anchor="w")
            
            ctk.CTkLabel(
                content, text=f"📅 {date} ⏰ {time_val}",
                font=ctk.CTkFont(size=10),
                text_color="#888", anchor="w"
            ).pack(anchor="w")
            
            # Delete button
            btn_del = ctk.CTkButton(
                card, text="×", width=25, height=25,
                fg_color="transparent", hover_color="#e74c3c",
                text_color="#666", corner_radius=12,
                command=lambda r=rem_id: self.delete_reminder(r)
            )
            btn_del.pack(side="right", padx=5, pady=5)
    
    def delete_reminder(self, reminder_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        conn.commit()
        conn.close()
        self.build_calendar()
        self.load_reminders()
    
    def export_to_ics(self):
        """Export reminders to .ics file for calendar apps."""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT title, description, date, time, category FROM reminders ORDER BY date")
        reminders = c.fetchall()
        conn.close()
        
        if not reminders:
            messagebox.showinfo("Info", "No reminders to export!")
            return
        
        # Build ICS content
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CareerBuddy//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
"""
        
        for title, desc, date, time_val, category in reminders:
            # Parse date and time
            try:
                dt = datetime.datetime.strptime(f"{date} {time_val}", "%Y-%m-%d %H:%M")
                dt_str = dt.strftime("%Y%m%dT%H%M%S")
                dt_end = (dt + datetime.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")
            except:
                continue
            
            ics_content += f"""BEGIN:VEVENT
DTSTART:{dt_str}
DTEND:{dt_end}
SUMMARY:{title}
DESCRIPTION:{desc} [Category: {category}]
END:VEVENT
"""
        
        ics_content += "END:VCALENDAR"
        
        # Save file
        filepath = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics")],
            initialfilename="careerbuddy_reminders.ics"
        )
        
        if filepath:
            with open(filepath, "w") as f:
                f.write(ics_content)
            messagebox.showinfo("Success", f"Exported {len(reminders)} reminders to:\n{filepath}\n\nImport this file into Google Calendar, Outlook, or Apple Calendar.")
    
    def start_reminder_checker(self):
        """Start background thread to check for upcoming reminders."""
        def check_reminders():
            while True:
                try:
                    now = datetime.datetime.now()
                    check_time = now + datetime.timedelta(minutes=15)
                    
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute(
                        "SELECT id, title, date, time, category FROM reminders WHERE date=? AND time<=? AND time>=? AND notified=0",
                        (now.strftime("%Y-%m-%d"), check_time.strftime("%H:%M"), now.strftime("%H:%M"))
                    )
                    upcoming = c.fetchall()
                    
                    for rem_id, title, date, time_val, category in upcoming:
                        # Send notification
                        try:
                            notification.notify(
                                title=f"🔔 CareerBuddy Reminder",
                                message=f"{title}\n{category} at {time_val}",
                                app_name="CareerBuddy",
                                timeout=10
                            )
                        except:
                            pass
                        
                        # Mark as notified
                        c.execute("UPDATE reminders SET notified=1 WHERE id=?", (rem_id,))
                    
                    conn.commit()
                    conn.close()
                except:
                    pass
                
                time.sleep(60)  # Check every minute
        
        thread = threading.Thread(target=check_reminders, daemon=True)
        thread.start()


class AnalyticsDashboardFrame(ctk.CTkFrame):
    """Analytics dashboard showing job application statistics."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["secondary"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="📊 Analytics Dashboard", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Refresh button
        self.btn_refresh = ctk.CTkButton(
            self.header, text="↻ Refresh", width=100,
            fg_color=COLORS["success"], hover_color="#3db389",
            corner_radius=8, command=self.refresh_stats
        )
        self.btn_refresh.pack(side="right", padx=20, pady=12)
        
        # Stats cards row
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Configure grid for equal card widths
        for i in range(5):
            self.stats_frame.grid_columnconfigure(i, weight=1, uniform="stat")
        
        self.stat_cards = {}
        stat_configs = [
            ("total", "Total Apps", "📋", "#3498db"),
            ("applied", "Applied", "📤", "#f39c12"),
            ("interviewing", "Interviewing", "🎤", "#9b59b6"),
            ("offers", "Offers", "🎉", "#27ae60"),
            ("rejected", "Rejected", "❌", "#e74c3c"),
        ]
        
        for i, (key, title, icon, color) in enumerate(stat_configs):
            card = self.create_stat_card(title, icon, color, "0")
            card.grid(row=0, column=i, sticky="nsew", padx=5, pady=5)
            self.stat_cards[key] = card
        
        # Charts area
        self.charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.charts_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)
        self.charts_frame.grid_rowconfigure(0, weight=1)
        
        # Status breakdown chart
        self.status_chart = ctk.CTkFrame(self.charts_frame, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.status_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        ctk.CTkLabel(
            self.status_chart, text="📊 Status Breakdown",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(15, 10))
        
        self.status_bars_frame = ctk.CTkFrame(self.status_chart, fg_color="transparent")
        self.status_bars_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Recent activity
        self.activity_chart = ctk.CTkFrame(self.charts_frame, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.activity_chart.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        ctk.CTkLabel(
            self.activity_chart, text="📅 Recent Applications",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(15, 10))
        
        self.activity_scroll = ctk.CTkScrollableFrame(
            self.activity_chart, fg_color="transparent",
            scrollbar_button_color="#444"
        )
        self.activity_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 15))
        
        # Response rate card
        self.response_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12, height=100)
        self.response_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.response_frame.pack_propagate(False)
        
        self.response_content = ctk.CTkFrame(self.response_frame, fg_color="transparent")
        self.response_content.pack(fill="both", expand=True, padx=20, pady=15)
        
        self.refresh_stats()
    
    def create_stat_card(self, title, icon, color, value):
        card = ctk.CTkFrame(self.stats_frame, fg_color=COLORS["bg_medium"], corner_radius=12, height=100)
        card.pack_propagate(False)
        
        # Icon and value row
        top_frame = ctk.CTkFrame(card, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        icon_label = ctk.CTkLabel(top_frame, text=icon, font=ctk.CTkFont(size=24))
        icon_label.pack(side="left")
        
        value_label = ctk.CTkLabel(
            top_frame, text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=color
        )
        value_label.pack(side="right")
        card.value_label = value_label
        
        # Title
        title_label = ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=12),
            text_color="#888"
        )
        title_label.pack(anchor="w", padx=15)
        
        return card
    
    def refresh_stats(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Get counts by status
        c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
        status_counts = dict(c.fetchall())
        
        total = sum(status_counts.values())
        applied = status_counts.get("Applied", 0)
        interviewing = status_counts.get("Interviewing", 0)
        offers = status_counts.get("Offer", 0)
        rejected = status_counts.get("Rejected", 0)
        to_apply = status_counts.get("To Apply", 0)
        
        # Update stat cards
        self.stat_cards["total"].value_label.configure(text=str(total))
        self.stat_cards["applied"].value_label.configure(text=str(applied))
        self.stat_cards["interviewing"].value_label.configure(text=str(interviewing))
        self.stat_cards["offers"].value_label.configure(text=str(offers))
        self.stat_cards["rejected"].value_label.configure(text=str(rejected))
        
        # Update status bars
        for widget in self.status_bars_frame.winfo_children():
            widget.destroy()
        
        statuses = [
            ("To Apply", to_apply, "#3498db"),
            ("Applied", applied, "#f39c12"),
            ("Interviewing", interviewing, "#9b59b6"),
            ("Offer", offers, "#27ae60"),
            ("Rejected", rejected, "#e74c3c"),
        ]
        
        max_count = max([s[1] for s in statuses]) if total > 0 else 1
        
        for status, count, color in statuses:
            row = ctk.CTkFrame(self.status_bars_frame, fg_color="transparent", height=35)
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)
            
            # Label
            ctk.CTkLabel(
                row, text=status, width=100,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text"], anchor="w"
            ).pack(side="left")
            
            # Bar background
            bar_bg = ctk.CTkFrame(row, fg_color="#333", corner_radius=4, height=20)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(10, 10))
            
            # Bar fill
            fill_width = (count / max_count) if max_count > 0 else 0
            if fill_width > 0:
                bar_fill = ctk.CTkFrame(bar_bg, fg_color=color, corner_radius=4)
                bar_fill.place(relx=0, rely=0.1, relwidth=fill_width, relheight=0.8)
            
            # Count
            ctk.CTkLabel(
                row, text=str(count), width=40,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=color
            ).pack(side="right")
        
        # Update recent activity
        for widget in self.activity_scroll.winfo_children():
            widget.destroy()
        
        c.execute("SELECT company, role, status, date_added FROM jobs ORDER BY date_added DESC LIMIT 10")
        recent = c.fetchall()
        
        if not recent:
            ctk.CTkLabel(
                self.activity_scroll, text="No applications yet.\nStart tracking your job search!",
                text_color="#666", font=ctk.CTkFont(size=12)
            ).pack(pady=30)
        else:
            for company, role, status, date in recent:
                item = ctk.CTkFrame(self.activity_scroll, fg_color="#2a2a4a", corner_radius=8, height=50)
                item.pack(fill="x", pady=3)
                item.pack_propagate(False)
                
                # Status indicator
                status_color = KANBAN_COLORS.get(status, "#555")
                indicator = ctk.CTkFrame(item, fg_color=status_color, width=4, corner_radius=2)
                indicator.pack(side="left", fill="y", padx=(0, 10), pady=5)
                
                # Info
                info = ctk.CTkFrame(item, fg_color="transparent")
                info.pack(side="left", fill="both", expand=True, pady=5)
                
                ctk.CTkLabel(
                    info, text=company[:25] + ("..." if len(company) > 25 else ""),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COLORS["text"], anchor="w"
                ).pack(anchor="w")
                
                ctk.CTkLabel(
                    info, text=f"{role[:20]}... • {date}" if len(role) > 20 else f"{role} • {date}",
                    font=ctk.CTkFont(size=10),
                    text_color="#666", anchor="w"
                ).pack(anchor="w")
        
        # Update response rate
        for widget in self.response_content.winfo_children():
            widget.destroy()
        
        # Calculate response rate (interviews + offers) / (applied + interviewing + offers + rejected)
        submitted = applied + interviewing + offers + rejected
        responses = interviewing + offers
        response_rate = (responses / submitted * 100) if submitted > 0 else 0
        
        # Success rate (offers / submitted)
        success_rate = (offers / submitted * 100) if submitted > 0 else 0
        
        # Left side - Response rate
        left = ctk.CTkFrame(self.response_content, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(
            left, text="📈 Response Rate",
            font=ctk.CTkFont(size=12),
            text_color="#888"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            left, text=f"{response_rate:.1f}%",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["success"] if response_rate > 20 else COLORS["warning"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            left, text=f"{responses} responses from {submitted} applications",
            font=ctk.CTkFont(size=10),
            text_color="#666"
        ).pack(anchor="w")
        
        # Right side - Success rate
        right = ctk.CTkFrame(self.response_content, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True)
        
        ctk.CTkLabel(
            right, text="🎯 Success Rate",
            font=ctk.CTkFont(size=12),
            text_color="#888"
        ).pack(anchor="e")
        
        ctk.CTkLabel(
            right, text=f"{success_rate:.1f}%",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["success"] if success_rate > 5 else "#888"
        ).pack(anchor="e")
        
        ctk.CTkLabel(
            right, text=f"{offers} offers received",
            font=ctk.CTkFont(size=10),
            text_color="#666"
        ).pack(anchor="e")
        
        conn.close()


class CoverLetterFrame(ctk.CTkFrame):
    """AI-powered cover letter generator."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.model = None
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color="#2ecc71", corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="✉️ Cover Letter Generator", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="white"
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Status
        self.status_label = ctk.CTkLabel(
            self.header, text="", font=ctk.CTkFont(size=11), text_color="#ddd"
        )
        self.status_label.pack(side="right", padx=20, pady=15)
        
        # Main content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        
        # Left side - Input
        self.input_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.input_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        ctk.CTkLabel(
            self.input_frame, text="📋 Job Description",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(15, 5), padx=15, anchor="w")
        
        ctk.CTkLabel(
            self.input_frame, text="Paste the job description here:",
            font=ctk.CTkFont(size=11), text_color="#888"
        ).pack(padx=15, anchor="w")
        
        self.job_desc_input = ctk.CTkTextbox(
            self.input_frame, fg_color="#1e1e2e", corner_radius=8,
            font=("Segoe UI", 11), text_color=COLORS["text"]
        )
        self.job_desc_input.pack(fill="both", expand=True, padx=15, pady=(10, 15))
        
        # Your info section
        self.info_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(
            self.info_frame, text="Your Name:",
            font=ctk.CTkFont(size=11), text_color=COLORS["text"]
        ).pack(side="left")
        
        self.name_entry = ctk.CTkEntry(self.info_frame, width=150, height=32, corner_radius=6)
        self.name_entry.pack(side="left", padx=(10, 20))
        
        ctk.CTkLabel(
            self.info_frame, text="Key Skills (comma-separated):",
            font=ctk.CTkFont(size=11), text_color=COLORS["text"]
        ).pack(side="left")
        
        self.skills_entry = ctk.CTkEntry(self.info_frame, width=200, height=32, corner_radius=6)
        self.skills_entry.pack(side="left", padx=10)
        
        # Generate button
        self.btn_generate = ctk.CTkButton(
            self.input_frame, text="✨ Generate Cover Letter",
            fg_color=COLORS["success"], hover_color="#3db389",
            height=45, corner_radius=8, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.generate_cover_letter
        )
        self.btn_generate.pack(fill="x", padx=15, pady=(0, 15))
        
        # Right side - Output
        self.output_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.output_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        output_header = ctk.CTkFrame(self.output_frame, fg_color="transparent")
        output_header.pack(fill="x", padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            output_header, text="✉️ Generated Cover Letter",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")
        
        self.btn_copy = ctk.CTkButton(
            output_header, text="📋 Copy", width=70, height=30,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=6, command=self.copy_to_clipboard
        )
        self.btn_copy.pack(side="right")
        
        self.output_text = ctk.CTkTextbox(
            self.output_frame, fg_color="#1e1e2e", corner_radius=8,
            font=("Segoe UI", 11), text_color=COLORS["text"]
        )
        self.output_text.pack(fill="both", expand=True, padx=15, pady=(10, 15))
        self.output_text.insert("0.0", "Your generated cover letter will appear here...\n\nTips:\n• Paste the full job description\n• Add your name and key skills\n• Click 'Generate' to create a personalized cover letter")
        
        self.initialize_ai()
    
    def initialize_ai(self):
        if not GEMINI_AVAILABLE:
            self.status_label.configure(text="⚠️ AI not available")
            return
        
        api_key = get_api_key()
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model_name='gemini-2.0-flash')
                self.status_label.configure(text="✅ AI Ready")
            except:
                self.status_label.configure(text="❌ API Error")
        else:
            self.status_label.configure(text="🔑 Set API key in AI Buddy tab")
    
    def generate_cover_letter(self):
        job_desc = self.job_desc_input.get("0.0", "end").strip()
        name = self.name_entry.get().strip() or "Your Name"
        skills = self.skills_entry.get().strip() or "relevant skills"
        
        if not job_desc or len(job_desc) < 50:
            messagebox.showwarning("Warning", "Please paste a job description (at least 50 characters)")
            return
        
        if not self.model:
            self.initialize_ai()
            if not self.model:
                messagebox.showerror("Error", "AI not available. Please set up your API key in the AI Buddy tab.")
                return
        
        self.btn_generate.configure(state="disabled", text="Generating...")
        self.output_text.delete("0.0", "end")
        self.output_text.insert("0.0", "Generating your cover letter...")
        
        def generate():
            try:
                prompt = f"""Generate a professional cover letter for the following job. 
                
The applicant's name is: {name}
Their key skills include: {skills}

Job Description:
{job_desc}

Write a compelling, personalized cover letter that:
1. Opens with enthusiasm for the specific role and company
2. Highlights relevant skills and experiences that match the job requirements
3. Shows knowledge of the company (infer from the job description)
4. Includes specific examples where possible
5. Ends with a strong call to action

Keep it professional but personable, around 300-400 words. Do not use placeholder text like [Company Name] - instead, use what you can infer from the job description or write it generically if unknown."""

                response = self.model.generate_content(prompt)
                self.after(0, lambda: self.show_result(response.text))
            except Exception as e:
                self.after(0, lambda: self.show_error(str(e)))
        
        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
    
    def show_result(self, text):
        self.output_text.delete("0.0", "end")
        self.output_text.insert("0.0", text)
        self.btn_generate.configure(state="normal", text="✨ Generate Cover Letter")
    
    def show_error(self, error):
        self.output_text.delete("0.0", "end")
        self.output_text.insert("0.0", f"Error generating cover letter:\n{error}")
        self.btn_generate.configure(state="normal", text="✨ Generate Cover Letter")
    
    def copy_to_clipboard(self):
        text = self.output_text.get("0.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.btn_copy.configure(text="✓ Copied!")
        self.after(2000, lambda: self.btn_copy.configure(text="📋 Copy"))


class JobCatcherFrame(ctk.CTkFrame):
    """Capture jobs from Indeed, LinkedIn, and other sites."""
    def __init__(self, master, app=None):
        super().__init__(master, fg_color="transparent")
        
        self.app = app
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color="#e67e22", corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="🎣 Job Catcher", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="white"
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Main content
        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Instructions
        self.instructions = ctk.CTkFrame(self.content, fg_color="#1e1e3a", corner_radius=10)
        self.instructions.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(
            self.instructions, text="📖 How to Capture Jobs from Websites",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(15, 10))
        
        instructions_text = """Method 1: Quick Add (Manual)
• Copy the job details from any website
• Paste them below and click 'Parse & Add Job'

Method 2: Browser Bookmarklet
• Drag the button below to your bookmarks bar
• When viewing a job on Indeed/LinkedIn, click the bookmarklet
• It will copy job details - then paste here

Supported Sites: Indeed, LinkedIn, Glassdoor, Monster, and more!"""
        
        ctk.CTkLabel(
            self.instructions, text=instructions_text,
            font=ctk.CTkFont(size=12),
            text_color="#aaa", justify="left"
        ).pack(padx=20, pady=(0, 15))
        
        # Bookmarklet section
        self.bookmarklet_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.bookmarklet_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(
            self.bookmarklet_frame, text="🔖 Bookmarklet (drag to bookmarks bar):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w")
        
        # Bookmarklet code display
        bookmarklet_code = """javascript:(function(){var t=document.title||'';var c='';var r='';var l=window.location.href;if(l.includes('indeed.com')){c=document.querySelector('[data-company]')?.innerText||document.querySelector('.jobsearch-CompanyInfoWithoutHeaderImage')?.innerText||'';r=document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"]')?.innerText||document.querySelector('.jobsearch-JobInfoHeader-title')?.innerText||t;}else if(l.includes('linkedin.com')){c=document.querySelector('.job-details-jobs-unified-top-card__company-name')?.innerText||'';r=document.querySelector('.job-details-jobs-unified-top-card__job-title')?.innerText||t;}else{c=t.split('-')[1]?.trim()||'';r=t.split('-')[0]?.trim()||t;}var d='CAREERBUDDY_JOB:\\nCompany: '+c+'\\nRole: '+r+'\\nURL: '+l;prompt('Copy this and paste in CareerBuddy Job Catcher:',d);})();"""
        
        self.bookmarklet_btn = ctk.CTkButton(
            self.bookmarklet_frame, text="📎 CareerBuddy Capture",
            fg_color="#3498db", hover_color="#2980b9",
            height=35, corner_radius=8
        )
        self.bookmarklet_btn.pack(anchor="w", pady=10)
        
        ctk.CTkLabel(
            self.bookmarklet_frame, 
            text="💡 Can't drag? Copy this code and create a bookmark manually:",
            font=ctk.CTkFont(size=10), text_color="#666"
        ).pack(anchor="w")
        
        self.code_display = ctk.CTkTextbox(
            self.bookmarklet_frame, height=60, fg_color="#1e1e2e",
            font=("Consolas", 9), text_color="#888"
        )
        self.code_display.pack(fill="x", pady=5)
        self.code_display.insert("0.0", bookmarklet_code)
        
        btn_copy_code = ctk.CTkButton(
            self.bookmarklet_frame, text="Copy Bookmarklet Code", width=160, height=30,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            corner_radius=6, command=lambda: self.copy_code(bookmarklet_code)
        )
        btn_copy_code.pack(anchor="w")
        
        # Paste area
        self.paste_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.paste_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        ctk.CTkLabel(
            self.paste_frame, text="📋 Paste Job Details Here:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", pady=(0, 5))
        
        self.paste_input = ctk.CTkTextbox(
            self.paste_frame, fg_color="#1e1e2e", corner_radius=8,
            font=("Segoe UI", 11), text_color=COLORS["text"], height=150
        )
        self.paste_input.pack(fill="both", expand=True, pady=(0, 10))
        self.paste_input.insert("0.0", "Paste job details here...\n\nFormat (from bookmarklet):\nCAREERBUDDY_JOB:\nCompany: Company Name\nRole: Job Title\nURL: https://...\n\nOr just paste any text with company/role info and we'll try to parse it!")
        
        # Parse button
        btn_frame = ctk.CTkFrame(self.paste_frame, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        self.btn_parse = ctk.CTkButton(
            btn_frame, text="🎯 Parse & Add to Job Tracker",
            fg_color=COLORS["success"], hover_color="#3db389",
            height=45, corner_radius=8, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.parse_and_add
        )
        self.btn_parse.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_clear = ctk.CTkButton(
            btn_frame, text="Clear", width=80,
            fg_color=COLORS["secondary"], hover_color="#1a4a7a",
            height=45, corner_radius=8,
            command=lambda: self.paste_input.delete("0.0", "end")
        )
        self.btn_clear.pack(side="right")
    
    def copy_code(self, code):
        self.clipboard_clear()
        self.clipboard_append(code)
        messagebox.showinfo("Copied", "Bookmarklet code copied! Create a new bookmark and paste this as the URL.")
    
    def parse_and_add(self):
        text = self.paste_input.get("0.0", "end").strip()
        
        if not text or text.startswith("Paste job details"):
            messagebox.showwarning("Warning", "Please paste job details first")
            return
        
        company = ""
        role = ""
        url = ""
        
        # Try to parse structured format
        if "CAREERBUDDY_JOB:" in text:
            lines = text.split("\n")
            for line in lines:
                if line.startswith("Company:"):
                    company = line.replace("Company:", "").strip()
                elif line.startswith("Role:"):
                    role = line.replace("Role:", "").strip()
                elif line.startswith("URL:"):
                    url = line.replace("URL:", "").strip()
        else:
            # Try to extract from plain text
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if lines:
                # First non-empty line might be role
                role = lines[0][:100] if lines else "Unknown Role"
                # Look for company patterns
                for line in lines:
                    if "company" in line.lower() or "at " in line.lower():
                        parts = line.split(" at ")
                        if len(parts) > 1:
                            company = parts[1].strip()[:100]
                            break
                if not company and len(lines) > 1:
                    company = lines[1][:100]
        
        # Open dialog to confirm/edit
        self.open_confirm_dialog(company, role, url)
    
    def open_confirm_dialog(self, company, role, url):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Job Details")
        dialog.geometry("450x400")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, text="Confirm Job Details", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 15))
        
        form_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        form_frame.pack(fill="x", padx=30)
        
        ctk.CTkLabel(form_frame, text="Company", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_company = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_company.insert(0, company)
        entry_company.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Role", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_role = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_role.insert(0, role)
        entry_role.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="Status", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        combo_status = ctk.CTkComboBox(
            form_frame, values=["To Apply", "Applied", "Interviewing", "Offer", "Rejected"],
            height=38, corner_radius=8
        )
        combo_status.set("To Apply")
        combo_status.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(form_frame, text="URL/Notes", text_color=COLORS["text"], anchor="w").pack(fill="x", pady=(10, 2))
        entry_notes = ctk.CTkEntry(form_frame, height=38, corner_radius=8)
        entry_notes.insert(0, url)
        entry_notes.pack(fill="x", pady=(0, 10))
        
        def save():
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            dt = datetime.datetime.now().strftime("%Y-%m-%d")
            c.execute(
                "INSERT INTO jobs (company, role, status, link, notes, date_added) VALUES (?,?,?,?,?,?)",
                (entry_company.get(), entry_role.get(), combo_status.get(), "", entry_notes.get(), dt)
            )
            conn.commit()
            conn.close()
            
            dialog.destroy()
            self.paste_input.delete("0.0", "end")
            messagebox.showinfo("Success", f"Added '{entry_role.get()}' at '{entry_company.get()}' to Job Tracker!")
        
        ctk.CTkButton(
            dialog, text="Add to Job Tracker", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=42, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save
        ).pack(pady=20)


class AIBuddyFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.chat_history = []
        self.model = None
        self.chat = None
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["purple"], corner_radius=12, height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="🤖 AI Career Buddy", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Settings button
        self.btn_settings = ctk.CTkButton(
            self.header, text="⚙️ API Key", width=100,
            fg_color=COLORS["purple_hover"], hover_color="#4a1172",
            corner_radius=8, command=self.open_settings
        )
        self.btn_settings.pack(side="right", padx=20, pady=12)
        
        # Status indicator
        self.status_label = ctk.CTkLabel(
            self.header, text="", 
            font=ctk.CTkFont(size=11),
            text_color="#aaa"
        )
        self.status_label.pack(side="right", padx=10, pady=15)
        
        # Chat container
        self.chat_container = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12)
        self.chat_container.pack(expand=True, fill="both", padx=20, pady=(0, 10))
        
        self.chat_display = ctk.CTkTextbox(
            self.chat_container, state="disabled", 
            font=("Segoe UI", 12),
            fg_color="#1e1e2e", corner_radius=8,
            text_color=COLORS["text"]
        )
        self.chat_display.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Input area
        self.input_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=12, height=60)
        self.input_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.input_frame.pack_propagate(False)
        
        self.entry_msg = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Ask CareerBuddy for advice...",
            height=40, corner_radius=8,
            font=("Segoe UI", 12)
        )
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=(10, 10), pady=10)
        self.entry_msg.bind("<Return>", lambda event: self.send_message())
        
        self.btn_send = ctk.CTkButton(
            self.input_frame, text="Send →", width=80,
            fg_color=COLORS["purple"], hover_color=COLORS["purple_hover"],
            corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=self.send_message
        )
        self.btn_send.pack(side="right", padx=(0, 10), pady=10)
        
        # Initialize AI
        self.initialize_ai()

    def initialize_ai(self):
        """Initialize the Gemini AI model."""
        if not GEMINI_AVAILABLE:
            self.status_label.configure(text="⚠️ Gemini not installed")
            self.append_message("System", "Google Gemini library not found. Please run: pip install google-generativeai")
            return
        
        api_key = get_api_key()
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(
                    model_name='gemini-2.0-flash',
                    system_instruction=CAREER_BUDDY_SYSTEM_PROMPT
                )
                self.chat = self.model.start_chat(history=[])
                self.status_label.configure(text="✅ AI Connected")
                self.append_message("Buddy", "Hi! I'm CareerBuddy, your AI career advisor! 🎓\n\nI'm powered by Google Gemini and ready to help you with:\n• CV/Resume writing\n• Interview preparation\n• Job search strategies\n• Career planning\n• Motivation when things get tough\n\nWhat can I help you with today?")
            except Exception as e:
                self.status_label.configure(text="❌ API Error")
                self.append_message("System", f"Failed to connect to Gemini API. Please check your API key.\nError: {str(e)}")
        else:
            self.status_label.configure(text="🔑 API Key needed")
            self.append_message("Buddy", "Welcome to CareerBuddy! 🎓\n\nTo unlock AI-powered career advice, you'll need to set up a free Gemini API key:\n\n1. Click '⚙️ API Key' button above\n2. Get your free key from Google AI Studio\n3. Paste it and click Save\n\nOnce connected, I can help with CVs, interviews, job searching, and more!")

    def open_settings(self):
        """Open API key settings dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("AI Settings")
        dialog.geometry("500x300")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, text="🔑 Gemini API Key Setup", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog, 
            text="Get your free API key from Google AI Studio:\nhttps://makersuite.google.com/app/apikey",
            font=ctk.CTkFont(size=12),
            text_color="#aaa"
        ).pack(pady=(0, 15))
        
        # API Key entry
        entry_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        entry_frame.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(entry_frame, text="API Key:", text_color=COLORS["text"]).pack(anchor="w")
        api_entry = ctk.CTkEntry(entry_frame, height=40, corner_radius=8, show="•")
        api_entry.pack(fill="x", pady=(5, 0))
        
        # Pre-fill if key exists
        existing_key = get_api_key()
        if existing_key:
            api_entry.insert(0, existing_key)
        
        def save_key():
            key = api_entry.get().strip()
            if key:
                save_api_key(key)
                dialog.destroy()
                # Reinitialize AI
                self.chat_display.configure(state="normal")
                self.chat_display.delete("0.0", "end")
                self.chat_display.configure(state="disabled")
                self.initialize_ai()
            else:
                messagebox.showwarning("Warning", "Please enter an API key")
        
        ctk.CTkButton(
            dialog, text="Save & Connect", 
            fg_color=COLORS["success"], hover_color="#3db389",
            height=40, corner_radius=8, font=ctk.CTkFont(weight="bold"),
            command=save_key
        ).pack(pady=20)

    def append_message(self, sender, message):
        self.chat_display.configure(state="normal")
        if sender == "Buddy":
            prefix = "🤖 "
        elif sender == "System":
            prefix = "⚠️ "
        else:
            prefix = "👤 "
        self.chat_display.insert("end", f"{prefix}[{sender}]: {message}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def send_message(self):
        msg = self.entry_msg.get().strip()
        if not msg:
            return
        
        self.append_message("You", msg)
        self.entry_msg.delete(0, "end")
        
        # Disable send button while processing
        self.btn_send.configure(state="disabled", text="...")
        
        # Check if AI is available
        if not self.chat:
            self.append_message("System", "AI not connected. Please set up your API key first.")
            self.btn_send.configure(state="normal", text="Send →")
            return
        
        # Send to AI in background thread
        def get_ai_response():
            try:
                response = self.chat.send_message(msg)
                # Schedule UI update on main thread
                self.after(0, lambda: self.handle_ai_response(response.text))
            except Exception as e:
                error_msg = str(e)
                if "quota" in error_msg.lower():
                    error_msg = "API quota exceeded. Please try again later or check your API key."
                elif "invalid" in error_msg.lower():
                    error_msg = "Invalid API key. Please update your API key in settings."
                self.after(0, lambda: self.handle_ai_error(error_msg))
        
        thread = threading.Thread(target=get_ai_response, daemon=True)
        thread.start()
    
    def handle_ai_response(self, response):
        """Handle successful AI response."""
        self.append_message("Buddy", response)
        self.btn_send.configure(state="normal", text="Send →")
    
    def handle_ai_error(self, error):
        """Handle AI error."""
        self.append_message("System", f"Error: {error}")
        self.btn_send.configure(state="normal", text="Send →")

# --- Main Application ---

class CareerBuddyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(APP_NAME)
        self.geometry("1100x750")
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS["bg_medium"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        self.sidebar.grid_propagate(False)
        
        # Logo
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.grid(row=0, column=0, padx=20, pady=(25, 20), sticky="ew")
        
        self.logo_label = ctk.CTkLabel(
            self.logo_frame, text="CareerBuddy", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLORS["text"]
        )
        self.logo_label.pack(side="left")
        
        self.logo_emoji = ctk.CTkLabel(
            self.logo_frame, text="🎓", 
            font=ctk.CTkFont(size=24)
        )
        self.logo_emoji.pack(side="left", padx=(5, 0))
        
        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("tracker", "📋 Job Tracker", 1),
            ("catcher", "🎣 Job Catcher", 2),
            ("calendar", "📅 Calendar", 3),
            ("analytics", "📊 Analytics", 4),
            ("cover", "✉️ Cover Letter", 5),
            ("files", "📁 Files", 6),
            ("board", "🎨 Whiteboard", 7),
            ("notes", "📝 Notepad", 8),
            ("ai", "🤖 AI Buddy", 9),
        ]
        
        for name, text, row in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=text, 
                fg_color="transparent", 
                hover_color=COLORS["secondary"],
                anchor="w", height=45, corner_radius=8,
                font=ctk.CTkFont(size=14),
                text_color=COLORS["text"],
                command=lambda n=name: self.show_frame(n)
            )
            btn.grid(row=row, column=0, padx=15, pady=5, sticky="ew")
            self.nav_buttons[name] = btn
        
        # Footer
        self.footer = ctk.CTkLabel(
            self.sidebar, text="v5.0 • AI Powered ✨",
            font=ctk.CTkFont(size=11),
            text_color="#666"
        )
        self.footer.grid(row=11, column=0, pady=20)
        
        # Main Content Area
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        # Initialize Frames
        self.frames = {}
        self.frames["tracker"] = JobTrackerFrame(self.main_area)
        self.frames["catcher"] = JobCatcherFrame(self.main_area, app=self)
        self.frames["calendar"] = CalendarFrame(self.main_area, app=self)
        self.frames["analytics"] = AnalyticsDashboardFrame(self.main_area)
        self.frames["cover"] = CoverLetterFrame(self.main_area)
        self.frames["files"] = FileStorageFrame(self.main_area)
        self.frames["board"] = WhiteboardFrame(self.main_area)
        self.frames["notes"] = NotepadFrame(self.main_area)
        self.frames["ai"] = AIBuddyFrame(self.main_area)
        
        self.current_frame = None
        self.show_frame("tracker")
        
    def show_frame(self, name):
        # Update nav button styles
        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=COLORS["accent"])
            else:
                btn.configure(fg_color="transparent")
        
        # Hide all frames
        for frame in self.frames.values():
            frame.pack_forget()
        # Show selected
        self.frames[name].pack(expand=True, fill="both")
        self.current_frame = name

if __name__ == "__main__":
    init_db()
    app = CareerBuddyApp()
    app.mainloop()
