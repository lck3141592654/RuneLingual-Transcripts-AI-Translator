#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from glossary import load_glossary
from tm_matcher import match_and_fill
from llm_translator import translate_all as llm_translate
from llm_translator import save_session, delete_checkpoint_files, load_backup
from enforcer import enforce


SEP = "=" * 60
AUTO_GLOSSARY_SENTINEL = Path("__AUTO__")
WORKPLACE_DIR_NAME = "workplace"


def _get_workplace() -> Path:
    """取得腳本所在目錄同級的 workplace/ 目錄，不存在則自動建立。"""
    wp = Path(__file__).parent / WORKPLACE_DIR_NAME
    wp.mkdir(parents=True, exist_ok=True)
    return wp


def timestamp(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  [{now}] {msg}")


def elapsed(start: datetime, label: str):
    secs = (datetime.now() - start).total_seconds()
    print(f"  [{label}] 耗時: {secs:.1f} 秒")


def list_excel_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted([f for f in directory.glob("*.xlsx") if not f.name.startswith("~$")])


def choose_int(prompt: str, max_val: int, allow_zero: bool = False) -> int | None:
    while True:
        try:
            choice = input(prompt).strip()
            if not choice:
                return None
            idx = int(choice)
            if idx == 0 and allow_zero:
                return 0
            if 1 <= idx <= max_val:
                return idx
        except ValueError:
            pass
        print("  無效輸入，請重新輸入。")


def choose_from_list(items: list[str], title: str, allow_zero: bool = False) -> int | None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item}")
    if allow_zero:
        print("  [0] 不使用 / 跳過")
    return choose_int("\n請輸入編號: ", len(items), allow_zero=allow_zero)


def choose_multi(items: list[str], title: str) -> list[str]:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item}")
    print("  [0] 全部選取")
    while True:
        try:
            choice = input("\n請輸入編號（可多個以逗號分隔）: ").strip()
            if choice == "0":
                return list(items)
            indices = [int(x.strip()) for x in choice.split(",") if x.strip()]
            selected = [items[i-1] for i in indices if 1 <= i <= len(items)]
            if selected:
                return selected
        except (ValueError, IndexError):
            pass
        print("  無效輸入，請重新輸入。")


def step1() -> Path:
    """step1：從 workplace/ 選擇翻譯目標 Excel，並輸入語言代碼。"""
    workplace = _get_workplace()
    xlsx_files = list_excel_files(workplace)
    if not xlsx_files:
        print(f"\n錯誤：{workplace}/ 下沒有 Excel 檔案")
        print(f"請將翻譯目標 Excel 放入 {workplace}/ 後再執行。")
        input("\n按 Enter 關閉...")
        sys.exit(1)
    fnames = [f.name for f in xlsx_files]
    c = choose_from_list(fnames, f"請選擇目標 Excel 檔案（{workplace}/）：")
    if c is None:
        print("已取消。")
        input("\n按 Enter 關閉...")
        sys.exit(0)
    return xlsx_files[c - 1]


def step2(exclude_path: Path | None = None) -> tuple[Path | None, list[str] | None]:
    """step2：從 workplace/ 選擇術語庫 Excel。"""
    workplace = _get_workplace()
    xlsx_files = [f for f in list_excel_files(workplace)
                  if exclude_path is None or f.resolve() != exclude_path.resolve()]
    if not xlsx_files:
        inp = input(f"\n{workplace}/ 下沒有 Excel 檔案，輸入其他路徑或直接 Enter 跳過: ").strip()
        if inp:
            p = Path(inp)
            if p.exists():
                return p, None
        return None, None
    fnames = [f.name for f in xlsx_files]
    fnames.append("✨ 自動從目標 Excel 萃取（name/manual 工作表）")
    c = choose_from_list(fnames, "選擇術語庫 Excel（translation 有值的行即為術語）:", allow_zero=True)
    if c is None or c == 0:
        return None, None
    if c == len(fnames):
        return AUTO_GLOSSARY_SENTINEL, None
    gp = xlsx_files[c - 1]
    xls = pd.ExcelFile(gp)
    sheets = xls.sheet_names
    if len(sheets) == 1:
        print(f"  自動使用工作表: {sheets[0]}")
        return gp, sheets
    selected = choose_multi(sheets, "選擇哪些工作表作為術語來源：")
    return gp, selected


