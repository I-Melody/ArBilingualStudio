# -*- coding: utf-8 -*-
import sys
import logging
from .paths import get_app_root


def setup_error_handling():
    base_path = get_app_root()
    log_file = base_path / "error_record.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(message)s',
        encoding='utf-8'
    )

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        logging.error("系统发生未捕获的致命异常", exc_info=(
            exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = global_exception_handler
