"""Kütüphane çıktılarını Türkçeleştirir.

Kullanıcı programı çalışırken Ursina, Panda3D, pygame ve Python'un kendisi
terminale İngilizce bilgi/uyarı satırları yazar ("info: Using primary
monitor...", ":display:windisplay(warning): ...", "Known pipe types:" ...).
Yeni başlayan biri bunları anlayamıyordu. Panda3D satırları C++ katmanından
doğrudan yazıldığı için Python'un print'i üzerinden yakalanamaz; çeviri bu
yüzden süreç çıktısını okuyan tarafta (IDE terminali, .trpy terminal
penceresi) satır satır yapılır.

Yalnızca tanınan satırlar değişir; kullanıcının kendi çıktısı aynen geçer.
Tanınan satırlardaki ANSI renk kodları (Ursina uyarıları "\\033[93m" ile
başlar) da silinir: iki terminal de bunları işlemiyor, "[93m" gibi çöp
görünüyordu.
"""
import re
import threading
import time

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# --------------------------------------------------------------------------
# Panda3D bildirimleri:  ":kategori(seviye): ileti"  /  ":a:b(seviye): ileti"
# --------------------------------------------------------------------------
_PANDA_SEVIYE = {
    "warning": "Uyarı",
    "error": "Hata",
    "info": "Bilgi",
    "debug": "Ayıklama",
    "spam": "Ayrıntı",
    "fatal": "Ölümcül hata",
}

_PANDA_KATEGORI = {
    "display": "ekran",
    "windisplay": "ekran",
    "wgldisplay": "OpenGL ekranı",
    "glgsg": "OpenGL",
    "glxdisplay": "ekran",
    "dxgsg9": "DirectX",
    "prc": "yapılandırma",
    "pnmimage": "resim",
    "png": "PNG resmi",
    "jpg": "JPG resmi",
    "gobj": "grafik nesnesi",
    "loader": "yükleyici",
    "Loader": "yükleyici",
    "audio": "ses",
    "openal": "ses",
    "fmod": "ses",
    "movies": "video",
    "ffmpeg": "video",
    "shader": "gölgelendirici",
    "text": "metin",
    "express": "temel",
    "util": "yardımcı",
    "putil": "yardımcı",
    "pgraph": "sahne",
    "egg": "model",
    "egg2pg": "model",
    "gltf": "model",
    "assimp": "model",
    "chan": "animasyon",
    "char": "karakter",
    "collide": "çarpışma",
    "task": "görev",
    "event": "olay",
    "device": "aygıt",
    "framework": "çatı",
    "linmath": "matematik",
    "ShowBase": "ShowBase",
    "Messenger": "ileti",
    "TaskManager": "görev yöneticisi",
}

_PANDA_SATIR = re.compile(r"^:(?P<kat>[\w:]+?)\((?P<sev>\w+)\): ?(?P<ileti>.*)$")

# (desen, Türkçe) — Panda3D iletisinin gövdesi için.
_PANDA_ILETILERI = [
    (r"SetForegroundWindow\(\) failed!?",
     "Pencere öne getirilemedi (önemsiz, programı etkilemez)."),
    (r"Could not find icon filename (?P<y>.+)",
     r"Pencere simgesi bulunamadı: \g<y> (önemsiz)."),
    (r"changing default value for ConfigVariable (?P<ad>\S+) from '(?P<a>.*)' to '(?P<b>.*)'\.?",
     r"'\g<ad>' ayarının varsayılan değeri '\g<a>' yerine '\g<b>' yapıldı (önemsiz)."),
    (r"iCCP: known incorrect sRGB profile",
     "Resmin içindeki renk profili (sRGB) hatalı; resim yine de yüklenir (önemsiz)."),
    (r"iCCP: (?P<m>.+)",
     r"Resmin renk profilinde sorun: \g<m> (çoğunlukla önemsiz)."),
    (r"Couldn't load file (?P<y>.+?): (?:does not exist|not found on model path).*",
     r"Dosya yüklenemedi: \g<y> (dosya bulunamadı)."),
    (r"Could(?:n't| not) (?:load|read) (?:file |texture |image )?(?P<y>.+?)\.?",
     r"Dosya yüklenemedi: \g<y>"),
    (r"Could(?:n't| not) open (?:file )?(?P<y>.+?)\.?",
     r"Açılamadı: \g<y>"),
    (r"Unable to (?:open|read) (?P<y>.+?)\.?",
     r"Açılamadı: \g<y>"),
    (r"(?P<y>.+?) is not a PNG file\.?",
     r"\g<y> bir PNG dosyası değil."),
    (r"Shader input (?P<ad>\S+) is not present\.?",
     r"Gölgelendiriciye '\g<ad>' girdisi verilmemiş."),
    (r"Could not open window\.?",
     "Pencere açılamadı."),
    (r"Unable to set window properties: (?P<m>.+)",
     r"Pencere ayarları uygulanamadı: \g<m>"),
    (r"Texture (?P<ad>.+?) has a non-power-of-2 size.*",
     r"'\g<ad>' dokusunun boyutu 2'nin kuvveti değil (önemsiz)."),
]
_PANDA_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _PANDA_ILETILERI]

