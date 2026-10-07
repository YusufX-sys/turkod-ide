"""Backend'in arayüz (Flutter) sürecine bağlı yaşamasını sağlar.

--parent-pid ile verilen süreç (arayüz) HANGİ yolla kapanırsa kapansın (X düğmesi,
çökme, Görev Yöneticisi, uygulama içi güncelleme) backend kendini ve çalıştırdığı
tüm alt süreçleri (kullanıcı programları, terminal) kapatır. Hem paketli exe
(backend_main.py) hem geliştirici kipi (python -m turkod_ide.server) kullanır.
"""
import os
import subprocess
import threading


def kendini_kapat(temizle=None):
    """Kendini ve alt süreçlerini (kullanıcı programları, terminal) sonlandırır."""
    if temizle:
        try:
            temizle()
        except Exception:
            pass
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(os.getpid())],
                       creationflags=0x08000000,  # CREATE_NO_WINDOW
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass
    os._exit(0)


def ebeveyni_izle(pid: int, temizle=None):
    """Ebeveyn (Flutter arayüzü) süreci bitince backend'i kapatır. Yalnızca Windows."""
    if os.name != "nt" or pid <= 0:
        return
    import ctypes

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
            kendini_kapat(temizle)
        return

    def izle():
        while True:
            sonuc = k32.WaitForSingleObject(tutamak, 1000)
            if sonuc == 0:            # WAIT_OBJECT_0: ebeveyn sonlandı
                kendini_kapat(temizle)
            if sonuc != 0x102:        # WAIT_TIMEOUT dışındaki her şey = hata: izlemeyi bırak
                return

    threading.Thread(target=izle, daemon=True, name="ebeveyn-izleyici").start()
