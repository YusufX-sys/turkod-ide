"""IDE arka ucu testleri: Türkçe hata mesajları, akıllı düzeltici, otomatik
tamamlama, tanımsız ad uyarıları, tanıma git, dosyalarda arama ve ayarlar.

Çalıştırma (proje kökünde):
    python -m unittest discover -s tests
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

# Testler kullanıcının gerçek ayar dosyasına (~/.turkod_ayarlar.json)
# dokunmasın ve gerçek API anahtarıyla yapay zekâ çağrısı yapılmasın diye ev
# klasörü geçici bir klasöre yönlendirilir (IDECore içe aktarılmadan önce).
_SANAL_EV = tempfile.mkdtemp(prefix="turkod_test_ev_")
import atexit  # noqa: E402
atexit.register(shutil.rmtree, _SANAL_EV, True)
for _degisken in ("USERPROFILE", "HOME", "LOCALAPPDATA"):
    os.environ[_degisken] = _SANAL_EV

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import settings as ayarlar_modulu
    from turkod_ide.ast_katmani import dogrula
    from turkod_ide.converter import turkce_kodu_donustur
    from turkod_ide.ide_core import IDECore
    from turkod_ide.runner import hata_aciklamasi, runner_kodu_uret

_CORE = None


def core():
    global _CORE
    if _CORE is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _CORE = IDECore()
    return _CORE


def calistir(turkce):
    """TürKod kodunu IDE'nin çalıştırıcısıyla çalıştırır; çıktıyı döndürür."""
    klasor = tempfile.mkdtemp(prefix="turkod_test_")
    try:
        kod_yolu = os.path.join(klasor, "program.py")
        runner_yolu = os.path.join(klasor, "runner.py")
        with open(kod_yolu, "w", encoding="utf-8") as f:
            f.write(turkce_kodu_donustur(turkce))
        with open(runner_yolu, "w", encoding="utf-8") as f:
            f.write(runner_kodu_uret(kod_yolu, kaynak_kod=turkce))
        r = subprocess.run([sys.executable, "-X", "utf8", runner_yolu],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=klasor)
        return r.stdout + r.stderr
    finally:
        shutil.rmtree(klasor, ignore_errors=True)


class HataMesajiTestleri(unittest.TestCase):
    def test_tanimsiz_ad_turkce_adla_gosterilir(self):
        cikti = calistir("sayi = 5\nyazdır(sayı)")
        self.assertIn("'sayı' adında", cikti)
        self.assertNotIn("number", cikti)
        self.assertIn("Bunu mu demek istediniz: 'sayi'", cikti)

    def test_metot_hatasi_tur_ve_oneri(self):
        cikti = calistir("l = [1]\nl.ekle(2)")
        self.assertIn("liste türündeki değerin 'ekle'", cikti)
        self.assertIn("'sona_ekle'", cikti)
        self.assertNotIn("'list' object", cikti)

    def test_karsilastirma_hatasi_cevrilir(self):
        cikti = calistir('yazdır("5" > 3)')
        self.assertIn("metin ile tamsayı arasında", cikti)
        self.assertNotIn("not supported", cikti)

    def test_sozluk_anahtar_hatasi_aciklanir(self):
        cikti = calistir('d = {"a": 1}\nyazdır(d["b"])')
        self.assertIn("sözlükte 'b' anahtarı yok", cikti)

    def test_tamsayi_donusum_hatasi(self):
        cikti = calistir('tamsayı("abc")')
        self.assertIn("'abc' değeri tamsayıya dönüştürülemiyor", cikti)
        self.assertNotIn("base 10", cikti)

    def test_parametre_eksik(self):
        cikti = calistir("fonksiyon f(a, b):\n    döndür a\nf(1)")
        self.assertIn("'f' fonksiyonuna 1 zorunlu değer verilmedi", cikti)

    def test_modul_adi_turkce(self):
        cikti = calistir("içe_aktar matematik\nyazdır(matematik.karekk(4))")
        self.assertIn("'matematik' modülünde", cikti)
        self.assertIn("'karekök'", cikti)

    def test_ingilizce_yazilan_ad_cevrilmez(self):
        # Kullanıcı 'number' adını kendisi yazdıysa mesajda da o görünür.
        cikti = calistir("number = 1\nyazdır(numbr)")
        self.assertIn("'numbr'", cikti)
        self.assertIn("'number'", cikti)

    def test_stderr_metni_cevrilir(self):
        self.assertEqual(
            hata_aciklamasi("NameError", "name 'number' is not defined"),
            "'sayı' adında bir değişken/fonksiyon tanımlı değil!")


