"""Yerel yapay zekâ: llama-cpp-python motoru, donanım/depolama analizi, modeller.

* Motor: llama-cpp-python, IDE'nin Python'una ayrı bir klasöre (pip --target)
  kurulur. NVIDIA ekran kartı ve uygun CUDA sürücüsü varsa CUDA sürümü, yoksa
  CPU sürümü seçilir. CUDA sürümü kurulduktan sonra denenir; çalışmazsa CPU
  sürümüne kendiliğinden geçilir. AMD ve Intel ekran kartları bu motorun hazır
  paketlerinde hızlandırma için kullanılmaz: modeller işlemcide çalışır.
* Sunucu: yerel_sunucu.py, motorun Python'uyla ayrı süreç olarak başlar ve
  OpenAI uyumlu /v1 arayüzü sunar (AI Paneli ve tamamlama bunu kullanır).
* Modeller: Hugging Face'ten doğrudan .gguf dosyası olarak indirilir (devam
  ettirilebilir), model klasöründe saklanır.
* Öneriler: en çok indirilen GGUF modeller; RAM, (yalnızca CUDA'lı) ekran kartı
  belleği ve model klasörünün bulunduğu sürücüdeki kullanılabilir alana göre
  3 hafif + 3 büyük model seçilir. Depolama analizi tüm sabit sürücüleri
  (boş alan, SSD/HDD) inceler ve en uygun sürücüyü önerir.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HF_API = "https://huggingface.co/api/models"
HF_INDIR = "https://huggingface.co/{depo}/resolve/main/{dosya}"
WHL_INDEKS = "https://abetlen.github.io/llama-cpp-python/whl/{paket}"
ONERI_OMRU = 24 * 3600

# (paket klasörü, sürüm). cu121–cu124 yalnızca 0.3.4 sürümüyle yayımlanmış.
MOTOR_PAKETLERI = {
    "cpu": ("cpu", "0.3.36"),
    "cu130": ("cu130", "0.3.36"),
    "cu125": ("cu125", "0.3.36"),
    "cu124": ("cu124", "0.3.4"),
    "cu121": ("cu121", "0.3.4"),
}
# CUDA paketleri cudart / cublas DLL'lerini içermez; CUDA Toolkit kurulu
# değilse 'import llama_cpp' başarısız oluyor, motor sessizce CPU'ya düşüyor ve
# "Ekran kartı sürümünü kur" düğmesi hiç kaybolmuyordu. NVIDIA'nın çalışma
# kitaplığı paketleri motorla aynı klasöre kurulur (nvidia/<ad>/bin).
CUDA_KITAPLIKLARI = {
    "cu121": ["nvidia-cuda-runtime-cu12==12.1.*", "nvidia-cublas-cu12==12.1.*"],
    "cu124": ["nvidia-cuda-runtime-cu12==12.4.*", "nvidia-cublas-cu12==12.4.*"],
    "cu125": ["nvidia-cuda-runtime-cu12==12.5.*", "nvidia-cublas-cu12==12.5.*"],
    # CUDA 13 paketleri sürüm ekisiz yayımlanıyor.
    "cu130": ["nvidia-cuda-runtime==13.0.*", "nvidia-cublas==13.0.*"],
}
# Paket indirme boyutu (yaklaşık, MB; CUDA kitaplıkları dahil) — arayüzde gösterilir.
MOTOR_BOYUTU_MB = {"cpu": 8, "cu130": 230 + 450, "cu125": 510 + 450, "cu124": 400 + 450,
                   "cu121": 400 + 450}

GOREVLER = {
    "tamamlama": "Otomatik tamamlama",
    "sohbet": "AI Paneli sohbet",
    "aciklama": "Kod açıklama / optimize",
    "hata_aciklama": "Hata açıklama",
    "duzeltme": "Akıllı Düzelt (AI aşaması)",
    "kodi": "Kodi (yardımcı robot)",
}

# Q4_K_M nicemlemesinde parametre başına ~0.6 bayt + bağlam/çalışma payı.
_BAYT_PARAMETRE = 0.6
_EK_BELLEK_GB = 0.6
_NICEM_SIRASI = ("Q4_K_M", "Q4_K_S", "Q4_0", "Q5_K_M", "Q6_K", "Q8_0")
_UYGUNSUZ = ("abliterat", "uncensor", "nsfw", "erotic", "roleplay", "rp-",
             "lewd", "heretic", "jailbreak")

# İnternet yoksa kullanılan öneriler (Hugging Face depoları).
YEDEK_ONERILER = {
    "hafif": [
        ("Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
         "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", 1.5, True),
        ("bartowski/Llama-3.2-1B-Instruct-GGUF", "Llama-3.2-1B-Instruct-Q4_K_M.gguf", 1.2, False),
        ("Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
         "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf", 0.5, True),
    ],
    "buyuk": [
        ("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
         "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 7.6, True),
        ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
         "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", 8.0, False),
        ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama-3.2-3B-Instruct-Q4_K_M.gguf", 3.2, False),
    ],
}


def _bayrak():
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def _veri_dizini():
    taban = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    dizin = os.path.join(taban, "TurKod", "yerel_ai")
    try:
        os.makedirs(dizin, exist_ok=True)
    except OSError:
        pass
    return dizin


def varsayilan_model_dizini():
    return os.path.join(_veri_dizini(), "modeller")


_MODEL_DIZINI = None


def model_dizini():
    return _MODEL_DIZINI or varsayilan_model_dizini()


def model_dizini_ayarla(yol):
    """Ayardaki model klasörü (boşsa varsayılan). Değişirse sunucu yeniden
    başlatılır."""
    global _MODEL_DIZINI
    yol = (yol or "").strip() or None
    if yol:
        yol = os.path.abspath(yol)
    if yol != _MODEL_DIZINI:
        _MODEL_DIZINI = yol
        sunucuyu_durdur()
    return model_dizini()


def _model_klasorleri():
    """Taranan klasörler: seçili klasör + (farklıysa) varsayılan klasör."""
    klasorler = [model_dizini()]
    if varsayilan_model_dizini() not in klasorler:
        klasorler.append(varsayilan_model_dizini())
    return klasorler


def motor_dizini(tur):
    return os.path.join(_veri_dizini(), "motor", tur)


def _python():
    try:
        from . import calistirici
    except ImportError:
        import calistirici
    return calistirici.python_exe_bul()


# ----------------------------------------------------------------------
# Donanım
# ----------------------------------------------------------------------
def _ram_gb():
    """(toplam, boş) GB."""
    if os.name == "nt":
        try:
            import ctypes

            class _Durum(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            d = _Durum()
            d.dwLength = ctypes.sizeof(_Durum)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(d)):
                return d.ullTotalPhys / 2**30, d.ullAvailPhys / 2**30
        except Exception:  # noqa: BLE001
            pass
    try:
        sayfa = os.sysconf("SC_PAGE_SIZE")
        return (os.sysconf("SC_PHYS_PAGES") * sayfa / 2**30,
                os.sysconf("SC_AVPHYS_PAGES") * sayfa / 2**30)
    except (ValueError, OSError, AttributeError):
        return 0.0, 0.0


def uretici(ad):
    k = (ad or "").lower()
    if "nvidia" in k or "geforce" in k or "quadro" in k or "rtx" in k or "tesla" in k:
        return "nvidia"
    if "amd" in k or "radeon" in k or "ati " in k or "firepro" in k:
        return "amd"
    if "intel" in k:
        return "intel"
    return "diger"


def _gpu_kayit_defteri():
    """Windows kayıt defterinden ekran kartları ve 64 bit VRAM boyutu
    (WMI'ın AdapterRAM alanı 4 GB'ta takılır)."""
    kartlar = []
    if os.name != "nt":
        return kartlar
    try:
        import winreg
        yol = (r"SYSTEM\CurrentControlSet\Control\Class"
               r"\{4d36e968-e325-11ce-bfc1-08002be10318}")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, yol) as sinif:
            i = 0
            while True:
                try:
                    alt = winreg.EnumKey(sinif, i)
                except OSError:
                    break
                i += 1
                if not alt.isdigit():
                    continue
                try:
                    with winreg.OpenKey(sinif, alt) as k:
                        try:
                            ad = winreg.QueryValueEx(k, "DriverDesc")[0]
                        except OSError:
                            continue
                        vram = 0
                        for deger in ("HardwareInformation.qwMemorySize",
                                      "HardwareInformation.MemorySize"):
                            try:
                                ham = winreg.QueryValueEx(k, deger)[0]
                                if isinstance(ham, bytes):
                                    ham = int.from_bytes(ham[:8], "little")
                                vram = int(ham)
                                if vram:
                                    break
                            except (OSError, ValueError, TypeError):
                                pass
                        if "basic display" in ad.lower() or "remote" in ad.lower():
                            continue
                        kartlar.append({"ad": ad, "vram_gb": round(vram / 2**30, 1),
                                        "uretici": uretici(ad)})
                except OSError:
                    continue
    except Exception:  # noqa: BLE001
        pass
    return kartlar


def _nvidia_bilgisi():
    """(kartlar, CUDA sürümü) — nvidia-smi yoksa ([], None)."""
    yol = shutil.which("nvidia-smi")
    if not yol and os.name == "nt":
        aday = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                            "nvidia-smi.exe")
        yol = aday if os.path.isfile(aday) else None
    if not yol:
        return [], None
    try:
        sorgu = subprocess.run(
            [yol, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, **_bayrak()).stdout
        ozet = subprocess.run([yol], capture_output=True, text=True, timeout=5,
                              **_bayrak()).stdout
    except Exception:  # noqa: BLE001
        return [], None
    kartlar = []
    for satir in sorgu.splitlines():
        parca = [p.strip() for p in satir.split(",")]
        if len(parca) == 2:
            try:
                kartlar.append({"ad": parca[0], "vram_gb": round(float(parca[1]) / 1024, 1),
                                "uretici": "nvidia"})
            except ValueError:
                pass
    m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", ozet)
    return kartlar, ((int(m.group(1)), int(m.group(2))) if m else None)


def cuda_paketi(cuda):
    """Sürücünün desteklediği en yeni CUDA paketi; uygun değilse None."""
    if not cuda:
        return None
    if cuda >= (13, 0):
        return "cu130"
    if cuda >= (12, 5):
        return "cu125"
    if cuda >= (12, 4):
        return "cu124"
    if cuda >= (12, 1):
        return "cu121"
    return None


def hizlandirma_karari(kartlar, cuda):
    """Modeller nerede çalışacak? {tur: 'cuda'|'cpu', paket, vram_gb, aciklama}.
    Yalnızca NVIDIA + CUDA 12.1+ sürücü + en az 3 GB ekran belleği hızlandırılır."""
    nvidia = [k for k in kartlar if k.get("uretici") == "nvidia"]
    paket = cuda_paketi(cuda)
    if nvidia:
        en_iyi = max(nvidia, key=lambda k: k.get("vram_gb", 0))
        if paket and en_iyi.get("vram_gb", 0) >= 3:
            return {"tur": "cuda", "paket": paket, "vram_gb": en_iyi["vram_gb"],
                    "kart": en_iyi["ad"],
                    "aciklama": f"{en_iyi['ad']} (CUDA {cuda[0]}.{cuda[1]}) ile ekran "
                                "kartında hızlandırılır."}
        if not paket:
            neden = ("NVIDIA sürücüsü eski (CUDA 12.1 ya da üstü gerekli); sürücüyü "
                     "güncellerseniz ekran kartı kullanılabilir.")
        else:
            neden = (f"{en_iyi['ad']} ekran belleği ({en_iyi['vram_gb']} GB) "
                     "hızlandırma için yetersiz.")
        return {"tur": "cpu", "paket": "cpu", "vram_gb": 0.0, "kart": None,
                "aciklama": neden + " Modeller işlemcide çalışır."}
    amd = [k for k in kartlar if k.get("uretici") == "amd"]
    if amd:
        return {"tur": "cpu", "paket": "cpu", "vram_gb": 0.0, "kart": None,
                "aciklama": f"{amd[0]['ad']}: AMD ekran kartları bu motorun hazır "
                            "paketlerinde hızlandırma için kullanılmıyor (yalnızca "
                            "NVIDIA CUDA). Modeller işlemcide çalışır."}
    if kartlar:
        return {"tur": "cpu", "paket": "cpu", "vram_gb": 0.0, "kart": None,
                "aciklama": "Tümleşik ekran kartı hızlandırma sağlamaz; modeller "
                            "işlemcide çalışır."}
    return {"tur": "cpu", "paket": "cpu", "vram_gb": 0.0, "kart": None,
            "aciklama": "Uygun ekran kartı bulunamadı; modeller işlemcide çalışır."}


_DONANIM = None
_DONANIM_ZAMANI = 0.0


def donanim_bilgisi(tazele=False):
    global _DONANIM, _DONANIM_ZAMANI
    if _DONANIM is not None and not tazele and time.time() - _DONANIM_ZAMANI < 60:
        return dict(_DONANIM)
    toplam, bos = _ram_gb()
    nvidia, cuda = _nvidia_bilgisi()
    kartlar = _gpu_kayit_defteri()
    # nvidia-smi'nin VRAM değeri daha doğrudur; aynı kart iki kez sayılmasın.
    if nvidia:
        kartlar = [k for k in kartlar if k["uretici"] != "nvidia"] + nvidia
    hiz = hizlandirma_karari(kartlar, cuda)
    _DONANIM = {
        "ram_toplam_gb": round(toplam, 1),
        "ram_bos_gb": round(bos, 1),
        "cekirdek": os.cpu_count() or 1,
        "gpu": kartlar,
        "hizlandirma": hiz,
        # Yalnızca kullanılabilir (CUDA) ekran belleği; AMD/Intel için 0.
        "vram_gb": hiz["vram_gb"],
        "isletim_sistemi": sys.platform,
    }
    _DONANIM_ZAMANI = time.time()
    return dict(_DONANIM)


# ----------------------------------------------------------------------
# Depolama
# ----------------------------------------------------------------------
_DISK_TURU = None


def _disk_turleri():
    """{'C': 'SSD'|'HDD'|...} — Windows Storage modülünden, 10 dk önbellekli."""
    global _DISK_TURU
    if _DISK_TURU is not None:
        return _DISK_TURU
    sonuc = {}
    if os.name == "nt":
        betik = ("Get-Partition | Where-Object DriveLetter | ForEach-Object { "
                 "$n = $_.DiskNumber; $pd = Get-PhysicalDisk | Where-Object DeviceId -eq \"$n\"; "
                 "[pscustomobject]@{H=[string]$_.DriveLetter; T=[string]$pd.MediaType; "
                 "B=[string]$pd.BusType} } | ConvertTo-Json -Compress")
        try:
            cikti = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                    betik], capture_output=True, text=True, timeout=12,
                                   **_bayrak()).stdout.strip()
            veri = json.loads(cikti) if cikti else []
            if isinstance(veri, dict):
                veri = [veri]
            for d in veri:
                tur = (d.get("T") or "").upper()
                if tur not in ("SSD", "HDD"):
                    # NVMe diskler çoğunlukla "Unspecified" görünür.
                    tur = "SSD" if (d.get("B") or "").upper() == "NVME" else "?"
                sonuc[(d.get("H") or "").upper()] = tur
        except Exception:  # noqa: BLE001
            pass
    _DISK_TURU = sonuc
    return sonuc


def _sabit_suruculer():
    if os.name != "nt":
        return [os.path.expanduser("~")]
    try:
        import ctypes
        maske = ctypes.windll.kernel32.GetLogicalDrives()
        suruculer = []
        for i in range(26):
            if maske >> i & 1:
                kok = f"{chr(65 + i)}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(kok) == 3:  # DRIVE_FIXED
                    suruculer.append(kok)
        return suruculer
    except Exception:  # noqa: BLE001
        return [os.path.splitdrive(os.path.expanduser("~"))[0] + "\\"]


def _surucu(yol):
    s = os.path.splitdrive(os.path.abspath(yol))[0]
    return (s.upper() + "\\") if s else os.path.abspath(os.sep)


def _ayrilacak_gb(toplam, sistem):
    """Sürücüde boş bırakılacak pay: sistem sürücüsünde Windows güncellemeleri
    ve sanal bellek için %3 (en az 2, en çok 10 GB), diğerlerinde %2 (1–5 GB)."""
    if sistem:
        return max(2.0, min(10.0, toplam * 0.03))
    return max(1.0, min(5.0, toplam * 0.02))


def kullanilabilir_gb(dizin):
    """Klasörün sürücüsünde, ayrılan pay düşüldükten sonra kalan alan."""
    try:
        u = shutil.disk_usage(_var_olan_ust(dizin))
    except OSError:
        return 0.0
    sistem = _surucu(os.environ.get("SystemRoot", os.path.expanduser("~")))
    ayrilan = _ayrilacak_gb(u.total / 2**30, _surucu(dizin).upper() == sistem.upper())
    return max(0.0, u.free / 2**30 - ayrilan)


def _var_olan_ust(yol):
    yol = os.path.abspath(yol)
    while not os.path.exists(yol):
        ust = os.path.dirname(yol)
        if ust == yol:
            break
        yol = ust
    return yol


def depolama_analizi():
    sistem = _surucu(os.environ.get("SystemRoot", os.path.expanduser("~")))
    turler = _disk_turleri()
    model_surucu = _surucu(model_dizini())
    suruculer = []
    for kok in _sabit_suruculer():
        try:
            u = shutil.disk_usage(kok)
        except OSError:
            continue
        toplam, bos = u.total / 2**30, u.free / 2**30
        sistem_mi = kok.upper() == sistem.upper()
        ayrilan = _ayrilacak_gb(toplam, sistem_mi)
        suruculer.append({
            "kok": kok, "harf": kok[:1].upper(), "toplam_gb": round(toplam, 1),
            "bos_gb": round(bos, 1), "tur": turler.get(kok[:1].upper(), "?"),
            "sistem": sistem_mi, "ayrilan_gb": round(ayrilan, 1),
            "kullanilabilir_gb": round(max(0.0, bos - ayrilan), 1),
            "model_surucusu": kok.upper() == model_surucu.upper(),
        })
    modeller_gb = sum(m["boyut_gb"] for m in yuklu_modeller())
    secili = next((s for s in suruculer if s["model_surucusu"]), None)
    # En uygun sürücü: önce SSD, sonra en çok kullanılabilir alan.
    aday = sorted(suruculer, key=lambda s: (s["kullanilabilir_gb"] < 5, s["tur"] == "HDD",
                                            -s["kullanilabilir_gb"]))
    en_iyi = aday[0] if aday else None
    notlar = []
    if secili and secili["kullanilabilir_gb"] < 5:
        notlar.append(f"{secili['harf']}: sürücüsünde model için çok az yer var "
                      f"({secili['kullanilabilir_gb']} GB kullanılabilir).")
    if en_iyi and secili and en_iyi["kok"] != secili["kok"] and \
            en_iyi["kullanilabilir_gb"] > secili["kullanilabilir_gb"] + 5:
        notlar.append(f"{en_iyi['harf']}: sürücüsünde daha çok yer var "
                      f"({en_iyi['kullanilabilir_gb']} GB); model klasörünü oraya taşıyabilirsiniz.")
    if secili and secili["tur"] == "HDD":
        notlar.append("Model klasörü sabit diskte (HDD): modeller yavaş yüklenir, SSD önerilir.")
    return {
        "suruculer": suruculer,
        "model_dizini": model_dizini(),
        "varsayilan_model_dizini": varsayilan_model_dizini(),
        "modeller_gb": round(modeller_gb, 2),
        # Model klasörü çıkarılabilir / ağ sürücüsündeyse sabit sürücü
        # listesinde yoktur; eskiden 0 GB sayılıp her model için "Diskte yer
        # yok" deniyordu. Boş alan klasörün kendi yolundan hesaplanır.
        "kullanilabilir_gb": (secili["kullanilabilir_gb"] if secili
                              else round(kullanilabilir_gb(model_dizini()), 1)),
        "onerilen_dizin": (os.path.join(en_iyi["kok"], "TurKod", "modeller")
                           if en_iyi and secili and en_iyi["kok"] != secili["kok"] else None),
        "notlar": notlar,
    }


def model_boyutu_gb(parametre_b):
    return round(parametre_b * _BAYT_PARAMETRE, 1)


def sigar_mi(parametre_b, donanim=None, depolama=None, boyut_gb=None):
    """(çalışır_mı, hızlı_mı, gerekçe). Bellek: CUDA ekran kartı ya da RAM'in
    %70'i; disk: model klasörünün sürücüsündeki kullanılabilir alan."""
    d = donanim or donanim_bilgisi()
    dep = depolama or depolama_analizi()
    boyut = boyut_gb or model_boyutu_gb(parametre_b)
    gerekli = boyut + _EK_BELLEK_GB
    kullanilabilir = dep.get("kullanilabilir_gb", 0.0)
    if boyut * 1.05 > kullanilabilir:
        baska = [s for s in dep.get("suruculer", [])
                 if not s["model_surucusu"] and s["kullanilabilir_gb"] >= boyut * 1.05]
        if baska:
            return False, False, (f"Model klasöründe yer yok ({boyut} GB gerekli); "
                                  f"{baska[0]['harf']}: sürücüsüne indirilebilir")
        return False, False, f"Diskte yer yok ({boyut} GB gerekli, {kullanilabilir} GB kullanılabilir)"
    if d.get("vram_gb", 0) >= gerekli:
        return True, True, "Ekran kartında (CUDA) hızlı çalışır"
    if d.get("ram_toplam_gb", 0) * 0.7 < gerekli:
        return False, False, f"Bellek yetersiz (~{gerekli:.1f} GB RAM gerekli)"
    if d.get("vram_gb", 0) >= 2:
        return True, False, "Kısmen ekran kartında, kısmen işlemcide çalışır"
    if parametre_b > 9:
        return True, False, "İşlemcide çalışır (yavaş olabilir)"
    return True, False, "İşlemcide çalışır"


