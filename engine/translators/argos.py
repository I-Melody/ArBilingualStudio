# -*- coding: utf-8 -*-
from typing import List

from engine.translator_interface import ITranslator, TranslationResult
from engine.translators.base import suppress_noisy_loggers
from core.paths import get_app_root
from core.error_handler import log_warning


class ArgosTranslator(ITranslator):
    _package_installed = False

    def __init__(self):
        self._models_dir = get_app_root() / "models"

    @property
    def engine_name(self) -> str:
        return "Argos NMT (本地轻量级)"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import argostranslate.translate
            import argostranslate.package
            return True
        except ImportError:
            return False

    @classmethod
    def has_local_model(cls) -> bool:
        models_dir = get_app_root() / "models"
        return len(list(models_dir.glob("translate-en_zh-*.argosmodel"))) > 0

    def _ensure_package_installed(self):
        if self._package_installed:
            return
        suppress_noisy_loggers()
        import argostranslate.translate
        import argostranslate.package
        installed_langs = argostranslate.translate.get_installed_languages()
        installed_codes = [lang.code for lang in installed_langs]
        if "en" in installed_codes and "zh" in installed_codes:
            self._package_installed = True
            return

        local_model_file = next(self._models_dir.glob("translate-en_zh-*.argosmodel"), None)
        if local_model_file and local_model_file.exists():
            argostranslate.package.install_from_path(str(local_model_file.resolve()))
            self._package_installed = True
            return

        try:
            argostranslate.package.update_package_index()
            available_packages = argostranslate.package.get_available_packages()
            en_zh_pack = next(filter(lambda x: x.from_code == "en" and x.to_code == "zh", available_packages), None)
            if en_zh_pack:
                downloaded_file = en_zh_pack.download()
                argostranslate.package.install_from_path(downloaded_file)
                self._package_installed = True
        except Exception as e:
            log_warning(f"Argos package install failed: {e}")

    def translate(self, text: str, from_code: str = "en", to_code: str = "zh") -> TranslationResult:
        try:
            self._ensure_package_installed()
            import argostranslate.translate
            result = argostranslate.translate.translate(text, from_code, to_code)
            return TranslationResult(text=result, engine_label=self.engine_name)
        except Exception as e:
            return TranslationResult(text=f"[Argos Error: {e}]", engine_label=self.engine_name, success=False, error=str(e))

    def batch_translate(self, texts: List[str], from_code: str = "en", to_code: str = "zh") -> List[TranslationResult]:
        return [self.translate(t, from_code, to_code) for t in texts]
