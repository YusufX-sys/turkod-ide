"""Kodi "Hadi tarayıcıyı açalım!" deyip hiçbir şey yapmıyordu: kök nedenler.

1. Model eylemsiz (düz yazı) cevap verince düzeltme turu da düz yazıyla
   dönebiliyordu; artık o turda araç çağrısı zorunludur.
2. Sağlayıcının reddettiği araç çağrısı atılıp modele "tarayıcı aracın yok,
   düz metinle cevap ver" deniyordu; artık çağrıdaki iş kurtarılır.
3. Bir düşünme ayarı reddedilince hepsi atılıyordu (Qwen düşünmeye başlıyordu).
4. Geçmişe giren uzun cevabın sonundaki eylem bloğu kesiliyordu.
"""
import contextlib
import json
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from turkod_ide import ai  # noqa: E402

GROQ = {"saglayici": "groq", "model": "qwen/qwen3.8-27b"}


def _yanit(kod, govde):
    y = mock.Mock(status_code=kod, headers={})
    y.json.return_value = govde
    y.text = ""
    return y


class SaglayiciTestleri(unittest.TestCase):
    def test_reddedilen_eylem_cagrisi_kurtarilir(self):
        hata = _yanit(400, {"error": {
            "message": "tool call validation failed: parameters for tool eylem did not match schema",
            "code": "tool_use_failed",
            "failed_generation": '{"name": "eylem", "arguments": {"eylem": "tarayici", '
                                 '"islem": "ac", "adres": "https://www.miniclip.com"}}'}})
        with mock.patch("requests.post", side_effect=[hata]) as post:
            r = ai.sohbet_ayrintili("groq", "qwen/qwen3.8-27b",
                                    [{"role": "user", "content": "oyun aç"}], anahtar="k",
                                    araclar=[{"type": "function", "function": {"name": "eylem"}}])
        self.assertEqual(post.call_count, 1)
        self.assertIn('"adres": "https://www.miniclip.com"', r["cevap"])
        self.assertIn("```eylem", r["cevap"])

    def test_yerlesik_tarayici_araci_eyleme_cevrilir(self):
        uretilen = ('<|channel|>commentary to=browser.search <|constrain|>json<|message|>'
                    '{"query": "çocuklar için tarayıcı oyunu"}')
        self.assertEqual(ai.basarisiz_cagri_eylemleri(uretilen),
                         [{"eylem": "tarayici", "islem": "ara",
                           "sorgu": "çocuklar için tarayıcı oyunu"}])
        self.assertEqual(ai.basarisiz_cagri_eylemleri(
            '{"name": "browser.open", "arguments": "{\\"url\\": \\"https://poki.com\\"}"}'),
            [{"eylem": "tarayici", "islem": "ac", "adres": "https://poki.com"}])
        self.assertEqual(ai.basarisiz_cagri_eylemleri("düz yazı"), [])

    def test_uyari_tarayiciyi_yasaklamaz(self):
        hata = _yanit(400, {"error": {"message": "Tool choice is none, but model called a tool",
                                      "code": "tool_use_failed"}})
        tamam = _yanit(200, {"choices": [{"message": {"content": "Tamam"}}]})
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            ai.sohbet_ayrintili("groq", "openai/gpt-oss-20b", [{"role": "user", "content": "a"}],
                                sistem="Sen Kodi'sin.", anahtar="k",
                                araclar=[{"type": "function", "function": {"name": "eylem"}}])
        sistem = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertNotIn("aracın yok", sistem)
        self.assertIn('"eylem" aracını {"eylem": "tarayici"', sistem)

    def test_zorunlu_cagri_ve_desteklenmezse_serbest(self):
        hata = _yanit(400, {"error": {"message": "Tool choice is required, but model did not call "
                                                 "a tool", "code": "tool_use_failed",
                                      "failed_generation": "Hadi açalım!"}})
        tamam = _yanit(200, {"choices": [{"message": {"content": "Tamam"}}]})
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            r = ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}], anahtar="k",
                                    araclar=[{"type": "function", "function": {"name": "eylem"}}],
                                    arac_zorunlu=True)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["tool_choice"], "auto")
        self.assertEqual(r["cevap"], "Tamam")
        self.assertNotIn("ÖNEMLİ", post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_yalnizca_reddedilen_dusunme_ayari_atilir_ve_hatirlanir(self):
        ai._DESTEKSIZ_PARAMLAR.clear()
        self.addCleanup(ai._DESTEKSIZ_PARAMLAR.clear)
        hata = _yanit(400, {"error": {"message": "property 'chat_template_kwargs' is unsupported"}})
        tamam = _yanit(200, {"choices": [{"message": {"content": "Tamam"}}]})
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            ai.sohbet_ayrintili("groq", "qwen/qwen3.8-27b", [{"role": "user", "content": "a"}],
                                anahtar="k", dusunme=False)
        govde = post.call_args.kwargs["json"]
        self.assertNotIn("chat_template_kwargs", govde)
        self.assertEqual(govde.get("reasoning_effort"), "none")
        # Sonraki istekte reddedilen ayar hiç gönderilmez (tek istek).
        with mock.patch("requests.post", side_effect=[tamam]) as post:
            ai.sohbet_ayrintili("groq", "qwen/qwen3.8-27b", [{"role": "user", "content": "a"}],
                                anahtar="k", dusunme=False)
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("chat_template_kwargs", post.call_args.kwargs["json"])


class KodiTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"groq": "g"}
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"kodi": GROQ}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_eylemsiz_cevapta_ikinci_tur_eylem_zorunlu(self):
        cevaplar = [
            {"cevap": "Hadi, tarayıcıyı açıp eğlenceli bir oyun bulalım! 🎮", "dusunce": ""},
            {"cevap": "evet", "dusunce": ""},  # minik soru: iş sözü var
            {"cevap": '```eylem\n{"eylem": "tarayici", "islem": "ara", "sorgu": "oyun"}\n```',
             "dusunce": ""},
        ]
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=cevaplar) as s, \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Tarayıcıdan bir oyun aç")
        self.assertFalse(s.call_args_list[0].kwargs.get("arac_zorunlu"))
        self.assertFalse(s.call_args_list[1].kwargs.get("araclar"))  # minik soru araçsız
        self.assertTrue(s.call_args_list[2].kwargs["arac_zorunlu"])
        self.assertEqual([e["islem"] for e in r["eylemler"]], ["ara"])
        # Yalnızca eylemi gönderen ikinci turda ilk cevabın yazısı söylenir.
        self.assertIn("oyun bulalım", r["cevap"])
        # Geçmişte tek soru-cevap; cevapta eylem de var.
        self.assertEqual(len(self.c.kodi_gecmisi), 2)
        self.assertIn("```eylem", self.c.kodi_gecmisi[1]["content"])

    def test_ikinci_tur_hata_verirse_ilk_cevap_ve_gecmis_kalir(self):
        from turkod_ide.ide_core import AIHatasi
        ilk = {"cevap": "Bunu bilmiyorum.", "dusunce": ""}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        side_effect=[ilk, {"cevap": "evet", "dusunce": ""},
                                     ai.AIIstekHatasi("olmadı")]), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Bir soru")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cevap"], "Bunu bilmiyorum.")
        self.assertEqual(len(self.c.kodi_gecmisi), 2)
        self.assertTrue(AIHatasi)

    def test_tarayici_adiminda_asil_istek_unutulmaz(self):
        # Geçmişte yalnızca son iki tur durur; üçüncü adımda asıl istek
        # eskiden modele hiç gitmiyordu.
        sorular = []

        def sahte(kimlik, model, mesajlar, **kw):
            sorular.append(mesajlar[-1]["content"])
            return {"cevap": 'Tamam\n```eylem\n{"eylem": "yok"}\n```', "dusunce": ""}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            self.c.kodi_sor("Tarayıcıdan bir oyun aç")
            for _ in range(3):
                self.c.kodi_sor("Sayfa açıldı, isteğime devam et.", otomatik=True)
            self.c.kodi_sor("Akıl oyunu olsun")
            self.c.kodi_sor("Sayfa açıldı, isteğime devam et.", otomatik=True)
        self.assertNotIn("Asıl isteğim", sorular[0])
        self.assertIn("Asıl isteğim: «Tarayıcıdan bir oyun aç»", sorular[3])
        self.assertIn("«Tarayıcıdan bir oyun aç» → «Akıl oyunu olsun»", sorular[5])
        self.c.kodi_temizle()
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            self.c.kodi_sor("Sayfa açıldı, isteğime devam et.", otomatik=True)
        self.assertNotIn("Asıl isteğim", sorular[-1])  # yeni sohbet eskiyi taşımaz

    def _otomatik_adim(self, mini_cevap):
        from turkod_ide import kodi
        cagrilar = []

        def sahte(kimlik, model, mesajlar, **kw):
            cagrilar.append(kw.get("sistem"))
            if kw.get("sistem") == kodi.HEDEF_SISTEMI:
                return {"cevap": mini_cevap, "dusunce": ""}
            return {"cevap": 'Tıklıyorum\n```eylem\n{"eylem": "tarayici", "islem": "tikla", '
                             '"no": 2}\n```', "dusunce": ""}

        self.c._kodi_istekler = ["Tarayıcıdan bir oyun aç"]
        baglam = {"tarayici": {"url": "https://poki.com/tr/g/flag-paint", "baslik": "Flag Paint",
                               "ogeler": [{"no": 2, "tur": "a", "metin": "Sudoku"}]},
                  "son_islemler": ['tarayici tikla: "Flag Paint" tıklandı']}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Sayfa açıldı, isteğime devam et.", baglam=baglam, otomatik=True)
        return r, cagrilar

    def test_istek_yerine_geldiyse_kodi_durur(self):
        from turkod_ide import kodi
        r, cagrilar = self._otomatik_adim("Evet\nFlag Paint oyunun açıldı, iyi eğlenceler!")
        self.assertEqual(cagrilar, [kodi.HEDEF_SISTEMI])  # koca istek gitmedi
        self.assertEqual(r["cevap"], "Flag Paint oyunun açıldı, iyi eğlenceler!")
        self.assertEqual(r["eylemler"], [])
        self.assertIn('"eylem": "yok"', self.c.kodi_gecmisi[-1]["content"])

    def test_onceki_istegin_dusuncesi_ve_modeli_sizmaz(self):
        # Sunucunun iş parçacığı havuzunda önceki (ilgisiz) isteğin düşüncesi
        # ve modeli "istek yerine geldi" cevabına sızıyordu.
        self.c._ai_dusunce.deger = "ESKİ DÜŞÜNCE"
        self.c._ai_kullanilan.deger = ("openai", "eski-model")
        r, _ = self._otomatik_adim("Evet\nOyunun açıldı!")
        self.assertEqual(r["cevap"], "Oyunun açıldı!")
        self.assertEqual(r["dusunce"], "")
        self.assertEqual(r["kaynak_model"], GROQ["model"])

    def test_istek_yerine_gelmediyse_adim_atilir(self):
        from turkod_ide import kodi
        r, cagrilar = self._otomatik_adim("hayır")
        self.assertEqual(cagrilar[0], kodi.HEDEF_SISTEMI)
        self.assertEqual(len(cagrilar), 2)
        self.assertEqual(r["eylemler"][0]["islem"], "tikla")

    def test_hedef_karari_okunur(self):
        from turkod_ide import kodi
        self.assertEqual(kodi.hedef_karari("evet\nOyunun açıldı!"), (True, "Oyunun açıldı!"))
        self.assertEqual(kodi.hedef_karari("Evet. Oyunun açıldı!"), (True, "Oyunun açıldı!"))
        self.assertEqual(kodi.hedef_karari("hayır"), (False, ""))
        self.assertEqual(kodi.hedef_karari("⚠️ Yanıt token sınırına takıldı"), (False, ""))

    def test_gecmiste_eylem_blogu_kesilmez(self):
        from turkod_ide.ide_core import IDECore
        uzun = "a" * 900 + '\n```eylem\n{"eylem": "tarayici", "islem": "ac", "adres": "x.com"}\n```'
        kirpilmis = IDECore._gecmis_cevabi(uzun, 600)
        self.assertTrue(kirpilmis.endswith("```"))
        self.assertIn('"adres": "x.com"', kirpilmis)
        self.assertLess(len(kirpilmis), 700)
        self.assertEqual(IDECore._gecmis_cevabi("kısa", 600), "kısa")


