# pr_pilot/analysis/history_analyzer.py

import json
import os
import config
from typing import List, Dict, Any

class HistoryAnalyzer:
    # 【【【 修改点 1: __init__ 接收 repo_name_cleaned 】】】
    def __init__(self, repo_name_cleaned: str):
        """
        :param repo_name_cleaned: 已经处理过的、与本地文件名匹配的仓库名。
        """
        self.repo_name_cleaned = repo_name_cleaned
        self.co_change_data = self._load_co_change_data()

    def _load_co_change_data(self) -> Dict[str, Any]:
        """加载由 indexer.py 生成的协同变更数据。"""
        # 现在直接使用传入的 repo_name_cleaned 来拼接路径
        co_change_file = os.path.join(config.CO_CHANGE_DIR, f"{self.repo_name_cleaned}_co_changes.json")
        if not os.path.exists(co_change_file):
            print(f"⚠️ 历史分析警告: 未找到协同变更数据文件: {co_change_file}")
            return {}
        
        try:
            with open(co_change_file, 'r', encoding='utf-8') as f:
                print("✅ 成功加载历史协同变更数据。")
                return json.load(f)
        except Exception as e:
            print(f"❌ 历史分析错误: 加载协同变更数据失败: {e}")
            return {}

    def analyze(self, changed_files: List[str], threshold: float = 0.7) -> List[str]:
        """
        分析 PR 中变更的文件，并根据历史数据查找潜在的遗漏。
        """
        if not self.co_change_data:
            return []

        warnings = []
        commit_counts = self.co_change_data.get("commit_counts", {})
        co_changes = self.co_change_data.get("co_changes", {})
        
        # 将变更文件列表转换为 set 以提高查找效率
        changed_files_set = set(changed_files)

        for changed_file in changed_files:
            if changed_file in co_changes:
                total_commits = commit_counts.get(changed_file, 0)
                if total_commits == 0:
                    continue

                # 检查与该文件协同变更过的所有伙伴
                for partner, count in co_changes[changed_file].items():
                    # 如果伙伴文件不在本次变更中
                    if partner not in changed_files_set:
                        confidence = count / total_commits
                        # 如果置信度高于阈值
                        if confidence >= threshold:
                            warning = (
                                f"文件 `{changed_file}` 被修改了。"
                                f" 根据历史记录，文件 `{partner}` 在过去 {confidence:.0%} 的时间里会随之一起变更，"
                                "但在此 PR 中未被修改。请确认是否需要同步更新。"
                            )
                            warnings.append(warning)
        
        return warnings