class CiktiCevirisiTestleri(unittest.TestCase):
    """Program çıktısındaki hata adları, mesajlar ve kütüphane satırları."""

    def test_yazdirilan_hata_nesnesi_turkce(self):
        cikti = calistir("dene:\n    [1].kaldır(5)\nhata_yakala DeğerHatası olarak h:\n"
                         "    yazdır(h)\n")
        self.assertIn("silinmek istenen değer listede yok!", cikti)
        self.assertNotIn("x not in list", cikti)

    def test_iddia_hatasi_adi(self):
        cikti = calistir('iddia_et 1 == 2, "eşit değil"')
        self.assertIn("[HATA]: Doğrulama (iddia_et) Hatası", cikti)
        self.assertIn("eşit değil", cikti)

    def test_kutuphane_hata_turu_ve_mesaji(self):
        cikti = calistir('içe_aktar json\njson.json_yükle_metin("{bozuk")')
        self.assertIn("[HATA]: JNG Kod Çözme Hatası (json)", cikti)
        self.assertIn("çift tırnaklı anahtar adı bekleniyordu", cikti)

    def test_kullanicinin_hata_sinifi_degismez(self):
        cikti = calistir('sınıf BenimHatam(İstisna):\n    geç\n'
                         'hata_fırlat BenimHatam("is not defined kalsın")')
        self.assertIn("[HATA]: BenimHatam", cikti)
        self.assertIn("is not defined kalsın", cikti)

    def test_hata_turu_adi_nitelikli(self):
        from turkod_ide.runner import hata_turu_adi
        self.assertEqual(hata_turu_adi("ValueError"), "Geçersiz Değer Hatası")
        self.assertEqual(hata_turu_adi("selenium.common.exceptions.TimeoutException"),
                         "Zaman Aşımı Hatası (selenium)")
        self.assertEqual(hata_turu_adi("cv2.error"), "OpenCV Hatası")

    def test_kutuphane_satirlari(self):
        from turkod_ide.cikti_cevirici import metni_cevir
        self.assertEqual(
            metni_cevir("[\x1b[1;32mINFO\x1b[0m   ] [Logger      ] Record log in C:\\k.txt"),
            "[Bilgi] [Kayıt] Kayıt dosyası: C:\\k.txt")
        self.assertTrue(metni_cevir(
            "I0000 00:00:1793190822.794679    8644 port.cc:153] oneDNN custom operations "
            "are on. You may see slightly different numerical results").startswith(
                "Bilgi (TensorFlow): oneDNN hızlandırmaları açık"))
        self.assertIn("Resim okunamadı: 'a.png'", metni_cevir(
            "[ WARN:0@0.128] global loadsave.cpp:278 cv::findDecoder imread_('a.png'): "
            "can't open/read file: check file path/integrity"))
        self.assertEqual(metni_cevir("Traceback (most recent call last):"),
                         "Hata izi (en son çağrı en altta):")
        self.assertEqual(metni_cevir("ZeroDivisionError: division by zero"),
                         "Sıfıra Bölme Hatası: bir sayı 0'a bölünemez!")
        self.assertEqual(metni_cevir("selam dünya"), "selam dünya")