class YedekModelTestleri(unittest.TestCase):
    """Kullanım hakkı dolan model beklenmez; istek bağlı başka modele gider."""

    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar.update({
            "ai_api_anahtarlari": {"groq": "g"},
            "ai_gorev_atamalari": {"kodi": GROQ, "sohbet": GROQ},
            "ai_bulut_modelleri": [GROQ, {"saglayici": "groq", "model": "openai/gpt-oss-20b"},
                                   {"saglayici": "groq", "model": "whisper-large-v3"}],
        })
        ai._TOKEN_PAYI.clear()
        self.addCleanup(ai._TOKEN_PAYI.clear)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _sor(self, davranis):
        modeller = []

        def sahte(kimlik, model, mesajlar, **kw):
            modeller.append(model)
            return davranis(model)

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.ai_prompt_gonder("Merhaba", gorev="sohbet")
        return r, modeller

    def test_gunluk_hakki_dolunca_yedek_model_cevaplar(self):
        def davranis(model):
            if model == "qwen/qwen3.8-27b":
                raise ai.AIIstekHatasi("Kullanım limiti doldu.", tur="sinir", bekle=2070)
            return {"cevap": "Selam!", "dusunce": ""}

        r, modeller = self._sor(davranis)
        self.assertTrue(r["ok"], r)
        self.assertEqual(modeller, ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"])
        self.assertEqual(r["kaynak_model"], "openai/gpt-oss-20b")
        # Hakkı dolan model bir sonraki istekte hiç denenmez (boşuna beklenmez).
        r, modeller = self._sor(davranis)
        self.assertEqual(modeller, ["openai/gpt-oss-20b"])
        self.assertNotIn("whisper-large-v3", modeller)

    def test_hepsi_doluysa_en_kisa_bekleme_soylenir(self):
        def davranis(model):
            bekle = 2070 if model == "qwen/qwen3.8-27b" else 95
            raise ai.AIIstekHatasi("Kullanım limiti doldu.", tur="sinir", bekle=bekle)

        r, modeller = self._sor(davranis)
        self.assertFalse(r["ok"])
        self.assertIn("qwen/qwen3.8-27b", modeller)
        self.assertIn("openai/gpt-oss-20b", modeller)
        from turkod_ide import kodi
        mesaj = kodi.hata_mesaji("x", "sinir", 95)
        self.assertIn("96 saniye", mesaj)

    def test_secili_modelin_hatasi_yedege_gecmeden_soylenir(self):
        def davranis(model):
            raise ai.AIIstekHatasi("API anahtarı geçersiz", tur="anahtar")

        r, modeller = self._sor(davranis)
        self.assertFalse(r["ok"])
        self.assertEqual(modeller, ["qwen/qwen3.8-27b"])

    def test_sunucusu_kapanan_model_yerine_yedek(self):
        # Kaggle / Colab oturumu kapanınca adres ölür: Kodi yedek modelle sürer.
        def davranis(model):
            if model == "qwen/qwen3.8-27b":
                raise ai.AIIstekHatasi("Bağlantı hatası!", tur="baglanti")
            return {"cevap": "Selam!", "dusunce": ""}

        r, modeller = self._sor(davranis)
        self.assertTrue(r["ok"], r)
        self.assertEqual(modeller, ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"])
        r, modeller = self._sor(davranis)
        self.assertEqual(modeller, ["openai/gpt-oss-20b"])  # 2 dk denenmez

    def test_tek_model_ulasilamazsa_gercek_hata_soylenir(self):
        self.c.ayarlar.ayarlar["ai_bulut_modelleri"] = [GROQ]
        with mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}):
            def davranis(model):
                raise ai.AIIstekHatasi("Bağlantı hatası!", tur="baglanti")

            for _ in range(2):
                r, modeller = self._sor(davranis)
                self.assertEqual(modeller, ["qwen/qwen3.8-27b"])
                self.assertIn("Bağlantı hatası", r["hata"])

    def test_sunucu_hatasi_baglanti_sayilir(self):
        y = _yanit(502, {"error": {"message": "Bad gateway"}})
        with mock.patch("requests.post", return_value=y):
            with self.assertRaises(ai.AIIstekHatasi) as h:
                ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}], anahtar="k")
        self.assertEqual(h.exception.tur, "baglanti")

    def test_dakikalik_payi_yetmeyen_model_yerine_bos_olan_once(self):
        import time
        # Seçili modelin dakikalık payı neredeyse bitik, 40 sn'de dolacak.
        ai._TOKEN_PAYI[("groq", "qwen/qwen3.8-27b")] = (100.0, 8000.0, time.monotonic() + 40)
        r, modeller = self._sor(lambda m: {"cevap": "Selam!", "dusunce": ""})
        self.assertTrue(r["ok"], r)
        self.assertEqual(modeller, ["openai/gpt-oss-20b"])

    def test_duzeltme_turu_basarisizsa_kaynak_ilk_cevabin_modeli(self):
        # Düzeltme turu hata verince kaynak, denenen modelde kalıyordu.
        def sahte(kimlik, model, mesajlar, **kw):
            if model == "qwen/qwen3.8-27b":
                raise ai.AIIstekHatasi("Kullanım limiti doldu.", tur="sinir", bekle=2070)
            if kw.get("arac_zorunlu"):
                raise ai.AIIstekHatasi("olmadı")
            if not kw.get("araclar"):
                return {"cevap": "evet", "dusunce": ""}  # minik soru
            return {"cevap": "Bunu bilmiyorum.", "dusunce": ""}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Bir soru")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cevap"], "Bunu bilmiyorum.")
        self.assertEqual(r["kaynak_model"], "openai/gpt-oss-20b")


