"""Demonstrates how many tokens DocPatch saves vs. the naive whole-document approach.

Scenario: change one sentence in the 'Why DocPatch' paragraph of README.md.

Naive approach  — send the full document as the prompt.
DocPatch approach — send only the target node + breadcrumb (the actual prompt
                   that ReplaceOperation builds).

Token counting: approximated with the standard rule-of-thumb: 1 token ≈ 4 chars.
This is intentionally model-agnostic so the test has no network dependency.
We verify that the savings are substantial (≥ 70 %) rather than pinning an exact
number, so the test stays valid as the README grows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from docpatch.core.types import NodeType
from docpatch.parsers.markdown import parse
from docpatch.patcher.replace import _build_breadcrumb

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_README = Path(__file__).parents[2] / "README.md"
_PROMPT_TEMPLATE_DIR = Path(__file__).parents[2] / "src/docpatch/patcher/prompts"

INSTRUCTION = "Add a note that DocPatch is model-agnostic."


def _approx_tokens(text: str) -> int:
    """1 token ≈ 4 characters (OpenAI / Anthropic rule of thumb)."""
    return max(1, len(text) // 4)


def _render_replace_prompt(breadcrumb: str, target_id: str, node_type: str, content: str) -> str:
    env = Environment(loader=FileSystemLoader(str(_PROMPT_TEMPLATE_DIR)), autoescape=False)
    tmpl = env.get_template("replace.j2")
    return tmpl.render(
        breadcrumb=breadcrumb,
        target_id=target_id,
        node_type=node_type,
        target_content=content,
        instruction=INSTRUCTION,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def readme_bytes() -> bytes:
    return _README.read_bytes()


@pytest.fixture(scope="module")
def readme_tree(readme_bytes: bytes):  # type: ignore[no-untyped-def]
    return parse(readme_bytes)


@pytest.fixture(scope="module")
def target_node(readme_tree):  # type: ignore[no-untyped-def]
    """First paragraph under the 'Why DocPatch' section."""
    paragraphs = [n for n in readme_tree.walk() if n.type == NodeType.PARAGRAPH]
    # pick the paragraph that contains the core value proposition
    for p in paragraphs:
        if p.content and "Sending a whole document" in p.content:
            return p
    pytest.fail("Could not find the target paragraph in README.md")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTokenSavings:
    """Token-saving metrics for a targeted README edit."""

    def test_target_node_found(self, target_node) -> None:  # type: ignore[no-untyped-def]
        assert target_node is not None
        assert target_node.content

    def test_naive_tokens(self, readme_bytes: bytes) -> None:
        """Naive: model receives the whole document as the prompt."""
        full_text = readme_bytes.decode("utf-8", errors="replace")
        tokens = _approx_tokens(full_text)
        # README is non-trivial — sanity check it's at least 500 tokens
        assert tokens >= 500, f"README seems too short: {tokens} tokens"

    def test_docpatch_prompt_is_much_shorter(self, readme_tree, target_node) -> None:  # type: ignore[no-untyped-def]
        breadcrumb = _build_breadcrumb(readme_tree, target_node.id)
        prompt = _render_replace_prompt(
            breadcrumb=breadcrumb,
            target_id=target_node.id,
            node_type=str(target_node.type),
            content=target_node.content or "",
        )
        readme_text = (readme_tree.root.raw_span or b"").decode("utf-8", errors="replace")
        # Fall back to serializing from the fixture bytes via the tree walk
        if not readme_text:
            # raw_span on the root may be absent; sum all node raw_spans instead
            readme_text = "".join(
                (n.raw_span or b"").decode("utf-8", errors="replace")
                for n in readme_tree.walk()
                if n.raw_span
            )

        naive_tokens = _approx_tokens(
            readme_tree.root.content  # not useful
            or readme_text
            or _README.read_text()
        )
        docpatch_tokens = _approx_tokens(prompt)

        saving_pct = (1 - docpatch_tokens / naive_tokens) * 100

        # Print a human-readable summary (visible with pytest -s or in CI logs)
        print(
            f"\n{'─' * 60}\n"
            f"  README edit token-savings report\n"
            f"{'─' * 60}\n"
            f"  Document  : {_README.name}  ({len(_README.read_bytes())} bytes)\n"
            f"  Target    : {target_node.id}\n"
            f"  Instruction: {INSTRUCTION!r}\n"
            f"\n"
            f"  Naive tokens (whole doc)  : {naive_tokens:>7,}\n"
            f"  DocPatch tokens (node+bc) : {docpatch_tokens:>7,}\n"
            f"  Tokens saved              : {naive_tokens - docpatch_tokens:>7,}\n"
            f"  Saving                    : {saving_pct:>6.1f}%\n"
            f"{'─' * 60}"
        )

        assert saving_pct >= 70, (
            f"Expected ≥ 70% token saving, got {saving_pct:.1f}%. "
            f"DocPatch prompt ({docpatch_tokens} tokens) vs. naive ({naive_tokens} tokens)."
        )

    def test_breadcrumb_contains_section_heading(self, readme_tree, target_node) -> None:  # type: ignore[no-untyped-def]
        """Breadcrumb must name the ancestor heading so the model has context."""
        breadcrumb = _build_breadcrumb(readme_tree, target_node.id)
        assert "Why DocPatch" in breadcrumb, (
            f"Expected 'Why DocPatch' in breadcrumb; got: {breadcrumb!r}"
        )

    def test_prompt_contains_target_content(self, readme_tree, target_node) -> None:  # type: ignore[no-untyped-def]
        """The rendered prompt must include the node's actual text."""
        breadcrumb = _build_breadcrumb(readme_tree, target_node.id)
        prompt = _render_replace_prompt(
            breadcrumb=breadcrumb,
            target_id=target_node.id,
            node_type=str(target_node.type),
            content=target_node.content or "",
        )
        assert "Sending a whole document" in prompt

    def test_savings_breakdown(self, readme_tree, target_node) -> None:  # type: ignore[no-untyped-def]
        """Parametric view: assert each prompt component is smaller than the full doc."""
        readme_tokens = _approx_tokens(_README.read_text())
        breadcrumb = _build_breadcrumb(readme_tree, target_node.id)
        node_content = target_node.content or ""

        breadcrumb_tokens = _approx_tokens(breadcrumb)
        node_tokens = _approx_tokens(node_content)
        instruction_tokens = _approx_tokens(INSTRUCTION)

        assert breadcrumb_tokens < readme_tokens, "Breadcrumb must be shorter than full doc"
        assert node_tokens < readme_tokens, "Node content must be shorter than full doc"
        assert (breadcrumb_tokens + node_tokens + instruction_tokens) < readme_tokens, (
            "Sum of prompt components must be shorter than full doc"
        )
