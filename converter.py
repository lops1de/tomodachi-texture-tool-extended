from __future__ import annotations

import io
import shutil
import struct
from pathlib import Path
from typing import Callable

import zstandard as zstd
from PIL import Image, ImageOps

from swizzle import nsw_deswizzle, nsw_swizzle

SWIZZLE_MODE = 4
ZSTD_LEVEL = 16

CANVAS_SIZE = (256, 256)
UGCTEX_SIZE = (512, 512)
THUMB_SIZE = (128, 128)

# File name templates per item type.
# {id} is replaced with the zero-padded ID.
ITEM_TYPES: dict[str, dict[str, str]] = {
    "facepaint": {
        "canvas": "UgcFacePaint{id}.canvas.zs",
        "ugctex": "UgcFacePaint{id}.ugctex.zs",
        "thumb": "UgcFacePaint{id}_Thumb.ugctex.zs",
    },
    "goods": {
        "canvas": "UgcGoods{id}.canvas.zs",
        "ugctex": "UgcGoods{id}.ugctex.zs",
        "thumb": "UgcGoods{id}_Thumb.ugctex.zs",
    },
    "clothes": {
        "canvas": "UgcCloth{id}.canvas.zs",
        "ugctex": "UgcCloth{id}.ugctex.zs",
        "thumb": "UgcCloth{id}_Thumb.ugctex.zs",
    },
    "exterior": {
        "canvas": "UgcExterior{id}.canvas.zs",
        "ugctex": "UgcExterior{id}.ugctex.zs",
        "thumb": "UgcExterior{id}_Thumb.ugctex.zs",
    },
    "interior": {
        "canvas": "UgcInterior{id}.canvas.zs",
        "ugctex": "UgcInterior{id}.ugctex.zs",
        "thumb": "UgcInterior{id}_Thumb.ugctex.zs",
    },
    "mapobject": {
        "canvas": "UgcMapObject{id}.canvas.zs",
        "ugctex": "UgcMapObject{id}.ugctex.zs",
        "thumb": "UgcMapObject{id}_Thumb.ugctex.zs",
    },
    "mapfloor": {
        "canvas": "UgcMapFloor{id}.canvas.zs",
        "ugctex": "UgcMapFloor{id}.ugctex.zs",
        "thumb": "UgcMapFloor{id}_Thumb.ugctex.zs",
    },
    "food": {
        "canvas": "UgcFood{id}.canvas.zs",
        "ugctex": "UgcFood{id}.ugctex.zs",
        "thumb": "UgcFood{id}_Thumb.ugctex.zs",
    },
}


def _gamma(img: Image.Image, gamma: float) -> Image.Image:
    return img.point(lambda x: ((x / 255) ** gamma) * 255)


def png_to_rgba_swizzled(
    img: Image.Image,
    size: tuple[int, int],
    use_srgb: bool,
    resize_mode: int,
) -> bytes:
    """RGBA Nintendo swizzled blob (same layout as CANVAS, arbitrary square size supported by swizzle)."""
    w, h = size
    img = img.convert("RGBA")
    if img.size != (w, h):
        if resize_mode == 1:
            img = img.resize((w, h), Image.LANCZOS)
        else:
            img = ImageOps.fit(img, (w, h), Image.LANCZOS)

    if not use_srgb:
        img = _gamma(img, 2.2)

    img = img.convert("RGBA")
    raw = img.tobytes("raw")
    return bytes(nsw_swizzle(raw, (w, h), (1, 1), 4, SWIZZLE_MODE))


def png_to_canvas(img: Image.Image, use_srgb: bool, resize_mode: int) -> bytes:
    """Convert a PIL image to a raw swizzled CANVAS blob (256x256 RGBA)."""
    return png_to_rgba_swizzled(img, CANVAS_SIZE, use_srgb, resize_mode)


def png_to_thumb_ugctex(img: Image.Image, use_srgb: bool, resize_mode: int) -> bytes:
    """Shop thumbnail: 128x128 RGBA swizzled → *_Thumb.ugctex.zs (same layout as canvas)."""
    return png_to_rgba_swizzled(img, THUMB_SIZE, use_srgb, resize_mode)


