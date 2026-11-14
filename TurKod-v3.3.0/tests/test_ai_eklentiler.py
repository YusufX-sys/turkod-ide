"""AI sağlayıcı kataloğu, yerel modeller, TürKod Kabuğu ve komut satırı testleri.

Ağ kullanılmaz: HTTP istekleri taklit edilir.
"""
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
    from turkod_ide import ai, calistirici, kabuk, yerel_modeller  # noqa: E402


class _Yanit:
    def __init__(self, kod, veri):
        self.status_code = kod
        self._veri = veri
        self.text = json.dumps(veri)
        self.ok = kod < 400

    def json(self):
        return self._veri


MODELS_DEV = {
    "groq": {"id": "groq", "name": "Groq", "npm": "@ai-sdk/groq", "env": ["GROQ_API_KEY"],
             "models": {
                 "eski": {"id": "eski", "release_date": "2023-01-01",
                          "modalities": {"output": ["text"]}},
                 "yeni": {"id": "yeni", "release_date": "2025-01-01",
                          "modalities": {"output": ["text"]}},
                 "kaldirilan": {"id": "kaldirilan", "status": "deprecated"},
                 "resim": {"id": "resim", "modalities": {"output": ["image"]}},
             }},
    "deepseek": {"id": "deepseek", "name": "DeepSeek", "api": "https://api.deepseek.com",
                 "npm": "@ai-sdk/openai-compatible",
                 "models": {"deepseek-chat": {"id": "deepseek-chat"}}},
    "minimax": {"id": "minimax", "name": "MiniMax", "api": "https://api.minimax.io/anthropic/v1",
                "npm": "@ai-sdk/anthropic", "models": {"m1": {"id": "m1"}}},
    "azure": {"id": "azure", "name": "Azure", "npm": "@ai-sdk/azure",
              "models": {"x": {"id": "x"}}},
    "degiskenli": {"id": "degiskenli", "name": "D", "api": "https://${HESAP}.example/v1",
                   "models": {"x": {"id": "x"}}},
    "adressiz": {"id": "adressiz", "name": "A", "npm": "bilinmeyen",
                 "models": {"x": {"id": "x"}}},
}


