# Project Akka — 技術架構文件
### Engineering Reference for Board Game Store Voice Assistant

> **對象**：開發者、系統維護人員
>
> **版本**：V2 Dual-Layer Routing (v9.6)
>
> **最後更新**：2026/02

---

## 一、系統總覽

```
┌──────────────────────────────────────────────────────────────┐
│                       Client (iPad App)                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────────┐ │
│  │ Whisper   │──▶│ POST     │──▶│ Display Response          │ │
│  │ (STT)     │   │ /api/chat│   │ + TTS Playback            │ │
│  └──────────┘   └────┬─────┘   └──────────────────────────┘ │
└───────────────────────┼──────────────────────────────────────┘
                        │ HTTP (JSON)
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  Akka Server (FastAPI)                        │
│                  main.py → uvicorn :8000                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Pipeline.process()                   │  │
│  │                                                        │  │
│  │  Stage 0: Context Extraction (from history)            │  │
│  │      │                                                 │  │
│  │      ▼                                                 │  │
│  │  Stage 1: Semantic Router (FastPath)  ──── Hit ──▶ ①   │  │
│  │      │ Miss                                            │  │
│  │      ▼                                                 │  │
│  │  Stage 2: LLM Router (Qwen-4B)                        │  │
│  │      │                                                 │  │
│  │      ▼                                                 │  │
│  │  Stage 3: Safety Filter (SENSITIVE check)              │  │
│  │      │                                                 │  │
│  │      ▼                                                 │  │
│  │  Stage 4: Dispatch ─┬─ content_static ──▶ ①            │  │
│  │                     ├─ local_llm_gen  ──▶ ②            │  │
│  │                     ├─ cloud_gen      ──▶ ③            │  │
│  │                     └─ reject / fallback               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ① store_info.yaml (Static)    ⏱ < 50ms                     │
│  ② Qwen-4B Local LLM (Persona) ⏱ ~800ms                    │
│  ③ Gemini Cloud LLM (RAG)       ⏱ 1.5s+                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、目錄結構

```
project_akka/
├── config/
│   ├── semantic_routes.yaml    # Layer 1 — 錨點句子定義
│   ├── prompts_local.yaml      # Layer 2 — Router & Persona System Prompt
│   ├── prompts_cloud.yaml      # Layer 3 — Cloud LLM System Prompt (RAG)
│   ├── intent_map.yaml         # Intent → Handler / Response Key 映射
│   ├── store_info.yaml         # 靜態回答資料庫
│   └── system_config.yaml      # 系統參數 (model, threshold, hardware)
├── src/
│   ├── main.py                 # FastAPI 入口點
│   ├── pipeline.py             # 核心路由編排器
│   ├── semantic_router.py      # Embedding 向量路由
│   ├── boardgame_utils.py      # ConfigLoader, PromptManager
│   ├── data_manager.py         # 桌遊規則資料管理
│   ├── llm/
│   │   ├── manager.py          # LLM 服務管理器
│   │   ├── local_llm_client.py # Ollama Client (Qwen-4B)
│   │   └── cloud_llm_client.py # Gemini Client
│   └── services/
│       └── discovery.py        # UDP 服務發現 (LAN)
├── data/                       # 桌遊規則書 (RAG 來源)
├── tests/
└── requirements.txt
```

---

## 三、Pipeline 路由流程

### 3.1 Stage 0 — Context Extraction

```python
# pipeline.py:124-148
# 從 Client 傳入的 history 提取最近 2 次 assistant 意圖
# 產出: context_str = "RULES -> STORE_FEE"
# 用途: 注入 Stage 2 的 LLM Prompt，解決模糊語句（如「那假日呢？」）
```

**輸入**: `history: List[Dict]`（由 Client 管理，Server 不保存狀態）

**輸出**: `context_str`（如 `"STORE_FEE -> RULES"`）

### 3.2 Stage 1 — Semantic Router (FastPath)

```python
# semantic_router.py:76-108
# 1. 用 e5-small encode 使用者輸入 (加 "query: " 前綴)
# 2. 與所有 intent 的 anchor embeddings 做 cosine similarity
# 3. 取最高分，若 >= threshold 則命中
```

| 參數 | 值 | 來源 |
|:---|:---|:---|
| **Model** | `intfloat/multilingual-e5-small` | system_config.yaml |
| **Device** | CPU (不搶 GPU) | semantic_router.py:50 |
| **Threshold** | 0.88 | system_config.yaml:28 |
| **Prefix** | `"query: "` (E5 模型要求) | semantic_router.py:68 |
| **Anchors 總數** | ~120 句 | semantic_routes.yaml |

**命中 (Hit)**: 直接跳到 `_dispatch()` 查 `store_info.yaml`，不經過 LLM。

**未命中 (Miss)**: 進入 Stage 2。

### 3.3 Stage 2 — LLM Router

```python
# pipeline.py:164-179
# 1. 注入 Context: "[Context: STORE_FEE -> RULES] User Input: 那假日呢？"
# 2. 送入 Local LLM，System Prompt 來自 prompts_local.yaml → router.system_prompt
# 3. LLM 回傳 JSON: {"intent": "STORE_FEE"}
```

| 參數 | 值 |
|:---|:---|
| **Model** | Qwen-4B-Chat-Int4 (via Ollama) |
| **輸出格式** | `{"intent": "...", "confidence": ...}` |
| **分類數量** | 12 種意圖 |

### 3.4 Stage 3 — Safety Filter

```python
# pipeline.py:182-184
# 若 intent == "SENSITIVE"，檢查 allowlist（遊戲專有名詞白名單）
# 若命中白名單 → 覆寫為 RULES（防止遊戲名稱被誤判為敏感）
```

### 3.5 Stage 4 — Dispatch

```python
# pipeline.py:252-287
# 路由優先順序：
# 1. store_info.yaml 靜態回答 → random.choice(candidates)
# 2. logic_intents 邏輯處理器 → local_llm / cloud_rag / reject
# 3. fallback → UNKNOWN_FALLBACK
```

---

## 四、設定檔關聯圖

```
                    使用者輸入
                        │
                        ▼
    ┌─────────────────────────────────────┐
    │      semantic_routes.yaml           │
    │  (Layer 1 Anchor Sentences)         │
    │                                     │
    │  STORE_ADDRESS:                     │
    │    - "店的地址在哪裡"                 │
    │    - "請問怎麼去你們店"               │
    │  STORE_FEE:                         │
    │    - "請問怎麼收費"                   │
    │    ...                              │
    └──────────┬──────────────────────────┘
               │ Hit → intent = "STORE_ADDRESS"
               │ Miss ↓
    ┌──────────▼──────────────────────────┐
    │      prompts_local.yaml             │
    │  (Layer 2 LLM Router Prompt)        │
    │                                     │
    │  8. STORE_ADDRESS:                  │
    │     - DEFINITION: 地址、捷運站...     │
    │  6. STORE_FEE:                      │
    │     - NEGATIVE_CONSTRAINT: ...      │
    │                                     │
    │  → LLM 輸出: {"intent": "..."}      │
    └──────────┬──────────────────────────┘
               │ intent = "STORE_ADDRESS"
               ▼
    ┌─────────────────────────────────────┐
    │      intent_map.yaml                │
    │  (Intent → Handler 映射)             │
    │                                     │
    │  content_map:                       │
    │    STORE_ADDRESS: ["STORE_ADDRESS"]  │
    │    STORE_FEE:     ["STORE_FEE"]     │
    │                                     │
    │  logic_intents:                     │
    │    RULES:  handler: "cloud_rag"     │
    │    SENSITIVE: handler: "reject"     │
    └──────────┬──────────────────────────┘
               │ key = "STORE_ADDRESS"
               ▼
    ┌─────────────────────────────────────┐
    │      store_info.yaml                │
    │  (靜態回答資料庫)                      │
    │                                     │
    │  responses:                         │
    │    STORE_ADDRESS:                   │
    │      - "我們在台北市錦西街84號..."     │
    │      - "地址是錦西街84號..."          │
    └─────────────────────────────────────┘
