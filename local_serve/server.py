import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel

from services.discovery import DiscoveryService
from services.filter import FilterService
from services.game_data import GameDataService
from services.local_llm import LocalLLMService
from services.gemini_rag import GeminiRAGService
from utils.boardgame_utils import ConfigLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("Server")

app = FastAPI(title="Board Game Assistant v4.3")
services = {}
store_info = {}

class AskRequest(BaseModel):
    table_id: str
    session_id: str
    game_name: Optional[str] = None
    user_text: str
    history: List[Dict[str, str]] = []

class AskResponse(BaseModel):
    answer: str
    source: str
    category: str
    hint: Optional[str] = None
    error: Optional[Dict[str, str]] = None

@app.on_event("startup")
async def startup():
    global store_info
    logger.info("🚀 Server Starting...")
    try:
        store_info = ConfigLoader("config/store_info.json").load()
    except:
        store_info = {}

    services["game_data"] = GameDataService("rules/_index.yaml")
    services["filter"] = FilterService("config/safety_filter.yaml")
    services["local_llm"] = LocalLLMService("config/llm_config.json")
    
    if os.getenv("GEMINI_API_KEY"):
        services["gemini"] = GeminiRAGService(os.getenv("GEMINI_API_KEY"), "config/gemini_config.yaml")
    else:
        logger.warning("⚠️ No GEMINI_API_KEY found")

    services["discovery"] = DiscoveryService(port=37020, api_port=8000)
    services["discovery"].start()

@app.on_event("shutdown")
async def shutdown():
    if "discovery" in services:
        services["discovery"].stop()

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    user_text = req.user_text
    
    # 1. Router
    kb_str = services["game_data"].get_knowledge_str()
    router_res = await services["local_llm"].classify(user_text, store_info, kb_str)
    category = router_res.get("type", "UNKNOWN")
    
    # 2. Filter
    filter_res = services["filter"].check(user_text, category, req.game_name)
    if filter_res:
        return AskResponse(**filter_res)

    # 3. Logic Dispatch
    if category == "GAME":
        if "gemini" not in services:
            return AskResponse(answer="雲端未連線", source="SYSTEM", category="GAME", error={"code": "NO_API"})
            
        target_game = services["game_data"].get_game_by_name(req.game_name)
        hint = None
        
        if not target_game:
            detected = services["game_data"].detect_game_name(user_text)
            if detected:
                hint = f"建議選擇遊戲：{detected}"
        
        fname = target_game["filename"] if target_game else None
        gname = target_game["name"] if target_game else "通用"
        
        res = await services["gemini"].query(user_text, fname, gname, req.history)
        return AskResponse(answer=res["answer"], source=res["source"], category="GAME", hint=hint)

    elif category == "STORE":
        return AskResponse(answer=router_res.get("content"), source="LOCAL_STORE", category="STORE")
    
    elif category == "POLITICAL":
        return AskResponse(answer="不談政治", source="FILTER", category="POLITICAL")
        
    else:
        res = await services["local_llm"].respond_joker(user_text)
        return AskResponse(answer=res["answer"], source="LOCAL_JOKER", category="UNKNOWN")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
