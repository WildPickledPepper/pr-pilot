# indexer.py
import argparse
import hashlib
import os
import platform
import subprocess
import sys
import chromadb
from openai import OpenAI
import config
from utils import code_parser
import tiktoken
from utils import repo_reader
import glob
try:
    from pyan.analyzer import CallGraphVisitor
    from pyan.visgraph import VisualGraph
    from pyan.writers import DotWriter
    import pyan
    HAS_PYAN = True
except ImportError:
    HAS_PYAN = False
    print("Warning: pyan not installed. Python call graph generation will be skipped.")
# --- 1. 初始化客户端 ---
from utils.language_registry import registry as lang_registry
from utils import callgraph_builder
from pydriller import Repository
import itertools
from collections import defaultdict
import json
import xml.etree.ElementTree as ET

# ChromaDB 客户端
try:
    db_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
except Exception as e:
    print(f"Failed to initialize ChromaDB client: {e}")
    exit(1)

# OpenAI 客户端: 专门用于生成 Embeddings
if not config.EMBEDDING_API_KEY:
    raise ValueError("EMBEDDING_API_KEY is not configured.")

print(f"Initializing Embedding client with base_url: {config.EMBEDDING_BASE_URL}")
openai_client = OpenAI(
    api_key=config.EMBEDDING_API_KEY,
    base_url=config.EMBEDDING_BASE_URL,
    timeout=180
)

# Tiktoken 编码器
try:
    encoding = tiktoken.encoding_for_model(config.EMBEDDING_MODEL)
except KeyError:
    print(f"Warning: Model {config.EMBEDDING_MODEL} not found in tiktoken. Using cl100k_base encoding.")
    encoding = tiktoken.get_encoding("cl100k_base")


# indexer.py

