import json, time, os, re, asyncio, uuid
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
import pandas as pd
from dotenv import load_dotenv
from glossary import normalize_term
from api_config import load_api_configs, REQUEST_INTERVAL

load_dotenv()

BATCH_SIZE_LIMIT = 100

CHECKPOINT_SUBDIR = "_checkpoint"
PROGRESS_FILE = "progress.json"
SESSION_FILE = "session.json"


def _timestamp(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  [{now}] {msg}")


SYSTEM_PROMPT_BASE = (
    "你是一个 OSRS（Old School RuneScape）"
    "游戏文本的简体中文翻译专家。\n"
    "请遵守以下规则：\n"
    "1. 只能输出简体中文，除非是占位符、标签或代码\n"
    "2. 保持游戏术语一致\n"
    "3. 保留 HTML/XML 标签（如 <col...>, <br>, </col> 等）\n"
    "4. 保留占位符（如 []內的文字）\n"
    "5. 流暢自然和避免翻譯腔優先，不必完全忠實原文內容\n"
    "6. 每条翻译独立进行，不要合并或省略\n"
    "7. 如果术语表的人名、地名等名詞用'.'分隔，例如'索菲娅.休斯'，你必須使用'.'分隔，不要自行改為'·'或其他方式。"
    "你必須使用'.'分隔，不要自行改為'·'或其他方式。你必須使用'.'分隔，不要自行改為'·'或其他方式。\n"
    "8. 输出格式为 JSON 阵列，每条物件包含 "
    "\"index\" 和 \"translation\" 两个栏位\n"
    "9. 如有 notes、wiki_url 等原始栏位，一并保留在输出物件中\n\n"
    "## 强制术语表（禁止使用官方和社区通常的翻譯，遇到以下英文词必须使用指定的中文翻译）\n"
    "{RELEVANT_GLOSSARY}"
)


def get_relevant_glossary(batch, glossary):
    """只回傳當前批次有出現的術語（含複數歸一化匹配）。"""
    batch_text = " ".join(item.get("english", "") for item in batch).lower()
    term_matches = []
    for eng, chn in glossary.items():
        eng_pat = r"(?<![a-z'])" + re.escape(eng.lower()) + r"(?![a-z'])"
        spans = [m.span() for m in re.finditer(eng_pat, batch_text)]
        norm = normalize_term(eng)
        if norm != eng.lower():
            norm_pat = r"(?<![a-z'])" + re.escape(norm) + r"(?![a-z'])"
            spans.extend([m.span() for m in re.finditer(norm_pat, batch_text)])
        if spans:
            term_matches.append((eng, chn, spans))
    if not term_matches:
        return []
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


def _checkpoint_dir(output_dir=None) -> Path:
    if output_dir:
        return Path(output_dir) / CHECKPOINT_SUBDIR
    return Path(__file__).parent / CHECKPOINT_SUBDIR


# ── 進度檔案 ──

def load_progress(output_dir=None) -> dict:
    p = _checkpoint_dir(output_dir) / PROGRESS_FILE
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed_count": 0, "completed_indices": []}


def save_progress(output_dir, completed_indices: list):
    cd = _checkpoint_dir(output_dir)
    cd.mkdir(parents=True, exist_ok=True)
    data = {
        "completed_count": len(completed_indices),
        "completed_indices": completed_indices,
        "last_saved": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    p = cd / PROGRESS_FILE
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Session 檔案 ──

def save_session(output_dir, session_info: dict):
    cd = _checkpoint_dir(output_dir)
    cd.mkdir(parents=True, exist_ok=True)
    sf = cd / SESSION_FILE
    sf.write_text(json.dumps(session_info, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session(output_dir=None) -> dict | None:
    sf = _checkpoint_dir(output_dir) / SESSION_FILE
    if sf.exists():
        try:
            return json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


# ── 備份：每批次獨立一個 part 檔案（UUID 避免覆蓋） ──

def save_backup_part(output_dir, session_tag: str, batch_num: int, batch_data: dict):
    """原子寫入單一批次的 part 檔案（強制同步磁碟後才 rename）"""
    cd = _checkpoint_dir(output_dir)
    cd.mkdir(parents=True, exist_ok=True)
    import os as _os
    tmp = cd / f"part_{session_tag}_{batch_num:06d}.tmp"
    final = cd / f"part_{session_tag}_{batch_num:06d}.json"
    tmp.write_text(json.dumps(batch_data, ensure_ascii=False), encoding="utf-8")
    with open(tmp, 'ab') as f:
        _os.fsync(f.fileno())
    tmp.replace(final)


def load_backup(output_dir=None) -> dict:
    """掃描所有 part_*.json，以 idx 為鍵合併所有備份資料"""
    cd = _checkpoint_dir(output_dir)
    if not cd.exists():
        return {}
    all_backup: dict = {}
    for f in sorted(cd.glob("part_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            all_backup.update(data)
        except Exception:
            pass
    return all_backup


def sync_progress(output_dir=None):
    """從 backup part 檔案反推 progress.json，確保絕對同步"""
    backup = load_backup(output_dir)
    indices = sorted(int(k) for k in backup)
    if indices:
        save_progress(output_dir, indices)
    else:
        pp = _checkpoint_dir(output_dir) / PROGRESS_FILE
        if pp.exists():
            pp.unlink()

def delete_checkpoint_files(output_dir):
    """清除所有 checkpoint 檔案"""
    cd = _checkpoint_dir(output_dir)
    if cd.exists():
        import shutil
        shutil.rmtree(cd)


# ── LLM API 調用 ──

async def _translate_batch(client, model_name, batch, glossary, api_id="?"):
    """發送單一批次到 LLM API 進行翻譯"""
    relevant = get_relevant_glossary(batch, glossary)
    glossary_str = "\n".join([f"  {e} → {c}" for e, c in relevant]) if relevant else "  无"
    system_prompt = SYSTEM_PROMPT_BASE.replace("{RELEVANT_GLOSSARY}", glossary_str)

    user_content = json.dumps([
        {"index": item["_idx"], "english": item["english"],
         "notes": item.get("notes"), "wiki_url": item.get("wiki_url")}
        for item in batch
    ], ensure_ascii=False)

    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=3600,
            )
            # 保持正則操作，不要改為字串，否則會大幅降低翻譯成功率
            text = resp.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\n```$", "", text)
            results = json.loads(text)

            # 方法一：先試明確的 key 名稱
            if isinstance(results, dict):
                if "translations" in results:
                    results = results["translations"]
                elif "translated" in results:
                    results = results["translated"]
                elif "data" in results:
                    results = results["data"]
                elif "object" in results and isinstance(results["object"], dict) and "translated" in results["object"]:
                    results = results["object"]["translated"]
            # 方法二：如果還是 dict，自動搜尋 index+translation 陣列
            if isinstance(results, dict):
                found = None
                for key, value in results.items():
                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) \
                            and "index" in value[0] and "translation" in value[0]:
                        found = value
                        break
                if found is None:
                    for key, value in results.items():
                        if isinstance(value, dict):
                            for k2, v2 in value.items():
                                if isinstance(v2, list) and len(v2) > 0 and isinstance(v2[0], dict) \
                                        and "index" in v2[0] and "translation" in v2[0]:
                                    found = v2
                                    break
                if found is not None:
                    results = found
            # ：如果 dict 本身就有 index+translation，視為單一條目
            if isinstance(results, dict) and "index" in results and "translation" in results:
                results = [results]
                print(f"    [{api_id}] ⚠️ API 回傳單一物件而非陣列")
                print(f"    [{api_id}] ⚠️ 如果多次顯示此訊息，代表此 API 不適合翻譯任務，建議從 .env 移除或更換模型")
            if isinstance(results, list) and len(results) > 0:
                success = sum(1 for r in results if isinstance(r, dict) and r.get("translation"))
                rate = success / len(batch) if len(batch) > 0 else 0
                if rate < 0.25:
                    debug_dir = Path(__file__).parent / "workplace" / "_debugmessage"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    uid = uuid.uuid4().hex[:4]
                    (debug_dir / f"debug_{ts}_{uid}.json").write_text(
                        json.dumps({
                            "api_id": api_id,
                            "model": model_name,
                            "batch_size": len(batch),
                            "returned": len(results),
                            "success": success,
                            "rate": round(rate, 3),
                            "response_preview": text[:3000]
                        }, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"    [{api_id}] ⚠️ 低翻譯率 {rate:.1%}（{success}/{len(batch)}），已儲存 debug 訊息")
            if isinstance(results, list) and len(results) > 0:
                null_count = sum(1 for r in results if r.get("translation") is None)
                if null_count > len(results) * 0.5:
                    print(f"    [{api_id}] 警告：{null_count}/{len(results)} 條翻譯為 null")
            if isinstance(results, list):
                if results and not all("index" in r and "translation" in r for r in results):
                    print(f"    [{api_id}] 警告：JSON 陣列中缺少 index/translation 欄位")
                    print(f"    回傳內容前 200 字: {text[:200]}")
            if isinstance(results, dict):
                if "translations" not in results and "index" not in results:
                    print(f"    [{api_id}] 警告：JSON 物件結構異常（無 translations 也無 index）")
                    print(f"    回傳內容前 200 字: {text[:200]}")
            # 保持正則操作，不要改為字串，否則會大幅降低翻譯成功率
            if isinstance(results, dict):
                results = [results]
            return results
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                raise
            # ↓ 嘗試用 json_repair 修復 JSON 格式錯誤
            if isinstance(e, json.JSONDecodeError):
                try:
                    from json_repair import repair_json
                    repaired = repair_json(text)
                    if repaired:
                        results = json.loads(repaired)
                        print(f"    [{api_id}] ⚠️ JSON 修復成功")
                        if isinstance(results, list):
                            return results
                        if isinstance(results, dict) and "translations" in results:
                            return results["translations"]
                except Exception:
                    pass
            # ↑ 修復結束
            print(f"    [{api_id}] API 錯誤 (嘗試 {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(5)

    return [{"index": item["_idx"], "translation": None, "_error": "API failed"} for item in batch]


# ── 非同步翻譯核心（多 API 共享隊列） ──
async def _translate_all_async(df, glossary, output_dir, pending):
    api_configs = load_api_configs()
    if not api_configs:
        print("  錯誤：沒有可用的 API 設定")
        return df

    # 過濾掉已永久停用的 API（若從 checkpoint 恢復時可能殘留）
    active_configs = [cfg for cfg in api_configs if not cfg.is_permanently_disabled]
    if not active_configs:
        print("  錯誤：所有 API 已永久停用")
        return df

    print(f"  已載入 {len(active_configs)} 個可用 API：")
    for cfg in active_configs:
        print(f"    {cfg.api_id} {cfg.model_provider}/{cfg.model} ({cfg.api_type}, 並發={cfg.parallel_limit})")

    # ── 分組 ──
    batches = _group_into_batches(pending)
    total_batches = len(batches)

    # ── 共享隊列 ──
    queue: asyncio.Queue = asyncio.Queue()
    for bi, batch in enumerate(batches):
        queue.put_nowait((bi + 1, batch))

    # ── 生成 session_tag ──
    session_tag = uuid.uuid4().hex[:8]

    # ── 每個 Worker 的狀態 ──
    worker_states = []
    for cfg in active_configs:
        worker_states.append({
            "cfg": cfg,
            "client": AsyncOpenAI(api_key=cfg.key, base_url=cfg.base_url),
            "sem": asyncio.Semaphore(cfg.parallel_limit),
            "rate_lock": asyncio.Lock(),
            "last_request": 0.0,
            "active_count": 0,
        })

    # ── 單一批次處理函數 ──
    async def process_batch(ws, batch_num, batch):
        cfg = ws["cfg"]
        async with ws["rate_lock"]:
            now = time.monotonic()
            gap = REQUEST_INTERVAL - (now - ws["last_request"])
            if gap > 0:
                await asyncio.sleep(gap)
            ws["last_request"] = time.monotonic()

        async with ws["sem"]:
            _timestamp(f"批次 {batch_num}/{total_batches} 開始 ({len(batch)} 条) [{cfg.api_id} {cfg.model}]")

            try:
                results = await _translate_batch(ws["client"], cfg.model, batch, glossary, cfg.api_id)
                new_backup = {}
                for res in results:
                    idx = res.get("index")
                    trans = res.get("translation")
                    if idx is not None and trans is not None:
                        df.at[idx, "translation"] = trans
                        new_backup[str(idx)] = str(trans)
                if new_backup:
                    save_backup_part(output_dir, session_tag, batch_num, new_backup)
                    sync_progress(output_dir)
                _timestamp(f"批次 {batch_num}/{total_batches} 完成 ({len(new_backup)} 条) [{cfg.api_id} {cfg.model}]")
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate" in error_str:
                    cfg.mark_429()
                    if cfg.is_permanently_disabled:
                        print(f"  [{cfg.api_id} {cfg.model}] 第二次 429，永久停用")
                    else:
                        print(f"  [{cfg.api_id} {cfg.model}] 429，冷卻 60 秒")
                    # 放回隊列
                    queue.put_nowait((batch_num, batch))
                else:
                    print(f"  [{cfg.api_id} {cfg.model}] 錯誤：{e}")
            finally:
                ws["active_count"] -= 1

    # ── 中央調度器：持續輪詢分配 ──
    all_tasks = []
    round_robin_index = 0

    while True:
        # 清理已完成的 task
        all_tasks = [t for t in all_tasks if not t.done()]

        # 檢查隊列是否空 + 無活躍任務
        if queue.empty() and all(ws["active_count"] == 0 for ws in worker_states):
            break

        # 過濾可用 Worker（未冷卻、未永久停用、未滿）
        available = []
        for ws in worker_states:
            cfg = ws["cfg"]
            if cfg.is_cooling_down or cfg.is_permanently_disabled:
                continue
            if ws["active_count"] >= cfg.parallel_limit:
                continue
            available.append(ws)

        if not available or queue.empty():
            await asyncio.sleep(0.2)
            continue

        # 輪流分配
        for _ in range(len(available)):
            ws = available[round_robin_index % len(available)]
            round_robin_index = (round_robin_index + 1) % len(available)

            try:
                batch_num, batch = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            ws["active_count"] += 1
            task = asyncio.create_task(process_batch(ws, batch_num, batch))
            all_tasks.append(task)

    # 等待所有 task 完成
    if all_tasks:
        try:
            await asyncio.gather(*all_tasks)
        except (asyncio.CancelledError, KeyboardInterrupt):
            sync_progress(output_dir)
            print(f"\n  ⚠️ 檢測到中斷，已儲存翻譯備份")
            raise

    sync_progress(output_dir)
    _timestamp("翻译完成")
    return df

def _group_into_batches(pending):
    """將待翻譯條目按 NPC 分組後切成批次"""
    # ── Step 1：按 sub_category 分組 ──
    groups = []
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

    # ── Step 3：小池合併（維持各 NPC 群組完整） ──
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
    return batches


def translate_all(df: pd.DataFrame, glossary: dict, output_dir: str | Path | None = None) -> pd.DataFrame:
    df = df.copy()

    # ── 從備份還原已翻譯的內容 ──
    backup = load_backup(output_dir)
    if backup:
        restore_count = 0
        for idx_str, trans in backup.items():
            idx = int(idx_str)
            if idx in df.index and (pd.isna(df.at[idx, "translation"]) or df.at[idx, "translation"] is None):
                df.at[idx, "translation"] = trans
                restore_count += 1
        if restore_count > 0:
            print(f"  從備份還原 {restore_count} 條翻譯")

    if "translation" not in df.columns:
        df["translation"] = None
    pending = []
    for idx, row in df.iterrows():
        if pd.isna(row.get("translation")) or row["translation"] is None:
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

    df = asyncio.run(_translate_all_async(df, glossary, output_dir, pending))
    return df