def step3(excel_path: Path) -> list[str]:
    """step3：選擇翻譯目標工作表。"""
    xls = pd.ExcelFile(excel_path)
    sheets = xls.sheet_names
    if len(sheets) == 1:
        return sheets
    return choose_multi(sheets, "選擇翻譯目標工作表：")


def step4(df_full: pd.DataFrame) -> pd.DataFrame:
    """step4：選擇翻譯範圍（全部未翻譯 / 前 N 條測試 / 指定行數）。"""
    untranslated_mask = df_full["translation"].isna() | (df_full["translation"].isnull())
    untranslated_count = int(untranslated_mask.sum())
    print(f"\n{SEP}")
    print("  選擇翻譯範圍")
    print(SEP)
    print(f"  [1] 全部未翻譯條目（共 {untranslated_count} 條）")
    print(f"  [2] 僅測試前 N 條")
    print(f"  [3] 指定行數範圍")
    while True:
        c = input("\n請選擇: ").strip()
        if c == "1":
            r = df_full[untranslated_mask].copy()
            print(f"  選取全部 {len(r)} 條未翻譯")
            return r
        elif c == "2":
            try:
                n = int(input("  請輸入 N: ").strip())
                idx = list(df_full.index[untranslated_mask][:n])
                r = df_full.loc[idx].copy()
                print(f"  選取前 {n} 條未翻譯")
                return r
            except ValueError:
                print("  無效數字")
        elif c == "3":
            try:
                rng = input("  請輸入行數範圍（如 100-500）: ").strip()
                parts = rng.split("-")
                s, e = int(parts[0]) - 1, int(parts[1])
                print(f"  選取行 {s+1} 到 {e}")
                return df_full.iloc[s:e].copy()
            except (ValueError, IndexError):
                print("  無效範圍")
        else:
            print("  無效輸入")


def confirm(excel_path: Path, glossary_path: Path | None,
            sheets: list[str], total_rows: int) -> bool:
    """顯示翻譯摘要並要求確認。"""
    print(f"\n{SEP}")
    print("  即將執行以下操作：")
    print(SEP)
    print(f"  目標: {excel_path}")
    if glossary_path == AUTO_GLOSSARY_SENTINEL:
        print(f"  術語庫: 自動萃取（name/manual 工作表）")
    else:
        print(f"  術語庫: {glossary_path if glossary_path else '無（僅內建 ADD_LIST）'}")
    print(f"  工作表: {', '.join(sheets)}")
    print(f"  翻譯條數: {total_rows}")
    print(SEP)
    return input("\n確認執行？(Y/n): ").strip().lower() != "n"


def find_existing_progress() -> dict | None:
    """掃描 workplace/_checkpoint/session.json，偵測未完成的翻譯進度。"""
    workplace = _get_workplace()
    sf = workplace / "_checkpoint" / "session.json"
    if sf.exists():
        try:
            session = json.loads(sf.read_text(encoding="utf-8"))
            session["_workplace"] = str(workplace)
            return session
        except Exception:
            pass
    return None


