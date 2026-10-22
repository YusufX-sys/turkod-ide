"""Calistirma sablonu."""


RUNNER_ORTAK = r'''# -- coding: utf-8 --
import os
import traceback
import sys
import re
import warnings

# Kütüphanelerin KENDİ kaynak kodundaki derleme uyarıları (ör. Ursina'nın
# mesh_importer.py dosyasındaki "invalid escape sequence '\P'") kullanıcıyla
# ilgisizdir ama program başında kullanıcının hatası gibi görünüyordu.
# Derleme uyarılarında "module" dosya yoludur; yalnızca ".*klasör.*" biçimi
# eşleşiyor (ters eğik çizgili desenler eşleşmiyor). Kullanıcının kendi
# kodundaki uyarılar etkilenmez.
for _kutuphane_klasoru in (r".*site-packages.*", r".*pip_packages.*"):
    warnings.filterwarnings("ignore", category=SyntaxWarning, module=_kutuphane_klasoru)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=_kutuphane_klasoru)


# Ursina FirstPersonController (birinci_şahıs_denetleyici) düşme düzeltmesi.
# Yerçekimi adımı "min(air_time, mesafe) * time.dt * 100" olduğundan tek bir
# uzun karede (program açılırken ya da bilgisayar o an meşgulken dt >~ 0.05 sn)
# oyuncu zemini geçecek kadar aşağı iner; aşağı atılan ışın artık zemini
# görmediği için oyuncu yerin altında takılı kalır (Python'da da olur, ama
# makine yavaşladıkça sıklaşır). Düzeltme: düşen oyuncunun bir önceki
# konumundan aşağı ışın atılır; arada bir zemin varsa oyuncu onun üstüne
# konur. Normal düşme/iniş davranışı değişmez.
def _tk_fpc_yamala(modul):
    sinif = getattr(modul, "FirstPersonController", None)
    if sinif is None or getattr(sinif, "_tk_yamali", False):
        return
    asil_update = sinif.update

    def update(self):
        onceki_y = self.y
        asil_update(self)
        try:
            if not getattr(self, "gravity", 0) or self.y >= onceki_y - 0.01:
                return
            from ursina import raycast, Vec3
            yukseklik = getattr(self, "height", 2)
            ray = raycast(
                Vec3(self.world_x, onceki_y + yukseklik, self.world_z), Vec3(0, -1, 0),
                distance=(onceki_y - self.y) + yukseklik,
                traverse_target=getattr(self, "traverse_target", None) or modul.scene,
                ignore=getattr(self, "ignore_list", (self,)))
            if ray.hit and ray.world_point[1] > self.y + 0.001:
                self.y = ray.world_point[1]
                if hasattr(self, "land"):
                    self.land()
        except Exception:
            pass

    sinif.update = update
    sinif._tk_yamali = True


# Kaplumbağa (turtle) Türkçe renk adları: kalem_rengi("kırmızı") eskiden
# "bad color string" hatası veriyordu (metin içleri çevrilmez).
_TK_TURTLE_RENKLER = {
    "kırmızı": "red", "yeşil": "green", "mavi": "blue", "beyaz": "white",
    "siyah": "black", "gri": "gray", "sarı": "yellow", "turuncu": "orange",
    "mor": "purple", "pembe": "pink", "kahverengi": "brown",
    "turkuaz": "turquoise", "lacivert": "navy", "altın": "gold",
    "gümüş": "silver", "bordo": "maroon", "eflatun": "violet",
    "camgöbeği": "cyan", "açık_mavi": "lightblue", "koyu_mavi": "darkblue",
    "açık_yeşil": "lightgreen", "koyu_yeşil": "darkgreen",
    "açık_gri": "lightgray", "koyu_gri": "darkgray",
}


def _tk_turtle_yamala(modul):
    ekran = getattr(modul, "TurtleScreen", None)
    if ekran is None or getattr(ekran, "_tk_yamali", False):
        return
    asil = ekran._colorstr

    def _colorstr(self, color):
        if len(color) == 1 and isinstance(color[0], str):
            ad = color[0].strip().replace("İ", "i").replace("I", "ı").lower()
            ad = ad.replace(" ", "_")
            if ad in _TK_TURTLE_RENKLER:
                color = (_TK_TURTLE_RENKLER[ad],)
        elif isinstance(color, str):
            ad = color.strip().replace("İ", "i").replace("I", "ı").lower().replace(" ", "_")
            color = _TK_TURTLE_RENKLER.get(ad, color)
        return asil(self, color)

    ekran._colorstr = _colorstr
    ekran._tk_yamali = True


def _tk_ice_aktarma_yamalari_kur():
    import importlib.abc
    import importlib.util

    yamalar = {"ursina.prefabs.first_person_controller": _tk_fpc_yamala,
               "turtle": _tk_turtle_yamala}

    class _Bulucu(importlib.abc.MetaPathFinder):
        def find_spec(self, ad, yol=None, hedef=None):
            yama = yamalar.get(ad)
            if yama is None:
                return None
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(ad)
            finally:
                if yamalar:
                    sys.meta_path.insert(0, self)
            if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
                return spec
            asil_exec = spec.loader.exec_module

            def exec_module(m):
                asil_exec(m)
                try:
                    yama(m)
                finally:
                    yamalar.pop(ad, None)
                    if not yamalar and self in sys.meta_path:
                        sys.meta_path.remove(self)

            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _Bulucu())


try:
    _tk_ice_aktarma_yamalari_kur()
except Exception:
    pass

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
    # Önce tam kalıp: eskiden yalnızca baş kısım çevrildiğinden mesaj
    # "...birleştirilebilir! (not "int") to str" diye yarım kalıyordu.
    r'can only concatenate str \(not "[^"]+"\) to str':
        "metin ile sayı gibi farklı türler + ile birleştirilemez! Önce metin() ile çevir ya da f-yazı kullan.",
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

def _yerel_modul_adi(yol, dosya_adi):
    """yol, programın içe aktardığı (geçici klasöre çevrilmiş) bir .trpy
    modülüyse "ad.trpy" döndürür."""
    try:
        if not yol or not os.path.isabs(dosya_adi):
            return None
        klasor = os.path.normcase(os.path.dirname(os.path.abspath(yol)))
        if klasor != os.path.normcase(os.path.dirname(dosya_adi)):
            return None
        ad = os.path.basename(yol)
        if not ad.endswith(".py") or "runner" in ad or ad == os.path.basename(dosya_adi):
            return None
        return ad[:-3] + ".trpy"
    except Exception:
        return None


# runner_kodu_uret() TürKod sözlüğündeki kelimeleri buraya yazar.
_TK_ONERI_KELIMELERI = []


def _isim_onerisi(e, tb):
    """Tanımsız isim için en yakın TürKod kelimesi / program adı. Yeni
    başlayanların en sık hatası ('girdi' yerine 'girdi_al', 'doğru' yerine
    'Doğru') eskiden yalnızca "tanımlı değil" diye bildiriliyordu."""
    ad = getattr(e, "name", None)
    if not isinstance(e, NameError) or not ad:
        return None
    kelimeler = set(_TK_ONERI_KELIMELERI)
    programdakiler = set()
    cagri = False
    son = tb
    while son is not None and son.tb_next is not None:
        son = son.tb_next
    if son is not None:
        cerceve = son.tb_frame
        programdakiler.update(k for k in cerceve.f_globals if not k.startswith("_"))
        programdakiler.update(k for k in cerceve.f_locals if not k.startswith("_"))
        import linecache
        satir = linecache.getline(cerceve.f_code.co_filename, son.tb_lineno)
        cagri = re.search(r"(?<![\w.])" + re.escape(ad) + r"\s*\(", satir) is not None
    kelimeler.discard(ad)
    programdakiler.discard(ad)
    kucuk = ad.casefold()
    # Büyük/küçük harf farkı ('doğru' -> 'Doğru') her zaman önerilir.
    for a in sorted(programdakiler | kelimeler):
        if a.casefold() == kucuk:
            return a
    # Sözlükteki kelimeler yalnızca ad bir komut gibi çağrıldıysa önerilir:
    # 'girdi(...)' -> 'girdi_al'; ama yazdır(isim) için 'isim_özel' değil.
    adaylar = programdakiler | (kelimeler if cagri else set())
    # 'girdi' -> 'girdi_al': adın eksik yazılmış bileşik hali önce gelir.
    bilesik = [a for a in adaylar if a.casefold().startswith(kucuk + "_")]
    if bilesik:
        return min(bilesik, key=lambda a: (len(a), a))
    import difflib
    yakin = difflib.get_close_matches(ad, adaylar, n=1, cutoff=0.75)
    return yakin[0] if yakin else None


def _hata_yazdir(e, tb, dosya_adi):
    """Yakalanmamış bir hatayı Türkçe olarak yazar; kullanıcı satırını döndürür."""
    hata_adi = type(e).__name__
    hata_adi_tr = HATA_ISIMLERI.get(hata_adi, hata_adi)

    satir_no = getattr(e, "lineno", None) if isinstance(e, SyntaxError) else None
    modul_dosyasi = None
    if isinstance(e, SyntaxError) and getattr(e, "filename", None):
        modul_dosyasi = _yerel_modul_adi(e.filename, dosya_adi)
    if satir_no is None:
        # En İÇTEKİ kullanıcı çerçevesi: fonksiyon içindeki bir hata,
        # fonksiyonun çağrıldığı satırda değil oluştuğu satırda gösterilir.
        # Aynı programın içe aktardığı yerel .trpy modülleri (geçici klasöre
        # .py olarak çevrilir) de kullanıcı kodudur.
        for frame in traceback.extract_tb(tb):
            if os.path.basename(frame.filename) == os.path.basename(dosya_adi):
                satir_no = frame.lineno
                modul_dosyasi = None
            else:
                ad = _yerel_modul_adi(frame.filename, dosya_adi)
                if ad:
                    satir_no = frame.lineno
                    modul_dosyasi = ad
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
    if modul_dosyasi:
        print(f"Dosya: {modul_dosyasi}")
    print(f"Satır Numarası: {satir_no}")
    try:
        oneri = _isim_onerisi(e, tb)
    except Exception:
        oneri = None
    if oneri:
        hata_detay += f" Bunu mu demek istediniz: '{oneri}'?"
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
except KeyboardInterrupt:
    # Konsolda Ctrl+C: İngilizce traceback yerine kısa bir Türkçe mesaj.
    print("\n[Program durduruldu (Ctrl+C)]")
    sys.exit(130)
except Exception as e:
    _hata_yazdir(e, sys.exc_info()[2], "turkce_kod_calisma.py")
    # Python gibi: yakalanmamış hata 1 çıkış koduyla biter (eskiden 0 dönüyor,
    # IDE hatalı programı başarılı bitmiş sayıyordu).
    sys.exit(1)
'''


