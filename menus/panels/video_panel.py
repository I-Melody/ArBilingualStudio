# -*- coding: utf-8 -*-
import hashlib
import re
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel,
    QPushButton, QLineEdit, QApplication,
)

from core.paths import get_app_root
from core import config as app_config
from core.error_handler import log_error, log_warning
from ui.widgets.focus_frame import FocusFrame
from ui.widgets.timeline_ticks import TimelineTicks
from ui.widgets.video_player import ExternalVideoWindow
from ui.workers.download_worker import VideoDownloadWorker

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_SUPPORTED = True
except ImportError:
    MULTIMEDIA_SUPPORTED = False


class VideoPanel(QWidget):
    status_message = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dragging_slider = False
        self._stream_mode = False
        self.player: QMediaPlayer | None = None
        self.audio_output = None
        self.video_widget: QVideoWidget | None = None
        self.popup_window = None
        self.download_worker = None
        self.poll_timer = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.frame = FocusFrame(self)
        self.frame.setObjectName("VideoFrame")
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(8)
        frame_layout.addWidget(QLabel("📹 视频播放控制", self, objectName="SectionHeader"))

        url_layout = QHBoxLayout()
        url_layout.setSpacing(6)
        self.url_input = QLineEdit(self)
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("在此输入在线MP4视频URL链接...")
        self.url_input.setText("https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4")
        self.url_input.setCursor(Qt.CursorShape.IBeamCursor)
        url_layout.addWidget(self.url_input)

        self.btn_load_video = QPushButton("加载", self)
        self.btn_load_video.setObjectName("PlayerBtn")
        self.btn_load_video.setFixedWidth(50)
        self.btn_load_video.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_video.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_load_video.clicked.connect(self.load_video_url)
        url_layout.addWidget(self.btn_load_video)

        self.btn_clear_cache = QPushButton("清空缓存", self)
        self.btn_clear_cache.setObjectName("PlayerBtn")
        self.btn_clear_cache.setFixedWidth(65)
        self.btn_clear_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_cache.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear_cache.clicked.connect(self.clear_local_cache)
        url_layout.addWidget(self.btn_clear_cache)

        self.btn_clip_video = QPushButton("📋 剪切板", self)
        self.btn_clip_video.setObjectName("ClipBtn")
        self.btn_clip_video.setFixedWidth(75)
        self.btn_clip_video.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip_video.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clip_video.clicked.connect(self.load_video_from_clipboard)
        url_layout.addWidget(self.btn_clip_video)

        self.btn_fill_all = QPushButton("⚡ 一键填充", self)
        self.btn_fill_all.setObjectName("ClipBtn")
        self.btn_fill_all.setFixedWidth(85)
        self.btn_fill_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fill_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_fill_all.clicked.connect(lambda: self.one_click_fill.emit())
        url_layout.addWidget(self.btn_fill_all)
        frame_layout.addLayout(url_layout)

        self.video_canvas_container = QWidget(self)
        self.video_canvas_layout = QVBoxLayout(self.video_canvas_container)
        self.video_canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.control_bar = QWidget(self)
        control_bar_layout = QVBoxLayout(self.control_bar)
        control_bar_layout.setContentsMargins(0, 0, 0, 0)
        control_bar_layout.setSpacing(4)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.progress_slider.setEnabled(False)
        self.progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        control_bar_layout.addWidget(self.progress_slider)

        self.timeline_ticks = TimelineTicks(self)
        control_bar_layout.addWidget(self.timeline_ticks)

        buttons_row = QWidget(self)
        buttons_layout = QHBoxLayout(buttons_row)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(6)

        self.btn_play_pause = QPushButton("▶ 播放", self)
        self.btn_play_pause.setObjectName("PlayerBtn")
        self.btn_play_pause.setFixedWidth(65)
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        self.btn_play_pause.setEnabled(False)
        buttons_layout.addWidget(self.btn_play_pause)

        self.btn_popup_play = QPushButton("🔲 窗口播放", self)
        self.btn_popup_play.setObjectName("PlayerBtn")
        self.btn_popup_play.setFixedWidth(85)
        self.btn_popup_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_popup_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_popup_play.clicked.connect(self.open_external_video_window)
        self.btn_popup_play.setEnabled(False)
        buttons_layout.addWidget(self.btn_popup_play)

        buttons_layout.addStretch()

        self.time_label = QLabel("00:00 / 00:00", self)
        self.time_label.setStyleSheet("color: #a1a1aa; font-family: monospace; font-size: 11px;")
        buttons_layout.addWidget(self.time_label)

        self.lbl_volume = QLabel("🔊", self)
        self.lbl_volume.setStyleSheet("font-size: 11px;")
        buttons_layout.addWidget(self.lbl_volume)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(60)
        self.volume_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        buttons_layout.addWidget(self.volume_slider)

        self.timestamp_input = QLineEdit(self)
        self.timestamp_input.setPlaceholderText("00:00")
        self.timestamp_input.setStyleSheet("QLineEdit { background-color: #121214; color: #e4e4e7; border: 1px solid #27272a; border-radius: 4px; padding: 2px 4px; font-size: 10px; font-family: monospace; }")
        self.timestamp_input.setFixedWidth(50)
        self.timestamp_input.returnPressed.connect(self.jump_to_timestamp)
        buttons_layout.addWidget(self.timestamp_input)

        self.btn_jump = QPushButton("跳转", self)
        self.btn_jump.setObjectName("PlayerBtn")
        self.btn_jump.setFixedWidth(40)
        self.btn_jump.setFixedHeight(20)
        self.btn_jump.setStyleSheet("font-size: 10px; padding: 0;")
        self.btn_jump.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_jump.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_jump.clicked.connect(self.jump_to_timestamp)
        buttons_layout.addWidget(self.btn_jump)

        control_bar_layout.addWidget(buttons_row)
        self._init_multimedia_engine()

        frame_layout.addWidget(self.video_canvas_container, stretch=1)
        frame_layout.addWidget(self.control_bar)
        layout.addWidget(self.frame)

    one_click_fill = pyqtSignal()
    clipboard_video_loaded = pyqtSignal(str)

    def _init_multimedia_engine(self):
        if not MULTIMEDIA_SUPPORTED:
            warn_lbl = QLabel("⚠️ [多媒体不支持] 未检测到 PyQt6.QtMultimedia 驱动。", self)
            warn_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
            warn_lbl.setWordWrap(True)
            warn_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.video_canvas_layout.addWidget(warn_lbl)
            self.control_bar.hide()
            return

        self.player = QMediaPlayer(self)
        try:
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)
        except Exception:
            self.audio_output = None

        self.video_widget = QVideoWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.video_canvas_layout.addWidget(self.video_widget)
        self.player.setVideoOutput(self.video_widget)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self._poll_player_progress)

        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.video_widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if MULTIMEDIA_SUPPORTED and obj == self.video_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.frame.setFocus()
        return super().eventFilter(obj, event)

    def _on_player_error(self, error, error_string):
        if hasattr(self, "player") and self.player.source().isLocalFile():
            local_path = self.player.source().toLocalFile()
            self.status_message.emit("⚠️ 视频格式内嵌解码失败，正在尝试调起系统默认外置播放器...", 4000)
            try:
                import os
                os.startfile(local_path)
            except Exception as e:
                log_warning(f"External player launch failed: {e}")
        else:
            self.time_label.setText("❌ 播放出错")
            self.status_message.emit(
                f"⚠️ 视频播放异常: {error_string}. 检查网络或切换为缓存模式重试。", 5000
            )

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.poll_timer.start()
        else:
            self.poll_timer.stop()

    def _poll_player_progress(self):
        if not MULTIMEDIA_SUPPORTED or not self.player or self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        pos = self.player.position()
        dur = self.player.duration()
        if not self._is_dragging_slider:
            if self.progress_slider.maximum() != dur and dur > 0:
                self.progress_slider.setRange(0, dur)
                self.timeline_ticks.set_duration(dur)
            self.progress_slider.setValue(pos)
        self._update_time_label(pos, dur)

    def _on_slider_pressed(self):
        self._is_dragging_slider = True

    def _on_slider_released(self):
        self._is_dragging_slider = False
        self.player.setPosition(self.progress_slider.value())

    def _on_slider_moved(self, position: int):
        self._update_time_label(position, self.player.duration())

    def _on_volume_changed(self, value: int):
        if MULTIMEDIA_SUPPORTED and self.audio_output:
            self.audio_output.setVolume(value / 100.0)
            if value == 0:
                self.lbl_volume.setText("🔇")
            elif value < 40:
                self.lbl_volume.setText("🔈")
            else:
                self.lbl_volume.setText("🔊")

    def _update_time_label(self, current_ms: int, total_ms: int):
        if self.download_worker and getattr(self.download_worker, 'isRunning', lambda: False)():
            return
        def fmt(ms):
            seconds = (ms // 1000) % 60
            minutes = (ms // (1000 * 60)) % 60
            return f"{minutes:02d}:{seconds:02d}"
        self.time_label.setText(f"{fmt(current_ms)} / {fmt(total_ms)}")

    def load_video_url(self):
        if not MULTIMEDIA_SUPPORTED:
            return
        url_str = self.url_input.text().strip()
        if not url_str:
            return

        if app_config.get_video_playback_mode() == app_config.VIDEO_MODE_STREAM:
            self._play_stream_url(url_str)
            return

        if self.player:
            self.player.pause()
            self.btn_play_pause.setText("▶ 播放")

        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.progress_info.disconnect()
            self.download_worker.finished.disconnect()
            self.download_worker.error.disconnect()
            self.download_worker.cancel()
            self.download_worker.wait()

        url_hash = hashlib.sha256(url_str.encode("utf-8")).hexdigest()
        ext = ".mp4"
        if "/" in url_str:
            last_part = url_str.split("/")[-1]
            if "." in last_part:
                possible_ext = "." + last_part.split(".")[-1]
                if len(possible_ext) <= 5 and possible_ext.isalnum():
                    ext = possible_ext

        cache_dir = get_app_root() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_cache_path = cache_dir / f"{url_hash}{ext}"

        if local_cache_path.exists():
            self._play_local_video(str(local_cache_path.resolve()))
            return

        self.btn_load_video.setEnabled(False)
        self.btn_play_pause.setEnabled(False)
        self.progress_slider.setEnabled(False)
        self.time_label.setText("⏬ 缓存 0%...")

        self.download_worker = VideoDownloadWorker(url_str, local_cache_path)
        self.download_worker.progress_info.connect(self._on_cache_progress)
        self.download_worker.finished.connect(self._on_cache_finished)
        self.download_worker.error.connect(self._on_cache_error)
        self.download_worker.start()

    def _on_cache_progress(self, percent, speed_mbs, total_mb, downloaded_mb=0.0):
        if percent >= 0:
            self.time_label.setText(f"⏬ {percent}% ({speed_mbs:.1f}M/s) / 共 {total_mb:.1f}M")
        else:
            self.time_label.setText(f"⏬ {total_mb:.1f}M ({speed_mbs:.1f}M/s)")

    def _on_cache_finished(self, local_path_str):
        self.btn_load_video.setEnabled(True)
        self._play_local_video(local_path_str)
        self.status_message.emit("🎉 视频缓存下载成功！已开启离线高滑度播放。", 4000)

    def _on_cache_error(self, err_msg):
        self.btn_load_video.setEnabled(True)
        self.time_label.setText("缓存失败")
        self.status_message.emit(f"❌ 下载故障: {err_msg}", 5000)

    def _play_local_video(self, local_path_str):
        self.player.stop()
        self.player.setVideoOutput(None)
        QApplication.processEvents()
        self.player.setVideoOutput(self.video_widget)
        self.video_widget.update()
        QTimer.singleShot(100, lambda: self._apply_source(local_path_str))

    def _apply_source(self, local_path_str):
        try:
            self.player.setSource(QUrl.fromLocalFile(local_path_str))
            self.btn_play_pause.setEnabled(True)
            self.btn_popup_play.setEnabled(True)
            self.btn_play_pause.setText("▶ 播放")
            self.progress_slider.setEnabled(True)
            self.timeline_ticks.set_duration(self.player.duration())
            self.video_widget.update()
            self.frame.setFocus()
        except Exception as e:
            log_error(f"Failed to set video source: {e}")

    def toggle_playback(self):
        if not MULTIMEDIA_SUPPORTED:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play_pause.setText("▶ 播放")
        else:
            self.player.play()
            self.btn_play_pause.setText("⏸ 暂停")

    def seek_offset(self, ms_offset: int):
        new_pos = self.player.position() + ms_offset
        duration = self.player.duration()
        if new_pos < 0:
            new_pos = 0
        elif duration > 0 and new_pos > duration:
            new_pos = duration
        self.player.setPosition(new_pos)
        self.progress_slider.setValue(new_pos)

    def adjust_volume_offset(self, vol_offset: int):
        current = self.volume_slider.value()
        new = max(0, min(100, current + vol_offset))
        self.volume_slider.setValue(new)

    def jump_to_timestamp(self):
        raw_text = self.timestamp_input.text().strip()
        if not raw_text or not MULTIMEDIA_SUPPORTED:
            return
        try:
            parts = re.split(r'[:\.]', raw_text)
            ms = 0
            if len(parts) == 3:
                total_seconds = int(parts[0]) * 60 + float(parts[1])
                ms = int(parts[2])
            elif len(parts) == 2:
                total_seconds = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                total_seconds = float(parts[0])
            elif len(parts) == 4:
                total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                ms = int(parts[3])
            else:
                raise ValueError()
            target_ms = int(total_seconds * 1000) + ms
            duration = self.player.duration()
            if target_ms < 0:
                target_ms = 0
            elif duration > 0 and target_ms > duration:
                target_ms = duration
            self.player.setPosition(target_ms)
            self.progress_slider.setValue(target_ms)
            self.player.play()
            self.btn_play_pause.setText("⏸ 暂停")
            self.frame.setFocus()
            self.timestamp_input.clearFocus()
        except Exception:
            pass  # Invalid timestamp format, silently ignore

    def set_stream_mode(self, enabled: bool = True):
        self._stream_mode = enabled
        self.btn_clear_cache.setVisible(not enabled)

    def _play_stream_url(self, url_str: str):
        """Play video directly from URL without caching (streaming mode)."""
        if self.player:
            self.player.stop()
            self.player.setVideoOutput(None)
        QApplication.processEvents()
        self.btn_play_pause.setEnabled(True)
        self.btn_popup_play.setEnabled(True)
        self.progress_slider.setEnabled(True)
        self.time_label.setText("🌐 直链播放中...")
        try:
            self.player.setSource(QUrl(url_str))
            self.player.setVideoOutput(self.video_widget)
            self.video_widget.update()
            self.frame.setFocus()
            dur = self.player.duration()
            if dur > 0:
                self.timeline_ticks.set_duration(dur)
        except Exception as e:
            log_error(f"Stream play setup failed: {e}")
            self.time_label.setText("❌ 直链播放失败")
            self.status_message.emit(
                "❌ 直链流播放失败，请检查网络连接或尝试切换为缓存模式。", 5000
            )

    def open_external_video_window(self):
        if not MULTIMEDIA_SUPPORTED or not self.player or not self.player.source().isValid():
            return
        pos = self.player.position()
        self.player.pause()
        if self.popup_window:
            self.popup_window.close()
        self.popup_window = ExternalVideoWindow(self.player, self)
        self.popup_window.show()
        self.player.setPosition(pos)
        self.player.play()
        self.btn_play_pause.setText("⏸ 暂停")

    def restore_video_to_embedded(self):
        if not MULTIMEDIA_SUPPORTED or not self.player:
            return
        pos = self.player.position()
        self.player.pause()
        self.player.setVideoOutput(self.video_widget)
        self.player.setPosition(pos)
        self.player.play()
        self.btn_play_pause.setText("⏸ 暂停")
        self.popup_window = None

    def load_video_from_clipboard(self):
        if not MULTIMEDIA_SUPPORTED:
            return
        text = QApplication.clipboard().text().strip()
        if text.startswith(("http://", "https://")) and any(ext in text.lower() for ext in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".3gp")):
            self.url_input.setText(text)
            self.load_video_url()
            self.clipboard_video_loaded.emit(text)

    def clear_local_cache(self):
        self.btn_clear_cache.setEnabled(False)
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.progress_info.disconnect()
            self.download_worker.finished.disconnect()
            self.download_worker.error.disconnect()
            self.download_worker.cancel()
            self.download_worker.wait()

        if MULTIMEDIA_SUPPORTED and self.player:
            self.player.stop()
            self.player.setSource(QUrl())
        QApplication.processEvents()

        cache_dir = get_app_root() / "cache"
        deleted_count = 0
        failed_count = 0
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                if item.is_file():
                    try:
                        item.unlink()
                        deleted_count += 1
                    except Exception as e:
                        log_warning(f"Cache file delete failed: {e}")
                        failed_count += 1

        self.btn_play_pause.setEnabled(False)
        self.btn_popup_play.setEnabled(False)
        self.btn_play_pause.setText("▶ 播放")
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.time_label.setText("00:00 / 00:00")
        self.timeline_ticks.set_duration(0)

        if failed_count > 0:
            self.status_message.emit(f"🧹 缓存清理完成，但有 {failed_count} 个文件正在被占用。", 4000)
        else:
            self.status_message.emit(f"🧹 成功清空本地离线视频缓存 (共 {deleted_count} 个文件)。", 4000)
        self.btn_clear_cache.setEnabled(True)

    def stop(self):
        if self.popup_window:
            self.popup_window.close()
        if MULTIMEDIA_SUPPORTED and self.player:
            self.player.stop()
