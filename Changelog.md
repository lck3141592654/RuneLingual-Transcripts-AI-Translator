# Changelog

## 18/6/2026 更新 / 18/6/2026 Update

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
- Fixed false positives in review report: when overlapping terms exist (e.g. “Lord Hosidius” vs “Hosidius”), correct longer-term translation no longer triggers a false alarm on the shorter term
- Enhanced interactive UI: per-batch API indicators, detailed retranslation stats, and comprehensive stage timestamps
- Expanded built-in term list (ADD_LIST) and ignore list (IGNORE_LIST)

## 19/6/2026 更新 / 19/6/2026 Update

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
