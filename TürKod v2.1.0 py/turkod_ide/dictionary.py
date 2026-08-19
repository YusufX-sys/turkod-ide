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

# Alternatif yol kontrolü
if not os.path.exists(SOZLUK_TXT_YOLU):
    SOZLUK_TXT_YOLU = os.path.join(_KAYNAK_YOLU, "TurKod_Sozluk.txt")

# Cache dosyası (json) - Kullanıcı klasörü
CACHE_JSON_YOLU = os.path.join(_CALISMA_YOLU, ".turkod_kelimeler.json")

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
        
        # 4. Hala yoksa dosya adıyla dene (mevcut dizin)
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

if not SOZLUK:
    print("[TurKod] UYARI: Sözlük dosyası bulunamadı veya boş!")

def _ters_sozluk_olustur():
    """SOZLUK'ten Python→Türkçe ters çeviri sözlüğü oluştur"""
    ters_sozluk = {}
    for desen, python_karsiligi in SOZLUK.items():
        tr_kelime = desen.replace(r'\b', '').strip('"').strip("'")
        py_kelime = python_karsiligi.strip('"').strip("'")
        if tr_kelime and py_kelime and ' ' not in tr_kelime and len(py_kelime) > 1:
            # Aynı Python adına birden çok Türkçe kelime eşlenebiliyor;
            # ilk (sözlükteki asıl) karşılığı koru ki ters çeviri belirleyici olsun.
            ters_sozluk.setdefault(py_kelime, tr_kelime)
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
    "fonksiyon", "sınıf", "döngü", "eğer", "değilse_eğer", "değilse",
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
    r"^(?:" + "|".join(re.escape(w) for w in _block_words) + r")\b"
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
    
    # Cache varsa direkt oku (Silme işlemi en üstte _cache_temizle ile yapıldı)
    if os.path.exists(CACHE_JSON_YOLU):
        try:
            with open(CACHE_JSON_YOLU, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Cache yoksa veya geçersizse oluştur
    kelimeler = set()
    for desen in SOZLUK.keys():
        if '.' in desen:
            continue
        kelime = desen.replace(r'\b', '').strip()
        kelime = kelime.strip('"').strip("'")
        if kelime and ' ' not in kelime and '.' not in kelime:
            kelimeler.add(kelime)
    
    sonuc = sorted(list(kelimeler))
    
    try:
        # Klasör yoksa oluştur (calisma_yolu garanti değilse)
        os.makedirs(os.path.dirname(CACHE_JSON_YOLU), exist_ok=True)
        with open(CACHE_JSON_YOLU, "w", encoding="utf-8") as f:
            json.dump(sonuc, f, ensure_ascii=False)
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

def kullanici_tanimlari(kod):
    """Kodda kullanıcının tanımladığı tüm isimleri döndürür.
    Çevirici ve yerel düzeltme bu isimlere dokunmaz."""
    tanimlar = set()
    # fonksiyon / sınıf adları
    tanimlar.update(re.findall(
        rf'\b{re.escape(FONKSIYON_KW)}\s+({KIMLIK})\s*\(', kod))
    tanimlar.update(re.findall(
        rf'\b{re.escape(SINIF_KW)}\s+({KIMLIK})\s*:', kod))
    # atama hedefleri: =, +=, -=, *=, /=, //=, %=, **=
    tanimlar.update(re.findall(
        rf'^\s*({KIMLIK})\s*(?:\+=|-=|\*=|/=|//=|%=|\*\*=|=(?!=))',
        kod, re.MULTILINE))
    # çoklu atama: a, b = ...
    for grup in re.findall(
            rf'^\s*((?:{KIMLIK}\s*,\s*)+{KIMLIK})\s*=(?!=)', kod, re.MULTILINE):
        tanimlar.update(p.strip() for p in grup.split(',') if p.strip())
    # döngü değişkenleri: döngü i aralık(...), döngü x içinde ...
    tanimlar.update(re.findall(rf'\bdöngü\s+({KIMLIK})', kod))
    # Liste üreteçleri: [x için x içinde liste] veya [x için x içinde liste eğer ...]
    for grup in re.findall(rf'\[({KIMLIK})\s+için\s+({KIMLIK})\s+içinde', kod):
        tanimlar.update(grup)
    # takma adlar: içe_aktar X olarak Y, ile X olarak Y
    tanimlar.update(re.findall(rf'\bolarak\s+({KIMLIK})', kod))
    # nesne öznitelikleri
    tanimlar.update(re.findall(rf'\bself\.({KIMLIK})\b', kod))
    tanimlar.update(re.findall(rf'\bkendisi\.({KIMLIK})\b', kod))
    # fonksiyon parametreleri
    for grup in re.findall(
            rf'\b{re.escape(FONKSIYON_KW)}\s+{KIMLIK}\s*\(([^)]*)\)', kod):
        for p in grup.split(','):
            p = p.strip().split('=')[0].strip()
            if p and p not in ("self", "kendisi"):
                tanimlar.add(p)
    return tanimlar - KORUNMAYAN_KELIMELER
