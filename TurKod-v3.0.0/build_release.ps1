<#
TürKod release hattı (Windows x64).

Sıra bilinçli: Authenticode imzası dosyayı değiştirir, manifest hash'leri bundan
SONRA alınmalı; kurulum paketi en son imzalanır.

Örnek:
  .\build_release.ps1 `
      -PythonKopya C:\build\py312 `
      -OzelAnahtar D:\gizli\turkod_private.pem `
      -SignToolArgs @('/sha1','SERTIFIKA_PARMAK_IZI') `
      -VcCrtDizini 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Redist\MSVC\14.xx.xxxxx\x64\Microsoft.VC143.CRT'

Sürüm surum.txt'den okunur. İmzasız deneme derlemesi için -ImzasizTest ekle.
Güncelleme bildirimi için -IndirmeUrl 'https://.../TurKod-Setup-X.Y.Z.exe' ekle.
#>
param(
    [string]$Surum = "",   # boşsa surum.txt okunur (tek sürüm kaynağı)
    # Kullanıcı programlarını çalıştıracak TAM CPython klasörü (tkinter/Tcl dahil).
    # Bu klasör ikinci bir installer çalıştırılarak OLUŞTURULMAZ: aynı sürümün
    # installer'ı ikinci kez çalışınca mevcut kurulumu taşır/bozar. Tek kurulumdan,
    # site-packages hariç kopyala:
    #   robocopy "$env:LOCALAPPDATA\Programs\Python\Python312" C:\build\py312 /E /XD site-packages
    #   C:\build\py312\python.exe -m ensurepip
    [Parameter(Mandatory)][string]$PythonKopya,
    [Parameter(Mandatory)][string]$OzelAnahtar,
    [string]$KutuphaneListesi = "kullanici_kutuphaneleri.txt",
    [string[]]$SignToolArgs = @(),
    [string]$ZamanSunucu = "http://timestamp.digicert.com",
    [string]$VcCrtDizini = "",
    [string]$IndirmeUrl = "",   # verilirse latest.json + .sig üretilir (güncelleme bildirimi)
    [switch]$TumPEleriImzala,
    [switch]$ImzasizTest,
    [switch]$SadeceInno   # dist\TurKod hazırsa: yalnızca Inno kurulumunu (ve latest.json) yeniden üret
)

$ErrorActionPreference = "Stop"
$Kok    = $PSScriptRoot
if (-not $Surum) { $Surum = (Get-Content (Join-Path $Kok "surum.txt") -Raw).Trim() }
if ($Surum -notmatch '^\d+\.\d+\.\d+$') { throw "Geçersiz sürüm: '$Surum' (surum.txt: 3.0.0 biçiminde olmalı)" }
$Dist   = Join-Path $Kok "dist"
$Cikis  = Join-Path $Dist "TurKod"
$Flutter = Join-Path $Kok "turkod_flutter"
$FlutterCikti = Join-Path $Flutter "build\windows\x64\runner\Release"

function Adim($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

function Calistir($exe, [string[]]$argumanlar) {
    & $exe @argumanlar
    if ($LASTEXITCODE -ne 0) { throw "$exe hata kodu $LASTEXITCODE ile bitti." }
}

function Imzala([string[]]$dosyalar) {
    if ($ImzasizTest -or $dosyalar.Count -eq 0) { return }
    $taban = @("sign", "/fd", "sha256", "/tr", $ZamanSunucu, "/td", "sha256") + $SignToolArgs
    for ($i = 0; $i -lt $dosyalar.Count; $i += 40) {
        $son = [Math]::Min($i + 39, $dosyalar.Count - 1)
        Calistir "signtool" ($taban + $dosyalar[$i..$son])
    }
}

# --- 0. Ön kontrol (uzun derlemeden ÖNCE) --------------------------------
Adim "0/8 Ön kontrol"
foreach ($k in "flutter", "pyinstaller", "python") {
    if (-not (Get-Command $k -ErrorAction SilentlyContinue)) { throw "$k bulunamadı (PATH'te değil)." }
}
if (-not $ImzasizTest -and -not (Get-Command "signtool" -ErrorAction SilentlyContinue)) {
    throw "signtool bulunamadı (Windows SDK). Sertifikasız deneme için -ImzasizTest kullan."
}
$isccAdaylari = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe", "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe")
$iscc = $isccAdaylari | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup bulunamadı. https://jrsoftware.org/isdl.php adresinden Inno Setup 6'yı kur." }
if (-not (Test-Path (Join-Path $PythonKopya "python.exe"))) { throw "PythonKopya içinde python.exe yok: $PythonKopya" }
if (-not (Test-Path $OzelAnahtar)) { throw "Özel anahtar yok: $OzelAnahtar" }
if (-not $env:TURKOD_KEY_PASS -and (Select-String -Path $OzelAnahtar -Pattern "ENCRYPTED" -Quiet)) {
    $g = Read-Host "Manifest özel anahtarının parolası" -AsSecureString
    $env:TURKOD_KEY_PASS = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($g))
}
Calistir "python" @((Join-Path $Kok "manifest_imzala.py"), "--anahtar-kontrol", $OzelAnahtar)

