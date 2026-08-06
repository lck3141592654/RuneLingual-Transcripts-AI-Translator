# Changelog

## 18/6/2026 v0.1 -> v0.2

### 中文
- 新增多 API Key 並行作業，自動輪流分配任務並處理 429 限流
- 新增斷點續傳，翻譯中斷後重新執行腳本即可從中斷處繼續
- 新增自動萃取術語庫，從目標 Excel 的 name/manual 工作表自動篩選，無需額外準備
- 統一 workplace/ 工作目錄，所有輸入輸出集中管理，簡化操作流程
- 重譯功能擴充為三層檢查：術語比對、佔位符誤翻檢測、翻譯失敗檢測
- 修正術語誤報：同一句內含重疊字串時（如「Lord Hosidius」與「Hosidius」），長術語翻譯正確即不再對短術語誤報
- 強化互動介面：顯示各批次所用 API、細化重譯統計數據、補全各階段時間戳
- 擴充內建術語庫（ADD_LIST）與排除清單（IGNORE_LIST）條目

### English
- Added multi-API parallel support with round-robin task distribution and automatic 429 rate-limit handling
- Added checkpoint resume — re-run the script to continue from where it left off after interruption
- Added auto-extract glossary from the target Excel's name and manual sheets, no separate file required
- Unified workplace/ directory for all inputs and outputs, simplifying the workflow
- Extended retranslation to three-layer checks: terminology, placeholder corruption, and untranslated entries
- Fixed false positives in review report: when overlapping terms exist (e.g. "Lord Hosidius" vs "Hosidius"), correct longer-term translation no longer triggers a false alarm on the shorter term
- Enhanced interactive UI: per-batch API indicators, detailed retranslation stats, and comprehensive stage timestamps
- Expanded built-in term list (ADD_LIST) and ignore list (IGNORE_LIST)

## 19/6/2026 v0.2 -> v0.2.1

### 中文
- 強化除錯訊息：API 錯誤、JSON 解析失敗、低翻譯率均顯示具體原因，不再靜默吞掉
- 新增智慧 JSON 提取：依序嘗試已知 key 名稱，未命中時自動搜尋巢狀結構中含 index+translation 的陣列
- 新增 API 適用性檢測：單一物件回傳時提示該 API 不適合翻譯任務，建議更換
- 新增低翻譯率 debug 記錄：翻譯率低於 25% 時將完整回傳內容儲存至 workplace/_debugmessage/，可直接在該目錄檢視
- 新增 JSON 修復機制：引入 json_repair 自動修復格式不完整的 JSON 回傳（缺少逗號/冒號等），減少重試次數
- 改善 API 兼容性：Nvidia、opencode、OpenRouter 等多種格式差異現已統一處理
- 新增依賴項：json-repair，執行 pip install json-repair 安裝

### English
- Enhanced debug output: API errors, JSON parse failures, and low translation rates now show detailed diagnostics instead of being silently ignored
- Added smart JSON extraction: tries known key names first, then auto-searches nested structures for arrays containing index+translation fields
- Added API compatibility detection: alerts when an API returns single objects instead of arrays, recommending replacement
- Added low-rate debug logging: saves full API response to workplace/_debugmessage/ when translation rate is below 25% for direct inspection
- Added JSON repair: uses json_repair to fix malformed JSON responses (missing commas/colons, etc.), reducing retries
- Improved API compatibility: unified handling of format differences across Nvidia, opencode, OpenRouter, and other providers
- New dependency: json-repair — run pip install json-repair to install

## 20/6/2026 v0.2.1 -> v0.2.2

### 中文
- 修正多工作表翻譯：原始設計已支援，但存在多項 BUG（範圍選擇/輸出/續傳），現已全面修復
  - 一次性選取所有工作表，逐表自訂翻譯範圍，無需逐表重複確認
  - 全部完成後才輸出 _translated_output.xlsx 與 review_report.xlsx
