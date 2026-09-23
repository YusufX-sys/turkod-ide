"""TürKod backend - PyInstaller giriş noktası.

Konum: turkod_ide klasörünün ÜST klasörü (spec dosyasının yanı).
Flutter şu komutla başlatır:
    backend\\turkod_backend.exe --backend --parent-pid <Flutter PID> [--port N]

--parent-pid: Flutter penceresi HANGİ yolla kapanırsa kapansın (X düğmesi, çökme,
Görev Yöneticisi, uygulama içi güncelleme) backend kendini ve çalıştırdığı tüm alt
süreçleri (kullanıcı programları, terminal) otomatik kapatır.
"""
import atexit
import multiprocessing
import os
import socket
import sys
import tempfile



def _log_dizini() -> str:
    taban = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    dizin = os.path.join(taban, "TurKod")
    os.makedirs(dizin, exist_ok=True)
    return dizin


def _stdio_logla():
    """console=False derlemede sys.stdout/sys.stderr None olur (uvicorn'un logger'ı
    isatty() çağırıp çöker) ya da okunmayan bir boruya bağlıdır. İkisini de
    %LOCALAPPDATA%\\TurKod\\backend.log dosyasına yönlendir: açılış sorunlarında
    nedeni buradan okuyabilirsin."""
    try:
        yol = os.path.join(_log_dizini(), "backend.log")
        if os.path.exists(yol) and os.path.getsize(yol) > 512 * 1024:
            os.replace(yol, yol + ".old")
        f = open(yol, "a", encoding="utf-8", errors="replace", buffering=1)
    except Exception:
        f = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = f
    sys.stderr = f


if getattr(sys, "frozen", False):
    _stdio_logla()
else:
    for _ad in ("stdout", "stderr"):
        if getattr(sys, _ad) is None:
            setattr(sys, _ad, open(os.devnull, "w", encoding="utf-8"))

# IDE terminali bu sürecin ortamını miras alır: paketli Python'u PATH'in başına koy,
# böylece kullanıcı terminalde `python ...` / `pip install X` yazabilir (pip.cmd
# build_release.ps1 tarafından oluşturulur).
if getattr(sys, "frozen", False):
    _py = os.path.join(os.path.dirname(sys.executable), "_internal", "python_embed")
    if os.path.isdir(_py):
        os.environ["PATH"] = _py + os.pathsep + os.environ.get("PATH", "")

TERCIH_EDILEN_PORT = 8765
PORT_DOSYASI = os.path.join(tempfile.gettempdir(), "turkod_backend_port")


def _port_bos_mu(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _bos_port_bul() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_sec(argv) -> int:
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
            if port > 0:
                return port
        except (ValueError, IndexError):
            pass
    return TERCIH_EDILEN_PORT if _port_bos_mu(TERCIH_EDILEN_PORT) else _bos_port_bul()


def _selftest() -> int:
    """`turkod_backend.exe --selftest`: paketlenmiş backend'in ihtiyaç duyduğu kütüphaneleri
    içe aktarabildiğini doğrular. Sonuç backend.log'a yazılır; çıkış kodu 0 = tamam."""
    import importlib
    gerekli = ("fastapi", "uvicorn", "websockets", "cryptography", "requests", "certifi",
               "openai", "anthropic", "groq", "google.genai", "tkinter")
    eksik = []
    for ad in gerekli:
        try:
            importlib.import_module(ad)
            print(f"[selftest] OK {ad}", flush=True)
        except BaseException as e:  # noqa: BLE001 - paket testi: her hatayı yakala
            eksik.append(ad)
            print(f"[selftest] HATA {ad}: {type(e).__name__}: {e}", flush=True)
    try:
        importlib.import_module("turkod_ide.server")
        print("[selftest] OK turkod_ide.server", flush=True)
    except BaseException as e:  # noqa: BLE001
        eksik.append("turkod_ide.server")
        print(f"[selftest] HATA turkod_ide.server: {type(e).__name__}: {e}", flush=True)
    try:  # Windows'ta saat dilimi veritabanı için tzdata gerekir; yalnızca uyarı
        import zoneinfo
        zoneinfo.ZoneInfo("Europe/Istanbul")
        print("[selftest] OK zoneinfo (tzdata)", flush=True)
    except BaseException as e:  # noqa: BLE001
        print(f"[selftest] UYARI zoneinfo/tzdata: {type(e).__name__}: {e}", flush=True)
    print(f"[selftest] {'BASARISIZ' if eksik else 'BASARILI'}: eksik={eksik}", flush=True)
    return 1 if eksik else 0


def _arg_deger(argv, ad):
    if ad in argv:
        try:
            return argv[argv.index(ad) + 1]
        except IndexError:
            return None
    return None


def _kendini_kapat(temizle=None):
    """Kendini ve alt süreçlerini (kullanıcı programları, terminal) sonlandırır."""
    if temizle:
        try:
            temizle()
        except Exception:
            pass
    try:
        import subprocess
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(os.getpid())],
                       creationflags=0x08000000,  # CREATE_NO_WINDOW
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass
    os._exit(0)


def _ebeveyni_izle(pid: int, temizle=None):
    """Ebeveyn (Flutter arayüzü) süreci bitince backend'i kapatır. Yalnızca Windows."""
    if os.name != "nt" or pid <= 0:
        return
    import ctypes
    import threading

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k32.WaitForSingleObject.restype = ctypes.c_ulong

    SYNCHRONIZE = 0x00100000
    tutamak = k32.OpenProcess(SYNCHRONIZE, 0, pid)
    if not tutamak:
        # 87 = ERROR_INVALID_PARAMETER: böyle bir süreç yok (ebeveyn zaten kapanmış).
        # Başka bir hata (örn. erişim reddedildi) ise izlemeyi bırak, backend'i kapatma.
        if ctypes.get_last_error() == 87:
            _kendini_kapat(temizle)
        return

    def izle():
        while True:
            sonuc = k32.WaitForSingleObject(tutamak, 1000)
            if sonuc == 0:            # WAIT_OBJECT_0: ebeveyn sonlandı
                _kendini_kapat(temizle)
            if sonuc != 0x102:        # WAIT_TIMEOUT dışındaki her şey = hata: izlemeyi bırak
                return

    threading.Thread(target=izle, daemon=True, name="ebeveyn-izleyici").start()


def main():
    import time
    print(f"--- backend başlıyor {time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} "
          f"argv={sys.argv[1:]}", flush=True)

    import uvicorn
    from turkod_ide.server import app

    port = _port_sec(sys.argv[1:])

    with open(PORT_DOSYASI, "w", encoding="utf-8") as f:
        f.write(str(port))

    def _temizle():
        try:
            with open(PORT_DOSYASI, "r", encoding="utf-8") as f:
                if f.read().strip() == str(port):
                    os.remove(PORT_DOSYASI)
        except OSError:
            pass

    atexit.register(_temizle)

    try:
        ebeveyn = int(_arg_deger(sys.argv[1:], "--parent-pid") or 0)
    except ValueError:
        ebeveyn = 0
    _ebeveyni_izle(ebeveyn, _temizle)

    # log_config=None: uvicorn'un renkli/isatty tabanlı logger kurulumunu atlar.
    uvicorn.run(app, host="127.0.0.1", port=port,
                log_config=None, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        raise
