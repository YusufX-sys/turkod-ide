# .gitignore'da eslesen (izlenmeyen) dosya ve klasorleri siler.
# Kullanim:
#   .\gitignore_temizle.ps1          -> sadece listeler (hicbir sey silmez)
#   .\gitignore_temizle.ps1 -Sil     -> listeler, onay ister, sonra siler
param([switch]$Sil)

$ErrorActionPreference = 'Stop'

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Bu klasor bir git reposu degil." -ForegroundColor Red; exit 1 }

Set-Location (git rev-parse --show-toplevel)

# -X: sadece .gitignore'daki dosyalar, -d: klasorler dahil, -n: deneme
$liste = git clean -Xdn
if (-not $liste) { Write-Host "Silinecek ignore edilmis dosya yok." -ForegroundColor Green; exit 0 }

Write-Host "Silinecekler:" -ForegroundColor Yellow
$liste | ForEach-Object { Write-Host "  $($_ -replace '^Would remove ', '')" }
Write-Host "Toplam: $($liste.Count)"

if (-not $Sil) { Write-Host "`nSilmek icin: .\gitignore_temizle.ps1 -Sil" -ForegroundColor Cyan; exit 0 }

$cevap = Read-Host "`nBunlar KALICI olarak silinecek. Emin misiniz? (e/h)"
if ($cevap -ne 'e') { Write-Host "Iptal edildi."; exit 0 }

git clean -Xdf
Write-Host "Temizlendi." -ForegroundColor Green

# Not: Daha once commit'lenmis ama sonradan .gitignore'a eklenmis dosyalar
# git clean ile silinmez. Onlari repodan cikarmak (diskte birakarak) icin:
#   git rm -r --cached <dosya>
