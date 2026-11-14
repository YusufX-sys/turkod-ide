"""TurKod <-> Python cevirici fonksiyonlar."""
import builtins
import keyword
import re
import threading
import warnings

from .dictionary import (KORUNMAYAN_KELIMELER, SOZLUK, TERS_SOZLUK, kullanici_tanimlari,
                         yalniz_oznitelik_adlari, _parantez_derinligi_haritasi)
from .deger_sozlugu import ters_degerleri_cevir
from .modul_sozlugu import MODUL_ADI_YENILEME, MODUL_ESKI_ADLARI, MODUL_METOTLARI_EK
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
        "ı": "i", "İ": "I",
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
    # Eskiden "tk.sonlandirici" idi: "tk" kullanıcının takma adı olduğundan
    # isim korumasıyla maskeleniyor ve madde hiç eşleşmiyordu; Türkçe yazım
    # da yoktu. Sonuç sözlükteki sonlandırıcı -> end ile "tk.end" (hata) idi.
    ".sonlandırıcı": ".END",
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
    ".mesaj_kutusu": ".messagebox",
    ".dosya_diyaloğu": ".filedialog",
    ".renk_seçici": ".colorchooser",
    ".açılır_kutu": ".Combobox",
    ".ağaç_görünümü": ".Treeview",
    ".sekmeli_defter": ".Notebook",
    ".not_defteri": ".Notebook",
    ".ilerleme_çubuğu": ".Progressbar",
    ".grafik_başlığı": ".title",
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
    ".simge_resmi": ".iconbitmap",
    ".ikon_resmi": ".iconbitmap",
    ".odaklan": ".focus",
    ".protokol": ".protocol",
    ".pencere_kapatma_protokolü": ".protocol",
    ".yapılandır": ".configure",
    ".ayarla": ".config",
}

