"""Screenshot calibrator — full-screen overlay to capture button template."""

import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPixmap, QImage


class CalibratorOverlay(QWidget):
    """Full-screen overlay with mouse-drag selection of capture zone."""

    template_captured = pyqtSignal(str, int, int)  # template_path, baseline_w, baseline_h

    def __init__(self, save_dir: str, parent=None):
        super().__init__(parent)
        self.save_dir = save_dir
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.showFullScreen()

        self.dragging = False
        self.rubber_band_rect = None
        self.start_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        screen = QApplication.primaryScreen()
        geo = screen.geometry()

        # Dark overlay with transparent cutout
        overlay_color = QColor(0, 0, 0, 160)
        painter.fillRect(geo, overlay_color)

        # Draw the selected rectangle with clear composition
        if self.rubber_band_rect:
            x, y, w, h = self.rubber_band_rect.getRect()
            # Clear the selection area
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(x, y, w, h, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # Selection border
            border_pen = QPen(QColor(255, 200, 100, 220))
            border_pen.setWidth(2)
            painter.setPen(border_pen)
            painter.drawRect(x, y, w, h)

            # Corner markers
            marker_len = 10
            painter.setPen(QPen(QColor(255, 200, 100), 3))
            painter.drawLine(x, y, x + marker_len, y)
            painter.drawLine(x, y, x, y + marker_len)
            painter.drawLine(x + w, y, x + w - marker_len, y)
            painter.drawLine(x + w, y, x + w, y + marker_len)
            painter.drawLine(x, y + h, x + marker_len, y + h)
            painter.drawLine(x, y + h, x, y + h - marker_len)
            painter.drawLine(x + w, y + h, x + w - marker_len, y + h)
            painter.drawLine(x + w, y + h, x + w, y + h - marker_len)

            # Size label
            painter.setPen(QColor(255, 255, 255, 220))
            font = QFont("Microsoft YaHei", 11)
            painter.setFont(font)
            painter.drawText(x, y - 25, w, 20, Qt.AlignCenter, f"{w}×{h}")

        # Instructions at top center
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Microsoft YaHei", 13)
        painter.setFont(font)
        if not self.rubber_band_rect:
            text = "在目标按钮上按住鼠标左键拖拽 → 松开后按 Enter 截取 | Esc 取消"
        elif not self.dragging:
            text = "按 Enter 确认截取 | Esc 取消 | 点击空白处重新选择"
        else:
            text = "松开鼠标完成选择"
        painter.drawText(geo, Qt.AlignHCenter | Qt.AlignTop, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.start_pos = event.pos()
            self.rubber_band_rect = QRect(self.start_pos, self.start_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.rubber_band_rect = QRect(self.start_pos, event.pos()).normalized()
            # Enforce minimum size 20x20
            if self.rubber_band_rect.width() < 20:
                self.rubber_band_rect.setWidth(20)
            if self.rubber_band_rect.height() < 20:
                self.rubber_band_rect.setHeight(20)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            # Finalize selection
            self.rubber_band_rect = QRect(self.start_pos, event.pos()).normalized()
            if self.rubber_band_rect.width() < 20 or self.rubber_band_rect.height() < 20:
                self.rubber_band_rect = None
            self.update()

    def mouseDoubleClickEvent(self, event):
        """Double-click to capture directly."""
        if self.rubber_band_rect and self.rubber_band_rect.contains(event.pos()):
            self._capture()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.rubber_band_rect:
                self._capture()
        elif event.key() == Qt.Key_Escape:
            if self.rubber_band_rect and not self.dragging:
                # Clear selection on first Esc, close on second
                self.rubber_band_rect = None
                self.update()
            else:
                self.close()

    def _capture(self):
        screen = QApplication.primaryScreen()

        # Hide overlay first so grabWindow captures the real screen behind
        self.hide()
        QApplication.processEvents()

        x, y, w, h = self.rubber_band_rect.getRect()
        pixmap = screen.grabWindow(0, x, y, w, h)
        geo = screen.geometry()

        # Save as PNG
        os.makedirs(self.save_dir, exist_ok=True)
        name = "button_1.png"
        path = os.path.join(self.save_dir, name)
        if os.path.exists(path):
            # Find next available name
            i = 2
            while os.path.exists(os.path.join(self.save_dir, f"button_{i}.png")):
                i += 1
            name = f"button_{i}.png"
            path = os.path.join(self.save_dir, name)

        pixmap.save(path, "PNG")

        self.template_captured.emit(path, geo.width(), geo.height())
        self.close()
