"""Parsing: page markers on any text (CI); a real KID only when it is on disk (local)."""

from pathlib import Path

import pytest

from kid_assistant.extract import format_pages, read_pages

REAL_KID = Path("data/raw/pictet_gold_i_usd.pdf")


def test_format_pages_numbers_markers_from_one_in_order():
    text = format_pages(["alpha", "beta", "gamma"])
    positions = [text.index(f"--- page {n} ---") for n in (1, 2, 3)]
    assert positions == sorted(positions)


def test_format_pages_puts_each_page_after_its_marker():
    text = format_pages(["alpha", "beta"])
    assert (
        text.index("--- page 1 ---")
        < text.index("alpha")
        < text.index("--- page 2 ---")
    )
    assert text.index("--- page 2 ---") < text.index("beta")


@pytest.mark.skipif(not REAL_KID.exists(), reason="KID PDFs are not in the repository")
def test_read_pages_on_a_real_kid():
    pages = read_pages(REAL_KID)
    assert len(pages) == 3
    assert all(page.strip() for page in pages)
    assert any("out of 7" in page for page in pages)
