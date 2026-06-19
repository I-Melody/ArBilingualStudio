# -*- coding: utf-8 -*-
# 文件路径：menus/menu3.py

import os
import sys
import json
import urllib.request
from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, QPointF, QSettings, QTimer

from .base_menu import BaseMenuWidget

try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    PDF_SUPPORTED = True
except ImportError:
    PDF_SUPPORTED = False

def get_root_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parents[1]


class MenuWidget(BaseMenuWidget):
    """
    菜单3：固定的规则 PDF 手册阅览窗口，集成 Ollama 本地模型与参数动态控制台。
    """
    def init_ui(self):
        self.setStyleSheet("""
            QFrame#PdfContainer {
                background-color: #121214;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            QLabel#WarnLabel {
                color: #a1a1aa;
                font-size: 13px;
                line-height: 1.8;
            }
            QPushButton#PageBtn {
                background-color: #1e1b4b;
                color: #c084fc;
                border: 1px solid #4338ca;
                border-radius: 6px;
                height: 28px;
                padding: 0 15px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#PageBtn:hover {
                background-color: #312e81;
                color: #e9d5ff;
            }
            QPushButton#PageBtn:disabled {
                background-color: #121214;
                color: #52525b;
                border: 1px solid #27272a;
            }
            
            /* Ollama 控制台专属扁平样式 */
            QFrame#ConfigFrame {
                background-color: #161619;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLabel#ConfigLabel {
                color: #a1a1aa;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QComboBox#ConfigCombo {
                background-color: #121214;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                height: 24px;
            }
            QPushButton#ConfigBtn {
                background-color: #1e1b4b;
                color: #c084fc;
                border: 1px solid #4338ca;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                height: 24px;
                padding: 0 10px;
            }
            QPushButton#ConfigBtn:hover {
                background-color: #312e81;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 头部说明
        self.header = QLabel("📖 规则配置手册与规范指南 (rule.pdf)", self)
        self.header.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.header)

        # ======================================================================
        # 【新增】：Ollama 动态引擎交互控制台
        # ======================================================================
        self.config_frame = QFrame(self)
        self.config_frame.setObjectName("ConfigFrame")
        config_layout = QHBoxLayout(self.config_frame)
        config_layout.setContentsMargins(8, 4, 8, 4)
        config_layout.setSpacing(8)

        config_layout.addWidget(QLabel("🤖 本地 Ollama 模型:", self, objectName="ConfigLabel"))
        self.combo_ollama_model = QComboBox(self)
        self.combo_ollama_model.setObjectName("ConfigCombo")
        self.combo_ollama_model.setMinimumWidth(180)
        self.combo_ollama_model.currentTextChanged.connect(self.save_ollama_config)
        config_layout.addWidget(self.combo_ollama_model)

        self.btn_refresh = QPushButton("🔄 扫描可用模型", self)
        self.btn_refresh.setObjectName("ConfigBtn")
        self.btn_refresh.clicked.connect(self.scan_local_ollama_tags)
        config_layout.addWidget(self.btn_refresh)

        config_layout.addSpacing(15)

        config_layout.addWidget(QLabel("🌡️ 创造力温度 (Temp):", self, objectName="ConfigLabel"))
        self.combo_ollama_temp = QComboBox(self)
        self.combo_ollama_temp.setObjectName("ConfigCombo")
        self.combo_ollama_temp.addItems(["0.0 (严谨/推荐)", "0.1", "0.2", "0.5 (温和)", "0.8 (发散)", "1.0 (高创意)"])
        self.combo_ollama_temp.currentTextChanged.connect(self.save_ollama_config)
        config_layout.addWidget(self.combo_ollama_temp)

        config_layout.addStretch()
        layout.addWidget(self.config_frame)
        # ======================================================================

        # 顶部翻页控制条区
        self.control_widget = QWidget(self)
        control_layout = QHBoxLayout(self.control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        self.btn_prev = QPushButton("◀ 上一页", self)
        self.btn_prev.setObjectName("PageBtn")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self.go_prev_page)

        self.page_label = QLabel("第 0 / 0 页", self)
        self.page_label.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 12px;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_next = QPushButton("下一页 ▶", self)
        self.btn_next.setObjectName("PageBtn")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self.go_next_page)

        control_layout.addWidget(self.btn_prev)
        control_layout.addWidget(self.page_label)
        control_layout.addWidget(self.btn_next)
        layout.addWidget(self.control_widget)

        # PDF 主画布容器
        self.container = QFrame(self)
        self.container.setObjectName("PdfContainer")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        
        self.pdf_path = get_root_path() / "rule.pdf" 
        
        self.current_page = 0
        self.current_cols = 1  
        
        self.init_pdf_view_engine()
        layout.addWidget(self.container)

        # 启动后自动载入并对准配置
        self.load_saved_ollama_settings()
        self.scan_local_ollama_tags()

    def load_saved_ollama_settings(self):
        """从注册表还原本地 Ollama 选项"""
        mw = self.window()
        if mw and hasattr(mw, "settings"):
            saved_model = mw.settings.value("ollama_model", "")
            saved_temp = mw.settings.value("ollama_temp", "0.1")
            
            # 回填温度
            for i in range(self.combo_ollama_temp.count()):
                if saved_temp in self.combo_ollama_temp.itemText(i):
                    self.combo_ollama_temp.setCurrentIndex(i)
                    break

    def scan_local_ollama_tags(self):
        """安全扫描本地 Ollama 已下载模型，填充下拉菜单"""
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ 扫描中...")
        
        # 使用轻量级 QTimer 避免阻塞界面，模拟延迟完成探测
        QTimer.singleShot(100, self._exec_ollama_scan)

    def _exec_ollama_scan(self):
        models_found = []
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    models = data.get("models", [])
                    for m in models:
                        name = m.get("name")
                        if name:
                            models_found.append(name)
        except Exception:
            pass

        self.combo_ollama_model.blockSignals(True)
        self.combo_ollama_model.clear()
        if models_found:
            self.combo_ollama_model.addItems(models_found)
            # 还原用户选定的模型
            mw = self.window()
            if mw and hasattr(mw, "settings"):
                saved_model = mw.settings.value("ollama_model", "")
                idx = self.combo_ollama_model.findText(saved_model)
                if idx != -1:
                    self.combo_ollama_model.setCurrentIndex(idx)
        else:
            self.combo_ollama_model.addItem("⚠️ 未检测到运行中的Ollama服务")
        self.combo_ollama_model.blockSignals(False)

        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄 扫描可用模型")

    def save_ollama_config(self):
        """实时将用户改变的引擎设置保存到系统注册表"""
        mw = self.window()
        if not mw or not hasattr(mw, "settings"):
            return
            
        current_model = self.combo_ollama_model.currentText()
        if "未检测到" in current_model or not current_model:
            return
            
        # 提取选中的温度数字
        temp_text = self.combo_ollama_temp.currentText()
        temp_val = "0.1"
        try:
            temp_val = temp_text.split(" ")[0]
        except Exception: pass

        mw.settings.setValue("ollama_model", current_model)
        mw.settings.setValue("ollama_temp", temp_val)
        
        if hasattr(mw, "status_bar"):
            mw.status_bar.showMessage(f"⚙️ Ollama 翻译模型已重设为: {current_model} (Temp: {temp_val})", 3000)

    # ========================== PDF 手册原生功能保护 ==========================
    def init_pdf_view_engine(self):
        if not PDF_SUPPORTED:
            self.control_widget.hide()
            self.show_placeholder(
                "⚠️ [环境警告] 当前系统的 PyQt6 环境中未编译集成 QPdf 渲染模块。\n"
                "您仍可使用外部常规阅读器打开项目根目录下的 rule.pdf 文件进行阅览。"
            )
            return

        if not self.pdf_path.exists():
            self.control_widget.hide()
            self.show_placeholder(
                f"📂 [手册加载引导] 未在项目根目录下检索到 [rule.pdf] 手册文件。\n"
                f"期待检测路径：{self.pdf_path.resolve()}"
            )
            return

        try:
            self.control_widget.show()
            self.document = QPdfDocument(self)
            self.document.load(str(self.pdf_path.resolve()))

            self.view_0 = QPdfView(self)
            self.view_0.setDocument(self.document)
            self.view_0.setPageMode(QPdfView.PageMode.SinglePage)
            self.view_0.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            
            self.view_1 = QPdfView(self)
            self.view_1.setDocument(self.document)
            self.view_1.setPageMode(QPdfView.PageMode.SinglePage)
            self.view_1.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            
            self.view_2 = QPdfView(self)
            self.view_2.setDocument(self.document)
            self.view_2.setPageMode(QPdfView.PageMode.SinglePage)
            self.view_2.setZoomMode(QPdfView.ZoomMode.FitToWidth)

            self.pdf_layout = QHBoxLayout()
            self.pdf_layout.setContentsMargins(0, 0, 0, 0)
            self.pdf_layout.setSpacing(6)
            
            self.pdf_layout.addWidget(self.view_0)
            self.pdf_layout.addWidget(self.view_1)
            self.pdf_layout.addWidget(self.view_2)
            
            self.container_layout.addLayout(self.pdf_layout)
            
            mw = self.window()
            saved_page = 0
            if mw and hasattr(mw, "settings"):
                saved_page = mw.settings.value("rule_pdf_current_page", 0, type=int)

            if saved_page >= self.document.pageCount():
                saved_page = 0
            self.current_page = saved_page

            self.check_responsive_layout()
            self.refresh_page_views()
        except Exception as e:
            self.control_widget.hide()
            self.show_placeholder(f"❌ 载入并渲染 PDF 发生严重异常: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.check_responsive_layout()

    def check_responsive_layout(self):
        if not PDF_SUPPORTED or not self.pdf_path.exists() or not hasattr(self, "view_0"):
            return
        width = self.container.width()
        height = self.container.height()
        if height <= 0: return
        ratio = width / height
        if ratio < 1.1: target_cols = 1
        elif ratio < 1.9: target_cols = 2
        else: target_cols = 3
            
        if target_cols != self.current_cols:
            self.current_cols = target_cols
            self.update_layout_visibility()

    def update_layout_visibility(self):
        if not hasattr(self, "view_0"): return
        self.view_0.setVisible(self.current_cols >= 1)
        self.view_1.setVisible(self.current_cols >= 2)
        self.view_2.setVisible(self.current_cols >= 3)
        self.refresh_page_views()

    def refresh_page_views(self):
        if not hasattr(self, "view_0") or self.document.pageCount() <= 0: return
        base_page = self.current_page
        self.view_0.pageNavigator().jump(base_page, QPointF(), self.view_0.pageNavigator().currentZoom())
        
        if self.current_cols >= 2:
            page_1 = base_page + 1
            if page_1 < self.document.pageCount():
                self.view_1.setVisible(True)
                self.view_1.pageNavigator().jump(page_1, QPointF(), self.view_1.pageNavigator().currentZoom())
            else: self.view_1.setVisible(False)
                
        if self.current_cols >= 3:
            page_2 = base_page + 2
            if page_2 < self.document.pageCount():
                self.view_2.setVisible(True)
                self.view_2.pageNavigator().jump(page_2, QPointF(), self.view_2.pageNavigator().currentZoom())
            else: self.view_2.setVisible(False)
        self.update_nav_controls_state()

    def update_nav_controls_state(self):
        total_pages = self.document.pageCount()
        active_end_page = min(self.current_page + self.current_cols, total_pages)
        if self.current_cols == 1 or active_end_page <= self.current_page + 1:
            self.page_label.setText(f"第 {self.current_page + 1} / {total_pages} 页")
        else:
            self.page_label.setText(f"第 {self.current_page + 1} - {active_end_page} / {total_pages} 页")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page + self.current_cols < total_pages)

    def go_prev_page(self):
        step = self.current_cols
        if self.current_page - step >= 0: self.current_page -= step
        else: self.current_page = 0
        self.refresh_page_views()
        self.save_progress()

    def go_next_page(self):
        step = self.current_cols
        total_pages = self.document.pageCount()
        if self.current_page + step < total_pages: self.current_page += step
        self.refresh_page_views()
        self.save_progress()

    def save_progress(self):
        mw = self.window()
        if mw and hasattr(mw, "settings"):
            mw.settings.setValue("rule_pdf_current_page", self.current_page)

    def show_placeholder(self, text: str):
        for i in reversed(range(self.container_layout.count())): 
            self.container_layout.itemAt(i).widget().setParent(None)
        placeholder = QLabel(text, self)
        placeholder.setObjectName("WarnLabel")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(placeholder)