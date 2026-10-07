"""TurKod <-> Python cevirici fonksiyonlar."""
import keyword
import re
import warnings

from .dictionary import KORUNMAYAN_KELIMELER, SOZLUK, TERS_SOZLUK, kullanici_tanimlari
from .tokenizer import tokenize, TokenTuru

# ---------------------------------------------------------
# 1. TABLOLAR VE SÖZLÜKLER (En üstte tanımlanmalı)
# ---------------------------------------------------------
# Satır 11-12'nin hemen altına ekle:
TR_HARF = "A-Za-z_ÇŞĞÜÖİçşğüöı"
TR_ID = rf"[{TR_HARF}][{TR_HARF}0-9]*"
TR_MODUL_ID = rf"[{TR_HARF}][{TR_HARF}0-9]*(?:\.[{TR_HARF}][{TR_HARF}0-9]*)*"


def _ascii_katlanmis(yazi):
    if not isinstance(yazi, str):
        return yazi
    return yazi.translate(str.maketrans({
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "I": "I",
        "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U",
    }))


def _ascii_alias_ekle(*tablolar):
    """Türkçe anahtarların ASCII takma adlarını ekler; kanonik yazım korunur."""
    for tablo in tablolar:
        if not isinstance(tablo, dict):
            continue
        for anahtar, deger in list(tablo.items()):
            if not isinstance(anahtar, str):
                continue
            if not any(h in anahtar for h in "çğıöşüÇĞİÖŞÜ"):
                continue
            takma = _ascii_katlanmis(anahtar)
            if takma == anahtar or takma in tablo:
                continue
            tablo[takma] = deger
        for anahtar, deger in list(tablo.items()):
            if not isinstance(deger, dict):
                continue
            for alt_anahtar, alt_deger in list(deger.items()):
                if not isinstance(alt_anahtar, str):
                    continue
                if not any(h in alt_anahtar for h in "çğıöşüÇĞİÖŞÜ"):
                    continue
                takma = _ascii_katlanmis(alt_anahtar)
                if takma == alt_anahtar or takma in deger:
                    continue
                deger[takma] = alt_deger


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
    "ursina": "ursina",
    "matematikf": "math",
    "rastgele": "random",
    "tarih_saat": "datetime",
    "işletim_sistemi": "os",
    "sistem": "sys",
    "json": "json",
    "desen": "re",
    "kaplumbağa": "turtle",
    "istatistik": "statistics",
    "fonksiyon_araçları": "functools",
    "yol_kütüphanesi": "pathlib",
    "özet_kütüphanesi": "hashlib",
    "serileştirici": "pickle",
    "güvenli_sır": "secrets",
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
    # Kısa/çıplak takma adlar: kullanıcı "içe_aktar X_kütüphanesi" yerine
    # doğrudan Python'daki alışılmış modül adını (torch, redis, bs4 ...)
    # yazdığında da "modül.metot" biçimi doğru çevrilsin diye eklendi.
    "torch": "torch",
    "httpx": "httpx",
    "pydantic": "pydantic",
    "pyautogui": "pyautogui",
    "redis": "redis",
    "bs4": "bs4",
    "polars": "polars",
    "spacy": "spacy",
    "pyarrow": "pyarrow",
    "streamlit": "streamlit",
    "openai": "openai",
    "boto3": "boto3",
    "sklearn": "sklearn",
    "sklearn_kütüphanesi": "sklearn",
    "pytest": "pytest",
    "tf": "tensorflow",
    "tensorflow": "tensorflow",
    "coverage": "coverage",
    "django": "django",
    "transformers": "transformers",
    "pymupdf": "pymupdf",
    "fitz": "fitz",
    "numpy": "numpy",
    "pandas": "pandas",
    "requests": "requests",
    "matplotlib.pyplot": "matplotlib.pyplot",
    "sqlalchemy": "sqlalchemy",
    "flask": "flask",
    "fastapi": "fastapi",
    "aiohttp": "aiohttp",
    "docker": "docker",
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
        "kesirli_ayır": "modf",
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
        "ekran_çevir": "display.flip",
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
    # Ursina modül metotları. "ursina" ve "ursina_kütüphanesi" iki farklı
    # kullanım biçimini (import takma adı "ursina" olarak kullanıldığında ve
    # ham "ursina_kütüphanesi" olarak kullanıldığında) aynı anda destekler.
    # NOT: python_kodu_turkceye_cevir() içindeki ters_modul_tablo "ilk
    # yazılan kazanır" mantığı kullanır (bkz. `if tam_py not in
    # ters_modul_tablo`); bu yüzden kısa/kanonik "ursina" formu bilerek ÖNCE
    # tanımlanır ki ters çeviride "ursina_kütüphanesi" değil "ursina"
    # seçilsin.
    "ursina": {
        "başlat": "Ursina",
        "varlık": "Entity",
        "çalıştır": "run",
        "çoğalt": "duplicate",
        "ekrana_yazdır": "print_on_screen",
        "ışın_at": "raycast",
        "örgü": "Mesh",
        "animasyon": "Animation",
        "beklet": "Wait",
        "fonksiyon_nesnesi": "Func",
        "asenkron_fonksiyon": "Async",
        "ekle_saniye": "wait",
        "uzaklık": "distance",
        "uzaklık_2b": "distance_2d",
        "uzaklık_xz": "distance_xz",
        "aradeğerle": "lerp",
        "eğri": "curve",
        "tuş_bas": "held_keys",
    },
    "ursina_kütüphanesi": {
        "başlat": "Ursina",
        "varlık": "Entity",
        "çalıştır": "run",
        "çoğalt": "duplicate",
        "ekrana_yazdır": "print_on_screen",
        "ışın_at": "raycast",
        "örgü": "Mesh",
        "animasyon": "Animation",
        "beklet": "Wait",
        "fonksiyon_nesnesi": "Func",
        "asenkron_fonksiyon": "Async",
        "ekle_saniye": "wait",
        "uzaklık": "distance",
        "uzaklık_2b": "distance_2d",
        "uzaklık_xz": "distance_xz",
        "aradeğerle": "lerp",
        "eğri": "curve",
        "tuş_bas": "held_keys",
    },
    "tarih_saat": {
        "şimdi": "datetime.now",
        "bugün": "datetime.today",
        "utc_şimdi": "datetime.utcnow",
        "utc_damgasi": "datetime.utcfromtimestamp",
        "damga_zaman": "datetime.fromtimestamp",
        "iso_ayristir": "datetime.fromisoformat",
        "tarih_birleştir": "datetime.combine",
        "tarih_ayristir": "datetime.strptime",
        "en_büyük_tarih": "datetime.max",
        "en_küçük_tarih": "datetime.min",
        "zaman_farki": "timedelta",
        "tarih": "date",
        "zaman": "time",
        "saat_dilimi": "timezone",
        "dilim_bilgisi": "tzinfo",
    },

    # === GENİŞLETİLMİŞ KÜTÜPHANE MODÜL METOTLARI ===
    # Aşağıdaki tablolar, önceden düz SOZLUK içinde
    # "kütüphane_metot" (örn. "torch_tenzoru") biçiminde duran ve
    # "kütüphane.metot" (örn. "torch.tenzoru") biçiminde KULLANILAMAYAN
    # maddelerin taşındığı yerdir (Ursina/pygame ile aynı mimari düzeltme).
    # NOT: Bu tablolar TurKod_Sozluk.txt'den otomatik olarak taşındı ve
    # yazımları bir kural tabanlı düzeltici ile normalize edildi. Özellikle
    # PascalCase sınıf adlarında (örn. bs4/torch/pyarrow) tüm Türkçe aksan
    # düzeltmeleri elle denetlenmedi; işlevsel olarak doğrudurlar ama
    # kozmetik yazım kusurları kalmış olabilir.
    "boto3": {
        "akış_günlük_kaydı": "set_stream_logger",
        "boş_işlem": "NullHandler",
        "istemci": "client",
        "kaynak": "resource",
        "oturum": "Session",
    },
    "bs4": {
        "BelgeTürü": "Doctype",
        "Bildirim": "Declaration",
        "Biçimlendirici": "Formatter",
        "Css": "CSS",
        "DönebilenMetin": "NavigableString",
        "Döngü": "Iterator",
        "ElemanFiltre": "ElementFilter",
        "GüzelÇorbalar": "BeautifulSoup",
        "GüzelTaşÇorbası": "BeautifulStoneSoup",
        "HTMLParserAğaçDüzenleyici": "HTMLParserTreeBuilder",
        "Herhangi": "Any",
        "İsteğeBağlı": "Optional",
        "İşlemTalimatı": "ProcessingInstruction",
        "Liste": "List",
        "ParçaReddedilenİşaretlemesi": "ParserRejectedMarkup",
        "SayaçTürü": "CounterType",
        "Sayaç": "Counter",
        "Sözlük": "Dict",
        "Veritipi": "CData",
        "Yorum": "Comment",
    },
    "coverage_kütüphanesi": {
        "başla": "start",
        "durdur": "stop",
        "html_rapor": "html_report",
        "rapor": "report",
        "xml_rapor": "xml_report",
    },
    "django_uygulaması": {
        "kur": "setup",
        "sürüm_al": "get_version",
    },
    "httpx": {
        "BaytAkışı": "ByteStream",
        "BağlantıHatası": "ConnectError",
        "BağlantıZamanAşımı": "ConnectTimeout",
        "Başlıklar": "Headers",
        "GeçersizURL": "InvalidURL",
        "HTTPDurumHatası": "HTTPStatusError",
        "HTTPHatası": "HTTPError",
        "HTTPTaşıyıcı": "HTTPTransport",
        "İstemci": "Client",
        "KapamaHatası": "CloseError",
        "ParolaKimlikDoğrulama": "DigestAuth",
        "Sınırlar": "Limits",
        "TemelKimlikDoğrulama": "BasicAuth",
        "YerelProtokolHatası": "LocalProtocolError",
        "asenkron_http_taşıma": "AsyncHTTPTransport",
        "asenkron_istemci": "AsyncClient",
        "asgi_taşıma": "ASGITransport",
        "Çerezler": "Cookies",
        "ÇerezÇakışması": "CookieConflict",
        "ÇözmeHatası": "DecodingError",
        # === MODÜL DÜZEYİ İSTEK FONKSİYONLARI (önceki kaynakta hiç yoktu) ===
        "al": "get",
        "gönder": "post",
        "koy": "put",
        "sil": "delete",
        "kısmi_güncelle": "patch",
        "başlık_iste": "head",
    },
    "openai": {
        "AsyncAkış": "AsyncStream",
        "AzureOpenAI": "AzureOpenAI",
        "BedrockOpenAI": "BedrockOpenAI",
        "HatalıİstekHatası": "BadRequestError",
        "KimlikDoğrulamaHatası": "AuthenticationError",
        "TemelModel": "BaseModel",
        "istemcisi": "Client",
        "varsayılan_zaman_asi_istemcisi": "DefaultAioHttpClient",
        "çakışma_hatası": "ConflictError",
    },
    "polars": {
        "AWS_Kimlik_Doğrulama_Sağlayıcısı": "CredentialProviderAWS",
        "Azure_Kimlik_Doğrulama_Sağlayıcısı": "CredentialProviderAzure",
        "Dizi": "Array",
        "GCP_Kimlik_Doğrulama_Sağlayıcısı": "CredentialProviderGCP",
        "Herhangi": "Any",
        "Katalog": "Catalog",
        "Kategorik": "Categorical",
        "Kategoriler": "Categories",
        "Kimlik_Doğrulama_Sağlayıcısı_İşlev": "CredentialProviderFunction",
        "Kimlik_Doğrulama_Sağlayıcısı_İşlev_Dönüş": "CredentialProviderFunctionReturn",
        "TemelUzantı": "BaseExtension",
        "Yapılandır": "Config",
        "alan": "Field",
        "dosya_sağlayıcı_argümanları": "FileProviderArgs",
        "genişletme": "Extension",
        "ondalık": "Decimal",
        "sayı": "Enum",
        "süre": "Duration",
        "tarih": "Datetime",
        "veri_çerçevesi": "DataFrame",
        # === EN ÇOK KULLANILAN OKUMA FONKSİYONLARI (önceki kaynakta yoktu) ===
        "oku_csv": "read_csv",
        "oku_parquet": "read_parquet",
        "oku_json": "read_json",
        "oku_excel": "read_excel",
        "veri_serisi": "Series",
        "sütun": "col",
    },
    "pyarrow": {
        "AyGünSaniye": "MonthDayNano",
        "ÇalışmaZamanıBilgisi": "RuntimeInfo",
        "CihazAtamaTürü": "DeviceAllocationType",
        "KayıtTopluAkışOkuyucu": "RecordBatchStreamReader",
        "KayıtTopluAkışYazıcı": "RecordBatchStreamWriter",
        "KayıtTopluOkuyucu": "RecordBatchFileReader",
        "KayıtTopluYazıcı": "RecordBatchFileWriter",
        "MetaDataSürümü": "MetadataVersion",
        "SürümBilgi": "VersionInfo",
        "TabloGrupla": "TableGroupBy",
        "aralık": "arange",
        "cpp_yapım_bilgisi": "CppBuildInfo",
        "dizi": "array",
        "dizi_birleştir": "concat_arrays",
        "ikili": "binary",
        "ok_yapımı_iptal": "ArrowCancelled",
        "tampon_ayır": "allocate_buffer",
        "yapım_bilgisi": "BuildInfo",
    },
    "pyautogui": {
        "bağlam_yöneticisi": "contextmanager",
        "büyüklük": "Size",
        "fare_pozisyonu_göster": "displayMousePosition",
        "hızlan_geri": "easeInBack",
        "hızlan_küp": "easeInCubic",
        "hızlan_lastik": "easeInElastic",
        "hızlan_patlama": "easeInExpo",
        "hızlan_zıpla": "easeInBounce",
        "hızlan_çember": "easeInCirc",
        "nokta": "Point",
        "onay": "confirm",
        "orta": "center",
        "pencere": "Window",
        "sayım": "countdown",
        "sürükle": "drag",
        "sürükle_ilişki": "dragRel",
        "sürükle_konum": "dragTo",
        "tıkla": "click",
        "uyarı": "alert",
        "çift_tıkla": "doubleClick",
        # === TEMEL KLAVYE/EKRAN FONKSİYONLARI (önceki kaynakta hiç yoktu) ===
        "yaz": "write",
        "tuşa_bas": "press",
        "tuş_kısayolu": "hotkey",
        "ekran_görüntüsü_al": "screenshot",
        "ekran_boyutu": "size",
        "fareyi_taşı": "moveTo",
        "fareyi_kaydır": "moveRel",
    },
    "pydantic": {
        "amqp_dsn": "AmqpDsn",
        "aynı_seçenekler": "AliasChoices",
        "aynı_üreticisi": "AliasGenerator",
        "aynı_yol": "AliasPath",
        "base64_bayt": "Base64Bytes",
        "base64_kodlayıcı": "Base64Encoder",
        "base64_metin": "Base64Str",
        "base64_url_bayt": "Base64UrlBytes",
        "base64_url_metin": "Base64UrlStr",
        "clickhouse_dsn": "ClickHouseDsn",
        "cockroach_dsn": "CockroachDsn",
        "klasör_yolu": "DirectoryPath",
        "son_validasyon": "AfterValidator",
        "sonsuz_nan_izni": "AllowInfNan",
        "temel_model": "BaseModel",
        "temel_yapılandırma": "BaseConfig",
        "tüm_http_url": "AnyHttpUrl",
        "tüm_url": "AnyUrl",
        "tüm_web_soket_url": "AnyWebsocketUrl",
        "önceki_validasyon": "BeforeValidator",
        # === EN ÇOK KULLANILAN ÜYELER (önceki kaynakta hiç yoktu) ===
        "alan": "Field",
        "doğrula_çağrı": "validate_call",
        "temel_ayarlar": "BaseSettings",
        "model_doğrulayıcı": "model_validator",
        "alan_doğrulayıcı": "field_validator",
    },
    "pytest_kütüphanesi": {
        "atla": "mark.skip",
        "başarısız": "mark.xfail",
        "bekle": "raises",
        "dizin": "Dir",
        "fikstur": "fixture",
        "kapsama": "cov",
        "konsol": "main",
        "parametrize": "mark.parametrize",
        "sınıf": "Class",
        "toplama_raporu": "CollectReport",
        "toplayıcı": "Collector",
        "yakala": "CaptureFixture",
        "yapılandırma": "Config",
        "çağrı_bilgi": "CallInfo",
        "önbellek": "Cache",
    },
    "redis": {
        "AnahtarBildirimi": "KeyNotification",
        "AnahtarKayıtBildirimleri": "KeyspaceNotifications",
        "AnahtarAlanıÇalışanİşParçacığı": "KeyspaceWorkerThread",
        "AnahtarAlanıKanalı": "KeyspaceChannel",
        "Bağlantı": "Connection",
        "BağlantıHatası": "ConnectionError",
        "BağlantıHavuzu": "ConnectionPool",
        "ÇaprazSlotİşlemHatası": "CrossSlotTransactionError",
        "GeçersizBoruHatti": "InvalidPipelineStack",
        "GeçersizYanit": "InvalidResponse",
        "KanalTürü": "ChannelType",
        "KümeAnahtarAlanıBildirimleri": "ClusterKeyspaceNotifications",
        "MaksimumBağlantıHatası": "MaxConnectionsError",
        "OlayKanalı": "KeyeventChannel",
        "SürücüBilgisi": "DriverInfo",
        "VeriHatası": "DataError",
        "bloklama_bağlantı_havuzu": "BlockingConnectionPool",
        "kimlik_doğrulama_hatası": "AuthenticationError",
        "kimlik_doğrulama_yanlış_argüman_hatası": "AuthenticationWrongNumberOfArgsError",
        "çok_işli_yükleme_hatası": "BusyLoadingError",
        # === ASIL İSTEMCİ SINIFI (önceki kaynakta hiç yoktu) ===
        "istemci": "Redis",
        "eski_istemci": "StrictRedis",
        "url_ile_bağlan": "Redis.from_url",
    },
    "sklearn_kütüphanesi": {
        "kopyala": "clone",
        "yapı_ayarla": "set_config",
        "yapı_konteks": "config_context",
    },
    "spacy": {
        "Birleşik": "Union",
        "Dil": "Language",
        "EğitimŞeması": "ConfigSchemaTraining",
        "Herhangi": "Any",
        "Sözlük": "Dict",
        "Yapılandırma": "Config",
        "YapılandırmaŞeması": "ConfigSchema",
        "YapılandırmaŞemasıBaşlat": "ConfigSchemaInit",
        "YapılandırmaŞemasıDilİşleme": "ConfigSchemaNlp",
        "YapılandırmaŞemasıÖnEğitim": "ConfigSchemaPretrain",
        "Yinelenen": "Iterable",
        "Yol": "Path",
        "açıklama": "explain",
        "bilgi": "info",
        "boş": "blank",
        "gereken_gpu": "require_gpu",
        "gpu_tercih": "prefer_gpu",
        "yükle": "load",
    },
    "streamlit": {
        "açıklama": "caption",
        "kamera_girdi": "camera_input",
        "kod": "code",
        "onay_kutusu": "checkbox",
        "renk_seçici": "color_picker",
        "sohbet_girdisi": "chat_input",
        "sohbet_mesajı": "chat_message",
        "sütunlar": "columns",
        "önbellek": "cache",
        "önbellek_kaynak": "cache_resource",
        "önbellek_veri": "cache_data",
        # === EN TEMEL ARAYÜZ FONKSİYONLARI (önceki kaynakta hiç yoktu) ===
        "başlık": "title",
        "alt_başlık": "subheader",
        "yaz": "write",
        "metin_girdisi": "text_input",
        "sayı_girdisi": "number_input",
        "buton": "button",
        "kenar_çubuğu": "sidebar",
        "resim_göster": "image",
        "veri_çerçevesi_göster": "dataframe",
        "çizgi_grafik": "line_chart",
        "seçim_kutusu": "selectbox",
        "kaydırıcı": "slider",
        "uyarı_göster": "warning",
        "hata_göster": "error",
        "başarı_göster": "success",
        "bilgi_göster": "info",
        "form": "form",
        "form_gönder_düğmesi": "form_submit_button",
        "durum_göster": "status",
        "ilerleme_çubuğu": "progress",
        "dosya_yükleyici": "file_uploader",
    },
    "tensorflow_kütüphanesi": {
        "BağlantısızKoşullar": "UnconnectedGradients",
        "CihazÖzelliği": "DeviceSpec",
        "Değişken": "Variable",
        "DizinliParçalı": "IndexedSlices",
        "DizinliParçalıÖzelliği": "IndexedSlicesSpec",
        "ElemanKilidi": "CriticalSection",
        "GradyanKaydı": "GradientTape",
        "KayıtYükle": "RegisterGradient",
        "Modül": "Module",
        "ParçalıTensör": "RaggedTensor",
        "ParçalıTensörSpec": "RaggedTensorSpec",
        "SeçimliÖzelliği": "OptionalSpec",
        "SeyrekTensör": "SparseTensor",
        "SeyrekTensörSpec": "SparseTensorSpec",
        "TensörDizisi": "TensorArray",
        "TensörDizisiSpec": "TensorArraySpec",
        "TensörÖzellikleri": "TensorSpec",
        "TensörŞekli": "TensorShape",
        "VeriTürü": "DType",
        "kanıtla": "Assert",
        "katmanı": "keras.layers",
        "modeli": "keras.Model",
        "sabit_değer": "constant",
        "yükle": "keras.models.load_model",
    },
    "torch": {
        "BFloat16Depolama": "BFloat16Storage",
        "BoolDepolama": "BoolStorage",
        "ByteDepolama": "ByteStorage",
        "Büyüklük": "Size",
        "CharDepolama": "CharStorage",
        "ÇiftDepolama": "DoubleStorage",
        "Depolama": "Storage",
        "KarmaÇiftDepolama": "ComplexDoubleStorage",
        "KarmaKayanNoktaDepolama": "ComplexFloatStorage",
        "KayıtDepolama": "FloatStorage",
        "KısaDepolama": "ShortStorage",
        "QTamsayı32Depolama": "QInt32Storage",
        "QTamsayı8Depolama": "QInt8Storage",
        "QUYuzde2x4Depolama": "QUInt2x4Storage",
        "QUYuzde4x2Depolama": "QUInt4x2Storage",
        "QUYuzde8Depolama": "QUInt8Storage",
        "TamSayıDepolama": "IntStorage",
        "UzunDepolama": "LongStorage",
        "YarıDepolama": "HalfStorage",
        "ekle": "nn",
        "ogradim_ölçekleyici": "GradScaler",
        "optimizasyonu": "optim",
        "tenzoru": "Tensor",
        "verisi": "utils.data",
        # === TEMEL FABRİKA FONKSİYONLARI (önceki kaynakta hiç yoktu) ===
        "tensör": "tensor",
        "sıfırlar": "zeros",
        "birler": "ones",
        "rastgele_tensör": "rand",
        "aygıt": "device",
        "gradyansız": "no_grad",
        "kaydet": "save",
        "yükle": "load",
        "cuda_var_mı": "cuda.is_available",
        "sinir_ağı_modülü": "nn.Module",
        "sabit_tohum": "manual_seed",
    },
    "transformers": {
        "ASTModel": "ASTModel",
        "ASTÖnEğitilmişModel": "ASTPreTrainedModel",
        "ASTÖzellikÇıkarıcı": "ASTFeatureExtractor",
        "ASTSesSınıflandırma": "ASTForAudioClassification",
        "ASTYapılandırma": "ASTConfig",
        "Adafaktör": "Adafactor",
        "Aimv2GörüntüModeli": "Aimv2VisionModel",
        "AlbertYapılandırma": "AlbertConfig",
    },
    # === PYMUPDF (fitz) — PDF okuma/yazma/render kütüphanesi ===
    # Not: Bu tablo yalnızca MODÜL DÜZEYİNDEKİ fonksiyon ve sınıfları kapsar
    # (pymupdf.aç(...), pymupdf.piksel_haritası(...) gibi). Document/Page
    # NESNELERİNİN kendi metotları (örn. sayfa.metin_al()) buraya dahil
    # EDİLEMEZ: bu çevirici değişkenlerin tipini bilmiyor (regüler ifade
    # tabanlı), "belge" veya "sayfa" adlı her değişken gerçek bir PyMuPDF
    # nesnesi olmak zorunda değil; böyle bir eşleme yanlış pozitif üretir.
    "pymupdf": {
        "aç": "open",
        "belge": "Document",
        "piksel_haritası": "Pixmap",
        "matris": "Matrix",
        "kimlik_matrisi": "Identity",
        "dörtgen": "Rect",
        "tam_sayı_dörtgen": "IRect",
        "nokta": "Point",
        "dörtgen_şekil": "Quad",
        "yazı_tipi": "Font",
        "metin_yazıcı": "TextWriter",
        "belge_yazıcı": "DocumentWriter",
        "görüntü_listesi": "DisplayList",
        "metin_sayfası": "TextPage",
        "öykü": "Story",
        "araçlar": "TOOLS",
        "renk_uzayı_rgb": "csRGB",
        "renk_uzayı_gri": "csGRAY",
        "renk_uzayı_cmyk": "csCMYK",
        "pdf_notu": "Annot",
        "bağlantı": "Link",
    },
    # === TURTLE (kaplumbağa grafik modülü) ===
    # Bu isimler önceden düz SOZLUK'ta bare kelime olarak duruyordu (örn.
    # "ileri" tek başına çalışıyordu). Buradaki tablo AYRICA "kaplumbağa.X"
    # noktalı kullanımını da destekler; düz kelimeler bilerek SİLİNMEDİ,
    # geriye dönük uyumluluk korunuyor. Modül tablosu içinde ad çakışması
    # sorun değildir (namespaced), bu yüzden "temizle"/"konum"/"güncelle"
    # gibi başka yerlerde de geçen genel kelimeler burada olduğu gibi
    # kullanılabildi; Qwen'in önerdiği "_turtle" son ek hack'ine gerek yok.
    "kaplumbağa": {
        "ileri": "forward",
        "geri": "back",
        "sağa_dön": "right",
        "sola_dön": "left",
        "kalem_bırak": "pendown",
        "kalem_kaldır": "penup",
        "kalem_rengi": "pencolor",
        "kalem_boyutu": "pensize",
        "hız_ayarla": "speed",
        "çember": "circle",
        "git_koordinat": "goto",
        "x_ayarla": "setx",
        "y_ayarla": "sety",
        "yön_ayarla": "setheading",
        "ekranı_temizle": "clearscreen",
        "arka_plan_rengi": "bgcolor",
        "ekran_ayarla": "setup",
        "çıkışta_bekle": "done",
        "tamamla": "done",
        "dolgu_rengi_ayarla": "fillcolor",
        "dolgu_başla": "begin_fill",
        "dolgu_bitir": "end_fill",
        "izleyici_kapat": "tracer",
        # === önceki kaynakta hiç yoktu ===
        "ok_gizle": "hideturtle",
        "ok_göster": "showturtle",
        "güncelle": "update",
        "temizle": "clear",
        "konum": "position",
        "mesafe": "distance",
    },
    "numpy": {
        "dizi": "array",
        "sıfırlar": "zeros",
        "birler": "ones",
        "boş_dizi": "empty",
        "aralık": "arange",
        "eşit_aralık": "linspace",
        "rastgele_sayı": "random.random",
        "rastgele_tamsayı": "random.randint",
        "ortalama": "mean",
        "toplam": "sum",
        "en_küçük": "min",
        "en_büyük": "max",
        "nokta_çarpımı": "dot",
        "birleştir": "concatenate",
        "yeniden_şekillendir": "reshape",
    },
    "pandas": {
        "veri_çerçevesi": "DataFrame",
        "veri_serisi": "Series",
        "csv_oku": "read_csv",
        "excel_oku": "read_excel",
        "json_oku": "read_json",
        "parquet_oku": "read_parquet",
        "birleştir": "concat",
        "tarih_aralığı": "date_range",
        "eksik_mi": "isna",
        # === İsimlendirme standardı: "eylem_nesne" (polars ile tutarlı) ===
        # "csv_oku" vb. eski biçimler bilerek SİLİNMEDİ (geriye dönük
        # uyumluluk); "oku_csv" vb. polars'la tutarlı ek takma addır.
        "oku_csv": "read_csv",
        "oku_excel": "read_excel",
        "oku_json": "read_json",
        "oku_parquet": "read_parquet",
    },
    "requests": {
        "al": "get",
        "gönder": "post",
        "koy": "put",
        "sil": "delete",
        "başlık_iste": "head",
        "seçenek_iste": "options",
        "oturum": "Session",
    },
    "matplotlib.pyplot": {
        "çiz": "plot",
        "serpilme_grafiği": "scatter",
        "çubuk_grafiği": "bar",
        "histogram": "hist",
        "başlık": "title",
        "x_etiketi": "xlabel",
        "y_etiketi": "ylabel",
        "lejant": "legend",
        "göster": "show",
        "kaydet": "savefig",
        "şekil": "figure",
        "alt_çizim": "subplot",
    },
    "sqlalchemy": {
        "motor_oluştur": "create_engine",
        "seç": "select",
        "metin": "text",
        "tablo": "Table",
        "meta_veri": "MetaData",
        "sütun": "Column",
        "tamsayı_türü": "Integer",
        "metin_türü": "String",
        "işlevler": "func",
    },
    "flask": {
        "uygulama_sınıfı": "Flask",
        "istek": "request",
        "jsonla": "jsonify",
        "yönlendir": "redirect",
        "url_oluştur": "url_for",
        "şablon_oluştur": "render_template",
        "hata_yanıtla": "abort",
        "yanıt_oluştur": "make_response",
        "oturum": "session",
    },
    "fastapi": {
        "uygulama_sınıfı": "FastAPI",
        "yönlendirici_sınıfı": "APIRouter",
        "bağımlılık": "Depends",
        "http_hatası": "HTTPException",
        "sorgu": "Query",
        "gövde": "Body",
    },
    "aiohttp": {
        "istemci_isteği": "ClientRequest",
        "istemci_yanıtı": "ClientResponse",
        "istemci_oturumu": "ClientSession",
        "istek_gönder": "request",
        "temel_kimlik_doğrulama": "BasicAuth",
    },
    "docker": {
        "istemci_oluştur": "from_env",
        "istemci_sınıfı": "DockerClient",
    },
}

