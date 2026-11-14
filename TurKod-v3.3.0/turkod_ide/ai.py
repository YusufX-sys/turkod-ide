"""AI sağlayıcı kataloğu ve genel sohbet istemcisi.

Sağlayıcı/model listesi elle tutulmaz: https://models.dev/api.json adresindeki
açık katalogdan (200+ sağlayıcı: OpenAI, Anthropic, Google, Groq, Mistral,
DeepSeek, xAI, OpenRouter, Together, Fireworks, Cerebras, Meta ...) indirilir,
günde bir kez yenilenir ve %LOCALAPPDATA%\\TurKod\\ai_katalog.json dosyasında
saklanır. İnternet yoksa önce diskteki son katalog, o da yoksa aşağıdaki küçük
yedek liste kullanılır.

Sağlayıcıların neredeyse tamamı OpenAI uyumlu /chat/completions ucu sunar;
Anthropic biçimli olanlar /messages ile konuşulur. Bu yüzden sağlayıcı başına
ayrı SDK gerekmez: tüm istekler `requests` ile yapılır. Yerel sağlayıcılar
(TürKod Yerel / llama-cpp-python, LM Studio, llama.cpp sunucusu) anahtar
istemez ve modelleri canlı sorgulanır.
"""
import json
import os
import re
import tempfile
import threading
import time

# ----------------------------------------------------------------------
# Eski sürüm uyumluluğu: SDK'lar artık kullanılmıyor; selftest ve eski
# çağıranlar için işlevler yerinde bırakıldı.
# ----------------------------------------------------------------------
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


def sdk_arka_planda_yukle(saglayici):
    """Eski API: artık SDK yüklenmez; yalnızca katalog arka planda tazelenir."""
    katalog_arka_planda_tazele()


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------
KATALOG_URL = "https://models.dev/api.json"
KATALOG_OMRU = 24 * 3600

# Eski ayar dosyalarındaki görünen adlar -> katalog kimliği.
ESKI_ADLAR = {"OpenAI": "openai", "Groq": "groq", "Gemini": "google",
              "Claude": "anthropic", "ollama": "yerel"}

# Katalogda taban adresi olmayan (kendi SDK'sı olan) sağlayıcıların OpenAI
# uyumlu uçları.
BILINEN_API = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "mistral": "https://api.mistral.ai/v1",
    "xai": "https://api.x.ai/v1",
    "togetherai": "https://api.together.xyz/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "cerebras": "https://api.cerebras.ai/v1",
    "perplexity": "https://api.perplexity.ai",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "venice": "https://api.venice.ai/api/v1",
    "vercel": "https://ai-gateway.vercel.sh/v1",
    "aihubmix": "https://aihubmix.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}

# Kimlik doğrulaması bulut hesabı/bölge gerektiren, düz API anahtarıyla
# kullanılamayan sağlayıcılar listelenmez.
ATLANAN = {"azure", "azure-cognitive-services", "google-vertex",
           "google-vertex-anthropic", "amazon-bedrock", "sap-ai-core", "gitlab",
           "watsonx", "cloudflare-ai-gateway", "qvac", "salad-cloud"}

# Öne çıkan sağlayıcılar listenin başında bu sırayla gösterilir.
ONCELIK = ["yerel", "lmstudio", "llamacpp", "openai", "anthropic", "google",
           "groq", "meta-llama", "mistral", "deepseek", "xai", "openrouter",
           "togetherai", "cerebras", "fireworks-ai", "deepinfra", "perplexity",
           "cohere"]

# Bilgisayarda çalışan, anahtar istemeyen sağlayıcılar. Modelleri canlı
# sorgulanır (yerel_modelleri_sorgula).
YEREL_SAGLAYICILAR = {
    # TürKod'un kendi llama-cpp-python motoru; adres sunucu başlayınca belli olur
    # (ide_core, yerel_modeller.sunucu_url() ile verir).
    "yerel": {"ad": "TürKod Yerel (llama.cpp)", "api": "", "doc": ""},
    "lmstudio": {"ad": "LM Studio (Yerel)", "api": "http://127.0.0.1:1234/v1",
                 "doc": "https://lmstudio.ai"},
    "llamacpp": {"ad": "llama.cpp sunucusu (Yerel)", "api": "http://127.0.0.1:8080/v1",
                 "doc": "https://github.com/ggml-org/llama.cpp"},
}

# Katalogda olmayan ek sağlayıcılar (Meta'nın resmi Llama API'si).
EK_SAGLAYICILAR = {
    "meta-llama": {
        "ad": "Meta Llama API", "api": "https://api.llama.com/compat/v1",
        "doc": "https://llama.developer.meta.com/docs/models",
        "modeller": ["Llama-4-Maverick-17B-128E-Instruct-FP8",
                     "Llama-4-Scout-17B-16E-Instruct-FP8",
                     "Llama-3.3-70B-Instruct", "Llama-3.3-8B-Instruct"],
    },
    "ozel": {
        "ad": "Özel (OpenAI uyumlu adres)", "api": "",
        "doc": "", "modeller": [],
    },
}

# İnternet ve disk önbelleği yoksa kullanılan küçük yedek katalog.
YEDEK_KATALOG = {
    "openai": {"ad": "OpenAI", "modeller": ["gpt-5-mini", "gpt-5", "gpt-4.1-mini",
                                             "gpt-4o-mini", "gpt-4o"]},
    "anthropic": {"ad": "Anthropic", "tur": "anthropic",
                  "modeller": ["claude-opus-5-5", "claude-sonnet-5-5",
                               "claude-haiku-4-5"]},
    "google": {"ad": "Google", "modeller": ["gemini-2.5-flash", "gemini-2.5-pro",
                                             "gemini-2.5-flash-lite"]},
    "groq": {"ad": "Groq", "modeller": ["llama-3.3-70b-versatile",
                                         "llama-3.1-8b-instant",
                                         "openai/gpt-oss-120b"]},
    "mistral": {"ad": "Mistral", "modeller": ["mistral-large-latest",
                                               "mistral-small-latest",
                                               "codestral-latest"]},
    "deepseek": {"ad": "DeepSeek", "api": "https://api.deepseek.com",
                 "modeller": ["deepseek-chat", "deepseek-reasoner"]},
    "xai": {"ad": "xAI", "modeller": ["grok-4", "grok-3-mini"]},
    "openrouter": {"ad": "OpenRouter", "api": "https://openrouter.ai/api/v1",
                   "modeller": ["openrouter/auto",
                                "meta-llama/llama-3.3-70b-instruct"]},
    "togetherai": {"ad": "Together AI",
                   "modeller": ["meta-llama/Llama-3.3-70B-Instruct-Turbo"]},
}

# Ayarlar sayfasının ilk açılışta göstereceği eski biçimli liste (geriye uyum).
AI_MODELLERI = {}

