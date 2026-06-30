# -*- coding: utf-8 -*-
"""Unified application configuration via QSettings.

All settings read/write goes through this module to avoid scattered
QSettings("BilingualStudioOrg", "BilingualStudioApp") calls across the codebase.
"""
import logging
from PyQt6.QtCore import QSettings

_ORG = "BilingualStudioOrg"
_APP = "BilingualStudioApp"

_settings = QSettings(_ORG, _APP)


def _log_read(key: str, value: str):
    logging.debug(f"[Config] Read {key} = {value!r}")


def _log_write(key: str, value):
    logging.debug(f"[Config] Write {key} = {value!r}")


def to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


# ----- Ollama -----
def get_ollama_model() -> str:
    val = _settings.value("ollama_model", "")
    return str(val) if val else ""

def set_ollama_model(model: str):
    _settings.setValue("ollama_model", model)
    _log_write("ollama_model", model)

def get_ollama_temp() -> float:
    try:
        return float(_settings.value("ollama_temp", "0.1"))
    except (ValueError, TypeError):
        return 0.1

def set_ollama_temp(temp: float):
    _settings.setValue("ollama_temp", str(temp))
    _log_write("ollama_temp", temp)

# ----- Window Geometry -----
def get_geometry():
    return _settings.value("geometry")

def set_geometry(geom):
    _settings.setValue("geometry", geom)

def get_maximized() -> bool:
    val = _settings.value("maximized", False)
    return to_bool(val, False)

def set_maximized(maximized: bool):
    _settings.setValue("maximized", maximized)

# ----- PDF -----
def get_pdf_current_page() -> int:
    try:
        return int(_settings.value("rule_pdf_current_page", 0))
    except (ValueError, TypeError):
        return 0

def set_pdf_current_page(page: int):
    _settings.setValue("rule_pdf_current_page", page)

# ----- Cache -----
def get_last_cache_cleanup_date() -> str:
    return str(_settings.value("last_cache_cleanup_date", ""))

def set_last_cache_cleanup_date(date_str: str):
    _settings.setValue("last_cache_cleanup_date", date_str)

# ----- Raw access (for backward compat) -----
def raw() -> QSettings:
    return _settings
