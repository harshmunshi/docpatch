"""ReplaceOperation — replaces a node's content via an LLM call."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from docpatch.core.errors import PatchError
from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeRef
from docpatch.models.base import ModelClient
from docpatch.patcher.base import Patch, ValidationResult

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)


def _build_breadcrumb(tree: DocTree, target_id: NodeRef) -> str:
    """Ancestor headings + sibling heading names — never sibling bodies."""
    ancestors = tree.ancestors(target_id)
    ancestor_text = " > ".join(a.content for a in ancestors if a.content)
    parent = tree.parent(target_id)
    sibling_headings: list[str] = []
    if parent is not None:
        for sibling in parent.children:
            if sibling.id != target_id and sibling.content:
                sibling_headings.append(sibling.content)
    sibling_text = ", ".join(sibling_headings[:5])
    parts = []
    if ancestor_text:
        parts.append(f"Path: {ancestor_text}")
    if sibling_text:
        parts.append(f"Siblings: {sibling_text}")
    return "\n".join(parts) or "(root)"


class ReplaceOperation:
    """Replace the content of a target node using a model call."""

    def __init__(self, max_retry: int = 3, max_tokens: int = 4096) -> None:
        self._max_retry = max_retry
        self._max_tokens = max_tokens

    def apply(
        self,
        tree: DocTree,
        target_id: NodeRef,
        instruction: str,
        model: ModelClient,
    ) -> Patch:
        node = tree.get(target_id)
        if node is None:
            raise PatchError(PatchError.Kind.TARGET_NOT_FOUND, target_id)

        breadcrumb = _build_breadcrumb(tree, target_id)
        target_content = node.content or (
            node.raw_span.decode("utf-8", errors="replace") if node.raw_span else ""
        )

        template = _JINJA_ENV.get_template("replace.j2")
        prompt = template.render(
            breadcrumb=breadcrumb,
            target_id=target_id,
            node_type=node.type,
            target_content=target_content,
            instruction=instruction,
        )

        last_error = ""
        for attempt in range(self._max_retry):
            resp = model.complete(prompt, max_tokens=self._max_tokens)
            new_content = resp.text.strip()
            if not new_content:
                last_error = f"attempt {attempt + 1}: empty model response"
                continue

            new_node = node.replace(content=new_content, raw_span=None, children=())
            patch = Patch(
                target_id=target_id,
                operation="replace",
                new_node=new_node,
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                model_id=resp.model_id,
            )
            result = self.validate(patch, tree)
            if result.ok:
                return patch
            last_error = result.error

        raise PatchError(PatchError.Kind.MAX_RETRY_EXCEEDED, last_error)

    def validate(self, patch: Patch, tree: DocTree) -> ValidationResult:
        """Structural validation: new node must have content and same type as original."""
        if not patch.new_node.content:
            return ValidationResult(ok=False, error="replacement content is empty")
        original = tree.get(patch.target_id)
        if original is None:
            return ValidationResult(ok=False, error=f"target {patch.target_id} not in tree")
        if patch.new_node.type != original.type:
            return ValidationResult(
                ok=False,
                error=f"type mismatch: {original.type} → {patch.new_node.type}",
            )
        return ValidationResult(ok=True)


def _build_node_from_response(original: Node, new_content: str) -> Node:
    """Helper kept for potential future use."""
    return original.replace(content=new_content, raw_span=None, children=())
