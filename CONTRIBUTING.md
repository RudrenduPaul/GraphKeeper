# Contributing to GraphKeeper

GraphKeeper ships two independently maintained, equally first-class
distributions of the same tool: an npm package (`graphkeeper-cli`,
TypeScript, repo root) and a PyPI package (`graphkeeper-cli`, Python,
`python/`). Both mine the same git-log co-change signal, apply the same
`--max-files-per-commit` skip logic, and (when graphify is installed)
merge in the same kind of symbol/call-graph enrichment. They also share
one on-disk store schema -- a `.graphkeeper/graph.json` written by either
CLI can be read back by the other. Please read this whole file before
opening a PR -- which section applies depends on which codebase you're
touching.

## Ground rules

- Every change lands with tests. Neither test suite is optional
  scaffolding -- both are the mechanism that keeps the two implementations
  in parity.
- A behavior change to co-change mining, path safety, or graphify
  enrichment must be made in **both** `src/` (TypeScript) and
  `python/src/graphkeeper/` (Python), with equivalent test coverage added
  to both suites. A change that only lands in one language is a silent
  behavior gap between the two CLIs -- avoid it.
- Output text, exit codes, and the on-disk store schema (`version`,
  `generatedAt`/`generated_at`, `repoPath`/`repo_path`,
  `commitsAnalyzed`/`commits_analyzed`, `coChange`/`co_change`, etc.)
  should read/serialize identically between the two CLIs wherever the
  underlying behavior is the same. The JSON keys on disk are always
  camelCase (matching the TypeScript store) regardless of which CLI wrote
  the file, so either can read the other's output.
- Every `git` and `graphify` subprocess call, in either codebase, must use
  an argv list (never a shell string) and must never pass untrusted
  content (commit messages, file paths, repo paths) through a shell.

## Working on the TypeScript package (repo root)

```bash
npm install
npm run build
npm test
npm run typecheck
```

- Source lives under `src/`; tests under `test/` (`vitest`, one file per
  module).
- `npm run build` compiles to `dist/`, which is what the `bin` entry
  (`graphkeeper`) and the library export both resolve to. Run it before
  manually testing `dist/cli.js`.

## Working on the Python package (`python/`)

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

- Source lives under `python/src/graphkeeper/`, laid out to mirror the
  TypeScript module structure 1:1 (`git.py` <-> `src/git.ts`, `store.py`
  <-> `src/store.ts`, `graphify.py` <-> `src/graphify.ts`, `query.py` <->
  `src/query.ts`, `build.py` <-> `src/build.ts`, `cli.py` + `formatters.py`
  <-> `src/cli.ts` + `src/cli-lib.ts`) so a change in one codebase has an
  obvious counterpart to check in the other.
- Tests use `pytest` (`python/tests/test_*.py`), including an end-to-end
  CLI test module that runs `python -m graphkeeper.cli` as a real
  subprocess, mirroring the TypeScript suite's own `node dist/cli.js`
  end-to-end tests.
- Build and verify a real install before opening a PR that touches
  packaging:
  ```bash
  python3 -m build python --outdir /tmp/graphkeeper-dist
  python3 -m venv /tmp/gk-verify && /tmp/gk-verify/bin/pip install /tmp/graphkeeper-dist/*.whl
  /tmp/gk-verify/bin/graphkeeper build .
  ```
  Build the venv and run `python -m build` from *outside* `python/` --
  building inside the source tree risks the venv itself getting bundled
  into the sdist.

## Adding a feature that touches both distributions

1. Implement and test it in TypeScript first (or Python first -- pick
   whichever codebase you're most comfortable verifying against a real git
   repo), including new fixture repos in `test/` or `tests/` as needed.
2. Port the same behavior to the other language, translating idioms (not
   copying syntax) -- e.g. TypeScript's `Map` becomes a Python `dict`,
   `spawnSync` becomes `subprocess.run`, but the actual decision logic
   (what counts as a safe path, when enrichment is skipped, how results
   are ranked) must match exactly.
3. Add equivalent test coverage to both suites, run both, and manually
   verify both CLIs produce the same `co-change` ranking and the same
   `build` summary against the same real repo.

## Reporting a security issue

Do not open a public issue for a security vulnerability. See
[SECURITY.md](./SECURITY.md).

## License

By contributing, you agree your contribution is licensed under the same
Apache License, Version 2.0 that covers the rest of this repository (see
[LICENSE](./LICENSE)).
