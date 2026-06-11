# Runelingual Transcripts 混合翻譯管線

<div align="center">

[English](README_en.md) | [中文](README.md)

</div>

## 概述

這是一套專為大規模遊戲文本翻譯設計的 AI 自動化管線，位於 `updater/experimental/` 目錄下。

> ⚠️ **測試版公告**：本工具目前為測試階段，暫時只支援**簡體中文**翻譯。繁體中文及其他語言將在正式版中支援。

### 特色

- **極低成本**：搭配 DeepSeek V4 Flash，75000 條對話翻譯成本約 **2.1 美元**
- **術語強制準確**：透過腳本輔助，AI 對人名/地名/物品名等專有名詞的翻譯準確率達 **99% 以上**。而Gemini的Gem功能或Qwen的專案之類的功能即使配合優秀的提示詞，在缺少腳本的輔助下，錯翻專有名詞的機率也不低。
- **互動式操作**：支援選擇語言、工作表、條目範圍
- **非同步並行**：同時發送多個 API 請求，大幅縮短翻譯時間
- **自動審查**：自動檢查術語使用情況，產出審查報告

### 檔案結構

| 檔案 | 用途                              |
|---|---------------------------------|
| `batch_translate.py` | **主控腳本** — 互動式操作入口              |
| `glossary.py` | 讀取術語庫 Excel 並輸出字典               |
| `tm_matcher.py` | 模板化比對（**尚未啟用**，將在正式版加入）         |
| `llm_translator.py` | **AI 批次翻譯核心**，非同步並行調用           |
| `enforcer.py` | **術語強制檢查**，自動修正+產出審查報告          |
| `.env` | 你的 API 設定，你需自行複製.env.example並刪去".example" |
| `.env.example` | 設定範本                            |

### 四階段流程

```
batch_translate.py → 依序執行：
① glossary.py      載入術語庫
② tm_matcher.py    模板參數比對 ⚠️ 尚未啟用，將在正式版加入
③ llm_translator.py AI 批次翻譯（非同步並行）
④ enforcer.py      術語強制檢查 + 審查報告
```

---

## 安裝

```bash
pip install openpyxl pandas openai python-dotenv
```

## 設定

### 1. 申請 API Key

本工具支援任何 **OpenAI 相容 API**。推薦的選項：

| 平台 | 推薦模型 | 成本 |
|------|---------|------|
| [OpenRouter](https://openrouter.ai/) | `deepseek/deepseek-v4-flash` | 極低 |
| DeepSeek 官方 | `deepseek-chat` | 極低 |
| OpenAI | `gpt-4o-mini` | 較高 |

### 2. 建立 `.env` 檔案

複製 `.env.example` 為 `.env`，填入你的設定：

```env
API_KEY=sk-your_api_key_here
MODEL_PROVIDER=openrouter
MODEL=deepseek/deepseek-v4-flash
BASE_URL=https://openrouter.ai/api/v1
```

---

## 使用方法 (先將experimental文件夾放入Runelingual-Transcripts\updater內)

### 執行主控腳本

```bash
cd updater/experimental
python batch_translate.py
```

### 互動步驟

```
Step 1：選擇語言          → 從 draft/ 下的目錄名稱選擇（如 zh、fr）
Step 2：選擇目標 Excel    → 選擇要翻譯的檔案
Step 3：選擇術語庫        → 可選 Excel 術語庫或僅用內建詞典
Step 4：選擇工作表        → 單選或多選
Step 5：選擇翻譯範圍      → 全部未翻譯 / 前 N 條測試 / 指定行數
Step 6：確認執行          → 顯示摘要後按 Y 確認
```

### 執行後產出

| 檔案 | 說明 |
|------|------|
| `{來源檔名}_translated_output.xlsx` | **翻譯完成檔案** |
| `review_report.xlsx` | **審查報告**（需人工確認的條目） |
| `progress.json` | 進度暫存（翻譯完成後自動刪除） |

---

## 輸出檔案命名規則

假設你選擇翻譯 `transcript_zh.xlsx`，輸出為 `transcript_zh_translated_output.xlsx`。

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

以下常數位於 `llm_translator.py` 頂部，**除非你很清楚自己在做什麼，否則不建議改動**：

| 常數 | 預設值 | 說明 |
|------|--------|------|
| `BATCH_SIZE_LIMIT` | 100 | 每批 API 請求的最大條數 |
| `PARALLEL_LIMIT` | 10 | 同時進行的 API 請求數上限 |
| `REQUEST_INTERVAL` | 1 | 每批請求啟動前的間隔秒數 |

> 調整 `PARALLEL_LIMIT` 時請注意：數值過高可能觸發 API 端點的 Rate Limit，反而拖慢整體速度；數值過低則無法充分利用並行優勢。預設值 10 經過實測為最佳平衡點。

---

## 效能參考

### 實測數據（DeepSeek V4 Flash，黃昏時段）

| 翻譯數量 | 平均成本 | 耗時（三次測試） |
|---------|---------|----------------|
| 500 條 | 0.01-0.02 USD | 329s, 467s, 353s |
| 2000 條 | 0.06-0.07 USD | 801s, 746s, 696s |
| 5000 條 | 0.14 USD | 2084s, 1465s, 2170s |

### 成本分析

翻譯成本與估算偏差不大，以 5000 條 0.14 美元推算，**75000 條約 2.1 美元**。

### 時段影響與波動 (推測)

- **白天比深夜慢 50-70%**：OpenRouter 聚合平台在亞洲/歐美重疊時段使用者較多，API 回應時間顯著增加。建議大規模翻譯在深夜離峰時段執行。
- **同批次波動約 ±20%**：OpenRouter 內部每次請求被路由到的上游 provider 或 GPU 節點不同，加上批次內句子長短差異，導致相同數量的翻譯耗時有隨機波動。

---

## 疑難排解

### API 相關

**Q：執行後出現 `ImportError: No module named 'openai'`**
<br>A：尚未安裝依賴，執行 `pip install openai pandas openpyxl python-dotenv`。

**Q：出現 `ValueError: 请设定 API_KEY 环境变量或在 .env 档案中设定`**
<br>A：忘記建立 `.env` 檔案。複製 `.env.example` 為 `.env`，填入你的 API Key。

**Q：API 請求一直失敗或超時**
<br>：檢查 `.env` 中的 `BASE_URL` 和 `MODEL` 是否正確。如果是 OpenRouter，確認帳戶餘額是否足夠。也可嘗試將 `PARALLEL_LIMIT` 調低至 5 來降低 Rate Limit 風險。

**Q：翻譯速度比預期慢很多**
<br>A：先確認時段——白天比深夜慢 50-70% 是正常現象。若深夜仍偏慢，可檢查網路連線或嘗試更換 API 端點。

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

**Q：`progress.json` 沒有被自動刪除**
<br>A：腳本正常完成時會自動刪除。若腳本被強制中斷，`progress.json` 會保留下來，方便下次續傳。手動刪除不會影響功能。

## 授權條款 (License)

本項目採用 GPL v3 授權條款。詳細內容請參閱 [LICENSE](LICENSE) 檔案。

Copyright (c) 2026 lck3141592654
