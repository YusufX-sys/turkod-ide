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
     "Resmin içindeki renk profili (sKYM) hatalı; resim yine de yüklenir (önemsiz)."),
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
     r"\g<y> bir TAG (PNG) dosyası değil."),
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
     "Dikey eşitleme izlence çalışırken kapatılamaz."),
    (r"error in obj file line: (?P<n>\S+) : (?P<s>.*)",
     r"OBJ biçim dosyasında hatalı satır \g<n>: \g<s>"),
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
# Kütüphanelerin kendi uyarı sınıfları (MatplotlibDeprecationWarning ...) da
# yakalanır; adı bilinmeyenler olduğu gibi kalır.
_UYARI_SATIRI = re.compile(r"^(?P<yer>.+?:\d+): (?P<tur>\w*Warning): (?P<ileti>.*)$")
# Çalıştırıcının geçici dosyası: "C:\...\turkce_kod_calisma.py:12" -> "Satır 12".
_KULLANICI_DOSYASI = re.compile(r"^.*[\\/]turkce_kod_calisma\.py:(?P<n>\d+)$")
_UYARI_ILETILERI = [
    (r"Palette images with Transparency expressed in bytes should be converted to RGBA images",
     "Saydamlık içeren paletli resimler KYMA'ya dönüştürülmeli (resim.dönüştür('RGBA'))."),
    (r"Image size \((?P<n>\d+) pixels\) exceeds limit of (?P<s>\d+) pixels.*",
     r"Resim çok büyük (\g<n> piksel; sınır \g<s>). Bozuk ya da zararlı bir dosya olabilir."),
    (r"divide by zero encountered in (?P<f>.+)",
     r"sıfıra bölme oldu (\g<f>); sonuç sonsuz olarak hesaplandı (ekranda inf görünür)."),
    (r"invalid value encountered in (?P<f>.+)",
     r"geçersiz bir değer oluştu (\g<f>); sonuç sayı değil olarak hesaplandı (ekranda nan görünür)."),
    (r"overflow encountered in (?P<f>.+)",
     r"sayı taşması oldu (\g<f>); sonuç bu veri tipine sığmıyor."),
    (r"Mean of empty slice\.?", "boş bir dilimin ortalaması alındı; sonuç sayı değil (nan)."),
    (r"invalid escape sequence '(?P<k>.+)'",
     r"metindeki '\g<k>' geçersiz bir kaçış dizisi; dosya yolunu r'...' biçiminde yazın "
     r"ya da \\ yerine \\\\ kullanın."),
]
_UYARI_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _UYARI_ILETILERI]

_URSINA_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _URSINA_ILETILERI]
_DUZ_SATIRLAR = [(re.compile(f"^(?:{d})$"), t) for d, t in _DUZ_SATIRLAR]

