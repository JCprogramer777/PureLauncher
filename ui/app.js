/* PureLauncher UI — se comunica con Python via pywebview (window.pywebview.api) */

const $ = (id) => document.getElementById(id);

const UI = {
  state: null,
  remoteVersions: [],
  launching: false,
  pendingUpdate: null,

  // ---------------------------------------------------------------- eventos

  onProgress(p) {
    const wrap = $("progress-wrap");
    wrap.classList.remove("hidden");
    $("progress-msg").textContent = p.msg;
    const bar = $("progress-bar");
    if (p.total > 1) {
      bar.classList.remove("indeterminate");
      bar.style.width = ((p.done / p.total) * 100).toFixed(1) + "%";
      $("progress-count").textContent = `${p.done} / ${p.total}`;
    } else {
      bar.classList.add("indeterminate");
      $("progress-count").textContent = "";
    }
  },

  onEvent(name, data) {
    switch (name) {
      case "gameStarted":
        this.launching = false;
        this.hideProgress();
        this.setPlayState("running");
        toast("¡A jugar! El juego se está abriendo…", true);
        break;
      case "gameExited":
        this.setPlayState("idle");
        this.hideProgress();
        if (data.code !== 0 && data.code !== null) {
          $("log-title").textContent = `El juego se cerró con errores (código ${data.code})`;
          $("log-body").textContent = data.log || "(sin registro)";
          show("modal-log");
        }
        break;
      case "launchError":
        this.launching = false;
        this.setPlayState("idle");
        this.hideProgress();
        toast("Error al lanzar: " + data.error);
        break;
      case "importDone":
        this.hideProgress();
        if (data.ok) {
          hide("modal-import");
          toast(`Versión “${data.id}” importada correctamente.`, true);
          this.refresh().then(() => {
            $("version-select").value = data.id;
          });
        } else {
          toast("Error al importar: " + data.error);
          $("import-confirm").disabled = false;
        }
        break;
      case "installDone":
        this.hideProgress();
        if (data.ok) {
          toast(`Versión ${data.id} descargada y lista para jugar.`, true);
          this.refresh().then(() => {
            $("version-select").value = data.id;
            this.updatePlaySub();
            this.setPlayState("idle");
          });
        } else {
          toast("Error al descargar: " + data.error);
        }
        break;
      case "updateAvailable":
        this.pendingUpdate = data;
        showUpdateModal(data);
        break;
      case "updateProgress": {
        show("update-progress");
        const bar = $("update-progress-bar");
        if (data.total > 0) {
          bar.classList.remove("indeterminate");
          bar.style.width = ((data.done / data.total) * 100).toFixed(1) + "%";
          $("update-progress-count").textContent =
            (data.done / 1048576).toFixed(1) + " / " + (data.total / 1048576).toFixed(1) + " MB";
        } else {
          bar.classList.add("indeterminate");
        }
        break;
      }
      case "updateRestarting":
        $("update-progress-msg").textContent = "Instalando y reiniciando…";
        break;
      case "updateError":
        hide("update-progress");
        $("update-now").disabled = false;
        toast("Error al actualizar: " + data.error);
        break;
    }
  },

  hideProgress() {
    $("progress-wrap").classList.add("hidden");
  },

  setPlayState(mode) {
    const btn = $("play-btn");
    const label = btn.querySelector(".play-label");
    btn.classList.toggle("busy", mode !== "idle");
    if (mode === "running") {
      label.textContent = "JUGANDO";
      $("play-sub").textContent = "clic para cerrar el juego";
      btn.disabled = false;
    } else if (mode === "preparing") {
      label.textContent = "PREPARANDO…";
      $("play-sub").textContent = "";
      btn.disabled = true;
    } else {
      label.textContent = "JUGAR";
      btn.disabled = !$("version-select").value;
      this.updatePlaySub();
    }
  },

  updatePlaySub() {
    const v = $("version-select").value;
    $("play-sub").textContent = v ? "Minecraft " + v : "";
  },

  // ------------------------------------------------------------------ estado

  async refresh() {
    this.state = await pywebview.api.get_state();
    const cfg = this.state.config;

    // barra de jugar
    $("username").value = cfg.username;
    const sel = $("version-select");
    sel.innerHTML = "";
    if (this.state.installed.length === 0) {
      sel.innerHTML = '<option value="">— importa una versión —</option>';
    } else {
      for (const v of this.state.installed) {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = v.id + (v.hasJar ? "" : "  (jar pendiente)");
        sel.appendChild(opt);
      }
      sel.value = this.state.installed.some((v) => v.id === cfg.last_version)
        ? cfg.last_version
        : this.state.installed[0].id;
    }
    if (this.state.running) this.setPlayState("running");
    else this.setPlayState("idle");

    // instalaciones
    const list = $("install-list");
    list.innerHTML = "";
    $("install-empty").classList.toggle("hidden", this.state.installed.length > 0);
    for (const v of this.state.installed) {
      const li = document.createElement("li");
      li.className = "install-item";
      li.innerHTML = `
        <div class="cube"></div>
        <div class="info">
          <div class="name"></div>
          <div class="meta ${v.hasJar ? "" : "warn"}">${
            v.hasJar
              ? "Jar propio instalado"
              : "Sin jar propio — se descargará el oficial al jugar"
          }</div>
        </div>
        <button class="btn primary small">Jugar</button>`;
      li.querySelector(".name").textContent = v.id;
      li.querySelector("button").onclick = () => {
        $("version-select").value = v.id;
        this.updatePlaySub();
        switchPage("play");
        $("play-btn").click();
      };
      list.appendChild(li);
    }

    // ajustes
    $("ram-slider").value = cfg.ram_mb;
    updateRamLabel();
    $("opt-level").value = cfg.opt_level || "balanced";
    $("high-priority").checked = cfg.high_priority !== false;
    $("block-services").checked = cfg.block_services;
    $("show-snapshots").checked = cfg.show_snapshots;
    $("java-path").value = cfg.java_path || "";
    $("java-path").placeholder = this.state.javaDetected || "auto";
    $("game-dir").value = cfg.game_dir;
    $("extra-jvm").value = cfg.extra_jvm || "";
    $("app-version").textContent =
      this.state.appVersion + (this.state.isInstalled ? "" : " (desarrollo)");
    $("side-version").textContent = "v" + this.state.appVersion;
  },

  async loadRemoteVersions() {
    const res = await pywebview.api.get_remote_versions();
    if (!res.ok) {
      toast("No se pudo obtener la lista de versiones: " + res.error);
      return;
    }
    this.remoteVersions = res.versions;
    renderBaseList("");
  },
};

