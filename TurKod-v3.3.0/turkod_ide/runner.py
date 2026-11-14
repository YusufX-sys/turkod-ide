"""Calistirma sablonu."""


RUNNER_ORTAK = r'''# -- coding: utf-8 --
import os
import traceback
import sys
import re
import warnings

# Kütüphanelerin KENDİ kaynak kodundaki derleme uyarıları (ör. Ursina'nın
# mesh_importer.py dosyasındaki "invalid escape sequence '\P'") kullanıcıyla
# ilgisizdir ama program başında kullanıcının hatası gibi görünüyordu.
# Derleme uyarılarında "module" dosya yoludur; yalnızca ".*klasör.*" biçimi
# eşleşiyor (ters eğik çizgili desenler eşleşmiyor). Kullanıcının kendi
# kodundaki uyarılar etkilenmez.
for _kutuphane_klasoru in (r".*site-packages.*", r".*pip_packages.*"):
    warnings.filterwarnings("ignore", category=SyntaxWarning, module=_kutuphane_klasoru)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=_kutuphane_klasoru)


# Ursina FirstPersonController (birinci_şahıs_denetleyici) düşme düzeltmesi.
# Yerçekimi adımı "min(air_time, mesafe) * time.dt * 100" olduğundan tek bir
# uzun karede (program açılırken ya da bilgisayar o an meşgulken dt >~ 0.05 sn)
# oyuncu zemini geçecek kadar aşağı iner; aşağı atılan ışın artık zemini
# görmediği için oyuncu yerin altında takılı kalır (Python'da da olur, ama
# makine yavaşladıkça sıklaşır). Düzeltme: düşen oyuncunun bir önceki
# konumundan aşağı ışın atılır; arada bir zemin varsa oyuncu onun üstüne
# konur. Normal düşme/iniş davranışı değişmez.
def _tk_fpc_yamala(modul):
    sinif = getattr(modul, "FirstPersonController", None)
    if sinif is None or getattr(sinif, "_tk_yamali", False):
        return
    asil_update = sinif.update

    def update(self):
        onceki_y = self.y
        asil_update(self)
        try:
            if not getattr(self, "gravity", 0) or self.y >= onceki_y - 0.01:
                return
            from ursina import raycast, Vec3
            yukseklik = getattr(self, "height", 2)
            ray = raycast(
                Vec3(self.world_x, onceki_y + yukseklik, self.world_z), Vec3(0, -1, 0),
                distance=(onceki_y - self.y) + yukseklik,
                traverse_target=getattr(self, "traverse_target", None) or modul.scene,
                ignore=getattr(self, "ignore_list", (self,)))
            if ray.hit and ray.world_point[1] > self.y + 0.001:
                self.y = ray.world_point[1]
                if hasattr(self, "land"):
                    self.land()
        except Exception:
            pass

    sinif.update = update
    sinif._tk_yamali = True


# Tırnak içindeki Türkçe seçenek değerleri: kalem_rengi("mavi"),
# şekil("kaplumbağa"), hız("en_hızlı"), arkaplan_rengi="açık mavi",
# kabartma="çökük" ... Metin içleri çevrilmediğinden bunlar kütüphaneye
# olduğu gibi gidip "bad color string" / "unknown shape" hatası veriyordu.
# Tablolar deger_sozlugu.py'den gelir (runner.py modül sonunda yazılır).
_TK_DEGERLER = {}


_TK_ASCII = str.maketrans("çğıöşü", "cgiosu")


def _tk_deger(tablo, deger):
    if not isinstance(deger, str):
        return deger
    ad = re.sub(r"[\s\-]+", "_", deger.strip().replace("İ", "i").replace("I", "ı").lower())
    if ad in tablo:
        return tablo[ad]
    # Türkçe harfsiz büyük yazım ("MAVI", "SIYAH", "ACIK MAVI"): büyük I
    # Türkçede ı'ya küçülür ("mavı"); eskiden bulunamıyor, Tk "bad color"
    # hatası veriyordu. Aksansız (ASCII) biçim de denenir (tablolarda var).
    return tablo.get(ad.translate(_TK_ASCII), deger)


def _tk_yazi_tipi(font):
    # ("Arial", 16, "kalın") / "Arial 12 kalın italik": aile adına dokunulmaz.
    bicim = _TK_DEGERLER.get("bicim", {})
    if isinstance(font, tuple) and len(font) > 2:
        return font[:2] + tuple(
            " ".join(_tk_deger(bicim, p) for p in f.split()) if isinstance(f, str) else f
            for f in font[2:])
    if isinstance(font, str) and " " in font.strip() and "{" not in font:
        ilk, *kalan = font.split()
        return " ".join([ilk] + [_tk_deger(bicim, p) for p in kalan])
    return font


def _tk_turtle_yamala(modul):
    ekran = getattr(modul, "TurtleScreen", None)
    if ekran is None or getattr(ekran, "_tk_yamali", False):
        return
    renk = _TK_DEGERLER.get("renk", {})
    asil = ekran._colorstr

    def _colorstr(self, color):
        if isinstance(color, tuple) and len(color) == 1 and isinstance(color[0], str):
            color = (_tk_deger(renk, color[0]),)
        elif isinstance(color, str):
            color = _tk_deger(renk, color)
        return asil(self, color)

    ekran._colorstr = _colorstr
    ekran._tk_yamali = True
    # Pencere başlığı ve görev çubuğu "Python Turtle Graphics" yazıyordu.
    # screen.title(...) ile verilen başlık yine geçerlidir.
    pencere = getattr(modul, "_Screen", None)
    if pencere is not None and getattr(pencere, "_title", None) == "Python Turtle Graphics":
        pencere._title = "TürKod Kaplumbağa"

    def sar(sinif, ad, yeni):
        asil_m = getattr(sinif, ad, None)
        if asil_m is not None:
            setattr(sinif, ad, yeni(asil_m))

    sekil = _TK_DEGERLER.get("sekil", {})
    hiz = _TK_DEGERLER.get("hiz", {})
    hiza = _TK_DEGERLER.get("hiza", {})
    tus = _TK_DEGERLER.get("tus", {})
    kip = _TK_DEGERLER.get("kip", {})
    kaplumbaga = getattr(modul, "RawTurtle", None)
    if kaplumbaga is not None:
        sar(kaplumbaga, "__init__", lambda a: lambda self, *ar, **kw: a(
            self, *ar, **({**kw, "shape": _tk_deger(sekil, kw["shape"])} if "shape" in kw else kw)))
        sar(kaplumbaga, "shape", lambda a: lambda self, name=None: a(self, _tk_deger(sekil, name)))
        sar(kaplumbaga, "speed", lambda a: lambda self, speed=None: a(self, _tk_deger(hiz, speed)))

        def write(a):
            # TürKod "hizala=" Tk'deki gibi justify'a çevrilir; kaplumbağada adı align.
            def yaz(self, arg, move=False, align="left", font=("Arial", 8, "normal"), **kw):
                if "justify" in kw:
                    align = kw.pop("justify")
                return a(self, arg, move, _tk_deger(hiza, align), _tk_yazi_tipi(font), **kw)
            return yaz
        sar(kaplumbaga, "write", write)
    sar(ekran, "mode", lambda a: lambda self, mode=None: a(self, _tk_deger(kip, mode)))
    taban = getattr(modul, "TurtleScreenBase", None)
    if taban is not None:
        sar(taban, "_onkeyrelease", lambda a: lambda self, fun, key: a(
            self, fun, tus.get(key.strip().lower(), key) if isinstance(key, str) else key))
        sar(taban, "_onkeypress", lambda a: lambda self, fun, key=None: a(
            self, fun, tus.get(key.strip().lower(), key) if isinstance(key, str) else key))


def _tk_tkinter_yamala(modul):
    try:
        _tk_tk_simgesi(modul)
    except Exception:
        pass
    misc = getattr(modul, "Misc", None)
    if misc is None or getattr(misc, "_tk_yamali", False):
        return
    secenekler = _TK_DEGERLER.get("tk", {})
    birlestir = modul._cnfmerge
    asil = misc._options

    def _options(self, cnf, kw=None):
        cnf = birlestir((cnf, kw)) if kw else birlestir(cnf)
        if isinstance(cnf, dict):
            yeni = None
            for k, v in cnf.items():
                if not isinstance(v, (str, tuple)):
                    continue
                anahtar = k[:-1] if k.endswith("_") else k
                if anahtar == "font":
                    d = _tk_yazi_tipi(v)
                elif isinstance(v, str) and anahtar in secenekler:
                    d = _tk_deger(secenekler[anahtar], v)
                else:
                    continue
                if d is not v:
                    if yeni is None:
                        yeni = dict(cnf)
                    yeni[k] = d
            if yeni is not None:
                cnf = yeni
        return asil(self, cnf)

    misc._options = _options
    misc._tk_yamali = True


def _tk_renk_ekle(tablo, donustur=lambda en, d: d):
    """Kütüphanenin kendi renk adları sözlüğüne Türkçe adları ekler
    (Pillow, pygame, matplotlib adları büyük/küçük harf duyarsız arar)."""
    for tr, en in _TK_DEGERLER.get("renk", {}).items():
        if en in tablo:
            for ad in (tr, tr.replace("_", " ")):
                tablo.setdefault(ad, donustur(en, tablo[en]))


def _tk_pil_yamala(modul):
    _tk_renk_ekle(modul.colormap)


def _tk_pygame_yamala(modul):
    _tk_renk_ekle(modul.THECOLORS)


def _tk_matplotlib_yamala(modul):
    tablo = modul.get_named_colors_mapping()
    for tr, en in _TK_DEGERLER.get("renk", {}).items():
        if en in tablo:
            for ad in (tr, tr.replace("_", " ")):
                if ad not in tablo:
                    tablo[ad] = tablo[en]


_TK_KULLANICI_SIMGESI = [False]   # pygame.display.set_icon çağrıldı mı


def _tk_simge_kullanilsin():
    """TürKod program simgesi verilsin mi? (Windows, IDE'den çalıştırma; EXE'de
    EXE'nin kendi simgesi kullanılır.)"""
    return (os.name == "nt" and not getattr(sys, "frozen", False)
            and bool(_TK_PROGRAM_IKONU) and os.path.isfile(_TK_PROGRAM_IKONU))


# Simge, kütüphaneye pencere OLUŞMADAN önce verilir. Sonradan (pencere
# olaylarıyla) konan simge bazı kütüphanelerde geç kalıyordu: Panda3D/ursina
# pencereyi açarken uzun süre Python'a sıra vermiyor, o arada görev
# çubuğunda bir saniyeden fazla Python simgesi görünüyordu.
def _tk_pygame_display_yamala(modul):
    asil = getattr(modul, "set_icon", None)
    if asil is None:
        return

    def set_icon(*a, **k):
        _TK_KULLANICI_SIMGESI[0] = True
        return asil(*a, **k)

    modul.set_icon = set_icon
    asil_set_mode = getattr(modul, "set_mode", None)
    if asil_set_mode is None:
        return

    def set_mode(*a, **k):
        # Program kendi simgesini vermediyse pencere TürKod simgesiyle açılır
        # (pygame'in kendi simgesi yerine). pygame .ico'yu okuyamaz: PNG.
        if not _TK_KULLANICI_SIMGESI[0] and _tk_simge_kullanilsin():
            try:
                import pygame.image
                asil(pygame.image.load(_TK_PROGRAM_IKONU[:-4] + ".png"))
                # Simge verildi: pencere olayları onu bir daha değiştirmesin.
                _TK_KULLANICI_SIMGESI[0] = True
            except Exception:
                pass
        return asil_set_mode(*a, **k)

    modul.set_mode = set_mode


def _tk_tk_simgesi(modul):
    """Tk() oluşturulur oluşturulmaz (pencere görünmeden) varsayılan simge
    verilir; program iconbitmap/iconphoto çağırırsa onunki geçerlidir."""
    tk = getattr(modul, "Tk", None)
    if tk is None or getattr(tk, "_tk_simgeli", False):
        return
    asil = tk.__init__

    def __init__(self, *a, **k):
        asil(self, *a, **k)
        if _tk_simge_kullanilsin():
            try:
                self.iconbitmap(default=_TK_PROGRAM_IKONU)
            except Exception:
                pass

    tk.__init__ = __init__
    tk._tk_simgeli = True


def _tk_ursina_yamala(modul):
    """Ursina varsayılan olarak 'textures/ursina.ico' göreli yolunu verir;
    bulunamayınca pencere simgesiz kalıyor, Windows python.exe simgesini
    koyuyordu. Program simge vermediyse TürKod simgesi verilir."""
    sinif = getattr(modul, "Ursina", None)
    if sinif is None or getattr(sinif, "_tk_simgeli", False):
        return
    asil = sinif.__init__

    def __init__(self, *a, **k):
        if len(a) < 2 and k.get("icon", "textures/ursina.ico") == "textures/ursina.ico" \
                and _tk_simge_kullanilsin():
            k["icon"] = _TK_PROGRAM_IKONU
        return asil(self, *a, **k)

    sinif.__init__ = __init__
    sinif._tk_simgeli = True


def _tk_panda3d_yamala(modul):
    """Panda3D'nin (ShowBase) açtığı pencerelerin varsayılan simgesi."""
    if _tk_simge_kullanilsin():
        try:
            modul.loadPrcFileData("", "icon-filename " + _TK_PROGRAM_IKONU)
        except Exception:
            pass


def _tk_ice_aktarma_yamalari_kur():
    import importlib.abc
    import importlib.util

    yamalar = {"ursina.prefabs.first_person_controller": _tk_fpc_yamala,
               "turtle": _tk_turtle_yamala,
               "tkinter": _tk_tkinter_yamala,
               "PIL.ImageColor": _tk_pil_yamala,
               "pygame.colordict": _tk_pygame_yamala,
               "pygame.display": _tk_pygame_display_yamala,
               "ursina.main": _tk_ursina_yamala,
               "panda3d.core": _tk_panda3d_yamala,
               "matplotlib.colors": _tk_matplotlib_yamala}

    class _Bulucu(importlib.abc.MetaPathFinder):
        def find_spec(self, ad, yol=None, hedef=None):
            yama = yamalar.get(ad)
            if yama is None:
                return None
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(ad)
            finally:
                if yamalar:
                    sys.meta_path.insert(0, self)
            if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
                return spec
            asil_exec = spec.loader.exec_module

            def exec_module(m):
                asil_exec(m)
                try:
                    yama(m)
                finally:
                    yamalar.pop(ad, None)
                    if not yamalar and self in sys.meta_path:
                        sys.meta_path.remove(self)

            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _Bulucu())


try:
    _tk_ice_aktarma_yamalari_kur()
except Exception:
    pass


# Programın pencereleri (kaplumbağa, tkinter, ursina, pygame ...) görev
# çubuğunda Python simgesiyle görünüyordu: program python.exe ile çalışır,
# kendi simgesi olmayan pencereye Windows python.exe'nin simgesini koyar.
# Programın kendi simgesi olmayan pencerelerine TürKod program simgesi
# verilir; programın kendisi bir simge koyarsa (iconbitmap, iconphoto,
# pygame.display.set_icon) o geçerlidir. Yol oneri_tablolarini_yerlestir
# ile doldurulur. EXE'de (frozen) EXE'nin kendi simgesi kullanılır.
_TK_PROGRAM_IKONU = None
def _tk_program_simgesi_kur():
    if os.name != "nt" or getattr(sys, "frozen", False) or not _TK_PROGRAM_IKONU \
            or not os.path.isfile(_TK_PROGRAM_IKONU):
        return
    import ctypes
    import threading
    import time
    from ctypes import wintypes
    u = ctypes.windll.user32
    try:
        # Görev çubuğunda python.exe ile değil, TürKod programı olarak gruplanır.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TurKod.CalisanProgram")
    except Exception:
        pass
    u.LoadImageW.restype = ctypes.c_void_p
    u.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_uint,
                             ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.SendMessageW.restype = ctypes.c_void_p
    u.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
    u.GetWindow.restype = wintypes.HWND
    u.GetAncestor.restype = wintypes.HWND
    u.SetWinEventHook.restype = ctypes.c_void_p
    simgeler = {}
    kilit = threading.Lock()

    def simge(buyuk):
        if buyuk not in simgeler:
            boyut = u.GetSystemMetrics(11 if buyuk else 49)  # SM_CXICON / SM_CXSMICON
            simgeler[buyuk] = u.LoadImageW(None, _TK_PROGRAM_IKONU, 1, boyut, boyut, 0x10)
        return simgeler[buyuk]

    pid = os.getpid()
    karar_verilen = set()   # gösterilmiş ve simgesine karar verilmiş pencereler
    sinif = ctypes.create_unicode_buffer(64)

    def dene(h, gosterildi):
        """Kendi simgesi olmayan (ya da pygame'in kendi simgesini taşıyan)
        üst düzey pencereye TürKod simgesini koyar. Pencere oluşturulurken bir
        kez, gösterilirken bir kez bakılır: pygame kendi simgesini pencere
        oluşturulduktan sonra koyar; programın kendi simgesine dokunulmaz."""
        with kilit:
            if h in karar_verilen or u.GetAncestor(h, 2) != h or u.GetWindow(h, 4):
                return  # GA_ROOT değil (iç pencere) ya da sahipli (görev çubuğunda yok)
            if gosterildi:
                karar_verilen.add(h)
            u.GetClassNameW(h, sinif, 64)
            pygame_varsayilani = sinif.value == "pygame" and not _TK_KULLANICI_SIMGESI[0]
            if pygame_varsayilani or not u.SendMessageW(h, 0x7F, 1, None):  # WM_GETICON
                for buyuk in (1, 0):
                    if simge(buyuk):
                        u.SendMessageW(h, 0x80, buyuk, simge(buyuk))  # WM_SETICON

    # Pencere olayları: EVENT_OBJECT_CREATE (0x8000) ve EVENT_OBJECT_SHOW
    # (0x8002). Eskiden pencereler aralıklarla taranıyordu; simge pencere
    # göründükten sonra (ursina'da 1 saniyeden fazla) geliyor, o arada görev
    # çubuğunda Python simgesi görünüyordu.
    OLAY = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, wintypes.DWORD, wintypes.HWND,
                              wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

    @OLAY
    def olay(_kanca, tur, h, nesne, cocuk, _is, _zaman):
        if h and nesne == 0 and cocuk == 0 and tur in (0x8000, 0x8002):  # OBJID_WINDOW
            try:
                dene(h, tur == 0x8002)
            except Exception:
                pass

    def olaylari_dinle():
        # WINEVENT_OUTOFCONTEXT: olaylar bu iş parçacığının ileti kuyruğuna gelir.
        kanca = u.SetWinEventHook(0x8000, 0x8002, None, olay, pid, 0, 0)
        if not kanca:
            return
        ileti = wintypes.MSG()
        while u.GetMessageW(ctypes.byref(ileti), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(ileti))
            u.DispatchMessageW(ctypes.byref(ileti))

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def tara(h, _):
        sahip = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(sahip))
        if sahip.value == pid and u.IsWindowVisible(h):
            dene(h, True)
        return True

    def yedek_tarama():
        # Olay kancası kurulamazsa ya da bir olay kaçarsa diye seyrek tarama.
        while True:
            time.sleep(1.0)
            try:
                u.EnumWindows(tara, 0)
            except Exception:
                return

    threading.Thread(target=olaylari_dinle, daemon=True, name="turkod-simge").start()
    threading.Thread(target=yedek_tarama, daemon=True, name="turkod-simge-yedek").start()
    # Kanca kurulmadan önce açılmış pencere olmasın: çalıştırıcı kullanıcı
    # kodundan önce çalışır, ama iş parçacığının başlaması beklenir.
    time.sleep(0.02)


try:
    _tk_program_simgesi_kur()
except Exception:
    pass

#@HATA_ACIKLAMA_KODU@

import builtins
_gercek_input = builtins.input
def _input(prompt=""):
    sys.stdout.write(str(prompt))
    sys.stdout.flush()
    return _gercek_input()
builtins.input = _input

_gercek_print = builtins.print
_CIKTI_DONUSUMLERI = [
    (re.compile(r'\bNone\b'), 'Hiçlik'),
    (re.compile(r'\bTrue\b'), 'Doğru'),
    (re.compile(r'\bFalse\b'), 'Yanlış'),
]
def _tr_repr(obj, gorulen=None):
    """Kapsayıcıları eleman eleman yazar: yalnızca gerçek Doğru/Yanlış/Hiçlik
    değerleri çevrilir. Eskiden str(liste) üzerinde metin değiştirme
    yapıldığından ["True story"] -> ['Doğru story'] oluyordu."""
    if obj is None:
        return 'Hiçlik'
    if obj is True:
        return 'Doğru'
    if obj is False:
        return 'Yanlış'
    t = type(obj)
    if t not in (list, tuple, dict, set):
        return repr(obj)
    gorulen = gorulen or set()
    if id(obj) in gorulen:
        return '[...]' if t is list else '{...}' if t is dict else '(...)'
    gorulen = gorulen | {id(obj)}
    if t is list:
        return '[' + ', '.join(_tr_repr(x, gorulen) for x in obj) + ']'
    if t is tuple:
        ic = ', '.join(_tr_repr(x, gorulen) for x in obj)
        return '(' + ic + (',' if len(obj) == 1 else '') + ')'
    if t is dict:
        return '{' + ', '.join(f'{_tr_repr(k, gorulen)}: {_tr_repr(v, gorulen)}'
                               for k, v in obj.items()) + '}'
    if not obj:
        return 'set()'
    return '{' + ', '.join(_tr_repr(x, gorulen) for x in obj) + '}'
def _turkcelestir(obj):
    if obj is None:
        return 'Hiçlik'
    if obj is True:
        return 'Doğru'
    if obj is False:
        return 'Yanlış'
    if isinstance(obj, str):
        return obj
    if isinstance(obj, BaseException):
        # yazdır(hata): "list.remove(x): x not in list" yerine Türkçe açıklama.
        try:
            return _hata_detayi(obj)
        except Exception:
            pass
    if type(obj) in (list, tuple, dict, set):
        try:
            return _tr_repr(obj)
        except Exception:
            pass
    metin = str(obj)
    for desen, karsilik in _CIKTI_DONUSUMLERI:
        metin = desen.sub(karsilik, metin)
    return metin
def _print(*args, **kwargs):
    # Yalnızca konsola (stdout/stderr) yazılanlar Türkçeleştirilir:
    # yazdır(Doğru, file=dosya) eskiden dosyaya "Doğru" yazıp içeriği
    # (CSV, JSON, yapılandırma...) bozuyordu.
    hedef = kwargs.get('file')
    if hedef is not None and hedef not in (sys.stdout, sys.stderr,
                                           sys.__stdout__, sys.__stderr__):
        return _gercek_print(*args, **kwargs)
    yeni = tuple(_turkcelestir(a) for a in args)
    _gercek_print(*yeni, **kwargs)
builtins.print = _print

def _yerel_modul_adi(yol, dosya_adi):
    """yol, programın içe aktardığı (geçici klasöre çevrilmiş) bir .trpy
    modülüyse "ad.trpy" döndürür."""
    try:
        if not yol or not os.path.isabs(dosya_adi):
            return None
        klasor = os.path.normcase(os.path.dirname(os.path.abspath(yol)))
        if klasor != os.path.normcase(os.path.dirname(dosya_adi)):
            return None
        ad = os.path.basename(yol)
        if not ad.endswith(".py") or "runner" in ad or ad == os.path.basename(dosya_adi):
            return None
        return ad[:-3] + ".trpy"
    except Exception:
        return None


# runner_kodu_uret() TürKod sözlüğündeki kelimeleri buraya yazar.
_TK_ONERI_KELIMELERI = []
# Bilinen modül adları (Türkçe ve Python): yanlış yazılmış modül adına öneri.
_TK_MODUL_ADLARI = []
# Python adı -> kullanıcının yazdığı TürKod kelimesi (runner_kodu_uret yazar).
# Hata mesajları çevrilmiş adı ('number', 'append', 'list') değil, öğrencinin
# kodunda gördüğü adı ('sayı', 'sona_ekle', 'liste') göstersin diye.
_TK_TERS_ADLAR = {}



def _tr_kucuk(s):
    """Türkçe küçük harf: 'YAZDIR' -> 'yazdır', 'İSİM' -> 'isim'."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def _isim_onerisi(e, tb):
    """Tanımsız isim için en yakın TürKod kelimesi / program adı. Yeni
    başlayanların en sık hatası ('girdi' yerine 'girdi_al', 'doğru' yerine
    'Doğru') eskiden yalnızca "tanımlı değil" diye bildiriliyordu."""
    if isinstance(e, AttributeError) and getattr(e, "name", None):
        return _ozellik_onerisi(getattr(e, "obj", None), e.name)
    if isinstance(e, ModuleNotFoundError) and getattr(e, "name", None):
        # "içe_aktar matematk" -> 'matematik' (eskiden yalnız "bulunamadı").
        import difflib
        ad = e.name.split(".")[0]
        bilinen = set(_TK_MODUL_ADLARI) | set(getattr(sys, "stdlib_module_names", ()))
        bilinen = {b for b in bilinen if b and not b.startswith("_")}
        if ad in bilinen:
            return None
        yakin = difflib.get_close_matches(ad, sorted(bilinen), n=3, cutoff=0.8)
        tr = [y for y in yakin if not y.isascii()]
        return (tr or yakin or [None])[0]
    ad = getattr(e, "name", None)
    if not isinstance(e, NameError) or not ad:
        return None
    python_adi = ad
    ad = _tr_ad(ad)
    kelimeler = set(_TK_ONERI_KELIMELERI)
    programdakiler = set()
    cagri = False
    son = tb
    while son is not None and son.tb_next is not None:
        son = son.tb_next
    if son is not None:
        cerceve = son.tb_frame
        programdakiler.update(k for k in cerceve.f_globals if not k.startswith("_"))
        programdakiler.update(k for k in cerceve.f_locals if not k.startswith("_"))
        import linecache
        satir = linecache.getline(cerceve.f_code.co_filename, son.tb_lineno)
        cagri = re.search(r"(?<![\w.])" + re.escape(python_adi) + r"\s*\(", satir) is not None
    kelimeler.discard(ad)
    programdakiler.discard(ad)
    kucuk = ad.casefold()
    tr_kucuk = _tr_kucuk(ad)
    # Büyük/küçük harf farkı ('doğru' -> 'Doğru', 'YAZDIR' -> 'yazdır') her
    # zaman önerilir; Türkçe I/ı ve İ/i kuralı da denenir.
    for a in sorted(programdakiler | kelimeler):
        if a.casefold() == kucuk or _tr_kucuk(a) == tr_kucuk:
            return a
    # Sözlükteki kelimeler yalnızca ad bir komut gibi çağrıldıysa önerilir:
    # 'girdi(...)' -> 'girdi_al'; ama yazdır(isim) için '__isim__' değil.
    adaylar = programdakiler | (kelimeler if cagri else set())
    # 'girdi' -> 'girdi_al': adın eksik yazılmış bileşik hali önce gelir.
    bilesik = [a for a in adaylar if a.casefold().startswith(kucuk + "_")]
    if bilesik:
        return min(bilesik, key=lambda a: (len(a), a))
    import difflib
    yakin = difflib.get_close_matches(ad, adaylar, n=1, cutoff=0.75)
    return yakin[0] if yakin else None


def _hata_yazdir(e, tb, dosya_adi):
    """Yakalanmamış bir hatayı Türkçe olarak yazar; kullanıcı satırını döndürür."""
    hata_adi_tr = _hata_turu_tr(type(e))

    satir_no = getattr(e, "lineno", None) if isinstance(e, SyntaxError) else None
    modul_dosyasi = None
    if isinstance(e, SyntaxError) and getattr(e, "filename", None):
        modul_dosyasi = _yerel_modul_adi(e.filename, dosya_adi)
    if satir_no is None:
        # En İÇTEKİ kullanıcı çerçevesi: fonksiyon içindeki bir hata,
        # fonksiyonun çağrıldığı satırda değil oluştuğu satırda gösterilir.
        # Aynı programın içe aktardığı yerel .trpy modülleri (geçici klasöre
        # .py olarak çevrilir) de kullanıcı kodudur.
        for frame in traceback.extract_tb(tb):
            if os.path.basename(frame.filename) == os.path.basename(dosya_adi):
                satir_no = frame.lineno
                modul_dosyasi = None
            else:
                ad = _yerel_modul_adi(frame.filename, dosya_adi)
                if ad:
                    satir_no = frame.lineno
                    modul_dosyasi = ad
    if satir_no is None:
        satir_no = "?"

    # Tanınan mesajlar baştan Türkçe yazılır; kalanlarda bilinen parçalar
    # (büyük/küçük harf duyarsız) ve "'str' object" gibi tür adları çevrilir.
    hata_detay = _hata_detayi(e)

    print("=" * 50)
    print(f"[HATA]: {hata_adi_tr}")
    if modul_dosyasi:
        print(f"Dosya: {modul_dosyasi}")
    print(f"Satır Numarası: {satir_no}")
    try:
        oneri = _isim_onerisi(e, tb)
    except Exception:
        oneri = None
    if oneri:
        hata_detay += f" Bunu mu demek istediniz: '{oneri}'?"
    print(f"Açıklama: {hata_detay}")
    print("=" * 50)
    return satir_no, hata_adi_tr, hata_detay
'''


