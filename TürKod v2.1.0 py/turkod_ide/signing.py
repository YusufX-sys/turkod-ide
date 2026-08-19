"""Dijital imza doğrulama modülü - Manifest tabanlı package bütünlük kontrolü."""
import base64
import hashlib
import json
import sys
from pathlib import Path


class DijitalImza:
    """
    RSA Dijital İmza Doğrulama Sınıfı (v2.1.0+)
    turkod_ide package bütünlüğünü manifest üzerinden kontrol eder.
    """

    TURKOD_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuFXhkaH2bJWbe56exYTP
JXZDkX5aBmeV9Hop5xL2+bVBn/uGG4zpFjnQjQkLhNV7lTZNDQcz/FAWTuBaZiY9
raINwqtz1fOF4cO1gKYL3pkiBnAVNB6HzsW7u7sKkTGyYnrEldFBsQy78joY5ve3
KGmttHvi+Uw5E89qUbFcgoihkmkEgxmaGmwvcT9wyVmlajFO2jtxP7S2b7ChAAqi
BoPepkXQoCo9c6kuyVlsVGe6r9ghi4F70nLt97cHmlMMHAr9SlNSgGRD6ZMV6b0c
xvvIld3r3ekTlqCvBE0ueTZN2LAmwxJ8fxR+pxYqvSMr4z/zSUC6CEZXur4bfH7/
1QIDAQAB
-----END PUBLIC KEY-----"""

    MANIFEST_DOSYA_ADI = "turkod_ide.manifest.json"
    SIG_DOSYA_ADI = "turkod_ide.manifest.json.sig"

    @staticmethod
    def _temel_yolu_bul():
        """Package kök dizinini döndürür (frozen veya dev ortamı)."""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS) / "turkod_ide"
        return Path(__file__).resolve().parent

    @staticmethod
    def dogrula():
        """
        Package bütünlüğünü manifest ve imza üzerinden doğrular.
        Returns:
            tuple: (basarili: bool, mesaj: str, detay: list|str)
        """
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            base_path = DijitalImza._temel_yolu_bul()
            manifest_yol = base_path / DijitalImza.MANIFEST_DOSYA_ADI
            sig_yol = base_path / DijitalImza.SIG_DOSYA_ADI

            # 1. Dosya varlık kontrolü
            if not manifest_yol.exists() or not sig_yol.exists():
                return False, "❌ Manifest veya imza dosyası eksik", str(manifest_yol)

            # 2. Verileri oku
            manifest_bytes = manifest_yol.read_bytes()
            imza_base64 = sig_yol.read_text(encoding="utf-8").strip()
            imza_bytes = base64.b64decode(imza_base64)

            # 3. Manifest imzasını doğrula
            public_key = serialization.load_pem_public_key(
                DijitalImza.TURKOD_PUBLIC_KEY.encode()
            )
            public_key.verify(
                imza_bytes,
                manifest_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # 4. Her dosyanın hash'ini kontrol et
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            hatali_dosyalar = []

            for dosya_bilgi in manifest.get("files", []):
                dosya_yol = base_path / dosya_bilgi["path"]

                if not dosya_yol.exists():
                    hatali_dosyalar.append(f"{dosya_bilgi['path']} (YOK)")
                    continue

                gercek_hash = hashlib.sha256(dosya_yol.read_bytes()).hexdigest()
                if gercek_hash != dosya_bilgi["sha256"]:
                    hatali_dosyalar.append(f"{dosya_bilgi['path']} (HASH UYUMSUZ)")

            if hatali_dosyalar:
                return False, "❌ Dosya bütünlüğü bozuk", hatali_dosyalar

            dosya_sayisi = len(manifest.get("files", []))
            return True, "✅ İmza ve bütünlük doğrulandı", f"{dosya_sayisi} dosya kontrol edildi"

        except Exception as e:
            hata_tipi = type(e).__name__
            hata_mesaj = str(e)

            if "verification failed" in hata_mesaj.lower() or hata_tipi == "InvalidSignature":
                return False, "❌ Manifest imzası GEÇERSİZ", "Manifest değiştirilmiş olabilir"

            return False, f"⚠️ Doğrulama hatası ({hata_tipi})", hata_mesaj[:200]

    @staticmethod
    def hash_hesapla(dosya_yol=None):
        """Verilen dosyanın SHA-256 hash'ini hesaplar."""
        if dosya_yol is None:
            return None
        try:
            return hashlib.sha256(Path(dosya_yol).read_bytes()).hexdigest()
        except Exception:
            return "Hesaplanamadı"


def imza_dogrula():
    """Kolay erişim için kısayol."""
    return DijitalImza.dogrula()