```

### 設定檔同步規則

新增或修改 Intent 時，**必須同時更新以下檔案**：

| 步驟 | 檔案 | 需要做什麼 |
|:---:|:---|:---|
| 1 | `semantic_routes.yaml` | 新增 anchor 句子（建議 ≥ 6 句） |
| 2 | `prompts_local.yaml` | 新增 Intent 定義 + CONSTRAINT |
| 3 | `intent_map.yaml` | 新增映射（content_map 或 logic_intents） |
| 4 | `store_info.yaml` | 新增回答（≥ 5 個變體） |

---

## 五、Intent 完整定義

### 5.1 目前支援的 12 種 Intent

| Intent Tag | Layer 1 (FastPath) | Layer 2 (LLM) | Dispatch |
|:---|:---:|:---:|:---|
| `STORE_WIFI` | 31 anchors | DEFINITION | → `store_info["STORE_WIFI"]` |
| `STORE_TOILET` | 21 anchors | DEFINITION | → `store_info["STORE_TOILET"]` |
| `STORE_ADDRESS` | 8 anchors | DEFINITION + KEYWORDS | → `store_info["STORE_ADDRESS"]` |
| `STORE_PHONE` | 6 anchors | DEFINITION + KEYWORDS | → `store_info["STORE_PHONE"]` |
| `STORE_FEE` | 12 anchors | DEFINITION + NEG_CONSTRAINT | → `store_info["STORE_FEE"]` |
| `STORE_INTRO` | 10 anchors | DEF + POS/NEG_CONSTRAINT | → `store_info["STORE_INTRO"]` |
| `STORE_FOOD` | — | DEFINITION | → `store_info["STORE_FOOD"]` |
| `STORE_HOURS` | — | DEFINITION | → `store_info["STORE_HOURS"]` |
| `RULES` | — | DEFINITION + NOTE | → `cloud_rag` (Gemini + RAG) |
| `SENSITIVE` | — | DEFINITION + PRIORITY | → `reject` (固定回覆) |
| `CASUAL_CHAT` | — | DEFINITION + CONSTRAINT | → `local_llm` (Qwen Persona) |
| `UNKNOWN` | — | DEFINITION | → `UNKNOWN_FALLBACK` |

### 5.2 Constraint 機制

防止語意重疊導致誤分類：

```yaml
# NEGATIVE_CONSTRAINT（排除）
STORE_FEE:
  - NEGATIVE_CONSTRAINT: "卡坦島多少錢？" → 不是場地費，應分類為 STORE_INTRO

