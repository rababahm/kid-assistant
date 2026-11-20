"""Write each parser's output for every PDF in data/raw to parsed/<parser>/<kid_id>.txt.

Run with: uv run --group compare python scripts/compare_parsers.py
"""

import time
from pathlib import Path

import pdfplumber
import pymupdf
import pymupdf4llm

ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repository root
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "parsed"


def plain_pymupdf(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def markdown_pymupdf4llm(path: Path, layout: bool) -> list[str]:
    # Global switch: True = machine-learning layout model, False = classic rules.
    pymupdf4llm.use_layout(layout)
    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    return [chunk["text"] for chunk in chunks]


def pdfplumber_tables(path: Path) -> list[str]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts = [page.extract_text() or ""]
            for i, table in enumerate(page.extract_tables(), start=1):
                parts.append(f"\n--- table {i} ---")
                for row in table:
                    cells = [(cell or "").replace("\n", " ") for cell in row]
                    parts.append(" | ".join(cells))
            pages.append("\n".join(parts))
    return pages


PARSERS = {
    "pymupdf_text": plain_pymupdf,
    "pymupdf4llm_layout": lambda path: markdown_pymupdf4llm(path, layout=True),
    "pymupdf4llm_classic": lambda path: markdown_pymupdf4llm(path, layout=False),
    "pdfplumber": pdfplumber_tables,
}


def main() -> None:
    for name, parse in PARSERS.items():
        (OUT_DIR / name).mkdir(parents=True, exist_ok=True)
        for pdf_path in sorted(RAW_DIR.glob("*.pdf")):
            start = time.perf_counter()
            pages = parse(pdf_path)
            seconds = time.perf_counter() - start
            text = "".join(
                f"\n\n===== page {n} =====\n{page}"
                for n, page in enumerate(pages, start=1)
            )
            (OUT_DIR / name / f"{pdf_path.stem}.txt").write_text(text, encoding="utf-8")
            print(f"{name:20} {pdf_path.stem:38} {len(pages)} pages  {seconds:5.2f} s")


if __name__ == "__main__":
    main()
