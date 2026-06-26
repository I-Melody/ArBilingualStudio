# -*- coding: utf-8 -*-
import time
import threading
import urllib.request
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ChunkDownloader(threading.Thread):
    def __init__(self, url, start_byte, end_byte, part_path):
        super().__init__()
        self.url, self.start_byte, self.end_byte, self.part_path = url, start_byte, end_byte, part_path
        self.downloaded, self.error, self.is_cancelled = 0, None, False

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Range": f"bytes={self.start_byte}-{self.end_byte}"})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.getcode() != 206:
                    raise Exception("服务器拒绝了分片 Range 请求")
                block_size = 256 * 1024
                with open(self.part_path, "wb") as f:
                    while not self.is_cancelled:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        self.downloaded += len(chunk)
        except Exception as e:
            self.error = str(e)


class VideoDownloadWorker(QThread):
    progress_info = pyqtSignal(int, float, float, float)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, target_file_path: Path):
        super().__init__()
        self.url, self.target_file_path = url, target_file_path
        self.is_cancelled, self.num_threads, self.max_retries = False, 4, 3

    def cancel(self):
        self.is_cancelled = True

    def calculate_optimal_chunks(self, total_size_bytes: int) -> int:
        mb = 1024 * 1024
        if total_size_bytes < 5 * mb:
            return 1
        elif total_size_bytes < 20 * mb:
            return 2
        elif total_size_bytes < 50 * mb:
            return 4
        elif total_size_bytes < 100 * mb:
            return 6
        else:
            return 8

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
                            if "/" in content_range:
                                total_size = int(content_range.split("/")[-1])
                    except Exception:
                        pass
                if supports_range and total_size > 4 * 1024 * 1024:
                    self.num_threads = self.calculate_optimal_chunks(total_size)
                    self.execute_multi_threaded_download(total_size)
                else:
                    self.execute_single_threaded_download()
                return
            except Exception as e:
                retries += 1
                if retries > self.max_retries or self.is_cancelled:
                    if self.target_file_path.exists():
                        try:
                            self.target_file_path.unlink()
                        except Exception:
                            pass
                    self.error.emit(f"下载失败: {e}")
                    return
                else:
                    self.msleep(2000)

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
                if percent >= 100:
                    percent = 99
                self.progress_info.emit(percent, speed_mbs, total_size / (1024 * 1024), dl / (1024 * 1024))
            self.msleep(100)
        if self.is_cancelled:
            for t in threads:
                t.is_cancelled = True
            for t in threads:
                t.join()
            for path in part_paths:
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass
            return
        for t in threads:
            t.join()
            if t.error:
                for path in part_paths:
                    if path.exists():
                        try:
                            path.unlink()
                        except Exception:
                            pass
                raise Exception(f"分片下载中断: {t.error}")
        elapsed_total = time.time() - start_time
        self.progress_info.emit(100, (total_size / elapsed_total) / (1024 * 1024) if elapsed_total > 0 else 0.0, total_size / (1024 * 1024), total_size / (1024 * 1024))
        try:
            with open(self.target_file_path, "wb") as dest:
                for path in part_paths:
                    with open(path, "rb") as src:
                        while True:
                            buf = src.read(1024 * 1024)
                            if not buf:
                                break
                            dest.write(buf)
                    path.unlink()
            self.finished.emit(str(self.target_file_path.resolve()))
        except Exception as e:
            raise Exception(f"分片合并失败: {e}")

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
                    if not chunk:
                        break
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
