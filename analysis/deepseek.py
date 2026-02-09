# pr_pilot/analysis/deepseek.py
import openai
from .base import AIAnalyzer, AnalysisInput, PRContext # <-- 【修正】导入 PRContext
import prompts
import config
import json
import os # <-- 引入 os 模块
import datetime 
# --- 【新增】为第一阶段的“分析员”设计专门的系统指令 ---
# 这个指令非常关键，它告诉 AI 不要写完整的报告，而是返回一个结构化的 JSON。
ANALYST_SYSTEM_PROMPT = """
You are a junior AI code analyst. Your task is to analyze a potential relationship between a main code change and a single related code snippet from the repository.
Your analysis must be concise and focused.
You MUST respond ONLY with a single JSON object, with no other text before or after it.

The JSON object must have the following structure:
{
  "impact_summary": "A brief, one-sentence summary of the potential impact the main change could have on the related snippet.",
  "risk_score": An integer from 1 (no risk) to 10 (critical risk of breaking changes or severe side-effects).,
  "impact_type": "Categorize the impact type. Examples: 'Logic Error', 'Data Flow Inconsistency', 'Redundant Code', 'Architectural Mismatch', 'No Significant Impact'.",
  "critical_code_block": "Extract a self-contained block of code from the 'Related Code Snippet' that is MOST RELEVANT to your analysis. Aim for a concise block, IDEALLY AROUND 5-15 LINES, that provides enough context to understand the risk. You have the flexibility to go slightly shorter or longer if it is critical for preserving the logical integrity of the code. The goal is clarity and relevance, not strict line counting."
}
"""

