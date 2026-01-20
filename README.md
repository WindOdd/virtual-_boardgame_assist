# Project Akka: 桌遊店智慧語音助理系統

[![Version](https://img.shields.io/badge/version-v9.5-blue.svg)](https://github.com/yourusername/project-akka)
[![Status](https://img.shields.io/badge/status-Ready%20for%20Coding-green.svg)](https://github.com/yourusername/project-akka)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

> 為桌遊店打造的低延遲、具備鮮明角色性格的語音助理系統

**最後更新:** 2026/01/20  
**版本:** v9.6 (Optimized for Experience & Load)  
**狀態:** 鎖定 (Ready for Coding)

---

## 📋 目錄

- [系統概述](#系統概述)
- [核心架構](#核心架構)
- [處理流程](#處理流程)
- [系統配置](#系統配置)
- [硬體規格](#硬體規格)
- [API 文件](#api-文件)
- [驗收標準](#驗收標準)
- [快速開始](#快速開始)

---

## 🎯 系統概述

本系統旨在為桌遊店提供一套低延遲、具備鮮明角色性格的語音助理。v9.5 版本引入「雙軌隨機機制」與「負載卸載保護」，在硬體資源受限下最大化使用者體驗。

### 核心特色

- ⚡ **低延遲響應** - Fast Path 可在 10ms 內完成常見查詢
- 🎭 **角色人設** - 熱情親切的專業桌遊店員風格
- 🔄 **混合架構** - 結合雲端與邊緣運算的優勢
- 🛡️ **負載保護** - 智慧卸載機制防止系統過載
- 🎲 **遊戲專精** - 支援專業桌遊規則查詢

---

## 🏗️ 核心架構

### 三層實體架構

```
┌─────────────────────────────────────────────────────────┐
│                    Cloud Brain (雲端)                    │
│         Google Gemini 2.5 Flash                         │
│      負責: RAG 規則推論 + 複雜語意理解                      │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                   Local Brain (本地)                     │
│         NVIDIA Jetson + Ollama/Qwen 4B                  │
│       負責: 意圖路由 + 敏感詞攔截 + 短閒聊生成               │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                   Edge Client (終端)                     │
│                    iPad + WhisperKit                    │
│      負責: STT/TTS + 對話狀態 + 填補音效                    │
└─────────────────────────────────────────────────────────┘
```

### 技術棧

| 層級 | 技術 | 用途 |
|------|------|------|
| Cloud | Google Gemini 2.5 Flash | 規則推論、複雜查詢 |
| Local | Ollama + Qwen 3:4B | 意圖分類、閒聊生成 |
| Edge | WhisperKit (On-device) | 語音轉文字 |
| Edge | iOS TTS | 文字轉語音 |

---

## 🔄 處理流程

系統採用五階段嚴格順序執行，最大化 CPU 利用率並保護 GPU 算力:

### Stage I: 實體映射 (Entity Mapping)
**必定執行** - CPU 密集型

```
輸入: "卡卡獸怎麼玩"
     ↓
掃描 store_info.yaml 別名庫
     ↓
命中: "卡卡獸" → mapped_game_id = "Carcassonne"
```

### Stage II: 極速反射 (Fast Path)
**條件執行** - CPU 優先路徑

```
觸發條件: mapped_game_id is None
安全閥:
  ├─ 輸入 > 12 字 → 跳過
  └─ 包含遊戲關鍵字 → 跳過

命中檢查:
  ├─ 常用閒聊 (Hello/Thanks) → 隨機回應
  └─ 店務關鍵字 (Wifi/Toilet) → 隨機回應

延遲: < 10ms
```

### Stage III: 意圖路由 (LLM Router)
**GPU 推論** - 細顆粒度分類

```
Local LLM (Qwen) 分類:
├─ RULES (規則查詢)
├─ STORE_WIFI (網路)
├─ STORE_TOILET (廁所)
├─ STORE_PRICING (價格)
├─ SENSITIVE (敏感內容)
└─ IRRELEVANT (閒聊)

輸出: JSON 格式意圖
```

### Stage IV: 負載卸載 (Load Shedding)
**保護機制** - v9.5 新增

```
if intent == IRRELEVANT and concurrent_requests >= 4:
    return random_choice(responses_pool.busy_fallback)
    # 例: "現在店裡像戰場一樣,我晚點再跟你聊!"
```

### Stage V: 執行與回應 (Action)

| 意圖類型 | 處理方式 | 延遲 |
|---------|---------|------|
| RULES | Cloud RAG (Gemini) | ~2-3s |
| STORE_* | CPU 隨機抽取語錄 | ~0.5s |
| IRRELEVANT | Local LLM 生成 (40字限制) | ~1-2s |
| SENSITIVE | 拒絕語錄 | <0.1s |

---

## ⚙️ 系統配置

### 目錄結構

```
project-akka/
├── config/
│   ├── system_config.yaml      # 系統參數
│   ├── store_info.yaml         # 店務與語錄
│   └── prompts.yaml            # 路由與人設
├── rules/
│   └── carcassonne.md          # 遊戲規則文件
└── /etc/systemd/system/
    └── ollama.service          # Ollama 服務配置
```

### 核心配置檔案

#### 1. Ollama Service 設定

```ini
# /etc/systemd/system/ollama.service
[Service]
Environment="OLLAMA_NUM_PARALLEL=4"         # 4路並發
Environment="OLLAMA_MAX_LOADED_MODELS=1"    # 鎖定單一模型
Environment="OLLAMA_KEEP_ALIVE=5m"          # 避免頻繁卸載
```

#### 2. system_config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  concurrency: 8                # 應用層 8 Threads

llm_settings:
  local_model:
    name: "qwen3:4b-instruct"
    num_ctx: 1024               # 記憶體硬上限
    num_predict: 120            # 生成上限 (~50-60 中文字)
    temperature: 0.1
```

#### 3. store_info.yaml (範例)

```yaml
# 常用閒聊 Fast Path
common_chat:
  greetings:
    keywords: ["你好", "早安", "嗨"]
    responses:
      - "喲！準備好決鬥了嗎？"
      - "早安！今天適合玩策略遊戲。"

# 店務回應池
responses_pool:
  wifi:
    - "Wifi 帳號 BoardGame_Guest，密碼 playmoregames。"
  busy_fallback:
    - "現在店裡像戰場一樣，我晚點再跟你聊！"

# 支援遊戲列表
supported_games:
  - name: "Carcassonne"
    display_name: "卡卡頌"
    aliases: ["卡卡送", "卡卡獸"]
    has_local_rules: true
    rule_file: "rules/carcassonne.md"
```

#### 4. prompts.yaml (人設範例)

```yaml
enthusiastic_persona: |
  你是「{STORE_NAME} 桌遊店」的熱情店員。
  
  【說話風格】
  1. 熱情親切：多用「歡迎」、「沒問題」等正向詞彙
  2. 專業引導：回答要具體且有幫助
  3. 語氣助詞：適度使用「喔！」、「耶！」增加親切感
  
  【絕對指令】
  1. 字數限制：回答控制在 40 字 (約 1-2 句話) 以內
  2. 避免幻覺：不清楚時引導客人詢問現場夥伴
```

---

## 💻 硬體規格

### 伺服器端 (Edge Server)

| 項目 | 規格 |
|------|------|
| 機型 | NVIDIA Jetson Orin Nano Super |
| 記憶體 | 8GB VRAM |
| 電源模式 | MAXN (25W) - `sudo nvpmodel -m 0` |
| 散熱 | 強制風扇最大轉 - `sudo jetson_clocks` |
| 防護 | 必須掛載 8GB Swap File |

### 客戶端 (Client Node)

| 功能 | 技術 |
|------|------|
| STT | On-device WhisperKit |
| TTS | iOS 原生 TTS |
| 填補機制 | 2.5秒後播放本地音效 ("嗯..."、"檢索中...") |
| 動態注入 | 當前遊戲關鍵字注入 WhisperKit |

---

## 📡 API 文件

### 1. 主要對話 API

**POST** `/api/chat`

```json
// Request
{
  "user_input": "卡卡頌怎麼玩",
  "current_game": "Carcassonne"  // Optional
}

// Response
{
  "response": "卡卡頌是拼放板塊的遊戲...",
  "intent": "RULES",
  "mapped_game": "Carcassonne",
  "source": "cloud_rag",
  "latency_ms": 2341
}
```

### 2. 遊戲關鍵字 API (v9.5 新增)

**GET** `/api/game_keywords?game_id=Carcassonne`

```json
// Response
{
  "keywords": ["卡卡頌", "米普", "板塊", "農夫", "騎士"]
}
```

**用途:** 供 iPad Client 動態設定 WhisperKit 上下文，提升辨識準確度

---

## ✅ 驗收標準

| ID | 輸入 | 預期流程 | 預期結果 | 延遲 |
|----|------|---------|---------|------|
| T01 | "Wifi 密碼多少" | FastPath → CPU Random | 隨機 Wifi 語錄 | <0.1s |
| T02 | "你好" | FastPath → CPU Random | 隨機招呼語 | <0.1s |
| T03 | "你好卡卡頌" | Entity Hit → Router | 進入規則查詢 | ~1.0s |
| T04 | "我想去洗手間" | Router → CPU Random | 隨機廁所語錄 | ~1.0s |
| T05 | "講個笑話" (滿載) | Router → Load Shedding | 忙碌罐頭訊息 | <0.1s |
| T06 | "卡卡獸怎麼玩" | Entity Hit → Cloud RAG | 規則解答 | ~2-3s |

---

## 🚀 快速開始

### 前置需求

- NVIDIA Jetson Orin Nano Super (8GB)
- Ubuntu 20.04+
- Ollama installed
- Python 3.8+

### 安裝步驟

```bash
# 1. Clone 專案
git clone https://github.com/yourusername/project-akka.git
cd project-akka

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 配置 Ollama
sudo systemctl edit ollama.service
# 添加環境變數 (參考上方配置)

# 4. 下載模型
ollama pull qwen3:4b-instruct

# 5. 設定 Jetson 效能模式
sudo nvpmodel -m 0
sudo jetson_clocks

# 6. 啟動服務
python main.py
```

### 驗證安裝

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "你好"}'
```

---

## 📝 授權

MIT License - 詳見 [LICENSE](LICENSE) 文件

---

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request！

---

## 📧 聯絡方式

如有問題請聯絡: [kdlmapcomtw@gmail.com](mailto:kdlmapcomtw@gmail.com)

---

**Made with ❤️ for Board Game Cafés**