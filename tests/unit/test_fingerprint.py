"""Unit tests for core/fingerprint.py."""

from docpatch.core.fingerprint import compute_fingerprint


def test_same_content_same_fingerprint() -> None:
    fp1 = compute_fingerprint("hello", [])
    fp2 = compute_fingerprint("hello", [])
    assert fp1 == fp2


def test_different_content_different_fingerprint() -> None:
    fp1 = compute_fingerprint("hello", [])
    fp2 = compute_fingerprint("world", [])
    assert fp1 != fp2


def test_child_change_propagates() -> None:
    child_fp_a = compute_fingerprint("child_a", [])
    child_fp_b = compute_fingerprint("child_b", [])
    parent_a = compute_fingerprint("parent", [child_fp_a])
    parent_b = compute_fingerprint("parent", [child_fp_b])
    assert parent_a != parent_b


def test_no_content_no_children() -> None:
    fp = compute_fingerprint(None, [])
    assert isinstance(fp, str)
    assert len(fp) == 64  # BLAKE3 hex digest


def test_order_matters() -> None:
    fp1 = compute_fingerprint(None, ["a", "b"])
    fp2 = compute_fingerprint(None, ["b", "a"])
    assert fp1 != fp2
