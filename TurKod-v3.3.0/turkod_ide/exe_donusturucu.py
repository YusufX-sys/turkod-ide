"""TürKod programını EXE'ye dönüştürür (her Windows bilgisayarda çalışır).

Kullanım (TürKod Kabuğu'nda baştaki "turkod" yazılmayabilir):
    turkod exe_yap oyun.trpy --ad "Uzay Oyunu" --kayit-yeri "C:\\Oyunlarım" --kaynak-acik
    turkod kaynak "Uzay Oyunu.exe"

Program IDE'deki "Çalıştır" ile aynı yoldan geçer (doğrula -> çevir ->
runner.RUNNER_KODU) ve PyInstaller ile paketlenir. PyInstaller, kullanıcı
programlarını çalıştıran Python'da (python_embed) yoksa ilk kullanımda
kullanıcı paket klasörüne kurulur.

EXE içinde (EXE'nin kendi modülleri kullanıcının modülleriyle çakışmasın
diye "_tk_" ile başlar):
* _tk_giris.py          giriş; beklenmeyen hatayı Türkçe gösterir (GIRIS_KOKU)
* _tk_ana               RUNNER_KODU + EXE başlangıç kodu (aşağıda GIRIS_BASI)
* turkce_kod_calisma    kullanıcının çevrilmiş kodu; yalnızca derlenmiş hali
                        (bytecode) konur, kaynak metni konmaz
* _tk_kaynak            yalnızca --kaynak-acik ile: TürKod kaynak kodu
* _tk_exe_terminali     TürKod terminal penceresi (Tk), Windows konsolu
                        aktarıcısı ve kaynak penceresi (exe_terminali.py)
* _tk_cikti_cevirici    kütüphane iletilerinin çevirisi (cikti_cevirici.py)
* _tk_hata_cevirileri   Türkçe hata adları ve açıklamaları
* turkod_exe_imzasi.txt "bu bir TürKod EXE'si" işareti (kaynak komutu bakar)
* _tk_kaynak.txt        yalnızca --kaynak-acik ile: kaynak kodun düz metni
                        (IDE, EXE'yi çalıştırmadan buradan okur)

EXE geçici bir klasörde yapılır, ancak hazır olunca kaydedileceği yere
taşınır: derleme yarıda kesilirse eski EXE bozulmaz.

Kaynak koduna bakma: her TürKod EXE'si "--turkod-kaynak [dosya]" argümanıyla
başlatılınca kullanıcı kodunu çalıştırmadan kaynağı verir ya da kaynağın
gizli olduğunu söyler (çıkış kodu 3). IDE ise EXE'yi hiç çalıştırmaz: kaynağı
PyInstaller paketinin içinden okur (exe_kaynagi_oku).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:
    from . import calistirici
except ImportError:
    import calistirici

IMZA = "TURKOD-EXE-1"
IMZA_DOSYASI = "turkod_exe_imzasi.txt"
KAYNAK_DOSYASI = "_tk_kaynak.txt"
KAYNAK_GIZLI_KODU = 3

PENCERE_TURLERI = ("turkod", "konsol", "yok")

# (anahtar, bayrak, değer adı (None: tik), açıklama). Arayüzdeki EXE
# paneli (main.dart, ExeDonusturmePaneli) aynı bayrakları üretir.
SECENEKLER = [
    ("ad", "--ad", "<ad>", "EXE dosyasının adı (varsayılan: kod dosyasının adı)"),
    ("kayit_yeri", "--kayit-yeri", "<klasör>",
     "EXE'nin kaydedileceği klasör (varsayılan: kod dosyasının klasörü)"),
    ("pencere=turkod", "--turkod-terminali", None,
     "Program TürKod terminal penceresinde çalışır (varsayılan)"),
    ("pencere=konsol", "--windows-konsolu", None,
     "Program klasik siyah Windows konsolunda çalışır"),
    ("pencere=yok", "--terminalsiz", None,
     "Terminal açılmaz; yalnızca programın kendi penceresi görünür (oyunlar, çizimler)"),
    ("kaynak", "--kaynak-acik", None,
     "EXE'nin TürKod koduna 'turkod kaynak program.exe' komutuyla bakılabilir"),
    ("klasorlu", "--klasorlu", None,
     "Tek dosya yerine bir klasör yapar (program daha hızlı açılır)"),
    ("sonda_bekle", "--sonda-bekle", None,
     "Windows konsolu, program bitince Enter'a basılana kadar kapanmaz"),
    ("simge", "--simge", "<dosya.ico>", "EXE'nin simgesi"),
    ("ekler", "--dosya-ekle", "<dosya ya da klasör>",
     "Programın kullandığı resim, ses gibi dosyaları EXE'nin içine koyar "
     "(birden çok kez yazılabilir)"),
]

_TR_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC")


def _bayrak_normal(metin):
    return metin.translate(_TR_ASCII).lower().replace("_", "-")


_BAYRAKLAR = {_bayrak_normal(b): (a, d) for a, b, d, _ in SECENEKLER}


def varsayilan_ayarlar():
    return {"ad": "", "kayit_yeri": "", "pencere": "turkod", "kaynak": False,
            "klasorlu": False, "sonda_bekle": False, "simge": "", "ekler": []}


def argumanlari_ayristir(parcalar):
    """["oyun.trpy", "--ad", "Oyun", ...] -> (dosya, ayarlar, hatalar)."""
    ayar = varsayilan_ayarlar()
    dosya = None
    hatalar = []
    i = 0
    while i < len(parcalar):
        p = parcalar[i]
        i += 1
        if not p.startswith("--"):
            if dosya is None:
                dosya = p
            else:
                hatalar.append(f"Fazladan yazılmış: {p} (boşluklu adları tırnak içine al)")
            continue
        bayrak, esit, deger = p.partition("=")
        tanim = _BAYRAKLAR.get(_bayrak_normal(bayrak))
        if tanim is None:
            hatalar.append(f"Bilinmeyen seçenek: {bayrak}")
            continue
        anahtar, deger_adi = tanim
        if deger_adi is None:
            if "=" in anahtar:
                k, v = anahtar.split("=")
                ayar[k] = v
            else:
                ayar[anahtar] = True
            continue
        if not esit:
            if i >= len(parcalar) or parcalar[i].startswith("--"):
                hatalar.append(f"{bayrak} seçeneğinden sonra {deger_adi} yazılmalı.")
                continue
            deger = parcalar[i]
            i += 1
        if anahtar == "ekler":
            ayar["ekler"].append(deger)
        else:
            ayar[anahtar] = deger
    return dosya, ayar, hatalar


def _tirnak(metin):
    """Komut satırı için tırnaklar. Tırnak içindeki sondaki "\\" ikilenir:
    Windows komut satırında `"C:\\Oyun Klasörü\\"` biçimindeki \\" kapanış
    tırnağını kaçırıyor, sonraki bütün seçenekler klasör adına karışıyordu."""
    if metin and not re.search(r'[\s&|<>^]', metin):
        return metin
    sondaki = len(metin) - len(metin.rstrip("\\"))
    return f'"{metin}{chr(92) * sondaki}"'


def komut_metni(dosya, ayar):
    """Ayarlara karşılık gelen komut satırı (arayüzdeki önizlemeyle aynı)."""
    parca = ["turkod", "exe_yap", _tirnak(dosya)]
    if ayar.get("ad"):
        parca += ["--ad", _tirnak(ayar["ad"])]
    if ayar.get("kayit_yeri"):
        parca += ["--kayit-yeri", _tirnak(ayar["kayit_yeri"])]
    if ayar.get("pencere") == "konsol":
        parca.append("--windows-konsolu")
    elif ayar.get("pencere") == "yok":
        parca.append("--terminalsiz")
    if ayar.get("kaynak"):
        parca.append("--kaynak-acik")
    if ayar.get("klasorlu"):
        parca.append("--klasorlu")
    if ayar.get("sonda_bekle") and ayar.get("pencere") == "konsol":
        parca.append("--sonda-bekle")
    if ayar.get("simge"):
        parca += ["--simge", _tirnak(ayar["simge"])]
    for e in ayar.get("ekler") or []:
        parca += ["--dosya-ekle", _tirnak(e)]
    return " ".join(parca)


def yardim_metni():
    satirlar = ["Kullanım: turkod exe_yap <dosya.trpy> [seçenekler]", "", "Seçenekler:"]
    for _, bayrak, deger_adi, aciklama in SECENEKLER:
        sol = f"{bayrak} {deger_adi}" if deger_adi else bayrak
        satirlar.append(f"  {sol:<36}{aciklama}")
    satirlar += ["", "Örnek:",
                 '  turkod exe_yap oyun.trpy --ad "Uzay Oyunu" --terminalsiz --dosya-ekle resimler',
                 "", "EXE'nin kaynak koduna bakmak (--kaynak-acik ile yapıldıysa):",
                 '  turkod kaynak "Uzay Oyunu.exe"   (--kaydet [dosya.trpy] ile kaydeder)']
    return "\n".join(satirlar)


# ----------------------------------------------------------------------
# EXE'nin başlangıç kodu
# ----------------------------------------------------------------------
GIRIS_BASI = r'''# -*- coding: utf-8 -*-
# TürKod EXE girişi: TürKod IDE "EXE'ye Dönüştür" ile üretildi.
import os as _tk_os
import sys as _tk_sys

_TK_EXE = {AYAR}
_TK_EXE_IMZA = {IMZA}


def _tk_kaynak():
    try:
        from _tk_kaynak import KAYNAK
        return KAYNAK
    except ImportError:
        return None


def _tk_kaynak_ver(hedef):
    """--turkod-kaynak [dosya]: kullanıcı kodunu çalıştırmadan kaynağı verir."""
    kaynak = _tk_kaynak()
    if hedef:
        with open(hedef, "w", encoding="utf-8", newline="\n") as f:
            f.write(_TK_EXE_IMZA + "\n")
            f.write("ACIK\n" + kaynak if kaynak is not None else "GIZLI\n")
    elif _tk_sys.stdout is not None:
        try:
            _tk_sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print(kaynak if kaynak is not None else
              "Bu programın kaynak kodu gizli: EXE yapılırken "
              "'Kaynak koduna bakılabilsin' seçilmemiş.")
    else:
        import _tk_exe_terminali as exe_terminali
        exe_terminali.kaynak_goster(_TK_EXE["ad"], kaynak)
    return 0 if kaynak is not None else {GIZLI_KODU}


if len(_tk_sys.argv) > 1 and _tk_sys.argv[1] == "--turkod-kaynak":
    _tk_sys.exit(_tk_kaynak_ver(_tk_sys.argv[2] if len(_tk_sys.argv) > 2 else None))

# TürKod terminali ve Windows konsolu: bu süreç pencereyi/konsolu yönetir,
# program aynı EXE'nin ikinci bir sürecinde (TURKOD_EXE_COCUK=1) çalışır.
# Programın çıktısı bu süreçten geçerken kütüphanelerin İngilizce iletileri
# (pygame, Panda3D, Python uyarıları ...) Türkçeleştirilir; C katmanından
# yazılan iletiler ancak böyle yakalanabilir.
_TK_COCUK = _tk_os.environ.pop("TURKOD_EXE_COCUK", None) == "1"
if _TK_EXE["pencere"] in ("turkod", "konsol") and not _TK_COCUK:
    import _tk_exe_terminali as exe_terminali
    if _TK_EXE["pencere"] == "turkod":
        _tk_sys.exit(exe_terminali.calistir(_TK_EXE, _tk_kaynak()))
    _tk_sys.exit(exe_terminali.konsolda_calistir(_TK_EXE))

# Program kendi klasöründe çalışır (IDE'deki gibi); EXE'ye dosya eklendiyse
# o dosyaların açıldığı klasörde.
_TK_EXE_DIZINI = _tk_os.path.dirname(_tk_os.path.abspath(_tk_sys.executable))
_TK_PROGRAM_DIZINI = (getattr(_tk_sys, "_MEIPASS", _TK_EXE_DIZINI)
                      if _TK_EXE["veri"] else _TK_EXE_DIZINI)
_TK_PROGRAM_DOSYASI = _tk_os.path.join(_TK_PROGRAM_DIZINI, _TK_EXE["ad"] + ".trpy")
try:
    _tk_os.chdir(_TK_PROGRAM_DIZINI)
except OSError:
    pass
_tk_sys.path.insert(0, _TK_PROGRAM_DIZINI)


def _tk_akislari_hazirla():
    import io
    if _TK_EXE["pencere"] == "konsol":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleTitleW(_TK_EXE["ad"])
        except Exception:
            pass
    if _TK_EXE["pencere"] == "yok":
        # Konsol yok: çıktı saklanır, hata olursa ileti kutusunda gösterilir.
        _tk_sys.stdout = _tk_sys.stderr = io.StringIO()

        # Girdi yazılacak bir yer de yok: Python'un İngilizce "lost
        # sys.stdin" hatası yerine ne yapılacağı Türkçe söylenir.
        def _tk_girdi_yok(*_a, **_k):
            raise RuntimeError(
                "Terminalsiz EXE'de girdi_al kullanılamaz: soru yazılacak bir terminal yok. "
                "EXE'yi 'TürKod terminalinde' ya da 'Windows konsolunda' seçeneğiyle yeniden yap.")
        import builtins
        builtins.input = _tk_girdi_yok
        return
    for ad in ("stdout", "stderr"):
        akim = getattr(_tk_sys, ad)
        if akim is None:
            continue
        if _TK_COCUK:
            # Boruya tampon olmadan yazılır: input() istemi ve her satır
            # TürKod terminaline hemen ulaşır.
            yeni = io.TextIOWrapper(io.FileIO(akim.fileno(), "wb", closefd=False),
                                    encoding="utf-8", errors="replace",
                                    line_buffering=True, write_through=True)
            setattr(_tk_sys, ad, yeni)
        else:
            try:
                akim.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except Exception:
                pass
    if _tk_sys.stdin is not None:
        try:
            _tk_sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_tk_akislari_hazirla()


def _tk_exe_hata_bitti():
    """Terminalsiz EXE'de yakalanmamış hata ileti kutusunda gösterilir."""
    if _TK_EXE["pencere"] != "yok":
        return
    try:
        metin = _tk_sys.stdout.getvalue()
        i = metin.rfind("[HATA]")
        metin = (metin[i:] if i >= 0 else metin[-1500:]).strip("=\n ")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, metin, _TK_EXE["ad"] + " - Hata", 0x10)
    except Exception:
        pass


