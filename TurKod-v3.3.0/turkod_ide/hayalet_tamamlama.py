"""Hayalet kod (satır içi AI tamamlama) — VS Code / Copilot benzeri.

Editör, imleçten önceki ve sonraki kodu gönderir; burada kodun amacını
anlatan bir bağlam (dosya adı, baştaki yorumlar, tanımlanan fonksiyon ve
sınıflar, TürKod sözlük özeti) hazırlanır ve iki kaynaktan biri kullanılır:

* yerel: Yerel AI Modelleri'nde "Otomatik tamamlama" görevine atanmış model.
  Kodlama modelleri ortadan doldurma (FIM) ile imleç öncesi + sonrasını görür.
* api:   Ayarlar → AI Kod Tamamlama'da seçilen bulut sağlayıcısı (sohbet API'si).

Model çıktısı temizlenir: düşünce blokları, ``` çitleri, imleç öncesini ya da
sonrasını tekrar eden kısımlar atılır; Python yazıldıysa TürKod'a çevrilir.
Bu modül saf işlevlerden oluşur; ağ çağrısı ide_core'dadır.
"""
import codeop
import re

TURKOD_OZETI = (
    "TürKod, Türkçe anahtar kelimeli Python'dur: yazdır=print, girdi_al=input, "
    "eğer=if, değilse_eğer=elif, değilse=else, için X içinde Y=for X in Y, "
    "döngü=while, fonksiyon=def, döndür=return, sınıf=class, kendisi=self, "
    "__başlat__=__init__ (özel adlar __ad__ biçimindedir: __isim__=__name__), "
    "dene/hata_yakala=try/except, içe_aktar=import, "
    "aralık=range, uzunluk=len, tamsayı=int, metin=str, Doğru/Yanlış/Hiçlik="
    "True/False/None, ve/veya/değil=and/or/not, kır=break, devam_et=continue."
)

IMLEC = "<İMLEÇ>"
AZAMI_SATIR = 8

# Satır sonunda imleçten sonra kalabilecek, öneriyi engellemeyen karakterler.
_SATIR_SONU_SERBEST = re.compile(r"^[\s)\]}\"':,;]*$")
_TANIM = re.compile(r"^\s*(fonksiyon|sınıf|def|class)\s+([^\s(:]+)", re.MULTILINE)
_PYTHON_IZI = re.compile(r"\b(print|def|elif|while|return|import|input|True|False|None|self)\b")
_TURKOD_IZI = re.compile(r"\b(yazdır|fonksiyon|eğer|değilse|döngü|döndür|için|içinde)\b")


def oneri_uygun_mu(once, sonra):
    """Editör imleci öneri istenecek bir yerde mi? Satırın geri kalanı boş
    (ya da yalnızca kapanış işaretleri) olmalı. Kelime ortası da uygundur:
    eskiden "x = 5▌" ya da "yazdır(isim▌" gibi en sık yerlerde öneri hiç
    istenmiyordu."""
    satir_sonu = (sonra or "").split("\n", 1)[0]
    return bool(_SATIR_SONU_SERBEST.match(satir_sonu))


_TEK_KELIME = re.compile(r"^[\wÇŞĞÜÖİçşğüöı.]+$")
_DEVAM_EDEN_SON = (",", "(", "[", "{", "+", "-", "*", "/", "%", "=", "<", ">", ".",
                   "\\", " ve", " veya", " değil", " and", " or", " not")


