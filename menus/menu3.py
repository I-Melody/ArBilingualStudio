# -*- coding: utf-8 -*-
# 文件路径：menus/menu3.py

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, QPointF

from .base_menu import BaseMenuWidget
import sys

# 安全动态检测 PyQt6 的 PDF 渲染原生套件
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
    菜单3：固定的规则 PDF 手册阅览窗口。
    支持自适应纵横比的 1、2、3 页智能响应式分屏切换，并保持阅读状态进度。
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
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 头部说明
        self.header = QLabel("📖 规则配置手册与规范指南 (rule.pdf)", self)
        self.header.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(self.header)

        # 1. 顶部翻页控制条区
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

        # 2. PDF 主画布容器
        self.container = QFrame(self)
        self.container.setObjectName("PdfContainer")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        
        self.pdf_path = get_root_path() / "rule.pdf" 
        
        # 本地阅读基本状态存储器
        self.current_page = 0
        self.current_cols = 1  # 初始默认 1 栏（单页）
        
        self.init_pdf_view_engine()
        layout.addWidget(self.container)

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
                f"期待检测路径：{self.pdf_path.resolve()}\n\n"
                f"💡 解决方法：\n"
                f"   请将需要阅览的 PDF 手册重命名为 'rule.pdf'，并拖放入上述文件夹中，"
                f"然后点击其他页签再切回来，软件将自动重新载入、规整并渲染。"
            )
            return

        try:
            self.control_widget.show()
            
            # 【核心优化】：实例化 1 个物理文档，供给 3 个独立视窗同时渲染 (节约内存)
            self.document = QPdfDocument(self)
            self.document.load(str(self.pdf_path.resolve()))

            # 初始化 3 联屏视窗
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

            # 横向流式拼接
            self.pdf_layout = QHBoxLayout()
            self.pdf_layout.setContentsMargins(0, 0, 0, 0)
            self.pdf_layout.setSpacing(6)
            
            self.pdf_layout.addWidget(self.view_0)
            self.pdf_layout.addWidget(self.view_1)
            self.pdf_layout.addWidget(self.view_2)
            
            self.container_layout.addLayout(self.pdf_layout)
            
            # 从本地读取阅读进度（最左侧基准页码）
            mw = self.window()
            saved_page = 0
            if mw and hasattr(mw, "settings"):
                saved_page = mw.settings.value("rule_pdf_current_page", 0, type=int)

            if saved_page >= self.document.pageCount():
                saved_page = 0

            self.current_page = saved_page

            # 初始化进行自适应探测与渲染
            self.check_responsive_layout()
            self.refresh_page_views()
            
            mw = self.window()
            if hasattr(mw, "status_bar"):
                mw.status_bar.showMessage("📖 响应式离线手册载入成功，支持单/双/三页自适应视窗排版。", 3000)
                
        except Exception as e:
            self.control_widget.hide()
            self.show_placeholder(f"❌ 载入并渲染 PDF 发生严重异常: {e}")

    # ========================== 响应式核心控制流 ==========================
    def resizeEvent(self, event):
        """
        覆写主窗体拉伸事件，实现毫秒级自适应比率探测
        """
        super().resizeEvent(event)
        self.check_responsive_layout()

    def check_responsive_layout(self):
        """
        自适应比率分析仪。
        纵向窄屏 (高远大于宽，比率 < 1.1) -> 1页
        横向标准屏 (1.1 <= 比率 < 1.9) -> 2页
        横向超宽屏 (比率 >= 1.9) -> 3页
        """
        if not PDF_SUPPORTED or not self.pdf_path.exists() or not hasattr(self, "view_0"):
            return
            
        width = self.container.width()
        height = self.container.height()
        if height <= 0:
            return
            
        ratio = width / height
        
        # 换算目标列数
        if ratio < 1.1:
            target_cols = 1
        elif ratio < 1.9:
            target_cols = 2
        else:
            target_cols = 3
            
        # 若发生分级跨越，执行重排
        if target_cols != self.current_cols:
            self.current_cols = target_cols
            self.update_layout_visibility()

    def update_layout_structure(self):
        # 兼容旧更名方法
        self.update_layout_visibility()

    def update_layout_visibility(self):
        """
        动态显隐隐藏视窗，交由 Qt 原生布局引擎，重排耗时 0 毫秒，毫无闪烁感
        """
        if not hasattr(self, "view_0"):
            return
            
        self.view_0.setVisible(self.current_cols >= 1)
        self.view_1.setVisible(self.current_cols >= 2)
        self.view_2.setVisible(self.current_cols >= 3)
        
        self.refresh_page_views()

    def refresh_page_views(self):
        """
        根据基准页码与当前列数，智能流式渲染各个分屏页面，并处理页码溢出保护
        """
        if not hasattr(self, "view_0") or self.document.pageCount() <= 0:
            return
            
        base_page = self.current_page
        
        # 视窗 0：永远渲染基准页
        self.view_0.pageNavigator().jump(base_page, QPointF(), self.view_0.pageNavigator().currentZoom())
        
        # 视窗 1：开本右侧页
        if self.current_cols >= 2:
            page_1 = base_page + 1
            if page_1 < self.document.pageCount():
                self.view_1.setVisible(True)
                self.view_1.pageNavigator().jump(page_1, QPointF(), self.view_1.pageNavigator().currentZoom())
            else:
                self.view_1.setVisible(False)  # 溢出时隐藏该屏
                
        # 视窗 2：三联屏最右侧页
        if self.current_cols >= 3:
            page_2 = base_page + 2
            if page_2 < self.document.pageCount():
                self.view_2.setVisible(True)
                self.view_2.pageNavigator().jump(page_2, QPointF(), self.view_2.pageNavigator().currentZoom())
            else:
                self.view_2.setVisible(False)
                
        # 刷新顶部的播控指示与按钮状态
        self.update_nav_controls_state()

    def update_nav_controls_state(self):
        """
        自适应书籍排版页码计算
        """
        total_pages = self.document.pageCount()
        
        # 计算当前展现的最大物理页数
        active_end_page = min(self.current_page + self.current_cols, total_pages)
        
        if self.current_cols == 1 or active_end_page <= self.current_page + 1:
            self.page_label.setText(f"第 {self.current_page + 1} / {total_pages} 页")
        else:
            self.page_label.setText(f"第 {self.current_page + 1} - {active_end_page} / {total_pages} 页")
            
        # 按钮临界状态锁定控制
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page + self.current_cols < total_pages)

    # ========================== 翻页业务控制流（自适应步长） ==========================
    def go_prev_page(self):
        # 向前跳转当前屏数对应的页码（例如双页开本下，一次往前翻2页）
        step = self.current_cols
        if self.current_page - step >= 0:
            self.current_page -= step
        else:
            self.current_page = 0
            
        self.refresh_page_views()
        self.save_progress()

    def go_next_page(self):
        # 向后跳转当前屏数对应的页码（符合真实看书习惯）
        step = self.current_cols
        total_pages = self.document.pageCount()
        if self.current_page + step < total_pages:
            self.current_page += step
            
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