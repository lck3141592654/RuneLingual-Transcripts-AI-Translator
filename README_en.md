# RuneLingual Transcripts AI Translation Pipeline

<div align="center">

[English](README_en.md) | [中文](README.md)

</div>

## Overview

An AI-powered automated translation pipeline designed for large-scale game text translation, located in the `updater/experimental/` directory.

> ⚠️ **Beta Notice**: This tool is currently in beta and only supports **Simplified Chinese** translation. Traditional Chinese and other languages will be supported in the official release.

### Features

- **Ultra-low cost**: With DeepSeek V4 Flash, translating 75,000 dialogue lines costs approximately **$2.1 USD**
- **Forced terminology accuracy**: With script assistance, AI achieves **99%+ accuracy** on proper nouns such as character names, locations, and item names. In contrast, tools like Gemini's Gem feature or Qwen's project feature still have a non-negligible rate of mistranslating proper nouns, even with well-crafted prompts.
- **Interactive operation**: Supports selecting language, sheet, and entry range
- **Asynchronous concurrency**: Sends multiple API requests simultaneously, significantly reducing translation time
- **Auto-review**: Automatically checks terminology usage and generates a review report

### File Structure

| File | Purpose |
|------|---------|
| `batch_translate.py` | **Main controller** — interactive entry point |
| `glossary.py` | Reads terminology Excel and outputs a dictionary |
| `tm_matcher.py` | Template matching (**not yet enabled**, will be added in the official release) |
| `llm_translator.py` | **AI batch translation core** — async parallel calls |
| `enforcer.py` | **Terminology enforcement** — auto-correction + review report generation |
| `.env` | Your API configuration (copy `.env.example` and remove ".example") |
| `.env.example` | Configuration template |

### Four-Stage Pipeline

```
batch_translate.py → executes in order:
① glossary.py      Load terminology database
② tm_matcher.py    Template pattern matching ⚠️ Not yet enabled, coming in official release
③ llm_translator.py AI batch translation (async parallel)
④ enforcer.py      Terminology enforcement + review report
```

---

## Installation

```bash
pip install openpyxl pandas openai python-dotenv
```

## Configuration

### 1. Get an API Key

This tool supports any **OpenAI-compatible API**. Recommended options:

