"""Hayalet kod (satır içi AI tamamlama) testleri. Ağ ve model kullanılmaz."""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import hayalet_tamamlama as h
    from turkod_ide.converter import python_kodu_turkceye_cevir, turkce_kodu_donustur


class KonumTestleri(unittest.TestCase):
    def test_oneri_konumu(self):
        self.assertTrue(h.oneri_uygun_mu("x = 1\n", ""))
        self.assertTrue(h.oneri_uygun_mu("yazdır(", ")\n"))
        self.assertTrue(h.oneri_uygun_mu("eğer x ", ""))
        # Kelime yazılırken normal tamamlama listesi çalışır.
        # Kelime ortası da uygun konum; yarım kelimeyi çekirdek ayrıca eler.
        self.assertTrue(h.oneri_uygun_mu("yazd", ""))
        # Satırın geri kalanında kod varsa öneri gösterilmez.
        self.assertFalse(h.oneri_uygun_mu("x = ", "5 + 3\n"))

    def test_kod_ozeti_amaci_tasir(self):
        kod = ("# Zar atma oyunu\nfonksiyon zar_at():\n    geç\n"
               "sınıf Oyuncu:\n    geç\n")
        ozet = h.kod_ozeti(kod, "zar.trpy")
        self.assertIn("zar.trpy", ozet)
        self.assertIn("Zar atma oyunu", ozet)
        self.assertIn("fonksiyon zar_at", ozet)
        self.assertIn("sınıf Oyuncu", ozet)

    def test_sohbet_istemi(self):
        sistem, kullanici = h.sohbet_mesajlari("a = 1\n", "\nyazdır(a)", "x.trpy", False)
        self.assertIn("TürKod", sistem)
        self.assertIn("tek satır", sistem)
        self.assertIn(f"a = 1\n{h.IMLEC}\nyazdır(a)", kullanici)


class TemizlemeTestleri(unittest.TestCase):
    def test_cit_ve_dusunce_atilir(self):
        ham = "<think>plan</think>```türkod\nb = 2\n```"
        self.assertEqual(h.temizle(ham, "a = 1\n", ""), "b = 2")

    def test_tekrar_eden_satir_basi_atilir(self):
        self.assertEqual(h.temizle("yazdır(isim)", "yazdır(", ")"), "isim")

    def test_sonraki_kod_tekrar_edilmez(self):
        ham = "çiftler.sona_ekle(s)\nyazdır(çiftler)"
        sonuc = h.temizle(ham, "için s içinde x:\n    ", "\nyazdır(çiftler)\n")
        self.assertEqual(sonuc, "çiftler.sona_ekle(s)")

    def test_tek_satir_kipi(self):
        self.assertEqual(h.temizle("a\nb\nc", "x = ", "", cok_satir=False), "a")

    def test_girinti_kaymasi_duzeltilir(self):
        ham = "if n <= 1:\n         return 1\n     else:\n         return 2"
        sonuc = h.temizle(ham, "fonksiyon f(n):\n    ", "", cevirici=python_kodu_turkceye_cevir,
                          python_cikti=True)
        self.assertEqual(sonuc, "eğer n <= 1:\n        döndür 1\n    değilse:\n        döndür 2")

    def test_cop_ve_dongu_kesilir(self):
        ham = "yazdır(x)\n!yazdır(x)\n!"
        self.assertEqual(h.temizle(ham, "", ""), "yazdır(x)")
        ham = "a = 1\nb = 2\nb = 2\nb = 2\nb = 2"
        # Blok açılmıyorsa VS Code gibi tek satır gösterilir.
        self.assertEqual(h.temizle(ham, "", ""), "a = 1")
        self.assertEqual(h.temizle("isim) # !! anlamsız", "yazdır(", ""), "isim)")

    def test_bulut_python_yazarsa_cevrilir(self):
        sonuc = h.temizle("print(a + b)", "a = 1\nb = 2\n", "",
                          cevirici=python_kodu_turkceye_cevir)
        self.assertEqual(sonuc, "yazdır(a + b)")

    def test_tum_python_parcalari_cevrilir(self):
        cev = python_kodu_turkceye_cevir
        ornekler = {
            "len(sayilar))": "uzunluk(sayilar))",
            "x.append(5)": "x.sona_ekle(5)",
            "isim.upper())": "isim.büyük_harf())",
            "random.randint(1, 6)": "rastgele.tamsayı(1, 6)",
            # Karışık (bir kısmı zaten TürKod) öneri de çevrilir.
            "yazdır(x)  ve  print(len(x))": "yazdır(x)  ve  yazdır(uzunluk(x))",
        }
        for ham, beklenen in ornekler.items():
            self.assertEqual(h.temizle(ham, "x = 1\n", "", cevirici=cev), beklenen, ham)

    def test_yeni_satirla_baslayan_oneri_atilmaz(self):
        sonuc = h.temizle("\nexcept ValueError:\n    print('Sayı girin')", "x = 1\n", "",
                          cevirici=python_kodu_turkceye_cevir)
        self.assertEqual(sonuc, "hata_yakala DeğerHatası:\n    yazdır('Sayı girin')")

    def test_kullanicinin_adlari_korunur(self):
        once = "total = 0\nnumbers = [1, 2]\nfor n in numbers:\n    "
        sonuc = h.temizle("total += n\n    print(total, len(numbers))", once, "",
                          cevirici=python_kodu_turkceye_cevir)
        self.assertEqual(sonuc, "total += n\n    yazdır(total, uzunluk(numbers))")

    def test_python_onek_imleci_korur(self):
        once = "için i içinde aralık(3):\n    eğer i "
        py = h.python_onu(once, turkce_kodu_donustur)
        self.assertTrue(py.endswith("\n    if i "), py)
        self.assertTrue(py.startswith("for i in range(3):"))


