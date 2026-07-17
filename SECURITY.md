# Security Policy

GraphKeeper mines git history and (optionally) shells out to a
third-party tool (`graphify`) against whatever repo it's pointed at. A
vulnerability that lets a maliciously crafted repo (an attacker-controlled
clone target, or a symlink planted inside `.graphkeeper/`) cause
GraphKeeper to read or write outside the intended `.graphkeeper/`
directory, or to execute anything beyond a plain `git`/`graphify`
subprocess call, is taken seriously and handled as a priority.

## Supported versions

| Package | Version | Supported |
| --- | --- | --- |
| `graphkeeper-cli` (npm) | 0.1.x | Yes |
| `graphkeeper-cli` (PyPI) | 0.1.x | Yes |

Both distributions are pre-1.0 and under active development. Security
fixes land on the latest `0.1.x` release of each; there is no older
supported line to backport to yet.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Report it privately via
[GitHub Security Advisories](https://github.com/RudrenduPaul/GraphKeeper/security/advisories/new)
for this repository. Include:

- Which distribution is affected (npm package, PyPI package, or both).
- A minimal reproduction: the repo layout or content that triggers the
  issue, and the command/library call that triggers it.
- What you expected GraphKeeper to do, and what it actually did.
- Your assessment of impact -- e.g. "a `.graphkeeper` entry that is a
  symlink to a path outside the repo causes GraphKeeper to write there" is
  exactly the class of bug the path-safety checks in `src/store.ts` /
  `python/src/graphkeeper/store.py` exist to prevent.

## What counts as in scope

- Any code path where `git` or `graphify` is invoked via a shell string
  (rather than an argv list), or where content read from a scanned repo
  (a file path, a commit message) can be interpreted as shell syntax.
- Any `.graphkeeper/` write or graphify-output read that lands outside the
  resolved repo root, including via a symlink planted at `.graphkeeper/`
  itself or at any path GraphKeeper resolves before it exists on disk.
- A crafted repo (e.g. an enormous number of commits or files in one
  commit) that causes unbounded resource consumption bypassing the
  documented `--max-files-per-commit` skip logic.
- Any use of `eval`/`exec` (Python) or dynamic code evaluation (TypeScript)
  against content read from a scanned repo. GraphKeeper only ever reads
  and pattern-matches `git log` output and graphify's own JSON output; it
  never evaluates or dynamically imports anything from the target repo.

## What is out of scope

- Vulnerabilities in a target repo itself (i.e. the repo GraphKeeper is
  pointed at) -- report those to that repo's own maintainers.
- Vulnerabilities in `graphify` itself (a separate project) -- report
  those upstream at
  [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).
  GraphKeeper only shells out to graphify's documented `extract` CLI path
  and never modifies or forks its behavior.

## Response

We aim to acknowledge a report within 5 business days and to have a fix or
a mitigation plan within 30 days for a confirmed, in-scope vulnerability.
Credit is given in the release notes unless you ask to remain anonymous.
