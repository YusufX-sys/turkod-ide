"""TurKod <-> Python cevirici fonksiyonlar."""
import re
import warnings

from .dictionary import SOZLUK, TERS_SOZLUK, kullanici_tanimlari
from typing import Optional
from .tokenizer import tokenize, TokenTuru, TokenizerHatasi

# ---------------------------------------------------------
# 1. TABLOLAR VE SÖZLÜKLER (En üstte tanımlanmalı)
# ---------------------------------------------------------
# Satır 11-12'nin hemen altına ekle:
TR_HARF = "A-Za-z_ÇŞĞÜÖİçşğüöı"
TR_ID = rf"[{TR_HARF}][{TR_HARF}0-9]*"
TR_MODUL_ID = rf"[{TR_HARF}][{TR_HARF}0-9]*(?:\.[{TR_HARF}][{TR_HARF}0-9]*)*"


TK_SABITLER = {
    "tk.sonlandirici": "tk.END",
    ".pencere": ".Tk",
    ".etiket": ".Label",
    ".düğme": ".Button",
    ".metin_kutusu": ".Entry",
    ".metin_alani": ".Text",
    ".metin_alanı": ".Text",
    ".çerçeve": ".Frame",
    ".liste_kutusu": ".Listbox",
    ".yeni_pencere": ".Toplevel",
    ".tuval": ".Canvas",
    ".kaydırma_çubuğu": ".Scrollbar",
    ".döner_kutu": ".Spinbox",
    ".onay_düğmesi": ".Checkbutton",
    ".seçenek_düğmesi": ".Radiobutton",
    ".ölçek_kaydırıcı": ".Scale",
    ".menü": ".Menu",
    ".ileti_şablonu": ".messagebox",
    ".dosya_dialogu": ".filedialog",
    ".renk_seçici": ".colorchooser",
    ".oylayici": ".Combobox",
    ".agac_görünümü": ".Treeview",
    ".not_defteri": ".Notebook",
    ".ilerleme_çubuğu": ".Progressbar",
    ".başlık_grafik": ".title",
    ".getir": ".get",
    ".yok_et": ".destroy",
    ".ana_döngü": ".mainloop",
    ".sonra": ".after",
    ".yerleştir": ".place",
    ".paketle": ".pack",
    ".ızgarala": ".grid",
    ".boyutlandır": ".geometry",
    ".pencere_boyutu": ".geometry",
    ".geometri": ".geometry",
    ".ikon_resmi": ".iconbitmap",
    ".odaklan": ".focus",
    ".pencere_kapatma_protokolu": ".protocol",
    ".yapılandır": ".configure",
    ".ayarla": ".config",
}

TK_PARAMLER = {
    "xml_metin": "text",
    "metin": "text",
    "komut": "command",
    "değişken": "variable",
    "metin_değişkeni": "textvariable",
    "genişlik": "width",
    "yükseklik": "height",
    "arkaplan_rengi": "bg",
    "ön_renk": "foreground",
    "ön_renk_kısa": "fg",
    "metin_rengi": "fg",
    "yazı_tipi": "font",
    "x_kenar_boslugu": "padx",
    "y_kenar_boslugu": "pady",
    "x_dolgu": "ipadx",
    "y_dolgu": "ipady",
    "kenar": "anchor",
    "hizala": "justify",
    "sarma": "wrap",
    "durum": "state",
    "yapışkan": "sticky",
    "satır_no": "row",
    "sütun_no": "column",
    "satır_uzanımı": "rowspan",
    "sütun_uzanımı": "columnspan",
    "kabartma": "relief",
}

