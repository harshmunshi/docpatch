# CLAUDE.md — DocPatch engineering guide

This file is the operating manual for Claude (and any other AI coding agent) working in this
repository. Read it end-to-end before writing or changing code. It encodes our taste, our
non-negotiables, and the version plan.

> **TL;DR.** DocPatch is a format-agnostic Python library that lets LLMs edit documents
> surgically: parse → address → locate → patch → splice. Production-grade from day one.
> Managed with `uv`. Strict types. Strict tests. Versioned in tight, shippable slices.

---

## 1. Project north star

**One sentence.** DocPatch turns any document into an addressable tree so an LLM can edit one
node at a time and put the result back losslessly.

**Non-goals (be ruthless about these).**

- Not a RAG library. Retrieval is a separate concern.
- Not a model. We call user-provided model endpoints; we do not ship weights.
- Not a UI. The library has a CLI and a server; visual editors are downstream products.
- Not a "Word clone". We do not replace authoring tools; we sit between an agent and a file.

If a feature request does not advance "edit one node, splice it back, losslessly", push back.

---

## 2. Repo layout

```
docpatch/
├── pyproject.toml           # uv-managed, single source of truth
├── uv.lock                  # checked in, never hand-edit
├── README.md
├── CLAUDE.md                # this file
├── CHANGELOG.md             # keep a changelog, every PR updates it
├── LICENSE                  # Apache-2.0 (core)
├── LICENSE-SERVER           # BSL-1.1 (server/)
├── src/
│   └── docpatch/
│       ├── __init__.py
│       ├── core/            # DocTree, Node, types, IDs, fingerprints
│       ├── parsers/         # one module per format: md, json, docx, pdf, xlsx, html
│       ├── locator/         # symbolic + semantic; pluggable
│       ├── patcher/         # operation primitives (replace/insert/delete/move/split/merge)
│       ├── splicer/         # deterministic reinsertion + serializers
│       ├── storage/         # in_mem, sidecar, sqlite, postgres adapters
│       ├── history/         # git-backed by default; pluggable
│       ├── refs/            # reference graph
│       ├── provenance/      # per-node audit metadata
│       ├── validators/      # structural (free) + policy (pluggable)
│       ├── models/          # LLM client abstraction (no provider in core)
│       ├── cli/             # `docpatch` entrypoint
│       └── server/          # FastAPI app, BSL-licensed, separate package extra
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── property/            # hypothesis-based
│   └── fixtures/            # real documents, anonymized
├── benchmarks/              # token cost + fidelity, runnable with `uv run bench`
├── docs/                    # mkdocs-material
└── .github/workflows/       # CI: lint, type, test, bench-smoke, publish
```

Rules:

- One format per parser module. No cross-format imports.
- Each layer depends only on layers below it. Parsers do not call locators. Locators do
  not call patchers. Wire-up happens in `docpatch/__init__.py` and the CLI.
- `server/` and `cli/` are *consumers* of the library, never imported by it.

---

## 3. Tech stack and tooling

Picked for fast iteration, boring reliability, and zero ambiguity.

| Concern              | Choice                              | Why                                          |
|----------------------|-------------------------------------|----------------------------------------------|
| Package manager      | **uv**                              | 10x faster than pip; single source of truth  |
| Python               | **3.11+** (3.12 default)            | Better tracebacks, perf, typing              |
| Data models          | **pydantic v2**                     | Validated boundaries, JSON in/out for free   |
| Lint                 | **ruff** (`E`, `F`, `I`, `UP`, `B`) | One tool, fast                               |
| Format               | **ruff format**                     | No bikeshedding                              |
| Types                | **mypy --strict** + **pyright**     | Belt and suspenders for public surface       |
| Tests                | **pytest** + **hypothesis**         | Property tests catch the bugs unit tests miss|
| Coverage             | **coverage.py**, target ≥ 90% core  | Enforced in CI                               |
| Docs                 | **mkdocs-material**                 | Live previews, versioned                     |
| Pre-commit           | **pre-commit**                      | Runs ruff, mypy, pytest-fast                 |
| CI                   | **GitHub Actions**                  | Matrix on py3.11, 3.12, 3.13                 |
| Release              | **uv publish** + sigstore           | Reproducible, signed                         |

