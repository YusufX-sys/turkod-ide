#!/usr/bin/env python3
"""TürKod kaynak kodu imzalama aracı — tek dosya, başka bir betiğe bağımlı değil.

Ne yapar:
  - Bir kaynak klasöründeki (varsayılan: turkod_ide) her dosyanın SHA-256'sını
    içeren bir manifest (turkod_ide.manifest.json) üretir.
  - Bu manifesti RSA-PSS (SHA-256) ile imzalar (turkod_ide.manifest.json.sig).
  - İmzayı, signing.py içine GÖMÜLÜ public key ile kendi kendine doğrular; yanlış
    özel anahtarla (public key'in eşi olmayan) imzalamayı engeller.
  - --dogrula ile, özel anahtar OLMADAN, yalnızca public key kullanarak mevcut
    manifestin dosyalarla hâlâ eşleştiğini kontrol eder (CI/CD veya herkes için).

Kullanım:
  Yeni anahtar çifti üret (bir kez; public key'i signing.py'ye elle koy):
      python kaynak_imzala.py --anahtar-uret C:\\gizli\\turkod

  Kaynak kodu imzala (her kod değişikliğinden sonra / her release'te):
      python kaynak_imzala.py --imzala --surum 3.0.0 --ozel-anahtar C:\\gizli\\turkod_private.pem

  Doğrula (özel anahtar gerekmez):
      python kaynak_imzala.py --dogrula

Varsayılan hedef klasör: bu betiğin yanındaki 'turkod_ide' (yoksa betiğin
bulunduğu klasörün kendisi — betik turkod_ide\\ içine konursa da çalışır).
--dizin ile başka bir klasör verilebilir.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path

MANIFEST_ADI = "turkod_ide.manifest.json"
SIG_ADI = MANIFEST_ADI + ".sig"

# Kaynak kodun parçası olmayan, imzaya girmemesi gereken dosya/klasörler.
HER_ZAMAN_HARIC = [
    "__pycache__/*", "*/__pycache__/*", "*.pyc", "*.pyo",
    MANIFEST_ADI, SIG_ADI,
    ".git/*", ".git", ".vscode/*", ".idea/*", ".kilo/*",
    ".turkod_kelimeler.json",
]

_PUBLIC_KEY_RE = re.compile(
    r'TURKOD_PUBLIC_KEY\s*=\s*"""(-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----)"""',
    re.DOTALL,
)


def _betik_dizini() -> Path:
    return Path(__file__).resolve().parent


def _varsayilan_hedef() -> Path:
    yaninda = _betik_dizini() / "turkod_ide"
    if yaninda.is_dir():
        return yaninda
    return _betik_dizini()


def _signing_py_bul(hedef: Path) -> Path | None:
    for aday in (hedef / "signing.py", _betik_dizini() / "signing.py",
                 _betik_dizini() / "turkod_ide" / "signing.py"):
        if aday.is_file():
            return aday
    return None


def _gomulu_public_key_pem(hedef: Path) -> str:
    """signing.py içindeki TURKOD_PUBLIC_KEY'i döndürür (tek doğruluk kaynağı)."""
    yol = _signing_py_bul(hedef)
    if yol is None:
        sys.exit("HATA: signing.py bulunamadı; public key okunamadı.")
    metin = yol.read_text(encoding="utf-8")
    m = _PUBLIC_KEY_RE.search(metin)
    if not m:
        sys.exit(f"HATA: {yol} içinde TURKOD_PUBLIC_KEY bulunamadı.")
    return m.group(1)


def _sha256_dosya(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _dosyalari_tara(hedef: Path, ek_haric: list[str]) -> list[dict]:
    hedef = hedef.resolve()
    desenler = HER_ZAMAN_HARIC + list(ek_haric)
    girisler = []
    for yol in sorted(p for p in hedef.rglob("*") if p.is_file()):
        rel = yol.relative_to(hedef).as_posix()
        if any(fnmatch.fnmatch(rel, d) for d in desenler):
            continue
        girisler.append({"path": rel, "sha256": _sha256_dosya(yol), "size": yol.stat().st_size})
    return girisler


def _parola(istemde: str) -> str:
    return os.environ.get("TURKOD_KEY_PASS") or getpass.getpass(istemde)


# ----------------------------------------------------------------------------
def anahtar_uret(onek: str) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    parola = _parola("Yeni özel anahtar için parola belirle: ").encode("utf-8")
    if not parola:
        sys.exit("Parola boş olamaz.")

    anahtar = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ozel_yol = Path(onek + "_private.pem")
    genel_yol = Path(onek + "_public.pem")

    ozel_yol.write_bytes(anahtar.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(parola)))
    genel_yol.write_bytes(anahtar.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))

    print(f"Yazıldı:\n  {ozel_yol}  (GİZLİ — depoya, paylaşılan klasöre koyma)\n  {genel_yol}")
    print(f"\nSonraki adım: {genel_yol} içeriğini signing.py'deki TURKOD_PUBLIC_KEY'e yapıştır.")


