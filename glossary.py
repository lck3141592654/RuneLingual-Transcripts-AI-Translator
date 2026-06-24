import re
import pandas as pd
from pathlib import Path

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

IGNORE_LIST: set[str] = set()
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
                         , "special", "markings", "file", "remains", "bottle"}

def normalize_term(term: str) -> str:
    """將術語歸一化，使 IGNORE_LIST 能同時匹配單數和複數型"""
    t = term.lower().strip()
    t = re.sub(r"^(a|an|the)\s+", "", t)
    # -ves → f (wolves → wolf)
    t = re.sub(r"(?i)(?<=[a-z])ves$", "f", t)
    # -ies → y (ponies → pony)
    t = re.sub(r"(?i)(?<=[a-z])ies$", "y", t)
    # -es → empty (boxes → box, eggs → egg)
    t = re.sub(r"(?i)(?<=[a-z])es$", "", t)
    # -s → empty (cats → cat) 要先做 -es 再做 -s
    t = re.sub(r"(?i)(?<=[a-z])s$", "", t)
    return t.strip()


def load_glossary(
    glossary_path: str | Path | None,
    sheet_names: list[str] | None = None,
) -> dict[str, str]:
    glossary: dict[str, str] = {}
    if glossary_path is not None:
        path = Path(glossary_path)
        if path.exists():
            xls = pd.ExcelFile(path)
            sheets = sheet_names if sheet_names else xls.sheet_names
            for sn in sheets:
                if sn not in xls.sheet_names:
                    continue
                df = pd.read_excel(path, sheet_name=sn, dtype=str)
                if "english" in df.columns and "translation" in df.columns:
                    for _, row in df.iterrows():
                        eng = str(row["english"]).strip()
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
    import pandas as pd
    from pathlib import Path

    target_path = Path(target_excel_path)
    xls = pd.ExcelFile(target_path)

    glossary: dict[str, str] = {}
    review_rows = []

    name_categories = {"item", "menu", "npc", "object"}
    manual_categories = {"activity", "location", "quest", "slayer_mob"}

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
            eng = str(row.get("english", "")).strip()
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