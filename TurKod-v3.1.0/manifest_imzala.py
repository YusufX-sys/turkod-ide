"""Build aracı - pakete KONMAZ.

signing.py'nin beklediği biçimde manifest üretir ve RSA-PSS (SHA-256,
MGF1-SHA256, salt=MAX_LENGTH) ile imzalar.

Anahtar çifti (bir kez; public key'i signing.py'deki TURKOD_PUBLIC_KEY'e koy):
    python manifest_imzala.py --anahtar-uret D:\\gizli\\turkod

Anahtar ile signing.py'deki public key eşleşiyor mu (uzun derlemeden önce):
    python manifest_imzala.py --anahtar-kontrol D:\\gizli\\turkod_private.pem

İmzalama (Authenticode imzasından SONRA çalıştır; hash'ler o zaman değişir):
    python manifest_imzala.py --dizin dist\\TurKod\\backend --surum 3.1.0 ^
        --ozel-anahtar D:\\gizli\\turkod_private.pem ^
        --haric "_internal/python_embed/*"

Mevcut bir paketin manifestini anahtarsız doğrulama (signing.py ile aynı kural):
    python manifest_imzala.py --dogrula dist\\TurKod\\backend

Neden eskisinden hızlı?
  * Hariç tutulan klasörlerin (ör. _internal/python_embed, on binlerce dosya)
    İÇİNE HİÇ GİRİLMEZ. Eskiden tüm ağaç `rglob("*")` ile gezilip her dosya
    sonradan fnmatch ile eleniyordu.
  * SHA-256 hesapları paralel yapılır (hashlib büyük bloklarda GIL'i bırakır).
  * Artımlı önbellek: build\\manifest_onbellek.json, değişmemiş dosyaların
    (aynı yol + boyut + değiştirilme zamanı) hash'ini yeniden kullanır. Önbellek
    pakete girmez; yalnızca imzalayan makinede durur. Her şeyi baştan hesaplamak
    için --tam ver. (Authenticode imzası dosyayı değiştirdiğinden imzalanan
    exe'ler zaten yeniden hesaplanır.)
  * Özel anahtar ve parolası yalnızca BİR kez okunur/sorulur.
"""
import argparse
import base64
import fnmatch
import getpass
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

MANIFEST_ADI = "turkod_ide.manifest.json"
SIG_ADI = MANIFEST_ADI + ".sig"
HER_ZAMAN_HARIC = ["__pycache__/*", "*/__pycache__/*", "*.pyc", ".turkod_kelimeler.json"]
KOK_DIZIN = Path(__file__).resolve().parent
ONBELLEK_VARSAYILAN = KOK_DIZIN / "build" / "manifest_onbellek.json"
_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


# ----------------------------------------------------------------------------
# Anahtarlar
# ----------------------------------------------------------------------------
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
    sys.path.insert(0, str(KOK_DIZIN))
    try:
        from turkod_ide.signing import DijitalImza
        return serialization.load_pem_public_key(DijitalImza.TURKOD_PUBLIC_KEY.encode("utf-8"))
    except Exception as e:
        print(f"UYARI: signing.py public key karşılaştırması yapılamadı: {e}")
        return None


def _anahtar_eslesiyor_mu(anahtar):
    gomulu = _gomulu_public_key()
    if gomulu is None:
        return None
    return gomulu.public_numbers() == anahtar.public_key().public_numbers()


def anahtar_kontrol(yol: str):
    """Uzun derlemeye başlamadan önce: özel anahtar signing.py'deki public key'in eşi mi?"""
    anahtar = _ozel_anahtar_yukle(yol)
    eslesme = _anahtar_eslesiyor_mu(anahtar)
    if eslesme is None:
        sys.exit("HATA: signing.py'deki public key okunamadı.")
    if not eslesme:
        sys.exit("HATA: Bu özel anahtar signing.py'deki public key'in eşi değil.\n"
                 "Ya doğru özel anahtarı ver ya da anahtarın _public.pem içeriğini "
                 "signing.py'deki TURKOD_PUBLIC_KEY'e yapıştır.")
    print("Özel anahtar signing.py'deki public key ile eşleşiyor.")


# ----------------------------------------------------------------------------
# Dosya toplama + hash
# ----------------------------------------------------------------------------
def _haric_mi(rel: str, desenler) -> bool:
    return any(fnmatch.fnmatch(rel, d) for d in desenler)


def _dizin_haric_mi(rel_dizin: str, desenler) -> bool:
    """'a/b' klasörünün TAMAMI hariç mi? Yalnızca 'a/b/*' (ya da tam 'a/b')
    biçimindeki desenler klasörü budar; '*.pyc' gibi dosya desenleri budamaz,
    onlar dosya düzeyinde ayrıca uygulanır."""
    for d in desenler:
        if d.endswith("/*") and fnmatch.fnmatch(rel_dizin, d[:-2]):
            return True
        if "*" not in d and "?" not in d and d == rel_dizin:
            return True
    return False