- 斷點續傳全面升級支援多工作表：各工作表擁有獨立檢查點目錄（_checkpoint/{sheet_name}/），中斷後續傳時自動接續未完成的工作表，保留已完成的工作表資料
- 新增重譯中斷續傳：重譯過程（術語強制後處理）若中斷，重新執行後會從中斷的輪次繼續，不浪費 API 調用
- save_session() 改為原子寫入（.tmp → rename），避免中斷導致 session.json 損毀
- 擴充內建術語庫（ADD_LIST）與排除清單（IGNORE_LIST）條目

### English
- Fixed multi-sheet translation: originally designed but had multiple bugs (range selection, output, resume), now fully resolved
  - Select all sheets at once, customize range per sheet, confirm once
  - Output _translated_output.xlsx and review_report.xlsx after all sheets complete
- Upgraded checkpoint resume for multi-sheet: each sheet gets its own checkpoint directory (_checkpoint/{sheet_name}/), resuming automatically continues with incomplete sheets while preserving completed ones
- Added enforce checkpoint resume: if the retranslation phase (enforce) is interrupted, re-running will continue from the interrupted round without wasting API calls
- save_session() now uses atomic write (.tmp → rename) to prevent session.json corruption on interrupt
- Expanded built-in term list (ADD_LIST) and ignore list (IGNORE_LIST)

## 24/6/2026 v0.2.2 -> v0.3

### 中文
- 新增校對管線（proofreader.py + batch_proofread.py）：
  - 三階段流程：LLM 雙輪評估（Phase 2）→ LLM 潤色（Phase 3）→ 重譯保護（Phase 4a）+ 模板校正（Phase 4b）
  - Phase 2 混合 R1+R2 批次池：R1 和 R2 的所有批次混合在一個 worker pool 中處理，而非順序執行兩輪
  - 雙輪交叉驗證：僅有兩次皆為 {沒問題, 輕度} 的任意組合才跳過，其餘列為第二類問題條目
  - 75% 完成率閾值：所有 API 回傳（含正常路徑與 json_repair 修復路徑）皆檢查，低於 75% 即重試，最高優先級
  - 互動式 CLI，支援續傳、debug 訊息檢視、備份與雙報告輸出（proofread_report.xlsx + review_report_proofread.xlsx）
  - 獨立 checkpoint 目錄（_proofread_checkpoint/），不與主翻譯干擾
- ⚠️ **已知限制**：校對管線目前只支援**單工作表**處理，不支援多工作表。
- 移除 response_format：
  - `_translate_batch()`（llm_translator.py）移除 `response_format={"type": "json_object"}`
  - `_evaluate_batch()` 和 `_polish_batch()`（proofreader.py）移除 `response_format={"type": "json_object"}`
  - 所有提示詞改為直接要求「原始 JSON 阵列（不要使用 ```json 代码块包裹）」
  - 保留智慧 JSON 提取（方法一/二）和 json_repair 修復作為後備保障
- 共用 `run_worker_pool()` 提取至 llm_translator.py，供翻譯與校對共用
- 擴充內建術語庫（ADD_LIST）與排除清單（IGNORE_LIST）條目

### English
- Added proofreading pipeline (proofreader.py + batch_proofread.py):
  - Three-phase flow: LLM Dual-round Evaluation (Phase 2) → LLM Polish (Phase 3) → Retry Protect (Phase 4a) + Template Correction (Phase 4b)
  - Phase 2 mixed R1+R2 batch pool: all R1 and R2 batches processed in one worker pool instead of sequential passes
  - Dual-round cross-validation: skips only when both rounds are {acceptable, mild} in any combination; all others flagged as category 2
  - 75% completion rate threshold: checked on all API returns (normal path + json_repair path), triggers retry below 75%, highest priority
  - Interactive CLI with resume, debug message review, backup, and dual report output (proofread_report.xlsx + review_report_proofread.xlsx)
  - Isolated checkpoint directory (_proofread_checkpoint/) independent from main translation
- ⚠️ **Known limitation**: The proofreading pipeline currently only supports **single worksheet** processing. Multi-sheet support is not yet implemented.
- Removed response_format:
  - `_translate_batch()` (llm_translator.py) removed `response_format={"type": "json_object"}`
  - `_evaluate_batch()` and `_polish_batch()` (proofreader.py) removed `response_format={"type": "json_object"}`
  - All prompts now directly require "raw JSON array (do not use ```json code blocks)"
  - Retained smart JSON extraction (method 1/2) and json_repair as fallbacks
