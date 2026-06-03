; Inno Setup script — YouTube Downloader Pro
; בונה קובץ התקנה יחיד )Setup.exe( שאורז את ה-exe, יוצר קיצורי דרך, ומאפשר הסרה.
; דורש Inno Setup 6:  winget install JRSoftware.InnoSetup

#define MyAppName "YouTube Downloader Pro"
#define MyAppVersion "2.0"
#define MyAppPublisher "Nahorai"
#define MyAppExeName "YouTube Downloader Pro.exe"

[Setup]
AppId={{8F3C2A91-7B4D-4E61-9C2A-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\YouTube Downloader Pro
DefaultGroupName=YouTube Downloader Pro
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=YouTubeDownloaderPro_Setup_v{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; ה-exe היחיד )onefile( שכולל את כל התלויות, ffmpeg והאייקון
Source: "dist\YouTube Downloader Pro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
