<#
TürKod: klasörü GitHub'a yüklemeden önce düzenler.

Proje klasörünün İÇİNDEN değil, bir üst dizinden çalıştır (klasörü yeniden
adlandıracağı için kendi içinden çalıştırılamaz):

    cd "C:\Users\261437\Downloads"
    powershell -ExecutionPolicy Bypass -File ".\TurKod v2.2.0f\duzenle_ve_hazirla.ps1"

Ya da betiği kopyalamadan, tam yol vererek:

    powershell -ExecutionPolicy Bypass -File "C:\Users\261437\Downloads\TurKod v2.2.0f\duzenle_ve_hazirla.ps1" `
        -Kaynak "C:\Users\261437\Downloads\TurKod v2.2.0f"

Yaptıkları (sırayla):
  1. Yedek/önbellek/IDE-özel dosyaları siler (*.bak, *.bak-*, __pycache__, .idea, .kilo, .vscode)
  2. dist/, build/, .dart_tool/, ephemeral/ klasörlerine DOKUNMAZ (yerelde kalsın diye;
     zaten .gitignore onları commit dışı tutar) — silmek istersen -DerlemeCiktilariniSil ekle
  3. .gitignore'u doğru içerikle yazar (eskisi varsa yedekler)
  4. Zorunlu dosyaların (LICENSE, README.md, surum.txt, sorumluluk_reddi.txt) var olduğunu
     denetler; eksikse uyarır (durdurmaz)
  5. Klasörü -Hedef ile verilen isme yeniden adlandırır (varsayılan: TurKod-v3.0.0)

Hiçbir adım git komutu ÇALIŞTIRMAZ; git add/commit/push'u sen yaparsın.
#>
param(
    [string]$Kaynak = $PSScriptRoot,
    [string]$Hedef = "TurKod-v3.0.0",
    [switch]$DerlemeCiktilariniSil,
    [switch]$Zorla   # onay istemeden çalıştır
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

function Adim($m)  { Write-Host "`n=== $m" -ForegroundColor Cyan }
function Tamam($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Uyari($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }

if (-not (Test-Path $Kaynak -PathType Container)) { throw "Kaynak klasör yok: $Kaynak" }
$Kaynak = (Resolve-Path $Kaynak).Path.TrimEnd('\')
$Ust    = Split-Path $Kaynak -Parent
$HedefTam = Join-Path $Ust $Hedef

Write-Host "Kaynak : $Kaynak"
Write-Host "Hedef  : $HedefTam"

# ----------------------------------------------------------------------------
Adim "1/5 Yedek ve önbellek dosyalarını temizle"
$silinecekDesenler = @("*.bak", "*.bak-*")
$silinenDosya = 0
foreach ($desen in $silinecekDesenler) {
    Get-ChildItem -Path $Kaynak -Recurse -File -Filter $desen -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force; $silinenDosya++ }
}
Tamam "$silinenDosya yedek dosyası silindi"

$silinecekKlasorAdlari = @("__pycache__", ".idea", ".vscode", ".kilo")
$silinenKlasor = 0
foreach ($ad in $silinecekKlasorAdlari) {
    Get-ChildItem -Path $Kaynak -Recurse -Directory -Filter $ad -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending |
        ForEach-Object {
            if (Test-Path $_.FullName) {
                Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                $silinenKlasor++
            }
        }
}
Tamam "$silinenKlasor önbellek/IDE klasörü silindi (__pycache__, .idea, .vscode, .kilo)"

Get-ChildItem -Path $Kaynak -Recurse -File -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

# ----------------------------------------------------------------------------
Adim "2/5 Derleme çıktıları"
$deriveKlasorleri = @(
    (Join-Path $Kaynak "dist"),
    (Join-Path $Kaynak "build"),
    (Join-Path $Kaynak "turkod_flutter\build"),
    (Join-Path $Kaynak "turkod_flutter\.dart_tool"),
    (Join-Path $Kaynak "turkod_flutter\windows\flutter\ephemeral")
)
if ($DerlemeCiktilariniSil) {
    foreach ($k in $deriveKlasorleri) {
        if (Test-Path $k) { Remove-Item $k -Recurse -Force; Tamam "silindi: $k" }
    }
} else {
    $varOlanlar = $deriveKlasorleri | Where-Object { Test-Path $_ }
    if ($varOlanlar) {
        Uyari "Şunlar yerelde kalıyor (silinmedi, .gitignore zaten commit dışı tutar):"
        $varOlanlar | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkYellow }
        Write-Host "       Silmek için: -DerlemeCiktilariniSil" -ForegroundColor DarkYellow
    } else {
        Tamam "Zaten yok, temiz"
    }
}

