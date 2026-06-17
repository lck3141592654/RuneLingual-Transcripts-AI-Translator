import pandas as pd
from pathlib import Path
from openai import AsyncOpenAI
import os, json, asyncio, time, re
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from llm_translator import BATCH_SIZE_LIMIT
from api_config import load_api_configs, REQUEST_INTERVAL

RETRY_PROMPTS = [
    "1. 如果译文中 [] 内的内容与原文不同，请恢复为原文的占位符。"
    "2. 如果当前译文与原文完全相同或沒有內容，请重新翻译。"
    "3. 使用简体中文修正以下翻译中的游戏术语错误。"
    "4. 如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
    "术语仍不正确，或占位符被翻译，或译文与原文相同、沒有內容，请严格对照要求重新翻译。"
    "如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
    "最后一次修正，以下条目的术语必须使用指定翻译，占位符必须保留原样，且不能回吐原文。"
    "如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
]

def _find_matched_spans(eng_lower: str, glossary: dict) -> list:
    """對每條原文找出所有匹配到（詞邊界）的術語及其 span，按術語長度降序排列。

    回傳 list[(eng, chn, [(start, end), ...])]
    """
    matches = []
    for eng, chn in glossary.items():
        pat_str = r"(?<![a-z'])" + re.escape(eng.lower()) + r"(?![a-z'])"
        spans = [m.span() for m in re.finditer(pat_str, eng_lower)]
        if spans:
            matches.append((eng, chn, spans))
    # 長術語優先處理（避免短術語被長術語覆蓋時誤報）
    matches.sort(key=lambda x: len(x[0]), reverse=True)
    return matches


def check_glossary_usage(english_text: str, translated_text: str, glossary: dict) -> list:
    """詞邊界匹配，防止『V』匹配到『Convert』或『Don』匹配到『don't』這類誤報。

    當原文中長術語（如 "Lord Hosidius"）的翻譯已正確出現在譯文中，
    則其範圍內的短術語（如 "Hosidius"）不再重複檢查。
    """
    issues = []
    eng_lower = english_text.lower()
    trans_lower = translated_text.lower()

    matches = _find_matched_spans(eng_lower, glossary)

    covered_by_correct = []  # 已被正確翻譯的長術語所覆蓋的 span 集合
    for eng, chn, spans in matches:
        # 檢查此術語的所有匹配 span 是否都被已覆蓋
        all_covered = all(
            any(s >= cs[0] and e <= cs[1] for cs in covered_by_correct)
            for s, e in spans
        )
        if all_covered:
            continue  # 已被更長且翻譯正確的術語覆蓋，跳過

        if chn.lower() in trans_lower:
            # 翻譯正確，將此術語的 span 加入已覆蓋集合
            covered_by_correct.extend(spans)
        else:
            issues.append((eng, chn, f"术语「{eng}」应为「{chn}」"))

    return issues

def check_placeholder(english_text: str, translated_text: str) -> list[str]:
    """比對原文和譯文中的 [...] 是否一致，返回問題描述清單"""
    issues = []
    eng_placeholders = re.findall(r'\[.*?\]', english_text)
    for ph in eng_placeholders:
        if ph not in translated_text:
            issues.append(f"佔位符「{ph}」被翻譯或遺失")
    return issues


def check_untranslated(english_text: str, translated_text) -> list[str]:
    """檢查是否未成功翻譯，返回問題描述清單"""
    issues = []
    # 情況 A：translation 為空
    if translated_text is None or (isinstance(translated_text, float) and pd.isna(translated_text)):
        issues.append("translation 欄位為空")
        return issues
    trans_str = str(translated_text).strip()
    # 情況 B：譯文與原文相同（不分大小寫），且原文包含英文字母
    if trans_str.lower() == english_text.strip().lower():
        if re.search(r'[a-zA-Z]', english_text):
            issues.append("譯文與原文相同，未實際翻譯")
    return issues

def scan_issues(df, relevant_glossary) -> list[tuple]:
    """走訪所有行，彙整三種檢查的結果，回傳問題 pool"""
    pool = []
    for idx, row in df.iterrows():
        eng = str(row.get("english", ""))
        trans = row.get("translation")
        all_issues = []

        # 未翻譯檢查（包含空值情況）
        untrans_issues = check_untranslated(eng, trans)
        if untrans_issues:
            for ui in untrans_issues:
                all_issues.append(("untranslated", "", ui))
            pool.append((idx, row, all_issues))
            continue  # 未翻譯時不繼續做其他檢查

        # 術語檢查（已有譯文才做）
        eng_term = str(eng)
        trans_str = str(trans)
        glossary_issues = check_glossary_usage(eng_term, trans_str, relevant_glossary)
        for eng_term, chn, desc in glossary_issues:
            all_issues.append(("glossary", f"{eng_term} → {chn}", desc))

        # 佔位符檢查
        ph_issues = check_placeholder(eng_term, trans_str)
        if ph_issues:
            for pi in ph_issues:
                all_issues.append(("placeholder", "", pi))

        if all_issues:
            pool.append((idx, row, all_issues))

    return pool

