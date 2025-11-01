"""Utilities for validating assistant responses with rule-based and LLM checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed when PyYAML is absent
    yaml = None

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "tests" / "validators" / "response_rules.yml"
_STATUS_EMOJIS = {"✅", "⚠️", "❌"}


@dataclass
class EvaluationResult:
    """Result of the evaluation."""

    passed: bool
    failures: List[Dict[str, str]] = field(default_factory=list)
    raw_response: Optional[str] = None
    used_llm: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Return the result as a serialisable dictionary."""

        return {
            "passed": self.passed,
            "failures": list(self.failures),
            "raw_response": self.raw_response,
            "used_llm": self.used_llm,
        }


def load_rules(rules_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load validation rules from YAML configuration."""

    path = Path(rules_path) if rules_path else DEFAULT_RULES_PATH
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        content = handle.read()
    if yaml is not None:
        return yaml.safe_load(content) or {}
    return json.loads(content)


def build_prompt(response_text: str, rules_config: Mapping[str, Any]) -> str:
    """Construct a prompt for the LLM judge."""

    prompt_lines: List[str] = []
    preamble = (rules_config.get("prompt_preamble") or "").strip()
    if preamble:
        prompt_lines.append(preamble)
        prompt_lines.append("")
    prompt_lines.append("Rules:")
    for idx, rule in enumerate(rules_config.get("rules", []), start=1):
        identifier = rule.get("id", f"rule-{idx}")
        description = rule.get("description", "No description provided.").strip()
        prompt_lines.append(f"{idx}. ({identifier}) {description}")
        guidance = (rule.get("guidance") or "").strip()
        if guidance:
            prompt_lines.append("   Guidance: " + guidance.replace("\n", "\n   "))
    prompt_lines.append("")
    prompt_lines.append("Response to evaluate:")
    prompt_lines.append("<<<")
    prompt_lines.append(response_text.strip())
    prompt_lines.append(">>>")
    prompt_lines.append("")
    response_format = (rules_config.get("response_format") or "").strip()
    if response_format:
        prompt_lines.append("Return the result strictly as JSON using this schema:")
        prompt_lines.append(response_format)
    return "\n".join(prompt_lines).strip()


def extract_section(text: str, header: str) -> Optional[str]:
    """Extract the body of a section headed by ``header``."""

    pattern = rf"^\*\*{re.escape(header)}\*\*\s*\n(?P<body>.*?)(?:\n{{2,}}|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if not match:
        return None
    return match.group("body").strip()


def _format_failure(rule_id: str, default_reason: str, extra: str | None = None) -> Dict[str, str]:
    reason = default_reason
    if extra:
        reason = f"{default_reason} {extra}".strip()
    return {"rule_id": rule_id, "reason": reason}


def run_fallback_checks(response_text: str, rules_config: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Run static checks to validate the response without LLM access."""

    rule_lookup = {rule.get("id"): rule for rule in rules_config.get("rules", [])}

    def rule_reason(rule_id: str) -> str:
        rule = rule_lookup.get(rule_id, {})
        return rule.get("description") or f"Rule violated: {rule_id}"

    failures: List[Dict[str, str]] = []

    summary_section = extract_section(response_text, "Summary")
    if not re.search(r"(?m)^\*\*Summary\*\*\s*$", response_text):
        failures.append(_format_failure("summary-header", rule_reason("summary-header")))
    if not summary_section:
        failures.append(
            _format_failure(
                "summary-bullets",
                rule_reason("summary-bullets"),
                "Summary section is missing or empty.",
            )
        )
    else:
        lines = [line for line in summary_section.splitlines() if line.strip()]
        if not lines:
            failures.append(
                _format_failure(
                    "summary-bullets",
                    rule_reason("summary-bullets"),
                    "No bullet entries detected.",
                )
            )
        elif not all(line.lstrip().startswith("* ") for line in lines):
            failures.append(
                _format_failure(
                    "summary-bullets",
                    rule_reason("summary-bullets"),
                    "Every non-empty line must start with '* '.",
                )
            )

    testing_section = extract_section(response_text, "Testing")
    if not re.search(r"(?m)^\*\*Testing\*\*\s*$", response_text):
        failures.append(_format_failure("testing-header", rule_reason("testing-header")))
    if not testing_section:
        failures.append(
            _format_failure(
                "testing-emoji-bullets",
                rule_reason("testing-emoji-bullets"),
                "Testing section is missing or empty.",
            )
        )
    else:
        lines = [line for line in testing_section.splitlines() if line.strip()]
        if not lines:
            failures.append(
                _format_failure(
                    "testing-emoji-bullets",
                    rule_reason("testing-emoji-bullets"),
                    "No bullet entries detected.",
                )
            )
        for line in lines:
            stripped = line.lstrip()
            if not stripped.startswith("* "):
                failures.append(
                    _format_failure(
                        "testing-emoji-bullets",
                        rule_reason("testing-emoji-bullets"),
                        "Testing lines must start with '* '.",
                    )
                )
                continue
            content = stripped[2:].lstrip()
            emoji = None
            for status in _STATUS_EMOJIS:
                if content.startswith(status):
                    emoji = status
                    break
            if emoji is None:
                failures.append(
                    _format_failure(
                        "testing-emoji-bullets",
                        rule_reason("testing-emoji-bullets"),
                        "Missing status emoji (✅, ⚠️, ❌).",
                    )
                )
            if "`" not in content:
                failures.append(
                    _format_failure(
                        "testing-command-format",
                        rule_reason("testing-command-format"),
                        "Expected command formatted in backticks.",
                    )
                )

    return failures


def parse_llm_response(response: Any) -> Dict[str, Any]:
    """Parse the LLM response into a dictionary."""

    data: Dict[str, Any]
    if isinstance(response, str):
        candidate = response.strip()
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            raise ValueError("LLM response does not contain JSON payload.")
        data = json.loads(match.group(0))
    elif isinstance(response, Mapping):
        data = dict(response)
    else:
        raise TypeError("Unsupported response type from LLM client.")

    if "passed" not in data:
        raise ValueError("LLM response missing 'passed' field.")
    passed = bool(data["passed"])
    failures_field = data.get("failures", [])
    if not isinstance(failures_field, Iterable) or isinstance(failures_field, (str, bytes)):
        raise ValueError("'failures' field must be an iterable of failure entries.")

    failures: List[Dict[str, str]] = []
    for failure in failures_field:
        if isinstance(failure, Mapping):
            rule_id = str(failure.get("rule_id", "")).strip() or "unknown"
            reason = str(failure.get("reason", "")).strip() or "No reason provided."
            failures.append({"rule_id": rule_id, "reason": reason})
        else:
            failures.append({"rule_id": "unknown", "reason": str(failure)})

    return {"passed": passed, "failures": failures}


class LLMJudge:
    """Wrapper around rule-based validation with optional LLM judging."""

    def __init__(
        self,
        *,
        rules_path: Optional[Path | str] = None,
        client: Optional[Callable[[str], Any]] = None,
        client_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.rules_config = load_rules(rules_path)
        self.client = client
        self.client_kwargs = client_kwargs or {}

    def judge(self, response_text: str) -> EvaluationResult:
        """Validate ``response_text`` using fallbacks and optionally an LLM."""

        fallback_failures = run_fallback_checks(response_text, self.rules_config)
        if fallback_failures:
            return EvaluationResult(False, fallback_failures, used_llm=False)

        if self.client is None:
            return EvaluationResult(True, [], used_llm=False)

        prompt = build_prompt(response_text, self.rules_config)
        response = self._call_client(prompt)
        parsed = parse_llm_response(response)
        return EvaluationResult(
            bool(parsed["passed"]),
            parsed.get("failures", []),
            raw_response=response if isinstance(response, str) else json.dumps(parsed),
            used_llm=True,
        )

    def _call_client(self, prompt: str) -> Any:
        if callable(self.client):
            return self.client(prompt, **self.client_kwargs)
        if hasattr(self.client, "complete"):
            return self.client.complete(prompt, **self.client_kwargs)
        if hasattr(self.client, "__call__"):
            return self.client(prompt, **self.client_kwargs)
        raise TypeError("LLM client must be callable or expose a 'complete' method.")


__all__ = [
    "LLMJudge",
    "EvaluationResult",
    "build_prompt",
    "load_rules",
    "run_fallback_checks",
    "parse_llm_response",
]