def yeni_satir_eki(once, sonra, cevir, birim=4):
    """İmleç TAMAMLANMIŞ bir satırın sonundaysa öneri alt satırdan başlamalı.
    Döndürür: "\n" + girinti (":" ile biten satırda bir düzey içeri) ya da
    satır sürüyorsa "". Eskiden model satır bitmişken de aynı satırın sonuna
    yazmaya çalışıyordu ("x = 5yazdır(x)")."""
    satir = (once or "").rsplit("\n", 1)[-1]
    govde = satir.strip()
    if not govde or (sonra or "").split("\n", 1)[0].strip():
        return ""
    girinti = satir[:len(satir) - len(satir.lstrip())]
    if govde.startswith("#"):
        return "\n" + girinti
    # Satır sonundaki yorum blok açmaz ("yazdır(x)  # sonuç:"); yorum atılıp
    # bakılır. Açık parantez ("d = {"a":") ise satır sürüyor demektir.
    kod_kismi = _satir_ici_yorumu_at(govde).rstrip()
    if not _dengeli_mi(kod_kismi):
        return ""
    if kod_kismi.endswith(":"):
        return "\n" + girinti + " " * birim
    govde = kod_kismi
    # Tek kelime ("yazd", "döndür") yazılıyor olabilir; aynı satırda sürdürülür.
    tek_ifade = govde in ("kır", "geç", "devam_et", "döndür", "break", "pass",
                          "continue", "return")
    if (_TEK_KELIME.match(govde) and not tek_ifade) or govde.endswith(_DEVAM_EDEN_SON):
        return ""
    try:
        py = cevir(govde)
    except Exception:  # noqa: BLE001
        return ""
    try:
        tamam = codeop.compile_command(py, "<satir>", "exec") is not None
    except SyntaxError as e:
        # "return/break fonksiyon/döngü dışında": satır tek başına derlenince
        # çıkan bağlam hatası; satırın kendisi tamamdır.
        tamam = "outside" in str(e) or "not properly in loop" in str(e)
    except (ValueError, OverflowError):
        return ""
    if not tamam:
        return ""
    # döndür / kır / devam_et / hata_fırlat'tan sonra blok biter: bir düzey dışarı.
    if re.match(r"(return|break|continue|raise|pass)\b", py.strip()) and \
            not py.strip().startswith("pass") and len(girinti) >= birim:
        girinti = girinti[:-birim]
    return "\n" + girinti


_SON_KELIME = re.compile(r"[\wÇŞĞÜÖİçşğüöı]+$")
_TAM_KELIMELER = {"Doğru", "Yanlış", "Hiçlik", "kır", "geç", "devam_et", "döndür",
                  "True", "False", "None", "break", "pass", "continue", "return"}


def kelime_ortasi_mi(once):
    """İmleç yarım yazılmış bir kelimenin sonunda mı ("yazd▌")? Sayılar ve
    kodda daha önce geçen adlar ("isim▌") tamam sayılır. Yarım kelimeyi
    model bilemez (Python'a çevrilemez); onu öneri listesi tamamlar."""
    m = _SON_KELIME.search((once or "").rsplit("\n", 1)[-1])
    if not m:
        return False
    kelime = m.group(0)
    if kelime.isdigit() or kelime in _TAM_KELIMELER:
        return False
    onceki = (once or "")[:-len(kelime)]
    return re.search(rf"(?<![\wÇŞĞÜÖİçşğüöı]){re.escape(kelime)}(?![\wÇŞĞÜÖİçşğüöı])",
                     onceki) is None


def _girinti(s):
    return len(s) - len(s.lstrip(" "))


def _dengeli_mi(s):
    """Satırda parantez ve tırnaklar kapanmış mı (yarıda kesilmiş satır)?
    Eskiden tırnaklar düz sayılıyordu: 'yazdır("Ali'nin kedisi")' içindeki
    kesme işareti satırı yarım gösteriyor, alt satır önerisi hiç gelmiyordu.
    Artık metinlerin içi (kaçış karakterleri dahil) atlanarak taranır;
    metin ve yorum içindeki parantezler sayılmaz."""
    if s.rstrip().endswith("#"):
        return False
    sayac = {"(": 0, "[": 0, "{": 0}
    kapayan = {")": "(", "]": "[", "}": "{"}
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "#":
            break
        if ch in "\"'":
            uc = s[i:i + 3]
            sinir = uc if uc in ('"""', "'''") else ch
            i += len(sinir)
            while i < n and not s.startswith(sinir, i):
                i += 2 if s[i] == "\\" else 1
            if i >= n:
                return False  # metin kapanmamış
            i += len(sinir)
            continue
        if ch in sayac:
            sayac[ch] += 1
        elif ch in kapayan:
            sayac[kapayan[ch]] -= 1
        i += 1
    return all(v == 0 for v in sayac.values())


