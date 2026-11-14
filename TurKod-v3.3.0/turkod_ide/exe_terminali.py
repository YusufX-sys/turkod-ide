"""TürKod EXE'lerinin terminal penceresi ve kaynak kodu penceresi.

Bu dosya EXE'nin İÇİNE konur (exe_donusturucu.py); TürKod'un diğer
modüllerine bağlı değildir. calistirici.TerminalPenceresi'nin sade hâlidir:
program aynı EXE'nin ikinci bir sürecinde (TURKOD_EXE_COCUK=1) çalışır,
çıktısı bu pencereye akar, yazılanlar programın girdisine gider.
"""
import codecs
import os
import queue
import re
import subprocess
import sys
import threading
import time

CREATE_NO_WINDOW = 0x08000000

RENK = {
    "zemin": "#070b16", "panel": "#0d1324", "kenar": "#1d2742", "yazi": "#e6edf6",
    "soluk": "#7d8aa8", "girdi": "#7dd3fc", "vurgu": "#22d3ee", "civit": "#6366f1",
    "hata": "#f87171", "basari": "#4ade80", "uyari": "#fbbf24", "secim": "#253a66",
    "dugme": "#18213b", "dugme_ust": "#223057",
}

_HATA_SATIRI = re.compile(r"^(\[HATA\]|Satır Numarası:|Açıklama:|={50}$|Dosya: )")
_AZAMI_SATIR = 20000

try:
    # cikti_cevirici kütüphanelerin hata satırlarını (ör. "ValueError: ...")
    # "runner" modülünün hata_turu_adi / hata_aciklamasi işlevleriyle çevirir.
    # EXE'de çalıştırıcının tamamı yoktur; bu iki işlevi taşıyan küçük modül
    # (exe_donusturucu.HATA_CEVIRILERI_SABLONU) onun yerine geçer. Bu süreç
    # kullanıcı kodu çalıştırmaz; programın kendi "runner" modülüyle çakışmaz.
    import _tk_hata_cevirileri
    sys.modules.setdefault("runner", _tk_hata_cevirileri)
except Exception:  # noqa: BLE001
    pass

try:
    # EXE'de "_tk_cikti_cevirici" adıyla bulunur (kullanıcının modülleriyle
    # çakışmasın diye); geliştirici kipinde asıl adıyla.
    try:
        from _tk_cikti_cevirici import SatirCevirici
    except ImportError:
        from cikti_cevirici import SatirCevirici
except Exception:  # noqa: BLE001 - çeviri yoksa çıktı olduğu gibi gösterilir
    SatirCevirici = None


def _dpi_farkinda_ol():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass


def _koyu_baslik(pencere):
    """Başlık çubuğunu koyu yapar (calistirici._koyu_baslik_cubugu ile aynı).
    Pencere görünmezken (alpha 0) çağrılmalı; SWP_FRAMECHANGED çerçeveyi
    yeniden çizdirir, sonra pencere görünür yapılır."""
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
        for oz in (20, 19):
            if dwm.DwmSetWindowAttribute(hwnd, oz, ctypes.byref(deger),
                                         ctypes.sizeof(deger)) == 0:
                break
        SWP = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020
        ctypes.windll.user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, SWP)
    except Exception:  # noqa: BLE001
        pass
    try:
        pencere.attributes("-alpha", 1.0)
    except Exception:  # noqa: BLE001
        pass


def _agaci_sonlandir(pid):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       creationflags=CREATE_NO_WINDOW, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


