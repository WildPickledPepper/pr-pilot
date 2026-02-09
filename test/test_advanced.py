# test_advanced.py (A much shorter and smarter version)
import sys
import os

# 确保 Python 能找到 analysis 目录下的模块
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from analysis.deepseek import DeepSeekAnalyzer
from analysis.base import AnalysisInput

# ------------------- 关键部分 -------------------
# 一个简短的、但包含了所有“可疑”特殊字符的测试字符串
tricky_context = """
This is a test with "special characters" and backslashes: C:\\Users\\Test.
Let's include the most suspicious line from the original log:
- ["\\"3.9\\", \\"3.10\\", \\"3.11\\"]
And also some characters from YAML: ${{ matrix.os }}
"""
# ----------------------------------------------------

print("--- Starting Smart & Short Advanced Content Test ---")

mock_input: AnalysisInput = {
    "pr_context": tricky_context,
    "repo_config": {}
}

try:
    analyzer = DeepSeekAnalyzer()
    print("Attempting to call analyzer with the tricky context...")
    
    result = analyzer.analyze(mock_input)

    print("\n--- ADVANCED TEST SUCCEEDED ---")
    print("The analyzer handled the tricky string correctly.")
    print("Response from API:")
    print(result)

except Exception as e:
    print(f"\n--- ADVANCED TEST FAILED ---")
    print("The error occurred even with the short tricky string.")
    print("This confirms the issue is with how special characters are handled.")
    print(f"Error: {e}")