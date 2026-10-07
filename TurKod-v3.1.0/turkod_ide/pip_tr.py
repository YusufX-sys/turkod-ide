"""Türkçe pip komutları.

IDE terminalinde şunlar çalışır:
    pip yükle numpy          ->  python -m pip install --target <kullanıcı paketleri> numpy
    pip güncelle numpy       ->  pip install --upgrade (kullanıcı paketlerine)
    pip sil numpy            ->  python -m pip uninstall -y numpy
    pip listele              ->  python -m pip list
    pip eskiler              ->  python -m pip list --outdated
    pip bilgi numpy          ->  python -m pip show numpy
    pip ara numpy            ->  kurulu paketler içinde ada göre arama
    pip dondur / denetle / indir / önbellek / yardım
Eş anlamlılar (kaldır/sil, liste/listele, göster/bilgi ...) ve Türkçe
karaktersiz yazımlar (yukle, guncelle ...) da kabul edilir. Eski (İngilizce)
alt komutlar da çalışmaya devam eder.

`pip_komutu_cevir()` bir komut satırını (cmd.exe için) döndürür; komut pip ile
ilgili değilse None döndürür ve terminal komutu olduğu gibi çalıştırılır.
"""
import re

ALT_KOMUTLAR = {
    # kurulum
    "yükle": "install", "yukle": "install", "kur": "install", "install": "install",
    # güncelleme (install --upgrade)
    "güncelle": "upgrade", "guncelle": "upgrade", "yükselt": "upgrade",
    "yukselt": "upgrade", "upgrade": "upgrade",
    # kaldırma
    "kaldır": "uninstall", "kaldir": "uninstall", "sil": "uninstall",
    "uninstall": "uninstall",
    # listeleme
    "liste": "list", "listele": "list", "list": "list",
    # eskimiş paketler (list --outdated)
    "eskiler": "outdated", "eskimiş": "outdated", "eskimis": "outdated",
    "outdated": "outdated",
    # ayrıntı
    "göster": "show", "goster": "show", "bilgi": "show", "show": "show",
    # kurulu paketlerde arama (pip search kaldırıldı; yerel arama yapılır)
    "ara": "search", "bul": "search", "search": "search",
    # diğer
    "dondur": "freeze", "freeze": "freeze",
    "denetle": "check", "kontrol": "check", "check": "check",
    "indir": "download", "download": "download",
    "önbellek": "cache", "onbellek": "cache", "cache": "cache",
    "sürüm": "--version", "surum": "--version", "version": "--version",
    "yardım": "help", "yardim": "help", "help": "help",
}

BAYRAKLAR = {
    "--yükselt": "--upgrade", "--yukselt": "--upgrade",
    "--evet": "--yes",
    "--sessiz": "--quiet",
    "--ayrıntılı": "--verbose", "--ayrintili": "--verbose",
    "--eskiler": "--outdated",
    "--gereksinimler": "-r", "-g": "-r",
}

# Kullanıcı paketlerini (PYTHONPATH ile) görmesi gereken alt komutlar.
_PAKET_YOLU_GEREKLI = {"uninstall", "list", "show", "freeze", "check"}

