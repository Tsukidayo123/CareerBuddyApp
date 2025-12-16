# ui_qt/whiteboard.py
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainterPath, QPen, QBrush, QAction, QImage, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsView, QGraphicsScene, QGraphicsPathItem, QColorDialog, QFileDialog, QMessageBox
)

from ui_qt.base import palette


class _CanvasView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)

        self._drawing = False
        self._path: QPainterPath | None = None
        self._item: QGraphicsPathItem | None = None

        self.pen_color = Qt.white
        self.pen_width = 5
        self.eraser = False
        self._undo_stack: list[QGraphicsPathItem] = []

        self.setStyleSheet("background: transparent; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = True
            pos = self.mapToScene(event.pos())
            self._path = QPainterPath(pos)

            pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            if self.eraser:
                # erase = draw with transparent brush by using background color approximation
                pen = QPen(Qt.black, self.pen_width * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

            self._item = QGraphicsPathItem()
            self._item.setPen(pen)
            self._item.setPath(self._path)
            self.scene().addItem(self._item)
            self._undo_stack.append(self._item)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing and self._path is not None and self._item is not None:
            pos = self.mapToScene(event.pos())
            self._path.lineTo(pos)
            self._item.setPath(self._path)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            self._path = None
            self._item = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def undo(self):
        if not self._undo_stack:
            return
        item = self._undo_stack.pop()
        self.scene().removeItem(item)

    def clear(self):
        self.scene().clear()
        self._undo_stack.clear()


class WhiteboardPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("🎨 Whiteboard")
        title.setStyleSheet("font-size:20px; font-weight:900;")
        header.addWidget(title)
        header.addStretch(1)

        self.btn_color = QPushButton("Color")
        self.btn_eraser = QPushButton("Eraser")
        self.btn_undo = QPushButton("Undo")
        self.btn_clear = QPushButton("Clear")
        self.btn_save = QPushButton("Save PNG")

        for b in (self.btn_color, self.btn_eraser, self.btn_undo, self.btn_clear, self.btn_save):
            b.setFixedHeight(38)
            b.setStyleSheet("background: rgba(255,255,255,0.10); padding: 10px 14px; border-radius:12px; font-weight:900;")
            header.addWidget(b)

        root.addLayout(header)

        # Canvas card
        card = QFrame()
        card.setStyleSheet("background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;")
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(12, 12, 12, 12)

        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, 2000, 1200)

        self.view = _CanvasView(scene)

        # give it a subtle “paper” background
        paper = QFrame()
        paper.setStyleSheet("background: rgba(0,0,0,0.22); border-radius: 14px;")
        paper_l = QVBoxLayout(paper)
        paper_l.setContentsMargins(10, 10, 10, 10)
        paper_l.addWidget(self.view)

        card_l.addWidget(paper, 1)
        root.addWidget(card, 1)

        # Wire
        self.btn_color.clicked.connect(self.pick_color)
        self.btn_eraser.clicked.connect(self.toggle_eraser)
        self.btn_undo.clicked.connect(self.view.undo)
        self.btn_clear.clicked.connect(self.view.clear)
        self.btn_save.clicked.connect(self.save_png)

        self.setStyleSheet(f"QLabel {{ color: {palette['text']}; }}")

    def pick_color(self):
        col = QColorDialog.getColor()
        if col.isValid():
            self.view.pen_color = col
            self.view.eraser = False
            self.btn_eraser.setText("Eraser")

    def toggle_eraser(self):
        self.view.eraser = not self.view.eraser
        self.btn_eraser.setText("Pen" if self.view.eraser else "Eraser")

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Whiteboard", f"whiteboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png", "PNG (*.png)")
        if not path:
            return

        # Render scene to image
        rect = self.view.scene().itemsBoundingRect()
        if rect.isNull():
            QMessageBox.information(self, "Nothing to save", "Your whiteboard is empty.")
            return

        image = QImage(int(rect.width()) + 40, int(rect.height()) + 40, QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.translate(-rect.topLeft() + QPointF(20, 20))
        self.view.scene().render(painter)
        painter.end()

        image.save(path)
