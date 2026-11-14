"""Kodi'nin kulağı ve sesi (yalnızca Windows, ek paket gerekmez).

- dinle(): mikrofonu winmm (waveIn) ile ctypes üzerinden dinler; konuşma
  başlayınca kaydeder, sessizlik gelince durur ve WAV baytlarını döndürür.
- yaziya_cevir(): kaydı Groq ya da OpenAI'nin Whisper ucuyla Türkçe yazıya çevirir.
- seslendir(): metni Windows'un Türkçe sesiyle (kodi_ses.ps1, WinRT) WAV'a
  çevirip winsound ile çalar; dur olayı gelince susar.
"""
import array
import ctypes
import io
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

ORNEKLEME = 16000
PARCA_SN = 0.1  # 100 ms'lik tamponlar
TRANSKRIPSIYON = {
    "groq": ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3-turbo"),
    "openai": ("https://api.openai.com/v1/audio/transcriptions", "whisper-1"),
}


class SesHatasi(Exception):
    pass


# ---------------------------------------------------------------------------
# Mikrofon (winmm waveIn)
# ---------------------------------------------------------------------------
class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort),
                ("nSamplesPerSec", ctypes.c_uint), ("nAvgBytesPerSec", ctypes.c_uint),
                ("nBlockAlign", ctypes.c_ushort), ("wBitsPerSample", ctypes.c_ushort),
                ("cbSize", ctypes.c_ushort)]


class _WAVEHDR(ctypes.Structure):
    pass


_WAVEHDR._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", ctypes.c_uint),
                     ("dwBytesRecorded", ctypes.c_uint), ("dwUser", ctypes.c_size_t),
                     ("dwFlags", ctypes.c_uint), ("dwLoops", ctypes.c_uint),
                     ("lpNext", ctypes.POINTER(_WAVEHDR)), ("reserved", ctypes.c_size_t)]

_WHDR_DONE = 0x1
_WAVE_MAPPER = 0xFFFFFFFF