_KILIT = threading.RLock()
_KATALOG = None          # {kimlik: kayıt}
_KATALOG_ZAMANI = 0.0
_KATALOG_KAYNAGI = "yedek"
_TAZELENIYOR = False


def _veri_dizini():
    taban = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    dizin = os.path.join(taban, "TurKod")
    try:
        os.makedirs(dizin, exist_ok=True)
    except OSError:
        pass
    return dizin


def _katalog_dosyasi():
    return os.path.join(_veri_dizini(), "ai_katalog.json")


def saglayici_kimligi(deger):
    """Eski görünen adları ("OpenAI", "Claude" ...) katalog kimliğine çevirir."""
    deger = (deger or "").strip()
    return ESKI_ADLAR.get(deger, deger)


# ----------------------------------------------------------------------
# Katalog
# ----------------------------------------------------------------------
def _kayit(kimlik, ad, api, tur="openai", modeller=(), doc="", env=(),
           yerel=False):
    return {"id": kimlik, "ad": ad, "api": api, "tur": tur,
            "modeller": list(modeller), "doc": doc, "env": list(env),
            "yerel": yerel, "anahtar_gerekli": not yerel and kimlik != "ozel"}


def models_dev_isle(ham):
    """models.dev api.json -> {kimlik: kayıt}. Yalnızca metin üreten, düz API
    anahtarıyla kullanılabilen sağlayıcı ve modeller alınır."""
    sonuc = {}
    if not isinstance(ham, dict):
        return sonuc
    for kimlik, s in ham.items():
        if not isinstance(s, dict) or kimlik in ATLANAN:
            continue
        api = (s.get("api") or BILINEN_API.get(kimlik) or "").rstrip("/")
        if not api or "${" in api:
            continue
        npm = s.get("npm") or ""
        tur = "anthropic" if npm == "@ai-sdk/anthropic" else "openai"
        modeller = []
        dusunme = {}
        gorsel = []
        for mid, m in (s.get("models") or {}).items():
            if not isinstance(m, dict):
                continue
            cikti = ((m.get("modalities") or {}).get("output") or ["text"])
            if "text" not in cikti:
                continue
            if m.get("status") == "deprecated":
                continue
            modeller.append((m.get("release_date") or "", m.get("id") or mid))
            if m.get("reasoning"):
                dusunme[m.get("id") or mid] = dusunme_bilgisi(m)
            if "image" in ((m.get("modalities") or {}).get("input") or []) or m.get("attachment"):
                gorsel.append(m.get("id") or mid)
        if not modeller:
            continue
        # En yeni model başta.
        modeller.sort(key=lambda x: x[0], reverse=True)
        yerel = api.startswith("http://127.0.0.1") or api.startswith("http://localhost")
        sonuc[kimlik] = _kayit(kimlik, s.get("name") or kimlik, api, tur,
                               [m for _, m in modeller], s.get("doc") or "",
                               s.get("env") or (), yerel)
        if dusunme:
            sonuc[kimlik]["dusunme"] = dusunme
        if gorsel:
            sonuc[kimlik]["gorsel"] = gorsel
    return sonuc


# Katalogda bilgisi olmayan modeller için ad ipuçları (görsel görebilenler).
_GORSEL_IPUCLARI = ("vision", "-vl", "vl-", "llama-4", "llava", "pixtral", "gpt-4o", "gpt-4.1",
                    "gpt-5", "o3", "o4", "claude", "gemini", "gemma-3", "qwen2.5-vl", "qwen3-vl",
                    "grok-4", "grok-2-vision", "mistral-medium", "mistral-small-3")


def gorsel_destekler(kimlik, model):
    """Model mesajdaki görüntüyü görebilir mi? (Katalog, yoksa adı.)"""
    s = saglayici(kimlik)
    if s and model in (s.get("gorsel") or ()):
        return True
    ad = str(model or "").lower()
    return any(i in ad for i in _GORSEL_IPUCLARI)


def _icerik_uzunlugu(icerik):
    """Token tahmini için karakter uzunluğu (görsel parça ~4000 karakter)."""
    if isinstance(icerik, list):
        return sum(len(str(p.get("text") or "")) if p.get("type") == "text" else 4000
                   for p in icerik if isinstance(p, dict))
    return len(str(icerik or ""))


def _anthropic_icerik(icerik):
    """OpenAI biçimindeki görsel parçayı Anthropic biçimine çevirir."""
    if not isinstance(icerik, list):
        return icerik
    sonuc = []
    for p in icerik:
        if isinstance(p, dict) and p.get("type") == "image_url":
            url = str((p.get("image_url") or {}).get("url") or "")
            tur, _, veri = url.partition(";base64,")
            sonuc.append({"type": "image", "source": {
                "type": "base64", "media_type": tur.replace("data:", "") or "image/jpeg",
                "data": veri}})
        else:
            sonuc.append(p)
    return sonuc


def _gorselsiz(mesajlar):
    """Görsel parçaları atılmış mesajlar (model görsel kabul etmeyince)."""
    sonuc = []
    for m in mesajlar:
        icerik = m.get("content")
        if isinstance(icerik, list):
            icerik = "\n".join(str(p.get("text") or "") for p in icerik
                               if isinstance(p, dict) and p.get("type") == "text")
        sonuc.append({**m, "content": icerik})
    return sonuc


def _arac_cagrilarini_ekle(metin, cagrilar):
    """Modelin "eylem" aracı çağrılarını cevabın sonuna eylem bloğu olarak
    ekler (Kodi bloğu nasıl yazılmışsa öyle işler)."""
    satirlar = []
    for c in cagrilar or []:
        f = (c or {}).get("function") or {}
        if f.get("name") != "eylem":
            continue
        try:
            arg = json.loads(f.get("arguments") or "{}", strict=False)
        except ValueError:
            continue
        if isinstance(arg, dict) and arg:
            satirlar.append(json.dumps(arg, ensure_ascii=False))
    if not satirlar:
        return metin
    return (metin or "").rstrip() + "\n```eylem\n" + "\n".join(satirlar) + "\n```"


def _json_parcalari(metin):
    """Metindeki bütün JSON nesneleri (iç içe olanlar dahil, sırayla)."""
    cozucu = json.JSONDecoder(strict=False)  # metinde gerçek satır sonu olabilir
    sonuc, i = [], 0
    while True:
        i = metin.find("{", i)
        if i < 0:
            return sonuc
        try:
            nesne, son = cozucu.raw_decode(metin, i)
        except ValueError:
            i += 1
            continue
        if isinstance(nesne, dict):
            sonuc.append(nesne)
        i = son


