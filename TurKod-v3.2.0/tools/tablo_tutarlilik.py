"""TurKod kalite kapısı (kısayol).

Asıl kontroller turkod_ide/tablo_tutarlilik.py içindedir; bu betik onu proje
kökünden çalıştırır:

    python tools/tablo_tutarlilik.py

(Eski kopya converter.py'yi paket bağlamı olmadan exec ettiği için hiç
çalışmıyordu ve kontrolleri asıl kapıdan geride kalmıştı.)
"""
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
PAKET = KOK / "turkod_ide"
sys.path.insert(0, str(PAKET))

import tablo_tutarlilik as _kapi  # noqa: E402  (turkod_ide/tablo_tutarlilik.py)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.chdir(KOK)
    sys.exit(_kapi.calistir(PAKET))
