"""TürKod hata ayıklayıcısı (debugger).

Eski sürüm (Tkinter'a bağlı "BasitDebugger") kodu hiç çalıştırmıyordu: yalnızca
breakpoint'ler arasında vurguyu gezdiriyordu. Bu modül gerçek, satır satır bir
hata ayıklayıcı sağlar:

* Kod Python'a çevrilir (satırlar birebir korunur) ve kullanıcının Python'unda
  ``bdb`` tabanlı bir çalıştırıcıyla (DEBUG_RUNNER_KODU) başlatılır.
* IDE ile çalıştırıcı 127.0.0.1 üzerindeki bir TCP soketinden, satır başına
  bir JSON mesajla konuşur. Programın kendi çıktısı / girdisi normal
  stdout / stdin'den akar (terminal paneli aynen çalışır).
* Desteklenenler: breakpoint, devam, adım at (üzerinden), içine gir, dışına
  çık, duraklat, durdur; her duruşta yerel / küresel değişkenler (liste,
  sözlük ve nesneler için alt elemanlarla) ve çağrı yığını.
"""
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading

try:
    from .runner import RUNNER_ORTAK
except ImportError:
    from runner import RUNNER_ORTAK


# argv: <port> <token> <kod_dosyasi> <ilk_satirda_dur 0|1> <bp1,bp2,...>
#
# Gelen komutlar : devam | adim | icine | disina | duraklat | durdur |
#                  bp (satirlar=[...])
# Giden olaylar  : merhaba, breakpointler, durdu, devam_ediyor, hata
DEBUG_RUNNER_KODU = RUNNER_ORTAK + r'''
import bdb
import dis
import json
import queue
import socket
import threading
import types

_PORT = int(sys.argv[1])
_TOKEN = sys.argv[2]
_KOD_DOSYASI = os.path.abspath(sys.argv[3])
_ILK_SATIRDA_DUR = sys.argv[4] == "1"
_ILK_BPLER = [int(x) for x in (sys.argv[5] if len(sys.argv) > 5 else "").split(",")
              if x.strip().isdigit()]

_sock = socket.create_connection(("127.0.0.1", _PORT), timeout=15)
_sock.settimeout(None)
_rf = _sock.makefile("r", encoding="utf-8", newline="\n")
_wf = _sock.makefile("w", encoding="utf-8", newline="\n")
_yaz_kilit = threading.Lock()
_komutlar = queue.Queue()


def _gonder(veri):
    try:
        with _yaz_kilit:
            _wf.write(json.dumps(veri, ensure_ascii=False) + "\n")
            _wf.flush()
    except Exception:
        pass


TIP_ADLARI = {
    "int": "tamsayı", "float": "ondalıklı", "str": "metin", "bool": "mantıksal",
    "list": "liste", "dict": "sözlük", "tuple": "demet", "set": "küme",
    "frozenset": "donmuş_küme", "NoneType": "Hiçlik", "function": "fonksiyon",
    "builtin_function_or_method": "yerleşik_fonksiyon", "type": "sınıf",
    "method": "metot", "complex": "karmaşık", "bytes": "bayt", "range": "aralık",
    "generator": "üreteç", "module": "modül",
}


def _tip_adi(deger):
    ad = type(deger).__name__
    return TIP_ADLARI.get(ad, ad)


def _deger_metni(deger, sinir=300):
    try:
        if isinstance(deger, (bool, type(None))):
            metin = _turkcelestir(deger)
        else:
            metin = _turkcelestir(repr(deger))
    except Exception as e:
        metin = f"<gösterilemedi: {type(e).__name__}>"
    if len(metin) > sinir:
        metin = metin[:sinir] + " …"
    return metin


def _cocuklar(deger, sinir=100):
    """Liste / sözlük / nesne gibi değerlerin ilk elemanları."""
    try:
        if isinstance(deger, dict):
            return [{"ad": _deger_metni(k, 60), "tip": _tip_adi(v), "deger": _deger_metni(v)}
                    for k, v in list(deger.items())[:sinir]]
        if isinstance(deger, (list, tuple)):
            return [{"ad": f"[{i}]", "tip": _tip_adi(v), "deger": _deger_metni(v)}
                    for i, v in enumerate(deger[:sinir])]
        if isinstance(deger, (set, frozenset)):
            return [{"ad": "•", "tip": _tip_adi(v), "deger": _deger_metni(v)}
                    for v in list(deger)[:sinir]]
        sozluk = getattr(deger, "__dict__", None)
        if (isinstance(sozluk, dict)
                and not isinstance(deger, (type, types.ModuleType, types.FunctionType))):
            return [{"ad": k, "tip": _tip_adi(v), "deger": _deger_metni(v)}
                    for k, v in list(sozluk.items())[:sinir] if not k.startswith("__")]
    except Exception:
        pass
    return None


_GIZLI_KURESELLER = set()


def _degiskenler(ad_alani, kuresel_mi=False):
    sonuc = []
    for ad, deger in list(ad_alani.items()):
        if ad.startswith("__") or ad.startswith("_tk_"):
            continue
        if isinstance(deger, types.ModuleType):
            continue
        if kuresel_mi and ad in _GIZLI_KURESELLER:
            continue
        oge = {"ad": ad, "tip": _tip_adi(deger), "deger": _deger_metni(deger)}
        cocuk = _cocuklar(deger)
        if cocuk:
            oge["cocuklar"] = cocuk
            try:
                oge["uzunluk"] = len(deger)
            except Exception:
                oge["uzunluk"] = len(cocuk)
        sonuc.append(oge)
        if len(sonuc) >= 300:
            break
    return sonuc


def _calistirilabilir_satirlar(kod_nesnesi):
    satirlar = set()
    yigin = [kod_nesnesi]
    while yigin:
        k = yigin.pop()
        for _, satir in dis.findlinestarts(k):
            if satir:
                satirlar.add(satir)
        for sabit in k.co_consts:
            if isinstance(sabit, types.CodeType):
                yigin.append(sabit)
    return satirlar


class TurKodDebugger(bdb.Bdb):
    def __init__(self, dosya, calisabilir):
        super().__init__()
        self.dosya = self.canonic(dosya)
        self.calisabilir = sorted(calisabilir)
        self.ilk = True
        self.duraklat_istegi = False
        self.durdurma_istegi = False

    # --- breakpoint yönetimi ------------------------------------------
    def _gecerli_satir(self, satir):
        """Boş / yorum satırındaki breakpoint sonraki çalıştırılabilir satıra kayar."""
        for s in self.calisabilir:
            if s >= satir:
                return s
        return None

    def bp_ayarla(self, satirlar):
        self.clear_all_file_breaks(self.dosya)
        eslesme = {}
        for s in sorted(set(int(x) for x in satirlar)):
            g = self._gecerli_satir(s)
            if g is None:
                continue
            eslesme[str(s)] = g
            if not self.get_break(self.dosya, g):
                self.set_break(self.dosya, g)
        _gonder({"tip": "breakpointler", "eslesme": eslesme,
                 "satirlar": sorted(set(eslesme.values()))})

    # bdb.set_continue, hiç breakpoint yoksa izlemeyi tamamen kapatır; o
    # durumda çalışma sırasında eklenen breakpoint'ler ve "Duraklat" bir daha
    # çalışmazdı. İzleme açık bırakılır.
    def set_continue(self):
        self._set_stopinfo(self.botframe, None, -1)

    # bdb, durulacak / breakpoint'i olan bir yer yoksa yeni çağrılan
    # fonksiyonları hiç izlemez. Bu yüzden breakpoint'siz çalışırken bir
    # fonksiyonun içindeki döngü "Duraklat" ile durdurulamıyordu. Kullanıcı
    # dosyasındaki çerçeveler her zaman izlenir (kütüphaneler izlenmez).
    def dispatch_call(self, frame, arg):
        sonuc = super().dispatch_call(frame, arg)
        if sonuc is None and not self.quitting and self._kullanici_dosyasi(frame):
            return self.trace_dispatch
        return sonuc

    # --- bdb geri çağrıları -------------------------------------------
    def _kullanici_dosyasi(self, frame):
        return self.canonic(frame.f_code.co_filename) == self.dosya

    def user_call(self, frame, argument_list):
        # Satır olayında durulur; çağrı olayında ayrıca durmak gereksiz.
        pass

    def user_return(self, frame, return_value):
        pass

    def user_exception(self, frame, exc_info):
        pass

    def user_line(self, frame):
        if self.durdurma_istegi:
            raise bdb.BdbQuit
        if not self._kullanici_dosyasi(frame):
            # Kütüphane kodunun içine girildi: çağıran kullanıcı satırına dön.
            self.set_return(frame)
            return
        neden = "adim"
        if self.ilk:
            self.ilk = False
            ilk_bp = bool(self.get_break(self.dosya, frame.f_lineno))
            if not _ILK_SATIRDA_DUR and not ilk_bp:
                self.set_continue()
                return
            neden = "breakpoint" if ilk_bp else "baslangic"
        if self.duraklat_istegi:
            self.duraklat_istegi = False
            neden = "duraklat"
        elif neden == "adim" and self.get_break(self.dosya, frame.f_lineno):
            neden = "breakpoint"
        self._dur(frame, neden)

    def _yigin(self, frame):
        cerceveler = []
        f = frame
        while f is not None:
            if self._kullanici_dosyasi(f):
                ad = f.f_code.co_name
                cerceveler.append({
                    "fonksiyon": "ana program" if ad == "<module>" else ad,
                    "satir": f.f_lineno,
                })
            if f is self.botframe:
                break
            f = f.f_back
        return cerceveler

    def _dur(self, frame, neden):
        modul_seviyesi = frame.f_code.co_name == "<module>"
        _gonder({
            "tip": "durdu",
            "satir": frame.f_lineno,
            "neden": neden,
            "fonksiyon": "ana program" if modul_seviyesi else frame.f_code.co_name,
            "yerel": [] if modul_seviyesi else _degiskenler(frame.f_locals),
            "kuresel": _degiskenler(frame.f_globals, kuresel_mi=True),
            "yigin": self._yigin(frame),
        })
        while True:
            mesaj = _komutlar.get()
            komut = mesaj.get("komut")
            if komut == "bp":
                self.bp_ayarla(mesaj.get("satirlar") or [])
                continue
            if komut == "durdur":
                raise bdb.BdbQuit
            if komut == "adim":
                self.set_next(frame)
            elif komut == "icine":
                self.set_step()
            elif komut == "disina":
                self.set_return(frame)
            elif komut == "devam":
                self.set_continue()
            else:
                continue
            _gonder({"tip": "devam_ediyor"})
            return


def _okuyucu(dbg):
    """Soketten gelen komutları kuyruğa aktarır. Program çalışırken gelen
    'duraklat' ve 'durdur' hemen işlenir; 'bp' bir sonraki duruşu beklemeden
    uygulanır."""
    try:
        for satir in _rf:
            try:
                mesaj = json.loads(satir)
            except Exception:
                continue
            komut = mesaj.get("komut")
            if komut == "duraklat":
                dbg.duraklat_istegi = True
                dbg.set_step()
                continue
            if komut == "durdur":
                dbg.durdurma_istegi = True
            elif komut == "bp" and not dbg.durakladi:
                dbg.bp_ayarla(mesaj.get("satirlar") or [])
                continue
            _komutlar.put(mesaj)
    except Exception:
        pass
    # IDE bağlantısı koptu: programı beklemede bırakma.
    dbg.durdurma_istegi = True
    _komutlar.put({"komut": "durdur"})


def _calistir():
    with open(_KOD_DOSYASI, "r", encoding="utf-8") as f:
        kaynak = f.read()
    # Önce kimlik doğrulanır: eskiden sözdizimi hatası 'merhaba'dan önce
    # gönderiliyor, IDE bunu yabancı bağlantı sanıp kapatıyor ve hata satırı
    # arayüze hiç ulaşmıyordu.
    _gonder({"tip": "merhaba", "token": _TOKEN})
    try:
        kod_nesnesi = compile(kaynak, _KOD_DOSYASI, "exec")
    except SyntaxError as e:
        satir, ad, detay = _hata_yazdir(e, None, _KOD_DOSYASI)
        _gonder({"tip": "hata", "satir": satir, "mesaj": f"{ad}: {detay}"})
        return 1

    dbg = TurKodDebugger(_KOD_DOSYASI, _calistirilabilir_satirlar(kod_nesnesi))
    dbg.durakladi = False
    dbg.bp_ayarla(_ILK_BPLER)

    _eski_dur = dbg._dur

    def _dur_izle(frame, neden):
        dbg.durakladi = True
        try:
            _eski_dur(frame, neden)
        finally:
            dbg.durakladi = False

    dbg._dur = _dur_izle
    threading.Thread(target=_okuyucu, args=(dbg,), daemon=True).start()

    # Gerçek bir __main__ modülü: düz sözlükte pickle / unittest / doctest
    # kullanıcı sınıflarını bulamıyordu.
    _ana = types.ModuleType("__main__")
    _ana.__file__ = _KOD_DOSYASI
    _ana.__builtins__ = builtins
    sys.modules["__main__"] = _ana
    kuresel = _ana.__dict__
    _GIZLI_KURESELLER.update(kuresel.keys())
    try:
        dbg.run(kod_nesnesi, kuresel)
    except bdb.BdbQuit:
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except BaseException as e:
        tb = sys.exc_info()[2]
        satir, ad, detay = _hata_yazdir(e, tb, _KOD_DOSYASI)
        _gonder({"tip": "hata", "satir": satir, "mesaj": f"{ad}: {detay}"})
        return 1
    finally:
        sys.settrace(None)
    return 0


_cikis = 1
try:
    _cikis = _calistir()
finally:
    try:
        sys.stdout.flush()
    except Exception:
        pass
    try:
        _sock.close()
    except Exception:
        pass
sys.exit(_cikis)
'''


