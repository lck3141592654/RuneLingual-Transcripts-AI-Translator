import re
import pandas as pd
from glossary import normalize_term

TEMPLATES: list[dict] = [
    # ═══════════════════════════════════════════
    #  模板使用說明
    #  {0} {1} {2}... = pattern 中第 1、2、3... 個 (.+?) 的翻譯
    #  可任意排列順序來調整語序，相容 {0} 也相容 {}
    #  注意：所有捕獲的參數都必須在術語庫中，
    #        模板才會套用，否則交給 LLM。
    # ═══════════════════════════════════════════

    # ─── 單變量（語序一致，{0} 或 {} 皆可） ───
    # {"pattern": r"I can carry (.+) for you\.",     "template": "我可以为你携带{0}。"},
    # {"pattern": r"Welcome to (.+)\.",              "template": "欢迎来到{0}。"},
    # {"pattern": r"Your task is to kill (.+)\.",    "template": "你的任务是杀死{0}。"},
    # {"pattern": r"Talk to (.+)\.",                 "template": "与{0}交谈。"},
    # {"pattern": r"Search (.+)\.",                  "template": "搜索{0}。"},

    # ─── 多變量（用 {0}{1} 調整語序） ───
    # 原文：kill X in Y → {0}=X(target), {1}=Y(location)
    # {"pattern": r"Your task is to kill (.+?) in (.+?)\.", "template": "你的任务是去{1}杀死{0}。"},
    # 原文：Give X to Y → {0}=X(item), {1}=Y(recipient)
    # {"pattern": r"Give (.+?) to (.+?)\.",               "template": "把{0}交给{1}。"},
    # 原文：Travel from X to Y → {0}=X(from), {1}=Y(to)
    # {"pattern": r"Travel from (.+?) to (.+?)\.",        "template": "从{0}旅行到{1}。"},
    # 原文：Use X on Y → {0}=X(item), {1}=Y(target)
    # {"pattern": r"Use (.+?) on (.+?)\.",                "template": "在{1}上使用{0}。"},
]

def match_and_fill(df: pd.DataFrame, glossary: dict) -> pd.DataFrame:
    df = df.copy()
    df["_status"] = "\u5f85 LLM"
    df["translation"] = df.get("translation", pd.Series([None] * len(df)))
    for idx, row in df.iterrows():
        english = str(row["english"])
        if not english or english.lower() == "nan":
            continue
        for tmpl in TEMPLATES:
            m = re.match(tmpl["pattern"], english, re.IGNORECASE)
            if m:
                params = [g for g in m.groups() if g]
                all_in_glossary = True
                translated_params = []
                for p in params:
                    norm_p = normalize_term(p)
                    if norm_p in glossary:
                        translated_params.append(glossary[norm_p])
                    elif p in glossary:
                        translated_params.append(glossary[p])
                    else:
                        all_in_glossary = False
                        break
                if all_in_glossary:
                    translated = tmpl["template"]
                    for i, tp in enumerate(translated_params):
                        translated = translated.replace("{" + str(i) + "}", tp)
                    df.at[idx, "translation"] = translated
                    df.at[idx, "_status"] = "\u5df2\u8655\u7406"
                    break
    return df
