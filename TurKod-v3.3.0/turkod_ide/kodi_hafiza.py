"""Kodi'nin kalıcı sohbeti ve hafızası.

- Sohbetler: her sohbet ayrı bir dosyadır (~/.turkod/kodi_sohbetler/<no>.json).
  Kodi'nin Sohbetler panelinde listelenir; yenisi açılır, eskisine dönülür,
  silinir. Program yeniden açılınca son sohbet kaldığı yerden sürer.
- Hafıza: Kodi'nin kullanıcı hakkında hatırladığı kısa notlar
  (~/.turkod/kodi_hafiza.json): adı, yaşı, sevdiği şeyler, öğrenme hedefi.
  Kullanıcı "bunu hatırla" ya da kendisi hakkında kalıcı bir şey söyleyince
  Kodi not alır; "unut" deyince siler. Ayarlar → Kodi'den görülür, silinir.

Gizlilik: şifre, adres, telefon, e-posta gibi özel bilgiler hiç kaydedilmez.
"""
import json
import os
import re
import tempfile
import threading
import time

EN_FAZLA_MESAJ = 200
EN_FAZLA_SOHBET = 100
BASLIK_SINIRI = 48
EN_FAZLA_NOT = 30
NOT_SINIRI = 200
# Yapay zekâya giden geçmiş (kaydedilmiş sohbetten kurulurken).
GECMIS_ADET = 6
GECMIS_KIRP = 1200

_OZEL = re.compile(
    r"(şifre|sifre|parola|password|adres|adresim|telefon|numaram|tc\s*kimlik|kimlik\s*no|"
    r"kredi\s*kart|iban|@|\d{6,}|\d{3}[\s-]\d{3}[\s-]\d{2})", re.I)


def ozel_bilgi_mi(metin):
    """Kaydedilmemesi gereken özel bilgi içeriyor mu?"""
    return bool(_OZEL.search(str(metin or "")))


def _kucuk(metin):
    return str(metin or "").replace("İ", "i").replace("I", "ı").lower().strip()