PROGRAM ="\n".join(f"print({i})" for i in range(20))


class UzunCevapVeKodTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar.update({"ai_api_anahtarlari": {"groq": "g"},
                                       "ai_gorev_atamalari": {"kodi": GROQ, "sohbet": GROQ},
                                       "ai_bulut_modelleri": [GROQ]})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _sor(self, cevaplar, soru="Bana bir program yaz"):
        cagrilar = []

        def sahte(kimlik, model, mesajlar, **kw):
            cagrilar.append(mesajlar)
            return cevaplar[min(len(cagrilar), len(cevaplar)) - 1]

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor(soru, baglam={"sekmeler": ["a.trpy"]})
        return r, cagrilar

    KODI_KOD_ISTER = {"cevap": 'Hemen AI Asistan\'a yazdırıyorum!\n```eylem\n{"eylem": "kod_yaz", '
                               '"istek": "0dan 19a kadar sayıları yazdıran program", '
                               '"hedef": "yeni_sekme"}\n```', "dusunce": "kodi"}

    def test_kesilen_cevabin_devami_alinir(self):
        # Eskiden 1000 token'da kesiliyor, kod Python olarak yarıda kalıyordu.
        bas = "Hazır!\n```python\n" + "\n".join(f"print({i})" for i in range(10))
        devam = "```python\nprint(9)\n" + "\n".join(f"print({i})" for i in range(10, 20)) + "\n```"
        r, cagrilar = self._sor([self.KODI_KOD_ISTER,
                                 {"cevap": bas, "dusunce": "", "kesildi": True},
                                 {"cevap": devam, "dusunce": ""}])
        self.assertEqual(len(cagrilar), 3)  # Kodi + AI Asistan (kesildi) + devamı
        self.assertEqual(cagrilar[2][-2], {"role": "assistant", "content": bas})
        self.assertEqual(cagrilar[2][-1]["content"], ai.DEVAM_ISTEMI)
        kod = r["eylemler"][0]["kod"]
        self.assertEqual(kod, "\n".join(f"yazdır({i})" for i in range(20)))  # tekrar yok
        self.assertNotIn("```", r["cevap"])
        self.assertEqual(len(self.c.kodi_gecmisi), 2)  # devam istekleri geçmişe girmez

    def test_kodu_ai_asistan_yazar_kodinin_kodu_kullanilmaz(self):
        # Kodi'nin modeli program yazarken uydurma TürKod üretebiliyordu
        # (`içeri_aktar kaplumbağa`). Kodu AI Paneli'nin yönergesiyle AI
        # Asistan yazar; Kodi'nin kendi kodu yalnızca yedektir.
        uydurma = ("Çiziyorum!\n```python\niçeri_aktar kaplumbağa\nkaplumbağa.kalem.renk = \"kırmızı\"\n"
                   "```\n```eylem\n{\"eylem\": \"kod_yaz\", \"istek\": \"kaplumbağa ile yıldız\"}\n```")
        dogru = "Al:\n```python\nimport turtle\nfor _ in range(5):\n    turtle.forward(100)\n```"
        r, cagrilar = self._sor([{"cevap": uydurma, "dusunce": "kodi"},
                                 {"cevap": dogru, "dusunce": "ai"}])
        self.assertEqual(len(cagrilar), 2)
        # AI Asistan'a giden istek: Kodi'nin isteği, kullanıcının sözü, geçmişsiz.
        self.assertEqual(len(cagrilar[1]), 1)
        self.assertIn("İSTEK: kaplumbağa ile yıldız", cagrilar[1][0]["content"])
        self.assertIn("KULLANICININ SÖZÜ: Bana bir program yaz", cagrilar[1][0]["content"])
        e = r["eylemler"][0]
        self.assertEqual(e["yazan"], "AI Asistan")
        self.assertIn("içe_aktar kaplumbağa", e["kod"])
        self.assertNotIn("içeri_aktar", e["kod"])
        self.assertEqual(r["cevap"], "Çiziyorum!")  # Kodi'nin uydurma kodu sohbette de yok
        self.assertEqual(r["dusunce"], "kodi")  # AI Asistan'ın düşüncesi karışmaz

    def test_hatali_kod_ai_asistana_duzelttirilir(self):
        bozuk = "```python\nfor i in range(3)\n    print(i)\n```"
        duzgun = "```python\nfor i in range(3):\n    print(i)\n```"
        r, cagrilar = self._sor([self.KODI_KOD_ISTER, {"cevap": bozuk, "dusunce": ""},
                                 {"cevap": duzgun, "dusunce": ""}])
        self.assertEqual(len(cagrilar), 3)
        self.assertIn("Bu kodda hata var: satır 1", cagrilar[2][-1]["content"])
        self.assertEqual(cagrilar[2][-2]["content"], bozuk)  # hatalı cevabını görür
        self.assertEqual(r["eylemler"][0]["kod"], "için i aralık(3):\n    yazdır(i)")

    def test_tek_kod_isi_ve_turkod_etiketli_cevap_duzelttirilir(self):
        iki_kod = {"cevap": '```eylem\n{"eylem": "kod_yaz", "istek": "yıldız"}\n'
                            '{"eylem": "kod_yaz", "istek": "yıldız", "hedef": "imlec"}\n```',
                   "dusunce": ""}
        karisik = "```TürKod\nimport turtle\nkaplumbağa = turtle.Turtle()\n```"
        duzgun = "```python\nimport turtle\nturtle.forward(100)\n```"
        r, cagrilar = self._sor([iki_kod, {"cevap": karisik, "dusunce": ""},
                                 {"cevap": duzgun, "dusunce": ""}])
        self.assertEqual(len(cagrilar), 3)  # Kodi + AI Asistan + tek düzeltme (iki iş değil)
        self.assertIn("başka bir etiketle", cagrilar[2][-1]["content"])
        self.assertEqual([e["eylem"] for e in r["eylemler"]], ["kod_yaz"])
        self.assertEqual(r["eylemler"][0]["kod"], "içe_aktar kaplumbağa\nkaplumbağa.ileri(100)")

    def test_turkceye_cevrilince_bozulan_kod_hata_sayilir(self):
        self.assertEqual(self.c._kod_denetle("for i in range(3):\n    print(i)"), "")
        with mock.patch("turkod_ide.ide_core.dogrula") as d:
            d.return_value = mock.Mock(basarili=False, hatalar=[mock.Mock(satir=1, mesaj="x")])
            self.assertIn("TürKod'a çevrilince satır 1 bozuluyor", self.c._kod_denetle("x = 1"))

    def test_ai_asistana_ulasilamazsa_kodinin_kodu_yedek(self):
        cevaplar = [{"cevap": "Al:\n```python\n" + PROGRAM + '\n```\n```eylem\n{"eylem": "kod_yaz"}\n```',
                     "dusunce": ""}]

        def sahte(kimlik, model, mesajlar, **kw):
            if kw.get("sistem") != self.c.ayarlar.get("ai_sistem_mesaji"):
                return cevaplar[0]
            raise ai.AIIstekHatasi("API anahtarı geçersiz", tur="anahtar")

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Bana bir program yaz", baglam={"sekmeler": ["a.trpy"]})
        self.assertIn("yazdır(19)", r["eylemler"][0]["kod"])
        self.assertNotIn("yazan", r["eylemler"][0])
        # Kodi'nin de kodu yoksa bunu söyler (eskiden boş balon).
        cevaplar[0] = {"cevap": '```eylem\n{"eylem": "kod_yaz", "istek": "x"}\n```', "dusunce": ""}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Bana bir program yaz", baglam={"sekmeler": ["a.trpy"]})
        self.assertEqual(r["eylemler"], [])
        self.assertIn("kodu yazdıramadım", r["cevap"])

    def test_uzun_kod_sohbete_yazilmaz_izin_karti_olur(self):
        r, _ = self._sor([{"cevap": "Al bakalım:\n```python\n" + PROGRAM
                                    + '\n```\nÇalıştırıp dene!\n{"eylem": "yok"}', "dusunce": ""}])
        self.assertEqual(r["cevap"], "Al bakalım:\n\nÇalıştırıp dene!")
        self.assertEqual(r["eylemler"][0]["eylem"], "kod_yaz")
        self.assertIn("yazdır(0)", r["eylemler"][0]["kod"])
        # Kısa örnekler sohbette kalır.
        r, _ = self._sor([{"cevap": 'Şöyle:\n```python\nprint("Selam")\n```\n{"eylem": "yok"}',
                           "dusunce": ""}], soru="Ekrana nasıl yazarım?")
        self.assertIn('yazdır("Selam")', r["cevap"])
        self.assertEqual(r["eylemler"], [])

    def test_kurulum_komutu_degil_program_yazilir(self):
        # Gerçek model programdan sonra bir de "pip install" bloğu yazdı;
        # eskiden son blok (kurulum komutu) editöre yazılacak kod sanılıyordu.
        for komut in ("```bash\npip install reportlab\n```", "```\npip install reportlab\n```",
                      "```python\npip install reportlab\n```"):
            r, _ = self._sor([{"cevap": "İşte!\n```python\n" + PROGRAM + "\n```\nÖnce kur:\n"
                                        + komut + '\n```eylem\n{"eylem": "kod_yaz", "hedef": '
                                        '"yeni_sekme"}\n```', "dusunce": ""}])
            self.assertIn("yazdır(19)", r["eylemler"][0]["kod"], komut)
            self.assertIn("reportlab", r["cevap"])  # kurulum komutu sohbette kalır
            self.assertNotIn("yazdır(19)", r["cevap"])

    def test_acik_kalan_kod_blogu_da_turkceye_cevrilir(self):
        cevap = self.c._cevabi_turkceye_cevir("Bak:\n```python\nfor i in range(3):\n    print(i)")
        self.assertIn("için i aralık(3):", cevap)
        self.assertTrue(cevap.rstrip().endswith("```"))

    def test_devami_birlestir(self):
        self.assertEqual(ai.devami_birlestir("```python\nprint(1)\nprint(2)",
                                             "```python\nprint(2)\nprint(3)\n```"),
                         "```python\nprint(1)\nprint(2)\nprint(3)\n```")
        self.assertEqual(ai.devami_birlestir("Merhaba ", "dünya"), "Merhaba dünya")


