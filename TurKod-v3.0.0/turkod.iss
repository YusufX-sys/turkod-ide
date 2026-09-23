; TürKod kurulum betiği. build_release.ps1 tarafından çağrılır.
; AppId sabit kalmalı: sürümler arası yükseltme bunu kullanır.
#ifndef Surum
  #define Surum "3.0.0"
#endif

[Setup]
AppId={{A85AA861-93EC-40E0-9FE0-9EA9E0E661E8}
AppName=TürKod
AppVersion={#Surum}
; "Uygulamalar ve özellikler" listesinde görünen yayıncı adı. Windows'un SmartScreen'de
; gösterdiği yayıncı bu DEĞİLDİR: o, kurulum dosyasını imzalayan sertifikanın adıdır.
AppPublisher=Yusuf Tandoğan
AppPublisherURL=https://github.com/YusufX-sys/turkod-ide
AppSupportURL=https://github.com/YusufX-sys/turkod-ide/issues
AppUpdatesURL=https://github.com/YusufX-sys/turkod-ide/releases
AppCopyright=Copyright (C) 2026 Yusuf Tandoğan
; Setup.exe'nin Özellikler > Ayrıntılar sekmesi (imzadan bağımsız).
VersionInfoVersion={#Surum}.0
VersionInfoProductVersion={#Surum}
VersionInfoCompany=Yusuf Tandoğan
VersionInfoProductName=TürKod IDE
VersionInfoDescription=TürKod IDE Kurulumu
VersionInfoCopyright=Copyright (C) 2026 Yusuf Tandoğan
; Flutter uygulaması Windows 10/11 (64 bit) ister.
MinVersion=10.0
; ASCII klasör adı: Türkçe karakterli yol kaynaklı araç sorunlarını baştan keser.
DefaultDirName={autopf}\TurKod
DefaultGroupName=TürKod
PrivilegesRequired=lowest
; Uygulama içi güncellemede uygulamayı yeniden başlatmayı [Run] bölümü yapar; Inno ayrıca başlatmasın.
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
; --- Sihirbaz görünümü -------------------------------------------------------
; Karşılama sayfası (varsayılan olarak gizli).
DisableWelcomePage=no
; Başlat menüsü klasörü sorusunu gizle; kısayol {group}\TürKod olarak oluşur.
DisableProgramGroupPage=yes
; Windows'un açık/koyu temasına uyar (Inno Setup 6.6+). Hep koyu için: WizardStyle=modern dark
WizardStyle=modern dynamic
; Lisans sayfası: build_release.ps1, LICENSE + sorumluluk_reddi.txt dosyalarından üretir.
#if FileExists(SourcePath + "KURULUM_LISANS.txt")
LicenseFile=KURULUM_LISANS.txt
#endif
; Görseller: `python sihirbaz_gorsel_uret.py` ile üretilir ya da kendi BMP dosyalarını koy.
#if FileExists(SourcePath + "sihirbaz\sihirbaz.bmp")
WizardImageFile=sihirbaz\sihirbaz.bmp,sihirbaz\sihirbaz_200.bmp
#endif
#if FileExists(SourcePath + "sihirbaz\logo.bmp")
WizardSmallImageFile=sihirbaz\logo.bmp,sihirbaz\logo_200.bmp
#endif
; Ham turkod.ico (1.8 MB) Inno'da "Resource update error: File is too large" veriyor.
; build_release.ps1 küçük, çok boyutlu bir kopyayı dist\turkod_setup.ico olarak üretir.
#if FileExists(SourcePath + "dist\turkod_setup.ico")
SetupIconFile=dist\turkod_setup.ico
#endif
UninstallDisplayIcon={app}\turkod_flutter.exe
OutputDir=dist
OutputBaseFilename=TurKod-Setup-{#Surum}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Messages]
; Sihirbaz metinlerini değiştirme: "turkish." öneki yalnızca Türkçe için geçerli olur.
turkish.WelcomeLabel1=TürKod {#Surum} kurulumuna hoş geldiniz
turkish.WelcomeLabel2=Bu sihirbaz [name] uygulamasını bilgisayarınıza kuracak.%n%nDevam etmeden önce açık olan TürKod pencerelerini kapatmanız önerilir.
turkish.FinishedHeadingLabel=TürKod kuruldu
turkish.FinishedLabel=Kurulum tamamlandı. TürKod'u Başlat menüsündeki kısayoldan açabilirsiniz.

[Files]
Source: "dist\TurKod\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\TürKod"; Filename: "{app}\turkod_flutter.exe"
Name: "{autodesktop}\TürKod"; Filename: "{app}\turkod_flutter.exe"; Tasks: masaustu

[Tasks]
Name: "masaustu"; Description: "Masaüstü kısayolu oluştur"; Flags: unchecked

[InstallDelete]
; Temiz güncelleme: yeni sürümde artık olmayan eski dosyalar (DLL, modül, veri) kalıp karışmasın.
; Bu satırlar kopyalamadan ÖNCE çalışır; ardından [Files] her şeyi yeniden yazar.
; Kullanıcının `pip yükle` ile kurduğu paketler {localappdata}\TurKod\pip_packages içinde durur, etkilenmez.
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\backend\_internal"
Type: files; Name: "{app}\*.dll"
; Sözlük değişince eski kelime önbelleği kalmasın.
Type: files; Name: "{app}\backend\.turkod_kelimeler.json"

[UninstallDelete]
; pip ile sonradan eklenen paketler kurulum kaydında yok; klasörü tamamen sil.
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\turkod_flutter.exe"; Description: "TürKod'u başlat"; Flags: nowait postinstall skipifsilent
; Uygulama içi güncelleme (/SILENT) sonrası yeniden başlat
Filename: "{app}\turkod_flutter.exe"; Flags: nowait; Check: WizardSilent

[Code]
// Çalışan backend dosyaları kilitler; kurulumdan/kaldırmadan önce kapat.
procedure BackendiDurdur;
var
  Kod: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM turkod_backend.exe', '', SW_HIDE, ewWaitUntilTerminated, Kod);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  BackendiDurdur;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then BackendiDurdur;
end;
