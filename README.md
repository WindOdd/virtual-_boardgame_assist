桌遊店智慧語音助理系統開發規劃書
. 專案概述 (Executive Summary)x
1.1 專案目的
本計畫旨在開發一套「低延遲、高隱私、高準確度」的實體桌遊店專用語音助理。系統將在吵雜的店面環境中，透過語音介面即時解決顧客的兩大需求：
桌遊規則查詢：解決複雜的規則判例與教學問題。
店務資訊諮詢：快速回答 Wifi、廁所、計費等固定問題。
1.2 核心策略
採用 「邊緣採集 (Edge) + 中央路由 (Central Core)」 的混合架構，結合本地輕量化模型 (Local LLM) 與雲端強大模型 (Online LLM)，以達成成本與效能的最佳平衡。

2. 系統架構 (System Architecture)
2.1 桌邊端 (Edge Client)
角色：負責「聽」與「說」。
任務：在本地端完成語音訊號處理 (STT/TTS)，只傳送純文字數據，確保極致反應速度並減少頻寬佔用。
部署位置：每張桌子配置一台。
2.2 中央端 (Central Core)
角色：負責「思考」、「記憶」與「路由」。
任務：作為全店的大腦，管理多桌對話狀態、進行意圖分類，並調度本地或雲端模型生成回應。
部署位置：店內機房或櫃檯（全店共用一台）。

3. 硬體規格清單 (Hardware BOM)
3.1 桌邊終端 (Raspberry Pi 5)
核心主機：Raspberry Pi 5 (8GB RAM)
散熱方案：原廠主動式散熱器 (Active Cooler) (必要配件，防止高負載過熱)。
聲音輸入：USB 全向性會議麥克風 (建議具備硬體 AEC 回音消除功能)。
聲音輸出：USB 供電小喇叭 或 3.5mm 音箱。
網路連線：有線網路 (Ethernet) 優先。
3.2 中央伺服器 (NVIDIA Jetson Orin Nano)
核心主機：NVIDIA Jetson Orin Nano Developer Kit (8GB RAM)
儲存空間：NVMe SSD 512GB (Gen3/Gen4)。
作業系統設定：Headless Mode (無桌面模式)。
注意：務必關閉圖形介面，以釋放約 1.5GB 記憶體給 AI 模型使用。
網路連線：Gigabit Ethernet (必須有線連接)。

4. 軟體技術堆疊 (Software Stack)
4.1 桌邊端 (Raspberry Pi 5)
語音轉文字 (STT)：Whisper.cpp
模型：Medium
量化：q5_0 (5-bit Integer)
優化：啟用 Arm NEON 指令集加速 (純 CPU 推論)。
文字轉語音 (TTS)：Piper TTS
部署：On-device (本地運行)
語音包：zh_TW (繁體中文)。
控制邏輯：Python (Audio I/O, HTTP Request)。
4.2 中央端 (Jetson Orin Nano)
流程框架：LangChain + LangGraph (管理狀態機與路由)。
模型引擎：Jetson Containers (搭配 Ollama 或 NanoLLM)。
本地模型 (Router/Store)：Qwen 3 4B Instruct (2507版)
量化：Int4 (GGUF/AWQ)。
任務：意圖分類、回答店務、拒絕閒聊。
雲端模型 (Game Rules)：Google Gemini 2.5 Flash (via Vertex AI)。
任務：閱讀規則書 (Long Context)，回答複雜邏輯。

5. 核心運作邏輯 (Logic Workflow)
系統將支援最多 8 桌 同時運作，每桌獨立狀態。
5.1 輸入與記憶 (Input Node)
接收資料：{table_id, game_name, user_text}。
滑動視窗記憶 (Sliding Window)：
長度：最近 8 輪 (8 Turns)。
目的：支援代名詞理解 (如「它」、「那個」) 與連續追問。
5.2 智慧路由 (Router Node - Qwen 3 4B)
將用戶問題分為三類：
[STORE] 店務類：Wifi、廁所、低消、營業時間。
[GAME] 桌遊類：規則疑問、玩法教學。
[UNKNOWN] 其他類：閒聊、政治、無關話題。
5.3 分支處理 (Branching)
路徑 A：本地極速回應 ([STORE])
Local LLM 根據 System Prompt 內的店務資料，直接生成回答。
優點：零延遲、零 API 成本。
路徑 B：雲端深度推理 ([GAME])
系統讀取對應遊戲的 Markdown 規則書。
呼叫 Gemini 2.5 Flash。
Prompt 結構：規則書 + (8輪歷史對話) + 當前問題。
路徑 C：拒絕回應 ([UNKNOWN])
回傳預設訊息：「抱歉，我只能回答桌遊規則或店內服務相關的問題。」

6. 資料與文件規範 (Data Strategy)
6.1 桌遊規則書 (Markdown)
格式：標準 Markdown。
撰寫規範：
使用 #, ## 明確區分層級。
將圖示邏輯轉化為文字描述 (例如：「不能斜角擺放」)。
去除無意義的裝飾性文字。
快取策略：不使用 Context Caching (因 Flash 成本低且單本規則書未達門檻)。
6.2 店務資訊庫 (Hard-coded)
直接寫入 Python 程式碼或 Local LLM 的 System Prompt 中。
包含：Wifi SSID/密碼、廁所位置引導、收費標準。

7. 專案執行階段 (Roadmap)
Phase 1: 基礎建設 (Foundation)
[Server] 架設 Orin Nano Headless 環境，部署 Qwen 3 4B (Int4)。
[Client] 架設 Pi 5，測試 Whisper.cpp 中文辨識率與 Piper TTS 發音。
[Network] 確保兩端透過內網 (LAN) 連線成功。
Phase 2: 邏輯核心 (The Brain)
[Server] 使用 LangGraph 實作路由狀態機。
[Server] 整合 Gemini Vertex AI SDK。
[Server] 實作多桌記憶模組 (Based on Table ID)。
[Data] 製作第一份《卡卡頌》Markdown 規則書。
Phase 3: 整合與驗證 (Integration)
[System] 端對端串接 (Mic -> Pi 5 -> Orin -> Model -> Pi 5 -> Speaker)。
[UX] 實作 Client 端「思考中」音效 (避免等待時的靜默焦慮)。
[Test] 單桌 POC 實測：Wifi 問答 (秒回)、規則問答 (準確)、閒聊 (拒絕)。
Phase 4: 壓力測試 (Deployment)
[System] 模擬 8 桌並發請求，測試 Orin Nano 的排隊 (Queuing) 狀況。
[System] 確認長時間運作下的記憶體釋放狀況 (Memory Leak Check)。

8. 風險評估 (Risk Management)
Orin Nano 記憶體不足 (OOM)
對策：嚴格執行 Headless 模式；確保 Qwen 使用 Int4 量化；若 8 桌併發導致記憶體吃緊，可將記憶視窗從 8 輪降為 5 輪。
噪音干擾導致辨識錯誤
對策：使用 Whisper Medium 模型 (非 Small)；選用指向性麥克風；在 Router Prompt 加入模糊修正指令。
網路延遲
對策：Server 端務必使用有線網路；選用 Gemini 2.5 Flash (低延遲版)。