class KatalogTestleri(unittest.TestCase):
    def test_katalog_dusunme_secenekleri(self):
        ham = {"openai": {"id": "openai", "name": "OpenAI", "npm": "@ai-sdk/openai", "models": {
            "gpt-5": {"id": "gpt-5", "reasoning": True, "reasoning_options": [
                {"type": "effort", "values": ["minimal", "high"]}, {"type": "toggle"}]},
            "gpt-4o": {"id": "gpt-4o", "reasoning": False}}}}
        k = ai.models_dev_isle(ham)["openai"]
        self.assertEqual(k["dusunme"], {"gpt-5": {"efor": ["minimal", "high"],
                                                  "ac_kapa": True, "butce": False}})

    def test_models_dev_isleme(self):
        k = ai.models_dev_isle(MODELS_DEV)
        self.assertEqual(set(k), {"groq", "deepseek", "minimax"})
        # En yeni model başta; kaldırılan ve metin üretmeyen modeller yok.
        self.assertEqual(k["groq"]["modeller"], ["yeni", "eski"])
        self.assertEqual(k["groq"]["api"], ai.BILINEN_API["groq"])
        self.assertEqual(k["minimax"]["tur"], "anthropic")
        self.assertTrue(k["deepseek"]["anahtar_gerekli"])

    def test_yerel_ve_ek_saglayicilar_eklenir(self):
        k = ai._tamamla(ai.models_dev_isle(MODELS_DEV))
        for kimlik in ("yerel", "lmstudio", "llamacpp", "meta-llama", "ozel"):
            self.assertIn(kimlik, k)
        self.assertFalse(k["yerel"]["anahtar_gerekli"])
        self.assertNotIn("ollama", k)
        self.assertFalse(k["ozel"]["anahtar_gerekli"])
        # Öncelikli sağlayıcılar başta.
        self.assertEqual(list(k)[0], "yerel")

    def test_eski_adlar(self):
        self.assertEqual(ai.saglayici_kimligi("Claude"), "anthropic")
        self.assertEqual(ai.saglayici_kimligi("Gemini"), "google")
        self.assertEqual(ai.saglayici_kimligi("groq"), "groq")
        self.assertEqual(ai.saglayici_kimligi("ollama"), "yerel")

    def test_acilissiz_dusunce_ayrilir(self):
        # Sohbet şablonu <think>'i kendisi yazdığından yanıtta yalnızca kapanış
        # etiketi gelir (kullanıcının gördüğü gerçek çıktı).
        ham = ("Merhaba! Size yardımcı olmak için hazır.\n\nLütfen sorularınızı "
               "belirtin.\n</think>\n\nMerhaba! Size nasıl yardımcı olabilirim? 😊")
        dusunce, cevap = ai.dusunce_ayir(ham)
        self.assertEqual(cevap, "Merhaba! Size nasıl yardımcı olabilirim? 😊")
        self.assertIn("Lütfen sorularınızı", dusunce)
        self.assertNotIn("think", cevap)

    def test_dusunce_bicimleri(self):
        self.assertEqual(ai.dusunce_ayir("<think>plan</think>\nCevap"), ("plan", "Cevap"))
        self.assertEqual(ai.dusunce_ayir("<thinking>a</thinking>B"), ("a", "B"))
        self.assertEqual(ai.dusunce_ayir("Cevap<think>yarım"), ("yarım", "Cevap"))
        self.assertEqual(ai.dusunce_ayir("Düz yanıt"), ("", "Düz yanıt"))

    def test_dusunce_blogu_temizlenir(self):
        self.assertEqual(ai.dusunceyi_temizle("<think>uzun</think>\nCevap"), "Cevap")
        self.assertEqual(ai.dusunceyi_temizle("Cevap<think>yarım"), "Cevap")


