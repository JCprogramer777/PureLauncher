# PureLauncher

Launcher de Minecraft: Java Edition **ligero, offline y sin telemetría**, pensado para
usar tu propio `.jar` (de tu copia comprada).

## Instalación en cualquier equipo

Ejecuta **`installer\PureLauncher-Setup-1.0.exe`**: instala la app (por usuario, sin
permisos de administrador, ~35 MB) con acceso directo en el menú Inicio y opcionalmente
en el escritorio. El equipo de destino **no necesita Python**, solo Java para el juego.

Para regenerar el instalador tras cambiar el código: `build.bat`
(requiere `pip install pywebview pillow pyinstaller` + Inno Setup).

## Sistema de actualización (GitHub Releases)

El launcher puede actualizarse solo desde un repositorio de GitHub:

1. **Repositorio**: por defecto apunta a
   [`JCprogramer777/PureLauncher`](https://github.com/JCprogramer777/PureLauncher)
   (cambiable en *Ajustes → Actualizaciones*, formato `usuario/repositorio`).
2. **Publica una versión nueva**:
   - Sube la versión en `updater.py` (`APP_VERSION = "1.2.0"`).
   - Ejecuta `build.bat` → genera `installer\PureLauncher-Update-1.2.0.zip`.
   - Crea la release con ese zip como asset:
     `gh release create v1.2.0 "installer\PureLauncher-Update-1.2.0.zip" --title "PureLauncher 1.2.0" --notes "cambios..."`
     (o desde la web de GitHub: *Releases → New release*, tag `v1.2.0`, adjunta el zip).
3. **En los equipos**: el launcher comprueba la última release al arrancar (y con el
   botón *Buscar*). Si el tag es mayor que la versión instalada, muestra las notas del
   cambio y, al aceptar, descarga el zip con barra de progreso, verifica su integridad,
   espera a que la app cierre, reemplaza los archivos y la relanza automáticamente.

Notas: la actualización automática solo aplica en la versión instalada (.exe); el tag
debe ser numérico (`v1.2.0`); el zip debe contener el contenido de `dist\PureLauncher`
(lo hace `build.bat` solo).

## Descargar versiones oficiales

En *Instalaciones → “Descargar versión”* puedes bajar cualquier versión del manifiesto
oficial (`piston-meta.mojang.com`): releases, snapshots (activables en Ajustes), betas y
alphas. Se descarga completa (jar + librerías + assets) y queda lista para jugar offline.

## Cómo usarlo

1. Abre **PureLauncher** (o en desarrollo: `PureLauncher.bat` / `pythonw main.py`).
2. Pestaña **Instalaciones → “+ Importar mi .jar”**: elige tu `.jar`, marca qué versión
   es (ej. `1.21.4`) e importa.
3. En **Jugar**: escribe tu nombre, elige la versión y pulsa **JUGAR**.

La primera vez descargará las librerías y recursos (sonidos, texturas, idiomas) de esa
versión **desde los CDN oficiales de Mojang** — es inevitable, el juego no arranca sin
ellos — pero sin iniciar sesión ni enviar ningún dato tuyo. Después de eso, todo queda
en caché y puedes jugar sin conexión.

## Privacidad

- El launcher **no tiene cuentas, analítica ni rastreo de ningún tipo**.
- Solo conecta a: `piston-meta.mojang.com` (lista de versiones),
  `libraries.minecraft.net` (librerías) y `resources.download.minecraft.net` (assets).
  Solo descargas, nunca subidas.
- El juego se lanza en **modo offline** (sin token de sesión) y, con el ajuste
  *“Bloquear servicios de Mojang”* (activado por defecto), se redirigen los hosts de
  autenticación/sesión/telemetría del juego a una dirección inválida: aunque el juego
  intente enviar telemetría, no puede.
- Nota: en modo offline no se puede entrar a servidores con `online-mode=true` ni se
  cargan skins de otros jugadores. Tus mundos, mods y servidores offline funcionan igual.

## Requisitos

- Windows + Python 3.10+ (con `pywebview`: `pip install pywebview`)
- Java (para versiones 1.20.5+ se necesita Java 21+; para versiones ≤1.16 suele ir
  mejor Java 8 — puedes fijar la ruta de Java en Ajustes).

## Estructura

- `main.py` — ventana y API de la interfaz (pywebview / WebView2)
- `mc_core.py` — descargas, resolución de versiones y comando de lanzamiento
- `ui/` — interfaz (HTML/CSS/JS + logo SVG, sin recursos externos)
- `assets/build_assets.py` — genera el logo (SVG/PNG) y el icono `.ico`
- `installer.iss` + `build.bat` — empaquetado del exe e instalador
- Ajustes del usuario: `%APPDATA%\PureLauncher\config.json`
- Carpeta del juego por defecto: `%APPDATA%\.minecraft` (compatible con tus mundos actuales)

## Mods

Los perfiles de Forge/Fabric instalados en la carpeta del juego (con `inheritsFrom`)
también se detectan y se pueden lanzar desde la pestaña de versiones.
