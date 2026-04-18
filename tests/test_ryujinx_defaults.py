"""Defaults for Ryujinx path and shop-thumbnail rules (no GUI)."""

from __future__ import annotations

from pathlib import Path

from app import (
    _is_expected_ryujinx_slot_root,
    thumb_needed_for_mode,
)


def test_thumb_needed_facepaint_off_else_on():
    assert thumb_needed_for_mode("facepaint") is False
    assert thumb_needed_for_mode("Facepaint") is False
    assert thumb_needed_for_mode(" goods ") is True
    assert thumb_needed_for_mode("food") is True


def test_expected_ryujinx_path_tail(tmp_path: Path):
    good = tmp_path / "Ryujinx" / "bis" / "user" / "save" / "0000000000000001"
    good.mkdir(parents=True)
    assert _is_expected_ryujinx_slot_root(good) is True

    wrong_name = tmp_path / "Ryujinx" / "bis" / "user" / "save" / "0000000000000002"
    wrong_name.mkdir(parents=True)
    assert _is_expected_ryujinx_slot_root(wrong_name) is False

    only_id = tmp_path / "0000000000000001"
    only_id.mkdir()
    assert _is_expected_ryujinx_slot_root(only_id) is False