class KodAlanindaIsaretTestleri(unittest.TestCase):
    """Model kodu kod_yaz eyleminin "kod" alanına ```python işaretleriyle
    koyunca eylem bloğu ilk ``` işaretinde bitmiş sayılıyor, JSON yarım
    kalıp atılıyor, ham JSON (\\n, \\" kaçışlarıyla) sohbete dökülüyordu."""

    KOD = 'import os\n\ndef ana():\n    print("Merhaba")\n\nif __name__ == "__main__":\n    ana()'
    EYLEM = {"eylem": "kod_yaz", "hedef": "yeni_sekme", "ad": "pdf.trpy",
             "kod": "```python\n" + KOD + "\n```"}

    def _denetle(self, cevap):
        from turkod_ide import kodi
        metin, eylemler = kodi.eylemleri_ayir(cevap)
        self.assertEqual(eylemler, [{"eylem": "kod_yaz", "hedef": "yeni_sekme", "ad": "pdf.trpy",
                                     "kod": self.EYLEM["kod"]}])
        self.assertEqual(kodi.gecersiz_eylemler(cevap), [])
        self.assertTrue(kodi.eylem_sablonu_var(cevap))
        return metin

    def test_arac_cagrisindan_gelen_blok(self):
        cevap = ai._arac_cagrilarini_ekle("Kodun hazır!", [{"function": {
            "name": "eylem", "arguments": json.dumps(self.EYLEM)}}])
        self.assertEqual(self._denetle(cevap), "Kodun hazır!")

    def test_ciplak_satir_ve_cok_satirli_json(self):
        self.assertEqual(self._denetle("Al!\n" + json.dumps(self.EYLEM, ensure_ascii=False)), "Al!")
        self.assertEqual(self._denetle("Al!\n```eylem\n" + json.dumps(self.EYLEM, indent=2)
                                       + "\n```\nİyi eğlenceler!"), "Al!\n\nİyi eğlenceler!")

    def test_json_bloguna_yazilan_eylemler(self):
        # Gerçek model (gpt-oss-120b) eylemleri ```json bloklarına yazdı,
        # sonuncusunu kapatmadı; JSON sohbete dökülüyordu.
        from turkod_ide import kodi
        cevap = ("Tamam, işte özellikler.\n\n```python\nprint(1)\n```\n\n```json\n"
                 + json.dumps(self.EYLEM, indent=2) + "\n```\n\n```json\n{\n  \"eylem\": \"yok\"\n}")
        metin, eylemler = kodi.eylemleri_ayir(cevap)
        self.assertEqual([e["eylem"] for e in eylemler], ["kod_yaz", "yok"])
        self.assertEqual(metin, "Tamam, işte özellikler.\n\n```python\nprint(1)\n```")
        self.assertTrue(kodi.eylem_sablonu_var(cevap))
        # Eylemsiz JSON örneği (JSON öğreten bir cevap) olduğu gibi kalır.
        ornek = 'JSON şöyle yazılır:\n```json\n{"ad": "Ece", "yaş": 9}\n```'
        self.assertEqual(kodi.eylemleri_ayir(ornek), (ornek, []))
        self.assertFalse(kodi.eylem_sablonu_var(ornek))

    def test_kod_alanindaki_isaretler_temizlenir_ve_turkcelesir(self):
        dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            c = IDECore()
        r = c._kodi_cevabi("Kodun hazır!", [dict(self.EYLEM)], None, "kodi")
        kod = r["eylemler"][0]["kod"]
        self.assertNotIn("```", kod)
        self.assertTrue(kod.startswith("içe_aktar işletim_sistemi"), kod)
        self.assertIn('yazdır("Merhaba")', kod)
        self.assertEqual(r["cevap"], "Kodun hazır!")


