"""Nucleo del launcher: manifiesto de versiones, descargas y construccion del comando de juego.

Solo contacta los CDN oficiales de Mojang para descargar librerias/assets
(piston-meta, libraries.minecraft.net, resources.download.minecraft.net).
No hay autenticacion, analitica ni telemetria: el juego se lanza en modo offline.
"""

import hashlib
import http.client
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES_URL = "https://resources.download.minecraft.net"
LIBRARIES_URL = "https://libraries.minecraft.net/"
LAUNCHER_NAME = "PureLauncher"
LAUNCHER_VERSION = "1.1.0"

IS_64BIT = platform.machine().endswith("64")


# ---------------------------------------------------------------- utilidades

# Pool de conexiones keep-alive por hilo: al descargar miles de archivos
# pequenos (assets) el handshake TLS por archivo es el cuello de botella.
_pool = threading.local()


def http_get(url, timeout=25, _depth=0):
    if _depth > 4:
        raise RuntimeError(f"Demasiadas redirecciones: {url}")
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise ValueError(f"URL no soportada: {url}")
    path = (u.path or "/") + (f"?{u.query}" if u.query else "")
    conns = getattr(_pool, "conns", None)
    if conns is None:
        conns = _pool.conns = {}
    key = f"{u.scheme}://{u.netloc}"
    last_err = None
    for attempt in range(2):
        conn = conns.get(key)
        try:
            if conn is None:
                cls = (http.client.HTTPSConnection if u.scheme == "https"
                       else http.client.HTTPConnection)
                conn = cls(u.netloc, timeout=max(timeout, 25))
                conns[key] = conn
            conn.request("GET", path, headers={
                "User-Agent": f"{LAUNCHER_NAME}/{LAUNCHER_VERSION}",
                "Connection": "keep-alive",
            })
            resp = conn.getresponse()
            data = resp.read()
            if resp.status in (301, 302, 303, 307, 308):
                loc = resp.getheader("Location")
                if loc:
                    return http_get(loc, timeout, _depth + 1)
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} en {url}")
            return data
        except (http.client.HTTPException, OSError) as e:
            last_err = e
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            conns.pop(key, None)
    raise RuntimeError(f"Fallo de red en {url}: {last_err}")


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def file_ok(path, sha1=None, size=None, quick=False):
    if not os.path.isfile(path):
        return False
    if size is not None and os.path.getsize(path) != size:
        return False
    # quick: si el tamano coincide no rehasheamos (rehashear cientos de MB
    # de assets en cada lanzamiento cuesta varios segundos).
    if quick and size is not None:
        return True
    if sha1:
        return sha1_of(path) == sha1
    return True


def download_file(url, path, sha1=None, size=None, retries=3):
    if file_ok(path, sha1, size):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    last_err = None
    for _ in range(retries):
        try:
            data = http_get(url, timeout=60)
            if sha1 and hashlib.sha1(data).hexdigest() != sha1:
                last_err = ValueError(f"sha1 incorrecto para {url}")
                continue
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return True
        except Exception as e:  # noqa: BLE001 - reintento generico de red
            last_err = e
    raise RuntimeError(f"No se pudo descargar {url}: {last_err}")


def offline_uuid(name):
    """Mismo UUID que usa el modo offline de Java: nameUUIDFromBytes."""
    digest = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=digest, version=3))


# ------------------------------------------------------------------- reglas

def _os_version():
    try:
        return platform.version()
    except Exception:  # noqa: BLE001
        return ""


def rule_matches(rule, features):
    os_spec = rule.get("os")
    if os_spec:
        if os_spec.get("name") and os_spec["name"] != "windows":
            return False
        if os_spec.get("arch"):
            want64 = os_spec["arch"] in ("x64", "x86_64", "amd64")
            if want64 != IS_64BIT:
                return False
        if os_spec.get("version"):
            if not re.match(os_spec["version"], _os_version()):
                return False
    feats = rule.get("features")
    if feats:
        features = features or {}
        for key, val in feats.items():
            if bool(features.get(key, False)) != bool(val):
                return False
    return True


