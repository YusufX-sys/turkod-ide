"""TürKod ile Kodlama Macerası kitabını (belgeler/TurKod_ile_Kodlama_Macerasi.pdf)
düzenlemek için ortak araçlar.

Kitabın kaynak dosyası yoktur: ReportLab ile üretilip PyMuPDF ile düzenlendi.
PDF'e gömülü fontlar Unicode eşlemesi olmayan alt kümeler olduğundan yeni metin
bu klasördeki tam DejaVu fontlarıyla yazılır. Renk ve ölçüler kitabın kendi
sayfalarından ölçülmüştür (bkz. KITAP_BAKIM.md).
"""
import re
import time
from pathlib import Path

import pymupdf

KLASOR = Path(__file__).resolve().parent
KOK = KLASOR.parent.parent
KITAP = KOK / "belgeler" / "TurKod_ile_Kodlama_Macerasi.pdf"
FONT_KLASORU = KLASOR / "fontlar"
GORUNTU_KLASORU = KLASOR / "goruntuler"   # kılavuzdaki ekran görüntüleri

FONT_DOSYALARI = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
    "DejaVuSansMono": "DejaVuSansMono.ttf",
    "DejaVuSansMono-Bold": "DejaVuSansMono-Bold.ttf",
}
# Sayfaya eklenirken kullanılan kısa adlar. Her çalıştırmada benzersizdir:
# sayfada aynı adla eski (alt kümeye indirilmiş, bazı harfleri olmayan) bir
# font varsa PyMuPDF onu yeniden kullanır ve yeni yazı bozuk çıkar.
_ON = "tk" + format(int(time.time() * 1000) % 0xFFFFFF, "06x")
FONT_KISA = {"DejaVuSans": _ON + "r", "DejaVuSans-Bold": _ON + "b",
             "DejaVuSansMono": _ON + "m", "DejaVuSansMono-Bold": _ON + "mb"}
FONTLAR = {ad: pymupdf.Font(fontfile=str(FONT_KLASORU / d)) for ad, d in FONT_DOSYALARI.items()}

# --- Kitabın tasarım değerleri (sayfa 47'den ölçüldü) ---
SOL, SAG = 57.0, 538.0            # metin kenar boşlukları
ALT_SINIR = 765.0                 # alt dalgaya (y=772) girmeden son satır
METIN = 0x1E1B3A                  # gövde yazısı
SOLUK = 0x6B6A85                  # alt başlık
MOR = 0xA21CAF                    # bölüm içi başlık, kod kelimesi
PEMBE = 0xD846EF                  # bölüm hapı, başlık altı çizgisi
TABLO_BASLIK = 0xA11CAF
TABLO_SATIR = 0xF6EFFF
TABLO_CIZGI = 0xE6DDF4
KUTULAR = {  # tür: (arka plan, şerit/simge rengi, simge, başlık)
    "gorev": (0xDBFBE6, 0x0FB880, "★", "Mini Görev"),
    "bilgi": (0xDFE6FF, 0x6266F0, "i", "Biliyor muydun?"),
    "ipucu": (0xFDF2C6, 0xF49E0A, "★", "İpucu"),
    "dikkat": (0xFFEDD4, 0xF97216, "!", "Dikkat"),
}


def renk(c):
    return ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255


def fontlari_ekle(page):
    for ad, kisa in FONT_KISA.items():
        page.insert_font(fontname=kisa, fontfile=str(FONT_KLASORU / FONT_DOSYALARI[ad]))


class Tasma(Exception):
    pass


def yaz(page, x, y, metin, font="DejaVuSans", boyut=10.6, c=METIN):
    """Tek parça metin yazar, bitiş x'ini döndürür. Fontta olmayan bir
    karakter (ör. emoji) PDF'te kutu olarak çıkacağından hata verir."""
    eksik = {ch for ch in metin if not ch.isspace() and not FONTLAR[font].has_glyph(ord(ch))}
    if eksik:
        raise Tasma(f"{font} fontunda olmayan karakter: {''.join(sorted(eksik))!r} ({metin[:40]!r})")
    if metin:
        page.insert_text((x, y), metin, fontname=FONT_KISA[font], fontsize=boyut, color=renk(c))
    return x + FONTLAR[font].text_length(metin, fontsize=boyut)


