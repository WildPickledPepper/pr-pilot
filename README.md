# 🚀 PR-Pilot: Your AI Co-pilot for Team Code Reviews

PR-Pilot is an open-source, self-hostable AI framework that acts as a "second pair of eyes" on your GitHub Pull Requests. It's not designed to replace human reviewers, but to augment them—handling the repetitive, time-consuming tasks and allowing your team to focus on what truly matters: building great software.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

### 🤔 Why PR-Pilot?

Modern code review is essential, but it's also a bottleneck. Senior engineers spend hours on routine checks, and junior engineers wait anxiously for feedback. Existing tools are often either simple linters that lack context, or closed-source SaaS products that are expensive and keep your code on third-party servers.

PR-Pilot is different. It's built on three core principles:

*   **🛡️ Self-Hosted & Secure:** Your code is your most valuable asset. PR-Pilot runs on your own infrastructure, so your source code never leaves your control.
*   **🧠 Global Context-Awareness:** Using the power of Retrieval-Augmented Generation (RAG), PR-Pilot doesn't just look at the *changes*—it understands the *entire codebase*. It builds a "brain" of your repository to detect code duplication, architectural inconsistencies, and potential side effects.
*   **🔧 Open & Customizable:** PR-Pilot's "brain" is a white box. You can define project-specific rules and best practices in a simple YAML file, teaching the AI what matters most to *your* team.

### ✨ Core Features

*   **Automated PR Analysis:** Generates a concise summary, lists key changes, and identifies potential issues for every PR.
*   **Just-in-Time Learning:** The first time you analyze a repository, PR-Pilot automatically and intelligently "learns" the entire codebase by building a vector knowledge base.
*   **Smart Global Context:** When reviewing a PR, it automatically finds and includes relevant code from other parts of the repository in its analysis, enabling deeper insights.
*   **Custom Review Rules:** Guide the AI's focus by defining your team's specific coding standards in a `.pr-pilot.yml` file.
*   **Intelligent Workflow:** It first checks if a PR is open and valid before triggering the expensive "learning" process, saving you time and API costs.
*   **Dry Run Mode:** Test the analysis on any public PR without actually posting a comment.

### ⚙️ How It Works

1.  **PR Check:** A lightweight check confirms the target Pull Request is open and valid.
2.  **Knowledge Check:** PR-Pilot checks if it already has a "brain" (vector index) for the repository.
3.  **Just-in-Time Indexing:** If no "brain" exists, it asks for permission to build one. It then scans the entire repository (either online via API or from a local clone), breaks down every function and class into "chunks," converts them into vectors using an Embedding model, and stores them in a local vector database (`ChromaDB`).
4.  **Context Augmentation (RAG):** It takes the code changes (the "diff") from the PR and uses them to search for the most semantically similar code chunks in its "brain."
5.  **Rich Prompt Generation:** It combines the PR title, description, diffs, and the retrieved global context into a rich, detailed prompt.
6.  **AI Analysis:** The prompt is sent to a powerful Large Language Model (e.g., DeepSeek, GPT-4) for review.
7.  **Report Generation:** The AI's response is formatted into a clean Markdown report and posted as a comment on the PR.

### 🏁 Getting Started

#### Prerequisites
*   Python 3.8+
*   Git

#### 1. Clone the Repository
```bash
git clone https://github.com/your-username/pr-pilot.git
cd pr-pilot
```

#### 2. Set Up a Virtual Environment
```bash
# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate
```

#### 3. Create `requirements.txt`
Create a file named `requirements.txt` in the root of the project and add the following dependencies:
```
PyGithub
openai
python-dotenv
PyYAML
chromadb
tiktoken
```

#### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 5. Configure Your Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Now, edit the `.env` file with your favorite editor and fill in your API keys:
```ini
# .env

# Your GitHub Personal Access Token with 'repo' scope
GITHUB_TOKEN="ghp_..."

# API Key for the LLM used for analysis (e.g., DeepSeek)
DEEPSEEK_API_KEY="sk-..."

# API Key and Base URL for the model used for embeddings (e.g., OpenAI compatible)
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.your-provider.com/v1"
```

### 🕹️ Usage

The primary entry point is `main.py`. It's designed to be simple and intuitive.

```bash
python main.py --repo "owner/repo-name" --pr <PR_NUMBER>
```

**Example (Dry Run):**
This will analyze the PR and save the review to a local file instead of posting to GitHub. This is the recommended way to test.

```bash
python main.py --repo "Textualize/rich" --pr 2780 --dry-run
```

The first time you run this for a new repository, it will prompt you to build the knowledge base. Just type `y` and press Enter.

### 🔧 Customization

To add project-specific review rules, create a `.pr-pilot.yml` file in the **root of the target repository** (the one you are analyzing, not in the PR-Pilot repo itself).

**Example `.pr-pilot.yml`:**
```yaml
# A list of rules for the AI to enforce during review.
rules:
  - "All public functions must have a docstring."
  - "Avoid using mutable default arguments in function definitions."
  - "Database queries should be wrapped in a try...except block to handle potential exceptions."
```

### 🗺️ Future Roadmap

PR-Pilot is actively being developed. Our future plans include:

*   **Phase 3: GitHub App Transformation:** Evolve from a command-line tool into a fully automated GitHub App that listens to webhook events (e.g., `pull_request.opened`).
*   **Phase 4: Easy Deployment:** Provide a `Dockerfile` for easy containerization and deployment on cloud services like Render or Fly.io.
*   **Smarter Chunking & Indexing:** Implement more advanced strategies for parsing different programming languages and handling huge files.
*   **Support for GitLab & Bitbucket:** Extend the `base.py` abstractions to support other popular Git providers.

###🤝 Contributing

Contributions are welcome! Whether it's bug reports, feature suggestions, or pull requests, your help is greatly appreciated. Please feel free to open an issue to discuss your ideas.

### 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.