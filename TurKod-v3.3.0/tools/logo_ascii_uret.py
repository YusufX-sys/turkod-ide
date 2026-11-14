"""TürKod logosunu (turkod_ide/turkod.ico) terminalde ASCII olarak çizmek için
gömülü veriye çevirir: turkod_ide/logo_verisi.py.

Paketlenmiş programda Pillow ve .ico dosyası bulunmayabildiği için çizici
(turkod_ide/logo_ascii.py) resmi değil, bu küçük veriyi kullanır. Logo
değişirse bu betiği proje kökünden yeniden çalıştır:

    python tools/logo_ascii_uret.py
"""
import base64
import os
import textwrap
import zlib

from PIL import Image

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "turkod_ide", "turkod.ico")
HEDEF = os.path.join(KOK, "turkod_ide", "logo_verisi.py")
BOYUT = 128


def main():
    resim = Image.open(KAYNAK)
    resim.size = max(resim.info.get("sizes") or [resim.size])  # en büyük katman
    resim = resim.convert("RGBA").resize((BOYUT, BOYUT), Image.LANCZOS)
    veri = base64.b64encode(zlib.compress(resim.tobytes(), 9)).decode("ascii")
    satirlar = "\n".join(f'    "{s}"' for s in textwrap.wrap(veri, 96))
    with open(HEDEF, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""TürKod logosunun piksel verisi (RGBA, zlib + base64).\n\n'
                "Elle düzenleme: tools/logo_ascii_uret.py üretir; çizici logo_ascii.py.\n"
                '"""\n'
                f"BOYUT = {BOYUT}\n"
                "VERI = (\n" + satirlar + "\n)\n")
    print(f"{HEDEF}: {BOYUT}x{BOYUT}, {len(veri)} karakter")


if __name__ == "__main__":
    main()