def _rms(veri):
    ornekler = array.array("h")
    ornekler.frombytes(veri[: len(veri) // 2 * 2])
    if not ornekler:
        return 0.0
    return math.sqrt(sum(o * o for o in ornekler) / len(ornekler))


def _wav(veri):
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ORNEKLEME)
        w.writeframes(veri)
    return tampon.getvalue()


def sessizlik_ayir(parcalar, sessizlik_sn=1.2, baslama_sn=8.0, en_uzun_sn=25.0, dur=None):
    """Ses parçalarından (100 ms'lik bayt dizileri; bir yineleyici) konuşmayı
    ayırır. Konuşma başlamadan [baslama_sn] geçerse None döner. Mikrofon
    olmadan da sınanabilsin diye kayıttan ayrı tutulur."""
    taban = []
    kayit = []
    konusma = False
    sessiz = 0
    yuksek = 0
    gecen = 0.0
    for parca in parcalar:
        if dur is not None and dur.is_set():
            return None
        gecen += PARCA_SN
        r = _rms(parca)
        if len(taban) < 3:  # ilk 300 ms: ortamın gürültüsü
            taban.append(r)
            continue
        esik = max(450.0, 3.0 * (sum(taban) / len(taban)))
        if not konusma:
            yuksek = yuksek + 1 if r > esik else 0
            kayit = (kayit + [parca])[-4:]  # konuşmanın başı kesilmesin
            if yuksek >= 2:
                konusma = True
                sessiz = 0
            elif gecen > baslama_sn:
                return None
            continue
        kayit.append(parca)
        sessiz = sessiz + 1 if r < esik else 0
        if sessiz * PARCA_SN >= sessizlik_sn or len(kayit) * PARCA_SN >= en_uzun_sn:
            break
    return b"".join(kayit) if konusma else None


def _mikrofon_parcalari(dur):
    """Mikrofondan 100 ms'lik parçalar üretir (dur olayı gelene ya da üreteç
    kapatılana dek)."""
    if sys.platform != "win32":
        raise SesHatasi("Sesli konuşma yalnızca Windows'ta çalışır.")
    winmm = ctypes.windll.winmm
    fmt = _WAVEFORMATEX(1, 1, ORNEKLEME, ORNEKLEME * 2, 2, 16, 0)
    hwi = ctypes.c_void_p()
    if winmm.waveInOpen(ctypes.byref(hwi), _WAVE_MAPPER, ctypes.byref(fmt), 0, 0, 0) != 0:
        raise SesHatasi("Mikrofon bulunamadı ya da kullanılamıyor. Windows ayarlarında "
                        "mikrofon iznini aç (Gizlilik → Mikrofon).")
    boyut = int(ORNEKLEME * 2 * PARCA_SN)
    tamponlar = [ctypes.create_string_buffer(boyut) for _ in range(4)]
    basliklar = []
    try:
        for t in tamponlar:
            h = _WAVEHDR()
            h.lpData = ctypes.cast(t, ctypes.c_void_p)
            h.dwBufferLength = boyut
            winmm.waveInPrepareHeader(hwi, ctypes.byref(h), ctypes.sizeof(h))
            winmm.waveInAddBuffer(hwi, ctypes.byref(h), ctypes.sizeof(h))
            basliklar.append(h)
        winmm.waveInStart(hwi)
        i = 0
        while dur is None or not dur.is_set():
            h = basliklar[i]
            bekle = 0
            while not (h.dwFlags & _WHDR_DONE):
                time.sleep(0.01)
                bekle += 1
                if bekle > 300 or (dur is not None and dur.is_set()):
                    return
            veri = ctypes.string_at(h.lpData, h.dwBytesRecorded)
            h.dwFlags &= ~_WHDR_DONE
            winmm.waveInAddBuffer(hwi, ctypes.byref(h), ctypes.sizeof(h))
            i = (i + 1) % len(basliklar)
            yield veri
    finally:
        winmm.waveInStop(hwi)
        winmm.waveInReset(hwi)
        for h in basliklar:
            winmm.waveInUnprepareHeader(hwi, ctypes.byref(h), ctypes.sizeof(h))
        winmm.waveInClose(hwi)


def dinle(dur=None, sessizlik_sn=1.2, baslama_sn=8.0):
    """Konuşma kaydını WAV baytları olarak döndürür; kimse konuşmazsa None."""
    uretec = _mikrofon_parcalari(dur)
    try:
        veri = sessizlik_ayir(uretec, sessizlik_sn, baslama_sn, dur=dur)
    finally:
        uretec.close()
    return _wav(veri) if veri else None


def yaziya_cevir(wav_bayt, saglayici, anahtar, zaman_asimi=40):
    """Kaydı Whisper ile Türkçe yazıya çevirir."""
    import requests
    url, model = TRANSKRIPSIYON[saglayici]
    try:
        yanit = requests.post(
            url, headers={"Authorization": f"Bearer {anahtar}"},
            files={"file": ("kodi.wav", wav_bayt, "audio/wav")},
            data={"model": model, "language": "tr", "response_format": "json"},
            timeout=zaman_asimi)
    except requests.RequestException:
        raise SesHatasi("Sesi yazıya çevirmek için internete ulaşamadım.") from None
    if yanit.status_code == 401:
        raise SesHatasi("API anahtarı geçersiz görünüyor; sesi yazıya çeviremedim.")
    if not yanit.ok:
        raise SesHatasi(f"Sesi yazıya çeviremedim (sunucu {yanit.status_code} dedi).")
    return str(yanit.json().get("text") or "").strip()


# ---------------------------------------------------------------------------
# Seslendirme
# ---------------------------------------------------------------------------
_PS1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kodi_ses.ps1")
if not os.path.exists(_PS1) and getattr(sys, "_MEIPASS", None):
    _PS1 = os.path.join(sys._MEIPASS, "kodi_ses.ps1")


def konusma_metni(metin):
    """Markdown cevaptan sesli okunacak metin: kod blokları, bağlantılar ve
    işaretler atılır."""
    metin = re.sub(r"```.*?```", " Kodu balona yazdım. ", metin or "", flags=re.S)
    metin = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", metin)
    metin = re.sub(r"https?://\S+", "", metin)
    metin = re.sub(r"[*_`#>|]", "", metin)
    metin = re.sub(r"^\s*[-•]\s+", "", metin, flags=re.M)
    metin = metin.replace("→", ", ")
    return re.sub(r"\s+", " ", metin).strip()[:1500]


def seslendir(metin, dur=None):
    """Metni okur; bitene ya da dur olayı gelene dek bekler."""
    if sys.platform != "win32":
        raise SesHatasi("Seslendirme yalnızca Windows'ta çalışır.")
    import winsound
    metin = konusma_metni(metin)
    if not metin:
        return
    klasor = tempfile.mkdtemp(prefix="kodi_ses_")
    girdi = os.path.join(klasor, "metin.txt")
    cikti = os.path.join(klasor, "ses.wav")
    try:
        with open(girdi, "w", encoding="utf-8") as f:
            f.write(metin)
        sonuc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", _PS1, girdi, cikti],
            capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if sonuc.returncode != 0 or not os.path.exists(cikti):
            raise SesHatasi("Windows'un konuşma sesi kullanılamadı.")
        if dur is not None and dur.is_set():
            return
        with wave.open(cikti) as w:
            sure = w.getnframes() / float(w.getframerate())
        winsound.PlaySound(cikti, winsound.SND_FILENAME | winsound.SND_ASYNC)
        bitis = time.time() + sure + 0.2
        while time.time() < bitis:
            if dur is not None and dur.is_set():
                winsound.PlaySound(None, 0)
                break
            time.sleep(0.05)
    finally:
        # Geçici klasör her durumda silinir. Eskiden ses dosyası üretilemeyince
        # os.remove(ses.wav) hata veriyor, klasör hiç silinmiyordu.
        shutil.rmtree(klasor, ignore_errors=True)


_SES_KILIDI = threading.Lock()