class SozdizimiIpucuTestleri(unittest.TestCase):
    def _mesaj(self, kod):
        sonuc = dogrula(kod)
        self.assertFalse(sonuc.basarili)
        return str(sonuc.hatalar[0])

    def test_durum_yerine_durumunda(self):
        self.assertIn("durumunda", self._mesaj(
            'k = "a"\neşleştir k:\n    durum "a":\n        geç'))

    def test_ayrik_degilse_eger(self):
        self.assertIn("değilse_eğer", self._mesaj(
            "x = 1\neğer x:\n    geç\ndeğilse eğer x:\n    geç"))


class DuzelticiTestleri(unittest.TestCase):
    def test_girdi_girdi_al_olur(self):
        with contextlib.redirect_stdout(io.StringIO()):
            sonuc = core().duzelt_kod('x = girdi("?")', calistirma_izni=True)
        self.assertIn("girdi_al", sonuc.get("kod", ""))
        self.assertNotIn("girdiler", sonuc.get("kod", ""))


class TamamlamaTestleri(unittest.TestCase):
    def _oneriler(self, kelime, kod="", once=""):
        return [o["kelime"] for o in
                core().tamamlama_onerileri(kelime, kod, once)["oneriler"]]

    def test_ozel_adlar_alt_cizgisiz_bulunur(self):
        # "başl" yazınca __başlat__ önerilir; eski başlat_özel önerilmez.
        oneriler = self._oneriler("başl")
        self.assertIn("__başlat__", oneriler)
        self.assertNotIn("başlat_özel", oneriler)

    def test_liste_metotlari(self):
        self.assertEqual(self._oneriler("so", "liste_ = [1]", "liste_.")[0], "sona_ekle")

    def test_metin_metotlari(self):
        self.assertIn("büyük_harf", self._oneriler("bü", "s = girdi_al()", "s."))

    def test_modul_uyeleri_ascii_tekrari_yok(self):
        oneriler = self._oneriler("ka", "içe_aktar matematik", "matematik.")
        self.assertIn("karekök", oneriler)
        self.assertNotIn("karekok", oneriler)

    def test_sinif_uyeleri(self):
        kod = ("sınıf Kedi:\n    fonksiyon __başlat__(kendisi):\n"
               "        kendisi.ad = 1\n    fonksiyon miyavla(kendisi):\n"
               "        geç\nk = Kedi()")
        self.assertEqual(sorted(self._oneriler("", kod, "k.")), ["ad", "miyavla"])

    def test_sik_kelime_once(self):
        self.assertEqual(self._oneriler("ya")[0], "yazdır")
        self.assertEqual(self._oneriler("gi")[0], "girdi_al")

    def test_sablon_yalnizca_satir_basinda(self):
        sonuc = core().tamamlama_onerileri("eğ", "", "    ")["oneriler"]
        self.assertTrue(any("sablon" in o for o in sonuc))
        sonuc = core().tamamlama_onerileri("eğ", "", "x = ")["oneriler"]
        self.assertFalse(any("sablon" in o for o in sonuc))


class TanimsizAdUyarisiTestleri(unittest.TestCase):
    def _uyarilar(self, kod):
        return [u["mesaj"] for u in core().syntax_kontrol(kod).get("uyarilar", [])]

    def test_yanlis_yazilan_degisken(self):
        self.assertEqual(self._uyarilar("sayi = 5\nyazdır(sayı)"),
                         ["Satır 2: 'sayı' tanımlı değil. Bunu mu demek istediniz: 'sayi'?"])

    def test_girdi_onerisi(self):
        self.assertIn("'girdi_al'", self._uyarilar('x = girdi("?")')[0])

    def test_gecerli_kodda_uyari_yok(self):
        self.assertEqual(self._uyarilar(
            "içe_aktar matematik\nfonksiyon f(a):\n    döndür a\nyazdır(f(matematik.pi))"), [])

    def test_yildizli_ice_aktarmada_atlanir(self):
        self.assertEqual(self._uyarilar("den ursina içe_aktar *\nyazdır(Entity)"), [])


class ProjeAraclariTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="turkod_proje_")
        os.makedirs(os.path.join(cls.klasor, ".gizli"))
        with open(os.path.join(cls.klasor, "yardimci.trpy"), "w", encoding="utf-8") as f:
            f.write('fonksiyon selam(ad):\n    yazdır("Selam", ad)\n')
        with open(os.path.join(cls.klasor, "ana.trpy"), "w", encoding="utf-8") as f:
            f.write('den yardimci içe_aktar selam\nsayaç = 0\nselam("Ali")\n')
        with open(os.path.join(cls.klasor, ".gizli", "x.trpy"), "w", encoding="utf-8") as f:
            f.write("selam\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.klasor, ignore_errors=True)

    def test_dosyalarda_ara_gizli_klasoru_atlar(self):
        r = core().dosyalarda_ara(self.klasor, "selam")
        dosyalar = {os.path.basename(s["yol"]) for s in r["sonuclar"]}
        self.assertEqual(dosyalar, {"ana.trpy", "yardimci.trpy"})

    def test_dosyalarda_ara_gecersiz_regex(self):
        self.assertFalse(core().dosyalarda_ara(self.klasor, "(", regex=True)["ok"])

    def test_tanim_ayni_dosyada(self):
        ana = os.path.join(self.klasor, "ana.trpy")
        with open(ana, encoding="utf-8") as f:
            kod = f.read()
        r = core().tanim_bul(kod, "sayaç", ana)
        self.assertEqual((r["satir"], r["yol"]), (2, None))

    def test_tanim_yerel_modulde(self):
        ana = os.path.join(self.klasor, "ana.trpy")
        with open(ana, encoding="utf-8") as f:
            kod = f.read()
        r = core().tanim_bul(kod, "selam", ana)
        self.assertEqual(os.path.basename(r["yol"]), "yardimci.trpy")
        self.assertEqual(r["satir"], 1)


class KodAraclariTestleri(unittest.TestCase):
    def test_bicimlendir_girinti_ve_bosluklar(self):
        kod = "eğer x>3 :\n  yazdır( x ,'a' )\n  eğer x==4:\n      yazdır(-x)\n\n\n\n\nson=Doğru"
        beklenen = ("eğer x > 3:\n    yazdır(x, 'a')\n    eğer x == 4:\n"
                    "        yazdır(-x)\n\n\nson = Doğru")
        self.assertEqual(core().kodu_bicimlendir(kod)["kod"], beklenen)

    def test_bicimlendir_ozel_durumlar(self):
        ornekler = {
            "fonksiyon f(a,b=2,*args,**kw):\n\tdöndür a+b": "fonksiyon f(a, b=2, *args, **kw):\n    döndür a + b",
            "yazdır(l[1:2],d['a'])": "yazdır(l[1:2], d['a'])",
            "f = isimsiz x: x*-1": "f = isimsiz x: x * -1",
            'yazdır(f"{x!r:>10} ve {y+1}")': 'yazdır(f"{x!r:>10} ve {y+1}")',
            "m = '''a  \n   b'''": "m = '''a  \n   b'''",
        }
        for kod, beklenen in ornekler.items():
            self.assertEqual(core().kodu_bicimlendir(kod)["kod"], beklenen, kod)

    def test_bicimlendir_ikinci_kez_degistirmez(self):
        kod = "sınıf A:\n  fonksiyon m(kendisi,x:tamsayı=3):\n   # yorum\n   döndür x\n"
        bir = core().kodu_bicimlendir(kod)["kod"]
        self.assertFalse(core().kodu_bicimlendir(bir)["degisti"])
        self.assertIn("x: tamsayı = 3", bir)
        self.assertIn("        # yorum\n        döndür x", bir)

    def test_bicimlendir_sozdizimi_hatasinda_dokunmaz(self):
        self.assertFalse(core().kodu_bicimlendir('yazdır("a"')["ok"])

    def test_ad_degistir(self):
        kod = ("sayac = 1\nfonksiyon f(sayac):\n    döndür sayac\n"
               "yazdır(f\"{sayac}\", 'sayac', x.sayac, kendisi.sayac)  # sayac\n")
        r = core().ad_degistir(kod, "sayac", "sayaç")
        # Düz değişken değişirken öznitelikler (x.sayac, kendisi.sayac)
        # değişmez; ikisi farklı şeylerdir.
        self.assertEqual(r["sayi"], 4)
        self.assertIn("'sayac'", r["kod"])
        self.assertIn("x.sayac", r["kod"])
        self.assertIn("kendisi.sayac", r["kod"])
        self.assertIn("# sayac", r["kod"])
        self.assertIn('f"{sayaç}"', r["kod"])

    def test_ad_degistir_anahtar_kelime_reddedilir(self):
        self.assertFalse(core().ad_degistir("x = 1", "x", "eğer")["ok"])

    def test_kelime_aciklamasi(self):
        kod = "fonksiyon topla(a, b):\n    döndür a + b\nsayılar = [1, 2]\n"
        self.assertEqual(core().kelime_aciklamasi("topla", kod)["baslik"],
                         "fonksiyon topla(a, b)")
        self.assertIn("liste", core().kelime_aciklamasi("sayılar", kod)["baslik"])
        r = core().kelime_aciklamasi("yazdır", kod)
        self.assertIn("print", r["baslik"])
        self.assertTrue(r["aciklama"])
        self.assertIsNone(core().kelime_aciklamasi("bilinmeyen_ad", kod)["baslik"])


class RiskFiltresiTestleri(unittest.TestCase):
    """Akıllı Düzeltme'nin izinsiz çalıştırmayacağı kodlar (izin listesi)."""

    def _riskli(self, py):
        return bool(IDECore._python_riskleri(py))

    def test_dolayli_riskler_yakalanir(self):
        for py in ('import importlib\nimportlib.import_module("os")',
                   'import io\nio.open("a", "w")',
                   'import builtins\nbuiltins.open("a", "w")',
                   'f = open\nf("a", "w")',
                   'import zipfile\nzipfile.ZipFile("a.zip").extractall()',
                   'getattr(__builtins__, "ex" + "ec")("print(1)")',
                   '__import__("os")',
                   'import tkinter\ntkinter.Tk()',
                   'x = ().__class__.__base__.__subclasses__()',
                   'open(*["a", "w"])'):
            self.assertTrue(self._riskli(py), py)

    def test_guvenli_kod_calistirilabilir(self):
        for py in ('import math, random\nprint(math.sqrt(4), random.random())',
                   'x = open("a.txt").read()',
                   'with open("a.txt", "r", encoding="utf-8") as f:\n    print(f.read())',
                   'print(getattr([], "append"))'):
            self.assertFalse(self._riskli(py), py)


class DurdurHazirlikTestleri(unittest.TestCase):
    def test_hazirlanirken_durdur_programi_baslatmaz(self):
        c = core()
        orijinal = c._python_kodu_hazirla
        sonuclar = {}

        def hazirla(*a, **k):
            # Çeviri sürerken kullanıcı Durdur'a bastı.
            sonuclar["durdur"] = c.kodu_durdur()
            return orijinal(*a, **k)

        c._python_kodu_hazirla = hazirla
        try:
            r = c.kodu_calistir("yazdır(1)")
        finally:
            del c._python_kodu_hazirla
        self.assertEqual(sonuclar["durdur"], {"ok": True, "iptal": True})
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("iptal"))
        self.assertIsNone(c._calistirma_process)
        self.assertEqual(c._hazirlananlar, {})


