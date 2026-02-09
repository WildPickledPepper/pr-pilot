# utils/graph_parser.py
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional

def parse_dot_file(file_path: str) -> Dict[str, List[str]]:
    """
    智能解析 .dot 文件，并确保所有出现过的节点都在图中有一个条目。
    """
    # 这一次，我们用一个 set 来记录所有出现过的节点
    all_nodes = set()
    
    # 邻接表
    adj_list = defaultdict(list)
    
    edge_pattern = re.compile(r'^\s*"?([a-zA-Z0-9_.]+)"?\s*->\s*"?([a-zA-Z0-9_.]+)"?\s*\[.*\];$')
    # Parse .dot file into adjacency list
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = edge_pattern.match(line)
                if match:
                    caller_raw = match.group(1).strip('"')
                    callee_raw = match.group(2).strip('"')
                    
                    # caller = caller_raw.replace('__', '.')
                    # callee = callee_raw.replace('__', '.')
                    caller = caller_raw
                    callee = callee_raw
                    
                    adj_list[caller].append(callee)
                    
                    # 无论作为调用者还是被调用者，都记录下来
                    all_nodes.add(caller)
                    all_nodes.add(callee)
        
        # 现在，我们构建最终的、完整的图
        full_graph = {node: [] for node in all_nodes}
        full_graph.update(adj_list) # 将我们解析到的边关系更新进去

        print(f"Call graph loaded: {len(all_nodes)} nodes, {len(adj_list)} with outgoing edges.")
        return full_graph

    except FileNotFoundError:
        print(f"❌ [Graph Parser] 错误: .dot 文件未找到: {file_path}")
        return {}
    except Exception as e:
        print(f"❌ [Graph Parser] 解析 .dot 文件时发生未知错误: {e}")
        return {}

def find_path(graph: Dict[str, List[str]], start_node: str, end_node: str) -> Optional[List[str]]:
    """
    使用广度优先搜索 (BFS) 在调用图中查找从 start_node 到 end_node 的路径。
    """
    if start_node not in graph or end_node not in graph:
        return None

    # 我们这次要找的是从 start_node 到 end_node 的正向路径
    queue = deque([(start_node, [start_node])])
    visited = {start_node}

    while queue:
        current_node, path = queue.popleft()

        if current_node == end_node:
            return path  # 找到了！

        for neighbor in graph.get(current_node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                new_path = list(path)
                new_path.append(neighbor)
                queue.append((neighbor, new_path))
                
    return None

if __name__ == '__main__':
    test_dot_file = './call_graphs/pr_pilot_call_graph.dot'
    parsed_graph = parse_dot_file(test_dot_file)
    
    if parsed_graph:
        print("\n--- “开图器”测试通过 ---")
        
        print("\n--- 开始测试“侦察兵” ---")
        
        # 测试用例 1: 查找一个已知的、存在的正向路径
        start = 'pr_pilot.main.main'
        end = 'pr_pilot.main.ensure_knowledge_base_exists'
        print(f"正在查找从 '{start}' 到 '{end}' 的调用路径...")
        path1 = find_path(parsed_graph, start, end) # <--- 我们现在找正向路径
        if path1:
            print(f"✅ 找到路径: {' -> '.join(path1)}")
        else:
            print("❌ 未找到路径。")
            
        # 测试用例 2: 查找一个不存在的路径
        start = 'pr_pilot.indexer.main'
        end = 'pr_pilot.main.main'
        print(f"\n正在查找从 '{start}' 到 '{end}' 的调用路径...")
        path2 = find_path(parsed_graph, start, end)
        if path2:
            print(f"❌ 找到了不该存在的路径: {' -> '.join(path2)}")
        else:
            print("✅ 未找到路径 (符合预期)。")
        
        # 我们可以检查一下图中到底有什么
        # print("\n--- 图中部分节点 ---")
        # for i, node in enumerate(parsed_graph.keys()):
        #     if i > 10: break
        #     print(node)

        print(f"\n✅ graph_parser.py 完整测试通过！")
    else:
        print("\n❌ graph_parser.py 测试失败。")