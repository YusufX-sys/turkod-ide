"""TürKod Akıllı Düzeltme Motoru.

Dışarıdan hiçbir yapay zekâ servisine bağlanmaz; tamamen yerel çalışır. Ama
bir yapay zekâ asistanı gibi davranır: kodu okur, sorunları teşhis eder,
her sorun için birden fazla olası düzeltme üretir, bunları kodu gerçekten
derleyip / çalıştırarak sınar, en iyi sonucu seçer ve yaptığı her şeyi
gerekçesi ve güven puanıyla birlikte açıklar.

Aşamalar
--------
1. Okuma        : kod istatistikleri, yapı (fonksiyon / sınıf / değişken).
2. Ön temizlik  : karışık sekme/boşluk, "değilse eğer" gibi ayrık yazılmış
                  anahtar kelimeler, sözlüğe dayalı yazım hataları.
3. Sözdizimi    : hata satırı için aday düzeltmeler üretilir (iki nokta,
                  girinti, parantez, tırnak, virgül, operatör, eksik
                  parantezli çağrı, akıllı tırnak ...). Her aday derlenerek
                  puanlanır; hatayı ortadan kaldıran ya da en ileri taşıyan
                  aday seçilir (küçük bir arama).
4. Anlam        : girdi_al() ile okunan metnin sayı gibi kullanılması gibi
                  çalışma hatası vermeyen ama yanlış sonuç üreten durumlar.
5. Çalışma      : kod güvenli kipte (girdi beklemeden, uyumadan) çalıştırılır;
                  hata türüne göre adaylar üretilir (tanımsız ad, eksik
                  içe aktarma, metin + sayı birleştirme, yanlış metot adı,
                  eksik 'kendisi', 'küresel' eksikliği ...). Her aday yeniden
                  çalıştırılarak doğrulanır; işe yaramayan geri alınır.
6. İnceleme     : otomatik düzeltilmeyen ama dikkat edilmesi gereken
                  durumlar (sonsuz döngü riski, ulaşılamayan kod, yanlış
                  argüman sayısı, kullanılmayan değişken ...).
7. Rapor        : düzeltmeler, öneriler, kod sağlık puanı, son doğrulama.

Sonuç sözlüğü eski ``gelismis_duzelt`` biçimiyle uyumludur (kod, diff,
degisiklikler, son_mesaj, dogrulama) ve ek olarak ``rapor`` alanı içerir.
"""
import ast
import builtins
import difflib
import hashlib
import re
import subprocess
import time

try:
    from .converter import MODUL_CEVIRILERI, URSINA_NESNELERI, turkce_kodu_donustur
    from .dictionary import SOZLUK, TERS_SOZLUK, _block_words, _keyword_words, kullanici_tanimlari
except ImportError:
    from converter import MODUL_CEVIRILERI, URSINA_NESNELERI, turkce_kodu_donustur
    from dictionary import SOZLUK, TERS_SOZLUK, _block_words, _keyword_words, kullanici_tanimlari


ID = r"[^\W\d]\w*"
_ID_RE = re.compile(ID)
_METIN_RE = re.compile(
    r'[rRbBfFuU]{0,2}"""[\s\S]*?"""|[rRbBfFuU]{0,2}\'\'\'[\s\S]*?\'\'\''
    r'|[rRbBfFuU]{0,2}"(?:[^"\\\n]|\\.)*"|[rRbBfFuU]{0,2}\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*')
_ACAN = {"(": ")", "[": "]", "{": "}"}
_KAPAYAN = {v: k for k, v in _ACAN.items()}

# Kod çalıştırmada girdi beklenmesini ve uyumayı engelleyen tek satırlık ön ek.
_KONTROL_ON_EKI = (
    "import builtins as _tk_b, time as _tk_t; "
    "_tk_b.input = lambda *a, **k: '1'; "
    "_tk_t.sleep = lambda *a, **k: None"
)


def _tr(py_ad, varsayilan):
    """Python adının TürKod karşılığı (ör. 'int' -> 'tamsayı')."""
    deger = TERS_SOZLUK.get(py_ad)
    return deger if isinstance(deger, str) and deger else varsayilan