class DilTespitiTestleri(unittest.TestCase):
    def test_metindeki_ingilizce_kelimeler_sayilmaz(self):
        c = core()
        self.assertEqual(c._kod_dili_tespit(
            'yazdır("Press Enter to continue or wait for import")'), "turkod")
        self.assertEqual(c._kod_dili_tespit("x = 1  # if for while import\nyazdır(x)"), "turkod")
        self.assertEqual(c._kod_dili_tespit('print("eğer ise yazdır")'), "python")
        # Tokenize edilemeyen kodda da çökmez.
        self.assertEqual(c._kod_dili_tespit('yazdır("a"\neğer x:\n  y\n    z'), "turkod")


class AdDegistirKapsamTestleri(unittest.TestCase):
    def test_anahtar_kelime_argumani_degismez(self):
        r = core().ad_degistir("sep = 1\nyazdır(1, sep=sep)\n", "sep", "ayrac")
        self.assertEqual(r["kod"], "ayrac = 1\nyazdır(1, sep=ayrac)\n")

    def test_yerel_degisken_yalnizca_kendi_fonksiyonunda(self):
        kod = ("fonksiyon f():\n    x = 1\n    döndür x\n"
               "fonksiyon g():\n    x = 2\n    döndür x\nx = 3\nyazdır(x)\n")
        r = core().ad_degistir(kod, "x", "y", 2, 5)
        self.assertEqual(r["kod"], kod.replace("    x = 1\n    döndür x", "    y = 1\n    döndür y"))
        r = core().ad_degistir(kod, "x", "y", 7, 1)
        self.assertEqual(r["kod"], kod.replace("x = 3\nyazdır(x)", "y = 3\nyazdır(y)"))
        # Konum verilmezse eskisi gibi bütün dosya.
        self.assertEqual(core().ad_degistir(kod, "x", "y")["sayi"], 6)

    def test_kuresel_bildirimi_tum_dosya(self):
        kod = "sayac = 0\nfonksiyon art():\n    küresel sayac\n    sayac = sayac + 1\n"
        self.assertEqual(core().ad_degistir(kod, "sayac", "s", 4, 5)["sayi"], 4)


class DosyaKodlamaTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_kodlama_")

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _gidis_donus(self, ad, ham):
        yol = os.path.join(self.klasor, ad)
        with open(yol, "wb") as f:
            f.write(ham)
        r = core().dosya_oku(yol)
        self.assertTrue(r["ok"], r)
        k = core().dosya_kaydet(yol, r["icerik"])
        self.assertTrue(k["ok"], k)
        with open(yol, "rb") as f:
            return r, k, f.read()

    def test_cp1254_tanimsiz_baytlar_kayipsiz(self):
        ham = "yazdır('çğış')\r\n".encode("cp1254") + b"# \x81\x8d\x9e\r\n"
        r, k, yeni = self._gidis_donus("a.trpy", ham)
        self.assertEqual(r["kodlama"], "cp1254")
        self.assertNotIn("\ufffd", r["icerik"])
        self.assertEqual(yeni, ham)

    def test_bom_utf16_ve_lf_korunur(self):
        for ad, ham in (("bom.trpy", b"\xef\xbb\xbfx = 1\ny = 2\n"),
                        ("lf.trpy", "x = 'ç'\ny = 2\n".encode("utf-8")),
                        ("u16.trpy", b"\xff\xfe" + "x = 'ç'\r\ny = 2\r\n".encode("utf-16-le"))):
            _r, _k, yeni = self._gidis_donus(ad, ham)
            self.assertEqual(yeni, ham, ad)

    def test_kodlanamayan_icerik_utf8e_duser(self):
        yol = os.path.join(self.klasor, "b.trpy")
        with open(yol, "wb") as f:
            f.write("x = 'ş'\r\n".encode("cp1254") + b"\x81\r\n")
        core().dosya_oku(yol)
        k = core().dosya_kaydet(yol, "x = '😀'\n")
        self.assertEqual(k["kodlama"], "utf-8")
        self.assertIn("uyari", k)
        with open(yol, "rb") as f:
            self.assertEqual(f.read().decode("utf-8"), "x = '😀'\r\n")

    def test_tanima_git_cp1254_modul(self):
        with open(os.path.join(self.klasor, "yardimci.trpy"), "wb") as f:
            f.write("# şöğüç \x81\nfonksiyon selam():\n    geç\n".encode("cp1254", "ignore") + b"\x81\n")
        ana = os.path.join(self.klasor, "ana.trpy")
        r = core().tanim_bul("den yardimci içe_aktar selam\nselam()\n", "selam", ana)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["satir"], 2)