class CiplakEylemTestleri(unittest.TestCase):
    def test_sondaki_ciplak_eylem_satiri_eylem_sayilir(self):
        from turkod_ide import kodi
        cevap = 'Değişken bir kutudur.\n\n{"eylem":"yok"}'
        self.assertTrue(kodi.eylem_sablonu_var(cevap))
        metin, eylemler = kodi.eylemleri_ayir(cevap)
        self.assertEqual(metin, "Değişken bir kutudur.")  # kullanıcı JSON görmez
        self.assertEqual(eylemler, [{"eylem": "yok"}])
        metin, eylemler = kodi.eylemleri_ayir(
            'Açıyorum!\n{"eylem": "panel", "panel": "terminal", "durum": "ac"}')
        self.assertEqual(eylemler[0]["panel"], "terminal")
        # Kod bloğundan sonra gelen çıplak eylem satırı da alınır.
        metin, eylemler = kodi.eylemleri_ayir('Bak:\n```python\nprint(1)\n```\n{"eylem": "yok"}')
        self.assertEqual(eylemler, [{"eylem": "yok"}])
        self.assertTrue(metin.endswith("```"))
        # gpt-oss'un sızdırdığı iç biçim de eylem bloğudur.
        metin, eylemler = kodi.eylemleri_ayir(
            'İyi eğlenceler!\n\n```commentary to=functions.eylem\n{"eylem":"yok"}\n```')
        self.assertEqual((metin, eylemler), ("İyi eğlenceler!", [{"eylem": "yok"}]))
        # Ortadaki ya da eylemi olmayan JSON'a dokunulmaz.
        self.assertFalse(kodi.eylem_sablonu_var('Örnek: {"ad": "Ece"}'))
        self.assertFalse(kodi.eylem_sablonu_var('{"eylem": "yok"}\nsonra yazı'))


