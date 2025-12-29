"""
Integration Test for Rules Flow (Real API Call)
這是一個真實環境測試，會真的呼叫 Google Gemini API。
請確保您的環境變數中已有 GEMINI_API_KEY。
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# --- 1. 設定路徑以匯入 src 模組 ---
# 讓我們能 import src.pipeline
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pipeline import Pipeline

async def main():
    # --- 2. 環境檢查 ---
    print("🚀 開始執行真實整合測試 (Real Cloud Integration)...")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 錯誤：找不到環境變數 GEMINI_API_KEY")
        print("   請執行: export GEMINI_API_KEY='your_actual_api_key'")
        return

    # 設定 Log 讓我們看到 pipeline 內部的運作 (如規則書讀取)
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("integration_test")

    # --- 3. 初始化真實 Pipeline ---
    # 這會去讀取 config/ 和 data/ 下的所有檔案
    print("\n📦 初始化 Pipeline (Loading Real Configs & Data)...")
    pipeline = Pipeline()
    
    # 確保 Cloud LLM 載入成功
    if not pipeline.cloud_llm:
        print("❌ 錯誤：Cloud LLM 未初始化，請檢查 system_config.yaml 是否啟用了 gemini。")
        return

    # --- 4. 準備真實測試資料 ---
    # 假設我們要測「卡卡頌」的規則
    game_name = "Carcassonne"  # 必須對應 data/rules/Carcassonne.md 檔名 (或 registry ID)
    user_input = "要怎麼樣才能得分"
    
    # 模擬 iPad Client 傳來的 Context
    context = {
        "table_id": "TB001",
        "session_id": "SE001",
        "game_context": {
            "game_name": game_name
        },
        "history": [
            {"role": "user", "content": "這遊戲怎麼玩？", "intent": "RULES"},
            {"role": "assistant", "content": "這是一個拼板塊的遊戲...", "intent": "RULES"}
        ]
    }

    print(f"\n🧪 測試場景:")
    print(f"   Game: {game_name}")
    print(f"   Input: {user_input}")
    print("   Target: Google Gemini (Online)")
    print("\n⏳ 發送請求中 (這會花費幾秒鐘)...")

    # --- 5. 執行測試 (直接呼叫我們剛寫好的邏輯函式) ---
    try:
        # 直接呼叫 _handle_rules_query 以隔離 Router 的變因，專注測 RAG/LLM 流程
        # 注意：這是 private method，但在測試腳本中呼叫是為了驗證邏輯
        response, source = await pipeline._handle_rules_query(user_input, context)

        print("\n" + "="*40)
        print(f"✅ 測試成功！(Source: {source})")
        print("="*40)
        print("🤖 Akka (Gemini) 回答：")
        print(response)
        print("="*40)

        # 簡單驗證內容
        if "農夫" in response and ("分" in response or "躺" in response):
            print("\n✨ 語意驗證通過：回答包含了農夫規則的關鍵字。")
        else:
            print("\n⚠️ 語意驗證警告：回答似乎有點文不對題，請人工檢查。")

    except Exception as e:
        print(f"\n❌ 測試失敗 Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())