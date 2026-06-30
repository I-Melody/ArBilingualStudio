# -*- coding: utf-8 -*-
import time
from PyQt6.QtCore import QThread, pyqtSignal
from engine.rule_engine import RuleContext
from engine.rules import TextCleanupRule, ActualTranslationRule, VideoTimelineParseRule
from engine.translator_service import TranslatorService


class TranslateWorker(QThread):
    finished = pyqtSignal(str, str, float)
    error = pyqtSignal(str)

    def __init__(self, engine, text: str, engine_mode: str, translator_service: TranslatorService):
        super().__init__()
        self.engine = engine
        self.text = text
        self.engine_mode = engine_mode
        self.translator_service = translator_service

    def run(self):
        try:
            t_start = time.time()
            self.engine.clear_rules()
            self.engine.register_rule(TextCleanupRule())
            self.engine.register_rule(ActualTranslationRule())
            context = RuleContext(raw_source=self.text)
            context.metadata["mode"] = "en_to_zh"
            context.metadata["engine"] = self.engine_mode
            context.metadata["translator_service"] = self.translator_service
            res = self.engine.run(context)
            elapsed = time.time() - t_start
            engine_label = res.metadata.get("engine_used", "未知引擎")
            self.finished.emit(res.raw_target, engine_label, elapsed)
        except Exception as e:
            self.error.emit(str(e))


class FormatWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, engine, source_text: str, engine_mode: str, translator_service: TranslatorService):
        super().__init__()
        self.engine = engine
        self.source_text = source_text
        self.engine_mode = engine_mode
        self.translator_service = translator_service

    def run(self):
        try:
            t_start = time.time()
            self.engine.clear_rules()
            self.engine.register_rule(VideoTimelineParseRule())
            self.engine.register_rule(TextCleanupRule())
            context = RuleContext(raw_source=self.source_text)
            context.metadata["engine"] = self.engine_mode
            context.metadata["translator_service"] = self.translator_service
            result = self.engine.run(context)
            result.metadata["elapsed"] = time.time() - t_start
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
