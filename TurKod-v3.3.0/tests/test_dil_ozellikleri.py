"""TürKod dil özellikleri: programlar gerçek çalıştırıcıyla (calistirici.Hazirlik)
çalıştırılır; aynı klasördeki dosyalar, yerel .trpy modülleri ve paketler dahil.

Çalıştırma (proje kökünde):
    python -m unittest tests.test_dil_ozellikleri
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
    from turkod_ide.calistirici import Hazirlik
    from turkod_ide.converter import python_kodu_turkceye_cevir, turkce_kodu_donustur


def calistir(ana, dosyalar=None, girdi=""):
    """TürKod programını (ana.trpy) yanındaki dosyalarla çalıştırır; (çıkış_kodu, çıktı)."""
    dizin = tempfile.mkdtemp()
    try:
        # newline="": satır sonları olduğu gibi yazılır (CRLF testi için).
        for ad, icerik in (dosyalar or {}).items():
            yol = os.path.join(dizin, ad)
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "w", encoding="utf-8", newline="") as f:
                f.write(icerik)
        yol = os.path.join(dizin, "ana.trpy")
        with open(yol, "w", encoding="utf-8", newline="") as f:
            f.write(ana)
        h = Hazirlik(yol)
        with contextlib.redirect_stdout(io.StringIO()):
            if not h.hazirla():
                return None, " | ".join(h.hatalar)
        try:
            sonuc = subprocess.run(h.komut, cwd=h.cwd, input=girdi, capture_output=True,
                                   text=True, encoding="utf-8", timeout=60)
        finally:
            h.temizle()
        return sonuc.returncode, sonuc.stdout + sonuc.stderr
    finally:
        shutil.rmtree(dizin, ignore_errors=True)


class DosyaVeModulTestleri(unittest.TestCase):
    def assertCikti(self, ana, beklenen, dosyalar=None, girdi=""):
        kod, cikti = calistir(ana, dosyalar, girdi)
        self.assertEqual((kod, cikti), (0, beklenen))

    def test_ayni_klasordeki_dosyayi_okuma_yazma(self):
        self.assertCikti(
            'ile aç("veri.txt", "r", kodlama="utf-8") olarak dosya:\n'
            '    için satır içinde dosya:\n'
            '        yazdır(satır.kırp().büyük_harf())\n'
            'ile aç("çıktı.txt", "w", kodlama="utf-8") olarak d:\n'
            '    yazdır("yazıldı", dosyaya=d)\n'
            'ile aç("çıktı.txt", kodlama="utf-8") olarak d:\n'
            '    yazdır(d.oku().kırp())\n',
            "ELMA\nARMUT\nyazıldı\n", {"veri.txt": "elma\narmut\n"})

    def test_program_klasoru_dosya_ozel_ile(self):
        self.assertCikti(
            'içe_aktar işletim_sistemi\n'
            'burası = işletim_sistemi.yol.dizin_adı(işletim_sistemi.yol.mutlak_yol(__dosya__))\n'
            'yol = işletim_sistemi.yol.birleştir(burası, "veri.txt")\n'
            'yazdır(işletim_sistemi.yol.var_mı(yol), işletim_sistemi.yol.temel_ad(yol))\n'
            'den yol_kütüphanesi içe_aktar Yol\n'
            'yazdır(Yol(yol).metni_oku(kodlama="utf-8").kırp(), Yol(yol).bir_dosya_mı())\n',
            "Doğru veri.txt\nmerhaba Doğru\n", {"veri.txt": "merhaba\n"})

    def test_yerel_modul_turkce_adli(self):
        self.assertCikti(
            'içe_aktar matematik_araçları\n'
            'den matematik_araçları içe_aktar kare, Hesap\n'
            'yazdır(matematik_araçları.küp(2), kare(5), Hesap(3).ikiye_katla())\n'
            'yazdır(matematik_araçları.uzunluk("abc"))\n',
            "8 25 6\n3\n",
            {"matematik_araçları.trpy":
             'fonksiyon kare(x):\n    döndür x * x\n'
             'fonksiyon küp(x):\n    döndür x ** 3\n'
             'fonksiyon uzunluk(m):\n    döndür 3\n'
             'sınıf Hesap:\n'
             '    fonksiyon __başlat__(kendisi, değer):\n        kendisi.değer = değer\n'
             '    fonksiyon ikiye_katla(kendisi):\n        döndür kendisi.değer * 2\n'
             'eğer __isim__ == "__main__":\n    yazdır("çalışmamalı")\n'})

    def test_alt_klasordeki_paket(self):
        # Eskiden yalnızca aynı klasördeki .trpy dosyaları bulunuyordu.
        self.assertCikti(
            'den paketim içe_aktar modul1\n'
            'den paketim.modul2 içe_aktar iki\n'
            'içe_aktar paketim.modul1\n'
            'içe_aktar araçlar.sayı_araçları olarak sa\n'
            'yazdır(modul1.bir(), iki(), paketim.modul1.bir(), sa.çift_mi(4), paketim.SÜRÜM)\n',
            "1 2 1 Doğru 3\n",
            {"paketim/__init__.trpy": "SÜRÜM = 3\n",
             "paketim/modul1.trpy": "fonksiyon bir():\n    döndür 1\n",
             "paketim/modul2.trpy": "den .modul1 içe_aktar bir\nfonksiyon iki():\n    döndür bir() + 1\n",
             "araçlar/sayı_araçları.trpy": "fonksiyon çift_mi(n):\n    döndür n % 2 == 0\n"})

    def test_crlf_dosyada_yerel_modul(self):
        # Windows satır sonlu (CRLF) ana dosyada "içe_aktar yardimci" eskiden
        # görülmüyor, modül çevrilmediği için bulunamıyordu.
        self.assertCikti(
            "içe_aktar yardimci\r\nyazdır(yardimci.topla(2, 3))\r\n", "5\n",
            {"yardimci.trpy": "fonksiyon topla(a, b):\r\n    döndür a + b\r\n"})

    def test_noktali_yerel_modul_yolu_cevrilmez(self):
        # "sayi" sözlükte number'dır; modül yolunda çevrilmemeli.
        self.assertCikti(
            "içe_aktar araclar.sayi olarak sa\nden araclar.sayi içe_aktar cift\n"
            "yazdır(sa.cift(4), cift(3))\n",
            "Doğru Yanlış\n",
            {"araclar/sayi.trpy": "fonksiyon cift(n):\n    döndür n % 2 == 0\n"})

    def test_girdi(self):
        self.assertCikti(
            'ad = girdi_al("Ad: ")\nyaş = tamsayı(girdi_al("Yaş: "))\n'
            'yazdır(f"{ad} {yaş + 1}")\n',
            "Ad: Yaş: Can 21\n", girdi="Can\n20\n")


class DilOzellikleriTestleri(unittest.TestCase):
    def assertCikti(self, ana, beklenen):
        kod, cikti = calistir(ana)
        self.assertEqual((kod, cikti), (0, beklenen))

    def test_ascii_yazimla_aralik_dongusu(self):
        # "icin i aralik(2):" eskiden "for i range(2)" (sözdizimi hatası) oluyordu.
        self.assertCikti(
            'icin i aralik(2):\n    yazdir("Ali" eger i degilse "-")\n'
            'dongu j aralik(1):\n    yazdir(j)\n',
            "-\nAli\n0\n")

    def test_kwargs_anahtarlari_cevrilmez(self):
        # bilgi(şehir=...) eskiden bilgi(city=...) oluyordu.
        self.assertCikti(
            'fonksiyon bilgi(**özellikler):\n    döndür sıralanmış(özellikler.anahtarlar())\n'
            'yazdır(bilgi(şehir="Bursa", renk="mavi", uzunluk=3))\n',
            "['renk', 'uzunluk', 'şehir']\n")

    def test_veri_sinifi_tip_ipuclu_alanlar(self):
        # "şehir: metin = ..." eskiden "şehir: text" (tkinter metin=) oluyordu;
        # "etiketler: liste" alanı da "labels" diye yeniden adlandırılıyordu.
        self.assertCikti(
            'den dataclasses içe_aktar dataclass\n'
            '@dataclass(sıralanabilir=Doğru)\n'
            'sınıf Öğrenci:\n    ad: metin\n    etiketler: liste\n    şehir: metin = "Ankara"\n'
            'yazdır(Öğrenci("Ece", []))\n',
            "Öğrenci(ad='Ece', etiketler=[], şehir='Ankara')\n")

    def test_ozellik_ayarlayici_ve_soyut_sinif(self):
        self.assertCikti(
            'den soyut_sınıflar içe_aktar SoyutTemelSınıf, soyut_metot\n'
            'sınıf Hesap(SoyutTemelSınıf):\n'
            '    @soyut_metot\n    fonksiyon faiz(kendisi):\n        geç\n'
            'sınıf Banka(Hesap):\n'
            '    fonksiyon __başlat__(kendisi):\n        kendisi._bakiye = 0\n'
            '    @özellik\n    fonksiyon bakiye(kendisi):\n        döndür kendisi._bakiye\n'
            '    @bakiye.ayarlayıcı\n    fonksiyon bakiye(kendisi, değer):\n'
            '        kendisi._bakiye = değer * 2\n'
            '    fonksiyon faiz(kendisi):\n        döndür 1\n'
            '    @sınıf_metodu\n    fonksiyon yeni(kendi_sınıfı):\n        döndür kendi_sınıfı()\n'
            'b = Banka.yeni()\nb.bakiye = 5\nyazdır(b.bakiye)\n'
            'dene:\n    Hesap()\nhata_yakala TürHatası:\n    yazdır("soyut")\n',
            "10\nsoyut\n")

    def test_ozel_islec_metotlari(self):
        self.assertCikti(
            'sınıf V:\n'
            '    fonksiyon __başlat__(kendisi, x):\n        kendisi.x = x\n'
            '    fonksiyon __topla__(kendisi, o):\n        döndür V(kendisi.x + o.x)\n'
            '    fonksiyon __eşit__(kendisi, o):\n        döndür kendisi.x == o.x\n'
            '    fonksiyon __küçük__(kendisi, o):\n        döndür kendisi.x < o.x\n'
            '    fonksiyon __temsil__(kendisi):\n        döndür f"V({kendisi.x})"\n'
            'yazdır(V(1) + V(2), V(1) == V(1), V(1) < V(0), sıralanmış([V(3), V(1)]))\n',
            "V(3) Doğru Yanlış [V(1), V(3)]\n")

    def test_koleksiyonlar_ve_tarih(self):
        self.assertCikti(
            'den koleksiyonlar içe_aktar Sayaç, çift_yönlü_kuyruk\n'
            'yazdır(Sayaç("abracadabra").en_sık_olanlar(1))\n'
            'k = çift_yönlü_kuyruk([1, 2])\nk.başa_ekle(0)\nyazdır(k.baştan_çıkar(), liste(k))\n'
            'den tarih_saat içe_aktar tarih_saat, zaman_farkı\n'
            't = tarih_saat.tarih_ayrıştır("05.06.2023", "%d.%m.%Y")\n'
            'yazdır(t.tarih(), zaman_farkı(günler=1).toplam_saniye())\n',
            "[('a', 5)]\n0 [1, 2]\n2023-06-05 86400.0\n")

    def test_vad_json_ve_desen(self):
        self.assertCikti(
            'içe_aktar vad, json, io\n'
            'tampon = io.StringIO()\nyazıcı = vad.vad_yazıcı(tampon)\n'
            'yazıcı.satır_yaz(["a", "b"])\nyazdır(tampon.getvalue().kırp())\n'
            'yazdır(json.jng_kaydet_metin({"ş": 1}, abdsk_sağla=Yanlış))\n'
            'içe_aktar desen\n'
            'yazdır(mantıksal(desen.eşleştir("ab", "AB", desen.BÜYÜK_KÜÇÜK_YOKSAY)))\n',
            'a,b\n{"ş": 1}\nDoğru\n')

    def test_yerlesik_arguman_adlari(self):
        self.assertCikti(
            'yazdır(yuvarla(3.14159, basamak=2), tamsayı("ff", taban=16),'
            ' "a b c".böl(en_fazla_bölme=1))\n',
            "3.14 255 ['a', 'b c']\n")

    def test_eslestir_ve_eszamansiz(self):
        self.assertCikti(
            'fonksiyon komut(k):\n'
            '    eşleştir k.böl():\n'
            '        durumunda ["git", yön]:\n            döndür yön\n'
            '        durumunda _:\n            döndür "?"\n'
            'yazdır(komut("git kuzey"), komut("uç"))\n'
            'içe_aktar asyncio\n'
            'eşzamansız fonksiyon iki_kat(n):\n'
            '    bekle asyncio.sleep(0)\n    döndür n * 2\n'
            'eşzamansız fonksiyon ana():\n'
            '    yazdır(bekle asyncio.gather(*(iki_kat(i) için i aralık(3))))\n'
            'asyncio.run(ana())\n',
            "kuzey ?\n[0, 2, 4]\n")


class GidisDonusTestleri(unittest.TestCase):
    """Python -> TürKod -> Python çevirisinde anlam değişmemeli."""

    def gidis_donus(self, py):
        return turkce_kodu_donustur(python_kodu_turkceye_cevir(py))

    def test_desen_degiskeni_re_modulunu_bozmaz(self):
        # "desen" (re'nin Türkçe adı) kullanıcı değişkeniyken re.IGNORECASE
        # eskiden "desen.BÜYÜK_KÜÇÜK_YOKSAY" olup değişkene gidiyordu.
        py = 'import re\ndesen = re.compile(r"^a", re.IGNORECASE)\n'
        self.assertIn("re.IGNORECASE", self.gidis_donus(py))

    def test_datetime_sinifi_ice_aktarilinca(self):
        py = 'from datetime import datetime\nt = datetime.strptime("1", "%d")\n'
        self.assertIn("datetime.strptime(", self.gidis_donus(py))
        self.assertNotIn("datetime.datetime", self.gidis_donus(py))

    def test_yeni_karsiliklar_turkcelesir(self):
        tr = python_kodu_turkceye_cevir(
            'from collections import Counter\nimport csv\n'
            'print(Counter("aab").most_common(1), file=f)\n'
            'class A:\n    @property\n    def x(self):\n        return 1\n'
            '    @x.setter\n    def x(self, v):\n        pass\n'
            '    def __eq__(self, o):\n        return True\n')
        for kelime in ("en_sık_olanlar", "dosyaya=", "içe_aktar vad", "@x.ayarlayıcı", "__eşit__"):
            self.assertIn(kelime, tr)

    def test_turkce_adli_sayac_icin_aralik(self):
        # Türkçe harfli sayaç adı da "için X aralık(...)" kalıbına girer
        # (eskiden "için sayı içinde aralık(...)" üretiliyordu).
        py = "for sayı in range(5, 0, -1):\n    print(sayı)\n"
        tr = python_kodu_turkceye_cevir(py)
        self.assertIn("için sayı aralık(5, 0, -1):", tr)
        self.assertEqual(turkce_kodu_donustur(tr), py)

    def test_turkce_harfsiz_yazim_kullanici_adini_bulur(self):
        # "sayı" sözlük kelimesi (number) olsa da kullanıcı tanımladıysa
        # "sayi" yazımı da o kutudur; eskiden number'a çevrilip hata veriyordu.
        self.assertIn("print(sayı + 1)", turkce_kodu_donustur("sayı = 5\nyazdır(sayi + 1)"))
        # Türkçe harfsiz yazım ayrıca tanımlıysa ikisi ayrı kalır.
        self.assertIn("print(sayi, sayı)",
                      turkce_kodu_donustur("sayı = 5\nsayi = 2\nyazdır(sayi, sayı)"))

    def test_kaplumbaga_tamamla(self):
        # turtle.done() -> kaplumbağa.tamamla(); eski "çıkışta_bekle" de çalışır.
        py = "import turtle\nturtle.forward(10)\nturtle.done()\n"
        tr = python_kodu_turkceye_cevir(py)
        self.assertIn("kaplumbağa.tamamla()", tr)
        self.assertEqual(turkce_kodu_donustur(tr), py)
        self.assertIn("from turtle import *\ndone()", turkce_kodu_donustur(
            python_kodu_turkceye_cevir("from turtle import *\ndone()")))
        self.assertIn("turtle.done()", turkce_kodu_donustur(
            "içe_aktar kaplumbağa\nkaplumbağa.çıkışta_bekle()"))

    def test_ozel_metotlar_turkcelesir(self):
        tr = python_kodu_turkceye_cevir(
            "class A:\n    def __init__(self):\n        pass\n"
            "    def __add__(self, o):\n        return self\n")
        self.assertIn("fonksiyon __başlat__(kendisi)", tr)
        self.assertIn("fonksiyon __topla__(kendisi, o)", tr)
        self.assertIn("def __add__", turkce_kodu_donustur(tr))

    def test_f_metin_ifadeleri_turkcelesir(self):
        # f-metin ifadeleri çevrilir; düz metin ve ifade içindeki metinler korunur.
        py = ('class V:\n    def f(self):\n'
              '        return f"V({self.x}) {{len}} {len(self.l)!r:>5} {\', \'.join(self.l)}"\n'
              'print(f"{\'print len\'} {max(1, 2):03d} {1 if True else 2}")\n')
        tr = python_kodu_turkceye_cevir(py)
        self.assertIn('f"V({kendisi.x}) {{len}} {uzunluk(kendisi.l)!r:>5} '
                      '{\', \'.birleştir(kendisi.l)}"', tr)
        self.assertIn('{\'print len\'} {en_büyük(1, 2):03d} {1 eğer Doğru değilse 2}', tr)
        self.assertEqual(turkce_kodu_donustur(tr), py)

    def test_ozel_adlar_python_gibi_alt_cizgili(self):
        # Özel adlar "__ad__" biçimindedir; aksansız yazım da çalışır.
        py = turkce_kodu_donustur(
            "sınıf A:\n    fonksiyon __başlat__(kendisi):\n        geç\n"
            "    fonksiyon __baslat__(kendisi):\n        geç\n"
            "eğer __isim__ == '__main__':\n    yazdır(__dosya__, A.__belge__)\n")
        self.assertEqual(py.count("def __init__(self)"), 2)
        self.assertIn("if __name__ == '__main__':", py)
        self.assertIn("print(__file__, A.__doc__)", py)
        self.assertIn("__dışlayıcı_veya__", python_kodu_turkceye_cevir(
            "class A:\n    def __xor__(self, o):\n        pass\n"))

    def test_eski_ozel_yazimi_calismaya_devam_eder(self):
        # v3.2.0'daki "başlat_özel" / "isim_özel" yazımıyla yazılmış kod bozulmamalı.
        py = turkce_kodu_donustur(
            "sınıf A:\n    fonksiyon başlat_özel(kendisi):\n        geç\n"
            "eğer isim_özel == '__main__':\n    yazdır(dosya_özel, tablo_adı)\n")
        self.assertIn("def __init__(self):", py)
        self.assertIn("if __name__ == '__main__':", py)
        self.assertIn("print(__file__, __tablename__)", py)


class CekirdekDuzeltmeTestleri(unittest.TestCase):
    """Dil çekirdeğindeki doğrulanmış hataların regresyon testleri."""

    def assertCikti(self, ana, beklenen):
        kod, cikti = calistir(ana)
        self.assertEqual((kod, cikti), (0, beklenen))

    # 1. kendisi.X özniteliği başka nesnelerin aynı adlı metotlarını korumamalı
    def test_oznitelik_adi_baska_nesnenin_metodunu_korumaz(self):
        py = turkce_kodu_donustur(
            "içe_aktar kaplumbağa\n"
            "sınıf Oyuncu:\n"
            "    fonksiyon __başlat__(kendisi):\n"
            "        kendisi.t = kaplumbağa.Kaplumbağa()\n"
            "        kendisi.hız = 5\n"
            "        kendisi.renk = 'mavi'\n"
            "        kendisi.t.hız(0)\n"
            "        kendisi.t.renk('kırmızı')\n"
            "        kendisi.t.ileri(kendisi.hız)\n"
            "        yazdır(kendisi.hız, kendisi.renk)\n")
        self.assertIn("self.t.speed(0)", py)
        self.assertIn("self.t.color('kırmızı')", py)
        self.assertIn("self.t.forward(self.hız)", py)
        self.assertIn("print(self.hız, self.renk)", py)
        self.assertIn("self.hız = 5", py)

    def test_kullanici_metodu_adi_liste_metodunu_korumaz(self):
        self.assertCikti(
            "sınıf Sepet:\n"
            "    fonksiyon __başlat__(kendisi):\n"
            "        kendisi.öğeler = []\n"
            "    fonksiyon sona_ekle(kendisi, x):\n"
            "        kendisi.öğeler.sona_ekle(x * 10)\n"
            "d = {'a': 1}\n"
            "yazdır(liste(d.öğeler()))\n"
            "sayılar = []\n"
            "sayılar.sona_ekle(5)\n"
            "s = Sepet()\n"
            "s.sona_ekle(3)\n"
            "yazdır(sayılar, s.öğeler)\n",
            "[('a', 1)]\n[5] [30]\n")

    # 2. from random import random: modül adı üye adıyla çevrilmemeli
    def test_from_random_import_random_modul_adi(self):
        tr = python_kodu_turkceye_cevir(
            "from random import random, randint\nfrom time import time\n"
            "from copy import copy\nfrom datetime import datetime\n")
        self.assertTrue(tr.startswith("den rastgele içe_aktar "), tr)
        self.assertIn("den zaman içe_aktar zaman", tr)
        self.assertIn("den kopyala içe_aktar kopyala", tr)
        self.assertIn("den tarih_saat içe_aktar tarih_saat", tr)
        py = turkce_kodu_donustur(tr)
        self.assertIn("from random import random, randint", py)

    # 3. math.pow / math.exp matematik tablosunda
    def test_math_pow_exp_iki_yonde(self):
        tr = python_kodu_turkceye_cevir(
            "import math\nprint(math.pow(2, 3), math.exp(0))\nfrom math import exp\n")
        self.assertNotIn("matematikf", tr)
        self.assertEqual(turkce_kodu_donustur(tr),
                         "import math\nprint(math.pow(2, 3), math.exp(0))\nfrom math import exp\n")
        self.assertCikti("içe_aktar matematik\n"
                         "yazdır(matematik.üst_al(2, 3), matematik.üstel_al(0), "
                         "matematik.üs_al(2, 2), matematik.üstel(0))\n",
                         "8.0 1.0 4.0 1.0\n")

    # 4. Büyük harfli ASCII renk adları
    def test_buyuk_harfli_ascii_renk_adlari(self):
        import re
        from turkod_ide import runner
        from turkod_ide.deger_sozlugu import calisma_tablolari
        kaynak = re.search(r"\n_TK_DEGERLER = .*?(?=\ndef _tk_yazi_tipi)",
                           runner.RUNNER_ORTAK, re.S).group(0)
        ad_alani = {"re": re}
        exec(kaynak, ad_alani)
        renk = calisma_tablolari()["renk"]
        tk_deger = ad_alani["_tk_deger"]
        for yazi, beklenen in (("MAVI", "blue"), ("SIYAH", "black"), ("GRI", "gray"),
                               ("ACIK MAVI", "lightblue"), ("MAVİ", "blue"),
                               ("KIRMIZI", "red"), ("SARI", "yellow"), ("Mavi", "blue"),
                               ("AÇIK MAVİ", "lightblue")):
            self.assertEqual(tk_deger(renk, yazi), beklenen, yazi)

    # 5. Sözdizimi hatası sütunu TürKod satırına göre
    def test_sozdizimi_hatasi_sutunu_turkod_satirina_gore(self):
        from turkod_ide.ast_katmani import dogrula
        sonuc = dogrula('yazdır(uzunluk("ab") ** )\n')
        self.assertFalse(sonuc.basarili)
        self.assertEqual((sonuc.hatalar[0].satir, sonuc.hatalar[0].sutun), (1, 25))
        sonuc = dogrula('x = 1\neğer x > 0 ise\n    yazdır(x)\n')
        self.assertFalse(sonuc.basarili)
        self.assertEqual(sonuc.hatalar[0].satir, 2)
        self.assertLessEqual(sonuc.hatalar[0].sutun, len("eğer x > 0 ise") + 1)

    # 6. "den rastgele içe_aktar tamsayı" sonrası iki argümanlı tamsayı(...)
    def test_rastgele_tamsayi_iki_argumanla_randint(self):
        py = turkce_kodu_donustur(
            "den rastgele içe_aktar tamsayı\n"
            "a = tamsayı(1, 5)\nb = tamsayı('7')\nc = tamsayı('ff', 16)\n"
            "d = tamsayı(uzunluk([1]), 3 + 2)\n")
        self.assertIn("a = randint(1, 5)", py)
        self.assertIn("b = int('7')", py)
        self.assertIn("c = int('ff', 16)", py)
        self.assertIn("d = randint(len([1]), 3 + 2)", py)
        self.assertIn("randint(1, 5)", turkce_kodu_donustur(
            "den rastgele içe_aktar *\nx = tamsayı(1, 5)\n"))

    # 7. Noktadan sonra anahtar kelimeye çevrilmez
    def test_noktadan_sonra_anahtar_kelime_uretilmez(self):
        py = turkce_kodu_donustur(
            "içe_aktar zaman\nzaman.bekle(0)\n"
            "sınıf A:\n    fonksiyon __başlat__(kendisi):\n        kendisi.geç = 1\n"
            "yazdır(A().geç)\n")
        self.assertNotIn(".await", py)
        self.assertNotIn(".pass", py)
        self.assertIn("self.geç = 1", py)
        self.assertIn("time.sleep(0)", py)
        compile(py, "<test>", "exec")

    # süper() takma adı: üst_sınıf() ile aynı (super)
    def test_super_takma_adi(self):
        for ad in ("süper", "üst_sınıf", "ust_sinif"):
            py = turkce_kodu_donustur(
                "içe_aktar kaplumbağa\n"
                "sınıf T(kaplumbağa.Kaplumbağa):\n"
                f"    fonksiyon __başlat__(kendisi):\n        {ad}().__başlat__()\n"
                "sınıf A:\n    geç\n"
                f"sınıf B(A):\n    fonksiyon __başlat__(kendisi, x):\n"
                f"        {ad}().__başlat__()\n        kendisi.x = x\n")
            self.assertEqual(py.count("super().__init__()"), 2, py)
        tr = python_kodu_turkceye_cevir(
            "class B(A):\n    def __init__(self):\n        super().__init__()\n")
        self.assertIn("üst_sınıf().__başlat__()", tr)
        self.assertIn("super().__init__()", turkce_kodu_donustur(tr))
        self.assertCikti(
            "sınıf A:\n    fonksiyon __başlat__(kendisi):\n        kendisi.a = 1\n"
            "sınıf B(A):\n    fonksiyon __başlat__(kendisi):\n"
            "        süper().__başlat__()\n        kendisi.b = 2\n"
            "b = B()\nyazdır(b.a + b.b)\n",
            "3\n")

    # A. Pencere başlığı: tkinter/kaplumbağa'da .başlık(...) -> title
    def test_pencere_basligi_title_olur(self):
        py = turkce_kodu_donustur(
            "içe_aktar tkinter_arayüz olarak tk\nk = tk.Tk()\nk.başlık('y')\n"
            "sınıf Uyg:\n    fonksiyon __başlat__(kendisi, kök):\n"
            "        kendisi.başlık = 'x'\n        kök.başlık(kendisi.başlık)\n")
        self.assertIn("k.title('y')", py)
        self.assertIn("kök.title(self.başlık)", py)
        self.assertIn("self.başlık = 'x'", py)
        py = turkce_kodu_donustur(
            "içe_aktar kaplumbağa\ne = kaplumbağa.Ekran()\ne.başlık('oyun')\n")
        self.assertIn("e.title('oyun')", py)
        # Kütüphane başka olunca düz sözlük anlamı (header) değişmez.
        self.assertIn("x.header(", turkce_kodu_donustur("x.başlık('a')\n"))

    # B. Kütüphane sınıfından türeyen sınıfta kendisi.ileri(...) çevrilir
    def test_kutuphane_alt_sinifinda_kendisi_metotlari(self):
        py = turkce_kodu_donustur(
            "içe_aktar kaplumbağa\n"
            "sınıf Oyuncu(kaplumbağa.Kaplumbağa):\n"
            "    fonksiyon __başlat__(kendisi):\n"
            "        süper().__başlat__()\n"
            "        kendisi.renk_adı = 'mavi'\n"
            "        kendisi.ileri(5)\n"
            "        kendisi.zıpla()\n"
            "        kendisi.renk_adı()\n"
            "    fonksiyon zıpla(kendisi):\n"
            "        kendisi.sola_dön(90)\n"
            "sınıf Kendi:\n"
            "    fonksiyon f(kendisi):\n"
            "        kendisi.ileri(1)\n")
        self.assertIn("self.forward(5)", py)
        self.assertIn("self.left(90)", py)
        self.assertIn("self.zıpla()", py)
        self.assertIn("self.renk_adı()", py)
        # Kütüphaneden türemeyen sınıfta kendisi.X korunur (eski davranış).
        self.assertIn("self.ileri(1)", py)


if __name__ == "__main__":
    unittest.main()
