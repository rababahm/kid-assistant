"""Extract facts from a fund's Key Information Document (KID) with a local Ollama model."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import ollama
import pdfplumber
from ollama import ChatResponse

from kid_assistant.schema import KidFacts

MODEL = "qwen3.5:4b"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "presence_penalty": 0}


def read_kid_text(pdf_path: str | Path) -> str:
    """Return the KID's text, with a '--- page N ---' marker before each page."""
    pages = []
    has_text = False
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):  # 1-based, as printed
            text = (page.extract_text() or "").strip()
            pages.append(f"--- page {number} ---\n{text}")
            has_text = has_text or bool(text)
    if not has_text:
        # A scanned PDF has no text layer: fail loudly rather than send empty pages.
        raise ValueError(f"No extractable text in {pdf_path}. A scan may need OCR.")
    return "\n\n".join(pages)


def build_prompt(kid_text: str) -> str:
    """Instruction, the JSON schema as text (Ollama's advice), then the document."""
    schema = json.dumps(KidFacts.model_json_schema())
    return (
        "Extract the facts below from this Key Information Document. Use only what the "
        "document states. For each value, give the page number from the preceding "
        "'--- page N ---' marker. Return one JSON object matching this schema.\n\n"
        f"Schema:\n{schema}\n\nKID text:\n{kid_text}"
    )


def extract(pdf_path: str | Path) -> tuple[KidFacts, ChatResponse]:
    """Run the model on one KID and validate its reply against the schema."""
    prompt = build_prompt(read_kid_text(pdf_path))
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        format=KidFacts.model_json_schema(),  # constrained decoding against the schema
        think=False,
        options=OPTIONS,
    )
    facts = KidFacts.model_validate_json(response.message.content)
    return facts, response


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="path to the KID PDF")
    parser.add_argument("--runs", type=int, default=3, help="number of repeated runs")
    args = parser.parse_args()

    print(f"model: {MODEL}  options: {OPTIONS}\n")
    for run in range(1, args.runs + 1):
        start = perf_counter()
        facts, response = extract(args.pdf_path)
        seconds = perf_counter() - start
        print(f"--- run {run}")
        print(facts.model_dump_json(indent=2))
        print(
            f"prompt tokens: {response.prompt_eval_count}  "
            f"output tokens: {response.eval_count}  seconds: {seconds:.1f}\n"
        )


if __name__ == "__main__":
    main()
