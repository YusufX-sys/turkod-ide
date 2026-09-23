"""TürKod backend sunucusu.

Çalıştırma:
    python server.py

veya üst klasörden:
    python -m turkod_ide.server

EXE modunda:
    TurKodIDE.exe --backend
"""

import os
import sys
import argparse

# ------------------------------------------------------------------
# Bootstrap / EXE entry point:
# --backend argümanı verilmişse FastAPI sunucusunu doğrudan başlat.
# EXE modunda (sys.frozen): --backend YOKSA kendini --backend ile yeniden başlatır.
# ------------------------------------------------------------------
if (__name__ == "__main__" and __package__ in (None, "")
        and not getattr(sys, "frozen", False)):
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _parent, _pkg = os.path.dirname(_this_dir), os.path.basename(_this_dir)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    import runpy
    runpy.run_module(f"{_pkg}.server", run_name="__main__")
    raise SystemExit(0)

import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

try:
    from .ide_core import IDECore
except ImportError:
    from ide_core import IDECore


app = FastAPI(title="TürKod Backend")
core = IDECore()


# ------------------------------------------------------------------
# Yardımcılar
# ------------------------------------------------------------------
async def _send_json(ws: WebSocket, payload: dict):
    try:
        await ws.send_json(payload)
    except Exception:
        pass


def _thread_event_sender(ws: WebSocket, loop: asyncio.AbstractEventLoop, event: str):
    def send(data):
        async def _send():
            await _send_json(ws, {"event": event, "data": data})

        try:
            asyncio.run_coroutine_threadsafe(_send(), loop)
        except RuntimeError:
            pass

    return send


# ------------------------------------------------------------------
# Senkron komutlar
# ------------------------------------------------------------------
def _cmd_ping(params):
    return {"pong": True, "zaman": time.time()}


def _cmd_ayar_get(params):
    return core.ayar_get(params["anahtar"])


def _cmd_ayar_set(params):
    return core.ayar_set(params["anahtar"], params.get("deger"))


def _cmd_ayarlar_tumu(params):
    return core.ayarlar_tumu()


def _cmd_proje_dizini_set(params):
    return core.proje_dizini_set(params.get("dizin"))


def _cmd_dosya_oku(params):
    return core.dosya_oku(params["yol"])


def _cmd_dosya_kaydet(params):
    return core.dosya_kaydet(params.get("yol"), params.get("icerik", ""))


def _cmd_dosya_agaci(params):
    return core.dosya_agaci(params.get("dizin"))


def _cmd_oturum_oku(params):
    return core.oturum_oku()


def _cmd_oturum_kaydet(params):
    return core.oturum_kaydet(
        params.get("sekmeler", []),
        params.get("aktif_sira", 0),
    )


def _cmd_kodu_cevir(params):
    return core.kodu_cevir(params.get("kod", ""))


def _cmd_kod_arama_cevir(params):
    return core.kod_arama_cevir(params.get("giris", ""))


def _cmd_istatistik(params):
    return core.istatistik_hesapla(params.get("kod", ""))


def _cmd_todo_bul(params):
    return core.todo_bul(params.get("kod", ""))


def _cmd_fold_bolgeleri(params):
    return core.fold_bolgeleri_bul(params.get("kod", ""))


def _cmd_tokenize(params):
    return core.tokenize_kod(params.get("kod", ""))


def _cmd_syntax_kontrol(params):
    return core.syntax_kontrol(params.get("kod", ""))


def _cmd_tamamlama_onerileri(params):
    return core.tamamlama_onerileri(
        params.get("kelime", ""),
        params.get("kod", ""),
    )


def _cmd_kod_tanimlari(params):
    return core.kod_tanimlari(params.get("kod", ""))


def _cmd_sozluk_verileri(params):
    return core.sozluk_verileri()


def _cmd_sistem_fontlari(params):
    return core.sistem_fontlari()


def _cmd_ai_modelleri(params):
    return core.ai_modelleri()


def _cmd_ai_modelleri_guncelle(params):
    return core.modelleri_guncelle()


def _cmd_ai_model_dogrula(params):
    return core.model_dogrula()


def _cmd_ai_sor(params):
    return core.ai_sor(params.get("mesaj", ""), params.get("kod"))


def _cmd_ai_kodu_acikla(params):
    return core.ai_kodu_acikla(params.get("kod", ""))


def _cmd_ai_kodu_optimize(params):
    return core.ai_kodu_optimize(params.get("kod", ""))


def _cmd_ai_temizle(params):
    return core.ai_temizle()


def _cmd_calistir_durdur(params):
    return core.kodu_durdur()


