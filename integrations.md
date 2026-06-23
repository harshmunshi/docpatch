# DocPatch Integration Guide

This guide covers three integration patterns in increasing order of control:

1. **Inline content** — parse and edit text produced by an LLM, not a file on disk.
2. **Framework adapters** — plug DocPatch into LangChain, CrewAI, or any tool-calling framework.
3. **Custom workflows** — compose the primitives directly for full pipeline control.

All three patterns share the same seam: the `ModelClient` protocol. Any object that satisfies

```python
def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse: ...
```

can drive locate and patch. Adapting a new framework is almost always just wrapping its LLM client in that one method.

---

## The core pipeline (reference)

```
bytes/str
  └─ parse()      →  DocTree
       └─ locate()  →  LocateResult  (node IDs + confidence)
            └─ apply()  →  Patch         (new_node + token counts)
                 └─ splice()  →  DocTree
                      └─ serialize()  →  bytes/str
```

Every integration pattern is a variation on where the input comes from, how the `ModelClient` is wired, and what happens to the output.

---

## 1. Inline and Generated Content

### Problem

`open_doc(path)` reads from disk. But in an agentic loop the content often lives in memory: an LLM just generated a draft, a retriever just assembled context, or an upstream step returned a string. There is no file.

### Solution: `parse_text()`

Add a convenience function next to `open_doc` in `docpatch/__init__.py`:

```python
def parse_text(text: str, *, fmt: DocFormat = DocFormat.MARKDOWN) -> DocTree:
    """Parse an in-memory string into a DocTree without touching the filesystem."""
    parser = get_parser(fmt)
    return parser.parse(text.encode())
```

With this in place the full flow is:

```python
from docpatch import parse_text, edit_doc, DocFormat
from docpatch.parsers.markdown import serialize

# 1. Generate a draft with any LLM (result is a plain string)
draft = my_llm.generate("Write a one-page design doc for a rate-limiter service.")

# 2. Parse into an addressable tree — no file involved
tree = parse_text(draft, fmt=DocFormat.MARKDOWN)

# 3. Edit a specific section surgically
patched = edit_doc(tree, "Make the 'Failure modes' section more concise.", model=my_client)

# 4. Get the result back as a string
result = serialize(patched).decode()
```

### Pattern: generate → verify → patch in a loop

The more interesting agentic pattern is using DocPatch inside a refinement loop. The generator never sees the whole document on a retry — only the node that failed validation.

```python
from docpatch import parse_text, edit_doc
from docpatch.parsers.markdown import serialize
from docpatch.core.types import DocFormat

def generate_and_refine(prompt: str, validators: list[callable], model) -> str:
    draft = model.complete(prompt, max_tokens=2048).text
    tree = parse_text(draft)

    for validator in validators:
        issues = validator(tree)
        for issue in issues:
            # Only the failing node goes back to the model
            tree = edit_doc(tree, issue.fix_instruction, model=model)

    return serialize(tree).decode()
```

The key property: the validator sees the full DocTree (structural checks, word counts, heading hierarchy), but the LLM fix call only receives the failing subtree. Token cost stays flat regardless of document length.

### What needs to be built

| Item | Status |
|------|--------|
| `parse_text(text, fmt)` convenience function | **Needs adding** to `__init__.py` |
| `serialize_to_str(tree)` convenience function | **Needs adding** (wraps `serialize(tree).decode()`) |
| `DocFormat` auto-detection from MIME type / extension string | Available via `detect_format()` — needs thin wrapper |

No new layers required. These are three lines in `__init__.py` each.

---

## 2. Framework Integrations

The integration surface is always the same: wrap the framework's LLM client into `ModelClient`, then expose DocPatch as a **tool** the agent can call.

### 2a. LangChain

#### Step 1 — Wrap `BaseChatModel` into `ModelClient`

LangChain's `invoke()` returns an `AIMessage`. The adapter is trivial:

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from docpatch.models.base import ModelClient, ModelResponse

class LangChainModelClient:
    """Adapt any LangChain BaseChatModel to DocPatch's ModelClient protocol."""

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        msg = self._llm.invoke(
            [HumanMessage(content=prompt)],
            config={"max_tokens": max_tokens},
        )
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        usage = getattr(msg, "usage_metadata", None)
        return ModelResponse(
            text=text,
            tokens_in=getattr(usage, "input_tokens", 0),
            tokens_out=getattr(usage, "output_tokens", 0),
            model_id=getattr(self._llm, "model_name", ""),
        )