# "fitz", pymupdf'in eski/klasik içe aktarma adıdır (v1.24+'da hâlâ
# çalışan bir "legacy alias"); aynı tabloyu paylaşır.
MODUL_METOTLARI["fitz"] = MODUL_METOTLARI["pymupdf"]
_ascii_alias_ekle(TK_SABITLER, TK_PARAMLER, MODUL_CEVIRILERI, MODUL_METOTLARI)

# Kısa çıplak takma adlar mevcut "_kütüphanesi" tablolarını paylaşır
# (import tensorflow as tf gibi kullanımlar için).
MODUL_METOTLARI["tf"] = MODUL_METOTLARI["tensorflow_kütüphanesi"]
MODUL_METOTLARI["tensorflow"] = MODUL_METOTLARI["tensorflow_kütüphanesi"]
MODUL_METOTLARI["pytest"] = MODUL_METOTLARI["pytest_kütüphanesi"]
MODUL_METOTLARI["sklearn"] = MODUL_METOTLARI["sklearn_kütüphanesi"]
MODUL_METOTLARI["coverage"] = MODUL_METOTLARI["coverage_kütüphanesi"]
MODUL_METOTLARI["django"] = MODUL_METOTLARI["django_uygulaması"]

# NOT: python_kodu_turkceye_cevir() ters çeviride "ilk yazılan kazanır"
# mantığını kullanır. Kısa/çıplak takma adlar (tf, tensorflow, pytest,
# sklearn, coverage, django) yukarıda SONRADAN eklendiği için dict
# sıralamasında en sona düşer; ters çeviride "uzun" _kütüphanesi biçimi
# kazanır. Ursina'da olduğu gibi kısa biçimin ters çeviride öncelikli
# olmasını sağlamak için bu anahtarları "yeniden eklenmiş" gibi öne alıyoruz:
for _kisa in ("tf", "tensorflow", "pytest", "sklearn", "coverage", "django"):
    MODUL_METOTLARI[_kisa] = MODUL_METOTLARI.pop(_kisa)
