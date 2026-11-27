"""Extract facts from a fund's Key Information Document (KID) with a local Ollama model."""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

import ollama
import pdfplumber
from ollama import ChatResponse
from pydantic import ValidationError

from kid_assistant.grounding import grounding_problems
from kid_assistant.schema import KidFacts

MODEL = "qwen3.5:4b"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "presence_penalty": 0}
MAX_ATTEMPTS = 2  # the first answer plus one retry
# pdfplumber default 3 merges words in tightly set fonts (SPDR KID, 25 Nov);
# 2 changes no line on the 8 dev KIDs and restores the spaces.
PDF_X_TOLERANCE = 2


@dataclass
class Extraction:
    """Outcome of one KID: the facts (None if no valid answer) and the evidence."""

    facts: KidFacts | None
    responses: list[ChatResponse]  # every raw reply, in order
    errors: list[str]  # one entry per rejected attempt (invalid or ungrounded)
    ungrounded: list[str] = field(default_factory=list)  # flags left on the final facts

    @property
    def attempts(self) -> int:
        return len(self.responses)


def read_pages(pdf_path: str | Path) -> list[str]:
    """Text of each page (pdfplumber), in order: index 0 is page 1."""
    with pdfplumber.open(pdf_path) as pdf:
        return [
            (page.extract_text(x_tolerance=PDF_X_TOLERANCE) or "").strip()
            for page in pdf.pages
        ]


def format_pages(pages: list[str], source: str | Path = "the PDF") -> str:
    """Join pages with a '--- page N ---' marker before each, as the model sees them."""
    if not any(pages):
        # A scanned PDF has no text layer: fail loudly rather than send empty pages.
        raise ValueError(f"No extractable text in {source}. A scan may need OCR.")
    return "\n\n".join(
        f"--- page {n} ---\n{text}" for n, text in enumerate(pages, start=1)
    )


def read_kid_text(pdf_path: str | Path) -> str:
    """Return the KID's text, with a '--- page N ---' marker before each page."""
    return format_pages(read_pages(pdf_path), pdf_path)


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
    """Ask the model; retry once if the reply is invalid or a value is not on its page."""
    pages = read_pages(pdf_path)
    prompt = build_prompt(format_pages(pages, pdf_path))
    messages = [{"role": "user", "content": prompt}]
    responses, errors = [], []
    last_valid = None  # (facts, flags) of the most recent schema-valid answer
    for _ in range(MAX_ATTEMPTS):
        response = call_model(messages, model, chat)
        responses.append(response)
        try:
            facts = KidFacts.model_validate_json(response.message.content)
        except ValidationError as error:
            problems = describe_errors(error)
            feedback = "Your JSON failed validation:\n" + problems
        else:
            flags = grounding_problems(facts, pages)
            if not flags:
                return Extraction(facts, responses, errors)
            last_valid = (facts, flags)
            problems = "\n".join(f"- {flag}" for flag in flags)
            feedback = (
                "These values are not printed on the page you cited:\n"
                + problems
                + "\nCheck the document and correct each value or its page."
            )
        errors.append(problems)
        messages += [
            {"role": "assistant", "content": response.message.content},
            {
                "role": "user",
                "content": feedback + "\nReturn the corrected JSON object only.",
            },
        ]
    if last_valid is not None:  # keep a usable answer, with its flags, over no answer
        return Extraction(last_valid[0], responses, errors, ungrounded=last_valid[1])
    return Extraction(None, responses, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the facts of one KID as JSON, each value with its page."
    )
    parser.add_argument("pdf_path", type=Path, help="path to the KID PDF")
    args = parser.parse_args()
    if not args.pdf_path.is_file():
        parser.error(f"no such file: {args.pdf_path}")  # exits with code 2

    start = perf_counter()
    result = extract(args.pdf_path)
    last = result.responses[-1]
    print(
        f"model: {MODEL}  attempts: {result.attempts}  "
        f"seconds: {perf_counter() - start:.1f}  "
        f"prompt tokens: {last.prompt_eval_count}  output tokens: {last.eval_count}",
        file=sys.stderr,
    )
    if result.facts is None:
        print("FAILED after retry:\n" + "\n".join(result.errors), file=sys.stderr)
        sys.exit(1)
    print(result.facts.model_dump_json(indent=2))
    for flag in result.ungrounded:
        print(f"UNGROUNDED: {flag}", file=sys.stderr)


if __name__ == "__main__":
    main()