_KOMUT_RE = re.compile(r"^\s*pip3?(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
_ARGUMAN_RE = re.compile(r'"[^"]*"|\S+')
# Paket adı + sürüm kısıtı: numpy>=1.2, pandas==2.0, requests[socks]<3
_SURUM_KISITI_RE = re.compile(r"^[A-Za-z0-9_.\-\[\],]+(?:===|==|>=|<=|!=|~=|>|<)")


PIP_YARDIM = """TürKod pip komutları:
  pip yükle <paket>       Paket kurar            (kur)
  pip güncelle <paket>    Paketi günceller       (yükselt)
  pip sil <paket>         Paketi kaldırır        (kaldır)
  pip listele             Kurulu paketler        (liste)
  pip eskiler             Güncellenebilir paketler
  pip bilgi <paket>       Paket ayrıntıları      (göster)
  pip ara <metin>         Kurulu paketlerde arar (bul)
  pip dondur              requirements biçiminde liste
  pip denetle             Bağımlılık uyumluluğunu denetler
  pip indir <paket>       Kurmadan indirir
  pip sürüm               pip sürümü
  pip yardım              Bu yardım (pip'in kendi yardımı: pip help)
Bayraklar: --yükselt, --evet, --sessiz, --ayrıntılı, -g <dosya> (gereksinimler)
"""


def pip_yardim_mi(komut: str) -> bool:
    """`pip`, `pip yardım` ve `pip yardim`: Türkçe özet gösterilir."""
    m = _KOMUT_RE.match((komut or "").strip())
    if not m:
        return False
    kalan = (m.group(1) or "").strip().lower()
    return kalan in ("", "yardım", "yardim")


def _tirnakla(yol: str) -> str:
    return '"' + yol.replace('"', "") + '"'


def _paket_yolu_ile(paket_yolu, komut):
    if not paket_yolu:
        return komut
    return f'set "PYTHONPATH={paket_yolu.replace(chr(34), "")}" && {komut}'


def pip_komutu_cevir(komut: str, python_exe, paket_yolu: str):
    """`pip ...` komutunu gömülü Python'un pip'ine çevirir; pip komutu değilse None."""
    if not komut or not python_exe:
        return None
    m = _KOMUT_RE.match(komut.strip())
    if not m:
        return None

    kalan = (m.group(1) or "").strip()
    py = _tirnakla(str(python_exe))
    if not kalan:
        return f"{py} -m pip"

    # Herhangi bir boşluk (sekme dahil) alt komutu ayırır.
    parcalar = kalan.split(None, 1)
    ilk = parcalar[0]
    geri = parcalar[1] if len(parcalar) > 1 else ""
    alt = ALT_KOMUTLAR.get(ilk.lower())
    if alt is None:
        # Bilinmeyen alt komut: olduğu gibi ilet (pip kendi hata iletisini verir).
        return f"{py} -m pip {kalan}"

    argumanlar = []
    # Tırnaklı argümanlar bölünmez ("pip ara "a b"" eskiden yalnızca "a"yı
    # arıyordu).
    for parca in _ARGUMAN_RE.findall(geri):
        # Türkçe uzun bayraklar büyük/küçük harf duyarsız; kısa bayraklar
        # duyarlı ("-G" eskiden sessizce "-r" oluyordu).
        karsilik = BAYRAKLAR.get(parca)
        if karsilik is None and parca.startswith("--"):
            karsilik = BAYRAKLAR.get(parca.lower())
        parca = karsilik or parca
        # "numpy>=1.2": cmd.exe'de tırnaksız ">" / "<" yönlendirme sayılır;
        # sürüm kısıtı kaybolup "=1.2" adlı bir dosyaya yazılıyordu.
        if not parca.startswith('"') and _SURUM_KISITI_RE.match(parca):
            parca = _tirnakla(parca)
        argumanlar.append(parca)

    # "--yes" yalnızca kaldırmada geçerli bir pip seçeneğidir; diğerlerinde
    # pip "no such option" hatası veriyordu.
    if alt != "uninstall":
        argumanlar = [a for a in argumanlar if a != "--yes"]

    if alt == "--version":
        return f"{py} -m pip --version"

    if alt == "upgrade":
        alt = "install"
        if "--upgrade" not in argumanlar and "-U" not in argumanlar:
            argumanlar.insert(0, "--upgrade")

    if alt == "outdated":
        alt = "list"
        if "--outdated" not in argumanlar:
            argumanlar.insert(0, "--outdated")

    # Kaldırmada pip "Proceed (Y/n)?" diye sorar; IDE terminali etkileşimli
    # olmadığından komut takılı kalırdı. Onay otomatik verilir.
    if alt == "uninstall" and not any(a in ("-y", "--yes") for a in argumanlar):
        argumanlar.insert(0, "-y")

    args = " ".join(argumanlar)
    args = (" " + args) if args else ""

    if alt == "search":
        # `pip search` PyPI tarafından kapatıldı; kurulu paketlerde ada göre
        # arama yapılır (Windows findstr, büyük/küçük harf duyarsız).
        if not argumanlar:
            return _paket_yolu_ile(paket_yolu, f"{py} -m pip list")
        aranan = argumanlar[0].replace('"', "")
        return _paket_yolu_ile(
            paket_yolu, f'{py} -m pip list | findstr /I /C:"{aranan}"')

    if alt in ("install", "download"):
        # --user / --prefix / --root, --target ile birlikte kullanılamaz
        # (pip reddeder); kullanıcı kendi kurulum yerini seçmişse eklenmez.
        hedef_var = any(
            a in ("-t", "--target", "--user", "--prefix", "--root")
            or a.startswith(("--target=", "--prefix=", "--root="))
            for a in argumanlar)
        if alt == "install" and not hedef_var and paket_yolu:
            return f"{py} -m pip install --target {_tirnakla(paket_yolu)}{args}"
        return f"{py} -m pip {alt}{args}"

    if alt in _PAKET_YOLU_GEREKLI and paket_yolu:
        return _paket_yolu_ile(paket_yolu, f"{py} -m pip {alt}{args}")

    return f"{py} -m pip {alt}{args}"
