"""Check how well each parser preserved the KIDs: facts, text fidelity and table structure."""

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
PARSED_DIR = ROOT / "parsed"
MANIFEST = ROOT / "data" / "manifest.csv"
REPORT = PARSED_DIR / "check_report.txt"
REFERENCE = "pymupdf_text"  # reads characters directly, with no layout logic

PAGE_MARKER = re.compile(r"^[ \t]*===== page \d+ =====[ \t]*$", flags=re.MULTILINE)
DATE = re.compile(
    r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b"
    r"|\b\d{1,2} (January|February|March|April|May|June|July|August|September"
    r"|October|November|December) \d{4}\b"
)
RISK = re.compile(r"classified this product as (\d) out of 7")
HOLDING = re.compile(
    r"recommended holding period[^.]{0,60}?(\d+) years?", flags=re.IGNORECASE
)
PERCENT = re.compile(r"\d+(\.\d+)?\s?%")
MONEY = re.compile(
    r"(USD|EUR|CHF|\u20ac)\s?\d[\d,' ]*|\d[\d,']*\s?(USD|EUR|CHF|\u20ac)"
)
NONE_STATED = re.compile(
    r"\bno\b|\bnone\b|n/a|not applicable|do(es)? not charge", flags=re.IGNORECASE
)
WORD = re.compile(r"[^\W_]+")
COST_LABELS = {
    "entry": "entry costs",
    "exit": "exit costs",
    "management": "management fees",
    "transaction": "transaction costs",
    "performance": "performance fee",
}
TABLE_SEPARATOR = re.compile(
    r"^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-*:?\s*$", flags=re.MULTILINE
)


def read_pages(path: Path) -> list[str]:
    """Split a parsed file into its pages, using the markers written by compare_parsers.py."""
    text = path.read_text(encoding="utf-8")
    parts = PAGE_MARKER.split(text)
    return [
        part.strip() for part in parts[1:]
    ]  # parts[0] is the empty text before page 1


def normalise(text: str) -> str:
    """Strip Markdown formatting and join wrapped lines, so phrases can be matched."""
    text = text.replace("**", "")  # bold
    text = re.sub(r"</?u>", "", text, flags=re.IGNORECASE)  # underline tags
    text = re.sub(r"^[ \t]*#+[ \t]*", "", text, flags=re.MULTILINE)  # heading marks
    # <br> marks a line break inside a table cell.
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = TABLE_SEPARATOR.sub("", text)  # |---|---| rows under table headers
    # Escaped pipes first: replacing "|" first would leave the backslash behind.
    text = text.replace(r"\|", " ")
    text = text.replace("|", " ")  # table cell borders
    return " ".join(text.split())  # any whitespace, line breaks included, to one space


def fact_checks(pages: list[str], row: dict) -> dict[str, bool]:
    """Check that facts every KID must state survived parsing, on normalised text."""
    page1 = normalise(pages[0])
    full = normalise(" ".join(pages))
    return {
        "isin_p1": row["isin"] in page1,
        "date_p1": DATE.search(page1) is not None,
        "risk": RISK.search(full) is not None,
        "holding": HOLDING.search(full) is not None,
    }


def missing_words(reference: str, output: str) -> list[str]:
    """Words the reference has more often than the output: lost or changed text."""
    ref_counts = Counter(WORD.findall(normalise(reference).lower()))
    out_counts = Counter(WORD.findall(normalise(output).lower()))
    return sorted((ref_counts - out_counts).elements())


def find_line(lines: list[str], phrase: str, passes) -> tuple[bool, str]:
    """First line starting with phrase that passes the test; else the first such line."""
    # Only lines that START with the label are table rows: this skips sentences such as
    # "There is no performance fee", which would otherwise pass the test by accident.
    candidates = [
        line for line in lines if line.lstrip("|*# ").lower().startswith(phrase)
    ]
    for line in candidates:
        if passes(line):
            return True, line.strip()
    return False, candidates[0].strip() if candidates else "(phrase not found)"


def structure_checks(pages: list[str]) -> dict[str, tuple[bool, str]]:
    """On raw lines: does each table row keep its label and its values together?"""
    lines = "\n".join(pages).splitlines()
    results = {}
    for name, label in COST_LABELS.items():
        results[name] = find_line(
            lines,
            label,
            lambda line: PERCENT.search(line) or NONE_STATED.search(line),
        )
    results["total_costs"] = find_line(
        lines, "total costs", lambda line: len(MONEY.findall(line)) >= 2
    )
    results["scenario"] = find_line(
        lines, "moderate", lambda line: len(MONEY.findall(line)) >= 2
    )
    return results


def mark(value) -> str:
    """Grid cell: a tick or cross for booleans, the value itself otherwise."""
    if isinstance(value, bool):
        return "\u2713" if value else "\u2717"
    return str(value)


def print_grid(kid_id: str, results: dict[str, dict]) -> None:
    """Print one KID's results: one row per check, one column per parser."""
    parsers = list(results)
    checks = list(next(iter(results.values())))
    widths = [max(len(parser), 2) for parser in parsers]
    print(f"\n{kid_id}")
    print("check".ljust(13) + "  ".join(p.ljust(w) for p, w in zip(parsers, widths)))
    for check in checks:
        cells = [mark(results[p][check]) for p in parsers]
        print(check.ljust(13) + "  ".join(c.ljust(w) for c, w in zip(cells, widths)))


def main() -> None:
    parsers = sorted(folder.name for folder in PARSED_DIR.iterdir() if folder.is_dir())

    with MANIFEST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    totals = Counter()  # parser -> number of passed checks
    n_checks = 0
    report = []  # evidence lines, written to REPORT for checking by eye
    for row in rows:
        kid_id = row["kid_id"]
        all_pages = {p: read_pages(PARSED_DIR / p / f"{kid_id}.txt") for p in parsers}
        reference = " ".join(all_pages[REFERENCE])
        results = {}  # parser name -> {check name -> result}
        for parser, pages in all_pages.items():
            lost = missing_words(reference, " ".join(pages))
            structure = structure_checks(pages)
            results[parser] = {
                "3_pages": len(pages) == 3,
                **fact_checks(pages, row),
                "lost_words": len(lost),
                **{name: ok for name, (ok, _) in structure.items()},
            }
            report.append(f"\n=== {kid_id} / {parser}")
            report.append(f"lost words ({len(lost)}): {' '.join(lost[:30])}")
            for name, (ok, line) in structure.items():
                report.append(f"{mark(ok)} {name:12} {line[:160]}")
            totals[parser] += sum(v is True for v in results[parser].values())
        n_checks = sum(isinstance(v, bool) for v in results[parsers[0]].values())
        print_grid(kid_id, results)

    print(f"\nPassed checks out of {n_checks * len(rows)} (lost words not included):")
    for parser in parsers:
        print(f"  {parser:20} {totals[parser]}")
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"\nEvidence for each check: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
