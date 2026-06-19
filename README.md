# Runelingual Transcripts 混合翻譯管線

<div align="center">

[English](README_en.md) | [中文](README.md)

</div>

## 概述

這是一套專為大規模遊戲文本翻譯設計的 AI 自動化管線。腳本目錄可任意放置，無需特定專案結構。

> ⚠️ **測試版公告**：本工具目前為測試階段，暫時只支援**簡體中文**翻譯。其他語言將在正式版中支援。

## 最近更新 (19/6/2026)，更新詳情請看 [Changelog](Changelog.md)
- 強化除錯訊息：API 錯誤、JSON 解析失敗、低翻譯率均顯示具體原因，不再靜默吞掉
- 新增智慧 JSON 提取：依序嘗試已知 key 名稱，未命中時自動搜尋巢狀結構中含 index+translation 的陣列
- 新增 API 適用性檢測：單一物件回傳時提示該 API 不適合翻譯任務，建議更換
- 新增低翻譯率 debug 記錄：翻譯率低於 25% 時將完整回傳內容儲存至 workplace/_debugmessage/
- 新增 JSON 修復機制：引入 json_repair 自動修復格式不完整的 JSON 回傳（缺少逗號/冒號等），減少重試次數
- 改善 API 兼容性：Nvidia、opencode、OpenRouter 等多種格式差異現已統一處理
- 新增依賴項：json-repair，執行 pip install json-repair 安裝

### 特色

- **極低成本**：搭配 DeepSeek V4 Flash，75000 條對話翻譯成本約 **2.39 美元**
- **術語強制準確**：透過腳本輔助，AI 對人名/地名/物品名等專有名詞的翻譯準確率達 **99% 以上**。而 Gemini 的 Gem 功能或 Qwen 的專案之類的功能即使配合優秀的提示詞，在缺少腳本的輔助下，仍不時會錯翻專有名詞。
- **互動式操作**：支援選擇工作表、條目範圍
- **非同步並行**：同時發送多個 API 請求，大幅縮短翻譯時間
- **中斷續傳**：翻譯過程中若因網路問題或人手中斷，重新執行腳本即可從中斷處繼續，無需從頭開始
- **自動審查**：三層檢查（術語 / 佔位符 / 未翻譯），產出彩色標示的審查報告
- **多 API 支援**：支援同時使用多個 API Key（主/副分類），輪流分配任務，自動處理 429 限流（冷卻/永久停用），最大化翻譯吞吐量

### 檔案結構

| 檔案 | 用途                              |
|---|---------------------------------|
| `batch_translate.py` | **主控腳本** — 互動式操作入口              |
|`glossary.py` | 讀取術語庫 Excel 或自動萃取術語庫 + 輸出審查檔|
| `tm_matcher.py` | 模板化比對（**尚未啟用**，將在正式版加入）         |
| `llm_translator.py` | **AI 批次翻譯核心**，非同步並行調用，含智慧 JSON 提取與 json_repair 修復 |
| `enforcer.py` | **三層強制檢查**（術語/佔位符/未翻譯），自動修正+產出彩色審查報告 |
| `api_config.py` | 多 API 配置解析，支援主/副分類、類別預設並發、個別覆蓋 |
| `.env` | API 設定檔，支援多 API 編號格式及舊版單一 API 格式 |
| `.env.example` | 設定範本                            |
| `workplace/` | **工作目錄**（腳本自動建立），所有輸入輸出統一存放於此  |

### 四階段流程

```
batch_translate.py → 依序執行：
① glossary.py      載入術語庫
② tm_matcher.py    模板參數比對 ⚠️ 尚未啟用，將在正式版加入
③ llm_translator.py AI 批次翻譯（非同步並行）
④ enforcer.py      三層強制檢查（術語/佔位符/未翻譯）+ 彩色審查報告
```

---

## 安裝

```bash
pip install openpyxl pandas openai python-dotenv json-repair
```

## 設定

### 1. 申請 API Key

本工具支援任何 **OpenAI 相容 API**。推薦的選項：

