from services.local_llm import LocalLLMService
from utils.boardgame_utils import ConfigLoader

# 1. 載入店務資訊 (給 Router 用)
store_info_loader = ConfigLoader("config/store_info.json")
store_info = store_info_loader.load()

# 2. 初始化 Local LLM 服務
llm_service = LocalLLMService(
    config_path="config/llm_config.json",
    prompts_dir="prompts"
)

# --- 模擬請求 ---
import asyncio

async def test():
    user_text = "廁所在哪？"
    
    # 測試分類
    print(f"User: {user_text}")
    result = await llm_service.classify(user_text, store_info)
    print(f"Result: {result}")
    
    if result["type"] == "UNKNOWN":
        # 測試 Joker
        joke = await llm_service.respond_joker(user_text)
        print(f"Joker: {joke}")

asyncio.run(test())