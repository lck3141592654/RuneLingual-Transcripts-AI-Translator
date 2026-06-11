import pandas as pd
from pathlib import Path
from openai import AsyncOpenAI
import os, json, asyncio, time, re
from dotenv import load_dotenv

load_dotenv()

# 與主翻譯共用常數（改一處即兩邊生效）
from llm_translator import BATCH_SIZE_LIMIT, PARALLEL_LIMIT, REQUEST_INTERVAL

RETRY_PROMPTS = [
    "1. 幫我檢查占位符（如 []內的文字）是否不小心被翻譯了，我需要在譯文保留占位符的原樣。2. 使用简体中文修正以下翻译中的游戏术语错误。"
    "3. 如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
    "术语仍不正确，请严格对照术语表重新翻译。如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
    "最后一次修正，以下条目的术语必须使用指定翻译。如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式：",
]


def _get_client():
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _get_model():
    return os.getenv("MODEL", "").strip()


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
                content = resp.choices[0].message.content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    content = content.rsplit("\n", 1)[0]
                    if content.endswith("```"):
                        content = content[:-3]
                all_results.extend(json.loads(content))
                break
            except json.JSONDecodeError:
                if attempt < 2:
                    await asyncio.sleep(2)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(5)
        else:
            all_results.extend([{"index": idx, "translation": None, "_error": "API failed"} for idx, _, _ in batch])
    return all_results


async def _enforce_async(df, relevant_glossary, glossary_text, api_key):
    """非同步執行重譯循環"""
    client = _get_client()
    model_name = _get_model()
    sem = asyncio.Semaphore(PARALLEL_LIMIT)
    rate_lock = asyncio.Lock()
    last_request_time = 0.0

    for rnd in range(3):
        # 找出有問題的條目
        pool = []
        for idx, row in df.iterrows():
            eng = str(row.get("english", ""))
            trans = row.get("translation")
            if pd.isna(trans) or trans is None:
                continue
            issues = check_glossary_usage(eng, str(trans), relevant_glossary)
            if issues:
                pool.append((idx, row, issues))

        if not pool:
            print(f"  第 {rnd+1} 轮检查：全部正确")
            break

        if len(pool) < 3:
            print(f"  第 {rnd+1} 轮检查：{len(pool)} 条有问题（少于3条，跳过重译）")
            break

        print(f"  第 {rnd+1} 轮检查：{len(pool)} 条有问题，进行重译...")
        if not api_key or not relevant_glossary:
            break

        pre_count = len(pool)

        # 分批，並用 semaphore + rate_limit 控制並行度（與主翻譯相同機制）
        async def translate_one_patch(batch_slice):
            nonlocal last_request_time
            async with rate_lock:
                now = time.monotonic()
                gap = REQUEST_INTERVAL - (now - last_request_time)
                if gap > 0:
                    await asyncio.sleep(gap)
                last_request_time = time.monotonic()
            async with sem:
                return await _retry_round(client, model_name, batch_slice, glossary_text, rnd)

        # 分割 pool 為 BATCH_SIZE_LIMIT 大小
        tasks = []
        for bs in range(0, len(pool), BATCH_SIZE_LIMIT):
            batch_slice = pool[bs:bs + BATCH_SIZE_LIMIT]
            tasks.append(asyncio.create_task(translate_one_patch(batch_slice)))

        all_results_lists = await asyncio.gather(*tasks)

        # 套用結果
        for results in all_results_lists:
            for res in results:
                idx = res.get("index")
                trans = res.get("translation")
                if idx is not None and trans is not None:
                    df.at[idx, "translation"] = trans

        # 計算修正率，決定是否繼續
        post_pool = []
        for idx, row in df.iterrows():
            eng = str(row.get("english", ""))
            trans = row.get("translation")
            if pd.isna(trans) or trans is None:
                continue
            issues = check_glossary_usage(eng, str(trans), relevant_glossary)
            if issues:
                post_pool.append((idx, row, issues))

        post_count = len(post_pool)
        if post_count == 0:
            print(f"  第 {rnd+1} 轮重译后：全部正确")
            break

        corrected = pre_count - post_count
        rate = corrected / pre_count if pre_count > 0 else 0
        print(f"  第 {rnd+1} 轮重译后：剩余 {post_count} 条，修正率 {rate*100:.1f}%")
        if rate < 0.05:
            print(f"  修正率低於 5%，跳過後續輪次")
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

    api_key = os.getenv("API_KEY", "")

    # 非同步重譯
    if api_key and relevant_glossary:
        df = asyncio.run(_enforce_async(df, relevant_glossary, glossary_text, api_key))

    # 最終審查掃描
    for idx, row in df.iterrows():
        eng = str(row.get("english", ""))
        trans = row.get("translation")
        if pd.isna(trans) or trans is None:
            continue
        issues = check_glossary_usage(eng, str(trans), relevant_glossary)
        for eng_term, chn, desc in issues:
            review_rows.append({
                "english": str(row.get("english", "")),
                "sub_category": str(row.get("sub_category", "")),
                "sheet_name": str(row.get("category", "")),
                "current_translation": str(trans),
                "issue": desc,
                "suggested_fix": f"{eng_term} → {chn}",
            })

    review_df = pd.DataFrame(review_rows)
    if not review_df.empty:
        fp = Path(output_dir) / "review_report.xlsx" if output_dir else Path(__file__).parent / "review_report.xlsx"
        review_df.to_excel(fp, index=False)
        print(f"  审查报告已写入: {fp} ({len(review_df)} 条需审查)")
    return df, review_df