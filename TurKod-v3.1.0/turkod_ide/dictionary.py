"""TurKod sozluk ve kelime altyapisi."""
import ast
import json
import os
import re
import sys
import keyword as _keyword

# 1. Yolları .paths modülünden al (FONKSİYON OLDUKLARI İÇİN PARANTEZ İLE ÇAĞIR)
try:
    from .paths import calisma_yolu, kaynak_yolu
    # Fonksiyonları çağırıp sonuçlarını değişkenlere ata
    _CALISMA_YOLU = calisma_yolu()
    _KAYNAK_YOLU = kaynak_yolu()
except ImportError:
    # Eğer paths modülü yoksa veya import edilemiyorsa varsayılanları kullan
    _CALISMA_YOLU = os.path.expanduser("~")
    _KAYNAK_YOLU = os.path.dirname(os.path.abspath(__file__))

# 2. Dosya yollarını tanımla (Düzeltilmiş değişken isimlerini kullan)
if getattr(sys, 'frozen', False):
    _base_path = sys._MEIPASS
else:
    _base_path = os.path.dirname(os.path.abspath(__file__))

SOZLUK_TXT_YOLU = os.path.join(_base_path, "TurKod_Sozluk.txt")

# Alternatif yol kontrolü (PyInstaller onedir modunda turkod_ide/ altına paketlenir)
if not os.path.exists(SOZLUK_TXT_YOLU):
    SOZLUK_TXT_YOLU = os.path.join(_KAYNAK_YOLU, "TurKod_Sozluk.txt")
if not os.path.exists(SOZLUK_TXT_YOLU):
    # PyInstaller onedir: exe_dir/turkod_ide/TurKod_Sozluk.txt
    _exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else _base_path
    SOZLUK_TXT_YOLU = os.path.join(_exe_dir, "turkod_ide", "TurKod_Sozluk.txt")
if not os.path.exists(SOZLUK_TXT_YOLU):
    # Son çare: MEIPASS/turkod_ide/
    if getattr(sys, 'frozen', False):
        SOZLUK_TXT_YOLU = os.path.join(sys._MEIPASS, "turkod_ide", "TurKod_Sozluk.txt")

# Cache dosyası (json) - Kullanıcı klasörü
# Önbellek biçimi değişti ({imza, kelimeler}); yeni dosya adı, aynı kullanıcı
# klasörünü paylaşan eski bir TürKod sürümünün (liste bekleyen) yeni dosyayı
# okuyup otomatik tamamlamayı bozmasını önler.
CACHE_JSON_YOLU = os.path.join(_CALISMA_YOLU, ".turkod_kelimeler_v2.json")

# 3. Cache Geçersizleştirme Mantığı
def _cache_temizle():
    """Sözlük txt dosyası cache'den yeniyse eski cache'i siler."""
    try:
        if os.path.exists(SOZLUK_TXT_YOLU) and os.path.exists(CACHE_JSON_YOLU):
            if os.path.getmtime(SOZLUK_TXT_YOLU) > os.path.getmtime(CACHE_JSON_YOLU):
                os.remove(CACHE_JSON_YOLU)
    except OSError:
        pass

# Uygulama başlarken kontrol et
_cache_temizle()


def _ascii_katlanmis(yazi):
    """Türkçe karakterleri ASCII eşdeğerlerine çevirir."""
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


def _sozluk_ascii_takma_adlari(sozluk):
    """Türkçe anahtarların ASCII takma adlarını döner; kanonik yazım korunur."""
    eklenen = {}
    uyari = []
    for anahtar in list(sozluk.keys()):
        if not isinstance(anahtar, str):
            continue
        if not any(h in anahtar for h in "çğıöşüÇĞİÖŞÜ"):
            continue
        takma = _ascii_katlanmis(anahtar)
        if takma == anahtar:
            continue
        if takma in sozluk:
            mevcut = sozluk[takma]
            # Aynı ASCII karşılığına sahip iki farklı kanonik anahtar
            # doğrudan "takma ad" değil, ayrı amaçlı kelimelerdir.
            # Örn. devre_dışı (disabled) ve devre_disi (deactivate).
            # Bu durumda otomatik alias eklemeyi atlayıp sadece gerçek
            # çakışma durumlarında uyarı veririz.
            if mevcut != sozluk[anahtar]:
                continue
            uyari.append(f"{anahtar} -> {takma}")
            continue
        if takma in eklenen:
            mevcut = eklenen[takma]
            if mevcut != sozluk[anahtar]:
                continue
            uyari.append(f"{anahtar} -> {takma}")
            continue
        eklenen[takma] = sozluk[anahtar]
    return eklenen, uyari


