"""Score extracted KID facts against hand-made gold labels (gold/<kid_id>.json)."""

import json
import re
from pathlib import Path

from kid_assistant.schema import KidFacts

TOLERANCE = 1e-3  # numbers: 0.22 and 0.2200001 are the same value
# Names may legitimately carry extra words, e.g. '(the "Fund")': for these two fields
# the answer must contain every word of the gold value, not match it exactly.
CONTAINS_ALL_WORDS = {"fund_name", "manufacturer"}


def load_gold(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalise(text: str) -> str:
    """Lower case, straight quotes, single spaces."""
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return " ".join(text.split()).lower()


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9$]+", normalise(text)))


def value_matches(field: str, predicted, gold) -> bool:
    if isinstance(gold, bool) or isinstance(predicted, bool):
        return predicted == gold
    if isinstance(gold, (int, float)):
        return isinstance(predicted, (int, float)) and abs(predicted - gold) < TOLERANCE
    if field in CONTAINS_ALL_WORDS:
        return words(gold) <= words(str(predicted))
    return normalise(str(predicted)) == normalise(str(gold))  # ISIN, date: exact


def score(facts: KidFacts, gold: dict) -> dict[str, dict[str, bool]]:
    """For each field: is the value right, and is the page one of the gold pages?"""
    results = {}
    for field in KidFacts.model_fields:
        predicted = getattr(facts, field)
        expected = gold[field]
        value_ok = value_matches(field, predicted.value, expected["value"])
        if (
            "is_maximum" in expected
        ):  # cost fields: "up to 5%" is not the same fact as "5%"
            value_ok = value_ok and predicted.is_maximum == expected["is_maximum"]
        results[field] = {
            "value": value_ok,
            "page": predicted.page in expected["pages"],
        }
    return results
