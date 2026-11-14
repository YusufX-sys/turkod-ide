"""Kodi (programdaki yardımcı robot) testleri. Ağ kullanılmaz."""
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
    from turkod_ide import kodi, kodi_kilavuz  # noqa: E402

DEEPSEEK = {"saglayici": "deepseek", "model": "deepseek-chat"}
GROQ = {"saglayici": "groq", "model": "qwen"}


class BilgiTestleri(unittest.TestCase):
    def test_kilavuz_kitaptan_uretilmis(self):
        basliklar = [b[0] for b in kodi_kilavuz.BOLUMLER]
        self.assertGreaterEqual(len(basliklar), 50)
        for gerekli in ("Ekranı kendine göre düzenle", "PDF dosyalarını okumak",
                        "Programını EXE yapmak", "Araç çubuğu"):
            self.assertIn(gerekli, basliklar)

    def test_kilavuz_bolumleri_basligiyla_bulunur(self):
        # Model bölümü başlığıyla ister (kelime puanlaması yok).
        def ilk(ad):
            return kodi.kilavuz_bolumleri([ad])[0][0].split(" (kitapta")[0]
        self.assertEqual(ilk("Programını EXE yapmak"), "Programını EXE yapmak")
        self.assertEqual(ilk("programını exe yapmak"), "Programını EXE yapmak")
        self.assertEqual(ilk("kesme noktaları"), "Hata ayıklayıcı: kesme noktaları")
        self.assertEqual(kodi.kilavuz_bolumleri(["böyle bir başlık yok"]), [])
        self.assertEqual(len(kodi.kilavuz_bolumleri(["Yerel model kurmak"] * 3)), 1)

    def test_baglam_siniri(self):
        basliklar = [b[0] for b in kodi_kilavuz.BOLUMLER][:10]
        toplam = sum(len(m) for _, m in kodi.kilavuz_bolumleri(basliklar))
        self.assertLessEqual(toplam, kodi.BAGLAM_SINIRI)

    def test_sistem_mesaji_temel_bilgiler(self):
        m = kodi.sistem_mesaji("Seni kim yaptı?", "3.2.0")
        for parca in ("Kodi", "Yusuf Tandoğan", "https://github.com/YusufX-sys/turkod-ide",
                      "yusuftndgn.2@gmail.com", "TürKod IDE 3.2.0", "MIT",
                      "TürKod ile Kodlama Macerası", '"sen" diye'):
            self.assertIn(parca, m)

    def test_dogal_turkce_kurallari(self):
        m = kodi.sistem_mesaji("Merhaba")
        self.assertIn("TÜRKÇEN", m)
        # İstek kipi örnekleri ve kaçınılacak resmî kalıplar.
        for parca in ("göresin", "yapasın", "deneyiversene", "yapalım", "gerçekleştirmek"):
            self.assertIn(parca, m)
        self.assertIn("kurasın", kodi.model_yok_mesaji())

    def test_kilavuz_basliklari_ve_istenen_bolum(self):
        # Sistem mesajında yalnızca başlıklar; bölüm, model isteyince gelir.
        m = kodi.sistem_mesaji("EXE nasıl yapılır?")
        self.assertIn("KILAVUZ BAŞLIKLARI:", m)
        self.assertIn("Programını EXE yapmak", m)
        self.assertNotIn("## Programını EXE yapmak", m)
        self.assertIn('{"eylem": "kilavuz"', m)
        s = kodi.soru_mesaji("EXE nasıl yapılır?", {},
                             kilavuz=kodi.kilavuz_bolumleri(["Programını EXE yapmak"]))
        self.assertIn("## Programını EXE yapmak", s)


class CekirdekTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"deepseek": "k", "groq": "g"}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_model_yoksa_dostca_uyari(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili") as s:
            r = self.c.kodi_sor("Merhaba!")
        self.assertFalse(r["ok"])
        self.assertTrue(r["model_yok"])
        self.assertIn("Kodi", r["hata"])
        s.assert_not_called()

    def test_kodi_gorevi_yoksa_sohbet_modeli(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "Merhaba!", "dusunce": ""}) as s:
            r = self.c.kodi_sor("Seni kim yaptı?")
        self.assertTrue(r["ok"], r)
        self.assertEqual(s.call_args.args[:2], ("deepseek", "deepseek-chat"))
        # Kodi'nin kimliği ve program bilgisi sistem mesajında.
        self.assertIn("Yusuf Tandoğan", s.call_args.kwargs["sistem"])

    def test_kodi_gorevi_ve_dusunme(self):
        self.c.ayarlar.ayarlar.update({"ai_gorev_atamalari": {"sohbet": DEEPSEEK, "kodi": GROQ},
                                       "kodi_dusunme": True, "ai_dusunme": False})
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "Tamam", "dusunce": "hmm"}) as s:
            r = self.c.kodi_sor("EXE nasıl yapılır?")
            self.assertEqual(s.call_args.args[:2], ("groq", "qwen"))
            self.assertTrue(s.call_args.kwargs["dusunme"])
            self.assertEqual(r["dusunce"], "hmm")
            # Balondaki düğme ayarı geçersiz kılar.
            self.c.kodi_sor("Bir soru daha", dusunme=False)
            self.assertFalse(s.call_args.kwargs["dusunme"])

    def test_gecmis_ai_paneline_karismaz(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        cevap = 'Cevap\n```eylem\n{"eylem": "yok"}\n```'
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": cevap, "dusunce": ""}) as s:
            self.c.kodi_sor("Birinci soru")
            self.c.kodi_sor("İkinci soru")
            # İkinci istekte ilk soru-cevap Kodi geçmişinden gelir.
            gecmis = s.call_args.args[2]
            # Geçmişte sorunun sade hâli; değişen bağlam yalnızca son mesajda.
            self.assertEqual([m["content"] for m in gecmis[:2]], ["Birinci soru", cevap])
            self.assertTrue(gecmis[2]["content"].endswith("İkinci soru"))
            # Sistem mesajı iki istekte birebir aynı (sağlayıcı önbelleğe alır).
            sistemler = [c.kwargs["sistem"] for c in s.call_args_list]
            self.assertEqual(sistemler[0], sistemler[1])
        self.assertEqual(self.c.ai_mesaj_gecmisi, [])
        self.assertEqual(len(self.c.kodi_gecmisi), 4)
        self.c.kodi_temizle()
        self.assertEqual(self.c.kodi_gecmisi, [])

    def test_kod_turkceye_cevrilir(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "Bak:\n```python\nprint('Selam')\n```",
                                      "dusunce": ""}):
            r = self.c.kodi_sor("Ekrana nasıl yazı yazarım?")
        self.assertIn("yazdır('Selam')", r["cevap"])

    def test_eylemler_ayiklanir_ve_kod_turkcelesir(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        cevap = ("Terminali açıyorum ve kodu yeni sekmeye yazıyorum!\n"
                 "```python\nfor i in range(3):\n    print(i)\n```\n"
                 "```eylem\n"
                 '{"eylem": "panel", "panel": "terminal", "durum": "ac"}\n'
                 '{"eylem": "kod_yaz", "hedef": "yeni_sekme", "ad": "sayac"}\n'
                 '{"eylem": "komut", "id": "os.system"}\n'
                 "```")
        baglam = {"sekmeler": ["oyun.trpy"], "aktif_sekme": "oyun.trpy",
                  "aktif_kod": "yazdır(1)", "dosyalar": ["oyun.trpy"],
                  "paneller": {"gezgin": True, "terminal": False}}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": cevap, "dusunce": ""}) as s:
            r = self.c.kodi_sor("Terminali aç ve sayaç yaz", baglam=baglam)
        # İlk çağrı Kodi'nin; ardından kodu arka planda AI Asistan yazar.
        sistem = s.call_args_list[0].kwargs["sistem"]
        son = s.call_args_list[0].args[2][-1]["content"]
        self.assertIn("run.run=Çalıştır", sistem)
        # Değişen bağlam sistem mesajında değil, son mesajda.
        self.assertNotIn("yazdır(1)", sistem)
        self.assertIn("Açık sekmeler: oyun.trpy", son)
        self.assertIn("yazdır(1)", son)
        self.assertTrue(son.endswith("KULLANICININ SORUSU: Terminali aç ve sayaç yaz"))
        self.assertEqual(self.c.kodi_gecmisi[0]["content"], "Terminali aç ve sayaç yaz")
        self.assertNotIn("```eylem", r["cevap"])
        # Yazılacak kod sohbette gösterilmez: izin kartına bağlanır, izin
        # verilince editöre yazılır.
        self.assertNotIn("```", r["cevap"])
        self.assertIn("için i aralık(3):", r["eylemler"][1]["kod"])
        self.assertEqual(r["eylemler"][0],
                         {"eylem": "panel", "panel": "terminal", "durum": "ac"})
        kod = r["eylemler"][1]
        self.assertEqual((kod["eylem"], kod["hedef"], kod["ad"]),
                         ("kod_yaz", "yeni_sekme", "sayac.trpy"))
        self.assertIn("yazdır(i)", kod["kod"])
        # Listede olmayan komut atılır.
        self.assertEqual(len(r["eylemler"]), 2)

    def test_kodsuz_kod_yaz_atilir(self):
        metin, eylemler = kodi.eylemleri_ayir(
            'Tamam\n<eylem>{"eylem": "kod_yaz"}</eylem>')
        self.assertEqual(metin, "Tamam")
        self.assertEqual(eylemler, [{"eylem": "kod_yaz", "hedef": "yeni_sekme"}])
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": 'Olmaz\n```eylem\n{"eylem": "kod_yaz"}\n```',
                                      "dusunce": ""}):
            r = self.c.kodi_sor("kod yaz")
        self.assertEqual(r["eylemler"], [])

    def test_satira_git_ve_ara(self):
        _, eylemler = kodi.eylemleri_ayir(
            '```eylem\n{"eylem": "satira_git", "satir": "12"}\n'
            '{"eylem": "satira_git", "satir": 0}\n'
            '{"eylem": "ara", "metin": "yazdır"}\n'
            '{"eylem": "ara", "metin": "  "}\n```')
        self.assertEqual(eylemler, [{"eylem": "satira_git", "satir": 12},
                                    {"eylem": "ara", "metin": "yazdır", "sira": 1}])
        self.assertIn('{"eylem": "satira_git", "satir"', kodi.sistem_mesaji("12. satıra git"))

    def test_kitap_ve_ayar_eylemleri(self):
        _, eylemler = kodi.eylemleri_ayir(
            "```eylem\n"
            '{"eylem": "kitap", "sayfa": "35"}\n'
            '{"eylem": "ayar", "ad": "tema", "deger": "açık"}\n'
            '{"eylem": "ayar", "ad": "tema", "deger": "Pembe"}\n'
            '{"eylem": "ayar", "ad": "yazi_boyutu", "deger": 50}\n'
            '{"eylem": "ayar", "ad": "ai_api_anahtarlari", "deger": "x"}\n'
            "```")
        self.assertEqual(eylemler, [
            {"eylem": "kitap", "sayfa": 35},
            {"eylem": "ayar", "ad": "tema", "deger": "Açık"},
            {"eylem": "ayar", "ad": "yazi_boyutu", "deger": 32},
        ])

    def test_kitap_sayfalari_ve_durum(self):
        baglam = {"imlec_satir": 5, "secili_kod": "yazdır(1)", "aktif_kod": "yazdır(x)",
                  "terminal": "NameError: x", "son_hata": "x tanımlı değil",
                  "sorunlar": ["Satır 3: ':' bekleniyor"]}
        m = kodi.sistem_mesaji("EXE nasıl yapılır?", baglam=baglam)
        self.assertIn("12. döngü: tekrar tekrar yapmak s.35", m)
        s = kodi.soru_mesaji("x", {}, kilavuz=kodi.kilavuz_bolumleri(["Programını EXE yapmak"]))
        self.assertRegex(s, r"## Programını EXE yapmak \(kitapta s\.\d+\)")
        # Bağlam, sorunun kelimelerine bakılmadan her istekte aynı yapıda gider.
        for soru in ("Programım neden hata veriyor?", "Nasılsın"):
            m = kodi.soru_mesaji(soru, baglam)
            for parca in ("İmleç 5. satırda", "seçtiği kod", "NameError: x",
                          "x tanımlı değil", "':' bekleniyor", "yazdır(x)"):
                self.assertIn(parca, m)
            # Soru başta ve sonda (uzun bağlamın içinde kaybolmasın).
            self.assertTrue(m.startswith("KULLANICININ SORUSU: " + soru))
            self.assertTrue(m.endswith("KULLANICININ SORUSU: " + soru))

    def test_bozuk_eylem_blogu(self):
        metin, eylemler = kodi.eylemleri_ayir(
            'Peki!\n```eylem\n[{"eylem": "panel", "panel": "ai", "durum": "kapat"}, '
            '{"eylem": "panel", "panel": "pencere"}]\n')
        self.assertEqual(metin, "Peki!")
        self.assertEqual(eylemler, [{"eylem": "panel", "panel": "ai", "durum": "kapat"}])

    def test_bos_soru(self):
        r = self.c.kodi_sor("   ")
        self.assertFalse(r["ok"])

    def test_kodi_gorevi_listede(self):
        from turkod_ide import yerel_modeller
        self.assertIn("kodi", yerel_modeller.GOREVLER)


