# Concepts

## The build pipeline

Both the npm and PyPI packages run the same pipeline (TypeScript:
`src/build.ts`; Python: `graphkeeper/build.py`):

```
target path
     |
     v
resolve repo root (symlinks followed, must be a real directory)
     |
     v
git log --no-merges --name-only  ->  mine co-change (git.ts / git.py)
     |
     v
graphify on PATH?  -- yes --> graphify extract --code-only --no-cluster
     |  no                        (into .graphkeeper/graphify-raw/, merged in)
     v
skippedReason recorded, co-change-only store
     |
     v
merged store written atomically to .graphkeeper/graph.json
```

A `BuildResult` (the store plus the output path) always comes back as a
structured value; graphify enrichment failures never raise or crash the
build -- they're recorded in the store's own `graphify.skippedReason`
field instead, so a caller can always tell exactly why enrichment did or
didn't happen.

## What co-change actually measures

For every non-merge commit, GraphKeeper takes the set of files that commit
touched (`git log --name-only`), and for every pair of files in that set,
increments a counter. After walking the whole history, `coChange` is the
full list of `{a, b, count}` edges -- unordered pairs, sorted by
descending count. `fileCommitCounts` separately tracks how many commits
touched each individual file, for future normalization (e.g. co-change
rate relative to how often a file changes at all).

**Why this is useful to an agent working alone on an unfamiliar codebase**:
before editing a file, "what else historically changes alongside this?" is
a fast, purely local signal for what else to look at or re-test -- no
symbol resolution or semantic understanding required, just what the
commit history itself already shows.

**`--max-files-per-commit` (default 100)**: a single vendoring commit, a
mass reformat, or a monorepo-wide dependency bump can touch hundreds of
unrelated files at once. Without a cap, that one commit would inject noise
into every pair of files it touched. Commits exceeding this threshold are
counted in `commitsSkipped` and excluded from the co-change graph
entirely, not partially included.

## Path safety

Every `.graphkeeper/` directory GraphKeeper creates, and the final
`graph.json` file itself, is checked -- after resolving symlinks -- to be
nested inside the target repo's resolved root before any write happens
(`src/store.ts` `assertPathInside` / `graphkeeper/store.py`
`assert_path_inside`). This guards against a repo where `.graphkeeper`
already exists as a symlink pointing somewhere else: GraphKeeper refuses
to write through it rather than silently following it outside the repo.

## graphify enrichment

If [graphify](https://github.com/Graphify-Labs/graphify) is detected on
`PATH` (`graphify --version` succeeds), `build` also runs `graphify
extract <path> --code-only --no-cluster --out
.graphkeeper/graphify-raw/` -- graphify's own headless, local, no-API-key
AST extraction mode -- and merges its `nodes`/`edges` into the same store.
graphify reports each node/edge's `source_file` relative to its own `--out`
directory; since that directory lives nested inside `.graphkeeper/`,
GraphKeeper rewrites those paths to be relative to the repo root instead,
so they line up with the co-change paths mined from `git log`.

Enrichment never blocks or fails a build: if graphify isn't installed, its
`extract` exits non-zero, its `graph.json` is missing or malformed, or its
JSON doesn't have the expected `{nodes, edges}` shape, GraphKeeper records
the specific reason in `graphify.skippedReason` and proceeds in
co-change-only mode.

## Query model

- **`query co-change <file>`** (`queryCoChange` / `query_co_change`):
  normalizes the file argument (strips a leading `./`, relativizes an
  absolute path under the repo root if possible), then scans the
  `coChange` edge list for any edge touching that file, returning the
  other side of each match ranked by descending count. An unmatched file
  simply returns an empty result list -- not an error.
- **`query calls <symbol>`** (`queryCalls` / `query_calls`): only
  meaningful when the most recent `build` included graphify enrichment.
  Without it, returns `available: false` with the build's own
  `skippedReason` as the explanation. With enrichment, `findGraphifyNode` /
  `find_graphify_node` matches `<symbol>` against graphify's node labels --
  exact match (with or without a trailing `()`), then case-insensitive,
  then by node ID -- and the result lists callers (`calledBy`/`called_by`)
  and callees (`calls`) from graphify's `calls`-relation edges. A symbol
  that isn't found returns `node: null`, not an error.

## Exit codes

| Code | `build` | `query co-change` | `query calls` |
| --- | --- | --- | --- |
| 0 | Build succeeded | Results found | Symbol found |
| 1 | *(not used)* | No co-change data for that file | Symbol not found, or enrichment unavailable |
| 2 | Target/config error (bad path, not a git repo, invalid flag) | Same | Same |
