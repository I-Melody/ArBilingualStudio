# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QLineEdit, QPushButton,
)

from .base_menu import BaseMenuWidget
from .panels.video_panel import VideoPanel
from .panels.translation_panel import TranslationPanel
from .panels.timeline_panel import TimelinePanel
from ui.workers.translate_worker import TranslateWorker, FormatWorker
from ui.workers.model_detect_worker import ModelDetectWorker
from ui.widgets.browser_window import WebBrowserWindow


class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        self._browser_win = None
        self.trans_worker = None
        self.format_worker = None

        self._setup_stylesheet()
        self._create_panels()
        self._setup_comboboxes()

    def _setup_stylesheet(self):
        self.setStyleSheet("""
            QFrame#SectionFrame, QFrame#VideoFrame, QFrame#SubLeftFrame { background-color: #161619; border: 1px solid #27272a; border-radius: 8px; padding: 10px; }
            QFrame#VideoFrame:focus { border: 1px solid #3b82f6; }
            QLabel#SectionHeader { color: #e4e4e7; font-weight: bold; font-size: 13px; }
            QTextEdit, QTextBrowser, QLineEdit, QComboBox, QListWidget { background-color: #121214; color: #e4e4e7; border: 1px solid #27272a; border-radius: 6px; padding: 8px; font-size: 12px; }
            QTextEdit, QTextBrowser { font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; padding: 10px; }
            QTextEdit:focus, QLineEdit:focus, QTextBrowser:focus { border: 1px solid #3b82f6; }
            QLineEdit#UrlInput { font-family: monospace; }
            QComboBox { height: 34px; font-size: 11px; font-weight: bold; background-color: #1c1c1f; }
            QComboBox::drop-down { border: none; width: 15px; }
            QComboBox QAbstractItemView { background-color: #1c1c1f; color: #e4e4e7; selection-background-color: #1e3a8a; selection-color: #60a5fa; border: 1px solid #27272a; }
            QPushButton { color: white; font-weight: bold; border-radius: 6px; height: 34px; font-size: 12px; border: none; }
            QPushButton#OnlineBtn { background-color: #2563eb; }
            QPushButton#OnlineBtn:hover { background-color: #1d4ed8; }
            QPushButton#OfflineBtn { background-color: #0d9488; }
            QPushButton#OfflineBtn:hover { background-color: #0f766e; }
            QPushButton#PlayerBtn { background-color: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; height: 28px; }
            QPushButton#PlayerBtn:hover { background-color: #3f3f46; }
            QPushButton#PlayerBtn:disabled { background-color: #121214; color: #52525b; border: 1px solid #27272a; }
            QPushButton#ClipBtn { background-color: #1e1b4b; color: #c084fc; border: 1px solid #4338ca; }
            QPushButton#ClipBtn:hover { background-color: #312e81; color: #e9d5ff; }
            QPushButton#AbortBtn { background-color: #3f3f46; color: #e4e4e7; border: 1px solid #52525b; }
            QPushButton#AbortBtn:hover { background-color: #ef4444; color: white; border-color: #ef4444; }
            QPushButton#AbortBtn:disabled { background-color: #121214; color: #52525b; border: 1px solid #27272a; }
            QPushButton#CapsuleBtn { background-color: #1c1c1f; color: #d4d4d8; border: 1px solid #27272a; border-radius: 12px; padding: 4px 12px; font-size: 11px; height: 24px; font-weight: 500; }
            QPushButton#CapsuleBtn:hover { background-color: #27272a; border-color: #3f3f46; color: #ffffff; }
            QListWidget { padding: 2px; }
            QListWidget::item { padding: 4px 12px; margin-right: 6px; border: 1px solid #27272a; border-radius: 4px; background-color: #18181b; color: #a1a1aa; font-weight: bold; font-size: 11px; }
            QListWidget::item:hover { background-color: #27272a; color: #ffffff; }
            QListWidget::item:selected { background-color: #1e3a8a; color: #60a5fa; font-weight: bold; border: 1px solid #3b82f6; }
        """)

    def _create_panels(self):
        main_horizontal_layout = QHBoxLayout(self)
        main_horizontal_layout.setContentsMargins(6, 6, 6, 6)
        main_horizontal_layout.setSpacing(10)

        left_main_widget = QWidget(self)
        left_main_layout = QVBoxLayout(left_main_widget)
        left_main_layout.setContentsMargins(0, 0, 0, 0)
        left_main_layout.setSpacing(10)

        self.video_panel = VideoPanel(self)
        self.video_panel.status_message.connect(self._show_status)
        self.video_panel.one_click_fill.connect(self._one_click_fill)
        self.video_panel.clipboard_video_loaded.connect(
            lambda t: self._show_status("🎬 成功从剪切板载入视频！", 3000)
        )
        left_main_layout.addWidget(self.video_panel, stretch=3)

        self._setup_web_panel(left_main_layout)

        main_horizontal_layout.addWidget(left_main_widget, stretch=45)

        right_main_widget = QWidget(self)
        right_main_layout = QVBoxLayout(right_main_widget)
        right_main_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.setSpacing(10)

        self.translation_panel = TranslationPanel(self)
        self.translation_panel.translate_requested.connect(self._on_translate_requested)
        self.translation_panel.abort_requested.connect(self._abort_translation)
        self.translation_panel.clipboard_translate_requested.connect(self._on_clipboard_translate)
        right_main_layout.addWidget(self.translation_panel, stretch=2)

        self.timeline_panel = TimelinePanel(self)
        self.timeline_panel.format_requested.connect(self._on_format_requested)
        self.timeline_panel.abort_requested.connect(self._abort_formatting)
        self.timeline_panel.clipboard_format_requested.connect(self._on_clipboard_format)
        self.timeline_panel.jump_to_timestamp.connect(self._on_jump_to_timestamp)
        right_main_layout.addWidget(self.timeline_panel, stretch=3)

        main_horizontal_layout.addWidget(right_main_widget, stretch=55)

    def _setup_web_panel(self, parent_layout):
        from PyQt6.QtWidgets import QFrame
        self.web_frame = QFrame(self)
        self.web_frame.setObjectName("SubLeftFrame")
        web_layout = QVBoxLayout(self.web_frame)
        web_layout.setContentsMargins(8, 8, 8, 8)
        web_layout.setSpacing(6)

        header = QLabel("🌐 网页操作", self, objectName="SectionHeader")
        web_layout.addWidget(header)
        web_layout.addStretch()

        url_row = QWidget(self)
        url_row.setStyleSheet("background-color: transparent;")
        url_layout = QHBoxLayout(url_row)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(6)

        self.web_url_input = QLineEdit(self)
        self.web_url_input.setPlaceholderText("在此输入网页URL地址...")
        self.web_url_input.setCursor(Qt.CursorShape.IBeamCursor)
        self.web_url_input.returnPressed.connect(self._open_web_url)
        url_layout.addWidget(self.web_url_input)

        self.btn_open_url = QPushButton("打开", self)
        self.btn_open_url.setFixedWidth(50)
        self.btn_open_url.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_url.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open_url.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; border-radius: 4px; height: 28px; font-size: 11px; border: none;"
        )
        self.btn_open_url.clicked.connect(self._open_web_url)
        url_layout.addWidget(self.btn_open_url)

        web_layout.addWidget(url_row)
        parent_layout.addWidget(self.web_frame, stretch=2)

    def _setup_comboboxes(self):
        routing_items = ["☁️ 在线优先 (自动降级)", "💻 本地优先 (自动降级)"]
        for combo in [self.translation_panel.combo_mode, self.timeline_panel.combo_mode]:
            combo.clear()
            combo.addItems(routing_items)

        self.detect_worker = ModelDetectWorker(self)
        self.detect_worker.finished_detect.connect(self._apply_detected_models)
        self.detect_worker.start()

    def _apply_detected_models(self, offline_items):
        for combo in [self.translation_panel.combo_mode, self.timeline_panel.combo_mode]:
            combo.addItems(offline_items)
            ollama_text = "🤖 Ollama (本地大模型)"
            idx = combo.findText(ollama_text)
            if idx != -1:
                combo.setCurrentIndex(idx)

    def _show_status(self, message: str, timeout: int = 3000):
        mw = self.window()
        if mw and hasattr(mw, "status_bar"):
            mw.status_bar.showMessage(message, timeout)

    def _on_jump_to_timestamp(self, raw_timestamp: str):
        self.video_panel.timestamp_input.setText(raw_timestamp)
        self.video_panel.jump_to_timestamp()

    def _on_translate_requested(self, text: str, engine_mode: str):
        self.trans_worker = TranslateWorker(self.engine, text, engine_mode, self.translator_service)
        self.trans_worker.finished.connect(self._on_translation_finished)
        self.trans_worker.error.connect(self.translation_panel.show_error)
        self.trans_worker.start()

    def _on_translation_finished(self, result_text, engine_label="", elapsed=0.0):
        self.translation_panel.show_result(result_text, engine_label, elapsed)

    def _abort_translation(self):
        if self.trans_worker and self.trans_worker.isRunning():
            self.trans_worker.terminate()
            self.trans_worker.wait()
            self.translation_panel.engine_label.hide()
            self.translation_panel.set_working(False)
            self._show_status("⏹ 在线翻译任务已由用户强行中止。", 3000)

    def _on_clipboard_translate(self, text: str):
        self.translation_panel.input_text.setPlainText(text)
        self._on_translate_requested(text, self.translation_panel.get_selected_engine_key())

    def _on_format_requested(self, text: str, engine_mode: str):
        self.format_worker = FormatWorker(self.engine, source_text=text, engine_mode=engine_mode,
                                          translator_service=self.translator_service)
        self.format_worker.finished.connect(self.timeline_panel.display_result)
        self.format_worker.error.connect(self.timeline_panel.show_error)
        self.format_worker.start()

    def _abort_formatting(self):
        if self.format_worker and self.format_worker.isRunning():
            self.format_worker.terminate()
            self.format_worker.wait()
            self.timeline_panel.engine_label.hide()
            self.timeline_panel.set_working(False)
            self._show_status("⏹ 离线格式化解析任务已由用户强行中止。", 3000)

    def _on_clipboard_format(self, text: str):
        self.timeline_panel.src_input.setPlainText(text)
        self._on_format_requested(text, self.timeline_panel.get_selected_engine_key())

    def _one_click_fill(self):
        mw = self.window()
        if not mw or not hasattr(mw, "clipboard_monitor"):
            self._show_status("📋 剪切板监听未就绪。", 3000)
            return

        recent = mw.clipboard_monitor.get_recent(3)
        if not recent:
            self._show_status("📋 剪切板历史为空，请先复制内容。", 3000)
            return

        first_text = recent[0].strip() if recent else ""
        first_is_url = first_text.lower().startswith(("http://", "https://"))
        items = recent if first_is_url else recent[:2]

        slots_filled = {"video": False, "translation": False, "timeline": False}

        for text in items:
            text = text.strip()
            if not text:
                continue
            is_video_url = (text.lower().startswith(("http://", "https://")) and
                           any(ext in text.lower() for ext in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".3gp")))
            is_json = text.startswith("[") and text.endswith("]")

            if is_video_url and not slots_filled["video"]:
                self.video_panel.url_input.setText(text)
                self.video_panel.load_video_url()
                slots_filled["video"] = True
            elif is_json and not slots_filled["timeline"]:
                self.timeline_panel.src_input.setPlainText(text)
                self._on_format_requested(text, self.timeline_panel.get_selected_engine_key())
                slots_filled["timeline"] = True
            elif not slots_filled["translation"]:
                self.translation_panel.input_text.setPlainText(text)
                self._on_translate_requested(text, self.translation_panel.get_selected_engine_key())
                slots_filled["translation"] = True

            if all(slots_filled.values()):
                break

        filled = sum(1 for v in slots_filled.values() if v)
        parts = []
        if slots_filled["video"]:
            parts.append("视频链接")
        if slots_filled["translation"]:
            parts.append("翻译区")
        if slots_filled["timeline"]:
            parts.append("时间线解析")
        self._show_status(f"🚀 一键填充完成：{', '.join(parts)} 共 {filled} 个区域。", 4000)

    def _open_web_url(self):
        url = self.web_url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.web_url_input.setText(url)

        if self._browser_win is None:
            self._browser_win = WebBrowserWindow()
            self._browser_win.data_captured.connect(self._on_browser_data)
        self._browser_win.open_url(url)
        self._browser_win.show()
        self._show_status(f"🌐 已在内置浏览器中打开: {url}", 4000)

    def _on_browser_data(self, data: str):
        pass

    def on_unload(self):
        if self._browser_win is not None:
            self._browser_win.close()
            self._browser_win = None
        self.video_panel.stop()

    def keyPressEvent(self, event):
        if not self.video_panel.frame.hasFocus():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.video_panel.toggle_playback()
        elif key == Qt.Key.Key_Left:
            self.video_panel.seek_offset(-5000)
        elif key == Qt.Key.Key_Right:
            self.video_panel.seek_offset(5000)
        elif key == Qt.Key.Key_Up:
            self.video_panel.adjust_volume_offset(5)
        elif key == Qt.Key.Key_Down:
            self.video_panel.adjust_volume_offset(-5)
        else:
            super().keyPressEvent(event)

    def open_external_video_window(self):
        self.video_panel.open_external_video_window()

    def restore_video_to_embedded(self):
        self.video_panel.restore_video_to_embedded()

    def toggle_playback(self):
        self.video_panel.toggle_playback()

    def seek_offset(self, ms_offset: int):
        self.video_panel.seek_offset(ms_offset)

    def adjust_volume_offset(self, vol_offset: int):
        self.video_panel.adjust_volume_offset(vol_offset)
