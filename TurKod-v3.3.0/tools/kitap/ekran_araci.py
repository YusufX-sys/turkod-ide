"""Kitaptaki ekran görüntüleri için TürKod IDE'yi başlatır, yönetir ve yakalar.

Yalnızca Windows; ek kütüphane olarak Pillow ister. Komutlar (proje kökünde):

    python tools/kitap/ekran_araci.py baslat <exe> <profil_klasoru>
    python tools/kitap/ekran_araci.py yakala <cikti.png> [x0 y0 x1 y1]
    python tools/kitap/ekran_araci.py tikla <x> <y> [sag|cift]
    python tools/kitap/ekran_araci.py tus ctrl+shift+p      (birden çok: tus esc esc)
    python tools/kitap/ekran_araci.py tekerlek <x> <y> <adım>   (adım < 0: aşağı)
    python tools/kitap/ekran_araci.py surukle <x1> <y1> <x2> <y2>
    python tools/kitap/ekran_araci.py yaz "metin"
    python tools/kitap/ekran_araci.py yapistir <dosya_ya_da_metin>   (kod için)
    python tools/kitap/ekran_araci.py kapat

Koordinatlar pencerenin sol üst köşesine göredir (fiziksel piksel). Pencere
her komutta öne getirilir ve PENCERE boyutuna ayarlanır, böylece görüntüler hep
aynı boyutta çıkar. "baslat", ayarları TURKOD_TEST_PROFIL ile verilen klasörde
tutar: kullanıcının gerçek ayarlarına ve oturumuna dokunulmaz.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

from PIL import ImageGrab

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u32 = ctypes.windll.user32
PENCERE = (0, 0, 1440, 900)       # x, y, genişlik, yükseklik (fiziksel piksel)
BASLIK = "TürKod"


def pencere_bul():
    bulunan = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            sinif = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(hwnd, sinif, 256)
            if BASLIK in buf.value and sinif.value == "FLUTTER_RUNNER_WIN32_WINDOW":
                bulunan.append(hwnd)
        return True

    u32.EnumWindows(cb, 0)
    return bulunan[0] if bulunan else None


def one_getir():
    hwnd = pencere_bul()
    if not hwnd:
        raise SystemExit("TürKod penceresi bulunamadı")
    u32.ShowWindow(hwnd, 9)  # SW_RESTORE
    x, y, w, h = PENCERE
    u32.MoveWindow(hwnd, x, y, w, h, True)
    # Arka plandaki bir süreç öne getiremeyebilir; Alt tuşu kilidi açar.
    u32.keybd_event(0x12, 0, 0, 0)
    u32.SetForegroundWindow(hwnd)
    u32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.25)
    return hwnd


def dikdortgen(hwnd):
    r = wt.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


TUSLAR = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "space": 0x20, "bosluk": 0x20, "back": 0x08, "del": 0x2E, "up": 0x26, "down": 0x28, "left": 0x25,
    "right": 0x27, "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    "/": 0xBF, "\\": 0xDC, "=": 0xBB, "-": 0xBD,
}


_GENIS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F}  # ok tuşları vb.


def _tus_olayi(vk, birak):
    # Flutter kısayolları tarama koduna (scan code) bakar; keybd_event'e
    # yalnızca sanal tuş kodu verilirse Ctrl+T gibi birleşimler algılanmaz.
    tarama = u32.MapVirtualKeyW(vk, 0)
    bayrak = (0x0002 if birak else 0) | (0x0001 if vk in _GENIS else 0)
    u32.keybd_event(vk, tarama, bayrak, 0)


def tus(birlesim):
    parcalar = birlesim.lower().split("+")
    kodlar = [TUSLAR.get(p) or ord(p.upper()) for p in parcalar]
    for k in kodlar:
        _tus_olayi(k, False)
        time.sleep(0.03)
    for k in reversed(kodlar):
        _tus_olayi(k, True)
        time.sleep(0.03)


def panoya_koy(metin):
    k32 = ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    veri = metin.encode("utf-16-le") + b"\0\0"
    h = k32.GlobalAlloc(0x0002, len(veri))
    ctypes.memmove(k32.GlobalLock(h), veri, len(veri))
    k32.GlobalUnlock(h)
    for _ in range(10):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    u32.EmptyClipboard()
    u32.SetClipboardData(13, h)  # CF_UNICODETEXT
    u32.CloseClipboard()


def yapistir(metin):
    """Kodu panodan yapıştırır: harf harf yazınca editörün otomatik parantez
    kapatması ve girinti eklemesi metni bozar."""
    panoya_koy(metin)
    tus("ctrl+v")


class _KI(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _GIRDI(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KI), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def yaz(metin):
    """Unicode karakterleri (Türkçe harfler dahil) klavyeden yazar."""
    for ch in metin:
        if ch == "\n":
            tus("enter")
            continue
        for bayrak in (0x0004, 0x0004 | 0x0002):  # KEYEVENTF_UNICODE, +KEYUP
            g = _GIRDI(type=1)
            g.ki = _KI(0, ord(ch), bayrak, 0, None)
            u32.SendInput(1, ctypes.byref(g), ctypes.sizeof(g))
        time.sleep(0.01)


def tikla(x, y, tur=""):
    hwnd = one_getir()
    l, t, _, _ = dikdortgen(hwnd)
    u32.SetCursorPos(l + x, t + y)
    time.sleep(0.1)
    asagi, yukari = (0x0008, 0x0010) if tur == "sag" else (0x0002, 0x0004)
    for _ in range(2 if tur == "cift" else 1):
        u32.mouse_event(asagi, 0, 0, 0, 0)
        u32.mouse_event(yukari, 0, 0, 0, 0)
        time.sleep(0.05)


def surukle(x1, y1, x2, y2):
    """Fareyle sürükler (ör. panel kenarını büyütmek için)."""
    hwnd = one_getir()
    l, t, _, _ = dikdortgen(hwnd)
    u32.SetCursorPos(l + x1, t + y1)
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    for i in range(1, 21):
        u32.SetCursorPos(l + x1 + (x2 - x1) * i // 20, t + y1 + (y2 - y1) * i // 20)
        time.sleep(0.02)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def tekerlek(x, y, adim):
    """(x, y) üzerinde fare tekerleğini çevirir; adim < 0 aşağı kaydırır."""
    hwnd = one_getir()
    l, t, _, _ = dikdortgen(hwnd)
    u32.SetCursorPos(l + x, t + y)
    time.sleep(0.1)
    for _ in range(abs(adim)):
        u32.mouse_event(0x0800, 0, 0, 120 if adim > 0 else -120, 0)
        time.sleep(0.05)


def yakala(cikti, kirp=None):
    hwnd = one_getir()
    l, t, r, b = dikdortgen(hwnd)
    resim = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    if kirp:
        resim = resim.crop(kirp)
    resim.save(cikti)
    print(f"{cikti}: {resim.size[0]}x{resim.size[1]}")


def baslat(exe, profil):
    env = dict(os.environ, TURKOD_TEST_PROFIL=os.path.abspath(profil))
    subprocess.Popen([exe], env=env, cwd=os.path.dirname(exe))
    for _ in range(120):
        if pencere_bul():
            break
        time.sleep(0.5)
    one_getir()
    print("başlatıldı")


def kapat():
    hwnd = pencere_bul()
    if hwnd:
        u32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    komut, *a = sys.argv[1:]
    if komut == "baslat":
        baslat(*a)
    elif komut == "yakala":
        yakala(a[0], tuple(int(v) for v in a[1:5]) if len(a) >= 5 else None)
    elif komut == "tikla":
        tikla(int(a[0]), int(a[1]), a[2] if len(a) > 2 else "")
    elif komut == "surukle":
        surukle(*(int(v) for v in a[:4]))
    elif komut == "tekerlek":
        tekerlek(int(a[0]), int(a[1]), int(a[2]))
    elif komut == "tus":
        one_getir()
        for t in a:
            tus(t)
            time.sleep(0.15)
    elif komut == "yaz":
        one_getir()
        yaz(a[0])
    elif komut == "yapistir":
        one_getir()
        yapistir(open(a[0], encoding="utf-8").read() if os.path.isfile(a[0]) else a[0])
    elif komut == "kapat":
        kapat()
    else:
        raise SystemExit(__doc__)
