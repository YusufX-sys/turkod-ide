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
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Erişim anahtarı: arayüz her açılışta rastgele bir anahtar üretip TURKOD_TOKEN
# ortam değişkeniyle verir; WebSocket bağlantısı ?token=<anahtar> ister. Böylece
# aynı makinedeki başka bir süreç/kullanıcı (loopback herkese açıktır) komut
# çalıştıramaz. Değişken hemen silinir: kullanıcı programları ve terminal bu
# sürecin ortamını miras alır, anahtarı görmemeliler.
_ERISIM_ANAHTARI = os.environ.pop("TURKOD_TOKEN", "")
if not _ERISIM_ANAHTARI:
    _ERISIM_ANAHTARI = secrets.token_urlsafe(32)
    print(f"[TurKod] TURKOD_TOKEN verilmedi; bu oturumun anahtarı: {_ERISIM_ANAHTARI}",
          flush=True)


def _anahtar_dogru_mu(anahtar: str) -> bool:
    return secrets.compare_digest(anahtar.encode("utf-8"), _ERISIM_ANAHTARI.encode("utf-8"))


try:
    from .ide_core import IDECore
    from . import entegrasyon
except ImportError:
    from ide_core import IDECore
    import entegrasyon


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


def _cmd_sistem_entegrasyonu(params):
    return entegrasyon.durum()


def _cmd_sistem_entegrasyonu_ayarla(params):
    return entegrasyon.ayarla(path=params.get("path"),
                              iliskilendir=params.get("iliskilendir"))


def _cmd_proje_dizini_set(params):
    return core.proje_dizini_set(params.get("dizin"))


def _cmd_cikti_onay(params):
    return core.cikti_onay(params.get("pid"), params.get("miktar", 0))


def _cmd_dosya_oku(params):
    return core.dosya_oku(params["yol"])


def _cmd_dosya_kaydet(params):
    return core.dosya_kaydet(params.get("yol"), params.get("icerik", ""))


def _cmd_dosya_agaci(params):
    return core.dosya_agaci(params.get("dizin"))


def _cmd_oge_olustur(params):
    return core.oge_olustur(params.get("dizin"), params.get("ad"),
                            bool(params.get("klasor", False)))


def _cmd_oge_yeniden_adlandir(params):
    return core.oge_yeniden_adlandir(params.get("yol"), params.get("ad"))


def _cmd_oge_sil(params):
    # kalici: Geri Dönüşüm Kutusu olmayan sürücüde kullanıcı onay verdi.
    return core.oge_sil(params.get("yol"), bool(params.get("kalici", False)))


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


def _cmd_duzelt_riskleri(params):
    return {"riskler": core.calistirma_riskleri(params.get("kod", ""))}


def _cmd_tamamlama_onerileri(params):
    return core.tamamlama_onerileri(
        params.get("kelime", ""),
        params.get("kod", ""),
        params.get("once", ""),
    )


def _cmd_kod_tanimlari(params):
    return core.kod_tanimlari(params.get("kod", ""))


def _cmd_kelime_aciklamasi(params):
    return core.kelime_aciklamasi(params.get("kelime", ""), params.get("kod", ""))


def _cmd_ad_degistir(params):
    return core.ad_degistir(params.get("kod", ""), params.get("eski", ""),
                            params.get("yeni", ""), params.get("satir"),
                            params.get("sutun"))


def _cmd_kodu_bicimlendir(params):
    return core.kodu_bicimlendir(params.get("kod", ""))


def _cmd_tanim_bul(params):
    return core.tanim_bul(params.get("kod", ""), params.get("ad", ""),
                          params.get("dosya"))


def _cmd_dosyalarda_ara(params):
    return core.dosyalarda_ara(
        params.get("dizin"),
        params.get("sorgu", ""),
        bool(params.get("buyuk_kucuk", False)),
        bool(params.get("tam_kelime", False)),
        bool(params.get("regex", False)),
    )


def _cmd_sozluk_verileri(params):
    return core.sozluk_verileri()


def _cmd_sistem_fontlari(params):
    return core.sistem_fontlari()


