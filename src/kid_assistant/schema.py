"""Schema for the facts extracted from one KID: each value with the page it was found on."""

from typing import Literal

from pydantic import BaseModel, Field

MAX_PAGES = 3  # a KID has at most three pages (PRIIPs regulation)
PAGE_DESCRIPTION = "Page where the value is stated (1 to 3)"


class TextValue(BaseModel):
    value: str
    page: int = Field(ge=1, le=MAX_PAGES, description=PAGE_DESCRIPTION)


class RiskValue(BaseModel):
    value: int = Field(ge=1, le=7)
    page: int = Field(ge=1, le=MAX_PAGES, description=PAGE_DESCRIPTION)


class HoldingPeriodValue(BaseModel):
    value: float = Field(
        gt=0, description="The number exactly as printed: 5 for '5 years'"
    )
    unit: Literal["days", "weeks", "months", "years"] = Field(
        description=(
            "The unit as printed, as one of these four words "
            "('Year(s)' is years, '1 month' is months)"
        )
    )
    page: int = Field(ge=1, le=MAX_PAGES, description=PAGE_DESCRIPTION)


class PercentValue(BaseModel):
    value: float = Field(
        ge=0, le=100, description="Percentage as a number: 1.5 for 1.5%"
    )
    page: int = Field(ge=1, le=MAX_PAGES, description=PAGE_DESCRIPTION)


class CostValue(PercentValue):
    is_maximum: bool = Field(
        description=(
            'True if the KID gives a maximum ("up to", "no more than") '
            "rather than the actual charge"
        )
    )


class KidFacts(BaseModel):
    """Facts from one KID, in the order they appear in the document."""

    # Page 1
    fund_name: TextValue = Field(
        description="Full name of the fund and share class, exactly as written on page 1"
    )
    isin: TextValue = Field(description="ISIN code of the share class: 12 characters")
    manufacturer: TextValue = Field(
        description="Company responsible for the product (the manufacturer)"
    )
    kid_date: TextValue = Field(
        description="Date of the KID (production date), exactly as printed, not reformatted"
    )
    # Page 2
    risk_indicator: RiskValue = Field(
        description=(
            'Summary risk indicator, from the sentence "We have classified this product '
            'as N out of 7"'
        )
    )
    recommended_holding_period: HoldingPeriodValue = Field(
        description=(
            "Recommended holding period: the number and its unit exactly as stated, "
            "not converted (1 month stays 1 month)"
        )
    )
    # Page 3: composition of costs
    entry_cost_pct: CostValue = Field(
        description="Entry costs, % of the amount invested; 0 if no entry costs are charged"
    )
    exit_cost_pct: CostValue = Field(
        description="Exit costs, % of the investment; 0 if no exit costs are charged"
    )
    management_fees_and_other_costs_pct: PercentValue = Field(
        description=(
            'The row "Management fees and other administrative or operating costs", '
            "% of the investment per year. Do not add transaction costs."
        )
    )
    transaction_costs_pct: PercentValue = Field(
        description='The row "Transaction costs", % of the investment per year'
    )
    performance_fee_pct: PercentValue = Field(
        description=(
            "Performance fee rate as stated in the KID, in % of outperformance "
            "(20 for '20% of outperformance'); 0 if the KID says there is no performance fee"
        )
    )