def prompt_resume(session: dict) -> bool:
    """顯示續傳提示。"""
    workplace = Path(session["_workplace"])
    backup = load_backup(str(workplace))
    completed = len(backup)
    total = session.get("total_selected", "?")
    excel_name = Path(session.get("excel_path", "?")).name

    print(f"\n{SEP}")
    print("  偵測到未完成的翻譯進度")
    print(SEP)
    print(f"  Excel: {excel_name}")
    print(f"  工作表: {session.get('sheet_name', '?')}")
    print(f"  進度: {completed}/{total} 條")
    glossary_path = session.get("glossary_path")
    if glossary_path == "__AUTO__":
        print(f"  術語庫: 自動萃取（name/manual 工作表）")
    else:
        print(f"  術語庫: {Path(glossary_path).name if glossary_path else '無'}")
    print(SEP)
    c = input("\n是否繼續上次的翻譯？(Y/n): ").strip().lower()
    return c != "n"


def main():
    print(SEP)
    print("      混合翻譯管線 v1.4")
    print(f"      工作目錄: {_get_workplace()}")
    print(SEP)

    # ── 續傳檢測 ──
    exist_session = find_existing_progress()
    if exist_session:
        if prompt_resume(exist_session):
            print("\n  繼續上次的翻譯...\n")
            overall_start = datetime.now()
            excel_path = Path(exist_session["excel_path"])
            sheet_name = exist_session["sheet_name"]
            glossary_path_str = exist_session.get("glossary_path")
            glossary_path = Path(glossary_path_str) if glossary_path_str else None
            selected_indices = set(exist_session.get("selected_indices", []))
            glossary_sheets = exist_session.get("glossary_sheets")
            workplace = _get_workplace()

            t0 = datetime.now()
            timestamp("載入術語庫...")
            if glossary_path_str == "__AUTO__":
                from glossary import auto_extract_glossary
                glossary = auto_extract_glossary(excel_path, workplace)
            else:
                glossary = load_glossary(glossary_path, glossary_sheets if glossary_path else None)
            elapsed(t0, "載入術語庫")
            print(f"  術語庫載入完成: {len(glossary)} 條")

            t1 = datetime.now()
            timestamp(f"讀取 {sheet_name}...")
            df_full = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
            total = len(df_full)
            print(f"    總條數: {total}")

            if selected_indices:
                mask = df_full.index.isin(selected_indices) & (
                    df_full["translation"].isna() | (df_full["translation"].isnull())
                )
                df = df_full[mask].copy()
                print(f"    還原選取範圍，剩餘未翻譯: {len(df)} 條")
            else:
                df = df_full[df_full["translation"].isna() | (df_full["translation"].isnull())].copy()
                print(f"    無法還原選取範圍（相容模式），未翻譯: {len(df)} 條")

            if len(df) == 0:
                print("  所有選取條目已完成，無需翻譯")
                delete_checkpoint_files(str(workplace))
                total_secs = (datetime.now() - overall_start).total_seconds()
                print(f"\n{SEP}")
                timestamp("管線執行完成")
                print(f"  總耗時: {total_secs:.1f} 秒")
                print(SEP)
                input("\n按 Enter 關閉...")
                return

            t2 = datetime.now()
            timestamp("模板參數化比對...")
            df = match_and_fill(df, glossary)
            matched = int((df["_status"] == "已處理").sum())
            elapsed(t2, "模板比對")
            print(f"    模板匹配完成: {matched} 條已處理")

            pending = int((df["translation"].isna() | (df["translation"] == "nan")).sum())
            timestamp(f"LLM 批次翻譯（待翻譯: {pending} 條）...")
            t3 = datetime.now()
            if pending > 0:
                df = llm_translate(df, glossary, str(workplace))
            else:
                print("    無需 LLM 翻譯")
            elapsed(t3, "LLM 翻譯")

            t4 = datetime.now()
            timestamp("術語強制後處理...")
            df, review_df = enforce(df, glossary, str(workplace))
            elapsed(t4, "術語強制後處理")

            df_full.update(df)
            out_path = workplace / f"{excel_path.stem}_translated_output.xlsx"
            timestamp(f"寫入輸出檔案 {out_path.name}...")
            df_full.to_excel(out_path, index=False)
            print(f"  輸出完成: {out_path}")

            delete_checkpoint_files(str(workplace))
            print(f"  已清除進度檔案")

            total_secs = (datetime.now() - overall_start).total_seconds()
            print(f"\n{SEP}")
            timestamp("管線執行完成")
            print(f"  總耗時: {total_secs:.1f} 秒")
            print(SEP)
            input("\n按 Enter 關閉...")
            return
        else:
            workplace = _get_workplace()
            delete_checkpoint_files(str(workplace))
            print("\n  已清除舊進度，開始新的翻譯。\n")

    # ── 全新翻譯路徑 ──
    excel_path = step1()
    workplace = _get_workplace()
    glossary_path, glossary_sheets = step2(exclude_path=excel_path)
    sheet_names = step3(excel_path)

    overall_start = datetime.now()
    t0 = datetime.now()
    timestamp("載入術語庫...")
    if glossary_path == AUTO_GLOSSARY_SENTINEL:
        from glossary import auto_extract_glossary
        glossary = auto_extract_glossary(excel_path, workplace)
    else:
        glossary = load_glossary(glossary_path, glossary_sheets)
    elapsed(t0, "載入術語庫")
    print(f"  術語庫載入完成: {len(glossary)} 條")

    for sheet_name in sheet_names:
        print(f"\n{SEP}")
        print(f"  處理工作表: {sheet_name}")
        print(SEP)

        t1 = datetime.now()
        timestamp(f"讀取 {sheet_name}...")
        df_full = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
        total = len(df_full)
        untranslated = int(df_full["translation"].isna().sum()) if "translation" in df_full.columns else total
        print(f"    總條數: {total}, 未翻譯: {untranslated}")
        if untranslated == 0:
            print(f"  {sheet_name} 全部已翻譯，跳過")
            continue

        df = step4(df_full)
        if len(df) == 0:
            print("  沒有符合條件的條目，跳過")
            continue

        if not confirm(excel_path, glossary_path, sheet_names, len(df)):
            print("  已取消。")
            input("\n按 Enter 關閉...")
            return

        save_session(str(workplace), {
            "excel_path": str(excel_path),
            "sheet_name": sheet_name,
            "glossary_path": str(glossary_path) if glossary_path else None,
            "glossary_sheets": glossary_sheets,
            "total_selected": len(df),
            "selected_indices": list(df.index),
            "timestamp": datetime.now().isoformat(),
        })

        t2 = datetime.now()
        timestamp("模板參數化比對...")
        df = match_and_fill(df, glossary)
        matched = int((df["_status"] == "已處理").sum())
        elapsed(t2, "模板比對")
        print(f"    模板匹配完成: {matched} 條已處理")

        pending = int((df["translation"].isna() | (df["translation"] == "nan")).sum())
        timestamp(f"LLM 批次翻譯（待翻譯: {pending} 條）...")
        t3 = datetime.now()
        if pending > 0:
            df = llm_translate(df, glossary, str(workplace))
        else:
            print("    無需 LLM 翻譯")
        elapsed(t3, "LLM 翻譯")

        t4 = datetime.now()
        timestamp("術語強制後處理...")
        df, review_df = enforce(df, glossary, str(workplace))
        elapsed(t4, "術語強制後處理")

        df_full.update(df)
        out_path = workplace / f"{excel_path.stem}_translated_output.xlsx"
        timestamp(f"寫入輸出檔案 {out_path.name}...")
        df_full.to_excel(out_path, index=False)
        print(f"  輸出完成: {out_path}")

    delete_checkpoint_files(str(workplace))
    print(f"  已清除進度檔案")

    total_secs = (datetime.now() - overall_start).total_seconds()
    print(f"\n{SEP}")
    timestamp("管線執行完成")
    print(f"  總耗時: {total_secs:.1f} 秒")
    print(SEP)
    input("\n按 Enter 關閉...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        input("\n按 Enter 關閉...")