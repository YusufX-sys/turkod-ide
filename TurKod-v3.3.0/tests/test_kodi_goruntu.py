"""Kodi'ye mesajla giden ekran görüntüsü ve kurulum rehberi (ağ kullanılmaz)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import ai, kodi_goruntu  # noqa: E402

GORSEL = {"saglayici": "openai", "model": "gpt-4o-mini"}
METIN = {"saglayici": "groq", "model": "openai/gpt-oss-20b"}


class AiTestleri(unittest.TestCase):
    def test_gorsel_destek(self):
        self.assertTrue(ai.gorsel_destekler("openai", "gpt-4o-mini"))
        self.assertTrue(ai.gorsel_destekler("groq", "meta-llama/llama-4-scout-17b-16e-instruct"))
        self.assertFalse(ai.gorsel_destekler("groq", "openai/gpt-oss-20b"))

    def test_anthropic_bicimi(self):
        icerik = [{"type": "text", "text": "a"},
                  {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}]
        donen = ai._anthropic_icerik(icerik)
        self.assertEqual(donen[1], {"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": "QUJD"}})
        self.assertEqual(ai._gorselsiz([{"role": "user", "content": icerik}]),
                         [{"role": "user", "content": "a"}])
        self.assertEqual(ai._icerik_uzunlugu(icerik), 4001)

    def test_model_gorsel_kabul_etmezse_gorselsiz_yeniden(self):
        hata = mock.Mock(status_code=400, headers={})
        hata.json.return_value = {"error": {"message": "image input not supported"}}
        hata.text = ""
        tamam = mock.Mock(status_code=200, headers={})
        tamam.json.return_value = {"choices": [{"message": {"content": "Göremiyorum ama..."}}]}
        icerik = [{"type": "text", "text": "Bak"},
                  {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QQ=="}}]
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            r = ai.sohbet_ayrintili("groq", "m", [{"role": "user", "content": icerik}], anahtar="k")
        self.assertTrue(r["gorsel_atildi"])
        self.assertEqual(post.call_args.kwargs["json"]["messages"][-1]["content"], "Bak")


class AracCagrisiTestleri(unittest.TestCase):
    def test_model_arac_cagirirsa_uyariyla_yeniden_denenir(self):
        hata = mock.Mock(status_code=400, headers={})
        hata.json.return_value = {"error": {"message": "Tool choice is none, but model called a tool",
                                            "code": "tool_use_failed"}}
        hata.text = ""
        tamam = mock.Mock(status_code=200, headers={})
        tamam.json.return_value = {"choices": [{"message": {"content": "Tamam"}}]}
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            r = ai.sohbet_ayrintili("groq", "openai/gpt-oss-20b",
                                    [{"role": "user", "content": "Google'da ara"}],
                                    sistem="Sen Kodi'sin.", anahtar="k")
        self.assertEqual(r["cevap"], "Tamam")
        sistem = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("Hiçbir araç", sistem)


class EylemAraciTestleri(unittest.TestCase):
    def test_arac_cagrisi_eylem_bloguna_cevrilir(self):
        from turkod_ide import kodi
        yanit = mock.Mock(status_code=200, headers={})
        yanit.json.return_value = {"choices": [{"message": {"content": "Tıklıyorum!", "tool_calls": [
            {"function": {"name": "eylem",
                          "arguments": '{"eylem": "tarayici", "islem": "tikla", "no": 3}'}},
            {"function": {"name": "browser.search", "arguments": "{}"}}]}}]}
        with mock.patch("requests.post", return_value=yanit) as post:
            r = ai.sohbet_ayrintili("groq", "openai/gpt-oss-20b",
                                    [{"role": "user", "content": "tıkla"}], anahtar="k",
                                    araclar=kodi.ARACLAR)
        self.assertEqual(post.call_args.kwargs["json"]["tools"][0]["function"]["name"], "eylem")
        metin, eylemler = kodi.eylemleri_ayir(r["cevap"], TarayiciTestleri.BAGLAM)
        self.assertEqual(metin, "Tıklıyorum!")
        self.assertEqual(eylemler[0]["no"], 3)

    def test_arac_desteklenmezse_kaldirilir(self):
        hata = mock.Mock(status_code=400, headers={})
        hata.json.return_value = {"error": {"message": "This model does not support tools"}}
        hata.text = ""
        tamam = mock.Mock(status_code=200, headers={})
        tamam.json.return_value = {"choices": [{"message": {"content": "Tamam"}}]}
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            ai.sohbet_ayrintili("ozel", "m", [{"role": "user", "content": "a"}], anahtar="k",
                                api="http://127.0.0.1:1/v1", araclar=[{"type": "function"}])
        self.assertNotIn("tools", post.call_args.kwargs["json"])


class CekirdekTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        with mock.patch("os.path.expanduser", return_value=self.dizin), \
                contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide.ide_core import IDECore
            self.c = IDECore()
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"openai": "k", "groq": "g"}

    def tearDown(self):
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _sor(self, atama, kip):
        self.c.ayarlar.ayarlar["ai_gorev_atamalari"] = {"sohbet": atama}
        self.c.ayarlar.ayarlar["kodi_goruntu"] = kip
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": "Gördüm!", "dusunce": ""}) as s, \
                mock.patch.object(kodi_goruntu, "yakala", return_value=("QUJD", "10x10")) as y, \
                contextlib.redirect_stdout(io.StringIO()):
            r = self.c.kodi_sor("Ekranımda ne var?")
        return r, s, y

    def test_gorsel_giden_istek(self):
        r, s, y = self._sor(GORSEL, "pencere")
        y.assert_called_once_with("pencere")
        son = s.call_args.args[2][-1]["content"]
        self.assertEqual(son[1]["image_url"]["url"], "data:image/jpeg;base64,QUJD")
        self.assertEqual(r["goruntu"], "gitti")
        # Geçmişe görsel girmez (her soruda yeniden gönderilmesin).
        self.assertEqual(self.c.kodi_gecmisi[0]["content"], "Ekranımda ne var?")

    def test_kapaliysa_gorsel_yok(self):
        r, s, y = self._sor(GORSEL, "kapali")
        y.assert_not_called()
        self.assertIsInstance(s.call_args.args[2][-1]["content"], str)
        self.assertIsNone(r["goruntu"])

    def test_model_gormuyorsa_alinmaz(self):
        r, s, y = self._sor(METIN, "ekran")
        y.assert_not_called()
        self.assertEqual(r["goruntu"], "desteklenmiyor")

    def test_kurulum(self):
        with mock.patch("turkod_ide.ai.api_modelleri",
                        return_value=["whisper-large-v3", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]), \
                mock.patch("turkod_ide.ai.modelleri_guncelle"):
            r = self.c.kodi_kurulum("groq", " gsk_1234567890abc ")
        self.assertTrue(r["ok"])
        self.assertEqual(r["model"], "openai/gpt-oss-20b")
        self.assertEqual(self.c.ayarlar.get("ai_api_anahtarlari")["groq"], "gsk_1234567890abc")
        self.assertEqual(self.c.ai_gorev_atamalari()["sohbet"],
                         {"saglayici": "groq", "model": "openai/gpt-oss-20b"})
        self.assertNotIn("kodi", self.c.ai_gorev_atamalari())
        self.assertTrue(self.c.kodi_durum()["hazir"])

    def test_kurulum_gecersiz_anahtar(self):
        with mock.patch("turkod_ide.ai.api_modelleri", side_effect=RuntimeError("HTTP 401")):
            r = self.c.kodi_kurulum("groq", "gsk_yanlisanahtar")
        self.assertFalse(r["ok"])
        self.assertIn("çalışmadı", r["hata"])
        self.assertFalse(self.c.kodi_kurulum("groq", "kisa")["ok"])


class TarayiciTestleri(unittest.TestCase):
    BAGLAM = {"tarayici": {"url": "https://ornek.com", "acik": True, "baslik": "Örnek",
                           "ozet": "Hoş geldin", "ogeler": [
                               {"no": 1, "tur": "button", "metin": "Satın al"},
                               {"no": 2, "tur": "input:password", "metin": "Şifre", "sifre": True},
                               {"no": 3, "tur": "a", "metin": "Belgeler"},
                               {"no": 4, "tur": "input:text", "metin": "Ara"}]}}

    def test_dogrulama(self):
        from turkod_ide import kodi
        cevap = ("```eylem\n"
                 '{"eylem": "tarayici", "islem": "tikla", "no": 1}\n'
                 '{"eylem": "tarayici", "islem": "yaz", "no": 2, "metin": "gizli"}\n'
                 '{"eylem": "tarayici", "islem": "yaz", "no": 4, "metin": "kedi", "gonder": true}\n'
                 '{"eylem": "tarayici", "islem": "tikla", "no": 3, "devam": true}\n'
                 '{"eylem": "tarayici", "islem": "tikla", "no": 99}\n'
                 '{"eylem": "tarayici", "islem": "ac", "adres": "groq.com"}\n'
                 '{"eylem": "rehber"}\n```')
        _, e = kodi.eylemleri_ayir(cevap, self.BAGLAM)
        # Tarayıcı işlerinden sonra Kodi yeni sayfaya bakıp kendiliğinden
        # devam eder (gönderilmeyen yazı hariç); no 99 listede yok, atılır.
        self.assertEqual(e, [
            {"eylem": "tarayici", "islem": "tikla", "devam": True, "no": 1, "etiket": "Satın al",
             "riskli": True},
            {"eylem": "tarayici", "islem": "yaz", "devam": True, "no": 4, "etiket": "Ara",
             "metin": "kedi", "gonder": True, "riskli": True},  # yazıp göndermek: izin
            {"eylem": "tarayici", "islem": "tikla", "devam": True, "no": 3, "etiket": "Belgeler"},
            {"eylem": "tarayici", "islem": "ac", "devam": True, "adres": "groq.com"},
            {"eylem": "rehber"}])

    def test_sayfa_bilgisi_kodiye_gider(self):
        from turkod_ide import kodi
        m = kodi.soru_mesaji("Belgeler'e tıkla", self.BAGLAM)
        self.assertIn("TARAYICI: Örnek (https://ornek.com)", m)
        self.assertIn('3=a "Belgeler"', m)
        self.assertIn("(şifre)", m)
        self.assertIn('"eylem": "tarayici"', kodi.sabit_sistem_mesaji("", self.BAGLAM))


if __name__ == "__main__":
    unittest.main()
