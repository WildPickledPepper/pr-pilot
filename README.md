# PR-Pilot

**AI-powered code review for GitHub Pull Requests.**

Four-dimensional analysis: semantic search (RAG), architectural dependency chains, historical co-change patterns, and code clone detection. 16 languages with full AST analysis + universal text fallback for all other files. Runs as a GitHub Action — zero infrastructure, bring your own API keys.

**AI 驱动的 GitHub Pull Request 代码审查工具。**

四维分析引擎：语义检索（RAG）、架构依赖链、历史协同变更、代码克隆检测。16 种语言深度 AST 分析 + 通用文本兜底覆盖所有文件。以 GitHub Action 形式运行——零基础设施，自带 API Key 即可使用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](#quick-start-github-action) | [中文](#快速开始github-action)

---

## Quick Start (GitHub Action)

**1. Add the workflow file** to your repository at `.github/workflows/pr-pilot.yml`:

```yaml
name: PR-Pilot Code Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for co-change analysis

      - name: Cache PR-Pilot knowledge base
        uses: actions/cache@v4
        with:
          path: |
            chroma_db/
            call_graphs/
            co_change_data/
            clone_data/
          key: pr-pilot-${{ github.repository }}-${{ hashFiles('**/*.py', '**/*.java', '**/*.go', '**/*.js', '**/*.ts', '**/*.c', '**/*.cpp', '**/*.rs', '**/*.rb', '**/*.php', '**/*.cs', '**/*.kt', '**/*.scala', '**/*.lua', '**/*.sh', '**/*.zig') }}
          restore-keys: |
            pr-pilot-${{ github.repository }}-

      - name: Run PR-Pilot
        uses: WildPickledPepper/pr-pilot@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          llm_api_key: ${{ secrets.LLM_API_KEY }}
          llm_base_url: ${{ secrets.LLM_BASE_URL }}
          embedding_api_key: ${{ secrets.EMBEDDING_API_KEY }}
          embedding_base_url: ${{ secrets.EMBEDDING_BASE_URL }}
          # llm_model: 'deepseek-chat'                        # Optional
          # embedding_model: 'text-embedding-3-small'          # Optional
          # analysis_mode: 'two-stage'                         # Default
          # retrieval_mode: 'precise'                          # Default
          # top_k: '5'                                         # Default
```

**2. Add secrets** in your repo Settings > Secrets and variables > Actions:

| Secret | Required | Description |
|--------|----------|-------------|
| `LLM_API_KEY` | Yes | API key for the LLM (OpenAI-compatible) |
| `LLM_BASE_URL` | No | Custom endpoint for LLM API (default: `https://api.openai.com/v1`) |
| `EMBEDDING_API_KEY` | Yes | API key for embedding API (OpenAI-compatible) |
| `EMBEDDING_BASE_URL` | No | Custom endpoint for embedding API (default: `https://api.openai.com/v1`) |

**3. Open a Pull Request** — PR-Pilot will automatically post a review comment.

---

## Four-Dimensional Analysis

| Dimension | What it does | How |
|-----------|-------------|-----|
| **Semantic (RAG)** | Finds related code across the entire codebase | Vector similarity search via ChromaDB + OpenAI Embeddings |
| **Architectural** | Traces function call chains to detect ripple effects | Static call graphs via pyan (Python) and tree-sitter (15 languages) |
| **Historical** | Warns when frequently co-changed files are missed | Git history mining via PyDriller |
| **Clone** | Flags duplicated code that should be updated together | PMD/CPD clone detection |

---

## Supported Languages

### Tier 1 — Full 4D Analysis (16 languages)

Deep AST parsing with function-level chunking, call graph generation, and clone detection.

| Language | AST Parsing | Call Graph | Clone Detection | Extensions |
|----------|------------|------------|-----------------|------------|
| Python | `ast` module | pyan (.dot) | PMD/CPD | `.py` |
| C | tree-sitter | tree-sitter (.json) | PMD/CPD | `.c`, `.h` |
| C++ | tree-sitter | tree-sitter (.json) | PMD/CPD | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx` |
| Java | tree-sitter | tree-sitter (.json) | PMD/CPD | `.java` |
| Go | tree-sitter | tree-sitter (.json) | PMD/CPD | `.go` |
| JavaScript | tree-sitter | tree-sitter (.json) | PMD/CPD | `.js`, `.jsx`, `.mjs` |
| TypeScript | tree-sitter | tree-sitter (.json) | PMD/CPD | `.ts`, `.tsx` |
| Rust | tree-sitter | tree-sitter (.json) | — | `.rs` |
| Ruby | tree-sitter | tree-sitter (.json) | PMD/CPD | `.rb` |
| PHP | tree-sitter | tree-sitter (.json) | PMD/CPD | `.php` |
| C# | tree-sitter | tree-sitter (.json) | PMD/CPD | `.cs` |
| Kotlin | tree-sitter | tree-sitter (.json) | PMD/CPD | `.kt`, `.kts` |
| Scala | tree-sitter | tree-sitter (.json) | PMD/CPD | `.scala` |
| Lua | tree-sitter | tree-sitter (.json) | PMD/CPD | `.lua` |
| Bash | tree-sitter | tree-sitter (.json) | — | `.sh`, `.bash` |
| Zig | tree-sitter | tree-sitter (.json) | — | `.zig` |

### Tier 2 — Universal Text Fallback

All other non-binary text files (Markdown, YAML, TOML, Dart, SQL, config files, etc.) are automatically indexed using paragraph-based chunking. Tier 2 files support:

- **Semantic search (RAG)** — find related content across the codebase
- **Historical co-change analysis** — detect co-change patterns in git history

Binary files (images, archives, executables, etc.) are automatically skipped.

Data-driven architecture: adding a new Tier 1 language requires only a grammar configuration — no new parsing code.

---

## Two-Stage LLM Architecture

**Stage 1 — Analysts:** For each RAG-retrieved code snippet, an analyst LLM evaluates its relationship to the PR changes and assigns a risk score.

**Stage 2 — Chief Architect:** Synthesizes all analyst reports, dependency chains, historical warnings, and clone alerts into a final review.

This produces more thorough reviews than a single-prompt approach, especially for complex PRs.

---

## CLI Usage (Local Development)

```bash
# Clone and set up
git clone https://github.com/WildPickledPepper/pr-pilot.git
cd pr-pilot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Fill in your API keys

# Build knowledge base for a repo
python indexer.py --repo "owner/repo"

# Review a PR (dry-run saves to reviews/ instead of posting)
python main.py --repo "owner/repo" --pr 123 --dry-run

# Full options
python main.py --repo "owner/repo" --pr 123 \
  --analysis-mode two-stage \
  --retrieval-mode precise \
  --top-k 5
```

### CLI Options

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--analysis-mode` | `single`, `two-stage` | `two-stage` | Single-prompt or two-stage analyst architecture |
| `--retrieval-mode` | `diff`, `fast`, `precise` | `precise` | How to query the vector database |
| `--top-k` | 1-20 | 5 | Number of related code snippets to retrieve |
| `--dry-run` | flag | off | Save review locally instead of posting to GitHub |
| `--full` | flag (indexer) | off | Force full rebuild of the knowledge base |

### Retrieval Modes

- **`diff`** — Uses the PR diff text as the search query (fastest, least accurate)
- **`fast`** — Uses pre-computed vectors of changed functions (fast, good accuracy)
- **`precise`** — Generates new vectors from the updated function code (slowest, best accuracy)

---

## Incremental Indexing

PR-Pilot tracks file hashes to avoid redundant work:

- Only changed/added files are re-embedded on subsequent runs
- Deleted files are automatically cleaned from the vector database
- `actions/cache` persists the knowledge base across Action runs
- Use `--full` to force a complete rebuild

---

## Custom Review Rules

Add a `.pr-pilot.yml` file to the root of the target repository:

```yaml
rules:
  - "All public functions must have a docstring."
  - "Avoid mutable default arguments."
  - "Database queries must be wrapped in try/except."
```

---

## Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `github_token` | No | `${{ github.token }}` | GitHub token for API access |
| `deepseek_api_key` | Yes | — | DeepSeek API key |
| `openai_api_key` | Yes | — | OpenAI API key for embeddings |
| `openai_base_url` | No | `https://api.openai.com/v1` | Custom embedding API endpoint |
| `deepseek_base_url` | No | `https://api.deepseek.com/v1` | Custom DeepSeek endpoint |
| `analysis_mode` | No | `two-stage` | `single` or `two-stage` |
| `retrieval_mode` | No | `precise` | `diff`, `fast`, or `precise` |
| `top_k` | No | `5` | Number of snippets to retrieve |

---

## Tech Stack

- **LLM**: DeepSeek (OpenAI-compatible API)
- **Embeddings**: OpenAI text-embedding-3-small
- **Vector DB**: ChromaDB (local, persistent)
- **AST Parsing**: Python `ast` + tree-sitter (15 languages)
- **Call Graphs**: pyan (Python) + tree-sitter (15 languages)
- **Clone Detection**: PMD/CPD (13 languages)
- **History Analysis**: PyDriller
- **CI/CD**: GitHub Actions + Docker

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

# 中文文档

## 快速开始（GitHub Action）

**1. 添加 workflow 文件**，在你的仓库中创建 `.github/workflows/pr-pilot.yml`：

```yaml
name: PR-Pilot Code Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 完整历史，用于协同变更分析

      - name: Cache PR-Pilot knowledge base
        uses: actions/cache@v4
        with:
          path: |
            chroma_db/
            call_graphs/
            co_change_data/
            clone_data/
          key: pr-pilot-${{ github.repository }}-${{ hashFiles('**/*.py', '**/*.java', '**/*.go', '**/*.js', '**/*.ts', '**/*.c', '**/*.cpp', '**/*.rs', '**/*.rb', '**/*.php', '**/*.cs', '**/*.kt', '**/*.scala', '**/*.lua', '**/*.sh', '**/*.zig') }}
          restore-keys: |
            pr-pilot-${{ github.repository }}-

      - name: Run PR-Pilot
        uses: WildPickledPepper/pr-pilot@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          llm_api_key: ${{ secrets.LLM_API_KEY }}
          llm_base_url: ${{ secrets.LLM_BASE_URL }}
          embedding_api_key: ${{ secrets.EMBEDDING_API_KEY }}
          embedding_base_url: ${{ secrets.EMBEDDING_BASE_URL }}
          # llm_model: 'deepseek-chat'                        # 可选
          # embedding_model: 'text-embedding-3-small'          # 可选
          # analysis_mode: 'two-stage'                         # 默认值
          # retrieval_mode: 'precise'                          # 默认值
          # top_k: '5'                                         # 默认值
```

**2. 配置 Secrets**，进入仓库 Settings > Secrets and variables > Actions：

| Secret 名称 | 必填 | 说明 |
|-------------|------|------|
| `LLM_API_KEY` | 是 | LLM API 密钥（OpenAI 兼容格式，支持 DeepSeek/OpenAI 等） |
| `LLM_BASE_URL` | 否 | LLM API 地址（默认 `https://api.openai.com/v1`，支持代理） |
| `EMBEDDING_API_KEY` | 是 | Embedding API 密钥（OpenAI 兼容格式） |
| `EMBEDDING_BASE_URL` | 否 | Embedding API 地址（默认 `https://api.openai.com/v1`，支持代理） |

**3. 提一个 Pull Request**——PR-Pilot 会自动在 PR 下发布审查评论。

---

## 四维分析引擎

| 维度 | 功能 | 实现方式 |
|------|------|---------|
| **语义分析（RAG）** | 在全仓库中检索与 PR 变更语义相关的代码 | ChromaDB 向量数据库 + OpenAI Embedding |
| **架构分析（依赖链）** | 追踪函数调用链，检测变更的波及效应 | pyan（Python）+ tree-sitter（15 种语言）静态调用图 |
| **历史分析（协同变更）** | 警告经常一起修改但这次遗漏的文件 | PyDriller 挖掘 Git 提交历史 |
| **克隆分析（代码基因）** | 标记应该同步更新的重复代码 | PMD/CPD 代码克隆检测（13 种语言） |

---

## 支持语言

### Tier 1 — 深度 4D 分析（16 种语言）

基于 AST 的函数级分块，支持调用图生成和克隆检测。

| 语言 | AST 解析 | 调用图 | 克隆检测 | 文件扩展名 |
|------|----------|--------|---------|-----------|
| Python | `ast` 模块 | pyan (.dot) | PMD/CPD | `.py` |
| C | tree-sitter | tree-sitter (.json) | PMD/CPD | `.c`, `.h` |
| C++ | tree-sitter | tree-sitter (.json) | PMD/CPD | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx` |
| Java | tree-sitter | tree-sitter (.json) | PMD/CPD | `.java` |
| Go | tree-sitter | tree-sitter (.json) | PMD/CPD | `.go` |
| JavaScript | tree-sitter | tree-sitter (.json) | PMD/CPD | `.js`, `.jsx`, `.mjs` |
| TypeScript | tree-sitter | tree-sitter (.json) | PMD/CPD | `.ts`, `.tsx` |
| Rust | tree-sitter | tree-sitter (.json) | — | `.rs` |
| Ruby | tree-sitter | tree-sitter (.json) | PMD/CPD | `.rb` |
| PHP | tree-sitter | tree-sitter (.json) | PMD/CPD | `.php` |
| C# | tree-sitter | tree-sitter (.json) | PMD/CPD | `.cs` |
| Kotlin | tree-sitter | tree-sitter (.json) | PMD/CPD | `.kt`, `.kts` |
| Scala | tree-sitter | tree-sitter (.json) | PMD/CPD | `.scala` |
| Lua | tree-sitter | tree-sitter (.json) | PMD/CPD | `.lua` |
| Bash | tree-sitter | tree-sitter (.json) | — | `.sh`, `.bash` |
| Zig | tree-sitter | tree-sitter (.json) | — | `.zig` |

### Tier 2 — 通用文本兜底

所有其他非二进制文本文件（Markdown、YAML、TOML、Dart、SQL、配置文件等）会自动以段落分块方式索引。Tier 2 文件支持：

- **语义检索（RAG）** — 在全仓库中查找相关内容
- **历史协同变更分析** — 检测 Git 历史中的协同变更模式

二进制文件（图片、压缩包、可执行文件等）会自动跳过。

数据驱动架构：添加新 Tier 1 语言只需注册一份 grammar 配置，无需编写新的解析代码。

---

## 两阶段 LLM 架构

**第一阶段——分析员：** 对 RAG 检索到的每个代码片段，分析员 LLM 评估其与 PR 变更的关联性，输出风险评分和影响类型。

**第二阶段——总指挥：** 汇总所有分析员报告 + 依赖链 + 历史警告 + 克隆警告，一次调用 LLM 生成最终审查报告。

相比单次 Prompt，两阶段架构在复杂 PR 上能产出更深入的审查。

---

## CLI 用法（本地开发）

```bash
# 克隆并配置
git clone https://github.com/WildPickledPepper/pr-pilot.git
cd pr-pilot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # 填入你的 API Key

# 为目标仓库建立知识库
python indexer.py --repo "owner/repo"

# 审查 PR（dry-run 模式保存到本地，不发评论）
python main.py --repo "owner/repo" --pr 123 --dry-run

# 完整参数
python main.py --repo "owner/repo" --pr 123 \
  --analysis-mode two-stage \
  --retrieval-mode precise \
  --top-k 5
```

### 命令行参数

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--analysis-mode` | `single`, `two-stage` | `two-stage` | 单阶段或两阶段分析架构 |
| `--retrieval-mode` | `diff`, `fast`, `precise` | `precise` | 向量检索策略 |
| `--top-k` | 1-20 | 5 | 检索相关代码片段数量 |
| `--dry-run` | 开关 | 关 | 保存到本地而非发到 GitHub |
| `--full` | 开关（indexer） | 关 | 强制全量重建知识库 |

### 三种检索模式

- **`diff`** — 用 PR diff 文本作为查询（最快，精度最低）
- **`fast`** — 用变更函数的旧向量查询（较快，精度较好）
- **`precise`** — 用变更后的新函数代码实时生成向量查询（最慢，精度最高）

---

## 增量索引

PR-Pilot 通过文件 hash 追踪避免重复工作：

- 只对新增/修改的文件重新生成 Embedding
- 删除的文件自动从向量数据库清理
- `actions/cache` 跨 Action 运行持久化知识库
- 使用 `--full` 参数强制全量重建

---

## 自定义审查规则

在目标仓库根目录添加 `.pr-pilot.yml` 文件：

```yaml
rules:
  - "所有公开函数必须有文档字符串。"
  - "禁止使用可变默认参数。"
  - "数据库查询必须包在 try/except 中。"
```

---

## 技术栈

- **LLM**: DeepSeek（兼容 OpenAI API 格式）
- **Embedding**: OpenAI text-embedding-3-small
- **向量数据库**: ChromaDB（本地持久化）
- **AST 解析**: Python `ast` + tree-sitter（15 种语言）
- **调用图**: pyan（Python）+ tree-sitter（15 种语言）
- **克隆检测**: PMD/CPD（13 种语言）
- **历史分析**: PyDriller
- **CI/CD**: GitHub Actions + Docker

---

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
