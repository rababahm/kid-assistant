# Step 1 results: extraction on the 12 held-out test KIDs

One run, made once, with the code, schema, prompt and gold labels frozen at tag `step1-freeze`
(run files committed in `c822ee0`, folder `results/runs/test_v1/`). No change was made after the run.

## Setup

- Model: `qwen3.5:4b`, digest `7f3251fa6878...`, Ollama 0.40.16 (Mac, mlx runner).
- Options: temperature 0, seed 42, `num_ctx` 8192, `think=False`, `presence_penalty` 0.
- Schema `KidFacts` passed in `format`; one retry on a validation error; grounding check
  (value printed on its cited page) with one retry.
- Parser: pdfplumber 0.11.10, `extract_text(x_tolerance=2)`, page markers.
- Data: 20 English KIDs from 9 providers, split by document: 8 dev KIDs for all tuning,
  12 test KIDs used only for this run. Share-class pairs kept in one split.
- Gold labels made by hand from the PDFs (regex helper, no model), each value with its pages
  and a quote.

## Results

| Measure | Result | 95% Wilson interval |
|---|---|---|
| Values correct | 131/132 (99.2%) | 95.8 to 99.9% |
| Cited page correct | 132/132 (100%) | 97.2 to 100% |
| KIDs with all 11 fields correct | 11/12 | 64.6 to 98.5% |
| Schema-valid outputs | 12/12 | |
| Retries triggered / values flagged ungrounded | 0 / 0 | |
| Median time per KID (MacBook Air M2, 8 GB) | 30.1 s | |

The 132 values are not independent: the 11 fields of one KID share a layout and a parse, so
errors cluster by document. The field-level interval is therefore too narrow; the KID-level row
is the conservative view.

For comparison, the 8 dev KIDs reached 88/88 values and pages after tuning. That number was
used to choose changes, so it is not an estimate of accuracy.

## The one miss

| KID | Field | Gold | Model | Cause |
|---|---|---|---|---|
| SPDR MSCI World Small Cap | `entry_cost_pct` | 0.0, `is_maximum` true | 0.0, `is_maximum` false | Judgement on wording ("This is the most you will pay") attached to a 0.00% rate printed on a different line from its label |

The number and page were right. `is_maximum` is not checked by the validators or the grounding
check, so no runtime layer could catch this. The gold convention (fixed before the run) was
not changed after seeing the result.

## Disclosures

- `x_tolerance=2` was found while labelling a test KID (SPDR, merged words at the default 3).
  It was judged on dev only (0 dev lines changed, dev unchanged at 88/88) before the freeze.
- The retry and grounding guards never fired on the test set; this run gives no evidence that
  they help, only that they did not harm.