def _satir_ici_yorumu_at(s):
    """Koddan sonra gelen yorum ("x = 5  # Output: 5") atılır; tırnak içindeki
    # korunur. Yalnızca yorumdan oluşan satırlar olduğu gibi kalır."""
    if not s.strip() or s.lstrip().startswith("#") or "#" not in s:
        return s
    tirnak = None
    for i, ch in enumerate(s):
        if ch in "\"'":
            tirnak = None if tirnak == ch else (ch if tirnak is None else tirnak)
        elif ch == "#" and tirnak is None:
            return s[:i].rstrip()
    return s


def blok_kirp(satirlar, once):
    """VS Code/Copilot gibi: bir blok açılmıyorsa yalnızca tek satır; blok
    gövdesindeysek ya da öneri bir blok açıyorsa ("için ...:") yalnızca o
    bloğun satırları. Küçük modellerin aynı satırı çeşitleyerek sürdürmesi
    ve yarıda kesilen son satır böylece gösterilmez."""
    if len(satirlar) <= 1:
        return satirlar
    imlec_satiri = (once or "").rsplit("\n", 1)[-1]
    onceki_satirlar = [s for s in (once or "").split("\n")[:-1] if s.strip()]
    govde_modu = not imlec_satiri.strip() and bool(onceki_satirlar) and \
        onceki_satirlar[-1].rstrip().endswith(":")
    if govde_modu:
        taban = len(imlec_satiri) - 1  # gövde satırları en az bu girintide
    elif satirlar[0].rstrip().endswith(":"):
        taban = _girinti(imlec_satiri)  # açılan bloğun gövdesi daha içeride
    else:
        return satirlar[:1]
    sonuc = [satirlar[0]]
    for s in satirlar[1:]:
        if s.strip() and _girinti(s) <= taban:
            break
        sonuc.append(s)
    # Token sınırında yarıda kalan son satır gösterilmez.
    while len(sonuc) > 1 and not _dengeli_mi(sonuc[-1]):
        sonuc.pop()
    return sonuc


def blok_sonu_durdurucular(once):
    """Girintili bir bloğun içindeyken üretim en dış düzeye dönünce kesilir
    (yerel modelde gereksiz jeton = bekleme)."""
    satir = (once or "").rsplit("\n", 1)[-1]
    if not satir[:1].isspace():
        return []
    return ["\ndef ", "\nclass ", "\nif __name__", "\nprint(", "\nimport ", "\nfrom "]


def kod_ozeti(kod, dosya=""):
    """Kodun amacını anlatan kısa bağlam: dosya adı, baştaki yorumlar,
    tanımlanan fonksiyon/sınıf adları."""
    parcalar = []
    if dosya:
        parcalar.append(f"Dosya: {dosya}")
    yorumlar = []
    for satir in (kod or "").splitlines()[:40]:
        s = satir.strip()
        if s.startswith("#") and len(s) > 2:
            yorumlar.append(s.lstrip("# ").strip())
        if len(yorumlar) >= 6:
            break
    if yorumlar:
        parcalar.append("Yorumlar: " + " | ".join(yorumlar))
    tanimlar = []
    for tur, ad in _TANIM.findall(kod or ""):
        etiket = "sınıf" if tur in ("sınıf", "class") else "fonksiyon"
        if (etiket, ad) not in tanimlar:
            tanimlar.append((etiket, ad))
    if tanimlar:
        parcalar.append("Tanımlar: " + ", ".join(f"{e} {a}" for e, a in tanimlar[:25]))
    return "\n".join(parcalar)