for _uzun in (
    "tensorflow_kütüphanesi", "pytest_kütüphanesi", "sklearn_kütüphanesi",
    "coverage_kütüphanesi", "django_uygulaması",
):
    MODUL_METOTLARI[_uzun] = MODUL_METOTLARI.pop(_uzun)

# DÜZELTME: _ascii_alias_ekle(...) yukarıdaki iki döngüden ÖNCE çalıştığı
# için, ürettiği ASCII takma adlar (örn. "pytest_kutuphanesi") bu yeniden
# sıralamaya hiç dahil olmadı ve dict'in en başında kaldı. Sonuç: ters
# çeviride (python_kodu_turkceye_cevir, "ilk yazılan kazanır") kanonik kısa
# ad yerine ASCII biçim seçiliyordu (örn. "pytest.raises(...)" ->
# "pytest_kutuphanesi.bekle(...)" üretiyordu, "pytest.bekle(...)" yerine).
# Çözüm: MODUL_METOTLARI'ndeki HER anahtarı tara; bir anahtar başka bir
# anahtarın ASCII-katlanmış hâliyse (ve tablo içeriği aynıysa, yani gerçek
# bir takma ad ise) onu dict'in en sonuna it. Böylece aksanlı/kanonik biçim
# her zaman ASCII biçimden önce gelir ve ters çeviride kazanır.
_mm_anahtarlari = list(MODUL_METOTLARI.keys())
for _mm_anahtar in _mm_anahtarlari:
    _katlanmis = _ascii_katlanmis(_mm_anahtar)
    if _katlanmis == _mm_anahtar:
        continue  # zaten ASCII, katlanacak bir şey yok
    if _katlanmis in MODUL_METOTLARI and MODUL_METOTLARI[_katlanmis] is MODUL_METOTLARI[_mm_anahtar]:
        MODUL_METOTLARI[_katlanmis] = MODUL_METOTLARI.pop(_katlanmis)

