"""Kitaba "TürKod IDE tam kılavuzu" bölümünü ekler ya da yeniler.

İçerik kilavuz_icerik.py'dedir; program değişince orayı düzenleyip bu betiği
yeniden çalıştırın. Betik tekrar çalıştırılabilir:
  * önceki kılavuz sayfalarını ("BÖLÜM <no>" haplı sayfalar) ve kılavuzun
    ayrıntılı içindekiler sayfasını silip yeniden üretir,
  * bölümü sertifikadan önceye koyar,
  * İçindekiler'in hemen arkasına kılavuzun sayfa sayfa içindekiler sayfasını koyar,
  * bütün sayfa numaralarını (kapak hariç) baştan yazar,
  * ana İçindekiler sayfasındaki numaraları bölümlerin gerçek yerinden hesaplar.

Kullanım (proje kökünde):
    python tools/kitap/kilavuz_ekle.py            # belgeler/ içindeki kitabı günceller
    python tools/kitap/kilavuz_ekle.py --png DIR  # ayrıca değişen sayfaları PNG'ye çizer
"""
import argparse
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kitap_araclari as k  # noqa: E402
from kilavuz_icerik import BOLUM_NO, BOLUM_ADI, SAYFALAR  # noqa: E402

HAP = f"BÖLÜM {BOLUM_NO}"
TOC_BASLIK = f"{BOLUM_NO}. {BOLUM_ADI}"
DEVAM_BASLIK = f"İçindekiler: Bölüm {BOLUM_NO}"     # ayrıntılı içindekiler sayfasının başlığı
SABLON_METNI = "BÖLÜM 16"        # içeriği silinip şablon olarak kopyalanan sayfa
SERTIFIKA_METNI = "KOD KAHRAMANI SERTİFİKASI"
TOC_METNI = "Sertifikan son sayfada seni bekliyor!"
KODI_METNI = "Bu kitabı çocuğunuzla birlikte nasıl kullanabilirsiniz?"   # Kodi çiziminin olduğu sayfa
MERHABA_METNI = "Bu kitabı nasıl okuyacağız?"


def _satirlar(page):
    return [l.strip() for l in page.get_text().split("\n")]


def eski_sayfalari_sil(doc):
    silinecek = [i for i, p in enumerate(doc)
                 if HAP in _satirlar(p) or DEVAM_BASLIK in _satirlar(p)]
    for i in reversed(silinecek):
        doc.delete_page(i)
    return len(silinecek)


def sayfa_ciz(page, hap, baslik, alt_baslik, bloklar):
    s = k.Sayfa(page, baslik)
    s.ust(hap, baslik, alt_baslik)
    for blok in bloklar:
        tur, *arg = blok
        getattr(s, tur)(*arg)


def bolum_sayfasi(doc, n):
    """BÖLÜM n hapının ilk göründüğü sayfa (0 tabanlı) ya da -1."""
    hap = f"BÖLÜM {n}"
    return next((i for i, p in enumerate(doc) if hap in _satirlar(p)), -1)


def toc_girdilerini_oku(page):
    satirlar = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if 135 < l["bbox"][1] < 790 and t:
                satirlar.append((l["bbox"][1], l["bbox"][0], t))
    satirlar.sort()
    girdiler, i = [], 0
    while i < len(satirlar):
        grup = [s for s in satirlar if abs(s[0] - satirlar[i][0]) < 3]
        girdiler.append(min(grup, key=lambda s: s[1])[2])
        i += len(grup)
    return girdiler


