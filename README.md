# GraphKeeper

[![PyPI version](https://img.shields.io/pypi/v/graphkeeper-cli.svg)](https://pypi.org/project/graphkeeper-cli/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)

A local-only CLI that mines your `git log` for which files actually change
together, then hands an AI coding agent a queryable answer instead of a
grep across the whole history.

```bash
npx graphkeeper-cli build
npx graphkeeper-cli query co-change src/git.ts
```

```
Files that historically change alongside "src/git.ts":

     1  src/store.ts
     1  src/types.ts
     1  test/git.test.ts
     1  test/store.test.ts
     1  test/test-helpers.ts
```

(Real output from running GraphKeeper against its own repo, this early in its
history -- co-change counts grow as a codebase accumulates more commits.)

No server, no account, no embeddings API, nothing leaves your machine. Every
byte of output comes from `git log` on the repo you already have checked out.

## Install

GraphKeeper ships two independent, equally first-class packages -- pick
whichever fits your toolchain, or install both. Both mine the same `git
log` co-change signal and share one on-disk `.graphkeeper/graph.json`
schema, so a store built by either can be read back by the other.

```bash
# npm -- JavaScript/TypeScript CLI + library
npm install -g graphkeeper-cli
# or run it once with no install
npx graphkeeper-cli build

# PyPI -- Python CLI + library (genuine port, not a wrapper around the Node binary)
pip install graphkeeper-cli
```

The npm package requires Node.js 18 or later; the Python package requires
Python 3.9 or later. Both require `git` on your `PATH`. The Python
package's CLI entry point is also `graphkeeper` (e.g. `graphkeeper build`);
see [`python/README.md`](./python/README.md) for the Python-specific
walkthrough, and [CHANGELOG.md](./CHANGELOG.md) for each distribution's
version history.

## Quickstart

Run it against any git repo, including this one:

```bash
git clone https://github.com/RudrenduPaul/GraphKeeper.git
cd GraphKeeper
graphkeeper build
```

```
GraphKeeper build complete: /path/to/GraphKeeper

Co-change graph: 4 commit(s) analyzed, 80 file pair(s) found
graphify enrichment: skipped -- graphify was not found on PATH. Install it with
`uv tool install graphifyy` (or `pipx install graphifyy`) for symbol/call-graph
enrichment; GraphKeeper works fine without it, in co-change-only mode.

Wrote /path/to/GraphKeeper/.graphkeeper/graph.json
```

Now query it:

```bash
graphkeeper query co-change src/git.ts
```

```
Files that historically change alongside "src/git.ts":

     1  src/store.ts
     1  src/types.ts
     1  test/git.test.ts
     1  test/store.test.ts
     1  test/test-helpers.ts
```

If [graphify](https://github.com/Graphify-Labs/graphify) is installed
(`uv tool install graphifyy`), `graphkeeper build` automatically shells out to
its local, no-API-key `graphify extract --code-only` and merges its
symbol/call-graph into the same store, unlocking call-graph queries:

```bash
graphkeeper query calls mineCoChange
```

```
mineCoChange() (src/git.ts)

Calls (2):
  --> assertIsGitRepo()
  --> runGit()

Called by (1):
  <-- build()
```

(Also real output, from running `graphkeeper build` against this repo with
graphify installed.)

Without graphify installed, that same command explains exactly why the
answer isn't available instead of crashing or returning an empty result:

```
Call-graph query for "mineCoChange" is not available.

graphify was not found on PATH. Install it with `uv tool install graphifyy`
(or `pipx install graphifyy`) for symbol/call-graph enrichment; GraphKeeper
works fine without it, in co-change-only mode.
```

Every command also supports `--json` for scripts and agents:

```bash
graphkeeper query co-change src/git.ts --json
```

```json
{
  "file": "src/git.ts",
  "results": [
    { "file": "src/store.ts", "count": 1 },
    { "file": "src/types.ts", "count": 1 },
    { "file": "test/git.test.ts", "count": 1 },
    { "file": "test/store.test.ts", "count": 1 },
    { "file": "test/test-helpers.ts", "count": 1 }
  ]
}
```

## CLI reference

```
Usage: graphkeeper [options] [command]

Options:
  -V, --version           output the version number
  -h, --help              display help for command

Commands:
  build [options] [path]  Mine git history for co-change and (if available)
                          merge in graphify's symbol/call graph
  query                   Query the GraphKeeper store built by
                          `graphkeeper build`
  help [command]          display help for command
```

### `graphkeeper build [path]`

Walks `path` (default: current directory), runs `git log --no-merges
--name-only` across the whole history, and counts how often each pair of
files was touched in the same commit. Writes the result to
`.graphkeeper/graph.json`.

| Option | Description |
|---|---|
| `--json` | emit machine-readable JSON instead of human-readable text |
| `--max-files-per-commit <n>` | skip commits touching more than this many files (default: 100) -- keeps a single mass-reformat or vendoring commit from drowning out real co-change signal |
| `--no-graphify` | skip graphify enrichment even if graphify is installed |

If [graphify](https://github.com/Graphify-Labs/graphify) is detected on
`PATH`, `build` also runs `graphify extract <path> --code-only --no-cluster`
(graphify's own headless, local, no-API-key AST extraction path) into a
directory inside `.graphkeeper/`, and merges its nodes/edges into the same
store. The build output always states plainly whether that enrichment was
included, and why it was skipped if not.

### `graphkeeper query co-change <file>`

Lists files that historically changed alongside `<file>`, ranked by how many
commits touched both.

| Option | Description |
|---|---|
| `--json` | emit machine-readable JSON instead of human-readable text |
| `--limit <n>` | cap the number of results |
| `--graph <path>` | path to a specific `graph.json` (default: `<cwd>/.graphkeeper/graph.json`) |

Exit code `0` when results are found, `1` when there's no co-change data for
that file yet, `2` on a usage or filesystem error.

### `graphkeeper query calls <symbol>`

Shows callers and callees of `<symbol>`, using graphify's `calls` edges from
the most recent `build`. Only meaningful when that build included graphify
enrichment -- if it didn't, this prints a clear explanation of why (never a
crash, never a silent empty result).

| Option | Description |
|---|---|
| `--json` | emit machine-readable JSON instead of human-readable text |
| `--graph <path>` | path to a specific `graph.json` (default: `<cwd>/.graphkeeper/graph.json`) |

Exit code `0` when the symbol is found, `1` when it isn't (or enrichment
wasn't available), `2` on a usage or filesystem error.

## Why this exists, and why it doesn't reimplement graphify

[graphify](https://github.com/Graphify-Labs/graphify) (87K+ stars, MIT
licensed, `pip install graphifyy`) already does symbol, import, and
call-graph extraction across 36 tree-sitter grammars, ships as a
slash-command skill for Claude Code, Codex, Gemini CLI, and 20+ other
assistants, and is actively developed by a funded (YC S26) team. Building a
competing symbol extractor from scratch would mean re-deriving years of
tree-sitter grammar coverage and edge-resolution work that already exists,
for no real gain.

GraphKeeper does something graphify has no reason to prioritize instead:
it mines `git log` for **file-level co-change** -- which files actually get
edited together across the real history of the repo. That's a narrow,
single-agent-workflow signal (useful to one agent working solo on a
codebase it doesn't fully know yet), not something a symbol-graph extractor
or a team code-review dashboard is built around. When graphify is present,
GraphKeeper enriches its own co-change graph with graphify's symbol/call
data by shelling out to graphify's own local `extract` command and merging
the two outputs into one store. When graphify isn't installed, GraphKeeper
still works, just without call-graph queries -- that's a documented,
graceful degradation, never an error.

The broader landscape, honestly:

| Tool | What it does | Local-only? | Free/OSS? | GraphKeeper's relationship |
|---|---|---|---|---|
| [graphify](https://github.com/Graphify-Labs/graphify) | Symbol/import/call-graph extraction via tree-sitter, AI-assistant skill | Yes (code parsing) | Yes, MIT | GraphKeeper enriches from it when installed; doesn't reimplement it |
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | Browser/WASM knowledge graph + MCP tools, structural + call-flow analysis | Yes (runs client-side) | Yes, ISC | Different delivery model (browser app vs. CLI); no co-change mining |
| [Greptile](https://www.greptile.com/) | Hosted AI code review with a graph-indexed codebase | No (hosted/enterprise) | No | Team/PR-review focused, not a local single-agent tool |
| [Augment Code](https://www.augmentcode.com/) | Hosted coding assistant with its own code+docs+media knowledge graph | No (hosted) | No | Enterprise assistant platform, not a standalone local CLI |

GraphKeeper is not trying to out-graph any of these. It's a small,
single-purpose complement: point it at a repo, and it tells an agent which
files tend to move together, based on nothing but the commit history that's
already sitting on disk.

## How it works

1. `graphkeeper build` runs `git log --no-merges --name-only` (via a safe
   argv-array subprocess call, never a shell string) across the whole
   repo history.
2. For every commit, it counts every pair of files that changed together.
   Commits touching more than `--max-files-per-commit` files (default 100)
   are skipped, so a single vendoring or mass-reformat commit can't drown
   out real signal.
3. If `graphify` is detected on `PATH`, GraphKeeper also runs
   `graphify extract <path> --code-only --no-cluster` -- graphify's own
   local, no-LLM, no-API-key extraction mode -- into a directory inside
   `.graphkeeper/`, then merges its `nodes`/`edges` into the same store.
4. The merged result is written once, atomically, to
   `.graphkeeper/graph.json`.
5. `graphkeeper query` reads that file back and answers co-change or
   call-graph questions against it -- no network calls, ever.

## Security

- Every `git` and `graphify` invocation uses an argv array passed directly
  to the OS (`spawnSync`), never a shell string, so commit messages, file
  names, or repo paths can't be interpreted as shell syntax.
- `.graphkeeper/` output paths are checked against the resolved repo root
  before every write (symlinks included), so a maliciously crafted repo
  can't redirect GraphKeeper's writes outside `.graphkeeper/`.
- No telemetry, no network calls, no secrets. The only files GraphKeeper
  reads are `git log` output and (optionally) graphify's own `graph.json`;
  the only file it writes is `.graphkeeper/graph.json`.

## Contributing

Issues and PRs welcome. To build the TypeScript package from source:

```bash
git clone https://github.com/RudrenduPaul/GraphKeeper.git
cd GraphKeeper
npm install
npm run build
npm test
npm run lint
npm run typecheck
```

For the Python package, see [`python/README.md`](./python/README.md). Full
contribution guidelines covering both codebases are in
[CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[Apache License 2.0](./LICENSE)
