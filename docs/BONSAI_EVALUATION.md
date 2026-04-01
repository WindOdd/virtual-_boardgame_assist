# Bonsai-8B 整合評估報告
## 針對 Project Akka 現有架構的可行性分析

> **評估對象**：[PrismML Bonsai-8B](https://huggingface.co/prism-ml/Bonsai-8B-gguf)
>
> **評估日期**：2026/04
>
> **現有架構**：Qwen-4B (Int4) + e5-small (embedding) + Gemini (Cloud)
>
> ⚠️ **重要更新**：Ollama **目前不支援** Q1_0_g128 格式
> 
> 需使用 **llama.cpp** 替代方案（見第七章）

---

## 一、Bonsai-8B 技術規格

| 項目 | 規格 |
|:---|:---|
| **參數量** | 8.2B (Qwen-4B 的 2 倍) |
| **量化方式** | End-to-end 1-bit (embeddings, attention, MLP, LM head 全 1-bit) |
| **模型大小** | 1.15 GB (vs Qwen-4B-Int4: ~2.5 GB) |
| **格式** | GGUF (Q1_0_g128) |
| **理論優勢** | 記憶體 ↓50%、能耗更低、推論速度可能更快 |
| **理論風險** | 1-bit 量化對繁體中文/台灣口語的表現未知 |

---

## 二、可替代組件分析

### 2.1 Local LLM (Router + Persona) — **可行性：中**

```
現有：Qwen-4B-Chat-Int4 (2.5 GB, ~800ms/gen)
      ├─ Router: 輸出結構化 JSON (12 類 Intent)
      └─ Persona: 生成閒聊回覆 (<40字)

替換方案：Bonsai-8B (1.15 GB, 推論速度未知)
```

**優勢：**
- ✅ 記憶體減半（2.5 GB → 1.15 GB），更適合低階硬體
- ✅ 參數量更大 (8.2B > 4B)，理論上推理能力更強
- ✅ 能耗更低，適合長時間運行

**風險：**
- ⚠️ **Ollama 相容性**：需確認 Ollama 是否支援 `Q1_0_g128` 格式
  - 目前 Ollama 主流支援：Q4_K_M, Q5_K_M, Q8_0
  - Q1_0_g128 是新格式，可能需要 Ollama 最新版或 llama.cpp 支援
- ⚠️ **繁體中文 / 台灣口語表現未知**
  - Qwen 系列針對中文優化，Bonsai-8B 需實測
  - 1-bit 量化對中文 Token 的精度損失需驗證
- ⚠️ **JSON 格式控制**
  - Router 需要穩定輸出 `{"intent": "...", "confidence": ...}`
  - 極端量化模型可能在結構化輸出時不穩定

### 2.2 Embedding Model (Semantic Router) — **不建議**

```
現有：e5-small (384 維, ~120 anchors, CPU 推論)

替換方案：Bonsai-8B embedding layer？
```

**不建議原因：**
- ❌ Bonsai-8B 是 LLM，不是專門的 Embedding Model
- ❌ e5-small 只有 ~100MB，已經夠輕量
- ❌ 用 8.2B LLM 做 embedding 會拖慢 FastPath (目前 <50ms)
- ❌ 語義向量檢索需要穩定的向量空間，1-bit 量化可能影響余弦相似度精度

**結論**：Semantic Router 保持 e5-small 不變。

### 2.3 Cloud LLM (RAG) — **不適用**

Cloud LLM 使用 Gemini API，不涉及本地模型替換。

---

## 三、整合改動幅度評估

### 方案 A：**僅替換 Local LLM (Qwen-4B → Bonsai-8B)**

#### 3.1 程式碼改動

| 檔案 | 改動內容 | 難度 |
|:---|:---|:---:|
| `system_config.yaml` | 修改 `model.local.name: "bonsai-8b"` | ⭐ |
| `local_llm_client.py` | 無需改動 (Ollama API 不變) | — |
| `prompts_local.yaml` | **可能需要調整 System Prompt** | ⭐⭐⭐ |

**關鍵風險：Prompt 相容性**

Qwen-4B 的 Prompt 模板：
```
<|im_start|>system
You are a helpful assistant.
<|im_end|>
<|im_start|>user
...
```

Bonsai-8B 的模板格式**需實測確認**，可能不同。

#### 3.2 部署改動

```bash
# 1. 下載 Bonsai-8B GGUF
wget https://huggingface.co/prism-ml/Bonsai-8B-gguf/resolve/main/bonsai-8b-q1_0_g128.gguf

# 2. 檢查 Ollama 支援度
ollama --version  # 需要 >= v0.5.0 (假設)

# 3. 建立 Modelfile
FROM ./bonsai-8b-q1_0_g128.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9

# 4. 匯入 Ollama
ollama create bonsai-8b -f Modelfile

# 5. 測試
ollama run bonsai-8b "測試中文回覆"
```

**潛在問題：**
- ⚠️ 如果 Ollama 不支援 Q1_0_g128，需要降級使用 llama.cpp 直接推論
- ⚠️ 需修改 `local_llm_client.py` 切換到 llama.cpp API

#### 3.3 測試驗證

| 測試項目 | 測試方法 | 通過標準 |
|:---|:---|:---|
| **Router JSON 穩定性** | 100 次隨機請求 → 檢查 JSON 格式正確率 | ≥ 95% |
| **繁體中文理解** | 台灣口語測試集 (50 句) → Intent 準確率 | ≥ Qwen-4B 基準 |
| **Persona 生成品質** | 人工評分 (流暢度、角色一致性) | ≥ 4/5 分 |
| **推論速度** | 平均 token/s | ≥ Qwen-4B (或 latency < 1s) |
| **記憶體使用** | Peak VRAM/RAM | < 2 GB |

---

### 方案 B：**保守測試 (雙模型並行)**

在不移除 Qwen-4B 的情況下，新增 Bonsai-8B 作為實驗選項。

```yaml
# system_config.yaml
model:
  local:
    - name: "qwen-4b"        # 預設
      role: "router,persona"
    - name: "bonsai-8b"      # 實驗
      role: "router"         # 僅用於 Router，Persona 仍用 Qwen
```

```python
# pipeline.py
router_model = self.llm_manager.get_local("router")  # 可選 bonsai-8b
persona_model = self.llm_manager.get_local("persona") # 仍用 qwen-4b
```

**優勢：**
- ✅ 降低風險，保留回退方案
- ✅ 可 A/B Test 比較兩者 Intent 準確率
- ⚠️ 記憶體需求變成 2.5 GB + 1.15 GB = 3.65 GB (需評估硬體)

---

## 四、硬體需求變化

| 配置 | 現有 (Qwen-4B) | 方案 A (Bonsai-8B) | 方案 B (雙模型) |
|:---|:---|:---|:---|
| **VRAM** | 2.5 GB | 1.2 GB ⬇ **-52%** | 3.7 GB ⬆ |
| **RAM** | ~4 GB | ~3 GB | ~6 GB |
| **最低顯卡** | GTX 1650 (4GB) | GTX 1050 Ti (4GB) ⬇ | RTX 3060 (6GB+) ⬆ |
| **CPU 回退** | 可行但慢 | 可行且更快 ✅ | — |

**關鍵發現：**
- ✅ Bonsai-8B 讓 **4GB 顯卡** 有更多 VRAM 餘裕
- ✅ **無 GPU 環境** 下，1-bit 模型在 CPU 推論可能更快

---

## 五、實測檢查清單

### Phase 1: 基礎驗證 (1 天)
- [ ] 確認 Ollama 是否支援 Q1_0_g128 格式
  - 若不支援 → 測試 llama.cpp 直接推論
- [ ] 下載模型並成功載入
- [ ] 測試基本中文對話 (10 句)

### Phase 2: Router 功能測試 (2 天)
- [ ] 注入 `prompts_local.yaml` 的 Router System Prompt
- [ ] 測試 12 種 Intent 分類準確率 (vs Qwen-4B 基準)
- [ ] 測試 JSON 輸出穩定性 (100 次請求)
- [ ] 測試 Context Injection 是否仍有效

### Phase 3: Persona 功能測試 (1 天)
- [ ] 測試閒聊生成品質 (流暢度、角色一致性)
- [ ] 測試回覆長度控制 (<40 字)
- [ ] 測試台灣口語理解 (「尿尿」、「捷運」等)

### Phase 4: 性能對比 (1 天)
- [ ] 記錄平均 Token/s
- [ ] 記錄峰值記憶體使用
- [ ] 記錄 Router 平均 Latency (Stage 2)
- [ ] 對比能耗 (可選)

### Phase 5: 生產環境測試 (3 天)
- [ ] 整合進 Pipeline，跑完整測試集
- [ ] 模擬真實店面場景 (100 輪對話)
- [ ] 監控錯誤率、Fallback 次數

---

## 六、風險評估與建議

### 高風險項
| 風險 | 影響 | 緩解策略 | 狀態 |
|:---|:---|:---|:---:|
| **Ollama 不支援 Q1_0 格式** | 無法使用原方案 | 改用 llama.cpp (~170 行改動) | ❌ **已確認** |
| **繁體中文表現下降** | Intent 錯誤率上升 | 保留 Qwen-4B 回退機制 | ⚠️ 待測 |
| **JSON 輸出不穩定** | Router 失效 | Few-shot Prompt + JSON Schema 強化 | ⚠️ 待測 |
| **llama.cpp 整合問題** | 開發延遲/失敗 | 快速驗證 (1 天) → 決定是否繼續 | 🆕 新增 |

### 中風險項
| 風險 | 影響 | 緩解策略 |
|:---|:---|:---|
| **推論速度不如預期** | 體驗下降 (>1s) | 調整 batch size / context length |
| **Prompt 模板不相容** | 需重寫 Prompt | 預留 2 天調整時間 |

### 低風險項
- 記憶體使用降低 → **無風險，純收益**
- 參數量增加 → **可能帶來更好的 Router 準確度**

---

## 七、Ollama 不支援 Q1_0_g128 — 替代方案

### ❌ **已確認：Ollama 目前不支援 Q1_0_g128 格式**

需要選擇以下替代路徑之一：

---

### 方案 A：**改用 llama.cpp 直接推論** ⭐⭐⭐☆☆

**架構改動：**
```python
# 現有: local_llm_client.py (Ollama API)
class OllamaClient:
    async def generate(self, prompt, system_prompt):
        resp = requests.post("http://localhost:11434/api/generate", ...)

# 新增: llama_cpp_client.py
class LlamaCppClient:
    def __init__(self):
        from llama_cpp import Llama
        self.model = Llama(
            model_path="./bonsai-8b-q1_0_g128.gguf",
            n_ctx=2048,
            n_gpu_layers=0  # CPU 推論
        )
    
    async def generate(self, prompt, system_prompt):
        result = self.model.create_chat_completion(...)
        return result
```

**優勢：**
- ✅ 可直接使用 Bonsai-8B 原始 GGUF 檔
- ✅ llama.cpp 對 Q1_0 格式支援完整
- ✅ Python binding (`llama-cpp-python`) 成熟

**劣勢：**
- ⚠️ 需修改 `llm/manager.py` 和 `local_llm_client.py`
- ⚠️ 失去 Ollama 的模型管理便利性 (需手動下載 GGUF)
- ⚠️ API 介面不同，需統一包裝

**改動幅度：**
| 檔案 | 改動行數 | 難度 |
|:---|:---:|:---:|
| `llm/llama_cpp_client.py` | +150 (新增) | ⭐⭐⭐ |
| `llm/manager.py` | ~20 (切換邏輯) | ⭐⭐ |
| `requirements.txt` | +1 (`llama-cpp-python`) | ⭐ |
| **總計** | ~170 行 | ⭐⭐⭐☆☆ |

**估計時程：2-3 天**

---

### 方案 B：**等待官方轉換更高量化版本** ⭐⭐☆☆☆

等待 PrismML 釋出 **Q4_K_M** 或 **Q5_K_M** 版本 (Ollama 原生支援)。

**優勢：**
- ✅ 零程式碼改動 (仍用 Ollama)
- ✅ 可能獲得更好的精度 (Q4 > Q1)

**劣勢：**
- ❌ 失去 1-bit 的記憶體優勢 (Q4: ~2.5 GB, vs Q1: 1.15 GB)
- ❌ 時程不可控 (可能數週或數月)
- ❌ PrismML 可能不會釋出 (因為 1-bit 是賣點)

**不推薦理由**：時程不確定，且失去核心優勢。

---

### 方案 C：**自行轉換量化格式** ⭐☆☆☆☆

使用 `llama.cpp` 工具將 Q1_0_g128 → Q4_K_M。

```bash
# 理論流程
./quantize bonsai-8b-q1_0_g128.gguf bonsai-8b-q4_k_m.gguf Q4_K_M
ollama create bonsai-8b-q4 -f Modelfile
```

**劣勢：**
- ❌ Q1 → Q4 是「反向量化」，會導致模型大小膨脹回 ~2.5 GB
- ❌ 失去 1-bit 的全部優勢
- ❌ 技術上可能不可行 (llama.cpp 不支援 upcasting)

**不推薦理由**：喪失 Bonsai-8B 的核心價值。

---

### 方案 D：**暫不採用，等待 Ollama 支援** ⭐⭐⭐⭐☆

**追蹤進度：**
- Ollama GitHub Issues: 搜尋 "Q1_0" / "1-bit quantization"
- llama.cpp releases: Q1 支援 → Ollama 通常會跟進

**如果 Ollama 在 1-2 個月內支援 → 重新評估**

---

## 八、推薦方案總結

### 🎯 **短期（1 個月內需要）：方案 A (llama.cpp)**

**理由：**
1. 唯一能立即使用 Bonsai-8B 的方案
2. 改動可控 (~170 行，2-3 天)
3. llama.cpp 是成熟解決方案，風險低

**前置條件：**
1. 確認 `llama-cpp-python` 對 Q1_0_g128 的支援度
2. 準備 Qwen-4B 的測試基準數據

**決策流程：**
```
Day 1: 安裝 llama-cpp-python → 測試載入 Bonsai-8B GGUF
Day 2-3: 實作 LlamaCppClient → 整合進 Pipeline
Day 4-6: Phase 2-3 測試 (Router + Persona)
Day 7: 決策是否正式切換
```

---

### 🕐 **長期（可等待）：方案 D (等 Ollama)**

如果不急於切換，可持續追蹤：
- Ollama v0.6.0+ 是否會支援 Q1 格式
- 約每 2 週檢查一次 Ollama release notes

**一旦 Ollama 支援 → 移除 llama.cpp 客製化，回歸統一架構**

### 📊 **決策指標：**
| 指標 | 切換門檻 |
|:---|:---|
| Intent 準確率 | ≥ Qwen-4B - 3% |
| Router Latency | ≤ 1000ms |
| JSON 格式正確率 | ≥ 95% |
| 記憶體峰值 | ≤ 1.5 GB |

若所有指標達標 → **正式切換**
若任一指標未達標 → **保留 Qwen-4B，Bonsai 降級為實驗功能**

---

## 八、長期架構演進

如果 Bonsai-8B 測試成功，可進一步探索：

### 8.1 三層架構優化
```
Layer 1: Semantic Router (e5-small, <50ms) ✅ 保持不變
Layer 2: Bonsai-8B Router (1.15 GB, ~500ms?) ✅ 記憶體優化
Layer 3: Gemini Cloud RAG ✅ 保持不變
```

### 8.2 Edge 部署可能性
- Bonsai-8B 可能在 **Raspberry Pi 5** (8GB RAM) 上跑
- 開啟「桌邊小助理」硬體產品化可能性

### 8.3 多語言支援
- 如果 Bonsai-8B 多語言表現好 → 可擴展英/日語店面

---

## 九、最終結論與建議

### 📊 **評分卡 (Updated: Ollama 不支援)**

| 項目 | 原始評分 | 考量 llama.cpp 後 |
|:---|:---:|:---:|
| **技術可行性** | ⭐⭐⭐⭐☆ (4/5) | ⭐⭐⭐☆☆ (3/5) ⬇ |
| **改動複雜度** | ⭐⭐☆☆☆ (2/5，低) | ⭐⭐⭐☆☆ (3/5，中) ⬆ |
| **風險程度** | ⭐⭐⭐☆☆ (3/5，中) | ⭐⭐⭐⭐☆ (4/5，高) ⬆ |
| **潛在收益** | ⭐⭐⭐⭐⭐ (5/5，高) | ⭐⭐⭐⭐⭐ (5/5，高) ✅ |

### 🎯 **最終建議**

#### 情境 1：**急需降低記憶體使用 (< 1 個月)**
→ **採用方案 A (llama.cpp)**
- 投入 1 週開發 + 1 週測試
- 風險：需維護雙 LLM Backend (Ollama + llama.cpp)
- 收益：記憶體立即減半

#### 情境 2：**可等待 2-3 個月**
→ **採用方案 D (等 Ollama 支援)**
- 每 2 週追蹤 Ollama releases
- 零開發成本
- 收益：未來一行 config 即可切換

#### 情境 3：**現有架構已滿足需求**
→ **暫不採用 Bonsai-8B**
- Qwen-4B (2.5 GB) 已經夠輕量
- 等待更成熟的 1-bit 模型生態

### 🔍 **關鍵決策點**

執行以下快速驗證 (1 天)：
```bash
# 1. 測試 llama-cpp-python 能否載入 Bonsai-8B
pip install llama-cpp-python
python -c "from llama_cpp import Llama; m = Llama('bonsai-8b-q1_0_g128.gguf'); print(m)"

# 2. 測試基本中文推論
# 如果成功 → 繼續方案 A
# 如果失敗 → 放棄，等方案 D
```

**若測試通過 → 投入 2-3 天開發 LlamaCppClient**
**若測試失敗 → 暫停整合，追蹤 Ollama 進度**

---

*評估報告 v2.0 (Updated) — Project Akka*
*針對 PrismML Bonsai-8B (Q1_0_g128) 的整合分析*
*更新：Ollama 不支援 Q1_0_g128，提供 llama.cpp 替代方案*
