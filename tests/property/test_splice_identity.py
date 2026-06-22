"""Property tests: splice(tree, []) == tree."""

from hypothesis import given, settings
from hypothesis import strategies as st

from docpatch.parsers.markdown import parse
from docpatch.splicer.splice import splice


@st.composite
def markdown_doc(draw: st.DrawFn) -> bytes:
    words = ["Hello", "World", "Intro", "Body", "Conclusion", "Section"]
    lines: list[str] = []
    n = draw(st.integers(min_value=1, max_value=3))
    for i in range(n):
        heading = draw(st.sampled_from(words))
        lines.append(f"# {heading}")
        lines.append("")
        lines.append(f"Paragraph {i}.")
        lines.append("")
    return "\n".join(lines).encode()


@settings(max_examples=30, deadline=5000)
@given(markdown_doc())
def test_splice_identity(data: bytes) -> None:
    """splice(tree, []) returns a tree with the same root fingerprint."""
    if not data.strip():
        return
    tree = parse(data)
    patched = splice(tree, [])
    assert patched.root.fingerprint == tree.root.fingerprint
