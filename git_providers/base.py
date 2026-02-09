# pr_pilot/git_providers/base.py
from abc import ABC, abstractmethod
from typing import Any, Tuple

class GitProvider(ABC):
    @abstractmethod
    def get_pr_metadata(self, repo_name: str, pr_number: int) -> Tuple[Any, Any]:
        """
        获取PR的元数据（如repo对象和pr对象）并检查其状态是否为 'open'。
        这必须是一个廉价的API调用，用于“快速失败”。
        """
        pass

    @abstractmethod
    def build_context_from_pr(self, repo: Any, pr: Any, use_rag: bool, retrieval_mode: str, analysis_mode: str, top_k: int) -> Tuple[str, dict]:
        """
        基于一个已经验证过的 PR 对象，构建完整的分析上下文（包括RAG）。
        这是昂贵的操作部分。返回 (上下文字符串, 项目配置字典)。
        """
        pass

    @abstractmethod
    def post_comment(self, repo_name: str, pr_number: int, comment: str):
        """将评论发布到PR。"""
        pass