"""TürKod tokenizer / lexer.

Bu modülün amacı:
- Kodu string, f-string, yorum, sayı, tanımlayıcı, anahtar kelime,
  sözlük kelimesi, işleç ve girinti/çıkıntı token'larına ayırmak.
- Kullanıcı tanımlarını sözlük kelimelerinden ayırmak.
- converter.py ve app.py içindeki regex tabanlı işlemleri daha güvenli hale getirmek.

Not:
- Bu bir lexer'dır, parser değildir.
- TürKod'u tam bir dil yapmak için arkasından grammar/parser/AST gerekir.
"""

from __future__ import annotations

import io
import tokenize as py_tokenize
import token as py_token
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Set

try:
    from .dictionary import _keyword_words, _builtin_words, _block_words
except ImportError:
    # Modül tek başına test edilirse sessizce boş kümelerle devam et.
    _keyword_words = set()
    _builtin_words = set()
    _block_words = set()


class TokenTuru(Enum):
    ANAHTAR = "anahtar_kelime"
    SOZLUK = "sozluk_kelimesi"
    KULLANICI = "kullanici_tanimi"
    TANIMLAYICI = "tanimlayici"
    SAYI = "sayi"
    METIN = "metin"
    F_METIN = "f_metin"
    YORUM = "yorum"
    ISLEC = "isleç"
    NOKTALAMA = "noktalama"
    YENI_SATIR = "yeni_satir"
    GIRINTI = "girinti"
    GIRINTI_BITISI = "girinti_bitisi"
    BILINMEYEN = "bilinmeyen"
    DOSYA_SONU = "dosya_sonu"


class TokenizerHatasi(Exception):
    def __init__(self, mesaj: str, satir: Optional[int] = None, sutun: Optional[int] = None):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.satir = satir
        self.sutun = sutun


@dataclass(frozen=True)
class Token:
    tur: TokenTuru
    deger: str
    satir: int          # 1 tabanlı
    sutun: int          # 1 tabanlı başlangıç
    son_satir: int      # 1 tabanlı
    son_sutun: int      # 1 tabanlı, özel konum; Tk indexi için son_sutun - 1 kullan

    def __str__(self) -> str:
        return (
            f"[{self.tur.value}] {self.deger!r} "
            f"({self.satir}:{self.sutun} -> {self.son_satir}:{self.son_sutun})"
        )


# Python keyword karşılığı olan TürKod kelimeleri ve blok başlatıcılar.
ANAHTAR_KELIMELER: Set[str] = set(_keyword_words) | set(_block_words)

# Sözlükte geçen ama Python keyword olmayan kelimeler.
# Örnek: yazdır, aralık, karekök, yönlü_ışık, varlık...
SOZLUK_KELIMELERI: Set[str] = set(_builtin_words) - ANAHTAR_KELIMELER

# Süslü parantez, köşeli parantez, normal parantez, virgül, nokta vb.
NOKTALAMA_ISARETLERI: Set[str] = set("()[]{},:;.")

# Python 3.12+ f-string token türleri varsa al.
_FSTRING_TURLERI: Set[int] = set()
for _ad in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    if hasattr(py_token, _ad):
        _FSTRING_TURLERI.add(getattr(py_token, _ad))


def _fstring_mi(deger: str) -> bool:
    """STRING token'ının f-string olup olmadığını ön ekine bakarak anlar."""
    for i, karakter in enumerate(deger):
        if karakter in ("'", '"'):
            return "f" in deger[:i].lower()
    return False


def _ad_turu(deger: str, kullanici_adlari: Set[str]) -> TokenTuru:
    if deger in kullanici_adlari:
        return TokenTuru.KULLANICI

    if deger in ANAHTAR_KELIMELER:
        return TokenTuru.ANAHTAR

    if deger in SOZLUK_KELIMELERI:
        return TokenTuru.SOZLUK

    return TokenTuru.TANIMLAYICI