def _sozluk_yukle(dosya_adi="TurKod_Sozluk.txt"):
    """
    TürKod sözlüğünü yükle.
    .exe'de sys._MEIPASS'ten, .py'de script dizininden okur.
    """
    try:
        # 1. PyInstaller .exe'de sys._MEIPASS kullan
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Normal Python çalışması - scriptin bulunduğu dizin
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        yol = os.path.join(base_path, dosya_adi)
        
        # 2. Yoksa çalışma dizinine bak
        if not os.path.exists(yol):
            yol = os.path.join(os.getcwd(), dosya_adi)
            
        # 3. Yoksa kaynak yoluna bak
        if not os.path.exists(yol):
            yol = os.path.join(_KAYNAK_YOLU, dosya_adi)
        
        # 4. PyInstaller onedir: turkod_ide/ alt dizini
        if not os.path.exists(yol):
            _exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else base_path
            yol = os.path.join(_exe_dir, "turkod_ide", dosya_adi)
        
        # 5. MEIPASS/turkod_ide/ (onefile extract)
        if not os.path.exists(yol) and getattr(sys, 'frozen', False):
            yol = os.path.join(sys._MEIPASS, "turkod_ide", dosya_adi)
        
        # 6. Hala yoksa dosya adıyla dene (mevcut dizin)
        if not os.path.exists(yol):
            yol = dosya_adi
        
        if not os.path.exists(yol):
            print(f"[TurKod] Sözlük dosyası bulunamadı: {dosya_adi}")
            return {}
        
        with open(yol, "r", encoding="utf-8") as f:
            icerik = f.read()
        
        bas = icerik.find("{")
        son = icerik.rfind("}") + 1
        if bas != -1 and son > bas:
            return ast.literal_eval(icerik[bas:son])
            
    except Exception as e:
        print(f"[TurKod] Sözlük yüklenemedi: {e}")
    
    return {}

SOZLUK = _sozluk_yukle()
SOZLUK_TAKMA_ADLAR = set()
SOZLUK_TAKMA_ADLARI_UYARI = []

if SOZLUK:
    _eklenen_takma, _uyari_listesi = _sozluk_ascii_takma_adlari(SOZLUK)
    SOZLUK.update(_eklenen_takma)
    SOZLUK_TAKMA_ADLAR = set(_eklenen_takma.keys())
    SOZLUK_TAKMA_ADLARI_UYARI = _uyari_listesi
    if _uyari_listesi:
        print(f"[TurKod] ASCII takma ad çakışması: {len(_uyari_listesi)} adet. Örnek: {_uyari_listesi[:3]}")

if not SOZLUK:
    print("[TurKod] UYARI: Sözlük dosyası bulunamadı veya boş!")

TERS_SOZLUK_ONCELIK = {
    # Genel dosya/metin metotları: eskiden "dosya.write" -> "dosya.zip_yaz",
    # "','.join" -> "','.katılım_bekle" gibi yanıltıcı karşılıklara gidiyordu.
    "write": "yaz",
    "read": "oku",
    "join": "birleştir",
    "min": "minimum",
    "max": "maksimum",
    "abs": "mutlak",
    "round": "yuvarla",
    "open": "açık",
    "font": "yazı_tipi",
    "append": "sona_ekle",
    "math": "matematik",
    "render": "yazı_oluştur",
    "remove": "kaldır",
    "get": "getir",
    "format": "biçimle",
    "forward": "ileri",
    "Button": "düğme",
    "Text": "metin_alanı",
    "input": "girdi_al",
    "set": "küme",
    "compile": "derle",
    "quit": "oyun_kapat",
    "wait": "bekle_eşzamansız",
    "Slider": "ursina_kaydırıcı",
    "max_length": "maks_uzunluk",
    "stop": "bitiş",
    "step": "adım",
    "save": "kaydet",
    "autoplay": "otomatik_çal",
    "on_click": "tıklanınca",
    "delay": "gecikme",
    "event_handler": "olay_işleyicisi",
    "origin": "köken",
    # Aşağıdakiler birden fazla Türkçe anahtara bağlı hedeflerdir; ters
    # çeviride (Python -> TürKod) hangisinin seçileceğini netleştirir.
    # Bu, ambiguity'i sadece TEK hedef için giderir; SOZLUK'taki kaynak
    # çakışmanın kendisini ortadan kaldırmaz (bkz. not aşağıda).
    "title": "başlık_yap",
    "update": "güncelle",
    "text": "xml_metin",
    "icon": "simge",
    "color": "renk",
    "size": "boyut",
    "scene": "sahne",
    "invoke": "çağır",
    "grid": "ızgarala",
    "run": "çalıştır_oyun",
    "delete": "öğe_sil",
    "row": "satır",
    "geometry": "geometri",
    "fg": "ön_renk_kısa",
}


