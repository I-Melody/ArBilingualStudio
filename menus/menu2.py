# -*- coding: utf-8 -*-
# 文件路径：menus/menu2.py

import time
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser, QPushButton, QLabel, QFrame, QListWidget, QWidget, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl

from .base_menu import BaseMenuWidget

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_SUPPORTED = True
except ImportError:
    WEBENGINE_SUPPORTED = False


class BrowserTitleBar(QWidget):
    """
    副窗口（Window 2）专用的扁平化无边框拖拽标题栏
    """

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setFixedHeight(35)
        self.setStyleSheet(
            "background-color: #1b1b1e; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)

        self.lbl = QLabel("🧭 自动化辅助浏览器 (v2.0 物理沙盒)", self)
        self.lbl.setStyleSheet(
            "color: #a1a1aa; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl)

        layout.addStretch()

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { background-color: transparent; color: #71717a; border: none; border-radius: 4px; font-size: 11px; } QPushButton:hover { background-color: #ef4444; color: white; }")
        self.btn_close.clicked.connect(self.parent_window.close)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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


class WebBrowserWindow(QWidget):
    """
    独立副窗口（Window 2）：内置原生多维 DOM 哈希抓包爬虫
    """
    data_captured = pyqtSignal(str)

    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.resize(550, 750)

        central_frame = QFrame(self)
        central_frame.setStyleSheet(
            "background-color: #121214; border: 1px solid #27272a; border-radius: 8px;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(central_frame)

        frame_layout = QVBoxLayout(central_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        # 1. 标题栏
        self.title_bar = BrowserTitleBar(self)
        frame_layout.addWidget(self.title_bar)

        # 2. 地址栏
        url_widget = QWidget(self)
        url_layout = QHBoxLayout(url_widget)
        url_layout.setContentsMargins(10, 0, 10, 0)
        url_layout.setSpacing(6)

        self.url_input = QLineEdit(self)
        self.url_input.setStyleSheet(
            "background-color: #18181b; color: #f4f4f5; border: 1px solid #27272a; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        self.url_input.setText(
            "https://commondatastorage.googleapis.com/.../rule.pdf")
        url_layout.addWidget(self.url_input)

        self.btn_go = QPushButton("导航", self)
        self.btn_go.setFixedSize(50, 24)
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setStyleSheet(
            "background-color: #2563eb; color: white; border-radius: 4px; font-size: 11px; font-weight: bold;")
        self.btn_go.clicked.connect(self.navigate_url)
        url_layout.addWidget(self.btn_go)

        self.btn_capture = QPushButton("⚡ 拦截并同步", self)
        self.btn_capture.setFixedSize(110, 24)
        self.btn_capture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_capture.setStyleSheet(
            "background-color: #0d9488; color: white; border-radius: 4px; font-size: 11px; font-weight: bold;")
        self.btn_capture.clicked.connect(self.capture_network_packet)
        url_layout.addWidget(self.btn_capture)

        frame_layout.addWidget(url_widget)

        # 3. 浏览器网页画布挂载
        self.web_container = QWidget(self)
        self.web_layout = QVBoxLayout(self.web_container)
        self.web_layout.setContentsMargins(10, 2, 10, 10)

        if WEBENGINE_SUPPORTED:
            self.web_view = QWebEngineView(self)
            self.web_view.setStyleSheet(
                "background-color: #000000; border-radius: 6px;")
            self.web_layout.addWidget(self.web_view)
        else:
            self.fallback_lbl = QLabel(
                "🧭 自动化浏览器沙盒就绪\n\n"
                "💡 提示：若要在本窗口内加载嵌入式网页，请在 (venv) 中执行：\n"
                "   pip install PyQt6-WebEngine\n"
                "系统将自动在重启后激活内置 Chromium 渲染层！\n\n"
                "当前显示为【拦截模拟箱】，可在下方修改或粘贴模拟的题包 JSON：",
                self
            )
            self.fallback_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
            self.fallback_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fallback_lbl.setWordWrap(True)
            self.web_layout.addWidget(self.fallback_lbl)

            self.mock_text_edit = QTextEdit(self)
            self.mock_text_edit.setStyleSheet(
                "background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a; border-radius: 6px; font-size: 11px;")
            self.mock_text_edit.setPlainText(
                '[\n'
                '  {\n'
                '    "id": "text-2064524048492191744",\n'
                '    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",\n'
                '    "english_text": "The person picks up the main green garment piece and lays it flat on the table.",\n'
                '    "formatted_json": "[{\\"step_id\\": \\"step_1\\", \\"segment_id\\": \\"event_01\\", \\"modality\\": \\"visual\\", \\"timestamp\\": \\"00:00.000-00:25.500\\", \\"content\\": \\"Bruce name origin.\\", \\"bridge\\": \\"energetic pace\\"}]"\n'
                '  },\n'
                '  {\n'
                '    "id": "text-2064524048492191745",\n'
                '    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",\n'
                '    "english_text": "This shows the pleated strip is about to be attached to the garment.",\n'
                '    "formatted_json": "[{\\"step_id\\": \\"step_2\\", \\"segment_id\\": \\"event_02\\", \\"modality\\": \\"audio\\", \\"timestamp\\": \\"00:30.000-00:59.000\\", \\"content\\": \\"Fast-changing reference images\\", \\"bridge\\": \\"factual montage\\"}]"\n'
                '  }\n'
                ']'
            )
            self.web_layout.addWidget(self.mock_text_edit)

        frame_layout.addWidget(self.web_container, stretch=1)

    def navigate_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if WEBENGINE_SUPPORTED:
            self.web_view.setUrl(QUrl(url))

    def capture_network_packet(self):
        """
        【动态多维哈希 DOM 归组算法 - 真实物理拦截版】
        针对您提供的网页 DOM 树特征进行定制。
        1. 寻找所有 class 为 'textSrc___T0QL6' 且 id 以 'text-' 开头的 div。
        2. 将具有相同 id 的元素（[0]视频地址, [1]英文文本, [2]格式化英文）进行多维哈希合并归组。
        3. 顺着 Qt 通信管道抛回给 Menu2 本地。
        """
        if WEBENGINE_SUPPORTED:
            # 注入针对您网页高度定制的 JS DOM 刮取器
            js_code = """
            (function() {
                // 1. 扫描页面中所有符合您特征的元素
                const elements = document.querySelectorAll('div.textSrc___T0QL6[id^="text-"]');
                const groups = {};
                
                // 2. 按照顺延的 id (如 text-2064524048492191744) 进行物理归组
                elements.forEach(el => {
                    const id = el.id;
                    if (!id) return;
                    if (!groups[id]) groups[id] = [];
                    groups[id].push(el);
                });
                
                const packs = [];
                for (const id in groups) {
                    const els = groups[id];
                    // 3. 校验每个题包容器是否收纳了完整的 [视频、原文、格式化] 三元组
                    if (els.length >= 3) {
                        // 提取第 1 个 div 内的视频 URL
                        const video_url = els[0].innerText.trim();
                        
                        // 提取第 2 个 div 内含多个 span 的英文文本
                        const english_text = els[1].innerText.trim();
                        
                        // 提取第 3 个 div 内部有文字的格式化英文串
                        const formatted_json = els[2].innerText.trim();
                        
                        packs.push({
                            "id": id,
                            "video_url": video_url,
                            "english_text": english_text,
                            "formatted_json": formatted_json
                        });
                    }
                }
                return JSON.stringify(packs);
            })()
            """
            self.web_view.page().runJavaScript(js_code, self.on_js_scraped)
        else:
            # 模拟箱：读取 mock_text_edit 里的内容（支持您在上面修改它，点击依然能测试联动）
            text = self.mock_text_edit.toPlainText().strip()
            if text:
                self.data_captured.emit(text)

    def on_js_scraped(self, result_str):
        if result_str:
            self.data_captured.emit(result_str)


class MenuWidget(BaseMenuWidget):
    """
    Menu2 主控制台。
    """

    def init_ui(self):
        self.setStyleSheet("""
            QFrame#ConsoleFrame { background-color: #161619; border: 1px solid #27272a; border-radius: 8px; padding: 10px; }
            QPushButton#LaunchBtn { background-color: #2563eb; color: white; font-weight: bold; font-size: 12px; border-radius: 6px; height: 36px; border: none; }
            QPushButton#LaunchBtn:hover { background-color: #1d4ed8; }
            
            /* 同步按钮：醒目的青色 */
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
        self.label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.label)

        # 1. 物理控制控制框
        self.console_frame = QFrame(self)
        self.console_frame.setObjectName("ConsoleFrame")
        console_layout = QVBoxLayout(self.console_frame)
        console_layout.setContentsMargins(8, 8, 8, 8)
        console_layout.setSpacing(8)

        # 启动副窗按钮
        self.btn_launch = QPushButton("🚀 启动自动化辅助浏览器 (Window 2)", self)
        self.btn_launch.setObjectName("LaunchBtn")
        self.btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch.clicked.connect(self.launch_sandbox_browser)
        console_layout.addWidget(self.btn_launch)

        # 2. 数据联动选择区（中部分栏）
        data_dock_layout = QHBoxLayout()
        data_dock_layout.setSpacing(8)

        # 2.1 左：提取出的题包物理列表
        list_container = QWidget(self)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(QLabel(
            "📦 已截获的动态题包列表", self, styleSheet="color: #a1a1aa; font-size: 11px; font-weight: bold;"))
        self.list_widget = QListWidget(self)
        list_layout.addWidget(self.list_widget)
        data_dock_layout.addWidget(list_container, stretch=4)

        # 2.2 右：通信监控日志
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

        # 3. 底部联动控制按钮
        self.btn_sync = QPushButton("📥 同步选定题包至双语处理中心 (激活页签一并高速缓存)", self)
        self.btn_sync.setObjectName("SyncBtn")
        self.btn_sync.setEnabled(False)  # 初始没有数据时置灰
        self.btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync.clicked.connect(self.sync_selected_pack_to_workspace)
        console_layout.addWidget(self.btn_sync)

        layout.addWidget(self.console_frame, stretch=1)

        self.browser_win = None
        self.scraped_packs_buffer = []  # 本地抓包历史缓冲区

    def launch_sandbox_browser(self):
        if self.browser_win is None:
            self.browser_win = WebBrowserWindow(self)
            self.browser_win.data_captured.connect(self.on_data_captured)

        # 自适应位置计算：副窗口自动出现在主窗口的左侧，距离 15 像素，完美平齐
        main_geom = self.window().geometry()
        self.browser_win.move(
            main_geom.x() - self.browser_win.width() - 15, main_geom.y())
        self.browser_win.show()

        mw = self.window()
        if mw and hasattr(mw, "status_bar"):
            mw.status_bar.showMessage("🧭 自动化辅助浏览器窗口已成功激活并贴边悬浮。", 3000)

    def on_data_captured(self, text: str):
        """
        接收来自 Window 2 的数据回传。
        自动检测并解析结构化 JSON 格式，将其无感映射入左侧列表。
        """
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.append(
            f"[{timestamp}] [Packet Intercepted] 🚀 数据回传成功，正在校验对准...")

        try:
            # 尝试反序列化
            packs = json.loads(text)
            if isinstance(packs, list) and len(packs) > 0 and "video_url" in packs[0]:
                self.scraped_packs_buffer = packs
                self.list_widget.clear()

                # 回填选择列表
                for idx, pack in enumerate(packs):
                    pack_id = pack.get("id", f"pack_{idx+1}")
                    self.list_widget.addItem(f"📦 动态题包: {pack_id}")

                if self.scraped_packs_buffer:
                    self.list_widget.setCurrentRow(0)
                    self.btn_sync.setEnabled(True)  # 点亮同步按钮

                mw = self.window()
                if mw and hasattr(mw, "status_bar"):
                    mw.status_bar.showMessage(
                        f"📥 成功截获并对准 {len(packs)} 个动态题包！可在下方点选同步。", 4000)
            else:
                self.log_box.append(text)
        except Exception:
            # 常规非结构化文本，直接走日志打印
            self.log_box.append(text)

    def sync_selected_pack_to_workspace(self):
        """
        【极速多窗口联动核心】：
        获取当前 Menu2 选定的物理题包，一键洗入主工作台（Menu1）的三个输入框中。
        强制将页签切回页签 1，并零延迟自动激活 4 线程下载缓存！
        """
        current_row = self.list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.scraped_packs_buffer):
            return

        selected_pack = self.scraped_packs_buffer[current_row]

        # 顺着 QMainWindow 树向上搜寻主页签实例
        mw = self.window()
        if mw and hasattr(mw, "tab_widget") and hasattr(mw, "active_menus"):
            menu1_tuple = mw.active_menus.get("menu1")
            if menu1_tuple:
                menu1_instance = menu1_tuple[0]

                # 1. 强行跨窗口注入数据
                menu1_instance.url_input.setText(
                    selected_pack.get("video_url", ""))
                menu1_instance.input_a.setPlainText(
                    selected_pack.get("english_text", ""))
                menu1_instance.src_input.setPlainText(
                    selected_pack.get("formatted_json", ""))

                # 2. 页签无感自适应回切 (切回双语处理中心)
                mw.tab_widget.setCurrentIndex(0)

                # 3. 自动唤醒后台 4 线程并发下载管线！
                menu1_instance.load_video_url()

                mw.status_bar.showMessage(
                    f"🚀 题包 {selected_pack.get('id')} 已一键同步并开启后台高速缓存！", 4000)