class SatirSonuTestleri(unittest.TestCase):
    def ek(self, once, sonra=""):
        return h.yeni_satir_eki(once, sonra, turkce_kodu_donustur)

    def test_tamamlanmis_satirdan_sonra_alt_satira_gecilir(self):
        self.assertEqual(self.ek("x = 5"), "\n")
        self.assertEqual(self.ek("    yazdır(isim)"), "\n    ")
        self.assertEqual(self.ek("# Not hesabı"), "\n")

    def test_blok_acan_satirdan_sonra_girinti_artar(self):
        self.assertEqual(self.ek("fonksiyon f(x):"), "\n    ")
        self.assertEqual(self.ek("    için i içinde aralık(3):"), "\n        ")

    def test_dondur_kir_sonrasi_girinti_azalir(self):
        self.assertEqual(self.ek("    döndür x * 2"), "\n")
        self.assertEqual(self.ek("        kır"), "\n    ")

    def test_bitmemis_satir_ayni_satirda_surer(self):
        for once in ("eğer x > 5", "yazd", "x = a +", "sayılar = [1, 2,", "yazdır(isim"):
            self.assertEqual(self.ek(once), "", once)
        # Satırın sağında kod varsa alt satıra geçilmez.
        self.assertEqual(self.ek("yazdır(isim", ")"), "")

    def test_kelime_ortasi(self):
        self.assertTrue(h.kelime_ortasi_mi("sayılar = [1]\nyazd"))
        self.assertFalse(h.kelime_ortasi_mi("isim = 1\nyazdır(isim"))
        self.assertFalse(h.kelime_ortasi_mi("x = 5"))
        self.assertFalse(h.kelime_ortasi_mi("eğer x > 5:"))

    def test_blok_kirpma(self):
        # Blok gövdesinde: dış düzeye dönen satırlar alınmaz.
        govde = h.blok_kirp(['döndür "BA"', '    değilse_eğer puan >= 60:'],
                            "    değilse_eğer puan >= 70:\n        ")
        self.assertEqual(govde, ['döndür "BA"'])
        # Öneri blok açıyorsa gövdesiyle birlikte gelir; yarım son satır atılır.
        acan = h.blok_kirp([":", "    yazdır(x)", "    yazdır(x, (y"], "eğer x > 5")
        self.assertEqual(acan, [":", "    yazdır(x)"])

    def test_satir_ici_gurultu_yorumu_atilir(self):
        self.assertEqual(h.temizle("kare(5)  # Output: 25", "x\n", ""), "kare(5)")
        self.assertEqual(h.temizle('yazdır("# değil")', "x\n", ""), 'yazdır("# değil")')
        self.assertEqual(h.temizle("yazdır(i)\n```", "için i içinde x:\n    ", ""),
                         "yazdır(i)")


YEREL_M = {"saglayici": "yerel", "model": "m.gguf"}


class CekirdekTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_kapaliyken_istek_yok(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {}
        with mock.patch("turkod_ide.yerel_modeller.tamamla") as t:
            self.assertEqual(self.c.ai_hayalet_tamamla("x = ", "")["oneri"], "")
        t.assert_not_called()

    def test_yerel_python_uzerinden(self):
        self.c.ayarlar.ayarlar.update({"ai_tamamlama_cok_satir": True,
                                       "ai_gorev_atamalari": {"tamamlama": YEREL_M}})
        with mock.patch("turkod_ide.yerel_modeller.tamamla",
                        return_value={"ok": True, "tamamlama": "print(toplam)"}) as t:
            r = self.c.ai_hayalet_tamamla("toplam = 5\n", "", "a.trpy")
        self.assertEqual(r["oneri"], "yazdır(toplam)")
        # Model Python önek görür (TürKod anahtar kelimeleri çevrilmiş).
        self.assertNotIn("yazdır", t.call_args.args[1])

    def test_satir_sonunda_oneri_alt_satirdan_baslar(self):
        self.c.ayarlar.ayarlar.update({"ai_tamamlama_cok_satir": True,
                                       "ai_gorev_atamalari": {"tamamlama": YEREL_M}})
        with mock.patch("turkod_ide.yerel_modeller.tamamla",
                        return_value={"ok": True, "tamamlama": "print(i)"}) as t:
            r = self.c.ai_hayalet_tamamla("için i içinde aralık(3):", "", "a.trpy")
            # Aynı konum ikinci kez istenince model çalışmaz (önbellek).
            r2 = self.c.ai_hayalet_tamamla("için i içinde aralık(3):", "", "a.trpy")
        self.assertEqual(r["oneri"], "\n    yazdır(i)")
        self.assertEqual(r2["oneri"], r["oneri"])
        self.assertEqual(t.call_count, 1)
        # Model imleci yeni satırın girintisinde görür.
        self.assertTrue(t.call_args.args[1].endswith(":\n    "))

    def test_yarim_kelimede_model_cagrilmaz(self):
        self.c.ayarlar.ayarlar.update({"ai_gorev_atamalari": {"tamamlama": YEREL_M}})
        with mock.patch("turkod_ide.yerel_modeller.tamamla") as t:
            r = self.c.ai_hayalet_tamamla("x = 1\nyazd", "", "a.trpy")
        self.assertEqual(r["oneri"], "")
        t.assert_not_called()

    def test_api_kaynagi(self):
        self.c.ayarlar.ayarlar.update({"ai_gorev_atamalari": {
                                           "tamamlama": {"saglayici": "deepseek",
                                                         "model": "deepseek-chat"}},
                                       "ai_api_anahtarlari": {"deepseek": "k"}})
        with mock.patch("turkod_ide.ai.sohbet", return_value="```\nb = 2\n```") as s:
            r = self.c.ai_hayalet_tamamla("a = 1\n", "", "a.trpy")
        self.assertEqual(r["oneri"], "b = 2")
        self.assertEqual(s.call_args.args[:2], ("deepseek", "deepseek-chat"))
        self.assertEqual(s.call_args.kwargs["anahtar"], "k")
        # Sohbet geçmişine karışmaz.
        self.assertEqual(self.c.ai_mesaj_gecmisi, [])


class BulutGorevTestleri(CekirdekTestleri):
    def test_gorev_kapaliysa_istek_gitmez(self):
        self.c.ayarlar.ayarlar.update({
            "ai_api_anahtarlari": {"deepseek": "k"},
            "ai_gorev_atamalari": {"sohbet": {"saglayici": "deepseek", "model": "deepseek-chat"}}})
        self.assertTrue(self.c.ai_hazir_mi("sohbet")[0])
        hazir, hata = self.c.ai_hazir_mi("hata_aciklama")
        self.assertFalse(hazir)
        self.assertIn("Hata açıklama", hata)
        with mock.patch("turkod_ide.ai.sohbet") as s:
            r = self.c.ai_hata_acikla("x", "NameError")
        self.assertFalse(r["ok"])
        s.assert_not_called()

    def test_yerel_model_anahtarsiz_hazir(self):
        self.c.ayarlar.ayarlar.update({"ai_gorev_atamalari": {"aciklama": YEREL_M}})
        self.assertTrue(self.c.ai_hazir_mi("aciklama")[0])

    def test_her_gorev_kendi_saglayicisiyla(self):
        self.c.ayarlar.ayarlar.update({
            "ai_api_anahtarlari": {"deepseek": "k1", "groq": "k2"},
            "ai_gorev_atamalari": {
                "sohbet": {"saglayici": "deepseek", "model": "deepseek-chat"},
                "aciklama": {"saglayici": "groq", "model": "llama-3.3-70b-versatile"}}})
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "tamam", "dusunce": ""}) as s:
            r1 = self.c.ai_sor("merhaba")
            r2 = self.c.ai_kodu_acikla("x = 1")
        self.assertEqual(s.call_args_list[0].args[:2], ("deepseek", "deepseek-chat"))
        self.assertEqual(s.call_args_list[0].kwargs["anahtar"], "k1")
        self.assertEqual(s.call_args_list[1].args[:2], ("groq", "llama-3.3-70b-versatile"))
        self.assertEqual(s.call_args_list[1].kwargs["anahtar"], "k2")
        self.assertEqual((r1["kaynak_model"], r2["kaynak_model"]),
                         ("deepseek-chat", "llama-3.3-70b-versatile"))

    def test_eski_ayarlar_atamaya_tasinir(self):
        a = self.c.ayarlar.ayarlar
        a.update({"ai_gorev_atamalari": None, "ai_bulut_modelleri": None,
                  "ai_aktif": True, "ai_saglayici": "deepseek", "ai_model": "deepseek-chat",
                  "ai_bulut_gorevleri": ["sohbet", "aciklama"],
                  "yerel_ai_gorevleri": {"aciklama": "m.gguf", "tamamlama": "m.gguf"},
                  "ai_tamamlama_acik": True, "ai_tamamlama_kaynagi": "yerel"})
        self.assertEqual(self.c.ai_gorev_atamalari(), {
            "sohbet": {"saglayici": "deepseek", "model": "deepseek-chat"},
            "aciklama": YEREL_M, "tamamlama": YEREL_M})
        self.assertEqual(self.c.ai_bulut_modelleri(),
                         [{"saglayici": "deepseek", "model": "deepseek-chat"}])
        with contextlib.redirect_stdout(io.StringIO()):
            self.c._atamalari_tasi()
        self.assertIsInstance(a["ai_gorev_atamalari"], dict)

    def test_birden_fazla_saglayici_ayri_ayri_guncellenir(self):
        self.c.ayarlar.ayarlar.update({"ai_saglayici": "groq",
                                       "ai_api_anahtarlari": {"groq": "k1", "deepseek": "k2"}})
        with mock.patch("turkod_ide.ai.modelleri_guncelle",
                        return_value={"ok": True, "canli": True}) as g:
            r = self.c.modelleri_guncelle("deepseek", katalog=False)
        self.assertEqual(g.call_args.args[:2], ("deepseek", "k2"))
        self.assertFalse(g.call_args.kwargs["katalog"])
        self.assertEqual(r["saglayici"], "deepseek")

    def test_baglanti_kesilince_modelleri_ve_gorevleri_kalkar(self):
        # Ayarlar her yazımda diskle birleştirilir: kurulum da diske yazılır.
        with contextlib.redirect_stdout(io.StringIO()):
            for k, v in {"ai_api_anahtarlari": {"groq": "k1", "deepseek": "k2"},
                         "ai_bulut_modelleri": [{"saglayici": "groq", "model": "g"},
                                                {"saglayici": "deepseek", "model": "d"}],
                         "ai_gorev_atamalari": {
                             "sohbet": {"saglayici": "groq", "model": "g"},
                             "aciklama": {"saglayici": "deepseek", "model": "d"},
                             "tamamlama": YEREL_M}}.items():
                self.c.ayarlar.set(k, v)
            self.assertTrue(self.c.ai_baglanti_kes("groq")["ok"])
        self.assertEqual(self.c.ayarlar.get("ai_api_anahtarlari"), {"deepseek": "k2"})
        self.assertEqual(self.c.ai_bulut_modelleri(), [{"saglayici": "deepseek", "model": "d"}])
        self.assertEqual(sorted(self.c.ai_gorev_atamalari()), ["aciklama", "tamamlama"])

    def test_yerel_model_silinince_atama_kalkar(self):
        self.c.ayarlar.ayarlar.update({"ai_gorev_atamalari": {
            "aciklama": YEREL_M, "sohbet": {"saglayici": "groq", "model": "x"}}})
        with mock.patch("turkod_ide.yerel_modeller.model_sil", return_value={"ok": True}):
            self.c.yerel_ai_model_sil("m.gguf")
        self.assertEqual(list(self.c.ai_gorev_atamalari()), ["sohbet"])


class SimgeTestleri(unittest.TestCase):
    def test_simgelerde_tum_boyutlar_var(self):
        from PIL import Image
        for ad in ("editor-logo.ico", "terminal-logo.ico"):
            with Image.open(os.path.join(KOK, "turkod_ide", ad)) as im:
                boyutlar = {w for w, _ in im.ico.sizes()}
            self.assertTrue({16, 20, 24, 32, 48, 256} <= boyutlar, (ad, boyutlar))


if __name__ == "__main__":
    unittest.main()
