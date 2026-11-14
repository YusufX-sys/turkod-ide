"""Tırnak içindeki seçenek DEĞERLERİNİN Türkçe karşılıkları.

Sözlük yalnızca adları çevirir; metinlerin içine (haklı olarak) dokunmaz.
Bu yüzden kaplumbağada kalem_rengi("mavi"), şekil("kaplumbağa"),
hız("en_hızlı"); tkinter'da arkaplan_rengi="mavi", kabartma="çökük" gibi
değerler kütüphaneye olduğu gibi gidip "bad color name" / "unknown shape"
hatası veriyordu. Ters yönde de (Python -> TürKod) pencolor("blue")
"kalem_rengi("blue")" olarak İngilizce kalıyordu.

Burada iki yön için TEK tablo tutulur:
  * calisma_tablolari(): çalıştırıcıya gömülür; kütüphane fonksiyonları
    Türkçe değeri İngilizcesine çevirerek çağrılır (runner.py yamaları).
  * ters_degerleri_cevir(): Python -> TürKod çevirisinde, bilinen çağrı
    bağlamlarındaki İngilizce değerleri Türkçeleştirir. Üretilen her Türkçe
    değer çalışma anında geri tanındığından çeviri gidiş-dönüş güvenlidir.
Her tabloda ilk yazılan Türkçe ad kanoniktir (ters çeviride o seçilir).
"""

import re

# Türkçe renk adı -> Tk / CSS / matplotlib / Pillow'da geçerli İngilizce ad.
RENKLER = {
    "kırmızı": "red",
    "yeşil": "green",
    "mavi": "blue",
    "beyaz": "white",
    "siyah": "black",
    "gri": "gray",
    "sarı": "yellow",
    "turuncu": "orange",
    "mor": "purple",
    "pembe": "pink",
    "kahverengi": "brown",
    "turkuaz": "turquoise",
    "lacivert": "navy",
    "altın": "gold",
    "gümüş": "silver",
    "bordo": "maroon",
    "eflatun": "violet",
    "menekşe": "violet",
    "camgöbeği": "cyan",
    "macenta": "magenta",
    "fuşya": "fuchsia",
    "açık_mavi": "lightblue",
    "koyu_mavi": "darkblue",
    "gök_mavisi": "skyblue",
    "gece_mavisi": "midnightblue",
    "kraliyet_mavisi": "royalblue",
    "çelik_mavisi": "steelblue",
    "açık_yeşil": "lightgreen",
    "koyu_yeşil": "darkgreen",
    "orman_yeşili": "forestgreen",
    "deniz_yeşili": "seagreen",
    "limon_yeşili": "lime",
    "çimen_yeşili": "lawngreen",
    "zeytin_yeşili": "olive",
    "açık_gri": "lightgray",
    "koyu_gri": "darkgray",
    "açık_pembe": "lightpink",
    "koyu_kırmızı": "darkred",
    "kızıl": "crimson",
    "koyu_turuncu": "darkorange",
    "koyu_mor": "darkviolet",
    "çivit": "indigo",
    "lila": "plum",
    "orkide": "orchid",
    "bej": "beige",
    "fildişi": "ivory",
    "haki": "khaki",
    "somon": "salmon",
    "mercan": "coral",
    "domates": "tomato",
    "çikolata": "chocolate",
    "şeftali": "peachpuff",
    "kar": "snow",
    "deniz_kabuğu": "seashell",
    "toprak": "sienna",
    "camgöbeği_mavisi": "teal",
    "gri_mavi": "slategray",
}

# İngilizce yazımın eş anlamlıları (ters çeviri bunları da tanır).
_INGILIZCE_ES_ADLAR = {
    "grey": "gray", "lightgrey": "lightgray", "darkgrey": "darkgray",
    "aqua": "cyan", "slategrey": "slategray",
}

# --- kaplumbağa (turtle) ---
SEKILLER = {
    "kaplumbağa": "turtle",
    "ok": "arrow",
    "daire": "circle",
    "çember": "circle",
    "kare": "square",
    "üçgen": "triangle",
    "klasik": "classic",
    "boş": "blank",
}