MODUL_CEVIRILERI = {
    "matematik": "math",
    "ursina_kütüphanesi": "ursina",
    "matematikf": "math",
    "rastgele": "random",
    "tarih_saat": "datetime",
    "işletim_sistemi": "os",
    "sistem": "sys",
    "json": "json",
    "desen": "re",
    "kaplumbaga": "turtle",
    "istatistik": "statistics",
    "fonksiyon_araclari": "functools",
    "yol_kütüphanesi": "pathlib",
    "özet_kütüphanesi": "hashlib",
    "serilestirici": "pickle",
    "güvenli_sir": "secrets",
    "çöp_toplayıcı": "gc",
    "hata_izleme": "traceback",
    "zayıf_bağ": "weakref",
    "takvim": "calendar",
    "sembolik_matematik": "sympy",
    "bilimsel_hesaplama": "scipy",
    "kesirler": "fractions",
    "inceleme": "inspect",
    "alt_süreç": "subprocess",
    "iş_parçacığı": "threading",
    "çoklu_işlem": "multiprocessing",
    "veritabanı_sqlite": "sqlite3",
    "django_uygulaması": "django",
    "pytest_kütüphanesi": "pytest",
    "tensorflow_kütüphanesi": "tensorflow",
    "torch_kütüphanesi": "torch",
    "redis_kütüphanesi": "redis",
    "docker_kütüphanesi": "docker",
    "coverage_kütüphanesi": "coverage",
    "py_oyun": "pygame",
}

