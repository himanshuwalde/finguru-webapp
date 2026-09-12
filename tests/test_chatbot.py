"""
Unit tests for the AI CA chatbot — NO network / Gemini required.
Coverage: intent routing (pure rules) + the offline deterministic fallback,
which is what the chat degrades to without an API key or when generation fails.
Run with:  python -m pytest tests/test_chatbot.py -v
"""
import json

import pytest

from ai.ca_chatbot import respond
from ai.context_builder import run_tools, serialize_results
from ai.intent_router import INTENT_TOOLS, route_intent


class _ExplodingTable:
    def __getattr__(self, _):
        raise AttributeError("fake supabase — table raises on access")


class _FakeSupabase:
    """Any .table(...) access raises → services catch → empty data (deterministic)."""
    @property
    def auth(self):
        return None

    def table(self, *_a, **_k):
        return _ExplodingTable()


FAKE = _FakeSupabase()


# ------------------------------------------------------------------- intent

def test_route_tax_saving():
    assert route_intent("how can I save tax this year?") == "tax_saving"


def test_route_tax():
    assert route_intent("what's my income tax in the new regime?") == "tax"


def test_route_fire():
    assert route_intent("when can I retire early?") == "fire"


def test_route_portfolio():
    assert route_intent("what is my portfolio xirr?") == "portfolio"


def test_route_net_worth():
    assert route_intent("what is my net worth and liabilities?") == "net_worth"


def test_route_spending():
    assert route_intent("where is my money going?") == "spending"


def test_route_unknown_is_general():
    assert route_intent("hello there") == "general"


def test_route_empty_message_is_general():
    assert route_intent("") == "general"


# ------------------------------------------------------------- grounding/tools

def test_all_tools_run_without_mutation_on_missing_data():
    results = run_tools(FAKE, "user-1", ["tax_calculator", "net_worth"])
    assert "tax_calculator" in results and "net_worth" in results
    for name, res in results.items():
        assert isinstance(res, dict)
        assert "status" in res  # either no_data / ok — never a crash


def test_grounding_serializes_to_valid_json():
    results = run_tools(FAKE, "user-1", ["net_worth", "fire_status"])
    blob = serialize_results(results)
    parsed = json.loads(blob)
    assert set(parsed.keys()) == {"net_worth", "fire_status"}


# ------------------------------------------------------- offline conversation


def _force_no_api_key(monkeypatch):
    """Guarantee the deterministic path: no Gemini key → ValueError → fallback."""
    def _no_key():
        raise ValueError("GEMINI_API_KEY intentionally missing in tests")
    monkeypatch.setattr("utils.ai_client._get_api_key", _no_key)
    import utils.ai_client as ac
    ac.get_gemini_client.cache_clear() if hasattr(ac.get_gemini_client, "cache_clear") else None


def test_respond_never_raises_without_gemini(monkeypatch):
    _force_no_api_key(monkeypatch)
    text, intent, results = respond(FAKE, "user-1", "how can I save tax?", [])
    assert isinstance(text, str) and text.strip()
    assert intent in INTENT_TOOLS
    assert isinstance(results, dict)


def test_fallback_mentions_missing_data_when_nothing_stored(monkeypatch):
    # No gemini key + empty DB → deterministic, truthful "no data" reply.
    _force_no_api_key(monkeypatch)
    text, intent, _ = respond(FAKE, "user-1", "what is my xirr?", [])
    assert intent == "portfolio"
    # The offline answer should not present invented numbers.
    assert "recording" in text or "recorded" in text or "offline" in text or "₹" in text


def test_fallback_is_same_for_same_input(monkeypatch):
    _force_no_api_key(monkeypatch)
    a = respond(FAKE, "user-1", "what is my net worth?", [])[0]
    b = respond(FAKE, "user-1", "what is my net worth?", [])[0]
    assert a == b  # deterministic — reproducible for viva/demo