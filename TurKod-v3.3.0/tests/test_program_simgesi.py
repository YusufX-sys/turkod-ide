"""Çalışan programın pencereleri görev çubuğunda Python simgesiyle değil
TürKod program simgesiyle görünür.

Pencere açan test yalnızca TURKOD_ARAYUZ_TESTI=1 ile (Windows masaüstü) çalışır:
    set TURKOD_ARAYUZ_TESTI=1 && python -m unittest tests.test_program_simgesi
"""
import contextlib
import io
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

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import calistirici, runner


class SablonTestleri(unittest.TestCase):
    def test_simge_dosyasi_var_ve_cok_boyutlu(self):
        yol = runner.program_ikonu_yolu()
        self.assertTrue(yol and os.path.isfile(yol))
        from PIL import Image
        boyutlar = Image.open(yol).info["sizes"]
        for b in (16, 32, 48, 256):
            self.assertIn((b, b), boyutlar)

    def test_her_calistiricida_simge_yolu_yerlesir(self):
        try:
            from turkod_ide.debugger import DEBUG_RUNNER_KODU
        except ImportError:
            DEBUG_RUNNER_KODU = None
        for sablon in (runner.RUNNER_KODU, runner.RUNNER_ORTAK, DEBUG_RUNNER_KODU):
            if sablon is None:
                continue
            govde = runner.oneri_tablolarini_yerlestir(sablon)
            self.assertIn(f"_TK_PROGRAM_IKONU = {runner.program_ikonu_yolu()!r}", govde)
            compile(govde, "calistirici", "exec")

    def test_yamalar_simge_kodundan_once_tanimli(self):
        """pygame yaması, içe aktarma yamalarını kuran çağrıdan önce
        tanımlanmalı; yoksa NameError bütün yamaları sessizce kapatır."""
        sablon = runner.RUNNER_ORTAK
        self.assertLess(sablon.index("def _tk_pygame_display_yamala"),
                        sablon.index("\n    _tk_ice_aktarma_yamalari_kur()"))

    def test_calistiricida_yamalar_kurulur(self):
        """Şablon çalışınca içe aktarma yamaları gerçekten kurulur."""
        kod = runner.oneri_tablolarini_yerlestir(runner.RUNNER_ORTAK).replace(
            "_TK_PROGRAM_IKONU = ", "_TK_PROGRAM_IKONU = None and ", 1)
        betik = kod + ("\nimport sys as _s\n"
                       "print(any(type(b).__name__ == '_Bulucu' for b in _s.meta_path))\n")
        klasor = tempfile.mkdtemp(prefix="turkod_sablon_")
        self.addCleanup(shutil.rmtree, klasor, True)
        yol = os.path.join(klasor, "sablon.py")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(betik)
        r = subprocess.run([sys.executable, "-X", "utf8", yol], capture_output=True, timeout=60)
        # Çalıştırıcı print'i Türkçeleştirir: True -> Doğru.
        self.assertEqual(r.stdout.decode("utf-8").strip().splitlines()[-1], "Doğru",
                         r.stderr.decode("utf-8", "replace"))


    def test_simge_pencere_olusmadan_once_verilir(self):
        """Ursina'ya, Panda3D'ye ve pygame'e simge pencere açılmadan önce
        verilir (sonradan konan simge görev çubuğunda geç kalıyordu)."""
        yol = runner.program_ikonu_yolu()
        self.assertTrue(os.path.isfile(yol[:-4] + ".png"), "pygame için PNG yok")
        kod = runner.oneri_tablolarini_yerlestir(runner.RUNNER_ORTAK)
        betik = kod + (
            "\nimport types as _t\n"
            "class Ursina:\n"
            "    def __init__(self, title='ursina', icon='textures/ursina.ico', **k):\n"
            "        self.icon = icon\n"
            "_tk_ursina_yamala(_t.SimpleNamespace(Ursina=Ursina))\n"
            "_prc = []\n"
            "_tk_panda3d_yamala(_t.SimpleNamespace(loadPrcFileData=lambda a, b: _prc.append(b)))\n"
            "print(Ursina().icon == _TK_PROGRAM_IKONU, Ursina(icon='kendi.ico').icon == 'kendi.ico',\n"
            "      _prc == ['icon-filename ' + _TK_PROGRAM_IKONU])\n")
        klasor = tempfile.mkdtemp(prefix="turkod_sablon_")
        self.addCleanup(shutil.rmtree, klasor, True)
        dosya = os.path.join(klasor, "sablon.py")
        with open(dosya, "w", encoding="utf-8") as f:
            f.write(betik)
        r = subprocess.run([sys.executable, "-X", "utf8", dosya], capture_output=True, timeout=60)
        self.assertEqual(r.stdout.decode("utf-8").strip().splitlines()[-1], "Doğru Doğru Doğru",
                         r.stderr.decode("utf-8", "replace"))


@unittest.skipUnless(os.environ.get("TURKOD_ARAYUZ_TESTI") == "1" and sys.platform == "win32",
                     "pencere açar (TURKOD_ARAYUZ_TESTI=1)")
