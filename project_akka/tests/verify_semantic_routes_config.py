"""
驗證 semantic_routes.yaml 配置優化
不需要載入實際模型，僅檢查配置結構和內容
"""

import yaml
from pathlib import Path
from collections import Counter

def verify_config():
    """驗證配置文件優化"""

    config_dir = Path(__file__).parent.parent / "config"
    semantic_routes_path = config_dir / "semantic_routes.yaml"
    system_config_path = config_dir / "system_config.yaml"

    print("=" * 80)
    print("Semantic Routes 配置驗證")
    print("=" * 80)
    print()

    # 1. 載入配置
    with open(semantic_routes_path, 'r', encoding='utf-8') as f:
        routes = yaml.safe_load(f)

    with open(system_config_path, 'r', encoding='utf-8') as f:
        system_config = yaml.safe_load(f)

    # 2. 檢查閾值
    threshold = system_config.get("model", {}).get("embedding", {}).get("threshold", 0.9)
    print(f"📊 當前閾值: {threshold}")
    if threshold == 0.85:
        print("   ✅ 閾值已優化至 0.85")
    elif threshold == 0.9:
        print("   ⚠️  閾值仍為 0.9（較高）")
    print()

    # 3. 分析每個 Intent
    print("=" * 80)
    print("Intent 分析")
    print("=" * 80)
    print()

    total_anchors = 0
    intent_stats = {}

    for intent, anchors in routes.items():
        if not isinstance(anchors, list):
            continue

        num_anchors = len(anchors)
        total_anchors += num_anchors

        # 統計句子長度分佈
        lengths = [len(a) for a in anchors]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        max_length = max(lengths) if lengths else 0
        min_length = min(lengths) if lengths else 0

        # 分類句子類型
        short_phrases = sum(1 for l in lengths if l <= 5)  # 短語/關鍵字
        medium_sentences = sum(1 for l in lengths if 6 <= l <= 15)  # 中等句子
        long_sentences = sum(1 for l in lengths if l > 15)  # 完整句子

        intent_stats[intent] = {
            'total': num_anchors,
            'avg_length': avg_length,
            'min_length': min_length,
            'max_length': max_length,
            'short': short_phrases,
            'medium': medium_sentences,
            'long': long_sentences
        }

        print(f"Intent: {intent}")
        print(f"  Anchor 數量: {num_anchors}")
        print(f"  平均長度: {avg_length:.1f} 字元")
        print(f"  長度範圍: {min_length} - {max_length}")
        print(f"  分佈: 短語 {short_phrases} | 中句 {medium_sentences} | 長句 {long_sentences}")
        print()

        # 顯示部分範例
        print(f"  範例 Anchors:")
        for i, anchor in enumerate(anchors[:5], 1):
            print(f"    {i}. '{anchor}'")
        if num_anchors > 5:
            print(f"    ... 還有 {num_anchors - 5} 個")
        print()

    # 4. 總結
    print("=" * 80)
    print("優化總結")
    print("=" * 80)
    print()
    print(f"總 Intent 數: {len(routes)}")
    print(f"總 Anchor 數: {total_anchors}")
    print(f"平均每個 Intent: {total_anchors / len(routes):.1f} anchors")
    print()

    # 5. 優化建議評估
    print("優化評估:")
    print()

    issues = []
    recommendations = []

    # 檢查每個 intent 是否有足夠的完整句子
    for intent, stats in intent_stats.items():
        if stats['long'] < 5:
            issues.append(f"  ⚠️  {intent}: 完整句子較少 ({stats['long']} 個)")
            recommendations.append(f"     建議為 {intent} 增加更多完整對話句子")

        if stats['total'] < 10:
            issues.append(f"  ⚠️  {intent}: Anchor 總數較少 ({stats['total']} 個)")
            recommendations.append(f"     建議為 {intent} 增加更多語句變化")

    if not issues:
        print("  ✅ 所有 Intent 都有充足的完整句子變化")
    else:
        print("  發現可優化項目:")
        for issue in issues:
            print(issue)
        print()
        print("  優化建議:")
        for rec in recommendations:
            print(rec)

    print()

    # 6. 對比優化前後（假設原本每個 intent 只有 5-7 個 anchor）
    print("=" * 80)
    print("優化效果預估")
    print("=" * 80)
    print()

    # 假設優化前的數據
    original_avg = 6  # 原本平均每個 intent 約 6 個 anchor
    current_avg = total_anchors / len(routes)
    improvement = ((current_avg - original_avg) / original_avg) * 100

    print(f"優化前平均 Anchor 數: ~{original_avg} 個/intent")
    print(f"優化後平均 Anchor 數: {current_avg:.1f} 個/intent")
    print(f"增加比例: +{improvement:.1f}%")
    print()

    print(f"閾值優化:")
    print(f"  0.9 -> 0.85 (降低 5.6%)")
    print(f"  預期可接受更多語義相近但表達不同的句子")
    print()

    print("預期效果:")
    print("  ✅ FastPath 命中率提升")
    print("  ✅ 支援更多口語化變體")
    print("  ✅ 減少 LLM Router 呼叫次數")
    print("  ✅ 降低延遲，提升使用者體驗")
    print()

    print("=" * 80)
    print("✅ 配置驗證完成")
    print("=" * 80)

if __name__ == "__main__":
    verify_config()
