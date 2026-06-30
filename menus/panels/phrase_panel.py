# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QGridLayout, QApplication, QFrame,
)
from core.paths import get_app_root
from core.error_handler import log_warning
from ui.widgets.capsule_button import CapsuleButton


class PhrasePanel(QWidget):
    phrase_copied = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.frame = QFrame(self)
        self.frame.setObjectName("SubLeftFrame")
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(6)
        frame_layout.addWidget(QLabel("📋 便捷短语复制 (words.txt)", self, objectName="SectionHeader"))

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; } "
            "QScrollBar:vertical { border: none; background-color: #121214; width: 6px; border-radius: 3px; } "
            "QScrollBar::handle:vertical { background-color: #27272a; border-radius: 3px; }"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setContentsMargins(0, 0, 5, 0)
        self.grid_layout.setSpacing(6)
        self._load_words_config()
        scroll_area.setWidget(scroll_content)
        frame_layout.addWidget(scroll_area)

        layout.addWidget(self.frame)

    def _load_words_config(self):
        words_path = get_app_root() / "words.txt"
        phrases = []
        if words_path.exists():
            try:
                with open(words_path, "r", encoding="utf-8") as f:
                    phrases = [line.strip() for line in f if line.strip()]
            except Exception as e:
                log_warning(f"Failed to load words.txt: {e}")
        else:
            phrases = [
                "在线大雄兔###https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "在线玩具世界###https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
                "极佳编辑###Brilliant editing",
                "一键加速###Hurry up",
                "Check this",
                "Behind scenes",
            ]
            try:
                with open(words_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(phrases))
            except Exception:
                pass

        cols = 2
        for idx, text in enumerate(phrases):
            row = idx // cols
            col = idx % cols
            if "###" in text:
                parts = text.split("###", 1)
                title_part = parts[0].strip()
                copy_part = parts[1].strip()
                cell_widget = QWidget(self)
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(4)
                title_lbl = QLabel(title_part, self)
                title_lbl.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold;")
                btn = CapsuleButton(copy_part, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda checked, t=copy_part: self._on_copy(t))
                cell_layout.addWidget(title_lbl)
                cell_layout.addWidget(btn, stretch=1)
                self.grid_layout.addWidget(cell_widget, row, col)
            else:
                btn = CapsuleButton(text, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda checked, t=text: self._on_copy(t))
                self.grid_layout.addWidget(btn, row, col)

    def _on_copy(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.phrase_copied.emit(text)
