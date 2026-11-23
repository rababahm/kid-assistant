"""Run each candidate model on every KID in the manifest and score it against gold/.

Run with: uv run python scripts/compare_models.py
Raw replies are saved in results/model_runs/<model>/<kid_id>.json.
"""

import csv
import json
import statistics
import time
from pathlib import Path

import ollama
from pydantic import ValidationError

from kid_assistant.extract import OPTIONS, ask_model
from kid_assistant.schema import KidFacts
from kid_assistant.score import load_gold, score

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
MANIFEST = ROOT / "data" / "manifest.csv"
RAW_DIR = ROOT / "data" / "raw"
GOLD_DIR = ROOT / "gold"
RUNS_DIR = ROOT / "results" / "model_runs"
MODELS = ["qwen3.5:4b", "llama3.2:3b", "phi4-mini"]


def loaded_size_gb(model: str) -> float | None:
    """Memory the loaded model uses, as reported by Ollama (same as `ollama ps`)."""
    for m in ollama.ps().models:
        if m.model.startswith(model):
            return round(m.size / 1e9, 1)
    return None


def main() -> None:
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        kids = [row["kid_id"] for row in csv.DictReader(f)]
    fields = list(KidFacts.model_fields)
    summary = {}  # model -> measures
    per_field = {}  # model -> field -> number of KIDs with the right value

    for model in MODELS:
        out_dir = RUNS_DIR / model.replace(":", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        valid = values_ok = pages_ok = 0
        seconds, memory = [], None
        per_field[model] = dict.fromkeys(fields, 0)
        for kid_id in kids:
            start = time.perf_counter()
            response = ask_model(RAW_DIR / f"{kid_id}.pdf", model)
            seconds.append(time.perf_counter() - start)
            memory = memory or loaded_size_gb(model)
            record = {
                "model": model,
                "options": OPTIONS,
                "kid_id": kid_id,
                "seconds": round(seconds[-1], 1),
                "prompt_tokens": response.prompt_eval_count,
                "raw": response.message.content,
            }
            try:
                facts = KidFacts.model_validate_json(response.message.content)
            except ValidationError as error:
                record["valid"] = False
                record["error"] = str(error)
                print(f"{model:12} {kid_id:36} INVALID")
            else:
                valid += 1
                result = score(facts, load_gold(GOLD_DIR / f"{kid_id}.json"))
                record["valid"], record["score"] = True, result
                for field, ok in result.items():
                    values_ok += ok["value"]
                    pages_ok += ok["page"]
                    per_field[model][field] += ok["value"]
                n_right = sum(ok["value"] for ok in result.values())
                print(f"{model:12} {kid_id:36} {n_right}/{len(fields)} values right")
            (out_dir / f"{kid_id}.json").write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
        ollama.generate(
            model=model, prompt="", keep_alive=0
        )  # unload before the next model
        n = len(kids) * len(fields)
        summary[model] = {
            "valid": f"{valid}/{len(kids)}",
            "values": f"{values_ok}/{n}",
            "pages": f"{pages_ok}/{n}",
            "median_s": round(statistics.median(seconds), 1),
            "memory_gb": memory,
        }

    print("\nmodel         valid  values  pages   median s/KID  memory GB")
    for model, s in summary.items():
        print(
            f"{model:12}  {s['valid']:5}  {s['values']:6}  {s['pages']:6}  "
            f"{s['median_s']:12}  {s['memory_gb']}"
        )
    print(f"\nRight values per field (of {len(kids)} KIDs):")
    print("field".ljust(38) + "".join(m.ljust(14) for m in MODELS))
    for field in fields:
        print(
            field.ljust(38)
            + "".join(str(per_field[m][field]).ljust(14) for m in MODELS)
        )


if __name__ == "__main__":
    main()
