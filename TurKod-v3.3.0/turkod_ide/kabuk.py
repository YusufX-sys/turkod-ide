"""TürKod Kabuğu: CMD tarzı etkileşimli komut satırı.

Açma yolları:
    turkod kabuk                 (bu konsolda)
    turkod --kabuk-pencere       (ayrı bir konsol penceresinde)
    IDE → Terminal → "TürKod Kabuğu" (program içinde)

İçinde hem kabuk komutları (çalıştır, düzelt, çevir, anlam, dersler ...) hem de
doğrudan TürKod kodu yazılır. Kod satır satır çalışır, değişkenler oturum
boyunca kalır; ":" ile biten satırlardan sonra blok bitene (boş satır) kadar
girdi toplanır. "dersler" komutu TürKod'u adım adım öğretir.
"""
import builtins
import codeop
import os
import shlex
import sys
import time
import traceback
import types

try:
    from . import calistirici, logo_ascii
    from .converter import python_kodu_turkceye_cevir, turkce_kodu_donustur
    from .runner import RUNNER_ORTAK, hata_aciklamasi, hata_turu_adi, oneri_tablolarini_yerlestir
except ImportError:
    import calistirici
    import logo_ascii
    from converter import python_kodu_turkceye_cevir, turkce_kodu_donustur
    from runner import RUNNER_ORTAK, hata_aciklamasi, hata_turu_adi, oneri_tablolarini_yerlestir


