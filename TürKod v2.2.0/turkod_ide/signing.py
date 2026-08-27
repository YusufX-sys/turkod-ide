"""Manifest tabanlı RSA dijital imza doğrulama modülü."""

import base64
import hashlib
import json
import sys
from pathlib import Path


class DijitalImza:
    MANIFEST_ADI = "turkod_ide.manifest.json"
    SIG_ADI = "turkod_ide.manifest.json.sig"
    PACKAGE_ADI = "turkod_ide"

    TURKOD_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuFXhkaH2bJWbe56exYTP
JXZDkX5aBmeV9Hop5xL2+bVBn/uGG4zpFjnQjQkLhNV7lTZNDQcz/FAWTuBaZiY9
raINwqtz1fOF4cO1gKYL3pkiBnAVNB6HzsW7u7sKkTGyYnrEldFBsQy78joY5ve3
KGmttHvi+Uw5E89qUbFcgoihkmkEgxmaGmwvcT9wyVmlajFO2jtxP7S2b7ChAAqi
BoPepkXQoCo9c6kuyVlsVGe6r9ghi4F70nLt97cHmlMMHAr9SlNSgGRD6ZMV6b0c
xvvIld3r3ekTlqCvBE0ueTZN2LAmwxJ8fxR+pxYqvSMr4z/zSUC6CEZXur4bfH7/
1QIDAQAB
-----END PUBLIC KEY-----"""

    @staticmethod
    def _candidate_dirs():
        candidates = []

        if getattr(sys, "frozen", False):
            meipass = Path(sys._MEIPASS)
            exe_dir = Path(sys.executable).resolve().parent

            candidates.extend(
                [
                    meipass / DijitalImza.PACKAGE_ADI,
                    meipass,
                    exe_dir / DijitalImza.PACKAGE_ADI,
                    exe_dir,
                ]
            )
        else:
            here = Path(__file__).resolve().parent

            candidates.extend(
                [
                    here,
                    here / DijitalImza.PACKAGE_ADI,
                    here.parent / DijitalImza.PACKAGE_ADI,
                    here.parent,
                ]
            )

        seen = set()
        result = []

        for candidate in candidates:
            try:
                candidate = candidate.resolve()
            except Exception:
                continue

            if candidate in seen:
                continue

            seen.add(candidate)
            result.append(candidate)

        return result

    @classmethod
    def _find_bundle(cls):
        for base in cls._candidate_dirs():
            manifest_path = base / cls.MANIFEST_ADI
            sig_path = base / cls.SIG_ADI

            if manifest_path.is_file() and sig_path.is_file():
                return base, manifest_path, sig_path

        return None, None, None

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()

        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)

        return h.hexdigest()
    @staticmethod
    def hash_hesapla(dosya_yol=None):
        """
        Geriye dönük uyumluluk için korunmuştur.
        Artık çalışan dosyayı değil, manifest bütünlüğünü temsil eder.
        Eğer app.py sadece UI'da göstermek için kullanıyorsa bu yeterlidir.
        """
        if dosya_yol is not None:
            # Eski kullanım: belirli bir dosyanın hash'i isteniyor
            try:
                with open(dosya_yol, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
            except Exception:
                return "Hesaplanamadı"
        
        # Yeni kullanım: manifest hash'i döndür
        try:
            base, manifest_path, _ = DijitalImza._find_bundle()
            if manifest_path and manifest_path.exists():
                return hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        except Exception:
            pass
        
        return "Manifest bulunamadı"
    @classmethod
    def dogrula(cls):
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except Exception as e:
            return False, "cryptography paketi bulunamadı", str(e)

        base, manifest_path, sig_path = cls._find_bundle()

        if not manifest_path or not sig_path:
            return (
                False,
                "Manifest veya imza dosyası bulunamadı",
                f"Aranan dizinler: {cls._candidate_dirs()}",
            )

        try:
            manifest_bytes = manifest_path.read_bytes()
        except Exception as e:
            return False, "Manifest okunamadı", str(e)

        try:
            signature_base64 = sig_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            return False, "İmza dosyası okunamadı", str(e)

        if not signature_base64:
            return False, "İmza dosyası boş", str(sig_path)

        try:
            signature = base64.b64decode(signature_base64)
        except Exception as e:
            return False, "İmza Base64 formatında değil", str(e)

        try:
            public_key = serialization.load_pem_public_key(
                cls.TURKOD_PUBLIC_KEY.encode("utf-8")
            )
        except Exception as e:
            return False, "Public key yüklenemedi", str(e)

        try:
            public_key.verify(
                signature,
                manifest_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        except Exception as e:
            return False, "Manifest imzası geçersiz", str(e)

        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except Exception as e:
            return False, "Manifest JSON olarak çözülemedi", str(e)

        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            return False, "Manifest geçersiz", "files listesi boş veya hatalı"

        base_resolved = base.resolve()

        for entry in files:
            if not isinstance(entry, dict):
                return False, "Manifest geçersiz", "files içinde hatalı giriş var"

            rel_path = str(entry.get("path", "")).replace("\\", "/")
            expected_sha256 = str(entry.get("sha256", "")).lower()
            expected_size = entry.get("size")

            if not rel_path or not expected_sha256:
                return False, "Manifest geçersiz", "path veya sha256 eksik"

            target = (base / rel_path).resolve()

            try:
                if not target.is_relative_to(base_resolved):
                    return (
                        False,
                        "Manifest geçersiz",
                        f"Dosya paket dışına işaret ediyor: {rel_path}",
                    )
            except AttributeError:
                # Python 3.9 öncesinde is_relative_to yoksa basit devam et.
                pass

            if not target.is_file():
                return False, "Eksik dosya", rel_path

            if expected_size is not None:
                actual_size = target.stat().st_size
                if actual_size != int(expected_size):
                    return (
                        False,
                        "Dosya boyutu değişmiş",
                        f"{rel_path}: beklenen={expected_size}, bulunan={actual_size}",
                    )

            actual_sha256 = cls._sha256_file(target)

            if actual_sha256 != expected_sha256:
                return False, "Dosya hash değeri değişmiş", rel_path

        version = manifest.get("version", "bilinmiyor")

        return (
            True,
            "Manifest ve dosya bütünlüğü doğrulandı",
            f"version={version}, file_count={len(files)}",
        )


def imza_dogrula():
    return DijitalImza.dogrula()


if __name__ == "__main__":
    ok, mesaj, detay = imza_dogrula()
    print(mesaj)
    print(detay)
    sys.exit(0 if ok else 1)
