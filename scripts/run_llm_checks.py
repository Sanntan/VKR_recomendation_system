#!/usr/bin/env python
"""Run fallback checks (and optional LLM verification) against a response sample."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.testing.llm_judge import LLMJudge

DEFAULT_SAMPLE = Path(__file__).resolve().parents[1] / "tests" / "data" / "sample_llm_response.md"


def read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    if DEFAULT_SAMPLE.exists():
        return DEFAULT_SAMPLE.read_text(encoding="utf-8")
    raise SystemExit("No response text provided and default sample is missing.")


def run() -> int:
    parser = argparse.ArgumentParser(description="Validate a response against formal rules.")
    parser.add_argument("--text", help="Inline text to validate", default=None)
    parser.add_argument("--file", help="Path to file containing the response", default=None)
    args = parser.parse_args()

    response_text = read_text(args)
    judge = LLMJudge()
    result = judge.judge(response_text)

    if result.passed:
        print("LLM checks passed. Used LLM:" , "yes" if result.used_llm else "no")
        return 0

    print("LLM checks failed:")
    for failure in result.failures:
        print(f"- {failure['rule_id']}: {failure['reason']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