# Hata adları/açıklamaları: hem çalıştırıcı şablonuna gömülür hem de arka uçta
# (akıllı düzeltici, ayrı süreçte çalışan kodun stderr'ini çevirirken)
# hata_aciklamasi() ile kullanılır.
HATA_ACIKLAMA_KODU = r'''HATA_ISIMLERI = {
    "NameError": "Tanımsız İsim Hatası",
    "SyntaxError": "Sözdizimi (Yazım) Hatası",
    "IndentationError": "Girinti Hatası",
    "TabError": "Sekme/Girinti Hatası",
    "TypeError": "Veri Tipi Hatası",
    "ValueError": "Geçersiz Değer Hatası",
    "ZeroDivisionError": "Sıfıra Bölme Hatası",
    "IndexError": "Liste İndeks Hatası",
    "KeyError": "Sözlük Anahtar Hatası",
    "AttributeError": "Özellik / Metot Bulunamadı Hatası",
    "ImportError": "İçe Aktarma Hatası",
    "ModuleNotFoundError": "Modül Bulunamadı Hatası",
    "FileNotFoundError": "Dosya Bulunamadı Hatası",
    "PermissionError": "İzin Hatası",
    "RecursionError": "Sonsuz Özyineleme Hatası",
    "StopIteration": "Döngü Sonu Hatası",
    "RuntimeError": "Çalışma Zamanı Hatası",
    "OSError": "Sistem Hatası",
    "IOError": "Giriş/Çıkış Hatası",
    "UnicodeDecodeError": "Karakter Kod Çözme Hatası",
    "UnicodeEncodeError": "Karakter Kodlama Hatası",
    "OverflowError": "Sayı Taşma Hatası",
    "MemoryError": "Bellek Yetersiz Hatası",
    "EOFError": "Dosya Sonu Hatası",
    "ConnectionError": "Bağlantı Hatası",
    "TimeoutError": "Zaman Aşımı Hatası",
    "IsADirectoryError": "Dizin Hatası",
    "NotADirectoryError": "Dizin Değil Hatası",
    "FileExistsError": "Dosya Zaten Var Hatası",
    "UnboundLocalError": "Tanımsız Yerel Değişken Hatası",
    "ArithmeticError": "Aritmetik Hatası",
    "FloatingPointError": "Ondalık Hatası",
    "BaseException": "Temel İstisna",
    "Exception": "İstisna",
    "AssertionError": "Doğrulama (iddia_et) Hatası",
    "LookupError": "Arama Hatası",
    "BufferError": "Tampon Hatası",
    "NotImplementedError": "Henüz Yazılmamış Özellik Hatası",
    "ReferenceError": "Referans Hatası",
    "SystemError": "Python İç Hatası",
    "UnicodeError": "Karakter Kodu Hatası",
    "UnicodeTranslateError": "Karakter Dönüştürme Hatası",
    "BlockingIOError": "Engellenen Giriş/Çıkış Hatası",
    "ChildProcessError": "Alt Süreç Hatası",
    "BrokenPipeError": "Kopuk Bağlantı (Boru) Hatası",
    "ConnectionAbortedError": "Bağlantı İptal Edildi Hatası",
    "ConnectionRefusedError": "Bağlantı Reddedildi Hatası",
    "ConnectionResetError": "Bağlantı Sıfırlandı Hatası",
    "InterruptedError": "Kesinti Hatası",
    "ProcessLookupError": "Süreç Bulunamadı Hatası",
    "StopAsyncIteration": "Eşzamansız Döngü Sonu Hatası",
    "GeneratorExit": "Üreteç Kapatıldı",
    "SystemExit": "İzlence (Program) Çıkışı",
    "KeyboardInterrupt": "Klavye Kesintisi (Ctrl+C)",
    "ExceptionGroup": "Hata Grubu",
    "BaseExceptionGroup": "Temel Hata Grubu",
    "PythonFinalizationError": "Python Kapanış Hatası",
    "Warning": "Uyarı",
    "UserWarning": "Uyarı",
    "DeprecationWarning": "Eskimiş Kullanım Uyarısı",
    "PendingDeprecationWarning": "Yakında Eskiyecek Kullanım Uyarısı",
    "FutureWarning": "Gelecek Sürüm Uyarısı",
    "RuntimeWarning": "Çalışma Zamanı Uyarısı",
    "SyntaxWarning": "Sözdizimi Uyarısı",
    "ResourceWarning": "Kaynak Uyarısı",
    "ImportWarning": "İçe Aktarma Uyarısı",
    "UnicodeWarning": "Karakter Kodlama Uyarısı",
    "BytesWarning": "Bayt Uyarısı",
    "EncodingWarning": "Kodlama Uyarısı",
}

# Kütüphane hata sınıfları: "kök_paket.SınıfAdı" -> Türkçe sınıf adı
# ("selenium.TimeoutException" -> "ZamanAşımıHatası"). runner_kodu_uret()
# modül sözlüğünden doldurur; boşsa düz sözlükteki karşılık (_TK_TERS_ADLAR)
# kullanılır.
_TK_HATA_ADLARI = {}
# Hata türünün yanında gösterilen kütüphane adı ("Zaman Aşımı Hatası (selenium)").
_KUTUPHANE_GORUNEN_ADLAR = {
    "cv2": "OpenCV", "PIL": "Pillow", "sklearn": "scikit-learn", "bs4": "BeautifulSoup",
    "fitz": "PyMuPDF", "pymupdf": "PyMuPDF", "docx": "python-docx", "pptx": "python-pptx",
    "_tkinter": "tkinter", "tkinter": "tkinter",
}
_BUYUK = "A-ZÇĞİÖŞÜ"
_KUCUK = "a-zçğıöşü0-9"


def _bosluklu(ad):
    """'ZamanAşımıHatası' -> 'Zaman Aşımı Hatası', 'HTTPHatası' -> 'HTTP Hatası'."""
    if not ad or " " in ad or "_" in ad:
        return ad
    return re.sub(rf"(?<=[{_KUCUK}])(?=[{_BUYUK}])|(?<=[{_BUYUK}])(?=[{_BUYUK}][{_KUCUK[:-3]}])",
                  " ", ad)


def _tek_tur_tr(tur):
    """Tek bir sınıfın Türkçe adı; bilinmiyorsa None."""
    ad = tur.__name__
    modul = getattr(tur, "__module__", "") or ""
    if modul == "builtins":
        return HATA_ISIMLERI.get(ad)
    kok = modul.split(".")[0].lstrip("_") if modul else ""
    tr = _TK_HATA_ADLARI.get(f"{kok}.{ad}") or _TK_HATA_ADLARI.get(f"_{kok}.{ad}")
    if tr is None:
        tr = _TK_TERS_ADLAR.get(ad)
        if tr is not None and not tr[:1].isupper():
            tr = None
    return _bosluklu(tr) if tr else None


def _hata_turu_tr(tur):
    """Hata sınıfının Türkçe adı. Kütüphane hatalarında kütüphane adı da
    eklenir; çevirisi olmayan bir kütüphane hatası, Türkçesi bilinen en yakın
    üst sınıfıyla anlatılır ("Bağlantı Hatası (ConnectTimeout, requests)")."""
    try:
        ad = tur.__name__
        modul = getattr(tur, "__module__", "") or ""
        if modul in ("builtins", "__main__") or modul.endswith("turkce_kod_calisma"):
            return HATA_ISIMLERI.get(ad, ad) if modul == "builtins" else ad
        kok = modul.split(".")[0]
        gorunen = _KUTUPHANE_GORUNEN_ADLAR.get(kok, kok)
        tr = _tek_tur_tr(tur)
        if tr:
            return f"{tr} ({gorunen})"
        if ad.lower() == "error":
            return f"{gorunen} Hatası"
        for ust in tur.__mro__[1:]:
            ust_tr = _tek_tur_tr(ust)
            if ust_tr and ust.__name__ not in ("Exception", "BaseException"):
                return f"{ust_tr} ({ad}, {gorunen})"
        return f"{ad} ({gorunen})"
    except Exception:
        return getattr(tur, "__name__", str(tur))

HATA_MESAJLARI = {
    r"^name '(.+?)' is not defined.*$": r"'\1' adında bir değişken/fonksiyon tanımlı değil!",
    r"is not defined": "bu isimde bir değişken/fonksiyon tanımlı değil!",
    r"invalid syntax": "geçersiz kod yazımı! Eksik sembol veya hatalı kelime kullanımı var!",
    r"unexpected EOF while parsing": "kapatılmamış parantez veya tırnak işareti var!",
    r"expected an indented block": "girintili kod bloğu eksik!",
    r"unindent does not match any outer indentation level": "girinti seviyesi üst bloklarla uyuşmuyor!",
    r"inconsistent use of tabs and spaces in indentation": "girintide tab ve boşluk karışık kullanılmış!",
    r"division by zero": "bir sayı 0'a bölünemez!",
    r"list index out of range": "listenin sınırları dışında bir elemana ulaşmaya çalıştınız!",
    r"tuple index out of range": "demetin sınırları dışında bir elemana ulaşmaya çalıştınız!",
    r"string index out of range": "metnin sınırları dışında bir konuma ulaşmaya çalıştınız!",
    r"has no attribute": "bu özelliği/metodu bulunamadı!",
    r"no module named": "bu isimde bir modül/kütüphane bulunamadı!",
    r"cannot import name": "bu isim içe aktarılamadı!",
    r"no such file or directory": "dosya veya dizin bulunamadı!",
    r"permission denied": "dosyaya erişim izni yok!",
    r"maximum recursion depth exceeded": "fonksiyon kendini çok fazla çağırdı (sonsuz döngü olabilir)!",
    r"invalid literal for int\(\)": "bu değer tamsayıya dönüştürülemiyor!",
    r"invalid literal for float\(\)": "bu değer ondalık sayıya dönüştürülemiyor!",
    r"could not convert string to float": "metin ondalık sayıya dönüştürülemiyor!",
    r"object is not iterable": "bu nesne döngüyle tekrarlanamaz!",
    r"unsupported operand type": "bu türler arasında bu işlem yapılamaz!",
    # Önce tam kalıp: eskiden yalnızca baş kısım çevrildiğinden mesaj
    # "...birleştirilebilir! (not "int") to str" diye yarım kalıyordu.
    r'can only concatenate str \(not "[^"]+"\) to str':
        "metin ile sayı gibi farklı türler + ile birleştirilemez! Önce metin() ile çevir ya da f-yazı kullan.",
    r"can only concatenate str": "yalnızca aynı türler birleştirilebilir!",
    r"not subscriptable": "köşeli parantezle erişilemez (liste/sözlük bekleniyor)!",
    r"not callable": "çağrılamaz (fonksiyon bekleniyor)!",
    r"unexpected keyword argument": "beklenmeyen bir parametre adı kullanıldı!",
    r"required positional argument": "zorunlu bir parametre eksik!",
    r"takes \d+ positional arguments? but \d+ w(?:as|ere) given": "fonksiyona yanlış sayıda parametre verildi!",
    r"object has no len\(\)": "bu nesnenin uzunluğu ölçülemez (len() kullanılamaz)!",
    r"not enough values to unpack": "açılacak yeterli değer yok!",
    r"too many values to unpack": "açılacak çok fazla değer var!",
    r"cannot be interpreted as an integer": "tamsayı olarak yorumlanamıyor!",
    r"local variable .* referenced before assignment": "değişken atanmadan önce kullanıldı!",
    r"cannot access local variable '(.+?)' where it is not associated with a value":
        r"'\1' değişkeni atanmadan önce kullanıldı!",
    r"'(.)' was never closed": r"'\1' açıldı ama kapatılmadı!",
    r"unterminated string literal.*": "kapatılmamış metin (tırnak eksik)!",
    r"is a directory": "bu bir dizin (dosya bekleniyordu)!",
    r"not a directory": "bu bir dizin değil!",
    r"file already exists": "dosya zaten var!",
    r"file exists": "dosya zaten var!",
    r"too many open files": "çok fazla açık dosya var!",
    r"slice indices must be integers": "dilim indeksleri tamsayı olmalı!",
    r"encode\(\) argument 1 must be str": "kodlama argümanı metin olmalı!",
}


def _tur(m, i):
    return _tr_tur(m.group(i))


# Mesajın tamamı için Türkçe açıklama (Python ve sık kullanılan kütüphaneler).
# HATA_MESAJLARI yalnızca parça değiştirir; bunlar mesajı baştan yazar ve
# içindeki ad, değer, satır gibi bilgileri korur. Sıra önemlidir: ilk
# eşleşen kullanılır.
_BLOK_ADLARI = {
    "if": "eğer", "elif": "değilse_eğer", "else": "değilse", "for": "için",
    "while": "döngü", "try": "dene", "except": "hata_yakala", "finally": "sonunda",
    "with": "ile", "match": "eşleştir", "case": "durumunda",
}

_TAM_MESAJLAR = [
    # --- Python 3.12 yazım (sözdizimi) iletileri ---
    (r"^unexpected indent$", "bu satır gereksiz yere içeride (fazladan girinti var)!"),
    (r"^expected ':'$", "satırın sonunda ':' eksik!"),
    (r"^expected an indented block after '(\w+)' statement on line (\d+)$",
     lambda m: f"{m.group(2)}. satırdaki '{_BLOK_ADLARI.get(m.group(1), m.group(1))}' "
               f"satırının altına girintili (içeride) kod yazılmalı!"),
    (r"^expected an indented block after (function|class) definition on line (\d+)$",
     lambda m: f"{m.group(2)}. satırdaki {'fonksiyonun' if m.group(1) == 'function' else 'sınıfın'} "
               f"altına girintili (içeride) kod yazılmalı!"),
    (r"^expected an indented block after '(\w+)' statement on line (\d+)$|"
     r"^expected an indented block.*$", "girintili kod bloğu eksik!"),
    # --- Python 3.12 iletileri ---
    (r"^(\w+)\(\) iterable argument is empty$",
     lambda m: f"boş bir diziden '{_tr_ad(m.group(1))}' hesaplanamaz!"),
    (r"^(\w+)\(\) argument must be a string, a bytes-like object or a (?:real )?number, not '(\w+)'$",
     lambda m: f"'{_tr_ad(m.group(1))}' metin ya da sayı bekliyor, {_tur(m, 2)} verildi!"),
    (r"^cannot import name '(.+?)' from '(.+?)'.*$",
     lambda m: f"'{m.group(2)}' içinde '{m.group(1)}' diye bir şey yok, içe aktarılamadı!"),
    (r"^type object '(.+?)' has no attribute '(.+?)'$",
     lambda m: f"'{m.group(1)}' içinde '{m.group(2)}' diye bir özellik/metot yok!"),
    (r"^empty range (?:in|for) randrange\(.*\)$",
     "rastgele sayı aralığı boş: ilk sayı ikinciden büyük olamaz!"),
    (r"^type (\w+) doesn't define __round__ method$",
     lambda m: f"{_tur(m, 1)} türündeki değer yuvarlanamaz (önce sayıya çevirin)!"),
    (r"^chr\(\) arg not in range\(0x110000\)$", "karakter kodu 0 ile 1114111 arasında olmalı!"),
    (r"^attempt to assign sequence of size (\d+) to extended slice of size (\d+)$",
     lambda m: f"adımlı dilime {m.group(2)} değer atanmalı, {m.group(1)} verildi!"),
    (r"^must assign iterable to extended slice$", "adımlı dilime liste gibi bir dizi atanmalı!"),
    (r"^\((\d+), '(.+?)'\)$|^(?:int|Result) too large.*$|^.*too large to convert.*$",
     "sayı çok büyük, hesaplanamıyor!"),
    # --- Python: listeler, sözlükler, metinler ---
    (r"^list\.remove\(x\): x not in list$", "silinmek istenen değer listede yok!"),
    (r"^(.+?) is not in list$", lambda m: f"{m.group(1)} değeri listede yok!"),
    (r"^(?:tuple|list)\.index\(x\): x not in (?:tuple|list)$", "aranan değer bulunamadı!"),
    (r"^unhashable type: '(\w+)'$",
     lambda m: f"{_tur(m, 1)} türündeki değer sözlük anahtarı ya da küme elemanı olamaz "
               f"(değiştirilebilir değerler anahtar olamaz; demet kullanın)!"),
    (r"^pop from empty list$", "boş listeden eleman çıkarılamaz!"),
    (r"^pop from an empty (deque|set)$",
     lambda m: f"boş {'çift uçlu kuyruktan' if m.group(1) == 'deque' else 'kümeden'} eleman çıkarılamaz!"),
    (r"^'?popitem\(\): dictionary is empty'?$", "boş sözlükten eleman çıkarılamaz!"),
    (r"^(dictionary|set) changed size during iteration$",
     lambda m: f"{'sözlük' if m.group(1) == 'dictionary' else 'küme'} üzerinde döngü dönerken "
               f"boyutu değiştirildi! Döngüyü bir kopyası (liste(...)) üzerinde kurun."),
    (r"^substring not found$", "aranan metin parçası bulunamadı!"),
    (r"^empty separator$", "ayırıcı boş olamaz!"),
    (r"^list assignment index out of range$",
     "listenin sınırları dışındaki bir konuma değer atanamaz (yeni eleman için sona_ekle kullanın)!"),
    (r"^'(\w+)' object does not support item assignment$",
     lambda m: f"{_tur(m, 1)} türündeki değerin elemanları değiştirilemez!"),
    (r"^'(\w+)' object doesn't support item deletion$|^'(\w+)' object does not support item deletion$",
     lambda m: f"{_tr_tur(m.group(1) or m.group(2))} türündeki değerden eleman silinemez!"),
    (r"^'(\w+)' object is not an iterator$",
     lambda m: f"{_tur(m, 1)} türündeki değer bir yineleyici değil (önce yineleyici(...) kullanın)!"),
    (r"^cannot unpack non-iterable (\w+) object$",
     lambda m: f"{_tur(m, 1)} türündeki tek bir değer birden fazla değişkene açılamaz!"),
    (r"^not enough values to unpack \(expected (\d+), got (\d+)\)$",
     lambda m: f"açılacak yeterli değer yok: {m.group(1)} değer bekleniyordu, {m.group(2)} geldi!"),
    (r"^too many values to unpack \(expected (\d+)(?:, got (\d+))?\)$",
     lambda m: f"açılacak değer çok fazla: {m.group(1)} değişken var"
               + (f", {m.group(2)} değer geldi!" if m.group(2) else "!")),
    (r"^can't multiply sequence by non-int of type '(\w+)'$",
     lambda m: f"liste/metin yalnızca tamsayıyla çarpılabilir, {_tur(m, 1)} ile değil!"),
    (r'^can only concatenate (list|tuple) \(not "(\w+)"\) to (?:list|tuple)$',
     lambda m: f"{_tur(m, 1)} türüne + ile yalnızca yine {_tur(m, 1)} eklenebilir, {_tur(m, 2)} değil!"),
    (r"^sequence item (\d+): expected str instance, (\w+) found$",
     lambda m: f"birleştirilen {int(m.group(1)) + 1}. eleman metin değil ({_tur(m, 2)}); "
               f"birleştir yalnızca metinlerle çalışır, önce metin(...) ile çevirin!"),
    (r"^(?:must be str|expected str)(?: or None)?, not (\w+)$|^must be str, not (\w+)$",
     lambda m: f"metin bekleniyordu, {_tr_tur(m.group(1) or m.group(2))} verildi!"),
    (r"^(\w+)\(\) argument must be a string or a (?:real )?number, not '(\w+)'$",
     lambda m: f"'{_tr_ad(m.group(1))}' metin ya da sayı bekliyor, {_tur(m, 2)} verildi!"),
    (r"^(\w+)\(\) takes no keyword arguments$",
     lambda m: f"'{_tr_ad(m.group(1))}' fonksiyonu adı verilmiş parametre (ad=değer) almaz!"),
    (r"^(\w+) expected at most (\d+) arguments?, got (\d+)$",
     lambda m: f"'{_tr_ad(m.group(1))}' en fazla {m.group(2)} değer alır, {m.group(3)} verildi!"),
    (r"^(\w+) expected at least (\d+) arguments?, got (\d+)$",
     lambda m: f"'{_tr_ad(m.group(1))}' en az {m.group(2)} değer ister, {m.group(3)} verildi!"),
    (r"^(\w+)\(\) (?:arg|iterable argument) is an empty sequence$",
     lambda m: f"boş bir diziden '{_tr_ad(m.group(1))}' hesaplanamaz!"),
    (r"^range\(\) arg 3 must not be zero$", "aralık() adımı sıfır olamaz!"),
    (r"^%(\w) format: a (?:real )?number is required, not (\w+)$",
     lambda m: f"%{m.group(1)} biçimi sayı bekliyor, {_tur(m, 2)} verildi!"),
    (r"^not all arguments converted during string formatting$",
     "biçimlendirmede bazı değerler kullanılmadı (% işaretlerinin sayısını kontrol edin)!"),
    (r"^not enough arguments for format string$", "biçimlendirme için yeterli değer verilmedi!"),
    (r"^Replacement index (\d+) out of range for positional args tuple$",
     lambda m: f"biçimle(): {{{m.group(1)}}} için değer verilmedi!"),
    (r"^unsupported format string passed to (\w+)\.__format__$",
     lambda m: f"{_tur(m, 1)} türündeki değer bu biçim belirteciyle biçimlenemez!"),
    (r"^Invalid format specifier.*$", "geçersiz biçim belirteci (f-yazıda : sonrasını kontrol edin)!"),
    # --- Python: sayılar ---
    (r"^math domain error$",
     "matematiksel tanım dışı değer (ör. negatif sayının karekökü ya da sıfırın logaritması)!"),
    (r"^math range error$", "sonuç hesaplanamayacak kadar büyük!"),
    (r"^(?:integer|float|complex) (?:division|modulo|divmod)(?: or modulo)? by zero$",
     "bir sayı 0'a bölünemez!"),
    (r"^int too large to convert to float$", "tamsayı ondalığa dönüştürülemeyecek kadar büyük!"),
    (r"^Exceeds the limit \((\d+) digits\) for integer string conversion.*$",
     lambda m: f"sayı metne çevrilemeyecek kadar uzun ({m.group(1)} basamak sınırı aşıldı)!"),
    (r"^(?:pow\(\) )?(?:negative number cannot be raised to a fractional power|"
     r"0\.0 cannot be raised to a negative power)$", "bu üs alma işlemi tanımsız!"),
    (r"^(.+?) is not a valid (\w+)$", lambda m: f"{m.group(1)}, geçerli bir {m.group(2)} değeri değil!"),
    # --- Python: dosyalar ve girdi ---
    (r"^\[Errno 2\] No such file or directory: (.+)$",
     lambda m: f"dosya ya da klasör bulunamadı: {m.group(1)} (adı ve programla aynı klasörde "
               f"olup olmadığını kontrol edin)"),
    (r"^\[Errno 13\] Permission denied: (.+)$",
     lambda m: f"erişim izni yok: {m.group(1)} (dosya başka bir programda açık olabilir)"),
    (r"^\[Errno 17\] File exists: (.+)$", lambda m: f"zaten var: {m.group(1)}"),
    (r"^\[Errno 21\] Is a directory: (.+)$", lambda m: f"bu bir klasör, dosya değil: {m.group(1)}"),
    (r"^\[Errno 20\] Not a directory: (.+)$", lambda m: f"bu bir klasör değil: {m.group(1)}"),
    (r"^\[Errno 22\] Invalid argument: (.+)$",
     lambda m: f"geçersiz dosya adı ya da yol: {m.group(1)}"),
    (r"^\[WinError 2\] .*?: (.+)$", lambda m: f"dosya ya da klasör bulunamadı: {m.group(1)}"),
    (r"^\[WinError 3\] .*?: (.+)$", lambda m: f"yol bulunamadı: {m.group(1)}"),
    (r"^\[WinError 5\] .*?: (.+)$", lambda m: f"erişim engellendi: {m.group(1)}"),
    (r"^\[WinError 32\] .*?: (.+)$",
     lambda m: f"dosya başka bir program tarafından kullanılıyor: {m.group(1)}"),
    (r"^\[WinError 10061\].*$",
     "bağlantı reddedildi: karşı tarafta bu bağlantı noktasını dinleyen bir sunucu yok!"),
    (r"^\[WinError 10060\].*$", "bağlantı zaman aşımına uğradı: karşı taraf yanıt vermedi!"),
    (r"^\[Errno 11001\] getaddrinfo failed$|^<urlopen error \[Errno 11001\] getaddrinfo failed>$",
     "adres çözümlenemedi: internet bağlantısını ve adresi kontrol edin!"),
    (r"^<urlopen error (.+)>$", lambda m: f"adres açılamadı: {m.group(1)}"),
    (r"^HTTP Error (\d+): (.+)$", lambda m: f"HMAP {m.group(1)} hatası: {m.group(2)}"),
    (r"^timed out$", "zaman aşımı: işlem süresinde tamamlanamadı!"),
    (r"^I/O operation on closed file\.?$", "kapatılmış bir dosya üzerinde işlem yapılamaz!"),
    (r"^not readable$", "dosya okuma kipinde açılmamış (aç(..., 'r') kullanın)!"),
    (r"^not writable$", "dosya yazma kipinde açılmamış (aç(..., 'w') ya da 'a' kullanın)!"),
    (r"^EOF when reading a line$",
     "girdi beklenirken giriş sona erdi (program klavyeden girdi alamıyor)!"),
    (r"^File is not a zip file$", "dosya bir sıkıştırılmış (zip) arşiv değil!"),
    (r"^'(\w+)' codec can't decode byte (0x[0-9a-f]+) in position (\d+): (.+)$",
     lambda m: f"metin '{m.group(1)}' kodlamasıyla okunamadı ({m.group(3)}. konumdaki "
               f"{m.group(2)} baytı); dosyayı aç(..., kodlama='utf-8') ile açmayı deneyin!"),
    (r"^'(\w+)' codec can't encode character (.+?) in position (\d+): (.+)$",
     lambda m: f"{m.group(2)} karakteri '{m.group(1)}' kodlamasıyla yazılamıyor "
               f"(kodlama='utf-8' kullanın)!"),
    # --- json ---
    (r"^Expecting value: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(1)}. satır {m.group(2)}. sütunda değer bekleniyordu "
               f"(metin geçerli JNG değil ya da boş)!"),
    (r"^Expecting property name enclosed in double quotes: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(1)}. satır {m.group(2)}. sütunda çift tırnaklı "
               f"anahtar adı bekleniyordu!"),
    (r"^Expecting '(.)' delimiter: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(2)}. satır {m.group(3)}. sütunda '{m.group(1)}' "
               f"bekleniyordu!"),
    (r"^Extra data: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(1)}. satır {m.group(2)}. sütundan sonra fazladan veri var!"),
    (r"^Unterminated string starting at: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(1)}. satır {m.group(2)}. sütunda başlayan metin kapatılmamış!"),
    (r"^Invalid control character at: line (\d+) column (\d+) \(char \d+\)$",
     lambda m: f"JNG (JSON) çözülemedi: {m.group(1)}. satır {m.group(2)}. sütunda geçersiz kontrol karakteri!"),
    (r"^Object of type (\w+) is not JSON serializable$",
     lambda m: f"{_tur(m, 1)} türündeki değer JNG'ye (JSON) dönüştürülemez!"),
    # --- sqlite3 ---
    (r"^no such table: (.+)$", lambda m: f"'{m.group(1)}' adında bir tablo yok!"),
    (r"^no such column: (.+)$", lambda m: f"'{m.group(1)}' adında bir sütun yok!"),
    (r"^table (\w+) already exists$", lambda m: f"'{m.group(1)}' tablosu zaten var!"),
    (r"^UNIQUE constraint failed: (.+)$",
     lambda m: f"benzersizlik kuralı çiğnendi: {m.group(1)} değeri zaten var!"),
    (r"^NOT NULL constraint failed: (.+)$", lambda m: f"{m.group(1)} boş bırakılamaz!"),
    (r'^near "(.+)": syntax error$', lambda m: f"YSD (SQL) yazım hatası: '{m.group(1)}' yakınında!"),
    (r"^database is locked$", "veritabanı kilitli (başka bir bağlantı ya da program kullanıyor)!"),
    (r"^Incorrect number of bindings supplied\. The current statement uses (\d+), and there are (\d+) supplied\.$",
     lambda m: f"YSD (SQL) komutu {m.group(1)} değer bekliyor ama {m.group(2)} değer verildi!"),
    # --- requests / urllib3 ---
    (r"^HTTPS?ConnectionPool\(host='([^']+)', port=(\d+)\): Max retries exceeded with url: (\S+) "
     r"\(Caused by (\w+)\(.*$",
     lambda m: f"{m.group(1)}:{m.group(2)}{m.group(3)} adresine ulaşılamadı: "
               + {"NewConnectionError": "bağlantı kurulamadı (sunucu kapalı ya da adres yanlış)",
                  "ConnectTimeoutError": "bağlantı zaman aşımına uğradı",
                  "ReadTimeoutError": "sunucu zamanında yanıt vermedi",
                  "NameResolutionError": "adres çözümlenemedi (internet bağlantısını kontrol edin)",
                  "SSLError": "güvenli bağlantı (GYK) kurulamadı",
                  "ProxyError": "vekil sunucuya bağlanılamadı",
                  "ResponseError": "sunucu çok fazla hata yanıtı döndürdü"}.get(
                      m.group(4), m.group(4)) + "!"),
    (r"^HTTPS?ConnectionPool\(host='([^']+)', port=(\d+)\): Read timed out\..*$",
     lambda m: f"{m.group(1)}:{m.group(2)} zamanında yanıt vermedi (okuma zaman aşımı)!"),
    (r"^Invalid URL '([^']*)': No scheme supplied\..*$",
     lambda m: f"geçersiz adres '{m.group(1)}': başına http:// ya da https:// ekleyin!"),
    (r"^No connection adapters were found for '([^']*)'$",
     lambda m: f"'{m.group(1)}' adresi açılamıyor: adres http:// ya da https:// ile başlamalı!"),
    (r"^(\d{3}) (Client|Server) Error: (.*?) for url: (\S+)$",
     lambda m: f"{m.group(1)} {'istemci' if m.group(2) == 'Client' else 'sunucu'} hatası "
               f"({m.group(3)}): {m.group(4)}"),
    # --- OpenCV ---
    (r"^OpenCV\([\d.]+\) .*?error: \(-215:Assertion failed\) !_src\.empty\(\) in function '(.+?)'\s*$",
     lambda m: f"işlenecek resim boş! resim_oku() dosyayı bulamamış olabilir; dosya adını ve "
               f"klasörünü kontrol edin. (OpenCV fonksiyonu: {m.group(1)})"),
    (r"^OpenCV\([\d.]+\) .*?error: \((-?\d+):([^)]+)\) (.+?) in function '(.+?)'\s*$",
     lambda m: "OpenCV: " + {"Assertion failed": "koşul sağlanmadı",
                             "Bad argument": "hatalı argüman",
                             "Unsupported format or combination of formats": "desteklenmeyen biçim",
                             "Sizes of input arguments do not match": "girdi boyutları uyuşmuyor",
                             "Unspecified error": "belirtilmemiş hata",
                             "Bad number of channels": "kanal sayısı uygun değil",
                             "Incorrect size of input array": "girdi dizisinin boyutu yanlış",
                             "Insufficient memory": "bellek yetersiz"}.get(
                                 m.group(2).strip(), m.group(2).strip())
               + f": {m.group(3).strip()} (fonksiyon: {m.group(4)})"),
    # --- NumPy / pandas / PyTorch ---
    (r"^operands could not be broadcast together with shapes (\S+) (\S+)\s*$",
     lambda m: f"şekilleri uyuşmayan diziler birlikte işlenemez: {m.group(1)} ve {m.group(2)}!"),
    (r"^The truth value of an? (?:array|Series|DataFrame).*?is ambiguous.*$",
     "birden çok elemanlı dizinin doğruluk değeri belirsiz; .herhangi() / .hepsi() "
     "(any/all) kullanın ya da & ve | ile karşılaştırın!"),
    (r"^index (-?\d+) is out of bounds for axis (\d+) with size (\d+)$",
     lambda m: f"{m.group(1)} indeksi {m.group(2)}. eksende sınırların dışında "
               f"(bu eksende {m.group(3)} eleman var)!"),
    (r"^setting an array element with a sequence.*$",
     "dizinin bir elemanına birden fazla değer konulamaz (alt listelerin uzunlukları farklı olabilir)!"),
    (r"^cannot reshape array of size (\d+) into shape (.+)$",
     lambda m: f"{m.group(1)} elemanlı dizi {m.group(2)} şekline sokulamaz!"),
    (r"^Length of values \((\d+)\) does not match length of index \((\d+)\)$",
     lambda m: f"{m.group(1)} değer var ama tablonun {m.group(2)} satırı var; uzunluklar uyuşmuyor!"),
    (r"^mat1 and mat2 shapes cannot be multiplied \((.+?) and (.+?)\)$",
     lambda m: f"matris boyutları çarpma için uyuşmuyor: {m.group(1)} ve {m.group(2)}!"),
    (r"^CUDA out of memory.*$", "GİB (CUDA) belleği yetersiz; toplu iş boyutunu küçültün!"),
    (r"^Torch not compiled with CUDA enabled$",
     "bu PyTorch kurulumu GİB (CUDA) desteklemiyor; aygıt('cpu') kullanın!"),
    # --- pygame / tkinter / turtle / Pillow ---
    (r"^video system not initialized$",
     "pygame başlatılmadı ya da pencere kapatıldı; önce py_oyun.oyun_başlat() çağırın!"),
    (r"^display Surface quit$", "pencere kapatıldığı için artık üzerine çizilemez!"),
    (r"^No file '(.+?)' found in working directory '(.+?)'\.?$",
     lambda m: f"'{m.group(1)}' dosyası çalışma klasöründe ({m.group(2)}) bulunamadı!"),
    (r"^Unsupported image format$", "desteklenmeyen resim biçimi!"),
    (r'^unknown color (?:name|specifier) "?(.+?)"?$', lambda m: f"bilinmeyen renk adı: {m.group(1)}"),
    (r'^bad color string: (.+)$', lambda m: f"bilinmeyen renk: {m.group(1)}"),
    (r'^can\'t invoke "(\w+)" command: application has been destroyed$',
     "pencere kapatıldığı için bu komut çalıştırılamaz!"),
    (r"^no display name and no \$DISPLAY environment variable$",
     "pencere açılamıyor: bu ortamda ekran yok!"),
    (r"^cannot identify image file (.+)$",
     lambda m: f"resim dosyası tanınamadı: {m.group(1)} (bozuk ya da desteklenmeyen biçim)!"),
    # --- Yerleşik fonksiyon / metotlara yanlış sayıda değer (C ile yazılmış olanlar) ---
    # "datetime.ctime() takes no arguments (1 given)", "len() takes exactly one argument
    # (2 given)", "divmod expected 2 arguments, got 1" ...
    (r"^([\w.]+)\(\) takes no arguments \((\d+) given\)$",
     lambda m: f"'{_metot_adi(m.group(1))}' parantez içine değer almaz ama {m.group(2)} "
               f"değer verildi!{_metot_ipucu(m.group(1))}"),
    (r"^([\w.]+)\(\) takes exactly one argument \((\d+) given\)$",
     lambda m: f"'{_metot_adi(m.group(1))}' tam 1 değer alır ama {m.group(2)} değer "
               f"verildi!{_metot_ipucu(m.group(1))}"),
    (r"^([\w.]+)\(\) takes (exactly|at most|at least) (\d+) arguments? \((\d+) given\)$",
     lambda m: f"'{_metot_adi(m.group(1))}' {_SAYI_SINIRI[m.group(2)]} {m.group(3)} değer "
               f"alır ama {m.group(4)} değer verildi!{_metot_ipucu(m.group(1))}"),
    (r"^([\w.]+) expected (?:(at most|at least) )?(\d+) arguments?, got (\d+)$",
     lambda m: f"'{_metot_adi(m.group(1))}' {_SAYI_SINIRI[m.group(2) or 'exactly']} "
               f"{m.group(3)} değer alır ama {m.group(4)} değer verildi!"
               f"{_metot_ipucu(m.group(1))}"),
    # --- Selenium ---
    (r"^Message: no such element: Unable to locate element: (.+?)(?:\n.*)?$",
     lambda m: f"sayfada öğe bulunamadı: {m.group(1).strip()}"),
    (r"^Message: session not created:? (.+?)(?:\n.*)?$",
     lambda m: f"tarayıcı oturumu başlatılamadı (tarayıcı ve sürücü sürümleri uyumsuz "
               f"olabilir): {m.group(1).strip()}"),
    (r"^Message: element click intercepted: (.+?)(?:\n.*)?$",
     lambda m: f"öğeye tıklanamadı, önünde başka bir öğe var: {m.group(1).strip()}"),
    (r"^Message: stale element reference.*$",
     "öğe artık sayfada yok (sayfa yenilenmiş olabilir); öğeyi yeniden bulun!"),
    (r"^Message: ?(.*?)(?:\nStacktrace:.*)?$",
     lambda m: m.group(1).strip() or "(ayrıntı yok)"),
]
_TAM_MESAJLAR = [(re.compile(d, re.DOTALL), t) for d, t in _TAM_MESAJLAR]


def _tam_mesaj_cevir(mesaj):
    for desen, karsilik in _TAM_MESAJLAR:
        m = desen.match(mesaj)
        if m:
            try:
                return karsilik(m) if callable(karsilik) else karsilik
            except Exception:
                return None
    return None


def _hata_detayi(e):
    """Hata nesnesinin Türkçe açıklaması (yazdır(hata) ve [HATA] çıktısı)."""
    tur = type(e)
    modul = getattr(tur, "__module__", "") or ""
    if modul == "__main__" or modul.endswith("turkce_kod_calisma"):
        return str(e)  # kullanıcının kendi hata sınıfı: mesajı olduğu gibi
    try:
        detay = _ozel_aciklama(e)
    except Exception:
        detay = None
    if detay is None:
        detay = str(e)
        if not detay and tur.__name__ in ("Terminator",):
            return "kaplumbağa penceresi kapatıldı, çizim durduruldu."
        for ing, tr in HATA_MESAJLARI.items():
            detay = re.sub(ing, tr, detay, flags=re.IGNORECASE)
        detay = _TIRNAKLI_TUR.sub(lambda m: f"'{_tr_tur(m.group(1))}' nesnesi", detay)
    return detay


_TK_TUR_ADLARI = {
    "str": "metin", "int": "tamsayı", "float": "ondalıklı", "list": "liste",
    "dict": "sözlük", "tuple": "demet", "set": "küme", "bool": "mantıksal",
    "NoneType": "Hiçlik", "function": "fonksiyon", "builtin_function_or_method":
    "hazır fonksiyon", "method": "metot", "module": "modül", "type": "tür",
    "range": "aralık", "bytes": "bayt dizisi", "complex": "karmaşık sayı",
}


def _tr_ad(ad):
    """Python adının TürKod karşılığı (yoksa adın kendisi)."""
    if not isinstance(ad, str):
        return ad
    return _TK_TERS_ADLAR.get(ad, ad)


_SAYI_SINIRI = {"exactly": "tam", "at most": "en fazla", "at least": "en az"}
# Sık karıştırılan metotlar için ek ipucu (hata mesajının sonuna eklenir).
_METOT_IPUCLARI = {
    "ctime": " Tarihi istediğin biçimde yazmak için tarih_biçimlendir(\"%d.%m.%Y %H:%M\") kullan.",
    "asctime": " Tarihi istediğin biçimde yazmak için tarih_biçimlendir(\"%d.%m.%Y %H:%M\") kullan.",
}


def _metot_adi(ad):
    """'datetime.ctime' -> 'metin_zaman' (yalnızca son parçanın TürKod adı)."""
    return _tr_ad(str(ad).rsplit(".", 1)[-1])


def _metot_ipucu(ad):
    return _METOT_IPUCLARI.get(str(ad).rsplit(".", 1)[-1], "")


def _tr_tur(tur_adi):
    """Tür ADI ('str') -> 'metin'. Bir değerin türü için _deger_turu()."""
    return _TK_TUR_ADLARI.get(tur_adi) or _TK_TERS_ADLAR.get(tur_adi, tur_adi)


def _deger_turu(deger):
    return _tr_tur(type(deger).__name__)


def _ozellik_onerisi(nesne, ad):
    """'liste.ekle' -> 'sona_ekle': nesnenin gerçek özellikleri arasında
    (TürKod adlarıyla) en yakın olanı."""
    try:
        adlar = {}
        for a in dir(nesne):
            if not a.startswith("_"):
                adlar.setdefault(_tr_ad(a), a)
    except Exception:
        return None
    tr = _tr_ad(ad)
    kucuk = tr.casefold()
    for a in adlar:
        if a.casefold() == kucuk and a != tr:
            return a
    bilesik = [a for a in adlar if a.casefold().endswith("_" + kucuk)
               or a.casefold().startswith(kucuk + "_")]
    if bilesik:
        return min(bilesik, key=lambda a: (len(a), a))
    import difflib
    yakin = difflib.get_close_matches(tr, list(adlar), n=1, cutoff=0.7)
    return yakin[0] if yakin else None


_KARSILASTIRMA_HATASI = re.compile(
    r"'(.+?)' not supported between instances of '(\w+)' and '(\w+)'")
_ISLEM_HATASI = re.compile(
    r"unsupported operand type\(s\) for (.+?): '(\w+)' and '(\w+)'")
_TEKLI_ISLEM_HATASI = re.compile(r"bad operand type for unary (.+?): '(\w+)'")
_SAYI_DONUSUM_HATASI = re.compile(
    r"invalid literal for int\(\) with base \d+: (.*)$", re.DOTALL)
_ONDALIK_DONUSUM_HATASI = re.compile(
    r"could not convert string to float: (.*)$", re.DOTALL)
_TIRNAKLI_TUR = re.compile(r"'(\w+)' (object|nesnesi)")
_NESNE_DEGIL = re.compile(r"'(\w+)' object is not (callable|subscriptable|iterable)")
_NESNE_DEGIL_TR = {
    "callable": "fonksiyon gibi çağrılamaz! Sonundaki () fazla olabilir.",
    "subscriptable": "köşeli parantezle [ ] erişilemez (liste/sözlük/metin bekleniyor)!",
    "iterable": "döngüyle tek tek gezilemez (liste, metin ya da aralık(...) bekleniyor)!",
}
_UZUNLUK_YOK = re.compile(r"object of type '(\w+)' has no len\(\)")
_EKSIK_PARAMETRE = re.compile(
    r"(\w+)\(\) missing (\d+) required (?:positional|keyword-only) arguments?: (.+)$")
_FAZLA_PARAMETRE = re.compile(
    r"(\w+)\(\) takes (?:from \d+ to )?(\d+) positional arguments? but (\d+) (?:was|were) given")
_BILINMEYEN_PARAMETRE = re.compile(r"(\w+)\(\) got an unexpected keyword argument '(\w+)'")
_GECERSIZ_PARAMETRE = re.compile(r"'(\w+)' is an invalid keyword argument for (\w+)\(\)")


def _ozel_aciklama(e):
    """Sık görülen hatalar için tam Türkçe açıklama; tanınmazsa None."""
    mesaj = str(e)
    if isinstance(e, NameError) and getattr(e, "name", None):
        if isinstance(e, UnboundLocalError):
            return f"'{_tr_ad(e.name)}' değişkeni değer atanmadan önce kullanıldı!"
        return f"'{_tr_ad(e.name)}' adında bir değişken/fonksiyon tanımlı değil!"
    if isinstance(e, AttributeError) and getattr(e, "name", None):
        nesne = getattr(e, "obj", None)
        ad = _tr_ad(e.name)
        if isinstance(nesne, type(sys)):
            return f"'{_tr_ad(getattr(nesne, '__name__', '?'))}' modülünde '{ad}' adında bir şey yok!"
        if nesne is None and "NoneType" not in mesaj:
            return f"'{ad}' adında bir özellik/metot bulunamadı!"
        return f"{_deger_turu(nesne)} türündeki değerin '{ad}' adında bir özelliği/metodu yok!"
    if (isinstance(e, KeyError) and len(e.args) == 1
            and not str(e.args[0]).startswith("popitem(): ")):
        return f"sözlükte {e.args[0]!r} anahtarı yok! Önce 'içinde' ile kontrol edin ya da .getir() kullanın."
    tam = _tam_mesaj_cevir(mesaj)
    if tam is not None:
        return tam
    m = _NESNE_DEGIL.search(mesaj)
    if m:
        return f"{_tr_tur(m.group(1))} türündeki değer {_NESNE_DEGIL_TR[m.group(2)]}"
    m = _UZUNLUK_YOK.search(mesaj)
    if m:
        return f"{_tr_tur(m.group(1))} türündeki değerin uzunluğu ölçülemez!"
    m = _EKSIK_PARAMETRE.search(mesaj)
    if m:
        eksikler = m.group(3).replace(" and ", ", ")
        return (f"'{_tr_ad(m.group(1))}' fonksiyonuna {m.group(2)} zorunlu değer "
                f"verilmedi: {eksikler}")
    m = _FAZLA_PARAMETRE.search(mesaj)
    if m:
        return (f"'{_tr_ad(m.group(1))}' fonksiyonu {m.group(2)} değer alıyor ama "
                f"{m.group(3)} değer verildi!")
    m = _BILINMEYEN_PARAMETRE.search(mesaj)
    if m:
        return (f"'{_tr_ad(m.group(1))}' fonksiyonunun '{_tr_ad(m.group(2))}' adında "
                f"bir parametresi yok!")
    m = _GECERSIZ_PARAMETRE.search(mesaj)
    if m:
        return (f"'{_tr_ad(m.group(2))}' fonksiyonunun '{_tr_ad(m.group(1))}' adında "
                f"bir parametresi yok!")
    m = _KARSILASTIRMA_HATASI.search(mesaj)
    if m:
        return (f"'{m.group(1)}' karşılaştırması {_tr_tur(m.group(2))} ile "
                f"{_tr_tur(m.group(3))} arasında yapılamaz! İki tarafı da aynı türe çevirin "
                f"(örn. tamsayı(...)).")
    m = _ISLEM_HATASI.search(mesaj)
    if m:
        return (f"'{m.group(1)}' işlemi {_tr_tur(m.group(2))} ile "
                f"{_tr_tur(m.group(3))} arasında yapılamaz!")
    m = _TEKLI_ISLEM_HATASI.search(mesaj)
    if m:
        return f"'{m.group(1)}' işareti {_tr_tur(m.group(2))} türüne uygulanamaz!"
    m = _SAYI_DONUSUM_HATASI.search(mesaj)
    if m:
        return f"{m.group(1)} değeri tamsayıya dönüştürülemiyor! Yalnızca rakam içermeli."
    m = _ONDALIK_DONUSUM_HATASI.search(mesaj)
    if m:
        return f"{m.group(1)} değeri ondalıklı sayıya dönüştürülemiyor!"
    return None

_METIN_OZELLIK_HATASI = re.compile(r"'(\w+)' object has no attribute '(\w+)'")
_METIN_MODUL_HATASI = re.compile(r"module '([\w.]+)' has no attribute '(\w+)'")
_METIN_AD_HATASI = re.compile(r"name '(\w+)' is not defined")


def turkce_hata_aciklamasi(tip, mesaj):
    """Yalnızca hata türü ve İngilizce metin bilinirken (ör. ayrı süreçte
    çalışan kodun stderr'i) Türkçe açıklama üretir."""
    mesaj = mesaj or ""
    m = _METIN_AD_HATASI.search(mesaj)
    if tip in ("NameError", "UnboundLocalError") and m:
        return f"'{_tr_ad(m.group(1))}' adında bir değişken/fonksiyon tanımlı değil!"
    m = _METIN_MODUL_HATASI.search(mesaj)
    if tip == "AttributeError" and m:
        return f"'{_tr_ad(m.group(1))}' modülünde '{_tr_ad(m.group(2))}' adında bir şey yok!"
    m = _METIN_OZELLIK_HATASI.search(mesaj)
    if tip == "AttributeError" and m:
        return (f"{_tr_tur(m.group(1))} türündeki değerin '{_tr_ad(m.group(2))}' adında "
                f"bir özelliği/metodu yok!")
    if tip == "KeyError" and mesaj and "popitem(): " not in mesaj:
        return f"sözlükte {mesaj} anahtarı yok! Önce 'içinde' ile kontrol edin ya da .getir() kullanın."
    try:
        aciklama = _ozel_aciklama(Exception(mesaj))
    except Exception:
        aciklama = None
    if aciklama is None:
        aciklama = mesaj
        for ing, tr in HATA_MESAJLARI.items():
            aciklama = re.sub(ing, tr, aciklama, flags=re.IGNORECASE)
        aciklama = _TIRNAKLI_TUR.sub(lambda m: f"'{_tr_tur(m.group(1))}' nesnesi", aciklama)
    return aciklama
'''

