# ============ DİJİTAL İMZA SİSTEMİ ============
import hashlib
import base64
import sys
import os


class DijitalImza:
    """
    RSA Dijital İmza Doğrulama Sınıfı
    .py ve .exe dosyalarının bütünlüğünü kontrol eder
    """
    
    TURKOD_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuFXhkaH2bJWbe56exYTP
JXZDkX5aBmeV9Hop5xL2+bVBn/uGG4zpFjnQjQkLhNV7lTZNDQcz/FAWTuBaZiY9
raINwqtz1fOF4cO1gKYL3pkiBnAVNB6HzsW7u7sKkTGyYnrEldFBsQy78joY5ve3
KGmttHvi+Uw5E89qUbFcgoihkmkEgxmaGmwvcT9wyVmlajFO2jtxP7S2b7ChAAqi
BoPepkXQoCo9c6kuyVlsVGe6r9ghi4F70nLt97cHmlMMHAr9SlNSgGRD6ZMV6b0c
xvvIld3r3ekTlqCvBE0ueTZN2LAmwxJ8fxR+pxYqvSMr4z/zSUC6CEZXur4bfH7/
1QIDAQAB
-----END PUBLIC KEY-----"""
    
    # İmza değeri (Her sürümde güncellenir)
    # .py için: turkod.py.sig içeriği
    # .exe için: turkod.exe.sig içeriği
    TURKOD_IMZA_PY = "GUNCELLENECEK"
    TURKOD_IMZA_EXE = "GUNCELLENECEK"
    
    @staticmethod
    def _kaynak_yolu_bul(dosya_adi=""):
        """
        PyInstaller .exe'sinde veya .py'de doğru kaynak yolunu bulur.
        .exe'de: sys._MEIPASS (geçici klasör, exe'nin içindeki dosyalar)
        .py'de:  scriptin bulunduğu klasör
        """
        if getattr(sys, 'frozen', False):
            # PyInstaller .exe - sys._MEIPASS kullan!
            base_path = sys._MEIPASS
        else:
            # Normal Python çalışması
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        if dosya_adi:
            return os.path.join(base_path, dosya_adi)
        return base_path
    
    @staticmethod
    def _calisma_yolu_bul(dosya_adi=""):
        """
        Çalışma zamanında yazılabilir dosyalar için.
        .exe'de: EXE'nin bulunduğu klasör
        .py'de:  scriptin bulunduğu klasör
        """
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        if dosya_adi:
            return os.path.join(base_path, dosya_adi)
        return base_path
    
    @staticmethod
    def dogrula():
        """
        Çalışan dosyanın (.py veya .exe) imzasını doğrula.
        Returns: (basarili: bool, mesaj: str, detay: str)
        """
        import traceback
        import binascii
        
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            
            # Hangi dosya çalışıyor?
            if getattr(sys, 'frozen', False):
                dosya_yol = sys.executable
                imza_base64 = DijitalImza.TURKOD_IMZA_EXE
                tip = "EXE"
                
                # 1. Önce .exe'nin yanındaki .sig dosyasına bak
                sig_yol = dosya_yol + ".sig"
                if os.path.exists(sig_yol):
                    with open(sig_yol, "r", encoding="utf-8") as f:
                        imza_base64 = f.read().strip()
                
                # 2. Yoksa sys._MEIPASS içine bak
                if not imza_base64 or imza_base64 == "GUNCELLENECEK":
                    sig_yol = os.path.join(sys._MEIPASS, "TürKod IDE.exe.sig")
                    if os.path.exists(sig_yol):
                        with open(sig_yol, "r", encoding="utf-8") as f:
                            imza_base64 = f.read().strip()
                
            else:
                dosya_yol = os.path.abspath(__file__)
                imza_base64 = DijitalImza.TURKOD_IMZA_PY
                tip = "PY"
                
                # 1. Önce .py'nin yanındaki .sig dosyasına bak
                sig_yol = dosya_yol + ".sig"
                if os.path.exists(sig_yol):
                    with open(sig_yol, "r", encoding="utf-8") as f:
                        imza_base64 = f.read().strip()
                
                # 2. Yoksa script dizinine bak
                if not imza_base64 or imza_base64 == "GUNCELLENECEK":
                    sig_yol = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "turkod_enhanced_complete.py.sig"
                    )
                    if os.path.exists(sig_yol):
                        with open(sig_yol, "r", encoding="utf-8") as f:
                            imza_base64 = f.read().strip()
            
            # ============ DETAYLI RAPOR BAŞLANGICI ============
            print(f"\n{'='*70}")
            print("  DİJİTAL İMZA - DETAYLI DOĞRULAMA RAPORU")
            print(f"{'='*70}")
            print(f"  Dosya tipi: {tip}")
            print(f"  Dosya yolu: {dosya_yol}")
            print(f"  Dosya var mı: {os.path.exists(dosya_yol)}")
            print(f"  İmza kaynağı: {'Kod içi değişken' if imza_base64 == DijitalImza.TURKOD_IMZA_PY or imza_base64 == DijitalImza.TURKOD_IMZA_EXE else 'Dosya: ' + sig_yol}")
            print(f"  İmza atanmış mı: {bool(imza_base64 and imza_base64 != 'GUNCELLENECEK')}")
            print(f"  İmza uzunluğu: {len(imza_base64) if imza_base64 else 0} karakter")
            print(f"{'='*70}")
            
            # Dosya var mı kontrol et
            if not os.path.exists(dosya_yol):
                print(f"  HATA: Dosya bulunamadı!")
                print(f"{'='*70}\n")
                return False, "❌ Dosya bulunamadı", dosya_yol
            
            # İmza boş mu?
            if not imza_base64 or imza_base64 == "GUNCELLENECEK":
                print(f"  HATA: İmza atanmamış!")
                print(f"{'='*70}\n")
                return False, "⚠️ İmza atanmamış", "Lütfen imza oluşturun"
            
            # Dosyayı oku ve hash hesapla
            with open(dosya_yol, "rb") as f:
                icerik = f.read()
            
            dosya_hash = hashlib.sha256(icerik).hexdigest()
            dosya_boyut = len(icerik)
            
            print(f"  Dosya boyutu: {dosya_boyut:,} bayt")
            print(f"  Dosya SHA-256: {dosya_hash}")
            print(f"  Dosya ilk 20 bayt (hex): {binascii.hexlify(icerik[:20]).decode()}")
            print(f"  Dosya son 20 bayt (hex): {binascii.hexlify(icerik[-20:]).decode()}")
            print(f"{'='*70}")
            
            # Public key'i yükle ve bilgilerini yazdır
            public_key = serialization.load_pem_public_key(
                DijitalImza.TURKOD_PUBLIC_KEY.encode()
            )
            
            # Public key hash'i (fingerprint)
            pub_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            pub_key_hash = hashlib.sha256(pub_key_bytes).hexdigest()[:16]
            print(f"  Public Key fingerprint: {pub_key_hash}")
            print(f"  Public Key uzunluğu: {len(DijitalImza.TURKOD_PUBLIC_KEY)} karakter")
            print(f"{'='*70}")
            
            # İmzayı decode et
            try:
                imza = base64.b64decode(imza_base64)
                print(f"  İmza decode edildi: {len(imza)} bayt")
                print(f"  İmza ilk 10 bayt (hex): {binascii.hexlify(imza[:10]).decode()}")
                print(f"{'='*70}")
            except Exception as decode_hata:
                print(f"  HATA: İmza Base64 decode başarısız!")
                print(f"  Decode hatası: {decode_hata}")
                print(f"{'='*70}\n")
                return False, "❌ İmza formatı hatalı", str(decode_hata)
            
            # Doğrula
            print(f"  Doğrulama başlatılıyor...")
            public_key.verify(
                imza,
                icerik,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Başarılı
            hash_kisa = dosya_hash[:16] + "..." + dosya_hash[-8:]
            print(f"  ✓ DOĞRULAMA BAŞARILI!")
            print(f"{'='*70}\n")
            
            return True, f"✅ İmza doğrulandı ({tip})", f"Hash: {hash_kisa}"
            
        except Exception as e:
            hata = str(e)
            print(f"\n{'='*70}")
            print("  DİJİTAL İMZA DOĞRULAMA HATASI (DETAYLI)")
            print(f"{'='*70}")
            print(f"  Exception tipi: {type(e).__name__}")
            print(f"  Exception mesajı: '{hata}'")
            print(f"  Exception mesajı boş mu: {len(hata) == 0}")
            print(f"{'='*70}")
            print("  FULL TRACEBACK:")
            traceback.print_exc()
            print(f"{'='*70}")
            
            if "verification failed" in hata.lower() or type(e).__name__ == "InvalidSignature":
                print(f"  YORUM: İmza GEÇERSİZ - Dosya imza atıldıktan sonra değiştirilmiş")
                print(f"  ÇÖZÜM: Yeni imza oluşturulmalı")
                print(f"{'='*70}\n")
                return False, "❌ İmza GEÇERSİZ", "Dosya değiştirilmiş olabilir"
            
            print(f"  YORUM: Beklenmeyen hata")
            print(f"{'='*70}\n")
            return False, "⚠️ Doğrulama hatası", hata[:100] if hata else type(e).__name__
    
    @staticmethod
    def hash_hesapla(dosya_yol=None):
        """Dosyanın SHA-256 hash'ini hesapla"""
        if dosya_yol is None:
            dosya_yol = sys.executable if getattr(sys, 'frozen', False) else __file__
        
        try:
            with open(dosya_yol, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except:
            return "Hesaplanamadı"


# ============ KISA YOL ============
def imza_dogrula():
    """Kolay erişim için kısayol"""
    return DijitalImza.dogrula()
# ============ PYINSTALLER UYUMLULUĞU ============
import sys
import os

def kaynak_yolu(dosya_adi=""):
    """
    PyInstaller .exe veya normal .py'de doğru kaynak yolunu bulur.
    .exe'de: sys._MEIPASS (geçici klasör)
    .py'de:  scriptin bulunduğu klasör
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller .exe
        base_path = sys._MEIPASS
    else:
        # Normal Python çalışması
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    if dosya_adi:
        return os.path.join(base_path, dosya_adi)
    return base_path


def calisma_yolu(dosya_adi=""):
    """
    Çalışma zamanında yazılabilir dosyalar için (log, cache, ayarlar)
    .exe'de: EXE'nin yanındaki klasör
    .py'de:  scriptin bulunduğu klasör
    """
    if getattr(sys, 'frozen', False):
        # .exe'nin bulunduğu klasör
        base_path = os.path.dirname(sys.executable)
    else:
        # .py'nin bulunduğu klasör
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    if dosya_adi:
        return os.path.join(base_path, dosya_adi)
    return base_path
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
import re
import subprocess
import tempfile
import json
import threading
import time
from datetime import datetime
import ast
import uuid

# Turkce-Python referans listesi (AI icin dahili kullanim, ayarlarda gorunmez)
# ============ PYTHON'DAN TÜRKOD'A ÇEVİRİ ============
# ============ SOZLUK (Turkish to Python) ============
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
        
        # 3. Hala yoksa dosya adıyla dene (mevcut dizin)
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
    print("[TurKod] UYARI: Sözlük dosyası bulunamadı!")

# ============ TERS SOZLUK (Python to Turkish) ============
def _ters_sozluk_olustur():
    """SOZLUK'ten Python→Türkçe ters çeviri sözlüğü oluştur"""
    ters_sozluk = {}
    for desen, python_karsiligi in SOZLUK.items():
        tr_kelime = desen.replace(r'\b', '').strip('"').strip("'")
        py_kelime = python_karsiligi.strip('"').strip("'")
        if tr_kelime and py_kelime and ' ' not in tr_kelime and len(py_kelime) > 1:
            ters_sozluk[py_kelime] = tr_kelime
    return ters_sozluk

TERS_SOZLUK = _ters_sozluk_olustur()

# ============ PYTHON'DAN TÜRKOD'A ÇEVİRİ ============
def python_kodu_turkceye_cevir(python_kodu):
    saklanan_metinler = []
    def sakla(match):
        uid = uuid.uuid4().hex[:12]
        saklanan_metinler.append((uid, match.group(0)))
        return f"\x00METIN_{uid}\x00"
    string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
    gecici_kod = re.sub(string_ve_yorum, sakla, python_kodu)

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

    isim_sak = {}
    for isim in sorted(tanimlar, key=len, reverse=True):
        yer = f"__ISIM_SABITI_{len(isim_sak)}__"
        isim_sak[yer] = isim
        gecici_kod = re.sub(rf'\b{re.escape(isim)}\b', yer, gecici_kod)

    for py_kelime, tr_kelime in sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True):
        gecici_kod = re.sub(rf'\b{re.escape(py_kelime)}\b', tr_kelime, gecici_kod)

    for uid, metin in saklanan_metinler:
        gecici_kod = gecici_kod.replace(f"\x00METIN_{uid}\x00", metin)
    for yer, isim in isim_sak.items():
        gecici_kod = gecici_kod.replace(yer, isim)
    return gecici_kod
# ============ AI PROVIDER IMPORTS (optional) ============
try:
    import openai
except ImportError:
    openai = None
try:
    from google import genai
except ImportError:
    genai = None
try:
    import anthropic
except ImportError:
    anthropic = None
try:
    from groq import Groq
except ImportError:
    Groq = None

