"""AI saglayici sabitleri ve model guncelleme."""
import threading

# Yapay zekâ SDK'ları ARTIK açılışta yüklenmez: dördü birlikte ~75 MB bellek
# ve ~8 sn açılış süresi tutuyordu (2 GB RAM'li makinelerde ciddi yük; AI
# özelliği varsayılan olarak kapalı). Yalnızca seçili sağlayıcınınki, ilk
# kullanımda yüklenir ve önbelleğe alınır. Düz `import` ifadeleri bilerek
# korunuyor: PyInstaller bunları statik analizle görüp pakete dahil eder.
_SDK_ONBELLEK = {}
_SDK_KILIT = threading.Lock()


def sdk_yukle(ad):
    """'openai' | 'groq' | 'genai' | 'anthropic' -> modül/sınıf ya da None."""
    with _SDK_KILIT:
        if ad in _SDK_ONBELLEK:
            return _SDK_ONBELLEK[ad]
        nesne = None
        try:
            if ad == "openai":
                import openai as nesne
            elif ad == "groq":
                from groq import Groq as nesne
            elif ad == "genai":
                from google import genai as nesne
            elif ad == "anthropic":
                import anthropic as nesne
        except ImportError:
            nesne = None
        _SDK_ONBELLEK[ad] = nesne
        return nesne


SAGLAYICI_SDK = {"OpenAI": "openai", "Groq": "groq", "Gemini": "genai", "Claude": "anthropic"}


def sdk_arka_planda_yukle(saglayici):
    """Seçili sağlayıcının SDK'sını arka planda önceden yükler (AI açıksa ilk
    soru beklemesin diye)."""
    ad = SAGLAYICI_SDK.get(saglayici)
    if not ad:
        return
    threading.Thread(target=sdk_yukle, args=(ad,), daemon=True,
                     name="ai-sdk-yukle").start()

AI_MODELLERI = {
    "OpenAI": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    # ← DÜZELTME: llama-3.1-70b-versatile (decommissioned) → llama-3.3-70b-versatile
    #            mixtral-8x7b-32768 (decommissioned) → çıkarıldı
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "deepseek-r1-distill-llama-70b",
        "qwen-2.5-coder-32b",
        "gemma2-9b-it",
    ],
    # ← DÜZELTME: gemini-2.5-* modelleri mevcut değil
    "Gemini": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"],
    # Eski claude-3-5-sonnet / claude-3-5-haiku / claude-3-opus kimlikleri
    # kullanımdan kaldırıldı; her istek "model bulunamadı" hatası veriyordu.
    "Claude": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"]
}


def groq_modelleri_guncelle(api_key=None):
    """Groq modellerini API'den guncelle. API key gerekli."""
    try:
        import requests
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            timeout=8,
            headers=headers
        )
        if resp.status_code == 200:
            modeller = [m["id"] for m in resp.json().get("data", [])]
            # Whisper (ses), guard, tool-use modellerini cikar
            modeller = [m for m in modeller
                       if "whisper" not in m.lower()
                       and "guard" not in m.lower()
                       and "tool-use" not in m.lower()]
            if modeller:
                AI_MODELLERI["Groq"] = sorted(modeller)
                print(f"[TurKod] Groq modelleri guncellendi: {len(modeller)} model")
                return True
        else:
            print(f"[TurKod] Groq model guncelleme: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[TurKod] Groq guncelleme hatasi: {e}")
    return False


def openai_modelleri_guncelle(api_key=None):
    """OpenAI modellerini API'den guncelle. API key gerekli."""
    try:
        import requests
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.get(
            "https://api.openai.com/v1/models",
            timeout=10,
            headers=headers
        )
        if resp.status_code == 200:
            modeller = [m["id"] for m in resp.json().get("data", [])]
            # Sohbet dışı modeller (görsel, ses, gerçek zamanlı, yazıya
            # dökme) seçilirse sohbet isteği hata veriyordu; elenir.
            sohbet_disi = ("image", "audio", "realtime", "transcribe", "tts",
                           "search", "embedding", "instruct")
            modeller = [m for m in modeller if "gpt" in m.lower()
                        and not any(k in m.lower() for k in sohbet_disi)]
            if modeller:
                AI_MODELLERI["OpenAI"] = sorted(modeller, reverse=True)
                print(f"[TurKod] OpenAI modelleri guncellendi: {len(modeller)} model")
                return True
        else:
            print(f"[TurKod] OpenAI model guncelleme: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[TurKod] OpenAI guncelleme hatasi: {e}")
    return False
