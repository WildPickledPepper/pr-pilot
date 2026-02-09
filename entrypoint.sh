#!/bin/bash
set -e

echo "=== PR-Pilot Code Review ==="

# --- 1. Extract PR info from GitHub Actions event ---
REPO_FULL_NAME="${GITHUB_REPOSITORY}"
PR_NUMBER=$(jq -r '.pull_request.number // .number' "$GITHUB_EVENT_PATH")

if [ -z "$PR_NUMBER" ] || [ "$PR_NUMBER" = "null" ]; then
    echo "Error: Could not determine PR number from event payload."
    exit 1
fi

echo "Repository: ${REPO_FULL_NAME}"
echo "PR Number: ${PR_NUMBER}"

# --- 2. Export configuration as environment variables ---
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
export DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}"

# Use workspace-relative paths so actions/cache can persist them
WORKSPACE="${GITHUB_WORKSPACE:-.}"
export CHROMA_DB_PATH="${WORKSPACE}/chroma_db"
export CALL_GRAPH_DIR="${WORKSPACE}/call_graphs"
export CO_CHANGE_DIR="${WORKSPACE}/co_change_data"
export CLONE_DATA_DIR="${WORKSPACE}/clone_data"

ANALYSIS_MODE="${INPUT_ANALYSIS_MODE:-two-stage}"
RETRIEVAL_MODE="${INPUT_RETRIEVAL_MODE:-precise}"
TOP_K="${INPUT_TOP_K:-5}"

# --- 3. Build knowledge base (indexer) ---
# Use --name to ensure collection name matches what main.py expects (repo short name)
REPO_SHORT_NAME=$(echo "${REPO_FULL_NAME}" | cut -d'/' -f2)
echo ""
echo "=== Phase 1: Building Knowledge Base ==="
python /app/indexer.py --path "${WORKSPACE}" --name "${REPO_SHORT_NAME}"

# --- 4. Run PR analysis ---
echo ""
echo "=== Phase 2: Analyzing PR ==="
python /app/main.py \
    --repo "${REPO_FULL_NAME}" \
    --pr "${PR_NUMBER}" \
    --analysis-mode "${ANALYSIS_MODE}" \
    --retrieval-mode "${RETRIEVAL_MODE}" \
    --top-k "${TOP_K}"

echo ""
echo "=== PR-Pilot Review Complete ==="
