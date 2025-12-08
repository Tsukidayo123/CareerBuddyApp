# careerbuddy/ui/whiteboard.py
import random
import tkinter as tk
import customtkinter as ctk
from ui.base import BaseCTkFrame
from config.theme import get as theme


class DraggablePostIt(ctk.CTkFrame):
    """A coloured sticky note that can be dragged around."""
    def __init__(self, master, text="New note", x=60, y=60, color="#fdfd96", on_delete=None):
        super().__init__(master, fg_color=color, corner_radius=12, border_width=2, border_color="#333")
        self.on_delete = on_delete
        self._drag_offset = {"x": 0, "y": 0}

        # Header with drag indicator + delete button
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=24)
        hdr.pack(fill="x", padx=4, pady=(4, 0))

        drag_lbl = ctk.CTkLabel(hdr, text="⋮⋮", font=("Arial", 10), text_color="#666", width=20)
        drag_lbl.pack(side="left")
        del_btn = ctk.CTkButton(
            hdr,
            text="×",
            width=20,
            height=20,
            fg_color="#cc4444",
            hover_color="#ff3333",
            text_color="white",
            font=("Arial", 14, "bold"),
            corner_radius=10,
            command=self._delete,
        )
        del_btn.pack(side="right")

        # Text widget
        txt = ctk.CTkTextbox(self, width=130, height=90, fg_color="#f5f5f5", text_color="#1a1a1a")
        txt.insert("0.0", text)
        txt.pack(padx=6, pady=(2, 6))
        self.textbox = txt

        # Place initially
        self.place(x=x, y=y)

        # Bind drag events to the header
        hdr.bind("<Button-1>", self._start_move)
        hdr.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event):
        self._drag_offset["x"], self._drag_offset["y"] = event.x, event.y
        self.lift()

    def _do_move(self, event):
        new_x = self.winfo_x() - self._drag_offset["x"] + event.x
        new_y = self.winfo_y() - self._drag_offset["y"] + event.y
        self.place(x=new_x, y=new_y)

    def _delete(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()


class WhiteboardFrame(BaseCTkFrame):
    """Free‑form canvas with drawing + draggable post‑its."""
    def __init__(self, master):
        super().__init__(master)
        self.mode = tk.StringVar(value="draw")  # draw / eraser / pinboard
        self.draw_color = "#ffffff"
        self.brush_size = 3
        self._setup_ui()
        self._postits = []      # keep references so they aren't garbage‑collected

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # ----- Header -------------------------------------------------
        hdr = ctk.CTkFrame(self, fg_color=theme("secondary"), corner_radius=12, height=60)
        hdr.pack(fill="x", **self.padded())
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🎨 Whiteboard",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme("text"),
        ).pack(side="left", padx=20, pady=15)

        # ----- Tool strip (draw / erase / pin) -----------------------
        tools = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12, height=70)
        tools.pack(fill="x", **self.padded())
        tools.pack_propagate(False)

        # Mode buttons
        for mode, txt, col in [
            ("pinboard", "📌 Pinboard", theme("warning")),
            ("draw", "✏️ Draw", theme("secondary")),
            ("eraser", "🧹 Eraser", theme("secondary")),
        ]:
            b = ctk.CTkButton(
                tools,
                text=txt,
                fg_color=col,
                hover_color=theme("accent_hover") if mode != "pinboard" else "#e6ac00",
                corner_radius=8,
                width=90,
                command=lambda m=mode: self._set_mode(m),
            )
            b.pack(side="left", padx=5, pady=10)

        # Color picker for drawing
        self._color_buttons = []
        colors = ["#ffffff", "#ff6b6b", "#4ecdc4", "#ffe66d", "#95e1d3", "#f38181", "#aa96da", "#fcbad3"]
        for col in colors:
            btn = ctk.CTkButton(
                tools,
                text="",
                width=28,
                height=28,
                fg_color=col,
                hover_color=col,
                corner_radius=14,
                command=lambda c=col: self._set_draw_color(c),
                border_width=3 if col == self.draw_color else 0,
                border_color="white",
            )
            btn.pack(side="left", padx=3)
            self._color_buttons.append(btn)

        # Brush size slider
        self.brush_slider = ctk.CTkSlider(
            tools,
            from_=1,
            to=20,
            number_of_steps=19,
            width=100,
            button_color=theme("accent"),
            command=self._set_brush_size,
        )
        self.brush_slider.set(self.brush_size)
        self.brush_slider.pack(side="left", padx=10)
        self.size_lbl = ctk.CTkLabel(tools, text=f"{self.brush_size}px", width=35, text_color=theme("text"))
        self.size_lbl.pack(side="left")

        # Add‑note button (right side)
        add_note = ctk.CTkButton(
            tools,
            text="+ Add Note",
            fg_color=theme("success"),
            hover_color="#3db389",
            corner_radius=8,
            command=self._add_postit,
        )
        add_note.pack(side="right", padx=10, pady=10)

        # ----- Canvas -------------------------------------------------
        canvas_frame = ctk.CTkFrame(self, fg_color=theme("bg_medium"), corner_radius=12)
        canvas_frame.pack(fill="both", expand=True, **self.padded())

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#2d2d44",
            highlightthickness=0,
            cursor="arrow",
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)

        # Bind drawing events
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    # ------------------------------------------------------------------
    def _set_mode(self, mode: str):
        self.mode.set(mode)
        # Update cursor for visual feedback
        curs = {"draw": "pencil", "eraser": "circle", "pinboard": "arrow"}[mode]
        self.canvas.config(cursor=curs)

    # ------------------------------------------------------------------
    def _set_draw_color(self, col: str):
        self.draw_color = col
        for btn in self._color_buttons:
            btn.configure(border_width=3 if btn.cget("fg_color") == col else 0)

    # ------------------------------------------------------------------
    def _set_brush_size(self, val):
        self.brush_size = int(val)
        self.size_lbl.configure(text=f"{self.brush_size}px")

    # ------------------------------------------------------------------
    def _on_press(self, event):
        if self.mode.get() == "draw":
            self.prev = (event.x, event.y)
        elif self.mode.get() == "eraser":
            self._erase(event)

    def _on_drag(self, event):
        if self.mode.get() == "draw" and hasattr(self, "prev"):
            x0, y0 = self.prev
            self.canvas.create_line(
                x0,
                y0,
                event.x,
                event.y,
                width=self.brush_size,
                fill=self.draw_color,
                capstyle=tk.ROUND,
                smooth=True,
                tags="draw",
            )
            self.prev = (event.x, event.y)
        elif self.mode.get() == "eraser":
            self._erase(event)

    def _on_release(self, _):
        if hasattr(self, "prev"):
            del self.prev

    # ------------------------------------------------------------------
    def _erase(self, event):
        size = self.brush_size * 2
        items = self.canvas.find_overlapping(event.x - size, event.y - size, event.x + size, event.y + size)
        for it in items:
            if "draw" in self.canvas.gettags(it):
                self.canvas.delete(it)

    # ------------------------------------------------------------------
    def _add_postit(self):
        if self.mode.get() != "pinboard":
            self._set_mode("pinboard")
        x = random.randint(50, 400)
        y = random.randint(50, 300)
        note = DraggablePostIt(self.canvas, x=x, y=y, color="#fdfd96", on_delete=self._remove_postit)
        self._postits.append(note)

    def _remove_postit(self, note):
        if note in self._postits:
            self._postits.remove(note)
