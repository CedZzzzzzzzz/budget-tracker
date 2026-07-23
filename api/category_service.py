import re
import unicodedata

from api.categorize import (
    CATEGORIES,
    CATEGORY_KEYWORDS,
    CATEGORY_LABELS,
    CATEGORY_PRIORITY,
    CATEGORIES_DATA,
    match_user_rule,
    tokenize,
)


CATEGORY_DESCRIPTIONS = CATEGORIES_DATA.get("descriptions", {})
GENERIC_TOKENS = frozenset({
    "and", "buy", "item", "items", "misc", "order", "paid", "payment",
    "purchase", "receipt", "shop", "store", "the", "total",
})


def normalize_text(value):
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = re.sub(r"[\x00-\x1f\x7f]", " ", normalized)
    return " ".join(normalized.split())


def build_category_context(custom_categories=None):
    context = []
    for slug in CATEGORIES:
        context.append({
            "slug": slug,
            "label": CATEGORY_LABELS.get(slug, slug),
            "description": CATEGORY_DESCRIPTIONS.get(slug, ""),
            "keywords": list(CATEGORY_KEYWORDS.get(slug, [])),
            "kind": "built_in",
        })
    for category in custom_categories or []:
        slug = normalize_text(category.get("slug")).replace(" ", "_")
        if not slug or any(row["slug"] == slug for row in context):
            continue
        context.append({
            "slug": slug,
            "label": str(category.get("label") or slug).strip(),
            "description": str(category.get("description") or "").strip(),
            "keywords": [
                normalize_text(keyword)
                for keyword in category.get("keywords") or []
                if normalize_text(keyword)
            ],
            "kind": "custom",
        })
    return context


def score_phrase(lower, tokens, phrase):
    candidate = normalize_text(phrase)
    if not candidate:
        return 0.0
    if " " in candidate or "-" in candidate:
        if candidate in lower:
            return 9.0 + min(len(candidate.split()), 4) * 0.5
        return 0.0
    return 3.0 if candidate in tokens else 0.0


def classify_category(
    text,
    user_rules=None,
    category_context=None,
    provider_category=None,
):
    lower = normalize_text(text)
    context = category_context or build_category_context()
    allowed = {row["slug"] for row in context}
    if not lower:
        return {
            "category": "other" if "other" in allowed else next(iter(allowed), "other"),
            "confidence": 0.0,
            "source": "fallback",
            "needs_review": True,
        }

    tokens = tokenize(lower)
    ranked_rules = sorted(
        user_rules or [],
        key=lambda rule: int(rule.get("hit_count") or 0),
        reverse=True,
    )
    for rule in ranked_rules:
        pattern = normalize_text(rule.get("pattern"))
        category = rule.get("category")
        if pattern and category in allowed and match_user_rule(lower, tokens, pattern):
            return {
                "category": category,
                "confidence": min(0.99, 0.94 + min(int(rule.get("hit_count") or 0), 10) * 0.005),
                "source": "learned_rule",
                "needs_review": False,
            }

    priority = {slug: index for index, slug in enumerate(CATEGORY_PRIORITY)}
    scores = []
    for row in context:
        slug = row["slug"]
        if slug == "other":
            continue
        score = 0.0
        for keyword in row.get("keywords") or []:
            score += score_phrase(lower, tokens, keyword)
        label_tokens = tokenize(normalize_text(row.get("label")))
        description_tokens = tokenize(normalize_text(row.get("description")))
        score += len(tokens & label_tokens) * 2.5
        score += len((tokens - GENERIC_TOKENS) & description_tokens) * 0.6
        if score > 0:
            scores.append((score, -priority.get(slug, 10_000), slug))

    scores.sort(reverse=True)
    if scores:
        best_score, _, best_category = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else 0.0
        margin = best_score - second_score
        if best_score >= 8 and margin >= 3:
            confidence = 0.92
        elif best_score >= 5 and margin >= 2:
            confidence = 0.84
        elif best_score >= 3 and margin >= 1:
            confidence = 0.68
        else:
            confidence = 0.56
        if provider_category == best_category:
            confidence = max(confidence, 0.88)
            source = "model" if confidence < 0.85 else "keyword_score"
        else:
            source = "keyword_score"
        if confidence >= 0.6:
            return {
                "category": best_category,
                "confidence": confidence,
                "source": source,
                "needs_review": confidence < 0.85,
            }

    if provider_category in allowed and provider_category != "other":
        return {
            "category": provider_category,
            "confidence": 0.72,
            "source": "model",
            "needs_review": True,
        }

    fallback = "other" if "other" in allowed else next(iter(allowed), "other")
    return {
        "category": fallback,
        "confidence": 0.25,
        "source": "fallback",
        "needs_review": True,
    }


def classify_receipt_items(
    merchant,
    items,
    user_rules=None,
    category_context=None,
):
    context = category_context or build_category_context()
    results = []
    for item in items:
        name = normalize_text(item.get("name"))
        combined = " ".join(value for value in (name, normalize_text(merchant)) if value)
        result = classify_category(
            combined,
            user_rules=user_rules,
            category_context=context,
            provider_category=item.get("category"),
        )
        results.append({**item, **result})
    return results
