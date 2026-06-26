# -*- coding: utf-8 -*-
import json
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QFrame, QLineEdit, QPushButton
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_SUPPORTED = True
except ImportError:
    WEBENGINE_SUPPORTED = False


class BrowserTitleBar(QWidget):
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
        self.lbl.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 11px;")
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
            self._drag_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class WebBrowserWindow(QWidget):
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

        self.title_bar = BrowserTitleBar(self)
        frame_layout.addWidget(self.title_bar)

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

        self.web_container = QWidget(self)
        self.web_layout = QVBoxLayout(self.web_container)
        self.web_layout.setContentsMargins(10, 2, 10, 10)

        if WEBENGINE_SUPPORTED:
            self.web_view = QWebEngineView(self)
            self.web_view.setStyleSheet("background-color: #000000; border-radius: 6px;")
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
        if WEBENGINE_SUPPORTED:
            js_code = """
            (function() {
                const elements = document.querySelectorAll('div.textSrc___T0QL6[id^="text-"]');
                const groups = {};
                elements.forEach(el => {
                    const id = el.id;
                    if (!id) return;
                    if (!groups[id]) groups[id] = [];
                    groups[id].push(el);
                });
                const packs = [];
                for (const id in groups) {
                    const els = groups[id];
                    if (els.length >= 3) {
                        const video_url = els[0].innerText.trim();
                        const english_text = els[1].innerText.trim();
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
            text = self.mock_text_edit.toPlainText().strip()
            if text:
                self.data_captured.emit(text)

    def on_js_scraped(self, result_str):
        if result_str:
            self.data_captured.emit(result_str)
