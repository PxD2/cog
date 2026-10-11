@echo off
rem Open Alexandria from the local copy (no internet needed). First run downloads the library.
cd /d "%~dp0"
set "VENV=%USERPROFILE%\PxD2\pxd2-studio\.venv\Scripts"
if exist "%VENV%\pythonw.exe" (set "PY=%VENV%\pythonw.exe") else (set "PY=pythonw")
start "" "%PY%" alexandria_launcher.py %*
