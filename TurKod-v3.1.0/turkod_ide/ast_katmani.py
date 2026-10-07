"""TürKod AST doğrulama katmanı.

TürKod, Python'un Türkçe yüzeyi olduğu için biçimsel dil tanımını
Python'un kendi ast modülü sağlar. Bu katman:
- tokenizer ile sözcük düzeyinde hata kontrolü yapar
- converter ile Python'a çevirir
- ast.parse ile yapısal doğrulama yapar
- Türkçe hata mesajları ve satır/sütun bilgisi döner
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .tokenizer import tokenize, TokenizerHatasi
from .converter import turkce_kodu_donustur

# Python SyntaxError mesajlarının Türkçe karşılıkları
HATA_CEVIRILERI = {
    # Sözdizimi hataları (SyntaxError)
    "invalid syntax": "geçersiz sözdizimi",
    "unexpected EOF while parsing": "kod eksik bitiyor (kapatılmamış blok veya parantez olabilir)",
    "expected ':'": "':' bekleniyor",
    "invalid decimal literal": "geçersiz sayı yazımı",
    "unmatched ')'": "eşleşmeyen fazladan ')' var (açılmamış parantez kapatılıyor)",
    "unmatched ']'": "eşleşmeyen fazladan ']' var (açılmamış köşeli parantez kapatılıyor)",
    "unmatched '}'": "eşleşmeyen fazladan '}' var (açılmamış süslü parantez kapatılıyor)",
    "unterminated f-string literal": "kapatılmamış f-string var",
    "too many nested parentheses": "çok fazla iç içe parantez var",
    "expected 'except' or 'finally' block": "'dene' bloğundan sonra 'hata_yakala' veya 'sonunda' bloğu bekleniyor",
    "cannot assign to literal": "sabit değere atama yapılamaz",
    "cannot assign to function call": "fonksiyon çağrısına atama yapılamaz",
    "f-string expression part cannot include a backslash": "f-string ifadesinde ters eğik çizgi kullanılamaz",
    "positional argument follows keyword argument": "konumlu argüman anahtar kelimeli argümandan sonra gelemez",
    "keyword argument repeated": "anahtar kelimeli argüman tekrarlanmış",
    "expression cannot contain assignment": "ifade içinde atama yapılamaz",
    "starred assignment target must be in a list or tuple": "yıldızlı atama hedefi liste veya demet içinde olmalı",
    "closing parenthesis ')' does not match opening parenthesis '['": "kapatma ')' açma '[' ile eşleşmiyor",
    "closing parenthesis ']' does not match opening parenthesis '('": "kapatma ']' açma '(' ile eşleşmiyor",
    "unterminated string literal": "kapatılmamış string var",
    "invalid character": "geçersiz karakter",
    "expected indented block": "girintili blok bekleniyor",
    "indentation error": "girinti hatası",
    # Python 3.10+ mesajları (eskiden genel "expected" anahtarına düşüp
    # yarım "beklenen:" mesajı üretiyordu)
    "expected an indented block": "girintili blok bekleniyor (bloğun gövdesi girintili olmalı)",
    "unexpected indent": "beklenmeyen girinti",
    "unindent does not match any outer indentation level": "girinti seviyesi üstteki bloklarla uyuşmuyor",
    "inconsistent use of tabs and spaces": "girintide sekme ve boşluk karışık kullanılmış",
    "unterminated triple-quoted string literal": "kapatılmamış çok satırlı metin (\"\"\" eksik)",
    "invalid syntax. perhaps you forgot a comma": "geçersiz sözdizimi (virgül unutulmuş olabilir)",
    "invalid syntax. maybe you meant '==' or ':='": "geçersiz sözdizimi (karşılaştırma için '==' kullanın)",
    "cannot assign to expression": "ifadeye atama yapılamaz",
    "cannot assign to": "atama yapılamaz:",
    "unexpected eof": "kod eksik bitiyor (kapatılmamış blok veya parantez olabilir)",
    "unexpected character after line continuation character": "satır devam karakterinden (\\) sonra beklenmeyen karakter",
    "missing parentheses in call to": "fonksiyon çağrısında parantez eksik:",
    "invalid non-printable character": "görünmeyen geçersiz karakter",
    "leading zeros in decimal integer literals are not permitted": "sayılar başında sıfırla yazılamaz",
    "'return' outside function": "'döndür' fonksiyon dışında kullanılamaz",
    "'break' outside loop": "'kır' döngü dışında kullanılamaz",
    "'continue' not properly in loop": "'devam_et' döngü dışında kullanılamaz",

    # Runtime hataları (çalışma zamanı)
    "name is not defined": "tanımsız değişken kullanıldı",
    "division by zero": "sıfıra bölme yapılamaz",
    "unsupported operand type": "desteklenmeyen işlem türü",
    "cannot concatenate": "birleştirilemiyor",
    "not subscriptable": "indekslenemiyor (dizi/liste bekleniyor)",
    "not callable": "çağrılamıyor (fonksiyon bekleniyor)",
    "list index out of range": "liste sınırı aşıldı",
    "tuple index out of range": "demet sınırı aşıldı",
    "string index out of range": "string sınırı aşıldı",
    "dictionary key": "sözlük anahtarı bulunamadı",
    "has no attribute": "özelliği/metodu bulunamadı",
    "unexpected keyword argument": "beklenmeyen anahtar kelime argümanı",
    "required positional argument": "zorunlu konumlu argüman eksik",
    "too many arguments": "çok fazla argüman",
    "too few arguments": "çok az argüman",
    "maximum recursion depth exceeded": "maksimum özyineleme derinliği aşıldı (sonsuz döngü?)",
    "file not found": "dosya bulunamadı",
    "permission denied": "erişim izni reddedildi",
    "no such file or directory": "dosya veya dizin bulunamadı",
    "invalid literal for int()": "geçersiz tamsayı değeri",
    "invalid literal for float()": "geçersiz ondalık değer",
    "could not convert string to float": "string ondalık sayıya dönüştürülemedi",
    "could not convert string to int": "string tamsayıya dönüştürülemedi",
    "encode() argument 1 must be str": "kodlama argümanı string olmalı",
    "cannot unpack": "açılamıyor (yapı uygun değil)",
    "cannot be interpreted as an integer": "tamsayı olarak yorumlanamıyor",
    "must be str, not": "string olmalı, şu değil:",
    "expected at least": "en az şu kadar bekleniyor:",
    "got": "alınan:",
    "expected": "beklenen:",
    "object is not iterable": "nesne tekrarlanabilir değil (for döngüsü için uygun değil)",
    "cannot import name": "isim içe aktarılamadı",
    "no module named": "modül bulunamadı",
    "isinstance() arg 2 must be": "isinstance() ikinci argümanı tip olmalı",
    "int() can't convert non-string": "int() string olmayan değeri dönüştüremez",
    "str() takes no keyword arguments": "str() anahtar kelime argümanı almaz",
    "type() takes 1 or 3 arguments": "type() 1 veya 3 argüman alır",
    "object has no len()": "nesnenin uzunluğu yok (len() kullanılamaz)",
    "slice indices must be integers": "dilim indeksleri tamsayı olmalı",
    "can only concatenate": "yalnızca şunlar birleştirilebilir:",
    "not defined": "tanımsız",
}


@dataclass(frozen=True)
class DogrulamaHatasi:
    mesaj: str
    satir: Optional[int] = None
    sutun: Optional[int] = None

    def __str__(self) -> str:
        if self.satir is not None:
            if self.sutun is not None:
                return f"Satır {self.satir}, sütun {self.sutun}: {self.mesaj}"
            return f"Satır {self.satir}: {self.mesaj}"
        return self.mesaj


@dataclass
class DogrulamaSonucu:
    basarili: bool
    hatalar: List[DogrulamaHatasi] = field(default_factory=list)
    python_kodu: str = ""
    agac: Optional[ast.Module] = None


_SIRALI_CEVIRILER = sorted(HATA_CEVIRILERI.items(), key=lambda kv: len(kv[0]), reverse=True)


def _hata_mesajini_cevir(mesaj: str) -> str:
    """İngilizce Python hata mesajını Türkçeye çevirir.

    En uzun (en özgül) anahtar önce denenir; "expected"/"got" gibi ':' ile
    biten genel karşılıklarda mesajın kalanı atılmaz, sona eklenir."""
    mesaj = mesaj.strip().rstrip(".")
    kucuk = mesaj.lower()
    # Değişken içerikli kalıplar önce denenir: genel "invalid character"
    # karşılığı startswith ile önce eşleştiği için karakter ve kodu
    # (ör. '€' U+20AC) mesajdan düşüyordu.
    m = re.match(r"invalid character '(.)' \(U\+([0-9A-F]+)\)", mesaj)
    if m:
        return f"geçersiz karakter '{m.group(1)}' (U+{m.group(2)})"
    # Tüm parantez türü eşleşmezlikleri (eskiden yalnızca iki birleşim
    # çevrilebiliyordu; diğerleri İngilizce kalıyordu).
    m = re.match(r"closing parenthesis '(.)' does not match opening "
                 r"parenthesis '(.)'(?: on line (\d+))?", mesaj)
    if m:
        ek = f" (satır {m.group(3)})" if m.group(3) else ""
        return f"kapatma '{m.group(1)}' açma '{m.group(2)}'{ek} ile eşleşmiyor"
    for ingilizce, turkce in _SIRALI_CEVIRILER:
        anahtar = ingilizce.lower()
        if kucuk.startswith(anahtar):
            kalan = mesaj[len(anahtar):].strip()
            if turkce.endswith(":") and kalan:
                kalan = re.sub(r"\bon line (\d+)", r"(satır \1)", kalan)
                return f"{turkce} {kalan}"
            # "'(' was never closed" gibi önü değişken mesajlar aşağıda
            return turkce
    m = re.match(r"'(.)' was never closed", mesaj)
    if m:
        return f"'{m.group(1)}' açıldı ama kapatılmadı"
    return mesaj


def dogrula(kod: str) -> DogrulamaSonucu:
    """TürKod kodunu tokenizer + ast ile doğrular."""
    # 1. Sözcük düzeyi kontrol: kapatılmamış string, bozuk girinti vb.
    tokenizer_hatasi = None
    try:
        tokenize(kod)
    except TokenizerHatasi as e:
        tokenizer_hatasi = DogrulamaHatasi(
            _hata_mesajini_cevir(str(e.mesaj)), e.satir, e.sutun)

    # 2. Python'a çevir
    python_kodu = turkce_kodu_donustur(kod)

    # 3. Yapısal doğrulama. Tokenizer hata verdiyse bile ast.parse denenir:
    #    ast, kapatılmamış parantezde hatayı parantezin AÇILDIĞI satırda
    #    gösterir (tokenizer yalnızca dosya sonunu bildirir).
    try:
        agac = ast.parse(python_kodu)
        if tokenizer_hatasi is not None:
            return DogrulamaSonucu(
                basarili=False,
                hatalar=[tokenizer_hatasi],
                python_kodu=python_kodu,
            )
    except SyntaxError as e:
        satir = e.lineno
        # Sütunlar kullanıcıya 1 tabanlı gösterilir (tokenizer ile tutarlı).
        sutun = e.offset if e.offset else None
        return DogrulamaSonucu(
            basarili=False,
            hatalar=[DogrulamaHatasi(_hata_mesajini_cevir(e.msg), satir, sutun)],
            python_kodu=python_kodu,
        )
    except ValueError as e:
        return DogrulamaSonucu(
            basarili=False,
            hatalar=[DogrulamaHatasi(str(e))],
            python_kodu=python_kodu,
        )

    return DogrulamaSonucu(basarili=True, python_kodu=python_kodu, agac=agac)
# ---------------------------------------------------------
# Çalışma zamanı (runtime) hata çevirileri
# ---------------------------------------------------------

RUNTIME_HATA_TIPLERI = {
    "NameError": "Tanımsız İsim Hatası",
    "TypeError": "Tip Hatası",
    "ValueError": "Değer Hatası",
    "ZeroDivisionError": "Sıfıra Bölme Hatası",
    "IndexError": "İndeks Hatası",
    "KeyError": "Anahtar Hatası",
    "AttributeError": "Özellik Hatası",
    "ImportError": "İçe Aktarma Hatası",
    "ModuleNotFoundError": "Modül Bulunamadı Hatası",
    "FileNotFoundError": "Dosya Bulunamadı Hatası",
    "PermissionError": "İzin Hatası",
    "RecursionError": "Özyineleme Hatası",
    "StopIteration": "Tekrarlama Sonu",
    "RuntimeError": "Çalışma Zamanı Hatası",
    "OSError": "İşletim Sistemi Hatası",
    "IOError": "Giriş/Çıkış Hatası",
    "UnicodeDecodeError": "Unicode Kod Çözme Hatası",
    "UnicodeEncodeError": "Unicode Kodlama Hatası",
    "OverflowError": "Taşma Hatası",
    "MemoryError": "Bellek Hatası",
    "ArithmeticError": "Aritmetik Hatası",
    "FloatingPointError": "Ondalık Hatası",
    "EOFError": "Dosya Sonu Hatası",
    "ConnectionError": "Bağlantı Hatası",
    "TimeoutError": "Zaman Aşımı Hatası",
    "IsADirectoryError": "Dizin Hatası (dosya bekleniyordu)",
    "NotADirectoryError": "Dosya Hatası (dizin bekleniyordu)",
    "FileExistsError": "Dosya Zaten Var Hatası",
    "UnboundLocalError": "Tanımsız Yerel Değişken Hatası",
    "StopAsyncIteration": "Eşzamansız Tekrarlama Sonu",
}

RUNTIME_HATA_MESAJLARI = {
    "is not defined": "tanımsız (bu isimde bir değişken/fonksiyon yok)",
    "name is not defined": "isim tanımsız",
    "division by zero": "sıfıra bölme yapılamaz",
    "unsupported operand type": "desteklenmeyen işlem türü",
    "can only concatenate": "yalnızca aynı türler birleştirilebilir",
    "not subscriptable": "indekslenemiyor (liste/sözlük bekleniyor)",
    "not callable": "çağrılamıyor (fonksiyon bekleniyor)",
    "list index out of range": "liste sınırı aşıldı",
    "tuple index out of range": "demet sınırı aşıldı",
    "string index out of range": "metin sınırı aşıldı",
    "has no attribute": "özelliği/metodu bulunamadı",
    "no module named": "modül bulunamadı",
    "cannot import name": "isim içe aktarılamadı",
    "no such file or directory": "dosya veya dizin bulunamadı",
    "permission denied": "erişim izni reddedildi",
    "maximum recursion depth exceeded": "maksimum özyineleme derinliği aşıldı (sonsuz döngü olabilir)",
    "invalid literal for int()": "geçersiz tamsayı değeri",
    "invalid literal for float()": "geçersiz ondalık değer",
    "could not convert string to float": "metin ondalık sayıya dönüştürülemedi",
    "could not convert string to int": "metin tamsayıya dönüştürülemedi",
    "object is not iterable": "nesne tekrarlanabilir değil (döngü için uygun değil)",
    "unexpected keyword argument": "beklenmeyen anahtar kelime argümanı",
    "required positional argument": "zorunlu konumlu argüman eksik",
    "positional argument follows keyword argument": "konumlu argüman anahtar kelimeli argümandan sonra gelemez",
    "too many arguments": "çok fazla argüman",
    "too few arguments": "çok az argüman",
    "takes 1 positional argument": "yalnızca 1 konumlu argüman alır",
    "cannot unpack": "açılamıyor (yapı uygun değil)",
    "cannot be interpreted as an integer": "tamsayı olarak yorumlanamıyor",
    "must be str, not": "metin olmalı, şu değil:",
    "object has no len()": "nesnenin uzunluğu yok (len() kullanılamaz)",
    "is a directory": "bir dizin (dosya bekleniyordu)",
    "not a directory": "bir dizin değil",
    "file already exists": "dosya zaten var",
    "isinstance() arg 2 must be": "isinstance() ikinci argümanı tip olmalı",
    "encode() argument 1 must be str": "kodlama argümanı metin olmalı",
    "slice indices must be integers": "dilim indeksleri tamsayı olmalı",
    "local variable": "yerel değişken",
    "referenced before assignment": "atanmadan önce kullanıldı",
    "dictionary key": "sözlük anahtarı bulunamadı",
    "cannot divide": "bölünemiyor",
    "not enough values to unpack": "açılacak yeterli değer yok",
    "too many values to unpack": "açılacak çok fazla değer var",
    "invalid syntax": "geçersiz sözdizimi",
    "unexpected EOF": "kod eksik bitiyor",
}


def calistirma_hatasi_cevir(hata: Exception) -> str:
    """Çalışma zamanı hatalarını Türkçe'ye çevirir."""
    hata_tipi = type(hata).__name__
    tip_tr = RUNTIME_HATA_TIPLERI.get(hata_tipi, hata_tipi)

    mesaj = str(hata)
    mesaj_tr = mesaj
    kucuk = mesaj.lower()
    # Uzun kalıplar önce denenmeli ki kısa kalıp yanlış eşleşmesin
    for ing, tr in sorted(RUNTIME_HATA_MESAJLARI.items(), key=lambda x: len(x[0]), reverse=True):
        if ing.lower() in kucuk:
            mesaj_tr = tr
            break

    return f"{tip_tr}: {mesaj_tr}"