### Why uv (and how we use it to ship faster)

- `uv venv && uv sync` — zero-cost environment, deterministic.
- `uv add <pkg>` — adds to `pyproject.toml` *and* updates `uv.lock` in one step.
- `uv add --dev <pkg>` — keep test/lint deps separate from runtime.
- `uv run pytest` — runs in the project's venv with no activation dance.
- `uv lock --upgrade` — refresh the lock, review the diff, ship.
- `uv tool install docpatch` — global install from PyPI for end users.
- Optional extras are first-class: `pip install docpatch[pdf,docx,ocr,server]`.

Anything not pinned in `uv.lock` is a bug. Anything installed outside uv is a bug.

---

## 4. Coding standards (production posture)

These are not preferences. They are gates.

**Typing.** Public surface is fully typed and passes `mypy --strict`. Internal helpers
should be typed; use `cast` sparingly and only with a comment explaining why.

**Data at boundaries = pydantic.** Anything that crosses a process or network boundary
(parser output, CLI args, HTTP bodies, LLM responses) is a pydantic model. Anything
internal can be a `@dataclass(slots=True)` if pydantic overhead isn't justified.

**Errors are types, not strings.** Each module defines a small enum of error kinds and
raises typed exceptions inheriting from `DocPatchError`. Never raise `Exception` or
`RuntimeError`. Catch only what you can recover from.

**Determinism in everything except the LLM call.** Parsers, IDs, fingerprints, splicing,
serialization — all deterministic. The only randomness is the model's output, and that is
quarantined behind `models/` and a validator.

**No global state.** Configuration is passed through a `Settings` pydantic model, loaded
via `pydantic-settings` from env vars. The library is library-shaped: import, instantiate,
use, dispose. No module-level connections, no singletons.

**Logging is structured (`structlog`).** Every log line has `event`, `doc_id`, `node_id`
where applicable, and `duration_ms`. No `print()` in library code. CLI may print.

**Observability is free.** OpenTelemetry spans wrap every public function in `core`,
`locator`, `patcher`, `splicer`. Default exporter is no-op; users plug in their own.

**Performance budgets** (regressions break CI):

| Operation                                     | p50 budget        |
|-----------------------------------------------|-------------------|
| Parse 100KB markdown                          | ≤ 50 ms           |
| Parse 100-page DOCX                           | ≤ 800 ms          |
| Symbolic locate on cached DocTree             | ≤ 5 ms            |
| Splice a 1KB subtree into 1MB tree (no LLM)   | ≤ 10 ms           |
| End-to-end edit (excluding model latency)     | ≤ 150 ms          |

**Security.**

- Never read or log model API keys. They come from env only.
- Treat parsed PDF / DOCX as untrusted: no path traversal, no XML external entity, no
  zip-slip. Use `defusedxml`, validate archive members.
- All filesystem writes go through `storage/`. No direct `open(path, "w")` in parsers
  or patchers.

**Backwards compatibility.**

- Before v1.0: anything can change, but document every breaking change in CHANGELOG.
- After v1.0: SemVer. Public API breakage requires a major bump and a deprecation
  shipped at least one minor before.

---

## 5. Module-by-module contracts

### `core/`
- `Node`: pydantic model. `id: str`, `type: NodeType`, `children: list[Node]`,
  `content: str | None`, `raw_span: bytes | None`, `fingerprint: str` (BLAKE3),
  `metadata: dict[str, Any]`.
- `DocTree`: holds the root node, an id→node index, and a back-pointer map.
- IDs are deterministic: `{type}:{parent_id}/{slug}#{ord}`. Slugs from headings/keys.
- Fingerprints over the canonicalized subtree (children fingerprints + content).

### `parsers/`
Each parser exports two functions:
```python
def parse(data: bytes) -> DocTree: ...
def serialize(tree: DocTree) -> bytes: ...
```
Round-trip invariant: `serialize(parse(x)) == x` byte-for-byte for unchanged regions.
This is the most important property in the codebase. Tested with hypothesis on real
corpora.