# ----------------------------------------------------------------------
# Motor (llama-cpp-python) kurulumu
# ----------------------------------------------------------------------
_KURULUM = {"durum": "bos", "tur": None, "gunluk": [], "hata": "", "asama": "",
            "sonuc_tur": None, "cpuya_dustu": False, "son_hata": ""}
_KURULUM_KILIDI = threading.Lock()


def _motor_surumu(tur):
    dizin = motor_dizini(tur)
    if not os.path.isfile(os.path.join(dizin, "llama_cpp", "__init__.py")):
        return None
    try:
        for ad in os.listdir(dizin):
            m = re.match(r"llama_cpp_python-([\d.]+)\.dist-info$", ad)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "?"


def _dogrulama_dosyasi(tur):
    return os.path.join(motor_dizini(tur), ".turkod_dogrulandi.json")


def _dogrulandi_mi(tur):
    try:
        with open(_dogrulama_dosyasi(tur), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def etkin_motor():
    """Kullanılacak motor: doğrulanmış CUDA, yoksa doğrulanmış CPU, yoksa None."""
    for tur in ("cuda", "cpu"):
        if _motor_surumu(tur) and _dogrulandi_mi(tur):
            return tur
    return None


def motor_durumu():
    d = donanim_bilgisi()
    hiz = d["hizlandirma"]
    with _KURULUM_KILIDI:
        kurulum = {k: (list(v) if isinstance(v, list) else v) for k, v in _KURULUM.items()}
    kurulu = {}
    for tur in ("cpu", "cuda"):
        surum = _motor_surumu(tur)
        dog = _dogrulandi_mi(tur)
        if surum:
            kurulu[tur] = {"surum": surum, "dogrulandi": bool(dog),
                           "gpu": bool(dog and dog.get("gpu"))}
    onerilen = "cuda" if hiz["tur"] == "cuda" else "cpu"
    paket = hiz["paket"] if onerilen == "cuda" else "cpu"
    return {
        "ok": True,
        "kurulu": kurulu,
        "etkin": etkin_motor(),
        "onerilen": onerilen,
        "paket": paket,
        "indirme_mb": MOTOR_BOYUTU_MB.get(paket, 0),
        "hizlandirma": hiz,
        "kurulum": kurulum,
        # Ekran kartı sürümü bu bilgisayarda çalışmadıysa nedeni (arayüz büyük
        # düğme yerine kısa bir not + "Yeniden dene" gösterir).
        "cuda_hata": _cuda_hatasi() if etkin_motor() != "cuda" else None,
        "sunucu": sunucu_durumu(),
    }


def _gunluk(metin):
    with _KURULUM_KILIDI:
        _KURULUM["gunluk"].append(metin)
        del _KURULUM["gunluk"][:-60]


def _pip_komutu(py, hedef, paket):
    _, surum = MOTOR_PAKETLERI[paket]
    return [py, "-m", "pip", "install", "--target", hedef, "--upgrade",
            "--only-binary=:all:", "--no-warn-script-location",
            "--disable-pip-version-check", "--progress-bar", "off",
            "--extra-index-url", WHL_INDEKS.format(paket=paket),
            f"llama-cpp-python=={surum}", *CUDA_KITAPLIKLARI.get(paket, [])]


def _pip_kur(tur, paket):
    """llama-cpp-python'u motor/<tur> klasörüne kurar. Başarıda True."""
    py = _python()
    if not py:
        _gunluk("Python bulunamadı.")
        return False
    _, surum = MOTOR_PAKETLERI[paket]
    hedef = motor_dizini(tur)
    gecici = hedef + ".kuruluyor"
    shutil.rmtree(gecici, ignore_errors=True)
    os.makedirs(gecici, exist_ok=True)
    komut = _pip_komutu(py, gecici, paket)
    _gunluk(f"pip ile llama-cpp-python {surum} ({paket}) kuruluyor…"
            + (" (CUDA çalışma kitaplıklarıyla birlikte)" if paket in CUDA_KITAPLIKLARI else ""))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PIP_NO_INPUT="1")
    env.pop("PYTHONPATH", None)
    try:
        p = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env=env,
                             **_bayrak())
        for satir in p.stdout:
            satir = satir.rstrip()
            if satir:
                _gunluk(satir)
                with _KURULUM_KILIDI:
                    if satir.startswith(("Collecting", "Downloading", "Installing")):
                        _KURULUM["asama"] = satir[:120]
        p.wait()
    except OSError as e:
        _gunluk(f"pip başlatılamadı: {e}")
        return False
    if p.returncode != 0:
        _gunluk(f"pip hata koduyla bitti ({p.returncode}).")
        _motor_hatasi(f"paket indirilemedi (pip hata kodu {p.returncode})")
        shutil.rmtree(gecici, ignore_errors=True)
        return False
    shutil.rmtree(hedef, ignore_errors=True)
    os.replace(gecici, hedef)
    return True


