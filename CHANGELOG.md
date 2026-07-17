# Changelog

All notable changes to GraphKeeper are documented in this file. This
changelog covers both distributions -- the npm package (`graphkeeper-cli`,
JS/TS) and the PyPI package (`graphkeeper-cli`, Python) -- since they mine
the same co-change signal and share an on-disk store schema; entries note
which distribution they apply to.

## [Python 0.1.0] - 2026-07-16

Initial public release of the Python port, published to PyPI as
`graphkeeper-cli` (`pip install graphkeeper-cli`). Complementary to the
npm package -- both are first-class and share the same
`.graphkeeper/graph.json` on-disk schema (a store built by one
distribution can be read back by the other). See `python/README.md` for
Python-specific usage.

### Added

- `graphkeeper build [path]` and `graphkeeper query co-change|calls` CLI
  (console script `graphkeeper`, package `graphkeeper`), with the same
  subcommands, flags, and exit-code contract as the npm CLI.
- Programmatic library API: `from graphkeeper import build,
  query_co_change, query_calls, BuildOptions`, returning the same
  structured result shapes as the CLI formats (`GraphKeeperStore`,
  `CoChangeQueryResult`, `CallsQueryResult` dataclasses).
- Git co-change mining (`graphkeeper.git.mine_co_change`) ported from
  `src/git.ts`: safe argv-list `git log --no-merges --name-only`
  subprocess calls, git's C-quoted-path unescaping (including multi-byte
  UTF-8 octal-escape reassembly), and the same
  `--max-files-per-commit` mass-commit skip logic.
- Path-safety-checked local storage (`graphkeeper.store`) ported from
  `src/store.ts`: every `.graphkeeper/` write is verified, after resolving
  symlinks, to stay inside the target repo's own `.graphkeeper/`
  directory.
- Optional graphify enrichment (`graphkeeper.graphify`) ported from
  `src/graphify.ts`: detects `graphify` on `PATH`, shells out to its local
  `graphify extract --code-only --no-cluster`, and merges the resulting
  symbol/call graph into the same store -- never raises on failure, always
  reports a clear `skipped_reason` instead.
- Full pytest suite (78 tests) ported from the TypeScript vitest suite,
  covering git mining, path safety, query logic, the build pipeline,
  graphify enrichment (with `subprocess.run` mocked the same way the
  TypeScript suite mocks `spawnSync`), output formatters, and an
  end-to-end CLI pass run as a real subprocess.
- Zero third-party runtime dependencies -- only the Python standard
  library and the real `git` binary on `PATH`.

## [0.1.0] - initial TypeScript release

Initial release of the npm package. See `src/` and the project README for
the full narrative: git-log co-change mining, path-safety-checked local
storage, optional graphify enrichment, and the `graphkeeper` CLI.
