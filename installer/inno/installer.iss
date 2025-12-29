#define MyOutputDir "installer\output"

[Setup]
AppName=Epstein Files Downloader
AppVersion=1.0.0
DefaultDirName={pf}\PlatypusFiles\WebsiteFileDownloader
DefaultGroupName=Epstein Files Downloader
OutputDir={#MyOutputDir}
OutputBaseFilename=EpsteinFilesDownloader_Installer
Compression=lzma
SolidCompression=yes
DisableDirPage=no
PrivilegesRequired=admin
SetupIconFile="C:\\Path\\JosephThePlatypus.ico"

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Install the PyInstaller one-dir output (everything under dist\epstein_downloader_gui)
Source: "..\..\dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; Useful files to include at top level
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\JosephThePlatypus.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Epstein Files Downloader"; Filename: "{app}\epstein_downloader_gui.exe"; IconFilename: "{app}\JosephThePlatypus.ico"
Name: "{commondesktop}\Epstein Files Downloader"; Filename: "{app}\epstein_downloader_gui.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\epstein_downloader_gui.exe"; Description: "Launch Epstein Files Downloader"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