# Sunucuyla aynı yoldan (yerel_sunucu.dll_dizinlerini_ekle) CUDA DLL'leri
# eklenip motor denenir. argv: [motor klasörü, yerel_sunucu.py'nin klasörü].
_DOGRULAMA_KODU = (
    "import sys, json; sys.path.append(sys.argv[2]); "
    "import yerel_sunucu; yerel_sunucu.dll_dizinlerini_ekle(sys.argv[1]); "
    "sys.path.insert(0, sys.argv[1]); import llama_cpp; "
    "print(json.dumps({'surum': llama_cpp.__version__, "
    "'gpu': bool(llama_cpp.llama_supports_gpu_offload())}))")


def _motor_hatasi(metin):
    """Son motor hatasını kısa, anlaşılır biçimde saklar (CUDA kaydı için)."""
    metin = str(metin or "").strip()
    k = metin.lower()
    if "could not find module" in k or "dependencies" in k or "dll load failed" in k \
            or "cudart" in k or "cublas" in k:
        metin = "CUDA kitaplıkları (DLL) yüklenemedi"
    elif "gpu" in k and "kullanam" in k:
        metin = "motor ekran kartını kullanamıyor (sürücü eski olabilir)"
    with _KURULUM_KILIDI:
        _KURULUM["son_hata"] = metin[:200]