def _arac_eylemi(ad, arg):
    """Modelin çağırdığı araç (ad, argümanlar) -> Kodi eylemi ya da None.
    "eylem" aracının şemaya uymayan çağrısı olduğu gibi alınır; gpt-oss'un
    kendiliğinden çağırdığı yerleşik tarayıcı araçları (browser.search,
    browser.open) tarayıcı eylemine çevrilir."""
    if not isinstance(arg, dict):
        return None
    ad = str(ad or "").lower()
    if "eylem" in arg:
        return arg
    if ad.endswith("search") or ad.endswith("find"):
        sorgu = arg.get("query") or arg.get("q") or arg.get("pattern")
        if isinstance(sorgu, str) and sorgu.strip():
            return {"eylem": "tarayici", "islem": "ara", "sorgu": sorgu.strip()}
    if ad.endswith("open"):
        adres = arg.get("url") or arg.get("id") or arg.get("adres")
        if isinstance(adres, str) and re.match(r"https?://|www\.", adres.strip()):
            return {"eylem": "tarayici", "islem": "ac", "adres": adres.strip()}
    return None


def basarisiz_cagri_eylemleri(uretilen):
    """Sağlayıcının reddettiği araç çağrısından (Groq: failed_generation)
    Kodi eylemlerini kurtarır. Eskiden bu cevap atılır, modele "hiçbir aracın
    yok, düz metinle cevap ver" denirdi: model de "Hadi tarayıcıyı açalım!"
    deyip hiçbir iş yapmıyordu."""
    if not isinstance(uretilen, str) or not uretilen.strip():
        return []
    m = re.search(r'to=(?:functions\.)?([\w.]+)', uretilen)
    varsayilan_ad = m.group(1) if m else ""
    eylemler = []
    for nesne in _json_parcalari(uretilen):
        ad = nesne.get("name") or varsayilan_ad
        arg = nesne.get("arguments", nesne.get("parameters"))
        if isinstance(arg, str):
            try:
                arg = json.loads(arg, strict=False)
            except ValueError:
                arg = None
        e = _arac_eylemi(ad, arg if isinstance(arg, dict) else nesne)
        if e and e not in eylemler:
            eylemler.append(e)
    return eylemler


def _basarisiz_uretim(yanit):
    try:
        hata = (yanit.json() or {}).get("error")
    except (ValueError, AttributeError):
        return ""
    return str(hata.get("failed_generation") or "") if isinstance(hata, dict) else ""


# Cevap token sınırında kesilince modele gönderilen istek (kaldığı yerden).
DEVAM_ISTEMI = ("Cevabın token sınırında yarıda kesildi. Tam kaldığın yerden, son karakterden "
                "itibaren devam et: hiçbir şeyi tekrarlama, açıklama ya da giriş cümlesi ekleme, "
                "açık kalan kod bloğunu yeniden açma; yalnızca devamını yaz.")


def devami_birlestir(onceki, devam):
    """Kesilen cevapla devamını birleştirir. Model devamın başında kod
    bloğunu yeniden açabiliyor ya da son satırları tekrarlayabiliyor: açık
    bir blok içindeyken baştaki ```python satırı ve önceki metnin sonuyla
    örtüşen kısım atılır."""
    onceki, devam = onceki or "", devam or ""
    if not devam.strip():
        return onceki  # devamı gelmedi (uyarı / boş yanıt atıldı): elde olan kalır
    if len(re.findall(r"^[ \t]*```", onceki, re.M)) % 2:  # açık kod bloğundayız
        devam = re.sub(r"^\s*```[^\n`]*\n", "", devam, count=1)
    en_uzun = 0
    for n in range(min(len(onceki), len(devam), 400), 11, -1):
        if onceki.endswith(devam[:n]):
            en_uzun = n
            break
    if not en_uzun:
        # Model yarım kalan son satırı baştan yeniden yazabiliyor
        # ("print(2)" → "print(2)\nprint(3)" ya da "pri" → "print(2)").
        son_satir = onceki.rsplit("\n", 1)[-1]
        if len(son_satir.strip()) >= 3 and devam.startswith(son_satir):
            en_uzun = len(son_satir)
    return onceki + devam[en_uzun:]


def _gorsel_var(mesajlar):
    return any(isinstance(m.get("content"), list) for m in mesajlar)


def dusunme_bilgisi(m):
    """models.dev reasoning_options -> {"efor": [...], "ac_kapa": bool, "butce": bool}."""
    bilgi = {"efor": [], "ac_kapa": False, "butce": False}
    for o in m.get("reasoning_options") or []:
        if not isinstance(o, dict):
            continue
        if o.get("type") == "effort":
            bilgi["efor"] = [str(v) for v in o.get("values") or []]
        elif o.get("type") == "toggle":
            bilgi["ac_kapa"] = True
        elif o.get("type") == "budget_tokens":
            bilgi["butce"] = True
    return bilgi


_DUSUNME_PARAMLARI = ("reasoning_effort", "reasoning", "thinking", "chat_template_kwargs")


