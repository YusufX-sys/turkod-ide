"""TürKod yama uygulayıcı (idempotent; her dosya için yedek alır).

Proje kökünden çalıştır:   python yama_uygula.py

Yaptıkları
  turkod_flutter/lib/main.dart
    * EditorProvider.saveAllForExit(): güncellemeden önce tüm sekmeleri/kodları kaydeder
    * Açılış denetimine kaydet geri çağrısını bağlar
    * Menüye "Güncelleştirmeler > Güncelleştirmeleri Denetle" ekler (Yardım'ın sağı)
    * Backend'i paketlenmiş exe olarak başlatır (backend\\turkod_backend.exe), --parent-pid
      verir (arayüz kapanınca backend de kapanır) ve her arayüze ayrı boş bir port atar
    * Önceki bir yama çakışan 'backendWorkingDir' eklediyse onu onarır
    * DONMA/GECİKME KÖK NEDENİ: satır göstergesi (kırılma noktası/katlama), re_editor'ün
      yerleşim (layout) sırasında güncellediği bir ValueNotifier'ı ValueListenableBuilder ile
      dinliyordu -> yerleşim sırasında setState = "Build scheduled during frame". Release'te
      sonraki setState'ler kare planlamıyor (arayüz pencere boyutu değişene kadar güncellenmiyor),
      debug'da her tuşta dev bir hata kaydı yazılıyor (gecikme). Çözüm: CustomPainter(repaint:)
    * Açılış ekranı: backend hazır olana kadar "Backend başlatılıyor..." gösterilir
      (önce backend, sonra arayüz); açılamazsa hata + "Yeniden dene / Yine de aç"
  turkod_ide/ide_core.py
    * IDE terminalinde `pip yükle X` (Türkçe pip komutları) desteği
    * Hata mesajlarındaki "pip install X" -> "pip yükle X"
  turkod_ide/server.py
    * güncelleme indirme ilerlemesi komutları

Bir dosyada beklenen kod bulunamazsa o dosyaya DOKUNMAZ, ne yapılacağını yazar.
Çıkış kodu 0: hepsi tamam; 1: en az bir dosya yamalanamadı.
"""
import re
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
ZAMAN = time.strftime("%Y%m%d-%H%M%S")
MAIN = KOK / "turkod_flutter" / "lib" / "main.dart"
CORE = KOK / "turkod_ide" / "ide_core.py"
SERVER = KOK / "turkod_ide" / "server.py"

OK, VAR, YOK, ATLA = "eklendi", "zaten var", "BULUNAMADI", "atlandı (isteğe bağlı)"


def oku(yol):
    with open(yol, "r", encoding="utf-8", newline="") as f:
        return f.read()


def yaz(yol, metin):
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write(metin)


def nl_uygula(metin, nl):
    return metin.replace("\r\n", "\n").replace("\n", nl)


# ----------------------------------------------------------------------------
# main.dart
# ----------------------------------------------------------------------------
KAYDET_YONTEMI = """
  /// Güncelleme (ve benzeri çıkışlar) öncesi çağrılır: kaydedilmemiş dosya
  /// sekmelerini diske yazar; adsız sekmeler ve sekme listesi oturuma kaydedilir
  /// (yeniden açılışta geri gelir). Bir şey yazılamazsa false döner.
  Future<bool> saveAllForExit() async {
    try {
      for (final t in List<EditorTab>.from(_tabs)) {
        if (t.path == kSettingsPath ||
            t.path.startsWith('untitled:') ||
            !t.dirty) {
          continue;
        }
        await _backend
            .call('dosya_kaydet', {'yol': t.path, 'icerik': t.content});
        t.dirty = false;
      }
      await _backend.call('oturum_kaydet', {
        'sekmeler': _tabs
            .where((t) => t.path != kSettingsPath)
            .map((t) => t.path.startsWith('untitled:')
                ? {'yol': null, 'isim': t.name, 'icerik': t.content}
                : {'yol': t.path, 'isim': t.name, 'icerik': null})
            .toList(),
        'aktif_sira': _active < 0 ? 0 : _active,
      });
      notifyListeners();
      return true;
    } catch (_) {
      return false;
    }
  }

"""

