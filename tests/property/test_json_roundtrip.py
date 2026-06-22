"""Property tests: serialize(parse(x)) == x for JSON."""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from docpatch.parsers.json_parser import parse, serialize

_JSON_VALUE: st.SearchStrategy[object] = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        st.text(min_size=0, max_size=20),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(min_size=1, max_size=10), children, max_size=4),
    ),
    max_leaves=20,
)


@st.composite
def json_bytes(draw: st.DrawFn) -> bytes:
    value = draw(_JSON_VALUE)
    return json.dumps(value, ensure_ascii=False).encode()


@settings(max_examples=50, deadline=5000)
@given(json_bytes())
def test_json_round_trip(data: bytes) -> None:
    """serialize(parse(x)) == x for any generated JSON."""
    tree = parse(data)
    out = serialize(tree)
    assert out == data, f"Round-trip mismatch.\nInput:  {data!r}\nOutput: {out!r}"


@settings(max_examples=20, deadline=5000)
@given(json_bytes())
def test_json_node_ids_stable(data: bytes) -> None:
    """Same JSON produces same node IDs."""
    tree1 = parse(data)
    tree2 = parse(data)
    ids1 = sorted(n.id for n in tree1.walk())
    ids2 = sorted(n.id for n in tree2.walk())
    assert ids1 == ids2
