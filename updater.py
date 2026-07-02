"""Sistema de actualizacion de PureLauncher via GitHub Releases.

Flujo:
1. `check_update(repo)` consulta la ultima release del repositorio
   (api.github.com) y compara su tag con APP_VERSION.
2. `download_zip(url, dest, progress)` baja el asset .zip de la release.
3. `stage_zip(zip_path)` lo verifica y extrae a una carpeta temporal.
4. `launch_applier(stage_dir)` deja un .bat que espera a que el launcher
   cierre, copia los archivos nuevos sobre la instalacion y lo relanza.

La release debe incluir un asset .zip con el contenido de la carpeta de la
app (PureLauncher.exe + _internal/), tal como lo genera build.bat.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from urllib.request import Request, urlopen

APP_VERSION = "1.1.1"
# Repositorio oficial de actualizaciones (fijo, no configurable por el usuario).
UPDATE_REPO = "JCprogramer777/PureLauncher"
USER_AGENT = f"PureLauncher/{APP_VERSION}"


def _get(url, timeout=25):
    req = Request(url, headers={"User-Agent": USER_AGENT,
                                "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_version(text):
    nums = [int(n) for n in re.findall(r"\d+", str(text))[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def install_dir():
    return os.path.dirname(sys.executable) if is_frozen() else None


# ------------------------------------------------------------------ comprobar

def check_update(repo=None):
    """Devuelve info de la actualizacion o None si ya estamos al dia."""
    repo = repo or UPDATE_REPO
    data = json.loads(_get(f"https://api.github.com/repos/{repo}/releases/latest"))
    tag = str(data.get("tag_name", ""))
    if parse_version(tag) <= parse_version(APP_VERSION):
        return None
    assets = data.get("assets", [])
    asset = next(
        (a for a in assets if "update" in a["name"].lower() and a["name"].lower().endswith(".zip")),
        None,
    ) or next((a for a in assets if a["name"].lower().endswith(".zip")), None)
    if asset is None:
        raise RuntimeError(f"La release {tag} no incluye ningun .zip de actualizacion.")
    return {
        "version": tag.lstrip("vV"),
        "title": data.get("name") or tag,
        "notes": (data.get("body") or "").strip()[:4000],
        "url": asset["browser_download_url"],
        "size": asset.get("size", 0),
        "assetName": asset["name"],
    }


# ------------------------------------------------------------------ descargar

def download_zip(url, dest, progress=None):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1024 * 128)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    os.replace(tmp, dest)
    return dest


def stage_zip(zip_path):
    """Verifica el zip y lo extrae a una carpeta temporal de staging."""
    stage = os.path.join(tempfile.gettempdir(), "PureLauncher-update-stage")
    if os.path.isdir(stage):
        shutil.rmtree(stage, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None:
            raise RuntimeError("El .zip de actualizacion esta corrupto.")
        names = z.namelist()
        for n in names:
            if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                raise RuntimeError("El .zip contiene rutas no seguras.")
        z.extractall(stage)
    # Si todo el contenido cuelga de una unica carpeta raiz, descender a ella.
    entries = os.listdir(stage)
    if len(entries) == 1 and os.path.isdir(os.path.join(stage, entries[0])):
        stage = os.path.join(stage, entries[0])
    return stage


# -------------------------------------------------------------------- aplicar

APPLY_BAT = r"""@echo off
setlocal
set "STAGE={stage}"
set "APP={app}"
:wait
tasklist /FI "PID eq {pid}" 2>nul | find " {pid} " >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)
if exist "%STAGE%\_internal" robocopy "%STAGE%\_internal" "%APP%\_internal" /MIR /R:3 /W:1 >nul
robocopy "%STAGE%" "%APP%" /E /XD _internal /R:3 /W:1 >nul
rd /s /q "%STAGE%" >nul 2>nul
if exist "%APP%\{exe}" start "" "%APP%\{exe}"
del "%~f0"
"""


def launch_applier(stage_dir, app_dir=None, exe_name="PureLauncher.exe", pid=None):
    """Deja el aplicador corriendo; el llamante debe cerrar la app justo despues."""
    app_dir = app_dir or install_dir()
    if not app_dir:
        raise RuntimeError(
            "La actualizacion automatica solo funciona en la version instalada "
            "(ejecutable), no al correr desde el codigo fuente."
        )
    new_exe = os.path.join(stage_dir, exe_name)
    if not os.path.isfile(new_exe) and not os.path.isdir(os.path.join(stage_dir, "_internal")):
        raise RuntimeError("El .zip no parece una actualizacion de PureLauncher.")
    bat = os.path.join(tempfile.gettempdir(), "purelauncher-apply-update.bat")
    with open(bat, "w", encoding="ascii", errors="replace") as f:
        f.write(APPLY_BAT.format(stage=stage_dir, app=app_dir,
                                 pid=pid or os.getpid(), exe=exe_name))
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
    return bat
