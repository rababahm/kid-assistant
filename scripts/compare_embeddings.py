"""Compare three embedding models on the pages of the 8 dev KIDs (provisional pick, week 3).

A: plain pages, question with the fund name, search over all pages.
B: plain pages, question without the name, search only the right fund's pages (fund filter).
C: fund name prepended to every page, question with the name, search over all pages.
"""

import csv
import json
from pathlib import Path

import numpy as np
import ollama

from kid_assistant.extract import read_pages

MODELS = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "qwen3-embedding:0.6b": (
        (
            "Instruct: Given a web search query, retrieve relevant passages that "
            "answer the query\nQuery: "
        ),
        "",
    ),
}
TEMPLATES = {
    "risk_indicator": "What is the risk indicator of {name}?",
    "recommended_holding_period": "How long should I hold {name}?",
    "entry_cost_pct": "What are the entry costs of {name}?",
    "management_fees_and_other_costs_pct": "What are the ongoing management fees of {name}?",
    "transaction_costs_pct": "What are the transaction costs of {name}?",
    "performance_fee_pct": "Does {name} charge a performance fee?",
}
QUESTIONS = [
    ("pictet_gold_i_usd", "management_fees_and_other_costs_pct"),
    ("pictet_gold_p_usd", "management_fees_and_other_costs_pct"),
    ("ishares_msci_world_usd_acc", "risk_indicator"),
    ("ishares_usd_treasury_1_3yr_dist", "recommended_holding_period"),
    ("carmignac_investissement_a_eur_acc", "performance_fee_pct"),
    ("carmignac_patrimoine_a_eur_acc", "entry_cost_pct"),
    ("pictet_st_mm_usd_p", "recommended_holding_period"),
    ("invesco_eqqq_nasdaq100_dist", "risk_indicator"),
    ("carmignac_patrimoine_a_eur_acc", "risk_indicator"),
    ("ishares_msci_world_usd_acc", "transaction_costs_pct"),
]


def dev_kids() -> list[str]:
    with open("data/manifest.csv", newline="", encoding="utf-8") as f:
        return [row["kid_id"] for row in csv.DictReader(f) if row["split"] == "dev"]


def embed(model: str, texts: list[str]) -> np.ndarray:
    # truncate=False: fail loudly if a page is longer than the model's input limit
    return np.array(ollama.embed(model=model, input=texts, truncate=False).embeddings)


def evaluate(P, Q, labels, gold, within_fund):
    """hit@1, number of top-1 pages from the wrong fund, and a short note per miss."""
    hits, wrong_fund, misses = 0, 0, []
    ranking = np.argsort(-(Q @ P.T), axis=1)
    for number, ((kid, field), order) in enumerate(zip(QUESTIONS, ranking), start=1):
        if within_fund:
            order = [i for i in order if labels[i][0] == kid]
        top_kid, top_page = labels[order[0]]
        if top_kid == kid and top_page in gold[kid][field]["pages"]:
            hits += 1
        else:
            wrong_fund += top_kid != kid
            where = f"p{top_page}" if top_kid == kid else f"{top_kid} p{top_page}"
            misses.append(f"q{number}->{where}")
    return hits, wrong_fund, misses


def main() -> None:
    kids = dev_kids()
    passages, labels = [], []
    for kid in kids:
        for page_number, text in enumerate(read_pages(f"data/raw/{kid}.pdf"), start=1):
            passages.append(text)
            labels.append((kid, page_number))
    gold = {kid: json.loads(Path(f"gold/{kid}.json").read_text()) for kid in kids}
    names = {kid: gold[kid]["fund_name"]["value"] for kid in kids}
    named = [TEMPLATES[f].format(name=names[k]) for k, f in QUESTIONS]
    topic = [TEMPLATES[f].format(name="this fund") for k, f in QUESTIONS]
    with_header = [f"{names[kid]}\n{text}" for text, (kid, _) in zip(passages, labels)]

    n = len(QUESTIONS)
    print(f"{len(passages)} passages from {len(kids)} dev KIDs, {n} questions")
    for number, ((kid, field), question) in enumerate(zip(QUESTIONS, named), start=1):
        print(f"  q{number}: {question}  [gold p{gold[kid][field]['pages']}]")
    print(
        f"\n{'model':24} A plain (wrong fund)   B filter+topic   C header (wrong fund)"
    )

    notes = []
    for model, (q_prefix, p_prefix) in MODELS.items():
        P = embed(model, [p_prefix + p for p in passages])
        P_header = embed(model, [p_prefix + p for p in with_header])
        Q_named = embed(model, [q_prefix + q for q in named])
        Q_topic = embed(model, [q_prefix + q for q in topic])
        a = evaluate(P, Q_named, labels, gold, within_fund=False)
        b = evaluate(P, Q_topic, labels, gold, within_fund=True)
        c = evaluate(P_header, Q_named, labels, gold, within_fund=False)
        print(
            f"{model:24} {a[0]:>2}/{n} ({a[1]})"
            f"            {b[0]:>2}/{n}"
            f"            {c[0]:>2}/{n} ({c[1]})"
        )
        notes.append(
            f"{model}\n    B misses: {' '.join(b[2]) or 'none'}"
            f"\n    C misses: {' '.join(c[2]) or 'none'}"
        )

    print("\n" + "\n".join(notes))


if __name__ == "__main__":
    main()
