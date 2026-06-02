@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Games Bot v1.0 Build ===
echo.

echo [1/3] Adding Defender exclusion...
powershell -Command "Add-MpPreference -ExclusionPath '%CD%'" 2>nul
powershell -Command "Add-MpPreference -ExclusionPath '%CD%\build_output'" 2>nul

echo [2/3] Building exe...
python -m PyInstaller --onefile --name "GamesBot" --add-data "templates;templates" --add-data "settings.json;." --hidden-import win32com --noconsole --distpath "%CD%\build_output" --workpath "%CD%\build_output\build" main.py

echo.
echo [3/3] Build complete!
echo Exe: %CD%\build_output\GamesBot.exe
echo Copy this exe anywhere to run.
pause
