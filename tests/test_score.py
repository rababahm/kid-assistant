"""Scoring against gold labels: normalisation and per-field matching."""

import pytest

from kid_assistant.schema import KidFacts
from kid_assistant.score import normalise, score, value_matches, words


def test_normalise_quotes_spaces_and_case():
    assert normalise("  The  \u201cFund\u201d\n\u2019s ") == 'the "fund" \'s'


def test_words_splits_on_punctuation():
    assert words("NASDAQ-100 (the \u201cFund\u201d)") == {
        "nasdaq",
        "100",
        "the",
        "fund",
    }


@pytest.mark.parametrize(
    "field, predicted, gold_value, expected",
    [
        ("transaction_costs_pct", 0.2200001, 0.22, True),
        ("transaction_costs_pct", 0.26, 0.22, False),
        ("transaction_costs_pct", "0.22", 0.22, False),
        ("risk_indicator", 5.0, 5, True),
        (
            "fund_name",
            'Example Fund A EUR Acc (the "Fund")',
            "Example Fund A EUR Acc",
            True,
        ),
        ("fund_name", "Example Fund", "Example Fund A EUR Acc", False),
        ("fund_name", "Mirabaud Flexible NH USD", "Mirabaud Flexible AH USD", False),
        ("isin", "lu0000000001", "LU0000000001", True),
        ("kid_date", "19/02/2026", "19 February 2026", False),
    ],
)
def test_value_matches(field, predicted, gold_value, expected):
    assert value_matches(field, predicted, gold_value) is expected


def test_score_all_right(make_facts, gold):
    results = score(make_facts(), gold)
    assert set(results) == set(KidFacts.model_fields)
    assert all(r["value"] and r["page"] for r in results.values())


def test_score_wrong_is_maximum_fails_value_not_page(make_facts, gold):
    gold["entry_cost_pct"]["is_maximum"] = False
    assert score(make_facts(), gold)["entry_cost_pct"] == {"value": False, "page": True}


def test_score_wrong_unit_fails_value(make_facts, gold):
    gold["recommended_holding_period"]["unit"] = "months"
    result = score(make_facts(), gold)["recommended_holding_period"]
    assert result == {"value": False, "page": True}


def test_score_page_must_be_one_of_the_gold_pages(make_facts, gold):
    gold["risk_indicator"]["pages"] = [1]
    assert score(make_facts(), gold)["risk_indicator"] == {"value": True, "page": False}
    gold["risk_indicator"]["pages"] = [1, 2]
    assert score(make_facts(), gold)["risk_indicator"] == {"value": True, "page": True}
