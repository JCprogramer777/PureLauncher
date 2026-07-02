"""Genera los archivos de informacion de version (VSVersionInfo) para los exes.

Los exes sin metadatos (empresa, producto, copyright) son un disparador
clasico de falsos positivos en antivirus. Ejecutar antes de PyInstaller.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import updater  # noqa: E402

COMPANY = "Pure Studios"
TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vers},
    prodvers={vers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040a04b0', [
        StringStruct('CompanyName', '{company}'),
        StringStruct('FileDescription', '{desc}'),
        StringStruct('FileVersion', '{ver4}'),
        StringStruct('InternalName', '{internal}'),
        StringStruct('LegalCopyright', '\\xa9 {company}'),
        StringStruct('OriginalFilename', '{orig}'),
        StringStruct('ProductName', 'PureLauncher'),
        StringStruct('ProductVersion', '{ver4}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1034, 1200])])
  ]
)
"""


def main():
    nums = [int(n) for n in updater.APP_VERSION.split(".")]
    while len(nums) < 4:
        nums.append(0)
    vers = tuple(nums[:4])
    ver4 = ".".join(str(n) for n in vers)
    targets = [
        ("version_launcher.txt", "PureLauncher - Launcher de Minecraft",
         "PureLauncher", "PureLauncher.exe"),
        ("version_restore.txt", "Restauracion de PureLauncher",
         "Restaurar", "Restaurar.exe"),
    ]
    for fname, desc, internal, orig in targets:
        path = os.path.join(ROOT, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(TEMPLATE.format(vers=vers, ver4=ver4, company=COMPANY,
                                    desc=desc, internal=internal, orig=orig))
        print("generado:", fname)


if __name__ == "__main__":
    main()