def python_onu(once, cevir):
    """Yerel kodlama modelleri Python'u TürKod'dan çok daha iyi bilir (ve
    Python daha az jeton tutar: daha hızlı). Önek satır satır Python'a
    çevrilir; imlecin bulunduğu yarım satır ve girintisi korunur."""
    govde, ayirici, satir = (once or "").rpartition("\n")
    bas = satir[:len(satir) - len(satir.lstrip())]
    try:
        py_govde = cevir(govde) + ayirici if govde else ayirici
        py_satir = cevir(satir.strip()) if satir.strip() else ""
    except Exception:  # noqa: BLE001 - çevrilemezse olduğu gibi
        return once or ""
    # Yarım satırın sonundaki boşluk ("eğer x ") korunur.
    son_bosluk = satir[len(satir.rstrip()):] if satir.strip() else ""
    return (py_govde + bas + py_satir + son_bosluk)[-6000:]


def python_sonu(sonra, cevir):
    if not (sonra or "").strip():
        return sonra or ""
    satir_sonu, ayirici, kalan = sonra.partition("\n")
    try:
        return satir_sonu + ayirici + (cevir(kalan) if kalan.strip() else kalan)
    except Exception:  # noqa: BLE001
        return sonra


def fim_onu(once, dosya=""):
    """Yerel kodlama modelinin göreceği önek: dili tanıtan bir başlık yorumu
    + dosyanın imleçten önceki kısmı."""
    baslik = f"# {TURKOD_OZETI}\n"
    if dosya:
        baslik += f"# Dosya: {dosya}\n"
    # yerel_modeller.tamamla öneki 6000 karakterde keser; başlık kaybolmasın.
    return baslik + (once or "")[-5500:]


def sohbet_mesajlari(once, sonra, dosya="", cok_satir=True):
    """Bulut sohbet API'si için (sistem, kullanıcı) mesajları."""
    sistem = (
        "Sen TürKod için satır içi kod tamamlama motorusun (VS Code / GitHub "
        f"Copilot gibi). {TURKOD_OZETI}\n"
        "Görevin: programın amacını yorumlardan, adlardan ve mevcut koddan anlayıp "
        f"{IMLEC} işaretinin yerine yazılacak en olası devamı üretmek.\n"
        "Kurallar:\n"
        "- YALNIZCA imlece eklenecek metni yaz. Açıklama, markdown ya da ``` yazma.\n"
        f"- {IMLEC} öncesindeki metni tekrar etme; sonrasındaki kodu tekrar etme.\n"
        "- TürKod anahtar kelimelerini ve koddaki mevcut adları kullan; girinti 4 boşluk.\n"
        + (f"- Bir mantıksal bütünü tamamla (en fazla {AZAMI_SATIR} satır).\n" if cok_satir
           else "- Yalnızca bulunduğun satırı tamamla (tek satır).\n")
        + "- Ne yazılacağından emin değilsen hiçbir şey yazma."
    )
    ozet = kod_ozeti((once or "") + (sonra or ""), dosya)
    kullanici = (f"{ozet}\n\n" if ozet else "") + \
        f"```\n{(once or '')[-5000:]}{IMLEC}{(sonra or '')[:1500]}\n```"
    return sistem, kullanici


_ANLAMSIZ_YORUM = re.compile(r"\s+#\s*!!.*$")


def _cop_ayikla(satirlar):
    """Küçük modellerin bozuk çıktısını keser: "!" ile başlayan satırlar
    (geçersiz kod), kendini tekrar eden satırlar ve "# !!" yorumları."""
    sonuc, gorulen = [], {}
    for s in satirlar:
        # "!" ile başlayan satır geçersiz koddur; ``` kapanış çitidir.
        if s.lstrip().startswith(("!", "```")):
            break
        s = _ANLAMSIZ_YORUM.sub("", s)
        anahtar = s.strip()
        if anahtar:
            gorulen[anahtar] = gorulen.get(anahtar, 0) + 1
            # Aynı satır üçüncü kez geliyorsa model döngüye girmiştir.
            if gorulen[anahtar] >= 3:
                break
        sonuc.append(s)
    while sonuc and not sonuc[-1].strip():
        sonuc.pop()
    return sonuc


