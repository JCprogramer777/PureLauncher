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

1. **Repositorio**: fijo en el código
   ([`JCprogramer777/PureLauncher`](https://github.com/JCprogramer777/PureLauncher),
   constante `UPDATE_REPO` en `updater.py`). El usuario no puede cambiarlo; solo
   dispone del botón *Buscar actualizaciones* en Ajustes.
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

## Skins

Pestaña **Skins**: biblioteca con vista previa de tus skins. Importa por **archivo PNG**
o por **enlace directo**, ponles nombre y elige el modelo (clásico o slim). Acepta
skins 64×64 y el formato antiguo 64×32 (se convierte solo). La skin activa se aplica
mediante un resource pack (`PureSkin`) que el launcher genera y activa automáticamente
al lanzar el juego — funciona **100% offline**. Nota: en modo offline el modelo
(brazos anchos/slim) en partida lo asigna el juego según tu nombre; la textura se ve
igual en ambos casos.

## Restauración (actualizaciones corruptas)

Antes de aplicar cualquier actualización, el launcher guarda una **copia de seguridad
automática** de la versión actual. Si una actualización sale mal o el launcher deja de
arrancar, abre **"Restaurar PureLauncher"** desde el menú Inicio (`Restaurar.exe`, una
herramienta independiente que no depende de los archivos del launcher) y elige:

- **Copia de seguridad local** — vuelve a la versión anterior al instante, sin conexión.
- **Descargar una versión estable de GitHub** — lista todas las releases publicadas y
  reinstala la que elijas (la más reciente u otra anterior).

La herramienta cierra el launcher si está abierto, aplica los archivos, respeta el
desinstalador y ofrece relanzar la app al terminar.

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

## Antivirus y firma

Los binarios van **firmados por "Pure Studios"** (certificado propio) con sello de
tiempo de DigiCert, e incluyen metadatos completos de versión (empresa, producto,
copyright) — todo esto reduce mucho los falsos positivos heurísticos de los antivirus,
habituales en apps empaquetadas con PyInstaller. La herramienta de restauración dejó
de ser *onefile* (el formato que más falsos positivos genera).

Si algún antivirus aún lo marca: es un falso positivo (el código es público en este
repositorio); añade una exclusión o repórtalo como falso positivo al fabricante.
Al ser un certificado autofirmado, Windows puede seguir mostrando "editor desconocido"
en SmartScreen — eliminarlo del todo requiere un certificado de pago de una CA (OV/EV).

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