def png_to_ugctex(img: Image.Image, use_srgb: bool, resize_mode: int) -> bytes:
    """Convert a PIL image to a raw swizzled UGCTEX blob (512x512 DXT1)."""
    img = img.convert("RGBA")
    if img.size != UGCTEX_SIZE:
        if resize_mode == 1:
            img = img.resize(UGCTEX_SIZE, Image.LANCZOS)
        else:
            img = ImageOps.fit(img, UGCTEX_SIZE, Image.LANCZOS)

    if not use_srgb:
        img = _gamma(img, 2.2)

    buf = io.BytesIO()
    img.save(buf, format="DDS", pixel_format="DXT1")
    dxt1_data = buf.getvalue()[128:]  # strip 128-byte DDS header

    return bytes(nsw_swizzle(dxt1_data, UGCTEX_SIZE, (4, 4), 8, SWIZZLE_MODE))


def get_highest_id(folder: Path, mode: str) -> int | None:
    """Return the highest numeric ID found in folder for the given mode, or None."""
    template = ITEM_TYPES[mode]["ugctex"]
    if "{id}" not in template:
        return None
    prefix, suffix = template.split("{id}")
    max_id = None
    for f in folder.glob(f"{prefix}*{suffix}"):
        id_part = f.name[len(prefix) : len(f.name) - len(suffix)]
        if id_part.isdigit():
            n = int(id_part)
            if max_id is None or n > max_id:
                max_id = n
    return max_id


def zstd_compress(data: bytes) -> bytes:
    return zstd.ZstdCompressor(level=ZSTD_LEVEL).compress(data)


def zstd_decompress(data: bytes) -> bytes:
    return zstd.ZstdDecompressor().decompress(data)


def zstd_decompress_file(path: Path) -> bytes:
    return zstd_decompress(path.read_bytes())


def _dxt1_dds_file(width: int, height: int, dxt1_payload: bytes) -> bytes:
    """Minimal DDS container so Pillow can decode DXT1 payload."""
    pitch = max(1, (width + 3) // 4) * 8
    header = bytearray(128)
    struct.pack_into("<4s", header, 0, b"DDS ")
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x1007)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, pitch)
    struct.pack_into("<I", header, 24, 1)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 4)
    struct.pack_into("<4s", header, 84, b"DXT1")
    struct.pack_into("<I", header, 104, 0x1000)
    return bytes(header) + dxt1_payload


def zs_bytes_to_png_canvas(data: bytes) -> Image.Image:
    raw = nsw_deswizzle(data, CANVAS_SIZE, (1, 1), 4, SWIZZLE_MODE)
    return Image.frombytes("RGBA", CANVAS_SIZE, raw, "raw")


def zs_bytes_to_png_ugctex(data: bytes) -> Image.Image:
    raw = nsw_deswizzle(data, UGCTEX_SIZE, (4, 4), 8, SWIZZLE_MODE)
    buf = _dxt1_dds_file(UGCTEX_SIZE[0], UGCTEX_SIZE[1], raw)
    im = Image.open(io.BytesIO(buf))
    return im.convert("RGBA")


def zs_bytes_to_png_thumb(data: bytes) -> Image.Image:
    """128x128 RGBA thumbnail (shop icon)."""
    raw = nsw_deswizzle(data, THUMB_SIZE, (1, 1), 4, SWIZZLE_MODE)
    return Image.frombytes("RGBA", THUMB_SIZE, raw, "raw")


def zs_file_to_png(path: Path, kind: str) -> Image.Image:
    """
    kind: 'canvas' | 'ugctex' (512 DXT1) | 'thumb' (128 RGBA shop icon).
    """
    data = zstd_decompress_file(path)
    if kind == "canvas":
        return zs_bytes_to_png_canvas(data)
    if kind == "ugctex":
        return zs_bytes_to_png_ugctex(data)
    if kind == "thumb":
        return zs_bytes_to_png_thumb(data)
    raise ValueError(f"Unknown kind: {kind}")


def thumb_file_expected_size() -> int:
    """Decompressed RGBA swizzled thumb size (for validation)."""
    w, h = THUMB_SIZE
    return w * h * 4


def list_ugc_profiles(save_path: Path) -> list[tuple[str, Path]]:
    """
    Discover profile folders that contain a Ugc directory.
    Returns [(label, ugc_folder), ...]. Label '—' for a single Ugc path.
    """
    path = save_path.resolve()
    if not path.is_dir():
        return []

    if path.name.lower() == "ugc":
        return [("—", path)]

    digit_ugc: list[tuple[str, Path]] = []
    try:
        for sub in path.iterdir():
            if sub.is_dir() and sub.name.isdigit() and (sub / "Ugc").is_dir():
                digit_ugc.append((sub.name, sub / "Ugc"))
    except OSError:
        return []

    if digit_ugc:
        digit_ugc.sort(key=lambda t: int(t[0]))
        return digit_ugc

    if (path / "Ugc").is_dir():
        return [("—", path / "Ugc")]

    if any(path.glob("*.zs")):
        return [("—", path)]

    return []