def _girinti_duzelt(satirlar, birim=4):
    """Bazı modeller devam satırlarını girinti biriminden 1–3 boşluk kaydırır
    (9 boşluk gibi). Hepsi aynı oranda kaymışsa düzeltilir."""
    girintiler = [len(s) - len(s.lstrip(" ")) for s in satirlar[1:] if s.strip()]
    if not girintiler:
        return satirlar
    kayma = {g % birim for g in girintiler}
    if len(kayma) != 1 or 0 in kayma:
        return satirlar
    k = kayma.pop()
    return [satirlar[0]] + [s[k:] if s.strip() and s.startswith(" " * k) else s
                            for s in satirlar[1:]]


def _python_mu(metin):
    return bool(_PYTHON_IZI.search(metin)) and not _TURKOD_IZI.search(metin)


def temizle(metin, once, sonra, cok_satir=True, cevirici=None, python_cikti=False):
    """Model çıktısını editöre konacak hayalet koda çevirir; kullanılamazsa ''.

    cevirici: Python → TürKod çevirisi (converter.python_kodu_turkceye_cevir).
    python_cikti: model Python yazdı (yerel model Python önekle çalışır);
    sonuç her durumda TürKod'a çevrilir.
    """
    m = metin or ""
    # Düşünme metni (açılış etiketi olmasa da) atılır.
    m = re.sub(r"<(think|thinking)>.*?</\1>", "", m, flags=re.DOTALL | re.IGNORECASE)
    kapanis = list(re.finditer(r"</(think|thinking)>", m, re.IGNORECASE))
    if kapanis:
        m = m[kapanis[-1].end():]
    m = m.replace(IMLEC, "").replace("\r\n", "\n")
    # Kod çiti: ```dil ... ```
    cit = re.search(r"```[^\n]*\n(.*?)(```|$)", m, re.DOTALL)
    if cit:
        m = cit.group(1)
    m = m.rstrip()
    if not m.strip():
        return ""
    satir_onu = (once or "").rsplit("\n", 1)[-1]
    # İmleç boş bir satırdaysa modelin başa koyduğu boş satırlar gereksizdir
    # (eskiden "\n    eğer ..." gibi öneriler boş ilk satıra takılıp atılıyordu).
    if not satir_onu.strip():
        m = m.lstrip("\n")
    if cevirici is not None:
        # Öneri her durumda TürKod'a çevrilir (yalnızca "tamamen Python"
        # görünenler değil: "len(x)", "x.append(5)" ve karışık öneriler
        # eskiden İngilizce kalıyordu). Kodda zaten geçen adlar korunur.
        m = _cevir("\n".join(_girinti_duzelt(_cop_ayikla(m.split("\n")))), cevirici,
                   korunan=kullanici_adlari(once, sonra))
        if not m.strip():
            return ""

    # Model bulunduğu satırı baştan yazdıysa tekrar eden kısım atılır.
    if satir_onu.strip() and m.lstrip().startswith(satir_onu.strip()):
        m = m.lstrip()[len(satir_onu.strip()):]
    # İmleç girintiden sonraysa ilk satırdaki fazladan girinti atılır.
    if not satir_onu.strip():
        ilk, _, kalan = m.partition("\n")
        m = ilk.lstrip(" \t") + ("\n" + kalan if kalan else "")
    if not m.strip():
        return ""

    satirlar = _cop_ayikla(m.split("\n"))
    if not satirlar:
        return ""
    # İmleç açık bir parantezin içindeyse ("yazdır(") yalnızca o satır
    # tamamlanır; öneri yeni satıra ya da yoruma kayıyorsa anlamsızdır.
    acik = sum(satir_onu.count(a) - satir_onu.count(k) for a, k in ("()", "[]", "{}"))
    if acik > 0:
        if not satirlar[0].strip() or satirlar[0].lstrip().startswith("#"):
            return ""
        satirlar = satirlar[:1]
    if not cok_satir:
        satirlar = satirlar[:1]
    satirlar = _girinti_duzelt(satirlar[:AZAMI_SATIR])
    satirlar = [_satir_ici_yorumu_at(x) for x in satirlar]
    if cok_satir:
        satirlar = blok_kirp(satirlar, once)

    # İmleçten sonraki kodu tekrar eden sondaki satırlar atılır.
    sonraki = [s.strip() for s in (sonra or "").split("\n")[1:] if s.strip()][:AZAMI_SATIR]
    while len(satirlar) > 1 and sonraki and satirlar[-1].strip() == sonraki[0]:
        satirlar.pop()
    while len(satirlar) > 1 and not satirlar[-1].strip():
        satirlar.pop()
    m = "\n".join(satirlar).rstrip()

    # Satırın geri kalanındaki kapanış işaretleri öneride tekrarlanmaz.
    satir_sonu = (sonra or "").split("\n", 1)[0].strip()
    if satir_sonu and "\n" not in m and m.endswith(satir_sonu):
        m = m[:-len(satir_sonu)]

    return m if m.strip() else ""


