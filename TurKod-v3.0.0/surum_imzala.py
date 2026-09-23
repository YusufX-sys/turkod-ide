"""Release aracı - pakete KONMAZ.

Kurulum dosyasından latest.json üretir ve manifest ile AYNI özel anahtarla imzalar.
    python surum_imzala.py --kurulum dist\\TurKod-Setup-3.0.0.exe ^
        --url https://github.com/KULLANICI/DEPO/releases/download/v3.0.0/TurKod-Setup-3.0.0.exe ^
        --ozel-anahtar D:\\gizli\\turkod_private.pem [--notlar "Neler değişti"]

Çıktı: kurulum dosyasının yanında latest.json ve latest.json.sig.
Üçünü (Setup.exe, latest.json, latest.json.sig) aynı yayına yükle.
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from manifest_imzala import _gomulu_public_key, _ozel_anahtar_yukle, _sha256


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kurulum", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--ozel-anahtar", required=True)
    ap.add_argument("--notlar", default="")
    a = ap.parse_args()

    kurulum = Path(a.kurulum).resolve()
    surum = (Path(__file__).resolve().parent / "surum.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", surum):
        sys.exit(f"surum.txt geçersiz: {surum!r}")
    if not a.url.lower().startswith("https://"):
        sys.exit("--url https ile başlamalı.")
    if not kurulum.is_file():
        sys.exit(f"Kurulum dosyası yok: {kurulum}")

    bildirim = {
        "version": surum,
        "url": a.url,
        "sha256": _sha256(kurulum),
        "size": kurulum.stat().st_size,
        "notes": a.notlar,
    }
    veri = json.dumps(bildirim, ensure_ascii=False, indent=2).encode("utf-8")

    anahtar = _ozel_anahtar_yukle(a.ozel_anahtar)
    gomulu = _gomulu_public_key()
    if gomulu is not None and gomulu.public_numbers() != anahtar.public_key().public_numbers():
        sys.exit("HATA: Bu özel anahtar signing.py'deki public key'in eşi değil.")

    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    imza = anahtar.sign(veri, pss, hashes.SHA256())
    anahtar.public_key().verify(imza, veri, pss, hashes.SHA256())

    (kurulum.parent / "latest.json").write_bytes(veri)
    (kurulum.parent / "latest.json.sig").write_text(base64.b64encode(imza).decode("ascii"), encoding="utf-8")
    print(f"latest.json ve latest.json.sig yazıldı: {kurulum.parent} (sürüm {surum})")


if __name__ == "__main__":
    main()