def _ters_sozluk_olustur():
    ters_sozluk = {}
    for desen, python_karsiligi in SOZLUK.items():
        if desen in SOZLUK_TAKMA_ADLAR:
            continue
        tr_kelime = desen.replace(r'\b', '').strip('"').strip("'")
        py_kelime = python_karsiligi.strip('"').strip("'")
        # Noktalı hedefler (örn. "mouse.x", "tf.constant") burada elenir.
        # Bunlar bağlamsız tek kelimeye indirgenirse yanlış/parçalı ters
        # çeviri üretir (örn. "mouse.x" -> "fare_x" değil "mouse.fare_x"
        # gibi bir şeye karışabilir); noktalı API'ler modül/nesne tablolarına
        # aittir, converter.py bunları ayrıca ters çevirir.
        if '.' in py_kelime:
            continue
        if tr_kelime and py_kelime and ' ' not in tr_kelime and len(py_kelime) > 1:
            ters_sozluk.setdefault(py_kelime, tr_kelime)
    # Öncelikli karşılıkları zorla
    for py, tr in TERS_SOZLUK_ONCELIK.items():
        if py in ters_sozluk:
            ters_sozluk[py] = tr
    return ters_sozluk

TERS_SOZLUK = _ters_sozluk_olustur()

def _sozluk_kelime(desen):
    return desen.replace(r"\b", "").strip().strip('"').strip("'")

_PY_KEYWORDS = set(_keyword.kwlist) | {"True", "False", "None"}

_BLOCK_VALUES = {
    "def", "class", "while", "if", "elif", "else",
    "try", "except", "finally"
}

_keyword_words = set()
_builtin_words = set()
_block_words = set()

for _desen, _hedef in SOZLUK.items():
    _kelime = _sozluk_kelime(_desen)
    _hedef = _hedef.strip()

    if not _kelime or " " in _kelime or "." in _kelime:
        continue

    if _hedef in _PY_KEYWORDS:
        _keyword_words.add(_kelime)
    else:
        _builtin_words.add(_kelime)

    if _hedef in _BLOCK_VALUES:
        _block_words.add(_kelime)

_block_words.update([
    "fonksiyon", "sınıf", "döngü", "için", "eğer", "değilse_eğer", "değilse",
    "dene", "hata_yakala", "sonunda"
])

def _regex_compile(words):
    words = sorted(words, key=len, reverse=True)
    if not words:
        return re.compile(r"(?!)")
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")

TURKOD_KEYWORD_RE = _regex_compile(_keyword_words)
TURKOD_BUILTIN_RE = _regex_compile(_builtin_words)

_block_words = sorted(_block_words, key=len, reverse=True)

TURKOD_BLOK_RE = re.compile(
    r"^(?:" + "|".join(re.escape(w) for w in _block_words) + r")\b",
    re.MULTILINE
)

def _sozlukten_python_kelime(py, fallback):
    for _desen, _hedef in SOZLUK.items():
        if _hedef.strip() == py:
            return _sozluk_kelime(_desen)
    return fallback

FONKSIYON_KW = _sozlukten_python_kelime("def", "fonksiyon")
SINIF_KW = _sozlukten_python_kelime("class", "sınıf")

