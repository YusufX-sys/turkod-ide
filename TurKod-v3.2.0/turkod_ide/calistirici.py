"""TürKod dosya çalıştırıcı: .trpy çift tıklama ve `turkod` komutu.

İki kip vardır (ikisi de backend_main.py üzerinden açılır):

* Pencere kipi  ``turkod_backend.exe --terminal dosya.trpy``
  Gezgin'de çift tıklanınca açılan, koyu temalı terminal penceresi (Tk).
  Program kendi penceresini açıyorsa (pygame, tkinter, turtle...) o pencere
  AYRI bir pencere olarak görünür; terminal çıktıyı ve input() girişini taşır.

* Konsol kipi   ``turkod dosya.trpy [argümanlar]``  (PATH'teki backend\\turkod.exe)
  Python gibi: program o anki konsolda çalışır, giriş/çıkış doğrudan konsoldur,
  çıkış kodu programın çıkış koduyla aynıdır.

Kullanıcı kodu IDE'deki "Çalıştır" ile aynı yoldan geçer (dogrula ->
turkce_kodu_donustur -> runner.RUNNER_KODU, paketli python_embed); fark,
çalışma klasörünün .trpy dosyasının klasörü olması ve __file__ / sys.argv'nin
.trpy dosyasını göstermesidir (oyunlar resim/ses dosyalarını yanından bulur).
"""
import codecs
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

try:
    from .runner import runner_kodu_uret
    from .cikti_cevirici import SatirCevirici
except ImportError:
    from runner import runner_kodu_uret
    from cikti_cevirici import SatirCevirici

CREATE_NO_WINDOW = 0x08000000
UZANTI = ".trpy"


# ----------------------------------------------------------------------
# Ortak yardımcılar
# ----------------------------------------------------------------------
def _paketli_mi():
    return getattr(sys, "frozen", False)


