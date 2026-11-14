"""TürKod Yerel AI sunucusu (llama-cpp-python).

Backend bu betiği, yerel AI motorunun kurulu olduğu Python ile ayrı bir süreç
olarak başlatır (paketli sürümde betik _internal klasöründen okunur). Yalnızca
standart kütüphane ve llama_cpp kullanır; OpenAI uyumlu küçük bir HTTP arayüzü
sunar:

    GET  /saglik               durum (sürüm, GPU desteği, yüklü modeller)
    GET  /v1/models            model klasörlerindeki .gguf dosyaları
    POST /v1/chat/completions  sohbet (model = .gguf dosya adı)
    POST /v1/completions       tamamlama; "suffix" ile ortadan doldurma

Modeller ilk istekte belleğe yüklenir; en fazla --azami-model kadarı bellekte
tutulur (en eski kullanılan çıkarılır). llama.cpp aynı anda tek istek işler.

Kullanım:
    python yerel_sunucu.py --paket <motor klasörü> --modeller <klasör;klasör>
                           --port 8765 [--gpu] [--vram 6.0] [--ebeveyn PID]
                           [--baglam 12288]   (bağlam üst sınırı)
"""
import argparse
import gc
import json
import os
import sys
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Eğitim bağlamı bilinmeyen model bu bağlamla açılır.
VARSAYILAN_BAGLAM = 8192


# ----------------------------------------------------------------------
# GGUF başlığı (bağımlılıksız): yalnızca anahtar-değer bölümü okunur.
# ----------------------------------------------------------------------
_GGUF_SABIT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
               7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


def gguf_meta(yol, anahtarlar=None, azami_kv=4096):
    """GGUF (v2/v3) başlığındaki sayı / metin değerleri: {anahtar: değer}.
    Diziler atlanır. anahtarlar verilirse hepsi bulununca okuma biter.
    Bozuk ya da okunamayan dosyada o ana kadar okunanlar döner."""
    import struct
    sonuc = {}
    try:
        with open(yol, "rb") as f:
            def oku(n):
                b = f.read(n)
                if len(b) != n:
                    raise EOFError
                return b

            def sabit(tur):
                bicim = _GGUF_SABIT[tur]
                return struct.unpack(bicim, oku(struct.calcsize(bicim)))[0]

            def metin(sinir=1 << 20):
                n = struct.unpack("<Q", oku(8))[0]
                if n > sinir:
                    raise ValueError("metin çok uzun")
                return oku(n).decode("utf-8", "replace")

            def atla(tur):
                if tur in _GGUF_SABIT:
                    f.seek(struct.calcsize(_GGUF_SABIT[tur]), 1)
                elif tur == 8:
                    n = struct.unpack("<Q", oku(8))[0]
                    f.seek(n, 1)
                elif tur == 9:
                    ic, adet = struct.unpack("<IQ", oku(12))
                    if ic in _GGUF_SABIT:
                        f.seek(struct.calcsize(_GGUF_SABIT[ic]) * adet, 1)
                    else:
                        for _ in range(adet):
                            atla(ic)
                else:
                    raise ValueError(f"bilinmeyen tür {tur}")

            if oku(4) != b"GGUF":
                return sonuc
            surum = struct.unpack("<I", oku(4))[0]
            if surum < 2:
                return sonuc  # v1 (32 bit sayılar) artık kullanılmıyor
            _, kv_sayisi = struct.unpack("<QQ", oku(16))
            for _ in range(min(kv_sayisi, azami_kv)):
                anahtar = metin(1 << 16)
                tur = struct.unpack("<I", oku(4))[0]
                if tur in _GGUF_SABIT:
                    sonuc[anahtar] = sabit(tur)
                elif tur == 8:
                    sonuc[anahtar] = metin()
                else:
                    atla(tur)
                if anahtarlar and all(a in sonuc for a in anahtarlar(sonuc)):
                    break
    except Exception:  # noqa: BLE001 - bozuk / yarım dosya
        pass
    return sonuc


def gguf_baglam(yol):
    """Modelin eğitildiği bağlam uzunluğu ('<mimari>.context_length'); yoksa None."""
    meta = gguf_meta(yol, anahtarlar=lambda m: [
        "general.architecture", f"{m.get('general.architecture', '?')}.context_length"])
    mimari = meta.get("general.architecture")
    deger = meta.get(f"{mimari}.context_length") if mimari else None
    try:
        deger = int(deger)
    except (TypeError, ValueError):
        return None
    return deger if deger > 0 else None


def model_baglami(yol):
    """Modelin açılacağı bağlam: eğitim bağlamı ile --baglam sınırının küçüğü."""
    sinir = max(512, int(getattr(ARG, "baglam", 0) or VARSAYILAN_BAGLAM))
    egitim = gguf_baglam(yol)
    return min(egitim or VARSAYILAN_BAGLAM, sinir)