def _py_tokeni_donustur(tok, kullanici_adlari: Set[str]) -> Optional[Token]:
    tur_kodu = tok.type
    deger = tok.string

    # Kodlamayı ve boş yeni satırları token akışında gürültü olarak tutma.
    if tur_kodu == py_tokenize.ENCODING:
        return None

    if tur_kodu == py_tokenize.NL:
        return None

    satir = tok.start[0]
    sutun = tok.start[1] + 1
    son_satir = tok.end[0]
    son_sutun = tok.end[1] + 1

    if tur_kodu == py_tokenize.NAME:
        tur = _ad_turu(deger, kullanici_adlari)

    elif tur_kodu == py_tokenize.STRING:
        tur = TokenTuru.F_METIN if _fstring_mi(deger) else TokenTuru.METIN

    elif tur_kodu in _FSTRING_TURLERI:
        tur = TokenTuru.F_METIN

    elif tur_kodu == py_tokenize.NUMBER:
        tur = TokenTuru.SAYI

    elif tur_kodu == py_tokenize.COMMENT:
        tur = TokenTuru.YORUM

    elif tur_kodu == py_tokenize.OP:
        tur = TokenTuru.NOKTALAMA if deger in NOKTALAMA_ISARETLERI else TokenTuru.ISLEC

    elif tur_kodu == py_tokenize.NEWLINE:
        tur = TokenTuru.YENI_SATIR

    elif tur_kodu == py_tokenize.INDENT:
        tur = TokenTuru.GIRINTI

    elif tur_kodu == py_tokenize.DEDENT:
        tur = TokenTuru.GIRINTI_BITISI

    elif tur_kodu == py_tokenize.ENDMARKER:
        tur = TokenTuru.DOSYA_SONU

    elif tur_kodu == py_tokenize.ERRORTOKEN:
        tur = TokenTuru.BILINMEYEN

    else:
        tur = TokenTuru.BILINMEYEN

    return Token(
        tur=tur,
        deger=deger,
        satir=satir,
        sutun=sutun,
        son_satir=son_satir,
        son_sutun=son_sutun,
    )


def tokenize(kod: str, kullanici_adlari: Iterable[str] = ()) -> List[Token]:
    """TürKod kodunu token listesine ayırır.

    kullanici_adlari:
        dictionary.kullanici_tanimlari(kod) ile alınan kullanıcı tanımları.
        Bu isimler sözlük kelimesi olsa bile KULLANICI token'ı olarak işaretlenir.
    """
    kullanici_set = set(kullanici_adlari)
    tokenlar: List[Token] = []

    try:
        py_tokenlar = py_tokenize.generate_tokens(io.StringIO(kod).readline)

        for tok in py_tokenlar:
            token = _py_tokeni_donustur(tok, kullanici_set)
            if token is not None:
                tokenlar.append(token)

    except (py_tokenize.TokenError, IndentationError, SyntaxError) as hata:
        satir = getattr(hata, "lineno", None)
        sutun = getattr(hata, "offset", None)
        raise TokenizerHatasi(str(hata), satir, sutun) from hata

    return tokenlar


def korunacak_tokenlar(tokenlar: Iterable[Token]) -> List[Token]:
    """Çeviri sırasında dokunulmaması gereken token'ları döndürür."""
    return [
        t for t in tokenlar
        if t.tur in (TokenTuru.METIN, TokenTuru.F_METIN, TokenTuru.YORUM)
    ]


def cevrilebilir_tokenlar(tokenlar: Iterable[Token]) -> List[Token]:
    """Sözlük çevirisine girebilecek token'ları döndürür."""
    return [
        t for t in tokenlar
        if t.tur in (TokenTuru.ANAHTAR, TokenTuru.SOZLUK)
    ]


def token_akisi_yazdir(tokenlar: Iterable[Token]) -> None:
    for token in tokenlar:
        print(token)
