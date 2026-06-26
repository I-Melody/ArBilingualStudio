# -*- coding: utf-8 -*-
import time
import json
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QFrame, QListWidget, QWidget, QPushButton
)
from PyQt6.QtCore import Qt

from .base_menu import BaseMenuWidget
from ui.widgets.browser_window import WebBrowserWindow


class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        self.setStyleSheet("""
            QFrame#ConsoleFrame { background-color: #161619; border: 1px solid #27272a; border-radius: 8px; padding: 10px; }
            QPushButton#LaunchBtn { background-color: #2563eb; color: white; font-weight: bold; font-size: 12px; border-radius: 6px; height: 36px; border: none; }
            QPushButton#LaunchBtn:hover { background-color: #1d4ed8; }
            QPushButton#SyncBtn { background-color: #0d9488; color: white; font-weight: bold; font-size: 12px; border-radius: 6px; height: 36px; border: none; }
            QPushButton#SyncBtn:hover { background-color: #0f766e; }
            QPushButton#SyncBtn:disabled { background-color: #121214; color: #52525b; border: 1px solid #27272a; }
            QTextEdit#LogBox { background-color: #121214; color: #10b981; border: 1px solid #27272a; border-radius: 6px; padding: 10px; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }
            QListWidget { background-color: #121214; border: 1px solid #27272a; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #1c1c1f; border-radius: 4px; margin-bottom: 2px; font-size: 11px; color: #e4e4e7; }
            QListWidget::item:selected { background-color: #1e3a8a; color: #60a5fa; font-weight: bold; border-left: 3px solid #3b82f6; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.label = QLabel("🌐 2. 自动化网页浏览器控制台 (v2.0 试验沙盒)", self)
        self.label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.label)

        self.console_frame = QFrame(self)
        self.console_frame.setObjectName("ConsoleFrame")
        console_layout = QVBoxLayout(self.console_frame)
        console_layout.setContentsMargins(8, 8, 8, 8)
        console_layout.setSpacing(8)

        self.btn_launch = QPushButton("🚀 启动自动化辅助浏览器 (Window 2)", self)
        self.btn_launch.setObjectName("LaunchBtn")
        self.btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch.clicked.connect(self.launch_sandbox_browser)
        console_layout.addWidget(self.btn_launch)

        data_dock_layout = QHBoxLayout()
        data_dock_layout.setSpacing(8)

        list_container = QWidget(self)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(QLabel("📦 已截获的动态题包列表", self, styleSheet="color: #a1a1aa; font-size: 11px; font-weight: bold;"))
        self.list_widget = QListWidget(self)
        list_layout.addWidget(self.list_widget)
        data_dock_layout.addWidget(list_container, stretch=4)

        log_container = QWidget(self)
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("📋 抓包通信实时监控 (Real-time Packet Monitor)", self,
                             styleSheet="color: #a1a1aa; font-size: 11px; font-weight: bold;"))
        self.log_box = QTextEdit(self)
        self.log_box.setObjectName("LogBox")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("等待副窗口 (Window 2) 拦截并回传结构化数据流...")
        log_layout.addWidget(self.log_box)
        data_dock_layout.addWidget(log_container, stretch=6)

        console_layout.addLayout(data_dock_layout)

        self.btn_sync = QPushButton("📥 同步选定题包至双语处理中心 (激活页签一并高速缓存)", self)
        self.btn_sync.setObjectName("SyncBtn")
        self.btn_sync.setEnabled(False)
        self.btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync.clicked.connect(self.sync_selected_pack_to_workspace)
        console_layout.addWidget(self.btn_sync)

        layout.addWidget(self.console_frame, stretch=1)

        self.browser_win = None
        self.scraped_packs_buffer = []

    def launch_sandbox_browser(self):
        if self.browser_win is None:
            self.browser_win = WebBrowserWindow(self)
            self.browser_win.data_captured.connect(self.on_data_captured)

        main_geom = self.window().geometry()
        self.browser_win.move(
            main_geom.x() - self.browser_win.width() - 15, main_geom.y())
        self.browser_win.show()

        mw = self.window()
        if mw and hasattr(mw, "status_bar"):
            mw.status_bar.showMessage("🧭 自动化辅助浏览器窗口已成功激活并贴边悬浮。", 3000)

    def on_data_captured(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.append(
            f"[{timestamp}] [Packet Intercepted] 🚀 数据回传成功，正在校验对准...")

        try:
            packs = json.loads(text)
            if isinstance(packs, list) and len(packs) > 0 and "video_url" in packs[0]:
                self.scraped_packs_buffer = packs
                self.list_widget.clear()

                for idx, pack in enumerate(packs):
                    pack_id = pack.get("id", f"pack_{idx+1}")
                    self.list_widget.addItem(f"📦 动态题包: {pack_id}")

                if self.scraped_packs_buffer:
                    self.list_widget.setCurrentRow(0)
                    self.btn_sync.setEnabled(True)

                mw = self.window()
                if mw and hasattr(mw, "status_bar"):
                    mw.status_bar.showMessage(
                        f"📥 成功截获并对准 {len(packs)} 个动态题包！可在下方点选同步。", 4000)
            else:
                self.log_box.append(text)
        except Exception:
            self.log_box.append(text)

    def sync_selected_pack_to_workspace(self):
        current_row = self.list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.scraped_packs_buffer):
            return

        selected_pack = self.scraped_packs_buffer[current_row]

        mw = self.window()
        if mw and hasattr(mw, "tab_widget") and hasattr(mw, "active_menus"):
            menu1_tuple = mw.active_menus.get("menu1")
            if menu1_tuple:
                menu1_instance = menu1_tuple[0]

                menu1_instance.url_input.setText(
                    selected_pack.get("video_url", ""))
                menu1_instance.input_a.setPlainText(
                    selected_pack.get("english_text", ""))
                menu1_instance.src_input.setPlainText(
                    selected_pack.get("formatted_json", ""))

                mw.tab_widget.setCurrentIndex(0)

                menu1_instance.load_video_url()

                mw.status_bar.showMessage(
                    f"🚀 题包 {selected_pack.get('id')} 已一键同步并开启后台高速缓存！", 4000)