async def _retry_round(client, model_name, pool, glossary_text, rnd):
    """非同步執行一輪重譯，返回修正後的條目數"""
    total_before = len(pool)
    # 每批 BATCH_SIZE_LIMIT（100）條，無群組機制
    all_results = []
    for bs in range(0, len(pool), BATCH_SIZE_LIMIT):
        batch = pool[bs:bs + BATCH_SIZE_LIMIT]
        items = [{"index": idx, "english": str(row["english"])} for idx, row, _ in batch]
        prompt = (RETRY_PROMPTS[rnd] + "\n" + json.dumps(items, ensure_ascii=False)
                  + f"\n## 强制术语表（请严格使用以下翻译）\n{glossary_text}"
                  + "\n请回传 JSON 阵列，每条包含 index 和 translation。")
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0, timeout=60,
                )
                # 保持正則操作，不要改為字串，否則會大幅降低翻譯成功率
                content = resp.choices[0].message.content.strip()
                content = re.sub(r"^```(?:json)?\n?", "", content, flags=re.IGNORECASE)
                content = re.sub(r"\n```$", "", content)
                all_results.extend(json.loads(content))
                # 保持正則操作，不要改為字串，否則會大幅降低翻譯成功率
                break
            except json.JSONDecodeError:
                if attempt < 2:
                    await asyncio.sleep(2)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(5)
        else:
            all_results.extend([{"index": idx, "translation": None, "_error": "API failed"}
                               for idx, _, _ in batch])
    return all_results

async def _enforce_async(df, relevant_glossary, glossary_text):
    """非同步執行重譯循環，使用多 API 共享隊列模式"""
    api_configs = load_api_configs()
    if not api_configs:
        print("  無可用 API，跳過重譯")
        return df

    for rnd in range(3):
        pool = scan_issues(df, relevant_glossary)

        if not pool:
            print(f"  第 {rnd + 1} 轮检查：全部正确")
            break

        if len(pool) < 3:
            print(f"  第 {rnd + 1} 轮检查：{len(pool)} 条有问题（少于3条，跳过重译）")
            break

        # ── 掃描問題條目 ──
        gloss_count = sum(1 for _, _, issues in pool for t, _, _ in issues if t == "glossary")
        ph_count = sum(1 for _, _, issues in pool for t, _, _ in issues if t == "placeholder")
        untrans_count = sum(1 for _, _, issues in pool for t, _, _ in issues if t == "untranslated")
        print(f"  ── 掃描問題條目 ──")
        print(f"    術語檢查：{gloss_count} 條")
        if ph_count > 0:
            print(f"    佔位符檢查：{ph_count} 條")
        if untrans_count > 0:
            print(f"    未翻譯檢查：{untrans_count} 條")
        print(f"  第 {rnd + 1} 轮检查：{len(pool)} 条有问题，进行重譯...")

        pre_count = len(pool)

        # 分割 pool 為 BATCH_SIZE_LIMIT 大小的批次，放入共享隊列
        queue: asyncio.Queue = asyncio.Queue()
        batch_id = 0
        for bs in range(0, len(pool), BATCH_SIZE_LIMIT):
            batch_slice = pool[bs:bs + BATCH_SIZE_LIMIT]
            queue.put_nowait((batch_id, batch_slice))
            batch_id += 1
            total_batches = batch_id

        # 為每個 API 啟動 worker
        async def enforce_worker(cfg):
            client = AsyncOpenAI(api_key=cfg.key, base_url=cfg.base_url)
            sem = asyncio.Semaphore(cfg.parallel_limit)
            rate_lock = asyncio.Lock()
            last_request = 0.0

            while True:
                if cfg.is_cooling_down:
                    await asyncio.sleep(1)
                    continue

                async with sem:
                    try:
                        bid, batch_slice = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return

                    # 速率控制（每個 API 獨立）
                    async with rate_lock:
                        now = time.monotonic()
                        gap = REQUEST_INTERVAL - (now - last_request)
                        if gap > 0:
                            await asyncio.sleep(gap)
                        last_request = time.monotonic()

                    try:
                        results = await _retry_round(client, cfg.model, batch_slice, glossary_text, rnd)
                        fixed = 0
                        for res in results:
                            idx = res.get("index")
                            trans = res.get("translation")
                            if idx is not None and trans is not None:
                                df.at[idx, "translation"] = trans
                                fixed += 1
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  [{now}] [重譯] 批次 {bid + 1}/{total_batches} 完成 ({fixed} 条已修正) [{cfg.api_id} {cfg.model}]")
                    except Exception as e:
                        error_str = str(e).lower()
                        if "429" in error_str or "rate" in error_str:
                            cfg.mark_429()
                            if cfg.is_permanently_disabled:
                                print(f"  [{cfg.api_id} {cfg.model}] 第二次 429，永久停用")
                            else:
                                print(f"  [{cfg.api_id} {cfg.model}] 429，冷卻 60 秒")
                            # 放回隊列
                            queue.put_nowait((bid, batch_slice))
                        else:
                            print(f"  [{cfg.api_id} {cfg.model}] 錯誤：{e}")

        workers = [asyncio.create_task(enforce_worker(cfg)) for cfg in api_configs]
        await asyncio.gather(*workers)

        # 計算修正率，決定是否繼續
        post_pool = scan_issues(df, relevant_glossary)

        post_count = len(post_pool)
        if post_count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  [{now}] 第 {rnd + 1} 轮重译后：全部正确")
            break

        corrected = pre_count - post_count
        rate = corrected / pre_count if pre_count > 0 else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"  [{now}] 第 {rnd + 1} 轮重译后：剩余 {post_count} 条，修正率 {rate * 100:.1f}%")
        if rate < 0.05:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  [{now}] 修正率低於 5%，跳過後續輪次")
            break

    return df