class SohbetTestleri(unittest.TestCase):
    def setUp(self):
        self._eski = ai._KATALOG
        ai._KATALOG = ai._tamamla(ai.models_dev_isle(MODELS_DEV))

    def tearDown(self):
        ai._KATALOG = self._eski

    def test_openai_uyumlu_istek(self):
        yanit = _Yanit(200, {"choices": [{"message": {"content": "merhaba"}}]})
        with mock.patch("requests.post", return_value=yanit) as post:
            metin = ai.sohbet("deepseek", "deepseek-chat", [{"role": "user", "content": "x"}],
                              sistem="S", anahtar="k")
        self.assertEqual(metin, "merhaba")
        url = post.call_args.args[0]
        govde = post.call_args.kwargs["json"]
        self.assertEqual(url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(govde["messages"][0], {"role": "system", "content": "S"})
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer k")

    def _govde(self, kimlik, model, ac, **s_ek):
        s = {"id": kimlik, "tur": "openai", "yerel": False, **s_ek}
        govde = {"model": model, "messages": [{"role": "user", "content": "selam"}],
                 "temperature": 0.7, "max_tokens": 4096}
        ai.dusunme_ayarla(govde, s, model, ac, 4096)
        return govde

    def test_dusunme_kapatma_parametreleri(self):
        # Katalogda "none" seçeneği olan model: tamamen kapatılır.
        g = self._govde("openai", "gpt-5", False,
                        dusunme={"gpt-5": {"efor": ["minimal", "low", "none"]}})
        self.assertEqual(g["reasoning_effort"], "none")
        g = self._govde("openai", "o3", False, dusunme={"o3": {"efor": ["low", "high"]}})
        self.assertEqual(g["reasoning_effort"], "low")
        # Katalogda bilgi yoksa bilinen uçların kuralı.
        self.assertEqual(self._govde("google", "gemini-x", False)["reasoning_effort"], "none")
        self.assertEqual(self._govde("openrouter", "x/y", False)["reasoning"], {"enabled": False})
        # Qwen3 (yerel): şablon bilgisi + /no_think yönergesi.
        g = self._govde("yerel", "Qwen3-8B-Q4_K_M.gguf", False, yerel=True)
        self.assertEqual(g["chat_template_kwargs"], {"enable_thinking": False})
        self.assertTrue(g["messages"][-1]["content"].endswith("/no_think"))
        # Düşünmeyen sıradan model: hiçbir şey eklenmez.
        g = self._govde("deepseek", "deepseek-chat", False)
        self.assertFalse(any(p in g for p in ai._DUSUNME_PARAMLARI))
        # None: hiç dokunulmaz.
        self.assertNotIn("reasoning_effort", self._govde("google", "g", None))

    def test_claude_dusunme_acilinca_butce(self):
        g = self._govde("anthropic", "claude-x", True, tur="anthropic")
        self.assertEqual(g["thinking"]["type"], "enabled")
        self.assertNotIn("temperature", g)
        self.assertGreater(g["max_tokens"], g["thinking"]["budget_tokens"])
        self.assertNotIn("thinking", self._govde("anthropic", "claude-x", False, tur="anthropic"))

    def test_desteklenmeyen_dusunme_ayari_atilip_yeniden_denenir(self):
        ai._KATALOG["google"] = ai._kayit("google", "Google", "https://g/v1", modeller=["g"])
        hata = _Yanit(400, {"error": {"message": "Unknown name \"reasoning_effort\""}})
        tamam = _Yanit(200, {"choices": [{"message": {"content": "ok"}}]})
        gonderilen, yanitlar = [], [hata, tamam]

        def post(*a, **kw):
            gonderilen.append(json.loads(json.dumps(kw["json"])))  # o anki kopya
            return yanitlar.pop(0)

        with mock.patch("requests.post", side_effect=post):
            self.assertEqual(ai.sohbet("google", "g", [{"role": "user", "content": "x"}],
                                       anahtar="k", dusunme=False), "ok")
        self.assertIn("reasoning_effort", gonderilen[0])
        self.assertNotIn("reasoning_effort", gonderilen[1])

    def test_ayri_alandaki_dusunce(self):
        yanit = _Yanit(200, {"choices": [{"message": {
            "content": "Sonuç 4.", "reasoning_content": "2+2 hesapla"}}]})
        with mock.patch("requests.post", return_value=yanit):
            r = ai.sohbet_ayrintili("deepseek", "m", [], anahtar="k")
        self.assertEqual(r, {"cevap": "Sonuç 4.", "dusunce": "2+2 hesapla", "kullanim": {}})

    def test_anthropic_bicimi(self):
        yanit = _Yanit(200, {"content": [{"type": "thinking", "thinking": "..."},
                                         {"type": "text", "text": "tamam"}]})
        with mock.patch("requests.post", return_value=yanit) as post:
            metin = ai.sohbet("minimax", "m1", [{"role": "user", "content": "x"}],
                              sistem="S", anahtar="k")
        self.assertEqual(metin, "tamam")
        self.assertTrue(post.call_args.args[0].endswith("/messages"))
        self.assertEqual(post.call_args.kwargs["json"]["system"], "S")
        self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "k")

    def test_desteklenmeyen_parametre_yeniden_denenir(self):
        hata = _Yanit(400, {"error": {"message": "Unsupported parameter: 'temperature'"}})
        tamam = _Yanit(200, {"choices": [{"message": {"content": "ok"}}]})
        with mock.patch("requests.post", side_effect=[hata, tamam]) as post:
            self.assertEqual(ai.sohbet("deepseek", "m", [], anahtar="k"), "ok")
        self.assertNotIn("temperature", post.call_args.kwargs["json"])

    def test_turkce_hata_iletileri(self):
        for kod, parca in ((401, "anahtar"), (404, "Model bulunamadı"), (429, "limit")):
            with mock.patch("requests.post", return_value=_Yanit(kod, {"error": "x"})):
                with self.assertRaises(ai.AIIstekHatasi) as h:
                    ai.sohbet("deepseek", "m", [], anahtar="k")
            self.assertIn(parca, str(h.exception))

    def test_anahtarsiz_bulut_reddedilir_yerel_kabul(self):
        with self.assertRaises(ai.AIIstekHatasi):
            ai.sohbet("deepseek", "m", [])
        yanit = _Yanit(200, {"choices": [{"message": {"content": "yerel"}}]})
        with mock.patch("requests.post", return_value=yanit) as post:
            self.assertEqual(ai.sohbet("yerel", "m.gguf", [], api="http://127.0.0.1:9/v1"),
                             "yerel")
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:9/v1/chat/completions")
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])

    def test_yerel_sunucu_kapali(self):
        import requests
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            with self.assertRaises(ai.AIIstekHatasi) as h:
                ai.sohbet("yerel", "m.gguf", [], api="http://127.0.0.1:9/v1")
        self.assertIn("ulaşılamıyor", str(h.exception))


