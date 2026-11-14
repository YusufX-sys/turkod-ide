"""Backend (IDECore / ayarlar / sunucu) hata düzeltmelerinin testleri."""
import ast
import codecs
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

# Gerçek ayar dosyasına dokunulmasın (IDECore içe aktarılmadan önce).
_SANAL_EV = tempfile.mkdtemp(prefix="turkod_test_ev_")
import atexit  # noqa: E402
atexit.register(shutil.rmtree, _SANAL_EV, True)
for _degisken in ("USERPROFILE", "HOME", "LOCALAPPDATA"):
    os.environ[_degisken] = _SANAL_EV

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import settings as ayarlar_modulu
    from turkod_ide.ide_core import IDECore

_CORE = None


def core():
    global _CORE
    if _CORE is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _CORE = IDECore()
    return _CORE


class AyarBekleyenTestleri(unittest.TestCase):
    def test_kaydedilemeyen_deger_sonraki_set_ile_kaybolmaz(self):
        a = ayarlar_modulu.AyarlarYoneticisi()
        self.assertTrue(a.set("yazi_boyutu", 14))
        asil = a.kaydet
        a.kaydet = lambda: False  # disk geçici olarak yazılamıyor
        try:
            self.assertFalse(a.set("yazi_boyutu", 20))
        finally:
            a.kaydet = asil
        self.assertTrue(a.set("tema", "Açık"))
        self.assertEqual(a.get("yazi_boyutu"), 20)
        with open(a.dosya_yolu, encoding="utf-8") as f:
            disk = json.load(f)
        self.assertEqual(disk["yazi_boyutu"], 20)
        self.assertEqual(disk["tema"], "Açık")


class SilmeTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_sil_")
        self.addCleanup(shutil.rmtree, self.klasor, True)
        self.yol = os.path.join(self.klasor, "a.trpy")
        with open(self.yol, "w") as f:
            f.write("x")

    @unittest.skipUnless(os.name == "nt", "yalnızca Windows")
    def test_cop_kutusu_yoksa_sessizce_silmez(self):
        c = core()
        c._cop_kutusu_var_mi = lambda yol: False  # USB bellek / ağ klasörü
        try:
            r = c.oge_sil(self.yol)
        finally:
            del c._cop_kutusu_var_mi
        self.assertFalse(r["ok"])
        self.assertTrue(r["kalici_gerekir"])
        self.assertTrue(os.path.exists(self.yol))
        r = c.oge_sil(self.yol, kalici=True)
        self.assertEqual(r, {"ok": True, "yol": self.yol, "kalici": True})
        self.assertFalse(os.path.exists(self.yol))

    @unittest.skipUnless(os.name == "nt", "yalnızca Windows")
    def test_kalici_klasor_silme(self):
        alt = os.path.join(self.klasor, "alt")
        os.makedirs(os.path.join(alt, "ic"))
        self.assertTrue(core().oge_sil(alt, kalici=True)["ok"])
        self.assertFalse(os.path.exists(alt))


class DebugHazirlikTestleri(unittest.TestCase):
    def test_hazirlanirken_debug_durdur_baslatmaz(self):
        c = core()
        orijinal = c._python_kodu_hazirla
        sonuclar = {}

        def hazirla(*a, **k):
            sonuclar["durdur"] = c.debug_durdur()
            return orijinal(*a, **k)

        c._python_kodu_hazirla = hazirla
        try:
            r = c.debug_baslat("yazdır(1)", ilk_satirda_dur=True)
        finally:
            del c._python_kodu_hazirla
        self.assertTrue(sonuclar["durdur"].get("iptal"))
        self.assertFalse(r["ok"], r)
        self.assertTrue(r.get("iptal"))
        self.assertIsNone(c._debug_oturumu)
        self.assertEqual(c._hazirlananlar, {})

    def test_sunucu_baglanti_kopunca_hazirligi_iptal_eder(self):
        with open(os.path.join(KOK, "turkod_ide", "server.py"), encoding="utf-8") as f:
            agac = ast.parse(f.read())
        islev = next(d for d in agac.body if isinstance(d, ast.FunctionDef)
                     and d.name == "_calisan_programi_durdur")
        self.assertIn("hazirliklari_iptal_et", ast.dump(islev))
        c = core()
        kimlik = c._hazirlik_baslat()
        try:
            self.assertTrue(c.hazirliklari_iptal_et())
            self.assertTrue(c._hazirlik_iptal_edildi(kimlik))
        finally:
            c._hazirlik_bitir(kimlik)


class AramaTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_ara_")
        self.addCleanup(shutil.rmtree, self.klasor, True)

    def yaz(self, ad, ham):
        with open(os.path.join(self.klasor, ad), "wb") as f:
            f.write(ham)

    def test_tam_kelime_duzenli_ifade_gruplanir(self):
        self.yaz("a.trpy", "kediler\nköpekler\nkedi\n".encode("utf-8"))
        r = core().dosyalarda_ara(self.klasor, "kedi|köpek", tam_kelime=True, regex=True)
        self.assertEqual([s["satir"] for s in r["sonuclar"]], [3])

    def test_cp1254_utf16_ve_bom(self):
        self.yaz("c.trpy", "# ağaç\r\nyazdır('çiçek')\r\n".encode("cp1254"))
        self.yaz("u.trpy", codecs.BOM_UTF16_LE + "x = 1\nçiçek = 2\n".encode("utf-16-le"))
        self.yaz("b.trpy", codecs.BOM_UTF8 + "çiçek = 3\n".encode("utf-8"))
        r = core().dosyalarda_ara(self.klasor, "çiçek")
        bulunan = {(os.path.basename(s["yol"]), s["satir"], s["sutun"]) for s in r["sonuclar"]}
        self.assertEqual(bulunan, {("c.trpy", 2, 9), ("u.trpy", 2, 1), ("b.trpy", 1, 1)})


class BicimTablosuTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_bicim_")
        self.addCleanup(shutil.rmtree, self.klasor, True)

    def test_ad_degisince_bicim_korunur(self):
        c = core()
        yol = os.path.join(self.klasor, "eski.trpy")
        ham = "x = 'ş'\ny = 2\n".encode("cp1254")
        with open(yol, "wb") as f:
            f.write(ham)
        r = c.dosya_oku(yol)
        yeni = c.oge_yeniden_adlandir(yol, "yeni.trpy")["yol"]
        # Diskten algılama devreye girmesin: yeni dosyanın biçimi tablodan gelmeli.
        with open(yeni, "wb") as f:
            f.write(b"")
        c.dosya_kaydet(yeni, r["icerik"])
        with open(yeni, "rb") as f:
            self.assertEqual(f.read(), ham)

    def test_klasor_adi_degisince_icindekilerin_bicimi_tasinir(self):
        c = core()
        alt = os.path.join(self.klasor, "proje")
        os.makedirs(alt)
        yol = os.path.join(alt, "a.trpy")
        with open(yol, "wb") as f:
            f.write("a = 'ğ'\n".encode("cp1254"))
        c.dosya_oku(yol)
        yeni = c.oge_yeniden_adlandir(alt, "proje2")["yol"]
        anahtar = c._bicim_anahtari(os.path.join(yeni, "a.trpy"))
        self.assertEqual(c._dosya_bicimleri().get(anahtar), ("cp1254", "\n"))

    def test_bicim_bilinmiyorsa_diskten_algilanir(self):
        # Backend yeniden başladı: biçim tablosu boş.
        c = core()
        for ad, ham in (("c.trpy", "x = 'ç'\ny = 1\n".encode("cp1254")),
                        ("u.trpy", codecs.BOM_UTF16_LE + "x = 'ç'\ny = 1\n".encode("utf-16-le")),
                        ("b.trpy", codecs.BOM_UTF8 + "x = 'ç'\r\ny = 1\r\n".encode("utf-8"))):
            yol = os.path.join(self.klasor, ad)
            with open(yol, "wb") as f:
                f.write(ham)
            c._dosya_bicimleri().pop(c._bicim_anahtari(yol), None)
            k = c.dosya_kaydet(yol, "x = 'ç'\ny = 1\n")
            self.assertTrue(k["ok"], k)
            with open(yol, "rb") as f:
                self.assertEqual(f.read(), ham, ad)


