# -*- coding: utf-8 -*-
import time
from PyQt6.QtCore import QThread, pyqtSignal
from engine.rule_engine import RuleContext
from engine.rules import TextCleanupRule, ActualTranslationRule, VideoTimelineParseRule


class TranslateWorker(QThread):
    finished = pyqtSignal(str, str, float)
    error = pyqtSignal(str)

    def __init__(self, engine, text: str, engine_mode: str):
        super().__init__()
        self.engine, self.text, self.engine_mode = engine, text, engine_mode

    def run(self):
        try:
            t_start = time.time()
            self.engine.clear_rules()
            self.engine.register_rule(TextCleanupRule())
            self.engine.register_rule(ActualTranslationRule())
            context = RuleContext(raw_source=self.text)
            context.metadata["mode"] = "en_to_zh"
            context.metadata["engine"] = self.engine_mode
            res = self.engine.run(context)
            elapsed = time.time() - t_start
            engine_label = res.metadata.get("engine_used", "未知引擎")
            self.finished.emit(res.raw_target, engine_label, elapsed)
        except Exception as e:
            self.error.emit(str(e))


class FormatWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, engine, source_text: str, engine_mode: str):
        super().__init__()
        self.engine, self.source_text, self.engine_mode = engine, source_text, engine_mode

    def run(self):
        try:
            t_start = time.time()
            self.engine.clear_rules()
            self.engine.register_rule(VideoTimelineParseRule())
            self.engine.register_rule(TextCleanupRule())
            context = RuleContext(raw_source=self.source_text)
            context.metadata["engine"] = self.engine_mode
            result = self.engine.run(context)
            result.metadata["elapsed"] = time.time() - t_start
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