class PencereSimgesiTesti(unittest.TestCase):
    def _calistir_ve_bak(self, kod):
        import ctypes
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        u.SendMessageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        klasor = tempfile.mkdtemp(prefix="turkod_simge_testi_")
        self.addCleanup(shutil.rmtree, klasor, True)
        yol = os.path.join(klasor, "program.trpy")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(kod)
        h = calistirici.Hazirlik(yol)
        self.assertTrue(h.hazirla(), h.hatalar)
        self.addCleanup(h.temizle)
        surec = subprocess.Popen(h.komut, cwd=h.cwd, env=calistirici._ortam(),
                                 creationflags=calistirici.CREATE_NO_WINDOW)
        self.addCleanup(subprocess.run, ["taskkill", "/F", "/T", "/PID", str(surec.pid)],
                        capture_output=True)
        bulunan = []
        for _ in range(40):
            time.sleep(0.5)

            @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
            def cb(hw, _):
                p = wt.DWORD()
                u.GetWindowThreadProcessId(hw, ctypes.byref(p))
                if p.value == surec.pid and u.IsWindowVisible(hw) and not u.GetWindow(hw, 4):
                    n = u.GetWindowTextLengthW(hw)
                    b = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hw, b, n + 1)
                    bulunan.append((b.value, u.SendMessageW(hw, 0x7F, 1, None)))
                return True
            bulunan.clear()
            u.EnumWindows(cb, 0)
            if bulunan and all(simge for _, simge in bulunan):
                break
        return bulunan

    def test_pencere_ilk_gorundugu_anda_turkod_simgesiyle_gorunur(self):
        """Görev çubuğunun kullandığı etkin simge (pencerenin simgesi, yoksa
        sınıfının simgesi) pencere ilk göründüğü anda TürKod simgesidir.
        Eskiden ilk 50 ms-1,3 sn Python simgesi görünüyordu."""
        import ctypes
        import ctypes.wintypes as wt
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        u.SendMessageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        u.GetClassLongPtrW.restype = ctypes.c_void_p
        u.GetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
        u.LoadImageW.restype = ctypes.c_void_p
        u.LoadImageW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, ctypes.c_uint, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_uint]
        u.DrawIconEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p,
                                 ctypes.c_uint]
        dc = u.GetDC(None)
        mdc = g.CreateCompatibleDC(dc)
        g.SelectObject(mdc, g.CreateCompatibleBitmap(dc, 32, 32))

        def pikseller(hicon):
            g.PatBlt(mdc, 0, 0, 32, 32, 0x00FF0062)
            u.DrawIconEx(mdc, 0, 0, hicon, 32, 32, 0, None, 3)
            return [g.GetPixel(mdc, x, y) for x in range(0, 32, 2) for y in range(0, 32, 2)]

        def yakin(a, b):
            fark = [max(abs((x >> s & 255) - (y >> s & 255)) for s in (0, 8, 16))
                    for x, y in zip(a, b)]
            return sum(1 for f in fark if f < 60) / len(fark)

        turkod = pikseller(u.LoadImageW(None, runner.program_ikonu_yolu(), 1, 32, 32, 0x10))
        klasor = tempfile.mkdtemp(prefix="turkod_simge_testi_")
        self.addCleanup(shutil.rmtree, klasor, True)
        yol = os.path.join(klasor, "program.trpy")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("içe_aktar kaplumbağa\nkaplumbağa.ileri(10)\nkaplumbağa.tamamla()\n")
        h = calistirici.Hazirlik(yol)
        self.assertTrue(h.hazirla(), h.hatalar)
        self.addCleanup(h.temizle)
        surec = subprocess.Popen(h.komut, cwd=h.cwd, env=calistirici._ortam(),
                                 creationflags=calistirici.CREATE_NO_WINDOW)
        self.addCleanup(subprocess.run, ["taskkill", "/F", "/T", "/PID", str(surec.pid)],
                        capture_output=True)
        ilk = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def cb(hw, _):
            p = wt.DWORD()
            u.GetWindowThreadProcessId(hw, ctypes.byref(p))
            if p.value == surec.pid and u.IsWindowVisible(hw) and not u.GetWindow(hw, 4):
                ilk.append(u.SendMessageW(hw, 0x7F, 1, None) or u.GetClassLongPtrW(hw, -14))
            return True
        son = time.monotonic() + 30
        while not ilk and time.monotonic() < son:
            u.EnumWindows(cb, 0)
            time.sleep(0.002)
        self.assertTrue(ilk, "pencere açılmadı")
        # Kütüphane simgenin başka bir boyuttaki karesini küçültebilir; birebir
        # aynı olmaz. Python simgesinden belirgin biçimde daha yakın olmalı.
        ctypes.windll.shell32.ExtractIconW.restype = ctypes.c_void_p
        python = pikseller(ctypes.windll.shell32.ExtractIconW(None, sys.executable, 0))
        ilk_resim = pikseller(ilk[0])
        self.assertGreater(yakin(ilk_resim, turkod), yakin(ilk_resim, python) + 0.2,
                           "pencere ilk göründüğünde TürKod simgesi yoktu (Python simgesi?)")

    def test_kaplumbaga_penceresi_turkod_simgesi_ve_basligi(self):
        pencereler = self._calistir_ve_bak(
            "içe_aktar kaplumbağa\nkaplumbağa.ileri(10)\nkaplumbağa.tamamla()\n")
        self.assertEqual(len(pencereler), 1, pencereler)
        baslik, simge = pencereler[0]
        self.assertEqual(baslik, "TürKod Kaplumbağa")
        self.assertTrue(simge, "pencereye simge konmadı (görev çubuğunda python.exe simgesi çıkar)")


if __name__ == "__main__":
    unittest.main()
