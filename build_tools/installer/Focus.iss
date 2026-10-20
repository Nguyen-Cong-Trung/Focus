; Focus 1.0.0: per-user install, stable upgrade identity and preserved workspace.
#ifndef BundleDir
  #define BundleDir "..\..\dist\Focus"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\..\releases"
#endif
#define AppVersion "1.0.0"

[Setup]
AppId={{139698E0-3B7B-4867-AB38-C8B37B01C9E1}
AppName=Focus
AppVersion={#AppVersion}
AppVerName=Focus {#AppVersion}
AppPublisher=Spertulo Utility
AppPublisherURL=https://github.com/Nguyen-Cong-Trung
AppSupportURL=https://github.com/Nguyen-Cong-Trung/Focus/issues
AppUpdatesURL=https://github.com/Nguyen-Cong-Trung/Focus/releases/latest
AppContact=trungcong0106a7@gmail.com
AppComments=Created by Nguyễn Công Trung. A focused workspace by Spertulo Utility.
DefaultDirName={localappdata}\Programs\Spertulo Utility\Focus
DefaultGroupName=Spertulo Utility\Focus
DisableProgramGroupPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupArchitecture=x64
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=Focus-Setup-{#AppVersion}-Windows-x64
SetupIconFile=..\..\branding\focus.ico
UninstallDisplayIcon={app}\Focus.exe
UninstallDisplayName=Focus
VersionInfoVersion=1.0.0.0
VersionInfoCompany=Spertulo Utility
VersionInfoDescription=Focus Setup
VersionInfoProductName=Focus
VersionInfoProductVersion={#AppVersion}
WizardStyle=modern dynamic windows11
WizardSizePercent=110
WizardImageFile=wizard.png
WizardSmallImageFile=..\..\branding\focus-logo.png
WizardImageBackColor=$111318
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=2
SetupMutex=Local\Spertulo.Focus.Setup
AppMutex=Local\Spertulo.Focus.Running
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
RestartIfNeededByRun=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
UsePreviousGroup=yes
ChangesEnvironment=no
Uninstallable=yes
UninstallLogMode=append
AllowNoIcons=yes
AllowUNCPath=no
AllowNetworkDrive=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to Focus
WelcomeLabel2=Make room for your best work.%n%nFocus brings your timer, plans, sounds and distraction controls into one personal workspace.%n%nThis wizard installs Focus {#AppVersion} for your Windows account. Your existing plans, settings and recordings are kept when you update.
FinishedHeadingLabel=You're ready to focus
FinishedLabel=Focus has been installed.%n%nYour workspace stays separate from the application, so updates and uninstalling keep your personal data.
SetupAppRunningError=Focus is currently running, possibly in the notification area.%n%nChoose Quit Focus from its tray menu, then click OK to continue. Setup will not force-close your session.
UninstallAppRunningError=Focus is currently running, possibly in the notification area.%n%nChoose Quit Focus from its tray menu, then click OK to uninstall. Your personal workspace will be kept.
BeveledLabel=Spertulo Utility

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\Focus.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BundleDir}\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "installed-guide.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Focus"; Filename: "{app}\Focus.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Focus.exe"; AppUserModelID: "SpertuloUtility.Focus"; Comment: "Focus — Spertulo Utility"
Name: "{group}\Uninstall Focus"; Filename: "{uninstallexe}"; IconFilename: "{app}\Focus.exe"; Comment: "Uninstall Focus (keeps your workspace)"
Name: "{autodesktop}\Focus"; Filename: "{app}\Focus.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Focus.exe"; AppUserModelID: "SpertuloUtility.Focus"; Tasks: desktopicon; Comment: "Focus — Spertulo Utility"

[Run]
Filename: "{app}\Focus.exe"; Description: "Launch Focus"; Flags: nowait postinstall skipifsilent unchecked

; Deliberately no wildcard deletion and no workspace entries. Inno removes only
; installed files and its own shortcuts; unknown files and user data survive.

[Code]
function ValidateInstallFolder(): String;
var
  DataDir: String;
  InstallDir: String;
begin
  Result := '';
  DataDir := AddBackslash(AddBackslash(GetEnv('USERPROFILE')) + '.deepfocus');
  InstallDir := AddBackslash(ExpandFileName(WizardDirValue));
  if (CompareText(InstallDir, DataDir) = 0) or
     (CompareText(Copy(InstallDir, 1, Length(DataDir)), DataDir) = 0) then begin
    Result := 'Choose an application folder outside your Focus workspace (.deepfocus).';
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Error: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then begin
    Error := ValidateInstallFolder();
    if Error <> '' then begin
      SuppressibleMsgBox(Error, mbError, MB_OK, IDOK);
      Result := False;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  VersionMS, VersionLS: Cardinal;
begin
  Result := ValidateInstallFolder();
  if (Result = '') and GetVersionNumbers(ExpandConstant('{app}\Focus.exe'), VersionMS, VersionLS) then
    if (VersionMS > $00010000) or ((VersionMS = $00010000) and (VersionLS > 0)) then
      Result := 'A newer version of Focus is installed. Use the latest installer to keep your workspace compatible.';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
  RunKey: String;
begin
  if CurUninstallStep = usUninstall then begin
    RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
    { Remove startup entries only when they point at this exact installation. }
    if RegQueryStringValue(HKCU, RunKey, 'DeepFocus', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\Focus.exe') + '"') = 0 then
        RegDeleteValue(HKCU, RunKey, 'DeepFocus');
    if RegQueryStringValue(HKCU, RunKey, 'Focus', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\Focus.exe') + '"') = 0 then
        RegDeleteValue(HKCU, RunKey, 'Focus');
  end;
end;
