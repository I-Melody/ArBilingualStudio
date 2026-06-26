# -*- coding: utf-8 -*-
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QPushButton


class CapsuleButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("CapsuleBtn")
        self.original_text = text
        self.clicked.connect(self.trigger_copied_effect)

    def trigger_copied_effect(self):
        self.setText("✓ 已复制")
        self.setStyleSheet("QPushButton#CapsuleBtn { background-color: #059669; color: #ffffff; border: 1px solid #34d399; font-weight: bold; }")
        QTimer.singleShot(800, self.restore_state)

    def restore_state(self):
        self.setText(self.original_text)
        self.setStyleSheet("")
