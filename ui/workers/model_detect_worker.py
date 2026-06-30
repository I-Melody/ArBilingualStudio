# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread, pyqtSignal
from engine.translators.ollama import OllamaTranslator
from engine.translators.marianmt import MarianMTTranslator
from engine.translators.argos import ArgosTranslator


class ModelDetectWorker(QThread):
    finished_detect = pyqtSignal(list)

    def run(self):
        offline_items = []

        if OllamaTranslator.is_available():
            offline_items.append("🤖 Ollama (本地大模型)")

        if MarianMTTranslator.has_local_model() and MarianMTTranslator.is_available():
            offline_items.append("📦 MarianMT (本地小模型)")

        if ArgosTranslator.has_local_model() and ArgosTranslator.is_available():
            offline_items.append("📦 Argos NMT (本地轻量级)")

        if offline_items:
            self.finished_detect.emit(offline_items)
