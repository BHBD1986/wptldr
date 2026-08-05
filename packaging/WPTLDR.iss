; Inno Setup script for the WP TLDR desktop app.
; Compile: ISCC.exe packaging\WPTLDR.iss /DMyAppVersion=1.0.0
; Requires the PyInstaller onedir build at dist\WPTLDR.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName "WP TLDR"
#define MyAppExeName "WPTLDR.exe"

[Setup]
AppId={{94F4494D-791D-4BC4-84C4-F6630351D3F7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=WP TLDR
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=WPTLDR-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Files]
Source: "..\dist\WPTLDR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
