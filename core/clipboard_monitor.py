# -*- coding: utf-8 -*-
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class ClipboardMonitor(QObject):
    history_changed = pyqtSignal()

    def __init__(self, parent=None, max_items=20):
        super().__init__(parent)
        self._history = deque(maxlen=max_items)
        self._last_written = None
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_data_changed)
        self._capture_initial()

    def _capture_initial(self):
        text = self._clipboard.text().strip()
        if text:
            self._history.append(text)

    def _on_data_changed(self):
        text = self._clipboard.text().strip()
        if not text:
            return
        if self._last_written == text:
            self._last_written = None
            return
        if self._history and self._history[-1] == text:
            return
        self._history.append(text)
        self.history_changed.emit()

    def get_recent(self, n=3):
        items = list(self._history)
        return list(reversed(items[-n:]))

    def mark_written(self, text):
        self._last_written = text
