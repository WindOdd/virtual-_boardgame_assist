版本：v3.0 (Model Upgrade Edition)
日期：2025-12-03
核心架構：Edge-Cloud Hybrid, Stateless Server, Data-Driven (YAML), Unified Utilities
AI 模型：Local Qwen3 + Online Gemini 2.5

1. 系統架構 (System Architecture)
1.1 設計原則
本系統採用 前端 (Client) - 後端 (Server) 分離架構。
無狀態 (Stateless)：Server 不保存對話紀錄，所有上下文 (Context) 由 Client 維護並於請求時帶入。
資料驅動 (Data-Driven)：所有邏輯變數（遊戲列表、敏感詞、Prompt）皆抽離至 YAML/JSON 設定檔。
混合 AI (Hybrid AI)：
Local LLM: 使用 Ollama 執行 Qwen3-4B-Instruct，負責低延遲的意圖路由與閒聊。
Online LLM: 使用 Gemini 2.5 Flash，負責高準確度的規則檢索 (RAG)。
1.2 處理流程圖 (Pipeline)
程式碼片段
graph TD
    User((使用者)) <-->|語音/UI操作| Client[Client: 樹莓派/PC]
    
    subgraph "Local Server (Jetson Orin Nano)"
        %% 服務發現層
        Client -.->|UDP Broadcast (37020)| UDPServer[UDP Discovery Service]
        UDPServer -.->|回傳 IP, Config, GameList| Client
        
        %% API 層
        Client <-->|HTTP POST /ask| FastAPI[Server.py]
        
        %% 邏輯處理層
        FastAPI -->|1. 意圖路由| Router[LocalLLM Router]
        Router -->|2. 安全過濾| Filter[FilterService]
        
        Filter -- Pass --> Logic{邏輯分流}
        Filter -- Block --> BlockRes[回傳 POLITICAL]
        
        Logic -- GAME --> Gemini[GeminiRAGService]
        Logic -- STORE --> StoreRes[Local Store Info]
        Logic -- UNKNOWN --> Joker[Local Joker]
        
        %% 模型服務層
        Router -.->|Ollama API| Ollama[Qwen3-4B-Instruct]
        Gemini -.->|Google GenAI SDK| GoogleAPI[Gemini 2.5 Flash]
    end


2. 核心 AI 模型規格 (AI Model Specifications)
2.1 Local LLM (Server 端推理)
引擎: Ollama
模型: Qwen3-4B-Instruct
來源: HuggingFace - Qwen3-4B-Instruct-2507
Python SDK: ollama-python
用途: 意圖分類 (Router)、閒聊 (Joker)、店務回答。
2.2 Online LLM (雲端推理)
服務: Google Gemini API
模型: Gemini 2.5 Flash
文件: Google AI Models
Python SDK: google-genai (新版 SDK)
用途: 複雜遊戲規則檢索 (RAG)、長文本理解。

3. 專案檔案結構 (Project Structure)
Plaintext
local_serve/
├── config/
│   ├── safety_filter.yaml      # [維護] 黑白名單與總開關
│   ├── store_info.json         # [維護] 店務資訊
│   ├── llm_config.json         # [設定] Ollama (Qwen3)
│   └── gemini_config.yaml      # [設定] Gemini (2.5 Flash)
│
├── prompts/
│   ├── prompt_router.txt       # 分類 Prompt
│   ├── prompt_joker.txt        # 閒聊 Prompt
│   └── system_role.txt         # RAG Prompt
│
├── rules/
│   ├── _index.yaml             # [維護] 遊戲索引資料庫
│   ├── avalon.md               # [維護] 規則檔
│   └── *.md                    # ...
│
├── services/
│   ├── discovery.py            # UDP Server
│   ├── filter.py               # 安全過濾
│   ├── game_data.py            # 遊戲資料管理
│   ├── local_llm.py            # Ollama Wrapper (使用 ollama-python)
│   └── gemini_rag.py           # Gemini Wrapper (使用 google-genai)
│
├── utils/
│   ├── __init__.py
│   └── boardgame_utils.py      # 共用工具 (ConfigLoader, PromptLoader)
│
├── requirements.txt            # 包含 ollama, google-genai
└── server.py                   # FastAPI 主程式


4. 設定檔規格 (Configuration)
4.1 Local LLM 設定 (config/llm_config.json)
JSON
{
  "model_settings": {
    "model_name": "qwen3:4b-instruct",  // 需與 `ollama list` 名稱一致
    "host": "http://localhost:11434"
  },
  "router_settings": {
    "prompt_file": "prompt_router",
    "temperature": 0.1
  },
  "joker_settings": {
    "prompt_file": "prompt_joker",
    "temperature": 0.8
  }
}

4.2 Gemini 設定 (config/gemini_config.yaml)
YAML
# 使用 Gemini 2.5 Flash 模型
model_name: "gemini-2.5-flash"

generation_config:
  temperature: 0.5
  top_p: 0.95
  max_output_tokens: 1024

system_prompt_file: "system_role"


5. API 通訊協定 (API Specification)
Endpoint: POST /ask
Content-Type: application/json
5.1 請求格式 (Request)
JSON
{
  "table_id": "T01",
  "session_id": "sess-01",
  "game_name": "阿瓦隆",        // 若無則傳 null
  "user_text": "刺客可以殺誰？",
  "history": [                 // Client 維護的 Deque 歷史
    {"role": "user", "content": "..."},
    {"role": "model", "content": "..."}
  ]
}

5.2 回應格式 (Response)
JSON
{
  "answer": "刺客在遊戲結束時...",
  "source": "CLOUD_GEMINI",   // 來源
  "category": "GAME",         // 分類
  "hint": "建議選擇遊戲：阿瓦隆",
  "error": null 
}


6. 後端處理邏輯 (Server Pipeline)
意圖路由 (Local Qwen3)：
注入 game_knowledge (全域遊戲關鍵字)。
判斷意圖：GAME, STORE, UNKNOWN, POLITICAL。
情境過濾 (Filter)：
若 Router=GAME $\rightarrow$ 寬鬆模式 (放行白名單)。
若 Router!=GAME $\rightarrow$ 嚴格模式 (攔截黑名單)。
邏輯分流：
GAME $\rightarrow$ Gemini 2.5 Flash (RAG)。
STORE/UNKNOWN $\rightarrow$ Local Qwen3 直接回應。

7. 部署配置 (Deployment)
7.1 環境需求
Python: 3.10+
Packages:
Bash
pip install fastapi uvicorn requests PyYAML ollama google-genai


7.2 模型準備
Ollama (Local):
由於 Qwen3 尚未內建於 Ollama library，需手動匯入 GGUF 或使用 HuggingFace 整合功能：
Bash
# 假設您已從 HuggingFace 下載了 GGUF
ollama create qwen3:4b-instruct -f Modelfile
# 啟動服務
ollama serve


Gemini (Cloud):
取得 Google API Key 並設定環境變數：
Bash
export GEMINI_API_KEY="your_api_key"


7.3 啟動服務
Bash
# 進入專案目錄
cd localllm_serve

# 啟動 Server (自動載入 UDP Discovery, Qwen3 設定, Gemini 設定)
python server.py

