# CI integrations

GraphKeeper is a local, read-only indexing tool -- it doesn't gate a build
the way a linter or security scanner does. The typical CI use case is
building the index as an artifact (or a scheduled/cached step) so an AI
coding agent working in that repo's CI environment has a fresh
`.graphkeeper/graph.json` available, rather than mining the full history
on every agent invocation.

## GitHub Actions -- build the index as an artifact

```yaml
name: GraphKeeper index
on:
  push:
    branches: [main]

jobs:
  build-index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # full history required -- co-change mining needs real commit history, not a shallow clone
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npx --yes graphkeeper-cli build --json
      - uses: actions/upload-artifact@v4
        with:
          name: graphkeeper-index
          path: .graphkeeper/graph.json
```

**`fetch-depth: 0` matters.** GitHub Actions' default checkout is shallow
(depth 1) -- a shallow clone has no commit history to mine, so `build`
would report `0` commits analyzed and an empty co-change graph. Full
history is required for co-change mining to produce anything useful.

## GitHub Actions -- Python CLI, equivalent step

```yaml
name: GraphKeeper index (Python)
on:
  push:
    branches: [main]

jobs:
  build-index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install graphkeeper-cli
      - run: graphkeeper build --json
      - uses: actions/upload-artifact@v4
        with:
          name: graphkeeper-index
          path: .graphkeeper/graph.json
```

## Scheduled rebuild

Because co-change signal only grows meaningfully with more commits, a
nightly or weekly scheduled rebuild (rather than one on every push) is
often enough:

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'   # weekly, Monday 06:00 UTC
  workflow_dispatch: {}
```

## Choosing `--max-files-per-commit`

The default (100) is a reasonable general-purpose threshold. Lower it for
a repo with frequent large dependency-bump or codegen commits that would
otherwise dominate the co-change signal; raise it only if you've confirmed
your repo's largest legitimate commits (e.g. a deliberate multi-file
refactor) regularly exceed 100 files and you want those counted.
