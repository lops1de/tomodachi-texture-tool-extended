"""Round-trip checks for canvas, ugctex, and shop thumbnails."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

import converter as c


def test_canvas_roundtrip():
    img = Image.new("RGBA", (32, 32), (10, 20, 30, 255))
    raw = c.png_to_canvas(img, False, 2)
    z = c.zstd_compress(raw)
    out = c.zs_bytes_to_png_canvas(c.zstd_decompress(z))
    assert out.size == c.CANVAS_SIZE


def test_ugctex_roundtrip():
    img = Image.new("RGBA", (64, 64), (200, 100, 50, 255))
    raw = c.png_to_ugctex(img, False, 2)
    z = c.zstd_compress(raw)
    out = c.zs_bytes_to_png_ugctex(c.zstd_decompress(z))
    assert out.size == c.UGCTEX_SIZE


def test_thumb_roundtrip_and_size():
    img = Image.new("RGBA", (64, 64), (1, 2, 3, 255))
    raw = c.png_to_thumb_ugctex(img, False, 2)
    assert len(raw) == c.thumb_file_expected_size()
    out = c.zs_bytes_to_png_thumb(raw)
    assert out.size == c.THUMB_CODEC_SIZE


def test_thumb_matches_canvas_shop_preview_pipeline():
    """On-disk thumb matches BC3/Tegra preset from decoded canvas."""
    img = Image.new("RGBA", (100, 40), (10, 20, 30, 240))
    for use_srgb in (False, True):
        cv = c.png_to_canvas(img, use_srgb, 2)
        thumb = c.thumb_payload_from_canvas_swizzled(cv)
        im256 = c.zs_bytes_to_png_canvas(cv)
        assert thumb == c._thumb_bc3_payload_from_rgba256(im256)
        assert c.zs_bytes_to_png_thumb(thumb).size == c.THUMB_CODEC_SIZE


def test_thumb_follows_ugctex_gamma_when_use_srgb_differs():
    """Thumb export follows ugctex path; γ setting (use_srgb=False) changes output bytes."""
    img = Image.new("RGBA", (64, 64), (200, 100, 50, 255))
    assert c.png_to_thumb_ugctex(img, False, 2) != c.png_to_thumb_ugctex(img, True, 2)


def test_thumb_decode_accepts_legacy_dxt1_payload():
    raw = c.png_to_ugctex(Image.new("RGBA", (64, 64), (9, 9, 9, 255)), False, 2)
    assert len(raw) == c.ugctex_file_expected_size()
    out = c.zs_bytes_to_png_thumb(raw)
    assert out.size == c.UGCTEX_SIZE


def test_convert_and_export_writes_three():
    img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        p = td / "x.png"
        img.save(p)
        cp, up, tp = c.convert_and_export(
            p, td, 7, "goods", write_thumb=True
        )
        assert cp.name == "UgcGoods007.canvas.zs"
        assert up.name == "UgcGoods007.ugctex.zs"
        assert tp and tp.name == "UgcGoods007_Thumb.ugctex.zs"
        c.zs_file_to_png(cp, "canvas")
        c.zs_file_to_png(up, "ugctex")
        c.zs_file_to_png(tp, "thumb")


def test_export_ugc_slot_pngs_includes_thumb():
    img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        p = td / "x.png"
        img.save(p)
        c.convert_and_export(p, td, 2, "goods", write_thumb=True)
        slot = c.scan_ugc_slot(td, "goods", 2)
        out = td / "png_out"
        written, errs = c.export_ugc_slot_pngs(out, slot, "goods", 2)
        assert not errs
        names = sorted(x.name for x in written)
        assert names == [
            "UgcGoods002.canvas.png",
            "UgcGoods002.ugctex.png",
            "UgcGoods002_Thumb.png",
            "UgcGoods002_Thumb_zs_decode.png",
        ]


def test_list_ugc_profiles_direct_ugc():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ugc = td / "Ugc"
        ugc.mkdir()
        profs = c.list_ugc_profiles(ugc)
        assert len(profs) == 1 and profs[0][0] == "—"


def test_list_ugc_profiles_multi():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "0" / "Ugc").mkdir(parents=True)
        (td / "1" / "Ugc").mkdir(parents=True)
        profs = c.list_ugc_profiles(td)
        assert [p[0] for p in profs] == ["0", "1"]
