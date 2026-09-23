"""turkod.ico'yu Inno Setup'ın kabul edeceği küçük, çok boyutlu bir .ico'ya çevirir.

Neden: Inno Setup, 1.8 MB'lık kaynak ikonda "Resource update error: File is too large"
hatası veriyor. Standart bir Windows ikonu 16-256 px arası boyutlar içerir ve genelde
birkaç yüz KB'ı geçmez.

Kullanım:  python ikon_kucult.py KAYNAK.ico HEDEF.ico
Çıkış kodu 0 = başarılı. Pillow gerekir (pip install pillow).
"""
import sys

from PIL import Image

BOYUTLAR = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
SINIR_BAYT = 600 * 1024


def main():
    if len(sys.argv) != 3:
        sys.exit("Kullanım: python ikon_kucult.py KAYNAK.ico HEDEF.ico")
    kaynak, hedef = sys.argv[1], sys.argv[2]

    ico = Image.open(kaynak)
    ico.load()                       # Pillow en büyük kareyi yükler
    img = ico.convert("RGBA")

    # 256'dan büyükse küçült; kare değilse şeffaf 256x256 tuvale ortala.
    if max(img.size) > 256 or img.size[0] != img.size[1]:
        img.thumbnail((256, 256), Image.LANCZOS)
        tuval = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        tuval.paste(img, ((256 - img.size[0]) // 2, (256 - img.size[1]) // 2))
        img = tuval
    elif img.size != (256, 256):
        img = img.resize((256, 256), Image.LANCZOS)

    img.save(hedef, format="ICO", sizes=BOYUTLAR)

    import os
    boyut = os.path.getsize(hedef)
    print(f"{hedef}: {boyut // 1024} KB, kaynak en büyük kare: {ico.size}")
    if boyut > SINIR_BAYT:
        sys.exit(f"Çıktı hâlâ büyük ({boyut} bayt).")


if __name__ == "__main__":
    main()