def dusunme_ayarla(govde, s, model, dusunme, max_token):
    """Modelin düşünmesini açar ya da kapatır (dusunme: True/False/None).

    Yöntem sağlayıcı ve modele göre seçilir: katalogdaki düşünme seçenekleri
    (models.dev), yoksa yaygın uçların kuralları. Desteklenmeyen parametre
    gönderilirse sohbet_ayrintili 400 hatasında onu atıp yeniden dener.
    """
    if dusunme is None:
        return
    kimlik = s.get("id", "")
    bilgi = (s.get("dusunme") or {}).get(model)
    qwen = re.search(r"qwen3|qwq", (model or "").lower()) is not None
    if s.get("tur") == "anthropic":
        # Claude'da düşünme varsayılan olarak kapalıdır; açıkken bütçe verilir.
        if dusunme and (bilgi is None or bilgi.get("butce")):
            butce = max(1024, min(8000, max_token // 2))
            govde["thinking"] = {"type": "enabled", "budget_tokens": butce}
            govde["max_tokens"] = max(max_token, butce + 1024)
            govde.pop("temperature", None)  # düşünmede sıcaklık sabittir
        return
    if kimlik == "openrouter":
        govde["reasoning"] = {"enabled": bool(dusunme)}
        return
    if not dusunme:
        efor = (bilgi or {}).get("efor") or []
        if "none" in efor:
            govde["reasoning_effort"] = "none"
        elif "minimal" in efor:
            govde["reasoning_effort"] = "minimal"
        elif "low" in efor:
            govde["reasoning_effort"] = "low"
        elif bilgi is None and (kimlik in ("google", "groq") or qwen):
            govde["reasoning_effort"] = "none"
        if s.get("yerel") or qwen or (bilgi or {}).get("ac_kapa"):
            # llama.cpp sunucusu / vLLM / LM Studio: şablona düşünme kapalı bilgisi.
            govde["chat_template_kwargs"] = {"enable_thinking": False}
        if qwen:
            # Qwen3 ailesi bu yönergeyi kullanıcı mesajında okur.
            mesajlar = govde.get("messages") or []
            for i in range(len(mesajlar) - 1, -1, -1):
                if mesajlar[i].get("role") == "user":
                    icerik = mesajlar[i].get("content", "")
                    if isinstance(icerik, list):
                        # Görselli mesaj (Kodi'nin ekran görüntüsü): yönerge
                        # metin parçasına eklenir. Eskiden liste str() ile
                        # metne çevriliyor, görüntü base64 yazı olarak gidiyordu.
                        icerik = list(icerik)
                        j = next((k for k in range(len(icerik) - 1, -1, -1)
                                  if isinstance(icerik[k], dict)
                                  and icerik[k].get("type") == "text"), None)
                        if j is None:
                            icerik.append({"type": "text", "text": "/no_think"})
                        else:
                            icerik[j] = {**icerik[j],
                                         "text": f"{icerik[j].get('text', '')} /no_think"}
                    else:
                        icerik = f"{icerik} /no_think"
                    mesajlar[i] = {**mesajlar[i], "content": icerik}
                    break
    else:
        if s.get("yerel") or qwen or (bilgi or {}).get("ac_kapa"):
            govde["chat_template_kwargs"] = {"enable_thinking": True}


def _yedek_katalog():
    sonuc = {}
    for kimlik, s in YEDEK_KATALOG.items():
        sonuc[kimlik] = _kayit(kimlik, s["ad"], s.get("api") or BILINEN_API.get(kimlik, ""),
                               s.get("tur", "openai"), s["modeller"])
    return sonuc


def _tamamla(katalog):
    """Yerel ve ek sağlayıcıları ekler, sıralı bir kopya döndürür."""
    k = dict(katalog)
    for kimlik, s in EK_SAGLAYICILAR.items():
        k.setdefault(kimlik, _kayit(kimlik, s["ad"], s["api"], "openai",
                                    s["modeller"], s["doc"]))
    for kimlik, s in YEREL_SAGLAYICILAR.items():
        eski = k.get(kimlik)
        k[kimlik] = _kayit(kimlik, s["ad"], s["api"], "openai",
                           eski["modeller"] if eski else (), s["doc"], yerel=True)

    def sira(kimlik):
        return (ONCELIK.index(kimlik) if kimlik in ONCELIK else len(ONCELIK),
                k[kimlik]["ad"].lower())

    return {kimlik: k[kimlik] for kimlik in sorted(k, key=sira)}


def _diskten_yukle():
    try:
        with open(_katalog_dosyasi(), "r", encoding="utf-8") as f:
            veri = json.load(f)
        if isinstance(veri, dict) and isinstance(veri.get("saglayicilar"), dict):
            return veri["saglayicilar"], float(veri.get("zaman") or 0)
    except (OSError, ValueError, TypeError):
        pass
    return None, 0.0


def _diske_yaz(katalog, zaman):
    yol = _katalog_dosyasi()
    try:
        fd, gecici = tempfile.mkstemp(prefix=".ai_katalog_", suffix=".tmp",
                                      dir=os.path.dirname(yol))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"zaman": zaman, "kaynak": KATALOG_URL,
                       "saglayicilar": katalog}, f, ensure_ascii=False)
        os.replace(gecici, yol)
    except OSError:
        pass


def _guncel_listeyi_yansit():
    AI_MODELLERI.clear()
    for kimlik, s in (_KATALOG or {}).items():
        AI_MODELLERI[kimlik] = list(s["modeller"])


def katalog(ag=False):
    """Geçerli katalog ({kimlik: kayıt}). ag=True: internetten tazelemeyi zorlar."""
    global _KATALOG, _KATALOG_ZAMANI, _KATALOG_KAYNAGI
    with _KILIT:
        if _KATALOG is None:
            disk, zaman = _diskten_yukle()
            if disk:
                _KATALOG, _KATALOG_ZAMANI, _KATALOG_KAYNAGI = _tamamla(disk), zaman, "disk"
            else:
                _KATALOG, _KATALOG_ZAMANI, _KATALOG_KAYNAGI = (
                    _tamamla(_yedek_katalog()), 0.0, "yedek")
            _guncel_listeyi_yansit()
    if ag:
        katalog_internetten_tazele()
    elif time.time() - _KATALOG_ZAMANI > KATALOG_OMRU:
        katalog_arka_planda_tazele()
    return _KATALOG


def katalog_internetten_tazele(zaman_asimi=25):
    """models.dev'den indirir. Başarıda True; hata metni ya da False döner."""
    global _KATALOG, _KATALOG_ZAMANI, _KATALOG_KAYNAGI
    try:
        import requests
        yanit = requests.get(KATALOG_URL, timeout=zaman_asimi,
                             headers={"User-Agent": "TurKod-IDE"})
        yanit.raise_for_status()
        islenmis = models_dev_isle(yanit.json())
    except Exception as e:  # noqa: BLE001 - ağ hatası: eski katalog kalır
        print(f"[TurKod] AI kataloğu indirilemedi: {e}", flush=True)
        return False
    if len(islenmis) < 5:
        return False
    simdi = time.time()
    _diske_yaz(islenmis, simdi)
    with _KILIT:
        _KATALOG, _KATALOG_ZAMANI, _KATALOG_KAYNAGI = _tamamla(islenmis), simdi, "internet"
        _guncel_listeyi_yansit()
    return True


def katalog_arka_planda_tazele():
    global _TAZELENIYOR
    with _KILIT:
        if _TAZELENIYOR:
            return
        _TAZELENIYOR = True

    def _calis():
        global _TAZELENIYOR
        try:
            katalog_internetten_tazele()
        finally:
            _TAZELENIYOR = False

    threading.Thread(target=_calis, daemon=True, name="ai-katalog").start()


def katalog_bilgisi():
    return {"kaynak": _KATALOG_KAYNAGI, "zaman": _KATALOG_ZAMANI,
            "url": KATALOG_URL}


def saglayici(kimlik):
    kimlik = saglayici_kimligi(kimlik)
    return katalog().get(kimlik)


def saglayici_ozeti():
    """Arayüze gönderilen hafif liste (model listeleri ayrı alanda)."""
    return [{"id": s["id"], "ad": s["ad"], "yerel": s["yerel"],
             "anahtar_gerekli": s["anahtar_gerekli"], "doc": s["doc"],
             "api": s["api"], "env": s.get("env", [])}
            for s in katalog().values()]


# ----------------------------------------------------------------------
# Canlı model listeleri
# ----------------------------------------------------------------------
_SOHBET_DISI = ("embed", "whisper", "tts", "transcribe", "audio", "image",
                "dall-e", "moderation", "guard", "realtime", "rerank", "search")


