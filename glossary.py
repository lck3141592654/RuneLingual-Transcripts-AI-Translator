import re
import pandas as pd
from pathlib import Path

# 供 find_term_spans 使用的通用 regex 快取
_re_exact_cache: dict = {}
_re_word_cache = re.compile(r"[a-z']+")

ADD_LIST: dict[str, str] = {
    "Old School RuneScape": "Old School RuneScape",
    "OSRS": "OSRS",
    "RuneLite": "RuneLite",
    "RuneLingual": "RuneLingual",
    "Lord Hosidius": "霍西迪乌斯领主", "Hosidius family": "霍西迪乌斯家族", "Anna Sinclair": "安娜.辛克莱尔",
    "fairy tales": "童话故事", " Shayzien Army": "谢兹恩城卫军", "Phoenix Gang": "凤凰帮",
    "Kourend Royal Guard": "库兰德皇家卫队", "Old School Leagues": "Old School 联赛", "Great Conch": "巨螺岛",
    "Lord Shayzien": "谢兹恩领主", "Deadman mode": "死亡模式", "Piscatoris Fishing Colony": "皮斯卡托里斯渔村",
    "Lord Arceuus": "阿西乌斯领主", "Historical Archive": "历史档案室", "White Wolf Mountain": "白狼山",
    "Kourend Council": "库兰德议会", "Runecrafting altar": "符石祭坛", "Runecraft altar": "符石祭坛",
    "River Molch": "莫尔奇河", "Proselyte Temple Knight": "皈依者圣殿骑士", "Brimhaven Agility Arena": "布尔哈文敏捷竞技场",
    "Arceuus Library": "阿西乌斯图书馆", "Saradomin": "萨拉多明", "Guthix": "古斯", "Zamorak": "扎莫拉克",
    "Armadyl": "阿玛杜尔", "Bandos": "班多斯", "Zaros": "扎罗斯", "Tumeken": "图梅肯",
    "Elidinis": "伊莉迪尼斯", "Jas": "贾斯", "Marimbo": "马里姆博", "Ralos": "拉洛斯",
    "Ranul": "拉努尔", "Kayzertief": "凯泽提夫", "Xeric": "泽里克", "Xerician": "泽里克西亚",
    "Iknami": "朋友", "Kuani": "太好了", "Nilsal": "你好", "Timoiva": "再见",
    "unranked Tournament": "非排位赛", "Old One": "古老者", "bank pin": "银行pin码", "Lady Lumbridge": "仑桥夫人号",
}

