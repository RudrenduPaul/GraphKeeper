# graphkeeper-cli (Python)

A local-only CLI and library that mines your `git log` for which files
actually change together, then hands an AI coding agent a queryable answer
instead of a grep across the whole history.

[![PyPI version](https://img.shields.io/pypi/v/graphkeeper-cli.svg)](https://pypi.org/project/graphkeeper-cli/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/RudrenduPaul/GraphKeeper/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/graphkeeper-cli.svg)](https://pypi.org/project/graphkeeper-cli/)
[![npm version](https://img.shields.io/npm/v/graphkeeper-cli.svg)](https://www.npmjs.com/package/graphkeeper-cli)

## Why this exists

An AI coding agent working solo on a codebase it doesn't fully know yet
usually has no fast way to answer "what else changes when I touch this
file?" short of scrolling `git log -p` or grepping blindly. GraphKeeper
mines the commit history that's already sitting on disk and turns it into
one queryable, local answer -- no server, no account, no embeddings API,
nothing leaves the machine. This package is the Python distribution -- a
genuine, independent port of the npm package's TypeScript source, not a
wrapper around the Node binary. It has zero third-party runtime
dependencies: only the Python standard library (`subprocess`, `argparse`,
`json`) and the real `git` binary on `PATH`.

## Install

```bash
pip install graphkeeper-cli
```

or with [uv](https://docs.astral.sh/uv/):

```bash
uv add graphkeeper-cli
```

Requires Python 3.9+ and `git` on your `PATH`. The complementary JS/TS
distribution is also live on npm and installs the same way:

```bash
npm install -g graphkeeper-cli
```

or run it once without installing: `npx graphkeeper-cli build` -- see the
[project README](https://github.com/RudrenduPaul/GraphKeeper#readme) for
that package. Both distributions are first-class, published, and
maintained together in behavioral parity; neither is a wrapper around the
other and neither is deprecated in favor of the other.

## Quickstart

Clone the repo and index it (works against any git repo, including this
one):

```bash
git clone https://github.com/RudrenduPaul/GraphKeeper.git
cd GraphKeeper/python
pip install -e .
graphkeeper build ..
```

```
GraphKeeper build complete: /path/to/GraphKeeper

Co-change graph: 6 commit(s) analyzed, 80 file pair(s) found
graphify enrichment: skipped -- graphify was not found on PATH. Install it with
`uv tool install graphifyy` (or `pipx install graphifyy`) for symbol/call-graph
enrichment; GraphKeeper works fine without it, in co-change-only mode.

Wrote /path/to/GraphKeeper/.graphkeeper/graph.json
```

(Real output from running this Python CLI against the GraphKeeper repo's
own checkout, this early in its history -- co-change counts grow as the
codebase accumulates more commits. Byte-for-byte the same command against
the npm CLI, against the same checkout, produces the same numbers -- both
distributions mine the same `git log`.)

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
(`uv tool install graphifyy`), `graphkeeper build` automatically shells out
to its local, no-API-key `graphify extract --code-only` and merges its
symbol/call-graph into the same store, unlocking call-graph queries.
Without graphify installed, `graphkeeper query calls <symbol>` explains
exactly why the answer isn't available instead of crashing or returning an
empty result:

```
Call-graph query for "mineCoChange" is not available.

graphify was not found on PATH. Install it with `uv tool install graphifyy`
(or `pipx install graphifyy`) for symbol/call-graph enrichment; GraphKeeper
works fine without it, in co-change-only mode.
```

Every command also supports `--json` for scripts and agents.

## Using the library instead of the CLI

```python
from graphkeeper import build, query_co_change, BuildOptions

result = build(".", BuildOptions(skip_graphify=True))
print(f"{result.store.commits_analyzed} commit(s) analyzed")

co_change = query_co_change(result.store, "src/git.ts", limit=5)
for row in co_change.results:
    print(row.count, row.file)
```

`graphkeeper.cli` is a thin `argparse` wrapper over these same functions,
so anything scriptable from the command line is also usable directly from
Python -- the agent-native path.

## CLI reference

```
usage: graphkeeper [-h] [-V] {build,query} ...

Commands:
  build [options] [path]  Mine git history for co-change and (if available)
                           merge in graphify's symbol/call graph
  query co-change <file>  List files that historically change alongside
                           <file>, ranked by co-change frequency
  query calls <symbol>    Show callers/callees of <symbol> (requires
                           graphify enrichment)
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

### `graphkeeper query co-change <file>`

Lists files that historically changed alongside `<file>`, ranked by how
many commits touched both.

| Option | Description |
|---|---|
| `--json` | emit machine-readable JSON instead of human-readable text |
| `--limit <n>` | cap the number of results |
| `--graph <path>` | path to a specific `graph.json` (default: `<cwd>/.graphkeeper/graph.json`) |

Exit code `0` when results are found, `1` when there's no co-change data
for that file yet, `2` on a usage or filesystem error.

### `graphkeeper query calls <symbol>`

Shows callers and callees of `<symbol>`, using graphify's `calls` edges
from the most recent `build`. Only meaningful when that build included
graphify enrichment -- if it didn't, this prints a clear explanation of why
(never a crash, never a silent empty result).

| Option | Description |
|---|---|
| `--json` | emit machine-readable JSON instead of human-readable text |
| `--graph <path>` | path to a specific `graph.json` (default: `<cwd>/.graphkeeper/graph.json`) |

Exit code `0` when the symbol is found, `1` when it isn't (or enrichment
wasn't available), `2` on a usage or filesystem error.

## How it works

Same pipeline as the npm package (see the
[project README](https://github.com/RudrenduPaul/GraphKeeper#how-it-works)
for the full narrative): `git log --no-merges --name-only` mined via a safe
argv-list subprocess call (never a shell string), pairs of co-changed files
counted per commit (commits touching more than `--max-files-per-commit`
files skipped), optionally merged with graphify's local symbol/call graph
when graphify is on `PATH`, and written once, atomically, to
`.graphkeeper/graph.json`. The on-disk JSON schema uses the same field
names (`commitsAnalyzed`, `coChange`, `fileCommitCounts`, etc.) as the npm
package's store, so a `.graphkeeper/graph.json` written by either
distribution can be read back by the other.

## How it compares

GraphKeeper mines `git log` for file-level co-change -- which files
actually get edited together across a repo's real history -- and, when
[graphify](https://github.com/Graphify-Labs/graphify) is on `PATH`,
enriches that with graphify's own local symbol/call-graph extraction
rather than reimplementing it. The full reasoning and a detailed
comparison table (against graphify, GitNexus, Greptile, and Augment Code)
live in the
[project README's "Why this exists, and why it doesn't reimplement
graphify" section](https://github.com/RudrenduPaul/GraphKeeper#why-this-exists-and-why-it-doesnt-reimplement-graphify).
The short version:

| Tool | What it does | Local-only? | Free/OSS? | GraphKeeper's relationship |
|---|---|---|---|---|
| [graphify](https://github.com/Graphify-Labs/graphify) | Symbol/import/call-graph extraction via tree-sitter, AI-assistant skill | Yes (code parsing) | Yes, MIT | GraphKeeper enriches from it when installed; doesn't reimplement it |
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | Browser/WASM knowledge graph + MCP tools, structural + call-flow analysis | Yes (runs client-side) | Yes, ISC | Different delivery model (browser app vs. CLI); no co-change mining |
| [Greptile](https://www.greptile.com/) | Hosted AI code review with a graph-indexed codebase | No (hosted/enterprise) | No | Team/PR-review focused, not a local single-agent tool |
| [Augment Code](https://www.augmentcode.com/) | Hosted coding assistant with its own code+docs+media knowledge graph | No (hosted) | No | Enterprise assistant platform, not a standalone local CLI |

## Security

- Every `git` and `graphify` invocation uses an argv list passed directly
  to the OS (`subprocess.run`, `shell=False`), never a shell string, so
  commit messages, file names, or repo paths can't be interpreted as shell
  syntax.
- `.graphkeeper/` output paths are checked against the resolved repo root
  before every write (symlinks included), so a maliciously crafted repo
  can't redirect GraphKeeper's writes outside `.graphkeeper/`.
- No telemetry, no network calls, no secrets, zero third-party runtime
  dependencies. The only files GraphKeeper reads are `git log` output and
  (optionally) graphify's own `graph.json`; the only file it writes is
  `.graphkeeper/graph.json`.
- See [SECURITY.md](https://github.com/RudrenduPaul/GraphKeeper/blob/main/SECURITY.md)
  for the private disclosure process.

## FAQ

**Is this Python package a wrapper around the npm CLI?**

No. It's an independent, from-scratch implementation
(`python/src/graphkeeper/`) that happens to agree with the TypeScript
source (`src/`) on the same `.graphkeeper/graph.json` schema, subcommands,
flags, and exit codes. A store built by one distribution can be read by
the other, and the Python test suite (78 tests, ported from the
TypeScript vitest suite) runs against a real subprocess CLI invocation,
not a mock of the other language's output.

**Do I need graphify installed for this to work?**

No. `graphkeeper build` works fine without it, in co-change-only mode.
If [graphify](https://github.com/Graphify-Labs/graphify) is detected on
`PATH`, `build` also merges in its symbol/call-graph data; if it isn't,
`graphkeeper query calls` explains exactly why the answer isn't available
instead of crashing or returning an empty result.

**How do I install it, and does it work on Windows?**

`pip install graphkeeper-cli` (Python 3.9+) or `npm install -g
graphkeeper-cli` (Node.js 18+); both need `git` on `PATH`. Neither
package contains OS-specific branches or native bindings, and the PyPI
listing is classified `Operating System :: OS Independent`, so it runs
the same way on Windows, macOS, and Linux anywhere git and a supported
Python or Node runtime are available.

**What actually breaks GraphKeeper, or gives an empty result?**

Two real cases, both documented, neither a crash: a shallow git clone
(GitHub Actions' default `fetch-depth: 1`) has no history to mine, so
`build` reports `0 commit(s) analyzed` and writes an empty co-change
graph; full history (`fetch-depth: 0`) is required. Separately,
`query calls` only returns results if the most recent `build` ran with
graphify on `PATH`.

**What license is this under, and can I use it commercially?**

Apache License 2.0, for both the npm and PyPI packages, with no dual
licensing and no separate commercial tier. That permits commercial use,
modification, and redistribution, with attribution and the standard
Apache patent grant; see
[LICENSE](https://github.com/RudrenduPaul/GraphKeeper/blob/main/LICENSE)
for the full text.

## Contributing

See [CONTRIBUTING.md](https://github.com/RudrenduPaul/GraphKeeper/blob/main/CONTRIBUTING.md)
for the full guide, covering both the TypeScript and Python codebases (they
must stay in behavioral parity). To build from source:

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0, see [LICENSE](https://github.com/RudrenduPaul/GraphKeeper/blob/main/LICENSE).
