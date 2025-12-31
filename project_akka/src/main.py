"""
Project Akka - FastAPI Server
Exposes the pipeline as a REST API for iPad/Client.
"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Import 您的 Pipeline 工廠函式
from pipeline import create_pipeline
from services.discovery import DiscoveryService
# 設定 Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("akka_server")

discovery_service = None

app = FastAPI(title="Project Akka API v9.6")

# 初始化 Pipeline (全域變數，啟動時載入一次)
pipeline = create_pipeline()

# --- 定義資料模型 (Data Models) ---
class ChatRequest(BaseModel):
    user_input: str
    # 接收 Client 傳來的完整歷史 (包含 intent)
    history: Optional[List[Dict[str, Any]]] = [] 
    # [NEW] 接收遊戲狀態 (如 {"game_name": "Carcassonne"})
    game_context: Optional[Dict[str, Any]] = {} 

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    source: str

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Akka Server Starting...")
    global discovery_service
    discovery_service = DiscoveryService()
    discovery_service.start()
    logger.info("✅ Discovery Service launched")
    # 可以在這裡預熱模型
    pass
@app.on_event("shutdown")
async def shutdown_event():
    if discovery_service:
        discovery_service.stop()
        logger.info("✅ Discovery Service stopped")
# --- [MODIFIED] API 1: 取得支援的遊戲列表 ---
@app.get("/api/games")
async def get_supported_games():
    """
    透過 DataManager 取得遊戲列表
    """
    try:
        # 直接使用 Pipeline 內的 DataManager，避免重複讀取檔案
        games_list = pipeline.data_manager.list_games()
        
        response_data = []
        for game in games_list:
            # 組合簡單的描述 (從 metadata 提取)
            meta = game.metadata
            desc_parts = []
            if "players" in meta: desc_parts.append(f"{meta['players']} players")
            if "playtime" in meta: desc_parts.append(meta['playtime'])
            description = ", ".join(desc_parts) if desc_parts else "No description"

            response_data.append({
                "id": game.id,
                "name": game.display_name,
                "description": description,
                # [關鍵修正] 加入這行，Client 才知道這個遊戲是否支援 STT 注入
                "enable_stt_injection": game.enable_stt_injection 
            })
            
        return {"games": response_data}
        
    except Exception as e:
        logger.error(f"Error getting games list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- [MODIFIED] API 2: 取得 Whisper 修正關鍵字 ---
@app.get("/api/keywords/{game_id}")
async def get_stt_keywords(game_id: str):
    """
    透過 DataManager 取得 STT 關鍵字
    DataManager 會自動處理 enable_stt_injection 的判斷
    """
    try:
        # DataManager 會回傳 List[str] 或 None (如果找不到或未啟用)
        keywords = pipeline.data_manager.get_stt_keywords(game_id)
        
        if keywords is None:
            # 找不到遊戲，或是該遊戲設定 enable_stt_injection: false
            logger.info(f"Keywords not found or disabled for {game_id}")
            keywords = []
            
        return {
            "game_id": game_id,
            "keywords": keywords,
            # 提供給 Whisper 使用的 Prompt String (用逗號分隔)
            "prompt_string": ", ".join(keywords)
        }
    except Exception as e:
        logger.error(f"Error reading keywords: {e}")
        return {"game_id": game_id, "keywords": [], "prompt_string": ""}
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    主要對話接口
    Client 需傳入: {"user_input": "...", "history": [...], "game_context": {...}}
    """
    logger.info(f"📨 Request: {request.user_input} | Context: {request.game_context}")
    
    try:
        # 呼叫 Pipeline 處理
        result = await pipeline.process(
            user_input=request.user_input,
            history=request.history,
            game_context=request.game_context
        )
        
        return ChatResponse(
            response=result.response,
            intent=result.intent or "UNKNOWN",
            confidence=result.confidence,
            source=result.source
        )
    except Exception as e:
        logger.error(f"❌ Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # 啟動 Server，監聽所有 IP
    uvicorn.run(app, host="0.0.0.0", port=8000)