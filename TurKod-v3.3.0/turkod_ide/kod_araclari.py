"""TürKod kaynak kodu araçları: biçimlendirici ve ad değiştirme.

TürKod anahtar kelimeleri de Python tanımlayıcısı olduğundan kaynak kod,
Python'un tokenize modülüyle sözcüklere ayrılabilir. Her iki araç da yalnızca
belirteçlerin (token) arasındaki boşluklara / ad belirteçlerine dokunur;
metinler ve yorumlar olduğu gibi kalır.
"""
import ast
import io
import keyword
import tokenize

try:
    from .converter import turkce_kodu_donustur
except ImportError:
    from converter import turkce_kodu_donustur

GIRINTI = 4
_VARSAYILAN_GIRINTI = GIRINTI

# İki yanına birer boşluk konan işleçler.
_IKILI_ISLECLER = {
    "=", "==", "!=", "<", ">", "<=", ">=", "+=", "-=", "*=", "/=", "//=",
    "%=", "**=", "&=", "|=", "^=", ">>=", "<<=", "@=", "->", ":=",
    "+", "-", "*", "**", "/", "//", "%", "|", "&", "^", "<<", ">>", "@",
}
# Sağ / sol yanında boşluk istemeyen parantezler.
_ACANLAR = "([{"
_KAPAYANLAR = ")]}"
# Önünde bir değer varsa +, -, * ikili işleçtir; yoksa tekli (-1, *liste).
_DEGER_TURLERI = {tokenize.NAME, tokenize.NUMBER, tokenize.STRING}
_ATLANAN = {tokenize.ENCODING, tokenize.ENDMARKER}
_FSTRING = {getattr(tokenize, ad) for ad in
            ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END") if hasattr(tokenize, ad)}


class BicimlendirmeHatasi(Exception):
    pass


def _deger_mi(tok):
    if tok is None:
        return False
    if tok.type in _DEGER_TURLERI:
        return not keyword.iskeyword(tok.string) or tok.string in ("True", "False", "None")
    if tok.type in _FSTRING:
        return tok.string.endswith(("\"", "'")) or tok.type == getattr(tokenize, "FSTRING_END", -1)
    return tok.string in _KAPAYANLAR


def _ast_imzasi(kod):
    try:
        return ast.dump(ast.parse(turkce_kodu_donustur(kod)))
    except Exception:
        return None


_TEKLI_OLABILEN = ("-", "+", "~", "*", "**")


def _tekli_mi(tok, onceki):
    """tok bir tekli işleç mi (-1, *liste, **sozluk)? Önünde değer yoksa evet."""
    return tok.string in _TEKLI_OLABILEN and not _deger_mi(onceki)


def _bosluk(onceki, tok, ikinci_onceki, yigin):
    """İki belirteç arasına konacak boşluk (aynı satırdayken). yigin: açık
    parantezler [(parantez, türlü_parametre_mi)]."""
    a, b = onceki.string, tok.string
    ic = yigin[-1][0] if yigin else ""
    if tok.type == tokenize.COMMENT:
        return "  "
    if a in _ACANLAR or b in _KAPAYANLAR:
        return ""
    if b in (",", ";") or b == ":":
        return ""
    if b == "." or a == ".":
        return ""
    if a in (",", ";"):
        return " "
    if a == ":":
        # Dilim: liste[1:2]; sözlük / lambda / tek satırlık blok: 'a: b'.
        return "" if ic == "[" else " "
    if b in "([" and _deger_mi(onceki) and onceki.type != tokenize.NUMBER:
        # Çağrı / indeks: yazdır(...), liste[0]. Anahtar kelimeden sonra
        # (eğer (x), içinde [..]) boşluk korunur.
        if onceki.type == tokenize.NAME and keyword.iskeyword(a):
            return " "
        return ""
    if _tekli_mi(onceki, ikinci_onceki):
        return ""  # tekli işleçten sonra: -1, *liste
    if a == "=" or b == "=":
        # Parantez içinde anahtar kelimeli argüman f(x=1); türü belirtilmiş
        # parametrede PEP 8 gibi 'x: int = 1'.
        if ic == "(" and not yigin[-1][1]:
            return ""
        return " "
    if b in _TEKLI_OLABILEN and _tekli_mi(tok, onceki):
        # Tekli işleçten önce: 'x = -1', 'f(a, *b)', '2 ** -1'.
        return " " if a in _IKILI_ISLECLER or onceki.type == tokenize.NAME else ""
    if a in _IKILI_ISLECLER or b in _IKILI_ISLECLER:
        return " "
    return " "


def bicimlendir(kod, girinti=None):
    """Kodu biçimlendirir. Girinti "girinti" kadar boşluğa (varsayılan 4;
    Ayarlar → Girinti genişliği) getirilir, işleç ve virgül
    çevresindeki boşluklar düzenlenir, satır sonu boşlukları silinir, art
    arda 2'den fazla boş satır 2'ye indirilir. Çevrilen Python kodunun
    yapısı değişirse BicimlendirmeHatasi verilir."""
    GIRINTI = girinti if isinstance(girinti, int) and 1 <= girinti <= 8 else _VARSAYILAN_GIRINTI
    kod = (kod or "").replace("\r\n", "\n").replace("\r", "\n")
    if not kod.strip():
        return kod
    imza = _ast_imzasi(kod)
    if imza is None:
        raise BicimlendirmeHatasi("Kodda sözdizimi hatası var; önce onu düzeltin.")
    try:
        toklar = list(tokenize.generate_tokens(io.StringIO(kod).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as e:
        raise BicimlendirmeHatasi(f"Kod sözcüklere ayrılamadı: {e}")
    satirlar = kod.split("\n")

    # Yorum satırları, kendilerinden sonraki kod satırının girintisini alır
    # (tokenize, yorumu INDENT/DEDENT'ten önce verir).
    yorum_seviyesi = {}
    seviye = 0
    bekleyen = []
    for i, tok in enumerate(toklar):
        if tok.type == tokenize.INDENT:
            seviye += 1
        elif tok.type == tokenize.DEDENT:
            seviye -= 1
        elif tok.type == tokenize.COMMENT:
            bekleyen.append(i)
        elif tok.type not in (tokenize.NL, tokenize.NEWLINE) and tok.type not in _ATLANAN:
            for j in bekleyen:
                yorum_seviyesi[j] = seviye
            bekleyen = []
    for j in bekleyen:
        yorum_seviyesi[j] = 0

    cikti = []
    seviye = 0
    derinlik = 0
    yigin = []
    onceki = ikinci_onceki = None
    satir_basi = True
    fmetin = 0  # iç içe f-metin derinliği: içeride özgün boşluk korunur
    fark = 0  # mantıksal satırın girinti değişimi (devam satırları için)
    for i, tok in enumerate(toklar):
        if tok.type in _ATLANAN:
            continue
        if tok.type == tokenize.INDENT:
            seviye += 1
            continue
        if tok.type == tokenize.DEDENT:
            seviye -= 1
            continue
        if tok.type in (tokenize.NEWLINE, tokenize.NL):
            # Satır sonundaki boşluklar burada silinir (çok satırlı metinlerin
            # içindeki satırlara dokunulmaz); art arda 2'den fazla boş satır
            # 2'ye indirilir.
            while cikti and cikti[-1].strip(" \t") == "" and cikti[-1] != "\n":
                cikti.pop()
            if cikti and cikti[-1] != "\n":
                cikti[-1] = cikti[-1].rstrip(" \t")
            bos = 0
            for parca in reversed(cikti):
                if parca != "\n":
                    break
                bos += 1
            if satir_basi and bos >= 3:
                continue
            cikti.append("\n")
            satir_basi = True
            # Parantez dışındaki NL yalnızca boş / yorum satırını bitirir;
            # sonraki satır yeni bir mantıksal satırdır.
            if tok.type == tokenize.NEWLINE or derinlik == 0:
                onceki = ikinci_onceki = None
            continue
        if satir_basi:
            satir = satirlar[tok.start[0] - 1]
            eski_girinti = len(satir) - len(satir.lstrip(" \t"))
            if onceki is None:
                # Yeni mantıksal satır (ya da tek başına yorum satırı).
                yeni = yorum_seviyesi.get(i, seviye) * GIRINTI
                fark = yeni - len(satir[:eski_girinti].expandtabs(GIRINTI))
                cikti.append(" " * yeni)
            else:
                # Parantez içindeki devam satırı: göreli girinti korunur.
                eski = len(satir[:eski_girinti].expandtabs(GIRINTI))
                cikti.append(" " * max(0, eski + fark))
            satir_basi = False
        elif onceki is not None:
            if fmetin or tok.type in _FSTRING or onceki.type in _FSTRING:
                # f-metin parçaları arasında özgün boşluk korunur.
                cikti.append(kod_arasi(satirlar, onceki, tok))
            else:
                cikti.append(_bosluk(onceki, tok, ikinci_onceki, yigin))
        cikti.append(tok.string)
        if tok.type == getattr(tokenize, "FSTRING_START", -1):
            fmetin += 1
        elif tok.type == getattr(tokenize, "FSTRING_END", -1):
            fmetin = max(0, fmetin - 1)
        elif fmetin:
            pass  # f-metin içindeki parantezler derinliği etkilemez
        elif tok.string in _ACANLAR and tok.type == tokenize.OP:
            derinlik += 1
            yigin.append([tok.string, False])
        elif tok.string in _KAPAYANLAR and tok.type == tokenize.OP:
            derinlik = max(0, derinlik - 1)
            if yigin:
                yigin.pop()
        elif yigin and yigin[-1][0] == "(":
            # Parametre listesinde 'x: tür' görüldüyse '=' boşluklu yazılır;
            # virgülde sonraki parametreye geçilir.
            if tok.string == ":":
                yigin[-1][1] = True
            elif tok.string == ",":
                yigin[-1][1] = False
        ikinci_onceki, onceki = onceki, tok
        if tok.end[0] > tok.start[0]:
            satir_basi = False

    metin = "".join(cikti).strip("\n") + "\n"
    if _ast_imzasi(metin) != imza:
        raise BicimlendirmeHatasi(
            "Biçimlendirme kodun anlamını değiştirecekti; kod olduğu gibi bırakıldı.")
    return metin


def kod_arasi(satirlar, onceki, tok):
    if onceki.end[0] != tok.start[0]:
        return ""
    satir = satirlar[tok.start[0] - 1]
    return satir[onceki.end[1]:tok.start[1]]


_FONKSIYON_KW = ("fonksiyon", "def")
_KAPSAM_KW = ("küresel", "global", "yerel_olmayan", "nonlocal")
_DONGU_KW = ("için", "döngü", "for")


def _fonksiyon_bloklari(toklar):
    """[(bas, bit)] — her fonksiyon tanımının ('fonksiyon' belirtecinden
    gövdesinin son belirtecine kadar) belirteç dizini aralığı."""
    bloklar = []
    for i, tok in enumerate(toklar):
        if tok.type != tokenize.NAME or tok.string not in _FONKSIYON_KW:
            continue
        if i + 1 >= len(toklar) or toklar[i + 1].type != tokenize.NAME:
            continue
        # Başlığın sonu (derinlik 0'daki NEWLINE), ardından INDENT gelmeli.
        j, derinlik = i, 0
        while j < len(toklar):
            t = toklar[j]
            if t.type == tokenize.OP and t.string in _ACANLAR:
                derinlik += 1
            elif t.type == tokenize.OP and t.string in _KAPAYANLAR:
                derinlik -= 1
            elif t.type == tokenize.NEWLINE and derinlik <= 0:
                break
            j += 1
        k = j + 1
        while k < len(toklar) and toklar[k].type in (tokenize.NL, tokenize.COMMENT):
            k += 1
        if k >= len(toklar) or toklar[k].type != tokenize.INDENT:
            bloklar.append((i, j))  # tek satırlık gövde: "fonksiyon f(): döndür 1"
            continue
        seviye = 0
        while k < len(toklar):
            if toklar[k].type == tokenize.INDENT:
                seviye += 1
            elif toklar[k].type == tokenize.DEDENT:
                seviye -= 1
                if seviye == 0:
                    break
            k += 1
        bloklar.append((i, k))
    return bloklar


def _parametre_mi(toklar, i):
    """toklar[i] bir fonksiyon tanımının parametre listesinde mi?"""
    derinlik = 0
    for j in range(i - 1, -1, -1):
        t = toklar[j]
        if t.type == tokenize.OP and t.string in _KAPAYANLAR:
            derinlik += 1
        elif t.type == tokenize.OP and t.string in _ACANLAR:
            if derinlik == 0:
                return (t.string == "(" and j >= 2 and toklar[j - 1].type == tokenize.NAME
                        and toklar[j - 2].string in _FONKSIYON_KW)
            derinlik -= 1
        elif t.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            return False
    return False


def _onceki_anlamli(toklar, i):
    """toklar[i]'den önceki, satır sonu (NL) ve yorum olmayan belirteç."""
    j = i - 1
    while j >= 0 and toklar[j].type in (tokenize.NL, tokenize.COMMENT):
        j -= 1
    return toklar[j] if j >= 0 else None


def _parametre_adi_mi(toklar, i):
    """toklar[i] bir fonksiyon tanımındaki parametrenin ADI mı? Varsayılan
    değer (f(a=x) içindeki x) ve tür ipucu (f(a: x)) dış kapsamdaki adın
    kullanımıdır, parametre değildir."""
    if not _parametre_mi(toklar, i):
        return False
    onceki = _onceki_anlamli(toklar, i)
    return onceki is not None and onceki.string in ("(", ",", "*", "**")


def _baslik_sonu(toklar, bas):
    """'fonksiyon' belirtecinden (bas) başlayan tanımın başlığını bitiren
    ':' belirtecinin dizini."""
    derinlik = 0
    for j in range(bas, len(toklar)):
        t = toklar[j]
        if t.type == tokenize.OP and t.string in _ACANLAR:
            derinlik += 1
        elif t.type == tokenize.OP and t.string in _KAPAYANLAR:
            derinlik -= 1
        elif t.type == tokenize.OP and t.string == ":" and derinlik <= 0:
            return j
        elif t.type == tokenize.NEWLINE:
            return j
    return len(toklar) - 1


def _kapsamda(toklar, i, blok):
    """toklar[i] fonksiyon bloğunun kendi kapsamında mı? Başlıktaki
    parametre adları içeride sayılır; fonksiyonun adı, varsayılan değerler
    ve tür ipuçları dış kapsamda değerlendirilir."""
    bas, bit = blok
    if not bas <= i <= bit:
        return False
    if i <= _baslik_sonu(toklar, bas):
        return _parametre_adi_mi(toklar, i)
    return True


def _sinif_bloklari(toklar):
    """[(bas, bit)] — her 'sınıf' tanımının belirteç aralığı."""
    bloklar = []
    for i, tok in enumerate(toklar):
        if tok.type != tokenize.NAME or tok.string not in ("sınıf", "class"):
            continue
        if i + 1 >= len(toklar) or toklar[i + 1].type != tokenize.NAME:
            continue
        j = _baslik_sonu(toklar, i)
        k = j + 1
        while k < len(toklar) and toklar[k].type in (tokenize.NL, tokenize.COMMENT,
                                                     tokenize.NEWLINE):
            k += 1
        if k >= len(toklar) or toklar[k].type != tokenize.INDENT:
            continue
        seviye = 0
        while k < len(toklar):
            if toklar[k].type == tokenize.INDENT:
                seviye += 1
            elif toklar[k].type == tokenize.DEDENT:
                seviye -= 1
                if seviye == 0:
                    break
            k += 1
        bloklar.append((i, k))
    return bloklar


def _sinif_uyesi_tanimi_mi(toklar, i, sinif_bloklari, fonk_bloklari):
    """toklar[i] doğrudan bir sınıf gövdesinde tanımlanan bir üye mi
    (metot adı 'fonksiyon ad' ya da sınıf özniteliği 'ad = ...')?"""
    sinif = [b for b in sinif_bloklari if b[0] < i <= b[1]]
    if not sinif:
        return False
    en_ic_sinif = max(b[0] for b in sinif)
    # Sınıfın içindeki bir fonksiyonun kapsamındaysa üye değildir; metot adı
    # ise fonksiyonun dış kapsamındadır (yani sınıf gövdesinde).
    if any(b[0] > en_ic_sinif and _kapsamda(toklar, i, b) for b in fonk_bloklari):
        return False
    onceki = _onceki_anlamli(toklar, i)
    if onceki is not None and onceki.string in _FONKSIYON_KW:
        return True
    sonraki = toklar[i + 1].string if i + 1 < len(toklar) else ""
    if sonraki in ("=", ":") and (onceki is None or onceki.type in (
            tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)):
        return True
    return False


def _anahtar_arguman_mi(toklar, i):
    """toklar[i], bir çağrıdaki anahtar kelime argümanının ADI mı
    (yazdır(1, sep=sep) içindeki soldaki sep)? Tanım parametresi
    (fonksiyon f(sep=1)) sayılmaz."""
    if i + 1 >= len(toklar) or toklar[i + 1].string != "=":
        return False
    # Eskiden yalnızca hemen önceki belirtece bakılıyordu; argüman alt
    # satırdaysa önceki belirteç satır sonu (NL) olduğundan 'sep=sep'
    # 'ayrac=ayrac' oluyordu. Satır sonu ve yorumlar atlanır.
    onceki = _onceki_anlamli(toklar, i)
    if onceki is None or onceki.string not in ("(", ","):
        return False
    # En içteki açık parantez '(' olmalı ve bir tanıma ait olmamalı.
    derinlik = 0
    for j in range(i - 1, -1, -1):
        t = toklar[j]
        if t.type == tokenize.OP and t.string in _KAPAYANLAR:
            derinlik += 1
        elif t.type == tokenize.OP and t.string in _ACANLAR:
            if derinlik == 0:
                return t.string == "(" and not _parametre_mi(toklar, i)
            derinlik -= 1
    return False


def _yerel_mi(toklar, bas, bit, ad):
    """'ad', [bas, bit] aralığındaki fonksiyonun yerel değişkeni mi
    (parametre, atama, döngü değişkeni, 'olarak ad'), ve küresel /
    yerel_olmayan olarak bildirilmemiş mi?"""
    yerel = False
    for i in range(bas, bit + 1):
        t = toklar[i]
        if t.type != tokenize.NAME:
            continue
        if t.string in _KAPSAM_KW:
            j = i + 1
            while j <= bit and toklar[j].type != tokenize.NEWLINE:
                if toklar[j].string == ad:
                    return False
                j += 1
        if t.string != ad or (i > 0 and toklar[i - 1].string == "."):
            continue
        # Eskiden varsayılan değer (f(a=x) içindeki x) parametre sayılıyor,
        # fonksiyon dışarıda bırakılıyordu: 'x = 1' değişip 'f(a=x)' kalıyordu.
        # Başlıkta yalnızca parametre adları fonksiyonun kendi kapsamındadır.
        if not _kapsamda(toklar, i, (bas, bit)):
            continue
        sonraki = toklar[i + 1].string if i + 1 < len(toklar) else ""
        onceki = toklar[i - 1].string if i > 0 else ""
        if _parametre_adi_mi(toklar, i):
            yerel = True
        elif sonraki in ("=", "+=", "-=", "*=", "/=", "//=", "%=", "**=", ":=") \
                and not _anahtar_arguman_mi(toklar, i):
            yerel = True
        elif onceki in _DONGU_KW or onceki in ("olarak", "as"):
            yerel = True
    return yerel


def ad_degistir(kod, eski, yeni, satir=None, sutun=None):
    """Kodda 'eski' adını 'yeni' ile değiştirir: (yeni_kod, sayi). Metinler,
    yorumlar ve öznitelikler (x.eski, kendisi.eski) değişmez. İmleç bir
    öznitelikte ya da sınıf üyesinin tanımındaysa (metot adı, sınıf
    özniteliği) tersine yalnızca bütün '.eski' öznitelikleri ve üye
    tanımları değişir. Konum verilmezse, düz kullanımı olmayan ad
    öznitelik sayılır. f-metin içindeki
    {eski} ifadeleri de değiştirilir. Çağrılardaki anahtar kelime argümanı
    adları (yazdır(1, sep=sep) içindeki soldaki sep) değişmez.

    satir/sutun (1 tabanlı, isteğe bağlı): imlecin konumu. İmleçteki ad bir
    fonksiyonun yerel değişkeniyse yalnızca o fonksiyonda değiştirilir;
    modül düzeyindeki bir adsa onu yerel olarak yeniden tanımlayan
    fonksiyonlara dokunulmaz. Konum verilmezse bütün dosya değişir."""
    toklar = list(tokenize.generate_tokens(io.StringIO(kod).readline))
    satir_baslari = [0]
    for s in kod.split("\n"):
        satir_baslari.append(satir_baslari[-1] + len(s) + 1)
    araliklar = None  # None: bütün dosya; aksi halde [(bas, bit)] dahil
    haric = []        # hariç tutulacak belirteç aralıkları
    bloklar = _fonksiyon_bloklari(toklar)
    sinif_bloklari = _sinif_bloklari(toklar)

    def oznitelik_mi(i):
        return i > 0 and toklar[i - 1].string == "."

    def uye_mi(i):
        return _sinif_uyesi_tanimi_mi(toklar, i, sinif_bloklari, bloklar)

    # Eskiden düz değişken değişirken 'kendisi.eski' öznitelikleri de
    # değişiyor, 'o.eski' kalıyordu (AttributeError). Artık iki ayrı iş var:
    # düz değişken değişirken hiçbir özniteliğe dokunulmaz; imleç bir
    # öznitelikte (o.eski) ya da sınıf üyesinin tanımındaysa (metot adı,
    # sınıf özniteliği) bütün '.eski' öznitelikleri ve üye tanımları değişir.
    imlec = None
    if satir is not None and sutun is not None:
        for i, tok in enumerate(toklar):
            if (tok.type == tokenize.NAME and tok.string == eski and tok.start[0] == satir
                    and tok.start[1] <= sutun - 1 <= tok.end[1]):
                imlec = i
                break
    if imlec is not None:
        uye_modu = oznitelik_mi(imlec) or uye_mi(imlec)
    else:
        # Konum yoksa: düz (öznitelik ve üye tanımı olmayan) kullanım varsa
        # düz değişken, yoksa öznitelik değiştirilir.
        uye_modu = not any(
            t.type == tokenize.NAME and t.string == eski and not oznitelik_mi(i)
            and not uye_mi(i) and not _anahtar_arguman_mi(toklar, i)
            for i, t in enumerate(toklar))
    if uye_modu:
        konumlar = []
        for i, tok in enumerate(toklar):
            if tok.type != tokenize.NAME or tok.string != eski:
                continue
            if oznitelik_mi(i) or uye_mi(i):
                konumlar.append(satir_baslari[tok.start[0] - 1] + tok.start[1])
        for k in reversed(konumlar):
            kod = kod[:k] + yeni + kod[k + len(eski):]
        return kod, len(konumlar)
    if imlec is not None:
        # İmleci içeren en içteki fonksiyon (parametreler dahil).
        icerenler = [b for b in bloklar if _kapsamda(toklar, imlec, b)]
        yerel_blok = None
        for b in sorted(icerenler, key=lambda b: b[1] - b[0]):
            if _yerel_mi(toklar, b[0], b[1], eski):
                yerel_blok = b
                break
        if yerel_blok is not None:
            araliklar = [yerel_blok]
            haric = [b for b in bloklar if yerel_blok[0] < b[0] and b[1] <= yerel_blok[1]
                     and _yerel_mi(toklar, b[0], b[1], eski)]
        else:
            haric = [b for b in bloklar if _yerel_mi(toklar, b[0], b[1], eski)]
            # İç içe fonksiyonlarda dıştaki yerel adı içtekinin kapsamına alır.
            haric = [b for b in haric if not any(
                d[0] < b[0] and b[1] <= d[1] for d in haric if d != b)]
    konumlar = []
    for i, tok in enumerate(toklar):
        if tok.type != tokenize.NAME or tok.string != eski:
            continue
        if araliklar is not None and not any(_kapsamda(toklar, i, b) for b in araliklar):
            continue
        if any(_kapsamda(toklar, i, b) for b in haric):
            continue
        if oznitelik_mi(i) or uye_mi(i):
            continue
        if _anahtar_arguman_mi(toklar, i):
            continue
        konumlar.append(satir_baslari[tok.start[0] - 1] + tok.start[1])
    for k in reversed(konumlar):
        kod = kod[:k] + yeni + kod[k + len(eski):]
    return kod, len(konumlar)
