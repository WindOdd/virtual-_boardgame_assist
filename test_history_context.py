#!/usr/bin/env python3
"""
Test script for _extract_recent_context() method
"""

def extract_recent_context(history, window=3, max_length=80):
    """
    Extract recent conversation context in format: "INTENT: user_query"
    """
    if not history:
        return []

    context = []

    # Iterate through history to find assistant messages with intent
    for i, msg in enumerate(history):
        if msg.get("role") == "assistant" and msg.get("intent"):
            # Find the corresponding user query (previous message)
            if i > 0 and history[i-1].get("role") == "user":
                user_query = history[i-1].get("content", "").strip()
                intent = msg.get("intent")

                # Truncate long queries
                if len(user_query) > max_length:
                    user_query_short = user_query[:max_length] + "..."
                else:
                    user_query_short = user_query

                # Format: "INTENT: query"
                context.append(f"{intent}: {user_query_short}")

    # Return most recent N entries
    return context[-window:]


# Test cases
def test_basic():
    """Test basic functionality"""
    history = [
        {"role": "user", "content": "你們有賣卡坦島嗎"},
        {"role": "assistant", "content": "有的，我們店內...", "intent": "STORE_SALES"},
        {"role": "user", "content": "要怎麼買發展卡"},
        {"role": "assistant", "content": "買發展卡需要...", "intent": "RULES"},
        {"role": "user", "content": "wifi密碼多少"},
        {"role": "assistant", "content": "密碼是...", "intent": "STORE_WIFI"},
    ]

    result = extract_recent_context(history, window=3, max_length=80)
    print("Test 1 - Basic (window=3):")
    for ctx in result:
        print(f"  - {ctx}")
    print()

    expected = [
        "STORE_SALES: 你們有賣卡坦島嗎",
        "RULES: 要怎麼買發展卡",
        "STORE_WIFI: wifi密碼多少"
    ]
    assert result == expected, f"Expected {expected}, got {result}"
    print("✓ Test 1 passed\n")


def test_truncation():
    """Test query truncation"""
    long_query = "我想知道卡坦島的基本規則包括怎麼擲骰子怎麼交易還有怎麼蓋房子這些基本流程是什麼還有怎麼算分數還有發展卡怎麼用還有強盜怎麼移動還有港口的交易規則是什麼這些我都不太清楚能不能解釋一下"

    history = [
        {"role": "user", "content": long_query},
        {"role": "assistant", "content": "...", "intent": "RULES"},
    ]

    result = extract_recent_context(history, window=3, max_length=80)
    print(f"Test 2 - Truncation (max_length=80, original length={len(long_query)}):")
    for ctx in result:
        print(f"  - {ctx}")
        print(f"    Length: {len(ctx)}")
    print()

    assert len(result) == 1
    # RULES: (7 chars) + content (80 chars) + ... (3 chars) = ~90 chars
    assert result[0].endswith("...")
    assert len(result[0]) <= 95  # Some buffer
    print("✓ Test 2 passed\n")


def test_window():
    """Test window parameter"""
    history = [
        {"role": "user", "content": "第一個問題"},
        {"role": "assistant", "content": "...", "intent": "RULES"},
        {"role": "user", "content": "第二個問題"},
        {"role": "assistant", "content": "...", "intent": "STORE_SALES"},
        {"role": "user", "content": "第三個問題"},
        {"role": "assistant", "content": "...", "intent": "RULES"},
        {"role": "user", "content": "第四個問題"},
        {"role": "assistant", "content": "...", "intent": "STORE_WIFI"},
    ]

    result = extract_recent_context(history, window=2, max_length=80)
    print("Test 3 - Window (window=2, should get last 2):")
    for ctx in result:
        print(f"  - {ctx}")
    print()

    assert len(result) == 2
    assert result[0] == "RULES: 第三個問題"
    assert result[1] == "STORE_WIFI: 第四個問題"
    print("✓ Test 3 passed\n")


def test_empty():
    """Test empty history"""
    result = extract_recent_context(None, window=3, max_length=80)
    assert result == []
    print("✓ Test 4 passed (empty history)\n")


def test_no_intent():
    """Test history without intent"""
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好"},
    ]

    result = extract_recent_context(history, window=3, max_length=80)
    assert result == []
    print("✓ Test 5 passed (no intent)\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing _extract_recent_context()")
    print("=" * 60)
    print()

    test_basic()
    test_truncation()
    test_window()
    test_empty()
    test_no_intent()

    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
