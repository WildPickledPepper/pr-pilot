# pr_pilot/analysis/clone_analyzer.py

import json
import os
import config
from typing import List, Dict, Any, Tuple

class CloneAnalyzer:
    def __init__(self, repo_name: str):
        self.repo_name_cleaned = repo_name.replace('/', '_').replace('.', '_').replace('-', '_')
        self.clone_data = self._load_clone_data()
        self.location_to_class_id = self._build_lookup()

    def _load_clone_data(self) -> List[Dict]:
        """加载由 indexer.py 生成的代码克隆数据。"""
        clone_file = os.path.join(config.CLONE_DATA_DIR, f"{self.repo_name_cleaned}_clones.json")
        if not os.path.exists(clone_file):
            print(f"⚠️ 克隆分析警告: 未找到代码克隆数据文件: {clone_file}")
            return []
        
        try:
            with open(clone_file, 'r', encoding='utf-8') as f:
                print("✅ 成功加载代码克隆数据。")
                return json.load(f)
        except Exception as e:
            print(f"❌ 克隆分析错误: 加载代码克隆数据失败: {e}")
            return []

    def _build_lookup(self) -> Dict[str, int]:
        """构建一个从 (文件:起始行) 到克隆类ID的快速查找表。"""
        lookup = {}
        for clone_class in self.clone_data:
            class_id = clone_class["class_id"]
            for location in clone_class["locations"]:
                key = f"{location['file']}:{location['start_line']}"
                lookup[key] = class_id
        return lookup

    def analyze(self, changed_function_locations: Dict[str, Tuple[int, int]]) -> List[str]:
        """
        分析变更的函数/类，并检查是否存在不一致的克隆变更。
        changed_function_locations: 格式为 {'file/path.py': (start, end), ...}
        """
        if not self.clone_data:
            return []

        warnings = []
        
        changed_clone_classes = set()
        
        # 找出本次PR变更了哪些克隆类
        for file_path, (start, end) in changed_function_locations.items():
            key = f"{file_path}:{start}"
            if key in self.location_to_class_id:
                class_id = self.location_to_class_id[key]
                changed_clone_classes.add(class_id)
        
        # 对于每个被变更的克隆类，检查是否所有成员都被变更了
        for class_id in changed_clone_classes:
            clone_class = self.clone_data[class_id - 1] # class_id 从1开始
            all_locations = clone_class["locations"]
            
            # 找到被修改的具体代码片段
            changed_snippet = [loc for loc in all_locations if f"{loc['file']}:{loc['start_line']}" in self.location_to_class_id and self.location_to_class_id[f"{loc['file']}:{loc['start_line']}"] == class_id and loc['file'] in changed_function_locations]
            
            # 找到未被修改的“孪生兄弟”
            unchanged_snippets = [loc for loc in all_locations if loc['file'] not in changed_function_locations]

            if unchanged_snippets and changed_snippet:
                changed_str = f"`{changed_snippet[0]['file']}` (行 {changed_snippet[0]['start_line']})"
                unchanged_str_list = [f"`{loc['file']}` (行 {loc['start_line']})" for loc in unchanged_snippets]
                
                warning = (
                    f"在 {changed_str} 中的代码块被修改了。"
                    f" 系统检测到它与 {', '.join(unchanged_str_list)} 中的代码存在克隆（高度相似）。"
                    "由于只有一个副本被修改，这可能导致行为不一致或未完全修复的 Bug。请务必检查是否需要应用相同的修改。"
                )
                warnings.append(warning)

        return warnings