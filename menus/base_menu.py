from typing import Optional

from PyQt6.QtWidgets import QWidget
from engine.rule_engine import RuleEngine
from engine.translator_service import TranslatorService


class BaseMenuWidget(QWidget):
    """
    主窗口动态加载的菜单基类。定义统一的生命周期与规则引擎接口。
    """
    def __init__(self, parent=None, engine: Optional[RuleEngine] = None,
                 translator_service: Optional[TranslatorService] = None):
        super().__init__(parent)
        self.engine = engine
        self.translator_service = translator_service
        self.init_ui()

    def init_ui(self):
        raise NotImplementedError("Subclasses must implement init_ui method")

    def on_unload(self):
        """
        当模块被热更新卸载时的清理钩子
        """
        pass