class YonetimTestleri(unittest.TestCase):
    """Kodi programı yönetir: bütün komutlar, eklentiler, ayarlar, modeller."""

    BAGLAM = {
        "komutlar": [{"id": "run.exe", "ad": "EXE'ye Dönüştür…", "izinsiz": True},
                     {"id": "file.save", "ad": "Kaydet", "izinsiz": False}],
        "eklentiler": [{"id": "odak_zamanlayici", "ad": "Odak Zamanlayıcı", "etkin": False,
                        "acilir": False, "aciklama": "Pomodoro sayacı"}],
        "ayarlar": {"satir_numaralari": {"ad": "Satır numaraları", "tur": "bool", "deger": True},
                    "girinti_boyutu": {"ad": "Girinti genişliği", "tur": "sayi", "min": 2,
                                       "max": 8, "deger": 4}},
        "modeller": ["Groq • openai/gpt-oss-20b"],
        "gorev_atamalari": {"sohbet": "Groq • openai/gpt-oss-20b", "kodi": "Otomatik"},
        "yetkiler": {"ayar": True, "eklenti": False, "komut": True, "hep_sor": False},
    }

    def test_sistem_mesaji_listeleri_ve_yetkileri_icerir(self):
        m = kodi.sistem_mesaji("EXE panelini aç", baglam=self.BAGLAM)
        sabit = kodi.sabit_sistem_mesaji("3.2.0", self.BAGLAM)
        self.assertIn("run.exe=EXE'ye Dönüştür…", sabit)
        self.assertIn("odak_zamanlayici=Odak Zamanlayıcı", sabit)
        self.assertIn("satir_numaralari=Satır numaraları [true|false]", sabit)
        self.assertIn('{"eylem": "ayarlar_ac"', sabit)
        # Değerler, durumlar ve yetkiler sabit kısımda yok (önbellek bozulmasın).
        for parca in ("kapalı", "MODELLER: ", "YETKİ"):
            self.assertNotIn(parca, sabit)
        soru = kodi.soru_mesaji("EXE panelini aç", self.BAGLAM)
        self.assertIn("odak_zamanlayici kapalı", soru)
        self.assertIn("eklentileri yönetmek", soru)  # kapalı yetki söylenir
        # Ayar değerleri ve modeller kelimeye bakılmadan her istekte gider.
        self.assertIn("MODELLER: Groq • openai/gpt-oss-20b", soru)
        self.assertIn("satir_numaralari=True", soru)
        self.assertIn("run.exe=EXE'ye Dönüştür…", m)

    def test_yonetim_eylemleri_ayiklanir(self):
        cevap = ("Hemen!\n```eylem\n"
                 '{"eylem": "komut", "id": "run.exe"}\n'
                 '{"eylem": "komut", "id": "olmayan.komut"}\n'
                 '{"eylem": "eklenti", "id": "Odak Zamanlayıcı", "durum": "ac"}\n'
                 '{"eylem": "ayar", "ad": "satir_numaralari", "deger": false}\n'
                 '{"eylem": "ayar", "ad": "kodi_yetki_ayar", "deger": false}\n'
                 '{"eylem": "ayar", "ad": "ai_api_anahtarlari", "deger": {}}\n'
                 '{"eylem": "ayarlar_ac", "bolum": "kodi"}\n'
                 '{"eylem": "model_ata", "gorev": "kodi", "model": "otomatik"}\n'
                 "```")
        metin, eylemler = kodi.eylemleri_ayir(cevap, self.BAGLAM)
        self.assertEqual(metin, "Hemen!")
        self.assertEqual(eylemler, [
            {"eylem": "komut", "id": "run.exe", "etiket": "EXE'ye Dönüştür…"},
            {"eylem": "eklenti", "id": "odak_zamanlayici", "durum": "ac",
             "etiket": "Odak Zamanlayıcı"},
            {"eylem": "ayar", "ad": "satir_numaralari", "deger": False,
             "etiket": "Satır numaraları"},
            {"eylem": "ayarlar_ac", "bolum": "kodi", "etiket": "Kodi"},
            {"eylem": "model_ata", "gorev": "kodi", "model": "otomatik"},
        ])

    def test_baglamsiz_eski_komutlar_calisir(self):
        _, eylemler = kodi.eylemleri_ayir('```eylem\n{"eylem": "komut", "id": "run.exe"}\n```')
        self.assertEqual(eylemler[0]["id"], "run.exe")


if __name__ == "__main__":
    unittest.main()