TK_PARAMLER = {
    # Tam Türkçe adlar; eskileri (aşağıda) takma ad olarak çalışmaya devam eder.
    "gid_metin": "text",
    "satır_sırası": "row",
    "sütun_sırası": "column",
    "xml_metin": "text",
    "metin": "text",
    "komut": "command",
    "değişken": "variable",
    "metin_değişkeni": "textvariable",
    "genişlik": "width",
    "yükseklik": "height",
    "arkaplan_rengi": "bg",
    "ön_renk": "foreground",
    "metin_rengi": "fg",
    "ön_renk_kısa": "fg",
    "yazı_tipi": "font",
    "x_kenar_boşluğu": "padx",
    "y_kenar_boşluğu": "pady",
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
    "jng": "json",
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
    "django_kütüphanesi": "django",
    "django_uygulaması": "django",
    "pytest_kütüphanesi": "pytest",
    "tensorflow_kütüphanesi": "tensorflow",
    "torch_kütüphanesi": "torch",
    "redis_kütüphanesi": "redis",
    "docker_kütüphanesi": "docker",
    "coverage_kütüphanesi": "coverage",
    "py_oyun": "pygame",
    "resim_kütüphanesi": "PIL",
    # Standart kütüphane modüllerinin Türkçe adları (TurKod_Sozluk.txt ile aynı)
    "koleksiyonlar": "collections",
    "yineleme_araçları": "itertools",
    "günlükleme": "logging",
    "dosya_araçları": "shutil",
    "geçici_dosyalar": "tempfile",
    "tip_ipuçları": "typing",
    "eşzamansız_gç": "asyncio",
    "birim_testi": "unittest",
    "argüman_ayrıştırma": "argparse",
    "veri_sınıfları": "dataclasses",
    "numaralandırmalar": "enum",
    "metin_sabitleri": "string",
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
    # "içe_aktar tkinter_arayüz" yukarıda özel olarak da ele alınıyor; burada
    # durması "tkinter_arayüz.X" noktalı kullanımının modül tablosuyla
    # çevrilebilmesi içindir.
    "tkinter_arayüz": "tkinter",
    # Arayüz, oyun, görüntü, ofis ve grafik kütüphaneleri. Kısa (Python) adı
    # ÖNCE gelir: ters çeviride numpy/torch'ta olduğu gibi o seçilir.
    "customtkinter": "customtkinter",
    "özel_tkinter": "customtkinter",
    "kivy": "kivy",
    "kivy_kütüphanesi": "kivy",
    "arcade": "arcade",
    "arcade_kütüphanesi": "arcade",
    "pyglet": "pyglet",
    "pyglet_kütüphanesi": "pyglet",
    "cv2": "cv2",
    "görüntü_işleme": "cv2",
    "openpyxl": "openpyxl",
    "excel_kütüphanesi": "openpyxl",
    "docx": "docx",
    "word_kütüphanesi": "docx",
    "pptx": "pptx",
    "sunum_kütüphanesi": "pptx",
    "matplotlib": "matplotlib",
    "grafik_kütüphanesi": "matplotlib",
    "seaborn": "seaborn",
    "istatistiksel_grafik": "seaborn",
    "plotly": "plotly",
    "etkileşimli_grafik": "plotly",
    "selenium": "selenium",
    "tarayıcı_otomasyonu": "selenium",
    # Düz sözlükte adı geçen standart kütüphane modülleri. Düz sözlükteki adı
    # bir fonksiyona da karşılık gelenler (kopyala -> copy() gibi) ayrı bir
    # modül adı alır.
    "zaman": "time",
    "kopyalama": "copy",
    "dosya_deseni": "glob",
    "platform": "platform",
    "güzel_yazdırma": "pprint",
    "sinyal_işleme": "signal",
    "ağ_soketi": "socket",
    "güvenli_bağlantı": "ssl",
    "durum_sabitleri": "stat",
    "c_kütüphanesi": "ctypes",
    "uyarılar": "warnings",
    "kod_izleme": "trace",
    "etkileşimli_kod": "code",
    "kopya_kayıt_defteri": "copyreg",
    "satır_düzenleme": "readline",
    "belirteç_sabitleri": "token",
    "token_sabitleri": "token",
    "_tkinter": "_tkinter",
    # Eskiden Türkçe adı olmayan standart kütüphane modülleri.
    "soyut_sınıflar": "abc",
    "bağlam_araçları": "contextlib",
    "vad": "csv",
    "işleçler": "operator",
    "yığın_kuyruğu": "heapq",
    "ikili_arama": "bisect",
    "metin_sarma": "textwrap",
    "taban64": "base64",
    "benzersiz_kimlik": "uuid",
    "ondalık_sayılar": "decimal",
    "zip_arşivi": "zipfile",
    "girdi_çıktı": "io",
    "parola_al_modülü": "getpass",
    "ağ_tarayıcısı": "webbrowser",
    "iş_kuyruğu": "queue",
    "süre_ölçer": "timeit",
    "saat_dilimleri": "zoneinfo",
    "yapılandırma_ayrıştırıcı": "configparser",
    "ikili_yapı": "struct",
    "tür_dizisi": "array",
    "eposta_gönderme": "smtplib",
    "komut_satırı_kabuğu": "shlex",
    "dosya_karşılaştırma": "filecmp",
    "fark_bulucu": "difflib",
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
        "dağılım_gama": "gammavariate",
        "dağılım_gauss": "gauss",
        "dağılım_lognormal": "lognormvariate",
        "dağılım_normal": "normalvariate",
        "dağılım_üçgen": "triangular",
    },
    "matematik": {
        "karekök": "sqrt",
        "faktöriyel": "factorial",
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
        # math.pow / math.exp / math.tau eskiden bu tabloda yoktu: ters
        # çeviri onları "matematikf.üst_al" (yerleşik pow) yapıyor, gidiş-
        # dönüşte 8.0 yerine 8 çıkıyordu; "from math import exp" de
        # "üstel_al" adıyla ImportError veriyordu. Düz sözlükteki adlar
        # (üs_al, üstel) kanoniktir; matematikf'teki adlar takma addır.
        "üs_al": "pow",
        "üst_al": "pow",
        "üstel": "exp",
        "üstel_al": "exp",
        "tau_sayısı": "tau",
        "sonsuz": "inf",
        "sayı_değil": "nan",
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
        "tümleyen_hata_fonksiyonu": "erfc",
        "hata_fonksiyonu_t": "erfc",
        "üstel_eksi_1": "expm1",
        "mod": "fmod",
        "kesirli_üst": "frexp",
        "toplam_hassas": "fsum",
        "gama_fonksiyonu": "gamma",
        "yakın_mı": "isclose",
        "sonlu_mu": "isfinite",
        "sonsuz_mu": "isinf",
        "sayı_değil_mi": "isnan",
        "tanım_değil_mi": "isnan",
        "tamsayı_kök": "isqrt",
        "kesirli_çarp": "ldexp",
        "gama_logaritma": "lgamma",
        "logaritma10": "log10",
        "logaritma_eksi_1": "log1p",
        "logaritma2": "log2",
        "kesirli_ayır": "modf",
        "sonraki_kayan_sayı": "nextafter",
        "permütasyon": "perm",
        "çarpım": "prod",
        "kalan": "remainder",
        "sinüs_h": "sinh",
        "tanjant_h": "tanh",
        "tam_kısım": "trunc",
        "son_basamak_birimi": "ulp",
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
        "oyun_kolu_sistemi": "joystick",
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
        "kirli_hareketli_resim": "DirtySprite",
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
        "tuş_kaçış": "K_ESCAPE",
        "tuş_esc": "K_ESCAPE",
        # Pencere Bayrakları (Flags)
        "tam_ekran": "FULLSCREEN",
        "yeniden_boyutlandırılabilir": "RESIZABLE",
        "çerçevesiz": "NOFRAME",
        "çift_tampon": "DOUBLEBUF",
        "donanım_yüzeyi": "HWSURFACE",
        "alfa_şeffaflık": "SRCALPHA",
        # Alt modüllerdeki sık kullanılanlar (pygame.mixer / image / sprite ...).
        # Alt modül adlarının düz sözlükte Türkçesi yok: "olay", "resim" gibi
        # adlar oyun kodunda değişken adı olarak çok kullanılıyor.
        "ses_sistemi_başlat": "mixer.init",
        "ses_yükle": "mixer.Sound",
        "müzik_yükle": "mixer.music.load",
        "müzik_çal": "mixer.music.play",
        "müzik_durdur": "mixer.music.stop",
        "müzik_duraklat": "mixer.music.pause",
        "müzik_sürdür": "mixer.music.unpause",
        "müzik_ses_düzeyi": "mixer.music.set_volume",
        "müzik_çalıyor_mu": "mixer.music.get_busy",
        "resim_yükle": "image.load",
        "resim_kaydet": "image.save",
        "resmi_ölçekle": "transform.scale",
        "resmi_döndür": "transform.rotate",
        "yazı_tipi_sistemi_başlat": "font.init",
        "yazı_tipi_yükle": "font.Font",
        "milisaniye_al": "time.get_ticks",
        "zamanlayıcı_ayarla": "time.set_timer",
        "fare_tuşları": "mouse.get_pressed",
        "fare_konumu_ayarla": "mouse.set_pos",
        "hareketli_resim": "sprite.Sprite",
        "hareketli_grup": "sprite.Group",
        "hareketli_çarpışma": "sprite.spritecollide",
        "grup_çarpışma": "sprite.groupcollide",
        "vektör2": "math.Vector2",
        "ekran_yüzeyi": "display.get_surface",
        "olay_gönder": "event.post",
        "olay_bekle": "event.wait",
        "yüzey": "Surface",
        "renk": "Color",
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
        "eşzamansız_fonksiyon": "Async",
        "saniye_bekle": "wait",
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
        "eşzamansız_fonksiyon": "Async",
        "saniye_bekle": "wait",
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
        "utc_damgası": "datetime.utcfromtimestamp",
        "damgadan_tarih": "datetime.fromtimestamp",
        "iso_ayrıştır": "datetime.fromisoformat",
        "tarih_birleştir": "datetime.combine",
        "tarih_ayrıştır": "datetime.strptime",
        "en_büyük_tarih": "datetime.max",
        "en_küçük_tarih": "datetime.min",
        "zaman_farkı": "timedelta",
        "tarih": "date",
        "zaman": "time",
        "saat_dilimi": "timezone",
        "dilim_bilgisi": "tzinfo",
        # Python'daki gibi sınıf adıyla yazılan biçim: "tarih_saat.tarih_saat.
        # şimdi()". Eskiden "datetime.datetime.datetime.now()" (AttributeError)
        # oluyordu. Yukarıdaki kısa biçimden SONRA gelir: ters çeviride
        # datetime.datetime.now yine "tarih_saat.şimdi" olur.
        "tarih_saat": "datetime",
        "tarih_saat.şimdi": "datetime.now",
        "tarih_saat.bugün": "datetime.today",
        "tarih_saat.utc_şimdi": "datetime.utcnow",
        "tarih_saat.utc_damgası": "datetime.utcfromtimestamp",
        "tarih_saat.damgadan_tarih": "datetime.fromtimestamp",
        "tarih_saat.iso_ayrıştır": "datetime.fromisoformat",
        "tarih_saat.tarih_birleştir": "datetime.combine",
        "tarih_saat.tarih_ayrıştır": "datetime.strptime",
        "tarih_saat.en_büyük_tarih": "datetime.max",
        "tarih_saat.en_küçük_tarih": "datetime.min",
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
        "GezinilebilirMetin": "NavigableString",
        "Döngü": "Iterator",
        "ElemanFiltre": "ElementFilter",
        "GüzelÇorba": "BeautifulSoup",
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
        "KarakterVerisi": "CData",
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
        "ÖzetKimlikDoğrulama": "DigestAuth",
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
        "varsayılan_aiohttp_istemcisi": "DefaultAioHttpClient",
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
        "numaralandırma": "Enum",
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
        "AyGünNanosaniye": "MonthDayNano",
        "ÇalışmaZamanıBilgisi": "RuntimeInfo",
        "CihazAtamaTürü": "DeviceAllocationType",
        "KayıtTopluAkışOkuyucu": "RecordBatchStreamReader",
        "KayıtTopluAkışYazıcı": "RecordBatchStreamWriter",
        "KayıtTopluDosyaOkuyucu": "RecordBatchFileReader",
        "KayıtTopluDosyaYazıcı": "RecordBatchFileWriter",
        "MetaDataSürümü": "MetadataVersion",
        "SürümBilgi": "VersionInfo",
        "TabloGrupla": "TableGroupBy",
        "aralık": "arange",
        "cpp_yapım_bilgisi": "CppBuildInfo",
        "dizi": "array",
        "dizi_birleştir": "concat_arrays",
        "ikili": "binary",
        "arrow_iptal_edildi": "ArrowCancelled",
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
        "hızlan_üstel": "easeInExpo",
        "hızlan_zıpla": "easeInBounce",
        "hızlan_çember": "easeInCirc",
        "nokta": "Point",
        "onay": "confirm",
        "orta": "center",
        "pencere": "Window",
        "geri_sayım": "countdown",
        "sürükle": "drag",
        "sürükle_göreli": "dragRel",
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
        "takma_ad_seçenekleri": "AliasChoices",
        "takma_ad_üreticisi": "AliasGenerator",
        "takma_ad_yolu": "AliasPath",
        "base64_bayt": "Base64Bytes",
        "base64_kodlayıcı": "Base64Encoder",
        "base64_metin": "Base64Str",
        "base64_url_bayt": "Base64UrlBytes",
        "base64_url_metin": "Base64UrlStr",
        "clickhouse_dsn": "ClickHouseDsn",
        "cockroach_dsn": "CockroachDsn",
        "klasör_yolu": "DirectoryPath",
        "sonra_doğrulayıcı": "AfterValidator",
        "sonsuz_nan_izni": "AllowInfNan",
        "temel_model": "BaseModel",
        "temel_yapılandırma": "BaseConfig",
        "tüm_http_url": "AnyHttpUrl",
        "tüm_url": "AnyUrl",
        "tüm_web_soket_url": "AnyWebsocketUrl",
        "önce_doğrulayıcı": "BeforeValidator",
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
        "AnahtarAlanıBildirimleri": "KeyspaceNotifications",
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
        "AnahtarOlayıKanalı": "KeyeventChannel",
        "SürücüBilgisi": "DriverInfo",
        "VeriHatası": "DataError",
        "bloklama_bağlantı_havuzu": "BlockingConnectionPool",
        "kimlik_doğrulama_hatası": "AuthenticationError",
        "kimlik_doğrulama_yanlış_argüman_hatası": "AuthenticationWrongNumberOfArgsError",
        "meşgul_yükleme_hatası": "BusyLoadingError",
        # === ASIL İSTEMCİ SINIFI (önceki kaynakta hiç yoktu) ===
        "istemci": "Redis",
        "eski_istemci": "StrictRedis",
        "url_ile_bağlan": "Redis.from_url",
    },
    "sklearn_kütüphanesi": {
        "kopyala": "clone",
        "yapılandırma_ayarla": "set_config",
        "yapılandırma_bağlamı": "config_context",
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
        "açıkla": "explain",
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
        "BağlantısızGradyanlar": "UnconnectedGradients",
        "CihazÖzelliği": "DeviceSpec",
        "Değişken": "Variable",
        "DizinliParçalı": "IndexedSlices",
        "DizinliParçalıÖzelliği": "IndexedSlicesSpec",
        "KritikBölüm": "CriticalSection",
        "GradyanKaydı": "GradientTape",
        "GradyanKaydet": "RegisterGradient",
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
        "KayanNoktaDepolama": "FloatStorage",
        "KısaDepolama": "ShortStorage",
        "QTamsayı32Depolama": "QInt32Storage",
        "QTamsayı8Depolama": "QInt8Storage",
        "QUYuzde2x4Depolama": "QUInt2x4Storage",
        "QUYuzde4x2Depolama": "QUInt4x2Storage",
        "QUYuzde8Depolama": "QUInt8Storage",
        "TamSayıDepolama": "IntStorage",
        "UzunDepolama": "LongStorage",
        "YarıDepolama": "HalfStorage",
        "sinir_ağı": "nn",
        "gradyan_ölçekleyici": "GradScaler",
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
        "kalem_indir": "pendown",
        "kalem_bırak": "pendown",
        "kalem_kaldır": "penup",
        "kalem_rengi": "pencolor",
        "kalem_boyutu": "pensize",
        "hız_ayarla": "speed",
        "çember": "circle",
        "konuma_git": "goto",
        "x_ayarla": "setx",
        "y_ayarla": "sety",
        "yön_ayarla": "setheading",
        "ekranı_temizle": "clearscreen",
        "arka_plan_rengi": "bgcolor",
        "ekran_ayarla": "setup",
        # turtle.done(): çizim biter, pencere kapatılana kadar açık kalır.
        "tamamla": "done",
        "çıkışta_bekle": "done",
        "dolgu_rengi_ayarla": "fillcolor",
        "dolgu_başla": "begin_fill",
        "dolgu_bitir": "end_fill",
        "izleyici_ayarla": "tracer",
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
        "dağılım_grafiği": "scatter",
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

# Modüllerin genel API'sinde olup yukarıda ya da düz sözlükte karşılığı
# bulunmayan adlar modul_sozlugu.py'de durur. Ek maddeler aynı Python
# modülüne giden TÜM TürKod adlarının tablolarına eklenir; mevcut maddeler
# ezilmez. Tablosu olmayan TürKod adları (işletim_sistemi, torch_kütüphanesi
# ...) ilk tabloyu paylaşır ya da yeni bir tablo alır. Yeni anahtarlar dict
# sonuna eklendiği için ters çeviride ("ilk yazılan kazanır") mevcut kısa
# adlar (torch, ursina ...) önceliğini korur.
for _modul_tr, _ek in MODUL_METOTLARI_EK.items():
    _py_modul = MODUL_CEVIRILERI[_modul_tr]
    _adlar = [_t for _t, _p in MODUL_CEVIRILERI.items() if _p == _py_modul]
    _tablolar = {id(MODUL_METOTLARI[_t]): MODUL_METOTLARI[_t]
                 for _t in _adlar if _t in MODUL_METOTLARI}
    if not _tablolar:
        _yeni = MODUL_METOTLARI.setdefault(_modul_tr, {})
        _tablolar = {id(_yeni): _yeni}
    _ilk = next(iter(_tablolar.values()))
    for _t in _adlar:
        MODUL_METOTLARI.setdefault(_t, _ilk)
    for _tablo in _tablolar.values():
        for _tr_ad, _py_ad in _ek.items():
            _tablo.setdefault(_tr_ad, _py_ad)
        # Değişen eski adlar yeni adların ARDINA eklenir: çalışırlar ama ters
        # çeviride ("ilk yazılan kazanır") yeni ad seçilir.
        for _eski_ad, _yeni_ad in MODUL_ESKI_ADLARI.get(_modul_tr, {}).items():
            if _yeni_ad in _ek:
                _tablo.setdefault(_eski_ad, _ek[_yeni_ad])

# Önceden var olan maddelerin tam Türkçe adları: yeni ad eskisinin hemen
# önüne eklenir (ters çeviride yeni ad seçilir), eski ad takma ad olarak
# çalışmaya devam eder. Tablo nesnesi yerinde değiştirilir (paylaşılıyor).
for _modul_tr, _yenilemeler in MODUL_ADI_YENILEME.items():
    _tablo = MODUL_METOTLARI.get(_modul_tr)
    if _tablo is None:
        continue
    _yeni_tablo = {}
    for _tr_ad, _py_ad in _tablo.items():
        _yeni_ad = _yenilemeler.get(_tr_ad)
        # Yeni ad tabloda başka bir anlamla zaten varsa yenileme atlanır
        # (mevcut madde ezilmesin).
        if _yeni_ad and _tablo.get(_yeni_ad, _py_ad) == _py_ad:
            _yeni_tablo.setdefault(_yeni_ad, _py_ad)
        _yeni_tablo.setdefault(_tr_ad, _py_ad)
    _tablo.clear()
    _tablo.update(_yeni_tablo)

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
    "coverage_kütüphanesi", "django_kütüphanesi", "django_uygulaması",
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

# Ayırıcı: ',' / '(' ya da boşluk dizisinin YALNIZCA başı, geri izlemesiz.
# Eskiden '[,\(\s]\s*' her boşluk konumundan başlayıp dizinin sonuna kadar
# tarıyordu: uzun boşluk/boş satır dizilerinde çeviri karesel yavaşlıyordu.
# ':' sonrası boşluk alınmaz: "şehir: metin = 'Ankara'" bir tip ipucudur,
# tkinter "metin=" argümanı değil (eskiden "şehir: text = ..." oluyordu).
_TK_PARAM_DESEN = re.compile(
    r"([,\(]\s*+|(?<![\s:])\s++)(" +"|".join(re.escape(k) for k in sorted(TK_PARAMLER, key=len, reverse=True)) + r")(?=\s*=[^=])"
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
        if py_metot in BUILTIN_FUNCS and py_modul == "math" and (
                py_metot != "pow" or metotlar is MODUL_METOTLARI.get("matematikf")):
            # math modülünde abs/min/max/round/sum yoktur: yerleşik kullanılır.
            # (Eskiden bu kural TÜM modüllere uygulanıyordu; "numpy.toplam(a,
            # axis=0)" -> "sum(a, axis=0)" TypeError veriyordu.) math.pow
            # vardır: "matematik.üs_al" eskiden yerleşik pow'a gidiyordu;
            # yalnızca matematikf'in eski davranışı (yerleşik pow) korunur.
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = py_metot
        else:
            # NOT: Eskiden hedef modül adıyla başlıyorsa (örn. tarih_saat ->
            # "datetime.now") önek eklenmiyordu; bu "datetime.now()" (modülde
            # yok -> AttributeError) üretiyordu. Doğrusu sınıf üzerinden
            # "datetime.datetime.now()". Normal durum: pygame.mixer.music.get_pos
            # veya pygame.display.set_mode.
            MODUL_METOT_TABLO[f"{modul}.{tr_metot}"] = f"{py_modul}.{py_metot}"

# Noktalı ad zinciri (a.b.c). Modül tabloları on binlerce madde içerdiğinden
# her maddeyi `\bmodül.ad\b` seçeneği olarak tek desene koymak hem derlemede
# (içe aktarma saniyeler sürüyordu) hem eşleştirmede çok yavaştı; zincir
# yakalanıp parçaları tabloda aranır.
_NOKTALI_ZINCIR = re.compile(r"\w+(?:\.\w+)+")


def _noktali_tablo_uygula(kod, tablo, donustur, en_cok_parca):
    """`tablo` anahtarlarını (noktalı adlar) kodda değiştirir.

    `\\banahtar\\b` seçeneklerini uzundan kısaya dizen bir desenle aynı sonucu
    verir: zincirin her parça başından itibaren en uzun anahtar seçilir,
    eşleşen bölüm `donustur(anahtar)` ile değişir."""
    def zinciri_cevir(m):
        parcalar = m.group(0).split(".")
        n = len(parcalar)
        sonuc = []
        i = 0
        while i < n:
            for j in range(min(n, i + en_cok_parca), i + 1, -1):
                anahtar = ".".join(parcalar[i:j])
                if anahtar in tablo:
                    sonuc.append(donustur(anahtar))
                    i = j
                    break
            else:
                sonuc.append(parcalar[i])
                i += 1
        return ".".join(sonuc)

    return _NOKTALI_ZINCIR.sub(zinciri_cevir, kod)


_MODUL_METOT_EN_COK_PARCA = max(
    (k.count(".") + 1 for k in MODUL_METOT_TABLO), default=2)


# ---------------------------------------------------------
# "den X içe_aktar Y" ile tek başına içe aktarılan modül adları
# ---------------------------------------------------------
# Modül tabloları yalnızca "modül.ad" biçimini çevirir. "den numpy
# içe_aktar dizi" yazıldığında hem içe aktarma satırındaki hem de koddaki
# çıplak "dizi" adı modül tablosuna göre (array) çevrilmelidir; aksi halde
# düz sözlük "dizi"yi başka bir ada çevirir ya da hiç çevirmez.
_DEN_ICE_AKTAR_SATIRI = re.compile(
    rf"^([ \t]*)den[ \t]+({TR_MODUL_ID})[ \t]+içe_aktar[ \t]+(\([^)]*\)|[^\n#]*)", re.M)
_ICE_AKTAR_DEN_SATIRI = re.compile(
    rf"^([ \t]*)içe_aktar[ \t]+({TR_ID}(?:[ \t]*,[ \t]*{TR_ID})*)[ \t]+den[ \t]+({TR_MODUL_ID})[ \t]*$",
    re.M)
_FROM_IMPORT_SATIRI = re.compile(
    r"^[ \t]*from[ \t]+([\w.]+)[ \t]+import[ \t]+(\([^)]*\)|[^\n#]*)", re.M)
_CIPLAK_AD = re.compile(r"(?<![\w.\x00])\w+(?![\w\x00])")
_KWARG_SONRASI = re.compile(r"\s*=(?!=)")


def _ice_aktarma_ogeleri(liste):
    """"a, b olarak c, (d,)" -> [("a", None), ("b", "c"), ("d", None)]."""
    ogeler = []
    for parca in liste.strip().strip("()").split(","):
        sozcukler = parca.split()
        if not sozcukler:
            continue
        takma = sozcukler[2] if len(sozcukler) >= 3 and sozcukler[1] in ("olarak", "as") else None
        ogeler.append((sozcukler[0], takma))
    return ogeler


def _turkce_modul_adi_karsiligi(modul_tr, ad_tr):
    """TürKod modülündeki adın, o modülden doğrudan içe aktarılabilen Python
    adı; yoksa None. ("numpy", "dizi") -> "array"."""
    if modul_tr in MODUL_CEVIRILERI:
        beklenen = MODUL_CEVIRILERI[modul_tr]
    else:
        beklenen = MODUL_METOT_TABLO.get(modul_tr)  # alt modül: torch.sinir_ağı
        if not beklenen:
            return None
    deger = MODUL_METOT_TABLO.get(f"{modul_tr}.{ad_tr}", "")
    on, _, ad = deger.rpartition(".")
    return ad if on == beklenen else None


_DUZ_KARSILIKLAR = None


def _duz_karsilik(ad_tr):
    """Düz sözlükte ad_tr'nin Python karşılığı ("tamsayı" -> "int"); yoksa None."""
    global _DUZ_KARSILIKLAR
    if _DUZ_KARSILIKLAR is None:
        _DUZ_KARSILIKLAR = {
            str(k).replace(r"\b", "").strip(): v for k, v in SOZLUK.items()
        }
    return _DUZ_KARSILIKLAR.get(ad_tr)


def _duz_sozlukle_cakisir(ad_tr, py):
    """"den rastgele içe_aktar tamsayı" (randint): "tamsayı" düz sözlükte
    başka bir şeydir (int). Böyle bir adın koddaki çıplak kullanımları düz
    anlamında kalır; yoksa dosyadaki her tamsayı("5") randint("5") oluyordu.
    Modülün işlevi düz sözlükteki adıyla (rastgele_tamsayı) çağrılır.
    Yalnız düz anlamı Python'un yerleşik bir adı (int, range, max, str ...)
    olan kelimeler için: "den numpy içe_aktar dizi" gibi yerleşik olmayan
    çakışmalarda modül anlamı geçerli kalır."""
    duz = _duz_karsilik(ad_tr)
    return duz is not None and duz != py and hasattr(builtins, duz)


_ICE_AKTARMA_MODUL_ADI = re.compile(
    r"^[ \t]*(?:(?:from|den)[ \t]+[\w.]+|(?:import|içe_aktar)[ \t]+[^\n#;]*)", re.M)


def _ciplak_adlari_degistir(kod, tablo, yer_tutucu):
    """Koddaki çıplak (öznitelik ya da anahtar kelime argümanı olmayan)
    adları tablodaki karşılıklarının yer tutucusuyla değiştirir.

    İçe aktarma satırlarındaki MODÜL adlarına dokunulmaz: eskiden "from
    random import random" ile gelen random -> ondalık eşlemesi satırın
    modül adını da değiştiriyor, "den ondalık içe_aktar ondalık" (gidiş-
    dönüşte ModuleNotFoundError) çıkıyordu."""
    if not tablo:
        return kod
    atla = []
    for m in _ICE_AKTARMA_MODUL_ADI.finditer(kod):
        if not re.search(r"[ \t]den[ \t]", m.group(0)):
            atla.append((m.start(), m.end()))

    def degistir(m):
        ad = m.group(0)
        if ad not in tablo or _KWARG_SONRASI.match(kod, m.end()):
            return ad
        if atla and any(b <= m.start() < s for b, s in atla):
            return ad
        return yer_tutucu(tablo[ad])
    return _CIPLAK_AD.sub(degistir, kod)


def _iki_argumanli_int_cagrilarini_cevir(kod, tablo, yer_tutucu):
    """tablo: {"tamsayı": "randint"}. Tam iki konumsal argümanlı ve ilk
    argümanı metin olmayan "tamsayı(a, b)" çağrılarını modül işlevine
    çevirir; "tamsayı('ff', 16)" ve tek argümanlı çağrılar int kalır."""
    desen = re.compile(
        r"(?<![\w.\x00])(" + "|".join(map(re.escape, tablo)) + r")(?=\s*\()")

    def argumanlar(bas):
        # bas: '(' konumu. Üst düzey argüman metinleri; kapanmazsa None.
        derinlik, parca_bas, parcalar = 0, bas + 1, []
        for i in range(bas, len(kod)):
            ch = kod[i]
            if ch in "([{":
                derinlik += 1
            elif ch in ")]}":
                derinlik -= 1
                if derinlik == 0:
                    parcalar.append(kod[parca_bas:i])
                    return parcalar
            elif ch == "," and derinlik == 1:
                parcalar.append(kod[parca_bas:i])
                parca_bas = i + 1
        return None

    def degistir(m):
        ad = m.group(1)
        parcalar = argumanlar(kod.index("(", m.end()))
        if parcalar and not parcalar[-1].strip():
            parcalar = parcalar[:-1]  # sondaki virgül
        if not parcalar or len(parcalar) != 2:
            return ad
        ilk = parcalar[0].strip()
        if (ilk.startswith(("\x00METIN", "\x00TKOR", "*")) or ilk[:1] in "\"'"
                or any(re.match(r"\w+\s*=(?!=)", p.strip()) or p.strip().startswith("*")
                       for p in parcalar)):
            return ad
        return yer_tutucu(tablo[ad])

    return desen.sub(degistir, kod)


def _ice_aktarilan_adlari_cevir(kod, tanimlar, yer_tutucu):
    """"den X içe_aktar Y" / "içe_aktar Y den X" satırlarındaki ve koddaki
    çıplak Y adlarını X'in modül tablosuna göre Python adına çevirir.

    "den X içe_aktar *" için yalnızca düz sözlükte bulunmayan adlar çevrilir
    (düz sözlükteki kelimelerin anlamı değişmesin diye). Kullanıcının kendi
    tanımladığı adlara dokunulmaz."""
    if "içe_aktar" not in kod or not re.search(r"\bden\b", kod):
        return kod
    # "içe_aktar a, b den X" -> "den X içe_aktar a, b" (anlamı aynı, tek biçim).
    kod = _ICE_AKTAR_DEN_SATIRI.sub(
        lambda m: (f"{m.group(1)}den {m.group(3)} içe_aktar {m.group(2)}"
                   if any(_turkce_modul_adi_karsiligi(m.group(3), a)
                          for a in re.split(r"[ \t]*,[ \t]*", m.group(2)))
                   else m.group(0)),
        kod)
    ciplak = {}
    sozluk_kelimeleri = None

    def satiri_cevir(m):
        nonlocal sozluk_kelimeleri
        girinti, modul_tr, liste = m.group(1), m.group(2), m.group(3)
        if liste.strip() == "*":
            if sozluk_kelimeleri is None:
                sozluk_kelimeleri = _sozluk_kelimeleri()
            on = modul_tr + "."
            for anahtar in MODUL_METOT_TABLO:
                if anahtar.startswith(on):
                    ad = anahtar[len(on):]
                    if "." in ad or ad in tanimlar:
                        continue
                    if ad in sozluk_kelimeleri:
                        if _duz_karsilik(ad) == "int":
                            py = _turkce_modul_adi_karsiligi(modul_tr, ad)
                            if py and py != "int":
                                int_cakisanlar.setdefault(ad, py)
                        continue
                    py = _turkce_modul_adi_karsiligi(modul_tr, ad)
                    if py:
                        ciplak.setdefault(ad, py)
            return m.group(0)
        degisen = False
        yeni = liste
        for ad, takma in _ice_aktarma_ogeleri(liste):
            if (takma is None and ad not in tanimlar and ad in MODUL_CEVIRILERI
                    and modul_tr in MODUL_CEVIRILERI):
                golgeleyen[ad] = MODUL_CEVIRILERI[modul_tr]
            py = _turkce_modul_adi_karsiligi(modul_tr, ad)
            if not py:
                continue
            degisen = True
            yeni = re.sub(rf"(?<![\w.]){re.escape(ad)}(?!\w)", lambda _m, p=py: yer_tutucu(p), yeni, count=1)
            if takma is None and ad not in tanimlar:
                if not _duz_sozlukle_cakisir(ad, py):
                    ciplak.setdefault(ad, py)
                elif _duz_karsilik(ad) == "int":
                    int_cakisanlar.setdefault(ad, py)
        if not degisen:
            return m.group(0)
        return f"{girinti}den {modul_tr} içe_aktar {yeni}"

    # "den tarih_saat içe_aktar tarih_saat": içe aktarılan ad (datetime
    # sınıfı) modülün Türkçe adıyla aynı. Modül tablosu "tarih_saat.şimdi"yi
    # modül biçiminde (datetime.datetime.now) verir; burada ad sınıfı
    # gösterdiğinden modül öneki atılır: datetime.now. Eskiden
    # "datetime.datetime.now" AttributeError veriyordu.
    golgeleyen = {}
    # "den rastgele içe_aktar tamsayı" sonrası "tamsayı(1, 5)": düz anlamı
    # (int) korunur ama iki konumsal argümanla ve ilki metin değilken
    # int(x, taban) hiçbir zaman kastedilmez; eskiden int(1, 5) olup
    # anlaşılmaz "int() can't convert non-string with explicit base"
    # hatası veriyordu. Bu çağrılar modülün işlevine (randint) gider.
    int_cakisanlar = {}
    kod = _DEN_ICE_AKTAR_SATIRI.sub(satiri_cevir, kod)
    if int_cakisanlar:
        kod = _iki_argumanli_int_cagrilarini_cevir(kod, int_cakisanlar, yer_tutucu)
    if golgeleyen:
        en_cok = _MODUL_METOT_EN_COK_PARCA

        def golge_zinciri(m):
            parcalar = m.group(0).split(".")
            on_py = golgeleyen.get(parcalar[0])
            if on_py is None:
                return m.group(0)
            for j in range(min(len(parcalar), en_cok), 1, -1):
                py = MODUL_METOT_TABLO.get(".".join(parcalar[:j]))
                if py and py.startswith(on_py + "."):
                    return yer_tutucu(py[len(on_py) + 1:]) + "".join(
                        "." + p for p in parcalar[j:])
            return m.group(0)

        kod = re.sub(r"(?<![\w.])\w+(?:\.\w+)+", golge_zinciri, kod)
    if ciplak:
        kod = _ciplak_adlari_degistir(kod, ciplak, yer_tutucu)
    return kod


_ICE_AKTAR_SATIRI = re.compile(r"^[ \t]*içe_aktar[ \t]+([^\n#;]+)", re.M)
_IMPORT_OLARAK = re.compile(r"^[ \t]*import[ \t]+([^\n#;]+)", re.M)


def _python_modulunun_turkce_adi(modul_py):
    """Modül tablosu olan ilk TürKod modül adı ("tkinter" -> "tkinter_arayüz",
    "scipy.stats" -> "bilimsel_hesaplama.istatistik"); yoksa None."""
    if "." in modul_py:
        tr = _ters_modul_tablosu()[0].get(modul_py)
        return tr if tr and tr in MODUL_METOT_TABLO else None
    for tr, py in MODUL_CEVIRILERI.items():
        if py == modul_py and tr in MODUL_METOTLARI:
            return tr
    return None


def _takma_adli_uyeleri_cevir(kod, yer_tutucu):
    """"içe_aktar tensorflow_kütüphanesi olarak tf" ile gelen
    "tf.sabit_değer" -> "tf.constant". Modül tabloları "modül.ad" biçimini
    çevirir; takma ad kullanıcı adı olarak korunduğu için eskiden yalnızca
    düz sözlükte bulunan adlar çevriliyordu. Takma adın kendisi aynen kalır."""
    takma = {}
    for m in _ICE_AKTAR_SATIRI.finditer(kod):
        for ad, ad_takma in _ice_aktarma_ogeleri(m.group(1)):
            if not ad_takma:
                # "içe_aktar re" (Python adıyla): "re.BÜYÜK_KÜÇÜK_YOKSAY" de
                # Türkçe tablodan çevrilir. Ters çeviri, modülün Türkçe adı
                # bir kullanıcı adıyla çakışınca (desen = ...) bu biçimi üretir.
                if ad not in MODUL_CEVIRILERI and "." not in ad:
                    modul_tr = _python_modulunun_turkce_adi(ad)
                    if modul_tr:
                        takma[ad] = (modul_tr, ad)
                continue
            on = MODUL_CEVIRILERI.get(ad) or (MODUL_METOT_TABLO.get(ad) if "." in ad else None)
            if on:
                takma[ad_takma] = (ad, on)
    # Python biçiminde yazılmış "import numpy as np" (TürKod bunu da kabul
    # eder; "içe_aktar tkinter_arayüz olarak tk" de bu adıma gelmeden önce bu
    # biçime çevrilir).
    for m in _IMPORT_OLARAK.finditer(kod):
        for ad, ad_takma in _ice_aktarma_ogeleri(m.group(1)):
            modul_tr = _python_modulunun_turkce_adi(ad) if ad_takma else None
            if modul_tr:
                takma.setdefault(ad_takma, (modul_tr, ad))
    if not takma:
        return kod
    en_cok = _MODUL_METOT_EN_COK_PARCA + 1

    def zinciri_cevir(m):
        parcalar = m.group(0).split(".")
        bilgi = takma.get(parcalar[0])
        if bilgi is None:
            return m.group(0)
        modul_tr, on_py = bilgi
        for j in range(min(len(parcalar), en_cok), 1, -1):
            py = MODUL_METOT_TABLO.get(modul_tr + "." + ".".join(parcalar[1:j]))
            if py is None or not py.startswith(on_py + "."):
                continue
            kalan = parcalar[j:]
            return (yer_tutucu(f"{parcalar[0]}.{py[len(on_py) + 1:]}")
                    + "".join("." + p for p in kalan))
        return m.group(0)

    return re.sub(r"(?<![\w.])\w+(?:\.\w+)+", zinciri_cevir, kod)


def _from_import_adlarini_cevir(kod, tanimlar, ters_tablo, yer_tutucu):
    """Ters yön: "from numpy import array" ve koddaki çıplak "array" ->
    "dizi" (Türkçe modül tablosu karşılığı)."""
    if "import" not in kod or "from" not in kod:
        return kod
    ciplak = {}

    def py_karsiligi(modul_py, ad):
        tam = ters_tablo.get(f"{modul_py}.{ad}")
        return tam.rpartition(".")[2] if tam else None

    def satiri_cevir(m):
        modul_py, liste = m.group(1), m.group(2)
        if liste.strip() == "*":
            on = modul_py + "."
            for anahtar, tam in ters_tablo.items():
                if anahtar.startswith(on):
                    ad = anahtar[len(on):]
                    if "." not in ad and ad not in TERS_SOZLUK and ad not in tanimlar:
                        ciplak.setdefault(ad, tam.rpartition(".")[2])
            return m.group(0)
        bas = m.start(2) - m.start(0)
        yeni = liste
        for ad, takma in _ice_aktarma_ogeleri(liste):
            tr = py_karsiligi(modul_py, ad)
            if not tr:
                continue
            yeni = re.sub(rf"(?<![\w.]){re.escape(ad)}(?!\w)", lambda _m, t=tr: yer_tutucu(t), yeni, count=1)
            # "from random import randint": içe aktarma satırı "tamsayı" olur,
            # ama koddaki çıplak randint "tamsayı" olursa int ile karışır;
            # düz sözlükteki adı (rastgele_tamsayı) kullanılır.
            if takma is None and ad not in tanimlar and not _duz_sozlukle_cakisir(tr, ad):
                ciplak.setdefault(ad, tr)
        return m.group(0)[:bas] + yeni

    kod = _FROM_IMPORT_SATIRI.sub(satiri_cevir, kod)
    if ciplak:
        kod = _ciplak_adlari_degistir(kod, ciplak, yer_tutucu)
    return kod

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
    "sahne": "scene",
}

# Sözlükteki uzun adlar (ursina_penceresi -> window, ursina_kamera -> camera ...)
# aynı nesne tablolarını kullanır. Eskiden bunlar tabloya girmediği için
# "ursina_penceresi.tam_ekran" gibi bağlamlı özellikler Türkçe yazılamıyordu
# ("tam_ekran" düz sözlükte pygame'in FULLSCREEN sabitidir). Ters çeviride
# (Python -> TürKod) kısa/kanonik ad seçilir; akıllı düzeltici önerileri de
# yalnızca kanonik adlarla üretilir (URSINA_NESNELERI'ye eklenmezler).
URSINA_NESNE_TAKMA_ADLARI = {
    "ursina_penceresi": "pencere",
    "ursina_kamera": "kamera",
    "ursina_fare": "fare",
    "ursina_uygulaması": "uygulama",
    "ursina_uygulama": "uygulama",
    "ursina_renk": "renk",
    "ursina_sahne": "sahne",
}

URSINA_NESNELERI = {
    "pencere": {
        "başlık": "title",
        "kenarsız": "borderless",
        "çıkış_düğmesi": "exit_button",
        "sbk_sayacı": "fps_counter",
        "fps_sayacı": "fps_counter",
        "tam_ekran": "fullscreen",
        "konum": "position",
        "boyut": "size",
        "renk": "color",
        "simge": "icon",
        "dikey_eşitleme": "vsync",
        "en_boy_oranı": "aspect_ratio",
        "her_zaman_üstte": "always_on_top",
        "ekranı_ortala": "center_on_screen",
        "görüntü_kipi": "render_mode",
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
        "konum": "position",
        "nokta": "point",
        "dünya_noktası": "world_point",
        "dünya_dikmesi": "world_normal",
        "dünya_normali": "world_normal",
    },
    "kamera": {
        "z": "z",
        "kilitli": "locked",
        "hedef": "target",
        "görüş_açısı": "fov",
        "ortografik": "orthographic",
        "arayüz": "ui",
        "en_boy_oranı": "aspect_ratio",
        "yakın_kesme_düzlemi": "clip_plane_near",
        "uzak_kesme_düzlemi": "clip_plane_far",
    },
    "sahne": {
        "sis_rengi": "fog_color",
        "sis_yoğunluğu": "fog_density",
        "temizle": "clear",
    },
    "uygulama": {
        "sbk": "fps",
        "fps": "fps",
        "kapat": "quit",
        "adı": "name",
        "sürümü": "version",
        "duraklatıldı": "paused",
        "zaman_ölçeği": "time_scale",
        "duraklat": "pause",
        "sürdür": "resume",
        "geliştirme_modu": "development_mode",
        "bilgileri_yazdır": "print_info",
        "uyarıları_yazdır": "print_warnings",
        "varlık_klasörü": "asset_folder",
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
        # Ursina'da ayrı turquoise ve cyan renkleri var; eskiden turkuaz -> cyan idi.
        # (lacivert -> navy ve gümüş -> silver kaldırıldı: Ursina 8.3'te bu
        # renkler yok, AttributeError veriyordu.)
        "turkuaz": "turquoise",
        "camgöbeği": "cyan",
        "gök_mavisi": "azure",
        "limon_yeşili": "lime",
        "menekşe": "violet",
        "zeytin_yeşili": "olive",
        "şeftali": "peach",
        "somon": "salmon",
        "duman": "smoke",
        "açık_gri": "light_gray",
        "koyu_gri": "dark_gray",
        "altın": "gold",
        # Tam Türkçe adlar (eski kısaltmalar aşağıda takma ad olarak kalır).
        "kym": "rgb",
        "kyma": "rgba",
        "tdp": "hsv",
        "rgb": "rgb",
        "rgba": "rgba",
        "hsv": "hsv",
        "rastgele_renk": "random_color",
        "ton_ver": "tint",
        "parlaklık": "brightness",
        "ters_renk": "inverse",
    },
}

# ASCII yazımlar (renk.sari, pencere.baslik) tablo kurulmadan ÖNCE eklenir;
# eskiden tablo kurulduktan sonra eklendiği için hiç eşleşmiyorlardı.
_ascii_alias_ekle(URSINA_NESNELERI)

URSINA_NESNE_TABLO = {}
for _nesne_tr, _ozellikler in URSINA_NESNELERI.items():
    _py_nesne = URSINA_NESNE_ADLARI[_nesne_tr]
    for _tr_oz, _py_oz in _ozellikler.items():
        URSINA_NESNE_TABLO[f"{_nesne_tr}.{_tr_oz}"] = f"{_py_nesne}.{_py_oz}"
for _takma, _kanonik in URSINA_NESNE_TAKMA_ADLARI.items():
    _py_nesne = URSINA_NESNE_ADLARI[_kanonik]
    for _tr_oz, _py_oz in URSINA_NESNELERI[_kanonik].items():
        URSINA_NESNE_TABLO[f"{_takma}.{_tr_oz}"] = f"{_py_nesne}.{_py_oz}"

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
        "üst_veri": "metadata",
        "meta_veri": "metadata",
        "yeni_sayfa": "new_page",
        "sayfa_sil": "delete_page",
        "sayfa_seç": "select",
        "tbb_ekle": "insert_pdf",
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
    "\x00(?:METIN|TKOR|NOKTALI|ICE)_\\d+\x00|__ISIM_SABITI_\\d+__"
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

        # Maddelerin hepsi `\bkelime\b` ve kelime yalnızca harf/rakam/_ ise
        # böyle bir eşleşme tam bir kelimeye denk gelir: binlerce seçenekli
        # (~90 KB) tek desen yerine her kelimeyi yakalayıp tabloda aramak
        # aynı sonucu ~10 kat hızlı verir (çağıran, tabloda olmayanı aynen
        # bırakır).
        if all(re.fullmatch(r"\w+", k) for k in cevirme_tablosu):
            _SOZLUK_REGEX = re.compile(r"\w+")
        else:
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


_ONCEKI_AD = re.compile(r"([\w.]+)\s*$")
_ATAMA_ESITTIR = re.compile(r"\s*=(?!=)")
_ICE_AKTAR_BASI = re.compile(r"^([ \t]*(?:içe_aktar|ice_aktar)[ \t]+)([^\n#;]+)", re.M)
_DEN_BASI = re.compile(rf"^[ \t]*den[ \t]+({TR_MODUL_ID})[ \t]+içe_aktar\b", re.M)
_ICE_AKTAR_DEN_SONU = re.compile(
    rf"^[ \t]*içe_aktar[ \t]+[^\n#;]+?[ \t]+den[ \t]+({TR_MODUL_ID})[ \t]*$", re.M)


def _ice_aktarma_modul_konumlari(kod):
    """İçe aktarma satırlarındaki modül adlarının başlangıç konumları:
    {konum: takma_ad_eklenmeli_mi}. "içe_aktar zaman" (tek parçalı, takma
    adsız) için True; "den zaman içe_aktar ...", "içe_aktar a.b",
    "içe_aktar zaman olarak z" için False."""
    konumlar = {}
    for m in _ICE_AKTAR_BASI.finditer(kod):
        if re.search(r"[ \t]den[ \t]", m.group(2)):
            continue  # "içe_aktar a den X": aşağıda ayrıca ele alınır
        konum = m.start(2)
        for parca in m.group(2).split(","):
            bosluk = len(parca) - len(parca.lstrip())
            ogeler = parca.split()
            if ogeler:
                takmasiz = len(ogeler) == 1 and "." not in ogeler[0]
                konumlar[konum + bosluk] = takmasiz
            konum += len(parca) + 1
    for desen in (_DEN_BASI, _ICE_AKTAR_DEN_SONU):
        for m in desen.finditer(kod):
            konumlar[m.start(1)] = False
    return konumlar


_BLOK_BASI = re.compile(
    rf"^([ \t]*)(?:(?:eşzamansız|eszamansiz|async)[ \t]+)?"
    rf"(?:fonksiyon|def|sınıf|sinif|class)[ \t]+({TR_ID})", re.M)
_KURESEL_SATIRI = re.compile(
    rf"\b(?:küresel|kuresel|global|yerel_olmayan|nonlocal)[ \t]+({TR_ID}(?:[ \t]*,[ \t]*{TR_ID})*)")


def _kapsam_bilgisi(kod, tanimlar, kutuphaneler=()):
    """Kullanıcı adlarının nerede korunacağı.

    Döner: (uye_adlari, yerel_bolgeler, veri_adlari, kalitim)
    * veri_adlari: başka nesnede çağrıldığında kütüphane metodu sayılabilecek
      veri öznitelikleri (bkz. aşağıdaki yorum).
    * kalitim: (bölgeler, tanımlı_üyeler). Bölgeler bir kütüphane sınıfından
      türeyen (sınıf Oyuncu(kaplumbağa.Kaplumbağa)) üst düzey sınıfların
      gövde aralıklarıdır; tanımlı_üyeler kullanıcının bu dosyada tanımladığı
      ya da atadığı üye adlarıdır.
    * uye_adlari: nokta sonrasında ("x.ad") korunacak adlar: kendisi./self.
      öznitelikleri, "nesne.ad = ..." hedefleri, metotlar (girintili
      fonksiyonlar), sınıf adları ve bu dosyada tanımlı olmayan (başka
      modülden gelen) adlar. Üst düzey fonksiyon/değişken adları nokta
      sonrasında korunmaz: eskiden "fonksiyon bul" yazınca "metin.bul(...)"
      çevrilmiyor, AttributeError veriyordu.
    * yerel_bolgeler: yalnızca fonksiyon/sınıf gövdelerinde tanımlanan
      adlar -> o gövdelerin (başlangıç, bitiş) aralıkları. Bu adlar gövde
      dışında korunmaz: eskiden bir fonksiyondaki "toplam = 0", dosyanın
      geri kalanındaki "toplam(liste)" çağrısını da sum'a çevirtmiyordu.
    """
    tanimlar = set(tanimlar)
    derinlik = _parantez_derinligi_haritasi(kod)
    satirlar = kod.split("\n")
    baslar = []
    konum = 0
    for s in satirlar:
        baslar.append(konum)
        konum += len(s) + 1

    def girinti(s):
        return len(s) - len(s.lstrip(" \t"))

    # En dıştaki fonksiyon/sınıf blokları: (baş, bitiş, ad).
    bolgeler = []
    sinif_uyeleri = set()
    i = 0
    while i < len(satirlar):
        m = _BLOK_BASI.match(satirlar[i])
        if not m or derinlik[baslar[i]] != 0:
            i += 1
            continue
        g = len(m.group(1))
        j = i + 1
        while j < len(satirlar):
            s = satirlar[j]
            if s.strip() and derinlik[baslar[j]] == 0 and girinti(s) <= g:
                break
            j += 1
        bit = baslar[j] - 1 if j < len(satirlar) else len(kod)
        bolgeler.append((baslar[i], bit, m.group(2)))
        if re.match(r"[ \t]*(?:sınıf|sinif|class)\b", satirlar[i]):
            # Sınıf gövdesindeki her ad (alan, metot, iç sınıf) bir üyedir:
            # "a.renk" sınıfın "renk = ..." alanını gösterir.
            # kendisi.X kullanımları ayrıca (aşağıda) eklenir; burada yalnızca
            # gerçek tanımlar alınır (kendisi.ileri(5) bir tanım değildir).
            sinif_uyeleri.update(kullanici_tanimlari(kod[baslar[i]:bit], oznitelikler=False))
        i = j

    uye_adlari = set(re.findall(rf"\b(?:kendisi|self)\.({TR_ID})", kod)) | sinif_uyeleri
    uye_adlari.update(re.findall(rf"(?<![\w.])\w+(?:\.\w+)*\.({TR_ID})\s*=(?!=)", kod))
    uye_adlari.update(re.findall(rf"\b(?:sınıf|sinif|class)[ \t]+({TR_ID})", kod))
    for m in _BLOK_BASI.finditer(kod):
        if m.group(1):
            uye_adlari.add(m.group(2))

    if not bolgeler:
        modul_duzeyi = kod
    else:
        parcalar, son = [], 0
        for bas, bit, _ad in bolgeler:
            parcalar.append(kod[son:bas])
            son = bit
        parcalar.append(kod[son:])
        modul_duzeyi = "\n".join(parcalar)
    kuresel = kullanici_tanimlari(modul_duzeyi)
    kuresel.update(ad for _b, _s, ad in bolgeler)
    for grup in _KURESEL_SATIRI.findall(kod):
        kuresel.update(p.strip() for p in grup.split(","))

    yerel_bolgeler = {}
    bu_dosya = set(kuresel)
    for bas, bit, _ad in bolgeler:
        for ad in kullanici_tanimlari(kod[bas:bit]):
            bu_dosya.add(ad)
            if ad in tanimlar and ad not in kuresel:
                yerel_bolgeler.setdefault(ad, []).append((bas, bit))
    bu_dosya.update(uye_adlari)
    # Başka modülden ya da başka yoldan gelen adlar her yerde korunur.
    uye_adlari.update(tanimlar - bu_dosya)
    # Veri öznitelikleri (kendisi.hız = 5, nesne.renk = ..., sınıf alanları)
    # başka bir nesnede ÇAĞRILDIKLARINDA (t.hız(0)) kütüphane metodu
    # sayılabilir. Çağrılabilir üyeler (metotlar, sınıf adları) ve bu
    # dosyada atanmadan yalnızca kullanılan adlar (başka modülde ya da üst
    # sınıfta tanımlı olabilir: kendisi.çiz()) bu kümeye girmez.
    cagrilabilir = set(re.findall(rf"\b(?:sınıf|sinif|class)[ \t]+({TR_ID})", kod))
    for m in _BLOK_BASI.finditer(kod):
        if m.group(1):
            cagrilabilir.add(m.group(2))
    veri_adlari = set(re.findall(
        rf"\b(?:kendisi|self)\.({TR_ID})[ \t]*(?:\*\*|//|[-+*/%])?=(?!=)", kod))
    veri_adlari.update(re.findall(rf"(?<![\w.])\w+(?:\.\w+)*\.({TR_ID})\s*=(?!=)", kod))
    veri_adlari.update(sinif_uyeleri)
    tanimli_uyeler = veri_adlari | cagrilabilir | (tanimlar - bu_dosya)
    veri_adlari -= cagrilabilir
    veri_adlari -= tanimlar - bu_dosya

    # Kütüphane sınıfından türeyen sınıflar: "kendisi.ileri(5)" kalıtılan
    # kütüphane metodudur. Eskiden kendisi.X kullanımı X'i kullanıcı adı
    # sayıp korur, self.ileri(5) AttributeError verirdi.
    kalitim_bolgeleri = []
    for bas, bit, _ad in bolgeler:
        taban = _KUTUPHANE_TABANLI_SINIF.match(kod, bas)
        if not taban:
            continue
        for parca in taban.group(1).split(","):
            parca = parca.strip()
            if parca.startswith("\x00ICE") or parca.split(".")[0] in kutuphaneler:
                kalitim_bolgeleri.append((bas, bit))
                break
    return uye_adlari, yerel_bolgeler, veri_adlari, (kalitim_bolgeleri, tanimli_uyeler)


_KUTUPHANE_TABANLI_SINIF = re.compile(
    rf"[ \t]*(?:sınıf|sinif|class)[ \t]+{TR_ID}[ \t]*\(([^)]*)\)")


_ALICI_ATAMASI = re.compile(
    rf"^[ \t]*((?:{TR_ID}\.)*{TR_ID})[ \t]*=(?!=)[ \t]*([^\n]*)", re.M)
_KENDI_ADLARI = frozenset(("kendisi", "self", "cls", "kendi_sınıfı", "kendi_sinifi"))


def _alici_turleri(kod, kutuphaneler, tanimlar):
    """Atamalardan nesnelerin türü: {"kendisi.t": "dis", "a": "kullanici"}.

    "dis": liste/sözlük/metin/sayı sabiti, kütüphane çağrısı
    (kaplumbağa.Kaplumbağa()) ya da yerleşik (liste(), sözlük()) ile
    oluşturulmuş nesne. "kullanici": dosyadaki bir sınıftan (Oyuncu())
    oluşturulmuş nesne. Farklı türlerle atanan adlar bilinmez sayılır."""
    sinif_adlari = set(re.findall(rf"\b(?:sınıf|sinif|class)[ \t]+({TR_ID})", kod))
    kelimeler = _sozluk_kelimeleri()
    turler = {}
    for m in _ALICI_ATAMASI.finditer(kod):
        hedef, sag = m.group(1), m.group(2).strip()
        tur = None
        if sag[:1] in "[{\"'" or re.match(r"\d|\x00(?:METIN|ICE)", sag):
            tur = "dis"
        else:
            cagri = re.match(r"((?:\w+\.)*\w+)\s*\(", sag)
            if cagri:
                zincir = cagri.group(1).split(".")
                if zincir[-1] in sinif_adlari:
                    tur = "kullanici"
                elif len(zincir) > 1 and zincir[0] in kutuphaneler:
                    tur = "dis"
                elif (len(zincir) == 1 and zincir[0] in kelimeler
                      and zincir[0] not in tanimlar):
                    tur = "dis"
        if hedef in turler and turler[hedef] != tur:
            tur = None
        turler[hedef] = tur
    return turler


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
    # Yalnızca kendisi.X olarak tanımlı adlar yalnızca öznitelik konumunda
    # (".X") korunur; çıplak X (ör. uzunluk(...)) normal çevrilir.
    yalniz_oz = yalniz_oznitelik_adlari(kod) & set(tanimlar)
    kutuphaneler = _kutuphane_adlari(kod)
    kutuphaneler -= oznitelikler
    ice_aktarma_konumlari = _ice_aktarma_modul_konumlari(kod)

    # Her konumu çevreleyen (en içteki) açık parantezin konumu; kwarg
    # denetimi için bir kez, doğrusal sürede hesaplanır. (Eskiden her aday
    # için 3000 karaktere kadar geriye doğru karakter karakter taranıyordu.)
    acik_parantez = None

    def _acik_parantezleri_hesapla():
        sonuc = [-1] * (len(kod) + 1)
        yigin = []
        for i, ch in enumerate(kod):
            sonuc[i] = yigin[-1] if yigin else -1
            if ch in "([{":
                yigin.append(i)
            elif ch in ")]}":
                if yigin:
                    yigin.pop()
        sonuc[len(kod)] = yigin[-1] if yigin else -1
        return sonuc

    def kutuphane_cagrisi_mi(konum):
        """konum'daki ad bir kwarg ise ve çağrılan şey bir kütüphane
        fonksiyonuysa True."""
        nonlocal acik_parantez
        if acik_parantez is None:
            acik_parantez = _acik_parantezleri_hesapla()
        i = acik_parantez[konum]
        if i < 0 or kod[i] != "(":
            return False
        onceki = _ONCEKI_AD.search(kod, max(0, i - 200), i)
        if not onceki:
            return False
        zincir = onceki.group(1).split(".")
        son = zincir[-1]
        if son in ("sözlük", "sozluk", "dict") or son in tanimlar:
            return False
        if len(zincir) > 1:
            return zincir[0] in kutuphaneler
        return son in _sozluk_kelimeleri()

    uye_adlari, yerel_bolgeler, veri_adlari, (kalitim_bolgeleri, tanimli_uyeler) = \
        _kapsam_bilgisi(kod, tanimlar, kutuphaneler)
    alici_turleri = None

    def baska_nesnenin_metodu_mu(isim, bas, son):
        """".X(" çağrısı kullanıcının X üyesini değil başka bir nesnenin
        (kütüphane/yerleşik) metodunu mu gösteriyor? Eskiden kendisi.hız = 5
        yazınca dosyadaki her ".hız" korunuyor, kendisi.t.hız(0) (kaplumbağa)
        çevrilmeyip AttributeError veriyordu; "kendisi.öğeler = []" de
        sözlük.öğeler()'i, "fonksiyon sona_ekle(kendisi, x)" metodu da
        liste.sona_ekle(5)'i bozuyordu. Çağrı olmayan erişimler (a.hız) ve
        kendisi./self. üzerindeki erişimler korunmaya devam eder."""
        nonlocal alici_turleri
        if not re.match(r"[ \t]*\(", kod[son:son + 40]):
            return False
        zincir = re.search(r"((?:\w+\.)*\w+)\.$", kod[max(0, bas - 200):bas])
        alici = zincir.group(1) if zincir else None
        if alici in _KENDI_ADLARI:
            # Kütüphane sınıfından türeyen sınıfta, kullanıcının tanımlamadığı
            # (fonksiyon X / kendisi.X = ... yok) kendisi.X(...) kalıtılan
            # kütüphane metodudur: sınıf Oyuncu(kaplumbağa.Kaplumbağa) içinde
            # kendisi.ileri(5) -> self.forward(5).
            return (isim not in tanimli_uyeler
                    and any(b <= bas < s for b, s in kalitim_bolgeleri))
        if alici_turleri is None:
            alici_turleri = _alici_turleri(kod, kutuphaneler, tanimlar)
        tur = alici_turleri.get(alici) if alici else None
        if tur == "kullanici":
            return False
        if tur == "dis":
            return True
        return isim in veri_adlari

    def kapsam_disi_mi(isim, bas, son, onceki_karakter):
        if onceki_karakter == ".":
            if isim not in uye_adlari:
                return True
            return baska_nesnenin_metodu_mu(isim, bas, son)
        bolgeler = yerel_bolgeler.get(isim)
        if not bolgeler:
            return False
        # Kullanıcı fonksiyonuna verilen anahtar kelime argümanı (f(ad=3))
        # parametre adıdır; çevrilmez.
        if _ATAMA_ESITTIR.match(kod, son):
            return False
        return not any(b <= bas < s for b, s in bolgeler)

    def isim_degistir(match):
        isim = match.group(0)
        bas, son = match.span()
        onceki_karakter = kod[bas - 1] if bas > 0 else ""
        if isim in yalniz_oz and onceki_karakter != ".":
            return isim
        if kapsam_disi_mi(isim, bas, son, onceki_karakter):
            return isim
        # İçe aktarma satırındaki KÜTÜPHANE modül adı her zaman çevrilir:
        # "içe_aktar zaman\nzaman = zaman.zaman()" eskiden "import zaman"
        # (ModuleNotFoundError) üretiyordu. Ad kullanıcı değişkeni de
        # olduğundan modül o adla bağlanır: "import time as zaman".
        if bas in ice_aktarma_konumlari and isim in MODUL_CEVIRILERI:
            if ice_aktarma_konumlari[bas] and isim not in isim_to_yer:
                yer = f"__ISIM_SABITI_{len(isim_sak)}__"
                isim_sak[yer] = isim
                isim_to_yer[isim] = yer
            if ice_aktarma_konumlari[bas]:
                return f"{isim} olarak {isim_to_yer[isim]}"
            return isim
        if onceki_karakter == "." and isim not in oznitelikler and kutuphaneler:
            zincir = re.search(r"([\w.]+)\.$", kod[max(0, bas - 200):bas])
            if zincir and zincir.group(1).split(".")[0] in kutuphaneler:
                return isim
        if _ATAMA_ESITTIR.match(kod, son) and kutuphane_cagrisi_mi(bas):
            return isim
        if isim not in isim_to_yer:
            yer = f"__ISIM_SABITI_{len(isim_sak)}__"
            isim_sak[yer] = isim
            isim_to_yer[isim] = yer
        return isim_to_yer[isim]

    return re.sub(isim_desen, isim_degistir, kod), isim_sak


_KWARG_ADI = re.compile(rf"(?<![\w.])({TR_ID})(?=\s*=(?!=))")


_KWARGS_FONKSIYONU = re.compile(
    rf"\b(?:fonksiyon|def)\s+({TR_ID})\s*\((?:[^()]|\([^()]*\))*\*\*")


def _sozluk_anahtarlarini_sakla(kod, isim_sak):
    """sözlük(...)/dict(...) çağrısındaki anahtar kelime argümanlarını
    (sözlüğün anahtarlarını) yer tutucuyla korur. Eskiden
    'sözlük(metin="a", sayı=3)' -> 'dict(text="a", number=3)' oluyor,
    sonraki x["metin"] KeyError veriyordu. **kwargs alan kullanıcı
    fonksiyonlarının çağrıları da aynıdır: selam(sehir="İzmir") ->
    selam(city=...) olup ekstra["sehir"] bulunamıyordu."""
    hedefler = {"sözlük", "sozluk", "dict"}
    hedefler.update(_KWARGS_FONKSIYONU.findall(kod))
    if not re.search(r"\b(?:" + "|".join(map(re.escape, hedefler)) + r")\s*\(", kod):
        return kod
    acik = [-1] * (len(kod) + 1)
    yigin = []
    for i, ch in enumerate(kod):
        acik[i] = yigin[-1] if yigin else -1
        if ch in "([{":
            yigin.append(i)
        elif ch in ")]}" and yigin:
            yigin.pop()

    def degistir(m):
        i = acik[m.start()]
        if i < 0 or kod[i] != "(":
            return m.group(0)
        onceki = _ONCEKI_AD.search(kod, max(0, i - 200), i)
        if not onceki or onceki.group(1).split(".")[-1] not in hedefler:
            return m.group(0)
        if m.group(0).startswith("__ISIM_SABITI_"):
            return m.group(0)  # zaten korunmuş (fonksiyon parametresi)
        yer = f"__ISIM_SABITI_{len(isim_sak)}__"
        isim_sak[yer] = m.group(0)
        return yer

    return _KWARG_ADI.sub(degistir, kod)


# ---------------------------------------------------------
# 3. DÖNÜŞTÜRÜCÜ FONKSİYONLAR
# ---------------------------------------------------------

_TERS_MODUL_TABLOSU = None


def _ters_modul_tablosu():
    """"python_modül.ad" -> "türkçe_modül.ad" tablosu ve en uzun anahtarın
    parça sayısı; bir kez kurulur. İlk yazılan kazanır (bkz. MODUL_METOTLARI
    sıralaması)."""
    global _TERS_MODUL_TABLOSU
    if _TERS_MODUL_TABLOSU is None:
        tablo = {}
        for modul_tr, metotlar in MODUL_METOTLARI.items():
            modul_py = MODUL_CEVIRILERI.get(modul_tr, modul_tr)
            for metot_tr, metot_py in metotlar.items():
                tablo.setdefault(f"{modul_py}.{metot_py}", f"{modul_tr}.{metot_tr}")
        en_cok = max((k.count(".") + 1 for k in tablo), default=2)
        _TERS_MODUL_TABLOSU = (tablo, en_cok)
    return _TERS_MODUL_TABLOSU


_MODUL_UYE_TERSLERI = {}


def _modul_uye_tersleri(modul_tr):
    """Bir TürKod modülünün (alt modül de olabilir: "bilimsel_hesaplama.
    istatistik") üyeleri: "python_modül.ad" -> Türkçe üye adı. Yalnızca o
    modülün kendi tablosundan kurulur; böylece ters çevrilen ad, aynı modülle
    ileri çevrildiğinde yine aynı Python adını verir."""
    tablo = _MODUL_UYE_TERSLERI.get(modul_tr)
    if tablo is None:
        on = modul_tr + "."
        tablo = {}
        for anahtar, py in MODUL_METOT_TABLO.items():
            if anahtar.startswith(on):
                tablo.setdefault(py, anahtar[len(on):])
        _MODUL_UYE_TERSLERI[modul_tr] = tablo
    return tablo


def _import_turkce_adi(modul_py):
    """"import X" satırının ters çeviride alacağı TürKod modül adı (bir modül
    tablosu yoksa None): "tensorflow" -> "tensorflow_kütüphanesi",
    "scipy.stats" -> "bilimsel_hesaplama.istatistik"."""
    if "." in modul_py:
        tr = _ters_modul_tablosu()[0].get(modul_py)
    else:
        tr = TERS_SOZLUK.get(modul_py, modul_py)
    if tr and (tr in MODUL_CEVIRILERI or ("." in tr and tr in MODUL_METOT_TABLO)):
        return tr
    return None


def _import_takma_adlarini_cevir(kod, yer_tutucu):
    """Ters yön: "import tensorflow as tf" ile gelen "tf.constant" ->
    "tf.sabit_değer". Takma adın kendisi olduğu gibi kalır."""
    if " as " not in kod:
        return kod
    takma = {}
    for m in _IMPORT_OLARAK.finditer(kod):
        for ad, ad_takma in _ice_aktarma_ogeleri(m.group(1)):
            modul_tr = _import_turkce_adi(ad) if ad_takma else None
            if modul_tr:
                takma[ad_takma] = (ad, modul_tr)
    if not takma:
        return kod
    en_cok = _MODUL_METOT_EN_COK_PARCA + 2

    def zinciri_cevir(m):
        parcalar = m.group(0).split(".")
        bilgi = takma.get(parcalar[0])
        if bilgi is None:
            return m.group(0)
        modul_py, modul_tr = bilgi
        uyeler = _modul_uye_tersleri(modul_tr)
        for j in range(min(len(parcalar), en_cok), 1, -1):
            tr = uyeler.get(modul_py + "." + ".".join(parcalar[1:j]))
            if tr is None:
                continue
            kalan = parcalar[j:]
            return yer_tutucu(f"{parcalar[0]}.{tr}") + "".join("." + p for p in kalan)
        return m.group(0)

    return re.sub(r"(?<![\w.])\w+(?:\.\w+)+", zinciri_cevir, kod)


def python_kodu_turkceye_cevir(python_kodu):
    # Satır sonu "[ \t]*$" desenleri '\r' önünde eşleşmiyor, CRLF'li kodda
    # "while x in y:" bile "döngü x içinde y:" (yani for) oluyordu.
    python_kodu = python_kodu.replace('\r\n', '\n').replace('\r', '\n')
    saklanan_metinler = []
    sayac = 0

    def metni_sakla(metin):
        nonlocal sayac
        uid = sayac
        sayac += 1
        saklanan_metinler.append((uid, metin))
        return f"\x00METIN_{uid}\x00"

    def sakla(match):
        # f-metinlerde düz metin korunur, {...} ifadeleri çevrilir (ileri
        # yöndeki _regex_tabanli_ceviri ile aynı): f"V({self.x})" ->
        # f"V({kendisi.x})". Eskiden f-metin bütünüyle korunduğundan
        # içindeki self, len(...) gibi adlar İngilizce kalıyordu.
        parca = match.group(0)
        if not _FSTRING_DESEN.fullmatch(parca):
            return metni_sakla(parca)
        parcalar = []
        son = 0
        for ifade in _FSTRING_IFADE_DESEN.finditer(parca):
            govde = ifade.group(0)
            if govde in ("{{", "}}"):
                # Kaçış süslü parantezi düz metindir; açıkta kalırsa
                # parantez derinliği hesabını bozar.
                continue
            if parca[son:ifade.start()]:
                parcalar.append(metni_sakla(parca[son:ifade.start()]))
            parcalar.append(
                re.sub(METIN_VE_YORUM_DESENI, lambda m: metni_sakla(m.group(0)), govde))
            son = ifade.end()
        if parca[son:]:
            parcalar.append(metni_sakla(parca[son:]))
        return "".join(parcalar)

    gecici_kod = re.sub(METIN_VE_YORUM_DESENI, sakla, python_kodu)

    # pencolor("blue") -> kalem_rengi("mavi"), shape("turtle") ->
    # şekil("kaplumbağa"), bg="red" -> arkaplan_rengi="kırmızı" ... Eskiden
    # metin içleri hiç çevrilmediğinden TürKod'da İngilizce değerler kalıyordu.
    metin_sozlugu = dict(saklanan_metinler)
    ters_degerleri_cevir(gecici_kod, metin_sozlugu)
    saklanan_metinler = list(metin_sozlugu.items())

    # Python adları Türkçe harf içerebilir (TürKod'dan çevrilmiş kodda sık):
    # eskiden ASCII'ye sınırlıydı, "for sayı in range(3):" kalıbı tutmuyor ve
    # "için sayı içinde aralık(3):" üretiliyordu ("için i aralık(3):" doğru).
    PY_ID = TR_ID
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
        for m in re.finditer(rf'^[ \t]*({PY_ID})\s*=(?!=)', gecici_kod, re.MULTILINE)
        if _derinlikler[m.start()] == 0
    )
    # Tip ipuçlu tanım (veri sınıfı alanları): "labels: list = ..."
    tanimlar.update(
        m.group(1)
        for m in re.finditer(rf'^[ \t]*({PY_ID})[ \t]*:(?!=)[ \t]*[^\s#][^\n]*$',
                             gecici_kod, re.MULTILINE)
        if _derinlikler[m.start()] == 0 and not keyword.iskeyword(m.group(1))
    )
    # Çoklu atama: a, b = ...
    for m in re.finditer(
            rf'^[ \t]*\(?((?:\*?{PY_ID}\s*,\s*)+\*?{PY_ID})\s*,?\s*\)?\s*=(?!=)',
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
            rf'^[ \t]*(?:global|nonlocal)\s+({PY_ID}(?:\s*,\s*{PY_ID})*)',
            gecici_kod, re.MULTILINE):
        tanimlar.update(p.strip() for p in grup.split(','))
    for param_blok in re.findall(rf'\bdef\s+{PY_ID}\s*\(([^)]*)\)', gecici_kod):
        for p in param_blok.split(','):
            # "*args", "**kw", "x: int = 3" biçimleri de desteklenir.
            p = p.strip().split('=')[0].split(':')[0].strip().lstrip('*').strip()
            # self/cls her zaman kendisi/kendi_sınıfı olur (kullanıcı adı sayılmaz).
            if p and p not in ('self', 'cls'):
                tanimlar.add(p)
    # Python ayrılmış kelimeleri ve yerleşikleri asla "kullanıcı tanımı"
    # sayılmaz (ör. "def print" gibi gölgeleme yine çevrilir).
    # Özel (dunder) metotlar da öyle: "def __init__" -> "fonksiyon
    # __başlat__"; eskiden tanım sayıldıkları için hiç Türkçeleşmiyorlardı.
    tanimlar = {t for t in tanimlar if not keyword.iskeyword(t)
                and not (t.startswith("__") and t.endswith("__"))}

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
    # Argümanda bir seviye iç içe parantez desteklenir: eskiden ilk ')' ile
    # bittiğinden "range(len(a))" kalıbı tutmuyor ve "için i içinde
    # aralık(uzunluk(a)):" üretiliyordu.
    gecici_kod = re.sub(
        rf"\bfor\s+({PY_ID}(?:\s*,\s*{PY_ID})*)\s+in\s+range\s*\(((?:[^()\n]|\([^()\n]*\))*)\)\s*:",
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
    ters_modul_tablo, ters_modul_en_cok_parca = _ters_modul_tablosu()

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

    # "from numpy import array" -> "den numpy içe_aktar dizi" ve koddaki
    # çıplak "array" -> "dizi" (noktalı modül adları aşağıda çevrilir).
    gecici_kod = _from_import_adlarini_cevir(
        gecici_kod, tanimlar, ters_modul_tablo, _noktali_koru)
    # "import tensorflow as tf" -> "tf.constant" -> "tf.sabit_değer".
    gecici_kod = _import_takma_adlarini_cevir(gecici_kod, _noktali_koru)

    def _modul_uyesi(k):
        # Modülün Türkçe adı bir kullanıcı adıyla çakışıyorsa (Python'da
        # "desen = re.compile(...)") modül adı aşağıda Python adıyla kalır;
        # üye de "re.BÜYÜK_KÜÇÜK_YOKSAY" olmalı. Eskiden
        # "desen.BÜYÜK_KÜÇÜK_YOKSAY" oluyor, desen değişkenine gidiyordu.
        tr = ters_modul_tablo[k]
        if tr.split(".")[0] in tanimlar:
            tr = k.split(".")[0] + tr[len(tr.split(".")[0]):]
        return _noktali_koru(tr)

    if ters_modul_tablo:
        gecici_kod = _noktali_tablo_uygula(
            gecici_kod, ters_modul_tablo, _modul_uyesi, ters_modul_en_cok_parca,
        )

    # Ursina ve PyMuPDF nesne özelliklerinin ters çevirisi: mouse.x -> fare.x,
    # color.red -> renk.kırmızı, sayfa.draw_rect -> sayfa.dörtgen_çiz, vb.
    # NOT: PYMUPDF_NESNE_TABLO burada eklenmezse python_kodu_turkceye_cevir()
    # (.py -> TürKod) bu metotları hiç Türkçeleştirmez; .turkod -> .py yönü
    # (_regex_tabanli_ceviri) ayrı bir koddur ve ondan etkilenmez.
    # İlk yazılan kazanır: kanonik adlar (pencere.başlık) takma adlardan
    # (ursina_penceresi.başlık) ve ASCII yazımlardan (pencere.baslik) önce gelir.
    ters_nesne_tablo = {}
    for tr, py in {**URSINA_NESNE_TABLO, **PYMUPDF_NESNE_TABLO}.items():
        ters_nesne_tablo.setdefault(py, tr)
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
    # dict(width=1) anahtarları çevrilmez: ileri yön sözlük(...) anahtarlarına
    # dokunmadığından "sözlük(genişlik=1)" geri "dict(genişlik=1)" olur,
    # anahtar değişirdi.
    gecici_kod = _sozluk_anahtarlarini_sakla(gecici_kod, isim_sak)

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

    # "den numpy içe_aktar dizi" -> "from numpy import array" ve koddaki
    # çıplak "dizi" -> "array". Sonuçlar düz sözlükten korunur.
    ice_aktarilanlar = {}

    def ice_aktarilani_koru(py_ad):
        yer = f"\x00ICE_{len(ice_aktarilanlar)}\x00"
        ice_aktarilanlar[yer] = py_ad
        return yer

    gecici_kod = _ice_aktarilan_adlari_cevir(gecici_kod, tanimlar, ice_aktarilani_koru)
    # "içe_aktar numpy olarak np" -> "np.eleman_en_küçük" -> "np.minimum".
    gecici_kod = _takma_adli_uyeleri_cevir(gecici_kod, ice_aktarilani_koru)

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
    gecici_kod = _sozluk_anahtarlarini_sakla(gecici_kod, isim_sak)

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
    # ASCII yazım da ("icin i aralik(3):") kabul edilir; eskiden yine
    # "for i range(3)" (sözdizimi hatası) oluyordu.
    python_kodu = re.sub(
        rf"\b(?:için|icin)\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+(?=aral[ıi]k\s*\()",
        r"for \1 in ",
        gecici_kod
    )
    python_kodu = re.sub(
        rf"\b(?:döngü|dongu)\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+(?=aral[ıi]k\s*\()",
        r"for \1 in ",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\b(?:döngü|dongu)\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+(?:içinde|icinde)\s+(.*?):",
        r"for \1 in \2:",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\biçin\s+({TR_ID}(?:\s*,\s*{TR_ID})*)\s+içinde\s+(.*?):",
        r"for \1 in \2:",
        python_kodu
    )
    # Önek '[' içermez ve boşlukla bitmez: eskiden önek ile (\s+) aynı
    # boşlukları paylaşabildiğinden kapanmamış çok sayıda '[' içeren
    # dosyalarda geri izleme patlıyor, çeviri/sözdizimi kontrolü onlarca
    # saniye donuyordu. Çok satırlı üreteçler yine eşleşir.
    python_kodu = re.sub(
        rf"\[([^\[\]]*?[^\s\[\]])(\s+)için(\s+)({TR_ID})(\s+)içinde(\s+)(.*?)(\s+)eğer(\s+)(.*?)\]",
        r"[\1\2for\3\4\5in\6\7\8if\9\10]",
        python_kodu
    )
    python_kodu = re.sub(
        rf"\[([^\[\]]*?[^\s\[\]])(\s+)için(\s+)({TR_ID})(\s+)içinde(\s+)([^]]+?)\]",
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
    # "uzunluk(a) 3 ise:" / "liste[0] x ise:" -> "... == 3:" (sol taraf çağrı
    # ya da indeks olduğunda yukarıdaki ad kuralı eşleşmez).
    python_kodu = re.sub(
        rf"([)\]])[ \t]+(?!(?:ve|veya|değil|degil|içinde|icinde)\b)({TR_ID}|\d+(?:\.\d+)?|\x00METIN_\d+\x00|\x00TKOR_\d+\x00)[ \t]+ise[ \t]*:",
        r"\1 == \2:",
        python_kodu,
    )
    # Koşulu bitiren "ise:" yalnızca koşulun sonunu belirtir: "eğer x > 3 ise:"
    # -> "if x > 3:", "eğer liste[0] ise:" -> "if liste[0]:", "hazır ise:" ->
    # "hazır:". Eskiden aşağıdaki ara ek kuralı bunları "x > 3 ==:" gibi
    # geçersiz koda çeviriyordu; "A ise:" de "A == True:" olup boş olmayan
    # liste/metin gibi doğru sayılan değerlerde koşulu yanlış yapıyordu.
    # (?<![ \t]): uzun boşluk dizilerinde her konumdan yeniden denenip
    # karesel süre almasın (20 bin boşlukta 1.4 sn sürüyordu).
    python_kodu = re.sub(r"(?<![ \t])[ \t]+ise[ \t]*:", ":", python_kodu)
    # infix: "A ise B" -> "A == B" (yalnızca iki yanında boşluk varken; "obj.ise"
    # gibi nitelik adları dokunulmaz).
    python_kodu = re.sub(r"(?<=[^\s.])(\s+)ise(?=\s)", r"\1==", python_kodu)

    # "içe_aktar bilimsel_hesaplama.istatistik" -> "import scipy.stats": alt
    # modül yolu modül tablosunda varsa bütün olarak çevrilir. Aksi halde önce
    # üst modül (scipy) çevrilir, ".istatistik" düz sözlüğe düşüp
    # "scipy.statistics" olurdu.
    python_kodu = re.sub(
        rf"\biçe_aktar([ \t]+)({TR_MODUL_ID})\b",
        lambda m: (f"import{m.group(1)}{MODUL_METOT_TABLO[m.group(2)]}"
                   if "." in m.group(2) and m.group(2) in MODUL_METOT_TABLO
                   else m.group(0)),
        python_kodu
    )
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

    # Modül tablosunun ürettiği Python adları yer tutucuyla korunur: aksi
    # halde düz sözlük bunları Türkçe kelime sanıp yeniden çevirir
    # ("numpy.minimum" -> "numpy.min", "minimum" düz sözlükte min'dir).
    modul_sonuclari = {}

    def modul_sonucunu_koru(anahtar):
        yer = f"\x00NOKTALI_{len(modul_sonuclari)}\x00"
        modul_sonuclari[yer] = MODUL_METOT_TABLO[anahtar]
        return yer

    python_kodu = _noktali_tablo_uygula(
        python_kodu, MODUL_METOT_TABLO, modul_sonucunu_koru,
        _MODUL_METOT_EN_COK_PARCA,
    )

    sozluk_regex, sozluk_tablo = _sozluk_hazirla()

    # Pencere başlığı: tkinter'de pencere.title(...), kaplumbağada
    # ekran.title(...). Düz sözlükte "başlık" header'dır (pandas başlık=,
    # streamlit ...); eskiden "pencere.başlık('Oyun')" -> ".header(...)"
    # olup AttributeError veriyordu. Yalnızca tkinter/turtle içe aktarılmış
    # dosyada ve nokta sonrası çağrıda title seçilir.
    pencere_basligi = re.search(
        r"^[ \t]*(?:import|from)[ \t]+(?:tkinter|turtle)\b", python_kodu, re.M)

    def sozluk_karsiligi(m):
        if (pencere_basligi and m.group(0) in ("başlık", "baslik")
                and m.start() and m.string[m.start() - 1] == "."
                and re.match(r"[ \t]*\(", m.string[m.end():m.end() + 20])):
            return "title"
        py = sozluk_tablo.get(m.group(0), m.group(0))
        # Nokta sonrası öznitelik adıdır; anahtar kelime olamaz. Eskiden
        # "zaman.bekle(0)" -> "time.await(0)", "kendisi.geç = 1" ->
        # "self.pass = 1" (sözdizimi hatası) oluyordu; ad olduğu gibi kalır.
        if (m.start() and m.string[m.start() - 1] == "."
                and keyword.iskeyword(py)):
            return m.group(0)
        return py

    python_kodu = sozluk_regex.sub(sozluk_karsiligi, python_kodu)

    python_kodu = _yer_tutuculari_geri_koy(python_kodu, modul_sonuclari)
    python_kodu = _yer_tutuculari_geri_koy(python_kodu, ice_aktarilanlar)

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


_CEVIRI_ONBELLEGI = {}
_CEVIRI_ONBELLEK_SINIRI = 16
_ceviri_kilidi = threading.Lock()


def turkce_kodu_donustur(turkce_kod: str, yerel_moduller=None) -> str:
    """Token tabanlı koruma ile güçlendirilmiş TürKod -> Python çevirici.

    yerel_moduller: {modül_adı: {tanımlı adlar}} — aynı klasördeki başka
    .trpy dosyaları. "yardimci.uzunluk(3)" gibi erişimlerde nitelik adı o
    dosyada tanımlıysa sözlükle çevrilmez (yoksa "yardimci.len(3)" olurdu).

    Sonuçlar küçük bir önbellekte tutulur: Çalıştır / Debug önce doğrular
    (dogrula da çevirir), sonra aynı kodu yeniden çevirirdi; büyük dosyada
    bu, program başlamadan önce yarım saniyelik gereksiz bekleme demekti."""
    anahtar = (turkce_kod, tuple(sorted(
        (ad, tuple(sorted(t))) for ad, t in yerel_moduller.items()))
        if yerel_moduller else None)
    with _ceviri_kilidi:
        sonuc = _CEVIRI_ONBELLEGI.get(anahtar)
    if sonuc is not None:
        return sonuc
    sonuc = _turkce_kodu_donustur(turkce_kod, yerel_moduller)
    with _ceviri_kilidi:
        if len(_CEVIRI_ONBELLEGI) >= _CEVIRI_ONBELLEK_SINIRI:
            _CEVIRI_ONBELLEGI.pop(next(iter(_CEVIRI_ONBELLEGI)))
        _CEVIRI_ONBELLEGI[anahtar] = sonuc
    return sonuc


def _ascii_yazimlari_tanima_bagla(kod, tanimlar):
    """TürKod'da Türkçe harfsiz yazım Türkçesiyle aynıdır (yazdir = yazdır).
    Kullanıcının tanımladığı "sayı" için yazılan "sayi" de o kutu olmalı;
    eskiden "sayi" sözlükteki karşılığına (number) çevriliyor, program
    "'sayı' tanımlı değil" diye hata veriyordu. Türkçe harfsiz yazımı ayrıca
    tanımlanmış adlara ve nokta sonrasındaki özniteliklere dokunulmaz.
    Metinler ve yorumlar bu adımdan önce yer tutucuyla saklanmıştır."""
    eslesme = {}
    for ad in tanimlar:
        katlanmis = _ascii_katlanmis(ad)
        if katlanmis != ad and katlanmis not in tanimlar:
            eslesme.setdefault(katlanmis, ad)
    if not eslesme:
        return kod
    desen = re.compile(
        rf"(?<![{TR_HARF}0-9.])(" + "|".join(map(re.escape, sorted(eslesme, key=len, reverse=True)))
        + rf")(?![{TR_HARF}0-9])")
    return desen.sub(lambda m: eslesme[m.group(1)], kod)


def _turkce_kodu_donustur(turkce_kod, yerel_moduller=None):
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

    if yerel_moduller:
        if tanimlar is None:
            tanimlar = kullanici_tanimlari(_tanim_icin_maskele(turkce_kod))
        gecici_kod, tanimlar = _yerel_modul_adlarini_koru(
            gecici_kod, tanimlar, yerel_moduller, saklanan_parcalar)

    if tanimlar:
        gecici_kod = _ascii_yazimlari_tanima_bagla(gecici_kod, tanimlar)

    python_kodu = _regex_tabanli_ceviri(gecici_kod, tanimlar)

    return _yer_tutuculari_geri_koy(
        python_kodu,
        {f"\x00TKOR_{uid}\x00": parca for uid, parca in saklanan_parcalar},
    )


# ---------------------------------------------------------------------------
# Yerel .trpy modülleri (aynı klasördeki dosyalar arası içe aktarma)
# ---------------------------------------------------------------------------
TRPY_UZANTI = ".trpy"
# Satır sonundaki yorum ("içe_aktar yardimci  # yorum") eşleşmeyi bozmaz.
_ICE_AKTAR_DESEN = re.compile(
    rf"^[ \t]*içe_aktar[ \t]+({TR_MODUL_ID}(?:[ \t]+olarak[ \t]+{TR_ID})?"
    rf"(?:[ \t]*,[ \t]*{TR_MODUL_ID}(?:[ \t]+olarak[ \t]+{TR_ID})?)*)[ \t]*(?:#[^\n]*)?$",
    re.MULTILINE,
)
# Göreli içe aktarma da ("den .modul içe_aktar ad", "den . içe_aktar modul").
_DEN_DESEN = re.compile(
    rf"^[ \t]*den[ \t]+(\.*(?:{TR_MODUL_ID})?)[ \t]+içe_aktar[ \t]+\(?([^)\n#]*)",
    re.MULTILINE,
)
_DEN_DESEN_2 = re.compile(
    rf"^[ \t]*içe_aktar[ \t]+([^\n#]+?)[ \t]+den[ \t]+(\.*(?:{TR_MODUL_ID})?)[ \t]*(?:#[^\n]*)?$",
    re.MULTILINE,
)


def _ad_listesi(metin):
    """"a, b olarak c" -> [("a", None), ("b", "c")]."""
    sonuc = []
    for parca in metin.split(","):
        ps = parca.split()
        if ps:
            sonuc.append((ps[0], ps[2] if len(ps) == 3 and ps[1] == "olarak" else None))
    return sonuc


def _ice_aktarilan_moduller(kod):
    """Koddaki içe aktarmalardan [(modül, takma_ad | None, [(ad, takma)] | None)]."""
    sonuc = []
    for m in _ICE_AKTAR_DESEN.finditer(kod):
        for ad, takma in _ad_listesi(m.group(1)):
            sonuc.append((ad, takma, None))
    for m in _DEN_DESEN.finditer(kod):
        if m.group(1):
            sonuc.append((m.group(1), None, _ad_listesi(m.group(2))))
    for m in _DEN_DESEN_2.finditer(kod):
        if m.group(2):
            sonuc.append((m.group(2), None, _ad_listesi(m.group(1))))
    return sonuc


def _alt_modul_adi(modul, ad):
    """"den paketim içe_aktar modul1" -> "paketim.modul1"; "den . içe_aktar m" -> ".m"."""
    return modul + ad if modul.endswith(".") else f"{modul}.{ad}"


def _yerel_modul_adlarini_koru(kod, tanimlar, yerel_moduller, saklanan):
    tanimlar = set(tanimlar or ())

    def uyeleri_koru(kod, on_ek, mod_tanimlari):
        if not mod_tanimlari:
            return kod
        desen = re.compile(
            rf"(?<![{TR_HARF}0-9.]){re.escape(on_ek)}[ \t]*\.[ \t]*({TR_ID})")

        def koru(m):
            ad = m.group(1)
            if ad not in mod_tanimlari:
                return m.group(0)
            uid = len(saklanan)
            saklanan.append((uid, ad))
            return m.group(0)[:m.start(1) - m.start(0)] + f"\x00TKOR_{uid}\x00"

        return desen.sub(koru, kod)

    for modul, takma, adlar in _ice_aktarilan_moduller(kod):
        # Yerel modül yolunun parçaları ("araclar.sayi") sözlükle çevrilmez;
        # eskiden "sayi" -> "number" olup modül bulunamıyordu.
        if any(a == modul or a.startswith(modul + ".") or modul.startswith(a + ".")
               for a in yerel_moduller):
            tanimlar.update(p for p in modul.split(".") if p)
        if adlar is not None:
            # "den paketim içe_aktar modul1": ad bir alt modül (paketim/modul1.trpy).
            for ad, ad_takma in adlar:
                alt = _alt_modul_adi(modul, ad)
                if alt in yerel_moduller:
                    tanimlar.add(ad_takma or ad)
                    kod = uyeleri_koru(kod, ad_takma or ad, yerel_moduller[alt])
            if modul not in yerel_moduller:
                continue
            mod_tanimlari = yerel_moduller[modul]
            # "den yardimci içe_aktar uzunluk": ad bu dosyada da kullanıcı adıdır.
            if any(ad == "*" for ad, _t in adlar):
                tanimlar.update(mod_tanimlari)
            else:
                tanimlar.update(ad for ad, _t in adlar if ad in mod_tanimlari)
            continue
        if modul not in yerel_moduller:
            continue
        on_ek = takma or modul
        tanimlar.update(on_ek.split("."))
        kod = uyeleri_koru(kod, on_ek, yerel_moduller[modul])
    return kod, tanimlar


def _mutlak_modul_adi(ad, paket):
    """Göreli adı paket içinden çözer: (".modul1", "paketim") -> "paketim.modul1"."""
    if not ad.startswith("."):
        return ad
    seviye = len(ad) - len(ad.lstrip("."))
    taban = paket.split(".") if paket else []
    if seviye > 1:
        taban = taban[:max(0, len(taban) - (seviye - 1))]
    kalan = ad.lstrip(".")
    return ".".join(taban + ([kalan] if kalan else []))


def _trpy_oku(yol):
    with open(yol, "rb") as f:
        ham = f.read()
    for kodlama in ("utf-8-sig", "cp1254"):
        try:
            return ham.decode(kodlama)
        except UnicodeDecodeError:
            continue
    return ham.decode("utf-8", errors="replace")


def yerel_modulleri_hazirla(kod, kaynak_dizin, hedef_dizin):
    """Kodun (dolaylı olarak da) içe aktardığı, kaynak_dizin'deki .trpy
    dosyalarını Python'a çevirip hedef_dizin'e <ad>.py olarak yazar.
    Alt klasörlerdeki paketler de desteklenir: "içe_aktar paketim.modul1"
    -> paketim/modul1.trpy (+ varsa paketim/__init__.trpy); paket içindeki
    göreli içe aktarma ("den .modul1 içe_aktar bir") çözülür.

    Döndürür: (yerel_moduller, yazilan_dosyalar, hatalar)
      yerel_moduller: {ad: tanımlar} — ana dosyanın çevirisine verilir.
    """
    import os
    import shutil

    yerel = {}
    kaynaklar = {}   # ad -> (metin, paket_mi, yol)
    hatalar = []
    if not kaynak_dizin or not os.path.isdir(kaynak_dizin):
        return yerel, [], hatalar
    # CRLF'li (Windows) dosyada satır sonu desenleri '\r' önünde eşleşmiyor,
    # "içe_aktar yardimci" hiç görülmüyor ve modül çevrilmiyordu.
    kod = kod.replace("\r\n", "\n").replace("\r", "\n")

    def dosyasi(ad):
        yol = os.path.join(kaynak_dizin, *ad.split("."))
        if os.path.isfile(yol + TRPY_UZANTI):
            return yol + TRPY_UZANTI, False
        if os.path.isfile(os.path.join(yol, "__init__" + TRPY_UZANTI)):
            return os.path.join(yol, "__init__" + TRPY_UZANTI), True
        return None, False

    def paketi(ad):
        if ad not in kaynaklar:
            return ""
        return ad if kaynaklar[ad][1] else ad.rpartition(".")[0]

    def aday_adlar(metin, paket):
        for modul, _t, adlar in _ice_aktarilan_moduller(metin):
            tam = _mutlak_modul_adi(modul, paket)
            if not tam:
                continue
            parcalar = tam.split(".")
            # "içe_aktar a.b.c" a ve a.b paketlerini de yükler.
            for i in range(1, len(parcalar) + 1):
                yield ".".join(parcalar[:i])
            for ad, _ta in adlar or ():
                if ad != "*":
                    yield f"{tam}.{ad}"

    kuyruk = list(aday_adlar(kod, ""))
    while kuyruk:
        ad = kuyruk.pop()
        if ad in kaynaklar:
            continue
        yol, paket_mi = dosyasi(ad)
        if yol is None:
            continue
        try:
            metin = _trpy_oku(yol).replace("\r\n", "\n").replace("\r", "\n")
        except OSError as e:
            hatalar.append(f"{os.path.relpath(yol, kaynak_dizin)} okunamadı: {e}")
            continue
        kaynaklar[ad] = (metin, paket_mi, yol)
        yerel[ad] = kullanici_tanimlari(_tanim_icin_maskele(metin))
        kuyruk.extend(aday_adlar(metin, paketi(ad)))

    def dosyaya_ozel(metin, paket):
        # Göreli adlar ("." / ".modul1") bu dosya için mutlak karşılıklarına bağlanır.
        ek = {}
        for modul, _t, adlar in _ice_aktarilan_moduller(metin):
            if not modul.startswith("."):
                continue
            tam = _mutlak_modul_adi(modul, paket)
            if tam in yerel:
                ek[modul] = yerel[tam]
            for ad, _ta in adlar or ():
                if f"{tam}.{ad}" in yerel:
                    ek[_alt_modul_adi(modul, ad)] = yerel[f"{tam}.{ad}"]
        return {**yerel, **ek} if ek else yerel

    yazilan = []
    for ad, (metin, paket_mi, yol) in kaynaklar.items():
        try:
            py = turkce_kodu_donustur(metin, yerel_moduller=dosyaya_ozel(metin, paketi(ad)))
            parcalar = ad.split(".")
            hedef = (os.path.join(hedef_dizin, *parcalar, "__init__.py") if paket_mi
                     else os.path.join(hedef_dizin, *parcalar) + ".py")
            os.makedirs(os.path.dirname(hedef), exist_ok=True)
            with open(hedef, "w", encoding="utf-8") as f:
                f.write(py)
            yazilan.append(hedef)
            # Paketin Python ile yazılmış __init__.py'si de taşınır; yoksa
            # geçici klasördeki (init'siz) klasör onu gölgelemez ama paketin
            # kendisi de bulunmaz.
            for i in range(1, len(parcalar)):
                ust = parcalar[:i]
                py_init = os.path.join(kaynak_dizin, *ust, "__init__.py")
                hedef_init = os.path.join(hedef_dizin, *ust, "__init__.py")
                if (".".join(ust) not in kaynaklar and os.path.isfile(py_init)
                        and not os.path.exists(hedef_init)):
                    shutil.copyfile(py_init, hedef_init)
        except Exception as e:  # noqa: BLE001 - kullanıcıya gösterilir
            hatalar.append(f"{os.path.relpath(yol, kaynak_dizin)} çevrilemedi: {e}")
    return yerel, yazilan, hatalar