def _oneri_kelimeleri():
    try:
        try:
            from .dictionary import TURKCE_KELIMELER
        except ImportError:
            from dictionary import TURKCE_KELIMELER
        return sorted({str(k) for k in TURKCE_KELIMELER if str(k).isidentifier()})
    except Exception:
        return []


def runner_kodu_uret(kod_yolu, program_yolu=None, calisma_dizini=None,
                     ek_yollar=()):
    """Çalıştırıcı betiği üretir.

    kod_yolu: çevrilmiş Python kodunun mutlak yolu (geçici klasörde).
    program_yolu: kullanıcının .trpy dosyası (varsa); __file__ ve sys.argv[0]
        onu gösterir.
    calisma_dizini: modül arama yoluna eklenecek kullanıcı klasörü.
    ek_yollar: sys.path'in en başına eklenecek klasörler (çevrilmiş yerel
        .trpy modüllerinin bulunduğu geçici klasör).
    """
    yollar = [y for y in ek_yollar if y]
    if calisma_dizini:
        yollar.append(calisma_dizini)
    on = "import sys as _ts\n"
    if program_yolu:
        on += f"_ts.argv = [{program_yolu!r}] + _ts.argv[1:]\n"
    if yollar:
        on += f"_ts.path[0:1] = {yollar!r}\n"
    on += "del _ts\n"
    govde = RUNNER_KODU.replace(
        "_TK_ONERI_KELIMELERI = []",
        f"_TK_ONERI_KELIMELERI = {_oneri_kelimeleri()!r}", 1)
    if program_yolu:
        govde = govde.replace(
            '_ana.__file__ = os.path.abspath("turkce_kod_calisma.py")',
            f"_ana.__file__ = {program_yolu!r}")
    return on + govde.replace('"turkce_kod_calisma.py"', repr(kod_yolu))
