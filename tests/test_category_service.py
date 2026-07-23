from api.category_service import (
    build_category_context,
    classify_category,
    classify_receipt_items,
)
from database import normalize_category_description, normalize_category_keywords


def test_learned_rule_has_priority():
    result = classify_category(
        "Lunch at school",
        user_rules=[{"pattern": "school", "category": "education", "hit_count": 4}],
        category_context=[
            {"slug": "food", "label": "Food", "description": "", "keywords": ["lunch"]},
            {"slug": "education", "label": "Education", "description": "", "keywords": []},
            {"slug": "other", "label": "Other", "description": "", "keywords": []},
        ],
    )

    assert result["category"] == "education"
    assert result["source"] == "learned_rule"
    assert result["needs_review"] is False


def test_custom_category_keywords_are_candidates():
    context = build_category_context([
        {
            "slug": "pets",
            "label": "Pets",
            "description": "Pet care and supplies",
            "keywords": ["dog food", "veterinary"],
        }
    ])
    result = classify_category("Premium dog food", category_context=context)

    assert result["category"] == "pets"
    assert result["confidence"] >= 0.85


def test_invalid_provider_category_falls_back_safely():
    result = classify_category(
        "unrecognized purchase 123",
        category_context=build_category_context(),
        provider_category="another_users_category",
    )

    assert result["category"] == "other"
    assert result["needs_review"] is True


def test_provider_can_resolve_ambiguous_item_with_allowed_category():
    result = classify_category(
        "annual policy",
        category_context=build_category_context(),
        provider_category="health",
    )

    assert result["category"] == "health"
    assert result["source"] == "model"
    assert result["needs_review"] is True


def test_receipt_items_include_merchant_context():
    context = build_category_context([
        {
            "slug": "pets",
            "label": "Pets",
            "description": "Animal care",
            "keywords": ["pet clinic"],
        }
    ])
    results = classify_receipt_items(
        "Happy Pet Clinic",
        [{"name": "Consultation", "amount": 500, "category": ""}],
        category_context=context,
    )

    assert results[0]["category"] == "pets"


def test_custom_category_metadata_is_normalized():
    assert normalize_category_description("  Pet   care  ") == "Pet care"
    assert normalize_category_keywords(" Vet, dog food, vet ") == ["vet", "dog food"]
