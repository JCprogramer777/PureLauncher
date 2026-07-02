"""Restauracion de PureLauncher.

Herramienta de recuperacion independiente (se compila como Restaurar.exe,
onefile, sin depender de los archivos del launcher). Sirve cuando una
actualizacion sale corrupta o el launcher no arranca:

- Restaurar la copia de seguridad local (se crea sola antes de cada
  actualizacion).
- Descargar e instalar cualquier version estable publicada en GitHub
  (la mas reciente o una anterior).

Cierra el launcher si esta abierto, aplica los archivos y lo relanza.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import updater

APP_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Programs", "PureLauncher"
)
EXE_NAME = "PureLauncher.exe"
SELF_NAME = "Restaurar.exe"

BG = "#14181d"
CARD = "#1d232b"
FG = "#eaf0f4"
DIM = "#93a1ad"
GREEN = "#2ecc71"


def list_releases():
    """Releases con asset .zip de actualizacion, de mas nueva a mas vieja."""
    data = json.loads(updater._get(
        f"https://api.github.com/repos/{updater.UPDATE_REPO}/releases?per_page=20"
    ))
    out = []
    for rel in data:
        if rel.get("draft"):
            continue
        asset = next(
            (a for a in rel.get("assets", [])
             if "update" in a["name"].lower() and a["name"].lower().endswith(".zip")),
            None,
        )
        if asset:
            out.append({
                "tag": rel["tag_name"],
                "title": rel.get("name") or rel["tag_name"],
                "url": asset["browser_download_url"],
                "size": asset.get("size", 0),
                "prerelease": rel.get("prerelease", False),
            })
    return out


def backup_info():
    info = os.path.join(updater.backup_dir(), "backup-info.txt")
    if os.path.isfile(info) and os.path.isdir(
        os.path.join(updater.backup_dir(), "_internal")
    ):
        try:
            with open(info, encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            pass
    return None


def kill_launcher():
    subprocess.run(
        ["taskkill", "/IM", EXE_NAME, "/F"],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def apply_tree(src, status):
    """Copia src sobre APP_DIR (sin tocar esta herramienta ni el desinstalador)."""
    status("Aplicando archivos...")
    src_internal = os.path.join(src, "_internal")
    dst_internal = os.path.join(APP_DIR, "_internal")
    if os.path.isdir(src_internal):
        if os.path.isdir(dst_internal):
            shutil.rmtree(dst_internal)
        shutil.copytree(src_internal, dst_internal)
    for name in os.listdir(src):
        if name == "_internal" or name.lower() == SELF_NAME.lower():
            continue
        full = os.path.join(src, name)
        if os.path.isfile(full):
            shutil.copy2(full, os.path.join(APP_DIR, name))


class RestoreApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Restauración de PureLauncher")
        self.root.geometry("520x430")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.releases = []
        self.busy = False
        self._build()
        threading.Thread(target=self._load_releases, daemon=True).start()

    # ------------------------------------------------------------------- ui

    def _build(self):
        tk.Label(self.root, text="Restauración de PureLauncher",
                 bg=BG, fg=FG, font=("Segoe UI", 15, "bold")).pack(pady=(18, 2))
        tk.Label(self.root,
                 text="Repara el launcher si una actualización falló o quedó corrupta.",
                 bg=BG, fg=DIM, font=("Segoe UI", 9)).pack()

        card = tk.Frame(self.root, bg=CARD, padx=16, pady=12)
        card.pack(fill="x", padx=22, pady=(16, 8))
        self.mode = tk.StringVar(value="github")

        bak = backup_info()
        state = "normal" if bak else "disabled"
        texto = (f"Copia de seguridad local  ({bak})" if bak
                 else "Copia de seguridad local  (no hay ninguna todavía)")
        tk.Radiobutton(card, text=texto, variable=self.mode, value="backup",
                       state=state, bg=CARD, fg=FG, selectcolor=BG,
                       activebackground=CARD, activeforeground=FG,
                       disabledforeground=DIM,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 8))
        if bak:
            self.mode.set("backup")

        tk.Radiobutton(card, text="Descargar una versión estable de GitHub:",
                       variable=self.mode, value="github",
                       bg=CARD, fg=FG, selectcolor=BG,
                       activebackground=CARD, activeforeground=FG,
                       font=("Segoe UI", 10)).pack(anchor="w")
        self.combo = ttk.Combobox(card, state="disabled", width=44)
        self.combo.pack(anchor="w", padx=(24, 0), pady=(6, 4))

        self.btn = tk.Button(self.root, text="RESTAURAR", command=self.start,
                             bg=GREEN, fg="white", activebackground="#37b24d",
                             activeforeground="white", relief="flat",
                             font=("Segoe UI", 12, "bold"), padx=30, pady=8,
                             cursor="hand2", state="disabled")
        self.btn.pack(pady=(14, 8))

        self.bar = ttk.Progressbar(self.root, length=440, mode="determinate")
        self.bar.pack(pady=(4, 4))
        self.status_lbl = tk.Label(self.root, text="Cargando versiones…",
                                   bg=BG, fg=DIM, font=("Segoe UI", 9))
        self.status_lbl.pack()

        tk.Label(self.root,
                 text=f"Instalación: {APP_DIR}",
                 bg=BG, fg="#5a6570", font=("Segoe UI", 8)).pack(side="bottom", pady=8)

    def status(self, text):
        self.root.after(0, lambda: self.status_lbl.config(text=text))

    def progress(self, done, total):
        def upd():
            if total:
                self.bar.config(mode="determinate", maximum=total, value=done)
            else:
                self.bar.config(mode="indeterminate")
        self.root.after(0, upd)

    # ---------------------------------------------------------------- carga

    def _load_releases(self):
        try:
            self.releases = list_releases()
            names = [
                f"{r['tag']}  —  {r['title']}  ({r['size'] / 1048576:.1f} MB)"
                + ("  [prerelease]" if r["prerelease"] else "")
                for r in self.releases
            ]

            def fill():
                self.combo.config(state="readonly", values=names)
                if names:
                    self.combo.current(0)
                self.btn.config(state="normal")
                self.status_lbl.config(
                    text=f"{len(names)} versiones disponibles. "
                         "La primera es la estable más reciente."
                )
            self.root.after(0, fill)
        except Exception as e:  # noqa: BLE001
            def fallback():
                if backup_info():
                    self.mode.set("backup")
                    self.btn.config(state="normal")
                    self.status_lbl.config(
                        text="Sin conexión con GitHub; puedes restaurar la copia local."
                    )
                else:
                    self.status_lbl.config(text=f"Error: {e}")
            self.root.after(0, fallback)

    # --------------------------------------------------------------- restaurar

    def start(self):
        if self.busy:
            return
        if not os.path.isdir(APP_DIR):
            messagebox.showerror(
                "PureLauncher no encontrado",
                f"No existe la instalación en:\n{APP_DIR}\n\n"
                "Instala PureLauncher primero con su instalador.",
            )
            return
        self.busy = True
        self.btn.config(state="disabled")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        try:
            self.status("Cerrando PureLauncher…")
            kill_launcher()
            if self.mode.get() == "backup":
                self.status("Restaurando copia de seguridad local…")
                apply_tree(updater.backup_dir(), self.status)
            else:
                rel = self.releases[self.combo.current()]
                self.status(f"Descargando {rel['tag']}…")
                zip_path = os.path.join(
                    os.environ.get("TEMP", "."), "purelauncher-restore.zip"
                )
                updater.download_zip(rel["url"], zip_path, self.progress)
                self.status("Verificando y extrayendo…")
                stage = updater.stage_zip(zip_path)
                apply_tree(stage, self.status)
                shutil.rmtree(stage, ignore_errors=True)
            self.progress(1, 1)
            self.status("¡Restaurado correctamente!")
            if messagebox.askyesno(
                "Restauración completada",
                "PureLauncher se restauró correctamente.\n¿Abrirlo ahora?",
            ):
                subprocess.Popen([os.path.join(APP_DIR, EXE_NAME)])
            self.root.after(0, self.root.destroy)
        except Exception as e:  # noqa: BLE001
            self.status("Error en la restauración.")
            self.root.after(0, lambda: messagebox.showerror(
                "Error", f"No se pudo restaurar:\n{e}"
            ))
            self.busy = False
            self.root.after(0, lambda: self.btn.config(state="normal"))


if __name__ == "__main__":
    RestoreApp().root.mainloop()