def _normalize(metin):
    return metin.translate(str.maketrans({
        "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    })).lower()


def maskele(metin):
    """Metin içeriklerini \\x01 ile, yorumları boşlukla maskeler (uzunluk ve
    satır yapısı korunur). Böylece kalıp aramaları metinlerin / yorumların
    içine takılmaz; tırnaklar yerinde kaldığı için metin değerleri yine de
    tanınabilir."""
    def degistir(m):
        s = m.group(0)
        if s.startswith("#"):
            return " " * len(s)
        bas_m = re.match(r"[rRbBfFuU]{0,2}(\"\"\"|'''|\"|')", s)
        bas = bas_m.end()
        son = len(s) - len(bas_m.group(1))
        ic = "".join("\n" if ch == "\n" else "\x01" for ch in s[bas:son])
        return s[:bas] + ic + s[son:]
    return _METIN_RE.sub(degistir, metin)


def _girinti(satir):
    return len(satir) - len(satir.lstrip(" \t"))


def _eslesen_kapanis(maskeli, ac_konum):
    """maskeli[ac_konum] açılış parantezinin kapanış konumu (yoksa -1)."""
    derinlik = 0
    for i in range(ac_konum, len(maskeli)):
        ch = maskeli[i]
        if ch in _ACAN:
            derinlik += 1
        elif ch in _KAPAYAN:
            derinlik -= 1
            if derinlik == 0:
                return i
    return -1


class Bulgu:
    """Bir düzeltme ya da öneri."""

    __slots__ = ("satir", "baslik", "aciklama", "guven", "kategori", "seviye", "oneri")

    def __init__(self, satir, baslik, aciklama="", guven=0.9, kategori="genel",
                 seviye="bilgi", oneri=""):
        self.satir = satir
        self.baslik = baslik
        self.aciklama = aciklama
        self.guven = guven
        self.kategori = kategori
        self.seviye = seviye
        self.oneri = oneri

    def sozluk(self):
        return {
            "satir": self.satir,
            "baslik": self.baslik,
            "aciklama": self.aciklama,
            "guven": int(round(self.guven * 100)),
            "kategori": self.kategori,
            "seviye": self.seviye,
            "oneri": self.oneri,
        }

    def metin(self):
        onek = f"Satır {self.satir}: " if self.satir else ""
        return f"• {onek}{self.baslik}"


class _PencereGizleyici:
    """Deneme sürecinin üst düzey pencerelerini DIŞARIDAN, açıldıkları anda
    görünmez yapar: tamamen saydam, tıklamaları geçiren, görev çubuğunda
    görünmeyen. Hedefin mesaj döngüsünü beklemez (Ursina gibi açılışta Python
    kilidini tutan motorlarda süreç içi gizleme saniyelerce gecikiyordu)."""

    def __init__(self, pid):
        self.pid = pid
        self._dur = False
        self._islenen = set()
        self._is = None
        try:
            import ctypes
            from ctypes import wintypes
            import threading
            self._c, self._w = ctypes, wintypes
            u = self._u = ctypes.windll.user32
            u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            u.GetAncestor.restype = wintypes.HWND
            u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                     ctypes.c_ubyte, wintypes.DWORD]
            self._sayac_turu = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            self._is = threading.Thread(target=self._calis, daemon=True)
            self._is.start()
        except Exception:  # noqa: BLE001 - Windows dışı: gizleme yok
            self._is = None

    def _gizle(self, h, _):
        try:
            p = self._w.DWORD()
            self._u.GetWindowThreadProcessId(h, self._c.byref(p))
            if p.value != self.pid or self._u.GetAncestor(h, 2) != h:
                return True
            stil = self._u.GetWindowLongW(h, -20)  # GWL_EXSTYLE
            # LAYERED | TRANSPARENT (tıklama geçer) | TOOLWINDOW (görev çubuğu) | NOACTIVATE
            istenen = stil | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000
            if h not in self._islenen or stil != istenen:
                self._u.SetWindowLongW(h, -20, self._c.c_long(istenen).value)
                self._u.SetLayeredWindowAttributes(h, 0, 0, 0x2)  # LWA_ALPHA = 0
                self._islenen.add(h)
        except Exception:  # noqa: BLE001
            pass
        return True

    def _calis(self):
        import time as _zaman
        sayac = self._sayac_turu(self._gizle)
        while not self._dur:
            self._u.EnumWindows(sayac, 0)
            _zaman.sleep(0.005)

    def durdur(self):
        self._dur = True
        if self._is is not None:
            self._is.join(timeout=1)


class AkilliDuzeltici:
    """IDECore'un yardımcılarını kullanan akıllı düzeltme motoru."""

    MAKS_SOZDIZIMI = 250
    MAKS_ADAY_CALISTIRMA = 8

    # Ayrık yazıldığında (ör. "değilse eğer") birleştirilen kelimeler. Bu
    # biçimler hiçbir zaman geçerli kod olmadığından birleştirme güvenlidir.
    _EK_BIRLESIK = (
        "girdi_al", "sona_ekle", "büyük_harf", "küçük_harf", "nesne_mi",
        "isimsiz", "başlat_özel",
    )

    _CAGRILABILIR_KOMUTLAR = ("yazdır", "yazdir")

    def __init__(self, core, progress_callback=None, calistir=True):
        self.core = core
        self.progress_callback = progress_callback
        self.duzeltmeler = []
        self.uyarilar = []
        self.dusunceler = []
        self._uyari_anahtarlari = set()
        self._calisma_onbellek = {}
        self.calistirma_sayisi = 0
        self.zaman_asimi = max(1, core._sayi_ayar("duzeltme_zaman_asimi", 5))
        self.maks_calisma = max(1, core._sayi_ayar("duzeltme_maks_dongu", 12))
        aralik = core._sayi_ayar("duzeltme_mesaj_araligi", 100)
        self._mesaj_bekleme = max(0, min(aralik, 250)) / 1000.0
        self.python_exe, self.python_hata = core._python_exe_bul()
        if not calistir:
            # Riskli kod (dosya silme, ağ, ...) ve kullanıcı izin vermedi:
            # tüm çalışma testleri atlanır, yalnızca statik düzeltme yapılır.
            self.python_exe = None
            self.python_hata = "Güvenlik nedeniyle kod çalıştırılmadı."

    # ------------------------------------------------------------------
    # İletişim
    # ------------------------------------------------------------------
    def dusun(self, metin, bekle=True):
        """Kullanıcıya 'düşünce akışı' iletir."""
        self.dusunceler.append(metin)
        if self.progress_callback:
            if bekle and self._mesaj_bekleme:
                time.sleep(self._mesaj_bekleme)
            self.core._guvenli_callback(self.progress_callback, metin)

    def _duzeltme_ekle(self, bulgu):
        self.duzeltmeler.append(bulgu)
        guven = int(round(bulgu.guven * 100))
        self.dusun(f"🔧 {bulgu.metin()[2:]}  (güven %{guven})")

    def _uyari_ekle(self, satir, mesaj, oneri="", seviye="uyari", kategori="inceleme"):
        anahtar = (satir, mesaj)
        if anahtar in self._uyari_anahtarlari:
            return
        self._uyari_anahtarlari.add(anahtar)
        self.uyarilar.append(Bulgu(satir, mesaj, oneri=oneri, seviye=seviye,
                                   kategori=kategori, guven=1.0))

    # ------------------------------------------------------------------
    # Çeviri / derleme / çalıştırma
    # ------------------------------------------------------------------
    @staticmethod
    def _hash(kod):
        return hashlib.sha256(kod.encode("utf-8")).hexdigest()

    @staticmethod
    def _cevir(kod):
        try:
            return turkce_kodu_donustur(kod)
        except Exception:
            return None

    def _sozdizimi_durumu(self, kod):
        """None: sorunsuz; değilse {'satir', 'mesaj', 'tip'}."""
        py = self._cevir(kod)
        if py is None:
            return {"satir": 1, "mesaj": "kod Python'a çevrilemedi", "tip": "CeviriHatasi"}
        try:
            # compile(): ast.parse'ın bildirmediği "'return' outside function",
            # "'break' outside loop" gibi hataları da yakalar.
            compile(py, "<turkod>", "exec", dont_inherit=True)
        except SyntaxError as e:
            return {"satir": max(1, e.lineno or 1), "mesaj": str(e.msg or ""),
                    "tip": type(e).__name__}
        except (ValueError, RecursionError) as e:
            return {"satir": 1, "mesaj": str(e), "tip": type(e).__name__}
        return None

    @staticmethod
    def _degisen_satirlar(eski, yeni):
        """yeni koddaki, eskisine göre değişmiş / eklenmiş satır numaraları."""
        a, b = eski.split("\n"), yeni.split("\n")
        degisen = set()
        for etiket, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if etiket in ("replace", "insert"):
                degisen.update(range(j1 + 1, j2 + 1))
            elif etiket == "delete":
                degisen.add(j1 + 1)
        return degisen

    def _degerlendir(self, eski_kod, yeni_kod, eski_durum=False):
        """Bir değişikliğin sözdizimi açısından değerini ölçer.

        Python bir dosyadaki hataların yalnızca ilkini (ve belirteç hatalarını
        diğerlerinden önce) bildirdiği için "hata satırı ilerledi mi" ölçütü
        yanıltıcıdır: bir hatayı düzeltmek daha yukarıdaki başka bir hatayı
        görünür kılabilir. Ölçüt: eski hata ortadan kalktı mı ve değişikliğin
        DOKUNDUĞU satırlarda yeni bir hata doğdu mu?

        Döner: None (reddet) ya da büyük olanı daha iyi bir puan.
        """
        if eski_durum is False:
            eski_durum = self._sozdizimi_durumu(eski_kod)
        yeni_durum = self._sozdizimi_durumu(yeni_kod)
        if yeni_durum is None:
            return (3, 0)
        if yeni_durum["tip"] == "CeviriHatasi":
            return None
        if eski_durum is None:
            return None  # derlenen kodu bozdu
        if eski_durum["tip"] == "CeviriHatasi":
            return (2, 0)
        degisen = self._degisen_satirlar(eski_kod, yeni_kod)
        kayma = yeni_kod.count("\n") - eski_kod.count("\n")
        ayni_hata = (yeni_durum["mesaj"] == eski_durum["mesaj"] and
                     yeni_durum["satir"] in (eski_durum["satir"], eski_durum["satir"] + kayma))
        if ayni_hata:
            return None
        if yeni_durum["satir"] in degisen:
            # Düzeltilen satırda hâlâ hata var: yalnızca aynı satırda farklı
            # bir hataya geçildiyse (adım adım ilerleme) zayıf bir ilerlemedir.
            if yeni_durum["satir"] == eski_durum["satir"]:
                return (1, 0)
            return None
        return (2, 0)

    def _kabul_edilebilir(self, eski_kod, yeni_kod):
        """Ön temizlik dönüşümleri için: kodu kötüleştirmiyor mu?"""
        eski_durum = self._sozdizimi_durumu(eski_kod)
        if eski_durum is None:
            return self._sozdizimi_durumu(yeni_kod) is None
        yeni_durum = self._sozdizimi_durumu(yeni_kod)
        if yeni_durum is None:
            return True
        if yeni_durum["tip"] == "CeviriHatasi" and eski_durum["tip"] != "CeviriHatasi":
            return False
        return yeni_durum["satir"] not in self._degisen_satirlar(eski_kod, yeni_kod) \
            or (yeni_durum["satir"] == eski_durum["satir"])

    def _calistir(self, kod):
        """Kodu güvenli kipte çalıştırır; sonucu önbelleğe alır.

        durum: ok | hata | zaman_asimi | sozdizimi | ceviri | atlandi
        """
        anahtar = self._hash(kod)
        if anahtar in self._calisma_onbellek:
            return self._calisma_onbellek[anahtar]

        py = self._cevir(kod)
        if py is None:
            sonuc = {"durum": "ceviri"}
        else:
            try:
                agac = ast.parse(py)
            except SyntaxError as e:
                sonuc = {"durum": "sozdizimi", "satir": e.lineno or 1, "mesaj": str(e.msg)}
            else:
                if self._arayuz_programi_mi(agac):
                    if self._ice_aktarilan_moduller(agac) & self._ARAYUZ_CALISTIRILMAZ:
                        # Gerçek fare/klavyeyi yöneten programlar denenmez.
                        sonuc = {"durum": "atlandi", "arayuz": True, "denetim": True}
                    else:
                        # Pencere açan programlar görünmez kipte, belirli bir süre
                        # çalıştırılır; bu sürede hata vermemek başarı sayılır.
                        sonuc = self._python_calistir(py, arayuz=True)
                        sonuc["arayuz"] = True
                else:
                    sonuc = self._python_calistir(py)
        self._calisma_onbellek[anahtar] = sonuc
        return sonuc

    _ARAYUZ_MODULLERI = {
        "turtle", "tkinter", "pygame", "ursina", "kivy", "PyQt5", "PyQt6",
        "PySide2", "PySide6", "wx", "arcade", "pyglet", "customtkinter",
        "matplotlib", "cv2", "pyautogui",
    }
    # Gerçek fare/klavyeyi denetleyen kütüphaneler: deneme çalıştırması yapılmaz.
    _ARAYUZ_CALISTIRILMAZ = {"pyautogui"}
    # Pencereli program bu kadar saniye hatasız çalışırsa başarılı sayılır
    # (oyun döngüleri kendiliğinden bitmez). Ursina gibi motorların açılışı
    # birkaç saniye sürdüğünden kısa tutulmaz.
    ARAYUZ_SURESI = 10

    # Pencereleri görünmez açan ön ek. Satır numaraları kaymasın diye tek satırda
    # exec ile çalışır (hata satırı hesabındaki 1 satırlık kayma değişmez).
    _ARAYUZ_ON_EKI_GOVDE = (
        "import os as _tk_os\n"
        "_tk_os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')\n"
        "_tk_os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')\n"
        "_tk_os.environ.setdefault('MPLBACKEND', 'Agg')\n"
        "_tk_os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "try:\n"
        "    from panda3d.core import loadPrcFileData as _tk_prc\n"
        "    _tk_prc('', 'audio-library-name null')\n"
        "except Exception:\n"
        "    pass\n"
        # Diğer tüm motorlar (Ursina/Panda3D, pyglet, arcade, kivy...): pencere
        # NORMAL açılır (ekran dışı kip pencere ayarlarını bozar ve doğru programı
        # hatalı gösterirdi) ama bu sürecin üst düzey pencereleri göründükleri
        # anda gizlenir (olay kancası + yedek tarama).
        "try:\n"
        "    import ctypes as _tk_c, threading as _tk_th, time as _tk_zaman\n"
        "    from ctypes import wintypes as _tk_w\n"
        "    _tk_u = _tk_c.windll.user32\n"
        "    _tk_u.ShowWindow.argtypes = [_tk_w.HWND, _tk_c.c_int]\n"
        "    _tk_u.IsWindowVisible.argtypes = [_tk_w.HWND]\n"
        "    _tk_u.GetWindowThreadProcessId.argtypes = [_tk_w.HWND, _tk_c.POINTER(_tk_w.DWORD)]\n"
        "    _tk_u.GetAncestor.argtypes = [_tk_w.HWND, _tk_c.c_uint]\n"
        "    _tk_u.GetAncestor.restype = _tk_w.HWND\n"
        "    _tk_u.SetWinEventHook.restype = _tk_w.HANDLE\n"
        "    _tk_pid = _tk_os.getpid()\n"
        "    def _tk_gizle_hwnd(h):\n"
        "        p = _tk_w.DWORD()\n"
        "        _tk_u.GetWindowThreadProcessId(h, _tk_c.byref(p))\n"
        "        if p.value == _tk_pid and _tk_u.IsWindowVisible(h) and _tk_u.GetAncestor(h, 2) == h:\n"
        "            _tk_u.ShowWindow(h, 0)\n"
        "    _TK_OLAY = _tk_c.WINFUNCTYPE(None, _tk_w.HANDLE, _tk_w.DWORD, _tk_w.HWND, _tk_w.LONG,\n"
        "                                 _tk_w.LONG, _tk_w.DWORD, _tk_w.DWORD)\n"
        "    def _tk_olay(kanca, olay, h, nesne, cocuk, is_, zaman_):\n"
        "        if h and nesne == 0:\n"
        "            _tk_gizle_hwnd(h)\n"
        "    _TK_SAYAC = _tk_c.WINFUNCTYPE(_tk_c.c_bool, _tk_w.HWND, _tk_w.LPARAM)\n"
        "    def _tk_say(h, _):\n"
        "        _tk_gizle_hwnd(h)\n"
        "        return True\n"
        "    def _tk_kanca():\n"
        "        geri = _TK_OLAY(_tk_olay)\n"
        "        _tk_u.SetWinEventHook(0x8002, 0x8002, None, geri, _tk_pid, 0, 0)\n"
        "        msg = _tk_w.MSG()\n"
        "        while _tk_u.GetMessageW(_tk_c.byref(msg), None, 0, 0) > 0:\n"
        "            _tk_u.TranslateMessage(_tk_c.byref(msg))\n"
        "            _tk_u.DispatchMessageW(_tk_c.byref(msg))\n"
        "    def _tk_tara():\n"
        "        say = _TK_SAYAC(_tk_say)\n"
        "        while True:\n"
        "            _tk_u.EnumWindows(say, 0)\n"
        "            _tk_zaman.sleep(0.05)\n"
        "    _tk_th.Thread(target=_tk_kanca, daemon=True).start()\n"
        "    _tk_th.Thread(target=_tk_tara, daemon=True).start()\n"
        "except Exception:\n"
        "    pass\n"
        "try:\n"
        "    import tkinter as _tk_tk, tkinter.messagebox as _tk_mb\n"
        "    def _tk_gizle(sinif):\n"
        "        _eski = sinif.__init__\n"
        "        def _yeni(self, *a, **k):\n"
        "            _eski(self, *a, **k)\n"
        "            try:\n"
        "                self.withdraw()\n"
        "            except Exception:\n"
        "                pass\n"
        "        sinif.__init__ = _yeni\n"
        "    _tk_gizle(_tk_tk.Tk)\n"
        "    _tk_gizle(_tk_tk.Toplevel)\n"
        "    _tk_tk.Wm.deiconify = _tk_tk.Wm.wm_deiconify = lambda self: None\n"
        "    for _a in ('showinfo', 'showwarning', 'showerror'):\n"
        "        setattr(_tk_mb, _a, lambda *a, **k: 'ok')\n"
        "    for _a in ('askyesno', 'askokcancel', 'askretrycancel', 'askyesnocancel', 'askquestion'):\n"
        "        setattr(_tk_mb, _a, lambda *a, **k: True)\n"
        "except Exception:\n"
        "    pass\n"
    )

    @classmethod
    def _arayuz_programi_mi(cls, agac):
        for d in ast.walk(agac):
            if isinstance(d, ast.Import):
                adlar = [a.name for a in d.names]
            elif isinstance(d, ast.ImportFrom) and d.module:
                adlar = [d.module]
            else:
                continue
            if any(ad.split(".")[0] in cls._ARAYUZ_MODULLERI for ad in adlar):
                return True
        return False

    def _python_calistir(self, py, arayuz=False):
        if not self.python_exe:
            return {"durum": "atlandi"}
        self.calistirma_sayisi += 1
        if arayuz:
            govde = self._ARAYUZ_ON_EKI_GOVDE
            on_ek = _KONTROL_ON_EKI + "; exec(compile(" + repr(govde) \
                + ", '<turkod_on_ek>', 'exec'))"
            return self._arayuz_calistir(on_ek + "\n" + py)
        tam = _KONTROL_ON_EKI + "\n" + py
        try:
            sonuc, temp_path = self.core._kontrol_calistir(self.python_exe, tam, self.zaman_asimi)
        except subprocess.TimeoutExpired:
            return {"durum": "zaman_asimi"}
        except Exception as e:
            return {"durum": "atlandi", "mesaj": str(e)}

        if sonuc.returncode == 0:
            return {"durum": "ok"}
        return self._hata_ayristir(sonuc.stderr or "", temp_path, sonuc.returncode)

    def _hata_ayristir(self, stderr, temp_path, cikis_kodu):
        """stderr'deki SON hata izinden {'durum': 'hata', ...}; iz yoksa ok."""
        blok = stderr
        i = stderr.rfind("Traceback (most recent call last):")
        if i >= 0:
            blok = stderr[i:]
        son = ""
        satirlar = [s.strip() for s in blok.splitlines() if s.strip()]
        for satir in reversed(satirlar):
            if re.match(r"^[\w.]+(?:Error|Exception|Exit|Interrupt|Warning)\b", satir):
                son = satir
                break
        if not son and satirlar:
            son = satirlar[-1]
        m = re.match(r"^([\w.]+)(?::\s*(.*))?$", son)
        tip = m.group(1).split(".")[-1] if m else "Hata"
        mesaj = (m.group(2) or "") if m else son
        if "Error" not in tip and "Exception" not in tip and "Exit" not in tip:
            # Traceback'siz çıkış (ör. çık(1)).
            return {"durum": "ok", "cikis": cikis_kodu}
        satir = self.core._hata_satiri(blok, temp_path, 1)
        return {"durum": "hata", "tip": tip, "mesaj": mesaj, "satir": satir,
                "son": son, "stderr": stderr}

    def _arayuz_calistir(self, tam):
        """Pencereli programı görünmez kipte ARAYUZ_SURESI saniye çalıştırır.
        Bu sürede çıkmazsa durdurulur; o ana kadar bir hata izi basılmadıysa
        (ör. tkinter geri çağrı hatası) başarılı sayılır."""
        import os
        import shutil
        import tempfile
        sure = max(self.ARAYUZ_SURESI, self.zaman_asimi)
        dizin = tempfile.mkdtemp(prefix="turkod_kontrol_")
        yol = os.path.join(dizin, "turkod_kontrol.py")
        try:
            with open(yol, "w", encoding="utf-8") as f:
                f.write(tam)
            # Gizli başlat: Windows, programın İLK pencere gösterme çağrısını
            # (ShowWindow / WS_VISIBLE) SW_HIDE olarak uygular. Açılışta Python
            # kilidini tutan motorlarda (Ursina) programın kendi içindeki gizleyici
            # geç kaldığından asıl koruma budur.
            bilgi = None
            if hasattr(subprocess, "STARTUPINFO"):
                bilgi = subprocess.STARTUPINFO()
                bilgi.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                bilgi.wShowWindow = 0  # SW_HIDE
            surec = subprocess.Popen(
                [self.python_exe, "-X", "utf8", yol], cwd=dizin,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", startupinfo=bilgi,
                env=self.core._subprocess_env(), **self.core._subprocess_flags())
            gizleyici = _PencereGizleyici(surec.pid)
            try:
                _, stderr = surec.communicate(timeout=sure)
                bitti = True
            except subprocess.TimeoutExpired:
                # Alt süreçleriyle birlikte (oyun motorlarının yardımcı süreçleri).
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(surec.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, **self.core._subprocess_flags())
                try:
                    _, stderr = surec.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    surec.kill()
                    _, stderr = surec.communicate()
                bitti = False
            gizleyici.durdur()
            stderr = stderr or ""
            if bitti and surec.returncode == 0:
                return {"durum": "ok"}
            if not bitti and "Traceback (most recent call last):" not in stderr:
                return {"durum": "ok", "pencere_suresi": sure}
            sonuc = self._hata_ayristir(stderr, yol, surec.returncode)
            if not bitti and sonuc["durum"] == "ok":
                sonuc["pencere_suresi"] = sure
            return sonuc
        except Exception as e:  # noqa: BLE001
            return {"durum": "atlandi", "mesaj": str(e)}
        finally:
            shutil.rmtree(dizin, ignore_errors=True)

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _satirlar(kod):
        return kod.split("\n")

    @staticmethod
    def _satir_degistir(kod, satir_no, yeni):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        if satirlar[satir_no - 1] == yeni:
            return None
        satirlar[satir_no - 1] = yeni
        return "\n".join(satirlar)

    def _girinti_birimi(self, kod):
        return self.core._girinti_birimi(kod.split("\n"))

    def _ice_aktarma_ekle(self, kod, modul):
        """'içe_aktar modul' satırını mevcut içe aktarmaların altına ekler."""
        satirlar = kod.split("\n")
        if re.search(rf"^[ \t]*(?:içe_aktar|ice_aktar)\s+{re.escape(modul)}\b", kod, re.M):
            return None
        yer = 0
        for i, s in enumerate(satirlar):
            temiz = s.strip()
            if re.match(r"^(?:içe_aktar|ice_aktar|den|from|import)\b", temiz) and _girinti(s) == 0:
                yer = i + 1
            elif temiz and not temiz.startswith("#") and yer:
                break
        satirlar.insert(yer, f"{_tr('import', 'içe_aktar')} {modul}")
        return "\n".join(satirlar)

    @staticmethod
    def _modul_var_mi(modul_tr):
        """TürKod modül adının Python karşılığı kurulu mu (yaklaşık)."""
        import importlib.util
        py = MODUL_CEVIRILERI.get(modul_tr, modul_tr)
        try:
            return importlib.util.find_spec(str(py).split(".")[0]) is not None
        except (ImportError, ValueError):
            return False

    def _sozluk(self):
        return self.core._sozluk_duz_harita()

    def _tanimlar(self, kod):
        try:
            return set(kullanici_tanimlari(kod))
        except Exception:
            return set()

    @staticmethod
    def _py_agaci(kod):
        try:
            py = turkce_kodu_donustur(kod)
            return ast.parse(py), py
        except Exception:
            return None, None

    # ==================================================================
    # ANA AKIŞ
    # ==================================================================
    def calistir(self, kod):
        baslangic = time.time()
        orijinal = (kod or "").replace("\r\n", "\n").replace("\r", "\n")
        if not orijinal.strip():
            return {"ok": False, "hata": "Düzeltilecek kod bulunamadı."}
        kod = orijinal

        self._okuma(kod)
        kod = self._on_temizlik(kod)
        kod = self._sozdizimi_asamasi(kod)
        if self._sozdizimi_durumu(kod) is not None:
            # Yerel sözdizimi araması tükendi: yapay zekâ (ayarlıysa) denenir.
            kod = self._ai_asamasi(kod)
        sozdizimi_temiz = self._sozdizimi_durumu(kod) is None
        if sozdizimi_temiz:
            kod = self._anlam_asamasi(kod)
            kod = self._calisma_asamasi(kod)
            if self._calistir(kod)["durum"] == "hata":
                ai_oncesi = kod
                kod = self._ai_asamasi(kod)
                if kod != ai_oncesi and self._calistir(kod)["durum"] == "hata":
                    # Yapay zekânın düzeltmesi yeni bir hatayı açığa çıkardıysa
                    # yerel çalışma aşaması bir tur daha dener.
                    kod = self._calisma_asamasi(kod)
            self._inceleme_asamasi(kod)
        son = self._son_dogrulama(kod)
        return self._rapor(orijinal, kod, son, time.time() - baslangic)

    # ------------------------------------------------------------------
    # Son çare: yapay zekâ (yalnızca kullanıcı AI'ı ayarlardan açtıysa)
    # ------------------------------------------------------------------
    MAKS_AI_DENEME = 3

    def _durum_ozeti(self, kod):
        """(sıra, açıklama, çalışma_sonucu). Sıra büyükse daha iyi."""
        sd = self._sozdizimi_durumu(kod)
        if sd is not None:
            return 0, f"Satır {sd['satir']}: {sd['mesaj']} ({sd['tip']})", None
        sonuc = self._calistir(kod)
        if sonuc["durum"] == "hata":
            return 1, f"Satır {sonuc['satir']}: {sonuc['son']}", sonuc
        return 2, "", sonuc

    def _ai_asamasi(self, kod):
        ayar = self.core.ayarlar
        if not ayar.get("ai_aktif") or not ayar.get("ai_api_key"):
            return kod
        sira, hata, sonuc = self._durum_ozeti(kod)
        if sira >= 2:
            return kod
        self.dusun("🤖 Yerel yöntemleri tükettim; yapay zekâdan çözüm istiyorum…")
        # Düzeltme istekleri sohbet geçmişine karışmasın.
        yedek_gecmis = list(getattr(self.core, "ai_mesaj_gecmisi", []))
        deneme_kodu = kod
        try:
            for deneme in range(1, self.MAKS_AI_DENEME + 1):
                try:
                    cevap = self.core._ai_api_cagri(self._ai_istemi(deneme_kodu, hata))
                except Exception as e:  # noqa: BLE001 - ağ/anahtar hatası: yerel sonuçla devam
                    self.dusun(f"⚠️ Yapay zekâ yanıt vermedi: {str(e)[:120]}", bekle=False)
                    return kod
                aday = self._ai_kodu_al(cevap)
                if not aday or aday.strip() == deneme_kodu.strip():
                    self.dusun("↩️ Yapay zekâ kullanılabilir bir kod döndürmedi.", bekle=False)
                    continue
                # Güvenlik: çalıştırma izni kullanıcının KENDİ koduna göre verildi.
                # Yapay zekâ dosya silme / ağ / komut çalıştırma gibi yeni bir işlem
                # eklediyse öneri hiç çalıştırılmadan reddedilir.
                try:
                    yeni_riskler = (set(self.core.calistirma_riskleri(aday))
                                    - set(self.core.calistirma_riskleri(kod)))
                except Exception:  # noqa: BLE001
                    yeni_riskler = {"risk denetimi yapılamadı"}
                if yeni_riskler:
                    self.dusun("🛡️ Yapay zekânın önerisi programda olmayan riskli bir işlem "
                               f"ekliyordu ({', '.join(sorted(yeni_riskler))[:120]}); "
                               "güvenlik için çalıştırmadan reddettim.", bekle=False)
                    continue
                benzerlik = difflib.SequenceMatcher(None, kod, aday, autojunk=False).ratio()
                if benzerlik < 0.35:
                    self.dusun("↩️ Yapay zekâ programı baştan yazdı; amacı korumak için "
                               "bu öneriyi kullanmadım.", bekle=False)
                    continue
                yeni_sira, yeni_hata, yeni_sonuc = self._durum_ozeti(aday)
                daha_iyi = yeni_sira > sira or (
                    yeni_sira == sira == 1 and self._daha_iyi(
                        yeni_sonuc, sonuc, aday.count("\n") - kod.count("\n")))
                if daha_iyi:
                    durum_metni = ("artık hatasız çalışıyor" if yeni_sira == 2 else
                                   "hata ilerledi")
                    self.dusun(f"✅ Yapay zekânın önerisini yerelde doğruladım: {durum_metni}.")
                    self._duzeltme_ekle(Bulgu(
                        None, "Yapay zekâ ile düzeltildi (yerelde doğrulandı)",
                        f"Yerel kurallar hatayı ({hata[:160]}) çözemedi; yapay zekânın "
                        "önerdiği düzeltme derlenip çalıştırılarak denendi ve kabul edildi.",
                        0.8, "ai"))
                    # Eski 'düzeltemedim' uyarıları artık geçersiz.
                    self.uyarilar = [u for u in self.uyarilar
                                     if u.kategori not in ("sozdizimi", "calisma")]
                    self._uyari_anahtarlari = {(u.satir, u.baslik) for u in self.uyarilar}
                    if yeni_sira == 2:
                        return aday
                    kod, sira, hata, sonuc = aday, yeni_sira, yeni_hata, yeni_sonuc
                    deneme_kodu = aday
                    continue
                self.dusun(f"↩️ Yapay zekânın {deneme}. önerisi sorunu çözmedi; "
                           "hatayı bildirip yeniden istiyorum.", bekle=False)
                deneme_kodu, hata = aday, yeni_hata or hata
        finally:
            self.core.ai_mesaj_gecmisi = yedek_gecmis
        return kod

    @staticmethod
    def _ai_istemi(kod, hata):
        return (
            "Aşağıdaki program TürKod ile yazılmış (Türkçe anahtar kelimeli Python: eğer, "
            "değilse, için, içinde, döngü, fonksiyon, döndür, yazdır, girdi_al ...). "
            "Programda bir hata var; hatayı KESİNLİKLE gider.\n"
            "Kurallar:\n"
            "- Programın amacını, yapısını, değişken adlarını ve çıktı metinlerini koru; "
            "yalnızca hatayı gidermek için gereken en az değişikliği yap.\n"
            "- Kodu TürKod olarak yaz (Python yazarsan da kabul edilir).\n"
            "- Yanıtında YALNIZCA programın tamamını içeren tek bir kod bloğu ver, açıklama yazma.\n\n"
            f"Hata: {hata}\n\n"
            f"```türkod\n{kod}\n```"
        )

    def _ai_kodu_al(self, cevap):
        try:
            parcalar = self.core._ai_mesaj_parse_et(cevap or "")
        except Exception:  # noqa: BLE001
            return None
        kodlar = [p["icerik"] for p in parcalar if p.get("tip") == "kod" and p.get("icerik")]
        if not kodlar:
            return None
        return max(kodlar, key=len).replace("\r\n", "\n").replace("\r", "\n")

    # ------------------------------------------------------------------
    # 1. Okuma
    # ------------------------------------------------------------------
    def _okuma(self, kod):
        satirlar = kod.split("\n")
        dolu = sum(1 for s in satirlar if s.strip() and not s.strip().startswith("#"))
        fonk = len(re.findall(r"^[ \t]*fonksiyon\s+" + ID, kod, re.M))
        sinif = len(re.findall(r"^[ \t]*(?:sınıf|sinif)\s+" + ID, kod, re.M))
        parcalar = [f"{len(satirlar)} satır ({dolu} kod satırı)"]
        if fonk:
            parcalar.append(f"{fonk} fonksiyon")
        if sinif:
            parcalar.append(f"{sinif} sınıf")
        self.dusun("🧠 Kodu okuyorum: " + ", ".join(parcalar) + ".")

    # ------------------------------------------------------------------
    # 2. Ön temizlik
    # ------------------------------------------------------------------
    def _on_temizlik(self, kod):
        self.dusun("🔍 Yazım ve biçim sorunlarını tarıyorum…")

        # a) Karışık sekme / boşluk girintisi.
        satirlar = kod.split("\n")
        if any(s[:1] == " " for s in satirlar) and any(s[:1] == "\t" for s in satirlar):
            kod = "\n".join(
                s[:_girinti(s)].expandtabs(4) + s[_girinti(s):] for s in satirlar)
            self._duzeltme_ekle(Bulgu(
                None, "Karışık sekme/boşluk girintisi boşluğa çevrildi",
                "Aynı dosyada hem sekme hem boşlukla girinti yapılması Python'da "
                "'inconsistent use of tabs' hatasına yol açar.",
                0.97, "girinti"))

        # b) Görünmez / yanlış karakterler (kopyala-yapıştır kaynaklı).
        kod = self._garip_karakterler(kod)

        # c) Ayrık yazılmış anahtar kelimeler ("değilse eğer" -> "değilse_eğer").
        kod = self._ayrik_kelimeler(kod)

        # d) Sözlüğe göre yazım hataları ('yazdir' -> 'yazdır', 'eger' -> 'eğer').
        try:
            _, ham_degisiklikler = self.core._kodu_yerel_duzelt(kod)
        except Exception:
            ham_degisiklikler = set()
        degisiklikler = self._yazim_filtrele(kod, ham_degisiklikler)
        # Yalnızca gerçekten tanımsız adlar düzeltilir: kod derlendiği için
        # kabul edilen düzeltmeler lambda parametrelerini ('sayim' -> 'sayı')
        # ve sözlük(...) anahtarlarını ('soyisim=' -> 'kesişim=') bozuyordu.
        if degisiklikler:
            try:
                tanimsiz = self._statik_tanimsiz(kod)
            except Exception:
                tanimsiz = None
            if tanimsiz is not None:
                adlar = {ad for ad, _ in tanimsiz}
                degisiklikler = [(e, d) for e, d in degisiklikler if e in adlar]
        yeni = kod
        for eski, dogru in degisiklikler:
            yeni = ad_degistir_kod(yeni, eski, dogru)
        if degisiklikler and yeni != kod and self._kabul_edilebilir(kod, yeni):
            tanimlar = self._kod_tanimlari(kod)
            maskeli = maskele(kod).split("\n")
            for eski, dogru in sorted(degisiklikler):
                satir = None
                for i, s in enumerate(maskeli, 1):
                    if re.search(rf"(?<![\w]){re.escape(eski)}(?![\w])", s):
                        satir = i
                        break
                neden = (f"'{eski}' tanımlı değil; koddaki en yakın ad '{dogru}'."
                         if dogru in tanimlar else
                         f"'{eski}' TürKod sözlüğünde yok; en yakın komut '{dogru}'.")
                self._duzeltme_ekle(Bulgu(
                    satir, f"Yazım: '{eski}' → '{dogru}'", neden, 0.85, "yazim"))
            kod = yeni
        return kod

    def _kod_tanimlari(self, kod):
        """Kullanıcının tanımladığı adlar (atama, fonksiyon, sınıf, parametre,
        döngü değişkeni, takma ad). Tanım satırı bozuk olsa bile (ör.
        'fonksiyon selam:') bulunur."""
        tanimlar = set(self._tanimlar(kod))
        maskeli = maskele(kod)
        desenler = (
            rf"^[ \t]*({ID})\s*(?:[-+*/%]|//|\*\*)?=(?!=)",
            rf"\b(?:fonksiyon|sınıf|sinif)\s+({ID})",
            rf"\b(?:için|icin)\s+({ID})",
            rf"\bolarak\s+({ID})",
        )
        for d in desenler:
            tanimlar.update(re.findall(d, maskeli, re.M))
        for m in re.finditer(rf"\bfonksiyon\s+{ID}\s*\(([^)\n]*)\)?", maskeli):
            tanimlar.update(re.findall(ID, m.group(1)))
        # İçe aktarılan modül/adlar da tanımdır ('math' -> 'Matris' olmasın).
        tanimlar.update(self.core.ice_aktarilan_adlar(maskeli))
        return tanimlar

    def _yazim_filtrele(self, kod, degisiklikler):
        """Sözlük tabanlı yazım düzeltmelerini akıllıca süzer:
        * Kullanıcının kendi tanımladığı adlara dokunulmaz.
        * Yanlış yazılan ad, kullanıcının bir değişkenine daha yakınsa sözlük
          kelimesi yerine o değişken seçilir ('sayc' -> 'sayac', 'Sayaç' değil).
        """
        if not degisiklikler:
            return []
        tanimlar = self._kod_tanimlari(kod)
        sonuc = []
        for eski, dogru in sorted(degisiklikler):
            if eski in tanimlar:
                continue
            yakin = self.core._en_yakin_eslesme(eski, sorted(tanimlar), cutoff=0.75)
            if yakin and yakin[0] != eski:
                oran_kullanici = difflib.SequenceMatcher(
                    None, _normalize(eski), _normalize(yakin[0])).ratio()
                oran_sozluk = difflib.SequenceMatcher(
                    None, _normalize(eski), _normalize(dogru)).ratio()
                if oran_kullanici >= oran_sozluk:
                    dogru = yakin[0]
            if dogru != eski:
                sonuc.append((eski, dogru))
        return sonuc

    _GARIP = {
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
        "‘": "'", "’": "'", "‚": "'",
        " ": " ", " ": " ", " ": " ", "​": "", "﻿": "",
        "−": "-", "–": "-", "×": "*", "÷": "/",
    }

    def _garip_karakterler(self, kod):
        maskeli = maskele(kod)
        cikti = []
        degisen_satirlar = set()
        satir = 1
        for ch_m, ch in zip(maskeli, kod):
            if ch == "\n":
                satir += 1
            # Tırnaklar maskede de kalır; metin İÇİNDEKİ karakterlere dokunma.
            if ch_m != "\x01" and ch in self._GARIP:
                cikti.append(self._GARIP[ch])
                degisen_satirlar.add(satir)
            else:
                cikti.append(ch)
        if not degisen_satirlar:
            return kod
        yeni = "".join(cikti)
        # Bu karakterler metin dışında hiçbir zaman geçerli olmadığından
        # dönüşüm her zaman güvenlidir; yalnızca çeviriyi bozmadığı denetlenir.
        if self._cevir(yeni) is None and self._cevir(kod) is not None:
            return kod
        ilk = min(degisen_satirlar)
        ek = f" (+{len(degisen_satirlar) - 1} satır daha)" if len(degisen_satirlar) > 1 else ""
        self._duzeltme_ekle(Bulgu(
            ilk, f"Akıllı tırnak / görünmez karakter düzeltildi{ek}",
            "Kelime işlemciden kopyalanan “ ” ‘ ’ tırnakları, bölünmez boşluk ve "
            "benzeri karakterler Python'da 'invalid character' hatası verir.",
            0.95, "karakter"))
        return yeni

    def _ayrik_kelimeler(self, kod):
        kelimeler = set()
        for k in list(_keyword_words) + list(_block_words) + list(self._EK_BIRLESIK):
            if "_" in k and not k.startswith("_") and k.count("_") <= 2:
                kelimeler.add(k)
        if not kelimeler:
            return kod
        maskeli = maskele(kod)
        degisimler = []
        for k in sorted(kelimeler, key=len, reverse=True):
            parca = [re.escape(p) for p in k.split("_")]
            desen = r"(?<![\w])" + r"[ \t]+".join(parca) + r"(?![\w])"
            for m in re.finditer(desen, maskeli):
                if any(m.start() < b and a < m.end() for a, b, _ in degisimler):
                    continue
                degisimler.append((m.start(), m.end(), k))
        if not degisimler:
            return kod
        yeni = kod
        for a, b, k in sorted(degisimler, reverse=True):
            yeni = yeni[:a] + k + yeni[b:]
        if not self._kabul_edilebilir(kod, yeni):
            return kod
        for a, _, k in sorted(degisimler):
            satir = kod.count("\n", 0, a) + 1
            self._duzeltme_ekle(Bulgu(
                satir, f"Ayrık yazılmış komut birleştirildi: '{k.replace('_', ' ')}' → '{k}'",
                "TürKod'da çok kelimeli komutlar alt çizgiyle tek kelime olarak yazılır.",
                0.96, "yazim"))
        return yeni

    # ------------------------------------------------------------------
    # 3. Sözdizimi
    # ------------------------------------------------------------------
    def _sozdizimi_asamasi(self, kod):
        durum = self._sozdizimi_durumu(kod)
        if durum is None:
            self.dusun("✅ Sözdizimi temiz görünüyor.")
            return kod
        self.dusun("🧩 Sözdizimi hatalarını çözüyorum…")
        gorulen = {self._hash(kod)}
        for _ in range(self.MAKS_SOZDIZIMI):
            durum = self._sozdizimi_durumu(kod)
            if durum is None:
                self.dusun("✅ Tüm sözdizimi hataları giderildi.")
                return kod
            if durum["tip"] == "CeviriHatasi":
                self._uyari_ekle(None, "Kod Python'a çevrilemedi.", seviye="hata")
                return kod
            satir, mesaj = durum["satir"], durum["mesaj"]
            self.dusun(f"⚠️ Satır {satir}: {self._mesaj_turkce(mesaj)}")

            adaylar = self._sozdizimi_adaylari(kod, satir, mesaj)
            en_iyi = None
            for sira, (aday_kod, bulgu) in enumerate(adaylar):
                if aday_kod is None or aday_kod == kod:
                    continue
                h = self._hash(aday_kod)
                if h in gorulen:
                    continue
                puan = self._degerlendir(kod, aday_kod, durum)
                if puan is None:
                    continue
                # Eşit puanda: daha az satıra dokunan, sonra daha güvenilir
                # (listede önce gelen) aday.
                dokunulan = len(self._degisen_satirlar(kod, aday_kod))
                anahtar = (puan, -dokunulan, -sira)
                if en_iyi is None or anahtar > en_iyi[0]:
                    en_iyi = (anahtar, aday_kod, bulgu)
            gecerli = [a for a in adaylar if a[0] is not None and a[0] != kod]
            if en_iyi is None:
                # Tek adımlık adaylar yetmedi: komşu satırlarda ve iki adımlı
                # birleşimlerde aramaya devam et (hata çoğu zaman bildirilen
                # satırdan önce başlar ya da iki küçük düzeltme birden gerekir).
                derin = self._derin_sozdizimi_arama(kod, durum, gorulen)
                if derin is not None:
                    kod, bulgular = derin
                    gorulen.add(self._hash(kod))
                    for b in bulgular:
                        self._duzeltme_ekle(b)
                    continue
                self._cozulemeyen_sozdizimi(kod, satir, mesaj)
                return kod
            if len(gecerli) > 1:
                self.dusun(f"💡 {len(gecerli)} olası çözümü denedim; en iyisini seçtim.", bekle=False)
            _, kod, bulgu = en_iyi
            gorulen.add(self._hash(kod))
            self._duzeltme_ekle(bulgu)
        return kod

    DERIN_ARAMA_SURESI = 12.0   # saniye; yalnızca tek adımlık adaylar tükenince

    def _genis_adaylar(self, kod, satir, mesaj):
        """Bildirilen satırın çevresindeki (2 üst, 1 alt) satırlar için de
        aday üretir; aynı kodu üreten adaylar tekilleştirilir."""
        gorulen, sonuc = set(), []
        for s in [satir, satir - 1, satir - 2, satir + 1]:
            if s < 1:
                continue
            for aday, bulgu in self._sozdizimi_adaylari(kod, s, mesaj):
                if aday is None or aday == kod:
                    continue
                h = self._hash(aday)
                if h not in gorulen:
                    gorulen.add(h)
                    sonuc.append((aday, bulgu))
        return sonuc

    def _derin_sozdizimi_arama(self, kod, durum, gorulen):
        """Komşu satırlar + iki adımlı arama. Döner: (yeni_kod, [bulgu]) | None."""
        bitis = time.monotonic() + self.DERIN_ARAMA_SURESI
        self.dusun("🔬 İlk denemeler yetmedi; çevredeki satırları ve birleşik "
                   "çözümleri de deniyorum…")
        ilk = self._genis_adaylar(kod, durum["satir"], durum["mesaj"])
        en_iyi = None
        ikinci_tur = []
        for aday, bulgu in ilk:
            if self._hash(aday) in gorulen:
                continue
            puan = self._degerlendir(kod, aday, durum)
            if puan is not None and puan[0] >= 2:
                anahtar = (puan, -len(self._degisen_satirlar(kod, aday)))
                if en_iyi is None or anahtar > en_iyi[0]:
                    en_iyi = (anahtar, aday, [bulgu])
            else:
                ikinci_tur.append((aday, bulgu))
        if en_iyi is not None:
            return en_iyi[1], en_iyi[2]

        # İki adım: ilk adım tek başına ilerleme sağlamasa da, ardından gelen
        # ikinci düzeltmeyle birlikte hatayı gideren bir çift aranır.
        for aday1, bulgu1 in ikinci_tur:
            if time.monotonic() > bitis:
                break
            d1 = self._sozdizimi_durumu(aday1)
            if d1 is None or d1["tip"] == "CeviriHatasi":
                continue
            for aday2, bulgu2 in self._genis_adaylar(aday1, d1["satir"], d1["mesaj"]):
                if time.monotonic() > bitis:
                    break
                if self._hash(aday2) in gorulen:
                    continue
                puan = self._degerlendir(kod, aday2, durum)
                if puan is None or puan[0] < 2:
                    continue
                anahtar = (puan, -len(self._degisen_satirlar(kod, aday2)))
                if en_iyi is None or anahtar > en_iyi[0]:
                    en_iyi = (anahtar, aday2, [bulgu1, bulgu2])
                    if puan[0] == 3:
                        break
            if en_iyi is not None and en_iyi[0][0][0] == 3:
                break
        if en_iyi is not None:
            self.dusun("💡 İki düzeltmenin birlikte uygulanmasıyla çözüm buldum.", bekle=False)
            return en_iyi[1], en_iyi[2]
        return None

    @staticmethod
    def _mesaj_turkce(mesaj):
        ceviri = (
            (r"expected ':'", "':' bekleniyordu"),
            (r"invalid syntax\. Perhaps you forgot a comma\?", "geçersiz yazım (virgül eksik olabilir)"),
            (r"invalid syntax", "geçersiz yazım"),
            (r"'(.)' was never closed", r"'\1' kapatılmamış"),
            (r"unmatched '(.)'", r"fazladan '\1'"),
            (r"closing parenthesis '(.)' does not match opening parenthesis '(.)'",
             r"'\1' kapanışı '\2' açılışıyla eşleşmiyor"),
            (r"expected an indented block.*", "girintili blok bekleniyordu"),
            (r"unexpected indent", "beklenmeyen girinti"),
            (r"unindent does not match any outer indentation level", "girinti seviyesi uyuşmuyor"),
            (r"unterminated string literal.*", "kapatılmamış metin (tırnak eksik)"),
            (r"unterminated triple-quoted string literal.*", "kapatılmamış çok satırlı metin"),
            (r"invalid character.*", "geçersiz karakter"),
            (r"Missing parentheses in call to '(\w+)'.*", r"'\1' çağrısında parantez eksik"),
            (r"expected '\('", "'(' bekleniyordu"),
            (r"cannot assign to .*", "buraya atama yapılamaz"),
            (r"'return' outside function", "'döndür' fonksiyon dışında"),
            (r"'break' outside loop", "'kır' döngü dışında"),
            (r"'continue' not properly in loop", "'devam_et' döngü dışında"),
        )
        for desen, tr in ceviri:
            if re.search(desen, mesaj):
                return re.sub(desen, tr, mesaj)
        return mesaj

    def _cozulemeyen_sozdizimi(self, kod, satir, mesaj):
        satirlar = kod.split("\n")
        metin = satirlar[satir - 1].strip() if 0 < satir <= len(satirlar) else ""
        oneri = ""
        try:
            kw = self.core._anahtar_kelime_tanimi(kod, satir)
        except Exception:
            kw = None
        if kw:
            mesaj_tr = kw["mesaj"]
            oneri = "Değişkene başka bir ad verin (ör. sonuna '_değer' ekleyin)."
            satir = kw["satir"] or satir
        else:
            mesaj_tr = f"Satır {satir}: {self._mesaj_turkce(mesaj)}"
            if "outside function" in mesaj:
                oneri = "'döndür' yalnızca bir fonksiyonun içinde kullanılabilir."
            elif "outside loop" in mesaj or "not properly in loop" in mesaj:
                oneri = "'kır' / 'devam_et' yalnızca bir döngünün içinde kullanılabilir."
            elif metin:
                oneri = f"Bu satırı kontrol edin: {metin[:80]}"
        self.dusun(f"🤔 Satır {satir}'deki hatayı güvenle düzeltemedim; öneri olarak bildiriyorum.")
        self._uyari_ekle(satir, mesaj_tr, oneri, seviye="hata", kategori="sozdizimi")

    # --- aday üreticiler ----------------------------------------------
    def _sozdizimi_adaylari(self, kod, satir, mesaj):
        m = mesaj.lower()
        adaylar = []

        def ekle(sonuc, baslik, aciklama, guven, kategori="sozdizimi", satir_no=None):
            if sonuc is None:
                return
            if isinstance(sonuc, tuple):
                sonuc = sonuc[0]
            adaylar.append((sonuc, Bulgu(satir_no or satir, baslik, aciklama, guven, kategori)))

        core = self.core
        satir_listesi = [satir] + ([satir - 1] if satir > 1 else [])

        if "indent" in m or "tab" in m:
            ekle(core._girinti_hatasi_duzelt(kod, satir, mesaj), "Girinti düzeltildi",
                 "Python'da bloklar girintiyle belirlenir; satırın girintisi "
                 "üstündeki bloğa göre hizalandı.", 0.9, "girinti")
        if "indent" in m or "outside function" in m or "outside loop" in m \
                or "not properly in loop" in m or "invalid syntax" in m:
            # Satırın olası TÜM girinti seviyeleri denenir (üstteki blokların
            # seviyeleri); derlenen seviye seçilir. Örn. 'döndür' yanlışlıkla
            # fonksiyon dışına kaydıysa geri fonksiyonun içine alınır.
            for s in [satir] + ([satir - 1] if satir > 1 else []):
                for yeni, hedef_g in self._girinti_seviye_adaylari(kod, s):
                    ekle(yeni, f"Girinti {hedef_g} boşluğa hizalandı",
                         "Satırın girintisi, ait olduğu bloğun girintisiyle "
                         "eşleşmiyordu.", 0.88, "girinti", satir_no=s)

        if "f-string" in m:
            ekle(self._fstring_parantez_duzelt(kod, satir), "f-metindeki süslü parantez kapatıldı",
                 "f\"...{değişken}...\" içinde açılan her '{' kapatılmalıdır.", 0.9)

        for s in satir_listesi:
            ekle(core._iki_nokta_duzelt(kod, s), "Eksik ':' eklendi",
                 "Blok başlatan komutlar (eğer, döngü, için, fonksiyon, sınıf …) "
                 "satır sonunda ':' ister.", 0.95, satir_no=s)

        if "'=='" in m or "cannot assign" in m or "invalid syntax" in m:
            ekle(core._esittir_duzelt(kod, satir), "Koşulda '=' → '==' yapıldı",
                 "'=' atama, '==' karşılaştırmadır; koşullarda karşılaştırma gerekir.",
                 0.9)

        ekle(self._operator_duzelt(kod, satir), "Operatör yazımı düzeltildi",
             "'=<', '=>', '<>' gibi yazımlar geçersizdir; doğrusu '<=', '>=', '!='.",
             0.93)

        if "missing parentheses" in m or "invalid syntax" in m:
            for s in satir_listesi:
                ekle(self._cagri_parantezi_ekle(kod, s), "Çağrıya parantez eklendi",
                     "Fonksiyon çağrılarında argümanlar parantez içinde yazılır: "
                     "yazdır(\"merhaba\").", 0.92, satir_no=s)

        if "expected '('" in m:
            ekle(self._fonksiyon_parantezi(kod, satir), "Fonksiyon tanımına '()' eklendi",
                 "Parametresi olmasa bile fonksiyon adından sonra '()' yazılmalıdır.",
                 0.95)

        if "comma" in m or "invalid syntax" in m:
            for s in satir_listesi:
                ekle(self._virgul_ekle(kod, s), "Eksik virgüller eklendi",
                     "Liste / çağrı içindeki değerler virgülle ayrılmalıdır.", 0.85,
                     satir_no=s)

        if "never closed" in m or "unexpected eof" in m or "invalid syntax" in m or "expected" in m:
            for s in range(satir, max(0, satir - 6), -1):
                for yeni, baslik in self._parantez_kapat_adaylari(kod, s):
                    ekle(yeni, baslik,
                         "Açılan her parantez kapatılmalıdır; kapanış en uygun yere eklendi.",
                         0.88, satir_no=s)

        if "unmatched" in m or "does not match" in m:
            ekle(self._fazla_kapanis_sil(kod, satir), "Fazladan kapanış parantezi silindi",
                 "Bu satırda açılmamış bir parantez kapatılıyordu.", 0.88)
            ekle(self._yanlis_kapanis_duzelt(kod, satir), "Yanlış tür kapanış parantezi düzeltildi",
                 "'(' ile açılan ')' ile, '[' ile açılan ']' ile kapanmalıdır.", 0.9)

        if "unterminated" in m or "eol" in m or "invalid syntax" in m:
            ekle(self._tirnak_duzelt(kod, satir), "Eksik / uyumsuz tırnak düzeltildi",
                 "Metinler aynı tür tırnakla açılıp kapanmalıdır.", 0.88)

        # Mevcut genel düzeltici (son çare).
        ekle(core._sozdizimi_duzelt(kod, satir, mesaj), "Sözdizimi hatası düzeltildi",
             "Hata satırı için bilinen kalıplarla otomatik düzeltme yapıldı.", 0.75)
        return adaylar

    @staticmethod
    def _operator_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        degisim = [("=<", "<="), ("=>", ">="), ("<>", "!="), ("=!", "!="), ("===", "==")]
        yeni = list(satir)
        degisti = False
        for eski, dogru in degisim:
            for mm in re.finditer(re.escape(eski), maskeli):
                a, b = mm.start(), mm.end()
                if eski == "=>" and maskeli[max(0, a - 1):a] in "<>!=":
                    continue
                yeni[a:b] = list(dogru) + [""] * (b - a - len(dogru))
                degisti = True
        if not degisti:
            return None
        satirlar[satir_no - 1] = "".join(yeni)
        return "\n".join(satirlar)

    def _cagri_parantezi_ekle(self, kod, satir_no):
        """yazdır "merhaba"  ->  yazdır("merhaba")"""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        sozluk = self._sozluk()
        m = re.match(rf"^(\s*)({ID})[ \t]+(?![=(\[.,:+\-*/%<>!])(.+?)\s*$", satir)
        if not m:
            return None
        ad = m.group(2)
        hedef = sozluk.get(ad, ad)
        cagrilabilir = (ad in self._CAGRILABILIR_KOMUTLAR
                        or (hasattr(builtins, hedef) and callable(getattr(builtins, hedef))
                            and not isinstance(getattr(builtins, hedef), type)))
        if not cagrilabilir or ad in _keyword_words or ad in _block_words:
            return None
        arguman = m.group(3)
        if arguman.endswith(":"):
            return None
        satirlar[satir_no - 1] = f"{m.group(1)}{ad}({arguman})"
        return "\n".join(satirlar)

    @staticmethod
    def _fonksiyon_parantezi(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        m = re.match(rf"^(\s*fonksiyon\s+{ID})\s*(:?)\s*$", satirlar[satir_no - 1])
        if not m:
            return None
        satirlar[satir_no - 1] = m.group(1) + "():"
        return "\n".join(satirlar)

    def _virgul_ekle(self, kod, satir_no):
        """[1 2 3] -> [1, 2, 3]   /   f(a b) -> f(a, b)"""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        anahtar = set(_keyword_words) | {
            "ve", "veya", "değil", "degil", "içinde", "icinde", "için", "icin", "eğer", "eger",
            "değilse", "degilse", "olarak", "aynı_mı", "ayni_mi", "isimsiz", "and", "or",
            "not", "in", "is", "if", "else", "for", "lambda", "as"}
        ekler = []
        derinlik = 0
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                derinlik += 1
            elif ch in _KAPAYAN:
                derinlik -= 1
            elif ch in " \t" and derinlik > 0:
                j = i
                while j < len(maskeli) and maskeli[j] in " \t":
                    j += 1
                if j >= len(maskeli) or i == 0 or maskeli[i - 1] in " \t":
                    continue
                onceki, sonraki = maskeli[i - 1], maskeli[j]
                atom_son = onceki.isalnum() or onceki in "_)]}\"'\x01"
                atom_bas = sonraki.isalnum() or sonraki in "_([{\"'" or sonraki == "\x01"
                if not (atom_son and atom_bas):
                    continue
                sol = re.search(r"(\w+)$", maskeli[:i])
                sag = re.match(r"(\w+)", maskeli[j:])
                if (sol and sol.group(1) in anahtar) or (sag and sag.group(1) in anahtar):
                    continue
                ekler.append(i)
        if not ekler:
            return None
        yeni = satir
        for i in reversed(ekler):
            yeni = yeni[:i] + "," + yeni[i:]
        satirlar[satir_no - 1] = yeni
        return "\n".join(satirlar)

    @staticmethod
    def _acik_parantezler(maskeli_satir):
        yigin = []
        for ch in maskeli_satir:
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN and yigin and yigin[-1] == _KAPAYAN[ch]:
                yigin.pop()
        return yigin

    def _parantez_kapat_adaylari(self, kod, satir_no):
        """Satırda açılıp kapanmayan parantezleri; aynı satırın sonuna (':'
        varsa ondan önce) ya da devam eden satırların sonuna kapatan adaylar."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return []
        maskeli = maskele(kod).split("\n")
        acik = self._acik_parantezler(maskeli[satir_no - 1])
        if not acik:
            return []
        ek = "".join(_ACAN[c] for c in reversed(acik))
        adaylar = []

        def kapat(i):
            s = satirlar[i].rstrip()
            ms = maskeli[i].rstrip()
            yorum = ""
            if len(ms) < len(s):  # satır sonunda yorum var
                yorum = s[len(ms):]
                s = s[:len(ms)].rstrip()
            if s.endswith(":"):
                yeni = s[:-1] + ek + ":"
            else:
                yeni = s + ek
            kopya = list(satirlar)
            kopya[i] = yeni + yorum
            return "\n".join(kopya)

        adaylar.append((kapat(satir_no - 1), f"Kapatılmamış parantez kapatıldı: {ek}"))
        # Çok satırlı ifade: sonraki satırların her birinin sonunda kapatmayı
        # dene (virgül / operatörle biten satırlar, daha içeride başlayan
        # devam satırları). Derlenen en yakın aday seçilir.
        bas_g = _girinti(satirlar[satir_no - 1])
        i = satir_no - 1
        while i + 1 < len(satirlar) and i - satir_no < 12:
            onceki = maskeli[i].rstrip()
            i += 1
            if not satirlar[i].strip():
                continue
            devam = onceki.endswith((",", "(", "[", "{", "+", "-", "*", "/", "%", "=",
                                     "<", ">", "\\")) or \
                re.search(r"\b(?:ve|veya|and|or|değil|not)$", onceki) or \
                _girinti(satirlar[i]) > bas_g
            adaylar.append((kapat(i), f"Çok satırlı ifadenin sonuna {ek} eklendi"))
            if not devam:
                break
        return adaylar

    def _girinti_seviye_adaylari(self, kod, satir_no):
        """Satırı (ve blok başlatıyorsa gövdesini) üstteki blokların olası
        her girinti seviyesine taşıyan adaylar: [(yeni_kod, hedef_girinti)]."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)) or not satirlar[satir_no - 1].strip():
            return []
        hedef = satirlar[satir_no - 1]
        g = _girinti(hedef)
        birim = self._girinti_birimi(kod) or 4
        seviyeler = set()
        en_kucuk = None
        ilk = True
        for s in reversed(satirlar[:satir_no - 1]):
            temiz = s.strip()
            if not temiz or temiz.startswith("#"):
                continue
            sg = _girinti(s)
            if ilk:
                seviyeler.add(sg)
                if maskele(s).rstrip().endswith(":"):
                    seviyeler.add(sg + birim)
                ilk = False
            if en_kucuk is None or sg < en_kucuk:
                seviyeler.add(sg)
                en_kucuk = sg
            if sg == 0:
                break
        seviyeler.add(0)
        # Blok başlatan satırın gövdesi de aynı miktarda kayar.
        bitis = satir_no
        if maskele(hedef).rstrip().endswith(":"):
            while bitis < len(satirlar) and (not satirlar[bitis].strip()
                                             or _girinti(satirlar[bitis]) > g):
                bitis += 1
        adaylar = []
        for hg in sorted(seviyeler, key=lambda x: abs(x - g)):
            if hg == g:
                continue
            fark = hg - g
            kopya = list(satirlar)
            for j in range(satir_no - 1, bitis):
                s = kopya[j].replace("\t", " " * birim) if j == satir_no - 1 else kopya[j]
                if not s.strip():
                    continue
                yg = max(0, _girinti(s) + fark)
                kopya[j] = " " * yg + s.lstrip(" \t")
            adaylar.append(("\n".join(kopya), hg))
        return adaylar

    @staticmethod
    def _fstring_parantez_duzelt(kod, satir_no):
        """f"Toplam: {toplam"  ->  f"Toplam: {toplam}" """
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        for m in re.finditer(r"(?<![\w])([fF][rR]?|[rR][fF])(\"|')(.*?)\2", satir):
            ic = m.group(3).replace("{{", "").replace("}}", "")
            acik = ic.count("{") - ic.count("}")
            if acik > 0:
                kapanis = m.end() - 1
                satirlar[satir_no - 1] = satir[:kapanis] + "}" * acik + satir[kapanis:]
                return "\n".join(satirlar)
        return None

    @staticmethod
    def _fazla_kapanis_sil(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        yigin = []
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN:
                if yigin and yigin[-1] == _KAPAYAN[ch]:
                    yigin.pop()
                elif not yigin:
                    satirlar[satir_no - 1] = satir[:i] + satir[i + 1:]
                    return "\n".join(satirlar)
        return None

    @staticmethod
    def _yanlis_kapanis_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        yigin = []
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN:
                if yigin and yigin[-1] == _KAPAYAN[ch]:
                    yigin.pop()
                elif yigin:
                    dogru = _ACAN[yigin.pop()]
                    satirlar[satir_no - 1] = satir[:i] + dogru + satir[i + 1:]
                    return "\n".join(satirlar)
        return None

    @staticmethod
    def _tirnak_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        govde = satir.rstrip()
        # "abc'  ->  "abc"   (uyumsuz tırnak)
        m = re.search(r"([\"'])([^\"'\n]*)([\"'])", govde)
        if m and m.group(1) != m.group(3):
            temiz = govde[:m.start()] + m.group(1) + m.group(2) + m.group(1) + govde[m.end():]
            if temiz.count('"') % 2 == 0 and temiz.count("'") % 2 == 0:
                satirlar[satir_no - 1] = temiz
                return "\n".join(satirlar)
        for t in ('"', "'"):
            if govde.count(t) % 2 == 1:
                # Kapanış: satır sonundaki ')' / ':' gibi karakterlerden önce.
                k = re.search(r"([)\]}:,]*)$", govde)
                son = k.group(1) if k else ""
                ic = govde[:len(govde) - len(son)] if son else govde
                bas = ic.find(t)
                if son and bas >= 0 and all(c not in ic[bas:] for c in son):
                    yeni = ic + t + son
                else:
                    yeni = govde + t
                satirlar[satir_no - 1] = yeni
                return "\n".join(satirlar)
        return None

    # ------------------------------------------------------------------
    # 4. Anlam (çalışma hatası vermeyen mantık hataları)
    # ------------------------------------------------------------------
    def _anlam_asamasi(self, kod):
        self.dusun("🧪 Kodun mantığını inceliyorum (tip uyumsuzlukları)…")
        yeni = self._girdi_tip_duzelt(kod)
        yeni = self._yerinde_metot_duzelt(yeni)
        return yeni

    # Listeyi/kümeyi YERİNDE değiştirip Hiçlik döndüren metotlar.
    _YERINDE_METOTLAR = {"append", "extend", "insert", "remove", "sort", "reverse",
                         "clear", "update", "add", "discard"}

    def _yerinde_metot_satirlari(self, kod):
        """'liste = liste.sona_ekle(3)' gibi, değişkene Hiçlik atayan satırlar:
        [(satir_no, girinti, ad, metot_tr, ayni_ad)]"""
        sozluk = self._sozluk()
        sonuc = []
        for i, s in enumerate(maskele(kod).split("\n"), 1):
            m = re.match(rf"^(\s*)({ID})\s*=\s*({ID})\s*\.\s*({ID})\s*\(", s)
            if not m:
                continue
            metot = m.group(4)
            if sozluk.get(metot, metot) not in self._YERINDE_METOTLAR:
                continue
            # Satırın tamamı tek çağrı olmalı: 'x = y.sırala() + z' gibi ifadelere dokunma.
            kapa = _eslesen_kapanis(s, m.end() - 1)
            if kapa < 0 or s[kapa + 1:].strip():
                continue
            sonuc.append((i, m.group(1), m.group(2), metot, m.group(2) == m.group(3)))
        return sonuc

    # Statik (hata görülmeden) düzeltmede yalnızca LİSTE metotları: add/update/
    # remove/clear gibi adlar kullanıcı sınıflarında yeni nesne döndürebilir.
    _LISTE_YERINDE_METOTLAR = {"append", "extend", "insert", "sort", "reverse"}

    def _liste_degiskenleri(self, kod):
        """Kodda yalnızca liste değerleri atanan (liste olduğu kesin) adlar."""
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return set()
        liste, diger = set(), set()
        for d in ast.walk(agac):
            if not isinstance(d, ast.Assign):
                continue
            deger = d.value
            liste_mi = isinstance(deger, (ast.List, ast.ListComp)) or (
                isinstance(deger, ast.Call) and isinstance(deger.func, ast.Name)
                and deger.func.id in ("list", "sorted"))
            for hedef in d.targets:
                if isinstance(hedef, ast.Name):
                    # 'x = x.append(...)' ataması bu kararı etkilemez.
                    yerinde = (isinstance(deger, ast.Call) and isinstance(deger.func, ast.Attribute)
                               and deger.func.attr in self._YERINDE_METOTLAR)
                    if liste_mi:
                        liste.add(hedef.id)
                    elif not yerinde:
                        diger.add(hedef.id)
        return liste - diger

    def _yerinde_metot_duzelt(self, kod):
        """Kesin liste olan değişkenlerde (çalışma hatası görülmeden):
        liste = liste.sona_ekle(3)  ->  liste.sona_ekle(3)
        sıralı = liste.sırala()        ->  liste.sırala() + sıralı = liste"""
        sozluk = self._sozluk()
        listeler = self._liste_degiskenleri(kod)
        for satir_no, girinti, ad, metot, ayni in reversed(self._yerinde_metot_satirlari(kod)):
            satirlar = kod.split("\n")
            satir = satirlar[satir_no - 1]
            py_metot = sozluk.get(metot, metot)
            if py_metot not in self._LISTE_YERINDE_METOTLAR:
                continue
            if ayni:
                if ad not in listeler:
                    continue
                yeni_satir = girinti + re.sub(rf"^\s*{re.escape(ad)}\s*=\s*", "", satir)
                baslik = f"'{ad} = {ad}.{metot}(...)' → '{ad}.{metot}(...)'"
                aciklama = (f"'{metot}' listeyi yerinde değiştirir ve Hiçlik döndürür; "
                            f"sonucu '{ad}' değişkenine atamak listeyi siler.")
            elif py_metot == "sort":
                m = re.match(rf"^(\s*){re.escape(ad)}\s*=\s*({ID})\s*\.\s*{re.escape(metot)}\s*\((.*)\)\s*$",
                             satir)
                if not m or m.group(2) not in listeler:
                    continue
                kaynak = m.group(2)
                # Liste yine yerinde sıralanır (program sonra onu kullanıyor olabilir);
                # yalnızca Hiçlik yerine sıralı liste atanır.
                yeni_satir = (f"{m.group(1)}{kaynak}.{metot}({m.group(3)})\n"
                              f"{m.group(1)}{ad} = {kaynak}")
                baslik = f"'{ad} = {kaynak}.{metot}()' düzeltildi"
                aciklama = (f"'{metot}' listeyi yerinde sıralar ve Hiçlik döndürür; "
                            f"'{ad}' artık sıralanmış '{kaynak}' listesini gösterir.")
            else:
                continue
            aday = self._satir_degistir(kod, satir_no, yeni_satir)
            if not aday or self._sozdizimi_durumu(aday) is not None:
                continue
            onceki, sonra = self._calistir(kod), self._calistir(aday)
            if sonra["durum"] == "hata" and onceki["durum"] != "hata":
                continue
            kod = aday
            self._duzeltme_ekle(Bulgu(satir_no, baslik, aciklama, 0.93, "mantik"))
        return kod

    def _girdi_tip_duzelt(self, kod):
        """girdi_al() her zaman METİN döndürür. Değer sayıyla karşılaştırılıyor
        ya da aritmetikte kullanılıyorsa tamsayı(...)/ondalıklı(...) ile sarılır."""
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return kod

        atamalar = {}     # ad -> [satır]
        istemler = {}     # ad -> girdi_al("...") metni
        diger_atama = set()
        donusturulen = set()
        sayisal = {}      # ad -> "int" | "float"
        tahmini = set()   # yalnızca ad/istem sezgisiyle sayı sanılanlar

        def input_mu(dugum):
            return (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name)
                    and dugum.func.id == "input")

        def sayi_mi(dugum):
            if isinstance(dugum, ast.Constant) and type(dugum.value) in (int, float):
                return "float" if isinstance(dugum.value, float) else "int"
            if isinstance(dugum, ast.UnaryOp) and isinstance(dugum.op, (ast.USub, ast.UAdd)):
                return sayi_mi(dugum.operand)
            return None

        for d in ast.walk(agac):
            if isinstance(d, ast.Assign):
                for hedef in d.targets:
                    if isinstance(hedef, ast.Name):
                        if input_mu(d.value):
                            atamalar.setdefault(hedef.id, []).append(d.lineno)
                            if d.value.args and isinstance(d.value.args[0], ast.Constant) \
                                    and isinstance(d.value.args[0].value, str):
                                istemler[hedef.id] = d.value.args[0].value
                        else:
                            diger_atama.add(hedef.id)
            elif isinstance(d, (ast.AugAssign, ast.AnnAssign)) and isinstance(d.target, ast.Name):
                diger_atama.add(d.target.id)
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) \
                    and d.func.id in ("int", "float") and d.args \
                    and isinstance(d.args[0], ast.Name):
                donusturulen.add(d.args[0].id)

        if not atamalar:
            return kod

        def isaretle(ad_dugum, diger):
            if isinstance(ad_dugum, ast.Name) and ad_dugum.id in atamalar:
                tur = sayi_mi(diger)
                if tur:
                    onceki = sayisal.get(ad_dugum.id)
                    sayisal[ad_dugum.id] = "float" if "float" in (tur, onceki) else "int"

        for d in ast.walk(agac):
            if isinstance(d, ast.Compare):
                parcalar = [d.left] + list(d.comparators)
                for op, (a, b) in zip(d.ops, zip(parcalar, parcalar[1:])):
                    if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq, ast.NotEq)):
                        isaretle(a, b)
                        isaretle(b, a)
            elif isinstance(d, ast.BinOp) and isinstance(
                    d.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
                # metin * tamsayı geçerli bir metin tekrarıdır (ad * 20);
                # bunu "sayıya çevir" diye yorumlamak doğru programı bozuyordu.
                def tamsayi_sabit(x):
                    return sayi_mi(x) == "int"
                if isinstance(d.op, ast.Mult) and (
                        tamsayi_sabit(d.left) or tamsayi_sabit(d.right)):
                    continue
                isaretle(d.left, d.right)
                isaretle(d.right, d.left)
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "range":
                for arg in d.args:
                    if isinstance(arg, ast.Name) and arg.id in atamalar:
                        sayisal.setdefault(arg.id, "int")

        # İki girdinin toplanması: "2" + "3" = "23". Metin birleştirme de olabilir;
        # yalnızca ad ya da istem sayı çağrıştırıyorsa (sayı, yaş, kaç, a, b, x ...)
        # sayıya çevrilir.
        def sayi_gibi(ad):
            istem = _normalize(istemler.get(ad, ""))
            return bool(self._SAYI_ADI.match(_normalize(ad)) or self._SAYI_ISTEMI.search(istem))

        for d in ast.walk(agac):
            if isinstance(d, ast.BinOp) and isinstance(d.op, ast.Add) \
                    and isinstance(d.left, ast.Name) and isinstance(d.right, ast.Name) \
                    and d.left.id in atamalar and d.right.id in atamalar \
                    and sayi_gibi(d.left.id) and sayi_gibi(d.right.id):
                for ad in (d.left.id, d.right.id):
                    if ad not in sayisal:
                        sayisal[ad] = "int"
                        tahmini.add(ad)

        sozluk = self._sozluk()
        # Birlikte toplanan girdiler TEK adımda çevrilir: yalnızca biri çevrilince
        # ara adımda 'sayı + metin' hatası çıkar ve doğru düzeltme reddedilirdi.
        gruplar = [[ad] for ad in sorted(sayisal) if ad not in tahmini]
        if tahmini:
            gruplar.append(sorted(tahmini))
        for grup in gruplar:
            grup = [ad for ad in grup if ad not in donusturulen and ad not in diger_atama]
            if not grup:
                continue
            yeni = kod
            satirlar_d = []
            for ad in grup:
                sarici = (_tr("float", "ondalıklı") if sayisal[ad] == "float"
                          else _tr("int", "tamsayı"))
                for satir_no in atamalar[ad]:
                    sonraki = self._cagriyi_sar(yeni, satir_no, "input", sarici, sozluk)
                    if sonraki:
                        yeni = sonraki
                        satirlar_d.append((satir_no, ad, sarici))
            if not satirlar_d or self._sozdizimi_durumu(yeni) is not None:
                continue
            onceki = self._calistir(kod)
            sonra = self._calistir(yeni)
            if sonra["durum"] == "hata" and onceki["durum"] != "hata":
                continue
            kod = yeni
            if grup[0] in tahmini:
                adlar = " ve ".join(f"'{a}'" for a in grup)
                aciklama = (f"girdi_al() her zaman metin döndürür; iki girdi '+' ile "
                            f"toplandığında '2' + '3' = '23' olur. {adlar} sayı gibi "
                            f"göründüğü için sayıya çevrildi (metin birleştirmek "
                            f"istiyorsanız bu değişikliği geri alın).")
                guven = 0.72
            else:
                aciklama = (f"girdi_al() her zaman metin döndürür; '{grup[0]}' ise sayıyla "
                            f"karşılaştırılıyor / hesaplamada kullanılıyor. Çevrilmezse "
                            f"'5' > 3 gibi karşılaştırmalar hata verir ya da '2' * 3 = '222' "
                            f"gibi yanlış sonuç üretir.")
                guven = 0.88
            adlar = ", ".join(dict.fromkeys(f"'{a}'" for _, a, _ in satirlar_d))
            self._duzeltme_ekle(Bulgu(
                satirlar_d[0][0], f"{adlar} girdisi {satirlar_d[0][2]}(...) ile sayıya çevrildi",
                aciklama, guven, "mantik"))
        return kod

    _SAYI_ADI = re.compile(
        r"^(?:[a-z]|[a-z]\d|n\d*|sayi\w*|s\d|\w*sayi\w*|yas|kac\w*|adet\w*|miktar\w*|"
        r"fiyat\w*|tutar\w*|puan\w*|not\d*|notu|vize|final|boy|kilo|agirlik|uzunluk|"
        r"genislik|yukseklik|derece|sicaklik|toplam\w*|carpan\w*|ust|taban|kenar\w*|"
        r"num\w*|number\w*|deger\d*)$")
    _SAYI_ISTEMI = re.compile(
        r"say[i]|kac|yas|adet|miktar|fiyat|tutar|puan|\bnot\b|notu|kilo|boy|derece|"
        r"sicaklik|uzunluk|genislik|yukseklik|number|tam ?sayi|ondalik|\d")

    @staticmethod
    def _cagriyi_sar(kod, satir_no, py_ad, sarici, sozluk):
        """Satırdaki (TürKod karşılığı py_ad olan) çağrıyı sarici(...) içine alır."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        for m in re.finditer(rf"({ID})\s*\(", maskeli):
            ad = m.group(1)
            if sozluk.get(ad, ad) != py_ad:
                continue
            onceki = maskeli[:m.start()].rstrip()
            if onceki.endswith("("):
                ic_ad = re.search(rf"({ID})\s*\($", onceki)
                if ic_ad and sozluk.get(ic_ad.group(1), ic_ad.group(1)) in ("int", "float"):
                    return None
            ac = m.end() - 1
            kapa = _eslesen_kapanis(maskeli, ac)
            if kapa < 0:
                return None
            satirlar[satir_no - 1] = (satir[:m.start()] + f"{sarici}(" +
                                      satir[m.start():kapa + 1] + ")" + satir[kapa + 1:])
            return "\n".join(satirlar)
        return None

    # ------------------------------------------------------------------
    # 5. Çalışma zamanı
    # ------------------------------------------------------------------
    def _calisma_asamasi(self, kod):
        if not self.python_exe:
            self.dusun(f"ℹ️ {self.python_hata} Çalışma testi atlandı.")
            return kod
        ilk = self._calistir(kod)
        if ilk.get("arayuz"):
            # Önce statik denetim: tuşa basınca / nadiren çalışan dallardaki
            # tanımsız adlar deneme çalıştırmasında hiç görünmeyebilir.
            kod = self._statik_ad_asamasi(kod)
            if ilk.get("durum") == "atlandi":
                neden = ("Program gerçek fare/klavyeyi yönetiyor; güvenlik için"
                         if ilk.get("denetim") else "Program çalıştırılamadığı için")
                self.dusun(f"🖼️ {neden} çalıştırmadan, yalnızca statik olarak inceledim.")
                return kod
            self.dusun(f"🖼️ Programı penceresi görünmeden {self.ARAYUZ_SURESI} saniye "
                       "çalıştırıp hata verip vermediğini gözlüyorum…")
        else:
            self.dusun("▶️ Kodu güvenli kipte çalıştırıp davranışını gözlüyorum…")
        cozulemeyen = set()
        for _ in range(self.maks_calisma):
            sonuc = self._calistir(kod)
            if sonuc["durum"] != "hata":
                if sonuc["durum"] == "zaman_asimi":
                    self._zaman_asimi_bildir(kod)
                return kod
            imza = (sonuc["satir"], sonuc["tip"], sonuc["mesaj"])
            if imza in cozulemeyen:
                return kod
            self.dusun(f"⚠️ Satır {sonuc['satir']}: {sonuc['tip']} — "
                       f"{self._calisma_mesaji(sonuc)}")
            adaylar = self._calisma_adaylari(kod, sonuc)
            secilen = None
            for aday_kod, bulgu in adaylar[:self.MAKS_ADAY_CALISTIRMA]:
                if aday_kod is None or aday_kod == kod:
                    continue
                if self._sozdizimi_durumu(aday_kod) is not None:
                    continue
                yeni = self._calistir(aday_kod)
                kayma = aday_kod.count("\n") - kod.count("\n")
                if self._daha_iyi(yeni, sonuc, kayma):
                    secilen = (aday_kod, bulgu)
                    break
                self.dusun("↩️ Bir çözüm denedim ama sorunu gidermedi; geri aldım.", bekle=False)
            if secilen is None:
                cozulemeyen.add(imza)
                self._calisma_ipucu(kod, sonuc)
                return kod
            kod, bulgu = secilen
            self._duzeltme_ekle(bulgu)
        return kod

    # ------------------------------------------------------------------
    # 5b. Statik ad denetimi (pencere açan, çalıştırılamayan programlar)
    # ------------------------------------------------------------------
    _YILDIZ_ONBELLEK = {}   # modül -> set(ad) | None   (süreç boyunca)

    def _yildiz_adlari(self, modul):
        """'from modul import *' ile gelen adlar. Modül, pencere açmadan ayrı bir
        süreçte içe aktarılarak öğrenilir. Belirlenemezse None."""
        if modul in self._YILDIZ_ONBELLEK:
            return self._YILDIZ_ONBELLEK[modul]
        if not self.python_exe:
            return None
        betik = ("import json, sys, importlib\n"
                 "m = importlib.import_module(sys.argv[1])\n"
                 "a = getattr(m, '__all__', None)\n"
                 "if a is None: a = [n for n in dir(m) if not n.startswith('_')]\n"
                 "print('\\n@@TURKOD@@' + json.dumps([str(x) for x in a]))\n")
        adlar = None
        try:
            import json
            import tempfile
            r = subprocess.run([self.python_exe, "-X", "utf8", "-c", betik, modul],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=40, cwd=tempfile.gettempdir(),
                               stdin=subprocess.DEVNULL, env=self.core._subprocess_env(),
                               **self.core._subprocess_flags())
            satirlar = [s for s in r.stdout.splitlines() if s.startswith("@@TURKOD@@")]
            if satirlar:
                adlar = set(json.loads(satirlar[-1][len("@@TURKOD@@"):]))
        except Exception:  # noqa: BLE001 - modül yok / zaman aşımı: denetim atlanır
            adlar = None
        self._YILDIZ_ONBELLEK[modul] = adlar
        return adlar

    def _yildiz_tum_adlari(self, kod):
        agac, _ = self._py_agaci(kod)
        tum = set()
        if agac is None:
            return tum
        for d in ast.walk(agac):
            if isinstance(d, ast.ImportFrom) and d.module and not d.level \
                    and any(a.name == "*" for a in d.names):
                tum |= self._yildiz_adlari(d.module) or set()
        return tum

    def _statik_tanimsiz(self, kod):
        """Hiçbir yerde tanımlanmayan, yerleşik olmayan ve içe aktarılmayan adlar:
        [(ad, satir)]. Belirlenemezse (çeviri hatası, bilinmeyen '*' modülü) None.
        Ad dosyanın HERHANGİ bir yerinde tanımlanıyorsa tanımlı sayılır (yanlış
        alarm vermemek için bilinçli olarak gevşek)."""
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return None
        tanimli = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__builtins__",
                                        "__spec__", "__loader__", "__package__"}
        for d in ast.walk(agac):
            if isinstance(d, ast.Name) and isinstance(d.ctx, (ast.Store, ast.Del)):
                tanimli.add(d.id)
            elif isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                tanimli.add(d.name)
            elif isinstance(d, ast.arg):
                tanimli.add(d.arg)
            elif isinstance(d, (ast.Global, ast.Nonlocal)):
                tanimli.update(d.names)
            elif isinstance(d, ast.ExceptHandler) and d.name:
                tanimli.add(d.name)
            elif isinstance(d, (ast.MatchAs, ast.MatchStar)) and d.name:
                tanimli.add(d.name)
            elif isinstance(d, ast.MatchMapping) and d.rest:
                tanimli.add(d.rest)
            elif isinstance(d, ast.Import):
                for a in d.names:
                    tanimli.add(a.asname or a.name.split(".")[0])
            elif isinstance(d, ast.ImportFrom):
                for a in d.names:
                    if a.name != "*":
                        tanimli.add(a.asname or a.name)
                        continue
                    if d.level or not d.module:
                        return None
                    adlar = self._yildiz_adlari(d.module)
                    if adlar is None:
                        return None
                    tanimli |= adlar
        sonuc, gorulen = [], set()
        for d in ast.walk(agac):
            if isinstance(d, ast.Name) and isinstance(d.ctx, ast.Load) \
                    and d.id not in tanimli and d.id not in gorulen:
                gorulen.add(d.id)
                sonuc.append((d.id, d.lineno))
        return sorted(sonuc, key=lambda x: x[1])

    def _statik_ad_asamasi(self, kod):
        self.dusun("🔎 Programı çalıştırmadan tanımsız adları ve hatalı çağrıları arıyorum…")
        kod = self._ursina_tekil_cagri_duzelt(kod)
        cozulemeyen = set()
        for _ in range(40):
            tanimsiz = self._statik_tanimsiz(kod)
            if tanimsiz is None:
                self.dusun("ℹ️ İçe aktarılan bir modülün adları öğrenilemedi; tanımsız "
                           "ad denetimi atlandı.", bekle=False)
                return kod
            onceki = {a for a, _ in tanimsiz}
            tanimsiz = [t for t in tanimsiz if t[0] not in cozulemeyen]
            if not tanimsiz:
                if not onceki:
                    self.dusun("✅ Tanımsız ad bulunamadı.")
                return kod
            ad, satir = tanimsiz[0]
            self.dusun(f"⚠️ Satır {satir}: '{ad}' tanımlı değil (program bu satıra "
                       f"gelince duracaktı).")
            sonuc = {"durum": "hata", "tip": "NameError", "satir": satir,
                     "mesaj": f"name '{ad}' is not defined",
                     "son": f"NameError: name '{ad}' is not defined"}
            secilen = None
            for aday, bulgu in self._calisma_adaylari(kod, sonuc):
                if self._sozdizimi_durumu(aday) is not None:
                    continue
                yeni = self._statik_tanimsiz(aday)
                if yeni is None:
                    continue
                yeni_adlar = {a for a, _ in yeni}
                if ad not in yeni_adlar and yeni_adlar <= onceki:
                    secilen = (aday, bulgu)
                    break
            if secilen is None:
                cozulemeyen.add(ad)
                self._uyari_ekle(satir, f"'{ad}' tanımlı değil",
                                 "Adı doğru yazdığınızdan ve kullanmadan önce tanımladığınızdan "
                                 "/ içe aktardığınızdan emin olun.", seviye="hata",
                                 kategori="calisma")
                continue
            kod, bulgu = secilen
            self._duzeltme_ekle(bulgu)
        return kod

    # Ursina'nın tekil nesneleri fonksiyon değildir; 'kamera()' çağrısı çöker.
    _URSINA_TEKILLER = {"camera", "window", "mouse", "scene", "color", "application"}

    def _ursina_tekil_cagri_duzelt(self, kod):
        agac, _ = self._py_agaci(kod)
        if agac is None or "ursina" not in self._ice_aktarilan_moduller(agac):
            return kod
        kapat = _tr("quit", "oyun_kapat")
        kapat = "oyun_kapat" if "oyun_kapat" in self._sozluk() else kapat
        satirlar = kod.split("\n")
        for d in ast.walk(agac):
            if not (isinstance(d, ast.If) and isinstance(d.test, ast.Compare)):
                continue
            sabitler = [x.value for x in [d.test.left] + d.test.comparators
                        if isinstance(x, ast.Constant)]
            kacis = "escape" in sabitler
            for ifade in d.body:
                for x in ast.walk(ifade):
                    if not (isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                            and x.func.id in self._URSINA_TEKILLER and not x.args):
                        continue
                    satir_no = x.lineno
                    metin = satirlar[satir_no - 1]
                    token, _ = self.core._satirdaki_sorunlu_token(metin, x.func.id)
                    token = token or x.func.id
                    if not kacis:
                        self._uyari_ekle(satir_no, f"'{token}' bir fonksiyon değil; '{token}()' çöker",
                                         f"Ursina'nın '{token}' nesnesi çağrılamaz; özelliklerini "
                                         f"kullanın (ör. {token}.konum).", seviye="hata",
                                         kategori="calisma")
                        continue
                    yeni = re.sub(rf"(?<![\w.]){re.escape(token)}\s*\(\s*\)", f"{kapat}()", metin, count=1)
                    if yeni != metin:
                        satirlar[satir_no - 1] = yeni
                        self._duzeltme_ekle(Bulgu(
                            satir_no, f"Esc tuşunda '{token}()' → '{kapat}()'",
                            f"'{token}' Ursina'nın bir nesnesidir, fonksiyon gibi çağrılamaz "
                            f"(Esc'e basınca program çökerdi). Esc ile oyundan çıkmak için "
                            f"'{kapat}()' kullanılır.", 0.85, "ursina"))
        return "\n".join(satirlar)

    @staticmethod
    def _ice_aktarilan_moduller(agac):
        moduller = set()
        for d in ast.walk(agac):
            if isinstance(d, ast.Import):
                moduller.update(a.name.split(".")[0] for a in d.names)
            elif isinstance(d, ast.ImportFrom) and d.module and not d.level:
                moduller.add(d.module.split(".")[0])
        return moduller

    def _ursina_adaylari(self, kod, satir, token, hata_adi):
        """Ursina programlarında sık karışan adlar:
        * app = <yanlış>()  ...  app.çalıştır_oyun()   ->  app = Ursina()
        * siyah / rgb_renk  ->  renk.siyah / renk.rgb  (renk, kamera ... nesnelerinin özellikleri)
        * '*' ile gelen adlara yakın yazımlar."""
        agac, _ = self._py_agaci(kod)
        if agac is None or "ursina" not in self._ice_aktarilan_moduller(agac):
            return []
        satirlar = kod.split("\n")
        satir_metni = satirlar[satir - 1] if 0 < satir <= len(satirlar) else ""
        adaylar = []
        disaridan = self._yildiz_tum_adlari(kod)

        m = re.match(rf"^(\s*)({ID})\s*=\s*{re.escape(token)}\s*\(", satir_metni)
        calistir_kelimeleri = [k for k, v in self._sozluk().items() if v == "run"] + ["run"]
        if m and "Ursina" in (disaridan or {"Ursina"}) and re.search(
                rf"\b{re.escape(m.group(2))}\s*\.\s*(?:{'|'.join(map(re.escape, calistir_kelimeleri))})\s*\(",
                kod):
            yeni = re.sub(rf"(?<![\w.]){re.escape(token)}(?=\s*\()", "Ursina", satir_metni, count=1)
            adaylar.append((self._satir_degistir(kod, satir, yeni), Bulgu(
                satir, f"'{token}()' → 'Ursina()'",
                f"Ursina oyunu 'uygulama = Ursina()' ile başlatılır ve sonunda "
                f"'.çalıştır_oyun()' ile çalıştırılır. '{token}' Ursina ile ilgisiz bir "
                f"komut ('{hata_adi}').", 0.92, "ursina")))

        parcalar = [token] + [p for p in token.split("_") if p]
        for nesne_tr, ozellikler in URSINA_NESNELERI.items():
            for p in parcalar:
                if p in ozellikler and p != nesne_tr:
                    adaylar.append((self._her_yerde_degistir(kod, token, f"{nesne_tr}.{p}"), Bulgu(
                        satir, f"'{token}' → '{nesne_tr}.{p}'",
                        f"'{p}' Ursina'da '{nesne_tr}' nesnesinin bir özelliğidir; "
                        f"'{nesne_tr}.{p}' biçiminde yazılır.", 0.88, "ursina")))
                    break

        if disaridan:
            for dogru in self.core._en_yakin_eslesme(hata_adi, sorted(disaridan), cutoff=0.8)[:1]:
                adaylar.append((self._her_yerde_degistir(kod, token, dogru), Bulgu(
                    satir, f"'{token}' → '{dogru}'",
                    f"'{hata_adi}' tanımlı değil; içe aktarılan modülde en yakın ad '{dogru}'.",
                    0.8, "ad")))
        return adaylar

    @staticmethod
    def _her_yerde_degistir(kod, eski, yeni):
        """Adı dosyanın tamamında (metin/yorum dışında) değiştirir; aynı yanlış ad
        birçok satırda geçiyorsa tek satırı düzeltmek hatayı gidermez."""
        sonuc = ad_degistir_kod(kod, eski, yeni)
        return None if sonuc == kod else sonuc

    @staticmethod
    def _daha_iyi(yeni, eski, kayma=0):
        """Aday, hatayı gerçekten ilerletti mi?

        kayma: adayın eklediği/sildiği satır sayısı (hata satırları buna göre
        karşılaştırılır; üste bir satır eklenince aynı hata bir alt satırda
        görünür ama bu ilerleme değildir)."""
        if yeni["durum"] in ("ok", "zaman_asimi"):
            return True
        if yeni["durum"] != "hata":
            return False
        modul_hatasi = ("ModuleNotFoundError", "ImportError")
        if yeni["tip"] in modul_hatasi and eski["tip"] not in modul_hatasi:
            return False  # kurulu olmayan bir modül eklenmiş
        satir = yeni["satir"] - kayma if yeni["satir"] > eski["satir"] else yeni["satir"]
        if satir > eski["satir"]:
            return True  # hata daha ileri bir satıra taşındı
        if satir == eski["satir"] and yeni["tip"] == eski["tip"] \
                and yeni["mesaj"] != eski["mesaj"]:
            return True  # aynı satırda sıradaki sorun (ör. ikinci tanımsız ad)
        # Aynı satırda BAŞKA türde hata: düzeltme yeni bir sorun yarattı.
        return False

    @staticmethod
    def _calisma_mesaji(sonuc):
        sozluk = {
            "NameError": "tanımsız bir ad kullanılıyor",
            "TypeError": "veri tipleri uyumsuz",
            "AttributeError": "olmayan bir özellik/metot çağrılıyor",
            "ZeroDivisionError": "sıfıra bölme",
            "IndexError": "liste sınırı aşıldı",
            "KeyError": "sözlükte olmayan anahtar",
            "ValueError": "geçersiz değer",
            "UnboundLocalError": "değişken atanmadan önce kullanılıyor",
            "ModuleNotFoundError": "modül bulunamadı",
            "RecursionError": "sonsuz özyineleme",
        }
        return sozluk.get(sonuc["tip"], sonuc["mesaj"][:120])

    def _zaman_asimi_bildir(self, kod):
        satir = None
        for i, s in enumerate(kod.split("\n"), 1):
            temiz = s.strip()
            if re.match(r"^(döngü|dongu|için|icin)\b", temiz):
                satir = i
                break
        # Güvenli kipte her girdi_al() "1" döndürür; çıkışı kullanıcının
        # yazacağı bir değere (ör. "q") bağlı döngüler bu yüzden hiç bitmez.
        # Bu durum bir hata değil, bilgi olarak bildirilir.
        # Yalnızca gövdesinde girdi okuyan bir döngü varsa: programın başka
        # bir yerinde girdi_al() geçmesi, gerçek bir sonsuz döngüyü gizlememeli.
        girdiye_bagli = False
        agac, _ = self._py_agaci(kod)
        if agac is not None:
            for d in ast.walk(agac):
                if isinstance(d, (ast.While, ast.For)) and any(
                        isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                        and x.func.id == "input"
                        for x in self._dongu_govdesi_dugumleri(d)):
                    girdiye_bagli = True
                    break
        if girdiye_bagli:
            self.dusun("⏳ Program kullanıcı girdisi bekleyen bir döngü içeriyor; "
                       "test girdileriyle süre sınırında bitmedi (bu normal olabilir).")
            self._uyari_ekle(
                satir, "Döngünün bitmesi kullanıcının gireceği değere bağlı",
                "Test sırasında her girdi '1' kabul edildi ve döngü bitmedi; "
                "çıkış koşulunun gerçekten sağlanabildiğinden emin olun.",
                seviye="bilgi", kategori="dongu")
            return
        self.dusun("⏳ Kod süre sınırında bitmedi; sonsuz döngü olabilir.")
        self._uyari_ekle(
            satir, f"Kod {self.zaman_asimi} saniyede bitmedi (sonsuz döngü ya da uzun işlem?)",
            "Döngü koşulunun bir noktada Yanlış olduğundan ya da 'kır' ile "
            "çıkıldığından emin olun.", seviye="uyari", kategori="dongu")

    def _calisma_ipucu(self, kod, sonuc):
        ipucu = None
        for desen, aciklama in self.core._CALISMA_IPUCLARI:
            if re.search(desen, sonuc["son"]):
                ipucu = aciklama
                break
        if sonuc["tip"] == "ModuleNotFoundError":
            mm = re.search(r"No module named '([^']+)'", sonuc["mesaj"])
            ad = mm.group(1).split(".")[0] if mm else "?"
            self._uyari_ekle(None, f"'{ad}' modülü kurulu değil",
                             f"Terminalde: pip yükle {ad}", seviye="hata", kategori="modul")
            self.dusun(f"📦 '{ad}' modülü kurulu değil; kurulum komutunu öneriyorum.")
            return
        if sonuc["tip"] == "IndexError":
            ipucu = "liste/metin sınırı aşıldı; indeks uzunluk(...) - 1'den büyük olamaz."
        self.dusun("🤔 Bu çalışma hatasını otomatik düzeltmek güvenli değil; ipucu bırakıyorum.")
        self._uyari_ekle(sonuc["satir"], f"{sonuc['tip']}: {sonuc['mesaj'][:160]}",
                         ipucu or "Hata satırındaki değerleri kontrol edin.",
                         seviye="hata", kategori="calisma")

    # --- çalışma zamanı aday üreticileri ------------------------------
    def _calisma_adaylari(self, kod, sonuc):
        tip, mesaj, satir = sonuc["tip"], sonuc["mesaj"], sonuc["satir"]
        adaylar = []
        try:
            if tip == "NameError":
                m = re.search(r"name '([^']+)' is not defined", mesaj)
                if m:
                    adaylar += self._nameerror_adaylari(kod, satir, m.group(1))
            elif tip == "UnboundLocalError":
                m = re.search(r"variable '([^']+)'", mesaj)
                if m:
                    adaylar += self._kuresel_adayi(kod, satir, m.group(1))
            elif tip == "TypeError":
                if "can only concatenate str" in mesaj or (
                        "unsupported operand" in mesaj and "str" in mesaj and "+" in mesaj):
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                    adaylar += self._metin_sarma_adayi(kod, satir)
                elif "not supported between instances of" in mesaj and "str" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                elif "unsupported operand" in mesaj and "str" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                m = re.search(r"(\w+)\(\) takes (\d+) positional arguments? but (\d+)", mesaj)
                if m and int(m.group(3)) == int(m.group(2)) + 1:
                    adaylar += self._kendisi_adayi(kod, m.group(1))
                if "'str' object cannot be interpreted as an integer" in mesaj \
                        or "can't multiply sequence by non-int" in mesaj \
                        or "indices must be integers or slices, not str" in mesaj \
                        or "must be real number, not str" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                if "'NoneType'" in mesaj:
                    adaylar += self._hiclik_adaylari(kod)
            elif tip == "AttributeError":
                m = re.search(r"'(\w+)' object has no attribute '(\w+)'", mesaj)
                if m and m.group(1) == "NoneType":
                    adaylar += self._hiclik_adaylari(kod)
                elif m:
                    adaylar += self._ozellik_adaylari(kod, satir, m.group(1), m.group(2))
            elif tip == "IndexError":
                adaylar += self._indeks_adaylari(kod, satir)
        except Exception:
            pass
        # Aynı kodu üreten adaylar bir kez denenir.
        tekil, gorulen = [], set()
        for aday, bulgu in adaylar:
            if aday is None:
                continue
            h = self._hash(aday)
            if h not in gorulen:
                gorulen.add(h)
                tekil.append((aday, bulgu))
        return tekil

    def _hiclik_adaylari(self, kod):
        """'NoneType' hataları çoğu zaman 'x = x.sona_ekle(...)' kaynaklıdır."""
        adaylar = []
        once = kod
        yeni = self._yerinde_metot_duzelt_sessiz(once)
        if yeni != once:
            adaylar.append((yeni, Bulgu(
                None, "Hiçlik döndüren metot sonucunun ataması kaldırıldı",
                "sona_ekle / sırala / ters_çevir gibi metotlar listeyi yerinde "
                "değiştirir ve Hiçlik döndürür; sonuçlarını değişkene atamak değeri siler.",
                0.9, "mantik")))
        return adaylar

    def _yerinde_metot_duzelt_sessiz(self, kod):
        for satir_no, girinti, ad, metot, ayni in reversed(self._yerinde_metot_satirlari(kod)):
            if not ayni:
                continue
            satir = kod.split("\n")[satir_no - 1]
            aday = self._satir_degistir(
                kod, satir_no, girinti + re.sub(rf"^\s*{re.escape(ad)}\s*=\s*", "", satir))
            if aday:
                kod = aday
        return kod

    def _indeks_adaylari(self, kod, satir):
        """Bir fazla sayma: aralık(uzunluk(x) + 1)  ->  aralık(uzunluk(x)),
        x[uzunluk(x)]  ->  x[uzunluk(x) - 1]  (hata satırı ve üstündeki döngüler)."""
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        sozluk = self._sozluk()
        aralik = "|".join(re.escape(k) for k, v in sozluk.items() if v == "range") or "aralık"
        uzunluk = "|".join(re.escape(k) for k, v in sozluk.items() if v == "len") or "uzunluk"
        adaylar = []
        # Hata satırı ve onu kapsayan döngü başlıkları.
        bakilacak = [satir]
        g = _girinti(satirlar[satir - 1])
        for i in range(satir - 2, max(-1, satir - 30), -1):
            s = satirlar[i]
            if s.strip() and _girinti(s) < g:
                bakilacak.append(i + 1)
                g = _girinti(s)
                if g == 0:
                    break
        for s_no in bakilacak:
            metin = satirlar[s_no - 1]
            yeni = re.sub(rf"((?:{aralik})\s*\(\s*(?:0\s*,\s*)?(?:{uzunluk})\s*\([^()]*\))\s*\+\s*1\s*\)",
                          r"\1)", metin)
            if yeni != metin:
                adaylar.append((self._satir_degistir(kod, s_no, yeni), Bulgu(
                    s_no, "Döngü sınırındaki '+ 1' kaldırıldı",
                    "Liste indeksleri 0'dan başlar; son eleman uzunluk - 1'dedir. "
                    "aralık(uzunluk(liste) + 1) bir fazla döner ve sınırı aşar.",
                    0.9, "indeks")))
            yeni = re.sub(rf"\b({ID})\s*\[\s*((?:{uzunluk})\s*\(\s*\1\s*\))\s*\]",
                          r"\1[\2 - 1]", metin)
            if yeni != metin:
                adaylar.append((self._satir_degistir(kod, s_no, yeni), Bulgu(
                    s_no, "Son eleman indeksi 'uzunluk - 1' yapıldı",
                    "x[uzunluk(x)] listenin bir sonrasına bakar; son eleman "
                    "x[uzunluk(x) - 1] (ya da x[-1]) ile alınır.", 0.9, "indeks")))
        return adaylar

    def _nameerror_adaylari(self, kod, satir, hata_adi):
        core = self.core
        satirlar = kod.split("\n")
        satir_metni = satirlar[satir - 1] if 0 < satir <= len(satirlar) else ""
        token, hedef = core._satirdaki_sorunlu_token(satir_metni, hata_adi)
        if token is None:
            tokenlar = re.findall(ID, maskele(satir_metni))
            yakin = core._en_yakin_eslesme(hata_adi, tokenlar, cutoff=0.65)
            if yakin:
                token = yakin[0]
                hedef = self._sozluk().get(token)
        if token is None:
            token = hata_adi
        # Kütüphaneye özgü adaylar önce (ör. Ursina'da 'app = Ursina()').
        try:
            adaylar = self._ursina_adaylari(kod, satir, token, hata_adi)
        except Exception:  # noqa: BLE001
            adaylar = []

        # a) Eksik içe aktarma.
        if token in MODUL_CEVIRILERI:
            adaylar.append((self._ice_aktarma_ekle(kod, token), Bulgu(
                satir, f"Eksik içe aktarma eklendi: içe_aktar {token}",
                f"'{token}' bir modül; kullanılmadan önce içe aktarılması gerekir.",
                0.95, "ice_aktarma")))

        # b) Modül fonksiyonunun modülsüz kullanımı (karekök -> matematik.karekök).
        if hedef:
            son = hedef.split(".")[-1]
            alt = core._py_ciplak_index().get(son) or core._py_ciplak_index().get(hata_adi)
            if alt and not self._modul_var_mi(alt[0]):
                alt = None
            if alt:
                modul_tr, metot_tr = alt
                yeni = re.sub(rf"(?<![\w.]){re.escape(token)}\b", f"{modul_tr}.{metot_tr}",
                              satir_metni, count=1)
                aday = self._satir_degistir(kod, satir, yeni)
                if aday:
                    aday = self._ice_aktarma_ekle(aday, modul_tr) or aday
                    adaylar.append((aday, Bulgu(
                        satir, f"'{token}' → '{modul_tr}.{metot_tr}' (+ içe_aktar {modul_tr})",
                        f"'{token}' '{modul_tr}' modülünün bir fonksiyonu; modül adıyla "
                        f"çağrılmalı ve modül içe aktarılmalıdır.", 0.9, "ice_aktarma")))

        # c) Yazım hatası: tanımlı adlara / TürKod komutlarına en yakın ad.
        tanimlar = self._tanimlar(kod)
        params = set(re.findall(rf"fonksiyon\s+{ID}\s*\(([^)]*)\)", kod))
        for p in params:
            tanimlar |= set(re.findall(ID, p))
        oneriler = core._en_yakin_eslesme(token, sorted(tanimlar - {token}), cutoff=0.72)
        if not oneriler:
            komutlar = [k for k in self._sozluk() if len(k) > 2]
            oneriler = core._en_yakin_eslesme(token, komutlar, cutoff=0.8)
        for dogru in oneriler[:1]:
            aday = self._satir_degistir(kod, satir, ad_degistir(satir_metni, token, dogru))
            adaylar.append((aday, Bulgu(
                satir, f"Tanımsız '{token}' → '{dogru}'",
                f"'{token}' hiçbir yerde tanımlı değil; büyük olasılıkla '{dogru}' "
                f"yazılmak istendi (benzerlik %{int(difflib.SequenceMatcher(None, _normalize(token), _normalize(dogru)).ratio() * 100)}).",
                0.82, "ad")))

        # d) Tırnaksız metin: yazdır(merhaba) -> yazdır("merhaba")
        if not oneriler and token not in tanimlar:
            m = re.search(rf"(\(\s*){re.escape(token)}(\s*\))", satir_metni)
            if m and re.search(r"(yazdır|yazdir)\s*\(\s*" + re.escape(token), satir_metni):
                yeni = satir_metni[:m.start()] + m.group(1) + f'"{token}"' + m.group(2) + satir_metni[m.end():]
                adaylar.append((self._satir_degistir(kod, satir, yeni), Bulgu(
                    satir, f"'{token}' metin olarak tırnağa alındı",
                    "Tanımlı olmayan bu kelime büyük olasılıkla ekrana yazdırılmak "
                    "istenen bir metin; metinler tırnak içinde yazılır.", 0.7, "ad")))

        # e) Tanımlanmadan önce kullanım: ileride atanıyorsa bildir.
        sonra = re.search(rf"^[ \t]*{re.escape(token)}\s*=(?!=)", "\n".join(satirlar[satir:]), re.M)
        if sonra and not adaylar:
            ileri = satir + "\n".join(satirlar[satir:])[:sonra.start()].count("\n") + 1
            self._uyari_ekle(satir, f"'{token}' tanımlanmadan önce kullanılıyor",
                             f"'{token}' ancak satır {ileri}'de tanımlanıyor; tanımı "
                             f"kullanımdan önceye taşıyın.", seviye="hata", kategori="ad")
        return adaylar

    def _kuresel_adayi(self, kod, satir, ad):
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        g = _girinti(satirlar[satir - 1])
        baslik = None
        for i in range(satir - 2, -1, -1):
            s = satirlar[i]
            if s.strip() and _girinti(s) < g and re.match(r"^\s*fonksiyon\b", s):
                baslik = i
                break
            if s.strip() and _girinti(s) == 0:
                break
        if baslik is None:
            return []
        if not re.search(rf"^{re.escape(ad)}\s*=(?!=)", kod, re.M):
            return []
        govde_g = None
        for s in satirlar[baslik + 1:]:
            if s.strip():
                govde_g = _girinti(s)
                break
        if govde_g is None:
            return []
        kopya = list(satirlar)
        kuresel = _tr("global", "küresel")
        kopya.insert(baslik + 1, " " * govde_g + f"{kuresel} {ad}")
        return [("\n".join(kopya), Bulgu(
            baslik + 2, f"'{kuresel} {ad}' eklendi",
            f"Fonksiyon, dışarıda tanımlı '{ad}' değişkenini değiştiriyor. "
            f"Python bunu yeni bir yerel değişken sanar; '{kuresel}' ile dıştaki "
            f"değişkenin kullanılacağı belirtilmelidir.", 0.88, "kapsam"))]

    def _girdi_sarma_adaylari(self, kod, satir):
        """Hata satırında, girdi_al() ile okunmuş ve sayıya çevrilmemiş
        değişkenlerin atamalarını tamsayı(...) ile sarar."""
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        adlar = set(re.findall(ID, maskele(satirlar[satir - 1])))
        sozluk = self._sozluk()
        girdi_kelimeleri = [k for k, v in sozluk.items() if v == "input"] or ["girdi_al"]
        gk = "|".join(re.escape(k) for k in girdi_kelimeleri)
        adaylar = []
        yeni = kod
        sarilan = []
        maskeli = maskele(kod).split("\n")
        for i, s in enumerate(maskeli, 1):
            m = re.match(rf"^\s*({ID})\s*=\s*(?:{gk})\s*\(", s)
            if m and m.group(1) in adlar:
                sonraki = self._cagriyi_sar(yeni, i, "input", _tr("int", "tamsayı"), sozluk)
                if sonraki:
                    yeni = sonraki
                    sarilan.append((i, m.group(1)))
        if sarilan:
            adlar_metin = ", ".join(f"'{a}'" for _, a in sarilan)
            adaylar.append((yeni, Bulgu(
                sarilan[0][0], f"{adlar_metin} girdisi tamsayıya çevrildi",
                "girdi_al() metin döndürür; metin ile sayı arasında işlem / "
                "karşılaştırma yapılamaz.", 0.86, "tip")))
        return adaylar

    def _metin_sarma_adayi(self, kod, satir):
        """"Yaş: " + yaş   ->   "Yaş: " + metin(yaş)"""
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        satir_metni = satirlar[satir - 1]
        maskeli = maskele(satir_metni)
        str_lit = r"[rRbBfFuU]{0,2}(?:\"[^\"\n]*\"|'[^'\n]*')"
        operand = rf"(?<![\w.]){ID}(?:\[[^\[\]]*\])?(?![\w(.\[])"
        if not re.search(str_lit, maskeli) or "+" not in maskeli:
            return []
        metin_kelime = _tr("str", "metin")
        araliklar = set()
        for m in re.finditer(rf"({str_lit}|\))\s*\+\s*({operand})", maskeli):
            araliklar.add(m.span(2))
        for m in re.finditer(rf"({operand})\s*\+\s*(?={str_lit})", maskeli):
            araliklar.add(m.span(1))
        # Zincir: "a" + ad + yaş  -> zincirdeki tüm adlar
        for zincir in re.finditer(rf"(?:(?:{str_lit}|{operand})\s*\+\s*)+(?:{str_lit}|{operand})", maskeli):
            if re.search(str_lit, zincir.group(0)):
                for m in re.finditer(operand, zincir.group(0)):
                    a = zincir.start() + m.start()
                    araliklar.add((a, a + len(m.group(0))))
        # "Seneye " + (yas + 1)  ->  "Seneye " + metin(yas + 1)
        parantezli = []
        for m in re.finditer(rf"(?:{str_lit})\s*\+\s*(\()", maskeli):
            ac = m.start(1)
            kapa = _eslesen_kapanis(maskeli, ac)
            if kapa > ac:
                parantezli.append(ac)
        tanimlar_str = set()
        for mm in re.finditer(rf"^[ \t]*({ID})\s*=\s*{str_lit}\s*$", maskele(kod), re.M):
            tanimlar_str.add(mm.group(1))
        anahtar = set(_keyword_words) | {"Doğru", "Yanlış", "Hiçlik"}
        secilen = []
        for a, b in sorted(araliklar):
            ad = maskeli[a:b]
            kok = re.match(ID, ad).group(0)
            if kok in tanimlar_str or kok in anahtar or kok == metin_kelime:
                continue
            if any(a < y and x < b for x, y in secilen):
                continue
            if any(p < a and b <= _eslesen_kapanis(maskeli, p) for p in parantezli):
                continue  # sarılacak parantezin içinde
            secilen.append((a, b))
        if not secilen and not parantezli:
            return []
        yeni = satir_metni
        # Sağdan sola: önce eklenen metin soldaki konumları kaydırmaz.
        islemler = [(a, "ad", b) for a, b in secilen] + [(a, "parantez", None) for a in parantezli]
        for a, tur, b in sorted(islemler, reverse=True):
            if tur == "parantez":
                yeni = yeni[:a] + metin_kelime + yeni[a:]
            else:
                yeni = yeni[:a] + f"{metin_kelime}(" + yeni[a:b] + ")" + yeni[b:]
        secilen = secilen or [(a, _eslesen_kapanis(maskeli, a) + 1) for a in parantezli]
        adlar = ", ".join(f"'{satir_metni[a:b]}'" for a, b in secilen)
        return [(self._satir_degistir(kod, satir, yeni), Bulgu(
            satir, f"{adlar} {metin_kelime}(...) ile metne çevrildi",
            "Metin ile sayı '+' ile birleştirilemez; sayı önce metne "
            f"çevrilmelidir ({metin_kelime}(sayı)).", 0.87, "tip"))]

    def _kendisi_adayi(self, kod, fonk_adi):
        satirlar = kod.split("\n")
        ilk_paramlar = re.findall(r"^\s+fonksiyon\s+\w+\s*\(\s*(\w+)", kod, re.M)
        varsayilan = _tr("self", "kendisi")
        kelime = max(set(ilk_paramlar), key=ilk_paramlar.count) if ilk_paramlar else varsayilan
        if kelime not in (varsayilan, "kendi", "self", "kendisi"):
            kelime = varsayilan
        for i, s in enumerate(satirlar):
            m = re.match(rf"^(\s+fonksiyon\s+{re.escape(fonk_adi)}\s*\()(\s*)(\)?)(.*)$", s)
            if not m:
                continue
            if m.group(3):
                yeni = m.group(1) + kelime + ")" + m.group(4)
            else:
                yeni = m.group(1) + kelime + ", " + s[len(m.group(1)) + len(m.group(2)):]
            kopya = list(satirlar)
            kopya[i] = yeni
            return [("\n".join(kopya), Bulgu(
                i + 1, f"'{fonk_adi}' metoduna '{kelime}' parametresi eklendi",
                f"Sınıf içindeki metotlar, nesnenin kendisini ilk parametre olarak "
                f"('{kelime}') alır; eksik olduğunda 'takes 0 positional arguments "
                f"but 1 was given' hatası oluşur.", 0.9, "sinif"))]
        return []

    def _ozellik_adaylari(self, kod, satir, tip_adi, ozellik):
        tipler = {"list": list, "str": str, "dict": dict, "set": set, "tuple": tuple,
                  "int": int, "float": float}
        tip = tipler.get(tip_adi)
        if tip is None:
            return []
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        satir_metni = satirlar[satir - 1]
        sozluk = self._sozluk()
        gecerli = {a for a in dir(tip) if not a.startswith("_")}
        # Satırdaki ".kelime" — Python karşılığı hatalı özellik olan.
        token = None
        for m in re.finditer(rf"\.\s*({ID})", maskele(satir_metni)):
            t = m.group(1)
            if sozluk.get(t, t) == ozellik or t == ozellik:
                token = t
                break
        if token is None:
            return []
        adaylar_tr = {tr: py for tr, py in sozluk.items() if py in gecerli and "." not in py}
        for py in gecerli:
            adaylar_tr.setdefault(py, py)
        puanlar = []
        nt = _normalize(token)
        for tr, py in adaylar_tr.items():
            ntr = _normalize(tr)
            oran = max(difflib.SequenceMatcher(None, nt, ntr).ratio(),
                       difflib.SequenceMatcher(None, ozellik.lower(), py.lower()).ratio())
            if nt and (nt in ntr.split("_") or ntr.endswith("_" + nt)):
                oran = max(oran, 0.8)
            puanlar.append((oran, tr.isascii(), tr, py))
        puanlar.sort(key=lambda x: (-x[0], x[1]))
        adaylar = []
        for oran, _, tr, py in puanlar[:3]:
            if oran < 0.6:
                break
            yeni = re.sub(rf"\.\s*{re.escape(token)}\b", f".{tr}", satir_metni, count=1)
            tip_tr = _tr(tip_adi, tip_adi)
            adaylar.append((self._satir_degistir(kod, satir, yeni), Bulgu(
                satir, f"'.{token}' → '.{tr}'",
                f"{tip_tr} türünde '{token}' diye bir metot yok; en yakın karşılık "
                f"'{tr}' ({py}).", round(0.6 + 0.35 * oran, 2), "metot")))
        return adaylar

    # ------------------------------------------------------------------
    # 6. İnceleme (otomatik düzeltilmeyen durumlar)
    # ------------------------------------------------------------------
    def _inceleme_asamasi(self, kod):
        self.dusun("🔎 Son inceleme: döngüler, fonksiyon çağrıları, ulaşılamayan kod…")
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return
        try:
            self._ast_incele(agac, kod)
        except Exception:
            pass
        try:
            for u in self.core._golgeleme_uyarilari(kod):
                self._uyari_ekle(u.get("satir"), u.get("mesaj", "").split(": ", 1)[-1],
                                 "Farklı bir değişken adı kullanın; aksi hâlde bu "
                                 "komut dosyada çalışmaz.", seviye="uyari", kategori="ad")
        except Exception:
            pass

    def _ast_incele(self, agac, kod):
        fonksiyonlar = {}
        for d in ast.walk(agac):
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fonksiyonlar.setdefault(d.name, []).append(d)

        # Aynı ad ile iki kez tanımlanan fonksiyonlar (modül düzeyi).
        gorulen = {}
        for d in agac.body:
            if isinstance(d, (ast.FunctionDef, ast.ClassDef)):
                if d.name in gorulen:
                    self._uyari_ekle(d.lineno, f"'{d.name}' ikinci kez tanımlanıyor",
                                     f"Satır {gorulen[d.name]}'deki tanım geçersiz kalır.",
                                     seviye="uyari", kategori="tanim")
                gorulen[d.name] = d.lineno

        for d in ast.walk(agac):
            # Ulaşılamayan kod.
            for alan in ("body", "orelse", "finalbody"):
                govde = getattr(d, alan, None)
                if not isinstance(govde, list):
                    continue
                for i, ifade in enumerate(govde[:-1]):
                    if isinstance(ifade, (ast.Return, ast.Break, ast.Continue, ast.Raise)):
                        sonraki = govde[i + 1]
                        komut = {ast.Return: "döndür", ast.Break: "kır",
                                 ast.Continue: "devam_et", ast.Raise: "hata_fırlat"}[type(ifade)]
                        self._uyari_ekle(sonraki.lineno, "Bu satıra hiçbir zaman ulaşılamaz",
                                         f"Hemen önündeki '{komut}' bloğu sonlandırıyor.",
                                         seviye="uyari", kategori="akis")
                        break

            # Sonsuz döngü riski.
            if isinstance(d, ast.While):
                # çık()/exit()/sys.exit() da döngüden (programdan) çıkar.
                cikis = any(
                    isinstance(x, (ast.Break, ast.Return, ast.Raise))
                    or (isinstance(x, ast.Call) and (
                        (isinstance(x.func, ast.Name) and x.func.id in ("exit", "quit"))
                        or (isinstance(x.func, ast.Attribute) and x.func.attr == "exit")))
                    for x in self._dongu_govdesi_dugumleri(d))
                sabit_dogru = isinstance(d.test, ast.Constant) and bool(d.test.value)
                if sabit_dogru and not cikis and not self._cagri_var(d):
                    self._uyari_ekle(d.lineno, "'döngü Doğru' içinde çıkış yok (sonsuz döngü)",
                                     "Döngüden çıkmak için bir koşulla 'kır' kullanın.",
                                     seviye="hata", kategori="dongu")
                elif not sabit_dogru and not cikis:
                    adlar = {n.id for n in ast.walk(d.test) if isinstance(n, ast.Name)}
                    degisen = set()
                    for x in self._dongu_govdesi_dugumleri(d):
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                            degisen.add(x.id)
                        elif isinstance(x, ast.AugAssign) and isinstance(x.target, ast.Name):
                            degisen.add(x.target.id)
                    cagri = self._cagri_var(d)
                    if adlar and not (adlar & degisen) and not cagri:
                        liste = ", ".join(sorted(adlar))
                        self._uyari_ekle(d.lineno, f"Döngü koşulundaki {liste} döngü içinde hiç değişmiyor",
                                         "Koşul hiç Yanlış olmayacağından döngü sonsuza kadar "
                                         "sürebilir; döngü içinde değişkeni güncelleyin "
                                         "(ör. sayaç = sayaç + 1).", seviye="hata", kategori="dongu")

            # Kullanıcı fonksiyonlarına yanlış sayıda argüman.
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) \
                    and d.func.id in fonksiyonlar and len(fonksiyonlar[d.func.id]) == 1:
                f = fonksiyonlar[d.func.id][0]
                a = f.args
                if a.vararg or a.kwarg or any(isinstance(x, ast.Starred) for x in d.args) or d.keywords:
                    continue
                toplam = len(a.posonlyargs) + len(a.args)
                en_az = toplam - len(a.defaults)
                verilen = len(d.args)
                if not (en_az <= verilen <= toplam):
                    beklenen = str(toplam) if en_az == toplam else f"{en_az}-{toplam}"
                    self._uyari_ekle(d.lineno,
                                     f"'{d.func.id}' {beklenen} argüman bekliyor, {verilen} verilmiş",
                                     f"Tanım satır {f.lineno}: argüman sayısını tanımla eşleştirin.",
                                     seviye="hata", kategori="cagri")

            # Sıfıra bölme.
            # ("%d" % 0 bir metin biçimlendirmesidir, bölme değil.)
            metin_bicim = isinstance(d, ast.BinOp) and isinstance(d.op, ast.Mod) and (
                isinstance(d.left, (ast.JoinedStr,))
                or (isinstance(d.left, ast.Constant) and isinstance(d.left.value, str)))
            if isinstance(d, ast.BinOp) and isinstance(d.op, (ast.Div, ast.FloorDiv, ast.Mod)) \
                    and not metin_bicim \
                    and isinstance(d.right, ast.Constant) and d.right.value == 0 \
                    and not isinstance(d.right.value, bool):
                self._uyari_ekle(d.lineno, "Sıfıra bölme", "Bölen 0 olamaz.",
                                 seviye="hata", kategori="matematik")

            # Hiçlik / Doğru ile '==' karşılaştırması.
            if isinstance(d, ast.Compare) and len(d.ops) == 1 and isinstance(d.ops[0], (ast.Eq, ast.NotEq)):
                sag = d.comparators[0]
                if isinstance(sag, ast.Constant) and sag.value is None:
                    self._uyari_ekle(d.lineno, "Hiçlik ile '==' karşılaştırması",
                                     "Hiçlik kontrolü için 'aynı_mı Hiçlik' kullanmak daha doğrudur.",
                                     seviye="bilgi", kategori="stil")
                elif isinstance(sag, ast.Constant) and sag.value is True and isinstance(d.ops[0], ast.Eq):
                    self._uyari_ekle(d.lineno, "'== Doğru' gereksiz",
                                     "'eğer x == Doğru:' yerine kısaca 'eğer x:' yazılabilir.",
                                     seviye="bilgi", kategori="stil")

            # Kendine atama.
            if isinstance(d, ast.Assign) and len(d.targets) == 1 \
                    and isinstance(d.targets[0], ast.Name) and isinstance(d.value, ast.Name) \
                    and d.targets[0].id == d.value.id:
                self._uyari_ekle(d.lineno, f"'{d.value.id} = {d.value.id}' hiçbir şey yapmıyor",
                                 seviye="bilgi", kategori="stil")

            # Değiştirilebilir varsayılan argüman.
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for v in d.args.defaults:
                    if isinstance(v, (ast.List, ast.Dict, ast.Set)):
                        self._uyari_ekle(d.lineno,
                                         f"'{d.name}' içinde liste/sözlük varsayılan değer",
                                         "Bu değer tüm çağrılarda paylaşılır; Hiçlik verip "
                                         "fonksiyon içinde oluşturun.", seviye="bilgi",
                                         kategori="stil")
                self._kullanilmayanlar(d)

    @staticmethod
    def _dongu_govdesi_dugumleri(dongu):
        for ifade in dongu.body + dongu.orelse:
            yield from ast.walk(ifade)

    @staticmethod
    def _cagri_var(dongu):
        """Döngü gövdesinde koşulu dolaylı değiştirebilecek bir çağrı var mı?
        Yerleşik fonksiyonlar (yazdır, uzunluk …) değişken değiştiremez;
        kullanıcı fonksiyonları ve metotlar (liste.çıkar() …) değiştirebilir."""
        for ifade in dongu.body:
            for x in ast.walk(ifade):
                if isinstance(x, ast.Call):
                    if isinstance(x.func, ast.Name) and hasattr(builtins, x.func.id) \
                            and x.func.id not in ("exec", "eval", "input"):
                        continue
                    return True
        return False

    def _kullanilmayanlar(self, fonk):
        atanan = {}
        okunan = set()
        kuresel = set()
        for x in ast.walk(fonk):
            if isinstance(x, (ast.Global, ast.Nonlocal)):
                kuresel.update(x.names)
            elif isinstance(x, ast.Name):
                if isinstance(x.ctx, ast.Store):
                    atanan.setdefault(x.id, x.lineno)
                else:
                    okunan.add(x.id)
            elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x is not fonk:
                okunan.update(n.id for n in ast.walk(x) if isinstance(n, ast.Name))
        for ad, satir in atanan.items():
            if ad not in okunan and ad not in kuresel and not ad.startswith("_"):
                self._uyari_ekle(satir, f"'{ad}' değişkenine değer atanıyor ama hiç kullanılmıyor",
                                 "Gereksizse silin; değilse adı doğru yazdığınızdan emin olun.",
                                 seviye="bilgi", kategori="stil")

    # ------------------------------------------------------------------
    # 7. Son doğrulama + rapor
    # ------------------------------------------------------------------
    def _son_dogrulama(self, kod):
        self.dusun("🧾 Son doğrulamayı yapıyorum…")
        durum = self._sozdizimi_durumu(kod)
        if durum is not None:
            return {"durum": "sozdizimi",
                    "metin": f"⚠️ Kalan sözdizimi hatası: Satır {durum['satir']} "
                             f"({self._mesaj_turkce(durum['mesaj'])})"}
        sonuc = self._calistir(kod)
        if sonuc["durum"] == "ok" and sonuc.get("pencere_suresi"):
            return {"durum": "ok",
                    "metin": f"✅ Doğrulandı: program açıldı ve {sonuc['pencere_suresi']} saniye "
                             "hatasız çalıştı (pencere deneme sırasında gizlendi)."}
        if sonuc["durum"] == "ok":
            return {"durum": "ok", "metin": "✅ Doğrulandı: kod hatasız çalıştı."}
        if sonuc["durum"] == "zaman_asimi":
            return {"durum": "zaman_asimi",
                    "metin": f"⏳ Son doğrulama {self.zaman_asimi} saniyelik süre sınırına "
                             "takıldı (sonsuz döngü ya da kullanıcı girdisi bekleyen döngü?)."}
        if sonuc["durum"] == "hata":
            return {"durum": "hata",
                    "metin": f"⚠️ Kalan hata: Satır {sonuc['satir']}: {sonuc['son'][:200]}"}
        if sonuc["durum"] == "atlandi" and sonuc.get("arayuz") \
                and self._statik_tanimsiz(kod) == []:
            return {"durum": "ok",
                    "metin": "✅ Doğrulandı (çalıştırmadan): sözdizimi temiz, tanımsız ad yok."}
        if sonuc["durum"] == "atlandi":
            neden = ("Program gerçek fare/klavyeyi yönettiği için" if sonuc.get("denetim") else
                     "Program pencere/grafik arayüzü açtığı için" if sonuc.get("arayuz") else
                     "Python bulunamadığı için")
            return {"durum": "atlandi",
                    "metin": f"ℹ️ {neden} yalnızca sözdizimi doğrulandı."}
        return {"durum": sonuc["durum"], "metin": ""}

    def _rapor(self, orijinal, kod, son, sure):
        degisti = kod != orijinal
        hata_uyari = sum(1 for u in self.uyarilar if u.seviye == "hata")
        normal_uyari = sum(1 for u in self.uyarilar if u.seviye == "uyari")
        bilgi = sum(1 for u in self.uyarilar if u.seviye == "bilgi")

        saglik = 100
        if son["durum"] in ("sozdizimi", "hata"):
            saglik -= 35
        elif son["durum"] == "zaman_asimi":
            saglik -= 15
        saglik -= 12 * hata_uyari + 5 * normal_uyari + 1 * bilgi
        saglik = max(0, min(100, saglik))

        if self.duzeltmeler:
            guven = sum(b.guven for b in self.duzeltmeler) / len(self.duzeltmeler)
            if son["durum"] == "ok":
                guven = min(0.99, guven + 0.08)
            elif son["durum"] in ("sozdizimi", "hata"):
                guven -= 0.15
            guven = int(round(max(0.0, min(1.0, guven)) * 100))
        else:
            guven = 100 if son["durum"] == "ok" else 0

        n = len(self.duzeltmeler)
        if n and son["durum"] == "ok":
            ozet = f"{n} sorun buldum ve düzelttim; kod artık hatasız çalışıyor."
        elif n:
            ozet = f"{n} sorunu düzelttim ancak hâlâ dikkat gerektiren bir sorun var."
        elif son["durum"] == "ok" and not hata_uyari:
            ozet = "Kodda düzeltilmesi gereken bir hata bulamadım. 👍"
        elif son["durum"] == "ok":
            ozet = "Kod çalışıyor ama gözden geçirmeniz gereken noktalar var."
        else:
            ozet = "Hatayı güvenle otomatik düzeltemedim; nedenini ve önerimi aşağıda bulabilirsiniz."
        if self.uyarilar:
            ozet += f" {len(self.uyarilar)} öneri/uyarı var."

        self.dusun(f"🏁 Bitti: {ozet}", bekle=False)

        seviye_sira = {"hata": 0, "uyari": 1, "bilgi": 2}
        uyarilar = sorted(self.uyarilar,
                          key=lambda u: (seviye_sira.get(u.seviye, 3), u.satir or 10 ** 9))

        degisiklik_metinleri = [b.metin() for b in self.duzeltmeler]
        degisiklik_metinleri += [
            f"• {('Satır ' + str(u.satir) + ': ') if u.satir else ''}{u.baslik}"
            + (f"\n  İpucu: {u.oneri}" if u.oneri else "")
            for u in uyarilar if u.seviye in ("hata", "uyari")
        ]

        return {
            "ok": True,
            "degisiklik": degisti or bool(degisiklik_metinleri),
            "kod": kod,
            "degisiklikler": degisiklik_metinleri,
            "son_mesaj": "",
            "dogrulama": son["metin"],
            "diff": self.core._diff_olustur(orijinal, kod) if degisti else "",
            "mesaj": ozet,
            "rapor": {
                "ozet": ozet,
                "durum": son["durum"],
                "saglik": saglik,
                "guven": guven,
                "sure_ms": int(sure * 1000),
                "calistirma": self.calistirma_sayisi,
                "duzeltmeler": [b.sozluk() for b in self.duzeltmeler],
                "uyarilar": [u.sozluk() for u in uyarilar],
                "dusunceler": list(self.dusunceler),
            },
        }


_METIN_YORUM_BOL = re.compile(
    r'([rRbBfFuU]{0,2}"""[\s\S]*?"""|[rRbBfFuU]{0,2}\'\'\'[\s\S]*?\'\'\''
    r'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*)')


def ad_degistir_kod(kod, eski, yeni):
    """Kodun tamamında metin/yorum DIŞINDAKİ 'eski' adlarını değiştirir.
    Satır satır çalışan ad_degistir çok satırlı (\"\"\"...\"\"\") metinleri
    göremiyor, içlerindeki kelimeleri de değiştiriyordu."""
    parcalar = _METIN_YORUM_BOL.split(kod)
    desen = re.compile(rf"(?<![\w.]){re.escape(eski)}(?![\w])")
    for i in range(0, len(parcalar), 2):
        parcalar[i] = desen.sub(lambda _m: yeni, parcalar[i])
    return "".join(parcalar)


def ad_degistir(satir, eski, yeni):
    """Satırda metin/yorum DIŞINDAKİ 'eski' adlarını 'yeni' ile değiştirir."""
    parcalar = re.split(r"(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|#.*$)", satir)
    for i in range(0, len(parcalar), 2):
        parcalar[i] = re.sub(rf"(?<![\w.]){re.escape(eski)}(?![\w])", yeni, parcalar[i])
    return "".join(parcalar)
