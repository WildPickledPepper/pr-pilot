# main.py
import sys
import platform

if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import config
from git_providers.github import GitHubProvider
from analysis.deepseek import DeepSeekAnalyzer
from analysis.base import AIAnalyzer, AnalysisInput, PRContext, DebugInfo
from git_providers.exceptions import PullRequestNotFound
import subprocess
import chromadb
import os
import shutil
from chromadb.errors import NotFoundError


def get_repo_name_from_full(repo_full_name: str) -> str:
    """从 'owner/repo' 中提取 'repo' 部分。"""
    return repo_full_name.split('/')[-1]

def ensure_knowledge_base_exists(repo_full_name: str) -> bool:
    """
    检查知识库是否存在。如果不存在，则触发构建流程。
    """
    repo_short_name = get_repo_name_from_full(repo_full_name)
    db_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    collection_name = repo_short_name.replace('/', '_').replace('.', '_').replace('-', '_')

    try:
        db_client.get_collection(name=collection_name)
        print(f"[OK] Knowledge base for '{repo_short_name}' found.")
        return True
    except Exception:
        print(f"[WARN] Knowledge base for '{repo_short_name}' not found.")

        # 非交互模式（CI 环境）自动构建
        if not sys.stdin.isatty():
            print("Non-interactive mode detected. Auto-building knowledge base...")
            answer = 'y'
        else:
            answer = input("Do you want to build it online now? (This is a one-time setup) (y/n): ").lower()

        if answer != 'y':
            print("Skipping knowledge base build. Analysis will proceed without global context.")
            return False

        print("\nAttempting to build knowledge base online...")
        python_executable = sys.executable
        online_command = [python_executable, "indexer.py", "--repo", repo_full_name]

        result = subprocess.run(
            online_command,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode == 0:
            print("-" * 20)
            print("[OK] Online knowledge base build successful!")
            return True
        else:
            print(f"[ERROR] Online knowledge-base build failed. Return code: {result.returncode}")
            return False


def main():
    parser = argparse.ArgumentParser(description="AI-powered Pull Request review tool.")
    parser.add_argument("--repo", required=True, help="Target repository in 'owner/repo' format.")
    parser.add_argument("--pr", required=True, type=int, help="Pull Request number.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the analysis without posting a comment to GitHub. Saves the review locally instead."
    )

    parser.add_argument(
    "--no-rag",
    action="store_true",
    help="Disable the RAG module to run an ablation study."
    )
    parser.add_argument(
    "--retrieval-mode",
    type=str,
    choices=['diff', 'fast', 'precise'],
    default='precise',
    help="Specify the retrieval strategy: "
         "'diff' (based on PR diff - current default), "
         "'fast' (based on pre-computed old vector), "
         "'precise' (based on real-time new vector)."
    )
    parser.add_argument(
        "--analysis-mode",
        type=str,
        choices=['single', 'two-stage'],
        default='two-stage',
        help="Specify the analysis architecture."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="The number of relevant code snippets to retrieve from the database (Top-K)."
    )
    args = parser.parse_args()
    try:
        # --- 依赖注入 ---
        git_provider = GitHubProvider()
        repo, pr = git_provider.get_pr_metadata(args.repo, args.pr)
        ensure_knowledge_base_exists(args.repo)
        use_rag_flag = not args.no_rag
        print(f"Running analysis with retrieval mode: '{args.retrieval_mode}'")
        pr_analysis_context: PRContext = git_provider.build_context_from_pr(
            repo,
            pr,
            use_rag=use_rag_flag,
            retrieval_mode=args.retrieval_mode,
            analysis_mode=args.analysis_mode,
            top_k=args.top_k
        )
        if config.AI_PROVIDER == "deepseek":
            ai_analyzer = DeepSeekAnalyzer()
            debug_info_for_logging: DebugInfo = {
            "repo_name": args.repo,
            "pr_number": args.pr,
            "retrieval_mode": args.retrieval_mode,
            "analysis_mode": args.analysis_mode,
            "top_k": args.top_k,
        }
        else:
            raise ValueError(f"Unsupported AI provider: {config.AI_PROVIDER}")
        analysis_input: AnalysisInput = {
            "pr_context": pr_analysis_context,
            "analysis_mode": args.analysis_mode,
            "debug_info": debug_info_for_logging
        }
        review = ai_analyzer.analyze(analysis_input)
        print(f"Starting analysis for {args.repo} PR #{args.pr}...")
        print("\n--- AI Review ---")
        print(review)


        if args.dry_run:
                print("\n--- Dry Run Mode: Skipping comment posting. ---")
                output_dir = "reviews"
                os.makedirs(output_dir, exist_ok=True)
                suffix_parts = []

                if not use_rag_flag:
                    suffix_parts.append("no-RAG")
                else:
                    suffix_parts.append(f"retrieval-{args.retrieval_mode}")
                    suffix_parts.append(f"analysis-{args.analysis_mode}")
                    suffix_parts.append(f"k{args.top_k}")

                descriptive_suffix = "_".join(suffix_parts)

                filename = f"{output_dir}/{args.repo.replace('/', '_')}_pr_{args.pr}_{descriptive_suffix}.md"

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(review)
                print(f"Review saved locally to: {filename}")
        else:
                print("\n--- Live Mode: Posting comment to GitHub. ---")
                git_provider.post_comment(args.repo, args.pr, review)

    except PullRequestNotFound as e:
            print(f"\n分析中止: {e}")

            print("\nAnalysis complete.")

    except Exception as e:
        print(f"\nAn error occurred during the main process: {e}")


if __name__ == "__main__":
    main()
