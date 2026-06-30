# -*- coding: utf-8 -*-
import logging
from typing import List, Optional, Callable

from engine.translator_interface import ITranslator, TranslationResult, is_translation_error
from engine.translators.ollama import OllamaTranslator
from engine.translators.marianmt import MarianMTTranslator
from engine.translators.argos import ArgosTranslator
from engine.translators.online import OnlineTranslator

ENGINE_ONLINE_FIRST = "online_first"
ENGINE_LOCAL_FIRST = "local_first"
ENGINE_OLLAMA = "ollama"
ENGINE_MARIANMT = "transformers"
ENGINE_ARGOS = "argos"


class TranslatorService:
    def __init__(self):
        self._ollama: Optional[OllamaTranslator] = None
        self._marianmt: Optional[MarianMTTranslator] = None
        self._argos: Optional[ArgosTranslator] = None
        self._online: Optional[OnlineTranslator] = None
        self._auto_detected = False

    def _auto_detect(self):
        if self._auto_detected:
            return
        self._auto_detected = True

        if OllamaTranslator.is_available():
            self._ollama = OllamaTranslator()
            return

        if MarianMTTranslator.has_local_model() and MarianMTTranslator.is_available():
            self._marianmt = MarianMTTranslator()
            return

        if ArgosTranslator.has_local_model() and ArgosTranslator.is_available():
            self._argos = ArgosTranslator()
            return

        if ArgosTranslator.is_available():
            self._argos = ArgosTranslator()
            return

        if MarianMTTranslator.is_available():
            self._marianmt = MarianMTTranslator()

    def ensure_ollama(self) -> OllamaTranslator:
        self._auto_detect()
        if self._ollama is None:
            self._ollama = OllamaTranslator()
        return self._ollama

    def ensure_marianmt(self) -> MarianMTTranslator:
        if self._marianmt is None:
            self._marianmt = MarianMTTranslator()
        return self._marianmt

    def ensure_argos(self) -> ArgosTranslator:
        if self._argos is None:
            self._argos = ArgosTranslator()
        return self._argos

    def ensure_online(self) -> OnlineTranslator:
        if self._online is None:
            self._online = OnlineTranslator()
        return self._online

    def _get_default_engine(self) -> Optional[str]:
        self._auto_detect()
        if self._ollama is not None:
            return ENGINE_OLLAMA
        if self._marianmt is not None:
            return ENGINE_MARIANMT
        if self._argos is not None:
            return ENGINE_ARGOS
        return None

    def translate(
        self,
        texts: List[str],
        from_code: str = "en",
        to_code: str = "zh",
        engine_mode: str = ENGINE_ONLINE_FIRST,
    ) -> List[TranslationResult]:
        if not texts:
            return []

        BATCH_SEP = '\n\n<span class="notranslate">###</span>\n\n'

        def _call_online() -> List[TranslationResult]:
            online = self.ensure_online()
            combined = BATCH_SEP.join([t for t in texts if t.strip()])
            if not combined.strip():
                return [TranslationResult(text="") for _ in texts]
            result = online.translate(combined, from_code, to_code)
            if result.success:
                return [TranslationResult(text=t, engine_label=result.engine_label) for t in [result.text] * len(texts)]
            raise RuntimeError(result.text)

        def _call_offline(force_engine: Optional[str] = None) -> List[TranslationResult]:
            effective = force_engine or self._get_default_engine()

            if effective == ENGINE_OLLAMA:
                ollama = self.ensure_ollama()
                return ollama.batch_translate(texts, from_code, to_code)

            combined = BATCH_SEP.join([t for t in texts if t.strip()])
            if not combined.strip():
                return [TranslationResult(text="") for _ in texts]

            translator: ITranslator
            if effective == ENGINE_MARIANMT:
                translator = self.ensure_marianmt()
            elif effective == ENGINE_ARGOS:
                translator = self.ensure_argos()
            else:
                translator = self.ensure_online()

            result = translator.translate(combined, from_code, to_code)
            if result.success:
                return [TranslationResult(text=t, engine_label=result.engine_label) for t in [result.text] * len(texts)]
            raise RuntimeError(result.text)

        if engine_mode == ENGINE_ONLINE_FIRST:
            try:
                return _call_online()
            except Exception as e:
                logging.warning(f"[TranslatorService] Online fallback to local: {e}")
            try:
                return _call_offline()
            except Exception as e2:
                logging.warning(f"[TranslatorService] Local fallback failed: {e2}")
        elif engine_mode == ENGINE_LOCAL_FIRST:
            try:
                return _call_offline()
            except Exception as e:
                logging.warning(f"[TranslatorService] Local fallback to online: {e}")
            try:
                return _call_online()
            except Exception as e2:
                logging.warning(f"[TranslatorService] Online fallback failed: {e2}")
        else:
            try:
                return _call_offline(force_engine=engine_mode)
            except Exception as e:
                logging.warning(f"[TranslatorService] Specified engine failed: {e}")

        return [TranslationResult(text="[所有翻译引擎均失败]", success=False) for _ in texts]

    def translate_single(
        self,
        text: str,
        from_code: str = "en",
        to_code: str = "zh",
        engine_mode: str = ENGINE_ONLINE_FIRST,
    ) -> TranslationResult:
        results = self.translate([text], from_code, to_code, engine_mode)
        return results[0] if results else TranslationResult(text="")

    def translate_batch_with_separator(
        self,
        texts: List[str],
        from_code: str = "en",
        to_code: str = "zh",
        engine_mode: str = ENGINE_ONLINE_FIRST,
    ) -> List[str]:
        """Translates each text separately, returns list of translated strings.

        Used by timeline parser: each content/bridge item gets its own translation.
        Optimizes Ollama with native batch, uses combined-separator for others.
        """
        valid_indices = []
        valid_texts = []
        for i, t in enumerate(texts):
            if t.strip():
                valid_indices.append(i)
                valid_texts.append(t.strip())

        if not valid_texts:
            return [""] * len(texts)

        results: List[str] = [""] * len(texts)

        effective = engine_mode
        if effective == ENGINE_OLLAMA or (effective in (ENGINE_LOCAL_FIRST, ENGINE_ONLINE_FIRST) and self._ollama):
            ollama = self.ensure_ollama()
            trans_results = ollama.batch_translate(valid_texts, from_code, to_code)
            for v_idx, tr in zip(valid_indices, trans_results):
                results[v_idx] = tr.text
            return results

        BATCH_SEP = '\n\n<span class="notranslate">###</span>\n\n'
        SPLIT_PATTERN = r'<span class="notranslate">###</span>'

        combined = BATCH_SEP.join(valid_texts)
        combined_result = self.translate_single(combined, from_code, to_code, effective)

        import re
        lines = [line.strip() for line in re.split(SPLIT_PATTERN, combined_result.text, flags=re.IGNORECASE)]
        if len(lines) == len(valid_texts):
            for v_idx, line in zip(valid_indices, lines):
                results[v_idx] = line
        else:
            for v_idx, text in zip(valid_indices, valid_texts):
                r = self.translate_single(text, from_code, to_code, effective)
                results[v_idx] = r.text
        return results
