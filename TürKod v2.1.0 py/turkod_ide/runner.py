"""Calistirma sablonu."""


RUNNER_KODU = '''# -- coding: utf-8 --
import traceback
import sys
import re

HATA_ISIMLERI = {
    "NameError": "Tanımsız Kelime Hatası",
    "SyntaxError": "Sözdizimi (Yazım) Hatası",
    "TypeError": "Veri Tipi Hatası",
    "ValueError": "Geçersiz Değer Hatası",
    "ZeroDivisionError": "Sıfıra Bölme Hatası",
    "IndexError": "Liste İndeks Hatası",
    "KeyError": "Sözlük Anahtar Hatası",
    "AttributeError": "Özellik / Metot Bulunamadı Hatası",
}

HATA_MESAJLARI = {
    r"is not defined": "Hatalı bir kelime! Düzeltmeyi deneyebilirsin!",
    r"invalid syntax": "Geçersiz kod yazımı! Eksik sembol veya hatalı kelime kullanımı var!",
    r"unexpected EOF while parsing": "Kapatılmamış parantez veya tırnak işareti var!",
    r"division by zero": "Bir sayı 0'a bölünemez!",
    r"list index out of range": "Listenin sınırları dışında bir elemana ulaşmaya çalıştınız!",
}

import builtins
_gercek_input = builtins.input

def _input(prompt=""):
    sys.stdout.write(str(prompt))
    sys.stdout.flush()
    return _gercek_input()

builtins.input = _input

try:
    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:
        kod = f.read()
    exec(compile(kod, "turkce_kod_calisma.py", "exec"))
except Exception as e:
    exc_type, exc_obj, tb = sys.exc_info()
    hata_adi = exc_type.__name__
    hata_adi_tr = HATA_ISIMLERI.get(hata_adi, hata_adi)

    satir_no = "?"
    for frame in traceback.extract_tb(tb):
        if frame.filename == "turkce_kod_calisma.py":
            satir_no = frame.lineno
            break

    hata_detay = str(e)
    for ing, tr in HATA_MESAJLARI.items():
        hata_detay = re.sub(ing, tr, hata_detay)

    print("\\n" + "=" * 50)
    print(f"[HATA]: {hata_adi_tr}")
    print(f"Satır Numarası: {satir_no}")
    print(f"Açıklama: {hata_detay}")
    print("=" * 50 + "\\n")
'''