class YerelModelTestleri(unittest.TestCase):
    DONANIM = {"ram_toplam_gb": 8.0, "ram_bos_gb": 4.0, "cekirdek": 4, "gpu": [],
               "vram_gb": 0.0, "isletim_sistemi": "win32",
               "hizlandirma": {"tur": "cpu", "paket": "cpu", "vram_gb": 0.0}}

    @staticmethod
    def depolama(kullanilabilir, baska=0.0):
        suruculer = [{"kok": "C:\\", "harf": "C", "model_surucusu": True,
                      "kullanilabilir_gb": kullanilabilir}]
        if baska:
            suruculer.append({"kok": "D:\\", "harf": "D", "model_surucusu": False,
                              "kullanilabilir_gb": baska})
        return {"suruculer": suruculer, "kullanilabilir_gb": kullanilabilir}

    def test_iptal_yarim_dosyayi_siler(self):
        dizin = tempfile.mkdtemp(prefix="turkod_iptal_")
        kimlik = "deneme/model/a.gguf"
        gecici = os.path.join(dizin, "a.gguf.part")

        class Yanit:
            status_code = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def iter_content(self, chunk_size):
                yield b"x" * 10
                yerel_modeller._INDIRMELER[kimlik]["iptal"] = True
                yield b"y" * 10

        yerel_modeller._INDIRMELER[kimlik] = {"durum": "indiriliyor", "iptal": False}
        with mock.patch.object(yerel_modeller, "model_dizini", return_value=dizin),                 mock.patch.object(yerel_modeller, "_dosya_bilgisi", return_value=30),                 mock.patch.object(yerel_modeller, "kullanilabilir_gb", return_value=100),                 mock.patch("requests.get", return_value=Yanit()):
            yerel_modeller._indir(kimlik, "A", 1)
        self.assertEqual(yerel_modeller._INDIRMELER.pop(kimlik)["durum"], "iptal")
        self.assertFalse(os.path.exists(gecici))
        os.rmdir(dizin)

    def test_kopan_indirme_kaldigi_yerden_surer(self):
        import requests
        dizin = tempfile.mkdtemp(prefix="turkod_surdur_")
        kimlik = "deneme/model/b.gguf"
        cagrilar = []

        class Yanit:
            def __init__(self, kod, parcalar, kop):
                self.status_code, self.parcalar, self.kop = kod, parcalar, kop
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def iter_content(self, chunk_size):
                yield from self.parcalar
                if self.kop:
                    raise requests.ConnectionError("koptu")

        def get(url, headers, **kw):
            cagrilar.append(dict(headers))
            if len(cagrilar) == 1:
                return Yanit(200, [b"a" * 10], True)
            return Yanit(206, [b"b" * 20], False)

        yerel_modeller._INDIRMELER[kimlik] = {"durum": "indiriliyor", "iptal": False}
        with mock.patch.object(yerel_modeller, "model_dizini", return_value=dizin), \
                mock.patch.object(yerel_modeller, "_dosya_bilgisi", return_value=30), \
                mock.patch.object(yerel_modeller, "kullanilabilir_gb", return_value=100), \
                mock.patch.object(yerel_modeller.time, "sleep"), \
                mock.patch("requests.get", side_effect=get):
            yerel_modeller._indir(kimlik, "B", 1)
        self.assertEqual(yerel_modeller._INDIRMELER.pop(kimlik)["durum"], "tamam")
        self.assertEqual(cagrilar[1].get("Range"), "bytes=10-")
        with open(os.path.join(dizin, "b.gguf"), "rb") as f:
            self.assertEqual(f.read(), b"a" * 10 + b"b" * 20)
        import shutil
        shutil.rmtree(dizin, ignore_errors=True)

    def test_gpu_karari(self):
        karar = yerel_modeller.hizlandirma_karari
        amd = [{"ad": "Radeon (TM) R5 M430", "vram_gb": 2.0, "uretici": "amd"},
               {"ad": "Intel(R) HD Graphics 620", "vram_gb": 1.0, "uretici": "intel"}]
        k = karar(amd, None)
        self.assertEqual(k["tur"], "cpu")
        self.assertIn("AMD", k["aciklama"])
        self.assertEqual(k["vram_gb"], 0.0)
        # Güçlü AMD kart da (8 GB) hazır paketlerde hızlandırılmaz.
        self.assertEqual(karar([{"ad": "Radeon RX 7600", "vram_gb": 8, "uretici": "amd"}],
                               None)["tur"], "cpu")
        nv = [{"ad": "NVIDIA GeForce RTX 3060", "vram_gb": 12.0, "uretici": "nvidia"}]
        k = karar(nv, (12, 4))
        self.assertEqual((k["tur"], k["paket"], k["vram_gb"]), ("cuda", "cu124", 12.0))
        self.assertEqual(karar(nv, (13, 0))["paket"], "cu130")
        self.assertEqual(karar(nv, (11, 8))["tur"], "cpu")        # eski sürücü
        az = [{"ad": "NVIDIA GeForce MX150", "vram_gb": 2.0, "uretici": "nvidia"}]
        self.assertEqual(karar(az, (12, 6))["tur"], "cpu")        # az VRAM
        self.assertEqual(yerel_modeller.uretici("AMD Radeon RX 580"), "amd")
        self.assertEqual(yerel_modeller.uretici("NVIDIA GeForce GTX 1650"), "nvidia")

    def test_sigar_mi_bellek_ve_disk(self):
        dep = self.depolama(50)
        self.assertTrue(yerel_modeller.sigar_mi(1.5, self.DONANIM, dep)[0])
        self.assertTrue(yerel_modeller.sigar_mi(7.6, self.DONANIM, dep)[0])
        self.assertFalse(yerel_modeller.sigar_mi(32, self.DONANIM, dep)[0])
        # İşlemcide çalışırken "ekran kartında" denmez.
        self.assertNotIn("ekran", yerel_modeller.sigar_mi(1.5, self.DONANIM, dep)[2].lower())
        gpu = dict(self.DONANIM, vram_gb=8.0)
        uygun, hizli, gerekce = yerel_modeller.sigar_mi(7.6, gpu, dep)
        self.assertTrue(hizli)
        self.assertIn("CUDA", gerekce)

    def test_depolamaya_gore_uygunluk(self):
        uygun, _, gerekce = yerel_modeller.sigar_mi(7.6, self.DONANIM, self.depolama(2))
        self.assertFalse(uygun)
        self.assertIn("Diskte yer yok", gerekce)
        uygun, _, gerekce = yerel_modeller.sigar_mi(7.6, self.DONANIM, self.depolama(2, 40))
        self.assertFalse(uygun)
        self.assertIn("D:", gerekce)
        self.assertTrue(yerel_modeller.sigar_mi(1.5, self.DONANIM, self.depolama(2))[0])

    def test_sistem_payi(self):
        self.assertEqual(yerel_modeller._ayrilacak_gb(111, True), 3.33)
        self.assertEqual(yerel_modeller._ayrilacak_gb(1000, True), 10.0)
        self.assertEqual(yerel_modeller._ayrilacak_gb(50, False), 1.0)

    def test_hf_isleme(self):
        ham = [
            {"id": "q/Qwen2.5-Coder-1.5B-Instruct-GGUF", "downloads": 10,
             "gguf": {"total": 1_500_000_000, "context_length": 32768},
             "siblings": [{"rfilename": "m-q8_0.gguf"}, {"rfilename": "m-q4_k_m.gguf"}]},
            {"id": "x/Model-abliterated-GGUF", "gguf": {"total": 1e9},
             "siblings": [{"rfilename": "a.Q4_K_M.gguf"}]},
            {"id": "x/NoQuant-GGUF", "gguf": {"total": 1e9},
             "siblings": [{"rfilename": "a.IQ2_XS.gguf"}]},
            {"id": "x/Parcali-GGUF", "gguf": {"total": 7e10},
             "siblings": [{"rfilename": "b-Q4_K_M-00001-of-00002.gguf"},
                          {"rfilename": "b-Q4_K_M-00002-of-00002.gguf"}]},
            {"id": "x/NoSize-GGUF", "gguf": {}, "siblings": []},
        ]
        sonuc = yerel_modeller.hf_isle(ham)
        self.assertEqual(len(sonuc), 1)
        m = sonuc[0]
        self.assertEqual(m["ad"], "q/Qwen2.5-Coder-1.5B-Instruct-GGUF/m-q4_k_m.gguf")
        self.assertEqual(m["dosya"], "m-q4_k_m.gguf")
        self.assertTrue(m["kodlama"])
        self.assertEqual(m["parametre_b"], 1.5)

    def test_oneriler_donanim_ve_depolamaya_gore(self):
        def model(ad, b, indirme, kod=False):
            return {"ad": f"{ad}/m.gguf", "dosya": "m.gguf", "depo": ad, "baslik": ad,
                    "parametre_b": b, "nicem": "Q4_K_M",
                    "boyut_gb": yerel_modeller.model_boyutu_gb(b), "baglam": 0, "mimari": "",
                    "indirme": indirme, "begeni": 0, "kodlama": kod, "sayfa": ""}
        katalog = [model("a/Kucuk-1B", 1.0, 100), model("a/Kod-1.5B", 1.5, 50, True),
                   model("a/Orta-3B", 3.0, 80), model("a/Buyuk-8B", 8.0, 500),
                   model("a/Buyuk2-7B", 7.0, 300), model("a/Dev-70B", 70.0, 900),
                   model("a/Dev2-14B", 14.0, 400)]

        def oner(kullanilabilir):
            with mock.patch.object(yerel_modeller, "_katalog_yukle",
                                   return_value=(katalog, "internet")), \
                    mock.patch.object(yerel_modeller, "donanim_bilgisi",
                                      return_value=self.DONANIM), \
                    mock.patch.object(yerel_modeller, "depolama_analizi",
                                      return_value=self.depolama(kullanilabilir)):
                return yerel_modeller.onerilen_modeller()

        o = oner(100)
        hafif = [m["depo"] for m in o["hafif"]]
        buyuk = [m["depo"] for m in o["buyuk"]]
        self.assertEqual(hafif[0], "a/Kod-1.5B")  # kodlama modeli öne
        self.assertEqual(len(hafif), 3)
        self.assertNotIn("a/Dev-70B", buyuk)       # 8 GB RAM'e sığmaz
        self.assertNotIn("a/Dev2-14B", buyuk)
        self.assertEqual(buyuk[:2], ["a/Buyuk-8B", "a/Buyuk2-7B"])
        # Diskte 3 GB varsa 7–8B modeller (≈4,5 GB) önerilmez.
        o = oner(3)
        self.assertTrue(all(m["boyut_gb"] <= 3 for m in o["hafif"] + o["buyuk"]))
        self.assertNotIn("a/Buyuk-8B", [m["depo"] for m in o["buyuk"]])
        self.assertFalse(o["hepsi_sigar"])

    def test_gecersiz_model_kimligi(self):
        for kimlik in ("x; rm -rf /", "../a/b.gguf", "a/b/../../c.gguf", "a/b/c.exe"):
            self.assertFalse(yerel_modeller.model_indir(kimlik)["ok"], kimlik)

    def test_motor_yokken_sunucu_turkce_hata(self):
        with mock.patch.object(yerel_modeller, "etkin_motor", return_value=None):
            yerel_modeller.sunucuyu_durdur()
            with self.assertRaises(yerel_modeller.YerelAIHatasi) as h:
                yerel_modeller.sunucu_url()
        self.assertIn("motoru kurulu değil", str(h.exception))

    def test_sunucu_yalnizca_model_klasorunu_acar(self):
        from turkod_ide import yerel_sunucu
        dizin = tempfile.mkdtemp()
        try:
            with open(os.path.join(dizin, "a.gguf"), "wb") as f:
                f.write(b"x")
            yerel_sunucu.ARG = yerel_sunucu._arglar(["--paket", dizin, "--modeller", dizin])
            self.assertEqual(yerel_sunucu.model_listesi(), ["a.gguf"])
            self.assertEqual(yerel_sunucu.model_yolu("a.gguf"), os.path.join(dizin, "a.gguf"))
            for kotu in ("../a.gguf", "C:\\Windows\\win.ini", "yok.gguf", "a.txt"):
                with self.assertRaises(FileNotFoundError):
                    yerel_sunucu.model_yolu(kotu if kotu != "../a.gguf" else "../x.gguf")
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)


