"""Round-trip and layout checks (validates thumb = 128x128 RGBA swizzled)."""

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
    raw = c.png_to_ugctext_thumb(img, False, 2)
    assert len(raw) == c.thumb_file_expected_size()
    out = c.zs_bytes_to_png_thumb(raw)
    assert out.size == c.THUMB_SIZE


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
        assert tp and tp.name == "UgcGoods007_Thumb.ugctext.zs"
        c.zs_file_to_png(cp, "canvas")
        c.zs_file_to_png(up, "ugctex")
        c.zs_file_to_png(tp, "ugctext")


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