def dosyalari_topla(kok: Path, desenler):
    """(rel_posix, mutlak_yol, os.stat) listesi; hariç klasörlere inilmez."""
    sonuc = []
    for dizin, alt_dizinler, dosyalar in os.walk(kok):
        rel_dizin = Path(dizin).relative_to(kok).as_posix()
        rel_dizin = "" if rel_dizin == "." else rel_dizin
        # Alt klasörleri yerinde budayarak os.walk'un içine girmesini engelle.
        alt_dizinler[:] = sorted(
            a for a in alt_dizinler
            if a != "__pycache__"
            and not _dizin_haric_mi(f"{rel_dizin}/{a}" if rel_dizin else a, desenler))
        for ad in dosyalar:
            rel = f"{rel_dizin}/{ad}" if rel_dizin else ad
            if rel in (MANIFEST_ADI, SIG_ADI) or _haric_mi(rel, desenler):
                continue
            yol = Path(dizin) / ad
            sonuc.append((rel, yol, yol.stat()))
    # Eski sürümle aynı sıra (büyük/küçük harfe duyarsız); doğrulama sıradan
    # bağımsızdır, bu yalnızca manifestlerin karşılaştırılabilir kalması için.
    sonuc.sort(key=lambda x: (x[0].lower(), x[0]))
    return sonuc


def _sha256(yol: Path) -> str:
    with yol.open("rb") as f:
        digest = getattr(hashlib, "file_digest", None)  # Python 3.11+
        if digest is not None:
            return digest(f, "sha256").hexdigest()
        h = hashlib.sha256()
        for parca in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(parca)
        return h.hexdigest()


def _onbellek_oku(yol: Path):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _onbellek_yaz(yol: Path, veri):
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_suffix(".tmp")
        gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        os.replace(gecici, yol)
    except Exception as e:
        print(f"UYARI: önbellek yazılamadı ({e}); sonraki imzalama tam hash yapar.")


def hashleri_hesapla(dosyalar, onbellek, isci_sayisi):
    """Her dosya için {path, sha256, size}; önbellekte geçerli olan yeniden kullanılır."""
    yeni_onbellek = {}
    girisler = [None] * len(dosyalar)
    hesaplanacak = []
    for i, (rel, yol, st) in enumerate(dosyalar):
        anahtar = f"{rel}|{st.st_size}|{st.st_mtime_ns}"
        h = onbellek.get(anahtar)
        if h:
            girisler[i] = {"path": rel, "sha256": h, "size": st.st_size}
            yeni_onbellek[anahtar] = h
        else:
            hesaplanacak.append((i, rel, yol, st, anahtar))

    def _isle(is_):
        i, rel, yol, st, anahtar = is_
        return i, rel, st.st_size, anahtar, _sha256(yol)

    if hesaplanacak:
        with ThreadPoolExecutor(max_workers=isci_sayisi) as havuz:
            for n, (i, rel, boyut, anahtar, h) in enumerate(havuz.map(_isle, hesaplanacak), 1):
                girisler[i] = {"path": rel, "sha256": h, "size": boyut}
                yeni_onbellek[anahtar] = h
                if n % 500 == 0 or n == len(hesaplanacak):
                    print(f"  hash: {n}/{len(hesaplanacak)}", flush=True)
    return girisler, yeni_onbellek, len(dosyalar) - len(hesaplanacak)


# ----------------------------------------------------------------------------
# İmzalama / doğrulama
# ----------------------------------------------------------------------------
def imzala(dizin, surum, ozel_anahtar, haric, tam=False, isci=None,
           onbellek_yolu=ONBELLEK_VARSAYILAN, kuru=False):
    t0 = time.perf_counter()
    kok = Path(dizin).resolve()
    if not kok.is_dir():
        sys.exit(f"Dizin yok: {kok}")

    # Anahtar ve eşleşme ÖNCE: yanlış anahtarla saniyelerce hash'leyip sonra
    # hata vermek yerine hemen dur. Parola yalnızca bir kez sorulur.
    anahtar = None
    if not kuru:
        anahtar = _ozel_anahtar_yukle(ozel_anahtar)
        if _anahtar_eslesiyor_mu(anahtar) is False:
            sys.exit("HATA: Bu özel anahtar signing.py'deki public key'in eşi değil.")

    desenler = HER_ZAMAN_HARIC + list(haric)
    dosyalar = dosyalari_topla(kok, desenler)
    if not dosyalar:
        sys.exit("Manifest'e girecek dosya bulunamadı.")
    t1 = time.perf_counter()

    onbellek = {} if tam else _onbellek_oku(onbellek_yolu)
    isci = isci or min(16, (os.cpu_count() or 4) + 2)
    girisler, yeni_onbellek, yeniden = hashleri_hesapla(dosyalar, onbellek, isci)
    t2 = time.perf_counter()

    # İmzalanan bayt dizisi, diske yazılan bayt dizisiyle birebir aynı olmalı.
    manifest_bayt = json.dumps(
        {"version": surum, "files": girisler}, ensure_ascii=False, indent=2
    ).encode("utf-8")

    toplam_mb = sum(g["size"] for g in girisler) / 1e6
    ozet = (f"{len(girisler)} dosya ({toplam_mb:.1f} MB); {yeniden} önbellekten, "
            f"{len(girisler) - yeniden} yeniden hesaplandı. "
            f"Tarama {t1 - t0:.2f} sn, hash {t2 - t1:.2f} sn")
    if kuru:
        print("[kuru çalıştırma] " + ozet + " — hiçbir dosya yazılmadı.")
        return

    imza = anahtar.sign(manifest_bayt, _PSS, hashes.SHA256())
    anahtar.public_key().verify(imza, manifest_bayt, _PSS, hashes.SHA256())  # öz-doğrulama

    # Önce imza geçici dosyaya; ikisi de hazır olunca yerine taşı (yarım kalmış
    # manifest/imza çifti oluşmasın).
    m_gecici = kok / (MANIFEST_ADI + ".tmp")
    s_gecici = kok / (SIG_ADI + ".tmp")
    m_gecici.write_bytes(manifest_bayt)
    s_gecici.write_text(base64.b64encode(imza).decode("ascii"), encoding="utf-8")
    os.replace(m_gecici, kok / MANIFEST_ADI)
    os.replace(s_gecici, kok / SIG_ADI)

    _onbellek_yaz(onbellek_yolu, yeni_onbellek)
    print(f"Manifest imzalandı: sürüm {surum}. {ozet}, toplam {time.perf_counter() - t0:.2f} sn")
    print(f"  {kok / MANIFEST_ADI}\n  {kok / SIG_ADI}")


