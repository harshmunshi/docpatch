"""docpatch edit FILE INSTRUCTION — end-to-end edit command."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from docpatch.config import Settings
from docpatch.core.errors import LocateError
from docpatch.locator import CompositeLocator
from docpatch.models.base import ModelClient
from docpatch.models.mock import MockModelClient
from docpatch.parsers import detect_format, get_parser
from docpatch.patcher.replace import ReplaceOperation
from docpatch.splicer import splice, validate_splice


@click.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.argument("instruction")
@click.option("--model", "model_name", default="mock", help="Model provider: mock|anthropic|openai")
@click.option("--out", default=None, help="Output path (default: overwrite in-place)")
@click.option("--dry-run", is_flag=True, default=False, help="Print result, do not write.")
@click.option("--api-key", default=None, envvar="DOCPATCH_API_KEY", help="Provider API key.")
@click.pass_context
def edit(
    ctx: click.Context,
    file: str,
    instruction: str,
    model_name: str,
    out: str | None,
    dry_run: bool,
    api_key: str | None,
) -> None:
    """Edit FILE according to INSTRUCTION using an LLM."""
    settings = Settings()
    path = Path(file)
    data = path.read_bytes()

    from typing import cast

    from docpatch.core.tree import DocTree

    fmt = detect_format(path, data)
    parser = get_parser(fmt)
    tree = cast(DocTree, parser.parse(data))

    model = _build_model(model_name, api_key)
    locator = CompositeLocator(
        model=model,
        threshold=settings.semantic_locator_threshold,
        max_tokens=settings.max_tokens,
    )

    try:
        locate_result = locator.locate(tree, instruction)
    except LocateError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not locate_result.node_ids:
        click.echo("Could not locate a target node. Candidates:", err=True)
        for c in locate_result.candidates:
            click.echo(f"  {c}", err=True)
        sys.exit(1)

    if (
        locate_result.confidence < settings.semantic_locator_threshold
        and not locate_result.node_ids
    ):
        click.echo(
            f"Ambiguous target (confidence={locate_result.confidence:.2f}). "
            "Use a more specific instruction.",
            err=True,
        )
        sys.exit(1)

    op = ReplaceOperation(max_retry=settings.max_retry, max_tokens=settings.max_tokens)
    target_id = locate_result.node_ids[0]
    patch = op.apply(tree, target_id, instruction, model)

    patched_tree = splice(tree, [patch])
    result = validate_splice(tree, patched_tree, [patch])
    if not result.ok:
        click.echo(f"Splice validation failed: {result.error}", err=True)
        sys.exit(1)

    output_bytes = cast(bytes, parser.serialize(patched_tree))

    if dry_run:
        click.echo(output_bytes.decode("utf-8", errors="replace"))
        return

    out_path = Path(out) if out else path
    out_path.write_bytes(output_bytes)
    click.echo(f"Wrote {len(output_bytes)} bytes to {out_path}")


def _build_model(name: str, api_key: str | None) -> ModelClient:
    if name == "mock":
        return MockModelClient()
    if name == "anthropic":
        from docpatch.models.anthropic import AnthropicClient

        return AnthropicClient(api_key=api_key)
    if name == "openai":
        from docpatch.models.openai import OpenAIClient

        return OpenAIClient(api_key=api_key)
    click.echo(f"Unknown model: {name}. Use mock|anthropic|openai.", err=True)
    sys.exit(1)