MENU_AKSIYONU = """    AppAction(
      id: 'update.check',
      label: 'Güncelleştirmeleri Denetle',
      menu: 'Güncelleştirmeler',
      icon: Icons.system_update_alt,
      run: (c) => guncellemeKontrolEt(
        c,
        c.read<BackendService>().call,
        kaydet: c.read<EditorProvider>().saveAllForExit,
        sessiz: false,
      ),
    ),
"""


GETTER_METNI = """/// Paketlenmiş backend: <uygulama klasörü>\\backend\\turkod_backend.exe
  static String get packagedBackendExe => p.join(
      p.dirname(Platform.resolvedExecutable), 'backend', 'turkod_backend.exe');

  /// EXE modunda mı çalışıyoruz? backend\\turkod_backend.exe yanımızdaysa evet.
  /// (`flutter run` sırasında bu dosya olmadığından geliştirme moduna düşer.)
  static bool get isExeMode =>
      Platform.isWindows && File(packagedBackendExe).existsSync();"""

KOMUT_METNI = """static List<String> backendCommand() {
    if (isExeMode) {
      // --parent-pid: arayüz (bu süreç) hangi yolla kapanırsa kapansın backend
      // kendini ve çalıştırdığı programları kapatır.
      return [@AD@, '--backend', '--parent-pid', '$pid'];
    }
    if (Platform.isWindows) return ['python', '-u', '-m', 'turkod_ide.server'];
    return ['python3', '-u', '-m', 'turkod_ide.server'];
  }"""

BAYAT_PORT_METNI = """
    try {
      // Önceki oturumdan kalan (ölü) port dosyası yeni backend'in portuyla karışmasın.
      final eski = File(AppConfig._portFile);
      if (eski.existsSync()) eski.deleteSync();
    } catch (_) {}
"""

PORT_SECIMI_METNI = """if (AppConfig.isExeMode) {
        // Her arayüz kendi backend'ini BOŞ bir porta açar: önceki oturumlardan kalan
        // backend'lere ya da bayat port dosyasına takılmaz.
        final s = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
        AppConfig._portOverride = s.port;
        await s.close();
      }
      final cmd = AppConfig.backendCommand();
      if (AppConfig._portOverride != null) {
        cmd.addAll(['--port', '${AppConfig._portOverride}']);
      }"""

ARDISIK_BASLATMA_METNI = """unawaited(() async {
      // Önce backend açılsın (port hazır olsun), sonra bağlan.
      try {
        await _launcher.launch();
      } catch (_) {}
      await _backend.connect();
    }());"""


ACILIS_ALANLARI = """// Backend hazır olana kadar açılış ekranı gösterilir (önce backend, sonra arayüz).
  bool _hazir = false;
  String? _acilisHatasi;
  StreamSubscription<String>? _acilisHataAbone;

  Future<void> _baslat() async {
    _acilisHataAbone?.cancel();
    _acilisHatasi = null;
    _acilisHataAbone = _launcher.errors.stream.listen((m) {
      _acilisHatasi ??= m;
    });
    try {
      await _launcher.launch();
    } catch (e) {
      _acilisHatasi ??= '$e';
    }
    if (!mounted) return;
    if (_acilisHatasi == null) {
      unawaited(_backend.connect());
      setState(() => _hazir = true);
    } else {
      setState(() {});
    }
  }

  void _yineDeAc() {
    unawaited(_backend.connect());
    setState(() => _hazir = true);
  }

"""

ACILIS_KAPISI = """if (!_hazir) {
      return AcilisEkrani(
        hata: _acilisHatasi,
        onYenidenDene: () {
          setState(() => _acilisHatasi = null);
          unawaited(_baslat());
        },
        onYineDeAc: _yineDeAc,
      );
    }
    """


def import_ekle(t, nl, dosya):
    satir = "import '" + dosya + "';"
    if satir in t:
        return t, VAR
    imports = list(re.finditer(r"^import [^\n]*;[^\n]*\n", t, flags=re.M))
    if not imports:
        return t, YOK
    son = imports[-1]
    return t[: son.end()] + satir + nl + t[son.end():], OK


