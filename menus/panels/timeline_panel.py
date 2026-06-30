# -*- coding: utf-8 -*-
import html as html_mod
import re
from typing import List

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QTextBrowser, QPushButton, QLabel, QFrame, QComboBox, QListWidget,
)

from core.paths import get_app_root


class TimelinePanel(QWidget):
    format_requested = pyqtSignal(str, str)
    abort_requested = pyqtSignal()
    clipboard_format_requested = pyqtSignal(str)
    jump_to_timestamp = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processed_items: List[dict] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.frame = QFrame(self)
        self.frame.setObjectName("SectionFrame")
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QLabel("🧬 2. 事件节点格式优化与离线解析", self, objectName="SectionHeader"))
        header_layout.addStretch()
        self.engine_label = QLabel("", self)
        self.engine_label.setStyleSheet(
            "color: #38bdf8; font-size: 11px; font-weight: bold; "
            "background-color: #1e1b4b; border: 1px solid #4338ca; border-radius: 6px; padding: 2px 10px;"
        )
        self.engine_label.hide()
        header_layout.addWidget(self.engine_label)
        frame_layout.addLayout(header_layout)

        format_columns = QHBoxLayout()
        format_columns.setSpacing(8)
        self.src_input = QTextEdit(self)
        self.src_input.setPlaceholderText("在此粘贴多模态分析 JSON 数组原始文本...")
        self.src_input.setCursor(Qt.CursorShape.IBeamCursor)
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
        self.list_widget.currentRowChanged.connect(self._display_item_detail)
        right_layout.addWidget(self.list_widget)

        self.detail_display = QTextBrowser(self)
        self.detail_display.setCursor(Qt.CursorShape.ArrowCursor)
        self.detail_display.setOpenLinks(False)
        self.detail_display.anchorClicked.connect(self._on_anchor_clicked)
        right_layout.addWidget(self.detail_display)

        format_columns.addWidget(right_container, stretch=55)
        frame_layout.addLayout(format_columns)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.combo_mode = QComboBox(self)
        self.combo_mode.setMinimumWidth(210)
        self.combo_mode.setFixedHeight(34)
        actions_layout.addWidget(self.combo_mode)

        self.btn_format = QPushButton("⚡ 执行格式整理与解析", self)
        self.btn_format.setObjectName("OfflineBtn")
        self.btn_format.setMinimumWidth(140)
        self.btn_format.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_format.clicked.connect(self._on_format)
        actions_layout.addWidget(self.btn_format, stretch=3)

        self.btn_abort = QPushButton("⏹ 中止", self)
        self.btn_abort.setObjectName("AbortBtn")
        self.btn_abort.setFixedWidth(50)
        self.btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_abort.clicked.connect(self.abort_requested.emit)
        self.btn_abort.setEnabled(False)
        actions_layout.addWidget(self.btn_abort)

        self.btn_clip = QPushButton("📋 读剪切板解析", self)
        self.btn_clip.setObjectName("ClipBtn")
        self.btn_clip.setMinimumWidth(110)
        self.btn_clip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip.clicked.connect(self._on_clipboard_format)
        actions_layout.addWidget(self.btn_clip, stretch=1)

        frame_layout.addLayout(actions_layout)
        layout.addWidget(self.frame)

    def _on_format(self):
        text = self.src_input.toPlainText().strip()
        if not text:
            return
        engine_mode = self.get_selected_engine_key()
        self.set_working(True)
        self.format_requested.emit(text, engine_mode)

    def _on_clipboard_format(self):
        from PyQt6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if text:
            self.src_input.setPlainText(text)
            self.clipboard_format_requested.emit(text)

    def set_working(self, working: bool):
        self.btn_format.setEnabled(not working)
        self.btn_format.setText("⏳ 正在解析中..." if working else "⚡ 执行格式整理与解析")
        self.btn_abort.setEnabled(working)

    def get_selected_engine_key(self) -> str:
        text = self.combo_mode.currentText()
        if "在线优先" in text:
            return "online_first"
        elif "本地优先" in text:
            return "local_first"
        elif "Ollama" in text:
            return "ollama"
        elif "MarianMT" in text:
            return "transformers"
        elif "Argos" in text:
            return "argos"
        return "online_first"

    def display_result(self, result_context):
        self.list_widget.clear()
        self.detail_display.clear()
        is_timeline = result_context.metadata.get("is_timeline", False)

        engine_label = result_context.metadata.get("engine_used", "")
        elapsed = result_context.metadata.get("elapsed", 0.0)
        if engine_label and is_timeline:
            time_str = f"{elapsed:.1f}s" if elapsed > 0 else ""
            self.engine_label.setText(
                f"🔧 {engine_label}  ⏱ {time_str}" if time_str else f"🔧 {engine_label}"
            )
            self.engine_label.show()
        else:
            self.engine_label.hide()

        if is_timeline:
            self.processed_items = result_context.metadata.get("timeline_processed", [])
            for item in self.processed_items:
                self.list_widget.addItem(f"{item['step_id']}")
        else:
            self.processed_items = []
            for idx, para in enumerate(result_context.processed_source_segments):
                self.list_widget.addItem(f"para_{idx+1}")
                self.processed_items.append({
                    "step_id": "N/A", "segment_id": f"para_{idx+1}", "modality": "TEXT",
                    "timestamp": "N/A", "content": para, "content_local_zh": "（暂不支持）",
                    "bridge": "无逻辑说明", "bridge_local_zh": "（暂不支持）",
                })

        if self.processed_items:
            self.list_widget.setCurrentRow(0)
        self.set_working(False)

    def show_error(self, err: str):
        self.detail_display.setPlainText(f"[引擎崩溃]: {err}")
        self.set_working(False)

    def _display_item_detail(self, index: int):
        if index < 0 or index >= len(self.processed_items):
            self.detail_display.clear()
            return
        item = self.processed_items[index]
        c_text = html_mod.escape(item['content'])
        b_text = html_mod.escape(item['bridge'])

        hl_path = get_app_root() / "highlight.txt"
        if hl_path.exists():
            try:
                with open(hl_path, "r", encoding="utf-8") as f:
                    keywords = [line.strip() for line in f if line.strip()]
                for kw in keywords:
                    pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                    repl = lambda m: f'<span style="background-color: #15803d; color: #ffffff; padding: 0 4px; border-radius: 4px; font-weight: bold;">{m.group(0)}</span>'
                    c_text = pattern.sub(repl, c_text)
                    b_text = pattern.sub(repl, b_text)
            except Exception:
                pass

        html_content = f"""
        <div style="line-height: 1.6; font-size: 13.5px; color: #e4e4e7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div style="border-bottom: 1px solid #27272a; padding-bottom: 4px; margin-bottom: 8px;">
                <span style="font-size: 15px; font-weight: bold; color: #3b82f6;">🎬 节点详情</span>
                <span style="background-color: #1e3a8a; color: #60a5fa; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 10px; font-weight: bold;">
                    {item['step_id']} / {item['segment_id']}
                </span>
            </div>
            <table style="width: 100%; margin-bottom: 8px;">
                <tr>
                    <td style="color: #71717a; width: 60px;">⏱️ 时间轴:</td>
                    <td><a href="jump:{item['timestamp']}" style="color: #10b981; text-decoration: none; font-weight: bold; font-family: monospace;">{item['timestamp']}</a></td>
                </tr>
                <tr>
                    <td style="color: #71717a;">🎙️ 模态:</td>
                    <td style="color: #f59e0b; font-weight: bold;">{item['modality']}</td>
                </tr>
            </table>
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px; margin-bottom: 6px;">
                <b style="color: #a1a1aa; font-size: 12.5px;">📝 原始描述 Content：</b>
                <span style="color: #f4f4f5; display: block; margin-top: 4px;">{c_text}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #38bdf8; font-size: 11.5px;">🤖 翻译：</b>
                    <span style="color: #60a5fa; display: block; margin-top: 4px;">{item['content_local_zh']}</span>
                </div>
            </div>
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px;">
                <b style="color: #a1a1aa; font-size: 12.5px;">🔗 逻辑关联与过渡 Bridge：</b>
                <span style="color: #e4e4e7; font-style: italic; display: block; margin-top: 4px;">{b_text}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #38bdf8; font-size: 11.5px;">🤖 翻译：</b>
                    <span style="color: #60a5fa; display: block; margin-top: 4px;">{item['bridge_local_zh']}</span>
                </div>
            </div>
        </div>
        """
        self.detail_display.setHtml(html_content)

    def _on_anchor_clicked(self, qurl: QUrl):
        url_str = qurl.toString()
        if url_str.startswith("jump:"):
            raw_timestamp = url_str.split("jump:")[1]
            start_time = raw_timestamp.split("-")[0].strip() if "-" in raw_timestamp else raw_timestamp.strip()
            self.jump_to_timestamp.emit(start_time)
