# Project Akka 規格書補充 (v9.6.1)
> 基於 v9.6 的實作補充，記錄開發過程中的設計決策與調整

---

## 1. game_id 正規化 (Case Normalization)

### 變更說明
所有 `game_id` 統一轉為**小寫 (lowercase)**，避免 Linux 大小寫敏感問題。

### 實作位置
- `data_manager.py`: 載入 registry 和查詢時自動轉小寫
- `games_registry.yaml`: ID 統一使用小寫

### Client 傳送範例
```json
{
  "game_context": {
    "game_id": "carcassonne"
  }
}
```

---

## 2. 意圖軌跡提取 (Context Extraction)

### 設計決策
從 **assistant 訊息**提取意圖軌跡，而非 user 訊息。

### 原因
- User 訊息無狀態（沒有 intent 欄位）
- Server 處理後才在 assistant 回應加上 intent

### 實作邏輯
```python
# 只看 assistant 且有 intent 的訊息
recent_assistant_logs = [
    msg for msg in history 
    if msg.get("role") == "assistant" and msg.get("intent")
]
# 組成軌跡：RULES -> STORE_PRICING
```

---

## 3. Cloud LLM History 過濾

### 設計決策
只將 **RULES 相關對話**傳給 Cloud LLM，節省 Token。

### 過濾邏輯
| 保留條件 | 說明 |
|---------|------|
| `assistant.intent == "RULES"` | 保留該回應 |
| 該回應的前一則 user 訊息 | 一併保留（問題+回答成對） |

### 效果
- 店務查詢 (STORE_*) 不會傳給 Cloud
- 閒聊 (CASUAL_CHAT) 不會傳給 Cloud
- 只有規則問答會被保留

---

## 4. ERROR Intent

### 設計決策
錯誤發生時回傳 `intent: "ERROR"`，而非原本的 intent。

### 目的
避免錯誤訊息被當作 RULES 對話存入 history。

### 回應範例
```json
{
  "response": "抱歉，雲端大腦連線有點問題，請稍後再試。",
  "intent": "ERROR",
  "source": "error"
}
```

### 錯誤觸發情境
| 情境 | intent |
|------|--------|
| Cloud LLM 連線失敗 | `ERROR` |
| Cloud LLM API 呼叫失敗 | `ERROR` |
| 其他正常處理 | 原本 intent |

---

## 5. API 格式確認

### POST /api/chat Request
```json
{
  "user_input": "農夫怎麼算分？",
  "game_context": {
    "game_id": "carcassonne"
  },
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "intent": "GREETING", "content": "哈囉！..."}
  ]
}
```

### POST /api/chat Response
```json
{
  "response": "農夫是遊戲結束才計分的...",
  "intent": "RULES",
  "confidence": 0.95,
  "source": "cloud_gen"
}
```

---

## 6. Client 責任

| 項目 | Client 端處理 |
|------|--------------|
| history 管理 | 保留最多 8 輪 (16 則訊息) |
| 切換遊戲 | 清空 history |
| 儲存 intent | 將 Server 回傳的 intent 存入 history |

---

*文件版本: v9.6.1*  
*更新日期: 2026-01-08*
