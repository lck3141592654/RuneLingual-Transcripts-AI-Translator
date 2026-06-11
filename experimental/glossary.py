import re
import pandas as pd
from pathlib import Path

ADD_LIST: dict[str, str] = {
    "Old School RuneScape": "Old School RuneScape",
    "OSRS": "OSRS",
    "RuneLite": "RuneLite",
    "RuneLingual": "RuneLingual",
    "Lord Hosidius": "霍西迪乌斯领主", "Hosidius family": "霍西迪乌斯家族",
    "fairy tales": "童话故事",
    #"Zamorak": "薩莫拉克",
    #"Guthix": "古西斯",
    #"Armadyl": "阿馬戴爾",
    #"Bandos": "班多斯",
    #"Zaros": "薩羅斯",
    #"Seren": "塞倫",
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
                         , "Tomb", "Drew", "Entrance", "Fox", "Space"}

def _normalize_for_ignore(term: str) -> str:
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
    ignore_norm_set = {_normalize_for_ignore(t) for t in IGNORE_LIST}
    glossary = {
        k: v for k, v in glossary.items()
        if _normalize_for_ignore(k) not in ignore_norm_set
    }

    return glossary