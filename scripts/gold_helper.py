"""Print where each fact sits in a KID, to help write its gold labels by hand (no model).

Run with:
  uv run python scripts/gold_helper.py <kid_id>          # print the evidence
  uv run python scripts/gold_helper.py <kid_id> --init   # also create an empty gold file
  uv run python scripts/gold_helper.py <kid_id> --check  # check a filled gold file

Copy quotes from lines marked 'pN lM' (pdfplumber text lines). Lines marked
'pN table' join table cells: use them to read, not to quote.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber
from pydantic import ValidationError

from kid_assistant.schema import CostValue, HoldingPeriodValue, KidFacts

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
RAW_DIR = ROOT / "data" / "raw"
GOLD_DIR = ROOT / "gold"

ISIN = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
DATE = re.compile(
    r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b"
    r"|\b\d{1,2}(st|nd|rd|th)? (January|February|March|April|May|June|July|August"
    r"|September|October|November|December),? \d{4}\b"
)
RISK = re.compile(r"out of 7")
HOLDING = re.compile(r"holding period", re.IGNORECASE)
MANUFACTURER = re.compile(r"manufacturer|managed by|management company", re.IGNORECASE)
COST_LABELS = [
    "entry costs",
    "exit costs",
    "management fees",
    "transaction costs",
    "performance fee",
]


def read_pages(pdf_path: Path) -> tuple[list[list[str]], list[list[str]]]:
    """Per page: the pdfplumber text lines, and the table rows as 'cell | cell'."""
    texts, tables = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texts.append((page.extract_text() or "").splitlines())
            tables.append(
                [
                    " | ".join((c or "").replace("\n", " ") for c in row)
                    for table in page.extract_tables()
                    for row in table
                ]
            )
    return texts, tables


def show(title: str, hits: list[tuple[str, str]]) -> None:
    print(f"\n{title}")
    for where, line in hits or [("", "(nothing found: look in the PDF)")]:
        print(f"  {where:9} {line.strip()[:150]}")


def text_hits(
    texts: list[list[str]], pattern: re.Pattern, pages: set[int] | None = None
) -> list[tuple[str, str]]:
    """Every text line matching the pattern, as ('pN lM', line)."""
    return [
        (f"p{p} l{i}", line)
        for p, lines in enumerate(texts, start=1)
        if pages is None or p in pages
        for i, line in enumerate(lines)
        if pattern.search(line)
    ]


def cost_block(texts: list[list[str]]) -> list[tuple[str, str]]:
    """Numbered text lines from just before 'Entry costs' to after 'Performance fee'."""
    for p, lines in enumerate(texts, start=1):
        starts = [i for i, line in enumerate(lines) if "entry costs" in line.lower()]
        if not starts:
            continue
        start = max(starts[0] - 2, 0)
        ends = [
            i
            for i, line in enumerate(lines)
            if i > starts[0] and "performance fee" in line.lower()
        ]
        end = min(ends[0] + 3 if ends else start + 25, len(lines))
        return [(f"p{p} l{i}", lines[i]) for i in range(start, end)]
    return []


def check(kid_id: str, texts: list[list[str]]) -> list[str]:
    """Problems in a filled gold file; an empty list means it passed."""
    path = GOLD_DIR / f"{kid_id}.json"
    try:
        gold = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"not valid JSON: {error}"]
    problems, data = [], {}
    for name in KidFacts.model_fields:
        entry = gold.get(name)
        if entry is None:
            problems.append(f"{name}: missing")
            continue
        for key, value in entry.items():
            if value is None or value == [] or value == "":
                problems.append(f"{name}.{key} is empty")
        for page in entry.get("pages", []):
            if not 1 <= page <= len(texts):
                problems.append(f"{name}: page {page} does not exist")
            elif not any(entry["quote"] in line for line in texts[page - 1]):
                problems.append(f"{name}: quote not on one line of page {page}")
        item = {k: v for k, v in entry.items() if k not in ("pages", "quote")}
        item["page"] = entry["pages"][0] if entry.get("pages") else 1
        data[name] = item
    try:
        KidFacts(**data)
    except ValidationError as error:
        problems += [
            f"schema: {'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in error.errors()
        ]
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("kid_id")
    parser.add_argument("--init", action="store_true", help="create an empty gold file")
    parser.add_argument("--check", action="store_true", help="check a filled gold file")
    args = parser.parse_args()

    texts, tables = read_pages(RAW_DIR / f"{args.kid_id}.pdf")

    if args.check:
        problems = check(args.kid_id, texts)
        print("\n".join(problems) or "all checks passed")
        sys.exit(1 if problems else 0)

    show(
        "PAGE 1, first lines (fund name, share class)",
        [(f"p1 l{i}", line) for i, line in enumerate(texts[0][:10])],
    )
    show("MANUFACTURER", text_hits(texts, MANUFACTURER))
    show("ISIN", text_hits(texts, ISIN)[:3])
    show("DATE on page 1", text_hits(texts, DATE, pages={1}))
    show("RISK sentence", text_hits(texts, RISK))
    show("HOLDING PERIOD", text_hits(texts, HOLDING))
    show("COST SECTION (text lines: quote from these)", cost_block(texts))
    show(
        "COST TABLE ROWS (cells joined: read, do not quote)",
        [
            (f"p{p} table", row)
            for p, rows in enumerate(tables, start=1)
            for row in rows
            if any(row.lstrip("| ").lower().startswith(lb) for lb in COST_LABELS)
        ],
    )

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