// ------------------------------------------------------------------ helpers

function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }

let toastTimer = null;
function toast(msg, ok = false) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("ok", ok);
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), ok ? 4000 : 8000);
}

function switchPage(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.page === name)
  );
  document.querySelectorAll(".page").forEach((p) =>
    p.classList.toggle("active", p.id === "page-" + name)
  );
  // La biblioteca de skins solo se (re)dibuja al entrar en su pestaña.
  if (name === "skins" && window.pywebview && !Skins.loaded) {
    Skins.loaded = true;
    Skins.refreshList();
  }
}

function updateRamLabel() {
  const gb = ($("ram-slider").value / 1024).toFixed(1);
  $("ram-value").textContent = gb + " GB";
}

function renderVersionList(listEl, filter, onDone) {
  listEl.innerHTML = "";
  const f = filter.trim().toLowerCase();
  const matches = UI.remoteVersions.filter((v) => v.id.toLowerCase().includes(f));
  for (const v of matches.slice(0, 200)) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = `${v.id}   (${v.type})`;
    listEl.appendChild(opt);
  }
  if (matches.length === 1) listEl.selectedIndex = 0;
  if (onDone) onDone();
}

function renderBaseList(filter) {
  renderVersionList($("base-version"), filter, validateImport);
}

function renderDlList(filter) {
  renderVersionList($("dl-version"), filter, () => {
    $("dl-confirm").disabled = !$("dl-version").value;
  });
}

function showUpdateModal(info) {
  $("update-title").textContent = `Actualización ${info.version} disponible`;
  $("update-sub").textContent =
    `Tienes la ${UI.state ? UI.state.appVersion : "…"} y hay una nueva versión ` +
    `(${info.assetName}, ${(info.size / 1048576).toFixed(1)} MB).`;
  const notes = $("update-notes");
  if (info.notes) {
    notes.textContent = info.notes;
    show("update-notes");
  } else {
    hide("update-notes");
  }
  hide("update-progress");
  $("update-later").disabled = false;
  $("update-now").disabled = !(UI.state && UI.state.isInstalled);
  $("update-now").textContent = UI.state && UI.state.isInstalled
    ? "Actualizar y reiniciar"
    : "Solo en la versión instalada";
  show("modal-update");
}

function validateImport() {
  $("import-confirm").disabled = !($("jar-path").value && $("base-version").value);
}