def acilis_adimlari(t, nl, d):
    """Önce backend, sonra arayüz: açılış ekranı."""
    if "_baslat()" in t and "AcilisEkrani(" in t:
        d["açılış ekranı (önce backend)"] = VAR
        return t

    sinif = re.search(r"class _TurkodAppState extends State<TurkodApp> \{\r?\n", t)
    if not sinif:
        d["açılış ekranı (önce backend)"] = YOK
        return t
    bas = sinif.end()

    yeni = t
    # a) alanlar + yöntemler
    yeni = yeni[:bas] + "  " + nl_uygula(ACILIS_ALANLARI, nl) + yeni[bas:]

    # b) initState: (eski iki satır ya da önceki yamanın ardışık hâli) -> unawaited(_baslat());
    desenler = [
        r"unawaited\(\(\) async \{[^}]*?await _launcher\.launch\(\);.*?await _backend\.connect\(\);\s*\}\(\)\);",
        r"unawaited\(_launcher\.launch\(\)\);\s*\r?\n\s*unawaited\(_backend\.connect\(\)\);",
    ]
    degisti = False
    for desen in desenler:
        m = re.search(desen, yeni[bas:], flags=re.S)
        if m:
            a0, a1 = bas + m.start(), bas + m.end()
            yeni = yeni[:a0] + "unawaited(_baslat());" + yeni[a1:]
            degisti = True
            break
    if not degisti:
        d["açılış ekranı (önce backend)"] = ATLA
        return t

    # c) build: kapı
    m = re.search(r"Widget build\(BuildContext context\) \{\s*\r?\n(\s*)return MultiProvider\(", yeni[bas:])
    if not m:
        d["açılış ekranı (önce backend)"] = ATLA
        return t
    # 'return MultiProvider(' başlangıcını bul
    ic = yeni.index("return MultiProvider(", bas + m.start())
    yeni = yeni[:ic] + nl_uygula(ACILIS_KAPISI, nl) + yeni[ic:]

    # d) dispose: aboneliği kapat
    m = re.search(r"void dispose\(\) \{\s*\r?\n(\s*)_launcher\.dispose\(\);", yeni[bas:])
    if m:
        ic = bas + m.start(0) + m.group(0).index("_launcher.dispose();")
        yeni = yeni[:ic] + "_acilisHataAbone?.cancel();" + nl + m.group(1) + yeni[ic:]

    # e) import
    yeni, durum = import_ekle(yeni, nl, "acilis_ekrani.dart")
    if durum == YOK:
        d["açılış ekranı (önce backend)"] = ATLA
        return t
    d["açılış ekranı (önce backend)"] = OK
    return yeni