def api_modelleri(kimlik, anahtar="", api=None, zaman_asimi=8):
    """Sağlayıcının /models ucundan güncel model listesini alır (OpenAI ve
    Anthropic biçimi). Hata olursa istisna fırlatır."""
    import requests
    s = saglayici(kimlik) or _kayit(kimlik, kimlik, api or "")
    taban = (api or s["api"]).rstrip("/")
    if not taban:
        raise ValueError("Bu sağlayıcı için API adresi yok.")
    basliklar = _basliklar(s, anahtar)
    yanit = requests.get(f"{taban}/models", headers=basliklar, timeout=zaman_asimi)
    if yanit.status_code >= 400:
        raise ValueError(_http_hatasi(yanit, s["ad"], ""))
    veri = yanit.json()
    ogeler = veri.get("data") if isinstance(veri, dict) else veri
    adlar = []
    for m in ogeler or []:
        mid = m.get("id") if isinstance(m, dict) else str(m)
        if mid and not any(k in mid.lower() for k in _SOHBET_DISI):
            adlar.append(mid)
    return sorted(set(adlar))


def yerel_modelleri_sorgula(kimlik):
    """Yerel sunucunun yüklü modelleri; sunucu kapalıysa boş liste."""
    try:
        return api_modelleri(kimlik, zaman_asimi=1.5)
    except Exception:  # noqa: BLE001
        return []


def modelleri_guncelle(kimlik, anahtar="", api=None, katalog=True):
    """Kataloğu internetten tazeler ve (anahtar varsa) sağlayıcının kendi
    /models ucundan canlı listeyi alır. {"ok", "modeller", "kaynak"}."""
    kimlik = saglayici_kimligi(kimlik)
    if katalog:
        katalog_internetten_tazele()
    s = saglayici(kimlik)
    canli = []
    hata = None
    if s and (anahtar or s["yerel"] or kimlik == "ozel"):
        try:
            canli = api_modelleri(kimlik, anahtar, api)
        except Exception as e:  # noqa: BLE001
            hata = str(e)
    if canli and s:
        with _KILIT:
            # Katalogdaki sıralama (yeni modeller önde) korunur, canlıda
            # olmayanlar çıkarılır, katalogda olmayanlar sona eklenir.
            eski = [m for m in s["modeller"] if m in canli]
            s["modeller"] = eski + [m for m in canli if m not in eski]
            AI_MODELLERI[kimlik] = list(s["modeller"])
    return {"ok": True, "modeller": list(s["modeller"]) if s else [],
            "canli": bool(canli), "hata": hata, **katalog_bilgisi()}


# Geriye uyumluluk (eski çağıranlar).
def groq_modelleri_guncelle(api_key=None):
    return modelleri_guncelle("groq", api_key or "")["canli"]


def openai_modelleri_guncelle(api_key=None):
    return modelleri_guncelle("openai", api_key or "")["canli"]


# ----------------------------------------------------------------------
# Sohbet isteği
# ----------------------------------------------------------------------
class AIIstekHatasi(Exception):
    """Kullanıcıya gösterilebilir Türkçe hata.

    tur: "cok_uzun" (istek modelin ya da dakikalık token sınırına sığmadı),
    "sinir" (hız / kullanım sınırı), "anahtar", "model", "baglanti" (sunucuya
    ulaşılamadı, zaman aşımı, sunucu hatası 5xx) ya da "" (diğer).
    bekle: sağlayıcının söylediği bekleme süresi (saniye), biliniyorsa."""

    def __init__(self, mesaj, tur="", bekle=None):
        super().__init__(mesaj)
        self.tur = tur
        self.bekle = bekle


def _basliklar(s, anahtar):
    b = {"Content-Type": "application/json", "User-Agent": "TurKod-IDE"}
    if s.get("tur") == "anthropic":
        b["anthropic-version"] = "2023-06-01"
        if anahtar:
            b["x-api-key"] = anahtar
    elif anahtar:
        b["Authorization"] = f"Bearer {anahtar}"
    if s.get("id") == "openrouter":
        b["HTTP-Referer"] = "https://github.com/YusufX-sys/turkod-ide"
        b["X-Title"] = "TurKod IDE"
    return b


def _hata_metni(yanit):
    try:
        veri = yanit.json()
    except ValueError:
        return (yanit.text or "")[:300]
    hata = veri.get("error") if isinstance(veri, dict) else None
    if isinstance(hata, dict):
        return str(hata.get("message") or hata)[:300]
    if isinstance(hata, str):
        return hata[:300]
    if isinstance(veri, list) and veri and isinstance(veri[0], dict):
        return _hata_metni_sozluk(veri[0])
    return str(veri)[:300]


def _hata_metni_sozluk(d):
    hata = d.get("error")
    if isinstance(hata, dict):
        return str(hata.get("message") or hata)[:300]
    return str(d)[:300]


def _hata_turu(yanit):
    kod = yanit.status_code
    kucuk = _hata_metni(yanit).lower()
    if kod == 413 or "too large" in kucuk or "context length" in kucuk or \
            "maximum context" in kucuk:
        return "cok_uzun"
    if kod == 429 or "rate limit" in kucuk or "quota" in kucuk:
        return "sinir"
    if kod in (401, 403) or "api key" in kucuk or "api_key" in kucuk:
        return "anahtar"
    if kod == 404:
        return "model"
    if kod >= 500:
        # Sağlayıcının ya da (Kaggle/Colab tüneli gibi) uzak sunucunun
        # kendisi çalışmıyor: yedek modele geçilebilir.
        return "baglanti"
    return ""


def bekleme_suresi(yanit):
    """Sınıra takılan istekte sağlayıcının söylediği bekleme (saniye) ya da
    None. Groq/OpenAI: retry-after (saniye) ya da x-ratelimit-reset-tokens
    ("7.66s", "1m2.5s"); hata metninde "try again in 2.5s"."""
    try:
        basliklar = yanit.headers or {}
    except Exception:
        basliklar = {}
    v = basliklar.get("retry-after") if hasattr(basliklar, "get") else None
    try:
        if v is not None:
            return max(0.0, float(v))
    except (TypeError, ValueError):
        pass
    adaylar = []
    if hasattr(basliklar, "get"):
        adaylar.append(str(basliklar.get("x-ratelimit-reset-tokens") or ""))
    m = re.search(r"try again in ([0-9.hms]+)", _hata_metni(yanit), re.I)
    if m:
        adaylar.append(m.group(1))
    for a in adaylar:
        s = _sure_coz(a)
        if s is not None:
            return s
    return None


_SURE = re.compile(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?"
                   r"(?:(\d+(?:\.\d+)?)ms)?$")


# Sağlayıcının bildirdiği dakikalık token payı: (kimlik, model) ->
# (kalan, sınır, payın tamamen dolacağı an). Groq / OpenAI her cevapta
# x-ratelimit-remaining-tokens ve x-ratelimit-reset-tokens başlıklarını
# gönderir; pay yetmeyecekse istek gönderilmeden önce kısa bir süre beklenir
# (kullanıcı hata yerine biraz daha uzun "Düşünüyorum..." görür).
_TOKEN_PAYI = {}
_TOKEN_PAYI_KILIDI = threading.Lock()
# (sağlayıcı, model) -> sağlayıcının adını verip reddettiği düşünme parametreleri.
_DESTEKSIZ_PARAMLAR = {}