MODUL_METOTLARI = {
    "rastgele": {
        "seç": "choice",
        "tamsayı": "randint",
        "ondalık": "random",
        "karıştır": "shuffle",
        "örneklem": "sample",
        "aralıkta_rastgele": "randrange",
        "tohum": "seed",
        "bit": "getrandbits",
        "durum_al": "getstate",
        "durum_ayarla": "setstate",
        "dağılım_düzgün": "uniform",
        "dağılım_beta": "betavariate",
        "dağılım_üstel": "expovariate",
        "dağılım_gamma": "gammavariate",
        "dağılım_gauss": "gauss",
        "dağılım_lognormal": "lognormvariate",
        "dağılım_normal": "normalvariate",
        "dağılım_üçgen": "triangular",
    },
    "matematik": {
        "karekök": "sqrt",
        "faktoriyel": "factorial",
        "ebob": "gcd",
        "ekok": "lcm",
        "tabana_yuvarla": "floor",
        "tavana_yuvarla": "ceil",
        "mutlak_değer": "fabs",
        "hipotenüs": "hypot",
        "logaritma": "log",
        "sinüs": "sin",
        "kosinüs": "cos",
        "tanjant": "tan",
        "açı_derece": "degrees",
        "açı_radyan": "radians",
        "pi_sayısı": "pi",
        "e_sayısı": "e",
        "sonsuz": "inf",
        "tanım_değil": "nan",
        "arkkosinüs": "acos",
        "arkkosinüs_h": "acosh",
        "arksinüs": "asin",
        "arksinüs_h": "asinh",
        "arktanjant": "atan",
        "arktanjant2": "atan2",
        "arktanjant_h": "atanh",
        "kombinasyon": "comb",
        "işaret_kopyala": "copysign",
        "kosinüs_h": "cosh",
        "mesafe": "dist",
        "hata_fonksiyonu": "erf",
        "hata_fonksiyonu_t": "erfc",
        "üst_eksi_1": "expm1",
        "mod": "fmod",
        "kesirli_üst": "frexp",
        "toplam_hassas": "fsum",
        "gamma_fonk": "gamma",
        "yakınsa": "isclose",
        "sonlu_mu": "isfinite",
        "sonsuz_mu": "isinf",
        "tanım_değil_mi": "isnan",
        "tamsayı_kök": "isqrt",
        "kesirli_çarp": "ldexp",
        "gamma_log": "lgamma",
        "logaritma10": "log10",
        "logaritma_eksi_1": "log1p",
        "logaritma2": "log2",
        "kesirli_ayir": "modf",
        "sonraki_say": "nextafter",
        "permutasyon": "perm",
        "çarpım": "prod",
        "kalan": "remainder",
        "sinüs_h": "sinh",
        "tanjant_h": "tanh",
        "kırp_sıfır": "trunc",
        "sonraki_ulp": "ulp",
    },
    "matematikf": {
        "tabana_yuvarla": "floor",
        "tavana_yuvarla": "ceil",
        "mutlak_değer": "abs",
        "yuvarla": "round",
        "karekök_al": "sqrt",
        "üst_al": "pow",
        "sinüs_al": "sin",
        "kosinüs_al": "cos",
        "tanjant_al": "tan",
        "ark_sinüs": "asin",
        "ark_kosinüs": "acos",
        "ark_tanjant": "atan",
        "üstel_al": "exp",
        "logaritma_al": "log",
        "pi_sayısı": "pi",
        "e_sayısı": "e",
        "en_küçük_değer": "min",
        "en_büyük_değer": "max",
        "radyan_derece": "degrees",
        "derece_radyan": "radians",
    },
    "py_oyun": {
        # Pygame Temel
        "oyun_başlat": "init",
        "oyun_kapat": "quit",
        "ekran_oluştur": "display.set_mode",
        "ekran_ayarla": "display.set_mode",
        "pencere_başlığı": "display.set_caption",
        "ekran_güncelle": "display.update",
        "olayları_al": "event.get",
        "çıkış_olayı": "QUIT",
        "tuş_basma_olayı": "KEYDOWN",
        "tuş_bırakma_olayı": "KEYUP",
        "basılı_tuşlar": "key.get_pressed",
        "dikdörtgen_çiz": "draw.rect",
        "çember_çiz": "draw.circle",
        "çizgi_çiz": "draw.line",
        "dikdörtgen": "Rect",
        "oyun_saati": "time.Clock",
        "bekle_ms": "time.wait",
        "fare_konumu": "mouse.get_pos",
        "yazı_tipi_oluştur": "font.SysFont",
        "tuş_a": "K_a",
        "tuş_d": "K_d",
        "tuş_w": "K_w",
        "tuş_s": "K_s",
        # Gelişmiş Ekran ve Pencere
        "ekran_cevir": "display.flip",
        "tam_ekran_yap": "display.toggle_fullscreen",
        "simge_durumuna_küçült": "display.iconify",
        "ekran_simgesi": "display.set_icon",
        # Gelişmiş Çizim (gfxdraw ve transform)
        "elips_çiz": "draw.ellipse",
        "çokgen_çiz": "draw.polygon",
        "yay_çiz": "draw.arc",
        "anti_aliaslı_çizgi": "gfxdraw.aaline",
        "anti_aliaslı_çember": "gfxdraw.aacircle",
        "yumuşak_ölçekle": "transform.smoothscale",
        "döndür_ve_ölçekle": "transform.rotozoom",
        "yatay_düşey_çevir": "transform.flip",
        # Gelişmiş Giriş Aygıtları
        "joystick_sistemi": "joystick",
        "joystick_sayısı": "joystick.get_count",
        "fare_görünür_mü": "mouse.set_visible",
        "fare_imleci": "mouse.set_cursor",
        "tuş_adı": "key.name",
        "tuş_tekrarı": "key.set_repeat",
        # Gelişmiş Ses
        "ses_kanalı": "mixer.Channel",
        "ses_kanal_sayısı": "mixer.set_num_channels",
        "ses_kıs": "mixer.fadeout",
        "müzik_süre": "mixer.music.get_pos",
        # Yüzey ve Piksel İşlemleri
        "piksel_dizisi": "PixelArray",
        "yüzey_dizisi": "surfarray",
        "ses_dizisi": "sndarray",
        "piksel_kopyala": "pixelcopy",
        # Gelişmiş Sprite ve Çarpışma
        "kirli_sprite": "DirtySprite",
        "güncellenen_grup": "RenderUpdates",
        "çember_çarpışma": "collide_circle",
        "maske_çarpışma": "collide_mask",
        # Klavye Sabitleri
        "tuş_yukarı": "K_UP",
        "tuş_aşağı": "K_DOWN",
        "tuş_sol": "K_LEFT",
        "tuş_sağ": "K_RIGHT",
        "tuş_boşluk": "K_SPACE",
        "tuş_giriş": "K_RETURN",
        "tuş_esc": "K_ESCAPE",
        # Pencere Bayrakları (Flags)
        "tam_ekran": "FULLSCREEN",
        "yeniden_boyutlandır": "RESIZABLE",
        "çerçevesiz": "NOFRAME",
        "çift_tampon": "DOUBLEBUF",
        "donanım_yüzeyi": "HWSURFACE",
        "alfa_şeffaflık": "SRCALPHA",
    },
    "tarih_saat": {
        "şimdi": "datetime.now",
        "bugün": "datetime.today",
        "utc_şimdi": "datetime.utcnow",
        "utc_damgasi": "datetime.utcfromtimestamp",
        "damga_zaman": "datetime.fromtimestamp",
        "iso_ayristir": "datetime.fromisoformat",
        "tarih_birlestir": "datetime.combine",
        "tarih_ayristir": "datetime.strptime",
        "en_büyük_tarih": "datetime.max",
        "en_küçük_tarih": "datetime.min",
        "zaman_farki": "timedelta",
        "tarih": "date",
        "zaman": "time",
        "saat_dilimi": "timezone",
        "dilim_bilgisi": "tzinfo",
    },
}