# --------------------------------------------------------------------------
# Kivy:  "[INFO   ] [Window      ] Provider: sdl2"
# --------------------------------------------------------------------------
_KIVY_SATIR = re.compile(r"^\[(?P<sev>[A-Z]+)\s*\] \[(?P<kat>[^\]]*?)\s*\] ?(?P<ileti>.*)$")
_KIVY_SEVIYE = {
    "INFO": "Bilgi", "WARNING": "Uyarı", "ERROR": "Hata", "DEBUG": "Ayıklama",
    "CRITICAL": "Kritik", "TRACE": "İz",
}
_KIVY_KATEGORI = {
    "Logger": "Kayıt", "deps": "Bağımlılık", "Kivy": "Kivy", "Python": "Python",
    "Window": "Pencere", "GL": "OpenGL", "Image": "Resim", "Text": "Metin",
    "Clipboard": "Pano", "Factory": "Fabrika", "Base": "Temel", "Audio": "Ses",
    "Video": "Video", "Camera": "Kamera", "Spelling": "Yazım denetimi",
    "Input": "Girdi", "Multitouch": "Çoklu dokunma", "Config": "Yapılandırma",
    "Modules": "Modüller", "Cutbuffer": "Pano", "Loader": "Yükleyici",
    "Clock": "Saat", "App": "Uygulama", "WindowSDL": "Pencere", "Context": "Bağlam",
    "Shader": "Gölgelendirici", "Atlas": "Doku atlası", "Lang": "Kivy dili",
}
_KIVY_ILETILERI = [
    (r"Record log in (?P<y>.+)", r"Kayıt dosyası: \g<y>"),
    (r'Successfully imported "(?P<ad>.+?)" (?P<s>\S+)', r'"\g<ad>" \g<s> yüklendi.'),
    (r'Installed at "(?P<y>.+)"', r'Kurulum klasörü: "\g<y>"'),
    (r'Interpreter at "(?P<y>.+)"', r'Python yorumlayıcısı: "\g<y>"'),
    (r"Purge log fired\. Processing\.\.\.", "Eski kayıt dosyaları temizleniyor..."),
    (r"Purge finished!?", "Eski kayıtların temizliği bitti."),
    (r"Purge log fired\. Analysing\.\.\.", "Eski kayıt dosyaları inceleniyor..."),
    (r"Providers: (?P<p>.+)", r"Sağlayıcılar: \g<p>"),
    (r"Provider: (?P<p>.+)", r"Sağlayıcı: \g<p>"),
    (r"Using the \"(?P<p>.+?)\" graphics system", r'"\g<p>" grafik sistemi kullanılıyor.'),
    (r"GLEW initialization succeeded", "GLEW başarıyla başlatıldı."),
    (r"Backend used <(?P<b>.+)>", r"Kullanılan arka uç: \g<b>"),
    (r"OpenGL version <(?P<v>.+)>", r"OpenGL sürümü: \g<v>"),
    (r"OpenGL vendor <(?P<v>.+)>", r"OpenGL üreticisi: \g<v>"),
    (r"OpenGL renderer <(?P<v>.+)>", r"OpenGL çizici: \g<v>"),
    (r"OpenGL parsed version: (?P<a>\d+), (?P<b>\d+)", r"OpenGL sürümü: \g<a>.\g<b>"),
    (r"Shading version <(?P<v>.+)>", r"Gölgelendirici sürümü: \g<v>"),
    (r"Texture max size <(?P<v>\d+)>", r"En büyük doku boyutu: \g<v>"),
    (r"Texture max units <(?P<v>\d+)>", r"En fazla doku birimi: \g<v>"),
    (r"auto add sdl2 input provider", "SDL2 girdi sağlayıcısı otomatik eklendi."),
    (r"virtual keyboard not allowed, single mode, not docked",
     "Sanal klavye kapalı (tek kip, sabitlenmemiş)."),
    (r"Start application main loop", "Uygulamanın ana döngüsü başladı."),
    (r"Leaving application in progress\.\.\.", "Uygulamadan çıkılıyor..."),
    (r"v(?P<v>\d[\w.]*)", r"sürüm \g<v>"),
    (r"v(?P<v>\d[\w.]*) (?P<r>\(.*)", r"sürüm \g<v> \g<r>"),
    (r"Unable to find any valuable (?P<n>.+?) provider\..*",
     r"Kullanılabilir bir '\g<n>' sağlayıcısı bulunamadı."),
    (r"(?P<y>.+?) does not exist", r"\g<y> bulunamadı."),
]
_KIVY_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _KIVY_ILETILERI]

# --------------------------------------------------------------------------
# TensorFlow / absl:  "I0000 00:00:1793... 8644 port.cc:153] ileti"
# ve eski biçim "2026-10-28 12:00:00.123: I tensorflow/... ] ileti"
# --------------------------------------------------------------------------
_TF_SATIR = re.compile(
    r"^(?:(?P<sev>[IWEF])\d{4} [\d:.]+\s+\d+ |\d{4}-\d\d-\d\d [\d:.]+: (?P<sev2>[IWEF]) )"
    r"(?P<dosya>\S+?:\d+|\S+)\] (?P<ileti>.*)$")
_TF_SEVIYE = {"I": "Bilgi", "W": "Uyarı", "E": "Hata", "F": "Ölümcül hata"}
_TF_ILETILERI = [
    (r"oneDNN custom operations are on\..*",
     "oneDNN hızlandırmaları açık; kayan nokta yuvarlaması nedeniyle sonuçlar çok az farklı "
     "çıkabilir. Kapatmak için TF_ENABLE_ONEDNN_OPTS=0 ortam değişkenini ayarlayın (önemsiz)."),
    (r"This TensorFlow binary is optimized to use available CPU instructions.*",
     "TensorFlow, işlemcinin hızlı komutlarını kullanacak şekilde derlenmiş (önemsiz)."),
    (r"To enable the following instructions: (?P<k>.+?), in other operations, rebuild TensorFlow.*",
     r"\g<k> komutları başka işlemlerde de kullanılabilir; bunun için TensorFlow yeniden "
     r"derlenmeli (önemsiz)."),
    (r"Could not find cuda drivers on your machine, GPU will not be used\.?",
     "Bilgisayarda CUDA sürücüsü yok; GİB kullanılmayacak, işlemler işlemcide yapılır."),
    (r"Cannot dlopen some GPU libraries\..*",
     "Bazı GİB kütüphaneleri yüklenemedi; GİB kullanılmayacak (önemsiz)."),
    (r"Created device (?P<d>\S+) with (?P<m>\d+) MB memory.*",
     r"\g<d> aygıtı \g<m> MB bellekle oluşturuldu."),
    (r"Your CPU supports instructions that this TensorFlow binary was not compiled to use: (?P<k>.+)",
     r"İşlemciniz, bu TensorFlow sürümünün kullanmadığı komutları destekliyor: \g<k> (önemsiz)."),
]
_TF_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _TF_ILETILERI]

