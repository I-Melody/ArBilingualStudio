# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen


class TimelineTicks(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.duration_ms = 0

    def set_duration(self, duration_ms: int):
        self.duration_ms = duration_ms
        self.update()

    def paintEvent(self, event):
        if self.duration_ms <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#27272a"), 1))
        painter.drawLine(0, 1, self.width(), 1)
        one_minute = 60000
        num_ticks = int(self.duration_ms / one_minute)
        painter.setPen(QPen(QColor("#52525b"), 1))
        for i in range(1, num_ticks + 1):
            x = int(((i * one_minute) / self.duration_ms) * self.width())
            painter.drawLine(x, 1, x, 6)
            if num_ticks <= 15:
                font = painter.font()
                font.setPointSize(7)
                painter.setFont(font)
                painter.setPen(QPen(QColor("#71717a")))
                painter.drawText(x - 6, 12, f"{i}m")
