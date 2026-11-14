# -*- coding: utf-8 -*-
"""TurKod kalite kapısı.

converter.py, dictionary.py ve TurKod_Sozluk.txt üzerinde altı kontrol
yapar. Herhangi biri başarısız olursa exit code 1 ile çıkar (CI'da
kullanılabilir). Çalıştırma:

    python tools/tablo_tutarlilik.py

Varsayım: bu betik, converter.py/dictionary.py/TurKod_Sozluk.txt ile
AYNI dizinde (paket kökünde) veya --paket-dizini ile verilen yolda çalışır.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


def _ascii_katlanmis(yazi: str) -> str:
    return yazi.translate(str.maketrans({
        "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    }))


# Aksansız şüpheli kök/ek listesi (kesin olarak yanlış olan, ASCII'ye
# katlanmış Türkçe kelime kökleri). Bilerek küçük tutuldu: yanlış pozitif
# üretmemek için sadece belirsizlik taşımayan kökler var.
_SUPHELI_KOKLER = (
    "cevir", "gecti", "gecis", "olustur", "duzenle", "baglanti", "gorunur",
    "yonetici", "arguman", "kayit", "akis", "bicim", "tikla", "surum",
    "kucuk", "buyuk", "dogru", "guncelle", "sikistir", "cakisma",
    "calis", "cikis", "acik", "ozellik", "sinif", "isle", "deger",
    "orani", "alani", "akisi", "sayisi", "adimi", "araligi",
    # NOT: "ismi" BİLEREK burada yok — "X_ismi" (isim+i iyelik eki,
    # örn. "argüman_ismi") zaten doğru yazım; ASCII-katlama sorunu değil.
    # İlk sürümde bunu yanlışlıkla şüpheli işaretlemiştik.
)
_SUPHELI_DESEN = re.compile(
    r"(?:^|_)(" + "|".join(_SUPHELI_KOKLER) + r")\w*(?:_|$)"
)


def _sozluk_yukle(yol: Path) -> dict:
    icerik = yol.read_text(encoding="utf-8")
    bas = icerik.find("{")
    son = icerik.rfind("}") + 1
    return ast.literal_eval(icerik[bas:son])


def _modul_ast(yol: Path) -> ast.Module:
    return ast.parse(yol.read_text(encoding="utf-8"))


def _ust_seviye_dict_literalleri(agac: ast.Module) -> dict:
    """Modül düzeyindeki `AD = {...}` atamalarını, literal_eval edilebiliyorsa
    Python nesnesi olarak döndürür."""
    sonuc = {}
    for node in agac.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            ad = node.targets[0].id
            try:
                sonuc[ad] = ast.literal_eval(node.value)
            except Exception:
                continue
    return sonuc


def kontrol_1_sozluk_yuklenebilir(sozluk_yolu: Path, hatalar: list) -> dict:
    try:
        d = _sozluk_yukle(sozluk_yolu)
    except Exception as e:
        hatalar.append(f"[1] TurKod_Sozluk.txt ast.literal_eval ile yüklenemedi: {e}")
        return {}
    if not d:
        hatalar.append("[1] Sözlük boş görünüyor.")
    return d


def kontrol_2_mukerrer_anahtar(converter_yolu: Path, hatalar: list) -> None:
    agac = _modul_ast(converter_yolu)

    class Gezici(ast.NodeVisitor):
        def visit_Dict(self, node: ast.Dict) -> None:
            gorulen = set()
            for k in node.keys:
                if isinstance(k, ast.Constant):
                    if k.value in gorulen:
                        hatalar.append(
                            f"[2] converter.py satır {node.lineno}: "
                            f"mükerrer dict anahtarı {k.value!r}"
                        )
                    gorulen.add(k.value)
            self.generic_visit(node)

    Gezici().visit(agac)


def kontrol_3_aksansiz_supheli(sozluk: dict, hatalar: list) -> list:
    supheli = []
    for desen in sozluk:
        kelime = desen.replace(r"\b", "")
        if _SUPHELI_DESEN.search(kelime):
            supheli.append(kelime)
    if supheli:
        hatalar.append(
            f"[3] {len(supheli)} adet aksansız/şüpheli anahtar bulundu "
            f"(ör: {supheli[:5]})"
        )
    return supheli


def kontrol_4_onekli_noktali(sozluk: dict, modul_cevirileri: dict, hatalar: list) -> list:
    """K5 ihlali: hedefi 'kutuphane.X' olan ama anahtarı 'kutuphane_' önekini
    TAŞIYAN flat madde — bunlar MODUL_METOTLARI'na taşınmalıydı."""
    py_prefixler = set(modul_cevirileri.values()) | set(modul_cevirileri.keys())
    ihlaller = []
    for desen, hedef in sozluk.items():
        kelime = desen.replace(r"\b", "")
        hedef = hedef.strip()
        if "." not in hedef:
            continue
        py_prefix = hedef.split(".", 1)[0]
        if py_prefix in py_prefixler and kelime.lower().startswith(py_prefix.lower() + "_"):
            ihlaller.append((kelime, hedef))
    if ihlaller:
        hatalar.append(
            f"[4] K5 ihlali: {len(ihlaller)} adet önekli+noktalı flat madde "
            f"MODUL_METOTLARI'na taşınmamış (ör: {ihlaller[:5]})"
        )
    return ihlaller