class KabukTestleri(unittest.TestCase):
    def kabuk(self, girdi):
        # Kullanıcı kodunun yazdır() çıktısı da kabuk çıktısıyla aynı akışa gider.
        cikis = io.StringIO()
        with contextlib.redirect_stdout(cikis):
            k = kabuk.TurKodKabugu(io.StringIO(girdi), cikis)
            k.calis()
        return cikis.getvalue()

    def test_komut_algilama(self):
        self.assertEqual(kabuk.komut_mu("yardım"), ("yardım", ""))
        self.assertEqual(kabuk.komut_mu("ders 3"), ("ders", "3"))
        self.assertEqual(kabuk.komut_mu(".calistir a.trpy"), ("çalıştır", "a.trpy"))
        self.assertIsNone(kabuk.komut_mu("ders = 3"))
        self.assertIsNone(kabuk.komut_mu("yazdır(1)"))
        self.assertIsNone(kabuk.komut_mu("sürüm()"))

    def test_kod_ve_blok_calisir(self):
        cikti = self.kabuk('x = [1, Doğru]\nx\neğer x:\n    yazdır("evet")\n\nçıkış\n')
        self.assertIn("[1, Doğru]", cikti)
        self.assertIn("evet", cikti)

    def test_oturumda_tanimlanan_ad_cevrilmez(self):
        # "kare" sözlükte başka bir şeye çevrilir; kullanıcı tanımladıysa çevrilmemeli.
        cikti = self.kabuk("fonksiyon kare(a):\n    döndür a * a\n\nkare(9)\nçıkış\n")
        self.assertIn("81", cikti)
        self.assertNotIn("HATA", cikti)

    def test_turkce_hata(self):
        cikti = self.kabuk("1 / 0\nçıkış\n")
        self.assertIn("[HATA] Sıfıra Bölme Hatası", cikti)

    def test_dersler_gecerli_turkod(self):
        from turkod_ide.converter import turkce_kodu_donustur
        for d in kabuk.DERSLER:
            compile(turkce_kodu_donustur(d["ornek"]), d["baslik"], "exec")

    def test_bos_satir_istemi_yinelemez(self):
        # IDE terminali / yapıştırma: boş satır yansımaz; istem aynı satırda
        # ikinci kez basılmamalı ("TürKod> TürKod>").
        cikti = self.kabuk('yazdır(3 + 4)\n\nyazdır(1)\nçıkış\n')
        self.assertNotIn("TürKod> TürKod>", cikti)
        self.assertIn("7", cikti)
        self.assertIn("1", cikti)

    def test_bastaki_bosluk_hata_vermez(self):
        cikti = self.kabuk("  yazdır(3 + 4)\nçıkış\n")
        self.assertIn("7", cikti)
        self.assertNotIn("HATA", cikti)

    def test_blok_ciktisi_istemle_ayni_satira_yapismaz(self):
        cikti = self.kabuk("için i içinde aralık(2):\n    yazdır(i)\n\nçıkış\n")
        self.assertNotIn("...> 0", cikti)
        self.assertIn("\n0\n1", cikti)

    def test_anlam(self):
        cikti = self.kabuk("anlam yazdır\nanlam while\nçıkış\n")
        # Çocuklar için: Python karşılığı değil, editördeki açıklama gösterilir.
        self.assertIn("yazdır: Verilen değerleri", cikti)
        self.assertNotIn("Python: print", cikti)
        self.assertIn("TürKod'da döngü yazılır", cikti)


class KomutSatiriTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix="turkod_cli_test_")
        self.dosya = os.path.join(self.dizin, "a.trpy")
        with open(self.dosya, "w", encoding="utf-8") as f:
            f.write("x = 1\nyazdr(x)\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def calistir(self, *argv):
        cikis = io.StringIO()
        with contextlib.redirect_stdout(cikis), contextlib.redirect_stderr(cikis), \
                mock.patch.object(calistirici, "_konsol_hazirla"):
            kod = calistirici.cli_main(list(argv))
        return kod, cikis.getvalue()

    def test_yardim_yeni_komutlari_listeler(self):
        kod, cikti = self.calistir("--yardim")
        self.assertEqual(kod, 0)
        for k in ("--duzelt", "--kontrol", "kabuk", "--kabuk-pencere"):
            self.assertIn(k, cikti)

    def test_python_cevirisi(self):
        kod, cikti = self.calistir("--python", self.dosya)
        self.assertEqual(kod, 0)
        self.assertIn("x = 1", cikti)

    def test_duzelt_yaz(self):
        kod, _ = self.calistir("--duzelt", self.dosya, "--yaz")
        self.assertEqual(kod, 0)
        with open(self.dosya, encoding="utf-8") as f:
            self.assertIn("yazdır(x)", f.read())

    def test_bilinmeyen_secenek(self):
        kod, cikti = self.calistir("--yok-boyle")
        self.assertEqual(kod, 2)
        self.assertIn("Bilinmeyen seçenek", cikti)


class AyarTestleri(unittest.TestCase):
    def test_saglayici_anahtarlari_sifrelenir(self):
        from turkod_ide import settings as ayarlar_modulu
        dizin = tempfile.mkdtemp()
        try:
            with mock.patch("os.path.expanduser", return_value=dizin):
                a = ayarlar_modulu.AyarlarYoneticisi()
                a.set("ai_api_anahtarlari", {"groq": "gsk-gizli"})
                with open(a.dosya_yolu, encoding="utf-8") as f:
                    disk = json.load(f)
                if sys.platform == "win32":
                    self.assertTrue(disk["ai_api_anahtarlari"]["groq"].startswith("dpapi:"))
                self.assertEqual(ayarlar_modulu.AyarlarYoneticisi()
                                 .get("ai_api_anahtarlari"), {"groq": "gsk-gizli"})
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
