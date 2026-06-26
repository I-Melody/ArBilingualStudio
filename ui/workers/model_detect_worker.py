# -*- coding: utf-8 -*-
import urllib.request
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.paths import get_app_root


class ModelDetectWorker(QThread):
    finished_detect = pyqtSignal(list)

    def run(self):
        offline_items = []
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with opener.open(req, timeout=1.0) as response:
                if response.status == 200:
                    offline_items.append("🤖 Ollama (本地大模型)")
        except Exception:
            pass

        models_dir = get_app_root() / "models"

        has_marian_libs = False
        if (models_dir / "opus-mt-en-zh").exists():
            try:
                import transformers
                import torch
                import sentencepiece
                has_marian_libs = True
            except ImportError:
                pass
        if has_marian_libs:
            offline_items.append("📦 MarianMT (本地小模型)")

        has_argos_libs = False
        if len(list(models_dir.glob("translate-en_zh-*.argosmodel"))) > 0:
            try:
                import argostranslate
                has_argos_libs = True
            except ImportError:
                pass
        if has_argos_libs:
            offline_items.append("📦 Argos NMT (本地轻量级)")

        if offline_items:
            self.finished_detect.emit(offline_items)
