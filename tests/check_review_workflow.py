#!/usr/bin/env python3
"""Guard the reusable review workflow's prompt against silent failure.

Two classes of bug this catches, both of which have actually happened:

1. The prompt tells the reviewer to run a `gh` command that is not in
   `--allowedTools`. On a runner nobody can approve a permission prompt, so the
   call is DENIED, the agent retries, and the turn budget is gone before it
   posts anything. The instruction reads fine and does nothing. A dedupe step
   was written this way once — hence this check.

2. The output contract drifts back out. The whole point of the prompt is that
   inline comments have a fixed severity scale, a plain-English lede, a word
   ceiling and a finding cap. Delete any one of those and the reviewer reverts
   to 200-word forensic prose, which is what it does when unconstrained.

No third-party dependencies on purpose — this must run anywhere with python3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/claude-code-review.yml"

# Commands the reviewer is told to run, but which we deliberately do NOT grant.
# Nothing here yet; kept so an intentional exemption has an obvious home.
EXEMPT_PREFIXES: tuple[str, ...] = ()

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def allowlist_prefixes(source: str) -> list[str]:
    """Every `Bash(<prefix>:*)` entry in --allowedTools, as bare prefixes."""
    match = re.search(r'--allowedTools\s+"([^"]*)"', source)
    if match is None:
        failures.append("--allowedTools is missing or not double-quoted on one line")
        return []
    # Split on commas that are not inside Bash( ... ) parentheses.
    entries, depth, current = [], 0, ""
    for char in match.group(1):
        if char == "," and depth == 0:
            entries.append(current)
            current = ""
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        current += char
    entries.append(current)

    prefixes = []
    for entry in (e.strip() for e in entries):
        bash = re.fullmatch(r"Bash\((.*)\)", entry)
        if bash:
            prefixes.append(re.sub(r":\*$", "", bash.group(1)))
    return prefixes


def prompt_block(source: str) -> str:
    """The `prompt: |` folded scalar, up to the next same-indent key."""
    match = re.search(r"\n(\s*)prompt: \|\n(.*?)\n\1[a-z_]+:", source, re.DOTALL)
    if match is None:
        failures.append("could not locate the `prompt: |` block")
        return ""
    return match.group(2)


def main() -> int:
    source = WORKFLOW.read_text()
    prompt = prompt_block(source)
    prefixes = allowlist_prefixes(source)

    # 1. Every gh/git command the prompt asks for must be covered by the allowlist.
    for command in re.findall(r"\bgh (?:api|pr|issue|search)\b[^\n]*", prompt):
        command = command.strip()
        if command.startswith(EXEMPT_PREFIXES):
            continue
        check(
            any(command.startswith(prefix) for prefix in prefixes),
            f"prompt runs `{command[:90]}` but no --allowedTools entry covers it "
            "— it will be DENIED on the runner and burn the turn budget",
        )

    # 2. The output contract. Each of these is load-bearing; see module docstring.
    check("--comment" in prompt, "the review command must pass --comment, or the "
          "upstream plugin's step 7 stops before posting anything")
    check(re.search(r"\bP1\b.*\n?.*\bP2\b", prompt, re.DOTALL) is not None,
          "the fixed P1/P2/P3 severity scale is missing — without it the reviewer "
          "invents a new label vocabulary on every run")
    check("<details>" in prompt,
          "the <details> fold is missing — the forensics belong behind it, not in the lede")
    check(re.search(r"\b60 words\b", prompt) is not None,
          "the 60-word ceiling on the visible lede is missing")
    check(re.search(r"at most 8 findings", prompt) is not None,
          "the 8-finding cap is missing")
    check("pulls/" in prompt and "comments" in prompt,
          "the dedupe step (read existing claude[bot] inline comments) is missing")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        print(f"\n{len(failures)} check(s) failed in {WORKFLOW.name}", file=sys.stderr)
        return 1
    print(f"OK: {WORKFLOW.name} — allowlist covers every prompted command, "
          "output contract intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
