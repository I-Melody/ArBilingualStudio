import sys
import importlib
from pathlib import Path
from PyQt6.QtCore import QObject, QFileSystemWatcher, pyqtSignal

class HotReloadManager(QObject):
    """
    监听menus目录下菜单文件的变化，自动卸载旧模块并发送重载信号
    """
    module_changed = pyqtSignal(str)  # 参数为变化的文件名，如 "menu1"

    def __init__(self, watch_dir: str, parent=None):
        super().__init__(parent)
        self.watch_dir = Path(watch_dir)
        self.watcher = QFileSystemWatcher(self)
        
        # 注册需要监听的文件
        self._registered_files = {}
        self.setup_watchers()
        self.watcher.fileChanged.connect(self._on_file_changed)

    def setup_watchers(self):
        for f in self.watch_dir.glob("menu*.py"):
            path_str = str(f.resolve())
            self.watcher.addPath(path_str)
            self._registered_files[path_str] = f.stem

    def _on_file_changed(self, path: str):
        module_name = self._registered_files.get(path)
        if not module_name:
            return
            
        full_module_name = f"menus.{module_name}"
        
        # 从sys.modules中卸载该模块，强制下一次import时读取最新磁盘文件
        if full_module_name in sys.modules:
            try:
                importlib.reload(sys.modules[full_module_name])
                self.module_changed.emit(module_name)
            except Exception as e:
                print(f"[HotReload Error] 动态重载发生错误: {e}")
