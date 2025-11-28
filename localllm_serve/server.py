import os
import json
import asyncio
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from ollama import Client as OllamaClient

# ==========================================
# 1. 全局設定
# ==========================================

# Local LLM 設定 (請確保 Docker 已經跑起來)
OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "qwen3:4b-instruct" # 統一使用同一個模型

# GPU 鎖 (確保一次只處理一個請求)
GPU_LOCK = asyncio.Lock()

# 路徑設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# 初始化 FastAPI 與 Ollama
app = FastAPI()
client = OllamaClient(host=OLLAMA_HOST)

# Request 資料結構
class ChatRequest(BaseModel):
    user_text: str
    table_id: str = "T01" # 預設值，POC 階段可不傳

# 固定回覆語句
POLITICAL_FIXED_REPLY = "抱歉,我們專注在桌遊話題上呦!有什麼遊戲問題可以問我~"

# ==========================================
# 2. 資料讀取函式 (動態載入)
# ==========================================

def load_json_file(filename):
    path = os.path.join(CONFIG_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

def load_text_file(filename):
    path = os.path.join(CONFIG_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return ""

def get_store_info_text():
    """將 JSON 店務資料轉為 LLM 易讀的文字"""
    data = load_json_file("store_info.json")
    if not data: return "暫無資訊"
    return "\n".join([f"- {k}: {v}" for k, v in data.items()])

def check_sensitive_keywords(text):
    """Python 層級的第一道過濾防線"""
    whitelist = load_json_file("game_whitelist.json")
    keywords = load_json_file("sensitive_keywords.json")
    
    # 1. 白名單放行
    for safe in whitelist:
        if safe in text: return False
    
    # 2. 黑名單攔截
    for word in keywords:
        if word in text: return True
        
    return False

# ==========================================
# 3. 核心 LLM 呼叫 (雙重人格)
# ==========================================

async def call_router_mode(user_text):
    """人格 A: 嚴肅分類員 (JSON Mode, Temp 0.1)"""
    
    # 1. 準備 Prompt
    raw_prompt = load_text_file("prompt_router.txt")
    store_info = get_store_info_text()
    system_prompt = raw_prompt.replace("{{STORE_INFO_BLOCK}}", store_info)
    
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_text}
    ]

    print(f"--- [Router] Processing: {user_text} ---")
    
    # 2. 呼叫 LLM (排隊)
    async with GPU_LOCK:
        try:
            response = client.chat(
                model=MODEL_NAME,
                messages=messages,
                format='json', # 強制 JSON
                options={
                    'temperature': 0.1, # 極度理性
                    'num_ctx': 4096,
                    'num_predict': 128  # 短輸出
                }
            )
            return response['message']['content']
        except Exception as e:
            print(f"LLM Error: {e}")
            return "{}"

async def call_joker_mode(user_text):
    """人格 B: 輕鬆閒聊 (Text Mode, Temp 0.7)"""
    
    # 1. 準備 Prompt
    system_prompt = load_text_file("prompt_joker.txt")
    
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_text}
    ]

    print(f"--- [Joker] Chatting: {user_text} ---")

    # 2. 呼叫 LLM (排隊)
    async with GPU_LOCK:
        try:
            response = client.chat(
                model=MODEL_NAME,
                messages=messages,
                # 不用 JSON format，讓它自然說話
                options={
                    'temperature': 0.7, # 增加創意與友善感
                    'num_ctx': 4096,
                    'num_predict': 64   # 限制長度，避免廢話
                }
            )
            return response['message']['content']
        except Exception as e:
            return "我現在有點累，請稍後再跟我聊天。"

# ==========================================
# 4. 主邏輯處理
# ==========================================

@app.post("/ask")
async def handle_ask(req: ChatRequest):
    user_text = req.user_text
    
    # --- Step 1: 關鍵字過濾 (Python Layer) ---
    if check_sensitive_keywords(user_text):
        print(f">>> [Filter] Keyword Blocked: {user_text}")
        return {
            "category": "POLITICAL",
            "answer": POLITICAL_FIXED_REPLY,
            "source": "FILTER_PY"
        }

    # --- Step 2: 意圖分類 (Router LLM) ---
    router_json_str = await call_router_mode(user_text)
    
    try:
        router_data = json.loads(router_json_str)
        category = router_data.get("type", "UNKNOWN")
        content = router_data.get("content", "")
    except:
        category = "UNKNOWN"
        content = ""
    
    print(f">>> [Router] Result: {category}")

    # --- Step 3: 分支處理 ---
    final_answer = ""
    source = "LOCAL_LLM"

    if category == "POLITICAL":
        # 雖然 Python 層擋過了，但如果 Router 也覺得是政治，再擋一次
        final_answer = POLITICAL_FIXED_REPLY
        source = "FILTER_LLM"

    elif category == "STORE":
        # Router 已經生成好答案了，直接用
        final_answer = content
        if not final_answer: # 防呆
            final_answer = "這部分請直接詢問櫃台人員喔。"

    elif category == "GAME":
        # 暫時不實作 Online LLM，回傳 Mock 訊息
        final_answer = "(系統訊息) 已識別為遊戲問題，準備轉接專業規則系統..." 
        source = "MOCK_ONLINE"

    else: # UNKNOWN
        # 進入 Joker 模式，進行友善回答
        final_answer = await call_joker_mode(user_text)
        source = "LOCAL_JOKER"

    return {
        "category": category,
        "answer": final_answer,
        "source": source
    }

# ==========================================
# 5. 啟動說明
# ==========================================
if __name__ == "__main__":
    print("請使用以下指令啟動 Server:")
    print("uvicorn server:app --host 0.0.0.0 --port 8000 --reload")