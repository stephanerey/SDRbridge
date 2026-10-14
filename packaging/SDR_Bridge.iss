#define MyAppName "SDRbridge"
#define MyAppVersion "0.3.0"
#define MyAppExeName "SDR_Bridge.exe"

[Setup]
AppId={{8E811417-B378-4B33-AF0F-91698DC5D028}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\SDRbridge
DefaultGroupName=SDRbridge
OutputDir=..\release-v0.3\installer
OutputBaseFilename=SDRbridge_Setup_0.3.0
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\SDR_Bridge\{#MyAppExeName}

[Files]
Source: "..\release-v0.3\SDR_Bridge\*"; DestDir: "{app}\SDR_Bridge"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release-v0.3\SDR_Bridge_Client\*"; DestDir: "{app}\SDR_Bridge_Client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release-v0.3\SDR_Bridge_Native_Client\*"; DestDir: "{app}\SDR_Bridge_Native_Client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release-v0.3\Connectors\*"; DestDir: "{app}\Connectors"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release-v0.3\CLIENT_SETUP.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion

[Icons]
Name: "{group}\SDRbridge"; Filename: "{app}\SDR_Bridge\{#MyAppExeName}"
Name: "{group}\Client natif SDRbridge"; Filename: "{app}\SDR_Bridge_Native_Client\SDR_Bridge_Native_Client.exe"
Name: "{group}\Guide des clients"; Filename: "{app}\Documentation\CLIENT_SETUP.md"
Name: "{autodesktop}\SDRbridge"; Filename: "{app}\SDR_Bridge\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Run]
Filename: "{app}\SDR_Bridge\{#MyAppExeName}"; Description: "Lancer SDRbridge"; Flags: nowait postinstall skipifsilent