def scan_ugc_slot(
    ugc_folder: Path,
    mode: str,
    item_id: int,
) -> dict:
    """Return which files exist for one ID."""
    t = ITEM_TYPES[mode]
    id_str = str(item_id).zfill(3)
    canvas = ugc_folder / t["canvas"].format(id=id_str)
    ugctex = ugc_folder / t["ugctex"].format(id=id_str)
    thumb = ugc_folder / t["thumb"].format(id=id_str)
    return {
        "id": item_id,
        "canvas": canvas if canvas.is_file() else None,
        "ugctex": ugctex if ugctex.is_file() else None,
        "thumb": thumb if thumb.is_file() else None,
    }


def list_ugc_ids_for_mode(ugc_folder: Path, mode: str) -> list[int]:
    """IDs that have at least one of canvas / ugctex / thumb for this mode."""
    t = ITEM_TYPES[mode]
    prefix_ugctex, suffix_ugctex = t["ugctex"].split("{id}")
    ids: set[int] = set()
    for f in ugc_folder.glob(f"{prefix_ugctex}*{suffix_ugctex}"):
        rest = f.name[len(prefix_ugctex) : -len(suffix_ugctex)]
        if rest.isdigit():
            ids.add(int(rest))
    prefix_c, suffix_c = t["canvas"].split("{id}")
    for f in ugc_folder.glob(f"{prefix_c}*{suffix_c}"):
        rest = f.name[len(prefix_c) : -len(suffix_c)]
        if rest.isdigit():
            ids.add(int(rest))
    prefix_th, suffix_th = t["thumb"].split("{id}")
    for f in ugc_folder.glob(f"{prefix_th}*{suffix_th}"):
        rest = f.name[len(prefix_th) : -len(suffix_th)]
        if rest.isdigit():
            ids.add(int(rest))
    return sorted(ids)


def convert_and_export(
    png_path: Path,
    output_dir: Path,
    item_id: int,
    mode: str,
    use_srgb: bool = False,
    resize_mode: int = 1,
    on_progress: Callable[[str, float], None] | None = None,
    write_thumb: bool = True,
) -> tuple[Path, Path, Path | None]:
    """
    PNG → CANVAS + UGCTEX [+ optional THUMB] → ZSTD → output_dir.

    Returns (canvas_path, ugctex_path, thumb_path_or_none).
    """
    templates = ITEM_TYPES[mode]
    id_str = str(item_id).zfill(3)

    def progress(msg: str, pct: float) -> None:
        if on_progress:
            on_progress(msg, pct)

    progress("Loading image…", 0.05)
    img = Image.open(png_path)

    progress("Converting to CANVAS…", 0.15)
    canvas_data = png_to_canvas(img.copy(), use_srgb, resize_mode)

    progress("Converting to UGCTEX…", 0.35)
    ugctex_data = png_to_ugctex(img.copy(), use_srgb, resize_mode)

    thumb_path: Path | None = None
    thumb_data: bytes | None = None
    if write_thumb:
        progress("Converting shop thumbnail…", 0.55)
        thumb_data = png_to_thumb_ugctex(img.copy(), use_srgb, resize_mode)

    progress("Compressing (ZSTD)…", 0.75)
    canvas_zs = zstd_compress(canvas_data)
    ugctex_zs = zstd_compress(ugctex_data)
    thumb_zs = zstd_compress(thumb_data) if thumb_data is not None else None

    progress("Writing files…", 0.9)
    output_dir.mkdir(parents=True, exist_ok=True)

    canvas_path = output_dir / templates["canvas"].format(id=id_str)
    ugctex_path = output_dir / templates["ugctex"].format(id=id_str)

    canvas_path.write_bytes(canvas_zs)
    ugctex_path.write_bytes(ugctex_zs)

    if thumb_zs is not None:
        thumb_path = output_dir / templates["thumb"].format(id=id_str)
        thumb_path.write_bytes(thumb_zs)

    progress("Done!", 1.0)
    return canvas_path, ugctex_path, thumb_path


def copy_zs_to_folders(
    files: list[Path],
    target_dirs: list[Path],
) -> None:
    """Copy exported .zs files to additional profile Ugc folders."""
    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, d / f.name)
