# Experiments

## Step 1: extraction, error analysis on the 8 dev KIDs (week 2, build task 6)

Model `qwen3.5:4b` (`7f3251fa6878`), temperature 0, seed 42, `num_ctx` 8192, `think=False`,
`presence_penalty` 0. 8 dev KIDs, 11 fields each: 88 values and 88 pages per run.
One change per run; every field scored on every run. Misses listed by `scripts/list_misses.py`
from the committed run files in `results/runs/`.

### Runs

| Run | Change | Values | Pages | Commit |
|---|---|---|---|---|
| baseline | schema of 23 Nov | 85/88 | 88/88 | `98b2812` |
| change_a_cost_descriptions | entry/exit: record the seller's maximum | 86/88 | 88/88 | `e88aacf` |
| change_b_fund_name | fund_name includes the share class | 88/88 | 87/88 | `55e4546` |
| change_c_risk_page | risk page: where "N out of 7" is printed | 88/88 | 88/88 | `778ba14` |
| retry_loop | one retry with the validation error | 88/88 | 88/88 | `7337a58` |
| grounding_check | value must be printed on its cited page, one retry | 88/88 | 88/88 | `bfab099` |
| x_tolerance_2 | pdfplumber `x_tolerance=2` | 88/88 | 88/88 | `05192a7` |

### Failures

6 miss rows, 4 distinct failures (two failures persisted across two runs).

| # | KID, field | Symptom | Cause | In runs | Fixed by |
|---|---|---|---|---|---|
| 1 | Carmignac Investissement, `fund_name` | share class dropped | schema description did not ask for the share class | baseline, A | B |
| 2 | Invesco EQQQ, `fund_name` | share class dropped; `(the "Fund")` copied in | as 1 | baseline, A | B |
| 3 | Carmignac Patrimoine, `entry_cost_pct` | 0 instead of 4.0 | schema description did not ask for the seller's "up to 4.00%"; "we do not charge" read as 0 | baseline | A |
| 4 | Invesco EQQQ, `risk_indicator` | right value, page 2 instead of 1 | side effect of change B (a different field); page 2 does not print the sentence | B | C |

Counts by cause: schema description 3; side effect of a change to another field 1;
parser lost it 0; invented value 0; wrong row 0.

### Findings

- All three baseline failures were specification errors: the gold conventions required
  something the schema descriptions did not ask for. The model followed its instructions.
- A change to one field's description moved another field's page (failure 4). This is why
  every field is scored on every change.
- Retry, grounding and `x_tolerance=2` changed nothing on dev: dev was already at 88/88.
  They are guards for cases dev does not contain.
- Dev is saturated (88/88, 95% Wilson interval 96 to 100%) and can no longer measure changes.
  A saturated score also hides fragility: on 23 Nov the Pictet I USD management fee flipped
  between 0.22 and 0.26 after a small description change, and no run here shows it.

### Decision: parser fallback

Trigger (set 20 Nov): Pictet KIDs (shaded tables) clearly worse, or misses tagged "parser
lost it". Result: 0 misses on the three Pictet dev KIDs in all 7 runs; 0 misses tagged
"parser lost it". Trigger not met, so no fallback is built. To watch on the test set:
Pictet TR Atlas uses the same shaded layout.
