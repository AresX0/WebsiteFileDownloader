; Inno Setup script to install EpsteinFilesDownloader
; Place this file in the repo under `installer\epstein_installer.iss` and compile with Inno Setup Compiler (ISCC.exe)
[Setup]
AppName=EpsteinFilesDownloader
AppVersion=1.0.0
DefaultDirName={pf}\PlatypusFiles\WebsiteFileDownloader
DefaultGroupName=EpsteinFilesDownloader
Uninstallable=yes
CreateUninstallRegKey=yes
Compression=lzma
SolidCompression=yes
OutputDir=output
OutputBaseFilename=EpsteinFilesDownloader_Setup
PrivilegesRequired=admin
; Overwrite pre-existing files silently
DisableDirPage=yes
DisableProgramGroupPage=yes

[Files]
; Main application exe
Source: "{#GetSourceFilePath('dist\\EpsteinDownloader.exe')}"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs overwritealways
; Include any additional files you want installed (config defaults, assets)
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion overwritealways
Source: "queue_state.json"; DestDir: "{app}"; Flags: ignoreversion overwritealways
Source: "assets\\*"; DestDir: "{app}\\assets"; Flags: recursesubdirs createallsubdirs ignoreversion overwritealways

[Icons]
Name: "{group}\EpsteinFilesDownloader"; Filename: "{app}\EpsteinDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\JosephThePlatypus.ico"; Tasks: desktopicon
Name: "{userdesktop}\EpsteinFilesDownloader"; Filename: "{app}\EpsteinDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\JosephThePlatypus.ico"; Tasks: desktopicon

[Run]
; Post-install: run app once to install runtime prereqs and Playwright browsers (internet required)
; We run both steps silently in a hidden process. If any step fails, the user can rerun manually.
Filename: "{app}\EpsteinDownloader.exe"; Parameters: "--install-prereqs"; StatusMsg: "Installing runtime prerequisites (pip packages)..."; RunOnceId: InstallPrereqs; Flags: runhidden waituntilterminated
Filename: "{app}\EpsteinDownloader.exe"; Parameters: "--install-browsers"; StatusMsg: "Installing Playwright browsers (downloads Chromium)..."; RunOnceId: InstallPlaywright; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\EpsteinDownloader.exe"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\queue_state.json"
Type: files; Name: "{app}\assets\*"

; Helper function used to expand the dist path at compile time
[Code]
function GetSourceFilePath(RelPath: String): String;
begin
  Result := ExpandConstant(ExpandConstant('{#SrcDir}')) + '\\' + RelPath;
end;