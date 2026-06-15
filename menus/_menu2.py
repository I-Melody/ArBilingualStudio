# -*- coding: utf-8 -*-
# 文件路径：menus/menu2.py

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFrame, QListWidget, QWidget, QLineEdit, QSlider
)
from PyQt6.QtCore import Qt
from .base_menu import BaseMenuWidget


class MenuWidget(BaseMenuWidget):
    """
    历史记录中心（对称结构体，完全规避指针残留）
    """
    def init_ui(self):
        self.setStyleSheet("""
            QFrame#SectionFrame {
                background-color: #161619;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#VideoFrame {
                background-color: #161619;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel#SectionHeader {
                color: #e4e4e7;
                font-weight: bold;
                font-size: 13px;
            }
            
            QTextEdit {
                background-color: #121214;
                color: #71717a;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px; 
            }
            
            QLineEdit#UrlInput {
                background-color: #121214;
                color: #52525b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                font-family: monospace;
            }
            
            QPushButton {
                color: #a1a1aa;
                font-weight: bold;
                border-radius: 6px;
                height: 34px;
                font-size: 12px;
                border: 1px solid #27272a;
                background-color: #18181b;
            }
            QPushButton:hover {
                background-color: #202023;
                color: #f4f4f5;
            }
            QPushButton#PlayerBtn {
                background-color: #18181b;
                color: #52525b;
                border: 1px solid #27272a;
                height: 28px;
            }
            
            QListWidget {
                background-color: #121214;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px 12px;
                margin-right: 6px;
                border: 1px solid #27272a;
                border-radius: 4px;
                background-color: #18181b;
                color: #71717a;
                font-weight: bold;
                font-size: 11px;
            }
            QListWidget::item:hover {
                background-color: #202023;
                color: #a1a1aa;
            }
            QListWidget::item:selected {
                background-color: #27272a;
                color: #e4e4e7;
                font-weight: bold;
                border: 1px solid #71717a;
            }
        """)

        main_horizontal_layout = QHBoxLayout(self)
        main_horizontal_layout.setContentsMargins(6, 6, 6, 6)
        main_horizontal_layout.setSpacing(10)

        # =========================================================================
        # 【对称左面板】历史视频播放区 (占 40%)
        # =========================================================================
        self.video_frame = QFrame(self)
        self.video_frame.setObjectName("VideoFrame")
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(8, 8, 8, 8)
        video_layout.setSpacing(10)

        video_layout.addWidget(QLabel("📹 历史播放备份", self, objectName="SectionHeader"))

        url_layout = QHBoxLayout()
        url_layout.setSpacing(6)
        self.url_input = QLineEdit(self)
        self.url_input.setObjectName("UrlInput")
        self.url_input.setReadOnly(True)
        self.url_input.setText("https://commondatastorage.googleapis.com/.../sample/BigBuckBunny.mp4")
        self.url_input.setCursor(Qt.CursorShape.IBeamCursor)
        url_layout.addWidget(self.url_input)

        self.btn_load_video = QPushButton("已载入", self)
        self.btn_load_video.setObjectName("PlayerBtn")
        self.btn_load_video.setFixedWidth(50)
        self.btn_load_video.setEnabled(False)
        url_layout.addWidget(self.btn_load_video)
        video_layout.addLayout(url_layout)

        # 历史播放器采用纯静态展示
        self.static_canvas = QFrame(self)
        self.static_canvas.setStyleSheet("background-color: #000000; border: 1px solid #27272a; border-radius: 6px;")
        canvas_lbl_layout = QVBoxLayout(self.static_canvas)
        canvas_lbl_layout.addWidget(QLabel("🎥 历史快照预览画布 (静态挂起)", self, alignment=Qt.AlignmentFlag.AlignCenter))
        video_layout.addWidget(self.static_canvas, stretch=1)

        # 历史播控条
        self.control_bar = QWidget(self)
        control_bar_layout = QHBoxLayout(self.control_bar)
        control_bar_layout.setContentsMargins(0, 0, 0, 0)
        control_bar_layout.setSpacing(8)

        self.btn_play_pause = QPushButton("▶ 播放", self)
        self.btn_play_pause.setObjectName("PlayerBtn")
        self.btn_play_pause.setFixedWidth(65)
        self.btn_play_pause.setEnabled(False)
        control_bar_layout.addWidget(self.btn_play_pause)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.progress_slider.setEnabled(False)
        control_bar_layout.addWidget(self.progress_slider)

        self.time_label = QLabel("00:42 / 03:50", self)
        self.time_label.setStyleSheet("color: #52525b; font-family: monospace; font-size: 11px;")
        control_bar_layout.addWidget(self.time_label)
        video_layout.addWidget(self.control_bar)

        main_horizontal_layout.addWidget(self.video_frame, stretch=40)

        # =========================================================================
        # 【右面板】原历史中心细节
        # =========================================================================
        right_main_widget = QWidget(self)
        right_main_layout = QVBoxLayout(right_main_widget)
        right_main_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.setSpacing(10)

        self.upper_frame = QFrame(self)
        self.upper_frame.setObjectName("SectionFrame")
        upper_layout = QVBoxLayout(self.upper_frame)
        upper_layout.setContentsMargins(8, 8, 8, 8)
        upper_layout.setSpacing(8)

        upper_layout.addWidget(QLabel("📂 1. 在线对照翻译历史快照", self, objectName="SectionHeader"))

        translate_columns = QHBoxLayout()
        translate_columns.setSpacing(8)
        
        self.input_a = QTextEdit(self)
        self.input_a.setReadOnly(True)
        self.input_a.setCursor(Qt.CursorShape.IBeamCursor)
        self.input_a.setPlainText("The narrator introduces the video concisely and quickly.")
        translate_columns.addWidget(self.input_a, stretch=45)

        self.output_a = QTextEdit(self)
        self.output_a.setReadOnly(True)
        self.output_a.setCursor(Qt.CursorShape.IBeamCursor)
        self.output_a.setPlainText("旁白简明扼要、迅速地介绍了该视频内容。")
        translate_columns.addWidget(self.output_a, stretch=55)

        upper_layout.addLayout(translate_columns)

        self.btn_online = QPushButton("🔄 载入上一条在线翻译历史", self)
        self.btn_online.setCursor(Qt.CursorShape.PointingHandCursor)
        upper_layout.addWidget(self.btn_online)

        right_main_layout.addWidget(self.upper_frame, stretch=2)

        self.lower_frame = QFrame(self)
        self.lower_frame.setObjectName("SectionFrame")
        lower_layout = QVBoxLayout(self.lower_frame)
        lower_layout.setContentsMargins(8, 8, 8, 8)
        lower_layout.setSpacing(8)

        lower_layout.addWidget(QLabel("📜 2. 本地离线整理历史备份", self, objectName="SectionHeader"))

        format_columns = QHBoxLayout()
        format_columns.setSpacing(8)

        self.src_input = QTextEdit(self)
        self.src_input.setReadOnly(True)
        self.src_input.setCursor(Qt.CursorShape.IBeamCursor)
        self.src_input.setPlainText(
            '[{"step_id": "step_1", "segment_id": "event_01", "timestamp": "00:00-00:25", "content": "Bruce name origin.", "bridge": "Consistently brisk format."}]'
        )
        format_columns.addWidget(self.src_input, stretch=45)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.list_widget = QListWidget(self)
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setFixedHeight(36)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.list_widget.currentRowChanged.connect(self.display_item_detail)
        right_layout.addWidget(self.list_widget)

        self.detail_display = QTextEdit(self)
        self.detail_display.setReadOnly(True)
        self.detail_display.setCursor(Qt.CursorShape.ArrowCursor)
        right_layout.addWidget(self.detail_display)

        format_columns.addWidget(right_container, stretch=55)

        lower_layout.addLayout(format_columns)

        self.btn_offline = QPushButton("🧹 清除本地离线历史留痕", self)
        self.btn_offline.setCursor(Qt.CursorShape.PointingHandCursor)
        lower_layout.addWidget(self.btn_offline)

        right_main_layout.addWidget(self.lower_frame, stretch=3)
        
        main_horizontal_layout.addWidget(right_main_widget, stretch=60)

        self.load_mock_history()

    def load_mock_history(self):
        self.processed_items = [
            {
                "step_id": "step_1",
                "segment_id": "event_01",
                "modality": "AUDIO",
                "timestamp": "00:00.000-00:25.500",
                "content": "The off-screen narrator quickly introduces the video.",
                "content_local_zh": "画面外的旁白迅速介绍了视频。",
                "bridge": "Consistently brisk delivery signals a trivia format.",
                "bridge_local_zh": "持续轻快的表达传递了花絮信息特征。"
            },
            {
                "step_id": "step_2",
                "segment_id": "event_02",
                "modality": "VISUAL",
                "timestamp": "00:30.000-00:59.000",
                "content": "The visuals rapidly cycle through Willem Dafoe.",
                "content_local_zh": "画面迅速扫过演员威廉·达福的影像。",
                "bridge": "Fast-changing reference images present multiple facts.",
                "bridge_local_zh": "快速切换的参照图片呈现了多组事实。"
            }
        ]
        for item in self.processed_items:
            title = f"{item['step_id']}"
            self.list_widget.addItem(title)
        
        if self.processed_items:
            self.list_widget.setCurrentRow(0)

    def display_item_detail(self, index: int):
        if index < 0 or index >= len(self.processed_items):
            self.detail_display.clear()
            return
        item = self.processed_items[index]
        
        html_content = f"""
        <div style="line-height: 1.6; font-size: 13.5px; color: #a1a1aa; font-family: sans-serif;">
            <div style="border-bottom: 1px solid #27272a; padding-bottom: 4px; margin-bottom: 8px;">
                <span style="font-size: 15px; font-weight: bold; color: #71717a;">📜 历史快照详情</span>
                <span style="background-color: #27272a; color: #a1a1aa; font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 10px; font-weight: bold;">
                    {item['step_id']} / {item['segment_id']}
                </span>
            </div>
            
            <table style="width: 100%; margin-bottom: 8px;">
                <tr>
                    <td style="color: #52525b; width: 60px;">⏱️ 时间轴:</td>
                    <td style="color: #71717a; font-weight: bold; font-family: monospace;">{item['timestamp']}</td>
                </tr>
                <tr>
                    <td style="color: #52525b;">🎙️ 模态:</td>
                    <td style="color: #71717a; font-weight: bold;">{item['modality']}</td>
                </tr>
            </table>
            
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px; margin-bottom: 6px;">
                <b style="color: #52525b; font-size: 12.5px;">📝 原始描述 Content：</b>
                <span style="color: #71717a; display: block; margin-top: 4px;">{item['content']}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #52525b; font-size: 11.5px;">🤖 离线翻译对照 Output：</b>
                    <span style="color: #71717a; display: block; margin-top: 4px;">{item['content_local_zh']}</span>
                </div>
            </div>
            
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px;">
                <b style="color: #52525b; font-size: 12.5px;">🔗 逻辑关联与过渡 Bridge：</b>
                <span style="color: #71717a; font-style: italic; display: block; margin-top: 4px;">{item['bridge']}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #52525b; font-size: 11.5px;">🤖 离线翻译对照 Output：</b>
                    <span style="color: #71717a; display: block; margin-top: 4px;">{item['bridge_local_zh']}</span>
                </div>
            </div>
        </div>
        """
        self.detail_display.setHtml(html_content)