# Tomodachi Texture Tool (extended)

Turn a **PNG** into the custom texture files the game expects for **Tomodachi Life: Living the Dream** — with a simple window, no command line.

This project is an **extended fork** of [farbensplasch/tomodachi-texture-tool](https://github.com/farbensplasch/tomodachi-texture-tool). It keeps everything that worked upstream and adds quality-of-life features for people who mod on PC (especially Ryujinx).

---

## Why use this fork

- **Shop thumbnails that work** — listing icons (`*_Thumb.ugctex.zs`) are generated so they match what the game expects, without relying on in-game “resave” tricks.
- **Browse your save** — see what you already made, preview textures, export PNGs, and jump straight to **Import** with the same slot.
- **Multiple profiles** — if your save has `0\Ugc`, `1\Ugc`, … pick the right one or sync an export to every profile at once.
- **Less path hunting** — when a typical Ryujinx save layout is present, the tool can fill in your **Ugc** folder for you.
- **Same game, more comfort** — drag-and-drop PNG, ZSTD output, highest-ID hints, and the same cross-platform scope as upstream.

---

## Download

Installers for **Windows**, **macOS**, and **Linux** are attached to **[Releases](../../releases)** on this repository.

The original app’s builds are on [upstream Releases](https://github.com/farbensplasch/tomodachi-texture-tool/releases).

**Windows note:** Some antivirus tools flag PyInstaller `.exe` files incorrectly. If that happens, run the app from source (below) or add an exception after you trust the build.

---

## Quick start

1. **Back up your save** before changing files.
2. **Close the game / emulator** while copying textures into the save folder (or you can get stale icons or locked files).
3. Open the app, choose your **PNG**, pick **item type** and **ID**, set your **Ugc** folder (or use the suggested path), then **Convert & Export**.
4. For shop items (everything except Facepaint), the tool also writes the **thumbnail** file next to the canvas and ugctex.

Step-by-step with pictures: **[docs/GUIDE.md](docs/GUIDE.md)**.

### If a shop icon looks wrong

Try **fully quitting** the emulator, confirm you copied into the **same profile** folder the game uses (`…\0\Ugc`, `…\1\Ugc`, …), and use **Sync to all profiles** if you play multiple slots.  
If an icon still won’t refresh, open the item once in the **in-game editor** and **save** — that forces the game to refresh its own copies of listing data.

---

## Run from source

- **Python 3.11+**
- Install dependencies and launch:

```sh
pip install -r requirements.txt
python main.py
```

Optional tests:

```sh
pip install pytest
python -m pytest tests/
```

### Build a standalone app

Use PyInstaller **on the same kind of computer** you want to ship for (Windows / Mac / Linux don’t cross-build in one step). See **`build.bat`** (Windows) and **`build.sh`** (macOS / Linux) in this repo.

---

## Credits

- **[farbensplasch](https://github.com/farbensplasch)** — original **Tomodachi Texture Tool**
- Nintendo Switch–style swizzle for canvas / ugctex — [Aclios/pyswizzle](https://github.com/Aclios/pyswizzle) (MIT)
- Format notes — community research (e.g. TomoKore / related tools)

This tool is **not** affiliated with or endorsed by Nintendo. MIT License — see [LICENSE](LICENSE).