# ----------------------------------------------------------------------
# CUDA çalışma kitaplıkları (cudart, cublas): llama-cpp-python'un CUDA
# paketi bunları içermez. Motorla birlikte nvidia-* paketlerinden kurulur
# (motor klasöründe nvidia/<ad>/bin) ya da CUDA Toolkit'ten (CUDA_PATH) gelir.
# ----------------------------------------------------------------------
_DLL_TUTAMACLARI = []


def cuda_dll_dizinleri(paket):
    dizinler = []
    kok = os.path.join(paket, "nvidia")
    if os.path.isdir(kok):
        for d, _, dosyalar in os.walk(kok):
            if any(x.lower().endswith(".dll") for x in dosyalar):
                dizinler.append(d)
    cuda = os.environ.get("CUDA_PATH")
    if cuda and os.path.isdir(os.path.join(cuda, "bin")):
        dizinler.append(os.path.join(cuda, "bin"))
    return dizinler


def dll_dizinlerini_ekle(paket):
    """CUDA DLL klasörlerini arama yoluna ekler ve kitaplıkları önceden
    yükler (llama.dll bağımlılıklarını adlarıyla bulabilsin)."""
    dizinler = cuda_dll_dizinleri(paket)
    for d in dizinler:
        try:
            _DLL_TUTAMACLARI.append(os.add_dll_directory(d))
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    if os.name == "nt":
        import ctypes
        for d in dizinler:
            if not os.path.abspath(d).startswith(os.path.abspath(paket)):
                continue  # Toolkit'in tüm DLL'leri önceden yüklenmez
            for ad in sorted(os.listdir(d)):
                k = ad.lower()
                if k.endswith(".dll") and k.startswith(("cudart", "cublaslt", "cublas")):
                    try:
                        _DLL_TUTAMACLARI.append(ctypes.WinDLL(os.path.join(d, ad)))
                    except OSError:
                        pass
    return dizinler


