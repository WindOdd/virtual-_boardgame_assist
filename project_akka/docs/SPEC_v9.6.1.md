# Project Akka：桌遊店智慧語音助理系統開發規格書
**版本：v9.6.1**  
**狀態：Active Development**  
**最後更新：2026/01/08**

---

## 1. 系統概述

本系統為桌遊店專用的低延遲語音助理，旨在資源受限的 Edge 裝置上提供流暢體驗。

### 1.1 核心三層架構

| 層級 | 硬體 | 職責 |
|------|------|------|
| **Cloud Brain** | Google Gemini 2.5 Flash | 閱讀英文規則，轉譯為繁體中文回答 |
| **Local Brain** | Jetson (Ollama/Qwen 4B) | 意圖路由、白名單過濾、閒聊兜底 |
| **Edge Client** | iPad App | UDP 發現、STT、填補音效、對話狀態維護 |

---

## 2. 硬體與環境規格

### 2.1 伺服器端 (NVIDIA Jetson Orin Nano Super)
- **VRAM**: 8GB
- **OS**: Ubuntu 20.04+ (JetPack 6.0)
- **電源模式**: MAXN (25W) - `sudo nvpmodel -m 0`
- **散熱**: 強制風扇最大 - `sudo jetson_clocks`
- **記憶體防護**: 必須掛載 8GB Swap File

### 2.2 Ollama 服務配置
```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=5m"
```

### 2.3 客戶端 (iPad)
- **STT**: iOS 原生 SFSpeechRecognizer (On-device 優先)
- **修正機制**: 透過 `contextualStrings` 注入遊戲專有名詞

---

## 3. 核心處理流水線

### 階段 I：UDP 服務發現
| 項目 | 值 |
|------|---|
| Port | 37020 |
| Magic String | `DISCOVER_AKKA_SERVER` |
| 回應格式 | `{"ip": "192.168.x.x", "port": 8000}` |

### 階段 II：Client 預處理
1. 透過 `/api/keywords/{game_id}` 取得關鍵詞
2. 注入 `contextualStrings` 給 STT
3. 若等待超過 2.5 秒，播放「填補音效」

### 階段 III：意圖路由 (Local Brain)
**輸出 Intent：**
- `RULES` - 規則詢問
- `SENSITIVE` - 敏感話題
- `CASUAL_CHAT` - 閒聊
- `STORE_*` - 店務查詢
- `ERROR` - 錯誤（v9.6.1 新增）

### 階段 IV：安全過濾 (Allowlist)
當 Router 判定為 `SENSITIVE` 時：
- 命中白名單 → 改為 `RULES`，放行
- 未命中 → 維持 `SENSITIVE`，攔截

### 階段 V：邏輯分派

| Intent | 處理者 | 說明 |
|--------|--------|------|
| RULES | Cloud LLM | 讀取完整規則書，繁中回答 |
| CASUAL_CHAT | Local LLM | 阿卡人設閒聊 (≤40字) |
| STORE_* | Static Lookup | 查表回應 (<10ms) |
| ERROR | - | 直接回傳錯誤訊息 |

---

## 4. API 定義

### 4.1 GET /api/games
取得支援的遊戲列表。

**Response:**
```json
{
  "games": [
    {
      "id": "carcassonne",
      "name": "卡卡頌",
      "description": "2-5 players, 30-45 minutes",
      "enable_stt_injection": true
    }
  ]
}
```

### 4.2 GET /api/keywords/{game_id}
取得 STT 修正關鍵字。

**Response:**
```json
{
  "game_id": "carcassonne",
  "keywords": ["卡卡頌", "米寶", "板塊", "農夫", "騎士"]
}
```

### 4.3 POST /api/chat
主要對話接口。

**Request:**
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

**Response:**
```json
{
  "response": "農夫是遊戲結束才計分的...",
  "intent": "RULES",
  "confidence": 0.95,
  "source": "cloud_gen"
}
```

---

## 5. 資料正規化規則 (v9.6.1)

### 5.1 game_id 正規化
- 所有 `game_id` 統一轉為**小寫**
- 避免 Linux 大小寫敏感問題
- DataManager 載入/查詢時自動轉換

### 5.2 意圖軌跡提取
- 從 **assistant 訊息**提取 intent（非 user）
- User 訊息無狀態，Server 處理後才加上 intent

```python
# 範例：取最後 2 個 assistant intent
context_str = "RULES -> STORE_PRICING"
```

### 5.3 Cloud LLM History 過濾
- 只傳送 **RULES 相關對話**給 Cloud LLM
- 保留 assistant.intent == "RULES" 的問答對
- 節省 Token，避免雜訊

### 5.4 ERROR Intent
- 錯誤發生時回傳 `intent: "ERROR"`
- 避免錯誤訊息污染 history

---

## 6. 檔案結構

```
project_akka/
├── config/
│   ├── system_config.yaml      # UDP, 模型設定
│   ├── intent_map.yaml         # 意圖映射表
│   ├── store_info.yaml         # 店務語錄
│   ├── prompts_local.yaml      # Router + Persona
│   └── prompts_cloud.yaml      # RAG Prompt
├── data/
│   ├── games_registry.yaml     # 遊戲總表
│   ├── rules/                  # 英文規則 (MD)
│   └── stt_keywords/           # STT 關鍵字
└── src/
    ├── main.py                 # FastAPI 入口
    ├── pipeline.py             # 核心流水線
    ├── data_manager.py         # 資料管理
    └── services/               # UDP Discovery 等
```

---

## 7. Client 責任

| 項目 | 處理方式 |
|------|---------|
| history 管理 | 保留最多 8 輪 (16 則訊息) |
| 切換遊戲 | 清空 history |
| 儲存 intent | 將 Server 回傳的 intent 存入 history |
| 辨識 ERROR | `intent == "ERROR"` 時不存入 RULES history |

---

## 8. 驗收標準

| ID | 測試項目 | 預期結果 |
|----|---------|---------|
| N01 | UDP 連線 | 取得 Server IP |
| C01 | STT 修正 | 正確辨識遊戲術語 |
| S01 | 白名單放行 | 「希特勒怎麼玩」→ RULES |
| S02 | 敏感攔截 | 政治話題 → 拒絕 |
| R01 | 規則查詢 | 繁中回答英文規則 |
| E01 | 錯誤處理 | 回傳 intent: ERROR |

---

*版本歷程：*
- v9.6: 初版規格
- v9.6.1: 新增 game_id 正規化、ERROR intent、History 過濾