RUNNER_ORTAK = RUNNER_ORTAK.replace("#@HATA_ACIKLAMA_KODU@", HATA_ACIKLAMA_KODU, 1)

try:
    from .deger_sozlugu import calisma_tablolari
except ImportError:
    from deger_sozlugu import calisma_tablolari

RUNNER_ORTAK = RUNNER_ORTAK.replace(
    "_TK_DEGERLER = {}", f"_TK_DEGERLER = {calisma_tablolari()!r}", 1)


RUNNER_KODU = RUNNER_ORTAK + r'''
try:
    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:
        kod = f.read()
    # Ayrı ad alanı: kullanıcının "re = 5" gibi bir değişkeni çalıştırıcının
    # kendi modüllerini (re, sys, traceback) ezip Türkçe hata çıktısını
    # bozamaz.
    # Ad alanı gerçek bir __main__ modülüdür ve sys.modules'a kaydedilir:
    # yalnızca düz bir sözlük kullanıldığında pickle, unittest.main() ve
    # doctest kullanıcının sınıflarını/testlerini "__main__"de bulamıyordu.
    import types as _types
    _ana = _types.ModuleType("__main__")
    _ana.__file__ = os.path.abspath("turkce_kod_calisma.py")
    _ana.__builtins__ = builtins
    sys.modules["__main__"] = _ana
    exec(compile(kod, "turkce_kod_calisma.py", "exec"), _ana.__dict__)
except KeyboardInterrupt:
    # Konsolda Ctrl+C: İngilizce traceback yerine kısa bir Türkçe mesaj.
    print("\n[Program durduruldu (Ctrl+C)]")
    sys.exit(130)
except Exception as e:
    _hata_yazdir(e, sys.exc_info()[2], "turkce_kod_calisma.py")
    # Python gibi: yakalanmamış hata 1 çıkış koduyla biter (eskiden 0 dönüyor,
    # IDE hatalı programı başarılı bitmiş sayıyordu).
    sys.exit(1)
'''


