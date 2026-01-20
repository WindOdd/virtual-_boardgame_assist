"""
分析 semantic_routes.yaml 中的誤判風險
測試簡單關鍵字是否容易誤觸
"""

import yaml
from pathlib import Path

def analyze_false_positive_risk():
    """分析誤判風險"""

    config_dir = Path(__file__).parent.parent / "config"
    semantic_routes_path = config_dir / "semantic_routes.yaml"

    with open(semantic_routes_path, 'r', encoding='utf-8') as f:
        routes = yaml.safe_load(f)

    print("=" * 80)
    print("誤判風險分析")
    print("=" * 80)
    print()

    # 定義桌遊相關測試案例
    test_cases_boardgame = [
        ("全力衝廁的規則是什麼", "RULES", "討論桌遊"),
        ("我想玩全力衝廁", "RULES", "詢問桌遊"),
        ("全力衝廁好玩嗎", "RULES", "詢問評價"),
        ("全力衝廁怎麼玩", "RULES", "詢問玩法"),
        ("店裡有賣全力衝廁嗎", "STORE_PRICING", "詢問販售"),
        ("網路奇兵的規則", "RULES", "討論桌遊"),
        ("這個遊戲需要連網路嗎", "RULES", "詢問機制"),
        ("有沒有網路連線的桌遊", "RULES", "詢問遊戲類型"),
    ]

    # 定義真實店務查詢案例
    test_cases_store = [
        ("廁所在哪", "STORE_TOILET", "店務查詢"),
        ("我要上廁所", "STORE_TOILET", "店務查詢"),
        ("wifi密碼是多少", "STORE_WIFI", "店務查詢"),
        ("網路連不上", "STORE_WIFI", "店務查詢"),
    ]

    # 分析短關鍵字
    print("📊 短關鍵字分析（可能造成誤判）")
    print("=" * 80)
    print()

    risky_keywords = {}

    for intent, anchors in routes.items():
        if not isinstance(anchors, list):
            continue

        short_keywords = [a for a in anchors if len(a) <= 4]
        if short_keywords:
            risky_keywords[intent] = short_keywords

            print(f"Intent: {intent}")
            print(f"  風險關鍵字 (≤4字): {short_keywords}")
            print(f"  風險等級: {'⚠️ 高' if len(short_keywords) > 3 else '🟡 中'}")
            print()

    # 模擬誤判情境
    print("=" * 80)
    print("🎮 模擬測試案例")
    print("=" * 80)
    print()

    print("情境 1: 討論桌遊（不應觸發店務 Intent）")
    print("-" * 80)
    for query, expected, description in test_cases_boardgame:
        # 檢查是否包含風險關鍵字
        potential_intents = []
        for intent, keywords in risky_keywords.items():
            for kw in keywords:
                if kw in query:
                    potential_intents.append((intent, kw))

        if potential_intents:
            print(f"⚠️  '{query}'")
            print(f"    期望: {expected} ({description})")
            print(f"    風險: 可能誤判為", end=" ")
            for intent, kw in potential_intents:
                print(f"{intent} (含關鍵字:'{kw}')", end=" ")
            print()
        else:
            print(f"✅ '{query}' - 無誤判風險")
        print()

    print("=" * 80)
    print("情境 2: 店務查詢（應該命中）")
    print("-" * 80)
    for query, expected, description in test_cases_store:
        print(f"✅ '{query}' → {expected} ({description})")
    print()

    # 建議
    print("=" * 80)
    print("💡 優化建議")
    print("=" * 80)
    print()

    print("方案 1: 移除過短關鍵字（推薦）")
    print("  - 移除 ≤3 字的單字關鍵字（如 '廁所', '網路', 'wifi'）")
    print("  - 保留完整問句（如 '廁所在哪', 'wifi密碼是多少'）")
    print("  - 優點: 降低誤判，依然保持高召回率")
    print("  - 缺點: 極短查詢（如 '廁所？'）可能 FastPath miss")
    print()

    print("方案 2: 提高 threshold（不推薦）")
    print("  - 從 0.85 提高到 0.88-0.90")
    print("  - 優點: 提高精確度")
    print("  - 缺點: 降低整體命中率，回到原問題")
    print()

    print("方案 3: 依賴 LLM Router 修正（現狀）")
    print("  - FastPath 誤判後，LLM Router 看到完整上下文會修正")
    print("  - 優點: 無需修改配置")
    print("  - 缺點: 誤判時會增加延遲和成本")
    print()

    print("方案 4: 混合策略（最佳）")
    print("  - 移除 1-2 字關鍵字")
    print("  - 保留 3-4 字短語和完整問句")
    print("  - 依賴上下文：如果 history 有 RULES intent，降低店務 intent 權重")
    print("  - 需要改進 Pipeline 的 context awareness")
    print()

if __name__ == "__main__":
    analyze_false_positive_risk()
