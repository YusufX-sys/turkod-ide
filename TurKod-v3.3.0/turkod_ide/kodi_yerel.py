"""Kodi'nin yapay zekâsız kipi: hazır kısa işler.

YALNIZCA HİÇ YAPAY ZEKÂ BAĞLI DEĞİLKEN çağrılır (ide_core.kodi_sor). Yapay
zekâ bağlıyken her istek ona gider; bu çözücü hiç çalışmaz, isteğe karışmaz
(eskiden önce bu çalışıyor, bir anahtar kelimeye takılıp isteğin yalnızca bir
parçasını yapıyordu: "tarayıcıda reponu aç" → yalnızca tarayıcı açılırdı).

"Terminali aç", "Kod Parçacıkları eklentisini etkinleştir", "EXE'ye dönüştürme
panelini aç", "mini haritayı kapat", "temayı açık yap", "yazıyı büyüt" gibi
açık, tek işlik istekleri yapar. Yapay zekâ olmadığından sayfaya bakıp devam
etmez, birden çok işli isteği hiç ele almaz (yarım iş yapmaz).

Temkinlidir; şunlarda hiçbir şey yapmaz (Kodi yapay zekâ gerektiğini söyler):
- soru sözcüğü varsa ("nasıl", "nedir", "nerede", ayrı yazılmış "mı" ...),
- birden çok iş istendiyse ("ve", "sonra" ...) ya da cümle uzunsa,
- açık bir fiil yoksa ya da hedefin bütün kelimeleri eşleşmiyorsa,
- iki farklı hedef aynı ölçüde eşleşiyorsa.
"""
import re

try:
    from . import kodi as kodi_bilgisi
except ImportError:  # pragma: no cover - doğrudan çalıştırma
    import kodi as kodi_bilgisi

EN_FAZLA_KELIME = 9

_SORU = ("nasıl", "nedir", "neden", "niçin", "niye", "nerede", "nereye", "nereden", "hangi",
         "hangisi", "kaç", "kim", "nelerdir", "neler", "ne", "anlat", "açıkla", "açıklar",
         "öğret", "yardım")
_SORU_EKI = {"mı", "mi", "mu", "mü"}
_BIRDEN_COK = {"ve", "sonra", "ardından", "ama", "ayrıca", "hem", "da", "de", "yaz",
               "yazar", "yazsana", "çalıştır", "kaydet"}

_AC = re.compile(r"^(aç|açar|açsana|açıver|açın|açabilir|açabilirsin|açalım|açarmısın|"
                 r"göster|gösterir|göstersene|gösterir|getir|getirir|getirsene|başlat)$")
_KAPAT = re.compile(r"^(kapat|kapatır|kapatsana|kapatıver|kapatın|kapatabilir|"
                    r"kapatabilirsin|kapatalım|gizle|gizler|gizlesene)$")
_ETKIN = re.compile(r"^(etkinleştir|etkinleştirir|etkinleştirsene|etkinleştirebilir|"
                    r"aktif|aktifleştir|aktifleştirir|yükle|yükler|kur|kurar)$")
_PASIF = re.compile(r"^(pasif|pasifleştir|deaktif|kaldır|kaldırır|kaldırsana)$")
_BUYUT = re.compile(r"^büyüt")
_KUCULT = re.compile(r"^küçült")
_YAP = re.compile(r"^(yap|yapar|yapsana|yapıver|geç|geçir|değiştir|çevir)$")
_NEZAKET = {"mısın", "misin", "musun", "müsün", "lütfen", "hadi", "bi", "bir",
            "bana", "benim", "için", "şunu", "şu", "bu"}

# Hedef adlarında eşleşme aranmayan sözcükler.
_DOLGU = {"ve", "ile", "bir", "aç", "kapat", "yan", "yana"}

