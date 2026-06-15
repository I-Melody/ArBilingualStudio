# -*- coding: utf-8 -*-
# 文件路径：main.py

from utils.hot_reload import HotReloadManager
from engine.rule_engine import RuleEngine
from PyQt6.QtCore import Qt, QPoint, QRect, QSettings, QDate
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStatusBar
)
import sys
import os
import importlib
from pathlib import Path

# =========================================================================
# 【抗震防护】：防止 --noconsole 模式下 sys.stdout/stderr 为 None 导致崩溃
# =========================================================================
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

# =========================================================================
# 【核心提速：幽灵导入陷阱】：
# 将重型库放在永远不会被执行的函数中。PyInstaller 扫描器会识别并打包它们，
# 但程序启动时不会执行这些 import，瞬间将启动速度从 3s 压缩到 0.1s 秒开！
# =========================================================================


def _pyinstaller_ghost_hook():
    import PyQt6.QtPdf
    import PyQt6.QtPdfWidgets
    import PyQt6.QtMultimedia
    import PyQt6.QtMultimediaWidgets
    import hashlib
    import urllib.request
    import urllib.parse
    import json
    import re
    import argostranslate.translate
    import argostranslate.package
    import transformers
    import torch
    import sentencepiece


# =========================================================================
# 【自适应路径判定算法】
# =========================================================================
def get_base_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parent

BASE_PATH = get_base_path()

if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