def _arglar(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--paket", required=True)
    p.add_argument("--modeller", required=True)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--gpu", action="store_true")
    p.add_argument("--vram", type=float, default=0.0)
    # Üst sınır (backend RAM'e göre verir). Eskiden her model 4096 ile açılıyor,
    # Kodi isteği (~5-6K + 2K cevap) "context length exceeded" veriyordu.
    p.add_argument("--baglam", type=int, default=VARSAYILAN_BAGLAM)
    p.add_argument("--azami-model", type=int, default=2)
    p.add_argument("--ebeveyn", type=int, default=0)
    return p.parse_args(argv)


ARG = None
llama_cpp = None
_YUKLU = OrderedDict()           # yol -> Llama
_YUKLEME_KILIDI = threading.Lock()
_CIKARIM_KILIDI = threading.Lock()


def model_klasorleri():
    return [d for d in ARG.modeller.split(os.pathsep) if d]


def model_listesi():
    gorulen, sonuc = set(), []
    for d in model_klasorleri():
        try:
            adlar = sorted(os.listdir(d))
        except OSError:
            continue
        for ad in adlar:
            if ad.lower().endswith(".gguf") and ad not in gorulen:
                gorulen.add(ad)
                sonuc.append(ad)
    return sonuc


def model_yolu(ad):
    """Yalnızca model klasörlerindeki dosyalar açılabilir (yol geçişi yok)."""
    taban = os.path.basename(str(ad or ""))
    for d in model_klasorleri():
        yol = os.path.join(d, taban)
        if taban.lower().endswith(".gguf") and os.path.isfile(yol):
            return yol
    raise FileNotFoundError(f"model not found: {taban}")


def _gpu_katmani(yol):
    """Model ekran kartı belleğine sığıyorsa tüm katmanlar (-1), sığmıyorsa
    sığan oranda katman ekran kartına verilir; GPU yoksa 0."""
    if not ARG.gpu or ARG.vram <= 0:
        return 0
    boyut = os.path.getsize(yol) / 2**30
    if boyut + 0.8 <= ARG.vram:
        return -1
    try:
        meta = llama_cpp.Llama(model_path=yol, vocab_only=True, verbose=False).metadata
        mimari = meta.get("general.architecture", "")
        katman = int(meta.get(f"{mimari}.block_count", 0))
    except Exception:  # noqa: BLE001
        katman = 0
    if katman <= 0:
        return 0
    return max(0, int(katman * max(0.0, ARG.vram - 0.8) / boyut))


def model_al(ad):
    yol = model_yolu(ad)
    with _YUKLEME_KILIDI:
        if yol in _YUKLU:
            _YUKLU.move_to_end(yol)
            return _YUKLU[yol]
        while len(_YUKLU) >= max(1, ARG.azami_model):
            _, eski = _YUKLU.popitem(last=False)
            del eski
            gc.collect()
        llm = llama_cpp.Llama(model_path=yol, n_ctx=model_baglami(yol),
                              n_gpu_layers=_gpu_katmani(yol), verbose=False)
        _YUKLU[yol] = llm
        return llm


def _ortak(govde):
    kw = {}
    max_token = govde.get("max_tokens") or govde.get("max_completion_tokens")
    if max_token:
        kw["max_tokens"] = int(max_token)
    if govde.get("temperature") is not None:
        kw["temperature"] = float(govde["temperature"])
    if govde.get("stop"):
        kw["stop"] = govde["stop"]
    return kw


def sohbet(govde):
    llm = model_al(govde.get("model"))
    with _CIKARIM_KILIDI:
        return llm.create_chat_completion(messages=govde.get("messages") or [],
                                          **_ortak(govde))


def tamamla(govde):
    llm = model_al(govde.get("model"))
    kw = _ortak(govde)
    if govde.get("suffix"):
        kw["suffix"] = govde["suffix"]
    with _CIKARIM_KILIDI:
        try:
            return llm.create_completion(prompt=govde.get("prompt") or "", **kw)
        except Exception:  # noqa: BLE001 - modelin ortadan doldurma jetonu yoksa
            kw.pop("suffix", None)
            return llm.create_completion(prompt=govde.get("prompt") or "", **kw)


class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):  # sessiz
        pass

    def _yanit(self, kod, veri):
        ham = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(ham)))
        self.end_headers()
        self.wfile.write(ham)

    def _hata(self, kod, mesaj):
        self._yanit(kod, {"error": {"message": mesaj}})

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/saglik":
            self._yanit(200, {
                "ok": True, "surum": getattr(llama_cpp, "__version__", ""),
                "gpu": bool(llama_cpp.llama_supports_gpu_offload()) and ARG.gpu,
                "yuklu": [os.path.basename(y) for y in _YUKLU]})
        elif self.path.rstrip("/") == "/v1/models":
            self._yanit(200, {"object": "list", "data": [
                {"id": m, "object": "model", "owned_by": "turkod"} for m in model_listesi()]})
        else:
            self._hata(404, "not found")

    def do_POST(self):  # noqa: N802
        try:
            uzunluk = int(self.headers.get("Content-Length") or 0)
            govde = json.loads(self.rfile.read(uzunluk) or b"{}")
        except ValueError:
            return self._hata(400, "invalid json")
        yol = self.path.rstrip("/")
        try:
            if yol == "/v1/chat/completions":
                return self._yanit(200, sohbet(govde))
            if yol == "/v1/completions":
                return self._yanit(200, tamamla(govde))
            return self._hata(404, "not found")
        except FileNotFoundError as e:
            return self._hata(404, str(e))
        except ValueError as e:
            # llama.cpp: "Requested tokens exceed context window"
            return self._hata(400, f"context length exceeded: {e}")
        except MemoryError:
            return self._hata(500, "model belleğe sığmadı (out of memory)")
        except Exception as e:  # noqa: BLE001
            return self._hata(500, f"{type(e).__name__}: {e}")


def _ebeveyni_izle(pid):
    """Backend kapanınca (çökse bile) sunucu da kapanır."""
    if not pid:
        return

    def yasiyor():
        if os.name == "nt":
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            kod = ctypes.c_ulong()
            k32.GetExitCodeProcess(h, ctypes.byref(kod))
            k32.CloseHandle(h)
            return kod.value == 259  # STILL_ACTIVE
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def dongu():
        while True:
            time.sleep(2)
            if not yasiyor():
                os._exit(0)

    threading.Thread(target=dongu, daemon=True).start()


def main(argv=None):
    global ARG, llama_cpp
    ARG = _arglar(argv)
    sys.path.insert(0, ARG.paket)
    # CUDA paketi: cudart / cublas DLL'leri llama.dll'den önce bulunabilmeli
    # (eskiden CUDA Toolkit kurulu değilse motor hiç açılmıyordu).
    dll_dizinlerini_ekle(ARG.paket)
    import llama_cpp as _llama_cpp
    llama_cpp = _llama_cpp
    _ebeveyni_izle(ARG.ebeveyn)
    sunucu = ThreadingHTTPServer(("127.0.0.1", ARG.port), Isleyici)
    print(json.dumps({"hazir": True, "port": sunucu.server_address[1],
                      "surum": getattr(llama_cpp, "__version__", ""),
                      "gpu": bool(llama_cpp.llama_supports_gpu_offload())}), flush=True)
    sunucu.serve_forever()


if __name__ == "__main__":
    main()