class DeepSeekAnalyzer(AIAnalyzer):
    def __init__(self, api_key: str = config.DEEPSEEK_API_KEY):
        if not api_key:
            raise ValueError("DeepSeek API key is not configured.")
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=config.DEEPSEEK_BASE_URL,
            timeout=120.0,
            max_retries=3
        )
        print("DeepSeek Analyzer initialized.")

    # --- 【新增】实现缺失的“分析员”函数 ---
    def _get_preliminary_analysis(self, main_change_context: str, related_snippet: str) -> dict:
        """
        [第一阶段 - 分析员]
        对单个代码片段进行初步分析，并返回包含 critical_quote 的结构化 JSON 报告。
        """
        # 为分析员构建专用的 User Prompt
        user_prompt = f"""
        ### Main Change Context
        This section contains the full context of the pull request, including file contents and diffs.
        {main_change_context}

        ---

        ### Related Code Snippet from Repository
        This is the specific code snippet you need to analyze in relation to the main change.
        ```
        {related_snippet}
        ```

        ---

        Based on the full context above, provide your analysis for the 'Related Code Snippet' in the required JSON format.
        """
        try:
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    # 使用我们新的、升级版的系统指令
                    {"role": "system", "content": ANALYST_SYSTEM_PROMPT}, 
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                # 强制要求返回 JSON，这能极大提升稳定性和成功率
                response_format={"type": "json_object"} 
            )
            report_str = response.choices[0].message.content

            if not report_str:
                raise json.JSONDecodeError("Empty content from API", "", 0)

            # 解析返回的 JSON 字符串
            return json.loads(report_str)
            
        except Exception as e:
            print(f"  - ❌ Analyst failed for a snippet: {e}")
            # 如果失败，返回一个符合新格式的错误字典
            return {
                "impact_summary": "Failed to analyze this snippet due to an error.",
                "risk_score": 0,
                "impact_type": "Analysis Error",
                "critical_quote": ""
            }


    # --- 【修正】修复单阶段分析的全部 Bug ---
    def _analyze_single_stage(self, analysis_input: AnalysisInput) -> str:
        """
        [单阶段 V2.0]
        将结构化的数据“格式化”成最终发送给LLM的巨大字符串。
        """
        print("Running single-stage analysis...")
        pr_context_structured: PRContext = analysis_input["pr_context"]
        repo_config = pr_context_structured["repo_config"] # <-- 【修正】从正确的位置获取 repo_config

        # --- 【修正】将所有结构化数据重新组合成一个完整的 Prompt 字符串 ---
        context_list = [pr_context_structured["main_context"]]

        # 格式化依赖链
        if pr_context_structured["dependency_chains"]:
            chains = pr_context_structured["dependency_chains"]
            context_list.append("\n---\n")
            context_list.append("### ⛓️ CRITICAL: Dependency Chains Detected!\n")
            context_list.append("These functions are connected to your changes through direct or indirect calls. Changes in one might unexpectedly affect the other.\n")
            for chain in sorted(list(set(chains))):
                context_list.append(f"- `{chain}`\n")

        # 格式化RAG结果
        if pr_context_structured["related_snippets"]:
            snippets = pr_context_structured["related_snippets"]
            context_list.append("\n---\n")
            context_list.append("### 📚 Potentially Related Code from the Repository\n")
            context_list.append("Below are the most semantically related code snippets based on content similarity:\n\n")
            for snippet in snippets:
                context_list.append("```\n")
                context_list.append(snippet)
                context_list.append("\n```\n\n")

        final_context_string = "\n".join(context_list) # <-- 【修正】创建最终的字符串变量

        # --- 构建 System Prompt (和原来一样) ---
        system_prompt = prompts.DEFAULT_SYSTEM_PROMPT
        if repo_config and 'rules' in repo_config:
            print("发现自定义规则，正在注入Prompt...")
            custom_rules = "\n".join([f"- {rule}" for rule in repo_config['rules']])
            rules_section = (
                "\n\n### 📝 项目特定审查规则\n"
                "除了通用代码审查外，请务必严格检查并报告以下项目特定规则是否被遵守：\n"
                f"{custom_rules}"
            )
            system_prompt += rules_section

        # --- 调试与 API 调用 ---
        try:
            print("Sending request to DeepSeek API...")
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_context_string} # <-- 【修正】使用正确的变量
                ],
                temperature=config.TEMPERATURE,
            )
            analysis = response.choices[0].message.content
            print("Successfully received analysis from DeepSeek.")
            return analysis
        except openai.APIError as e:
            print(f"Error from DeepSeek API: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred during single-stage analysis: {e}")
            raise

    # --- 【修正】完善两阶段分析的 Prompt 构建 ---
    def _analyze_two_stage(self, analysis_input: AnalysisInput) -> str:
        """
        [新架构 - 两阶段 V2.0]
        编排“分析员-总指挥”流程，先并行收集情报，再进行综合研判。
        """
        print("Starting two-stage analysis with structured data...")
        pr_context_structured: PRContext = analysis_input["pr_context"]
        full_main_context = pr_context_structured["main_context"]         # <-- 完整版，只给分析员
        lean_main_context = pr_context_structured["lean_main_context"] 
        
        related_code_snippets = pr_context_structured["related_snippets"]
        dependency_chains = pr_context_structured["dependency_chains"]
        historical_warnings = pr_context_structured.get("historical_warnings", [])
        clone_warnings = pr_context_structured.get("clone_warnings", [])

        if not related_code_snippets:
            print("No related snippets found. Falling back to single-stage analysis.")
            return self._analyze_single_stage(analysis_input)

        # --- [第一阶段] 并行调用“分析员” (现在可以工作了) ---
        print(f"Found {len(related_code_snippets)} related snippets. Dispatching analysts...")
        preliminary_reports = []
        for i, snippet in enumerate(related_code_snippets):
            print(f"  - Analyzing snippet {i+1}/{len(related_code_snippets)}...")
            report = self._get_preliminary_analysis(full_main_context, snippet)
            report['original_snippet'] = snippet
            preliminary_reports.append(report)

        # --- [第二阶段] 构建“总指挥”的最终 Prompt ---
        preliminary_reports.sort(key=lambda r: r.get('risk_score', 0), reverse=True)
        TOP_N_EVIDENCE = 3
        
        critical_evidence_text = "\n\n---\n\n".join([
            f"--- Critical Evidence #{i+1} (Risk: {report.get('risk_score')}/10) ---\n"
            "```\n"
            f"{report.get('original_snippet', 'N/A')}\n"
            "```"
            for i, report in enumerate(preliminary_reports[:TOP_N_EVIDENCE])
            if report.get('risk_score', 0) > 3
        ])

        briefing_text = "\n\n".join([
            f"Analyst Report #{i+1}:\n" +
            f"- Impact Summary: {report.get('impact_summary', 'N/A')}\n" +
            f"- Risk Score: {report.get('risk_score', 'N/A')}/10\n" +
            f"- Impact Type: {report.get('impact_type', 'N/A')}"
            for i, report in enumerate(preliminary_reports)
        ])
        
        # 【新增】将依赖链信息也加入到最终情报中
        dependency_chains_text = ""
        if dependency_chains:
            chains_str_list = []
            for chain in sorted(list(set(dependency_chains))):
                chains_str_list.append(f"- **Chain**: `{chain}`\n  - **Potential Risk**: [AI to fill this in]")
            
            chains_str = "\n".join(chains_str_list)
            
            dependency_chains_text = f"""
            ### ⛓️ CRITICAL: Dependency Chains Detected!
            Here are the critical dependency chains related to your changes. You MUST analyze the potential risk for EACH chain in your final report.
            {chains_str}
            """

        final_system_prompt = prompts.DEFAULT_SYSTEM_PROMPT
        final_user_prompt = f"""
        {lean_main_context}
        {historical_warnings if historical_warnings else "" }
        {dependency_chains_text}

        ### Intelligence Briefing from Analyst Team
        {briefing_text}

        ### Appendix: High-Risk Code Snippets
        {critical_evidence_text if critical_evidence_text else "No high-risk snippets were identified by the analyst team."}
        
        ### Your Task as Chief Architect
        Based on all the information above (main context, dependency map, intelligence briefing, and high-risk snippets), synthesize the findings and write the final, comprehensive code review report.
        """
        
        # --- 调用 LLM 进行最终研判 ---
        try:
            try:
                debug_info = analysis_input.get("debug_info")
                if debug_info:
                    # 1. 根据 debug_info 构建一个与 .md 文件格式一致的文件名
                    repo = debug_info['repo_name'].replace('/', '_')
                    pr_num = debug_info['pr_number']
                    retrieval = debug_info['retrieval_mode']
                    analysis = debug_info['analysis_mode']
                    k = debug_info['top_k']
                    
                    debug_filename = f"{repo}_pr_{pr_num}_retrieval-{retrieval}_analysis-{analysis}_k{k}_prompt.txt"
                else:
                    # 2. 如果没有 debug_info，提供一个带时间戳的备用方案
                    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_filename = f"stage_two_prompt_{now}.txt"

                # 3. 创建文件夹并写入文件
                output_dir = "debug_prompts"
                os.makedirs(output_dir, exist_ok=True)
                full_path = os.path.join(output_dir, debug_filename)

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write("========== SYSTEM PROMPT (CHIEF ARCHITECT) ==========\n")
                    f.write(final_system_prompt)
                    f.write("\n\n" + "="*80 + "\n\n")
                    f.write("========== USER PROMPT (CHIEF ARCHITECT) ==========\n")
                    f.write(final_user_prompt)
                print(f"✅ [调试] 第二阶段 Prompt 已保存到: {full_path}")

            except Exception as e:
                # 确保日志记录失败不会中断主流程
                print(f"❌ [调试] 保存第二阶段 Prompt 文件失败: {e}")
            print("Briefing complete. Requesting final synthesis from the Chief Architect...")
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": final_user_prompt}
                ],
                temperature=config.TEMPERATURE,
            )
            final_review = response.choices[0].message.content
            print("Successfully received final analysis from Chief Architect.")
            return final_review
        except Exception as e:
            print(f"An unexpected error occurred during two-stage analysis: {e}")
            raise
    # def _analyze_two_stage(self, analysis_input: AnalysisInput) -> str:
    #     """
    #     [临时测试版本] - 仅用于测试阶段一 (分析员) 的输入和输出。
    #     """
    #     print("--- [启动阶段一测试模式] ---")
    #     pr_context_structured: PRContext = analysis_input["pr_context"]

    #     # --- 1. 准备输入数据 ---
    #     full_main_context = pr_context_structured["main_context"]
    #     related_code_snippets = pr_context_structured["related_snippets"]

    #     if not related_code_snippets:
    #         print("错误: RAG 未检索到任何相关代码片段，无法进行测试。")
    #         return "Test Failed: No snippets found."

    #     # 我们只测试第一个检索到的代码片段
    #     test_snippet = related_code_snippets[0]

    #     # 【【【【【 核心测试区域 START 】】】】】
    #     print("\n--- [阶段一输入 Input] ---")
    #     print("1. 发送给分析员的 main_change_context (前500个字符):")
    #     print(full_main_context[:500] + "...")
    #     print("\n" + "="*50 + "\n")
    #     print("2. 发送给分析员的 related_snippet (完整内容):")
    #     print("```python")
    #     print(test_snippet)
    #     print("```")

    #     print("\n--- [正在调用分析员API...] ---")
        
    #     # 调用我们想要测试的核心函数
    #     report = self._get_preliminary_analysis(full_main_context, test_snippet)

    #     print("\n--- [阶段一输出 Output] ---")
    #     print("分析员返回的 JSON 对象:")
    #     # 使用 json.dumps 美化打印输出
    #     print(json.dumps(report, indent=2, ensure_ascii=False))
    #     # 【【【【【 核心测试区域 END 】】】】】

    #     print("\n--- [测试完成，程序将退出] ---")
    #     exit() # 立即退出，不执行后续任何操作

    #     # 后续的总指挥逻辑暂时不会被执行
    #     return "This part will not be reached."

    def analyze(self, analysis_input: AnalysisInput) -> str:
        """
        [调度中心]
        根据传入的 analysis_mode，决定使用单阶段还是两阶段架构。
        """
        mode = analysis_input.get("analysis_mode", "single")

        if mode == "two-stage":
            return self._analyze_two_stage(analysis_input)
        else:
            return self._analyze_single_stage(analysis_input)