# ---------------------------------------------------------
# 2. REGEX VE TÜREV MADDELERİN DERLENMESİ
# ---------------------------------------------------------

# Üç tırnaklı bloklar tek tırnaklı olanlardan ÖNCE denenmeli; aksi halde `"""`
# iki ayrı boş string gibi eşleşip metin/kod sınırını kaydırır.
METIN_VE_YORUM_DESENI = (
    r'([rbufRBUF]{0,2}"""(?:[^"\\]|\\[\s\S]|"(?!""))*"""'
    r"|[rbufRBUF]{0,2}'''(?:[^'\\]|\\[\s\S]|'(?!''))*'''"
    r'|[rbufRBUF]{0,2}"(?:[^"\\\n]|\\[\s\S])*"'
    r"|[rbufRBUF]{0,2}'(?:[^'\\\n]|\\[\s\S])*'"
    r"|#[^\n]*)"
)

# f-string'ler ayrı ele alınır: düz metni korunur, `{...}` ifadeleri çevrilir.
FSTRING_DESENI = (
    rf'(?<![{TR_HARF}0-9])[rbuRBU]?[fF][rbuRBU]?"""(?:[^"\\]|\\[\s\S]|"(?!""))*"""'
    rf"|(?<![{TR_HARF}0-9])[rbuRBU]?[fF][rbuRBU]?'''(?:[^'\\]|\\[\s\S]|'(?!''))*'''"
    rf'|(?<![{TR_HARF}0-9])[rbuRBU]?[fF][rbuRBU]?"(?:[^"\\\n]|\\[\s\S])*"'
    rf"|(?<![{TR_HARF}0-9])[rbuRBU]?[fF][rbuRBU]?'(?:[^'\\\n]|\\[\s\S])*'"
)

_FSTRING_DESEN = re.compile(FSTRING_DESENI)

# Tek geçişte tara: önce f-string alternatifleri, sonra normal metin/yorum.
_METIN_DESEN = re.compile(f"(?:{FSTRING_DESENI})|{METIN_VE_YORUM_DESENI}")

