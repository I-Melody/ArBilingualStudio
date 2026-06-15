# -*- coding: utf-8 -*-
# 文件路径：engine/rules.py

import re
import sys
import os
import urllib.request
import urllib.parse
import json
import threading  
from pathlib import Path
from .rule_engine import BaseRule, RuleContext


def get_root_path():
    """
    自适应获取物理根目录。
    * 兼容开发环境与 PyInstaller 打包环境。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parents[1]


class OfflineTranslator:
    """
    本地离线神经网络翻译引擎。
    【2026 终极体验优化】：
    1. 动态侦测本地 Ollama 大语言模型服务 (默认 Qwen2.5:3b/1.5b)，实现人类级别的离线大模型意译。
    2. 兼容 Argos 本地模型自适应加载与降级。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        双重校验锁机制实现高效单例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return  
            
        # =========================================================================
        # 【新增】：暴力静默第三方 NLP 库的冗杂日志，防止它们污染全局 error_record.log
        # =========================================================================
        import logging
        for noisy_logger in ["argostranslate", "stanza", "transformers", "urllib3"]:
            logging.getLogger(noisy_logger).setLevel(logging.ERROR)
        # =========================================================================

        self.engine_type = None
        self.model = None
        self.tokenizer = None
        self.use_ollama = False  
        
        self.root_path = get_root_path()
        self.models_dir = self.root_path / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 1. 探测本地 Ollama 大模型服务
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as response:
                if response.status == 200:
                    self.use_ollama = True
                    self.engine_type = "ollama"
                    print("[Offline Engine] [Info] Detected active local Ollama service. Upgrading to LLM offline translation!")
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
        """
        核心翻译接口。修复了 force_engine 参数缺失的问题，完美支持动态强制路由。
        """
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

        # 判断最终使用的引擎：如果有强制指定，则使用指定的；否则使用自动探测到的
        active_engine = force_engine if force_engine else self.engine_type

        # 模式 A：本地运行的 Ollama (GGUF) 大语言模型翻译
        if active_engine == "ollama" or (active_engine is None and self.use_ollama):
            try:
                for idx, t in zip(valid_indices, valid_texts):
                    results[idx] = self._translate_via_ollama(t, from_code, to_code)
                return results if is_list else results[0]
            except Exception as e_ollama:
                print(f"[Ollama Error] Fallback to local translation: {e_ollama}")
                self.use_ollama = False
                active_engine = self.engine_type # Ollama崩溃则退避回传统模型

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
                            raise RuntimeError("Windows 环境下 SentencePiece 库无法读取带中文字符的路径。")
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
            f"1. KEEP all proper nouns, personal names, and character names in their original English form. (e.g. 'Bruce', 'Nemo', 'Willem Dafoe' MUST remain unchanged as 'Bruce', 'Nemo', 'Willem Dafoe').\n"
            f"2. KEEP all step IDs, serial numbers, and indexes exactly in their original format. (e.g. 'step_1', 'event_02', 'A.', '1.' must not be altered).\n"
            f"3. Translate the description and context into extremely natural, native {lang_name}.\n"
            f"4. Output ONLY the translated text. Do not provide any explanation, quotes, or notes.\n\n"
            f"### Few-Shot Demonstration:\n"
            f"Input: \"F.Bruce picks up the pleated strip after event_02.\"\n"
            f"Output: \"F.Bruce 在 event_02 之后拾起了褶边条。\"\n\n"
            f"### Actual Task Input:\n"
            f"Input: \"{text}\"\n"
            f"Output: "
        )
        
        data = {
            "model": "qwen2.5:3b", 
            "prompt": prompt,
            "stream": False
        }
        encoded_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=encoded_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("response", "").strip()


import logging

class TextCleanupRule(BaseRule):
    def execute(self, context: RuleContext) -> RuleContext:
        src = context.raw_source
        src = re.sub(r'\r\n', '\n', src)
        src = re.sub(r'\n{3,}', '\n\n', src)
        context.processed_source_segments = [line.strip() for line in src.split('\n') if line.strip()]

        tgt = context.raw_target
        if tgt:
            tgt = re.sub(r'\r\n', '\n', tgt)
            tgt = re.sub(r'\n{3,}', '\n\n', tgt)
            context.processed_target_segments = [line.strip() for line in tgt.split('\n') if line.strip()]
            
        return context


class SimpleAlignmentRule(BaseRule):
    def execute(self, context: RuleContext) -> RuleContext:
        if context.metadata.get("is_timeline", False): return context
        src_lines = context.processed_source_segments
        tgt_lines = context.processed_target_segments
        aligned = []
        max_len = max(len(src_lines), len(tgt_lines))
        for i in range(max_len):
            src_val = src_lines[i] if i < len(src_lines) else ""
            tgt_val = tgt_lines[i] if i < len(tgt_lines) else ""
            aligned.append((src_val, tgt_val))
        context.aligned_pairs = aligned
        return context


