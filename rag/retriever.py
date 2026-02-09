# pr_pilot/rag/retriever.py
import chromadb
from openai import OpenAI
import config
from typing import Any, Dict, List, Tuple, Optional
# --- 客户端初始化 ---
# 和 indexer.py 中保持一致
try:
    db_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    openai_client = OpenAI(
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        timeout=180.0  
    )
    print("RAG Retriever initialized successfully.")
except Exception as e:
    print(f"Failed to initialize RAG Retriever clients: {e}")
    db_client = None
    openai_client = None


def get_embedding(text: str, model=config.EMBEDDING_MODEL):
    """为查询文本生成 embedding."""
    if not openai_client:
        return None
    try:
        text = text.replace("\n", " ")
        return openai_client.embeddings.create(input=[text], model=model).data[0].embedding
    except Exception as e:
        print(f"Error getting embedding for query: {e}")
        return None


def retrieve_relevant_code(
    query_text: Optional[str], 
    repo_name: str, 
    n_results: int = 5, 
    query_embedding: Optional[List[float]] = None
) -> Tuple[List[str], List[Dict]]:
#  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<  函数签名修改 END >>>>>>>>>>>>>>>>>>>>>>>>>

    if not db_client:
        print("ChromaDB client not initialized. Skipping retrieval.")
        return [], []
    
    try:
        collection_name = repo_name.replace('/', '_').replace('.', '_').replace('-', '_')
        collection = db_client.get_collection(name=collection_name)
    except Exception as e:
        print(f"An error occurred while getting the collection: {e}")
        return [], []

    # 如果没有提供预计算的 embedding，则实时生成
    if not query_embedding:
        if not query_text:
            print("Error: Both query_text and query_embedding are None.")
            return [], []
        print("Generating new embedding for query text...")
        query_embedding = get_embedding(query_text)

    if not query_embedding:
        return [], []

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas"]
        )
        docs = results['documents'][0] if results and results['documents'] else []
        metas = results['metadatas'][0] if results and results['metadatas'] else []
        if not docs: return [], []
        return docs, metas
    except Exception as e:
        print(f"An error occurred during ChromaDB query: {e}")
        return [], []