def get_embedding(text: str, model=config.EMBEDDING_MODEL):
    """Generates an embedding for a given text using OpenAI's API."""
    text = text.replace("\n", " ")
    try:
        response = openai_client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def _compute_file_hash(content: str) -> str:
    """Compute MD5 hash of file content for change detection."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def _load_file_hashes(repo_name: str) -> dict:
    """Load previously stored file hashes from disk."""
    hash_file = os.path.join(config.CHROMA_DB_PATH, f"{repo_name}_file_hashes.json")
    if os.path.exists(hash_file):
        with open(hash_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_file_hashes(repo_name: str, hashes: dict):
    """Save current file hashes to disk for next incremental run."""
    os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)
    hash_file = os.path.join(config.CHROMA_DB_PATH, f"{repo_name}_file_hashes.json")
    with open(hash_file, 'w', encoding='utf-8') as f:
        json.dump(hashes, f, indent=2)


def analyze_co_changes(repo_path: str, repo_name_cleaned: str):
    """
    使用 PyDriller 遍历 Git 历史，分析文件协同变更，并输出到 JSON 文件。
    """
    print("\n--- 阶段 0.1: 分析历史协同变更 (这可能需要几分钟，取决于仓库大小) ---")
    output_dir = config.CO_CHANGE_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name_cleaned}_co_changes.json")

    # commit_counts: 记录每个文件在多少个 commit 中出现过
    # co_changes: 记录文件对共同出现的次数
    commit_counts = defaultdict(int)
    co_changes = defaultdict(lambda: defaultdict(int))
    
    try:
        commit_iterator = Repository(repo_path).traverse_commits()
        
        # 使用 tqdm 来显示进度
        from tqdm import tqdm
        # 我们需要先知道总的 commit 数量来初始化 tqdm
        total_commits = sum(1 for _ in Repository(repo_path).traverse_commits())
        
        print(f"正在分析 {total_commits} 个 commits...")

        for commit in tqdm(Repository(repo_path).traverse_commits(), total=total_commits, desc="Analyzing commit history"):
            # 只关心被修改的、受支持语言的文件
            # 过滤掉已删除的文件 (f.new_path is None)
            supported_files = sorted([
                f.new_path for f in commit.modified_files
                if f.new_path and (lang_registry.is_supported(f.new_path) or
                                   lang_registry.is_text_file_candidate(f.new_path))
            ])
            
            # 如果该 commit 中至少修改了两个受支持语言的文件
            if len(supported_files) >= 2:
                # 更新每个文件出现的总次数
                for file_path in supported_files:
                    commit_counts[file_path] += 1
                
                # 更新协同变更的次数
                # itertools.combinations 会生成所有不重复的文件对
                for file1, file2 in itertools.combinations(supported_files, 2):
                    co_changes[file1][file2] += 1
                    co_changes[file2][file1] += 1
        
        # 将结果保存到 JSON 文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"commit_counts": commit_counts, "co_changes": co_changes}, f, indent=4)
            
        print(f"[OK] 成功生成协同变更数据，并保存至: {output_path}")

    except Exception as e:
        print(f"[ERROR] 在分析协同变更时发生错误: {e}")
        import traceback
        traceback.print_exc()

def analyze_clones(repo_path: str, repo_name_cleaned: str):
    """
    【Windows 最终版】根据官方文档，使用 --dir 参数调用 PMD's CPD。
    """
    print("\n--- 阶段 0.2: 分析代码克隆 (使用 PMD's CPD for Windows) ---")

    # --- 1. 定义所有需要的路径 ---
    pmd_root_path = os.path.abspath(config.PMD_HOME)
    if platform.system() == 'Windows':
        cpd_executable_path = os.path.join(pmd_root_path, "bin", "pmd.bat")
    else:
        cpd_executable_path = os.path.join(pmd_root_path, "bin", "pmd")

    clone_dir = config.CLONE_DATA_DIR
    os.makedirs(clone_dir, exist_ok=True)
    xml_output_path = os.path.join(clone_dir, f"{repo_name_cleaned}_clones.xml")
    json_output_path = os.path.join(clone_dir, f"{repo_name_cleaned}_clones.json")

    if not os.path.exists(cpd_executable_path):
        print(f"[ERROR] 未在预期路径找到 CPD 可执行文件: {cpd_executable_path}")
        return

    try:
        # --- 2. Run CPD for each registered language ---
        all_clone_classes = []
        class_id_counter = 1

        for cpd_language in lang_registry.get_pmd_languages():
            xml_output_path_lang = os.path.join(clone_dir, f"{repo_name_cleaned}_clones_{cpd_language}.xml")

            command = [
                cpd_executable_path,
                "cpd",
                "--minimum-tokens", "25",
                "--dir", os.path.abspath(repo_path),
                "--language", cpd_language,
                "--format", "xml",
            ]

            print(f"正在运行 CPD for {cpd_language}: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=(platform.system() == 'Windows')
            )

            if result.returncode not in [0, 4]:
                print(f"  [WARN] CPD for {cpd_language} returned code {result.returncode}, skipping.")
                continue

            with open(xml_output_path_lang, 'w', encoding='utf-8') as f:
                f.write(result.stdout)

            # Parse XML for this language
            try:
                tree = ET.parse(xml_output_path_lang)
                root = tree.getroot()

                abs_repo_path = os.path.abspath(repo_path)
                for duplication in root.findall('duplication'):
                    locations = []
                    for file_element in duplication.findall('file'):
                        file_path_abs = file_element.get('path')
                        relative_path = os.path.relpath(file_path_abs, abs_repo_path)
                        start_line = int(file_element.get('line'))
                        end_line = int(file_element.get('endline'))
                        locations.append({
                            "file": relative_path.replace('\\', '/'),
                            "start_line": start_line,
                            "end_line": end_line
                        })

                    if len(locations) > 1:
                        all_clone_classes.append({"class_id": class_id_counter, "locations": locations})
                        class_id_counter += 1

                print(f"  [OK] CPD for {cpd_language} parsed successfully.")
            except ET.ParseError:
                print(f"  [WARN] No valid XML output from CPD for {cpd_language} (likely no clones found).")

        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(all_clone_classes, f, indent=2)

        print(f"[OK] 成功解析克隆数据，并保存至: {json_output_path}")

    except Exception as e:
        print(f"[ERROR] 在分析代码克隆时发生未知错误: {e}")
        import traceback
        traceback.print_exc()
def main():
    # --- 1. 升级命令行参数，支持 --path 和 --repo 两种模式 ---
    parser = argparse.ArgumentParser(
        description="Index a code repository into the vector database from a local path or a GitHub repo.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # 使用互斥组，确保 --path 和 --repo 只有一个能被使用
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", help="The LOCAL root path of the repository to index.")
    group.add_argument("--repo", help="The GITHUB repository name to index online (e.g., 'owner/repo').")

    parser.add_argument(
        "--ignore",
        nargs='*',
        default=['.git', '__pycache__', 'node_modules', 'dist', 'build',
                 'chroma_db', 'docs', 'tests', 'examples', 'test',
                 'venv',
                 'call_graphs',
                 'temp_clones',
                 'pycg-master'
                 ],
        help="List of directories to ignore."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full rebuild of the vector database (ignore cached file hashes)."
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Override the collection name (useful in CI where workspace path != repo name)."
    )
    args = parser.parse_args()

    # --- 2. 根据用户选择的模式，准备好 repo_name 和 file_iterator ---
    file_iterator = None
    repo_local_path = None
    if args.repo:
        # 在线模式：自动克隆 GitHub 仓库到临时目录
        print(f"Starting online indexing for GitHub repo: {args.repo}")
        repo_name = args.repo.split('/')[-1].replace('.', '_').replace('-', '_')

        clone_dir = "./temp_clones"
        os.makedirs(clone_dir, exist_ok=True)
        repo_local_path = os.path.join(clone_dir, repo_name)

        if os.path.exists(repo_local_path):
            print(f"Found existing clone at {repo_local_path}, reusing it.")
            # Pull latest changes
            subprocess.run(["git", "-C", repo_local_path, "pull", "--ff-only"],
                         capture_output=True, text=True)
        else:
            clone_url = f"https://github.com/{args.repo}.git"
            print(f"Cloning {clone_url} to {repo_local_path}...")
            result = subprocess.run(
                ["git", "clone", clone_url, repo_local_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            if result.returncode != 0:
                print(f"Failed to clone repository: {result.stderr}")
                return
            print(f"Successfully cloned to {repo_local_path}")

        absolute_path = os.path.abspath(repo_local_path)
        args.path = repo_local_path  # Set path for the file iterator below
    else: # args.path
        absolute_path = os.path.abspath(args.path)
        repo_name = os.path.basename(absolute_path).replace('.', '_').replace('-', '_')

    # --name overrides the auto-derived repo_name (needed in CI/Docker where path != repo name)
    if args.name:
        repo_name = args.name.replace('/', '_').replace('.', '_').replace('-', '_')

    # --- 通用流程：调用图生成 (按语言分支) ---
    try:
        print("\n--- 阶段0: 生成全局调用图 ---")
        call_graph_dir = config.CALL_GRAPH_DIR
        os.makedirs(call_graph_dir, exist_ok=True)

        # Collect all supported files grouped by language
        all_supported_files = {}  # language_name -> [file_paths]
        for f in glob.glob(os.path.join(absolute_path, '**/*'), recursive=True):
            if not os.path.isfile(f):
                continue
            if 'venv' in f:
                continue
            lang_config = lang_registry.detect_language(f)
            if lang_config:
                if lang_config.name not in all_supported_files:
                    all_supported_files[lang_config.name] = []
                all_supported_files[lang_config.name].append(f)

        # Python: use pyan (generates .dot)
        py_files = all_supported_files.get("python", [])
        py_files = [f for f in py_files if os.path.basename(f) != '__init__.py']
        if py_files and HAS_PYAN:
            print(f"Found {len(py_files)} Python files — generating call graph with pyan...")
            output_dot_path = os.path.join(call_graph_dir, f"{repo_name}_call_graph.dot")
            try:
                dot_output = pyan.create_callgraph(
                    filenames=py_files,
                    format='dot',
                    draw_uses=True,
                    draw_defines=False,
                    annotated=True,
                    colored=False,
                    grouped=False,
                    nested_groups=False
                )
                with open(output_dot_path, 'w', encoding='utf-8') as f:
                    f.write(dot_output)
                print(f"  Python call graph saved to: {output_dot_path}")
            except Exception as e:
                print(f"  Warning: pyan call graph generation failed: {e}")
        elif py_files:
            print(f"Found {len(py_files)} Python files but pyan is not installed — skipping Python call graph.")

        # C/C++/Java/Go/JS/TS and all other tree-sitter languages: use tree-sitter (generates .json)
        for lang_config in lang_registry.get_tree_sitter_languages():
            ts_lang = lang_config.tree_sitter_language
            lang_files = all_supported_files.get(lang_config.name, [])
            if lang_files:
                print(f"Found {len(lang_files)} {lang_config.name} files — generating call graph with tree-sitter...")
                ts_graph = callgraph_builder.build_callgraph_tree_sitter(lang_files, ts_lang)
                json_path = os.path.join(call_graph_dir, f"{repo_name}_ts_{ts_lang}_call_graph.json")
                callgraph_builder.save_callgraph_json(ts_graph, json_path)

    except Exception as e:
        print(f"Error generating call graphs: {e}")
        import traceback
        traceback.print_exc()

    # --- 阶段0.1 & 0.2: 历史协同变更 + 代码克隆检测 ---
    analyze_co_changes(absolute_path, repo_name)
    analyze_clones(absolute_path, repo_name)

    # --- 通用流程：文件遍历 (支持 Tier 1 语言 + Tier 2 文本文件) ---
    from utils.language_registry import MAX_TEXT_FILE_SIZE
    def local_file_iterator(path, ignore_list):
        for root, dirs, files in os.walk(path, topdown=True):
            dirs[:] = [d for d in dirs if d not in ignore_list]
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, path)

                if lang_registry.is_supported(file):
                    # Tier 1: registered language
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f_content:
                            yield relative_path, f_content.read()
                    except (IOError, UnicodeDecodeError) as e:
                        print(f"  - Skipping file {relative_path}: {e}")

                elif lang_registry.is_text_file_candidate(file):
                    # Tier 2: unregistered but possibly text
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > MAX_TEXT_FILE_SIZE:
                            continue
                        with open(file_path, 'rb') as f_bin:
                            raw = f_bin.read(8192)
                            if b'\x00' in raw:
                                continue  # binary file
                        with open(file_path, 'r', encoding='utf-8') as f_content:
                            yield relative_path, f_content.read()
                    except (IOError, UnicodeDecodeError):
                        pass  # skip unreadable files silently

    file_iterator = local_file_iterator(args.path, args.ignore)

    # --- 3. 增量索引：对比文件 hash，只处理变更文件 ---
    # 收集当前所有文件及其 hash
    all_files = {}  # relative_path -> content
    new_hashes = {}  # relative_path -> md5_hash
    for relative_path, file_content in file_iterator:
        all_files[relative_path] = file_content
        new_hashes[relative_path] = _compute_file_hash(file_content)

    # 加载上次的文件 hash（--full 模式跳过，视为全新）
    if args.full:
        old_hashes = {}
        print("[Full rebuild mode] Ignoring cached file hashes.")
    else:
        old_hashes = _load_file_hashes(repo_name)

    # 计算差异
    current_files = set(new_hashes.keys())
    previous_files = set(old_hashes.keys())

    added_files = current_files - previous_files
    removed_files = previous_files - current_files
    modified_files = {f for f in current_files & previous_files if new_hashes[f] != old_hashes[f]}
    unchanged_files = current_files & previous_files - modified_files

    files_to_reindex = added_files | modified_files
    files_to_delete = removed_files | modified_files  # modified = delete old + insert new

    print(f"\n--- 阶段3: 增量索引分析 ---")
    print(f"  Total files:     {len(current_files)}")
    print(f"  Unchanged:       {len(unchanged_files)} (skipped)")
    print(f"  Added:           {len(added_files)}")
    print(f"  Modified:        {len(modified_files)}")
    print(f"  Removed:         {len(removed_files)}")

    # 获取或创建 collection（不再删除重建）
    collection = db_client.get_or_create_collection(name=repo_name)

    # 删除已移除/已修改文件的旧 chunks
    if files_to_delete:
        print(f"  Deleting old chunks for {len(files_to_delete)} changed/removed files...")
        for file_path in files_to_delete:
            try:
                collection.delete(where={"file_path": file_path})
            except Exception:
                pass  # file_path may not exist in DB yet

    # 只对新增/修改的文件生成 embedding
    if not files_to_reindex:
        print("  No files changed. Vector database is up to date.")
        _save_file_hashes(repo_name, new_hashes)
        return

    all_chunks_to_process = []
    for file_path in files_to_reindex:
        content = all_files[file_path]
        chunks = code_parser.parse_file_content(content, file_path)
        for chunk_name, chunk_code, _start_line, _end_line in chunks:
            all_chunks_to_process.append((file_path, chunk_name, chunk_code))

    total_chunks = len(all_chunks_to_process)
    print(f"  Chunks to embed: {total_chunks}")

    # --- 4. 生成向量（只处理变更部分）---
    doc_id = collection.count()  # 从已有数量开始编号
    chunks_to_add = {
        "ids": [], "documents": [], "metadatas": [], "embeddings": []
    }

    from tqdm import tqdm
    for i, (relative_path, chunk_name, chunk_code) in enumerate(tqdm(all_chunks_to_process, desc="Generating embeddings")):
        if len(encoding.encode(chunk_code)) > 8191:
            continue

        embedding = get_embedding(chunk_code)

        if embedding:
            chunks_to_add["ids"].append(str(doc_id))
            chunks_to_add["documents"].append(chunk_code)
            chunks_to_add["metadatas"].append({
                "file_path": relative_path, "chunk_name": chunk_name
            })
            chunks_to_add["embeddings"].append(embedding)
            doc_id += 1

    # --- 5. 批量将数据存入数据库 ---
    if chunks_to_add["ids"]:
        print(f"\nAdding {len(chunks_to_add['ids'])} new chunks to the database...")
        try:
            collection.add(**chunks_to_add)
            print(f"Successfully indexed {len(chunks_to_add['ids'])} chunks. "
                  f"Collection '{repo_name}' now has {collection.count()} total chunks.")
        except Exception as e:
            print(f"Error adding chunks to collection: {e}")
    else:
        print("\nNo new code chunks were processed.")

    # 保存文件 hash，下次增量用
    _save_file_hashes(repo_name, new_hashes)
    print(f"File hashes saved for next incremental run.")

if __name__ == "__main__":
    main()