def _oneri_kelimeleri():
    try:
        try:
            from .dictionary import TURKCE_KELIMELER
        except ImportError:
            from dictionary import TURKCE_KELIMELER
        return sorted({str(k) for k in TURKCE_KELIMELER if str(k).isidentifier()})
    except Exception:
        return []


def _modul_adlari():
    """Türkçe modül adları ("matematik", "rastgele" ...)."""
    try:
        try:
            from .converter import MODUL_CEVIRILERI
        except ImportError:
            from converter import MODUL_CEVIRILERI
        adlar = set(MODUL_CEVIRILERI) | set(MODUL_CEVIRILERI.values())
        return sorted(k for k in adlar if isinstance(k, str) and k.isidentifier())
    except Exception:
        return []


def _ters_adlar(kaynak_kod=None):
    """Python adı -> TürKod kelimesi. Kaynakta İngilizce adın kendisi
    yazılmışsa (TürKod düz Python'u da kabul eder) o ad çevrilmez."""
    try:
        try:
            from .dictionary import TERS_SOZLUK
        except ImportError:
            from dictionary import TERS_SOZLUK
    except Exception:
        return {}
    import re as _re
    yazilanlar = set(_re.findall(r"\w+", kaynak_kod)) if kaynak_kod else set()
    return {py: tr for py, tr in TERS_SOZLUK.items()
            if isinstance(py, str) and isinstance(tr, str) and py != tr
            and py.isidentifier() and tr.isidentifier() and py not in yazilanlar}


