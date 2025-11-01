import json
import sys
import types

from src.testing.llm_judge import (
    LLMJudge,
    build_prompt,
    load_rules,
    parse_llm_response,
    run_fallback_checks,
    create_ollama_client,
)

VALID_RESPONSE = """**Summary**
* Added feature A.

**Testing**
* ✅ `pytest -q`
"""


class DummyClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        return self.reply


def test_build_prompt_includes_rules_and_response():
    rules = load_rules()
    prompt = build_prompt(VALID_RESPONSE, rules)

    assert "Rules:" in prompt
    assert "(summary-header)" in prompt
    assert "Response to evaluate:" in prompt
    assert "Return the result strictly as JSON" in prompt
    assert "pytest -q" in prompt


def test_fallback_failure_prevents_llm_call():
    client = DummyClient('{"passed": true, "failures": []}')
    judge = LLMJudge(client=client)

    result = judge.judge("No sections here")

    assert not result.passed
    assert not result.used_llm
    assert result.failures
    assert client.calls == []
    assert any(failure["rule_id"] == "summary-header" for failure in result.failures)


def test_llm_judge_parses_successful_response():
    client = DummyClient('{"passed": true, "failures": []}')
    judge = LLMJudge(client=client)

    result = judge.judge(VALID_RESPONSE)

    assert result.passed
    assert result.used_llm
    assert result.failures == []
    assert client.calls and "pytest -q" in client.calls[0]


def test_parse_llm_response_normalises_failures():
    payload = {
        "passed": False,
        "failures": [
            {"rule_id": "summary-header", "reason": "Missing heading"},
            "generic failure",
        ],
    }

    parsed = parse_llm_response(json.dumps(payload))

    assert parsed["passed"] is False
    assert any(item["rule_id"] == "unknown" for item in parsed["failures"])


def test_run_fallback_checks_passes_for_valid_response():
    rules = load_rules()
    failures = run_fallback_checks(VALID_RESPONSE, rules)

    assert failures == []


def test_create_ollama_client_uses_configured_endpoint(monkeypatch):
    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class DummySession:
        def __init__(self):
            self.calls = []

        def post(self, url, json, timeout):
            self.calls.append({"url": url, "json": json, "timeout": timeout})
            return DummyResponse({"response": "{\"passed\": true, \"failures\": []}"})

    session = DummySession()
    dummy_requests = types.SimpleNamespace(Session=lambda: session)
    monkeypatch.setitem(sys.modules, "requests", dummy_requests)

    client = create_ollama_client(base_url="http://ollama.test:11434", model="phi-mini")
    reply = client("PROMPT")

    assert reply == '{"passed": true, "failures": []}'
    assert session.calls
    call = session.calls[0]
    assert call["url"] == "http://ollama.test:11434/api/generate"
    assert call["json"]["model"] == "phi-mini"
    assert call["timeout"] == 30.0
