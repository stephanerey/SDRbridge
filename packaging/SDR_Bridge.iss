#define MyAppName "SDRbridge"
#ifndef MyAppVersion
#define MyAppVersion "0.4.0"
#endif
#ifndef ReleaseDir
#define ReleaseDir "..\release-v0.4"
#endif
#define MyAppExeName "SDR_Bridge.exe"

[Setup]
AppId={{8E811417-B378-4B33-AF0F-91698DC5D028}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\SDRbridge
DefaultGroupName=SDRbridge
OutputDir={#ReleaseDir}\installer
OutputBaseFilename=SDRbridge_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\assets\branding\sdrbridge.ico
UninstallDisplayIcon={app}\SDR_Bridge\{#MyAppExeName}
LicenseFile=..\LICENSE
InfoBeforeFile=..\docs\HELP_FR.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "{#ReleaseDir}\SDR_Bridge\*"; DestDir: "{app}\SDR_Bridge"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\SDR_Bridge_Client\*"; DestDir: "{app}\SDR_Bridge_Client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\SDR_Bridge_Native_Client\*"; DestDir: "{app}\SDR_Bridge_Native_Client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\Connectors\*"; DestDir: "{app}\Connectors"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\CLIENT_SETUP.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion
Source: "{#ReleaseDir}\HELP_FR.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion
Source: "{#ReleaseDir}\HELP_EN.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion
Source: "{#ReleaseDir}\HARDWARE_COMPATIBILITY_FR.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion
Source: "{#ReleaseDir}\HARDWARE_COMPATIBILITY.md"; DestDir: "{app}\Documentation"; Flags: ignoreversion
Source: "{#ReleaseDir}\verification\GENERIC_SOAPY_VALIDATION_FR.md"; DestDir: "{app}\Documentation\verification"; Flags: ignoreversion
Source: "{#ReleaseDir}\verification\GENERIC_SOAPY_VALIDATION.md"; DestDir: "{app}\Documentation\verification"; Flags: ignoreversion
Source: "{#ReleaseDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\AUTHORS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\COPYRIGHT"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\config.soapy-sdrpp.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\config.native-sdrpp.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\start-sdrbridge.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SDRbridge"; Filename: "{app}\SDR_Bridge\{#MyAppExeName}"; Parameters: "--config ""{app}\config.soapy-sdrpp.json"""; WorkingDir: "{app}"; IconFilename: "{app}\SDR_Bridge\{#MyAppExeName}"; AppUserModelID: "SDRbridge.SDRbridge"
Name: "{group}\Client natif SDRbridge"; Filename: "{app}\SDR_Bridge_Native_Client\SDR_Bridge_Native_Client.exe"
Name: "{group}\Guide des clients"; Filename: "{app}\Documentation\CLIENT_SETUP.md"
Name: "{group}\Aide SDRbridge"; Filename: "{app}\Documentation\HELP_FR.md"
Name: "{autodesktop}\SDRbridge"; Filename: "{app}\SDR_Bridge\{#MyAppExeName}"; Parameters: "--config ""{app}\config.soapy-sdrpp.json"""; WorkingDir: "{app}"; IconFilename: "{app}\SDR_Bridge\{#MyAppExeName}"; AppUserModelID: "SDRbridge.SDRbridge"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Run]
Filename: "{app}\SDR_Bridge\{#MyAppExeName}"; Parameters: "--config ""{app}\config.soapy-sdrpp.json"""; WorkingDir: "{app}"; Description: "Lancer SDRbridge"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not FileExists(ExpandConstant('{pf}\SDRplay\API\x64\sdrplay_api.dll')) then
    MsgBox(
      'SDRplay receivers require the official SDRplay API/driver 3.15. ' +
      'You may continue for IQ files or another SDR, but install the official API before using an RSP.',
      mbInformation, MB_OK);
end;
