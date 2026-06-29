# -*- coding: utf-8 -*-
import json
import sys
import os
import traceback
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QPoint, QRect, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QFrame, QLineEdit, QPushButton, QMessageBox, QSizeGrip
)

WEBENGINE_SUPPORTED = False
_WEBENGINE_ERROR = ""

if sys.platform == "win32" and getattr(sys, "frozen", False):
    try:
        import PyQt6.Qt6 as _qt6_mod
        _qt6_dir = os.path.dirname(_qt6_mod.__file__)
        os.add_dll_directory(_qt6_dir)
    except Exception:
        pass

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    WEBENGINE_SUPPORTED = True
except Exception as e:
    _WEBENGINE_ERROR = traceback.format_exc()
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        try:
            import PyQt6.Qt6
            _dll_dir = os.path.dirname(PyQt6.Qt6.__file__)
            os.add_dll_directory(_dll_dir)
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            WEBENGINE_SUPPORTED = True
            _WEBENGINE_ERROR = ""
        except Exception:
            pass


if WEBENGINE_SUPPORTED:
    class BrowserWebPage(QWebEnginePage):
        def createWindow(self, _type):
            view = self.parent()
            msg = QMessageBox(view if isinstance(view, QWidget) else None)
            msg.setWindowTitle("新窗口请求")
            msg.setText("网页尝试打开新窗口。\n是否在当前窗口打开？")
            yes_btn = msg.addButton("在当前窗口打开", QMessageBox.ButtonRole.AcceptRole)
            no_btn = msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(yes_btn)
            msg.exec()
            if msg.clickedButton() == yes_btn:
                return self
            return None


class BrowserTitleBar(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setFixedHeight(35)
        self.setStyleSheet(
            "background-color: #1b1b1e; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(4)

        self.btn_pin = QPushButton("📌", self)
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            "QPushButton { background-color: transparent; color: #71717a; border: none; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #27272a; color: #fbbf24; }")
        self.btn_pin.clicked.connect(self._toggle_pin)
        layout.addWidget(self.btn_pin)

        self.lbl = QLabel("🌐 网页浏览器", self)
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

    def _toggle_pin(self):
        flags = self.parent_window.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            self.parent_window.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setText("📌")
        else:
            self.parent_window.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setText("📍")
        self.parent_window.show()

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
    EDGE_MARGIN = 4
    data_captured = pyqtSignal(str)

    def __init__(self, parent=None, url: str = ""):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(350, 400)
        self.resize(550, 750)
        self._resize_edges = 0
        self._drag_start_global = QPoint()
        self._drag_start_geometry = QRect()

        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(80)
        self._edge_timer.timeout.connect(self._update_edge_cursor)
        self._edge_timer.start()

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
        if url:
            self.url_input.setText(url)
        else:
            self.url_input.setPlaceholderText("输入网页URL...")
        self.url_input.returnPressed.connect(self.navigate_to_url)
        url_layout.addWidget(self.url_input)

        self.btn_go = QPushButton("导航", self)
        self.btn_go.setFixedSize(50, 24)
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setStyleSheet(
            "background-color: #2563eb; color: white; border-radius: 4px; font-size: 11px; font-weight: bold;")
        self.btn_go.clicked.connect(self.navigate_to_url)
        url_layout.addWidget(self.btn_go)

        self.btn_extract = QPushButton("🔍 抓取", self)
        self.btn_extract.setFixedSize(60, 24)
        self.btn_extract.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_extract.setStyleSheet(
            "background-color: #0d9488; color: white; border-radius: 4px; font-size: 11px; font-weight: bold;")
        self.btn_extract.clicked.connect(self._on_extract_clicked)
        url_layout.addWidget(self.btn_extract)

        frame_layout.addWidget(url_widget)

        self.web_container = QWidget(self)
        self.web_layout = QVBoxLayout(self.web_container)
        self.web_layout.setContentsMargins(10, 2, 10, 10)

        if WEBENGINE_SUPPORTED:
            self.web_view = QWebEngineView(self)
            self.web_view.setPage(BrowserWebPage(self.web_view))
            self.web_view.setStyleSheet("background-color: #000000; border-radius: 6px;")
            self.web_view.titleChanged.connect(self._on_title_changed)
            self.web_layout.addWidget(self.web_view)
        else:
            err_msg = _WEBENGINE_ERROR if _WEBENGINE_ERROR else "PyQt6-WebEngine 未安装"
            fallback = QTextEdit(self)
            fallback.setReadOnly(True)
            fallback.setPlainText(
                f"⚠️ 内置浏览器不可用\n\n{err_msg}\n\n"
                f"请执行: pip install PyQt6-WebEngine"
            )
            fallback.setStyleSheet("color: #f87171; font-size: 9px; background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 10px; font-family: 'Consolas', 'Courier New', monospace;")
            self.web_layout.addWidget(fallback)

        frame_layout.addWidget(self.web_container, stretch=1)

        grip_row = QWidget(self)
        grip_layout = QHBoxLayout(grip_row)
        grip_layout.setContentsMargins(0, 0, 4, 4)
        grip_layout.addStretch()
        size_grip = QSizeGrip(self)
        size_grip.setFixedSize(14, 14)
        size_grip.setStyleSheet("QSizeGrip { background: transparent; }")
        grip_layout.addWidget(size_grip)
        frame_layout.addWidget(grip_row)

        if url and WEBENGINE_SUPPORTED:
            self.navigate_to_url(url)

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
            self._resize_edges = self._get_resize_edges(event.position().toPoint())
            if self._resize_edges:
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
            edges = self._get_resize_edges(event.position().toPoint())
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

    def _update_edge_cursor(self):
        if self._resize_edges:
            return
        pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(pos):
            return
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

    def navigate_to_url(self, url: str = None):
        if url is None:
            url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.url_input.setText(url)
        if WEBENGINE_SUPPORTED:
            self.web_view.setUrl(QUrl(url))

    def open_url(self, url: str):
        self.url_input.setText(url)
        self.navigate_to_url(url)

    def extract_text(self, css_selector: str, callback):
        if not WEBENGINE_SUPPORTED:
            callback([])
            return
        js = f"""
        (function() {{
            const els = document.querySelectorAll('{css_selector}');
            return JSON.stringify(Array.from(els).map(el => el.innerText.trim()));
        }})()
        """
        self.web_view.page().runJavaScript(js, lambda result: callback(json.loads(result) if result else []))

    def extract_html(self, css_selector: str, callback):
        if not WEBENGINE_SUPPORTED:
            callback([])
            return
        js = f"""
        (function() {{
            const els = document.querySelectorAll('{css_selector}');
            return JSON.stringify(Array.from(els).map(el => el.outerHTML));
        }})()
        """
        self.web_view.page().runJavaScript(js, lambda result: callback(json.loads(result) if result else []))

    def run_page_js(self, js_code: str, callback=None):
        if not WEBENGINE_SUPPORTED:
            if callback:
                callback(None)
            return
        self.web_view.page().runJavaScript(js_code, callback)

    def get_page_html(self, callback):
        if not WEBENGINE_SUPPORTED:
            callback("")
            return
        self.web_view.page().toHtml(callback)

    def _on_extract_clicked(self):
        self.capture_network_packet()

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

    def on_js_scraped(self, result_str):
        if result_str:
            self.data_captured.emit(result_str)

    def _on_title_changed(self, title):
        if title:
            self.title_bar.lbl.setText(f"🌐 {title}")