```

#### Step 2 — Expose DocPatch as a LangChain `@tool`

```python
from langchain_core.tools import tool
from docpatch import open_doc, edit_doc
from docpatch.parsers import get_parser, detect_format
from pathlib import Path

def make_docpatch_tool(llm: BaseChatModel):
    client = LangChainModelClient(llm)

    @tool
    def edit_document(file_path: str, instruction: str) -> str:
        """
        Edit a specific section of a document.
        Uses surgical patching — only the relevant node is sent to the model.

        Args:
            file_path: Path to a Markdown or JSON file.
            instruction: Natural-language description of the change to make.

        Returns:
            Confirmation message with token savings summary.
        """
        p = Path(file_path)
        tree = open_doc(p)
        patched = edit_doc(tree, instruction, model=client)

        fmt = detect_format(p, p.read_bytes())
        parser = get_parser(fmt)
        p.write_bytes(parser.serialize(patched))
        return f"Edited '{p.name}' — {instruction}"

    return edit_document
```

Usage with a LangChain agent:

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor

llm = ChatOpenAI(model="gpt-4o")
tools = [make_docpatch_tool(llm)]
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
executor.invoke({"input": "Tighten the intro section in README.md"})
```

#### Optional: LangChain document loader

When you want to use DocPatch trees as context in a retrieval chain rather than editing:

```python
from langchain_core.documents import Document as LCDocument
from langchain_core.document_loaders import BaseLoader
from docpatch import open_doc
from docpatch.core.types import NodeType

class DocPatchLoader(BaseLoader):
    """Load a file as individual DocTree nodes — one LangChain Document per node."""

    def __init__(self, path: str, node_types: set[NodeType] | None = None) -> None:
        self._path = path
        self._filter = node_types or {NodeType.PARAGRAPH, NodeType.HEADING}

    def lazy_load(self):
        tree = open_doc(self._path)
        for node in tree.walk():
            if node.type in self._filter and node.content:
                yield LCDocument(
                    page_content=node.content,
                    metadata={"node_id": node.id, "source": self._path},
                )
```

This enables RAG over structured document nodes. When the retriever surfaces a node, you have its `node_id` and can pass it directly to a targeted patch operation — bypassing the locator entirely for a zero-overhead edit.

### 2b. CrewAI

CrewAI uses the `@tool` decorator directly on functions. The adapter pattern is the same; only the decorator changes.

```python
from crewai.tools import tool as crewai_tool
from docpatch import open_doc, edit_doc
from docpatch.models.openai import OpenAIClient
from pathlib import Path

@crewai_tool("Document Editor")
def edit_document(file_path: str, instruction: str) -> str:
    """
    Edit a specific section of a document with surgical precision.
    Only the relevant passage is sent to the LLM — the rest of the document is untouched.
    """
    model = OpenAIClient()  # reads OPENAI_API_KEY from env
    p = Path(file_path)
    tree = open_doc(p)
    patched = edit_doc(tree, instruction, model=model)

    from docpatch.parsers import detect_format, get_parser
    parser = get_parser(detect_format(p, p.read_bytes()))
    p.write_bytes(parser.serialize(patched))
    return f"Done: {instruction}"
```

Attach to a CrewAI agent:

```python
from crewai import Agent

editor_agent = Agent(
    role="Technical Writer",
    goal="Keep documentation accurate and concise.",
    backstory="You improve technical documents section by section.",
    tools=[edit_document],
    verbose=True,
)
```

The important point: because DocPatch only sends the target node to the model, the CrewAI agent's token budget is not consumed by re-processing unchanged sections. A 100-page spec costs the same as a 1-page note for a targeted edit.

### 2c. Generic tool-calling pattern (OpenAI function schema)

Any framework that accepts OpenAI-style function definitions can use this schema directly:

```json
{
  "name": "edit_document",
  "description": "Edit a specific section of a document. Only the relevant node is patched — the rest is untouched.",
  "parameters": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "Path to the document (Markdown or JSON)."
      },
      "instruction": {
        "type": "string",
        "description": "Natural-language instruction describing what to change and where."
      }
    },
    "required": ["file_path", "instruction"]
  }
}
```

The corresponding Python handler is the same `edit_document` function body from the examples above — framework-independent. Register it against whichever dispatcher your framework uses (AutoGen's `register_function`, Haystack's `ComponentBase`, Semantic Kernel's `kernel_function`, etc.).

### What needs to be built

| Item | Status | Target version |
|------|--------|----------------|
| `LangChainModelClient` adapter class | **Needs building** | v0.9 |
| `DocPatchLoader` LangChain document loader | **Needs building** | v0.9 |
| `DocPatchTool` factory (importable, not hand-rolled) | **Needs building** | v0.9 |
| CrewAI tool wrapper | **Needs building** | v0.9 |
| MCP server (exposes DocPatch to any MCP-aware agent) | **Needs building** | v0.9 |
| Official Haystack / LlamaIndex integrations | **Needs building** | v0.9 |

The adapters above can all be written today against the existing v0.1 API. Nothing in the core needs to change. The v0.9 work is packaging, testing, and publishing these as installable extras (`pip install "docpatch[langchain]"`).

---

## 3. Custom Workflows

When the built-in `edit_doc()` is too coarse — you want multi-step operations, conditional branching, custom locator logic, or your own model routing — use the primitives directly.

### 3a. Ground-up pipeline

```python
from pathlib import Path
from docpatch.parsers.markdown import parse, serialize
from docpatch.locator.composite import CompositeLocator
from docpatch.patcher.replace import ReplaceOperation
from docpatch.splicer import splice
from docpatch.models.openai import OpenAIClient

model = OpenAIClient(model="gpt-4o-mini")
locator = CompositeLocator(model=model, threshold=0.6)
patcher = ReplaceOperation(max_retry=3)

data = Path("spec.md").read_bytes()
tree = parse(data)

# Locate
result = locator.locate(tree, "Tighten the 'Failure modes' section")
if result.confidence < 0.6:
    raise ValueError(f"Low confidence ({result.confidence:.2f}); candidates: {result.candidates}")

# Patch
patch = patcher.apply(tree, result.node_ids[0], "Tighten the 'Failure modes' section", model)

# Splice and write
new_tree = splice(tree, [patch])
Path("spec.md").write_bytes(serialize(new_tree))

print(f"Tokens in: {patch.tokens_in}, out: {patch.tokens_out}")
```

### 3b. Multi-patch transactions

`splice()` accepts a list of patches and applies them in one pass. All patches reference node IDs from the original tree — they do not compose with each other, so ordering is irrelevant and conflicts are caught at splice time.

```python
instructions = [
    ("Tighten the intro", "heading:document:root/introduction#0"),
    ("Add a note about rate limiting", "paragraph:document:root/failure-modes#2"),
]

patches = []
for instruction, node_id in instructions:
    patch = patcher.apply(tree, node_id, instruction, model)
    patches.append(patch)

# All patches applied atomically
new_tree = splice(tree, patches)
```

If two patches target the same node, `splice()` raises `SpliceError.CONFLICT`. Handle it by re-locating and re-patching on the merged tree.

### 3c. Implementing a custom Locator

Any class satisfying the `Locator` protocol can replace the built-in locators:

```python
from docpatch.locator.base import LocateResult, Locator
from docpatch.core.tree import DocTree

class NodeIdLocator:
    """Bypass the LLM entirely — caller already knows the node ID."""

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        # instruction is treated as a raw node ID
        if instruction in tree:
            return LocateResult(node_ids=[instruction], confidence=1.0, method="direct")
        return LocateResult(node_ids=[], confidence=0.0, method="direct")
```

Use cases for custom locators:
- **Direct addressing** — the node ID is known (e.g., returned by a previous DocPatchLoader retrieval).
- **Schema-driven** — for JSON documents, address by JSON Pointer without LLM involvement.
- **Vector-based** — embed the skeleton and do nearest-neighbor search instead of a generative call.
- **Rule-based** — regex or XPath over the content for deterministic targeting.

### 3d. Implementing a custom ModelClient

Wrap any completion API in one method:

```python
import anthropic
from docpatch.models.base import ModelClient, ModelResponse

class AnthropicBatchClient:
    """
    Uses Anthropic's Message Batches API for async high-volume edits.
    complete() submits a batch request and blocks until the result arrives.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        # For illustration — replace with actual batch submission + poll
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return ModelResponse(
            text=msg.content[0].text,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            model_id=msg.model,
        )
```

Because `ModelClient` is a `Protocol`, Python's structural typing guarantees compatibility without inheriting from a base class. The class above satisfies `isinstance(client, ModelClient)` at runtime.

### 3e. Routing by node type

Use different models for different node types to control cost:

```python
from docpatch.core.types import NodeType
from docpatch.models.openai import OpenAIClient
from docpatch.models.anthropic import AnthropicClient

cheap = OpenAIClient(model="gpt-4o-mini")
powerful = AnthropicClient(model="claude-sonnet-4-6")

def route(tree, node_id):
    node = tree.get(node_id)
    if node and node.type == NodeType.CODE_BLOCK:
        return powerful   # code edits need stronger reasoning
    return cheap          # prose edits are cheaper

result = locator.locate(tree, instruction)
model = route(tree, result.node_ids[0])
patch = patcher.apply(tree, result.node_ids[0], instruction, model)
```

### 3f. Batching across documents

For bulk editing (many files, same instruction), parse and patch in parallel, serialize when done:

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from docpatch import open_doc, edit_doc
from docpatch.parsers.markdown import serialize
from docpatch.models.openai import OpenAIClient

model = OpenAIClient(model="gpt-4o-mini")
files = list(Path("docs/").glob("**/*.md"))

def process(p: Path) -> None:
    tree = open_doc(p)
    patched = edit_doc(tree, "Ensure every section has a concrete example.", model=model)
    p.write_bytes(serialize(patched))
    print(f"Done: {p}")

with ThreadPoolExecutor(max_workers=8) as pool:
    pool.map(process, files)
```

`OpenAIClient` is stateless (no shared mutable state), so concurrent calls are safe. The `DocTree` objects are immutable pydantic models — `edit_doc` returns a new tree, it does not mutate the input.

### What needs to be built

| Item | Status |
|------|--------|
| `splice()` conflict detection and `SpliceError.CONFLICT` | **Needs adding** to splicer |
| `NodeIdLocator` (bypass LLM when ID is known) | **Needs adding** to `locator/` |
| `patcher/insert.py`, `delete.py`, `move.py` | Planned v0.4 |
| Composite multi-operation transaction helper | Planned v0.4 |

---

## Protocol reference

### `ModelClient`

```python
class ModelClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse: ...
```

`ModelResponse` fields: `text: str`, `tokens_in: int`, `tokens_out: int`, `model_id: str`.

### `Locator`

```python
class Locator(Protocol):
    def locate(self, tree: DocTree, instruction: str) -> LocateResult: ...
```

`LocateResult` fields: `node_ids: list[str]`, `confidence: float`, `candidates: list[str]`, `method: str`.

### `Operation`

```python
class Operation(Protocol):
    def apply(self, tree: DocTree, target_id: str, instruction: str, model: ModelClient) -> Patch: ...
    def validate(self, patch: Patch, tree: DocTree) -> ValidationResult: ...
```

`Patch` fields: `target_id: str`, `operation: str`, `new_node: Node`, `tokens_in: int`, `tokens_out: int`, `model_id: str`.

---

## Decision guide

| Situation | Recommended pattern |
|-----------|---------------------|
| Simple agentic loop; one file at a time | `open_doc` + `edit_doc` + `parse_text` |
| Using LangChain agents | `LangChainModelClient` + `make_docpatch_tool` |
| Using CrewAI agents | `@crewai_tool` wrapping `edit_doc` |
| Known node ID from retrieval | `NodeIdLocator` — skip the LLM locate step |
| Multi-section edits atomically | Build a `patches: list[Patch]` then `splice(tree, patches)` |
| Different models per node type | Custom routing function before `patcher.apply()` |
| Bulk edit across many files | `ThreadPoolExecutor` over `edit_doc` — stateless and safe |
| Full programmatic control | Raw `parse → locate → apply → splice → serialize` pipeline |
