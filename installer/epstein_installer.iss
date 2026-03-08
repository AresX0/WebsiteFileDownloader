; Inno Setup script to install EpsteinFilesDownloader
; Place this file in the repo under `installer\epstein_installer.iss` and compile with Inno Setup Compiler (ISCC.exe)
#define SrcDir "..\"

[Setup]
AppName=EpsteinFilesDownloader
AppVersion=2.1.1
AppId={{8E2F4A1B-3C5D-4E6F-A7B8-9C0D1E2F3A4B}
DefaultDirName={pf}\PlatypusFiles\WebsiteFileDownloader
DefaultGroupName=EpsteinFilesDownloader
Uninstallable=yes
CreateUninstallRegKey=yes
Compression=lzma
SolidCompression=yes
OutputDir=output
OutputBaseFilename=EpsteinFilesDownloader_Setup
PrivilegesRequired=admin
SetupIconFile={#SrcDir}logo.ico
; Overwrite pre-existing files silently — same AppId means upgrade in place
DisableDirPage=yes
DisableProgramGroupPage=yes
; Close running instances before installing so files are not locked
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Main application exe (PyInstaller one-file build)
Source: "{#SrcDir}dist\EpsteinDownloader.exe"; DestDir: "{app}"; Flags: ignoreversion
; Include any additional files you want installed (config defaults, assets, branding)
Source: "{#SrcDir}config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}queue_state.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SrcDir}logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}VERSION.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\EpsteinFilesDownloader"; Filename: "{app}\EpsteinDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"
Name: "{userdesktop}\EpsteinFilesDownloader"; Filename: "{app}\EpsteinDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\EpsteinDownloader.exe"; Description: "Launch EpsteinFilesDownloader"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"