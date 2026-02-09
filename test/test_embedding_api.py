# test_embedding_api_final.py (基于你的官方文档)

import os
from openai import OpenAI
from dotenv import load_dotenv

# 1. 加载环境变量
print("Loading .env file to get API key and Base URL...")
load_dotenv()

# 2. 从 .env 文件读取配置
key = os.getenv("EMBEDDING_API_KEY")
base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")

print("\n--- Configuration Check ---")
print(f"Base URL being used: {base_url}")
print(key)
if key:
    print(f"API Key found: {key[:5]}...{key[-4:]}")
else:
    print("FATAL ERROR: EMBEDDING_API_KEY not found in .env file!")
    exit() # 如果没有key，直接退出
print("--------------------------\n")

# 3. 完全按照你的文档示例来初始化和定义函数
try:
    print("Initializing OpenAI client exactly as per the documentation...")
    client = OpenAI(
        base_url=base_url,
        api_key=key,
        timeout=180  # 设置超时时间为30秒
    )
    print("Client initialized.")

    def get_embedding(text, model="text-embedding-3-small"):
       print(f"Sending request to get embedding for text: '{text}'")
       text = text.replace("\n", " ")
       # 下面这行就是核心的API调用
       response = client.embeddings.create(input=[text], model=model)
       print("API call successful, processing response...")
       return response.data[0].embedding

    # 4. 调用函数并打印结果
    test_text = "Hello, world!"
    embedding_vector = get_embedding(test_text)

    print("\n✅ --- SUCCESS! --- ✅")
    print("The API call was successful.")
    print(f"Received an embedding vector with {len(embedding_vector)} dimensions.")
    print(f"First 5 dimensions: {embedding_vector[:5]}")

except Exception as e:
    print("\n❌ --- FAILED! --- ❌")
    print("The API call failed. See details below.")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Details: {e}")