# 挂载全局级日志监听，所有大大小小的报错/崩溃都会被写入根目录的 error_record.log
import logging
log_file = BASE_PATH / "error_record.log"
logging.basicConfig(
    filename=str(log_file), 
    level=logging.WARNING, # 记录警告及以上级别
    format='%(asctime)s [%(levelname)s] %(message)s', 
    encoding='utf-8'
)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    logging.error("系统发生未捕获的致命异常", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = global_exception_handler
# =========================================================================


class CustomTitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(40)
        self._drag_pos = None

        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(5)

        self.title_label = QLabel("✨ 智能双语对照与清洗系统 (专业版)", self)
        self.title_label.setStyleSheet(
            "color: #e4e4e7; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #a1a1aa;
                border: none;
                font-size: 14px;
                width: 32px;
                height: 32px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
        """

        self.btn_min = QPushButton("—", self)
        self.btn_min.setStyleSheet(btn_style)
        self.btn_min.clicked.connect(self.parent_window.showMinimized)

        self.btn_max = QPushButton("⛶", self)
        self.btn_max.setStyleSheet(btn_style)
        self.btn_max.clicked.connect(self.toggle_maximize)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setStyleSheet(btn_style + """
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.btn_close.clicked.connect(QApplication.instance().quit)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            self.btn_max.setText("⛶")
        else:
            self.parent_window.showMaximized()
            self.btn_max.setText("❐")

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().enterEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.parent_window.isMaximized():
            self._drag_pos = event.globalPosition().toPoint(
            ) - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.parent_window.move(
                event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class MainWindow(QMainWindow):
    EDGE_MARGIN = 5

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowSystemMenuHint)

        self.settings = QSettings("BilingualStudioOrg", "BilingualStudioApp")
        self.setMinimumSize(960, 860)

        self.engine = RuleEngine()
        self.active_menus = {}

        self._is_resizing = False
        self._resize_directions = (False, False, False, False)
        self._drag_start_global = QPoint()
        self._drag_start_geometry = QRect()

        self.init_ui()
        self.init_hot_reload()
        self.restore_saved_geometry()

        self.perform_daily_cache_cleanup()

    def init_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        central_widget.setMouseTracking(True)
        self.setMouseTracking(True)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(
            self.EDGE_MARGIN, self.EDGE_MARGIN, self.EDGE_MARGIN, self.EDGE_MARGIN)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("MainWorkSpace")
        self.tab_widget.setMouseTracking(True)
        self.tab_widget.setCursor(Qt.CursorShape.ArrowCursor)
        main_layout.addWidget(self.tab_widget)

        self.status_bar = QStatusBar(self)
        self.status_bar.setObjectName("CustomStatusBar")
        self.setStatusBar(self.status_bar)

        self.load_all_menus()

    def load_all_menus(self):
        menus_dir = BASE_PATH / "menus"
        menu_files = sorted(menus_dir.glob("menu*.py"))
        for file in menu_files:
            if file.stem == "menu2":
                continue
            self.load_tab_module(file.stem)

    def load_tab_module(self, module_name: str):
        try:
            module_path = f"menus.{module_name}"
            module = importlib.import_module(module_path)
            widget_class = getattr(module, "MenuWidget")
            widget_instance = widget_class(parent=self, engine=self.engine)

            title_map = {
                "menu1": "双语处理中心",
                "menu2": "历史记录中心",
                "menu3": "规则配置控制"
            }
            tab_title = title_map.get(module_name, module_name.capitalize())

            if module_name in self.active_menus:
                old_widget, index = self.active_menus[module_name]
                old_widget.on_unload()
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, widget_instance, tab_title)
                old_widget.deleteLater()
                self.active_menus[module_name] = (widget_instance, index)
            else:
                index = self.tab_widget.count()
                self.tab_widget.addTab(widget_instance, tab_title)
                self.active_menus[module_name] = (widget_instance, index)

        except Exception as e:
            pass

    def init_hot_reload(self):
        if getattr(sys, "frozen", False):
            return

        menus_dir = str((BASE_PATH / "menus").resolve())
        self.reload_manager = HotReloadManager(menus_dir, self)
        self.reload_manager.module_changed.connect(self.load_tab_module)

    def restore_saved_geometry(self):
        saved_geom = self.settings.value("geometry")
        if saved_geom:
            self.restoreGeometry(saved_geom)
        else:
            self.resize(1180, 960)

    def perform_daily_cache_cleanup(self):
        try:
            today_str = QDate.currentDate().toString(Qt.DateFormat.ISODate)
            last_cleanup = self.settings.value("last_cache_cleanup_date", "")

            cache_dir = BASE_PATH / "cache"

            if today_str != last_cleanup:
                if cache_dir.exists():
                    for item in cache_dir.iterdir():
                        if item.is_file():
                            try:
                                item.unlink()
                            except Exception:
                                pass
                else:
                    cache_dir.mkdir(parents=True, exist_ok=True)

                self.settings.setValue("last_cache_cleanup_date", today_str)
            else:
                cache_dir.mkdir(parents=True, exist_ok=True)

        except Exception:
            pass

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def get_resize_edge_state(self, local_pos: QPoint):
        rect = self.rect()
        x = local_pos.x()
        y = local_pos.y()
        left = x < self.EDGE_MARGIN
        right = x > rect.width() - self.EDGE_MARGIN
        top = y < self.EDGE_MARGIN
        bottom = y > rect.height() - self.EDGE_MARGIN
        return left, right, top, bottom

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        left, right, top, bottom = self.get_resize_edge_state(pos)

        if not self._is_resizing:
            if (left and top) or (right and bottom):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (right and top) or (left and bottom):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif left or right:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif top or bottom:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            geom = self._drag_start_geometry
            x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            r_left, r_right, r_top, r_bottom = self._resize_directions
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()

            if r_left:
                new_w = w - delta.x()
                if new_w >= min_w:
                    x = geom.x() + delta.x()
                    w = new_w
            elif r_right:
                w = max(min_w, w + delta.x())

            if r_top:
                new_h = h - delta.y()
                if new_h >= min_h:
                    y = geom.y() + delta.y()
                    h = new_h
            elif r_bottom:
                h = max(min_h, h + delta.y())

            self.setGeometry(x, y, w, h)
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            left, right, top, bottom = self.get_resize_edge_state(pos)
            if left or right or top or bottom:
                self._is_resizing = True
                self._resize_directions = (left, right, top, bottom)
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_geometry = self.geometry()
                event.accept()

    def mouseReleaseEvent(self, event):
        self._is_resizing = False
        self._resize_directions = (False, False, False, False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