# --------------------------------------------------------------------------
# Ursina:  "info: ..."  /  "\033[93mwarning: ... \033[0m"  ve düz print'ler
# --------------------------------------------------------------------------
_URSINA_ONEK = re.compile(r"^(?P<onek>info|warning): ?(?P<ileti>.*?)\s*$")
_URSINA_ONEK_TR = {"info": "Bilgi", "warning": "Uyarı"}


def _vektor_sade(metin):
    """'Vec2(192, 108)' -> '(192, 108)'."""
    return re.sub(r"\bVec[234]\(", "(", metin)


def _monitor(m):
    ad = re.sub(r"[\\.']", "", m.groupdict().get("ad") or "")
    ek = f" ({ad})" if ad else ""
    return f"Ana monitör kullanılıyor: {m.group('w')}x{m.group('h')}{ek}"


# Ursina iletilerinin gövdesi ("info:"/"warning:" öneki çıkarılmış hâli).
_URSINA_ILETILERI = [
    (r"Using primary monitor: Monitor\(.*?width=(?P<w>\d+), height=(?P<h>\d+).*?name=(?P<ad>'[^']*').*\)",
     _monitor),
    (r"Using primary monitor: Monitor\(.*?width=(?P<w>\d+), height=(?P<h>\d+).*\)",
     _monitor),
    (r"No primary monitor found, using first monitor instead",
     "Ana monitör bulunamadı, ilk monitör kullanılıyor."),
    (r"No monitors found", "Hiç monitör bulunamadı."),
    (r"changed aspect ratio: (?P<a>\S+) -> (?P<b>\S+)",
     r"Pencerenin en-boy oranı değişti: \g<a> -> \g<b>"),
    (r"set camera shader to: (?P<g>.+)", r"Kamera gölgelendiricisi ayarlandı: \g<g>"),
    (r"loaded settings from ursina_settings\.py successfully",
     "ursina_settings.py ayarları yüklendi."),
    (r"(?:warning: )?ursina_settings\.py error: (?P<h>.+)",
     r"ursina_settings.py dosyasında hata: \g<h>"),
    (r"missing texture: '(?P<ad>.*)'",
     r"Doku (resim) bulunamadı: '\g<ad>'. Dosyanın programla aynı klasörde ya da "
     r"'textures' klasöründe olduğundan emin olun."),
    (r"missing model: '(?P<ad>.*)'",
     r"Model bulunamadı: '\g<ad>'. Dosya adını ve klasörünü kontrol edin."),
    (r"missing audio clip: (?P<ad>.+)", r"Ses dosyası bulunamadı: \g<ad>"),
    (r"audio not found: (?P<ad>.+)", r"Ses bulunamadı: \g<ad>"),
    (r"track not found: (?P<ad>.+)", r"Müzik parçası bulunamadı: \g<ad>"),
    (r"Invalid audio group: (?P<ad>.+)", r"Geçersiz ses grubu: \g<ad>"),
    (r"missing font: (?P<ad>.+)", r"Yazı tipi bulunamadı: \g<ad>"),
    (r"missing shader: (?P<ad>.+)", r"Gölgelendirici bulunamadı: \g<ad>"),
    (r"missing particle system: (?P<ad>.+)", r"Parçacık sistemi bulunamadı: \g<ad>"),
    (r"font not loaded, so Text\.width may be wrong",
     "Yazı tipi yüklenemedi; metin genişliği yanlış hesaplanabilir."),
    (r"Tried to instantiate Entity before Ursina\. Please create an instance of Ursina first "
     r"\(app = Ursina\(\)\)(?P<ek>.*)",
     r"Ursina başlatılmadan varlık oluşturulmaya çalışıldı. Önce "
     r"'uygulama = ursina_başlat()' satırını yazın.\g<ek>"),
    (r"look_at axis as str is deprecated.*",
     "hedefe_bak() için ekseni metin olarak vermek artık desteklenmiyor; "
     "vektör3.ileri, vektör3.yukarı gibi yönler kullanın."),
    (r"error: disabling vsync during runtime is not yet implemented",
     "Dikey eşitleme (vsync) program çalışırken kapatılamaz."),
    (r"error in obj file line: (?P<n>\S+) : (?P<s>.*)",
     r"OBJ model dosyasında hatalı satır \g<n>: \g<s>"),
    (r"Error: Trying to load \.blend file, but no blender installation was found\..*",
     ".blend modeli yüklenemedi: bilgisayarda Blender kurulu değil. Modeli .obj/.glb "
     "olarak dışa aktarın."),
    (r"(?P<v>.+) has no animation: (?P<a>.+)", r"\g<v> nesnesinde '\g<a>' animasyonu yok."),
]

