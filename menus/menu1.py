# -*- coding: utf-8 -*-
# 文件路径：menus/menu1.py
import hashlib
import urllib.request
import time
import threading
from pathlib import Path
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser, QPushButton, QLabel, QFrame, QListWidget, QWidget, QLineEdit, QSlider, QScrollArea, QGridLayout, QApplication, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QPointF, QEvent
from PyQt6.QtGui import QPainter, QColor, QPen
from .base_menu import BaseMenuWidget
from engine.rule_engine import RuleContext

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_SUPPORTED = True
except ImportError:
    MULTIMEDIA_SUPPORTED = False

def get_root_path():
    """
    自适应获取物理根目录。
    * 完美解决打包后由于临时目录释放导致的寻址错误和视频下载缓存失败
    """
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parents[1]


class FocusFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

class TimelineTicks(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.duration_ms = 0
    def set_duration(self, duration_ms: int):
        self.duration_ms = duration_ms
        self.update()
    def paintEvent(self, event):
        if self.duration_ms <= 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#27272a"), 1))
        painter.drawLine(0, 1, self.width(), 1)
        one_minute = 60000
        num_ticks = int(self.duration_ms / one_minute)
        painter.setPen(QPen(QColor("#52525b"), 1))
        for i in range(1, num_ticks + 1):
            x = int(((i * one_minute) / self.duration_ms) * self.width())
            painter.drawLine(x, 1, x, 6)
            if num_ticks <= 15:
                font = painter.font()
                font.setPointSize(7)
                painter.setFont(font)
                painter.setPen(QPen(QColor("#71717a")))
                painter.drawText(x - 6, 12, f"{i}m")

class CapsuleButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("CapsuleBtn")
        self.original_text = text
        self.clicked.connect(self.trigger_copied_effect)
    def trigger_copied_effect(self):
        self.setText("✓ 已复制")
        self.setStyleSheet("QPushButton#CapsuleBtn { background-color: #059669; color: #ffffff; border: 1px solid #34d399; font-weight: bold; }")
        QTimer.singleShot(800, self.restore_state)
    def restore_state(self):
        self.setText(self.original_text)
        self.setStyleSheet("")

class ChunkDownloader(threading.Thread):
    def __init__(self, url, start_byte, end_byte, part_path):
        super().__init__()
        self.url, self.start_byte, self.end_byte, self.part_path = url, start_byte, end_byte, part_path
        self.downloaded, self.error, self.is_cancelled = 0, None, False
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Range": f"bytes={self.start_byte}-{self.end_byte}"})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.getcode() != 206: raise Exception("服务器拒绝了分片 Range 请求")
                block_size = 256 * 1024  
                with open(self.part_path, "wb") as f:
                    while not self.is_cancelled:
                        chunk = response.read(block_size)
                        if not chunk: break
                        f.write(chunk)
                        self.downloaded += len(chunk)
        except Exception as e: self.error = str(e)

class VideoDownloadWorker(QThread):
    progress_info = pyqtSignal(int, float, float, float)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, url: str, target_file_path: Path):
        super().__init__()
        self.url, self.target_file_path = url, target_file_path
        self.is_cancelled, self.num_threads, self.max_retries = False, 4, 3
    def cancel(self): self.is_cancelled = True
    def calculate_optimal_chunks(self, total_size_bytes: int) -> int:
        mb = 1024 * 1024
        if total_size_bytes < 5 * mb: return 1   
        elif total_size_bytes < 20 * mb: return 2   
        elif total_size_bytes < 50 * mb: return 4   
        elif total_size_bytes < 100 * mb: return 6   
        else: return 8   
    def run(self):
        retries = 0
        while retries <= self.max_retries and not self.is_cancelled:
            try:
                req = urllib.request.Request(self.url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                supports_range = False
                total_size = -1
                try:
                    with urllib.request.urlopen(req, timeout=8) as response:
                        accept_ranges = response.info().get('Accept-Ranges', '')
                        total_size = int(response.info().get('Content-Length')) if response.info().get('Content-Length') is not None else -1
                        supports_range = (accept_ranges.lower() == 'bytes')
                except Exception:
                    req_get = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
                    try:
                        with urllib.request.urlopen(req_get, timeout=8) as response_get:
                            supports_range = (response_get.getcode() == 206)
                            content_range = response_get.info().get('Content-Range', '')
                            if "/" in content_range: total_size = int(content_range.split("/")[-1])
                    except: pass
                if supports_range and total_size > 4 * 1024 * 1024:
                    self.num_threads = self.calculate_optimal_chunks(total_size)
                    self.execute_multi_threaded_download(total_size)
                else: self.execute_single_threaded_download()
                return
            except Exception as e:
                retries += 1
                if retries > self.max_retries or self.is_cancelled:
                    if self.target_file_path.exists():
                        try: self.target_file_path.unlink()
                        except: pass
                    self.error.emit(f"下载失败: {e}")
                    return
                else: self.msleep(2000)
    def execute_multi_threaded_download(self, total_size: int):
        chunk_size = total_size // self.num_threads
        threads, part_paths = [], []
        start_time = time.time()
        last_emit_time = 0.0
        for i in range(self.num_threads):
            start_byte = i * chunk_size
            end_byte = total_size - 1 if i == self.num_threads - 1 else (start_byte + chunk_size - 1)
            part_path = self.target_file_path.with_suffix(f"{self.target_file_path.suffix}.part{i}")
            part_paths.append(part_path)
            t = ChunkDownloader(self.url, start_byte, end_byte, part_path)
            threads.append(t)
            t.start()
        while any(t.is_alive() for t in threads) and not self.is_cancelled:
            current_time = time.time()
            if current_time - last_emit_time > 0.15:
                last_emit_time = current_time
                dl = sum(t.downloaded for t in threads)
                speed_mbs = (dl / (current_time - start_time)) / (1024 * 1024) if current_time - start_time > 0 else 0.0
                percent = int((dl * 100) / total_size)
                if percent >= 100: percent = 99
                self.progress_info.emit(percent, speed_mbs, total_size / (1024 * 1024), dl / (1024 * 1024))
            self.msleep(100)
        if self.is_cancelled:
            for t in threads: t.is_cancelled = True
            for t in threads: t.join()
            for path in part_paths:
                if path.exists():
                    try: path.unlink()
                    except: pass
            return
        for t in threads:
            t.join()
            if t.error:
                for path in part_paths:
                    if path.exists():
                        try: path.unlink()
                        except: pass
                raise Exception(f"分片下载中断: {t.error}")
        elapsed_total = time.time() - start_time
        self.progress_info.emit(100, (total_size / elapsed_total) / (1024 * 1024) if elapsed_total > 0 else 0.0, total_size / (1024 * 1024), total_size / (1024 * 1024))
        try:
            with open(self.target_file_path, "wb") as dest:
                for path in part_paths:
                    with open(path, "rb") as src:
                        while True:
                            buf = src.read(1024 * 1024)
                            if not buf: break
                            dest.write(buf)
                    path.unlink() 
            self.finished.emit(str(self.target_file_path.resolve()))
        except Exception as e: raise Exception(f"分片合并失败: {e}")
    def execute_single_threaded_download(self):
        bytes_downloaded = 0
        req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        start_time = time.time()
        last_emit_time = 0.0
        with urllib.request.urlopen(req, timeout=10) as response:
            total_size = int(response.info().get('Content-Length')) if response.info().get('Content-Length') is not None else -1
            total_size_mb = total_size / (1024 * 1024) if total_size > 0 else 0.0
            block_size = 256 * 1024
            with open(self.target_file_path, "wb") as f:
                while not self.is_cancelled:
                    chunk = response.read(block_size)
                    if not chunk: break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    current_time = time.time()
                    if (current_time - last_emit_time > 0.15) or (total_size > 0 and bytes_downloaded >= total_size):
                        last_emit_time = current_time
                        speed_mbs = (bytes_downloaded / (current_time - start_time)) / (1024.0 * 1024.0) if current_time - start_time > 0 else 0.0
                        downloaded_mb = bytes_downloaded / (1024.0 * 1024.0)
                        if total_size > 0:
                            self.progress_info.emit(int((bytes_downloaded * 100) / total_size), speed_mbs, total_size_mb, downloaded_mb)
                        else:
                            self.progress_info.emit(-1, speed_mbs, downloaded_mb, downloaded_mb)
        if not self.is_cancelled:
            self.progress_info.emit(100, (bytes_downloaded / (time.time() - start_time)) / (1024 * 1024), total_size_mb, total_size_mb)
            self.finished.emit(str(self.target_file_path.resolve()))

class TranslateWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, engine, text: str, engine_mode: str):
        super().__init__()
        self.engine, self.text, self.engine_mode = engine, text, engine_mode
    def run(self):
        try:
            from engine.rules import TextCleanupRule, ActualTranslationRule
            self.engine.clear_rules()
            self.engine.register_rule(TextCleanupRule())
            self.engine.register_rule(ActualTranslationRule())
            context = RuleContext(raw_source=self.text)
            context.metadata["mode"] = "en_to_zh"
            context.metadata["engine"] = self.engine_mode
            res = self.engine.run(context)
            self.finished.emit(res.raw_target)
        except Exception as e: self.error.emit(str(e))

class FormatWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, engine, source_text: str, engine_mode: str):
        super().__init__()
        self.engine, self.source_text, self.engine_mode = engine, source_text, engine_mode
    def run(self):
        try:
            from engine.rules import VideoTimelineParseRule, TextCleanupRule
            self.engine.clear_rules()
            self.engine.register_rule(VideoTimelineParseRule())
            self.engine.register_rule(TextCleanupRule())
            context = RuleContext(raw_source=self.source_text)
            context.metadata["engine"] = self.engine_mode
            result = self.engine.run(context)
            self.finished.emit(result)
        except Exception as e: self.error.emit(str(e))

class ModelDetectWorker(QThread):
    finished_detect = pyqtSignal(list)
    
    def run(self):
        offline_items = []
        try:
            # 【核心优化】：使用无代理 Opener 快速探测，保障视频高速下载通道不会因为代理冲突锁死在 0%
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with opener.open(req, timeout=1.0) as response:
                if response.status == 200:
                    offline_items.append("🤖 Ollama (本地大模型)")
        except: pass

        models_dir = get_root_path() / "models"
        if (models_dir / "opus-mt-en-zh").exists():
            offline_items.append("📦 MarianMT (本地小模型)")
        if len(list(models_dir.glob("translate-en_zh-*.argosmodel"))) > 0:
            offline_items.append("📦 Argos NMT (本地轻量级)")

        if offline_items:
            self.finished_detect.emit(offline_items)

