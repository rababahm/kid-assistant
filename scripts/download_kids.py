"""Download the KID PDFs listed in data/manifest.csv and check their SHA-256 hashes."""

import argparse
import csv
import hashlib
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
MANIFEST = ROOT / "data" / "manifest.csv"
RAW_DIR = ROOT / "data" / "raw"
USER_AGENT = "kid-assistant/0.1 (+https://github.com/rababahm/kid-assistant)"
NEEDS_ATTENTION = ("MANUAL", "NOT A PDF", "DOWNLOAD ERROR", "CHANGED")


def get_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def check_row(row: dict) -> tuple[str, str, str | None]:
    """Return (status, detail, actual hash) for one row, downloading the PDF if it is missing."""
    pdf_path = RAW_DIR / f"{row['kid_id'].strip()}.pdf"
    url = row["url"].strip()

    if pdf_path.is_file():
        data = pdf_path.read_bytes()  # never re-download a file we already have
    elif not url:
        return "MANUAL", "no URL: download by hand from the provider's page", None
    else:
        try:
            data = download(url)
        except (urllib.error.URLError, TimeoutError) as error:
            return "DOWNLOAD ERROR", str(error), None
        if not data.startswith(b"%PDF"):
            return (
                "NOT A PDF",
                "probably a country or investor-type page: download by hand",
                None,
            )
        pdf_path.write_bytes(data)

    actual = get_sha256(data)
    expected = row["sha256"].strip().lower()
    if not expected:
        return "NEW", actual, actual
    if actual == expected:
        return "OK", "", actual
    return (
        "CHANGED",
        f"provider replaced the KID? expected {expected}, got {actual}",
        actual,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-hashes",
        action="store_true",
        help="fill empty sha256 cells in the manifest with the computed hashes",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    counts = Counter()
    for row in rows:
        status, detail, actual = check_row(row)
        counts[status] += 1
        print(f"[{row['kid_id']}] {status} {detail}".rstrip())
        if status == "NEW" and args.write_hashes:
            row["sha256"] = actual

    if args.write_hashes and counts["NEW"]:
        with MANIFEST.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {counts['NEW']} new hash(es) to {MANIFEST.relative_to(ROOT)}")

    print("\n--- SUMMARY ---")
    for status in ("OK", "NEW", *NEEDS_ATTENTION):
        print(f"{status:<15}{counts[status]}")
    sys.exit(1 if any(counts[s] for s in NEEDS_ATTENTION) else 0)


if __name__ == "__main__":
    main()
