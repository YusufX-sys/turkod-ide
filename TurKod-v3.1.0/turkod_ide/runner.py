"""Calistirma sablonu."""


RUNNER_ORTAK = r'''# -- coding: utf-8 --
import os
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
    r"^name '(.+?)' is not defined.*$": r"'\1' adında bir değişken/fonksiyon tanımlı değil!",
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
    r"takes \d+ positional arguments? but \d+ w(?:as|ere) given": "fonksiyona yanlış sayıda parametre verildi!",
    r"object has no len\(\)": "bu nesnenin uzunluğu ölçülemez (len() kullanılamaz)!",
    r"not enough values to unpack": "açılacak yeterli değer yok!",
    r"too many values to unpack": "açılacak çok fazla değer var!",
    r"cannot be interpreted as an integer": "tamsayı olarak yorumlanamıyor!",
    r"local variable .* referenced before assignment": "değişken atanmadan önce kullanıldı!",
    r"cannot access local variable '(.+?)' where it is not associated with a value":
        r"'\1' değişkeni atanmadan önce kullanıldı!",
    r"'(.)' was never closed": r"'\1' açıldı ama kapatılmadı!",
    r"unterminated string literal.*": "kapatılmamış metin (tırnak eksik)!",
    r"is a directory": "bu bir dizin (dosya bekleniyordu)!",
    r"not a directory": "bu bir dizin değil!",
    r"file already exists": "dosya zaten var!",
    r"file exists": "dosya zaten var!",
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
def _tr_repr(obj, gorulen=None):
    """Kapsayıcıları eleman eleman yazar: yalnızca gerçek Doğru/Yanlış/Hiçlik
    değerleri çevrilir. Eskiden str(liste) üzerinde metin değiştirme
    yapıldığından ["True story"] -> ['Doğru story'] oluyordu."""
    if obj is None:
        return 'Hiçlik'
    if obj is True:
        return 'Doğru'
    if obj is False:
        return 'Yanlış'
    t = type(obj)
    if t not in (list, tuple, dict, set):
        return repr(obj)
    gorulen = gorulen or set()
    if id(obj) in gorulen:
        return '[...]' if t is list else '{...}' if t is dict else '(...)'
    gorulen = gorulen | {id(obj)}
    if t is list:
        return '[' + ', '.join(_tr_repr(x, gorulen) for x in obj) + ']'
    if t is tuple:
        ic = ', '.join(_tr_repr(x, gorulen) for x in obj)
        return '(' + ic + (',' if len(obj) == 1 else '') + ')'
    if t is dict:
        return '{' + ', '.join(f'{_tr_repr(k, gorulen)}: {_tr_repr(v, gorulen)}'
                               for k, v in obj.items()) + '}'
    if not obj:
        return 'set()'
    return '{' + ', '.join(_tr_repr(x, gorulen) for x in obj) + '}'
def _turkcelestir(obj):
    if obj is None:
        return 'Hiçlik'
    if obj is True:
        return 'Doğru'
    if obj is False:
        return 'Yanlış'
    if isinstance(obj, str):
        return obj
    if type(obj) in (list, tuple, dict, set):
        try:
            return _tr_repr(obj)
        except Exception:
            pass
    metin = str(obj)
    for desen, karsilik in _CIKTI_DONUSUMLERI:
        metin = desen.sub(karsilik, metin)
    return metin
def _print(*args, **kwargs):
    yeni = tuple(_turkcelestir(a) for a in args)
    _gercek_print(*yeni, **kwargs)
builtins.print = _print

def _hata_yazdir(e, tb, dosya_adi):
    """Yakalanmamış bir hatayı Türkçe olarak yazar; kullanıcı satırını döndürür."""
    hata_adi = type(e).__name__
    hata_adi_tr = HATA_ISIMLERI.get(hata_adi, hata_adi)

    satir_no = getattr(e, "lineno", None) if isinstance(e, SyntaxError) else None
    if satir_no is None:
        # En İÇTEKİ kullanıcı çerçevesi: fonksiyon içindeki bir hata,
        # fonksiyonun çağrıldığı satırda değil oluştuğu satırda gösterilir.
        for frame in traceback.extract_tb(tb):
            if os.path.basename(frame.filename) == os.path.basename(dosya_adi):
                satir_no = frame.lineno
    if satir_no is None:
        satir_no = "?"

    hata_detay = str(e)
    # Büyük/küçük harf duyarsız: Python "No module named", "No such file or
    # directory", "Permission denied" gibi mesajları büyük harfle başlatır;
    # eskiden bunlar hiç Türkçeleşmiyordu.
    for ing, tr in HATA_MESAJLARI.items():
        hata_detay = re.sub(ing, tr, hata_detay, flags=re.IGNORECASE)

    print("=" * 50)
    print(f"[HATA]: {hata_adi_tr}")
    print(f"Satır Numarası: {satir_no}")
    print(f"Açıklama: {hata_detay}")
    print("=" * 50)
    return satir_no, hata_adi_tr, hata_detay
'''


RUNNER_KODU = RUNNER_ORTAK + r'''
try:
    with open("turkce_kod_calisma.py", "r", encoding="utf-8") as f:
        kod = f.read()
    # Ayrı ad alanı: kullanıcının "re = 5" gibi bir değişkeni çalıştırıcının
    # kendi modüllerini (re, sys, traceback) ezip Türkçe hata çıktısını
    # bozamaz.
    # Ad alanı gerçek bir __main__ modülüdür ve sys.modules'a kaydedilir:
    # yalnızca düz bir sözlük kullanıldığında pickle, unittest.main() ve
    # doctest kullanıcının sınıflarını/testlerini "__main__"de bulamıyordu.
    import types as _types
    _ana = _types.ModuleType("__main__")
    _ana.__file__ = os.path.abspath("turkce_kod_calisma.py")
    _ana.__builtins__ = builtins
    sys.modules["__main__"] = _ana
    exec(compile(kod, "turkce_kod_calisma.py", "exec"), _ana.__dict__)
except Exception as e:
    _hata_yazdir(e, sys.exc_info()[2], "turkce_kod_calisma.py")
'''
