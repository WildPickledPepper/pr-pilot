# pr_pilot/utils/repo_reader.py
import os
from github import Github, GithubException, UnknownObjectException
import config
from tqdm import tqdm # <--- 推荐使用 from ... import ... 格式
from utils.language_registry import registry as lang_registry

def read_repo_from_github(repo_name: str, ignore_list: list):
    """
    在线递归地读取一个GitHub仓库的内容，并提供优雅的进度反馈。
    """
    if not config.GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is not configured in .env file.")
    
    g = Github(config.GITHUB_TOKEN)
    
    try:
        repo = g.get_repo(repo_name)
        print(f"Successfully connected to GitHub repository: {repo_name}")
    except UnknownObjectException:
        print(f"Error: Repository '{repo_name}' not found.")
        return

    
    print("Enumerating repository files...")
    all_files = []
    contents_to_scan = repo.get_contents("")
    
    # --- 阶段一：发现文件 ---
    # 我们不再需要那个动态的进度条了，因为它的输出被证明是混乱的。
    # 改为更简单的日志，让用户知道程序在工作。
    print("Discovering content... (This can take several minutes for large repos)")
    
    # 简化发现逻辑，只打印少量反馈
    dir_scan_count = 0
    while contents_to_scan:
        file_content = contents_to_scan.pop(0)
        
        if file_content.name in ignore_list:
            continue

        if file_content.type == "dir":
            dir_scan_count += 1
            if dir_scan_count % 20 == 0: # 每扫描20个目录，打印一个点，表示还在运行
                print(".", end="", flush=True)
            try:
                contents_to_scan.extend(repo.get_contents(file_content.path))
            except Exception as e:
                print(f"\nCould not access dir {file_content.path}: {e}")
        else:
            all_files.append(file_content)

    print(f"\nDiscovery complete. Found {len(all_files)} files.")

    # --- 阶段二：处理文件 (这是我们真正需要进度条的地方) ---
    print(f"Downloading and processing source files...")
    
    if not all_files:
        print("No source files to process.")
        return

    # 过滤出需要处理的受支持语言文件
    supported_files = [f for f in all_files if lang_registry.is_supported(f.name)]

    if not supported_files:
        print("No supported source files found to process.")
        return

    # --- 关键修改：强制使用 ASCII 模式的 tqdm ---
    for file_content in tqdm(
        supported_files,
        desc="Processing source files",
        # 强制使用 ASCII 字符，它能在所有终端上正确显示成 `###`
        ascii=True, 
        # 添加单位，让进度条更易读
        unit="file"
    ):
        try:
            decoded_content = file_content.decoded_content.decode("utf-8")
            yield file_content.path, decoded_content
        except Exception as e:
            # 使用 tqdm.write 来安全地打印错误信息
            tqdm.write(f"    ! Error reading file {file_content.path}: {e}")

    print("\n\nScan complete. Now generating embeddings...", flush=True)