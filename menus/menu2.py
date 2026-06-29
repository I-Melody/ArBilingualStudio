# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QLineEdit, QPushButton
)

from menus.menu1 import MenuWidget as Menu1Widget
from ui.widgets.browser_window import WebBrowserWindow


class MenuWidget(Menu1Widget):
    def init_ui(self):
        super().init_ui()
        self._browser_win = None
        self._replace_phrase_with_web_ops()

    def load_words_config(self):
        pass

    def on_unload(self):
        if self._browser_win is not None:
            self._browser_win.close()
            self._browser_win = None
        super().on_unload()

    def _replace_phrase_with_web_ops(self):
        phrase_layout = self.phrase_frame.layout()
        while phrase_layout.count():
            item = phrase_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_layout(item.layout())

        header = QLabel("🌐 网页操作", self)
        header.setObjectName("SectionHeader")
        phrase_layout.addWidget(header)

        phrase_layout.addStretch()

        url_row = QWidget(self)
        url_row.setStyleSheet("background-color: transparent;")
        url_layout = QHBoxLayout(url_row)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(6)

        self.web_url_input = QLineEdit(self)
        self.web_url_input.setPlaceholderText("在此输入网页URL地址...")
        self.web_url_input.setCursor(Qt.CursorShape.IBeamCursor)
        self.web_url_input.returnPressed.connect(self._open_web_url)
        url_layout.addWidget(self.web_url_input)

        self.btn_open_url = QPushButton("打开", self)
        self.btn_open_url.setFixedWidth(50)
        self.btn_open_url.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_url.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open_url.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; border-radius: 4px; height: 28px; font-size: 11px; border: none;"
        )
        self.btn_open_url.clicked.connect(self._open_web_url)
        url_layout.addWidget(self.btn_open_url)

        phrase_layout.addWidget(url_row)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_layout(item.layout())

    def _open_web_url(self):
        url = self.web_url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.web_url_input.setText(url)

        if self._browser_win is None:
            self._browser_win = WebBrowserWindow()
            self._browser_win.data_captured.connect(self._on_browser_data)

        self._browser_win.open_url(url)
        self._browser_win.show()

        mw = self.window()
        if mw and hasattr(mw, "status_bar"):
            mw.status_bar.showMessage(f"🌐 已在内置浏览器中打开: {url}", 4000)

    def _on_browser_data(self, data: str):
        pass