def _cmd_imza_dogrula(params):
    return core.imza_dogrula()


def _cmd_dosya_hash(params):
    return core.dosya_hash()


def _cmd_breakpoint_toggle(params):
    return core.breakpoint_toggle(params.get("satir"))


def _cmd_breakpoint_list(params):
    return core.breakpoint_list()


def _cmd_debug_baslat(params):
    return core.debug_baslat(params.get("kod", ""))


def _cmd_debug_adim(params):
    return core.debug_adim()


def _cmd_debug_devam(params):
    return core.debug_devam()


def _cmd_debug_durdur(params):
    return core.debug_durdur()


SYNC_COMMANDS = {
    "ping": _cmd_ping,
    "ayar_get": _cmd_ayar_get,
    "ayar_set": _cmd_ayar_set,
    "ayarlar_tumu": _cmd_ayarlar_tumu,
    "proje_dizini_set": _cmd_proje_dizini_set,
    "dosya_oku": _cmd_dosya_oku,
    "dosya_kaydet": _cmd_dosya_kaydet,
    "dosya_agaci": _cmd_dosya_agaci,
    "oturum_oku": _cmd_oturum_oku,
    "oturum_kaydet": _cmd_oturum_kaydet,
    "kodu_cevir": _cmd_kodu_cevir,
    "kod_arama_cevir": _cmd_kod_arama_cevir,
    "istatistik": _cmd_istatistik,
    "todo_bul": _cmd_todo_bul,
    "fold_bolgeleri": _cmd_fold_bolgeleri,
    "tokenize": _cmd_tokenize,
    "syntax_kontrol": _cmd_syntax_kontrol,
    "tamamlama_onerileri": _cmd_tamamlama_onerileri,
    "kod_tanimlari": _cmd_kod_tanimlari,
    "sozluk_verileri": _cmd_sozluk_verileri,
    "sistem_fontlari": _cmd_sistem_fontlari,
    "ai_modelleri": _cmd_ai_modelleri,
    "ai_modelleri_guncelle": _cmd_ai_modelleri_guncelle,
    "ai_model_dogrula": _cmd_ai_model_dogrula,
    "ai_sor": _cmd_ai_sor,
    "ai_kodu_acikla": _cmd_ai_kodu_acikla,
    "ai_kodu_optimize": _cmd_ai_kodu_optimize,
    "ai_temizle": _cmd_ai_temizle,
    "calistir_durdur": _cmd_calistir_durdur,
    "imza_dogrula": _cmd_imza_dogrula,
    "dosya_hash": _cmd_dosya_hash,
    "breakpoint_toggle": _cmd_breakpoint_toggle,
    "breakpoint_list": _cmd_breakpoint_list,
    "debug_baslat": _cmd_debug_baslat,
    "debug_adim": _cmd_debug_adim,
    "debug_devam": _cmd_debug_devam,
    "debug_durdur": _cmd_debug_durdur,
}
try:
    from . import updater
except ImportError:
    import updater

SYNC_COMMANDS["guncelleme_kontrol"] = lambda params: updater.kontrol_et()
SYNC_COMMANDS["guncelleme_indir"] = lambda params: updater.indir_ve_dogrula()
SYNC_COMMANDS["guncelleme_indir_baslat"] = lambda params: updater.indir_baslat()
SYNC_COMMANDS["guncelleme_indir_durum"] = lambda params: updater.indir_durum()