### `locator/`
```python
class Locator(Protocol):
    def locate(self, tree: DocTree, instruction: str) -> LocateResult: ...
```
Ships with `SymbolicLocator` (regex/grammar over instruction text) and `SemanticLocator`
(small LLM call over the heading skeleton). `LocateResult` includes node IDs, a
confidence, and candidates for disambiguation.

### `patcher/`
One submodule per operation. Each implements:
```python
class Operation(Protocol):
    def apply(self, tree: DocTree, target: NodeRef, instruction: str,
              model: ModelClient) -> Patch: ...
    def validate(self, patch: Patch, tree: DocTree) -> ValidationResult: ...
```
The model never sees more than the target subtree + a breadcrumb (ancestor path +
sibling headings, never sibling bodies).

### `splicer/`
Pure function: `splice(tree, patches) -> DocTree`. No model calls. Deterministic.

### `storage/`
Adapter interface:
```python
class StorageAdapter(Protocol):
    def save(self, doc_id: str, bundle: DocPatchBundle) -> None: ...
    def load(self, doc_id: str) -> DocPatchBundle: ...
    def list(self) -> list[DocMeta]: ...
```
Adapters: `InMemoryStorage`, `SidecarStorage` (`.dpx/` directory), `SQLiteStorage`,
`PostgresStorage`. The `.dpx/` bundle layout is the canonical on-disk format; other
adapters serialize to/from it.

### `history/`
Git-backed by default. Each patch becomes a commit in a hidden `.docpatch-history/`
repo inside the bundle. The adapter is pluggable so server mode can use Postgres rows
with the same semantics.

### `refs/`
Reference graph: edges between nodes that mention defined terms, headings, numeric
values from tables. Built incrementally; invalidated on patch.

### `validators/`
Two layers:
- **Structural** (always on, free): re-parse the patched output; check node type,
  schema conformance, table shape, list integrity.
- **Policy** (opt-in, pluggable): PII detection, citation preservation, style-guide
  rules, schema-guided JSON validation. Each policy is a class implementing
  `validate(node, patch) -> PolicyResult`.

### `models/`
Provider-agnostic client. Out of the box: `AnthropicClient`, `OpenAIClient`, and a
`LiteLLMClient` that delegates. No provider library is a hard dependency; they are
optional extras. The library accepts any object satisfying:
```python
class ModelClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse: ...
```

---

## 6. Version plan

Each version is a shippable slice. Ship the smallest thing that an honest reviewer
would call "useful in production". No version is allowed to add a feature that breaks
the previous version's tests.

### v0.1 — Core algorithm, MD + JSON (target: 4 weeks)

**Scope.** The five stages end-to-end for Markdown and JSON only.

Deliverables:
- `core/` with `Node`, `DocTree`, IDs, fingerprints.
- `parsers/markdown.py` (markdown-it-py).
- `parsers/json.py` (typed tree, JSON Pointer IDs).
- `locator/symbolic.py` and `locator/semantic.py` (Haiku-class default).
- `patcher/replace.py` only.
- `splicer/` lossless for MD + JSON.
- `storage/in_memory.py` and `storage/sidecar.py`.
- `cli/`: `docpatch edit <file> "<instruction>"`.
- `models/anthropic.py` and `models/openai.py` as optional extras.
- 90% test coverage on `core`, `splicer`, parsers.
- Hypothesis round-trip property tests for both parsers.
- Mini benchmark: 10 real documents, before/after token counts, fidelity score.

Exit criteria:
- `uv run pytest` green, mypy strict clean, ruff clean.
- `docpatch edit README.md "tighten the intro"` works end-to-end on a fresh `uv sync`.
- Bundle layout v1 frozen and documented.

**Explicitly out of scope.** DOCX, PDF, history, refs graph, operations other than
replace, server, policy validators.

### v0.2 — DOCX (target: +3 weeks)

- `parsers/docx.py` using python-docx + lxml.
- Run/style preservation; lossless round-trip for unchanged paragraphs.
- Tracked-changes mode (opt-in): emits `w:ins`/`w:del`.
- Extras: `pip install docpatch[docx]`.