def _cmd_ai_modelleri(params):
    return core.ai_modelleri()


def _cmd_ai_modelleri_guncelle(params):
    return core.modelleri_guncelle(params.get("saglayici"),
                                   katalog=params.get("katalog", True) is not False)


def _cmd_ai_baglanti_kes(params):
    return core.ai_baglanti_kes(params.get("saglayici"))


def _cmd_ai_model_dogrula(params):
    return core.model_dogrula()


def _cmd_ai_sor(params):
    return core.ai_sor(params.get("mesaj", ""), params.get("kod"))


# Kodi köprüsü: TürKod'un ana penceresi ile masaüstü Kodi penceresi (ikinci
# pencere, ayrı bağlantı) birbirine "kodi_kopru" olayıyla mesaj gönderir.
_KODI_KOPRU = {}


def _cmd_kodi_kopru_gonder(params):
    gonder = _KODI_KOPRU.get(str(params.get("rol") or ""))
    if gonder is None:
        return {"ok": False, "hata": "Karşı pencere bağlı değil."}
    veri = params.get("veri")
    gonder(veri if isinstance(veri, dict) else {})
    return {"ok": True}


def _cmd_kodi_sor(params):
    return core.kodi_sor(params.get("mesaj", ""), params.get("dusunme"),
                         params.get("baglam"), otomatik=params.get("otomatik") is True)


def _cmd_ai_kodu_acikla(params):
    return core.ai_kodu_acikla(params.get("kod", ""))


def _cmd_ai_hata_acikla(params):
    return core.ai_hata_acikla(params.get("kod", ""), params.get("hata", ""))


def _cmd_ai_baglanti_test(params):
    return core.ai_baglanti_test()


def _cmd_ai_kodu_optimize(params):
    return core.ai_kodu_optimize(params.get("kod", ""))


def _cmd_ai_temizle(params):
    return core.ai_temizle()


def _cmd_calistir_durdur(params):
    return core.kodu_durdur(params.get("oturum"), bool(params.get("yalnizca_kabuk", False)))


def _cmd_exe_kaynagi(params):
    """TürKod ile yapılmış bir EXE'nin kaynak kodu (--kaynak-acik ile yapıldıysa)."""
    try:
        from .exe_donusturucu import exe_kaynagi_oku
    except ImportError:
        from exe_donusturucu import exe_kaynagi_oku
    durum, metin = exe_kaynagi_oku(params.get("yol", ""))
    if durum == "acik":
        return {"ok": True, "durum": durum, "kaynak": metin}
    return {"ok": False, "durum": durum, "hata": metin}


def _cmd_imza_dogrula(params):
    return core.imza_dogrula()


def _cmd_dosya_hash(params):
    return core.dosya_hash()


def _cmd_breakpoint_toggle(params):
    return core.breakpoint_toggle(params.get("satir"))


def _cmd_breakpoint_list(params):
    return core.breakpoint_list()


def _cmd_debug_adim(params):
    return core.debug_adim()


def _cmd_debug_icine(params):
    return core.debug_icine()


def _cmd_debug_disina(params):
    return core.debug_disina()


def _cmd_debug_duraklat(params):
    return core.debug_duraklat()


def _cmd_debug_durum(params):
    return core.debug_durum()


def _cmd_debug_breakpoint_ayarla(params):
    return core.debug_breakpoint_ayarla(params.get("satirlar") or [],
                                        params.get("kosullar"),
                                        params.get("isabetler"))


def _cmd_debug_izle(params):
    return core.debug_izle(params.get("ifadeler") or [])


def _cmd_debug_degerlendir(params):
    return core.debug_degerlendir(params.get("ifade", ""), params.get("cerceve", 0))


def _cmd_debug_degisken_ata(params):
    return core.debug_degisken_ata(params.get("ad", ""), params.get("ifade", ""),
                                   params.get("cerceve", 0))


def _cmd_debug_cerceve(params):
    return core.debug_cerceve(params.get("indeks", 0))


def _cmd_debug_devam(params):
    return core.debug_devam()


