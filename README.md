# FB-QA workflows

Central **reusable** GitHub Actions workflows shared across FB-QA repositories.

## Claude PR review

`.github/workflows/claude-code-review.yml` reviews pull requests with Claude. Each
repo carries only a thin caller:

```yaml
name: Claude code review
on:
  pull_request:
    types: [opened, synchronize, reopened]
concurrency:
  group: claude-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
      issues: write
      id-token: write
    uses: FB-QA/workflows/.github/workflows/claude-code-review.yml@main
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

Edit the reusable workflow here once; the change reaches every caller on its next PR.

### What a review comment looks like

Findings are posted as **inline** comments, never as one summary. Each one leads with
a plain-English lede capped at **60 words** and folds the forensics into a `<details>`
block, so the surface of a PR stays scannable by someone who does not read the code:

```
**P1 · Save and Cancel become untappable** — `12-mobile.css:214`

On any screen with a Delete button, Save and Cancel get pushed off the edge of the
card on a phone. You can see them; you can't tap them.

**Fix:** add `min-width: 0` to `.foot-right` — the new `flex-wrap: nowrap` collides
with its existing `width: 100%`.

<details><summary>Technical detail</summary>
...full analysis, evidence, line references, suggested code — uncapped...
</details>
```

Three rules keep the thread readable, all enforced from the prompt:

- **Fixed severity scale.** `P1` (a real user hits this and something breaks),
  `P2` (wrong under plausible conditions), `P3` (worth knowing). No other labels —
  an invented vocabulary per run cannot be triaged.
- **Cap of 8 findings** per run, highest severity first; the remainder are named in
  one line each on the tracking comment.
- **Dedupe across pushes.** Inline comments accumulate on every `synchronize` and are
  never resolved, so the reviewer reads its own existing comments first and never
  re-flags the same `file:line`.

### Tests

`tests/check_review_workflow.py` (no dependencies, run it with `python3`) guards two
things that fail *silently* in production:

1. Every `gh` command the prompt tells the reviewer to run has a matching
   `--allowedTools` entry. On a runner nobody can approve a permission prompt, so an
   ungranted command is denied, retried, and exhausts the turn budget before anything
   is posted — the instruction reads fine and does nothing.
2. No prompted command carries a **shell variable, command substitution, or `&&`/`||`
   chaining**. An allowlist entry is necessary but not sufficient: the sandbox cannot
   statically match a command it cannot read, so those are denied however correct the
   entry looks. This is not hypothetical — run `31489080897` on `FB-QA/bbbk` died at
   `error_max_turns` with `permission_denials_count: 6`, all of them a reaction-removal
   line whose allowlist entry was perfect. Check 1 passed it; check 2 exists because of
   it.
3. The output contract above is still present. Remove any part of it and the reviewer
   reverts to 200-word forensic prose, which is what it does unconstrained.

Turns are the binding constraint, not tokens. The review fans out to several subagents
before it posts anything, so anything that wastes turns — a denied command, a tracking
comment rewritten a dozen times — costs findings, not tidiness. `--max-turns` is 60.

CI runs it on every push and PR to this repo.

**This repo is public** so any FB-QA repo (private or not) can call it. It contains
**no secrets** — each caller passes its own `CLAUDE_CODE_OAUTH_TOKEN`. Per-repo setup:
install the Claude GitHub App and add that secret (`claude setup-token`).
