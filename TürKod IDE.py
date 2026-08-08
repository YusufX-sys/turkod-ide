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
import re
import subprocess
import tempfile
import json
import threading
import time
from datetime import datetime
import ast

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
    # TürKod'da değişken tanımı doğrudan atama ile olur
    degiskenler = re.findall(r'^([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\s*=', kod, re.MULTILINE)
    tanimlar.update(degiskenler)
    
    # self.degisken atamaları
    self_degiskenler = re.findall(r'\bself\.([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)\b', kod)
    tanimlar.update(self_degiskenler)
    
    # Parametre isimleri: fonksiyon isim(param1, param2):
    parametreler = re.findall(r'\bfonksiyon\s+[a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüı]*\s*\(([^)]*)\)', kod)
    for param_grup in parametreler:
        for param in param_grup.split(','):
            param = param.strip().split('=')[0].strip()  # Varsayılan değeri at
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
# Turkce-Python referans listesi (AI icin dahili kullanim, ayarlarda gorunmez)
# ============ PYTHON'DAN TÜRKOD'A ÇEVİRİ ============
# ============ SOZLUK (Turkish to Python) ============
def _sozluk_yukle(dosya_adi="TürKod Sözlüğü.txt"):
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
    """Python kodunu TürKod'a çevir"""
    saklanan_metinler = []

    def sakla(match):
        saklanan_metinler.append(match.group(0))
        return f"__METIN_SABITI_{len(saklanan_metinler)-1}__"

    string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
    gecici_kod = re.sub(string_ve_yorum, sakla, python_kodu)

    # Uzunluk sırasına göre sırala (çakışma önleme)
    sirali = sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True)

    for py_kelime, tr_kelime in sirali:
        gecici_kod = re.sub(rf'\b{re.escape(py_kelime)}\b', tr_kelime, gecici_kod)

    for i, metin in enumerate(saklanan_metinler):
        gecici_kod = gecici_kod.replace(f"__METIN_SABITI_{i}__", metin)

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
            Sen ise Python kodu yazdığında program onu çevirerek kullanıcıya doğru olanı gösteriyor bu yüzden Python kodu yazmalısın.
            KURALLAR:
            - Kod verirken MUTLAKA ```TürKod ve ``` arasina yaz.
            - Aciklama kismi duz metin, kod kismi ayri blok olmali.
            -Sadece Python kodları ver başka bir dil kullanamazsın.
            """,
            "ai_sicaklik": 0.7,
            "ai_max_token": 2048,
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
    "Acik": {
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
    "Yuksek Kontrast": {
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

# ============ SOZLUK (Turkish to Python) ============
def _sozluk_yukle(dosya_adi="TürKod Sözlüğü.txt"):
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
    
# ============ KELIME LISTESI (Otomatik Tamamlama Icin) ============
def sozlukten_kelime_listesi():
    """SOZLUK'ten temiz Türkçe kelime listesi çıkar - önbellekli"""
    cache_dosya = os.path.join(os.path.expanduser("~"), ".turkod_kelimeler.json")
    
    if os.path.exists(cache_dosya):
        try:
            with open(cache_dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
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
    import requests
    
    try:
        resp = requests.get("[https://api.groq.com/openai/v1/models](https://api.groq.com/openai/v1/models)", timeout=8)
        if resp.status_code == 200:
            modeller = [m["id"] for m in resp.json().get("data", [])]
            modeller = [m for m in modeller if "whisper" not in m.lower()]
            if modeller:
                AI_MODELLERI["Groq"] = sorted(modeller)
                print(f"[TurKod] Groq modelleri guncellendi: {len(modeller)} model")
    except Exception as e:
        print(f"[TurKod] Groq guncelleme hatasi: {e}")
    
    try:
        resp = requests.get("[https://api.openai.com/v1/models](https://api.openai.com/v1/models)", timeout=8)
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
    saklanan_metinler = []

    def sakla(match):
        saklanan_metinler.append(match.group(0))
        return f"__METIN_SABITI_{len(saklanan_metinler)-1}__"

    string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
    gecici_kod = re.sub(string_ve_yorum, sakla, turkce_kod)

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
            "simdi": "now", "bugun": "today", "zaman_farki": "timedelta",
            "tarih_bicimlendir": "strftime", "tarih_ayristir": "strptime",
            "zaman_damgasi": "timestamp", "haftanin_gunu": "weekday",
            "tarih": "date", "zaman": "time", "saat_dilimi": "timezone",
            "dilim_bilgisi": "tzinfo", "iso_format": "isoformat",
            "iso_ayristir": "fromisoformat", "metin_zaman": "ctime",
            "yer_degistir": "replace", "utc_simdi": "utcnow",
            "utc_damgasi": "utcfromtimestamp", "damga_zaman": "fromtimestamp",
            "tarih_birlestir": "combine", "en_kucuk_tarih": "min",
            "en_buyuk_tarih": "max", "cozunurluk": "resolution",
        }
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

    for turkce, python_karsiligi in SOZLUK.items():
        python_kodu = re.sub(turkce, python_karsiligi, python_kodu)

    for i, metin in enumerate(saklanan_metinler):
        python_kodu = python_kodu.replace(f"__METIN_SABITI_{i}__", metin)

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
        self._kod_tanimlari_cache = []
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
        
    def _arayuz_olustur(self):
        # === AKTIVITE BAR (sol en dar) ===
        self.activity_bar = ctk.CTkFrame(self, width=48, fg_color=self.colors["activity_bar"])
        self.activity_bar.grid(row=0, column=0, rowspan=3, sticky="nsew")
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
        self.sidebar.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(0, 0))
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

        # === TAB BAR ===
        self.tab_bar = ctk.CTkFrame(self, height=38, fg_color=self.colors["tab_inactive"])
        self.tab_bar.grid(row=0, column=3, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tab_bar.grid_columnconfigure(0, weight=1)

        self.sekmeler_container = ctk.CTkFrame(self.tab_bar, fg_color="transparent", height=38)
        self.sekmeler_container.grid(row=0, column=0, sticky="w")
        self.sekmeler_container.grid_propagate(False)

        self.tab_buttons = ctk.CTkFrame(self.tab_bar, fg_color="transparent")
        self.tab_buttons.grid(row=0, column=1, sticky="e", padx=10)

        self.yeni_sekme_btn = ctk.CTkButton(self.tab_buttons, text="＋", width=30, height=26,
                                             command=self._yeni_sekme_olustur,
                                             fg_color=self.colors["button_bg"],
                                             hover_color=self.colors["button_hover"],
                                             border_color=self.colors["border"],
                                             border_width=2,
                                             font=("Segoe UI", 14, "bold"), corner_radius=8)
        self.yeni_sekme_btn.pack(side="left", padx=3)

        self.calistir_btn = ctk.CTkButton(self.tab_buttons, text="▶  Çalıştır", width=90, height=26,
                                           command=self.kodu_calistir, fg_color="#28a745",
                                           border_color=self.colors["border"],
                                           border_width=2,
                                           hover_color="#218838", font=("Segoe UI", 14),
                                           corner_radius=8)
        self.calistir_btn.pack(side="left", padx=3)

        self.ac_btn = ctk.CTkButton(self.tab_buttons, text="📂 Aç", width=60, height=26,
                                     command=self.dosya_ac, fg_color=self.colors["button_bg"],
                                     hover_color=self.colors["button_hover"],
                                     border_color=self.colors["border"],
                                     border_width=2,
                                     font=("Segoe UI ", 14), corner_radius=8)
        self.ac_btn.pack(side="left", padx=3)

        self.kaydet_btn = ctk.CTkButton(self.tab_buttons, text="📃 Kaydet", width=70, height=26,
                                         command=self.dosya_kaydet, fg_color=self.colors["button_bg"],
                                         hover_color=self.colors["button_hover"],
                                         border_color=self.colors["border"],
                                         border_width=2,
                                         font=("Segoe UI", 14), corner_radius=8)
        self.kaydet_btn.pack(side="left", padx=3)
        
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
            wrap="none" if not self.ayarlar.get("kelime_sar") else "word"
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
        self.ai_panel.grid(row=0, column=5, rowspan=3, sticky="nsew")
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
                          
        # === STATUS BAR ===
        self.status_bar = ctk.CTkFrame(self, height=24, fg_color=self.colors["status_bar"])
        self.status_bar.grid(row=2, column=3, sticky="ew")
        self.status_bar.grid_propagate(False)

        self.status_left = ctk.CTkLabel(self.status_bar,
                                         text="  Python 3.x | TürKod Hazır",
                                         font=("Segoe UI", 9, "bold"), text_color="white")
        self.status_left.place(rely=0.5, anchor="w")

        self.status_right = ctk.CTkLabel(self.status_bar,
                                          text="UTF-8 | TRPY ",
                                          font=("Segoe UI", 9, "bold"), text_color="white")
        self.status_right.place(relx=1.0, rely=0.5, anchor="e")

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
        self.renk_ayarlarini_yap()
        if self.proje_dizini and os.path.exists(self.proje_dizini):
            self.after(200, self._dosya_tree_guncelle)

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
        self.sidebar_grip.grid(row=0, column=2, rowspan=3, sticky="ns")
        self.sidebar_grip.configure(cursor="sb_h_double_arrow")
        
        self.sidebar_grip.bind("<Button-1>", self._sidebar_grip_basla)
        self.sidebar_grip.bind("<B1-Motion>", self._sidebar_grip_surukle)
        self.sidebar_grip.bind("<ButtonRelease-1>", self._sidebar_grip_birak)
        self.sidebar_grip.bind("<Enter>", lambda e: self.sidebar_grip.configure(fg_color="#007acc"))
        self.sidebar_grip.bind("<Leave>", lambda e: self.sidebar_grip.configure(fg_color="#3c3c3c"))
        
        self.ai_grip = ctk.CTkFrame(self, width=4, fg_color="#3c3c3c")
        self.ai_grip.grid(row=0, column=4, rowspan=3, sticky="ns")
        self.ai_grip.configure(cursor="sb_h_double_arrow")
        
        self.ai_grip.bind("<Button-1>", self._ai_grip_basla)
        self.ai_grip.bind("<B1-Motion>", self._ai_grip_surukle)
        self.ai_grip.bind("<ButtonRelease-1>", self._ai_grip_birak)
        self.ai_grip.bind("<Enter>", lambda e: self.ai_grip.configure(fg_color="#007acc"))
        self.ai_grip.bind("<Leave>", lambda e: self.ai_grip.configure(fg_color="#3c3c3c"))

    def _ai_input_focus(self, event=None):
        if self.ai_input.get("1.0", "end-1c").strip() == "Bir şey sor...":
            self.ai_input.delete("1.0", "end")

    def _ai_input_blur(self, event=None):
        if not self.ai_input.get("1.0", "end-1c").strip():
            self.ai_input.insert("1.0", "Bir şey sor...")

    def renk_ayarlarini_yap(self):
        for tag in ["keyword", "builtin", "string", "comment", "number"]:
            self.kod_alani.tag_config(tag, foreground=self.colors.get(tag, "#d4d4d4"))

    def _senkronize_scroll(self, event=None):
        """Kod alanının scroll pozisyonunu satır numaralarına ve minimapa uygula"""
        try:
            first, last = self.kod_alani.yview()
            if self.ayarlar.get("satir_numaralari"):
                self.line_numbers.yview_moveto(first)
            if hasattr(self, 'minimap') and self.ayarlar.get("minimap"):
                self.minimap.yview_moveto(first)
        except Exception:
            pass
        
        if event and event.type == "38":  
            return None  

    def _baglayicilari_ayarla(self):
        self.kod_alani.bind("<KeyRelease>", self.on_key_release)
        self.kod_alani.bind("<Tab>", self.on_tab_key)
        self.kod_alani.bind("<Return>", self.on_return_key)
        self.kod_alani.bind("<Down>", self.on_arrow_down)
        self.kod_alani.bind("<Up>", self.on_arrow_up)
        self.kod_alani.bind("<Escape>", lambda e: self.popup_kapat())
        self.kod_alani.bind("<FocusOut>", lambda e: self.popup_kapat()) 
        self.kod_alani.bind("<Button-1>", lambda e: self.popup_kapat(), add="+") 
        self.kod_alani.bind("<Key>", lambda e: self.after_idle(self.sync_line_numbers))
        self.kod_alani.bind("<ButtonRelease>", lambda e: self.after_idle(self.sync_line_numbers))
        self.kod_alani.bind("<Control-s>", lambda e: self.dosya_kaydet())
        self.kod_alani.bind("<Control-o>", lambda e: self.dosya_ac())
        self.kod_alani.bind("<Control-r>", lambda e: self.kodu_calistir())
        self.kod_alani.bind("<F5>", lambda e: self.kodu_calistir())
        self.kod_alani.bind("<Key>", self._dosya_degisti_kontrol, add="+")
        self.kod_alani.bind("<MouseWheel>", self._senkronize_scroll)
        self.kod_alani.bind("<Button-4>", self._senkronize_scroll)
        self.kod_alani.bind("<Button-5>", self._senkronize_scroll)
        self.kod_alani._y_scrollbar.bind("<B1-Motion>", lambda e: self._senkronize_scroll())
        self.kod_alani._y_scrollbar.bind("<ButtonRelease-1>", lambda e: self._senkronize_scroll())

        self.popup = None
        self.listbox = None

    def _dosya_degisti_kontrol(self, event=None):
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
            
            def _yukle():
                try:
                    with os.scandir(tam_yol) as entries:
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
                        
                        def _ekle():
                            for entry in klasorler:
                                yol = entry.path
                                node = self.dosya_tree.insert(
                                    item, "end",
                                    text=f"📁 {entry.name}",
                                    values=(yol, "directory", "collapsed"),
                                    tags=("directory",)
                                )
                                self.dosya_tree.insert(node, "end", text="⏳ Yükleniyor...", 
                                                       values=("", "dummy"), tags=("dummy",))
                            
                            for entry in dosyalar:
                                yol = entry.path
                                uzanti = os.path.splitext(entry.name)[1].lower()
                                if uzanti == ".trpy":
                                    icon, tag = "📄", "trpy"
                                elif uzanti == ".py":
                                    icon, tag = "🐍", "python"
                                else:
                                    icon, tag = "📄", "other"
                                
                                self.dosya_tree.insert(
                                    item, "end",
                                    text=f"{icon} {entry.name}",
                                    values=(yol, "file"),
                                    tags=(tag,)
                                )
                            
                            if fazla_mesaj:
                                self.dosya_tree.insert(item, "end", text=fazla_mesaj,
                                                       values=("", "dummy"), tags=("dummy",))
                            
                            self.dosya_tree.item(item, values=(tam_yol, "directory", "expanded"))
                            self.dosya_tree.item(item, open=True)
                        
                        self.after(0, _ekle)
                        
                except Exception as e:
                    print(f"[TurKod] Ağaç açma hatası: {e}")
            
            threading.Thread(target=_yukle, daemon=True).start()
            
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
            self.sidebar.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(0, 0))
            self.sidebar_grip.grid(row=0, column=2, rowspan=3, sticky="ns")
            self.grid_columnconfigure(1, minsize=220)  
            self.explorer_btn.configure(text="◀")

    # ============ AI PANEL ============
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
            self._sekme_aktif_yap(sid)  
            cevap = messagebox.askyesnocancel("Kaydet?",
                f"'{sekme['isim']}' için değişiklikler kaydedilsin mi?")
            if cevap is None:
                return
            if cevap:
                self.dosya_kaydet()

        sekme["frame"].destroy()
        self.sekmeler.remove(sekme)

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
        isim = sekme["isim"]
        if sekme["degisti"]:
            isim += " ●"
        sekme["label"].configure(text=isim)

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
        frame = ctk.CTkFrame(parent, fg_color="#1e1e1e", corner_radius=6, 
                            border_width=1, border_color="#3c3c3c")
        
        bar = ctk.CTkFrame(frame, fg_color="#252526", height=32, corner_radius=0)
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
                                    fg_color="#1e1e1e", text_color="#d4d4d4",
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
            self.ai_panel.grid(row=0, column=5, rowspan=3, sticky="nsew")
            self.ai_grip.grid(row=0, column=4, rowspan=3, sticky="ns")
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
        
        for parca in parcalar:
            if parca[0] == "metin":
                text = parca[1]
                text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
                text = re.sub(r'\*(.*?)\*', r'\1', text)
                
                msg_lbl = ctk.CTkLabel(bubble, text=text,
                                        font=("Segoe UI", 11),
                                        text_color=self.colors["text"],
                                        wraplength=400, justify="left")
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

    def _ai_kodu_duzelt(self):
        kod = self.kod_alani.get("1.0", "end-1c").strip()
        if not kod:
            self._ai_mesaj_ekle("assistant", "⚠️ Düzenlenecek kod bulunamadı.")
            return
        prompt = f"""Aşağıdaki TürKod kodundaki hataları bul ve düzelt:
```TürKod
{kod}
Yapacakların:
- Bulduğun hataları listele
- Düzeltilmiş kodu Türkod bloğunda ver"""
        self._ai_gonder_prompt(prompt)

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
        pencere.title("Ayarlar")
        pencere.geometry("600x800")
        pencere.transient(self)
        pencere.grab_set()

        notebook = ctk.CTkTabview(pencere, width=560, height=620)
        notebook.pack(padx=20, pady=20)

        # === GENEL AYARLAR ===
        notebook.add("Genel")
        genel = notebook.tab("Genel")

        ctk.CTkLabel(genel, text="Tema:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        tema_var = ctk.StringVar(value=self.ayarlar.get("tema"))
        tema_combo = ctk.CTkOptionMenu(genel, values=list(TEMA_RENKLERI.keys()), variable=tema_var)
        tema_combo.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazi Tipi:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        yazi_var = ctk.StringVar(value=self.ayarlar.get("yazi_tipi"))
        yazi_combo = ctk.CTkOptionMenu(genel, values=["Consolas", "Courier New", "Fira Code", "JetBrains Mono", "Source Code Pro"], variable=yazi_var)
        yazi_combo.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazi Boyutu:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        boyut_var = ctk.IntVar(value=self.ayarlar.get("yazi_boyutu"))
        boyut_slider = ctk.CTkSlider(genel, from_=8, to=32, number_of_steps=24, variable=boyut_var)
        boyut_slider.pack(fill="x", padx=10, pady=5)
        boyut_label = ctk.CTkLabel(genel, textvariable=boyut_var)
        boyut_label.pack(anchor="w", padx=10)

        satir_var = ctk.BooleanVar(value=self.ayarlar.get("satir_numaralari"))
        satir_cb = ctk.CTkCheckBox(genel, text="Satır Numaralarını Göster", variable=satir_var)
        satir_cb.pack(anchor="w", pady=5, padx=10)

        sar_var = ctk.BooleanVar(value=self.ayarlar.get("kelime_sar"))
        sar_cb = ctk.CTkCheckBox(genel, text="Kelime Sarma (Word Wrap)", variable=sar_var)
        sar_cb.pack(anchor="w", pady=5, padx=10)

        # === EDITOR AYARLARI ===
        notebook.add("Editor")
        editor = notebook.tab("Editor")

        tamamlama_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_tamamlama"))
        tamamlama_cb = ctk.CTkCheckBox(editor, text="Otomatik Tamamlama", variable=tamamlama_var)
        tamamlama_cb.pack(anchor="w", pady=10, padx=10)

        oto_kaydet_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_kaydetme"))
        oto_kaydet_cb = ctk.CTkCheckBox(editor, text="Otomatik Kaydetme", variable=oto_kaydet_var)
        oto_kaydet_cb.pack(anchor="w", pady=5, padx=10)

        ctk.CTkLabel(editor, text="Oto. Kaydetme Araligi (sn):", font=("Segoe UI", 11)).pack(anchor="w", pady=(10, 0), padx=10)
        aralik_var = ctk.IntVar(value=self.ayarlar.get("otomatik_kaydetme_aralik"))
        aralik_slider = ctk.CTkSlider(editor, from_=5, to=300, number_of_steps=59, variable=aralik_var)
        aralik_slider.pack(fill="x", padx=10, pady=5)
        aralik_label = ctk.CTkLabel(editor, textvariable=aralik_var)
        aralik_label.pack(anchor="w", padx=10)

        bosluk_var = ctk.BooleanVar(value=self.ayarlar.get("bosluk_gostergesi"))
        bosluk_cb = ctk.CTkCheckBox(editor, text="Boşluk Göstergesi", variable=bosluk_var)
        bosluk_cb.pack(anchor="w", pady=5, padx=10)

        minimap_var = ctk.BooleanVar(value=self.ayarlar.get("minimap"))
        minimap_cb = ctk.CTkCheckBox(editor, text="Minimap (Küçük Harita)", variable=minimap_var)
        minimap_cb.pack(anchor="w", pady=5, padx=10)
        
        # === AI AYARLARI ===
        notebook.add("AI Asistan")
        ai_tab = notebook.tab("AI Asistan")

        ai_aktif_var = ctk.BooleanVar(value=self.ayarlar.get("ai_aktif"))
        ai_aktif_cb = ctk.CTkCheckBox(ai_tab, text="AI Asistanı Aktif", variable=ai_aktif_var)
        ai_aktif_cb.pack(anchor="w", pady=10, padx=10)

        ctk.CTkLabel(ai_tab, text="AI Sağlayıcı:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        saglayici_var = ctk.StringVar(value=self.ayarlar.get("ai_saglayici"))
        saglayici_combo = ctk.CTkOptionMenu(ai_tab, values=list(AI_MODELLERI.keys()), variable=saglayici_var)
        saglayici_combo.pack(fill="x", padx=10, pady=5)

        model_var = ctk.StringVar(value=self.ayarlar.get("ai_model"))
        model_combo = ctk.CTkOptionMenu(ai_tab, values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]), variable=model_var)
        model_combo.pack(fill="x", padx=10, pady=5)

        def saglayici_degisti(*args):
            model_combo.configure(values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]))
            model_var.set(AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"])[0])
        saglayici_var.trace_add("write", saglayici_degisti)

        ctk.CTkLabel(ai_tab, text="API Key:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        api_key_var = ctk.StringVar(value=self.ayarlar.get("ai_api_key"))
        api_key_entry = ctk.CTkEntry(ai_tab, textvariable=api_key_var, show="*", width=500)
        api_key_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sistem Mesajı:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0), padx=10)
        sistem_var = ctk.StringVar(value=self.ayarlar.get("ai_sistem_mesaji"))
        sistem_entry = ctk.CTkEntry(ai_tab, textvariable=sistem_var, width=500)
        sistem_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sıcaklık (0-2):", font=("Segoe UI", 11)).pack(anchor="w", pady=(10, 0), padx=10)
        sicaklik_var = ctk.DoubleVar(value=self.ayarlar.get("ai_sicaklik"))
        sicaklik_slider = ctk.CTkSlider(ai_tab, from_=0, to=2, number_of_steps=20, variable=sicaklik_var)
        sicaklik_slider.pack(fill="x", padx=10, pady=5)
        sicaklik_label = ctk.CTkLabel(ai_tab, textvariable=sicaklik_var)
        sicaklik_label.pack(anchor="w", padx=10)

        ctk.CTkLabel(ai_tab, text="Max Token:", font=("Segoe UI", 11)).pack(anchor="w", pady=(10, 0), padx=10)
        token_var = ctk.IntVar(value=self.ayarlar.get("ai_max_token"))
        token_slider = ctk.CTkSlider(ai_tab, from_=4096, to=32768, number_of_steps=30, variable=token_var)
        token_slider.pack(fill="x", padx=10, pady=5)
        token_label = ctk.CTkLabel(ai_tab, textvariable=token_var)
        token_label.pack(anchor="w", padx=10)
        # === HAKKIMDA ===
        notebook.add("Hakkımda")
        hakkinda = notebook.tab("Hakkımda")

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

        ctk.CTkLabel(hakkinda, text="Versiyon 1.0  |  © 2026 Tüm Hakları Saklıdır", 
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
            self.ayarlar.set("tema", tema_var.get())
            self.ayarlar.set("yazi_tipi", yazi_var.get())
            self.ayarlar.set("yazi_boyutu", boyut_var.get())
            self.ayarlar.set("satir_numaralari", satir_var.get())
            self.ayarlar.set("kelime_sar", sar_var.get())
            self.ayarlar.set("otomatik_tamamlama", tamamlama_var.get())
            self.ayarlar.set("otomatik_kaydetme", oto_kaydet_var.get())
            self.ayarlar.set("otomatik_kaydetme_aralik", aralik_var.get())
            self.ayarlar.set("bosluk_gostergesi", bosluk_var.get())
            self.ayarlar.set("minimap", minimap_var.get())
            self.ayarlar.set("ai_aktif", ai_aktif_var.get())
            self.ayarlar.set("ai_saglayici", saglayici_var.get())
            self.ayarlar.set("ai_model", model_var.get())
            self.ayarlar.set("ai_api_key", api_key_var.get())
            self.ayarlar.set("ai_sistem_mesaji", sistem_var.get())
            self.ayarlar.set("ai_sicaklik", sicaklik_var.get())
            self.ayarlar.set("ai_max_token", token_var.get())

            self.tema = tema_var.get()
            self.colors = TEMA_RENKLERI.get(self.tema, TEMA_RENKLERI["Koyu"])
            
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
                
            self._tema_uygula()
            pencere.destroy()

        ctk.CTkButton(pencere, text="Kaydet ve Uygula", command=kaydet_ayarlar,
                       fg_color="#28a745", hover_color="#218838",
                       border_color=self.colors["border"],
                       border_width=2,
                       font=("Segoe UI", 14, "bold")).pack(pady=15)

    def _tema_uygula(self):
        self.configure(fg_color=self.colors["bg"])
        
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
        self.tab_bar.configure(fg_color=self.colors.get("tab_inactive", "#f3f3f3"))
        
        for sekme in self.sekmeler:
            is_active = (sekme["id"] == self.aktif_sekme_id)
            sekme["frame"].configure(
                fg_color=self.colors["tab_active"] if is_active else self.colors["tab_inactive"],
                border_color=self.colors["border"]
            )
            sekme["label"].configure(text_color=self.colors["text"])
            sekme["kapat_btn"].configure(text_color=self.colors["text"])

        # Tab Butonları
        self.yeni_sekme_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.ac_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.kaydet_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.calistir_btn.configure(border_color=self.colors["border"]) 
        
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
        if hasattr(self, 'ai_typing_frame') and self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame.configure(fg_color=self.colors["ai_assistant"])
        # Alt Durum Çubuğu (Status Bar)
        self.status_bar.configure(fg_color=self.colors["status_bar"])

        self.renk_ayarlarini_yap()
        self.kod_renklendir()
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
    def sync_line_numbers(self):
        try:
            satir_sayisi = int(self.kod_alani.index("end-1c").split(".")[0])
            self.line_numbers.configure(state="normal")
            self.line_numbers.delete("1.0", "end")
            numara_metni = "\n".join(str(i) for i in range(1, satir_sayisi + 1))
            self.line_numbers.insert("1.0", numara_metni)
            self.line_numbers.configure(state="disabled")
            
            self._senkronize_scroll()
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
            for tag in ["keyword", "builtin", "string", "comment", "number"]:
                self.kod_alani.tag_remove(tag, "1.0", "end")

            metin = self.kod_alani.get("1.0", "end")

            keyword_pattern = r"\b(fonksiyon|dondur|sinif|eger|degilse_eger|degilse|dongu|kir|devam_et|gec|dene|hata_yakala|sonunda|ice_aktar|den|olarak|ve|veya|degil|eszamansiz|bekle|verim|kuresel|yerel_olmayan|sil|ile)\b"
            builtin_pattern = r"\b(yazdir|girdi_al|uzunluk|aralik|tip|en_buyuk|en_kucuk|toplam|mutlak|tamsayi|metin|ondalikli|mantiksal|liste|sozluk|tarih_saat|rastgele|matematik|simdi|ekle|sirala|karekok|kaplumbaga|ileri|geri|saga_don|sola_don|kalem_birak|kalem_kaldir|tkinter_arayuz|dugme|pencere|hepsi|herhangi|ascii_goster|ikili|kirma_noktasi|byte_dizisi|byte|cagrilabilir_mi|karakter|sinif_metodu|derle|karmasik|ozellik_sil|dizin|bolum_kalan|sirali_numaralandir|degerlendir|calistir|suz|icindekiler|donmus_kume|ozellik_al|kuresel_degiskenler|ozellik_var_mi|ozet|yardim|onaltilik|kimlik|alt_sinif_mi|yineleyici|yerel_degiskenler|harita|hafiza_gorunumu|sonraki|nesne|sekizlik|sirala_builtin|ters_cevir_builtin|temsil|ozellik_ayarla|dilim|durum_metodu|ust_sinif|degiskenler|izdusum|ice_aktar_builtin|bas_harf_buyuk|kucult_karsilastir|ortele|kodla|genislet_sekme|bul|bicimle|bicimle_harita|harf_sayi_mi|harf_mi|ascii_mi|onluk_mu|rakam_mi|tanimlayici_mi|kucuk_mu|sayi_mi|yazilabilir_mi|bosluk_mu|baslik_mi|buyuk_mu|sola_yasla|sol_kirp|cevirim_tablo|bolumle|on_ek_kaldir|son_ek_kaldir|sagdan_bul|sagdan_indeks|saga_yasla|sagdan_bolumle|sagdan_bol|sag_kirp|satir_bol|harf_degistir|baslik_yap|cevir|sifir_doldur|anahtardan_olustur|son_ogeyi_cikart|varsayilan_ayarla|guncelle|ekle_kume|fark|fark_guncelle|at|kesisim|kesisim_guncelle|ayrik_mi|alt_kume_mi|ust_kume_mi|bakirisim|bakirisim_guncelle|birlesim|kume_guncelle|kapat|oku|satir_oku|satirlari_oku|konumla|kacinci_byte|kisalt|yaz|satirlari_yaz|tampon_temizle|okunabilir_mi|yazilabilir_mi_dosya|konumlanabilir_mi|etiket|metin_kutusu|metin_alani|cerceve|liste_kutusu|menu|yeni_pencere|checkbutton|radiobutton|scale|scrollbar|spinbox|canvas|messagebox|filedialog|colorchooser|pack|grid|yerlestir|mainloop|after|destroy|configure|config|isletim_sistemi|bulundugu_dizin|dizin_degistir|dizin_listele|dizin_olustur|dizinler_olustur|dosya_sil|dizin_sil|yeniden_adlandir|yol_var_mi|dosya_mi|dizin_mi|yol_birlestir|dosya_adi|dizin_adi|tam_yol|yol_ayir|cevre_degiskenleri|sistem_calistir|cevre_al|sistem|argumanlar|cikis|yol_listesi|platform|surum|standart_cikis|standart_giris|standart_hata|boyut_al|zaman_modulu|buyu|anlik_zaman|yerel_zaman|greenwich_zaman|zaman_bicimle|zaman_ayristir|performans_sayaci|monotonik_sayac|json|json_yukle|json_yukle_metin|json_kaydet|json_kaydet_metin|desen|eslestir|ara|hepsini_bul|yineleyici_bul|desen_bol|desen_degistir|desen_degistir_say|desen_derle|kacis)\b"
            string_pattern = r"\"[^\"\\]*(\\.[^\"\\]*)*\"|\'[^\'\\]*(\\.[^\'\\]*)*\'"
            comment_pattern = r"#.*"
            number_pattern = r"\b\d+\.?\d*\b"

            desenler = {
                "keyword": keyword_pattern,
                "builtin": builtin_pattern,
                "string": string_pattern,
                "comment": comment_pattern,
                "number": number_pattern
            }

            def tk_idx(pos):
                satir = metin.count("\n", 0, pos) + 1
                sutun = pos - metin.rfind("\n", 0, pos) - 1
                return f"{satir}.{sutun}"

            for tag_adi, desen in desenler.items():
                for match in re.finditer(desen, metin):
                    self.kod_alani.tag_add(tag_adi, tk_idx(match.start()), tk_idx(match.end()))
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
        
        # ⬅️ YENİ: Dinamik kelime listesi al
        tum_kelimeler = self._tamamlama_kelime_listesi_al()
        
        if not tum_kelimeler:
            return
        
        # Eşleşmeleri bul (kod tanımları öncelikli)
        eslesmeler = []
        
        # Önce kod içi tanımları ara
        kod_tanimlari = self._koddan_tanimlari_cikar(self.kod_alani.get("1.0", "end-1c"))
        for k in kod_tanimlari:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                eslesmeler.append(("📌", k))  # 📌 = kod içi tanım
        
        # Sonra sözlük kelimelerini ara
        for k in TURKCE_KELIMELER:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                if k not in [x[1] for x in eslesmeler]:  # Tekrar ekleme
                    eslesmeler.append(("📚", k))  # 📚 = sözlük kelimesi
        
        if not eslesmeler or len(kelime) < 2:
            self.popup_kapat()
            return

        # Popup oluştur/güncelle
        if not self.popup:
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            self.popup.wm_attributes("-topmost", True)

            self.listbox = tk.Listbox(
                self.popup, bg="#252526", fg="#d4d4d4", selectbackground="#04395e",
                selectforeground="#ffffff", font=("Consolas", 11), bd=1, relief="solid"
            )
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<Double-Button-1>", lambda e: self.kelime_tamamla())
            self.listbox.bind("<Return>", lambda e: self.kelime_tamamla())

        self.listbox.delete(0, tk.END)
        
        # ⬅️ YENİ: İkonlu gösterim
        for ikon, item in eslesmeler[:15]:  # Max 15 öneri
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

    def on_key_release(self, event):
        if event.keysym in ["Up", "Down", "Return", "Tab", "Escape"]:
            return
        
        # ⬅️ YENİ: Kod değiştiğinde tanımları güncelle (her 10 saniyede bir)
        self.kod_renklendir()
        kelime, bas, bit = self.mevcut_kelimeyi_al()
        if kelime:
            self.popup_goster(kelime, bas, bit)
        else:
            self.popup_kapat()
    def on_tab_key(self, event):
        if self.popup:
            return self.kelime_tamamla()
        else:
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

    def on_arrow_up(self, event):
        if self.popup and self.listbox:
            idx = self.listbox.curselection()
            if idx:
                onceki = max(idx[0] - 1, 0)
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(onceki)
            return "break"

    def dosya_ac(self):
        path = filedialog.askopenfilename(title="Dosya Seç", filetypes=[("Türkçe Python", "*.trpy")])
        if path:
            self._yeni_sekme_olustur(yol=path)

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
        if getattr(sys, 'frozen', False):
            # PyInstaller .exe - once _internal'da python.exe ara
            exe_dir = os.path.dirname(sys.executable)
            internal_dir = os.path.join(exe_dir, "_internal")
            python_exe = os.path.join(internal_dir, "python.exe")
            
            if not os.path.exists(python_exe):
                # _internal'da yoksa, exe ile ayni klasore bak
                python_exe = os.path.join(exe_dir, "python.exe")
                
                if not os.path.exists(python_exe):
                    # Son care: sistem PATH'inden Python ara
                    import shutil
                    python_exe = shutil.which("python.exe")
                    
                    if not python_exe:
                        messagebox.showerror(
                            "Python Bulunamadi",
                            "Kodu calistirmak icin Python 3.12+ gerekli.\n\n"
                            "Lutfen Python'u kurun:\nhttps://python.org/downloads"
                        )
                        return
        else:
            # Normal .py calismasi
            python_exe = sys.executable
            if python_exe.endswith("pythonw.exe"):
                python_exe = python_exe.replace("pythonw.exe", "python.exe")

        # ==================== CALISTIRMA ====================
        if os.name == "nt":
            subprocess.Popen(
                [python_exe, "-X", "utf8", "-i", runner_path],
                cwd=temp_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(
                ["gnome-terminal", "--", python_exe, "-X", "utf8", "-i", runner_path],
                cwd=temp_dir
            )
        
        self.status_left.configure(text="  Kod calistiriliyor...")

if __name__ == "__main__":
    app = TurkceIDE()
    app.mainloop()
