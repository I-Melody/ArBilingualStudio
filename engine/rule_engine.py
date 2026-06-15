from typing import List, Dict, Any

class RuleContext:
    """
    存储规则执行过程中的上下文状态与流水线数据
    """
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
    """
    抽象规则基类。所有文本清洗与对照对齐规则必须继承此类。
    """
    def execute(self, context: RuleContext) -> RuleContext:
        raise NotImplementedError("Rules must implement the 'execute' method.")


class RuleEngine:
    """
    业务规则调度引擎，负责流水线管理与规则链式调用
    """
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