def kontrol_5_modul_metot_tutarliligi(
    modul_metotlari: dict, modul_cevirileri: dict, hatalar: list
) -> list:
    eksik = [k for k in modul_metotlari if k not in modul_cevirileri]
    if eksik:
        hatalar.append(
            f"[5] MODUL_METOTLARI'nda olup MODUL_CEVIRILERI'nde OLMAYAN "
            f"anahtarlar (py_modul çözülemez, sessizce kendi adına düşer): "
            f"{eksik}"
        )
    return eksik


def kontrol_6_ters_ceviri_ascii_onceligi(modul_metotlari: dict, hatalar: list) -> list:
    """Bir python hedefine giden birden fazla MODUL_METOTLARI anahtarı
    (aynı tablo objesini paylaşan ASCII/aksanlı takma adlar) varsa, ASCII
    biçimin dict sırasında aksanlı biçimden ÖNCE gelip gelmediğini kontrol
    eder. Öndeyse, ters çeviride (ilk-yazılan-kazanır) ASCII biçim yanlışça
    seçilir."""
    sira = list(modul_metotlari.keys())
    sorunlar = []
    for anahtar in sira:
        katlanmis = _ascii_katlanmis(anahtar)
        if katlanmis == anahtar:
            continue
        if katlanmis in modul_metotlari and modul_metotlari[katlanmis] is modul_metotlari[anahtar]:
            if sira.index(katlanmis) < sira.index(anahtar):
                sorunlar.append((katlanmis, anahtar))
    if sorunlar:
        hatalar.append(
            f"[6] Ters çeviri önceliği bozuk: ASCII takma ad, aksanlı/"
            f"kanonik biçimden ÖNCE geliyor (ters çeviride yanlış kazanır): "
            f"{sorunlar}"
        )
    return sorunlar


def calistir(paket_dizini: Path) -> int:
    converter_yolu = paket_dizini / "converter.py"
    sozluk_yolu = paket_dizini / "TurKod_Sozluk.txt"

    hatalar: list[str] = []

    sozluk = kontrol_1_sozluk_yuklenebilir(sozluk_yolu, hatalar)
    kontrol_2_mukerrer_anahtar(converter_yolu, hatalar)
    if sozluk:
        kontrol_3_aksansiz_supheli(sozluk, hatalar)

    agac = _modul_ast(converter_yolu)
    top = _ust_seviye_dict_literalleri(agac)

    # MODUL_METOTLARI ve MODUL_CEVIRILERI literal_eval ile OKUNAMAZ:
    # değerleri paylaşılan dict referansları, fonksiyon çağrıları (_ascii_
    # alias_ekle) içeriyor ve bu ikisi ÇALIŞMA ZAMANINDA (import sırasında)
    # ASCII takma adlarla genişletiliyor. Bu yüzden statik AST'den DEĞİL,
    # modülü fiilen import edip CANLI nesneden okumamız gerekir; aksi
    # halde ASCII takma adlarını "MODUL_CEVIRILERI'nde yok" diye yanlışça
    # rapor ederiz (bu hatayı ilk sürümde yaptık).
    sys.path.insert(0, str(paket_dizini.parent))
    paket_adi = paket_dizini.name
    try:
        modul = __import__(f"{paket_adi}.converter", fromlist=["converter"])
    except Exception as e:
        hatalar.append(f"[*] converter.py import edilemedi: {e}")
        modul = None

    modul_cevirileri = getattr(modul, "MODUL_CEVIRILERI", {}) if modul is not None else top.get("MODUL_CEVIRILERI", {})

    if modul is not None:
        mm = getattr(modul, "MODUL_METOTLARI", {})
        if modul_cevirileri:
            kontrol_4_onekli_noktali(sozluk, modul_cevirileri, hatalar)
            kontrol_5_modul_metot_tutarliligi(mm, modul_cevirileri, hatalar)
        kontrol_6_ters_ceviri_ascii_onceligi(mm, hatalar)

    print(f"Toplam kontrol: 6, hata sayısı: {len(hatalar)}")
    for h in hatalar:
        print(" -", h)

    return 1 if hatalar else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--paket-dizini", type=Path, default=Path(__file__).resolve().parent,  # bu dosya paketin içinde duruyor
        help="converter.py/dictionary.py/TurKod_Sozluk.txt'nin bulunduğu dizin",
    )
    args = ap.parse_args()
    sys.exit(calistir(args.paket_dizini))
