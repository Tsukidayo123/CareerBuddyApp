# careerbuddy/app.py
import logging
import customtkinter as ctk
from services.db import CareerDB
from config.theme import get as theme
from ui.tracker import JobTrackerFrame
from ui.catcher import JobCatcherFrame
from ui.calendar import CalendarFrame
from ui.analytics import AnalyticsDashboardFrame
from ui.coverletter import CoverLetterFrame
from ui.filevault import FileStorageFrame
from ui.whiteboard import WhiteboardFrame
from ui.notepad import NotepadFrame
from ui.aibuddy import AIBuddyFrame


APP_NAME = "CareerBuddy"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    # --------------------------------------------------------------
    # 1️⃣ Initialise logging
    # --------------------------------------------------------------
    _setup_logging()

    # --------------------------------------------------------------
    # 2️⃣ Shared DB instance – all UI screens talk to the same DB
    # --------------------------------------------------------------
    db = CareerDB()

    # --------------------------------------------------------------
    # 3️⃣ CustomTkinter appearance
    # --------------------------------------------------------------
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")

    # --------------------------------------------------------------
    # 4️⃣ Root window (Card Mode → Full App Mode)
    # --------------------------------------------------------------
    root = ctk.CTk()
    root.title(APP_NAME)
    root.configure(fg_color=theme("bg_dark"))

    CARD_MODE = True  # 🔥 Start as floating desktop card


    def set_card_mode():
        root.geometry("280x160")
        root.overrideredirect(True)   # ✅ No title bar (widget-style)
        root.attributes("-topmost", True)


    def set_full_mode():
        root.overrideredirect(False)
        root.attributes("-topmost", False)
        root.geometry("1100x750")


    # ✅ Apply the initial mode
    if CARD_MODE:
        set_card_mode()
    else:
        set_full_mode()

    # ---------- Sidebar ----------
    sidebar = ctk.CTkFrame(root, width=220, fg_color=theme("bg_medium"))
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_rowconfigure(6, weight=1)
    sidebar.grid_propagate(False)

    # Logo / title
    logo = ctk.CTkLabel(
        sidebar,
        text="CareerBuddy 🎓",
        font=ctk.CTkFont(size=22, weight="bold"),
        text_color=theme("text"),
    )
    logo.grid(row=0, column=0, pady=(30, 10), padx=20)

    minimise_btn = ctk.CTkButton(
        sidebar,
        text="⬇ Minimise",
        height=32,
        command=set_card_mode
    )
    minimise_btn.grid(row=11, column=0, padx=15, pady=10, sticky="ew")

    # --------------------------------------------------------------
    # 5️⃣ Navigation mapping – each key → (button text, UI class)
    # --------------------------------------------------------------
    nav_map = {
        "tracker": ("📋 Job Tracker", JobTrackerFrame),
        "catcher": ("🎣 Job Catcher", JobCatcherFrame),
        "calendar": ("📅 Calendar", CalendarFrame),
        "analytics": ("📊 Analytics", AnalyticsDashboardFrame),
        "cover": ("✉️ Cover Letter", CoverLetterFrame),
        "files": ("📁 Files", FileStorageFrame),
        "board": ("🎨 Whiteboard", WhiteboardFrame),
        "notes": ("📝 Notepad", NotepadFrame),
        "ai": ("🤖 AI Buddy", AIBuddyFrame),
    }

    # Create navigation buttons
    btns = {}
    for idx, (key, (text, _)) in enumerate(nav_map.items(), start=1):
        btn = ctk.CTkButton(
            sidebar,
            text=text,
            fg_color="transparent",
            hover_color=theme("secondary"),
            anchor="w",
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(size=14),
            command=lambda k=key: show(k),
        )
        btn.grid(row=idx, column=0, padx=15, pady=5, sticky="ew")
        btns[key] = btn

    # Footer
    ctk.CTkLabel(
        sidebar,
        text="v5.0 • AI Powered ✨",
        font=ctk.CTkFont(size=11),
        text_color="#666",
    ).grid(row=12, column=0, pady=20)

    # ---------- Main content area ----------
    main_area = ctk.CTkFrame(root, fg_color="transparent")
    main_area.grid(row=0, column=1, sticky="nsew")
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)

    # Keep instantiated frames so we don’t recreate them on every navigation click
    instantiated: dict[str, ctk.CTkFrame] = {}

    def show(name: str) -> None:
        """Swap the visible screen."""
        # Highlight the selected button
        for k, b in btns.items():
            b.configure(fg_color="transparent" if k != name else theme("accent"))
        # Hide whichever frame is currently displayed
        for child in main_area.winfo_children():
            child.pack_forget()

        # Lazily instantiate the frame the first time we need it
        if name not in instantiated:
            _, cls = nav_map[name]
            # AI Buddy does **not** need the DB argument
            instantiated[name] = cls(main_area, db) if name != "ai" else cls(main_area)
        instantiated[name].pack(fill="both", expand=True)

    # Show the default screen at startup
    show("tracker")

    # --------------------------------------------------------------
    # 🖱️ Click anywhere to expand from card → full app
    # --------------------------------------------------------------
    def expand_to_full(event=None):
        set_full_mode()

    root.bind("<Button-1>", expand_to_full)


    # --------------------------------------------------------------
    # 6️⃣ Run the Tk main loop
    # --------------------------------------------------------------
    logging.getLogger(__name__).info("CareerBuddy UI started")
    root.mainloop()
    logging.getLogger(__name__).info("CareerBuddy UI closed")


# ----------------------------------------------------------------------
# When the file is executed directly (``python careerbuddy/app.py``)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
