# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil
from pathlib import Path

# 定义项目目录结构与源码内容
PROJECT_FILES = {}

# 1. 依赖声明
PROJECT_FILES["requirements.txt"] = """\
PyQt6>=6.4.0
"""

# 2. 规则引擎核心逻辑
PROJECT_FILES["engine/rule_engine.py"] = """\
from typing import List, Dict, Any

class RuleContext:
    \"\"\"
    存储规则执行过程中的上下文状态与流水线数据
    \"\"\"
    def __init__(self, raw_source: str, raw_target: str = ""):
        self.raw_source = raw_source
        self.raw_target = raw_target
        
        # 过程变量
        self.processed_source_segments: List[str] = []
        self.processed_target_segments: List[str] = []
        
        # 最终输出结果（对齐后的对偶元组）
        self.aligned_pairs: List[tuple[str, str]] = []
        self.metadata: Dict[str, Any] = {}


class BaseRule:
    \"\"\"
    抽象规则基类。所有文本清洗与对照对齐规则必须继承此类。
    \"\"\"
    def execute(self, context: RuleContext) -> RuleContext:
        raise NotImplementedError("Rules must implement the 'execute' method.")


class RuleEngine:
    \"\"\"
    业务规则调度引擎，负责流水线管理与规则链式调用
    \"\"\"
    def __init__(self):
        self._rules: List[BaseRule] = []

    def register_rule(self, rule: BaseRule) -> None:
        if rule not in self._rules:
            self._rules.append(rule)

    def clear_rules(self) -> None:
        self._rules.clear()

    def run(self, context: RuleContext) -> RuleContext:
        for rule in self._rules:
            context = rule.execute(context)
        return context
"""

# 3. 基础清洗与对齐规则
PROJECT_FILES["engine/rules.py"] = """\
import re
from .rule_engine import BaseRule, RuleContext

class TextCleanupRule(BaseRule):
    \"\"\"
    基础文本格式化规则：清理多余空行、统一段落缩进、修复中英文标点空格
    \"\"\"
    def execute(self, context: RuleContext) -> RuleContext:
        # 清洗源文本
        src = context.raw_source
        src = re.sub(r'\\r\\n', '\\n', src)
        src = re.sub(r'\\n{3,}', '\\n\\n', src)  # 限制连续换行
        context.processed_source_segments = [line.strip() for line in src.split('\\n') if line.strip()]

        # 清洗目标译文
        tgt = context.raw_target
        if tgt:
            tgt = re.sub(r'\\r\\n', '\\n', tgt)
            tgt = re.sub(r'\\n{3,}', '\\n\\n', tgt)
            context.processed_target_segments = [line.strip() for line in tgt.split('\\n') if line.strip()]
            
        return context


class SimpleAlignmentRule(BaseRule):
    \"\"\"
    基础行对齐规则：根据段落/句进行简易双语启发式对齐
    \"\"\"
    def execute(self, context: RuleContext) -> RuleContext:
        src_lines = context.processed_source_segments
        tgt_lines = context.processed_target_segments

        aligned = []
        max_len = max(len(src_lines), len(tgt_lines))
        
        for i in range(max_len):
            src_val = src_lines[i] if i < len(src_lines) else ""
            tgt_val = tgt_lines[i] if i < len(tgt_lines) else ""
            aligned.append((src_val, tgt_val))
            
        context.aligned_pairs = aligned
        return context
"""

# 4. 动态菜单基类
PROJECT_FILES["menus/base_menu.py"] = """\
from PyQt6.QtWidgets import QWidget
from engine.rule_engine import RuleEngine

class BaseMenuWidget(QWidget):
    \"\"\"
    主窗口动态加载的菜单基类。定义统一的生命周期与规则引擎接口。
    \"\"\"
    def __init__(self, parent=None, engine: RuleEngine = None):
        super().__init__(parent)
        self.engine = engine
        self.init_ui()

    def init_ui(self):
        raise NotImplementedError("Subclasses must implement init_ui method")
        
    def on_unload(self):
        \"\"\"
        当模块被热更新卸载时的清理钩子
        \"\"\"
        pass
"""