def _cuda_hata_dosyasi():
    return os.path.join(os.path.dirname(motor_dizini("cuda")), "cuda_hatasi.json")


def _cuda_hatasi():
    """Kaydedilmiş CUDA başarısızlığı: {"neden", "tarih"} ya da None."""
    try:
        with open(_cuda_hata_dosyasi(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("neden") else None
    except (OSError, ValueError):
        return None


def motoru_dogrula(tur):
    """Kurulu motoru ayrı süreçte yükleyip dener; sonuç dosyaya yazılır."""
    py = _python()
    try:
        r = subprocess.run([py, "-c", _DOGRULAMA_KODU, motor_dizini(tur),
                            os.path.dirname(_sunucu_betigi())],
                           capture_output=True, text=True, timeout=120, **_bayrak())
        satir = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
        sonuc = json.loads(satir) if satir.startswith("{") else None
    except Exception as e:  # noqa: BLE001
        _gunluk(f"Motor denenemedi: {e}")
        _motor_hatasi(f"motor denenemedi: {e}")
        return None
    if not sonuc:
        _gunluk("Motor yüklenemedi: " + (r.stderr or "")[-400:])
        satirlar = [s for s in (r.stderr or "").splitlines() if s.strip()]
        _motor_hatasi(satirlar[-1] if satirlar else "motor yüklenemedi")
        return None
    if tur == "cuda" and not sonuc.get("gpu"):
        _gunluk("CUDA motoru ekran kartını kullanamıyor.")
        _motor_hatasi("motor ekran kartını kullanamıyor (sürücü eski olabilir)")
        return None
    with open(_dogrulama_dosyasi(tur), "w", encoding="utf-8") as f:
        json.dump(sonuc, f)
    return sonuc


def motor_kur(tur=None):
    """Motoru arka planda kurar. tur None: donanıma göre (CUDA ya da CPU).
    CUDA kurulamaz ya da çalışmazsa CPU sürümü kurulur."""
    hiz = donanim_bilgisi(tazele=True)["hizlandirma"]
    tur = tur or ("cuda" if hiz["tur"] == "cuda" else "cpu")
    if tur == "cuda" and hiz["tur"] != "cuda":
        return {"ok": False, "hata": hiz["aciklama"]}
    with _KURULUM_KILIDI:
        if _KURULUM["durum"] == "kuruluyor":
            return {"ok": True, "zaten": True}
        _KURULUM.update({"durum": "kuruluyor", "tur": tur, "gunluk": [], "hata": "",
                         "asama": "başlıyor", "sonuc_tur": None, "cpuya_dustu": False,
                         "son_hata": ""})

    def calis():
        # Eskiden burada beklenmeyen bir hata (kilitli llama.dll yüzünden
        # os.replace / doğrulama dosyası yazılamaması) iş parçacığını
        # öldürüyor, durum sonsuza dek "kuruluyor" kalıyor ve sonraki her
        # deneme "zaten kuruluyor" diye geri dönüyordu.
        tamam, hata_metni, sonuc_tur, cpuya_dustu = False, "", None, False
        try:
            sunucuyu_durdur()
            if tur == "cuda":
                try:
                    if _pip_kur("cuda", hiz["paket"]) and motoru_dogrula("cuda"):
                        tamam, sonuc_tur = True, "cuda"
                except Exception as e:  # noqa: BLE001
                    _gunluk(f"CUDA kurulumunda hata: {e}")
                    _motor_hatasi(str(e))
                if tamam:
                    try:
                        os.remove(_cuda_hata_dosyasi())
                    except OSError:
                        pass
                else:
                    _gunluk("Ekran kartı (CUDA) sürümü çalışmadı; işlemci (CPU) sürümüne geçiliyor.")
                    shutil.rmtree(motor_dizini("cuda"), ignore_errors=True)
                    # Başarısızlık kaydedilir: arayüz büyük "kur" düğmesini
                    # yeniden göstermez, nedenini ve "Yeniden dene"yi gösterir.
                    with _KURULUM_KILIDI:
                        neden = _KURULUM.get("son_hata") or "motor yüklenemedi"
                    try:
                        os.makedirs(os.path.dirname(_cuda_hata_dosyasi()), exist_ok=True)
                        with open(_cuda_hata_dosyasi(), "w", encoding="utf-8") as f:
                            json.dump({"neden": neden, "paket": hiz.get("paket"),
                                       "tarih": time.strftime("%Y-%m-%d %H:%M")}, f,
                                      ensure_ascii=False)
                    except OSError:
                        pass
                    cpuya_dustu = True
            if not tamam:
                tamam = bool(_pip_kur("cpu", "cpu") and motoru_dogrula("cpu"))
                sonuc_tur = "cpu" if tamam else None
        except Exception as e:  # noqa: BLE001
            _gunluk(f"Kurulum hatası: {e}")
            hata_metni = ("Motor kurulamadı: motor dosyaları kullanımda olabilir. TürKod'u "
                          "yeniden başlatıp tekrar deneyin; ayrıntı günlükte.")
        finally:
            with _KURULUM_KILIDI:
                _KURULUM["durum"] = "tamam" if tamam else "hata"
                _KURULUM["asama"] = ""
                _KURULUM["sonuc_tur"] = sonuc_tur
                _KURULUM["cpuya_dustu"] = cpuya_dustu
                if not tamam:
                    _KURULUM["hata"] = hata_metni or (
                        "Motor kurulamadı. İnternet bağlantısını kontrol edip "
                        "yeniden deneyin; ayrıntı günlükte.")

    threading.Thread(target=calis, daemon=True, name="yerel-ai-motor").start()
    return {"ok": True}


def motor_kaldir():
    sunucuyu_durdur()
    for tur in ("cpu", "cuda"):
        shutil.rmtree(motor_dizini(tur), ignore_errors=True)
    return {"ok": True}


# ----------------------------------------------------------------------
# Sunucu
# ----------------------------------------------------------------------
_SUNUCU = {"surec": None, "port": None, "tur": None, "hata": "", "hazir": False,
           "gunluk": None}
_SUNUCU_KILIDI = threading.Lock()


def _sunucu_betigi():
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)),
                            "yerel_sunucu.py")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "yerel_sunucu.py")


