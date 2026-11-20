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
