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
# Shop *_Thumb.ugctex.zs breakthrough:
# payload is 65,536 bytes that matches 256x256 BC3/DXT5 blocks (16 bytes per 4x4 block),
# arranged in Tegra block-linear order at the block level.
THUMB_SIZE = (128, 128)  # preview/UI size
THUMB_CODEC_SIZE = (256, 256)  # on-disk thumb texture dimensions
THUMB_BLOCK = (4, 4)
THUMB_BLOCK_BYTES = 16
THUMB_TEGRA_BLOCK_HEIGHT = 8


def _thumb_inverse_perm(order: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    inv = [0, 0, 0, 0]
    for out_idx, src_idx in enumerate(order):
        inv[src_idx] = out_idx
    return tuple(inv)  # type: ignore[return-value]


def _decode_legacy_thumb_128_tile8(disk: bytes) -> bytes:
    """
    Decode older experimental thumbs: 128×128, 8×8 tiles, row-major inside tile,
    X-major tile order, ABGR channel packing on disk.
    """
    w, h = THUMB_SIZE
    t = 8
    order = (3, 2, 1, 0)  # ABGR
    inv = _thumb_inverse_perm(order)
    n = w * h * 4
    if len(disk) != n:
        raise ValueError(f"Expected {n} bytes on disk, got {len(disk)}")
    out = bytearray(n)
    tile_bytes = t * t * 4
    tile_ord = 0
    for tx in range(w // t):
        for ty in range(h // t):
            base = tile_ord * tile_bytes
            for y in range(t):
                for x in range(t):
                    px, py = tx * t + x, ty * t + y
                    di = (py * w + px) * 4
                    idx = y * t + x
                    ii = base + idx * 4
                    p = disk[ii : ii + 4]
                    out[di : di + 4] = bytes((p[inv[0]], p[inv[1]], p[inv[2]], p[inv[3]]))
            tile_ord += 1
    return bytes(out)


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


def _dxt5_dds_file(width: int, height: int, dxt5_payload: bytes) -> bytes:
    """Minimal DDS container so Pillow can decode DXT5 payload."""
    pitch = max(1, (width + 3) // 4) * 16
    header = bytearray(128)
    struct.pack_into("<4s", header, 0, b"DDS ")
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x81007)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, pitch)
    struct.pack_into("<I", header, 24, 1)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 4)
    struct.pack_into("<4s", header, 84, b"DXT5")
    struct.pack_into("<I", header, 104, 0x1000)
    return bytes(header) + dxt5_payload


def _div_round_up(n: int, d: int) -> int:
    return (n + d - 1) // d


def _tegra_get_addr_block_linear(
    x: int,
    y: int,
    image_width: int,
    bytes_per_element: int,
    base_address: int,
    block_height: int,
) -> int:
    image_width_in_gobs = _div_round_up(image_width * bytes_per_element, 64)
    gob_address = (
        base_address
        + (y // (8 * block_height)) * 512 * block_height * image_width_in_gobs
        + (x * bytes_per_element // 64) * 512 * block_height
        + (y % (8 * block_height) // 8) * 512
    )
    xb = x * bytes_per_element
    return (
        gob_address
        + ((xb % 64) // 32) * 256
        + ((y % 8) // 2) * 64
        + ((xb % 32) // 16) * 32
        + (y % 2) * 16
        + (xb % 16)
    )


def _tegra_deswizzle_elements(
    tiled: bytes,
    width_elems: int,
    height_elems: int,
    bytes_per_element: int,
    block_height: int,
) -> bytes:
    out = bytearray(width_elems * height_elems * bytes_per_element)
    n = len(tiled)
    for y in range(height_elems):
        for x in range(width_elems):
            src = _tegra_get_addr_block_linear(
                x, y, width_elems, bytes_per_element, 0, block_height
            )
            dst = (y * width_elems + x) * bytes_per_element
            if src + bytes_per_element <= n:
                out[dst : dst + bytes_per_element] = tiled[src : src + bytes_per_element]
            else:
                out[dst : dst + bytes_per_element] = b"\x00" * bytes_per_element
    return bytes(out)


def _tegra_swizzle_elements(
    linear: bytes,
    width_elems: int,
    height_elems: int,
    bytes_per_element: int,
    block_height: int,
) -> bytes:
    out = bytearray(width_elems * height_elems * bytes_per_element)
    n = len(out)
    for y in range(height_elems):
        for x in range(width_elems):
            src = (y * width_elems + x) * bytes_per_element
            dst = _tegra_get_addr_block_linear(
                x, y, width_elems, bytes_per_element, 0, block_height
            )
            if dst + bytes_per_element <= n:
                out[dst : dst + bytes_per_element] = linear[src : src + bytes_per_element]
    return bytes(out)


def _thumb_bc3_payload_from_rgba256(im256: Image.Image) -> bytes:
    """
    Encode RGBA 256x256 -> DXT5/BC3 blocks -> Tegra block-linear (BH8) block order.
    """
    im = im256.convert("RGBA")
    if im.size != THUMB_CODEC_SIZE:
        im = im.resize(THUMB_CODEC_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="DDS", pixel_format="DXT5")
    dxt5_linear = buf.getvalue()[128:]
    w, h = THUMB_CODEC_SIZE
    bw, bh = THUMB_BLOCK
    wb, hb = w // bw, h // bh
    return _tegra_swizzle_elements(
        dxt5_linear,
        wb,
        hb,
        THUMB_BLOCK_BYTES,
        THUMB_TEGRA_BLOCK_HEIGHT,
    )


def _thumb_bc3_payload_to_rgba256(data: bytes) -> Image.Image:
    w, h = THUMB_CODEC_SIZE
    bw, bh = THUMB_BLOCK
    wb, hb = w // bw, h // bh
    dxt5_linear = _tegra_deswizzle_elements(
        data,
        wb,
        hb,
        THUMB_BLOCK_BYTES,
        THUMB_TEGRA_BLOCK_HEIGHT,
    )
    dds = _dxt5_dds_file(w, h, dxt5_linear)
    return Image.open(io.BytesIO(dds)).convert("RGBA")


def _looks_like_bc3_thumb(data: bytes) -> bool:
    """
    Heuristic for 65,536-byte thumb payload ambiguity:
    BC3 blocks usually have relatively low per-lane cardinality in byte lanes 12..15
    (2-bit color index field), unlike raw RGBA payloads.
    """
    if len(data) != 65536:
        return False
    lane_vals = [set() for _ in range(4)]  # lanes 12..15
    mv = memoryview(data)
    for i in range(0, len(data), 16):
        lane_vals[0].add(mv[i + 12])
        lane_vals[1].add(mv[i + 13])
        lane_vals[2].add(mv[i + 14])
        lane_vals[3].add(mv[i + 15])
        if any(len(s) > 192 for s in lane_vals):
            return False
    return True


def zs_bytes_to_png_canvas(data: bytes) -> Image.Image:
    raw = nsw_deswizzle(data, CANVAS_SIZE, (1, 1), 4, SWIZZLE_MODE)
    return Image.frombytes("RGBA", CANVAS_SIZE, raw, "raw")


def zs_bytes_to_png_ugctex(data: bytes) -> Image.Image:
    raw = nsw_deswizzle(data, UGCTEX_SIZE, (4, 4), 8, SWIZZLE_MODE)
    buf = _dxt1_dds_file(UGCTEX_SIZE[0], UGCTEX_SIZE[1], raw)
    im = Image.open(io.BytesIO(buf))
    return im.convert("RGBA")


def thumb_payload_from_canvas_swizzled(canvas_swizzled: bytes) -> bytes:
    """
    Shop listing thumbnail bytes (65536), encoded as BC3/DXT5 in Tegra block-linear order.
    """
    im256 = zs_bytes_to_png_canvas(canvas_swizzled)
    return _thumb_bc3_payload_from_rgba256(im256)


def thumb_payload_from_ugctex_swizzled(ugctex_swizzled: bytes) -> bytes:
    """
    Alternate thumb source: decode ``ugctex`` -> 512² RGBA -> 256² LANCZOS -> BC3/Tegra.
    """
    im512 = zs_bytes_to_png_ugctex(ugctex_swizzled)
    im256 = im512.resize(THUMB_CODEC_SIZE, Image.LANCZOS)
    return _thumb_bc3_payload_from_rgba256(im256)


def png_to_thumb_ugctex(img: Image.Image, use_srgb: bool, resize_mode: int) -> bytes:
    """Encode a shop thumb from ``img`` via the ugctex->BC3/Tegra pipeline."""
    return thumb_payload_from_ugctex_swizzled(png_to_ugctex(img, use_srgb, resize_mode))


def zs_bytes_to_png_thumb(data: bytes) -> Image.Image:
    """Decode *_Thumb.ugctex.zs (BC3/Tegra BH8; legacy raw-128 and legacy DXT1 fallback)."""
    n = len(data)
    if n == THUMB_SIZE[0] * THUMB_SIZE[1] * 4:
        # Preferred: BC3/DXT5 blocks in Tegra block-linear order.
        if _looks_like_bc3_thumb(data):
            try:
                return _thumb_bc3_payload_to_rgba256(data)
            except Exception:
                pass
        # Legacy experimental raw 128×128 tile8 path.
        raw = _decode_legacy_thumb_128_tile8(data)
        return Image.frombytes("RGBA", THUMB_SIZE, raw, "raw")
    if n == ugctex_file_expected_size():
        return zs_bytes_to_png_ugctex(data)
    raise ValueError(
        f"Unknown thumb payload size: {n} (expected "
        f"{THUMB_SIZE[0] * THUMB_SIZE[1] * 4} or {ugctex_file_expected_size()})"
    )


def zs_file_to_png(path: Path, kind: str) -> Image.Image:
    """
    kind: 'canvas' | 'ugctex' (512 DXT1) | 'thumb' (shop thumb or legacy ugctex-sized).
    """
    data = zstd_decompress_file(path)
    if kind == "canvas":
        return zs_bytes_to_png_canvas(data)
    if kind == "ugctex":
        return zs_bytes_to_png_ugctex(data)
    if kind == "thumb":
        return zs_bytes_to_png_thumb(data)
    raise ValueError(f"Unknown kind: {kind}")


def thumb_shop_preview_png(slot: dict) -> Image.Image | None:
    """128×128 preview: LANCZOS of decoded ``canvas`` if present, else ``ugctex`` (matches written thumb)."""
    if slot.get("canvas"):
        im = zs_file_to_png(slot["canvas"], "canvas")
        return im.resize((128, 128), Image.LANCZOS)
    if slot.get("ugctex"):
        im = zs_file_to_png(slot["ugctex"], "ugctex")
        return im.resize((128, 128), Image.LANCZOS)
    return None


def export_ugc_slot_pngs(
    out_dir: Path,
    slot: dict,
    mode: str,
    item_id: int,
) -> tuple[list[Path], list[str]]:
    """
    Decode existing .zs files in ``slot`` to PNGs under ``out_dir``.
    Each asset is written independently; one failure does not skip the others.

    Writes (when the corresponding file exists):
    ``{stem}.canvas.png``, ``{stem}.ugctex.png``,
    and for shop thumbnails ``{stem}_Thumb.png`` plus ``{stem}_Thumb_zs_decode.png``
    when a ``*_Thumb.ugctex.zs`` file exists.

    Returns (paths written, error messages).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t = ITEM_TYPES[mode]
    id_str = str(item_id).zfill(3)
    stem = t["ugctex"].format(id=id_str).replace(".ugctex.zs", "")

    jobs: list[tuple[str, Path | None, str, str]] = [
        ("canvas", slot.get("canvas"), "canvas", f"{stem}.canvas.png"),
        ("ugctex", slot.get("ugctex"), "ugctex", f"{stem}.ugctex.png"),
    ]

    written: list[Path] = []
    errors: list[str] = []
    for label, zs_path, kind, filename in jobs:
        if not zs_path:
            continue
        dest = out_dir / filename
        try:
            im = zs_file_to_png(zs_path, kind)
            im.save(dest)
            written.append(dest)
        except Exception as e:
            errors.append(f"{label} → {filename}: {e}")

    if slot.get("thumb"):
        preview = thumb_shop_preview_png(slot)
        if preview is not None:
            dest = out_dir / f"{stem}_Thumb.png"
            try:
                preview.save(dest)
                written.append(dest)
            except Exception as e:
                errors.append(f"thumb preview → {dest.name}: {e}")
            try:
                raw = zs_file_to_png(slot["thumb"], "thumb")
                dest_raw = out_dir / f"{stem}_Thumb_zs_decode.png"
                raw.save(dest_raw)
                written.append(dest_raw)
            except Exception as e:
                errors.append(f"thumb zs decode → {dest_raw.name}: {e}")
        else:
            dest = out_dir / f"{stem}_Thumb.png"
            try:
                im = zs_file_to_png(slot["thumb"], "thumb")
                im.save(dest)
                written.append(dest)
            except Exception as e:
                errors.append(f"thumb → {dest.name}: {e}")

    return written, errors


def ugctex_file_expected_size() -> int:
    """Decompressed DXT1 swizzled payload size for 512×512 ugctex."""
    w, h = UGCTEX_SIZE
    return (w * h // 16) * 8


def thumb_file_expected_size() -> int:
    """Decompressed shop thumb payload size (currently BC3 blocks for 256×256)."""
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
        thumb_data = thumb_payload_from_ugctex_swizzled(ugctex_data)

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