# ---------------------------------------------------------
# 2. REGEX VE TÜREV MADDELERİN DERLENMESİ
# ---------------------------------------------------------

# Üç tırnaklı bloklar tek tırnaklı olanlardan ÖNCE denenmeli; aksi halde `"""`
# iki ayrı boş string gibi eşleşip metin/kod sınırını kaydırır.
METIN_VE_YORUM_DESENI = (
    r'([rbuf]{0,2}"""(?:[^"\\]|\\.|"(?!""))*"""'
    r"|[rbuf]{0,2}'''(?:[^'\\]|\\.|'(?!''))*'''"
    r'|[rbuf]{0,2}"(?:[^"\\\n]|\\.)*"'
    r"|[rbuf]{0,2}'(?:[^'\\\n]|\\.)*'"
    r"|#[^\n]*)"
)

# f-string'ler ayrı ele alınır: düz metni korunur, `{...}` ifadeleri çevrilir.
FSTRING_DESENI = (
    rf'(?<![{TR_HARF}0-9])[rbu]?f[rbu]?"""(?:[^"\\]|\\.|"(?!""))*"""'
    rf"|(?<![{TR_HARF}0-9])[rbu]?f[rbu]?'''(?:[^'\\]|\\.|'(?!''))*'''"
    rf'|(?<![{TR_HARF}0-9])[rbu]?f[rbu]?"(?:[^"\\\n]|\\.)*"'
    rf"|(?<![{TR_HARF}0-9])[rbu]?f[rbu]?'(?:[^'\\\n]|\\.)*'"
)

_FSTRING_DESEN = re.compile(FSTRING_DESENI)

# Tek geçişte tara: önce f-string alternatifleri, sonra normal metin/yorum.
_METIN_DESEN = re.compile(f"(?:{FSTRING_DESENI})|{METIN_VE_YORUM_DESENI}")