# `{{`/`}}` kaçışları ve bir seviye iç içe süslü parantez destekli ifade bloğu.
_FSTRING_IFADE_DESEN = re.compile(r"\{\{|\}\}|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

# Geriye donuk uyumluluk: eskiden ayri (ve eksik) bir tablo olan MODUL_ISIMLERI
# artik tek kaynak olan MODUL_CEVIRILERI'ne isaret eder.
MODUL_ISIMLERI = MODUL_CEVIRILERI

def _satir_baslari(kod):
    """Her satırın başlangıç ofseti (0 tabanlı). Bir kez hesaplanır."""
    baslar = [0]
    i = kod.find('\n')
    while i >= 0:
        baslar.append(i + 1)
        i = kod.find('\n', i + 1)
    return baslar


def _pozisyon_hesapla(kod, satir, sutun, satir_baslari=None):
    """1 tabanlı satır/sütun -> 0 tabanlı karakter pozisyonu.

    ``satir_baslari`` verilirse metin yeniden bölünmez (O(1)); eskiden her
    token için tüm dosya baştan bölünüyordu."""
    if satir_baslari is not None:
        if satir < 1 or satir > len(satir_baslari):
            return None
        pozisyon = satir_baslari[satir - 1] + sutun - 1
        return None if pozisyon > len(kod) else pozisyon
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
    py_modul = MODUL_CEVIRILERI.get(modul, modul)
    for tr_metot, py_metot in metotlar.items():
        if py_metot in BUILTIN_FUNCS and py_modul == "math":
            # math modülünde abs/min/max/round/sum yoktur: yerleşik kullanılır.
            # (Eskiden bu kural TÜM modüllere uygulanıyordu; "numpy.toplam(a,
            # axis=0)" -> "sum(a, axis=0)" TypeError veriyordu.)
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = py_metot
        else:
            # NOT: Eskiden hedef modül adıyla başlıyorsa (örn. tarih_saat ->
            # "datetime.now") önek eklenmiyordu; bu "datetime.now()" (modülde
            # yok -> AttributeError) üretiyordu. Doğrusu sınıf üzerinden
            # "datetime.datetime.now()". Normal durum: pygame.mixer.music.get_pos
            # veya pygame.display.set_mode.
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = f"{py_modul}.{py_metot}"

_MODUL_METOT_DESEN = re.compile(
    "|".join(
        rf"\b{re.escape(k)}\b"
        for k in sorted(MODUL_METOT_TABLO, key=len, reverse=True)
    )
)

# ---------------------------------------------------------
# Ursina nesne (singleton) özellik tabloları
# "pencere.başlık", "fare.x", "kamera.z", "uygulama.fps", "renk.kırmızı"
# gibi noktalı kullanımları bağlam içinde, tek birim olarak çevirir.
# Bunlar düz SOZLUK'a konmaz; çünkü orada "kırmızı" veya "fare_x" gibi
# bağlamsız tek kelimeler üretmek "renk.renk.kırmızı" tarzı çift önek
# hatalarına yol açar.
# ---------------------------------------------------------

URSINA_NESNE_ADLARI = {
    "pencere": "window",
    "fare": "mouse",
    "kamera": "camera",
    "uygulama": "application",
    "renk": "color",
}

URSINA_NESNELERI = {
    "pencere": {
        "başlık": "title",
        "kenarsız": "borderless",
        "çıkış_düğmesi": "exit_button",
        "fps_sayacı": "fps_counter",
    },
    "fare": {
        "x": "x",
        "y": "y",
        "sol": "left",
        "sağ": "right",
        "orta": "middle",
        "delta": "delta",
        "kilitli": "locked",
        "görünür": "visible",
        "etkin": "enabled",
        "üstündeki_varlık": "hovered_entity",
    },
    "kamera": {
        "z": "z",
        "kilitli": "locked",
        "hedef": "target",
    },
    "uygulama": {
        "fps": "fps",
        "kapat": "quit",
        "adı": "name",
        "sürümü": "version",
        "duraklatıldı": "paused",
        "zaman_ölçeği": "time_scale",
    },
    "renk": {
        "kırmızı": "red",
        "yeşil": "green",
        "mavi": "blue",
        "beyaz": "white",
        "siyah": "black",
        "şeffaf": "clear",
        "gri": "gray",
        "sarı": "yellow",
        "turuncu": "orange",
        "mor": "magenta",
        "pembe": "pink",
        "kahverengi": "brown",
        "turkuaz": "cyan",
        "lacivert": "navy",
        "altın": "gold",
        "gümüş": "silver",
        "rgb": "rgb",
        "hsv": "hsv",
    },
}

URSINA_NESNE_TABLO = {}
for _nesne_tr, _ozellikler in URSINA_NESNELERI.items():
    _py_nesne = URSINA_NESNE_ADLARI[_nesne_tr]
    for _tr_oz, _py_oz in _ozellikler.items():
        URSINA_NESNE_TABLO[f"{_nesne_tr}.{_tr_oz}"] = f"{_py_nesne}.{_py_oz}"

_URSINA_NESNE_DESEN = re.compile(
    "|".join(
        rf"\b{re.escape(k)}\b"
        for k in sorted(URSINA_NESNE_TABLO, key=len, reverse=True)
    )
)

# ---------------------------------------------------------
# PyMuPDF "ayrılmış değişken adı" nesne tabloları
# ---------------------------------------------------------
# Ursina'daki fare/kamera/uygulama/renk ile AYNI mimari: "belge" ve "sayfa"
# kelimeleri PyMuPDF Document/Page nesneleri için AYRILMIŞ (reserved) isim
# olarak kabul edilir. Bu, Ursina'nın singleton'larından FARKLI bir varsayım
# taşır: fare/kamera gerçekten tekil global nesnelerdir, ama her PDF belgesi
# kullanıcının seçtiği rastgele bir Python değişkenidir. Dolayısıyla "belge"
# veya "sayfa" adını BAŞKA bir amaçla (örn. genel bir "sayfa numarası"
# değişkeni) kullanan kod, burada YANLIŞ ÇEVRİLİR. Bu ursina nesneleriyle
# aynı sınıf riski, sadece isimler daha jenerik olduğu için gerçekleşme
# olasılığı daha yüksek. Kullanıcı bu çakışmayı yakalayan bir uyarı sistemi
# eklemeyi planladığı için bu ödünleşim kabul edilerek eklendi.
PYMUPDF_NESNE_ADLARI = {
    "belge": "belge",  # değişken adı korunur, sadece .metot çevrilir
    "pdf": "pdf",  # PyMuPDF'te çok yaygın kullanılan değişken adı, belge ile aynı tablo
    "doc": "doc",  # PyMuPDF resmi örneklerinde en sık kullanılan isim
    "sayfa": "sayfa",
    "şekil": "şekil",  # sayfa.yeni_şekil() ile üretilen Shape nesnesi
    # "belge" ve "sayfa"da aksanlı harf yok, bu yüzden ASCII katlama sorun
    # çıkarmıyordu. "şekil" ise "ş" içeriyor ve Python tarafında kullanıcılar
    # değişkeni çoğunlukla Türkçe karaktersiz "sekil" diye yazar. Bu ayrı
    # anahtar olmadan "sekil.draw_rect" gibi literal metin hiç eşleşmiyor ve
    # çevrilmeden kalıyordu (python_kodu_turkceye_cevir yönünde test edilip
    # doğrulandı).
    "sekil": "sekil",
}

PYMUPDF_NESNELERI = {
    "belge": {
        "yükle_sayfa": "load_page",
        "sayfa_sayısı": "page_count",
        "kaydet": "save",
        "kapat": "close",
        "meta_veri": "metadata",
        "yeni_sayfa": "new_page",
        "sayfa_sil": "delete_page",
        "sayfa_seç": "select",
        "pdf_ekle": "insert_pdf",
        "görüntü_çıkar": "extract_image",
        "sayfa_taşı": "move_page",
        "kimlik_doğrula": "authenticate",
        "kapalı_mı": "is_closed",
        "şifreli_mi": "is_encrypted",
    },
    "sayfa": {
        "metin_al": "get_text",
        "piksel_al": "get_pixmap",
        "görüntüleri_al": "get_images",
        "resim_ekle": "insert_image",
        "metin_ekle": "insert_text",
        "metin_kutusu_ekle": "insert_textbox",
        "ara": "search_for",
        "bağlantıları_al": "get_links",
        "çizimleri_al": "get_drawings",
        "döndür": "set_rotation",
        "pdf_sayfası_göster": "show_pdf_page",
        "numara": "number",
        "sınır_kutusu": "mediabox",
        "döndürme": "rotation",
        "dörtgen_çiz": "draw_rect",
        "çember_çiz": "draw_circle",
        "çizgi_çiz": "draw_line",
        "yeni_şekil": "new_shape",
    },
    "şekil": {
        "dörtgen_çiz": "draw_rect",
        "çember_çiz": "draw_circle",
        "çizgi_çiz": "draw_line",
        "bitir": "finish",
    },
}
# ASCII değişken adı "sekil" için aynı metot tablosunu paylaştır (MODUL_METOTLARI["fitz"]
# = MODUL_METOTLARI["pymupdf"] ile aynı desen).
PYMUPDF_NESNELERI["sekil"] = PYMUPDF_NESNELERI["şekil"]
PYMUPDF_NESNELERI["pdf"] = PYMUPDF_NESNELERI["belge"]
PYMUPDF_NESNELERI["doc"] = PYMUPDF_NESNELERI["belge"]

PYMUPDF_NESNE_TABLO = {}
for _nesne_tr, _ozellikler in PYMUPDF_NESNELERI.items():
    _py_nesne = PYMUPDF_NESNE_ADLARI[_nesne_tr]
    for _tr_oz, _py_oz in _ozellikler.items():
        PYMUPDF_NESNE_TABLO[f"{_nesne_tr}.{_tr_oz}"] = f"{_py_nesne}.{_py_oz}"

_ascii_alias_ekle(URSINA_NESNELERI, PYMUPDF_NESNELERI)

_PYMUPDF_NESNE_DESEN = re.compile(
    "|".join(
        rf"\b{re.escape(k)}\b"
        for k in sorted(PYMUPDF_NESNE_TABLO, key=len, reverse=True)
    )
)

_YER_TUTUCU_DESEN = re.compile(
    "\x00(?:METIN|TKOR|NOKTALI)_\\d+\x00|__ISIM_SABITI_\\d+__"
)


def _yer_tutuculari_geri_koy(kod, tablo):
    """Yer tutucuları tek geçişte geri koyar. Eskiden her yer tutucu için
    metnin tamamı baştan taranıyordu (binlerce metin içeren uzun dosyalarda
    saniyeler sürüyordu)."""
    if not tablo:
        return kod
    return _YER_TUTUCU_DESEN.sub(lambda m: tablo.get(m.group(0), m.group(0)), kod)


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


def _oznitelik_tanimlari(kod):
    """Kullanıcı nesnelerine ait olabilecek adlar: kendisi.X / self.X
    öznitelikleri ile kullanıcının tanımladığı fonksiyon/metot ve sınıf adları
    (nesne.hesapla() gibi metot çağrıları tanımla aynı adı korumalı)."""
    adlar = set(re.findall(rf"\b(?:kendisi|self)\.({TR_ID})", kod))
    adlar.update(re.findall(rf"\b(?:fonksiyon|def|sınıf|sinif|class)\s+({TR_ID})", kod))
    return adlar


_BILINEN_UCUNCU_TARAF = {
    "pygame", "ursina", "numpy", "pandas", "requests", "PIL", "matplotlib",
    "pymupdf", "fitz", "customtkinter", "turtle", "tkinter", "flask", "django",
    "openpyxl", "docx", "pptx", "cv2", "kivy", "arcade", "pyglet", "bs4",
    "selenium", "sklearn", "scipy", "seaborn", "plotly", "pyautogui",
}


def _kutuphane_adlari(kod):
    """Bilinen bir KÜTÜPHANE modülüne bağlı adlar: "içe_aktar tkinter olarak
    tk" -> tk, "içe_aktar matematik" -> matematik. Kullanıcının kendi
    modülleri (sözlükte olmayan) bu kümeye girmez."""
    import sys as _sys
    bilinen = (set(MODUL_CEVIRILERI) | set(MODUL_CEVIRILERI.values())
               | set(getattr(_sys, "stdlib_module_names", ()))
               | _BILINEN_UCUNCU_TARAF)
    adlar = set()
    for m in re.finditer(r"^[ \t]*(?:içe_aktar|ice_aktar|import)[ \t]+([^\n#]+)", kod, re.M):
        for parca in m.group(1).split(","):
            ogeler = parca.split()
            if not ogeler:
                continue
            modul = ogeler[0]
            if modul.split(".")[0] not in bilinen and modul not in bilinen:
                continue
            if len(ogeler) >= 3 and ogeler[1] in ("olarak", "as"):
                adlar.add(ogeler[2])
            else:
                adlar.add(modul.split(".")[0])
    return adlar


_SOZLUK_KELIMELERI = None


def _sozluk_kelimeleri():
    global _SOZLUK_KELIMELERI
    if _SOZLUK_KELIMELERI is None:
        _SOZLUK_KELIMELERI = {
            str(k).replace(r"\b", "").strip() for k in SOZLUK.keys()
        }
    return _SOZLUK_KELIMELERI


def _isimleri_sakla(kod, tanimlar):
    """Kullanıcı tanımlarını yer tutucularla değiştirir; (kod, yer_tutucu_tablosu) döner.

    İki dar istisna (kullanıcı değişkeniyle aynı adı taşıyan KÜTÜPHANE
    adları çevrilebilsin diye):
    * Bilinen bir kütüphane modülünün özniteliği: "pencere = tk.pencere()"
      içinde sağdaki tk.pencere (tk = içe aktarılmış tkinter). Kullanıcının
      kendi sınıf/nesne/modül öznitelikleri (Ayar.renk, benim_modul.renk)
      korunmaya devam eder.
    * Kütüphane çağrısındaki anahtar kelime argümanı: "düğme(p,
      genişlik=genişlik)" ya da "tk.Button(genişlik=...)" içinde soldaki
      kwarg adı çevrilmelidir. Kullanıcı fonksiyonlarına (başka dosyadakiler
      dahil) ve sözlük(...) anahtarlarına dokunulmaz.
    """
    isim_sak = {}

    if not tanimlar:
        return kod, isim_sak

    isim_to_yer = {}
    isim_desen = "|".join(
        rf"\b{re.escape(isim)}\b"
        for isim in sorted(tanimlar, key=len, reverse=True)
    )
    oznitelikler = _oznitelik_tanimlari(kod)
    kutuphaneler = _kutuphane_adlari(kod)
    kutuphaneler -= oznitelikler

    def kutuphane_cagrisi_mi(konum):
        """konum'daki ad bir kwarg ise ve çağrılan şey bir kütüphane
        fonksiyonuysa True."""
        derinlik = 0
        i = konum - 1
        sinir = max(0, konum - 3000)  # büyük dosyada karesel taramayı önler
        while i >= sinir:
            ch = kod[i]
            if ch in ")]}":
                derinlik += 1
            elif ch in "([{":
                if derinlik == 0:
                    if ch != "(":
                        return False
                    onceki = re.search(r"([\w.]+)\s*$", kod[max(0, i - 200):i])
                    if not onceki:
                        return False
                    zincir = onceki.group(1).split(".")
                    son = zincir[-1]
                    if son in ("sözlük", "sozluk", "dict") or son in tanimlar:
                        return False
                    if len(zincir) > 1:
                        return zincir[0] in kutuphaneler
                    return son in _sozluk_kelimeleri()
                derinlik -= 1
            i -= 1
        return False

    def isim_degistir(match):
        isim = match.group(0)
        bas, son = match.span()
        onceki_karakter = kod[bas - 1] if bas > 0 else ""
        if onceki_karakter == "." and isim not in oznitelikler and kutuphaneler:
            zincir = re.search(r"([\w.]+)\.$", kod[max(0, bas - 200):bas])
            if zincir and zincir.group(1).split(".")[0] in kutuphaneler:
                return isim
        if re.match(r"\s*=(?!=)", kod[son:]) and kutuphane_cagrisi_mi(bas):
            return isim
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
    # Satır sonu "[ \t]*$" desenleri '\r' önünde eşleşmiyor, CRLF'li kodda
    # "while x in y:" bile "döngü x içinde y:" (yani for) oluyordu.
    python_kodu = python_kodu.replace('\r\n', '\n').replace('\r', '\n')
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

    # Parantez/köşeli/süslü parantez derinliği 0 olmayan satır-başı
    # "isim =" eşleşmelerini ele: çok satırlı çağrılarda ("draw_rect(\n
    # fill=...,\n radius=...,\n)") her kwarg kendi satırında durur ve
    # "^\s*(ID)\s*=" buna satır başı değişken ataması gibi bakardı. Bu
    # yüzden fill/width/color/radius gibi parametre adları yanlışlıkla
    # "kullanıcı tanımı" sayılıp çeviriden muaf tutuluyordu (dictionary.py
    # içindeki kullanici_tanimlari()'nda aynı sınıf hatanın bir kopyası
    # ayrıca düzeltildi, ama bu fonksiyon (python_kodu_turkceye_cevir) onu
    # çağırmıyor, kendi ayrı tanimlar hesaplamasını yapıyor).
    def _derinlik_haritasi(kod):
        derinlikler = [0] * (len(kod) + 1)
        derinlik = 0
        for i, c in enumerate(kod):
            derinlikler[i] = derinlik
            if c in '([{':
                derinlik += 1
            elif c in ')]}':
                derinlik = max(0, derinlik - 1)
        derinlikler[len(kod)] = derinlik
        return derinlikler

    _derinlikler = _derinlik_haritasi(gecici_kod)
    tanimlar.update(
        m.group(1)
        for m in re.finditer(rf'^\s*({PY_ID})\s*=(?!=)', gecici_kod, re.MULTILINE)
        if _derinlikler[m.start()] == 0
    )
    # Çoklu atama: a, b = ...
    for m in re.finditer(
            rf'^\s*\(?((?:\*?{PY_ID}\s*,\s*)+\*?{PY_ID})\s*,?\s*\)?\s*=(?!=)',
            gecici_kod, re.MULTILINE):
        if _derinlikler[m.start()] == 0:
            tanimlar.update(p.strip().lstrip('*') for p in m.group(1).split(','))
    # Döngü değişkenleri (tekli ve çoklu): for i in / for a, b in
    for grup in re.findall(
            rf'\bfor\s+\(?((?:{PY_ID}\s*,\s*)*{PY_ID})\)?\s+in\b', gecici_kod):
        tanimlar.update(p.strip() for p in grup.split(','))
    tanimlar.update(re.findall(rf'\bself\.({PY_ID})', gecici_kod))
    # Fonksiyon / sınıf adları, takma adlar (import/with/except ... as X),
    # global / nonlocal bildirimleri.
    tanimlar.update(re.findall(rf'\bdef\s+({PY_ID})', gecici_kod))
    tanimlar.update(re.findall(rf'\bclass\s+({PY_ID})', gecici_kod))
    tanimlar.update(re.findall(rf'\bas\s+({PY_ID})', gecici_kod))
    for grup in re.findall(
            rf'^\s*(?:global|nonlocal)\s+({PY_ID}(?:\s*,\s*{PY_ID})*)',
            gecici_kod, re.MULTILINE):
        tanimlar.update(p.strip() for p in grup.split(','))
    for param_blok in re.findall(rf'\bdef\s+{PY_ID}\s*\(([^)]*)\)', gecici_kod):
        for p in param_blok.split(','):
            # "*args", "**kw", "x: int = 3" biçimleri de desteklenir.
            p = p.strip().split('=')[0].split(':')[0].strip().lstrip('*').strip()
            if p and p != 'self':
                tanimlar.add(p)
    # Python ayrılmış kelimeleri ve yerleşikleri asla "kullanıcı tanımı"
    # sayılmaz (ör. "def print" gibi gölgeleme yine çevrilir).
    tanimlar = {t for t in tanimlar if not keyword.iskeyword(t)}

    # "for X in range(Y):" -> "için X aralık(Y):" ve "for X in Y:" ->
    # "için X içinde Y:" BÜTÜN KALIP olarak burada, genel sözlük (ters_regex)
    # çalışmadan önce dönüştürülür. Aksi halde "for", "in", "range" ayrı ayrı
    # kelime kelime çevrilir ("için", "içinde", "aralık") ve sonuç geçersiz
    # TürKod sentaksı olan "için i içinde aralık(3):" olur — doğrusu
    # "için i aralık(3):" olmalı ("içinde" sadece range DIŞI döngülerde
    # kullanılır, örn. "için öğe içinde liste:").
    # "while x in y:" TürKod'da "döngü x içinde y:" olur ve bu, TürKod'un
    # "döngü X içinde Y" (for) kalıbıyla karışır. Koşul parantezlenerek
    # belirsizlik giderilir: "döngü (x içinde y):".
    gecici_kod = re.sub(
        rf"^([ \t]*)while[ \t]+({PY_ID}[ \t]+(?:not[ \t]+)?in[ \t]+[^\n]+?)[ \t]*:[ \t]*$",
        r"\1while (\2):",
        gecici_kod,
        flags=re.MULTILINE,
    )
    gecici_kod = re.sub(
        rf"\bfor\s+({PY_ID}(?:\s*,\s*{PY_ID})*)\s+in\s+range\s*\(([^)]*)\)\s*:",
        lambda m: f"için {m.group(1)} aralık({m.group(2)}):",
        gecici_kod
    )
    gecici_kod = re.sub(
        rf"\bfor\s+({PY_ID}(?:\s*,\s*{PY_ID})*)\s+in\s+(.+?):",
        lambda m: f"için {m.group(1)} içinde {m.group(2)}:",
        gecici_kod
    )

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

    # Noktalı ters çeviri sonuçları (modül metotları ve Ursina nesne
    # özellikleri) hemen yer tutucuyla korunur. Aksi halde, aşağıda çalışan
    # genel sözlük (ters_regex) bu sonuçların İÇİNDEKİ tek kelimeleri
    # tekrar yakalayabilir: örn. "ursina.başlat" üretildikten sonra genel
    # sözlükte "ursina -> ursina_kütüphanesi" gibi bağımsız bir madde varsa,
    # "ursina.başlat" yeniden "ursina_kütüphanesi.başlat" haline bozulur;
    # ya da "uygulama.fps" içindeki "fps" kelimesi "animasyon_fps" olarak
    # tekrar çevrilebilir.
    noktali_koru = {}

    def _noktali_koru(deger):
        uid = len(noktali_koru)
        yer = f"\x00NOKTALI_{uid}\x00"
        noktali_koru[yer] = deger
        return yer

    if ters_modul_tablo:
        ters_modul_sirali = sorted(ters_modul_tablo, key=len, reverse=True)

        ters_modul_desen = re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in ters_modul_sirali) + r")\b"
        )

        gecici_kod = ters_modul_desen.sub(
            lambda m: _noktali_koru(ters_modul_tablo[m.group(0)]),
            gecici_kod
        )

    # Ursina ve PyMuPDF nesne özelliklerinin ters çevirisi: mouse.x -> fare.x,
    # color.red -> renk.kırmızı, sayfa.draw_rect -> sayfa.dörtgen_çiz, vb.
    # NOT: PYMUPDF_NESNE_TABLO burada eklenmezse python_kodu_turkceye_cevir()
    # (.py -> TürKod) bu metotları hiç Türkçeleştirmez; .turkod -> .py yönü
    # (_regex_tabanli_ceviri) ayrı bir koddur ve ondan etkilenmez.
    ters_nesne_tablo = {
        py: tr for tr, py in {**URSINA_NESNE_TABLO, **PYMUPDF_NESNE_TABLO}.items()
    }
    if ters_nesne_tablo:
        ters_nesne_sirali = sorted(ters_nesne_tablo, key=len, reverse=True)
        ters_nesne_desen = re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in ters_nesne_sirali) + r")\b"
        )
        gecici_kod = ters_nesne_desen.sub(
            lambda m: _noktali_koru(ters_nesne_tablo[m.group(0)]),
            gecici_kod
        )

    # İsim koruması (_isimleri_sakla) burada, nesne tablosu ters
    # çevirisinden SONRA çalıştırılır. Sebep: "sayfa", "belge", "şekil" gibi
    # ayrılmış adlar neredeyse her zaman bir atamanın sol tarafında bulunur
    # (örn. "sayfa = pdf.new_page(...)") ve bu yüzden `tanimlar` kümesine
    # otomatik girer. İsim koruması daha önce çalışsaydı "sayfa" yer
    # tutucuyla değişir, ters_nesne_desen artık "sayfa.draw_rect" dizisini
    # metinde bulamaz ve draw_rect/draw_circle/draw_line gibi metotlar hiç
    # çevrilmeden Python biçiminde kalırdı (yaşanan hata buydu). Forward
    # yöndeki _regex_tabanli_ceviri aynı sırayı zaten uyguluyor (bkz. o
    # fonksiyondaki benzer yorum).
    # Kullanıcı adı bir TürKod anahtar kelimesiyle aynıysa (ör. Python'da
    # "den = ..." -> TürKod'da "den" = from) geri çeviride anahtar kelime
    # sanılır ve kod bozulur: böyle adlar "_" ekiyle yeniden adlandırılır.
    cakisan = {t for t in tanimlar if t in KORUNMAYAN_KELIMELER}
    if cakisan:
        gecici_kod = re.sub(
            r"\b(" + "|".join(re.escape(c) for c in sorted(cakisan, key=len, reverse=True)) + r")\b",
            r"\1_",
            gecici_kod,
        )
        tanimlar = (tanimlar - cakisan) | {c + "_" for c in cakisan}

    gecici_kod, isim_sak = _isimleri_sakla(gecici_kod, tanimlar)

    ters_regex, ters_tablo = _ters_sozluk_hazirla()

    # Türkçe karşılık, kodda zaten kullanıcı tarafından tanımlı bir adsa
    # (ör. "min" -> "minimum" ama kodda "minimum = ..." değişkeni var)
    # çeviri yapılmaz; aksi halde iki farklı ad tek ada çöker.
    gecici_kod = ters_regex.sub(
        lambda m: m.group(0) if ters_tablo[m.group(0)] in tanimlar
        else ters_tablo[m.group(0)],
        gecici_kod
    )

    gecici_kod = _yer_tutuculari_geri_koy(gecici_kod, noktali_koru)
    gecici_kod = _yer_tutuculari_geri_koy(gecici_kod, isim_sak)
    gecici_kod = _yer_tutuculari_geri_koy(
        gecici_kod,
        {f"\x00METIN_{uid}\x00": metin for uid, metin in saklanan_metinler},
    )
    return gecici_kod

