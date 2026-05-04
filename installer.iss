; Inno Setup Script for TaskbarTimer

[Setup]
AppName=TaskbarTimer
AppVersion=1.0
DefaultDirName={autopf}\TaskbarTimer
DefaultGroupName=TaskbarTimer
UninstallDisplayIcon={app}\TaskbarTimer.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=TaskbarTimer_Setup
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source points to the output of your build.bat
Source: "dist\TaskbarTimer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TaskbarTimer"; Filename: "{app}\TaskbarTimer.exe"
Name: "{autodesktop}\TaskbarTimer"; Filename: "{app}\TaskbarTimer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TaskbarTimer.exe"; Description: "{cm:LaunchProgram,TaskbarTimer}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up the config file on uninstall if desired
Type: files; Name: "{userprofile}\.timer_alarm_v3.json"
