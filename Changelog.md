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