IGNORE_LIST: set[str] = {"Toolkit", "Vial", "Bones", "Burnt bones", "Cup of tea", "Message", "Book"
                         , "Translation book", "Twigs", "Knife", "Plank", "Rock", "Chisel"
                         , "Barrel", "Cake", "Watch", "Chart", "Journal"
                         , "Man", "Fremennik", "Branch", "Manual", "Stool"
                         , "Monkey", "Torso", "Arms", "Legs", "Letter"
                         , "Corpse of woman", "Mud", "Pole", "Rake", "Chores"
                         , "Sand", "Sandy hand", "Roll", "Item", "Dummy"
                         , "Hoop", "Pond", "Tree", "Plant", "Small fern"
                         , "Fern", "Bush", "The desert", "Rug", "Saw"
                         , "Footprint", "A pattern", "A container", "No eggs", "Hair"
                         , "Documents", "Run", "Artefact", "Spear", "Carpet"
                         , "Fungi", "Me", "Stick", "Ash", "? ? ? ?"
                         , "Red", "Will", "Symbol", "Zero", "One"
                         , "Two", "Three", "Four", "Five", "Six"
                         , "Seven", "Eight", "Nine", "Dead Body", "Death"
                         , "Pack", "Woman", "Eye", "Corpses", "Remnant"
                         , "Beam", "Shadow", "Plants", "REPLACE ME", "Rain"
                         , "Head", "Body", "Warp", "Gateway", "Bags"
                         , "Void", "Spike", "Pillow", "A Goblin", "Droppings"
                         , "Extremity", "Surface", "Breach", "Display dial", "Debug Man"
                         , "Debug Woman", "Jug", "Art", "Smith", "Gem"
                         , "Well", "pit", "Other", "Sign", "Notice"
                         , "Wave", "Stand", "Note", "Tap", "Current"
                         , "Start", "Egg", "Mechanism", "Poison", "Fire"
                         , "Display", "Don't Know What", "Black", "Nothing", "Cleaner"
                         , "Charge", "Support", "River", "Handle", "Scout"
                         , "Port", "Target", "Cross", "Font", "Arrows"
                         , "Flowers", "Sails", "Leaflets", "Crack", "Stop!"
                         , "Leaves", "Ed", "Safe", "Mark", "Gene"
                         , "Chest", "History", "Crystal", "Dragon", "Passage"
                         , "Me?", "Steps", "Child", "Throne", "Bone"
                         , "Grip", "Mess", "Locked", "Hunter", "Harness"
                         , "Suspect", "My life", "House", "Stake", "level"
                         , "Prisoner", "Light", "Tracks", "Present", "Eyes"
                         , "Nest", "Bars", "Key", "Shell", "Old man"
                         , "Information", "Sacrifice", "Picture", "Reach", "Giant"
                         , "Edge", "Dad", "White", "Vial of water", "Feather"
                         , "Sieve", "Gossip", "Lift", "Till", "Mirror"
                         , "Dust", "Hanging", "Door", "Trees", "Experiment"
                         , "Dream", "Our lives", "Paper", "Boy", "girl"
                         , "Piles", "List", "Pages", "Study", "Opening"
                         , "Gas", "Gold", "Path", "Core", "Shot"
                         , "Fingers", "Gate", "Boot", "Stocks", "Cook"
                         , "Tomb", "Drew", "Entrance", "Fox", "Space"
                         , "Feud, The", "Golem, The", "A", "B", "C"
                         , "D", "E", "F", "H", "G"
                         , "I", "J", "K", "L", "M"
                         , "N", "O", "P", "Q", "R"
                         , "S", "T", "U", "V", "W"
                         , "X", "Y", "Z", "In Progress", "Not Started"
                         , "Completed", "Intermediate", "Experienced", "Master", "Very Short"
                         , "Short", "Medium", "Long", "Very Long", "Camelot"
                         , "Monkeys", "Rats", "Spiders", "Birds", "Cows"
                         , "Scorpions", "Bats", "Search", "Tail", "Chuck"
                         , "Ship", "Hole", "Plunder", "Posts", "Supplies"
                         , "Entry", "Shorts", "Mercy", "Birds", "Staff"
                         , "Directions", "Circle", "Stone", "Trap", "Carving"
                         , "Floor", "Dishes", "Orange", "Table", "Grave"
                         , "Nick", "A corpse", "Spirit", "Flames", "Shark"
                         , "Cages", "Wood", "Frame", "Heat", "Pots"
                         , "Green", "Wool", "Hammer", "Standard", "Box"
                         , "Bricks", "not", "be", "The stuff", "Casual"
                         , "brain", "Boards", "Mime", "a wall", "switch"
                         , "pin", "web", "file", "remains", "bottle"
                         , "special", "markings", "file", "remains", "bottle"
                         , 'A crack', 'A rock', 'Container', 'Corpse', 'Desert', 'Goblin', 'Goblins', 'Rocks', 'The rocks', 'Wall'}

def normalize_term(term: str) -> str:
    """將術語歸一化，使 IGNORE_LIST 能同時匹配單數和複數型"""
    t = term.lower().strip()
    # -ves → f (wolves → wolf)
    t = re.sub(r"(?i)(?<=[a-z])ves$", "f", t)
    # -ies → y (ponies → pony)
    t = re.sub(r"(?i)(?<=[a-z])ies$", "y", t)
    # -es → empty (boxes → box, eggs → egg)
    t = re.sub(r"(?i)(?<=[a-z])es$", "", t)
    # -s → empty (cats → cat) 要先做 -es 再做 -s
    t = re.sub(r"(?i)(?<=[a-z])s$", "", t)
    return t.strip()


def build_relevance_context(text_l: str) -> tuple[set, dict]:
    """預先建立文本的詞集合與「單數 → 其複數形態」對照，供大量術語批次匹配共用。"""
    words = set(_re_word_cache.findall(text_l))
    plural_map: dict[str, set] = {}
    for w in words:
        for cand in _plural_candidates(w):
            plural_map.setdefault(cand, set()).add(w)
    return words, plural_map


