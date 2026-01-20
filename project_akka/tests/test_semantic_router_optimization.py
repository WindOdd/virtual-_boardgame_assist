"""
測試 Semantic Router 優化效果
驗證 FastPath 命中率提升
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.semantic_router import SemanticRouter
from src.boardgame_utils import ConfigLoader

def test_semantic_router():
    """測試語意路由器的命中率"""

    # 載入配置
    config_dir = project_root / "config"
    system_config = ConfigLoader(config_dir / "system_config.yaml").load()
    semantic_routes = ConfigLoader(config_dir / "semantic_routes.yaml").load()

    # 初始化路由器
    embedding_config = system_config.get("model", {}).get("embedding", {})
    router = SemanticRouter(embedding_config, semantic_routes)

    # 定義測試案例
    test_cases = [
        # STORE_WIFI 測試
        ("wifi密碼", "STORE_WIFI"),
        ("請問wifi密碼是什麼", "STORE_WIFI"),
        ("這裡有無線網路嗎", "STORE_WIFI"),
        ("網路連不上", "STORE_WIFI"),
        ("密碼多少", "STORE_WIFI"),
        ("可以給我wifi密碼嗎", "STORE_WIFI"),

        # STORE_TOILET 測試
        ("廁所在哪", "STORE_TOILET"),
        ("我要尿尿", "STORE_TOILET"),
        ("請問洗手間在哪裡", "STORE_TOILET"),
        ("哪裡可以上廁所", "STORE_TOILET"),
        ("可以借廁所嗎", "STORE_TOILET"),

        # GREETING 測試
        ("你好", "GREETING"),
        ("嗨", "GREETING"),
        ("早安", "GREETING"),
        ("有人在嗎", "GREETING"),
        ("不好意思", "GREETING"),

        # IDENTITY 測試
        ("你是誰", "IDENTITY"),
        ("你叫什麼名字", "IDENTITY"),
        ("介紹一下你自己", "IDENTITY"),
        ("你會做什麼", "IDENTITY"),
        ("你是機器人嗎", "IDENTITY"),
    ]

    # 統計結果
    total = len(test_cases)
    hits = 0
    misses = 0

    print("=" * 80)
    print("Semantic Router 優化測試")
    print(f"閾值: {embedding_config.get('threshold', 0.85)}")
    print("=" * 80)
    print()

    for user_input, expected_intent in test_cases:
        intent, score = router.route(user_input)

        if intent == expected_intent:
            hits += 1
            status = "✅ HIT"
        else:
            misses += 1
            status = "❌ MISS"

        print(f"{status} | Score: {score:.4f} | Input: '{user_input}'")
        print(f"      Expected: {expected_intent}, Got: {intent}")
        print()

    # 計算命中率
    hit_rate = (hits / total) * 100

    print("=" * 80)
    print("測試結果統計")
    print("=" * 80)
    print(f"總測試數: {total}")
    print(f"命中數: {hits}")
    print(f"未命中數: {misses}")
    print(f"命中率: {hit_rate:.2f}%")
    print("=" * 80)

    return hit_rate

if __name__ == "__main__":
    hit_rate = test_semantic_router()

    # 如果命中率低於 90%，返回錯誤碼
    if hit_rate < 90:
        print(f"\n⚠️  警告: 命中率 {hit_rate:.2f}% 低於預期 90%")
        sys.exit(1)
    else:
        print(f"\n✅ 測試通過: 命中率 {hit_rate:.2f}% 達標")
        sys.exit(0)
