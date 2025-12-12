; TakibiEsasi Inno Setup Script
; Bu script, TakibiEsasi icin Windows kurulum paketi olusturur

#define MyAppName "TakibiEsasi"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TakibiEsasi"
#define MyAppURL "https://takibiesasi.com"
#define MyAppExeName "TakibiEsasi.exe"
#define MyAppDescription "Avukatlar icin Takip Yonetim Sistemi"

[Setup]
; Uygulama kimlik bilgileri
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/support
AppUpdatesURL={#MyAppURL}/download
AppCopyright=Copyright (c) 2024 {#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Kurulum dizinleri
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Cikti dosyasi ayarlari
OutputDir=..\dist\installer
OutputBaseFilename=TakibiEsasi_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMADictionarySize=65536
LZMANumFastBytes=64

; Kurulum ikonu ve gorseller
SetupIconFile=..\assets\icon.ico
; WizardImageFile=..\assets\wizard.bmp
; WizardSmallImageFile=..\assets\wizard_small.bmp

; Gereksinimler
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

; Lisans dosyasi (EULA + KVKK)
LicenseFile=license_tr.txt

; Diger ayarlar
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no
DisableFinishedPage=no
ShowLanguageDialog=no
WizardStyle=modern
WindowVisible=no
CloseApplications=yes
RestartApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
turkish.LaunchProgram={#MyAppName} uygulamasini baslat
turkish.CreateDesktopIcon=Masaustunde kisayol olustur
turkish.CreateQuickLaunchIcon=Hizli Baslatma cubuğunda kisayol olustur

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Ana uygulama
Source: "..\dist\TakibiEsasi.exe"; DestDir: "{app}"; Flags: ignoreversion

; Versiyon dosyasi
Source: "..\version.txt"; DestDir: "{app}"; Flags: ignoreversion

; Yasal belgeler
Source: "..\legal\*"; DestDir: "{app}\legal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Tema dosyalari (eger ayri ise)
; Source: "..\app\themes\*"; DestDir: "{app}\themes"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Baslat menusu kisayolu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{group}\{#MyAppName} Kaldır"; Filename: "{uninstallexe}"; Comment: "{#MyAppName} uygulamasini kaldir"

; Masaustu kisayolu
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

; Hizli Baslatma kisayolu
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon; Comment: "{#MyAppDescription}"

[Run]
; Kurulum sonrasi uygulamayi baslat secenegi
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kaldirilmadan once uygulamayi kapat
Filename: "{cmd}"; Parameters: "/C taskkill /f /im TakibiEsasi.exe"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; Kullanici verilerini silme (opsiyonel - yorum satiri olarak birakiyoruz)
; Type: filesandordirs; Name: "{userappdata}\TakibiEsasi"

[Registry]
; Uygulama kayit defteri girisleri
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

; .teb dosya uzantisi iliskilendirmesi (Transfer paketi)
Root: HKCR; Subkey: ".teb"; ValueType: string; ValueData: "TakibiEsasiTransfer"; Flags: uninsdeletekey
Root: HKCR; Subkey: "TakibiEsasiTransfer"; ValueType: string; ValueData: "TakibiEsasi Transfer Paketi"; Flags: uninsdeletekey
Root: HKCR; Subkey: "TakibiEsasiTransfer\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCR; Subkey: "TakibiEsasiTransfer\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

[Code]
// Kurulum oncesi eski versiyon kontrolu
function InitializeSetup(): Boolean;
var
  InstalledVersion: String;
  ResultCode: Integer;
begin
  Result := True;

  // Onceki kurulum kontrolu
  if RegQueryStringValue(HKLM, 'Software\{#MyAppPublisher}\{#MyAppName}', 'Version', InstalledVersion) then
  begin
    if CompareStr(InstalledVersion, '{#MyAppVersion}') >= 0 then
    begin
      if MsgBox('TakibiEsasi {#MyAppVersion} veya daha yeni bir surum zaten kurulu.' + #13#10 + #13#10 +
                'Yeniden kurmak istiyor musunuz?', mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
  end;

  // Calisiyorsa uygulamayi kapat
  if CheckForMutexes('{#MyAppName}') then
  begin
    if MsgBox('TakibiEsasi su anda calisiyor. Kuruluma devam etmek icin kapatilmasi gerekiyor.' + #13#10 + #13#10 +
              'Uygulamayi kapatip devam etmek istiyor musunuz?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill', '/f /im TakibiEsasi.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);
    end
    else
    begin
      Result := False;
    end;
  end;
end;

// Kurulum tamamlandiginda
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Kurulum sonrasi islemler
    // Ornegin: istatistik gonderme, log olusturma vs.
  end;
end;

// Kaldirma oncesi onay
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('TakibiEsasi uygulamasini kaldirmak istediginizden emin misiniz?' + #13#10 + #13#10 +
                   'Not: Kullanici verileriniz (veritabani, ayarlar) silinmeyecektir.',
                   mbConfirmation, MB_YESNO) = IDYES;
end;