def _kaynak_dizini():
    """Paketli derlemede PyInstaller veri klasörü (_internal), değilse bu klasör."""
    if _paketli_mi():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def surum():
    if _paketli_mi():
        yol = os.path.join(_kaynak_dizini(), "surum.txt")
    else:
        yol = os.path.join(os.path.dirname(_kaynak_dizini()), "surum.txt")
    try:
        with open(yol, encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def ikon_yolu():
    yol = os.path.join(_kaynak_dizini(), "editor-logo.ico")
    return yol if os.path.exists(yol) else None


def python_exe_bul():
    """ide_core.IDECore._python_exe_bul ile aynı kural (IDECore'u yüklemeden)."""
    python_exe = None
    if _paketli_mi():
        embed = os.path.join(os.path.dirname(sys.executable),
                             "_internal", "python_embed", "python.exe")
        if os.path.exists(embed):
            python_exe = embed
    if not python_exe:
        python_exe = shutil.which("python.exe") or shutil.which("python")
    if not python_exe and not _paketli_mi():
        python_exe = sys.executable
    if python_exe and python_exe.lower().endswith("pythonw.exe"):
        python_exe = python_exe[:-len("pythonw.exe")] + "python.exe"
    return python_exe


def _ortam():
    """ide_core.IDECore._subprocess_env ile aynı: `pip yükle` paketleri görünsün."""
    env = dict(os.environ)
    # PyInstaller'ın tkinter kancası backend'in Tcl/Tk yollarını koyar;
    # kullanıcı programı (python_embed) kendi Tcl'ini kullanmalı, yoksa
    # sürümler ayrıştığında tkinter/turtle init.tcl hatasıyla açılmaz.
    for _anahtar in ("TCL_LIBRARY", "TK_LIBRARY"):
        env.pop(_anahtar, None)
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    pkg = os.path.join(base, "TurKod", "pip_packages")
    try:
        os.makedirs(pkg, exist_ok=True)
    except OSError:
        pass
    mevcut = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pkg + (os.pathsep + mevcut if mevcut else "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def editor_exe_bul():
    """<kurulum>\\turkod_flutter.exe (backend\\ klasörünün bir üstü)."""
    if not _paketli_mi():
        return None
    yol = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "turkod_flutter.exe")
    return yol if os.path.exists(yol) else None


def editorde_ac(dosyalar=()):
    exe = editor_exe_bul()
    if not exe:
        return False
    try:
        # Açık editör varsa yeni süreç dosyayı ona iletip onu öne getirir;
        # bunun için öne getirme izni bu (ön plandaki) süreçten devredilir.
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:  # noqa: BLE001
        pass
    try:
        # "cmd /c start" aracılığıyla: editör bu sürecin ALT süreci olmaz. Kurulum
        # / güncelleme 'taskkill /T /IM turkod_backend.exe' ile terminal
        # pencerelerini kapatırken açık editörü kaydetmeden öldürmesin.
        # Her yol tırnaklanır: '&' içeren klasör adları cmd'yi bölmesin.
        komut = 'cmd.exe /d /c start "" ' + " ".join(f'"{y}"' for y in (exe, *dosyalar))
        subprocess.Popen(komut, cwd=os.path.dirname(exe), close_fds=True,
                         creationflags=CREATE_NO_WINDOW)
        return True
    except OSError:
        return False


# Geçici çalışma klasörünü oluşturan sürecin PID'i (ide_core da aynı adı yazar).
SAHIP_DOSYASI = ".turkod_sahip"


def _surec_yasiyor(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        # Erişim engeli: süreç var ama sorgulanamıyor -> yaşıyor say.
        return ctypes.GetLastError() == 5
    try:
        kod = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(h, ctypes.byref(kod)):
            return True
        return kod.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def _sahibi_yasiyor(yol):
    try:
        with open(os.path.join(yol, SAHIP_DOSYASI), encoding="ascii") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return False  # eski sürümden kalma / sahipsiz klasör
    try:
        return _surec_yasiyor(pid)
    except Exception:
        return True  # emin değilsek silme


def gecici_sahiplen(dizin):
    try:
        with open(os.path.join(dizin, SAHIP_DOSYASI), "w", encoding="ascii") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def _eski_gecicileri_temizle(saat=6):
    """Kapatılan konsol/çöken süreçlerden kalan %TEMP%\\turkod_calisma_* klasörleri.
    Klasörün tarihi yalnızca içine dosya eklenince değişir: eskiden 6 saatten
    uzun çalışan bir programın (bot, sunucu, oyun) klasörü — çevrilmiş yerel
    modüller ve kaydedilmemiş sekmede programın yazdığı dosyalar dahil —
    çalışırken siliniyordu. Artık sahibi yaşayan klasörlere dokunulmaz."""
    sinir = time.time() - saat * 3600
    try:
        kok = tempfile.gettempdir()
        for ad in os.listdir(kok):
            if not ad.startswith("turkod_calisma_"):
                continue
            yol = os.path.join(kok, ad)
            try:
                if os.path.isdir(yol) and os.path.getmtime(yol) < sinir \
                        and not _sahibi_yasiyor(yol):
                    shutil.rmtree(yol, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass


def _dosya_oku(yol):
    with open(yol, "rb") as f:
        ham = f.read()
    # UTF-16 (ör. PowerShell 5.1 '>' ile oluşturulan dosyalar): IDE açıyordu,
    # çift tıklama/turkod komutu cp1254 sanıp NUL'lu bozuk metin okuyordu.
    if ham.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return ham.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for kod in ("utf-8-sig", "cp1254"):
        try:
            return ham.decode(kod)
        except UnicodeDecodeError:
            continue
    return ham.decode("utf-8", errors="replace")


class Hazirlik:
    """Bir .trpy dosyasını çalıştırmaya hazırlar (geçici klasör + komut)."""

    def __init__(self, yol, argumanlar=()):
        self.yol = os.path.abspath(yol)
        self.argumanlar = list(argumanlar)
        self.komut = None
        self.cwd = os.path.dirname(self.yol) or os.getcwd()
        self.hatalar = []        # [str] — kullanıcıya gösterilecek, Türkçe
        self._gecici = None

    def hazirla(self):
        if not os.path.isfile(self.yol):
            self.hatalar.append(f"Dosya bulunamadı: {self.yol}")
            return False
        try:
            kod = _dosya_oku(self.yol)
        except OSError as e:
            self.hatalar.append(f"Dosya okunamadı: {e}")
            return False
        if not kod.strip():
            self.hatalar.append("Dosya boş: çalıştırılacak kod yok.")
            return False

        # Sözlük modülü yüklenirken bilgi satırı basar; programın çıktısına karışmasın.
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                from .ast_katmani import dogrula
                from .converter import turkce_kodu_donustur, yerel_modulleri_hazirla
            except ImportError:
                from ast_katmani import dogrula
                from converter import turkce_kodu_donustur, yerel_modulleri_hazirla

        sonuc = dogrula(kod)
        if not sonuc.basarili:
            self.hatalar.extend(str(h) for h in sonuc.hatalar)
            return False
        python_exe = python_exe_bul()
        if not python_exe:
            self.hatalar.append("Python bulunamadı. TürKod'u yeniden kurmayı deneyin.")
            return False

        _eski_gecicileri_temizle()
        try:
            self._gecici = tempfile.mkdtemp(prefix="turkod_calisma_")
        except OSError as e:
            self.hatalar.append(f"Geçici dosyalar yazılamadı: {e}")
            return False
        gecici_sahiplen(self._gecici)
        # Aynı klasördeki, içe aktarılan .trpy dosyaları da çevrilir.
        yerel, _yazilan, modul_hatalari = yerel_modulleri_hazirla(
            kod, self.cwd, self._gecici)
        if modul_hatalari:
            self.hatalar.extend(modul_hatalari)
            self.temizle()
            return False
        try:
            python_kodu = turkce_kodu_donustur(kod, yerel_moduller=yerel)
        except Exception as e:  # noqa: BLE001 - çevirici hatası kullanıcıya gösterilir
            self.hatalar.append(f"Çeviri hatası: {e}")
            self.temizle()
            return False

        try:
            kod_yolu = os.path.join(self._gecici, "turkce_kod_calisma.py")
            runner_yolu = os.path.join(self._gecici, "runner.py")
            with open(kod_yolu, "w", encoding="utf-8") as f:
                f.write(python_kodu)
            with open(runner_yolu, "w", encoding="utf-8") as f:
                f.write(self._runner_kodu(kod_yolu))
        except OSError as e:
            self.hatalar.append(f"Geçici dosyalar yazılamadı: {e}")
            self.temizle()
            return False

        self.komut = [python_exe, "-X", "utf8", "-u", runner_yolu, *self.argumanlar]
        return True

    def _runner_kodu(self, kod_yolu):
        # __file__ ve sys.argv[0] .trpy dosyasını gösterir; modül arama yolu
        # .trpy'nin klasörüdür (Python'daki gibi). Geçici klasör önce gelir:
        # çevrilmiş yerel .trpy modülleri oradadır.
        return runner_kodu_uret(kod_yolu, program_yolu=self.yol,
                                calisma_dizini=self.cwd, ek_yollar=[self._gecici])

    def temizle(self):
        if not self._gecici:
            return
        shutil.rmtree(self._gecici, ignore_errors=True)
        self._gecici = None


def _agaci_sonlandir(pid):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       creationflags=CREATE_NO_WINDOW, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


def _hata_metni(hatalar):
    cizgi = "=" * 50
    satirlar = [cizgi, "[HATA]: Kod çalıştırılamadı"]
    satirlar += [f"  {h}" for h in hatalar]
    satirlar.append(cizgi)
    return "\n".join(satirlar) + "\n"


# ----------------------------------------------------------------------
# Konsol kipi (turkod.exe)
# ----------------------------------------------------------------------
YARDIM = """TürKod {surum}

Kullanım:
  turkod <dosya.trpy> [argümanlar]   Programı bu konsolda çalıştırır
  turkod --pencere <dosya.trpy>      Programı TürKod terminal penceresinde çalıştırır
  turkod --editor [dosya.trpy ...]   TürKod editörünü (IDE) açar
  turkod --surum                     Sürümü gösterir
  turkod --yardim                    Bu yardımı gösterir
"""


def _konsol_hazirla():
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetConsoleOutputCP(65001)
        k32.SetConsoleCP(65001)
        tutamak = k32.GetStdHandle(-11)
        mod = ctypes.c_uint32()
        if k32.GetConsoleMode(tutamak, ctypes.byref(mod)):
            k32.SetConsoleMode(tutamak, mod.value | 0x0004)  # VT işleme (renkler)
    except Exception:  # noqa: BLE001
        pass
    for akim in (sys.stdout, sys.stderr):
        try:
            akim.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def konsolda_calistir(yol, argumanlar=()):
    _konsol_hazirla()
    h = Hazirlik(yol, argumanlar)
    if not h.hazirla():
        renkli = sys.stderr.isatty()
        metin = _hata_metni(h.hatalar)
        sys.stderr.write(f"\x1b[91m{metin}\x1b[0m" if renkli else metin)
        return 1
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(f"{os.path.basename(h.yol)} — TürKod")
    except Exception:  # noqa: BLE001
        pass

    import signal
    # Ctrl+C programa (alt sürece) gider; çalıştırıcı kendisi kapanmaz, çıkış kodunu bekler.
    eski = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        surec = subprocess.Popen(h.komut, cwd=h.cwd, env=_ortam())
        return surec.wait()
    except OSError as e:
        sys.stderr.write(_hata_metni([f"Program başlatılamadı: {e}"]))
        return 1
    finally:
        signal.signal(signal.SIGINT, eski)
        h.temizle()


def cli_main(argv):
    """turkod.exe ve `turkod_backend.exe --terminal` girişi. Çıkış kodu döndürür."""
    argv = list(argv)
    if not argv or argv[0] in ("-h", "--help", "--yardim", "/?"):
        _konsol_hazirla()
        print(YARDIM.format(surum=surum()))
        return 0
    ilk = argv[0]
    if ilk in ("-V", "--version", "--surum"):
        _konsol_hazirla()
        print(f"TürKod {surum()}")
        return 0
    if ilk in ("--editor", "--editör"):
        dosyalar = [os.path.abspath(d) for d in argv[1:]]
        if editorde_ac(dosyalar):
            return 0
        _konsol_hazirla()
        print("TürKod editörü bulunamadı.", file=sys.stderr)
        return 1
    if ilk in ("--terminal", "--pencere"):
        if len(argv) < 2:
            return pencerede_goster_hata("Çalıştırılacak dosya verilmedi.")
        return pencerede_calistir(argv[1], argv[2:])
    return konsolda_calistir(ilk, argv[1:])


# ----------------------------------------------------------------------
# Pencere kipi (Tk terminal)
# ----------------------------------------------------------------------
RENK = {
    "zemin": "#070b16",      # sitenin koyu zemini
    "panel": "#0d1324",
    "panel2": "#131b31",
    "kenar": "#1d2742",
    "yazi": "#e6edf6",
    "soluk": "#7d8aa8",
    "girdi": "#7dd3fc",
    "vurgu": "#22d3ee",      # camgöbeği
    "civit": "#6366f1",      # çivit
    "fusya": "#d946ef",      # fuşya
    "hata": "#f87171",
    "basari": "#4ade80",
    "uyari": "#fbbf24",
    "secim": "#253a66",
    "dugme": "#18213b",
    "dugme_ust": "#223057",
}

_HATA_SATIRI = re.compile(r"^(\[HATA\]|Satır Numarası:|Açıklama:|={50}$|Traceback |  File \"|"
                          r"[A-Za-z_]+(Error|Exception): )")
_AZAMI_SATIR = 20000
_AZAMI_TIK_METNI = 200_000


def _dpi_farkinda_ol():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _uygulama_kimligi():
    # Görev çubuğunda turkod_backend.exe'nin simgesi yerine pencerenin
    # (editor-logo.ico) simgesi görünsün ve terminaller ayrı gruplansın.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TurKod.Terminal")
    except Exception:  # noqa: BLE001
        pass


def _koyu_baslik_cubugu(pencere):
    """Başlık çubuğunu koyu yapar. Pencere görünmezken (alpha 0) çağrılmalıdır:
    Windows 10, özellik çizimden SONRA verilirse çerçeveyi yeniden çizmez;
    başlık yazısı koyu temayla, zemini açık temayla kalır (beyaz zemin üstünde
    siyah kutulu yazı). SWP_FRAMECHANGED çerçeveyi zorla yeniden çizdirir."""
    try:
        import ctypes
        from ctypes import wintypes
        pencere.update_idletasks()
        try:
            hwnd = int(pencere.wm_frame(), 16)
        except (ValueError, TypeError):
            hwnd = ctypes.windll.user32.GetParent(pencere.winfo_id())
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                              ctypes.c_void_p, wintypes.DWORD]
        deger = ctypes.c_int(1)
        for oz in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (yeni / eski Windows 10)
            if dwm.DwmSetWindowAttribute(hwnd, oz, ctypes.byref(deger),
                                         ctypes.sizeof(deger)) == 0:
                break
        if sys.getwindowsversion().build >= 22000:  # yalnızca Windows 11
            renk = RENK["panel"].lstrip("#")
            colorref = ctypes.c_int(int(renk[4:6] + renk[2:4] + renk[0:2], 16))  # 0x00BBGGRR
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref),  # DWMWA_CAPTION_COLOR
                                      ctypes.sizeof(colorref))
            yazi = ctypes.c_int(0x00F6EDE6)  # DWMWA_TEXT_COLOR: RENK["yazi"]
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(yazi), ctypes.sizeof(yazi))
        SWP = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, SWP)
    except Exception:  # noqa: BLE001
        pass