class IsVaadiTestleri(unittest.TestCase):
    def test_karar_okunur(self):
        from turkod_ide import kodi
        self.assertFalse(kodi.is_vaadi_karari("Hayır."))
        self.assertFalse(kodi.is_vaadi_karari("hayir"))
        self.assertTrue(kodi.is_vaadi_karari("Evet"))
        self.assertTrue(kodi.is_vaadi_karari("⚠️ Yanıt token sınırına takıldı"))  # anlaşılmadı
        self.assertTrue(kodi.is_vaadi_karari("evet, hayır değil"))


def _ide():
    dizin = tempfile.mkdtemp()
    with mock.patch("os.path.expanduser", return_value=dizin), \
            contextlib.redirect_stdout(io.StringIO()):
        from turkod_ide.ide_core import IDECore
        c = IDECore()
    return c, dizin


class DevamUyarisiTestleri(unittest.TestCase):
    """Kesilen cevabın devamı yerine gelen uyarı ("⚠️ Model boş yanıt
    döndürdü.") ya da kurtarılmış eylem bloğu koda yapıştırılıyordu."""

    def setUp(self):
        self.c, self.dizin = _ide()
        self.c.ayarlar.ayarlar.update({"ai_api_anahtarlari": {"groq": "g"},
                                       "ai_gorev_atamalari": {"sohbet": GROQ},
                                       "ai_bulut_modelleri": [GROQ]})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _cagir(self, devam):
        bas = {"cevap": "```python\nfor i in range(3):\n    x = i*2", "dusunce": "",
               "kesildi": True}
        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=[bas, devam]) as s, \
                mock.patch.object(type(self.c), "_ONERILEN_MODELLER", {}), \
                contextlib.redirect_stdout(io.StringIO()):
            cevap = self.c._ai_api_cagri("Kod yaz", gorev="sohbet", gecmis_listesi=[],
                                         ham_cevap=True)
        self.assertEqual(s.call_count, 2)
        return cevap

    def test_uyari_devam_sayilmaz(self):
        for uyari in ("⚠️ Model boş yanıt döndürdü.",
                      "⚠️ Yanıt token sınırına takıldı (model düşünürken kesilmiş olabilir)."):
            cevap = self._cagir({"cevap": uyari, "dusunce": "", "uyari": True})
            self.assertEqual(cevap, "```python\nfor i in range(3):\n    x = i*2")

    def test_kurtarilan_eylem_blogu_devam_sayilmaz(self):
        cevap = self._cagir({"cevap": '```eylem\n{"eylem": "yok"}\n```', "dusunce": "",
                             "kurtarildi": True})
        self.assertNotIn("eylem", cevap)

    def test_sohbet_ayrintili_uyariyi_isaretler(self):
        bos = _yanit(200, {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]})
        sinir = _yanit(200, {"choices": [{"message": {"content": ""},
                                          "finish_reason": "length"}]})
        dolu = _yanit(200, {"choices": [{"message": {"content": "Selam"}}]})
        for y, uyari in ((bos, True), (sinir, True), (dolu, False)):
            with mock.patch("requests.post", return_value=y):
                r = ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}],
                                        anahtar="k")
            self.assertEqual(bool(r.get("uyari")), uyari, r)
        hata = _yanit(400, {"error": {
            "message": "tool call validation failed", "code": "tool_use_failed",
            "failed_generation": '{"name": "eylem", "arguments": {"eylem": "yok"}}'}})
        with mock.patch("requests.post", return_value=hata):
            r = ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": "a"}],
                                    anahtar="k",
                                    araclar=[{"type": "function", "function": {"name": "eylem"}}])
        self.assertTrue(r.get("kurtarildi"))


