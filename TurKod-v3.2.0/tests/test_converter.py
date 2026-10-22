"""TürKod -> Python çevirici testleri.

Çalıştırma (proje kökünde):
    python -m unittest discover -s tests
"""
import contextlib
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


if __name__ == "__main__":
    unittest.main()