| Provider | Recommended Model | Cost |
|----------|-------------------|------|
| [OpenRouter](https://openrouter.ai/) | `deepseek/deepseek-v4-flash` | Very low |
| DeepSeek Official | `deepseek-chat` | Very low |
| OpenAI | `gpt-4o-mini` | Higher |

### 2. Create a `.env` File

Copy `.env.example` to `.env` and fill in your settings:

```env
API_KEY=sk-your_api_key_here
MODEL_PROVIDER=openrouter
MODEL=deepseek/deepseek-v4-flash
BASE_URL=https://openrouter.ai/api/v1
```

---

## Usage (Put experimental folder to Runelingual-Transcripts\updater first)

### Run the Main Script

```bash
cd updater/experimental
python batch_translate.py
```

### Interactive Steps

```
Step 1: Choose language       → Select from directory names under draft/ (e.g., zh, fr)
Step 2: Choose target Excel   → Select the file to translate
Step 3: Choose glossary       → Select an Excel glossary or use built-in dictionary only
Step 4: Choose sheet          → Single or multi-select
Step 5: Choose translation range → All untranslated / First N test entries / Specific row range
Step 6: Confirm execution     → Review summary and press Y to confirm
```

### Output Files

| File | Description |
|------|-------------|
| `{source_filename}_translated_output.xlsx` | **Completed translation file** |
| `review_report.xlsx` | **Review report** (entries requiring manual review) |
| `progress.json` | Progress checkpoint (automatically deleted after translation completes) |

---

## Output File Naming

If you choose to translate `transcript_zh.xlsx`, the output will be `transcript_zh_translated_output.xlsx`.

---

## Glossary and Custom Dictionary

### Excel Glossary

Use an Excel file with the same format as the translation target. Column order:
`english / translation / category / sub_category / source / notes / wiki_url`

Only rows with a non-empty `translation` column are loaded as glossary entries.

### Built-in ADD_LIST

Hard-coded terms can be added directly in `glossary.py` (these take priority over Excel entries when conflicts occur):

```python
ADD_LIST: dict[str, str] = {
    "Old School RuneScape": "Old School RuneScape",
    "OSRS": "OSRS",
    "RuneLite": "RuneLite",
    "RuneLingual": "RuneLingual",
    # Add your own entries, for example:
    # "Saradomin": "萨拉多明",
}
```

### Built-in IGNORE_LIST

Common nouns that are easily mistranslated are pre-excluded in `glossary.py`'s `IGNORE_LIST` to prevent AI from incorrectly treating them as terminology.

**Example (in `glossary.py`):**

```python
IGNORE_LIST: set[str] = {
    "Toolkit", "Vial", "Bones", "Book", "Man", "Run", "Ash",
    "Red", "Will", "Art", "Smith", "Gem", "Woman", "Tree",
    "Shadow", "Rock", "Letter", "Jug", "Egg",
    # ... see glossary.py for the full list
}
```

**How to add your own entries:**
- Any common English word you don't want checked as terminology can be added
- Entries are matched against **singular/plural and case variations** automatically (e.g., adding `Egg` will also ignore `Eggs`, `EGGS`)
- Identical entries already present in the Excel glossary are also ignored

---

## Template Matching (tm_matcher)

⚠️ **This feature is not yet enabled** (the `TEMPLATES` list is empty). All entries are currently translated by AI.

Template matching will be added in the **official release**. You will be able to define regex templates for automatic translation (e.g., `"Talk to (.+?)\."` → `"与{0}对话。"`), reducing API calls. Interested users can check `tm_matcher.py` for syntax details in advance.

---

## Constants Configuration

The following constants are defined at the top of `llm_translator.py`. **It is not recommended to change them unless you know what you are doing:**

| Constant | Default | Description |
|----------|---------|-------------|
| `BATCH_SIZE_LIMIT` | 100 | Maximum entries per batch API request |
| `PARALLEL_LIMIT` | 10 | Maximum concurrent API requests |
| `REQUEST_INTERVAL` | 1 | Interval in seconds between starting consecutive requests |

> When adjusting `PARALLEL_LIMIT`, note that values that are too high may trigger API rate limits and actually slow down overall speed, while values that are too low cannot fully utilize parallelism. The default of 10 has been tested as the optimal balance.

---

## Performance Reference

### Benchmark Data (DeepSeek V4 Flash, dusk时段)

| Lines | Avg Cost | Duration (3 runs) |
|-------|---------|-------------------|
| 500 | 0.01-0.02 USD | 329s, 467s, 353s |
| 2000 | 0.06-0.07 USD | 801s, 746s, 696s |
| 5000 | 0.14 USD | 2084s, 1465s, 2170s |

### Cost Analysis

Translation costs align closely with estimates. Based on $0.14 USD for 5,000 lines, **75,000 lines are estimated at ~$2.1 USD**.

### Time-of-Day Impact and Variance (Estimated)

- **Daytime is 50-70% slower than nighttime**: OpenRouter's aggregation platform sees higher concurrent usage during the Asia/Europe-America overlap period, significantly increasing API response times. Large-scale translations are recommended during off-peak nighttime hours.
- **~20% variance within same batch size**: Each request on OpenRouter may be routed to different upstream providers or GPU nodes, combined with sentence length variation within batches, causing random timing fluctuations for the same line count.

---

## Troubleshooting

### API Issues

**Q: I get `ImportError: No module named 'openai'`**
<br>A: Dependencies are not installed. Run `pip install openai pandas openpyxl python-dotenv`.

**Q: I get `ValueError: Please set API_KEY environment variable or configure it in the .env file`**
<br>A: You forgot to create the `.env` file. Copy `.env.example` to `.env` and fill in your API Key.

**Q: API requests keep failing or timing out**
<br>A: Check that `BASE_URL` and `MODEL` in `.env` are correct. If using OpenRouter, verify your account balance is sufficient. You can also try lowering `PARALLEL_LIMIT` to 5 to reduce rate limit risk.

**Q: Translation is much slower than expected**
<br>A: First check the time of day — daytime being 50-70% slower than nighttime is normal. If it's still slow at night, check your network connection or try switching API endpoints.

### Terminology Issues

**Q: The review report contains many unfamiliar terminology issues**
<br>A: Common nouns may be incorrectly flagged as terminology. Check your Excel glossary for entries that shouldn't be there, or add the word to `IGNORE_LIST` in `glossary.py`.

**Q: I added a term but the AI didn't use it**
<br>A: Check if the `translation` column in your Excel glossary has a value (only rows with a non-empty `translation` column are loaded). If from `ADD_LIST`, verify the spelling and case match exactly.

**Q: `"Eggs"` is in IGNORE_LIST but still shows up as an issue**
<br>A: Confirm you're using the latest version of `glossary.py` where `IGNORE_LIST` uses normalized matching (adding `Egg` will filter `Eggs`, `EGGS`, etc.). If you also have an `"Eggs"` entry in your Excel glossary, remove it from there as well.

### File Issues

**Q: No output file was generated**
<br>A: Check if the target Excel already has translations (non-empty `translation` column). If everything is already translated, the script will skip that sheet. Try selecting a range option other than "All untranslated entries".

**Q: The output `_translated_output.xlsx` won't open**
<br>A: Make sure the file isn't being held open by another program (e.g., Excel). If it still won't open, an error may have occurred during translation — check the terminal output for error messages.

**Q: `progress.json` was not automatically deleted**
<br>A: The script deletes it on normal completion. If the script was interrupted, `progress.json` is preserved for checkpoint resumption. Manually deleting it won't affect functionality.