class VideoTimelineParseRule(BaseRule):
    def __init__(self):
        super().__init__()
        self.offline_translator = None

    def execute(self, context: RuleContext) -> RuleContext:
        text = context.raw_source.strip()
        if not (text.startswith("[") and text.endswith("]")):
            context.metadata["is_timeline"] = False
            return context
            
        try:
            data = json.loads(text)
            if not isinstance(data, list) or len(data) == 0:
                context.metadata["is_timeline"] = False
                return context

            raw_texts_to_translate = []
            for item in data:
                raw_texts_to_translate.append(str(item.get("content", "")).strip())
                raw_texts_to_translate.append(str(item.get("bridge", "")).strip())

            engine_mode = context.metadata.get("engine", "online_first")
            
            # 定义两种基础翻译器的包装函数
            def try_online_batch():
                online_engine = ActualTranslationRule()
                valid_indices, valid_texts = [], []
                for idx, t in enumerate(raw_texts_to_translate):
                    if t.strip():
                        valid_indices.append(idx)
                        valid_texts.append(t.strip())
                if not valid_texts: return [""] * len(raw_texts_to_translate), None
                
                prefixed_lines = [f"{i}. {line}" for i, line in enumerate(valid_texts)]
                combined_text = "\n".join(prefixed_lines)
                try:
                    translated_combined = online_engine._translate_with_fallback(combined_text, "en", "zh")
                    if "接口错误" in translated_combined or "429" in translated_combined:
                        return None, translated_combined
                    translated_lines = [line.strip() for line in translated_combined.split("\n")]
                    clean_translated_lines = [re.sub(r'^\d+\s*[\.\、\s]\s*', '', line) for line in translated_lines]
                    if len(clean_translated_lines) != len(valid_texts):
                        return None, "在线合并翻译对齐数目不一致"
                    translated_list = [""] * len(raw_texts_to_translate)
                    for v_idx, decoded_text in zip(valid_indices, clean_translated_lines):
                        translated_list[v_idx] = decoded_text
                    return translated_list, None
                except Exception as e:
                    return None, str(e)

            def try_offline_batch(force_model=None):
                if self.offline_translator is None:
                    self.offline_translator = OfflineTranslator()
                try:
                    res_list = self.offline_translator.translate(raw_texts_to_translate, "en", "zh", force_engine=force_model)
                    if isinstance(res_list, list) and any("未就绪" in t or "待装载" in t or "异常" in t for t in res_list):
                        return None, res_list[0]
                    return res_list, None
                except Exception as e:
                    return None, str(e)

            # 【严格执行在线优先/本地优先路由与自动降级】
            translated_list = None
            if engine_mode == "online_first":
                translated_list, err = try_online_batch()
                if translated_list is None:
                    logging.warning(f"[Timeline] 在线优先失败，降级本地: {err}")
                    translated_list, err2 = try_offline_batch()
                    if translated_list is None: translated_list = [f"在线失败:{err} | 本地失败:{err2}"] * len(raw_texts_to_translate)
            elif engine_mode == "local_first":
                translated_list, err = try_offline_batch()
                if translated_list is None:
                    logging.warning(f"[Timeline] 本地优先失败，降级在线: {err}")
                    translated_list, err2 = try_online_batch()
                    if translated_list is None: translated_list = [f"本地失败:{err} | 在线失败:{err2}"] * len(raw_texts_to_translate)
            else:
                translated_list, err = try_offline_batch(force_model=engine_mode)
                if translated_list is None: translated_list = [f"[指定模型载入失败]: {err}"] * len(raw_texts_to_translate)

            processed_items = []
            for idx, item in enumerate(data):
                step_id = str(item.get("step_id", "")).strip()
                segment_id = str(item.get("segment_id", "")).strip()
                modality = str(item.get("modality", "")).strip().upper()
                timestamp = str(item.get("timestamp", "")).strip()
                content = re.sub(r'\s+', ' ', str(item.get("content", "")).strip())
                bridge = re.sub(r'\s+', ' ', str(item.get("bridge", "")).strip())
                
                c_zh = translated_list[idx * 2] if (idx * 2) < len(translated_list) else ""
                b_zh = translated_list[idx * 2 + 1] if (idx * 2 + 1) < len(translated_list) else ""
                
                processed_items.append({
                    "step_id": step_id, "segment_id": segment_id, "modality": modality, "timestamp": timestamp,
                    "content": content, "content_local_zh": c_zh, "bridge": bridge, "bridge_local_zh": b_zh
                })
            context.metadata["timeline_processed"] = processed_items
            context.metadata["is_timeline"] = True
        except Exception as e:
            logging.error(f"[Timeline Parsing Error]: {e}")
            context.metadata["is_timeline"] = False
        return context


