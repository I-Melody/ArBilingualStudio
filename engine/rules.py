# -*- coding: utf-8 -*-
import re
import json
import logging
from .rule_engine import BaseRule, RuleContext
from .translator import OfflineTranslator, is_translation_error
from .online_api import translate_google, translate_mymemory


def _offline_engine_label(engine_name):
    if engine_name == "ollama":
        return "Ollama (本地大模型)"
    elif engine_name == "argos":
        return "Argos NMT (本地轻量级)"
    elif engine_name == "transformers":
        return "MarianMT (本地小模型)"
    return str(engine_name) if engine_name else "未知离线引擎"


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
        if context.metadata.get("is_timeline", False):
            return context
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

            BATCH_SEP = '\n\n<span class="notranslate">###</span>\n\n'
            SPLIT_PATTERN = r'<span class="notranslate">###</span>'

            def try_online_batch():
                valid_indices, valid_texts = [], []
                for idx, t in enumerate(raw_texts_to_translate):
                    if t.strip():
                        valid_indices.append(idx)
                        valid_texts.append(t.strip())
                if not valid_texts:
                    return [""] * len(raw_texts_to_translate), None

                combined_text = BATCH_SEP.join(valid_texts)
                try:
                    translated_combined = translate_google(combined_text, "en", "zh")
                    if "接口错误" in translated_combined or "429" in translated_combined:
                        raise Exception("Google returned error")
                    context.metadata["engine_used"] = "Google 在线翻译"
                except Exception:
                    try:
                        translated_combined = translate_mymemory(combined_text, "en", "zh")
                        if "接口错误" in translated_combined or "429" in translated_combined:
                            return None, translated_combined
                        context.metadata["engine_used"] = "MyMemory 在线翻译"
                    except Exception as e:
                        return None, str(e)

                try:
                    clean_translated_lines = [line.strip() for line in re.split(SPLIT_PATTERN, translated_combined, flags=re.IGNORECASE)]

                    if len(clean_translated_lines) != len(valid_texts):
                        return None, f"在线合并翻译长度断层 (期望 {len(valid_texts)} 但返回 {len(clean_translated_lines)})"

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
                    engine_t = force_model if force_model else self.offline_translator.engine_type
                    if engine_t == "ollama" or (engine_t is None and self.offline_translator.use_ollama):
                        res_list = self.offline_translator.translate(raw_texts_to_translate, "en", "zh", force_engine=force_model)
                        if isinstance(res_list, list) and any(is_translation_error(t) for t in res_list):
                            return None, "Ollama离线异常"
                        context.metadata["engine_used"] = _offline_engine_label("ollama")
                        return res_list, None
                    else:
                        context.metadata["engine_used"] = _offline_engine_label(engine_t)
                        valid_indices, valid_texts = [], []
                        for idx, t in enumerate(raw_texts_to_translate):
                            if t.strip():
                                valid_indices.append(idx)
                                valid_texts.append(t.strip())
                        if not valid_texts:
                            return [""] * len(raw_texts_to_translate), None

                        combined_text = BATCH_SEP.join(valid_texts)
                        res_combined = self.offline_translator.translate(combined_text, "en", "zh", force_engine=force_model)
                        if is_translation_error(res_combined):
                            return None, res_combined

                        clean_translated_lines = [line.strip() for line in re.split(SPLIT_PATTERN, res_combined, flags=re.IGNORECASE)]
                        if len(clean_translated_lines) != len(valid_texts):
                            return None, f"离线合并翻译对齐失效 (期望 {len(valid_texts)} 但返回 {len(clean_translated_lines)})"

                        translated_list = [""] * len(raw_texts_to_translate)
                        for v_idx, decoded_text in zip(valid_indices, clean_translated_lines):
                            translated_list[v_idx] = decoded_text
                        return translated_list, None
                except Exception as e:
                    return None, str(e)

            translated_list = None
            if engine_mode == "online_first":
                translated_list, err = try_online_batch()
                if translated_list is None:
                    logging.warning(f"[Timeline] 在线优先失败，降级本地: {err}")
                    translated_list, err2 = try_offline_batch()
                    if translated_list is None:
                        translated_list = [f"在线失败:{err} | 本地失败:{err2}"] * len(raw_texts_to_translate)
            elif engine_mode == "local_first":
                translated_list, err = try_offline_batch()
                if translated_list is None:
                    logging.warning(f"[Timeline] 本地优先失败，降级在线: {err}")
                    translated_list, err2 = try_online_batch()
                    if translated_list is None:
                        translated_list = [f"本地失败:{err} | 在线失败:{err2}"] * len(raw_texts_to_translate)
            else:
                translated_list, err = try_offline_batch(force_model=engine_mode)
                if translated_list is None:
                    translated_list = [f"[指定模型载入失败]: {err}"] * len(raw_texts_to_translate)

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
                res = translate_google(raw_text, from_lang, to_lang)
                context.metadata["engine_used"] = "Google 在线翻译"
                return res, None
            except Exception:
                pass
            try:
                res = translate_mymemory(raw_text, from_lang, to_lang)
                context.metadata["engine_used"] = "MyMemory 在线翻译"
                return res, None
            except Exception as e:
                return None, str(e)

        def try_offline(force_model=None):
            if self.offline_translator is None:
                self.offline_translator = OfflineTranslator()
            try:
                engine_name = force_model or self.offline_translator.engine_type
                paragraphs = [p.strip() for p in raw_text.split('\n') if p.strip()]
                if not paragraphs:
                    return "", None
                res_list = self.offline_translator.translate(paragraphs, from_code=from_lang[:2], to_code=to_lang[:2], force_engine=force_model)
                if isinstance(res_list, list) and any(is_translation_error(t) for t in res_list):
                    err_item = next((t for t in res_list if is_translation_error(t)), "未知离线异常")
                    return None, err_item
                context.metadata["engine_used"] = _offline_engine_label(engine_name)
                return "\n".join(res_list) if isinstance(res_list, list) else str(res_list), None
            except Exception as e:
                return None, str(e)

        final_text = ""
        if engine_mode == "online_first":
            final_text, err = try_online()
            if final_text is None:
                logging.warning(f"[Upper] 在线优先失败，降级离线: {err}")
                final_text, err2 = try_offline()
                if final_text is None:
                    final_text = f"[双重降级失败]\n在线报错: {err}\n离线报错: {err2}"
        elif engine_mode == "local_first":
            final_text, err = try_offline()
            if final_text is None:
                logging.warning(f"[Upper] 本地优先失败，降级在线: {err}")
                final_text, err2 = try_online()
                if final_text is None:
                    final_text = f"[双重降级失败]\n离线报错: {err}\n在线报错: {err2}"
        else:
            final_text, err = try_offline(force_model=engine_mode)
            if final_text is None:
                final_text = f"[指定物理模型调度失败]: {err}"

        context.raw_target = re.sub(r'\n{2,}', '\n', final_text).strip()
        return context
