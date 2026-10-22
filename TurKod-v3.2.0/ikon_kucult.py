"""Kaynak .ico'yu küçük, çok boyutlu (16-256 px) bir Windows ikonuna çevirir.

Neden: Inno Setup, 1.8 MB'lık kaynak ikonda "Resource update error: File is too large"
hatası veriyor. Ayrıca Windows görev çubuğu / başlık çubuğu ölçeğe göre 16, 20, 24, 32,
40, 48 ... px kare ister; ikonda o boyut yoksa kendisi küçültür ve sonuç bulanık olur
(Flutter'ın ürettiği app_icon.ico yalnızca 48 px içeriyordu). Burada her boyut ayrı
kare olarak yazılır; kaynakta o boyutta elle hazırlanmış kare varsa o kullanılır.

Kullanım:  python ikon_kucult.py KAYNAK.ico|KAYNAK.png HEDEF.ico
Çıkış kodu 0 = başarılı. Pillow gerekir (pip install pillow).
"""
import os
import sys

from PIL import Image

BOYUTLAR = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
SINIR_BAYT = 600 * 1024


def _kare_256(img):
    """En büyük kareyi kırpıp şeffaf 256x256 tuvale ortalayarak sığdırır.

    editor-logo.ico'nun 256 px karesinde içerik sola kaymış ve çevresinde ~%15 boşluk
    var; bundan küçültülen kareler görev çubuğunda küçük ve bulanık görünüyordu.
    """
    img = img.convert("RGBA")
    kutu = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if kutu:
        img = img.crop(kutu)
    oran = 256 / max(img.size)
    img = img.resize((max(1, round(img.size[0] * oran)), max(1, round(img.size[1] * oran))),
                     Image.LANCZOS)
    tuval = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    tuval.paste(img, ((256 - img.size[0]) // 2, (256 - img.size[1]) // 2))
    return tuval


def main():
    if len(sys.argv) != 3:
        sys.exit("Kullanım: python ikon_kucult.py KAYNAK.ico HEDEF.ico")
    kaynak, hedef = sys.argv[1], sys.argv[2]

    src = Image.open(kaynak)
    hazir = {}                       # kaynakta zaten bulunan kare boyutlar
    if src.format == "ICO":
        for w, h in src.ico.sizes():
            if w == h:
                hazir[w] = src.ico.getimage((w, h)).convert("RGBA")
    src.load()                       # Pillow en büyük kareyi yükler
    buyuk = _kare_256(src)

    kareler = []
    for b in BOYUTLAR:
        kare = buyuk if b == 256 else hazir.get(b)
        if kare is None or kare.size != (b, b):
            kare = buyuk.resize((b, b), Image.LANCZOS)
        kareler.append(kare)

    # Pillow, append_images içindeki boyutu tutan kareyi yeniden ölçeklemeden yazar.
    kareler[-1].save(hedef, format="ICO", sizes=[(b, b) for b in BOYUTLAR],
                     append_images=kareler[:-1])

    boyut = os.path.getsize(hedef)
    print(f"{hedef}: {boyut // 1024} KB, kareler: {BOYUTLAR}")
    if boyut > SINIR_BAYT:
        sys.exit(f"Çıktı hâlâ büyük ({boyut} bayt).")


if __name__ == "__main__":
    main()
