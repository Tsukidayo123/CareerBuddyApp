import logging
import os
import json
import time
import threading

import customtkinter as ctk
from PIL import Image
import pystray

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
STATE_FILE = "card_state.json"


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> None:
    _setup_logging()
    db = CareerDB()

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.title(APP_NAME)
    root.configure(fg_color=theme("bg_dark"))

    CARD_MIN_WIDTH = 140
    CARD_MIN_HEIGHT = 200
    CARD_WIDTH = 180
    CARD_HEIGHT = 260

    ASSET_PATH = os.path.join(os.path.dirname(__file__), "assets", "icons", "card.png")

    drag_offset_x = 0
    drag_offset_y = 0
    idle_timer = time.time()
    drag_started = False

    
    # Persist Card Position
    
    def save_position(x: int, y: int) -> None:
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"x": x, "y": y}, f)
        except Exception:
            pass

    def load_position():
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    return int(data.get("x", 100)), int(data.get("y", 100))
            except Exception:
                pass
        return 100, 100

    def clear_root():
        for widget in root.winfo_children():
            widget.destroy()

    
    # Card Mode
    
    def set_card_mode():
        nonlocal drag_started

        clear_root()
        drag_started = False

        x, y = load_position()
        root.geometry(f"{CARD_WIDTH}x{CARD_HEIGHT}+{x}+{y}")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(fg_color=theme("bg_dark"))

        base_image = Image.open(ASSET_PATH).convert("RGBA")

        def update_card_visual(w, h):
            return ctk.CTkImage(light_image=base_image, size=(int(w), int(h)))

        card_img = update_card_visual(CARD_WIDTH, CARD_HEIGHT)

        card_label = ctk.CTkLabel(
            root,
            image=card_img,
            text="",
            cursor="hand2",
            fg_color=theme("bg_dark"),
        )
        card_label.image = card_img
        card_label.pack(fill="both", expand=True)

        # Hover glow
        card_label.bind("<Enter>", lambda e: card_label.configure(fg_color=theme("bg_medium")))
        card_label.bind("<Leave>", lambda e: card_label.configure(fg_color=theme("bg_dark")))

        # Drag Logic
        def start_move(event):
            nonlocal drag_offset_x, drag_offset_y, drag_started
            drag_offset_x = event.x
            drag_offset_y = event.y
            drag_started = False

        def do_move(event):
            nonlocal drag_started
            drag_started = True
            x_cur = root.winfo_x() + event.x - drag_offset_x
            y_cur = root.winfo_y() + event.y - drag_offset_y
            root.geometry(f"+{x_cur}+{y_cur}")
            save_position(x_cur, y_cur)

        def on_release(event):
            nonlocal drag_started
            if not drag_started:
                set_full_mode()
            drag_started = False

        card_label.bind("<Button-1>", start_move)
        card_label.bind("<B1-Motion>", do_move)
        card_label.bind("<ButtonRelease-1>", on_release)

    
    # Full App Mode
    
    def set_full_mode():
        clear_root()
        root.overrideredirect(False)
        root.attributes("-topmost", False)
        root.geometry("1200x800")
        root.configure(fg_color=theme("bg_dark"))
        build_full_ui()

    
    # Full UI Layout
    
    def build_full_ui():
        sidebar = ctk.CTkFrame(root, width=220, fg_color=theme("bg_medium"))
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        logo = ctk.CTkLabel(
            sidebar,
            text="CareerBuddy 🎓",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme("text"),
        )
        logo.grid(row=0, column=0, pady=(20, 10), padx=20, sticky="w")

        minimise_btn = ctk.CTkButton(
            sidebar,
            text="⬇ Minimise to Card",
            height=36,
            command=set_card_mode,
        )
        minimise_btn.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")

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

        btns = {}

        for idx, (key, (text, _)) in enumerate(nav_map.items(), start=2):
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                fg_color="transparent",
                hover_color=theme("secondary"),
                anchor="w",
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=14),
                command=lambda k=key: show(k),
            )
            btn.grid(row=idx, column=0, padx=15, pady=3, sticky="ew")
            btns[key] = btn

        footer = ctk.CTkLabel(
            sidebar,
            text="v5.0 • AI Powered ✨",
            font=ctk.CTkFont(size=11),
            text_color="#666",
        )
        footer.grid(row=len(nav_map) + 3, column=0, pady=15, padx=15, sticky="sw")

        main_area = ctk.CTkFrame(root, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew")

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        instantiated = {}

        def show(name: str):
            for k, b in btns.items():
                b.configure(fg_color="transparent" if k != name else theme("accent"))

            for child in main_area.winfo_children():
                child.pack_forget()

            if name not in instantiated:
                _, cls = nav_map[name]
                instantiated[name] = cls(main_area, db) if name != "ai" else cls(main_area)

            instantiated[name].pack(fill="both", expand=True)

        show("tracker")

    
    # Tray icon
    
    def tray_thread():
        def on_show(icon, item):
            root.after(0, set_full_mode)

        def on_quit(icon, item):
            icon.stop()
            root.after(0, root.destroy)

        try:
            image = Image.open(ASSET_PATH)
            menu = pystray.Menu(
                pystray.MenuItem("Open CareerBuddy", on_show),
                pystray.MenuItem("Quit", on_quit),
            )
            icon = pystray.Icon("CareerBuddy", image, "CareerBuddy", menu)
            icon.run()
        except Exception as e:
            print("Tray icon error:", e)

    threading.Thread(target=tray_thread, daemon=True).start()

    # Start in true card mode
    set_card_mode()

    logging.info("CareerBuddy UI started")
    root.mainloop()
    logging.info("CareerBuddy UI closed")


if __name__ == "__main__":
    main()
