🎲 Board Game Store — 智慧語音助理系統
<div align="center"> <img src="https://img.shields.io/badge/AI%20Voice%20Assistant-Boardgame-blueviolet?style=for-the-badge" /> <img src="https://img.shields.io/badge/Raspberry%20Pi%205-Edge%20Client-red?style=for-the-badge" /> <img src="https://img.shields.io/badge/Jetson%20Orin%20Nano-AI%20Core-green?style=for-the-badge" /> <img src="https://img.shields.io/badge/Local%20LLM-Qwen%203%204B-orange?style=for-the-badge" /> <img src="https://img.shields.io/badge/Cloud%20LLM-Gemini%202.5%20Flash-yellow?style=for-the-badge" /> <img src="https://img.shields.io/badge/LICENSE-MIT-lightgrey?style=for-the-badge" /> </div> <br/> <div align="center"> <img src="https://img.icons8.com/color/240/board-games.png" width="160" alt="board game icon"/> <h3>低延遲・高隱私・高準確度的桌遊店語音助理系統</h3> </div>

## 📘 目錄

-   [🚀 專案介紹](#-專案介紹)
-   [🧩 系統架構](#-系統架構)
-   [🖥️ 硬體規格](#️-硬體規格)
-   [🧠 軟體技術堆疊](#-軟體技術堆疊)
-   [🔁 系統運作流程](#-系統運作流程)
-   [📄 規則書與資料格式](#-規則書與資料格式)
-   [🗺️ 開發時程](#️-開發時程)
-   [⚠️ 風險管理](#️-風險管理)
-   [📜 授權](#-授權)

# 🚀 專案介紹

本專案致力於打造 **實體桌遊店專用智慧語音助理系統**，提供：

🎙️ **桌遊規則查詢**\
📚 **複雜規則推理**\
🛎️ **店務資訊回答**\
⚡ **低延遲、隱私安全的本地化語音體驗**

採用 **Edge + Central Core** 混合架構，結合 **本地 STT/TTS、Local
LLM、Cloud LLM** 達成效能與成本最優化。

# 🧩 系統架構

## Edge（桌邊端：Raspberry Pi 5）

負責 **聽**（STT）與 **說**（TTS），僅傳送純文字到中央。

## Central Core（Jetson Orin Nano）

負責 **推理、路由、記憶、協作多桌**。

### 路由邏輯

  類別      說明              處理方式
  --------- ----------------- -----------
  STORE     店務資訊          Local LLM
  GAME      桌遊規則          Cloud LLM
  UNKNOWN   閒聊 / 無關問題   拒答

# 🖥️ 硬體規格

## Edge（Raspberry Pi 5）

-   Raspberry Pi 5 (8GB)
-   主動式散熱器
-   USB 麥克風（含 AEC）
-   USB / 3.5mm 喇叭
-   Ethernet 建議使用

## Central（Jetson Orin Nano）

-   Jetson Orin Nano 8GB
-   512GB NVMe SSD
-   Headless mode
-   Gigabit Ethernet

# 🧠 軟體技術堆疊

## Edge（Pi 5）

-   Whisper.cpp (Medium q5_0)
-   Piper TTS zh_TW
-   Python 控制

## Central（Orin Nano）

-   LangChain + LangGraph
-   Qwen 3 4B Int4（Local）
-   Gemini 2.5 Flash（Cloud）

# 🔁 系統運作流程

1.  Pi 5：Whisper STT\
2.  Router：Qwen Intent 分類\
3.  STORE → Local 回答\
4.  GAME → 規則書 + 問題 → Gemini 推理\
5.  Pi 5：TTS 播放

支援 **多桌最多 8 桌**。

# 📄 規則書與資料格式

## Markdown 規則書

-   清楚分層
-   圖解 → 文字描述
-   不使用 context caching

## 店務資料

Hard-coded：Wifi / 廁所 / 收費方式

# 🗺️ 開發時程

-   Phase 1：基礎建設（Pi + Orin）
-   Phase 2：路由大腦（LangGraph）
-   Phase 3：整合測試
-   Phase 4：8 桌壓力測試

# ⚠️ 風險管理

-   Orin 記憶體不足 → Int4 + Headless
-   噪音環境 → Whisper Medium + AEC
-   網路延遲 → 必須有線網路

# 📜 授權

MIT License
