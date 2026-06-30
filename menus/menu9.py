# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QWidget, QFrame, QComboBox, QHBoxLayout,
)

from .base_menu import BaseMenuWidget
from core import config as app_config
from ui.widgets.ollama_config import OllamaConfigWidget


class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        self.setStyleSheet("""
            QFrame#ConfigFrame {
                background-color: #161619;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QLabel#ConfigLabel {
                color: #a1a1aa;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QLabel#SectionHeader {
                color: #e4e4e7;
                font-weight: bold;
                font-size: 13px;
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
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.header = QLabel("⚙️ 软件行为设置", self)
        self.header.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.header)

        self._add_ollama_section(layout)
        self._add_video_mode_section(layout)

        layout.addStretch()

        self.ollama_config.load_saved_settings()
        QTimer.singleShot(500, self.ollama_config.scan_local_ollama_tags)

    def _add_ollama_section(self, parent_layout):
        section_frame = QFrame(self)
        section_frame.setObjectName("ConfigFrame")
        section_layout = QVBoxLayout(section_frame)
        section_layout.setSpacing(8)
        section_layout.addWidget(QLabel("🤖 本地 Ollama 模型", self, objectName="SectionHeader"))

        self.ollama_config = OllamaConfigWidget(parent=self)
        section_layout.addWidget(self.ollama_config)
        parent_layout.addWidget(section_frame)

    def _add_video_mode_section(self, parent_layout):
        section_frame = QFrame(self)
        section_frame.setObjectName("ConfigFrame")
        section_layout = QVBoxLayout(section_frame)
        section_layout.setSpacing(8)
        section_layout.addWidget(QLabel("📹 视频播放加载方式", self, objectName="SectionHeader"))

        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        row_layout.addWidget(QLabel("加载策略:", self, objectName="ConfigLabel"))

        self.video_mode_combo = QComboBox(self)
        self.video_mode_combo.setObjectName("ConfigCombo")
        self.video_mode_combo.setMinimumWidth(260)
        self.video_mode_combo.addItem("💾 缓存至本地后播放 (推荐 - 支持离线重放)", app_config.VIDEO_MODE_CACHE)
        self.video_mode_combo.addItem("🌐 直链流播放 (不占用磁盘空间)", app_config.VIDEO_MODE_STREAM)
        self.video_mode_combo.currentIndexChanged.connect(self._on_video_mode_changed)
        row_layout.addWidget(self.video_mode_combo)

        row_layout.addStretch()
        section_layout.addWidget(row)

        hint = QLabel(
            "提示：切换后新加载的视频将使用选定的方式。直链模式下\"清空缓存\"按钮将自动隐藏。",
            self
        )
        hint.setStyleSheet("color: #71717a; font-size: 11px; padding-left: 4px;")
        hint.setWordWrap(True)
        section_layout.addWidget(hint)

        parent_layout.addWidget(section_frame)

        current_mode = app_config.get_video_playback_mode()
        idx = self.video_mode_combo.findData(current_mode)
        if idx >= 0:
            self.video_mode_combo.setCurrentIndex(idx)

    def _on_video_mode_changed(self):
        mode = self.video_mode_combo.currentData()
        if mode:
            app_config.set_video_playback_mode(mode)