def dogrula(dizin):
    """Paketi signing.py'deki public key ve aynı kurallarla doğrular (anahtar gerekmez)."""
    kok = Path(dizin).resolve()
    m, s = kok / MANIFEST_ADI, kok / SIG_ADI
    if not m.is_file() or not s.is_file():
        sys.exit(f"Manifest veya imza yok: {kok}")
    gomulu = _gomulu_public_key()
    if gomulu is None:
        sys.exit("HATA: signing.py'deki public key okunamadı.")
    bayt = m.read_bytes()
    try:
        gomulu.verify(base64.b64decode(s.read_text(encoding="utf-8").strip()),
                      bayt, _PSS, hashes.SHA256())
    except Exception as e:
        sys.exit(f"İMZA GEÇERSİZ: {e}")
    girisler = json.loads(bayt.decode("utf-8"))["files"]

    def _kontrol(g):
        yol = kok / g["path"]
        if not yol.is_file():
            return g["path"], "eksik"
        if yol.stat().st_size != int(g["size"]):
            return g["path"], "boyut farklı"
        if _sha256(yol) != g["sha256"].lower():
            return g["path"], "hash farklı"
        return g["path"], None

    with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) + 2)) as havuz:
        hatalar = [(p, n) for p, n in havuz.map(_kontrol, girisler) if n]
    if hatalar:
        for p, n in hatalar[:20]:
            print(f"  {n}: {p}")
        sys.exit(f"DOĞRULAMA BAŞARISIZ: {len(hatalar)} dosya")
    print(f"Doğrulandı: imza geçerli, {len(girisler)} dosya eşleşiyor.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TürKod manifest üretici/imzalayıcı")
    ap.add_argument("--anahtar-uret", metavar="ONEK")
    ap.add_argument("--anahtar-kontrol", metavar="PEM")
    ap.add_argument("--dogrula", metavar="DIZIN", help="mevcut manifesti anahtarsız doğrula")
    ap.add_argument("--dizin")
    ap.add_argument("--surum", default="0.0.0")
    ap.add_argument("--ozel-anahtar")
    ap.add_argument("--haric", action="append", default=[],
                    help="posix yolu üzerinde fnmatch deseni; birden fazla verilebilir")
    ap.add_argument("--tam", action="store_true", help="önbelleği yok say, her şeyi yeniden hash'le")
    ap.add_argument("--is-parcacigi", type=int, default=None, help="paralel hash iş parçacığı sayısı")
    ap.add_argument("--onbellek", default=str(ONBELLEK_VARSAYILAN), help="hash önbellek dosyası")
    ap.add_argument("--kuru", action="store_true",
                    help="yalnızca tara ve hash'le, hiçbir şey yazma (süre ölçmek için)")
    a = ap.parse_args()

    if a.anahtar_uret:
        anahtar_uret(a.anahtar_uret)
    elif a.anahtar_kontrol:
        anahtar_kontrol(a.anahtar_kontrol)
    elif a.dogrula:
        dogrula(a.dogrula)
    elif a.dizin and (a.ozel_anahtar or a.kuru):
        imzala(a.dizin, a.surum, a.ozel_anahtar, a.haric, tam=a.tam, isci=a.is_parcacigi,
               onbellek_yolu=Path(a.onbellek), kuru=a.kuru)
    else:
        ap.error("--anahtar-uret, --anahtar-kontrol, --dogrula ya da (--dizin ve --ozel-anahtar) gerekli")
