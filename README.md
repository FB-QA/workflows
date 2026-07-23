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

**This repo is public** so any FB-QA repo (private or not) can call it. It contains
**no secrets** — each caller passes its own `CLAUDE_CODE_OAUTH_TOKEN`. Per-repo setup:
install the Claude GitHub App and add that secret (`claude setup-token`).