# 5. 菜单1：格式整理模块
PROJECT_FILES["menus/menu1.py"] = """\
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel
from .base_menu import BaseMenuWidget
from engine.rule_engine import RuleContext
from engine.rules import TextCleanupRule

class MenuWidget(BaseMenuWidget):
    \"\"\"
    菜单1：文本格式整理与噪点过滤
    \"\"\"
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.label = QLabel("文本格式整理与清洗（菜单1）", self)
        self.label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.label)
        
        splitter_layout = QHBoxLayout()
        self.input_text = QTextEdit(self)
        self.input_text.setPlaceholderText("在此处粘贴需要整理的原始文本...")
        
        self.output_text = QTextEdit(self)
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("清洗整理后的文本输出...")
        
        splitter_layout.addWidget(self.input_text)
        splitter_layout.addWidget(self.output_text)
        layout.addLayout(splitter_layout)
        
        self.btn_run = QPushButton("执行规则清洗", self)
        self.btn_run.clicked.connect(self.process_text)
        layout.addWidget(self.btn_run)

    def process_text(self):
        if not self.engine:
            return
            
        self.engine.clear_rules()
        self.engine.register_rule(TextCleanupRule())
        
        raw_text = self.input_text.toPlainText()
        context = RuleContext(raw_source=raw_text)
        
        processed_context = self.engine.run(context)
        
        cleaned_result = "\\n".join(processed_context.processed_source_segments)
        self.output_text.setPlainText(cleaned_result)
"""

# 6. 菜单2：中英对照翻译对齐
PROJECT_FILES["menus/menu2.py"] = """\
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from .base_menu import BaseMenuWidget
from engine.rule_engine import RuleContext
from engine.rules import TextCleanupRule, SimpleAlignmentRule

class MenuWidget(BaseMenuWidget):
    \"\"\"
    菜单2：中英文本双轨对齐
    \"\"\"
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.label = QLabel("中英文对齐对照中心（菜单2）", self)
        self.label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.label)
        
        # 输入区
        input_layout = QHBoxLayout()
        self.src_input = QTextEdit(self)
        self.src_input.setPlaceholderText("输入英文源文段落...")
        self.tgt_input = QTextEdit(self)
        self.tgt_input.setPlaceholderText("输入中文译文段落...")
        input_layout.addWidget(self.src_input)
        input_layout.addWidget(self.tgt_input)
        layout.addLayout(input_layout)
        
        # 执行控制
        self.btn_align = QPushButton("执行启发式对齐分析", self)
        self.btn_align.clicked.connect(self.align_texts)
        layout.addWidget(self.btn_align)
        
        # 对齐显示表
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["英文原文", "中文译文"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def align_texts(self):
        if not self.engine:
            return
            
        self.engine.clear_rules()
        self.engine.register_rule(TextCleanupRule())
        self.engine.register_rule(SimpleAlignmentRule())
        
        context = RuleContext(
            raw_source=self.src_input.toPlainText(),
            raw_target=self.tgt_input.toPlainText()
        )
        
        result = self.engine.run(context)
        
        self.table.setRowCount(0)
        for src_line, tgt_line in result.aligned_pairs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(src_line))
            self.table.setItem(row, 1, QTableWidgetItem(tgt_line))
"""

# 7. 菜单3：规则流水线配置
PROJECT_FILES["menus/menu3.py"] = """\
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from .base_menu import BaseMenuWidget

class MenuWidget(BaseMenuWidget):
    \"\"\"
    菜单3：引擎清洗规则流水线观测配置
    \"\"\"
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.label = QLabel("当前引擎装载的过滤链规则流水线列表（菜单3）", self)
        self.label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.label)
        
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        
        self.load_active_rules()

    def load_active_rules(self):
        self.list_widget.clear()
        
        # 默认演示规则链的组成
        rule_chains = [
            "1. TextCleanupRule (多余空格与非法换行归一化)",
            "2. SentenceSplitRule (多语言断句边界识别)",
            "3. HeuristicAlignmentRule (双语段落相似度距离对齐)",
            "4. FinalSanitizeRule (控制符与占位符还原)"
        ]
        
        for rule in rule_chains:
            item = QListWidgetItem(rule)
            self.list_widget.addItem(item)
"""

# 8. 工具：热重载监听器
PROJECT_FILES["utils/hot_reload.py"] = """\
import sys
import importlib
from pathlib import Path
from PyQt6.QtCore import QObject, QFileSystemWatcher, pyqtSignal

class HotReloadManager(QObject):
    \"\"\"
    监听menus目录下菜单文件的变化，自动卸载旧模块并发送重载信号
    \"\"\"
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
"""

