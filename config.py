# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- GitHub Settings ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# --- LLM Settings (Analysis, OpenAI-compatible) ---
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# --- Embedding Settings (RAG, OpenAI-compatible) ---
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1").rstrip("/")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# --- Analysis Settings ---
MAX_FILES_TO_REVIEW = int(os.getenv("MAX_FILES_TO_REVIEW", "10"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# --- Data Directory Settings ---
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CALL_GRAPH_DIR = os.getenv("CALL_GRAPH_DIR", "./call_graphs")
CO_CHANGE_DIR = os.getenv("CO_CHANGE_DIR", "./co_change_data")
CLONE_DATA_DIR = os.getenv("CLONE_DATA_DIR", "./clone_data")

# --- Language Support Settings ---
SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "python,c,cpp,java,go,javascript,typescript,rust,ruby,php,csharp,kotlin,scala,lua,bash,zig").split(",")

# --- Tool Paths ---
PMD_HOME = os.getenv("PMD_HOME", os.path.join(os.path.dirname(__file__), "tools", "pmd-bin-7.18.0-SNAPSHOT"))