def _cmd_debug_durdur(params):
    return core.debug_durdur()


SYNC_COMMANDS = {
    "ping": _cmd_ping,
    "ayar_get": _cmd_ayar_get,
    "ayar_set": _cmd_ayar_set,
    "ayarlar_tumu": _cmd_ayarlar_tumu,
    "sistem_entegrasyonu": _cmd_sistem_entegrasyonu,
    "sistem_entegrasyonu_ayarla": _cmd_sistem_entegrasyonu_ayarla,
    "proje_dizini_set": _cmd_proje_dizini_set,
    "cikti_onay": _cmd_cikti_onay,
    "dosya_oku": _cmd_dosya_oku,
    "dosya_kaydet": _cmd_dosya_kaydet,
    "dosya_agaci": _cmd_dosya_agaci,
    "oge_olustur": _cmd_oge_olustur,
    "oge_yeniden_adlandir": _cmd_oge_yeniden_adlandir,
    "oge_sil": _cmd_oge_sil,
    "oturum_oku": _cmd_oturum_oku,
    "oturum_kaydet": _cmd_oturum_kaydet,
    "kodu_cevir": _cmd_kodu_cevir,
    "kod_arama_cevir": _cmd_kod_arama_cevir,
    "istatistik": _cmd_istatistik,
    "todo_bul": _cmd_todo_bul,
    "fold_bolgeleri": _cmd_fold_bolgeleri,
    "tokenize": _cmd_tokenize,
    "syntax_kontrol": _cmd_syntax_kontrol,
    "duzelt_riskleri": _cmd_duzelt_riskleri,
    "tamamlama_onerileri": _cmd_tamamlama_onerileri,
    "kod_tanimlari": _cmd_kod_tanimlari,
    "tanim_bul": _cmd_tanim_bul,
    "kelime_aciklamasi": _cmd_kelime_aciklamasi,
    "ad_degistir": _cmd_ad_degistir,
    "kodu_bicimlendir": _cmd_kodu_bicimlendir,
    "dosyalarda_ara": _cmd_dosyalarda_ara,
    "sozluk_verileri": _cmd_sozluk_verileri,
    "sistem_fontlari": _cmd_sistem_fontlari,
    "ai_modelleri": _cmd_ai_modelleri,
    "ai_modelleri_guncelle": _cmd_ai_modelleri_guncelle,
    "ai_baglanti_kes": _cmd_ai_baglanti_kes,
    "ai_model_dogrula": _cmd_ai_model_dogrula,
    "ai_sor": _cmd_ai_sor,
    "ai_kodu_acikla": _cmd_ai_kodu_acikla,
    "ai_hata_acikla": _cmd_ai_hata_acikla,
    "ai_baglanti_test": _cmd_ai_baglanti_test,
    "ai_kodu_optimize": _cmd_ai_kodu_optimize,
    "ai_temizle": _cmd_ai_temizle,
    "kodi_sor": _cmd_kodi_sor,
    "kodi_durum": lambda params: core.kodi_durum(),
    "kodi_temizle": lambda params: core.kodi_temizle(),
    "kodi_sohbet_yukle": lambda params: core.kodi_sohbet_yukle(params.get("no")),
    "kodi_sohbetler": lambda params: core.kodi_sohbetler(),
    "kodi_goruntu_dene": lambda params: core.kodi_goruntu_dene(),
    "kodi_kurulum": lambda params: core.kodi_kurulum(params.get("saglayici"), params.get("anahtar")),
    "kodi_sohbet_sil": lambda params: core.kodi_sohbet_sil(params.get("no"), params.get("hepsi")),
    "kodi_sohbet_kaydet": lambda params: core.kodi_sohbet_kaydet(params.get("mesajlar")),
    "kodi_hafiza": lambda params: core.kodi_hafiza_listesi(),
    "kodi_hafiza_sil": lambda params: core.kodi_hafiza_sil(params.get("metin"),
                                                           params.get("hepsi")),
    "kodi_dinle": lambda params: core.kodi_dinle(params.get("sessizlik"), params.get("baslama")),
    "kodi_dinlemeyi_durdur": lambda params: core.kodi_dinlemeyi_durdur(),
    "kodi_seslendir": lambda params: core.kodi_seslendir(params.get("metin", "")),
    "kodi_sus": lambda params: core.kodi_sus(),
    "kodi_kopru_gonder": _cmd_kodi_kopru_gonder,
    "kodi_imlec_konumu": lambda params: core.kodi_imlec_konumu(),
    "calistir_durdur": _cmd_calistir_durdur,
    "exe_kaynagi": _cmd_exe_kaynagi,
    "imza_dogrula": _cmd_imza_dogrula,
    "dosya_hash": _cmd_dosya_hash,
    "breakpoint_toggle": _cmd_breakpoint_toggle,
    "breakpoint_list": _cmd_breakpoint_list,
    "debug_adim": _cmd_debug_adim,
    "debug_icine": _cmd_debug_icine,
    "debug_disina": _cmd_debug_disina,
    "debug_duraklat": _cmd_debug_duraklat,
    "debug_durum": _cmd_debug_durum,
    "debug_breakpoint_ayarla": _cmd_debug_breakpoint_ayarla,
    "debug_izle": _cmd_debug_izle,
    "debug_degerlendir": _cmd_debug_degerlendir,
    "debug_cerceve": _cmd_debug_cerceve,
    "debug_degisken_ata": _cmd_debug_degisken_ata,
    "debug_devam": _cmd_debug_devam,
    "debug_durdur": _cmd_debug_durdur,
}
try:
    from . import updater