class CiktiAkisiTestleri(unittest.TestCase):
    def test_kullanici_ciktisi_cevrilmez_hata_izi_cevrilir(self):
        from turkod_ide.cikti_cevirici import SatirCevirici
        cikti = []
        c = SatirCevirici(cikti.append, bekleme=0, aralik=0)
        c.besle("ValueError: sayı negatif olamaz\n[INFO] Sunucu başladı\nKeyError\n"
                "Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n"
                "    1/0\nZeroDivisionError: division by zero\nKeyError\n")
        c.bitir()
        satirlar = "".join(cikti).splitlines()
        self.assertEqual(satirlar[:3], ["ValueError: sayı negatif olamaz",
                                        "[INFO] Sunucu başladı", "KeyError"])
        self.assertEqual(satirlar[6], "Sıfıra Bölme Hatası: bir sayı 0'a bölünemez!")
        self.assertEqual(satirlar[7], "KeyError")


class TerminalCdTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_cd_")
        os.makedirs(os.path.join(self.klasor, "alt klasör"))
        self.c = IDECore.__new__(IDECore)
        self.c.proje_dizini = self.klasor
        self.c._terminal_dizini = None

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    def test_cd_kalici_ve_dogrulanir(self):
        c = self.c
        self.assertEqual(c._terminal_cd('cd "alt klasör"')["dizin"],
                         os.path.join(self.klasor, "alt klasör"))
        self.assertEqual(c._terminal_cwd(), os.path.join(self.klasor, "alt klasör"))
        self.assertEqual(c._terminal_cd("cd..")["dizin"], self.klasor)
        self.assertEqual(c._terminal_cd("chdir alt klasör")["dizin"],
                         os.path.join(self.klasor, "alt klasör"))
        r = c._terminal_cd("cd /d olmayan")
        self.assertFalse(r["ok"])
        self.assertEqual(c._terminal_cwd(), os.path.join(self.klasor, "alt klasör"))
        self.assertIsNone(c._terminal_cd("cd alt && dir"))
        self.assertIsNone(c._terminal_cd("dir"))
        if sys.platform == "win32":
            surucu = os.path.splitdrive(self.klasor)[0]
            self.assertEqual(c._terminal_cd(surucu)["dizin"], surucu + os.sep)


class GirdiDogrulamaTestleri(unittest.TestCase):
    def test_ayar_kaydedilemezse_hata(self):
        c = core()
        eski = c.ayarlar.kaydet
        c.ayarlar.kaydet = lambda: False
        try:
            r = c.ayar_set("yazi_boyutu", 15)
        finally:
            del c.ayarlar.kaydet
        self.assertFalse(r["ok"])
        self.assertIn("kaydedilemedi", r["hata"])
        self.assertIs(c.ayarlar.kaydet.__func__, eski.__func__)

    def test_oturum_turleri_dogrulanir(self):
        c = core()
        self.assertFalse(c.oturum_kaydet("C:/a.trpy", 0)["ok"])
        self.assertFalse(c.oturum_kaydet(["a.trpy"], "1")["ok"])
        self.assertTrue(c.oturum_kaydet(["a.trpy", {"isim": "Yeni", "icerik": ""}], 1)["ok"])
        self.assertEqual(c.oturum_oku()["son_oturum_aktif"], 1)
        # Bozuk kayıt okunurken ayıklanır.
        c.ayarlar.ayarlar["son_oturum"] = "bozuk"
        c.ayarlar.ayarlar["son_oturum_aktif"] = "x"
        r = c.oturum_oku()
        self.assertEqual((r["son_oturum"], r["son_oturum_aktif"]), ([], 0))

    def test_debug_listeleri_metin_kabul_etmez(self):
        c = core()
        self.assertFalse(c.debug_breakpoint_ayarla("12")["ok"])
        self.assertFalse(c.debug_izle("abc")["ok"])
        self.assertEqual(c.debug_breakpoint_ayarla(["12", 3])["breakpoints"], [3, 12])
        self.assertEqual(c.debug_izle(["x"])["izlenenler"], ["x"])
        c.debug_breakpoint_ayarla([])
        c.debug_izle([])