def icindekileri_yaz(doc, toc_no, devam_no):
    """Ana İçindekiler: başlıklar korunur, numaralar bölümlerin gerçek
    yerinden hesaplanır (kılavuz satırı yoksa eklenir)."""
    page = doc[toc_no]
    basliklar = [b for b in toc_girdilerini_oku(page) if b != TOC_BASLIK]
    basliklar.insert(basliklar.index("Sertifika"), TOC_BASLIK)
    girdiler = []
    for b in basliklar:
        m = re.match(r"(\d+)\. ", b)
        if m:
            no = bolum_sayfasi(doc, int(m.group(1))) + 1
            sayi = str(no)
        elif b == "Merhaba, ben Kodi!":
            sayi = str(k.sayfa_bul(doc, MERHABA_METNI) + 1)
        elif b == "İçindekiler":
            sayi = f"{toc_no + 1}-{devam_no + 1}"
        elif b == "Sertifika":
            sayi = str(k.sayfa_bul(doc, SERTIFIKA_METNI) + 1)
        else:
            raise SystemExit(f"İçindekiler satırı tanınmadı: {b!r}")
        if sayi == "0":
            raise SystemExit(f"Sayfası bulunamadı: {b!r}")
        girdiler.append((b, sayi))

    page.add_redact_annot(pymupdf.Rect(50, 135, 545, 770), fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    k.fontlari_ekle(page)
    aralik = min(27.0, (757.0 - 155.0) / (len(girdiler) - 1))
    for j, (baslik, sayi) in enumerate(girdiler):
        y = 154.0 + j * aralik
        k.yaz(page, k.SOL, y, baslik, "DejaVuSans-Bold", 11.6, k.METIN)
        w = k.FONTLAR["DejaVuSans-Bold"].text_length(sayi, fontsize=11.6)
        k.yaz(page, k.SAG - w, y, sayi, "DejaVuSans-Bold", 11.6, k.METIN)


def ayrintili_icindekiler(page, ilk_no):
    """Kılavuzun her sayfasını numarasıyla, iki sütunda listeler."""
    s = k.Sayfa(page, DEVAM_BASLIK)
    s.ust("EK", DEVAM_BASLIK, "TürKod IDE tam kılavuzu, sayfa sayfa. Merak ettiğin konuyu bul!")
    girdiler = [(b, ilk_no + j + 1) for j, (b, _, _) in enumerate(SAYFALAR)]
    yari = (len(girdiler) + 1) // 2
    sutunlar = [girdiler[:yari], girdiler[yari:]]
    genislik = (k.SAG - k.SOL - 20) / 2
    aralik = min(24.0, (k.ALT_SINIR - 150) / yari)
    boyut = 9.4
    for c, sutun in enumerate(sutunlar):
        x0 = k.SOL + c * (genislik + 20)
        for j, (baslik, no) in enumerate(sutun):
            y = 150 + j * aralik
            if j % 2 == 0:
                page.draw_rect(pymupdf.Rect(x0, y - 2, x0 + genislik, y + aralik - 2),
                               color=None, fill=k.renk(k.TABLO_SATIR))
            sayi = str(no)
            sw = k.FONTLAR["DejaVuSans-Bold"].text_length(sayi, fontsize=boyut)
            sigdir = baslik
            while k.FONTLAR["DejaVuSans-Bold"].text_length(sigdir, fontsize=boyut) > genislik - sw - 22:
                sigdir = sigdir[:-2].rstrip() + "…"
            k.yaz(page, x0 + 6, y + aralik / 2 + 3, sigdir, "DejaVuSans-Bold", boyut, k.METIN)
            k.yaz(page, x0 + genislik - 6 - sw, y + aralik / 2 + 3, sayi, "DejaVuSans-Bold", boyut, k.MOR)
    return girdiler


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--girdi", default=str(k.KITAP))
    ap.add_argument("--cikti", default=str(k.KITAP))
    ap.add_argument("--png", default=None)
    a = ap.parse_args()

    doc = pymupdf.open(a.girdi)
    kaynak = pymupdf.open(a.girdi)       # Kodi çizimi buradan kopyalanır (aynı belgeden olmaz)
    k.KODI_KAYNAK = (kaynak, k.sayfa_bul(kaynak, KODI_METNI))
    if k.KODI_KAYNAK[1] < 0:
        raise SystemExit(f"Kodi çiziminin sayfası bulunamadı: {KODI_METNI}")

    silinen = eski_sayfalari_sil(doc)
    sablon = k.sayfa_bul(doc, SABLON_METNI)
    toc_no = k.sayfa_bul(doc, TOC_METNI)
    if sablon < 0 or toc_no < 0:
        raise SystemExit("Şablon ya da İçindekiler sayfası bulunamadı")

    # 1) Ayrıntılı içindekiler için boş sayfa (içeriği numaralar belli olunca yazılır).
    devam_no = toc_no + 1
    devam = k.bos_sayfa_ekle(doc, sablon, devam_no)
    # 2) Kılavuz sayfaları sertifikadan önce.
    sablon = k.sayfa_bul(doc, SABLON_METNI)
    ilk = k.sayfa_bul(doc, SERTIFIKA_METNI)
    for j, (baslik, alt_baslik, bloklar) in enumerate(SAYFALAR):
        page = k.bos_sayfa_ekle(doc, sablon, ilk + j)
        sayfa_ciz(page, HAP, baslik, alt_baslik, bloklar)
    # 3) Ayrıntılı içindekiler, ana içindekiler ve bütün sayfa numaraları.
    ayrintili_icindekiler(doc[devam_no], ilk)
    icindekileri_yaz(doc, toc_no, devam_no)
    for i, page in enumerate(doc):
        if i:
            k.sayfa_numarasi_yaz(page, i + 1)

    doc.subset_fonts()
    gecici = a.cikti + ".yeni.pdf"
    doc.save(gecici, garbage=3, deflate=True)
    doc.close()
    kaynak.close()
    Path(gecici).replace(a.cikti)
    sertifika = ilk + len(SAYFALAR)
    print(f"{silinen} eski sayfa silindi; ayrıntılı içindekiler s.{devam_no + 1}; "
          f"{len(SAYFALAR)} kılavuz sayfası s.{ilk + 1}-{ilk + len(SAYFALAR)}; sertifika s.{sertifika + 1}.")
    if a.png:
        out = pymupdf.open(a.cikti)
        Path(a.png).mkdir(parents=True, exist_ok=True)
        for no in [toc_no, devam_no] + list(range(ilk, sertifika + 1)):
            out[no].get_pixmap(dpi=90).save(str(Path(a.png) / f"s{no + 1}.png"))


if __name__ == "__main__":
    main()