_KUTUPHANE_HATA_ADLARI = None
_HATA_SINIFI_DESENI = None


def _kutuphane_hata_adlari():
    """"kök_paket.SınıfAdı" -> Türkçe sınıf adı, modül sözlüğünden
    ("selenium.TimeoutException" -> "ZamanAşımıHatası"). Bir kez kurulur."""
    global _KUTUPHANE_HATA_ADLARI, _HATA_SINIFI_DESENI
    if _KUTUPHANE_HATA_ADLARI is None:
        import re as _re
        _HATA_SINIFI_DESENI = _re.compile(
            r"(?:Error|Exception|Warning|Timeout|Exit|Interrupt|Abort|Failure|Terminator)$")
        sonuc = {}
        try:
            try:
                from .converter import MODUL_METOT_TABLO
            except ImportError:
                from converter import MODUL_METOT_TABLO
        except Exception:
            MODUL_METOT_TABLO = {}
        for tr, py in MODUL_METOT_TABLO.items():
            if "." not in py:
                continue
            ad = py.rsplit(".", 1)[1]
            tr_ad = tr.rsplit(".", 1)[1]
            if not tr_ad[:1].isupper() or not (_HATA_SINIFI_DESENI.search(ad) or ad == "error"):
                continue
            # İlk yazılan kazanır: tablolarda kanonik (aksanlı) ad ASCII yazımdan önce gelir.
            sonuc.setdefault(f"{py.split('.')[0]}.{ad}", tr_ad)
        _KUTUPHANE_HATA_ADLARI = sonuc
    return _KUTUPHANE_HATA_ADLARI


