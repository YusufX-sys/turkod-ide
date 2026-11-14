"""Kodi'nin kalıcı sohbeti ve hafızası (ağ kullanılmaz)."""
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
    from turkod_ide import kodi, kodi_hafiza  # noqa: E402

DEEPSEEK = {"saglayici": "deepseek", "model": "deepseek-chat"}


class HafizaTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        self.h = kodi_hafiza.KodiHafizasi(self.dizin)

    def tearDown(self):
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_sohbet_kaydedilir_ve_yuklenir(self):
        mesajlar = [{"kodiden": True, "metin": "Merhaba, ben Kodi!"},
                    {"kodiden": False, "metin": "Adım Ece"},
                    {"kodiden": True, "metin": "Memnun oldum Ece!"}]
        self.h.sohbet_kaydet(mesajlar)
        self.assertEqual(kodi_hafiza.KodiHafizasi(self.dizin).sohbet_yukle(), mesajlar)
        self.h.sohbet_sil()
        self.assertEqual(self.h.sohbet_yukle(), [])

    def test_eski_tek_sohbet_tasinir_selam_kaydedilmez(self):
        os.makedirs(self.dizin, exist_ok=True)
        with open(os.path.join(self.dizin, "kodi_sohbet.json"), "w", encoding="utf-8") as f:
            f.write('{"mesajlar": [{"kodiden": false, "metin": "Eski soru"}]}')
        self.assertEqual(self.h.sohbet_yukle()[0]["metin"], "Eski soru")
        self.assertFalse(os.path.exists(os.path.join(self.dizin, "kodi_sohbet.json")))
        self.h.yeni_sohbet()
        self.assertEqual(self.h.sohbet_kaydet([{"kodiden": True, "metin": "Merhaba!"}]), 0)
        self.assertEqual(len(self.h.sohbetler()), 1)

    def test_en_fazla_200_mesaj(self):
        self.h.sohbet_kaydet([{"kodiden": False, "metin": str(i)} for i in range(250)])
        yuklenen = self.h.sohbet_yukle()
        self.assertEqual(len(yuklenen), 200)
        self.assertEqual(yuklenen[-1]["metin"], "249")

    def test_gecmis_kullaniciyla_baslar_hatalar_atilir(self):
        g = kodi_hafiza.KodiHafizasi.gecmis_kur([
            {"kodiden": True, "metin": "Merhaba, ben Kodi!"},
            {"kodiden": False, "metin": "Selam"},
            {"kodiden": True, "metin": "Eyvah", "hata": True},
            {"kodiden": True, "metin": "Selam sana!"},
        ])
        self.assertEqual([m["role"] for m in g], ["user", "assistant"])
        self.assertEqual(g[1]["content"], "Selam sana!")

    def test_notlar(self):
        self.assertEqual(self.h.not_ekle("Adı Ece"), (True, "eklendi"))
        self.assertEqual(self.h.not_ekle("adı ece"), (True, "zaten biliyorum"))
        self.assertEqual(self.h.not_ekle("En sevdiği renk mor"), (True, "eklendi"))
        self.assertEqual([n["metin"] for n in self.h.notlar()], ["Adı Ece", "En sevdiği renk mor"])
        self.assertEqual(self.h.not_sil("renk"), 1)
        self.assertEqual([n["metin"] for n in self.h.notlar()], ["Adı Ece"])
        self.assertIn("Adı Ece", self.h.istem_metni())
        self.assertEqual(self.h.not_sil(hepsi=True), 1)
        self.assertEqual(self.h.notlar(), [])

    def test_ozel_bilgi_hatirlanmaz(self):
        for metin in ("Şifresi kedi123", "Telefonu 0532 123 45 67", "E-postası ece@ornek.com",
                      "Adresi Çiçek Sokak", "TC kimlik 12345678901"):
            with self.subTest(metin=metin):
                self.assertEqual(self.h.not_ekle(metin), (False, "özel bilgi"))
        self.assertEqual(self.h.notlar(), [])

    def test_eylem_dogrulama(self):
        _, eylemler = kodi.eylemleri_ayir(
            '```eylem\n{"eylem": "hatirla", "not": "Adı Ece"}\n'
            '{"eylem": "unut", "not": "renk"}\n{"eylem": "hatirla", "not": ""}\n```')
        self.assertEqual(eylemler, [{"eylem": "hatirla", "not": "Adı Ece"},
                                    {"eylem": "unut", "not": "renk"}])

    def test_eski_sohbet_temizligi_etkin_sohbeti_silmez(self):
        # Sınır aşılınca en eski sohbet silinir; kullanıcı en eski sohbeti
        # açıp yazdıysa eskiden az önce kaydedilen etkin sohbet siliniyordu.
        mesaj = [{"kodiden": False, "metin": "soru"}]
        adlar = ["20200101-000000-%03d" % i for i in range(kodi_hafiza.EN_FAZLA_SOHBET + 1)]
        for no in adlar:
            self.h._sohbet_dosyasi_yaz(no, mesaj)
        self.h.sohbet_yukle(adlar[0])  # en eskisi etkin
        self.h.sohbet_kaydet(mesaj + [{"kodiden": True, "metin": "cevap"}])
        self.assertTrue(os.path.exists(self.h._sohbet_yolu(adlar[0])))
        self.assertFalse(os.path.exists(self.h._sohbet_yolu(adlar[1])))
        self.assertEqual(len(self.h.sohbetler()), kodi_hafiza.EN_FAZLA_SOHBET)


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
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _sor(self, soru, cevap):
        with mock.patch("turkod_ide.ai.sohbet_ayrintili",
                        return_value={"cevap": cevap, "dusunce": ""}) as s, \
                contextlib.redirect_stdout(io.StringIO()):
            return self.c.kodi_sor(soru), s

    def test_hatirla_eylemi_motorda_uygulanir(self):
        r, _ = self._sor("Adım Ece", 'Memnun oldum Ece!\n```eylem\n{"eylem": "hatirla", "not": "Adı Ece"}\n```')
        self.assertEqual(r["eylemler"], [{"eylem": "hatirla", "not": "Adı Ece",
                                          "_durum": "yapildi", "_sonuc": "Hatırladım: Adı Ece"}])
        self.assertEqual([n["metin"] for n in self.c.kodi_hafizasi.notlar()], ["Adı Ece"])
        # Sonraki soruda hafıza sistem mesajında (sabit kısmın sonunda).
        _, s = self._sor("Beni hatırlıyor musun?", "Tabii, Ece!")
        self.assertIn("- Adı Ece", s.call_args.kwargs["sistem"])

    def test_hafiza_kapaliysa_hatirlamaz(self):
        self.c.ayarlar.ayarlar["kodi_hafiza"] = False
        r, s = self._sor("Adım Ece", 'Tamam!\n```eylem\n{"eylem": "hatirla", "not": "Adı Ece"}\n```')
        self.assertEqual(r["eylemler"][0]["_durum"], "hata")
        self.assertEqual(self.c.kodi_hafizasi.notlar(), [])
        self.assertNotIn("HAFIZAN", s.call_args.kwargs["sistem"])

    def test_sohbet_yuklenince_gecmis_kurulur(self):
        self.c.kodi_sohbet_kaydet([{"kodiden": True, "metin": "Merhaba, ben Kodi!"},
                                   {"kodiden": False, "metin": "Döngü nedir?"},
                                   {"kodiden": True, "metin": "Tekrar tekrar yapmaktır."}])
        self.c.kodi_gecmisi.clear()
        r = self.c.kodi_sohbet_yukle()
        self.assertEqual(len(r["mesajlar"]), 3)
        self.assertEqual([m["content"] for m in self.c.kodi_gecmisi],
                         ["Döngü nedir?", "Tekrar tekrar yapmaktır."])
        self.c.kodi_temizle()
        self.assertEqual(self.c.kodi_sohbet_yukle()["mesajlar"], [])

    def test_kayit_kapaliysa_yazilmaz(self):
        self.c.kodi_sohbet_kaydet([{"kodiden": False, "metin": "a"}])
        self.c.ayarlar.ayarlar["kodi_sohbet_kaydet"] = False
        self.assertFalse(self.c.kodi_sohbet_kaydet([{"kodiden": False, "metin": "b"}])["kaydedildi"])
        # Açılışta eski sohbet geri gelmez; eskiler panelde durur, oradan silinir.
        self.assertEqual(self.c.kodi_sohbet_yukle()["mesajlar"], [])
        self.assertEqual(len(self.c.kodi_sohbetler()["sohbetler"]), 1)

    def test_coklu_sohbet(self):
        self.c.kodi_sohbet_kaydet([{"kodiden": False, "metin": "Döngü nedir?"},
                                   {"kodiden": True, "metin": "Tekrar etmektir."}])
        self.c.kodi_temizle()  # yeni sohbet; eskisi kalır
        self.assertEqual(self.c.kodi_gecmisi, [])
        self.c.kodi_sohbet_kaydet([{"kodiden": False, "metin": "Liste nedir?"}])
        liste = self.c.kodi_sohbetler()["sohbetler"]
        self.assertEqual([s["baslik"] for s in liste], ["Liste nedir?", "Döngü nedir?"])
        self.assertTrue(liste[0]["etkin"])
        eski = liste[1]["no"]
        r = self.c.kodi_sohbet_yukle(eski)
        self.assertEqual(r["mesajlar"][0]["metin"], "Döngü nedir?")
        self.assertEqual([m["content"] for m in self.c.kodi_gecmisi],
                         ["Döngü nedir?", "Tekrar etmektir."])
        self.assertEqual(self.c.kodi_sohbetler()["sohbetler"][1]["etkin"], True)
        self.c.kodi_sohbet_sil(eski)
        self.assertEqual(self.c.kodi_gecmisi, [])
        self.assertEqual([s["baslik"] for s in self.c.kodi_sohbetler()["sohbetler"]],
                         ["Liste nedir?"])
        self.c.kodi_sohbet_sil(hepsi=True)
        self.assertEqual(self.c.kodi_sohbetler()["sohbetler"], [])
        self.assertFalse(self.c.kodi_sohbet_yukle("olmayan")["ok"])

    def test_kodi_hafiza_ayarlarini_degistiremez(self):
        baglam = {"ayarlar": {"kodi_hafiza": {"ad": "x", "tur": "bool", "deger": True}}}
        _, eylemler = kodi.eylemleri_ayir(
            '```eylem\n{"eylem": "ayar", "ad": "kodi_hafiza", "deger": false}\n'
            '{"eylem": "ayar", "ad": "kodi_sohbet_kaydet", "deger": false}\n```', baglam)
        self.assertEqual(eylemler, [])


if __name__ == "__main__":
    unittest.main()
