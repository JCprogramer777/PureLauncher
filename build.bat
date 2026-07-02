@echo off
rem Reconstruye PureLauncher: assets -> exe -> zip de actualizacion -> instalador.
cd /d "%~dp0"

for /f %%v in ('python -c "import updater; print(updater.APP_VERSION)"') do set VER=%%v
echo Version: %VER%

echo [1/4] Generando assets de marca...
python assets\build_assets.py || goto :error

echo [2/4] Empaquetando exe (PyInstaller, optimizado)...
pyinstaller --noconfirm --clean --log-level WARN --windowed --name PureLauncher --icon assets\icon.ico --add-data "ui;ui" --optimize 2 --exclude-module tkinter --exclude-module unittest --exclude-module pydoc --exclude-module doctest --exclude-module xmlrpc --exclude-module lib2to3 --exclude-module sqlite3 --exclude-module test main.py || goto :error

echo [3/4] Creando zip de actualizacion...
if not exist installer mkdir installer
if exist "installer\PureLauncher-Update-%VER%.zip" del "installer\PureLauncher-Update-%VER%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PureLauncher\*' -DestinationPath 'installer\PureLauncher-Update-%VER%.zip' -CompressionLevel Optimal" || goto :error

echo [4/4] Compilando instalador (Inno Setup)...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
"%ISCC%" /Q /DMyAppVersion=%VER% installer.iss || goto :error

echo.
echo Listo:
echo   installer\PureLauncher-Setup-%VER%.exe        (instalador para equipos nuevos)
echo   installer\PureLauncher-Update-%VER%.zip       (asset para la release de GitHub)
echo.
echo Para publicar la actualizacion:
echo   gh release create v%VER% "installer\PureLauncher-Update-%VER%.zip" --title "PureLauncher %VER%" --notes "cambios..."
goto :eof

:error
echo ERROR en la compilacion.
exit /b 1
