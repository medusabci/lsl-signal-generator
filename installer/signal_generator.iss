; Inno Setup script of "Signal generator". Do not run it by hand: build_release.ps1 compiles the application with PyInstaller
; and then calls ISCC.exe with /DAppVersion=<version of src/version.py>. By hand (the application must be built first):
;   "C:\Program Files\Inno Setup 7\ISCC.exe" /DAppVersion=2.4 installer\signal_generator.iss
; The installer is written to ..\release\signal_generator_setup_<version>.exe

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#define AppName "Signal generator"
#define AppExe "signal_generator.exe"

[Setup]
; Fixed identifier of the application: it makes a new installer UPDATE the installed version (and the uninstaller find it)
AppId={{4E9A6D12-7C3B-4F58-A1D0-8B2E5C917F36}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher=GIB-UVa
AppComments=Synthetic EEG signal generator that transmits through lab-streaming layer (LSL), for MEDUSA and any other LSL receiver
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Per-user installation by default (no administrator rights). The dialog lets the user choose an installation for everybody.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\release
OutputBaseFilename=signal_generator_setup_{#AppVersion}
SetupIconFile=..\src\gui\images\icons\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} v{#AppVersion}
VersionInfoVersion={#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; If the application is running, close it before replacing its files
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Everything that PyInstaller produced (the .exe and its libraries and resources)
Source: "..\dist\signal_generator\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
; Logs of the application (next to the .exe). If this folder is not writable the program uses %LOCALAPPDATA%\SignalGenerator\logs
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\Signal generator v{#AppVersion}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Signal generator v{#AppVersion}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The logs are created by the program, not by the installer
Type: filesandordirs; Name: "{app}\logs"