except ImportError:
    import updater

try:
    from . import yerel_modeller, calistirici
except ImportError:
    import yerel_modeller
    import calistirici

# Yerel AI modelleri (Eklenti Özellikleri → Yerel AI Modelleri) ve AI tamamlama.
SYNC_COMMANDS.update({
    "yerel_ai_durum": lambda params: core.yerel_ai_durum(params.get("tazele", False)),
    "yerel_ai_oneriler": lambda params: yerel_modeller.onerilen_modeller(
        bool(params.get("tazele", False))),
    "yerel_ai_ara": lambda params: yerel_modeller.model_ara(params.get("sorgu", "")),
    "yerel_ai_indir": lambda params: yerel_modeller.model_indir(
        params.get("ad", ""), params.get("baslik", ""), params.get("parametre_b")),
    "yerel_ai_indirme_durumu": lambda params: yerel_modeller.indirme_durumu(),
    "yerel_ai_indirme_iptal": lambda params: yerel_modeller.indirme_iptal(params.get("ad", "")),
    "yerel_ai_indirme_temizle": lambda params: yerel_modeller.indirme_temizle(params.get("ad")),
    "yerel_ai_sil": lambda params: core.yerel_ai_model_sil(params.get("ad", "")),
    "yerel_ai_motor_durumu": lambda params: yerel_modeller.motor_durumu(),
    "yerel_ai_motor_kur": lambda params: yerel_modeller.motor_kur(params.get("tur")),
    "yerel_ai_motor_kaldir": lambda params: yerel_modeller.motor_kaldir(),
    "yerel_ai_depolama": lambda params: yerel_modeller.depolama_analizi(),
    "yerel_ai_model_dizini": lambda params: core.yerel_ai_model_dizini_ayarla(
        params.get("dizin")),
    "yerel_ai_gorev_ata": lambda params: core.yerel_ai_gorev_ata(params.get("gorev"),
                                                                  params.get("model")),
    "ai_hayalet_tamamla": lambda params: core.ai_hayalet_tamamla(
        params.get("once", ""), params.get("sonra", ""), params.get("dosya"),
        bool(params.get("zorla", False))),
    "ai_tamamla": lambda params: core.ai_tamamla(params.get("once", ""),
                                                 params.get("sonra", "")),
    "kabuk_penceresi": lambda params: {"ok": calistirici.kabuk_penceresi_ac()},
})

