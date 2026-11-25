"""Extract facts from a fund's Key Information Document (KID) with a local Ollama model."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import ollama
import pdfplumber
from ollama import ChatResponse
from pydantic import ValidationError

from kid_assistant.schema import KidFacts

MODEL = "qwen3.5:4b"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "presence_penalty": 0}
MAX_ATTEMPTS = 2  # the first answer plus one retry


@dataclass
class Extraction:
    """Outcome of one KID: the facts (None if every attempt failed) and the evidence."""

    facts: KidFacts | None
    responses: list[ChatResponse]  # every raw reply, in order
    errors: list[str]  # one entry per failed attempt

    @property
    def attempts(self) -> int:
        return len(self.responses)


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


def call_model(
    messages: list[dict], model: str = MODEL, chat=ollama.chat
) -> ChatResponse:
    """One model call, constrained to the schema. `chat` is replaceable by a fake in tests."""
    return chat(
        model=model,
        messages=messages,
        format=KidFacts.model_json_schema(),  # constrained decoding against the schema
        think=False,
        options=OPTIONS,
    )


def ask_model(pdf_path: str | Path, model: str = MODEL) -> ChatResponse:
    """Single call on one KID, no retry (kept for scripts/compare_models.py)."""
    prompt = build_prompt(read_kid_text(pdf_path))
    return call_model([{"role": "user", "content": prompt}], model)


def describe_errors(error: ValidationError) -> str:
    """Short list of what failed, readable by the model: '- field.sub: message'."""
    return "\n".join(
        f"- {'.'.join(str(p) for p in e['loc']) or 'output'}: {e['msg']}"
        for e in error.errors()
    )


def extract(pdf_path: str | Path, model: str = MODEL, chat=ollama.chat) -> Extraction:
    """Ask the model; if the reply fails validation, retry once with the errors."""
    prompt = build_prompt(read_kid_text(pdf_path))
    messages = [{"role": "user", "content": prompt}]
    responses, errors = [], []
    for _ in range(MAX_ATTEMPTS):
        response = call_model(messages, model, chat)
        responses.append(response)
        try:
            facts = KidFacts.model_validate_json(response.message.content)
        except ValidationError as error:
            errors.append(describe_errors(error))
            messages += [
                {"role": "assistant", "content": response.message.content},
                {
                    "role": "user",
                    "content": "Your JSON failed validation:\n"
                    + errors[-1]
                    + "\nReturn the corrected JSON object only.",
                },
            ]
        else:
            return Extraction(facts, responses, errors)
    return Extraction(None, responses, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="path to the KID PDF")
    parser.add_argument("--runs", type=int, default=3, help="number of repeated runs")
    args = parser.parse_args()

    print(f"model: {MODEL}  options: {OPTIONS}\n")
    for run in range(1, args.runs + 1):
        start = perf_counter()
        result = extract(args.pdf_path)
        seconds = perf_counter() - start
        print(f"--- run {run}  attempts: {result.attempts}  seconds: {seconds:.1f}")
        if result.facts is None:
            print("FAILED after retry:\n" + "\n".join(result.errors))
        else:
            print(result.facts.model_dump_json(indent=2))
        last = result.responses[-1]
        print(
            f"prompt tokens: {last.prompt_eval_count}  output tokens: {last.eval_count}\n"
        )


if __name__ == "__main__":
    main()
