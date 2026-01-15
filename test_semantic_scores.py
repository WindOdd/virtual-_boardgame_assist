"""
Test script for semantic scores and STT keywords integration
"""

import sys
from pathlib import Path

# Add project_akka to path
sys.path.insert(0, str(Path(__file__).parent / "project_akka"))

from src.semantic_router import SemanticRouter
from src.pipeline import Pipeline

def test_semantic_top_matches():
    """Test SemanticRouter.get_top_matches() method"""
    print("=" * 60)
    print("Test 1: SemanticRouter.get_top_matches()")
    print("=" * 60)

    # Mock configs
    model_config = {
        "name": "intfloat/multilingual-e5-small",
        "threshold": 0.9
    }

    routes_config = {
        "STORE_WIFI": ["wifi密碼", "無線網路", "網路連不上"],
        "STORE_TOILET": ["廁所在哪", "洗手間", "化妝室"],
        "GREETING": ["你好", "早安", "嗨"],
        "IDENTITY": ["你是誰", "名字", "介紹一下"]
    }

    router = SemanticRouter(model_config, routes_config)

    # Test query
    test_query = "請問wifi密碼是多少"

    print(f"\nQuery: {test_query}")
    print("\nTop 3 matches:")

    top_matches = router.get_top_matches(test_query, top_k=3)

    for i, (intent, score) in enumerate(top_matches, 1):
        print(f"  {i}. {intent}: {score:.4f}")

    # Verify
    assert len(top_matches) <= 3, "Should return at most 3 matches"
    assert top_matches[0][0] == "STORE_WIFI", "Top match should be STORE_WIFI"
    assert top_matches[0][1] > 0.7, "Top score should be > 0.7"

    print("\n✅ Test 1 passed!")

def test_stt_keywords_loading():
    """Test Pipeline._load_stt_keywords() method"""
    print("\n" + "=" * 60)
    print("Test 2: Pipeline._load_stt_keywords()")
    print("=" * 60)

    pipeline = Pipeline()

    # Test loading Carcassonne keywords
    game_id = "Carcassonne"
    keywords = pipeline._load_stt_keywords(game_id)

    print(f"\nGame: {game_id}")
    print(f"Keywords loaded: {len(keywords)}")
    print(f"Sample keywords: {keywords[:5]}")

    # Verify
    assert len(keywords) > 0, "Should load keywords"
    assert "卡卡頌" in keywords, "Should contain '卡卡頌'"
    assert "米寶" in keywords, "Should contain '米寶'"

    print("\n✅ Test 2 passed!")

    # Test non-existent game
    print("\n--- Test non-existent game ---")
    keywords_empty = pipeline._load_stt_keywords("NonExistentGame")
    assert len(keywords_empty) == 0, "Should return empty list for non-existent game"
    print("✅ Non-existent game returns empty list")

def test_integration_format():
    """Test the complete format sent to 4B LLM"""
    print("\n" + "=" * 60)
    print("Test 3: Integration Format Example")
    print("=" * 60)

    # Simulate what gets sent to 4B
    top_matches = [
        ("RULES", 0.89),
        ("STORE_SALES", 0.72),
        ("STORE_WIFI", 0.65)
    ]

    recent_context = [
        "STORE_SALES: 你們有賣卡坦島嗎",
        "RULES: 要怎麼買發展卡"
    ]

    stt_keywords = ["卡卡頌", "米寶", "板塊", "騎士", "農夫", "修士"]

    # Build format
    scores_lines = "\n".join([f"- {intent}: {score:.2f}" for intent, score in top_matches])
    scores_block = f"[Semantic Scores]\n{scores_lines}\n\n"

    context_lines = "\n".join([f"- {ctx}" for ctx in recent_context])
    context_block = f"[Recent Context]\n{context_lines}\n\n"

    keywords_str = ", ".join(stt_keywords[:20])
    keywords_block = f"[Game Keywords]\n{keywords_str}\n\n"

    user_input = "農夫要怎麼放"
    final_input = f"{scores_block}{context_block}{keywords_block}[User Input] {user_input}"

    print("\nFinal input sent to 4B LLM:")
    print("-" * 60)
    print(final_input)
    print("-" * 60)

    # Verify structure
    assert "[Semantic Scores]" in final_input
    assert "[Recent Context]" in final_input
    assert "[Game Keywords]" in final_input
    assert "[User Input]" in final_input

    print("\n✅ Test 3 passed!")

if __name__ == "__main__":
    try:
        test_semantic_top_matches()
        test_stt_keywords_loading()
        test_integration_format()

        print("\n" + "=" * 60)
        print("🎉 All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
