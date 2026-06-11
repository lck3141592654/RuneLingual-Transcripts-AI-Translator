import json, time, os, re, asyncio
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE_LIMIT = 100
PARALLEL_LIMIT = 10
REQUEST_INTERVAL = 1  # seconds


def _timestamp(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  [{now}] {msg}")


def _get_config():
    provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    model = os.getenv("MODEL", "").strip()
    base_url = os.getenv("BASE_URL", "").strip()
    api_key = os.getenv("API_KEY", "")
    return provider, model, base_url, api_key


SYSTEM_PROMPT_BASE = (
    "你是一个 OSRS（Old School RuneScape）"
    "游戏文本的简体中文翻译专家。\n"
    "请遵守以下规则：\n"
    "1. 只能输出简体中文，除非是占位符、标签或代码\n"
    "2. 保持游戏术语一致\n"
    "3. 保留 HTML/XML 标签（如 <col...>, <br>, </col> 等）\n"
    "4. 保留占位符（如 []內的文字）\n"
    "5. 流暢自然和避免翻譯腔優先，不必完全忠實原文內谷\n"
    "6. 每条翻译独立进行，不要合并或省略\n"
    "7. 如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式。"
    "你必須使用'.'分隔，不要自行改為'·'或其他方式。你必須使用'.'分隔，不要自行改為'·'或其他方式。\n"
    "8. 输出格式为 JSON 阵列，每条物件包含 "
    "\"index\" 和 \"translation\" 两个栏位\n"
    "9. 如有 notes、wiki_url 等原始栏位，一并保留在输出物件中\n\n"
    "## 强制术语表（禁止使用官方和社区通常的翻譯，遇到以下英文词必须使用指定的中文翻译）\n"
    "{RELEVANT_GLOSSARY}"
)


def normalize_term(term: str) -> str:
    """复数归一化，用于术语匹配"""
    term = term.lower().strip()
    term = re.sub(r"^(a|an|the)\s+", "", term)
    term = re.sub(r"(?i)(?<=[a-z])ves$", "f", term)
    term = re.sub(r"(?i)(?<=[a-z])ies$", "y", term)
    term = re.sub(r"(?i)(?<=[a-z])es$", "", term)
    term = re.sub(r"(?i)(?<=[a-z])s$", "", term)
    return term.strip()


def get_relevant_glossary(batch, glossary):
    """只回傳當前批次有出現的術語（含複數歸一化匹配）。

    當長術語（如 "Lord Hosidius"）已覆蓋短術語的匹配範圍時，
    短術語不重複加入，節省 token 且避免混亂。
    """
    batch_text = " ".join(item.get("english", "") for item in batch).lower()

    # Step 1：找出所有匹配的術語及其 span
    term_matches = []  # (eng, chn, [(start, end), ...])
    for eng, chn in glossary.items():
        # 原始詞邊界匹配
        eng_pat = r"(?<![a-z'])" + re.escape(eng.lower()) + r"(?![a-z'])"
        spans = [m.span() for m in re.finditer(eng_pat, batch_text)]

        # 複數歸一化匹配（原機制不變）
        norm = normalize_term(eng)
        if norm != eng.lower():
            norm_pat = r"(?<![a-z'])" + re.escape(norm) + r"(?![a-z'])"
            spans.extend([m.span() for m in re.finditer(norm_pat, batch_text)])

        if spans:
            term_matches.append((eng, chn, spans))

    if not term_matches:
        return []

    # Step 2：長術語優先，短術語若被覆蓋則排除
    term_matches.sort(key=lambda x: len(x[0]), reverse=True)
    relevant = []
    covered_spans = []
    for eng, chn, spans in term_matches:
        all_covered = all(
            any(s >= cs[0] and e <= cs[1] for cs in covered_spans)
            for s, e in spans
        )
        if not all_covered:
            relevant.append((eng, chn))
            covered_spans.extend(spans)

    return relevant


def load_progress(output_dir=None) -> dict:
    progress_file = Path(output_dir) / "progress.json" if output_dir else Path(__file__).parent / "progress.json"
    if progress_file.exists():
        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed_count": 0, "processed_npcs": [], "completed_indices": []}


def save_progress(completed_count, processed_npcs, completed_indices, output_dir=None):
    progress_file = Path(output_dir) / "progress.json" if output_dir else Path(__file__).parent / "progress.json"
    progress_file.write_text(
        json.dumps({
            "completed_count": completed_count,
            "processed_npcs": processed_npcs,
            "completed_indices": completed_indices,
            "last_saved": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_client() -> AsyncOpenAI:
    _, _, base_url, api_key = _get_config()
    if not api_key:
        raise ValueError("请设定 API_KEY 环境变量或在 .env 档案中设定")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_model_name() -> str:
    _, model, _, _ = _get_config()
    return model


async def _translate_batch(client, model_name, batch, glossary):
    relevant = get_relevant_glossary(batch, glossary)
    glossary_text = (
        "\n".join([f"  {e} → {c}" for e, c in relevant])
        if relevant else "  无"
    )
    system_prompt = SYSTEM_PROMPT_BASE.replace("{RELEVANT_GLOSSARY}", glossary_text)
    msgs = []
    for item in batch:
        msg = {"index": item["_idx"], "english": item["english"]}
        for k in ["notes", "wiki_url"]:
            if item.get(k):
                msg[k] = item[k]
        msgs.append(msg)
    user_prompt = json.dumps(msgs, ensure_ascii=False)
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                timeout=120,
            )
            content = resp.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("\n", 1)[0]
                if content.endswith("```"):
                    content = content[:-3]
            return json.loads(content)
        except json.JSONDecodeError:
            if attempt < 2:
                await asyncio.sleep(2)
        except Exception:
            if attempt < 2:
                await asyncio.sleep(5)
    return [{"index": item["_idx"], "translation": None, "_error": "API failed"} for item in batch]


async def _translate_all_async(df, glossary, output_dir, completed_indices, pending):
    total = len(pending)

    # ── Step 1：按 sub_category 分組 ──
    groups: list[tuple[str, list[dict]]] = []
    i = 0
    while i < len(pending):
        npc = pending[i].get("sub_category", "")
        group = []
        while i < len(pending) and pending[i].get("sub_category", "") == npc:
            group.append(pending[i])
            i += 1
        groups.append((npc, group))

    # ── Step 2：大 NPC（≥100）拆分，餘數進小池；小 NPC 整組進小池 ──
    batches: list[list[dict]] = []
    small_pool: list[tuple[str, list[dict]]] = []

    for npc, group in groups:
        gs = len(group)
        if gs >= BATCH_SIZE_LIMIT:
            for k in range(0, gs, BATCH_SIZE_LIMIT):
                chunk = group[k:k + BATCH_SIZE_LIMIT]
                if len(chunk) == BATCH_SIZE_LIMIT:
                    batches.append(chunk)
                else:
                    small_pool.append((npc, chunk))
        else:
            small_pool.append((npc, group))

    # ── Step 3：小池合併（維持各 NPC 群組完整，逐組添加，不超過 100） ──
    current_batch: list[dict] = []
    for npc, group in small_pool:
        gs = len(group)
        if len(current_batch) + gs <= BATCH_SIZE_LIMIT:
            current_batch.extend(group)
        else:
            if current_batch:
                batches.append(list(current_batch))
            current_batch = list(group)
    if current_batch:
        batches.append(list(current_batch))

    batch_sizes = [len(b) for b in batches]
    print(f"  分組結果: {len(batches)} 批, 各批大小: {batch_sizes}")

    # ── 並行執行 ──
    client = get_client()
    model_name = get_model_name()
    sem = asyncio.Semaphore(PARALLEL_LIMIT)
    rate_lock = asyncio.Lock()
    last_request_time = 0.0
    progress_lock = asyncio.Lock()

    async def translate_and_update(batch, batch_num):
        nonlocal last_request_time

        async with rate_lock:
            now = time.monotonic()
            gap = REQUEST_INTERVAL - (now - last_request_time)
            if gap > 0:
                await asyncio.sleep(gap)
            last_request_time = time.monotonic()

        async with sem:
            _timestamp(f"批次 {batch_num}/{len(batches)} 開始 ({len(batch)} 条)")
            results = await _translate_batch(client, model_name, batch, glossary)
            new_count = 0
            for res in results:
                idx = res.get("index")
                trans = res.get("translation")
                if idx is not None and trans is not None:
                    df.at[idx, "translation"] = trans
                    new_count += 1
            async with progress_lock:
                completed_indices.update(
                    r.get("index") for r in results
                    if r.get("index") is not None and r.get("translation") is not None
                )
                save_progress(len(completed_indices), [], list(completed_indices), output_dir)
            _timestamp(f"批次 {batch_num}/{len(batches)} 完成 ({len(batch)} 条)")
            return new_count

    tasks = []
    for bi, batch in enumerate(batches):
        task = asyncio.create_task(translate_and_update(batch, bi + 1))
        tasks.append(task)

    await asyncio.gather(*tasks)
    save_progress(len(completed_indices), [], list(completed_indices), output_dir)
    _timestamp(f"翻译完成: {len(completed_indices)} 条")
    return df


def translate_all(df: pd.DataFrame, glossary: dict, output_dir: str | Path | None = None) -> pd.DataFrame:
    df = df.copy()
    progress = load_progress(output_dir)
    completed_indices = set(progress.get("completed_indices", []))
    if "translation" not in df.columns:
        df["translation"] = None
    pending = []
    for idx, row in df.iterrows():
        if pd.isna(row.get("translation")) or row["translation"] is None:
            if idx in completed_indices:
                continue
            pending.append({
                "_idx": idx,
                "english": str(row["english"]),
                "sub_category": str(row.get("sub_category", "")),
                "notes": row.get("notes"),
                "wiki_url": row.get("wiki_url"),
            })
    if not pending:
        print("  所有条目已完成，无需翻译")
        return df

    pending.sort(key=lambda x: (x.get("sub_category", ""), x.get("_idx", 0)))
    total = len(pending)
    print(f"  待翻译: {total} 条")

    df = asyncio.run(_translate_all_async(df, glossary, output_dir, completed_indices, pending))
    return df