def pencerede_goster_hata(mesaj):
    try:
        import tkinter as tk
        from tkinter import messagebox
        kok = tk.Tk()
        kok.withdraw()
        ikon = ikon_yolu()
        if ikon:
            try:
                kok.iconbitmap(default=ikon)
            except tk.TclError:
                pass
        messagebox.showerror("TürKod", mesaj, parent=kok)
        kok.destroy()
    except Exception:  # noqa: BLE001
        pass
    return 1


def pencerede_calistir(yol, argumanlar=()):
    _dpi_farkinda_ol()
    _uygulama_kimligi()
    try:
        terminal = TerminalPenceresi(yol, argumanlar)
    except Exception as e:  # noqa: BLE001 - Tk açılamadıysa en azından mesaj göster
        return pencerede_goster_hata(f"Terminal penceresi açılamadı:\n{e}")
    return terminal.calistir()


class TerminalPenceresi:
    def __init__(self, yol, argumanlar=()):
        import tkinter as tk
        import tkinter.font as tkfont
        from tkinter import ttk

        self.tk = tk
        self.yol = os.path.abspath(yol)
        self.ad = os.path.basename(self.yol)
        self.argumanlar = list(argumanlar)
        self.surec = None
        self.hazirlik = None
        # Sınırlı kuyruk: "sürekli: yazdır(i)" gibi programlar arayüzün
        # işleyebileceğinden hızlı yazınca kuyruk sınırsız büyüyor (RAM
        # artıyor), pencere ve Durdur düğmesi tepkisiz kalıyordu. Kuyruk
        # dolunca okuyucu bekler, boru dolar ve program yavaşlar.
        self.kuyruk = queue.Queue(maxsize=2000)
        self._girdi_kuyrugu = queue.Queue()
        self.cikis_kodu = 0
        self.baslangic = 0.0
        self.gecmis = []
        self.gecmis_sira = 0
        self._taranan_satir = 1
        self._nesil = 0          # her çalıştırmada artar; eski okuyucunun olayları atlanır

        kok = self.kok = tk.Tk()
        # Koyu başlık çubuğu ilk çizimden önce uygulanabilsin diye pencere
        # hazırlanırken görünmez (bkz. _koyu_baslik_cubugu).
        try:
            kok.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        kok.title(f"{self.ad} — TürKod")
        kok.configure(bg=RENK["zemin"])
        ikon = ikon_yolu()
        if ikon:
            try:
                kok.iconbitmap(default=ikon)
            except tk.TclError:
                pass

        olcek = kok.winfo_fpixels("1i") / 96.0
        self.o = lambda px: max(1, int(round(px * olcek)))
        en, boy = self.o(980), self.o(620)
        x = max(0, (kok.winfo_screenwidth() - en) // 2)
        y = max(0, (kok.winfo_screenheight() - boy) // 3)
        kok.geometry(f"{en}x{boy}+{x}+{y}")
        kok.minsize(self.o(520), self.o(300))

        aileler = set(tkfont.families(kok))
        mono = next((a for a in ("Cascadia Mono", "Cascadia Code", "JetBrains Mono",
                                 "Consolas", "Courier New") if a in aileler), "TkFixedFont")
        arayuz = next((a for a in ("Segoe UI Variable Text", "Segoe UI")
                       if a in aileler), "TkDefaultFont")
        self.f_kod = tkfont.Font(kok, family=mono, size=11)
        self.f_kod_k = tkfont.Font(kok, family=mono, size=11, weight="bold")
        self.f_ui = tkfont.Font(kok, family=arayuz, size=10)
        self.f_ui_k = tkfont.Font(kok, family=arayuz, size=10, weight="bold")
        self.f_ui_kucuk = tkfont.Font(kok, family=arayuz, size=9)

        stil = ttk.Style(kok)
        try:
            stil.theme_use("clam")
        except tk.TclError:
            pass
        stil.configure("TurKod.Vertical.TScrollbar", gripcount=0,
                       background=RENK["kenar"], darkcolor=RENK["zemin"],
                       lightcolor=RENK["zemin"], troughcolor=RENK["zemin"],
                       bordercolor=RENK["zemin"], arrowcolor=RENK["soluk"],
                       relief="flat", arrowsize=self.o(12))
        stil.map("TurKod.Vertical.TScrollbar",
                 background=[("active", RENK["dugme_ust"]), ("pressed", RENK["civit"])])

        self._ust_cubuk()
        self._serit()
        self._metin_alani(ttk)
        self._alt_cubuk()
        self._kisayollar()

        kok.protocol("WM_DELETE_WINDOW", self.kapat)
        _koyu_baslik_cubugu(kok)
        try:
            kok.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    # -- arayüz ---------------------------------------------------------
    def _dugme(self, ana, metin, komut, ipucu=None):
        tk = self.tk
        d = tk.Label(ana, text=metin, font=self.f_ui, fg=RENK["yazi"], bg=RENK["dugme"],
                     padx=self.o(12), pady=self.o(5), cursor="hand2")
        d._etkin = True

        def gir(_):
            if d._etkin:
                d.configure(bg=RENK["dugme_ust"])
            if ipucu:
                self._ipucu_goster(ipucu)

        def cik(_):
            d.configure(bg=RENK["dugme"])
            if ipucu:
                self._ipucu_goster("")

        def tikla(_):
            if d._etkin:
                komut()
                self.metin.focus_set()

        d.bind("<Enter>", gir)
        d.bind("<Leave>", cik)
        d.bind("<Button-1>", tikla)
        return d

    def _dugme_etkin(self, d, etkin):
        d._etkin = etkin
        d.configure(fg=RENK["yazi"] if etkin else RENK["soluk"],
                    cursor="hand2" if etkin else "arrow")

    def _ust_cubuk(self):
        tk = self.tk
        ust = tk.Frame(self.kok, bg=RENK["panel"], padx=self.o(14), pady=self.o(10))
        ust.pack(fill="x")

        # Sağ grup ÖNCE yerleşir: uzun bir klasör yolu düğmeleri pencere dışına itmesin.
        sag = tk.Frame(ust, bg=RENK["panel"])
        sag.pack(side="right")

        sol = tk.Frame(ust, bg=RENK["panel"])
        sol.pack(side="left", fill="x", expand=True)
        self.nokta = tk.Canvas(sol, width=self.o(12), height=self.o(12), bg=RENK["panel"],
                               highlightthickness=0)
        self.nokta.pack(side="left", padx=(0, self.o(10)))
        self._nokta_ciz(RENK["vurgu"])
        baslik = tk.Frame(sol, bg=RENK["panel"])
        baslik.pack(side="left", fill="x", expand=True)
        tk.Label(baslik, text=self.ad, font=self.f_ui_k, fg=RENK["yazi"], bg=RENK["panel"],
                 anchor="w").pack(fill="x")
        klasor = os.path.dirname(self.yol)
        if len(klasor) > 60:
            klasor = klasor[:3] + "…" + klasor[-56:]
        tk.Label(baslik, text=klasor, font=self.f_ui_kucuk,
                 fg=RENK["soluk"], bg=RENK["panel"], anchor="w").pack(fill="x")
        self.durum = tk.Label(sag, text="", font=self.f_ui_kucuk, fg=RENK["zemin"],
                              bg=RENK["vurgu"], padx=self.o(10), pady=self.o(3))
        self.durum.pack(side="left", padx=(0, self.o(12)))
        self.d_yeniden = self._dugme(sag, "↻  Yeniden çalıştır", self.yeniden_calistir,
                                     "Programı baştan çalıştır (F5)")
        self.d_yeniden.pack(side="left", padx=(0, self.o(6)))
        self.d_durdur = self._dugme(sag, "■  Durdur", self.durdur,
                                    "Programı durdur (Ctrl+C, seçim yokken)")
        self.d_durdur.pack(side="left", padx=(0, self.o(6)))
        if editor_exe_bul() or not _paketli_mi():
            d = self._dugme(sag, "✎  Editörde aç", self.editorde_ac,
                            "Dosyayı TürKod editöründe aç (Ctrl+E)")
            d.pack(side="left")

    def _nokta_ciz(self, renk):
        self.nokta.delete("all")
        s = self.o(12)
        self.nokta.create_oval(1, 1, s - 1, s - 1, fill=renk, outline=renk)

    def _serit(self):
        # Sitenin camgöbeği -> çivit -> fuşya gradyanı (ince şerit).
        tk = self.tk
        yuk = self.o(2)
        c = tk.Canvas(self.kok, height=yuk, bg=RENK["panel"], highlightthickness=0, bd=0)
        c.pack(fill="x")

        def renk_karistir(a, b, t):
            a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
            b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
            return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

        def ciz(_=None):
            c.delete("all")
            en = max(1, c.winfo_width())
            adim = max(1, en // 160)
            for x in range(0, en, adim):
                t = x / en
                renk = (renk_karistir(RENK["vurgu"], RENK["civit"], t * 2) if t < 0.5
                        else renk_karistir(RENK["civit"], RENK["fusya"], (t - 0.5) * 2))
                c.create_rectangle(x, 0, x + adim, yuk, fill=renk, outline=renk)

        c.bind("<Configure>", ciz)

    def _metin_alani(self, ttk):
        tk = self.tk
        cerceve = tk.Frame(self.kok, bg=RENK["zemin"])
        cerceve.pack(fill="both", expand=True)
        t = self.metin = tk.Text(
            cerceve, bg=RENK["zemin"], fg=RENK["yazi"], insertbackground=RENK["vurgu"],
            insertwidth=self.o(2), selectbackground=RENK["secim"], selectforeground=RENK["yazi"],
            inactiveselectbackground=RENK["secim"], font=self.f_kod, relief="flat", bd=0,
            highlightthickness=0, padx=self.o(16), pady=self.o(12), wrap="char",
            undo=False, spacing1=self.o(1), spacing3=self.o(1))
        kaydirma = ttk.Scrollbar(cerceve, orient="vertical", command=t.yview,
                                 style="TurKod.Vertical.TScrollbar")
        t.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)

        t.tag_configure("sistem", foreground=RENK["soluk"])
        t.tag_configure("girdi", foreground=RENK["girdi"])
        t.tag_configure("hata", foreground=RENK["hata"])
        t.tag_configure("basari", foreground=RENK["basari"])
        t.tag_configure("uyari", foreground=RENK["uyari"])
        t.tag_configure("vurgu", foreground=RENK["vurgu"], font=self.f_kod_k)

        t.mark_set("giris", "end-1c")
        t.mark_gravity("giris", "left")
        t.focus_set()

    def _alt_cubuk(self):
        tk = self.tk
        alt = tk.Frame(self.kok, bg=RENK["panel"], padx=self.o(14), pady=self.o(5))
        alt.pack(fill="x", side="bottom", before=self.metin.master)
        self.ipucu = tk.Label(alt, text="", font=self.f_ui_kucuk, fg=RENK["soluk"],
                              bg=RENK["panel"], anchor="w")
        self.ipucu.pack(side="left", fill="x", expand=True)
        self.varsayilan_ipucu = ("F5 yeniden çalıştır  ·  Ctrl+C durdur  ·  Ctrl+L temizle  ·  "
                                 "Ctrl+E editörde aç  ·  ↑/↓ önceki girdiler")
        self._ipucu_goster("")
        tk.Label(alt, text=f"TürKod {surum()}  ·  UTF-8", font=self.f_ui_kucuk,
                 fg=RENK["soluk"], bg=RENK["panel"]).pack(side="right")

    def _ipucu_goster(self, metin):
        self.ipucu.configure(text=metin or self.varsayilan_ipucu)

    def _durum(self, metin, renk):
        self.durum.configure(text=metin, bg=renk)
        self._nokta_ciz(renk)

    # -- klavye ---------------------------------------------------------
    def _kisayollar(self):
        t = self.metin
        t.bind("<Key>", self._tus)
        t.bind("<Return>", self._enter)
        t.bind("<KP_Enter>", self._enter)
        t.bind("<BackSpace>", self._geri_sil)
        t.bind("<Delete>", self._ileri_sil)
        t.bind("<Up>", lambda e: self._gecmis_git(-1))
        t.bind("<Down>", lambda e: self._gecmis_git(1))
        t.bind("<Home>", self._satir_basi)
        t.bind("<<Paste>>", self._yapistir)
        t.bind("<<Cut>>", self._kes)
        t.bind("<Control-c>", self._ctrl_c)
        t.bind("<Control-C>", self._ctrl_c)
        t.bind("<Control-l>", lambda e: (self.temizle(), "break")[1])
        t.bind("<Control-L>", lambda e: (self.temizle(), "break")[1])
        t.bind("<Control-a>", self._tumunu_sec)
        # Tk Text'in yerleşik Emacs tarzı düzenleme kısayolları (Ctrl+H/K/D/O/T/I)
        # ve orta tıkla yapıştırma, çıktı alanını korumayı atlatıyordu.
        t.bind("<Control-h>", self._geri_sil)
        for k in ("<Control-k>", "<Control-d>", "<Control-o>", "<Control-t>",
                  "<Control-i>", "<<PasteSelection>>", "<Button-2>", "<ButtonRelease-2>"):
            t.bind(k, lambda e: "break")
        for k in ("<F5>", "<Control-r>", "<Control-R>"):
            self.kok.bind(k, lambda e: (self.yeniden_calistir(), "break")[1])
        for k in ("<Control-e>", "<Control-E>"):
            self.kok.bind(k, lambda e: (self.editorde_ac(), "break")[1])
        self.kok.bind("<Escape>", lambda e: self.kapat() if self.surec is None else None)

    def _calisiyor(self):
        return self.surec is not None and self.surec.poll() is None

    def _duzenlenebilir_mi(self, indeks):
        return self.metin.compare(indeks, ">=", "giris")

    def _secim(self):
        try:
            return self.metin.index("sel.first"), self.metin.index("sel.last")
        except self.tk.TclError:
            return None

    def _tus(self, e):
        # Gezinme/kopyalama tuşları (oklar, Ctrl+harf...) serbest; yazılabilir
        # karakterler (AltGr ile yazılanlar dahil) yalnızca giriş alanına yazılır.
        if not (e.char and (e.char.isprintable() or e.char == "\t")):
            return None
        if not self._calisiyor():
            return "break"
        if not self._duzenlenebilir_mi("insert"):
            self.metin.mark_set("insert", "end-1c")
        sec = self._secim()
        if sec and not self._duzenlenebilir_mi(sec[0]):
            self.metin.tag_remove("sel", "1.0", "end")
        self.metin.see("insert")
        return None

    def _geri_sil(self, _):
        if not self._calisiyor():
            return "break"
        sec = self._secim()
        if sec:
            if self._duzenlenebilir_mi(sec[0]):
                self.metin.delete(*sec)
            return "break"
        if self.metin.compare("insert", "<=", "giris"):
            return "break"
        return None

    def _ileri_sil(self, _):
        if not self._calisiyor():
            return "break"
        sec = self._secim()
        if sec:
            if self._duzenlenebilir_mi(sec[0]):
                self.metin.delete(*sec)
            return "break"
        if not self._duzenlenebilir_mi("insert"):
            return "break"
        return None

    def _satir_basi(self, _):
        if self._duzenlenebilir_mi("insert") and self.metin.compare(
                "giris linestart", "==", "insert linestart"):
            self.metin.mark_set("insert", "giris")
            return "break"
        return None

    def _yapistir(self, _):
        if not self._calisiyor():
            return "break"
        try:
            pano = self.metin.clipboard_get()
        except self.tk.TclError:
            return "break"
        sec = self._secim()
        if sec and self._duzenlenebilir_mi(sec[0]):
            self.metin.delete(*sec)
        if not self._duzenlenebilir_mi("insert"):
            self.metin.mark_set("insert", "end-1c")
        satirlar = pano.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.metin.insert("insert", satirlar[0], "girdi")
        for satir in satirlar[1:]:   # çok satırlı yapıştırma: her satır ayrı girdi
            self._enter(None)
            self.metin.insert("end-1c", satir, "girdi")
        self.metin.see("insert")
        return "break"

    def _kes(self, _):
        sec = self._secim()
        if not sec or not self._duzenlenebilir_mi(sec[0]) or not self._calisiyor():
            return "break"
        return None

    def _ctrl_c(self, _):
        if self._secim():
            return None   # seçim varsa kopyala (Tk varsayılanı)
        if self._calisiyor():
            self.durdur()
        return "break"

    def _tumunu_sec(self, _):
        self.metin.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _enter(self, _):
        if not self._calisiyor():
            return "break"
        satir = self.metin.get("giris", "end-1c")
        self.metin.tag_add("girdi", "giris", "end-1c")
        self.metin.insert("end-1c", "\n", "girdi")
        self.metin.mark_set("giris", "end-1c")
        self.metin.mark_set("insert", "end-1c")
        self.metin.see("end")
        self._taranan_satir = int(self.metin.index("giris").split(".")[0])
        if satir and (not self.gecmis or self.gecmis[-1] != satir):
            self.gecmis.append(satir)
        self.gecmis_sira = len(self.gecmis)
        # Yazma ayrı iş parçacığında: program girdiyi okumuyorken boru dolarsa
        # pencere (ve Durdur düğmesi) donmasın.
        self._girdi_kuyrugu.put((satir + "\n").encode("utf-8"))
        return "break"

    @staticmethod
    def _girdi_yaz(surec, kuyruk):
        while True:
            veri = kuyruk.get()
            if veri is None:
                return
            try:
                surec.stdin.write(veri)
                surec.stdin.flush()
            except (OSError, ValueError):
                return

    def _gecmis_git(self, yon):
        if not self._calisiyor() or not self._duzenlenebilir_mi("insert") or not self.gecmis:
            return None
        self.gecmis_sira = max(0, min(len(self.gecmis), self.gecmis_sira + yon))
        deger = self.gecmis[self.gecmis_sira] if self.gecmis_sira < len(self.gecmis) else ""
        self.metin.delete("giris", "end-1c")
        self.metin.insert("end-1c", deger, "girdi")
        self.metin.mark_set("insert", "end-1c")
        return "break"

    # -- çıktı ----------------------------------------------------------
    def _yaz(self, metin, etiket=None):
        """Çıktıyı kullanıcının yazmakta olduğu girdinin ÖNÜNE ekler."""
        if not metin:
            return
        t = self.metin
        altta = t.yview()[1] >= 0.999
        metin = metin.replace("\r\n", "\n")
        parcalar = metin.split("\r")
        for i, parca in enumerate(parcalar):
            if i > 0:   # \r: satır başına dön (ilerleme çubukları)
                t.delete("giris linestart", "giris")
            if parca:
                t.mark_set("_son", "giris")
                t.mark_gravity("_son", "right")
                t.insert("giris", parca, etiket or ())
                t.mark_set("giris", "_son")
        if etiket is None:
            self._satirlari_renklendir()
        satir_sayisi = int(t.index("end-1c").split(".")[0])
        if satir_sayisi > _AZAMI_SATIR:
            fazla = satir_sayisi - _AZAMI_SATIR
            t.delete("1.0", f"{fazla + 1}.0")
            self._taranan_satir = max(1, self._taranan_satir - fazla)
        if altta:
            t.see("end")

    def _satirlari_renklendir(self):
        t = self.metin
        son = int(t.index("giris").split(".")[0])
        for no in range(max(self._taranan_satir, son - _AZAMI_SATIR), son):
            satir = t.get(f"{no}.0", f"{no}.end")
            if _HATA_SATIRI.match(satir):
                t.tag_add("hata", f"{no}.0", f"{no}.end")
        self._taranan_satir = son

    def _kuyrugu_bosalt(self):
        try:
            parcalar = []
            bitti = None
            # Tik başına sınırlı iş: arayüz her 25 ms'de nefes alabilsin.
            for _ in range(500):
                nesil, tur, veri = self.kuyruk.get_nowait()
                if nesil != self._nesil:
                    continue
                if tur == "cikti":
                    parcalar.append(veri)
                else:
                    bitti = veri
                    break
        except queue.Empty:
            pass
        if parcalar:
            metin = "".join(parcalar)
            if len(metin) > _AZAMI_TIK_METNI:
                # Zaten yalnızca son satırlar tutuluyor; gerisi dizilmez.
                kes = metin.find("\n", len(metin) - _AZAMI_TIK_METNI)
                metin = metin[kes + 1:] if kes != -1 else metin[-_AZAMI_TIK_METNI:]
            self._yaz(metin)
        if bitti is not None:
            self._bitti(bitti)
        self.kok.after(25, self._kuyrugu_bosalt)

    def _oku(self, surec, nesil):
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        fd = surec.stdout.fileno()
        # Kütüphanelerin İngilizce bilgi/uyarı satırları Türkçeleştirilir.
        cevirici = SatirCevirici(lambda m: self.kuyruk.put((nesil, "cikti", m)))
        try:
            while True:
                ham = os.read(fd, 8192)
                if not ham:
                    break
                metin = cozucu.decode(ham)
                if metin:
                    cevirici.besle(metin)
            kalan = cozucu.decode(b"", final=True)
            if kalan:
                cevirici.besle(kalan)
        except OSError:
            pass
        cevirici.bitir()
        kod = surec.wait()
        self.kuyruk.put((nesil, "bitti", kod))

    # -- çalıştırma -----------------------------------------------------
    def baslat(self):
        self._nesil += 1
        self._durum("Hazırlanıyor", RENK["civit"])
        self._dugme_etkin(self.d_durdur, False)
        self._yaz(f"▶ {self.ad}", "vurgu")
        self._yaz(f"   {time.strftime('%H:%M:%S')}\n\n", "sistem")
        self.kok.update_idletasks()

        h = self.hazirlik = Hazirlik(self.yol, self.argumanlar)
        if not h.hazirla():
            self._yaz(_hata_metni(h.hatalar), "hata")
            self._bitti(1, baslamadi=True)
            return
        try:
            self.surec = subprocess.Popen(
                h.komut, cwd=h.cwd, env=_ortam(), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            h.temizle()
            self._yaz(_hata_metni([f"Program başlatılamadı: {e}"]), "hata")
            self._bitti(1, baslamadi=True)
            return
        self.baslangic = time.monotonic()
        self._durum("Çalışıyor", RENK["vurgu"])
        self._dugme_etkin(self.d_durdur, True)
        self._girdi_kuyrugu = queue.Queue()
        threading.Thread(target=self._oku, args=(self.surec, self._nesil), daemon=True).start()
        threading.Thread(target=self._girdi_yaz, args=(self.surec, self._girdi_kuyrugu),
                         daemon=True).start()

    def _bitti(self, kod, baslamadi=False):
        self.cikis_kodu = kod
        self._girdi_kuyrugu.put(None)
        if self.hazirlik:
            self.hazirlik.temizle()
        self.surec = None
        self._dugme_etkin(self.d_durdur, False)
        # Kullanıcının yarım bıraktığı girdi atılır.
        self.metin.delete("giris", "end-1c")
        if self.metin.get("end-2c", "end-1c") not in ("\n", ""):
            self._yaz("\n", "sistem")
        if baslamadi:
            self._durum("Hata", RENK["hata"])
            self._yaz("\nKod düzeltildikten sonra F5 ile yeniden çalıştırabilirsiniz.\n", "sistem")
            return
        sure = time.monotonic() - self.baslangic
        if kod == 0:
            self._durum("Tamamlandı", RENK["basari"])
            self._yaz(f"\n── Program tamamlandı · {sure:.2f} sn ", "basari")
        elif self._durduruldu:
            self._durum("Durduruldu", RENK["uyari"])
            self._yaz(f"\n── Program durduruldu · {sure:.2f} sn ", "uyari")
        else:
            self._durum("Hata" if kod == 1 else f"Çıkış kodu {kod}", RENK["hata"])
            self._yaz(f"\n── Program {kod} koduyla sonlandı · {sure:.2f} sn ", "hata")
        self._yaz("── F5: yeniden çalıştır · Esc: kapat\n", "sistem")
        self.metin.see("end")

    _durduruldu = False

    def durdur(self):
        if not self._calisiyor():
            return
        self._durduruldu = True
        _agaci_sonlandir(self.surec.pid)

    def yeniden_calistir(self):
        self._nesil += 1              # eski sürecin çıktısı/"bitti" olayı yok sayılır
        if self._calisiyor():
            _agaci_sonlandir(self.surec.pid)
        self._girdi_kuyrugu.put(None)
        # Süreç bitmiş ama "bitti" olayı henüz işlenmemiş olabilir: o olay artık
        # yok sayılacağından geçici klasör burada her durumda temizlenir.
        if self.hazirlik:
            self.hazirlik.temizle()
        self.surec = None
        self._durduruldu = False
        self.temizle()
        self.baslat()

    def temizle(self):
        self.metin.delete("1.0", "giris")
        self._taranan_satir = 1

    def editorde_ac(self):
        if not editorde_ac([self.yol]):
            self._ipucu_goster("TürKod editörü bulunamadı.")

    def kapat(self):
        self._girdi_kuyrugu.put(None)
        if self._calisiyor():
            self._nesil += 1
            _agaci_sonlandir(self.surec.pid)
        if self.hazirlik:
            self.hazirlik.temizle()
        self.kok.destroy()

    def calistir(self):
        self.kok.after(10, self.baslat)
        self.kok.after(25, self._kuyrugu_bosalt)
        self.kok.mainloop()
        return self.cikis_kodu
