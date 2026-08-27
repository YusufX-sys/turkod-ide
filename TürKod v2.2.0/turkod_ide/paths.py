"""PyInstaller ve normal Python icin yol yardimcilari."""
import os
import sys
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
    """Yazilabilir calisma zamanı dosyalari icin yol uretir."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = str(Path(__file__).resolve().parents[1])

    if dosya_adi:
        return os.path.join(base, dosya_adi)

    return base
