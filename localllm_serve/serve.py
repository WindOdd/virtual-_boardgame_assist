import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# 導入我們寫好的服務
from services.local_llm import LocalLLMService
from services.online_llm_rag import GeminiRAGService
from utils.boardgame_utils import ConfigLoader

# 設定 Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Server")

app = FastAPI()

# ================= 環境變數與設定 =================

# ⚠️ 請確保環境變數有 GEMINI_API_KEY
# export GEMINI_API_KEY="你的_KEY"
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# ================= 初始化服務 =================

# 1. 載入店務資訊 (Local Router 用)
store_info = ConfigLoader("config/store_info.json").load()

# 2. 啟動 Local LLM (Router & Joker)
# 注意：在 Mac 上測試時，llm_config.json 的 device 記得改 "cpu"
local_llm = LocalLLMService(config_path="config/llm_config.json")

# 3. 啟動 Online LLM (Gemini RAG)
# 如果沒有 Key，這裡會報錯提醒
if GEMINI_KEY:
    gemini_service = GeminiRAGService(api_key=GEMINI_KEY)
else:
    logger.warning("⚠️ 未設定 GEMINI_API_KEY，Online 功能將無法使用！")
    gemini_service = None

# ================= API 定義 =================

class AskRequest(BaseModel):
    user_text: str
    game_name: Optional[str] = None # 前端若知道遊戲名可傳，不知道則為 None
    history: Optional[List[dict]] = []

@app.post("/ask")
async def ask_endpoint(req: AskRequest):
    """
    統一問答入口
    Flow: Router -> (Store/Joker) OR (Gemini)
    """
    user_text = req.user_text
    
    # --- 第一階段：Router 分類 (Local) ---
    router_result = await local_llm.classify(user_text, store_info)
    category = router_result.get("type", "UNKNOWN")
    logger.info(f"分類結果: {category} (Input: {user_text})")

    # --- 第二階段：分流處理 ---
    
    # Case 1: 遊戲問題 -> 呼叫 Gemini
    if category == "GAME":
        if gemini_service:
            # 如果前端沒傳 game_name，這裡可以嘗試從對話中解析，或預設 None
            # 這裡簡單處理：如果 router 判斷是 GAME，但我們不知道哪款，
            # 還是丟給 Gemini，讓 Gemini 根據上下文猜或反問。
            game_to_query = req.game_name 
            
            result = await gemini_service.query(
                game_name=game_to_query,
                user_question=user_text,
                history=req.history
            )
            return result
        else:
            return {"answer": "抱歉，雲端服務未設定。", "source": "SYSTEM"}

    # Case 2: 店務問題 -> Local 直接回
    elif category == "STORE":
        return {
            "answer": router_result.get("content", "詳細請詢問櫃台。"),
            "source": "LOCAL_STORE"
        }

    # Case 3: 政治 -> 拒絕
    elif category == "POLITICAL":
        return {
            "answer": "抱歉，我們這裡只聊桌遊，不談政治喔！",
            "source": "FILTER"
        }

    # Case 4: UNKNOWN -> Joker 閒聊
    else:
        joker_result = await local_llm.respond_joker(user_text, req.history)
        return joker_result

# ================= 啟動方式 =================
# export GEMINI_API_KEY="AIzaSy..."
# python server.py
# (若使用 uvicorn: uvicorn server:app --reload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)