HIZLAR = {
    "en_hızlı": "fastest",
    "hızlı": "fast",
    "normal": "normal",
    "yavaş": "slow",
    "en_yavaş": "slowest",
}

# kaplumbağa yaz(..., hizala=...) ve tkinter justify.
HIZALAR = {
    "sol": "left",
    "orta": "center",
    "sağ": "right",
    "sola": "left",
    "ortada": "center",
    "ortala": "center",
    "merkez": "center",
    "sağa": "right",
}

# Yazı tipi biçimleri: ("Arial", 16, "kalın"), "Arial 12 kalın italik".
YAZI_BICIMLERI = {
    "normal": "normal",
    "kalın": "bold",
    "italik": "italic",
    "eğik": "italic",
    "altı_çizili": "underline",
    "üstü_çizili": "overstrike",
}

# Klavye tuşları: ekran.tuşa_basınca(fonksiyon, "yukarı").
TUSLAR = {
    "yukarı": "Up",
    "aşağı": "Down",
    "sol": "Left",
    "sağ": "Right",
    "boşluk": "space",
    "enter": "Return",
    "giriş": "Return",
    "esc": "Escape",
    "kaçış": "Escape",
    "geri_sil": "BackSpace",
    "sil": "Delete",
    "sekme": "Tab",
}

KIPLER = {
    "standart": "standard",
    "logo": "logo",
    "dünya": "world",
}

# --- tkinter seçenek değerleri (seçenek adı -> değer tablosu) ---
KABARTMALAR = {
    "düz": "flat",
    "kabarık": "raised",
    "çökük": "sunken",
    "oluklu": "groove",
    "sırtlı": "ridge",
    "katı": "solid",
    "çıkık": "raised",
    "gömük": "sunken",
}

DURUMLAR = {
    "normal": "normal",
    "devre_dışı": "disabled",
    "etkin": "active",
    "salt_okunur": "readonly",
    "gizli": "hidden",
    "pasif": "disabled",
    "aktif": "active",
}

YANLAR = {
    "üst": "top",
    "alt": "bottom",
    "sol": "left",
    "sağ": "right",
    "üstte": "top",
    "altta": "bottom",
    "solda": "left",
    "sağda": "right",
}

DOLGULAR = {
    "her_ikisi": "both",
    "yok": "none",
    "ikisi": "both",
}

YONLER = {
    "kuzey": "n",
    "güney": "s",
    "doğu": "e",
    "batı": "w",
    "kuzeydoğu": "ne",
    "kuzeybatı": "nw",
    "güneydoğu": "se",
    "güneybatı": "sw",
    "merkez": "center",
    "orta": "center",
}

SARMALAR = {
    "kelime": "word",
    "karakter": "char",
    "yok": "none",
    "harf": "char",
}

YONELIMLER = {
    "yatay": "horizontal",
    "dikey": "vertical",
}

SECIM_KIPLERI = {
    "tek": "single",
    "gözat": "browse",
    "çoklu": "multiple",
    "genişletilmiş": "extended",
}

BIRLESIKLER = {
    "üst": "top",
    "alt": "bottom",
    "sol": "left",
    "sağ": "right",
    "orta": "center",
    "yok": "none",
}

IMLECLER = {
    "el": "hand2",
    "ok": "arrow",
    "bekle": "watch",
    "artı": "crosshair",
    "metin": "xterm",
}

# Tk'de renk alan seçenekler.
TK_RENK_SECENEKLERI = (
    "bg", "fg", "background", "foreground",
    "activebackground", "activeforeground", "disabledforeground",
    "disabledbackground", "readonlybackground",
    "highlightbackground", "highlightcolor", "insertbackground",
    "selectbackground", "selectforeground", "selectcolor", "troughcolor",
    "outline", "activefill", "activeoutline", "disabledfill", "disabledoutline",
)

