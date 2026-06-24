# Runelingual Transcripts Hybrid Translation Pipeline

<div align="center">

[English](README_en.md) | [中文](README.md)

</div>

## Overview

An AI-powered automated pipeline designed for large-scale game text translation. Scripts can be placed anywhere — no specific project structure required.

> ⚠️ **Beta Notice**: This tool is currently in beta and only supports **Simplified Chinese** translation. Other languages will be supported in the official release.

## Latest Update on 24/6/2026, see [Changelog](Changelog.md) for details
- **New proofreading pipeline**: Added `proofreader.py` + `batch_proofread.py` with LLM dual-round evaluation, polishing, and retranslation protection
- **Removed response_format**: All API calls (translation and proofreading) now use prompt to directly request raw JSON arrays for better compatibility
- Shared `run_worker_pool()` and `get_relevant_glossary()` extracted to `llm_translator.py`, used by both translation and proofreading
- Expanded built-in term list (ADD_LIST) and ignore list (IGNORE_LIST)

### Features

- **Ultra-low cost**: With DeepSeek V4 Flash, translating ~75,000 dialogue entries costs approximately **$2.39 USD**
- **Enforced terminology accuracy**: With script assistance, AI achieves **99%+ accuracy** on proper nouns such as character names, locations, and item names. In contrast, tools like Gemini's Gem feature or Qwen's project feature still have a non-negligible rate of mistranslating proper nouns, even with well-crafted prompts.
- **Interactive operation**: Supports selecting sheets and entry ranges
- **Async concurrency**: Sends multiple API requests simultaneously, significantly reducing translation time
- **Checkpoint resume**: If the translation is interrupted due to network issues or manual interruption (Ctrl+C), simply re-run the script to resume from where it left off — no need to start over
- **Auto-review**: Three-layer checks (terminology / placeholders / untranslated), generates a color-coded review report
- **Multi-API support**: Supports using multiple API keys simultaneously (main/fallback classification), round-robin task distribution, automatic 429 rate-limit handling (cooldown/permanent disable), maximizing translation throughput
- **Automated proofreading workflow**: LLM dual-round evaluation cross-validation + up to 3 rounds of polishing + retranslation protection, produces color-coded proofreading reports
- **Glossary-based proofreading**: Enforces glossary during proofreading to prevent the LLM from deviating from correct terminology when polishing

### File Structure

| File | Purpose |
|---|---------------------------------|
| `batch_translate.py` | **Main translation script** — interactive entry point |
| `batch_proofread.py` | **Proofreading script** — interactive entry point |
| `proofreader.py` | **Proofreading core module** — LLM dual-round evaluation + polishing + retranslation protection |
| `glossary.py` | Reads terminology Excel or auto-extracts glossary from target + outputs review file |
| `tm_matcher.py` | Template matching (**not yet enabled**, will be added in the official release) |
| `llm_translator.py` | **AI batch translation core**, async parallel calls, with smart JSON extraction and json_repair fallback |
| enforcer.py | **Three-layer enforcement** (terminology/placeholders/untranslated), auto-correction + color-coded review report |
| `api_config.py` | Multi-API configuration parser, supports main/fallback classification, category-level default concurrency, per-API overrides |
| `.env` | API configuration file, supports multi-API numbered format and legacy single-API format |
| `.env.example` | Configuration template |
| `workplace/` | **Working directory** (auto-created), all inputs and outputs stored here |

> The `workplace/` directory contains the following subdirectories:
> - `_checkpoint/` — Translation checkpoint data for resume, each sheet has its own subdirectory (`{sheet_name}/`), auto-deleted after completion
> - `_proofread_checkpoint/` — Proofreading-specific checkpoint, independent from main translation
> - `_proofread_backup/` — Proofreading backup
> - `_debugmessage/` — Low translation rate debug logs (auto-generated, displayed and cleared on next startup)


### Pipeline

