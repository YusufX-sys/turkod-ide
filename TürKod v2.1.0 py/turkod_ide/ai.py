"""AI saglayici sabitleri ve model guncelleme."""
import threading


try:
    import openai
except ImportError:
    openai = None

try:
    from google import genai
except ImportError:
    genai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from groq import Groq
except ImportError:
    Groq = None

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
    # ← DÜZELTME: claude-sonnet-4-6 gibi modeller mevcut değil
    "Claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
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
            modeller = [m for m in modeller if "gpt" in m.lower()]
            if modeller:
                AI_MODELLERI["OpenAI"] = sorted(modeller, reverse=True)
                print(f"[TurKod] OpenAI modelleri guncellendi: {len(modeller)} model")
                return True
        else:
            print(f"[TurKod] OpenAI model guncelleme: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[TurKod] OpenAI guncelleme hatasi: {e}")
    return False
