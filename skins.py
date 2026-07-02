"""Biblioteca de skins de PureLauncher.

Las skins se guardan en APPDATA/PureLauncher/skins (PNG 64x64 normalizado por
la interfaz). La skin activa se aplica al juego mediante un resource pack
("PureSkin") generado en resourcepacks/ que sustituye las texturas por defecto
del jugador (steve/alex y los 9 perfiles de 1.19.3+, en ancho y slim), y se
activa solo anadiendolo a options.txt. Funciona 100% offline.

Nota: en modo offline el modelo (brazos anchos o slim) lo decide el juego a
partir del UUID del nombre; la variante elegida se usa para la vista previa
y queda guardada con la skin.
"""

import base64
import json
import os
import re
import shutil
import struct
import uuid

PACK_NAME = "PureSkin"
# Perfiles por defecto de 1.19.3+ (carpetas wide/ y slim/).
DEFAULT_PROFILES = ["alex", "ari", "efe", "kai", "makena", "noor",
                    "steve", "sunny", "zuri"]


def png_size(data):
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("El archivo no es un PNG valido.")
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def pack_format_for(version_id):
    """pack_format aproximado segun la version que se lanza."""
    m = re.match(r"1\.(\d+)(?:\.(\d+))?", version_id)
    if not m:
        return 34
    minor = int(m.group(1))
    patch = int(m.group(2) or 0)
    if minor <= 8:
        return 1
    if minor <= 10:
        return 2
    if minor <= 12:
        return 3
    if minor <= 14:
        return 4
    if minor == 15:
        return 5
    if minor == 16:
        return 5 if patch < 2 else 6
    if minor == 17:
        return 7
    if minor == 18:
        return 8
    if minor == 19:
        return 9 if patch < 3 else (12 if patch == 3 else 13)
    if minor == 20:
        if patch <= 1:
            return 15
        if patch == 2:
            return 18
        if patch <= 4:
            return 22
        return 32
    if minor == 21:
        if patch <= 1:
            return 34
        if patch <= 3:
            return 42
        if patch == 4:
            return 46
        return 55
    return 55


class SkinManager:
    def __init__(self, config_dir):
        self.dir = os.path.join(config_dir, "skins")
        self.index_path = os.path.join(self.dir, "skins.json")

    # ------------------------------------------------------------- indice

    def _load(self):
        try:
            with open(self.index_path, encoding="utf-8") as f:
                idx = json.load(f)
            idx.setdefault("active", None)
            idx.setdefault("skins", [])
            return idx
        except (OSError, ValueError):
            return {"active": None, "skins": []}

    def _save(self, idx):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2)

    def _png_path(self, skin_id):
        return os.path.join(self.dir, skin_id + ".png")

    # ---------------------------------------------------------------- api

    def list(self):
        idx = self._load()
        out = []
        for s in idx["skins"]:
            try:
                with open(self._png_path(s["id"]), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                continue
            out.append({**s, "active": s["id"] == idx["active"],
                        "dataUrl": "data:image/png;base64," + b64})
        return out

    def add(self, name, variant, png_bytes):
        w, h = png_size(png_bytes)
        if (w, h) != (64, 64):
            raise ValueError(f"La skin debe ser 64x64 (recibido {w}x{h}).")
        if len(png_bytes) > 512 * 1024:
            raise ValueError("El PNG es demasiado grande.")
        name = (name or "Skin").strip()[:32] or "Skin"
        variant = "slim" if variant == "slim" else "classic"
        skin_id = uuid.uuid4().hex[:10]
        os.makedirs(self.dir, exist_ok=True)
        with open(self._png_path(skin_id), "wb") as f:
            f.write(png_bytes)
        idx = self._load()
        idx["skins"].append({"id": skin_id, "name": name, "variant": variant})
        if idx["active"] is None:
            idx["active"] = skin_id
        self._save(idx)
        return skin_id

    def delete(self, skin_id):
        idx = self._load()
        idx["skins"] = [s for s in idx["skins"] if s["id"] != skin_id]
        if idx["active"] == skin_id:
            idx["active"] = None
        self._save(idx)
        try:
            os.remove(self._png_path(skin_id))
        except OSError:
            pass

    def set_active(self, skin_id):
        idx = self._load()
        if skin_id is not None and not any(
            s["id"] == skin_id for s in idx["skins"]
        ):
            raise ValueError("Skin desconocida.")
        idx["active"] = skin_id
        self._save(idx)

    def active(self):
        idx = self._load()
        return next(
            (s for s in idx["skins"] if s["id"] == idx["active"]), None
        )

    # ------------------------------------------------- aplicacion al juego

    def _pack_dir(self, game_dir):
        return os.path.join(game_dir, "resourcepacks", PACK_NAME)

    def remove_pack(self, game_dir):
        shutil.rmtree(self._pack_dir(game_dir), ignore_errors=True)
        self._patch_options(game_dir, remove=True)

    def build_pack(self, game_dir, version_id, modern=True):
        """Escribe el resource pack con la skin activa y lo activa en options.txt."""
        entry = self.active()
        if entry is None:
            self.remove_pack(game_dir)
            return False
        with open(self._png_path(entry["id"]), "rb") as f:
            png = f.read()
        pack = self._pack_dir(game_dir)
        tex = os.path.join(pack, "assets", "minecraft", "textures", "entity")
        shutil.rmtree(pack, ignore_errors=True)
        os.makedirs(tex, exist_ok=True)
        with open(os.path.join(pack, "pack.mcmeta"), "w", encoding="utf-8") as f:
            json.dump({"pack": {
                "pack_format": pack_format_for(version_id),
                "description": f"Skin «{entry['name']}» (PureLauncher)",
            }}, f)
        targets = [os.path.join(tex, "steve.png"), os.path.join(tex, "alex.png")]
        for kind in ("wide", "slim"):
            d = os.path.join(tex, "player", kind)
            os.makedirs(d, exist_ok=True)
            targets += [os.path.join(d, p + ".png") for p in DEFAULT_PROFILES]
        for t in targets:
            with open(t, "wb") as f:
                f.write(png)
        self._patch_options(
            game_dir,
            entries=["file/" + PACK_NAME] if modern else [PACK_NAME],
        )
        return True

    @staticmethod
    def _patch_options(game_dir, entries=None, remove=False):
        path = os.path.join(game_dir, "options.txt")
        lines = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        ours = {PACK_NAME, "file/" + PACK_NAME}
        found = False
        for i, line in enumerate(lines):
            if line.startswith("resourcePacks:"):
                try:
                    arr = json.loads(line.split(":", 1)[1])
                except ValueError:
                    arr = []
                arr = [e for e in arr if e not in ours]
                if not remove:
                    arr += entries
                lines[i] = "resourcePacks:" + json.dumps(arr)
                found = True
        if not found and not remove:
            lines.append("resourcePacks:" + json.dumps(["vanilla"] + entries))
        os.makedirs(game_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