# Bazı komutların kullanıcıların söylediği başka adları.
_TAKMA_ADLAR = {
    "run.exe": [["exe"]],
    "run.exe_kaynak": [["exe", "kaynak"]],
    "view.keybindings": [["kısayol"]],
    "view.palette": [["komut", "palet"]],
    "view.problems": [["sorun"]],
    "view.split": [["editör", "böl"]],
    "learn.book": [["kitap"]],
    "learn.docs": [["dokümantasyon"], ["belge", "site"]],
    "tools.shell": [["kabuk"]],
    "tools.local_models": [["yerel", "model"]],
    "tools.codesearch": [["kod", "arama"]],
    "tools.stats": [["istatistik"]],
    "tools.todo": [["yapılacak"]],
    "help.tour": [["arayüz", "tur"]],
    "help.about": [["hakkında"]],
    "update.check": [["güncelle"]],
}
_PANELLER = {
    "gezgin": [["gezgin"], ["dosya", "gezgin"]],
    "eklentiler": [["eklenti", "özellik"], ["eklentiler", "panel"]],
    "ai": [["ai", "asistan"], ["ai", "panel"], ["yapay", "zeka", "panel"], ["asistan"]],
    "terminal": [["terminal"]],
}
# Panelleri açıp kapatan komutlar (yerine panel eylemi kullanılır).
_PANEL_KOMUTLARI = {"view.explorer", "view.ai", "view.terminal", "view.extensions"}
_AYAR_TAKMA = {"kodi_sesli": [["sesli", "cevap"], ["sesli", "oku"]],
               "minimap": [["mini", "harita"]],
               "sutun_cizgileri": [["girinti", "kılavuz"]]}
# Aynı ölçüde eşleşen farklı türden hedeflerde öncelik (büyük olan kazanır).
_ONCELIK = {"ayarlar_ac": 5, "eklenti": 4, "ayar": 3, "panel": 2, "komut": 1}


def _normal(metin):
    m = str(metin or "").replace("İ", "i").replace("I", "ı").lower()
    for a, b in (("â", "a"), ("î", "i"), ("û", "u"), ("’", " "), ("'", " ")):
        m = m.replace(a, b)
    return m


def _kelimeler(metin):
    return re.findall(r"[a-zçğıöşü0-9]+", _normal(metin))


def _adin_kelimeleri(ad):
    ad = re.sub(r"\([^)]*\)", " ", str(ad or ""))
    ad = ad.replace("Aç/Kapat", " ")
    return [k for k in _kelimeler(ad) if k not in _DOLGU and len(k) >= 2]


def _eslesir(ad_kelimesi, kelime):
    if len(ad_kelimesi) <= 3:
        return kelime == ad_kelimesi or (kelime.startswith(ad_kelimesi)
                                         and len(kelime) - len(ad_kelimesi) <= 4)
    # Ünsüz yumuşaması (kitap → kitabı, renk → rengi): son harf karşılaştırılmaz.
    return kelime.startswith(ad_kelimesi[:min(5, len(ad_kelimesi) - 1)])


def _puan(adlar, kelimeler):
    """Adlardan birinin bütün kelimeleri soruda varsa kelime sayısı; yoksa 0."""
    en_iyi = 0
    for ad in adlar:
        if ad and all(any(_eslesir(a, k) for k in kelimeler) for a in ad):
            en_iyi = max(en_iyi, len(ad))
    return en_iyi


def _soru_mu(ham, kelimeler):
    if any(k in _SORU_EKI for k in kelimeler):
        return True
    if any(k in _SORU for k in kelimeler):
        return True
    return "?" in ham and not any(k in ("mısın", "misin", "musun", "müsün") for k in kelimeler)


def _fiil(kelimeler):
    """("ac" | "kapat" | "etkin" | "pasif" | "buyut" | "kucult" | "yap", kelime) ya da None."""
    metin = " ".join(kelimeler)
    if "devre dışı" in metin:
        return "pasif"
    bulunan = []
    for k in kelimeler:
        for ad, desen in (("etkin", _ETKIN), ("pasif", _PASIF), ("kapat", _KAPAT),
                          ("ac", _AC), ("buyut", _BUYUT), ("kucult", _KUCULT), ("yap", _YAP)):
            if desen.match(k):
                bulunan.append(ad)
                break
    turler = set(bulunan)
    if len(turler) != 1:
        return None
    return bulunan[0]