def _plural_candidates(word: str) -> set:
    """回傳 word 可能的單數形態（含自身），例如 boxes → {boxes, box}、buses → {buses, bus}。"""
    cands = {word}
    if word.endswith("ies") and len(word) > 4:
        cands.add(word[:-3] + "y")
    if word.endswith("ves") and len(word) > 4:
        cands.add(word[:-3] + "f")
        cands.add(word[:-3] + "fe")
    if word.endswith("es") and len(word) > 3:
        cands.add(word[:-2])
    if word.endswith("s") and len(word) > 1:
        cands.add(word[:-1])
    return cands


def find_term_spans(term: str, text: str, ctx: tuple[set, dict] | None = None) -> list[tuple[int, int]]:
    """回傳術語在文本中出現的 span 清單（詞邊界）。

    只接受兩種情況：
    1. 術語原樣（小寫化後）出現在文本中；
    2. 文本詞是術語的「真正的複數/變形」（例如 boxes 對應 Box，demons 對應 demon），
       避免 News 誤匹配 new、The Face 誤匹配 face 這類歸一化誤報。
    """
    if not term or not text:
        return []
    term_l = term.lower().strip()
    text_l = text.lower()
    pat = _re_exact_cache.get(term_l)
    if pat is None:
        pat = re.compile(r"(?<![a-z'])" + re.escape(term_l) + r"(?![a-z'])")
        _re_exact_cache[term_l] = pat
    if ctx is None:
        ctx = build_relevance_context(text_l)
    words, plural_map = ctx
    is_multi = " " in term_l
    if is_multi:
        parts = term_l.split()
        # 詞集合預篩：任一詞（或其變形）不在文本中就直接跳過
        for w in parts:
            if w in words:
                continue
            if not any(inf in words for inf in plural_map.get(w, ())):
                return []
    else:
        if term_l not in words and not any(
            inf in words for inf in plural_map.get(term_l, ())
        ):
            return []
    # 原樣匹配（詞邊界）
    spans = [m.span() for m in pat.finditer(text_l)]
    if spans:
        return spans
    # 無原樣匹配：多字詞以位置比對，單字詞以「文字詞是否為術語的複數」比對
    if is_multi:
        return _find_multi_word_span(parts, text_l)
    for w in plural_map.get(term_l, ()):
        pos = text_l.find(w)
        if pos >= 0:
            return [(pos, pos + len(w))]
    return []


def _find_multi_word_span(parts: list, text_l: str) -> list[tuple[int, int]]:
    """以位置比對找出多字詞術語（詞與詞之間只能有空白）的實際 span。"""
    first = parts[0]
    start = 0
    while True:
        pos = text_l.find(first, start)
        if pos < 0:
            return []
        cursor = pos + len(first)
        ok = True
        for w in parts[1:-1]:
            nxt = text_l.find(w, cursor)
            if nxt < 0 or text_l[cursor:nxt].strip():
                ok = False
                break
            cursor = nxt + len(w)
        if not ok:
            return []
        # 最後一詞：原樣或帶複數後綴，且與前一詞之間只能有空白
        last = parts[-1]
        found = False
        for suffix in ("", "s", "es", "ies", "ves"):
            candidate = last + suffix
            nxt = text_l.find(candidate, cursor)
            if nxt >= 0 and not text_l[cursor:nxt].strip():
                cursor = nxt + len(candidate)
                found = True
                break
        if found:
            return [(pos, cursor)]
        start = pos + 1


def _is_plural_like(word: str) -> bool:
    """粗略判斷一個詞是否為複數形態（以 s/es/ies/ves 結尾）。"""
    return word.endswith(("s", "es", "ies", "ves"))


