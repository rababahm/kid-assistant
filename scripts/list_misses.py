"""List every value or page miss in the dev runs (week 2, build task 6)."""

import json
from pathlib import Path

RUNS = Path("results/runs")
GOLD = Path("gold")
RUN_ORDER = [
    "baseline",
    "change_a_cost_descriptions",
    "change_b_fund_name",
    "change_c_risk_page",
    "retry_loop",
    "grounding_check",
    "x_tolerance_2",
]


def last_reply(raw):
    if isinstance(raw, list):
        raw = raw[-1]
    return json.loads(raw) if isinstance(raw, str) else raw


def short(entry):
    if not isinstance(entry, dict):
        return repr(entry)
    keep = {k: v for k, v in entry.items() if k in ("value", "unit", "page", "pages")}
    return json.dumps(keep, ensure_ascii=False)


def main():
    rows = []
    for run_name in RUN_ORDER:
        for path in sorted((RUNS / run_name).glob("*.json")):
            if path.name == "summary.json":
                continue
            run = json.loads(path.read_text())
            kid = run["kid_id"]
            if not run.get("valid"):
                rows.append((kid, "-", run_name, "INVALID OUTPUT", "", ""))
                continue
            gold = json.loads((GOLD / f"{kid}.json").read_text())
            pred = last_reply(run["raw"])
            for field, ok in run["score"].items():
                if ok["value"] and ok["page"]:
                    continue
                flags = f"value_ok={ok['value']} page_ok={ok['page']}"
                rows.append(
                    (
                        kid,
                        field,
                        run_name,
                        flags,
                        short(gold.get(field)),
                        short(pred.get(field)),
                    )
                )
    order = {name: i for i, name in enumerate(RUN_ORDER)}
    for kid, field, run_name, flags, g, p in sorted(
        rows, key=lambda r: (r[0], r[1], order[r[2]])
    ):
        print(f"{kid} | {field} | {run_name} | {flags}\n    gold: {g}\n    pred: {p}")
    print(f"\n{len(rows)} misses")


if __name__ == "__main__":
    main()