def _hedefler(baglam):
    """[(tür, kimlik, ad, [ad kelimeleri listeleri], ek)]"""
    hedefler = []
    for p, adlar in _PANELLER.items():
        hedefler.append(("panel", p, kodi_bilgisi.PANEL_ADLARI.get(p, p), adlar, None))
    for kimlik, ad, izinsiz in kodi_bilgisi._komut_listesi(baglam):
        if not izinsiz or kimlik in _PANEL_KOMUTLARI:
            continue
        adlar = [_adin_kelimeleri(ad)] + _TAKMA_ADLAR.get(kimlik, [])
        hedefler.append(("komut", kimlik, ad, adlar, None))
    for e in kodi_bilgisi._liste(baglam, "eklentiler"):
        if isinstance(e, dict) and e.get("id"):
            adlar = [_adin_kelimeleri(e.get("ad")), _adin_kelimeleri(str(e["id"]).replace("_", " "))]
            hedefler.append(("eklenti", str(e["id"]), str(e.get("ad") or e["id"]), adlar, e))
    for k, ad in kodi_bilgisi._ayar_bolumleri(baglam).items():
        hedefler.append(("ayarlar_ac", k, str(ad), [["ayar"] + _adin_kelimeleri(ad)], None))
    for k, a in kodi_bilgisi._ayar_listesi(baglam).items():
        if isinstance(a, dict) and a.get("tur") == "bool":
            adlar = [_adin_kelimeleri(a.get("ad"))] + _AYAR_TAKMA.get(k, [])
            hedefler.append(("ayar", k, str(a.get("ad") or k), adlar, a))
    return hedefler


def _sonuc(cevap, eylem, baglam):
    g = kodi_bilgisi._dogrula(eylem, baglam)
    if g:
        # Bu çözücü yalnızca yapay zekâ yokken çalışır: sayfaya bakıp devam
        # edecek kimse yoktur.
        g.pop("devam", None)
    return {"cevap": cevap, "eylemler": [g]} if g else None


def _tema_ya_da_yazi(kelimeler, fiil, baglam):
    ayarlar = kodi_bilgisi._ayar_listesi(baglam)
    if any(k.startswith("tema") for k in kelimeler) and fiil in ("yap", "ac") \
            and isinstance(ayarlar.get("tema"), dict):
        en_iyi, secilen = 0, None
        for t in ayarlar["tema"].get("secenekler") or []:
            p = _puan([_adin_kelimeleri(t)], [k for k in kelimeler if not k.startswith("tema")])
            if p > en_iyi:
                en_iyi, secilen = p, t
        if secilen:
            return _sonuc(f"Hemen temayı **{secilen}** yapıyorum!",
                          {"eylem": "ayar", "ad": "tema", "deger": secilen}, baglam)
    if fiil in ("buyut", "kucult") and any(k.startswith("yazı") for k in kelimeler):
        anahtar = "terminal_yazi_boyutu" if any(k.startswith("terminal") for k in kelimeler) \
            else "yazi_boyutu"
        a = ayarlar.get(anahtar)
        if not isinstance(a, dict):
            return None
        try:
            simdi = int(a.get("deger") or (13 if anahtar.startswith("terminal") else 14))
        except (TypeError, ValueError):
            return None
        yeni = simdi + 2 if fiil == "buyut" else simdi - 2
        yeni = max(int(a.get("min") or 8), min(int(a.get("max") or 32), yeni))
        return _sonuc(f"Yazıyı {'büyütüyorum' if fiil == 'buyut' else 'küçültüyorum'}!",
                      {"eylem": "ayar", "ad": anahtar, "deger": yeni}, baglam)
    return None


_UZANTILAR = {"trpy", "py", "md", "txt", "json", "csv", "pdf"}


def _gövde_kelimeleri(dosya_adi):
    """"oyun_2.trpy" -> ["oyun", "2"] (uzantısız adın kelimeleri)."""
    ad = str(dosya_adi or "").replace("\\", "/").rsplit("/", 1)[-1]
    govde = ad.rsplit(".", 1)[0] if "." in ad else ad
    return [k for k in _kelimeler(govde) if k]