# `{{`/`}}` kaçışları ve bir seviye iç içe süslü parantez destekli ifade bloğu.
_FSTRING_IFADE_DESEN = re.compile(r"\{\{|\}\}|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

# Geriye donuk uyumluluk: eskiden ayri (ve eksik) bir tablo olan MODUL_ISIMLERI
# artik tek kaynak olan MODUL_CEVIRILERI'ne isaret eder.
MODUL_ISIMLERI = MODUL_CEVIRILERI

def _pozisyon_hesapla(kod, satir, sutun):
    """1 tabanlı satır/sütun -> 0 tabanlı karakter pozisyonu."""
    satirlar = kod.split('\n')
    if satir < 1 or satir > len(satirlar):
        return None
    pozisyon = sum(len(s) + 1 for s in satirlar[:satir - 1])
    pozisyon += sutun - 1
    if pozisyon > len(kod):
        return None
    return pozisyon


def _token_tabanli_koruma(kod: str):
    """Tokenize ederek korunacak bölgeleri yer tutucularla değiştirir.

    String, yorum ve kullanıcı tanımları çeviri sırasında bozulmasın diye
    geçici yer tutucularla saklanır. f-string'ler mevcut regex mantığına
    bırakılır çünkü f-string içi ifadelerin ayrıca çevrilmesi gerekir.
    """
    try:
        tanimlar = kullanici_tanimlari(kod)
        tokenlar = tokenize(kod, kullanici_adlari=tanimlar)
    except Exception:
        return kod, []

    korunacak_turler = {
        TokenTuru.METIN,
        TokenTuru.YORUM,
        TokenTuru.KULLANICI,
    }

    korunacaklar = [t for t in tokenlar if t.tur in korunacak_turler]
    if not korunacaklar:
        return kod, []

    # Sondan başa sırala; böylece öndeki konumlar kaymaz.
    korunacaklar.sort(key=lambda t: (t.satir, t.sutun), reverse=True)

    saklanan = []
    sayac = 0
    kod_list = list(kod)

    for t in korunacaklar:
        bas = _pozisyon_hesapla(kod, t.satir, t.sutun)
        bit = _pozisyon_hesapla(kod, t.son_satir, t.son_sutun)

        if bas is None or bit is None or bas >= bit:
            continue

        parca = kod[bas:bit]
        uid = sayac
        sayac += 1
        saklanan.append((uid, parca))

        kod_list[bas:bit] = list(f"\x00TKOR_{uid}\x00")

    return "".join(kod_list), saklanan

_TK_PARAM_DESEN = re.compile(
    r"([,\(\s]\s*)(" + "|".join(re.escape(k) for k in sorted(TK_PARAMLER, key=len, reverse=True)) + r")(?=\s*=[^=])"
)

# Sonundaki lookahead olmazsa `.getir` deseni `.getirici` içinde de eşleşir.
_TK_SABIT_DESEN = re.compile(
    "(?:"
    + "|".join(re.escape(k) for k in sorted(TK_SABITLER, key=len, reverse=True))
    + rf")(?![{TR_HARF}0-9])"
)

_MODUL_DESEN = re.compile(
    r"\biçe_aktar\s+("
    + "|".join(re.escape(k) for k in sorted(MODUL_CEVIRILERI, key=len, reverse=True))
    + r")\b"
)

MODUL_METOT_TABLO = {}
BUILTIN_FUNCS = {"abs", "round", "min", "max", "sum", "len", "pow"}
for modul, metotlar in MODUL_METOTLARI.items():
    py_modul = MODUL_CEVIRILERI[modul]
    for tr_metot, py_metot in metotlar.items():
        if py_metot in BUILTIN_FUNCS:
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = py_metot
        elif py_metot.startswith(f"{py_modul}."):
            # Hedef zaten modül adıyla başlıyorsa (örn: datetime.max) tekrar ekleme
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = py_metot
        else:
            # Normal durum: pygame.mixer.music.get_pos veya pygame.display.set_mode
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = f"{py_modul}.{py_metot}"

_MODUL_METOT_DESEN = re.compile(
    "|".join(
        rf"\b{re.escape(k)}\b"
        for k in sorted(MODUL_METOT_TABLO, key=len, reverse=True)
    )
)

_SOZLUK_REGEX = None
_SOZLUK_TABLO = None


def _sozluk_hazirla():
    global _SOZLUK_REGEX, _SOZLUK_TABLO

    if _SOZLUK_REGEX is None:
        sirali = sorted(SOZLUK.items(), key=lambda x: len(x[0]), reverse=True)

        desen_listesi = []
        cevirme_tablosu = {}
        cakisan = []
        bicimsiz = []

        for desen, hedef in sirali:
            kelime = desen.replace(r"\b", "")
            # Arama tablosu eşleşen metne göre kurulduğu için maddeler
            # `\bkelime\b` biçiminde ve tekil olmak zorunda.
            if desen != rf"\b{kelime}\b":
                bicimsiz.append(desen)
                continue
            if kelime in cevirme_tablosu:
                if cevirme_tablosu[kelime] != hedef:
                    cakisan.append(kelime)
                continue
            desen_listesi.append(desen)
            cevirme_tablosu[kelime] = hedef

        if bicimsiz:
            warnings.warn(
                "Sözlükte `\\bkelime\\b` biçiminde olmayan ve yok sayılan maddeler var: "
                + ", ".join(bicimsiz[:10]),
                stacklevel=2,
            )
        if cakisan:
            warnings.warn(
                "Sözlükte aynı kelime birden fazla hedefe bağlanmış: " + ", ".join(cakisan[:10]),
                stacklevel=2,
            )

        _SOZLUK_REGEX = re.compile("|".join(desen_listesi))
        _SOZLUK_TABLO = cevirme_tablosu

    return _SOZLUK_REGEX, _SOZLUK_TABLO


_TERS_SOZLUK_REGEX = None
_TERS_SOZLUK_TABLO = None


def _ters_sozluk_hazirla():
    global _TERS_SOZLUK_REGEX, _TERS_SOZLUK_TABLO

    if _TERS_SOZLUK_REGEX is None:
        ters_sirali = sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True)

        desen = "|".join(
            rf"\b{re.escape(k)}\b"
            for k, _ in ters_sirali
        )

        _TERS_SOZLUK_REGEX = re.compile(desen)
        _TERS_SOZLUK_TABLO = dict(ters_sirali)

    return _TERS_SOZLUK_REGEX, _TERS_SOZLUK_TABLO