def rules_allow(rules, features=None):
    if not rules:
        return True
    allowed = False
    for rule in rules:
        if rule_matches(rule, features):
            allowed = rule.get("action") == "allow"
    return allowed


# --------------------------------------------------------------- lanzamiento

class Launcher:
    def __init__(self, game_dir, progress=None):
        self.game_dir = os.path.abspath(game_dir)
        self.versions_dir = os.path.join(self.game_dir, "versions")
        self.libraries_dir = os.path.join(self.game_dir, "libraries")
        self.assets_dir = os.path.join(self.game_dir, "assets")
        self.progress = progress or (lambda stage, done, total, msg: None)
        self._manifest = None

    # ------------------------------------------------------------ manifiesto

    def manifest(self, force=False, max_age=1800):
        cache = os.path.join(self.game_dir, "version_manifest_v2.json")
        if self._manifest and not force:
            return self._manifest
        # Cache en disco reciente: evita un viaje de red en cada arranque.
        if (not force and os.path.isfile(cache)
                and time.time() - os.path.getmtime(cache) < max_age):
            try:
                with open(cache, encoding="utf-8") as f:
                    self._manifest = json.load(f)
                return self._manifest
            except (OSError, ValueError):
                pass
        try:
            data = http_get(MANIFEST_URL)
            os.makedirs(self.game_dir, exist_ok=True)
            with open(cache, "wb") as f:
                f.write(data)
            self._manifest = json.loads(data)
        except Exception:  # noqa: BLE001 - sin red usamos la cache
            if os.path.isfile(cache):
                with open(cache, encoding="utf-8") as f:
                    self._manifest = json.load(f)
            else:
                raise RuntimeError(
                    "Sin conexion y sin manifiesto en cache. "
                    "Conectate a internet para la primera descarga."
                )
        return self._manifest

    def remote_versions(self):
        return [
            {"id": v["id"], "type": v["type"], "released": v.get("releaseTime", "")}
            for v in self.manifest()["versions"]
        ]

    def installed_versions(self):
        result = []
        if not os.path.isdir(self.versions_dir):
            return result
        for name in sorted(os.listdir(self.versions_dir)):
            vdir = os.path.join(self.versions_dir, name)
            vjson = os.path.join(vdir, name + ".json")
            if os.path.isfile(vjson):
                result.append({
                    "id": name,
                    "hasJar": os.path.isfile(os.path.join(vdir, name + ".jar")),
                })
        return result

    # -------------------------------------------------------------- importar

    def import_version(self, jar_path, base_version, name=None):
        """Instala el .jar del usuario junto al JSON oficial de la version base."""
        name = (name or base_version).strip()
        if not re.fullmatch(r"[\w .()\[\]-]+", name):
            raise ValueError("Nombre de version no valido.")
        entry = next(
            (v for v in self.manifest()["versions"] if v["id"] == base_version), None
        )
        if entry is None:
            raise ValueError(f"Version base desconocida: {base_version}")
        self.progress("import", 0, 2, "Descargando metadatos de la version...")
        vdata = json.loads(http_get(entry["url"]))
        vdata["id"] = name
        vdir = os.path.join(self.versions_dir, name)
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(vdata, f)
        self.progress("import", 1, 2, "Copiando tu .jar...")
        shutil.copyfile(jar_path, os.path.join(vdir, name + ".jar"))
        self.progress("import", 2, 2, "Version importada.")
        return name

    def install_vanilla(self, version_id):
        """Instala el JSON (y luego el jar oficial al preparar) de una version vanilla."""
        entry = next(
            (v for v in self.manifest()["versions"] if v["id"] == version_id), None
        )
        if entry is None:
            raise ValueError(f"Version desconocida: {version_id}")
        vdata = json.loads(http_get(entry["url"]))
        vdir = os.path.join(self.versions_dir, version_id)
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, version_id + ".json"), "w", encoding="utf-8") as f:
            json.dump(vdata, f)
        return version_id

    # ------------------------------------------------------- resolver version

    def load_version(self, version_id, _depth=0):
        if _depth > 5:
            raise RuntimeError("Cadena de inheritsFrom demasiado profunda.")
        vjson = os.path.join(self.versions_dir, version_id, version_id + ".json")
        if not os.path.isfile(vjson):
            raise FileNotFoundError(f"No existe versions/{version_id}/{version_id}.json")
        with open(vjson, encoding="utf-8") as f:
            data = json.load(f)
        parent_id = data.get("inheritsFrom")
        if not parent_id:
            return data
        # Perfiles de Forge/Fabric: fusionar con la version padre.
        parent_json = os.path.join(self.versions_dir, parent_id, parent_id + ".json")
        if not os.path.isfile(parent_json):
            self.install_vanilla(parent_id)
        parent = self.load_version(parent_id, _depth + 1)
        merged = dict(parent)
        merged["id"] = data.get("id", version_id)
        for key in ("mainClass", "assets", "assetIndex", "type", "minecraftArguments"):
            if key in data:
                merged[key] = data[key]
        merged["libraries"] = data.get("libraries", []) + parent.get("libraries", [])
        if "arguments" in data or "arguments" in parent:
            pa, ca = parent.get("arguments", {}), data.get("arguments", {})
            merged["arguments"] = {
                "game": pa.get("game", []) + ca.get("game", []),
                "jvm": pa.get("jvm", []) + ca.get("jvm", []),
            }
        merged["_jarFrom"] = parent_id if not os.path.isfile(
            os.path.join(self.versions_dir, version_id, version_id + ".jar")
        ) else version_id
        return merged

    # -------------------------------------------------------------- librerias

    @staticmethod
    def _maven_path(coord):
        parts = coord.split(":")
        group, artifact, version = parts[0], parts[1], parts[2]
        classifier = "-" + parts[3] if len(parts) > 3 else ""
        return "/".join(
            [group.replace(".", "/"), artifact, version,
             f"{artifact}-{version}{classifier}.jar"]
        )

    def _collect_libraries(self, vdata):
        """Devuelve (jars_classpath, natives_a_extraer, descargas_pendientes)."""
        classpath, natives, downloads = [], [], []
        seen = set()
        for lib in vdata.get("libraries", []):
            if not rules_allow(lib.get("rules")):
                continue
            dl = lib.get("downloads", {})
            art = dl.get("artifact")
            if art is None and "name" in lib and "classifiers" not in dl:
                # Formato Forge/Fabric: name + url base maven.
                rel = self._maven_path(lib["name"])
                art = {"path": rel, "url": (lib.get("url") or LIBRARIES_URL).rstrip("/") + "/" + rel}
            if art and art.get("path"):
                path = os.path.join(self.libraries_dir, *art["path"].split("/"))
                if art["path"] not in seen:
                    seen.add(art["path"])
                    classpath.append(path)
                    if art.get("url"):
                        downloads.append((art["url"], path, art.get("sha1"), art.get("size")))
            # Natives con classifier (versiones antiguas).
            natives_map = lib.get("natives", {})
            key = natives_map.get("windows")
            if key:
                key = key.replace("${arch}", "64" if IS_64BIT else "32")
                cls = dl.get("classifiers", {}).get(key)
                if cls and cls.get("path"):
                    path = os.path.join(self.libraries_dir, *cls["path"].split("/"))
                    downloads.append((cls["url"], path, cls.get("sha1"), cls.get("size")))
                    natives.append((path, lib.get("extract", {}).get("exclude", [])))
        return classpath, natives, downloads

    # ----------------------------------------------------------------- assets

    def _collect_assets(self, vdata):
        idx_info = vdata.get("assetIndex")
        if not idx_info:
            return vdata.get("assets", "legacy"), []
        idx_path = os.path.join(self.assets_dir, "indexes", idx_info["id"] + ".json")
        download_file(idx_info["url"], idx_path, idx_info.get("sha1"))
        with open(idx_path, encoding="utf-8") as f:
            index = json.load(f)
        downloads = []
        for obj in index.get("objects", {}).values():
            h = obj["hash"]
            path = os.path.join(self.assets_dir, "objects", h[:2], h)
            downloads.append((f"{RESOURCES_URL}/{h[:2]}/{h}", path, h, obj.get("size")))
        self._asset_index_data = index
        return idx_info["id"], downloads

    def _materialize_legacy_assets(self, index_id):
        index = getattr(self, "_asset_index_data", None)
        if not index:
            return None
        if index.get("map_to_resources"):
            target = os.path.join(self.game_dir, "resources")
        elif index.get("virtual"):
            target = os.path.join(self.assets_dir, "virtual", index_id)
        else:
            return None
        for name, obj in index.get("objects", {}).items():
            h = obj["hash"]
            src = os.path.join(self.assets_dir, "objects", h[:2], h)
            dst = os.path.join(target, *name.split("/"))
            if not file_ok(dst, size=obj.get("size")):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        return target

    # ------------------------------------------------------------- descargas

    def _download_all(self, downloads, stage, label):
        pending = [d for d in downloads if not file_ok(d[1], d[2], d[3], quick=True)]
        total = len(pending)
        if not total:
            return
        done = 0
        self.progress(stage, 0, total, label)
        errors = []
        workers = min(32, max(12, (os.cpu_count() or 4) * 3))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(download_file, url, path, sha1, size): path
                    for url, path, sha1, size in pending}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:  # noqa: BLE001
                    errors.append(str(e))
                done += 1
                if done % 5 == 0 or done == total:
                    self.progress(stage, done, total, label)
        if errors:
            raise RuntimeError(f"{len(errors)} descargas fallaron. Primera: {errors[0]}")

    def _extract_natives(self, natives, natives_dir):
        os.makedirs(natives_dir, exist_ok=True)
        for jar_path, excludes in natives:
            with zipfile.ZipFile(jar_path) as z:
                for info in z.infolist():
                    n = info.filename
                    if n.endswith("/") or n.startswith("META-INF"):
                        continue
                    if any(n.startswith(ex) for ex in excludes):
                        continue
                    target = os.path.join(natives_dir, os.path.basename(n))
                    if not os.path.exists(target):
                        with z.open(info) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)

    # -------------------------------------------------------------- preparar

    def prepare(self, version_id):
        """Descarga todo lo necesario y devuelve el contexto de lanzamiento."""
        self.progress("prepare", 0, 1, "Leyendo la version...")
        vdata = self.load_version(version_id)

        jar_owner = vdata.get("_jarFrom", version_id)
        client_jar = os.path.join(self.versions_dir, jar_owner, jar_owner + ".jar")
        client_dl = vdata.get("downloads", {}).get("client")
        if not os.path.isfile(client_jar):
            if client_dl and client_dl.get("url"):
                self.progress("client", 0, 1, "Descargando el jar del cliente...")
                download_file(client_dl["url"], client_jar,
                              client_dl.get("sha1"), client_dl.get("size"))
            else:
                raise FileNotFoundError(
                    f"Falta el jar del cliente: {client_jar}. Importa tu .jar primero."
                )

        classpath, natives, lib_downloads = self._collect_libraries(vdata)
        self._download_all(lib_downloads, "libraries", "Descargando librerias...")

        asset_index_id, asset_downloads = self._collect_assets(vdata)
        self._download_all(asset_downloads, "assets", "Descargando recursos (assets)...")
        legacy_assets = self._materialize_legacy_assets(asset_index_id)

        natives_dir = os.path.join(self.versions_dir, version_id, "natives")
        self._extract_natives(natives, natives_dir)

        classpath.append(client_jar)
        self.progress("ready", 1, 1, "Todo listo.")
        return {
            "vdata": vdata,
            "classpath": classpath,
            "natives_dir": natives_dir,
            "asset_index_id": asset_index_id,
            "legacy_assets": legacy_assets,
        }

    # --------------------------------------------------------------- comando

    def build_command(self, version_id, ctx, username, java, ram_mb,
                      extra_jvm="", block_services=True, resolution=None,
                      opt_flags=None, xms_mb=512):
        vdata = ctx["vdata"]
        cp = os.pathsep.join(ctx["classpath"])
        assets_root = self.assets_dir
        game_assets = ctx["legacy_assets"] or assets_root

        subs = {
            "auth_player_name": username,
            "version_name": version_id,
            "game_directory": self.game_dir,
            "assets_root": assets_root,
            "game_assets": game_assets,
            "assets_index_name": ctx["asset_index_id"],
            "auth_uuid": offline_uuid(username),
            "auth_access_token": "0",
            "auth_session": "0",
            "clientid": "",
            "auth_xuid": "",
            "user_type": "legacy",
            "user_properties": "{}",
            "version_type": vdata.get("type", "release"),
            "natives_directory": ctx["natives_dir"],
            "launcher_name": LAUNCHER_NAME,
            "launcher_version": LAUNCHER_VERSION,
            "classpath": cp,
            "resolution_width": str((resolution or {}).get("width", 854)),
            "resolution_height": str((resolution or {}).get("height", 480)),
        }

        def sub(text):
            for key, val in subs.items():
                text = text.replace("${" + key + "}", val)
            return text

        features = {"has_custom_resolution": bool(resolution)}

        def expand(entries):
            out = []
            for entry in entries:
                if isinstance(entry, str):
                    out.append(sub(entry))
                    continue
                if not rules_allow(entry.get("rules"), features):
                    continue
                value = entry.get("value", [])
                if isinstance(value, str):
                    value = [value]
                out.extend(sub(v) for v in value)
            return out

        cmd = [java, f"-Xms{int(xms_mb)}M", f"-Xmx{int(ram_mb)}M",
               "-Dlog4j2.formatMsgNoLookups=true"]
        if opt_flags:
            cmd.extend(opt_flags)
        if block_services:
            # Redirige los servicios de Mojang (auth, sesion, telemetria) a un
            # host invalido: el juego no puede enviar nada aunque lo intente.
            for svc in ("auth", "account", "session", "services"):
                cmd.append(f"-Dminecraft.api.{svc}.host=https://0.0.0.0")
            cmd.append("-Dminecraft.api.env=custom")
        if extra_jvm.strip():
            try:
                cmd.extend(shlex.split(extra_jvm, posix=False))
            except ValueError:
                cmd.extend(extra_jvm.split())

        args = vdata.get("arguments")
        if args:
            cmd.extend(expand(args.get("jvm", [])))
        else:
            cmd.extend([f"-Djava.library.path={ctx['natives_dir']}", "-cp", cp])

        cmd.append(vdata["mainClass"])

        if args:
            cmd.extend(expand(args.get("game", [])))
        else:
            cmd.extend(sub(tok) for tok in vdata.get("minecraftArguments", "").split())
        if resolution and not args:
            cmd.extend(["--width", subs["resolution_width"],
                        "--height", subs["resolution_height"]])
        return cmd

    def launch(self, cmd, log_path, high_priority=False):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log = open(log_path, "w", encoding="utf-8", errors="replace")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        if high_priority and os.name == "nt":
            flags |= subprocess.ABOVE_NORMAL_PRIORITY_CLASS
        return subprocess.Popen(
            cmd, cwd=self.game_dir, stdout=log, stderr=subprocess.STDOUT,
            creationflags=flags,
        )


def find_java():
    """Busca javaw.exe (sin consola) o java. Devuelve None si no hay Java."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        cand = os.path.join(java_home, "bin", "javaw.exe")
        if os.path.isfile(cand):
            return cand
    for name in ("javaw", "java"):
        found = shutil.which(name)
        if found:
            return found
    return None