# 9. 入口：主程序
PROJECT_FILES["main.py"] = """\
import sys
from pathlib import Path
import importlib

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QStatusBar
from PyQt6.QtCore import Qt

from engine.rule_engine import RuleEngine
from utils.hot_reload import HotReloadManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("双语对齐与格式整理系统")
        self.resize(1000, 700)
        
        # 核心业务引擎初始化
        self.engine = RuleEngine()
        
        # 映射动态加载的页签实例：{ "menu1": (widget_instance, tab_index) }
        self.active_menus = {}
        
        self.init_ui()
        self.init_hot_reload()

    def init_ui(self):
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        
        # 扫描 menus 文件夹加载所有 menu*.py
        menus_dir = Path(__file__).parent / "menus"
        menu_files = sorted(menus_dir.glob("menu*.py"))
        
        for file in menu_files:
            module_name = file.stem
            self.load_tab_module(module_name)
            
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统就绪。修改 menus/ 下的文件，界面将无缝自动更新。")

    def load_tab_module(self, module_name: str):
        \"\"\"
        动态反射加载菜单模块
        \"\"\"
        try:
            module_path = f"menus.{module_name}"
            module = importlib.import_module(module_path)
            
            # 统一提取名为 MenuWidget 的类
            widget_class = getattr(module, "MenuWidget")
            
            # 实例化
            widget_instance = widget_class(parent=self, engine=self.engine)
            
            # 设置标签页标题
            title_map = {
                "menu1": "1. 格式清洗",
                "menu2": "2. 双语对照",
                "menu3": "3. 规则配置"
            }
            tab_title = title_map.get(module_name, module_name.capitalize())
            
            # 添加或替换到 TabWidget
            if module_name in self.active_menus:
                old_widget, index = self.active_menus[module_name]
                old_widget.on_unload()
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, widget_instance, tab_title)
                old_widget.deleteLater()
                self.active_menus[module_name] = (widget_instance, index)
            else:
                index = self.tab_widget.count()
                self.tab_widget.addTab(widget_instance, tab_title)
                self.active_menus[module_name] = (widget_instance, index)
                
        except Exception as e:
            print(f"[Error] 载入菜单失败 {module_name}: {e}")

    def init_hot_reload(self):
        \"\"\"
        开启热重载监听器
        \"\"\"
        menus_dir = str((Path(__file__).parent / "menus").resolve())
        self.reload_manager = HotReloadManager(menus_dir, self)
        self.reload_manager.module_changed.connect(self.on_module_reloaded)

    def on_module_reloaded(self, module_name: str):
        print(f"[HotReload] 检测到文件改动，正在热更新模块: {module_name}")
        self.load_tab_module(module_name)
        self.status_bar.showMessage(f"模块 {module_name} 已于后台完成热重载更新。", 3000)


def main():
    app = QApplication(sys.argv)
    
    # 极简扁平化现代设计样式表，无过度修饰
    app.setStyleSheet(\"\"\"
        QMainWindow {
            background-color: #f7f9fa;
        }
        QTabWidget::pane {
            border: 1px solid #e2e8f0;
            background: #ffffff;
            border-radius: 4px;
        }
        QTabBar::tab {
            background: #edf2f7;
            border: 1px solid #cbd5e0;
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #ffffff;
            border-bottom-color: #ffffff;
            font-weight: bold;
        }
        QPushButton {
            background-color: #3182ce;
            color: white;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #2b6cb0;
        }
        QTextEdit, QTableWidget {
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            background-color: #ffffff;
        }
    \"\"\")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
"""

def create_project_structure():
    """根据定义，生成项目文件"""
    print("[1/4] 开始在当前目录构建项目骨架...")
    for file_path, content in PROJECT_FILES.items():
        path = Path(file_path)
        # 自动创建父文件夹
        path.parent.mkdir(parents=True, exist_ok=True)
        # 写入代码文件
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  已生成文件 -> {file_path}")

def setup_virtual_env():
    """建立 venv 并安装必要依赖"""
    print("\\n[2/4] 创建 Python 虚拟环境 (venv)...")
    venv_dir = Path("venv")
    
    # 兼容Windows与Unix的路径获取
    if sys.platform == "win32":
        pip_path = venv_dir / "Scripts" / "pip.exe"
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"

    # 执行创建虚拟环境命令
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    print("  venv 虚拟环境创建完毕。")

    print("\\n[3/4] 升级 pip 并安装 PyQt6 依赖...")
    # 升级 pip
    subprocess.run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    # 安装 requirements.txt
    subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
    print("  PyQt6 与项目依赖包安装成功。")

def print_execution_manual():
    """提供下一步的操作说明"""
    print("\\n[4/4] 骨架搭建与环境配置全部完成！")
    print("=" * 60)
    print("如何运行并测试热重载功能？")
    print("=" * 60)
    
    if sys.platform == "win32":
        print("1. 激活虚拟环境：")
        print("   .\\\\venv\\\\Scripts\\\\activate")
        print("2. 启动应用程序：")
        print("   python main.py")
    else:
        print("1. 激活虚拟环境：")
        print("   source venv/bin/activate")
        print("2. 启动应用程序：")
        print("   python main.py")
        
    print("-" * 60)
    print("【热重载效果测试步骤】")
    print(" 保持程序运行，直接在编辑器中修改 'menus/menu1.py' 的 UI (例如改动 QPushButton 的文本)。")
    print(" 保存文件后观察软件窗口，菜单页的内容会自动动态刷新，无需手动关闭并重启应用！")
    print("=" * 60)

if __name__ == "__main__":
    try:
        create_project_structure()
        setup_virtual_env()
        print_execution_manual()
    except Exception as e:
        print(f"\\n[Error] 初始化项目骨架时发生意外错误: {e}")