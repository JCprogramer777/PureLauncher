; Instalador de PureLauncher (Inno Setup)
; Compilar con: ISCC.exe installer.iss  ->  installer\PureLauncher-Setup-1.0.exe

#define MyAppName "PureLauncher"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
#define MyAppExeName "PureLauncher.exe"

[Setup]
AppId={{7C2D9A41-6B8E-4F5A-9D3C-PURELAUNCH01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Pure Studios
VersionInfoCompany=Pure Studios
VersionInfoProductName=PureLauncher
VersionInfoVersion={#MyAppVersion}
VersionInfoCopyright=(c) Pure Studios
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
; Instalacion por usuario: no requiere permisos de administrador.
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=PureLauncher-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\PureLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Restaurar\*"; DestDir: "{app}\restore-tool"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Restaurar {#MyAppName}"; Filename: "{app}\restore-tool\Restaurar.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