def _sure_coz(metin):
    metin = str(metin or "").strip().rstrip(".")
    e = _SURE.match(metin) if metin else None
    if e and any(e.groups()):
        sa, dk, sn, ms = (float(x) if x else 0.0 for x in e.groups())
        return sa * 3600 + dk * 60 + sn + ms / 1000
    return None


def token_payini_kaydet(kimlik, model, yanit):
    try:
        b = yanit.headers or {}
        kalan = b.get("x-ratelimit-remaining-tokens")
        sinir = b.get("x-ratelimit-limit-tokens")
        sure = _sure_coz(b.get("x-ratelimit-reset-tokens"))
    except Exception:
        return
    if kalan is None or sure is None:
        return
    try:
        kalan, sinir = float(kalan), float(sinir or 0)
    except (TypeError, ValueError):
        return
    with _TOKEN_PAYI_KILIDI:
        _TOKEN_PAYI[(kimlik, model)] = (kalan, sinir, time.monotonic() + sure)


def token_payi_bekleme(kimlik, model, tahmini):
    """Bu modelin dakikalık payı tahmini kadar token'a şu an yetmiyorsa
    dolması için gereken saniye; yetiyorsa ya da bilinmiyorsa 0."""
    with _TOKEN_PAYI_KILIDI:
        kayit = _TOKEN_PAYI.get((kimlik, model))
    if not kayit:
        return 0.0
    kalan, sinir, dolma = kayit
    simdi = time.monotonic()
    if kalan >= tahmini or dolma <= simdi:
        return 0.0
    tam = dolma - simdi
    return tam if sinir <= kalan else min(tam, tam * (tahmini - kalan) / (sinir - kalan))


def token_payini_bekle(kimlik, model, tahmini, en_uzun):
    """Pay bu isteğe yetmeyecekse yetecek kadar (en çok en_uzun saniye)
    bekler. Bekleyemeyecekse beklemez; sağlayıcı yine de deneyebilir."""
    with _TOKEN_PAYI_KILIDI:
        kayit = _TOKEN_PAYI.get((kimlik, model))
    if not kayit:
        return 0.0
    kalan, sinir, dolma = kayit
    simdi = time.monotonic()
    if kalan >= tahmini or dolma <= simdi:
        return 0.0
    tam = dolma - simdi
    # Pay sürekli dolar: eksik kadarının dolma süresi (tamamı en çok tam süre).
    bekle = tam if sinir <= kalan else min(tam, tam * (tahmini - kalan) / (sinir - kalan))
    if bekle > en_uzun:
        return 0.0
    time.sleep(bekle + 0.3)
    return bekle


def _http_hatasi(yanit, ad, model):
    kod = yanit.status_code
    ayrinti = _hata_metni(yanit)
    kucuk = ayrinti.lower()
    if kod in (401, 403) or "api key" in kucuk or "api_key" in kucuk:
        return f"API anahtarı geçersiz ya da bu modele yetkisi yok ({ad})."
    if kod == 404 or ("model" in kucuk and ("not found" in kucuk or "does not exist" in kucuk)):
        return f"Model bulunamadı: {model} ({ad}). Ayarlardan başka bir model seçin."
    if kod == 413 or "too large" in kucuk or "context length" in kucuk:
        return "İstek çok uzun. Kodu kısaltın ya da daha büyük bağlamlı bir model seçin."
    if kod == 429 or "rate limit" in kucuk or "quota" in kucuk:
        return "Kullanım limiti doldu. Biraz bekleyin ya da başka bir anahtar/model deneyin."
    if "decommissioned" in kucuk or "deprecated" in kucuk:
        return f"Model kullanımdan kaldırılmış: {model}. Ayarlardan başka bir model seçin."
    return f"{ad} hatası (HTTP {kod}): {ayrinti}"


_DUSUNCE = re.compile(r"<(think|thinking|reasoning)>(.*?)</\1>\s*", re.DOTALL | re.IGNORECASE)
_DUSUNCE_SONU = re.compile(r"</(think|thinking|reasoning)>", re.IGNORECASE)
_DUSUNCE_BASI = re.compile(r"<(think|thinking|reasoning)>", re.IGNORECASE)


def dusunce_ayir(metin):
    """Akıl yürüten modellerin (DeepSeek-R1, Qwen3, QwQ ...) düşünme metnini
    yanıttan ayırır. Döndürür: (düşünce, yanıt).

    Görülen biçimler:
    * <think> ... </think> yanıt
    * düşünce ... </think> yanıt — açılış etiketi sohbet şablonunda yazıldığı
      için yanıtta yalnızca kapanış gelir (eskiden düşünce yanıta sızıyordu)
    * <think> ... (kapanmamış: token sınırında kesildi; yanıt yok)
    """
    metin = metin or ""
    dusunceler = []

    def topla(m):
        dusunceler.append(m.group(2).strip())
        return ""

    metin = _DUSUNCE.sub(topla, metin)
    son = None
    for son in _DUSUNCE_SONU.finditer(metin):
        pass
    if son is not None:  # açılışı olmayan kapanış: öncesi düşüncedir
        dusunceler.append(metin[:son.start()].strip())
        metin = metin[son.end():]
    bas = _DUSUNCE_BASI.search(metin)
    if bas is not None:  # kapanmamış düşünce
        dusunceler.append(metin[bas.end():].strip())
        metin = metin[:bas.start()]
    return "\n\n".join(d for d in dusunceler if d), metin.strip()


def dusunceyi_temizle(metin):
    """Yanıttan düşünme metnini atar (yalnızca yanıt kalır)."""
    return dusunce_ayir(metin)[1]


def sohbet(kimlik, model, mesajlar, sistem="", sicaklik=0.7, max_token=4096,
           anahtar="", api=None, zaman_asimi=90, dusunme=None):
    """Tek bir sohbet isteği gönderir, yanıt metnini (düşünme olmadan) döndürür."""
    return sohbet_ayrintili(kimlik, model, mesajlar, sistem, sicaklik, max_token,
                            anahtar, api, zaman_asimi, dusunme)["cevap"]


