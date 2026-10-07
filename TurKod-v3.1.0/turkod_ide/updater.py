"""TürKod güncelleme kontrolü.

Akış: latest.json + latest.json.sig indir -> RSA-PSS imzasını signing.py'deki
public key ile doğrula -> sürüm daha yeniyse kurulum dosyasını indir ->
SHA-256'yı latest.json'daki değerle karşılaştır -> dosya yolunu döndür.

Kurulumu backend DEĞİL Flutter başlatır: backend'in alt süreci olarak
başlatılan kurulum, Flutter kapanırken `taskkill /T` ile birlikte ölür.
"""
import hashlib
import json
import re
import sys
import tempfile
import threading
import urllib.request
import base64
from pathlib import Path

try:
    from .signing import DijitalImza
except ImportError:
    from signing import DijitalImza

# latest.json ve latest.json.sig, GitHub'daki EN SON (draft/pre-release olmayan) yayının
# eklerinden okunur. Depo herkese açık olmalı.
GUNCELLEME_URL = "https://github.com/YusufX-sys/turkod-ide/releases/latest/download/latest.json"

ZAMAN_ASIMI = 10
_SURUM_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_son_bildirim = {}
# _son_bildirim her kontrolde YENİ bir sözlükle değiştirilir (yerinde
# temizlenmez): eşzamanlı bir kontrol, başka bir iş parçacığının okuduğu
# bildirimi yarıda boşaltıp KeyError'a yol açamaz.
_bildirim_kilit = threading.Lock()


def mevcut_surum() -> str:
    if getattr(sys, "frozen", False):
        yol = Path(sys._MEIPASS) / "surum.txt"
    else:
        yol = Path(__file__).resolve().parents[1] / "surum.txt"
    try:
        return yol.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _tuple(surum: str):
    return tuple(int(p) for p in surum.split("."))


def _https_ac(url: str):
    if not url.lower().startswith("https://"):
        raise ValueError("Yalnızca https adresleri kabul edilir.")
    istek = urllib.request.Request(url, headers={"User-Agent": "TurKod-Updater"})
    yanit = urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI)
    if not yanit.geturl().lower().startswith("https://"):
        yanit.close()
        raise ValueError("https dışına yönlendirme reddedildi.")
    return yanit


