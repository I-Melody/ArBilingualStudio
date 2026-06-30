# -*- coding: utf-8 -*-
import re
import json
import logging
from typing import Optional

from .rule_engine import BaseRule, RuleContext
from .translator_interface import is_translation_error
from .translator_service import (
    TranslatorService,
    ENGINE_ONLINE_FIRST,
    ENGINE_LOCAL_FIRST,
    ENGINE_OLLAMA,
    ENGINE_MARIANMT,
    ENGINE_ARGOS,
)


def resolve_translator(context: RuleContext) -> TranslatorService:
    svc = context.metadata.get("translator_service")
    if svc is None:
        raise RuntimeError("TranslatorService not found in RuleContext.metadata")
    return svc


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
    """Parses JSON timeline arrays and translates content/bridge fields."""

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

            engine_mode = context.metadata.get("engine", ENGINE_ONLINE_FIRST)
            svc = resolve_translator(context)

            translated_list = svc.translate_batch_with_separator(
                raw_texts_to_translate,
                from_code="en",
                to_code="zh",
                engine_mode=engine_mode,
            )

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
                    "content": content, "content_local_zh": c_zh, "bridge": bridge, "bridge_local_zh": b_zh,
                })

            context.metadata["timeline_processed"] = processed_items
            context.metadata["is_timeline"] = True

        except Exception as e:
            logging.error(f"[Timeline Parsing Error]: {e}")
            context.metadata["is_timeline"] = False

        return context


class ActualTranslationRule(BaseRule):
    """Translates source text using the configured engine with fallback."""

    def execute(self, context: RuleContext) -> RuleContext:
        direction = context.metadata.get("mode", "en_to_zh")
        raw_text = context.raw_source.strip()
        engine_mode = context.metadata.get("engine", ENGINE_ONLINE_FIRST)

        if not raw_text:
            context.raw_target = ""
            return context

        from_lang = "en" if direction == "en_to_zh" else "zh"
        to_lang = "zh" if direction == "en_to_zh" else "en"

        svc = resolve_translator(context)
        result = svc.translate_single(raw_text, from_code=from_lang, to_code=to_lang, engine_mode=engine_mode)

        if result.success:
            context.metadata["engine_used"] = result.engine_label
        context.raw_target = re.sub(r'\n{2,}', '\n', result.text).strip()

        return context