# ------------------------------------------------------------------
# Özel asenkron komutlar
# ------------------------------------------------------------------
async def _cmd_duzelt(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    progress = _thread_event_sender(ws, loop, "duzelt_progress")

    def _progress(metin):
        progress({"metin": metin})

    result = await asyncio.to_thread(
        core.duzelt_kod,
        params.get("kod", ""),
        _progress,
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


async def _cmd_calistir(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "calistirma_cikti")
    exit_ev = _thread_event_sender(ws, loop, "calistirma_bitti")

    def _output(metin):
        output({"metin": metin})

    def _exit(cikis_kodu):
        exit_ev({"cikis_kodu": cikis_kodu})

    result = await asyncio.to_thread(
        core.kodu_calistir,
        params.get("kod", ""),
        _output,
        _exit,
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


async def _cmd_terminal_komut(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "terminal_cikti")

    def _output(metin):
        output({"metin": metin})

    result = await asyncio.to_thread(
        core.terminal_komut,
        params.get("komut", ""),
        _output,
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


# ------------------------------------------------------------------
# WebSocket handler
# ------------------------------------------------------------------
async def _handle_message(ws: WebSocket, raw: str):
    try:
        msg = json.loads(raw)
    except Exception:
        await _send_json(ws, {
            "id": None,
            "ok": False,
            "error": "Geçersiz JSON.",
        })
        return

    msg_id = msg.get("id")
    command = msg.get("command")
    params = msg.get("params") or {}

    if not command:
        await _send_json(ws, {
            "id": msg_id,
            "ok": False,
            "error": "command alanı yok.",
        })
        return

    try:
        if command == "duzelt":
            await _cmd_duzelt(ws, msg_id, params)
            return

        if command == "calistir":
            await _cmd_calistir(ws, msg_id, params)
            return

        if command == "terminal_komut":
            await _cmd_terminal_komut(ws, msg_id, params)
            return

        handler = SYNC_COMMANDS.get(command)

        if handler is None:
            await _send_json(ws, {
                "id": msg_id,
                "ok": False,
                "error": f"Bilinmeyen komut: {command}",
            })
            return

        result = await asyncio.to_thread(handler, params)

        # ÖNEMLİ: Önceden "ok" burada koşulsuz True gönderiliyordu; bir
        # komut kendi içinde {"ok": False, "hata": "..."} döndürse bile
        # istemci bunu "başarılı" sanıyor, asıl hata mesajı hiç iletilmiyordu.
        # Artık komutun kendi "ok" değeri (varsa) üst seviyeye de yansıtılıyor.
        ok = result.get("ok", True) if isinstance(result, dict) else True

        await _send_json(ws, {
            "id": msg_id,
            "ok": bool(ok),
            "result": result,
        })

    except KeyError as e:
        await _send_json(ws, {
            "id": msg_id,
            "ok": False,
            "error": f"Eksik parametre: {e}",
        })
    except Exception as e:
        await _send_json(ws, {
            "id": msg_id,
            "ok": False,
            "error": str(e),
        })


@app.get("/")
def index():
    return {
        "servis": "TürKod Backend",
        "ws": "/ws",
        "komutlar": sorted(SYNC_COMMANDS.keys()) + [
            "calistir",
            "duzelt",
            "terminal_komut",
        ],
    }


@app.get("/komutlar")
def komutlar():
    return {
        "sync": sorted(SYNC_COMMANDS.keys()),
        "async": ["calistir", "duzelt", "terminal_komut"],
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if ws.headers.get("origin"):
        await ws.close(code=1008)
        return
    await ws.accept()

    # ------------------------------------------------------------------
    # ÖNEMLİ: Önceden burada `await _handle_message(ws, raw)` ile mesajlar
    # SIRAYLA işleniyordu. Bu, tek bir uzun süren komut (ör. bir AI isteği
    # ya da "Gelişmiş Düzeltme") devam ederken, o sırada gönderilen HER
    # ŞEYİN (terminal komutu dahil) o iş bitene kadar kuyrukta beklemesine
    # ve kullanıcıya "pencere donmuş" gibi görünmesine yol açıyordu.
    # Artık her gelen mesaj kendi asyncio görevinde, birbirinden bağımsız
    # olarak işleniyor; böylece terminal, kod çalıştırma, AI isteği vb.
    # gerçekten eşzamanlı (paralel) yürüyor ve biri diğerini bloklamıyor.
    # ------------------------------------------------------------------
    tasks: set[asyncio.Task] = set()

    async def _run(raw: str):
        try:
            await _handle_message(ws, raw)
        except Exception:
            pass

    try:
        while True:
            raw = await ws.receive_text()
            task = asyncio.create_task(_run(raw))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()


def main():
    import socket
    import tempfile
    import uvicorn

    # console=False derlemede sys.stdout/stderr None olur; print() ve
    # uvicorn log config'i None stream üzerinde çöker.
    if sys.stdout is None or sys.stderr is None:
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        dizin = os.path.join(base, "TurKod")
        os.makedirs(dizin, exist_ok=True)
        log = open(os.path.join(dizin, "backend.log"), "a",
                   encoding="utf-8", errors="replace")
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--backend", action="store_true",
                        help="Flutter exe modu tarafından gönderilir.")
    args = parser.parse_args()

    PREFERRED_PORT = 8765
    PORT_FILE = os.path.join(tempfile.gettempdir(), "turkod_backend_port")

    def _find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _port_available(port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    if args.port != 0:
        actual_port = args.port
    elif _port_available(PREFERRED_PORT):
        actual_port = PREFERRED_PORT
    else:
        actual_port = _find_free_port()

    with open(PORT_FILE, "w", encoding="utf-8") as f:
        f.write(str(actual_port))

    print(f"[TurKod] Backend port: {actual_port}")
    uvicorn.run(app, host="127.0.0.1", port=actual_port, log_level="warning")


if __name__ == "__main__":
    main()
