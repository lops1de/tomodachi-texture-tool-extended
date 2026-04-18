import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

# Paths relative to this .spec file (PyInstaller sets SPEC).
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# Optional icons: add files to /assets — see README "Application icon".
# Windows one-file .exe uses .ico; macOS .app bundle can use .icns.
WIN_ICON = os.path.join(SPEC_DIR, "assets", "app.ico")
MAC_ICON = os.path.join(SPEC_DIR, "assets", "app.icns")
EXE_ICON_KW = {}
if os.path.isfile(WIN_ICON):
    EXE_ICON_KW["icon"] = WIN_ICON

# customtkinter ships theme JSON files that must be bundled
ctk_datas, ctk_bins, ctk_hidden = collect_all("customtkinter")

# tkinterdnd2 ships a native shared library per platform
try:
    dnd_datas, dnd_bins, dnd_hidden = collect_all("tkinterdnd2")
except Exception:
    dnd_datas, dnd_bins, dnd_hidden = [], [], []

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=ctk_bins + dnd_bins,
    datas=ctk_datas + dnd_datas,
    hiddenimports=(
        ctk_hidden
        + dnd_hidden
        + [
            "PIL._tkinter_finder",
            "numpy",
            "zstandard",
        ]
    ),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TomodachiTextureTool",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no terminal window
    windowed=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **EXE_ICON_KW,
)

# macOS: also wrap in a .app bundle
# Change bundle_identifier if you publish under your own developer identity.
if sys.platform == "darwin":
    BUNDLE_KW = {
        "name": "TomodachiTextureTool.app",
        "bundle_identifier": "com.farbensplasch.tomodachi-texture-tool",
    }
    if os.path.isfile(MAC_ICON):
        BUNDLE_KW["iconfile"] = MAC_ICON
    app = BUNDLE(exe, **BUNDLE_KW)
