# ui_qt/whiteboard.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSlider,
    QColorDialog,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPathItem,
    QSizePolicy,
)


# ---------------------------------
# Card-theme friendly colors
# ---------------------------------
CANVAS_BG = "#F8F4EC"   # warm paper
CANVAS_GRID = "#E7E0D7"  # subtle grid line (optional later)

SUIT_SWATCHES = [
    ("♠", "#111111"),  # black
    ("♥", "#D64545"),  # red
    ("♦", "#D6A94A"),  # gold
    ("♣", "#1F9D8A"),  # teal
]


@dataclass
class StrokeStyle:
    color: QColor
    width: int
    alpha: int
    mode: str  # "pen" | "highlighter" | "eraser"


class DrawView(QGraphicsView):
    """
    QGraphicsView canvas with:
    - Draw strokes (pen/highlighter/eraser)
    - Undo/redo stack
    - Space+drag pan
    - Wheel zoom (under mouse)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Scene (IMPORTANT: must exist, fixes your earlier NoneType error)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Make a large workspace
        self._scene.setSceneRect(QRectF(-3000, -2000, 6000, 4000))

        # Rendering
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Feel
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(QColor(CANVAS_BG))
        self.setFrameShape(QFrame.NoFrame)

        # Zoom behavior (center under cursor)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        # Drawing state
        self._drawing = False
        self._path: Optional[QPainterPath] = None
        self._item: Optional[QGraphicsPathItem] = None
        self._last_pt: Optional[QPointF] = None

        # Pan state
        self._space_down = False
        self._pan_mode = False

        # Undo/redo
        self._undo_stack: List[QGraphicsPathItem] = []
        self._redo_stack: List[QGraphicsPathItem] = []

        # Current style defaults
        self.style = StrokeStyle(
            color=QColor("#111111"),
            width=5,
            alpha=255,
            mode="pen",
        )

    # -------------------------
    # Public API for toolbar
    # -------------------------
    def set_mode(self, mode: str):
        self.style.mode = mode

    def set_color(self, hex_color: str):
        self.style.color = QColor(hex_color)

    def set_width(self, w: int):
        self.style.width = max(1, min(40, w))

    def set_opacity_percent(self, pct: int):
        pct = max(1, min(100, pct))
        self.style.alpha = int(255 * (pct / 100.0))

    def undo(self):
        if not self._undo_stack:
            return
        item = self._undo_stack.pop()
        self._scene.removeItem(item)
        self._redo_stack.append(item)

    def redo(self):
        if not self._redo_stack:
            return
        item = self._redo_stack.pop()
        self._scene.addItem(item)
        self._undo_stack.append(item)

    def clear_all(self):
        self._scene.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def reset_zoom(self):
        self.resetTransform()

    # -------------------------
    # Internal helpers
    # -------------------------
    def _make_pen(self) -> QPen:
        # Determine stroke color based on mode
        if self.style.mode == "eraser":
            col = QColor(CANVAS_BG)
            col.setAlpha(255)
            width = max(10, self.style.width + 8)
        else:
            col = QColor(self.style.color)
            col.setAlpha(self.style.alpha)
            width = self.style.width
            if self.style.mode == "highlighter":
                # highlighter feels better thicker & slightly translucent
                width = max(width, 12)
                col.setAlpha(min(col.alpha(), 140))

        pen = QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        return pen

    def _begin_stroke(self, scene_pos: QPointF):
        self._drawing = True
        self._redo_stack.clear()

        self._path = QPainterPath(scene_pos)
        self._item = QGraphicsPathItem()
        self._item.setPen(self._make_pen())
        self._item.setPath(self._path)

        # Add to scene and to undo stack
        self._scene.addItem(self._item)
        self._undo_stack.append(self._item)

        self._last_pt = scene_pos

    def _extend_stroke(self, scene_pos: QPointF):
        if not self._drawing or self._path is None or self._item is None or self._last_pt is None:
            return

        # Simple smoothing: draw a line to the midpoint
        mid = QPointF((self._last_pt.x() + scene_pos.x()) / 2.0, (self._last_pt.y() + scene_pos.y()) / 2.0)
        self._path.quadTo(self._last_pt, mid)
        self._item.setPath(self._path)
        self._last_pt = scene_pos

    def _end_stroke(self):
        self._drawing = False
        self._path = None
        self._item = None
        self._last_pt = None

    # -------------------------
    # Events (draw/pan/zoom)
    # -------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not self._space_down:
            self._space_down = True
            # Pan mode
            self._pan_mode = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = False
            self._pan_mode = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def wheelEvent(self, event):
        # Zoom under mouse
        delta = event.angleDelta().y()
        if delta == 0:
            return

        factor = 1.15 if delta > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        # If panning (space held), let QGraphicsView handle it
        if self._pan_mode:
            # gives the "hand drag" behavior
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._begin_stroke(scene_pos)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_mode:
            super().mouseMoveEvent(event)
            return

        if self._drawing:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._extend_stroke(scene_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_mode:
            super().mouseReleaseEvent(event)
            return

        if event.button() == Qt.LeftButton and self._drawing:
            self._end_stroke()
            event.accept()
            return

        super().mouseReleaseEvent(event)


class WhiteboardPage(QWidget):
    """
    Full page with a top toolbar + DrawView.
    """

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Toolbar container
        toolbar = QFrame()
        toolbar.setObjectName("wbToolbar")
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        t = QHBoxLayout(toolbar)
        t.setContentsMargins(12, 10, 12, 10)
        t.setSpacing(10)

        title = QLabel("🎨 Whiteboard")
        title.setObjectName("wbTitle")
        t.addWidget(title)
        t.addSpacing(6)

        # Mode buttons
        self.btn_pen = QPushButton("Pen")
        self.btn_high = QPushButton("Highlighter")
        self.btn_erase = QPushButton("Eraser")

        for b in (self.btn_pen, self.btn_high, self.btn_erase):
            b.setObjectName("wbBtn")
            b.setCursor(Qt.PointingHandCursor)

        t.addWidget(self.btn_pen)
        t.addWidget(self.btn_high)
        t.addWidget(self.btn_erase)

        t.addSpacing(10)

        # Swatches (card suits)
        sw_label = QLabel("Suits:")
        sw_label.setObjectName("wbLabel")
        t.addWidget(sw_label)

        self.swatch_buttons: list[QPushButton] = []
        for sym, hx in SUIT_SWATCHES:
            b = QPushButton(sym)
            b.setObjectName("swatch")
            b.setFixedSize(36, 36)
            b.setCursor(Qt.PointingHandCursor)

            b.setProperty("swatchColor", hx)   # store color on the button
            b.setStyleSheet(f"color: {hx};")   # apply icon color

            b.clicked.connect(lambda _=False, c=hx: self._set_color_hex(c))
            self.swatch_buttons.append(b)
            t.addWidget(b)

        # Color picker
        self.btn_pick = QPushButton("🎨")
        self.btn_pick.setObjectName("wbBtn")
        self.btn_pick.setFixedWidth(44)
        self.btn_pick.setToolTip("Pick a color")
        self.btn_pick.clicked.connect(self._pick_color)
        t.addWidget(self.btn_pick)

        t.addSpacing(10)

        # Brush size slider
        size_lab = QLabel("Size")
        size_lab.setObjectName("wbLabel")
        self.sld_size = QSlider(Qt.Horizontal)
        self.sld_size.setRange(1, 20)
        self.sld_size.setValue(5)
        self.sld_size.setFixedWidth(140)

        t.addWidget(size_lab)
        t.addWidget(self.sld_size)

        # Opacity slider
        op_lab = QLabel("Opacity")
        op_lab.setObjectName("wbLabel")
        self.sld_op = QSlider(Qt.Horizontal)
        self.sld_op.setRange(10, 100)
        self.sld_op.setValue(100)
        self.sld_op.setFixedWidth(160)

        t.addWidget(op_lab)
        t.addWidget(self.sld_op)

        t.addStretch(1)

        # Undo/Redo/Clear/Zoom
        self.btn_undo = QPushButton("↶ Undo")
        self.btn_redo = QPushButton("↷ Redo")
        self.btn_clear = QPushButton("🗑 Clear")
        self.btn_reset_zoom = QPushButton("🔍 Reset")

        for b in (self.btn_undo, self.btn_redo, self.btn_clear, self.btn_reset_zoom):
            b.setObjectName("wbBtn")
            b.setCursor(Qt.PointingHandCursor)

        t.addWidget(self.btn_undo)
        t.addWidget(self.btn_redo)
        t.addWidget(self.btn_reset_zoom)
        t.addWidget(self.btn_clear)

        root.addWidget(toolbar)

        # Canvas
        self.view = DrawView()
        root.addWidget(self.view, 1)

        # Wire buttons
        self.btn_pen.clicked.connect(lambda: self._set_mode("pen"))
        self.btn_high.clicked.connect(lambda: self._set_mode("highlighter"))
        self.btn_erase.clicked.connect(lambda: self._set_mode("eraser"))

        self.sld_size.valueChanged.connect(self.view.set_width)
        self.sld_op.valueChanged.connect(self.view.set_opacity_percent)

        self.btn_undo.clicked.connect(self.view.undo)
        self.btn_redo.clicked.connect(self.view.redo)
        self.btn_reset_zoom.clicked.connect(self.view.reset_zoom)
        self.btn_clear.clicked.connect(self._clear_confirm)

        # Keyboard shortcuts (Ctrl+Z / Ctrl+Y)
        act_undo = QAction(self)
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(self.view.undo)
        self.addAction(act_undo)

        act_redo = QAction(self)
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(self.view.redo)
        self.addAction(act_redo)

        # Set default mode visuals
        self._set_mode("pen")

        # Stylesheet (works with your dark app shell, but keeps canvas readable)
        self.setStyleSheet("""
            QFrame#wbToolbar {
                background: rgba(0,0,0,0.18);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }
            QLabel#wbTitle {
                color: white;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#wbLabel {
                color: rgba(255,255,255,0.72);
                font-weight: 800;
            }
            QPushButton#wbBtn {
                background: rgba(255,255,255,0.10);
                color: white;
                font-weight: 850;
                padding: 8px 12px;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.10);
            }
            QPushButton#wbBtn:hover {
                background: rgba(255,255,255,0.16);
            }
            QPushButton#wbBtn[active="true"] {
                background: rgba(231,195,91,0.22);
                border: 1px solid rgba(231,195,91,0.35);
                color: white;
            }
            QPushButton#swatch {
                background: rgba(255,255,255,0.10);
                font-size: 16px;
                font-weight: 900;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.10);
            }

            QPushButton#swatch:hover {
                background: rgba(255,255,255,0.18);
            }
                           
            QPushButton#swatch[active="true"] {
                background: rgba(231,195,91,0.22);
                border: 1px solid rgba(231,195,91,0.45);
            }
        """)

    # -------------------------
    # Toolbar helpers
    # -------------------------
    def _set_mode(self, mode: str):
        self.view.set_mode(mode)

        # Toggle active style
        self.btn_pen.setProperty("active", mode == "pen")
        self.btn_high.setProperty("active", mode == "highlighter")
        self.btn_erase.setProperty("active", mode == "eraser")
        for b in (self.btn_pen, self.btn_high, self.btn_erase):
            b.style().unpolish(b)
            b.style().polish(b)

        # Sensible defaults when switching
        if mode == "highlighter":
            self.sld_op.setValue(min(self.sld_op.value(), 60))
            self.sld_size.setValue(max(self.sld_size.value(), 12))
        elif mode == "eraser":
            self.sld_op.setValue(100)

    def _set_color_hex(self, hx: str):
        self.view.set_color(hx)

        for b in self.swatch_buttons:
            active = b.property("swatchColor") == hx
            b.setProperty("active", active)
            b.style().unpolish(b)
            b.style().polish(b)
    
        # If user picks a color while erasing, switch back to pen automatically
        if self.view.style.mode == "eraser":
            self._set_mode("pen")

    def _pick_color(self):
        col = QColorDialog.getColor(self.view.style.color, self, "Pick a color")
        if col.isValid():
            self.view.style.color = col
            if self.view.style.mode == "eraser":
                self._set_mode("pen")

    def _clear_confirm(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Clear Whiteboard")
        msg.setText("Clear the entire whiteboard?")
        msg.setInformativeText("This cannot be undone.")
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        msg.setDefaultButton(QMessageBox.Cancel)
        if msg.exec() == QMessageBox.Yes:
            self.view.clear_all()
