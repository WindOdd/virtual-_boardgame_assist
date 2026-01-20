"""
分析 STORE_PRICING vs STORE_INTRO 的命名混淆問題
評估改為 STORE_FEE 的可行性
"""

import yaml
from pathlib import Path

def analyze_naming_confusion():
    """分析命名混淆風險"""

    config_dir = Path(__file__).parent.parent / "config"

    with open(config_dir / "store_info.yaml", 'r', encoding='utf-8') as f:
        store_info = yaml.safe_load(f)

    print("=" * 80)
    print("STORE_PRICING vs STORE_INTRO 命名混淆分析")
    print("=" * 80)
    print()

    # 提取實際回應內容
    pricing_responses = store_info.get("responses", {}).get("STORE_PRICING", [])
    intro_responses = store_info.get("responses", {}).get("STORE_INTRO", [])

    print("📊 當前配置分析")
    print("-" * 80)
    print()

    print("STORE_PRICING 實際內容:")
    for i, resp in enumerate(pricing_responses[:3], 1):
        print(f"  {i}. {resp}")
    print()

    print("STORE_INTRO 實際內容:")
    for i, resp in enumerate(intro_responses[:3], 1):
        print(f"  {i}. {resp}")
    print()

    # 分析混淆場景
    print("=" * 80)
    print("⚠️  潛在混淆場景")
    print("=" * 80)
    print()

    confusion_cases = [
        {
            "query": "這個遊戲賣多少錢？",
            "expected": "STORE_INTRO",
            "confused_with": "STORE_PRICING",
            "reason": "包含「多少錢」，但詢問的是商品價格，不是入場費"
        },
        {
            "query": "卡坦島多少錢？",
            "expected": "STORE_INTRO",
            "confused_with": "STORE_PRICING",
            "reason": "特定遊戲名稱 + 價格詢問 → 商品定價"
        },
        {
            "query": "你們有賣什麼？價格怎麼算？",
            "expected": "STORE_INTRO",
            "confused_with": "STORE_PRICING",
            "reason": "詢問商品種類和價格，不是場地費"
        },
        {
            "query": "平日多少錢？",
            "expected": "STORE_PRICING",
            "confused_with": "可能正確",
            "reason": "典型的入場費詢問，應該命中 STORE_PRICING"
        }
    ]

    for i, case in enumerate(confusion_cases, 1):
        print(f"{i}. '{case['query']}'")
        print(f"   期望: {case['expected']}")
        print(f"   風險: {case['confused_with']}")
        print(f"   原因: {case['reason']}")
        print()

    # 語義分析
    print("=" * 80)
    print("🔍 語義差異分析")
    print("=" * 80)
    print()

    print("【STORE_PRICING 的語義範圍】")
    print("  ❌ 問題: 'Pricing' 在英文中通常指「商品定價」")
    print("      - Product Pricing (產品定價)")
    print("      - Price List (價目表)")
    print("      - Pricing Strategy (定價策略)")
    print()
    print("  ✅ 實際內容: 場地使用費、入場費、計時收費")
    print("      - 平日每小時 $60-$70")
    print("      - 假日每小時 $80")
    print("      - 包日方案")
    print()

    print("【STORE_INTRO 的語義範圍】")
    print("  ✅ 實際內容: 店家介紹、商品販售、庫存查詢")
    print("      - '想買遊戲嗎？'")
    print("      - '架上都有標示價格'")
    print("      - '確認有沒有現貨'")
    print()

    print("⚠️  重疊區域:")
    print("    當用戶問「XX 多少錢？」時:")
    print("    - 如果 XX = 遊戲名稱 → STORE_INTRO (商品價格)")
    print("    - 如果 XX = 平日/假日/一天 → STORE_PRICING (場地費)")
    print("    - 語義模型可能難以區分！")
    print()

    # 改名方案評估
    print("=" * 80)
    print("💡 改名方案: STORE_PRICING → STORE_FEE")
    print("=" * 80)
    print()

    print("【FEE 的語義優勢】")
    print("  ✅ FEE = 費用（服務費、入場費、使用費）")
    print("      - Entrance Fee (入場費)")
    print("      - Service Fee (服務費)")
    print("      - Usage Fee (使用費)")
    print()
    print("  ✅ 更精確描述場地使用成本")
    print("  ✅ 與商品定價語義區隔明確")
    print("  ✅ 降低 FastPath 和 LLM Router 誤判風險")
    print()

    print("【PRICING 的語義劣勢】")
    print("  ❌ PRICING = 定價（商品價格、售價）")
    print("      - Game Pricing (遊戲定價)")
    print("      - Product Pricing (產品定價)")
    print("  ❌ 容易與 STORE_INTRO 的商品販售混淆")
    print()

    # 對比表格
    print("=" * 80)
    print("📊 命名對比")
    print("=" * 80)
    print()

    comparison = {
        "語義明確度": {"PRICING": "❌ 模糊（可指商品或服務）", "FEE": "✅ 明確（僅指服務費用）"},
        "與 INTRO 區隔": {"PRICING": "⚠️  易混淆", "FEE": "✅ 清晰區隔"},
        "用戶理解": {"PRICING": "⚠️  可能誤解為商品價", "FEE": "✅ 直覺理解為入場費"},
        "FastPath 準確度": {"PRICING": "⚠️  容易誤判", "FEE": "✅ 降低誤判"},
        "代碼一致性": {"PRICING": "✅ 已使用", "FEE": "⚠️  需全域重命名"}
    }

    print(f"{'項目':<15} {'STORE_PRICING':<30} {'STORE_FEE':<30}")
    print("-" * 80)
    for key, values in comparison.items():
        print(f"{key:<15} {values['PRICING']:<30} {values['FEE']:<30}")
    print()

    # 影響範圍
    print("=" * 80)
    print("📝 改名影響範圍")
    print("=" * 80)
    print()

    print("需要修改的文件:")
    print("  1. config/store_info.yaml (STORE_PRICING → STORE_FEE)")
    print("  2. config/intent_map.yaml (content_map 中的 STORE_PRICING)")
    print("  3. config/prompts_local.yaml (router 定義中的 STORE_PRICING)")
    print("  4. config/semantic_routes.yaml (新增時使用 STORE_FEE)")
    print()

    print("工作量: 低（約 4 個文件，純文本替換）")
    print("風險: 低（不影響核心邏輯）")
    print()

    # 最終建議
    print("=" * 80)
    print("✅ 最終建議")
    print("=" * 80)
    print()

    print("【強烈建議】改名為 STORE_FEE")
    print()
    print("理由:")
    print("  1. 語義更精確，避免與商品定價混淆")
    print("  2. 降低 FastPath 誤判風險")
    print("  3. 提升 LLM Router 分類準確度")
    print("  4. 改動成本低，影響範圍可控")
    print()

    print("實施步驟:")
    print("  Phase 1: 重命名 intent (PRICING → FEE)")
    print("  Phase 2: 補充 STORE_FEE 的 semantic anchors")
    print("  Phase 3: 測試驗證分類準確度")
    print()

    print("預期效果:")
    print("  ✅ 「平日多少錢」→ STORE_FEE (正確)")
    print("  ✅ 「卡坦島多少錢」→ STORE_INTRO (正確)")
    print("  ✅ 減少跨 intent 誤判")
    print()

    print("=" * 80)
    print("✅ 分析完成")
    print("=" * 80)

if __name__ == "__main__":
    analyze_naming_confusion()