Exit criteria: round-trip property tests on a corpus of 50 real DOCX files, zero
byte-diff on unchanged sections.

### v0.3 — PDF (target: +4 weeks)

- `parsers/pdf.py`: pdfplumber for text-layer; Unstructured hi-res for scanned.
- Recovery heuristics (font-size → heading level) behind a documented confidence score.
- `render_pdf()` export step using WeasyPrint or ReportLab.
- Explicit non-goal: in-place PDF mutation. Source of truth is the DocTree.

### v0.4 — Operation taxonomy (target: +2 weeks)

- `patcher/insert.py`, `delete.py`, `move.py`, `split.py`, `merge.py`, `restyle.py`.
- Each operation has its own validator and prompt template.
- Composite operations: a single user instruction can decompose into a list of
  primitive ops applied transactionally.

### v0.5 — History as first-class (target: +3 weeks)

- `history/git.py`: every patch is a real git commit inside `.dpx/.docpatch-history/`.
- `docpatch log`, `docpatch diff`, `docpatch revert`, `docpatch blame <node_id>`.
- Branches and three-way merge of DocTrees (node-level conflict resolution).

### v0.6 — Reference graph (target: +3 weeks)

- `refs/builder.py`: extract defined terms, heading references, numeric quotes.
- Incremental updates: on patch, invalidate edges touching the changed node, re-derive
  only those.
- `docpatch deps <node_id>` and `docpatch dependents <node_id>`.
- Evaluator integration: after a patch, only dependents are re-checked.

### v0.7 — Server (BSL) (target: +4 weeks)

- `server/` FastAPI app: REST + WebSocket.
- `storage/postgres.py`, `storage/s3.py`.
- API-key auth, per-tenant quotas, OpenTelemetry traces.
- Docker image and Helm chart in `deploy/`.
- BSL-1.1 license file, additional restriction text, 4-year Apache-2.0 conversion clause.

### v0.8 — Provenance + policy (target: +3 weeks)

- `provenance/`: every node carries the model, prompt hash, RAG source IDs that
  produced it.
- `validators/policy/`: PII, citation preservation, style-guide DSL, JSON schema
  enforcement.
- Audit export: `docpatch audit <doc_id>` produces a signed JSON ledger.

### v0.9 — Ecosystem (target: +3 weeks)

- `integrations/langchain/`, `integrations/llamaindex/`, `integrations/haystack/`.
- `mcp-server/`: a Model Context Protocol server exposing DocPatch tools to any
  MCP-aware agent.
- TypeScript SDK (`docpatch-ts`) talking to the server over the same wire format.

### v1.0 — Stable surface + benchmark (target: +4 weeks)

- Freeze public API. Document every type and function with examples.
- `benchmarks/`: open dataset of (document, instruction, expected edit) pairs, scored
  on token cost and fidelity. Runnable: `uv run docpatch-bench`.
- Migration guide from v0.x.
- Signed release on PyPI via sigstore.

---

## 7. Development workflow

### One-time setup

```bash
uv venv
uv sync --all-extras --dev
uv run pre-commit install
```

### Daily loop

```bash
uv run pytest -x                       # fast tests, stop on first failure
uv run pytest --cov=docpatch tests/    # full run with coverage
uv run ruff check --fix src tests
uv run ruff format src tests
uv run mypy --strict src
```

### Adding a dependency

```bash
uv add markdown-it-py                  # runtime
uv add --dev hypothesis                # dev only
uv add --optional pdf pdfplumber       # belongs to the [pdf] extra
```

Then commit `pyproject.toml` and `uv.lock` together. Never one without the other.

### Adding a new parser

1. Create `src/docpatch/parsers/<format>.py` with `parse` and `serialize`.
2. Add round-trip hypothesis tests in `tests/property/test_<format>_roundtrip.py`.
3. Register the format in `parsers/__init__.py:detect_format()`.
4. Add a real document to `tests/fixtures/<format>/` and a smoke test.
5. Update `CHANGELOG.md` under `Unreleased`.
6. Update the extras in `pyproject.toml` if the parser pulls heavy deps.

### Adding a new operation