# --------------------------------------------------------------------------
# OpenCV:  "[ WARN:0@0.128] global loadsave.cpp:278 cv::findDecoder imread_(...): ..."
# --------------------------------------------------------------------------
_CV_SATIR = re.compile(
    # Kaynak dosya (loadsave.cpp:278) şartı: kullanıcının yazdırdığı
    # "[INFO] Sunucu başladı" gibi satırlar OpenCV iletisi sanılmasın.
    r"^\[ ?(?P<sev>WARN|ERROR|INFO|DEBUG|FATAL)[:\d@.]*\] (?:global )?"
    r"(?P<dosya>\S+\.(?:cpp|hpp|cc|c|h|mm)(?::\d+)?) "
    r"(?P<fn>\S+) (?P<ileti>.*)$")
_CV_SEVIYE = {"WARN": "Uyarı", "ERROR": "Hata", "INFO": "Bilgi", "DEBUG": "Ayıklama",
              "FATAL": "Ölümcül hata"}
_CV_ILETILERI = [
    (r"imread_\('(?P<y>.*)'\): can't open/read file: check file path/integrity",
     r"Resim okunamadı: '\g<y>'. Dosya adını, klasörünü ve dosyanın bozuk olmadığını "
     r"kontrol edin (resim_oku Hiçlik döndürür)."),
    (r"imwrite_\('(?P<y>.*)'\): can't (?:open|write) file.*",
     r"Resim kaydedilemedi: '\g<y>' (klasör yok ya da yazma izni yok)."),
    (r"VIDEOIO\((?P<a>\w+)\): can't (?:open|be opened) camera by index (?P<n>\d+)",
     r"\g<n> numaralı kamera açılamadı (\g<a>)."),
    (r"VIDEOIO\((?P<a>\w+)\): backend is generally available but can't be used to capture by index",
     r"Video altyapısı (\g<a>) bu kamerayla çalışamıyor."),
    (r"(?P<fn>\S+) Camera index out of range",
     "Kamera numarası geçersiz; bilgisayarda bu numarada bir kamera yok."),
    (r"anonymous-namespace'::SourceReaderCB::~SourceReaderCB terminating async callback",
     "Kamera okuyucusu kapatılıyor (önemsiz)."),
    (r"(?P<m>.+)", r"\g<m>"),
]
_CV_ILETILERI = [(re.compile(f"^(?:{d})$"), t) for d, t in _CV_ILETILERI]

# --------------------------------------------------------------------------
# Kütüphanelerin (iş parçacıkları, geri çağırmalar) doğrudan yazdığı Python
# hata izleri. Kullanıcı programının kendi hataları zaten çalıştırıcıda
# Türkçe yazılır; bunlar çalıştırıcının yakalayamadığı izlerdir.
# --------------------------------------------------------------------------
_IZ_SATIRLARI = [
    (r"Traceback \(most recent call last\):", "Hata izi (en son çağrı en altta):"),
    (r'(?P<b>\s+)File "(?P<d>.+?)", line (?P<n>\d+), in (?P<f>.+)',
     r'\g<b>Dosya "\g<d>", satır \g<n>, \g<f> içinde'),
    (r'(?P<b>\s+)File "(?P<d>.+?)", line (?P<n>\d+)', r'\g<b>Dosya "\g<d>", satır \g<n>'),
    (r"During handling of the above exception, another exception occurred:",
     "Yukarıdaki hata işlenirken başka bir hata oluştu:"),
    (r"The above exception was the direct cause of the following exception:",
     "Yukarıdaki hata, aşağıdaki hatanın doğrudan sebebidir:"),
    (r"Exception ignored in: (?P<y>.+)", r"Şuradaki bir hata yok sayıldı: \g<y>"),
    (r"Exception in thread (?P<t>.+?):", r"'\g<t>' iş parçacığında hata:"),
    (r"Exception in Tkinter callback", "Tkinter geri çağırmasında hata:"),
]
_IZ_SATIRLARI = [(re.compile(f"^(?:{d})$"), t) for d, t in _IZ_SATIRLARI]
_HATA_SON_SATIRI = re.compile(
    r"^(?P<tur>(?:[A-Za-z_]\w*\.)*(?:[A-Za-z_]\w*(?:Error|Exception|Interrupt|Exit|Iteration|Terminator|error)|Exception))"
    r"(?:: (?P<ileti>.*))?$")