# Öneksiz Ursina / Panda3D / pygame satırları (tam satır).
_DUZ_SATIRLAR = [
    (r"Known pipe types:", "Kullanılabilir grafik altyapıları:"),
    (r"(?P<b>\s+)wglGraphicsPipe", r"\g<b>wglGraphicsPipe (OpenGL)"),
    (r"\((?P<n>\d+) aux display modules? not yet loaded\.\)",
     r"(\g<n> yardımcı ekran modülü henüz yüklenmedi; önemsiz.)"),
    (r"set window position: (?P<v>.+)",
     lambda m: f"Pencere konumu ayarlandı: {_vektor_sade(m.group('v'))}"),
    (r"-*set size to: (?P<v>.+)",
     lambda m: f"Pencere boyutu ayarlandı: {_vektor_sade(m.group('v'))}"),
    (r"set fullscreen to (?P<v>.+)", r"Tam ekran: \g<v>"),
    (r"package_folder: (?P<y>.+)", r"Ursina klasörü: \g<y>"),
    (r"asset_folder: (?P<y>.+)", r"Proje klasörü (resim, model, ses dosyaları burada aranır): \g<y>"),
    (r"os: (?P<v>Windows|Linux|Darwin)", r"İşletim sistemi: \g<v>"),
    (r"python version: (?P<v>.+)", r"Python sürümü: \g<v>"),
    (r"ursina version: (?P<v>.+)", r"Ursina sürümü: \g<v>"),
    (r"development mode: (?P<v>.+)", r"Geliştirme modu: \g<v>"),
    (r"application successfully started", "Uygulama başarıyla başlatıldı."),
    (r"window\.toggle_editor_camera\(\) is only available in development_mode",
     "Düzenleyici kamerası yalnızca geliştirme modunda kullanılabilir."),
    (r"no audio found with name: (?P<ad>.+?) supported formats: (?P<b>.+)",
     r"Ses dosyası bulunamadı: \g<ad> (desteklenen biçimler: \g<b>)"),
    (r"(?P<v>.+) has no audio clip", r"\g<v> için ses dosyası ayarlanmamış."),
    (r"failed to destroy entity (?P<v>.+)", r"Varlık yok edilemedi: \g<v>"),
    (r"pygame (?P<v>\S+) \(SDL (?P<sdl>\S+), Python (?P<py>\S+)\)",
     r"pygame \g<v> yüklendi (SDL \g<sdl>, Python \g<py>)"),
    (r"Hello from the pygame community\. (?P<u>\S+)",
     r"pygame topluluğundan merhaba! \g<u>"),
]

# Python "warnings" çıktısı:  "dosya.py:12: DeprecationWarning: ileti"
_UYARI_TURLERI = {
    "DeprecationWarning": "Eskimiş Kullanım Uyarısı",
    "PendingDeprecationWarning": "Yakında Eskiyecek Kullanım Uyarısı",
    "FutureWarning": "Gelecek Sürüm Uyarısı",
    "UserWarning": "Uyarı",
    "RuntimeWarning": "Çalışma Zamanı Uyarısı",
    "SyntaxWarning": "Sözdizimi Uyarısı",
    "ResourceWarning": "Kaynak Uyarısı",
    "ImportWarning": "İçe Aktarma Uyarısı",
    "UnicodeWarning": "Karakter Kodlama Uyarısı",
    "BytesWarning": "Bayt Uyarısı",
    "EncodingWarning": "Kodlama Uyarısı",
    "DecompressionBombWarning": "Çok Büyük Resim Uyarısı",
}
_UYARI_SATIRI = re.compile(
    r"^(?P<yer>.+?:\d+): (?P<tur>" + "|".join(_UYARI_TURLERI) + r"): (?P<ileti>.*)$")
