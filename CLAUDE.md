# PR-Pilot 项目上下文

## 项目简介

PR-Pilot 是一个 AI 驱动的 GitHub Pull Request 代码审查工具。它不是简单的"LLM 包一层"，而是融合了四个维度的分析能力，具备真正的技术壁垒。以 **GitHub Action** 形式发布，用户只需在仓库配 workflow 即可使用。

## 当前状态（2026-02-09 更新）

v2.0 核心功能已完成，CLI + GitHub Action 双形态：

```bash
# CLI 模式（本地调试）
python indexer.py --repo "owner/repo"
python main.py --repo "owner/repo" --pr 123 --dry-run --analysis-mode two-stage --retrieval-mode precise --top-k 5

# GitHub Action 模式（自动触发）
# 用户在自己仓库配置 .github/workflows/pr-pilot.yml 即可
```

## 架构总览

```
main.py                          # 入口，解析命令行参数，调度流程
config.py                        # 配置（API keys 从 .env 或环境变量读取）
prompts.py                       # LLM System Prompt 模板
indexer.py                       # 离线预处理：调用图 + 向量化 + 历史分析 + 克隆检测（支持增量索引）

analysis/
  base.py                        # 数据结构定义（PRContext, AnalysisInput, DebugInfo）
  deepseek.py                    # LLM 分析引擎（单阶段 + 两阶段"分析员-总指挥"架构）
  history_analyzer.py            # 历史协同变更分析（基于 PyDriller）
  clone_analyzer.py              # 代码克隆检测（基于 PMD/CPD）

git_providers/
  base.py                        # GitProvider 抽象基类
  github.py                      # GitHub API 集成（读 PR、构建上下文、RAG + 依赖链增强、发评论）
  exceptions.py                  # 自定义异常

rag/
  retriever.py                   # 向量检索（ChromaDB + Embedding API）

utils/
  language_registry.py           # 语言注册中心（7 种语言配置 + TreeSitterGrammar 数据类）
  code_parser.py                 # 多语言 AST 解析（Python ast + tree-sitter 通用提取）
  callgraph_builder.py           # tree-sitter 调用图构建器（通用 + C/C++ 专用）
  graph_parser.py                # .dot 调用图解析 + BFS 路径搜索
  repo_reader.py                 # 仓库文件读取工具

tools/
  pyan-1.2.0/                    # Python 静态分析（生成调用图）
  pmd-bin-7.18.0-SNAPSHOT/       # PMD/CPD（代码克隆检测）

# GitHub Action 基础设施
action.yml                       # Action 定义（inputs: API keys, 分析参数）
Dockerfile                       # Docker 镜像（Python 3.11 + git + JRE + jq）
entrypoint.sh                    # Action 入口脚本（建库 → 分析 PR）
.github/workflows/pr-pilot.yml  # 示例 workflow（含 actions/cache）

test/
  test_multi_language.py         # 39 个单元测试（语言注册、解析、调用图）
```

## 四维分析引擎

| 维度 | 模块 | 功能 | 状态 |
|------|------|------|------|
| 语义分析（RAG） | `retriever.py` | 向量相似度检索全仓库相关代码 | 完成 |
| 架构分析（依赖链） | `graph_parser.py` + `callgraph_builder.py` | pyan/tree-sitter 调用图 + BFS 路径搜索 | 完成 |
| 历史分析（协同变更） | `history_analyzer.py` | PyDriller 挖掘 Git 历史模式 | 完成 |
| 克隆分析（代码基因） | `clone_analyzer.py` | PMD/CPD 检测代码克隆 | 完成 |

## 支持语言（7 种）

| 语言 | AST 解析 | 调用图 | 文件扩展名 |
|------|----------|--------|-----------|
| Python | ast 模块 | pyan (.dot) | .py |
| C | tree-sitter (declarator) | tree-sitter (.json) | .c, .h |
| C++ | tree-sitter (declarator) | tree-sitter (.json) | .cpp, .cc, .cxx, .hpp, .hxx |
| Java | tree-sitter (generic) | tree-sitter (.json) | .java |
| Go | tree-sitter (generic) | tree-sitter (.json) | .go |
| JavaScript | tree-sitter (generic) | tree-sitter (.json) | .js, .jsx, .mjs |
| TypeScript | tree-sitter (generic) | tree-sitter (.json) | .ts, .tsx |

