"""Run the extractor on one split of the manifest and score it against gold/.

Run with:
  uv run python scripts/run_extraction.py --split dev --run baseline
  uv run python scripts/run_extraction.py --split test --run final --final
Raw replies, scores and a summary are saved in results/runs/<run>/.
"""

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

import ollama

from kid_assistant.extract import MAX_ATTEMPTS, MODEL, OPTIONS, extract
from kid_assistant.schema import KidFacts
from kid_assistant.score import load_gold, score

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
MANIFEST = ROOT / "data" / "manifest.csv"
RAW_DIR = ROOT / "data" / "raw"
GOLD_DIR = ROOT / "gold"
RUNS_DIR = ROOT / "results" / "runs"


def model_digest(model: str) -> str | None:
    """Digest of the local model: a re-pulled model shows up as a different run."""
    for m in ollama.list().models:
        if m.model == model:
            return m.digest
    return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--run", required=True, help="name of the run, e.g. baseline")
    parser.add_argument(
        "--final", action="store_true", help="required for --split test (frozen run)"
    )
    args = parser.parse_args()

    if args.split == "test" and not args.final:
        sys.exit(
            "Refusing the test split without --final: it is run once, after the freeze."
        )
    out_dir = RUNS_DIR / args.run
    if out_dir.exists():
        sys.exit(
            f"{out_dir.relative_to(ROOT)} already exists: choose another --run name"
        )

    with MANIFEST.open(encoding="utf-8", newline="") as f:
        rows = [
            r
            for r in csv.DictReader(f)
            if r["split"] == args.split and r["language"] == "en"
        ]
    missing = [
        r["kid_id"] for r in rows if not (GOLD_DIR / f"{r['kid_id']}.json").exists()
    ]
    if missing:
        sys.exit(f"No gold file for: {', '.join(missing)}")

    fields = list(KidFacts.model_fields)
    value_ok = dict.fromkeys(fields, 0)
    page_ok = dict.fromkeys(fields, 0)
    invalid, retried, seconds = [], [], []
    digest = model_digest(MODEL)
    out_dir.mkdir(parents=True)

    for row in rows:
        kid_id = row["kid_id"]
        pdf = RAW_DIR / f"{kid_id}.pdf"
        if sha256(pdf) != row["sha256"]:
            sys.exit(f"{kid_id}: file differs from the manifest hash")
        start = time.perf_counter()
        result = extract(pdf, MODEL)
        seconds.append(time.perf_counter() - start)
        if result.attempts > 1:
            retried.append(kid_id)
        record = {
            "kid_id": kid_id,
            "kid_sha256": row["sha256"],
            "model": MODEL,
            "model_digest": digest,
            "options": OPTIONS,
            "max_attempts": MAX_ATTEMPTS,
            "attempts": result.attempts,
            "seconds": round(seconds[-1], 1),
            "prompt_tokens": [r.prompt_eval_count for r in result.responses],
            "raw": [r.message.content for r in result.responses],
            "errors": result.errors,
        }
        if result.facts is None:
            invalid.append(kid_id)
            record["valid"] = False
            print(f"{kid_id:42} INVALID after {result.attempts} attempts")
        else:
            scored = score(result.facts, load_gold(GOLD_DIR / f"{kid_id}.json"))
            record["valid"], record["score"] = True, scored
            for field, ok in scored.items():
                value_ok[field] += ok["value"]
                page_ok[field] += ok["page"]
            v = sum(ok["value"] for ok in scored.values())
            p = sum(ok["page"] for ok in scored.values())
            note = "  (after retry)" if result.attempts > 1 else ""
            print(
                f"{kid_id:42} values {v}/{len(fields)}  pages {p}/{len(fields)}{note}"
            )
        (out_dir / f"{kid_id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )

    n = len(rows) * len(fields)  # invalid outputs count as wrong on every field
    summary = {
        "run": args.run,
        "split": args.split,
        "model": MODEL,
        "model_digest": digest,
        "options": OPTIONS,
        "max_attempts": MAX_ATTEMPTS,
        "kids": len(rows),
        "invalid": invalid,
        "retried": retried,
        "values": f"{sum(value_ok.values())}/{n}",
        "pages": f"{sum(page_ok.values())}/{n}",
        "median_seconds": round(statistics.median(seconds), 1),
        "per_field": {f: {"values": value_ok[f], "pages": page_ok[f]} for f in fields},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"\n{'field':40} values  pages   (of {len(rows)} KIDs)")
    for f in fields:
        print(f"{f:40} {value_ok[f]:6} {page_ok[f]:6}")
    print(
        f"\nvalues {summary['values']}  pages {summary['pages']}  "
        f"invalid {len(invalid)}  retried {len(retried)}"
    )
    print(f"median {summary['median_seconds']} s/KID  model {MODEL} {digest}")


if __name__ == "__main__":
    main()
