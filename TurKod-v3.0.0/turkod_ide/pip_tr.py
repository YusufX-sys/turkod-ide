"""Türkçe pip komutları.

IDE terminalinde şunlar çalışır:
    pip yükle numpy          ->  python -m pip install --target <kullanıcı paketleri> numpy
    pip kaldır numpy         ->  python -m pip uninstall numpy
    pip liste / göster / dondur / denetle / indir / yardım
Eski (İngilizce) alt komutlar da çalışmaya devam eder.

`pip_komutu_cevir()` bir komut satırını (cmd.exe için) döndürür; komut pip ile
ilgili değilse None döndürür ve terminal komutu olduğu gibi çalıştırılır.
"""
import re

ALT_KOMUTLAR = {
    "yükle": "install", "yukle": "install", "install": "install",
    "kaldır": "uninstall", "kaldir": "uninstall", "uninstall": "uninstall",
    "liste": "list", "list": "list",
    "göster": "show", "goster": "show", "show": "show",
    "dondur": "freeze", "freeze": "freeze",
    "denetle": "check", "check": "check",
    "indir": "download", "download": "download",
    "yardım": "help", "yardim": "help", "help": "help",
}

BAYRAKLAR = {
    "--yükselt": "--upgrade", "--yukselt": "--upgrade",
    "--evet": "--yes",
}

# Kullanıcı paketlerini (PYTHONPATH ile) görmesi gereken alt komutlar.
_PAKET_YOLU_GEREKLI = {"uninstall", "list", "show", "freeze", "check"}

_KOMUT_RE = re.compile(r"^\s*pip3?(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)


def _tirnakla(yol: str) -> str:
    return '"' + yol.replace('"', "") + '"'


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

    ilk, _, geri = kalan.partition(" ")
    alt = ALT_KOMUTLAR.get(ilk.lower())
    if alt is None:
        # Bilinmeyen alt komut: olduğu gibi ilet (pip kendi hata iletisini verir).
        return f"{py} -m pip {kalan}"

    argumanlar = []
    for parca in geri.split():
        argumanlar.append(BAYRAKLAR.get(parca.lower(), parca))
    args = " ".join(argumanlar)
    args = (" " + args) if args else ""

    if alt in ("install", "download"):
        hedef_var = any(a in ("-t", "--target") or a.startswith("--target=") for a in argumanlar)
        if alt == "install" and not hedef_var and paket_yolu:
            return f"{py} -m pip install --target {_tirnakla(paket_yolu)}{args}"
        return f"{py} -m pip {alt}{args}"

    if alt in _PAKET_YOLU_GEREKLI and paket_yolu:
        return f'set "PYTHONPATH={paket_yolu.replace(chr(34), "")}" && {py} -m pip {alt}{args}'

    return f"{py} -m pip {alt}{args}"
