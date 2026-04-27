; ラベル一発作成 Inno Setup スクリプト
#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppName=ラベル一発作成
AppVersion={#AppVersion}
AppPublisher=mozu93
AppPublisherURL=https://github.com/mozu93/label-ippatsusaku
AppSupportURL=https://github.com/mozu93/label-ippatsusaku/issues
DefaultDirName={localappdata}\LabelIppatsusaku
DefaultGroupName=ラベル一発作成
DisableDirPage=yes
OutputDir={#SourcePath}\..\installer_output
OutputBaseFilename=LabelIppatsusaku_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile={#SourcePath}\..\assets\app_icon.ico

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"

[Files]
Source: "{#SourcePath}\..\dist\LabelIppatsusaku\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ラベル一発作成"; Filename: "{app}\LabelIppatsusaku.exe"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ラベル一発作成"; Filename: "{app}\LabelIppatsusaku.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LabelIppatsusaku.exe"; Description: "ラベル一発作成を起動する"; Flags: nowait postinstall skipifsilent