def _tk_dosya_adi_ver(kod, ad):
    sabitler = tuple(_tk_dosya_adi_ver(c, ad) if isinstance(c, type(kod)) else c
                     for c in kod.co_consts)
    return kod.replace(co_filename=ad, co_consts=sabitler)


def _tk_program_kodu():
    # Kullanıcının kodu EXE'de yalnızca derlenmiş (bytecode) olarak bulunur.
    import importlib.util
    bilgi = importlib.util.find_spec("turkce_kod_calisma")
    kod = bilgi.loader.get_code("turkce_kod_calisma")
    # Hata yazıcısı kullanıcı satırlarını bu dosya adından tanır.
    return _tk_dosya_adi_ver(kod, "turkce_kod_calisma.py")

'''

_RUNNER_DEGISIKLIKLERI = [
    ('    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:\n'
     '        kod = f.read()\n',
     "    kod = _tk_program_kodu()\n"),
    ('_ana.__file__ = os.path.abspath("turkce_kod_calisma.py")',
     "_ana.__file__ = _TK_PROGRAM_DOSYASI"),
    ('exec(compile(kod, "turkce_kod_calisma.py", "exec"), _ana.__dict__)',
     "exec(kod, _ana.__dict__)"),
    ('    _hata_yazdir(e, sys.exc_info()[2], "turkce_kod_calisma.py")\n',
     '    _hata_yazdir(e, sys.exc_info()[2], "turkce_kod_calisma.py")\n'
     "    _tk_exe_hata_bitti()\n"),
]


def giris_kodu_uret(exe_ayar, kaynak_kod=None):
    """EXE'nin giriş betiği: başlangıç kodu + IDE'nin çalıştırıcısı."""
    try:
        from .runner import RUNNER_KODU, oneri_tablolarini_yerlestir
    except ImportError:
        from runner import RUNNER_KODU, oneri_tablolarini_yerlestir
    govde = oneri_tablolarini_yerlestir(RUNNER_KODU, kaynak_kod)
    for eski, yeni in _RUNNER_DEGISIKLIKLERI:
        if govde.count(eski) != 1:
            raise RuntimeError(f"Çalıştırıcı şablonu değişmiş; EXE girişi üretilemedi: {eski.strip()!r}")
        govde = govde.replace(eski, yeni)
    bas = (GIRIS_BASI.replace("{AYAR}", repr(exe_ayar))
           .replace("{IMZA}", repr(IMZA))
           .replace("{GIZLI_KODU}", str(KAYNAK_GIZLI_KODU)))
    return bas + govde


# EXE'nin asıl giriş betiği. Program _tk_ana modülünde (giris_kodu_uret)
# çalışır; oradan kaçan beklenmeyen bir hata PyInstaller'ın İngilizce
# "Unhandled exception in script" kutusu yerine Türkçe gösterilir.
GIRIS_KOKU = r'''# -*- coding: utf-8 -*-
# TürKod EXE girişi: TürKod IDE "EXE'ye Dönüştür" ile üretildi.
import sys


