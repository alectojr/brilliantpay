#define MyAppName "BrilliantPay"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Brilliant Driving School"
#ifndef BuildRoot
  #define BuildRoot "dist\release"
#endif

[Setup]
AppId={{8C026BCC-58FC-47E1-9234-7D6882A4B1AA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\BrilliantPay
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=BrilliantPaySetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\BrilliantPay.exe

[Files]
Source: "{#BuildRoot}\BrilliantPay\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\BrilliantPay"; Filename: "{app}\BrilliantPay.exe"
Name: "{autoprograms}\Configure BrilliantPay Server"; Filename: "{app}\BrilliantPay.exe"; Parameters: "--configure"
Name: "{autodesktop}\BrilliantPay"; Filename: "{app}\BrilliantPay.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\BrilliantPay.exe"; Description: "Launch BrilliantPay"; Flags: postinstall nowait skipifsilent