if ($SadeceInno) {
    if (-not (Test-Path (Join-Path $Cikis "backend\turkod_backend.exe"))) {
        throw "-SadeceInno için dist\TurKod hazır olmalı; önce -SadeceInno olmadan tam derleme yap."
    }
    Write-Warning "-SadeceInno: Flutter, PyInstaller, python_embed, imza ve manifest adımları atlanıyor; mevcut dist\TurKod kullanılacak."
} else {
    # --- 1. Flutter ---------------------------------------------------------
    Adim "1/7 Flutter release"
    Push-Location $Flutter
    try { Calistir "flutter" @("build", "windows", "--release") } finally { Pop-Location }

    # --- 2. PyInstaller (onedir) --------------------------------------------
    Adim "2/7 PyInstaller onedir"
    Remove-Item -Recurse -Force $Cikis, (Join-Path $Dist "backend"), (Join-Path $Kok "build\pyi") -ErrorAction SilentlyContinue
    Push-Location $Kok
    try {
        Calistir "pyinstaller" @("--noconfirm", "--clean", "--distpath", $Dist,
                                 "--workpath", (Join-Path $Kok "build\pyi"), "turkod_backend.spec")
    } finally { Pop-Location }

    # --- 3. Kullanıcı kodu için Python çalışma ortamı -----------------------
    Adim "3/7 python_embed (kullanıcı programlarını çalıştıran Python)"
    $PyHedef = Join-Path $Dist "backend\_internal\python_embed"
    robocopy $PythonKopya $PyHedef /E /NFL /NDL /NJH /NJS /NP `
        /XD (Join-Path $PythonKopya "Lib\test") (Join-Path $PythonKopya "Doc") `
            (Join-Path $PythonKopya "Include") (Join-Path $PythonKopya "libs") `
            (Join-Path $PythonKopya "Lib\idlelib") (Join-Path $PythonKopya "Lib\turtledemo") `
        /XF "unins*.exe" | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy başarısız ($LASTEXITCODE)" }
    $global:LASTEXITCODE = 0

    $Py = Join-Path $PyHedef "python.exe"
    $Liste = Join-Path $Kok $KutuphaneListesi
    if (Test-Path $Liste) {
        Calistir $Py @("-m", "pip", "install", "--no-warn-script-location",
                       "--disable-pip-version-check", "-r", $Liste)
    }
    Remove-Item -Recurse -Force (Join-Path $PyHedef "Scripts") -ErrorAction SilentlyContinue  # yolu gömülü .exe başlatıcılar
    # IDE terminalinde `pip install X` çalışsın diye yol bağımsız kısayol:
    Set-Content -Path (Join-Path $PyHedef "pip.cmd") -Value '@"%~dp0python.exe" -m pip %*' -Encoding ASCII
    # Kendi kendine yeten bir Python mı? Uyarı çıkmamalı, sys.prefix kendi klasörü olmalı.
    # (Yolu stdout'a basıp karşılaştırmıyoruz: "TürKod" gibi yollarda kodlama sorunu çıkar.)
    $dogrulama = "import sys, os, tkinter, turtle, ssl, sqlite3, ctypes, pip; sys.exit(0 if os.path.samefile(sys.prefix, sys.argv[1]) else 3)"
    $onceki = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $cikti = & $Py -I -X utf8 -c $dogrulama $PyHedef 2>&1 | ForEach-Object { "$_" }
    $kod = $LASTEXITCODE; $ErrorActionPreference = $onceki
    if ($kod -ne 0 -or ($cikti -join "`n") -match "platform independent") {
        throw "python_embed kendi kendine yetmiyor (çıkış kodu $kod; 3 = prefix başka klasörde):`n$($cikti -join "`n")"
    }
    Write-Host "python_embed OK"

    # --- 4. Birleştir --------------------------------------------------------
    Adim "4/7 Paket düzeni"
    New-Item -ItemType Directory -Path $Cikis -Force | Out-Null
    Copy-Item "$FlutterCikti\*" $Cikis -Recurse -Force
    Copy-Item (Join-Path $Dist "backend") (Join-Path $Cikis "backend") -Recurse -Force

    if ($VcCrtDizini -and (Test-Path $VcCrtDizini)) {
        foreach ($dll in "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll") {
            Copy-Item (Join-Path $VcCrtDizini $dll) $Cikis -Force   # Flutter exe için app-local VC++ runtime
        }
    } else {
        Write-Warning "VC++ runtime DLL'leri eklenmedi; temiz makinede Flutter exe açılmayabilir."
    }

    # --- 5. Authenticode -----------------------------------------------------
    Adim "5/7 Authenticode imzası"
    if ($TumPEleriImzala) {
        $hedef = Get-ChildItem $Cikis -Recurse -File -Include *.exe, *.dll, *.pyd |
            Where-Object { (Get-AuthenticodeSignature $_.FullName).Status -eq "NotSigned" } |
            ForEach-Object FullName
    } else {
        $hedef = @(Get-ChildItem $Cikis -Filter *.exe -File | ForEach-Object FullName) +
                 @(Join-Path $Cikis "backend\turkod_backend.exe")
    }
    Imzala $hedef
    if (-not $ImzasizTest) {
        foreach ($h in @(Join-Path $Cikis "backend\turkod_backend.exe")) {
            Calistir "signtool" @("verify", "/pa", "/all", $h)
        }
    }

    # --- 6. Manifest + RSA imzası (Authenticode'dan sonra!) ------------------
    Adim "6/7 Manifest imzası"
    Calistir "python" @((Join-Path $Kok "manifest_imzala.py"),
                        "--dizin", (Join-Path $Cikis "backend"),
                        "--surum", $Surum,
                        "--ozel-anahtar", $OzelAnahtar,
                        "--haric", "_internal/python_embed/*")
}

# --- 7. Kurulum paketi ---------------------------------------------------
Adim "7/7 Inno Setup"
$Kurulum = Join-Path $Dist "TurKod-Setup-$Surum.exe"
Remove-Item $Kurulum -Force -ErrorAction SilentlyContinue

# Inno, büyük kaynak ikonda "Resource update error: File is too large" verir:
# küçük, çok boyutlu bir kopya üret. Olmazsa varsayılan simgeyle devam et.
$ikonHedef = Join-Path $Dist "turkod_setup.ico"
Remove-Item $ikonHedef -Force -ErrorAction SilentlyContinue
$onceki = $ErrorActionPreference; $ErrorActionPreference = "Continue"
& python (Join-Path $Kok "ikon_kucult.py") (Join-Path $Kok "turkod_ide\turkod.ico") $ikonHedef
$ikonKod = $LASTEXITCODE
$ErrorActionPreference = $onceki
if ($ikonKod -ne 0) {
    Write-Warning "İkon küçültülemedi (Pillow kurulu mu?); kurulum varsayılan simgeyle derlenecek."
    Remove-Item $ikonHedef -Force -ErrorAction SilentlyContinue
}

# Lisans sayfası: LICENSE (MIT) + sorumluluk_reddi.txt birleştirilir. LICENSE'a dokunulmaz.
# İkisi de proje kökündeyse KURULUM_LISANS.txt üretilir; turkod.iss varsa otomatik kullanır.
$lisansKaynak = Join-Path $Kok "LICENSE"
$sorumluluk = Join-Path $Kok "sorumluluk_reddi.txt"
if ((Test-Path $lisansKaynak) -and (Test-Path $sorumluluk)) {
    Get-Content $lisansKaynak, $sorumluluk -Encoding UTF8 | Set-Content (Join-Path $Kok "KURULUM_LISANS.txt") -Encoding UTF8
    Write-Host "KURULUM_LISANS.txt üretildi (lisans + sorumluluk reddi)."
} else {
    Write-Warning "LICENSE ve/veya sorumluluk_reddi.txt proje kökünde yok; kurulumda lisans sayfası çıkmayacak."
}

$isccArgs = @("/DSurum=$Surum", (Join-Path $Kok "turkod.iss"))
$isccLog = Join-Path $Dist "iscc.log"

function IsccCalistir {
    $onceki = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $iscc @isccArgs 2>&1 | Tee-Object -FilePath $isccLog | ForEach-Object { Write-Host $_ }
        return $LASTEXITCODE
    } finally { $ErrorActionPreference = $onceki }
}

$isccKod = IsccCalistir
if ($isccKod -ne 0 -and (Test-Path $ikonHedef) -and (Select-String -Path $isccLog -Pattern "Resource update error|SetupIconFile" -Quiet)) {
    Write-Warning "Inno ikon yüzünden başarısız oldu; ikonsuz yeniden deneniyor."
    Remove-Item $ikonHedef -Force
    $isccKod = IsccCalistir
}
if ($isccKod -ne 0) { throw "ISCC hata kodu $isccKod ile bitti. Ayrıntı: $isccLog" }

# Kurulum dosyasını burada imzala (Inno'nun SignTool'u yerine): argümanlarda boşluk/tırnak sorunu olmaz.
# Not: kaldırıcı (unins000.exe) bu yolla imzalanmaz; SmartScreen zaten yalnızca indirilen Setup'ı denetler.
# latest.json'daki SHA-256 imzadan SONRA hesaplanır (aşağıdaki adım).
if (-not $ImzasizTest) {
    Imzala @($Kurulum)
    Calistir "signtool" @("verify", "/pa", "/all", $Kurulum)
}

# --- 8. Güncelleme bildirimi (latest.json + .sig) -------------------------
if ($IndirmeUrl) {
    Adim "8/8 latest.json"
    Calistir "python" @((Join-Path $Kok "surum_imzala.py"), "--kurulum", $Kurulum,
                        "--url", $IndirmeUrl, "--ozel-anahtar", $OzelAnahtar)
}

Write-Host "`nTamam: $Kurulum" -ForegroundColor Green