def _isimleri_sakla(kod, tanimlar):
    """Kullanıcı tanımlarını yer tutucularla değiştirir; (kod, yer_tutucu_tablosu) döner."""
    isim_sak = {}

    if not tanimlar:
        return kod, isim_sak

    isim_to_yer = {}
    isim_desen = "|".join(
        rf"\b{re.escape(isim)}\b"
        for isim in sorted(tanimlar, key=len, reverse=True)
    )

    def isim_degistir(match):
        isim = match.group(0)
        if isim not in isim_to_yer:
            yer = f"__ISIM_SABITI_{len(isim_sak)}__"
            isim_sak[yer] = isim
            isim_to_yer[isim] = yer
        return isim_to_yer[isim]

    return re.sub(isim_desen, isim_degistir, kod), isim_sak


# ---------------------------------------------------------
# 3. DÖNÜŞTÜRÜCÜ FONKSİYONLAR
# ---------------------------------------------------------

def python_kodu_turkceye_cevir(python_kodu):
    saklanan_metinler = []
    sayac = 0

    def sakla(match):
        nonlocal sayac
        uid = sayac
        sayac += 1
        saklanan_metinler.append((uid, match.group(0)))
        return f"\x00METIN_{uid}\x00"

    gecici_kod = re.sub(METIN_VE_YORUM_DESENI, sakla, python_kodu)

    PY_ID = r'[A-Za-z_][A-Za-z0-9_]*'
    tanimlar = set()
    tanimlar.update(re.findall(rf'^\s*({PY_ID})\s*=(?!=)', gecici_kod, re.MULTILINE))
    tanimlar.update(re.findall(rf'\bfor\s+({PY_ID})\s+in\b', gecici_kod))
    tanimlar.update(re.findall(rf'\bself\.({PY_ID})', gecici_kod))
    for param_blok in re.findall(rf'\bdef\s+{PY_ID}\s*\(([^)]*)\)', gecici_kod):
        for p in param_blok.split(','):
            p = p.strip().split('=')[0].strip()
            if p and p != 'self':
                tanimlar.add(p)

    gecici_kod, isim_sak = _isimleri_sakla(gecici_kod, tanimlar)
    # Ters modül metot çevirisi:
    # mathf.floor -> matematik_fonksiyonları.tabana_yuvarla
    # math.sqrt   -> matematik.karekök
    # pygame.init -> py_oyun.oyun_başlat
    ters_modul_tablo = {}

    for modul_tr, metotlar in MODUL_METOTLARI.items():
        modul_py = MODUL_CEVIRILERI.get(modul_tr, modul_tr)

        for metot_tr, metot_py in metotlar.items():
            tam_py = f"{modul_py}.{metot_py}"
            tam_tr = f"{modul_tr}.{metot_tr}"

            if tam_py not in ters_modul_tablo:
                ters_modul_tablo[tam_py] = tam_tr

    if ters_modul_tablo:
        ters_modul_sirali = sorted(ters_modul_tablo, key=len, reverse=True)

        ters_modul_desen = re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in ters_modul_sirali) + r")\b"
        )

        gecici_kod = ters_modul_desen.sub(
            lambda m: ters_modul_tablo[m.group(0)],
            gecici_kod
        )
    ters_regex, ters_tablo = _ters_sozluk_hazirla()

    gecici_kod = ters_regex.sub(
        lambda m: ters_tablo[m.group(0)],
        gecici_kod
    )


    for yer, isim in isim_sak.items():
        gecici_kod = gecici_kod.replace(yer, isim)
    for uid, metin in saklanan_metinler:
        gecici_kod = gecici_kod.replace(f"\x00METIN_{uid}\x00", metin)
    return gecici_kod