# ANSI renkleri yalnızca gerçek konsolda (IDE terminali düz metin gösterir).
def _renkli_mi():
    return bool(getattr(sys.stdout, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")


class _R:
    ACIK = _renkli_mi()
    VURGU = "\x1b[96m" if ACIK else ""
    YESIL = "\x1b[92m" if ACIK else ""
    SARI = "\x1b[93m" if ACIK else ""
    KIRMIZI = "\x1b[91m" if ACIK else ""
    SOLUK = "\x1b[90m" if ACIK else ""
    KALIN = "\x1b[1m" if ACIK else ""
    SON = "\x1b[0m" if ACIK else ""


_ASIL_PRINT, _ASIL_INPUT = builtins.print, builtins.input

ISTEM = "TürKod> "
DEVAM_ISTEMI = "   ...> "

# ----------------------------------------------------------------------
# Dersler
# ----------------------------------------------------------------------
DERSLER = [
    {
        "baslik": "Ekrana yazdırma",
        "anlatim": "yazdır(...) parantez içindekini ekrana yazar. Metinler tırnak "
                   "içinde yazılır, sayılar tırnaksız.",
        "ornek": 'yazdır("Merhaba Dünya!")\nyazdır(3 + 4)',
        "gorev": 'Kendi adını ekrana yazdır: yazdır("...")',
    },
    {
        "baslik": "Değişkenler",
        "anlatim": "Bir değeri isimle saklamak için '=' kullanılır. f\"...\" "
                   "metinlerinde {değişken} yazınca değeri yerine konur.",
        "ornek": 'ad = "Ayşe"\nyaş = 12\nyazdır(f"{ad} {yaş} yaşında")',
        "gorev": "şehir adında bir değişken oluştur ve yazdır.",
    },
    {
        "baslik": "Kullanıcıdan girdi alma",
        "anlatim": "girdi_al(...) kullanıcının yazdığını METİN olarak verir. "
                   "Sayıya çevirmek için tamsayı(...) ya da ondalıklı(...) kullan.",
        "ornek": 'yaş = tamsayı(girdi_al("Yaşın kaç? "))\nyazdır(f"Seneye {yaş + 1} olacaksın")',
        "gorev": "İki sayı al ve toplamını yazdır.",
    },
    {
        "baslik": "Karar verme (eğer)",
        "anlatim": "eğer koşul: ... değilse_eğer koşul: ... değilse: ... "
                   "Bloklar 4 boşluk girintiyle yazılır.",
        "ornek": 'puan = 75\neğer puan >= 85:\n    yazdır("Pekiyi")\n'
                 'değilse_eğer puan >= 50:\n    yazdır("Geçti")\ndeğilse:\n    yazdır("Kaldı")',
        "gorev": "Bir sayının tek mi çift mi olduğunu yazdır (ipucu: sayı % 2).",
    },
    {
        "baslik": "Döngüler (için / döngü)",
        "anlatim": "için x içinde aralık(...): belirli sayıda tekrarlar. "
                   "döngü koşul: koşul doğru olduğu sürece tekrarlar. kır döngüden çıkar.",
        "ornek": 'için i içinde aralık(1, 4):\n    yazdır(i, "kere merhaba")\n'
                 'sayaç = 3\ndöngü sayaç > 0:\n    yazdır(sayaç)\n    sayaç -= 1',
        "gorev": "1'den 10'a kadar sayıların toplamını bul.",
    },
    {
        "baslik": "Listeler",
        "anlatim": "Köşeli parantezle birden çok değer saklanır. sona_ekle ekler, "
                   "uzunluk(...) eleman sayısını verir, [0] ilk elemandır.",
        "ornek": 'meyveler = ["elma", "armut"]\nmeyveler.sona_ekle("kiraz")\n'
                 'yazdır(meyveler[0], uzunluk(meyveler))\niçin m içinde meyveler:\n    yazdır(m)',
        "gorev": "Beş sayılık bir listenin en büyüğünü en_büyük(...) ile bul.",
    },
    {
        "baslik": "Fonksiyonlar",
        "anlatim": "fonksiyon ad(parametreler): ile tekrar kullanılabilir kod yazılır; "
                   "döndür sonucu geri verir.",
        "ornek": 'fonksiyon kare(x):\n    döndür x * x\n\nyazdır(kare(7))',
        "gorev": "İki sayının ortalamasını döndüren bir fonksiyon yaz.",
    },
    {
        "baslik": "Sözlükler",
        "anlatim": "{anahtar: değer} çiftleri saklar. .öğeler() ile anahtar ve "
                   "değerler birlikte gezilir.",
        "ornek": 'notlar = {"Ali": 90, "Ece": 85}\nnotlar["Can"] = 70\n'
                 'için ad, puan içinde notlar.öğeler():\n    yazdır(ad, puan)',
        "gorev": "Üç ülkenin başkentini saklayan bir sözlük oluştur.",
    },
    {
        "baslik": "Hataları yakalama",
        "anlatim": "dene: içindeki kod hata verirse program durmaz, "
                   "hata_yakala bloğu çalışır.",
        "ornek": 'dene:\n    sonuç = 10 / 0\nhata_yakala SıfıraBölmeHatası:\n'
                 '    yazdır("Sıfıra bölünemez!")',
        "gorev": "Kullanıcıdan sayı iste; sayı yazmazsa uyarı ver (DeğerHatası).",
    },
    {
        "baslik": "Sınıflar",
        "anlatim": "sınıf ile kendi veri türünü tanımlarsın. __başlat__ nesne "
                   "oluşurken çalışır, kendisi nesnenin kendisidir.",
        "ornek": 'sınıf Kedi:\n    fonksiyon __başlat__(kendisi, ad):\n'
                 '        kendisi.ad = ad\n    fonksiyon miyavla(kendisi):\n'
                 '        yazdır(kendisi.ad + ": Miyav!")\n\nKedi("Tekir").miyavla()',
        "gorev": "Hesap adında, para_yatır ve bakiye metotları olan bir sınıf yaz.",
    },
]

KOMUTLAR = [
    ("yardım", "", "Bu yardımı gösterir"),
    ("dersler", "", "TürKod derslerini listeler"),
    ("ders", "<no>", "Dersi gösterir (örnek + görev)"),
    ("dene", "<no>", "Dersin örneğini bu kabukta çalıştırır"),
    ("anlam", "<kelime>", "Kelimenin ne işe yaradığını anlatır"),
    ("çevir", "<TürKod kodu>", "TürKod satırını Python'a çevirir"),
    ("pyçevir", "<Python kodu>", "Python satırını TürKod'a çevirir"),
    ("çalıştır", "<dosya.trpy> [arg]", "Programı çalıştırır"),
    ("kontrol", "<dosya.trpy>", "Sözdizimi denetimi yapar"),
    ("düzelt", "<dosya.trpy> [--yaz]", "Akıllı Düzelt (--yaz: dosyaya kaydeder)"),
    ("biçimlendir", "<dosya.trpy> [--yaz]", "Kodu düzenli biçime sokar"),
    ("pythona", "<dosya.trpy>", "Dosyanın Python karşılığını yazar"),
    ("exe_yap", "<dosya.trpy> [--seçenekler]", "Programı EXE yapar (exe_yap --yardim)"),
    ("kaynak", "<program.exe> [--kaydet]", "EXE'nin TürKod kodunu gösterir"),
    ("değişkenler", "", "Oturumdaki değişkenleri listeler"),
    ("sıfırla", "", "Oturumu (değişkenleri) temizler"),
    ("temizle", "", "Ekranı temizler"),
    ("editör", "[dosya]", "TürKod editörünü açar"),
    ("sürüm", "", "TürKod sürümü"),
    ("logo", "[renksiz]", "TürKod logosunu bütün terminale çizer"),
    ("çıkış", "", "Kabuktan çıkar"),
]

# ASCII yazımlar ve kısaltmalar -> komut adı.
_TAKMA = {
    "yardim": "yardım", "?": "yardım", "help": "yardım", "komutlar": "yardım",
    "ogret": "dersler", "öğret": "dersler", "calistir": "çalıştır", "duzelt": "düzelt",
    "cevir": "çevir", "pycevir": "pyçevir", "bicimlendir": "biçimlendir",
    "degiskenler": "değişkenler", "sifirla": "sıfırla", "cls": "temizle",
    "clear": "temizle", "editor": "editör", "surum": "sürüm", "cikis": "çıkış",
    "çık": "çıkış", "cik": "çıkış", "exit": "çıkış", "quit": "çıkış",
    "python'a": "pythona", "exe": "exe_yap", "exe-yap": "exe_yap", "exeyap": "exe_yap",
    "amblem": "logo", "simge": "logo",
}
_KOMUT_ADLARI = {k for k, _, _ in KOMUTLAR}


def komut_mu(satir):
    """(komut, argüman) ya da None. Satırın ilk sözcüğü bir komutsa ve satır
    kod gibi görünmüyorsa ("ders = 3", "sürüm()") komuttur. Başa nokta
    konursa (.yardım) her zaman komuttur."""
    s = satir.strip()
    if not s:
        return None
    zorla = s.startswith(".")
    if zorla:
        s = s[1:]
    # IDE'nin EXE panelindeki komut "turkod exe_yap ..." biçimindedir; kabukta
    # da aynen yapıştırılabilsin.
    if s.lower().startswith("turkod "):
        s = s[7:].lstrip()
        zorla = True
    ilk, _, kalan = s.partition(" ")
    ad = _TAKMA.get(ilk.lower(), ilk.lower())
    if ad not in _KOMUT_ADLARI:
        return None
    if not zorla:
        k = kalan.lstrip()
        if k.startswith(("=", "(", "[", ".", "+=", "-=")) or ilk.endswith(("(", ":")):
            return None
    return ad, kalan.strip()


class TurKodKabugu:
    def __init__(self, giris=None, cikis=None):
        self.giris = giris or sys.stdin
        self.cikis = cikis or sys.stdout
        self.ad_alani = None
        self.kaynak = []          # bu oturumda çalışan TürKod girişleri
        self.sifirla()

    # -- çıktı --------------------------------------------------------
    def yaz(self, metin="", son="\n"):
        self.cikis.write(metin + son)
        self.cikis.flush()

    def baslik(self):
        self.yaz(f"{_R.VURGU}{_R.KALIN}TürKod Terminali {calistirici.surum()}{_R.SON}")
        self.yaz(f"{_R.SOLUK}TürKod kodu yaz ya da bir komut kullan. "
                 f"'yardım' komutları, 'dersler' TürKod'u adım adım öğretir.{_R.SON}")

    # -- oturum -------------------------------------------------------
    def sifirla(self):
        """Çalıştırıcının ortak ön kodu (Türkçe print/input, hata çevirisi)
        yeni bir __main__ ad alanına yüklenir."""
        modul = types.ModuleType("__main__")
        ad_alani = modul.__dict__
        ad_alani["__builtins__"] = builtins
        # Ön kod builtins.print/input'u sarar; her sıfırlamada iç içe
        # sarılmasın diye önce asılları geri konur.
        builtins.print, builtins.input = _ASIL_PRINT, _ASIL_INPUT
        try:
            exec(compile(oneri_tablolarini_yerlestir(RUNNER_ORTAK, None),
                         "<turkod-onkod>", "exec"), ad_alani)
        except Exception:  # noqa: BLE001 - ön kod olmadan da çalışılabilir
            pass
        self._on_adlar = set(ad_alani)
        self.ad_alani = ad_alani
        self.kaynak = []

    # -- kod ----------------------------------------------------------
    def tamam_mi(self, tr_kod):
        """Girilen blok çalışmaya hazır mı? (None: devam satırı gerekli)."""
        if tr_kod.rstrip().endswith(":"):
            return False
        try:
            py = self.cevir(tr_kod)
        except Exception:  # noqa: BLE001 - çeviri hatası çalıştırınca gösterilir
            return True
        try:
            return codeop.compile_command(py, "<kabuk>", "exec") is not None
        except (SyntaxError, ValueError, OverflowError):
            return True

    def cevir(self, tr_kod):
        """Girişi, oturumda daha önce tanımlanan adlarla birlikte çevirir:
        "kare" gibi sözlükte karşılığı olan bir ad kullanıcı tarafından
        tanımlandıysa çevrilmemeli. Çevirici satır sayısını koruduğundan
        yalnızca son satırlar (yeni giriş) alınır."""
        if not self.kaynak:
            return turkce_kodu_donustur(tr_kod)
        onceki = "\n".join(self.kaynak)
        tam = turkce_kodu_donustur(onceki + "\n" + tr_kod)
        satirlar = tam.split("\n")
        n = tr_kod.count("\n") + 1
        if len(satirlar) != onceki.count("\n") + 1 + n:
            return turkce_kodu_donustur(tr_kod)
        return "\n".join(satirlar[-n:])

    def kod_calistir(self, tr_kod):
        try:
            py = self.cevir(tr_kod)
        except Exception as e:  # noqa: BLE001
            self.yaz(f"{_R.KIRMIZI}[Çeviri hatası] {e}{_R.SON}")
            return False
        # Tek bir ifade ise değeri (Python REPL'i gibi) gösterilir.
        try:
            kod = compile(py, "<kabuk>", "single")
        except SyntaxError:
            try:
                kod = compile(py, "<kabuk>", "exec")
            except SyntaxError as e:
                self._hata_goster(e, tr_kod)
                return False
        eski_kanca = sys.displayhook
        sys.displayhook = self._goster
        try:
            exec(kod, self.ad_alani)
            self.kaynak.append(tr_kod)
            return True
        except KeyboardInterrupt:
            self.yaz(f"\n{_R.SARI}[Durduruldu]{_R.SON}")
        except SystemExit:
            self.yaz(f"{_R.SOLUK}[çık() çağrıldı; kabuk açık kalıyor]{_R.SON}")
        except BaseException as e:  # noqa: BLE001
            self._hata_goster(e, tr_kod)
        finally:
            sys.displayhook = eski_kanca
        return False

    def _goster(self, deger):
        if deger is None:
            return
        self.ad_alani["_"] = deger
        # Doğru/Yanlış/Hiçlik (kapsayıcıların içindekiler dahil) Türkçe yazılır.
        tr_repr = self.ad_alani.get("_tr_repr")
        try:
            metin = tr_repr(deger) if tr_repr else repr(deger)
        except Exception:  # noqa: BLE001
            metin = repr(deger)
        self.yaz(f"{_R.VURGU}{metin}{_R.SON}")

    def _hata_goster(self, e, tr_kod=""):
        tip = type(e).__name__
        try:
            tur = hata_turu_adi(tip)
        except Exception:  # noqa: BLE001
            tur = tip
        try:
            aciklama = hata_aciklamasi(tip, str(e), tr_kod)
        except Exception:  # noqa: BLE001
            aciklama = str(e)
        satir = getattr(e, "lineno", None)
        if satir is None:
            tb = e.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code.co_filename == "<kabuk>":
                    satir = tb.tb_lineno
                tb = tb.tb_next
        konum = f" (satır {satir})" if satir and tr_kod.count("\n") else ""
        self.yaz(f"{_R.KIRMIZI}[HATA] {tur}{konum}: {aciklama}{_R.SON}")

    # -- komutlar -----------------------------------------------------
    def komut(self, ad, arg):
        islev = getattr(self, "_k_" + {
            "yardım": "yardim", "dersler": "dersler", "ders": "ders", "dene": "dene",
            "anlam": "anlam", "çevir": "cevir", "pyçevir": "pycevir",
            "çalıştır": "calistir", "kontrol": "kontrol", "düzelt": "duzelt",
            "biçimlendir": "bicimlendir", "pythona": "pythona",
            "değişkenler": "degiskenler", "sıfırla": "sifirla", "temizle": "temizle",
            "editör": "editor", "sürüm": "surum", "çıkış": "cikis",
            "exe_yap": "exe_yap", "kaynak": "kaynak", "logo": "logo",
        }[ad])
        return islev(arg)

    def _k_yardim(self, _arg):
        self.yaz(f"{_R.KALIN}Komutlar{_R.SON} (başa nokta da konabilir: .yardım)")
        for ad, args, aciklama in KOMUTLAR:
            sol = f"{ad} {args}".strip()
            self.yaz(f"  {_R.VURGU}{sol:<34}{_R.SON}{aciklama}")
        self.yaz(f"\n{_R.KALIN}Kod yazma{_R.SON}")
        self.yaz("  TürKod kodunu doğrudan yaz: yazdır(\"Merhaba\"), x = 5, x * 2 ...")
        self.yaz("  ':' ile biten satırdan sonra blok yazılır; boş satır bloğu bitirir.")
        self.yaz(f"\n{_R.KALIN}Terminalden{_R.SON}")
        self.yaz("  turkod --yardim  bütün komut satırı seçeneklerini gösterir.")

    def _k_dersler(self, _arg):
        self.yaz(f"{_R.KALIN}TürKod Dersleri{_R.SON}  (ders <no> ile aç, dene <no> ile çalıştır)")
        for i, d in enumerate(DERSLER, 1):
            self.yaz(f"  {_R.VURGU}{i:>2}{_R.SON}. {d['baslik']}")

    def _ders_no(self, arg):
        try:
            no = int(arg.split()[0])
        except (ValueError, IndexError):
            self.yaz(f"{_R.SARI}Ders numarası yaz: ders 1 … ders {len(DERSLER)}{_R.SON}")
            return None
        if not 1 <= no <= len(DERSLER):
            self.yaz(f"{_R.SARI}1 ile {len(DERSLER)} arasında bir ders seç.{_R.SON}")
            return None
        return no

    def _k_ders(self, arg):
        no = self._ders_no(arg)
        if no is None:
            return
        d = DERSLER[no - 1]
        self.yaz(f"\n{_R.KALIN}{_R.VURGU}Ders {no}: {d['baslik']}{_R.SON}")
        self.yaz(d["anlatim"])
        self.yaz(f"\n{_R.KALIN}Örnek:{_R.SON}")
        for s in d["ornek"].split("\n"):
            self.yaz(f"  {_R.YESIL}{s}{_R.SON}")
        self.yaz(f"\n{_R.KALIN}Görev:{_R.SON} {d['gorev']}")
        sonraki = f", sonra 'ders {no + 1}'" if no < len(DERSLER) else ""
        self.yaz(f"{_R.SOLUK}Örneği çalıştırmak için: dene {no}{sonraki}{_R.SON}\n")

    def _k_dene(self, arg):
        no = self._ders_no(arg)
        if no is None:
            return
        ornek = DERSLER[no - 1]["ornek"]
        if "girdi_al" in ornek and not getattr(self.giris, "isatty", lambda: True)():
            self.yaz(f"{_R.SOLUK}(Bu örnek senden girdi bekleyecek.){_R.SON}")
        for s in ornek.split("\n"):
            self.yaz(f"{_R.SOLUK}{ISTEM}{_R.SON}{s}")
        self.kod_calistir(ornek)

    def _k_anlam(self, arg):
        """Kelimenin ne işe yaradığını anlatır: editörde imleç bir kelimenin
        üzerine gelince çıkan Türkçe açıklamanın aynısı. (Eskiden yalnızca
        Python karşılığı veriliyordu; yeni başlayan biri bunu anlayamıyordu.)"""
        kelime = arg.strip()
        if not kelime:
            self.yaz("Kullanım: anlam <kelime>   (ör. anlam yazdır, anlam döngü)")
            return
        try:
            from .dictionary import TERS_SOZLUK
        except ImportError:
            from dictionary import TERS_SOZLUK
        cekirdek = self._cekirdek()
        aciklama = cekirdek.kelime_aciklamasi(kelime, "\n".join(self.kaynak))
        if aciklama.get("aciklama"):
            self.yaz(f"  {_R.VURGU}{_R.KALIN}{kelime}{_R.SON}: {aciklama['aciklama']}")
            return
        # Python kelimesi yazıldıysa ("print") TürKod karşılığı anlatılır.
        karsilik = TERS_SOZLUK.get(kelime)
        if isinstance(karsilik, str):
            ac = cekirdek.kelime_aciklamasi(karsilik, "").get("aciklama")
            self.yaz(f"  TürKod'da {_R.VURGU}{_R.KALIN}{karsilik}{_R.SON} yazılır."
                     + (f" {ac}" if ac else ""))
            return
        if kelime in self.ad_alani and kelime not in self._on_adlar:
            deger = self.ad_alani[kelime]
            tur = "fonksiyon" if callable(deger) else "değişken"
            self.yaz(f"  {_R.VURGU}{kelime}{_R.SON}: bu oturumda senin tanımladığın bir {tur}.")
            return
        import difflib
        tr_kelimeler = [t for t in TERS_SOZLUK.values() if isinstance(t, str)]
        yakin = difflib.get_close_matches(kelime, tr_kelimeler, 5, 0.7)
        self.yaz(f"{_R.SARI}'{kelime}' için açıklama bulunamadı.{_R.SON}"
                 + (f" Bunu mu demek istedin: {', '.join(yakin)}" if yakin else ""))

    def _cekirdek(self):
        if getattr(self, "_ide_cekirdek", None) is None:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    from .ide_core import IDECore
                except ImportError:
                    from ide_core import IDECore
                self._ide_cekirdek = IDECore()
        return self._ide_cekirdek

    def _k_cevir(self, arg):
        if not arg:
            self.yaz("Kullanım: çevir <TürKod kodu>   (ör. çevir yazdır(\"a\"))")
            return
        try:
            self.yaz(f"{_R.YESIL}{turkce_kodu_donustur(arg)}{_R.SON}")
        except Exception as e:  # noqa: BLE001
            self.yaz(f"{_R.KIRMIZI}[Çeviri hatası] {e}{_R.SON}")

    def _k_pycevir(self, arg):
        if not arg:
            self.yaz("Kullanım: pyçevir <Python kodu>   (ör. pyçevir print(len(x)))")
            return
        try:
            self.yaz(f"{_R.YESIL}{python_kodu_turkceye_cevir(arg)}{_R.SON}")
        except Exception as e:  # noqa: BLE001
            self.yaz(f"{_R.KIRMIZI}[Çeviri hatası] {e}{_R.SON}")

    def _dosya_arg(self, arg, kullanim):
        try:
            parca = shlex.split(arg, posix=False)
        except ValueError:
            parca = arg.split()
        parca = [p.strip('"') for p in parca]
        if not parca:
            self.yaz(f"Kullanım: {kullanim}")
            return None, []
        yol = os.path.abspath(os.path.expanduser(parca[0]))
        if not os.path.isfile(yol) and os.path.isfile(yol + ".trpy"):
            yol += ".trpy"
        if not os.path.isfile(yol):
            self.yaz(f"{_R.KIRMIZI}Dosya bulunamadı: {parca[0]}{_R.SON}")
            return None, []
        return yol, parca[1:]

    def _k_calistir(self, arg):
        yol, ek = self._dosya_arg(arg, "çalıştır <dosya.trpy> [argümanlar]")
        if yol:
            kod = calistirici.konsolda_calistir(yol, ek, konsol_hazirla=False)
            if kod:
                self.yaz(f"{_R.SOLUK}[Program {kod} koduyla sonlandı]{_R.SON}")

    def _k_kontrol(self, arg):
        yol, _ = self._dosya_arg(arg, "kontrol <dosya.trpy>")
        if yol:
            calistirici.dosya_kontrol(yol, self.yaz)

    def _k_duzelt(self, arg):
        yol, ek = self._dosya_arg(arg, "düzelt <dosya.trpy> [--yaz]")
        if yol:
            calistirici.dosya_duzelt(yol, "--yaz" in ek, self.yaz)

    def _k_bicimlendir(self, arg):
        yol, ek = self._dosya_arg(arg, "biçimlendir <dosya.trpy> [--yaz]")
        if yol:
            calistirici.dosya_bicimlendir(yol, "--yaz" in ek, self.yaz)

    def _k_pythona(self, arg):
        yol, _ = self._dosya_arg(arg, "pythona <dosya.trpy>")
        if yol:
            calistirici.dosya_pythona(yol, self.yaz)

    @staticmethod
    def _parcala(arg):
        try:
            parca = shlex.split(arg, posix=False)
        except ValueError:
            parca = arg.split()
        return [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parca]

    def _k_exe_yap(self, arg):
        calistirici._exe_modulu().exe_komutu(self._parcala(arg), self.yaz)

    def _k_kaynak(self, arg):
        calistirici._exe_modulu().kaynak_komutu(self._parcala(arg), self.yaz)

    def _k_degiskenler(self, _arg):
        adlar = [a for a in self.ad_alani if a not in self._on_adlar and not a.startswith("_")]
        if not adlar:
            self.yaz(f"{_R.SOLUK}Henüz değişken yok.{_R.SON}")
            return
        for a in sorted(adlar):
            d = self.ad_alani[a]
            tur = type(d).__name__
            try:
                tur_tr = hata_turu_adi(tur) if tur.endswith("Error") else tur
            except Exception:  # noqa: BLE001
                tur_tr = tur
            tr_repr = self.ad_alani.get("_tr_repr")
            try:
                gosterim = tr_repr(d) if tr_repr else repr(d)
            except Exception:  # noqa: BLE001
                gosterim = repr(d)
            if len(gosterim) > 70:
                gosterim = gosterim[:67] + "..."
            self.yaz(f"  {_R.VURGU}{a}{_R.SON} ({tur_tr}) = {gosterim}")

    def _k_sifirla(self, _arg):
        self.sifirla()
        self.yaz(f"{_R.SOLUK}Oturum sıfırlandı.{_R.SON}")

    def _k_temizle(self, _arg):
        if getattr(self.cikis, "isatty", lambda: False)():
            os.system("cls" if os.name == "nt" else "clear")
        else:
            self.yaz("\n" * 3)

    def _k_editor(self, arg):
        dosyalar = [os.path.abspath(d.strip('"')) for d in arg.split()] if arg else []
        if not calistirici.editorde_ac(dosyalar):
            self.yaz(f"{_R.KIRMIZI}TürKod editörü bulunamadı.{_R.SON}")

    def _k_logo(self, arg):
        """TürKod logosu, terminali dolduracak büyüklükte ASCII karakterlerle.
        Gerçek konsolda ekran temizlenir ve logo kendi renkleriyle çizilir."""
        konsol = getattr(self.cikis, "isatty", lambda: False)()
        if konsol:
            os.system("cls" if os.name == "nt" else "clear")
        renkli = _R.ACIK and konsol and "renksiz" not in (arg or "").lower()
        for satir in logo_ascii.ciz(renkli=renkli):
            self.yaz(satir)

    def _k_surum(self, _arg):
        self.yaz(f"TürKod {calistirici.surum()}")

    def _k_cikis(self, _arg):
        return "cik"

    # -- döngü --------------------------------------------------------
    def _satir_oku(self, istem):
        self.cikis.write(istem)
        self.cikis.flush()
        bas = time.monotonic()
        satir = self.giris.readline()
        # İstem basılır basılmaz gelen satır önceden tamponda bekliyordu
        # (yapıştırma); kullanıcı bu kadar hızlı Enter'a basamaz.
        self._tampondan = time.monotonic() - bas < 0.05
        if not satir:
            raise EOFError
        return satir.rstrip("\r\n")

    def _bos_satirda_istem(self):
        """Boş satırdan sonra istem yeniden basılsın mı? Konsol Enter'ı yeni
        satır olarak yansıtır, istem alt satıra gelir. IDE terminali boş Enter'ı
        yansıtmaz, yapıştırmadaki fazladan satır sonu da yansımaz: istem aynı
        satırda ikinci kez basılıp "TürKod> TürKod>" görünüyordu."""
        konsol = getattr(self.giris, "isatty", lambda: False)()
        return konsol and not getattr(self, "_tampondan", False)

    def calis(self):
        self.baslik()
        istem = ISTEM
        while True:
            try:
                satir = self._satir_oku(istem)
            except EOFError:
                self.yaz("")
                return 0
            except KeyboardInterrupt:
                self.yaz("")
                istem = ISTEM
                continue
            istem = ISTEM
            if not satir.strip():
                if not self._bos_satirda_istem():
                    istem = ""
                continue
            # Dersten kopyalanan satırların baştaki boşluğu girinti hatası
            # vermesin (ilk satır her zaman en dış düzeydedir).
            satir = satir.lstrip()
            k = komut_mu(satir)
            if k is not None:
                try:
                    if self.komut(*k) == "cik":
                        return 0
                except KeyboardInterrupt:
                    self.yaz(f"\n{_R.SARI}[Durduruldu]{_R.SON}")
                except Exception as e:  # noqa: BLE001
                    self.yaz(f"{_R.KIRMIZI}[Komut hatası] {e}{_R.SON}")
                    traceback.print_exc(file=sys.stderr)
                continue
            # Çok satırlı blok: blok bitene (boş satır) kadar topla.
            satirlar = [satir]
            try:
                while not self.tamam_mi("\n".join(satirlar)) or (
                        len(satirlar) > 1 and satirlar[-1].strip()):
                    devam = self._satir_oku(DEVAM_ISTEMI)
                    if not devam.strip():
                        # IDE terminali boş Enter'ı yansıtmaz: bloğun çıktısı
                        # "...>" istemiyle aynı satıra yapışıyordu.
                        if not getattr(self.giris, "isatty", lambda: False)():
                            self.cikis.write("\n")
                        break
                    satirlar.append(devam)
            except EOFError:
                pass
            except KeyboardInterrupt:
                self.yaz("")
                continue
            self.kod_calistir("\n".join(satirlar))


def main(argv=()):
    try:
        calistirici._konsol_hazirla()
    except Exception:  # noqa: BLE001
        pass
    # IDE terminalinde çıktı bir boruya gider; tamponda beklemesin.
    for akim in (sys.stdout, sys.stderr):
        try:
            akim.reconfigure(line_buffering=True, write_through=True)
        except Exception:  # noqa: BLE001
            pass
    calistirici.konsol_kimligi_ayarla("TürKod Terminali")
    kabuk = TurKodKabugu()
    for komut in argv:
        # turkod kabuk "ders 1" -> açılışta komutu çalıştır
        k = komut_mu(komut)
        if k:
            kabuk.komut(*k)
    return kabuk.calis()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