_UYARI_ILETILERI = [
    (r"Palette images with Transparency expressed in bytes should be converted to RGBA images",
     "Saydamlık içeren paletli resimler RGBA'ya dönüştürülmeli (resim.dönüştür('RGBA'))."),
    (r"Image size \((?P<n>\d+) pixels\) exceeds limit of (?P<s>\d+) pixels.*",
     r"Resim çok büyük (\g<n> piksel; sınır \g<s>). Bozuk ya da zararlı bir dosya olabilir."),
    (r"invalid escape sequence '(?P<k>.+)'",
     r"metindeki '\g<k>' geçersiz bir kaçış dizisi; dosya yolunu r'...' biçiminde yazın "
     r"ya da \\ yerine \\\\ kullanın."),
]
_UYARI_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _UYARI_ILETILERI]

_URSINA_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _URSINA_ILETILERI]
_DUZ_SATIRLAR = [(re.compile(f"^(?:{d})$"), t) for d, t in _DUZ_SATIRLAR]

# Hızlı ön eleme: bu başlangıçlardan biri yoksa satır hiç incelenmez (uzun
# çıktılarda her satır için onlarca desen denenmesin).
_ADAY = re.compile(
    r"^(?:\x1b\[[0-9;]*m)*(?::|info:|warning:|Known pipe|\s+\w+GraphicsPipe|\(\d+ aux|set |-+set |"
    r"package_folder|asset_folder|os: |python version|ursina version|development mode|"
    r"application successfully|window\.toggle|no audio found|failed to destroy|pygame |Hello from)"
    r"|has no audio clip|Warning: ")


def _uygula(tablo, metin):
    for desen, karsilik in tablo:
        m = desen.match(metin)
        if m:
            return karsilik(m) if callable(karsilik) else m.expand(karsilik)
    return None


def satiri_cevir(satir):
    """Tek satırı (satır sonu karakteri olmadan) çevirir; tanınmazsa aynen döner."""
    if not _ADAY.search(satir):
        return satir
    sade = _ANSI.sub("", satir).rstrip()

    m = _PANDA_SATIR.match(sade)
    if m and m.group("sev") in _PANDA_SEVIYE:
        kategoriler = [k for k in m.group("kat").split(":") if k]
        kat = next((_PANDA_KATEGORI[k] for k in reversed(kategoriler) if k in _PANDA_KATEGORI),
                   ":".join(kategoriler))
        ileti = m.group("ileti")
        cevrilen = _uygula(_PANDA_ILETILERI, ileti)
        return f"{_PANDA_SEVIYE[m.group('sev')]} ({kat}): {cevrilen or ileti}"

    m = _URSINA_ONEK.match(sade)
    if m:
        ileti = m.group("ileti")
        cevrilen = _uygula(_URSINA_ILETILERI, ileti)
        return f"{_URSINA_ONEK_TR[m.group('onek')]}: {cevrilen or ileti}"

    cevrilen = _uygula(_DUZ_SATIRLAR, sade)
    if cevrilen is not None:
        return cevrilen

    m = _UYARI_SATIRI.match(sade)
    if m:
        ileti = m.group("ileti")
        tur = _UYARI_TURLERI[m.group("tur")]
        if re.search(r"[\\/](?:site-packages|pip_packages)[\\/]", m.group("yer")):
            # Kütüphanenin kendi dosyası: "kodunuzu düzeltin" tavsiyesi yanıltıcı olur.
            return (f"{m.group('yer')}: {tur}: {ileti} "
                    f"(kütüphanenin kendi kodunda; sizin kodunuzla ilgisi yok, önemsiz)")
        cevrilen = _uygula(_UYARI_ILETILERI, ileti)
        return f"{m.group('yer')}: {tur}: {cevrilen or ileti}"
    return satir


