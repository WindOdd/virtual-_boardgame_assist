# Project Akka: 桌遊店語音助理 (Board Game Store Voice Assistant)

Project Akka 是一個專為桌遊店設計的本地化語音助理，部署於「貝克街桌遊專賣店」。

本系統採用 **V2 雙層語意路由架構 (Dual-Layer Routing)**，結合輕量級語意搜尋模型與本地 LLM。設計目標是在 **NVIDIA Jetson Orin Nano** 等邊緣裝置上實現毫秒級的店務回應，同時保留強大的雲端 LongContext 能力進行複雜的桌遊規則教學。

---

## 📂 專案結構 (Project Structure)

本 Repository 包含兩代架構版本，**請開發者專注於 `project_akka/` 目錄**。

* **`project_akka/` (✅ Current - V2 Architecture)**
    * **這是目前活躍開發的版本。**
    * 採用雙層路由架構 (Semantic Router + Local LLM)。
    * 包含所有最新的意圖定義 (`STORE_ADDRESS`, `STORE_FEE` 等) 與設定檔。
    * **所有新功能與修復請在此目錄進行。**
    * 入口點：`src/main.py`

* `legacy_v1/` (❌ Deprecated - V1 Archive)
    * 舊版架構備份 (僅供參考)。
    * 包含早期的 Regex 路由與單體 LLM 測試代碼。
    * **請勿執行此目錄下的程式碼。**

---

## 🏗️ 系統架構 (System Architecture)

系統設計目標是為了在有限算力下，最大化回應速度與準確度。

| 層級 (Layer) | 技術棧 (Tech Stack) | 功能描述 (Description) | 典型延遲 (Latency) |
| :--- | :--- | :--- | :--- |
| **Layer 1 (FastPath)** | **Semantic Router**<br>(`intfloat/e5-small-v2`) | **[店務攔截]**<br>使用向量相似度 (Embedding) 直接攔截高頻店務問題（如：地址、WIFI、廁所），不經過 LLM，回應極快。 | **< 50ms** |
| **Layer 2 (Router)** | **Local LLM**<br>(Qwen-4B-Chat-Int4) | **[意圖判斷]**<br>處理 Layer 1 無法攔截的模糊語句，或判斷是否進入規則教學模式。具備完整的人設與防呆機制。 | ~800ms |
| **Layer 3 (LongContext)** | **Cloud LLM**<br>(Google Gemini 1.5) | **[規則講解]**<br>針對特定桌遊（如：卡坦島、璀璨寶石）進行深度規則檢索與教學。 | 1.5s+ |

---

## 💻 硬體與環境需求 (Hardware Requirements)

本系統採用彈性架構 (Hardware Agnostic)，支援多種運行環境：

### 推薦配置 (Edge Device)
* **Device**: NVIDIA Jetson Orin Nano (8GB)
* **Backend**: `nano_llm` (Jetson Native) or Ollama (Docker)
* **Performance**: 最佳化後 Layer 2 回應約 800ms

