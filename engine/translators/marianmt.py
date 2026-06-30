# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import List

from engine.translator_interface import ITranslator, TranslationResult
from engine.translators.base import suppress_noisy_loggers
from core.paths import get_app_root

MODEL_DIR_NAME = "opus-mt-en-zh"


class MarianMTTranslator(ITranslator):
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._models_dir = get_app_root() / "models"
        self._model_path = self._models_dir / MODEL_DIR_NAME

    @property
    def engine_name(self) -> str:
        return "MarianMT (本地小模型)"

    @classmethod
    def is_available(cls) -> bool:
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            return True
        except ImportError:
            return False

    @classmethod
    def has_local_model(cls) -> bool:
        models_dir = get_app_root() / "models"
        return (models_dir / MODEL_DIR_NAME).exists()

    def _ensure_loaded(self, from_code: str, to_code: str):
        if self._model is not None and self._tokenizer is not None:
            return
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        local_model_dir = self._models_dir / f"opus-mt-{from_code}-{to_code}"
        if local_model_dir.exists() and local_model_dir.is_dir():
            path_str = str(local_model_dir.resolve())
            if sys.platform == "win32" and any(ord(c) > 127 for c in path_str):
                raise RuntimeError("Windows path contains non-ASCII characters.")
            self._tokenizer = AutoTokenizer.from_pretrained(path_str)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(path_str)
        else:
            model_id = f"Helsinki-NLP/opus-mt-{from_code}-{to_code}"
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(model_id)

    def translate(self, text: str, from_code: str = "en", to_code: str = "zh") -> TranslationResult:
        try:
            results = self.batch_translate([text], from_code, to_code)
            return results[0] if results else TranslationResult(text="")
        except Exception as e:
            return TranslationResult(text=f"[MarianMT Error: {e}]", engine_label=self.engine_name, success=False, error=str(e))

    def batch_translate(self, texts: List[str], from_code: str = "en", to_code: str = "zh") -> List[TranslationResult]:
        try:
            suppress_noisy_loggers()
            self._ensure_loaded(from_code, to_code)
            inputs = self._tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            translated = self._model.generate(**inputs, max_new_tokens=512)
            decoded = self._tokenizer.batch_decode(translated, skip_special_tokens=True)
            return [TranslationResult(text=d, engine_label=self.engine_name) for d in decoded]
        except Exception as e:
            return [TranslationResult(text=f"[MarianMT Error: {e}]", engine_label=self.engine_name, success=False, error=str(e)) for _ in texts]
