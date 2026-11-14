"""Kodi'nin API yükünü azaltan parçalar: yerel komut çözücü, önbelleğe uygun
istek, sessiz yeniden deneme, hız sınırında bekleme (ağ kullanılmaz)."""
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
    from turkod_ide import ai, kodi_yerel  # noqa: E402
    from turkod_ide.ai import AIIstekHatasi  # noqa: E402

DEEPSEEK = {"saglayici": "deepseek", "model": "deepseek-chat"}
# İş isteğinde cevap şablonla (eylem bloğuyla) biter.
SABLONLU = "Tamam!\n```eylem\n{\"eylem\": \"yok\"}\n```"

BAGLAM = {
    "komutlar": [
        {"id": "run.exe", "ad": "EXE'ye Dönüştür…", "izinsiz": True},
        {"id": "view.keybindings", "ad": "Klavye Kısayolları…", "izinsiz": True},
        {"id": "view.settings", "ad": "Ayarlar", "izinsiz": True},
        {"id": "learn.book", "ad": "TürKod ile Kodlama Macerası (Kitap)", "izinsiz": True},
        {"id": "tools.snippets", "ad": "Kod Parçacıkları…", "izinsiz": True},
        {"id": "run.run", "ad": "Çalıştır", "izinsiz": False},
        {"id": "file.save", "ad": "Kaydet", "izinsiz": False},
    ],
    "eklentiler": [
        {"id": "parcaciklar", "ad": "Kod Parçacıkları", "etkin": False, "acilir": True},
        {"id": "odak_zamanlayici", "ad": "Odak Zamanlayıcı", "etkin": False, "acilir": False},
        {"id": "karalama_defteri", "ad": "Karalama Defteri", "etkin": False, "acilir": True},
    ],
    "ayarlar": {
        "tema": {"ad": "Tema", "tur": "secim", "deger": "Modern Koyu",
                 "secenekler": ["Modern Koyu", "Koyu", "Açık", "Yüksek Kontrast"]},
        "yazi_boyutu": {"ad": "Editör yazı boyutu", "tur": "sayi", "deger": 14, "min": 8,
                        "max": 32},
        "minimap": {"ad": "Mini harita", "tur": "bool", "deger": False},
        "satir_numaralari": {"ad": "Satır numaraları", "tur": "bool", "deger": True},
    },
}


def _coz(m):
    r = kodi_yerel.coz(m, BAGLAM)
    return r["eylemler"][0] if r else None


