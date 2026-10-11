@echo off
rem Rebuild the Alexandria 3D sets in high quality on this PC's RTX GPU, then render the hero pictures.
rem Web sets (baked light) -> ..\sets   Unreal sets (colour + real lights for Lumen) -> ..\sets   Pictures -> ..\..\cog-img
cd /d "%~dp0"
set "BL="
for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BL=%%D\blender.exe"
where blender >nul 2>nul && if not defined BL set "BL=blender"
if not defined BL (echo Blender not found. Install it or put blender.exe on PATH. & pause & exit /b 1)
echo Using %BL%
set OUT=%~dp0..\sets
"%BL%" -b -P build_sets.py -- --scene hall --out "%OUT%" --res 2048 --samples 256 --gpu
"%BL%" -b -P build_sets.py -- --scene presidents --out "%OUT%" --res 2048 --samples 256 --gpu
"%BL%" -b -P build_sets.py -- --scene reading --out "%OUT%" --res 2048 --samples 256 --gpu
"%BL%" -b -P build_sets.py -- --scene stair --out "%OUT%" --res 2048 --samples 256 --gpu
"%BL%" -b -P build_sets.py -- --scene hall --out "%OUT%" --res 2048 --unreal
"%BL%" -b -P build_sets.py -- --scene presidents --out "%OUT%" --res 2048 --unreal
"%BL%" -b -P build_sets.py -- --scene reading --out "%OUT%" --res 2048 --unreal
"%BL%" -b -P build_sets.py -- --scene stair --out "%OUT%" --res 2048 --unreal
"%BL%" -b -P render_still.py -- "%OUT%\great_hall_lit.blend" "%OUT%\rotunda.jpg" 0,-11,1.8 0,6,5.5 256 2400 1350
"%BL%" -b -P render_still.py -- "%OUT%\presidents_hall_lit.blend" "%OUT%\theater.jpg" 0,-14,3.2 0,5,4 256 2400 1350
"%BL%" -b -P render_still.py -- "%OUT%\reading_room_lit.blend" "%OUT%\reading.jpg" -6.5,0,1.7 6,0,5 256 2400 1350
"%BL%" -b -P render_still.py -- "%OUT%\archive_stair_lit.blend" "%OUT%\stair.jpg" -7.5,-2,1.7 6,1,4.5 256 2400 1350
echo.
echo Done. Press "Publish 3D sets" in the COG Absorber (or run: python ..\publish_sets.py) to put them on GitHub.
pause
