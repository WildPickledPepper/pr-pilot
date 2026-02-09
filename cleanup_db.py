# cleanup_db.py
import chromadb

# ！！！把这里换成你想要删除的仓库名！！！
REPO_NAME_TO_DELETE = "fastapi/fastapi" 
# ！！！---------------------------------！！！

print(f"--- Attempting to delete collection for '{REPO_NAME_TO_DELETE}' ---")

try:
    # 连接到数据库
    db_client = chromadb.PersistentClient(path="./chroma_db")

    # 把仓库名转换成 collection 名 (和 indexer.py 里保持一致)
    collection_name = REPO_NAME_TO_DELETE.replace('/', '_').replace('.', '_').replace('-', '_')

    # 执行删除操作
    db_client.delete_collection(name=collection_name)

    print(f"✅ Success: Collection '{collection_name}' has been deleted.")

except ValueError:
    print(f"ℹ️ Info: Collection for '{REPO_NAME_TO_DELETE}' not found. Nothing to do.")
except Exception as e:
    print(f"❌ Error: An unexpected error occurred: {e}")