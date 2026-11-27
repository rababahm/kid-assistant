"""The kid-extract command: JSON on stdout, diagnostics on stderr, exit codes."""

import json
import sys
from types import SimpleNamespace

import pytest

from kid_assistant import extract as extract_module
from kid_assistant.extract import Extraction


def fake_response():
    return SimpleNamespace(prompt_eval_count=100, eval_count=10)


def run_cli(monkeypatch, tmp_path, result):
    pdf = tmp_path / "kid.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(extract_module, "extract", lambda path: result)
    monkeypatch.setattr(sys, "argv", ["kid-extract", str(pdf)])
    extract_module.main()


def test_stdout_is_only_the_json(monkeypatch, tmp_path, capsys, make_facts):
    run_cli(monkeypatch, tmp_path, Extraction(make_facts(), [fake_response()], []))
    output = capsys.readouterr()
    assert json.loads(output.out)["isin"]["value"] == "LU0000000001"
    assert "attempts: 1" in output.err


def test_no_valid_answer_exits_with_code_1(monkeypatch, tmp_path):
    failed = Extraction(None, [fake_response()] * 2, ["bad", "bad"])
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, tmp_path, failed)
    assert exit_info.value.code == 1


def test_missing_file_exits_with_code_2(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["kid-extract", str(tmp_path / "missing.pdf")])
    with pytest.raises(SystemExit) as exit_info:
        extract_module.main()
    assert exit_info.value.code == 2
