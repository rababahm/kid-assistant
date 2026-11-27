"""Shared test data: one valid set of facts, its gold labels, and page text that supports it."""

import copy

import pytest

from kid_assistant.schema import KidFacts

FACTS = {
    "fund_name": {"value": "Example Fund A EUR Acc", "page": 1},
    "isin": {"value": "LU0000000001", "page": 1},
    "manufacturer": {"value": "Example Asset Management S.A.", "page": 1},
    "kid_date": {"value": "19 February 2026", "page": 1},
    "risk_indicator": {"value": 4, "page": 2},
    "recommended_holding_period": {"value": 5, "unit": "years", "page": 2},
    "entry_cost_pct": {"value": 3.0, "is_maximum": True, "page": 3},
    "exit_cost_pct": {"value": 0, "is_maximum": False, "page": 3},
    "management_fees_and_other_costs_pct": {"value": 0.22, "page": 3},
    "transaction_costs_pct": {"value": 0.08, "page": 3},
    "performance_fee_pct": {"value": 0, "page": 3},
}

PAGES = [
    (
        "Key Information Document\nExample Fund A EUR Acc\nISIN: LU0000000001\n"
        "Manufacturer: Example Asset Management S.A.\nDate of production: 19 February 2026"
    ),
    (
        "We have classified this product as 4 out of 7, which is a medium risk class.\n"
        "Recommended holding period: 5 years"
    ),
    (
        "Entry costs Up to 3.00% of the amount you pay in\n"
        "Exit costs We do not charge an exit fee\n"
        "Management fees and other administrative or operating costs 0.22% of the value "
        "of your investment per year\n"
        "Transaction costs 0.08% of the value of your investment per year\n"
        "Performance fees There is no performance fee for this product."
    ),
]


@pytest.fixture
def facts_json():
    return KidFacts.model_validate(FACTS).model_dump_json()


@pytest.fixture
def make_facts():
    """Build valid KidFacts, changing only the fields given."""

    def _make(**changes):
        data = copy.deepcopy(FACTS)
        for field, update in changes.items():
            data[field].update(update)
        return KidFacts.model_validate(data)

    return _make


@pytest.fixture
def gold():
    entries = {}
    for field, item in copy.deepcopy(FACTS).items():
        entry = {"value": item["value"], "pages": [item["page"]]}
        for key in ("is_maximum", "unit"):
            if key in item:
                entry[key] = item[key]
        entries[field] = entry
    return entries


@pytest.fixture
def pages():
    return list(PAGES)
