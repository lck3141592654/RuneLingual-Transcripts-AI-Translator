#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from glossary import load_glossary
from tm_matcher import match_and_fill
from llm_translator import translate_all as llm_translate
from enforcer import enforce


SEP = "=" * 60


def timestamp(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  [{now}] {msg}")


def elapsed(start: datetime, label: str):
    secs = (datetime.now() - start).total_seconds()
    print(f"  [{label}] 耗時: {secs:.1f} 秒")


def list_draft_langs() -> list[str]:
    draft_dir = Path(__file__).parent.parent.parent / "draft"
    if not draft_dir.exists():
        return []
    return sorted([d.name for d in draft_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])


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


def step1() -> tuple[Path, str]:
    langs = list_draft_langs()
    if not langs:
        print(f"\n錯誤：draft/ 下沒有子目錄")
        input("\n按 Enter 關閉...")
        sys.exit(1)
    c = choose_from_list(langs, "請選擇語言（目錄名稱即為語言）：")
    if c is None:
        print("已取消。")
        input("\n按 Enter 關閉...")
        sys.exit(0)
    lang = langs[c - 1]
    draft_dir = Path(__file__).parent.parent.parent / "draft" / lang
    xlsx_files = list_excel_files(draft_dir)
    if not xlsx_files:
        print(f"\n錯誤：draft/{lang}/ 下沒有 Excel 檔案")
        input("\n按 Enter 關閉...")
        sys.exit(1)
    fnames = [f.name for f in xlsx_files]
    c2 = choose_from_list(fnames, f"請選擇目標 Excel 檔案（draft/{lang}/）：")
    if c2 is None:
        print("已取消。")
        input("\n按 Enter 關閉...")
        sys.exit(0)
    return xlsx_files[c2 - 1], lang


def step2(excel_path: Path) -> tuple[Path | None, list[str] | None]:
    xlsx_files = list_excel_files(excel_path.parent)
    if not xlsx_files:
        inp = input("\n沒有 Excel 檔案，輸入其他路徑或直接 Enter 跳過: ").strip()
        if inp:
            p = Path(inp)
            if p.exists():
                return p, None
        return None, None
    fnames = [f.name for f in xlsx_files]
    c = choose_from_list(fnames, "選擇術語庫 Excel（translation 有值的行即為術語）:", allow_zero=True)
    if c is None or c == 0:
        return None, None
    gp = xlsx_files[c - 1]
    xls = pd.ExcelFile(gp)
    sheets = xls.sheet_names
    if len(sheets) == 1:
        print(f"  自動使用工作表: {sheets[0]}")
        return gp, sheets
    selected = choose_multi(sheets, "選擇哪些工作表作為術語來源：")
    return gp, selected


def step3(excel_path: Path) -> list[str]:
    xls = pd.ExcelFile(excel_path)
    sheets = xls.sheet_names
    if len(sheets) == 1:
        return sheets
    return choose_multi(sheets, "選擇翻譯目標工作表：")


def step4(df_full: pd.DataFrame) -> pd.DataFrame:
    untranslated_mask = df_full["translation"].isna() | (df_full["translation"].isnull())
    untranslated_count = int(untranslated_mask.sum())
    total = len(df_full)
    print(f"\n{SEP}")
    print(f"  選擇翻譯範圍")
    print(SEP)
    print(f"  總條數: {total}, 未翻譯: {untranslated_count}")
    print("  [1] 全部未翻譯條目")
    print("  [2] 前 N 條未翻譯（測試用）")
    print("  [3] 指定行數範圍（如 100-500）")
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


def confirm(excel_path: Path, lang: str, glossary_path, sheets: list[str], total_rows: int):
    print(f"\n{SEP}")
    print("  即將執行以下操作：")
    print(SEP)
    print(f"  目標: {excel_path}")
    print(f"  語言: {lang}")
    print(f"  術語庫: {glossary_path if glossary_path else '無（僅內建 ADD_LIST）'}")
    print(f"  工作表: {', '.join(sheets)}")
    print(f"  翻譯條數: {total_rows}")
    print(SEP)
    return input("\n確認執行？(Y/n): ").strip().lower() != "n"


def main():
    overall_start = datetime.now()
    print(SEP)
    print("      混合翻譯管線 v1.3")
    print(SEP)

    excel_path, lang = step1()
    output_dir = excel_path.parent
    glossary_path, glossary_sheets = step2(excel_path)
    sheet_names = step3(excel_path)

    t0 = datetime.now()
    timestamp("載入術語庫...")
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

        if not confirm(excel_path, lang, glossary_path, [sheet_name], len(df)):
            print("  已取消。")
            continue

        # ── 階段 2：模板比對 ──
        t2 = datetime.now()
        timestamp("模板參數化比對...")
        df = match_and_fill(df, glossary)
        matched = int((df["_status"] == "已處理").sum())
        elapsed(t2, "模板比對")
        print(f"    模板匹配完成: {matched} 條已處理")

        # ── 階段 3：LLM 翻譯 ──
        pending = int((df["translation"].isna() | (df["translation"] == "nan")).sum())
        timestamp(f"LLM 批次翻譯（待翻譯: {pending} 條）...")
        t3 = datetime.now()
        if pending > 0:
            df = llm_translate(df, glossary, output_dir)
        else:
            print("    無需 LLM 翻譯")
        elapsed(t3, "LLM 翻譯")

        # ── 階段 4：術語強制 ──
        t4 = datetime.now()
        timestamp("術語強制後處理...")
        df, review_df = enforce(df, glossary, output_dir)
        elapsed(t4, "術語強制後處理")

        # 更新原始 DataFrame
        df_full.update(df)

        # 輸出：使用來源檔案名加 _translated_output 後綴
        out_path = output_dir / f"{excel_path.stem}_translated_output.xlsx"
        timestamp(f"寫入輸出檔案 {out_path.name}...")
        df_full.to_excel(out_path, index=False)
        print(f"  輸出完成: {out_path}")

    # ── 清理多餘檔案 ──
    progress_file = output_dir / "progress.json"
    if progress_file.exists():
        os.remove(str(progress_file))
        print(f"  已清除: progress.json")

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