| 平台                                                | 推薦模型                            | 成本 |
|---------------------------------------------------|---------------------------------|----|
| [OpenRouter](https://openrouter.ai/)              | `deepseek/deepseek-v4-flash`    | 極低 |
| [DeepSeek 官方](https://platform.deepseek.com/)     | `deepseek-v4-flash`                 | 極低 |
| [Nvidia (免費API)](https://build.nvidia.com/)       | `deepseek-ai/deepseek-v4-flash` | 免費 |
| [Opencode Zen (免費API)](https://opencode.ai/zen/) | `deepseek-v4-flash-free` | 免費 |

### 2. 建立 `.env` 檔案

複製 `.env.example` 為 `.env`，填入你的設定。支援兩種格式，以下為範本：

#### 多 API 格式（推薦）

```env
# 主 API（付費，預設並發=10）
API1_TYPE=main
API1_PARALLEL_LIMIT=x (如果你想設置獨立並發數就增加這個參數，填入數字)
API1_MODEL_PROVIDER=openrouter
API1_MODEL=deepseek/deepseek-v4-flash
API1_API_KEY=sk-your_api_key_here
API1_BASE_URL=https://openrouter.ai/api/v1

# 副 API（免費，預設並發=1）
API2_TYPE=fallback
API2_PARALLEL_LIMIT=x (如果你想設置獨立並發數就增加這個參數，填入數字)
API2_MODEL_PROVIDER=nvidia
API2_MODEL=deepseek-ai/deepseek-v4-flash
API2_API_KEY=nvapi-your_free_key_here
API2_BASE_URL=https://integrate.api.nvidia.com/v1
```
舊版單一 API 格式（向後相容）
```env
API_KEY=sk-your_api_key_here
MODEL_PROVIDER=openrouter
MODEL=deepseek/deepseek-v4-flash
BASE_URL=https://openrouter.ai/api/v1
```
> 兩種格式可同時存在——若偵測到 `API1_` 設定，優先使用多 API 格式。每個 API 可選填 `APIx_PARALLEL_LIMIT` 覆蓋類別預設值。主 API 預設並發=10，副 API 預設並發=1。

---

## 使用方法

將翻譯目標 Excel 和術語庫（可選）放入 `workplace/` 目錄，然後執行主控腳本。

### 執行主控腳本

```bash
cd <腳本所在目錄>
python batch_translate.py
```
或直接運行 batch_translate.py。

### 互動步驟

```
Step 1：選擇目標 Excel    → 從 workplace/ 下列出所有 .xlsx 檔案
Step 2：選擇術語庫        → 可選 Excel 術語庫、自動從目標 Excel 萃取、或跳過（只有 ADD_LIST 硬編碼術語）
Step 3：選擇工作表        → 單選或多選
Step 4：選擇翻譯範圍      → 全部未翻譯 / 前 N 條測試 / 指定行數
Step 5：確認執行          → 顯示摘要後按 Y 確認
```

### 執行後產出

所有輸出檔案統一放在 `workplace/` 目錄下：

| 檔案 | 說明 |
|------|------|
| `{來源檔名}_translated_output.xlsx` | **翻譯完成檔案**，位於 `workplace/` |
| `review_report.xlsx` | **審查報告**（需人工確認的條目），位於 `workplace/` |
| `_checkpoint/` | **中斷續傳暫存目錄**，位於 `workplace/`（翻譯完成後自動刪除） |

---

### 中斷續傳

若翻譯過程中因網路斷線、API 錯誤、或人手中斷（Ctrl+C），腳本支援從中斷處繼續：

**續傳流程：**
1. 重新執行 `batch_translate.py`
2. 腳本會自動掃描 `workplace/_checkpoint/session.json`，偵測未完成的進度
3. 顯示上次的翻譯設定摘要（Excel、工作表、進度）
4. 詢問是否繼續上次的翻譯：

```
============================================================
  偵測到未完成的翻譯進度
============================================================
  Excel: transcript_zh.xlsx
  工作表: dialogue_experimental
  進度: 504/1000 條
  術語庫: 术语库.xlsx
============================================================

是否繼續上次的翻譯？(Y/n):
```

5. 選擇 `Y` → 自動載入術語庫設定、還原已翻譯條目，從中斷處繼續
6. 選擇 `n` → 清除舊暫存，進入全新翻譯流程

> ⚠️ **注意**：中斷續傳功能**能確保保存絕大部分已翻譯進度，但並非 100%**。極端情況下（如突然關機），最近 1-2 批已完成但尚未寫入暫存的翻譯可能無法還原。
---

## 術語庫與自訂詞典

### Excel 術語庫

直接使用與翻譯目標相同格式的 Excel，欄位順序：
`english / translation / category / sub_category / source / notes / wiki_url`

只取 `translation` 欄位有值的行作為術語條目。

### 內建 ADD_LIST

可在 `glossary.py` 中直接寫入硬編碼術語（衝突時優先於 Excel）：

```python
ADD_LIST: dict[str, str] = {
    "Old School RuneScape": "Old School RuneScape",
    "OSRS": "OSRS",
    "RuneLite": "RuneLite",
    "RuneLingual": "RuneLingual",
    # 可自行新增，例如：
    # "Saradomin": "薩拉多明",
}
```

### 內建 IGNORE_LIST

部分容易誤譯的普通名詞已在 `glossary.py` 的 `IGNORE_LIST` 中預先排除，避免 AI 錯誤地將它們當作術語處理。

**範例（位於 `glossary.py` 中）：**

```python
IGNORE_LIST: set[str] = {
    "Toolkit", "Vial", "Bones", "Book", "Man", "Run", "Ash",
    "Red", "Will", "Art", "Smith", "Gem", "Woman", "Tree",
    "Shadow", "Rock", "Letter", "Jug", "Egg",
    # ... 完整清單請見 glossary.py
}
```

**自行新增指引：**
- 任何你不想被當作術語檢查的普通英文單詞都可以加入
- 加入後會同時匹配**單數/複數/大小寫**形態（例如加入 `Egg` 會自動忽略 `Eggs`、`EGGS`）
- 已存在於 Excel 術語庫中的同名條目也會被一併忽略

---

## 模板比對（tm_matcher）

⚠️ **此功能目前尚未啟用**（`TEMPLATES` 列表為空），所有條目目前全部交由 AI 翻譯。

模板比對功能將在**正式版**中加入。屆時可自訂正則模板讓腳本自動填入翻譯（如 `"Talk to (.+?)\."` → `"与{0}对话。"`），減少 API 調用次數。有興趣的使用者可以參考 `tm_matcher.py` 中的說明提前了解語法。

---

## 常數設定

以下常數位於 `api_config.py` 和 `llm_translator.py`，**除非你很清楚自己在做什麼，否則不建議改動**：

| 常數 | 預設值 | 說明                           |
|------|--------|------------------------------|
| `BATCH_SIZE_LIMIT` | 100 | 每批 API 請求的最大條數 (llm_translator.py)            |
| `MAIN_DEFAULT_LIMIT` | 10 | 主 API 預設並發數（api_config.py）   |
| `FALLBACK_DEFAULT_LIMIT` | 1 | 副 API 預設並發數（api_config.py）   |
| `REQUEST_INTERVAL` | 1 | 同一 API 請求間隔秒數（api_config.py） |

> 調整並發數時請注意：可在 `.env` 中為個別 API 設 `APIx_PARALLEL_LIMIT`，或修改 `api_config.py` 中的類別預設值。數值過高可能觸發 API 端點的 Rate Limit。預設主 API=10、副 API=1 經過實測為最佳平衡點。

---

## 效能參考

### 實測數據（DeepSeek V4 Flash，黃昏時段）

| 翻譯數量 | 平均成本          | 耗時（三次測試） |
|---------|---------------|----------------|
| 500 條 | 0.01-0.02 USD | 329s, 467s, 353s |
| 2000 條 | 0.06-0.07 USD | 801s, 746s, 696s |
| 5000 條 | 0.14 USD      | 2084s, 1465s, 2170s |
|75000 條   | 2.39 USD      | 8hours     |

### 實測數據（付費 vs 免費 API 速度對比）

以付費 API DeepSeek V4 Flash 為基準（1x），以下為免費 API 翻譯單一批次（100 條）所需的相對時間。如有更多實測數據，歡迎提供。

| API 來源 | Nvidia（DS v4 flash） |Opencode（DS v4 flash） | Openrouter（gpt-oss-120b） |
|----------|:-------------------:|:--------------------:|:------------------------:|
| 相對耗時 |       1-1.5x        |        1-1.5x        |         1.5-2x           |

> 💡 **使用建議**：免費 API 速度較慢，僅建議在大規模翻譯（如 2000 條以上）時搭配付費 API 使用。由於多 API 輪流分配機制會自動將任務分配給所有可用 API，少量翻譯（如 500 條）中免費 API 的比重過高反而會拖慢總體進度。

### 時段影響與波動（推測）

- **白天比深夜慢 ~20%**：OpenRouter 聚合平台在亞洲/歐美重疊時段使用者較多，API 端點回應時間增加。建議大規模翻譯在深夜離峰時段執行。
- **同批次波動約 ±30%**：OpenRouter 內部每次請求被路由到的上游供應商或 GPU 節點不同，加上批次內句子長短差異、重試次數不同，導致相同數量的翻譯耗時有隨機波動。

---

## 疑難排解

### API 相關

**Q：執行後出現 `ImportError: No module named 'openai'`**
<br>A：尚未安裝依賴，執行 `pip install openai pandas openpyxl python-dotenv json-repair`。

**Q：出現 `ValueError: 请设定 API_KEY 环境变量或在 .env 档案中设定`**
<br>A：忘記建立 `.env` 檔案。複製 `.env.example` 為 `.env`，填入你的 API Key。

**Q：API 請求一直失敗或超時**
<br>A：檢查 `.env` 中的 `BASE_URL` 和 `MODEL` 是否正確。如果是 OpenRouter，確認帳戶餘額是否足夠。也可嘗試調低主/副 API 的並發數來降低 Rate Limit 風險。

**Q：翻譯速度比預期慢很多**
<br>A：先確認時段——白天比深夜慢 ~20% 是正常現象。若深夜仍偏慢，可檢查網路連線或嘗試更換 API 端點。

### 術語相關

**Q：審查報告中有大量我沒聽過的術語 issue**
<br>A：可能是普通名詞被誤當作術語。檢查你的 Excel 術語庫是否有不該出現的條目，或將該單詞加入 `glossary.py` 的 `IGNORE_LIST`。

**Q：我加入了術語但 AI 沒有使用**
<br>A：檢查術語庫 Excel 中 `translation` 欄位是否有值（只有該欄位非空的列才會被載入）。若來自 `ADD_LIST`，確認拼寫和大小寫是否完全一致。

**Q：`"Eggs"` 明明在 IGNORE_LIST 但還是有 issue**
<br>A：確認你的 `glossary.py` 使用的是最新版本，`IGNORE_LIST` 已改為歸一化匹配（加入 `Egg` 即可過濾 `Eggs`、`EGGS` 等形態）。若你同時在 Excel 術語庫中有 `"Eggs"` 條目，也需要一併從 Excel 中移除。

### 檔案相關

**Q：翻譯輸出沒有產生任何檔案**
<br>A：檢查目標 Excel 中是否已有翻譯（`translation` 欄位非空）。若全部已翻譯，腳本會跳過該工作表。可嘗試選擇「全部未翻譯條目」以外的範圍選項。

**Q：輸出的 `_translated_output.xlsx` 打不開**
<br>A：確認該檔案未被其他程式（如 Excel）佔用。若仍無法開啟，可能是翻譯過程中發生錯誤，檢查終端機輸出是否有錯誤訊息。

**Q：`_checkpoint/` 目錄沒有被自動刪除**
<br>A：腳本正常完成時會自動刪除。若腳本被強制中斷，`_checkpoint/` 會保留下來，方便下次續傳。手動刪除不會影響功能。

### 中斷續傳相關

**Q：續傳時偵測不到進度**
<br>A：續傳依賴 `workplace/_checkpoint/session.json`。如果你手動搬移檔案，需要將整個 `_checkpoint/` 目錄一併移動。如果手動刪除了 `session.json`，續傳功能將無法使用。

**Q：續傳後部分翻譯遺失**
<br>A：如「中斷續傳」章節所述，極端情況下（如突然關機）最近 1-2 批翻譯可能無法保存。這是正常現象，重新翻譯遺失的部分即可。

**Q：續傳時目標 Excel 已修改，可以繼續嗎？**
<br>A：續傳依賴記錄的選取索引（`selected_indices`）。如果目標 Excel 內容或條目順序已變更，索引可能對不上，建議選擇「否」開始全新翻譯。

### 除錯相關

**Q：出現 `[APIx] ⚠️ 低翻譯率 1.1%（1/94），已儲存 debug 訊息`**
<br>A：該 API 的翻譯能力不足，94 條中只成功翻譯了 1 條。檢查 `workplace/_debugmessage/` 目錄下的 debug 檔案檢視完整回傳內容，建議更換其他模型。

**Q：出現 `[APIx] ⚠️ API 回傳單一物件而非陣列`**
<br>A：該 API 不支援批次回傳多條翻譯，只回了單一條目。如果多次顯示此訊息，建議從 `.env` 移除或更換模型。

**Q：出現 `JSON 修復成功`**
<br>A：模型回傳的 JSON 格式有微小瑕疵（如缺少逗號或冒號），`json_repair` 已自動修復，不影響翻譯結果。

---

## 授權條款 (License)

本項目採用 GPL v3 授權條款。詳細內容請參閱 [LICENSE](LICENSE) 檔案。

Copyright (c) 2026 lck3141592654