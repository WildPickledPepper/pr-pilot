# send_payload_test.py
import json
import openai
import config  # 我们需要 config 来获取 API 密钥

print("--- Starting the Ultimate Payload Sending Test ---")
print("This script will read 'payload_to_debug.json' and send its exact contents to the API.")

# 1. 初始化 OpenAI 客户端 (和 deepseek.py 中完全一样)
try:
    client = openai.OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1"
    )
    print("OpenAI client initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize OpenAI client: {e}")
    exit()

# 2. 读取并加载我们已经验证过的 JSON 文件
try:
    with open("payload_to_debug.json", "r", encoding="utf-8") as f:
        # json.load 会把它直接解析成一个 Python 字典
        payload_data = json.load(f)
    print("Successfully loaded 'payload_to_debug.json'.")
except Exception as e:
    print(f"❌ Failed to read or parse the payload file: {e}")
    exit()

# 3. 终极对决：直接使用加载的数据调用 API
print("\nAttempting to send the exact payload to DeepSeek API...")
try:
    # `**payload_data` 是一个非常 Pythonic 的写法
    # 它会把字典 {'model': '...', 'messages': [...], ...}
    # 自动解包成 `model='...', messages=[...], ...` 这样的关键字参数
    response = client.chat.completions.create(**payload_data)

    analysis = response.choices[0].message.content
    
    print("\n--- ✅ ULTIMATE TEST SUCCEEDED! ---")
    print("The API accepted the payload without any issues.")
    print("\n--- AI Response ---")
    print(analysis)

except Exception as e:
    print("\n--- ❌ ULTIMATE TEST FAILED! ---")
    print("The error occurred even when sending the valid JSON file directly.")
    print("This is the definitive proof that the bug is inside the OpenAI library's handling of large requests.")
    print("\n--- Error Details ---")
    print(e)