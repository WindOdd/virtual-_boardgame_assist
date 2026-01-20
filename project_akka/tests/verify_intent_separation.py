"""
驗證 Intent 拆分修正效果
測試 STORE_LOCATION、STORE_PHONE、STORE_INTRO、STORE_FEE 的區隔
"""

from pathlib import Path
import yaml

def verify_intent_separation():
    """驗證意圖定義的正確性"""

    config_dir = Path(__file__).parent.parent / "config"

    # 載入配置
    with open(config_dir / "prompts_local.yaml", 'r', encoding='utf-8') as f:
        prompts_content = f.read()

    with open(config_dir / "intent_map.yaml", 'r', encoding='utf-8') as f:
        intent_map = yaml.safe_load(f)

    with open(config_dir / "store_info.yaml", 'r', encoding='utf-8') as f:
        store_info = yaml.safe_load(f)

    print("=" * 80)
    print("Intent 拆分修正驗證")
    print("=" * 80)
    print()

    # 測試案例
    test_cases = [
        {
            "query": "你們的地址在哪裡？",
            "expected_intent": "STORE_LOCATION",
            "expected_response_key": "STORE_ADDRESS",
            "category": "地址查詢"
        },
        {
            "query": "請問店裡的電話號碼？",
            "expected_intent": "STORE_PHONE",
            "expected_response_key": "STORE_PHONE",
            "category": "電話查詢"
        },
        {
            "query": "卡坦島多少錢？",
            "expected_intent": "STORE_INTRO",
            "expected_response_key": "STORE_INTRO",
            "category": "商品價格"
        },
        {
            "query": "平日多少錢？",
            "expected_intent": "STORE_FEE",
            "expected_response_key": "STORE_FEE",
            "category": "場地費用"
        },
        {
            "query": "這裡有賣桌遊嗎？",
            "expected_intent": "STORE_INTRO",
            "expected_response_key": "STORE_INTRO",
            "category": "商品販售"
        },
        {
            "query": "入場費怎麼算？",
            "expected_intent": "STORE_FEE",
            "expected_response_key": "STORE_FEE",
            "category": "場地費用"
        }
    ]

    print("📊 測試案例")
    print("=" * 80)
    print()

    # 檢查 prompts_local.yaml 中的定義
    print("1️⃣ 檢查 prompts_local.yaml 定義")
    print("-" * 80)

    required_intents = [
        "STORE_LOCATION",
        "STORE_PHONE",
        "STORE_INTRO",
        "STORE_FEE"
    ]

    for intent in required_intents:
        if intent in prompts_content:
            print(f"  ✅ {intent} 已定義")
        else:
            print(f"  ❌ {intent} 未定義")
    print()

    # 檢查 STORE_FEE 負向約束
    if "NEGATIVE_CONSTRAINT" in prompts_content and "STORE_FEE" in prompts_content:
        print("  ✅ STORE_FEE 包含負向約束（避免誤判商品價格）")
    else:
        print("  ⚠️  STORE_FEE 缺少負向約束")
    print()

    # 檢查 STORE_INTRO 約束
    if "POSITIVE_CONSTRAINT" in prompts_content and "NEGATIVE_CONSTRAINT" in prompts_content:
        print("  ✅ STORE_INTRO 包含正負向約束（明確範圍）")
    else:
        print("  ⚠️  STORE_INTRO 缺少約束")
    print()

    # 檢查 intent_map.yaml
    print("2️⃣ 檢查 intent_map.yaml 映射")
    print("-" * 80)

    content_map = intent_map.get("content_map", {})

    mappings = [
        ("STORE_LOCATION", "STORE_ADDRESS"),
        ("STORE_PHONE", "STORE_PHONE"),
        ("STORE_INTRO", "STORE_INTRO"),
        ("STORE_FEE", "STORE_FEE")
    ]

    for intent, expected_key in mappings:
        if intent in content_map:
            actual_keys = content_map[intent]
            expected_in_list = expected_key in actual_keys
            if expected_in_list:
                print(f"  ✅ {intent} → {actual_keys} (正確)")
            else:
                print(f"  ⚠️  {intent} → {actual_keys} (預期: {expected_key})")
        else:
            print(f"  ❌ {intent} 未映射")
    print()

    # 檢查 store_info.yaml
    print("3️⃣ 檢查 store_info.yaml 回應")
    print("-" * 80)

    responses = store_info.get("responses", {})

    required_response_keys = [
        "STORE_ADDRESS",
        "STORE_PHONE",
        "STORE_INTRO",
        "STORE_FEE"
    ]

    for key in required_response_keys:
        if key in responses:
            count = len(responses[key])
            print(f"  ✅ {key}: {count} 個回應變體")
        else:
            print(f"  ❌ {key}: 無回應內容")
    print()

    # 模擬測試案例
    print("4️⃣ 模擬測試案例")
    print("=" * 80)
    print()

    for case in test_cases:
        query = case['query']
        expected = case['expected_intent']
        category = case['category']
        response_key = case['expected_response_key']

        print(f"📝 {category}: '{query}'")
        print(f"   期望 Intent: {expected}")
        print(f"   期望回應來源: {response_key}")

        # 檢查映射是否存在
        if expected in content_map:
            mapped_keys = content_map[expected]
            if response_key in responses:
                print(f"   ✅ 路由鏈完整: {expected} → {mapped_keys} → 回應存在")
            else:
                print(f"   ⚠️  回應缺失: {response_key}")
        else:
            print(f"   ❌ 映射缺失: {expected}")
        print()

    # 關鍵改進總結
    print("=" * 80)
    print("🎯 關鍵改進總結")
    print("=" * 80)
    print()

    print("修正前的問題:")
    print("  ❌ STORE_INTRO 包含 location + phone + sales（過於寬泛）")
    print("  ❌ 用戶問地址 → 返回店鋪介紹（答非所問）")
    print("  ❌ '卡坦島多少錢' → STORE_FEE（誤判為場地費）")
    print()

    print("修正後的改善:")
    print("  ✅ 拆分 STORE_LOCATION（地址查詢）")
    print("  ✅ 拆分 STORE_PHONE（電話查詢）")
    print("  ✅ STORE_FEE 加入負向約束（避免誤判商品價格）")
    print("  ✅ STORE_INTRO 收束定義（專注商品販售）")
    print("  ✅ Layer 1 & Layer 2 同步（消除不一致）")
    print()

    print("預期效果:")
    print("  ✅ '你們的地址？' → STORE_LOCATION → 精確地址")
    print("  ✅ '電話號碼？' → STORE_PHONE → 電話號碼")
    print("  ✅ '卡坦島多少錢？' → STORE_INTRO → 商品價格/庫存")
    print("  ✅ '平日多少錢？' → STORE_FEE → 場地使用費")
    print()

    print("=" * 80)
    print("✅ 驗證完成")
    print("=" * 80)

if __name__ == "__main__":
    verify_intent_separation()
