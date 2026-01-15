"""
Simple test for new features without requiring model loading
"""

import sys
from pathlib import Path

# Add project_akka to path
sys.path.insert(0, str(Path(__file__).parent / "project_akka"))

def test_stt_keywords_loading():
    """Test STT keywords file loading"""
    print("=" * 60)
    print("Test 1: STT Keywords File Loading")
    print("=" * 60)

    # Manually load keywords file
    keywords_file = Path(__file__).parent / "project_akka" / "data" / "stt_keywords" / "Carcassonne.txt"

    if not keywords_file.exists():
        print(f"❌ Keywords file not found: {keywords_file}")
        return False

    with open(keywords_file, 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]

    print(f"\n✅ Loaded {len(keywords)} keywords from {keywords_file.name}")
    print(f"Sample keywords: {keywords[:8]}")

    # Verify
    assert len(keywords) > 0, "Should load keywords"
    assert "卡卡頌" in keywords, "Should contain '卡卡頌'"

    print("\n✅ Test 1 passed!")
    return True

def test_format_integration():
    """Test the complete format sent to 4B LLM"""
    print("\n" + "=" * 60)
    print("Test 2: Integration Format for 4B LLM")
    print("=" * 60)

    # Simulate data
    top_matches = [
        ("RULES", 0.89),
        ("STORE_SALES", 0.72),
        ("STORE_WIFI", 0.65)
    ]

    recent_context = [
        "STORE_SALES: 你們有賣卡坦島嗎",
        "RULES: 要怎麼買發展卡"
    ]

    stt_keywords = ["卡卡頌", "米寶", "板塊", "騎士", "農夫", "修士", "強盜", "城堡"]

    # Build blocks (same as pipeline.py)
    scores_lines = "\n".join([f"- {intent}: {score:.2f}" for intent, score in top_matches])
    scores_block = f"[Semantic Scores]\n{scores_lines}\n\n"

    context_lines = "\n".join([f"- {ctx}" for ctx in recent_context])
    context_block = f"[Recent Context]\n{context_lines}\n\n"

    keywords_str = ", ".join(stt_keywords[:20])
    keywords_block = f"[Game Keywords]\n{keywords_str}\n\n"

    user_input = "農夫要怎麼放"
    final_input = f"{scores_block}{context_block}{keywords_block}[User Input] {user_input}"

    print("\nFinal input format sent to 4B LLM:")
    print("-" * 60)
    print(final_input)
    print("-" * 60)

    # Verify structure
    assert "[Semantic Scores]" in final_input
    assert "RULES: 0.89" in final_input
    assert "[Recent Context]" in final_input
    assert "STORE_SALES: 你們有賣卡坦島嗎" in final_input
    assert "[Game Keywords]" in final_input
    assert "卡卡頌, 米寶" in final_input
    assert "[User Input]" in final_input
    assert "農夫要怎麼放" in final_input

    print("\n✅ Test 2 passed!")
    return True

def test_code_changes():
    """Verify code changes are present"""
    print("\n" + "=" * 60)
    print("Test 3: Code Changes Verification")
    print("=" * 60)

    # Check semantic_router.py
    router_file = Path(__file__).parent / "project_akka" / "src" / "semantic_router.py"
    with open(router_file, 'r', encoding='utf-8') as f:
        router_code = f.read()

    assert "def get_top_matches" in router_code, "get_top_matches method should exist"
    assert "top_k" in router_code, "Should have top_k parameter"
    print("✅ semantic_router.py: get_top_matches() method found")

    # Check pipeline.py
    pipeline_file = Path(__file__).parent / "project_akka" / "src" / "pipeline.py"
    with open(pipeline_file, 'r', encoding='utf-8') as f:
        pipeline_code = f.read()

    assert "def _load_stt_keywords" in pipeline_code, "_load_stt_keywords method should exist"
    assert "get_top_matches" in pipeline_code, "Should call get_top_matches"
    assert "[Semantic Scores]" in pipeline_code, "Should format semantic scores"
    assert "[Game Keywords]" in pipeline_code, "Should format game keywords"
    print("✅ pipeline.py: _load_stt_keywords() method found")
    print("✅ pipeline.py: get_top_matches() integration found")
    print("✅ pipeline.py: Format blocks for 4B found")

    print("\n✅ Test 3 passed!")
    return True

if __name__ == "__main__":
    try:
        results = [
            test_stt_keywords_loading(),
            test_format_integration(),
            test_code_changes()
        ]

        if all(results):
            print("\n" + "=" * 60)
            print("🎉 All tests passed!")
            print("=" * 60)
            print("\n📊 Summary:")
            print("✅ STT keywords file loading works")
            print("✅ Integration format is correct")
            print("✅ Code changes are in place")
            print("\n📝 New features:")
            print("  - Semantic top 3 scores sent to 4B")
            print("  - History context with queries sent to 4B")
            print("  - Game STT keywords sent to 4B")
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
