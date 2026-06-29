# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtWidgets import QWidget, QMainWindow, QHBoxLayout, QLabel, QPushButton, QApplication


class CustomTitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(40)
        self._drag_pos = None

        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.init_ui()

    def _update_max_button_text(self):
        if self.parent_window._maximized:
            self.btn_max.setText("❐")
        else:
            self.btn_max.setText("⛶")

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(5)

        self.title_label = QLabel("✨ 智能双语对照与清洗系统 (专业版)", self)
        self.title_label.setStyleSheet(
            "color: #e4e4e7; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #a1a1aa;
                border: none;
                font-size: 14px;
                width: 32px;
                height: 32px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
        """

        self.btn_min = QPushButton("—", self)
        self.btn_min.setStyleSheet(btn_style)
        self.btn_min.clicked.connect(self.parent_window.showMinimized)

        self.btn_max = QPushButton("⛶", self)
        self.btn_max.setStyleSheet(btn_style)
        self.btn_max.clicked.connect(self.toggle_maximize)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setStyleSheet(btn_style + """
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.btn_close.clicked.connect(QApplication.instance().quit)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def toggle_maximize(self):
        if self.parent_window._maximized:
            self.parent_window.showNormal()
            self.parent_window._maximized = False
            QTimer.singleShot(50, self._update_max_button_text)
        else:
            self.parent_window.showMaximized()
            self.parent_window._maximized = True
            QTimer.singleShot(50, self._update_max_button_text)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().enterEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.parent_window._maximized:
            self._drag_pos = event.globalPosition().toPoint(
            ) - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.parent_window.move(
                event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