def sohbet_ayrintili(kimlik, model, mesajlar, sistem="", sicaklik=0.7, max_token=4096,
                     anahtar="", api=None, zaman_asimi=90, dusunme=None, en_uzun_bekleme=12,
                     araclar=None, arac_zorunlu=False):
    """Tek bir sohbet isteği gönderir. Döndürür: {"cevap", "dusunce"}.

    mesajlar: [{"role": "user"|"assistant", "content": str}]
    arac_zorunlu: model araçlardan birini çağırmak zorunda (tool_choice
    "required"; desteklemeyen sağlayıcıda "auto"ya dönülür).
    Hata durumunda Türkçe AIIstekHatasi fırlatır.
    """
    import requests
    kimlik = saglayici_kimligi(kimlik)
    s = saglayici(kimlik)
    if s is None:
        s = _kayit(kimlik, kimlik, api or "")
    taban = (api or s["api"] or "").rstrip("/")
    if not taban:
        raise AIIstekHatasi("Bu sağlayıcı için API adresi girilmemiş (Ayarlar → AI Asistan).")
    if s["anahtar_gerekli"] and not anahtar:
        raise AIIstekHatasi(f"{s['ad']} için API anahtarı girilmemiş (Ayarlar → AI Asistan).")
    if not model:
        raise AIIstekHatasi("Model seçilmemiş (Ayarlar → AI Asistan).")

    basliklar = _basliklar(s, anahtar)
    try:
        sicaklik = float(sicaklik)
    except (TypeError, ValueError):
        sicaklik = 0.7
    try:
        max_token = max(16, int(max_token))
    except (TypeError, ValueError):
        max_token = 4096

    if s["tur"] == "anthropic":
        url = f"{taban}/messages"
        govde = {"model": model, "max_tokens": max_token,
                 "messages": [{**m, "content": _anthropic_icerik(m.get("content"))}
                              for m in mesajlar],
                 "temperature": min(sicaklik, 1.0)}
        if sistem:
            govde["system"] = sistem
    else:
        url = f"{taban}/chat/completions"
        govde = {"model": model,
                 "messages": ([{"role": "system", "content": sistem}] if sistem else [])
                 + list(mesajlar),
                 "temperature": sicaklik}
        # OpenAI'nin yeni (akıl yürüten) modelleri max_tokens'ı reddeder.
        if kimlik == "openai":
            govde["max_completion_tokens"] = max_token
        else:
            govde["max_tokens"] = max_token
    # dusunme: True = model düşünsün, False = düşünmesin, None = varsayılan.
    dusunme_ayarla(govde, s, model, dusunme, max_token)
    # Bu modelin daha önce reddettiği parametreler hiç gönderilmez (her
    # istekte önce 400 alıp yeniden denemek, isteği iki kat yavaşlatıyordu).
    for p in _DESTEKSIZ_PARAMLAR.get((kimlik, model), ()):
        govde.pop(p, None)
    # araclar: OpenAI biçimindeki işlev tanımları (Kodi'nin "eylem" aracı).
    # Desteklemeyen sağlayıcıda kaldırılıp yeniden denenir.
    if araclar and s["tur"] != "anthropic":
        govde["tools"] = list(araclar)
        govde["tool_choice"] = "required" if arac_zorunlu else "auto"
    arac_adlari = {str(((a or {}).get("function") or {}).get("name") or "")
                   for a in araclar or []}

    # Dakikalık token payı bu isteğe yetmeyecekse önce biraz beklenir.
    tahmini = (len(sistem or "") + sum(_icerik_uzunlugu(m.get("content")) for m in mesajlar)) / 2.8
    token_payini_bekle(kimlik, model, tahmini + min(max_token, 2048), en_uzun_bekleme)

    yanit = None
    gorsel_atildi = False
    arac_denemesi = 0
    for _deneme in range(6):
        try:
            yanit = requests.post(url, headers=basliklar, json=govde, timeout=zaman_asimi)
        except requests.exceptions.ConnectionError:
            if s["yerel"]:
                raise AIIstekHatasi(
                    f"{s['ad']} sunucusuna ulaşılamıyor. Sunucunun çalıştığını denetleyin "
                    "(Eklenti Özellikleri → Yerel AI Modelleri) ya da başka bir sağlayıcı "
                    "seçin.", tur="baglanti") from None
            raise AIIstekHatasi("Bağlantı hatası! İnternetinizi kontrol edin.",
                                tur="baglanti") from None
        except requests.exceptions.Timeout:
            raise AIIstekHatasi(
                f"{s['ad']} {zaman_asimi} saniyede yanıt vermedi. Daha küçük bir model "
                "deneyin ya da sonra tekrar deneyin.", tur="baglanti") from None
        if yanit.status_code != 400:
            break
        if _gorsel_var(list(mesajlar)) and not govde.get("_gorselsiz"):
            # Model görsel kabul etmiyor: görüntü atılıp yeniden denenir.
            mesajlar = _gorselsiz(list(mesajlar))
            if s["tur"] == "anthropic":
                govde["messages"] = mesajlar
            else:
                govde["messages"] = ([{"role": "system", "content": sistem}] if sistem else []) \
                    + mesajlar
            gorsel_atildi = True
            continue
        # Bazı modeller sıcaklık ya da token parametresini desteklemez: hata
        # iletisine göre parametre düzeltilip bir kez daha denenir.
        ayrinti = _hata_metni(yanit).lower()
        dusunme_param = [p for p in _DUSUNME_PARAMLARI if p in govde]
        # Hata iletisinde adı geçen düşünme ayarı ("property
        # 'chat_template_kwargs' is unsupported"): yalnızca o atılır. Eskiden
        # hepsi atılıyordu; reasoning_effort da gidince Qwen gibi modeller
        # düşünmeye başlıyor, cevap payını düşünerek bitiriyordu.
        adi_gecen = [p for p in dusunme_param if p in ayrinti]
        arac_hatasi = ("called a tool" in ayrinti or "tool_use_failed" in ayrinti
                       or "tool call" in ayrinti or "failed to call a function" in ayrinti
                       or "tool choice" in ayrinti)
        if adi_gecen:
            for p in adi_gecen:
                govde.pop(p, None)
            _DESTEKSIZ_PARAMLAR.setdefault((kimlik, model), set()).update(adi_gecen)
        elif dusunme_param and not arac_hatasi and any(k in ayrinti for k in (
                "reasoning", "thinking", "chat_template_kwargs", "effort", "unrecognized",
                "unknown", "extra", "not supported", "unsupported")):
            # Model bu düşünme ayarını desteklemiyor: varsayılanıyla çalışsın.
            for p in dusunme_param:
                govde.pop(p, None)
        elif "tools" in govde and any(k in ayrinti for k in (
                "tools are not supported", "does not support tools", "tool use is not supported",
                "tools is not supported", "function calling is not supported",
                "does not support function")):
            govde.pop("tools", None)
            govde.pop("tool_choice", None)
        elif govde.get("tool_choice") == "required" and "tool_choice" in ayrinti \
                and not arac_hatasi:
            # Sağlayıcı "required" seçeneğini tanımıyor.
            govde["tool_choice"] = "auto"
        elif arac_hatasi and "eylem" in arac_adlari and (
                kurtarilan := basarisiz_cagri_eylemleri(_basarisiz_uretim(yanit))):
            # Model işi yapmak istedi ama çağrısı reddedildi (şemaya uymayan
            # alan, kendi "browser" aracı ...): çağrıdaki iş kurtarılır.
            blok = "\n".join(json.dumps(e, ensure_ascii=False) for e in kurtarilan)
            # kurtarildi: bu bir model metni değil; kesilen cevabın "devamı"
            # olarak koda yapıştırılmaz (bkz. ide_core._ai_tek_cagri).
            return {"cevap": "```eylem\n" + blok + "\n```", "dusunce": "", "kullanim": {},
                    "kurtarildi": True}
        elif arac_hatasi and govde.get("tool_choice") == "required":
            # Model zorunlu çağrıyı yapamadı: serbest bırakılıp yeniden denenir.
            govde["tool_choice"] = "auto"
        elif arac_hatasi and arac_denemesi < 2:
            # gpt-oss gibi modeller kendi yerleşik araçlarını ("browser",
            # "python") çağırmaya kalkıyor; araç tanımlı olmadığı için sağlayıcı
            # reddediyor. Uyarıyla yeniden denenir. Eskiden "tarayıcı aracın
            # yok, düz metinle cevap ver" deniyordu: Kodi de tarayıcıda iş
            # istenince "Hadi açalım!" deyip hiçbir şey yapmıyordu.
            arac_denemesi += 1
            if "eylem" in arac_adlari:
                uyari = ("\n\nÖNEMLİ: Tek aracın \"eylem\" aracıdır; \"browser\", \"python\", "
                         "\"search\" gibi araçlar yok. Tarayıcıda bir iş (site açmak, aramak, "
                         "tıklamak) için de \"eylem\" aracını {\"eylem\": \"tarayici\", ...} ile "
                         "çağır ya da cevabın sonuna ```eylem bloğu yaz.")
            else:
                uyari = ("\n\nÖNEMLİ: Hiçbir araç (tool / function) çağırma. Programda ya da "
                         "tarayıcıda bir iş yapılacaksa cevabın sonuna ```eylem bloğu yaz.")
            if s["tur"] == "anthropic":
                govde["system"] = (govde.get("system") or "") + uyari
            else:
                ilk = govde["messages"][0] if govde.get("messages") else None
                if ilk and ilk.get("role") == "system" and uyari not in ilk["content"]:
                    govde["messages"] = [{**ilk, "content": ilk["content"] + uyari}] \
                        + govde["messages"][1:]
                elif not ilk or ilk.get("role") != "system":
                    govde["messages"] = [{"role": "system", "content": uyari.strip()}] \
                        + govde.get("messages", [])
            govde["temperature"] = 0.3
        elif "temperature" in ayrinti and "temperature" in govde:
            govde.pop("temperature")
        elif "max_completion_tokens" in ayrinti and "max_completion_tokens" in govde:
            govde["max_tokens"] = govde.pop("max_completion_tokens")
        elif "max_tokens" in ayrinti and "max_tokens" in govde and s["tur"] != "anthropic":
            govde["max_completion_tokens"] = govde.pop("max_tokens")
        else:
            break

    # Hız sınırı: sağlayıcı kısa bir bekleme söylüyorsa kullanıcıya hata
    # göstermeden bir kez bekleyip yeniden denenir.
    if yanit.status_code == 429:
        bekle = bekleme_suresi(yanit)
        if bekle is not None and bekle <= en_uzun_bekleme:
            time.sleep(bekle + 0.3)
            try:
                yanit = requests.post(url, headers=basliklar, json=govde, timeout=zaman_asimi)
            except requests.exceptions.RequestException:
                pass

    token_payini_kaydet(kimlik, model, yanit)
    if yanit.status_code >= 400:
        raise AIIstekHatasi(_http_hatasi(yanit, s["ad"], model), tur=_hata_turu(yanit),
                            bekle=bekleme_suresi(yanit))
    try:
        veri = yanit.json()
    except ValueError:
        raise AIIstekHatasi(f"{s['ad']} geçersiz bir yanıt döndürdü.") from None

    ayri_dusunce = ""
    kesildi = False
    if s["tur"] == "anthropic":
        kesildi = veri.get("stop_reason") == "max_tokens"
        bloklar = [b for b in veri.get("content") or [] if isinstance(b, dict)]
        metin = "".join(b.get("text", "") for b in bloklar if b.get("type") == "text")
        ayri_dusunce = "\n\n".join(b.get("thinking", "") for b in bloklar
                                    if b.get("type") == "thinking")
        if not metin.strip() and veri.get("stop_reason") == "refusal":
            return {"cevap": "⚠️ Model bu isteği yanıtlamayı reddetti.", "dusunce": "",
                    "uyari": True}
    else:
        secim = (veri.get("choices") or [{}])[0]
        kesildi = secim.get("finish_reason") == "length"
        mesaj = secim.get("message") or {}
        metin = mesaj.get("content") or ""
        if isinstance(metin, list):  # bazı sağlayıcılar parça listesi döndürür
            metin = "".join(p.get("text", "") for p in metin if isinstance(p, dict))
        metin = _arac_cagrilarini_ekle(metin, mesaj.get("tool_calls"))
        # DeepSeek / Groq / OpenRouter düşünmeyi ayrı alanda gönderir.
        ayri_dusunce = mesaj.get("reasoning_content") or mesaj.get("reasoning") or ""
        if not isinstance(ayri_dusunce, str):
            ayri_dusunce = ""
        if not metin.strip() and secim.get("finish_reason") == "length":
            return {"cevap": ("⚠️ Yanıt token sınırına takıldı (model düşünürken "
                              "kesilmiş olabilir). Ayarlar → AI Asistan'dan 'En Fazla "
                              "Token' değerini artırın."),
                    "dusunce": dusunce_ayir(metin)[0] or ayri_dusunce, "uyari": True}
    dusunce, metin = dusunce_ayir(metin)
    dusunce = "\n\n".join(d for d in (ayri_dusunce.strip(), dusunce) if d)
    # usage: kaç token gitti, kaçı önbellekten geldi (prompt_tokens_details.
    # cached_tokens; Anthropic: cache_read_input_tokens).
    kullanim = veri.get("usage") if isinstance(veri.get("usage"), dict) else {}
    sonuc = {"cevap": metin or "⚠️ Model boş yanıt döndürdü.", "dusunce": dusunce,
             "kullanim": kullanim}
    if not metin:
        # uyari: cevap modelin metni değil, programın uyarısı. Eskiden kesilen
        # cevabın devamı yerine gelince koda yapıştırılıyordu
        # ("x = i*2⚠️ Model boş yanıt döndürdü.").
        sonuc["uyari"] = True
    if gorsel_atildi:
        sonuc["gorsel_atildi"] = True
    if kesildi and metin:
        # Cevap token sınırında yarıda kesildi: çağıran devamını isteyebilir
        # (DEVAM_ISTEMI, devami_birlestir).
        sonuc["kesildi"] = True
    return sonuc
