"""Grounding: each value must be printed on the page the model cited."""

import pytest

from kid_assistant.grounding import grounding_problems, percent_on_page


def test_no_false_alarm_on_correct_facts(make_facts, pages):
    assert grounding_problems(make_facts(), pages) == []


def test_invented_value_is_caught(make_facts, pages):
    facts = make_facts(management_fees_and_other_costs_pct={"value": 0.26})
    problems = grounding_problems(facts, pages)
    assert len(problems) == 1
    assert problems[0].startswith("management_fees_and_other_costs_pct")


def test_wrong_page_is_caught(make_facts, pages):
    problems = grounding_problems(make_facts(risk_indicator={"page": 1}), pages)
    assert len(problems) == 1
    assert problems[0].startswith("risk_indicator")


def test_wrong_unit_is_caught(make_facts, pages):
    facts = make_facts(recommended_holding_period={"unit": "months"})
    assert len(grounding_problems(facts, pages)) == 1


def test_missing_page_is_reported(make_facts, pages):
    problems = grounding_problems(make_facts(), pages[:2])
    assert len(problems) == 5
    assert all("page 3 does not exist" in p for p in problems)


def test_zero_is_never_checked_known_blind_spot(make_facts, pages):
    facts = make_facts(exit_cost_pct={"value": 0, "page": 1})
    assert grounding_problems(facts, pages) == []


@pytest.mark.parametrize(
    "x, text, expected",
    [
        (1.5, "Entry costs 1,50 % of the amount", True),
        (0.22, "costs 0.22% per year", True),
        (0.22, "costs 10.22% per year", False),
        (20, "20% of the outperformance", True),
        (0.26, "costs 0.3% per year", False),
    ],
)
def test_percent_on_page(x, text, expected):
    assert percent_on_page(x, text) is expected


@pytest.mark.parametrize("field", ["isin", "fund_name"])
def test_empty_text_value_is_not_grounded(make_facts, pages, field):
    problems = grounding_problems(make_facts(**{field: {"value": ""}}), pages)
    assert len(problems) == 1