class MenuWidget(BaseMenuWidget):
    def init_ui(self):
        # 极简样式表高度融合
        self.setStyleSheet("""
            QFrame#SectionFrame, QFrame#VideoFrame, QFrame#SubLeftFrame { background-color: #161619; border: 1px solid #27272a; border-radius: 8px; padding: 10px; }
            QFrame#VideoFrame:focus { border: 1px solid #3b82f6; }
            QLabel#SectionHeader { color: #e4e4e7; font-weight: bold; font-size: 13px; }
            QTextEdit, QTextBrowser, QLineEdit, QComboBox, QListWidget { background-color: #121214; color: #e4e4e7; border: 1px solid #27272a; border-radius: 6px; padding: 8px; font-size: 12px; }
            QTextEdit, QTextBrowser { font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; padding: 10px; }
            QTextEdit:focus, QLineEdit:focus, QTextBrowser:focus { border: 1px solid #3b82f6; }
            QLineEdit#UrlInput { font-family: monospace; }
            QComboBox { height: 34px; font-size: 11px; font-weight: bold; background-color: #1c1c1f; }
            QComboBox::drop-down { border: none; width: 15px; }
            QComboBox QAbstractItemView { background-color: #1c1c1f; color: #e4e4e7; selection-background-color: #1e3a8a; selection-color: #60a5fa; border: 1px solid #27272a; }
            QPushButton { color: white; font-weight: bold; border-radius: 6px; height: 34px; font-size: 12px; border: none; }
            QPushButton#OnlineBtn { background-color: #2563eb; }
            QPushButton#OnlineBtn:hover { background-color: #1d4ed8; }
            QPushButton#OfflineBtn { background-color: #0d9488; }
            QPushButton#OfflineBtn:hover { background-color: #0f766e; }
            QPushButton#PlayerBtn { background-color: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; height: 28px; }
            QPushButton#PlayerBtn:hover { background-color: #3f3f46; }
            QPushButton#PlayerBtn:disabled { background-color: #121214; color: #52525b; border: 1px solid #27272a; }
            QPushButton#ClipBtn { background-color: #1e1b4b; color: #c084fc; border: 1px solid #4338ca; }
            QPushButton#ClipBtn:hover { background-color: #312e81; color: #e9d5ff; }
            QPushButton#AbortBtn { background-color: #3f3f46; color: #e4e4e7; border: 1px solid #52525b; }
            QPushButton#AbortBtn:hover { background-color: #ef4444; color: white; border-color: #ef4444; }
            QPushButton#AbortBtn:disabled { background-color: #121214; color: #52525b; border: 1px solid #27272a; }
            QPushButton#CapsuleBtn { background-color: #1c1c1f; color: #d4d4d8; border: 1px solid #27272a; border-radius: 12px; padding: 4px 12px; font-size: 11px; height: 24px; font-weight: 500; }
            QPushButton#CapsuleBtn:hover { background-color: #27272a; border-color: #3f3f46; color: #ffffff; }
            QListWidget { padding: 2px; }
            QListWidget::item { padding: 4px 12px; margin-right: 6px; border: 1px solid #27272a; border-radius: 4px; background-color: #18181b; color: #a1a1aa; font-weight: bold; font-size: 11px; }
            QListWidget::item:hover { background-color: #27272a; color: #ffffff; }
            QListWidget::item:selected { background-color: #1e3a8a; color: #60a5fa; font-weight: bold; border: 1px solid #3b82f6; }
        """)

        self._is_dragging_slider = False
        main_horizontal_layout = QHBoxLayout(self)
        main_horizontal_layout.setContentsMargins(6, 6, 6, 6)
        main_horizontal_layout.setSpacing(10)

        left_main_widget = QWidget(self)
        left_main_layout = QVBoxLayout(left_main_widget)
        left_main_layout.setContentsMargins(0, 0, 0, 0)
        left_main_layout.setSpacing(10)

        self.video_frame = FocusFrame(self)
        self.video_frame.setObjectName("VideoFrame")
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(8, 8, 8, 8)
        video_layout.setSpacing(8)
        video_layout.addWidget(QLabel("📹 视频播放控制", self, objectName="SectionHeader"))

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
        video_layout.addLayout(url_layout)

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
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
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
        self.init_multimedia_engine()

        video_layout.addWidget(self.video_canvas_container, stretch=1)
        video_layout.addWidget(self.control_bar)
        left_main_layout.addWidget(self.video_frame, stretch=3)

        self.phrase_frame = QFrame(self)
        self.phrase_frame.setObjectName("SubLeftFrame")
        phrase_layout = QVBoxLayout(self.phrase_frame)
        phrase_layout.setContentsMargins(8, 8, 8, 8)
        phrase_layout.setSpacing(6)
        phrase_layout.addWidget(QLabel("📋 便捷短语复制 (words.txt)", self, objectName="SectionHeader"))

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QScrollBar:vertical { border: none; background-color: #121214; width: 6px; border-radius: 3px; } QScrollBar::handle:vertical { background-color: #27272a; border-radius: 3px; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setContentsMargins(0, 0, 5, 0)
        self.grid_layout.setSpacing(6)
        self.load_words_config()
        scroll_area.setWidget(scroll_content)
        phrase_layout.addWidget(scroll_area)

        left_main_layout.addWidget(self.phrase_frame, stretch=2)
        main_horizontal_layout.addWidget(left_main_widget, stretch=45)

        # ================== 右侧对照面板 ==================
        right_main_widget = QWidget(self)
        right_main_layout = QVBoxLayout(right_main_widget)
        right_main_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.setSpacing(10)

        self.upper_frame = QFrame(self)
        self.upper_frame.setObjectName("SectionFrame")
        upper_layout = QVBoxLayout(self.upper_frame)
        upper_layout.setContentsMargins(8, 8, 8, 8)
        upper_layout.setSpacing(8)
        upper_layout.addWidget(QLabel("🗣️ 1. 在线双路并行对照翻译", self, objectName="SectionHeader"))

        translate_columns = QHBoxLayout()
        translate_columns.setSpacing(8)
        self.input_a = QTextEdit(self)
        self.input_a.setPlaceholderText("在此输入英文原始文本段落...")
        self.input_a.setCursor(Qt.CursorShape.IBeamCursor)
        translate_columns.addWidget(self.input_a, stretch=45)

        self.output_a = QTextEdit(self)
        self.output_a.setReadOnly(True)
        self.output_a.setPlaceholderText("等待引擎翻译对照输出...")
        self.output_a.setCursor(Qt.CursorShape.IBeamCursor)
        translate_columns.addWidget(self.output_a, stretch=55)
        upper_layout.addLayout(translate_columns)

        online_actions_layout = QHBoxLayout()
        online_actions_layout.setSpacing(8)
        
        # 下拉切换菜单 (加宽，防字符截断)
        self.combo_mode_upper = QComboBox(self)
        self.combo_mode_upper.setMinimumWidth(210)
        # 【新增】：强制物理高度锁死为 34px，与右侧 QPushButton 绝对对齐
        self.combo_mode_upper.setFixedHeight(34)
        online_actions_layout.addWidget(self.combo_mode_upper)

        self.btn_online = QPushButton("🚀 运行双通道翻译", self)
        self.btn_online.setObjectName("OnlineBtn")
        self.btn_online.setMinimumWidth(140)
        self.btn_online.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_online.clicked.connect(self.start_online_translation)
        online_actions_layout.addWidget(self.btn_online, stretch=3)

        self.btn_abort_upper = QPushButton("⏹ 中止", self)
        self.btn_abort_upper.setObjectName("AbortBtn")
        self.btn_abort_upper.setFixedWidth(50)
        self.btn_abort_upper.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort_upper.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_abort_upper.clicked.connect(self.abort_upper_translation)
        self.btn_abort_upper.setEnabled(False)  
        online_actions_layout.addWidget(self.btn_abort_upper)

        self.btn_clip_online = QPushButton("📋 读剪切板翻译", self)
        self.btn_clip_online.setObjectName("ClipBtn")
        self.btn_clip_online.setMinimumWidth(110)
        self.btn_clip_online.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip_online.clicked.connect(self.translate_clipboard_online)
        online_actions_layout.addWidget(self.btn_clip_online, stretch=1)
        upper_layout.addLayout(online_actions_layout)
        right_main_layout.addWidget(self.upper_frame, stretch=2)

        self.lower_frame = QFrame(self)
        self.lower_frame.setObjectName("SectionFrame")
        lower_layout = QVBoxLayout(self.lower_frame)
        lower_layout.setContentsMargins(8, 8, 8, 8)
        lower_layout.setSpacing(8)
        lower_layout.addWidget(QLabel("🧬 2. 事件节点格式优化与离线解析", self, objectName="SectionHeader"))

        format_columns = QHBoxLayout()
        format_columns.setSpacing(8)
        self.src_input = QTextEdit(self)
        self.src_input.setPlaceholderText("在此粘贴多模态分析 JSON 数组原始文本...")
        self.src_input.setCursor(Qt.CursorShape.IBeamCursor)
        format_columns.addWidget(self.src_input, stretch=45)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.list_widget = QListWidget(self)
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setFixedHeight(36)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.list_widget.currentRowChanged.connect(self.display_item_detail)
        right_layout.addWidget(self.list_widget)

        self.detail_display = QTextBrowser(self)
        self.detail_display.setCursor(Qt.CursorShape.ArrowCursor)
        self.detail_display.setOpenLinks(False)
        self.detail_display.anchorClicked.connect(self.handle_anchor_clicked)
        right_layout.addWidget(self.detail_display)

        format_columns.addWidget(right_container, stretch=55)
        lower_layout.addLayout(format_columns)

        offline_actions_layout = QHBoxLayout()
        offline_actions_layout.setSpacing(8)
        
        # 下拉切换菜单 (加宽，防字符截断)
        self.combo_mode_lower = QComboBox(self)
        self.combo_mode_lower.setMinimumWidth(210)
        # 【新增】：强制物理高度锁死为 34px，与右侧 QPushButton 绝对对齐
        self.combo_mode_lower.setFixedHeight(34)
        offline_actions_layout.addWidget(self.combo_mode_lower)

        self.btn_offline = QPushButton("⚡ 执行格式整理与解析", self)
        self.btn_offline.setObjectName("OfflineBtn")
        self.btn_offline.setMinimumWidth(140)
        self.btn_offline.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_offline.clicked.connect(self.start_offline_optimization)
        offline_actions_layout.addWidget(self.btn_offline, stretch=3)

        self.btn_abort_lower = QPushButton("⏹ 中止", self)
        self.btn_abort_lower.setObjectName("AbortBtn")
        self.btn_abort_lower.setFixedWidth(50)
        self.btn_abort_lower.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort_lower.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_abort_lower.clicked.connect(self.abort_lower_formatting)
        self.btn_abort_lower.setEnabled(False)  
        offline_actions_layout.addWidget(self.btn_abort_lower)

        self.btn_clip_offline = QPushButton("📋 读剪切板解析", self)
        self.btn_clip_offline.setObjectName("ClipBtn")
        self.btn_clip_offline.setMinimumWidth(110)
        self.btn_clip_offline.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip_offline.clicked.connect(self.format_clipboard_offline)
        offline_actions_layout.addWidget(self.btn_clip_offline, stretch=1)

        lower_layout.addLayout(offline_actions_layout)
        right_main_layout.addWidget(self.lower_frame, stretch=3)
        main_horizontal_layout.addWidget(right_main_widget, stretch=55)
        self.processed_items = []

        self.update_engine_combobox_labels()

    def update_engine_combobox_labels(self):
        """
        异步后台路由项加载，采用 Qt 标准线程通信，消除冷启动卡顿与静默失败。
        """
        routing_items = [
            "☁️ 在线优先 (自动降级)",
            "💻 本地优先 (自动降级)"
        ]
        self.combo_mode_upper.clear()
        self.combo_mode_upper.addItems(routing_items)
        self.combo_mode_lower.clear()
        self.combo_mode_lower.addItems(routing_items)

        # 启动合法 QThread 守护线程后台探测
        self.detect_worker = ModelDetectWorker(self)
        self.detect_worker.finished_detect.connect(self._apply_detected_models)
        self.detect_worker.start()

    def _apply_detected_models(self, offline_items):
        self.combo_mode_upper.addItems(offline_items)
        self.combo_mode_lower.addItems(offline_items)
        
        ollama_text = "🤖 Ollama (本地大模型)"
        idx = self.combo_mode_upper.findText(ollama_text)
        if idx != -1:
            self.combo_mode_upper.setCurrentIndex(idx)
            self.combo_mode_lower.setCurrentIndex(idx)


    def get_selected_engine_key(self, combobox: QComboBox) -> str:
        text = combobox.currentText()
        if "在线优先" in text: return "online_first"
        elif "本地优先" in text: return "local_first"
        elif "Ollama" in text: return "ollama"
        elif "MarianMT" in text: return "transformers"
        elif "Argos" in text: return "argos"
        return "online_first"

    def abort_upper_translation(self):
        if hasattr(self, "trans_worker") and self.trans_worker.isRunning():
            self.trans_worker.terminate()  
            self.trans_worker.wait()
            self._reset_upper_ui()
            mw = self.window()
            if mw and hasattr(mw, "status_bar"): mw.status_bar.showMessage("⏹ 在线翻译任务已由用户强行中止。", 3000)

    def _reset_upper_ui(self):
        self.btn_online.setEnabled(True)
        self.btn_online.setText("🚀 运行双通道翻译")
        self.btn_abort_upper.setEnabled(False)

    def abort_lower_formatting(self):
        if hasattr(self, "format_worker") and self.format_worker.isRunning():
            self.format_worker.terminate()
            self.format_worker.wait()
            self._reset_lower_ui()
            mw = self.window()
            if mw and hasattr(mw, "status_bar"): mw.status_bar.showMessage("⏹ 离线格式化解析任务已由用户强行中止。", 3000)

    def _reset_lower_ui(self):
        self.btn_offline.setEnabled(True)
        self.btn_offline.setText("⚡ 执行格式整理与解析")
        self.btn_abort_lower.setEnabled(False)

    def load_words_config(self):
        words_path = get_root_path() / "words.txt"
        phrases = []
        if words_path.exists():
            try:
                with open(words_path, "r", encoding="utf-8") as f:
                    phrases = [line.strip() for line in f if line.strip()]
            except Exception: pass
        else:
            phrases = [
                "在线大雄兔###https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "在线玩具世界###https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
                "极佳编辑###Brilliant editing", 
                "一键加速###Hurry up", 
                "Check this", 
                "Behind scenes"
            ]
            try:
                with open(words_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(phrases))
            except: pass

        cols = 2
        for idx, text in enumerate(phrases):
            row = idx // cols
            col = idx % cols
            if "###" in text:
                parts = text.split("###", 1)  
                title_part = parts[0].strip()
                copy_part = parts[1].strip()
                
                cell_widget = QWidget(self)
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(4)
                
                title_lbl = QLabel(title_part, self)
                title_lbl.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold;")
                
                btn = CapsuleButton(copy_part, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda checked, t=copy_part: self.copy_phrase_to_clipboard(t))
                
                cell_layout.addWidget(title_lbl)
                cell_layout.addWidget(btn, stretch=1)
                self.grid_layout.addWidget(cell_widget, row, col)
            else:
                btn = CapsuleButton(text, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda checked, t=text: self.copy_phrase_to_clipboard(t))
                self.grid_layout.addWidget(btn, row, col)

    def copy_phrase_to_clipboard(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        mw = self.window()
        if mw and hasattr(mw, "status_bar"):
            mw.status_bar.showMessage(f"📋 短语已成功复制到剪切板: \"{text}\"", 2000)

    def init_multimedia_engine(self):
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
        self.poll_timer.timeout.connect(self.poll_player_progress)

        self.player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.player.errorOccurred.connect(self.on_player_error)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.video_widget.installEventFilter(self)

    def on_player_error(self, error, error_string):
        if hasattr(self, "player") and self.player.source().isLocalFile():
            local_path = self.player.source().toLocalFile()
            mw = self.window()
            if mw and hasattr(mw, "status_bar"):
                mw.status_bar.showMessage(f"⚠️ 视频格式内嵌解码失败，正在尝试调起系统默认外置播放器...", 4000)
            try:
                import os
                os.startfile(local_path)
            except Exception: pass

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.poll_timer.start()
        else:
            self.poll_timer.stop()

    def poll_player_progress(self):
        if not MULTIMEDIA_SUPPORTED or not hasattr(self, "player") or self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        pos = self.player.position()
        dur = self.player.duration()
        if not self._is_dragging_slider:
            if self.progress_slider.maximum() != dur and dur > 0:
                self.progress_slider.setRange(0, dur)
                self.timeline_ticks.set_duration(dur)
            self.progress_slider.setValue(pos)
        self.update_play_timer_label(pos, dur)

    def eventFilter(self, obj, event):
        if MULTIMEDIA_SUPPORTED and obj == self.video_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.video_frame.setFocus()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if not MULTIMEDIA_SUPPORTED or not self.video_frame.hasFocus():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.toggle_playback()
            event.accept()
        elif key == Qt.Key.Key_Left:
            self.seek_offset(-5000)
            event.accept()
        elif key == Qt.Key.Key_Right:
            self.seek_offset(5000)
            event.accept()
        elif key == Qt.Key.Key_Up:
            self.adjust_volume_offset(5)
            event.accept()
        elif key == Qt.Key.Key_Down:
            self.adjust_volume_offset(-5)
            event.accept()
        else:
            super().keyPressEvent(event)

    def seek_offset(self, ms_offset: int):
        new_pos = self.player.position() + ms_offset
        duration = self.player.duration()
        if new_pos < 0: new_pos = 0
        elif duration > 0 and new_pos > duration: new_pos = duration
        self.player.setPosition(new_pos)
        self.progress_slider.setValue(new_pos)

    def adjust_volume_offset(self, vol_offset: int):
        current_vol = self.volume_slider.value()
        new_vol = current_vol + vol_offset
        if new_vol < 0: new_vol = 0
        elif new_vol > 100: new_vol = 100
        self.volume_slider.setValue(new_vol)

    def load_video_from_clipboard(self):
        if not MULTIMEDIA_SUPPORTED: return
        text = QApplication.clipboard().text().strip()
        if text.startswith(("http://", "https://")) and any(ext in text.lower() for ext in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".3gp")):
            self.url_input.setText(text)
            self.load_video_url()
            mw = self.window()
            if mw and hasattr(mw, "status_bar"): mw.status_bar.showMessage("🎬 成功从剪切板载入视频！", 3000)

    def translate_clipboard_online(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.input_a.setPlainText(text)
            self.start_online_translation()

    def format_clipboard_offline(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.src_input.setPlainText(text)
            self.start_offline_optimization()

    def on_volume_changed(self, value: int):
        if MULTIMEDIA_SUPPORTED and hasattr(self, "audio_output"):
            self.audio_output.setVolume(value / 100.0)
            if value == 0: self.lbl_volume.setText("🔇")
            elif value < 40: self.lbl_volume.setText("🔈")
            else: self.lbl_volume.setText("🔊")

    def jump_to_timestamp(self):
        raw_text = self.timestamp_input.text().strip()
        if not raw_text or not MULTIMEDIA_SUPPORTED: return
        try:
            import re
            parts = re.split(r'[:\.]', raw_text)
            ms = 0

            # 严格根据冒号/点号的切割数量来重置逻辑
            if len(parts) == 3:
                # 三段式：强制识别为 分:秒:毫秒 (例如 00:01:15 -> 0分 1秒 15毫秒)
                total_seconds = int(parts[0]) * 60 + float(parts[1])
                ms = int(parts[2])
            elif len(parts) == 2:
                # 两段式：分:秒
                total_seconds = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                # 一段式：总秒数
                total_seconds = float(parts[0])
            elif len(parts) == 4:
                # 四段式：时:分:秒:毫秒
                total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                ms = int(parts[3])
            else:
                raise ValueError()
            
            target_ms = int(total_seconds * 1000) + ms
            
            duration = self.player.duration()
            if target_ms < 0: target_ms = 0
            elif duration > 0 and target_ms > duration: target_ms = duration
            
            self.player.setPosition(target_ms)
            self.progress_slider.setValue(target_ms)
            self.video_frame.setFocus()
            self.timestamp_input.clearFocus()
        except Exception:
            pass

    def handle_anchor_clicked(self, qurl: QUrl):
        url_str = qurl.toString()
        if url_str.startswith("jump:"):
            raw_timestamp = url_str.split("jump:")[1]
            start_time = raw_timestamp.split("-")[0].strip() if "-" in raw_timestamp else raw_timestamp.strip()
            self.timestamp_input.setText(start_time)
            self.jump_to_timestamp()

    def clear_local_cache(self):
        """
        【彻底修复】：防连点卡退，并安全终止进行中的下载任务与文件锁
        """
        self.btn_clear_cache.setEnabled(False) # 立即锁死按键，防连点崩溃

        # 1. 如果正在下载，必须先优雅取消并强制等待线程销毁，防止文件流死锁
        if hasattr(self, "download_worker") and self.download_worker.isRunning():
            self.download_worker.progress_info.disconnect()
            self.download_worker.finished.disconnect()
            self.download_worker.error.disconnect()
            self.download_worker.cancel()  
            self.download_worker.wait()    

        # 2. 释放播放器文件句柄
        if MULTIMEDIA_SUPPORTED and hasattr(self, "player"):
            self.player.stop()
            self.player.setSource(QUrl())
        QApplication.processEvents()

        # 3. 执行物理文件清理
        cache_dir = get_root_path() / "cache"
        deleted_count = 0
        failed_count = 0
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                if item.is_file():
                    try: 
                        item.unlink()
                        deleted_count += 1
                    except Exception as e: 
                        import logging
                        logging.warning(f"缓存文件删除失败: {e}")
                        failed_count += 1

        # 4. 重置 UI 状态
        self.btn_play_pause.setEnabled(False)
        self.btn_play_pause.setText("▶ 播放")
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.time_label.setText("00:00 / 00:00")
        self.timeline_ticks.set_duration(0)
        
        mw = self.window()
        if mw and hasattr(mw, "status_bar"): 
            if failed_count > 0:
                mw.status_bar.showMessage(f"🧹 缓存清理完成，但有 {failed_count} 个文件正在被占用。", 4000)
            else:
                mw.status_bar.showMessage(f"🧹 成功清空本地离线视频缓存 (共 {deleted_count} 个文件)。", 4000)
                
        self.btn_clear_cache.setEnabled(True) # 清理完毕，恢复按键

    # ========================== 物理进度绑定槽 ==========================
    def on_video_position_changed(self, position: int):
        if not self._is_dragging_slider:
            self.progress_slider.setValue(position)
        self.update_play_timer_label(position, self.player.duration())

    def on_video_duration_changed(self, duration: int):
        self.progress_slider.setRange(0, duration)
        self.timeline_ticks.set_duration(duration)
        self.update_play_timer_label(self.player.position(), duration)

    def on_slider_pressed(self):
        self._is_dragging_slider = True

    def on_slider_released(self):
        self._is_dragging_slider = False
        self.player.setPosition(self.progress_slider.value())

    def on_slider_moved(self, position: int):
        self.update_play_timer_label(position, self.player.duration())

    # ========================== 极速合并下载流程 ==========================
    def load_video_url(self):
        if not MULTIMEDIA_SUPPORTED: return
        url_str = self.url_input.text().strip()
        if not url_str: return
        
        if hasattr(self, "download_worker") and self.download_worker.isRunning():
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
                if len(possible_ext) <= 5 and possible_ext.isalnum(): ext = possible_ext

        cache_dir = get_root_path() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_cache_path = cache_dir / f"{url_hash}{ext}"

        if local_cache_path.exists():
            self.play_local_video(str(local_cache_path.resolve()))
            return

        self.btn_load_video.setEnabled(False)
        self.btn_play_pause.setEnabled(False)
        self.progress_slider.setEnabled(False)
        self.time_label.setText("⏬ 缓存 0%...")
        
        self.download_worker = VideoDownloadWorker(url_str, local_cache_path)
        self.download_worker.progress_info.connect(self.on_cache_progress)
        self.download_worker.finished.connect(self.on_cache_finished)
        self.download_worker.error.connect(self.on_cache_error)
        self.download_worker.start()

    def on_cache_progress(self, percent: int, speed_mbs: float, total_mb: float, downloaded_mb: float = 0.0):
        if percent >= 0:
            self.time_label.setText(f"⏬ {percent}% ({speed_mbs:.1f}M/s) / 共 {total_mb:.1f}M")
        else:
            self.time_label.setText(f"⏬ {total_mb:.1f}M ({speed_mbs:.1f}M/s)")

    def on_cache_finished(self, local_path_str: str):
        self.btn_load_video.setEnabled(True)
        self.play_local_video(local_path_str)
        mw = self.window()
        if mw and hasattr(mw, "status_bar"): mw.status_bar.showMessage("🎉 视频缓存下载成功！已开启离线高滑度播放。", 4000)

    def on_cache_error(self, err_msg: str):
        self.btn_load_video.setEnabled(True)
        self.time_label.setText("缓存失败")
        mw = self.window()
        if mw and hasattr(mw, "status_bar"): mw.status_bar.showMessage(f"❌ 下载故障: {err_msg}", 5000)

    def play_local_video(self, local_path_str: str):
        self.player.stop()
        QApplication.processEvents()
        QTimer.singleShot(100, lambda: self._apply_local_video_source(local_path_str))

    def _apply_local_video_source(self, local_path_str: str):
        try:
            self.player.setSource(QUrl.fromLocalFile(local_path_str))
            self.btn_play_pause.setEnabled(True)
            self.btn_play_pause.setText("▶ 播放")
            self.progress_slider.setEnabled(True)
            self.timeline_ticks.set_duration(self.player.duration())
            self.video_frame.setFocus()
        except Exception: pass

    def toggle_playback(self):
        if not MULTIMEDIA_SUPPORTED: return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play_pause.setText("▶ 播放")
        else:
            self.player.play()
            self.btn_play_pause.setText("⏸ 暂停")

    def update_play_timer_label(self, current_ms: int, total_ms: int):
        if hasattr(self, "download_worker") and self.download_worker.isRunning():
            return
            
        def parse_ms_to_str(ms: int) -> str:
            seconds = (ms // 1000) % 60
            minutes = (ms // (1000 * 60)) % 60
            return f"{minutes:02d}:{seconds:02d}"
        self.time_label.setText(f"{parse_ms_to_str(current_ms)} / {parse_ms_to_str(total_ms)}")

    def on_unload(self):
        if MULTIMEDIA_SUPPORTED and hasattr(self, "player"):
            self.player.stop()

    # ========================== 翻译异步控制 ==========================
    def start_online_translation(self):
        text = self.input_a.toPlainText().strip()
        if not text: return
        self.btn_online.setEnabled(False)
        self.btn_online.setText("⏳ 正在翻译中...")
        self.btn_abort_upper.setEnabled(True)  
        
        engine_mode = self.get_selected_engine_key(self.combo_mode_upper)
        self.trans_worker = TranslateWorker(self.engine, text, engine_mode)
        self.trans_worker.finished.connect(self.on_online_finished)
        self.trans_worker.error.connect(self.on_online_error)
        self.trans_worker.start()

    def on_online_finished(self, result_text):
        self.output_a.setPlainText(result_text)
        self._reset_upper_ui()

    def on_online_error(self, err):
        self.output_a.setPlainText(f"[系统级请求故障]: {err}")
        self._reset_upper_ui()

    def start_offline_optimization(self):
        src_text = self.src_input.toPlainText().strip()
        if not src_text: return
        self.btn_offline.setEnabled(False)
        self.btn_offline.setText("⏳ 正在解析中...")
        self.btn_abort_lower.setEnabled(True)  
        
        engine_mode = self.get_selected_engine_key(self.combo_mode_lower)
        self.format_worker = FormatWorker(self.engine, source_text=src_text, engine_mode=engine_mode)
        self.format_worker.finished.connect(self.on_offline_finished)
        self.format_worker.error.connect(self.on_offline_error)
        self.format_worker.start()

    def on_offline_finished(self, result_context):
        self.list_widget.clear()
        self.detail_display.clear()
        is_timeline = result_context.metadata.get("is_timeline", False)
        if is_timeline:
            self.processed_items = result_context.metadata.get("timeline_processed", [])
            for item in self.processed_items:
                self.list_widget.addItem(f"{item['step_id']}")
            if self.processed_items:
                self.list_widget.setCurrentRow(0)
        else:
            self.processed_items = []
            for idx, para in enumerate(result_context.processed_source_segments):
                self.list_widget.addItem(f"para_{idx+1}")
                self.processed_items.append({"step_id": "N/A", "segment_id": f"para_{idx+1}", "modality": "TEXT", "timestamp": "N/A", "content": para, "content_local_zh": "（暂不支持）", "bridge": "无逻辑说明", "bridge_local_zh": "（暂不支持）"})
            if self.processed_items:
                self.list_widget.setCurrentRow(0)
        self._reset_lower_ui()

    def on_offline_error(self, err):
        self.detail_display.setPlainText(f"[引擎崩溃]: {err}")
        self._reset_lower_ui()

    # ========================== HTML 列表单条细节渲染（100% 完整收尾） ==========================
    def display_item_detail(self, index: int):
        """
        选中左下方条目时，在右侧渲染精美的富文本卡片。
        """
        # 【必须将索引判断与 item 提取放在函数的最开头！】
        if index < 0 or index >= len(self.processed_items):
            self.detail_display.clear()
            return
        item = self.processed_items[index]

        import html
        import re
        
        c_text = html.escape(item['content'])
        b_text = html.escape(item['bridge'])
        
        hl_path = get_root_path() / "highlight.txt"
        if hl_path.exists():
            try:
                with open(hl_path, "r", encoding="utf-8") as f:
                    keywords = [line.strip() for line in f if line.strip()]
                for kw in keywords:
                    pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                    repl = lambda m: f'<span style="background-color: #15803d; color: #ffffff; padding: 0 4px; border-radius: 4px; font-weight: bold;">{m.group(0)}</span>'
                    c_text = pattern.sub(repl, c_text)
                    b_text = pattern.sub(repl, b_text)
            except Exception: pass
            
        html_content = f"""
        <div style="line-height: 1.6; font-size: 13.5px; color: #e4e4e7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div style="border-bottom: 1px solid #27272a; padding-bottom: 4px; margin-bottom: 8px;">
                <span style="font-size: 15px; font-weight: bold; color: #3b82f6;">🎬 节点详情</span>
                <span style="background-color: #1e3a8a; color: #60a5fa; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 10px; font-weight: bold;">
                    {item['step_id']} / {item['segment_id']}
                </span>
            </div>
            <table style="width: 100%; margin-bottom: 8px;">
                <tr>
                    <td style="color: #71717a; width: 60px;">⏱️ 时间轴:</td>
                    <td><a href="jump:{item['timestamp']}" style="color: #10b981; text-decoration: none; font-weight: bold; font-family: monospace;">{item['timestamp']}</a></td>
                </tr>
                <tr>
                    <td style="color: #71717a;">🎙️ 模态:</td>
                    <td style="color: #f59e0b; font-weight: bold;">{item['modality']}</td>
                </tr>
            </table>
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px; margin-bottom: 6px;">
                <b style="color: #a1a1aa; font-size: 12.5px;">📝 原始描述 Content：</b>
                <span style="color: #f4f4f5; display: block; margin-top: 4px;">{c_text}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #38bdf8; font-size: 11.5px;">🤖 翻译：</b>
                    <span style="color: #60a5fa; display: block; margin-top: 4px;">{item['content_local_zh']}</span>
                </div>
            </div>
            <div style="background-color: #121214; border: 1px solid #27272a; border-radius: 4px; padding: 10px;">
                <b style="color: #a1a1aa; font-size: 12.5px;">🔗 逻辑关联与过渡 Bridge：</b>
                <span style="color: #e4e4e7; font-style: italic; display: block; margin-top: 4px;">{b_text}</span>
                <div style="border-top: 1px dashed #27272a; margin-top: 8px; padding-top: 8px;">
                    <b style="color: #38bdf8; font-size: 11.5px;">🤖 翻译：</b>
                    <span style="color: #60a5fa; display: block; margin-top: 4px;">{item['bridge_local_zh']}</span>
                </div>
            </div>
        </div>
        """
        self.detail_display.setHtml(html_content)