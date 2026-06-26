# -*- coding: utf-8 -*-
import sys
from pathlib import Path


def get_app_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parents[1]