class YerelCozucuTestleri(unittest.TestCase):
    def test_acik_komutlar_yerelde_cozulur(self):
        beklenen = {
            "Kod Parçacıkları eklentisini aktif et":
                {"eylem": "eklenti", "id": "parcaciklar", "durum": "ac"},
            "Kodi, terminali aç": {"eylem": "panel", "panel": "terminal", "durum": "ac"},
            "gezgini kapat": {"eylem": "panel", "panel": "gezgin", "durum": "kapat"},
            "EXE'ye dönüştürme panelini aç": {"eylem": "komut", "id": "run.exe"},
            "kısayolları göster": {"eylem": "komut", "id": "view.keybindings"},
            "kitabı aç": {"eylem": "komut", "id": "learn.book"},
            "Ayarlarda Kodi bölümünü aç": {"eylem": "ayarlar_ac", "bolum": "kodi"},
            "temayı açık yap": {"eylem": "ayar", "ad": "tema", "deger": "Açık"},
            "yazıyı büyüt": {"eylem": "ayar", "ad": "yazi_boyutu", "deger": 16},
            "mini haritayı kapat": {"eylem": "ayar", "ad": "minimap", "deger": False},
            "karalama defterini aç":
                {"eylem": "eklenti", "id": "karalama_defteri", "durum": "calistir"},
            "Odak Zamanlayıcıyı devre dışı bırak":
                {"eylem": "eklenti", "id": "odak_zamanlayici", "durum": "kapat"},
        }
        for mesaj, eylem in beklenen.items():
            with self.subTest(mesaj=mesaj):
                g = _coz(mesaj)
                self.assertIsNotNone(g)
                self.assertEqual({k: g[k] for k in eylem}, eylem)

    def test_sekme_ve_dosya(self):
        b = dict(BAGLAM, sekmeler=["merhaba.trpy", "kodi_kodu.trpy"],
                 dosyalar=["oyun.trpy", "notlar.md", "resimler/", "araclar/sayilar.trpy"])
        beklenen = {
            "merhaba.trpy sekmesine geç": {"eylem": "sekme", "ad": "merhaba.trpy"},
            "merhaba sekmesine geç": {"eylem": "sekme", "ad": "merhaba.trpy"},
            "notlar.md dosyasını aç": {"eylem": "dosya_ac", "dosya": "notlar.md"},
            "sayilar.trpy aç": {"eylem": "dosya_ac", "dosya": "araclar/sayilar.trpy"},
        }
        for mesaj, eylem in beklenen.items():
            with self.subTest(mesaj=mesaj):
                self.assertEqual(kodi_yerel.coz(mesaj, b)["eylemler"][0], eylem)
        for mesaj in ("merhaba nedir", "sekmeyi kapat", "olmayan.trpy dosyasını aç"):
            with self.subTest(mesaj=mesaj):
                self.assertIsNone(kodi_yerel.coz(mesaj, b))

    def test_kod_parcaciklari_komut_degil_eklenti(self):
        # Aynı adlı komut da var; eklenti (etkinleştirip açar) seçilir.
        self.assertEqual(_coz("kod parçacıklarını aç")["eylem"], "eklenti")

    def test_emin_olmadigi_yerde_karismaz(self):
        for mesaj in ("Terminal nasıl açılır?", "terminali aç ve sayaç yaz", "EXE nedir?",
                      "Kod Parçacıkları ne işe yarar?", "bana bir oyun yaz", "kodumu çalıştır",
                      "kodumu açıklar mısın", "tema açık mı?", "Merhaba Kodi", "dosyayı kaydet",
                      "kitapta döngüler nerede?", "bu kodu aç", "kodi aç",
                      "terminali aç, sonra kodu çalıştır", "temayı değiştir"):
            with self.subTest(mesaj=mesaj):
                self.assertIsNone(kodi_yerel.coz(mesaj, BAGLAM))

    def test_cevap_kodi_dilinde(self):
        r = kodi_yerel.coz("Kod Parçacıkları eklentisini aktif et", BAGLAM)
        self.assertIn("Kod Parçacıkları", r["cevap"])
        self.assertIn("etkinleştiriyorum", r["cevap"])


class CekirdekTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"deepseek": "k"}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_model_yoksa_hazir_kisa_is_yapilir(self):
        # Yalnızca hiç yapay zekâ bağlı değilken: API'ye gidilmez, iş yapılır.
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili") as s:
            r = self.c.kodi_sor("terminali aç", baglam=BAGLAM)
            r2 = self.c.kodi_sor("Döngü nedir?", baglam=BAGLAM)
        s.assert_not_called()
        self.assertTrue(r["ok"])
        self.assertTrue(r["yerel"])
        self.assertEqual(r["eylemler"], [{"eylem": "panel", "panel": "terminal", "durum": "ac"}])
        # Hazır iş değilse Kodi yapay zekâ gerektiğini söyler.
        self.assertFalse(r2["ok"])
        self.assertTrue(r2["model_yok"])

    def test_model_yoksa_yarim_is_ve_devam_yok(self):
        # Yapay zekâ olmadan birden çok işli istek hiç ele alınmaz (yarım iş
        # yapılmaz); hiçbir hazır işte "devam" olmaz.
        self.assertIsNone(kodi_yerel.coz("Google'da TürKod github ara ve ilk sonuca tıkla", {}))
        for mesaj in ("google'ı aç", "Google'da kedi resimleri ara", "github sayfasını aç"):
            with self.subTest(mesaj=mesaj):
                self.assertNotIn("devam", kodi_yerel.coz(mesaj, {})["eylemler"][0])

    def test_yapay_zeka_bagliyken_hazir_cozucu_asla_cagrilmaz(self):
        # Yapay zekâ bağlıyken hazır çözücü hiç çağrılmamalı (çağrılırsa test
        # kırılır): istek bütünüyle yapay zekâya gider.
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.kodi_yerel.coz",
                        side_effect=AssertionError("hazır çözücü çağrıldı")) as coz,                 mock.patch("turkod_ide.ai.sohbet_ayrintili",
                           return_value={"cevap": SABLONLU, "dusunce": ""}) as s,                 contextlib.redirect_stdout(io.StringIO()):
            for mesaj in ("terminali aç", "google'ı aç", "temayı açık yap",
                          "Tarayıcıda bu projenin github reposunu açar mısın"):
                r = self.c.kodi_sor(mesaj, baglam=BAGLAM)
                self.assertTrue(r["ok"], r)
                self.assertNotIn("yerel", r)
        coz.assert_not_called()
        self.assertEqual(s.call_count, 4)

    def test_yapay_zeka_bagliyken_hazir_kalip_kullanilmaz(self):
        # "tarayıcı" kelimesi geçiyor diye yalnızca tarayıcı açılmamalı: istek
        # bütünüyle yapay zekâya gider (repoyu da açsın).
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        for mesaj in ("Tarayıcıda bu projenin github reposunu açar mısın",
                      "terminali aç"):
            with self.subTest(mesaj=mesaj), mock.patch(
                    "turkod_ide.ai.sohbet_ayrintili",
                    return_value={"cevap": "Hemen açıyorum!\n```eylem\n{\"eylem\": \"yok\"}\n```",
                                  "dusunce": ""}) as s:
                r = self.c.kodi_sor(mesaj, baglam=BAGLAM)
            s.assert_called_once()
            self.assertTrue(r["ok"], r)
            self.assertNotIn("yerel", r)

    def test_cok_uzun_istek_sessizce_kisaltilip_yeniden_denenir(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        self.c.kodi_gecmisi[:] = [{"role": "user", "content": "eski"},
                                  {"role": "assistant", "content": "eski cevap"}]
        cagrilar = []

        def sahte(kimlik, model, mesajlar, **kw):
            cagrilar.append(list(mesajlar))
            if len(cagrilar) == 1:
                raise AIIstekHatasi("İstek çok uzun.", tur="cok_uzun")
            return {"cevap": SABLONLU, "dusunce": ""}

        baglam = dict(BAGLAM, aktif_kod="yazdır(1)\n" * 400)
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Kodumdaki hatayı bulur musun?", baglam=baglam)
        self.assertTrue(r["ok"])
        self.assertEqual(r["cevap"], "Tamam!")
        self.assertEqual(len(cagrilar), 2)
        # İkinci deneme geçmişsiz ve daha kısa.
        self.assertEqual(len(cagrilar[1]), 1)
        self.assertLess(len(cagrilar[1][0]["content"]), len(cagrilar[0][-1]["content"]))
        self.assertEqual([m["content"] for m in self.c.kodi_gecmisi][-2:],
                         ["Kodumdaki hatayı bulur musun?", SABLONLU])

    def test_sinir_hatasi_kodi_diliyle(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        side_effect=AIIstekHatasi("Kullanım limiti doldu.", tur="sinir",
                                                  bekle=20.2)):
            r = self.c.kodi_sor("Döngü nedir?")
        self.assertFalse(r["ok"])
        self.assertIn("21 saniye sonra", r["hata"])
        self.assertNotIn("motor", r["hata"])

    def test_her_istekte_katalog_ve_arac_gider(self):
        # Mesajın kelimelerine bakılmaz: bilgi sorusu da iş isteği de aynı
        # sistem mesajıyla ve "eylem" aracıyla gider.
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        self.c.ayarlar.ayarlar["ai_max_token"] = 4096
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": SABLONLU, "dusunce": ""}) as s,                 contextlib.redirect_stdout(io.StringIO()):
            self.c.kodi_sor("Değişken nedir?", baglam=BAGLAM)
            bilgi = s.call_args.kwargs
            self.c.kodi_sor("EXE panelini ve kısayolları göster lütfen", baglam=BAGLAM)
            is_ = s.call_args.kwargs
        self.assertEqual(bilgi["sistem"], is_["sistem"])
        self.assertIn("KOMUTLAR:", bilgi["sistem"])
        self.assertIn("KILAVUZ BAŞLIKLARI:", bilgi["sistem"])
        self.assertTrue(bilgi["araclar"])
        self.assertEqual(bilgi["max_token"], 2048)  # daha uzunu kesilmez, devamı istenir
        self.assertEqual(bilgi["en_uzun_bekleme"], 40)

    def test_gecmis_kisa_ve_cevaplar_kirpilir(self):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": DEEPSEEK}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "x" * 5000, "dusunce": ""}) as s, \
                contextlib.redirect_stdout(io.StringIO()):
            for i in range(6):
                self.c.kodi_sor(f"Soru {i}")
        self.assertLessEqual(len(s.call_args.args[2]), 7)  # 6 geçmiş + yeni soru
        self.assertTrue(all(len(m["content"]) <= 1200 for m in self.c.kodi_gecmisi))


class HizSiniriTestleri(unittest.TestCase):
    def _yanit(self, kod, basliklar=None, govde=None):
        y = mock.Mock(status_code=kod, headers=basliklar or {})
        y.json.return_value = govde or {}
        y.text = ""
        return y

    def test_bekleme_suresi_okunur(self):
        self.assertEqual(ai.bekleme_suresi(self._yanit(429, {"retry-after": "3"})), 3.0)
        self.assertAlmostEqual(
            ai.bekleme_suresi(self._yanit(429, {"x-ratelimit-reset-tokens": "1m2.5s"})), 62.5)
        self.assertAlmostEqual(ai.bekleme_suresi(self._yanit(
            429, govde={"error": {"message": "Rate limit reached. Please try again in 7.66s."}})),
            7.66)
        self.assertIsNone(ai.bekleme_suresi(self._yanit(429)))

    def test_kisa_beklemede_sessizce_yeniden_dener(self):
        sinir = self._yanit(429, {"retry-after": "0.1"},
                            {"error": {"message": "rate limit"}})
        tamam = self._yanit(200, govde={"choices": [{"message": {"content": "Selam!"}}],
                                        "usage": {"prompt_tokens": 100,
                                                  "prompt_tokens_details": {"cached_tokens": 80}}})
        with mock.patch("requests.post", side_effect=[sinir, tamam]) as post, \
                mock.patch("time.sleep"):
            r = ai.sohbet_ayrintili("groq", "openai/gpt-oss-20b",
                                    [{"role": "user", "content": "Merhaba"}], anahtar="k")
        self.assertEqual(r["cevap"], "Selam!")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(r["kullanim"]["prompt_tokens_details"]["cached_tokens"], 80)

    def test_uzun_beklemede_hata_turu_ve_suresi_iletilir(self):
        sinir = self._yanit(429, {"retry-after": "45"}, {"error": {"message": "rate limit"}})
        with mock.patch("requests.post", return_value=sinir), mock.patch("time.sleep") as uyku:
            with self.assertRaises(AIIstekHatasi) as h:
                ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}], anahtar="k")
        uyku.assert_not_called()
        self.assertEqual((h.exception.tur, h.exception.bekle), ("sinir", 45.0))

    def test_token_payi_yetmezse_once_beklenir(self):
        y = self._yanit(200, {"x-ratelimit-remaining-tokens": "500",
                              "x-ratelimit-limit-tokens": "8000",
                              "x-ratelimit-reset-tokens": "30s"})
        ai.token_payini_kaydet("groq", "deneme-model", y)
        with mock.patch("time.sleep") as uyku:
            # 4250 token gerekiyor: eksik 3750 / 7500 dolacak pay -> ~15 sn.
            ai.token_payini_bekle("groq", "deneme-model", 4250, en_uzun=40)
            self.assertAlmostEqual(uyku.call_args.args[0], 15.3, delta=0.5)
            uyku.reset_mock()
            ai.token_payini_bekle("groq", "deneme-model", 400, en_uzun=40)  # yeter
            uyku.assert_not_called()
            ai.token_payini_bekle("groq", "deneme-model", 4250, en_uzun=5)  # çok uzun
            uyku.assert_not_called()

    def test_413_cok_uzun_sayilir(self):
        y = self._yanit(413, govde={"error": {"message": "Request too large for model"}})
        with mock.patch("requests.post", return_value=y):
            with self.assertRaises(AIIstekHatasi) as h:
                ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}], anahtar="k")
        self.assertEqual(h.exception.tur, "cok_uzun")


if __name__ == "__main__":
    unittest.main()