class DebugYerelModulTestleri(unittest.TestCase):
    def test_yerel_modulun_icine_girilir_ve_file_trpy(self):
        import queue
        klasor = tempfile.mkdtemp(prefix="turkod_dbg_")
        try:
            with open(os.path.join(klasor, "yardimci.trpy"), "w", encoding="utf-8") as f:
                f.write("fonksiyon iki_kat(x):\n    y = x * 2\n    döndür y\n")
            ana = os.path.join(klasor, "ana.trpy")
            kod = "içe_aktar yardimci\nyazdır(__file__)\nz = yardimci.iki_kat(3)\nyazdır(z)\n"
            olaylar, cikti = queue.Queue(), []
            c = core()
            r = c.debug_baslat(kod, [3], False, cikti.append, None,
                               lambda ad, veri: olaylar.put((ad, veri)), ana)
            self.assertTrue(r["ok"], r)

            def durus():
                while True:
                    ad, veri = olaylar.get(timeout=30)
                    if ad == "debug_durdu":
                        return veri
                    if ad == "debug_bitti":
                        self.fail("program durmadan bitti")

            self.assertEqual(durus()["satir"], 3)
            c.debug_icine()
            d = durus()
            self.assertEqual((d.get("modul"), d["satir"]), ("yardimci.trpy", 2))
            self.assertEqual(os.path.normcase(d.get("dosya")),
                             os.path.normcase(os.path.join(klasor, "yardimci.trpy")))
            c.breakpoints = set()
            c.debug_breakpoint_ayarla([])
            c.debug_devam()
            while True:
                ad, _veri = olaylar.get(timeout=30)
                if ad == "debug_bitti":
                    break
            metin = "".join(cikti)
            self.assertIn(ana, metin)
            self.assertNotIn("turkod_program.py", metin)
        finally:
            c.debug_durdur()
            shutil.rmtree(klasor, ignore_errors=True)


@unittest.skipUnless(sys.platform == "win32", "DPAPI yalnızca Windows'ta")
class AyarSifrelemeTestleri(unittest.TestCase):
    def test_api_anahtari_diskte_sifreli(self):
        klasor = tempfile.mkdtemp(prefix="turkod_ayar_")
        eski = {k: os.environ.get(k) for k in ("USERPROFILE", "HOME")}
        os.environ["USERPROFILE"] = os.environ["HOME"] = klasor
        try:
            a = ayarlar_modulu.AyarlarYoneticisi()
            a.set("ai_api_key", "sk-gizli-123")
            with open(a.dosya_yolu, encoding="utf-8") as f:
                disk = json.load(f)
            self.assertTrue(disk["ai_api_key"].startswith("dpapi:"))
            self.assertNotIn("sk-gizli-123", json.dumps(disk))
            self.assertEqual(ayarlar_modulu.AyarlarYoneticisi().get("ai_api_key"),
                             "sk-gizli-123")
        finally:
            for k, v in eski.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            shutil.rmtree(klasor, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