def _tk_beklenmeyen_hata(e):
    tur, aciklama = type(e).__name__, str(e)
    try:
        from _tk_hata_cevirileri import hata_aciklamasi, hata_turu_adi
        tur, aciklama = hata_turu_adi(tur), hata_aciklamasi(tur, aciklama)
    except Exception:
        pass
    metin = f"Program başlatılamadı.\n{tur}: {aciklama}"
    if sys.stderr is not None and sys.stderr.__class__.__name__ != "StringIO":
        try:
            sys.stderr.write("=" * 50 + "\n[HATA] " + metin + "\n" + "=" * 50 + "\n")
            sys.stderr.flush()
            return
        except Exception:
            pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, metin, "TürKod programı - Hata", 0x10)
    except Exception:
        pass


try:
    import _tk_ana  # noqa: F401
except SystemExit:
    raise
except KeyboardInterrupt:
    print("\n[Program durduruldu (Ctrl+C)]")
    sys.exit(130)
except BaseException as e:  # noqa: BLE001
    _tk_beklenmeyen_hata(e)
    sys.exit(1)
'''

# EXE'yi yöneten süreçte (TürKod terminali / Windows konsolu) kütüphane hata
# satırlarını çeviren cikti_cevirici "runner" modülünün hata_turu_adi ve
# hata_aciklamasi işlevlerini ister. Çalıştırıcının tamamı yerine yalnızca
# bu iki işlev ve tabloları EXE'ye konur (exe_terminali, "runner" adıyla
# kaydeder).
HATA_CEVIRILERI_SABLONU = r'''# -*- coding: utf-8 -*-
"""TürKod hata adları ve açıklamaları (TürKod IDE çalıştırıcısından)."""
import re
import sys

_AD_ALANI = {"re": re, "sys": sys, "_TK_TERS_ADLAR": {TERS_ADLAR}}
exec({KOD}, _AD_ALANI)
_AD_ALANI["_TK_HATA_ADLARI"] = {KUTUPHANE_ADLARI}


def hata_aciklamasi(tip, mesaj, kaynak_kod=None):
    try:
        return _AD_ALANI["turkce_hata_aciklamasi"](tip, mesaj)
    except Exception:
        return mesaj


def hata_turu_adi(tip):
    adlar = _AD_ALANI["HATA_ISIMLERI"]
    if tip in adlar:
        return adlar[tip]
    modul, _, ad = tip.rpartition(".")
    if not modul:
        return tip
    kok = modul.split(".")[0]
    gorunen = _AD_ALANI["_KUTUPHANE_GORUNEN_ADLAR"].get(kok, kok)
    tr = _AD_ALANI["_TK_HATA_ADLARI"].get(f"{kok}.{ad}")
    if tr:
        return f"{_AD_ALANI['_bosluklu'](tr)} ({gorunen})"
    if ad.lower() == "error":
        return f"{gorunen} Hatası"
    return tip
