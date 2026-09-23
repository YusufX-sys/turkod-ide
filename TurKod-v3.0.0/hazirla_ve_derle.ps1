<#
TürKod: hazırlıktan teslime kadar her şeyi yapan betik.

Proje kökünde (turkod_ide ve turkod_flutter ile AYNI klasörde) çalıştır:

    powershell -ExecutionPolicy Bypass -File .\hazirla_ve_derle.ps1

Sırayla yaptığı işler:
  1. Klasör/dosya ve sürüm tutarlılığını denetler (surum.txt = pubspec.yaml)
  2. Build Python paketlerini kurar (pyinstaller, fastapi, uvicorn, ...)
  3. server.py'ye güncelleme komutlarını ekler (yoksa; yedek alır), eski dosyayı siler
  4. C:\build\py312 kopyasını denetler
  5. Inno Setup'ı bulur, yoksa winget ile kurar
  6. Özel anahtarı signing.py'deki public key ile eşleştirir (uyuşmazsa düzeltmeyi önerir)
  7. build_release.ps1'i çalıştırır (Flutter + PyInstaller + Python ortamı + manifest + kurulum)
  8. Çıkan paketi test eder (backend'i açar, WebSocket ile imza/güncelleme komutlarını dener)

Parametreler (hepsi isteğe bağlı):
  -OzelAnahtar   varsayılan C:\gizli\turkod_private.pem
  -PythonKopya   varsayılan C:\build\py312
  -Imzali        Authenticode ile imzala (sertifika gerekir; -SignToolArgs zorunlu)
  -SignToolArgs  örn. @('/sha1','SERTIFIKA_PARMAK_IZI')
  -SadeceInno    dist\TurKod hazırsa Flutter/PyInstaller adımlarını atlar; kurulumu (Inno) ve latest.json'ı yeniden üretir, sonra paketi test eder
  -ZamanSunucu   varsayılan http://timestamp.digicert.com (Artifact Signing: http://timestamp.acs.microsoft.com)
  -IndirmeUrl    verilirse latest.json + latest.json.sig da üretilir
#>
param(
    [string]$OzelAnahtar = "C:\gizli\turkod_private.pem",
    [string]$PythonKopya = "C:\build\py312",
    [switch]$Imzali,
    [switch]$SadeceInno,
    [string[]]$SignToolArgs = @(),
    [string]$ZamanSunucu = "http://timestamp.digicert.com",
    [string]$IndirmeUrl = ""
)

$ErrorActionPreference = "Stop"
# Python çıktısı UTF-8 olsun, PowerShell de UTF-8 okusun (Türkçe Windows'ta yığın ANSI/OEM uyuşmazlığı olur).
$env:PYTHONUTF8 = "1"
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$Kok = $PSScriptRoot
Set-Location $Kok
$Saat = [System.Diagnostics.Stopwatch]::StartNew()
$Utf8Bomsuz = New-Object System.Text.UTF8Encoding($false)
$parolaBizAyarladik = $false

function Adim($m)  { Write-Host "`n=== $m" -ForegroundColor Cyan }
function Tamam($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Uyari($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Dur($m)   { throw $m }

function Calistir($exe, [string[]]$argumanlar) {
    & $exe @argumanlar
    if ($LASTEXITCODE -ne 0) { throw "$exe hata kodu $LASTEXITCODE ile bitti." }
}

# Çıktıyı yakalar; stderr yüzünden betiği durdurmaz.
function CalistirSessiz($exe, [string[]]$argumanlar) {
    $onceki = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $cikti = & $exe @argumanlar 2>&1 | ForEach-Object { "$_" }
        $kod = $LASTEXITCODE
    } finally { $ErrorActionPreference = $onceki }
    return [pscustomobject]@{ Kod = $kod; Cikti = ($cikti -join "`n") }
}

function Oku($yol)         { return [System.IO.File]::ReadAllText($yol, [System.Text.Encoding]::UTF8) }
function Yaz($yol, $metin) { [System.IO.File]::WriteAllText($yol, $metin, $Utf8Bomsuz) }
function Yedekle($yol) {
    $y = "$yol.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Copy-Item $yol $y
    Uyari "Yedek alındı: $y"
}

function IsccBul {
    $adaylar = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe", "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe")
    return ($adaylar | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function WsCagri([int]$port, [string]$komut) {
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $iptal = [System.Threading.CancellationToken]::None
    try {
        $ws.ConnectAsync([Uri]"ws://127.0.0.1:$port/ws", $iptal).Wait(8000) | Out-Null
        $veri = [System.Text.Encoding]::UTF8.GetBytes('{"id":1,"command":"' + $komut + '","params":{}}')
        $gonder = New-Object 'System.ArraySegment[byte]' -ArgumentList @(, $veri)
        $ws.SendAsync($gonder, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $iptal).Wait(8000) | Out-Null
        $tampon = New-Object byte[] 262144
        $al = New-Object 'System.ArraySegment[byte]' -ArgumentList @(, $tampon)
        $gorev = $ws.ReceiveAsync($al, $iptal)
        if (-not $gorev.Wait(30000)) { throw "Yanıt zaman aşımı ($komut)" }
        $metin = [System.Text.Encoding]::UTF8.GetString($tampon, 0, $gorev.Result.Count)
        return ($metin | ConvertFrom-Json)
    } finally { $ws.Dispose() }
}

try {
    # ------------------------------------------------------------------
    Adim "1/8 Klasör ve dosya kontrolü"
    $gerekli = @(
        "turkod_ide\server.py", "turkod_ide\updater.py", "turkod_ide\signing.py",
        "turkod_flutter\pubspec.yaml", "turkod_flutter\lib\main.dart", "turkod_flutter\lib\guncelleme.dart", "turkod_flutter\lib\acilis_ekrani.dart",
        "backend_main.py", "turkod_backend.spec", "manifest_imzala.py", "surum_imzala.py",
        "surum.txt", "turkod.iss", "kullanici_kutuphaneleri.txt", "build_release.ps1", "ikon_kucult.py", "yama_uygula.py", "turkod_ide\pip_tr.py")
    foreach ($g in $gerekli) {
        if (-not (Test-Path (Join-Path $Kok $g))) {
            Dur "Eksik dosya: $g  (betik proje kökünde olmalı; dosyaları yeniden indirip yerleştir)"
        }
    }
    if (-not (Select-String -Path "manifest_imzala.py" -Pattern "anahtar-kontrol" -Quiet)) {
        Dur "manifest_imzala.py eski sürüm. Son sürümü indirip üzerine yaz."
    }
    if (-not (Select-String -Path "build_release.ps1" -Pattern "0/8" -Quiet)) {
        Dur "build_release.ps1 eski sürüm. Son sürümü indirip üzerine yaz."
    }
    if (-not (Select-String -Path "turkod_flutter\lib\main.dart" -Pattern "guncellemeKontrolEt" -Quiet)) {
        Dur "main.dart içinde guncellemeKontrolEt çağrısı yok (HomeShell.initState'e eklenmeli)."
    }
    $surum = (Get-Content "surum.txt" -Raw).Trim()
    $pub = Select-String -Path "turkod_flutter\pubspec.yaml" -Pattern '^version:\s*(\d+\.\d+\.\d+)' | Select-Object -First 1
    if (-not $pub) { Dur "pubspec.yaml içinde 'version: X.Y.Z' satırı yok." }
    $pubSurum = $pub.Matches[0].Groups[1].Value
    if ($pubSurum -ne $surum) { Dur "Sürümler farklı: surum.txt = $surum, pubspec.yaml = $pubSurum. İkisini eşitle." }
    Tamam "Sürüm $surum (surum.txt = pubspec.yaml)"
    $yonetici = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    # Flutter sürümü: Windows motorunda, 3.47.2'de bildirilen (3.41.6'da olmayan) bir hata var:
    # pencere boyutu gerçekten değişene kadar çizim güncellenmiyor (flutter/flutter#192537).
    $fv = ""
    try {
        $ham = (& flutter --version --machine 2>$null) -join "`n"
        if ($ham -match '"frameworkVersion"\s*:\s*"([^"]+)"') { $fv = $Matches[1] }
    } catch { }
    if ($fv -match '^3\.41\.') { Tamam "Flutter $fv" }
    elseif ($fv) {
        Uyari "Flutter ${fv}: bu sürümde Windows'ta 'yazdığım kod pencere boyutu değişene kadar görünmüyor' hatası bildirildi (flutter/flutter#192537; 3.47.2'de var, 3.41.6'da yok). Sorun yaşıyorsan uygulamayı Flutter 3.41.6 ile derle."
    }
    if ($yonetici) { Uyari "Yönetici olarak çalışıyorsun. PyInstaller bunu istemez (7.0'da engellenecek); normal (yönetici olmayan) bir PowerShell'de çalıştırman önerilir." }

    # ------------------------------------------------------------------
    Adim "2/8 Build Python paketleri"
    Calistir "python" @("--version")
    Calistir "python" @("-m", "pip", "install", "--disable-pip-version-check", "-q",
        "pyinstaller", "fastapi", "uvicorn", "websockets", "cryptography", "requests",
        "openai", "anthropic", "groq", "google-genai", "pillow", "tzdata")
    Tamam "pyinstaller, fastapi, uvicorn, websockets, cryptography, pillow, tzdata, AI kütüphaneleri hazır"

    # ------------------------------------------------------------------
    Adim "3/8 Kaynak düzeltmeleri"
    $eskiBackend = Join-Path $Kok "turkod_ide\backend_main.py"
    if (Test-Path $eskiBackend) { Remove-Item $eskiBackend -Force; Tamam "Eski turkod_ide\backend_main.py silindi" }

    $sp = Join-Path $Kok "turkod_ide\server.py"
    $s = Oku $sp
    if ($s -match "guncelleme_kontrol") {
        Tamam "server.py: güncelleme komutları zaten var"
    } else {
        $m = [regex]::Match($s, '(?ms)^SYNC_COMMANDS\s*=\s*\{.*?^\}[ \t]*\r?$\n?')
        if (-not $m.Success) { Dur "server.py içinde SYNC_COMMANDS sözlüğü bulunamadı; snippet'i elle ekle." }
        $nl = "`n"
        if ($s.Contains("`r`n")) { $nl = "`r`n" }
        $ek = (@("", "try:", "    from . import updater", "except ImportError:", "    import updater", "",
                 'SYNC_COMMANDS["guncelleme_kontrol"] = lambda params: updater.kontrol_et()',
                 'SYNC_COMMANDS["guncelleme_indir"] = lambda params: updater.indir_ve_dogrula()', "") -join $nl) + $nl
        Yedekle $sp
        Yaz $sp ($s.Insert($m.Index + $m.Length, $ek))
        Tamam "server.py: güncelleme komutları eklendi"
    }
    # Yamalar (idempotent, yedek alır): menü, kaydet-ve-çık, Türkçe pip, indirme ilerlemesi
    Calistir "python" @((Join-Path $Kok "yama_uygula.py"))
    Calistir "python" @("-c", "from turkod_ide.pip_tr import pip_komutu_cevir as c; r = c('pip yukle x', 'py', 'pk'); assert r and 'install --target' in r; print('pip_tr OK')")

    Calistir "python" @("-c", "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read()); print('server.py sozdizimi OK')", $sp)
    Calistir "python" @("-c", "import turkod_ide.server; print('server.py ice aktarma OK')")
    # Kullanıcı kodu çalıştırılırken kullanılan ortam hazırlığı (ide_core yamaları) gerçekten çağrılabiliyor mu?
    Calistir "python" @("-c", "from turkod_ide.ide_core import IDECore; c = IDECore(); e = c._subprocess_env() if hasattr(c, '_subprocess_env') else {}; print('IDECore._subprocess_env OK')")

    # Dart derleme hataları (error) 20 dakikalık derlemeden ÖNCE yakalansın; uyarı/bilgi (info/warning) önemsenmez.
    Push-Location (Join-Path $Kok "turkod_flutter")
    try { $an = CalistirSessiz "flutter" @("analyze", "--no-pub", "lib\main.dart", "lib\guncelleme.dart", "lib\acilis_ekrani.dart") } finally { Pop-Location }
    $dartHata = @($an.Cikti -split "`n" | Where-Object { $_ -match '^\s*error\s+[-•]' })
    if ($dartHata.Count -gt 0) { Dur "Dart derleme hatası ($($dartHata.Count)):`n$($dartHata -join "`n")" }
    Tamam "flutter analyze: hata yok"

    # ------------------------------------------------------------------
    Adim "4/8 Kullanıcı Python kopyası ($PythonKopya)"
    $pyKopya = Join-Path $PythonKopya "python.exe"
    if (-not (Test-Path $pyKopya)) { Dur "python.exe yok: $pyKopya" }
    $pth = Get-ChildItem $PythonKopya -Filter "python*._pth" -File -ErrorAction SilentlyContinue
    if ($pth) { Dur "$PythonKopya içinde '$($pth[0].Name)' var (embeddable kalıntısı). Klasörü silip robocopy ile yeniden kopyala." }
    $kontrolPy = Join-Path $env:TEMP "turkod_py_kontrol.py"
    Set-Content -Path $kontrolPy -Encoding ASCII -Value @'
import os, sys, tkinter
sys.exit(0 if os.path.samefile(sys.prefix, sys.argv[1]) else 3)
'@
    $r = CalistirSessiz $pyKopya @("-I", "-X", "utf8", $kontrolPy, $PythonKopya)
    if ($r.Kod -ne 0 -or $r.Cikti -match "platform independent") {
        Dur "$PythonKopya kendi kendine yetmiyor (çıkış kodu $($r.Kod)). Çıktı:`n$($r.Cikti)"
    }
    Tamam "tkinter çalışıyor, sys.prefix doğru, uyarı yok"

    # ------------------------------------------------------------------
    Adim "5/8 Inno Setup"
    $iscc = IsccBul
    if (-not $iscc) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Uyari "Inno Setup bulunamadı; winget ile kuruluyor (onay penceresi çıkabilir)..."
            & winget install --id JRSoftware.InnoSetup -e -s winget --silent --accept-package-agreements --accept-source-agreements
            $iscc = IsccBul
        }
        if (-not $iscc) {
            Dur "Inno Setup kurulamadı. https://jrsoftware.org/isdl.php adresinden 'Inno Setup 6' indirip kur ('Install for all users'), sonra betiği tekrar çalıştır."
        }
    }
    Tamam $iscc

    # ------------------------------------------------------------------
    Adim "6/8 İmzalama anahtarı"
    if (-not (Test-Path $OzelAnahtar)) { Dur "Özel anahtar yok: $OzelAnahtar" }
    if (-not $env:TURKOD_KEY_PASS -and (Select-String -Path $OzelAnahtar -Pattern "ENCRYPTED" -Quiet)) {
        $g = Read-Host "Özel anahtarın parolası" -AsSecureString
        $env:TURKOD_KEY_PASS = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($g))
        $parolaBizAyarladik = $true
    }
    $r = CalistirSessiz "python" @("manifest_imzala.py", "--anahtar-kontrol", $OzelAnahtar)
    if ($r.Kod -eq 0) {
        Tamam "Özel anahtar signing.py'deki public key ile eşleşiyor"
    } elseif ($r.Cikti -match "public key'in e") {
        Uyari "Özel anahtar signing.py'deki public key'in eşi değil."
        Write-Host "  Public key'i değiştirmek güvenlidir, ama SADECE bu anahtarla imzalanmış hiçbir sürüm dağıtılmadıysa." -ForegroundColor Yellow
        Write-Host "  Eski sürümler yeni anahtarla imzalanan güncellemeleri doğrulayamaz." -ForegroundColor Yellow
        $cevap = Read-Host "  signing.py'deki public key bu özel anahtarın public key'iyle değiştirilsin mi? (E/H)"
        if ($cevap -notmatch '^[EeYy]') { Dur "İptal edildi. Doğru özel anahtarı -OzelAnahtar ile ver." }
        $pubPy = Join-Path $env:TEMP "turkod_public_yaz.py"
        Set-Content -Path $pubPy -Encoding ASCII -Value @'
import os, sys
from cryptography.hazmat.primitives import serialization
veri = open(sys.argv[1], "rb").read()
try:
    k = serialization.load_pem_private_key(veri, password=None)
except TypeError:
    k = serialization.load_pem_private_key(veri, password=os.environ.get("TURKOD_KEY_PASS", "").encode("utf-8"))
sys.stdout.write(k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii"))
'@
        $p = CalistirSessiz "python" @($pubPy, $OzelAnahtar)
        if ($p.Kod -ne 0 -or $p.Cikti -notmatch "BEGIN PUBLIC KEY") { Dur "Public key üretilemedi (parola yanlış olabilir):`n$($p.Cikti)" }
        $pem = ($p.Cikti -replace "`r", "").Trim()
        $sg = Join-Path $Kok "turkod_ide\signing.py"
        $t = Oku $sg
        $mm = [regex]::Match($t, '(TURKOD_PUBLIC_KEY\s*=\s*""")(.*?)(""")', 'Singleline')
        if (-not $mm.Success) { Dur "signing.py içinde TURKOD_PUBLIC_KEY bulunamadı." }
        Yedekle $sg
        $g2 = $mm.Groups[2]
        Yaz $sg ($t.Substring(0, $g2.Index) + $pem + $t.Substring($g2.Index + $g2.Length))
        $r = CalistirSessiz "python" @("manifest_imzala.py", "--anahtar-kontrol", $OzelAnahtar)
        if ($r.Kod -ne 0) { Dur "Değişiklikten sonra da eşleşmedi:`n$($r.Cikti)" }
        Tamam "signing.py'deki public key güncellendi ve eşleşiyor"
    } else {
        Dur "Anahtar kontrolü başarısız (parola yanlış olabilir):`n$($r.Cikti)"
    }

    # ------------------------------------------------------------------
    Adim "7/8 Derleme (build_release.ps1) - uzun sürer"
    $bp = @{ PythonKopya = $PythonKopya; OzelAnahtar = $OzelAnahtar; ZamanSunucu = $ZamanSunucu }
    if ($Imzali) {
        if ($SignToolArgs.Count -eq 0) { Dur "-Imzali için -SignToolArgs gerekli (örn. @('/sha1','PARMAK_IZI'))." }
        $bp.SignToolArgs = $SignToolArgs

        # signtool PATH'te olmayabilir (Windows SDK içinde durur)
        if (-not (Get-Command signtool -ErrorAction SilentlyContinue)) {
            $st = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
                  Sort-Object FullName -Descending | Select-Object -First 1
            if (-not $st) { Dur "signtool.exe bulunamadı. Visual Studio Installer > Değiştir > 'Windows 10/11 SDK' bileşenini ekle." }
            $env:PATH = "$($st.DirectoryName);$env:PATH"
        }
        Tamam "signtool: $((Get-Command signtool).Source)"

        # 20 dakikalık derlemeden ÖNCE: sertifika, PIN/token ve zaman damgası gerçekten çalışıyor mu?
        $deneme = Join-Path $env:TEMP "turkod_imza_testi.exe"
        Copy-Item "$env:WINDIR\System32\where.exe" $deneme -Force
        Uyari "Deneme imzası atılıyor (token/kart kullanıyorsan PIN penceresi çıkabilir)..."
        $r = CalistirSessiz "signtool" (@("sign", "/fd", "sha256", "/tr", $ZamanSunucu, "/td", "sha256") + $SignToolArgs + @($deneme))
        if ($r.Kod -ne 0) { Dur "Deneme imzası başarısız. -SignToolArgs / sertifika / PIN / zaman sunucusunu kontrol et:`n$($r.Cikti)" }
        $r = CalistirSessiz "signtool" @("verify", "/pa", $deneme)
        Remove-Item $deneme -Force -ErrorAction SilentlyContinue
        if ($r.Kod -ne 0) { Dur "İmza atıldı ama Windows güvenmiyor (sertifika zinciri/kök):`n$($r.Cikti)" }
        Tamam "Sertifika, zaman damgası ve zincir çalışıyor"
    } else {
        $bp.ImzasizTest = $true
        Uyari "Authenticode imzası ATLANIYOR (deneme derlemesi). Dağıtım için -Imzali kullan."
    }
    if ($IndirmeUrl) { $bp.IndirmeUrl = $IndirmeUrl }
    if ($SadeceInno) { $bp.SadeceInno = $true }

    $crt = Get-ChildItem -Path @(
            "${env:ProgramFiles}\Microsoft Visual Studio\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT",
            "${env:ProgramFiles(x86)}\Microsoft Visual Studio\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT") `
        -Directory -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($crt) { $bp.VcCrtDizini = $crt.FullName; Tamam "VC++ çalışma zamanı DLL'leri: $($crt.FullName)" }
    else { Uyari "Visual Studio VC++ DLL klasörü bulunamadı; temiz makinede Flutter exe açılmayabilir." }

    & (Join-Path $Kok "build_release.ps1") @bp

    # ------------------------------------------------------------------
    Adim "8/8 Paket testi"
    $paket = Join-Path $Kok "dist\TurKod"
    $kurulum = Join-Path $Kok "dist\TurKod-Setup-$surum.exe"
    $hatalar = @()

    foreach ($f in @("turkod_flutter.exe", "flutter_windows.dll", "backend\turkod_backend.exe",
                     "backend\turkod_ide.manifest.json", "backend\turkod_ide.manifest.json.sig",
                     "backend\_internal\python_embed\python.exe", "backend\_internal\TurKod_Sozluk.txt",
                     "backend\_internal\surum.txt")) {
        if (-not (Test-Path (Join-Path $paket $f))) { $hatalar += "Pakette eksik: $f" }
    }
    if (-not (Test-Path $kurulum)) { $hatalar += "Kurulum dosyası yok: $kurulum" }

    $pe = Join-Path $paket "backend\_internal\python_embed\python.exe"
    if (Test-Path $pe) {
        $r = CalistirSessiz $pe @("-I", "-X", "utf8", "-c", "import tkinter, turtle, ssl, sqlite3, pygame, sympy; print('ok')")
        if ($r.Kod -eq 0) { Tamam "python_embed: tkinter, turtle, pygame, sympy içe aktarılıyor" }
        else { $hatalar += "python_embed içe aktarma hatası:`n$($r.Cikti)" }
    }

    $backend = Join-Path $paket "backend\turkod_backend.exe"
    if (Test-Path $backend) {
        $port = 18765
        $portDosyasi = Join-Path $env:TEMP "turkod_backend_port"
        $proc = Start-Process -FilePath $backend -ArgumentList @("--backend", "--port", "$port") -PassThru -WindowStyle Hidden
        try {
            $ayakta = $false
            for ($i = 0; $i -lt 60; $i++) {
                Start-Sleep -Milliseconds 500
                try {
                    $yanit = Invoke-RestMethod -Uri "http://127.0.0.1:$port/" -TimeoutSec 2
                    if ($yanit.servis) { $ayakta = $true; break }
                } catch { }
            }
            if (-not $ayakta) {
                $logYolu = Join-Path $env:LOCALAPPDATA "TurKod\backend.log"
                $sonSatirlar = ""
                if (Test-Path $logYolu) { $sonSatirlar = "`nbackend.log son satırlar:`n" + ((Get-Content $logYolu -Tail 15) -join "`n") }
                $hatalar += "Paketlenmiş backend 30 sn içinde açılmadı.$sonSatirlar"
            } else {
                Tamam "Backend paketten açıldı"
                try {
                    $imza = WsCagri $port "imza_dogrula"
                    if ($imza.result.basarili -eq $true) { Tamam "Manifest imzası: $($imza.result.mesaj)" }
                    else { $hatalar += "Manifest doğrulaması BAŞARISIZ: $($imza.result.mesaj) - $($imza.result.detay)" }

                    $gun = WsCagri $port "guncelleme_kontrol"
                    if ($gun.error -match "Bilinmeyen komut") { $hatalar += "Pakette güncelleme komutları yok (server.py)." }
                    elseif ($gun.result.hata) { Uyari "Güncelleme kontrolü: $($gun.result.hata) (GitHub'da yayın yoksa beklenen)" }
                    else { Tamam "Güncelleme kontrolü çalıştı (yeni sürüm var mı: $($gun.result.guncelleme_var))" }

                    $dur = WsCagri $port "guncelleme_indir_durum"
                    if ($dur.error -match "Bilinmeyen komut") { $hatalar += "Pakette güncelleme indirme komutları yok (server.py yaması)." }
                    else { Tamam "Güncelleme indirme komutları hazır" }
                } catch { $hatalar += "WebSocket testi başarısız: $($_.Exception.Message)" }
            }
        } finally {
            & taskkill.exe /F /T /PID $proc.Id 2>&1 | Out-Null
            Remove-Item $portDosyasi -Force -ErrorAction SilentlyContinue
        }
    }

    # Backend, arayüz (ebeveyn) kapanınca kendiliğinden kapanıyor mu? (--parent-pid)
    if (Test-Path $backend) {
        $port2 = 18766
        $yardimci = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 600") -PassThru -WindowStyle Hidden
        $b2 = Start-Process -FilePath $backend -ArgumentList @("--backend", "--port", "$port2", "--parent-pid", "$($yardimci.Id)") -PassThru -WindowStyle Hidden
        try {
            $ayakta2 = $false
            for ($i = 0; $i -lt 60; $i++) {
                Start-Sleep -Milliseconds 500
                try {
                    $y2 = Invoke-RestMethod -Uri "http://127.0.0.1:$port2/" -TimeoutSec 2
                    if ($y2.servis) { $ayakta2 = $true; break }
                } catch { }
            }
            if (-not $ayakta2) {
                $hatalar += "Ebeveyn-izleme testi: backend 30 sn içinde açılmadı."
            } else {
                Stop-Process -Id $yardimci.Id -Force          # "arayüz kapandı"
                if ($b2.WaitForExit(15000)) { Tamam "Backend, arayüz kapanınca kendiliğinden kapandı" }
                else { $hatalar += "Backend, ebeveyn kapandıktan 15 sn sonra da kapanmadı (--parent-pid izleme çalışmıyor)." }
            }
        } finally {
            if (-not $b2.HasExited) { & taskkill.exe /F /T /PID $b2.Id 2>&1 | Out-Null }
            if (-not $yardimci.HasExited) { Stop-Process -Id $yardimci.Id -Force -ErrorAction SilentlyContinue }
            Remove-Item (Join-Path $env:TEMP "turkod_backend_port") -Force -ErrorAction SilentlyContinue
        }
    }

    # Paketlenmiş backend gerekli kütüphaneleri (openai, anthropic, groq, ...) içe aktarabiliyor mu?
    # (PyInstaller uyarıları "bulunamadı" dese de asıl kanıt budur.)
    if (Test-Path $backend) {
        $st = Start-Process -FilePath $backend -ArgumentList @("--selftest") -Wait -PassThru -WindowStyle Hidden
        $logYolu2 = Join-Path $env:LOCALAPPDATA "TurKod\backend.log"
        $selftestSatirlari = @()
        if (Test-Path $logYolu2) { $selftestSatirlari = @(Get-Content $logYolu2 -Tail 60 | Where-Object { $_ -match "\[selftest\]" }) }
        if ($st.ExitCode -eq 0) {
            Tamam "Paketlenmiş backend: gerekli kütüphanelerin hepsi içe aktarılıyor"
            $uyarilar = @($selftestSatirlari | Where-Object { $_ -match "UYARI" })
            foreach ($u in $uyarilar) { Uyari $u }
        } else {
            $hatalar += "Paketlenmiş backend'de eksik kütüphane var (selftest çıkış kodu $($st.ExitCode)):`n$($selftestSatirlari -join "`n")"
        }
    }

    if ($Imzali) {
        foreach ($f in @((Join-Path $paket "turkod_flutter.exe"), $backend, $kurulum)) {
            $r = CalistirSessiz "signtool" @("verify", "/pa", $f)
            if ($r.Kod -eq 0) { Tamam "Authenticode imzası geçerli: $(Split-Path $f -Leaf)" }
            else { $hatalar += "Authenticode imzası doğrulanamadı: $f`n$($r.Cikti)" }
        }
    }

    if ($hatalar.Count -gt 0) {
        Write-Host "`nPAKET TESTİ BAŞARISIZ:" -ForegroundColor Red
        $hatalar | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
        throw "Paket testi $($hatalar.Count) sorun buldu."
    }

    # ------------------------------------------------------------------
    $mb = [Math]::Round((Get-Item $kurulum).Length / 1MB, 1)
    Write-Host "`n================================================================" -ForegroundColor Green
    Write-Host " TAMAM  ($([int]$Saat.Elapsed.TotalMinutes) dk)   Sürüm $surum" -ForegroundColor Green
    Write-Host " Kurulum : $kurulum  ($mb MB)" -ForegroundColor Green
    Write-Host " Klasör  : $paket" -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "Sonraki adımlar:"
    Write-Host "  1) $paket\turkod_flutter.exe dosyasını çalıştırıp elle dene (editör, çalıştır, kaplumbaga, pygame)."
    Write-Host "  2) Setup dosyasını temiz bir Windows VM'de kur ve aynı denemeleri yap."
    Write-Host "  3) Dağıtım için sertifika al, -Imzali ve -IndirmeUrl ile yeniden çalıştır."
    Start-Process explorer.exe (Join-Path $Kok "dist")
}
catch {
    Write-Host "`nHATA: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Bu mesajı olduğu gibi gönder; hangi adımda durduğu yukarıdaki '=== n/8' satırından anlaşılır." -ForegroundColor DarkYellow
    exit 1
}
finally {
    if ($parolaBizAyarladik) { Remove-Item Env:\TURKOD_KEY_PASS -ErrorAction SilentlyContinue }
}