_HATA_ACIKLAMA_AD_ALANI = None


def hata_aciklamasi(tip, mesaj, kaynak_kod=None):
    """('NameError', "name 'number' is not defined") -> Türkçe açıklama
    ("'sayı' adında bir değişken/fonksiyon tanımlı değil!")."""
    global _HATA_ACIKLAMA_AD_ALANI
    if _HATA_ACIKLAMA_AD_ALANI is None:
        import re as _re
        import sys as _sys
        ad_alani = {"re": _re, "sys": _sys, "_TK_TERS_ADLAR": {}}
        exec(HATA_ACIKLAMA_KODU, ad_alani)
        ad_alani["_TK_HATA_ADLARI"] = _kutuphane_hata_adlari()
        _HATA_ACIKLAMA_AD_ALANI = ad_alani
    _HATA_ACIKLAMA_AD_ALANI["_TK_TERS_ADLAR"] = _ters_adlar(kaynak_kod)
    try:
        return _HATA_ACIKLAMA_AD_ALANI["turkce_hata_aciklamasi"](tip, mesaj)
    except Exception:
        return mesaj


def hata_turu_adi(tip):
    """Yalnızca adı bilinen hata türü ('ValueError', 'cv2.error',
    'selenium.common.exceptions.TimeoutException') -> Türkçe ad."""
    if _HATA_ACIKLAMA_AD_ALANI is None:
        hata_aciklamasi(tip, "")
    ad_alani = _HATA_ACIKLAMA_AD_ALANI
    if tip in ad_alani["HATA_ISIMLERI"]:
        return ad_alani["HATA_ISIMLERI"][tip]
    modul, _, ad = tip.rpartition(".")
    if not modul:
        return tip
    kok = modul.split(".")[0]
    gorunen = ad_alani["_KUTUPHANE_GORUNEN_ADLAR"].get(kok, kok)
    tr = _kutuphane_hata_adlari().get(f"{kok}.{ad}")
    if tr:
        return f"{ad_alani['_bosluklu'](tr)} ({gorunen})"
    if ad.lower() == "error":
        return f"{gorunen} Hatası"
    return tip