def _sekme_ya_da_dosya(kelimeler, fiil, baglam):
    """"merhaba.trpy sekmesine geç", "notlar.md dosyasını aç": açık sekmeye
    geçer ya da proje dosyasını açar. Ad tam eşleşmeli ve "sekme" / "dosya"
    sözcüğü ya da bir dosya uzantısı söylenmiş olmalı."""
    if fiil not in ("ac", "yap") or not isinstance(baglam, dict):
        return None
    sekme_dendi = any(k.startswith("sekme") for k in kelimeler)
    dosya_dendi = any(k.startswith("dosya") for k in kelimeler) or \
        any(k in _UZANTILAR for k in kelimeler)
    if not (sekme_dendi or dosya_dendi):
        return None
    adaylar = []
    for ad in kodi_bilgisi._liste(baglam, "sekmeler"):
        g = _gövde_kelimeleri(ad)
        if g and all(any(k == x or (len(x) > 3 and k.startswith(x)) for k in kelimeler) for x in g):
            adaylar.append(("sekme", str(ad), len(g)))
    if not adaylar and fiil == "ac":
        for ad in kodi_bilgisi._liste(baglam, "dosyalar"):
            if str(ad).endswith("/"):
                continue
            g = _gövde_kelimeleri(ad)
            if g and all(any(k == x or (len(x) > 3 and k.startswith(x)) for k in kelimeler)
                         for x in g):
                adaylar.append(("dosya_ac", str(ad), len(g)))
    if not adaylar:
        return None
    adaylar.sort(key=lambda a: -a[2])
    if len(adaylar) > 1 and adaylar[1][2] == adaylar[0][2]:
        return None  # aynı adlı birden çok dosya / sekme: yapay zekâ sorsun
    tur, ad, _ = adaylar[0]
    if tur == "sekme":
        return _sonuc(f"Hemen **{ad}** sekmesine geçiyorum!", {"eylem": "sekme", "ad": ad}, baglam)
    return _sonuc(f"Hemen **{ad}** dosyasını açıyorum!", {"eylem": "dosya_ac", "dosya": ad}, baglam)


_SITE = re.compile(r"\b((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|dev|ai|edu|gov|tr|"
                   r"co|app|info)(?:\.tr)?)\b")
_BILINEN_SITELER = {"google": "google.com", "youtube": "youtube.com", "vikipedi": "tr.wikipedia.org",
                    "wikipedia": "wikipedia.org", "github": "github.com"}


def _site(ham, kelimeler, fiil, baglam):
    """"google'ı aç", "youtube.com'u aç": tarayıcıda site açılır."""
    if fiil != "ac":
        return None
    m = _SITE.search(_normal(ham).replace("'", " "))
    adres = m.group(1) if m else None
    if adres is None:
        hedef = [k for k in kelimeler if _fiil([k]) is None and k not in _NEZAKET
                 and len(k) > 1 and not k.startswith(("sayfa", "site", "web"))]
        if len(hedef) == 1:
            for ad, site in _BILINEN_SITELER.items():
                if hedef[0].startswith(ad):
                    adres = site
    if adres is None:
        return None
    return _sonuc(f"Hemen açıyorum: **{adres}**!",
                  {"eylem": "tarayici", "islem": "ac", "adres": adres}, baglam)


_ARAMA = (
    # "Google'da kedi resimleri ara (ve ilk sonuca tıkla)"
    re.compile(r"^(?:google'?(?:da|de|dan)?|internette|webde|web'?de)\s+(?P<sorgu>.+?)\s+"
               r"(?:ara|arat|aratır\s*mısın|arar\s*mısın|arasana|aratsana)"
               r"(?:\s+ve\s+(?P<devam>.+?))?[.!]*$", re.I),
    # "kedi resimlerini Google'da ara (ve ...)"
    re.compile(r"^(?P<sorgu>.+?)\s+(?:google'?(?:da|de)|internette|web'?de)\s+"
               r"(?:ara|arat|aratır\s*mısın|arar\s*mısın|arasana|aratsana)"
               r"(?:\s+ve\s+(?P<devam>.+?))?[.!]*$", re.I),
)


def _google_arama(ham, baglam):
    """"Google'da X ara": tarayıcıda aranır. Arkasından bir iş daha istendiyse
    ("ve ilk sonuca tıkla") hiç ele alınmaz: yapay zekâ olmadan isteğin
    yalnızca bir parçası yapılırdı."""
    for desen in _ARAMA:
        m = desen.match(ham.strip())
        if not m:
            continue
        if m.group("devam"):
            return None
        sorgu = m.group("sorgu").strip(" '\"")
        if not sorgu or len(sorgu) > 200:
            return None
        return _sonuc(f"Google'da **{sorgu}** arıyorum!",
                      {"eylem": "tarayici", "islem": "ara", "sorgu": sorgu}, baglam)
    return None


