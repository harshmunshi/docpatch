# DocPatch

**Surgical LLM document editing.** Parse any document into an addressable tree, locate the right node, send only that node to a model, splice the result back — losslessly.

```bash
pip install git+https://github.com/docpatch/docpatch.git
pip install "docpatch[anthropic] @ git+https://github.com/docpatch/docpatch.git"
pip install "docpatch[openai,anthropic] @ git+https://github.com/docpatch/docpatch.git"
```

---

## Why DocPatch

Sending a whole document to an LLM and asking it to return the whole document back is slow, expensive, and error-prone. DocPatch changes the unit of work:

```
FILE → parse → DocTree → locate → Node → patch (LLM) → splice → FILE′
```

- **The model sees one node.** Not the whole document — just the target subtree and a breadcrumb path.
- **Unchanged regions are untouched.** Each node carries its original bytes (`raw_span`). Serialization reuses them verbatim.
- **IDs are deterministic.** `{type}:{parent_id}/{slug}#{ord}` — stable across re-parses of unchanged content.
- **Fingerprints detect drift.** BLAKE3 over content + child fingerprints. Diff two trees node-by-node.

---

## Quick start

```python
from docpatch import open_doc, edit_doc
from docpatch.models.anthropic import AnthropicClient

tree = open_doc("spec.md")
model = AnthropicClient(model="claude-haiku-4-5-20251001")

patched = edit_doc(tree, "Tighten the introduction", model=model)

from docpatch.parsers import get_parser, detect_format
parser = get_parser(detect_format("spec.md", None))
open("spec.md", "wb").write(parser.serialize(patched))
```

Or from the command line:

```bash
docpatch edit README.md "Tighten the introduction" --model anthropic
docpatch edit spec.md "Add a rate-limits note" --dry-run
```

---

## Manual pipeline

```python
from docpatch.parsers.markdown import parse, serialize
from docpatch.locator import CompositeLocator
from docpatch.patcher.replace import ReplaceOperation
from docpatch.splicer import splice, validate_splice
from docpatch.models.mock import MockModelClient

# 1. Parse
data = open("report.md", "rb").read()
tree = parse(data)

# 2. Locate — symbolic regex first, LLM semantic fallback
model = MockModelClient(response="Rewritten content.")
locator = CompositeLocator(model=model, threshold=0.6)
result = locator.locate(tree, "Replace the executive summary")

# 3. Patch — only the target node reaches the model
op = ReplaceOperation(max_retry=3)
patch = op.apply(tree, result.node_ids[0], "Tighten and clarify", model)

# 4. Splice — deterministic, no model call
new_tree = splice(tree, [patch])
assert validate_splice(tree, new_tree, [patch]).ok

# 5. Serialize — unchanged regions are their original bytes
open("report.md", "wb").write(serialize(new_tree))
```

---

## Bring your own model

Any object that implements the `ModelClient` protocol works:

```python
from docpatch.models.base import ModelClient, ModelResponse

class MyLLM:
    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        raw = my_local_model.generate(prompt, max_tokens=max_tokens)
        return ModelResponse(
            text=raw.text,
            tokens_in=raw.usage.prompt,
            tokens_out=raw.usage.completion,
            model_id="my-model",
        )

patched = edit_doc(tree, "Rewrite intro", model=MyLLM())
```

Built-in clients: `AnthropicClient` (`docpatch[anthropic]`), `OpenAIClient` (`docpatch[openai]`), `MockModelClient` (for tests, no extras required).

---

## Inspect the DocTree

```python
from docpatch.parsers.markdown import parse

tree = parse(open("README.md", "rb").read())

# Walk every node depth-first
for node in tree.walk():
    print(node.id, node.type, node.fingerprint[:12])

# Look up by deterministic ID
node = tree.get_node("heading:document:root/installation#0")

# Heading skeleton — what SemanticLocator sends to the model
# (headings only, never paragraph bodies)
print(tree.heading_skeleton())
```

---

## Supported formats (v0.1)

| Format | Parse | Serialize | Round-trip |
|--------|-------|-----------|------------|
| Markdown (`.md`) | ✓ | ✓ | byte-exact |
| JSON (`.json`) | ✓ | ✓ | byte-exact |

DOCX (v0.2), PDF (v0.3), and further formats are on the [roadmap](#roadmap).

---

## CLI reference

```
Usage: docpatch edit FILE INSTRUCTION [OPTIONS]

Options:
  --model TEXT     Model provider: mock | anthropic | openai  [default: mock]
  --out TEXT       Output path (default: overwrite in-place)
  --dry-run        Print result, do not write
  --api-key TEXT   Provider API key (or set DOCPATCH_API_KEY)
  --help
```

---

## Integrations

[integrations.md](integrations.md) covers three integration levels in depth:

- **Streaming content** — `parse_text()` for in-memory strings and streamed LLM output (Anthropic, OpenAI, generic iterator)
- **Agentic patterns** — generate → verify → patch refinement loops, atomic multi-patch transactions, model routing by node type, batch editing across document collections
- **Framework adapters** — LangChain (`LangChainModelClient` + `@tool`), CrewAI (`@crewai_tool`), generic OpenAI function schema, MCP server (v0.9)
- **Custom pipelines** — implementing `Locator`, `Operation`, and `ModelClient` from scratch; full protocol reference

---

## Development

```bash
uv venv && uv sync --all-extras --dev
uv run pytest -x
uv run pytest --cov=docpatch tests/
uv run mypy --strict src
uv run ruff check --fix src tests
```

Requirements: Python 3.11+, [uv](https://github.com/astral-sh/uv).

---

## Roadmap

| Version | Target | Scope |
|---------|--------|-------|
| **v0.1** | ✓ shipped | Markdown + JSON, locate, replace, splice, CLI |
| v0.2 | +3 weeks | DOCX with tracked-changes mode |
| v0.3 | +4 weeks | PDF (text-layer + OCR fallback) |
| v0.4 | +2 weeks | insert, delete, move, split, merge operations |
| v0.5 | +3 weeks | Git-backed history, `docpatch log/diff/revert` |
| v0.6 | +3 weeks | Reference graph, dependency tracking |
| v0.7 | +4 weeks | Server (FastAPI, BSL-1.1), Postgres, S3 |
| v1.0 | +4 weeks | Stable public API, signed PyPI release |

---

## License

- **Core library** (`src/docpatch/` excluding `server/`): Apache-2.0
- **Server** (`src/docpatch/server/`): Business Source License 1.1 — converts to Apache-2.0 four years after each release

See [LICENSE](LICENSE) and [LICENSE-SERVER](LICENSE-SERVER).