class GercekSatirSonuTestleri(unittest.TestCase):
    """JSON metninin içinde gerçek satır sonu olan eylem sessizce atılıyordu
    (eylem yok, şablon var, geçersiz de yok: düzeltme turu da olmuyordu)."""

    def test_satir_sonlu_kod_alani(self):
        from turkod_ide import kodi
        govde = '{"eylem":"kod_yaz","kod":"yazdır(1)\nyazdır(2)"}'
        for cevap in ("Al!\n```eylem\n" + govde + "\n```",
                      "Al!\n" + govde,
                      "Al!\n```json\n" + govde + "\n```",
                      "Al!\n<eylem>" + govde + "</eylem>"):
            metin, eylemler = kodi.eylemleri_ayir(cevap)
            self.assertEqual(metin, "Al!", cevap)
            self.assertEqual(len(eylemler), 1, cevap)
            self.assertEqual(eylemler[0]["kod"], "yazdır(1)\nyazdır(2)")
            self.assertEqual(kodi.gecersiz_eylemler(cevap), [])


class KodGirintisiTestleri(unittest.TestCase):
    def test_ilk_satirin_girintisi_korunur(self):
        c, dizin = _ide()
        try:
            cevap = c._cevabi_turkceye_cevir("```python\n    x = 1\n    print(x)\n```")
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)
        self.assertIn("```TürKod\n    x = 1\n    yazdır(x)\n", cevap)


