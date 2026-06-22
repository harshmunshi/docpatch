"""Unit tests for core/ids.py."""

from docpatch.core.ids import _slugify, make_id


def test_slugify_basic() -> None:
    assert _slugify("Hello World") == "hello-world"


def test_slugify_unicode() -> None:
    result = _slugify("Über cool")
    assert "ber" in result


def test_slugify_empty() -> None:
    assert _slugify("") == "node"


def test_slugify_max_len() -> None:
    long_text = "a" * 100
    assert len(_slugify(long_text)) <= 40


def test_make_id_root() -> None:
    nid = make_id("document", None, None, 0)
    assert nid == "document:root"


def test_make_id_with_parent() -> None:
    nid = make_id("heading", "document:root", "Introduction", 0)
    assert nid.startswith("heading:document:root/")
    assert "introduction" in nid
    assert "#0" in nid


def test_make_id_no_text() -> None:
    nid = make_id("paragraph", "document:root", None, 2)
    assert "#2" in nid
    assert "n2" in nid


def test_make_id_deterministic() -> None:
    id1 = make_id("heading", "document:root", "Intro", 0)
    id2 = make_id("heading", "document:root", "Intro", 0)
    assert id1 == id2


def test_make_id_different_ordinals() -> None:
    id1 = make_id("paragraph", "document:root", None, 0)
    id2 = make_id("paragraph", "document:root", None, 1)
    assert id1 != id2
