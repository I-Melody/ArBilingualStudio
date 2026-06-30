# -*- coding: utf-8 -*-
import json
import urllib.request
import urllib.parse
from typing import List

from engine.translator_interface import ITranslator, TranslationResult
from core.error_handler import log_warning

GOOGLE_API = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_API = "https://api.mymemory.translated.net/get"


class OnlineTranslator(ITranslator):
    def __init__(self):
        self._engines = [
            ("Google 在线翻译", self._translate_google),
            ("MyMemory 在线翻译", self._translate_mymemory),
        ]

    @property
    def engine_name(self) -> str:
        return "在线翻译 (Google + MyMemory)"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def translate(self, text: str, from_code: str = "en", to_code: str = "zh") -> TranslationResult:
        for label, fn in self._engines:
            try:
                result = fn(text, from_code, to_code)
                if result and "429" not in result and "接口错误" not in result:
                    return TranslationResult(text=result, engine_label=label)
            except Exception as e:
                log_warning(f"Online translator '{label}' failed: {e}")
                continue
        return TranslationResult(
            text="[翻译接口错误] 在线链路均无法建立连接。网络超时或被阻断。",
            engine_label="在线翻译",
            success=False,
            error="All online engines failed",
        )

    def batch_translate(self, texts: List[str], from_code: str = "en", to_code: str = "zh") -> List[TranslationResult]:
        return [self.translate(t, from_code, to_code) for t in texts]

    @staticmethod
    def _translate_google(text: str, from_lang: str, to_lang: str) -> str:
        sl = "en" if from_lang.startswith("en") else "zh-CN"
        tl = "zh-CN" if from_lang.startswith("en") else "en"
        query_string = urllib.parse.urlencode({"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": text})
        req = urllib.request.Request(f"{GOOGLE_API}?{query_string}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            segments = []
            if data and isinstance(data, list) and len(data) > 0:
                for segment in data[0]:
                    if isinstance(segment, list) and len(segment) > 0:
                        segments.append(segment[0])
            return "".join(segments)

    @staticmethod
    def _translate_mymemory(text: str, from_lang: str, to_lang: str) -> str:
        if len(text) <= 500:
            return OnlineTranslator._translate_mymemory_single(text, from_lang, to_lang)
        paragraphs = text.split("\n")
        chunks, current_chunk, current_len = [], [], 0
        for p in paragraphs:
            if current_len + len(p) + 1 > 450:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk, current_len = [p], len(p)
            else:
                current_chunk.append(p)
                current_len += len(p) + 1
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        translated = []
        for chunk in chunks:
            translated.append(OnlineTranslator._translate_mymemory_single(chunk, from_lang, to_lang) if chunk.strip() else "")
        return "\n".join(translated)

    @staticmethod
    def _translate_mymemory_single(text: str, from_lang: str, to_lang: str) -> str:
        f = "en" if from_lang.startswith("en") else "zh"
        t = "zh" if from_lang.startswith("zh") else "en"
        query_string = urllib.parse.urlencode({"q": text, "langpair": f"{f}|{t}"})
        req = urllib.request.Request(f"{MYMEMORY_API}?{query_string}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            if "responseData" in res_json:
                return res_json["responseData"].get("translatedText", text)
            raise ValueError(f"MyMemory error: {res_json}")

    @staticmethod
    def translate_combined_batch(texts: List[str], from_code: str = "en", to_code: str = "zh") -> str:
        """Used by timeline parser: join texts with separator, translate, then split."""
        valid_indices, valid_texts = [], []
        for idx, t in enumerate(texts):
            if t.strip():
                valid_indices.append(idx)
                valid_texts.append(t.strip())
        if not valid_texts:
            return ""

        BATCH_SEP = '\n\n<span class="notranslate">###</span>\n\n'
        combined = BATCH_SEP.join(valid_texts)

        translator = OnlineTranslator()
        result = translator.translate(combined, from_code, to_code)
        if not result.success:
            raise RuntimeError(result.text)
        return result.text
