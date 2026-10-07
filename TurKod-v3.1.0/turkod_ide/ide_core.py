"""TurKod IDE mantık katmanı.

Bu dosya UI oluşturmaz. Tkinter/CustomTkinter import etmez.
Fonksiyonlar parametre alır ve JSON'a uygun dict/list döndürür.
"""

import ast
import codecs
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback

try:
    from .ast_katmani import dogrula
    from .converter import (MODUL_CEVIRILERI, MODUL_METOTLARI,
                            python_kodu_turkceye_cevir, turkce_kodu_donustur)
    from .dictionary import (FONKSIYON_KW, SINIF_KW, SOZLUK, TERS_SOZLUK,
                             TURKCE_KELIMELER, TURKOD_BUILTIN_RE,
                             TURKOD_KEYWORD_RE, _builtin_words, _keyword_words,
                             kullanici_tanimlari)
    from .runner import RUNNER_KODU
    from .debugger import DebugHatasi, DebugOturumu
    from .akilli_duzeltici import AkilliDuzeltici
    from .settings import AyarlarYoneticisi
    from .signing import DijitalImza
    from .tokenizer import TokenTuru, TokenizerHatasi, tokenize
    from .ai import (AI_MODELLERI, sdk_arka_planda_yukle, sdk_yukle,
                     groq_modelleri_guncelle, openai_modelleri_guncelle)
except ImportError:
    from ast_katmani import dogrula
    from converter import (MODUL_CEVIRILERI, MODUL_METOTLARI,
                           python_kodu_turkceye_cevir, turkce_kodu_donustur)
    from dictionary import (FONKSIYON_KW, SINIF_KW, SOZLUK, TERS_SOZLUK,
                            TURKCE_KELIMELER, TURKOD_BUILTIN_RE,
                            TURKOD_KEYWORD_RE, _builtin_words, _keyword_words,
                            kullanici_tanimlari)
    from runner import RUNNER_KODU
    from debugger import DebugHatasi, DebugOturumu
    from akilli_duzeltici import AkilliDuzeltici
    from settings import AyarlarYoneticisi
    from signing import DijitalImza
    from tokenizer import TokenTuru, TokenizerHatasi, tokenize
    from ai import (AI_MODELLERI, sdk_arka_planda_yukle, sdk_yukle,
                    groq_modelleri_guncelle, openai_modelleri_guncelle)


class AIHatasi(Exception):
    """AI API çağrılarında kullanıcıya gösterilebilir hata."""


# Akıllı Düzeltme kodu denemek için çalıştırır. Aşağıdakileri içeren kod,
# kullanıcı açıkça izin vermedikçe ÇALIŞTIRILMAZ (yalnızca statik düzeltme).
# Modül adı -> kullanıcıya gösterilecek gerekçe.
RISKLI_MODULLER = {
    "os": "dosya/klasör silme, komut çalıştırma (os)",
    "shutil": "dosya/klasör kopyalama, taşıma, silme (shutil)",
    "pathlib": "dosya yazma/silme (pathlib)",
    "glob": "dosya sistemi tarama (glob)",
    "subprocess": "başka program çalıştırma (subprocess)",
    "multiprocessing": "yeni süreç başlatma (multiprocessing)",
    "ctypes": "işletim sistemi işlevlerine doğrudan erişim (ctypes)",
    "winreg": "Windows kayıt defteri (winreg)",
    "socket": "ağ bağlantısı (socket)",
    "ssl": "ağ bağlantısı (ssl)",
    "urllib": "internete istek (urllib)",
    "http": "internete istek (http)",
    "requests": "internete istek (requests)",
    "httpx": "internete istek (httpx)",
    "aiohttp": "internete istek (aiohttp)",
    "ftplib": "dosya aktarımı (ftplib)",
    "smtplib": "e-posta gönderme (smtplib)",
    "webbrowser": "tarayıcı açma (webbrowser)",
    "sqlite3": "veritabanı dosyası yazma (sqlite3)",
    "pickle": "güvensiz veri yükleme (pickle)",
    "keyboard": "klavye denetimi (keyboard)",
    "pynput": "klavye/fare denetimi (pynput)",
}
RISKLI_CAGRILAR = {
    "eval": "metni kod olarak çalıştırma (eval)",
    "exec": "metni kod olarak çalıştırma (exec)",
    "compile": "metni koda çevirme (compile)",
    "__import__": "dinamik modül yükleme (__import__)",
}


try:
    from .pip_tr import PIP_YARDIM, pip_komutu_cevir, pip_yardim_mi
except ImportError:
    from pip_tr import PIP_YARDIM, pip_komutu_cevir, pip_yardim_mi