def _pencere_hazirla(tk, baslik, en, boy):
    kok = tk.Tk()
    try:
        kok.attributes("-alpha", 0.0)   # koyu başlık çizilene kadar görünmez
    except tk.TclError:
        pass
    kok.title(baslik)
    kok.configure(bg=RENK["zemin"])
    try:
        kok.iconbitmap(default=sys.executable)
    except tk.TclError:
        pass
    olcek = kok.winfo_fpixels("1i") / 96.0
    o = lambda px: max(1, int(round(px * olcek)))  # noqa: E731
    x = max(0, (kok.winfo_screenwidth() - o(en)) // 2)
    y = max(0, (kok.winfo_screenheight() - o(boy)) // 3)
    kok.geometry(f"{o(en)}x{o(boy)}+{x}+{y}")
    kok.minsize(o(420), o(260))
    return kok, o


def _yazi_tipleri(kok):
    import tkinter.font as tkfont
    aileler = set(tkfont.families(kok))
    mono = next((a for a in ("Cascadia Mono", "Consolas", "Courier New") if a in aileler),
                "TkFixedFont")
    arayuz = next((a for a in ("Segoe UI Variable Text", "Segoe UI") if a in aileler),
                  "TkDefaultFont")
    return tkfont.Font(kok, family=mono, size=11), tkfont.Font(kok, family=arayuz, size=10)


class _Dugmeler:
    def __init__(self, tk, ana, font, o):
        self.tk, self.ana, self.font, self.o = tk, ana, font, o

    def ekle(self, metin, komut, sag=True):
        d = self.tk.Label(self.ana, text=metin, font=self.font, fg=RENK["yazi"],
                          bg=RENK["dugme"], padx=self.o(12), pady=self.o(4), cursor="hand2")
        d.bind("<Button-1>", lambda _e: komut())
        d.bind("<Enter>", lambda _e: d.configure(bg=RENK["dugme_ust"]))
        d.bind("<Leave>", lambda _e: d.configure(bg=RENK["dugme"]))
        d.pack(side="right" if sag else "left", padx=(self.o(6), 0), pady=self.o(6))
        return d


def _metin_alani(tk, ana, font, o):
    from tkinter import ttk
    cerceve = tk.Frame(ana, bg=RENK["zemin"])
    cerceve.pack(fill="both", expand=True, padx=o(10), pady=(o(8), 0))
    metin = tk.Text(cerceve, font=font, bg=RENK["zemin"], fg=RENK["yazi"],
                    insertbackground=RENK["vurgu"], selectbackground=RENK["secim"],
                    relief="flat", borderwidth=0, highlightthickness=0, wrap="char",
                    undo=False, padx=o(6), pady=o(4))
    kaydirma = ttk.Scrollbar(cerceve, orient="vertical", command=metin.yview)
    metin.configure(yscrollcommand=kaydirma.set)
    kaydirma.pack(side="right", fill="y")
    metin.pack(side="left", fill="both", expand=True)
    for etiket, renk in (("hata", "hata"), ("sistem", "soluk"), ("vurgu", "vurgu"),
                         ("basari", "basari"), ("uyari", "uyari"), ("girdi", "girdi")):
        metin.tag_configure(etiket, foreground=RENK[renk])
    return metin


# ----------------------------------------------------------------------
# Kaynak kodu penceresi
# ----------------------------------------------------------------------
def kaynak_penceresi_ac(tk, ana, ad, kaynak, kok_mu=False):
    """Kaynak kodunu salt okunur gösterir; Kopyala ve Kaydet düğmeleri vardır."""
    if kok_mu:
        pencere, o = _pencere_hazirla(tk, f"{ad} — TürKod kaynak kodu", 820, 600)
    else:
        pencere = tk.Toplevel(ana)
        pencere.attributes("-alpha", 0.0)
        pencere.title(f"{ad} — TürKod kaynak kodu")
        pencere.configure(bg=RENK["zemin"])
        olcek = pencere.winfo_fpixels("1i") / 96.0
        o = lambda px: max(1, int(round(px * olcek)))  # noqa: E731
        pencere.geometry(f"{o(820)}x{o(600)}")
    f_kod, f_ui = _yazi_tipleri(pencere)
    alt = tk.Frame(pencere, bg=RENK["panel"])
    alt.pack(side="bottom", fill="x")
    metin = _metin_alani(tk, pencere, f_kod, o)
    if kaynak is None:
        metin.insert("end", "Bu programın kaynak kodu gizli: EXE yapılırken "
                            "'Kaynak koduna bakılabilsin' seçilmemiş.", "uyari")
    else:
        metin.insert("end", kaynak)
    metin.configure(state="disabled")
    durum = tk.Label(alt, text="", font=f_ui, fg=RENK["soluk"], bg=RENK["panel"])
    durum.pack(side="left", padx=o(10))
    dugmeler = _Dugmeler(tk, alt, f_ui, o)

    def kopyala():
        pencere.clipboard_clear()
        pencere.clipboard_append(kaynak or "")
        durum.configure(text="Kopyalandı")

    def kaydet():
        from tkinter import filedialog
        yol = filedialog.asksaveasfilename(
            parent=pencere, defaultextension=".trpy", initialfile=f"{ad}.trpy",
            filetypes=[("TürKod dosyası", "*.trpy"), ("Tüm dosyalar", "*.*")])
        if yol:
            with open(yol, "w", encoding="utf-8") as f:
                f.write(kaynak or "")
            durum.configure(text=f"Kaydedildi: {yol}")

    dugmeler.ekle("Kapat", pencere.destroy)
    if kaynak is not None:
        dugmeler.ekle("Kaydet...", kaydet)
        dugmeler.ekle("Kopyala", kopyala)
    pencere.bind("<Escape>", lambda _e: pencere.destroy())
    _koyu_baslik(pencere)
    return pencere


def kaynak_goster(ad, kaynak):
    """Konsolsuz EXE'de "--turkod-kaynak" ile açılan pencere."""
    import tkinter as tk
    _dpi_farkinda_ol()
    pencere = kaynak_penceresi_ac(tk, None, ad, kaynak, kok_mu=True)
    pencere.mainloop()


# ----------------------------------------------------------------------
# Terminal penceresi
# ----------------------------------------------------------------------
class ExeTerminali:
    def __init__(self, ayar, kaynak):
        import tkinter as tk
        self.tk = tk
        self.ad = ayar.get("ad") or "Program"
        self.kaynak = kaynak
        self.kaynak_acik = bool(ayar.get("kaynak_acik"))
        self.surec = None
        self.kuyruk = queue.Queue(maxsize=2000)
        self.nesil = 0
        self.cikis_kodu = 0
        self.baslangic = 0.0
        self.durduruldu = False
        self.gecmis, self.gecmis_sira = [], 0

        kok, o = self.kok, self.o = _pencere_hazirla(tk, f"{self.ad} — TürKod", 940, 600)
        self.f_kod, self.f_ui = _yazi_tipleri(kok)
        alt = tk.Frame(kok, bg=RENK["panel"])
        alt.pack(side="bottom", fill="x")
        self.metin = _metin_alani(tk, kok, self.f_kod, o)
        self.metin.mark_set("giris", "end-1c")
        self.metin.mark_gravity("giris", "left")

        self.durum = tk.Label(alt, text="", font=self.f_ui, fg=RENK["soluk"], bg=RENK["panel"])
        self.durum.pack(side="left", padx=o(10))
        dugmeler = _Dugmeler(tk, alt, self.f_ui, o)
        dugmeler.ekle("Kapat (Esc)", self.kapat)
        dugmeler.ekle("Yeniden başlat (F5)", self.yeniden)
        dugmeler.ekle("Durdur", self.durdur)
        if self.kaynak_acik:
            dugmeler.ekle("Kaynak kodu", lambda: kaynak_penceresi_ac(
                tk, kok, self.ad, self.kaynak))

        m = self.metin
        m.bind("<Key>", self._tus)
        m.bind("<Return>", self._enter)
        m.bind("<BackSpace>", self._geri_sil)
        m.bind("<Up>", lambda _e: self._gecmis_git(-1))
        m.bind("<Down>", lambda _e: self._gecmis_git(1))
        m.bind("<<Paste>>", self._yapistir)
        m.bind("<Control-c>", self._ctrl_c)
        kok.bind("<F5>", lambda _e: self.yeniden())
        kok.bind("<Escape>", lambda _e: self.kapat())
        kok.protocol("WM_DELETE_WINDOW", self.kapat)
        _koyu_baslik(kok)
        m.focus_set()

    # -- yazma ----------------------------------------------------------
    def _yaz(self, metin, etiket=None):
        m = self.metin
        bas = m.index("giris")
        # "giris" işareti sola yapışıktır (yazılan girdi onu itmez); çıktı
        # işaretin önüne eklenir ve işaret çıktının sonuna taşınır.
        m.insert("giris", metin, etiket or ())
        m.mark_set("giris", f"{bas} + {len(metin)} chars")
        if etiket is None:
            for no in range(int(bas.split(".")[0]), int(m.index("giris").split(".")[0]) + 1):
                if _HATA_SATIRI.match(m.get(f"{no}.0", f"{no}.end")):
                    m.tag_add("hata", f"{no}.0", f"{no}.end")
        satir = int(m.index("end-1c").split(".")[0])
        if satir > _AZAMI_SATIR:
            m.delete("1.0", f"{satir - _AZAMI_SATIR}.0")
        m.see("end")

    def _durum(self, metin, renk):
        self.durum.configure(text=metin, fg=RENK[renk])

    # -- klavye ---------------------------------------------------------
    def _calisiyor(self):
        return self.surec is not None and self.surec.poll() is None

    def _tus(self, e):
        if e.state & 0x4 and e.keysym.lower() in ("a", "c"):
            return None
        if e.char and self.metin.compare("insert", "<", "giris"):
            self.metin.mark_set("insert", "end-1c")
        return None

    def _geri_sil(self, _e):
        m = self.metin
        if m.tag_ranges("sel") and m.compare("sel.first", ">=", "giris"):
            return None
        if m.compare("insert", "<=", "giris"):
            return "break"
        return None

    def _yapistir(self, _e):
        if self.metin.compare("insert", "<", "giris"):
            self.metin.mark_set("insert", "end-1c")
        return None

    def _ctrl_c(self, _e):
        if self.metin.tag_ranges("sel"):
            return None
        self.durdur()
        return "break"

    def _gecmis_git(self, yon):
        if not self.gecmis:
            return "break"
        self.gecmis_sira = max(0, min(len(self.gecmis), self.gecmis_sira + yon))
        deger = self.gecmis[self.gecmis_sira] if self.gecmis_sira < len(self.gecmis) else ""
        self.metin.delete("giris", "end-1c")
        self.metin.insert("end-1c", deger, "girdi")
        return "break"

    def _enter(self, _e):
        m = self.metin
        satir = m.get("giris", "end-1c")
        m.delete("giris", "end-1c")
        if not self._calisiyor():
            return "break"
        m.insert("giris", satir + "\n", "girdi")
        m.mark_set("giris", "end-1c")
        m.see("end")
        if satir.strip():
            self.gecmis.append(satir)
        self.gecmis_sira = len(self.gecmis)
        try:
            self.surec.stdin.write((satir + "\n").encode("utf-8"))
            self.surec.stdin.flush()
        except OSError:
            pass
        return "break"

    # -- süreç ----------------------------------------------------------
    def _oku(self, surec, nesil):
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        ilet = lambda m: self.kuyruk.put((nesil, "cikti", m))  # noqa: E731
        cevirici = SatirCevirici(ilet) if SatirCevirici else None
        fd = surec.stdout.fileno()
        try:
            while True:
                ham = os.read(fd, 8192)
                if not ham:
                    break
                parca = cozucu.decode(ham)
                if parca:
                    cevirici.besle(parca) if cevirici else ilet(parca)
        except OSError:
            pass
        if cevirici:
            cevirici.bitir()
        self.kuyruk.put((nesil, "bitti", surec.wait()))

    def _kuyrugu_bosalt(self):
        parcalar, bitti = [], None
        try:
            for _ in range(500):
                nesil, tur, veri = self.kuyruk.get_nowait()
                if nesil != self.nesil:
                    continue
                if tur == "cikti":
                    parcalar.append(veri)
                else:
                    bitti = veri
                    break
        except queue.Empty:
            pass
        if parcalar:
            self._yaz("".join(parcalar))
        if bitti is not None:
            self._bitti(bitti)
        self.kok.after(25, self._kuyrugu_bosalt)

    def baslat(self):
        self.nesil += 1
        self.durduruldu = False
        env = dict(os.environ)
        env["TURKOD_EXE_COCUK"] = "1"
        try:
            self.surec = subprocess.Popen(
                [sys.executable, *sys.argv[1:]], env=env,
                cwd=os.path.dirname(os.path.abspath(sys.executable)),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=0, creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            self._yaz(f"[HATA] Program başlatılamadı: {e}\n", "hata")
            self._durum("Hata", "hata")
            return
        self.baslangic = time.monotonic()
        self._durum("Çalışıyor", "vurgu")
        threading.Thread(target=self._oku, args=(self.surec, self.nesil), daemon=True).start()

    def _bitti(self, kod):
        self.cikis_kodu = kod
        self.surec = None
        self.metin.delete("giris", "end-1c")
        if self.metin.get("end-2c", "end-1c") not in ("\n", ""):
            self._yaz("\n", "sistem")
        sure = time.monotonic() - self.baslangic
        if self.durduruldu:
            self._durum("Durduruldu", "uyari")
            self._yaz(f"\n── Program durduruldu · {sure:.2f} sn ", "uyari")
        elif kod == 0:
            self._durum("Tamamlandı", "basari")
            self._yaz(f"\n── Program tamamlandı · {sure:.2f} sn ", "basari")
        else:
            self._durum("Hata" if kod == 1 else f"Çıkış kodu {kod}", "hata")
            self._yaz(f"\n── Program {kod} koduyla sonlandı · {sure:.2f} sn ", "hata")
        self._yaz("── F5: yeniden başlat · Esc: kapat\n", "sistem")

    def durdur(self):
        if self._calisiyor():
            self.durduruldu = True
            _agaci_sonlandir(self.surec.pid)

    def yeniden(self):
        self.nesil += 1
        if self._calisiyor():
            _agaci_sonlandir(self.surec.pid)
        self.surec = None
        self.metin.delete("1.0", "end")
        self.metin.mark_set("giris", "end-1c")
        self.baslat()

    def kapat(self):
        self.nesil += 1
        if self._calisiyor():
            _agaci_sonlandir(self.surec.pid)
        self.kok.destroy()

    def calistir(self):
        self.kok.after(10, self.baslat)
        self.kok.after(25, self._kuyrugu_bosalt)
        self.kok.mainloop()
        return self.cikis_kodu


# ----------------------------------------------------------------------
# Windows konsolu
# ----------------------------------------------------------------------
def _ctrl_c_yakala(*olaylar):
    """Konsolda Ctrl+C / Ctrl+Break basılınca olayları kurar, bu süreci
    kapatmaz. Windows bu işlevi ayrı bir iş parçacığında hemen çağırır
    (Python'un sinyal işleyicisi ise ana iş parçacığı borudan okurken
    bekler). Geri çağrı nesnesi döndürülür; çöp toplanmasın diye saklanmalı."""
    import ctypes
    from ctypes import wintypes

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    def isleyici(tur):
        if tur in (0, 1):  # CTRL_C_EVENT, CTRL_BREAK_EVENT
            for olay in olaylar:
                olay.set()
            return True
        return False

    ctypes.windll.kernel32.SetConsoleCtrlHandler(isleyici, True)
    return isleyici


def konsolda_calistir(ayar):
    """Windows konsolu kipi: program aynı konsolda, ikinci bir süreçte çalışır;
    çıktısı bu süreçten geçerken Türkçeleştirilip konsola yazılır, konsola
    yazılanlar programın girdisine aktarılır. Çıkış kodu döndürür.

    Ctrl+C aynı konsoldaki programa da gider: program bir şey hesaplıyorsa
    kendisi "[Program durduruldu (Ctrl+C)]" yazıp kapanır. Girdi bekliyorsa
    (borudan okurken Ctrl+C'yi göremez) kısa bir beklemeden sonra bu süreç
    onu kapatır ve aynı iletiyi yazar. Eskiden Ctrl+C girdinin bittiği
    sanılıyor, program yanlış bir "Dosya Sonu Hatası" veriyordu."""
    ctrl_c = threading.Event()            # izleyici iş parçacığı için
    ctrl_c_okuyucu = threading.Event()    # girdi aktaran iş parçacığı için
    try:
        _isleyici = _ctrl_c_yakala(ctrl_c, ctrl_c_okuyucu)  # noqa: F841 - çöp toplanmasın
    except Exception:  # noqa: BLE001
        import signal
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleTitleW(ayar.get("ad") or "Program")
    except Exception:  # noqa: BLE001
        pass
    cikis = sys.stdout
    try:
        cikis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    kilit = threading.Lock()

    def yaz(metin):
        with kilit:
            try:
                cikis.write(metin)
                cikis.flush()
            except Exception:  # noqa: BLE001
                pass

    env = dict(os.environ)
    env["TURKOD_EXE_COCUK"] = "1"
    try:
        surec = subprocess.Popen(
            [sys.executable, *sys.argv[1:]], env=env,
            cwd=os.path.dirname(os.path.abspath(sys.executable)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    except OSError as e:
        yaz(f"[HATA] Program başlatılamadı: {e}\n")
        return 1

    bitti = threading.Event()
    enter_basildi = threading.Event()
    durduruldu = threading.Event()
    konsol_mu = sys.stdin is not None and sys.stdin.isatty()

    def ctrl_c_izle():
        while not bitti.is_set():
            if not ctrl_c.wait(0.2):
                continue
            ctrl_c.clear()
            if bitti.is_set():
                return
            # Program hesap yaparken Ctrl+C'yi kendisi alır ve kapanır.
            for _ in range(15):
                if surec.poll() is not None:
                    return
                time.sleep(0.1)
            durduruldu.set()
            _agaci_sonlandir(surec.pid)
            return

    def girdi_aktar():
        son_ctrl_c = -10.0
        while True:
            try:
                satir = sys.stdin.readline() if sys.stdin is not None else ""
            except Exception:  # noqa: BLE001
                satir = ""
            # Konsolda Ctrl+C okumayı boş satırla bitirir (hemen ardından bir
            # kez daha); bu, girdinin sonu da Enter da değildir. Ctrl+C olayı
            # okumadan biraz sonra gelebilir.
            if not satir and konsol_mu and (ctrl_c_okuyucu.wait(0.3)
                                            or time.monotonic() - son_ctrl_c < 1.0):
                if ctrl_c_okuyucu.is_set():
                    ctrl_c_okuyucu.clear()
                    son_ctrl_c = time.monotonic()
                continue
            if bitti.is_set():
                enter_basildi.set()
                return
            if not satir:
                try:
                    surec.stdin.close()
                except OSError:
                    pass
                enter_basildi.set()   # girdi kapandı: Enter da beklenemez
                return
            try:
                surec.stdin.write(satir.encode("utf-8"))
                surec.stdin.flush()
            except OSError:
                return

    okuyucu = threading.Thread(target=girdi_aktar, daemon=True)
    okuyucu.start()
    threading.Thread(target=ctrl_c_izle, daemon=True).start()
    cevirici = SatirCevirici(yaz) if SatirCevirici else None
    cozucu = codecs.getincrementaldecoder("utf-8")("replace")
    fd = surec.stdout.fileno()
    try:
        while True:
            ham = os.read(fd, 8192)
            if not ham:
                break
            parca = cozucu.decode(ham)
            if parca:
                cevirici.besle(parca) if cevirici else yaz(parca)
    except OSError:
        pass
    if cevirici:
        cevirici.bitir()
    kod = surec.wait()
    bitti.set()
    if durduruldu.is_set():
        yaz("\n[Program durduruldu (Ctrl+C)]\n")
        kod = 130
    if ayar.get("sonda_bekle") and konsol_mu:
        yaz("\nKapatmak için Enter'a basın...")
        enter_basildi.wait()   # okuyucu iş parçacığı Enter'ı bekliyor
    return kod


def calistir(ayar, kaynak=None):
    _dpi_farkinda_ol()
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "TurKod.Exe." + re.sub(r"\W", "", ayar.get("ad") or "Program"))
    except Exception:  # noqa: BLE001
        pass
    return ExeTerminali(ayar, kaynak).calistir()