def _bos_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _saglikli(port):
    import requests
    try:
        return requests.get(f"http://127.0.0.1:{port}/saglik", timeout=1.5).ok
    except Exception:  # noqa: BLE001
        return False


def sunucu_durumu():
    with _SUNUCU_KILIDI:
        p = _SUNUCU["surec"]
        calisiyor = p is not None and p.poll() is None
        return {"calisiyor": calisiyor, "port": _SUNUCU["port"] if calisiyor else None,
                "tur": _SUNUCU["tur"] if calisiyor else None, "hata": _SUNUCU["hata"]}


class YerelAIHatasi(Exception):
    """Kullanıcıya gösterilebilir Türkçe hata."""


def baglam_siniri(ram_gb):
    """Sunucunun modelleri açacağı bağlamın üst sınırı (RAM'e göre). Model
    daha kısa bağlamla eğitildiyse onunki kullanılır (yerel_sunucu)."""
    if (ram_gb or 0) >= 16:
        return 16384
    if (ram_gb or 0) >= 8:
        return 12288
    return 8192


def sunucu_url():
    """Çalışan sunucunun /v1 adresi; gerekirse başlatır."""
    # Eskiden ikinci bir çağıran, sunucu daha açılırken (süreç var ama model
    # sunucusu hazır değil) adresi hemen alıyor ve "Yerel AI sunucusuna
    # ulaşılamadı" hatası görüyordu. Artık herkes sunucunun hazır olmasını bekler.
    baslatan = False
    with _SUNUCU_KILIDI:
        p = _SUNUCU["surec"]
        if p is not None and p.poll() is None:
            port, gunluk = _SUNUCU["port"], _SUNUCU.get("gunluk")
            if _SUNUCU.get("hazir"):
                return f"http://127.0.0.1:{port}/v1"
        else:
            baslatan = True
    if baslatan:
        p, port, gunluk = _sunucu_baslat()
    for _ in range(120):
        if p.poll() is not None:
            break
        if _saglikli(port):
            with _SUNUCU_KILIDI:
                if _SUNUCU["surec"] is p:
                    _SUNUCU["hazir"] = True
            return f"http://127.0.0.1:{port}/v1"
        time.sleep(0.25)
    try:
        with open(gunluk or os.devnull, encoding="utf-8", errors="replace") as f:
            ayrinti = f.read()[-400:]
    except OSError:
        ayrinti = ""
    if baslatan:
        sunucuyu_durdur()
        _SUNUCU["hata"] = ayrinti
    raise YerelAIHatasi("Yerel AI sunucusu başlamadı. Motoru yeniden kurmayı deneyin."
                        + (f"\n{ayrinti}" if ayrinti else ""))


def _sunucu_baslat():
    """Sunucu sürecini başlatır (hazır olmasını beklemez): (süreç, port, günlük)."""
    with _SUNUCU_KILIDI:
        p = _SUNUCU["surec"]
        if p is not None and p.poll() is None:  # bu arada başkası başlattı
            return p, _SUNUCU["port"], _SUNUCU.get("gunluk")
        tur = etkin_motor()
        if not tur:
            raise YerelAIHatasi("Yerel AI motoru kurulu değil. Eklenti Özellikleri → "
                                "Yerel AI Modelleri → 'Motoru kur' ile kurun.")
        d = donanim_bilgisi()
        port = _bos_port()
        os.makedirs(model_dizini(), exist_ok=True)
        komut = [_python(), "-X", "utf8", _sunucu_betigi(), "--paket", motor_dizini(tur),
                 "--modeller", os.pathsep.join(_model_klasorleri()), "--port", str(port),
                 "--ebeveyn", str(os.getpid()),
                 # Düşük RAM'de aynı anda tek model bellekte tutulur.
                 "--azami-model", "2" if d["ram_toplam_gb"] >= 12 else "1",
                 # Eskiden verilmiyordu: her model 4096 bağlamla açılıyordu.
                 "--baglam", str(baglam_siniri(d["ram_toplam_gb"]))]
        if tur == "cuda":
            komut += ["--gpu", "--vram", str(d["vram_gb"])]
        gunluk = os.path.join(_veri_dizini(), "sunucu.log")
        try:
            cikis = open(gunluk, "w", encoding="utf-8", errors="replace")
        except OSError:
            cikis = open(os.devnull, "w", encoding="utf-8")
        try:
            p = subprocess.Popen(komut, stdout=cikis, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                 **_bayrak())
        except OSError as e:
            raise YerelAIHatasi(f"Yerel AI sunucusu başlatılamadı: {e}") from None
        finally:
            cikis.close()  # alt süreç kendi kopyasını kullanır
        _SUNUCU.update({"surec": p, "port": port, "tur": tur, "hata": "",
                        "hazir": False, "gunluk": gunluk})
    return p, port, gunluk


def sunucuyu_durdur():
    with _SUNUCU_KILIDI:
        p = _SUNUCU["surec"]
        _SUNUCU.update({"surec": None, "port": None, "tur": None, "hazir": False})
    if p is not None and p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass
    return {"ok": True}


# ----------------------------------------------------------------------
# Yüklü modeller
# ----------------------------------------------------------------------
_NICEM_DESENI = re.compile(r"(?i)(IQ\d_[A-Z]+|Q\d_K_[SML]|Q\d_K|Q\d_\d|F16|BF16|F32)")


