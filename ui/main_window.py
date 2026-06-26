# -*- coding: utf-8 -*-
import sys
import importlib
from PyQt6.QtCore import Qt, QPoint, QRect, QSettings, QDate
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QStatusBar
)
from core.paths import get_app_root
from core.clipboard_monitor import ClipboardMonitor
from engine.rule_engine import RuleEngine
from .title_bar import CustomTitleBar


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
        self.clipboard_monitor = ClipboardMonitor(parent=self)

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
        menus_dir = get_app_root() / "menus"
        menu_files = sorted(menus_dir.glob("menu*.py"))
        for file in menu_files:
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

        from utils.hot_reload import HotReloadManager
        menus_dir = str((get_app_root() / "menus").resolve())
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

            cache_dir = get_app_root() / "cache"

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

    def _get_resize_edges(self, local_pos: QPoint):
        rect = self.rect()
        x = local_pos.x()
        y = local_pos.y()
        edges = Qt.Edge(0)
        if x < self.EDGE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif x > rect.width() - self.EDGE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if y < self.EDGE_MARGIN:
            edges |= Qt.Edge.TopEdge
        elif y > rect.height() - self.EDGE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edges = self._get_resize_edges(pos)
            if edges:
                wh = self.windowHandle()
                if wh is not None:
                    wh.startSystemResize(edges)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        edges = self._get_resize_edges(pos)

        if edges == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge) or edges == (Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges == (Qt.Edge.RightEdge | Qt.Edge.TopEdge) or edges == (Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()
