# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from .base_menu import BaseMenuWidget
from core.paths import get_app_root
from ui.widgets.pdf_viewer import PdfViewerWidget


class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        self.setStyleSheet("""
            QPushButton#PageBtn {
                background-color: #1e1b4b;
                color: #c084fc;
                border: 1px solid #4338ca;
                border-radius: 6px;
                height: 28px;
                padding: 0 15px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#PageBtn:hover {
                background-color: #312e81;
                color: #e9d5ff;
            }
            QPushButton#PageBtn:disabled {
                background-color: #121214;
                color: #52525b;
                border: 1px solid #27272a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.header = QLabel("📖 规则配置手册与规范指南 (rule.pdf)", self)
        self.header.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.header)

        self.pdf_viewer = PdfViewerWidget(
            pdf_path=get_app_root() / "rule.pdf",
            parent=self,
        )
        layout.addWidget(self.pdf_viewer)
