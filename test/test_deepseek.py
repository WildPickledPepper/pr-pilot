# test_deepseek.py
import os
import sys

# 关键：确保我们能找到 pr_pilot 目录下的模块
# 这通常在你从根目录运行时不是问题，但为了测试的健壮性，我们加上
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# --- 我们要测试的目标 ---
from analysis.deepseek import DeepSeekAnalyzer
from analysis.base import AnalysisInput
# -------------------------

print("--- Starting DeepSeek Isolation Test ---")

# 1. 模拟一个最简单的输入数据
# 我们不再使用那个几千个字符的巨大 PR 上下文，只用 "Hello, world!"
mock_analysis_input: AnalysisInput = {
    "pr_context": "This is a simple test. Just say hello.",
    "repo_config": {}  # 模拟一个空的仓库配置
}

try:
    # 2. 初始化分析器
    # (确保你的 .env 文件在正确的位置并且包含了 LLM_API_KEY)
    analyzer = DeepSeekAnalyzer()

    # 3. 调用 analyze 方法
    print("Attempting to call analyzer.analyze()...")
    result = analyzer.analyze(mock_analysis_input)

    # 4. 打印结果
    print("\n--- TEST SUCCEEDED ---")
    print("Successfully received a response from the API:")
    print(result)

except Exception as e:
    print(f"\n--- TEST FAILED ---")
    print(f"An error occurred: {e}")

print("\n--- DeepSeek Isolation Test Finished ---")