# POSITIVE_CONSTRAINT（強化）
STORE_INTRO:
  - POSITIVE_CONSTRAINT: "有賣[遊戲]嗎？", "庫存查詢", "商品價格"

# 交叉約束
STORE_INTRO:
  - NEGATIVE_CONSTRAINT: 不處理 Food / Fee / Address / Phone
```

---

## 六、API Endpoints

### 6.1 `POST /api/chat` — 主對話接口

**Request:**
```json
{
  "user_input": "廁所在哪？",
  "history": [
    {"role": "user", "content": "平日多少錢？"},
    {"role": "assistant", "content": "平日 60 元...", "intent": "STORE_FEE"}
  ],
  "game_context": {
    "game_id": "carcassonne"
  }
}
```

**Response:**
```json
{
  "response": "洗手間在店面後方喔，直走到底就看到了！",
  "intent": "STORE_TOILET",
  "confidence": 0.95,
  "source": "fastpath_content_static"
}
```

**`source` 欄位含義：**

| source 值 | 說明 |
|:---|:---|
| `fastpath_content_static` | Layer 1 命中 → 靜態回答 |
| `content_static` | Layer 2 判斷 → 靜態回答 |
| `local_llm_gen` | Layer 2 判斷 → Qwen Persona 生成 |
| `cloud_gen` | Layer 2 判斷 → Gemini RAG 生成 |
| `reject` | SENSITIVE 攔截 |
| `fallback` | 所有路由皆未命中 |

### 6.2 `GET /api/games` — 遊戲清單

回傳所有支援的桌遊及其 STT Injection 啟用狀態。

### 6.3 `GET /api/keywords/{game_id}` — STT 修正關鍵字

回傳指定遊戲的 Whisper 修正關鍵字列表。

---

## 七、Semantic Router 技術細節

### 7.1 Embedding Model

| 項目 | 規格 |
|:---|:---|
| **模型** | `intfloat/multilingual-e5-small` |
| **維度** | 384 |
| **語言** | 多語言（含中文） |
| **推論設備** | CPU（不佔用 GPU） |
| **快取** | `model_cache/` 目錄 |

### 7.2 向量比對流程

```
1. 啟動時: 對 semantic_routes.yaml 所有 anchor 做 encode → 存入記憶體
2. 收到請求: encode(user_input) → 與所有 anchor vectors 做 cosine_sim
3. 取 max_score → 若 >= 0.88 → 回傳對應 intent
4. 若 < 0.88 → 回傳 None（交給 LLM Router）
```

### 7.3 Threshold 調校紀錄

| 版本 | Threshold | 變更原因 |
|:---|:---|:---|
| V1 | 0.85 | 初始值，過於寬鬆 |
| V2 | **0.88** | 錨點品質提升後可提高精度要求，降低 false positive |

**調校建議**：
- 調高 → 精度 ↑ 但命中率 ↓（更多進入 LLM Router）
- 調低 → 命中率 ↑ 但可能誤判（如「網路奇兵的規則」命中 STORE_WIFI）

---

## 八、Stateless 架構設計

```
┌────────────┐          ┌────────────┐
│   Client    │ ──JSON──▶│   Server    │
│  (iPad)     │◀──JSON── │  (FastAPI)  │
│             │          │             │
│ ┌─────────┐│          │  ┌────────┐ │
│ │ History  ││          │  │Pipeline│ │
│ │ Manager  ││          │  │(無狀態) │ │
│ └─────────┘│          │  └────────┘ │
└────────────┘          └────────────┘
```

- **Server 不保存對話狀態**。每次請求由 Client 帶入完整 `history`。
- **好處**：Server 可水平擴展、重啟不丟失對話。
- **Client 職責**：管理 history、附加 `intent` 標籤、傳入 `game_context`。

---

## 九、UDP 服務發現

```yaml
# system_config.yaml
udp_service:
  port: 37020
  magic_string: "DISCOVER_AKKA_SERVER"
