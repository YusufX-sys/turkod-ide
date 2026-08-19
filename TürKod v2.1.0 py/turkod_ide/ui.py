"""Windows 11 UI yardimcilari."""
import os
import tkinter as tk
import tkinter.font as tkfont


def win11_uygula(widget):
    """Win11: koyu başlık çubuğu + yuvarlatılmış köşeler.

    Not: SYSTEMBACKDROP_TYPE (attr 38, Mica) bilinçli olarak
    uygulanmıyor. Tk, DWM backdrop'unu kendi arka planıyla
    yeniden çizmediği için canlı yeniden boyutlandırmada siyah
    bölgeler ve çift çizilen parçalar üretiyordu.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        dwm = ctypes.windll.dwmapi
        hwndlar = {widget.winfo_id(),
                   ctypes.windll.user32.GetParent(widget.winfo_id())}

        def attr(hwnd, no, deger):
            v = ctypes.c_int(deger)
            dwm.DwmSetWindowAttribute(hwnd, no, ctypes.byref(v), ctypes.sizeof(v))

        for hwnd in hwndlar:
            attr(hwnd, 20, 1)   # USE_IMMERSIVE_DARK_MODE
            attr(hwnd, 33, 2)   # WINDOW_CORNER_PREFERENCE = ROUND
    except Exception:
        pass


def ui_font(buyukluk=10, bold=False):
    try:
        aileler = set(tkfont.families())
    except RuntimeError:
        aileler = set()

    aile = "Segoe UI Variable Text" if "Segoe UI Variable Text" in aileler else "Segoe UI"
    return (aile, buyukluk, "bold" if bold else "normal")


# === FONT KONTROLÜ İÇİN GEÇİCİ ROOT PENCERESİ ===
# tkfont.families() aktif bir root penceresi gerektirir; modül import
# edilirken henüz ana pencere yok, bu yüzden geçici bir tane aç-kapat.
_temp_root = tk.Tk()
_temp_root.withdraw()
try:
    _mevcut_fontlar = set(tkfont.families())
except Exception:
    _mevcut_fontlar = set()
finally:
    # ttk, yorumlayıcı sökümü sırasında <<ThemeChanged>> üretip yok olmuş
    # pencereye event generate edebilir; prosedürü şimdiden etkisizleştir.
    try:
        _temp_root.tk.eval("proc ttk::ThemeChanged args {}")
    except Exception:
        pass
    _temp_root.destroy()

if "Segoe MDL2 Assets" in _mevcut_fontlar:
    ICON_FONT = ("Segoe MDL2 Assets", 15)

    WIN11_IKON = {
        "calistir": "\uE768", "ac": "\uE8B7", "kaydet": "\uE74E",
        "yeni": "\uE710", "cevir": "\uE895", "gezgin": "\uE8B7",
        "ai": "\uE8BD", "ayarlar": "\uE713", "terminal": "\uE756",
        "cop": "\uE74D", "kapat": "\uE8BB", "kopyala":  "\uE8C8",
    }
else:  # Windows dışı veya font bulunamadıysa fallback
    ICON_FONT = ("Segoe UI", 11)
    WIN11_IKON = {
        "calistir": "▶", "ac": "📂", "kaydet": "💾",
        "yeni": "＋", "cevir": "🔄", "gezgin": "📁",
        "ai": "🤖", "ayarlar": "⚙", "terminal": "🖥",
        "cop": "🗑", "kapat": "×", "kopyala": "⧉"
    }