def yuklu_modeller():
    sonuc, gorulen = [], set()
    for dizin in _model_klasorleri():
        try:
            adlar = sorted(os.listdir(dizin))
        except OSError:
            continue
        for ad in adlar:
            if not ad.lower().endswith(".gguf") or ad in gorulen:
                continue
            gorulen.add(ad)
            yol = os.path.join(dizin, ad)
            meta = {}
            try:
                with open(yol + ".json", encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                pass
            # Eğitim bağlamı GGUF başlığından bir kez okunup bilgi dosyasına yazılır.
            if "baglam" not in meta:
                meta["baglam"] = _gguf_baglam(yol) or 0
                try:
                    with open(yol + ".json", "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False)
                except OSError:
                    pass
            m = _NICEM_DESENI.search(ad)
            parametre = meta.get("parametre_b")
            sonuc.append({
                "ad": ad,
                "baslik": meta.get("baslik") or ad[:-5],
                "boyut_gb": round(os.path.getsize(yol) / 2**30, 2),
                "parametre": f"{parametre}B" if parametre else "",
                "nicem": m.group(1).upper() if m else "",
                "depo": meta.get("depo", ""),
                "yol": yol,
                "baglam": int(meta.get("baglam") or 0),
                "kodi_uygun": kodi_uygun_mu(meta.get("baglam")),
            })
    return sonuc


# Kodi isteği ~5-6K jeton + 2K cevap: en az 8K bağlam gerekir.
KODI_EN_AZ_BAGLAM = 8192


def kodi_uygun_mu(baglam):
    """True / False; bağlam bilinmiyorsa None."""
    try:
        baglam = int(baglam or 0)
    except (TypeError, ValueError):
        return None
    return None if baglam <= 0 else baglam >= KODI_EN_AZ_BAGLAM


def _gguf_baglam(yol):
    try:
        from .yerel_sunucu import gguf_baglam
    except ImportError:
        from yerel_sunucu import gguf_baglam
    return gguf_baglam(yol)


def model_sil(ad):
    taban = os.path.basename(ad or "")
    for dizin in _model_klasorleri():
        yol = os.path.join(dizin, taban)
        if taban.lower().endswith(".gguf") and os.path.isfile(yol):
            sunucuyu_durdur()  # dosya açıkken silinemez
            try:
                os.remove(yol)
            except OSError as e:
                return {"ok": False, "hata": f"Silinemedi: {e}"}
            try:
                os.remove(yol + ".json")
            except OSError:
                pass
            return {"ok": True}
    return {"ok": False, "hata": "Model bulunamadı."}


# ----------------------------------------------------------------------
# Model indirme (Hugging Face)
# ----------------------------------------------------------------------
_INDIRMELER = {}
_INDIRME_KILIT = threading.Lock()
_KIMLIK_DESENI = re.compile(r"^[A-Za-z0-9._\-]+/[A-Za-z0-9._\-]+/[A-Za-z0-9._\-]+\.gguf$")


def _dosya_bilgisi(depo, dosya):
    """(boyut_bayt) — Hugging Face ağaç API'sinden."""
    import requests
    r = requests.get(f"{HF_API}/{depo}/tree/main", timeout=20,
                     headers={"User-Agent": "TurKod-IDE"})
    r.raise_for_status()
    for o in r.json():
        if o.get("path") == dosya:
            return int(o.get("size") or 0)
    raise FileNotFoundError(dosya)


def model_indir(kimlik, baslik="", parametre_b=None):
    """kimlik: "<kullanıcı>/<depo>/<dosya>.gguf". İndirme arka planda yapılır;
    ilerleme indirme_durumu() ile okunur."""
    kimlik = (kimlik or "").strip()
    if not _KIMLIK_DESENI.match(kimlik) or ".." in kimlik:
        return {"ok": False, "hata": "Geçersiz model kimliği."}
    depo, dosya = kimlik.rsplit("/", 1)
    # Modeller dosya adıyla saklanır. Eskiden başka bir depodaki aynı adlı
    # dosya, var olan modelin ve bilgi dosyasının üzerine yazılıyor; aynı
    # anda indirilirse ikisi tek .part dosyasını paylaşıp birbirini bozuyordu.
    baska = _ayni_adli_baska_depo(depo, dosya)
    if baska:
        return {"ok": False, "hata": (
            f"'{dosya}' adlı model zaten '{baska}' deposundan indirilmiş. Aynı adlı iki "
            "model birlikte tutulamaz; bunu indirmek için önce ötekini silin.")}
    with _INDIRME_KILIT:
        mevcut = _INDIRMELER.get(kimlik)
        if mevcut and mevcut["durum"] == "indiriliyor":
            return {"ok": True, "zaten": True}
        for k, v in _INDIRMELER.items():
            if k != kimlik and k.rsplit("/", 1)[1] == dosya and v.get("durum") == "indiriliyor":
                return {"ok": False, "hata": (
                    f"Aynı adlı '{dosya}' dosyası şu anda başka bir depodan "
                    f"({k.rsplit('/', 1)[0]}) indiriliyor; o bitince yeniden deneyin.")}
        _INDIRMELER[kimlik] = {"durum": "indiriliyor", "yuzde": 0.0, "tamamlanan": 0,
                               "toplam": 0, "hata": "", "iptal": False,
                               "asama": "hazırlanıyor"}
    threading.Thread(target=_indir, args=(kimlik, baslik, parametre_b), daemon=True,
                     name="model-indir").start()
    return {"ok": True}


def _ayni_adli_baska_depo(depo, dosya):
    """Model klasörlerinde aynı adlı ama başka depodan indirilmiş model varsa
    o deponun adı; yoksa ''. Bilgi dosyası olmayan (elle eklenmiş) modeller
    için de '' döner (eski davranış: üzerine yazılmaz, dosya adı aynıdır)."""
    for dizin in _model_klasorleri():
        yol = os.path.join(dizin, dosya)
        if not os.path.isfile(yol):
            continue
        try:
            with open(yol + ".json", encoding="utf-8") as f:
                eski = str(json.load(f).get("depo") or "")
        except (OSError, ValueError, AttributeError):
            continue
        if eski and eski != depo:
            return eski
    return ""


class _IndirmeIptal(Exception):
    pass


def _yarim_dosyayi_sil(yol):
    for _ in range(10):
        try:
            if os.path.exists(yol):
                os.remove(yol)
            return
        except PermissionError:  # antivirüs kısa süre tutabilir
            time.sleep(0.2)
        except OSError:
            return


class _IndirmeTakildi(Exception):
    pass


# 64 KB'lık parçalar: iptal ve ilerleme yavaş bağlantıda da hemen işlenir.
_PARCA = 1 << 16
# Bir parça bu kadar sürerse bağlantı takılmış sayılır ve yeniden kurulur.
_TAKILMA_SN = 45


def _parcalari_indir(url, gecici, toplam, kayit):
    """Dosyayı .part'ın sonundan devam ettirir. Bittiyse True; bağlantı erken
    kapandıysa False; takılırsa _IndirmeTakildi."""
    import requests
    var = os.path.getsize(gecici) if os.path.exists(gecici) else 0
    # Eskiden .part sunucudaki dosyadan büyükse (dosya değişmiş) "bitti"
    # sayılıyor, boyut denetimi tutmayınca her denemede "yarıda kaldı"
    # deniyordu; .part hiç silinmediği için indirme asla düzelmiyordu.
    if toplam and var > toplam:
        _yarim_dosyayi_sil(gecici)
        var = 0
    if toplam and var == toplam:
        return True
    basliklar = {"User-Agent": "TurKod-IDE"}
    if var:
        basliklar["Range"] = f"bytes={var}-"
    with requests.get(url, headers=basliklar, stream=True, timeout=(15, 30)) as r:
        if r.status_code == 200:
            var = 0  # sunucu baştan gönderiyor
        elif r.status_code == 416 and var:
            if toplam and var != toplam:
                _yarim_dosyayi_sil(gecici)  # uyuşmayan yarım dosya: baştan
                return False
            return True  # dosya zaten tamam
        elif r.status_code != 206:
            raise RuntimeError(f"HTTP {r.status_code}")
        with open(gecici, "ab" if var else "wb") as f:
            tamam = var
            son = time.monotonic()
            for parca in r.iter_content(chunk_size=_PARCA):
                if kayit["iptal"]:
                    raise _IndirmeIptal()
                f.write(parca)
                tamam += len(parca)
                kayit["tamamlanan"] = tamam
                if toplam:
                    kayit["yuzde"] = round(100.0 * tamam / toplam, 1)
                simdi = time.monotonic()
                if simdi - son > _TAKILMA_SN:
                    raise _IndirmeTakildi()
                son = simdi
    return not toplam or os.path.getsize(gecici) >= toplam


def _indir(kimlik, baslik, parametre_b):
    import requests
    kayit = _INDIRMELER[kimlik]
    depo, dosya = kimlik.rsplit("/", 1)
    dizin = model_dizini()
    hedef = os.path.join(dizin, dosya)
    gecici = hedef + ".part"
    part_bilgisi = gecici + ".json"
    try:
        os.makedirs(dizin, exist_ok=True)
        toplam = _dosya_bilgisi(depo, dosya)
        kayit["toplam"] = toplam
        # Yarım dosyanın hangi depodan geldiği yanına yazılır; başka bir
        # deponun aynı adlı yarım dosyası devam ettirilmez, baştan indirilir.
        # (Bilgisi olmayan eski .part dosyaları eskisi gibi sürdürülür.)
        try:
            with open(part_bilgisi, encoding="utf-8") as f:
                part_depo = str(json.load(f).get("depo") or "")
        except (OSError, ValueError, AttributeError):
            part_depo = ""
        if part_depo and part_depo != depo:
            _yarim_dosyayi_sil(gecici)
        with open(part_bilgisi, "w", encoding="utf-8") as f:
            json.dump({"depo": depo}, f)
        var = os.path.getsize(gecici) if os.path.exists(gecici) else 0
        kalan = kullanilabilir_gb(dizin)
        if (toplam - var) / 2**30 > kalan:
            raise RuntimeError(f"Diskte yer yok: {toplam / 2**30:.1f} GB gerekli, "
                               f"{kalan:.1f} GB kullanılabilir (sürücüde sistem için pay "
                               "bırakılır). Model klasörünü başka bir sürücüye taşıyın.")
        if kayit["iptal"]:
            raise _IndirmeIptal()
        # Bağlantı koparsa ya da neredeyse durursa kaldığı yerden yeniden
        # bağlanılır (eskiden yavaş bağlantıda indirme dakikalarca takılı kalıyordu).
        hata_sayisi = 0
        while True:
            kayit["asama"] = "indiriliyor"
            try:
                if _parcalari_indir(HF_INDIR.format(depo=depo, dosya=dosya), gecici,
                                    toplam, kayit):
                    break
                hata_sayisi = 0  # ilerleme oldu; bağlantı erken kapandı
            except (_IndirmeTakildi, requests.RequestException):
                hata_sayisi += 1
                if hata_sayisi > 8:
                    raise RuntimeError("Bağlantı sürekli kesiliyor; internetinizi denetleyip "
                                       "yeniden deneyin (kaldığı yerden sürer).") from None
            kayit["asama"] = "yeniden bağlanıyor"
            for _ in range(min(2 * hata_sayisi, 10) * 5):
                if kayit["iptal"]:
                    raise _IndirmeIptal()
                time.sleep(0.2)
        if toplam and os.path.getsize(gecici) > toplam:
            _yarim_dosyayi_sil(gecici)
            raise RuntimeError("İndirilen dosya beklenenden büyük çıktı (model sunucuda "
                               "değişmiş olabilir); yarım dosya silindi, yeniden deneyin.")
        if toplam and os.path.getsize(gecici) != toplam:
            raise RuntimeError("İndirme yarıda kaldı; yeniden deneyin (kaldığı yerden sürer).")
        baska = _ayni_adli_baska_depo(depo, dosya)
        if baska:
            raise RuntimeError(f"'{dosya}' adlı model bu arada '{baska}' deposundan "
                               "indirilmiş; üzerine yazılmadı.")
        os.replace(gecici, hedef)
        _yarim_dosyayi_sil(part_bilgisi)
        with open(hedef + ".json", "w", encoding="utf-8") as f:
            json.dump({"depo": depo, "baslik": baslik or dosya[:-5],
                       "parametre_b": parametre_b, "indirildi": time.time()}, f,
                      ensure_ascii=False)
        kayit["durum"] = "tamam"
        kayit["yuzde"] = 100.0
    except _IndirmeIptal:
        # İptal edilen indirmenin yarım dosyası silinir (eskiden diskte
        # kalıyor, elle silinmesi gerekiyordu).
        kayit["durum"] = "iptal"
        _yarim_dosyayi_sil(gecici)
        _yarim_dosyayi_sil(part_bilgisi)
    except FileNotFoundError:
        kayit["durum"] = "hata"
        kayit["hata"] = "Model dosyası Hugging Face'te bulunamadı."
    except Exception as e:  # noqa: BLE001
        kayit["durum"] = "hata"
        kayit["hata"] = _indirme_hatasi(str(e))


def _indirme_hatasi(metin):
    k = metin.lower()
    if "404" in k:
        return "Model dosyası bulunamadı."
    if "no space" in k or "yer yok" in k:
        return metin if "yer yok" in k else "Diskte yer kalmadı."
    if "connection" in k or "timeout" in k or "timed out" in k:
        return "Bağlantı hatası; internetinizi kontrol edin (yeniden denerseniz kaldığı yerden sürer)."
    return metin[:300]


def indirme_iptal(kimlik):
    with _INDIRME_KILIT:
        k = _INDIRMELER.get(kimlik)
        if k and k["durum"] == "indiriliyor":
            k["iptal"] = True
            return {"ok": True}
    return {"ok": False, "hata": "Süren indirme yok."}


def indirme_durumu():
    with _INDIRME_KILIT:
        return {"ok": True, "indirmeler": {k: {x: v[x] for x in v if x != "iptal"}
                                           for k, v in _INDIRMELER.items()}}


def indirme_temizle(kimlik=None):
    with _INDIRME_KILIT:
        for k in list(_INDIRMELER):
            if (kimlik is None or k == kimlik) and _INDIRMELER[k]["durum"] != "indiriliyor":
                del _INDIRMELER[k]
    return {"ok": True}


# ----------------------------------------------------------------------
# Tamamlama
# ----------------------------------------------------------------------
def tamamla(model, once, sonra="", en_fazla=64, zaman_asimi=30, dur=None):
    """Kodun devamını önerir (ortadan doldurma için 'suffix' gönderilir).
    dur: üretimi kesen diziler (varsayılan: üç boş satır ve kod çiti)."""
    import requests
    try:
        url = sunucu_url()
    except YerelAIHatasi as e:
        return {"ok": False, "hata": str(e)}
    govde = {"model": model, "prompt": once[-6000:], "max_tokens": int(en_fazla),
             "temperature": 0.2, "stop": dur or ["\n\n\n", "```"]}
    if sonra.strip():
        govde["suffix"] = sonra[:2000]
    try:
        r = requests.post(f"{url}/completions", json=govde, timeout=zaman_asimi)
    except requests.exceptions.Timeout:
        return {"ok": False, "hata": "Model zamanında yanıt vermedi."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "hata": "Yerel AI sunucusuna ulaşılamadı."}
    if r.status_code >= 400:
        return {"ok": False, "hata": f"Yerel AI hatası: {r.text[:200]}"}
    secim = (r.json().get("choices") or [{}])[0]
    try:
        from .ai import dusunceyi_temizle
    except ImportError:
        from ai import dusunceyi_temizle
    return {"ok": True, "tamamlama": dusunceyi_temizle(secim.get("text") or "").rstrip()}


# ----------------------------------------------------------------------
# Öneriler (Hugging Face)
# ----------------------------------------------------------------------
_ONERI_ONBELLEK = None
_ONERI_ZAMANI = 0.0


def _oneri_dosyasi():
    return os.path.join(_veri_dizini(), "model_katalogu.json")


def _hf_cek(ek=""):
    import requests
    url = (f"{HF_API}?filter=gguf&pipeline_tag=text-generation&sort=downloads"
           f"&direction=-1&limit=150&expand[]=gguf&expand[]=downloads"
           f"&expand[]=likes&expand[]=tags&expand[]=siblings{ek}")
    r = requests.get(url, timeout=25, headers={"User-Agent": "TurKod-IDE"})
    r.raise_for_status()
    return r.json()


def hf_isle(ham):
    """HF yanıtı -> sade model listesi (parametre, nicem, indirilecek dosya)."""
    sonuc = []
    for m in ham or []:
        if not isinstance(m, dict):
            continue
        depo = m.get("id") or ""
        kucuk = depo.lower()
        etiketler = [str(t).lower() for t in m.get("tags") or []]
        if any(k in kucuk for k in _UYGUNSUZ) or any(
                any(k in t for k in _UYGUNSUZ) for t in etiketler):
            continue
        gguf = m.get("gguf") or {}
        toplam = gguf.get("total") or 0
        if not toplam:
            continue
        parametre_b = round(toplam / 1e9, 1)
        # Parçalı (…-00001-of-00003.gguf) ve görsel kodlayıcı (mmproj) dosyaları alınmaz.
        dosyalar = [s.get("rfilename", "") for s in m.get("siblings") or []
                    if isinstance(s, dict)]
        dosyalar = [d for d in dosyalar if d.lower().endswith(".gguf") and "/" not in d
                    and "mmproj" not in d.lower() and "-of-" not in d.lower()]
        dosya = nicem = None
        for n in _NICEM_SIRASI:
            eslesen = [d for d in dosyalar
                       if re.search(rf"(?i)[-_.]{n}(?:[-_.]|$)", d[:-5] + ".")]
            if eslesen:
                dosya, nicem = sorted(eslesen, key=len)[0], n
                break
        if not dosya:
            continue
        kodlama = any(k in kucuk for k in ("coder", "code", "starcoder", "codegemma"))
        sonuc.append({
            "ad": f"{depo}/{dosya}",
            "dosya": dosya,
            "depo": depo,
            "baslik": depo.split("/")[-1].replace("-GGUF", "").replace("-gguf", ""),
            "parametre_b": parametre_b,
            "nicem": nicem,
            "boyut_gb": model_boyutu_gb(parametre_b),
            "baglam": gguf.get("context_length") or 0,
            "mimari": gguf.get("architecture") or "",
            "indirme": m.get("downloads") or 0,
            "begeni": m.get("likes") or 0,
            "kodlama": kodlama,
            "sayfa": f"https://huggingface.co/{depo}",
        })
    return sonuc


def _aile(m):
    """Aynı modelin farklı yayıncılarını tek sayar ("Qwen2.5-Coder-1.5B")."""
    b = m["baslik"].lower()
    b = re.sub(r"[-_.](instruct|it|chat|gguf|q\d.*|i1|imat.*)$", "", b)
    return re.sub(r"[^a-z0-9]", "", b)


def _katalog_yukle(tazele=False):
    global _ONERI_ONBELLEK, _ONERI_ZAMANI
    if not tazele and _ONERI_ONBELLEK is not None and time.time() - _ONERI_ZAMANI < ONERI_OMRU:
        return _ONERI_ONBELLEK, "internet"
    if not tazele:
        try:
            with open(_oneri_dosyasi(), "r", encoding="utf-8") as f:
                disk = json.load(f)
            if time.time() - float(disk.get("zaman", 0)) < ONERI_OMRU:
                _ONERI_ONBELLEK, _ONERI_ZAMANI = disk["modeller"], float(disk["zaman"])
                return _ONERI_ONBELLEK, "disk"
        except (OSError, ValueError, KeyError, TypeError):
            pass
    try:
        modeller = hf_isle(_hf_cek())
        try:
            modeller += hf_isle(_hf_cek("&search=coder"))
        except Exception:  # noqa: BLE001
            pass
        tekil = {}
        for m in modeller:
            tekil.setdefault(m["ad"], m)
        modeller = list(tekil.values())
        if modeller:
            _ONERI_ONBELLEK, _ONERI_ZAMANI = modeller, time.time()
            try:
                with open(_oneri_dosyasi(), "w", encoding="utf-8") as f:
                    json.dump({"zaman": _ONERI_ZAMANI, "modeller": modeller}, f,
                              ensure_ascii=False)
            except OSError:
                pass
            return modeller, "internet"
    except Exception as e:  # noqa: BLE001
        print(f"[TurKod] Model kataloğu indirilemedi: {e}", flush=True)
    try:
        with open(_oneri_dosyasi(), "r", encoding="utf-8") as f:
            return json.load(f)["modeller"], "disk"
    except (OSError, ValueError, KeyError, TypeError):
        return None, "yedek"


def _degerlendir(m, d, dep):
    calisir, hizli, gerekce = sigar_mi(m["parametre_b"], d, dep, m.get("boyut_gb"))
    return {**m, "boyut_gb": m.get("boyut_gb") or model_boyutu_gb(m["parametre_b"]),
            "uygun": calisir, "hizli": hizli, "gerekce": gerekce,
            "kodi_uygun": kodi_uygun_mu(m.get("baglam"))}


def _yedek_listesi():
    sonuc = {}
    for grup, liste in YEDEK_ONERILER.items():
        sonuc[grup] = [{
            "ad": f"{depo}/{dosya}", "dosya": dosya, "depo": depo,
            "baslik": depo.split("/")[-1].replace("-GGUF", ""), "parametre_b": p,
            "nicem": "Q4_K_M", "boyut_gb": model_boyutu_gb(p), "baglam": 0, "mimari": "",
            "indirme": 0, "begeni": 0, "kodlama": kod,
            "sayfa": f"https://huggingface.co/{depo}"} for depo, dosya, p, kod in liste]
    return sonuc


def onerilen_modeller(tazele=False):
    """Bu bilgisayarın belleğine ve DEPOLAMASINA uygun 3 hafif + 3 büyük model."""
    d = donanim_bilgisi(tazele=tazele)
    dep = depolama_analizi()
    modeller, kaynak = _katalog_yukle(tazele)
    if not modeller:
        yedek = _yedek_listesi()
        modeller = yedek["hafif"] + yedek["buyuk"]
        kaynak = "yedek"
    degerli = [_degerlendir(m, d, dep) for m in modeller]
    kullanilabilir = dep["kullanilabilir_gb"]

    def sec(adaylar, n=3):
        secilen, aileler = [], set()
        for m in adaylar:
            a = _aile(m)
            if a in aileler:
                continue
            aileler.add(a)
            secilen.append(m)
            if len(secilen) == n:
                break
        return secilen

    uygun = [m for m in degerli if m["uygun"]]
    # Hafif: 0.3–4.5B; otomatik tamamlama için kodlama modelleri öne alınır.
    hafif = sorted((m for m in uygun if 0.3 <= m["parametre_b"] <= 4.5),
                   key=lambda m: (not m["kodlama"], -m["indirme"]))
    # Büyük: hızlı (CUDA) olanlar, sonra boş alanın yarısından azını kaplayanlar,
    # sonra indirme sayısı. Disk darsa küçük-büyük modeller öne çıkar.
    buyuk = sorted((m for m in uygun if 4.5 < m["parametre_b"] <= 72),
                   key=lambda m: (not m["hizli"], m["boyut_gb"] > kullanilabilir * 0.5,
                                  -m["indirme"]))
    if len(sec(buyuk)) < 3:
        ekstra = sorted((m for m in uygun if 2.5 <= m["parametre_b"] <= 4.5),
                        key=lambda m: -m["indirme"])
        buyuk = buyuk + [m for m in ekstra if m not in buyuk]
    hafif_sec, buyuk_sec = sec(hafif), sec(buyuk)
    toplam = round(sum(m["boyut_gb"] for m in hafif_sec + buyuk_sec), 1)
    return {"ok": True, "kaynak": kaynak, "donanim": d, "depolama": dep,
            "hafif": hafif_sec, "buyuk": buyuk_sec,
            "onerilen_toplam_gb": toplam,
            "hepsi_sigar": toplam <= kullanilabilir,
            "tumu": sorted(degerli, key=lambda m: -m["indirme"])[:200]}


def model_ara(sorgu):
    """Hugging Face'te GGUF model arar."""
    sorgu = (sorgu or "").strip()
    if not sorgu:
        return {"ok": True, "modeller": []}
    try:
        from urllib.parse import quote
        modeller = hf_isle(_hf_cek(f"&search={quote(sorgu)}"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "hata": f"Arama yapılamadı: {e}"}
    d, dep = donanim_bilgisi(), depolama_analizi()
    return {"ok": True, "modeller": [_degerlendir(m, d, dep) for m in modeller][:60]}
