"""Check that each extracted value is printed on the page the model cited."""

import re

from kid_assistant.schema import KidFacts
from kid_assistant.score import words

PERCENT_FIELDS = [
    "entry_cost_pct",
    "exit_cost_pct",
    "management_fees_and_other_costs_pct",
    "transaction_costs_pct",
    "performance_fee_pct",
]


def number_forms(x: float) -> set[str]:
    """Ways a KID may print a number: 0.22, 1.5, 1.50, 20, and with a decimal comma."""
    forms = {f"{x:g}", f"{x:.1f}", f"{x:.2f}"}
    return forms | {f.replace(".", ",") for f in forms}


def percent_on_page(x: float, text: str) -> bool:
    """True if x is printed as a percentage (not as part of a longer number)."""
    return any(
        re.search(rf"(?<![\d.,]){re.escape(form)}\s?%", text)
        for form in number_forms(x)
    )


def grounding_problems(facts: KidFacts, pages: list[str]) -> list[str]:
    """One message per value not printed on its cited page. Values of 0 are not checked."""
    problems = []
    for field in KidFacts.model_fields:
        item = getattr(facts, field)
        if item.page > len(pages):
            problems.append(f"{field}: page {item.page} does not exist")
            continue
        text = pages[item.page - 1]
        if field in PERCENT_FIELDS:
            found = item.value == 0 or percent_on_page(item.value, text)
        elif field == "risk_indicator":
            found = re.search(rf"\b{item.value} out of 7", text) is not None
        elif field == "recommended_holding_period":
            stem = item.unit[:-1]  # years -> year, months -> month
            pattern = rf"holding period[^.]{{0,60}}?\b{item.value:g}\s+{stem}"
            found = re.search(pattern, text, re.IGNORECASE) is not None
        elif field in ("isin", "kid_date"):
            found = item.value in text
        else:  # fund_name, manufacturer: every word of the answer on the page
            found = words(item.value) <= words(text)
        if not found:
            problems.append(
                f"{field}: {item.value!r} is not printed on page {item.page}"
            )
    return problems
