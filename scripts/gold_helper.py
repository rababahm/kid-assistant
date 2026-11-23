"""Print where each fact sits in a KID, to help write its gold labels by hand (no model).

Run with:
  uv run python scripts/gold_helper.py <kid_id>          # print the evidence
  uv run python scripts/gold_helper.py <kid_id> --init   # also create an empty gold/<kid_id>.json
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber

from kid_assistant.schema import CostValue, HoldingPeriodValue, KidFacts

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
RAW_DIR = ROOT / "data" / "raw"
GOLD_DIR = ROOT / "gold"

ISIN = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
DATE = re.compile(
    r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b"
    r"|\b\d{1,2} (January|February|March|April|May|June|July|August|September"
    r"|October|November|December) \d{4}\b"
)
RISK = re.compile(r"classified this product as (\d) out of 7")
HOLDING = re.compile(
    r"recommended holding period[^.]{0,60}?\d+ (?:years?|months?|weeks?|days?)(?:\(s\))?",
    re.IGNORECASE,
)
COST_LABELS = [
    "entry costs",
    "exit costs",
    "management fees",
    "transaction costs",
    "performance fee",
]


def read_pages(pdf_path: Path) -> list[list[str]]:
    """Lines of each page: pdfplumber text, then each table row as 'cell | cell'."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = (page.extract_text() or "").splitlines()
            for table in page.extract_tables():
                for row in table:
                    lines.append(" | ".join((c or "").replace("\n", " ") for c in row))
            pages.append(lines)
    return pages


def show(title: str, hits: list[tuple[int, str]]) -> None:
    print(f"\n{title}")
    for page, line in hits or [(0, "(nothing found: look in the PDF)")]:
        print(f"  p{page}  {line.strip()[:150]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kid_id")
    parser.add_argument("--init", action="store_true", help="create an empty gold file")
    args = parser.parse_args()

    pages = read_pages(RAW_DIR / f"{args.kid_id}.pdf")
    numbered = [(n, line) for n, lines in enumerate(pages, start=1) for line in lines]
    joined = {
        n: " ".join(" ".join(lines).split()) for n, lines in enumerate(pages, start=1)
    }

    show(
        "PAGE 1, first lines (fund name, manufacturer)", [(1, l) for l in pages[0][:8]]
    )
    show("ISIN", [(n, l) for n, l in numbered if ISIN.search(l)][:3])
    show("DATE on page 1", [(1, l) for l in pages[0] if DATE.search(l)])
    show(
        "RISK sentence",
        [(n, m.group(0)) for n, t in joined.items() for m in RISK.finditer(t)],
    )
    show(
        "RECOMMENDED HOLDING PERIOD",
        [(n, m.group(0)) for n, t in joined.items() for m in HOLDING.finditer(t)],
    )
    for label in COST_LABELS:
        rows = [(n, l) for n, l in numbered if l.lstrip("| ").lower().startswith(label)]
        show(f"COST ROW: {label}", rows)

    if args.init:
        path = GOLD_DIR / f"{args.kid_id}.json"
        if path.exists():
            print(f"\n{path.relative_to(ROOT)} already exists: not overwritten")
            return
        empty = {"kid_id": args.kid_id}
        for name, field in KidFacts.model_fields.items():
            entry = {"value": None}
            if field.annotation is HoldingPeriodValue:
                entry["unit"] = None  # same key order as the migrated gold files
            entry |= {"pages": [], "quote": ""}
            if field.annotation is CostValue:
                entry["is_maximum"] = None
            empty[name] = entry
        GOLD_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
        print(f"\nCreated {path.relative_to(ROOT)}: fill every value, pages and quote")


if __name__ == "__main__":
    main()
