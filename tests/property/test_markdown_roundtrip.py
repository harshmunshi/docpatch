"""Property tests: serialize(parse(x)) == x for Markdown."""

from hypothesis import given, settings
from hypothesis import strategies as st

from docpatch.parsers.markdown import parse, serialize

# Generate realistic Markdown documents
_HEADING_LEVELS = st.integers(min_value=1, max_value=4)
_WORDS = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=12,
)
_SENTENCE = st.lists(_WORDS, min_size=2, max_size=8).map(lambda ws: " ".join(ws) + ".")


@st.composite
def markdown_doc(draw: st.DrawFn) -> bytes:
    """Generate a simple but realistic Markdown document."""
    lines: list[str] = []
    num_sections = draw(st.integers(min_value=1, max_value=4))
    for _ in range(num_sections):
        level = draw(_HEADING_LEVELS)
        heading_text = draw(_WORDS)
        lines.append(f"{'#' * level} {heading_text}")
        lines.append("")
        num_paras = draw(st.integers(min_value=1, max_value=3))
        for _ in range(num_paras):
            sentence = draw(_SENTENCE)
            lines.append(sentence)
            lines.append("")
    return "\n".join(lines).encode()


@settings(max_examples=50, deadline=5000)
@given(markdown_doc())
def test_markdown_round_trip(data: bytes) -> None:
    """serialize(parse(x)) == x for any generated markdown document."""
    if not data.strip():
        return
    tree = parse(data)
    out = serialize(tree)
    assert out == data, f"Round-trip mismatch.\nInput:  {data!r}\nOutput: {out!r}"


@settings(max_examples=20, deadline=5000)
@given(markdown_doc())
def test_node_ids_stable(data: bytes) -> None:
    """Same content produces the same node IDs on re-parse."""
    if not data.strip():
        return
    tree1 = parse(data)
    tree2 = parse(data)
    ids1 = sorted(n.id for n in tree1.walk())
    ids2 = sorted(n.id for n in tree2.walk())
    assert ids1 == ids2


@settings(max_examples=20, deadline=5000)
@given(markdown_doc())
def test_fingerprints_filled(data: bytes) -> None:
    """Every node has a non-empty fingerprint."""
    if not data.strip():
        return
    tree = parse(data)
    for node in tree.walk():
        assert node.fingerprint != ""
