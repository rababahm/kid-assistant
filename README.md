# KID assistant

An assistant for the Key Information Documents (KIDs) of investment funds, built with a small
language model running locally (Ollama, `qwen3.5:4b` on a MacBook Air M2 with 8 GB).

**Status: step 1 of 4 finished.** Structured extraction of the risk indicator, costs and other
key facts from a KID, each value with the page it was found on. Next: question answering over
20 KIDs with page citations (retrieval-augmented generation).

## What a KID is

A KID is the three-page document that EU and Swiss rules (PRIIPs) require for investment funds
sold to retail investors. Its layout is fixed by regulation: what the product is, a risk
indicator from 1 to 7, performance scenarios, costs, and how long to hold it. The facts are
public, but every provider prints them differently, which makes them a good test for extraction.

## What step 1 does

```
uv run kid-extract data/raw/pictet_gold_i_usd.pdf
```

prints a validated JSON object with 11 fields, each with its page (excerpt):

```json
"kid_date": {"value": "06-02-2026", "page": 1},
"risk_indicator": {"value": 4, "page": 2},
"recommended_holding_period": {"value": 5.0, "unit": "years", "page": 2},
"entry_cost_pct": {"value": 5.0, "page": 3, "is_maximum": true},
"management_fees_and_other_costs_pct": {"value": 0.22, "page": 3},
```

Fields: fund name (with share class), ISIN, manufacturer, KID date, risk indicator, recommended
holding period, entry, exit, management and transaction costs, performance fee. Costs carry
`is_maximum`: "up to 5%" is not the same fact as "5%". Diagnostics (attempts, time, tokens) go
to stderr; exit code 1 if no valid answer, 2 for a usage error.

## Results

Measured once on 12 held-out KIDs (7 providers), with code, prompt and labels frozen at tag
`step1-freeze` before the run. Details: [`results/extraction.md`](results/extraction.md).

| Measure | Result | 95% Wilson interval |
|---|---|---|
| Values correct | 131/132 (99.2%) | 95.8 to 99.9% |
| Cited page correct | 132/132 (100%) | 97.2 to 100% |
| KIDs with all 11 fields correct | 11/12 | 64.6 to 98.5% |
| Schema-valid outputs | 12/12 | |
| Median time per KID (M2, 8 GB) | 30.1 s | |

The one miss: the SPDR KID prints a 0.00% entry cost with "This is the most you will pay"; the
model returned 0.0 correctly but `is_maximum` false. The 132 values are not independent (fields
of one KID share a layout), so the KID-level row is the conservative view.

## How it was measured

- **Data:** 20 English KIDs from 9 providers (Pictet, iShares, Carmignac, Invesco, Mirabaud,
  SPDR, Vanguard, VanEck, Lombard Odier), risk classes 1 to 6, domiciles CH, IE, LU and FR.
- **Split by document:** 8 development KIDs for every choice and prompt change; 12 test KIDs
  touched once, for the table above. Share-class pairs (same fund, different costs) are kept in
  one split.
- **Gold labels by hand:** each value with all pages that print it and an exact quote, checked
  against the PDF. Pre-filled by regular expressions for mechanical fields only, never by a model.
- **Choices from measurements:** parser (4 compared, [`docs/decisions.md`](docs/decisions.md)),
  model (3 compared on pages and values), and each prompt change scored on every field
  ([`docs/experiments.md`](docs/experiments.md)). After tuning, the development set reached
  88/88; that number was used to choose changes, so it is not an accuracy estimate.

## How it works

1. **Parse:** pdfplumber text per page, with `--- page N ---` markers.
2. **Constrained generation:** the Pydantic schema is passed to Ollama as the output format, so
   the reply is always valid JSON of the right shape. Temperature 0, fixed seed, thinking off,
   context set explicitly to 8,192 tokens.
3. **Validation with one retry:** impossible values (risk 9, a cost of 120%) are rejected and
   the error is sent back to the model once.
4. **Grounding with one retry:** code checks that each value is printed on the page it cites;
   if not, the model is told which values to check. Values still not found are kept and flagged.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com) running.
8 GB of memory is enough (the model uses 4.1 to 4.7 GB on an M2; close other heavy apps).
Tested on macOS only.

```
git clone https://github.com/rababahm/kid-assistant.git
cd kid-assistant
uv sync
ollama pull qwen3.5:4b
uv run python scripts/download_kids.py
uv run kid-extract data/raw/pictet_gold_i_usd.pdf
make test
```

The download step lists the KIDs that must be fetched by hand (see Data) and exits with code 1
until they are in place. The extraction example and the tests only need
`pictet_gold_i_usd.pdf`, which the script downloads.

## Data

KID PDFs are **not** in this repository. [`data/manifest.csv`](data/manifest.csv) lists each
KID (fund, share class, ISIN, provider, language, URL, download date, KID date, SHA-256, split),
and `scripts/download_kids.py` downloads them into `data/raw/` and checks each hash, because
providers replace KIDs in place.

Some KIDs cannot be downloaded by a script, because the provider's site asks for country and
investor type first. The script reports these as `MANUAL` (no URL in the manifest) or
`NOT A PDF` (the URL now returns the provider's selection page). Download each by hand from the
provider's site, save it as `data/raw/<kid_id>.pdf`, and run the script again: it checks the
hash of each file like the others. On 27 November 2026, 12 of the 24 KIDs needed this.

If the script reports `CHANGED`, the provider has published a new version of that KID; results
on it may differ from the reported run.

## Reproducing the results

```
git checkout step1-freeze
uv run python scripts/run_extraction.py --split test --run my_test_run --final
```

`--final` is required for the test split, and an existing run folder is never overwritten.
Temperature 0 and a fixed seed make runs repeatable: the same KID extracted from two separate
clones on one machine gave identical output. Another Ollama version or another machine may
differ slightly. The run files of the reported run are in `results/runs/test_v1/`.

## Tests

`make test` runs 86 offline tests in under a second, with no model and no PDF: schema
constraints, scoring, grounding, the retry loop with a fake model, and the command line. One
test parses a real KID and is skipped when the PDFs are absent, as in CI. GitHub Actions runs
lint and the tests on every push.

## Limitations

- 20 documents, English only, one local 4B model; results on other providers or languages are
  not measured.
- The test set is small: 12 KIDs give wide intervals, and errors cluster by document.
- The development set is saturated (88/88), so changes after that point were not measurable on it.
- Seller fees stated without a figure ("the person selling you the product may charge") are
  recorded as 0.
- `x_tolerance=2` in the parser was found while labelling a test KID. It was judged on
  development KIDs only (no line changed) before the freeze.
- The retry and grounding checks never fired on the test set, so this run gives no evidence that
  they help.
- Grounding cannot catch a wrong 0 or the right number taken from the wrong row on the right
  page; `is_maximum` is not checked at run time.
- Two grounding bugs (rounded number forms, empty strings counted as found) were found by tests
  after the frozen run and fixed. They cannot have changed the reported numbers: every value in
  that run was printed exactly as returned, and none was flagged.

## Repository layout

```
src/kid_assistant/   schema.py, extract.py (kid-extract), grounding.py, score.py
scripts/             download_kids.py, run_extraction.py, gold_helper.py, list_misses.py, ...
data/manifest.csv    the 24 KIDs (20 English, 4 French kept for later)
gold/                hand-made labels, one file per English KID
results/             run files and extraction.md
docs/                decisions.md, experiments.md
tests/               offline test suite
```