# Hızlı ön eleme: bu başlangıçlardan biri yoksa satır hiç incelenmez (uzun
# çıktılarda her satır için onlarca desen denenmesin).
_ADAY = re.compile(
    r"^(?:\x1b\[[0-9;]*m)*(?::|info:|warning:|Known pipe|\s+\w+GraphicsPipe|\(\d+ aux|set |-+set |"
    r"package_folder|asset_folder|os: |python version|ursina version|development mode|"
    r"application successfully|window\.toggle|no audio found|failed to destroy|pygame |Hello from)"
    r"|has no audio clip|Warning: "
    r"|^\[(?:\x1b\[[0-9;]*m)*[A-Z]+(?:\x1b\[[0-9;]*m)*\s*\] \["
    r"|^[IWEF]\d{4} |^\d{4}-\d\d-\d\d [\d:.]+: [IWEF] |^WARNING: All log messages"
    r"|^\[ ?(?:WARN|ERROR|INFO|DEBUG|FATAL)[:\d@.]*\] "
    r"|^Traceback \(|^\s+File \"|^During handling|^The above exception|^Exception (?:ignored|in )"
    r"|^(?:[A-Za-z_]\w*\.)*(?:[A-Za-z_]\w*(?:Error|Exception|Interrupt|Exit|Iteration|Terminator|error)|Exception)(?::|$)")


def _hata_cevirileri():
    """Çalıştırıcının hata adı/açıklama çevirileri (yoksa None)."""
    try:
        try:
            from .runner import hata_aciklamasi, hata_turu_adi
        except ImportError:
            from runner import hata_aciklamasi, hata_turu_adi
        return hata_turu_adi, hata_aciklamasi
    except Exception:
        return None


def _uygula(tablo, metin):
    for desen, karsilik in tablo:
        m = desen.match(metin)
        if m:
            return karsilik(m) if callable(karsilik) else m.expand(karsilik)
    return None


# Kullanıcı kodundaki bir uyarının ardından Python, uyarıya yol açan satırı
# (çevrilmiş Python koduyla) yazar; o satır TürKod'a geri çevrilir.
_onceki_kullanici_uyarisi = False


def _python_satirini_turkcele(satir):
    try:
        try:
            from .converter import python_kodu_turkceye_cevir
        except ImportError:
            from converter import python_kodu_turkceye_cevir
        govde = satir.lstrip()
        return satir[:len(satir) - len(govde)] + python_kodu_turkceye_cevir(govde)
    except Exception:
        return satir


_IZ_BASLIGI = re.compile(
    r"^(?:Traceback \(|During handling of the above|The above exception was|"
    r"Exception (?:ignored|in thread|in Tkinter))")


def _iz_durumunu_guncelle(satir, durum):
    """durum["iz"]: bir hata izi (Traceback) bloğunun içinde miyiz? Döndürür:
    bu satır hata izinin parçası (ya da onu bitiren hata satırı) mı?
    Program çıktısı (stdout) ile hata çıktısı (stderr) aynı borudan geldiğinden
    "ValueError: ..." gibi bir satırın kullanıcının kendi yazdırdığı metin mi
    yoksa gerçek bir hata mı olduğu ancak öncesindeki iz bloğundan anlaşılır."""
    sade = _ANSI.sub("", satir)
    iz_icinde = bool(durum.get("iz"))
    if _IZ_BASLIGI.match(sade):
        durum["iz"] = True
        return True
    if sade.strip() and not sade[:1].isspace():
        # İzin ilk girintisiz satırı hatanın kendisidir; blok burada biter.
        durum["iz"] = False
    return iz_icinde