# ============ SETTINGS MANAGER ============
class AyarlarYoneticisi:
    def __init__(self):
        self.dosya_yolu = os.path.join(os.path.expanduser("~"), ".turkod_ayarlar.json")
        self.varsayilanlar = {
            "tema": "Koyu",
            "otomatik_tamamlama": True,
            "otomatik_kaydetme": False,
            "otomatik_kaydetme_aralik": 30,
            "yazi_boyutu": 14,
            "yazi_tipi": "Consolas",
            "satir_numaralari": True,
            "bosluk_gostergesi": True,
            "kelime_sar": False,
            "minimap": False,
            "ai_aktif": False,
            "ai_saglayici": "OpenAI",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
           "ai_sistem_mesaji": """Sen bir Python kodlama asistanisin. Kullanici TürKod (Türkçe'ye çevrilmiş özel Python) yazıyor.
            Sen ise Python değil ``` python ``` arasına Python yaz.
            KURALLAR:
            - Kod verirken MUTLAKA ```python ve ``` arasina yaz.
            - Aciklama kismi duz metin, kod kismi ayri blok olmali.
            -Sadece Python kodları ver başka bir dil kullanamazsın.
            """,
            "ai_sicaklik": 0.7,
            "ai_max_token": 4096,
            "son_proje_dizini": os.path.expanduser("~"),
            "son_acik_dosyalar": []
        }
        self.ayarlar = self.varsayilanlar.copy()
        self.yukle()

    def yukle(self):
        if os.path.exists(self.dosya_yolu):
            try:
                with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                    kayitli = json.load(f)
                    self.ayarlar.update(kayitli)
            except:
                pass

    def kaydet(self):
        try:
            with open(self.dosya_yolu, "w", encoding="utf-8") as f:
                json.dump(self.ayarlar, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get(self, anahtar):
        return self.ayarlar.get(anahtar, self.varsayilanlar.get(anahtar))

    def set(self, anahtar, deger):
        self.ayarlar[anahtar] = deger
        self.kaydet()


# ============ TEMA RENKLERI ============
TEMA_RENKLERI = {
    "Koyu": {
        "bg": "#1e1e1e", "sidebar": "#252526", "activity_bar": "#333333",
        "tab_active": "#1e1e1e", "tab_inactive": "#2d2d2d", "status_bar": "#007acc",
        "line_number": "#858585", "text": "#d4d4d4", "keyword": "#569cd6",
        "builtin": "#dcdcaa", "string": "#ce9178", "comment": "#6a9955",
        "number": "#b5cea8", "operator": "#d4d4d4", "selection": "#264f78",
        "panel_bg": "#252526", "panel_fg": "#cccccc", "border": "#3c3c3c",
        "button_bg": "#0e639c", "button_hover": "#1177bb", "ai_panel": "#1e1e1e",
        "ai_user": "#2d2d30", "ai_assistant": "#252526", "ai_input": "#3c3c3c",
        "minimap_bg": "#252526",
    },
    "Açık": {
        "bg": "#ffffff", "sidebar": "#f3f3f3", "activity_bar": "#e8e8e8",
        "tab_active": "#ffffff", "tab_inactive": "#ececec", "status_bar": "#0078d4",
        "line_number": "#237893", "text": "#000000", "keyword": "#0000ff",
        "builtin": "#795e26", "string": "#a31515", "comment": "#008000",
        "number": "#098658", "operator": "#000000", "selection": "#add6ff",
        "panel_bg": "#f3f3f3", "panel_fg": "#333333", "border": "#e5e5e5",
        "button_bg": "#0078d4", "button_hover": "#106ebe", "ai_panel": "#ffffff",
        "ai_user": "#e8f4ff", "ai_assistant": "#f5f5f5", "ai_input": "#ffffff",
        "ai_chat_bg": "#f0f0f0", "minimap_bg": "#f3f3f3",
    },
    "Yüksek Kontrast": {
        "bg": "#000000", "sidebar": "#000000", "activity_bar": "#000000",
        "tab_active": "#000000", "tab_inactive": "#000000", "status_bar": "#000000",
        "line_number": "#ffffff", "text": "#ffffff", "keyword": "#ffff00",
        "builtin": "#00ffff", "string": "#00ff00", "comment": "#808080",
        "number": "#ff00ff", "operator": "#ffffff", "selection": "#0080ff",
        "panel_bg": "#000000", "panel_fg": "#ffffff", "border": "#ffffff",
        "button_bg": "#0000ff", "button_hover": "#000080", "ai_panel": "#000000",
        "ai_user": "#1a1a1a", "ai_assistant": "#0a0a0a", "ai_input": "#1a1a1a"
    },
    "Monokai": {
        "bg": "#272822", "sidebar": "#3e3d32", "activity_bar": "#414339",
        "tab_active": "#272822", "tab_inactive": "#3e3d32", "status_bar": "#75715e",
        "line_number": "#90908a", "text": "#f8f8f2", "keyword": "#f92672",
        "builtin": "#a6e22e", "string": "#e6db74", "comment": "#75715e",
        "number": "#ae81ff", "operator": "#f8f8f2", "selection": "#49483e",
        "panel_bg": "#3e3d32", "panel_fg": "#f8f8f2", "border": "#75715e",
        "button_bg": "#66d9ef", "button_hover": "#a6e22e", "ai_panel": "#272822",
        "ai_user": "#3e3d32", "ai_assistant": "#383830", "ai_input": "#3e3d32"
    },
    "Solarized Koyu": {
        "bg": "#002b36", "sidebar": "#073642", "activity_bar": "#073642",
        "tab_active": "#002b36", "tab_inactive": "#073642", "status_bar": "#268bd2",
        "line_number": "#586e75", "text": "#839496", "keyword": "#268bd2",
        "builtin": "#b58900", "string": "#2aa198", "comment": "#586e75",
        "number": "#d33682", "operator": "#839496", "selection": "#073642",
        "panel_bg": "#073642", "panel_fg": "#93a1a1", "border": "#586e75",
        "button_bg": "#268bd2", "button_hover": "#2aa198", "ai_panel": "#002b36",
        "ai_user": "#073642", "ai_assistant": "#083a4b", "ai_input": "#073642"
    }
}

    
# ============ KELIME LISTESI (Otomatik Tamamlama Icin) ============
def sozlukten_kelime_listesi():
    """SOZLUK'ten temiz Türkçe kelime listesi çıkar - önbellekli"""
    cache_dosya = os.path.join(os.path.expanduser("~"), ".turkod_kelimeler.json")
    sozluk_yolu = None
    for aday in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "TurKod_Sozluk.txt"),
                 os.path.join(os.getcwd(), "TurKod_Sozluk.txt")):
        if os.path.exists(aday):
            sozluk_yolu = aday
            break
    if os.path.exists(cache_dosya) and (sozluk_yolu is None or
            os.path.getmtime(cache_dosya) >= os.path.getmtime(sozluk_yolu)):
        try:
            with open(cache_dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
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
        with open(cache_dosya, "w", encoding="utf-8") as f:
            json.dump(sonuc, f, ensure_ascii=False)
    except:
        pass
    
    return sonuc

TURKCE_KELIMELER = sozlukten_kelime_listesi()
print(f"[TurKod] {len(TURKCE_KELIMELER)} kelime otomatik tamamlama icin yuklendi")

AI_MODELLERI = {
    "OpenAI": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    "Gemini": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"],
    "Claude": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7"]
}

# ============ OTOMATIK MODEL GUNCELLEME ============
def _modelleri_guncelle():
    
    try:
        import requests
        resp = requests.get("https://api.groq.com/openai/v1/models", timeout=8)
        if resp.status_code == 200:
            modeller = [m["id"] for m in resp.json().get("data", [])]
            modeller = [m for m in modeller if "whisper" not in m.lower()]
            if modeller:
                AI_MODELLERI["Groq"] = sorted(modeller)
                print(f"[TurKod] Groq modelleri guncellendi: {len(modeller)} model")
    except Exception as e:
        print(f"[TurKod] Groq guncelleme hatasi: {e}")
    
    try:
        resp = requests.get("https://api.openai.com/v1/models", timeout=10)
        if resp.status_code == 200:
            modeller = [m["id"] for m in resp.json().get("data", [])]
            modeller = [m for m in modeller if "gpt" in m.lower()]
            if modeller:
                AI_MODELLERI["OpenAI"] = sorted(modeller, reverse=True)
                print(f"[TurKod] OpenAI modelleri guncellendi: {len(modeller)} model")
    except Exception as e:
        print(f"[TurKod] OpenAI guncelleme hatasi: {e}")

threading.Thread(target=_modelleri_guncelle, daemon=True).start()


def turkce_kodu_donustur(turkce_kod):
    # 1) Önce string ve yorumları sakla
    saklanan_metinler = []
    def sakla(match):
        saklanan_metinler.append(match.group(0))
        return f"__METIN_SABITI_{len(saklanan_metinler)-1}__"
    string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
    gecici_kod = re.sub(string_ve_yorum, sakla, turkce_kod)

    # 2) tkinter API çevirileri (nokta-bazlı; korumadan ÖNCE çalışmalı)
    TK_CEVIRILERI = [
        # import
        (r"\bice_aktar\s+tkinter_arayuz\s+olarak\s+([A-Za-z_][A-Za-z0-9_]*)\b", r"import tkinter as \1"),
        (r"\bice_aktar\s+tkinter_arayuz\b", "import tkinter"),
        # sınıflar ve metotlar (nokta-bazlı: değişken adlarına dokunmaz)
        (r"\.pencere\b", ".Tk"),
        (r"\.etiket\b", ".Label"),
        (r"\.dugme\b", ".Button"),
        (r"\.metin_kutusu\b", ".Entry"),
        (r"\.metin_alani\b", ".Text"),
        (r"\.cerceve\b", ".Frame"),
        (r"\.liste_kutusu\b", ".Listbox"),
        (r"\.yeni_pencere\b", ".Toplevel"),
        (r"\.canvas\b", ".Canvas"),
        (r"\.scrollbar\b", ".Scrollbar"),
        (r"\.spinbox\b", ".Spinbox"),
        (r"\.checkbutton\b", ".Checkbutton"),
        (r"\.radiobutton\b", ".Radiobutton"),
        (r"\.menu\b", ".Menu"),
        (r"\.baslik_grafik\b", ".title"),
        (r"\.getir\b", ".get"),
        (r"\.yok_et\b", ".destroy"),
        (r"\.ana_dongu\b", ".mainloop"),
        (r"\.yerlestir\b", ".place"),
        (r"\.boyutlandir\b", ".geometry"),
        # parametre adları (sadece çağrı içindeyken: önünde , veya ( varken)
        (r"([,(]\s*)xml_metin\s*=", r"\1text="),
        (r"([,(]\s*)komut\s*=", r"\1command="),
        (r"([,(]\s*)degisken\s*=", r"\1variable="),
    ]
    for desen, hedef in TK_CEVIRILERI:
        gecici_kod = re.sub(desen, hedef, gecici_kod)

    # 3) Kullanıcı tanımlı isimleri sözlükten koru
    #    NOT: fonksiyon adları ve parametreler KORUNMAZ;
    #    baslat_ozel -> __init__, kendisi -> self gibi çeviriler çalışmalı.
    TR_ID = r'[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*'
    tanimlar = set()
        # Atama hedefleri (parantez derinliği farkındalıklı):
    # açık parantez içindeki devam satırlarında başlayan kwarg'ları atama sanma
    derinlik = 0
    for satir in gecici_kod.split("\n"):
        if derinlik == 0:
            m = re.match(rf'\s*({TR_ID})\s*=(?!=)', satir)
            if m:
                tanimlar.add(m.group(1))
        derinlik += satir.count("(") + satir.count("[") + satir.count("{")
        derinlik -= satir.count(")") + satir.count("]") + satir.count("}")
        if derinlik < 0:
            derinlik = 0
    tanimlar.update(re.findall(rf'\bsinif\s+({TR_ID})', gecici_kod))
    tanimlar.update(re.findall(rf'\bdongu\s+({TR_ID})\s+icinde', gecici_kod))
    tanimlar.update(re.findall(rf'\bself\.({TR_ID})', gecici_kod))
    tanimlar.update(re.findall(rf'\bkendisi\.({TR_ID})', gecici_kod))

    isim_sak = {}
    for isim in sorted(tanimlar, key=len, reverse=True):
        yer = f"__ISIM_SABITI_{len(isim_sak)}__"
        isim_sak[yer] = isim
        gecici_kod = re.sub(rf'\b{re.escape(isim)}\b', yer, gecici_kod)

    # 4) Modül import çevirileri
    MODUL_CEVIRILERI = {
        "matematik": "math",
        "rastgele": "random",
        "tarih_saat": "datetime",
        "isletim_sistemi": "os",
        "sistem": "sys",
        "json": "json",
        "desen": "re",
    }
    for tr_modul, py_modul in MODUL_CEVIRILERI.items():
        gecici_kod = re.sub(
            rf"\bice_aktar\s+{tr_modul}\b",
            f"import {py_modul}",
            gecici_kod
        )
    python_kodu = re.sub(
        r"\bice_aktar\s+([a-zA-Z0-9_]+)\s+den\s+([a-zA-Z0-9_]+)\b",
        r"from \2 import \1",
        gecici_kod
    )
    python_kodu = re.sub(
        r"\bden\s+([a-zA-Z0-9_]+)\s+ice_aktar\s+([a-zA-Z0-9_]+)\b",
        r"from \1 import \2",
        python_kodu
    )
    python_kodu = re.sub(
        r"\bdongu\s+(.*?)\s+icinde\s+(.*?):",
        r"for \1 in \2:",
        python_kodu
    )

    # 5) Modül metot çevirileri (matematik.karekok -> math.sqrt vb.)
    MODUL_METOTLARI = {
        "rastgele": {
            "sec": "choice", "tamsayi": "randint", "ondalik": "random",
            "karistir": "shuffle", "orneklem": "sample", "aralikta_rastgele": "randrange",
            "tohum": "seed", "bit": "getrandbits", "durum_al": "getstate",
            "durum_ayarla": "setstate", "dagilim_duzgun": "uniform",
            "dagilim_beta": "betavariate", "dagilim_ustel": "expovariate",
            "dagilim_gamma": "gammavariate", "dagilim_gauss": "gauss",
            "dagilim_lognormal": "lognormvariate", "dagilim_normal": "normalvariate",
            "dagilim_ucgen": "triangular",
        },
        "matematik": {
            "karekok": "sqrt", "faktoriyel": "factorial", "ebob": "gcd", "ekok": "lcm",
            "taban": "floor", "tavan": "ceil", "mutlak_deger": "fabs",
            "hipotenus": "hypot", "logaritma": "log", "matematik_ust": "exp",
            "sinus": "sin", "cosinus": "cos", "tanjant": "tan",
            "aci_derece": "degrees", "aci_radyan": "radians", "pi_sayisi": "pi", "e_sayisi": "e",
            "arkkosinus": "acos", "arkkosinus_h": "acosh", "arksinus": "asin",
            "arksinus_h": "asinh", "arktanjant": "atan", "arktanjant2": "atan2",
            "arktanjant_h": "atanh", "kombinasyon": "comb", "isaret_kopyala": "copysign",
            "cosinus_h": "cosh", "mesafe": "dist", "hata_fonksiyonu": "erf",
            "hata_fonksiyonu_t": "erfc", "ust_eksi_1": "expm1", "mod": "fmod",
            "kesirli_ust": "frexp", "toplam_hassas": "fsum", "gamma_fonk": "gamma",
            "yakinsa": "isclose", "sonlu_mu": "isfinite", "sonsuz_mu": "isinf",
            "tanim_degil_mi": "isnan", "tamsayi_kok": "isqrt", "kesirli_carp": "ldexp",
            "gamma_log": "lgamma", "logaritma10": "log10", "logaritma_eksi_1": "log1p",
            "logaritma2": "log2", "kesirli_ayir": "modf", "sonraki_say": "nextafter",
            "permutasyon": "perm", "carpim": "prod", "kalan": "remainder",
            "sinus_h": "sinh", "tanjant_h": "tanh", "kirp_sifir": "trunc", "sonraki_ulp": "ulp",
        },
        "tarih_saat": {
            "simdi": "datetime.now", "bugun": "datetime.today",
            "utc_simdi": "datetime.utcnow",
            "utc_damgasi": "datetime.utcfromtimestamp",
            "damga_zaman": "datetime.fromtimestamp",
            "iso_ayristir": "datetime.fromisoformat",
            "tarih_birlestir": "datetime.combine",
            "tarih_ayristir": "datetime.strptime",
            "en_buyuk_tarih": "datetime.max",
            "en_kucuk_tarih": "datetime.min",
            "zaman_farki": "timedelta", "tarih": "date", "zaman": "time",
            "saat_dilimi": "timezone", "dilim_bilgisi": "tzinfo",
            "cozunurluk": "timedelta.resolution",
            "tarih_bicimlendir": "strftime", "zaman_damgasi": "timestamp",
            "haftanin_gunu": "weekday", "iso_format": "isoformat",
            "metin_zaman": "ctime", "yer_degistir": "replace",
        },
    }
    MODUL_ISIMLERI = {
        "rastgele": "random",
        "matematik": "math",
        "tarih_saat": "datetime"
    }
    for modul, metotlar in MODUL_METOTLARI.items():
        py_modul = MODUL_ISIMLERI[modul]
        for tr_metot, py_metot in metotlar.items():
            python_kodu = re.sub(
                rf"\b{modul}\.{tr_metot}\b",
                f"{py_modul}.{py_metot}",
                python_kodu
            )

    # 6) Genel sözlük (uzun desenler önce: çakışma önleme)
    for turkce, python_karsiligi in sorted(SOZLUK.items(), key=lambda x: len(x[0]), reverse=True):
        python_kodu = re.sub(turkce, python_karsiligi, python_kodu)

    # 7) Saklananları geri koy
    for i, metin in enumerate(saklanan_metinler):
        python_kodu = python_kodu.replace(f"__METIN_SABITI_{i}__", metin)
    for yer, isim in isim_sak.items():
        python_kodu = python_kodu.replace(yer, isim)
    return python_kodu


RUNNER_KODU = '''# -*- coding: utf-8 -*-
import traceback
import sys
import re

HATA_ISIMLERI = {
    "NameError": "Tanımsız Kelime Hatası",
    "SyntaxError": "Sözdizimi (Yazım) Hatası",
    "TypeError": "Veri Tipi Hatası",
    "ValueError": "Geçersiz Değer Hatası",
    "ZeroDivisionError": "Sıfıra Bölme Hatası",
    "IndexError": "Liste Indeks Hatası",
    "KeyError": "Sözlük Anahtar Hatası",
    "AttributeError": "Özellik / Metot Bulunamadı Hatası"
}

HATA_MESAJLARI = {
    r"is not defined": "Hatalı bir kelime! Düzeltmeyi deneyebilirsin!",
    r"invalid syntax": "Geçersiz kod yazımı! Eksik sembol veya hatalı kelime kullanımı var!",
    r"unexpected EOF while parsing": "Kapatılmamış parantez veya tırnak işareti var!",
    r"division by zero": "Bir sayı 0'a bolunemez!",
    r"list index out of range": "Listenin sınırları dışında bir elemana ulaşmaya çalıştınız!"
}

import builtins
_gercek_input = builtins.input
def _input(prompt=""):
    sys.stdout.write(str(prompt))
    sys.stdout.flush()
    return _gercek_input()
builtins.input = _input

try:
    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:
        kod = f.read()
    exec(compile(kod, "turkce_kod_calisma.py", "exec"))
except Exception as e:
    exc_type, exc_obj, tb = sys.exc_info()
    hata_adi = exc_type.__name__
    hata_adi_tr = HATA_ISIMLERI.get(hata_adi, hata_adi)

    satir_no = "?"
    for frame in traceback.extract_tb(tb):
        if frame.filename == "turkce_kod_calisma.py":
            satir_no = frame.lineno
            break

    hata_detay = str(e)
    for ing, tr in HATA_MESAJLARI.items():
        hata_detay = re.sub(ing, tr, hata_detay)

    print("\\n" + "="*50)
    print(f"[HATA]: {hata_adi_tr}")
    print(f"Satir Numarasi: {satir_no}")
    print(f"Aciklama: {hata_detay}")
    print("="*50 + "\\n")
'''


# ============ MAIN IDE CLASS ============
class TurkceIDE(ctk.CTk):
    def __init__(self):
        super().__init__()
        # === DEBUGGER ===
        self.debugger = BasitDebugger(self)
        self.withdraw()
        self.ayarlar = AyarlarYoneticisi()
        self.tema = self.ayarlar.get("tema")
        self.colors = TEMA_RENKLERI.get(self.tema, TEMA_RENKLERI["Koyu"])

        self.title("TürKod IDE - Profesyonel Türkçe Python Editorü")
        self.geometry("1600x900")
        self.minsize(1200, 700)

        # SEKME SISTEMI
        self.sekmeler = []
        self.aktif_sekme_id = None
        self.sekme_id_sayac = 0
        
        self.proje_dizini = self.ayarlar.get("son_proje_dizini")
        self.ai_mesajlar = []
        self.ai_mesaj_gecmisi = []

        self.grid_columnconfigure(1, minsize=220)
        self.grid_columnconfigure(2, minsize=4)
        self.grid_columnconfigure(4, minsize=4)
        self.grid_columnconfigure(5, minsize=480)

        self.configure(fg_color=self.colors["bg"])
        self.grid_columnconfigure(3, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._arayuz_olustur()
        self._baglayicilari_ayarla()
        self.after(100, self._ornek_kod_yukle)
        self._otomatik_kaydetme_baslat()
        self.after(200, self._pencere_goster)
        self.protocol("WM_DELETE_WINDOW", self._pencere_kapat)
        self._kod_tanimlari_cache = []
        self._calistirma_process = None
        self._son_kod_hash = ""

    # ← BURAYA TAŞI! __init__ bitti, metodlar buraya başlıyor

    def _koddan_tanimlari_cikar(self, kod):
        """Koddan fonksiyon, sınıf ve değişken isimlerini çıkar"""
        tanimlar = set()
        
        # Fonksiyon tanımları: fonksiyon isim(...):
        fonksiyonlar = re.findall(r'\bfonksiyon\s+([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\s*\(', kod)
        tanimlar.update(fonksiyonlar)
        
        # Sınıf tanımları: sinif Isim:
        siniflar = re.findall(r'\bsinif\s+([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\s*:', kod)
        tanimlar.update(siniflar)
        
        # Değişken atamaları: degisken = ...
        degiskenler = re.findall(r'^([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\s*=', kod, re.MULTILINE)
        tanimlar.update(degiskenler)
        
        # self.degisken atamaları
        self_degiskenler = re.findall(r'\bself\.([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\b', kod)
        kendisi_degiskenler = re.findall(r'\bkendisi\.([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\b', kod)
        tanimlar.update(kendisi_degiskenler)
        tanimlar.update(self_degiskenler)
        
        # Parametre isimleri: fonksiyon isim(param1, param2):
        parametreler = re.findall(r'\bfonksiyon\s+[a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüı]*\s*\(([^)]*)\)', kod)
        for param_grup in parametreler:
            for param in param_grup.split(','):
                param = param.strip().split('=')[0].strip()
                if param and param != 'self':
                    tanimlar.add(param)
        
        return sorted(list(tanimlar))

    def _tamamlama_kelime_listesi_al(self):
        """Otomatik tamamlama için kelime listesini oluştur (sözlük + kod içi tanımlar)"""
        # 1. Sabit sözlük kelimeleri
        sabit_kelimeler = set(TURKCE_KELIMELER)
        
        # 2. Kod içi tanımlar
        mevcut_kod = self.kod_alani.get("1.0", "end-1c")
        kod_tanimlari = set(self._koddan_tanimlari_cikar(mevcut_kod))
        
        # 3. Birleştir (kod tanımları önce gelsin)
        tum_kelimeler = list(kod_tanimlari) + [k for k in sabit_kelimeler if k not in kod_tanimlari]
        
        return tum_kelimeler
        
    def _pencere_goster(self):
        self.deiconify()
        self.update_idletasks()
        self._sekme_layout_guncelle()
        
    def _arayuz_olustur(self):
        # === AKTIVITE BAR (sol en dar) ===
        self.activity_bar = ctk.CTkFrame(self, width=48, fg_color=self.colors["activity_bar"])
        self.activity_bar.grid(row=0, column=0, rowspan=5, sticky="nsew")
        self.activity_bar.grid_propagate(False)

        # Explorer butonu 
        self.explorer_btn = ctk.CTkButton(
            self.activity_bar, 
            text="◀",  
            width=36, 
            height=36,
            fg_color="transparent", 
            text_color=self.colors["text"],
            hover_color="#505050",
            border_color=self.colors["border"],
            border_width=2,
            font=("Segoe UI", 16, "bold"), 
            command=self._gezgin_ac
        )
        self.explorer_btn.pack(pady=(15, 5))
        
        # AI panel butonu 
        self.ai_toggle_btn = ctk.CTkButton(
            self.activity_bar, 
            text="▶", 
            width=36, 
            height=36,
            fg_color="transparent", 
            text_color=self.colors["text"],
            hover_color="#505050",
            border_color=self.colors["border"],
            border_width=2,
            font=("Segoe UI", 16, "bold"), 
            command=self._ai_panel_toggle
        )
        self.ai_toggle_btn.pack(pady=5)

        # === SIDEBAR (Dosya Gezgini) ===
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=self.colors["sidebar"])
        self.sidebar.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=(0, 0))
        self.sidebar.grid_propagate(False)

        self.sidebar_title = ctk.CTkLabel(self.sidebar, text="GEZGİN", font=("Segoe UI", 9, "bold"),
                                           text_color=self.colors["panel_fg"])
        self.sidebar_title.pack(pady=(15, 5), padx=15, anchor="w")

        self.proje_ac_btn = ctk.CTkButton(self.sidebar, text="Proje Aç", width=180,
                                           fg_color=self.colors["button_bg"],
                                           hover_color=self.colors["button_hover"],
                                           border_width=2,
                                           font=("Segoe UI", 10, "bold"), command=self._proje_ac)
        self.proje_ac_btn.pack(pady=(0, 10), padx=15)

        # Treeview için frame
        self.dosya_tree_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.dosya_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.dosya_tree_frame.grid_columnconfigure(0, weight=1)  
        self.dosya_tree_frame.grid_rowconfigure(0, weight=1)     

        # Treeview
        self.dosya_tree = ttk.Treeview(self.dosya_tree_frame, style="Custom.Treeview", show="tree")
        self.dosya_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar 
        self.tree_scrollbar = ctk.CTkScrollbar(self.dosya_tree_frame, command=self.dosya_tree.yview,
                                                orientation="vertical", width=12)
        self.tree_scrollbar.grid(row=0, column=1, sticky="ns")

        self.dosya_tree.configure(yscrollcommand=self.tree_scrollbar.set)

        # Treeview stil ayarları
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            fieldbackground=self.colors["sidebar"],
            font=("Segoe UI", 10),
            rowheight=24
        )
        style.configure("Custom.Treeview.Heading",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            font=("Segoe UI", 9, "bold")
        )
        style.map("Custom.Treeview",
            background=[("selected", self.colors.get("selection", "#264f78"))],
            foreground=[("selected", "white")]
        )

        self.dosya_tree.bind("<Double-1>", self._dosya_tree_cift_tik)
        self.dosya_tree.bind("<<TreeviewOpen>>", self._tree_acildi)

        # === TAB BAR ===
        self.tab_bar = ctk.CTkFrame(self, height=38, fg_color=self.colors["tab_inactive"])
        self.tab_bar.grid(row=0, column=3, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tab_bar.grid_columnconfigure(0, weight=1)
        self.tab_bar.grid_rowconfigure(0, weight=1)

        # Taşma okları (gereksizse gizlenir)
        self.tab_left_btn = ctk.CTkButton(self.tab_bar, text="‹", width=22, corner_radius=0,
            fg_color="transparent", hover_color=self.colors["tab_active"],
            text_color=self.colors["text"], command=lambda: self._sekme_kaydir(120))
        self.tab_right_btn = ctk.CTkButton(self.tab_bar, text="›", width=22, corner_radius=0,
            fg_color="transparent", hover_color=self.colors["tab_active"],
            text_color=self.colors["text"], command=lambda: self._sekme_kaydir(-120))

        # Sekme şeridi (kaydırılabilir alan)
        self.tab_strip = ctk.CTkFrame(self.tab_bar, fg_color="transparent", height=38)
        self.tab_strip.grid(row=0, column=0, sticky="nsew")
        self.tab_strip.grid_propagate(False)
        self.tab_strip.bind("<MouseWheel>", self._sekme_wheel)
        self.tab_strip.bind("<Button-4>", lambda e: self._sekme_kaydir(120))
        self.tab_strip.bind("<Button-5>", lambda e: self._sekme_kaydir(-120))

        self.sekmeler_container = ctk.CTkFrame(self.tab_strip, fg_color="transparent",
                                       height=38, width=176)
        self.sekmeler_container.pack_propagate(False)
        self.sekmeler_container.place(x=0, y=0, relheight=1.0)
        self._sekme_offset = 0
        self._sekme_genisligi = 170

        # Butonlar artık ayrı sütunda, sekmelerle çakışamaz
        self.tab_buttons = ctk.CTkFrame(self.tab_bar, fg_color="transparent")
        self.tab_buttons.grid(row=0, column=3, sticky="e", padx=(5, 10))
        self.yeni_sekme_btn = ctk.CTkButton(self.tab_buttons, text="＋", width=30, height=26,
            command=self._yeni_sekme_olustur, fg_color=self.colors["button_bg"],
            hover_color=self.colors["button_hover"], border_color=self.colors["border"],
            border_width=2, font=("Segoe UI", 14, "bold"), corner_radius=8)
        self.yeni_sekme_btn.pack(side="left", padx=3)

        self.calistir_btn = ctk.CTkButton(self.tab_buttons, text="▶  Çalıştır", width=90, height=26,
            command=self.kodu_calistir, fg_color="#28a745", border_color=self.colors["border"],
            border_width=2, hover_color="#218838", font=("Segoe UI", 14), corner_radius=8)
        self.calistir_btn.pack(side="left", padx=3)

        self.ac_btn = ctk.CTkButton(self.tab_buttons, text="📂 Aç", width=60, height=26,
            command=self.dosya_ac, fg_color=self.colors["button_bg"],
            hover_color=self.colors["button_hover"], border_color=self.colors["border"],
            border_width=2, font=("Segoe UI", 14), corner_radius=8)
        self.ac_btn.pack(side="left", padx=3)

        self.kaydet_btn = ctk.CTkButton(self.tab_buttons, text="📃 Kaydet", width=70, height=26,
            command=self.dosya_kaydet, fg_color=self.colors["button_bg"],
            hover_color=self.colors["button_hover"], border_color=self.colors["border"],
            border_width=2, font=("Segoe UI", 14), corner_radius=8)
        self.kaydet_btn.pack(side="left", padx=3)

        self.cevir_btn = ctk.CTkButton(self.tab_buttons, text="⇄ Çevir", width=70, height=26,
            command=self._kodu_cevir, fg_color=self.colors["button_bg"],
            hover_color=self.colors["button_hover"], border_color=self.colors["border"],
            border_width=2, font=("Segoe UI", 14), corner_radius=8)
        self.cevir_btn.pack(side="left", padx=3)
        

        self.tab_bar.bind("<Configure>", lambda e: self._sekme_layout_guncelle())
        
        # === EDITOR FRAME ===
        self.editor_frame = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        self.editor_frame.grid(row=1, column=3, sticky="nsew")
        self.editor_frame.grid_columnconfigure(1, weight=1)
        self.editor_frame.grid_rowconfigure(0, weight=1)

        # Line Numbers (Izgaraya yalnızca ayar açıksa eklenir)
        self.line_numbers = ctk.CTkTextbox(
            self.editor_frame, width=50,
            font=(self.ayarlar.get("yazi_tipi"), self.ayarlar.get("yazi_boyutu")),
            fg_color=self.colors["bg"], text_color=self.colors["line_number"],
            activate_scrollbars=False, state="disabled", wrap="none"
        )
        if self.ayarlar.get("satir_numaralari"):
            self.line_numbers.grid(row=0, column=0, sticky="nsew")
            
        # Code Editor
        self.kod_alani = ctk.CTkTextbox(
            self.editor_frame,
            font=(self.ayarlar.get("yazi_tipi"), self.ayarlar.get("yazi_boyutu")),
            corner_radius=0, fg_color=self.colors["bg"], text_color=self.colors["text"],
            wrap="none" if not self.ayarlar.get("kelime_sar") else "word",
            undo=True, maxundo=100
        )
        self.kod_alani.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        
        # Minimap (Küçük Harita) - Yeni Eklenti
        self.minimap = ctk.CTkTextbox(
            self.editor_frame, width=120,
            font=(self.ayarlar.get("yazi_tipi"), 4), # Kucuk font boyutu
            fg_color=self.colors["sidebar"], text_color=self.colors["text"],
            activate_scrollbars=False, state="disabled", wrap="none"
        )
        if self.ayarlar.get("minimap"):
            self.minimap.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        # === AI PANEL (sağ) ===
        self.ai_panel = ctk.CTkFrame(self, width=480, fg_color=self.colors["ai_panel"])
        self.ai_panel.grid(row=0, column=5, rowspan=5, sticky="nsew")
        self.ai_panel.grid_propagate(False)
        self.ai_panel_visible = True

        # === ÜST BAR (Başlık + Butonlar) ===
        ai_header = ctk.CTkFrame(self.ai_panel, fg_color="transparent", height=40)
        ai_header.pack(fill="x", padx=12, pady=(10, 0))
        ai_header.pack_propagate(False)

        self.ai_baslik = ctk.CTkLabel(ai_header, text="🤖 AI Asistan",
                                       font=("Segoe UI", 14, "bold"),
                                       text_color=self.colors["text"])
        self.ai_baslik.pack(side="left")

        self.ai_durum = ctk.CTkLabel(ai_header, text="● Hazır",
                                      font=("Segoe UI", 10), text_color="#4caf50")
        self.ai_durum.pack(side="left", padx=(8, 0))

        ctk.CTkButton(ai_header, text="🗑 Yeni", width=60, height=24,
                      fg_color="transparent", hover_color="#c75450",
                      text_color="#ff6b6b", font=("Segoe UI", 10),
                      command=self._ai_temizle).pack(side="right")

        ctk.CTkFrame(self.ai_panel, fg_color=self.colors["border"], height=1).pack(fill="x", padx=12, pady=5)

        # === MESAJ ALANI (Scrollable) ===
        self.ai_chat_frame = ctk.CTkScrollableFrame(self.ai_panel, fg_color="transparent")
        self.ai_chat_frame.pack(fill="both", expand=True, padx=8, pady=5)

        self.ai_typing_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color=self.colors["ai_assistant"],
                                             corner_radius=12, height=32)
        self.ai_typing_label = ctk.CTkLabel(self.ai_typing_frame, text="● ● ●",
                                             font=("Segoe UI", 12), text_color="#888")
        self.ai_typing_label.pack(padx=12, pady=6)
        self.ai_typing_frame.pack_forget() 

        # === ALT GİRİŞ ALANI ===
        self.ai_input_frame = ctk.CTkFrame(self.ai_panel, fg_color=self.colors["ai_input"],
                                            height=100, corner_radius=8)
        self.ai_input_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.ai_input_frame.pack_propagate(False)

        self.ai_input = ctk.CTkTextbox(self.ai_input_frame, font=("Segoe UI", 12),
                                        fg_color="transparent", text_color=self.colors["text"],
                                        height=60, wrap="word", activate_scrollbars=False)
        self.ai_input.pack(fill="both", expand=True, padx=8, pady=(6, 2))
        self.ai_input.insert("1.0", "Bir şey sor...")
        self.ai_input.bind("<FocusIn>", self._ai_input_focus)
        self.ai_input.bind("<FocusOut>", self._ai_input_blur)
        self.ai_input.bind("<Return>", self._ai_gonder_event)
        self.ai_input.bind("<Shift-Return>", lambda e: None)
        
        input_bar = ctk.CTkFrame(self.ai_input_frame, fg_color="transparent", height=28)
        input_bar.pack(fill="x", padx=8, pady=(0, 4))
        input_bar.pack_propagate(False)

        ctk.CTkLabel(input_bar, text="↵ Gönder  |  Shift+↵ Yeni Satır",
                     font=("Segoe UI", 8), text_color="#666").pack(side="left")

        self.ai_gonder_btn = ctk.CTkButton(input_bar, text="⬆ Gönder", width=70, height=22,
                                            fg_color=self.colors["button_bg"],
                                            hover_color=self.colors["button_hover"],
                                            font=("Segoe UI", 10, "bold"),
                                            command=self._ai_gonder)
        self.ai_gonder_btn.pack(side="right")

        # === HIZLI AKSIYONLAR ===
        self.ai_aksiyonlar = ctk.CTkFrame(self.ai_panel, fg_color="transparent", height=32)
        self.ai_aksiyonlar.pack(fill="x", padx=10, pady=(0, 8))
        self.ai_aksiyonlar.pack_propagate(False)

        aksiyonlar = [
            ("🔧 Düzelt", self._ai_kodu_duzelt),
            ("📖 Açıkla", self._ai_kodu_acikla),
            ("⚡ Optimize", self._ai_kodu_optimize),
        ]
        for text, cmd in aksiyonlar:
            ctk.CTkButton(self.ai_aksiyonlar, text=text, width=70, height=26,
                          fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                          font=("Segoe UI", 10), command=cmd).pack(side="left", padx=2)
            
        ctk.CTkButton(self.ai_aksiyonlar, text="📝 TODO", width=70, height=26,
                      fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                      font=("Segoe UI", 10), command=self._todo_panel_ac).pack(side="left", padx=2)                          
        # === STATUS BAR ===
        self.status_bar = ctk.CTkFrame(self, height=24, fg_color=self.colors["status_bar"])
        self.status_bar.grid(row=4, column=3, sticky="ew")
        self.status_bar.grid_propagate(False)

        self.status_left = ctk.CTkLabel(self.status_bar,
                                         text="  Python 3.x | TürKod Hazır",
                                         font=("Segoe UI", 9, "bold"), text_color="white")
        self.status_left.place(rely=0.5, anchor="w")

        # Sağ grup: istatistik butonu + dosya bilgisi yan yana
        self.status_right_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.status_right_frame.place(relx=1.0, rely=0.5, anchor="e")

        self.stats_btn = ctk.CTkButton(self.status_right_frame, text="📊", width=26, height=20,
            fg_color="transparent", hover_color="#1177bb",
            text_color="white", corner_radius=4,
            font=("Segoe UI", 10), command=self._istatistik_goster)
        self.stats_btn.pack(side="left", padx=(0, 6))

        self.status_right = ctk.CTkLabel(self.status_right_frame,
            text="UTF-8 | TRPY ",
            font=("Segoe UI", 9, "bold"), text_color="white")
        self.status_right.pack(side="left")

        # === ENTEGRE TERMİNAL ===
        self.terminal_visible = False
        self.terminal_frame = ctk.CTkFrame(self, height=220, fg_color=self.colors["panel_bg"])
        self.terminal_frame.grid_propagate(False)
        # --- Üstten yeniden boyutlandırma çizgisi ---
        self.terminal_grip = tk.Frame(
            self.terminal_frame,
            bg=self.colors["border"],
            height=6,
            cursor="sb_v_double_arrow"
        )
        self.terminal_grip.pack(fill="x", side="top")
        self.terminal_grip.bind("<Button-1>", self._terminal_grip_basla)
        self.terminal_grip.bind("<B1-Motion>", self._terminal_grip_surukle)
        self.terminal_grip.bind("<ButtonRelease-1>", self._terminal_grip_birak)
        # Başlangıçta gizli; _terminal_toggle ile açılır

        term_header = ctk.CTkFrame(self.terminal_frame, fg_color=self.colors["sidebar"], height=28)
        term_header.pack(fill="x", side="top")
        term_header.pack_propagate(False)
        ctk.CTkLabel(term_header, text="  TERMİNAL", font=("Segoe UI", 9, "bold"),
                     text_color=self.colors["panel_fg"]).pack(side="left", padx=8)
        ctk.CTkButton(term_header, text="🗑", width=26, height=22, fg_color="transparent",
                      hover_color="#c75450", text_color=self.colors["text"],
                      command=self._terminal_temizle).pack(side="right", padx=2)
        ctk.CTkButton(term_header, text="×", width=26, height=22, fg_color="transparent",
                      hover_color="#c75450", text_color=self.colors["text"],
                      command=self._terminal_toggle).pack(side="right", padx=2)

        self.terminal_output = ctk.CTkTextbox(
            self.terminal_frame, font=("Consolas", 10),
            fg_color=self.colors["bg"], text_color=self.colors["text"],
            corner_radius=0, state="disabled"
        )
        self.terminal_output.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        self.terminal_input = ctk.CTkEntry(
            self.terminal_frame, font=("Consolas", 11), height=28,
            fg_color=self.colors["ai_input"], text_color=self.colors["text"],
            border_color=self.colors["border"]
        )
        self.terminal_input.pack(fill="x", padx=2, pady=2)
        self.terminal_input.bind("<Return>", self._terminal_enter)
        # === AYARLAR BUTONU (sol alt) ===
        self.ayarlar_btn = ctk.CTkButton(self.activity_bar, text="⚙", width=36, height=36,
                                          fg_color="transparent", 
                                          text_color=self.colors["text"],
                                          hover_color="#505050",
                                          border_color=self.colors["border"],
                                          border_width=2,
                                          font=("Segoe UI", 16, "bold"),
                                          command=self._ayarlar_penceresi_ac)
        self.ayarlar_btn.pack(side="bottom", pady=15)
        self._grip_olustur()
        self.fold_regions = {}  # {satir_no: (bas_idx, bit_idx, collapsed)}
        self.fold_indicators = {}  # Satır numaralarındaki fold ikonları
        self.fold_states = {}
        self.renk_ayarlarini_yap()
        self._tree_tagleri_ayarla()
        if self.proje_dizini and os.path.exists(self.proje_dizini):
            self.after(200, self._dosya_tree_guncelle)
    def _tree_acildi(self, event=None):
        """Ok işaretine tek tıkla açılan klasörleri de senkron doldur"""
        try:
            item = self.dosya_tree.focus()
            if not item:
                return

            values = self.dosya_tree.item(item, "values")
            if not values or len(values) < 2 or values[1] != "directory":
                return

            durum = values[2] if len(values) > 2 else "collapsed"
            if durum != "collapsed":
                return  # zaten yüklü, tekrar doldurma

            # "⏳ Yükleniyor..." dummy'sini temizle, gerçek içeriği koy
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)

            self._tree_doldur(values[0], item)
            self.dosya_tree.item(item, values=(values[0], "directory", "expanded"))
        except Exception:
            pass
    def _istatistik_goster(self, event=None):
        """Kod istatistiklerini göster"""
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.split('\n')
        
        toplam_satir = len(satirlar)
        bos_satir = sum(1 for s in satirlar if not s.strip())
        yorum_satir = sum(1 for s in satirlar if s.strip().startswith('#'))
        kod_satir = toplam_satir - bos_satir - yorum_satir
        karakter = len(kod)
        karakter_bosluksuz = len(kod.replace(' ', '').replace('\n', '').replace('\t', ''))
        
        import re
        fonksiyon_sayisi = len(re.findall(r'\bfonksiyon\s+\w+', kod))
        sinif_sayisi = len(re.findall(r'\bsinif\s+\w+', kod))
        degisken_sayisi = len(set(re.findall(r'^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=', kod, re.MULTILINE)))
        
        mesaj = f"""📊 Kod İstatistikleri

    Toplam Satır: {toplam_satir}
      ├─ Kod Satırı: {kod_satir}
      ├─ Yorum Satırı: {yorum_satir}
      └─ Boş Satır: {bos_satir}

    Karakter: {karakter} (boşluksuz: {karakter_bosluksuz})

    Fonksiyon: {fonksiyon_sayisi}
    Sınıf: {sinif_sayisi}
    Değişken: {degisken_sayisi}"""
        
        messagebox.showinfo("Kod İstatistikleri", mesaj)
    # ============ SEKME ŞERİDİ YÖNETİMİ ============
    def _sekme_wheel(self, event):
        self._sekme_kaydir(120 if event.delta > 0 else -120)
        return "break"

    def _sekme_kaydir(self, delta):
        gorunur = self.tab_strip.winfo_width()
        icerik = self.sekmeler_container.winfo_width()
        min_offset = min(0, gorunur - icerik)
        self._sekme_offset = max(min_offset, min(0, self._sekme_offset + delta))
        self.sekmeler_container.place_configure(x=self._sekme_offset)
        self._sekme_ok_guncelle()

    def _sekme_ok_guncelle(self):
        gorunur = self.tab_strip.winfo_width()
        icerik = self.sekmeler_container.winfo_width()
        if icerik > gorunur - 4:
            self.tab_left_btn.grid(row=0, column=1, sticky="ns")
            self.tab_right_btn.grid(row=0, column=2, sticky="ns")
        else:
            self.tab_left_btn.grid_remove()
            self.tab_right_btn.grid_remove()
            self._sekme_offset = 0
            self.sekmeler_container.place_configure(x=0)

    def _sekme_layout_guncelle(self):
        """Chrome gibi: sekme sayısına göre genişlik hesapla"""
        gorunur = self.tab_strip.winfo_width()
        n = len(self.sekmeler)
        
        # Sekme kalmadıysa bölme hatasını önlemek için konteyneri sıfırla ve çık
        if n == 0:
            self.sekmeler_container.configure(width=0)
            self._sekme_ok_guncelle()
            return

        if gorunur < 50:
            # Pencere henüz haritalanmadı; biraz sonra tekrar dene
            try:
                self.after(50, self._sekme_layout_guncelle)
            except Exception:
                pass
            return
            
        min_w, max_w = 90, 170
        genislik = min(max_w, max(min_w, (gorunur - 8) // n))
        self._sekme_genisligi = genislik
        
        for s in self.sekmeler:
            s["frame"].configure(width=genislik)
            self._sekme_etiket_kirp(s, genislik)
            
        self.sekmeler_container.configure(width=n * (genislik + 2) + 4)
        self._sekme_ok_guncelle()

    def _sekme_etiket_kirp(self, sekme, genislik):
        isim = sekme["isim"]
        if sekme["degisti"]:
            isim += " ●"
        max_karakter = max(4, (genislik - 46) // 7)
        if len(isim) > max_karakter:
            isim = isim[:max_karakter - 1] + "…"
        sekme["label"].configure(text=isim)
    def _todo_panel_ac(self):
        """TODO/FIXME/HACK yorumlarını listeleyen panel aç"""
        if hasattr(self, '_todo_pencere') and self._todo_pencere.winfo_exists():
            self._todo_pencere.lift()
            return
        
        pencere = ctk.CTkToplevel(self)
        pencere.title("TODO Listesi")
        pencere.geometry("500x400")
        pencere.transient(self)
        self._todo_pencere = pencere
        
        # Başlık
        ctk.CTkLabel(pencere, text="📝 Kod İçi Notlar", font=("Segoe UI", 14, "bold"),
                     text_color=self.colors["text"]).pack(pady=10)
        
        # Liste çerçevesi
        liste_frame = ctk.CTkScrollableFrame(pencere, fg_color="transparent")
        liste_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        import re
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.split('\n')
        
        todo_bulundu = False
        for i, satir in enumerate(satirlar, 1):
            # TODO, FIXME, HACK, XXX, BUG ara
            match = re.search(r'#.*?(TODO|FIXME|HACK|XXX|BUG)[\s:]*(.*)', satir, re.IGNORECASE)
            if match:
                todo_bulundu = True
                tip = match.group(1).upper()
                aciklama = match.group(2).strip() or "(açıklama yok)"
                
                # Renk
                renk = {"TODO": "#4caf50", "FIXME": "#ff9800", "HACK": "#f44336", 
                        "XXX": "#9c27b0", "BUG": "#e91e63"}.get(tip, "#888")
                
                frame = ctk.CTkFrame(liste_frame, fg_color=self.colors["sidebar"], corner_radius=6)
                frame.pack(fill="x", pady=2)
                
                ctk.CTkLabel(frame, text=f"{tip}", font=("Segoe UI", 9, "bold"),
                             text_color=renk, width=60).pack(side="left", padx=8)
                ctk.CTkLabel(frame, text=f"Satır {i}:", font=("Segoe UI", 9),
                             text_color="#888", width=50).pack(side="left")
                ctk.CTkLabel(frame, text=aciklama[:50], font=("Segoe UI", 10),
                             text_color=self.colors["text"]).pack(side="left", padx=5)
                
                # Tıklayınca o satıra git
                def git(satir_no=i):
                    self.kod_alani.see(f"{satir_no}.0")
                    self.kod_alani.mark_set("insert", f"{satir_no}.0")
                    self.kod_alani.tag_remove("sel", "1.0", "end")
                    self.kod_alani.tag_add("sel", f"{satir_no}.0", f"{satir_no}.end")
                
                ctk.CTkButton(frame, text="Git", width=40, height=20,
                              fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                              font=("Segoe UI", 9), command=git).pack(side="right", padx=5)
        
        if not todo_bulundu:
            ctk.CTkLabel(liste_frame, text="Hiç TODO/FIXME/HACK/XXX/BUG bulunamadı.",
                         font=("Segoe UI", 11), text_color="#666").pack(pady=20)
    def _fold_bolgeleri_bul(self):
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.split("\n")

        bolgeler = []
        yigin = []

        blok_deseni = re.compile(
            r"^(fonksiyon|sinif|dongu|eger|degilse_eger|degilse|dene|hata_yakala|yakalama|sonunda)\b"
        )

        def kapat(bas_satir, bit_satir):
            if bit_satir <= bas_satir:
                return

            govde_var = False

            # bas_satir 1 tabanlı; gövde bas_satir+1 satırından başlar
            for s in satirlar[bas_satir:bit_satir]:
                if s.strip():
                    govde_var = True
                    break

            if govde_var:
                bolgeler.append((bas_satir, bit_satir))

        for i, satir in enumerate(satirlar, 1):
            bosluksuz = satir.lstrip()

            # Boş satırlarda fold göstergesi oluşturma
            if not bosluksuz:
                continue

            # Yorum satırlarını blok kapatma/açma için kullanma
            if bosluksuz.startswith("#"):
                continue

            indent = len(satir) - len(bosluksuz)

            # Mevcut satırın indent'i üstteki bloktan küçük veya eşitse blokları kapat
            while yigin and indent <= yigin[-1][1]:
                bas_satir, _ = yigin.pop()
                kapat(bas_satir, i - 1)

            if blok_deseni.match(bosluksuz):
                yigin.append((i, indent))

        son_satir = len(satirlar)

        while yigin:
            bas_satir, _ = yigin.pop()
            kapat(bas_satir, son_satir)

        return bolgeler
    def _fold_satir_numaralari_guncelle(self):
        try:
            self._satir_numaralarini_ciz()
        except Exception:
            pass
    def _fold_guncelle(self):
        editor = getattr(self.kod_alani, "_textbox", self.kod_alani)
        for tag in editor.tag_names():
            if tag.startswith("fold_"):
                editor.tag_delete(tag)
        self.fold_regions = {}
        self.fold_indicators = {}
        eski_states = getattr(self, "fold_states", {})
        self.fold_states = {}
        if not self.ayarlar.get("satir_numaralari"):
            self._satir_numaralarini_ciz()
            return
        for bas, bit in self._fold_bolgeleri_bul():
            if bit <= bas:
                continue
            tag_adi = f"fold_{bas}"
            editor.tag_add(tag_adi, f"{bas}.end", f"{bit}.end")
            folded = eski_states.get(bas, False)
            self.fold_states[bas] = folded
            self.fold_regions[bas] = (bas, bit)
            self.fold_indicators[bas] = "▶" if folded else "▼"
            editor.tag_config(tag_adi, elide=folded)
        self._satir_numaralarini_ciz()
    def _gizli_satirlar(self):
        """Katlanmış bölgelerde editörde görünmeyen satır numaraları"""
        gizli = set()
        for bas, (b0, b1) in getattr(self, "fold_regions", {}).items():
            if self.fold_states.get(bas):
                gizli.update(range(b0 + 1, b1 + 1))
        return gizli
    def _fold_tikla(self, event=None):
        try:
            satir, sutun = self._gutter_rakamini_oku(event)
            if satir is None:
                return None
            if satir not in getattr(self, "fold_indicators", {}):
                return None
            if sutun > 1:
                return None                   # rakama tıklandı → breakpoint'e düşsün
            editor = getattr(self.kod_alani, "_textbox", self.kod_alani)
            tag_adi = f"fold_{satir}"
            if tag_adi not in editor.tag_names():
                return None
            if self.fold_indicators[satir] == "▼":
                self.fold_indicators[satir] = "▶"
                self.fold_states[satir] = True
                editor.tag_config(tag_adi, elide=True)
            else:
                self.fold_indicators[satir] = "▼"
                self.fold_states[satir] = False
                editor.tag_config(tag_adi, elide=False)
            self._satir_numaralarini_ciz()
            self._senkronize_scroll()
            return "break"
        except Exception:
            return None

    def _sidebar_grip_basla(self, event):
        self._sg_baslangic_x = event.x_root
        self._sg_baslangic_w = self.sidebar.winfo_width()
        self._grip_aktif = True

    def _sidebar_grip_surukle(self, event):
        if not self._grip_aktif:
            return
        delta = event.x_root - self._sg_baslangic_x
        yeni = max(150, min(450, self._sg_baslangic_w + delta))
        
        x_pos = yeni + self.sidebar.winfo_x()
        self._ghost_line.place(x=x_pos, y=0, relheight=1.0)
        self._ghost_line.lift()
        self._ghost_line_w = yeni  

    def _sidebar_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line.place_forget()
        
        yeni = getattr(self, '_ghost_line_w', self.sidebar.winfo_width())
        self.grid_columnconfigure(1, minsize=int(yeni))
        self.update_idletasks()

    def _ai_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line.place_forget()
        
        yeni = getattr(self, '_ghost_line_w', self.ai_panel.winfo_width())
        self.grid_columnconfigure(5, minsize=int(yeni))
        self.update_idletasks()

    def _ai_grip_basla(self, event):
        self._ag_baslangic_x = event.x_root
        self._ag_baslangic_w = self.ai_panel.winfo_width()
        self._grip_aktif = True

    def _ai_grip_surukle(self, event):
        if not self._grip_aktif:
            return
        delta = self._ag_baslangic_x - event.x_root
        yeni = max(320, min(800, self._ag_baslangic_w + delta))
        
        x_pos = self.winfo_width() - yeni
        self._ghost_line.place(x=x_pos, y=0, relheight=1.0)
        self._ghost_line.lift()
        self._ghost_line_w = yeni

    def _grip_olustur(self):
        self._ghost_line = tk.Frame(self, bg="#007acc", width=2)
        self._ghost_line.place_forget()
        self._grip_aktif = False
        
        self.sidebar_grip = ctk.CTkFrame(self, width=4, fg_color="#3c3c3c")
        self.sidebar_grip.grid(row=0, column=2, rowspan=5, sticky="ns")
        self.sidebar_grip.configure(cursor="sb_h_double_arrow")
        
        self.sidebar_grip.bind("<Button-1>", self._sidebar_grip_basla)
        self.sidebar_grip.bind("<B1-Motion>", self._sidebar_grip_surukle)
        self.sidebar_grip.bind("<ButtonRelease-1>", self._sidebar_grip_birak)
        self.sidebar_grip.bind("<Enter>", lambda e: self.sidebar_grip.configure(fg_color="#007acc"))
        self.sidebar_grip.bind("<Leave>", lambda e: self.sidebar_grip.configure(fg_color="#3c3c3c"))
        
        self.ai_grip = ctk.CTkFrame(self, width=4, fg_color="#3c3c3c")
        self.ai_grip.grid(row=0, column=4, rowspan=5, sticky="ns")
        self.ai_grip.configure(cursor="sb_h_double_arrow")
        
        self.ai_grip.bind("<Button-1>", self._ai_grip_basla)
        self.ai_grip.bind("<B1-Motion>", self._ai_grip_surukle)
        self.ai_grip.bind("<ButtonRelease-1>", self._ai_grip_birak)
        self.ai_grip.bind("<Enter>", lambda e: self.ai_grip.configure(fg_color="#007acc"))
        self.ai_grip.bind("<Leave>", lambda e: self.ai_grip.configure(fg_color="#3c3c3c"))

        self._ghost_line_y = tk.Frame(self, bg="#007acc", height=2)
        self._ghost_line_y.place_forget()

        self.terminal_grip = ctk.CTkFrame(self, height=5, fg_color="#3c3c3c")
        self.terminal_grip.configure(cursor="sb_v_double_arrow")
        self.terminal_grip.bind("<Button-1>", self._terminal_grip_basla)
        self.terminal_grip.bind("<B1-Motion>", self._terminal_grip_surukle)
        self.terminal_grip.bind("<ButtonRelease-1>", self._terminal_grip_birak)
        self.terminal_grip.bind("<Enter>", lambda e: self.terminal_grip.configure(fg_color="#007acc"))
        self.terminal_grip.bind("<Leave>", lambda e: self.terminal_grip.configure(fg_color="#3c3c3c"))

    def _ai_input_focus(self, event=None):
        if self.ai_input.get("1.0", "end-1c").strip() == "Bir şey sor...":
            self.ai_input.delete("1.0", "end")

    def _ai_input_blur(self, event=None):
        if not self.ai_input.get("1.0", "end-1c").strip():
            self.ai_input.insert("1.0", "Bir şey sor...")

    def renk_ayarlarini_yap(self):
        for tag in ["keyword", "builtin", "string", "comment", "number"]:
            self.kod_alani.tag_config(tag, foreground=self.colors.get(tag, "#d4d4d4"))
        self.kod_alani.tag_config("fstring", foreground="#ce9178")

        # ODAK KAYBINDA SEÇİMİN SİLİNMEMESİ İÇİN
        tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        tb.configure(
            exportselection=False,
            selectbackground=self.colors["selection"],
            selectforeground=self.colors["text"],
            inactiveselectbackground=self.colors["selection"],
        )
    def _line_numbers_scroll(self, event):
        kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
            kod_tb.yview_scroll(-3, "units")
        else:
            kod_tb.yview_scroll(3, "units")
        self._senkronize_scroll()
        return "break"
    def _senkronize_scroll(self, event=None):
        if event and getattr(event, "state", 0) & 0x0004:
            return None
        try:
            kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
            first, last = kod_tb.yview()
            if self.ayarlar.get("satir_numaralari"):
                getattr(self.line_numbers, "_textbox", self.line_numbers).yview_moveto(first)
            if hasattr(self, "minimap") and self.ayarlar.get("minimap"):
                getattr(self.minimap, "_textbox", self.minimap).yview_moveto(first)
        except Exception:
            pass

    def _baglayicilari_ayarla(self):
        txt = getattr(self.kod_alani, "_textbox", self.kod_alani)
        ctk_sb = getattr(self.kod_alani, "_y_scrollbar", None)

        def _editor_yscroll(*args):
            if ctk_sb is not None:
                try:
                    ctk_sb.set(*args)
                except Exception:
                    pass
            self._senkronize_scroll()
        
        txt.configure(yscrollcommand=_editor_yscroll)
        ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
        def _guvenli_undo(event=None):
            try:
                self.kod_alani.edit_undo()
            except Exception:
                pass
            return "break"

        txt.bind("<Control-Z>", _guvenli_undo)
        txt.bind("<Control-z>", _guvenli_undo)
        def _guvenli_redo(event=None):
            try:
                self.kod_alani.edit_redo()
            except Exception:
                pass
            return "break"

        txt.bind("<Control-Y>", _guvenli_redo)
        txt.bind("<Control-y>", _guvenli_redo)
        txt.bind("<Control-S>", lambda e: self.dosya_kaydet())
        txt.bind("<Control-t>", lambda e: self._yeni_sekme_olustur())
        txt.bind("<Control-T>", lambda e: self._yeni_sekme_olustur())
        txt.bind("<Control-Shift-V>", self._alta_yapistir)
        txt.bind("<Control-F>", self._bul_penceresi_ac)
        txt.bind("<Control-O>", lambda e: self.dosya_ac())
        txt.bind("<Control-R>", lambda e: self.kodu_calistir())
        txt.bind("<KeyRelease>", self.on_key_release)
        txt.bind("<Tab>", self._tab_indent)
        txt.bind("<Shift-ISO_Left_Tab>", self._shift_tab_outdent)
        txt.bind("<Shift-Tab>", self._shift_tab_outdent)
        txt.bind("<Return>", self.on_return_key)
        txt.bind("<Down>", self.on_arrow_down)
        txt.bind("<Control-j>", self._terminal_toggle)
        txt.bind("<Up>", self.on_arrow_up)
        txt.bind("<Escape>", lambda e: self.popup_kapat())
        txt.bind("<FocusOut>", lambda e: self.popup_kapat())
        txt.bind("<Button-1>", lambda e: self.popup_kapat(), add="+")
        txt.bind("<Key>", lambda e: self.after_idle(self.sync_line_numbers), add="+")
        txt.bind("<ButtonRelease>", lambda e: self.after_idle(self.sync_line_numbers))
        txt.bind("<Control-s>", lambda e: self.dosya_kaydet())
        txt.bind("<Control-o>", lambda e: self.dosya_ac())
        txt.bind("<Control-r>", lambda e: self.kodu_calistir())
        txt.bind("<F5>", lambda e: self.debugger.devam_et() if getattr(self.debugger, 'calistiriliyor', False) else self.kodu_calistir())
        txt.bind("<Key>", self._dosya_degisti_kontrol, add="+")
        txt.bind("<MouseWheel>", self._senkronize_scroll)
        txt.bind("<Button-4>", self._senkronize_scroll)
        txt.bind("<Button-5>", self._senkronize_scroll)
        
        # Parantez/braket otomatik kapatma
        txt.bind("<Key>", self._parantez_kapat, add="+")
        
        # Seçili metni tırnak içine al
        txt.bind("<Control-quotedbl>", self._seciliyi_tirnak_icine_al)
        
        # Alt satıra yapıştır
        txt.bind("<Control-v>", None)
        
        # Font büyüt/küçült
        txt.bind("<Control-plus>", self._font_buyut)
        txt.bind("<Control-minus>", self._font_kucult)
        txt.bind("<Control-KP_Add>", self._font_buyut)
        txt.bind("<Control-KP_Subtract>", self._font_kucult)
        
        # Yorum satırı
        txt.bind("<Control-slash>", self._yorum_toggle)
        
        # Bul/Değiştir
        txt.bind("<Control-f>", self._bul_penceresi_ac)
        txt.bind("<Control-h>", lambda e: self._bul_penceresi_ac(e, degistir=True))
        
        # Satır çoğaltma
        txt.bind("<Control-Shift-D>", self._satir_cogalt)
        
        # Boş satır ekleme
        txt.bind("<Control-Return>", self._bos_satir_ekle_alt)      # ← Düzelt
        txt.bind("<Control-Shift-Return>", self._bos_satir_ekle_ust) # ← Düzelt
        
        # Satır taşıma
        txt.bind("<Alt-Up>", self._satir_yukari_tasi)
        txt.bind("<Alt-Down>", self._satir_asagi_tasi)
        
        # Komut paleti
        txt.bind("<Control-Shift-P>", self._komut_paleti_ac)
        
        # Debugger
        ln.bind("<Button-1>", self._line_number_click)
        txt.bind("<F9>", lambda e: self.debugger.baslat())
        txt.bind("<F10>", lambda e: self.debugger.adim())
        
        if self.ayarlar.get("satir_numaralari"):
            ln.bind("<MouseWheel>", self._line_numbers_scroll)
            ln.bind("<Button-4>", self._line_numbers_scroll)
            ln.bind("<Button-5>", self._line_numbers_scroll)
        
        if self.ayarlar.get("minimap") and hasattr(self, 'minimap'):
            self.minimap.bind("<MouseWheel>", lambda e: self._senkronize_scroll())
            self.minimap.bind("<Button-4>", lambda e: self._senkronize_scroll())
            self.minimap.bind("<Button-5>", lambda e: self._senkronize_scroll())
        # Ctrl + " ile seçili metni tırnak içine alma
        txt.bind("<Key>", self._ctrl_shift_tirnak_kontrol, add="+")

        # Ctrl + tekerlek ile font zoom
        txt.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
        txt.bind("<Control-Button-4>", self._zoom_in_event, add="+")
        txt.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        ln.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
        ln.bind("<Control-Button-4>", self._zoom_in_event, add="+")
        ln.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        if hasattr(self, "minimap") and self.minimap is not None:
            mm = getattr(self.minimap, "_textbox", self.minimap)

            # Minimap tıklama
            mm.bind("<ButtonRelease-1>", self._minimap_tikla, add="+")

            # Minimap üzerinde Ctrl + tekerlek zoom
            mm.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
            mm.bind("<Control-Button-4>", self._zoom_in_event, add="+")
            mm.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        self.popup = None
        self.listbox = None
    def _line_number_click(self, event=None):
        try:
            if self._fold_tikla(event) == "break":
                return "break"
        except Exception:
            pass

        self._breakpoint_toggle(event)
        return "break"

    def _ctrl_shift_tirnak_kontrol(self, event=None):
        if not event:
            return None

        state = getattr(event, "state", 0)

        # Ctrl basılı değilse işlem yapma
        if not (state & 0x0004):
            return None

        keysym = str(getattr(event, "keysym", "")).lower()
        char = getattr(event, "char", "")

        if keysym == "quotedbl" or char == '"':
            return self._seciliyi_tirnak_icine_al(event)

        return None

    def _zoom_mousewheel(self, event=None):
        if getattr(event, "delta", 0) > 0:
            self._font_buyut()
        else:
            self._font_kucult()
        return "break"

    def _zoom_in_event(self, event=None):
        self._font_buyut()
        return "break"

    def _zoom_out_event(self, event=None):
        self._font_kucult()
        return "break"
    def _minimap_tikla(self, event=None):
        try:
            if not hasattr(self, "minimap") or not self.minimap.winfo_exists():
                return None

            mm = getattr(self.minimap, "_textbox", self.minimap)
            hedef = mm.index(f"@{event.x},{event.y}")
            hedef_satir = int(hedef.split(".")[0])

            self.kod_alani.see(f"{hedef_satir}.0")
            self.kod_alani.mark_set("insert", f"{hedef_satir}.0")
            self.kod_alani.focus_set()

            return "break"
        except Exception:
            return None
    def _breakpoint_toggle(self, event=None):
        try:
            satir, _ = self._gutter_rakamini_oku(event)
            if satir is None:
                return
            self.debugger.breakpoint_toggle(satir)
        except Exception:
            pass
    def _satir_yukari_tasi(self, event=None):
        try:
            imlec = self.kod_alani.index("insert")
            satir, sutun = imlec.split(".")
            satir = int(satir)
            sutun = int(sutun)

            if satir <= 1:
                return "break"

            mevcut = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            ust = self.kod_alani.get(f"{satir - 1}.0", f"{satir - 1}.end")

            self.kod_alani.delete(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.0", ust)

            self.kod_alani.delete(f"{satir - 1}.0", f"{satir - 1}.end")
            self.kod_alani.insert(f"{satir - 1}.0", mevcut)

            self.kod_alani.mark_set("insert", f"{satir - 1}.{sutun}")

            self._dosya_degisti_kontrol()
            self.sync_line_numbers()
            self.kod_renklendir()

            return "break"
        except Exception:
            return None
    def _komut_paleti_ac(self, event=None):
        """Ctrl+Shift+P ile komut paleti aç"""
        if hasattr(self, '_palet_pencere') and self._palet_pencere.winfo_exists():
            self._palet_pencere.lift()
            self._palet_entry.focus()
            return "break"
        
        pencere = ctk.CTkToplevel(self)
        pencere.title("Komut Paleti")
        pencere.geometry("500x400")
        pencere.transient(self)
        pencere.resizable(False, False)
        self._palet_pencere = pencere
        
        # Komut listesi
        self.komutlar = [
            ("Dosya: Yeni Sekme", self._yeni_sekme_olustur, "Ctrl+T"),
            ("Dosya: Aç", self.dosya_ac, "Ctrl+O"),
            ("Dosya: Kaydet", self.dosya_kaydet, "Ctrl+S"),
            ("Kod: Çalıştır", self.kodu_calistir, "Ctrl+R / F5"),
            ("Kod: Yorum Satırı Aç/Kapat", self._yorum_toggle, "Ctrl+/"),
            ("Kod: Satırı Yukarı Taşı", self._satir_yukari_tasi, "Alt+↑"),
            ("Kod: Satırı Aşağı Taşı", self._satir_asagi_tasi, "Alt+↓"),
            ("Kod: Satırı Çoğalt", self._satir_cogalt, "Ctrl+Shift+D"),
            ("Editör: Bul", lambda: self._bul_penceresi_ac(degistir=False), "Ctrl+F"),
            ("Editör: Değiştir", lambda: self._bul_penceresi_ac(degistir=True), "Ctrl+H"),
            ("Editör: Font Büyüt", self._font_buyut, "Ctrl++"),
            ("Editör: Font Küçült", self._font_kucult, "Ctrl+-"),
            ("AI: Kodu Düzelt", self._ai_kodu_duzelt, ""),
            ("AI: Kodu Açıkla", self._ai_kodu_acikla, ""),
            ("AI: Kodu Optimize Et", self._ai_kodu_optimize, ""),
            ("Görünüm: Gezgin Aç/Kapat", self._gezgin_ac, ""),
            ("Görünüm: AI Panel Aç/Kapat", self._ai_panel_toggle, ""),
            ("Ayarlar: Pencere Aç", self._ayarlar_penceresi_ac, ""),
            ("Görünüm: Terminal Aç/Kapat", self._terminal_toggle, "Ctrl+J"),
            ("Kod: TürKod ⇄ Python Çevir", self._kodu_cevir, ""),
        ]
        
        # Arama kutusu
        self._palet_entry = ctk.CTkEntry(pencere, font=("Segoe UI", 12), height=35)
        self._palet_entry.pack(fill="x", padx=10, pady=10)
        self._palet_entry.focus()
        
        # Sonuç listesi
        self._palet_liste = tk.Listbox(
            pencere, 
            bg=self.colors["sidebar"],
            fg=self.colors["text"],
            selectbackground=self.colors.get("selection", "#264f78"),
            font=("Segoe UI", 11),
            bd=0, highlightthickness=0
        )
        self._palet_liste.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        def _palet_filtrele(*args):
            arama = self._palet_entry.get().lower()
            self._palet_liste.delete(0, tk.END)
            for isim, cmd, kisa in self.komutlar:
                if arama in isim.lower():
                    self._palet_liste.insert(tk.END, f"{isim}  ({kisa})" if kisa else isim)
        
        def _palet_calistir(event=None):
            secili = self._palet_liste.curselection()
            if not secili:
                return
            metin = self._palet_liste.get(secili[0]).split("  (")[0]
            for isim, cmd, kisa in self.komutlar:
                if isim == metin:
                    pencere.destroy()
                    cmd()
                    break
        
        self._palet_entry.bind("<KeyRelease>", _palet_filtrele)
        self._palet_liste.bind("<Double-Button-1>", _palet_calistir)
        self._palet_liste.bind("<Return>", _palet_calistir)
        self._palet_entry.bind("<Return>", _palet_calistir)
        self._palet_entry.bind("<Down>", lambda e: self._palet_liste.focus() or self._palet_liste.select_set(0))
        
        # İlk listeyi doldur
        _palet_filtrele()
        
        return "break"
    def _satir_asagi_tasi(self, event=None):
        try:
            imlec = self.kod_alani.index("insert")
            satir, sutun = imlec.split(".")
            satir = int(satir)
            sutun = int(sutun)

            son_satir = int(self.kod_alani.index("end-1c").split(".")[0])

            if satir >= son_satir:
                return "break"

            mevcut = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            alt = self.kod_alani.get(f"{satir + 1}.0", f"{satir + 1}.end")

            self.kod_alani.delete(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.0", alt)

            self.kod_alani.delete(f"{satir + 1}.0", f"{satir + 1}.end")
            self.kod_alani.insert(f"{satir + 1}.0", mevcut)

            self.kod_alani.mark_set("insert", f"{satir + 1}.{sutun}")

            self._dosya_degisti_kontrol()
            self.sync_line_numbers()
            self.kod_renklendir()

            return "break"
        except Exception:
            return None
    def _bos_satir_ekle_alt(self, event=None):
        """Ctrl+Enter → İmleç hareket etmeden alt satıra boş satır ekle"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            self.kod_alani.insert(f"{satir}.end", "\n")
            self.sync_line_numbers()
            return "break"
        except Exception:
            pass
        return None

    def _bos_satir_ekle_ust(self, event=None):
        """Ctrl+Shift+Enter → İmleç hareket etmeden üst satıra boş satır ekle"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            self.kod_alani.insert(f"{satir}.0", "\n")
            self.sync_line_numbers()
            return "break"
        except Exception:
            pass
        return None
    def _satir_cogalt(self, event=None):
        """Ctrl+Shift+D ile mevcut satırı altına kopyala"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            satir_metni = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.end", f"\n{satir_metni}")
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            pass
        return None
    def _bul_penceresi_ac(self, event=None, degistir=False):
        # Panel açıksa: aynı modsa öne getir, farklı modsa yeniden kur
        if hasattr(self, '_bul_pencere') and self._bul_pencere.winfo_exists():
            if getattr(self, '_bul_modu', None) == degistir:
                self._bul_pencere.lift()
                return "break"
            self._bul_pencere.destroy()

        pencere = ctk.CTkToplevel(self)
        pencere.title("Değiştir" if degistir else "Bul")
        pencere.geometry("400x160" if degistir else "400x100")
        pencere.transient(self)
        pencere.resizable(False, False)
        self._bul_pencere = pencere
        self._bul_modu = degistir

        def _kapat():
            self.kod_alani.tag_remove("sel", "1.0", "end")
            pencere.destroy()

        pencere.protocol("WM_DELETE_WINDOW", _kapat)
        pencere.bind("<Escape>", lambda e: _kapat())

        # Bul satırı
        ctk.CTkLabel(pencere, text="Bul:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=10, pady=8, sticky="e")
        bul_var = ctk.StringVar()
        bul_entry = ctk.CTkEntry(pencere, textvariable=bul_var, width=280)
        bul_entry.grid(row=0, column=1, padx=5, pady=8, sticky="w")
        bul_entry.focus()

        # Değiştir satırı (SADECE Ctrl+H)
        degis_var = ctk.StringVar()
        degis_entry = None
        if degistir:
            ctk.CTkLabel(pencere, text="Değiştir:", font=("Segoe UI", 11)).grid(row=1, column=0, padx=10, pady=5, sticky="e")
            degis_entry = ctk.CTkEntry(pencere, textvariable=degis_var, width=280)
            degis_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        def bul_sonraki():
            aranan = bul_var.get()
            if not aranan:
                return
            bas = self.kod_alani.index("insert")
            pos = self.kod_alani.search(aranan, bas, stopindex="end")
            if not pos:
                pos = self.kod_alani.search(aranan, "1.0", stopindex=bas)
            if pos:
                bit = f"{pos}+{len(aranan)}c"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", pos, bit)
                self.kod_alani.mark_set("insert", bit)
                self.kod_alani.see(pos)

        def secili_degistir():
            aranan = bul_var.get()
            degisen = degis_var.get()
            if not aranan:
                return
            if self.kod_alani.tag_ranges("sel"):
                secili = self.kod_alani.get("sel.first", "sel.last")
                if secili == aranan:
                    self.kod_alani.delete("sel.first", "sel.last")
                    self.kod_alani.insert("insert", degisen)
            bul_sonraki()

        def tumunu_degistir():
            aranan = bul_var.get()
            degisen = degis_var.get()
            if not aranan:
                return
            icerik = self.kod_alani.get("1.0", "end-1c")
            self.kod_alani.delete("1.0", "end")
            self.kod_alani.insert("1.0", icerik.replace(aranan, degisen))
            self.sync_line_numbers()
            self.kod_renklendir()

        btn_frame = ctk.CTkFrame(pencere, fg_color="transparent")
        btn_frame.grid(row=2 if degistir else 1, column=0, columnspan=2, pady=10)

        ctk.CTkButton(btn_frame, text="Sonraki", width=80, command=bul_sonraki,
            fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"]).pack(side="left", padx=3)

        # Değiştir butonları SADECE degistir=True ise (Ctrl+H)
        if degistir:
            ctk.CTkButton(btn_frame, text="Değiştir", width=80, command=secili_degistir,
                fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"]).pack(side="left", padx=3)
            ctk.CTkButton(btn_frame, text="Tümünü Değiştir", width=110, command=tumunu_degistir,
                fg_color="#c75450", hover_color="#a03030").pack(side="left", padx=3)

        ctk.CTkButton(btn_frame, text="Kapat", width=60, command=_kapat,
            fg_color="transparent", hover_color="#c75450").pack(side="left", padx=3)

        bul_entry.bind("<Return>", lambda e: bul_sonraki())
        if degistir and degis_entry is not None:
            degis_entry.bind("<Return>", lambda e: secili_degistir())

        return "break"
    def _yorum_toggle(self, event=None):
        """Ctrl+/ ile seçili satırları yorumla veya yorumdan çıkar"""
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
            else:
                satir = self.kod_alani.index("insert").split(".")[0]
                bas = f"{satir}.0"
                bit = f"{satir}.end"
            
            bas_satir = int(bas.split(".")[0])
            bit_satir = int(bit.split(".")[0])
            
            # Tüm satırlar yorumlu mu kontrol et
            hepsi_yorumlu = True
            for satir_no in range(bas_satir, bit_satir + 1):
                satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.end")
                if satir_metni.strip() and not satir_metni.strip().startswith("#"):
                    hepsi_yorumlu = False
                    break
            
            for satir_no in range(bas_satir, bit_satir + 1):
                satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.end")
                if hepsi_yorumlu:
                    # Yorumdan çıkar
                    if satir_metni.strip().startswith("# "):
                        yeni = satir_metni.replace("# ", "", 1)
                    elif satir_metni.strip().startswith("#"):
                        yeni = satir_metni.replace("#", "", 1)
                    else:
                        continue
                    self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.end")
                    self.kod_alani.insert(f"{satir_no}.0", yeni)
                else:
                    # Yorum yap
                    if satir_metni.strip():
                        self.kod_alani.insert(f"{satir_no}.0", "# ")
            
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            pass
        return None
    def _parantez_kapat(self, event=None):
        if not event or len(getattr(event, "char", "")) != 1:
            return None

        # Ctrl basılıysa özel kısayolları bozma
        if getattr(event, "state", 0) & 0x0004:
            return None
        
        acilis = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
        kapanis = {')', ']', '}', '"', "'"}
        
        # Kapanış karakteri yazıldıysa ve sağda aynısı varsa sadece sağa geç
        if event.char in kapanis:
            try:
                sag = self.kod_alani.get("insert", "insert+1c")
                if sag == event.char:
                    self.kod_alani.mark_set("insert", "insert+1c")
                    return "break"  # ← Ekle
            except:
                pass
            return None  # Normal karakter, default handler çalışsın
        
        if event.char not in acilis:
            return None
        
        kapat = acilis[event.char]
        
        try:
            if self.kod_alani.tag_ranges("sel"):
                secili = self.kod_alani.get("sel.first", "sel.last")
                self.kod_alani.delete("sel.first", "sel.last")
                self.kod_alani.insert("insert", f"{event.char}{secili}{kapat}")
                # Seçili metni tekrar seç (açılış ve kapanış hariç)
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", "insert-1c", f"insert-{len(kapat)}c")
                self.kod_alani.mark_set("insert", f"insert-{len(kapat)}c")
                return "break"  # ← Ekle
            else:
                self.kod_alani.insert("insert", f"{event.char}{kapat}")
                self.kod_alani.mark_set("insert", "insert-1c")
                return "break"  # ← Ekle
        except:
            return None
    def _alta_yapistir(self, event=None):
        """Ctrl+V ile panodaki metni yeni satıra yapıştırır"""
        try:
            icerik = self.clipboard_get()
            # İmleci satır sonuna götür, yeni satır aç, yapıştır
            satir = self.kod_alani.index("insert").split(".")[0]
            satir_sonu = f"{satir}.end"
            self.kod_alani.mark_set("insert", satir_sonu)
            self.kod_alani.insert("insert", "\n" + icerik)
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            # Normal yapıştırma davranışı (panoda metin yoksa vs.)
            return None
    def _font_buyut(self, event=None):
        """Ctrl++ → Font boyutunu 1 artır"""
        mevcut = self.ayarlar.get("yazi_boyutu")
        if mevcut < 32:
            yeni = mevcut + 1
            self.ayarlar.set("yazi_boyutu", yeni)
            self.kod_alani.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.line_numbers.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.status_left.configure(text=f"  Font boyutu: {yeni}px")
        return "break"

    def _font_kucult(self, event=None):
        """Ctrl+- → Font boyutunu 1 azalt"""
        mevcut = self.ayarlar.get("yazi_boyutu")
        if mevcut > 8:
            yeni = mevcut - 1
            self.ayarlar.set("yazi_boyutu", yeni)
            self.kod_alani.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.line_numbers.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.status_left.configure(text=f"  Font boyutu: {yeni}px")
        return "break"
    def _shift_tab_outdent(self, event=None):
        """Shift+Tab: Seçili satırları sola kaydır"""
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                bas_satir = int(bas.split(".")[0])
                bit_satir = int(bit.split(".")[0])
                
                for satir_no in range(bas_satir, bit_satir + 1):
                    satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.4")
                    if satir_metni.startswith("    "):
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.4")
                    elif satir_metni.startswith("  "):
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.2")
                    elif satir_metni.startswith(" "):
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.1")
                    elif satir_metni.startswith("\t"):
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.1")
                
                yeni_bas = f"{bas_satir}.0"
                yeni_bit = f"{bit_satir}.end"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", yeni_bas, yeni_bit)
                
                self.sync_line_numbers()
                return "break"
        except Exception:
            pass
        return None
    def _seciliyi_tirnak_icine_al(self, event=None):
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                secili = self.kod_alani.get(bas, bit)

                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, f'"{secili}"')

                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add(
                    "sel",
                    f"{bas}+1c",
                    f"{bas}+{len(secili) + 1}c"
                )
                self.kod_alani.mark_set("insert", f"{bas}+{len(secili) + 1}c")

                self._dosya_degisti_kontrol()
                self.sync_line_numbers()
                self.kod_renklendir()
                return "break"

            kelime, bas, bit = self.mevcut_kelimeyi_al()
            if kelime:
                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, f'"{kelime}"')
                self.kod_alani.mark_set("insert", f"{bas}+{len(kelime) + 1}c")

                self._dosya_degisti_kontrol()
                self.sync_line_numbers()
                self.kod_renklendir()
                return "break"

        except Exception:
            pass

        return None
    def _dosya_degisti_kontrol(self, event=None):
        if event is not None:
            # Sadece metni gerçekten değiştiren tuşlar
            if not event.char and event.keysym not in ("Return", "BackSpace", "Delete", "Tab"):
                return
        sekme = self._aktif_sekme()
        if sekme and not sekme["degisti"]:
            sekme["degisti"] = True
            self._sekme_baslik_guncelle()

    def _ornek_kod_yukle(self):
        ornek_kod = 'yazdir("Merhaba Dünya")'
        self._yeni_sekme_olustur(isim="main.trpy", icerik=ornek_kod)

    def _otomatik_kaydetme_baslat(self):
        def kontrol():
            while True:
                time.sleep(self.ayarlar.get("otomatik_kaydetme_aralik"))
                if self.ayarlar.get("otomatik_kaydetme"):
                    self.after(0, self._otomatik_kaydet)
        threading.Thread(target=kontrol, daemon=True).start()

    def _otomatik_kaydet(self):
        sekme = self._aktif_sekme()
        if sekme and sekme["yol"] and sekme["degisti"]:
            try:
                with open(sekme["yol"], "w", encoding="utf-8") as f:
                    f.write(self.kod_alani.get("1.0", "end"))
                sekme["degisti"] = False
                self._sekme_baslik_guncelle()
                self.status_left.configure(text=f"  Otomatik kaydedildi: {sekme['isim']}")
            except:
                pass

    # ============ DOSYA GEZGINI ============
    def _proje_ac(self):
        dizin = filedialog.askdirectory(title="Proje Dizini Sec",
                                         initialdir=self.proje_dizini)
        if dizin:
            self.proje_dizini = dizin
            self.ayarlar.set("son_proje_dizini", dizin)
            self._dosya_tree_guncelle()

    def _dosya_tree_guncelle(self):
        self.dosya_tree.delete(*self.dosya_tree.get_children())
        
        if not self.proje_dizini or not os.path.exists(self.proje_dizini):
            return

        proje_adi = os.path.basename(self.proje_dizini) or "Proje"
        root_node = self.dosya_tree.insert(
            "", "end", 
            text=f"📁 {proje_adi}", 
            values=(self.proje_dizini, "directory", "expanded"),
            open=True, 
            tags=("directory",)
        )
        
        self._tree_doldur(self.proje_dizini, root_node)

    def _tree_doldur(self, dizin, parent_node):
        try:
            with os.scandir(dizin) as entries:
                tum_girdiler = list(entries)
                
                MAX_OGE = 300
                fazla_mesaj = None
                
                if len(tum_girdiler) > MAX_OGE:
                    tum_girdiler = tum_girdiler[:MAX_OGE]
                    fazla_mesaj = f"... ({len(tum_girdiler) - MAX_OGE} öğe daha var)"
                
                klasorler = []
                dosyalar = []
                
                for entry in tum_girdiler:
                    if entry.name.startswith('.'):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        klasorler.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        dosyalar.append(entry)
                
                klasorler.sort(key=lambda e: e.name.lower())
                dosyalar.sort(key=lambda e: e.name.lower())

                for entry in klasorler:
                    tam_yol = entry.path
                    node = self.dosya_tree.insert(
                        parent_node, "end",
                        text=f"📁 {entry.name}",
                        values=(tam_yol, "directory", "collapsed"),
                        tags=("directory",)
                    )
                    self.dosya_tree.insert(node, "end", text="⏳ Yükleniyor...", 
                                           values=("", "dummy"), tags=("dummy",))

                for entry in dosyalar:
                    tam_yol = entry.path
                    uzanti = os.path.splitext(entry.name)[1].lower()
                    
                    if uzanti == ".trpy":
                        icon, tag = "📄", "trpy"
                    elif uzanti == ".py":
                        icon, tag = "🐍", "python"
                    else:
                        icon, tag = "📄", "other"

                    self.dosya_tree.insert(
                        parent_node, "end",
                        text=f"{icon} {entry.name}",
                        values=(tam_yol, "file"),
                        tags=(tag,)
                    )
                
                if fazla_mesaj:
                    self.dosya_tree.insert(
                        parent_node, "end",
                        text=fazla_mesaj,
                        values=("", "dummy"),
                        tags=("dummy",)
                    )
                    
        except PermissionError:
            pass
        except Exception as e:
            print(f"[TurKod] Ağaç doldurma hatası: {e}")

    def _tree_node_ac_kapat(self, event=None, item=None):
        if item is None:
            item = self.dosya_tree.selection()
            if not item:
                return
            item = item[0]

        values = self.dosya_tree.item(item, "values")
        if not values or len(values) < 2:
            return

        tam_yol, tip = values[0], values[1]

        if tip == "file":
            if os.path.exists(tam_yol):
                self._dosya_ac_yol(tam_yol)
            return

        if tip != "directory":
            return

        durum = values[2] if len(values) > 2 else "collapsed"

        if durum == "collapsed":
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)

            # Thread/after YOK: ana thread'de doğrudan doldur
            self._tree_doldur(tam_yol, item)
            self.dosya_tree.item(item, values=(tam_yol, "directory", "expanded"))
            self.dosya_tree.item(item, open=True)
        else:
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)
            self.dosya_tree.insert(item, "end", text="⏳ Yükleniyor...",
                                   values=("", "dummy"), tags=("dummy",))
            self.dosya_tree.item(item, values=(tam_yol, "directory", "collapsed"))
            self.dosya_tree.item(item, open=False)

    def _tree_tagleri_ayarla(self):
        if hasattr(self, '_tree_tags_ayarlandi'):
            return
        
        self.dosya_tree.tag_configure("directory", foreground="#569cd6")
        self.dosya_tree.tag_configure("trpy", foreground="#ce9178")
        self.dosya_tree.tag_configure("python", foreground="#dcdcaa")
        self.dosya_tree.tag_configure("other", foreground="#d4d4d4")
        self.dosya_tree.tag_configure("dummy", foreground="#666666", font=("Segoe UI", 9, "italic"))
        
        self._tree_tags_ayarlandi = True

    def _dosya_tree_cift_tik(self, event):
        item = self.dosya_tree.identify_row(event.y)
        if not item:
            return
        
        values = self.dosya_tree.item(item, "values")
        if not values:
            return
        
        tip = values[1] if len(values) > 1 else ""
        
        if tip == "directory":
            self._tree_node_ac_kapat(item=item)
        elif tip == "file":
            tam_yol = values[0]
            if os.path.exists(tam_yol):
                self._dosya_ac_yol(tam_yol)

    def _dosya_ac_yol(self, yol):
        self._yeni_sekme_olustur(yol=yol)

    def _gezgin_ac(self):
        if self.sidebar.winfo_viewable():
            self.sidebar.grid_remove()
            self.sidebar_grip.grid_remove()
            self.grid_columnconfigure(1, minsize=0)   
            self.explorer_btn.configure(text="▶")
        else:
            self.sidebar.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=(0, 0))
            self.sidebar_grip.grid(row=0, column=2, rowspan=5, sticky="ns")
            self.grid_columnconfigure(1, minsize=220)  
            self.explorer_btn.configure(text="◀")

    # ============ AI PANEL ============
    def _ai_kodu_acikla(self):
        kod = self.kod_alani.get("1.0", "end-1c").strip()

        if not kod:
            self._ai_mesaj_ekle("assistant", "⚠️ Açıklanacak kod bulunamadı.")
            return

        prompt = f"""Aşağıdaki TürKod kodunu satır satır açıkla ve ne yaptığını özetle:

    ```TürKod
    {kod}
    ```"""

        self._ai_gonder_prompt(prompt)
    def _ai_kodu_uygula(self, kod):
        # Kod zaten TürKod (program çevirdi), direkt uygula
        mevcut_kod = self.kod_alani.get("1.0", "end-1c").strip()
            
        if mevcut_kod:
            cevap = messagebox.askyesnocancel(
                "✏️ Kodu Uygula",
                "AI'in verdigi kod mevcut kodunuzun yerine gecsin mi?\n\n"
                "• Evet = Mevcut kodun ustune yaz\n"
                "• Hayir = Kodu imlecin oldugu yere ekle\n"
                "• Iptal = Hicbir sey yapma",
                icon='question'
            )
                
            if cevap is None:  
                return
            elif cevap is True:  
                self.kod_alani.delete("1.0", "end")
                self.kod_alani.insert("1.0", kod)
            else:  
                self.kod_alani.insert("insert", kod)
        else:
            self.kod_alani.delete("1.0", "end")
            self.kod_alani.insert("1.0", kod)
            
        self._dosya_degisti_kontrol()
        self.sync_line_numbers()
        self.kod_renklendir()
        self.status_left.configure(text="  AI kodu editor'e uygulandi ✓")

    def _yeni_sekme_olustur(self, yol=None, isim=None, icerik=None):
        self.sekme_id_sayac += 1
        sid = self.sekme_id_sayac

        if yol and os.path.exists(yol):
            isim = os.path.basename(yol)
            try:
                with open(yol, "r", encoding="utf-8") as f:
                    icerik = f.read()
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya okunamadı: {e}")
                icerik = ""
        else:
            isim = isim or f"Untitled-{sid}.trpy"
            icerik = icerik or ""
            yol = None

        frame = ctk.CTkFrame(self.sekmeler_container, width=170, height=34,
                             fg_color=self.colors["tab_inactive"],
                             border_color=self.colors["border"], border_width=1,
                             corner_radius=8)
        frame.pack(side="left", padx=(0, 2))
        frame.grid_propagate(False)
        frame.columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(frame, text=isim, font=("Segoe UI", 10, "bold"),
                           text_color=self.colors["text"], anchor="w")
        lbl.grid(row=0, column=0, sticky="w", padx=(10, 2), pady=5)

        kapat_btn = ctk.CTkButton(frame, text="×", width=18, height=18,
                                  fg_color="transparent", hover_color="#c75450",
                                  text_color=self.colors["text"],
                                  font=("Segoe UI", 12, "bold"),
                                  corner_radius=10,
                                  command=lambda id=sid: self._sekme_kapat(id))
        kapat_btn.grid(row=0, column=1, padx=(0, 5), pady=5)

        for widget in [frame, lbl]:
            widget.bind("<Button-1>", lambda e, id=sid: self._sekme_aktif_yap(id))
        for widget in (frame, lbl, kapat_btn):
            widget.bind("<MouseWheel>", self._sekme_wheel)
            widget.bind("<Button-4>", lambda e: self._sekme_kaydir(120))
            widget.bind("<Button-5>", lambda e: self._sekme_kaydir(-120))

        sekme = {
            "id": sid,
            "frame": frame,
            "label": lbl,
            "kapat_btn": kapat_btn,
            "isim": isim,
            "yol": yol,
            "icerik": icerik,
            "degisti": False
        }
        self.sekmeler.append(sekme)
        self._sekme_aktif_yap(sid)
        self._sekme_layout_guncelle()
        return sid

    def _sekme_bul(self, sid):
        for s in self.sekmeler:
            if s["id"] == sid:
                return s
        return None

    def _aktif_sekme(self):
        return self._sekme_bul(self.aktif_sekme_id)

    def _sekme_aktif_yap(self, sid):
        if self.aktif_sekme_id == sid:
            return

        if self.aktif_sekme_id is not None:
            eski = self._sekme_bul(self.aktif_sekme_id)
            if eski:
                eski["icerik"] = self.kod_alani.get("1.0", "end-1c")
                eski["frame"].configure(fg_color=self.colors["tab_inactive"])

        yeni = self._sekme_bul(sid)
        if not yeni:
            return

        self.aktif_sekme_id = sid
        self.kod_alani.delete("1.0", "end")
        self.kod_alani.insert("1.0", yeni["icerik"])

        yeni["frame"].configure(fg_color=self.colors["tab_active"])

        self.sync_line_numbers()
        self.after(150, self.kod_renklendir)
        self._status_guncelle()

    def _sekme_kapat(self, sid):
        sekme = self._sekme_bul(sid)
        if not sekme:
            return

        if self.aktif_sekme_id == sid:
            sekme["icerik"] = self.kod_alani.get("1.0", "end-1c")

        if sekme["degisti"]:
            cevap = messagebox.askyesnocancel("Kaydet?", f"'{sekme['isim']}' kaydedilsin mi?")
            if cevap is None:
                return
            if cevap:
                self._sekme_aktif_yap(sid)
                self.dosya_kaydet()

        sekme["frame"].destroy()
        self.sekmeler.remove(sekme)
        self._sekme_layout_guncelle()

        if self.sekmeler:
            self._sekme_aktif_yap(self.sekmeler[-1]["id"])
        else:
            self.aktif_sekme_id = None
            self.kod_alani.delete("1.0", "end")
            self._yeni_sekme_olustur()

    def _sekme_baslik_guncelle(self, sid=None):
        sekme = self._aktif_sekme() if sid is None else self._sekme_bul(sid)
        if not sekme:
            return
        self._sekme_etiket_kirp(sekme, getattr(self, "_sekme_genisligi", 170))

    def _status_guncelle(self):
        sekme = self._aktif_sekme()
        if sekme and sekme["yol"]:
            self.status_right.configure(text=f"UTF-8 | {sekme['isim']} ")
        else:
            self.status_right.configure(text="UTF-8 | Yeni Dosya ")

    def _ai_kod_kopyala(self, kod):
        self.clipboard_clear()
        self.clipboard_append(kod)
        self.status_left.configure(text="  Kod panoya kopyalandi ✓")

    def _ai_kod_bloju_olustur(self, parent, kod, dil=""):
        frame = ctk.CTkFrame(parent, fg_color=self.colors.get("bg", "#1e1e1e"), corner_radius=6,
                     border_width=1, border_color=self.colors["border"])
        
        bar = ctk.CTkFrame(frame, fg_color=self.colors.get("sidebar", "#252526"), height=32, corner_radius=0)
        bar.pack(fill="x", padx=0, pady=0)
        bar.pack_propagate(False)
            
        # ⬅️ YENİ: Her zaman "TÜRKOD" göster
        gosterilen_dil = "TÜRKOD" if not dil else dil.upper()
        
        dil_label = ctk.CTkLabel(bar, text=gosterilen_dil, 
                                     font=("Segoe UI", 8, "bold"), text_color="#858585")
        dil_label.pack(side="left", padx=8)
            
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.pack(side="right", padx=5)
            
        kopyala_btn = ctk.CTkButton(btn_frame, text="📋 Kopyala", width=70, height=20,
                                         fg_color="transparent", hover_color="#3c3c3c",
                                         font=("Segoe UI", 8), 
                                         command=lambda: self._ai_kod_kopyala(kod))
        kopyala_btn.pack(side="left", padx=2)
            
        uygula_btn = ctk.CTkButton(btn_frame, text="✏️ Uygula", width=70, height=20,
                                        fg_color="#0e639c", hover_color="#1177bb",
                                        font=("Segoe UI", 8, "bold"), 
                                        command=lambda: self._ai_kodu_uygula(kod))
        uygula_btn.pack(side="left", padx=2)
            
        satir_sayisi = kod.count('\n') + 1
        yukseklik = min(250, satir_sayisi * 18 + 20)  
            
        kod_text = ctk.CTkTextbox(frame, font=("Consolas", 11),
                          fg_color=self.colors.get("bg", "#1e1e1e"),
                          text_color=self.colors.get("text", "#d4d4d4"),
                          wrap="none", height=yukseklik)
        kod_text.pack(fill="x", padx=5, pady=5)
        kod_text.insert("1.0", kod)
        kod_text.configure(state="disabled") 
            
        return frame

    def _ai_mesaj_parse_et(self, mesaj):
        parcalar = []
        kalan = mesaj
        
        while True:
            match = re.search(r'```(\w*)\s*\n?(.*?)```', kalan, re.DOTALL)
            if not match:
                break
            
            baslangic, bitis = match.span()
            
            if baslangic > 0 and kalan[:baslangic].strip():
                parcalar.append(("metin", kalan[:baslangic].strip(), ""))
            
            dil = match.group(1).strip()
            kod = match.group(2).strip()
            
            # ⬅️ YENİ: Python kodunu TürKod'a çevir
            if dil.lower() == 'python':
                kod = python_kodu_turkceye_cevir(kod)
                dil = "TürKod"
            
            parcalar.append(("kod", kod, dil))
            
            kalan = kalan[bitis:]
        
        if kalan.strip():
            parcalar.append(("metin", kalan.strip(), ""))
        
        if not parcalar and mesaj.strip():
            parcalar.append(("metin", mesaj.strip(), ""))
        
        return parcalar

    def _ai_panel_toggle(self):
        if self.ai_panel_visible:
            self.ai_panel.grid_remove()
            self.ai_grip.grid_remove()
            self.grid_columnconfigure(5, minsize=0)   
            self.ai_panel_visible = False
            self.ai_toggle_btn.configure(text="◀")
        else:
            self.ai_panel.grid(row=0, column=5, rowspan=5, sticky="nsew")
            self.ai_grip.grid(row=0, column=4, rowspan=5, sticky="ns")
            self.grid_columnconfigure(5, minsize=480)  
            self.ai_panel_visible = True
            self.ai_toggle_btn.configure(text="▶")

    def _ai_mesaj_ekle(self, gonderen, mesaj):
        is_user = gonderen == "user"
        if not hasattr(self, 'ai_mesajlar'):
            self.ai_mesajlar = []
        
        row_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2, padx=4)

        msg_container = ctk.CTkFrame(row_frame, fg_color="transparent")
        msg_container.pack(side="right" if is_user else "left")

        avatar_text = "👤" if is_user else "🤖"
        avatar = ctk.CTkLabel(msg_container, text=avatar_text, font=("Segoe UI", 14))
        avatar.pack(side="left" if not is_user else "right", padx=4, anchor="n")
        
        if gonderen == "assistant":
            mesaj = self._python_bloklarini_turkceye_cevir(mesaj)
            
        bg_color = self.colors["ai_user"] if is_user else self.colors["ai_assistant"]
        bubble = ctk.CTkFrame(msg_container, fg_color=bg_color, corner_radius=14)
        bubble.pack(side="left" if not is_user else "right", padx=2)

        header = ctk.CTkFrame(bubble, fg_color="transparent", height=18)
        header.pack(fill="x", padx=(12, 12), pady=(6, 0))
        header.pack_propagate(False)
        
        name = "Sen" if is_user else "AI"
        ctk.CTkLabel(header, text=name, font=("Segoe UI", 9, "bold"),
                     text_color="#888").pack(side="left")
        ctk.CTkLabel(header, text=datetime.now().strftime("%H:%M"),
                     font=("Segoe UI", 8), text_color="#666").pack(side="right")

        parcalar = self._ai_mesaj_parse_et(mesaj)
        panel_genislik = self.ai_panel.winfo_width()
        if panel_genislik < 100:
            panel_genislik = 400  # Varsayılan değer
        wrap_length = max(200, panel_genislik - 80)
        for parca in parcalar:
            if parca[0] == "metin":
                text = parca[1]
                text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
                text = re.sub(r'\*(.*?)\*', r'\1', text)
                
                msg_lbl = ctk.CTkLabel(bubble, text=text,
                                        font=("Segoe UI", 11),
                                        text_color=self.colors["text"],
                                        wraplength=wrap_length, justify="left")
                msg_lbl.pack(anchor="w", padx=12, pady=(2, 6))
            else:
                kod_frame = self._ai_kod_bloju_olustur(bubble, parca[1], parca[2])
                kod_frame.pack(fill="x", padx=8, pady=(2, 8))

        self.ai_mesajlar.append({"gonderen": gonderen, "mesaj": mesaj})
        
        self.after(100, lambda: self.ai_chat_frame._parent_canvas.yview_moveto(1.0))
    

    def _python_bloklarini_turkceye_cevir(self, mesaj):
        """Mesajdaki ```python bloklarını ```TürKod'a çevir"""
        import re
        
        def cevir_blok(match):
            dil = match.group(1)
            kod = match.group(2)
            
            if dil.lower() == 'python':
                turkce_kod = python_kodu_turkceye_cevir(kod)
                return f'```TürKod\n{turkce_kod}\n```'
            
            return match.group(0)
        
        # ```dil\nkod\n``` patternini bul ve çevir
        return re.sub(r'```(\w+)\n?(.*?)```', cevir_blok, mesaj, flags=re.DOTALL)
    def _ai_yaziyor_goster(self):
        self.ai_durum.configure(text="● Yazıyor...", text_color="#ff9800")
        
        if not self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color=self.colors["ai_assistant"],
                                                 corner_radius=12, height=32)
            self.ai_typing_label = ctk.CTkLabel(self.ai_typing_frame, text="● ● ●",
                                                 font=("Segoe UI", 12), text_color="#888")
            self.ai_typing_label.pack(padx=12, pady=6)
        else:
            self.ai_typing_frame.configure(fg_color=self.colors["ai_assistant"])
        
        self.ai_typing_frame.pack(fill="x", padx=40, pady=5)
        self._typing_animasyon()

    def _typing_animasyon(self, step=0):
        if not self.ai_typing_frame.winfo_viewable():
            return
        dots = ["● ○ ○", "○ ● ○", "○ ○ ●", "○ ● ○"]
        self.ai_typing_label.configure(text=dots[step % 4])
        self.after(400, lambda: self._typing_animasyon(step + 1))

    def _ai_yaziyor_gizle(self):
        self.ai_durum.configure(text="● Hazır", text_color="#4caf50")
        if self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame.pack_forget()

    def _ai_gonder_event(self, event):
        if not event.state & 0x1:
            self._ai_gonder()
            return "break"

    def _ai_gonder(self):
        if not self.ayarlar.get("ai_aktif"):
            self._ai_mesaj_ekle("assistant", "AI aktif değil.")
            return

        mesaj = self.ai_input.get("1.0", "end-1c").strip()
        if not mesaj:
            return

        mevcut_kod = self.kod_alani.get("1.0", "end-1c").strip()
        
        # ⬅️ YENİ: Kullanıcı kodunu Python'a çevir (AI'a göndermek için)
        python_kodu = ""
        if mevcut_kod:
            python_kodu = turkce_kodu_donustur(mevcut_kod)
            
            # Kısaltma (gerekirse)
            satirlar = python_kodu.split('\n')
            if len(satirlar) > 25:
                python_kodu = '\n'.join(satirlar[-20:])
                python_kodu = f"[Kod son 20 satır]:\n```python\n{python_kodu}\n```"
            else:
                python_kodu = f"[Kod:\n```python\n{python_kodu}\n```]"
        
        # AI'a gönderilecek mesaj (Python formatında)
        if python_kodu:
            tam_mesaj = f"{mesaj}\n\n{python_kodu}"
        else:
            tam_mesaj = mesaj

        # Mesajı kısalt
        if len(tam_mesaj) > 2000:
            tam_mesaj = tam_mesaj[:2000] + "\n[...kısaltıldı]"

        self.ai_input.delete("1.0", "end")
        self._ai_mesaj_ekle("user", mesaj)  # Kullanıcıya orijinal TürKod göster
        self._ai_yaziyor_goster()
        self.ai_durum.configure(text="Yazıyor...")
        self.ai_gonder_btn.configure(state="disabled")
        
        # ⬅️ AI'a Python mesajı gönder (kullanıcı farketmez)
        threading.Thread(target=self._ai_api_cagri, args=(tam_mesaj,), daemon=True).start()

    def _ai_kodu_optimize(self):
        kod = self.kod_alani.get("1.0", "end-1c").strip()
        if not kod:
            self._ai_mesaj_ekle("assistant", "⚠️ Optimize edilecek kod bulunamadı.")
            return
        prompt = f"""Aşağıdaki TürKod kodunu optimize et ve daha verimli hale getir:

```TürKod
{kod}
Yapacakların:
- Yapılan iyileştirmeleri kısaca açıkla
- Optimize edilmiş kodu Türkod bloğunda ver"""
        self._ai_gonder_prompt(prompt)
    def _yerel_duzelt_sozluk(self):
        """Yerel düzeltme için sözlük kelime listesini üret"""
        if hasattr(self, "_yerel_duzelt_sozluk_cache"):
            return self._yerel_duzelt_sozluk_cache

        kelimeler = set()

        try:
            for kelime in TURKCE_KELIMELER:
                kelime = str(kelime).strip()
                if kelime and " " not in kelime:
                    kelimeler.add(kelime)
        except Exception:
            pass

        try:
            for desen in SOZLUK.keys():
                temiz = str(desen).replace(r"\b", "").strip()
                temiz = temiz.strip('"').strip("'")

                if temiz and " " not in temiz and "." not in temiz:
                    kelimeler.add(temiz)
        except Exception:
            pass

        # Sözlük yüklenmezse temel kelimeler yine çalışsın
        kelimeler.update([
            "yazdir", "girdi_al", "fonksiyon", "sinif", "eger", "degilse",
            "degilse_eger", "dongu", "kir", "devam_et", "gec", "dene",
            "hata_yakala", "sonunda", "ice_aktar", "dondur", "ve", "veya", "degil"
        ])

        self._yerel_duzelt_sozluk_cache = sorted(kelimeler)
        return self._yerel_duzelt_sozluk_cache

    def _yerel_duzelt_sozluk_haritasi(self):
        """Küçük harf tabanlı sözlük haritasını üret"""
        if hasattr(self, "_yerel_duzelt_sozluk_map") and hasattr(self, "_yerel_duzelt_sozluk_kucuk_listesi"):
            return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

        sozluk = self._yerel_duzelt_sozluk()
        sozluk_map = {}

        for kelime in sozluk:
            kucuk = kelime.lower()
            if kucuk not in sozluk_map:
                sozluk_map[kucuk] = kelime

        self._yerel_duzelt_sozluk_map = sozluk_map
        self._yerel_duzelt_sozluk_kucuk_listesi = sorted(sozluk_map.keys())

        return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

    def _kodu_yerel_duzelt(self, kod):
        """Koddaki bilinmeyen kelimeleri sözlükteki en yakın kelimeyle düzeltir"""
        import difflib

        sozluk_map, sozluk_kucuk_listesi = self._yerel_duzelt_sozluk_haritasi()

        if not sozluk_kucuk_listesi:
            return kod, set()

        try:
            tanimli_kelimeler = set(self._koddan_tanimlari_cikar(kod))
        except Exception:
            tanimli_kelimeler = set()

        tanimli_kucuk = {str(k).lower() for k in tanimli_kelimeler}
        # Nokta sonrası kullanılan isimler (öznitelik/metot) kullanıcıya aittir, düzeltme
        attr_adlari = re.findall(r'\.\s*([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)', kod)
        tanimli_kucuk |= {a.lower() for a in attr_adlari}

        degisiklikler = set()
        cache = {}

        string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
        parcalar = re.split(string_ve_yorum, kod)
        kelime_deseni = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*"

        def bitisik_takasla_duzelt(kelime):
            """
            Bitişik iki harfin yer değiştirdiği yazım hatalarını yakalar.
            Örnek:
            egre -> eger
            yazidr -> yazdir
            """
            for i in range(len(kelime) - 1):
                takas = kelime[:i] + kelime[i + 1] + kelime[i] + kelime[i + 2:]
                if takas in sozluk_map:
                    return sozluk_map[takas]
            return None

        def duzelt(match):
            token = match.group(0)

            # Çok kısa kelimeleri düzeltme
            if len(token) < 4:
                return token

            kucuk = token.lower()

            # Zaten sözlükte varsa veya kod içinde tanımlıysa dokunma
            if kucuk in sozluk_map or kucuk in tanimli_kucuk:
                return token

            if kucuk in cache:
                return cache[kucuk]

            # 1) Bitişik harf takası: egre -> eger
            takas = bitisik_takasla_duzelt(kucuk)
            if takas and takas != token:
                degisiklikler.add((token, takas))
                cache[kucuk] = takas
                return takas

            # 2) Kısa kelimelerde daha esnek, uzun kelimelerde daha güvenli
            if len(kucuk) <= 5:
                cutoff = 0.60
            elif len(kucuk) <= 8:
                cutoff = 0.70
            else:
                cutoff = 0.78

            oneri = difflib.get_close_matches(
                kucuk,
                sozluk_kucuk_listesi,
                n=1,
                cutoff=cutoff
            )

            if oneri:
                # Kısa kelimelerde yanlış düzeltmeyi azaltmak için ilk 2 harf kontrolü
                if len(kucuk) <= 5 and len(oneri[0]) >= 2 and kucuk[:2] != oneri[0][:2]:
                    cache[kucuk] = token
                    return token

                yeni = sozluk_map[oneri[0]]

                if yeni != token:
                    degisiklikler.add((token, yeni))
                    cache[kucuk] = yeni
                    return yeni

            cache[kucuk] = token
            return token

        for i, parca in enumerate(parcalar):
            if not parca:
                continue

            # String ve yorum parçalarını değiştirme
            if re.fullmatch(string_ve_yorum, parca):
                continue

            parcalar[i] = re.sub(kelime_deseni, duzelt, parca)

        return "".join(parcalar), degisiklikler
    def _ai_kodu_duzelt(self):
        """Düzelt butonu: AI yerine sözlük tabanlı yerel düzeltme yapar"""
        kod = self.kod_alani.get("1.0", "end-1c")

        if not kod.strip():
            self._ai_mesaj_ekle("assistant", "⚠️ Düzeltilecek kod bulunamadı.")
            return

        yeni_kod, degisiklikler = self._kodu_yerel_duzelt(kod)

        if not degisiklikler:
            self._ai_mesaj_ekle(
                "assistant",
                "✅ Sözlüğe göre düzeltilecek belirgin yazım hatası bulunamadı."
            )
            return

        self.kod_alani.delete("1.0", "end")
        self.kod_alani.insert("1.0", yeni_kod)

        self._dosya_degisti_kontrol()
        self.sync_line_numbers()
        self.kod_renklendir()

        satirlar = ["🔧 AI yerine yerel sözlük düzeltmesi yapıldı:", ""]
        for eski, yeni in sorted(degisiklikler):
            satirlar.append(f"• {eski} → {yeni}")

        self._ai_mesaj_ekle("assistant", "\n".join(satirlar))
    
    def _ai_gonder_prompt(self, prompt):
        if not self.ayarlar.get("ai_aktif"):
            self._ai_mesaj_ekle("assistant", "AI aktif değil. Ayarlardan API Key girin.")
            return
        self._ai_mesaj_ekle("user", "[Kod analizi istendi]")
        self.ai_durum.configure(text="Yazıyor...")
        self.ai_gonder_btn.configure(state="disabled")
        threading.Thread(target=self._ai_api_cagri, args=(prompt,), daemon=True).start()

    def _ai_temizle(self):
        for widget in self.ai_chat_frame.winfo_children():
            if widget is not self.ai_typing_frame:
                widget.destroy()
        self.ai_mesajlar.clear()
        self.ai_mesaj_gecmisi.clear()
        self.ai_typing_frame.pack_forget() 
        
    def _ai_api_cagri(self, mesaj):
        saglayici = self.ayarlar.get("ai_saglayici")
        api_key = self.ayarlar.get("ai_api_key")
        model = self.ayarlar.get("ai_model")
        sicaklik = self.ayarlar.get("ai_sicaklik")
        max_token = self.ayarlar.get("ai_max_token")
        sistem_mesaji = self.ayarlar.get("ai_sistem_mesaji")

        try:
            if saglayici == "OpenAI" and openai:
                client = openai.OpenAI(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sistem_mesaji}] + self.ai_mesaj_gecmisi[-2:],
                    temperature=sicaklik,
                    max_tokens=max_token
                )
                cevap = response.choices[0].message.content
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Groq" and Groq:
                client = Groq(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sistem_mesaji}] + self.ai_mesaj_gecmisi[-2:],
                    temperature=sicaklik,
                    max_tokens=max_token
                )
                cevap = response.choices[0].message.content
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Gemini" and genai:
                client = genai.Client(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.models.generate_content(
                    model=model,
                    contents=[sistem_mesaji + "\n\n" + mesaj]
                )
                cevap = response.text
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Claude" and anthropic:
                client = anthropic.Anthropic(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.messages.create(
                    model=model,
                    max_tokens=max_token,
                    system=sistem_mesaji,
                    messages=[{"role": "user", "content": mesaj}]
                )
                cevap = response.content[0].text
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            else:
                import traceback
                print("\n" + "="*60)
                print("  ❌ AI HATASI: Kütüphane Yüklenmemiş")
                print("="*60)
                print(f"\n  Sağlayıcı: {saglayici}")
                print(f"  Durum: İlgili Python kütüphanesi import edilemedi!")
                print(f"\n  Çözüm: Aşağıdaki komutu CMD'de çalıştırın:")
                
                kutuphane_adi = {
                    "OpenAI": "openai",
                    "Groq": "groq", 
                    "Gemini": "google-genai",
                    "Claude": "anthropic"
                }.get(saglayici, saglayici.lower())
                
                print(f"\n    pip install {kutuphane_adi}")
                print("\n" + "="*60)
                print("  Detaylı Hata Bilgisi (Traceback):")
                print("="*60 + "\n")
                
                traceback.print_exc()
                
                cevap = f"⚠️ {saglayici} kütüphanesi yüklü değil!\n\nYüklemek için:\npip install {kutuphane_adi}"

                self.after(0, lambda: self._ai_mesaj_ekle("assistant", cevap))
                self.after(0, self._ai_yaziyor_gizle)
                return

            cevap = self._cevabi_turkceye_cevir(cevap)  # inline `kod` parçalarını da çevirir
            self.after(0, lambda c=cevap: self._ai_mesaj_ekle("assistant", c))
            self.after(0, self._ai_yaziyor_gizle)
            self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))
        except Exception as e:
            hata = str(e).lower()
            hata_kodu = getattr(e, 'status_code', None) or getattr(e, 'code', None)

            # 413 = Payload Too Large (fiziksel boyut, değil rate limit)
            if hata_kodu == 413 or "too large for model" in hata:
                hata_msg = "İstek çok uzun! Kodu kısaltın."
            elif "tokens per minute" in hata or "rate limit" in hata or "limit exceeded" in hata:
                hata_msg = "Limitiniz bitti. Lütfen başka bir API anahtarı alın veya daha sonra tekrar deneyin."
            elif "authentication" in hata or "api key" in hata:
                hata_msg = "API Key geçersiz!"
            elif "model" in hata and "not found" in hata:
                hata_msg = f"Model bulunamadı: {model}"
            elif "connection" in hata or "timeout" in hata:
                hata_msg = "Bağlantı hatası! İnternetinizi kontrol edin."
            else:
                hata_msg = "Bir hata oluştu. Lütfen tekrar deneyin."

            self.after(0, lambda: self._ai_mesaj_ekle("assistant", f"❌ {hata_msg}"))
            self.after(0, self._ai_yaziyor_gizle)
            self.after(0, lambda: self.ai_durum.configure(text="Hazır"))
            self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))

        self.after(0, lambda: self.ai_durum.configure(text="Hazır"))
        self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))
        
    def _cevabi_turkceye_cevir(self, cevap):
        """AI'ın Python yanıtını TürKod'a çevir"""
        import re
        
        # ```python bloklarını bul ve çevir
        def cevir_blok(match):
            dil = match.group(1).strip().lower()
            kod = match.group(2)
            
            if dil == 'python':
                turkce_kod = python_kodu_turkceye_cevir(kod)
                return f'```TürKod\n{turkce_kod}\n```'
            
            return match.group(0)
        
        # Kod bloklarını çevir
        cevap = re.sub(r'```(\w*)\n?(.*?)```', cevir_blok, cevap, flags=re.DOTALL)
        
        # Inline kodları da çevir (tek tırnaklı)
        # `def` -> `fonksiyon` gibi
        for py, tr in sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True):
            # Sadece kelime sınırında değiştir
            cevap = re.sub(rf'`{re.escape(py)}`', f'`{tr}`', cevap)
        
        return cevap
    # ============ AYARLAR PENCERESI ============
    def _ayarlar_penceresi_ac(self):
        pencere = ctk.CTkToplevel(self)
        pencere.configure(fg_color=self.colors["bg"])
        pencere.title("Ayarlar")
        pencere.geometry("600x800")
        pencere.transient(self)
        pencere.grab_set()
        self.ayarlar_penceresi = pencere

        self.notebook = ctk.CTkTabview(pencere, width=560, height=620, fg_color=self.colors["bg"])
        self.notebook.pack(padx=20, pady=20)
        self.notebook._segmented_button.configure(
            fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
            selected_color=self.colors.get("button_bg", "#0e639c"),
            selected_hover_color=self.colors.get("button_hover", "#1177bb"),
            unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
            unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
            text_color=self.colors["text"]
        )

        # === GENEL AYARLAR ===
        self.notebook.add("Genel")
        genel = self.notebook.tab("Genel")

        ctk.CTkLabel(genel, text="Tema:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        tema_var = ctk.StringVar(value=self.ayarlar.get("tema"))
        tema_combo = ctk.CTkOptionMenu(
            genel, 
            values=list(TEMA_RENKLERI.keys()), 
            variable=tema_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        tema_combo.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazi Tipi:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        yazi_var = ctk.StringVar(value=self.ayarlar.get("yazi_tipi"))

        # Tüm kurulu fontları al, önerilenleri üste taşı
        onerilen_fontlar = ["Consolas", "Courier New", "Fira Code", "JetBrains Mono", "Source Code Pro", "Segoe UI", "Arial"]
        tum_fontlar = sorted(set(tkfont.families()))
        font_listesi = [f for f in onerilen_fontlar if f in tum_fontlar] + [f for f in tum_fontlar if f not in onerilen_fontlar]
        if not font_listesi:
            font_listesi = ["Consolas"]

        def _font_secici_ac():
            if hasattr(self, '_font_popup') and self._font_popup.winfo_exists():
                self._font_popup.lift()
                return
            popup = ctk.CTkToplevel(pencere)
            popup.title("Yazı Tipi Seç")
            popup.geometry("320x340")
            popup.transient(pencere)
            popup.grab_set()
            popup.configure(fg_color=self.colors["bg"])
            self._font_popup = popup

            # Arama çubuğu
            arama_var = ctk.StringVar()
            arama_entry = ctk.CTkEntry(popup, textvariable=arama_var, placeholder_text="🔍 Yazı tipi ara...",
                                       height=32, fg_color=self.colors.get("ai_input", "#3c3c3c"),
                                       text_color=self.colors["text"], border_color=self.colors["border"])
            arama_entry.pack(fill="x", padx=10, pady=(10, 5))
            arama_entry.focus_set()

            # Liste çerçevesi
            liste_frame = tk.Frame(popup, bg=self.colors["bg"])
            liste_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            scrollbar = ctk.CTkScrollbar(liste_frame, orientation="vertical")
            scrollbar.pack(side="right", fill="y")

            listbox = tk.Listbox(liste_frame, bg=self.colors.get("sidebar", "#252526"),
                                 fg=self.colors["text"], selectbackground=self.colors.get("selection", "#264f78"),
                                 selectforeground="white", font=("Segoe UI", 11), bd=0,
                                 highlightthickness=1, highlightbackground=self.colors["border"],
                                 activestyle="none", yscrollcommand=scrollbar.set)
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.configure(command=listbox.yview)

            def _doldur(filtre_metni=""):
                listbox.delete(0, tk.END)
                filtre_metni = filtre_metni.lower()
                for f in font_listesi:
                    if filtre_metni in f.lower():
                        listbox.insert(tk.END, f)
                # Mevcut seçimi vurgula
                mevcut = yazi_var.get()
                for i in range(listbox.size()):
                    if listbox.get(i) == mevcut:
                        listbox.selection_set(i)
                        listbox.see(i)
                        break

            def _sec(event=None):
                secim = listbox.curselection()
                if secim:
                    yazi_var.set(listbox.get(secim[0]))
                    font_btn.configure(text=yazi_var.get())
                    popup.destroy()

            def _tekerlek(event):
                # Orta tekerlek (Button-2 sürükleme) ve normal tekerlek (MouseWheel) desteği
                if getattr(event, "num", None) == 2 or event.type == "38":  # 38 = MouseWheel olay tipi
                    pass
                delta = getattr(event, "delta", 0)
                if delta:
                    listbox.yview_scroll(int(-1 * (delta / 120)), "units")
                return "break"

            # Orta tekerlek ile kaydırma (Windows/Linux)
            listbox.bind("<MouseWheel>", _tekerlek)
            listbox.bind("<Button-4>", lambda e: (listbox.yview_scroll(-3, "units"), "break"))
            listbox.bind("<Button-5>", lambda e: (listbox.yview_scroll(3, "units"), "break"))
            # Orta tuş basılı tutarak kaydırma
            listbox.bind("<B2-Motion>", lambda e: (listbox.yview_moveto(e.y / listbox.winfo_height()), "break"))

            arama_var.trace_add("write", lambda *a: _doldur(arama_var.get()))
            listbox.bind("<Double-Button-1>", _sec)
            listbox.bind("<Return>", _sec)
            arama_entry.bind("<Return>", lambda e: (listbox.focus_set(), listbox.select_set(0) if listbox.size() else None))
            arama_entry.bind("<Down>", lambda e: listbox.focus_set())

            _doldur()

        # Seçim butonu (OptionMenu yerine)
        font_btn = ctk.CTkButton(genel, text=yazi_var.get(), command=_font_secici_ac,
                                 fg_color=self.colors.get("button_bg", "#0e639c"),
                                 hover_color=self.colors.get("button_hover", "#1177bb"),
                                 text_color=self.colors["text"], anchor="w")
        font_btn.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazi Boyutu:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        boyut_var = ctk.IntVar(value=self.ayarlar.get("yazi_boyutu"))
        self.slider_boyut = ctk.CTkSlider(
            genel, 
            from_=8, 
            to=32, 
            number_of_steps=24, 
            variable=boyut_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_boyut.pack(fill="x", padx=10, pady=5)
        self.label_boyut = ctk.CTkLabel(genel, textvariable=boyut_var, text_color=self.colors["text"])
        self.label_boyut.pack(anchor="w", padx=10)

        satir_var = ctk.BooleanVar(value=self.ayarlar.get("satir_numaralari"))
        satir_cb = ctk.CTkCheckBox(genel, text="Satır Numaralarını Göster", variable=satir_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        satir_cb.pack(anchor="w", pady=5, padx=10)

        sar_var = ctk.BooleanVar(value=self.ayarlar.get("kelime_sar"))
        sar_cb = ctk.CTkCheckBox(genel, text="Kelime Sarma (Word Wrap)", variable=sar_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        sar_cb.pack(anchor="w", pady=5, padx=10)

        # === EDITOR AYARLARI ===
        self.notebook.add("Editor")
        editor = self.notebook.tab("Editor")

        tamamlama_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_tamamlama"))
        tamamlama_cb = ctk.CTkCheckBox(editor, text="Otomatik Tamamlama", variable=tamamlama_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        tamamlama_cb.pack(anchor="w", pady=10, padx=10)

        oto_kaydet_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_kaydetme"))
        oto_kaydet_cb = ctk.CTkCheckBox(editor, text="Otomatik Kaydetme", variable=oto_kaydet_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        oto_kaydet_cb.pack(anchor="w", pady=5, padx=10)

        ctk.CTkLabel(editor, text="Oto. Kaydetme Aralığı (sn):", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        aralik_var = ctk.IntVar(value=self.ayarlar.get("otomatik_kaydetme_aralik"))
        self.slider_aralik = ctk.CTkSlider(
            editor,
            from_=5,
            to=300,
            number_of_steps=59,
            variable=aralik_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_aralik.pack(fill="x", padx=10, pady=5)
        self.label_aralik = ctk.CTkLabel(editor, textvariable=aralik_var, text_color=self.colors["text"])
        self.label_aralik.pack(anchor="w", padx=10)

        bosluk_var = ctk.BooleanVar(value=self.ayarlar.get("bosluk_gostergesi"))
        bosluk_cb = ctk.CTkCheckBox(editor, text="Boşluk Göstergesi", variable=bosluk_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        bosluk_cb.pack(anchor="w", pady=5, padx=10)

        minimap_var = ctk.BooleanVar(value=self.ayarlar.get("minimap"))
        minimap_cb = ctk.CTkCheckBox(editor, text="Minimap (Küçük Harita)", variable=minimap_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        minimap_cb.pack(anchor="w", pady=5, padx=10)
        
        # === AI AYARLARI ===
        self.notebook.add("AI Asistan")
        ai_tab = self.notebook.tab("AI Asistan")

        ai_aktif_var = ctk.BooleanVar(value=self.ayarlar.get("ai_aktif"))
        ai_aktif_cb = ctk.CTkCheckBox(ai_tab, text="AI Asistanı Aktif", variable=ai_aktif_var,
            text_color=self.colors["text"],
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"))
        ai_aktif_cb.pack(anchor="w", pady=10, padx=10)

        ctk.CTkLabel(ai_tab, text="AI Sağlayıcı:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        saglayici_var = ctk.StringVar(value=self.ayarlar.get("ai_saglayici"))
        saglayici_combo = ctk.CTkOptionMenu(
            ai_tab, 
            values=list(AI_MODELLERI.keys()), 
            variable=saglayici_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        saglayici_combo.pack(fill="x", padx=10, pady=5)

        model_var = ctk.StringVar(value=self.ayarlar.get("ai_model"))
        model_combo = ctk.CTkOptionMenu(
            ai_tab, 
            values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]), 
            variable=model_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        model_combo.pack(fill="x", padx=10, pady=5)

        def saglayici_degisti(*args):
            model_combo.configure(values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]))
            model_var.set(AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"])[0])
        saglayici_var.trace_add("write", saglayici_degisti)

        ctk.CTkLabel(ai_tab, text="API Key:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        api_key_var = ctk.StringVar(value=self.ayarlar.get("ai_api_key"))
        api_key_entry = ctk.CTkEntry(ai_tab, textvariable=api_key_var, show="*", width=500,
            fg_color=self.colors.get("ai_input", "#3c3c3c"),
            text_color=self.colors["text"],
            border_color=self.colors.get("border", "#3c3c3c"))
        api_key_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sistem Mesajı:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        sistem_var = ctk.StringVar(value=self.ayarlar.get("ai_sistem_mesaji"))
        sistem_entry = ctk.CTkEntry(ai_tab, textvariable=sistem_var, width=500,
            fg_color=self.colors.get("ai_input", "#3c3c3c"),
            text_color=self.colors["text"],
            border_color=self.colors.get("border", "#3c3c3c"))
        sistem_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sıcaklık (0-2):", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        sicaklik_var = ctk.DoubleVar(value=self.ayarlar.get("ai_sicaklik"))
        self.slider_sicaklik = ctk.CTkSlider(
            ai_tab,
            from_=0,
            to=2,
            number_of_steps=20,
            variable=sicaklik_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_sicaklik.pack(fill="x", padx=10, pady=5)
        self.label_sicaklik = ctk.CTkLabel(ai_tab, textvariable=sicaklik_var, text_color=self.colors["text"])
        self.label_sicaklik.pack(anchor="w", padx=10)

        ctk.CTkLabel(ai_tab, text="Max Token:", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        token_var = ctk.IntVar(value=self.ayarlar.get("ai_max_token"))
        self.slider_token = ctk.CTkSlider(
            ai_tab,
            from_=4096,
            to=32768,
            number_of_steps=30,
            variable=token_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_token.pack(fill="x", padx=10, pady=5)
        self.label_token = ctk.CTkLabel(ai_tab, textvariable=token_var, text_color=self.colors["text"])
        self.label_token.pack(anchor="w", padx=10)
        # === HAKKIMDA ===
        self.notebook.add("Hakkımda")
        hakkinda = self.notebook.tab("Hakkımda")

        # ===== BAŞLIK =====
        ctk.CTkLabel(hakkinda, text="TürKod IDE", 
                     font=("Segoe UI", 24, "bold"),
                     text_color=self.colors["text"]).pack(pady=(20, 5))
        
        ctk.CTkLabel(hakkinda, text="Profesyonel Türkçe Python Editörü", 
                     font=("Segoe UI", 12), text_color="#888").pack()

        # Çizgi
        ctk.CTkFrame(hakkinda, fg_color=self.colors["border"], 
                     height=2).pack(fill="x", padx=40, pady=15)

        # ===== GELİŞTİRİCİ =====
        ctk.CTkLabel(hakkinda, text="Geliştirici", 
                     font=("Segoe UI", 10, "bold"), text_color="#666").pack()
        
        # ↓↓↓ ADIN SOYADIN ↓↓↓
        ctk.CTkLabel(hakkinda, text="YUSUF TANDOĞAN",  
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.colors["text"]).pack(pady=(2, 5))

        ctk.CTkLabel(hakkinda, text="yusuftndgn.2@gmail.com",  
                     font=("Segoe UI", 10), text_color="#888").pack()

        ctk.CTkLabel(hakkinda, text="Versiyon 2.0  |  © 2026 Tüm Hakları Saklıdır", 
                     font=("Segoe UI", 10), text_color="#666").pack(pady=(0, 10))

        # ===== RSA DİJİTAL İMZA KUTUSU =====
        self.rsa_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                       corner_radius=8, border_width=1,
                                       border_color=self.colors["border"])
        self.rsa_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(self.rsa_frame, text="🔐 RSA Dijital İmza", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#4caf50").pack(anchor="w", padx=12, pady=(10, 0))

        self.rsa_durum = ctk.CTkLabel(self.rsa_frame, 
                     text="Doğrulanıyor...",
                     font=("Segoe UI", 9),
                     text_color=self.colors["panel_fg"])
        self.rsa_durum.pack(anchor="w", padx=12, pady=(5, 2))

        self.rsa_detay = ctk.CTkLabel(self.rsa_frame, 
                     text="",
                     font=("Consolas", 8),
                     text_color="#666")
        self.rsa_detay.pack(anchor="w", padx=12, pady=(0, 10))

        # ===== GITHUB KANITI =====
        github_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                     corner_radius=8, border_width=1,
                                     border_color=self.colors["border"])
        github_frame.pack(fill="x", padx=40, pady=(0, 10))

        ctk.CTkLabel(github_frame, text="📁 Kaynak Kod Kanıtı", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#569cd6").pack(anchor="w", padx=12, pady=(10, 0))

        ctk.CTkLabel(github_frame, 
                     text="github.com/YusufX-sys/turkod-ide",
                     font=("Consolas", 9),
                     text_color="#ce9178").pack(anchor="w", padx=12, pady=(5, 2))

        ctk.CTkLabel(github_frame, 
                     text="İlk commit: 8 Ağustos 2026",
                     font=("Segoe UI", 8),
                     text_color="#666").pack(anchor="w", padx=12, pady=(0, 10))

        # ===== DOSYA BİLGİSİ =====
        dosya_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                    corner_radius=8, border_width=1,
                                    border_color=self.colors["border"])
        dosya_frame.pack(fill="x", padx=40, pady=(0, 20))

        ctk.CTkLabel(dosya_frame, text="📄 Dosya Bilgisi", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#666").pack(anchor="w", padx=12, pady=(10, 0))

        # Çalışan dosya tipi
        tip = "EXE" if getattr(sys, 'frozen', False) else "PY"
        ctk.CTkLabel(dosya_frame, 
                     text=f"Çalışan format: {tip}",
                     font=("Segoe UI", 9),
                     text_color="#888").pack(anchor="w", padx=12, pady=(5, 2))

        # Hash değeri
        dosya_hash = DijitalImza.hash_hesapla()
        hash_kisa = dosya_hash[:20] + "..." + dosya_hash[-10:] if len(dosya_hash) > 30 else dosya_hash
        
        ctk.CTkLabel(dosya_frame, 
                     text=f"SHA-256: {hash_kisa}",
                     font=("Consolas", 8),
                     text_color="#666").pack(anchor="w", padx=12, pady=(0, 10))

        # ===== DOĞRULAMAYI BAŞLAT =====
        self.after(500, self._hakkimda_imza_kontrol)
        # ===== KAYDET BUTONU =====
        def kaydet_ayarlar():
            self.ayarlar.set("tema", tema_combo.get())
            self.ayarlar.set("yazi_tipi", yazi_var.get())
            self.ayarlar.set("yazi_boyutu", int(self.slider_boyut.get()))
            self.ayarlar.set("satir_numaralari", satir_var.get())
            self.ayarlar.set("kelime_sar", sar_var.get())
            self.ayarlar.set("otomatik_tamamlama", tamamlama_var.get())
            self.ayarlar.set("otomatik_kaydetme", oto_kaydet_var.get())
            self.ayarlar.set("otomatik_kaydetme_aralik", int(self.slider_aralik.get()))
            self.ayarlar.set("bosluk_gostergesi", bosluk_var.get())
            self.ayarlar.set("minimap", minimap_var.get())
            self.ayarlar.set("ai_aktif", ai_aktif_var.get())
            self.ayarlar.set("ai_saglayici", saglayici_var.get())
            self.ayarlar.set("ai_model", model_var.get())
            self.ayarlar.set("ai_api_key", api_key_var.get())
            self.ayarlar.set("ai_sistem_mesaji", sistem_var.get())
            self.ayarlar.set("ai_sicaklik", float(self.slider_sicaklik.get()))
            self.ayarlar.set("ai_max_token", int(self.slider_token.get()))

            self.tema = tema_combo.get()
            self.colors = TEMA_RENKLERI.get(self.tema, TEMA_RENKLERI["Koyu"])
            # === WORD WRAP GÜNCELLEME ===
            self.kod_alani.configure(
                wrap="word" if self.ayarlar.get("kelime_sar") else "none"
            )
            
            # Ayarlari aninda UI grid'e yansit
            if satir_var.get():
                self.line_numbers.grid(row=0, column=0, sticky="nsew")
            else:
                self.line_numbers.grid_forget()
                
            if minimap_var.get():
                self.minimap.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
                self._sync_minimap()
            else:
                self.minimap.grid_forget()
            self.sync_line_numbers()
            self._tema_uygula()
            pencere.destroy()

        ctk.CTkButton(pencere, text="Kaydet ve Uygula", command=kaydet_ayarlar,
                       fg_color="#28a745", hover_color="#218838",
                       border_color=self.colors["border"],
                       border_width=2,
                       font=("Segoe UI", 14, "bold")).pack(pady=15)

    def _tema_uygula(self):
        self.configure(fg_color=self.colors["bg"])
        if hasattr(self, "terminal_grip"):
            self.terminal_grip.configure(fg_color=self.colors["border"])
        # Aktivite Çubuğu (Activity Bar)
        if hasattr(self, 'activity_bar'):
            self.activity_bar.configure(fg_color=self.colors.get("activity_bar", self.colors["sidebar"]))
        
        # Aktivite barı butonları
        for btn in [self.explorer_btn, self.ai_toggle_btn, self.ayarlar_btn]:
            btn.configure(
                fg_color="transparent",
                border_color=self.colors["border"], 
                text_color=self.colors["text"]
            )
        
        # SOL PANEL (Sidebar) & Treeview
        self.sidebar.configure(fg_color=self.colors["sidebar"])
        self.sidebar_title.configure(text_color=self.colors["panel_fg"])
        self.proje_ac_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"])
        
        style = ttk.Style()
        style.configure("Custom.Treeview",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            fieldbackground=self.colors["sidebar"]
        )
        style.map("Custom.Treeview",
            background=[("selected", self.colors.get("selection", "#264f78"))],
            foreground=[("selected", "white")]
        )

        self.dosya_tree.tag_configure("directory", foreground=self.colors.get("keyword", "#569cd6"))
        self.dosya_tree.tag_configure("trpy", foreground=self.colors.get("string", "#ce9178"))
        self.dosya_tree.tag_configure("python", foreground=self.colors.get("builtin", "#dcdcaa"))
        self.dosya_tree.tag_configure("other", foreground=self.colors["panel_fg"])

        # TAB BAR & SEKMELER
        for btn in (getattr(self, "tab_left_btn", None), getattr(self, "tab_right_btn", None)):
            if btn:
                btn.configure(text_color=self.colors["text"],
                              hover_color=self.colors["tab_active"])
        self.tab_bar.configure(fg_color=self.colors.get("tab_inactive", "#f3f3f3"))
        
        for sekme in self.sekmeler:
            is_active = (sekme["id"] == self.aktif_sekme_id)
            sekme["frame"].configure(
                fg_color=self.colors["tab_active"] if is_active else self.colors["tab_inactive"],
                border_color=self.colors["border"]
            )
            sekme["label"].configure(text_color=self.colors["text"])
            sekme["kapat_btn"].configure(text_color=self.colors["text"])

        # === TERMİNAL ===
        if hasattr(self, 'terminal_frame') and self.terminal_frame.winfo_exists():
            self.terminal_frame.configure(fg_color=self.colors["panel_bg"])

            for child in self.terminal_frame.winfo_children():
                # Üst başlık çubuğu
                if isinstance(child, ctk.CTkFrame):
                    child.configure(fg_color=self.colors["sidebar"])
                    for w in child.winfo_children():
                        if isinstance(w, ctk.CTkLabel):
                            w.configure(text_color=self.colors["panel_fg"])
                        elif isinstance(w, ctk.CTkButton):
                            w.configure(text_color=self.colors["text"])
                # Çıktı alanı
                elif isinstance(child, ctk.CTkTextbox):
                    child.configure(fg_color=self.colors["bg"],
                                    text_color=self.colors["text"])
                # Komut satırı
                elif isinstance(child, ctk.CTkEntry):
                    child.configure(fg_color=self.colors["ai_input"],
                                    text_color=self.colors["text"],
                                    border_color=self.colors["border"])
            
        # EDİTÖR FONT GÜNCELLEME
        yazi_tipi = self.ayarlar.get("yazi_tipi")
        if yazi_tipi not in set(tkfont.families()):
            yazi_tipi = "Consolas"
            self.ayarlar.set("yazi_tipi", yazi_tipi)

        yeni_font = (yazi_tipi, self.ayarlar.get("yazi_boyutu"))
        self.kod_alani.configure(font=yeni_font)
        self.line_numbers.configure(font=yeni_font)
            
        # Tab Butonları
        self.yeni_sekme_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.ac_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.kaydet_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.calistir_btn.configure(border_color=self.colors["border"])
        self.cevir_btn.configure(fg_color=self.colors["button_bg"],
        hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        
        # EDİTÖR ALANI
        self.editor_frame.configure(fg_color=self.colors["bg"])
        self.line_numbers.configure(fg_color=self.colors["bg"], text_color=self.colors["line_number"])
        self.kod_alani.configure(fg_color=self.colors["bg"], text_color=self.colors["text"])
        
        if hasattr(self, 'minimap') and self.minimap.winfo_exists():
            self.minimap.configure(fg_color=self.colors["sidebar"], text_color=self.colors["text"])
        
        # AI PANEL
        self.ai_panel.configure(fg_color=self.colors["ai_panel"])
        self.ai_baslik.configure(text_color=self.colors["text"])
        
        for attr in ['ai_chat_area', 'ai_chat_frame', 'ai_messages_frame', 'chat_display']:
            if hasattr(self, attr):
                getattr(self, attr).configure(fg_color="transparent") 

        # Girdi Kutusu ve Butonlar
        self.ai_input_frame.configure(fg_color=self.colors["ai_input"])
        self.ai_input.configure(fg_color="transparent", text_color=self.colors["text"])
        self.ai_gonder_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"])
        # AI sohbetini yeni temayla yeniden çiz
        if hasattr(self, 'ai_chat_frame') and self.ai_chat_frame.winfo_exists():
            kayitli = list(getattr(self, 'ai_mesajlar', []))
            for widget in self.ai_chat_frame.winfo_children():
                if widget is not getattr(self, 'ai_typing_frame', None):
                    widget.destroy()
            self.ai_mesajlar = []
            for m in kayitli:
                self._ai_mesaj_ekle(m["gonderen"], m["mesaj"])
        if hasattr(self, 'ai_typing_frame') and self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame.configure(fg_color=self.colors["ai_assistant"])
        # Alt Durum Çubuğu (Status Bar)
        self.status_bar.configure(fg_color=self.colors["status_bar"])

        self.renk_ayarlarini_yap()
        self.kod_renklendir()
        # === AYARLAR PENCERESI DE GUNCELLENSIN ===
        if hasattr(self, 'ayarlar_penceresi') and self.ayarlar_penceresi.winfo_exists():
            self.ayarlar_penceresi.configure(fg_color=self.colors["bg"])
        # === AYARLAR PENCERESI NOTEBOOK TAB'LARI GUNCELLEME ===
        if hasattr(self, 'notebook') and self.notebook.winfo_exists():
            # Notebook'un kendisi
            self.notebook.configure(fg_color=self.colors["bg"])
            
            # Segmented button (tab başlıkları)
            if hasattr(self.notebook, '_segmented_button') and self.notebook._segmented_button:
                self.notebook._segmented_button.configure(
                    fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                    selected_color=self.colors.get("button_bg", "#0e639c"),
                    selected_hover_color=self.colors.get("button_hover", "#1177bb"),
                    unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                    unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
                    text_color=self.colors["text"],
                    text_color_disabled=self.colors.get("line_number", "#858585")
                )
            
            # Her bir tab'ın içeriği (frame)
            if hasattr(self.notebook, '_tab_dict'):
                for tab in self.notebook._tab_dict.values():
                    tab.configure(fg_color=self.colors["bg"])
            
            def _widget_renk_guncelle(widget, derinlik=0):
                if derinlik > 6:
                    return
                try:
                    if isinstance(widget, ctk.CTkFrame):
                        # Tab içeriği mi kontrol et (CTkTabview'in _tab_dict içinde mi?)
                        is_tab_content = False
                        try:
                            parent = widget.master
                            while parent:
                                if isinstance(parent, ctk.CTkTabview):
                                    is_tab_content = True
                                    break
                                parent = parent.master
                        except:
                            pass
                        
                        if is_tab_content:
                            # Tab içeriği = arka plan rengi
                            widget.configure(
                                fg_color=self.colors["bg"],
                                border_color=self.colors["border"]
                            )
                        else:
                            # Normal frame = sidebar rengi
                            widget.configure(
                                fg_color=self.colors.get("sidebar", self.colors["bg"]),
                                border_color=self.colors["border"]
                            )
                    elif isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=self.colors["text"])
                    elif isinstance(widget, ctk.CTkCheckBox):
                        widget.configure(
                            text_color=self.colors["text"],
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkEntry):
                        widget.configure(
                            fg_color=self.colors.get("ai_input", "#3c3c3c"),
                            text_color=self.colors["text"],
                            border_color=self.colors["border"]
                        )
                    elif isinstance(widget, ctk.CTkOptionMenu):
                        widget.configure(
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            text_color=self.colors["text"],
                            button_color=self.colors.get("button_hover", "#1177bb"),
                            button_hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkSlider):
                        widget.configure(
                            fg_color=self.colors.get("sidebar", self.colors["bg"]),
                            progress_color=self.colors.get("button_bg", "#0e639c"),
                            button_color=self.colors.get("button_bg", "#0e639c"),
                            button_hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkButton):
                        widget.configure(
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            hover_color=self.colors.get("button_hover", "#1177bb"),
                            text_color=self.colors["text"],
                            border_color=self.colors["border"]
                        )
                except Exception:
                    pass
                for child in widget.winfo_children():
                    _widget_renk_guncelle(child, derinlik + 1)
            
            _widget_renk_guncelle(self.ayarlar_penceresi)
            # === AYARLAR PENCERESI NOTEBOOK TAB'LARI GUNCELLEME ===
            if hasattr(self, 'notebook') and self.notebook.winfo_exists():
                self.notebook.configure(fg_color=self.colors["bg"])
                if hasattr(self.notebook, '_segmented_button') and self.notebook._segmented_button:
                    self.notebook._segmented_button.configure(
                        fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                        selected_color=self.colors.get("button_bg", "#0e639c"),
                        selected_hover_color=self.colors.get("button_hover", "#1177bb"),
                        unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                        unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
                        text_color=self.colors["text"],
                        text_color_disabled=self.colors.get("line_number", "#858585")
                    )
                if hasattr(self.notebook, '_tab_dict'):
                    for tab in self.notebook._tab_dict.values():
                        tab.configure(fg_color=self.colors["bg"])
            # === SLIDER'LARI DOĞRUDAN GÜNCELLE ===
            # CTkTabview içinde oldukları için recursive bulunamayabilirler
            slider_renkleri = {
                "fg_color": self.colors.get("sidebar", self.colors["bg"]),
                "progress_color": self.colors.get("button_bg", "#0e639c"),
                "button_color": self.colors.get("button_bg", "#0e639c"),
                "button_hover_color": self.colors.get("button_hover", "#1177bb")
            }
            for attr in ['slider_boyut', 'slider_aralik', 'slider_sicaklik', 'slider_token']:
                if hasattr(self, attr):
                    try:
                        getattr(self, attr).configure(**slider_renkleri)
                    except Exception:
                        pass
                    
            # === DEĞER LABEL'LARINI DOĞRUDAN GÜNCELLE ===
            for attr in ['label_boyut', 'label_aralik', 'label_sicaklik', 'label_token']:
                if hasattr(self, attr):
                    try:
                        getattr(self, attr).configure(text_color=self.colors["text"])
                    except Exception:
                        pass
    def _hakkimda_imza_kontrol(self):
        """Hakkımda sekmesindeki RSA imzasını kontrol et ve göster"""
        try:
            print(f"\n{'='*70}")
            print("  HAKKIMDA - İMZA KONTROL BAŞLATILIYOR")
            print(f"{'='*70}")
            
            basarili, mesaj, detay = DijitalImza.dogrula()
            
            print(f"\n  Sonuç: basarili={basarili}, mesaj='{mesaj}', detay='{detay}'")
            print(f"{'='*70}\n")
            
            self.rsa_durum.configure(text=mesaj)
            self.rsa_detay.configure(text=detay)
            
            if basarili:
                self.rsa_durum.configure(text_color="#4caf50")
            elif "GEÇERSİZ" in mesaj:
                self.rsa_durum.configure(text_color="#f44336")
            else:
                self.rsa_durum.configure(text_color="#ff9800")
                
        except Exception as e:
            import traceback
            print(f"\n{'='*70}")
            print("  İMZA KONTROL EXCEPTION (HAKKIMDA)")
            print(f"{'='*70}")
            print(f"  Hata: {str(e)}")
            print("  Traceback:")
            traceback.print_exc()
            print(f"{'='*70}\n")
            
            self.rsa_durum.configure(
                text="⚠️ Kontrol hatası",
                text_color="#ff9800"
            )
            self.rsa_detay.configure(
                text=str(e)[:80],
                text_color="#666"
            )
    # ============ EDITOR FONKSIYONLARI ============
    def _gorsel_satir_adedi(self, satir):
        kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        try:
            n = kod_tb.count(f"{satir}.0", f"{satir + 1}.0", "displaylines")
            if isinstance(n, (tuple, list)):
                n = n[0]
            return max(1, int(n or 1))
        except Exception:
            return 1

    def _satir_numaralarini_ciz(self):
        gizli = self._gizli_satirlar()
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        satir_sayisi = int(self.kod_alani.index("end-1c").split(".")[0])
        for i in range(1, satir_sayisi + 1):
            if i in gizli:
                continue                      # katlanmış satırın numarası çizilmez
            ikon = ""
            if i in getattr(self, "fold_indicators", {}):
                ikon = self.fold_indicators[i] + " "
            self.line_numbers.insert("end", f"{ikon}{i}\n")
            for _ in range(self._gorsel_satir_adedi(i) - 1):
                self.line_numbers.insert("end", "\n")
        self.line_numbers.configure(state="disabled")
    def _gutter_rakamini_oku(self, event):
        """Tıklanan gutter satırındaki gerçek satır numarasını ve sütunu döndürür"""
        ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
        idx = ln.index(f"@{event.x},{event.y}")
        g_satir, sutun = idx.split(".")
        metin = ln.get(f"{g_satir}.0", f"{g_satir}.end")
        m = re.search(r"\d+", metin)
        if not m:
            return None, None
        return int(m.group(0)), int(sutun)

    def sync_line_numbers(self):
        try:
            self._fold_guncelle()          # numaraları da yeniden çizer
            self._senkronize_scroll()      # çizimden SONRA senkron
            self._sync_minimap()
        except Exception:
            pass
    def _sync_minimap(self):
        """Minimap textini ana editorle senkronize et"""
        if not self.ayarlar.get("minimap") or not hasattr(self, 'minimap'):
            return
            
        try:
            icerik = self.kod_alani.get("1.0", "end")
            self.minimap.configure(state="normal")
            self.minimap.delete("1.0", "end")
            self.minimap.insert("1.0", icerik)
            self.minimap.configure(state="disabled")
            
            first, last = self.kod_alani.yview()
            self.minimap.yview_moveto(first)
        except Exception:
            pass
    
    def kod_renklendir(self):
        try:
            tb = getattr(self.kod_alani, "_textbox", self.kod_alani)

            # 1) Eski tag'leri temizle (fstring ve bosluk dahil)
            for tag in ("keyword", "builtin", "string", "comment", "number", "fstring", "bosluk"):
                tb.tag_remove(tag, "1.0", "end")

            metin = self.kod_alani.get("1.0", "end-1c")
            if not metin:
                return

            def tk_idx(pos):
                satir = metin.count("\n", 0, pos) + 1
                sutun = pos - metin.rfind("\n", 0, pos) - 1
                return f"{satir}.{sutun}"

            string_pattern = (
                r'(?<![A-Za-z0-9_])'
                r'([fF]?(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\''
                r'|"(?:[^"\\\n]|\\.)*"?|\'(?:[^\'\\\n]|\\.)*\'?))'
            )
            comment_pattern = r'#[^\n]*'
            keyword_pattern = r"\b(fonksiyon|dondur|sinif|eger|degilse_eger|degilse|dongu|kir|devam_et|gec|dene|hata_yakala|sonunda|ice_aktar|den|olarak|ve|veya|degil|eszamansiz|bekle|verim|kuresel|yerel_olmayan|sil|ile)\b"
            builtin_pattern = r"\b(yazdir|girdi_al|uzunluk|aralik|tip|en_buyuk|en_kucuk|toplam|mutlak|tamsayi|metin|ondalikli|mantiksal|liste|sozluk|tarih_saat|rastgele|matematik|simdi|ekle|sirala|karekok|kaplumbaga|ileri|geri|saga_don|sola_don|kalem_birak|kalem_kaldir|tkinter_arayuz|dugme|pencere|hepsi|herhangi|ascii_goster|ikili|kirma_noktasi|byte_dizisi|byte|cagrilabilir_mi|karakter|sinif_metodu|derle|karmasik|ozellik_sil|dizin|bolum_kalan|sirali_numaralandir|degerlendir|calistir|suz|icindekiler|donmus_kume|ozellik_al|kuresel_degiskenler|ozellik_var_mi|ozet|yardim|onaltilik|kimlik|alt_sinif_mi|yineleyici|yerel_degiskenler|harita|hafiza_gorunumu|sonraki|nesne|sekizlik|sirala_builtin|ters_cevir_builtin|temsil|ozellik_ayarla|dilim|durum_metodu|ust_sinif|degiskenler|izdusum|ice_aktar_builtin|bas_harf_buyuk|kucult_karsilastir|ortele|kodla|genislet_sekme|bul|bicimle|bicimle_harita|harf_sayi_mi|harf_mi|ascii_mi|onluk_mu|rakam_mi|tanimlayici_mi|kucuk_mu|sayi_mi|yazilabilir_mi|bosluk_mu|baslik_mi|buyuk_mu|sola_yasla|sol_kirp|cevirim_tablo|bolumle|on_ek_kaldir|son_ek_kaldir|sagdan_bul|sagdan_indeks|saga_yasla|sagdan_bolumle|sagdan_bol|sag_kirp|satir_bol|harf_degistir|baslik_yap|cevir|sifir_doldur|anahtardan_olustur|son_ogeyi_cikart|varsayilan_ayarla|guncelle|ekle_kume|fark|fark_guncelle|at|kesisim|kesisim_guncelle|ayrik_mi|alt_kume_mi|ust_kume_mi|bakirisim|bakirisim_guncelle|birlesim|kume_guncelle|kapat|oku|satir_oku|satirlari_oku|konumla|kacinci_byte|kisalt|yaz|satirlari_yaz|tampon_temizle|okunabilir_mi|yazilabilir_mi_dosya|konumlanabilir_mi|etiket|metin_kutusu|metin_alani|cerceve|liste_kutusu|menu|yeni_pencere|checkbutton|radiobutton|scale|scrollbar|spinbox|canvas|messagebox|filedialog|colorchooser|pack|grid|yerlestir|mainloop|after|destroy|configure|config|isletim_sistemi|bulundugu_dizin|dizin_degistir|dizin_listele|dizin_olustur|dizinler_olustur|dosya_sil|dizin_sil|yeniden_adlandir|yol_var_mi|dosya_mi|dizin_mi|yol_birlestir|dosya_adi|dizin_adi|tam_yol|yol_ayir|cevre_degiskenleri|sistem_calistir|cevre_al|sistem|argumanlar|cikis|yol_listesi|platform|surum|standart_cikis|standart_giris|standart_hata|boyut_al|zaman_modulu|buyu|anlik_zaman|yerel_zaman|greenwich_zaman|zaman_bicimle|zaman_ayristir|performans_sayaci|monotonik_sayac|json|json_yukle|json_yukle_metin|json_kaydet|json_kaydet_metin|desen|eslestir|ara|hepsini_bul|yineleyici_bul|desen_bol|desen_degistir|desen_degistir_say|desen_derle|kacis)\b"
            number_pattern = r'\b\d+(?:\.\d+)?\b'

            # 2) String'ler ve f-string'ler (üçlü tırnak dahil)
            string_araliklari = []
            for m in re.finditer(string_pattern, metin):
                string_araliklari.append((m.start(), m.end()))
                tag = "fstring" if m.group(1)[:1] in "fF" else "string"
                tb.tag_add(tag, tk_idx(m.start()), tk_idx(m.end()))

            # 3) Yorumlar (string içindeki # yok sayılır)
            korunacak = list(string_araliklari)
            for m in re.finditer(comment_pattern, metin):
                if any(s <= m.start() < e for s, e in string_araliklari):
                    continue
                korunacak.append((m.start(), m.end()))
                tb.tag_add("comment", tk_idx(m.start()), tk_idx(m.end()))

            def disinda(a, b):
                return not any(s <= a and b <= e for s, e in korunacak)

            # 4) Keyword / builtin / sayı (string ve yorum dışındakiler)
            for m in re.finditer(keyword_pattern, metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("keyword", tk_idx(m.start()), tk_idx(m.end()))
            for m in re.finditer(builtin_pattern, metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("builtin", tk_idx(m.start()), tk_idx(m.end()))
            for m in re.finditer(number_pattern, metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("number", tk_idx(m.start()), tk_idx(m.end()))

            # 5) Boşluk göstergesi (ayar açıksa)
            if self.ayarlar.get("bosluk_gostergesi"):
                tb.tag_config("bosluk", underline=True,
                              foreground=self.colors.get("line_number", "#858585"))
                for m in re.finditer(r'[ \t]+', metin):
                    tb.tag_add("bosluk", tk_idx(m.start()), tk_idx(m.end()))
        except Exception:
            pass

    def mevcut_kelimeyi_al(self):
        cursor_pos = self.kod_alani.index("insert")
        satir, sutun = cursor_pos.split(".")
        satir_metni = self.kod_alani.get(f"{satir}.0", cursor_pos)
        match = re.search(r"([a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]+)$", satir_metni)
        if match:
            baslangic_col = match.start(1)
            return match.group(1), f"{satir}.{baslangic_col}", cursor_pos
        return "", cursor_pos, cursor_pos

    def popup_goster(self, kelime, bas_idx, bit_idx):
        if not self.ayarlar.get("otomatik_tamamlama"):
            return
        
        tum_kelimeler = self._tamamlama_kelime_listesi_al()
        if not tum_kelimeler:
            return
        
        # Eşleşmeleri bul
        eslesmeler = []
        kod_tanimlari = self._koddan_tanimlari_cikar(self.kod_alani.get("1.0", "end-1c"))
        for k in kod_tanimlari:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                eslesmeler.append(("📌", k))
        for k in TURKCE_KELIMELER:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                if k not in [x[1] for x in eslesmeler]:
                    eslesmeler.append(("📚", k))
        
        if not eslesmeler or len(kelime) < 2:
            self.popup_kapat()
            return

        # Tema renklerini al
        bg_color = self.colors.get("sidebar", "#252526")
        fg_color = self.colors.get("text", "#d4d4d4")
        select_bg = self.colors.get("selection", "#04395e")
        select_fg = "#ffffff"
        border_color = self.colors.get("border", "#3c3c3c")

        if not self.popup:
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            self.popup.wm_attributes("-topmost", True)

            self.listbox = tk.Listbox(
                self.popup, 
                bg=bg_color, 
                fg=fg_color, 
                selectbackground=select_bg,
                selectforeground=select_fg, 
                font=("Consolas", 11), 
                bd=1, 
                relief="solid",
                highlightbackground=border_color,
                highlightcolor=border_color
            )
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<Double-Button-1>", lambda e: self.kelime_tamamla())
            self.listbox.bind("<Return>", lambda e: self.kelime_tamamla())

        # Renkleri güncelle (tema değişiminde)
        self.listbox.configure(
            bg=bg_color,
            fg=fg_color,
            selectbackground=select_bg,
            highlightbackground=border_color
        )
        self.popup.configure(bg=bg_color)

        self.listbox.delete(0, tk.END)
        for ikon, item in eslesmeler[:15]:
            self.listbox.insert(tk.END, f"{ikon} {item}")
        self.listbox.select_set(0)
        
        try:
            bbox = self.kod_alani._textbox.bbox("insert")
            if bbox:
                x = self.kod_alani.winfo_rootx() + bbox[0] + 10
                y = self.kod_alani.winfo_rooty() + bbox[1] + bbox[3] + 25
                self.popup.geometry(f"260x180+{x}+{y}")
                self.popup.deiconify()
                self.popup.lift()
            else:
                x = self.kod_alani.winfo_rootx() + 50
                y = self.kod_alani.winfo_rooty() + 50
                self.popup.geometry(f"260x180+{x}+{y}")
                self.popup.deiconify()
        except Exception as e:
            self.popup_kapat()

    def popup_kapat(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.listbox = None

    def kelime_tamamla(self):
        if self.popup and self.listbox and self.listbox.curselection():
            secilen = self.listbox.get(self.listbox.curselection()[0])
            secilen = secilen.replace("📌 ", "").replace("📚 ", "")
            
            kelime, bas, bit = self.mevcut_kelimeyi_al()
            if kelime:
                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, secilen)
                self.popup_kapat()
                self.after(50, self.kod_renklendir)
                return "break"
        self.popup_kapat()
        return None
    def _turkce_karakter_kontrol(self):
        """Türkçe karakter içeren değişken/fonksiyon isimlerini uyarı olarak işaretle"""
        try:
            self.kod_alani.tag_remove("turkce_uyari", "1.0", "end")
            
            turkce_harfler = "çğıöşüÇĞİÖŞÜ"
            kod = self.kod_alani.get("1.0", "end-1c")
            
            # Değişken/fonksiyon tanımlarını bul
            import re
            
            # fonksiyon isim(...)
            for match in re.finditer(r'fonksiyon\s+([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)', kod):
                isim = match.group(1)
                if any(h in isim for h in turkce_harfler):
                    # Satır ve sütun bul
                    satir = kod[:match.start(1)].count('\n') + 1
                    satir_bas = kod.rfind('\n', 0, match.start(1)) + 1
                    sutun = match.start(1) - satir_bas
                    self.kod_alani.tag_add("turkce_uyari", f"{satir}.{sutun}", f"{satir}.{sutun + len(isim)}")
            
            # değişken = ...
            for match in re.finditer(r'^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=', kod, re.MULTILINE):
                isim = match.group(1)
                if any(h in isim for h in turkce_harfler):
                    satir = kod[:match.start(1)].count('\n') + 1
                    satir_bas = kod.rfind('\n', 0, match.start(1)) + 1
                    sutun = match.start(1) - satir_bas
                    self.kod_alani.tag_add("turkce_uyari", f"{satir}.{sutun}", f"{satir}.{sutun + len(isim)}")
            
            # Stil
            self.kod_alani.tag_config("turkce_uyari", underline=True, foreground="#ff9800")
            
        except Exception:
            pass
    def on_key_release(self, event):
        if event.keysym in ["Up", "Down", "Return", "Tab", "Escape"]:
            return
        
        self.kod_renklendir()
        kelime, bas, bit = self.mevcut_kelimeyi_al()
        if kelime:
            self.popup_goster(kelime, bas, bit)
        else:
            self.popup_kapat()
        
        # Syntax kontrolü - önceki timer'ı iptal et
        if hasattr(self, '_syntax_timer') and self._syntax_timer:
            self.after_cancel(self._syntax_timer)
        self._syntax_timer = self.after(500, self._syntax_kontrol)
        
        # Türkçe karakter uyarısı
        self._turkce_karakter_kontrol()
    def _syntax_kontrol(self):
        """Kodu AST ile kontrol et, hatalı satırları kırmızı alt çizgi ile işaretle"""
        try:
            # Önceki hata etiketlerini temizle
            self.kod_alani.tag_remove("syntax_hata", "1.0", "end")
            
            turkce_kod = self.kod_alani.get("1.0", "end-1c")
            if not turkce_kod.strip():
                return
            
            # TürKod'u Python'a çevir
            python_kodu = turkce_kodu_donustur(turkce_kod)
            
            # AST parse dene
            import ast
            try:
                ast.parse(python_kodu)
                self.status_left.configure(text="  ✓ Sözdizimi doğru")
                return
            except SyntaxError as e:
                if e.lineno:
                    hata_satir = e.lineno
                    self.kod_alani.tag_add("syntax_hata", f"{hata_satir}.0", f"{hata_satir}.end")
                    self.status_left.configure(text=f"  ⚠ Sözdizimi hatası: Satır {hata_satir}")
            
            # Hata etiketi stili
            renk = "#ffdcdc" if self.tema == "Açık" else "#5a1d1d"
            self.kod_alani.tag_config("syntax_hata", background=renk, underline=True)
            
        except Exception:
            pass
    def _tab_indent(self, event=None):
        """Tab: Seçili satırları sağa kaydır, yoksa otomatik tamamlama veya boşluk"""
        try:
            if self.popup:
                return self.kelime_tamamla()
            
            # Seçili metin var mı?
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                bas_satir = int(bas.split(".")[0])
                bit_satir = int(bit.split(".")[0])
                
                # Her satırın başına 4 boşluk ekle
                for satir_no in range(bas_satir, bit_satir + 1):
                    self.kod_alani.insert(f"{satir_no}.0", "    ")
                
                # Seçimi güncelle
                yeni_bas = f"{bas_satir}.0"
                yeni_bit = f"{bit_satir}.end"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", yeni_bas, yeni_bit)
                
                self.sync_line_numbers()
                return "break"
            else:
                # Normal tab davranışı (otomatik tamamlama veya 4 boşluk)
                self.kod_alani.insert("insert", "    ")
                return "break"
        except Exception:
            self.kod_alani.insert("insert", "    ")
            return "break"
    def on_return_key(self, event):
        if self.popup:
            return self.kelime_tamamla()

    def on_arrow_down(self, event):
        if self.popup and self.listbox:
            idx = self.listbox.curselection()
            if idx:
                sonraki = min(idx[0] + 1, self.listbox.size() - 1)
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(sonraki)
            return "break"
        return None  # ← Ekle: Popup yoksa imleç normal hareket etsin

    def on_arrow_up(self, event):
        if self.popup and self.listbox:
            idx = self.listbox.curselection()
            if idx:
                onceki = max(idx[0] - 1, 0)
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(onceki)
            return "break"
        return None  # ← Ekle

    def dosya_ac(self):
        path = filedialog.askopenfilename(title="Dosya Seç", filetypes=[("Türkçe Python", "*.trpy")])
        if path:
            self._yeni_sekme_olustur(yol=path)
    def _kod_dili_tespit(self, kod):
        """Puanlama ile tespit: TürKod mu Python mu?"""
        turkod = len(re.findall(
            r"\b(fonksiyon|dondur|sinif|eger|degilse_eger|degilse|dongu|icinde|"
            r"yazdir|girdi_al|ice_aktar|dene|hata_yakala|sonunda|kir|devam_et)\b", kod))
        python = len(re.findall(
            r"\b(def|return|class|if|elif|else|for|while|print|input|import|"
            r"from|try|except|finally|break|continue)\b", kod))
        if turkod == python:
            return "turkod"
        return "turkod" if turkod > python else "python"

    def _kodu_cevir(self, event=None):
        kod = self.kod_alani.get("1.0", "end-1c")
        if not kod.strip():
            self.status_left.configure(text="  Çevrilecek kod yok.")
            return "break"

        dil = self._kod_dili_tespit(kod)

        if dil == "turkod":
            sonuc = turkce_kodu_donustur(kod)
            kaynak, hedef, uzanti = "TürKod", "Python", ".py"
        else:
            sonuc = python_kodu_turkceye_cevir(kod)
            kaynak, hedef, uzanti = "Python", "TürKod", ".trpy"

        # Orijinal bozulmasın diye sonucu yeni sekmede aç
        sekme = self._aktif_sekme()
        taban = os.path.splitext(sekme["isim"])[0] if sekme else "cevrilmis"
        self._yeni_sekme_olustur(isim=taban + uzanti, icerik=sonuc)

        self.status_left.configure(text=f"  {kaynak} → {hedef} çevrildi, yeni sekmede açıldı.")
        return "break"
    def dosya_kaydet(self):
        sekme = self._aktif_sekme()
        if not sekme:
            return

        sekme["icerik"] = self.kod_alani.get("1.0", "end")

        if sekme["yol"]:
            with open(sekme["yol"], "w", encoding="utf-8") as f:
                f.write(sekme["icerik"])
            sekme["degisti"] = False
            sekme["isim"] = os.path.basename(sekme["yol"])
            self._sekme_baslik_guncelle()
            self.status_left.configure(text=f"  Kaydedildi: {sekme['isim']}")
        else:
            path = filedialog.asksaveasfilename(title="Kaydet", defaultextension=".trpy",
                                                 filetypes=[("Türkçe Python", "*.trpy")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(sekme["icerik"])
                sekme["yol"] = path
                sekme["isim"] = os.path.basename(path)
                sekme["degisti"] = False
                self._sekme_baslik_guncelle()
                self._status_guncelle()

    def kodu_calistir(self):
        # Önceki çalışan process'i kapat
        if self._calistirma_process is not None:
            try:
                self._calistirma_process.terminate()
                self._calistirma_process.wait(timeout=2)
            except:
                try:
                    self._calistirma_process.kill()
                except:
                    pass
            self._calistirma_process = None
        turkce_kod = self.kod_alani.get("1.0", "end")
        python_kodu = turkce_kodu_donustur(turkce_kod)

        temp_dir = tempfile.gettempdir()
        kod_path = os.path.join(temp_dir, "turkce_kod_calisma.py")
        runner_path = os.path.join(temp_dir, "runner.py")

        with open(kod_path, "w", encoding="utf-8") as f:
            f.write(python_kodu)

        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(RUNNER_KODU)

        # ==================== PYTHON BULMA ====================
        python_exe = None
        
        if getattr(sys, 'frozen', False):
            # 1. Önce _internal/python_embed/ var mı? (taşınabilir Python)
            exe_dir = os.path.dirname(sys.executable)
            embed_python = os.path.join(exe_dir, "_internal", "python_embed", "python.exe")
            if os.path.exists(embed_python):
                python_exe = embed_python
            
            # 2. Yoksa sistemdeki Python'u dene
            if not python_exe:
                import shutil
                python_exe = shutil.which("python.exe") or shutil.which("python")
                
            # 3. Hala yoksa hata ver
            if not python_exe:
                messagebox.showerror(
                    "Python Gerekli",
                    "Kodu çalıştırmak için Python 3.x gerekli.\n\n"
                    "Python kurulu olmayan bilgisayarlarda:\n"
                    "1. https://python.org/downloads adresinden indirin\n"
                    "2. Kurulumda 'Add Python to PATH' seçeneğini işaretleyin\n\n"
                    "Veya geliştirici modunda taşınabilir Python paketini "
                    "_internal/python_embed/ klasörüne ekleyin."
                )
                return
        else:
            python_exe = sys.executable
            if python_exe.endswith("pythonw.exe"):
                python_exe = python_exe.replace("pythonw.exe", "python.exe")

        # ==================== CALISTIRMA ====================
        if not self.terminal_visible:
            self._terminal_toggle()
        self._terminal_yazdir(f"\n> python -u runner.py\n")

        cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._calistirma_process = subprocess.Popen(
            [python_exe, "-X", "utf8", "-u", runner_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=cf
        )
        threading.Thread(target=self._terminal_oku, args=(self._calistirma_process,), daemon=True).start()
        self.status_left.configure(text="  Kod calistiriliyor...")
    # ============ ENTEGRE TERMİNAL ============
    def _terminal_toggle(self, event=None):
        if getattr(self, "terminal_visible", False):
            self.terminal_frame.grid_remove()
            self.terminal_grip.grid_remove()
            self.terminal_visible = False
        else:
            self.terminal_grip.grid(row=2, column=3, sticky="ew")
            self.terminal_frame.grid(row=3, column=3, sticky="nsew")
            self.terminal_visible = True
        return "break"
    def _terminal_grip_basla(self, event):
        self._tg_baslangic_y = event.y_root
        self._tg_baslangic_h = self.terminal_frame.winfo_height()
        self._grip_aktif = True

    def _terminal_grip_surukle(self, event):
        if not self._grip_aktif:
            return
        delta = self._tg_baslangic_y - event.y_root   # yukarı çek = büyüt
        yeni = max(80, min(600, self._tg_baslangic_h + delta))
        y_pos = self.terminal_frame.winfo_y() - (yeni - self._tg_baslangic_h)
        self._ghost_line_y.place(x=self.editor_frame.winfo_x(), y=y_pos,
                                 width=self.editor_frame.winfo_width(), height=2)
        self._ghost_line_y.lift()
        self._tg_yeni = yeni

    def _terminal_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line_y.place_forget()
        yeni = getattr(self, "_tg_yeni", self.terminal_frame.winfo_height())
        self.terminal_frame.configure(height=int(yeni))
        self.grid_rowconfigure(3, minsize=int(yeni))
        self.update_idletasks()
    def _terminal_yazdir(self, metin):
        self.terminal_output.configure(state="normal")
        self.terminal_output.insert("end", metin)
        self.terminal_output.see("end")
        self.terminal_output.configure(state="disabled")

    def _terminal_temizle(self):
        self.terminal_output.configure(state="normal")
        self.terminal_output.delete("1.0", "end")
        self.terminal_output.configure(state="disabled")

    def _terminal_enter(self, event=None):
        komut = self.terminal_input.get().strip()
        self.terminal_input.delete(0, "end")
        if not komut:
            return "break"

        self._terminal_yazdir(f"> {komut}\n")

        proc = getattr(self, "_calistirma_process", None)
        # Kod çalışıyorsa yazılanı input()'a gönder
        if proc is not None and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write(komut + "\n")
                proc.stdin.flush()
            except Exception:
                pass
            return "break"

        # Kod çalışmıyorsa sistem komutu olarak çalıştır
        threading.Thread(target=self._terminal_komut_calistir, args=(komut,), daemon=True).start()
        return "break"

    def _terminal_komut_calistir(self, komut):
        try:
            cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            cwd = self.proje_dizini if self.proje_dizini and os.path.exists(self.proje_dizini) else os.getcwd()
            sonuc = subprocess.run(
                komut, shell=True, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=cf
            )
            self.after(0, self._terminal_yazdir, (sonuc.stdout or "") + "\n")
        except Exception as e:
            self.after(0, self._terminal_yazdir, f"[Hata: {e}]\n")

    def _terminal_oku(self, process):
        import codecs
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        fd = process.stdout.fileno()
        try:
            while True:
                ham = os.read(fd, 4096)   # \n beklemez, veri gelince döner
                if not ham:
                    break
                metin = cozucu.decode(ham)
                if metin:
                    self.after(0, self._terminal_yazdir, metin)
            kalan = cozucu.decode(b"", final=True)
            if kalan:
                self.after(0, self._terminal_yazdir, kalan)
            kod = process.wait()
            self.after(0, self._terminal_yazdir, f"\n[Process {kod} koduyla çıktı]\n")
        except Exception as e:
            self.after(0, self._terminal_yazdir, f"[Terminal okuma hatası: {e}]\n")
        finally:
            self._calistirma_process = None
    def _pencere_kapat(self):
        degisikler = [s for s in self.sekmeler if s["degisti"]]
        if degisikler:
            isimler = ", ".join(s["isim"] for s in degisikler)
            cevap = messagebox.askyesnocancel("Çıkış",
                f"Kaydedilmemiş dosyalar: {isimler}\nKaydedilsin mi?")
            if cevap is None:
                return
            if cevap:
                for s in degisikler:
                    if s["yol"]:
                        icerik = self.kod_alani.get("1.0", "end-1c") if s["id"] == self.aktif_sekme_id else s["icerik"]
                        try:
                            with open(s["yol"], "w", encoding="utf-8") as f:
                                f.write(icerik)
                        except Exception:
                            pass
        self.destroy()
class BasitDebugger:
    """Basit satır satır hata ayıklayıcı"""
    
    def __init__(self, ide):
        self.ide = ide
        self.breakpoints = set()  # {satir_no}
        self.calistiriliyor = False
        self.mevcut_satir = 0
        self._highlight_tag = "breakpoint"
        self._current_tag = "debug_current"
    
    def breakpoint_toggle(self, satir):
        """Satırda breakpoint aç/kapat"""
        if satir in self.breakpoints:
            self.breakpoints.remove(satir)
            self.ide.kod_alani.tag_remove(self._highlight_tag, f"{satir}.0", f"{satir}.end")
        else:
            self.breakpoints.add(satir)
            self.ide.kod_alani.tag_add(self._highlight_tag, f"{satir}.0", f"{satir}.end")
            renk = "#ffdcdc" if self.tema == "Açık" else "#5a1d1d"
            self.ide.kod_alani.tag_config(self._highlight_tag, background=renk)
    def baslat(self):
        """Debugger'ı başlat"""
        if not self.breakpoints:
            messagebox.showwarning("Debugger", "Önce breakpoint ekleyin! (Satır numarasına tıklayın)")
            return
        
        self.calistiriliyor = True
        self.mevcut_satir = min(self.breakpoints)
        self._vurgula(self.mevcut_satir)
        self.ide.status_left.configure(text=f"  ⏸ Debugger: Satır {self.mevcut_satir}")
    
    def adim(self):
        """Bir sonraki satıra geç"""
        if not self.calistiriliyor:
            return
        
        self._vurgula_kaldir(self.mevcut_satir)
        
        # Sonraki breakpoint veya satır
        sonraki = sorted([b for b in self.breakpoints if b > self.mevcut_satir])
        if sonraki:
            self.mevcut_satir = sonraki[0]
            self._vurgula(self.mevcut_satir)
            self.ide.status_left.configure(text=f"  ⏸ Debugger: Satır {self.mevcut_satir}")
        else:
            self.durdur()
    
    def devam_et(self):
        """Sonraki breakpoint'e kadar çalıştır"""
        if not self.calistiriliyor:
            self.baslat()
            return
        self.adim()
    
    def durdur(self):
        """Debugger'ı durdur"""
        self.calistiriliyor = False
        if self.mevcut_satir:
            self._vurgula_kaldir(self.mevcut_satir)
        self.ide.status_left.configure(text="  ■ Debugger durduruldu")
    
    def _vurgula(self, satir):
        """Mevcut satırı vurgula"""
        self.ide.kod_alani.tag_add(self._current_tag, f"{satir}.0", f"{satir}.end")
        self.ide.kod_alani.tag_config(self._current_tag, background="#264f78")
        self.ide.kod_alani.see(f"{satir}.0")
    
    def _vurgula_kaldir(self, satir):
        """Vurguyu kaldır"""
        self.ide.kod_alani.tag_remove(self._current_tag, f"{satir}.0", f"{satir}.end")
if __name__ == "__main__":
    app = TurkceIDE()
    app.mainloop()
