# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QFrame, QComboBox,
)


class TranslationPanel(QWidget):
    translate_requested = pyqtSignal(str, str)
    abort_requested = pyqtSignal()
    clipboard_translate_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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
        header_layout.addWidget(QLabel("🗣️ 1. 在线双路并行对照翻译", self, objectName="SectionHeader"))
        header_layout.addStretch()
        self.engine_label = QLabel("", self)
        self.engine_label.setStyleSheet(
            "color: #38bdf8; font-size: 11px; font-weight: bold; "
            "background-color: #1e1b4b; border: 1px solid #4338ca; border-radius: 6px; padding: 2px 10px;"
        )
        self.engine_label.hide()
        header_layout.addWidget(self.engine_label)
        frame_layout.addLayout(header_layout)

        translate_columns = QHBoxLayout()
        translate_columns.setSpacing(8)
        self.input_text = QTextEdit(self)
        self.input_text.setPlaceholderText("在此输入英文原始文本段落...")
        self.input_text.setCursor(Qt.CursorShape.IBeamCursor)
        translate_columns.addWidget(self.input_text, stretch=45)

        self.output_text = QTextEdit(self)
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("等待引擎翻译对照输出...")
        self.output_text.setCursor(Qt.CursorShape.IBeamCursor)
        translate_columns.addWidget(self.output_text, stretch=55)
        frame_layout.addLayout(translate_columns)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.combo_mode = QComboBox(self)
        self.combo_mode.setMinimumWidth(210)
        self.combo_mode.setFixedHeight(34)
        actions_layout.addWidget(self.combo_mode)

        self.btn_translate = QPushButton("🚀 运行双通道翻译", self)
        self.btn_translate.setObjectName("OnlineBtn")
        self.btn_translate.setMinimumWidth(140)
        self.btn_translate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_translate.clicked.connect(self._on_translate)
        actions_layout.addWidget(self.btn_translate, stretch=3)

        self.btn_abort = QPushButton("⏹ 中止", self)
        self.btn_abort.setObjectName("AbortBtn")
        self.btn_abort.setFixedWidth(50)
        self.btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_abort.clicked.connect(self.abort_requested.emit)
        self.btn_abort.setEnabled(False)
        actions_layout.addWidget(self.btn_abort)

        self.btn_clip = QPushButton("📋 读剪切板翻译", self)
        self.btn_clip.setObjectName("ClipBtn")
        self.btn_clip.setMinimumWidth(110)
        self.btn_clip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip.clicked.connect(self._on_clipboard_translate)
        actions_layout.addWidget(self.btn_clip, stretch=1)
        frame_layout.addLayout(actions_layout)

        layout.addWidget(self.frame)

    def _on_translate(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            return
        engine_mode = self._get_selected_engine_key()
        self.set_working(True)
        self.translate_requested.emit(text, engine_mode)

    def _on_clipboard_translate(self):
        from PyQt6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if text:
            self.input_text.setPlainText(text)
            self.clipboard_translate_requested.emit(text)

    def set_working(self, working: bool):
        self.btn_translate.setEnabled(not working)
        self.btn_translate.setText("⏳ 正在翻译中..." if working else "🚀 运行双通道翻译")
        self.btn_abort.setEnabled(working)

    def show_result(self, result_text: str, engine_label: str = "", elapsed: float = 0.0):
        self.output_text.setPlainText(result_text)
        if engine_label and "[双重降级失败]" not in result_text:
            time_str = f"{elapsed:.1f}s" if elapsed > 0 else ""
            self.engine_label.setText(
                f"🔧 {engine_label}  ⏱ {time_str}" if time_str else f"🔧 {engine_label}"
            )
            self.engine_label.show()
        else:
            self.engine_label.hide()
        self.set_working(False)

    def show_error(self, err: str):
        self.output_text.setPlainText(f"[系统级请求故障]: {err}")
        self.set_working(False)

    def _get_selected_engine_key(self) -> str:
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

    def get_selected_engine_key(self) -> str:
        return self._get_selected_engine_key()
