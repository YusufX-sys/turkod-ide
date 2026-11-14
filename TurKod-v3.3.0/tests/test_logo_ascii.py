"""TürKod Terminali'ndeki `logo` komutu: logo terminali dolduracak
büyüklükte ASCII karakterlerle çizilir."""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from turkod_ide import logo_ascii  # noqa: E402


class LogoCizimTestleri(unittest.TestCase):
    def test_terminal_yuksekligini_doldurur_ve_ortalanir(self):
        satirlar = logo_ascii.ciz(120, 40)
        self.assertEqual(len(satirlar), 39)  # son satır istem için
        dolu = [s for s in satirlar if s.strip()]
        self.assertGreater(len(dolu), 30)
        self.assertTrue(all(len(s) <= 119 for s in satirlar))
        sol = min(len(s) - len(s.lstrip()) for s in dolu)
        sag = 119 - max(len(s) for s in dolu)
        self.assertLess(abs(sol - sag), 8)  # yatayda ortalı
        # Yalnızca ASCII karakterler.
        self.assertTrue(all(ord(c) < 128 for s in satirlar for c in s))

    def test_dar_terminalde_genislige_gore_kuculur(self):
        satirlar = logo_ascii.ciz(40, 60)
        self.assertTrue(all(len(s) <= 39 for s in satirlar))
        self.assertLess(len(satirlar), 30)

    def test_renkli_ve_renksiz(self):
        self.assertFalse(any("\x1b" in s for s in logo_ascii.ciz(80, 24)))
        renkli = "\n".join(logo_ascii.ciz(80, 24, renkli=True))
        self.assertIn("\x1b[38;2;", renkli)
        self.assertIn("\x1b[0m", renkli)

    def test_ortam_degiskenindeki_boyutu_kullanir(self):
        with mock.patch.dict(os.environ, {"COLUMNS": "100", "LINES": "30"}):
            satirlar = logo_ascii.ciz()
        self.assertEqual(len(satirlar), 29)


class LogoKomutuTestleri(unittest.TestCase):
    def test_kabuk_komutu(self):
        from turkod_ide import kabuk
        self.assertTrue(kabuk.komut_mu("logo"))
        self.assertTrue(kabuk.komut_mu("amblem"))
        cikis = io.StringIO()
        k = kabuk.TurKodKabugu(giris=io.StringIO(), cikis=cikis)
        with mock.patch.dict(os.environ, {"COLUMNS": "80", "LINES": "24"}):
            k.komut("logo", "")
        metin = cikis.getvalue()
        self.assertGreater(len(metin.splitlines()), 20)
        self.assertNotIn("\x1b", metin)  # konsol değil: renksiz

    def test_turkod_logo_komutu(self):
        from turkod_ide import calistirici
        cikis = io.StringIO()
        with mock.patch.dict(os.environ, {"COLUMNS": "90", "LINES": "30"}), \
                contextlib.redirect_stdout(cikis), mock.patch.object(calistirici, "_konsol_hazirla"):
            kod = calistirici.cli_main(["logo"])
        self.assertEqual(kod, 0)
        self.assertEqual(len(cikis.getvalue().rstrip("\n").split("\n")), 29)


class TerminalBoyutuTestleri(unittest.TestCase):
    """IDE terminali boyutunu bildirir; terminal komutları COLUMNS / LINES görür."""

    def setUp(self):
        import tempfile
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_boyut_ortama_gecer(self):
        self.assertTrue(self.c.terminal_boyutu_ayarla("t1", 132, 41)["ok"])
        env = self.c._terminal_ortami("t1")
        self.assertEqual((env["COLUMNS"], env["LINES"]), ("132", "41"))
        self.assertNotIn("COLUMNS", self.c._terminal_ortami("t2"))  # başka sekme
        self.assertFalse(self.c.terminal_boyutu_ayarla("t1", "x", 4)["ok"])
        self.assertFalse(self.c.terminal_boyutu_ayarla("t1", 2, 2)["ok"])

    def test_terminal_komutu_boyutu_gorur(self):
        self.c.terminal_boyutu_ayarla("t1", 77, 22)
        cikti = []
        komut = f'"{sys.executable}" -c "import shutil; print(shutil.get_terminal_size())"'
        self.c._terminal_komut_calistir(komut, on_output=cikti.append, oturum="t1")
        self.assertIn("columns=77, lines=22", "".join(cikti))


if __name__ == "__main__":
    unittest.main()
