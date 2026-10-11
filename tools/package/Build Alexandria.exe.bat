@echo off
rem Builds Alexandria.exe: a one-file desktop app that carries the whole library (app + COG packs + 3D sets) and
rem updates itself from GitHub when online. Output: dist\Alexandria.exe   (copy it anywhere; no install needed)
cd /d "%~dp0"
set "VENV=%USERPROFILE%\PxD2\pxd2-studio\.venv\Scripts"
if exist "%VENV%\python.exe" (set "PY=%VENV%\python.exe") else (set "PY=python")
"%PY%" -m pip install --quiet pyinstaller pillow
echo Getting the latest library from GitHub...


"%PY%" -c "import alexandria_launcher as a; a.update_from_github()"
if not exist library\alexandria\index.html (echo Could not get the library. Check the internet connection. & pause & exit /b 1)
"%PY%" -m PyInstaller --noconfirm --onefile --windowed --name Alexandria --icon=library\alexandria\img\icon-512.png --add-data "library;library" alexandria_launcher.py
echo.
echo Built dist\Alexandria.exe
pause
