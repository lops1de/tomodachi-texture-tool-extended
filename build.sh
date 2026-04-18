#!/usr/bin/env bash
set -e

echo "Installing build dependencies..."
python3 -m pip install pyinstaller

echo "Building..."
python3 -m PyInstaller TomodachiTextureTool.spec

echo ""
echo "Done! Executable is at: dist/TomodachiTextureTool"