def _regex_tabanli_ceviri(turkce_kod, tanimlar=None):
    """Saf regex tabanlı çevirici. Token koruması olmadan çalışır."""
    saklanan_metinler = []
    sayac = 0

    def metni_sakla(metin):
        nonlocal sayac
        uid = sayac
        sayac += 1
        saklanan_metinler.append((uid, metin))
        return f"\x00METIN_{uid}\x00"

    def sakla(match):
        parca = match.group(0)
        if not _FSTRING_DESEN.fullmatch(parca):
            return metni_sakla(parca)
        parcalar = []
        son = 0
        for ifade in _FSTRING_IFADE_DESEN.finditer(parca):
            if parca[son:ifade.start()]:
                parcalar.append(metni_sakla(parca[son:ifade.start()]))
            govde = ifade.group(0)
            if govde in ("{{", "}}"):
                parcalar.append(govde)
            else:
                parcalar.append(
                    re.sub(METIN_VE_YORUM_DESENI, lambda m: metni_sakla(m.group(0)), govde)
                )
            son = ifade.end()
        if parca[son:]:
            parcalar.append(metni_sakla(parca[son:]))
        return "".join(parcalar)

    gecici_kod = _METIN_DESEN.sub(sakla, turkce_kod)

    gecici_kod = re.sub(
        rf"\biçe_aktar\s+tkinter_arayüz\s+olarak\s+({TR_ID})\b",
        r"import tkinter as \1",
        gecici_kod
    )

    gecici_kod = re.sub(
        r"\biçe_aktar\s+tkinter_arayüz\b",
        "import tkinter",
        gecici_kod
    )

    if tanimlar is None:
        tanimlar = kullanici_tanimlari(gecici_kod)
    gecici_kod, isim_sak = _isimleri_sakla(gecici_kod, tanimlar)

    gecici_kod = _TK_PARAM_DESEN.sub(
        lambda m: m.group(1) + TK_PARAMLER[m.group(2)],
        gecici_kod
    )

    gecici_kod = _TK_SABIT_DESEN.sub(
        lambda m: TK_SABITLER.get(m.group(0), m.group(0)),
        gecici_kod
    )

    python_kodu = re.sub(
        rf"\biçin\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+aralık\s*\(([^)]*)\)\s*:",
        r"for \1 in range(\2):",
        gecici_kod
    )
    python_kodu = re.sub(
        rf"\bdöngü\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+aralık\s*\(([^)]*)\)\s*:",
        r"for \1 in range(\2):",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\bdöngü\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+içinde\s+(.*?):",
        r"for \1 in \2:",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\biçin\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+içinde\s+(.*?):",
        r"for \1 in \2:",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\[([^]]+?)\s+için\s+({TR_ID})\s+içinde\s+(.*?)\s+eğer\s+(.*?)\]",
        r"[\1 for \2 in \3 if \4]",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\[([^]]+?)\s+için\s+({TR_ID})\s+içinde\s+([^]]+?)\]",
        r"[\1 for \2 in \3]",
        python_kodu
    )
    _ISE_BLOK = (r"\b(?!(?:eğer|değilse_eğer|değilse|döngü|için|fonksiyon|sınıf|dene|"
                 r"hata_yakala|sonunda|ile|ve|veya|değil)\b)")
    # "A B ise:" -> "A == B:"  (örn. "yaş 18 ise:" -> "yaş == 18:")
    python_kodu = re.sub(
        _ISE_BLOK + rf"({TR_ID})\s+({TR_ID}|\d+(?:\.\d+)?)\s+ise\s*:",
        r"\1 == \2:",
        python_kodu,
    )
    # "A ise:" -> "A == True:"  (örn. "hazır ise:" -> "hazır == True:")
    python_kodu = re.sub(
        _ISE_BLOK + rf"({TR_ID})\s+ise\s*:",
        r"\1 == True:",
        python_kodu,
    )
    # infix: "A ise B" -> "A == B"
    python_kodu = re.sub(r"\bise\b", "==", python_kodu)

    python_kodu = _MODUL_DESEN.sub(
        lambda m: f"import {MODUL_CEVIRILERI[m.group(1)]}",
        python_kodu
    )

    python_kodu = re.sub(
        rf"\biçe_aktar[ \t]+({TR_ID})[ \t]+den[ \t]+({TR_MODUL_ID})\b",
        r"from \2 import \1",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\bden[ \t]+({TR_MODUL_ID})[ \t]+içe_aktar[ \t]+\(([^)]+)\)",
        r"from \1 import \2",
        python_kodu
    )

    python_kodu = _MODUL_METOT_DESEN.sub(
        lambda m: MODUL_METOT_TABLO[m.group(0)],
        python_kodu
    )

    sozluk_regex, sozluk_tablo = _sozluk_hazirla()

    python_kodu = sozluk_regex.sub(
        lambda m: sozluk_tablo.get(m.group(0), m.group(0)),
        python_kodu
    )

    for yer, isim in isim_sak.items():
        python_kodu = python_kodu.replace(yer, isim)

    for uid, metin in saklanan_metinler:
        python_kodu = python_kodu.replace(f"\x00METIN_{uid}\x00", metin)

    return python_kodu