def load_glossary(
    glossary_path: str | Path | None,
    sheet_names: list[str] | None = None,
) -> dict[str, str]:
    glossary: dict[str, str] = {}
    if glossary_path is not None:
        path = Path(glossary_path)
        if path.exists():
            with pd.ExcelFile(path) as xls:
                sheets = sheet_names if sheet_names else xls.sheet_names
                for sn in sheets:
                    if sn not in xls.sheet_names:
                        continue
                    df = pd.read_excel(path, sheet_name=sn, dtype=str)
                    if "english" in df.columns and "translation" in df.columns:
                        for _, row in df.iterrows():
                            eng_raw = row["english"]
                            if pd.isna(eng_raw):
                                continue
                            eng = str(eng_raw).strip()
                            if not eng:
                                continue
                            trans = row["translation"]
                            if pd.notna(trans) and str(trans).strip():
                                chn = str(trans).strip()
                                if chn.lower() != "nan":
                                    glossary[eng] = chn
    for eng, chn in ADD_LIST.items():
        glossary[eng] = chn

    # 用歸一化匹配來過濾 IGNORE_LIST（捕獲單數/複數/大小寫）
    ignore_norm_set = {normalize_term(t) for t in IGNORE_LIST}
    glossary = {
        k: v for k, v in glossary.items()
        if normalize_term(k) not in ignore_norm_set
    }

    return glossary

def auto_extract_glossary(
    target_excel_path: str | Path,
    output_dir: str | Path,
) -> dict[str, str]:
    """自動從翻譯目標 Excel 的 name/manual 工作表萃取術語庫。

    篩選條件：
    - name 工作表：sub_category ∈ {item, menu, npc, object}
    - manual 工作表：sub_category ∈ {activity, location, quest, slayer_mob}
    - translation 不為空且不等於 english
    """
    target_path = Path(target_excel_path)

    glossary: dict[str, str] = {}
    review_rows = []

    name_categories = {"item", "menu", "npc", "object"}
    manual_categories = {"activity", "location", "quest", "slayer_mob"}

    with pd.ExcelFile(target_path) as xls:
        for sheet_name, valid_cats in [("name", name_categories), ("manual", manual_categories)]:
            if sheet_name not in xls.sheet_names:
                print(f"  工作表 '{sheet_name}' 不存在，跳過")
                continue
            df = pd.read_excel(target_path, sheet_name=sheet_name, dtype=str)
            if "sub_category" not in df.columns:
                print(f"  工作表 '{sheet_name}' 缺少 sub_category 欄位，跳過")
                continue
            if "english" not in df.columns or "translation" not in df.columns:
                print(f"  工作表 '{sheet_name}' 缺少 english 或 translation 欄位，跳過")
                continue

            mask = df["sub_category"].str.strip().str.lower().isin(valid_cats)
            filtered = df[mask]
            print(f"  從 '{sheet_name}' 篩出 {len(filtered)} 行")

            for _, row in filtered.iterrows():
                eng_raw = row.get("english")
                if pd.isna(eng_raw):
                    continue
                eng = str(eng_raw).strip()
                if not eng:
                    continue
                trans = row.get("translation")

                if pd.isna(trans):
                    continue
                trans_str = str(trans).strip()
                if not trans_str or trans_str.lower() == "nan":
                    continue
                if trans_str == eng:
                    continue

                glossary[eng] = trans_str
                review_rows.append({
                    "english": eng,
                    "translation": trans_str,
                    "category": str(row.get("category", "")),
                    "sub_category": str(row.get("sub_category", "")),
                })

    # 合併 ADD_LIST（覆蓋相同 key）
    for eng, chn in ADD_LIST.items():
        glossary[eng] = chn

    # IGNORE_LIST 歸一化過濾
    ignore_norm_set = {normalize_term(t) for t in IGNORE_LIST}
    glossary = {
        k: v for k, v in glossary.items()
        if normalize_term(k) not in ignore_norm_set
    }

    # 輸出審查檔案
    output_path = Path(output_dir) / "auto_glossary_for_review.xlsx"
    if review_rows:
        review_df = pd.DataFrame(review_rows)
        review_df.to_excel(output_path, index=False)
        print(f"  自動術語庫審查檔已寫入: {output_path} ({len(review_df)} 條)")
    else:
        review_df = pd.DataFrame(columns=["english", "translation", "category", "sub_category"])
        review_df.to_excel(output_path, index=False)
        print(f"  自動萃取未產生任何術語條目，空審查檔已建立: {output_path}")

    return glossary