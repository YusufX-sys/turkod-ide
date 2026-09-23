"""Kurulum sihirbazı görsellerini üretir (Pillow gerekir).

    python sihirbaz_gorsel_uret.py

Çıktı (sihirbaz\\ klasörüne):
    sihirbaz.bmp / sihirbaz_200.bmp   sol büyük görsel  (164x314 ve iki kat)
    logo.bmp / logo_200.bmp           sağ üst küçük logo (55x55 ve iki kat)

Renkleri ve yazıları aşağıdaki ayarlardan değiştir; ya da kendi görsellerini
aynı adlarla bu klasöre koy (BMP, 24 bit).
"""
import os
from PIL import Image, ImageDraw, ImageFont

ARKA_PLAN = (15, 23, 42)      # koyu lacivert
VURGU = (46, 204, 113)        # yeşil
YAZI = (241, 245, 249)
SOLUK = (148, 163, 184)
BASLIK = "TürKod"
ALT_BASLIK = "Türkçe Python IDE"
SEMBOL = ">_"

YAZI_TIPLERI = [
    r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
YAZI_TIPLERI_NORMAL = [
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
SS = 4  # süper örnekleme: daha yumuşak kenarlar


def yazi_tipi(adaylar, boyut):
    for yol in adaylar:
        if os.path.exists(yol):
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default()


def sembol_kutusu(d, x, y, kenar, olcek):
    """Yeşil yuvarlak kare + '>_' sembolü."""
    d.rounded_rectangle([x, y, x + kenar, y + kenar], radius=kenar // 5, fill=VURGU)
    f = yazi_tipi(YAZI_TIPLERI, int(kenar * 0.52))
    kutu = d.textbbox((0, 0), SEMBOL, font=f)
    w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
    d.text((x + (kenar - w) / 2 - kutu[0], y + (kenar - h) / 2 - kutu[1]), SEMBOL, font=f, fill=ARKA_PLAN)


def buyuk(genislik, yukseklik, dosya):
    k = genislik / 164.0
    W, H = int(genislik * SS), int(yukseklik * SS)
    im = Image.new("RGB", (W, H), ARKA_PLAN)
    d = ImageDraw.Draw(im)
    ks = k * SS
    # üstte ince yeşil çizgi
    d.rectangle([0, 0, W, int(6 * ks)], fill=VURGU)
    kenar = int(64 * ks)
    sembol_kutusu(d, int(20 * ks), int(48 * ks), kenar, ks)
    d.text((int(20 * ks), int(130 * ks)), BASLIK, font=yazi_tipi(YAZI_TIPLERI, int(28 * ks)), fill=YAZI)
    d.text((int(20 * ks), int(168 * ks)), ALT_BASLIK, font=yazi_tipi(YAZI_TIPLERI_NORMAL, int(12 * ks)), fill=SOLUK)
    im = im.resize((int(genislik), int(yukseklik)), Image.LANCZOS)
    im.save(dosya, format="BMP")


def kucuk(kenar, dosya):
    W = kenar * SS
    im = Image.new("RGB", (W, W), ARKA_PLAN)
    d = ImageDraw.Draw(im)
    pay = int(W * 0.06)
    sembol_kutusu(d, pay, pay, W - 2 * pay, 1)
    im = im.resize((kenar, kenar), Image.LANCZOS)
    im.save(dosya, format="BMP")


if __name__ == "__main__":
    os.makedirs("sihirbaz", exist_ok=True)
    buyuk(164, 314, os.path.join("sihirbaz", "sihirbaz.bmp"))
    buyuk(328, 628, os.path.join("sihirbaz", "sihirbaz_200.bmp"))
    kucuk(55, os.path.join("sihirbaz", "logo.bmp"))
    kucuk(110, os.path.join("sihirbaz", "logo_200.bmp"))
    print("Görseller sihirbaz\\ klasörüne yazıldı.")
