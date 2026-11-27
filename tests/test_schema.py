"""Schema constraints: impossible values from the model must be rejected."""

import pytest
from pydantic import ValidationError

from kid_assistant.schema import (
    CostValue,
    HoldingPeriodValue,
    PercentValue,
    RiskValue,
    TextValue,
)


@pytest.mark.parametrize("value", [1, 4, 7])
def test_risk_accepts_1_to_7(value):
    assert RiskValue(value=value, page=2).value == value


@pytest.mark.parametrize("value", [-1, 0, 8])
def test_risk_rejects_outside_1_to_7(value):
    with pytest.raises(ValidationError):
        RiskValue(value=value, page=2)


@pytest.mark.parametrize("value", [0, 1.5, 100])
def test_percent_accepts_0_to_100(value):
    assert PercentValue(value=value, page=3).value == value


@pytest.mark.parametrize("value", [-0.01, 100.01])
def test_percent_rejects_outside_0_to_100(value):
    with pytest.raises(ValidationError):
        PercentValue(value=value, page=3)


def test_holding_period_rejects_zero():
    with pytest.raises(ValidationError):
        HoldingPeriodValue(value=0, unit="years", page=2)


def test_holding_period_accepts_fraction():
    assert HoldingPeriodValue(value=0.5, unit="years", page=2).value == 0.5


@pytest.mark.parametrize("unit", ["days", "weeks", "months", "years"])
def test_holding_period_accepts_the_four_units(unit):
    assert HoldingPeriodValue(value=1, unit=unit, page=2).unit == unit


@pytest.mark.parametrize("unit", ["year", "Years", "yrs", ""])
def test_holding_period_rejects_other_units(unit):
    with pytest.raises(ValidationError):
        HoldingPeriodValue(value=1, unit=unit, page=2)


MINIMAL_VALID = {
    TextValue: {"value": "x"},
    RiskValue: {"value": 4},
    HoldingPeriodValue: {"value": 5, "unit": "years"},
    PercentValue: {"value": 1.5},
    CostValue: {"value": 1.5, "is_maximum": False},
}
MODEL_IDS = [model.__name__ for model in MINIMAL_VALID]


@pytest.mark.parametrize("model", MINIMAL_VALID, ids=MODEL_IDS)
@pytest.mark.parametrize("page", [1, 3])
def test_every_model_accepts_pages_1_to_3(model, page):
    assert model(**MINIMAL_VALID[model], page=page).page == page


@pytest.mark.parametrize("model", MINIMAL_VALID, ids=MODEL_IDS)
@pytest.mark.parametrize("page", [0, 4])
def test_every_model_rejects_pages_outside_1_to_3(model, page):
    with pytest.raises(ValidationError):
        model(**MINIMAL_VALID[model], page=page)


def test_cost_requires_is_maximum():
    with pytest.raises(ValidationError):
        CostValue(value=1.5, page=3)


def test_percent_coerces_a_numeric_string():
    # Pydantic's default (lax) mode converts "1.5" to 1.5
    assert PercentValue(value="1.5", page=3).value == 1.5


@pytest.mark.parametrize("text", ["1.5%", "1,5"])
def test_percent_rejects_strings_that_are_not_plain_numbers(text):
    with pytest.raises(ValidationError):
        PercentValue(value=text, page=3)
