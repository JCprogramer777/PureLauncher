@echo off
rem Reconstruye PureLauncher: assets -> exes firmados -> zip -> instalador firmado.
cd /d "%~dp0"

for /f %%v in ('python -c "import updater; print(updater.APP_VERSION)"') do set VER=%%v
echo Version: %VER%

echo [1/6] Generando assets de marca y metadatos de version...
python assets\build_assets.py || goto :error
python assets\make_version_info.py || goto :error

echo [2/6] Empaquetando launcher (PyInstaller, optimizado)...
pyinstaller --noconfirm --clean --log-level WARN --windowed --name PureLauncher --icon assets\icon.ico --add-data "ui;ui" --version-file version_launcher.txt --splash assets\splash.png --optimize 2 --exclude-module cryptography --exclude-module unittest --exclude-module pydoc --exclude-module doctest --exclude-module xmlrpc --exclude-module lib2to3 --exclude-module sqlite3 --exclude-module test main.py || goto :error

echo [3/6] Empaquetando herramienta de restauracion (onedir, menos falsos positivos)...
if exist dist\Restaurar.exe del dist\Restaurar.exe
pyinstaller --noconfirm --clean --log-level WARN --windowed --name Restaurar --icon assets\icon.ico --version-file version_restore.txt --optimize 2 --exclude-module cryptography --exclude-module unittest --exclude-module pydoc --exclude-module doctest --exclude-module xmlrpc --exclude-module lib2to3 --exclude-module sqlite3 --exclude-module test restore.py || goto :error

echo [4/6] Firmando binarios (Pure Studios)...
powershell -NoProfile -ExecutionPolicy Bypass -File sign.ps1 -Files "dist\PureLauncher\PureLauncher.exe","dist\Restaurar\Restaurar.exe" || goto :error

echo [5/6] Creando zip de actualizacion...
if not exist installer mkdir installer
if exist "installer\PureLauncher-Update-%VER%.zip" del "installer\PureLauncher-Update-%VER%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PureLauncher\*' -DestinationPath 'installer\PureLauncher-Update-%VER%.zip' -CompressionLevel Optimal" || goto :error

echo [6/6] Compilando y firmando el instalador (Inno Setup)...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
"%ISCC%" /Q /DMyAppVersion=%VER% installer.iss || goto :error
powershell -NoProfile -ExecutionPolicy Bypass -File sign.ps1 -Files "installer\PureLauncher-Setup-%VER%.exe" || goto :error

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
