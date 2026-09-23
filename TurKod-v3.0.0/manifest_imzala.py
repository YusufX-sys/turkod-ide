"""Build aracı - pakete KONMAZ.

signing.py'nin beklediği biçimde manifest üretir ve RSA-PSS (SHA-256,
MGF1-SHA256, salt=MAX_LENGTH) ile imzalar.

Anahtar çifti (bir kez; public key'i signing.py'deki TURKOD_PUBLIC_KEY'e koy):
    python manifest_imzala.py --anahtar-uret D:\\gizli\\turkod

İmzalama (Authenticode imzasından SONRA çalıştır; hash'ler o zaman değişir):
    python manifest_imzala.py --dizin dist\\TurKod\\backend --surum 2.2.0 ^
        --ozel-anahtar D:\\gizli\\turkod_private.pem ^
        --haric "_internal/python_embed/*"
"""
import argparse
import base64
import fnmatch
import getpass
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

MANIFEST_ADI = "turkod_ide.manifest.json"
SIG_ADI = MANIFEST_ADI + ".sig"
HER_ZAMAN_HARIC = ["__pycache__/*", "*/__pycache__/*", "*.pyc", ".turkod_kelimeler.json"]


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _parola():
    return os.environ.get("TURKOD_KEY_PASS") or getpass.getpass("Özel anahtar parolası: ")


def anahtar_uret(onek: str):
    parola = _parola().encode("utf-8")
    anahtar = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    Path(onek + "_private.pem").write_bytes(anahtar.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(parola)))
    Path(onek + "_public.pem").write_bytes(anahtar.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Yazıldı: {onek}_private.pem (GİZLİ, repoya koyma) ve {onek}_public.pem")


def _ozel_anahtar_yukle(yol: str):
    veri = Path(yol).read_bytes()
    try:
        return serialization.load_pem_private_key(veri, password=None)
    except TypeError:  # parolalı
        return serialization.load_pem_private_key(veri, password=_parola().encode("utf-8"))


def _gomulu_public_key():
    """signing.py içindeki public key; yanlış özel anahtarla imzayı engellemek için."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from turkod_ide.signing import DijitalImza
        return serialization.load_pem_public_key(DijitalImza.TURKOD_PUBLIC_KEY.encode("utf-8"))
    except Exception as e:
        print(f"UYARI: signing.py public key karşılaştırması yapılamadı: {e}")
        return None


def anahtar_kontrol(yol: str):
    """Uzun derlemeye başlamadan önce: özel anahtar signing.py'deki public key'in eşi mi?"""
    anahtar = _ozel_anahtar_yukle(yol)
    gomulu = _gomulu_public_key()
    if gomulu is None:
        sys.exit("HATA: signing.py'deki public key okunamadı.")
    if gomulu.public_numbers() != anahtar.public_key().public_numbers():
        sys.exit("HATA: Bu özel anahtar signing.py'deki public key'in eşi değil.\n"
                 "Ya doğru özel anahtarı ver ya da anahtarın _public.pem içeriğini "
                 "signing.py'deki TURKOD_PUBLIC_KEY'e yapıştır.")
    print("Özel anahtar signing.py'deki public key ile eşleşiyor.")


def imzala(dizin: str, surum: str, ozel_anahtar: str, haric):
    kok = Path(dizin).resolve()
    if not kok.is_dir():
        sys.exit(f"Dizin yok: {kok}")

    desenler = HER_ZAMAN_HARIC + list(haric)
    girisler = []
    for yol in sorted(p for p in kok.rglob("*") if p.is_file()):
        rel = yol.relative_to(kok).as_posix()
        if rel in (MANIFEST_ADI, SIG_ADI):
            continue
        if any(fnmatch.fnmatch(rel, d) for d in desenler):
            continue
        girisler.append({"path": rel, "sha256": _sha256(yol), "size": yol.stat().st_size})

    if not girisler:
        sys.exit("Manifest'e girecek dosya bulunamadı.")

    # İmzalanan bayt dizisi, diske yazılan bayt dizisiyle birebir aynı olmalı.
    manifest_bayt = json.dumps(
        {"version": surum, "files": girisler}, ensure_ascii=False, indent=2
    ).encode("utf-8")
    (kok / MANIFEST_ADI).write_bytes(manifest_bayt)

    anahtar = _ozel_anahtar_yukle(ozel_anahtar)
    gomulu = _gomulu_public_key()
    if gomulu is not None and gomulu.public_numbers() != anahtar.public_key().public_numbers():
        (kok / MANIFEST_ADI).unlink()
        sys.exit("HATA: Bu özel anahtar signing.py'deki public key'in eşi değil.")

    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    imza = anahtar.sign(manifest_bayt, pss, hashes.SHA256())
    anahtar.public_key().verify(imza, manifest_bayt, pss, hashes.SHA256())  # öz-doğrulama

    (kok / SIG_ADI).write_text(base64.b64encode(imza).decode("ascii"), encoding="utf-8")
    print(f"Manifest imzalandı: {len(girisler)} dosya, sürüm {surum}")
    print(f"  {kok / MANIFEST_ADI}\n  {kok / SIG_ADI}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anahtar-uret", metavar="ONEK")
    ap.add_argument("--anahtar-kontrol", metavar="PEM")
    ap.add_argument("--dizin")
    ap.add_argument("--surum", default="0.0.0")
    ap.add_argument("--ozel-anahtar")
    ap.add_argument("--haric", action="append", default=[],
                    help="posix yolu üzerinde fnmatch deseni; birden fazla verilebilir")
    a = ap.parse_args()

    if a.anahtar_uret:
        anahtar_uret(a.anahtar_uret)
    elif a.anahtar_kontrol:
        anahtar_kontrol(a.anahtar_kontrol)
    elif a.dizin and a.ozel_anahtar:
        imzala(a.dizin, a.surum, a.ozel_anahtar, a.haric)
    else:
        ap.error("--anahtar-uret ya da (--dizin ve --ozel-anahtar) gerekli")