def metni_cevir(metin):
    """Tam satırlardan oluşan metni çevirir (satır sonları korunur)."""
    parcalar = metin.split("\n")
    for i, p in enumerate(parcalar):
        if not p:
            continue
        cr = p.endswith("\r")
        govde = p[:-1] if cr else p
        yeni = satiri_cevir(govde)
        if yeni is not govde:
            parcalar[i] = yeni + ("\r" if cr else "")
    return "\n".join(parcalar)


class SatirCevirici:
    """Parça parça gelen süreç çıktısını satır satır çevirip iletir.

    os.read() satırları ortadan bölebilir (print metni ve "\n" ayrı yazılır).
    Tamamlanmış satırlar toplanır ve en fazla ARALIK saniyede bir tek parça
    olarak iletilir: eskiden her okuma ayrı gönderiliyordu; döngüde yazdıran
    bir program arayüze saniyede binlerce mesaj yolluyor, IDE donuyordu.
    Satır sonu gelmemiş kuyruk kısa bir süre bekletilir; o sürede devamı
    gelmezse olduğu gibi gönderilir. Böylece input("Adın: ") gibi satır sonu
    olmayan istemler de görünür.
    """

    BEKLEME = 0.12
    ARALIK = 0.05
    AZAMI_KUYRUK = 8192
    AZAMI_PAKET = 256 * 1024

    def __init__(self, gonder, bekleme=None, aralik=None):
        self._gonder = gonder
        self._bekleme = self.BEKLEME if bekleme is None else bekleme
        self._aralik = self.ARALIK if aralik is None else aralik
        self._kuyruk = ""
        self._kuyruk_zamani = 0.0
        self._hazir = []
        self._hazir_boy = 0
        self._son_gonderim = 0.0
        self._kilit = threading.Lock()
        self._zamanlayici = None

    def _zamanlayiciyi_durdur(self):
        if self._zamanlayici is not None:
            self._zamanlayici.cancel()
            self._zamanlayici = None

    def _zamanla(self, sure):
        self._zamanlayici = threading.Timer(max(sure, 0.005), self._zaman_doldu)
        self._zamanlayici.daemon = True
        self._zamanlayici.start()

    def _haziri_gonder(self):
        if self._hazir:
            metin = "".join(self._hazir)
            self._hazir, self._hazir_boy = [], 0
            self._son_gonderim = time.monotonic()
            self._gonder(metin)

    def _planla(self):
        """Kilit altında: bekleyen işe göre zamanlayıcıyı kurar."""
        simdi = time.monotonic()
        if self._hazir:
            self._zamanla(self._aralik - (simdi - self._son_gonderim))
        elif self._kuyruk:
            self._zamanla(self._bekleme - (simdi - self._kuyruk_zamani))

    def besle(self, metin):
        if not metin:
            return
        with self._kilit:
            self._zamanlayiciyi_durdur()
            veri = self._kuyruk + metin
            son = veri.rfind("\n")
            if son != -1:
                tam, self._kuyruk = veri[:son + 1], veri[son + 1:]
                tam = metni_cevir(tam)
                self._hazir.append(tam)
                self._hazir_boy += len(tam)
            else:
                self._kuyruk = veri
            self._kuyruk_zamani = time.monotonic()
            if len(self._kuyruk) > self.AZAMI_KUYRUK:
                self._hazir.append(self._kuyruk)
                self._hazir_boy += len(self._kuyruk)
                self._kuyruk = ""
            if self._hazir and (
                    time.monotonic() - self._son_gonderim >= self._aralik
                    or self._hazir_boy >= self.AZAMI_PAKET):
                self._haziri_gonder()
            self._planla()

    def _zaman_doldu(self):
        with self._kilit:
            self._zamanlayici = None
            self._haziri_gonder()
            if self._kuyruk and                     time.monotonic() - self._kuyruk_zamani >= self._bekleme - 0.001:
                kuyruk, self._kuyruk = self._kuyruk, ""
                self._son_gonderim = time.monotonic()
                self._gonder(metni_cevir(kuyruk))
            self._planla()

    def bitir(self):
        """Kalan her şeyi gönderir (süreç bitince çağrılır)."""
        with self._kilit:
            self._zamanlayiciyi_durdur()
            self._haziri_gonder()
            if self._kuyruk:
                kuyruk, self._kuyruk = self._kuyruk, ""
                self._gonder(metni_cevir(kuyruk))
