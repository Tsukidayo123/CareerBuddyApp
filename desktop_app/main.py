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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    _setup_logging()

    db = CareerDB()

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.title(APP_NAME)
    root.configure(fg_color=theme("bg_dark"))
    root.resizable(True, True)

    # Card state
    CARD_MIN_WIDTH = 140
    CARD_MIN_HEIGHT = 200
    CARD_WIDTH = 180
    CARD_HEIGHT = 260

    ASSET_PATH = os.path.join(
        os.path.dirname(__file__),
        "assets",
        "icons",
        "card.png"
    )

    drag_offset_x = 0
    drag_offset_y = 0
    resizing = False
    idle_timer = time.time()

    # ------------------------------
    # Save / load card position
    # ------------------------------
    def save_position(x: int, y: int) -> None:
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"x": x, "y": y}, f)
        except Exception as e:
            print("Failed to save position:", e)

    def load_position() -> tuple[int, int]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    return int(data.get("x", 100)), int(data.get("y", 100))
            except Exception:
                pass
        return 100, 100

    # ------------------------------
    # Utilities
    # ------------------------------
    def clear_root() -> None:
        for widget in root.winfo_children():
            widget.destroy()

    def snap_to_edges(x: int, y: int) -> tuple[int, int]:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        margin = 20

        # Left / top snap
        if abs(x) < margin:
            x = 0
        if abs(y) < margin:
            y = 0

        # Right / bottom snap (approx with current card size)
        if abs((screen_w - x) - CARD_WIDTH) < margin:
            x = screen_w - CARD_WIDTH
        if abs((screen_h - y) - CARD_HEIGHT) < margin:
            y = screen_h - CARD_HEIGHT

        return x, y

    # ------------------------------
    # Idle pulse (subtle attention)
    # ------------------------------
    def start_idle_animation(widget: ctk.CTkLabel) -> None:
        def pulse():
            if not widget.winfo_exists():
                return

            # If user hasn't interacted in a while
            if time.time() - idle_timer > 8:
                try:
                    original = widget.cget("fg_color")
                    widget.configure(fg_color=theme("accent"))
                    root.after(
                        400,
                        lambda: widget.configure(fg_color=original)
                        if widget.winfo_exists()
                        else None,
                    )
                except Exception:
                    pass

            root.after(2500, pulse)

        root.after(2500, pulse)

    # ------------------------------
    # Card mode (widget)
    # ------------------------------
    def set_card_mode() -> None:
        nonlocal drag_offset_x, drag_offset_y, resizing, CARD_WIDTH, CARD_HEIGHT, idle_timer

        clear_root()

        x, y = load_position()
        root.geometry(f"{CARD_WIDTH}x{CARD_HEIGHT}+{x}+{y}")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(fg_color=theme("bg_dark"))

        base_image = Image.open(ASSET_PATH)
        if base_image.mode != "RGBA":
            base_image = base_image.convert("RGBA")

        # We'll recreate this image on resize
        def update_card_visual(width: int, height: int) -> ctk.CTkImage:
            img = ctk.CTkImage(
                light_image=base_image,
                size=(int(width), int(height)),
            )
            return img

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

        # Hover effect (no border, just bg tweak)
        def glow_on(_event=None):
            card_label.configure(fg_color=theme("bg_medium"))

        def glow_off(_event=None):
            card_label.configure(fg_color=theme("bg_dark"))

        card_label.bind("<Enter>", glow_on)
        card_label.bind("<Leave>", glow_off)

        # Drag logic
        def start_move(event):
            nonlocal drag_offset_x, drag_offset_y, idle_timer
            drag_offset_x = event.x
            drag_offset_y = event.y
            idle_timer = time.time()

        def do_move(event):
            nonlocal idle_timer
            x_cur = root.winfo_x() + event.x - drag_offset_x
            y_cur = root.winfo_y() + event.y - drag_offset_y
            x_snapped, y_snapped = snap_to_edges(x_cur, y_cur)
            root.geometry(f"+{x_snapped}+{y_snapped}")
            save_position(x_snapped, y_snapped)
            idle_timer = time.time()

        card_label.bind("<Button-1>", start_move)
        card_label.bind("<B1-Motion>", do_move)

        # Click to expand (simple behaviour)
        def on_release(_event=None):
            nonlocal idle_timer
            idle_timer = time.time()
            set_full_mode()

        card_label.bind("<ButtonRelease-1>", on_release)

        # Resize handle (bottom-right)
        resize_handle = ctk.CTkLabel(
            root,
            text="◢",
            cursor="sizing",
            fg_color=theme("bg_dark"),
            width=20,
            height=20,
        )
        resize_handle.place(x=CARD_WIDTH - 20, y=CARD_HEIGHT - 20)

        def start_resize(_event=None):
            nonlocal resizing, idle_timer
            resizing = True
            idle_timer = time.time()

        def do_resize(event):
            nonlocal CARD_WIDTH, CARD_HEIGHT, idle_timer
            new_w = max(CARD_MIN_WIDTH, event.x_root - root.winfo_x())
            new_h = max(CARD_MIN_HEIGHT, event.y_root - root.winfo_y())
            CARD_WIDTH = new_w
            CARD_HEIGHT = new_h

            root.geometry(f"{CARD_WIDTH}x{CARD_HEIGHT}")

            # Rescale image to new size
            new_img = update_card_visual(CARD_WIDTH, CARD_HEIGHT)
            card_label.configure(image=new_img)
            card_label.image = new_img

            resize_handle.place(x=CARD_WIDTH - 20, y=CARD_HEIGHT - 20)
            idle_timer = time.time()

        def stop_resize(_event=None):
            nonlocal resizing, idle_timer
            resizing = False
            # Save new position + size baseline
            save_position(root.winfo_x(), root.winfo_y())
            idle_timer = time.time()

        resize_handle.bind("<Button-1>", start_resize)
        resize_handle.bind("<B1-Motion>", do_resize)
        resize_handle.bind("<ButtonRelease-1>", stop_resize)

        root.focus_force()
        start_idle_animation(card_label)

    # ------------------------------
    # Full app mode
    # ------------------------------
    def set_full_mode() -> None:
        clear_root()

        root.overrideredirect(False)
        root.attributes("-topmost", False)
        root.geometry("1100x750")
        root.configure(fg_color=theme("bg_dark"))

        build_full_ui()

    # ------------------------------
    # Full UI (content resizes with window)
    # ------------------------------
    def build_full_ui() -> None:
        # Left sidebar
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
            height=32,
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

        btns: dict[str, ctk.CTkButton] = {}

        # Navigation buttons
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

        # Main area (resizes with window)
        main_area = ctk.CTkFrame(root, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew")

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        instantiated: dict[str, ctk.CTkFrame] = {}

        def show(name: str) -> None:
            # Highlight button
            for k, b in btns.items():
                b.configure(
                    fg_color="transparent" if k != name else theme("accent")
                )

            # Clear main area
            for child in main_area.winfo_children():
                child.pack_forget()

            # Lazy-load frame
            if name not in instantiated:
                _, cls = nav_map[name]
                instantiated[name] = (
                    cls(main_area, db) if name != "ai" else cls(main_area)
                )

            instantiated[name].pack(fill="both", expand=True)

        show("tracker")

    # ------------------------------
    # System tray icon (background)
    # ------------------------------
    def tray_thread() -> None:
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

    # Start in card mode
    set_card_mode()

    logging.getLogger(__name__).info("CareerBuddy UI started")
    root.mainloop()
    logging.getLogger(__name__).info("CareerBuddy UI closed")


if __name__ == "__main__":
    main()