def program_ikonu_yolu():
    """Çalışan programın pencerelerine verilen TürKod program simgesi.
    Paketli derlemede <_MEIPASS>\\program-logo.ico (turkod_backend.spec)."""
    import os
    import sys
    if getattr(sys, "frozen", False):
        kok = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        kok = os.path.dirname(os.path.abspath(__file__))
    yol = os.path.join(kok, "program-logo.ico")
    return yol if os.path.isfile(yol) else None


def oneri_tablolarini_yerlestir(govde, kaynak_kod=None):
    """Çalıştırıcı şablonundaki boş öneri/çeviri tablolarını doldurur
    (normal çalıştırıcı ve hata ayıklayıcı aynı hata yazıcısını kullanır)."""
    govde = govde.replace(
        "_TK_PROGRAM_IKONU = None", f"_TK_PROGRAM_IKONU = {program_ikonu_yolu()!r}", 1)
    govde = govde.replace(
        "_TK_ONERI_KELIMELERI = []",
        f"_TK_ONERI_KELIMELERI = {_oneri_kelimeleri()!r}", 1)
    govde = govde.replace(
        "_TK_MODUL_ADLARI = []",
        f"_TK_MODUL_ADLARI = {_modul_adlari()!r}", 1)
    govde = govde.replace(
        "_TK_HATA_ADLARI = {}",
        f"_TK_HATA_ADLARI = {_kutuphane_hata_adlari()!r}", 1)
    return govde.replace(
        "_TK_TERS_ADLAR = {}",
        f"_TK_TERS_ADLAR = {_ters_adlar(kaynak_kod)!r}", 1)