// ------------------------------------------------------------------- skins

const Skins = {
  pendingCanvas: null, // skin normalizada 64x64 lista para guardar
  loaded: false,

  // Convierte cualquier fuente a un canvas 64x64 (incluye skins antiguas 64x32).
  async normalize(dataUrl) {
    const img = new Image();
    await new Promise((res, rej) => {
      img.onload = res;
      img.onerror = () => rej(new Error("No se pudo leer la imagen."));
      img.src = dataUrl;
    });
    const ratio = img.width / img.height;
    if (img.width < 64 || (ratio !== 1 && ratio !== 2)) {
      throw new Error(`Tamaño no válido (${img.width}×${img.height}). ` +
                      "Debe ser 64×64, 64×32 o un múltiplo HD.");
    }
    const c = document.createElement("canvas");
    c.width = 64; c.height = 64;
    const g = c.getContext("2d");
    g.imageSmoothingEnabled = false;
    const legacy = ratio === 2;
    g.drawImage(img, 0, 0, img.width, img.height, 0, 0, 64, legacy ? 32 : 64);
    if (legacy) this._convertLegacy(g);
    return c;
  },

  // Sintetiza brazo/pierna izquierdos (espejados) para skins 64x32.
  _convertLegacy(g) {
    const flip = (sx, sy, w, h, dx, dy) => {
      const t = document.createElement("canvas");
      t.width = w; t.height = h;
      const tg = t.getContext("2d");
      tg.translate(w, 0); tg.scale(-1, 1);
      tg.drawImage(g.canvas, sx, sy, w, h, 0, 0, w, h);
      g.drawImage(t, dx, dy);
    };
    // pierna izquierda desde la derecha
    flip(4, 16, 4, 4, 20, 48);   // arriba
    flip(8, 16, 4, 4, 24, 48);   // abajo
    flip(8, 20, 4, 12, 16, 52);  // interior
    flip(4, 20, 4, 12, 20, 52);  // frente
    flip(0, 20, 4, 12, 24, 52);  // exterior
    flip(12, 20, 4, 12, 28, 52); // detrás
    // brazo izquierdo desde el derecho
    flip(44, 16, 4, 4, 36, 48);
    flip(48, 16, 4, 4, 40, 48);
    flip(48, 20, 4, 12, 32, 52);
    flip(44, 20, 4, 12, 36, 52);
    flip(40, 20, 4, 12, 40, 52);
    flip(52, 20, 4, 12, 44, 52);
  },

  // Dibuja la vista frontal (cabeza+cuerpo+brazos+piernas, con capas).
  render(canvas, skin, slim) {
    const s = canvas.width / 16;
    const g = canvas.getContext("2d");
    g.imageSmoothingEnabled = false;
    g.clearRect(0, 0, canvas.width, canvas.height);
    const aw = slim ? 3 : 4;
    const d = (sx, sy, w, h, dx, dy) =>
      g.drawImage(skin, sx, sy, w, h, dx * s, dy * s, w * s, h * s);
    d(4, 20, 4, 12, 4, 20);            // pierna derecha
    d(20, 52, 4, 12, 8, 20);           // pierna izquierda
    d(20, 20, 8, 12, 4, 8);            // cuerpo
    d(44, 20, aw, 12, 4 - aw, 8);      // brazo derecho
    d(36, 52, aw, 12, 12, 8);          // brazo izquierdo
    d(8, 8, 8, 8, 4, 0);               // cabeza
    // capas exteriores
    d(4, 36, 4, 12, 4, 20);
    d(4, 52, 4, 12, 8, 20);
    d(20, 36, 8, 12, 4, 8);
    d(44, 36, aw, 12, 4 - aw, 8);
    d(52, 52, aw, 12, 12, 8);
    d(40, 8, 8, 8, 4, 0);              // gorro
  },

  async refreshList() {
    const list = await pywebview.api.list_skins();
    const grid = $("skin-list");
    grid.innerHTML = "";
    $("skin-empty").classList.toggle("hidden", list.length > 0);
    $("skin-none-btn").classList.toggle(
      "active-ghost", !list.some((s) => s.active)
    );
    for (const s of list) {
      const li = document.createElement("li");
      li.className = "skin-card" + (s.active ? " active" : "");
      li.innerHTML = `
        <canvas width="96" height="192"></canvas>
        <div class="skin-name"></div>
        <div class="skin-variant">${s.variant === "slim" ? "Slim" : "Clásico"}</div>
        <div class="skin-actions">
          <button class="btn primary small use-btn">${s.active ? "✓ En uso" : "Usar"}</button>
          <button class="btn ghost small del-btn" title="Eliminar">🗑</button>
        </div>`;
      li.querySelector(".skin-name").textContent = s.name;
      const img = new Image();
      img.onload = () =>
        this.render(li.querySelector("canvas"), img, s.variant === "slim");
      img.src = s.dataUrl;
      li.querySelector(".use-btn").onclick = async () => {
        if (s.active) return;
        const r = await pywebview.api.set_active_skin(s.id);
        if (!r.ok) { toast(r.error); return; }
        toast(`Skin “${s.name}” activada. Se aplicará al lanzar el juego.`, true);
        this.refreshList();
      };
      li.querySelector(".del-btn").onclick = async () => {
        await pywebview.api.delete_skin(s.id);
        toast(`Skin “${s.name}” eliminada.`, true);
        this.refreshList();
      };
      grid.appendChild(li);
    }
  },

  async loadSource(kind, value) {
    $("skin-status").textContent = "Cargando…";
    const res = await pywebview.api.fetch_skin_source(kind, value);
    if (!res.ok) {
      $("skin-status").textContent = "Error: " + res.error;
      return;
    }
    try {
      this.pendingCanvas = await this.normalize(res.b64);
    } catch (e) {
      this.pendingCanvas = null;
      $("skin-save").disabled = true;
      $("skin-status").textContent = "Error: " + e.message;
      return;
    }
    this.updatePreview();
    $("skin-save").disabled = false;
    $("skin-status").textContent = "Skin lista. Ponle nombre y guárdala.";
  },

  updatePreview() {
    if (!this.pendingCanvas) return;
    const slim =
      document.querySelector('input[name="skin-variant"]:checked').value === "slim";
    this.render($("skin-preview"), this.pendingCanvas, slim);
  },
};

