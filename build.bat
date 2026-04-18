@echo off
echo Installing build dependencies...
python -m pip install pyinstaller
echo.
echo Building...
python -m PyInstaller TomodachiTextureTool.spec
echo.
echo Done! Executable is at: dist\TomodachiTextureTool.exe
pause
