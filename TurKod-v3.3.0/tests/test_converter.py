"""TürKod -> Python çevirici testleri.

Çalıştırma (proje kökünde):
    python -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide.converter import (python_kodu_turkceye_cevir,
                                      turkce_kodu_donustur,
                                      yerel_modulleri_hazirla)


def cevir(kod):
    return turkce_kodu_donustur(kod)


class TemelCeviriTestleri(unittest.TestCase):
    def test_yazdir(self):
        self.assertEqual(cevir("yazdır('merhaba')"), "print('merhaba')")

    def test_metin_icerigi_cevrilmez(self):
        self.assertEqual(cevir("yazdır('yazdır eğer ise')"), "print('yazdır eğer ise')")

    def test_yorum_cevrilmez(self):
        self.assertEqual(cevir("x = 1  # eğer ise yazdır"), "x = 1  # eğer ise yazdır")

    def test_satir_sayisi_korunur(self):
        kod = "x = 1\neğer x > 0 ise:\n    yazdır(x)\ndeğilse:\n    geç\n"
        self.assertEqual(cevir(kod).count("\n"), kod.count("\n"))

    def test_icin_aralik(self):
        self.assertEqual(cevir("için i aralık(uzunluk(a)):\n    geç"),
                         "for i in range(len(a)):\n    pass")

    def test_icinde(self):
        self.assertEqual(cevir("için x içinde liste_1:\n    geç"),
                         "for x in liste_1:\n    pass")


class IseKosuluTestleri(unittest.TestCase):
    """'ise' koşul sonu ve karşılaştırma biçimleri."""

    def test_karsilastirma_ise(self):
        # Eskiden "if x > 3 ==:" üretiyordu.
        self.assertEqual(cevir("eğer x > 3 ise:\n    geç"), "if x > 3:\n    pass")

    def test_indeks_ise(self):
        kod = "liste = [1]\neğer liste[0] ise:\n    geç"
        self.assertEqual(cevir(kod), "liste = [1]\nif liste[0]:\n    pass")

    def test_tek_ad_ise_dogruluk(self):
        # "A ise:" -> "A:" (eskiden "A == True:" — boş olmayan liste yanlış sayılıyordu)
        self.assertEqual(cevir("hazır = 1\neğer hazır ise:\n    geç"),
                         "hazır = 1\nif hazır:\n    pass")

    def test_iki_ad_ise_esitlik(self):
        self.assertEqual(cevir("yaş = 3\neğer yaş 18 ise:\n    geç"),
                         "yaş = 3\nif yaş == 18:\n    pass")

    def test_cagri_deger_ise(self):
        self.assertEqual(cevir("eğer uzunluk(a) 3 ise:\n    geç"),
                         "if len(a) == 3:\n    pass")

    def test_degil_ise(self):
        self.assertEqual(cevir("eğer değil a ise:\n    geç"), "if not a:\n    pass")

    def test_ve_ise(self):
        self.assertEqual(cevir("eğer a ve b ise:\n    geç"), "if a and b:\n    pass")

    def test_dongu_ise(self):
        self.assertEqual(cevir("döngü x < 3 ise:\n    geç"), "while x < 3:\n    pass")

    def test_ara_ek_ise(self):
        self.assertEqual(cevir("a = b ise c"), "a = b == c")

    def test_nitelik_ise_dokunulmaz(self):
        self.assertEqual(cevir("x = obj.ise"), "x = obj.ise")


class UretecTestleri(unittest.TestCase):
    def test_ic_ice_koseli_parantez(self):
        self.assertEqual(cevir("t = [x[0] için x içinde m]"), "t = [x[0] for x in m]")

    def test_kosullu_uretec(self):
        self.assertEqual(cevir("t = [x için x içinde aralık(10) eğer x > 1]"),
                         "t = [x for x in range(10) if x > 1]")


class KullaniciAdlariTestleri(unittest.TestCase):
    def test_kullanici_metodu_korunur(self):
        kod = "sınıf A:\n  fonksiyon yazdır(kendi):\n    geç\nA().yazdır()"
        self.assertTrue(cevir(kod).endswith("A().yazdır()"))

    def test_sozluk_kelimesi_degisken(self):
        self.assertEqual(cevir("liste = [1]\nyazdır(liste)"), "liste = [1]\nprint(liste)")


class TersCeviriTestleri(unittest.TestCase):
    def test_print(self):
        self.assertEqual(python_kodu_turkceye_cevir("print(len(a))"), "yazdır(uzunluk(a))")


class ModulTablosuTestleri(unittest.TestCase):
    """modul_sozlugu.py maddeleri ve "den X içe_aktar Y" biçimi."""

    def test_modul_noktali_ad(self):
        self.assertEqual(cevir("içe_aktar işletim_sistemi\nx = işletim_sistemi.süreç_kimliği_al()"),
                         "import os\nx = os.getpid()")

    def test_alt_modul(self):
        self.assertEqual(cevir("içe_aktar torch\nk = torch.sinir_ağı.Doğrusal(3, 2)"),
                         "import torch\nk = torch.nn.Linear(3, 2)")

    def test_modul_sonucu_duz_sozlukten_korunur(self):
        # "minimum" düz sözlükte min'dir; eskiden numpy.minimum -> numpy.min oluyordu.
        self.assertEqual(cevir("içe_aktar numpy\nx = numpy.eleman_en_küçük(a, b)"),
                         "import numpy\nx = numpy.minimum(a, b)")

    def test_alt_modul_ice_aktar(self):
        # Eskiden "import scipy.statistics" üretiyordu.
        self.assertEqual(cevir("içe_aktar bilimsel_hesaplama.istatistik"), "import scipy.stats")

    def test_yeni_kutuphaneler(self):
        self.assertEqual(cevir("içe_aktar cv2\ngri = cv2.renk_dönüştür(r, cv2.RENK_MYKden_GRİye)"),
                         "import cv2\ngri = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY)")
        self.assertEqual(cevir("içe_aktar görüntü_işleme\nx = görüntü_işleme.eşikle(a, 1, 2, görüntü_işleme.EŞİK_İKİLİ)"),
                         "import cv2\nx = cv2.threshold(a, 1, 2, cv2.THRESH_BINARY)")
        self.assertEqual(cevir("içe_aktar zaman\nt = zaman.performans_sayacı()"),
                         "import time\nt = time.perf_counter()")

    def test_takma_adli_modul(self):
        self.assertEqual(cevir("içe_aktar tensorflow_kütüphanesi olarak tf\nx = tf.sabit_değer(3)"),
                         "import tensorflow as tf\nx = tf.constant(3)")
        self.assertEqual(cevir("içe_aktar bilimsel_hesaplama.istatistik olarak st\n"
                               "p = st.olağan_dağılım.cdf(0)"),
                         "import scipy.stats as st\np = st.norm.cdf(0)")
        # Python biçimindeki içe aktarma ve tkinter'in özel içe aktarma kuralı
        self.assertEqual(cevir("import numpy as np\nx = np.eleman_en_küçük(a, b)"),
                         "import numpy as np\nx = np.minimum(a, b)")
        self.assertEqual(cevir("içe_aktar tkinter_arayüz olarak tk\nx = tk.ÇAPA"),
                         "import tkinter as tk\nx = tk.ANCHOR")

    def test_takma_adli_modul_geri_ceviri(self):
        kod = "import torch.nn as nn\nimport math as m\nk = nn.Linear(2, 3)\ny = m.exp(1)\n"
        tr = python_kodu_turkceye_cevir(kod)
        self.assertIn("k = nn.Doğrusal(2, 3)", tr)
        self.assertEqual(cevir(tr), kod)

    def test_den_ice_aktar(self):
        self.assertEqual(cevir("den numpy içe_aktar dizi, sıfırlar\nx = dizi([1]) + sıfırlar(2)"),
                         "from numpy import array, zeros\nx = array([1]) + zeros(2)")

    def test_den_ice_aktar_takma_ad_ve_alt_modul(self):
        self.assertEqual(cevir("den torch.sinir_ağı içe_aktar Doğrusal olarak D\nk = D(1, 2)"),
                         "from torch.nn import Linear as D\nk = D(1, 2)")

    def test_ice_aktar_den(self):
        self.assertEqual(cevir("içe_aktar küpkök den matematik\nyazdır(küpkök(27))"),
                         "from math import cbrt\nprint(cbrt(27))")

    def test_from_import_geri_ceviri(self):
        kod = "from torch.nn import Linear\nm = Linear(2, 3)\nf(Linear=1)\nx.Linear\n"
        tr = python_kodu_turkceye_cevir(kod)
        self.assertEqual(tr.split("\n")[:2],
                         ["den torch.sinir_ağı içe_aktar Doğrusal", "m = Doğrusal(2, 3)"])
        self.assertEqual(cevir(tr), kod)

    def test_case_anahtar_kelimesi(self):
        kod = "match x:\n    case 1:\n        pass\n"
        self.assertEqual(cevir(python_kodu_turkceye_cevir(kod)), kod)
        self.assertIn("durumunda 1:", python_kodu_turkceye_cevir(kod))


class YerelModulTestleri(unittest.TestCase):
    def setUp(self):
        self.kaynak = tempfile.mkdtemp()
        self.hedef = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.kaynak, ignore_errors=True)
        shutil.rmtree(self.hedef, ignore_errors=True)

    def _yaz(self, ad, icerik):
        with open(os.path.join(self.kaynak, ad), "w", encoding="utf-8") as f:
            f.write(icerik)

    def test_modul_niteligi_cevrilmez(self):
        self._yaz("yardimci.trpy", "fonksiyon uzunluk(x):\n    döndür x * 2\n")
        ana = "içe_aktar yardimci\nyazdır(yardimci.uzunluk(3), uzunluk([1]))\n"
        yerel, yazilan, hatalar = yerel_modulleri_hazirla(ana, self.kaynak, self.hedef)
        self.assertEqual(hatalar, [])
        self.assertEqual(len(yazilan), 1)
        py = turkce_kodu_donustur(ana, yerel_moduller=yerel)
        self.assertIn("yardimci.uzunluk(3)", py)
        self.assertIn("len([1])", py)

    def test_den_ice_aktar_ve_calistir(self):
        self._yaz("araclar.trpy",
                  "fonksiyon selam(ad):\n    döndür 'selam ' + ad\n")
        self._yaz("orta.trpy",
                  "den araclar içe_aktar selam\nfonksiyon iki():\n    döndür selam('iki')\n")
        ana = "içe_aktar orta\nden araclar içe_aktar selam\nyazdır(selam('bir'), orta.iki())\n"
        yerel, _y, hatalar = yerel_modulleri_hazirla(ana, self.kaynak, self.hedef)
        self.assertEqual(hatalar, [])
        self.assertEqual(set(yerel), {"orta", "araclar"})
        with open(os.path.join(self.hedef, "ana.py"), "w", encoding="utf-8") as f:
            f.write(turkce_kodu_donustur(ana, yerel_moduller=yerel))
        sonuc = subprocess.run([sys.executable, "ana.py"], cwd=self.hedef,
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(sonuc.returncode, 0, sonuc.stderr)
        self.assertEqual(sonuc.stdout.strip(), "selam bir selam iki")

    def test_olmayan_modul_yok_sayilir(self):
        yerel, yazilan, hatalar = yerel_modulleri_hazirla(
            "içe_aktar matematik\n", self.kaynak, self.hedef)
        self.assertEqual((yerel, yazilan, hatalar), ({}, [], []))


class HataDuzeltmeCeviriTestleri(unittest.TestCase):
    """2026-10-28 hata düzeltmeleri: içe aktarma, kullanıcı adları, geri çeviri."""

    def test_ice_aktarilan_modul_adi_atansa_da_cevrilir(self):
        py = cevir("içe_aktar zaman\nzaman = zaman.zaman()")
        self.assertEqual(py, "import time as zaman\nzaman = zaman.time()")
        self.assertIn("from time import", cevir("den zaman içe_aktar uyku\nzaman = 3"))

    def test_isimsiz_mors_ve_durumunda_adlari_korunur(self):
        self.assertEqual(cevir("f = isimsiz açık, aç: açık"), "f = lambda açık, aç: açık")
        self.assertEqual(cevir("eğer (açık := 3):\n    geç"), "if (açık := 3):\n    pass")
        py = cevir("eşleştir k:\n    durumunda [açık, *liste]:\n        yazdır(açık)\n")
        self.assertIn("case [açık, *liste]:", py)
        self.assertIn("print(açık)", py)

    def test_geri_ceviri_gidis_donus_ayni(self):
        import ast
        for kod in ("d = dict(width=1, height=2)",
                    "import os\nx = os.path.exists('a')",
                    "from pathlib import Path\nPath('a').exists()",
                    "d = dict(a=dict(width=1), b=len([1]))"):
            tr = python_kodu_turkceye_cevir(kod)
            self.assertNotIn("redis", tr)
            self.assertEqual(ast.dump(ast.parse(cevir(tr))), ast.dump(ast.parse(kod)), tr)


class YerelModulYorumTestleri(unittest.TestCase):
    def test_satir_sonu_yorumlu_ice_aktarma(self):
        kaynak, hedef = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            with open(os.path.join(kaynak, "yardimci.trpy"), "w", encoding="utf-8") as f:
                f.write("fonksiyon iki():\n    döndür 2\n")
            yerel, yazilan, hatalar = yerel_modulleri_hazirla(
                "içe_aktar yardimci  # yorum\nyazdır(yardimci.iki())\n", kaynak, hedef)
            self.assertEqual((set(yerel), len(yazilan), hatalar), ({"yardimci"}, 1, []))
        finally:
            shutil.rmtree(kaynak, ignore_errors=True)
            shutil.rmtree(hedef, ignore_errors=True)


class CalistiriciTestleri(unittest.TestCase):
    """runner şablonu: çıkış kodu ve hata çıktısı."""

    def _calistir(self, kod):
        from turkod_ide.runner import runner_kodu_uret
        dizin = tempfile.mkdtemp()
        try:
            kod_yolu = os.path.join(dizin, "turkce_kod_calisma.py")
            with open(kod_yolu, "w", encoding="utf-8") as f:
                f.write(turkce_kodu_donustur(kod))
            runner = os.path.join(dizin, "runner.py")
            with open(runner, "w", encoding="utf-8") as f:
                f.write(runner_kodu_uret(kod_yolu, ek_yollar=[dizin]))
            return subprocess.run([sys.executable, "-X", "utf8", runner], cwd=dizin,
                                  capture_output=True, text=True, encoding="utf-8",
                                  timeout=30)
        finally:
            shutil.rmtree(dizin, ignore_errors=True)

    def test_basarili_cikis_kodu(self):
        sonuc = self._calistir("yazdır(Doğru)")
        self.assertEqual(sonuc.returncode, 0)
        self.assertEqual(sonuc.stdout.strip(), "Doğru")

    def test_hata_cikis_kodu_ve_satir(self):
        sonuc = self._calistir("x = 1\ny = [1]\nyazdır(y[3])\n")
        self.assertEqual(sonuc.returncode, 1)
        self.assertIn("Satır Numarası: 3", sonuc.stdout)

    def test_yerlesik_metoda_yanlis_sayida_deger_turkce(self):
        # "datetime.ctime() takes no arguments (1 given)" İngilizce kalıyordu.
        sonuc = self._calistir(
            'içe_aktar tarih_saat\nsimdi = tarih_saat.şimdi()\n'
            'yazdır(simdi.metin_zaman("%Y-%m-%d"))\n')
        self.assertEqual(sonuc.returncode, 1)
        self.assertNotIn("takes no arguments", sonuc.stdout)
        self.assertIn("'metin_zaman' parantez içine değer almaz ama 1 değer verildi", sonuc.stdout)
        self.assertIn("tarih_biçimlendir", sonuc.stdout)
        sonuc = self._calistir("uzunluk([1], [2])\n")
        self.assertIn("'uzunluk' tam 1 değer alır ama 2 değer verildi", sonuc.stdout)

    def test_dosyaya_yazdirma_turkcelestirilmez(self):
        # yazdır(..., file=dosya) dosya içeriğini "Doğru/Hiçlik" ile bozmamalı.
        sonuc = self._calistir(
            'içe_aktar io\nb = io.StringIO()\nyazdır(Doğru, Hiçlik, file=b)\n'
            'yazdır(repr(b.getvalue()))\nyazdır(Doğru)\n')
        self.assertEqual(sonuc.stdout.split(), ["'True", "None\\n'", "Doğru"])

    def test_turkce_tkinter_degerleri(self):
        # arkaplan_rengi="açık gri", kabartma="çökük" eskiden Tk hatası veriyordu.
        sonuc = self._calistir(
            'içe_aktar tkinter_arayüz olarak tk\np = tk.pencere()\n'
            'e = tk.etiket(p, gid_metin="mavi", ön_renk_kısa="kırmızı", '
            'arkaplan_rengi="açık gri", kabartma="çökük", '
            'yazı_tipi=("Arial", 12, "kalın"))\n'
            'e.paketle(yan="sol", doldur="her_ikisi")\n'
            'yazdır(e.cget("text"), e.cget("fg"), e.cget("bg"), e.cget("relief"), '
            'e.cget("font"), e.pack_info()["side"], e.pack_info()["fill"])\n'
            'p.destroy()\n')
        self.assertEqual(sonuc.returncode, 0, sonuc.stdout)
        self.assertEqual(sonuc.stdout.split(),
                         ["mavi", "red", "lightgray", "sunken", "Arial", "12", "bold",
                          "left", "both"])

    def test_turkce_pillow_renkleri(self):
        sonuc = self._calistir(
            'den PIL içe_aktar Image\n'
            'yazdır(Image.new("RGB", (2, 2), "Açık Mavi").getpixel((0, 0)))\n')
        self.assertEqual(sonuc.stdout.strip(), "(173, 216, 230)")

    @unittest.skipUnless(importlib.util.find_spec("pygame"), "pygame kurulu değil")
    def test_turkce_pygame_renkleri(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        sonuc = self._calistir(
            'içe_aktar pygame\nekran = pygame.Surface((4, 4))\nekran.fill("mavi")\n'
            'pygame.draw.rect(ekran, "Açık Yeşil", (0, 0, 2, 2))\n'
            'yazdır(ekran.get_at((3, 3)), ekran.get_at((0, 0)), pygame.Color("kırmızı"))\n')
        # pygame açılışta kendi tanıtım satırlarını yazar; son satır bizim.
        self.assertEqual(sonuc.stdout.strip().splitlines()[-1],
                         "(0, 0, 255, 255) (144, 238, 144, 255) (255, 0, 0, 255)")

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib kurulu değil")
    def test_turkce_matplotlib_renkleri(self):
        os.environ.setdefault("MPLBACKEND", "Agg")
        sonuc = self._calistir(
            'den matplotlib içe_aktar colors\n'
            'yazdır(colors.to_hex("mavi"), colors.to_hex("Açık Yeşil"), colors.to_hex("kızıl"))\n')
        self.assertEqual(sonuc.stdout.strip(), "#0000ff #90ee90 #dc143c")


class DegerCevirisiTestleri(unittest.TestCase):
    """Tırnak içindeki seçenek değerlerinin (renk, şekil, hız...) çevirisi."""

    def test_python_kaplumbaga_degerleri_turkcelesir(self):
        tr = python_kodu_turkceye_cevir(
            'import turtle\nt = turtle.Turtle()\nt.color("blue", "Yellow")\n'
            't.shape("turtle")\nt.speed("fastest")\nturtle.bgcolor("light grey")\n'
            't.write("blue", align="center", font=("Arial", 16, "bold"))\n'
            'print("blue")\n')
        self.assertIn('renk("mavi", "sarı")', tr)
        self.assertIn('şekil("kaplumbağa")', tr)
        self.assertIn('hız("en_hızlı")', tr)
        self.assertIn('("açık_gri")', tr)
        self.assertIn('yaz("blue", align="orta", yazı_tipi=("Arial", 16, "kalın"))', tr)
        self.assertIn('yazdır("blue")', tr)

    def test_python_tkinter_degerleri_turkcelesir(self):
        tr = python_kodu_turkceye_cevir(
            'import tkinter as tk\nl = tk.Label(text="red", bg="white", relief="sunken")\n'
            'l.pack(side="left", fill="both")\n')
        self.assertIn('gid_metin="red"', tr)
        self.assertIn('arkaplan_rengi="beyaz"', tr)
        self.assertIn('kabartma="çökük"', tr)
        self.assertIn('"sol"', tr)
        self.assertIn('"her_ikisi"', tr)

    def test_ilgisiz_kutuphanede_degerlere_dokunulmaz(self):
        tr = python_kodu_turkceye_cevir('import plotly\nf(color="blue", shape="turtle")\n')
        self.assertIn('"blue"', tr)
        self.assertIn('"turtle"', tr)

    def test_turkce_degerler_calisma_aninda_taninir(self):
        from turkod_ide.deger_sozlugu import calisma_tablolari
        t = calisma_tablolari()
        self.assertEqual(t["renk"]["açık_mavi"], "lightblue")
        self.assertEqual(t["renk"]["acik_mavi"], "lightblue")
        self.assertEqual(t["sekil"]["kaplumbağa"], "turtle")
        self.assertEqual(t["hiz"]["en_hızlı"], "fastest")
        self.assertEqual(t["tk"]["relief"]["çökük"], "sunken")


if __name__ == "__main__":
    unittest.main()
