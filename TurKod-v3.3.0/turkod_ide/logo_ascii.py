"""TürKod logosunu terminali dolduracak büyüklükte ASCII karakterlerle çizer.

TürKod Terminali'nde (kabuk) `logo` komutu, IDE terminalinde `turkod logo`
kullanır. Veri logo_verisi.py'dedir (tools/logo_ascii_uret.py üretir);
Pillow gerekmez.
"""
import base64
import shutil
import zlib

try:
    from .logo_verisi import BOYUT, VERI
except ImportError:  # turkod_ide klasörü sys.path'teyken
    from logo_verisi import BOYUT, VERI

# Koyudan parlağa: logo koyu terminal zemininde parlak çizilir.
RAMPA = ".:-=+*#%@"
# Bir karakter hücresi yaklaşık iki kat uzundur: kare logo, satır sayısının
# iki katı genişlikte çizilir.
HUCRE_ORANI = 2.0

_PIKSELLER = None


def _pikseller():
    global _PIKSELLER
    if _PIKSELLER is None:
        _PIKSELLER = zlib.decompress(base64.b64decode("".join(VERI)))
    return _PIKSELLER


def boyut_hesapla(sutun, satir):
    """(genişlik, yükseklik) karakter: logo terminalin yüksekliğini doldurur,
    sığmazsa genişliğe göre küçülür. Son satır istem için boş kalır."""
    yukseklik = max(4, satir - 1)
    genislik = int(round(yukseklik * HUCRE_ORANI))
    if genislik > sutun - 1:
        genislik = max(8, sutun - 1)
        yukseklik = max(4, int(round(genislik / HUCRE_ORANI)))
    return genislik, yukseklik


def _hucre(px, x0, x1, y0, y1):
    """Kutudaki piksellerin ortalaması: (r, g, b, kaplama 0-1)."""
    r = g = b = a = 0
    n = 0
    # Büyük kutularda en çok 4x4 örnek (hız).
    adim_x = max(1, (x1 - x0) // 4)
    adim_y = max(1, (y1 - y0) // 4)
    for y in range(y0, y1, adim_y):
        satir = y * BOYUT
        for x in range(x0, x1, adim_x):
            i = (satir + x) * 4
            al = px[i + 3]
            r += px[i] * al
            g += px[i + 1] * al
            b += px[i + 2] * al
            a += al
            n += 1
    if not a:
        return 0, 0, 0, 0.0
    return r // a, g // a, b // a, a / (255.0 * n)


def ciz(sutun=None, satir=None, renkli=False):
    """Logo satırları (liste). sutun/satir verilmezse terminalin boyutu
    kullanılır (COLUMNS/LINES ortam değişkenleri de geçerlidir)."""
    if not sutun or not satir:
        olcu = shutil.get_terminal_size(fallback=(80, 24))
        sutun, satir = sutun or olcu.columns, satir or olcu.lines
    genislik, yukseklik = boyut_hesapla(int(sutun), int(satir))
    px = _pikseller()
    bosluk = " " * max(0, (int(sutun) - 1 - genislik) // 2)
    satirlar = []
    for cy in range(yukseklik):
        y0 = cy * BOYUT // yukseklik
        y1 = max(y0 + 1, (cy + 1) * BOYUT // yukseklik)
        parcalar = []
        son_renk = None
        for cx in range(genislik):
            x0 = cx * BOYUT // genislik
            x1 = max(x0 + 1, (cx + 1) * BOYUT // genislik)
            r, g, b, kaplama = _hucre(px, x0, x1, y0, y1)
            if kaplama < 0.12:
                parcalar.append(" ")
                continue
            parlaklik = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            yogunluk = min(1.0, kaplama * (0.35 + 0.65 * parlaklik))
            harf = RAMPA[min(len(RAMPA) - 1, int(yogunluk * len(RAMPA)))]
            if renkli:
                renk = (r, g, b)
                if renk != son_renk:
                    parcalar.append(f"\x1b[38;2;{r};{g};{b}m")
                    son_renk = renk
            parcalar.append(harf)
        metin = "".join(parcalar).rstrip()
        if renkli and son_renk is not None:
            metin += "\x1b[0m"
        satirlar.append(bosluk + metin if metin.strip() else "")
    # Üstteki ve alttaki boş satırlar korunur (logo dikeyde de ortalı kalır).
    return satirlar
