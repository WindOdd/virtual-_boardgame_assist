"""
Test STT keywords loading fix (case-insensitive game_id)
"""

import sys
from pathlib import Path

# Add project_akka to path
sys.path.insert(0, str(Path(__file__).parent / "project_akka"))

def test_data_manager_stt_keywords():
    """Test data_manager.get_stt_keywords() with case-insensitive lookup"""
    print("=" * 60)
    print("Test: DataManager STT Keywords Loading (Case-Insensitive)")
    print("=" * 60)

    from src.data_manager import get_data_manager

    dm = get_data_manager()

    # Test 1: lowercase game_id (what client sends)
    print("\n--- Test 1: Lowercase game_id ---")
    keywords_lower = dm.get_stt_keywords("carcassonne")
    print(f"Game ID: 'carcassonne' (lowercase)")
    print(f"Loaded: {len(keywords_lower) if keywords_lower else 0} keywords")

    assert keywords_lower is not None, "Should return keywords for lowercase game_id"
    assert len(keywords_lower) > 0, "Keywords list should not be empty"
    assert "卡卡頌" in keywords_lower, "Should contain '卡卡頌'"
    print(f"Sample: {keywords_lower[:5]}")
    print("✅ Lowercase game_id works!")

    # Test 2: Capitalized game_id
    print("\n--- Test 2: Capitalized game_id ---")
    keywords_cap = dm.get_stt_keywords("Carcassonne")
    print(f"Game ID: 'Carcassonne' (capitalized)")
    print(f"Loaded: {len(keywords_cap) if keywords_cap else 0} keywords")

    assert keywords_cap is not None, "Should return keywords for capitalized game_id"
    assert len(keywords_cap) == len(keywords_lower), "Should return same keywords"
    print("✅ Capitalized game_id works!")

    # Test 3: Non-existent game
    print("\n--- Test 3: Non-existent game ---")
    keywords_none = dm.get_stt_keywords("NonExistentGame")
    print(f"Game ID: 'NonExistentGame'")
    print(f"Result: {keywords_none}")

    assert keywords_none is None, "Should return None for non-existent game"
    print("✅ Non-existent game returns None!")

    # Test 4: Verify file path resolution
    print("\n--- Test 4: File path resolution ---")
    game = dm.get_game("carcassonne")
    print(f"Game entry: {game.display_name}")
    print(f"Keywords path: {game.keywords_path}")
    print(f"File exists: {(dm.base_path / game.keywords_path).exists()}")
    assert (dm.base_path / game.keywords_path).exists(), "Keywords file should exist"
    print("✅ File path resolution works!")

    print("\n" + "=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
    print("\n✅ DataManager correctly handles:")
    print("  - Case-insensitive game_id lookup")
    print("  - Correct file path resolution from registry")
    print("  - Returns None for non-existent games")

if __name__ == "__main__":
    try:
        test_data_manager_stt_keywords()
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
