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
    from .settings import AyarlarYoneticisi
    from .signing import DijitalImza
    from .tokenizer import TokenTuru, TokenizerHatasi, tokenize
    from .ai import (AI_MODELLERI, anthropic, genai, Groq, openai,
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
    from settings import AyarlarYoneticisi
    from signing import DijitalImza
    from tokenizer import TokenTuru, TokenizerHatasi, tokenize
    from ai import (AI_MODELLERI, anthropic, genai, Groq, openai,
                    groq_modelleri_guncelle, openai_modelleri_guncelle)


class AIHatasi(Exception):
    """AI API çağrılarında kullanıcıya gösterilebilir hata."""


GUVENLI_OLMAYAN_KALIPLAR = [
    r'\bopen\s*\(',
    r'\bos\.(remove|unlink|rmdir|system)\b',
    r'\bshutil\.(rmtree|move)\b',
    r'\bsubprocess\b',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\b__import__\b',
    r'\brequests\.(get|post|put|delete)\b',
    r'\burllib\b',
    r'\bsocket\b',
]


try:
    from .pip_tr import pip_komutu_cevir
except ImportError:
    from pip_tr import pip_komutu_cevir


class IDECore:
    """Tkinter içermeyen TürKod IDE mantık katmanı."""

    def __init__(self):
        self.ayarlar = AyarlarYoneticisi()
        self.proje_dizini = self.ayarlar.get("son_proje_dizini")

        self.ai_mesajlar = []
        self.ai_mesaj_gecmisi = []

        self._tanim_cache_hash = ""
        self._tanim_cache_deger = set()

        self._yerel_duzelt_sozluk_cache = None
        self._yerel_duzelt_sozluk_map = None
        self._yerel_duzelt_sozluk_kucuk_listesi = None
        self._sozluk_duz_cache = None
        self._py_ciplak_cache = None

        self._calistirma_process = None

        self.breakpoints = set()
        self.debug_calistiriliyor = False
        self.debug_mevcut_satir = 0

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
        os.makedirs(yol, exist_ok=True)
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
        if not dizin or not os.path.exists(dizin):
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
            with open(yol, "r", encoding="utf-8") as f:
                icerik = f.read()

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
        tum_sayi = len(tum_girdiler)

        if tum_sayi > MAX_OGE:
            tum_girdiler = tum_girdiler[:MAX_OGE]
            fazla = tum_sayi - MAX_OGE

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

        if h == self._tanim_cache_hash:
            return self._tanim_cache_deger

        try:
            sonuc = sorted(kullanici_tanimlari(kod))
        except Exception:
            sonuc = []

        self._tanim_cache_hash = h
        self._tanim_cache_deger = sonuc

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
        fonts = set()
        kaynak = None

        try:
            import tkinter as tk
            import tkinter.font as tkfont

            root = tk.Tk()
            try:
                root.withdraw()
                fonts.update(f for f in tkfont.families() if f and not f.startswith("@"))
                kaynak = "tkinter"
            finally:
                root.destroy()
        except Exception:
            fonts = set()

        if not fonts:
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

        return {
            "ok": True,
            "fontlar": sorted(fonts, key=lambda s: s.lower()),
            "kaynak": kaynak,
        }

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
            r"^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=",
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
            match = re.search(
                r"#.*?(TODO|FIXME|HACK|XXX|BUG)[\s:]*(.*)",
                satir,
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
        satirlar = kod.splitlines()
        bolgeler = []
        yigin = []

        def kapat(bas_satir, bit_satir):
            if bit_satir <= bas_satir:
                return

            govde_var = any(s.strip() for s in satirlar[bas_satir:bit_satir])

            if govde_var:
                bolgeler.append((bas_satir, bit_satir))

        for i, satir in enumerate(satirlar, 1):
            bosluksuz = satir.lstrip()

            if not bosluksuz or bosluksuz.startswith("#"):
                continue

            indent = len(satir) - len(bosluksuz)

            while yigin and indent <= yigin[-1][1]:
                bas_satir, _ = yigin.pop()
                kapat(bas_satir, i - 1)

            temiz = self._yorumdan_arindir(bosluksuz)

            if temiz.endswith(":"):
                yigin.append((i, indent))

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

            return {
                "ok": True,
                "basarili": sonuc.basarili,
                "hatalar": hatalar,
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

        if python_kodu:
            satirlar = python_kodu.split("\n")

            if len(satirlar) > 25:
                python_kodu = "\n".join(satirlar[-20:])
                python_kodu = (
                    "[Kod son 20 satır]:\n"
                    "```python\n"
                    f"{python_kodu}\n"
                    "```"
                )
            else:
                python_kodu = (
                    "[Kod:\n"
                    "```python\n"
                    f"{python_kodu}\n"
                    "```]"
                )

        if python_kodu:
            tam_mesaj = f"{mesaj}\n{python_kodu}"
        else:
            tam_mesaj = mesaj

        if len(tam_mesaj) > 2000:
            tam_mesaj = tam_mesaj[:2000] + "\n[...kısaltıldı]"

        return tam_mesaj

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

        for match in re.finditer(r"```(\w*)\s*\n?(.*?)```", mesaj, re.DOTALL):
            if match.start() > son_pos:
                metin = mesaj[son_pos:match.start()].strip()

                if metin:
                    parcalar.append({
                        "tip": "metin",
                        "icerik": metin,
                        "dil": "",
                    })

            dil = match.group(1).strip()
            kod = match.group(2).strip()

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

                if response.content:
                    cevap = response.content[0].text
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

            if kucuk not in sozluk_map:
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

            if kucuk in sozluk_map or kucuk in tanimli_kucuk:
                return token

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

    def _sozdizimi_duzelt(self, kod, satir_no, hata_mesaji):
        duzeltme = self._iki_nokta_duzelt(kod, satir_no)

        if duzeltme:
            return duzeltme

        satirlar = kod.split("\n")

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

        if "indent" in hata_mesaji.lower():
            # Mevcut app.py'de bu bölüm boş bırakılmıştı.
            pass

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

    def _guvenli_mi(self, python_kodu):
        for desen in GUVENLI_OLMAYAN_KALIPLAR:
            if re.search(desen, python_kodu):
                return False, f"Güvenlik: '{desen}' kalıbı tespit edildi"

        return True, ""

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

    def duzelt_kod(self, kod, progress_callback=None):
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Düzeltilecek kod bulunamadı."}

        if not self.ayarlar.get("gelismis_duzeltme"):
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

        return self.gelismis_duzelt(kod, progress_callback)

    def gelismis_duzelt(self, kod, progress_callback=None):
        MAKS_DONGU = self._sayi_ayar("duzeltme_maks_dongu", 12)
        ZAMAN_ASIMI = self._sayi_ayar("duzeltme_zaman_asimi", 5)
        MESAJ_ARALIGI = self._sayi_ayar("duzeltme_mesaj_araligi", 100)

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

        python_exe, python_hata = self._python_exe_bul()

        if not python_exe:
            return {"ok": False, "hata": python_hata}

        _cevirme_cache = {}

        def _python_calisma():
            cache_key = _hash(duzeltilmis) + str(frozenset(beklenen_importlar))

            if cache_key in _cevirme_cache:
                return _cevirme_cache[cache_key]

            try:
                py = turkce_kodu_donustur(duzeltilmis)
            except Exception:
                return None, 0

            enjekte = [
                f"import {MODUL_CEVIRILERI.get(m, m)}"
                for m in sorted(beklenen_importlar)
            ]

            if enjekte:
                ayirac = "\n"
                sonuc = ayirac.join(enjekte) + ayirac + py, len(enjekte)
            else:
                sonuc = py, 0

            _cevirme_cache[cache_key] = sonuc

            return sonuc

        def _dongu_satiri_bul(kod_str):
            for i, satir in enumerate(kod_str.split("\n"), 1):
                temiz = satir.strip()

                if temiz.startswith("döngü") or temiz.startswith("için"):
                    return i

            return None

        for _ in range(MAKS_DONGU):
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
                satir = (e.lineno or 1) - offset
                duzeltme = self._sozdizimi_duzelt(duzeltilmis, satir, str(e.msg or ""))

                if duzeltme:
                    duzeltilmis, msg = duzeltme
                    degisiklikler.append(msg)
                    mesaj_ver(f"⚠️ Hata {satir}. satırında. Tip: SyntaxError\n{msg}")
                    continue

                py_satirlar = py.split("\n")
                py_goster = py_satirlar[satir - 1].strip() if 0 < satir <= len(py_satirlar) else "?"

                degisiklikler.append(
                    f"• Satır {satir}: sözdizimi hatası otomatik düzeltilemedi. "
                    f"Python tarafı: {py_goster}"
                )
                break

            temp_path = os.path.join(tempfile.gettempdir(), "turkod_hata_kontrol.py")

            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(py)

                sonuc = subprocess.run(
                    [python_exe, "-X", "utf8", temp_path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=ZAMAN_ASIMI,
                    env=self._subprocess_env(),
                    **self._subprocess_flags()
                )
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
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            if sonuc.returncode == 0:
                break

            stderr = sonuc.stderr
            m_satir = re.search(r"line (\d+)", stderr)
            satir = (int(m_satir.group(1)) - offset) if m_satir else 1

            if "NameError:" not in stderr:
                if "TypeError:" in stderr:
                    # Mevcut app.py'de bu bölüm boş bırakılmıştı.
                    pass

                if "AttributeError:" in stderr:
                    # Mevcut app.py'de bu bölüm boş bırakılmıştı.
                    pass

                if "IndexError:" in stderr:
                    degisiklikler.append(
                        f"• Satır {satir}: IndexError - liste/dizi sınırı aşıldı. "
                        f"İndeks değerini kontrol edin."
                    )
                    break

                if "ModuleNotFoundError:" in stderr:
                    m_mod = re.search(r"No module named '([^']+)'", stderr)
                    mod_ad = m_mod.group(1) if m_mod else "?"

                    degisiklikler.append(
                        f"• '{mod_ad}' modülü kurulu değil (pip yükle {mod_ad}). "
                        f"Kod dönüştürüldü ama çalıştırılamaz."
                    )
                    break

                tail = stderr.splitlines()[-1] if stderr.splitlines() else "Bilinmeyen hata"
                degisiklikler.append(f"• Satır {satir}: {tail} (otomatik düzeltme yok)")
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
        py, _ = _python_calisma()

        if py is not None:
            try:
                ast.parse(py)
            except SyntaxError as e2:
                dogrulama = f"⚠️ Kalan sözdizimi hatası: Satır {e2.lineno}"
            else:
                temp_path = os.path.join(tempfile.gettempdir(), "turkod_hata_kontrol.py")

                try:
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(py)

                    v = subprocess.run(
                        [python_exe, "-X", "utf8", temp_path],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=ZAMAN_ASIMI,
                        env=self._subprocess_env(),
                        **self._subprocess_flags()
                    )

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
                finally:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

        return {
            "ok": True,
            "degisiklik": bool(degisiklikler),
            "kod": duzeltilmis,
            "degisiklikler": degisiklikler,
            "son_mesaj": son_mesaj,
            "dogrulama": dogrulama,
            "diff": self._diff_olustur(kod, duzeltilmis),
        }

    # ------------------------------------------------------------------
    # Çalıştırma / terminal
    # ------------------------------------------------------------------
    def kodu_calistir(self, kod, on_output=None, on_exit=None):
        kod = kod or ""

        if not kod.strip():
            return {"ok": False, "hata": "Çalıştırılacak kod yok."}

        if self._calistirma_process is not None:
            self.kodu_durdur()

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

        temp_dir = tempfile.gettempdir()
        kod_path = os.path.join(temp_dir, "turkce_kod_calisma.py")
        runner_path = os.path.join(temp_dir, "runner.py")

        try:
            with open(kod_path, "w", encoding="utf-8") as f:
                f.write(python_kodu)

            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(RUNNER_KODU)
        except Exception as e:
            return {"ok": False, "hata": str(e)}

        python_exe, hata = self._python_exe_bul()

        if not python_exe:
            return {"ok": False, "hata": hata}

        self._guvenli_callback(on_output, "> python -u runner.py\n")

        try:
            self._calistirma_process = subprocess.Popen(
                [python_exe, "-X", "utf8", "-u", runner_path],
                cwd=temp_dir,
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
            return {"ok": False, "hata": str(e)}

        threading.Thread(
            target=self._terminal_oku,
            args=(self._calistirma_process, on_output, on_exit),
            daemon=True
        ).start()

        return {
            "ok": True,
            "pid": self._calistirma_process.pid,
        }

    def _terminal_oku(self, process, on_output=None, on_exit=None):
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        fd = process.stdout.fileno()

        try:
            while True:
                ham = os.read(fd, 4096)

                if not ham:
                    break

                metin = cozucu.decode(ham)

                if metin:
                    self._guvenli_callback(on_output, metin)

            kalan = cozucu.decode(b"", final=True)

            if kalan:
                self._guvenli_callback(on_output, kalan)

            kod = process.wait()

            self._guvenli_callback(on_output, f"\n[Process {kod} koduyla çıktı]\n")
            self._guvenli_callback(on_exit, kod)
        except Exception as e:
            self._guvenli_callback(on_output, f"[Terminal okuma hatası: {e}]\n")
            self._guvenli_callback(on_exit, -1)
        finally:
            self._calistirma_process = None

    def kodu_durdur(self):
        proc = getattr(self, "_calistirma_process", None)

        if proc is None or proc.poll() is not None:
            return {"ok": False, "hata": "Çalışan süreç yok."}

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc.terminate()
        except Exception as e:
            return {"ok": False, "hata": str(e)}

        return {"ok": True}

    def terminal_komut(self, komut, on_output=None):
        komut = (komut or "").strip()

        if not komut:
            return {"ok": False, "hata": "Komut boş."}

        proc = getattr(self, "_calistirma_process", None)

        if proc is not None and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write(komut + "\n")
                proc.stdin.flush()

                return {
                    "ok": True,
                    "kip": "stdin",
                }
            except Exception as e:
                return {"ok": False, "hata": str(e)}

        self._guvenli_callback(on_output, f"> {komut}\n")

        threading.Thread(
            target=self._terminal_komut_calistir,
            args=(komut, on_output),
            daemon=True
        ).start()

        return {
            "ok": True,
            "kip": "shell",
        }

    def _terminal_komut_calistir(self, komut, on_output=None):
        try:
            python_exe, _ = self._python_exe_bul()
            yeni_komut = pip_komutu_cevir(komut, python_exe, self._kullanici_paket_yolu())
            if yeni_komut:
                komut = yeni_komut
            cwd = (
                self.proje_dizini
                if self.proje_dizini and os.path.exists(self.proje_dizini)
                else os.getcwd()
            )

            sonuc = subprocess.run(
                komut,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._subprocess_flags()
            )

            self._guvenli_callback(on_output, (sonuc.stdout or "") + "\n")
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
    # Debugger state
    # ------------------------------------------------------------------
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

    def debug_baslat(self, kod=None):
        if kod:
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

        if not self.breakpoints:
            return {
                "ok": False,
                "hata": "Önce breakpoint ekleyin.",
            }

        self.debug_calistiriliyor = True
        self.debug_mevcut_satir = min(self.breakpoints)

        return {
            "ok": True,
            "calistiriliyor": True,
            "mevcut_satir": self.debug_mevcut_satir,
            "breakpoints": sorted(self.breakpoints),
        }

    def debug_adim(self):
        if not self.debug_calistiriliyor:
            return {
                "ok": False,
                "hata": "Debug çalışmıyor.",
            }

        sonraki = sorted(
            b for b in self.breakpoints
            if b > self.debug_mevcut_satir
        )

        if sonraki:
            self.debug_mevcut_satir = sonraki[0]

            return {
                "ok": True,
                "calistiriliyor": True,
                "mevcut_satir": self.debug_mevcut_satir,
                "breakpoints": sorted(self.breakpoints),
            }

        return self.debug_durdur()

    def debug_devam(self):
        if not self.debug_calistiriliyor:
            return self.debug_baslat()

        return self.debug_adim()

    def debug_durdur(self):
        self.debug_calistiriliyor = False
        self.debug_mevcut_satir = 0

        return {
            "ok": True,
            "calistiriliyor": False,
            "mevcut_satir": 0,
            "breakpoints": sorted(self.breakpoints),
        }