_AD = re.compile(r"[A-Za-z_ÇŞĞÜÖİçşğüöı][\wÇŞĞÜÖİçşğüöı]*")


def kullanici_adlari(once, sonra):
    """Kullanıcının kodunda geçen adlar (değişken, fonksiyon, modül ...).
    Çevirici İngilizce adları da çevirdiğinden ("total" -> "toplam") bunlar
    öneride olduğu gibi bırakılmalı. Python anahtar kelimeleri ve yerleşik
    işlevleri (print, len ...) korunmaz: onlar TürKod'a çevrilir."""
    import builtins
    import keyword
    python_adlari = set(keyword.kwlist) | set(dir(builtins))
    kod = (once or "")[-8000:] + "\n" + (sonra or "")[:3000]
    # Yorum ve metin içindeki kelimeler ad sayılmaz.
    kod = re.sub(r"#[^\n]*", "", kod)
    kod = re.sub(r"(\"[^\"\n]*\"|'[^'\n]*')", "", kod)
    return {a for a in _AD.findall(kod) if a not in python_adlari}


def _cevir(m, cevirici, korunan=()):
    """Python parçasını TürKod'a çevirir; baştaki boşluk/girinti ve kodda zaten
    geçen adlar korunur."""
    bas = re.match(r"\s*", m).group(0)
    yer_tutucular = {}

    def koru(e):
        ad = e.group(0)
        if ad not in korunan:
            return ad
        tutucu = yer_tutucular.setdefault(ad, f"zqtk{len(yer_tutucular)}q")
        return tutucu

    # Yalnızca kod kısmında: metin ("...") ve yorumlara dokunulmaz.
    parcalar = re.split(r"(\"[^\"\n]*\"|'[^'\n]*'|#[^\n]*)", m)
    # f-metinlerin {…} ifadeleri koddur: f'{name}' içindeki kullanıcı adı da
    # korunur (eskiden f'{varlık_adı}' oluyordu).
    for i in range(1, len(parcalar), 2):
        if re.search(r"[rRbBuU]?[fF][rRbB]?$", parcalar[i - 1]):
            parcalar[i] = re.sub(r"(?<!\{)\{(?!\{)[^{}]*\}",
                                 lambda b: _AD.sub(koru, b.group(0)), parcalar[i])
    korumali = "".join(p if i % 2 else _AD.sub(koru, p) for i, p in enumerate(parcalar))
    try:
        cevrilmis = cevirici(korumali)
    except Exception:  # noqa: BLE001 - çevrilemezse olduğu gibi
        return m
    for ad, tutucu in yer_tutucular.items():
        cevrilmis = cevrilmis.replace(tutucu, ad)
    return cevrilmis if cevrilmis.startswith(bas) else bas + cevrilmis.lstrip()