_BLOK_BASLIGI_RE = re.compile(
    r"^(?:eğer|eger|değilse_eğer|degilse_eger|değilse|degilse|döngü|dongu|için|icin|"
    r"ile|dene|hata_yakala|sonunda|fonksiyon|sınıf|sinif|eşzamansız|eszamansiz|"
    r"if|elif|else|while|for|with|try|except|finally|def|class|async|match|case)\b")


def _ayni_satira_import_ekle(kod, tr_ad, import_satiri):
    """Importu, sınıfın ilk kullanımından ÖNCE çalışan ilk modül düzeyi basit
    ifade satırının başına "; " ile ekler (satır sayısı değişmez, import
    modül düzeyinde kalır). Uygun satır yoksa dosyanın başına yeni satır
    eklenir (eski davranış)."""
    m = re.search(rf"\b{re.escape(tr_ad)}\b", kod)
    if not m:
        return import_satiri + "\n" + kod
    kullanim_satiri = kod.count("\n", 0, m.start())
    satirlar = kod.split("\n")
    derinlik = 0
    onceki_devam = False
    for i, satir in enumerate(satirlar):
        if i > kullanim_satiri:
            break
        govde = satir.lstrip(" \t")
        girinti = len(satir) - len(govde)
        uygun = (
            derinlik == 0 and not onceki_devam and girinti == 0 and govde
            and not govde.startswith(("#", "@", "\x00"))
            and not govde.rstrip().endswith(":")
            and not _BLOK_BASLIGI_RE.match(govde)
        )
        if uygun:
            satirlar[i] = import_satiri + "; " + satir
            return "\n".join(satirlar)
        if (govde and girinti == 0 and derinlik == 0 and not onceki_devam
                and (govde.rstrip().endswith(":") or govde.startswith("@")
                     or _BLOK_BASLIGI_RE.match(govde))):
            # Kullanımdan önce modül düzeyinde bir blok başlıyor: blok önce
            # çalışabileceğinden import en başa konur.
            break
        derinlik += sum(satir.count(c) for c in "([{") - sum(satir.count(c) for c in ")]}")
        derinlik = max(0, derinlik)
        onceki_devam = satir.rstrip().endswith("\\")
    return import_satiri + "\n" + kod


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

    # Ursina'nın alt-modülden içe aktarılması gereken prefab sınıfları:
    # FirstPersonController ve PlatformerController2d, "from ursina import *"
    # ile bile otomatik erişilebilir DEĞİLDİR (resmi örneklerin hepsinde ayrı
    # bir "from ursina.prefabs.X import Y" satırı gerekir). Bu yüzden bu
    # sınıflardan biri kodda kullanılıyorsa, "içe_aktar ursina" satırının
    # hemen ardına gerekli alt-modül importu otomatik eklenir.
    _URSINA_ALT_MODUL_SINIFLARI = {
        "birinci_şahıs_denetleyici": (
            "ursina.prefabs.first_person_controller", "FirstPersonController"
        ),
        "platform_denetleyici_2b": (
            "ursina.prefabs.platformer_controller_2d", "PlatformerController2d"
        ),
    }
    for _tr_ad, (_alt_modul, _sinif_adi) in _URSINA_ALT_MODUL_SINIFLARI.items():
        if not re.search(rf"\b{_tr_ad}\b", gecici_kod):
            continue
        _eklenecek_import = f"from {_alt_modul} import {_sinif_adi}"
        # "içe_aktar ursina[_kütüphanesi] [olarak TAKMA_AD]" satırının TAMAMINI
        # (takma ad varsa onu da) tek seferde yakala; aksi halde " olarak X"
        # kısmı satırda öksüz kalıp yanlış yerlere eklenir.
        _ursina_import_deseni = re.compile(
            r"\biçe_aktar\s+ursina(?:_kütüphanesi)?\b(?:\s+olarak\s+(" + TR_ID + r"))?"
        )
        _eslesme = _ursina_import_deseni.search(gecici_kod)
        if _eslesme:
            _takma_ad = _eslesme.group(1)
            if _takma_ad:
                _ana_import = f"import ursina as {_takma_ad}"
            else:
                _ana_import = "import ursina"
            # Aynı satıra "; " ile eklenir: yeni satır eklemek TürKod ve
            # Python satırlarının 1:1 eşleşmesini bozuyor, hata satırları ve
            # hata ayıklayıcı yanlış satırı gösteriyordu.
            gecici_kod = (
                gecici_kod[:_eslesme.start()]
                + f"{_ana_import}; {_eklenecek_import}"
                + gecici_kod[_eslesme.end():]
            )
        else:
            # "içe_aktar ursina" hiç yazılmamışsa (başka yerden geldiği
            # varsayılır), gerekli alt-modül importu sınıfın ilk kullanıldığı
            # basit ifade satırının başına "; " ile eklenir (satır sayısı
            # değişmez). Uygun satır yoksa eski yönteme (dosya başına yeni
            # satır) geri düşülür.
            gecici_kod = _ayni_satira_import_ekle(
                gecici_kod, _tr_ad, _eklenecek_import)

    if tanimlar is None:
        tanimlar = kullanici_tanimlari(gecici_kod)

    # Nesne tabloları (pencere.başlık, fare.x, renk.kırmızı, belge.kaydet,
    # sayfa.metin_al ...) İSİM KORUMASINDAN (_isimleri_sakla) ÖNCE
    # çalıştırılmalı. Sebep: kullanıcı bu ayrılmış isimleri genellikle bir
    # değişkene atar (örn. "belge = pymupdf.aç(...)", "uygulama =
    # ursina.başlat()"). İsim koruması önce çalışırsa "belge" yer tutucuyla
    # değişir ve "belge.metin_al" deseni bir daha asla eşleşmez. Burada,
    # henüz hiçbir isim maskelenmeden, ham Türkçe metin üzerinde noktalı
    # eşleşme yapılır; STRING/YORUM içerikleri ise bu fonksiyonun başında
    # zaten \x00METIN_N\x00 ile maskelenmiş olduğundan etkilenmez.
    # Tablolar yalnızca ilgili kütüphane dosyada geçiyorsa uygulanır: aksi
    # halde tkinter kodundaki "pencere.başlık(...)" Ursina'nın "window.title"
    # nesnesine, "renk.kırmızı" gibi kullanıcı değişkenleri "color.red"e
    # çevrilip NameError veriyordu.
    if re.search(r"\bursina", gecici_kod):
        gecici_kod = _URSINA_NESNE_DESEN.sub(
            lambda m: URSINA_NESNE_TABLO[m.group(0)],
            gecici_kod
        )
    if re.search(r"\b(?:pymupdf|fitz)\b", gecici_kod):
        gecici_kod = _PYMUPDF_NESNE_DESEN.sub(
            lambda m: PYMUPDF_NESNE_TABLO[m.group(0)],
            gecici_kod
        )

    gecici_kod, isim_sak = _isimleri_sakla(gecici_kod, tanimlar)

    gecici_kod = _TK_PARAM_DESEN.sub(
        lambda m: m.group(1) + TK_PARAMLER[m.group(2)],
        gecici_kod
    )

    gecici_kod = _TK_SABIT_DESEN.sub(
        lambda m: TK_SABITLER.get(m.group(0), m.group(0)),
        gecici_kod
    )

    # Yalnızca "için i " -> "for i in " yapılır; aralık(...) sözlükle range(...)
    # olur. Eskiden "\(([^)]*)\)" ilk ')' ile bittiği için
    # "için i aralık(uzunluk(a)):" geçersiz "for i range(len(a)):" üretiyordu.
    python_kodu = re.sub(
        rf"\biçin\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+(?=aralık\s*\()",
        r"for \1 in ",
        gecici_kod
    )
    python_kodu = re.sub(
        rf"\bdöngü\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+(?=aralık\s*\()",
        r"for \1 in ",
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
        rf"\[([^]]+?)(\s+)için(\s+)({TR_ID})(\s+)içinde(\s+)(.*?)(\s+)eğer(\s+)(.*?)\]",
        r"[\1\2for\3\4\5in\6\7\8if\9\10]",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\[([^]]+?)(\s+)için(\s+)({TR_ID})(\s+)içinde(\s+)([^]]+?)\]",
        r"[\1\2for\3\4\5in\6\7]",
        python_kodu
    )
    _ISE_BLOK = (r"\b(?!(?:eğer|değilse_eğer|değilse|döngü|için|fonksiyon|sınıf|dene|"
                 r"hata_yakala|sonunda|ile|ve|veya|değil)\b)")
    # "A değil ise:" -> "not A:"  (eskiden "A == not:" üretiliyordu)
    python_kodu = re.sub(
        _ISE_BLOK + rf"({TR_ID})\s+değil\s+ise\s*:",
        r"not \1:",
        python_kodu,
    )
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
        # Parantezler korunur: çok satırlı ve sonda virgüllü listeler ancak
        # parantez içinde geçerli Python'dur.
        r"from \1 import (\2)",
        python_kodu
    )

    # (Ursina/PyMuPDF nesne tabloları artık isim korumasından ÖNCE, yukarıda
    # gecici_kod üzerinde uygulanıyor — bkz. yorum satırı.)

    python_kodu = _MODUL_METOT_DESEN.sub(
        lambda m: MODUL_METOT_TABLO[m.group(0)],
        python_kodu
    )

    sozluk_regex, sozluk_tablo = _sozluk_hazirla()

    python_kodu = sozluk_regex.sub(
        lambda m: sozluk_tablo.get(m.group(0), m.group(0)),
        python_kodu
    )

    python_kodu = _yer_tutuculari_geri_koy(python_kodu, isim_sak)
    python_kodu = _yer_tutuculari_geri_koy(
        python_kodu,
        {f"\x00METIN_{uid}\x00": metin for uid, metin in saklanan_metinler},
    )

    return python_kodu


