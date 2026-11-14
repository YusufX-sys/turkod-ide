"""Manifest tabanlı RSA dijital imza doğrulama modülü."""

import base64
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class DijitalImza:
    MANIFEST_ADI = "turkod_ide.manifest.json"
    SIG_ADI = "turkod_ide.manifest.json.sig"
    PACKAGE_ADI = "turkod_ide"

    # Performans: public key yalnızca bir kez çözülür; başarılı doğrulama
    # sonucu, manifest/imza içeriği ve tüm dosyaların (boyut, mtime_ns)
    # parmak izi değişmediği sürece süreç içinde önbellekten döner.
    # Önbellek yalnızca bellekte tutulur (diske yazılmaz).
    _public_key = None
    _kilit = threading.Lock()
    _sonuc_onbellek = None  # (iz, sonuc, dosya_izleri)
    _hash_onbellek = {}  # (yol, boyut, mtime_ns) -> sha256
    _PARALEL_ESIK = 4  # bundan az dosyada iş parçacığı açmaya değmez

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
        with path.open("rb") as f:
            digest = getattr(hashlib, "file_digest", None)  # Python 3.11+
            if digest is not None:
                return digest(f, "sha256").hexdigest()
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(chunk)
            return h.hexdigest()

    @classmethod
    def _sha256_cached(cls, path: Path, st) -> str:
        anahtar = (str(path), st.st_size, st.st_mtime_ns)
        h = cls._hash_onbellek.get(anahtar)
        if h is None:
            h = cls._sha256_file(path)
            cls._hash_onbellek[anahtar] = h
        return h

    @classmethod
    def _load_public_key(cls):
        if cls._public_key is None:
            from cryptography.hazmat.primitives import serialization

            cls._public_key = serialization.load_pem_public_key(
                cls.TURKOD_PUBLIC_KEY.encode("utf-8")
            )
        return cls._public_key

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
                return DijitalImza._sha256_cached(manifest_path, manifest_path.stat())
        except Exception:
            pass
        
        return "Manifest bulunamadı"
    @classmethod
    def dogrula(cls, zorla=False):
        """Manifest imzasını ve dosya bütünlüğünü doğrular.

        Eşzamanlı çağrılar tek doğrulamayı paylaşır (kilit); hiçbir dosya
        değişmediyse sonuç önbellekten anında döner. ``zorla=True`` önbelleği
        atlar.
        """
        with cls._kilit:
            return cls._dogrula_kilitli(zorla)

    @classmethod
    def _dogrula_kilitli(cls, zorla):
        try:
            from cryptography.hazmat.primitives import hashes
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
            sig_st = sig_path.stat()
        except Exception as e:
            return False, "Manifest okunamadı", str(e)

        iz = (str(base), hashlib.sha256(manifest_bytes).digest(),
              sig_st.st_size, sig_st.st_mtime_ns)
        onbellek = cls._sonuc_onbellek
        if not zorla and onbellek is not None and onbellek[0] == iz:
            if cls._dosyalar_ayni(onbellek[2]):
                return onbellek[1]

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
            public_key = cls._load_public_key()
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

        # 1) Ucuz geçiş: yol, varlık ve boyut denetimi. Hash'lemeden önce
        #    yapılır; bozuk/eksik paket hemen yakalanır.
        hedefler = []
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

            try:
                st = target.stat()
            except OSError:
                return False, "Eksik dosya", rel_path
            if not target.is_file():
                return False, "Eksik dosya", rel_path

            if expected_size is not None and st.st_size != int(expected_size):
                return (
                    False,
                    "Dosya boyutu değişmiş",
                    f"{rel_path}: beklenen={expected_size}, bulunan={st.st_size}",
                )

            hedefler.append((rel_path, target, st, expected_sha256))

        # 2) Hash geçişi: çok dosyada paralel (hashlib GIL'i bırakır).
        def _kontrol(item):
            rel, target, st, beklenen = item
            return rel, cls._sha256_cached(target, st) == beklenen

        if len(hedefler) >= cls._PARALEL_ESIK:
            isci = min(8, os.cpu_count() or 2, len(hedefler))
            with ThreadPoolExecutor(max_workers=isci) as havuz:
                sonuclar = list(havuz.map(_kontrol, hedefler))
        else:
            sonuclar = [_kontrol(h) for h in hedefler]

        for rel, ok in sonuclar:
            if not ok:
                return False, "Dosya hash değeri değişmiş", rel

        version = manifest.get("version", "bilinmiyor")
        sonuc = (
            True,
            "Manifest ve dosya bütünlüğü doğrulandı",
            f"version={version}, file_count={len(files)}",
        )
        # Yalnızca başarılı sonuç önbelleğe alınır; hata durumunda her
        # çağrıda yeniden denetlenir.
        cls._sonuc_onbellek = (
            iz,
            sonuc,
            [(t, st.st_size, st.st_mtime_ns) for _, t, st, _ in hedefler],
        )
        return sonuc

    @staticmethod
    def _dosyalar_ayni(dosya_izleri):
        for yol, boyut, mtime in dosya_izleri:
            try:
                st = yol.stat()
            except OSError:
                return False
            if st.st_size != boyut or st.st_mtime_ns != mtime:
                return False
        return True

    @classmethod
    def arka_planda_isit(cls):
        """Açılışta doğrulamayı arka planda yapıp önbelleği ısıtır; Hakkında /
        İmza penceresi açıldığında sonuç anında hazır olur."""
        t = threading.Thread(target=cls.dogrula, daemon=True,
                             name="imza-dogrulama")
        t.start()
        return t


def imza_dogrula():
    return DijitalImza.dogrula()


if __name__ == "__main__":
    ok, mesaj, detay = imza_dogrula()
    print(mesaj)
    print(detay)
    sys.exit(0 if ok else 1)