1. Create `src/docpatch/patcher/<op>.py` implementing the `Operation` protocol.
2. Write the prompt template in `src/docpatch/patcher/prompts/<op>.j2`.
3. Add the validator that re-parses and checks structural invariants.
4. Tests:
   - unit: validator catches each known failure mode.
   - integration: full round-trip on a fixture.
   - property: random subtree + random instruction does not crash; result either
     validates or returns a typed failure.
5. Update `cli/` and the public docs.

### Commits and PRs

- Conventional commits: `feat(parser): docx tracked-changes mode`,
  `fix(splicer): handle empty heading`, `chore: bump uv lock`.
- One concern per PR. Squash on merge. PR template enforces a CHANGELOG entry and a
  link to the failing test before the fix.
- Every PR runs the full benchmark smoke. If token-cost or fidelity regresses by
  more than 5% on the reference corpus, CI fails.

---

## 8. Testing strategy (non-negotiable)

- **Unit tests** for every public function. Fast (< 5 s total).
- **Property tests** (hypothesis) for parsers and the splicer. The properties:
  - `serialize(parse(x)) == x` for unchanged regions.
  - `splice(tree, []) == tree`.
  - IDs are stable across re-parses of the same content.
  - Fingerprints change iff content changes.
- **Integration tests** with a *mocked* model client by default. Real model calls
  live in `tests/integration/test_real_model.py` and only run on `RUN_LIVE=1`.
- **Golden tests** on a fixture corpus: instruction in, expected node-set out,
  expected post-edit document out (byte-compared for non-LLM stages).
- **Benchmarks** in `benchmarks/` run nightly in CI, post results to a static page.

Coverage gates:
- `core/`, `splicer/`, `storage/`: ≥ 95%.
- `parsers/`, `patcher/`, `locator/`: ≥ 90%.
- `server/`: ≥ 85%.
- Anything else: ≥ 80%.

---

## 9. CI/CD

GitHub Actions matrix on Ubuntu + macOS, Python 3.11/3.12/3.13. Jobs:

1. **lint** — ruff check + ruff format --check.
2. **type** — mypy --strict, pyright on public surface.
3. **test-fast** — `uv run pytest tests/unit tests/property -x`.
4. **test-full** — `uv run pytest --cov`, fails under coverage gate.
5. **bench-smoke** — runs a 10-document subset of `benchmarks/`, compares against
   the main branch's stored baseline.
6. **build** — `uv build`, uploads wheel + sdist as artifacts.
7. **publish** (on tag) — `uv publish` with sigstore signing.

A PR cannot merge unless all gates green and at least one human reviewer approved.

---

## 10. Releasing

1. Update `CHANGELOG.md`: move `Unreleased` items under the new version + date.
2. Bump version in `pyproject.toml`.
3. `uv lock` to confirm lockfile is clean.
4. `git tag v0.X.Y && git push --tags`.
5. CI publishes to PyPI and creates a GitHub release with the changelog excerpt.
6. Post the benchmark numbers for the release on the docs site.

---

## 11. When in doubt

- **Prefer deletion to addition.** A smaller library is a better library.
- **If a test is hard to write, the design is wrong.** Refactor first.
- **If a public function takes more than four arguments, it is two functions.**
- **If a comment explains *what* the code does, the code is unclear.** Comments
  explain *why*.
- **If a PR touches more than one of: parsers, locator, patcher, splicer — split it.**
- **No silent failures.** Either succeed, return a typed failure, or raise. Never
  `except: pass`.
- **No LLM call without a validator on its output.**
- **The DocTree is the source of truth. The file is one possible export.**

---

## 12. Things we will not do (yet, or ever)

- Ship our own LLM. We are model-agnostic forever.
- Add a database ORM. SQL is fine; SQLAlchemy is overkill at our scale.
- Add a UI in this repo. Editors and viewers live in separate repos.
- Support Python < 3.11. Modern Python only.
- Add a configuration file format. Env vars and pydantic settings are enough.
- Take a hard dependency on any single LLM provider. Extras only.

---

*Last reviewed: keep this file current. If something here is no longer true,
update it in the same PR that breaks it.*
