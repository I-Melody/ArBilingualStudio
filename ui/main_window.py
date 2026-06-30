# -*- coding: utf-8 -*-
import sys
import importlib
from PyQt6.QtCore import Qt, QPoint, QRect, QDate
from core import config as app_config
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QStatusBar, QSizeGrip
)
from core.paths import get_app_root
from core.clipboard_monitor import ClipboardMonitor
from engine.rule_engine import RuleEngine
from engine.translator_service import TranslatorService
from .title_bar import CustomTitleBar


class MainWindow(QMainWindow):
    EDGE_MARGIN = 5

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowSystemMenuHint)

        self.setMinimumSize(960, 860)

        self.engine = RuleEngine()
        self.translator_service = TranslatorService()
        self.active_menus = {}
        self.clipboard_monitor = ClipboardMonitor(parent=self)

        self._maximized = False
        self._resize_edges = 0
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

        size_grip = QSizeGrip(self)
        size_grip.setFixedSize(16, 16)
        size_grip.setStyleSheet(
            "QSizeGrip { background: transparent; }")
        self.status_bar.addPermanentWidget(size_grip)

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
            widget_instance = widget_class(parent=self, engine=self.engine,
                                            translator_service=self.translator_service)

            title_map = {
                "menu1": "双语处理中心",
                "menu2": "双模翻译工作流",
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
        screen = self.screen()
        if screen is None:
            self.resize(1180, 960)
            return

        saved_geom = app_config.get_geometry()
        screen_geom = screen.availableGeometry()
        was_maximized = app_config.get_maximized()

        if was_maximized:
            self.setGeometry(screen_geom)
            self._maximized = True
            self.title_bar._update_max_button_text()
        elif saved_geom:
            self.restoreGeometry(saved_geom)
            self._maximized = False
        else:
            self.resize(1180, 960)
            self._maximized = False

    def perform_daily_cache_cleanup(self):
        try:
            today_str = QDate.currentDate().toString(Qt.DateFormat.ISODate)
            last_cleanup = app_config.get_last_cache_cleanup_date()

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

                app_config.set_last_cache_cleanup_date(today_str)
            else:
                cache_dir.mkdir(parents=True, exist_ok=True)

        except Exception:
            pass

    def closeEvent(self, event):
        app_config.set_geometry(self.saveGeometry())
        app_config.set_maximized(self._maximized)
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
            self._resize_edges = self._get_resize_edges(pos)
            if self._resize_edges:
                if self._maximized:
                    self._maximized = False
                    self.showNormal()
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_geometry = QRect(self.geometry())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_edges:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            g = QRect(self._drag_start_geometry)
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()

            if self._resize_edges & Qt.Edge.LeftEdge:
                new_left = g.left() + delta.x()
                if new_left > g.right() - min_w:
                    new_left = g.right() - min_w
                g.setLeft(new_left)
            if self._resize_edges & Qt.Edge.TopEdge:
                new_top = g.top() + delta.y()
                if new_top > g.bottom() - min_h:
                    new_top = g.bottom() - min_h
                g.setTop(new_top)
            if self._resize_edges & Qt.Edge.RightEdge:
                g.setRight(max(g.right() + delta.x(), g.left() + min_w))
            if self._resize_edges & Qt.Edge.BottomEdge:
                g.setBottom(max(g.bottom() + delta.y(), g.top() + min_h))

            self.setGeometry(g)
        else:
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
        self._resize_edges = 0
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()
