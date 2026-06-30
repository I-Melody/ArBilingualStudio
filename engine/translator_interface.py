# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TranslationResult:
    text: str
    engine_label: str = ""
    success: bool = True
    error: Optional[str] = None


class ITranslator(ABC):
    @abstractmethod
    def translate(self, text: str, from_code: str = "en", to_code: str = "zh") -> TranslationResult:
        ...

    @abstractmethod
    def batch_translate(self, texts: List[str], from_code: str = "en", to_code: str = "zh") -> List[TranslationResult]:
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        ...


def is_translation_error(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        if any(indicator in stripped for indicator in ["Error", "Exception", "未配置", "失败", "故障", "未就绪"]):
            return True
    return False
