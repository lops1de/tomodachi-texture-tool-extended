# Tomodachi Texture Tool (extended fork)

A GUI tool for converting PNG images into **Tomodachi Life: Living the Dream** custom UGC texture files (`.canvas.zs`, `.ugctex.zs`, and shop thumbnails where needed) — no command line required.

## About this fork

This repository is a **fork** of **[farbensplasch/tomodachi-texture-tool](https://github.com/farbensplasch/tomodachi-texture-tool)**. It adds features such as browse/export, Ryujinx save-path defaults, shop-thumbnail handling by item type, and multi-profile sync. Development here is **vibe-coded** (AI-assisted iteration) and kept **separate from upstream** so experimental or opinionated changes are not pushed into the original project without the maintainer’s review.

If improvements stabilize and the upstream author wants them, they can be offered as focused pull requests. Until then, treat **this repo as the fork** and **upstream as the canonical base**.

**License respect:** This project stays under the **MIT License** (see [LICENSE](LICENSE)). Keep the MIT text and copyright notices in distributions. The upstream app remains **Copyright (c) farbensplasch**; note your own copyright for fork-specific changes if you redistribute builds. Third-party credits in [Credits](#credits) (e.g. pyswizzle, TomoKore research) must remain intact. This is an independent tool — it is **not** affiliated with or endorsed by Nintendo.

---

## Features

- Convert PNG → `.canvas.zs` + `.ugctex.zs`, and **`_Thumb.ugctex.zs`** for shop-listed types (automatically **off** for Facepaint, **on** for other item types)
- Item types: Facepaint, Goods, Clothes, Exterior, Interior, MapObject, MapFloor, Food
- **Browse / Export** tab: list UGC in your save, preview, export PNGs, **Use for import** to jump to Import with the same slot
- **Profile** selector (`…/0/Ugc`, `1/Ugc`, …) and **Sync exports to all profiles**
- **Default save path** when `%APPDATA%\Ryujinx\bis\user\save\0000000000000001` (or the Linux/macOS equivalents) exists and matches the expected Ryujinx layout
- ZSTD compression, highest-ID hint, drag-and-drop PNG
- Windows, macOS, and Linux (same scope as [upstream releases](https://github.com/farbensplasch/tomodachi-texture-tool/releases))

---

## Download

Use **[Releases](../../releases)** on **this fork** for binaries built from this branch. For the **original** v1.0.x builds, see [upstream releases](https://github.com/farbensplasch/tomodachi-texture-tool/releases).

> **Windows antivirus:** PyInstaller `.exe` files are often flagged as generic malware (**false positive**). Prefer building from source if you need to verify the binary.

| Platform | Typical artifact |
|----------|------------------|
| Windows  | `TomodachiTextureTool.exe` (from PyInstaller; you may rename, e.g. `TomodachiTextureTool-Windows.exe`) |
| macOS    | `TomodachiTextureTool.app` (from the `.spec` bundle step) |
| Linux    | `TomodachiTextureTool` one-file binary |

```sh
chmod +x TomodachiTextureTool
```

On macOS, if Gatekeeper blocks the app: **System Settings → Privacy & Security** → allow, or right-click → **Open** the first time.

---

## How to use

See **[docs/GUIDE.md](docs/GUIDE.md)** for a longer walkthrough.

**Safety:** Back up your save. Close Ryujinx (or lock-producing tools) while writing files.

**Import:** Choose PNG, item type and ID, set **Save / Ugc** (auto-filled when the default Ryujinx path exists), pick **Profile** if needed, then **Convert & Export**.

**Browse / Export:** Refresh the list, **Export PNGs** or **Use for import** to align Import with a row.

---

## File naming (reference)

| Item type | Canvas | UgcTex | Shop thumbnail (non-facepaint) |
|-----------|--------|--------|--------------------------------|
| Facepaint | `UgcFacePaintXXX…` | `…` | (not written) |
| Others | `…canvas.zs` | `…ugctex.zs` | `…_Thumb.ugctex.zs` |

`XXX` = zero-padded ID (e.g. `002`).

---

## Building from source

**Requirements:** Python 3.11+, dependencies in `requirements.txt`.

```sh
git clone <your-fork-url>
cd tomodachi-texture-tool
pip install -r requirements.txt
python main.py
```

```sh
pip install pytest
pytest tests/
```

### Standalone executables (PyInstaller)

Same **three platforms** as upstream: build **on each OS** you want to ship (PyInstaller does not cross-compile Windows ↔ macOS ↔ Linux from one machine).

```sh
pip install pyinstaller
```

**Windows**

```bat
build.bat
```

Output: `dist\TomodachiTextureTool.exe`

**macOS / Linux**

```sh
bash build.sh
```

- **Linux:** `dist/TomodachiTextureTool` (single executable).
- **macOS:** `dist/TomodachiTextureTool.app` (bundle); the one-file `TomodachiTextureTool` executable is also produced — distribute the `.app` for a standard macOS experience.

Zip or archive artifacts per platform for GitHub Releases. Naming can mirror upstream (e.g. `TomodachiTextureTool-Windows.exe`, `TomodachiTextureTool-macOS.zip`, `TomodachiTextureTool-Linux`) for consistency.

---

## Credits

- **[farbensplasch](https://github.com/farbensplasch)** — original **Tomodachi Texture Tool**
- Nintendo Switch texture swizzle — [Aclios/pyswizzle](https://github.com/Aclios/pyswizzle) (MIT)
- Format research — [Timimimi](https://github.com/Timiimiimii/TomoKoreFacepaintTool) / RealDarkCraft