SYNC_COMMANDS["surum"] = lambda params: {"ok": True, "surum": updater.mevcut_surum()}
# IDE terminalinin karakter boyutu (sütun x satır): o terminalde başlatılan
# komutlara COLUMNS / LINES olarak verilir (ör. `turkod logo` terminali doldurur).
SYNC_COMMANDS["terminal_boyutu"] = lambda params: core.terminal_boyutu_ayarla(
    params.get("oturum"), params.get("sutun"), params.get("satir"))
SYNC_COMMANDS["guncelleme_kontrol"] = lambda params: updater.kontrol_et()
SYNC_COMMANDS["guncelleme_indir"] = lambda params: updater.indir_ve_dogrula()
SYNC_COMMANDS["guncelleme_indir_baslat"] = lambda params: updater.indir_baslat()
SYNC_COMMANDS["guncelleme_indir_durum"] = lambda params: updater.indir_durum()
SYNC_COMMANDS["guncelleme_kurulum_dogrula"] = \
    lambda params: updater.kurulum_dogrula(str(params.get("yol") or ""))

# Ağa çıkan / uzun süren komutlar ayrı havuzda çalışır. Varsayılan havuz
# küçük (min(32, çekirdek+4)); birkaç AI isteği + takılan bir güncelleme
# kontrolü onu doldurunca kaydet, ping, hata ayıklama adımı gibi hızlı
# komutlar da kuyrukta bekliyor, arayüz donmuş görünüyordu.
_UZUN_KOMUTLAR = frozenset({
    "exe_kaynagi",
    "ai_sor", "kodi_sor", "kodi_kurulum", "kodi_goruntu_dene", "kodi_durum", "kodi_dinle", "kodi_seslendir", "ai_kodu_acikla", "ai_kodu_optimize", "ai_model_dogrula",
    "ai_modelleri_guncelle", "guncelleme_kontrol",
    "guncelleme_indir", "guncelleme_indir_baslat",
    "ai_modelleri", "ai_baglanti_test", "ai_hata_acikla", "ai_tamamla",
    "ai_hayalet_tamamla",
    "yerel_ai_durum", "yerel_ai_oneriler", "yerel_ai_ara", "yerel_ai_indir",
    "yerel_ai_sil", "yerel_ai_motor_durumu", "yerel_ai_depolama", "yerel_ai_model_dizini",
})
_UZUN_HAVUZ = ThreadPoolExecutor(max_workers=16, thread_name_prefix="turkod-uzun")

