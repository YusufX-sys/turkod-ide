"""Kitabın "TürKod IDE tam kılavuzu" bölümünü (kilavuz_icerik.py) ve kitabın
içindekiler sayfasını Kodi'nin bilgi dosyasına (turkod_ide/kodi_kilavuz.py)
çevirir.

Programdaki Kodi, kullanıcının sorusuyla ilgili bölümleri bu dosyadan seçip
yapay zekâya verir; sayfa numaralarıyla kitabı istenen sayfada açabilir.
Kılavuz değişince (kilavuz_ekle.py'den sonra) bunu da çalıştır:

    python tools/kitap/kodi_bilgisi_uret.py
"""
import os
import re
import sys

import pymupdf

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(os.path.dirname(BURASI))
sys.path.insert(0, BURASI)

import kilavuz_icerik  # noqa: E402

HEDEF = os.path.join(KOK, "turkod_ide", "kodi_kilavuz.py")
KITAP = os.path.join(KOK, "belgeler", "TurKod_ile_Kodlama_Macerasi.pdf")


def sade(metin):
    """Kitap biçimlemesini (kalın) kaldırır; satır içi kodu korur."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", str(metin)).strip()


def blok_metni(blok):
    tur = blok[0]
    if tur in ("paragraf", "baslik"):
        return sade(blok[1])
    if tur == "maddeler":
        return "\n".join("- " + sade(m) for m in blok[1])
    if tur == "kutu":
        return sade(blok[2])
    if tur == "tablo":
        basliklar, satirlar = blok[1], blok[2]
        out = []
        for s in satirlar:
            hucreler = [sade(h) for h in s]
            out.append("- " + "; ".join(
                f"{b}: {h}" if i else h
                for i, (b, h) in enumerate(zip(basliklar, hucreler)) if h))
        return "\n".join(out)
    if tur == "kod":
        return f"Örnek ({blok[1]}):\n" + "\n".join("    " + s for s in blok[2])
    if tur == "terminal":
        return "Terminal:\n" + "\n".join("    " + s for s in blok[1])
    return ""  # resim ve Kodi balonları bilgi taşımaz


def kitap_icindekiler(doc):
    """s.3'teki içindekiler: [(bölüm adı, sayfa)]."""
    satirlar = [s.strip() for s in doc[2].get_text().splitlines() if s.strip()]
    sonuc = []
    for i, s in enumerate(satirlar[:-1]):
        if re.match(r"^\d+\.\s", s) and satirlar[i + 1].isdigit():
            sonuc.append((s, int(satirlar[i + 1])))
    return sonuc


def kilavuz_sayfalari(doc, basliklar, baslangic):
    """Her kılavuz sayfasının kitaptaki sayfa numarası (bulunamazsa 0)."""
    metinler = [doc[i].get_text().splitlines() for i in range(len(doc))]
    sonuc = []
    ara = baslangic
    for b in basliklar:
        bulunan = 0
        for i in range(ara, len(doc)):
            if b in (s.strip() for s in metinler[i]):
                bulunan = i + 1
                ara = i + 1
                break
        sonuc.append(bulunan)
    return sonuc


def main():
    doc = pymupdf.open(KITAP)
    icindekiler = kitap_icindekiler(doc)
    kilavuz_bas = next((p for ad, p in icindekiler if ad.startswith("21.")), 1)
    basliklar = [sade(s[0]) for s in kilavuz_icerik.SAYFALAR]
    sayfalar = kilavuz_sayfalari(doc, basliklar, kilavuz_bas - 1)

    bolumler = []
    for (baslik, alt, bloklar), sayfa in zip(kilavuz_icerik.SAYFALAR, sayfalar):
        parcalar = [p for p in (blok_metni(b) for b in bloklar) if p]
        bolumler.append((sade(baslik), sade(alt), "\n".join(parcalar), sayfa))
    with open(HEDEF, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Kodi\'nin program bilgisi: kitabın "TürKod IDE tam kılavuzu"\n'
                'bölümü ve içindekiler sayfasından üretildi. Elle düzenleme;\n'
                'tools/kitap/kodi_bilgisi_uret.py ile yeniden üret."""\n\n')
        f.write("# (bölüm adı, kitaptaki sayfa)\n")
        f.write("KITAP_BOLUMLERI = [\n")
        for ad, sayfa in icindekiler:
            f.write(f"    ({ad!r}, {sayfa}),\n")
        f.write("]\n\n")
        f.write("# (başlık, alt başlık, metin, kitaptaki sayfa)\n")
        f.write("BOLUMLER = [\n")
        for b in bolumler:
            f.write(f"    ({b[0]!r},\n     {b[1]!r},\n     {b[2]!r},\n     {b[3]}),\n")
        f.write("]\n")
    toplam = sum(len(b[2]) for b in bolumler)
    eksik = [b[0] for b in bolumler if not b[3]]
    print(f"{HEDEF}: {len(bolumler)} bölüm, {toplam} karakter, "
          f"{len(icindekiler)} kitap bölümü; sayfası bulunamayan: {eksik or 'yok'}")


if __name__ == "__main__":
    main()