def _imza_dogru_mu(veri: bytes, imza_b64: bytes) -> bool:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        anahtar = serialization.load_pem_public_key(DijitalImza.TURKOD_PUBLIC_KEY.encode("utf-8"))
        anahtar.verify(
            base64.b64decode(imza_b64.strip()),
            veri,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def kontrol_et() -> dict:
    try:
        with _https_ac(GUNCELLEME_URL) as y:
            veri = y.read(1_000_000)
        with _https_ac(GUNCELLEME_URL + ".sig") as y:
            imza = y.read(10_000)
    except Exception as e:
        return {"ok": False, "hata": f"Güncelleme sunucusuna ulaşılamadı: {e}"}

    if not _imza_dogru_mu(veri, imza):
        return {"ok": False, "hata": "Güncelleme bilgisinin imzası geçersiz."}

    try:
        m = json.loads(veri.decode("utf-8"))
        yeni, url, sha = str(m["version"]), str(m["url"]), str(m["sha256"]).lower()
    except Exception:
        return {"ok": False, "hata": "Güncelleme bilgisi okunamadı."}

    if not _SURUM_RE.match(yeni) or not _SHA_RE.match(sha) or not url.lower().startswith("https://"):
        return {"ok": False, "hata": "Güncelleme bilgisi geçersiz."}

    mevcut = mevcut_surum()
    var = _tuple(yeni) > _tuple(mevcut) if _SURUM_RE.match(mevcut) else False

    try:
        boyut = int(m.get("size") or 0)
    except (TypeError, ValueError):
        boyut = 0

    global _son_bildirim
    with _bildirim_kilit:
        _son_bildirim = (
            {"version": yeni, "url": url, "sha256": sha, "size": boyut} if var else {})

    return {
        "ok": True,
        "guncelleme_var": var,
        "mevcut": mevcut,
        "yeni": yeni,
        "notlar": str(m.get("notes", ""))[:2000],
    }


_indirme = {"durum": "yok", "indirilen": 0, "toplam": 0, "yol": "", "hata": "", "surum": ""}
_kilit = threading.Lock()


def _indir(m: dict, ilerleme=None) -> dict:
    """Kurulum dosyasını indirir, SHA-256'yı doğrular. Başarıda {"ok": True, "yol": ...}."""
    dizin = Path(tempfile.gettempdir()) / "turkod_guncelleme"
    dizin.mkdir(exist_ok=True)
    hedef = dizin / f"TurKod-Setup-{m['version']}.exe"
    # Önce benzersiz geçici dosyaya indirilir; SHA doğrulanınca hedefe
    # taşınır. Böylece aynı anda iki indirme aynı dosyaya yazamaz ve diskte
    # doğrulanmamış (yarım) bir kurulum dosyası "hazır" görünmez.
    gecici = dizin / f"TurKod-Setup-{m['version']}.{threading.get_ident()}.part"
    h = hashlib.sha256()
    indirilen = 0

    def _sil(yol):
        # Defender taraması / açık kurulum dosyası yüzünden silme başarısız
        # olabilir; bu, durumu "indiriyor"da asılı bırakmamalı.
        try:
            yol.unlink(missing_ok=True)
        except OSError:
            pass

    try:
        with _https_ac(m["url"]) as y, gecici.open("wb") as f:
            try:
                toplam = int(y.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                toplam = 0
            toplam = toplam or int(m.get("size") or 0)
            if ilerleme:
                ilerleme(0, toplam)
            while True:
                parca = y.read(1024 * 1024)
                if not parca:
                    break
                h.update(parca)
                f.write(parca)
                indirilen += len(parca)
                if ilerleme:
                    ilerleme(indirilen, toplam)
    except Exception as e:
        _sil(gecici)
        return {"ok": False, "hata": f"İndirme başarısız: {e}"}

    if h.hexdigest() != m["sha256"]:
        _sil(gecici)
        return {"ok": False, "hata": "İndirilen dosyanın SHA-256 değeri uyuşmuyor."}

    try:
        gecici.replace(hedef)
    except OSError:
        # Hedef kilitliyse (ör. aynı kurulum dosyası hâlâ açık) doğrulanmış
        # geçici dosya doğrudan kullanılır.
        hedef = gecici

    return {"ok": True, "yol": str(hedef), "surum": m["version"]}


def _yeni_bildirim_hazirla() -> dict:
    """Bildirim yoksa (ya da eskiyse) latest.json'ı yeniden okuyup imzasını doğrular."""
    r = kontrol_et()
    if not r.get("ok"):
        return r
    m = dict(_son_bildirim)
    if not m:
        return {"ok": False, "hata": "Yeni sürüm yok."}
    return {"ok": True, "bildirim": m}


def indir_ve_dogrula() -> dict:
    """Bloklayan sürüm (geriye dönük uyumluluk)."""
    m = dict(_son_bildirim)
    if not m:
        r = _yeni_bildirim_hazirla()
        if not r.get("ok"):
            return r
        m = r["bildirim"]
    return _indir(m)


def indir_baslat() -> dict:
    """İndirmeyi arka planda başlatır; ilerleme indir_durum() ile sorgulanır."""
    # Durum, kontrolle AYNI kilit bölümünde "indiriyor" yapılır: eskiden iki
    # hızlı tıklama ikisi de kontrolü geçip aynı dosyayı aynı anda indiriyordu.
    with _kilit:
        if _indirme["durum"] == "indiriyor":
            return {"ok": True, "durum": "indiriyor"}
        onceki_durum = dict(_indirme)
        _indirme.update(durum="indiriyor", indirilen=0, toplam=0,
                        yol="", hata="", surum="")

    # Her indirmeden önce en güncel bilgiyi al: "en son sürüm" kurulsun.
    try:
        r = _yeni_bildirim_hazirla()
    except Exception as e:
        r = {"ok": False, "hata": str(e)}
    if not r.get("ok"):
        with _kilit:
            # Kontrol başarısızsa (ör. çevrimdışı) önceki durum geri yüklenir:
            # daha önce indirilmiş ("bitti") bir kurulum kaybolmamalı.
            _indirme.clear()
            _indirme.update(onceki_durum)
        return r
    m = r["bildirim"]

    with _kilit:
        _indirme.update(toplam=int(m.get("size") or 0), surum=m["version"])

    def ilerleme(indirilen, toplam):
        with _kilit:
            _indirme["indirilen"] = indirilen
            if toplam:
                _indirme["toplam"] = toplam

    def is_():
        try:
            sonuc = _indir(m, ilerleme)
        except Exception as e:
            sonuc = {"ok": False, "hata": f"İndirme başarısız: {e}"}
        with _kilit:
            if sonuc.get("ok"):
                _indirme.update(durum="bitti", yol=sonuc["yol"], hata="")
            else:
                _indirme.update(durum="hata", hata=sonuc.get("hata", "Bilinmeyen hata"))

    threading.Thread(target=is_, daemon=True).start()
    return {"ok": True, "durum": "indiriyor", "surum": m["version"]}


def indir_durum() -> dict:
    with _kilit:
        return {"ok": True, **_indirme}