# "fill": tuvalde renk, pack()'te x/y/both/none; ikisi birlikte aranır.
TK_SECENEKLERI = {
    "relief": KABARTMALAR,
    "overrelief": KABARTMALAR,
    "state": DURUMLAR,
    "side": YANLAR,
    "fill": {**DOLGULAR, **RENKLER},
    "anchor": YONLER,
    "justify": HIZALAR,
    "wrap": SARMALAR,
    "orient": YONELIMLER,
    "selectmode": SECIM_KIPLERI,
    "compound": BIRLESIKLER,
    "cursor": IMLECLER,
}
for _secenek in TK_RENK_SECENEKLERI:
    TK_SECENEKLERI[_secenek] = RENKLER

# matplotlib renk anahtar kelimeleri (ters çeviri için).
MPL_RENK_SECENEKLERI = (
    "color", "c", "facecolor", "edgecolor", "fc", "ec", "ecolor",
    "markerfacecolor", "markeredgecolor", "mfc", "mec",
)

_TR_KUCUK = str.maketrans({"İ": "i", "I": "ı"})
_ASCII = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
})


def ad_normallestir(yazi):
    """'Açık Mavi', 'açık-mavi', 'AÇIK MAVİ' -> 'açık_mavi'."""
    yazi = yazi.strip().translate(_TR_KUCUK).lower()
    return re.sub(r"[\s\-]+", "_", yazi)


def _genislet(tablo):
    """Normalleştirilmiş adla birlikte ASCII ('acik_mavi') ve bitişik
    ('açıkmavi') yazımları da ekler; kanonik yazımlar ezilmez."""
    sonuc = dict(tablo)
    for tr, en in tablo.items():
        for takma in (tr.translate(_ASCII), tr.replace("_", ""),
                      tr.translate(_ASCII).replace("_", "")):
            sonuc.setdefault(takma, en)
    return sonuc


def calisma_tablolari():
    """Çalıştırıcıya gömülecek tablolar (yalnızca düz dict/str/tuple)."""
    return {
        "renk": _genislet(RENKLER),
        "sekil": _genislet(SEKILLER),
        "hiz": _genislet(HIZLAR),
        "hiza": _genislet(HIZALAR),
        "bicim": _genislet(YAZI_BICIMLERI),
        "tus": _genislet(TUSLAR),
        "kip": _genislet(KIPLER),
        "tk": {ad: _genislet(t) for ad, t in TK_SECENEKLERI.items()},
    }


# ---------------------------------------------------------------------
# Ters yön: Python -> TürKod
# ---------------------------------------------------------------------

def _ters(tablo, es_adlar=None):
    ters = {}
    for tr, en in tablo.items():
        ters.setdefault(en, tr)
    for es, asil in (es_adlar or {}).items():
        if asil in ters:
            ters.setdefault(es, ters[asil])
    return ters


_TERS_RENK = _ters(RENKLER, _INGILIZCE_ES_ADLAR)
_TERS_SEKIL = _ters(SEKILLER)
_TERS_HIZ = _ters(HIZLAR)
_TERS_HIZA = _ters(HIZALAR)
_TERS_BICIM = _ters(YAZI_BICIMLERI)
_TERS_TUS = _ters(TUSLAR)
_TERS_KIP = _ters(KIPLER)
_TERS_TK = {ad: _ters(t, _INGILIZCE_ES_ADLAR if t is RENKLER else None)
            for ad, t in TK_SECENEKLERI.items()}
_TERS_TK["fill"] = {**_TERS_RENK, **_ters(DOLGULAR)}


def _renk_anahtari(yazi):
    return yazi.strip().lower().replace(" ", "").replace("_", "")


_YT = r"\x00METIN_(\d+)\x00"
_YT_LISTESI = rf"({_YT}(?:\s*,\s*{_YT})*)"
_DUZ_METIN = re.compile(r"""^([rRuU]?)(['"])(.*)\2$""", re.S)
_KUTUPHANE = re.compile(
    r"^[ \t]*(?:import|from)[ \t]+(turtle|tkinter|matplotlib|PIL|pygame)\b", re.M)