_TANIM_MASKE_DESENI = re.compile(
    r'[rRbBfFuU]{0,2}"""[\s\S]*?"""|[rRbBfFuU]{0,2}\'\'\'[\s\S]*?\'\'\''
    r'|[rRbBfFuU]{0,2}"(?:[^"\\\n]|\\.)*"|[rRbBfFuU]{0,2}\'(?:[^\'\\\n]|\\.)*\''
    r'|#[^\n]*'
)


def _tanim_icin_maskele(kod):
    """Metin ve yorum içeriklerini boşlukla maskeler (satır yapısı korunur).

    Kullanıcı tanımı taraması ham kaynakta yapıldığında metinlerin/yorumların
    içindeki "... olarak yazdır", "uzunluk = 1" gibi ifadeler kullanıcı tanımı
    sanılıyor; o kelimeler dosyanın TAMAMINDA çeviriden muaf kalıyordu
    (yazdır(1) -> yazdır(1), çalışma zamanında NameError)."""
    return _TANIM_MASKE_DESENI.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), kod)


def turkce_kodu_donustur(turkce_kod: str) -> str:
    """Token tabanlı koruma ile güçlendirilmiş TürKod -> Python çevirici."""
    turkce_kod = turkce_kod.replace('\r\n', '\n').replace('\r', '\n')
    # Not Defteri vb. ile kaydedilmiş dosyalardaki BOM, Python'da "geçersiz
    # karakter" hatası verir.
    turkce_kod = turkce_kod.lstrip('\ufeff')
    saklanan_parcalar = []
    # Tokenizer/tanım çıkarımı hata verirse aşağıdaki çağrı NameError ile
    # çökmesin: tanımlar None ise _regex_tabanli_ceviri kendisi hesaplar.
    tanimlar = None
    try:
        tanimlar = kullanici_tanimlari(_tanim_icin_maskele(turkce_kod))
        tokenlar = tokenize(turkce_kod, kullanici_adlari=tanimlar)

        # ÖNEMLİ: KULLANICI token'ını KORUMA! 
        # _regex_tabanli_ceviri içindeki _isimleri_sakla zaten kullanıcı tanımlarını koruyor.
        # Eğer burada da korursak, `için i aralık` gibi yapısal regex'ler bozulur.
        korunacak_turler = {TokenTuru.METIN, TokenTuru.F_METIN, TokenTuru.YORUM}
        korunacak_tokenlar = [t for t in tokenlar if t.tur in korunacak_turler]

        korunacak_tokenlar.sort(key=lambda t: (t.satir, t.sutun))

        # Tek geçiş: satır başları bir kez hesaplanır ve çıktı parçalar
        # halinde kurulur (eskiden her token için metin baştan bölünüyor ve
        # karakter listesi kaydırılıyordu: uzun dosyalarda karesel maliyet).
        baslar = _satir_baslari(turkce_kod)
        parcalar = []
        son = 0
        for t in korunacak_tokenlar:
            bas = _pozisyon_hesapla(turkce_kod, t.satir, t.sutun, baslar)
            bit = _pozisyon_hesapla(turkce_kod, t.son_satir, t.son_sutun, baslar)
            if bas is None or bit is None or bas >= bit or bas < son:
                continue
            uid = len(saklanan_parcalar)
            saklanan_parcalar.append((uid, turkce_kod[bas:bit]))
            parcalar.append(turkce_kod[son:bas])
            parcalar.append(f"\x00TKOR_{uid}\x00")
            son = bit
        parcalar.append(turkce_kod[son:])

        gecici_kod = "".join(parcalar)

    except Exception:
        gecici_kod = turkce_kod
        saklanan_parcalar = []

    python_kodu = _regex_tabanli_ceviri(gecici_kod, tanimlar)

    return _yer_tutuculari_geri_koy(
        python_kodu,
        {f"\x00TKOR_{uid}\x00": parca for uid, parca in saklanan_parcalar},
    )