def backend_adimlari(t, nl, d):
    """Backend'in paketlenmiş exe olarak başlatılması. Hem eski hem de daha önce
    elle/yamayla değiştirilmiş (backendExe, backendWorkingDir()) kodlarla çalışır."""

    # --- onarım: önceki yamanın eklediği, çakışan 'backendWorkingDir' getter'ı ---
    if re.search(r"static String backendWorkingDir\(\)", t):
        g = re.search(
            r"[ \t]*/// Backend'in çalışma klasörü\.\r?\n[ \t]*static String get backendWorkingDir\s*=>[^;]*;\r?\n", t)
        if g:
            t = t[: g.start()] + t[g.end():]
            d["onarım: yinelenen backendWorkingDir"] = OK

    # --- exe yolu getter'ı: mevcut olanı kullan, yoksa ekle ---
    ad = None
    for aday in ("backendExe", "packagedBackendExe"):
        if re.search(r"static String get " + aday + r"\b", t):
            ad = aday
            break
    if ad is None:
        m1 = re.search(r"static bool get isExeMode\s*=>[^;]*;", t)
        if not m1:
            m1 = re.search(r"static bool get isExeMode\s*\{.*?\r?\n  \}", t, flags=re.S)
        if not m1:
            d["backend exe modu ve komutu"] = YOK
            return t
        t = t[: m1.start()] + nl_uygula(GETTER_METNI, nl) + t[m1.end():]
        ad = "packagedBackendExe"

    # --- başlatma komutu: --parent-pid ---
    if "'--parent-pid'" in t:
        d["backend exe modu ve komutu"] = VAR
    else:
        m = re.search(r"return\s*\[\s*" + ad + r"\s*,\s*'--backend'\s*\]\s*;", t)
        if m:
            t = t[: m.start()] + "return [" + ad + ", '--backend', '--parent-pid', '$pid'];" + t[m.end():]
            d["backend exe modu ve komutu"] = OK
        else:
            m2 = re.search(r"static List<String> backendCommand\(\)\s*\{.*?\r?\n  \}", t, flags=re.S)
            if m2:
                t = t[: m2.start()] + nl_uygula(KOMUT_METNI.replace("@AD@", ad), nl) + t[m2.end():]
                d["backend exe modu ve komutu"] = OK
            else:
                d["backend exe modu ve komutu"] = YOK
                return t

    # eski, artık yanıltıcı olan yorumları düzelt (kozmetik)
    t = re.sub(r"  /// EXE modunda mı çalışıyoruz\?\r?\n(  /// Paketlenmiş backend)", r"\1", t)
    t = t.replace("/// EXE modunda: kendi executable'ımızı --backend ile başlatırız.",
                  "/// EXE modunda: <uygulama klasörü>\\backend\\turkod_backend.exe başlatılır.")

    # --- çalışma klasörü ---
    if re.search(r"static String backendWorkingDir\(\)\s*=>\s*isExeMode\s*\?\s*Directory\.current\.path", t):
        t = re.sub(r"(static String backendWorkingDir\(\)\s*=>\s*isExeMode\s*\?\s*)Directory\.current\.path",
                   lambda m: m.group(1) + "p.dirname(" + ad + ")", t, count=1)
        d["backend çalışma klasörü"] = OK
    elif "workingDirectory: Directory.current.path," in t:
        t = t.replace("workingDirectory: Directory.current.path,",
                      "workingDirectory: AppConfig.isExeMode ? p.dirname(AppConfig." + ad + ") : Directory.current.path,", 1)
        d["backend çalışma klasörü"] = OK
    elif "backendWorkingDir" in t:
        d["backend çalışma klasörü"] = VAR
    else:
        d["backend çalışma klasörü"] = ATLA

    # --- bayat port dosyası temizliği (geliştirme modu için) ---
    if "eski.deleteSync()" in t:
        d["bayat port dosyası temizliği"] = VAR
    else:
        m3 = re.search(r"(Future<void> launch\(\) async \{\s*\r?\n\s*if \((?:!AppConfig\.isExeMode && )?await _isServerRunning\(\)\) return;\r?\n)", t)
        if m3:
            t = t[: m3.end()] + nl_uygula(BAYAT_PORT_METNI.lstrip("\n"), nl) + t[m3.end():]
            d["bayat port dosyası temizliği"] = OK
        else:
            d["bayat port dosyası temizliği"] = ATLA

    # --- ilk açılışta antivirüs taraması yavaş olabilir: port bekleme süresini 15 sn'den 45 sn'ye çıkar ---
    m5 = re.search(r"(_waitForPort\(\) async \{\s*\r?\n\s*for \(var i = 0; i < )30(; i\+\+\))", t)
    if m5:
        t = t[: m5.start()] + m5.group(1) + "90" + m5.group(2) + t[m5.end():]
        d["backend bekleme süresi (45 sn)"] = OK
    elif re.search(r"_waitForPort\(\) async \{\s*\r?\n\s*for \(var i = 0; i < 90;", t):
        d["backend bekleme süresi (45 sn)"] = VAR
    else:
        d["backend bekleme süresi (45 sn)"] = ATLA

    # --- her arayüz kendi backend'ini boş bir porta açsın (hepsi ya da hiçbiri) ---
    if "_portOverride" in t:
        d["backend için ayrı port"] = VAR
    else:
        yeni = t
        ok = True
        m = re.search(r"static Future<int> discoverPort\(\{[^}]*\}\)\s*async\s*\{\r?\n", yeni)
        if m:
            govde = "    if (_portOverride != null) return _portOverride!;" + nl
            yeni = yeni[: m.end()] + govde + yeni[m.end():]
            yeni = yeni[: m.start()] + "static int? _portOverride;" + nl + nl + "  " + yeni[m.start():]
        else:
            ok = False
        if ok and "if (await _isServerRunning()) return;" in yeni:
            yeni = yeni.replace("if (await _isServerRunning()) return;",
                                "if (!AppConfig.isExeMode && await _isServerRunning()) return;", 1)
        else:
            ok = False
        if ok and "final cmd = AppConfig.backendCommand();" in yeni:
            yeni = yeni.replace("final cmd = AppConfig.backendCommand();", nl_uygula(PORT_SECIMI_METNI, nl), 1)
        else:
            ok = False
        if ok:
            m4 = re.search(r"unawaited\(_launcher\.launch\(\)\);\s*\r?\n\s*unawaited\(_backend\.connect\(\)\);", yeni)
            if m4:
                yeni = yeni[: m4.start()] + nl_uygula(ARDISIK_BASLATMA_METNI, nl) + yeni[m4.end():]
            else:
                ok = False
        if ok:
            t = yeni
            d["backend için ayrı port"] = OK
        else:
            d["backend için ayrı port"] = ATLA
    return t


