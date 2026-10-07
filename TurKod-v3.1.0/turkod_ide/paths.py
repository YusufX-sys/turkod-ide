"""PyInstaller ve normal Python icin yol yardimcilari."""
import os
import sys
import tempfile
from pathlib import Path


def kaynak_kok() -> str:
    """Kaynak dosyalarin kok dizinini bulur."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS

    return str(Path(__file__).resolve().parents[1])


def kaynak_yolu(dosya_adi: str = "") -> str:
    """Paket icindeki kaynak dosyalar icin yol uretir."""
    base = kaynak_kok()

    if dosya_adi:
        return os.path.join(base, dosya_adi)

    return base


def calisma_yolu(dosya_adi: str = "") -> str:
    """Yazilabilir calisma zamani dosyalari icin yol uretir."""
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "TurKod",
        )
    else:
        # Geliştirme ortamında kaynak kodu proje köküne yazmak yerine,
        # kullanıcıya ait tek bir yazılabilir klasör kullanmak daha güvenlidir.
        base = os.path.join(os.path.expanduser("~"), ".turkod")

    # Klasör oluşturulamazsa (aynı adlı bir dosya var, izin yok, LOCALAPPDATA
    # bozuk) eskiden dictionary.py içe aktarılırken backend çöküyor, program
    # hiç açılmıyordu. Geçici klasöre düşülür; o da olmazsa kullanılabilir
    # olmasa da bir yol döndürülür (yazma noktaları zaten hataları yakalıyor).
    for aday in (base, os.path.join(tempfile.gettempdir(), "TurKod")):
        try:
            os.makedirs(aday, exist_ok=True)
            base = aday
            break
        except OSError:
            continue

    if dosya_adi:
        return os.path.join(base, dosya_adi)

    return base
