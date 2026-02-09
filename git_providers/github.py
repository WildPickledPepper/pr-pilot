# pr_pilot/git_providers/github.py

from github import Github, GithubException, UnknownObjectException, PullRequest, Repository
from .base import GitProvider
import config
import yaml
import os
from utils import graph_parser
from .exceptions import PullRequestNotFound
from rag import retriever
from utils import code_parser
from utils.language_registry import registry as lang_registry
from utils.callgraph_builder import load_callgraph_json
import numpy as np
import chromadb

# 确保导入了所有需要的数据结构和新分析器
from analysis.base import PRContext
from analysis.history_analyzer import HistoryAnalyzer
from analysis.clone_analyzer import CloneAnalyzer

from typing import Optional

class GitHubProvider(GitProvider):
    def __init__(self, token: str = config.GITHUB_TOKEN):
        if not token:
            raise ValueError("GitHub token is not configured.")
        self.client = Github(token)
        self.db_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        print("Successfully connected to GitHub API.")

    def get_pr_metadata(self, repo_name: str, pr_number: int) -> tuple[Repository.Repository, PullRequest.PullRequest]:
        print(f"Checking metadata for {repo_name} PR #{pr_number}...")
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            if pr.state != 'open':
                raise PullRequestNotFound(f"PR #{pr_number} state is '{pr.state}', not 'open'.")
            print(f"PR is open: '{pr.title}'")
            return repo, pr
        except UnknownObjectException:
            raise PullRequestNotFound(f"PR #{pr_number} in repo {repo_name} does not exist.")
        except GithubException as e:
            print(f"GitHub API error during metadata check: {e}")
            raise

    # 【【【 V3.0 最终版 build_context_from_pr 】】】
    def build_context_from_pr(self, repo: Repository.Repository, pr: PullRequest.PullRequest, use_rag: bool = True, retrieval_mode: str = 'diff', analysis_mode: str = 'two-stage', top_k: int = 5) -> PRContext:
        print("Building structured context for the PR (V3.0)...")

        # 1. 初始化完整的 PRContext 结构
        pr_context: PRContext = {
            "main_context": "",
            "lean_main_context": "",
            "repo_config": {},
            "related_snippets": [],
            "dependency_chains": [],
            "historical_warnings": [],
            "clone_warnings": [],
        }

        # 2. 填充基本信息
        pr_context["repo_config"] = self._load_project_configuration(repo)
        call_graph = self._load_call_graph(repo)
        
        # 3. 分析文件变更 (调用 V3.0 版的函数)
        file_changes_analysis = self._analyze_file_changes(pr, repo)
        
        pr_header = (
            f"Pull Request #{pr.number}: {pr.title}\n"
            f"Author: {pr.user.login}\n---\nPR Description:\n{pr.body or 'No description provided.'}\n---\n"
        )
        
        # 4. 正确地为两个上下文赋值
        pr_context["main_context"] = pr_header + file_changes_analysis["context_for_prompt"]
        pr_context["lean_main_context"] = pr_header + file_changes_analysis["lean_context_for_prompt"]

        # 5. 运行所有增强分析模块
        if use_rag and (file_changes_analysis["diff_query_text"] or file_changes_analysis["changed_functions_code"]):
            pr_context["related_snippets"], pr_context["dependency_chains"] = self._augment_context_with_rag(
                repo, call_graph, file_changes_analysis, retrieval_mode, top_k
        
            )

        repo_short_name = repo.full_name.split('/')[-1]
        repo_name_cleaned = repo_short_name.replace('.', '_').replace('-', '_')

        history_analyzer = HistoryAnalyzer(repo_name_cleaned)
        changed_files_for_history = file_changes_analysis["changed_files"]
        pr_context["historical_warnings"] = history_analyzer.analyze(changed_files_for_history)

        clone_analyzer = CloneAnalyzer(repo_name_cleaned)
        pr_context["clone_warnings"] = clone_analyzer.analyze(file_changes_analysis["changed_function_locations"])

        print("✅ Successfully built comprehensive structured PR context.")
        return pr_context


    def _load_project_configuration(self, repo: Repository.Repository) -> dict:
        """【专业模块 1】加载 .pr-pilot.yml 配置文件。"""
        # (此函数与上一版完全相同)
        try:
            config_content = repo.get_contents(".pr-pilot.yml").decoded_content.decode("utf-8")
            print("Successfully loaded .pr-pilot.yml config from the repository.")
            return yaml.safe_load(config_content)
        except UnknownObjectException:
            print("No .pr-pilot.yml config file found in the repository. Using default settings.")
            return {}
        except Exception as e:
            print(f"Error loading .pr-pilot.yml: {e}")
            return {}

    def _load_call_graph(self, repo: Repository.Repository) -> dict:
        """【专业模块 2】加载并合并项目的全局调用图（pyan .dot + tree-sitter .json）。"""
        repo_short_name = repo.name
        repo_name_cleaned = repo_short_name.replace('.', '_').replace('-', '_')
        call_graph = {}

        # Load pyan .dot call graph (Python)
        dot_file_path = os.path.join(config.CALL_GRAPH_DIR, f"{repo_name_cleaned}_call_graph.dot")
        if os.path.exists(dot_file_path):
            print(f"Loading pyan call graph from: {dot_file_path}")
            parsed_data = graph_parser.parse_dot_file(dot_file_path)
            if parsed_data:
                print("✅ Pyan call graph loaded successfully.")
                call_graph.update(parsed_data)
            else:
                print("⚠️ Warning: Pyan call graph file exists but failed to parse.")

        # Load tree-sitter .json call graphs (C/C++/Java/Go/JS/TS)
        for ts_lang in ("c", "cpp", "java", "go", "javascript", "typescript"):
            json_file_path = os.path.join(config.CALL_GRAPH_DIR, f"{repo_name_cleaned}_ts_{ts_lang}_call_graph.json")
            if os.path.exists(json_file_path):
                print(f"Loading tree-sitter {ts_lang} call graph from: {json_file_path}")
                ts_graph = load_callgraph_json(json_file_path)
                if ts_graph:
                    # Merge: for overlapping keys, combine edge lists
                    for node, edges in ts_graph.items():
                        if node in call_graph:
                            existing = set(call_graph[node])
                            existing.update(edges)
                            call_graph[node] = list(existing)
                        else:
                            call_graph[node] = edges
                    print(f"✅ Tree-sitter {ts_lang} call graph merged ({len(ts_graph)} nodes).")

        if not call_graph:
            print("⚠️ Warning: No call graph files found. Skipping dependency chain analysis.")
        return call_graph

    def _analyze_file_changes(self, pr: PullRequest.PullRequest, repo: Repository.Repository) -> dict:
        analysis_result = {
            "changed_files": [],
            "changed_function_locations": {},
            "changed_function_nodes": set(),
            "changed_functions_code": [],
            "diff_query_text": "",
            "context_for_prompt": "",           # 完整版上下文
            "lean_context_for_prompt": "File Changes (Diffs Only):\n" # 瘦身版上下文
        }
        
        all_diffs_for_rag_query = []
        full_context_list = ["File Changes:\n"]
        lean_context_list = []

        # 2. 遍历 PR 中的所有文件
        files = pr.get_files()
        for file in files:
            # 只处理被修改或新增的受支持语言文件
            if file.status not in ['modified', 'added'] or not lang_registry.is_supported(file.filename):
                continue
            
            analysis_result["changed_files"].append(file.filename)
            
            try:
                # 获取文件的完整内容（用于完整版上下文）
                full_content = repo.get_contents(file.filename, ref=pr.head.sha).decoded_content.decode("utf-8")
                # 解析文件，获取函数/类的定义和位置
                file_definitions = code_parser.parse_file_content(full_content, file.filename)
            except Exception as e:
                print(f"Could not get or parse content for file {file.filename}: {e}")
                continue

            # 3. 解析 Diff，找出被修改的具体行号
            changed_lines = set()
            patch_lines = (file.patch or "").split('\n')
            line_num_in_file = 0
            for line in patch_lines:
                if line.startswith('@@'):
                    try:
                        line_num_in_file = int(line.split(' ')[2].split(',')[0].strip('+'))
                    except (ValueError, IndexError): 
                        line_num_in_file = 0 # 如果解析失败，从头开始，这是一个安全的回退
                        continue
                elif line.startswith('+') and not line.startswith('+++'):
                    changed_lines.add(line_num_in_file)
                    line_num_in_file += 1
                elif not line.startswith('-'):
                    line_num_in_file += 1
            
            # 4. 识别被修改的具体函数/类
            module_path = lang_registry.strip_extension(file.filename).replace('/', '.').replace('\\', '.')
            for name, code, start, end in file_definitions:
                # 如果函数/类的行号范围与被修改的行号有交集
                if not changed_lines.isdisjoint(range(start, end + 1)):
                    # 类方法名格式 "ClassName.method" → "module__ClassName__method"
                    sanitized_name = name.replace('.', '__')
                    full_name = f"{module_path.replace('.', '__')}__{sanitized_name}"
                    analysis_result["changed_function_nodes"].add(full_name)
                    analysis_result["changed_functions_code"].append(code)
                    analysis_result["changed_function_locations"][file.filename] = (start, end)
            
            diff_patch = file.patch or "No diff available."
            all_diffs_for_rag_query.append(diff_patch)

            # 5. 同时为两种上下文列表添加内容
            # --- 为完整版上下文拼接 ---
            full_context_list.append(f"--- Modified File: {file.filename} ---")
            full_context_list.append("\n<< FILE CONTENT >>\n")
            full_context_list.append(full_content)
            full_context_list.append("\n<< DIFF >>\n")
            full_context_list.append(diff_patch)
            full_context_list.append("\n<< END DIFF >>\n")

            # --- 为瘦身版上下文拼接 ---
            lean_context_list.append(f"--- Diff for {file.filename} ---")
            lean_context_list.append(diff_patch)
            lean_context_list.append("\n")

        # 6. 将列表拼接成最终的字符串并存入返回字典
        analysis_result["diff_query_text"] = "\n".join(all_diffs_for_rag_query)
        analysis_result["context_for_prompt"] = "\n".join(full_context_list)
        analysis_result["lean_context_for_prompt"] += "\n".join(lean_context_list)
        
        return analysis_result

    def _augment_context_with_rag(self, repo: Repository.Repository, call_graph: dict, file_changes_analysis: dict, retrieval_mode: str, top_k: int) -> tuple[list[str], list[str]] :
        """
        【A/B/C 核心战场】执行 RAG 和依赖链增强，根据模式选择不同查询策略。
        """
        print(f"\nAugmenting context using '{retrieval_mode}' retrieval mode...")
        
        query_text = ""
        query_embedding = None
        
        collection_name = repo.name.replace('.', '_').replace('-', '_')

        # ================== A/B/C 测试逻辑分支 START ==================
        if retrieval_mode == 'precise':
            if file_changes_analysis["changed_functions_code"]:
                print("Strategy: Using new code from changed functions.")
                query_text = "\n".join(file_changes_analysis["changed_functions_code"])
            else:
                print("Warning: 'precise' mode selected but no changed function code found. Falling back to 'diff'.")
                query_text = file_changes_analysis['diff_query_text']
        
        elif retrieval_mode == 'fast':
            changed_nodes = file_changes_analysis['changed_function_nodes']
            if changed_nodes:
                print(f"Strategy: Using pre-computed vectors for {len(changed_nodes)} changed functions.")
                try:
                    collection = self.db_client.get_collection(name=collection_name)
                    
                    # 提取函数名用于元数据查询
                    chunk_names = [name.split('__')[-1] for name in changed_nodes]
                    where_clause = {"chunk_name": {"$in": chunk_names}}
                    
                    results = collection.get(where=where_clause, include=["embeddings"])
                    
                    if results and results['embeddings']:
                        # 对所有找到的向量取平均值，创建一个综合查询向量
                        embeddings = np.array(results['embeddings'])
                        query_embedding = np.mean(embeddings, axis=0).tolist()
                        print(f"Successfully retrieved and averaged {len(embeddings)} vectors.")
                    else:
                        print("Warning: 'fast' mode: No pre-computed vectors found for changed functions. Falling back to 'diff'.")
                        query_text = file_changes_analysis['diff_query_text']
                except Exception as e:
                    print(f"Error in 'fast' mode: {e}. Falling back to 'diff'.")
                    query_text = file_changes_analysis['diff_query_text']
            else:
                print("Warning: 'fast' mode selected but no changed functions identified. Falling back to 'diff'.")
                query_text = file_changes_analysis['diff_query_text']
        
        else: # 默认 'diff' 模式
            print("Strategy: Using PR diff content.")
            query_text = file_changes_analysis['diff_query_text']
        
        # ================== A/B/C 测试逻辑分支 END ==================

        if not query_text and not query_embedding:
            print("No query text or embedding for RAG. Skipping.")
            return [], []

        # --- retriever 现在需要能同时处理 text 或 embedding ---
        # (这需要对 retriever.py 做一个小的修改)
        print(f"Retrieving Top-K={top_k} relevant code snippets...")
        if query_embedding:
             relevant_chunks_docs, relevant_chunks_metas = retriever.retrieve_relevant_code(None, repo.name, n_results=top_k, query_embedding=query_embedding)
        else:
             relevant_chunks_docs, relevant_chunks_metas = retriever.retrieve_relevant_code(query_text, repo.name, n_results=top_k)

        if not relevant_chunks_docs:
            print("No relevant code snippets found in the knowledge base.")
            return [], []

        # --- 依赖链分析与 Prompt 组装逻辑 (和原来保持一致) ---
        # (省略了这部分代码，因为它和上一版完全相同，以保持简洁)
        context_list = []
        dependency_chains = []
        changed_function_nodes = file_changes_analysis["changed_function_nodes"]
        if call_graph and changed_function_nodes:
            for i, meta in enumerate(relevant_chunks_metas):
                candidate_module_path = lang_registry.strip_extension(meta['file_path']).replace('/', '.').replace('\\', '.')
                candidate_name = meta['chunk_name']
                candidate_full_name = f"{candidate_module_path.replace('.', '__')}__{candidate_name}"

                aligned_candidate_name = self._align_node_name(candidate_full_name, call_graph)
                if not aligned_candidate_name:
                    continue

                for changed_func_name in changed_function_nodes:
                    aligned_changed_name = self._align_node_name(changed_func_name, call_graph)
                    if not aligned_changed_name:
                        continue

                    # 正向搜索
                    path = graph_parser.find_path(call_graph, start_node=aligned_changed_name, end_node=aligned_candidate_name)
                    if path:
                        dependency_chains.append(" -> ".join(path))

                    # 反向搜索
                    path_reversed = graph_parser.find_path(call_graph, start_node=aligned_candidate_name, end_node=aligned_changed_name)
                    if path_reversed:
                        dependency_chains.append(" -> ".join(path_reversed))
        
        # 拼接 Prompt
        if dependency_chains:
            context_list.append("\n---\n")
            context_list.append("### ⛓️ CRITICAL: Dependency Chains Detected!\n")
            context_list.append("These functions are connected to your changes through direct or indirect calls. Changes in one might unexpectedly affect the other.\n")
            for chain in sorted(list(set(dependency_chains))):
                context_list.append(f"- `{chain}`\n")
            context_list.append("\n---\n")
        
        context_list.append("\n---\n")
        context_list.append("### 📚 Potentially Related Code from the Repository\n")
        context_list.append("Below are the most semantically related code snippets based on content similarity:\n\n")
        for i, snippet in enumerate(relevant_chunks_docs):
            fence_tag = ""
            if i < len(relevant_chunks_metas):
                fence_tag = lang_registry.get_code_fence_tag(relevant_chunks_metas[i].get('file_path', ''))
            context_list.append(f"```{fence_tag}\n")
            context_list.append(snippet)
            context_list.append("\n```\n\n")
            
        return relevant_chunks_docs, dependency_chains

    # ... _align_node_name 和 post_comment 方法保持不变 ...
    def _align_node_name(self, node_name: str, graph: dict) -> Optional[str]:
        """【工具函数】动态对齐节点名，解决 pyan 前缀不一致问题。"""
        if node_name in graph:
            return node_name
        
        # 尝试移除路径前缀，直到匹配或无法再分
        parts = node_name.split('__')
        for i in range(1, len(parts)):
            potential_match = "__".join(parts[i:])
            if potential_match in graph:
                return potential_match
        return None

    def post_comment(self, repo_name: str, pr_number: int, comment: str):
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            print(f"Successfully posted a comment on PR #{pr_number}.")
        except GithubException as e:
            print(f"Error posting comment to GitHub: {e.status} {e.data}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred in post_comment: {e}")
            raise