def enforce(df: pd.DataFrame, glossary: dict, output_dir: str | Path | None = None) -> tuple:
    df = df.copy()
    review_rows = []

    # 只保留對當前批次有相關性的術語
    all_text = " ".join(str(row.get("english", "")).lower() for _, row in df.iterrows())
    relevant_glossary = {
        e: c for e, c in glossary.items()
        if re.search(r"(?<![a-z'])" + re.escape(e.lower()) + r"(?![a-z'])", all_text)
    }
    glossary_text = "\n".join([f"  {e} → {c}" for e, c in relevant_glossary.items()]) if relevant_glossary else "  无"

    # 檢查是否有可用 API
    api_configs = load_api_configs()

    # 非同步重譯
    if api_configs:
        df = asyncio.run(_enforce_async(df, relevant_glossary, glossary_text))

    # 最終審查掃描
    final_pool = scan_issues(df, relevant_glossary)
    for idx, row, issues in final_pool:
        trans = row.get("translation")
        trans_str = str(trans) if not (trans is None or (isinstance(trans, float) and pd.isna(trans))) else ""
        for issue_type, suggested_fix, desc in issues:
            review_rows.append({
                "english": str(row.get("english", "")),
                "current_translation": trans_str,
                "category": str(row.get("category", "")),
                "issue": f"[{issue_type}] {desc}",
            })

    review_df = pd.DataFrame(review_rows)
    if not review_df.empty:
        fp = Path(output_dir) / "review_report.xlsx" if output_dir else Path(__file__).parent / "review_report.xlsx"

        from openpyxl.styles import PatternFill

        fill_glossary = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        fill_placeholder = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
        fill_untranslated = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")

        with pd.ExcelWriter(fp, engine='openpyxl') as writer:
            review_df.to_excel(writer, index=False, sheet_name='Sheet1')
            worksheet = writer.sheets['Sheet1']

            # 找到 issue 欄位的欄號
            issue_col = None
            for col_idx, cell in enumerate(worksheet[1], start=1):
                if cell.value == "issue":
                    issue_col = col_idx
                    break

            if issue_col:
                for row in worksheet.iter_rows(min_row=2, max_col=worksheet.max_column, max_row=worksheet.max_row):
                    issue_cell = row[issue_col - 1]
                    issue_val = str(issue_cell.value) if issue_cell.value else ""
                    if issue_val.startswith("[glossary]"):
                        fill = fill_glossary
                    elif issue_val.startswith("[placeholder]"):
                        fill = fill_placeholder
                    elif issue_val.startswith("[untranslated]"):
                        fill = fill_untranslated
                    else:
                        continue
                    for cell in row:
                        cell.fill = fill

        print(f"  审查报告已写入: {fp} ({len(review_df)} 条需审查)")
    return df, review_df