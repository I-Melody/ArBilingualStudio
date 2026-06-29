# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QEvent, QTimer, QPoint, QRect
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton, QSizeGrip

from .timeline_ticks import TimelineTicks

try:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_SUPPORTED = True
except ImportError:
    MULTIMEDIA_SUPPORTED = False


class VideoTitleBar(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #0a0a0a;")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        self.btn_pin = QPushButton("📌", self)
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            "QPushButton { background-color: transparent; color: #52525b; border: none; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #27272a; color: #fbbf24; }")
        self.btn_pin.clicked.connect(self._toggle_pin)
        layout.addWidget(self.btn_pin)

        self.lbl = QLabel("📺 视频独立播放视窗", self)
        self.lbl.setStyleSheet("color: #71717a; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl)

        layout.addStretch()

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { background-color: transparent; color: #52525b; border: none; border-radius: 4px; font-size: 11px; } QPushButton:hover { background-color: #ef4444; color: white; }")
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


class ExternalVideoWindow(QWidget):
    EDGE_MARGIN = 4

    def __init__(self, player, main_menu):
        super().__init__()
        self.player = player
        self.main_menu = main_menu
        self._is_dragging_slider = False
        self.setWindowTitle("📺 视频独立播放视窗")
        self.resize(800, 600)
        self.setMinimumSize(320, 240)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self._resize_edges = 0
        self._drag_start_global = QPoint()
        self._drag_start_geometry = QRect()

        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(80)
        self._edge_timer.timeout.connect(self._update_edge_cursor)
        self._edge_timer.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = VideoTitleBar(self)
        layout.addWidget(self.title_bar)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.video_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video_widget.installEventFilter(self)
        layout.addWidget(self.video_widget, stretch=1)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.progress_slider.setFixedHeight(20)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #27272a;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3b82f6;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 2px;
            }
        """)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self.progress_slider)

        self.timeline_ticks = TimelineTicks(self)
        layout.addWidget(self.timeline_ticks)

        grip_row = QWidget(self)
        grip_layout = QHBoxLayout(grip_row)
        grip_layout.setContentsMargins(0, 0, 4, 0)
        grip_layout.addStretch()
        size_grip = QSizeGrip(self)
        size_grip.setFixedSize(14, 14)
        size_grip.setStyleSheet("QSizeGrip { background: transparent; }")
        grip_layout.addWidget(size_grip)
        layout.addWidget(grip_row)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(250)
        self.poll_timer.timeout.connect(self._poll_progress)

        self.player.setVideoOutput(self.video_widget)
        self.setFocus()

        dur = self.player.duration()
        if dur > 0:
            self.progress_slider.setRange(0, dur)
            self.timeline_ticks.set_duration(dur)
        self.poll_timer.start()

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

    def eventFilter(self, obj, event):
        if obj == self.video_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.setFocus()
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if not MULTIMEDIA_SUPPORTED:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key.Key_Space:
            self.main_menu.toggle_playback()
            event.accept()
        elif key == Qt.Key.Key_Left:
            self.main_menu.seek_offset(-5000)
            event.accept()
        elif key == Qt.Key.Key_Right:
            self.main_menu.seek_offset(5000)
            event.accept()
        elif key == Qt.Key.Key_Up:
            self.main_menu.adjust_volume_offset(5)
            event.accept()
        elif key == Qt.Key.Key_Down:
            self.main_menu.adjust_volume_offset(-5)
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._edge_timer.stop()
        self.poll_timer.stop()
        self.main_menu.restore_video_to_embedded()
        super().closeEvent(event)

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

    def _poll_progress(self):
        if not MULTIMEDIA_SUPPORTED:
            return
        pos = self.player.position()
        dur = self.player.duration()
        if not self._is_dragging_slider:
            if self.progress_slider.maximum() != dur and dur > 0:
                self.progress_slider.setRange(0, dur)
                self.timeline_ticks.set_duration(dur)
            self.progress_slider.setValue(pos)

    def _on_slider_pressed(self):
        self._is_dragging_slider = True

    def _on_slider_released(self):
        self._is_dragging_slider = False
        self.player.setPosition(self.progress_slider.value())

    def _on_slider_moved(self, position: int):
        pass
