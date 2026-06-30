# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer

from .base_menu import BaseMenuWidget
from core.paths import get_app_root
from ui.widgets.ollama_config import OllamaConfigWidget
from ui.widgets.pdf_viewer import PdfViewerWidget


class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        self.setStyleSheet("""
            QFrame#ConfigFrame {
                background-color: #161619;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLabel#ConfigLabel {
                color: #a1a1aa;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QComboBox#ConfigCombo {
                background-color: #121214;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                height: 24px;
            }
            QPushButton#ConfigBtn {
                background-color: #1e1b4b;
                color: #c084fc;
                border: 1px solid #4338ca;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                height: 24px;
                padding: 0 10px;
            }
            QPushButton#ConfigBtn:hover {
                background-color: #312e81;
            }
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

        self.ollama_config = OllamaConfigWidget(parent=self)
        layout.addWidget(self.ollama_config)

        self.pdf_viewer = PdfViewerWidget(
            pdf_path=get_app_root() / "rule.pdf",
            parent=self
        )
        layout.addWidget(self.pdf_viewer)

        self.ollama_config.load_saved_settings()

        QTimer.singleShot(500, self.ollama_config.scan_local_ollama_tags)
