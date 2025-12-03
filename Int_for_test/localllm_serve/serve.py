import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 引入自定義服務與工具
from services.discovery import DiscoveryService
from services.filter import FilterService
from services.game_data import GameDataService
from services.local_llm import LocalLLMService
from services.gemini_rag import GeminiRAGService
from utils.boardgame_utils import ConfigLoader

# ==================== 1. 系統初始化 ====================

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Server")

app = FastAPI(title="Board Game Voice Assistant", version="4.2.0")

# 全域服務容器 (Service Container)
services: Dict[str, Any] = {}
store_info: Dict[str, Any] = {}

# ==================== 2. 資料模型 (Pydantic Models) ====================

class ChatMessage(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    table_id: str
    session_id: str
    game_name: Optional[str] = None  # 當下遊戲名稱 (可能為 None)
    user_text: str
    history: List[ChatMessage] = []  # Client 維護的對話歷史

class AskResponse(BaseModel):
    answer: str
    source: str       # CLOUD_GEMINI, LOCAL_STORE, LOCAL_JOKER, FILTER, SYSTEM
    category: str     # GAME, STORE, POLITICAL, UNKNOWN
    hint: Optional[str] = None
    error: Optional[Dict[str, str]] = None

# ==================== 3. 生命週期管理 ====================

@app.on_event("startup")
async def startup_event():
    """系統啟動：初始化所有服務"""
    global store_info
    logger.info("🚀 系統啟動中...")

    # 1. 載入店務資訊 (ConfigLoader)
    try:
        store_loader = ConfigLoader("config/store_info.json")
        store_info = store_loader.load()
    except Exception as e:
        logger.error(f"❌ 載入店務資訊失敗: {e}")
        store_info = {}

    # 2. 初始化各項服務
    try:
        # A. 遊戲資料服務 (負責 YAML 索引與關鍵字)
        services["game_data"] = GameDataService("rules/_index.yaml")
        
        # B. 安全過濾服務 (負責黑白名單)
        services["filter"] = FilterService("config/safety_filter.yaml")
        
        # C. Local LLM (Ollama - Router & Joker)
        services["local_llm"] = LocalLLMService("config/llm_config.json")
        
        # D. Online LLM (Gemini - RAG)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            services["gemini"] = GeminiRAGService(api_key, "config/gemini_config.yaml")
        else:
            logger.warning("⚠️ 未設定 GEMINI_API_KEY，RAG 功能將無法使用")

        # E. UDP 服務發現 (最後啟動)
        # 讓 Client 能找到我們，並回傳配置參數
        services["discovery"] = DiscoveryService(port=37020, api_port=8000)
        services["discovery"].start()
        
        logger.info("✅ 所有服務初始化完成")

    except Exception as e:
        logger.critical(f"❌ 服務啟動失敗: {e}")
        # 在生產環境中可能需要 raise e 來終止啟動，但在 POC 階段可先保留

@app.on_event("shutdown")
async def shutdown_event():
    """系統關閉：清理資源"""
    logger.info("🛑 系統關閉中...")
    
    if "discovery" in services:
        services["discovery"].stop()
        logger.info("UDP 服務已停止")

# ==================== 4. 核心 API ====================

@app.post("/ask", response_model=AskResponse)
async def ask_endpoint(req: AskRequest):
    """
    處理使用者提問
    Pipeline: Router -> Filter -> Logic Dispatch
    """
    user_text = req.user_text
    current_game = req.game_name
    
    # 準備 Router 需要的知識 (全域遊戲關鍵字)
    kb_str = services["game_data"].get_knowledge_str()

    # --- Step 1: 意圖路由 (Router) ---
    # 使用 Local LLM 判斷意圖 (GAME, STORE, POLITICAL, UNKNOWN)
    router_result = await services["local_llm"].classify(user_text, store_info, kb_str)
    category = router_result.get("type", "UNKNOWN")
    
    logger.info(f"[{req.table_id}] Input: '{user_text}' | Game: {current_game} | Router: {category}")

    # --- Step 2: 安全過濾 (Post-Routing Filter) ---
    # 根據 Router 結果決定過濾強度
    # 若是 GAME，使用寬鬆模式 (允許殺、刺客)；否則使用嚴格模式
    filter_res = services["filter"].check(user_text, category, current_game)
    if filter_res:
        logger.info(f"🚫 請求被過濾攔截: {user_text}")
        return AskResponse(
            answer=filter_res["answer"],
            source=filter_res["source"],
            category=filter_res["category"]
        )

    # --- Step 3: 邏輯分流 (Logic Dispatch) ---
    
    # Case A: 遊戲規則問題 (GAME)
    if category == "GAME":
        if "gemini" not in services:
            return AskResponse(
                answer="抱歉，雲端大腦未連線，無法查詢規則。",
                source="SYSTEM_ERROR",
                category="GAME",
                error={"code": "NO_GEMINI", "message": "API Key missing"}
            )

        # 1. 確定要查哪款遊戲
        target_game_data = None
        hint_msg = None
        
        if current_game:
            # Client 有指定遊戲，直接查表
            target_game_data = services["game_data"].get_game_by_name(current_game)
        else:
            # Client 沒指定 (Idle)，嘗試從對話偵測
            # 這邊假設 get_game_by_name 也能處理偵測邏輯，或是 game_data 有 detect 方法
            # 這裡簡化：若沒指定，就不掛載特定規則，讓 Gemini 自由回答
            # 但我們可以給個提示
            detected_name = services["game_data"].detect_game_name(user_text)
            if detected_name:
                hint_msg = f"建議選擇遊戲：{detected_name}"
        
        # 2. 呼叫 Gemini RAG
        # 若 target_game_data 存在，傳入 filename；否則傳入 None (通用模式)
        rule_filename = target_game_data["filename"] if target_game_data else None
        game_display_name = target_game_data["name"] if target_game_data else "通用桌遊知識"

        rag_result = await services["gemini"].query(
            user_text=user_text,
            rule_filename=rule_filename,
            game_name=game_display_name,
            history=req.history
        )
        
        return AskResponse(
            answer=rag_result["answer"],
            source=rag_result["source"],
            category="GAME",
            hint=hint_msg,
            error=None
        )

    # Case B: 店務問題 (STORE)
    elif category == "STORE":
        return AskResponse(
            answer=router_result.get("content", "詳細資訊請洽櫃台人員。"),
            source="LOCAL_STORE",
            category="STORE"
        )

    # Case C: 政治/敏感 (POLITICAL) - Router 直接判定的
    elif category == "POLITICAL":
        return AskResponse(
            answer="抱歉，我們這裡只聊桌遊，不談政治喔！",
            source="FILTER_ROUTER",
            category="POLITICAL"
        )

    # Case D: 未知/閒聊 (UNKNOWN) -> Joker
    else:
        joker_res = await services["local_llm"].respond_joker(user_text)
        return AskResponse(
            answer=joker_res["answer"],
            source=joker_res["source"],
            category="UNKNOWN"
        )

# ==================== 5. 啟動入口 ====================

if __name__ == "__main__":
    import uvicorn
    # 使用 0.0.0.0 允許外部連線
    uvicorn.run(app, host="0.0.0.0", port=8000)