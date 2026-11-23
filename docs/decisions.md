# Decisions

Each decision records what was chosen, the evidence, and when to revisit it.

## 1. PDF parser: pdfplumber (20 Nov 2026)

**Compared:** four parser variants on the six pilot (dev) KIDs, with
`scripts/compare_parsers.py` (outputs in `parsed/`, not committed) and
`scripts/check_parsers.py` (evidence in `parsed/check_report.txt`).

| Parser | Version | Licence | Checks passed (of 72) | Lost words (6 KIDs) | Seconds per KID |
|---|---|---|---|---|---|
| pdfplumber (text + tables) | 0.11.10 | MIT | 62 | 0 | 0.2 to 0.3 |
| PyMuPDF4LLM, layout model | 2.1 | AGPL | 70 | 53 | 0.7 to 2.2 |
| PyMuPDF4LLM, classic | 2.1 | AGPL | 54 | 137 | 0.4 to 1.2 |
| PyMuPDF plain text | 2.1 | AGPL | 30 | 0 (reference) | < 0.05 |

Checks per KID: 3 pages; ISIN and date on page 1; risk sentence; recommended
holding period; each of the five cost rows with its value on the same line;
"Total costs" with both horizons; the "Moderate" scenario row with both amounts.
Lost words: words that appear fewer times than in plain PyMuPDF text.

**What the checks do not show:** the layout model passes the row checks while
removing text. Confirmed by hand: Pictet's "Unfavourable" and "Favourable"
scenario labels are missing; iShares "Total costs" and "Annual cost impact"
labels are missing and spaces are removed ("Ifyou exit after 1year"); a
Carmignac heading is split and placed inside the Transaction costs row.

**Reasoning:** I chose pdfplumber because it was the only structured parser that kept every word of all six KIDs, and in a financial document, text fidelity is a hard requirement: an interleaved table still contains every label and value for the model or a validator to work with, but a deleted label such as “Unfavourable” or “Total costs” cannot be recovered by anything downstream. The layout model scored higher on the row checks, but those checks only test whether a label and a value share a line, not whether the right label is there, and it also adds a machine-learning dependency that is slower and not yet checked for repeatable output. pdfplumber is rule-based, fast, and MIT-licensed, while PyMuPDF and PyMuPDF4LLM are AGPL, which matters for reuse inside a company.

**Known weaknesses of pdfplumber:**
- Tables drawn with shading instead of lines (Pictet) are not detected: rows
  come out interleaved, and the Pictet scenario rows are not joined.
- Text and table output repeat the same content; choose one representation
  in `parse.py`.
- Not yet measured: wrong cell boundaries inside detected tables; layouts not
  in the pilot set (two columns, other providers).

**Revisit when:** the model comparison or the week 2 error analysis shows the
Pictet KIDs scoring clearly worse, or misses tagged "parser lost it". A
fallback would be chosen on a property measured in the document (for example,
no table found on the cost page) and accepted only if no words are lost
compared with plain text, never on the provider's name.

## 2. Generation model: qwen3.5:4b (23 Nov 2026)

**Compared:** three local models on the six pilot (dev) KIDs, one extraction each,
with `scripts/compare_models.py` (raw replies in `results/model_runs/`), scored
against `gold/` with `src/kid_assistant/score.py`. Settings for all: schema in
`format`, `think=False`, temperature 0, seed 42, `num_ctx` 8192, `presence_penalty` 0.

| Model | Ollama ID | Schema-valid | Values right (95% CI) | Pages right (95% CI) | Median s/KID | Memory |
|---|---|---|---|---|---|---|
| qwen3.5:4b | 7f3251fa6878 | 6/6 | 64/66 = 97% (90-99) | 66/66 = 100% (94-100) | 28.5 | 4.2 GB |
| phi4-mini | 78fad5d182a7 | 6/6 | 62/66 = 94% (85-98) | 46/66 = 70% (58-79) | 23.8 | 3.7 GB |
| llama3.2:3b | a80c4f17acd5 | 6/6 | 54/66 = 82% (71-89) | 41/66 = 62% (50-73) | 16.9 | 3.1 GB |

**Reasoning:** On values, qwen3.5:4b and phi4-mini cannot be separated with 66
values (2 against 4 misses, overlapping intervals). On pages they can: qwen3.5:4b
cited the right page for all 66 values, while phi4-mini cited page 2 for most
page-3 costs. Correct pages are required for citations in step 2, so qwen3.5:4b
is chosen, at the cost of about 5 seconds more per KID and 0.5 GB more memory.
llama3.2:3b missed entry and exit costs on every KID.

**Known issues (dev set, to fix in week 2):**
- Entry costs where the manufacturer charges nothing but the seller may charge
  up to a maximum (Carmignac, Pictet): the schema does not say which to record.
  The gold labels record the maximum; the description must say so.
- Pictet I USD management fees: 0.26 instead of 0.22 in some runs (with the
  default `presence_penalty`, and after a small schema change). The value is not
  on the page; a check that every value appears on its cited page would catch it.
- Sample: 6 KIDs, one run each, dev set only. These numbers are for choosing,
  not for reporting.