```

Client 在 LAN 廣播 magic string → Server 回應自身 IP + Port → Client 自動連線。

---

## 十、開發指南

### 10.1 新增 Store Intent（例：新增 STORE_RESERVATION）

```bash
# 1. semantic_routes.yaml — 新增 anchor
STORE_RESERVATION:
  - "我想訂位"
  - "可以預約嗎"
  - "訂位電話"
  ...（≥ 6 句）

# 2. prompts_local.yaml — router.system_prompt 內新增定義
13. STORE_RESERVATION:
    - DEFINITION: Questions about reservations or booking.
    - KEYWORDS: 訂位, 預約, 預訂.

# 3. intent_map.yaml — content_map 新增映射
STORE_RESERVATION: ["STORE_RESERVATION"]

# 4. store_info.yaml — responses 新增回答
STORE_RESERVATION:
  - "想訂位嗎？歡迎撥打 (02) 2552-9059！"
  - ...（≥ 5 個變體）
```

### 10.2 調整 Anchor 品質原則

1. **最低長度 ≥ 3 字**（避免單字誤判，如「廁所」可能命中桌遊名「全力衝廁」）
2. **使用完整問句**（「廁所在哪裡」優於「廁所」）
3. **涵蓋口語變化**（「想尿尿」、「可以借廁所嗎」等台灣口語）
4. **避免跨 Intent 重疊**（「多少錢」同時出現在 FEE 和 INTRO 時，需用 Constraint 區分）

### 10.3 測試

```bash
# 單元測試 (Pipeline 獨立執行)
cd project_akka/src
python pipeline.py

# Client 端測試
python tests/udp_client_test.py
```

### 10.4 Config 熱重載

```python
# 不需重啟 Server
pipeline.reload_configs()  # 重新載入所有 YAML + 重建向量索引
```

---

## 十一、已知限制與注意事項

| 項目 | 說明 |
|:---|:---|
| **E5 模型前綴** | 必須加 `"query: "` 前綴，否則向量品質下降（見 `semantic_router.py:68`） |
| **GPU 共用** | Semantic Router 強制用 CPU，避免搶佔 LLM 的 GPU VRAM |
| **History 過濾** | Cloud RAG 只注入 `intent == "RULES"` 的歷史，避免 token 浪費 |
| **Persona 長度** | 閒聊回覆限制 < 40 字（TTS 優化） |
| **禁止捏造商品** | Persona 被問到販售商品時，引導找櫃台而非自行回答 |
| **Allowlist 機制** | 遊戲專有名詞可能觸發 SENSITIVE，需在遊戲 metadata 設定白名單 |

---

*Project Akka — Baker Street Board Game Store*
*Architecture Document v2.0*
