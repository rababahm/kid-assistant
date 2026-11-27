"""The retry loop in extract(), with a fake model and fake pages: no Ollama, no PDF."""

from types import SimpleNamespace

import pytest

from kid_assistant import extract as extract_module
from kid_assistant.extract import MAX_ATTEMPTS, extract
from kid_assistant.schema import KidFacts

BAD_JSON = "not json"


class FakeChat:
    """Returns the scripted replies in order and records a copy of every call."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        content = self.replies[len(self.calls) - 1]
        return SimpleNamespace(message=SimpleNamespace(content=content))


@pytest.fixture(autouse=True)
def fake_pages(monkeypatch, pages):
    monkeypatch.setattr(extract_module, "read_pages", lambda path: pages)


@pytest.fixture
def ungrounded_json(make_facts):
    facts = make_facts(management_fees_and_other_costs_pct={"value": 0.26})
    return facts.model_dump_json()


def test_good_first_answer_needs_one_call(facts_json):
    chat = FakeChat(facts_json)
    result = extract("fake.pdf", chat=chat)
    assert result.attempts == 1
    assert result.facts is not None
    assert result.errors == [] and result.ungrounded == []


def test_call_uses_schema_and_deterministic_settings(facts_json):
    chat = FakeChat(facts_json)
    extract("fake.pdf", chat=chat)
    call = chat.calls[0]
    assert call["format"] == KidFacts.model_json_schema()
    assert call["think"] is False
    assert call["options"]["temperature"] == 0
    assert call["options"]["seed"] == 42


def test_invalid_then_valid_retries_once_with_the_error(facts_json):
    chat = FakeChat(BAD_JSON, facts_json)
    result = extract("fake.pdf", chat=chat)
    assert result.attempts == 2
    assert result.facts is not None
    assert len(result.errors) == 1
    retry_messages = chat.calls[1]["messages"]
    assert [m["role"] for m in retry_messages] == ["user", "assistant", "user"]
    assert retry_messages[1]["content"] == BAD_JSON
    assert "failed validation" in retry_messages[2]["content"]


def test_always_invalid_gives_no_facts_and_no_crash():
    chat = FakeChat(*[BAD_JSON] * MAX_ATTEMPTS)
    result = extract("fake.pdf", chat=chat)
    assert result.attempts == MAX_ATTEMPTS
    assert result.facts is None
    assert len(result.errors) == MAX_ATTEMPTS


def test_ungrounded_then_grounded_retries_and_names_the_field(facts_json, ungrounded_json):
    chat = FakeChat(ungrounded_json, facts_json)
    result = extract("fake.pdf", chat=chat)
    assert result.attempts == 2
    assert result.ungrounded == []
    feedback = chat.calls[1]["messages"][-1]["content"]
    assert "management_fees_and_other_costs_pct" in feedback


def test_always_ungrounded_keeps_the_facts_and_flags_them(ungrounded_json):
    chat = FakeChat(ungrounded_json, ungrounded_json)
    result = extract("fake.pdf", chat=chat)
    assert result.facts.management_fees_and_other_costs_pct.value == 0.26
    assert len(result.ungrounded) == 1
    assert result.ungrounded[0].startswith("management_fees_and_other_costs_pct")


def test_ungrounded_then_invalid_keeps_the_first_answer(ungrounded_json):
    chat = FakeChat(ungrounded_json, BAD_JSON)
    result = extract("fake.pdf", chat=chat)
    assert result.attempts == 2
    assert result.facts.management_fees_and_other_costs_pct.value == 0.26
    assert len(result.ungrounded) == 1
    assert len(result.errors) == 2