数据驱动架构：`TreeSitterGrammar` 数据类描述每种语言的 AST 节点类型，通用提取函数配合 grammar 配置工作。添加新语言只需注册 grammar 配置。

## 两阶段 LLM 架构

**第一阶段 "分析员"**：对每个 RAG 检索到的代码片段，并行调用 LLM，返回结构化 JSON（风险评分、影响类型、关键代码块）

**第二阶段 "总指挥"**：汇总所有分析员报告 + 依赖链 + 历史警告 + 克隆警告，一次调用 LLM 生成最终审查报告

## 增量索引

- 文件 hash 追踪：`{repo_name}_file_hashes.json` 存于 `chroma_db/`
- `get_or_create_collection()` 替代 delete+create
- 只对新增/修改文件调 embedding API，未变更文件跳过
- `collection.delete(where={"file_path": path})` 清理旧 chunks
- `--full` 参数强制全量重建
- `--name` 参数支持 CI 环境显式指定集合名

## 技术栈

- **语言**: Python 3.9+
- **LLM**: 任意 OpenAI 兼容 API（DeepSeek、OpenAI、自定义代理等）
- **Embedding**: 任意 OpenAI 兼容 Embedding API（支持自定义 base_url 代理）
- **向量数据库**: ChromaDB（本地持久化 + 增量更新）
- **GitHub**: PyGithub
- **AST 解析**: Python ast + tree-sitter（7 种语言）
- **静态分析**: pyan（Python 调用图）、tree-sitter（多语言调用图）、PMD/CPD（克隆检测）
- **历史分析**: PyDriller
- **CI/CD**: GitHub Actions + Docker

## 三种检索模式

- `diff`：用 PR diff 内容生成查询向量
- `fast`：用预计算的旧函数向量查询（最快）
- `precise`：用变更后的新函数代码实时生成向量查询（最准）

## 数据文件

- `chroma_db/` — 向量数据库 + 文件 hash 缓存
- `call_graphs/` — .dot（Python）+ .json（其他语言）调用图
- `co_change_data/` — 历史协同变更 JSON
- `clone_data/` — 代码克隆检测 JSON
- `temp_clones/` — git clone 的临时目录
- `reviews/` — dry-run 模式输出的审查报告

## 已完成的改造记录

### 2026-02-07: 多语言支持 v1（C/C++）
1. 创建 `language_registry.py`、`callgraph_builder.py`
2. `code_parser.py` 新增 tree-sitter C/C++ 解析 + 调度器
3. `indexer.py` 5 处过滤点改为语言感知
4. `github.py` 4 处过滤点 + 调用图合并加载
5. 20 个单元测试全部通过，3 个 E2E 测试通过（zlib/json-c/fmt）

### 2026-02-08: Bug 修复 + 多语言扩展 + 增量索引
1. RAG 集合名不匹配修复（`github.py` 用 `repo.name` 统一短名）
2. 协同变更/克隆检测接入 `indexer.py main()`
3. 移除 `git clone --depth 1`，支持 PyDriller 历史分析
4. 扩展到 7 种语言（+Java/Go/JS/TS），数据驱动 `TreeSitterGrammar` 架构
5. 增量索引（文件 hash 比对，只对变更文件调 embedding API）
6. Action 适配：`--name` 参数、`entrypoint.sh` 集合名修复、`main.py` 自动构建修复
7. 示例 workflow 文件（含 `actions/cache` + `fetch-depth: 0`）
8. 39 个单元测试全部通过

### 2026-02-09: 待完成
1. Docker 构建验证
2. 推送到 GitHub 仓库
3. 真实仓库 Action 端到端测试

## 发布计划：GitHub Action（Marketplace）

### 商业模式
- BYOK（Bring Your Own Key）：用户自带 LLM + Embedding API Key（支持任意 OpenAI 兼容服务）
- 零运营成本：Action 跑在用户的 GitHub Runner 上
- 定价：Free（BYOK）+ Pro（$19-29/月，含 API 额度）

### 用户接入流程
1. 在仓库添加 `.github/workflows/pr-pilot.yml`
2. 在 Settings > Secrets 配置 `LLM_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`
3. 提 PR 自动触发审查

### 竞品参考
- CodeRabbit: $12/用户/月
- Codacy: $15/用户/月
- Qodo (PR-Agent): $19/用户/月
- **PR-Pilot 的四维分析（RAG + 调用图 + 历史 + 克隆）在技术深度上超过以上竞品**
