; TürKod kurulum betiği. build_release.ps1 tarafından çağrılır.
; AppId sabit kalmalı: sürümler arası yükseltme bunu kullanır.
#ifndef Surum
  #define Surum "3.2.0"
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
; .trpy dosya ilişkisi ve PATH değişince Gezgin / yeni konsollar haberdar edilsin.
ChangesAssociations=yes
ChangesEnvironment=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
; --- Sihirbaz görünümü -------------------------------------------------------
; Karşılama sayfası (varsayılan olarak gizli).
DisableWelcomePage=no
; Başlat menüsü klasörü sorusunu gizle; kısayol {group}\TürKod olarak oluşur.
DisableProgramGroupPage=yes
; Windows'un açık/koyu temasına uyar (Inno Setup 6.6+; 6.7.1 ile denendi).
; Tasarım projenin sitesiyle aynı dili kullanır (https://yusufx-sys.github.io/turkod-site/):
; koyu #070b16 / açık #f5f7fb zemin, camgöbeği -> çivit -> fuşya gradyan, alt dalgalar.
;   windows11  : Inno'nun yerleşik modern stili (açık temada da özel stil)
;   hidebevels : sayfalar arasındaki yatay çizgileri gizler (daha sade görünüm)
; Hep koyu için: WizardStyle=modern dark windows11 hidebevels
WizardStyle=modern dynamic windows11 hidebevels
; Lisans sayfası: build_release.ps1, LICENSE + sorumluluk_reddi.txt dosyalarından üretir.
#if FileExists(SourcePath + "KURULUM_LISANS.txt")
LicenseFile=KURULUM_LISANS.txt
#endif
; Görseller: `python sihirbaz_gorsel_uret.py` ile üretilir (sihirbaz\ klasörü, PNG).
; - Sayfa arka planı temaya göre değişir: açık tema arka*.png, koyu tema arka_dark*.png.
;   (Doğru yönerge adı ...DynamicDark'tır; eski "WizardImageFileDark" gibi adlar Inno'da yoktur.)
; - Büyük (karşılama/bitiş) ve küçük (sağ üst) görseller saydam PNG'dir ve temaya göre değişen
;   arka planın üstünde iki temada da okunur; bu yüzden koyu tema (...DynamicDark) için de aynı
;   dosyalar verilir. Verilmezse Inno koyu temada kendi varsayılan kutu görseline döner.
; - Arka plan renkleri: dil seçimi penceresi, uyarı kutuları ve Kaldırma sihirbazı da aynı zemini kullanır.
WizardBackColor=#f5f7fb
WizardBackColorDynamicDark=#070b16
#if FileExists(SourcePath + "sihirbaz\arka.png")
WizardBackImageFile=sihirbaz\arka.png,sihirbaz\arka_150.png,sihirbaz\arka_200.png
#endif
#if FileExists(SourcePath + "sihirbaz\arka_dark.png")
WizardBackImageFileDynamicDark=sihirbaz\arka_dark.png,sihirbaz\arka_dark_150.png,sihirbaz\arka_dark_200.png
#endif
#define SihirbazPanel "sihirbaz\sihirbaz.png,sihirbaz\sihirbaz_125.png,sihirbaz\sihirbaz_150.png,sihirbaz\sihirbaz_175.png,sihirbaz\sihirbaz_200.png,sihirbaz\sihirbaz_225.png,sihirbaz\sihirbaz_250.png"
#define SihirbazLogo "sihirbaz\logo.png,sihirbaz\logo_125.png,sihirbaz\logo_150.png,sihirbaz\logo_175.png,sihirbaz\logo_200.png,sihirbaz\logo_225.png,sihirbaz\logo_250.png"
#if FileExists(SourcePath + "sihirbaz\sihirbaz.png")
WizardImageFile={#SihirbazPanel}
WizardImageFileDynamicDark={#SihirbazPanel}
#endif
#if FileExists(SourcePath + "sihirbaz\logo.png")
WizardSmallImageFile={#SihirbazLogo}
WizardSmallImageFileDynamicDark={#SihirbazLogo}
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
turkish.WelcomeLabel2=Programlamayı kendi dilinde öğren: TürKod, Türkçe konuşan bir kodlama ortamıdır.%n%nBu sihirbaz [name] uygulamasını bilgisayarınıza kuracak. Devam etmeden önce açık olan TürKod pencerelerini kapatmanız önerilir.
turkish.FinishedHeadingLabel=TürKod kuruldu
turkish.FinishedLabel=Kurulum tamamlandı. TürKod'u Başlat menüsündeki kısayoldan açabilirsiniz.%n%nBelgeler ve örnekler: yusufx-sys.github.io/turkod-site

[Files]
Source: "dist\TurKod\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\TürKod"; Filename: "{app}\turkod_flutter.exe"
Name: "{autodesktop}\TürKod"; Filename: "{app}\turkod_flutter.exe"; Tasks: masaustu
Name: "{group}\TürKod ile Kodlama Macerası (Kitap)"; Filename: "{app}\belgeler\TurKod_ile_Kodlama_Macerasi.pdf"
Name: "{group}\Lisans"; Filename: "{app}\belgeler\LISANS.txt"

[Tasks]
Name: "masaustu"; Description: "Masaüstü kısayolu oluştur"; Flags: unchecked
; Varsayılan olarak AÇIK (unchecked bayrağı yok).
Name: "iliskilendir"; Description: ".trpy dosyalarını TürKod ile ilişkilendir (çift tıklayınca çalıştır, sağ tıkta ""Editör ile aç"")"
Name: "path"; Description: "TürKod'u PATH'e ekle (terminalde ""turkod dosya.trpy"" komutu)"

[Registry]
; --- .trpy dosya türü ------------------------------------------------------
; HKA: yönetici olmadan kurulumda HKCU\Software\Classes, yönetici kurulumunda HKLM.
Root: HKA; Subkey: "Software\Classes\.trpy"; ValueType: string; ValueName: ""; ValueData: "TurKod.Program"; Flags: uninsdeletevalue uninsdeletekeyifempty; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\.trpy"; ValueType: string; ValueName: "Content Type"; ValueData: "text/plain"; Flags: uninsdeletevalue; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\.trpy"; ValueType: string; ValueName: "PerceivedType"; ValueData: "text"; Flags: uninsdeletevalue; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\.trpy\OpenWithProgids"; ValueType: string; ValueName: "TurKod.Program"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\TurKod.Program"; ValueType: string; ValueName: ""; ValueData: "TürKod Programı"; Flags: uninsdeletekey; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\TurKod.Program\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\backend\_internal\editor-logo.ico,0"; Tasks: iliskilendir
; Çift tıklama: TürKod terminal penceresinde çalıştır.
Root: HKA; Subkey: "Software\Classes\TurKod.Program\shell"; ValueType: string; ValueName: ""; ValueData: "open"; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\TurKod.Program\shell\open"; ValueType: string; ValueName: ""; ValueData: "TürKod ile çalıştır"; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\TurKod.Program\shell\open"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\backend\_internal\editor-logo.ico,0"; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\TurKod.Program\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\backend\turkod_backend.exe"" --terminal ""%1"""; Tasks: iliskilendir
; "Birlikte aç" listesinde editör de görünsün.
Root: HKA; Subkey: "Software\Classes\Applications\turkod_flutter.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "TürKod Editör"; Flags: uninsdeletekey; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\Applications\turkod_flutter.exe\SupportedTypes"; ValueType: string; ValueName: ".trpy"; ValueData: ""; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\Applications\turkod_flutter.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\turkod_flutter.exe"" ""%1"""; Tasks: iliskilendir
; Sağ tık "Editör ile aç" (proje logosuyla). SystemFileAssociations altında: kullanıcı
; .trpy için varsayılan programı sonradan değiştirse de (Not Defteri, VS Code...) menüde kalır.
; Üst anahtarlar ÖNCE yazılır: kaldırıcı ters sırada çalışır, boş kalanları en son siler.
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.trpy"; Flags: uninsdeletekeyifempty; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.trpy\shell"; Flags: uninsdeletekeyifempty; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.trpy\shell\TurKod.Editor"; ValueType: string; ValueName: ""; ValueData: "Editör ile aç"; Flags: uninsdeletekey; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.trpy\shell\TurKod.Editor"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\turkod_flutter.exe,0"; Tasks: iliskilendir
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.trpy\shell\TurKod.Editor\command"; ValueType: string; ValueName: ""; ValueData: """{app}\turkod_flutter.exe"" ""%1"""; Tasks: iliskilendir

[InstallDelete]
; Temiz güncelleme: yeni sürümde artık olmayan eski dosyalar (DLL, modül, veri) kalıp karışmasın.
; Bu satırlar kopyalamadan ÖNCE çalışır; ardından [Files] her şeyi yeniden yazar.
; Kullanıcının `pip yükle` ile kurduğu paketler {localappdata}\TurKod\pip_packages içinde durur, etkilenmez.
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\backend\_internal"
Type: filesandordirs; Name: "{app}\belgeler"
Type: files; Name: "{app}\*.dll"
; Sözlük değişince eski kelime önbelleği kalmasın.
Type: files; Name: "{app}\backend\.turkod_kelimeler.json"

[UninstallDelete]
; pip ile sonradan eklenen paketler kurulum kaydında yok; uygulamanın KENDİ alt
; klasörleri tamamen silinir. Eskiden {app} klasörünün tamamı siliniyordu: kurulum
; klasörü olarak mevcut bir klasör (ör. Belgeler) seçildiyse kaldırma işlemi o
; klasördeki tüm kullanıcı dosyalarını da siliyordu. {app} boş kalırsa Inno
; Setup onu kendisi kaldırır.
Type: filesandordirs; Name: "{app}\backend"
Type: filesandordirs; Name: "{app}\data"

[Run]
Filename: "{app}\turkod_flutter.exe"; Description: "TürKod'u başlat"; Flags: nowait postinstall skipifsilent
; Güncellemede Windows simge önbelleği eski (bulanık) görev çubuğu simgesini göstermeye
; devam edebiliyor; Gezgin'in simge önbelleğini yeniler.
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden nowait skipifdoesntexist
; Uygulama içi güncelleme (/SILENT) sonrası yeniden başlat
Filename: "{app}\turkod_flutter.exe"; Flags: nowait; Check: WizardSilent

[Code]
// Çalışan backend dosyaları kilitler; kurulumdan/kaldırmadan önce kapat.
// (turkod_backend.exe aynı zamanda .trpy terminal pencerelerini, turkod.exe de
// PATH'ten açılmış konsol programlarını taşır.)
procedure BackendiDurdur;
var
  Kod: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM turkod_backend.exe', '', SW_HIDE, ewWaitUntilTerminated, Kod);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM turkod.exe', '', SW_HIDE, ewWaitUntilTerminated, Kod);
end;

// --- PATH -------------------------------------------------------------------
// {app}\backend PATH'e eklenir: içinde turkod.exe (konsol komutu) bulunur.
// Kullanıcı kurulumunda kullanıcının, yönetici kurulumunda sistemin PATH'i değişir.
function PathKoku: Integer;
begin
  if IsAdminInstallMode then Result := HKEY_LOCAL_MACHINE
  else Result := HKEY_CURRENT_USER;
end;

function PathAnahtari: String;
begin
  if IsAdminInstallMode then Result := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
  else Result := 'Environment';
end;

function PathDizini: String;
begin
  Result := ExpandConstant('{app}\backend');
end;

// ';' ile ayrılmış listeden Oge'yi çıkarır (büyük/küçük harf ve sondaki '\' önemsiz).
function PathtenCikar(Liste, Oge: String): String;
var
  Parca, Kalan: String;
  P: Integer;
begin
  Result := '';
  Kalan := Liste;
  while Kalan <> '' do
  begin
    P := Pos(';', Kalan);
    if P = 0 then
    begin
      Parca := Kalan;
      Kalan := '';
    end else
    begin
      Parca := Copy(Kalan, 1, P - 1);
      Delete(Kalan, 1, P);
    end;
    if (Trim(Parca) <> '') and (CompareText(RemoveBackslash(Trim(Parca)), RemoveBackslash(Oge)) <> 0) then
    begin
      if Result <> '' then Result := Result + ';';
      Result := Result + Parca;
    end;
  end;
end;

procedure PathGuncelle(Ekle: Boolean);
var
  Eski, Yeni: String;
begin
  if not RegQueryStringValue(PathKoku, PathAnahtari, 'Path', Eski) then
  begin
    // Değer var ama okunamıyorsa (beklenmedik tür) dokunma: yoksa kullanıcının
    // PATH'i yalnızca TürKod klasörüyle değiştirilirdi.
    if RegValueExists(PathKoku, PathAnahtari, 'Path') then
    begin
      Log('PATH okunamadı; değiştirilmedi.');
      Exit;
    end;
    Eski := '';
  end;
  Yeni := PathtenCikar(Eski, PathDizini);
  if Ekle then
  begin
    if Yeni <> '' then Yeni := Yeni + ';';
    Yeni := Yeni + PathDizini;
  end;
  if Yeni = Eski then Exit;
  if Yeni = '' then
    RegDeleteValue(PathKoku, PathAnahtari, 'Path')
  else if not RegWriteExpandStringValue(PathKoku, PathAnahtari, 'Path', Yeni) then
    Log('PATH güncellenemedi: ' + PathDizini);
end;

// Ayarlar > Sistem Entegrasyonu, kurulumda seçilmemiş olsa da .trpy ilişkisini ve
// PATH girdisini kullanıcı kayıt defterine (HKCU) yazabilir (turkod_ide\entegrasyon.py).
// [Registry] satırları yalnızca kurulumda seçilen görevleri geri alır; bunlar burada silinir.
procedure KullaniciEntegrasyonunuTemizle;
var
  Deger: String;
begin
  if RegQueryStringValue(HKCU, 'Software\Classes\.trpy', '', Deger) and (Deger = 'TurKod.Program') then
  begin
    RegDeleteValue(HKCU, 'Software\Classes\.trpy', '');
    RegDeleteValue(HKCU, 'Software\Classes\.trpy', 'Content Type');
    RegDeleteValue(HKCU, 'Software\Classes\.trpy', 'PerceivedType');
  end;
  RegDeleteValue(HKCU, 'Software\Classes\.trpy\OpenWithProgids', 'TurKod.Program');
  RegDeleteKeyIfEmpty(HKCU, 'Software\Classes\.trpy\OpenWithProgids');
  RegDeleteKeyIfEmpty(HKCU, 'Software\Classes\.trpy');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\TurKod.Program');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\Applications\turkod_flutter.exe');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\SystemFileAssociations\.trpy\shell\TurKod.Editor');
  RegDeleteKeyIfEmpty(HKCU, 'Software\Classes\SystemFileAssociations\.trpy\shell');
  RegDeleteKeyIfEmpty(HKCU, 'Software\Classes\SystemFileAssociations\.trpy');
  // Kullanıcı PATH'i (yönetici kurulumunda PathGuncelle yalnızca sistem PATH'ine bakar).
  if RegQueryStringValue(HKCU, 'Environment', 'Path', Deger) then
  begin
    if PathtenCikar(Deger, PathDizini) <> Deger then
    begin
      Deger := PathtenCikar(Deger, PathDizini);
      if Deger = '' then RegDeleteValue(HKCU, 'Environment', 'Path')
      else RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Deger);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  BackendiDurdur;
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // Görev kaldırıldıysa (yeniden kurulumda işaret kaldırılmışsa) eski girdi de silinir.
  if CurStep = ssPostInstall then PathGuncelle(WizardIsTaskSelected('path'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then BackendiDurdur;
  if CurUninstallStep = usPostUninstall then
  begin
    PathGuncelle(False);
    KullaniciEntegrasyonunuTemizle;
  end;
end;