class KodiHafizasi:
    def __init__(self, klasor=None):
        self.klasor = klasor or os.path.join(os.path.expanduser("~"), ".turkod")
        self._kilit = threading.Lock()

    # ---------------------------------------------------------------- dosya
    def _yol(self, ad):
        return os.path.join(self.klasor, ad)

    def _oku(self, ad, varsayilan):
        try:
            with open(self._yol(ad), encoding="utf-8") as f:
                veri = json.load(f)
            return veri if isinstance(veri, type(varsayilan)) else varsayilan
        except (OSError, ValueError):
            return varsayilan

    def _yaz(self, ad, veri):
        os.makedirs(self.klasor, exist_ok=True)
        fd, gecici = tempfile.mkstemp(prefix="." + ad + ".", suffix=".tmp", dir=self.klasor)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(veri, f, ensure_ascii=False)
            os.replace(gecici, self._yol(ad))
        except OSError:
            try:
                os.remove(gecici)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------- sohbetler
    def _klasor(self):
        return os.path.join(self.klasor, "kodi_sohbetler")

    def _sohbet_yolu(self, no):
        no = re.sub(r"[^0-9a-z_-]", "", str(no or "").lower())
        return os.path.join(self._klasor(), no + ".json") if no else ""

    def _etkin_oku(self):
        try:
            with open(os.path.join(self._klasor(), "etkin.txt"), encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    def _etkin_yaz(self, no):
        os.makedirs(self._klasor(), exist_ok=True)
        with open(os.path.join(self._klasor(), "etkin.txt"), "w", encoding="utf-8") as f:
            f.write(no or "")

    def _tasi(self):
        """Eski tek sohbet dosyası (kodi_sohbet.json) ilk sohbet olur."""
        eski = self._yol("kodi_sohbet.json")
        if not os.path.exists(eski):
            return
        veri = self._oku("kodi_sohbet.json", {})
        mesajlar = veri.get("mesajlar") if isinstance(veri, dict) else None
        try:
            if mesajlar:
                no = self._yeni_no()
                self._sohbet_dosyasi_yaz(no, [m for m in mesajlar if isinstance(m, dict)])
                self._etkin_yaz(no)
            os.remove(eski)
        except OSError:
            pass

    @staticmethod
    def _yeni_no():
        return time.strftime("%Y%m%d-%H%M%S") + "-%03d" % (int(time.time() * 1000) % 1000)

    @staticmethod
    def baslik_bul(mesajlar):
        for m in mesajlar:
            if not m.get("kodiden"):
                metin = " ".join(str(m.get("metin") or "").split())
                if metin:
                    return metin if len(metin) <= BASLIK_SINIRI else metin[:BASLIK_SINIRI - 1] + "…"
        return "Yeni sohbet"

    def _sohbet_dosyasi_yaz(self, no, mesajlar):
        os.makedirs(self._klasor(), exist_ok=True)
        temiz = [m for m in (mesajlar or []) if isinstance(m, dict)][-EN_FAZLA_MESAJ:]
        veri = {"surum": 1, "no": no, "baslik": self.baslik_bul(temiz),
                "guncelleme": time.strftime("%Y-%m-%d %H:%M"), "mesajlar": temiz}
        fd, gecici = tempfile.mkstemp(prefix=".sohbet.", suffix=".tmp", dir=self._klasor())
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(veri, f, ensure_ascii=False)
            os.replace(gecici, self._sohbet_yolu(no))
        except OSError:
            try:
                os.remove(gecici)
            except OSError:
                pass
            raise
        return len(temiz)

    def _sohbet_oku(self, no):
        yol = self._sohbet_yolu(no)
        if not yol:
            return None
        try:
            with open(yol, encoding="utf-8") as f:
                veri = json.load(f)
        except (OSError, ValueError):
            return None
        return veri if isinstance(veri, dict) else None

    def sohbetler(self):
        """[{no, baslik, guncelleme, mesaj_sayisi, etkin}] (en yeni başta)."""
        with self._kilit:
            self._tasi()
            etkin = self._etkin_oku()
            liste = []
            try:
                adlar = os.listdir(self._klasor())
            except OSError:
                adlar = []
            for ad in adlar:
                if not ad.endswith(".json"):
                    continue
                veri = self._sohbet_oku(ad[:-5])
                if not veri:
                    continue
                mesajlar = veri.get("mesajlar") or []
                liste.append({"no": ad[:-5], "baslik": veri.get("baslik") or "Sohbet",
                              "guncelleme": veri.get("guncelleme") or "",
                              "mesaj_sayisi": len(mesajlar), "etkin": ad[:-5] == etkin})
        liste.sort(key=lambda s: (s["guncelleme"], s["no"]), reverse=True)
        return liste

    def etkin_sohbet(self):
        with self._kilit:
            self._tasi()
            return self._etkin_oku()

    def sohbet_yukle(self, no=None):
        """Bir sohbetin mesajları (no yoksa etkin sohbet); onu etkin yapar."""
        with self._kilit:
            self._tasi()
            no = no or self._etkin_oku()
            veri = self._sohbet_oku(no) if no else None
            if veri is None:
                return []
            self._etkin_yaz(no)
        mesajlar = veri.get("mesajlar") or []
        return [m for m in mesajlar if isinstance(m, dict)][-EN_FAZLA_MESAJ:]

    def sohbet_kaydet(self, mesajlar):
        """Etkin sohbete yazar (yoksa yenisini açar). Kullanıcının hiç yazmadığı
        (yalnızca selamdan oluşan) sohbet kaydedilmez."""
        temiz = [m for m in (mesajlar or []) if isinstance(m, dict)]
        if not any(not m.get("kodiden") and str(m.get("metin") or "").strip() for m in temiz):
            return 0
        with self._kilit:
            self._tasi()
            no = self._etkin_oku()
            if not no or not os.path.exists(self._sohbet_yolu(no)):
                no = self._yeni_no()
                self._etkin_yaz(no)
            sayi = self._sohbet_dosyasi_yaz(no, temiz)
            self._eskileri_sil(korunan=no)
        return sayi

    def _eskileri_sil(self, korunan=None):
        """Sınırı aşan en eski sohbetleri siler; etkin sohbet (korunan) hiç
        silinmez. Eskiden kullanıcı en eski sohbeti açıp yazınca az önce
        kaydedilen o sohbet siliniyordu."""
        try:
            adlar = sorted(a for a in os.listdir(self._klasor()) if a.endswith(".json"))
        except OSError:
            return
        fazla = len(adlar) - EN_FAZLA_SOHBET
        if fazla <= 0:
            return
        korunan_ad = (korunan + ".json") if korunan else None
        for ad in [a for a in adlar if a != korunan_ad][:fazla]:
            try:
                os.remove(os.path.join(self._klasor(), ad))
            except OSError:
                pass

    def yeni_sohbet(self):
        """Yeni (boş) sohbet: ilk mesaj yazılınca dosyası açılır."""
        with self._kilit:
            self._tasi()
            self._etkin_yaz("")
        return ""

    def sohbet_sil(self, no=None, hepsi=False):
        """Bir sohbeti (no yoksa etkin olanı) ya da hepsini siler."""
        with self._kilit:
            self._tasi()
            etkin = self._etkin_oku()
            if hepsi:
                try:
                    adlar = [a for a in os.listdir(self._klasor()) if a.endswith(".json")]
                except OSError:
                    adlar = []
            else:
                no = no or etkin
                adlar = [no + ".json"] if no else []
            for ad in adlar:
                try:
                    os.remove(os.path.join(self._klasor(), ad))
                except OSError:
                    pass
            if hepsi or (no and no == etkin):
                if os.path.isdir(self._klasor()):
                    self._etkin_yaz("")
            try:
                os.remove(self._yol("kodi_sohbet.json"))
            except OSError:
                pass

    @staticmethod
    def gecmis_kur(mesajlar):
        """Kayıtlı balon mesajlarından yapay zekâya gidecek kısa geçmiş."""
        gecmis = []
        for m in mesajlar:
            metin = str(m.get("metin") or "").strip()
            if not metin or m.get("hata"):
                continue
            gecmis.append({"role": "assistant" if m.get("kodiden") else "user",
                           "content": metin[:GECMIS_KIRP]})
        # Yapay zekâ geçmişi kullanıcıyla başlamalı (Kodi'nin selamı atılır).
        while gecmis and gecmis[0]["role"] != "user":
            gecmis.pop(0)
        gecmis = gecmis[-GECMIS_ADET:]
        while gecmis and gecmis[0]["role"] != "user":
            gecmis.pop(0)
        return gecmis

    # --------------------------------------------------------------- hafıza
    def notlar(self):
        with self._kilit:
            veri = self._oku("kodi_hafiza.json", {})
        notlar = veri.get("notlar") if isinstance(veri, dict) else None
        return [n for n in (notlar or []) if isinstance(n, dict) and n.get("metin")]

    def _notlari_yaz(self, notlar):
        self._yaz("kodi_hafiza.json", {"surum": 1, "notlar": notlar[-EN_FAZLA_NOT:]})

    def not_ekle(self, metin):
        """(eklendi mi, açıklama)."""
        metin = " ".join(str(metin or "").split())[:NOT_SINIRI]
        if not metin:
            return False, "boş not"
        if ozel_bilgi_mi(metin):
            return False, "özel bilgi"
        with self._kilit:
            notlar = self.notlar_kilitsiz()
            if any(_kucuk(n["metin"]) == _kucuk(metin) for n in notlar):
                return True, "zaten biliyorum"
            notlar.append({"metin": metin, "tarih": time.strftime("%Y-%m-%d")})
            self._notlari_yaz(notlar)
        return True, "eklendi"

    def notlar_kilitsiz(self):
        veri = self._oku("kodi_hafiza.json", {})
        notlar = veri.get("notlar") if isinstance(veri, dict) else None
        return [n for n in (notlar or []) if isinstance(n, dict) and n.get("metin")]

    def not_sil(self, metin=None, hepsi=False):
        """Silinen not sayısı. metin: notun içinde geçen ifade."""
        with self._kilit:
            notlar = self.notlar_kilitsiz()
            if hepsi:
                kalan = []
            else:
                aranan = _kucuk(metin)
                if not aranan:
                    return 0
                kalan = [n for n in notlar if aranan not in _kucuk(n["metin"])
                         and _kucuk(n["metin"]) not in aranan]
            silinen = len(notlar) - len(kalan)
            if silinen:
                self._notlari_yaz(kalan)
        return silinen

    def istem_metni(self):
        """Sistem mesajına giden hafıza bölümü."""
        notlar = self.notlar()
        satirlar = "\n".join(f"- {n['metin']}" for n in notlar[-EN_FAZLA_NOT:])
        metin = ("\nHAFIZAN (kullanıcı hakkında hatırladıkların; yeri gelince doğal kullan, her "
                 "cevapta tekrarlama):\n" + (satirlar or "- (henüz bir şey yok)") + "\n")
        metin += ("Kullanıcı kendisi hakkında kalıcı bir bilgi verirse (adı, yaşı, sevdiği şeyler, "
                  "öğrenme hedefi) ya da \"bunu hatırla\" derse cevabının sonundaki eylem bloğuna "
                  "{\"eylem\": \"hatirla\", \"not\": \"<kısa not, ör. Adı Ece>\"} ekle. \"Unut\" "
                  "derse {\"eylem\": \"unut\", \"not\": \"<neyi>\"} ekle. Şifre, adres, telefon, "
                  "e-posta gibi özel bilgileri asla hatırlama; kullanıcıya bunları kimseyle "
                  "paylaşmamasını söyle.\n")
        return metin
