# -*- coding: utf-8 -*-
import sys
import logging
import traceback
from .paths import get_app_root


def setup_error_handling():
    base_path = get_app_root()
    log_file = base_path / "error_record.log"

    class SeverityFormatter(logging.Formatter):
        def format(self, record):
            if record.levelno >= logging.CRITICAL:
                record.severity_prefix = "[!!! FATAL !!!]"
            elif record.levelno >= logging.ERROR:
                record.severity_prefix = "[!! ERROR !!]"
            elif record.levelno >= logging.WARNING:
                record.severity_prefix = "[! WARNING !]"
            else:
                record.severity_prefix = "[INFO]"
            return super().format(record)

    formatter = SeverityFormatter(
        "%(asctime)s %(severity_prefix)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    def global_exception_handler(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Unhandled exception:\n%s", msg.rstrip())
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = global_exception_handler

    _install_qt_message_handler()


def _install_qt_message_handler():
    try:
        from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

        _dedup = {"last_msg": "", "last_time": 0.0}
        import time as _time

        def qt_message_handler(msg_type, context, message):
            ctx_info = ""
            if context.file:
                ctx_info = f" [{context.file.name.split('/')[-1] if '/' in str(context.file) else str(context.file)}:{context.line}]"

            is_ffmpeg = "ffmpeg" in str(context.file).lower() if context.file else False

            if is_ffmpeg and msg_type in (QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg):
                return

            if is_ffmpeg and msg_type == QtMsgType.QtWarningMsg:
                now = _time.time()
                if message == _dedup["last_msg"] and now - _dedup["last_time"] < 2.0:
                    return
                _dedup["last_msg"] = message
                _dedup["last_time"] = now

            full_msg = f"Qt{ctx_info}: {message}"

            if msg_type == QtMsgType.QtFatalMsg:
                logging.critical(full_msg)
            elif msg_type == QtMsgType.QtCriticalMsg:
                logging.error(full_msg)
            elif msg_type == QtMsgType.QtWarningMsg:
                logging.warning(full_msg)
            elif msg_type == QtMsgType.QtInfoMsg:
                logging.info(full_msg)
            else:
                logging.debug(full_msg)

        qInstallMessageHandler(qt_message_handler)
    except ImportError:
        pass


def log_error(message: str, exc: Exception = None):
    if exc:
        logging.error("%s: %s", message, exc, exc_info=True)
    else:
        logging.error(message)


def log_warning(message: str):
    logging.warning(message)


def log_info(message: str):
    logging.info(message)