class IDECore:
    """Tkinter içermeyen TürKod IDE mantık katmanı."""

    def __init__(self):
        self.ayarlar = AyarlarYoneticisi()
        self.proje_dizini = self.ayarlar.get("son_proje_dizini")

        self.ai_mesajlar = []
        self.ai_mesaj_gecmisi = []

        self._tanim_cache = None  # (hash, tanımlar)
        # Çalıştırma başlat/durdur işlemleri farklı iş parçacıklarından
        # gelebilir (her WebSocket mesajı ayrı iş parçacığında işlenir).
        self._calistirma_kilit = threading.RLock()
        self._calistirma_kimlik = 0

        self._yerel_duzelt_sozluk_cache = None
        self._yerel_duzelt_sozluk_map = None
        self._yerel_duzelt_sozluk_kucuk_listesi = None
        self._sozluk_duz_cache = None
        self._py_ciplak_cache = None

        self._calistirma_process = None
        # Terminalde süren kabuk komutları (Durdur hepsini öldürür).
        self._kabuk_surecleri = set()

        self.breakpoints = set()
        self._debug_oturumu = None

        # AI açıksa seçili sağlayıcının SDK'sını arka planda önceden yükle.
        if self.ayarlar.get("ai_aktif"):
            try:
                sdk_arka_planda_yukle(self.ayarlar.get("ai_saglayici"))
            except Exception:
                pass

        # İmza doğrulamasını açılışta arka planda yap: Hakkında/İmza
        # penceresi açıldığında sonuç önbellekten anında gelir.
        try:
            DijitalImza.arka_planda_isit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _guvenli_callback(cb, *args):
        if cb is None:
            return
        try:
            cb(*args)
        except Exception:
            pass

    @staticmethod
    def _subprocess_flags():
        if os.name == "nt":
            return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
        return {}
    def _kullanici_paket_yolu(self):
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        yol = os.path.join(base, "TurKod", "pip_packages")
        try:
            os.makedirs(yol, exist_ok=True)
        except OSError:
            pass  # oluşturulamazsa da kod çalıştırma engellenmesin
        return yol

    def _subprocess_env(self):
        env = dict(os.environ)
        pkg = self._kullanici_paket_yolu()
        mevcut = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pkg + (os.pathsep + mevcut if mevcut else "")
        env["PYTHONIOENCODING"] = "utf-8"
        return env
    def _python_exe_bul(self):
        python_exe = None

        if getattr(sys, "frozen", False):
            embed = os.path.join(os.path.dirname(sys.executable),
                                 "_internal", "python_embed", "python.exe")
            if os.path.exists(embed):
                python_exe = embed

        if not python_exe:
            python_exe = shutil.which("python.exe") or shutil.which("python")

        if not python_exe and not getattr(sys, "frozen", False):
            python_exe = sys.executable

        if python_exe and python_exe.endswith("pythonw.exe"):
            python_exe = python_exe.replace("pythonw.exe", "python.exe")

        if not python_exe:
            return None, (
                "Python bulunamadı. Python 3.x kurun ve PATH'e ekleyin. "
                "Veya _internal/python_embed/python.exe ekleyin."
            )

        return python_exe, ""

    def _sayi_ayar(self, anahtar, varsayilan):
        try:
            return int(self.ayarlar.get(anahtar))
        except (TypeError, ValueError):
            return varsayilan

    # ------------------------------------------------------------------
    # Ayarlar
    # ------------------------------------------------------------------
    def ayar_get(self, anahtar):
        return {
            "ok": True,
            "anahtar": anahtar,
            "deger": self.ayarlar.get(anahtar),
        }

    def ayar_set(self, anahtar, deger):
        self.ayarlar.set(anahtar, deger)
        return {
            "ok": True,
            "anahtar": anahtar,
            "deger": self.ayarlar.get(anahtar),
        }

    def ayarlar_tumu(self):
        try:
            veri = dict(getattr(self.ayarlar, "ayarlar", {}))
        except Exception:
            veri = {}

        return {
            "ok": True,
            "ayarlar": veri,
        }

    def proje_dizini_set(self, dizin):
        # Dosya yolu verilirse ağaç ve terminal (cwd) bozuluyordu.
        if not dizin or not os.path.isdir(dizin):
            return {"ok": False, "hata": "Dizin bulunamadı."}

        self.proje_dizini = dizin
        self.ayarlar.set("son_proje_dizini", dizin)

        return {
            "ok": True,
            "proje_dizini": dizin,
        }

    # ------------------------------------------------------------------
    # Dosya / oturum işlemleri
    # ------------------------------------------------------------------
    def dosya_oku(self, yol):
        try:
            # utf-8-sig: Not Defteri vb. ile kaydedilmiş BOM'lu dosyalarda
            # baştaki görünmez karakter "geçersiz karakter" hatası veriyor,
            # dosya hiç çalıştırılamıyordu. UTF-8 olmayan eski dosyalar için
            # Türkçe Windows kod sayfasına geri düşülür.
            with open(yol, "rb") as f:
                ham = f.read()
            if ham.startswith((b"\xff\xfe", b"\xfe\xff")):
                # PowerShell 5.1'in ">" yönlendirmesi gibi UTF-16 dosyalar.
                icerik = ham.decode("utf-16")
            elif b"\x00" in ham[:8192]:
                # İkili dosya: metin olarak açılıp otomatik kaydedilirse
                # dosya geri dönüşsüz bozulurdu.
                return {"ok": False, "hata": "Bu bir metin dosyası değil (ikili dosya)."}
            else:
                try:
                    icerik = ham.decode("utf-8-sig")
                except UnicodeDecodeError:
                    icerik = ham.decode("cp1254", errors="replace")
            icerik = icerik.replace("\r\n", "\n").replace("\r", "\n")

            return {
                "ok": True,
                "yol": yol,
                "isim": os.path.basename(yol),
                "icerik": icerik,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def dosya_kaydet(self, yol, icerik):
        if not yol:
            return {
                "ok": False,
                "yol_gerekli": True,
                "hata": "Dosya yolu yok.",
            }

        try:
            # Metin kipi '\n'i zaten '\r\n' yazar; içerikte '\r\n' varsa
            # (Windows panosundan yapıştırma) '\r\r\n' oluşuyor ve her
            # kaydet/aç döngüsünde boş satırlar ikiye katlanıyordu.
            icerik = (icerik or "").replace("\r\n", "\n").replace("\r", "\n")
            with open(yol, "w", encoding="utf-8") as f:
                f.write(icerik)

            return {
                "ok": True,
                "yol": yol,
                "isim": os.path.basename(yol),
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def dosya_agaci(self, dizin=None):
        dizin = dizin or self.proje_dizini

        if not dizin or not os.path.exists(dizin):
            return {"ok": False, "hata": "Proje dizini yok."}

        try:
            with os.scandir(dizin) as entries:
                tum_girdiler = list(entries)
        except PermissionError:
            return {"ok": False, "hata": "Dizin okuma izni yok."}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

        MAX_OGE = 300
        fazla = None

        klasorler = []
        dosyalar = []

        for entry in tum_girdiler:
            if entry.name.startswith("."):
                continue

            try:
                if entry.is_dir(follow_symlinks=False):
                    klasorler.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    dosyalar.append(entry)
            except OSError:
                continue

        klasorler.sort(key=lambda e: e.name.lower())
        dosyalar.sort(key=lambda e: e.name.lower())

        # Sınır, gizli öğeler elendikten ve klasörler öne alınıp sıralandıktan
        # SONRA uygulanır. Eskiden ham scandir sırasıyla kesildiğinden büyük
        # klasörlerde rastgele alt klasörler kayboluyor, gizli dosyalar yer
        # kaplıyordu.
        tum_sayi = len(klasorler) + len(dosyalar)
        if tum_sayi > MAX_OGE:
            fazla = tum_sayi - MAX_OGE
            klasorler = klasorler[:MAX_OGE]
            dosyalar = dosyalar[:MAX_OGE - len(klasorler)]

        ogeler = []

        for entry in klasorler:
            ogeler.append({
                "ad": entry.name,
                "yol": entry.path,
                "tip": "directory",
                "durum": "collapsed",
            })

        for entry in dosyalar:
            uzanti = os.path.splitext(entry.name)[1].lower()

            if uzanti == ".trpy":
                dosya_tipi = "trpy"
            elif uzanti == ".py":
                dosya_tipi = "python"
            else:
                dosya_tipi = "other"

            ogeler.append({
                "ad": entry.name,
                "yol": entry.path,
                "tip": "file",
                "dosya_tipi": dosya_tipi,
                "uzanti": uzanti,
            })

        return {
            "ok": True,
            "dizin": dizin,
            "ogeler": ogeler,
            "fazla_oge": fazla,
        }

    def oturum_oku(self):
        return {
            "ok": True,
            "son_oturum": self.ayarlar.get("son_oturum") or [],
            "son_oturum_aktif": self.ayarlar.get("son_oturum_aktif") or 0,
        }

    def oturum_kaydet(self, sekmeler, aktif_sira=0):
        try:
            self.ayarlar.set("son_oturum", sekmeler)
            self.ayarlar.set("son_oturum_aktif", aktif_sira)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ------------------------------------------------------------------
    # Kod analizi / tamamlama
    # ------------------------------------------------------------------
    def _koddan_tanimlari_cikar(self, kod):
        kod = kod or ""
        h = hash(kod)

        # Önbellek (anahtar, değer) tek bir demette tutulur: komutlar ayrı
        # iş parçacıklarında çalıştığından iki ayrı alana yazmak, bir dosyanın
        # anahtarıyla başka bir dosyanın tanımlarının eşleşmesine yol açabiliyordu.
        onbellek = self._tanim_cache
        if onbellek is not None and onbellek[0] == h:
            return onbellek[1]

        try:
            sonuc = sorted(kullanici_tanimlari(kod))
        except Exception:
            sonuc = []

        self._tanim_cache = (h, sonuc)

        return sonuc

    def kod_tanimlari(self, kod):
        return {
            "ok": True,
            "tanimlar": self._koddan_tanimlari_cikar(kod),
        }
    def sozluk_verileri(self):
        """Flutter tarafının sözdük tabanlı renklendirme ve dil bilgisi için kullanacağı veri."""
        try:
            from .dictionary import _block_words
        except ImportError:
            from dictionary import _block_words

        return {
            "ok": True,
            "keyword_words": sorted(_keyword_words),
            "builtin_words": sorted(_builtin_words),
            "block_words": sorted(_block_words),
            "modul_adlari": sorted(MODUL_CEVIRILERI.keys()),
            "turkce_kelime_sayisi": len(TURKCE_KELIMELER),
        }

    _FONT_FALLBACK = sorted([
        "Consolas", "Courier New", "Segoe UI", "Calibri", "Arial",
        "Times New Roman", "Verdana", "Tahoma", "Georgia", "Trebuchet MS",
        "Comic Sans MS", "Menlo", "Monaco", "Helvetica", "Ubuntu Mono",
        "DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono",
        "Roboto Mono", "Source Code Pro", "Fira Code", "JetBrains Mono",
    ])

    def sistem_fontlari(self):
        """Bu makinede kurulu GERÇEK yazı tiplerini döndürür.

        Flutter/Dart'ın kendi başına (native bir eklenti olmadan) OS'e kurulu
        fontları numaralandırmasının yerleşik bir yolu yok. Ancak bu backend
        zaten kullanıcının kendi makinesinde, bir masaüstü oturumunda
        çalışıyor; bu yüzden font numaralandırmasını burada, Python
        tarafında yapıp sonucu Flutter'a gönderiyoruz.

        Sırasıyla:
          1) tkinter.font.families() (Tk kurulu ise en güvenilir yöntem)
          2) matplotlib.font_manager (Tk yoksa / başsız ortamda)
          3) Küçük bir sabit yedek liste (ikisi de yoksa)
        """
        onbellek = getattr(self, "_font_onbellek", None)
        if onbellek is not None:
            return onbellek

        fonts = set()
        kaynak = None

        # 0) Windows: GDI ile doğrudan numaralandırma. tkinter yolu görünmez
        #    bir Tk penceresi açıp Tcl/Tk'yı kalıcı olarak belleğe yüklüyordu;
        #    bu yol hafiftir ve ek kütüphane gerektirmez.
        if os.name == "nt":
            try:
                fonts = self._win_font_aileleri()
                if fonts:
                    kaynak = "windows_gdi"
            except Exception:
                fonts = set()

        try:
            if fonts:
                raise StopIteration  # zaten bulundu; Tk'yı hiç yükleme
            import tkinter as tk
            import tkinter.font as tkfont

            root = tk.Tk()
            try:
                root.withdraw()
                fonts.update(f for f in tkfont.families() if f and not f.startswith("@"))
                kaynak = "tkinter"
            finally:
                root.destroy()
        except StopIteration:
            pass
        except Exception:
            fonts = set()

        # matplotlib çok ağırdır (onlarca MB, saniyeler); yalnızca Windows
        # dışında ve diğer yollar başarısızsa denenir.
        if not fonts and os.name != "nt":
            try:
                from matplotlib import font_manager

                for f in font_manager.fontManager.ttflist:
                    if f.name:
                        fonts.add(f.name)
                if fonts:
                    kaynak = "matplotlib"
            except Exception:
                fonts = set()

        if not fonts:
            fonts = set(self._FONT_FALLBACK)
            kaynak = "yedek_liste"

        sonuc = {
            "ok": True,
            "fontlar": sorted(fonts, key=lambda s: s.lower()),
            "kaynak": kaynak,
        }
        self._font_onbellek = sonuc
        return sonuc

    @staticmethod
    def _win_font_aileleri():
        """Win32 EnumFontFamiliesExW ile kurulu font ailelerini döndürür."""
        import ctypes
        from ctypes import wintypes

        class LOGFONTW(ctypes.Structure):
            _fields_ = [
                ("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
                ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
                ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
                ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
                ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
                ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
                ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", ctypes.c_wchar * 32),
            ]

        aileler = set()
        FONTENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.POINTER(LOGFONTW), ctypes.c_void_p,
            wintypes.DWORD, wintypes.LPARAM)

        def geri_cagir(lf, _tm, _tur, _param):
            ad = lf.contents.lfFaceName
            if ad and not ad.startswith("@"):
                aileler.add(ad)
            return 1

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.GetDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.EnumFontFamiliesExW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(LOGFONTW), FONTENUMPROC,
            wintypes.LPARAM, wintypes.DWORD]
        hdc = user32.GetDC(None)
        try:
            lf = LOGFONTW()
            lf.lfCharSet = 1  # DEFAULT_CHARSET: tüm karakter kümeleri
            cb = FONTENUMPROC(geri_cagir)
            gdi32.EnumFontFamiliesExW(hdc, ctypes.byref(lf), cb, 0, 0)
        finally:
            user32.ReleaseDC(None, hdc)
        return aileler

    def tamamlama_kelime_listesi_al(self, kod):
        sabit_kelimeler = set(TURKCE_KELIMELER)
        kod_tanimlari = set(self._koddan_tanimlari_cikar(kod))

        return list(kod_tanimlari) + [
            k for k in sabit_kelimeler if k not in kod_tanimlari
        ]

    def tamamlama_onerileri(self, kelime, kod):
        if not kelime or len(kelime) < 2:
            return {"ok": True, "oneriler": []}

        oneriler = []
        gorulen = set()

        kod_tanimlari = self._koddan_tanimlari_cikar(kod)

        for k in kod_tanimlari:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                if k not in gorulen:
                    oneriler.append({"ikon": "📌", "kelime": k})
                    gorulen.add(k)

        for k in TURKCE_KELIMELER:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                if k not in gorulen:
                    oneriler.append({"ikon": "📚", "kelime": k})
                    gorulen.add(k)

        return {
            "ok": True,
            "oneriler": oneriler[:15],
        }

    def istatistik_hesapla(self, kod):
        kod = kod or ""
        satirlar = kod.split("\n")

        toplam_satir = len(satirlar)
        bos_satir = sum(1 for s in satirlar if not s.strip())
        yorum_satir = sum(1 for s in satirlar if s.strip().startswith("#"))
        kod_satir = toplam_satir - bos_satir - yorum_satir

        karakter = len(kod)
        karakter_bosluksuz = len(
            kod.replace(" ", "").replace("\n", "").replace("\t", "")
        )

        fonksiyon_sayisi = len(
            re.findall(rf"\b{re.escape(FONKSIYON_KW)}\s+\w+", kod)
        )
        sinif_sayisi = len(
            re.findall(rf"\b{re.escape(SINIF_KW)}\s+\w+", kod)
        )
        degisken_sayisi = len(set(re.findall(
            # (?!=): "x == 1" bir karşılaştırmadır, değişken tanımı değil.
            r"^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=(?!=)",
            kod,
            re.MULTILINE
        )))

        return {
            "ok": True,
            "toplam_satir": toplam_satir,
            "kod_satiri": kod_satir,
            "yorum_satiri": yorum_satir,
            "bos_satir": bos_satir,
            "karakter": karakter,
            "karakter_bosluksuz": karakter_bosluksuz,
            "fonksiyon_sayisi": fonksiyon_sayisi,
            "sinif_sayisi": sinif_sayisi,
            "degisken_sayisi": degisken_sayisi,
        }

    def todo_bul(self, kod):
        kod = kod or ""
        sonuclar = []
        satirlar = kod.split("\n")

        for i, satir in enumerate(satirlar, 1):
            # Yalnızca gerçek yorum (metin dışındaki ilk #) ve tam kelime:
            # eskiden "# debugger" BUG, "# hackathon" HACK, metin içindeki
            # "# TODO" da TODO sayılıyordu.
            kod_kismi = self._yorumdan_arindir(satir)
            if len(kod_kismi) >= len(satir.rstrip()):
                continue
            yorum = satir[len(kod_kismi):]
            match = re.search(
                r"#.*?\b(TODO|FIXME|HACK|XXX|BUG)\b[\s:]*(.*)",
                yorum,
                re.IGNORECASE
            )

            if match:
                tip = match.group(1).upper()
                aciklama = match.group(2).strip() or "(açıklama yok)"

                sonuclar.append({
                    "satir": i,
                    "tip": tip,
                    "aciklama": aciklama,
                })

        return {
            "ok": True,
            "todolar": sonuclar,
        }

    @staticmethod
    def _yorumdan_arindir(satir):
        """Satırdaki string literal'leri dışındaki ilk # yorumunu keser."""
        tek = False
        cift = False
        i = 0

        while i < len(satir):
            ch = satir[i]

            if ch == "\\" and (tek or cift):
                i += 2
                continue

            if ch == "'" and not cift:
                tek = not tek
            elif ch == '"' and not tek:
                cift = not cift
            elif ch == "#" and not tek and not cift:
                return satir[:i].rstrip()

            i += 1

        return satir.rstrip()

    def fold_bolgeleri_bul(self, kod):
        kod = kod or ""
        # split("\n"): editör satırları yalnızca \n ile ayırır. splitlines()
        # metin içindeki  , \x0c gibi karakterlerde de böldüğünden
        # satır numaraları kayıyordu.
        satirlar = kod.split("\n")
        bolgeler = []
        yigin = []

        def kapat(bas_satir, bit_satir):
            if bit_satir <= bas_satir:
                return

            govde_var = any(s.strip() for s in satirlar[bas_satir:bit_satir])

            if govde_var:
                bolgeler.append((bas_satir, bit_satir))

        # Mantıksal satır takibi: açık parantez içindeki ya da çok satırlı
        # metin içindeki satırlar girinti karşılaştırmasına katılmaz. Eskiden
        # "x = [\n1, 2\n]" gibi daha az girintili bir devam satırı bloğu
        # erken kapatıyor, parantez içindeki "anahtar:" satırı sahte bir
        # katlama bölgesi oluşturuyordu.
        derinlik = 0
        metin = None          # içinde bulunulan metnin tırnağı (', ", ''' , """)
        mantiksal_bas = None  # (satır no, girinti)
        son_karakter = None   # mantıksal satırın yorum dışı son karakteri

        for i, satir in enumerate(satirlar, 1):
            devam_satiri = mantiksal_bas is not None

            if not devam_satiri:
                bosluksuz = satir.lstrip()

                if not bosluksuz or bosluksuz.startswith("#"):
                    continue

                indent = len(satir) - len(bosluksuz)

                while yigin and indent <= yigin[-1][1]:
                    bas_satir, _ = yigin.pop()
                    kapat(bas_satir, i - 1)

                mantiksal_bas = (i, indent)
                son_karakter = None

            j = 0
            n = len(satir)
            while j < n:
                ch = satir[j]
                if metin is not None:
                    if ch == "\\":
                        j += 2
                        continue
                    if satir.startswith(metin, j):
                        j += len(metin)
                        metin = None
                        son_karakter = '"'
                        continue
                    j += 1
                    continue
                if ch == "#":
                    break
                if ch in "\"'":
                    metin = ch * 3 if satir.startswith(ch * 3, j) else ch
                    j += len(metin)
                    continue
                if ch in "([{":
                    derinlik += 1
                elif ch in ")]}":
                    derinlik = max(0, derinlik - 1)
                if not ch.isspace():
                    son_karakter = ch
                j += 1

            if metin in ("'", '"'):
                metin = None  # tek satırlık metin satır sonunda biter

            ters_bolu = son_karakter == "\\" and metin is None
            if derinlik == 0 and metin is None and not ters_bolu:
                if son_karakter == ":" and mantiksal_bas is not None:
                    yigin.append(mantiksal_bas)
                mantiksal_bas = None

        son_satir = len(satirlar)

        while yigin:
            bas_satir, _ = yigin.pop()
            kapat(bas_satir, son_satir)

        return {
            "ok": True,
            "bolgeler": [
                {"baslangic": b, "bitis": e}
                for b, e in bolgeler
            ],
        }

    def tokenize_kod(self, kod):
        kod = kod or ""

        try:
            tanimlar = kullanici_tanimlari(kod)
            tokenlar = tokenize(kod, kullanici_adlari=tanimlar)

            cikti = []

            for t in tokenlar:
                cikti.append({
                    "tur": t.tur.name,
                    "deger": t.deger,
                    "satir": t.satir,
                    "sutun": t.sutun,
                    "son_satir": t.son_satir,
                    "son_sutun": t.son_sutun,
                })

            return {
                "ok": True,
                "tokenlar": cikti,
            }
        except TokenizerHatasi as e:
            return {
                "ok": False,
                "hata": str(e.mesaj),
                "satir": e.satir,
                "sutun": e.sutun,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def _golgeleme_uyarilari(self, kod, en_fazla=20):
        """Kullanıcı bir TürKod komutunu değişken/fonksiyon adı olarak
        tanımlamışsa (ör. "toplam = 0") uyarı listesi döndürür.

        Böyle bir ad dosya genelinde kullanıcı tanımı sayılır ve çevrilmez;
        yani aynı dosyada "toplam(liste)" artık sum() olarak ÇALIŞMAZ. Yalnızca
        gerçekten işlev kaybettiren durumlar raporlanır: hedefi Python
        yerleşik fonksiyonu olan kelimeler (toplam->sum, uzunluk->len ...) ve
        kodda içe aktarılmış modül adları. "sonuç", "değer" gibi zararsız
        sözlük kelimeleri gürültü olmaması için uyarılmaz."""
        import builtins
        import keyword

        try:
            tanimlar = kullanici_tanimlari(kod)
        except Exception:
            return []
        if not tanimlar:
            return []

        sozluk = self._sozluk_duz_harita()
        ice_aktarilan = set(re.findall(
            r"^\s*(?:içe_aktar|ice_aktar)\s+([A-Za-z_ÇŞĞÜÖİçşğüöı][\wÇŞĞÜÖİçşğüöı]*)",
            kod, re.MULTILINE))

        adaylar = {}
        for ad in tanimlar:
            hedef = sozluk.get(ad)
            if hedef and "." not in hedef and (
                    hasattr(builtins, hedef) and callable(getattr(builtins, hedef))
                    or keyword.iskeyword(hedef)):
                adaylar[ad] = (f"bir TürKod komutu ({hedef})", "komut")
            elif ad in ice_aktarilan and ad in MODUL_CEVIRILERI:
                adaylar[ad] = ("içe aktarılan bir modül", "modül")
        if not adaylar:
            return []

        # Satır bulmak için metin/yorum içerikleri aynı uzunlukta boşlukla
        # maskelenir (konumlar korunur, "toplam" yazan bir yorum sayılmaz).
        maskeli = re.sub(
            r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*',
            lambda m: re.sub(r"[^\n]", " ", m.group(0)), kod)

        uyarilar = []
        for ad, (neden, tur) in adaylar.items():
            e = re.escape(ad)
            desen = re.compile(
                rf"^[ \t]*{e}[ \t]*(?:[-+*/%]|//|\*\*)?=(?!=)"          # atama
                rf"|^[ \t]*(?:[\w, \t]*,[ \t]*)?{e}[ \t]*(?:,[\w, \t]*)?=(?!=)"  # çoklu atama
                rf"|\b(?:fonksiyon|sınıf|sinif)[ \t]+{e}\b"              # tanım
                rf"|\b(?:için|icin|döngü|dongu)[ \t]+(?:[\w, \t]*,[ \t]*)?{e}\b"  # döngü
                rf"|\bolarak[ \t]+{e}\b",                                # takma ad
                re.MULTILINE)
            m = desen.search(maskeli) or re.search(rf"(?<![\w.]){e}\b", maskeli)
            satir = maskeli.count("\n", 0, m.start()) + 1 if m else None
            onek = f"Satır {satir}: " if satir else ""
            uyarilar.append({
                "satir": satir,
                "ad": ad,
                "mesaj": f"{onek}'{ad}' {neden}, ama değişken olarak tanımlanmış",
            })
        uyarilar.sort(key=lambda u: (u["satir"] or 10 ** 9, u["ad"]))
        return uyarilar[:en_fazla]

    def _anahtar_kelime_tanimi(self, kod, tercih_satir=None):
        """TürKod anahtar kelimesi (eğer, için, Doğru, ...) değişken /
        fonksiyon / parametre adı olarak kullanılmışsa ilk (tercihen hata
        satırındaki) örneği {satir, ad, mesaj} olarak döndürür, yoksa None.

        Böyle bir kullanım Python'a çevrilince sözdizimini bozar ("if = 5");
        ham "geçersiz sözdizimi" yerine nedenini söyleyen kısa bir mesaj
        gösterilir."""
        kelimeler = sorted(_keyword_words, key=len, reverse=True)
        if not kelimeler:
            return None
        kw = "|".join(re.escape(k) for k in kelimeler)
        ID = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][\wÇŞĞÜÖİçşğüöı]*"
        maskeli = re.sub(
            r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*',
            lambda m: re.sub(r"[^\n]", " ", m.group(0)), kod)
        desenler = [
            # atama / artırımlı atama: "eğer = 5", "ve += 1"
            rf"^[ \t]*(?P<ad>{kw})[ \t]*(?:[-+*/%]|//|\*\*)?=(?!=)",
            # çoklu atama: "a, için = 1, 2"
            rf"^[ \t]*(?:{ID}[ \t]*,[ \t]*)+(?P<ad>{kw})[ \t]*=(?!=)",
            # fonksiyon / sınıf adı: "fonksiyon eğer():"
            rf"\b(?:fonksiyon|sınıf|sinif)[ \t]+(?P<ad>{kw})\b",
            # döngü değişkeni: "için eğer içinde ..."
            rf"\b(?:için|icin)[ \t]+(?P<ad>{kw})[ \t]+(?:içinde|icinde|aralık|aralik)\b",
            # parametre: "fonksiyon f(eğer, x)"
            rf"\b(?:fonksiyon)[ \t]+{ID}[ \t]*\([^)\n]*?(?<![\w])(?P<ad>{kw})(?![\w])[ \t]*[,)=:]",
            # takma ad: "içe_aktar x olarak için"
            rf"\bolarak[ \t]+(?P<ad>{kw})\b",
        ]
        bulunan = []
        for d in desenler:
            for m in re.finditer(d, maskeli, re.MULTILINE):
                satir = maskeli.count("\n", 0, m.start("ad")) + 1
                bulunan.append((satir, m.group("ad")))
        if not bulunan:
            return None
        bulunan.sort()
        if tercih_satir:
            ayni = [b for b in bulunan if b[0] == tercih_satir]
            if ayni:
                bulunan = ayni
        satir, ad = bulunan[0]
        return {
            "satir": satir,
            "sutun": None,
            "mesaj": (f"Satır {satir}: '{ad}' bir TürKod anahtar kelimesi; "
                      f"değişken adı olarak kullanılamaz"),
        }

    def syntax_kontrol(self, kod):
        kod = kod or ""

        if not kod.strip():
            return {
                "ok": True,
                "basarili": True,
                "hatalar": [],
                "durum": "Kod boş.",
            }

        satir_sayisi = kod.count("\n") + 1

        if satir_sayisi > 5000:
            return {
                "ok": True,
                "basarili": True,
                "buyuk_dosya": True,
                "hatalar": [],
                "durum": "Büyük dosya: hızlı kontrol.",
            }

        try:
            sonuc = dogrula(kod)
            hatalar = []

            for h in sonuc.hatalar:
                hatalar.append({
                    "satir": getattr(h, "satir", None),
                    "sutun": getattr(h, "sutun", None),
                    "mesaj": str(h),
                })

            # Hata, bir TürKod anahtar kelimesinin ad olarak kullanılmasından
            # kaynaklanıyorsa ham "geçersiz sözdizimi" yerine nedenini söyle.
            if not sonuc.basarili:
                try:
                    ilk_satir = hatalar[0].get("satir") if hatalar else None
                    neden = self._anahtar_kelime_tanimi(kod, ilk_satir)
                    if neden is not None:
                        hatalar = [neden] + [
                            h for h in hatalar if h.get("satir") != neden["satir"]]
                except Exception:
                    pass

            try:
                uyarilar = self._golgeleme_uyarilari(kod)
            except Exception:
                uyarilar = []

            return {
                "ok": True,
                "basarili": sonuc.basarili,
                "hatalar": hatalar,
                "uyarilar": uyarilar,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ------------------------------------------------------------------
    # Çeviri / arama
    # ------------------------------------------------------------------
    def _kod_dili_tespit(self, kod):
        kod = kod or ""

        turkod = len(TURKOD_KEYWORD_RE.findall(kod))
        python = len(re.findall(
            r"\b(def|return|class|if|elif|else|for|while|import|from|try|"
            r"except|finally|break|continue|lambda|with|as|yield|global|"
            r"nonlocal|del|assert|async|await)\b",
            kod
        ))

        if turkod != python:
            return "turkod" if turkod > python else "python"

        python_kaliplari = [
            re.search(r"^\s*import\s+\w", kod, re.MULTILINE),
            re.search(r"^\s*from\s+\w+\s+import\b", kod, re.MULTILINE),
            re.search(r"^\s*def\s+\w", kod, re.MULTILINE),
            re.search(r"^\s*print\s*\(", kod, re.MULTILINE),
        ]

        turkod_kaliplari = [
            re.search(r"^\s*içe_aktar\s+\w", kod, re.MULTILINE),
            re.search(r"^\s*den\s+\w+\s+içe_aktar\b", kod, re.MULTILINE),
            re.search(r"^\s*fonksiyon\s+\w", kod, re.MULTILINE),
            re.search(r"^\s*yazdır\s*\(", kod, re.MULTILINE),
        ]

        python_skor = sum(bool(k) for k in python_kaliplari)
        turkod_skor = sum(bool(k) for k in turkod_kaliplari)

        if python_skor >= turkod_skor:
            return "python"

        return "turkod"

    def kodu_cevir(self, kod):
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Çevrilecek kod yok."}

        dil = self._kod_dili_tespit(kod)

        try:
            if dil == "turkod":
                sonuc = turkce_kodu_donustur(kod)
                kaynak, hedef, uzanti = "TürKod", "Python", ".py"
            else:
                sonuc = python_kodu_turkceye_cevir(kod)
                kaynak, hedef, uzanti = "Python", "TürKod", ".trpy"

            return {
                "ok": True,
                "kaynak": kaynak,
                "hedef": hedef,
                "uzanti": uzanti,
                "sonuc": sonuc,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def kod_arama_cevir(self, giris):
        giris = (giris or "").strip()

        if not giris:
            return {"ok": False, "hata": "Arama metni boş."}

        kelimeler = re.findall(
            r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*",
            giris
        )

        karsiliklar = []
        eslesme_bulundu = False

        for kelime in kelimeler:
            bulundu = False
            kl = kelime.lower()

            if kl in TERS_SOZLUK:
                karsiliklar.append({
                    "kelime": kelime,
                    "karsilik": TERS_SOZLUK[kl],
                })
                bulundu = True
                eslesme_bulundu = True
            elif kelime in TERS_SOZLUK:
                karsiliklar.append({
                    "kelime": kelime,
                    "karsilik": TERS_SOZLUK[kelime],
                })
                bulundu = True
                eslesme_bulundu = True

            if not bulundu:
                for desen, karsilik in SOZLUK.items():
                    temiz = str(desen).replace(r"\b", "").strip()
                    temiz = temiz.strip('"').strip("'")

                    if temiz and temiz.lower() == kl:
                        karsiliklar.append({
                            "kelime": kelime,
                            "karsilik": karsilik,
                        })
                        bulundu = True
                        eslesme_bulundu = True
                        break

        tam_ceviri = None
        cevirme_hatasi = None

        try:
            tam_ceviri = python_kodu_turkceye_cevir(giris)

            if not tam_ceviri.strip():
                tam_ceviri = None
        except Exception as e:
            cevirme_hatasi = str(e)

        return {
            "ok": True,
            "kelime_karsiliklari": karsiliklar,
            "tam_ceviri": tam_ceviri,
            "cevirme_hatasi": cevirme_hatasi,
            "eslesme_bulundu": eslesme_bulundu,
        }

    # ------------------------------------------------------------------
    # AI model / prompt / API
    # ------------------------------------------------------------------
    def ai_modelleri(self):
        return {
            "ok": True,
            "modeller": AI_MODELLERI,
        }

    def modelleri_guncelle(self):
        saglayici = self.ayarlar.get("ai_saglayici")
        api_key = self.ayarlar.get("ai_api_key")

        if not api_key:
            return {"ok": False, "hata": "API anahtarı yok."}

        try:
            if saglayici == "Groq":
                groq_modelleri_guncelle(api_key)
            elif saglayici == "OpenAI":
                openai_modelleri_guncelle(api_key)
            else:
                return {
                    "ok": False,
                    "hata": "Model güncelleme bu sağlayıcı için desteklenmiyor.",
                }

            return {
                "ok": True,
                "saglayici": saglayici,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def model_dogrula(self):
        saglayici = self.ayarlar.get("ai_saglayici")
        mevcut_model = self.ayarlar.get("ai_model")

        try:
            if saglayici in AI_MODELLERI:
                gecerli_modeller = AI_MODELLERI[saglayici]

                if mevcut_model not in gecerli_modeller and gecerli_modeller:
                    yeni_model = gecerli_modeller[0]
                    self.ayarlar.set("ai_model", yeni_model)

                    return {
                        "ok": True,
                        "degisti": True,
                        "eski_model": mevcut_model,
                        "yeni_model": yeni_model,
                    }

            return {
                "ok": True,
                "degisti": False,
                "model": mevcut_model,
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def ai_temizle(self):
        self.ai_mesajlar.clear()
        self.ai_mesaj_gecmisi.clear()

        return {"ok": True}

    def ai_mesaj_hazirla(self, mesaj, kod=None):
        python_kodu = ""

        if kod:
            try:
                python_kodu = turkce_kodu_donustur(kod)
            except Exception:
                python_kodu = ""

        if not python_kodu:
            return mesaj

        # Sınır yalnızca KOD kısmına uygulanır ve kod bloğu her zaman
        # kapatılır. Eskiden birleşik metin 2000. karakterden kesiliyor;
        # kapanış ``` işareti ve uzun sorularda kullanıcının kendi sorusu
        # yarıda kalıyordu.
        SINIR = 2000
        satirlar = python_kodu.split("\n")
        if len(satirlar) > 25:
            satirlar = satirlar[-20:]
        butce = max(400, SINIR - len(mesaj))
        while len(satirlar) > 1 and sum(len(s) + 1 for s in satirlar) > butce:
            satirlar = satirlar[1:]
        govde = "\n".join(satirlar)
        if len(govde) > butce:
            govde = govde[-butce:]
        baslik = ("[Kod (son satırlar)]:" if len(satirlar) < python_kodu.count("\n") + 1
                  else "[Kod]:")
        return f"{mesaj}\n{baslik}\n```python\n{govde}\n```"

    def ai_kodu_acikla_prompt(self, kod):
        return (
            "Aşağıdaki TürKod kodunu satır satır açıkla ve ne yaptığını özetle:\n"
            "```TürKod\n"
            f"{kod}\n"
            "```"
        )

    def ai_kodu_optimize_prompt(self, kod):
        return (
            "Aşağıdaki TürKod kodunu optimize et ve daha verimli hale getir:\n"
            "```TürKod\n"
            f"{kod}\n"
            "```\n"
            "Yapacakların:\n"
            "- Yapılan iyileştirmeleri kısaca açıkla\n"
            "- Optimize edilmiş kodu TürKod bloğunda ver"
        )

    def ai_sor(self, mesaj, kod=None):
        if not self.ayarlar.get("ai_aktif"):
            return {"ok": False, "hata": "AI aktif değil."}

        if not self.ayarlar.get("ai_api_key"):
            return {"ok": False, "hata": "API anahtarı yok."}

        tam_mesaj = self.ai_mesaj_hazirla(mesaj, kod)
        self.ai_mesajlar.append({"gonderen": "user", "mesaj": mesaj})

        try:
            cevap = self._ai_api_cagri(tam_mesaj)
            self.ai_mesajlar.append({"gonderen": "assistant", "mesaj": cevap})

            return {
                "ok": True,
                "cevap": cevap,
                "parcalar": self._ai_mesaj_parse_et(cevap),
            }
        except AIHatasi as e:
            return {"ok": False, "hata": str(e)}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def ai_prompt_gonder(self, prompt):
        if not self.ayarlar.get("ai_aktif"):
            return {"ok": False, "hata": "AI aktif değil."}

        if not self.ayarlar.get("ai_api_key"):
            return {"ok": False, "hata": "API anahtarı yok."}

        self.ai_mesajlar.append({"gonderen": "user", "mesaj": prompt})

        try:
            cevap = self._ai_api_cagri(prompt)
            self.ai_mesajlar.append({"gonderen": "assistant", "mesaj": cevap})

            return {
                "ok": True,
                "cevap": cevap,
                "parcalar": self._ai_mesaj_parse_et(cevap),
            }
        except AIHatasi as e:
            return {"ok": False, "hata": str(e)}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def ai_kodu_acikla(self, kod):
        kod = (kod or "").strip()

        if not kod:
            return {"ok": False, "hata": "Açıklanacak kod bulunamadı."}

        return self.ai_prompt_gonder(self.ai_kodu_acikla_prompt(kod))

    def ai_kodu_optimize(self, kod):
        kod = (kod or "").strip()

        if not kod:
            return {"ok": False, "hata": "Optimize edilecek kod bulunamadı."}

        return self.ai_prompt_gonder(self.ai_kodu_optimize_prompt(kod))

    def _ai_mesaj_parse_et(self, mesaj):
        parcalar = []
        son_pos = 0

        # Dil etiketi yalnızca açılış satırındadır; kodun ilk satırının
        # girintisi korunur (eskiden "\s*" ve strip() ilk satırın
        # girintisini yutup İmlece Ekle'de IndentationError üretiyordu;
        # etiketsiz "```x = 1" da "x" dili sanılıyordu).
        for match in re.finditer(r"```([^\n`]*)\n(.*?)```", mesaj, re.DOTALL):
            if match.start() > son_pos:
                metin = mesaj[son_pos:match.start()].strip()

                if metin:
                    parcalar.append({
                        "tip": "metin",
                        "icerik": metin,
                        "dil": "",
                    })

            dil = match.group(1).strip()
            kod = textwrap.dedent(match.group(2).strip("\r\n")).rstrip()

            if dil.lower() in ("python", "py") or (
                dil.lower() in ("", "türkod") and self._kod_dili_tespit(kod) == "python"
            ):
                try:
                    kod = python_kodu_turkceye_cevir(kod)
                    dil = "TürKod"
                except Exception as e:
                    print(f"[AI Parse Hatası] {e}")

            parcalar.append({
                "tip": "kod",
                "icerik": kod,
                "dil": dil,
            })

            son_pos = match.end()

        if son_pos < len(mesaj):
            kalan = mesaj[son_pos:].strip()

            if kalan:
                parcalar.append({
                    "tip": "metin",
                    "icerik": kalan,
                    "dil": "",
                })

        if not parcalar and mesaj.strip():
            parcalar.append({
                "tip": "metin",
                "icerik": mesaj.strip(),
                "dil": "",
            })

        return parcalar

    def _cevabi_turkceye_cevir(self, cevap):
        sonuc = []
        son_pos = 0

        for match in re.finditer(r"```(\w*)\s*\n?(.*?)```", cevap, re.DOTALL):
            sonuc.append(cevap[son_pos:match.start()])

            dil = match.group(1).strip().lower()
            kod = match.group(2)

            if dil in ("python", "py") or (
                dil in ("", "türkod") and self._kod_dili_tespit(kod) == "python"
            ):
                try:
                    turkce_kod = python_kodu_turkceye_cevir(kod)
                    sonuc.append(f"```TürKod\n{turkce_kod}\n```")
                except Exception as e:
                    print(f"[AI Çeviri Hatası] {e}")
                    sonuc.append(match.group(0))
            else:
                sonuc.append(match.group(0))

            son_pos = match.end()

        sonuc.append(cevap[son_pos:])
        cevap = "".join(sonuc)

        for py, tr in sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True):
            cevap = re.sub(rf"`{re.escape(py)}`", f"`{tr}`", cevap)

        return cevap

    def _ai_api_cagri(self, mesaj):
        if len(self.ai_mesaj_gecmisi) > 20:
            self.ai_mesaj_gecmisi = self.ai_mesaj_gecmisi[-20:]

        saglayici = self.ayarlar.get("ai_saglayici")
        api_key = self.ayarlar.get("ai_api_key")
        model = self.ayarlar.get("ai_model")
        sicaklik = self.ayarlar.get("ai_sicaklik")
        max_token = self.ayarlar.get("ai_max_token")
        sistem_mesaji = self.ayarlar.get("ai_sistem_mesaji") or ""

        # SDK'lar yalnızca seçili sağlayıcı için, ilk kullanımda yüklenir.
        openai = sdk_yukle("openai") if saglayici == "OpenAI" else None
        Groq = sdk_yukle("groq") if saglayici == "Groq" else None
        genai = sdk_yukle("genai") if saglayici == "Gemini" else None
        anthropic = sdk_yukle("anthropic") if saglayici == "Claude" else None

        try:
            if saglayici == "OpenAI" and openai:
                client = openai.OpenAI(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})

                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sistem_mesaji}] + self.ai_mesaj_gecmisi[-2:],
                    temperature=sicaklik,
                    max_tokens=max_token,
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
                    max_tokens=max_token,
                )

                cevap = response.choices[0].message.content
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Gemini" and genai:
                client = genai.Client(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})

                icerik = f"{sistem_mesaji}\n{mesaj}" if sistem_mesaji else mesaj

                response = client.models.generate_content(
                    model=model,
                    contents=[icerik],
                )

                try:
                    cevap = response.text
                except (ValueError, AttributeError):
                    cevap = "⚠️ AI yanıtı alınamadı (güvenlik filtresi engellemiş olabilir)."

                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Claude" and anthropic:
                client = anthropic.Anthropic(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})

                response = client.messages.create(
                    model=model,
                    max_tokens=max_token,
                    system=sistem_mesaji,
                    messages=[{"role": "user", "content": mesaj}],
                )

                # Güncel Claude modellerinde ilk blok bir 'thinking' bloğu
                # olabilir; eskiden content[0].text AttributeError veriyordu.
                # Yalnızca metin blokları birleştirilir.
                metinler = [
                    getattr(b, "text", "") for b in (response.content or [])
                    if getattr(b, "type", "") == "text"
                ]
                cevap = "".join(metinler).strip()
                if not cevap:
                    if getattr(response, "stop_reason", "") == "refusal":
                        cevap = "⚠️ Claude bu isteği yanıtlamayı reddetti."
                    else:
                        cevap = "⚠️ Claude boş yanıt döndürdü."

                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            else:
                kutuphane_adi = {
                    "OpenAI": "openai",
                    "Groq": "groq",
                    "Gemini": "google-genai",
                    "Claude": "anthropic",
                }.get(saglayici, saglayici.lower())

                print("\n" + "=" * 60)
                print("  ❌ AI HATASI: Kütüphane Yüklenmemiş")
                print("=" * 60)
                print(f"\nSağlayıcı: {saglayici}")
                print(f"\npip yükle {kutuphane_adi}")
                print("=" * 60 + "\n")

                raise AIHatasi(
                    f"⚠️ {saglayici} kütüphanesi yüklü değil!\n"
                    f"Yüklemek için:\npip yükle {kutuphane_adi}"
                )

            cevap = self._cevabi_turkceye_cevir(cevap)
            return cevap

        except AIHatasi:
            raise
        except Exception as e:
            hata = str(e).lower()
            hata_kodu = getattr(e, "status_code", None) or getattr(e, "code", None)

            if hata_kodu == 413 or "too large for model" in hata:
                hata_msg = "İstek çok uzun! Kodu kısaltın."
            elif "tokens per minute" in hata or "rate limit" in hata or "limit exceeded" in hata:
                hata_msg = "Limitiniz bitti. Lütfen başka bir API anahtarı alın veya daha sonra tekrar deneyin."
            elif "authentication" in hata or "api key" in hata or "api_key" in hata:
                hata_msg = "API Anahtarı geçersiz!"
            elif "decommissioned" in hata or "model_decommissioned" in hata:
                hata_msg = (
                    f"⚠️ Model kullanımdan kaldırılmış: {model}\n"
                    "Lütfen Ayarlar → AI Asistan'dan başka bir model seçin.\n"
                    "Önerilen: llama-3.3-70b-versatile"
                )
            elif "model" in hata and ("not found" in hata or "not_found" in hata):
                hata_msg = f"Model bulunamadı: {model}"
            elif "connection" in hata or "timeout" in hata:
                hata_msg = "Bağlantı hatası! İnternetinizi kontrol edin."
            else:
                print("\n" + "=" * 60)
                print("  ❌ AI HATASI")
                print("=" * 60)
                print(f"  Sağlayıcı: {saglayici}")
                print(f"  Model: {model}")
                print(f"  Hata: {str(e)}")
                traceback.print_exc()
                print("=" * 60 + "\n")
                hata_msg = f"Bir hata oluştu: {str(e)[:200]}"

            raise AIHatasi(hata_msg)

    # ------------------------------------------------------------------
    # Yerel düzeltme
    # ------------------------------------------------------------------
    def _yerel_duzelt_sozluk(self):
        if self._yerel_duzelt_sozluk_cache is not None:
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

        kelimeler.update([
            "yazdır", "girdi_al", "fonksiyon", "sınıf", "eğer", "değilse",
            "değilse_eğer", "döngü", "kır", "devam_et", "geç", "dene",
            "hata_yakala", "sonunda", "içe_aktar", "döndür", "ve", "veya",
            "değil",
        ])

        try:
            kelimeler.update(_keyword_words)
            kelimeler.update(_builtin_words)
        except Exception:
            pass

        self._yerel_duzelt_sozluk_cache = sorted(kelimeler)

        return self._yerel_duzelt_sozluk_cache

    @staticmethod
    def _tr_normalize(metin):
        cevirim = str.maketrans({
            "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g",
            "ü": "u", "Ü": "u", "ş": "s", "Ş": "s",
            "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
        })

        return metin.translate(cevirim).lower()

    def _yerel_duzelt_sozluk_haritasi(self):
        if (
            self._yerel_duzelt_sozluk_map is not None
            and self._yerel_duzelt_sozluk_kucuk_listesi is not None
        ):
            return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

        sozluk = self._yerel_duzelt_sozluk()
        sozluk_map = {}

        for kelime in sozluk:
            kucuk = self._tr_normalize(kelime)

            # Aynı normalize biçime sahip birden çok yazım varsa (ör.
            # 'yazdir' ve 'yazdır') Türkçe karakterli olan tercih edilir.
            mevcut = sozluk_map.get(kucuk)
            if mevcut is None or (mevcut.isascii() and not kelime.isascii()):
                sozluk_map[kucuk] = kelime

        self._yerel_duzelt_sozluk_map = sozluk_map
        self._yerel_duzelt_sozluk_kucuk_listesi = sorted(sozluk_map.keys())

        return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

    def _kodu_yerel_duzelt(self, kod):
        sozluk_map, sozluk_kucuk_listesi = self._yerel_duzelt_sozluk_haritasi()

        if not sozluk_kucuk_listesi:
            return kod, set()

        try:
            tanimli_kelimeler = set(self._koddan_tanimlari_cikar(kod))
        except Exception:
            tanimli_kelimeler = set()

        tanimli_kucuk = {str(k).lower() for k in tanimli_kelimeler}

        attr_adlari = re.findall(r"\.\s*([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)", kod)
        tanimli_kucuk |= {a.lower() for a in attr_adlari}
        tanimli_norm = {self._tr_normalize(k) for k in tanimli_kucuk}

        degisiklikler = set()
        cache = {}

        string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
        parcalar = re.split(string_ve_yorum, kod)
        kelime_deseni = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*"

        def bitisik_takasla_duzelt(kelime):
            for i in range(len(kelime) - 1):
                takas = kelime[:i] + kelime[i + 1] + kelime[i] + kelime[i + 2:]

                if takas in sozluk_map:
                    return sozluk_map[takas]

            return None

        def duzelt(match):
            token = match.group(0)

            if len(token) < 4:
                return token

            kucuk = token.lower()

            # Sözlükteki anahtarlar Türkçe karakterleri sadeleştirilmiş
            # (normalize) biçimdedir; doğru yazılmış 'yazdır' da 'yazdir'
            # olarak aranmalı, yoksa doğru kelime "düzeltilip" bozuluyordu.
            norm = self._tr_normalize(token)

            if (kucuk in sozluk_map or norm in sozluk_map
                    or kucuk in tanimli_kucuk or norm in tanimli_norm):
                return token

            kucuk = norm

            if kucuk in cache:
                return cache[kucuk]

            takas = bitisik_takasla_duzelt(kucuk)

            if takas and takas != token:
                degisiklikler.add((token, takas))
                cache[kucuk] = takas
                return takas

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
                cutoff=cutoff,
            )

            if oneri:
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

            if re.fullmatch(string_ve_yorum, parca):
                continue

            parcalar[i] = re.sub(kelime_deseni, duzelt, parca)

        return "".join(parcalar), degisiklikler

    def _en_yakin_eslesme(self, hatali_kelime, adaylar, cutoff=0.6):
        if not adaylar:
            return []

        norm_hatali = self._tr_normalize(hatali_kelime)

        for aday in adaylar:
            if self._tr_normalize(aday) == norm_hatali:
                return [aday]

        norm_harita = {}

        for aday in adaylar:
            norm_harita.setdefault(self._tr_normalize(aday), aday)

        oneri = difflib.get_close_matches(
            norm_hatali,
            list(norm_harita.keys()),
            n=1,
            cutoff=cutoff,
        )

        if oneri:
            return [norm_harita[oneri[0]]]

        return difflib.get_close_matches(
            hatali_kelime,
            list(adaylar),
            n=1,
            cutoff=cutoff,
        )

    def _sozluk_duz_harita(self):
        if self._sozluk_duz_cache is not None:
            return self._sozluk_duz_cache

        harita = {}

        for desen, hedef in SOZLUK.items():
            kelime = str(desen).replace(r"\b", "").strip()
            kelime = kelime.strip('"').strip("'")

            if kelime and " " not in kelime and "." not in kelime:
                harita.setdefault(kelime, str(hedef).strip())

        self._sozluk_duz_cache = harita

        return harita

    def _py_ciplak_index(self):
        if self._py_ciplak_cache is not None:
            return self._py_ciplak_cache

        indeks = {}

        for modul, metotlar in MODUL_METOTLARI.items():
            for tr_metot, py_metot in metotlar.items():
                if "." not in py_metot:
                    indeks.setdefault(py_metot, (modul, tr_metot))

        self._py_ciplak_cache = indeks

        return indeks

    def _satirdaki_sorunlu_token(self, satir_metni, hata_adi):
        sozluk_duz = self._sozluk_duz_harita()

        for token in re.findall(
            r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*",
            satir_metni
        ):
            hedef = sozluk_duz.get(token)

            if hedef:
                ilk = hedef.split(".")[0]

                if ilk == hata_adi or hedef == hata_adi:
                    return token, hedef
            elif token == hata_adi:
                return token, None

        return None, None

    def _iki_nokta_duzelt(self, kod, satir_no):
        satirlar = kod.split("\n")

        if not (0 < satir_no <= len(satirlar)):
            return None

        eski = satirlar[satir_no - 1]
        temiz = eski.strip()

        BLOK = (
            "eğer", "değilse_eğer", "değilse", "döngü", "için",
            "fonksiyon", "sınıf", "dene", "hata_yakala", "sonunda", "ile",
            "if", "elif", "else", "while", "for", "def", "class",
            "try", "except", "finally", "with",
        )

        if (
            temiz
            and not temiz.startswith("#")
            and not temiz.endswith(":")
            and temiz.split()[0] in BLOK
        ):
            satirlar[satir_no - 1] = eski.rstrip() + ":"
            return "\n".join(satirlar), f"• Satır {satir_no}: eksik ':' eklendi."

        return None

    # Girintiyi kapatan / devam ettiren anahtar kelimeler: "beklenen girinti"
    # hatasında bu satırlar içeri itilmez, önlerine 'geç' eklenir.
    _DEVAM_BLOKLARI = (
        "değilse_eğer", "değilse", "hata_yakala", "sonunda",
        "elif", "else", "except", "finally",
    )

    @staticmethod
    def _girinti(satir):
        return len(satir) - len(satir.lstrip(" \t"))

    @classmethod
    def _girinti_birimi(cls, satirlar):
        """Dosyadaki en sık girinti artışı (2..8); bulunamazsa 4."""
        sayac = {}
        onceki = 0
        for satir in satirlar[:5000]:
            temiz = satir.strip()
            if not temiz or temiz.startswith("#"):
                continue
            g = cls._girinti(satir)
            fark = g - onceki
            if 2 <= fark <= 8:
                sayac[fark] = sayac.get(fark, 0) + 1
            onceki = g
        if not sayac:
            return 4
        return max(sayac.items(), key=lambda kv: (kv[1], -kv[0]))[0]

    @staticmethod
    def _onceki_dolu_satir(satirlar, i):
        j = i - 1
        while j >= 0:
            temiz = satirlar[j].strip()
            if temiz and not temiz.startswith("#"):
                return j
            j -= 1
        return -1

    def _girinti_hatasi_duzelt(self, kod, satir_no, hata_mesaji):
        satirlar = kod.split("\n")
        m = hata_mesaji.lower()
        i = satir_no - 1
        birim = self._girinti_birimi(satirlar)

        if "expected an indented block" in m:
            # Başlık satırı dosyanın sonundaysa / gövde yoksa 'geç' ekle.
            j = self._onceki_dolu_satir(satirlar, min(i, len(satirlar)))
            baslik_g = self._girinti(satirlar[j]) if j >= 0 else 0
            hedef = satirlar[i] if 0 <= i < len(satirlar) else ""
            govde = hedef.strip()
            devam = {self._tr_normalize(k) for k in self._DEVAM_BLOKLARI}
            ilk = self._tr_normalize(govde.split()[0].rstrip(":")) if govde else ""
            if not govde or ilk in devam:
                ekle_yer = i if 0 <= i < len(satirlar) else len(satirlar)
                satirlar.insert(ekle_yer, " " * (baslik_g + birim) + "geç")
                return ("\n".join(satirlar),
                        f"• Satır {ekle_yer + 1}: boş blok için 'geç' eklendi.")
            satirlar[i] = " " * (baslik_g + birim) + hedef.lstrip(" \t")
            return ("\n".join(satirlar),
                    f"• Satır {satir_no}: eksik girinti eklendi.")

        if not (0 <= i < len(satirlar)):
            return None
        hedef = satirlar[i]
        govde = hedef.lstrip(" \t")
        if not govde:
            return None
        mevcut = self._girinti(hedef)

        if "unexpected indent" in m:
            j = self._onceki_dolu_satir(satirlar, i)
            if j < 0:
                yeni = 0
            else:
                yeni = self._girinti(satirlar[j])
                if satirlar[j].rstrip().endswith(":"):
                    yeni += birim
        elif "unindent does not match" in m or "inconsistent" in m:
            # Önceki satırlardan açık girinti seviyelerini çıkar ve mevcut
            # girintiye en yakın (ondan büyük olmayan) seviyeye hizala.
            yigin = [0]
            for k in range(i):
                temiz = satirlar[k].strip()
                if not temiz or temiz.startswith("#"):
                    continue
                g = self._girinti(satirlar[k])
                while yigin and yigin[-1] > g:
                    yigin.pop()
                if not yigin or yigin[-1] < g:
                    yigin.append(g)
            adaylar = [g for g in yigin if g <= mevcut]
            yeni = max(adaylar) if adaylar else 0
        else:
            return None

        if yeni == mevcut:
            return None
        satirlar[i] = " " * yeni + govde
        return "\n".join(satirlar), f"• Satır {satir_no}: girinti düzeltildi."

    @staticmethod
    def _esittir_duzelt(kod, satir_no):
        """Koşulda '=' yerine '==' (ör. 'eğer x = 5:')."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        eski = satirlar[satir_no - 1]
        m = re.match(
            r"^(\s*(?:eğer|değilse_eğer|döngü|if|elif|while)\b)(.*)$", eski)
        if not m:
            return None
        govde = m.group(2)
        yeni = re.sub(r"(?<![=!<>:+\-*/%&|^])=(?!=)", "==", govde, count=1)
        if yeni == govde:
            return None
        satirlar[satir_no - 1] = m.group(1) + yeni
        return "\n".join(satirlar), f"• Satır {satir_no}: koşulda '=' -> '==' yapıldı."

    @staticmethod
    def _satir_parantez_kapat(kod, satir_no):
        """'(' was never closed: kapanışı hatanın olduğu satıra ekler."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        # Metinleri kabaca ayıkla ki tırnak içindeki parantezler sayılmasın.
        sade = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*$', "", satir)
        acik = []
        for ch in sade:
            if ch in "([{":
                acik.append(ch)
            elif ch in ")]}" and acik:
                acik.pop()
        if not acik:
            return None
        ek = "".join({"(": ")", "[": "]", "{": "}"}[c] for c in reversed(acik))
        govde = satir.rstrip()
        if govde.endswith(":"):
            satirlar[satir_no - 1] = govde[:-1] + ek + ":"
        else:
            satirlar[satir_no - 1] = govde + ek
        return "\n".join(satirlar), f"• Satır {satir_no}: kapatılmamış parantez eklendi: {ek}"

    def _sozdizimi_duzelt(self, kod, satir_no, hata_mesaji):
        msg_kucuk = hata_mesaji.lower()

        if "indent" in msg_kucuk or "inconsistent use of tabs" in msg_kucuk:
            duzeltme = self._girinti_hatasi_duzelt(kod, satir_no, hata_mesaji)
            if duzeltme:
                return duzeltme

        duzeltme = self._iki_nokta_duzelt(kod, satir_no)

        if duzeltme:
            return duzeltme

        satirlar = kod.split("\n")

        if "maybe you meant '=='" in msg_kucuk or "cannot assign to" in msg_kucuk:
            duzeltme = self._esittir_duzelt(kod, satir_no)
            if duzeltme:
                return duzeltme

        if "was never closed" in msg_kucuk:
            duzeltme = self._satir_parantez_kapat(kod, satir_no)
            if duzeltme:
                return duzeltme

        if "invalid character" in msg_kucuk and 0 < satir_no <= len(satirlar):
            eski = satirlar[satir_no - 1]
            yeni = (eski.replace("“", '"').replace("”", '"').replace("„", '"')
                    .replace("‘", "'").replace("’", "'").replace("‚", "'"))
            if yeni != eski:
                satirlar[satir_no - 1] = yeni
                return "\n".join(satirlar), f"• Satır {satir_no}: akıllı tırnaklar düz tırnağa çevrildi."

        if "unmatched" in hata_mesaji or "unexpected EOF" in hata_mesaji:
            acik_parantezler = []

            for ch in kod:
                if ch in "([{":
                    acik_parantezler.append(ch)
                elif ch in ")]}":
                    if acik_parantezler:
                        acik_parantezler.pop()

            ek = "".join(
                {"(": ")", "[": "]", "{": "}"}[p]
                for p in reversed(acik_parantezler)
            )

            if ek:
                if not satirlar:
                    satirlar = [""]

                satirlar[-1] += ek

                return "\n".join(satirlar), f"• Kapatılmamış parantez eklendi: {ek}"

        if "unterminated triple-quoted string" in msg_kucuk:
            tirnak = '"' * 3 if kod.count('"' * 3) % 2 == 1 else "'" * 3
            satirlar.append(tirnak)
            return "\n".join(satirlar), f"• Kapatılmamış çok satırlı metne {tirnak} eklendi."

        if "unterminated string" in hata_mesaji:
            if 0 < satir_no <= len(satirlar):
                satir = satirlar[satir_no - 1]

                if satir.count('"') % 2 == 1:
                    satirlar[satir_no - 1] = satir + '"'
                    return "\n".join(satirlar), f"• Satır {satir_no}: eksik tırnak eklendi."
                elif satir.count("'") % 2 == 1:
                    satirlar[satir_no - 1] = satir + "'"
                    return "\n".join(satirlar), f"• Satır {satir_no}: eksik tırnak eklendi."

        return None

    @staticmethod
    def _python_riskleri(python_kodu):
        """Python kodundaki, denemek için çalıştırılması riskli yapılar
        (dosya silme, ağ, başka program çalıştırma...). Gerekçe listesi döner;
        boşsa kod güvenle denenebilir. Ayrıştırılamayan kod zaten çalışmaz."""
        try:
            agac = ast.parse(python_kodu)
        except (SyntaxError, ValueError):
            return []
        riskler = []

        def ekle(gerekce):
            if gerekce not in riskler:
                riskler.append(gerekce)

        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Import):
                for ad in dugum.names:
                    kok = ad.name.split(".")[0]
                    if kok in RISKLI_MODULLER:
                        ekle(RISKLI_MODULLER[kok])
            elif isinstance(dugum, ast.ImportFrom):
                kok = (dugum.module or "").split(".")[0]
                if kok in RISKLI_MODULLER:
                    ekle(RISKLI_MODULLER[kok])
            elif isinstance(dugum, ast.Call):
                ad = dugum.func.id if isinstance(dugum.func, ast.Name) else None
                if ad in RISKLI_CAGRILAR:
                    ekle(RISKLI_CAGRILAR[ad])
                elif ad == "open" and IDECore._yazma_kipinde_mi(dugum):
                    ekle("dosyaya yazma (open)")
        return riskler

    @staticmethod
    def _yazma_kipinde_mi(cagri):
        """open(...) çağrısı yazma/ekleme kipinde mi? Kip bir sabit değilse
        (değişkenden geliyorsa) temkinli davranılır."""
        kip = None
        if len(cagri.args) >= 2:
            kip = cagri.args[1]
        for k in cagri.keywords:
            if k.arg == "mode":
                kip = k.value
        if kip is None:
            return False
        if isinstance(kip, ast.Constant) and isinstance(kip.value, str):
            return any(c in kip.value for c in "wax+")
        return True

    def calistirma_riskleri(self, kod):
        """TürKod kodu için _python_riskleri; çevrilemeyen kod çalıştırılamaz."""
        try:
            python_kodu = turkce_kodu_donustur(kod or "")
        except Exception:
            return []
        return self._python_riskleri(python_kodu)

    def _diff_olustur(self, eski, yeni):
        fark = difflib.unified_diff(
            eski.splitlines(keepends=True),
            yeni.splitlines(keepends=True),
            fromfile="Orijinal",
            tofile="Düzeltilmiş",
            lineterm="",
        )

        return "\n".join(fark)

    def _nameerror_duzelt(self, duzeltilmis, satir, hata_adi, degisiklikler, beklenen_importlar):
        satirlar = duzeltilmis.split("\n")
        satir_metni = satirlar[satir - 1] if 0 < satir <= len(satirlar) else ""

        token, hedef = self._satirdaki_sorunlu_token(satir_metni, hata_adi)

        if token is None and satir_metni:
            satir_tokenlari = re.findall(
                r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*",
                satir_metni
            )

            yakin = self._en_yakin_eslesme(hata_adi, satir_tokenlari, cutoff=0.65)

            if yakin:
                token = yakin[0]
                hedef = self._sozluk_duz_harita().get(token)

        if token is None:
            return duzeltilmis, f"• Satır {satir}: '{hata_adi}' için öneri bulunamadı.", False

        if hedef is None:
            tanimlar = list(kullanici_tanimlari(duzeltilmis))
            oner = self._en_yakin_eslesme(token, tanimlar, cutoff=0.7)
            dogru = oner[0] if oner else None

            if dogru and dogru != token:
                satirlar[satir - 1] = re.sub(
                    rf"\b{re.escape(token)}\b",
                    dogru,
                    satir_metni
                )

                yeni_kod = "\n".join(satirlar)
                msg = f"• Tanımsız '{token}' -> '{dogru}' olarak düzeltildi."

                return yeni_kod, msg, True

            girinti = len(satir_metni) - len(satir_metni.lstrip())
            satirlar.insert(satir - 1, " " * girinti + f"{token} = Hiçlik")

            yeni_kod = "\n".join(satirlar)
            msg = f"• '{token}' tanımsız; satır {satir} üstüne '{token} = Hiçlik' eklendi."

            return yeni_kod, msg, True

        if token in MODUL_CEVIRILERI:
            beklenen_importlar.add(token)
            msg = f"• Satır {satir}: '{token}' içe aktarılmamış; 'içe_aktar {token}' ekleniyor."

            return duzeltilmis, msg, True

        son = hedef.split(".")[-1]
        alt = self._py_ciplak_index().get(son) or self._py_ciplak_index().get(hata_adi)

        if not alt:
            return duzeltilmis, f"• Satır {satir}: '{token}' için çalışan karşılık bulunamadı.", False

        modul_tr, metot_tr = alt
        yeni = f"{modul_tr}.{metot_tr}"

        satirlar[satir - 1] = re.sub(
            rf"\b{re.escape(token)}\b",
            yeni,
            satirlar[satir - 1],
            count=1
        )

        yeni_kod = "\n".join(satirlar)
        beklenen_importlar.add(modul_tr)

        msg = (
            f"• Satır {satir}: '{token}' -> '{yeni}' olarak düzeltildi. "
            f"'{modul_tr}' import listesine eklendi."
        )

        return yeni_kod, msg, True

    # Çalışma zamanı hataları için (kodu değiştirmeden) verilen açıklayıcı
    # ipuçları.
    _CALISMA_IPUCLARI = (
        (r"ZeroDivisionError", "sıfıra bölme yapılıyor; böleni kontrol edin."),
        (r'can only concatenate str \(not "(\w+)"\) to str',
         "metin ile başka bir türü birleştiriyorsunuz; değeri metin(...) ile dönüştürün."),
        (r"unsupported operand type\(s\)",
         "uyumsuz türler arasında işlem yapılıyor (ör. metin + sayı); tamsayı(...) / metin(...) kullanın."),
        (r"invalid literal for int\(\)",
         "sayıya çevrilemeyen bir metin tamsayı(...) ile dönüştürülüyor."),
        (r"KeyError", "sözlükte olmayan bir anahtar kullanılıyor."),
        (r"RecursionError", "fonksiyon kendini sonu gelmeden çağırıyor olabilir."),
        (r"takes (\d+) positional arguments? but (\d+)",
         "fonksiyona beklenenden farklı sayıda argüman verilmiş."),
        (r"missing \d+ required positional argument",
         "fonksiyon çağrısında eksik argüman var."),
        (r"object is not callable", "fonksiyon olmayan bir değer çağrılıyor (ad çakışması?)."),
        (r"object is not subscriptable", "indekslenemeyen bir değere [ ] uygulanıyor."),
        (r"has no attribute '([^']+)'", "nesnede böyle bir özellik/metot yok; adı kontrol edin."),
        (r"FileNotFoundError", "dosya bulunamadı; yolu kontrol edin."),
        (r"UnboundLocalError",
         "değişken, fonksiyon içinde atanmadan önce kullanılıyor."),
    )

    # Kontrol çalıştırmasında programın kullanıcıdan girdi beklemesini ve
    # uyumasını engelleyen tek satırlık ön ek (satır numaraları için offset'e
    # dahildir).
    _KONTROL_ON_EKI = (
        "import builtins as _tk_b, time as _tk_t; "
        "_tk_b.input = lambda *a, **k: '1'; "
        "_tk_t.sleep = lambda *a, **k: None"
    )

    def duzelt_kod(self, kod, progress_callback=None, calistirma_izni=None):
        """calistirma_izni: True = kod (riskli olsa da) denenebilir; False = hiç
        çalıştırılmaz; None = yalnızca risk içermeyen kod çalıştırılır."""
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Düzeltilecek kod bulunamadı."}

        if calistirma_izni is None:
            calistir = not self.calistirma_riskleri(kod)
        else:
            calistir = bool(calistirma_izni)

        # Akıllı düzeltme motoru (akilli_duzeltici.py). Beklenmedik bir iç
        # hata olursa eski gelişmiş düzeltmeye geri düşülür; kullanıcı yine
        # bir sonuç alır.
        try:
            return AkilliDuzeltici(self, progress_callback, calistir=calistir).calistir(kod)
        except Exception:
            traceback.print_exc()
            return self.gelismis_duzelt(kod, progress_callback, calistir=calistir)

    def _yerel_duzeltme_sonucu(self, kod):
        yeni_kod, degisiklikler = self._kodu_yerel_duzelt(kod)

        if not degisiklikler:
            return {
                "ok": True,
                "degisiklik": False,
                "mesaj": "Sözlüğe göre düzeltilecek belirgin yazım hatası bulunamadı.",
            }

        return {
            "ok": True,
            "degisiklik": True,
            "kod": yeni_kod,
            "degisiklikler": sorted(degisiklikler),
            "diff": self._diff_olustur(kod, yeni_kod),
        }

    def _kontrol_calistir(self, python_exe, py, zaman_asimi):
        """Python kodunu benzersiz bir geçici dosyada, girdi beklemeden
        çalıştırır. (sonuc, dosya_yolu) döndürür."""
        # Düzeltme denemeleri kullanıcının programını defalarca çalıştırır;
        # programın oluşturduğu/sildiği dosyalar gerçek klasörlere değil,
        # her denemeye özel boş bir geçici klasöre gider.
        calisma_dizini = tempfile.mkdtemp(prefix="turkod_kontrol_")
        temp_path = os.path.join(calisma_dizini, "turkod_kontrol.py")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(py)

            sonuc = subprocess.run(
                [python_exe, "-X", "utf8", temp_path],
                cwd=calisma_dizini,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=zaman_asimi,
                env=self._subprocess_env(),
                **self._subprocess_flags()
            )
            return sonuc, temp_path
        finally:
            shutil.rmtree(calisma_dizini, ignore_errors=True)

    @staticmethod
    def _hata_satiri(stderr, temp_path, offset):
        """Traceback'te kullanıcının dosyasına ait EN İÇTEKİ satırı bulur
        (fonksiyon içindeki hatalar için ilk değil son çerçeve doğrudur)."""
        ad = os.path.basename(temp_path) if temp_path else ""
        satirlar = [
            int(m.group(2))
            for m in re.finditer(r'File "([^"]+)", line (\d+)', stderr)
            if not ad or os.path.basename(m.group(1)) == ad
        ]
        if not satirlar:
            m = re.search(r"line (\d+)", stderr)
            satirlar = [int(m.group(1))] if m else [1 + offset]
        return max(1, satirlar[-1] - offset)

    def gelismis_duzelt(self, kod, progress_callback=None, calistir=True):
        MAKS_DONGU = self._sayi_ayar("duzeltme_maks_dongu", 12)
        ZAMAN_ASIMI = self._sayi_ayar("duzeltme_zaman_asimi", 5)
        MESAJ_ARALIGI = self._sayi_ayar("duzeltme_mesaj_araligi", 100)
        # Sözdizimi/girinti düzeltmeleri çalıştırma gerektirmez ve ucuzdur;
        # bunlar çalıştırma bütçesinden (MAKS_DONGU) ayrı sayılır.
        MAKS_SOZDIZIMI = 200

        duzeltilmis = kod.replace("\r\n", "\n").replace("\r", "\n")

        beklenen_importlar = set()
        degisiklikler = []
        gorulen = set()
        son_mesaj = ""

        def mesaj_ver(metin):
            if progress_callback:
                time.sleep(MESAJ_ARALIGI / 1000.0)
                self._guvenli_callback(progress_callback, metin)

        def _hash(kod_str):
            return hashlib.sha256(kod_str.encode("utf-8")).hexdigest()[:16]

        # --- Ön geçişler (çalıştırma gerektirmeyen) ----------------------
        # a) Sekme/boşluk karışık girintiyi tek tipe getir.
        satirlar0 = duzeltilmis.split("\n")
        bosluklu = any(s_[:1] == " " for s_ in satirlar0)
        sekmeli = any(s_[:1] == "\t" for s_ in satirlar0)
        if bosluklu and sekmeli:
            duzeltilmis = "\n".join(
                s_[: self._girinti(s_)].expandtabs(4) + s_[self._girinti(s_):]
                for s_ in satirlar0
            )
            degisiklikler.append("• Karışık sekme/boşluk girintisi boşluğa çevrildi.")

        # b) Sözlüğe dayalı yazım düzeltmesi (yanlış yazılmış anahtar
        #    kelimeler: 'yazdir' -> 'yazdır', 'eger' -> 'eğer' ...).
        try:
            yerel, yerel_degisiklikler = self._kodu_yerel_duzelt(duzeltilmis)
        except Exception:
            yerel, yerel_degisiklikler = duzeltilmis, set()
        if yerel_degisiklikler:
            duzeltilmis = yerel
            for eski, yeni in sorted(yerel_degisiklikler):
                degisiklikler.append(f"• Yazım: '{eski}' -> '{yeni}'")
            mesaj_ver(f"Yazım hataları düzeltildi ({len(yerel_degisiklikler)}).")

        python_exe, python_hata = self._python_exe_bul()
        if not calistir:
            python_exe, python_hata = None, "Güvenlik nedeniyle kod çalıştırılmadı."

        if not python_exe:
            # Python yoksa en azından yazım düzeltmesini döndür.
            sonuc = self._yerel_duzeltme_sonucu(kod)
            sonuc["son_mesaj"] = f"• {python_hata} (yalnızca yazım düzeltmesi yapıldı)"
            return sonuc

        _cevirme_cache = {}

        def _python_calisma():
            cache_key = _hash(duzeltilmis) + str(frozenset(beklenen_importlar))

            if cache_key in _cevirme_cache:
                return _cevirme_cache[cache_key]

            try:
                py = turkce_kodu_donustur(duzeltilmis)
            except Exception:
                return None, 0

            enjekte = [self._KONTROL_ON_EKI] + [
                f"import {MODUL_CEVIRILERI.get(m, m)}"
                for m in sorted(beklenen_importlar)
            ]

            sonuc = "\n".join(enjekte) + "\n" + py, len(enjekte)

            _cevirme_cache[cache_key] = sonuc

            return sonuc

        def _dongu_satiri_bul(kod_str):
            for i, satir in enumerate(kod_str.split("\n"), 1):
                temiz = satir.strip()

                if temiz.startswith("döngü") or temiz.startswith("için"):
                    return i

            return None

        calistirma = 0
        sozdizimi = 0

        while calistirma < MAKS_DONGU and sozdizimi < MAKS_SOZDIZIMI:
            durum = (_hash(duzeltilmis), frozenset(beklenen_importlar))

            if durum in gorulen:
                break

            gorulen.add(durum)

            py, offset = _python_calisma()

            if py is None:
                son_mesaj = "• Çeviri hatası: kod dönüştürülemedi."
                break

            try:
                ast.parse(py)
            except SyntaxError as e:
                sozdizimi += 1
                satir = max(1, (e.lineno or 1) - offset)
                tip = type(e).__name__
                duzeltme = self._sozdizimi_duzelt(duzeltilmis, satir, str(e.msg or ""))

                if duzeltme:
                    duzeltilmis, msg = duzeltme
                    degisiklikler.append(msg)
                    mesaj_ver(f"⚠️ Hata {satir}. satırında. Tip: {tip}\n{msg}")
                    continue

                py_satirlar = py.split("\n")
                py_satir = (e.lineno or 1)
                py_goster = py_satirlar[py_satir - 1].strip() if 0 < py_satir <= len(py_satirlar) else "?"

                degisiklikler.append(
                    f"• Satır {satir}: {tip} ({e.msg}) otomatik düzeltilemedi. "
                    f"Python tarafı: {py_goster}"
                )
                break

            calistirma += 1

            try:
                sonuc, temp_path = self._kontrol_calistir(python_exe, py, ZAMAN_ASIMI)
            except subprocess.TimeoutExpired:
                dongu_satiri = _dongu_satiri_bul(duzeltilmis)
                satir_bilgi = f" (şüpheli satır: {dongu_satiri})" if dongu_satiri else ""

                son_mesaj = (
                    f"• Kod {ZAMAN_ASIMI} saniyede bitmedi "
                    f"(sonsuz döngü veya uzun işlem?){satir_bilgi}. "
                    f"Kalan kontroller iptal edildi."
                )
                break
            except Exception as e:
                son_mesaj = f"• Çalıştırma hatası: {e}"
                break

            if sonuc.returncode == 0:
                break

            stderr = sonuc.stderr
            satir = self._hata_satiri(stderr, temp_path, offset)
            son_satir = stderr.splitlines()[-1] if stderr.splitlines() else "Bilinmeyen hata"

            if "NameError:" not in stderr:
                if "ModuleNotFoundError:" in stderr:
                    m_mod = re.search(r"No module named '([^']+)'", stderr)
                    mod_ad = m_mod.group(1) if m_mod else "?"

                    degisiklikler.append(
                        f"• '{mod_ad}' modülü kurulu değil (pip yükle {mod_ad}). "
                        f"Kod dönüştürüldü ama çalıştırılamaz."
                    )
                    break

                if "IndexError:" in stderr:
                    degisiklikler.append(
                        f"• Satır {satir}: IndexError - liste/dizi sınırı aşıldı. "
                        f"İndeks değerini kontrol edin."
                    )
                    break

                ipucu = None
                for desen, aciklama in self._CALISMA_IPUCLARI:
                    if re.search(desen, son_satir):
                        ipucu = aciklama
                        break

                if ipucu:
                    degisiklikler.append(f"• Satır {satir}: {son_satir}\n  İpucu: {ipucu}")
                else:
                    degisiklikler.append(f"• Satır {satir}: {son_satir} (otomatik düzeltme yok)")
                break

            m_ad = re.search(r"name '([^']+)' is not defined", stderr)
            hata_adi = m_ad.group(1) if m_ad else ""

            if not hata_adi:
                m_fallback = re.search(r"NameError:.*?'(\w+)'", stderr)
                hata_adi = m_fallback.group(1) if m_fallback else "bilinmeyen"

            mesaj_ver(f"⚠️ Hata {satir}. satırında. Tip: NameError")

            satirlar = duzeltilmis.split("\n")
            satir_metni = satirlar[satir - 1] if 0 < satir <= len(satirlar) else ""

            token, hedef = self._satirdaki_sorunlu_token(satir_metni, hata_adi)

            if token is None and satir_metni:
                satir_tokenlari = re.findall(
                    r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*",
                    satir_metni
                )

                yakin = self._en_yakin_eslesme(hata_adi, satir_tokenlari, cutoff=0.65)

                if yakin:
                    token = yakin[0]
                    hedef = self._sozluk_duz_harita().get(token)

            if token is None:
                degisiklikler.append(f"• Satır {satir}: '{hata_adi}' için öneri bulunamadı.")
                break

            if hedef is None:
                mesaj_ver("Bu bir değişken hatası.")

                tanimlar = list(kullanici_tanimlari(duzeltilmis))
                oner = self._en_yakin_eslesme(token, tanimlar, cutoff=0.7)
                dogru = oner[0] if oner else None

                if dogru and dogru != token:
                    satirlar[satir - 1] = re.sub(
                        rf"\b{re.escape(token)}\b",
                        dogru,
                        satir_metni
                    )

                    duzeltilmis = "\n".join(satirlar)
                    msg = f"• Tanımsız '{token}' -> '{dogru}' olarak düzeltildi."

                    degisiklikler.append(msg)
                    mesaj_ver(msg)
                    continue

                # Bilinen bir modül adıysa tanımsız değişken değil, eksik
                # içe aktarmadır.
                if token in MODUL_CEVIRILERI:
                    beklenen_importlar.add(token)
                    msg = (
                        f"• Satır {satir}: '{token}' içe aktarılmamış; "
                        f"'içe_aktar {token}' ekleniyor."
                    )
                    degisiklikler.append(msg)
                    mesaj_ver(msg)
                    continue

                girinti = len(satir_metni) - len(satir_metni.lstrip())
                satirlar.insert(satir - 1, " " * girinti + f"{token} = Hiçlik")
                duzeltilmis = "\n".join(satirlar)

                msg = (
                    f"• '{token}' tanımsız; satır {satir} üstüne "
                    f"'{token} = Hiçlik' eklendi."
                )

                degisiklikler.append(msg)
                mesaj_ver(msg)
                continue

            if token in MODUL_CEVIRILERI:
                beklenen_importlar.add(token)

                msg = (
                    f"• Satır {satir}: '{token}' içe aktarılmamış; "
                    f"'içe_aktar {token}' ekleniyor."
                )

                degisiklikler.append(msg)
                mesaj_ver(msg)
                continue

            son = hedef.split(".")[-1]
            alt = self._py_ciplak_index().get(son) or self._py_ciplak_index().get(hata_adi)

            if not alt:
                degisiklikler.append(
                    f"• Satır {satir}: '{token}' için çalışan karşılık bulunamadı."
                )
                break

            modul_tr, metot_tr = alt
            yeni = f"{modul_tr}.{metot_tr}"

            satirlar[satir - 1] = re.sub(
                rf"\b{re.escape(token)}\b",
                yeni,
                satirlar[satir - 1],
                count=1
            )

            duzeltilmis = "\n".join(satirlar)
            beklenen_importlar.add(modul_tr)

            msg = (
                f"• Satır {satir}: '{token}' -> '{yeni}' olarak düzeltildi. "
                f"'{modul_tr}' import listesine eklendi."
            )

            degisiklikler.append(msg)
            mesaj_ver(msg)
            continue

        if beklenen_importlar:
            mevcut_moduller = set(re.findall(
                r"^\s*içe_aktar\s+([A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*)",
                duzeltilmis,
                re.MULTILINE
            ))

            eklenecek = [
                f"içe_aktar {m}"
                for m in sorted(beklenen_importlar)
                if m not in mevcut_moduller
            ]

            if eklenecek:
                duzeltilmis = "\n".join(eklenecek) + "\n" + duzeltilmis

            beklenen_importlar.clear()

        dogrulama = ""
        py, offset = _python_calisma()

        if py is not None:
            try:
                ast.parse(py)
            except SyntaxError as e2:
                dogrulama = f"⚠️ Kalan sözdizimi hatası: Satır {max(1, (e2.lineno or 1) - offset)}"
            else:
                try:
                    v, _ = self._kontrol_calistir(python_exe, py, ZAMAN_ASIMI)

                    if v.returncode == 0:
                        dogrulama = "✅ Doğrulandı: kod hatasız çalıştı."
                    else:
                        tail = v.stderr.splitlines()[-1] if v.stderr.splitlines() else ""
                        dogrulama = f"⚠️ Kalan hata: {tail}"
                except subprocess.TimeoutExpired:
                    dogrulama = (
                        f"⏳ Son doğrulama {ZAMAN_ASIMI} saniyelik "
                        "zaman aşımına uğradı (sonsuz döngü?)."
                    )
                except Exception as e2:
                    dogrulama = f"⚠️ Son doğrulama yapılamadı: {e2}"

        degisti = duzeltilmis != kod.replace("\r\n", "\n").replace("\r", "\n")

        return {
            "ok": True,
            "degisiklik": bool(degisiklikler),
            "kod": duzeltilmis,
            "degisiklikler": degisiklikler,
            "son_mesaj": son_mesaj,
            "dogrulama": dogrulama,
            "diff": self._diff_olustur(kod, duzeltilmis) if degisti else "",
        }

    # ------------------------------------------------------------------
    # Çalıştırma / terminal
    # ------------------------------------------------------------------
    def kodu_calistir(self, kod, on_output=None, on_exit=None):
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Çalıştırılacak kod yok."}

        sonuc = dogrula(kod)

        if not sonuc.basarili:
            hatalar = []

            for h in sonuc.hatalar:
                hatalar.append({
                    "satir": getattr(h, "satir", None),
                    "sutun": getattr(h, "sutun", None),
                    "mesaj": str(h),
                })

            return {
                "ok": False,
                "hatalar": hatalar,
            }

        try:
            python_kodu = turkce_kodu_donustur(kod)
        except Exception as e:
            return {"ok": False, "hata": f"Çeviri hatası: {e}"}

        python_exe, hata = self._python_exe_bul()

        if not python_exe:
            return {"ok": False, "hata": hata}

        # Her çalıştırma kendi geçici klasörünü kullanır. Eskiden herkes
        # %TEMP%\turkce_kod_calisma.py ve %TEMP%\runner.py dosyalarını
        # paylaşıyordu: iki pencere / üst üste iki çalıştırma birbirinin
        # programını eziyor, %TEMP%'teki başıboş bir "random.py" da kullanıcı
        # programında standart kütüphaneyi gölgeliyordu.
        try:
            calisma_dizini = tempfile.mkdtemp(prefix="turkod_calisma_")
            kod_path = os.path.join(calisma_dizini, "turkce_kod_calisma.py")
            runner_path = os.path.join(calisma_dizini, "runner.py")
            with open(kod_path, "w", encoding="utf-8") as f:
                f.write(python_kodu)

            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(RUNNER_KODU)
        except Exception as e:
            return {"ok": False, "hata": str(e)}

        def _temizle():
            # Yalnızca bizim yazdığımız dosyalar silinir; program klasöre
            # kendi dosyalarını yazdıysa klasör (boş olmadığından) kalır.
            for yol in (kod_path, runner_path):
                try:
                    os.unlink(yol)
                except OSError:
                    pass
            try:
                os.rmdir(calisma_dizini)
            except OSError:
                pass

        # Başlat/durdur/yeniden başlat tek bir kilit altında: iki "Çalıştır"
        # aynı anda gelirse ilk süreç sahipsiz kalıp Durdur'dan kaçıyordu.
        with self._calistirma_kilit:
            if self._calistirma_process is not None:
                self._calistirmayi_sonlandir()
                # Eski süreç artık "güncel" değil: okuyucusu, yeni çalıştırmanın
                # terminaline "bitti" olayı göndermez.
                self._calistirma_process = None

            # Not: Eskiden burada terminale "> python -u runner.py" yazılıyordu;
            # kullanıcı için anlamsız teknik bir ayrıntı olduğundan kaldırıldı.
            try:
                process = subprocess.Popen(
                    [python_exe, "-X", "utf8", "-u", runner_path],
                    cwd=calisma_dizini,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=self._subprocess_env(),
                    **self._subprocess_flags()
                )
            except Exception as e:
                _temizle()
                return {"ok": False, "hata": str(e)}

            self._calistirma_process = process

        threading.Thread(
            target=self._terminal_oku,
            args=(process, on_output, on_exit, _temizle),
            daemon=True
        ).start()

        return {
            "ok": True,
            "pid": process.pid,
        }

    def _terminal_oku(self, process, on_output=None, on_exit=None, on_temizlik=None):
        """Sürecin çıktısını okur ve iletir.

        Süreç başka bir çalıştırmayla DEĞİŞTİRİLDİYSE (yeniden Çalıştır,
        debug başlat) çıktısı ve çıkış olayı artık iletilmez: eskiden öldürülen
        programın "bitti" olayı yeni programın terminaline düşüyor, çalışma
        göstergesini kapatıyor ve "[Program 1 koduyla sonlandı]" yazıyordu.
        on_temizlik her durumda çağrılır.
        """
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        fd = process.stdout.fileno()

        def guncel():
            return self._calistirma_process is process

        kod = -1
        try:
            while True:
                ham = os.read(fd, 4096)

                if not ham:
                    break

                metin = cozucu.decode(ham)

                if metin and guncel():
                    self._guvenli_callback(on_output, metin)

            kalan = cozucu.decode(b"", final=True)

            if kalan and guncel():
                self._guvenli_callback(on_output, kalan)

            kod = process.wait()
        except Exception as e:
            if guncel():
                self._guvenli_callback(on_output, f"[Terminal okuma hatası: {e}]\n")

        with self._calistirma_kilit:
            hala_guncel = guncel()
            # Bu arada yeni bir çalıştırma başlamışsa onun sürecini silme.
            if hala_guncel:
                self._calistirma_process = None

        try:
            process.stdout.close()
        except Exception:
            pass
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass

        # Çıkış bilgisi on_exit ile (calistirma_bitti olayı) iletilir;
        # arayüz bunu kendisi gösterir.
        if hala_guncel:
            self._guvenli_callback(on_exit, kod)
        if on_temizlik is not None:
            self._guvenli_callback(on_temizlik, kod)

    @staticmethod
    def _sureci_oldur(proc):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()

    def _calistirmayi_sonlandir(self):
        """Yeniden çalıştırma / debug başlatma öncesi YALNIZCA çalışan
        programı öldürür. (kodu_durdur'un kabuk komutu yedeği burada
        kullanılmaz: eskiden program zaten bitmişse süren bir "pip yükle"
        sessizce öldürülüyordu.)"""
        proc = self._calistirma_process
        if proc is not None and proc.poll() is None:
            try:
                self._sureci_oldur(proc)
            except Exception:
                pass

    def kodu_durdur(self):
        proc = getattr(self, "_calistirma_process", None)

        if proc is None or proc.poll() is not None:
            # Program yoksa terminalde takılı kalmış kabuk komutları
            # (ör. "pause", "python" REPL'i) durdurulur — hepsi.
            canli = [k for k in list(self._kabuk_surecleri) if k.poll() is None]
            if canli:
                hata = None
                for kabuk in canli:
                    try:
                        self._sureci_oldur(kabuk)
                    except Exception as e:
                        hata = str(e)
                return {"ok": hata is None, **({"hata": hata} if hata else {})}
            return {"ok": False, "hata": "Çalışan süreç yok."}

        try:
            self._sureci_oldur(proc)
        except Exception as e:
            return {"ok": False, "hata": str(e)}

        return {"ok": True}

    def terminal_komut(self, komut, on_output=None):
        ham = komut or ""
        komut = ham.strip()

        proc = getattr(self, "_calistirma_process", None)

        if proc is not None and proc.poll() is None and proc.stdin:
            # Çalışan programa girdi olduğu gibi (boş satır ve baştaki/sondaki
            # boşluklar dahil) iletilir; eskiden boş Enter reddediliyordu.
            try:
                proc.stdin.write(ham + "\n")
                proc.stdin.flush()

                return {
                    "ok": True,
                    "kip": "stdin",
                }
            except Exception as e:
                return {"ok": False, "hata": str(e)}

        if not komut:
            return {"ok": False, "hata": "Komut boş."}

        # Komut satırı arayüz tarafından zaten yazılıyor ("> komut");
        # burada tekrar yazmak her komutu iki kez gösteriyordu.
        threading.Thread(
            target=self._terminal_komut_calistir,
            args=(komut, on_output),
            daemon=True
        ).start()

        return {
            "ok": True,
            "kip": "shell",
        }

    @staticmethod
    def _kabuk_kod_sayfasi():
        """cmd yerleşik komutlarının (dir, ipconfig …) çıktı kod sayfası."""
        if os.name == "nt":
            try:
                import ctypes
                return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
            except Exception:
                return "cp857"
        return "utf-8"

    def _terminal_komut_calistir(self, komut, on_output=None):
        try:
            if pip_yardim_mi(komut):
                self._guvenli_callback(on_output, PIP_YARDIM)
                return
            python_exe, _ = self._python_exe_bul()
            yeni_komut = pip_komutu_cevir(komut, python_exe, self._kullanici_paket_yolu())
            if yeni_komut:
                komut = yeni_komut
            cwd = (
                self.proje_dizini
                if self.proje_dizini and os.path.isdir(self.proje_dizini)
                else os.getcwd()
            )

            # * env: kullanıcı paket klasörü (pip yükle ile kurulanlar) ve
            #   UTF-8 çıktı; eskiden terminalde "python app.py" kurulu paketi
            #   bulamıyor, Türkçe karakterler bozuk görünüyordu.
            # * stdin=DEVNULL: girdi bekleyen komutlar ("pause", "python")
            #   backend'in hiç yazılmayan stdin'inde sonsuza kadar asılıyordu.
            # * Çıktı satır satır akıtılır (uzun "pip yükle" donmuş görünmez)
            #   ve süreç Durdur ile öldürülebilir.
            kod_sayfasi = self._kabuk_kod_sayfasi()
            proc = subprocess.Popen(
                komut,
                shell=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=self._subprocess_env(),
                **self._subprocess_flags()
            )
            self._kabuk_surecleri.add(proc)
            try:
                for ham in iter(proc.stdout.readline, b""):
                    # Python alt süreçleri UTF-8, cmd yerleşikleri OEM kod
                    # sayfasıyla yazar; satır bazında doğru olanı seç.
                    try:
                        metin = ham.decode("utf-8")
                    except UnicodeDecodeError:
                        metin = ham.decode(kod_sayfasi, errors="replace")
                    self._guvenli_callback(on_output, metin.replace("\r\n", "\n"))
                proc.wait()
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                self._kabuk_surecleri.discard(proc)

            self._guvenli_callback(on_output, "\n")
        except Exception as e:
            self._guvenli_callback(on_output, f"[Hata: {e}]\n")

    # ------------------------------------------------------------------
    # İmza / hakkında
    # ------------------------------------------------------------------
    def imza_dogrula(self):
        try:
            basarili, mesaj, detay = DijitalImza.dogrula()

            return {
                "ok": True,
                "basarili": basarili,
                "mesaj": mesaj,
                "detay": detay,
            }
        except Exception as e:
            return {
                "ok": False,
                "hata": str(e),
            }

    def dosya_hash(self):
        try:
            return {
                "ok": True,
                "hash": DijitalImza.hash_hesapla(),
            }
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ------------------------------------------------------------------
    # Hata ayıklayıcı (debugger)
    # ------------------------------------------------------------------
    @staticmethod
    def _satir_listesi(satirlar):
        sonuc = set()
        for s_ in satirlar or []:
            try:
                n = int(s_)
            except (TypeError, ValueError):
                continue
            if n > 0:
                sonuc.add(n)
        return sonuc

    def breakpoint_toggle(self, satir):
        try:
            satir = int(satir)
        except (TypeError, ValueError):
            return {"ok": False, "hata": "Satır numarası geçersiz."}

        if satir <= 0:
            return {"ok": False, "hata": "Satır numarası 1'den küçük olamaz."}

        if satir in self.breakpoints:
            self.breakpoints.remove(satir)
            aktif = False
        else:
            self.breakpoints.add(satir)
            aktif = True

        self._debug_bp_gonder()

        return {
            "ok": True,
            "satir": satir,
            "aktif": aktif,
            "breakpoints": sorted(self.breakpoints),
        }

    def breakpoint_list(self):
        return {
            "ok": True,
            "breakpoints": sorted(self.breakpoints),
        }

    def debug_breakpoint_ayarla(self, satirlar):
        """Arayüzdeki (hata ayıklanan dosyanın) breakpoint listesini topluca
        ayarlar; çalışan bir oturum varsa ona da hemen iletilir."""
        self.breakpoints = self._satir_listesi(satirlar)
        self._debug_bp_gonder()
        return {"ok": True, "breakpoints": sorted(self.breakpoints)}

    def _debug_bp_gonder(self):
        oturum = self._debug_oturumu
        if oturum is None or oturum.bitti:
            return
        try:
            oturum.komut("bp", satirlar=sorted(self.breakpoints))
        except (DebugHatasi, OSError):
            pass

    def _debug_aktif(self, oturum=None):
        if oturum is None:
            oturum = self._debug_oturumu
        return (oturum is not None and not oturum.bitti
                and oturum.process.poll() is None)

    def debug_durum(self):
        oturum = self._debug_oturumu
        aktif = self._debug_aktif(oturum)
        return {
            "ok": True,
            "calistiriliyor": aktif,
            "durdu": bool(aktif and oturum.durdu),
            "mevcut_satir": oturum.mevcut_satir if aktif and oturum.durdu else 0,
            "breakpoints": sorted(self.breakpoints),
        }

    def debug_baslat(self, kod=None, breakpointler=None, ilk_satirda_dur=False,
                     on_output=None, on_exit=None, on_olay=None):
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Hata ayıklanacak kod yok."}

        if breakpointler is not None:
            self.breakpoints = self._satir_listesi(breakpointler)

        # Hiç breakpoint yoksa program bir çırpıda bitip gideceğinden ilk
        # satırda durulur (adım adım ilerlemek için).
        if not self.breakpoints:
            ilk_satirda_dur = True

        sonuc = dogrula(kod)

        if not sonuc.basarili:
            return {
                "ok": False,
                "hatalar": [
                    {
                        "satir": getattr(h, "satir", None),
                        "sutun": getattr(h, "sutun", None),
                        "mesaj": str(h),
                    }
                    for h in sonuc.hatalar
                ],
                "hata": "; ".join(str(h) for h in sonuc.hatalar[:3])
                        or "Sözdizimi hatası.",
            }

        try:
            python_kodu = turkce_kodu_donustur(kod)
        except Exception as e:
            return {"ok": False, "hata": f"Çeviri hatası: {e}"}

        python_exe, hata = self._python_exe_bul()

        if not python_exe:
            return {"ok": False, "hata": hata}

        with self._calistirma_kilit:
            # Önceki oturum / çalışan program kapatılır; eski süreç artık
            # "güncel" sayılmaz (bitiş olayı yeni oturumun terminaline düşmez).
            self.debug_durdur()
            if self._calistirma_process is not None:
                self._calistirmayi_sonlandir()
                self._calistirma_process = None

            try:
                oturum = DebugOturumu(
                    python_exe,
                    python_kodu,
                    sorted(self.breakpoints),
                    ilk_satirda_dur,
                    env=self._subprocess_env(),
                    popen_ek=self._subprocess_flags(),
                    on_olay=on_olay,
                )
            except Exception as e:
                return {"ok": False, "hata": f"Debugger başlatılamadı: {e}"}

            self._debug_oturumu = oturum
            self._calistirma_process = oturum.process

        def _temizlik(cikis_kodu):
            # Her durumda çalışır: debug_bitti, oturum kimliğiyle gönderilir;
            # arayüz eski oturumun olayını kimlikten ayırt eder.
            oturum.temizle()
            if self._debug_oturumu is oturum:
                self._debug_oturumu = None
            self._guvenli_callback(on_olay, "debug_bitti", {
                "cikis_kodu": cikis_kodu, "oturum": oturum.kimlik})

        threading.Thread(
            target=self._terminal_oku,
            args=(oturum.process, on_output, on_exit, _temizlik),
            daemon=True,
            name="turkod-debug-cikti",
        ).start()

        return {
            "ok": True,
            "pid": oturum.process.pid,
            "oturum": oturum.kimlik,
            "calistiriliyor": True,
            "ilk_satirda_dur": bool(ilk_satirda_dur),
            "breakpoints": sorted(self.breakpoints),
        }

    def _debug_komut(self, komut, durmus_olmali=True):
        oturum = self._debug_oturumu

        if not self._debug_aktif(oturum):
            return {"ok": False, "hata": "Hata ayıklama oturumu çalışmıyor."}

        if durmus_olmali and not oturum.durdu:
            return {"ok": False, "hata": "Program şu an duraklatılmış değil."}

        try:
            oturum.komut(komut)
        except (DebugHatasi, OSError) as e:
            return {"ok": False, "hata": str(e)}

        return {"ok": True, "calistiriliyor": True}

    def debug_devam(self):
        return self._debug_komut("devam")

    def debug_adim(self):
        """Adım at (üzerinden): fonksiyonların içine girmeden sonraki satır."""
        return self._debug_komut("adim")

    def debug_icine(self):
        return self._debug_komut("icine")

    def debug_disina(self):
        return self._debug_komut("disina")

    def debug_duraklat(self):
        return self._debug_komut("duraklat", durmus_olmali=False)

    def debug_durdur(self):
        oturum = self._debug_oturumu

        if oturum is None:
            return {
                "ok": True,
                "calistiriliyor": False,
                "mevcut_satir": 0,
                "breakpoints": sorted(self.breakpoints),
            }

        self._debug_oturumu = None
        oturum.kapat()
        proc = oturum.process

        if proc.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    proc.kill()
            except Exception:
                pass

        return {
            "ok": True,
            "calistiriliyor": False,
            "mevcut_satir": 0,
            "breakpoints": sorted(self.breakpoints),
        }