def coz(mesaj, baglam=None):
    """Mesaj açık, tek işlik bir komutsa {"cevap", "eylemler"}; değilse None."""
    # Baştaki hitap ("Kodi, ...") virgül sayılmasın.
    ham = re.sub(r"^\s*kodi\s*[,!:]\s*", "", str(mesaj or "").strip(), flags=re.I)
    kelimeler = _kelimeler(ham)
    if kelimeler and not _soru_mu(ham, kelimeler):
        arama = _google_arama(ham, baglam)
        if arama:
            return arama
    if not kelimeler or len(kelimeler) > EN_FAZLA_KELIME:
        return None
    if "," in ham or ";" in ham or _soru_mu(ham, kelimeler):
        return None
    if any(k in _BIRDEN_COK for k in kelimeler):
        return None
    fiil = _fiil(kelimeler)
    if fiil is None:
        return None
    hedef_kelimeleri = [k for k in kelimeler if k not in _NEZAKET and _fiil([k]) is None]
    if not hedef_kelimeleri:
        return None

    ozel = (_tema_ya_da_yazi(kelimeler, fiil, baglam) or _sekme_ya_da_dosya(kelimeler, fiil, baglam)
            or _site(ham, kelimeler, fiil, baglam))
    if ozel or fiil in ("buyut", "kucult", "yap"):
        return ozel

    adaylar = []
    for tur, kimlik, ad, adlar, ek in _hedefler(baglam):
        p = _puan(adlar, hedef_kelimeleri)
        if p:
            adaylar.append((p, _ONCELIK[tur], tur, kimlik, ad, ek))
    if not adaylar:
        return None
    adaylar.sort(key=lambda x: (-x[0], -x[1]))
    en = adaylar[0]
    if len(adaylar) > 1 and adaylar[1][:2] == en[:2] and adaylar[1][3] != en[3]:
        return None  # belirsiz: iki farklı hedef aynı ölçüde uyuyor
    _, _, tur, kimlik, ad, ek = en

    if tur == "panel":
        if fiil not in ("ac", "kapat"):
            return None
        return _sonuc("Hemen açıyorum!" if fiil == "ac" else "Tamam, kapatıyorum!",
                      {"eylem": "panel", "panel": kimlik, "durum": fiil}, baglam)
    if tur == "komut":
        if fiil != "ac":
            return None
        return _sonuc(f"Hemen açıyorum: **{ad.rstrip('…').strip()}**!",
                      {"eylem": "komut", "id": kimlik}, baglam)
    if tur == "ayarlar_ac":
        if fiil != "ac":
            return None
        return _sonuc(f"Ayarlar'da **{ad}** bölümünü açıyorum!",
                      {"eylem": "ayarlar_ac", "bolum": kimlik}, baglam)
    if tur == "eklenti":
        etkin = bool(ek and ek.get("etkin"))
        if fiil in ("etkin",) or (fiil == "ac" and not (ek and ek.get("acilir"))):
            durum = "ac"
            cevap = (f"**{ad}** zaten etkin, kullanıma hazır!" if etkin
                     else f"Tamam, **{ad}** eklentisini etkinleştiriyorum!")
        elif fiil in ("pasif", "kapat"):
            durum = "kapat"
            cevap = (f"Peki, **{ad}** eklentisini kapatıyorum." if etkin
                     else f"**{ad}** zaten kapalı.")
        elif fiil == "ac":
            durum, cevap = "calistir", f"Hemen açıyorum: **{ad}**!"
        else:
            return None
        return _sonuc(cevap, {"eylem": "eklenti", "id": kimlik, "durum": durum}, baglam)
    if tur == "ayar":
        if fiil in ("ac", "etkin"):
            deger = True
        elif fiil in ("kapat", "pasif"):
            deger = False
        else:
            return None
        if ek and ek.get("deger") is deger:
            return _sonuc(f"**{ad}** zaten {'açık' if deger else 'kapalı'}!",
                          {"eylem": "ayar", "ad": kimlik, "deger": deger}, baglam)
        return _sonuc(f"Tamam, **{ad}** {'açılıyor' if deger else 'kapanıyor'}!",
                      {"eylem": "ayar", "ad": kimlik, "deger": deger}, baglam)
    return None