def imzala(hedef: Path, surum: str, ozel_anahtar_yolu: str, ek_haric: list[str]) -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    if not hedef.is_dir():
        sys.exit(f"Klasör yok: {hedef}")

    girisler = _dosyalari_tara(hedef, ek_haric)
    if not girisler:
        sys.exit("Manifest'e girecek dosya bulunamadı (hepsi hariç tutulmuş olabilir).")

    manifest_bayt = json.dumps(
        {"version": surum, "files": girisler}, ensure_ascii=False, indent=2,
    ).encode("utf-8")

    veri = Path(ozel_anahtar_yolu).read_bytes()
    try:
        ozel_anahtar = serialization.load_pem_private_key(veri, password=None)
    except TypeError:
        parola = _parola("Özel anahtar parolası: ").encode("utf-8")
        ozel_anahtar = serialization.load_pem_private_key(veri, password=parola)

    # Yanlış (signing.py'deki public key'in eşi olmayan) özel anahtarla imzalamayı
    # baştan engelle: sessizce doğrulanamaz bir manifest üretmek yerine hemen dur.
    gomulu_pem = _gomulu_public_key_pem(hedef).encode("utf-8")
    gomulu_public = serialization.load_pem_public_key(gomulu_pem)
    if gomulu_public.public_numbers() != ozel_anahtar.public_key().public_numbers():
        sys.exit("HATA: Bu özel anahtar, signing.py'deki TURKOD_PUBLIC_KEY'in eşi değil.\n"
                 "       Doğru özel anahtarı ver ya da önce signing.py'yi bu anahtarın "
                 "public key'iyle güncelle.")

    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    imza = ozel_anahtar.sign(manifest_bayt, pss, hashes.SHA256())
    gomulu_public.verify(imza, manifest_bayt, pss, hashes.SHA256())  # öz-doğrulama

    (hedef / MANIFEST_ADI).write_bytes(manifest_bayt)
    (hedef / SIG_ADI).write_text(base64.b64encode(imza).decode("ascii"), encoding="utf-8")

    print(f"İmzalandı: {len(girisler)} dosya, sürüm {surum}")
    print(f"  {hedef / MANIFEST_ADI}\n  {hedef / SIG_ADI}")
    print("\nGit'e eklemeyi unutma:")
    print(f"  git add {(hedef / MANIFEST_ADI).as_posix()} {(hedef / SIG_ADI).as_posix()}")


def dogrula(hedef: Path, ek_haric: list[str]) -> bool:
    """Yalnızca public key ile: manifest imzası geçerli mi ve dosyalar hâlâ eşleşiyor mu?
    Özel anahtar gerekmez; CI/CD'de ya da herkes tarafından çalıştırılabilir."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    manifest_yol = hedef / MANIFEST_ADI
    sig_yol = hedef / SIG_ADI
    if not manifest_yol.is_file() or not sig_yol.is_file():
        print(f"HATA: {MANIFEST_ADI} veya {SIG_ADI} bulunamadı: {hedef}")
        return False

    manifest_bayt = manifest_yol.read_bytes()
    try:
        imza = base64.b64decode(sig_yol.read_text(encoding="utf-8").strip())
    except Exception as e:
        print(f"HATA: İmza Base64 formatında değil: {e}")
        return False

    public_key = serialization.load_pem_public_key(_gomulu_public_key_pem(hedef).encode("utf-8"))
    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    try:
        public_key.verify(imza, manifest_bayt, pss, hashes.SHA256())
    except Exception:
        print("HATA: Manifest imzası GEÇERSİZ (dosya değiştirilmiş ya da başka bir anahtarla imzalanmış).")
        return False
    print("İmza geçerli.")

    manifest = json.loads(manifest_bayt.decode("utf-8"))
    print(f"Sürüm: {manifest.get('version', 'bilinmiyor')} | dosya sayısı: {len(manifest.get('files', []))}")

    guncel = {g["path"]: g for g in _dosyalari_tara(hedef, ek_haric)}
    kayitli = {g["path"]: g for g in manifest.get("files", [])}

    sorun = False
    for yol, kayit in kayitli.items():
        if yol not in guncel:
            print(f"  EKSİK: {yol}")
            sorun = True
        elif guncel[yol]["sha256"] != kayit["sha256"]:
            print(f"  DEĞİŞMİŞ: {yol}")
            sorun = True
    for yol in guncel:
        if yol not in kayitli:
            print(f"  YENİ (manifestte yok): {yol}")
            sorun = True

    if sorun:
        print("\nSonuç: kaynak kod, imzalandığı hâlden FARKLI. Yeniden imzalamak için --imzala kullan.")
        return False
    print("\nSonuç: kaynak kod, imzalandığı hâlle birebir aynı.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dizin", default=None, help="İmzalanacak/doğrulanacak kaynak klasörü (varsayılan: turkod_ide)")
    ap.add_argument("--haric", action="append", default=[],
                    help="posix yolu üzerinde fnmatch deseni; birden fazla kez verilebilir")
    grup = ap.add_mutually_exclusive_group(required=True)
    grup.add_argument("--anahtar-uret", metavar="ONEK", help="Yeni RSA anahtar çifti üret ve çık")
    grup.add_argument("--imzala", action="store_true", help="Kaynak klasörünü imzala")
    grup.add_argument("--dogrula", action="store_true", help="Mevcut imzayı doğrula (özel anahtar gerekmez)")
    ap.add_argument("--surum", default="0.0.0", help="--imzala ile: manifest'e yazılacak sürüm")
    ap.add_argument("--ozel-anahtar", help="--imzala için zorunlu: özel anahtar dosyası (.pem)")
    a = ap.parse_args()

    hedef = Path(a.dizin).resolve() if a.dizin else _varsayilan_hedef()

    if a.anahtar_uret:
        anahtar_uret(a.anahtar_uret)
        return 0
    if a.imzala:
        if not a.ozel_anahtar:
            ap.error("--imzala için --ozel-anahtar zorunlu")
        imzala(hedef, a.surum, a.ozel_anahtar, a.haric)
        return 0
    if a.dogrula:
        return 0 if dogrula(hedef, a.haric) else 1
    return 1  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