class KodiGecmisiYarisTestleri(unittest.TestCase):
    """Vazgeçilen ya da yeni sohbetten önce başlamış istek geçmişi bozuyordu."""

    def setUp(self):
        self.c, self.dizin = _ide()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"groq": "g"}
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"kodi": GROQ}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_yeni_sohbetten_sonra_eski_istek_yazmaz(self):
        def sahte(kimlik, model, mesajlar, **kw):
            self.c.kodi_temizle()  # istek sürerken "Yeni sohbet"
            return {"cevap": 'Tamam\n```eylem\n{"eylem": "yok"}\n```', "dusunce": ""}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Eski soru")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.c.kodi_gecmisi, [])

    def test_vazgecilen_istek_yenisinin_turunu_silmez(self):
        ic_ice = []

        def sahte(kimlik, model, mesajlar, **kw):
            if not ic_ice:
                # Kullanıcı vazgeçip yeni soru sordu; eski istek hâlâ sürüyor.
                ic_ice.append(1)
                self.c.kodi_sor("Yeni soru")
                # Eski istek kılavuz istiyor (eskiden son iki kayıt silinirdi).
                return {"cevap": '```eylem\n{"eylem": "kilavuz", "bolum": "Tema"}\n```',
                        "dusunce": ""}
            return {"cevap": 'Cevap\n```eylem\n{"eylem": "yok"}\n```', "dusunce": ""}

        with mock.patch("turkod_ide.ai.sohbet_ayrintili", side_effect=sahte), \
                contextlib.redirect_stdout(io.StringIO()):
            self.c.kodi_sor("Eski soru")
        self.assertEqual([m["content"] for m in self.c.kodi_gecmisi if m["role"] == "user"],
                         ["Yeni soru"])
        self.assertEqual(len(self.c.kodi_gecmisi), 2)


class GorselNoThinkTestleri(unittest.TestCase):
    def test_gorselli_mesajda_yonerge_metne_eklenir(self):
        govde = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "Ekranda ne var?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}]}]}
        ai.dusunme_ayarla(govde, {"id": "groq"}, "qwen/qwen3-32b", False, 1000)
        icerik = govde["messages"][0]["content"]
        self.assertIsInstance(icerik, list)
        self.assertEqual(icerik[0]["text"], "Ekranda ne var? /no_think")
        self.assertEqual(icerik[1]["image_url"]["url"], "data:image/jpeg;base64,QUJD")
        govde = {"messages": [{"role": "user", "content": "Selam"}]}
        ai.dusunme_ayarla(govde, {"id": "groq"}, "qwen/qwen3-32b", False, 1000)
        self.assertEqual(govde["messages"][0]["content"], "Selam /no_think")


class TarayiciYazGuvenlikTestleri(unittest.TestCase):
    def _eylem(self, e, baglam):
        from turkod_ide import kodi
        _, eylemler = kodi.eylemleri_ayir("```eylem\n" + json.dumps(e) + "\n```", baglam)
        return eylemler[0] if eylemler else None

    def test_yazip_gondermek_izin_ister(self):
        baglam = {"tarayici": {"url": "https://a.com",
                               "ogeler": [{"no": 3, "tur": "input", "metin": "Ara"}]}}
        e = self._eylem({"eylem": "tarayici", "islem": "yaz", "no": 3, "metin": "kedi",
                         "gonder": True}, baglam)
        self.assertTrue(e.get("riskli"), e)
        e = self._eylem({"eylem": "tarayici", "islem": "yaz", "no": 3, "metin": "kedi"}, baglam)
        self.assertFalse(e.get("riskli"), e)

    def test_oge_listesi_yoksa_yazmak_izin_ister(self):
        e = self._eylem({"eylem": "tarayici", "islem": "yaz", "no": 3, "metin": "kedi"},
                        {"tarayici": {"url": "https://a.com"}})
        self.assertTrue(e.get("riskli"), e)


if __name__ == "__main__":
    unittest.main()