def ters_degerleri_cevir(gecici_kod, metinler):
    """Python kodunda (metinler yer tutucuya alınmışken) bilinen çağrıların
    İngilizce değerlerini Türkçeleştirir. metinler: {uid: kaynak_metin};
    yerinde güncellenir. Yalnızca ilgili kütüphane içe aktarılmışsa çalışır;
    başka bir kütüphanenin color="blue" değeri Türkçeleşip bozulmaz."""
    kutuphaneler = set(_KUTUPHANE.findall(gecici_kod))
    if not kutuphaneler:
        return

    def cevir(uid, tablo, anahtar=str.strip):
        uid = int(uid)
        kaynak = metinler.get(uid)
        if kaynak is None:
            return
        m = _DUZ_METIN.match(kaynak)
        if not m or "\\" in m.group(3) or m.group(2) * 3 in kaynak:
            return
        tr = tablo.get(anahtar(m.group(3)))
        if tr is not None:
            metinler[uid] = f"{m.group(1)}{m.group(2)}{tr}{m.group(2)}"

    def konumsal(desen, tablo, anahtar=str.strip):
        for m in re.finditer(desen + r"\(\s*" + _YT_LISTESI + r"\s*[,)]", gecici_kod):
            for uid in re.findall(_YT, m.group(1)):
                cevir(uid, tablo, anahtar)

    def anahtar_kelime(adlar, tablolar, anahtar=str.strip):
        desen = r"(?<![\w.])(" + "|".join(adlar) + r")\s*=\s*" + _YT + r"(?=\s*[,)\n])"
        for m in re.finditer(desen, gecici_kod):
            cevir(m.group(2), tablolar[m.group(1)], anahtar)

    def yazi_tipi_bicimi():
        # font=("Arial", 16, "bold") -> ("Arial", 16, "kalın")
        desen = r"\bfont\s*=\s*\(\s*" + _YT + r"\s*,\s*[^,()]+,\s*" + _YT
        for m in re.finditer(desen, gecici_kod):
            cevir(m.group(2), _TERS_BICIM)

    if "turtle" in kutuphaneler:
        konumsal(r"\b(?:pencolor|fillcolor|bgcolor|color)", _TERS_RENK, _renk_anahtari)
        konumsal(r"\bshape", _TERS_SEKIL)
        konumsal(r"\bspeed", _TERS_HIZ)
        konumsal(r"\bmode", _TERS_KIP)
        anahtar_kelime(["shape"], {"shape": _TERS_SEKIL})
        anahtar_kelime(["align"], {"align": _TERS_HIZA})
        for m in re.finditer(
                r"\bonkey(?:press|release)?\(\s*[^,()]+,\s*" + _YT, gecici_kod):
            cevir(m.group(1), _TERS_TUS, lambda y: y)
        yazi_tipi_bicimi()
    if "tkinter" in kutuphaneler:
        renkli = [ad for ad, t in TK_SECENEKLERI.items() if t is RENKLER] + ["fill"]
        anahtar_kelime(renkli, _TERS_TK, _renk_anahtari)
        anahtar_kelime([ad for ad in TK_SECENEKLERI if ad not in renkli], _TERS_TK)
        yazi_tipi_bicimi()
    if "matplotlib" in kutuphaneler:
        anahtar_kelime(MPL_RENK_SECENEKLERI,
                       dict.fromkeys(MPL_RENK_SECENEKLERI, _TERS_RENK), _renk_anahtari)
    if "PIL" in kutuphaneler:
        anahtar_kelime(["fill", "outline"],
                       {"fill": _TERS_RENK, "outline": _TERS_RENK}, _renk_anahtari)
        for m in re.finditer(r"\bImage\.new\(\s*[^,()]+,\s*(?:\([^()]*\)|[\w.]+)\s*,\s*"
                             + _YT, gecici_kod):
            cevir(m.group(1), _TERS_RENK, _renk_anahtari)
    if "pygame" in kutuphaneler:
        konumsal(r"(?:\.fill|\bColor)", _TERS_RENK, _renk_anahtari)
        for m in re.finditer(r"\bdraw\.\w+\(\s*[\w.]+\s*,\s*" + _YT, gecici_kod):
            cevir(m.group(1), _TERS_RENK, _renk_anahtari)
