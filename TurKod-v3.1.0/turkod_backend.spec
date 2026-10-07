# -*- mode: python ; coding: utf-8 -*-
# Kullanım (backend_main.py ile aynı klasörden):
#     pyinstaller --noconfirm --clean turkod_backend.spec
#
# Gereksinim: PyInstaller >= 6.0. Onedir çıktısı  backend\turkod_backend.exe +
# backend\_internal\  düzeninde olur; ide_core._python_exe_bul()
# backend\_internal\python_embed\python.exe yolunu bekliyor.
import os
from PyInstaller.utils.hooks import collect_all

KOK = os.path.abspath(SPECPATH)
PAKET = os.path.join(KOK, "turkod_ide")

datas, binaries, hiddenimports = [], [], []

# Dinamik import eden ya da veri dosyası isteyen paketler.
# (uvicorn: loop/protocol/lifespan seçimleri string ile import edilir.)
for paket in ("uvicorn", "websockets", "openai", "anthropic", "groq",
              "google.genai", "certifi", "tzdata"):
    try:
        d, b, h = collect_all(paket)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:  # paket build ortamında kurulu değilse atla
        print(f"[spec] {paket} atlandı: {e}")

# dictionary.py ilk olarak <_MEIPASS>\TurKod_Sozluk.txt yoluna bakar.
datas.append((os.path.join(PAKET, "TurKod_Sozluk.txt"), "."))
# updater.mevcut_surum() <_MEIPASS>\surum.txt dosyasını okur (tek sürüm kaynağı).
datas.append((os.path.join(KOK, "surum.txt"), "."))

a = Analysis(
    [os.path.join(KOK, "backend_main.py")],
    pathex=[KOK],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # ide_core yalnızca yedek font listesi için matplotlib dener; yüzlerce MB
    # ekler. Tk varken zaten kullanılmıyor.
    excludes=["matplotlib", "IPython", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="turkod_backend",
    console=False,          # siyah pencere açılmasın
    upx=False,              # UPX: antivirüs yanlış pozitifi + imza sorunları
    icon=os.path.join(PAKET, "turkod.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="backend",
)
