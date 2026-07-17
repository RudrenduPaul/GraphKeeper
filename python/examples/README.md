# Python examples

Each numbered subdirectory is a real, runnable script against the actual
`graphkeeper` Python library (`from graphkeeper import build, ...`), not
pseudocode. All three point at this very repository checkout (`GraphKeeper`
itself, both its TypeScript and Python source, plus this file's own commit
history) as the target repo, so nothing external is required.

Install the package first (editable install from this checkout, or `pip
install graphkeeper-cli` from PyPI both work identically):

```bash
cd python
pip install -e .
```

Then run any example directly:

```bash
python3 examples/01-index-and-query/build_and_query.py
python3 examples/02-agent-json/report.py
python3 examples/03-graceful-degradation/calls_without_graphify.py
```

| Example | What it demonstrates |
| --- | --- |
| [01-index-and-query](./01-index-and-query/) | The core library calls: `build()` to mine this repo's own git history, then `query_co_change()` to rank which files historically changed alongside a given one. |
| [02-agent-json](./02-agent-json/) | The agent-native use case: calling GraphKeeper in-process (no CLI subprocess), serializing a structured co-change report to JSON, and applying a result `limit`. |
| [03-graceful-degradation](./03-graceful-degradation/) | `query_calls()`'s documented graceful-degradation path: without graphify installed, a call-graph query returns a clear, structured explanation instead of an empty result or a crash. Also shows `detect_graphify()` directly. |