class DebugHatasi(Exception):
    pass


class DebugOturumu:
    """Tek bir hata ayıklama oturumu: soket sunucusu + çalıştırıcı süreci.

    Olaylar ``on_olay(ad, veri)`` ile bildirilir:
      ``debug_durdu``, ``debug_devam``, ``debug_breakpointler``, ``debug_hata``.
    Program çıktısı süreç stdout'undan okunur (bkz. IDECore._terminal_oku).
    """

    BAGLANTI_ZAMAN_ASIMI = 15

    def __init__(self, python_exe, python_kodu, breakpointler, ilk_satirda_dur,
                 env=None, popen_ek=None, on_olay=None):
        self.on_olay = on_olay
        self.durdu = False
        self.mevcut_satir = 0
        self.bitti = False
        self._yaz_kilit = threading.Lock()
        self._baglanti = None
        self._yazici = None
        self._token = secrets.token_hex(16)
        self.kimlik = secrets.token_hex(6)

        self._gecici_dizin = tempfile.mkdtemp(prefix="turkod_debug_")
        self.kod_yolu = os.path.join(self._gecici_dizin, "turkod_program.py")
        runner_yolu = os.path.join(self._gecici_dizin, "turkod_debug_runner.py")
        with open(self.kod_yolu, "w", encoding="utf-8") as f:
            f.write(python_kodu)
        with open(runner_yolu, "w", encoding="utf-8") as f:
            f.write(DEBUG_RUNNER_KODU)

        self._sunucu = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sunucu.bind(("127.0.0.1", 0))
        self._sunucu.listen(1)
        port = self._sunucu.getsockname()[1]

        bp_metni = ",".join(str(int(b)) for b in sorted(set(breakpointler)) if int(b) > 0)
        try:
            self.process = subprocess.Popen(
                [python_exe, "-X", "utf8", "-u", runner_yolu, str(port), self._token,
                 self.kod_yolu, "1" if ilk_satirda_dur else "0", bp_metni],
                cwd=self._gecici_dizin,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                **(popen_ek or {}),
            )
        except Exception:
            self._sunucu.close()
            raise

        threading.Thread(target=self._kabul_et, daemon=True,
                         name="turkod-debug-baglanti").start()

    # ------------------------------------------------------------------
    def _olay(self, ad, veri):
        if self.on_olay:
            try:
                self.on_olay(ad, veri)
            except Exception:
                pass

    def _kabul_et(self):
        try:
            self._sunucu.settimeout(self.BAGLANTI_ZAMAN_ASIMI)
            while True:
                baglanti, _ = self._sunucu.accept()
                baglanti.settimeout(self.BAGLANTI_ZAMAN_ASIMI)
                okuyucu = baglanti.makefile("r", encoding="utf-8", newline="\n")
                ilk = okuyucu.readline()
                try:
                    merhaba = json.loads(ilk)
                except Exception:
                    merhaba = {}
                if merhaba.get("tip") == "merhaba" and merhaba.get("token") == self._token:
                    break
                # Yabancı bağlantı (token yanlış): kapat, beklemeye devam et.
                baglanti.close()
            baglanti.settimeout(None)
            self._baglanti = baglanti
            self._yazici = baglanti.makefile("w", encoding="utf-8", newline="\n")
        except Exception:
            # Program, debugger'a bağlanamadan bitti (ör. sözdizimi hatası)
            # ya da zaman aşımı: çıktı/çıkış olayı zaten süreçten gelir.
            return
        finally:
            try:
                self._sunucu.close()
            except Exception:
                pass

        try:
            for satir in okuyucu:
                try:
                    mesaj = json.loads(satir)
                except Exception:
                    continue
                self._mesaj_isle(mesaj)
        except Exception:
            pass
        finally:
            self.durdu = False
            self.bitti = True

    def _mesaj_isle(self, mesaj):
        tip = mesaj.get("tip")
        if tip == "durdu":
            self.durdu = True
            self.mevcut_satir = int(mesaj.get("satir") or 0)
            self._olay("debug_durdu", mesaj)
        elif tip == "devam_ediyor":
            self.durdu = False
            self._olay("debug_devam", {})
        elif tip == "breakpointler":
            self._olay("debug_breakpointler", mesaj)
        elif tip == "hata":
            self._olay("debug_hata", mesaj)

    # ------------------------------------------------------------------
    def komut(self, komut, **ek):
        if self.bitti or self.process.poll() is not None:
            raise DebugHatasi("Hata ayıklama oturumu sona erdi.")
        if self._yazici is None:
            raise DebugHatasi("Debugger henüz programa bağlanmadı.")
        veri = {"komut": komut}
        veri.update(ek)
        with self._yaz_kilit:
            self._yazici.write(json.dumps(veri, ensure_ascii=False) + "\n")
            self._yazici.flush()

    def kapat(self):
        self.bitti = True
        try:
            if self._baglanti is not None:
                self._baglanti.close()
        except Exception:
            pass
        try:
            self._sunucu.close()
        except Exception:
            pass

    def temizle(self):
        """Süreç bittikten sonra geçici dosyaları siler."""
        self.kapat()
        try:
            import shutil
            shutil.rmtree(self._gecici_dizin, ignore_errors=True)
        except Exception:
            pass