def _olu_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class GeciciSupurmeTestleri(unittest.TestCase):
    def test_yalnizca_sahibi_olmus_eski_klasorler_silinir(self):
        kok = tempfile.mkdtemp(prefix="turkod_supur_kok_")
        self.addCleanup(shutil.rmtree, kok, True)
        canli = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(canli.wait)
        self.addCleanup(canli.kill)
        eski = time.time() - 3 * 24 * 3600

        def klasor(ad, sahip=None, eski_mi=True):
            yol = os.path.join(kok, ad)
            os.makedirs(yol)
            with open(os.path.join(yol, "dosya.txt"), "w") as f:
                f.write("x")
            if sahip is not None:
                with open(os.path.join(yol, ".turkod_sahip"), "w") as f:
                    f.write(str(sahip))
            if eski_mi:
                os.utime(yol, (eski, eski))
            return yol

        olu_debug = klasor("turkod_debug_a", _olu_pid())
        sahipsiz_debug = klasor("turkod_debug_b")
        olu_calisma = klasor("turkod_calisma_c", _olu_pid())
        canli_debug = klasor("turkod_debug_d", canli.pid)  # çalışan ikinci pencere
        yeni_debug = klasor("turkod_debug_e", _olu_pid(), eski_mi=False)
        kendi = klasor("turkod_calisma_f", os.getpid())
        yabanci = klasor("baska_klasor")
        IDECore.eski_gecicileri_supur(kok=kok)
        for yol in (olu_debug, sahipsiz_debug, olu_calisma):
            self.assertFalse(os.path.exists(yol), yol)
        for yol in (canli_debug, yeni_debug, kendi, yabanci):
            self.assertTrue(os.path.exists(yol), yol)
        IDECore.eski_gecicileri_supur(yalnizca_kendi=True, kok=kok)
        self.assertFalse(os.path.exists(kendi))
        self.assertTrue(os.path.exists(canli_debug))


@unittest.skipUnless(os.name == "nt", "yalnızca Windows")
class KontrolCalistirTestleri(unittest.TestCase):
    def test_sonsuz_cikti_sinirli_ve_surec_agaci_olur(self):
        klasor = tempfile.mkdtemp(prefix="turkod_kontrol_testi_")
        self.addCleanup(shutil.rmtree, klasor, True)
        pid_dosyasi = os.path.join(klasor, "torun.pid")
        py = ("import subprocess, sys\n"
              "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
              f"open({pid_dosyasi!r}, 'w').write(str(p.pid))\n"
              "while True:\n    print('x' * 1000)\n")
        with self.assertRaises(subprocess.TimeoutExpired):
            core()._kontrol_calistir(sys.executable, py, 3)
        with open(pid_dosyasi) as f:
            torun = int(f.read())
        from turkod_ide.calistirici import _surec_yasiyor
        son = time.time() + 5
        while _surec_yasiyor(torun) and time.time() < son:
            time.sleep(0.2)
        self.assertFalse(_surec_yasiyor(torun))

    def test_cok_cikti_sonra_hata_izi_korunur(self):
        py = ("import sys\nfor i in range(20000):\n    print('y' * 500)\n"
              "sys.stderr.write('z' * 300000)\nraise NameError('bulunamadi')\n")
        sonuc, _ = core()._kontrol_calistir(sys.executable, py, 60)
        self.assertNotEqual(sonuc.returncode, 0)
        self.assertLess(len(sonuc.stdout), 200 * 1024)
        self.assertLess(len(sonuc.stderr), 200 * 1024)
        self.assertIn("NameError: bulunamadi", sonuc.stderr)


if __name__ == "__main__":
    unittest.main()
