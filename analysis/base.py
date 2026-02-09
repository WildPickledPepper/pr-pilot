# pr_pilot/analysis/base.py

from abc import ABC, abstractmethod
from typing import TypedDict, List, Dict, Any, Optional

# 1. 定义用于PR上下文的结构化字典
class PRContext(TypedDict):
    main_context: str
    lean_main_context: str
    repo_config: Dict[str, Any]
    related_snippets: List[str]
    dependency_chains: List[str]
    historical_warnings: List[str]  # <-- 新增：历史协同变更警告
    clone_warnings: List[str]  # 检测到的依赖链

# 2. 定义AI分析器的统一输入结构
class DebugInfo(TypedDict):
    repo_name: str
    pr_number: int
    retrieval_mode: str
    analysis_mode: str
    top_k: int

class AnalysisInput(TypedDict):
    pr_context: PRContext
    analysis_mode: str
    # 【【【【【 关键修改 2: 将调试信息作为可选字段加入 】】】】】
    debug_info: Optional[DebugInfo]

# 3. 定义AI分析器的接口（ABC - 抽象基类）
class AIAnalyzer(ABC):
    @abstractmethod
    def analyze(self, analysis_input: AnalysisInput) -> str:
        """Analyze the provided context and return the review."""
        pass