'''


def hata_cevirileri_kodu_uret(kaynak_kod=None):
    try:
        from . import runner
    except ImportError:
        import runner
    return (HATA_CEVIRILERI_SABLONU
            .replace("{TERS_ADLAR}", repr(runner._ters_adlar(kaynak_kod)))
            .replace("{KOD}", repr(runner.HATA_ACIKLAMA_KODU))
            .replace("{KUTUPHANE_ADLARI}", repr(runner._kutuphane_hata_adlari())))


# ----------------------------------------------------------------------
# PyInstaller
# ----------------------------------------------------------------------
def _sablon_dosyasi(ad):
    """exe_terminali.py / cikti_cevirici.py: paketli derlemede _internal'a düz
    dosya olarak konur (turkod_backend.spec), geliştirici kipinde bu klasörde."""
    for kok in (calistirici._kaynak_dizini(), os.path.dirname(os.path.abspath(__file__))):
        yol = os.path.join(kok, ad)
        if os.path.isfile(yol):
            return yol
    return None


def _ortam():
    env = calistirici._ortam()
    env["PYTHONUTF8"] = "1"
    return env


def _kullanici_paket_yolu():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(base, "TurKod", "pip_packages")


def _calistir_akit(komut, yaz, cwd=None, satir_isle=None):
    """Komutu çalıştırır, çıktısını satır satır işler. (çıkış kodu, son satırlar)."""
    surec = subprocess.Popen(
        komut, cwd=cwd, env=_ortam(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
        creationflags=calistirici.CREATE_NO_WINDOW)
    son = []
    with surec.stdout:
        for satir in surec.stdout:
            satir = satir.rstrip()
            son.append(satir)
            del son[:-40]
            if satir_isle:
                satir_isle(satir)
    return surec.wait(), son


# pip ve PyInstaller'ın İngilizce iletileri. Satır başındaki "123 INFO:",
# "ERROR:" gibi önekler _arac_oneki ile ayrılır, ileti bu tabloyla çevrilir.
# Tanınmayan Python hata izi satırlarını cikti_cevirici çevirir.
_ARAC_CEVIRILERI = [(re.compile(d), t) for d, t in [
    # pip
    (r"Collecting (\S+).*", r"Alınıyor: \1"),
    (r"Downloading (\S+) \((.+)\)", r"İndiriliyor: \1 (\2)"),
    (r"Downloading (\S+).*", r"İndiriliyor: \1"),
    (r"Using cached (\S+).*", r"Önbellekten alınıyor: \1"),
    (r"Requirement already satisfied: (\S+).*", r"Zaten kurulu: \1"),
    (r"Installing collected packages: (.*)", r"Kuruluyor: \1"),
    (r"Successfully installed (.*)", r"Kuruldu: \1"),
    (r"Could not find a version that satisfies the requirement (\S+).*",
     r"\1 için uygun bir sürüm bulunamadı (internet bağlantısı olmayabilir)."),
    (r"No matching distribution found for (\S+).*", r"\1 paketi bulunamadı."),
    (r"Retrying \(.*\) after connection broken by .*",
     "Bağlantı koptu; yeniden deneniyor..."),
    (r".*(?:Failed to establish a new connection|getaddrinfo failed|NewConnectionError"
     r"|Name or service not known|No connection could be made).*",
     "İnternete bağlanılamadı. Bağlantını kontrol et."),
    (r".*(?:ReadTimeoutError|timed out).*", "Bağlantı zaman aşımına uğradı (internet çok yavaş)."),
    (r".*(?:SSLError|CERTIFICATE_VERIFY_FAILED).*",
     "Güvenli bağlantı (SSL) kurulamadı; bilgisayarın saati ya da ağ ayarları yanlış olabilir."),
    (r"Could not install packages due to an OSError: (.*)",
     r"Paketler bir sistem hatası yüzünden kurulamadı: \1"),
    (r"Target directory (.*) already exists\..*", r"Hedef klasör zaten var: \1"),
    (r"(\S+) is not a supported wheel on this platform\.",
     r"\1 bu bilgisayar için uygun değil."),
    # PyInstaller
    (r"Unable to find ['\"](.+?)['\"] when adding binary and data files\.?",
     r"EXE'ye eklenecek dosya bulunamadı: \1"),
    (r"(?:FileNotFoundError: )?Icon input file (.+) not found\.?", r"Simge dosyası bulunamadı: \1"),
    (r".*Something went wrong converting icon image ['\"](.+?)['\"].*",
     r"Simge dosyası okunamadı (bozuk ya da .ico değil): \1"),
    (r"Hidden import ['\"](.+?)['\"] not found", r"'\1' modülü bulunamadı (EXE'ye konamadı)."),
    (r"lib not found: (\S+) dependency of (.+)", r"\1 kütüphanesi bulunamadı (\2 onu istiyor)."),
    (r"Library not found: could not resolve ['\"](.+?)['\"].*", r"Kütüphane bulunamadı: \1"),
    (r"Failed to collect submodules for ['\"](.+?)['\"].*",
     r"'\1' paketinin alt modülleri toplanamadı."),
    (r"Script file ['\"](.+?)['\"] does not exist\.?", r"Program dosyası bulunamadı: \1"),
    (r"Aborting build process due to attempt to collect multiple Qt bindings packages.*",
     "Birden çok Qt paketi (PyQt5, PySide6 ...) bulundu; programın yalnızca birini kullanmalı."),
    (r"The ['\"](.+?)['\"] package is an obsolete backport.*",
     r"'\1' paketi eskimiş bir yedek paket; EXE yapmayı engelliyor. Kaldırmak için: pip kaldır \1"),
    (r".*pywintypes\.error: \((\d+), '(\w+)', '.*'\)",
     r"Windows EXE dosyasına yazamadı (\2). Antivirüs programı dosyayı kilitliyor olabilir; "
     r"biraz bekleyip yeniden dene."),
    (r".*\[WinError 5\].*|.*Access is denied.*",
     "Erişim engellendi: dosya şu an açık ya da o klasöre yazma izni yok."),
    (r".*\[WinError 32\].*",
     "Dosya başka bir program tarafından kullanılıyor; EXE'yi kapatıp yeniden dene."),
    (r".*\[WinError 225\].*|.*contains a virus or potentially unwanted software.*",
     "Antivirüs programı EXE'yi engelledi. Antivirüsün izin listesine ekleyip yeniden dene."),
    (r".*No space left on device.*|.*\[WinError 112\].*", "Diskte yeterli boş yer yok."),
    (r"RecursionError: maximum recursion depth exceeded.*",
     "Program çok derin iç içe; EXE yapma aracı sınırı aştı."),
    (r"ModuleNotFoundError: No module named ['\"](.+?)['\"]",
     r"Modül Bulunamadı Hatası: '\1' adında bir modül yok."),
]]

_ARAC_ONEKI = re.compile(r"^(?:\d+ )?(INFO|WARNING|WARN|ERROR|CRITICAL|DEBUG): ")
_ONEK_TR = {"INFO": "", "DEBUG": "", "WARNING": "Uyarı: ", "WARN": "Uyarı: ",
            "ERROR": "Hata: ", "CRITICAL": "Ciddi hata: "}


def arac_satiri_cevir(satir, durum=None):
    """pip / PyInstaller çıktısının bir satırını Türkçeye çevirir.
    Döndürür: (metin, cevrildi_mi). durum: cikti_cevirici'nin iz durumu."""
    sade = satir.strip()
    onek = ""
    m = _ARAC_ONEKI.match(sade)
    if m:
        onek = _ONEK_TR[m.group(1)]
        sade = sade[m.end():]
    for desen, karsilik in _ARAC_CEVIRILERI:
        m = desen.fullmatch(sade)
        if m:
            return onek + m.expand(karsilik), True
    try:
        try:
            from .cikti_cevirici import satiri_cevir
        except ImportError:
            from cikti_cevirici import satiri_cevir
        cevrilen = satiri_cevir(sade, durum)
        if cevrilen != sade:
            return onek + cevrilen, True
    except Exception:  # noqa: BLE001
        pass
    return onek + sade, False


def _hata_ayrintisi_yaz(son, yaz, satir_sayisi=10):
    """Başarısız bir aracın son satırlarından önemli olanları Türkçe yazar.
    Çevrilemeyen satırlar ayrıca, "İngilizce" diye belirtilerek gösterilir."""
    onemli = [s for s in son if re.search(r"ERROR|Error|Exception|Traceback|denied|failed", s)]
    secilen = (onemli or [s for s in son if s.strip()])[-satir_sayisi:]
    durum = {"iz": False}
    cevrilenler, cevrilemeyenler = [], []
    for s in secilen:
        metin, tamam = arac_satiri_cevir(s, durum)
        (cevrilenler if tamam else cevrilemeyenler).append(metin)
    for metin in dict.fromkeys(cevrilenler):
        yaz("  " + metin)
    if cevrilemeyenler:
        yaz("  Aracın kendi iletisi (İngilizce, çevirisi bilinmiyor):")
        for metin in cevrilemeyenler:
            yaz("    " + metin)


def pyinstaller_hazirla(python_exe, yaz):
    """PyInstaller yoksa kullanıcı paket klasörüne kurar. Başarılıysa True."""
    denetim = subprocess.run([python_exe, "-c", "import PyInstaller"], env=_ortam(),
                             capture_output=True, creationflags=calistirici.CREATE_NO_WINDOW)
    if denetim.returncode == 0:
        return True
    yaz("EXE yapma aracı (PyInstaller) ilk kez kuruluyor; internet bağlantısı gerekir...")
    hedef = _kullanici_paket_yolu()
    os.makedirs(hedef, exist_ok=True)

    def isle(satir):
        if satir.startswith(("Collecting", "Downloading", "Installing", "Successfully",
                             "Retrying", "WARNING: Retrying")):
            yaz("  " + arac_satiri_cevir(satir)[0])

    kod, son = _calistir_akit([python_exe, "-m", "pip", "install", "--disable-pip-version-check",
                               "--no-warn-script-location", "--upgrade", "--target", hedef,
                               "pyinstaller"], yaz, satir_isle=isle)
    if kod != 0:
        yaz("[HATA] PyInstaller kurulamadı. İnternet bağlantını kontrol et.")
        _hata_ayrintisi_yaz(son, yaz, 8)
        return False
    return True


_ADIMLAR = [
    ("Analyzing", "Kod ve kullandığı kütüphaneler inceleniyor..."),
    ("Building PYZ", "Python dosyaları paketleniyor..."),
    ("Building PKG", "Program dosyaları birleştiriliyor..."),
    ("Building EXE", "EXE dosyası oluşturuluyor..."),
    ("Building COLLECT", "Program klasörü oluşturuluyor..."),
]

# İçe aktarılınca veri dosyaları/eklentileri de toplanması gereken paketler.
_TOPLANACAK = {"ursina": ("ursina", "panda3d", "panda3d_gltf", "simplepbr"),
               "panda3d": ("panda3d",)}


def _ice_aktarilan_paketler(python_kodu):
    return set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]\w*)", python_kodu, re.M))


def _gecersiz_karakterleri_at(ad):
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", ad).strip(" .")


# Windows'ta dosya adı olamayan aygıt adları ("CON.exe" de olmaz).
_AYRILMIS_ADLAR = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                   *(f"LPT{i}" for i in range(1, 10))}

# EXE'nin kendi dosyaları. Kullanıcının modülleriyle (ör. giris.trpy)
# çakışmasınlar diye hepsi "_tk_" ile başlar ve ayrı bir klasörde hazırlanır.
_IC_GIRIS = "_tk_giris.py"
_IC_KOPYALAR = {"exe_terminali.py": "_tk_exe_terminali.py",
                "cikti_cevirici.py": "_tk_cikti_cevirici.py"}


_GECICI_ONEKI = "turkod_exe_derleme_"


def _eski_exe_gecicilerini_temizle():
    """Durdur'la yarıda kesilen ya da çöken derlemelerden kalan
    %TEMP%\\turkod_exe_derleme_* klasörleri (her biri yüzlerce MB olabilir).
    Yalnızca TürKod'un sahip dosyası koyduğu ve sahibi kapanmış klasörler
    silinir: adı benzeyen başka bir klasöre dokunulmaz."""
    try:
        kok = tempfile.gettempdir()
        for ad in os.listdir(kok):
            yol = os.path.join(kok, ad)
            if ad.startswith(_GECICI_ONEKI) and os.path.isdir(yol) \
                    and os.path.isfile(os.path.join(yol, calistirici.SAHIP_DOSYASI)) \
                    and not calistirici._sahibi_yasiyor(yol):
                shutil.rmtree(yol, ignore_errors=True)
    except OSError:
        pass


def _yazilabilir_mi(exe_yolu):
    """EXE çalışıyorsa Windows onu yazmaya açtırmaz."""
    if not os.path.exists(exe_yolu):
        return True
    try:
        with open(exe_yolu, "ab"):
            return True
    except OSError:
        return False


def _turkod_klasoru_mu(klasor, ad):
    """klasor, daha önce TürKod'un yaptığı klasörlü bir EXE mi? (içinde
    <ad>.exe ve _internal/<imza dosyası> bulunur, imza doğrudur)."""
    if not os.path.isfile(os.path.join(klasor, ad + ".exe")):
        return False
    try:
        with open(os.path.join(klasor, "_internal", IMZA_DOSYASI), encoding="utf-8") as f:
            return f.read(64).strip() == IMZA
    except (OSError, UnicodeDecodeError):
        return False


def _hedef_engeli(hedef, klasorlu, ad):
    """EXE'nin konacağı yerde TürKod'un yapmadığı bir şey varsa açıklaması
    (yoksa None). Eskiden klasörlü EXE'de hedef klasör ne olursa olsun
    siliniyordu: "uzay.trpy"nin yanındaki resimlerle dolu "uzay" klasörü
    kalıcı olarak gidiyordu. Artık yalnızca eski TürKod EXE'si değiştirilir."""
    if not os.path.lexists(hedef):
        return None
    if klasorlu:
        if os.path.isdir(hedef) and not os.path.islink(hedef) and _turkod_klasoru_mu(hedef, ad):
            return None
        return (f"'{os.path.basename(hedef)}' adında, TürKod'un yapmadığı bir klasör "
                f"ya da dosya zaten var ({hedef}). İçindekiler silinmesin diye EXE oraya "
                "konmadı. EXE'ye başka bir ad ver ya da başka bir klasör seç.")
    if os.path.isfile(hedef) and turkod_exe_mi(hedef):
        return None
    return (f"'{os.path.basename(hedef)}' zaten var ve TürKod ile yapılmamış "
            f"({hedef}). Silinmesin diye üzerine yazılmadı. EXE'ye başka bir ad ver "
            "ya da başka bir klasör seç.")


def _kaldir(yol):
    if os.path.isdir(yol) and not os.path.islink(yol):
        shutil.rmtree(yol, ignore_errors=True)
    elif os.path.lexists(yol):
        try:
            os.remove(yol)
        except OSError:
            pass


def _yerine_koy(yeni, hedef):
    """Geçici klasörde hazırlanan EXE'yi (ya da klasörü) hedefe taşır. Eski
    EXE ancak yenisi hazır olunca kaldırılır: derleme yarıda kesilirse ya da
    başarısız olursa çalışan eski EXE bozulmaz. (Hedefin eski bir TürKod
    EXE'si olduğu önceden _hedef_engeli ile denetlenir.)"""
    eski = None
    if os.path.lexists(hedef):
        eski = f"{hedef}.eski_{os.getpid()}"
        _kaldir(eski)  # önceki yarım kalmış denemeden kalan
        os.replace(hedef, eski)
    try:
        shutil.move(yeni, hedef)
    except BaseException:
        # Eskiden sürücüler arası taşıma yarıda kalınca (disk dolu) hedefte
        # yarım bir klasör kalıyor, os.replace dolu klasörün üstüne
        # yazamadığından eski EXE ".eski_PID" adıyla kalıyordu. Hedefte
        # yalnızca bizim yarım kopyamız vardır: önce o kaldırılır.
        _kaldir(hedef)
        if eski:
            os.replace(eski, hedef)
        raise
    if eski:
        if os.path.isdir(eski):
            shutil.rmtree(eski, ignore_errors=True)
        else:
            try:
                os.remove(eski)
            except OSError:
                pass


_DOSYA_ADI = re.compile(r"""(?<![\w.])["']([^"'\n\r]{1,200}?\.[A-Za-z0-9]{1,5})["']""")


def _eklenmemis_dosyalar(kod, kaynak_dizin, ekler):
    """Kodda adı geçen, kod dosyasının klasöründe duran ama EXE'ye
    eklenmemiş dosyalar (resim, ses, metin ...)."""
    eksik = []
    for ad in dict.fromkeys(_DOSYA_ADI.findall(kod)):
        yol = os.path.normcase(os.path.abspath(os.path.join(kaynak_dizin, ad)))
        if not os.path.isfile(yol) or yol.endswith(calistirici.UZANTI):
            continue
        kapsanan = any(yol == os.path.normcase(e) or yol.startswith(os.path.normcase(e) + os.sep)
                       for e in ekler)
        if not kapsanan:
            eksik.append(ad)
    return eksik


def exe_yap(dosya, ayar, yaz=print, kod=None):
    """dosya: .trpy yolu (kod verilirse yalnızca ad ve klasör için kullanılır).
    Döndürür: oluşan EXE'nin yolu ya da None."""
    def baslik(metin):
        yaz(f"[EXE] {metin}")

    dosya = os.path.abspath(os.path.expanduser(dosya))
    if kod is None:
        if not os.path.isfile(dosya) and os.path.isfile(dosya + calistirici.UZANTI):
            dosya += calistirici.UZANTI
        if not os.path.isfile(dosya):
            yaz(f"[HATA] Dosya bulunamadı: {dosya}")
            return None
        kod = calistirici._dosya_oku(dosya)
    if not kod.strip():
        yaz("[HATA] Kod boş: EXE'ye dönüştürülecek bir şey yok.")
        return None
    kaynak_dizin = os.path.dirname(dosya)
    ad = _gecersiz_karakterleri_at(ayar.get("ad") or
                                   os.path.splitext(os.path.basename(dosya))[0]) or "program"
    if ad.lower().endswith(".exe"):
        ad = _gecersiz_karakterleri_at(ad[:-4]) or "program"
    if ad.split(".")[0].upper() in _AYRILMIS_ADLAR:
        yeni_ad = f"{ad}_program"
        yaz(f"[UYARI] '{ad}' Windows'ta dosya adı olamaz; EXE '{yeni_ad}.exe' adıyla yapılacak.")
        ad = yeni_ad
    # Göreli klasör, simge ve eklenen dosyalar gibi kod dosyasının klasörüne
    # göre çözülür (eskiden terminalin o anki klasörüne göre çözülüyor,
    # paneldeki "Oluşacak dosya" yolundan başka bir yere yazılıyordu).
    kayit_yeri = os.path.abspath(os.path.join(
        kaynak_dizin, os.path.expanduser(ayar.get("kayit_yeri") or "")))
    if os.path.isfile(kayit_yeri):
        yaz(f"[HATA] Kaydedileceği yer bir klasör olmalı: {kayit_yeri}")
        return None
    pencere = ayar.get("pencere") or "turkod"
    if pencere not in PENCERE_TURLERI:
        yaz(f"[HATA] Bilinmeyen pencere türü: {pencere}")
        return None
    simge = ayar.get("simge") or ""
    if simge:
        simge = os.path.abspath(os.path.join(kaynak_dizin, simge))
        if not os.path.isfile(simge):
            yaz(f"[HATA] Simge dosyası bulunamadı: {ayar['simge']}")
            return None
        if not simge.lower().endswith(".ico"):
            yaz(f"[HATA] Simge bir .ico dosyası olmalı: {ayar['simge']}")
            return None
    ekler = []
    for e in ayar.get("ekler") or []:
        yol = os.path.abspath(os.path.join(kaynak_dizin, e))
        if not os.path.exists(yol):
            yaz(f"[HATA] Eklenecek dosya bulunamadı: {e}")
            return None
        ekler.append(yol)

    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            from .ast_katmani import dogrula
            from .converter import turkce_kodu_donustur, yerel_modulleri_hazirla
        except ImportError:
            from ast_katmani import dogrula
            from converter import turkce_kodu_donustur, yerel_modulleri_hazirla

    baslik(f"{os.path.basename(dosya)} -> {ad}.exe")
    sonuc = dogrula(kod)
    if not sonuc.basarili:
        yaz("[HATA] Kodda hata var; önce düzeltilmeli:")
        for h in sonuc.hatalar:
            yaz(f"  {h}")
        return None
    if pencere == "yok" and re.search(r"(?<![\w.])(?:girdi_al|input)\s*\(", kod):
        yaz("[UYARI] Program girdi_al kullanıyor ama terminalsiz yapılıyor: soru soracak bir "
            "terminal olmayacak. Terminal olmadan yerine 'TürKod terminalinde' seçmelisin.")
    for eksik in _eklenmemis_dosyalar(kod, kaynak_dizin, ekler):
        yaz(f"[UYARI] Program '{eksik}' dosyasını kullanıyor ama EXE'ye eklenmedi; başka "
            f"bilgisayarda bulunamaz. Eklemek için: --dosya-ekle \"{eksik}\"")
    hedef_exe = (os.path.join(kayit_yeri, ad, ad + ".exe") if ayar.get("klasorlu")
                 else os.path.join(kayit_yeri, ad + ".exe"))
    koyulacak = os.path.dirname(hedef_exe) if ayar.get("klasorlu") else hedef_exe
    engel = _hedef_engeli(koyulacak, ayar.get("klasorlu"), ad)
    if engel:
        yaz(f"[HATA] {engel}")
        return None
    if not _yazilabilir_mi(hedef_exe):
        yaz(f"[HATA] {ad}.exe şu an açık; kapatıp yeniden dene.")
        return None
    python_exe = calistirici.python_exe_bul()
    if not python_exe:
        yaz("[HATA] Python bulunamadı. TürKod'u yeniden kurmayı deneyin.")
        return None
    if not pyinstaller_hazirla(python_exe, yaz):
        return None
    if not _sablon_dosyasi("exe_terminali.py"):
        yaz("[HATA] exe_terminali.py bulunamadı. TürKod'u yeniden kurmayı deneyin.")
        return None

    _eski_exe_gecicilerini_temizle()
    gecici = tempfile.mkdtemp(prefix=_GECICI_ONEKI)
    calistirici.gecici_sahiplen(gecici)
    try:
        # kaynak/: kullanıcının kodu ve modülleri; ic/: EXE'nin kendi dosyaları.
        kaynaklar = os.path.join(gecici, "kaynak")
        ic = os.path.join(gecici, "ic")
        os.makedirs(kaynaklar)
        os.makedirs(ic)
        yerel, _yazilan, hatalar = yerel_modulleri_hazirla(kod, kaynak_dizin, kaynaklar)
        if hatalar:
            for h in hatalar:
                yaz(f"[HATA] {h}")
            return None
        try:
            python_kodu = turkce_kodu_donustur(kod, yerel_moduller=yerel)
        except Exception as e:  # noqa: BLE001 - çevirici hatası kullanıcıya gösterilir
            yaz(f"[HATA] Çeviri hatası: {e}")
            return None

        exe_ayar = {"ad": ad, "pencere": pencere,
                    "sonda_bekle": bool(ayar.get("sonda_bekle")) and pencere == "konsol",
                    "veri": bool(ekler), "kaynak_acik": bool(ayar.get("kaynak"))}

        def yazdir(klasor, ad_, icerik):
            with open(os.path.join(klasor, ad_), "w", encoding="utf-8") as f:
                f.write(icerik)

        yazdir(kaynaklar, "turkce_kod_calisma.py", python_kodu)
        yazdir(ic, _IC_GIRIS, GIRIS_KOKU)
        yazdir(ic, "_tk_ana.py", giris_kodu_uret(exe_ayar, kod))
        yazdir(ic, "_tk_hata_cevirileri.py", hata_cevirileri_kodu_uret(kod))
        yazdir(ic, IMZA_DOSYASI, IMZA + "\n")
        if ayar.get("kaynak"):
            yazdir(ic, "_tk_kaynak.py", f"KAYNAK = {kod.replace(chr(13) + chr(10), chr(10))!r}\n")
            # Düz metin kopyası: IDE kaynağı EXE'yi çalıştırmadan okur.
            with open(os.path.join(ic, KAYNAK_DOSYASI), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(kod.replace("\r\n", "\n"))
        for kaynak_ad, ic_ad in _IC_KOPYALAR.items():
            kaynak_yolu = _sablon_dosyasi(kaynak_ad)
            if kaynak_yolu:
                shutil.copy2(kaynak_yolu, os.path.join(ic, ic_ad))

        dagitim = os.path.join(gecici, "dagitim")
        komut = [python_exe, "-m", "PyInstaller", "--noconfirm",
                 "--onedir" if ayar.get("klasorlu") else "--onefile",
                 "--console" if pencere == "konsol" else "--windowed",
                 "--name", ad, "--distpath", dagitim,
                 "--workpath", os.path.join(gecici, "is"), "--specpath", gecici,
                 "--paths", kaynaklar, "--paths", ic,
                 "--hidden-import", "turkce_kod_calisma",
                 "--hidden-import", "_tk_exe_terminali", "--hidden-import", "_tk_hata_cevirileri",
                 "--add-data", os.path.join(ic, IMZA_DOSYASI) + os.pathsep + "."]
        if ayar.get("kaynak"):
            komut += ["--hidden-import", "_tk_kaynak",
                      "--add-data", os.path.join(ic, KAYNAK_DOSYASI) + os.pathsep + "."]
        if os.path.isfile(os.path.join(ic, "_tk_cikti_cevirici.py")):
            komut += ["--hidden-import", "_tk_cikti_cevirici"]
        if not simge:
            simge = _sablon_dosyasi("editor-logo.ico") or ""
        if simge:
            komut += ["--icon", simge]
        for e in ekler:
            hedef_ad = os.path.basename(e) if os.path.isdir(e) else "."
            komut += ["--add-data", e + os.pathsep + hedef_ad]
        paketler = _ice_aktarilan_paketler(python_kodu)
        for p in yerel or ():
            paketler.discard(p)
        toplanan = sorted({t for p in paketler for t in _TOPLANACAK.get(p, ())})
        for t in toplanan:
            komut += ["--collect-all", t]
        komut.append(os.path.join(ic, _IC_GIRIS))

        gorulen = set()

        def isle(satir):
            for anahtar, metin in _ADIMLAR:
                if anahtar in satir and anahtar not in gorulen:
                    gorulen.add(anahtar)
                    baslik(metin)

        baslik("Paketleniyor; bu işlem birkaç dakika sürebilir...")
        bas = time.monotonic()
        kod_, son = _calistir_akit(komut, yaz, cwd=gecici, satir_isle=isle)
        hazir = os.path.join(dagitim, ad) if ayar.get("klasorlu") else \
            os.path.join(dagitim, ad + ".exe")
        hazir_exe = os.path.join(hazir, ad + ".exe") if ayar.get("klasorlu") else hazir
        if kod_ != 0 or not os.path.isfile(hazir_exe):
            yaz("[HATA] EXE oluşturulamadı. Ayrıntı:")
            _hata_ayrintisi_yaz(son, yaz)
            return None
        try:
            os.makedirs(kayit_yeri, exist_ok=True)
            if not _yazilabilir_mi(hedef_exe):
                raise PermissionError(f"{ad}.exe şu an açık")
            # Derleme dakikalar sürer: bu arada kullanıcı aynı adla bir
            # klasör/dosya oluşturmuş olabilir; yeniden denetlenir.
            engel = _hedef_engeli(koyulacak, ayar.get("klasorlu"), ad)
            if engel:
                yaz(f"[HATA] {engel}")
                return None
            _yerine_koy(hazir, koyulacak)
        except OSError as e:
            yaz(f"[HATA] EXE hazırlandı ama kaydedilemedi ({kayit_yeri}): "
                + _beklenmeyen_hata_metni(e).split(". ", 1)[-1])
            yaz("  EXE açıksa kapat ya da başka bir klasör seç, sonra yeniden dene.")
            return None
        boyut = os.path.getsize(hedef_exe) / (1024 * 1024)
        baslik(f"Hazır! ({time.monotonic() - bas:.0f} sn, {boyut:.1f} MB)")
        yaz(f"  {hedef_exe}")
        if ayar.get("klasorlu"):
            yaz(f"  Başka bilgisayara '{ad}' klasörünün tamamını kopyala.")
        if ayar.get("kaynak"):
            yaz(f'  Kaynak koduna bakmak için: turkod kaynak "{hedef_exe}"')
        return hedef_exe
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


# ----------------------------------------------------------------------
# EXE'nin kaynak koduna bakma
# ----------------------------------------------------------------------
# Eskiden "kaynağı gör" EXE'yi "--turkod-kaynak" ile ÇALIŞTIRIYORDU; TürKod
# EXE'si olup olmadığına da yalnızca imza dosyasının adı dosyada düz metin
# olarak geçiyor mu diye bakılıyordu. Bu adı içeren herhangi bir indirilmiş
# EXE böylece başlatılabiliyordu. Artık EXE hiç çalıştırılmaz: PyInstaller
# paketinin içindekiler listesi okunur, kaynak oradan çıkarılır.
_PAKET_IMZASI = b"MEI\014\013\012\013\016"
_PAKET_SONU = "!8sIIII64s"
_PAKET_GIRDISI = "!IIIIBc"
_EN_FAZLA_ICERIK = 64 * 1024 * 1024


class _Paket:
    """PyInstaller'ın EXE'nin sonuna eklediği paketin (CArchive) salt okunur
    hâli. Paket değilse ValueError."""

    def __init__(self, yol):
        import struct
        self.yol = yol
        sonu_boy = struct.calcsize(_PAKET_SONU)
        with open(yol, "rb") as f:
            f.seek(0, os.SEEK_END)
            boy = f.tell()
            # Paketin sonu dosyanın sonundadır (imzalı EXE'de ardından
            # yalnızca birkaç KB sertifika gelir).
            bas = max(0, boy - 1024 * 1024)
            f.seek(bas)
            kuyruk = f.read()
            yer = kuyruk.rfind(_PAKET_IMZASI)
            if yer < 0 or yer + sonu_boy > len(kuyruk):
                raise ValueError("PyInstaller paketi değil")
            _m, paket_boy, toc_yeri, toc_boy, _s, _l = struct.unpack(
                _PAKET_SONU, kuyruk[yer:yer + sonu_boy])
            son = bas + yer + sonu_boy
            self.baslangic = son - paket_boy
            if self.baslangic < 0 or toc_boy > 16 * 1024 * 1024 \
                    or toc_yeri + toc_boy > paket_boy:
                raise ValueError("bozuk paket")
            f.seek(self.baslangic + toc_yeri)
            toc = f.read(toc_boy)
        self.girdiler = {}
        girdi_boy = struct.calcsize(_PAKET_GIRDISI)
        i = 0
        while i + girdi_boy <= len(toc):
            uzunluk, yer_, sikisik, acik, sikistirma, tur = struct.unpack(
                _PAKET_GIRDISI, toc[i:i + girdi_boy])
            if uzunluk < girdi_boy or i + uzunluk > len(toc):
                raise ValueError("bozuk içerik listesi")
            ad = toc[i + girdi_boy:i + uzunluk].rstrip(b"\0").decode("utf-8", "replace")
            i += uzunluk
            if tur != b"o":
                self.girdiler[ad] = (yer_, sikisik, acik, sikistirma, tur)

    def oku(self, ad):
        import zlib
        yer, sikisik, acik, sikistirma, _tur = self.girdiler[ad]
        if sikisik > _EN_FAZLA_ICERIK or acik > _EN_FAZLA_ICERIK:
            raise ValueError("çok büyük")
        with open(self.yol, "rb") as f:
            f.seek(self.baslangic + yer)
            veri = f.read(sikisik)
        if sikistirma:
            veri = zlib.decompressobj().decompress(veri, _EN_FAZLA_ICERIK)
        return veri

    def pyz_modulu(self, modul):
        """PYZ arşivindeki modülün kod nesnesi; modül yoksa None.
        Kod nesnesi yalnızca yüklenir (marshal), ÇALIŞTIRILMAZ."""
        import importlib.util
        import marshal
        import struct
        import zlib
        pyz = next((ad for ad, g in self.girdiler.items() if g[4] == b"z"), None)
        if pyz is None:
            raise ValueError("PYZ yok")
        yer = self.baslangic + self.girdiler[pyz][0]
        with open(self.yol, "rb") as f:
            f.seek(yer)
            bas = f.read(12)
            if bas[:4] != b"PYZ\0":
                raise ValueError("PYZ bozuk")
            sihir = bas[4:8]
            toc_yeri = struct.unpack("!i", bas[8:12])[0]
            f.seek(yer + toc_yeri)
            toc = dict(marshal.loads(f.read(min(self.girdiler[pyz][1], 16 * 1024 * 1024))))
            girdi = toc.get(modul)
            if girdi is None:
                return None
            if sihir != importlib.util.MAGIC_NUMBER:
                raise _SurumFarki()
            _tur, m_yer, m_boy = girdi
            if m_boy > _EN_FAZLA_ICERIK:
                raise ValueError("çok büyük")
            f.seek(yer + m_yer)
            veri = zlib.decompressobj().decompress(f.read(m_boy), _EN_FAZLA_ICERIK)
        return marshal.loads(veri)


class _SurumFarki(Exception):
    pass


def _imza_dogru_mu(veri):
    return veri.decode("utf-8", "replace").strip() == IMZA


def _exe_bilgisi(exe_yolu):
    """(paket ya da None, klasörlü EXE'nin _internal klasörü ya da None).
    TürKod EXE'si değilse (None, None)."""
    try:
        paket = _Paket(exe_yolu)
    except Exception:  # noqa: BLE001 - bozuk/yabancı dosya
        return None, None
    if IMZA_DOSYASI in paket.girdiler:
        try:
            if _imza_dogru_mu(paket.oku(IMZA_DOSYASI)):
                return paket, None
        except Exception:  # noqa: BLE001
            return None, None
    ic = os.path.join(os.path.dirname(exe_yolu), "_internal")
    try:
        with open(os.path.join(ic, IMZA_DOSYASI), "rb") as f:
            if _imza_dogru_mu(f.read(64)):
                return paket, ic
    except OSError:
        pass
    return None, None


def turkod_exe_mi(exe_yolu):
    """EXE'yi çalıştırmadan, TürKod ile yapıldığını anlar: dosya bir
    PyInstaller paketi olmalı ve içindeki (ya da klasörlü EXE'de
    _internal'daki) imza dosyası TürKod imzasını taşımalı."""
    return _exe_bilgisi(exe_yolu)[0] is not None


def _metne(veri):
    return veri.decode("utf-8", "replace").replace("\r\n", "\n")


_GIZLI_METNI = ("Bu programın kaynak kodu gizli: EXE yapılırken "
                "'Kaynak koduna bakılabilsin' seçilmemiş.")


def exe_kaynagi_oku(exe_yolu, zaman_asimi=120):
    """(durum, metin): durum "acik" (metin = TürKod kodu), "gizli",
    "turkod_degil" ya da "hata" (metin = açıklama). EXE çalıştırılmaz.
    (zaman_asimi eski çağıranlar için duruyor; kullanılmıyor.)"""
    exe_yolu = os.path.abspath(os.path.expanduser(exe_yolu))
    if not os.path.isfile(exe_yolu):
        return "hata", f"Dosya bulunamadı: {exe_yolu}"
    if not exe_yolu.lower().endswith(".exe"):
        return "turkod_degil", "Bu dosya TürKod ile yapılmış bir EXE değil."
    paket, ic = _exe_bilgisi(exe_yolu)
    if paket is None:
        return "turkod_degil", "Bu dosya TürKod ile yapılmış bir EXE değil."
    try:
        # Yeni EXE'ler: kaynağın düz metin kopyası.
        if ic is not None:
            yol = os.path.join(ic, KAYNAK_DOSYASI)
            if os.path.isfile(yol):
                if os.path.getsize(yol) > _EN_FAZLA_ICERIK:
                    raise ValueError("çok büyük")
                with open(yol, "rb") as f:
                    return "acik", _metne(f.read())
        elif KAYNAK_DOSYASI in paket.girdiler:
            return "acik", _metne(paket.oku(KAYNAK_DOSYASI))
        # Eski EXE'ler: kaynak yalnızca derlenmiş _tk_kaynak modülünde.
        kod = paket.pyz_modulu("_tk_kaynak")
    except _SurumFarki:
        return "hata", ("Bu EXE TürKod'un eski bir sürümüyle yapılmış; kaynak kodu "
                        "okunamadı. Kaynağı görmek için EXE'yi yeniden yap ya da "
                        "EXE'nin kendisini --turkod-kaynak ile aç.")
    except Exception:  # noqa: BLE001 - bozuk paket
        return "hata", "EXE'nin içi okunamadı (bozuk olabilir)."
    if kod is None:
        return "gizli", _GIZLI_METNI
    metin = next((c for c in getattr(kod, "co_consts", ()) if isinstance(c, str)), None)
    if metin is None:
        return "hata", "EXE'nin içi okunamadı (bozuk olabilir)."
    return "acik", metin


def _beklenmeyen_hata_metni(e):
    """Beklenmeyen bir hatanın Türkçe tek satırlık açıklaması (İngilizce
    Python hata izi yerine)."""
    tur, aciklama = type(e).__name__, str(e)
    try:
        try:
            from .runner import hata_aciklamasi, hata_turu_adi
        except ImportError:
            from runner import hata_aciklamasi, hata_turu_adi
        tur, aciklama = hata_turu_adi(tur), hata_aciklamasi(tur, aciklama)
    except Exception:  # noqa: BLE001
        pass
    return f"[HATA] Beklenmeyen bir sorun oldu. {tur}: {aciklama}"


def _hatasiz(islev):
    def sarili(parcalar, yaz=print):
        try:
            return islev(parcalar, yaz)
        except KeyboardInterrupt:
            yaz("[Durduruldu]")
            return 130
        except Exception as e:  # noqa: BLE001 - kullanıcıya Türkçe gösterilir
            yaz(_beklenmeyen_hata_metni(e))
            return 1
    sarili.__doc__ = islev.__doc__
    return sarili


@_hatasiz
def kaynak_komutu(parcalar, yaz=print):
    """turkod kaynak <program.exe> [--kaydet [dosya.trpy]]. Çıkış kodu döndürür."""
    if not parcalar:
        yaz("Kullanım: turkod kaynak <program.exe> [--kaydet [dosya.trpy]]")
        return 2
    exe = parcalar[0]
    kaydet = None
    if len(parcalar) > 1 and _bayrak_normal(parcalar[1]) == "--kaydet":
        kaydet = (parcalar[2] if len(parcalar) > 2
                  else os.path.splitext(os.path.abspath(exe))[0] + calistirici.UZANTI)
    durum, metin = exe_kaynagi_oku(exe)
    if durum != "acik":
        yaz(("[HATA] " if durum != "gizli" else "") + metin)
        return 1 if durum != "gizli" else KAYNAK_GIZLI_KODU
    if kaydet:
        kaydet = os.path.abspath(kaydet)
        if os.path.exists(kaydet):
            yaz(f"[HATA] {kaydet} zaten var; başka bir ad yaz: --kaydet yeni_ad.trpy")
            return 1
        with open(kaydet, "w", encoding="utf-8") as f:
            f.write(metin)
        yaz(f"Kaynak kod kaydedildi: {kaydet}")
        return 0
    yaz(metin.rstrip("\n"))
    return 0


@_hatasiz
def exe_komutu(parcalar, yaz=print):
    """turkod exe_yap <dosya.trpy> [seçenekler]. Çıkış kodu döndürür."""
    if not parcalar or parcalar[0] in ("--yardim", "--yardım", "-h", "--help", "?"):
        yaz(yardim_metni())
        return 0 if parcalar else 2
    dosya, ayar, hatalar = argumanlari_ayristir(parcalar)
    if dosya is None:
        hatalar.insert(0, "Dönüştürülecek .trpy dosyası yazılmadı.")
    if hatalar:
        for h in hatalar:
            yaz(f"[HATA] {h}")
        yaz("Seçenekleri görmek için: turkod exe_yap --yardim")
        return 2
    return 0 if exe_yap(dosya, ayar, yaz) else 1
