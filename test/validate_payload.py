# validate_payload.py
import json

filename = "payload_to_debug.json"

print(f"--- Attempting to validate {filename} ---")

try:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 进一步检查关键结构
    if 'messages' in data and isinstance(data['messages'], list) and len(data['messages']) > 1:
        if isinstance(data['messages'][1], dict) and 'content' in data['messages'][1]:
            print("\n✅ SUCCESS: The file is a valid JSON and has the correct structure.")
            print("This means the Python object was created correctly.")
        else:
            print("\n❌ FAILURE: The JSON is valid, but the structure of 'messages[1]' is incorrect.")
            print(f"Type of messages[1]: {type(data['messages'][1])}")
    else:
        print("\n❌ FAILURE: The JSON is valid, but is missing the expected 'messages' structure.")

except json.JSONDecodeError as e:
    print(f"\n❌ CRITICAL FAILURE: The file is NOT a valid JSON.")
    print(f"This is the root cause. The data was corrupted before being sent.")
    print(f"Error details: {e}")
except FileNotFoundError:
    print(f"\n❌ ERROR: The file '{filename}' was not found. Please run main.py first to generate it.")