# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSlider

from .timeline_ticks import TimelineTicks

try:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_SUPPORTED = True
except ImportError:
    MULTIMEDIA_SUPPORTED = False


class ExternalVideoWindow(QWidget):
    def __init__(self, player, main_menu):
        super().__init__()
        self.player = player
        self.main_menu = main_menu
        self._is_dragging_slider = False
        self.setWindowTitle("📺 视频独立播放视窗 (双屏/大图细节模式)")
        self.resize(800, 600)
        self.setStyleSheet("background-color: #000000;")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video_widget.installEventFilter(self)
        layout.addWidget(self.video_widget)

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
        self.poll_timer.stop()
        self.main_menu.restore_video_to_embedded()
        super().closeEvent(event)

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
