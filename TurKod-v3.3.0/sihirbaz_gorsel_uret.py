"""Kurulum sihirbazı görsellerini üretir (Pillow gerekir).

    python sihirbaz_gorsel_uret.py

Tasarım, projenin sitesiyle (https://yusufx-sys.github.io/turkod-site/) aynı
görsel dili kullanır: koyu temada #070b16 zemin, açık temada #f5f7fb zemin;
camgöbeği -> çivit -> fuşya gradyanı, yumuşak ışık lekeleri ve alt kısımda
gradyan dalgalar. Logo, uygulamanın kendi ikonu (turkod_ide/turkod.ico).

Çıktı (sihirbaz\\ klasörüne, hepsi PNG):
    arka.png, arka_150.png, arka_200.png              sayfa arka planı, AÇIK tema
    arka_dark.png, arka_dark_150.png, arka_dark_200.png  sayfa arka planı, KOYU tema
    sihirbaz.png ... sihirbaz_250.png                 karşılama/bitiş sayfası sol paneli
    logo.png ... logo_250.png                         sağ üst küçük logo

turkod.iss bunları şöyle kullanır (Inno Setup 6.6+; 6.7.1 ile denendi):
    WizardBackImageFile / WizardBackImageFileDynamicDark  -> arka*.png
    WizardImageFile / WizardSmallImageFile                -> sihirbaz*.png / logo*.png
Inno'da büyük/küçük sihirbaz görselleri için ayrı koyu tema varyantı YOKTUR;
bu yüzden ikisi de saydam PNG olarak üretilir ve her iki temada da okunur
(alttaki arka plan temaya göre değişir).
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

KOK = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(KOK, "sihirbaz")
IKON = os.path.join(KOK, "turkod_ide", "turkod.ico")

BASLIK = "TürKod"
ALT_BASLIK = ["Türkçe Konuşan", "Kodlama Ortamı"]

# Sitedeki renkler
TEMALAR = {
    "": dict(  # açık
        ZEMIN=(245, 247, 251),
        LEKELER=[((0.18, 0.28), 0.55, (34, 211, 238), 0.10),
                 ((0.86, 0.12), 0.45, (232, 121, 249), 0.08),
                 ((0.62, 0.92), 0.65, (99, 102, 241), 0.11),
                 ((0.30, 0.78), 0.35, (16, 185, 129), 0.06)],
        DALGA=[(8, 145, 178), (99, 102, 241), (192, 38, 211)],
        DALGA_OPAK=(0.16, 0.10),
    ),
    "_dark": dict(  # koyu
        ZEMIN=(7, 11, 22),
        LEKELER=[((0.18, 0.28), 0.50, (34, 211, 238), 0.11),
                 ((0.86, 0.12), 0.42, (232, 121, 249), 0.09),
                 ((0.62, 0.92), 0.60, (99, 102, 241), 0.14),
                 ((0.30, 0.78), 0.32, (16, 185, 129), 0.06)],
        DALGA=[(34, 211, 238), (129, 140, 248), (232, 121, 249)],
        DALGA_OPAK=(0.24, 0.16),
    ),
}
# Saydam görsellerde metin: iki temada da okunan gradyan + nötr gri.
YAZI_GRADYAN = [(8, 172, 210), (99, 102, 241), (200, 60, 220)]
ALT_YAZI_RENK = (125, 135, 150)

YAZI_TIPLERI = [
    r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
YAZI_TIPLERI_NORMAL = [
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# Arka plan taban boyutu (100% DPI'deki sihirbaz penceresinin iç alanından
# biraz büyük; Inno görseli pencereye sığdırırken kırpar/ölçekler).
ARKA_TABAN = (720, 560)
# Inno'nun standart görsel boyutları (100% DPI).
PANEL_TABAN = (164, 314)
LOGO_TABAN = 55
OLCEKLER = {"": 1.0, "_125": 1.25, "_150": 1.5, "_175": 1.75, "_200": 2.0,
            "_225": 2.25, "_250": 2.5}
SS = 3  # süper örnekleme (yumuşak kenarlar)


def yazi_tipi(adaylar, boyut):
    for yol in adaylar:
        if os.path.exists(yol):
            return ImageFont.truetype(yol, max(1, int(boyut)))
    return ImageFont.load_default()


def _yatay_gradyan(w, h, renkler):
    """Soldan sağa çok duraklı gradyan (RGB)."""
    satir = Image.new("RGB", (w, 1))
    px = satir.load()
    n = len(renkler) - 1
    for x in range(w):
        t = x / max(1, w - 1) * n
        i = min(int(t), n - 1)
        f = t - i
        a, b = renkler[i], renkler[i + 1]
        px[x, 0] = tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))
    return satir.resize((w, h))


def _leke(w, h, merkez, yaricap, renk, opaklik):
    """Yumuşak radyal ışık lekesi (RGBA katman)."""
    kat = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(kat)
    cx, cy = merkez[0] * w, merkez[1] * h
    r = yaricap * max(w, h)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=int(255 * opaklik))
    kat = kat.filter(ImageFilter.GaussianBlur(r * 0.45))
    renkli = Image.new("RGBA", (w, h), renk + (0,))
    renkli.putalpha(kat)
    return renkli


def _dalga(w, h, taban_y, genlik, faz, renkler, opaklik):
    """Alttan dolu, yatay gradyanlı sinüs dalgası (RGBA katman)."""
    maske = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(maske)
    noktalar = [(0, h)]
    for x in range(0, w + 1, max(1, w // 120)):
        y = taban_y + genlik * math.sin(2 * math.pi * (x / w) * 1.3 + faz)
        noktalar.append((x, y))
    noktalar.append((w, h))
    d.polygon(noktalar, fill=int(255 * opaklik))
    kat = _yatay_gradyan(w, h, renkler + [renkler[0]]).convert("RGBA")
    kat.putalpha(maske)
    return kat


def arka_plan(olcek, ek_ad, tema):
    w, h = int(ARKA_TABAN[0] * olcek), int(ARKA_TABAN[1] * olcek)
    im = Image.new("RGBA", (w, h), tema["ZEMIN"] + (255,))
    for merkez, yaricap, renk, opak in tema["LEKELER"]:
        im = Image.alpha_composite(im, _leke(w, h, merkez, yaricap, renk, opak))
    o1, o2 = tema["DALGA_OPAK"]
    im = Image.alpha_composite(im, _dalga(w, h, h * 0.86, h * 0.035, 0.0, tema["DALGA"], o1))
    im = Image.alpha_composite(im, _dalga(w, h, h * 0.90, h * 0.03, 1.9, tema["DALGA"], o2))
    im.convert("RGB").save(os.path.join(CIKTI, f"arka{ek_ad}.png"), optimize=True)


def _ikon(boyut):
    ico = Image.open(IKON)
    ico.size = max(ico.info.get("sizes", {ico.size}))
    return ico.convert("RGBA").resize((boyut, boyut), Image.LANCZOS)


def _gradyan_yazi(metin, yazi, renkler):
    """Gradyan dolgulu saydam metin görseli."""
    kutu = yazi.getbbox(metin)
    w, h = kutu[2] - kutu[0] + 4, kutu[3] - kutu[1] + 4
    maske = Image.new("L", (w, h), 0)
    ImageDraw.Draw(maske).text((2 - kutu[0], 2 - kutu[1]), metin, font=yazi, fill=255)
    im = _yatay_gradyan(w, h, renkler).convert("RGBA")
    im.putalpha(maske)
    return im


def panel(olcek, ek_ad):
    """Karşılama/bitiş sayfası sol paneli: ışıma + logo + gradyan başlık."""
    k = olcek * SS
    w, h = int(PANEL_TABAN[0] * k), int(PANEL_TABAN[1] * k)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Logonun arkasında çivit/camgöbeği ışıma (iki temada da hoş durur).
    logo_k = int(112 * k)
    lx, ly = (w - logo_k) // 2, int(46 * k)
    isima = Image.new("L", (w, h), 0)
    r = min(logo_k * 0.55, w * 0.30)
    cx, cy = w / 2, ly + logo_k / 2
    ImageDraw.Draw(isima).ellipse([cx - r, cy - r, cx + r, cy + r], fill=110)
    isima = isima.filter(ImageFilter.GaussianBlur(r * 0.45))
    # Panel kenarlarına doğru sıfıra inen maske: ışıma panel sınırında
    # kesilip dikdörtgen bir kenar olarak görünmesin.
    kenar = Image.new("L", (w, h), 0)
    pay = int(w * 0.12)
    ImageDraw.Draw(kenar).rectangle([pay, pay, w - pay, h - pay], fill=255)
    kenar = kenar.filter(ImageFilter.GaussianBlur(pay * 0.6))
    isima = ImageChops.multiply(isima, kenar)
    renkli = Image.new("RGBA", (w, h), (99, 102, 241, 0))
    renkli.putalpha(isima)
    im = Image.alpha_composite(im, renkli)
    im.alpha_composite(_ikon(logo_k), (lx, ly))

    baslik = _gradyan_yazi(BASLIK, yazi_tipi(YAZI_TIPLERI, 30 * k), YAZI_GRADYAN)
    im.alpha_composite(baslik, ((w - baslik.width) // 2, int(176 * k)))

    d = ImageDraw.Draw(im)
    f = yazi_tipi(YAZI_TIPLERI_NORMAL, 11.5 * k)
    y = int(222 * k)
    for satir in ALT_BASLIK:
        kutu = d.textbbox((0, 0), satir, font=f)
        d.text(((w - (kutu[2] - kutu[0])) / 2 - kutu[0], y), satir, font=f,
               fill=ALT_YAZI_RENK + (255,))
        y += int(17 * k)

    # Altta ince gradyan çizgi (sitedeki vurgu şeridi)
    serit = _yatay_gradyan(int(64 * k), max(1, int(3 * k)), YAZI_GRADYAN).convert("RGBA")
    im.alpha_composite(serit, ((w - serit.width) // 2, int(272 * k)))

    hedef = (int(PANEL_TABAN[0] * olcek), int(PANEL_TABAN[1] * olcek))
    im.resize(hedef, Image.LANCZOS).save(os.path.join(CIKTI, f"sihirbaz{ek_ad}.png"), optimize=True)


def logo(olcek, ek_ad):
    kenar = int(LOGO_TABAN * olcek)
    im = Image.new("RGBA", (kenar * SS, kenar * SS), (0, 0, 0, 0))
    pay = int(kenar * SS * 0.04)
    im.alpha_composite(_ikon(kenar * SS - 2 * pay), (pay, pay))
    im.resize((kenar, kenar), Image.LANCZOS).save(os.path.join(CIKTI, f"logo{ek_ad}.png"), optimize=True)


def eski_bmp_temizle():
    """Önceki tasarımın BMP dosyaları artık kullanılmıyor; karışmasın."""
    for ad in os.listdir(CIKTI):
        if ad.lower().endswith(".bmp") and (ad.startswith("sihirbaz") or ad.startswith("logo")):
            os.remove(os.path.join(CIKTI, ad))


if __name__ == "__main__":
    os.makedirs(CIKTI, exist_ok=True)
    eski_bmp_temizle()
    for ek_ad, tema in TEMALAR.items():
        for olcek_ad, olcek in (("", 1.0), ("_150", 1.5), ("_200", 2.0)):
            arka_plan(olcek, f"{ek_ad}{olcek_ad}", tema)
    for olcek_ad, olcek in OLCEKLER.items():
        panel(olcek, olcek_ad)
        logo(olcek, olcek_ad)
    print("Sihirbaz görselleri (açık + koyu tema) sihirbaz\\ klasörüne yazıldı.")