def sozlukten_kelime_listesi():
    """SOZLUK'ten temiz Türkçe kelime listesi çıkar - önbellekli"""
    
    # Önbellek, sözlüğün o anki içeriğine bağlı bir imzayla doğrulanır.
    # Eskiden yalnızca dosya tarihine bakılıyordu: tarihi korunarak kurulan
    # yeni bir sürüm eski kelime listesini, bir kez başarısız yüklenen sözlük
    # ise sonsuza dek BOŞ listeyi kullanmaya devam ediyordu.
    try:
        boyut = os.path.getsize(SOZLUK_TXT_YOLU)
    except OSError:
        boyut = -1
    imza = f"{len(SOZLUK)}|{len(SOZLUK_TAKMA_ADLAR)}|{boyut}"
    if os.path.exists(CACHE_JSON_YOLU):
        try:
            with open(CACHE_JSON_YOLU, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if (isinstance(veri, dict) and veri.get("imza") == imza
                    and veri.get("kelimeler")):
                return veri["kelimeler"]
        except Exception:
            pass
    
    # Cache yoksa veya geçersizse oluştur
    kelimeler = set()
    for desen in SOZLUK.keys():
        if desen in SOZLUK_TAKMA_ADLAR:
            continue
        if '.' in desen:
            continue
        kelime = desen.replace(r'\b', '').strip()
        kelime = kelime.strip('"').strip("'")
        if kelime and ' ' not in kelime and '.' not in kelime:
            kelimeler.add(kelime)
    
    sonuc = sorted(list(kelimeler))

    if sonuc:  # boş liste (sözlük yüklenemedi) asla önbelleğe yazılmaz
        try:
            # Klasör yoksa oluştur (calisma_yolu garanti değilse)
            os.makedirs(os.path.dirname(CACHE_JSON_YOLU), exist_ok=True)
            with open(CACHE_JSON_YOLU, "w", encoding="utf-8") as f:
                json.dump({"imza": imza, "kelimeler": sonuc}, f, ensure_ascii=False)
        except Exception:
            pass
    
    return sonuc

TURKCE_KELIMELER = sozlukten_kelime_listesi()

print(f"[TurKod] {len(TURKCE_KELIMELER)} kelime otomatik tamamlama icin yuklendi")
# === KULLANICI TANIMLARI (değişken/fonksiyon adları) ===
KIMLIK = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*"

# Kullanıcı bu adları kendi değişkeni olarak tanımlasa bile çevrilmeleri gerekir:
# dil sözdizimine ait anahtar kelimeler ve dunder karşılıkları (başlat_özel -> __init__).
KORUNMAYAN_KELIMELER = {
    _sozluk_kelime(_desen)
    for _desen, _hedef in SOZLUK.items()
    if _hedef.strip() in _PY_KEYWORDS or _hedef.strip().startswith("__")
}

# Framework'lerin özel metot adları kullanıcı tanımı olarak korunmamalı;
# aksi halde sözlük çevirisi uygulanmaz ve Ursina/Pygame bu metotları çağırırken bulamaz.
_OZEL_METOT_HEDEFLERI = {
    "update", "input", "awake", "on_enable", "on_disable",
    "on_destroy", "run", "quit",
}
KORUNMAYAN_KELIMELER.update({
    _sozluk_kelime(_desen)
    for _desen, _hedef in SOZLUK.items()
    if _hedef.strip() in _OZEL_METOT_HEDEFLERI
})


def _parantez_derinligi_haritasi(kod):
    """Her karakter konumu için ( [ { derinliğini döner (string/yorum kabaca atlanır).

    `^\\s*isim\\s*=` gibi satır-başı regex'leri, çok satırlı bir çağrının
    içinde (derinlik > 0) tek başına duran bir kwarg satırını ("dolgu=...,")
    gerçek bir üst düzey atamayla ayırt edemez. Bu harita, eşleşmenin
    derinlik 0'da olup olmadığını kontrol etmek için kullanılır.
    """
    derinlikler = [0] * (len(kod) + 1)
    derinlik = 0
    tirnak = None
    i = 0
    n = len(kod)
    while i < n:
        c = kod[i]
        derinlikler[i] = derinlik
        if tirnak:
            if c == '\\':
                i += 2
                continue
            if c == tirnak:
                tirnak = None
        elif c in ('"', "'"):
            tirnak = c
        elif c == '#':
            # Yorumun geri kalanını atla (derinlik değişmez, satır sonuna kadar).
            while i < n and kod[i] != '\n':
                derinlikler[i] = derinlik
                i += 1
            continue
        elif c in '([{':
            derinlik += 1
        elif c in ')]}':
            derinlik = max(0, derinlik - 1)
        i += 1
    derinlikler[n] = derinlik
    return derinlikler


def _ust_duzey_eslesmeler(desen, kod, flags=0):
    """re.findall ile aynı, ama yalnızca derinlik 0'daki eşleşmeleri döner."""
    derinlikler = _parantez_derinligi_haritasi(kod)
    sonuc = []
    for m in re.finditer(desen, kod, flags):
        if derinlikler[m.start()] == 0:
            sonuc.append(m.group(1) if m.groups() else m.group(0))
    return sonuc


def kullanici_tanimlari(kod):
    """Kodda kullanıcının tanımladığı tüm isimleri döndürür.
    Çevirici ve yerel düzeltme bu isimlere dokunmaz."""
    tanimlar = set()
    # fonksiyon / sınıf adları
    tanimlar.update(re.findall(
        rf'\b{re.escape(FONKSIYON_KW)}\s+({KIMLIK})\s*\(', kod))
    # "sınıf A:" ve kalıtımlı "sınıf A(Temel):" biçimleri
    tanimlar.update(re.findall(
        rf'\b{re.escape(SINIF_KW)}\s+({KIMLIK})\s*[:(]', kod))
    # atama hedefleri: =, +=, -=, *=, /=, //=, %=, **=
    # NOT: Yalnızca parantez/köşeli parantez/süslü parantez derinliği 0 olan
    # eşleşmeler kabul edilir; aksi halde çok satırlı bir fonksiyon çağrısı
    # içindeki "dolgu=(0.8, 0.9, 1)," gibi bir kwarg satırı, üst düzey bir
    # değişken ataması sanılıp yanlışlıkla çeviriden muaf tutulurdu.
    tanimlar.update(_ust_duzey_eslesmeler(
        rf'^\s*({KIMLIK})\s*(?:\+=|-=|\*=|/=|//=|%=|\*\*=|=(?!=))',
        kod, re.MULTILINE))
    # çoklu atama: a, b = ...
    for grup in _ust_duzey_eslesmeler(
            rf'^\s*((?:\*?{KIMLIK}\s*,\s*)+\*?{KIMLIK})\s*=(?!=)', kod, re.MULTILINE):
        tanimlar.update(p.strip().lstrip('*') for p in grup.split(',') if p.strip())
    # döngü değişkenleri: için i aralık(...), için x, y içinde ..., döngü i aralık(...)
    # Virgülle ayrılmış tüm değişkenler yakalanır; 'döngü' kalıbı da kapsanır.
    # 'döngü doğru:' gibi kalıplar sonra 'içinde'/'aralık(' gelmediği için eşleşmez.
    for grup in re.findall(
            rf'\b(?:için|döngü)\s+((?:{KIMLIK}\s*,\s*)*{KIMLIK})\s+(?:içinde|aralık\s*\()',
            kod):
        tanimlar.update(p.strip() for p in grup.split(',') if p.strip())
    # Liste üreteçleri: [x için x içinde liste] veya [x için x içinde liste eğer ...]
    tanimlar.update(re.findall(rf'\[[^]]*?\s+için\s+({KIMLIK})\s+içinde', kod))
    # takma adlar: içe_aktar X olarak Y, ile X olarak Y
    tanimlar.update(re.findall(rf'\bolarak\s+({KIMLIK})', kod))
    # nesne öznitelikleri
    tanimlar.update(re.findall(rf'\bself\.({KIMLIK})\b', kod))
    tanimlar.update(re.findall(rf'\bkendisi\.({KIMLIK})\b', kod))
    # fonksiyon parametreleri
    for grup in re.findall(
            rf'\b{re.escape(FONKSIYON_KW)}\s+{KIMLIK}\s*\(([^)]*)\)', kod):
        for p in grup.split(','):
            # "*argümanlar", "**sözlük", "x: int = 3" biçimleri de desteklenir.
            p = p.strip().split('=')[0].split(':')[0].strip().lstrip('*').strip()
            if p and p not in ("self", "kendisi"):
                tanimlar.add(p)
    # with ... as ... kalıbı
    tanimlar.update(re.findall(rf'\bile\b\s+.*?\s+olarak\s+({KIMLIK})\b', kod))
    # except ... as ... kalıbı
    tanimlar.update(re.findall(rf'\bhata_yakala\b\s+.*?\s+olarak\s+({KIMLIK})\b', kod))
    return tanimlar - KORUNMAYAN_KELIMELER
