"""Sistema de optimizacion de PureLauncher.

Dos vertientes:
- Juego: perfiles de flags JVM (G1GC afinado, estilo Aikar) segun nivel,
  RAM recomendada segun la memoria fisica del equipo y prioridad de proceso.
- Launcher: las optimizaciones de red/cache viven en mc_core (pool de
  conexiones keep-alive, cache del manifiesto, verificacion rapida) y las
  del ejecutable en build.bat (bytecode -OO y exclusion de modulos).
"""

import ctypes
import os

LEVELS = ("off", "balanced", "max")

# G1GC afinado para Minecraft (flags estilo Aikar, validas en Java 17-22).
_G1_BASE = [
    "-XX:+UseG1GC",
    "-XX:+ParallelRefProcEnabled",
    "-XX:MaxGCPauseMillis=200",
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+DisableExplicitGC",
    "-XX:G1NewSizePercent=30",
    "-XX:G1MaxNewSizePercent=40",
    "-XX:G1HeapRegionSize=8M",
    "-XX:G1ReservePercent=20",
    "-XX:G1HeapWastePercent=5",
    "-XX:G1MixedGCCountTarget=4",
    "-XX:InitiatingHeapOccupancyPercent=15",
    "-XX:G1MixedGCLiveThresholdPercent=90",
    "-XX:G1RSetUpdatingPauseTimePercent=5",
    "-XX:SurvivorRatio=32",
    "-XX:MaxTenuringThreshold=1",
    "-XX:+PerfDisableSharedMem",
]

# "max" reserva todo el heap al arrancar (menos fallos de pagina en juego,
# arranque algo mas lento) y compacta strings duplicadas.
_G1_MAX_EXTRA = [
    "-XX:+AlwaysPreTouch",
    "-XX:+UseStringDeduplication",
]


def system_ram_mb():
    """RAM fisica total del equipo en MB (0 si no se puede detectar)."""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.ullTotalPhys / (1024 * 1024))
    except Exception:  # noqa: BLE001
        return 0


def recommended_ram_mb():
    """Xmx recomendado: suficiente para el juego sin ahogar al sistema."""
    total = system_ram_mb()
    if total >= 30000:
        return 10240
    if total >= 15000:
        return 8192
    if total >= 11000:
        return 6144
    if total >= 7000:
        return 4096
    if total >= 5000:
        return 3072
    return 2048


def jvm_setup(level, ram_mb):
    """Devuelve (xms_mb, flags) para el nivel de optimizacion dado."""
    level = level if level in LEVELS else "balanced"
    if level == "off":
        return 512, []
    if level == "max":
        return int(ram_mb), _G1_BASE + _G1_MAX_EXTRA
    return min(1024, int(ram_mb)), list(_G1_BASE)