# ------------------------------------------------------------------
# Özel asenkron komutlar
# ------------------------------------------------------------------
async def _cmd_duzelt(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    progress = _thread_event_sender(ws, loop, "duzelt_progress")

    def _progress(metin):
        progress({"metin": metin})

    # calistirma_izni: True = kullanıcı riskli kodun denenmesine izin verdi,
    # False = hiç çalıştırma, yok = yalnızca risk içermeyen kod çalıştırılır.
    izin = params.get("calistirma_izni")
    # Düzeltme dakikalarca sürebilir (döngü x zaman aşımı): uzun havuzda.
    result = await loop.run_in_executor(
        _UZUN_HAVUZ,
        core.duzelt_kod,
        params.get("kod", ""),
        _progress,
        izin if isinstance(izin, bool) else None,
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


def _akis_cikti(metin):
    """Çıktı olayı: boy (onaylanacak karakter) ve çıktıyı üreten sürecin pid'i.
    Arayüz onayı bu pid'e gönderir; böylece hata ayıklama oturumunun ya da
    yeni çalıştırmanın akış penceresi eski bir pid'le onaylanıp kilitlenmez."""
    veri = {"metin": metin, "boy": len(metin)}
    akis = getattr(core, "_akis", None)
    if akis is not None and akis.pid is not None:
        veri["pid"] = akis.pid
    return veri


async def _cmd_calistir(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "calistirma_cikti")
    exit_ev = _thread_event_sender(ws, loop, "calistirma_bitti")

    def _output(metin):
        # boy: Python karakter sayısı; akış kontrolünde arayüz bunu onaylar.
        output(_akis_cikti(metin))

    def _exit(cikis_kodu):
        exit_ev({"cikis_kodu": cikis_kodu})

    result = await asyncio.to_thread(
        core.kodu_calistir,
        params.get("kod", ""),
        _output,
        _exit,
        params.get("dosya"),
        params.get("argumanlar"),
        bool(params.get("akis_kontrolu", False)),
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


async def _cmd_kabuk_baslat(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "calistirma_cikti")
    exit_ev = _thread_event_sender(ws, loop, "calistirma_bitti")
    result = await asyncio.to_thread(
        core.kabuk_baslat,
        lambda metin: output({"metin": metin}),
        lambda kod: exit_ev({"cikis_kodu": kod}),
        params.get("oturum"),
    )
    await _send_json(ws, {"id": msg_id, "ok": bool(result.get("ok", False)),
                          "result": result})




async def _cmd_kodi_kopru_kayit(ws: WebSocket, msg_id, params):
    rol = str(params.get("rol") or "")
    _KODI_KOPRU[rol] = _thread_event_sender(ws, asyncio.get_running_loop(), "kodi_kopru")
    await _send_json(ws, {"id": msg_id, "ok": True, "result": {"ok": True}})




async def _cmd_debug_baslat(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "calistirma_cikti")
    exit_ev = _thread_event_sender(ws, loop, "calistirma_bitti")
    olay_gondericileri = {}
    akis_kontrolu = bool(params.get("akis_kontrolu", False))

    def _output(metin):
        # Akış kontrolü yoksa "boy" gönderilmez (arayüz onaylamaz).
        output(_akis_cikti(metin) if akis_kontrolu else {"metin": metin})

    def _exit(cikis_kodu):
        exit_ev({"cikis_kodu": cikis_kodu})

    def _olay(ad, veri):
        gonder = olay_gondericileri.get(ad)
        if gonder is None:
            gonder = olay_gondericileri[ad] = _thread_event_sender(ws, loop, ad)
        gonder(veri)

    result = await asyncio.to_thread(
        core.debug_baslat,
        params.get("kod", ""),
        params.get("breakpointler"),
        bool(params.get("ilk_satirda_dur", False)),
        _output,
        _exit,
        _olay,
        params.get("dosya"),
        params.get("argumanlar"),
        params.get("kosullar"),
        params.get("izlenenler"),
        akis_kontrolu,
        params.get("isabetler"),
    )

    await _send_json(ws, {
        "id": msg_id,
        "ok": bool(result.get("ok", False)),
        "result": result,
    })


async def _cmd_terminal_komut(ws: WebSocket, msg_id, params):
    loop = asyncio.get_running_loop()
    output = _thread_event_sender(ws, loop, "terminal_cikti")
    # Her sekmenin kendi terminali vardır: çıktı, komutu yazan oturuma gider.
    oturum = params.get("oturum")

    def _output(metin):
        output({"metin": metin, "oturum": oturum} if oturum else {"metin": metin})

    result = await asyncio.to_thread(
        core.terminal_komut,
        params.get("komut", ""),
        _output,
        oturum,
        params.get("programa", True) is not False,
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

    # Geçerli ama nesne olmayan JSON ([] gibi) eskiden yakalanmayan bir
    # AttributeError'a yol açıyor, istemci 5 dakika yanıt bekliyordu.
    if not isinstance(msg, dict):
        await _send_json(ws, {"id": None, "ok": False, "error": "Geçersiz mesaj."})
        return

    msg_id = msg.get("id")
    command = msg.get("command")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        params = {}

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

        if command == "debug_baslat":
            await _cmd_debug_baslat(ws, msg_id, params)
            return

        if command == "kabuk_baslat":
            await _cmd_kabuk_baslat(ws, msg_id, params)
            return

        if command == "kodi_kopru_kayit":
            await _cmd_kodi_kopru_kayit(ws, msg_id, params)
            return

        handler = SYNC_COMMANDS.get(command)

        if handler is None:
            await _send_json(ws, {
                "id": msg_id,
                "ok": False,
                "error": f"Bilinmeyen komut: {command}",
            })
            return

        if command in _UZUN_KOMUTLAR:
            result = await asyncio.get_running_loop().run_in_executor(
                _UZUN_HAVUZ, handler, params)
        else:
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
        "komutlar": sorted(SYNC_COMMANDS.keys()) + ["kabuk_baslat",
            "calistir",
            "duzelt",
            "terminal_komut",
            "debug_baslat",
        ],
    }


@app.get("/komutlar")
def komutlar():
    return {
        "sync": sorted(SYNC_COMMANDS.keys()),
        "async": ["calistir", "duzelt", "terminal_komut", "debug_baslat", "kabuk_baslat"],
    }


_AKTIF_BAGLANTI = 0


def _calisan_programi_durdur():
    """Yalnızca çalışan programı durdurur (terminaldeki pip vb. kabuk
    komutlarına dokunmaz). Hazırlanmakta olan çalıştırma da iptal edilir:
    eskiden bağlantı koptuktan sonra başlıyor, sahipsiz kalıyordu
    (t.cancel() iş parçacığındaki hazırlığı durdurmaz)."""
    core.hazirliklari_iptal_et()
    with core._calistirma_kilit:
        core._calistirmayi_sonlandir()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Origin: tarayıcı sayfalarını (DNS rebinding dahil) reddeder.
    # token: Origin göndermeyen yerel süreçleri reddeder.
    if ws.headers.get("origin") or not _anahtar_dogru_mu(ws.query_params.get("token", "")):
        await ws.close(code=1008)
        return
    await ws.accept()
    global _AKTIF_BAGLANTI
    _AKTIF_BAGLANTI += 1

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
        # Arayüz bağlantı kopunca programı sonlandırılmış sayar; burada da
        # durdurulur. Eskiden program sahipsiz kalıyor, akış kontrolünde
        # onay gelmediği için çıktı yazarken sonsuza dek askıda kalıyordu.
        _AKTIF_BAGLANTI -= 1
        if _AKTIF_BAGLANTI == 0:
            for durdur in (core.debug_durdur, _calisan_programi_durdur):
                try:
                    await asyncio.to_thread(durdur)
                except Exception:
                    pass


def main():
    import socket
    import tempfile
    import threading
    import uvicorn

    # console=False derlemede sys.stdout/stderr None olur; print() ve
    # uvicorn log config'i None stream üzerinde çöker.
    if sys.stdout is None or sys.stderr is None:
        try:
            base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
            dizin = os.path.join(base, "TurKod")
            os.makedirs(dizin, exist_ok=True)
            log = open(os.path.join(dizin, "backend.log"), "a",
                       encoding="utf-8", errors="replace")
        except OSError:
            log = open(os.devnull, "w", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log

    # Geliştirici kipinde stdout bir boruya bağlı ve Windows kod sayfasındadır
    # (cp1254); "❌" gibi karakterli print'ler UnicodeEncodeError fırlatıp
    # asıl hata mesajının yerine geçiyordu.
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--backend", action="store_true",
                        help="Flutter exe modu tarafından gönderilir.")
    parser.add_argument("--parent-pid", type=int, default=0,
                        help="Bu süreç (arayüz) kapanınca backend de kapanır.")
    args = parser.parse_args()

    try:
        from .surec_izleyici import ebeveyni_izle
    except ImportError:
        from surec_izleyici import ebeveyni_izle
    # temizle: izleyici backend'i os._exit ile kapatır; eskiden geçici
    # klasörler hiç silinmiyordu.
    ebeveyni_izle(args.parent_pid, temizle=core.kapanis_temizligi)
    # Önceki (öldürülmüş / çökmüş) oturumlardan kalan geçici klasörler.
    threading.Thread(target=core.eski_gecicileri_supur, daemon=True,
                     name="turkod-gecici-supurme").start()

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

    try:
        with open(PORT_FILE, "w", encoding="utf-8") as f:
            f.write(str(actual_port))
    except OSError as e:
        print(f"[TurKod] Port dosyası yazılamadı ({e}); devam ediliyor.")

    print(f"[TurKod] Backend port: {actual_port}")
    uvicorn.run(app, host="127.0.0.1", port=actual_port, log_level="warning")


if __name__ == "__main__":
    main()