def gosterge_adimlari(t, nl, d):
    """Satır göstergesi: ValueListenableBuilder(setState) yerine CustomPainter(repaint: notifier)."""
    ad = "gösterge çizimi (donma/gecikme düzeltmesi)"
    if "super(repaint: notifier)" in t:
        d[ad] = VAR
        return t

    sinif = re.search(r"class _EditorIndicatorPainter extends CustomPainter \{.*?\r?\n\}\r?\n", t, flags=re.S)
    if not sinif:
        d[ad] = YOK
        return t
    blok = sinif.group(0)
    yeni = blok
    yeni = yeni.replace("final re.CodeIndicatorValue? value;",
                        "final ValueListenable<re.CodeIndicatorValue?> notifier;" + nl +
                        "  re.CodeIndicatorValue? get value => notifier.value;", 1)
    yeni = yeni.replace("required this.value,", "required this.notifier,", 1)
    yeni, n1 = re.subn(r"(required this\.fontSize,\s*\})\);", r"\1) : super(repaint: notifier);", yeni, count=1)
    yeni = yeni.replace("old.value != value ||", "old.notifier != notifier ||", 1)
    if n1 != 1 or "ValueListenable<re.CodeIndicatorValue?> notifier" not in yeni \
            or "required this.notifier," not in yeni or "old.notifier != notifier" not in yeni:
        d[ad] = YOK
        return t
    t2 = t[: sinif.start()] + yeni + t[sinif.end():]

    # kullanım yeri: ValueListenableBuilder -> Builder (parantez yapısı aynı kalır)
    t3, n2 = re.subn(
        r"ValueListenableBuilder<re\.CodeIndicatorValue\?>\(\s*valueListenable:\s*notifier,\s*builder:\s*\(context,\s*value,\s*_\)\s*=>",
        "Builder(builder: (context) =>", t2, count=1)
    t4, n3 = re.subn(r"(_EditorIndicatorPainter\(\s*)value:\s*value,", r"\1notifier: notifier,", t3, count=1)
    if n2 != 1 or n3 != 1:
        d[ad] = YOK
        return t
    d[ad] = OK
    return t4


