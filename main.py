"""PureLauncher: launcher de Minecraft ligero, offline y sin telemetria."""

import base64
import json
import os
import subprocess
import sys
import threading

import webview

import mc_core
import optimizer
import skins
import updater

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Recursos empaquetados (PyInstaller) o del arbol de codigo.
RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
# La configuracion vive en APPDATA: escribible aunque la app este instalada.
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", BASE_DIR), "PureLauncher")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "username": "Jugador",
    "ram_mb": 4096,
    "game_dir": os.path.join(os.environ.get("APPDATA", BASE_DIR), ".minecraft"),
    "java_path": "",
    "extra_jvm": "",
    "block_services": True,
    "show_snapshots": False,
    "keep_open": True,
    "last_version": "",
    "resolution": None,
    "auto_check_updates": True,
    "opt_level": "balanced",
    "high_priority": True,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    for path in (CONFIG_PATH, os.path.join(BASE_DIR, "config.json")):
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
            break
        except (OSError, ValueError):
            continue
    return cfg


class Api:
    def __init__(self):
        self.window = None
        self.config = load_config()
        self.process = None
        self._busy = False
        self._pending_update = None
        self._auto_checked = False
        self._launcher_obj = None
        self.skins = skins.SkinManager(CONFIG_DIR)

    # ------------------------------------------------------------ auxiliares

    def _launcher(self):
        game_dir = os.path.abspath(self.config["game_dir"])
        if self._launcher_obj is None or self._launcher_obj.game_dir != game_dir:
            self._launcher_obj = mc_core.Launcher(game_dir, progress=self._progress)
        return self._launcher_obj

    def _progress(self, stage, done, total, msg):
        payload = json.dumps(
            {"stage": stage, "done": done, "total": total, "msg": msg}
        )
        if self.window:
            self.window.evaluate_js(f"UI.onProgress({payload})")

    def _emit(self, event, data=None):
        payload = json.dumps(data if data is not None else {})
        if self.window:
            self.window.evaluate_js(f"UI.onEvent({json.dumps(event)}, {payload})")

    # ------------------------------------------------------------------- api

    def get_state(self):
        installed = []
        try:
            installed = self._launcher().installed_versions()
        except Exception:  # noqa: BLE001
            pass
        self._auto_check_updates()
        return {
            "config": self.config,
            "installed": installed,
            "running": self.process is not None and self.process.poll() is None,
            "javaDetected": mc_core.find_java(),
            "appVersion": updater.APP_VERSION,
            "isInstalled": updater.is_frozen(),
            "systemRamMb": optimizer.system_ram_mb(),
            "recommendedRamMb": optimizer.recommended_ram_mb(),
        }

    def _auto_check_updates(self):
        if self._auto_checked or not self.config.get("auto_check_updates"):
            return
        self._auto_checked = True

        def work():
            try:
                info = updater.check_update()
                if info:
                    self._pending_update = info
                    self._emit("updateAvailable", info)
            except Exception:  # noqa: BLE001 - la comprobacion silenciosa no molesta
                pass

        threading.Thread(target=work, daemon=True).start()

    def check_updates(self):
        try:
            info = updater.check_update()
            self._pending_update = info
            return {"ok": True, "update": info, "current": updater.APP_VERSION}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def apply_update(self):
        if self._busy:
            return {"ok": False, "error": "Ya hay una operacion en curso."}
        info = self._pending_update
        if not info:
            return {"ok": False, "error": "No hay ninguna actualizacion pendiente."}
        if not updater.is_frozen():
            return {"ok": False, "error": "Solo disponible en la version instalada (.exe)."}

        def work():
            self._busy = True
            try:
                zip_path = os.path.join(
                    os.environ.get("TEMP", "."), "purelauncher-update.zip"
                )

                def prog(done, total):
                    self._emit("updateProgress", {"done": done, "total": total})

                updater.download_zip(info["url"], zip_path, prog)
                stage = updater.stage_zip(zip_path)
                updater.launch_applier(stage)
                self._emit("updateRestarting", {})
                import time
                time.sleep(1.2)
                self.window.destroy()
            except Exception as e:  # noqa: BLE001
                self._emit("updateError", {"error": str(e)})
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    # ---------------------------------------------------------------- skins

    def list_skins(self):
        return self.skins.list()

    def pick_skin_file(self):
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Skin PNG (*.png)",)
        )
        return paths[0] if paths else None

    def fetch_skin_source(self, kind, value):
        """Lee la skin en bruto (archivo o URL) y la devuelve en base64
        para que la interfaz la normalice a 64x64 con canvas."""
        try:
            if kind == "file":
                with open(value, "rb") as f:
                    data = f.read()
            else:
                if not value.lower().startswith(("http://", "https://")):
                    raise ValueError("El enlace debe empezar por http:// o https://")
                data = mc_core.http_get(value.strip())
            if len(data) > 4 * 1024 * 1024:
                raise ValueError("El archivo es demasiado grande.")
            skins.png_size(data)  # valida que sea PNG
            return {"ok": True,
                    "b64": "data:image/png;base64,"
                           + base64.b64encode(data).decode("ascii")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def save_skin(self, name, variant, data_url):
        try:
            b64 = data_url.split(",", 1)[1]
            skin_id = self.skins.add(name, variant, base64.b64decode(b64))
            return {"ok": True, "id": skin_id}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def set_active_skin(self, skin_id):
        try:
            self.skins.set_active(skin_id)
            if skin_id is None:
                self.skins.remove_pack(self.config["game_dir"])
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def delete_skin(self, skin_id):
        was_active = (self.skins.active() or {}).get("id") == skin_id
        self.skins.delete(skin_id)
        if was_active:
            self.skins.remove_pack(self.config["game_dir"])
        return {"ok": True}

    def download_vanilla(self, version_id):
        """Instala una version oficial completa (json + jar + librerias + assets)."""
        if self._busy:
            return {"ok": False, "error": "Ya hay una operacion en curso."}

        def work():
            self._busy = True
            try:
                launcher = self._launcher()
                launcher.install_vanilla(version_id)
                launcher.prepare(version_id)
                self.config["last_version"] = version_id
                self.save_settings({})
                self._emit("installDone", {"ok": True, "id": version_id})
            except Exception as e:  # noqa: BLE001
                self._emit("installDone", {"ok": False, "error": str(e)})
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def get_remote_versions(self):
        try:
            versions = self._launcher().remote_versions()
            if not self.config["show_snapshots"]:
                versions = [v for v in versions if v["type"] in ("release", "old_beta", "old_alpha")]
            return {"ok": True, "versions": versions}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def save_settings(self, settings):
        for key in DEFAULT_CONFIG:
            if key in settings:
                self.config[key] = settings[key]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        return self.get_state()

    def pick_jar(self):
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Minecraft jar (*.jar)",)
        )
        return paths[0] if paths else None

    def pick_folder(self):
        paths = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return paths[0] if paths else None

    def pick_java(self):
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Java (javaw.exe;java.exe)",)
        )
        return paths[0] if paths else None

    def open_game_dir(self):
        os.makedirs(self.config["game_dir"], exist_ok=True)
        os.startfile(self.config["game_dir"])  # noqa: S606

    def import_jar(self, jar_path, base_version, name):
        if self._busy:
            return {"ok": False, "error": "Ya hay una operacion en curso."}

        def work():
            self._busy = True
            try:
                vid = self._launcher().import_version(jar_path, base_version, name or None)
                self.config["last_version"] = vid
                self.save_settings({})
                self._emit("importDone", {"ok": True, "id": vid})
            except Exception as e:  # noqa: BLE001
                self._emit("importDone", {"ok": False, "error": str(e)})
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def install_vanilla(self, version_id):
        if self._busy:
            return {"ok": False, "error": "Ya hay una operacion en curso."}

        def work():
            self._busy = True
            try:
                vid = self._launcher().install_vanilla(version_id)
                self._emit("importDone", {"ok": True, "id": vid})
            except Exception as e:  # noqa: BLE001
                self._emit("importDone", {"ok": False, "error": str(e)})
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def launch(self, version_id, username):
        if self._busy:
            return {"ok": False, "error": "Ya hay una operacion en curso."}
        if self.process is not None and self.process.poll() is None:
            return {"ok": False, "error": "El juego ya esta en ejecucion."}
        username = (username or "Jugador").strip()[:16] or "Jugador"
        self.config["username"] = username
        self.config["last_version"] = version_id
        self.save_settings({})

        def work():
            self._busy = True
            try:
                launcher = self._launcher()
                ctx = launcher.prepare(version_id)
                try:
                    # Aplica la skin activa (resource pack); si falla no
                    # bloquea el lanzamiento.
                    self.skins.build_pack(
                        self.config["game_dir"], version_id,
                        modern="arguments" in ctx["vdata"],
                    )
                except Exception:  # noqa: BLE001
                    pass
                java = self.config["java_path"] or mc_core.find_java()
                xms_mb, opt_flags = optimizer.jvm_setup(
                    self.config["opt_level"], self.config["ram_mb"]
                )
                cmd = launcher.build_command(
                    version_id, ctx, username, java,
                    self.config["ram_mb"],
                    extra_jvm=self.config["extra_jvm"],
                    block_services=self.config["block_services"],
                    resolution=self.config["resolution"],
                    opt_flags=opt_flags,
                    xms_mb=xms_mb,
                )
                log_path = os.path.join(
                    self.config["game_dir"], "logs", "purelauncher-latest.log"
                )
                self.process = launcher.launch(
                    cmd, log_path, high_priority=self.config["high_priority"]
                )
                self._emit("gameStarted", {"pid": self.process.pid})
                code = self.process.wait()
                tail = ""
                try:
                    with open(log_path, encoding="utf-8", errors="replace") as f:
                        tail = "".join(f.readlines()[-40:])
                except OSError:
                    pass
                self.process = None
                self._emit("gameExited", {"code": code, "log": tail})
            except Exception as e:  # noqa: BLE001
                self.process = None
                self._emit("launchError", {"error": str(e)})
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def kill_game(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
        return {"ok": True}


def main():
    api = Api()
    window = webview.create_window(
        "PureLauncher",
        url=os.path.join(RES_DIR, "ui", "index.html"),
        js_api=api,
        width=1000,
        height=640,
        min_size=(860, 560),
        background_color="#17171c",
    )
    api.window = window
    webview.start(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