// ------------------------------------------------------------------- wiring

function wire() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => switchPage(t.dataset.page);
  });

  $("version-select").onchange = () => {
    UI.updatePlaySub();
    UI.setPlayState("idle");
  };

  $("play-btn").onclick = async () => {
    if (UI.state && UI.state.running) {
      await pywebview.api.kill_game();
      return;
    }
    const version = $("version-select").value;
    if (!version || UI.launching) return;
    UI.launching = true;
    UI.setPlayState("preparing");
    const res = await pywebview.api.launch(version, $("username").value);
    if (!res.ok) {
      UI.launching = false;
      UI.setPlayState("idle");
      toast(res.error);
    }
  };

  // importar
  $("import-btn").onclick = async () => {
    $("jar-path").value = "";
    $("install-name").value = "";
    $("base-search").value = "";
    show("modal-import");
    if (UI.remoteVersions.length === 0) await UI.loadRemoteVersions();
    else renderBaseList("");
  };
  $("import-cancel").onclick = () => hide("modal-import");
  $("pick-jar-btn").onclick = async () => {
    const p = await pywebview.api.pick_jar();
    if (p) $("jar-path").value = p;
    validateImport();
  };
  $("base-search").oninput = () => renderBaseList($("base-search").value);
  $("base-version").onchange = validateImport;
  $("import-confirm").onclick = async () => {
    $("import-confirm").disabled = true;
    await pywebview.api.import_jar(
      $("jar-path").value,
      $("base-version").value,
      $("install-name").value.trim()
    );
  };

  $("open-dir-btn").onclick = () => pywebview.api.open_game_dir();

  // descargar versión oficial
  $("download-btn").onclick = async () => {
    $("dl-search").value = "";
    show("modal-download");
    if (UI.remoteVersions.length === 0) await UI.loadRemoteVersions();
    renderDlList("");
  };
  $("dl-cancel").onclick = () => hide("modal-download");
  $("dl-search").oninput = () => renderDlList($("dl-search").value);
  $("dl-version").onchange = () => {
    $("dl-confirm").disabled = !$("dl-version").value;
  };
  $("dl-version").ondblclick = () => $("dl-confirm").click();
  $("dl-confirm").onclick = async () => {
    const vid = $("dl-version").value;
    if (!vid) return;
    hide("modal-download");
    const res = await pywebview.api.download_vanilla(vid);
    if (!res.ok) toast(res.error);
  };

  // actualizaciones
  $("check-updates-btn").onclick = async () => {
    $("check-updates-btn").disabled = true;
    const res = await pywebview.api.check_updates();
    $("check-updates-btn").disabled = false;
    if (!res.ok) toast(res.error);
    else if (!res.update) toast(`Estás al día (versión ${res.current}).`, true);
    else {
      UI.pendingUpdate = res.update;
      showUpdateModal(res.update);
    }
  };
  $("update-later").onclick = () => hide("modal-update");
  $("update-now").onclick = async () => {
    $("update-now").disabled = true;
    $("update-later").disabled = true;
    show("update-progress");
    const res = await pywebview.api.apply_update();
    if (!res.ok) {
      toast(res.error);
      $("update-now").disabled = false;
      $("update-later").disabled = false;
      hide("update-progress");
    }
  };

  // ajustes
  $("ram-slider").oninput = updateRamLabel;
  $("ram-auto-btn").onclick = () => {
    if (!UI.state || !UI.state.recommendedRamMb) return;
    $("ram-slider").value = UI.state.recommendedRamMb;
    updateRamLabel();
    const total = UI.state.systemRamMb;
    toast(
      `RAM ajustada a ${(UI.state.recommendedRamMb / 1024).toFixed(1)} GB` +
      (total ? ` (tu equipo tiene ${(total / 1024).toFixed(0)} GB)` : ""),
      true
    );
  };
  $("pick-java-btn").onclick = async () => {
    const p = await pywebview.api.pick_java();
    if (p) $("java-path").value = p;
  };
  $("pick-dir-btn").onclick = async () => {
    const p = await pywebview.api.pick_folder();
    if (p) $("game-dir").value = p;
  };
  $("save-settings-btn").onclick = async () => {
    await pywebview.api.save_settings({
      ram_mb: parseInt($("ram-slider").value, 10),
      opt_level: $("opt-level").value,
      high_priority: $("high-priority").checked,
      block_services: $("block-services").checked,
      show_snapshots: $("show-snapshots").checked,
      java_path: $("java-path").value.trim(),
      game_dir: $("game-dir").value.trim(),
      extra_jvm: $("extra-jvm").value.trim(),
    });
    UI.remoteVersions = []; // por si cambió show_snapshots
    $("save-note").textContent = "Guardado ✓";
    setTimeout(() => ($("save-note").textContent = ""), 2500);
    UI.refresh();
  };

  $("username").onchange = () => {
    pywebview.api.save_settings({ username: $("username").value.trim() });
  };

  $("log-close").onclick = () => hide("modal-log");

  // skins
  $("skin-import-btn").onclick = () => {
    Skins.pendingCanvas = null;
    $("skin-name").value = "";
    $("skin-url").value = "";
    $("skin-save").disabled = true;
    $("skin-status").textContent = "Sin skin cargada.";
    const g = $("skin-preview").getContext("2d");
    g.clearRect(0, 0, 96, 192);
    show("modal-skin");
  };
  $("skin-cancel").onclick = () => hide("modal-skin");
  $("skin-pick-file").onclick = async () => {
    const p = await pywebview.api.pick_skin_file();
    if (!p) return;
    if (!$("skin-name").value) {
      $("skin-name").value = p.split(/[\\/]/).pop().replace(/\.png$/i, "");
    }
    Skins.loadSource("file", p);
  };
  $("skin-load-url").onclick = () => {
    const url = $("skin-url").value.trim();
    if (url) Skins.loadSource("url", url);
  };
  $("skin-url").onkeydown = (e) => {
    if (e.key === "Enter") $("skin-load-url").click();
  };
  document.querySelectorAll('input[name="skin-variant"]').forEach((r) => {
    r.onchange = () => Skins.updatePreview();
  });
  $("skin-save").onclick = async () => {
    if (!Skins.pendingCanvas) return;
    const variant =
      document.querySelector('input[name="skin-variant"]:checked').value;
    const res = await pywebview.api.save_skin(
      $("skin-name").value.trim(),
      variant,
      Skins.pendingCanvas.toDataURL("image/png")
    );
    if (!res.ok) { toast(res.error); return; }
    hide("modal-skin");
    toast("Skin guardada en la biblioteca.", true);
    Skins.refreshList();
  };
  $("skin-none-btn").onclick = async () => {
    await pywebview.api.set_active_skin(null);
    toast("Skin desactivada: volverás a la skin por defecto.", true);
    Skins.refreshList();
  };
}

window.addEventListener("pywebviewready", () => {
  wire();
  UI.refresh();
});

// Fallback por si el evento ya se disparó antes de cargar el script.
document.addEventListener("DOMContentLoaded", () => {
  if (window.pywebview && window.pywebview.api) {
    wire();
    UI.refresh();
  }
});