def main_adimlari(t, nl):
    d = {}

    # 1) import
    if "import 'guncelleme.dart';" in t:
        d["import guncelleme.dart"] = VAR
    else:
        imports = list(re.finditer(r"^import [^\n]*;[^\n]*\n", t, flags=re.M))
        if imports:
            son = imports[-1]
            t = t[: son.end()] + "import 'guncelleme.dart';" + nl + t[son.end():]
            d["import guncelleme.dart"] = OK
        else:
            d["import guncelleme.dart"] = YOK

    # 2) EditorProvider.saveAllForExit
    if "saveAllForExit()" in t and "Future<bool> saveAllForExit" in t:
        d["EditorProvider.saveAllForExit"] = VAR
    else:
        bulunan = list(re.finditer(r"^  void autoSave\(\) \{", t, flags=re.M))
        if len(bulunan) == 1:
            i = bulunan[0].start()
            t = t[:i] + nl_uygula(KAYDET_YONTEMI.lstrip("\n"), nl) + nl + t[i:]
            d["EditorProvider.saveAllForExit"] = OK
        else:
            d["EditorProvider.saveAllForExit"] = YOK

    # 3) açılış denetimi: kaydet geri çağrısı
    if "saveAllForExit" in t and re.search(
            r"guncellemeKontrolEt\([^;]*kaydet:\s*context\.read<EditorProvider>\(\)\.saveAllForExit", t, flags=re.S):
        d["açılış denetimi (kaydet)"] = VAR
    else:
        desen = re.compile(r"guncellemeKontrolEt\(\s*context\s*,\s*backend\.call\s*\)")
        if desen.search(t):
            t = desen.sub(
                "guncellemeKontrolEt(context, backend.call,"
                " kaydet: context.read<EditorProvider>().saveAllForExit)", t, count=1)
            d["açılış denetimi (kaydet)"] = OK
        else:
            d["açılış denetimi (kaydet)"] = YOK

    # 4) menü grubu
    m = re.search(r"(static const List<String> _groups = \[)(.*?)(\];)", t, flags=re.S)
    if not m:
        d["menü grubu"] = YOK
    elif "'Güncelleştirmeler'" in m.group(2):
        d["menü grubu"] = VAR
    elif "'Yardım'" not in m.group(2):
        d["menü grubu"] = YOK
    else:
        govde = m.group(2).rstrip().rstrip(",")
        yeni = govde + "," + nl + "    'Güncelleştirmeler'" + nl + "  "
        t = t[: m.start(2)] + yeni + t[m.end(2):]
        d["menü grubu"] = OK

    # 5) menü aksiyonu
    if "id: 'update.check'" in t:
        d["menü aksiyonu"] = VAR
    else:
        m = re.search(r"\n  \];\n\}\n\nAppAction\? findAction\(", t.replace("\r\n", "\n"))
        if not m:
            d["menü aksiyonu"] = YOK
        else:
            # \r\n olabilir: konumu orijinal metinde yeniden bul
            desen = re.compile(r"(\r?\n)  \];(\r?\n)\}(\r?\n)(\r?\n)AppAction\? findAction\(")
            mm = desen.search(t)
            if not mm:
                d["menü aksiyonu"] = YOK
            else:
                ekle = nl_uygula(MENU_AKSIYONU, nl)
                t = t[: mm.start() + len(mm.group(1))] + ekle + t[mm.start() + len(mm.group(1)):]
                d["menü aksiyonu"] = OK

    # 6) backend başlatma (paketlenmiş exe, --parent-pid, ayrı port)
    t = backend_adimlari(t, nl, d)
    t = acilis_adimlari(t, nl, d)
    t = gosterge_adimlari(t, nl, d)
    return t, d


# ----------------------------------------------------------------------------
# ide_core.py
# ----------------------------------------------------------------------------
IMPORT_BLOGU = """try:
    from .pip_tr import pip_komutu_cevir
except ImportError:
    from pip_tr import pip_komutu_cevir


"""

TERMINAL_BLOGU = """python_exe, _ = self._python_exe_bul()
{i}yeni_komut = pip_komutu_cevir(komut, python_exe, self._kullanici_paket_yolu())
{i}if yeni_komut:
{i}    komut = yeni_komut
"""


