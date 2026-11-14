"""EXE'ye dönüştürme ve sekme başına terminal testleri.

Gerçek bir EXE derlemesi (PyInstaller, ~1 dk) yalnızca TURKOD_EXE_TESTI=1
ortam değişkeniyle çalışır:
    set TURKOD_EXE_TESTI=1 && python -m unittest tests.test_exe_donusturucu
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
    from turkod_ide import exe_donusturucu as exe
    from turkod_ide import kabuk
    from turkod_ide.ide_core import IDECore


def sahte_paket(girdiler):
    """PyInstaller'ın EXE sonuna eklediği pakete (CArchive) benzeyen baytlar.
    girdiler: {ad: (veri, tür kodu, sıkıştırılsın mı)}."""
    import struct
    import zlib
    veri_kismi, toc = b"", b""
    bas_boy = struct.calcsize("!IIIIBc")
    for ad, (veri, tur, sik) in girdiler.items():
        saklanan = zlib.compress(veri) if sik else veri
        adb = ad.encode() + b"\0"
        adb += b"\0" * (-(bas_boy + len(adb)) % 16)
        toc += struct.pack("!IIIIBc", bas_boy + len(adb), len(veri_kismi), len(saklanan),
                           len(veri), sik, tur) + adb
        veri_kismi += saklanan
    sonu_boy = struct.calcsize("!8sIIII64s")
    sonu = struct.pack("!8sIIII64s", b"MEI\014\013\012\013\016",
                       len(veri_kismi) + len(toc) + sonu_boy, len(veri_kismi), len(toc),
                       312, b"python312.dll")
    return b"MZ" + b"\0" * 200 + veri_kismi + toc + sonu


def sahte_pyz(kaynak):
    """Eski TürKod EXE'lerindeki gibi _tk_kaynak modülünü içeren PYZ arşivi
    (kaynak None ise modül yok: kaynak gizli)."""
    import importlib.util
    import marshal
    import struct
    import zlib
    govde, toc = b"", []
    if kaynak is not None:
        kod = compile(f"KAYNAK = {kaynak!r}\n", "_tk_kaynak", "exec")
        govde = zlib.compress(marshal.dumps(kod))
        toc.append(("_tk_kaynak", (0, 12, len(govde))))
    toc.append(("baska", (0, 12, 0)))
    return (b"PYZ\0" + importlib.util.MAGIC_NUMBER + struct.pack("!i", 12 + len(govde))
            + govde + marshal.dumps(toc))


class SecenekTestleri(unittest.TestCase):
    def test_varsayilanlar(self):
        dosya, ayar, hatalar = exe.argumanlari_ayristir(["oyun.trpy"])
        self.assertEqual(dosya, "oyun.trpy")
        self.assertEqual(hatalar, [])
        self.assertEqual(ayar, exe.varsayilan_ayarlar())
        self.assertEqual(ayar["pencere"], "turkod")

    def test_butun_secenekler(self):
        dosya, ayar, hatalar = exe.argumanlari_ayristir([
            "oyun.trpy", "--ad", "Uzay Oyunu", "--kayit-yeri", r"C:\Oyunlar",
            "--terminalsiz", "--kaynak-acik", "--klasorlu", "--simge", "a.ico",
            "--dosya-ekle", "resimler", "--dosya-ekle=ses.wav"])
        self.assertEqual(hatalar, [])
        self.assertEqual(ayar["ad"], "Uzay Oyunu")
        self.assertEqual(ayar["kayit_yeri"], r"C:\Oyunlar")
        self.assertEqual(ayar["pencere"], "yok")
        self.assertTrue(ayar["kaynak"] and ayar["klasorlu"])
        self.assertEqual(ayar["ekler"], ["resimler", "ses.wav"])

    def test_turkce_harfli_yazim_da_olur(self):
        _, ayar, hatalar = exe.argumanlari_ayristir(
            ["a.trpy", "--kaynak-açık", "--klasörlü", "--kayıt-yeri", "x", "--Windows_Konsolu"])
        self.assertEqual(hatalar, [])
        self.assertTrue(ayar["kaynak"] and ayar["klasorlu"])
        self.assertEqual((ayar["kayit_yeri"], ayar["pencere"]), ("x", "konsol"))

    def test_hatalar(self):
        _, _, hatalar = exe.argumanlari_ayristir(["a.trpy", "--uçur", "--ad"])
        self.assertEqual(len(hatalar), 2)
        self.assertIn("--uçur", hatalar[0])
        self.assertIn("--ad", hatalar[1])
        dosya, _, hatalar = exe.argumanlari_ayristir(["a.trpy", "b.trpy"])
        self.assertIn("tırnak", hatalar[0])

    def test_komut_metni_geri_ayristirilir(self):
        ayar = exe.varsayilan_ayarlar()
        ayar.update(ad="Uzay Oyunu", kayit_yeri=r"C:\Oyun Klasörü", pencere="konsol",
                    kaynak=True, sonda_bekle=True, ekler=["resimler"])
        metin = exe.komut_metni(r"C:\Kod\uzay oyunu.trpy", ayar)
        self.assertTrue(metin.startswith('turkod exe_yap "C:\\Kod\\uzay oyunu.trpy"'))
        k = kabuk.komut_mu(metin)
        self.assertEqual(k[0], "exe_yap")
        dosya, geri, hatalar = exe.argumanlari_ayristir(kabuk.TurKodKabugu._parcala(k[1]))
        self.assertEqual(hatalar, [])
        self.assertEqual(dosya, r"C:\Kod\uzay oyunu.trpy")
        self.assertEqual(geri, ayar)

    def test_yardim_butun_secenekleri_anlatir(self):
        metin = exe.yardim_metni()
        for _, bayrak, _, _ in exe.SECENEKLER:
            self.assertIn(bayrak, metin)

    def test_kabuk_komutlari(self):
        self.assertEqual(kabuk.komut_mu("exe a.trpy"), ("exe_yap", "a.trpy"))
        self.assertEqual(kabuk.komut_mu("kaynak oyun.exe"), ("kaynak", "oyun.exe"))
        self.assertIsNone(kabuk.komut_mu("kaynak = 5"))
        self.assertIsNone(kabuk.komut_mu("turkod --bilinmeyen"))


class GirisKoduTestleri(unittest.TestCase):
    def test_runner_sablonu_uyarlanir(self):
        ayar = {"ad": "x", "pencere": "konsol", "sonda_bekle": False, "veri": False,
                "kaynak_acik": False}
        kod = exe.giris_kodu_uret(ayar, 'yazdır("a")')
        compile(kod, "giris.py", "exec")
        self.assertIn("kod = _tk_program_kodu()", kod)
        self.assertIn("exec(kod, _ana.__dict__)", kod)
        self.assertIn("_tk_exe_hata_bitti()", kod)
        self.assertNotIn('open("turkce_kod_calisma.py"', kod)
        self.assertIn(repr(exe.IMZA), kod)

    def test_turkod_exe_mi(self):
        klasor = tempfile.mkdtemp(prefix="turkod_exe_imza_")
        self.addCleanup(shutil.rmtree, klasor, True)
        baska = os.path.join(klasor, "baska.exe")
        with open(baska, "wb") as f:
            f.write(b"MZ" + b"\0" * 1000)
        self.assertFalse(exe.turkod_exe_mi(baska))
        self.assertEqual(exe.exe_kaynagi_oku(baska)[0], "turkod_degil")
        # Eskiden imza dosyasının adını düz metin olarak içeren HER dosya
        # TürKod EXE'si sayılıp çalıştırılıyordu.
        sahte = os.path.join(klasor, "sahte.exe")
        with open(sahte, "wb") as f:
            f.write(b"MZ" + b"\0" * 1000 + exe.IMZA_DOSYASI.encode() + b"\0" * 100)
        self.assertFalse(exe.turkod_exe_mi(sahte))
        tek = os.path.join(klasor, "tek.exe")
        with open(tek, "wb") as f:
            f.write(sahte_paket({exe.IMZA_DOSYASI: (exe.IMZA.encode() + b"\n", b"x", 1)}))
        self.assertTrue(exe.turkod_exe_mi(tek))
        # Klasörlü: EXE bir PyInstaller paketi, imza _internal'da.
        os.makedirs(os.path.join(klasor, "k", "_internal"))
        with open(os.path.join(klasor, "k", "_internal", exe.IMZA_DOSYASI), "w") as f:
            f.write(exe.IMZA + "\n")
        with open(os.path.join(klasor, "k", "k.exe"), "wb") as f:
            f.write(sahte_paket({}))
        self.assertTrue(exe.turkod_exe_mi(os.path.join(klasor, "k", "k.exe")))
        self.assertEqual(exe.exe_kaynagi_oku(os.path.join(klasor, "yok.exe"))[0], "hata")

    def test_kaynak_exe_calistirilmadan_okunur(self):
        klasor = tempfile.mkdtemp(prefix="turkod_exe_kaynak_")
        self.addCleanup(shutil.rmtree, klasor, True)
        imza = {exe.IMZA_DOSYASI: (exe.IMZA.encode() + b"\n", b"x", 1)}
        yeni = os.path.join(klasor, "yeni.exe")
        with open(yeni, "wb") as f:
            f.write(sahte_paket({**imza, exe.KAYNAK_DOSYASI: ('yazdır("ç")\n'.encode(), b"x", 1)}))
        eski = os.path.join(klasor, "eski.exe")
        with open(eski, "wb") as f:
            f.write(sahte_paket({**imza, "PYZ-00.pyz": (sahte_pyz('yazdır("eski")\n'), b"z", 0)}))
        gizli = os.path.join(klasor, "gizli.exe")
        with open(gizli, "wb") as f:
            f.write(sahte_paket({**imza, "PYZ-00.pyz": (sahte_pyz(None), b"z", 0)}))
        os.makedirs(os.path.join(klasor, "k", "_internal"))
        for ad, icerik in ((exe.IMZA_DOSYASI, exe.IMZA + "\n"), (exe.KAYNAK_DOSYASI, "a = 1\n")):
            with open(os.path.join(klasor, "k", "_internal", ad), "w", encoding="utf-8") as f:
                f.write(icerik)
        klasorlu = os.path.join(klasor, "k", "k.exe")
        with open(klasorlu, "wb") as f:
            f.write(sahte_paket({}))

        def calistirilmamali(*_a, **_k):
            raise AssertionError("EXE çalıştırılmamalı")
        asil = exe.subprocess.run, exe.subprocess.Popen
        exe.subprocess.run = exe.subprocess.Popen = calistirilmamali
        try:
            self.assertEqual(exe.exe_kaynagi_oku(yeni), ("acik", 'yazdır("ç")\n'))
            self.assertEqual(exe.exe_kaynagi_oku(eski), ("acik", 'yazdır("eski")\n'))
            self.assertEqual(exe.exe_kaynagi_oku(gizli)[0], "gizli")
            self.assertEqual(exe.exe_kaynagi_oku(klasorlu), ("acik", "a = 1\n"))
        finally:
            exe.subprocess.run, exe.subprocess.Popen = asil

    def test_yabanci_klasor_ve_exe_silinmez(self):
        klasor = tempfile.mkdtemp(prefix="turkod_exe_hedef_")
        self.addCleanup(shutil.rmtree, klasor, True)
        # uzay.trpy'nin yanında kullanıcının resimlerle dolu "uzay" klasörü.
        kullanici = os.path.join(klasor, "uzay")
        os.makedirs(kullanici)
        with open(os.path.join(kullanici, "resim.png"), "wb") as f:
            f.write(b"resim")
        self.assertIsNotNone(exe._hedef_engeli(kullanici, True, "uzay"))
        # Klasörün sonuna kadar gidilse bile (derleme sırasında oluşan) yine silinmez.
        cikti = []
        with open(os.path.join(klasor, "uzay.trpy"), "w", encoding="utf-8") as f:
            f.write('yazdır("a")\n')
        self.assertIsNone(exe.exe_yap(os.path.join(klasor, "uzay.trpy"),
                                      dict(exe.varsayilan_ayarlar(), klasorlu=True),
                                      yaz=cikti.append))
        self.assertIn("TürKod'un yapmadığı", "\n".join(cikti))
        self.assertTrue(os.path.isfile(os.path.join(kullanici, "resim.png")))
        # Önceki TürKod klasörü değiştirilebilir.
        onceki = os.path.join(klasor, "say")
        os.makedirs(os.path.join(onceki, "_internal"))
        with open(os.path.join(onceki, "_internal", exe.IMZA_DOSYASI), "w") as f:
            f.write(exe.IMZA + "\n")
        open(os.path.join(onceki, "say.exe"), "wb").close()
        self.assertIsNone(exe._hedef_engeli(onceki, True, "say"))
        # Tek dosyalı: TürKod'un yapmadığı aynı adlı EXE'nin üstüne yazılmaz.
        baska = os.path.join(klasor, "oyun.exe")
        with open(baska, "wb") as f:
            f.write(b"MZ baska program")
        self.assertIsNotNone(exe._hedef_engeli(baska, False, "oyun"))
        with open(baska, "wb") as f:
            f.write(sahte_paket({exe.IMZA_DOSYASI: (exe.IMZA.encode(), b"x", 0)}))
        self.assertIsNone(exe._hedef_engeli(baska, False, "oyun"))
        self.assertIsNone(exe._hedef_engeli(os.path.join(klasor, "yeni.exe"), False, "yeni"))


class TurkceCiktiTestleri(unittest.TestCase):
    """EXE yapılırken ve çalışırken çıkabilecek İngilizce iletiler Türkçeleşir."""

    def test_pip_ve_pyinstaller_satirlari(self):
        ornekler = {
            "ERROR: No matching distribution found for pyinstaller":
                "Hata: pyinstaller paketi bulunamadı.",
            r"12 ERROR: Unable to find 'C:\o\r.png' when adding binary and data files.":
                r"Hata: EXE'ye eklenecek dosya bulunamadı: C:\o\r.png",
            "Successfully installed altgraph-0.17 pyinstaller-6.1":
                "Kuruldu: altgraph-0.17 pyinstaller-6.1",
            "PermissionError: [WinError 5] Access is denied: 'a.exe'":
                "Erişim engellendi: dosya şu an açık ya da o klasöre yazma izni yok.",
            "Traceback (most recent call last):": "Hata izi (en son çağrı en altta):",
        }
        for ingilizce, turkce in ornekler.items():
            self.assertEqual(exe.arac_satiri_cevir(ingilizce), (turkce, True), ingilizce)
        self.assertEqual(exe.arac_satiri_cevir("7 ERROR: hiç görülmemiş")[1], False)

    def test_hata_ayrintisi_cevrilemeyeni_ayri_gosterir(self):
        cikti = []
        exe._hata_ayrintisi_yaz(["Traceback (most recent call last):",
                                 "ValueError: invalid literal for int() with base 10: 'a'",
                                 "9 ERROR: Weird failure"], cikti.append)
        self.assertIn("Geçersiz Değer Hatası", cikti[1])
        self.assertIn("İngilizce", cikti[2])

    def test_exe_ici_hata_cevirileri_modulu(self):
        ad_alani = {}
        exec(exe.hata_cevirileri_kodu_uret(""), ad_alani)
        self.assertEqual(ad_alani["hata_turu_adi"]("ZeroDivisionError"), "Sıfıra Bölme Hatası")
        self.assertIn("tamsayıya", ad_alani["hata_aciklamasi"](
            "ValueError", "invalid literal for int() with base 10: 'a'"))

    def test_beklenmeyen_baslatma_hatasi_turkce(self):
        klasor = tempfile.mkdtemp(prefix="turkod_giris_")
        self.addCleanup(shutil.rmtree, klasor, True)
        for ad, icerik in (("giris.py", exe.GIRIS_KOKU),
                           ("_tk_hata_cevirileri.py", exe.hata_cevirileri_kodu_uret("")),
                           ("_tk_ana.py", "1 / 0\n")):
            with open(os.path.join(klasor, ad), "w", encoding="utf-8") as f:
                f.write(icerik)
        r = subprocess.run([sys.executable, "-X", "utf8", "giris.py"], cwd=klasor,
                           capture_output=True, timeout=60)
        hata = r.stderr.decode("utf-8")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Program başlatılamadı", hata)
        self.assertIn("Sıfıra Bölme Hatası", hata)
        self.assertNotIn("Traceback", hata)

    def test_komut_hatasi_iz_basmaz(self):
        hatali = []

        def yaz(m=""):
            hatali.append(m)
            if len(hatali) == 1:
                raise PermissionError(13, "izin yok")
        self.assertEqual(exe.kaynak_komutu([], yaz), 1)
        self.assertTrue(hatali[-1].startswith("[HATA] Beklenmeyen bir sorun oldu. İzin Hatası"))


class SekmeTerminaliTestleri(unittest.TestCase):
    """Her sekmenin terminalinin klasörü ve kabuk komutları ayrıdır."""

    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_oturum_")
        os.makedirs(os.path.join(self.klasor, "a"))
        os.makedirs(os.path.join(self.klasor, "b"))
        c = self.c = IDECore.__new__(IDECore)
        c.proje_dizini = self.klasor
        c._terminal_dizini = None
        c._terminal_dizinleri = {}
        c._kabuk_surecleri = {}

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    def test_cd_oturuma_ozel(self):
        c = self.c
        c._terminal_cd("cd a", oturum="tab_1")
        c._terminal_cd("cd b", oturum="tab_2")
        self.assertEqual(c._terminal_cwd("tab_1"), os.path.join(self.klasor, "a"))
        self.assertEqual(c._terminal_cwd("tab_2"), os.path.join(self.klasor, "b"))
        self.assertEqual(c._terminal_cwd("tab_3"), self.klasor)
        self.assertEqual(c._terminal_cwd(), self.klasor)

    def test_durdur_yalnizca_o_oturumun_komutlarini_oldurur(self):
        c = self.c
        olduruldu = []
        c._sureci_oldur = olduruldu.append

        class Surec:
            def poll(self):
                return None

        s1, s2 = Surec(), Surec()
        c._kabuk_surecleri.update({s1: "tab_1", s2: "tab_2"})
        self.assertTrue(c.kodu_durdur("tab_2", yalnizca_kabuk=True)["ok"])
        self.assertEqual(olduruldu, [s2])
        self.assertFalse(c.kodu_durdur("tab_9", yalnizca_kabuk=True)["ok"])


class _DerlemesizExeYap:
    """exe_yap'ı PyInstaller'a gelmeden durdurur: derleme öncesi denetimler
    ve uyarılar hızlıca sınanır."""

    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_exe_denetim_")
        self.addCleanup(shutil.rmtree, self.klasor, True)
        eski = exe.pyinstaller_hazirla
        exe.pyinstaller_hazirla = lambda *_a: False
        self.addCleanup(setattr, exe, "pyinstaller_hazirla", eski)

    def dosya(self, ad, icerik=""):
        yol = os.path.join(self.klasor, ad)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(icerik)
        return yol

    def calistir(self, kod, **ayarlar):
        ayar = exe.varsayilan_ayarlar()
        ayar.update(ayarlar)
        cikti = []
        exe.exe_yap(self.dosya("ana.trpy", kod), ayar, yaz=cikti.append)
        return cikti


class DerlemeOncesiDenetimTestleri(_DerlemesizExeYap, unittest.TestCase):
    def test_ayrilmis_windows_adi_degistirilir(self):
        cikti = self.calistir('yazdır(1)\n', ad="con")
        self.assertIn("con_program.exe", "\n".join(cikti))

    def test_eksik_dosya_uyarisi(self):
        self.dosya("sorular.txt", "soru")
        self.dosya("resimler/kedi.png", "x")
        kod = 'a = aç("sorular.txt")\nb = "resimler/kedi.png"\nc = "olmayan.txt"\n'
        uyarilar = [s for s in self.calistir(kod) if s.startswith("[UYARI]")]
        self.assertEqual(len(uyarilar), 2)
        self.assertIn("'sorular.txt'", uyarilar[0])
        self.assertIn('--dosya-ekle "sorular.txt"', uyarilar[0])
        self.assertIn("'resimler/kedi.png'", uyarilar[1])
        uyarilar = [s for s in self.calistir(kod, ekler=["sorular.txt", "resimler"])
                    if s.startswith("[UYARI]")]
        self.assertEqual(uyarilar, [])

    def test_goreli_kayit_yeri_kod_klasorune_gore(self):
        yakalanan = {}
        asil = exe._yazilabilir_mi

        def yakala(yol):
            yakalanan["yol"] = yol
            return asil(yol)
        exe._yazilabilir_mi = yakala
        self.addCleanup(setattr, exe, "_yazilabilir_mi", asil)
        self.calistir("yazdır(1)\n", kayit_yeri="Oyunlar")
        self.assertEqual(yakalanan["yol"], os.path.join(self.klasor, "Oyunlar", "ana.exe"))
        self.calistir("yazdır(1)\n", kayit_yeri="")
        self.assertEqual(yakalanan["yol"], os.path.join(self.klasor, "ana.exe"))

    def test_terminalsiz_girdi_uyarisi(self):
        kod = 'ad = girdi_al("Ad? ")\n'
        self.assertTrue(any("girdi_al" in s for s in self.calistir(kod, pencere="yok")))
        self.assertFalse(any("girdi_al" in s for s in self.calistir(kod, pencere="turkod")))

    def test_hatali_secenekler_derlemeden_once_soylenir(self):
        self.dosya("a.txt")
        self.assertIn("[HATA] Simge dosyası bulunamadı: yok.ico",
                      self.calistir("yazdır(1)\n", simge="yok.ico"))
        self.assertIn("[HATA] Simge bir .ico dosyası olmalı: a.txt",
                      self.calistir("yazdır(1)\n", simge="a.txt"))
        self.assertIn("[HATA] Eklenecek dosya bulunamadı: yok.png",
                      self.calistir("yazdır(1)\n", ekler=["yok.png"]))
        self.assertTrue(self.calistir("yazdır(1)\n", kayit_yeri=self.dosya("a.txt"))[0]
                        .startswith("[HATA] Kaydedileceği yer bir klasör olmalı"))
        cikti = self.calistir("eğer x\n")
        self.assertIn("[HATA] Kodda hata var; önce düzeltilmeli:", cikti)


class YardimciIslevTestleri(unittest.TestCase):
    def test_sondaki_ters_egik_cizgi_komut_satirini_bozmaz(self):
        """Paneldeki komut Windows komut satırında (IDE terminali cmd ile
        çalıştırır) aynı klasöre ayrıştırılmalı."""
        klasor = tempfile.mkdtemp(prefix="turkod_argv_")
        self.addCleanup(shutil.rmtree, klasor, True)
        betik = os.path.join(klasor, "argv_yaz.py")
        with open(betik, "w", encoding="utf-8") as f:
            f.write("import sys, json\nsys.stdout.buffer.write(json.dumps(sys.argv[1:]).encode())\n")
        ayar = exe.varsayilan_ayarlar()
        ayar.update(kayit_yeri="C:\\Oyun Klasörü\\", ad="Uzay Oyunu", kaynak=True)
        komut = exe.komut_metni(r"C:\Kod\a b.trpy", ayar)
        komut = komut.replace("turkod exe_yap", f'"{sys.executable}" "{betik}"', 1)
        r = subprocess.run(komut, shell=True, capture_output=True, timeout=60)
        import json
        dosya, geri, hatalar = exe.argumanlari_ayristir(json.loads(r.stdout.decode()))
        self.assertEqual(hatalar, [])
        self.assertEqual(dosya, r"C:\Kod\a b.trpy")
        self.assertEqual(geri["kayit_yeri"], "C:\\Oyun Klasörü\\")
        self.assertTrue(geri["kaynak"])

    def test_sonda_bekle_yalnizca_windows_konsolunda(self):
        ayar = exe.varsayilan_ayarlar()
        ayar.update(sonda_bekle=True)
        self.assertNotIn("--sonda-bekle", exe.komut_metni("a.trpy", ayar))
        ayar.update(pencere="konsol")
        self.assertIn("--sonda-bekle", exe.komut_metni("a.trpy", ayar))

    def test_yarim_kalan_derlemenin_gecici_klasoru_temizlenir(self):
        olu = subprocess.Popen([sys.executable, "-c", "pass"])
        olu.wait()
        sahipsiz = tempfile.mkdtemp(prefix=exe._GECICI_ONEKI)
        with open(os.path.join(sahipsiz, exe.calistirici.SAHIP_DOSYASI), "w") as f:
            f.write(str(olu.pid))
        canli = tempfile.mkdtemp(prefix=exe._GECICI_ONEKI)
        self.addCleanup(shutil.rmtree, canli, True)
        exe.calistirici.gecici_sahiplen(canli)
        # Adı benzeyen ama TürKod'un sahiplenmediği bir klasör (eskiden
        # "sahibi ölmüş" sayılıp siliniyordu).
        yabanci = tempfile.mkdtemp(prefix=exe._GECICI_ONEKI)
        self.addCleanup(shutil.rmtree, yabanci, True)
        with open(os.path.join(yabanci, "onemli.txt"), "w") as f:
            f.write("silinmemeli")
        exe._eski_exe_gecicilerini_temizle()
        self.assertFalse(os.path.exists(sahipsiz))
        self.assertTrue(os.path.exists(canli))
        self.assertTrue(os.path.exists(os.path.join(yabanci, "onemli.txt")))

    def test_yerine_koy_basarisizsa_eski_exe_kalir(self):
        klasor = tempfile.mkdtemp(prefix="turkod_koy_")
        self.addCleanup(shutil.rmtree, klasor, True)
        hedef, yeni = os.path.join(klasor, "o.exe"), os.path.join(klasor, "yeni.exe")
        for yol, icerik in ((hedef, b"ESKI"), (yeni, b"YENI")):
            with open(yol, "wb") as f:
                f.write(icerik)
        asil = exe.shutil.move

        def bozuk(*_a):
            raise OSError("disk dolu")
        exe.shutil.move = bozuk
        try:
            with self.assertRaises(OSError):
                exe._yerine_koy(yeni, hedef)
        finally:
            exe.shutil.move = asil
        with open(hedef, "rb") as f:
            self.assertEqual(f.read(), b"ESKI")
        exe._yerine_koy(yeni, hedef)
        with open(hedef, "rb") as f:
            self.assertEqual(f.read(), b"YENI")
        self.assertEqual(os.listdir(klasor), ["o.exe"])

    def test_yerine_koy_klasor_yarida_kalirsa_eskisi_geri_gelir(self):
        klasor = tempfile.mkdtemp(prefix="turkod_koy_")
        self.addCleanup(shutil.rmtree, klasor, True)
        hedef, yeni = os.path.join(klasor, "o"), os.path.join(klasor, "yeni")
        for yol, icerik in ((hedef, b"ESKI"), (yeni, b"YENI")):
            os.makedirs(yol)
            with open(os.path.join(yol, "o.exe"), "wb") as f:
                f.write(icerik)
        asil = exe.shutil.move

        def yarim(kaynak, varilan):
            # Sürücüler arası kopya yarıda kaldı (disk dolu).
            os.makedirs(varilan)
            with open(os.path.join(varilan, "yarim.dll"), "wb") as f:
                f.write(b"y")
            raise OSError("disk dolu")
        exe.shutil.move = yarim
        try:
            with self.assertRaises(OSError):
                exe._yerine_koy(yeni, hedef)
        finally:
            exe.shutil.move = asil
        self.assertEqual(os.listdir(hedef), ["o.exe"])
        with open(os.path.join(hedef, "o.exe"), "rb") as f:
            self.assertEqual(f.read(), b"ESKI")
        self.assertEqual(sorted(os.listdir(klasor)), ["o", "yeni"])


def _ileti_kutusunu_oku_ve_kapat(baslik, sure=90):
    """Başlığı verilen ileti kutusunun metnini döndürür ve kutuyu kapatır."""
    import ctypes
    import ctypes.wintypes as wt
    import time
    u = ctypes.windll.user32
    son = time.monotonic() + sure
    while time.monotonic() < son:
        hwnd = u.FindWindowW(None, baslik)
        if hwnd:
            metinler = []

            @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
            def cocuk(h, _):
                n = u.GetWindowTextLengthW(h)
                b = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, b, n + 1)
                metinler.append(b.value)
                return True
            u.EnumChildWindows(hwnd, cocuk, 0)
            u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return "\n".join(metinler)
        time.sleep(0.3)
    return None


@unittest.skipUnless(os.environ.get("TURKOD_EXE_TESTI") == "1" and sys.platform == "win32",
                     "gerçek EXE derlemesi uzun sürer (TURKOD_EXE_TESTI=1)")
class GercekExeTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="turkod_exe_testi_")
        self.addCleanup(shutil.rmtree, self.klasor, True)

    def dosya(self, ad, icerik):
        yol = os.path.join(self.klasor, ad)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(icerik)
        return yol

    def yap(self, dosya, **ayarlar):
        ayar = exe.varsayilan_ayarlar()
        ayar.update(ayarlar)
        cikti = []
        yol = exe.exe_yap(dosya, ayar, yaz=cikti.append)
        return yol, "\n".join(cikti)

    def test_yerel_modul_giris_ve_eklenen_dosyalar(self):
        """Kullanıcının giris.trpy modülü EXE'nin kendi dosyalarıyla çakışmaz;
        eklenen dosya ve klasörler EXE'de bulunur; geçici klasör kalmaz."""
        self.dosya("giris.trpy", 'fonksiyon selam():\n    döndür "giriş modülünden selam"\n')
        self.dosya("sorular.txt", "Başkent neresi?")
        self.dosya("resimler/bilgi.txt", "klasördeki dosya")
        ana = self.dosya("ana.trpy",
                         'içe_aktar giris\nyazdır(giris.selam())\n'
                         'ile aç("sorular.txt", kodlama="utf-8") olarak d:\n    yazdır(d.oku())\n'
                         'ile aç("resimler/bilgi.txt", kodlama="utf-8") olarak d:\n    yazdır(d.oku())\n')
        onceki = {a for a in os.listdir(tempfile.gettempdir()) if a.startswith(exe._GECICI_ONEKI)}
        yol, cikti = self.yap(ana, pencere="konsol", ekler=["sorular.txt", "resimler"])
        self.assertTrue(yol, cikti)
        self.assertNotIn("[UYARI]", cikti)
        r = subprocess.run([yol], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        sonuc = r.stdout.decode("utf-8")
        self.assertEqual(r.returncode, 0, sonuc)
        self.assertIn("giriş modülünden selam", sonuc)
        self.assertIn("Başkent neresi?", sonuc)
        self.assertIn("klasördeki dosya", sonuc)
        sonraki = {a for a in os.listdir(tempfile.gettempdir()) if a.startswith(exe._GECICI_ONEKI)}
        self.assertEqual(sonraki - onceki, set())

    def test_terminalsiz_girdi_turkce_ileti_kutusu(self):
        ana = self.dosya("soru.trpy", 'ad = girdi_al("Adın? ")\nyazdır(ad)\n')
        yol, cikti = self.yap(ana, pencere="yok")
        self.assertIn("[UYARI] Program girdi_al kullanıyor", cikti)
        surec = subprocess.Popen([yol])
        metin = _ileti_kutusunu_oku_ve_kapat("soru - Hata")
        self.assertEqual(surec.wait(timeout=60), 1)
        self.assertIsNotNone(metin)
        self.assertIn("Terminalsiz EXE'de girdi_al kullanılamaz", metin)
        self.assertNotIn("lost sys.stdin", metin)

    def test_basarisiz_derleme_eski_exeyi_bozmaz(self):
        ana = self.dosya("oyun.trpy", 'yazdır("yeni")\n')
        eski = os.path.join(self.klasor, "oyun.exe")
        eski_icerik = sahte_paket({exe.IMZA_DOSYASI: (exe.IMZA.encode(), b"x", 0)})
        with open(eski, "wb") as f:
            f.write(eski_icerik)
        with open(os.path.join(self.klasor, "bozuk.ico"), "wb") as f:
            f.write(b"bu bir simge degil")
        yol, cikti = self.yap(ana, simge="bozuk.ico")
        self.assertIsNone(yol)
        self.assertIn("[HATA] EXE oluşturulamadı", cikti)
        with open(eski, "rb") as f:
            self.assertEqual(f.read(), eski_icerik)
        self.assertEqual(sorted(os.listdir(self.klasor)), ["bozuk.ico", "oyun.exe", "oyun.trpy"])

    def test_klasorlu_exe_yeniden_yapilir_ve_terminal_kipi_calisir(self):
        ana = self.dosya("say.trpy", 'yazdır("bir")\n')
        yol, cikti = self.yap(ana, klasorlu=True, kaynak=True)
        self.assertTrue(yol, cikti)
        self.dosya("say.trpy", 'yazdır("iki")\n')
        yol2, cikti = self.yap(ana, klasorlu=True, kaynak=True)
        self.assertEqual(yol, yol2, cikti)
        self.assertEqual(sorted(os.listdir(self.klasor)), ["say", "say.trpy"])
        r = subprocess.run([yol2], capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
                           env=dict(os.environ, TURKOD_EXE_COCUK="1"))
        self.assertIn("iki", r.stdout.decode("utf-8"))
        self.assertEqual(exe.exe_kaynagi_oku(yol2), ("acik", 'yazdır("iki")\n'))

    def test_exe_calisir_ve_kaynagi_okunur(self):
        klasor = tempfile.mkdtemp(prefix="turkod_exe_testi_")
        self.addCleanup(shutil.rmtree, klasor, True)
        dosya = os.path.join(klasor, "selam.trpy")
        with open(dosya, "w", encoding="utf-8") as f:
            f.write('ad = girdi_al("Ad? ")\nyazdır(f"Merhaba {ad}!")\nyazdır([1][3])\n')
        ayar = exe.varsayilan_ayarlar()
        ayar.update(pencere="konsol", kaynak=True)
        yol = exe.exe_yap(dosya, ayar, yaz=lambda m="": None)
        self.assertTrue(yol and os.path.isfile(yol))
        r = subprocess.run([yol], input="Ece\n".encode("utf-8"), capture_output=True,
                           timeout=120)
        cikti = r.stdout.decode("utf-8")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Merhaba Ece!", cikti)
        self.assertIn("Liste İndeks Hatası", cikti)
        self.assertIn("Satır Numarası: 3", cikti)
        self.assertEqual(exe.exe_kaynagi_oku(yol)[0], "acik")


if __name__ == "__main__":
    unittest.main()
