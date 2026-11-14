"""TürKod simgelerini üretir (Pillow).

1. turkod_ide/terminal-logo.ico  — TürKod Terminali (turkod.exe, Başlat menüsü
   kısayolu, kabuk penceresi): koyu zemin, camgöbeği ">_" istemi, TürKod yıldızı.
2. turkod_ide/editor-logo.ico     — .trpy dosya simgesi: 16–48 px kareler yeniden
   çizilir. Eski küçük kareler 256 px'lik ayrıntılı logodan küçültülmüştü;
   ".trpy" yazısı ve yıldızın ince kenarları 16–32 px'te "çamur" gibi
   görünüyordu. Küçük boyutlar için yazısız, yüksek kontrastlı sade çizim
   kullanılır; 64 px ve üstü özgün tasarım olarak kalır.

Her kare kendi boyutunda (8x örneklemeyle) çizilir; küçültülmez.
Kullanım:  python ikon_uret.py
"""
import math
import os

from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.abspath(__file__))
PAKET = os.path.join(KOK, "turkod_ide")
BOYUTLAR = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
OS = 8  # örnekleme katsayısı

LACIVERT = (11, 21, 48, 255)
LACIVERT2 = (22, 33, 62, 255)
MAVI = (33, 150, 243, 255)
ACIK_MAVI = (100, 181, 246, 255)
CAMGOBEGI = (34, 211, 238, 255)
MOR = (124, 77, 255, 255)
BEYAZ = (241, 245, 249, 255)


def _gradyan(boyut, ust, alt):
    g = Image.new("RGBA", (boyut, boyut))
    p = g.load()
    for y in range(boyut):
        t = y / max(1, boyut - 1)
        renk = tuple(round(ust[i] + (alt[i] - ust[i]) * t) for i in range(4))
        for x in range(boyut):
            p[x, y] = renk
    return g


def _yildiz(cx, cy, r_dis, r_ic):
    noktalar = []
    for i in range(10):
        r = r_dis if i % 2 == 0 else r_ic
        a = -math.pi / 2 + i * math.pi / 5
        noktalar.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return noktalar


def _yildiz_bas(tuval, cx, cy, r_dis, r_ic, ust=CAMGOBEGI, alt=MOR):
    """Yukarıdan aşağı camgöbeği→mor degrade dolgulu yıldız."""
    S = tuval.size[0]
    maske = Image.new("L", (S, S), 0)
    ImageDraw.Draw(maske).polygon(_yildiz(cx, cy, r_dis, r_ic), fill=255)
    tuval.paste(_gradyan(S, ust, alt), (0, 0), maske)


def trpy_kare(boyut):
    """Sade .trpy belge simgesi (16–48 px)."""
    S = boyut * OS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    kenar = max(OS, round(S / 16))
    sol, sag, ust, alt = 0.14 * S, 0.86 * S, 0.04 * S, 0.96 * S
    kat = 0.24 * S
    sayfa = [(sol, ust), (sag - kat, ust), (sag, ust + kat), (sag, alt), (sol, alt)]
    d.polygon(sayfa, fill=LACIVERT)
    d.line(sayfa + [sayfa[0]], fill=MAVI, width=kenar, joint="curve")
    d.polygon([(sag - kat, ust), (sag - kat, ust + kat), (sag, ust + kat)], fill=ACIK_MAVI)
    # Yıldız büyük ve dolu: küçük boyutta da net seçilir.
    _yildiz_bas(im, 0.5 * S, 0.57 * S, 0.30 * S, 0.13 * S)
    return im.resize((boyut, boyut), Image.LANCZOS)


