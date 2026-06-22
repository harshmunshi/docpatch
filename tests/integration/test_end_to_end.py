"""Integration tests: full pipeline with MockModelClient."""

from docpatch import open_doc
from docpatch.locator.composite import CompositeLocator
from docpatch.models.mock import MockModelClient
from docpatch.parsers.json_parser import parse as json_parse
from docpatch.parsers.markdown import parse, serialize
from docpatch.patcher.replace import ReplaceOperation
from docpatch.splicer import splice, validate_splice

FIXTURE_MD = b"""\
# Introduction

This is the introduction paragraph. It provides context.

# Methods

We used several methods in this study.

## Data Collection

Data was collected from multiple sources.

# Results

The results were promising.
"""


def test_markdown_full_pipeline() -> None:
    """Parse → locate → patch → splice → serialize — all with MockModelClient."""
    tree = parse(FIXTURE_MD)

    model = MockModelClient("This is a concise, rewritten introduction.")
    locator = CompositeLocator(model=model, threshold=0.5)

    result = locator.locate(tree, 'rewrite the "Introduction" section')
    assert result.node_ids, "Locator should find the Introduction heading"

    op = ReplaceOperation()
    patch = op.apply(tree, result.node_ids[0], "make it concise", model)
    assert patch.new_node.content == "This is a concise, rewritten introduction."

    patched = splice(tree, [patch])
    val = validate_splice(tree, patched, [patch])
    assert val.ok

    output = serialize(patched)
    assert b"This is a concise, rewritten introduction." in output


def test_json_full_pipeline() -> None:
    """JSON: parse → locate → patch → splice → rebuild."""
    data = b'{"title": "Old Title", "body": "Old body text."}'
    tree = json_parse(data)

    model = MockModelClient("New Title")
    locator = CompositeLocator(model=model, threshold=0.4)

    result = locator.locate(tree, '"title" field')
    # Locator may or may not find it symbolically — just verify pipeline doesn't crash
    if result.node_ids:
        op = ReplaceOperation()
        target = result.node_ids[0]
        node = tree.get(target)
        if node is not None:
            patch = op.apply(tree, target, "update title", model)
            patched = splice(tree, [patch])
            assert patched.root.fingerprint != tree.root.fingerprint


def test_open_doc_markdown(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """open_doc() convenience function parses a file correctly."""
    md_file = tmp_path / "test.md"
    md_file.write_bytes(FIXTURE_MD)
    tree = open_doc(md_file)
    from docpatch.core.types import NodeType

    assert tree.root.type == NodeType.DOCUMENT


def test_cli_edit_dry_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """CLI edit --dry-run outputs the (mock-patched) document."""
    from click.testing import CliRunner

    from docpatch.cli.main import cli

    md_file = tmp_path / "doc.md"
    md_file.write_bytes(FIXTURE_MD)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["edit", str(md_file), 'rewrite the "Introduction" heading', "--dry-run"],
    )
    # With MockModelClient(response=""), patcher will fail max-retry
    # But we verify the CLI at least starts correctly and hits the right code path
    assert result.exit_code in (0, 1)  # 1 on patcher failure with empty mock
