"""Akıllı Düzelt, Adı Değiştir, hayalet tamamlama ve yerel modeller için
bulunmuş hataların gerileme testleri.

Çalıştırma (proje kökünde):
    python -m unittest tests.test_duzeltme_hatalari
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

# Kullanıcının gerçek ayar dosyasına dokunulmasın (IDECore içe aktarılmadan önce).
_SANAL_EV = tempfile.mkdtemp(prefix="turkod_test_ev_")
import atexit  # noqa: E402
atexit.register(shutil.rmtree, _SANAL_EV, True)
for _degisken in ("USERPROFILE", "HOME", "LOCALAPPDATA"):
    os.environ[_degisken] = _SANAL_EV

from unittest import mock  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import akilli_duzeltici as ad_modulu  # noqa: E402
    from turkod_ide.ide_core import IDECore  # noqa: E402
from turkod_ide.kod_araclari import ad_degistir  # noqa: E402

_CORE = None


def core():
    global _CORE
    if _CORE is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _CORE = IDECore()
    return _CORE


def duzelt(kod):
    """Çalıştırma izni olmadan (yalnızca statik) Akıllı Düzelt."""
    with contextlib.redirect_stdout(io.StringIO()):
        return core().duzelt_kod(kod, calistirma_izni=False)


class AdDegistirHataTestleri(unittest.TestCase):
    def test_alt_satirdaki_anahtar_kelime_argumani_degismez(self):
        kod = "sep = '-'\nyazdır(1, 2,\n       sep=sep)\n"
        yeni, _ = ad_degistir(kod, "sep", "ayrac", 1, 1)
        self.assertEqual(yeni, "ayrac = '-'\nyazdır(1, 2,\n       sep=ayrac)\n")
        # Araya yorum girse de.
        kod = "sep = '-'\nyazdır(1,  # not\n       sep=sep)\n"
        yeni, _ = ad_degistir(kod, "sep", "ayrac")
        self.assertIn("sep=ayrac", yeni)

    def test_degisken_degisince_oznitelikler_degismez(self):
        kod = ("puan = 0\nsınıf A:\n    fonksiyon __init__(kendisi):\n"
               "        kendisi.puan = 0\no = A()\nyazdır(o.puan, puan)\n")
        yeni, sayi = ad_degistir(kod, "puan", "skor", 1, 1)
        self.assertEqual(sayi, 2)
        self.assertIn("kendisi.puan = 0", yeni)
        self.assertIn("yazdır(o.puan, skor)", yeni)
        self.assertTrue(yeni.startswith("skor = 0"))

    def test_oznitelik_degisince_hepsi_tutarli_degisir(self):
        kod = ("puan = 0\nsınıf A:\n    fonksiyon __init__(kendisi):\n"
               "        kendisi.puan = 0\no = A()\nyazdır(o.puan, puan)\n")
        # İmleç o.puan üzerinde (satır 6, sütun 11).
        yeni, sayi = ad_degistir(kod, "puan", "skor", 6, 11)
        self.assertEqual(sayi, 2)
        self.assertIn("kendisi.skor = 0", yeni)
        self.assertIn("yazdır(o.skor, puan)", yeni)
        self.assertTrue(yeni.startswith("puan = 0"))

    def test_metot_adi_degisince_cagrilari_da_degisir(self):
        kod = ("sınıf A:\n    fonksiyon hesapla(kendisi):\n        döndür 1\n"
               "    fonksiyon b(kendisi):\n        döndür kendisi.hesapla()\n"
               "yazdır(A().hesapla())\n")
        yeni, sayi = ad_degistir(kod, "hesapla", "topla", 2, 15)
        self.assertEqual(sayi, 3)
        self.assertNotIn("hesapla", yeni)

    def test_varsayilan_deger_dis_degiskenin_kullanimidir(self):
        kod = "x = 1\nfonksiyon f(a=x):\n    döndür a\n"
        yeni, _ = ad_degistir(kod, "x", "y", 1, 1)
        self.assertEqual(yeni, "y = 1\nfonksiyon f(a=y):\n    döndür a\n")
        kod = "x = 1\nfonksiyon f(x=x):\n    döndür x\nyazdır(x)\n"
        yeni, _ = ad_degistir(kod, "x", "y", 1, 1)
        self.assertEqual(yeni, "y = 1\nfonksiyon f(x=y):\n    döndür x\nyazdır(y)\n")
        # Parametre üzerinden değiştirmek varsayılan değere dokunmaz.
        yeni, _ = ad_degistir(kod, "x", "z", 2, 13)
        self.assertEqual(yeni, "x = 1\nfonksiyon f(z=x):\n    döndür z\nyazdır(x)\n")


class HayaletDengeTestleri(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide import hayalet_tamamlama
            from turkod_ide.converter import turkce_kodu_donustur
        self.h, self.cevir = hayalet_tamamlama, turkce_kodu_donustur

    def test_metin_icindeki_kesme_isareti_satiri_yarim_saydirmaz(self):
        h = self.h
        self.assertEqual(h.yeni_satir_eki('yazdır("Ali\'nin kedisi")', "", self.cevir), "\n")
        self.assertEqual(h.yeni_satir_eki("yazdır('dedi ki \"merhaba\"')", "", self.cevir), "\n")
        self.assertEqual(h.yeni_satir_eki('yazdır("(gülümse")', "", self.cevir), "\n")
        # Gerçekten yarım satırlar yine yarım sayılır.
        self.assertEqual(h.yeni_satir_eki('yazdır("Ali\'nin', "", self.cevir), "")
        self.assertEqual(h.yeni_satir_eki("yazdır((1, 2)", "", self.cevir), "")
        self.assertFalse(h._dengeli_mi('x = "a\\"'))
        self.assertTrue(h._dengeli_mi('x = "a\\"b"'))


class AkilliDuzeltYanlisDuzeltmeTestleri(unittest.TestCase):
    def test_yildizla_gelen_adlar_ve_anahtar_argumanlar_degismez(self):
        kod = ('den kaplumbağa içe_aktar *\nsetup(width=400, height=300)\n'
               'k = Turtle(shape="turtle", visible=Doğru)\n')
        r = duzelt(kod)
        self.assertIn("setup(width=400, height=300)", r["kod"])
        self.assertIn("visible=Doğru", r["kod"])

    def test_baska_yerde_sozdizimi_hatasi_varken_anahtar_arguman_degismez(self):
        r = duzelt('d = sözlük(soyisim="Kaya")\neğer d\n    yazdır(d)\n')
        self.assertIn('sözlük(soyisim="Kaya")', r["kod"])
        self.assertIn("eğer d:", r["kod"])

    def test_cozulemeyen_yildizda_temkinli_duzeltme(self):
        # Kullanıcının kendi modülü: adları öğrenilemez. Sözlük kelimesine
        # çok yakın olmayan ad ('setup') değişmez; bariz yazım hatası düzelir.
        r = duzelt("den benim_modulum içe_aktar *\nsetup(width=1)\nyazdr(1)\n")
        self.assertIn("setup(width=1)", r["kod"])
        self.assertIn("yazdır(1)", r["kod"])

    def test_sozdizimi_aramasi_kotulestirmez(self):
        kod = ('fonksiyon bol(a, b):\n    eğer b == 0:\n        yükselt DeğerHatası("x")\n'
               '    döndür a / b\nyazdır(bol(4, 2))\n')
        r = duzelt(kod)
        # 'yükselt' hata fırlatma girişimidir: doğrusu hata_fırlat.
        self.assertIn('        hata_fırlat DeğerHatası("x")', r["kod"])
        self.assertNotIn("yükseklik", r["kod"])

    def test_sozdizimi_aramasi_daha_kotu_sonucu_geri_alir(self):
        c = core()
        d = ad_modulu.AkilliDuzeltici(c, calistir=False)
        kod = 'eğer Doğru:\n    xq 1\n'
        bozuk = 'eğer Doğru:\nxq 1\n'  # blok boş kalır: daha kötü
        with mock.patch.object(d, "_sozdizimi_adaylari",
                               side_effect=lambda k, s, m: [(bozuk, ad_modulu.Bulgu(
                                   2, "girinti", "", 0.5, "sozdizimi"))] if k == kod else []):
            with mock.patch.object(d, "_derin_sozdizimi_arama", return_value=None):
                sonuc = d._sozdizimi_asamasi(kod)
        self.assertEqual(sonuc, kod)
        self.assertEqual(d.duzeltmeler, [])

    def test_yorumdaki_ozel_karakterlere_dokunulmaz(self):
        kod = "x = 3  # 3 × 4 – “tamam”  \nyazdır(x)\n"
        d = ad_modulu.AkilliDuzeltici(core(), calistir=False)
        self.assertEqual(d._garip_karakterler(kod), kod)
        self.assertEqual(d.duzeltmeler, [])
        # Koddaki akıllı tırnaklar yine düzelir.
        self.assertEqual(d._garip_karakterler("yazdır(“a”)  # “b”"), 'yazdır("a")  # “b”')

    def test_karisik_girinti_metin_icine_dokunmaz(self):
        kod = 'eğer Doğru:\n    s = """a\n\tb"""\n    yazdır(s)\n'
        d = ad_modulu.AkilliDuzeltici(core(), calistir=False)
        self.assertEqual(d._on_temizlik(kod), kod)
        self.assertFalse(any(b.kategori == "girinti" for b in d.duzeltmeler))
        # Gerçek karışık girinti yine düzelir; metnin içi korunur.
        kod2 = 'eğer Doğru:\n    s = """a\n\tb"""\n\tyazdır(s)\n'
        self.assertEqual(d._on_temizlik(kod2), 'eğer Doğru:\n    s = """a\n\tb"""\n    yazdır(s)\n')

    def test_f_metindeki_sozluk_anahtari_degismez(self):
        yeni = ad_modulu.ad_degistir_kod("yazdır(f\"{d['isim']} {isim}\")", "isim", "ad")
        self.assertEqual(yeni, "yazdır(f\"{d['isim']} {ad}\")")
        yeni = ad_modulu.ad_degistir("yazdır(f'{d[\"isim\"]} {isim}')", "isim", "ad")
        self.assertEqual(yeni, "yazdır(f'{d[\"isim\"]} {ad}')")


class AkilliDuzeltAiGecmisTestleri(unittest.TestCase):
    def test_ai_asamasi_panel_gecmisine_dokunmaz(self):
        c = core()
        d = ad_modulu.AkilliDuzeltici(c, calistir=False)
        cagrilar = []

        def sahte_cagri(mesaj, **k):
            cagrilar.append(k)
            # Kullanıcı bu sırada AI panelinde sohbet ediyor.
            c.ai_mesaj_gecmisi.append({"role": "user", "content": "panel"})
            return "```türkod\nyazdır(1)\n```"

        eski_gecmis = list(getattr(c, "ai_mesaj_gecmisi", []))
        c.ai_mesaj_gecmisi = [{"role": "user", "content": "önceki"}]
        try:
            with mock.patch.object(c, "ai_hazir_mi", return_value=(True, ""), create=True), \
                    mock.patch.object(c, "_ai_api_cagri", side_effect=sahte_cagri):
                d._ai_asamasi("yazdır(1")
            self.assertEqual([m["content"] for m in c.ai_mesaj_gecmisi], ["önceki", "panel"])
            self.assertTrue(cagrilar)
            self.assertEqual(cagrilar[0].get("gecmis_listesi"), [])
            self.assertEqual(cagrilar[0].get("gecmis_adet"), 0)
        finally:
            c.ai_mesaj_gecmisi = eski_gecmis


class ArayuzSurecSizintiTestleri(unittest.TestCase):
    def test_taskkill_zaman_asiminda_surec_oldurulur_gizleyici_durur(self):
        d = ad_modulu.AkilliDuzeltici(core(), calistir=False)
        d.python_exe = sys.executable
        d.ARAYUZ_SURESI = 0.2
        d.zaman_asimi = 0.2
        gizleyiciler = []

        class SahteGizleyici:
            def __init__(self, pid):
                self.durduruldu = False
                gizleyiciler.append(self)

            def durdur(self):
                self.durduruldu = True

        gercek_run = ad_modulu.subprocess.run

        def sahte_run(args, *a, **k):
            if args and args[0] == "taskkill":
                raise ad_modulu.subprocess.TimeoutExpired(args, 10)
            return gercek_run(args, *a, **k)

        with mock.patch.object(ad_modulu, "_PencereGizleyici", SahteGizleyici), \
                mock.patch.object(ad_modulu.subprocess, "run", side_effect=sahte_run), \
                mock.patch.object(ad_modulu.subprocess.Popen, "kill",
                                  autospec=True, side_effect=ad_modulu.subprocess.Popen.kill) as kill:
            sonuc = d._arayuz_calistir("import time\ntime.sleep(30)\n")
        self.assertEqual(sonuc["durum"], "atlandi")
        self.assertTrue(gizleyiciler and gizleyiciler[0].durduruldu)
        self.assertTrue(kill.called)
        surec = kill.call_args[0][0]
        self.assertIsNotNone(surec.poll())


class _SahteYanit:
    """requests.get(..., stream=True) yerine: verilen baytları gönderir."""

    def __init__(self, veri, kod=200):
        self.veri, self.status_code = veri, kod

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.veri), chunk_size):
            yield self.veri[i:i + chunk_size]


class _EsZamanliThread:
    """threading.Thread yerine: hedefi hemen (aynı iş parçacığında) çalıştırır."""

    def __init__(self, target=None, args=(), kwargs=None, **_):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


class YerelModelHataTestleri(unittest.TestCase):
    def setUp(self):
        from turkod_ide import yerel_modeller
        self.ym = yerel_modeller
        self.dizin = tempfile.mkdtemp(prefix="turkod_model_")
        self.addCleanup(shutil.rmtree, self.dizin, True)
        self.ym._INDIRMELER.clear()
        self.addCleanup(self.ym._INDIRMELER.clear)

    def _indir(self, kimlik, veri, toplam=None):
        ym = self.ym
        kayit = {"durum": "indiriliyor", "yuzde": 0.0, "tamamlanan": 0, "toplam": 0,
                 "hata": "", "iptal": False, "asama": ""}
        ym._INDIRMELER[kimlik] = kayit
        with mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "_dosya_bilgisi", return_value=toplam or len(veri)), \
                mock.patch.object(ym, "kullanilabilir_gb", return_value=100.0), \
                mock.patch("requests.get", side_effect=lambda url, headers=None, **k: (
                    _SahteYanit(veri[int(headers["Range"][6:-1]):], 206)
                    if headers and "Range" in headers else _SahteYanit(veri))):
            ym._indir(kimlik, "", None)
        return kayit

    def test_motor_kurulumu_hata_verirse_durum_takili_kalmaz(self):
        ym = self.ym
        with mock.patch.object(ym, "donanim_bilgisi",
                               return_value={"hizlandirma": {"tur": "cpu", "paket": "cpu"}}), \
                mock.patch.object(ym, "sunucuyu_durdur"), \
                mock.patch.object(ym, "_pip_kur", side_effect=PermissionError("llama.dll kilitli")), \
                mock.patch.object(ym.threading, "Thread", _EsZamanliThread):
            ym._KURULUM["durum"] = "bos"
            self.assertTrue(ym.motor_kur("cpu")["ok"])
        self.assertEqual(ym._KURULUM["durum"], "hata")
        self.assertTrue(ym._KURULUM["hata"])
        # Sonraki deneme yeniden başlar ("zaten kuruluyor" denmez).
        with mock.patch.object(ym, "donanim_bilgisi",
                               return_value={"hizlandirma": {"tur": "cpu", "paket": "cpu"}}), \
                mock.patch.object(ym, "sunucuyu_durdur"), \
                mock.patch.object(ym, "_pip_kur", return_value=False), \
                mock.patch.object(ym.threading, "Thread", _EsZamanliThread):
            self.assertNotIn("zaten", ym.motor_kur("cpu"))

    def test_buyuk_part_dosyasi_silinip_bastan_indirilir(self):
        kimlik = "a/b/model.gguf"
        with open(os.path.join(self.dizin, "model.gguf.part"), "wb") as f:
            f.write(b"x" * 15)
        kayit = self._indir(kimlik, b"y" * 10)
        self.assertEqual(kayit["durum"], "tamam", kayit["hata"])
        with open(os.path.join(self.dizin, "model.gguf"), "rb") as f:
            self.assertEqual(f.read(), b"y" * 10)

    def test_baska_depodan_ayni_adli_model_ezilmez(self):
        ym = self.ym
        self.assertEqual(self._indir("a/b/model.gguf", b"1" * 10)["durum"], "tamam")
        with mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym.threading, "Thread", _EsZamanliThread), \
                mock.patch.object(ym, "_indir") as indir:
            r = ym.model_indir("c/d/model.gguf")
        self.assertFalse(r["ok"])
        self.assertIn("a/b", r["hata"])
        indir.assert_not_called()
        with open(os.path.join(self.dizin, "model.gguf"), "rb") as f:
            self.assertEqual(f.read(), b"1" * 10)

    def test_ayni_adli_dosya_ayni_anda_iki_depodan_indirilmez(self):
        ym = self.ym
        ym._INDIRMELER["a/b/model.gguf"] = {"durum": "indiriliyor"}
        with mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "_indir") as indir:
            r = ym.model_indir("c/d/model.gguf")
        self.assertFalse(r["ok"])
        indir.assert_not_called()

    def test_baska_deponun_yarim_dosyasi_devam_ettirilmez(self):
        kimlik = "a/b/model.gguf"
        # Önce a/b'den yarım kalmış indirme...
        kayit = {"durum": "indiriliyor", "yuzde": 0.0, "tamamlanan": 0, "toplam": 0,
                 "hata": "", "iptal": False, "asama": ""}
        self.ym._INDIRMELER[kimlik] = kayit
        with mock.patch.object(self.ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(self.ym, "_dosya_bilgisi", return_value=10), \
                mock.patch.object(self.ym, "kullanilabilir_gb", return_value=100.0), \
                mock.patch.object(self.ym, "_parcalari_indir",
                                  side_effect=RuntimeError("HTTP 500")):
            with open(os.path.join(self.dizin, "model.gguf.part"), "wb") as f:
                f.write(b"A" * 4)
            self.ym._indir(kimlik, "", None)
        # ...sonra c/d'den aynı adlı dosya: a/b'nin baytları kullanılmaz.
        kayit = self._indir("c/d/model.gguf", b"C" * 10)
        self.assertEqual(kayit["durum"], "tamam", kayit["hata"])
        with open(os.path.join(self.dizin, "model.gguf"), "rb") as f:
            self.assertEqual(f.read(), b"C" * 10)

    def test_model_klasoru_sabit_surucude_degilse_bos_alan_hesaplanir(self):
        ym = self.ym
        from collections import namedtuple
        Kullanim = namedtuple("Kullanim", "total used free")
        with mock.patch.object(ym, "_sabit_suruculer", return_value=[]), \
                mock.patch.object(ym, "_disk_turleri", return_value={}), \
                mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "yuklu_modeller", return_value=[]), \
                mock.patch.object(ym.shutil, "disk_usage",
                                  return_value=Kullanim(500 * 2**30, 400 * 2**30, 100 * 2**30)):
            dep = ym.depolama_analizi()
        self.assertGreater(dep["kullanilabilir_gb"], 80)
        ok, _, neden = ym.sigar_mi(1, donanim={"ram_toplam_gb": 64, "vram_gb": 0},
                                   depolama=dep)
        self.assertTrue(ok, neden)

    def test_sunucu_baslarken_ikinci_cagiran_hazir_olmasini_bekler(self):
        import threading
        ym = self.ym
        hazir = threading.Event()

        class SahteSurec:
            pid = 1

            def poll(self):
                return None

        sonuclar = {}

        def cagir(ad):
            try:
                sonuclar[ad] = ym.sunucu_url()
            except Exception as e:  # noqa: BLE001
                sonuclar[ad] = e

        with mock.patch.object(ym, "etkin_motor", return_value="cpu"), \
                mock.patch.object(ym, "donanim_bilgisi", return_value={"ram_toplam_gb": 16}), \
                mock.patch.object(ym, "_bos_port", return_value=5555), \
                mock.patch.object(ym, "_veri_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "_model_klasorleri", return_value=[self.dizin]), \
                mock.patch.object(ym.subprocess, "Popen", return_value=SahteSurec()), \
                mock.patch.object(ym, "_saglikli", side_effect=lambda port: hazir.is_set()):
            try:
                a = threading.Thread(target=cagir, args=("a",))
                a.start()
                time.sleep(0.3)
                b = threading.Thread(target=cagir, args=("b",))
                b.start()
                time.sleep(0.5)
                self.assertNotIn("b", sonuclar)  # hazır olmadan adres verilmez
                hazir.set()
                a.join(5)
                b.join(5)
            finally:
                with ym._SUNUCU_KILIDI:
                    ym._SUNUCU.update({"surec": None, "port": None, "tur": None})
        self.assertEqual(sonuclar.get("a"), "http://127.0.0.1:5555/v1")
        self.assertEqual(sonuclar.get("b"), "http://127.0.0.1:5555/v1")


def _gguf_yaz(yol, kv, surum=3):
    """Küçük bir GGUF başlığı yazar. kv: [(anahtar, tür, değer)]."""
    import struct

    def metin(s):
        b = s.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    govde = b""
    for anahtar, tur, deger in kv:
        govde += metin(anahtar) + struct.pack("<I", tur)
        if tur == 8:
            govde += metin(deger)
        elif tur == 4:
            govde += struct.pack("<I", deger)
        elif tur == 10:
            govde += struct.pack("<Q", deger)
        elif tur == 9:  # metin dizisi
            govde += struct.pack("<IQ", 8, len(deger)) + b"".join(metin(x) for x in deger)
    with open(yol, "wb") as f:
        f.write(b"GGUF" + struct.pack("<IQQ", surum, 0, len(kv)) + govde)


class YerelBaglamTestleri(unittest.TestCase):
    def setUp(self):
        from turkod_ide import yerel_modeller, yerel_sunucu
        self.ym, self.ys = yerel_modeller, yerel_sunucu
        self.dizin = tempfile.mkdtemp(prefix="turkod_gguf_")
        self.addCleanup(shutil.rmtree, self.dizin, True)

    def _model(self, ad, baglam, tur=4):
        yol = os.path.join(self.dizin, ad)
        kv = [("general.architecture", 8, "qwen2"),
              ("tokenizer.ggml.tokens", 9, ["a", "bb", "ccc"] * 50)]
        if baglam:
            kv.insert(1, ("qwen2.context_length", tur, baglam))
        _gguf_yaz(yol, kv)
        return yol

    def test_gguf_basligindan_baglam_okunur(self):
        self.assertEqual(self.ys.gguf_baglam(self._model("a.gguf", 32768)), 32768)
        self.assertEqual(self.ys.gguf_baglam(self._model("b.gguf", 4096, tur=10)), 4096)
        self.assertIsNone(self.ys.gguf_baglam(self._model("c.gguf", 0)))
        bozuk = os.path.join(self.dizin, "d.gguf")
        with open(bozuk, "wb") as f:
            f.write(b"GGUF\x03\x00\x00\x00\xff")
        self.assertIsNone(self.ys.gguf_baglam(bozuk))
        self.assertIsNone(self.ys.gguf_baglam(os.path.join(self.dizin, "yok.gguf")))

    def test_yuklu_modeller_baglam_ve_kodi_uygunlugu(self):
        self._model("buyuk.gguf", 32768)
        self._model("kucuk.gguf", 4096)
        self._model("bilinmeyen.gguf", 0)
        with mock.patch.object(self.ym, "_model_klasorleri", return_value=[self.dizin]):
            m = {x["ad"]: x for x in self.ym.yuklu_modeller()}
        self.assertEqual((m["buyuk.gguf"]["baglam"], m["buyuk.gguf"]["kodi_uygun"]), (32768, True))
        self.assertEqual((m["kucuk.gguf"]["baglam"], m["kucuk.gguf"]["kodi_uygun"]), (4096, False))
        self.assertIsNone(m["bilinmeyen.gguf"]["kodi_uygun"])
        # Bağlam bilgi dosyasına yazılır (her açılışta yeniden okunmaz).
        import json
        with open(os.path.join(self.dizin, "buyuk.gguf.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["baglam"], 32768)

    def test_oneri_kartlarinda_kodi_uygunlugu(self):
        dep = {"kullanilabilir_gb": 100.0, "suruculer": []}
        d = {"ram_toplam_gb": 32, "vram_gb": 0}
        f = lambda b: self.ym._degerlendir(  # noqa: E731
            {"parametre_b": 1.5, "boyut_gb": 1.0, "baglam": b}, d, dep)["kodi_uygun"]
        self.assertTrue(f(32768))
        self.assertFalse(f(4096))
        self.assertIsNone(f(0))

    def test_sunucu_baglami_bellege_ve_modele_gore(self):
        self.assertEqual(self.ym.baglam_siniri(32), 16384)
        self.assertEqual(self.ym.baglam_siniri(8), 12288)
        self.assertEqual(self.ym.baglam_siniri(4), 8192)
        import argparse
        self.ys.ARG = argparse.Namespace(baglam=12288)
        self.assertEqual(self.ys.model_baglami(self._model("e.gguf", 32768)), 12288)
        self.assertEqual(self.ys.model_baglami(self._model("f.gguf", 4096)), 4096)
        self.assertEqual(self.ys.model_baglami(self._model("g.gguf", 0)), 8192)
        self.assertEqual(self.ys._arglar(["--paket", "x", "--modeller", "y"]).baglam, 8192)

    def test_sunucu_baglam_sinirini_iletir(self):
        ym = self.ym

        class SahteSurec:
            def poll(self):
                return None

        with mock.patch.object(ym, "etkin_motor", return_value="cpu"), \
                mock.patch.object(ym, "donanim_bilgisi", return_value={"ram_toplam_gb": 16}), \
                mock.patch.object(ym, "_bos_port", return_value=5556), \
                mock.patch.object(ym, "_veri_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "model_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "_model_klasorleri", return_value=[self.dizin]), \
                mock.patch.object(ym.subprocess, "Popen", return_value=SahteSurec()) as popen:
            try:
                ym._sunucu_baslat()
            finally:
                with ym._SUNUCU_KILIDI:
                    ym._SUNUCU.update({"surec": None, "port": None, "tur": None})
        komut = popen.call_args[0][0]
        self.assertEqual(komut[komut.index("--baglam") + 1], "16384")


class CudaMotorTestleri(unittest.TestCase):
    def setUp(self):
        from turkod_ide import yerel_modeller, yerel_sunucu
        self.ym, self.ys = yerel_modeller, yerel_sunucu
        self.dizin = tempfile.mkdtemp(prefix="turkod_motor_")
        self.addCleanup(shutil.rmtree, self.dizin, True)
        self.ym._KURULUM["durum"] = "bos"

    def test_cuda_paketiyle_calisma_kitapliklari_da_kurulur(self):
        komut = self.ym._pip_komutu("py", "hedef", "cu124")
        self.assertIn("llama-cpp-python==0.3.4", komut)
        self.assertTrue(any(k.startswith("nvidia-cuda-runtime-cu12==12.4") for k in komut))
        self.assertTrue(any(k.startswith("nvidia-cublas-cu12==12.4") for k in komut))
        komut13 = self.ym._pip_komutu("py", "hedef", "cu130")
        self.assertTrue(any(k.startswith("nvidia-cublas") for k in komut13))
        self.assertFalse(any(k.startswith("nvidia") for k in self.ym._pip_komutu("py", "h", "cpu")))
        self.assertGreater(self.ym.MOTOR_BOYUTU_MB["cu124"], 600)

    def test_dll_klasorleri_bulunur(self):
        bin_dizini = os.path.join(self.dizin, "nvidia", "cublas", "bin")
        os.makedirs(bin_dizini)
        open(os.path.join(bin_dizini, "cublas64_12.dll"), "wb").close()
        cuda = os.path.join(self.dizin, "toolkit")
        os.makedirs(os.path.join(cuda, "bin"))
        with mock.patch.dict(os.environ, {"CUDA_PATH": cuda}):
            dizinler = self.ys.cuda_dll_dizinleri(self.dizin)
        self.assertIn(bin_dizini, dizinler)
        self.assertIn(os.path.join(cuda, "bin"), dizinler)
        self.assertIn("dll_dizinlerini_ekle", self.ym._DOGRULAMA_KODU)

    def _kur(self, cuda_calisir):
        ym = self.ym
        hiz = {"tur": "cuda", "paket": "cu124", "aciklama": ""}

        def dogrula(tur):
            if tur == "cuda" and not cuda_calisir:
                ym._motor_hatasi("FileNotFoundError: Could not find module 'llama.dll' "
                                 "(or one of its dependencies).")
                return None
            os.makedirs(ym.motor_dizini(tur), exist_ok=True)
            return {"surum": "0.3.4", "gpu": tur == "cuda"}

        with mock.patch.object(ym, "_veri_dizini", return_value=self.dizin), \
                mock.patch.object(ym, "donanim_bilgisi", return_value={"hizlandirma": hiz}), \
                mock.patch.object(ym, "sunucuyu_durdur"), \
                mock.patch.object(ym, "_pip_kur", return_value=True), \
                mock.patch.object(ym, "motoru_dogrula", side_effect=dogrula), \
                mock.patch.object(ym.threading, "Thread", _EsZamanliThread):
            ym.motor_kur()
            return ym._cuda_hatasi(), dict(ym._KURULUM)

    def test_cuda_basarisizligi_kaydedilir_ve_bildirilir(self):
        hata, kurulum = self._kur(cuda_calisir=False)
        self.assertEqual(kurulum["durum"], "tamam")
        self.assertEqual(kurulum["sonuc_tur"], "cpu")
        self.assertTrue(kurulum["cpuya_dustu"])
        self.assertIn("DLL", hata["neden"])
        self.assertTrue(hata["tarih"])
        # Başarılı CUDA kurulumu kaydı siler.
        hata, kurulum = self._kur(cuda_calisir=True)
        self.assertIsNone(hata)
        self.assertFalse(kurulum["cpuya_dustu"])


if __name__ == "__main__":
    unittest.main()