def terminal_kare(boyut):
    """TürKod Terminali: yuvarlak köşeli koyu kare, ">_" ve yıldız."""
    S = boyut * OS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    maske = Image.new("L", (S, S), 0)
    pay = 0.05 * S
    yaricap = 0.2 * S
    ImageDraw.Draw(maske).rounded_rectangle((pay, pay, S - pay, S - pay), yaricap, fill=255)
    im.paste(_gradyan(S, LACIVERT2, LACIVERT), (0, 0), maske)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pay, pay, S - pay, S - pay), yaricap, outline=CAMGOBEGI,
                        width=max(OS, round(S / 22)))
    kalin = max(OS * 1.5, S / 9)
    # ">" istemi
    d.line([(0.22 * S, 0.40 * S), (0.42 * S, 0.56 * S), (0.22 * S, 0.72 * S)],
           fill=CAMGOBEGI, width=round(kalin), joint="curve")
    # "_" imleci
    d.rectangle((0.50 * S, 0.66 * S, 0.76 * S, 0.66 * S + kalin * 0.8), fill=BEYAZ)
    if boyut >= 24:
        _yildiz_bas(im, 0.70 * S, 0.30 * S, 0.17 * S, 0.075 * S)
    return im.resize((boyut, boyut), Image.LANCZOS)


YESIL = (74, 222, 128, 255)


def program_kare(boyut):
    """Çalışan TürKod programı (IDE'den çalıştırılan programın pencereleri):
    Terminal simgesiyle aynı çerçeve, büyük TürKod yıldızı ve "çalışıyor"
    anlamında yeşil oynat rozeti. Görev çubuğunda Python simgesinin yerini alır."""
    S = boyut * OS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    maske = Image.new("L", (S, S), 0)
    pay = 0.05 * S
    yaricap = 0.2 * S
    ImageDraw.Draw(maske).rounded_rectangle((pay, pay, S - pay, S - pay), yaricap, fill=255)
    im.paste(_gradyan(S, LACIVERT2, LACIVERT), (0, 0), maske)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pay, pay, S - pay, S - pay), yaricap, outline=CAMGOBEGI,
                        width=max(OS, round(S / 22)))
    if boyut < 24:
        # Küçük boyutta yalnızca büyük yıldız: rozet "çamur" gibi görünürdü.
        _yildiz_bas(im, 0.5 * S, 0.53 * S, 0.36 * S, 0.16 * S)
    else:
        _yildiz_bas(im, 0.44 * S, 0.47 * S, 0.33 * S, 0.145 * S)
        # Oynat rozeti: sağ altta, çerçeveyle aynı koyu halkalı yeşil daire.
        cx, cy, r = 0.71 * S, 0.71 * S, 0.19 * S
        d.ellipse((cx - r - 0.035 * S, cy - r - 0.035 * S, cx + r + 0.035 * S,
                   cy + r + 0.035 * S), fill=LACIVERT)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=YESIL)
        u = 0.085 * S
        d.polygon([(cx - u * 0.75, cy - u), (cx - u * 0.75, cy + u), (cx + u * 1.1, cy)],
                  fill=LACIVERT)
    return im.resize((boyut, boyut), Image.LANCZOS)


def ico_yaz(yol, kareler):
    sirali = [kareler[b] for b in BOYUTLAR]
    sirali[-1].save(yol, format="ICO", sizes=[(b, b) for b in BOYUTLAR],
                    append_images=sirali[:-1])
    print(f"{os.path.relpath(yol, KOK)}: {os.path.getsize(yol) // 1024} KB")


def main():
    ico_yaz(os.path.join(PAKET, "terminal-logo.ico"),
            {b: terminal_kare(b) for b in BOYUTLAR})
    ico_yaz(os.path.join(PAKET, "program-logo.ico"),
            {b: program_kare(b) for b in BOYUTLAR})
    # pygame.display.set_icon bu .ico biçimini okuyamıyor ("Unsupported ICO
    # bitmap format"); pygame pencereleri için aynı simgenin PNG hâli.
    program_kare(64).save(os.path.join(PAKET, "program-logo.png"))

    editor = os.path.join(PAKET, "editor-logo.ico")
    kaynak = Image.open(editor)
    kareler = {}
    for b in BOYUTLAR:
        if b <= 48:
            kareler[b] = trpy_kare(b)
        else:
            kareler[b] = kaynak.ico.getimage((b, b)).convert("RGBA")
    ico_yaz(editor, kareler)


if __name__ == "__main__":
    main()