class ActualTranslationRule(BaseRule):
    def __init__(self):
        super().__init__()
        self.offline_translator = None

    def execute(self, context: RuleContext) -> RuleContext:
        direction = context.metadata.get("mode", "en_to_zh")
        raw_text = context.raw_source.strip()
        engine_mode = context.metadata.get("engine", "online_first")
        
        if not raw_text:
            context.raw_target = ""
            return context
        
        from_lang = "en" if direction == "en_to_zh" else "zh-CN"
        to_lang = "zh-CN" if direction == "en_to_zh" else "en"

        def try_online():
            try:
                res = self._translate_with_fallback(raw_text, from_lang, to_lang)
                if "翻译接口错误" in res or "429" in res:
                    return None, res
                return res, None
            except Exception as e:
                return None, str(e)

        def try_offline(force_model=None):
            if self.offline_translator is None:
                self.offline_translator = OfflineTranslator()
            try:
                paragraphs = [p.strip() for p in raw_text.split('\n') if p.strip()]
                if not paragraphs: return "", None
                res_list = self.offline_translator.translate(paragraphs, from_code=from_lang[:2], to_code=to_lang[:2], force_engine=force_model)
                if isinstance(res_list, list) and any("未就绪" in t or "待装载" in t or "异常" in t for t in res_list):
                    return None, res_list[0]
                return "\n".join(res_list) if isinstance(res_list, list) else str(res_list), None
            except Exception as e:
                return None, str(e)

        # 【彻底闭环的顶层双向容错路由】
        final_text = ""
        if engine_mode == "online_first":
            final_text, err = try_online()
            if final_text is None:
                logging.warning(f"[Upper] 在线优先失败，降级离线: {err}")
                final_text, err2 = try_offline()
                if final_text is None: final_text = f"[双重降级失败]\n在线报错: {err}\n离线报错: {err2}"
        elif engine_mode == "local_first":
            final_text, err = try_offline()
            if final_text is None:
                logging.warning(f"[Upper] 本地优先失败，降级在线: {err}")
                final_text, err2 = try_online()
                if final_text is None: final_text = f"[双重降级失败]\n离线报错: {err}\n在线报错: {err2}"
        else:
            final_text, err = try_offline(force_model=engine_mode)
            if final_text is None: final_text = f"[指定物理模型调度失败]: {err}"

        context.raw_target = re.sub(r'\n{2,}', '\n', final_text).strip()
        return context

    def _translate_with_fallback(self, text: str, from_lang: str, to_lang: str) -> str:
        try:
            return self._translate_google(text, from_lang, to_lang)
        except Exception: pass
        try:
            return self._translate_mymemory(text, from_lang, to_lang)
        except Exception as e_mymemory:
            return f"[翻译接口错误] 在线链路均无法建立连接。网络超时或被阻断。最后反馈: {e_mymemory}"

    def _translate_mymemory(self, text: str, from_lang: str, to_lang: str) -> str:
        if len(text) <= 500:
            return self._translate_mymemory_single(text, from_lang, to_lang)
        paragraphs = text.split("\n")
        chunks, current_chunk, current_len = [], [], 0
        for p in paragraphs:
            if current_len + len(p) + 1 > 450:
                if current_chunk: chunks.append("\n".join(current_chunk))
                current_chunk, current_len = [p], len(p)
            else:
                current_chunk.append(p)
                current_len += len(p) + 1
        if current_chunk: chunks.append("\n".join(current_chunk))

        translated_chunks = []
        for chunk in chunks:
            if chunk.strip(): translated_chunks.append(self._translate_mymemory_single(chunk, from_lang, to_lang))
            else: translated_chunks.append("")
        return "\n".join(translated_chunks)

    def _translate_mymemory_single(self, text: str, from_lang: str, to_lang: str) -> str:
        f = "en" if from_lang.startswith("en") else "zh"
        t = "zh" if to_lang.startswith("zh") else "en"
        url = "https://api.mymemory.translated.net/get"
        query_string = urllib.parse.urlencode({"q": text, "langpair": f"{f}|{t}"})
        req = urllib.request.Request(f"{url}?{query_string}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            if "responseData" in res_json: return res_json["responseData"].get("translatedText", text)
            raise ValueError(f"MyMemory 异常: {res_json}")

    def _translate_google(self, text: str, from_lang: str, to_lang: str) -> str:
        sl = "en" if from_lang.startswith("en") else "zh-CN"
        tl = "zh-CN" if from_lang.startswith("en") else "en"
        url = "https://translate.googleapis.com/translate_a/single"
        query_string = urllib.parse.urlencode({'client': 'gtx', 'sl': sl, 'tl': tl, 'dt': 't', 'q': text})
        req = urllib.request.Request(f"{url}?{query_string}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            translated_segments = []
            if data and isinstance(data, list) and len(data) > 0:
                for segment in data[0]:
                    if isinstance(segment, list) and len(segment) > 0:
                        translated_segments.append(segment[0])
            return "".join(translated_segments)