### 通用配置 (Generic / PC / Mac)
* **System**: 任何可運行 [Ollama](https://ollama.com/) 的電腦 (Mac M-series, Windows/Linux with GPU)。
* **Requirements**:
    * Python 3.10+
    * RAM: 8GB+ (for Qwen-4B)
    * Ollama Service (Running in background)

### 必要依賴
* **Layer 1**: 需安裝 `sentence-transformers` (CPU 即可運行，速度極快)。
* **Layer 3**: 需具備 Google Gemini API Key。

---

## 🎯 意圖分類 (Intent Definitions)

系統目前支援 **12 種核心意圖**，由 Layer 1 與 Layer 2 協同運作：

### 🏪 店務類 (Store Operations)
| 意圖標籤 (Intent Tag) | 定義與範例 (Definition & Examples) | 備註 (Note) |
| :--- | :--- | :--- |
| **STORE_ADDRESS** | **詢問地址、位置**<br>Ex: "店怎麼走？", "你們在哪裡？" | 用於回覆地址與交通指引。 |
| **STORE_PHONE** | **詢問電話、聯絡**<br>Ex: "電話幾號？", "我要訂位" | 用於回覆聯絡電話。 |
| **STORE_FEE** | **詢問入場費、計價**<br>Ex: "怎麼收費？", "一小時多少錢？" | **[注意]** 僅限場地費/入場費，不包含商品價格。 |
| **STORE_INTRO** | **詢問商品販售、店鋪簡介**<br>Ex: "有賣卡坦島嗎？", "這盒遊戲賣多少？" | 專門處理「購買商品」與「庫存查詢」。 |
| **STORE_FOOD** | **詢問餐飲**<br>Ex: "有賣吃的嗎？", "可以帶外食嗎？" | 回覆菜單或外食政策。 |
| **STORE_HOURS** | **詢問營業時間**<br>Ex: "幾點關門？", "今天開到幾點？" | |
| **STORE_WIFI** | **詢問網路**<br>Ex: "Wifi密碼多少？" | |
| **STORE_TOILET** | **詢問廁所**<br>Ex: "廁所在哪？", "我想尿尿" | |

### 🎲 核心與其他 (Core & Others)
| 意圖標籤 (Intent Tag) | 定義與範例 (Definition & Examples) | 備註 (Note) |
| :--- | :--- | :--- |
| **RULES** | **桌遊規則教學**<br>Ex: "這張牌怎麼用？", "卡坦島怎麼玩？" | 系統核心功能，觸發 LongContext 流程。 |
| **SENSITIVE** | **安全過濾**<br>Ex: 政治、暴力、色情話題 | 最高優先級攔截。 |
| **CASUAL_CHAT** | **閒聊**<br>Ex: "你好", "有人在嗎" | 簡單寒暄與人設互動。 |
| **UNKNOWN** | **無法識別**<br>Ex: "今天天氣如何？" | 超出服務範圍的問題。 |

---

## 🚀 快速啟動 (Quick Start)

請確保您已安裝 Python 3.10+。

### 1. 環境設定
進入 V2 架構目錄並安裝相依套件：

```bash
cd project_akka
pip install -r requirements.txt
```

### 2. 設定 API Key
本系統 Layer 3 (longContext ) 依賴 Google Gemini API。請設定環境變數：

Linux / Mac (Bash):
export GOOGLE_API_KEY="your_api_key"

Windows (PowerShell):
$env:GOOGLE_API_KEY="your_api_key"

### 3. 啟動系統
執行主程式以啟動語音助理服務：

```bash
python main.py
```
### ⚙️ 關鍵設定檔 (Configuration)
若需調整路由邏輯或回答內容，請修改 project_akka/config/ 下的檔案：

1. semantic_routes.yaml (Layer 1 設定)

    I.  定義語意搜尋的「錨點句子 (Anchors)」。
    II. 若發現簡單的店務問題（如問地址）回應太慢，請檢查此處是否有對應的問句。
    III. 關鍵變更：V2 已加入 STORE_ADDRESS 與 STORE_PHONE 分流。

2. prompts_local.yaml (Layer 2 設定)

    I.  定義 LLM 的 System Prompt 與分類邏輯。
    II. 包含「負向約束 (Negative Constraints)」，例如：防止 STORE_FEE 搶走「買遊戲」的問題。

3. store_info.yaml (資料庫)

    I.  店務意圖的標準回答庫（Static Responses）。
    II. 若要修改地址、電話、WIFI 密碼或營業時間，請直接編輯此檔。

4. system_config.yaml
    I.  設定硬體參數、Threshold (信心閾值) 與 Log 等級。
### 🛠️ 開發與維護 (Development)

1.  新增意圖：需同時修改 semantic_routes.yaml (Layer 1)、prompts_local.yaml (Layer 2) 與 store_info.yaml (回應)。

2.測試建議：修改後請執行 tests/udp_client_test.py 進行回歸測試。

Last Updated: 2026/01 - V2 Architecture Release

## 📝 授權

MIT License - 詳見 [LICENSE](LICENSE) 文件

---

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request！

---

## 📧 聯絡方式

如有問題請聯絡: [kdlmapcomtw@gmail.com](mailto:kdlmapcomtw@gmail.com)