# --- Satır içi biçim: **kalın**, `kod` ---
_BICIM = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def parcala(metin):
    """'**a** `b` c' -> [(metin, stil)]; stil: normal | kalin | kod"""
    out = []
    for p in _BICIM.split(metin):
        if not p:
            continue
        if p.startswith("**"):
            out.append((p[2:-2], "kalin"))
        elif p.startswith("`"):
            out.append((p[1:-1], "kod"))
        else:
            out.append((p, "normal"))
    return out


def _stil(stil, boyut, renk_normal):
    if stil == "kalin":
        return "DejaVuSans-Bold", boyut, renk_normal
    if stil == "kod":
        return "DejaVuSansMono-Bold", boyut, MOR
    return "DejaVuSans", boyut, renk_normal


def satirlara_bol(metin, genislik, boyut, renk_normal=METIN):
    """Biçimli metni genişliğe göre satırlara böler:
    [[(önündeki_boşluk_genişliği, parça, font, boyut, renk)]]. Boşluk her zaman
    düz yazı fontuyla ölçülür (kod fontunun geniş boşluğu çift boşluk gibi durur)."""
    bosluk_w = FONTLAR["DejaVuSans"].text_length(" ", fontsize=boyut)
    kelimeler = []  # (metin, font, boyut, renk, önünde_boşluk_var)
    onceki_bosluk = False
    for parca, stil in parcala(metin):
        font, b, c = _stil(stil, boyut, renk_normal)
        if stil == "kod":  # kod parçası bölünmez
            kelimeler.append((parca, font, b, c, onceki_bosluk))
            onceki_bosluk = False
            continue
        for m in re.finditer(r"\S+", parca):
            bas = m.start()
            kelimeler.append((m.group(), font, b, c, parca[bas - 1].isspace() if bas else onceki_bosluk))
        onceki_bosluk = parca[-1:].isspace()
    satirlar, satir, x = [], [], 0.0
    for k, font, b, c, bosluk in kelimeler:
        on = bosluk_w if (bosluk and satir) else 0.0
        w = FONTLAR[font].text_length(k, fontsize=b)
        if satir and x + on + w > genislik:
            satirlar.append(satir)
            satir, x, on = [], 0.0, 0.0
        satir.append((on, k, font, b, c))
        x += on + w
    if satir:
        satirlar.append(satir)
    return satirlar


def satir_ciz(page, x, taban, satir):
    for on, parca, font, b, c in satir:
        x = yaz(page, x + on, taban, parca, font, b, c)
    return x


