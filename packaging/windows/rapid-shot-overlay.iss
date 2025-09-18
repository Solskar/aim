; Inno Setup script for Rapid Shot Heat Overlay

#ifndef MyAppName
#define MyAppName "Rapid Shot Heat Overlay"
#endif

#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif

#ifndef MyAppPublisher
#define MyAppPublisher "AIM"
#endif

#ifndef MyAppExeName
#define MyAppExeName "rapid-shot-overlay.exe"
#endif

#ifndef DistDir
#define DistDir "..\\..\\dist\\rapid-shot-overlay"
#endif

#ifndef OutputDir
#define OutputDir "..\\..\\dist\\installer"
#endif

[Setup]
AppId={{1F6F1C05-CCCB-4ED9-89DD-1E6FD7748C8D}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Rapid Shot Heat Overlay
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=RapidShotHeatOverlaySetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
