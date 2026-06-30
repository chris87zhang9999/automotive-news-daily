"""Automotive keyword filter + multi-language priority scoring."""
import re
from src.schemas import NewsItem, Priority

_HTML_RE = re.compile(r"<[^>]+>")

LI_AUTO_VARIANTS = [
    "理想汽车", "理想", "aito", "li auto", "lixiang",
    "лисян", "ли сян", "리샹", "リシャン", "ليكسيانغ",
]

# Each entry is (keyword_lowercase, display_name).
# keyword is matched against lowercased text; display_name is stored in item.brand.
CN_BRANDS: list[tuple[str, str]] = [
    ("比亚迪", "BYD"), ("byd", "BYD"),
    ("蔚来", "NIO"), ("nio", "NIO"),
    ("小鹏", "XPeng"), ("xpeng", "XPeng"),
    ("吉利", "Geely"), ("geely", "Geely"),
    ("问界", "AITO"), ("华为汽车", "Huawei Auto"),
    ("长城", "GWM"), ("哈弗", "Haval"),
    ("奇瑞", "Chery"), ("chery", "Chery"),
    ("长安", "Changan"),
    ("mg motor", "MG"), ("mg zs", "MG"), ("mg4", "MG"), ("mg5", "MG"), ("mg6", "MG"),
    ("上汽", "SAIC"), ("saic", "SAIC"),
    ("零跑", "Leapmotor"), ("leapmotor", "Leapmotor"),
    ("岚图", "Voyah"), ("voyah", "Voyah"),
    ("极氪", "Zeekr"), ("zeekr", "Zeekr"),
    ("深蓝", "Deepal"),
    ("仰望", "Yangwang"),
    ("方程豹", "Fang Cheng Bao"),
    ("smart #", "Smart"), ("smart automobile", "Smart"),
    ("坦克", "Tank"), ("tank suv", "Tank"), ("tank 300", "Tank"), ("tank 500", "Tank"),
]

# Flat keyword list for fast membership checks
_CN_BRAND_KEYS = [kw for kw, _ in CN_BRANDS]

# Short English tokens that appear as substrings of common words — require word-boundary match.
# "nio" appears in "senior", "companion", "opinion", "pinion", "union", etc.
_WHOLE_WORD_BRAND_KEYS: frozenset[str] = frozenset({"nio", "byd"})


def _brand_in_text(text: str, keyword: str) -> bool:
    if keyword in _WHOLE_WORD_BRAND_KEYS:
        return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))
    return keyword in text

QUALITY_VARIANTS = [
    "召回", "recall", "rückruf", "rappel", "отзыв",
    "استدعاء", "缺陷", "安全隐患", "故障", "投诉",
    "quality issue", "defect", "safety alert", "investigation",
    "probe", "nhtsa", "samr", "rapex", "tsrc",
]

AUTO_GENERIC = [
    "汽车", "electric vehicle", " ev ", "car", " auto ", "vehicle",
    "sedan", "suv", "pickup", "truck", "hybrid", "battery",
    "charging", "range", "motor", "fahrzeug", "voiture",
    "автомобиль", "سيارة", "รถยนต์", "xe hơi",
    "tesla", "volkswagen", "toyota", "bmw", "mercedes", "ford",
    "gm ", "general motors", "honda", "hyundai", "kia",
]

def _text(item: NewsItem) -> str:
    raw = _HTML_RE.sub(" ", item.raw_text)
    return (item.title + " " + raw).lower()

def _matches_any(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)

def is_automotive(item: NewsItem) -> bool:
    text = _text(item)
    all_kw = LI_AUTO_VARIANTS + _CN_BRAND_KEYS + QUALITY_VARIANTS + AUTO_GENERIC
    return _matches_any(text, all_kw)

def assign_priority(item: NewsItem) -> NewsItem:
    text = _text(item)
    is_quality = _matches_any(text, QUALITY_VARIANTS)
    is_li_auto = _matches_any(text, LI_AUTO_VARIANTS)
    is_cn = any(_brand_in_text(text, kw) for kw in _CN_BRAND_KEYS)

    if is_li_auto and is_quality:
        item.priority = "P0"
        item.brand = "Li Auto"
    elif is_li_auto:
        item.priority = "P1"
        item.brand = "Li Auto"
    elif is_cn:
        item.priority = "P2"
        for brand_kw, display_name in CN_BRANDS:
            if _brand_in_text(text, brand_kw):
                item.brand = display_name
                break
    else:
        item.priority = "P3"
    return item

_PRIORITY_ORDER: dict[Priority, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

def filter_and_prioritize(items: list[NewsItem]) -> list[NewsItem]:
    filtered = [assign_priority(item) for item in items if is_automotive(item)]
    return sorted(filtered, key=lambda x: _PRIORITY_ORDER[x.priority])