def core_adimlari(t, nl):
    d = {}

    if "pip_komutu_cevir" in t and "from .pip_tr import" in t:
        d["pip_tr içe aktarma"] = VAR
    else:
        m = re.search(r"^class IDECore\b", t, flags=re.M)
        if m:
            t = t[: m.start()] + nl_uygula(IMPORT_BLOGU, nl) + t[m.start():]
            d["pip_tr içe aktarma"] = OK
        else:
            d["pip_tr içe aktarma"] = YOK

    if "yeni_komut = pip_komutu_cevir(" in t:
        d["terminal pip komutu"] = VAR
    elif "def _kullanici_paket_yolu" not in t:
        d["terminal pip komutu"] = YOK  # önceki yama (ide_core Yama 4) uygulanmamış
    else:
        # a) eski yama bloğu varsa değiştir
        eski = re.compile(
            r"(?P<ind>[ \t]+)python_exe, _ = self\._python_exe_bul\(\)\r?\n"
            r"(?:.*\r?\n)*?"
            r"[ \t]+komut = f['\"]\\?\"\{python_exe\}\\?\" -m pip \{rest\}['\"]\r?\n")
        m = eski.search(t)
        if m:
            ind = m.group("ind")
            yeni = ind + nl_uygula(TERMINAL_BLOGU.format(i=ind), nl)
            t = t[: m.start()] + yeni + t[m.end():]
            d["terminal pip komutu"] = OK
        else:
            # b) blok hiç yoksa fonksiyonun başına ekle
            m = re.search(
                r"(    def _terminal_komut_calistir\(self, komut[^\n]*\)\s*:\r?\n)(\s*try:\r?\n)", t)
            if m:
                ind = "            "
                ekle = ind + nl_uygula(TERMINAL_BLOGU.format(i=ind), nl)
                t = t[: m.end()] + ekle + t[m.end():]
                d["terminal pip komutu"] = OK
            else:
                d["terminal pip komutu"] = YOK

    if "pip install {" in t:
        t = t.replace("pip install {", "pip yükle {")
        d["'pip install' mesajları"] = OK
    else:
        d["'pip install' mesajları"] = VAR
    return t, d


# ----------------------------------------------------------------------------
# server.py
# ----------------------------------------------------------------------------
def server_adimlari(t, nl):
    d = {}
    if "guncelleme_indir_baslat" in t:
        d["indirme ilerleme komutları"] = VAR
        return t, d
    m = re.search(r'^SYNC_COMMANDS\["guncelleme_indir"\][^\n]*\n', t, flags=re.M)
    if not m:
        d["indirme ilerleme komutları"] = YOK
        return t, d
    ekle = (
        'SYNC_COMMANDS["guncelleme_indir_baslat"] = lambda params: updater.indir_baslat()' + nl +
        'SYNC_COMMANDS["guncelleme_indir_durum"] = lambda params: updater.indir_durum()' + nl)
    t = t[: m.end()] + ekle + t[m.end():]
    d["indirme ilerleme komutları"] = OK
    return t, d


# ----------------------------------------------------------------------------
def yamala(yol, adimlar, opsiyonel=False):
    if not yol.exists():
        print(f"\n{yol.relative_to(KOK)}: DOSYA YOK" + (" (isteğe bağlı, atlandı)" if opsiyonel else ""))
        return opsiyonel
    metin = oku(yol)
    nl = "\r\n" if "\r\n" in metin else "\n"
    yeni, durumlar = adimlar(metin, nl)
    print(f"\n{yol.relative_to(KOK)}")
    for ad, durum in durumlar.items():
        isaret = "[!]" if durum == YOK else ("[-]" if durum == ATLA else "[OK]")
        print(f"  {isaret} {ad}: {durum}")
    if YOK in durumlar.values():
        print("  -> Dosyaya DOKUNULMADI (beklenen kod bulunamadı; yamayı elle uygula).")
        return False
    if yeni != metin:
        yedek = yol.with_name(yol.name + f".bak-{ZAMAN}")
        yaz(yedek, metin)
        yaz(yol, yeni)
        print(f"  yedek: {yedek.name}")
    return True


def main():
    sonuc = [
        yamala(MAIN, main_adimlari),
        yamala(CORE, core_adimlari),
        yamala(SERVER, server_adimlari),
    ]
    print()
    if all(sonuc):
        print("Tüm yamalar uygulandı / zaten uygulanmıştı.")
        return 0
    print("Bazı dosyalar yamalanamadı; yukarıdaki [!] satırlarına bak.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