- Extracted shared `run_worker_pool()` to llm_translator.py, used by both translation and proofreading
- Expanded built-in term list (ADD_LIST) and ignore list (IGNORE_LIST)


## 25/6/2026 v0.3 -> v0.3.1

### 中文
- **新增空格檢查**：`scan_issues()` 加入第四層檢查，檢測六種空格問題（連續多個空格、中文字間空格、空格+中文/英文標點、中文/英文標點+空格），審查報告以綠色標示
- **新增腳本預處理機制**：在 LLM 重譯前三輪皆先執行機械式修正，減少 API 調用
  - 單佔位符修正：原文僅含一個 `[]` 時，直接用原文內容覆蓋譯文的 `[]` 內容
  - 空格修正：自動清除六種不合格空格，保留正常合理空格
- **修正純佔位符誤判**：原文去除 `[]` 後僅剩空白或標點符號時，不再視為未翻譯

### English
- **New space check**: Added a fourth layer to `scan_issues()` detecting six types of spacing issues (consecutive spaces, spaces between Chinese characters, space before/after Chinese/English punctuation). Displayed in green in review reports.
- **New script preprocessing**: Applies mechanical fixes before each of the 3 LLM retranslation rounds, reducing API calls
  - Single placeholder fix: when the source has exactly one `[]`, overwrites the translation's `[]` content with the source's
  - Space fix: automatically removes six types of abnormal spaces while preserving legitimate ones
- **Fixed false positive for placeholder-only entries**: Entries where removing all `[]` leaves only whitespace or punctuation are no longer flagged as untranslated


## 7/8/2026 v0.3.1 -> v0.3.2

### 中文
- 新增多工作表並行（翻譯與校對皆支援）：所有工作表在同一階段內並行處理，階段間同步（全部表完成該階段才進下一階段）
- 新增共享批次池（shared_pool.py）：整個執行共用一份 API 配置、並發與 429 冷卻狀態；每個 API 依 parallel_limit 建立多個 worker，批次真正並行處理
- 新增 API_TIMEOUT 統一逾時常數（api_config.py，預設 3600 秒）：主翻譯、校對各階段與重譯共用
- 新增 PERMANENT_DISABLE_AFTER 常數（api_config.py，預設 2）：可調整 429 停用次數
- 重譯逾時修正：固定 60 秒逾時造成慢速 API 誤判 Request timed out.，改為統一逾時
- 純空格問題不再送 LLM：由腳本機械式處理，節省 API 調用
- 術語正則快取：每個術語只編譯一次，大表掃描大幅加速
- 審查報告補齊四色標記：合併報告補上空格問題綠色標記
- checkpoint 全面原子寫入：新增 atomic_write_text helper（.tmp → fsync → rename），session、progress、part、enforce、階段標記、模板、P2、P3 統一使用
- 移除大量死代碼：run_worker_pool、translate_all、enforce 同步包裝與未使用的 import、函數、變數

### English
- Added multi-worksheet parallelism for both translation and proofreading: all sheets run concurrently within each phase, with a phase barrier (all sheets must finish a phase before the next starts)
- Added a shared batch pool (shared_pool.py): one set of API configs, concurrency and 429 state for the whole run; each API spawns parallel_limit workers so batches truly run concurrently
- Added unified API_TIMEOUT constant (api_config.py, default 3600s) shared by translation, proofreading phases and retranslation
- Added PERMANENT_DISABLE_AFTER constant (api_config.py, default 2) to tune the 429 disable threshold
- Fixed retranslation timeout: the fixed 60s timeout caused spurious Request timed out. on slow APIs; now uses the unified timeout
- Space-only issues are no longer sent to the LLM; handled by script preprocessing
- Cached compiled glossary regexes so each term is compiled only once, speeding up large-sheet scanning
- Completed the four-color review report: the merged report now colors space issues green
- Unified atomic checkpoint writes via atomic_write_text (.tmp -> fsync -> rename) for session/progress/part/enforce/phase markers/template/P2/P3 files
- Removed dead code: run_worker_pool, translate_all, enforce sync wrapper and unused imports/functions/variables