def turkce_kodu_donustur(turkce_kod: str) -> str:
    """Token tabanlı koruma ile güçlendirilmiş TürKod -> Python çevirici."""
    turkce_kod = turkce_kod.replace('\r\n', '\n').replace('\r', '\n')
    saklanan_parcalar = []
    saklanan_parcalar = []
    try:
        tanimlar = kullanici_tanimlari(turkce_kod)
        tokenlar = tokenize(turkce_kod, kullanici_adlari=tanimlar)
        
        # ÖNEMLİ: KULLANICI token'ını KORUMA! 
        # _regex_tabanli_ceviri içindeki _isimleri_sakla zaten kullanıcı tanımlarını koruyor.
        # Eğer burada da korursak, `için i aralık` gibi yapısal regex'ler bozulur.
        korunacak_turler = {TokenTuru.METIN, TokenTuru.F_METIN, TokenTuru.YORUM}
        korunacak_tokenlar = [t for t in tokenlar if t.tur in korunacak_turler]
        
        korunacak_tokenlar.sort(key=lambda t: (t.satir, t.sutun), reverse=True)
        
        kod_list = list(turkce_kod)
        sayac = 0
        
        for t in korunacak_tokenlar:
            bas = _pozisyon_hesapla(turkce_kod, t.satir, t.sutun)
            bit = _pozisyon_hesapla(turkce_kod, t.son_satir, t.son_sutun)
            if bas is not None and bit is not None and bas < bit:
                parca = turkce_kod[bas:bit]
                uid = sayac
                sayac += 1
                saklanan_parcalar.append((uid, parca))
                kod_list[bas:bit] = list(f"\x00TKOR_{uid}\x00")
        
        gecici_kod = "".join(kod_list)
        
    except Exception:
        gecici_kod = turkce_kod
        saklanan_parcalar = []

    python_kodu = _regex_tabanli_ceviri(gecici_kod, tanimlar)

    for uid, parca in saklanan_parcalar:
        python_kodu = python_kodu.replace(f"\x00TKOR_{uid}\x00", parca)

    return python_kodu