def runner_kodu_uret(kod_yolu, program_yolu=None, calisma_dizini=None,
                     ek_yollar=(), kaynak_kod=None):
    """Çalıştırıcı betiği üretir.

    kod_yolu: çevrilmiş Python kodunun mutlak yolu (geçici klasörde).
    program_yolu: kullanıcının .trpy dosyası (varsa); __file__ ve sys.argv[0]
        onu gösterir.
    calisma_dizini: modül arama yoluna eklenecek kullanıcı klasörü.
    ek_yollar: sys.path'in en başına eklenecek klasörler (çevrilmiş yerel
        .trpy modüllerinin bulunduğu geçici klasör).
    kaynak_kod: kullanıcının TürKod kodu (varsa); hata mesajlarında hangi
        adların TürKod karşılığıyla gösterileceğini belirler.
    """
    yollar = [y for y in ek_yollar if y]
    if calisma_dizini:
        yollar.append(calisma_dizini)
    on = "import sys as _ts\n"
    if program_yolu:
        on += f"_ts.argv = [{program_yolu!r}] + _ts.argv[1:]\n"
    if yollar:
        on += f"_ts.path[0:1] = {yollar!r}\n"
    on += "del _ts\n"
    govde = oneri_tablolarini_yerlestir(RUNNER_KODU, kaynak_kod)
    if program_yolu:
        govde = govde.replace(
            '_ana.__file__ = os.path.abspath("turkce_kod_calisma.py")',
            f"_ana.__file__ = {program_yolu!r}")
    return on + govde.replace('"turkce_kod_calisma.py"', repr(kod_yolu))
