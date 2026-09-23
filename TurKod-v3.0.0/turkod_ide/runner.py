"""Calistirma sablonu."""


RUNNER_KODU = r'''# -- coding: utf-8 --
import traceback
import sys
import re

HATA_ISIMLERI = {
    "NameError": "Tanımsız İsim Hatası",
    "SyntaxError": "Sözdizimi (Yazım) Hatası",
    "IndentationError": "Girinti Hatası",
    "TabError": "Sekme/Girinti Hatası",
    "TypeError": "Veri Tipi Hatası",
    "ValueError": "Geçersiz Değer Hatası",
    "ZeroDivisionError": "Sıfıra Bölme Hatası",
    "IndexError": "Liste İndeks Hatası",
    "KeyError": "Sözlük Anahtar Hatası",
    "AttributeError": "Özellik / Metot Bulunamadı Hatası",
    "ImportError": "İçe Aktarma Hatası",
    "ModuleNotFoundError": "Modül Bulunamadı Hatası",
    "FileNotFoundError": "Dosya Bulunamadı Hatası",
    "PermissionError": "İzin Hatası",
    "RecursionError": "Sonsuz Özyineleme Hatası",
    "StopIteration": "Döngü Sonu Hatası",
    "RuntimeError": "Çalışma Zamanı Hatası",
    "OSError": "Sistem Hatası",
    "IOError": "Giriş/Çıkış Hatası",
    "UnicodeDecodeError": "Karakter Kod Çözme Hatası",
    "UnicodeEncodeError": "Karakter Kodlama Hatası",
    "OverflowError": "Sayı Taşma Hatası",
    "MemoryError": "Bellek Yetersiz Hatası",
    "EOFError": "Dosya Sonu Hatası",
    "ConnectionError": "Bağlantı Hatası",
    "TimeoutError": "Zaman Aşımı Hatası",
    "IsADirectoryError": "Dizin Hatası",
    "NotADirectoryError": "Dizin Değil Hatası",
    "FileExistsError": "Dosya Zaten Var Hatası",
    "UnboundLocalError": "Tanımsız Yerel Değişken Hatası",
    "ArithmeticError": "Aritmetik Hatası",
    "FloatingPointError": "Ondalık Hatası",
}

HATA_MESAJLARI = {
    r"is not defined": "bu isimde bir değişken/fonksiyon tanımlı değil!",
    r"invalid syntax": "geçersiz kod yazımı! Eksik sembol veya hatalı kelime kullanımı var!",
    r"unexpected EOF while parsing": "kapatılmamış parantez veya tırnak işareti var!",
    r"expected an indented block": "girintili kod bloğu eksik!",
    r"unindent does not match any outer indentation level": "girinti seviyesi üst bloklarla uyuşmuyor!",
    r"inconsistent use of tabs and spaces in indentation": "girintide tab ve boşluk karışık kullanılmış!",
    r"division by zero": "bir sayı 0'a bölünemez!",
    r"list index out of range": "listenin sınırları dışında bir elemana ulaşmaya çalıştınız!",
    r"tuple index out of range": "demetin sınırları dışında bir elemana ulaşmaya çalıştınız!",
    r"string index out of range": "metnin sınırları dışında bir konuma ulaşmaya çalıştınız!",
    r"has no attribute": "bu özelliği/metodu bulunamadı!",
    r"no module named": "bu isimde bir modül/kütüphane bulunamadı!",
    r"cannot import name": "bu isim içe aktarılamadı!",
    r"no such file or directory": "dosya veya dizin bulunamadı!",
    r"permission denied": "dosyaya erişim izni yok!",
    r"maximum recursion depth exceeded": "fonksiyon kendini çok fazla çağırdı (sonsuz döngü olabilir)!",
    r"invalid literal for int\(\)": "bu değer tamsayıya dönüştürülemiyor!",
    r"invalid literal for float\(\)": "bu değer ondalık sayıya dönüştürülemiyor!",
    r"could not convert string to float": "metin ondalık sayıya dönüştürülemiyor!",
    r"object is not iterable": "bu nesne döngüyle tekrarlanamaz!",
    r"unsupported operand type": "bu türler arasında bu işlem yapılamaz!",
    r"can only concatenate str": "yalnızca aynı türler birleştirilebilir!",
    r"not subscriptable": "köşeli parantezle erişilemez (liste/sözlük bekleniyor)!",
    r"not callable": "çağrılamaz (fonksiyon bekleniyor)!",
    r"unexpected keyword argument": "beklenmeyen bir parametre adı kullanıldı!",
    r"required positional argument": "zorunlu bir parametre eksik!",
    r"takes \d+ positional argument but \d+ w(?:as|ere) given": "fonksiyona yanlış sayıda parametre verildi!",
    r"object has no len\(\)": "bu nesnenin uzunluğu ölçülemez (len() kullanılamaz)!",
    r"not enough values to unpack": "açılacak yeterli değer yok!",
    r"too many values to unpack": "açılacak çok fazla değer var!",
    r"cannot be interpreted as an integer": "tamsayı olarak yorumlanamıyor!",
    r"local variable .* referenced before assignment": "değişken atanmadan önce kullanıldı!",
    r"is a directory": "bu bir dizin (dosya bekleniyordu)!",
    r"not a directory": "bu bir dizin değil!",
    r"file already exists": "dosya zaten var!",
    r"too many open files": "çok fazla açık dosya var!",
    r"slice indices must be integers": "dilim indeksleri tamsayı olmalı!",
    r"encode\(\) argument 1 must be str": "kodlama argümanı metin olmalı!",
}

import builtins
_gercek_input = builtins.input
def _input(prompt=""):
    sys.stdout.write(str(prompt))
    sys.stdout.flush()
    return _gercek_input()
builtins.input = _input

_gercek_print = builtins.print
_CIKTI_DONUSUMLERI = [
    (re.compile(r'\bNone\b'), 'Hiçlik'),
    (re.compile(r'\bTrue\b'), 'Doğru'),
    (re.compile(r'\bFalse\b'), 'Yanlış'),
]
def _turkcelestir(obj):
    if obj is None:
        return 'Hiçlik'
    if obj is True:
        return 'Doğru'
    if obj is False:
        return 'Yanlış'
    if isinstance(obj, str):
        return obj
    metin = str(obj)
    for desen, karsilik in _CIKTI_DONUSUMLERI:
        metin = desen.sub(karsilik, metin)
    return metin
def _print(*args, **kwargs):
    yeni = tuple(_turkcelestir(a) for a in args)
    _gercek_print(*yeni, **kwargs)
builtins.print = _print

try:
    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:
        kod = f.read()
    exec(compile(kod, "turkce_kod_calisma.py", "exec"))
except Exception as e:
    exc_type, exc_obj, tb = sys.exc_info()
    hata_adi = exc_type.__name__
    hata_adi_tr = HATA_ISIMLERI.get(hata_adi, hata_adi)

    satir_no = getattr(e, "lineno", None)
    if satir_no is None:
        for frame in traceback.extract_tb(tb):
            if frame.filename == "turkce_kod_calisma.py":
                satir_no = frame.lineno
                break
    if satir_no is None:
        satir_no = "?"

    hata_detay = str(e)
    for ing, tr in HATA_MESAJLARI.items():
        hata_detay = re.sub(ing, tr, hata_detay)

    print("=" * 50)
    print(f"[HATA]: {hata_adi_tr}")
    print(f"Satır Numarası: {satir_no}")
    print(f"Açıklama: {hata_detay}")
    print("=" * 50)
'''