# ----------------------------------------------------------------------------
Adim "3/5 .gitignore yaz"
$gitignoreYol = Join-Path $Kaynak ".gitignore"
if (Test-Path $gitignoreYol) {
    $yedek = "$gitignoreYol.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Copy-Item $gitignoreYol $yedek
    Uyari "Eski .gitignore yedeklendi: $(Split-Path $yedek -Leaf)"
}
$gitignoreIcerik = @'
# Derleme çıktıları (yeniden üretilir; içindeki .exe/.dll'ler GitHub'ın 100 MB
# dosya sınırını aşar — dist/ ve build/ ASLA depoya girmemeli)
dist/
build/
.dart_tool/
ephemeral/
.flutter-plugins
.flutter-plugins-dependencies

# Python
__pycache__/
*.pyc
*.pyo

# GİZLİ: imzalama anahtarları asla depoya girmemeli
keys/
*_private.pem

# yama_uygula.py'nin ve elle alınan yedekler
*.bak
*.bak-*

# Derleme sırasında üretilen / yeniden üretilebilen dosyalar
KURULUM_LISANS.txt
sihirbaz/*.bmp
dist_backend/

# IDE / editör klasörleri
.idea/
.vscode/
.kilo/
*.iml

# Yerel ayarlar / önbellek (makineye özel, kullanıcı verisi)
.turkod_ayarlar.json
.turkod_kelimeler.json
'@
# BOM'suz UTF-8: bazı git istemcileri BOM'lu .gitignore'u yanlış işliyor.
[System.IO.File]::WriteAllText($gitignoreYol, $gitignoreIcerik, (New-Object System.Text.UTF8Encoding($false)))
Tamam ".gitignore yazıldı"

# ----------------------------------------------------------------------------
Adim "4/5 Zorunlu dosya denetimi"
$zorunlular = @("LICENSE", "README.md", "surum.txt", "sorumluluk_reddi.txt",
                "turkod_ide\__init__.py", "turkod_ide\signing.py",
                "turkod_flutter\pubspec.yaml", "turkod_flutter\lib\main.dart")
$eksikVar = $false
foreach ($z in $zorunlular) {
    $tam = Join-Path $Kaynak $z
    if (Test-Path $tam) { Tamam $z }
    else { Uyari "EKSİK: $z"; $eksikVar = $true }
}
if (Test-Path (Join-Path $Kaynak "keys")) {
    Uyari "keys\ klasörü hâlâ kaynak içinde duruyor — .gitignore commit dışı tutar, ama"
    Uyari "istersen bu klasörü kaynak dışına (ör. C:\gizli\) taşı."
}

# ----------------------------------------------------------------------------
Adim "5/5 Klasörü yeniden adlandır"
if (Test-Path $HedefTam) {
    throw "Hedef zaten var: $HedefTam  (önce sil ya da farklı -Hedef ver)"
}
if (-not $Zorla) {
    $cevap = Read-Host "`n'$Kaynak' klasörü '$Hedef' olarak yeniden adlandırılacak. Onaylıyor musun? (E/H)"
    if ($cevap -notmatch '^[EeYy]') { Write-Host "İptal edildi."; exit 1 }
}
Rename-Item -Path $Kaynak -NewName $Hedef
Tamam "Yeniden adlandırıldı: $HedefTam"

if ($eksikVar) {
    Write-Host "`n[!] Eksik dosyalar vardı, yukarıya bak." -ForegroundColor Yellow
}
Write-Host "`nSırada:" -ForegroundColor Green
Write-Host "  cd `"$HedefTam`""
Write-Host "  git status --short   # dist/build/.pdb/.bak GÖRÜNMEMELİ"
Write-Host "  git add ."
Write-Host "  git commit -m `"TürKod 3.0.0`""
Write-Host "  git push"