class Sayfa:
    """Kitap tarzında içerik çizen imleç (y aşağı doğru ilerler)."""

    def __init__(self, page, ad=""):
        self.page = page
        self.ad = ad
        self.y = 140.0
        fontlari_ekle(page)

    def _kontrol(self, h):
        if self.y + h > ALT_SINIR:
            raise Tasma(f"'{self.ad}' sayfası taştı ({self.y + h:.0f} > {ALT_SINIR})")

    # Sayfa başı: hap + başlık + alt başlık + çizgi (kitaptaki ölçüler)
    def ust(self, hap, baslik, alt_baslik):
        w = FONTLAR["DejaVuSans-Bold"].text_length(hap, fontsize=8.4) + 22
        self.page.draw_rect(pymupdf.Rect(SOL, 48, SOL + w, 64), color=None, fill=renk(PEMBE), radius=0.5)
        yaz(self.page, SOL + 11, 59.4, hap, "DejaVuSans-Bold", 8.4, 0xFFFFFF)
        if FONTLAR["DejaVuSans-Bold"].text_length(baslik, fontsize=25) > SAG - SOL:
            raise Tasma(f"'{baslik}' başlığı sayfaya sığmıyor; kısaltın")
        yaz(self.page, SOL, 95, baslik, "DejaVuSans-Bold", 25, METIN)
        yaz(self.page, SOL, 112, alt_baslik, "DejaVuSans", 11, SOLUK)
        self.page.draw_line((SOL, 125), (103, 125), color=renk(PEMBE), width=2.4)
        self.y = 140.0

    def baslik(self, metin):
        self._kontrol(28)
        self.y += 8
        yaz(self.page, SOL, self.y + 13, metin, "DejaVuSans-Bold", 15.2, MOR)
        self.y += 24

    def paragraf(self, metin, boyut=10.6, aralik=16.0, girinti=0.0, sonra=6.0):
        satirlar = satirlara_bol(metin, SAG - SOL - girinti, boyut)
        self._kontrol(len(satirlar) * aralik)
        for satir in satirlar:
            satir_ciz(self.page, SOL + girinti, self.y + boyut, satir)
            self.y += aralik
        self.y += sonra

    def maddeler(self, maddeler, boyut=10.4, aralik=15.0):
        for m in maddeler:
            satirlar = satirlara_bol(m, SAG - SOL - 14, boyut)
            self._kontrol(len(satirlar) * aralik)
            yaz(self.page, SOL + 2, self.y + boyut, "•", "DejaVuSans-Bold", boyut, PEMBE)
            for satir in satirlar:
                satir_ciz(self.page, SOL + 14, self.y + boyut, satir)
                self.y += aralik
            self.y += 2
        self.y += 4

    def tablo(self, basliklar, satirlar, oranlar, boyut=9.6, aralik=13.0):
        """Kitaptaki mor başlıklı, çizgili tablo. oranlar: sütun genişlik oranları."""
        genislik = SAG - SOL
        topl = sum(oranlar)
        gen = [genislik * o / topl for o in oranlar]
        xs = [SOL]
        for g in gen[:-1]:
            xs.append(xs[-1] + g)
        bas_h = 22.0
        self._kontrol(bas_h + 20)
        p = self.page
        p.draw_rect(pymupdf.Rect(SOL, self.y, SAG, self.y + bas_h), color=None, fill=renk(TABLO_BASLIK))
        for x, b in zip(xs, basliklar):
            yaz(p, x + 8, self.y + 15, b, "DejaVuSans-Bold", 9.8, 0xFFFFFF)
        self.y += bas_h
        for i, satir in enumerate(satirlar):
            hucreler = [satirlara_bol(str(h), g - 16, boyut) for h, g in zip(satir, gen)]
            h = max(len(c) for c in hucreler) * aralik + 10
            self._kontrol(h)
            if i % 2 == 1:
                p.draw_rect(pymupdf.Rect(SOL, self.y, SAG, self.y + h), color=None, fill=renk(TABLO_SATIR))
            for x, hucre in zip(xs, hucreler):
                yy = self.y + 5
                for s in hucre:
                    satir_ciz(p, x + 8, yy + boyut, s)
                    yy += aralik
            self.y += h
            p.draw_line((SOL, self.y), (SAG, self.y), color=renk(TABLO_CIZGI), width=0.5)
        self.y += 10

    def kutu(self, tur, metin, baslik=None):
        arka, serit, simge, varsayilan = KUTULAR[tur]
        satirlar = satirlara_bol(metin, SAG - 105 - 14, 10.2)
        h = 31 + len(satirlar) * 14.5 + 6
        self._kontrol(h)
        p = self.page
        r = pymupdf.Rect(SOL, self.y, SAG, self.y + h)
        p.draw_rect(r, color=None, fill=renk(arka), radius=0.06)
        p.draw_rect(pymupdf.Rect(SOL, self.y, SOL + 6, self.y + h), color=None, fill=renk(serit))
        p.draw_circle((85.5, self.y + 20.5), 10.5, color=None, fill=renk(serit))
        sw = FONTLAR["DejaVuSans-Bold"].text_length(simge, fontsize=12)
        yaz(p, 85.5 - sw / 2, self.y + 25, simge, "DejaVuSans-Bold", 12, 0xFFFFFF)
        yaz(p, 105, self.y + 26, baslik or varsayilan, "DejaVuSans-Bold", 10.6, METIN)
        yy = self.y + 32
        for s in satirlar:
            satir_ciz(p, 105, yy + 10.2, s)
            yy += 14.5
        self.y += h + 8

    def kod(self, dosya, satirlar):
        """Kitaptaki koyu kod kutusu: başlık şeridi, satır numaraları, renkler."""
        h = 19 + 11 + len(satirlar) * 13.2 + 6
        self._kontrol(h)
        p, ust = self.page, self.y
        p.draw_rect(pymupdf.Rect(SOL, ust, SAG, ust + h), color=None, fill=renk(0x151A33), radius=0.04)
        p.draw_rect(pymupdf.Rect(SOL, ust, SAG, ust + 19), color=None, fill=renk(0x232A49), radius=0.04)
        p.draw_rect(pymupdf.Rect(SOL, ust + 11, SAG, ust + 19), color=None, fill=renk(0x232A49))
        for x, c in ((68, 0xF87070), (79, 0xFBBF23), (90, 0x34D399)):
            p.draw_circle((x, ust + 9.5), 3, color=None, fill=renk(c))
        yaz(p, 107, ust + 13, dosya, "DejaVuSans", 8.0, 0xC9D0F0)
        taban = ust + 30.4
        for i, satir in enumerate(satirlar, 1):
            n = str(i)
            yaz(p, 81 - FONTLAR["DejaVuSansMono"].text_length(n, fontsize=8.6), taban, n,
                "DejaVuSansMono", 8.6, 0x5C6690)
            x = 89.0
            for parca, c in kod_renklendir(satir):
                x = yaz(p, x, taban, parca, "DejaVuSansMono", 8.6, c)
            taban += 13.2
        self.y += h + 6

    def terminal(self, satirlar):
        h = 22 + len(satirlar) * 12.4 + 6
        self._kontrol(h)
        p, ust = self.page, self.y
        p.draw_rect(pymupdf.Rect(SOL, ust, SAG, ust + h), color=None, fill=renk(0x0C111F), radius=0.04)
        yaz(p, 70, ust + 13, ">_  TERMİNAL", "DejaVuSans-Bold", 6.4, 0x94A0C8)
        taban = ust + 27
        for s in satirlar:
            yaz(p, 70, taban, s, "DejaVuSansMono", 8.1, 0xDDE6FF)
            taban += 12.4
        self.y += h + 8

    def resim(self, dosya, alt_yazi="", en_fazla_yukseklik=330.0, genislik=None):
        """Ekran görüntüsü: goruntuler/ klasöründen, ince çerçeve ve alt yazıyla.
        Genişlik verilmezse sayfa genişliğine sığdırılır; yükseklik sınırı
        aşılırsa orantılı küçültülüp ortalanır."""
        yol = GORUNTU_KLASORU / dosya
        if not yol.exists():
            raise Tasma(f"Ekran görüntüsü yok: {yol}")
        pix = pymupdf.Pixmap(str(yol))
        oran = pix.height / pix.width
        w = genislik or (SAG - SOL)
        h = w * oran
        if h > en_fazla_yukseklik:
            h = en_fazla_yukseklik
            w = h / oran
        yazi_h = 14 if alt_yazi else 0
        self._kontrol(h + yazi_h + 4)
        x0 = SOL + (SAG - SOL - w) / 2
        r = pymupdf.Rect(x0, self.y, x0 + w, self.y + h)
        self.page.insert_image(r, filename=str(yol))
        self.page.draw_rect(r, color=renk(0xCAD4E1), width=0.8)
        self.y += h + 3
        if alt_yazi:
            tw = FONTLAR["DejaVuSans"].text_length(alt_yazi, fontsize=8.6)
            yaz(self.page, SOL + (SAG - SOL - tw) / 2, self.y + 8.6, alt_yazi, "DejaVuSans", 8.6, SOLUK)
            self.y += yazi_h
        self.y += 8

    def kodi(self, metin):
        """Kitaptaki Kodi robotu ve konuşma balonu. Robot çizimi kitabın kendi
        sayfasından (KODI_KAYNAK) alınır; kilavuz_ekle.py bunu ayarlar."""
        if KODI_KAYNAK is None:
            raise Tasma("KODI_KAYNAK ayarlanmadı (kitap_araclari.KODI_KAYNAK = (belge, sayfa_no))")
        belge, sayfa_no = KODI_KAYNAK
        satirlar = satirlara_bol(metin, SAG - 152 - 18, 10.6)
        h = max(78.0, len(satirlar) * 16 + 26)
        self._kontrol(h)
        p, ust = self.page, self.y
        rw, rh = KODI_KIRP.width, KODI_KIRP.height
        ry = ust + (h - rh) / 2
        p.show_pdf_page(pymupdf.Rect(SOL + 5, ry, SOL + 5 + rw, ry + rh), belge, sayfa_no, clip=KODI_KIRP)
        balon = pymupdf.Rect(138, ust, SAG, ust + h)
        p.draw_rect(balon, color=renk(0x6266F0), fill=(1, 1, 1), width=1.76, radius=0.12)
        yy = ust + (h - len(satirlar) * 16) / 2 - 2
        for s in satirlar:
            satir_ciz(p, 152, yy + 12, s)
            yy += 16
        self.y += h + 10

    def bosluk(self, h):
        self.y += h


