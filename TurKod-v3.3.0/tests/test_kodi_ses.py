"""Kodi'nin sesi, kulağı ve masaüstü penceresi testleri (mikrofon ve ağ kullanılmaz)."""
import array
import contextlib
import io
import math
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

with contextlib.redirect_stdout(io.StringIO()):
    from turkod_ide import kodi_ses  # noqa: E402


def parca(genlik):
    """100 ms'lik 16 bit ses parçası (sinüs)."""
    n = int(kodi_ses.ORNEKLEME * kodi_ses.PARCA_SN)
    return array.array("h", (int(genlik * math.sin(i / 8)) for i in range(n))).tobytes()


class SessizlikTestleri(unittest.TestCase):
    def test_konusma_ayrilir(self):
        akis = [parca(30)] * 5 + [parca(4000)] * 10 + [parca(30)] * 15 + [parca(4000)] * 50
        veri = kodi_ses.sessizlik_ayir(iter(akis), sessizlik_sn=1.2)
        self.assertIsNotNone(veri)
        sure = len(veri) / (kodi_ses.ORNEKLEME * 2)
        # Konuşma (1 sn) + baştaki pay + 1,2 sn sessizlik; sonraki ses alınmaz.
        self.assertGreater(sure, 1.0)
        self.assertLess(sure, 3.0)

    def test_kimse_konusmazsa_none(self):
        akis = [parca(30)] * 100
        self.assertIsNone(kodi_ses.sessizlik_ayir(iter(akis), baslama_sn=3))

    def test_dur_olayi(self):
        dur = threading.Event()
        dur.set()
        self.assertIsNone(kodi_ses.sessizlik_ayir(iter([parca(4000)] * 30), dur=dur))

    def test_wav(self):
        import wave
        w = wave.open(io.BytesIO(kodi_ses._wav(parca(100))))
        self.assertEqual((w.getnchannels(), w.getframerate(), w.getsampwidth()), (1, 16000, 2))


class MetinTestleri(unittest.TestCase):
    def test_konusma_metni(self):
        m = kodi_ses.konusma_metni(
            "**Süper!** Şöyle yap:\n- **Çalıştır → EXE'ye Dönüştür**\n```python\nprint(1)\n```\n"
            "[Site](https://x.y) https://a.b")
        self.assertNotIn("print", m)
        self.assertNotIn("**", m)
        self.assertNotIn("http", m)
        self.assertIn("Kodu balona yazdım", m)
        self.assertIn("Süper!", m)

    @unittest.skipUnless(sys.platform == "win32", "Seslendirme yalnızca Windows'ta")
    def test_seslendirme_basarisizsa_gecici_klasor_kalmaz(self):
        # Eskiden PowerShell ses dosyası üretemeyince os.remove(ses.wav) hata
        # veriyor, geçici klasör hiç silinmiyordu (her denemede bir klasör).
        ust = tempfile.mkdtemp()
        klasor = os.path.join(ust, "kodi_ses_deneme")
        os.makedirs(klasor)
        try:
            with mock.patch("tempfile.mkdtemp", return_value=klasor), \
                    mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)):
                with self.assertRaises(kodi_ses.SesHatasi):
                    kodi_ses.seslendir("Merhaba")
            self.assertFalse(os.path.exists(klasor))
        finally:
            import shutil
            shutil.rmtree(ust, ignore_errors=True)


class YaziyaCevirTestleri(unittest.TestCase):
    def test_groq_whisper_istegi(self):
        yanit = mock.Mock(status_code=200, ok=True)
        yanit.json.return_value = {"text": " Merhaba Kodi "}
        with mock.patch("requests.post", return_value=yanit) as post:
            metin = kodi_ses.yaziya_cevir(b"RIFF", "groq", "anahtar")
        self.assertEqual(metin, "Merhaba Kodi")
        self.assertIn("groq.com", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["data"]["language"], "tr")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer anahtar")

    def test_gecersiz_anahtar(self):
        with mock.patch("requests.post", return_value=mock.Mock(status_code=401, ok=False)):
            with self.assertRaises(kodi_ses.SesHatasi):
                kodi_ses.yaziya_cevir(b"RIFF", "openai", "x")


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

    def test_anahtar_yoksa_dinlemez(self):
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {}
        with mock.patch.object(kodi_ses, "dinle") as d:
            r = self.c.kodi_dinle()
        self.assertFalse(r["ok"])
        self.assertTrue(r["anahtar_yok"])
        d.assert_not_called()

    def test_dinle_ve_yaziya_cevir(self):
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"deepseek": "d", "groq": "g"}
        with mock.patch.object(kodi_ses, "dinle", return_value=b"WAV"), \
                mock.patch.object(kodi_ses, "yaziya_cevir", return_value="selam") as y:
            r = self.c.kodi_dinle()
        self.assertEqual(r, {"ok": True, "metin": "selam"})
        self.assertEqual(y.call_args.args[1], "groq")

    def test_sessizlik(self):
        self.c.ayarlar.ayarlar["ai_api_anahtarlari"] = {"openai": "o"}
        with mock.patch.object(kodi_ses, "dinle", return_value=None):
            r = self.c.kodi_dinle()
        self.assertTrue(r["ok"])
        self.assertTrue(r["sessiz"])

    def test_ses_betigi_paketlenir(self):
        with open(os.path.join(KOK, "turkod_backend.spec"), encoding="utf-8") as f:
            self.assertIn("kodi_ses.ps1", f.read())

    def test_imlec_konumu(self):
        r = self.c.kodi_imlec_konumu()
        if sys.platform == "win32":
            self.assertTrue(r["ok"])
            self.assertIsInstance(r["x"], int)


class KopruTestleri(unittest.TestCase):
    def test_kopru_iletir(self):
        with contextlib.redirect_stdout(io.StringIO()):
            from turkod_ide import server
        gelen = []
        server._KODI_KOPRU.clear()
        self.assertFalse(server._cmd_kodi_kopru_gonder({"rol": "kodi", "veri": {}})["ok"])
        server._KODI_KOPRU["kodi"] = gelen.append
        r = server._cmd_kodi_kopru_gonder({"rol": "kodi", "veri": {"tur": "don"}})
        self.assertTrue(r["ok"])
        self.assertEqual(gelen, [{"tur": "don"}])
        server._KODI_KOPRU.clear()


if __name__ == "__main__":
    unittest.main()
