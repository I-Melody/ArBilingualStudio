# -*- coding: utf-8 -*-
import json
import re
from typing import List

from engine.translator_interface import ITranslator, TranslationResult
from engine.translators.base import make_local_request, OLLAMA_BASE
from core.error_handler import log_error, log_warning


class OllamaTranslator(ITranslator):
    HY_MT2_TOKENS = [
        "<｜hy_begin▁of▁sentence｜>", "<｜hy_User｜>", "<｜hy_Assistant｜>",
        "<｜hy_place▁holder▁no▁3｜>", "<｜hy_place▁holder▁no▁2｜>",
        "<suggested_response>", "</suggested_response>",
        "<ｆin｜hy-", "<ｈy-", "<ｺ｜hy-", "<ｂ｜hy-", "<｜",
    ]
    HY_MT2_STOP_TOKENS = [
        "<｜", "<suggested_response", "</suggested_response",
        "<ｆin｜hy-", "<ｈy-", "<ｺ｜hy-", "<ｂ｜hy-",
    ]
    LANG_LABELS = {"en": "English", "zh": "Chinese"}

    def __init__(self, model_name: str = "translategemma:4b", temperature: float = 0.1):
        self._model_name = model_name
        self._temperature = temperature

    @property
    def engine_name(self) -> str:
        return "Ollama (本地大模型)"

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, value: str):
        self._model_name = value

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        self._temperature = value

    @classmethod
    def is_available(cls) -> bool:
        try:
            make_local_request(f"{OLLAMA_BASE}/api/tags", timeout=1.0)
            return True
        except Exception as e:
            log_warning(f"Ollama not available: {e}")
            return False

    @classmethod
    def list_models(cls) -> List[str]:
        try:
            res = make_local_request(f"{OLLAMA_BASE}/api/tags", timeout=1.0)
            data = json.loads(res)
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            log_warning(f"Ollama list_models failed: {e}")
            return []

    def translate(self, text: str, from_code: str = "en", to_code: str = "zh") -> TranslationResult:
        try:
            result_text = self._call_ollama_single(text, from_code, to_code)
            if self._is_hy_mt2():
                result_text = self._clean_hy_mt2_output(result_text)
            return TranslationResult(text=result_text, engine_label=self.engine_name)
        except Exception as e:
            return TranslationResult(text=f"[Ollama Error: {e}]", engine_label=self.engine_name, success=False, error=str(e))

    def batch_translate(self, texts: List[str], from_code: str = "en", to_code: str = "zh") -> List[TranslationResult]:
        if self._is_hy_mt2():
            results = []
            for t in texts:
                results.append(self.translate(t.strip() if t.strip() else t, from_code, to_code))
            return results
        try:
            translated_texts = self._call_ollama_batch(texts, from_code, to_code)
            return [TranslationResult(text=t, engine_label=self.engine_name) for t in translated_texts]
        except Exception as e:
            return [TranslationResult(text=f"[Ollama Batch Error: {e}]", engine_label=self.engine_name, success=False, error=str(e)) for _ in texts]

    def _is_hy_mt2(self) -> bool:
        return "hy-mt" in self._model_name.lower()

    def _clean_hy_mt2_output(self, text: str) -> str:
        for token in self.HY_MT2_TOKENS:
            text = text.replace(token, "")
        return text.strip()

    def _call_ollama_single(self, text: str, from_code: str, to_code: str) -> str:
        if self._is_hy_mt2():
            data = self._build_hy_mt2_payload(text, from_code, to_code)
        else:
            data = self._build_default_payload(text, from_code, to_code)
        res_data = make_local_request(f"{OLLAMA_BASE}/api/generate", data_dict=data, timeout=12)
        return json.loads(res_data).get("response", "").strip()

    def _call_ollama_batch(self, texts: List[str], from_code: str, to_code: str) -> List[str]:
        lang_name = "Chinese" if to_code == "zh" else "English"
        input_dict = {f"k_{i}": t for i, t in enumerate(texts)}
        input_json = json.dumps(input_dict, ensure_ascii=False)

        prompt = (
            f"### Role:\n"
            f"You are a professional video translator translator from {from_code} to {lang_name}.\n\n"
            f"### Strict Translation Rules:\n"
            f"1. KEEP all proper nouns, personal names, and character names in their original English form (e.g., 'Kent', 'Andre' MUST remain unchanged).\n"
            f"2. KEEP all step IDs, serial numbers, and indexes exactly in their original format.\n"
            f"3. Translate the description into extremely natural, native {lang_name}.\n"
            f"4. You are given a JSON object where keys are IDs (e.g. \"k_0\", \"k_1\") and values are English texts.\n"
            f"   You MUST translate each value and return a JSON object with the EXACT same keys.\n"
            f"5. Output ONLY the raw valid JSON object. Do not provide any markdown, explain, quotes, or notes.\n\n"
            f"### Input JSON Object:\n"
            f"{input_json}\n\n"
            f"### Output JSON Object:\n"
        )
        data = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "enable_thinking": False,
            "options": {"temperature": self._temperature},
        }
        res_data = make_local_request(f"{OLLAMA_BASE}/api/generate", data_dict=data, timeout=25)
        response_text = json.loads(res_data).get("response", "").strip()

        clean_text = response_text
        if clean_text.startswith("```"):
            clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
            clean_text = re.sub(r'\s*```$', '', clean_text)
        clean_text = clean_text.strip()

        translated_dict = json.loads(clean_text)
        if not isinstance(translated_dict, dict):
            raise ValueError("Ollama failed to produce JSON object")

        results = []
        for i, original_text in enumerate(texts):
            key = f"k_{i}"
            if key in translated_dict and str(translated_dict[key]).strip():
                results.append(str(translated_dict[key]).strip())
            else:
                fallback = self._call_ollama_single(original_text, from_code, to_code)
                results.append(fallback)
        return results

    def _build_hy_mt2_payload(self, text: str, from_code: str, to_code: str) -> dict:
        src_label = self.LANG_LABELS.get(from_code, from_code)
        tgt_label = self.LANG_LABELS.get(to_code, to_code)
        prompt = f"<｜hy_begin▁of▁sentence｜><｜hy_User｜>Translate from {src_label} to {tgt_label}: {text}<｜hy_Assistant｜>"
        return {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "top_p": 0.6,
                "top_k": 20,
                "repeat_penalty": 1.05,
                "num_predict": 4096,
                "stop": self.HY_MT2_STOP_TOKENS,
            },
        }

    def _build_default_payload(self, text: str, from_code: str, to_code: str) -> dict:
        lang_name = "Chinese" if to_code == "zh" else "English"
        prompt = (
            f"### Role:\n"
            f"You are a professional video translator translator from {from_code} to {lang_name}.\n\n"
            f"### Strict Translation Rules:\n"
            f"1. KEEP all proper nouns, personal names, and character names in their original English form.\n"
            f"2. KEEP all step IDs, serial numbers, and indexes exactly in their original format.\n"
            f"3. Translate the description and context into extremely natural, native {lang_name}.\n"
            f"4. Output ONLY the translated text. Do not provide any explanation, quotes, or notes.\n\n"
            f"### Actual Task Input:\n"
            f"Input: \"{text}\"\n"
            f"Output: "
        )
        return {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "enable_thinking": False,
            "options": {"temperature": self._temperature},
        }