# Kodi robotunun çizimi: "Büyükler için not" sayfasının sol altından kırpılır.
KODI_KAYNAK = None                               # (pymupdf belgesi, sayfa no)
KODI_KIRP = pymupdf.Rect(62, 680, 130, 759)


ANAHTAR_KELIMELER = {
    "içe_aktar", "den", "olarak", "için", "içinde", "eğer", "değilse", "değilse_eğer", "döngü",
    "fonksiyon", "döndür", "kır", "devam_et", "ve", "veya", "değil", "Doğru", "Yanlış", "Hiçlik",
    "sınıf", "dene", "hata_yakala", "sonunda", "kendisi", "küresel",
}
_KOD_PARCA = re.compile(r'(#.*$|"[^"]*"|\'[^\']*\'|\d+(?:\.\d+)?|[A-Za-z_ÇŞĞÜÖİçşğüöı][\wçşğüöıÇŞĞÜÖİ]*|\s+|.)')


def kod_renklendir(satir):
    """Kitabın kod renkleri: anahtar kelime pembe, fonksiyon/modül camgöbeği,
    nokta sonrası üye sarı, sayı turuncu, metin yeşil, yorum soluk."""
    parcalar = [m.group(0) for m in _KOD_PARCA.finditer(satir)]
    out = []
    for i, t in enumerate(parcalar):
        onceki = next((p for p in reversed(parcalar[:i]) if not p.isspace()), "")
        sonraki = next((p for p in parcalar[i + 1:] if not p.isspace()), "")
        if t.startswith("#"):
            c = 0x7C8AB5
        elif t[:1] in "\"'":
            c = 0x86EFAC
        elif t[:1].isdigit():
            c = 0xFDBA74
        elif t in ANAHTAR_KELIMELER:
            c = 0xF472B6
        elif t[:1].isalpha() or t[:1] == "_":
            if onceki == ".":
                c = 0xFDE68A
            elif sonraki in ("(", ".") or onceki == "içe_aktar":
                c = 0x67E8F9
            else:
                c = 0xE6E9F5
        else:
            c = 0xE6E9F5
        out.append((t, c))
    return out