def satiri_cevir(satir, durum=None):
    """Tek satırı (satır sonu karakteri olmadan) çevirir; tanınmazsa aynen döner.

    durum: akışın iz durumu (SatirCevirici verir). Verilirse "Hata: ileti"
    biçimli satırlar yalnızca bir hata izinin içindeyse çevrilir; kullanıcının
    yazdır("ValueError: sayı negatif olamaz") ya da yazdır("KeyError")
    çıktısı olduğu gibi kalır. Verilmezse (tek satır çevirisi) her zaman çevrilir."""
    global _onceki_kullanici_uyarisi
    iz_icinde = True if durum is None else _iz_durumunu_guncelle(satir, durum)
    if _onceki_kullanici_uyarisi:
        _onceki_kullanici_uyarisi = False
        if satir.startswith("  ") and satir.strip():
            return _python_satirini_turkcele(satir)
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

    m = _KIVY_SATIR.match(sade)
    if m and m.group("sev") in _KIVY_SEVIYE:
        kat = m.group("kat").strip()
        ileti = m.group("ileti")
        cevrilen = _uygula(_KIVY_ILETILERI, ileti)
        return f"[{_KIVY_SEVIYE[m.group('sev')]}] [{_KIVY_KATEGORI.get(kat, kat)}] {cevrilen or ileti}"

    if sade.startswith("WARNING: All log messages before absl::InitializeLog()"):
        return "Uyarı: kayıt sistemi başlamadan önceki iletiler doğrudan hata akışına yazılıyor (önemsiz)."
    m = _TF_SATIR.match(sade)
    if m:
        sev = _TF_SEVIYE[m.group("sev") or m.group("sev2")]
        ileti = m.group("ileti")
        cevrilen = _uygula(_TF_ILETILERI, ileti)
        return f"{sev} (TensorFlow): {cevrilen or ileti}"

    m = _CV_SATIR.match(sade)
    if m:
        cevrilen = _uygula(_CV_ILETILERI, m.group("ileti"))
        return f"{_CV_SEVIYE[m.group('sev')]} (OpenCV): {cevrilen}"

    cevrilen = _uygula(_IZ_SATIRLARI, sade)
    if cevrilen is not None:
        return cevrilen

    m = _UYARI_SATIRI.match(sade)
    if m:
        ileti = m.group("ileti")
        tur = _UYARI_TURLERI.get(m.group("tur"))
        if tur is None:
            ceviri = _hata_cevirileri()
            tur = ceviri[0](m.group("tur")) if ceviri else m.group("tur")
        yer = m.group("yer")
        if re.search(r"[\\/](?:site-packages|pip_packages)[\\/]", yer):
            # Kütüphanenin kendi dosyası: "kodunuzu düzeltin" tavsiyesi yanıltıcı olur.
            return (f"{yer}: {tur}: {ileti} "
                    f"(kütüphanenin kendi kodunda; sizin kodunuzla ilgisi yok, önemsiz)")
        k = _KULLANICI_DOSYASI.match(yer)
        if k:
            yer = f"Satır {k.group('n')}"
            _onceki_kullanici_uyarisi = True
        cevrilen = _uygula(_UYARI_ILETILERI, ileti)
        return f"{yer}: {tur}: {cevrilen or ileti}"

    m = _HATA_SON_SATIRI.match(sade) if iz_icinde else None
    if m:
        ceviri = _hata_cevirileri()
        if ceviri:
            tur_adi = m.group("tur")
            tur = ceviri[0](tur_adi)
            ileti = m.group("ileti")
            if tur == tur_adi and ileti is None:
                return satir  # tanınmayan tek kelime (ör. kullanıcının yazdığı "MyError")
            if ileti is None:
                return tur
            return f"{tur}: {ceviri[1](tur_adi.rpartition('.')[2], ileti)}"
    return satir


def metni_cevir(metin, durum=None):
    """Tam satırlardan oluşan metni çevirir (satır sonları korunur).
    durum: bkz. satiri_cevir."""
    parcalar = metin.split("\n")
    for i, p in enumerate(parcalar):
        if not p:
            continue
        cr = p.endswith("\r")
        govde = p[:-1] if cr else p
        yeni = satiri_cevir(govde, durum)
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
        # Hata izi (Traceback) bloğu durumu: yalnızca gerçek hata çıktısı
        # çevrilir, kullanıcının yazdırdığı "ValueError: ..." metni değil.
        self._durum = {"iz": False}

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
                tam = metni_cevir(tam, self._durum)
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
                self._gonder(metni_cevir(kuyruk, self._durum))
            self._planla()

    def bitir(self):
        """Kalan her şeyi gönderir (süreç bitince çağrılır)."""
        with self._kilit:
            self._zamanlayiciyi_durdur()
            self._haziri_gonder()
            if self._kuyruk:
                kuyruk, self._kuyruk = self._kuyruk, ""
                self._gonder(metni_cevir(kuyruk, self._durum))
