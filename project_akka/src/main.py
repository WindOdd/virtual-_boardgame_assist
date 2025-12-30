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