def sayfa_numarasi_yaz(page, no):
    """Alttaki pembe daire içindeki sayfa numarasını değiştirir. Sayfada
    numara yoksa (kapak) dokunmaz ve False döndürür."""
    bulundu = False
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                if y0 > 800 and x0 > 520 and s["text"].strip().isdigit():
                    page.add_redact_annot(pymupdf.Rect(x0 - 1, y0 + 2, x1 + 1, y1 - 2), fill=False)
                    bulundu = True
    if not bulundu:
        return False
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    fontlari_ekle(page)
    t = str(no)
    w = FONTLAR["DejaVuSans-Bold"].text_length(t, fontsize=8.6)
    yaz(page, 538 - w / 2, 814.8, t, "DejaVuSans-Bold", 8.6, 0xFFFFFF)
    return True


def bos_sayfa_ekle(doc, sablon_no, hedef_no):
    """Şablon sayfayı kopyalayıp içeriğini siler (arka plan, köşe daireleri,
    alt dalga ve altbilgi kalır). hedef_no: yeni sayfanın 0 tabanlı yeri."""
    doc.fullcopy_page(sablon_no, hedef_no)
    page = doc[hedef_no]
    for r in (pymupdf.Rect(40, 64, 590, 770), pymupdf.Rect(40, 40, 480, 64)):
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
    return page


def satir_degistir(page, satir_metni, yeni_parcalar):
    """Sayfadaki satırı (birebir metniyle bulunur) siler, aynı başlangıç
    noktasından yeni parçalarla yazar. yeni_parcalar: [(metin, eski_span_no)];
    font/boyut/renk o span'den alınır. Bulunan satır sayısını döndürür."""
    isler = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            if "".join(s["text"] for s in l["spans"]) == satir_metni:
                isler.append(l)
    for l in isler:
        x0, y0, x1, y1 = l["bbox"]
        h = y1 - y0
        page.add_redact_annot(pymupdf.Rect(x0 - 0.5, y0 + h * 0.3, x1 + 0.5, y1 - h * 0.3), fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    fontlari_ekle(page)
    for l in isler:
        x, y = l["spans"][0]["origin"]
        for metin, i in yeni_parcalar:
            s = l["spans"][i]
            font = s["font"].split("+")[-1]
            font = {"DejaVu Sans Book": "DejaVuSans", "DejaVu Sans Bold": "DejaVuSans-Bold",
                    "DejaVu Sans Mono Book": "DejaVuSansMono",
                    "DejaVu Sans Mono Bold": "DejaVuSansMono-Bold"}.get(font, font)
            x = yaz(page, x, y, metin, font, s["size"], s["color"])
    return len(isler)


def sayfa_bul(doc, metin):
    """İçinde 'metin' geçen ilk sayfanın 0 tabanlı numarası (yoksa -1)."""
    for i, p in enumerate(doc):
        if metin in p.get_text():
            return i
    return -1
