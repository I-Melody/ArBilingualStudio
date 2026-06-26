# -*- coding: utf-8 -*-
import re
import sys
import json
import threading
import urllib.request
from pathlib import Path
from PyQt6.QtCore import QSettings
from core.paths import get_app_root


def is_translation_error(t: str) -> bool:
    t_strip = t.strip()
    if t_strip.startswith("[") and t_strip.endswith("]"):
        if any(indicator in t_strip for indicator in ["Error", "Exception", "未配置", "失败", "故障", "未就绪"]):
            return True
    return False


def make_local_request(url, data_dict=None, timeout=10):
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    req = urllib.request.Request(url)
    if data_dict:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data_dict).encode("utf-8")
        req.method = "POST"
    with opener.open(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


class OfflineTranslator:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        import logging
        for noisy_logger in ["argostranslate", "stanza", "transformers", "urllib3"]:
            logging.getLogger(noisy_logger).setLevel(logging.ERROR)

        self.engine_type = None
        self.model = None
        self.tokenizer = None
        self.use_ollama = False
        self.ollama_model = "translategemma:4b"

        self.root_path = get_app_root()
        self.models_dir = self.root_path / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 1. 探测本地 Ollama 大模型服务
        try:
            res_data = make_local_request("http://localhost:11434/api/tags", timeout=1.0)
            data = json.loads(res_data)
            models = data.get("models", [])
            if models:
                self.ollama_model = models[0].get("name", "translategemma:4b")
            self.use_ollama = True
            self.engine_type = "ollama"
        except Exception:
            pass

        # 2. 传统物理模型扫描
        if not self.use_ollama:
            has_local_transformers = (self.models_dir / "opus-mt-en-zh").exists()
            has_local_argos = len(list(self.models_dir.glob("translate-en_zh-*.argosmodel"))) > 0

            if has_local_transformers:
                try:
                    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                    self.engine_type = "transformers"
                    print("[Offline Engine] [Info] Physical detection: Found local Transformers directory.")
                except ImportError:
                    pass
            elif has_local_argos:
                try:
                    import argostranslate.translate
                    import argostranslate.package
                    self.engine_type = "argos"
                    self._ensure_argos_en_zh_package()
                except ImportError:
                    pass

        # 3. 备用容错自适应探测
        if self.engine_type is None:
            try:
                import argostranslate.translate
                import argostranslate.package
                self.engine_type = "argos"
                print("[Offline Engine] [Info] Default detection: Using Argos Translate from environment...")
                self._ensure_argos_en_zh_package()
            except ImportError:
                try:
                    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                    self.engine_type = "transformers"
                    print("[Offline Engine] [Info] Default detection: Using Transformers from environment...")
                except ImportError:
                    pass

        self._initialized = True

    def _ensure_argos_en_zh_package(self):
        try:
            import argostranslate.translate
            import argostranslate.package
            installed_langs = argostranslate.translate.get_installed_languages()
            installed_codes = [lang.code for lang in installed_langs]
            if "en" in installed_codes and "zh" in installed_codes:
                return

            local_model_file = next(self.models_dir.glob("translate-en_zh-*.argosmodel"), None)
            if local_model_file and local_model_file.exists():
                argostranslate.package.install_from_path(str(local_model_file.resolve()))
                return

            try:
                argostranslate.package.update_package_index()
                available_packages = argostranslate.package.get_available_packages()
                en_zh_pack = next(filter(lambda x: x.from_code == "en" and x.to_code == "zh", available_packages), None)
                if en_zh_pack:
                    downloaded_file = en_zh_pack.download()
                    argostranslate.package.install_from_path(downloaded_file)
            except Exception:
                pass
        except Exception:
            pass

    def translate(self, text, from_code: str = "en", to_code: str = "zh", force_engine: str = None):
        settings = QSettings("BilingualStudioOrg", "BilingualStudioApp")
        saved_model = settings.value("ollama_model", "")
        if saved_model and "未检测到" not in saved_model:
            self.ollama_model = saved_model

        try:
            self.ollama_temp = float(settings.value("ollama_temp", "0.1"))
        except Exception:
            self.ollama_temp = 0.1

        is_list = isinstance(text, list)
        original_texts = text if is_list else [text]

        valid_indices = []
        valid_texts = []
        for i, t in enumerate(original_texts):
            if t.strip():
                valid_indices.append(i)
                valid_texts.append(t.strip())

        if not valid_texts:
            return [""] * len(original_texts) if is_list else ""

        results = [""] * len(original_texts)
        active_engine = force_engine if force_engine else self.engine_type

        # 模式 A：本地运行的 Ollama (GGUF) 大语言模型翻译
        if active_engine == "ollama" or (active_engine is None and self.use_ollama):
            try:
                if is_list and len(valid_texts) > 1:
                    try:
                        batch_results = self._translate_batch_via_ollama(valid_texts, from_code, to_code)
                        for idx, trans_t in zip(valid_indices, batch_results):
                            results[idx] = trans_t
                        return results
                    except Exception as e_batch:
                        print(f"[Ollama Batch Error] Fallback to line-by-line: {e_batch}")

                for idx, t in zip(valid_indices, valid_texts):
                    results[idx] = self._translate_via_ollama(t, from_code, to_code)
                return results if is_list else results[0]
            except Exception as e_ollama:
                print(f"[Ollama Error] Fallback to local NMT: {e_ollama}")
                self.use_ollama = False
                active_engine = self.engine_type

        # 模式 B：Argos 离线翻译
        if active_engine == "argos":
            try:
                import argostranslate.translate
                for i, t in zip(valid_indices, valid_texts):
                    results[i] = argostranslate.translate.translate(t, from_code, to_code)
                return results if is_list else results[0]
            except Exception as e:
                err_msg = f"[Argos Error: {e}]"
                return [err_msg] * len(original_texts) if is_list else err_msg

        # 模式 C：Transformers 离线翻译
        elif active_engine == "transformers":
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                if self.model is None or self.tokenizer is None:
                    local_model_dir = self.models_dir / f"opus-mt-{from_code}-{to_code}"
                    if local_model_dir.exists() and local_model_dir.is_dir():
                        path_str = str(local_model_dir.resolve())
                        if sys.platform == "win32" and any(ord(c) > 127 for c in path_str):
                            raise RuntimeError("Windows 路径包含中文字符。")
                        self.tokenizer = AutoTokenizer.from_pretrained(path_str)
                        self.model = AutoModelForSeq2SeqLM.from_pretrained(path_str)
                    else:
                        model_id = f"Helsinki-NLP/opus-mt-{from_code}-{to_code}"
                        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
                        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id)

                inputs = self.tokenizer(valid_texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
                translated = self.model.generate(**inputs, max_new_tokens=512)
                decoded = self.tokenizer.batch_decode(translated, skip_special_tokens=True)
                for idx, decoded_text in zip(valid_indices, decoded):
                    results[idx] = decoded_text
                return results if is_list else results[0]
            except Exception as e:
                err_msg = f"[Transformers Error: {e}]"
                return [err_msg] * len(original_texts) if is_list else err_msg

        err_msg = "[离线引擎未配置]"
        return [err_msg] * len(original_texts) if is_list else err_msg

    def _translate_via_ollama(self, text: str, from_code: str, to_code: str) -> str:
        url = "http://localhost:11434/api/generate"
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
        data = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": getattr(self, "ollama_temp", 0.1)
            }
        }
        try:
            res_data = make_local_request(url, data_dict=data, timeout=12)
            res = json.loads(res_data)
            return res.get("response", "").strip()
        except Exception as e:
            raise e

    def _translate_batch_via_ollama(self, texts: list[str], from_code: str, to_code: str) -> list[str]:
        url = "http://localhost:11434/api/generate"
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
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": getattr(self, "ollama_temp", 0.1)
            }
        }

        try:
            res_data = make_local_request(url, data_dict=data, timeout=25)
            res = json.loads(res_data)
            response_text = res.get("response", "").strip()

            clean_text = response_text
            if clean_text.startswith("```"):
                clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
                clean_text = re.sub(r'\s*```$', '', clean_text)
            clean_text = clean_text.strip()

            translated_dict = json.loads(clean_text)
            if not isinstance(translated_dict, dict):
                raise ValueError("Ollama 未能成功生成 JSON 键值对对象")

            results = []
            for i, original_text in enumerate(texts):
                key = f"k_{i}"
                if key in translated_dict and str(translated_dict[key]).strip():
                    results.append(str(translated_dict[key]).strip())
                else:
                    print(f"[Ollama 批量自愈] 检测到模型遗漏了 Key: {key}，正在执行单句高容错补全...")
                    fallback_val = self._translate_via_ollama(original_text, from_code, to_code)
                    results.append(fallback_val)

            return results
        except Exception as e:
            raise e
