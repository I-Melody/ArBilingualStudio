# -*- coding: utf-8 -*-
from pathlib import Path
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    PDF_SUPPORTED = True
except ImportError:
    PDF_SUPPORTED = False


class PdfViewerWidget(QWidget):
    def __init__(self, pdf_path: Path, settings=None, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self._settings = settings
        self.current_page = 0
        self.current_cols = 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

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

        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.container)

        self.container.setStyleSheet(
            "background-color: #121214; border: 1px solid #27272a; border-radius: 8px;"
        )

        QTimer.singleShot(0, self._init_pdf)

    def _init_pdf(self):
        if not PDF_SUPPORTED:
            self.control_widget.hide()
            self._show_placeholder(
                "⚠️ [环境警告] 当前系统的 PyQt6 环境中未编译集成 QPdf 渲染模块。\n"
                "您仍可使用外部常规阅读器打开项目根目录下的 rule.pdf 文件进行阅览。"
            )
            return

        if not self.pdf_path.exists():
            self.control_widget.hide()
            self._show_placeholder(
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

            saved_page = 0
            if self._settings:
                saved_page = self._settings.value("rule_pdf_current_page", 0, type=int)

            if saved_page >= self.document.pageCount():
                saved_page = 0
            self.current_page = saved_page

            self.check_responsive_layout()
            self.refresh_page_views()
        except Exception as e:
            self.control_widget.hide()
            self._show_placeholder(f"❌ 载入并渲染 PDF 发生严重异常: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.check_responsive_layout()

    def check_responsive_layout(self):
        if not PDF_SUPPORTED or not self.pdf_path.exists() or not hasattr(self, "view_0"):
            return
        width = self.container.width()
        height = self.container.height()
        if height <= 0:
            return
        ratio = width / height
        if ratio < 1.1:
            target_cols = 1
        elif ratio < 1.9:
            target_cols = 2
        else:
            target_cols = 3

        if target_cols != self.current_cols:
            self.current_cols = target_cols
            self.update_layout_visibility()

    def update_layout_visibility(self):
        if not hasattr(self, "view_0"):
            return
        self.view_0.setVisible(self.current_cols >= 1)
        self.view_1.setVisible(self.current_cols >= 2)
        self.view_2.setVisible(self.current_cols >= 3)
        self.refresh_page_views()

    def refresh_page_views(self):
        if not hasattr(self, "view_0") or self.document.pageCount() <= 0:
            return
        base_page = self.current_page
        self.view_0.pageNavigator().jump(base_page, QPointF(), self.view_0.pageNavigator().currentZoom())

        if self.current_cols >= 2:
            page_1 = base_page + 1
            if page_1 < self.document.pageCount():
                self.view_1.setVisible(True)
                self.view_1.pageNavigator().jump(page_1, QPointF(), self.view_1.pageNavigator().currentZoom())
            else:
                self.view_1.setVisible(False)

        if self.current_cols >= 3:
            page_2 = base_page + 2
            if page_2 < self.document.pageCount():
                self.view_2.setVisible(True)
                self.view_2.pageNavigator().jump(page_2, QPointF(), self.view_2.pageNavigator().currentZoom())
            else:
                self.view_2.setVisible(False)
        self._update_nav()

    def _update_nav(self):
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
        if self.current_page - step >= 0:
            self.current_page -= step
        else:
            self.current_page = 0
        self.refresh_page_views()
        self._save_progress()

    def go_next_page(self):
        step = self.current_cols
        total_pages = self.document.pageCount()
        if self.current_page + step < total_pages:
            self.current_page += step
        self.refresh_page_views()
        self._save_progress()

    def _save_progress(self):
        if self._settings:
            self._settings.setValue("rule_pdf_current_page", self.current_page)

    def _show_placeholder(self, text: str):
        for i in reversed(range(self.container_layout.count())):
            self.container_layout.itemAt(i).widget().setParent(None)
        placeholder = QLabel(text, self)
        placeholder.setObjectName("WarnLabel")
        placeholder.setStyleSheet("color: #a1a1aa; font-size: 13px; line-height: 1.8;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(placeholder)
