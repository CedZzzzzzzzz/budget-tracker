import json
import re
from pathlib import Path

CATEGORIES_PATH = Path(__file__).resolve().parent.parent / "shared" / "categories.json"
with CATEGORIES_PATH.open(encoding="utf-8") as handle:
    CATEGORIES_DATA = json.load(handle)

CATEGORIES = CATEGORIES_DATA["categories"]
CATEGORY_LABELS = CATEGORIES_DATA["labels"]
CATEGORY_KEYWORDS = CATEGORIES_DATA["keywords"]
CATEGORY_PRIORITY = CATEGORIES_DATA["priority"]


def tokenize(lower):
    return set(re.findall(r"[a-z0-9]+", lower))


def match_user_rule(lower, tokens, pattern):
    if " " in pattern or "-" in pattern:
        return pattern in lower
    return pattern in tokens or pattern == lower


def categorize_item(name: str, user_rules=None) -> str:
    lower = (name or "").lower().strip()
    if not lower:
        return "other"

    tokens = tokenize(lower)
    if user_rules:
        for rule in user_rules:
            pattern = (rule.get("pattern") or "").lower().strip()
            category = rule.get("category")
            if not pattern or category not in CATEGORIES:
                continue
            if match_user_rule(lower, tokens, pattern):
                return category

    for category in CATEGORY_PRIORITY:
        for kw in CATEGORY_KEYWORDS.get(category, []):
            if " " in kw or "-" in kw:
                if kw in lower:
                    return category
            elif kw in tokens:
                return category
    return "other"


def extract_learn_patterns(name: str):
    lower = (name or "").lower().strip()
    if not lower:
        return []
    patterns = {lower}
    for token in tokenize(lower):
        if len(token) >= 3:
            patterns.add(token)
    return sorted(patterns, key=len, reverse=True)
