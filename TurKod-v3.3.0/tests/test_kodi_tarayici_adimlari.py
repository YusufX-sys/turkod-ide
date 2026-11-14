"""Kodi'nin tarayıcıda adım adım iş yapması: sayfadaki bütün öğeleri görmesi,
geçersiz eylemi düzeltmesi, söz verdiği işi yapması, önceki adımların
sonuçlarını bilmesi (ağ kullanılmaz; yapay zekâ taklit edilir)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import kodi as kodi_bilgisi  # noqa: E402

DEEPSEEK = {"saglayici": "deepseek", "model": "deepseek-chat"}

# GitHub depo sayfasındaki gibi: "Releases" 47. öğe.
OGELER = [{"no": i, "tur": "a", "metin": f"bağlantı {i}"} for i in range(1, 61)]
OGELER[46] = {"no": 47, "tur": "a", "metin": "Releases"}
OGELER[16] = {"no": 17, "tur": "a", "metin": "8 Tags"}
BAGLAM = {"tarayici": {"acik": True, "url": "https://github.com/YusufX-sys/turkod-ide",
                       "baslik": "GitHub - YusufX-sys/turkod-ide", "ogeler": OGELER}}


def blok(*eylemler):
    return "```eylem\n" + "\n".join(json.dumps(e, ensure_ascii=False) for e in eylemler) + "\n```"


class BaglamTestleri(unittest.TestCase):
    def test_sayfadaki_butun_ogeler_gorunur(self):
        metin = kodi_bilgisi.soru_mesaji("Programın en son Release sürümü ne", BAGLAM)
        self.assertIn('47=a "Releases"', metin)
        self.assertIn('60=a "bağlantı 60"', metin)

    def test_son_islemler_baglamda(self):
        b = dict(BAGLAM, son_islemler=["tarayici tikla: \"Releases\" tıklandı",
                                       "tarayici kaydir: HATA: sayfa yok"])
        metin = kodi_bilgisi.soru_mesaji("devam et", b)
        self.assertIn("\"Releases\" tıklandı", metin)
        self.assertIn("HATA: sayfa yok", metin)


class DogrulamaTestleri(unittest.TestCase):
    def test_yazisiyla_tiklama(self):
        _, e = kodi_bilgisi.eylemleri_ayir(
            blok({"eylem": "tarayici", "islem": "tikla", "metin": "Releases"}), BAGLAM)
        self.assertEqual(e[0]["islem"], "tikla")
        self.assertEqual(e[0]["bul"], "Releases")
        self.assertNotIn("no", e[0])

    def test_adres_baska_alanda_gelse_de_acilir(self):
        # Gerçek model (gpt-oss) adresi "metin" alanına koydu; eylem atılıyor,
        # Kodi sayfayı hiç açamıyordu.
        _, e = kodi_bilgisi.eylemleri_ayir(blok(
            {"eylem": "tarayici", "islem": "ac", "metin": "https://github.com/YusufX-sys/turkod-ide"},
            {"eylem": "tarayici", "islem": "ac", "url": "turkod.dev"},
            {"eylem": "tarayici", "islem": "ara", "metin": "kaplumbağa çizimi"}), {})
        self.assertEqual([x.get("adres") or x.get("sorgu") for x in e],
                         ["https://github.com/YusufX-sys/turkod-ide", "turkod.dev", "kaplumbağa çizimi"])

    def test_duzeltme_notu_eksik_alani_soyler(self):
        self.assertIn('"adres"', kodi_bilgisi.eksik_alan_notu({"eylem": "tarayici", "islem": "ac"}))
        self.assertIn('"islem"', kodi_bilgisi.eksik_alan_notu({"eylem": "tarayici"}))
        self.assertIn('"sorgu"', kodi_bilgisi.eksik_alan_notu({"eylem": "tarayici", "islem": "ara"}))

    def test_tarayici_isinden_sonra_devam_edilir(self):
        # Tarayıcı işinden sonra varsayılan olarak devam edilir ("bir oyun
        # bulayım" deyip Google'ı açıp duruyordu); "devam": false durur.
        _, e = kodi_bilgisi.eylemleri_ayir(blok(
            {"eylem": "tarayici", "islem": "tikla", "no": 47},
            {"eylem": "tarayici", "islem": "kaydir", "yon": "asagi", "devam": False},
            {"eylem": "tarayici", "islem": "ac", "adres": "github.com"},
            {"eylem": "tarayici", "islem": "ac", "adres": "github.com/a/b/releases", "devam": True},
            {"eylem": "tarayici", "islem": "ara", "sorgu": "TürKod"}), BAGLAM)
        self.assertEqual([x.get("devam", False) for x in e], [True, False, True, True, True])

    def test_otomatik_adim_sinira_takilinca_uzun_bekler(self):
        self.assertGreater(kodi_bilgisi.bekleme_siniri(otomatik=True),
                           kodi_bilgisi.bekleme_siniri(otomatik=False))
        self.assertGreaterEqual(kodi_bilgisi.bekleme_siniri(otomatik=True), 60)

    def test_gecersiz_eylemler_bulunur(self):
        cevap = "Tıklıyorum!\n" + blok({"eylem": "tarayici"})
        self.assertEqual(kodi_bilgisi.gecersiz_eylemler(cevap, BAGLAM), [{"eylem": "tarayici"}])
        self.assertEqual(kodi_bilgisi.gecersiz_eylemler("Merhaba", BAGLAM), [])

    def test_sablon(self):
        # Yalnızca şablon (eylem bloğu) aranır; yazıdaki sözlere bakılmaz.
        self.assertTrue(kodi_bilgisi.eylem_sablonu_var("Tamam!\n" + blok({"eylem": "yok"})))
        self.assertTrue(kodi_bilgisi.eylem_sablonu_var('<eylem>{"eylem": "yok"}</eylem>'))
        self.assertFalse(kodi_bilgisi.eylem_sablonu_var("Releases sekmesine tıklıyorum!"))
        _, e = kodi_bilgisi.eylemleri_ayir(blok({"eylem": "yok"}), BAGLAM)
        self.assertEqual(e, [{"eylem": "yok"}])

    def test_arac_semasi_butun_alanlari_tanitir(self):
        # Model yalnızca şemadaki alanları dolduruyor: eskiden yalnızca "eylem"
        # vardı, tarayıcı işleri {"eylem": "tarayici"} diye eksik geliyordu.
        alanlar = kodi_bilgisi.ARACLAR[0]["function"]["parameters"]["properties"]
        for ad in ("eylem", "islem", "no", "metin", "adres", "sorgu", "yon", "devam",
                   "panel", "durum", "id", "ad", "sayfa", "not"):
            self.assertIn(ad, alanlar)
        self.assertIn("yok", alanlar["eylem"]["enum"])
        # Hiçbir alan zorunlu değil: Groq şemaya uymayan araç çağrısında bütün
        # isteği reddediyordu (HTTP 400 "missing properties: 'eylem'").
        self.assertNotIn("required", kodi_bilgisi.ARACLAR[0]["function"]["parameters"])

    def test_katalogda_kisayol_ve_eklenti_penceresi(self):
        # Kısayollar arayüzden gelir (uydurulmasın); "etkin" eklentinin
        # penceresinin açık olduğu anlamına gelmez, pencere "calistir" ile açılır.
        b = {"komutlar": [{"id": "view.keybindings", "ad": "Klavye Kısayolları…",
                           "kisayol": "Ctrl+K Ctrl+S"},
                          {"id": "view.settings", "ad": "Ayarlar"}],
             "eklentiler": [{"id": "karalama_defteri", "ad": "Karalama Defteri", "etkin": True,
                             "acilir": True}]}
        s = kodi_bilgisi.sabit_sistem_mesaji("3.3", b)
        self.assertIn("view.keybindings=Klavye Kısayolları… (Ctrl+K Ctrl+S)", s)
        self.assertIn("view.settings=Ayarlar\n", s)  # kısayolsuz komutta parantez yok
        self.assertIn("karalama_defteri=Karalama Defteri [penceresi var]", s)
        self.assertIn("calistir: [penceresi var]", s)
        self.assertIn("ezberden liste yazma", s)

    def test_sistem_mesaji_sablonu_anlatir(self):
        s = kodi_bilgisi.sabit_sistem_mesaji("3.3", BAGLAM, katalog=True)
        self.assertIn("ŞABLON", s)
        self.assertIn('{"eylem": "yok"}', s)
        self.assertIn('"metin": "<düğmenin yazısı>"', s)
        self.assertIn('{"eylem": "kilavuz", "bolum"', s)


class CekirdekTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"deepseek": "k"}
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _sor(self, cevaplar, soru="Aç bakalım"):
        cagrilar = []

        def sahte(kimlik, model, mesajlar, **kw):
            cagrilar.append(mesajlar)
            return {"cevap": cevaplar[min(len(cagrilar), len(cevaplar)) - 1], "dusunce": ""}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor(soru, baglam=BAGLAM)
        return r, cagrilar

    def test_gecersiz_eylem_bir_kez_duzeltilir(self):
        r, cagrilar = self._sor([
            "Tamam, Releases sekmesine tıklıyorum!\n" + blok({"eylem": "tarayici"}),
            "Tıklıyorum!\n" + blok({"eylem": "tarayici", "islem": "tikla", "no": 47}),
        ])
        self.assertEqual(len(cagrilar), 2)
        self.assertIn("uygulanamadı", json.dumps(cagrilar[1][-1], ensure_ascii=False))
        self.assertEqual(r["eylemler"][0]["no"], 47)
        # Geçmişte bozuk deneme değil, düzeltilmiş cevap kalır.
        self.assertEqual(len(self.c.kodi_gecmisi), 2)
        self.assertIn('"no": 47', self.c.kodi_gecmisi[-1]["content"])

    def test_soz_verip_yapmayan_cevap_tekrar_istenir(self):
        # Eylemsiz cevap: önce minik soruyla iş sözü var mı bakılır ("evet"),
        # sonra eylem bir kez daha istenir.
        r, cagrilar = self._sor([
            "GitHub sayfasında Releases sekmesini açıp bakayım.",
            "evet",
            "Açıyorum!\n" + blok({"eylem": "tarayici", "islem": "tikla", "no": 47}),
        ])
        self.assertEqual(len(cagrilar), 3)
        self.assertEqual(len(cagrilar[1]), 1)  # minik soru: geçmişsiz, tek mesaj
        self.assertIn("Releases sekmesini açıp bakayım", cagrilar[1][0]["content"])
        self.assertEqual(r["eylemler"][0]["islem"], "tikla")

    def test_duzeltme_de_olmazsa_hazir_kalip_yerine_durum_soylenir(self):
        r, cagrilar = self._sor([blok({"eylem": "tarayici"}), blok({"eylem": "tarayici"})])
        self.assertEqual(len(cagrilar), 2)
        self.assertNotIn("aradığım şeyi bulamadım", r["cevap"])
        self.assertTrue(r["cevap"].strip())

    def test_sablona_uyan_cevapta_tekrar_istenmez(self):
        r, cagrilar = self._sor(["Reponun 9 yıldızı var!\n" + blok({"eylem": "yok"})],
                                soru="Kaç yıldızı var")
        self.assertEqual(len(cagrilar), 1)
        self.assertEqual(r["cevap"], "Reponun 9 yıldızı var!")
        self.assertEqual(r["eylemler"], [])  # "yok" arayüze gitmez

    def test_sohbet_sorusunda_da_sablon_aranir(self):
        # Mesajın kelimelerine program bakmaz: eylemsiz cevapta yapay zekâya
        # minik bir soruyla iş sözü var mı diye sorulur. "hayır" ise koca
        # istek ikinci kez gönderilmez (eskiden her sohbet sorusu iki kat
        # token harcıyordu).
        from turkod_ide import kodi
        cagrilar = []

        def sahte(kimlik, model, mesajlar, **kw):
            cagrilar.append(kw.get("sistem"))
            if kw.get("sistem") == kodi.IS_VAADI_SISTEMI:
                return {"cevap": "Hayır", "dusunce": "minik"}
            return {"cevap": "Döngü, bir işi tekrar tekrar yapmaktır.", "dusunce": "asıl"}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Döngü nedir?")
        self.assertEqual(len(cagrilar), 2)
        self.assertEqual(cagrilar[1], kodi.IS_VAADI_SISTEMI)
        self.assertTrue(r["ok"])
        self.assertEqual(r["cevap"], "Döngü, bir işi tekrar tekrar yapmaktır.")
        self.assertEqual(r["dusunce"], "asıl")  # minik sorunun düşüncesi karışmaz
        self.assertEqual(len(self.c.kodi_gecmisi), 2)


if __name__ == "__main__":
    unittest.main()
