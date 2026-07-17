# Getting started

GraphKeeper mines your `git log` for file-level co-change -- which files
actually get edited together across a repo's real history -- and, when
[graphify](https://github.com/Graphify-Labs/graphify) is installed,
enriches that with its symbol/call-graph output. It ships as two
independent, equally first-class packages that share one on-disk store
schema: an npm package (`graphkeeper-cli`, JavaScript/TypeScript) and a
PyPI package (`graphkeeper-cli`, Python). Pick whichever fits your
toolchain, or install both -- a `.graphkeeper/graph.json` built by one can
be read by the other.

## Install

**npm (JS/TS CLI):**

```bash
npm install -g graphkeeper-cli
# or run it once without installing:
npx graphkeeper-cli build
```

**pip (Python library + CLI):**

```bash
pip install graphkeeper-cli
```

Both require Node.js 18+ / Python 3.9+ respectively, and `git` on `PATH`.
Neither pulls anything else at build time -- the Python package has zero
third-party runtime dependencies.

## Your first build

Point either CLI at any git repo, including a clone of GraphKeeper itself:

```bash
git clone https://github.com/RudrenduPaul/GraphKeeper.git
cd GraphKeeper
```

```bash
# npm CLI
graphkeeper build

# Python CLI (after `pip install graphkeeper-cli`)
graphkeeper build
```

Both write the same shape of result to `.graphkeeper/graph.json`: a
`version`, `generatedAt` timestamp, `repoPath`, commit counts, the
`coChange` edge list, per-file `fileCommitCounts`, and a `graphify` block
recording whether enrichment ran and why, if not.

## Querying

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

Exit code `0` when results are found, `1` when there's no co-change data
for that file yet, `2` on a usage or filesystem error -- identical
contract on both CLIs.

Every command also takes `--json` for scripts and agents:

```bash
graphkeeper query co-change src/git.ts --json
```

```json
{
  "file": "src/git.ts",
  "results": [
    { "file": "src/store.ts", "count": 1 },
    { "file": "src/types.ts", "count": 1 }
  ]
}
```

## Using the library instead of the CLI

**TypeScript:**

```ts
import { build, queryCoChange } from 'graphkeeper-cli';

const result = build('.');
const coChange = queryCoChange(result.store, 'src/git.ts', { limit: 5 });
for (const row of coChange.results) {
  console.log(row.count, row.file);
}
```

**Python:**

```python
from graphkeeper import build, query_co_change

result = build(".")
co_change = query_co_change(result.store, "src/git.ts", limit=5)
for row in co_change.results:
    print(row.count, row.file)
```

Both return the same shape of structured result -- see
[concepts.md](./concepts.md) for the full data model.

## Next steps

- [concepts.md](./concepts.md) -- what the co-change graph actually
  represents, how graphify enrichment merges in, and the query model.
- [integrations/ci.md](./integrations/ci.md) -- using GraphKeeper as a
  scheduled or pre-review step in CI.
- The [project README](../README.md) for the full comparison against
  adjacent tools and why GraphKeeper doesn't reimplement graphify.