```
Main Translation Script
batch_translate.py → executes in order:
① glossary.py      Load terminology database
② tm_matcher.py    Template parameter matching ⚠️ Not yet enabled, will be added in official release
③ llm_translator.py AI batch translation (async parallel)
④ enforcer.py      Three-layer enforcement + retranslation + checkpoint resume + color-coded review report
```
```
Proofreading Script
batch_proofread.py → processes each worksheet:
① Phase 2: LLM Dual-round Evaluation (mixed R1+R2 batch pool)
② Phase 3: LLM Polish (up to 3 rounds)
③ Phase 4a: Retranslation Protection
④ Phase 4b: Template Correction (executed after all worksheets)
⑤ Generate Reports
```

---

## Installation

```bash
pip install openpyxl pandas openai python-dotenv json-repair
```

## Configuration

### 1. Get an API Key

This tool supports any **OpenAI-compatible API**. Recommended options:

| Platform                                            | Recommended Model | Cost |
|-----------------------------------------------------|---------------------------------|----|
| [OpenRouter](https://openrouter.ai/)                | `deepseek/deepseek-v4-flash` | Very low |
| [DeepSeek Official](https://platform.deepseek.com/) | `deepseek-v4-flash` | Very low |
| [Nvidia (Free API)](https://build.nvidia.com/)      | `deepseek-ai/deepseek-v4-flash` | Free |
| [Opencode Zen (Free API)](https://opencode.ai/zen/)     | `deepseek-v4-flash-free` | Free |

### 2. Create the `.env` File

Copy `.env.example` to `.env` and fill in your settings. Two formats are supported; examples below:

#### Multi-API Format (Recommended)

```env
# Main API (paid, default concurrency=10)
API1_TYPE=main
API1_PARALLEL_LIMIT=x (Add this parameter with a number if you want to set a custom concurrency limit)
API1_MODEL_PROVIDER=openrouter
API1_MODEL=deepseek/deepseek-v4-flash
API1_API_KEY=sk-your_api_key_here
API1_BASE_URL=https://openrouter.ai/api/v1

# Fallback API (free, default concurrency=1)
API2_TYPE=fallback
API2_PARALLEL_LIMIT=x (Add this parameter with a number if you want to set a custom concurrency limit)
API2_MODEL_PROVIDER=nvidia
API2_MODEL=deepseek-ai/deepseek-v4-flash
API2_API_KEY=nvapi-your_free_key_here
API2_BASE_URL=https://integrate.api.nvidia.com/v1
```

Legacy single-API format (backward compatible)
```env
API_KEY=sk-your_api_key_here
MODEL_PROVIDER=openrouter
MODEL=deepseek/deepseek-v4-flash
BASE_URL=https://openrouter.ai/api/v1
```
> Both formats can coexist — if `API1_` settings are detected, the multi-API format takes priority. Each API can optionally set `APIx_PARALLEL_LIMIT` to override the category default. Main API default concurrency=10, fallback API default concurrency=1.

---

## Usage

### Running the Main translation script
Place the translation target Excel and glossary (optional) into the `workplace/` directory, then run the main controller script.

### Interactive Steps (Translation)

```
Step 1: Select target Excel  → Lists all .xlsx files under workplace/
Step 2: Select glossary      → Choose a glossary Excel, auto-extract from target's name/manual sheets, or skip (built-in ADD_LIST only)
Step 3: Select worksheets    → Single or multiple
Step 4: Select range         → All untranslated / First N for testing / Specify row range
Step 5: Confirm execution    → Shows summary, press Y to confirm
```

### Output After Execution (Translation)

All output files are placed under the `workplace/` directory:

| File | Description |
|------|------|
| `{source_name}_translated_output.xlsx` | **Completed translation file**, located in `workplace/` |
| `review_report.xlsx` | **Review report** (entries needing manual review), located in `workplace/` |
| `_checkpoint/` | **Checkpoint resume temp directory**, located in `workplace/` (auto-deleted after completion) |

---

### Usage: Proofreading
Place the translated Excel into `workplace/` and run `batch_proofread.py`.
> ⚠️ **Note**: The proofreading pipeline currently only supports **single worksheet** processing.

### Interactive Steps (Proofreading)

```
Step 1: Select target Excel    → Lists all .xlsx files under workplace/
Step 2: Select glossary (required) → Choose a glossary Excel or auto-extract (proofreading requires a glossary, cannot skip)
Step 3: Select worksheet       → Choose the worksheet to proofread
Step 4: Select proofreading range → Select the entry range to proofread
Step 5: Confirm execution      → Starts proofreading (Phase 2→3→4a→4b→Reports)
```

### Output After Execution (Proofreading)

| File | Description |
|------|---------|
| `{source_name}_proofread_output.xlsx` | **Proofread Excel file** |
| `proofread_report.xlsx` | **Proofreading summary report** (Type1/Type2 color-coded) |
| `review_report_proofread.xlsx` | **Retranslation protection review details** |
| `_proofread_checkpoint/` | **Checkpoint resume temp directory**, located in `workplace/` (auto-deleted after completion) |

---

### Checkpoint Resume

If the translation/proofreading is interrupted due to network issues, API errors, or manual interruption (Ctrl+C), the script supports resuming from where it left off:

**Resume workflow:**
1. Re-run `batch_translate.py` / `batch_proofread.py`
2. The script automatically scans `workplace/_checkpoint/session.json` (translation) or `workplace/_proofread_checkpoint/session.json` (proofreading) to detect unfinished progress
3. Displays a summary of the last translation settings (Excel, worksheet, progress)
4. Asks whether to resume:

```
============================================================
  Unfinished translation progress detected
============================================================
  Excel: transcript_zh.xlsx
  Worksheet: dialogue_experimental
  Progress: 504/1000 entries
  Glossary: glossary.xlsx
============================================================

Resume the previous translation? (Y/n):
```

5. Choose `Y` → automatically loads glossary settings, restores translated/proofread entries, and resumes from the interruption point
6. Choose `n` → clears old checkpoint and starts a fresh translation

> ⚠️ **Note**: The checkpoint resume feature **ensures the vast majority of translated progress is saved, but not 100%**. In extreme cases (such as abrupt shutdown), the last 1-2 batches that were completed but not yet written to checkpoint may not be recoverable.

---

## Glossary & Custom Dictionary

### Excel Glossary

Use an Excel file with the same format as the translation target, column order:
`english / translation / category / sub_category / source / notes / wiki_url`

Only rows with a non-empty `translation` column are loaded as glossary entries.

### Built-in ADD_LIST

Hardcoded terms can be written directly in `glossary.py` (takes priority over Excel when there's a conflict):

```python
ADD_LIST: dict[str, str] = {
    "Old School RuneScape": "Old School RuneScape",
    "OSRS": "OSRS",
    "RuneLite": "RuneLite",
    "RuneLingual": "RuneLingual",
    # Add your own, e.g.:
    # "Saradomin": "萨拉多明",
}
```

### Built-in IGNORE_LIST

Some common nouns that are prone to mistranslation have been pre-excluded in `glossary.py`'s `IGNORE_LIST` to prevent the AI from incorrectly treating them as terminology.

**Example (located in `glossary.py`):**

```python
IGNORE_LIST: set[str] = {
    "Toolkit", "Vial", "Bones", "Book", "Man", "Run", "Ash",
    "Red", "Will", "Art", "Smith", "Gem", "Woman", "Tree",
    "Shadow", "Rock", "Letter", "Jug", "Egg",
    # ... see glossary.py for the full list
}
```

**How to add entries:**
- Any common English word you don't want checked as terminology can be added
- Adding a word also matches its **singular/plural/case** forms (e.g., adding `Egg` automatically filters `Eggs`, `EGGS`)
- Entries with the same name already in the Excel glossary will also be ignored

---

## Template Matching (tm_matcher)

⚠️ **This feature is not yet enabled** (the `TEMPLATES` list is empty). All entries are currently handled entirely by AI translation.

Template matching will be added in the **official release**. Users will then be able to define regex templates for automatic translation fill-in (e.g., `"Talk to (.+?)\\."` → `"与{0}对话。"`), reducing the number of API calls. Interested users can refer to the comments in `tm_matcher.py` to learn the syntax in advance.

---

## Constants

The following constants are located in `api_config.py` and `llm_translator.py`. **Do not change them unless you know exactly what you're doing:**

| Constant | Default | Description |
|------|--------|------------------------------|
| `BATCH_SIZE_LIMIT` | 100 | Max entries per API request batch (llm_translator.py) |
| `MAIN_DEFAULT_LIMIT` | 10 | Main API default concurrency (api_config.py) |
| `FALLBACK_DEFAULT_LIMIT` | 1 | Fallback API default concurrency (api_config.py) |
| `REQUEST_INTERVAL` | 1 | Interval in seconds between requests from the same API (api_config.py) |

> When adjusting concurrency: you can set `APIx_PARALLEL_LIMIT` in `.env` for individual APIs, or modify the category defaults in `api_config.py`. Setting it too high may trigger API endpoint rate limits. The defaults of main=10 and fallback=1 have been tested as the optimal balance point.

---

## Performance Reference

### Benchmarks (DeepSeek V4 Flash, evening hours)

| Entries | Avg Cost (Translation) | Translation Time (3 runs) | Avg Cost (Proofreading) | Proofreading Time (3 runs) |
|---------|---------------|----------------|----------|----------------|
| 500 | 0.01-0.02 USD | 329s, 467s, 353s | 0.02 USD | 350s, 387s, 461s |
| 2,000 | 0.06-0.07 USD | 801s, 746s, 696s | 0.07-0.08 USD | 912s, 1243s |
| 5,000 | 0.14 USD | 2084s, 1465s, 2170s | |
| 75,000 | 2.39 USD | 8 hours | | |

### Benchmarks (Paid vs Free API Speed Comparison)

Using paid API DeepSeek V4 Flash as the baseline (1x), the following shows the relative time required for a free API to translate a single batch (100 entries). If you have additional benchmark data, contributions are welcome.

| API Source | Nvidia (DS v4 flash) | Opencode (DS v4 flash) | Openrouter (gpt-oss-120b) |
|----------|:-------------------:|:--------------------:|:------------------------:|
| Relative Time |       1-1.5x        |        1-1.5x        |         1.5-2x           |

> 💡 **Usage tip**: Free APIs are considerably slower and are only recommended as a supplement to paid APIs for large-scale translations (e.g., 2,000+ entries). Since the multi-API round-robin dispatcher automatically distributes tasks to all available APIs, using free APIs for small batches (e.g., 500 entries) may proportionally slow down overall progress.

### Time-of-Day Impact & Fluctuation (Speculative)

- **Daytime is ~20% slower than late night**: OpenRouter's aggregation platform has more users during overlapping Asia/Europe hours, significantly increasing API endpoint response times. Large-scale translation is recommended during off-peak late-night hours.
- **Same-batch fluctuation of ~±30%**: Each request on OpenRouter may be routed to a different upstream provider or GPU node, combined with varying sentence lengths within batches and different retry counts, resulting in random time variance for the same translation volume.

---

## Troubleshooting

### API Related

**Q: After running, `ImportError: No module named 'openai'` appears**
<br>A: Dependencies not installed. Run `pip install openai pandas openpyxl python-dotenv`.

**Q: `ValueError: Please set the API_KEY environment variable or set it in the .env file` appears**
<br>A: You forgot to create the `.env` file. Copy `.env.example` to `.env` and fill in your API Key.

**Q: API requests keep failing or timing out**
<br>A: Check that `BASE_URL` and `MODEL` in `.env` are correct. If using OpenRouter, verify your account balance is sufficient. You can also try lowering the concurrency of your main/fallback APIs to reduce rate limit risk.

**Q: Translation speed is much slower than expected**
<br>A: First check the time of day — daytime being ~20% slower than late night is normal. If it's still slow at night, check your network connection or try switching API endpoints.

### Terminology Related

**Q: The review report has many terminology issues I don't recognize**
<br>A: Common nouns may be incorrectly treated as terminology. Check your Excel glossary for unintended entries, or add the word to `glossary.py`'s `IGNORE_LIST`.

**Q: I added a term but the AI didn't use it**
<br>A: Check that the `translation` column in your glossary Excel is non-empty (only rows with a non-empty translation column are loaded). For `ADD_LIST` entries, verify spelling and capitalization are exactly correct.

**Q: "Eggs" is in IGNORE_LIST but still shows up as an issue**
<br>A: Make sure your `glossary.py` is the latest version — `IGNORE_LIST` now uses normalized matching (adding `Egg` automatically filters `Eggs`, `EGGS`, etc.). If you also have an `"Eggs"` entry in the Excel glossary, remove it from Excel as well.

### File Related

**Q: No output files were generated after translation**
<br>A: Check whether the target Excel already has translations (non-empty `translation` column). If all entries are already translated, the script skips the worksheet. Try selecting a range option other than "All untranslated".

**Q: The output `_translated_output.xlsx` won't open**
<br>A: Make sure the file isn't locked by another program (e.g., Excel). If it still won't open, an error may have occurred during translation — check the terminal output for error messages.

**Q: The `_checkpoint/` directory wasn't auto-deleted**
<br>A: It's automatically deleted when the script completes normally. If the script was forcibly interrupted, `_checkpoint/` is preserved for future resume. Manually deleting it won't affect functionality.

### Checkpoint Resume Related

**Q: Progress is not detected when resuming**
<br>A: Resume depends on `workplace/_checkpoint/session.json`. If you manually moved files, you need to move the entire `_checkpoint/` directory together. If `session.json` was manually deleted, the resume feature will not work.

**Q: Translations from a completed sheet are missing after resume**
<br>A: Resume automatically restores data from completed sheets. If the interruption occurred during translation, simply re-run the script to continue from the interrupted sheet.

**Q: Some translations are missing after resuming**
<br>A: As noted in the "Checkpoint Resume" section, in extreme cases (such as abrupt shutdown) the last 1-2 batches may not be saved. This is normal — simply re-translate the missing entries.

**Q: The target Excel has been modified since the last run — can I still resume?**
<br>A: Resume relies on recorded selected indices (`selected_indices`). If the target Excel's content or entry order has changed, the indices may no longer match. It's recommended to choose "No" and start a fresh translation.

### Debug Related

**Q: The message `[APIx] ⚠️ Low translation rate 1.1% (1/94), debug info saved` appears**
<br>A: The API lacks sufficient translation capability — only 1 out of 94 entries was successfully translated. Check the debug files in `workplace/_debugmessage/` to review the full response and consider switching to a different model.

**Q: The message `[APIx] ⚠️ API returned a single object instead of an array` appears**
<br>A: The API does not support batch responses, returning only a single item. If this message appears repeatedly, consider removing it from `.env` or switching to another

**Q: The message `JSON repair successful` appears**
<br>A: The model's response contained minor JSON formatting issues (e.g., missing commas or colons). `json_repair` has automatically fixed them — no impact on translation results.

### Proofreading Related

**Q: The message `[APIx] ⚠️ Completion rate 40% (4/10) below 75%, retrying` appears**
<br>A: The 75% completion rate check is a normal mechanism in the proofreading phase. It automatically retries up to 3 attempts. If still below 75% after 3 tries, it accepts the result and logs debug info.

**Q: What are Type1 and Type2 in the proofreading report?**
<br>A: Type1 refers to terminology/placeholder/untranslated issues that can be automatically detected by scripts, marked with background colors. Type2 refers to fluency issues found by LLM dual-round evaluation — entries judged acceptable in both rounds are skipped.

**Q: Can proofreading handle multiple worksheets?**
<br>A: Currently only supports single worksheet processing. For multiple worksheets, run the proofreading script for each worksheet separately.

---

## License

This project is licensed under GPL v3. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 lck3141592654
