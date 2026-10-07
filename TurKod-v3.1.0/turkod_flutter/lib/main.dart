import 'dart:async';
import 'guncelleme.dart';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' show AppExitResponse;
import 'package:flutter/gestures.dart'; // PointerScrollEvent buradan gelir
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show RenderAbstractViewport;
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path/path.dart' as p;
import 'package:re_editor/re_editor.dart' as re;
import 'acilis_ekrani.dart';

extension _CodeLineSelectionX on re.CodeLineSelection {
  bool get isValid => baseIndex >= 0 && extentIndex >= 0;
}

// ============================================================================
// SABİTLER
// ============================================================================

const String kMonoFontFamily = 'Consolas';
const List<String> kMonoFontFallback = ['Menlo', 'Courier New', 'monospace'];

/// Ayarlar sekmesi özel bir sekmedir; dosya gibi davranmaz.
const String kSettingsPath = 'internal:settings';

/// Terminal çıktısı için maksimum karakter sayısı.
/// 200 bin karakter: terminal metni her güncellemede yeniden dizilir; 500 bin
/// karakter düşük RAM'li makinelerde onlarca MB'lık yerleşim belleği ve
/// belirgin takılma demekti.
const int kMaxTermChars = 200000;

/// Panel aç/kapa animasyonu.
const Duration kAnim = Duration(milliseconds: 200);
const Curve kAnimCurve = Curves.easeOutCubic;
// NOT (dürüstlük payı): Flutter'ın cihazda kurulu TÜM fontları taşıyıcı bir
// eklenti olmadan (ör. native bir font-numaralandırma plugin'i) programatik
// olarak listelemesinin standart/yerleşik bir yolu yok. Bu yüzden burada
// Windows/macOS/Linux'ta yaygın olarak bulunan fontlardan oluşan bir öneri
// listesi sunuyoruz + kullanıcı arama kutusuna kendi sistemindeki tam font
// adını serbestçe yazabiliyor (yazı tipi kurulu değilse sessizce moifontuna
// düşer, çökme olmaz).
const List<String> kCommonFonts = [
  'Consolas',
  'Cascadia Code',
  'Cascadia Mono',
  'Courier New',
  'Lucida Console',
  'Segoe UI',
  'Calibri',
  'Arial',
  'Times New Roman',
  'Verdana',
  'Tahoma',
  'Georgia',
  'Trebuchet MS',
  'Comic Sans MS',
  'Impact',
  'Menlo',
  'Monaco',
  'SF Mono',
  'Helvetica',
  'Helvetica Neue',
  'San Francisco',
  'Ubuntu Mono',
  'Ubuntu',
  'DejaVu Sans Mono',
  'Liberation Mono',
  'Noto Sans Mono',
  'Roboto Mono',
  'Source Code Pro',
  'Fira Code',
  'Fira Mono',
  'JetBrains Mono',
  'Inconsolata',
  'Hack',
  'IBM Plex Mono',
  'Droid Sans Mono',
];
const Map<String, List<String>> kFallbackAiModels = {
  'OpenAI': ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
  'Groq': ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'],
  'Gemini': ['gemini-2.0-flash', 'gemini-1.5-flash'],
  'Claude': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
};

// ============================================================================
// MODELLER
// ============================================================================

class BackendEvent {
  final String name;
  final Map<String, dynamic> data;
  BackendEvent({required this.name, required this.data});
}

class BackendException implements Exception {
  final String message;
  final Map<String, dynamic>? data;
  BackendException(this.message, {this.data});
  factory BackendException.fromResult(Map<String, dynamic> result) {
    String msg = result['error']?.toString() ??
        result['hata']?.toString() ??
        'Bilinmeyen hata';
    if (result['hatalar'] is List && (result['hatalar'] as List).isNotEmpty) {
      final h = (result['hatalar'] as List).first;
      if (h is Map) msg = "Satır ${h['satir']}: ${h['mesaj']}";
    }
    return BackendException(msg, data: result);
  }
  @override
  String toString() => message;
}

class FileNode {
  final String name;
  final String path;
  final bool isDir;
  List<FileNode> children;
  bool expanded;
  bool loaded;
  FileNode({
    required this.name,
    required this.path,
    required this.isDir,
    this.children = const [],
    this.expanded = false,
    this.loaded = false,
  });
}

class EditorTab {
  static int _seq = 0;

  final String id;
  final String path;
  final String name;
  String content;
  bool dirty;

  EditorTab({
    String? id,
    required this.path,
    required this.name,
    required this.content,
    this.dirty = false,
  }) : id = id ?? 'tab_${_seq++}';
}

enum AiRole { user, assistant }

class AiPart {
  final String type;
  final String content;
  final String? language;
  AiPart({required this.type, required this.content, this.language});
}

class AiMessage {
  final AiRole role;
  final List<AiPart> parts;
  AiMessage({required this.role, required this.parts});
}

/// Akıllı düzeltme raporundaki tek bir düzeltme ya da öneri.
class FixItem {
  final int? line;
  final String title;
  final String detail;
  final int confidence;
  final String category;
  final String level; // hata | uyari | bilgi
  final String hint;
  const FixItem({
    this.line,
    required this.title,
    this.detail = '',
    this.confidence = 0,
    this.category = '',
    this.level = 'bilgi',
    this.hint = '',
  });

  static List<FixItem> listFrom(Object? raw) {
    if (raw is! List) return const [];
    return [
      for (final e in raw)
        if (e is Map)
          FixItem(
            line: (e['satir'] as num?)?.toInt(),
            title: e['baslik']?.toString() ?? '',
            detail: e['aciklama']?.toString() ?? '',
            confidence: (e['guven'] as num?)?.toInt() ?? 0,
            category: e['kategori']?.toString() ?? '',
            level: e['seviye']?.toString() ?? 'bilgi',
            hint: e['oneri']?.toString() ?? '',
          ),
    ];
  }
}

/// Akıllı düzeltme motorunun raporu (backend: akilli_duzeltici.py).
class FixReport {
  final String summary;
  final String status; // ok | hata | sozdizimi | zaman_asimi | atlandi
  final int health;
  final int confidence;
  final int durationMs;
  final int runs;
  final List<FixItem> fixes;
  final List<FixItem> warnings;
  final List<String> thoughts;
  const FixReport({
    required this.summary,
    required this.status,
    required this.health,
    required this.confidence,
    required this.durationMs,
    required this.runs,
    required this.fixes,
    required this.warnings,
    required this.thoughts,
  });

  static FixReport? fromJson(Object? raw) {
    if (raw is! Map) return null;
    return FixReport(
      summary: raw['ozet']?.toString() ?? '',
      status: raw['durum']?.toString() ?? '',
      health: (raw['saglik'] as num?)?.toInt() ?? 0,
      confidence: (raw['guven'] as num?)?.toInt() ?? 0,
      durationMs: (raw['sure_ms'] as num?)?.toInt() ?? 0,
      runs: (raw['calistirma'] as num?)?.toInt() ?? 0,
      fixes: FixItem.listFrom(raw['duzeltmeler']),
      warnings: FixItem.listFrom(raw['uyarilar']),
      thoughts: [
        for (final t in (raw['dusunceler'] as List? ?? const [])) t.toString()
      ],
    );
  }
}

class FixResult {
  final String code;
  final String diff;
  final List<String> changes;
  final FixReport? report;
  final String verification;
  final bool codeChanged;
  FixResult({
    required this.code,
    required this.diff,
    required this.changes,
    this.report,
    this.verification = '',
    this.codeChanged = true,
  });
}

// ============================================================================
// BACKEND SERVİSİ
// ============================================================================

class AppConfig {
  static const int preferredPort = 8765;
  static const String portFileName = 'turkod_backend_port';
  static String get _portFile =>
      p.join(Directory.systemTemp.path, portFileName);
  static int? _portOverride;

  static Future<int> discoverPort({int retries = 10, int delayMs = 500}) async {
    if (_portOverride != null) return _portOverride!;
    final file = File(_portFile);
    for (var i = 0; i < retries; i++) {
      if (await file.exists()) {
        try {
          final port = int.tryParse((await file.readAsString()).trim());
          if (port != null && port > 0 && port < 65536) return port;
        } catch (_) {}
      }
      await Future.delayed(Duration(milliseconds: delayMs));
    }
    return preferredPort;
  }

  /// Backend'in WebSocket erişim anahtarı (BackendLauncher her başlatmada
  /// yenisini üretir ve TURKOD_TOKEN ortam değişkeniyle backend'e verir).
  static String _token = '';

  static Future<String> get wsUrl async {
    final port = await discoverPort();
    return 'ws://127.0.0.1:$port/ws?token=${Uri.encodeQueryComponent(_token)}';
  }

  /// Paketlenmiş backend: <uygulama klasörü>\backend\turkod_backend.exe
  static String get packagedBackendExe => p.join(
      p.dirname(Platform.resolvedExecutable), 'backend', 'turkod_backend.exe');

  /// EXE modunda mı çalışıyoruz? backend\turkod_backend.exe yanımızdaysa evet.
  /// (`flutter run` sırasında bu dosya olmadığından geliştirme moduna düşer.)
  static bool get isExeMode =>
      Platform.isWindows && File(packagedBackendExe).existsSync();


  /// Dev modda repo kökü: turkod_ide\server.py'yi içeren ilk üst klasör.
  /// Hem çalışma dizininden (`flutter run`) hem exe'nin klasöründen
  /// (build\windows\x64\runner\Debug\turkod_flutter.exe'ye çift tıklama)
  /// yukarı doğru aranır; bulunamazsa eski davranışa (cwd'nin üstü) düşer.
  static String get _repoKok {
    for (final bas in [
      Directory.current.path,
      p.dirname(Platform.resolvedExecutable),
    ]) {
      var dizin = p.normalize(p.absolute(bas));
      while (true) {
        if (File(p.join(dizin, 'turkod_ide', 'server.py')).existsSync()) {
          return dizin;
        }
        final ust = p.dirname(dizin);
        if (ust == dizin) break;
        dizin = ust;
      }
    }
    return p.dirname(Directory.current.path);
  }

  /// Backend başlatma komutu.
  /// --parent-pid: arayüz (bu süreç) hangi yolla kapanırsa kapansın backend
  /// kendini ve çalıştırdığı programları kapatır (geliştirici kipinde de).
  static List<String> backendCommand() {
    if (isExeMode) {
      return [packagedBackendExe, '--backend', '--parent-pid', '$pid'];
    }
    final python = Platform.isWindows ? 'python' : 'python3';
    return [python, '-u', '-m', 'turkod_ide.server', '--parent-pid', '$pid'];
  }

  /// Backend çalışma dizini (dev modda repo kökü gerekli).
  static String backendWorkingDir() =>
    isExeMode ? p.dirname(packagedBackendExe) : _repoKok;
}

class BackendService {
  WebSocketChannel? _channel;
  int _nextId = 1;
  bool _isConnected = false, _connecting = false, _disposed = false;
  Timer? _reconnectTimer;
  final Map<int, Completer<Map<String, dynamic>>> _pending = {};
  final StreamController<BackendEvent> _events = StreamController.broadcast();
  final StreamController<bool> _connectionState = StreamController.broadcast();
  BackendService();
  bool get isConnected => _isConnected;
  Stream<BackendEvent> get events => _events.stream;
  Stream<bool> get connectionStream => _connectionState.stream;
  Future<void> waitUntilConnected() async {
    if (_isConnected) return;
    await connectionStream.firstWhere((c) => c);
  }

  Future<void> connect() async {
    if (_disposed || _isConnected || _connecting) return;
    _connecting = true;
    final url = await AppConfig.wsUrl;
    WebSocketChannel? channel;
    try {
      channel = WebSocketChannel.connect(Uri.parse(url));
      await channel.ready.timeout(const Duration(seconds: 3));
      _channel = channel;
      _isConnected = true;
      _reconnectTimer?.cancel();
      _connectionState.add(true);
      channel.stream.listen(
        _onMessage,
        onError: (_) => _onDone(),
        onDone: _onDone,
        cancelOnError: true,
      );
    } catch (_) {
      try {
        await channel?.sink.close();
      } catch (_) {}
      _scheduleReconnect();
    } finally {
      _connecting = false;
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final msg = jsonDecode(raw as String);
      if (msg is! Map<String, dynamic>) return;
      if (msg.containsKey('event')) {
        _events.add(BackendEvent(
          name: msg['event'].toString(),
          data:
              msg['data'] is Map ? Map<String, dynamic>.from(msg['data']) : {},
        ));
        return;
      }
      final id = msg['id'];
      if (id is int && _pending.containsKey(id)) {
        final c = _pending.remove(id)!;
        if (c.isCompleted) return;
        if (msg['ok'] == true) {
          c.complete(msg['result'] is Map
              ? Map<String, dynamic>.from(msg['result'] as Map)
              : {});
        } else {
          c.completeError(BackendException(_extractError(msg), data: msg));
        }
      }
    } catch (_) {}
  }

  // Backend iki farklı biçimde hata bildirebiliyor:
  //  1) Protokol seviyesi hatalar (bilinmeyen komut, eksik parametre vb.):
  //     üst seviyede {"error": "..."}.
  //  2) Komuta özgü hatalar (syntax hatası, çeviri hatası, çalıştırma
  //     hatası vb.): {"result": {"hata": "..."}} veya
  //     {"result": {"hatalar": [{"satir":.., "sutun":.., "mesaj":..}, ...]}}.
  // Önceden yalnızca (1) okunuyordu; (2) durumunda mesaj hep sabit "Hata"
  // metnine düşüyor, gerçek sebep hiç görünmüyordu. Artık ikisi de okunuyor.
  String _extractError(Map<String, dynamic> msg) {
    final topLevel = msg['error']?.toString();
    if (topLevel != null && topLevel.trim().isNotEmpty) return topLevel;

    final result = msg['result'];
    if (result is Map) {
      final tek = result['hata'];
      if (tek != null && tek.toString().trim().isNotEmpty)
        return tek.toString();

      final liste = result['hatalar'];
      if (liste is List && liste.isNotEmpty) {
        return liste.map((h) {
          if (h is Map) {
            final mesaj = h['mesaj']?.toString() ?? h.toString();
            final satir = h['satir'];
            final sutun = h['sutun'];
            // Backend mesajı konumu zaten "Satır X, sütun Y: ..." diye
            // başlatıyorsa tekrar eklenmez (eskiden konum iki kez yazılıyordu).
            final konum = satir != null && !mesaj.startsWith('Satır ')
                ? ' (satır $satir${sutun != null ? ', sütun $sutun' : ''})'
                : '';
            return '$mesaj$konum';
          }
          return h.toString();
        }).join('\n');
      }
    }
    return 'Bilinmeyen hata (komut: ${msg['id']})';
  }

  void _onDone() {
    if (_disposed) return;
    _isConnected = false;
    _connectionState.add(false);
    for (var c in _pending.values) {
      if (!c.isCompleted) c.completeError(BackendException('Bağlantı koptu'));
    }
    _pending.clear();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_disposed || _reconnectTimer != null || _isConnected) return;
    _reconnectTimer = Timer(const Duration(seconds: 2), () {
      _reconnectTimer = null;
      connect();
    });
  }

  Future<Map<String, dynamic>> call(String command,
      [Map<String, dynamic> params = const {}]) async {
    if (_channel == null || !_isConnected) {
      throw BackendException('Backend bağlı değil');
    }
    final id = _nextId++;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    try {
      _channel!.sink
          .add(jsonEncode({'id': id, 'command': command, 'params': params}));
    } catch (e) {
      // Soket kapanmış ama _onDone henüz çalışmamış: istek sahipsiz kalıp
      // yakalanmamış bir async hataya dönüşmesin.
      _pending.remove(id);
      throw BackendException('Backend bağlı değil');
    }
    return completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
      _pending.remove(id);
      throw BackendException('Zaman aşımı: $command');
    }).then((res) {
      if (res['ok'] == false) throw BackendException.fromResult(res);
      return res;
    });
  }

  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _events.close();
    _connectionState.close();
  }
}

enum BackendDurum { baslatiliyor, calisiyor, durdu }

/// Backend sürecini başlatır, izler ve çökerse yeniden başlatır.
///
/// Her arayüz kendi backend'ini boş bir porta ve rastgele bir erişim anahtarıyla
/// açar (önceki oturumlardan kalan backend'lere ya da bayat port dosyasına
/// takılmaz). [BackendService] her yeniden bağlanma denemesinde güncel port ve
/// anahtarı [AppConfig]'den okuduğundan, yeniden başlatmadan sonra kendiliğinden
/// yeni sürece bağlanır.
class BackendLauncher {
  Process? _process;
  bool _disposed = false;
  final StreamController<String> errors = StreamController.broadcast();
  final ValueNotifier<BackendDurum> durum =
      ValueNotifier(BackendDurum.baslatiliyor);

  /// Son başarısız başlatmanın açıklaması (bağlantı bannerında gösterilir).
  String? sonHata;

  // Otomatik yeniden başlatma sınırı: çöküp duran bir backend sonsuz döngüye
  // girmesin; sınır aşılınca kullanıcı bannerdaki düğmeyle yeniden başlatır.
  static const int _maksOtomatik = 3;
  static const Duration _otomatikPencere = Duration(minutes: 2);
  final List<DateTime> _otomatikBaslatmalar = [];
  Future<bool>? _surenBaslatma;

  /// Sürecin son çıktı satırları (açılamazsa hata mesajında gösterilir).
  final List<String> _sonCikti = [];
  static const int _maksCiktiSatiri = 12;

  static String _yeniAnahtar() {
    final r = math.Random.secure();
    final bytes = List<int>.generate(32, (_) => r.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }

  /// Backend'i (önceki süreci kapatarak) başlatır; port açılınca true döner.
  /// Aynı anda gelen çağrılar tek başlatmayı paylaşır.
  Future<bool> launch() => _surenBaslatma ??=
      _launch().whenComplete(() => _surenBaslatma = null);

  Future<bool> _launch() async {
    _oncekiniKapat();
    if (_disposed) return false;
    durum.value = BackendDurum.baslatiliyor;
    _sonCikti.clear();
    final Process proc;
    final bitti = Completer<void>();
    try {
      final s = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
      final port = s.port;
      await s.close();
      final anahtar = _yeniAnahtar();
      final cmd = AppConfig.backendCommand()..addAll(['--port', '$port']);
      proc = await Process.start(
        cmd.first,
        cmd.skip(1).toList(),
        workingDirectory: AppConfig.backendWorkingDir(),
        environment: {'TURKOD_TOKEN': anahtar},
        // detachedWithStdio: geliştirici kipinde python.exe için konsol
        // penceresi açılmaz. Bu kipte exitCode alınamaz; sürecin bittiği,
        // stdout/stderr borularının kapanmasından anlaşılır.
        mode: ProcessStartMode.detachedWithStdio,
      );
      _process = proc;
      AppConfig._portOverride = port;
      AppConfig._token = anahtar;
      // Borular okunmazsa (birkaç KB sonra) backend'deki her print/traceback
      // bloke olur ve IDE donmuş görünür; çıktı okunur, son satırlar tutulur.
      var acikBoru = 2;
      void boruKapandi() {
        if (--acikBoru == 0 && !bitti.isCompleted) bitti.complete();
      }

      for (final boru in [proc.stdout, proc.stderr]) {
        boru
            .transform(const Utf8Decoder(allowMalformed: true))
            .transform(const LineSplitter())
            .listen(_ciktiSatiri,
                onDone: boruKapandi,
                onError: (_) => boruKapandi(),
                cancelOnError: true);
      }
    } catch (e) {
      return _basarisiz('Python backend başlatılamadı: $e');
    }

    final acildi = await _waitForPort(bitti.future);
    if (!identical(_process, proc)) return false; // bu arada yeniden başlatıldı
    if (!acildi) {
      final kapandi = bitti.isCompleted;
      _oncekiniKapat();
      final ayrinti = _sonCikti.isEmpty ? '' : '\n\n${_sonCikti.join('\n')}';
      return _basarisiz(kapandi
          ? 'Python backend başlatılamadı: süreç hemen kapandı.$ayrinti'
          : 'Python backend başlatılamadı: sunucu 60 sn içinde açılmadı.$ayrinti');
    }
    sonHata = null;
    durum.value = BackendDurum.calisiyor;
    unawaited(bitti.future.then((_) {
      if (identical(_process, proc)) _beklenmedikKapanma();
    }));
    return true;
  }

  bool _basarisiz(String mesaj) {
    sonHata = mesaj;
    durum.value = BackendDurum.durdu;
    if (!_disposed) errors.add(mesaj);
    return false;
  }

  void _ciktiSatiri(String satir) {
    if (satir.trim().isEmpty) return;
    _sonCikti.add(satir);
    if (_sonCikti.length > _maksCiktiSatiri) _sonCikti.removeAt(0);
  }

  void _beklenmedikKapanma() {
    _process = null;
    if (_disposed) return;
    sonHata = 'Backend beklenmedik biçimde kapandı.';
    durum.value = BackendDurum.durdu;
    unawaited(_otomatikYenidenBaslat());
  }

  Future<void> _otomatikYenidenBaslat() async {
    final simdi = DateTime.now();
    _otomatikBaslatmalar
        .removeWhere((t) => simdi.difference(t) > _otomatikPencere);
    if (_otomatikBaslatmalar.length >= _maksOtomatik) {
      sonHata = 'Backend art arda kapandı; otomatik yeniden başlatma durduruldu.';
      durum.value = BackendDurum.durdu;
      return;
    }
    _otomatikBaslatmalar.add(simdi);
    await launch();
  }

  /// Bağlantı koptuğunda çağrılır: süreç borularını açık tutan bir alt süreç
  /// yüzünden kapanma fark edilmemişse portu yoklar; kapalıysa yeniden başlatır.
  Future<void> baglantiKoptu() async {
    if (_disposed || durum.value != BackendDurum.calisiyor) return;
    if (await _portAcikMi()) return;
    if (durum.value == BackendDurum.calisiyor) _beklenmedikKapanma();
  }

  /// Kullanıcının istediği yeniden başlatma (sınır uygulanmaz).
  Future<bool> yenidenBaslat() {
    _otomatikBaslatmalar.clear();
    return launch();
  }

  Future<bool> _portAcikMi() async {
    final port = AppConfig._portOverride;
    if (port == null) return false;
    try {
      final s = await Socket.connect('127.0.0.1', port,
          timeout: const Duration(milliseconds: 500));
      s.destroy();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Port açılınca true; süreç kapanırsa ya da 60 sn geçerse false (eskiden
  /// süreç baştan çökmüş olsa da ~90 sn beklenirdi).
  Future<bool> _waitForPort(Future<void> bitti) async {
    var kapandi = false;
    unawaited(bitti.then((_) => kapandi = true));
    final sinir = DateTime.now().add(const Duration(seconds: 60));
    while (!_disposed && DateTime.now().isBefore(sinir)) {
      if (kapandi) return false;
      if (await _portAcikMi()) return true;
      await Future.delayed(const Duration(milliseconds: 250));
    }
    return false;
  }

  void _oncekiniKapat() {
    final eski = _process;
    _process = null;
    if (eski == null) return;
    if (Platform.isWindows) {
      Process.run('taskkill', ['/F', '/T', '/PID', '${eski.pid}']);
    } else {
      eski.kill(ProcessSignal.sigterm);
    }
  }

  void dispose() {
    _disposed = true;
    _oncekiniKapat();
  }
}

// ============================================================================
// METİN YARDIMCILARI
// ============================================================================

int _lineStart(String text, int offset) {
  var i = offset.clamp(0, text.length);
  while (i > 0 && text[i - 1] != '\n') {
    i--;
  }
  return i;
}

int _lineEnd(String text, int offset) {
  var i = offset.clamp(0, text.length);
  while (i < text.length && text[i] != '\n') {
    i++;
  }
  return i;
}

/// 1 tabanlı satır numarası. Eskiden `substring + split` ile metnin kopyası
/// alınıp bölünüyordu; büyük dosyalarda her tuş vuruşunda megabaytlarca
/// geçici bellek ayırıyordu. Artık yalnızca satır sonları sayılır.
int _lineNumber(String text, int offset) {
  final end = offset.clamp(0, text.length).toInt();
  var n = 1;
  for (var i = text.indexOf('\n');
      i >= 0 && i < end;
      i = text.indexOf('\n', i + 1)) {
    n++;
  }
  return n;
}
int _columnNumber(String text, int offset) => offset - _lineStart(text, offset);

/// toggleComment/duplicateCurrentLine/moveCurrentLine/jumpToLine gibi
/// serbest fonksiyonlar `TextEditingController?` tipinde bir referans
/// alıyor, ama elimizdeki gerçek nesne her zaman [SyntaxHighlightingController]
/// (bkz. EditorProvider.uiController = _ctrl). KÖK NEDEN DÜZELTMESİ: bu
/// fonksiyonlar eskiden ham `c.value =` ataması yapıyordu; bu da
/// _CodeEditorState._onControllerChange/_onChanged içindeki fold-koruması
/// tarafından (programatik olarak işaretlenmediği için) bazen SESSİZCE
/// İPTAL ediliyordu — "yorum satırı yap" veya "satırı taşı" gibi komutların
/// bazen hiçbir şey yapmıyormuş gibi görünmesinin sebebi buydu. Artık tip
/// kontrolü yapıp [SyntaxHighlightingController.setProgrammaticValue]
/// kullanıyoruz; farklı bir controller türü verilirse (örn. testlerde)
/// eski davranışa (ham atama) geri düşüyoruz.
void _setControllerValueProgrammatic(
    TextEditingController c, TextEditingValue v) {
  if (c is SyntaxHighlightingController) {
    c.setProgrammaticValue(v);
  } else {
    c.value = v;
  }
}

void toggleComment(TextEditingController? c) {
  if (c == null) return;
  final t = c.text;
  final sel = c.selection;
  final start = sel.isValid ? sel.start : 0;
  final end = sel.isValid ? sel.end : start;
  final ls = _lineStart(t, start);
  final le = _lineEnd(t, end);
  final lines = t.substring(ls, le).split('\n');
  final nonEmpty = lines.where((l) => l.trim().isNotEmpty).toList();
  final allCommented = nonEmpty.isNotEmpty &&
      nonEmpty.every((l) => l.trimLeft().startsWith('#'));
  final newLines = <String>[];
  for (final l in lines) {
    if (l.trim().isEmpty) {
      newLines.add(l);
    } else if (allCommented) {
      newLines.add(l.replaceFirst(RegExp(r'^(\s*)#\s?'), r'$1'));
    } else {
      newLines.add('# $l');
    }
  }
  final nb = newLines.join('\n');
  _setControllerValueProgrammatic(
    c,
    TextEditingValue(
      text: t.replaceRange(ls, le, nb),
      selection: TextSelection(baseOffset: ls, extentOffset: ls + nb.length),
    ),
  );
}

void duplicateCurrentLine(TextEditingController? c) {
  if (c == null) return;
  final t = c.text;
  final sel = c.selection;
  final start = sel.isValid ? sel.start : 0;
  final end = sel.isValid ? sel.end : start;
  final ls = _lineStart(t, start);
  final le = _lineEnd(t, end);
  final block = t.substring(ls, le);
  final nt = t.replaceRange(le, le, '\n$block');
  _setControllerValueProgrammatic(
    c,
    TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: end + block.length + 1),
    ),
  );
}

void moveCurrentLine(TextEditingController? c, bool up) {
  if (c == null) return;
  final t = c.text;
  final sel = c.selection;
  final pos = sel.isValid ? sel.baseOffset : 0;
  final lines = t.split('\n');
  final lineIndex = _lineNumber(t, pos) - 1;
  if (lineIndex < 0 || lineIndex >= lines.length) return;
  final oldLineStart = _lineStart(t, pos);
  final relCol = pos - oldLineStart;
  int targetIndex;
  if (up) {
    if (lineIndex == 0) return;
    targetIndex = lineIndex - 1;
  } else {
    if (lineIndex >= lines.length - 1) return;
    targetIndex = lineIndex + 1;
  }
  final tmp = lines[lineIndex];
  lines[lineIndex] = lines[targetIndex];
  lines[targetIndex] = tmp;
  final nt = lines.join('\n');
  var newStart = 0;
  for (var i = 0; i < targetIndex; i++) {
    newStart += lines[i].length + 1;
  }
  final movedLen = lines[targetIndex].length;
  final newPos =
      (newStart + math.min(relCol, movedLen)).clamp(0, nt.length).toInt();
  _setControllerValueProgrammatic(
    c,
    TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: newPos),
    ),
  );
}

/// Bir satırın başlangıç offset'ine imleci koyar (listener kaydırmayı yapar).
void jumpToLine(BuildContext context, int line) {
  final c = context.read<EditorProvider>().uiController;
  if (c == null) return;
  jumpToLineIn(c, line);
}

void jumpToLineIn(TextEditingController c, int line) {
  final lines = c.text.split('\n');
  if (line < 1 || line > lines.length) return;
  var off = 0;
  for (var i = 0; i < line - 1; i++) {
    off += lines[i].length + 1;
  }
  final offset = off.clamp(0, c.text.length);
  if (c is SyntaxHighlightingController) {
    c.runProgrammatic(
      () => c.selection = TextSelection.collapsed(offset: offset),
    );
  } else {
    c.selection = TextSelection.collapsed(offset: offset);
  }
}

// ============================================================================
// PROVIDER'LAR
// ============================================================================

class ConnectionProvider extends ChangeNotifier {
  final BackendService _backend;
  final BackendLauncher? _launcher;
  late final StreamSubscription<bool> _sub;
  Timer? _kontrolTimer;
  bool _connected = false;
  bool get connected => _connected;
  BackendDurum get durum => _launcher?.durum.value ?? BackendDurum.calisiyor;
  String? get sonHata => _launcher?.sonHata;
  bool get yenidenBaslatilabilir => _launcher != null;

  ConnectionProvider(this._backend, [this._launcher]) {
    _connected = _backend.isConnected;
    _sub = _backend.connectionStream.listen((c) {
      _connected = c;
      _kontrolTimer?.cancel();
      // Bağlantı koptu ve birkaç saniyede geri gelmedi: backend ölmüş
      // olabilir; başlatıcı portu yoklayıp gerekirse yeniden başlatır.
      if (!c) {
        _kontrolTimer = Timer(const Duration(seconds: 3),
            () => _launcher?.baglantiKoptu());
      }
      notifyListeners();
    });
    _launcher?.durum.addListener(notifyListeners);
  }

  Future<void> yenidenBaslat() async => _launcher?.yenidenBaslat();

  @override
  void dispose() {
    _kontrolTimer?.cancel();
    _launcher?.durum.removeListener(notifyListeners);
    _sub.cancel();
    super.dispose();
  }
}

enum SnackKind { info, success, error }
class AppToast {
  final String message;
  final SnackKind kind;
  final DateTime time;

  AppToast({
    required this.message,
    required this.kind,
    required this.time,
  });

  String get timeText {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(time.hour)}:${two(time.minute)}:${two(time.second)}';
  }
}
class UiProvider extends ChangeNotifier {
  final BackendLauncher? _launcher;

  StreamSubscription<String>? _errSub;
  Timer? _toastTimer;
  Timer? _statusTimer;

  bool showExplorer = true;
  bool showAi = true;
  bool showTerminal = false;

  double sidebarWidth = 240;
  double aiWidth = 340;
  double terminalHeight = 180;

  String statusMessage = 'Hazır';
  String syntaxStatus = '';

  int cursorLine = 1;
  int cursorColumn = 0;

  String? toast;
  SnackKind toastKind = SnackKind.info;

  bool toastHistoryOpen = false;
  final List<AppToast> toastHistory = [];

  static const int _maxToastHistory = 200;

  Offset findOffset = Offset.zero;
  bool findOpen = false;
  bool findReplaceMode = false;
  String findQuery = '';

  // Klavye odağı istekleri: her istekte sayaç artar, ilgili panel (Bul
  // kutusu / terminal girişi) değişikliği görünce odağı kendine alır.
  // Panel o an ağaçta yoksa istek bekletilir ve panel açılır açılmaz
  // tüketilir.
  int findFocusTick = 0;
  String? findSeed;
  int terminalFocusTick = 0;
  bool _terminalFocusPending = false;

  int _pendingLine = 1;
  int _pendingCol = 0;
  bool _cursorScheduled = false;

  UiProvider([this._launcher]) {
    _errSub = _launcher?.errors.stream.listen((m) {
      setStatus(m);
      showToast(m, SnackKind.error);
    });
  }

  void toggleExplorer() {
    showExplorer = !showExplorer;
    notifyListeners();
  }

  void toggleAi() {
    showAi = !showAi;
    notifyListeners();
  }

  void toggleTerminal() {
    showTerminal = !showTerminal;
    notifyListeners();
  }

  /// Terminali (kapalıysa) odağı taşımadan açar.
  void revealTerminal() {
    if (showTerminal) return;
    showTerminal = true;
    notifyListeners();
  }

  /// Terminali (kapalıysa) açar ve klavye odağını komut satırına taşır.
  void focusTerminal() {
    showTerminal = true;
    _terminalFocusPending = true;
    terminalFocusTick++;
    notifyListeners();
  }

  bool consumeTerminalFocus() {
    final v = _terminalFocusPending;
    _terminalFocusPending = false;
    return v;
  }

  void setSidebarWidth(double v) {
    sidebarWidth = v.clamp(180, 420).toDouble();
    notifyListeners();
  }

  void setAiWidth(double v) {
    aiWidth = v.clamp(280, 640).toDouble();
    notifyListeners();
  }

  void setTerminalHeight(double v) {
    terminalHeight = v.clamp(120, 480).toDouble();
    notifyListeners();
  }

  void setStatus(String m) {
    statusMessage = m;
    notifyListeners();
  }

  void flashStatus(String m) {
    statusMessage = m;
    _statusTimer?.cancel();
    _statusTimer = Timer(const Duration(seconds: 4), () {
      statusMessage = 'Hazır';
      notifyListeners();
    });
    notifyListeners();
  }

  /// Durum çubuğundaki ayrıntı (fare üzerine gelince tüm hata/uyarılar).
  String syntaxTooltip = '';

  void setSyntaxStatus(String m, {String tooltip = ''}) {
    if (syntaxStatus == m && syntaxTooltip == tooltip) return;
    syntaxStatus = m;
    syntaxTooltip = tooltip;
    notifyListeners();
  }

  void setCursor(int line, int col) {
    _pendingLine = line;
    _pendingCol = col;

    if (_cursorScheduled) return;

    _cursorScheduled = true;

    Future.microtask(() {
      _cursorScheduled = false;

      if (cursorLine == _pendingLine && cursorColumn == _pendingCol) return;

      cursorLine = _pendingLine;
      cursorColumn = _pendingCol;

      notifyListeners();
    });
  }

  void showToast(String msg, SnackKind kind) {
    final item = AppToast(
      message: msg,
      kind: kind,
      time: DateTime.now(),
    );

    toastHistory.insert(0, item);

    if (toastHistory.length > _maxToastHistory) {
      toastHistory.removeRange(_maxToastHistory, toastHistory.length);
    }

    toast = msg;
    toastKind = kind;

    _toastTimer?.cancel();
    _toastTimer = Timer(const Duration(seconds: 6), () {
      toast = null;
      notifyListeners();
    });

    notifyListeners();
  }

  void dismissToast() {
    _toastTimer?.cancel();
    toast = null;
    notifyListeners();
  }

  void toggleToastHistory() {
    toastHistoryOpen = !toastHistoryOpen;

    if (toastHistoryOpen) {
      _toastTimer?.cancel();
      toast = null;
    }

    notifyListeners();
  }

  void clearToastHistory() {
    toastHistory.clear();
    notifyListeners();
  }

  /// [seed]: editörde seçili (tek satırlık) metin; VS Code'daki gibi arama
  /// kutusuna önceden doldurulur.
  void openFind(bool replace, {String? seed}) {
    findOpen = true;
    findReplaceMode = replace;
    findSeed = seed;
    findFocusTick++;
    notifyListeners();
  }

  String? consumeFindSeed() {
    final v = findSeed;
    findSeed = null;
    return v;
  }

  void closeFind() {
    findOpen = false;
    findQuery = '';
    notifyListeners();
  }

  void setFindQuery(String value) {
    if (findQuery == value) return;
    findQuery = value;
    notifyListeners();
  }

  void setFindOffset(Offset o) {
    findOffset = o;
    notifyListeners();
  }

  @override
  void dispose() {
    _errSub?.cancel();
    _toastTimer?.cancel();
    _statusTimer?.cancel();
    super.dispose();
  }
}

void showAppSnackbar(BuildContext context, String msg,
    {SnackKind kind = SnackKind.info}) {
  if (!context.mounted) return;
  context.read<UiProvider>().showToast(msg, kind);
}

class SettingsProvider extends ChangeNotifier {
  final BackendService _backend;
  final Map<String, dynamic> _values = {};
  Map<String, List<String>> aiModels = Map.from(kFallbackAiModels);
  List<String> systemFonts = [];
  String fontsSource = '';
  bool _loaded = false;
  bool get loaded => _loaded;
  SettingsProvider(this._backend) {
    _init();
  }
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      await load();
    } catch (_) {}
  }

  T? get<T>(String key) => _values[key] as T?;
  String getString(String key, {String fallback = ''}) =>
      _values[key]?.toString() ?? fallback;
  bool getBool(String key, {bool fallback = false}) {
    final v = _values[key];
    if (v is bool) return v;
    if (v == null) return fallback;
    return v.toString().toLowerCase() == 'true';
  }

  int getInt(String key, {int fallback = 0}) {
    final v = _values[key];
    if (v is int) return v;
    if (v is double) return v.round();
    return int.tryParse(v?.toString() ?? '') ?? fallback;
  }

  double getDouble(String key, {double fallback = 0}) {
    final v = _values[key];
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v?.toString() ?? '') ?? fallback;
  }

  Future<void> load() async {
    final keys = [
      'tema', 'otomatik_tamamlama', 'otomatik_kaydetme',
      'otomatik_kaydetme_aralik', 'yazi_boyutu', 'yazi_tipi',
      'satir_numaralari', 'kelime_sar', 'bosluk_gostergesi', 'minimap',
      'ai_aktif', 'ai_saglayici', 'ai_model', 'ai_api_key', 'ai_sistem_mesaji',
      'ai_sicaklik', 'ai_max_token', 'son_proje_dizini', 'gelismis_duzeltme',
      'duzeltme_zaman_asimi', 'duzeltme_mesaj_araligi', 'duzeltme_maks_dongu',
      // Not: app.py'de karşılığı olmayan, yalnızca bu Flutter arayüzüne özgü
      // yeni bir ayar (terminal yazı boyutu). Backend anahtar bazında genel
      // olduğu için ek bir şema değişikliği gerekmiyor.
      'terminal_yazi_boyutu',
      // Editördeki girinti kılavuzları (VS Code "indent guides"). Backend'de
      // varsayılanı yok; null gelirse açık kabul edilir.
      'sutun_cizgileri',
    ];
    // Tüm ayarlar tek istekle alınır (eskiden anahtar başına ayrı istek:
    // ~25 gidiş-dönüş). Başarısız olursa eski yönteme düşülür.
    var bulk = false;
    try {
      final r = await _backend.call('ayarlar_tumu');
      final m = r['ayarlar'];
      if (m is Map) {
        for (final k in keys) {
          _values[k] = m[k];
        }
        bulk = true;
      }
    } catch (_) {}
    if (!bulk) {
      for (final k in keys) {
        try {
          final r = await _backend.call('ayar_get', {'anahtar': k});
          _values[k] = r['deger'];
        } catch (_) {}
      }
    }
    await refreshModels(silent: true);
    // Font listesi burada (açılışta) istenmez: Ayarlar sayfası açılınca
    // yüklenir. Düşük donanımda açılışı ve belleği gereksiz yere yoruyordu.
    _loaded = true;
    notifyListeners();
  }

  Future<void> refreshSystemFonts({bool silent = false}) async {
    try {
      final r = await _backend.call('sistem_fontlari');
      final f = r['fontlar'];
      if (f is List && f.isNotEmpty) {
        systemFonts = f.map((e) => e.toString()).toList();
        fontsSource = r['kaynak']?.toString() ?? '';
        if (!silent) notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> refreshModels({bool silent = false}) async {
    try {
      final r = await _backend.call('ai_modelleri');
      final m = r['modeller'];
      if (m is Map && m.isNotEmpty) {
        aiModels = m.map((k, v) => MapEntry(
              k.toString(),
              v is List ? v.map((e) => e.toString()).toList() : <String>[],
            ));
      }
    } catch (_) {}
  }

  Future<void> setValue(String key, dynamic value) async {
    await _backend.call('ayar_set', {'anahtar': key, 'deger': value});
    _values[key] = value;
    notifyListeners();
  }
}

class LanguageProvider extends ChangeNotifier {
  final BackendService _backend;
  bool loaded = false;
  LanguageProvider(this._backend) {
    _init();
  }
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      final r = await _backend.call('sozluk_verileri');
      final kw = Set<String>.from(
          (r['keyword_words'] as List? ?? []).map((e) => e.toString()));
      final bi = Set<String>.from(
          (r['builtin_words'] as List? ?? []).map((e) => e.toString()));
      final mo = Set<String>.from(
          (r['modul_adlari'] as List? ?? []).map((e) => e.toString()));
      SyntaxHighlightingController.configure(
          keywords: kw, builtins: bi, modules: mo);
      loaded = true;
      notifyListeners();
    } catch (_) {}
  }
}

class EditorProvider extends ChangeNotifier {
  final BackendService _backend;
  final List<EditorTab> _tabs = [];
  final ValueNotifier<String> activeContent = ValueNotifier<String>('');
  int _active = -1;
  int _revision = 0;
  int _untitledCounter = 1;
  bool _sessionLoaded = false;
  TextEditingController? uiController;

  /// Sekme içeriği değiştiğinde (sekme kimliği, eski metin, yeni metin) ile
  /// çağrılır; breakpoint'lerin eklenen/silinen satırlarla kaymasını sağlar.
  void Function(String tabId, String oldText, String newText)? onContentEdited;

  /// Editör, katlamaları hesaba katarak bir MODEL satırına (dosyadaki gerçek
  /// satır) gider. Editör kurulu değilse null.
  void Function(int modelLine)? revealModelLine;

  /// İmlecin bulunduğu MODEL satırı (katlamalar açılmış hâliyle).
  int Function()? caretModelLine;

  /// Editör görünümünü (katlamalar AÇILMIŞ tam metinle) sekmeye aktarır.
  VoidCallback? pushViewContent;

  /// Editördeki tüm katlamaları açar (toplu değişiklik öncesi).
  VoidCallback? unfoldAll;

  /// Kod editörünün odak düğümü (kısayolların editör odaktayken çalışması
  /// için; Bul kutusu editörün alt ağacında olduğu için ata denetimi yetmez).
  FocusNode? editorFocusNode;

  /// uiController üzerinde doğrudan değişiklik yapan araçlar (Bul/Değiştir,
  /// AI "İmlece Ekle") bunu çağırır. Eskiden updateContent(c.text) ile
  /// GÖRÜNÜM metni (katlama yer tutucuları dahil, gizli kod hariç) sekmeye
  /// yazılıyor ve kaydedilince gizli kod dosyadan siliniyordu.
  void syncFromView() {
    final push = pushViewContent;
    if (push != null) {
      push();
    } else if (uiController != null) {
      updateContent(uiController!.text);
    }
  }
  final Map<String, int> _caretMemory = {};
  int? _pendingCaretOffset;
  int? Function()? caretOffsetProvider;

  int? consumePendingCaret() {
    final v = _pendingCaretOffset;
    _pendingCaretOffset = null;
    return v;
  }
  List<EditorTab> get tabs => List.unmodifiable(_tabs);
  int get activeIndex => _active;
  int get revision => _revision;
  EditorTab? get activeTab =>
      _active >= 0 && _active < _tabs.length ? _tabs[_active] : null;
  EditorProvider(this._backend) {
    _init();
  }
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      await loadSession();
    } catch (_) {}
  }
  String suggestUniqueName(String base) {
    // "(n)" uzantıdan ÖNCE eklenir: eskiden "Untitled-1.trpy(1)" oluyor,
    // Farklı Kaydet'in varsayılan dosya adının uzantısı bozuluyordu.
    final ext = p.extension(base);
    final stem = ext.isEmpty ? base : base.substring(0, base.length - ext.length);
    var n = 1;
    var candidate = '$stem($n)$ext';

    while (_tabs.any((t) => t.name == candidate)) {
      n++;
      candidate = '$stem($n)$ext';
    }

    return candidate;
  }
  Future<String?> _confirmUniqueName(BuildContext context, String desired) async {
    final suggested = suggestUniqueName(desired);

    final choice = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Sekme adı'),
        content: Text(
          'Bu isme sahip sekme zaten açık. "$suggested" olarak değiştirilsin mi?',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(dc, 'yes'),
            child: const Text('Evet'),
          ),
          // Eskiden bir "Hayır" düğmesi vardı ama İptal ile aynı şeyi yapıyor
          // (hiçbir sekme açılmıyordu); aynı adla ikinci sekme zaten
          // desteklenmediğinden kaldırıldı.
          TextButton(
            onPressed: () => Navigator.pop(dc, 'cancel'),
            child: const Text('İptal'),
          ),
        ],
      ),
    );

    if (choice == 'yes') return suggested;
    return null;
  }
  void _rememberActiveCaret() {
    final t = activeTab;
    if (t == null || t.path == kSettingsPath) return;

    int? off;

    final provider = caretOffsetProvider;
    if (provider != null) {
      off = provider();
    } else {
      final c = uiController;
      if (c != null && c.selection.isValid) {
        off = c.selection.baseOffset;
      }
    }

    off ??= 0;
    _caretMemory[t.path] = off.clamp(0, t.content.length).toInt();
  }
  /// Oturum: yol (String eski biçim) veya {yol,isim,icerik} map'i desteklenir.
  Future<void> loadSession() async {
    if (_sessionLoaded) return;

    try {
      final r = await _backend.call('oturum_oku');
      final rawList = r['son_oturum'] as List? ?? [];
      // Kaydedilen listedeki her girdinin hangi sekmeyi oluşturduğu: açılamayan
      // (silinmiş) dosyalar aktif sekme sırasını kaydırmasın.
      final restoredIds = <String?>[];

      for (final e in rawList) {
        final onceki = _tabs.length;
        try {
          if (e is String) {
            if (e != kSettingsPath) {
              await openFile(
                e,
                makeActive: false,
                saveSession: false,
              );
            }
          } else if (e is Map) {
            final m = Map<String, dynamic>.from(e);

            final yol = m['yol']?.toString();
            final isim = m['isim']?.toString();
            final icerik = m['icerik']?.toString() ?? '';

            if (yol != null && yol.isNotEmpty && yol != kSettingsPath) {
              await openFile(
                yol,
                makeActive: false,
                saveSession: false,
              );
            } else if (isim != null && isim.isNotEmpty) {
              await createUntitled(
                name: isim,
                content: icerik,
                setActive: false,
                saveSession: false,
              );
            }
          }
        } catch (_) {}
        restoredIds.add(_tabs.length > onceki ? _tabs.last.id : null);
      }

      if (_tabs.isNotEmpty) {
        final raw = r['son_oturum_aktif'];
        final idx = raw is int ? raw : int.tryParse(raw.toString()) ?? 0;
        final hedefId =
            idx >= 0 && idx < restoredIds.length ? restoredIds[idx] : null;
        final bulunan =
            hedefId == null ? -1 : _tabs.indexWhere((t) => t.id == hedefId);

        _active = bulunan >= 0 ? bulunan : idx.clamp(0, _tabs.length - 1);
        activeContent.value = _tabs[_active].content;
        _pendingCaretOffset = _caretMemory[_tabs[_active].path];
      }

      _sessionLoaded = true;
      _revision++;
      notifyListeners();
    } catch (_) {}
  }

  /// Kaydedilen sekme listesi Ayarlar sekmesini içermez; aktif sıra da o
  /// listeye göre hesaplanmalı (eskiden Ayarlar sekmesi soldayken geri
  /// yüklemede yanlış sekme aktif oluyordu).
  Map<String, dynamic> _sessionPayload() {
    final kayitli = _tabs.where((t) => t.path != kSettingsPath).toList();
    final aktifId = activeTab?.id;
    final sira = kayitli.indexWhere((t) => t.id == aktifId);
    return {
      'sekmeler': kayitli
          .map((t) => t.path.startsWith('untitled:')
              ? {'yol': null, 'isim': t.name, 'icerik': t.content}
              : {'yol': t.path, 'isim': t.name, 'icerik': null})
          .toList(),
      'aktif_sira': sira < 0 ? 0 : sira,
    };
  }

  Future<void> _saveSession() async {
    try {
      await _backend.call('oturum_kaydet', _sessionPayload());
    } catch (_) {}
  }

  /// Çıkışta oturumu (adsız sekmelerin içeriği dahil) kaydeder. Backend
  /// yanıt vermezse pencerenin kapanmasını engellememek için kısa süre
  /// beklenir.
  Future<void> saveSessionNow() =>
      _saveSession().timeout(const Duration(seconds: 3), onTimeout: () {});

  // Aynı dosyaya yapılan kayıtlar sıraya konur: komutlar backend'de paralel
  // işlendiğinden otomatik kayıt ile Ctrl+S ters sırada bitip diske ESKİ
  // içeriği yazabiliyordu.
  final Map<String, Future<void>> _saveChains = {};

  Future<void> _writeFile(String path, String content) {
    final onceki = _saveChains[path] ?? Future<void>.value();
    final yazma = onceki.then((_) =>
        _backend.call('dosya_kaydet', {'yol': path, 'icerik': content}));
    _saveChains[path] = yazma.then<void>((_) {}, onError: (_) {});
    return yazma.then<void>((_) {});
  }

  Future<void> openFile(
    String path, {
    bool makeActive = true,
    bool saveSession = true,
    BuildContext? context,
  }) async {
    final idx = _tabs.indexWhere((t) => t.path == path);

    if (idx >= 0) {
      if (makeActive) setActive(idx);
      return;
    }

    final r = await _backend.call('dosya_oku', {'yol': path});

    var name = r['isim']?.toString() ?? p.basename(path);
    final resolvedPath = r['yol']?.toString() ?? path;

    // Okuma sürerken aynı dosya (çift tıklama / iki hızlı seçim) zaten
    // açılmış olabilir: ikinci sekme açılmaz; ikisinden biri kaydedilince
    // diğerindeki değişiklikler sessizce eziliyordu.
    final simdi = _tabs.indexWhere((t) => t.path == resolvedPath || t.path == path);
    if (simdi >= 0) {
      if (makeActive) setActive(simdi);
      return;
    }

    if (_tabs.any((t) => t.name == name && t.path != resolvedPath)) {
      if (context != null && context.mounted) {
        final unique = await _confirmUniqueName(context, name);
        if (unique == null) return;
        name = unique;
      } else {
        name = suggestUniqueName(name);
      }
    }

    while (_tabs.any((t) => t.name == name)) {
      name = suggestUniqueName(name);
    }

    _tabs.add(
      EditorTab(
        path: resolvedPath,
        name: name,
        content: r['icerik']?.toString() ?? '',
      ),
    );

    if (makeActive) {
      _rememberActiveCaret();

      _active = _tabs.length - 1;
      activeContent.value = _tabs[_active].content;
      _pendingCaretOffset = _caretMemory[resolvedPath];
    }

    _revision++;
    notifyListeners();

    if (saveSession) _saveSession();
  }

  Future<void> createUntitled({
    String? name,
    String content = '',
    bool setActive = true,
    bool saveSession = true,
    BuildContext? context,
  }) async {
    String? desiredOrNull = name;
    if (desiredOrNull == null) {
      // Oturumdan geri yüklenen "Untitled-N" sekmeleri sayacı ilerletmiyordu;
      // Ctrl+T ad çakışması penceresi açıyordu.
      do {
        desiredOrNull = 'Untitled-${_untitledCounter++}.trpy';
      } while (_tabs.any((t) => t.name == desiredOrNull));
    }
    var desired = desiredOrNull;

    if (_tabs.any((t) => t.name == desired)) {
      if (context != null && context.mounted) {
        final unique = await _confirmUniqueName(context, desired);
        if (unique == null) return;
        desired = unique;
      } else {
        desired = suggestUniqueName(desired);
      }
    }

    while (_tabs.any((t) => t.name == desired)) {
      desired = suggestUniqueName(desired);
    }

    var path = 'untitled:$desired';

    while (_tabs.any((t) => t.path == path)) {
      desired = suggestUniqueName(desired);
      path = 'untitled:$desired';
    }

    _tabs.add(
      EditorTab(
        path: path,
        name: desired,
        content: content,
      ),
    );

    if (setActive) {
      _rememberActiveCaret();

      _active = _tabs.length - 1;
      activeContent.value = content;
      _pendingCaretOffset = null;
    }

    _revision++;
    notifyListeners();

    if (saveSession) _saveSession();
  }

  void openSettings() {
    final i = _tabs.indexWhere((t) => t.path == kSettingsPath);

    if (i >= 0) {
      setActive(i);
      return;
    }

    var name = 'Ayarlar';

    if (_tabs.any((t) => t.name == name)) {
      name = suggestUniqueName(name);
    }

    _tabs.add(
      EditorTab(
        path: kSettingsPath,
        name: name,
        content: '',
      ),
    );

    _rememberActiveCaret();

    _active = _tabs.length - 1;
    activeContent.value = '';
    _pendingCaretOffset = null;

    _revision++;
    notifyListeners();
    _saveSession();
  }

  void setActive(int index) {
    if (index < 0 || index >= _tabs.length || _active == index) return;

    _rememberActiveCaret();

    _active = index;
    activeContent.value = _tabs[index].content;
    _pendingCaretOffset = _caretMemory[_tabs[index].path];

    _revision++;
    notifyListeners();
    _saveSession();
  }

  /// Sekmeyi [from] konumundan [to] konumuna taşır (sürükle-bırak / kısayol).
  /// Aktif sekme aynı kalır; içerik değişmediği için `revision` artırılmaz
  /// (editör yeniden yüklenmez, katlama ve imleç korunur).
  void moveTab(int from, int to) {
    if (from < 0 || from >= _tabs.length) return;
    to = to.clamp(0, _tabs.length - 1).toInt();
    if (from == to) return;
    final activeId = activeTab?.id;
    final t = _tabs.removeAt(from);
    _tabs.insert(to, t);
    if (activeId != null) {
      _active = _tabs.indexWhere((x) => x.id == activeId);
    }
    notifyListeners();
    _saveSession();
  }

  /// Aktif sekmeyi bir adım sola (-1) / sağa (+1) taşır.
  void moveActiveTab(int delta) {
    if (_active < 0) return;
    moveTab(_active, _active + delta);
  }

  void updateContent(String val) {
    final t = activeTab;
    if (t == null || t.path == kSettingsPath || t.content == val) return;
    final old = t.content;
    t.content = val;
    activeContent.value = val;
    onContentEdited?.call(t.id, old, val);
    if (!t.dirty) {
      t.dirty = true;
      notifyListeners();
    }
  }

  void replaceActiveContent(String val) {
    final t = activeTab;
    if (t == null || t.path == kSettingsPath) return;
    final old = t.content;
    t.content = val;
    t.dirty = true;
    activeContent.value = val;
    if (old != val) onContentEdited?.call(t.id, old, val);
    _revision++;
    notifyListeners();
  }

  /// Kaydedildiyse true; kullanıcı Farklı Kaydet'i iptal ettiyse false.
  Future<bool> saveTab(int index) async {
    if (index < 0 || index >= _tabs.length) return false;
    final t = _tabs[index];
    if (t.path == kSettingsPath) return false;
    if (t.path.startsWith('untitled:')) {
      return saveAsTab(index);
    }
    // Kayıt sürerken yazılanlar "kaydedildi" sayılmamalı: kirli bayrağı ancak
    // içerik, gönderilen içerikle hâlâ aynıysa temizlenir.
    final snap = t.content;
    await _writeFile(t.path, snap);
    if (t.content == snap) t.dirty = false;
    notifyListeners();
    return true;
  }

  Future<bool> saveActive() async {
    if (_active >= 0) return saveTab(_active);
    return false;
  }

  Future<bool> saveAsTab(int index, {BuildContext? context}) async {
    if (index < 0 || index >= _tabs.length) return false;

    final t = _tabs[index];
    if (t.path == kSettingsPath) return false;

    final path = await FilePicker.platform.saveFile(fileName: t.name);
    if (path == null || path.isEmpty) return false;

    var name = p.basename(path);

    if (_tabs.any((x) => x.id != t.id && x.path != path && x.name == name)) {
      if (context != null && context.mounted) {
        final unique = await _confirmUniqueName(context, name);
        if (unique == null) return false;
        name = unique;
      } else {
        name = suggestUniqueName(name);
      }
    }

    while (_tabs.any((x) => x.id != t.id && x.path != path && x.name == name)) {
      name = suggestUniqueName(name);
    }

    final snap = t.content;
    await _writeFile(path, snap);

    // Dosya penceresi / kayıt beklenirken sekmeler taşınmış ya da kapanmış
    // olabilir: eskiden eski indeksle BAŞKA bir sekmenin üzerine yazılıyor
    // ya da RangeError oluşuyordu. Sekme kimliğiyle yeniden bulunur.
    index = _tabs.indexWhere((x) => x.id == t.id);
    if (index < 0) return true;
    final guncel = _tabs[index];

    final oldPath = guncel.path;

    _tabs[index] = EditorTab(
      id: t.id,
      path: path,
      name: name,
      content: guncel.content,
      dirty: guncel.content != snap,
    );

    if (_caretMemory.containsKey(oldPath)) {
      _caretMemory[path] = _caretMemory.remove(oldPath)!;
    }

    if (_active == index) {
      activeContent.value = guncel.content;
      _pendingCaretOffset = _caretMemory[path];
    }

    notifyListeners();
    _saveSession();
    return true;
  }

  Future<bool> saveAsActive({BuildContext? context}) async {
    if (_active >= 0) return saveAsTab(_active, context: context);
    return false;
  }

  Future<void> closeTab(int index) async {
    if (index < 0 || index >= _tabs.length) return;

    _rememberActiveCaret();

    final wasActive = index == _active;

    _tabs.removeAt(index);

    if (_tabs.isEmpty) {
      _active = -1;
      activeContent.value = '';
      _pendingCaretOffset = null;
    } else if (_active > index) {
      _active--;
      activeContent.value = _tabs[_active].content;
      _pendingCaretOffset = _caretMemory[_tabs[_active].path];
    } else if (wasActive) {
      _active = index.clamp(0, _tabs.length - 1);
      activeContent.value = _tabs[_active].content;
      _pendingCaretOffset = _caretMemory[_tabs[_active].path];
    } else {
      if (_active >= 0) {
        activeContent.value = _tabs[_active].content;
        _pendingCaretOffset = _caretMemory[_tabs[_active].path];
      }
    }

    _revision++;
    notifyListeners();
    _saveSession();
  }

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
        final snap = t.content;
        await _writeFile(t.path, snap);
        if (t.content == snap) t.dirty = false;
      }
      await _backend.call('oturum_kaydet', _sessionPayload());
      notifyListeners();
      return true;
    } catch (_) {
      return false;
    }
  }


  void autoSave() {
    final t = activeTab;
    if (t == null || !t.dirty) return;
    if (t.path.startsWith('untitled:') || t.path == kSettingsPath) return;
    final snap = t.content;
    _writeFile(t.path, snap).then((_) {
      // Kayıt sürerken yazılan tuşlar "kaydedildi" sayılmasın.
      if (t.content == snap) t.dirty = false;
      notifyListeners();
    }).catchError((_) {});
  }

  @override
  void dispose() {
    activeContent.dispose();
    super.dispose();
  }
}

class FileTreeProvider extends ChangeNotifier {
  final BackendService _backend;
  FileNode? _root;
  bool _loading = false;
  String? errorMessage;
  FileTreeProvider(this._backend) {
    _init();
  }
  FileNode? get root => _root;
  bool get loading => _loading;
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      await loadInitial();
    } catch (_) {}
  }

  Future<void> loadInitial() async {
    if (_root != null) return;
    try {
      final r =
          await _backend.call('ayar_get', {'anahtar': 'son_proje_dizini'});
      final d = r['deger']?.toString();
      if (d != null && d.isNotEmpty) await load(d);
    } catch (_) {}
  }

  List<FileNode> _parse(dynamic items) {
    final res = <FileNode>[];
    if (items is! List) return res;
    for (final i in items) {
      if (i is! Map) continue;
      final m = Map<String, dynamic>.from(i);
      final name = m['ad']?.toString() ?? '';
      final path = m['yol']?.toString() ?? '';
      if (name.isEmpty || path.isEmpty) continue;
      res.add(FileNode(name: name, path: path, isDir: m['tip'] == 'directory'));
    }
    return res;
  }

  Future<void> load(String? dir) async {
    if (dir == null || dir.isEmpty) return;
    _loading = true;
    errorMessage = null;
    notifyListeners();
    try {
      final r = await _backend.call('dosya_agaci', {'dizin': dir});
      _root = FileNode(
        name: r['dizin']?.toString() ?? dir,
        path: r['dizin']?.toString() ?? dir,
        isDir: true,
        expanded: true,
        loaded: true,
        children: _parse(r['ogeler']),
      );
    } catch (e) {
      _root = null;
      errorMessage = e.toString();
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> setProjectDirectory(String dir) async {
    await _backend.call('proje_dizini_set', {'dizin': dir});
    await load(dir);
  }

  // Yüklenmekte olan klasörler: hızlı çift tıklamada iki istek de "kapalı ve
  // yüklenmemiş" görüp ikisi birden durumu çevirince klasör kapalı kalıyordu.
  final Set<String> _yuklenenKlasorler = {};

  Future<void> toggleExpand(FileNode node) async {
    if (!node.isDir) return;
    if (!node.expanded && !node.loaded) {
      if (!_yuklenenKlasorler.add(node.path)) return;
      try {
        final r = await _backend.call('dosya_agaci', {'dizin': node.path});
        node.children = _parse(r['ogeler']);
        node.loaded = true;
      } catch (_) {
        node.children = [];
        node.loaded = true;
      } finally {
        _yuklenenKlasorler.remove(node.path);
      }
      node.expanded = true;
      notifyListeners();
      return;
    }
    node.expanded = !node.expanded;
    notifyListeners();
  }

  Future<void> refresh() async {
    if (_root != null) {
      final path = _root!.path;
      _root = null;
      notifyListeners();
      await load(path);
    } else {
      await loadInitial();
    }
  }
}

class TerminalProvider extends ChangeNotifier {
  final BackendService _backend;
  late final StreamSubscription<BackendEvent> _sub;
  final StringBuffer _output = StringBuffer();
  bool _running = false;
  String? _outputCache;
  Timer? _notifyTimer;
  // Yoğun çıktıda (ör. döngü içinde yazdır) her parça için ayrı rebuild
  // yapmak yerine bildirimler ~1 kareye (16 ms) toplanır.
  static const Duration _notifyDelay = Duration(milliseconds: 16);
  String get output => _outputCache ??= _output.toString();
  bool get isRunning => _running;
  late final StreamSubscription<bool> _connSub;
  TerminalProvider(this._backend) {
    _sub = _backend.events.listen(_onEvent);
    // Backend bağlantısı koparsa (çökme, yeniden başlatma) çalışan program da
    // onunla birlikte kapanmıştır; "calistirma_bitti" hiç gelmeyeceğinden
    // terminal "çalışıyor" durumunda takılı kalmasın.
    _connSub = _backend.connectionStream.listen((bagli) {
      if (!bagli && _running) {
        _running = false;
        _append('\n[Backend bağlantısı koptu; program sonlandırıldı]\n');
        notifyListeners();
      }
    });
  }
  // Eski backend sürümlerinin yazdığı teknik satırlar ("> python -u
  // runner.py", "[Process 0 koduyla çıktı]") kullanıcıya gösterilmez.
  static final RegExp _teknikSatir = RegExp(
    r'^> *python[^\n]*runner\.py[^\n]*(\n|$)|^\[Process -?\d+ koduyla çıktı\][^\n]*(\n|$)',
    multiLine: true,
  );

  static String _filtrele(String metin) =>
      metin.contains('runner.py') || metin.contains('[Process ')
          ? metin.replaceAll(_teknikSatir, '')
          : metin;

  void _onEvent(BackendEvent e) {
    if (e.name == 'calistirma_cikti') {
      _append(_filtrele(e.data['metin']?.toString() ?? ''));
      _scheduleNotify();
    } else if (e.name == 'calistirma_bitti') {
      _running = false;
      // Normal bitişte ek satır yazılmaz (bitiş, dönen göstergenin
      // kaybolmasından anlaşılır); yalnızca hatalı çıkış kodu bildirilir.
      final kod = e.data['cikis_kodu'];
      final kodSayi = kod is num ? kod.toInt() : int.tryParse('$kod');
      if (kodSayi != null && kodSayi != 0) {
        _append('\n[Program $kodSayi koduyla sonlandı]\n');
      }
      notifyListeners();
    } else if (e.name == 'terminal_cikti') {
      _append(e.data['metin']?.toString() ?? '');
      _scheduleNotify();
    }
  }

  void _scheduleNotify() {
    if (_notifyTimer?.isActive ?? false) return;
    _notifyTimer = Timer(_notifyDelay, notifyListeners);
  }

  @override
  void notifyListeners() {
    _notifyTimer?.cancel();
    super.notifyListeners();
  }

  void _append(String s) {
    _outputCache = null;
    _output.write(s);
    if (_output.length > kMaxTermChars) {
      final keep = _output.toString().substring(_output.length - kMaxTermChars);
      _output
        ..clear()
        ..write('[... kesildi ...]\n')
        ..write(keep);
    }
  }

  Future<void> run(String kod) async {
    _output.clear();
    _outputCache = null;
    _running = true;
    notifyListeners();
    try {
      await _backend.call('calistir', {'kod': kod});
    } on BackendException catch (e) {
      _running = false;
      _append('[Hata] ${e.message}\n');
    } catch (e) {
      _running = false;
      _append('[Hata] $e\n');
    } finally {
      notifyListeners();
    }
  }

  /// Backend'de başka bir yoldan (ör. hata ayıklayıcı) başlatılan bir
  /// programın çıktısı için terminali hazırlar.
  void beginRun() {
    _output.clear();
    _outputCache = null;
    _running = true;
    notifyListeners();
  }

  /// [beginRun] sonrası program hiç başlatılamadıysa.
  void endRun([String? message]) {
    _running = false;
    if (message != null) _append('$message\n');
    notifyListeners();
  }

  Future<void> stop() async {
    try {
      await _backend.call('calistir_durdur');
      _append('[Durduruldu]\n');
    } catch (_) {
      // Backend'e ulaşılamıyorsa program da onunla birlikte kapanmıştır.
      if (!_backend.isConnected) _running = false;
    }
    notifyListeners();
  }

  Future<void> sendCommand(String cmd) async {
    // Program çalışırken boş satır geçerli bir girdidir; kabuk komutu boş
    // olamaz.
    if (!_running && cmd.trim().isEmpty) return;
    // Çalışan programa girdi gönderiliyorsa konsoldaki gibi yalnızca yazılan
    // metin görünür; kabuk komutunda "> komut" biçiminde yazılır.
    _append(_running ? '$cmd\n' : '> $cmd\n');
    notifyListeners();
    try {
      await _backend.call('terminal_komut', {'komut': cmd});
    } catch (e) {
      _append('[Hata] $e\n');
    }
    notifyListeners();
  }

  void clear() {
    _output.clear();
    _outputCache = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _notifyTimer?.cancel();
    _sub.cancel();
    _connSub.cancel();
    super.dispose();
  }
}

class AiProvider extends ChangeNotifier {
  final BackendService _backend;
  final List<AiMessage> _messages = [];
  bool _loading = false;
  AiProvider(this._backend);
  List<AiMessage> get messages => List.unmodifiable(_messages);
  bool get loading => _loading;
  List<AiPart> _parseParts(Map<String, dynamic> r) {
    final parts = <AiPart>[];
    if (r['parcalar'] is List) {
      for (var i in r['parcalar'] as List) {
        if (i is Map) {
          final m = Map<String, dynamic>.from(i);
          parts.add(AiPart(
            type: m['tip']?.toString() ?? 'metin',
            content: m['icerik']?.toString() ?? '',
            language: m['dil']?.toString(),
          ));
        }
      }
    }
    if (parts.isEmpty && r['cevap'] != null) {
      parts.add(AiPart(type: 'metin', content: r['cevap'].toString()));
    }
    return parts;
  }

  Future<void> ask(String msg, {String? kod}) async {
    if (msg.trim().isEmpty || _loading) return;
    _messages.add(AiMessage(
        role: AiRole.user, parts: [AiPart(type: 'metin', content: msg)]));
    _loading = true;
    notifyListeners();
    try {
      final r = await _backend
          .call('ai_sor', {'mesaj': msg, if (kod != null) 'kod': kod});
      _messages.add(AiMessage(role: AiRole.assistant, parts: _parseParts(r)));
    } catch (e) {
      _messages.add(AiMessage(
          role: AiRole.assistant,
          parts: [AiPart(type: 'metin', content: 'Hata: $e')]));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> explain(String kod) async {
    if (_loading || kod.trim().isEmpty) return;
    _loading = true;
    notifyListeners();
    try {
      final r = await _backend.call('ai_kodu_acikla', {'kod': kod});
      _messages.add(AiMessage(role: AiRole.assistant, parts: _parseParts(r)));
    } catch (e) {
      _messages.add(AiMessage(
          role: AiRole.assistant,
          parts: [AiPart(type: 'metin', content: 'Hata: $e')]));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> optimize(String kod) async {
    if (_loading || kod.trim().isEmpty) return;
    _loading = true;
    notifyListeners();
    try {
      final r = await _backend.call('ai_kodu_optimize', {'kod': kod});
      _messages.add(AiMessage(role: AiRole.assistant, parts: _parseParts(r)));
    } catch (e) {
      _messages.add(AiMessage(
          role: AiRole.assistant,
          parts: [AiPart(type: 'metin', content: 'Hata: $e')]));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> clear() async {
    try {
      await _backend.call('ai_temizle');
    } catch (_) {}
    _messages.clear();
    _loading = false;
    notifyListeners();
  }
}

/// Hata ayıklayıcıda bir değişken (yerel / küresel) ve varsa alt elemanları.
class DebugVar {
  final String name;
  final String type;
  final String value;
  final int? length;
  final List<DebugVar> children;
  const DebugVar({
    required this.name,
    required this.type,
    required this.value,
    this.length,
    this.children = const [],
  });

  static List<DebugVar> listFrom(Object? raw) {
    if (raw is! List) return const [];
    return [
      for (final e in raw)
        if (e is Map)
          DebugVar(
            name: e['ad']?.toString() ?? '?',
            type: e['tip']?.toString() ?? '',
            value: e['deger']?.toString() ?? '',
            length: e['uzunluk'] is num ? (e['uzunluk'] as num).toInt() : null,
            children: listFrom(e['cocuklar']),
          ),
    ];
  }
}

class DebugFrame {
  final String function;
  final int line;
  const DebugFrame(this.function, this.line);
}

/// Breakpoint'ler ve gerçek (adım adım) hata ayıklama oturumu.
///
/// Eski sürümdeki hatalar ve düzeltmeleri:
/// * Breakpoint'ler TEK bir genel kümede tutuluyordu; bir dosyada konan
///   breakpoint bütün sekmelerde aynı satırlarda görünüyordu. Artık her
///   sekmenin kendi kümesi var.
/// * Satır eklenip silindiğinde breakpoint'ler yerinde kalıp yanlış satırlara
///   kayıyordu; artık düzenlemeyle birlikte kaydırılıyor.
/// * "Debug Başlat" kodu hiç çalıştırmıyordu, "Adım" yalnızca bir sonraki
///   breakpoint'e atlıyordu. Artık kod gerçekten çalıştırılıyor; adım at /
///   içine gir / dışına çık / duraklat / devam / durdur ve değişkenler gerçek.
class BreakpointProvider extends ChangeNotifier {
  final BackendService _backend;
  final EditorProvider? _editor;
  late final StreamSubscription<BackendEvent> _sub;
  final Map<String, Set<int>> _bps = {};

  bool _debugging = false;
  bool _paused = false;
  bool _starting = false;
  String? _debugTabId;
  String? _sessionId;
  int _currentLine = 0;
  String stopReason = '';
  String currentFunction = '';
  List<DebugVar> locals = const [];
  List<DebugVar> globals = const [];
  List<DebugFrame> stack = const [];
  String? lastError;
  String? notice;

  late final StreamSubscription<bool> _connSub;

  BreakpointProvider(this._backend, [this._editor]) {
    _sub = _backend.events.listen(_onEvent);
    _editor?.onContentEdited = adjustForEdit;
    // Backend bağlantısı koparsa oturum da bitmiştir (süreç backend'in
    // alt sürecidir); arayüz "hata ayıklanıyor" durumunda takılı kalmasın.
    _connSub = _backend.connectionStream.listen((bagli) {
      if (!bagli && _debugging) {
        _endSession();
        notice = 'Backend bağlantısı koptu; hata ayıklama sonlandırıldı.';
        notifyListeners();
      }
    });
  }

  bool get debugging => _debugging;
  bool get paused => _debugging && _paused;
  bool get starting => _starting;
  String? get debugTabId => _debugTabId;
  int get currentLine => _currentLine;

  /// Geriye dönük uyumluluk: aktif sekmenin breakpoint'leri.
  Set<int> get breakpoints => breakpointsFor(_editor?.activeTab?.id);

  Set<int> breakpointsFor(String? tabId) =>
      tabId == null ? const {} : Set.unmodifiable(_bps[tabId] ?? const {});

  /// Bu sekmede şu an durulan satır (yoksa null).
  int? pausedLineFor(String? tabId) =>
      paused && tabId != null && tabId == _debugTabId && _currentLine > 0
          ? _currentLine
          : null;

  void clearNotice() {
    if (notice != null) {
      notice = null;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------- breakpoint
  void toggle(String? tabId, int line) {
    if (tabId == null || line < 1) return;
    final set = _bps.putIfAbsent(tabId, () => <int>{});
    if (!set.remove(line)) set.add(line);
    _syncSession(tabId);
    notifyListeners();
  }

  void clearAll([String? tabId]) {
    if (tabId == null) {
      _bps.clear();
    } else {
      _bps.remove(tabId);
    }
    if (_debugTabId != null) _syncSession(_debugTabId!);
    notifyListeners();
  }

  void forgetTab(String tabId) {
    _bps.remove(tabId);
  }

  /// Çalışan oturum bu sekmeye aitse breakpoint değişikliğini hemen iletir
  /// (program yeniden başlatılmadan breakpoint eklenip kaldırılabilir).
  void _syncSession(String tabId) {
    if (!_debugging || tabId != _debugTabId) return;
    final lines = (_bps[tabId] ?? const <int>{}).toList()..sort();
    _backend
        .call('debug_breakpoint_ayarla', {'satirlar': lines})
        .catchError((_) => <String, dynamic>{});
  }

  /// Metin düzenlemesinde satır eklenip silindiyse breakpoint'leri kaydırır.
  /// Değişen bölge, eski ve yeni metnin ortak başı / sonu çıkarılarak bulunur.
  void adjustForEdit(String tabId, String oldText, String newText) {
    final set = _bps[tabId];
    if (set == null || set.isEmpty) return;
    final oldLines = '\n'.allMatches(oldText).length;
    final newLines = '\n'.allMatches(newText).length;
    final delta = newLines - oldLines;
    if (delta == 0) return;

    final minLen = math.min(oldText.length, newText.length);
    var prefix = 0;
    while (prefix < minLen &&
        oldText.codeUnitAt(prefix) == newText.codeUnitAt(prefix)) {
      prefix++;
    }
    var suffix = 0;
    while (suffix < minLen - prefix &&
        oldText.codeUnitAt(oldText.length - 1 - suffix) ==
            newText.codeUnitAt(newText.length - 1 - suffix)) {
      suffix++;
    }
    // Değişikliğin başladığı satır (1 tabanlı) ve eski metinde kapladığı son
    // satır.
    final startLine = '\n'.allMatches(oldText.substring(0, prefix)).length + 1;
    final oldEndLine = '\n'
            .allMatches(oldText.substring(0, oldText.length - suffix))
            .length +
        1;
    // Satır başında yapılan ekleme (ör. satırın üstüne Enter) o satırın
    // breakpoint'ini aşağı taşır; satır ortasındaki bölme taşımaz.
    final atLineStart = prefix == 0 || oldText.codeUnitAt(prefix - 1) == 0x0A;

    final updated = <int>{};
    for (final b in set) {
      if (b < startLine || (b == startLine && !atLineStart)) {
        updated.add(b);
      } else if (delta < 0 && b > startLine && b <= oldEndLine) {
        // Silinen satırlardaki breakpoint, birleşilen satıra taşınır.
        updated.add(startLine);
      } else {
        final n = b + delta;
        if (n >= 1 && n <= newLines + 1) updated.add(n);
      }
    }
    set
      ..clear()
      ..addAll(updated);
    _syncSession(tabId);
    notifyListeners();
  }

  // ----------------------------------------------------------------- oturum
  void _onEvent(BackendEvent e) {
    switch (e.name) {
      case 'debug_durdu':
        if (!_debugging) return;
        _paused = true;
        _currentLine = (e.data['satir'] as num?)?.toInt() ?? 0;
        stopReason = e.data['neden']?.toString() ?? '';
        currentFunction = e.data['fonksiyon']?.toString() ?? '';
        locals = DebugVar.listFrom(e.data['yerel']);
        globals = DebugVar.listFrom(e.data['kuresel']);
        stack = [
          for (final f in (e.data['yigin'] as List? ?? const []))
            if (f is Map)
              DebugFrame(f['fonksiyon']?.toString() ?? '?',
                  (f['satir'] as num?)?.toInt() ?? 0),
        ];
        _revealCurrentLine();
        notifyListeners();
        break;
      case 'debug_devam':
        if (!_debugging) return;
        _paused = false;
        notifyListeners();
        break;
      case 'debug_breakpointler':
        // Boş / yorum satırına konan breakpoint, çalıştırılabilir ilk satıra
        // kaydırılır; arayüzdeki nokta da gerçek yerine taşınır.
        final tabId = _debugTabId;
        final map = e.data['eslesme'];
        if (tabId == null || map is! Map) return;
        final set = _bps[tabId];
        if (set == null) return;
        var changed = false;
        map.forEach((k, v) {
          final from = int.tryParse('$k');
          final to = v is num ? v.toInt() : int.tryParse('$v');
          if (from != null && to != null && from != to && set.remove(from)) {
            set.add(to);
            changed = true;
          }
        });
        if (changed) notifyListeners();
        break;
      case 'debug_hata':
        final satir = e.data['satir'];
        lastError = 'Satır $satir: ${e.data['mesaj'] ?? 'Hata'}';
        notice = lastError;
        notifyListeners();
        break;
      case 'debug_bitti':
        if (!_debugging) return;
        if (_starting) {
          // Oturum, debug_baslat yanıtı gelmeden bitmiş olabilir (ör. hiç
          // çağrılmayan bir fonksiyondaki breakpoint). Olay saklanır; yanıt
          // gelince oturum kimliği eşleşirse uygulanır. Eskiden atılıyor ve
          // arayüz sonsuza dek "hata ayıklanıyor" durumunda kalıyordu.
          _bekleyenBitti = e.data;
          return;
        }
        _bittiUygula(e.data);
        break;
    }
  }

  Map<String, dynamic>? _bekleyenBitti;

  void _bittiUygula(Map<String, dynamic> data) {
    // Yeniden başlatmada öldürülen ESKİ oturumun bitiş olayı yeni oturumu
    // kapatmamalı.
    final id = data['oturum']?.toString();
    if (id != null && _sessionId != null && id != _sessionId) return;
    final kod = data['cikis_kodu'];
    _endSession();
    notice ??= kod == 0 || kod == null
        ? 'Hata ayıklama tamamlandı.'
        : 'Hata ayıklama sona erdi (çıkış kodu $kod).';
    notifyListeners();
  }

  void _endSession() {
    _debugging = false;
    _paused = false;
    _currentLine = 0;
    stopReason = '';
    currentFunction = '';
    locals = const [];
    globals = const [];
    stack = const [];
  }

  /// Durulan satırı editörde gösterir; gerekirse hata ayıklanan sekmeye geçer.
  void _revealCurrentLine() {
    final ed = _editor;
    final tabId = _debugTabId;
    if (ed == null || tabId == null || _currentLine < 1) return;
    final line = _currentLine;
    void jump() {
      if (ed.activeTab?.id != tabId) return;
      final reveal = ed.revealModelLine;
      if (reveal != null) {
        reveal(line);
        return;
      }
      final c = ed.uiController;
      if (c != null) jumpToLineIn(c, line);
    }

    if (ed.activeTab?.id != tabId) {
      final idx = ed.tabs.indexWhere((t) => t.id == tabId);
      if (idx < 0) return;
      ed.setActive(idx);
      // Sekme değişince editör içeriği bir sonraki karede yüklenir.
      WidgetsBinding.instance.addPostFrameCallback(
          (_) => WidgetsBinding.instance.addPostFrameCallback((_) => jump()));
      WidgetsBinding.instance.ensureVisualUpdate();
    } else {
      jump();
    }
  }

  Future<void> start({
    required String? tabId,
    required String kod,
    bool stepIn = false,
  }) async {
    if (tabId == null) return;
    if (kod.trim().isEmpty) {
      notice = 'Kod boş';
      notifyListeners();
      return;
    }
    if (_starting) return;
    _starting = true;
    lastError = null;
    // Önceki oturum varsa onun bitiş olayı yeni oturumu kapatmasın.
    _endSession();
    _debugTabId = tabId;
    _debugging = true;
    notifyListeners();
    _bekleyenBitti = null;
    try {
      final lines = (_bps[tabId] ?? const <int>{}).toList()..sort();
      _sessionId = null;
      final r = await _backend.call('debug_baslat', {
        'kod': kod,
        'breakpointler': lines,
        'ilk_satirda_dur': stepIn,
      });
      _sessionId = r['oturum']?.toString();
      notice = r['ilk_satirda_dur'] == true && lines.isEmpty
          ? 'Breakpoint yok: program ilk satırda duraklatıldı (F10 ile adım atın).'
          : 'Hata ayıklayıcı başladı.';
      final bekleyen = _bekleyenBitti;
      _bekleyenBitti = null;
      if (bekleyen != null &&
          bekleyen['oturum']?.toString() == _sessionId &&
          _sessionId != null) {
        notice = null;
        _bittiUygula(bekleyen);
      }
    } on BackendException catch (e) {
      _endSession();
      notice = e.message;
    } catch (e) {
      _endSession();
      notice = e.toString();
    } finally {
      _starting = false;
      notifyListeners();
    }
  }

  Future<void> _command(String command) async {
    if (!_debugging) return;
    try {
      await _backend.call(command);
    } on BackendException catch (e) {
      notice = e.message;
    } catch (e) {
      notice = e.toString();
    }
    notifyListeners();
  }

  Future<void> continueRun() => _command('debug_devam');
  Future<void> step() => _command('debug_adim');
  Future<void> stepInto() => _command('debug_icine');
  Future<void> stepOut() => _command('debug_disina');
  Future<void> pause() => _command('debug_duraklat');

  Future<void> stop() async {
    if (!_debugging) return;
    try {
      await _backend.call('debug_durdur');
    } catch (_) {}
    _endSession();
    notice = 'Hata ayıklama durduruldu.';
    notifyListeners();
  }

  @override
  void dispose() {
    _sub.cancel();
    _connSub.cancel();
    if (_editor?.onContentEdited == adjustForEdit) {
      _editor?.onContentEdited = null;
    }
    super.dispose();
  }
}

class FixProvider extends ChangeNotifier {
  final BackendService _backend;
  late final StreamSubscription<BackendEvent> _sub;
  bool fixing = false;
  String progress = '';

  /// Motorun canlı "düşünce akışı" (ilerleme mesajları).
  final List<String> thoughts = [];
  String? lastError;
  String? infoMessage;
  FixResult? pending;
  FixProvider(this._backend) {
    _sub = _backend.events.listen((e) {
      if (e.name == 'duzelt_progress') {
        progress = e.data['metin']?.toString() ?? '';
        if (fixing && progress.isNotEmpty) thoughts.add(progress);
        notifyListeners();
      }
    });
  }
  /// [calistirmaIzni]: true = kod (riskli olsa da) denenmek için çalıştırılabilir,
  /// false = hiç çalıştırılmaz, null = backend yalnızca risksiz kodu çalıştırır.
  Future<void> runFix(String kod, {bool? calistirmaIzni}) async {
    if (fixing) return;
    fixing = true;
    progress = 'Başlatıldı...';
    thoughts.clear();
    lastError = null;
    infoMessage = null;
    pending = null;
    notifyListeners();
    try {
      final r = await _backend.call('duzelt', {
        'kod': kod,
        if (calistirmaIzni != null) 'calistirma_izni': calistirmaIzni,
      });
      final code = r['kod']?.toString() ?? kod;
      final report = FixReport.fromJson(r['rapor']);
      final verification = r['dogrulama']?.toString() ?? '';
      // Değişiklik listesine son durum ve doğrulama satırları da eklenir.
      final changes = <String>[
        ...(r['degisiklikler'] as List? ?? []).map((e) => e.toString()),
        for (final k in ['son_mesaj', 'dogrulama'])
          if ((r[k]?.toString() ?? '').trim().isNotEmpty) r[k].toString(),
      ];
      final codeChanged =
          code.replaceAll('\r\n', '\n') != kod.replaceAll('\r\n', '\n');
      if (codeChanged || (report != null && report.warnings.isNotEmpty)) {
        // Kod değişmese bile öneri/uyarı varsa rapor penceresi gösterilir.
        pending = FixResult(
          code: code,
          diff: r['diff']?.toString() ?? '',
          changes: changes,
          report: report,
          verification: verification,
          codeChanged: codeChanged,
        );
      } else if (report != null) {
        infoMessage = report.summary;
      } else if (changes.isNotEmpty) {
        infoMessage = changes.join('\n');
      } else {
        infoMessage = r['mesaj']?.toString() ?? 'Değişiklik yok.';
      }
    } on BackendException catch (e) {
      lastError = e.message;
    } catch (e) {
      lastError = e.toString();
    } finally {
      fixing = false;
      progress = '';
      notifyListeners();
    }
  }

  void clearPending() {
    pending = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
}

// ============================================================================
// MERKEZİ KOMUT KAYIT YAPISI
// ============================================================================

class AppAction {
  final String id;
  final String label;
  final String? menu;
  final String shortcut;
  final SingleActivator? activator;
  final IconData? icon;
  final void Function(BuildContext) run;
  const AppAction({
    required this.id,
    required this.label,
    this.menu,
    this.shortcut = '',
    this.activator,
    this.icon,
    required this.run,
  });
}

void _runSave(BuildContext context) {
  final ed = context.read<EditorProvider>();
  ed.saveActive().then((kaydedildi) {
    // Farklı Kaydet penceresi iptal edildiyse "Kaydedildi" gösterilmez.
    if (kaydedildi && context.mounted) {
      showAppSnackbar(context, 'Kaydedildi', kind: SnackKind.success);
    }
  }).catchError((e) {
    if (context.mounted) {
      showAppSnackbar(context, 'Kaydetme hatası: $e', kind: SnackKind.error);
    }
  });
}

void _runRun(BuildContext context) {
  final k = context.read<EditorProvider>().activeContent.value;
  if (k.isEmpty) {
    showAppSnackbar(context, 'Kod boş', kind: SnackKind.error);
    return;
  }
  // Terminali açar ve klavye odağını komut satırına taşır; böylece program
  // girdi beklediğinde kullanıcı doğrudan yazabilir.
  context.read<UiProvider>().focusTerminal();
  context.read<TerminalProvider>().run(k);
}

/// Bul / Değiştir'i açar ve odağı arama kutusuna verir. Editörde tek satırlık
/// bir seçim varsa arama kutusuna önceden doldurulur (VS Code davranışı).
void _runFind(BuildContext context, bool replace) {
  String? seed;
  final c = context.read<EditorProvider>().uiController;
  if (c != null) {
    final sel = c.selection;
    if (sel.isValid && !sel.isCollapsed && sel.end <= c.text.length) {
      final s = c.text.substring(sel.start, sel.end);
      if (!s.contains('\n')) seed = s;
    }
  }
  context.read<UiProvider>().openFind(replace, seed: seed);
}

Future<void> openFilePicker(BuildContext context) async {
  final r = await FilePicker.platform.pickFiles(type: FileType.any);

  if (r != null && r.files.isNotEmpty && r.files.first.path != null) {
    try {
      await context.read<EditorProvider>().openFile(
            r.files.first.path!,
            context: context,
          );
    } catch (e) {
      if (context.mounted) {
        showAppSnackbar(context, 'Hata: $e', kind: SnackKind.error);
      }
    }
  }
}

Future<void> _runFix(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final fix = context.read<FixProvider>();
  final kod = ed.activeContent.value;
  if (kod.isEmpty) {
    showAppSnackbar(context, 'Kod boş', kind: SnackKind.error);
    return;
  }
  if (fix.fixing) return;
  // Akıllı Düzeltme kodu denemek için çalıştırır. Kod dosya silme, ağ erişimi,
  // başka program çalıştırma gibi riskli işler içeriyorsa önce kullanıcıya sorulur.
  bool? calistirmaIzni;
  List<String> riskler = const [];
  try {
    final r = await context
        .read<BackendService>()
        .call('duzelt_riskleri', {'kod': kod});
    riskler = (r['riskler'] as List? ?? []).map((e) => e.toString()).toList();
  } catch (_) {
    // Risk analizi yapılamadıysa backend varsayılanı (yalnızca risksiz kodu
    // çalıştırma) geçerlidir.
  }
  if (!context.mounted) return;
  if (riskler.isNotEmpty) {
    final secim = await showDialog<String>(
      context: context,
      builder: (dc) => _FixRiskDialog(riskler: riskler),
    );
    if (!context.mounted || secim == null) return;
    calistirmaIzni = secim == 'calistir';
  }
  final fixFuture = fix.runFix(kod, calistirmaIzni: calistirmaIzni);
  // Pencerenin kendi rotası kapatılır; araya başka bir pencere (ör. komut
  // paleti) girerse eskiden yanlış pencere kapanıyordu.
  Route<dynamic>? ilerlemeRotasi;
  unawaited(showDialog(
    context: context,
    barrierDismissible: false,
    builder: (dc) {
      ilerlemeRotasi ??= ModalRoute.of(dc);
      return const _FixThinkingDialog();
    },
  ));
  await fixFuture;
  if (!context.mounted) return;
  final rota = ilerlemeRotasi;
  if (rota != null && rota.isActive && rota.navigator != null) {
    rota.navigator!.removeRoute(rota);
  } else if (rota == null) {
    Navigator.of(context, rootNavigator: true).pop();
  }
  if (fix.pending != null) {
    final result = fix.pending!;
    final choice = await showDialog<String>(
      context: context,
      builder: (dc) => _FixResultDialog(result: result),
    );
    if (!context.mounted) return;
    if (choice == 'apply') {
      ed.replaceActiveContent(result.code);
      fix.clearPending();
      showAppSnackbar(context, 'Düzeltmeler uygulandı', kind: SnackKind.success);
    } else if (choice == 'tab') {
      ed.createUntitled(
        name: 'duzeltilmis.trpy',
        content: result.code,
        context: context,
      );
      fix.clearPending();
      showAppSnackbar(context, 'Düzeltilmiş kod yeni sekmede açıldı',
          kind: SnackKind.success);
    } else if (choice != null && choice.startsWith('goto:')) {
      fix.clearPending();
      final line = int.tryParse(choice.substring(5));
      if (line != null) ed.revealModelLine?.call(line);
    } else {
      fix.clearPending();
    }
  } else if (fix.lastError != null) {
    showAppSnackbar(context, fix.lastError!, kind: SnackKind.error);
  } else if (fix.infoMessage != null) {
    showAppSnackbar(context, fix.infoMessage!, kind: SnackKind.success);
  }
}

/// Riskli kod için Akıllı Düzeltme öncesi onay: 'statik' (çalıştırmadan),
/// 'calistir' (çalıştırarak) ya da null (vazgeç).
class _FixRiskDialog extends StatelessWidget {
  final List<String> riskler;
  const _FixRiskDialog({required this.riskler});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: Row(children: [
        Icon(Icons.warning_amber_rounded, color: theme.colorScheme.error),
        const SizedBox(width: 10),
        const Expanded(child: Text('Kod çalıştırılsın mı?')),
      ]),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Akıllı Düzeltme, hataları bulmak için kodu birkaç kez '
                'çalıştırır. Bu kod şunları içeriyor:'),
            const SizedBox(height: 8),
            for (final r in riskler)
              Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text('• $r'),
              ),
            const SizedBox(height: 12),
            const Text('Çalıştırmadan düzeltme yalnızca yazım ve sözdizimi '
                'hatalarını düzeltir; çalışma sırasında ortaya çıkan hatalar '
                'bulunmaz.'),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Vazgeç'),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop('calistir'),
          child: const Text('Çalıştırarak düzelt'),
        ),
        FilledButton(
          autofocus: true,
          onPressed: () => Navigator.of(context).pop('statik'),
          child: const Text('Çalıştırmadan düzelt'),
        ),
      ],
    );
  }
}

/// Düzeltme sürerken motorun "düşünce akışını" canlı gösterir.
class _FixThinkingDialog extends StatelessWidget {
  const _FixThinkingDialog();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: Row(children: [
        Icon(Icons.auto_fix_high, color: theme.colorScheme.primary),
        const SizedBox(width: 10),
        const Text('Akıllı Düzeltme'),
      ]),
      content: SizedBox(
        width: 460,
        child: Consumer<FixProvider>(builder: (_, p, __) {
          final son = p.thoughts.length > 9
              ? p.thoughts.sublist(p.thoughts.length - 9)
              : p.thoughts;
          return Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const LinearProgressIndicator(),
              const SizedBox(height: 12),
              if (son.isEmpty)
                Text('Kod analiz ediliyor…', style: theme.textTheme.bodySmall),
              for (var i = 0; i < son.length; i++)
                AnimatedOpacity(
                  key: ValueKey('${p.thoughts.length - son.length + i}'),
                  duration: const Duration(milliseconds: 250),
                  // Eski düşünceler soluklaşır, en yenisi belirgin kalır.
                  opacity: (0.35 + 0.65 * (i + 1) / son.length).clamp(0.0, 1.0),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      son[i],
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontWeight:
                            i == son.length - 1 ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ),
                ),
            ],
          );
        }),
      ),
    );
  }
}

class _FixResultDialog extends StatefulWidget {
  final FixResult result;
  const _FixResultDialog({required this.result});
  @override
  State<_FixResultDialog> createState() => _FixResultDialogState();
}

class _FixResultDialogState extends State<_FixResultDialog> {
  bool _showDiff = false;
  bool _showThoughts = false;

  static Color _levelColor(String level) => switch (level) {
        'hata' => const Color(0xFFEF5350),
        'uyari' => const Color(0xFFFFA726),
        _ => const Color(0xFF42A5F5),
      };

  static IconData _levelIcon(String level) => switch (level) {
        'hata' => Icons.error_outline,
        'uyari' => Icons.warning_amber_rounded,
        _ => Icons.lightbulb_outline,
      };

  Color _scoreColor(int v) => v >= 85
      ? const Color(0xFF66BB6A)
      : v >= 60
          ? const Color(0xFFFFCA28)
          : const Color(0xFFEF5350);

  Widget _metric(ThemeData theme, String label, int value) {
    final c = _scoreColor(value);
    return Expanded(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('$label  %$value',
            style: theme.textTheme.labelMedium
                ?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: value / 100,
            minHeight: 6,
            color: c,
            backgroundColor: c.withOpacity(0.18),
          ),
        ),
      ]),
    );
  }

  Widget _lineChip(ThemeData theme, int? line) {
    if (line == null) return const SizedBox(width: 0);
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ActionChip(
        visualDensity: VisualDensity.compact,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        padding: EdgeInsets.zero,
        label: Text('Satır $line', style: const TextStyle(fontSize: 11)),
        tooltip: 'Bu satıra git',
        onPressed: () => Navigator.pop(context, 'goto:$line'),
      ),
    );
  }

  Widget _fixTile(ThemeData theme, FixItem f) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.5),
        borderRadius: BorderRadius.circular(6),
        border: Border(left: BorderSide(color: _scoreColor(f.confidence), width: 3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          _lineChip(theme, f.line),
          Expanded(
            child: Text(f.title,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
          ),
          Tooltip(
            message: 'Bu düzeltmeye güven',
            child: Text('%${f.confidence}',
                style: theme.textTheme.labelSmall
                    ?.copyWith(color: _scoreColor(f.confidence))),
          ),
        ]),
        if (f.detail.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(f.detail, style: theme.textTheme.bodySmall),
        ],
      ]),
    );
  }

  Widget _warningTile(ThemeData theme, FixItem w) {
    final c = _levelColor(w.level);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.only(top: 2, right: 8),
          child: Icon(_levelIcon(w.level), size: 16, color: c),
        ),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              _lineChip(theme, w.line),
              Expanded(
                child: Text(w.title,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(fontWeight: FontWeight.w600)),
              ),
            ]),
            if (w.hint.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text('💡 ${w.hint}', style: theme.textTheme.bodySmall),
              ),
          ]),
        ),
      ]),
    );
  }

  Widget _sectionTitle(ThemeData theme, String t) => Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 6),
        child: Text(t,
            style: theme.textTheme.labelLarge
                ?.copyWith(fontWeight: FontWeight.w700)),
      );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final r = widget.result;
    final rep = r.report;
    final mono = TextStyle(
        fontFamily: kMonoFontFamily,
        fontFamilyFallback: kMonoFontFallback,
        fontSize: 12);

    final body = <Widget>[];
    if (rep != null) {
      body.addAll([
        Text(rep.summary, style: theme.textTheme.bodyMedium),
        if (r.verification.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(r.verification, style: theme.textTheme.bodySmall),
          ),
        const SizedBox(height: 12),
        Row(children: [
          _metric(theme, 'Kod sağlığı', rep.health),
          if (rep.fixes.isNotEmpty) ...[
            const SizedBox(width: 16),
            _metric(theme, 'Güven', rep.confidence),
          ],
        ]),
        const SizedBox(height: 4),
        Text(
          '${(rep.durationMs / 1000).toStringAsFixed(1)} sn • '
          '${rep.runs} test çalıştırması',
          style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurface.withOpacity(0.6)),
        ),
        if (rep.fixes.isNotEmpty) ...[
          _sectionTitle(theme, 'Yaptığım düzeltmeler (${rep.fixes.length})'),
          for (final f in rep.fixes) _fixTile(theme, f),
        ],
        if (rep.warnings.isNotEmpty) ...[
          _sectionTitle(theme, 'Öneriler ve uyarılar (${rep.warnings.length})'),
          for (final w in rep.warnings) _warningTile(theme, w),
        ],
        if (rep.thoughts.isNotEmpty) ...[
          const SizedBox(height: 4),
          TextButton.icon(
            style: TextButton.styleFrom(padding: EdgeInsets.zero),
            onPressed: () => setState(() => _showThoughts = !_showThoughts),
            icon: Icon(_showThoughts ? Icons.expand_less : Icons.psychology_alt,
                size: 18),
            label: Text(_showThoughts
                ? 'Düşünce sürecini gizle'
                : 'Düşünce sürecini göster'),
          ),
          if (_showThoughts)
            for (final t in rep.thoughts)
              Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text(t, style: theme.textTheme.bodySmall),
              ),
        ],
      ]);
    } else if (r.changes.isNotEmpty) {
      body.addAll([
        for (final c in r.changes.take(12))
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(c, style: theme.textTheme.bodySmall),
          ),
      ]);
    }

    if (r.codeChanged && r.diff.isNotEmpty) {
      body.addAll([
        const SizedBox(height: 4),
        TextButton.icon(
          style: TextButton.styleFrom(padding: EdgeInsets.zero),
          onPressed: () => setState(() => _showDiff = !_showDiff),
          icon: Icon(_showDiff ? Icons.expand_less : Icons.difference_outlined,
              size: 18),
          label: Text(_showDiff ? 'Farkları gizle' : 'Kod farklarını göster'),
        ),
        if (_showDiff || rep == null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.5),
              borderRadius: BorderRadius.circular(4),
            ),
            child: SelectableText.rich(TextSpan(children: [
              for (final l in r.diff.split('\n'))
                TextSpan(
                  text: '$l\n',
                  style: mono.copyWith(
                    color: l.startsWith('+') && !l.startsWith('+++')
                        ? const Color(0xFF66BB6A)
                        : l.startsWith('-') && !l.startsWith('---')
                            ? const Color(0xFFEF5350)
                            : null,
                  ),
                ),
            ])),
          ),
      ]);
    }

    return AlertDialog(
      title: Row(children: [
        Icon(
          rep == null || rep.status == 'ok'
              ? Icons.auto_fix_high
              : Icons.report_gmailerrorred,
          color: rep == null || rep.status == 'ok'
              ? theme.colorScheme.primary
              : const Color(0xFFFFA726),
        ),
        const SizedBox(width: 10),
        Text(r.codeChanged ? 'Akıllı Düzeltme Raporu' : 'Kod İnceleme Raporu'),
      ]),
      content: SizedBox(
        width: 680,
        height: 520,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: body,
          ),
        ),
      ),
      actions: r.codeChanged
          ? [
              TextButton(
                  onPressed: () => Navigator.pop(context, 'reject'),
                  child: const Text('Reddet')),
              OutlinedButton(
                  onPressed: () => Navigator.pop(context, 'tab'),
                  child: const Text('Yeni Sekmede Aç')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, 'apply'),
                  child: const Text('Uygula')),
            ]
          : [
              FilledButton(
                  onPressed: () => Navigator.pop(context, 'reject'),
                  child: const Text('Kapat')),
            ],
    );
  }
}

Future<void> _runConvert(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final backend = context.read<BackendService>();
  final kod = ed.activeContent.value;
  if (kod.isEmpty) {
    showAppSnackbar(context, 'Çevrilecek kod yok', kind: SnackKind.error);
    return;
  }
  try {
    final r = await backend.call('kodu_cevir', {'kod': kod});
    ed.createUntitled(
      name: 'cevrilmis${r['uzanti'] ?? '.trpy'}',
      content: r['sonuc']?.toString() ?? '',
      context: context,
    );
    if (context.mounted) {
      showAppSnackbar(context, '${r['kaynak']} → ${r['hedef']} çevrildi',
          kind: SnackKind.success);
    }
  } catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, 'Çeviri hatası: $e', kind: SnackKind.error);
    }
  }
}

void _debugWrap(
    BuildContext context, Future<void> Function(BreakpointProvider) f) {
  final bp = context.read<BreakpointProvider>();
  f(bp).then((_) {
    if (bp.notice != null && context.mounted) {
      showAppSnackbar(context, bp.notice!);
      bp.clearNotice();
    }
  });
}

/// Hata ayıklamayı başlatır (stepIn: ilk satırda dur).
void _debugStart(BuildContext context, {bool stepIn = false}) {
  final ed = context.read<EditorProvider>();
  final tab = ed.activeTab;
  if (tab == null || tab.path == kSettingsPath) {
    showAppSnackbar(context, 'Hata ayıklanacak bir kod sekmesi yok',
        kind: SnackKind.error);
    return;
  }
  final kod = ed.activeContent.value;
  if (kod.trim().isEmpty) {
    showAppSnackbar(context, 'Kod boş', kind: SnackKind.error);
    return;
  }
  final terminal = context.read<TerminalProvider>();
  context.read<UiProvider>().revealTerminal();
  terminal.beginRun();
  _debugWrap(context, (bp) async {
    await bp.start(tabId: tab.id, kod: kod, stepIn: stepIn);
    if (!bp.debugging) terminal.endRun();
  });
}

/// F5: duraklatılmışsa devam eder, oturum yoksa başlatır.
void _debugStartOrContinue(BuildContext context) {
  final bp = context.read<BreakpointProvider>();
  if (bp.paused) {
    _debugWrap(context, (b) => b.continueRun());
  } else if (!bp.debugging) {
    _debugStart(context);
  }
}

/// F10 / F11: oturum yoksa ilk satırda durarak başlatır (VS Code davranışı).
void _debugStepAction(BuildContext context,
    Future<void> Function(BreakpointProvider) f) {
  final bp = context.read<BreakpointProvider>();
  if (bp.paused) {
    _debugWrap(context, f);
  } else if (!bp.debugging) {
    _debugStart(context, stepIn: true);
  }
}

List<AppAction> buildAppActions() {
  return [
    AppAction(
      id: 'file.new_tab',
      label: 'Yeni Sekme',
      menu: 'Dosya',
      shortcut: 'Ctrl+T',
      activator: const SingleActivator(LogicalKeyboardKey.keyT, control: true),
      icon: Icons.add,
      run: (c) {
        c.read<EditorProvider>().createUntitled(context: c);
      },
    ),
    AppAction(
      id: 'file.open_file',
      label: 'Dosya Aç',
      menu: 'Dosya',
      shortcut: 'Ctrl+O',
      activator: const SingleActivator(LogicalKeyboardKey.keyO, control: true),
      icon: Icons.file_open,
      run: (c) => openFilePicker(c),
    ),
    AppAction(
      id: 'file.open',
      label: 'Klasör Aç',
      menu: 'Dosya',
      icon: Icons.folder_open,
      run: (c) async {
        final d = await FilePicker.platform.getDirectoryPath();
        if (d != null && c.mounted) {
          await c.read<FileTreeProvider>().setProjectDirectory(d);
        }
      },
    ),
    AppAction(
      id: 'file.save',
      label: 'Kaydet',
      menu: 'Dosya',
      shortcut: 'Ctrl+S',
      activator: const SingleActivator(LogicalKeyboardKey.keyS, control: true),
      icon: Icons.save,
      run: _runSave,
    ),
    AppAction(
      id: 'file.save_as',
      label: 'Farklı Kaydet',
      menu: 'Dosya',
      icon: Icons.save_as,
      run: (c) {
        c.read<EditorProvider>().saveAsActive().then((kaydedildi) {
          if (kaydedildi && c.mounted) {
            showAppSnackbar(c, 'Kaydedildi', kind: SnackKind.success);
          }
        }).catchError((e) {
          if (c.mounted) {
            showAppSnackbar(c, 'Kaydetme hatası: $e', kind: SnackKind.error);
          }
        });
      },
    ),
    AppAction(
      id: 'edit.find',
      label: 'Bul',
      menu: 'Düzenle',
      shortcut: 'Ctrl+F',
      activator: const SingleActivator(LogicalKeyboardKey.keyF, control: true),
      icon: Icons.search,
      run: (c) => _runFind(c, false),
    ),
    AppAction(
      id: 'edit.find_replace',
      label: 'Bul / Değiştir',
      menu: 'Düzenle',
      shortcut: 'Ctrl+H',
      activator: const SingleActivator(LogicalKeyboardKey.keyH, control: true),
      icon: Icons.find_replace,
      run: (c) => _runFind(c, true),
    ),
    AppAction(
      id: 'edit.comment',
      label: 'Yorum Aç/Kapat',
      menu: 'Düzenle',
      shortcut: 'Ctrl+/',
      activator: const SingleActivator(LogicalKeyboardKey.slash, control: true),
      icon: Icons.code,
      run: (c) => toggleComment(c.read<EditorProvider>().uiController),
    ),
    AppAction(
      id: 'edit.duplicate',
      label: 'Satırı Çoğalt',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Shift+D',
      activator: const SingleActivator(LogicalKeyboardKey.keyD,
          control: true, shift: true),
      icon: Icons.content_copy,
      run: (c) => duplicateCurrentLine(c.read<EditorProvider>().uiController),
    ),
    AppAction(
      id: 'edit.move_up',
      label: 'Satırı Yukarı Taşı',
      menu: 'Düzenle',
      shortcut: 'Alt+Up',
      activator: const SingleActivator(LogicalKeyboardKey.arrowUp, alt: true),
      icon: Icons.arrow_upward,
      run: (c) => moveCurrentLine(c.read<EditorProvider>().uiController, true),
    ),
    AppAction(
      id: 'edit.move_down',
      label: 'Satırı Aşağı Taşı',
      menu: 'Düzenle',
      shortcut: 'Alt+Down',
      activator: const SingleActivator(LogicalKeyboardKey.arrowDown, alt: true),
      icon: Icons.arrow_downward,
      run: (c) => moveCurrentLine(c.read<EditorProvider>().uiController, false),
    ),
    AppAction(
      id: 'view.explorer',
      label: 'Gezgin Aç/Kapat',
      menu: 'Görünüm',
      icon: Icons.account_tree_outlined,
      run: (c) => c.read<UiProvider>().toggleExplorer(),
    ),
    AppAction(
      id: 'view.ai',
      label: 'AI Panel Aç/Kapat',
      menu: 'Görünüm',
      icon: Icons.auto_awesome,
      run: (c) => c.read<UiProvider>().toggleAi(),
    ),
    AppAction(
      id: 'view.terminal',
      label: 'Terminal Aç/Kapat',
      menu: 'Görünüm',
      shortcut: 'Ctrl+J',
      activator: const SingleActivator(LogicalKeyboardKey.keyJ, control: true),
      icon: Icons.terminal,
      run: (c) => c.read<UiProvider>().toggleTerminal(),
    ),
    AppAction(
      id: 'view.tab_left',
      label: 'Sekmeyi Sola Taşı',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+PageUp',
      activator: const SingleActivator(LogicalKeyboardKey.pageUp,
          control: true, shift: true),
      icon: Icons.keyboard_double_arrow_left,
      run: (c) => c.read<EditorProvider>().moveActiveTab(-1),
    ),
    AppAction(
      id: 'view.tab_right',
      label: 'Sekmeyi Sağa Taşı',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+PageDown',
      activator: const SingleActivator(LogicalKeyboardKey.pageDown,
          control: true, shift: true),
      icon: Icons.keyboard_double_arrow_right,
      run: (c) => c.read<EditorProvider>().moveActiveTab(1),
    ),
    AppAction(
      id: 'view.palette',
      label: 'Komut Paleti',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+P',
      activator: const SingleActivator(LogicalKeyboardKey.keyP,
          control: true, shift: true),
      icon: Icons.palette_outlined,
      run: (c) => showDialog<AppAction>(
              context: c, builder: (_) => const CommandPaletteDialog())
          .then((secilen) {
        if (secilen != null && c.mounted) secilen.run(c);
      }),
    ),
    AppAction(
      id: 'view.settings',
      label: 'Ayarlar',
      menu: 'Görünüm',
      icon: Icons.settings_outlined,
      run: (c) => c.read<EditorProvider>().openSettings(),
    ),
    AppAction(
      id: 'run.run',
      label: 'Çalıştır',
      menu: 'Çalıştır',
      shortcut: 'Ctrl+R',
      activator: const SingleActivator(LogicalKeyboardKey.keyR, control: true),
      icon: Icons.play_arrow,
      run: _runRun,
    ),
    AppAction(
      id: 'run.stop',
      label: 'Durdur',
      menu: 'Çalıştır',
      icon: Icons.stop,
      run: (c) => c.read<TerminalProvider>().stop(),
    ),
    AppAction(
      id: 'run.breakpoint',
      label: 'Breakpoint Aç/Kapat',
      menu: 'Çalıştır',
      shortcut: 'F9',
      activator: const SingleActivator(LogicalKeyboardKey.f9),
      icon: Icons.bookmark_border,
      run: (c) {
        final ed = c.read<EditorProvider>();
        final ctrl = ed.uiController;
        if (ctrl == null) return;
        final line = c.read<EditorProvider>().caretModelLine?.call() ??
            cursorLineOf(ctrl);
        c.read<BreakpointProvider>().toggle(ed.activeTab?.id, line);
      },
    ),
    AppAction(
      id: 'run.breakpoint_clear',
      label: "Tüm Breakpoint'leri Kaldır",
      menu: 'Çalıştır',
      icon: Icons.layers_clear_outlined,
      run: (c) => c
          .read<BreakpointProvider>()
          .clearAll(c.read<EditorProvider>().activeTab?.id),
    ),
    AppAction(
      id: 'run.debug_start',
      label: 'Debug Başlat / Devam',
      menu: 'Çalıştır',
      shortcut: 'F5',
      activator: const SingleActivator(LogicalKeyboardKey.f5),
      icon: Icons.bug_report,
      run: _debugStartOrContinue,
    ),
    AppAction(
      id: 'run.debug_step',
      label: 'Adım At',
      menu: 'Çalıştır',
      shortcut: 'F10',
      activator: const SingleActivator(LogicalKeyboardKey.f10),
      icon: Icons.redo,
      run: (c) => _debugStepAction(c, (bp) => bp.step()),
    ),
    AppAction(
      id: 'run.debug_step_into',
      label: 'İçine Gir',
      menu: 'Çalıştır',
      shortcut: 'F11',
      activator: const SingleActivator(LogicalKeyboardKey.f11),
      icon: Icons.subdirectory_arrow_right,
      run: (c) => _debugStepAction(c, (bp) => bp.stepInto()),
    ),
    AppAction(
      id: 'run.debug_step_out',
      label: 'Dışına Çık',
      menu: 'Çalıştır',
      shortcut: 'Shift+F11',
      activator:
          const SingleActivator(LogicalKeyboardKey.f11, shift: true),
      icon: Icons.subdirectory_arrow_left,
      run: (c) {
        if (c.read<BreakpointProvider>().paused) {
          _debugWrap(c, (bp) => bp.stepOut());
        }
      },
    ),
    AppAction(
      id: 'run.debug_continue',
      label: 'Devam',
      menu: 'Çalıştır',
      icon: Icons.fast_forward,
      run: (c) {
        if (c.read<BreakpointProvider>().paused) {
          _debugWrap(c, (bp) => bp.continueRun());
        }
      },
    ),
    AppAction(
      id: 'run.debug_pause',
      label: 'Duraklat',
      menu: 'Çalıştır',
      shortcut: 'F6',
      activator: const SingleActivator(LogicalKeyboardKey.f6),
      icon: Icons.pause,
      run: (c) {
        final bp = c.read<BreakpointProvider>();
        if (bp.debugging && !bp.paused) _debugWrap(c, (b) => b.pause());
      },
    ),
    AppAction(
      id: 'run.debug_stop',
      label: 'Debug Durdur',
      menu: 'Çalıştır',
      shortcut: 'Shift+F5',
      activator: const SingleActivator(LogicalKeyboardKey.f5, shift: true),
      icon: Icons.cancel_outlined,
      run: (c) => _debugWrap(c, (bp) => bp.stop()),
    ),
    AppAction(
      id: 'tools.convert',
      label: 'TürKod ⇄ Python Çevir',
      menu: 'Araçlar',
      icon: Icons.swap_horiz,
      run: (c) => _runConvert(c),
    ),
    AppAction(
      id: 'tools.fix',
      label: 'Düzelt',
      menu: 'Araçlar',
      icon: Icons.auto_fix_high,
      run: (c) => _runFix(c),
    ),
    AppAction(
      id: 'tools.stats',
      label: 'Kod İstatistikleri',
      menu: 'Araçlar',
      icon: Icons.info_outline,
      run: (c) => showDialog(context: c, builder: (_) => const StatsDialog()),
    ),
    AppAction(
      id: 'tools.todo',
      label: 'TODO Listesi',
      menu: 'Araçlar',
      icon: Icons.checklist,
      run: (c) => showDialog(context: c, builder: (_) => const TodoDialog()),
    ),
    AppAction(
      id: 'tools.codesearch',
      label: 'Kod Arama Çevirici',
      menu: 'Araçlar',
      icon: Icons.manage_search,
      run: (c) =>
          showDialog(context: c, builder: (_) => const CodeSearchDialog()),
    ),
    AppAction(
      id: 'help.about',
      label: 'Hakkında / İmza',
      menu: 'Yardım',
      icon: Icons.verified_user_outlined,
      run: (c) =>
          showDialog(context: c, builder: (_) => const AboutSignDialog()),
    ),
    AppAction(
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
  ];
}

AppAction? findAction(List<AppAction> actions, String id) {
  for (final a in actions) {
    if (a.id == id) return a;
  }
  return null;
}

int cursorLineOf(TextEditingController c) {
  final off =
      c.selection.isValid ? c.selection.baseOffset.clamp(0, c.text.length) : 0;
  return _lineNumber(c.text, off);
}

// ============================================================================
// TEMA SİSTEMİ
// ============================================================================

class AppSyntaxPalette extends ThemeExtension<AppSyntaxPalette> {
  final Color keyword;
  final Color string;
  final Color number;
  final Color comment;
  final Color function;
  final Color type;
  final Color variable;
  final Color operatorColor;
  final Color punctuation;
  // === Arama vurgusu renkleri (tema başına ayrı tanımlı) =================
  // Eskiden arama eşleşmesi sadece _ctrl.selection'a atanıyordu; bu da
  // görsel olarak NORMAL metin seçimiyle birebir aynı renkti (kullanıcı
  // "seçtiğim mi yoksa bulunan mı" ayıramıyordu) ve koyu temada düşük
  // kontrastlıydı. Artık TÜM eşleşmeler ve AKTİF eşleşme için ayrı,
  // seçim renginden bağımsız, tema başına tanımlı renkler var.
  final Color matchBackground;
  final Color activeMatchBackground;
  final Color activeMatchBorder;
  const AppSyntaxPalette({
    required this.keyword,
    required this.string,
    required this.number,
    required this.comment,
    required this.function,
    required this.type,
    required this.variable,
    required this.operatorColor,
    required this.punctuation,
    this.matchBackground = const Color(0x4DFFC107), // amber @ ~30%
    this.activeMatchBackground = const Color(0xB3FF9800), // turuncu @ ~70%
    this.activeMatchBorder = const Color(0xFFFFB300),
  });
  static const AppSyntaxPalette fallback = AppSyntaxPalette(
    keyword: Color(0xFF93C5FD),
    string: Color(0xFF86EFAC),
    number: Color(0xFFFCD34D),
    comment: Color(0xFF6B7280),
    function: Color(0xFFF472B6),
    type: Color(0xFF38BDF8),
    variable: Color(0xFFE5E7EB),
    operatorColor: Color(0xFF94A3B8),
    punctuation: Color(0xFF94A3B8),
  );
  @override
  AppSyntaxPalette copyWith({
    Color? keyword,
    Color? string,
    Color? number,
    Color? comment,
    Color? function,
    Color? type,
    Color? variable,
    Color? operatorColor,
    Color? punctuation,
    Color? matchBackground,
    Color? activeMatchBackground,
    Color? activeMatchBorder,
  }) {
    return AppSyntaxPalette(
      keyword: keyword ?? this.keyword,
      string: string ?? this.string,
      number: number ?? this.number,
      comment: comment ?? this.comment,
      function: function ?? this.function,
      type: type ?? this.type,
      variable: variable ?? this.variable,
      operatorColor: operatorColor ?? this.operatorColor,
      punctuation: punctuation ?? this.punctuation,
      matchBackground: matchBackground ?? this.matchBackground,
      activeMatchBackground:
          activeMatchBackground ?? this.activeMatchBackground,
      activeMatchBorder: activeMatchBorder ?? this.activeMatchBorder,
    );
  }

  @override
  AppSyntaxPalette lerp(
      covariant ThemeExtension<AppSyntaxPalette>? other, double t) {
    if (other is! AppSyntaxPalette) return this;
    return AppSyntaxPalette(
      keyword: Color.lerp(keyword, other.keyword, t)!,
      string: Color.lerp(string, other.string, t)!,
      number: Color.lerp(number, other.number, t)!,
      comment: Color.lerp(comment, other.comment, t)!,
      function: Color.lerp(function, other.function, t)!,
      type: Color.lerp(type, other.type, t)!,
      variable: Color.lerp(variable, other.variable, t)!,
      operatorColor: Color.lerp(operatorColor, other.operatorColor, t)!,
      punctuation: Color.lerp(punctuation, other.punctuation, t)!,
      matchBackground: Color.lerp(matchBackground, other.matchBackground, t)!,
      activeMatchBackground:
          Color.lerp(activeMatchBackground, other.activeMatchBackground, t)!,
      activeMatchBorder:
          Color.lerp(activeMatchBorder, other.activeMatchBorder, t)!,
    );
  }
}

class AppThemeDefinition {
  final String name;
  final Brightness brightness;
  final Color primary;
  final Color onPrimary;
  final Color surface;
  final Color surfaceLow;
  final Color surfaceContainer;
  final Color surfaceHigh;
  final Color onSurface;
  final Color outline;
  final Color outlineVariant;
  final Color hover;
  final AppSyntaxPalette syntax;
  const AppThemeDefinition({
    required this.name,
    required this.brightness,
    required this.primary,
    required this.onPrimary,
    required this.surface,
    required this.surfaceLow,
    required this.surfaceContainer,
    required this.surfaceHigh,
    required this.onSurface,
    required this.outline,
    required this.outlineVariant,
    required this.hover,
    required this.syntax,
  });
}

class AppThemeRegistry {
  static const List<AppThemeDefinition> definitions = [
    AppThemeDefinition(
      name: 'Modern Koyu',
      brightness: Brightness.dark,
      primary: Color(0xFF3B82F6),
      onPrimary: Color(0xFFFFFFFF),
      surface: Color(0xFF0B1220),
      surfaceLow: Color(0xFF0B1220),
      surfaceContainer: Color(0xFF16203A),
      surfaceHigh: Color(0xFF1E293B),
      onSurface: Color(0xFFE5E7EB),
      outline: Color(0xFF334155),
      outlineVariant: Color(0xFF243248),
      hover: Color(0xFF1E293B),
      syntax: AppSyntaxPalette.fallback,
    ),
    AppThemeDefinition(
      name: 'Koyu',
      brightness: Brightness.dark,
      primary: Color(0xFF3794FF),
      onPrimary: Color(0xFFFFFFFF),
      surface: Color(0xFF1E1E1E),
      surfaceLow: Color(0xFF1A1A1A),
      surfaceContainer: Color(0xFF252526),
      surfaceHigh: Color(0xFF2D2D30),
      onSurface: Color(0xFFD4D4D4),
      outline: Color(0xFF3C3C3C),
      outlineVariant: Color(0xFF2D2D2D),
      hover: Color(0xFF2A2D2E),
      syntax: AppSyntaxPalette(
        keyword: Color(0xFF569CD6),
        string: Color(0xFFCE9178),
        number: Color(0xFFB5CEA8),
        comment: Color(0xFF6A9955),
        function: Color(0xFFDCDCAA),
        type: Color(0xFF4EC9B0),
        variable: Color(0xFFD4D4D4),
        operatorColor: Color(0xFFD4D4D4),
        punctuation: Color(0xFFD4D4D4),
        // Koyu zemin (#1E1E1E) üzerinde yüksek kontrast: amber/turuncu.
        matchBackground: Color(0x4DFFC107),
        activeMatchBackground: Color(0xB3FF9800),
        activeMatchBorder: Color(0xFFFFB300),
      ),
    ),
    AppThemeDefinition(
      name: 'Açık',
      brightness: Brightness.light,
      primary: Color(0xFF2563EB),
      onPrimary: Color(0xFFFFFFFF),
      surface: Color(0xFFFFFFFF),
      surfaceLow: Color(0xFFFFFFFF),
      surfaceContainer: Color(0xFFF3F3F3),
      surfaceHigh: Color(0xFFE8E8E8),
      onSurface: Color(0xFF111827),
      outline: Color(0xFFC8C8C8),
      outlineVariant: Color(0xFFE0E0E0),
      hover: Color(0xFFF0F0F0),
      syntax: AppSyntaxPalette(
        keyword: Color(0xFF0000B3),
        string: Color(0xFF86181D),
        number: Color(0xFF006B45),
        comment: Color(0xFF4B5563),
        function: Color(0xFF5C4315),
        type: Color(0xFF075A70),
        variable: Color(0xFF000000),
        operatorColor: Color(0xFF000000),
        punctuation: Color(0xFF000000),
        // Beyaz zemin üzerinde yüksek kontrast: doygun sarı/amber.
        // (Koyu temadakiyle aynı ton ailesini kullanıyoruz ama daha az
        // saydam, çünkü beyaz üstünde düşük-alfa sarı neredeyse görünmez.)
        matchBackground: Color(0x80FDE047),
        activeMatchBackground: Color(0xB3F59E0B),
        activeMatchBorder: Color(0xFFB45309),
      ),
    ),
  ];
  static final Map<String, ThemeData> _cache = {};
  static AppThemeDefinition find(String name) {
    for (final d in definitions) {
      if (d.name == name) return d;
    }
    return definitions.first;
  }

  static ThemeData build(String name) {
    final def = find(name);
    return _cache.putIfAbsent(def.name, () => _build(def));
  }

  static ColorScheme _scheme(AppThemeDefinition d) {
    final base = d.brightness == Brightness.dark
        ? const ColorScheme.dark()
        : const ColorScheme.light();
    return base.copyWith(
      primary: d.primary,
      onPrimary: d.onPrimary,
      primaryContainer: d.surfaceHigh,
      onPrimaryContainer: d.onSurface,
      secondary: d.primary,
      onSecondary: d.onPrimary,
      secondaryContainer: d.surfaceHigh,
      onSecondaryContainer: d.onSurface,
      tertiary: d.primary,
      onTertiary: d.onPrimary,
      tertiaryContainer: d.surfaceHigh,
      onTertiaryContainer: d.onSurface,
      surface: d.surface,
      onSurface: d.onSurface,
      surfaceContainerLowest: d.surfaceLow,
      surfaceContainerLow: d.surfaceLow,
      surfaceContainer: d.surfaceContainer,
      surfaceContainerHigh: d.surfaceHigh,
      surfaceContainerHighest: d.surfaceHigh,
      outline: d.outline,
      outlineVariant: d.outlineVariant,
      inverseSurface: d.onSurface,
      onInverseSurface: d.surface,
      surfaceTint: Colors.transparent,
      shadow: Colors.transparent,
    );
  }

  static ThemeData _build(AppThemeDefinition def) {
    final scheme = _scheme(def);
    final base = ThemeData(
      useMaterial3: true,
      brightness: def.brightness,
      colorScheme: scheme,
    );
    return base.copyWith(
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      splashColor: Colors.transparent,
      hoverColor: def.hover,
      shadowColor: Colors.transparent,
      canvasColor: def.surfaceContainer,
      scaffoldBackgroundColor: def.surface,
      dividerTheme: DividerThemeData(
        color: def.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: scheme.inverseSurface,
          borderRadius: BorderRadius.circular(3),
          border: Border.all(color: def.outlineVariant),
        ),
        textStyle: TextStyle(color: scheme.onInverseSurface, fontSize: 12),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: def.surfaceLow,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(3),
          borderSide: BorderSide(color: def.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(3),
          borderSide: BorderSide(color: def.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(3),
          borderSide: BorderSide(color: def.primary),
        ),
      ),
      dialogTheme: DialogThemeData(
        elevation: 0,
        backgroundColor: def.surfaceContainer,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
          side: BorderSide(color: def.outline),
        ),
        titleTextStyle: base.textTheme.titleMedium
            ?.copyWith(color: scheme.onSurface, fontWeight: FontWeight.w600),
        contentTextStyle:
            base.textTheme.bodyMedium?.copyWith(color: scheme.onSurface),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          elevation: 0,
          shadowColor: Colors.transparent,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          elevation: 0,
          shadowColor: Colors.transparent,
          side: BorderSide(color: def.outlineVariant),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          textStyle: const TextStyle(fontSize: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          textStyle: const TextStyle(fontSize: 13),
        ),
      ),
      listTileTheme:
          const ListTileThemeData(horizontalTitleGap: 8, minVerticalPadding: 2),
      extensions: [def.syntax],
    );
  }
}

// ============================================================================
// SYNTAX HIGHLIGHTING
// ============================================================================

class SyntaxHighlightingController extends TextEditingController {
  // --- Programatik değişiklik izleme -----------------------------------
  // KÖK NEDEN DÜZELTMESİ: Önceden, satır/komut işlemleri (parantez
  // kapama, girinti, yorum aç/kapa, satır kopyala/taşı, öneri kabul
  // etme...) bu controller'ı DOĞRUDAN `value =` ile değiştiriyor ama
  // _CodeEditorState._onControllerChange içindeki "fold görünümü
  // geçerli mi" koruması bunu PROGRAMATİK olarak işaretlemiyordu. Sonuç:
  // o anki fold durumuna bağlı olarak değişiklik bazen gerçek editöre
  // (re.CodeEditor / _reCtrl) hiç yansımıyor, kullanıcı aynı tuşa 2-3 kez
  // basmak zorunda kalıyordu (ör. kapanan parantezin üzerinden atlama).
  // Artık HER yerde ham `value =`/`text =`/`selection =` ataması yerine
  // [setProgrammaticValue] kullanılmalı; bu, hem State içindeki hem de
  // (toggleComment, duplicateCurrentLine, moveCurrentLine, jumpToLine
  // gibi) dışarıdaki serbest fonksiyonlardan erişilebilir.
  bool _programmatic = false;
  bool get isProgrammaticChange => _programmatic;

  /// Bu controller'ı "güvenilir" (editör komutu kaynaklı) bir değerle
  /// günceller. Kullanıcının ham klavye girdisinden DEĞİL, bilinçli bir
  /// düzenleme komutundan (girinti, parantez kapama, satır taşıma, öneri
  /// kabul etme vb.) geliyorsa HER ZAMAN bunu kullan.
  void setProgrammaticValue(TextEditingValue v) {
    final was = _programmatic;
    _programmatic = true;
    try {
      value = v;
    } finally {
      _programmatic = was;
    }
  }

  /// `.clear()`, `.text = ...` gibi doğrudan `value =` ATAMASI OLMAYAN
  /// ama yine de programatik (güvenilir) sayılması gereken işlemler için.
  T runProgrammatic<T>(T Function() action) {
    final was = _programmatic;
    _programmatic = true;
    try {
      return action();
    } finally {
      _programmatic = was;
    }
  }

  String? _lastText;
  AppSyntaxPalette? _lastPalette;
  TextStyle? _lastStyle;
  List<TextSpan>? _lastSpans;
  static Set<String> _keywords = {
    'eğer',
    'eger',
    'değilse',
    'degilse',
    'değilse_eğer',
    'degilse_eger',
    'döngü',
    'dongu',
    'için',
    'icin',
    'içinde',
    'icinde',
    'fonksiyon',
    'sınıf',
    'sinif',
    'döndür',
    'dondur',
    'dene',
    'hata_yakala',
    'sonunda',
    'içe_aktar',
    'ice_aktar',
    'den',
    'olarak',
    've',
    'veya',
    'değil',
    'degil',
    'doğru',
    'dogru',
    'yanlış',
    'yanlis',
    'hiçlik',
    'hiclik',
    'kır',
    'kir',
    'devam_et',
    'geç',
    'gec',
    'ile',
    'bekle',
    'kendisi',
    'ise',
  };
  static Set<String> _builtins = {
    'yazdır',
    'yazdir',
    'girdi_al',
    'uzunluk',
    'aralık',
    'aralik',
    'tip',
    'toplam',
    'mutlak',
    'yuvarla',
    'üssü',
    'ussu',
    'nesne_mi',
    'tamsayı',
    'tamsayi',
    'metin',
    'ondalıklı',
    'ondalikli',
    'mantıksal',
    'mantiksal',
    'liste',
    'demet',
    'sözlük',
    'sozluk',
    'küme',
    'kume',
    'hepsi',
    'herhangi',
    'sırala',
    'sirala',
    'en_büyük',
    'en_buyuk',
    'en_küçük',
    'en_kucuk',
  };
  static Set<String> _modules = {
    'matematik',
    'matematikf',
    'rastgele',
    'tarih_saat',
    'işletim_sistemi',
    'isletim_sistemi',
    'sistem',
    'json',
    'desen',
    'kaplumbağa',
    'kaplumbaga',
    'istatistik',
    'py_oyun',
    'tkinter_arayüz',
    'tkinter_arayuz',
  };
  static void configure(
      {Set<String>? keywords, Set<String>? builtins, Set<String>? modules}) {
    if (keywords != null && keywords.isNotEmpty) _keywords = keywords;
    if (builtins != null && builtins.isNotEmpty) _builtins = builtins;
    if (modules != null && modules.isNotEmpty) _modules = modules;
  }

  static final RegExp _tokenPattern = RegExp(
    r'''(#[^\n]*|\x22\x22\x22[\s\S]*?\x22\x22\x22|\x27\x27\x27[\s\S]*?\x27\x27\x27|\x22(?:\\.|[^\x22\\\n])*\x22|\x27(?:\\.|[^\x27\\\n])*\x27|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b|[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*|[+\-*/%=<>!&|^~:]+)''',
    unicode: true,
  );
  static final RegExp _identPattern =
      RegExp(r'^[A-Za-z_ÇŞĞÜÖİçşğüöı]', unicode: true);
  static final RegExp _typePattern = RegExp(r'^[A-ZÇŞĞÜÖİ]', unicode: true);
  @override
  TextSpan buildTextSpan({
    required BuildContext context,
    TextStyle? style,
    required bool withComposing,
  }) {
    final palette = Theme.of(context).extension<AppSyntaxPalette>() ??
        AppSyntaxPalette.fallback;
    final text = value.text;
    if (text == _lastText &&
        palette == _lastPalette &&
        style == _lastStyle &&
        _lastSpans != null) {
      return TextSpan(style: style, children: _lastSpans);
    }
    _lastSpans = _tokenize(text, palette, style ?? const TextStyle());
    _lastText = text;
    _lastPalette = palette;
    _lastStyle = style;
    return TextSpan(style: style, children: _lastSpans);
  }

  // === Arama vurgusu: Türkçe-güvenli eşleşme + renk birleştirme =========
  // KRİTİK TÜRKÇE HATASI (bilerek önlendi): Dart'ta 'İ'.toLowerCase() iki
  // kod birimi üretir ve naif toLowerCase() karşılaştırması offsetleri
  // kaydırabilir; ayrıca standart toLowerCase 'I'→'ı' ya da 'İ'→'i'
  // eşlemesini YAPMAZ (İngilizce kuralı kullanır). Bu yüzden ASCII dışı
  // Türkçe harfler için AYRI, elle tanımlı bir eşleme kullanılıyor; genel
  // karşılaştırma hiçbir zaman offset kayması yapmıyor (orijinal string
  // index'leri üzerinde çalışılıyor, küçültülmüş bir kopya üzerinde değil).
  static bool _trCharEquals(String a, String b) {
    if (a == b) return true;
    const upperToLower = {'İ': 'i', 'I': 'ı'};
    const lowerToUpper = {'i': 'İ', 'ı': 'I'};
    if (upperToLower[a] == b || lowerToUpper[a] == b) return true;
    if (upperToLower[b] == a || lowerToUpper[b] == a) return true;
    return a.toLowerCase() == b.toLowerCase();
  }

  /// [haystack] içinde [needle]'ın tüm (case-insensitive, Türkçe-güvenli)
  /// geçtiği [start, end) aralıklarını, ORİJİNAL metin offsetleriyle
  /// döndürür.
  static List<List<int>> findAllMatches(String haystack, String needle) {
    if (needle.isEmpty) return const [];
    final out = <List<int>>[];
    for (var i = 0; i + needle.length <= haystack.length; i++) {
      var ok = true;
      for (var j = 0; j < needle.length; j++) {
        if (!_trCharEquals(haystack[i + j], needle[j])) {
          ok = false;
          break;
        }
      }
      if (ok) {
        out.add([i, i + needle.length]);
        // Eşleşmeler örtüşmez ("aaa" içinde "aa" = 1 eşleşme). Örtüşen
        // eşleşmeler "Tümünü Değiştir"de metni bozuyordu.
        i += needle.length - 1;
      }
    }
    return out;
  }

  /// Sözdizimi renklendirmesinden gelen [baseSpans] ile arama eşleşme
  /// aralıklarını BİRLEŞTİRİR: her segment hem doğru sözdizimi rengini
  /// (anahtar kelime/string/sayı...) HEM DE (varsa) arama arka plan
  /// rengini aynı anda taşır. Aktif eşleşme [activeStart]/[activeEnd]
  /// (satır-yerel offset) verilirse daha güçlü bir renkle vurgulanır.
  static List<InlineSpan> applyFindHighlight(
    List<TextSpan> baseSpans,
    String lineText,
    String query, {
    int? activeStart,
    int? activeEnd,
    required Color matchBackground,
    required Color activeMatchBackground,
  }) {
    if (query.isEmpty) return baseSpans;
    final matches = findAllMatches(lineText, query);
    if (matches.isEmpty) return baseSpans;

    final breakpoints = <int>{0, lineText.length};
    var pos = 0;
    for (final s in baseSpans) {
      pos += s.text?.length ?? 0;
      breakpoints.add(pos);
    }
    for (final m in matches) {
      breakpoints.add(m[0]);
      breakpoints.add(m[1]);
    }
    if (activeStart != null && activeEnd != null) {
      breakpoints.add(activeStart);
      breakpoints.add(activeEnd);
    }
    final sorted = breakpoints.toList()..sort();

    final result = <InlineSpan>[];
    var tokenIdx = 0;
    var tokenStart = 0;
    for (var i = 0; i < sorted.length - 1; i++) {
      final segStart = sorted[i];
      final segEnd = sorted[i + 1];
      if (segStart == segEnd || segStart < 0 || segEnd > lineText.length) {
        continue;
      }
      while (tokenIdx < baseSpans.length &&
          tokenStart + (baseSpans[tokenIdx].text?.length ?? 0) <= segStart) {
        tokenStart += baseSpans[tokenIdx].text?.length ?? 0;
        tokenIdx++;
      }
      final baseStyle =
          tokenIdx < baseSpans.length ? baseSpans[tokenIdx].style : null;
      final segText = lineText.substring(segStart, segEnd);

      final inActive = activeStart != null &&
          activeEnd != null &&
          segStart >= activeStart &&
          segEnd <= activeEnd;
      final inAnyMatch =
          matches.any((m) => segStart >= m[0] && segEnd <= m[1]);

      var style = baseStyle ?? const TextStyle();
      if (inActive) {
        style = style.copyWith(backgroundColor: activeMatchBackground);
      } else if (inAnyMatch) {
        style = style.copyWith(backgroundColor: matchBackground);
      }
      result.add(TextSpan(text: segText, style: style));
    }
    return result;
  }

  static List<TextSpan> _tokenize(
      String text, AppSyntaxPalette palette, TextStyle base) {
    if (text.isEmpty) return const [];
    final spans = <TextSpan>[];
    var last = 0;
    for (final m in _tokenPattern.allMatches(text)) {
      if (m.start > last)
        spans.add(TextSpan(text: text.substring(last, m.start)));
      final token = m.group(0)!;
      TextStyle style = base;
      if (token.startsWith('#')) {
        style =
            base.copyWith(color: palette.comment, fontStyle: FontStyle.italic);
      } else if (token.startsWith('"') || token.startsWith("'")) {
        style = base.copyWith(color: palette.string);
      } else if (_isNumber(token)) {
        style = base.copyWith(color: palette.number);
      } else if (_isIdentifier(token)) {
        final lower = token.toLowerCase();
        if (_keywords.contains(lower)) {
          style = base.copyWith(
              color: palette.keyword, fontWeight: FontWeight.w600);
        } else if (_modules.contains(lower)) {
          style = base.copyWith(color: palette.type);
        } else if (_builtins.contains(lower)) {
          style = base.copyWith(color: palette.function);
        } else if (_isFunctionCall(text, m.end)) {
          style = base.copyWith(color: palette.function);
        } else if (_isType(token)) {
          style = base.copyWith(color: palette.type);
        } else {
          style = base.copyWith(color: palette.variable);
        }
      } else {
        style = base.copyWith(color: palette.operatorColor);
      }
      spans.add(TextSpan(text: token, style: style));
      last = m.end;
    }
    if (last < text.length) spans.add(TextSpan(text: text.substring(last)));
    return spans;
  }

  static bool _isNumber(String token) {
    if (token.isEmpty) return false;
    final c = token.codeUnitAt(0);
    return c >= 0x30 && c <= 0x39;
  }

  static bool _isIdentifier(String token) => _identPattern.hasMatch(token);
  static bool _isType(String token) => _typePattern.hasMatch(token);
  static bool _isFunctionCall(String text, int end) {
    var i = end;
    while (i < text.length && (text[i] == ' ' || text[i] == '\t')) {
      i++;
    }
    return i < text.length && text[i] == '(';
  }
}

// ============================================================================
// KÜÇÜK WIDGET'LAR
// ============================================================================

class _HGrip extends StatelessWidget {
  final ValueChanged<double> onDelta;
  const _HGrip(this.onDelta);
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.resizeColumn,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onHorizontalDragUpdate: (d) => onDelta(d.delta.dx),
        child: SizedBox(
          width: 8,
          height: double.infinity,
          child: Center(
            child: Container(
                width: 1, color: Theme.of(context).colorScheme.outlineVariant),
          ),
        ),
      ),
    );
  }
}

class _VGrip extends StatelessWidget {
  final ValueChanged<double> onDelta;
  const _VGrip(this.onDelta);
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.resizeRow,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onVerticalDragUpdate: (d) => onDelta(d.delta.dy),
        child: SizedBox(
          height: 8,
          width: double.infinity,
          child: Center(
            child: Container(
                height: 1, color: Theme.of(context).colorScheme.outlineVariant),
          ),
        ),
      ),
    );
  }
}

class _ToastBox extends StatelessWidget {
  final String msg;
  final SnackKind kind;
  final VoidCallback? onHistory;
  final VoidCallback? onClose;

  const _ToastBox({
    required this.msg,
    required this.kind,
    this.onHistory,
    this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final Color color;
    final IconData icon;

    switch (kind) {
      case SnackKind.success:
        color = Colors.green;
        icon = Icons.check_circle_outline;
        break;
      case SnackKind.error:
        color = theme.colorScheme.error;
        icon = Icons.error_outline;
        break;
      case SnackKind.info:
        color = theme.colorScheme.primary;
        icon = Icons.info_outline;
        break;
    }

    return ConstrainedBox(
      constraints: const BoxConstraints(
        minWidth: 340,
        maxWidth: 560,
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHigh,
          border: Border.all(color: theme.colorScheme.outline),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(width: 8),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Text(
                msg,
                style: TextStyle(
                  fontSize: 13,
                  height: 1.3,
                  color: theme.colorScheme.onSurface,
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              tooltip: 'Bildirimler',
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
              icon: const Icon(Icons.notifications_outlined, size: 15),
              onPressed: onHistory,
            ),
            IconButton(
              tooltip: 'Kapat',
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
              icon: const Icon(Icons.close, size: 15),
              onPressed: onClose,
            ),
          ],
        ),
      ),
    );
  }
}
class _ToastHistoryPanel extends StatelessWidget {
  final List<AppToast> items;
  final VoidCallback onClose;
  final VoidCallback onClear;

  const _ToastHistoryPanel({
    required this.items,
    required this.onClose,
    required this.onClear,
  });

  Color _color(BuildContext context, SnackKind kind) {
    final theme = Theme.of(context);

    switch (kind) {
      case SnackKind.success:
        return Colors.green;
      case SnackKind.error:
        return theme.colorScheme.error;
      case SnackKind.info:
        return theme.colorScheme.primary;
    }
  }

  IconData _icon(SnackKind kind) {
    switch (kind) {
      case SnackKind.success:
        return Icons.check_circle_outline;
      case SnackKind.error:
        return Icons.error_outline;
      case SnackKind.info:
        return Icons.info_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 460, maxHeight: 480),
      child: Container(
        width: 460,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHigh,
          border: Border.all(color: theme.colorScheme.outline),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(children: [
              Icon(
                Icons.notifications_outlined,
                size: 16,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(width: 6),
              Text(
                'Bildirimler',
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const Spacer(),
              TextButton(
                onPressed: onClear,
                child: const Text('Temizle'),
              ),
              IconButton(
                tooltip: 'Kapat',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.close, size: 16),
                onPressed: onClose,
              ),
            ]),
            Divider(height: 1, color: theme.colorScheme.outlineVariant),
            const SizedBox(height: 4),
            if (items.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  'Bildirim yok.',
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.onSurface.withOpacity(0.6),
                  ),
                ),
              )
            else
              Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  itemCount: items.length,
                  separatorBuilder: (_, __) => Divider(
                    height: 1,
                    color: theme.colorScheme.outlineVariant,
                  ),
                  itemBuilder: (c, i) {
                    final item = items[i];

                    return Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 8,
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            _icon(item.kind),
                            size: 16,
                            color: _color(c, item.kind),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.message,
                                  style: const TextStyle(
                                    fontSize: 13,
                                    height: 1.3,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  item.timeText,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: theme.colorScheme.onSurface
                                        .withOpacity(0.55),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
class ConnectionBanner extends StatelessWidget {
  const ConnectionBanner({super.key});
  @override
  Widget build(BuildContext context) {
    final conn = context.watch<ConnectionProvider>();
    if (conn.connected) return const SizedBox.shrink();
    final durdu = conn.durum == BackendDurum.durdu;
    final baslatiliyor = conn.durum == BackendDurum.baslatiliyor;
    final metin = baslatiliyor
        ? 'Backend yeniden başlatılıyor...'
        : durdu
            ? '${conn.sonHata ?? 'Backend çalışmıyor.'} '
                r'Ayrıntı: %LOCALAPPDATA%\TurKod\backend.log'
            : 'Backend bağlantısı yok; yeniden bağlanılıyor...';
    const yazi = TextStyle(color: Colors.white, fontSize: 13);
    return Container(
      width: double.infinity,
      color: Colors.red.shade700,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(children: [
        const Icon(Icons.cloud_off, size: 18, color: Colors.white),
        const SizedBox(width: 8),
        Expanded(
          child: Text(metin,
              style: yazi, maxLines: 3, overflow: TextOverflow.ellipsis),
        ),
        if (conn.yenidenBaslatilabilir && !baslatiliyor)
          TextButton.icon(
            onPressed: conn.yenidenBaslat,
            icon: const Icon(Icons.restart_alt, size: 18, color: Colors.white),
            label: const Text('Yeniden başlat', style: yazi),
          ),
      ]),
    );
  }
}

// ============================================================================
// SEKME ANİMASYONU (giriş + çıkış)
// ============================================================================

class _TabAnim extends StatefulWidget {
  final Widget child;
  final bool closing;
  final VoidCallback onClosed;
  // false: sekme zaten görüldü (tembel liste onu kaydırma sonrası yeniden
  // kuruyor) -> giriş animasyonu oynatılmaz, tam genişlikte başlar.
  final bool animateIn;
  const _TabAnim(
      {super.key,
      required this.child,
      required this.closing,
      required this.onClosed,
      this.animateIn = true});
  @override
  State<_TabAnim> createState() => _TabAnimState();
}

class _TabAnimState extends State<_TabAnim>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 160),
    value: 0,
  );
  // Tek sefer oluşturulur: build() içinde her seferinde yeni bir
  // CurvedAnimation yaratmak, ebeveyn controller'a dinleyici biriktiriyordu.
  late final CurvedAnimation _curve =
      CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);
  bool _closedFired = false;
  void _fireClosed() {
    if (_closedFired) return;
    _closedFired = true;
    WidgetsBinding.instance.addPostFrameCallback((_) => widget.onClosed());
  }

  @override
  void initState() {
    super.initState();
    // Not: build() içinde _c.status kontrolü yeterli değil, çünkü
    // FadeTransition/SizeTransition animasyonu kendi içinde dinler ve
    // State.build() bir daha tetiklenmeyebilir. Kapanışı garanti altına
    // almak için doğrudan status listener kullanıyoruz.
    _c.addStatusListener((status) {
      if (status == AnimationStatus.dismissed && widget.closing) _fireClosed();
    });
    if (widget.closing) {
      _c.value = 0;
      _fireClosed();
    } else if (widget.animateIn) {
      _c.forward();
    } else {
      _c.value = 1;
    }
  }

  @override
  void didUpdateWidget(covariant _TabAnim old) {
    super.didUpdateWidget(old);
    if (widget.closing && !old.closing) _c.reverse();
  }

  @override
  void dispose() {
    _curve.dispose();
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_closedFired) return const SizedBox.shrink();
    return FadeTransition(
      opacity: _curve,
      child: SizeTransition(
        axis: Axis.horizontal,
        sizeFactor: _curve,
        axisAlignment: -1,
        child: widget.child,
      ),
    );
  }
}

// ============================================================================
// BAŞLIK + MENÜ ÇUBUĞU
// ============================================================================

class _MenuBar extends StatelessWidget {
  final List<AppAction> actions;
  const _MenuBar({required this.actions});
  static const List<String> _groups = [
    'Dosya',
    'Düzenle',
    'Görünüm',
    'Çalıştır',
    'Araçlar',
    'Yardım',
    'Güncelleştirmeler'
  ];
  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      for (final g in _groups)
        PopupMenuButton<String>(
          tooltip: '',
          position: PopupMenuPosition.under,
          offset: const Offset(0, 2),
          color: Theme.of(context).colorScheme.surfaceContainerHigh,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(3),
            side: BorderSide(color: Theme.of(context).colorScheme.outline),
          ),
          onSelected: (id) {
            final a = findAction(actions, id);
            if (a != null) a.run(context);
          },
          itemBuilder: (c) => actions
              .where((a) => a.menu == g)
              .map((a) => PopupMenuItem<String>(
                    value: a.id,
                    height: 30,
                    child: Row(children: [
                      Text(a.label, style: const TextStyle(fontSize: 13)),
                      const SizedBox(width: 24),
                      Text(a.shortcut,
                          style: TextStyle(
                              fontSize: 11,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withOpacity(0.55))),
                    ]),
                  ))
              .toList(),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
            child: MouseRegion(
              cursor: SystemMouseCursors.click,
              child: Text(g, style: const TextStyle(fontSize: 13)),
            ),
          ),
        ),
    ]);
  }
}

class AppTitleBar extends StatelessWidget {
  final List<AppAction> actions;
  const AppTitleBar({super.key, required this.actions});
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      height: 36,
      color: theme.colorScheme.surfaceContainer,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      child: Row(children: [
        Icon(Icons.terminal_rounded,
            size: 16, color: theme.colorScheme.primary),
        const SizedBox(width: 6),
        Text('TürKod IDE',
            style: theme.textTheme.titleSmall
                ?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(width: 14),
        _MenuBar(actions: actions),
        const Spacer(),
        IconButton(
          tooltip: 'Ayarlar',
          visualDensity: VisualDensity.compact,
          icon: const Icon(Icons.settings_outlined, size: 17),
          onPressed: () => context.read<EditorProvider>().openSettings(),
        ),
      ]),
    );
  }
}

// ============================================================================
// ARAÇ ÇUBUĞU (renkli, satırın ortasında çivili)
// ============================================================================

class TopToolbar extends StatelessWidget {
  final List<AppAction> actions;
  const TopToolbar({super.key, required this.actions});
  static const List<String> _ids = [
    'file.open_file',
    'file.open',
    'file.save',
    'file.save_as',
    'run.run',
    'run.stop',
    'tools.convert',
    'tools.fix',
    'edit.find_replace',
    'view.palette',
    'run.debug_start',
    'run.debug_step',
    'run.debug_continue',
    'run.debug_stop',
    'view.explorer',
    'view.ai',
    'view.terminal',
  ];
  static const Map<String, Color> _colors = {
    'file.open_file': Color(0xFF4FC3F7),
    'file.open': Color(0xFFE8A33D),
    'file.save': Color(0xFF26A69A),
    'file.save_as': Color(0xFF26C6DA),
    'run.run': Color(0xFF66BB6A),
    'run.stop': Color(0xFFEF5350),
    'tools.convert': Color(0xFF5C6BC0),
    'tools.fix': Color(0xFFFFCA28),
    'edit.find_replace': Color(0xFFFFA726),
    'view.palette': Color(0xFFAB47BC),
    'run.debug_start': Color(0xFFEC407A),
    'run.debug_step': Color(0xFF42A5F5),
    'run.debug_continue': Color(0xFF9CCC65),
    'run.debug_stop': Color(0xFF8D6E63),
    'view.explorer': Color(0xFFD4E157),
    'view.ai': Color(0xFF7E57C2),
    'view.terminal': Color(0xFF90A4AE),
  };
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final widgets = <Widget>[];
    var lastGroup = '';
    for (final id in _ids) {
      final a = findAction(actions, id);
      if (a == null) continue;
      final group = id.split('.').first;
      if (lastGroup.isNotEmpty && group != lastGroup) {
        widgets.add(Padding(
          padding: const EdgeInsets.symmetric(horizontal: 5),
          child: SizedBox(
              height: 20,
              child: VerticalDivider(
                  width: 1, color: theme.colorScheme.outlineVariant)),
        ));
      }
      lastGroup = group;
      widgets.add(IconButton(
        tooltip: a.shortcut.isEmpty ? a.label : '${a.label} (${a.shortcut})',
        visualDensity: VisualDensity.compact,
        icon: Icon(a.icon,
            size: 17, color: _colors[id] ?? theme.colorScheme.onSurface),
        onPressed: () => a.run(context),
      ));
    }
    return Container(
      height: 38,
      color: theme.colorScheme.surfaceContainer,
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Center(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(mainAxisSize: MainAxisSize.min, children: widgets),
        ),
      ),
    );
  }
}

// ============================================================================
// DOSYA GEZGİNİ
// ============================================================================

class FileTreePanel extends StatelessWidget {
  const FileTreePanel({super.key});
  static const Color _folderColor = Color(0xFFE8A33D);
  Color _fileColor(String n) {
    final l = n.toLowerCase();
    if (l.endsWith('.trpy')) return const Color(0xFF4EC9B0);
    if (l.endsWith('.py')) return const Color(0xFF569CD6);
    if (l.endsWith('.dart')) return const Color(0xFF42A5F5);
    if (l.endsWith('.json')) return const Color(0xFFE5C07B);
    if (l.endsWith('.md')) return const Color(0xFF9E9E9E);
    if (l.endsWith('.txt')) return const Color(0xFFB0BEC5);
    if (l.endsWith('.png') ||
        l.endsWith('.jpg') ||
        l.endsWith('.jpeg') ||
        l.endsWith('.gif')) {
      return const Color(0xFF26A69A);
    }
    if (l.endsWith('.yaml') || l.endsWith('.yml'))
      return const Color(0xFFEF5350);
    return const Color(0xFF90A4AE);
  }

  Widget _buildNode(
      BuildContext ctx, FileNode node, int depth, String? activePath) {
    final tree = ctx.read<FileTreeProvider>();
    final isActive = !node.isDir && node.path == activePath;
    final theme = Theme.of(ctx);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () {
            if (node.isDir) {
              tree.toggleExpand(node);
            } else {
              ctx.read<EditorProvider>().openFile(node.path, context: ctx).catchError((e) {
                if (ctx.mounted) {
                  showAppSnackbar(ctx, 'Hata: $e', kind: SnackKind.error);
                }
              });
            }
          },
          child: Container(
            color: isActive
                ? theme.colorScheme.primary.withOpacity(0.14)
                : Colors.transparent,
            padding: EdgeInsets.only(
                left: 8.0 + depth * 14, right: 8, top: 4, bottom: 4),
            child: Row(children: [
              Icon(
                node.isDir
                    ? (node.expanded ? Icons.folder_open : Icons.folder)
                    : Icons.insert_drive_file,
                size: 16,
                color: node.isDir ? _folderColor : _fileColor(node.name),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(node.name,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight:
                            isActive ? FontWeight.w600 : FontWeight.normal)),
              ),
            ]),
          ),
        ),
      ),
      if (node.isDir && node.expanded)
        ...node.children.map((c) => _buildNode(ctx, c, depth + 1, activePath)),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final tree = context.watch<FileTreeProvider>();
    final conn = context.watch<ConnectionProvider>().connected;
    // Yalnızca aktif yol değişince yeniden çiz (her "kaydedilmedi" bayrağı
    // değişiminde tüm ağacı yeniden kurmaya gerek yok).
    final activePath =
        context.select<EditorProvider, String?>((e) => e.activeTab?.path);
    final theme = Theme.of(context);
    return Container(
      color: theme.colorScheme.surfaceContainer,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 6, 6),
          child: Row(children: [
            Expanded(
              child: Text('GEZGİN',
                  style: theme.textTheme.labelLarge
                      ?.copyWith(letterSpacing: 0.5, fontSize: 11)),
            ),
            IconButton(
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.folder_open, size: 16),
              onPressed: conn
                  ? () async {
                      final d = await FilePicker.platform.getDirectoryPath();
                      if (d != null && context.mounted) {
                        await context
                            .read<FileTreeProvider>()
                            .setProjectDirectory(d);
                      }
                    }
                  : null,
            ),
            IconButton(
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.refresh, size: 16),
              onPressed: conn ? tree.refresh : null,
            ),
          ]),
        ),
        Divider(height: 1, color: theme.colorScheme.outlineVariant),
        Expanded(
          child: !conn
              ? const Center(child: Text('Bağlantı Yok'))
              : tree.loading
                  ? const Center(
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : tree.errorMessage != null
                      ? Padding(
                          padding: const EdgeInsets.all(16),
                          child: Center(
                              child: Text(tree.errorMessage!,
                                  textAlign: TextAlign.center)),
                        )
                      : tree.root == null
                          ? const Center(child: Text('Klasör Seçin'))
                          : ListView(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              children: tree.root!.children
                                  .map((c) =>
                                      _buildNode(context, c, 0, activePath))
                                  .toList(),
                            ),
        ),
      ]),
    );
  }
}

// ============================================================================

class EditorTabsBar extends StatefulWidget {
  const EditorTabsBar({super.key});
  @override
  State<EditorTabsBar> createState() => _EditorTabsBarState();
}

class _EditorTabsBarState extends State<EditorTabsBar> {
  final Set<String> _closing = {};

  Future<void> _requestClose(EditorProvider ed, int i) async {
    if (i < 0 || i >= ed.tabs.length) return;
    final t = ed.tabs[i];

    if (_closing.contains(t.id)) return;

    if (t.dirty) {
      final a = await showDialog<String>(
        context: context,
        builder: (dc) => AlertDialog(
          title: const Text('Kapat'),
          content: Text('${t.name} kaydedilmemiş.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dc, 'c'),
              child: const Text('Vazgeç'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dc, 'x'),
              child: const Text('Kapat'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dc, 's'),
              child: const Text('Kaydet'),
            ),
          ],
        ),
      );

      if (!mounted) return;
      if (a != 'x' && a != 's') return;

      if (a == 's') {
        // Diyalog açıkken sekme sırası değişmiş olabilir: indeksi id ile
        // yeniden bul.
        final idx = ed.tabs.indexWhere((x) => x.id == t.id);
        if (idx < 0) return;
        try {
          await ed.saveTab(idx);
        } catch (e) {
          if (mounted) {
            showAppSnackbar(context, 'Kaydetme hatası: $e',
                kind: SnackKind.error);
          }
          return;
        }
        if (!mounted) return;
        // Adsız sekmede "Farklı Kaydet" iptal edildiyse sekme hâlâ
        // kaydedilmemiştir; içerik kaybolmasın diye kapatma.
        final saved = ed.tabs.where((x) => x.id == t.id);
        if (saved.isNotEmpty && saved.first.dirty) return;
      }
    }

    setState(() => _closing.add(t.id));
  }

  final ScrollController _scroll = ScrollController();
  // Sekme listesinin kapladığı alan (sürükleme sınırı için).
  final GlobalKey _listAreaKey = GlobalKey();
  final Map<String, GlobalKey> _tabKeys = {};
  // Giriş animasyonu oynatılmış sekmeler (bkz. _TabAnim.animateIn).
  final Set<String> _shown = {};
  String? _lastActiveId;

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  /// Fare tekerleği: dikey tekerlek hareketi sekmeleri yatay kaydırır
  /// (yatay tekerlek / touchpad da desteklenir). Olay başka bir kaydırılabilir
  /// alanla çakışmasın diye pointerSignalResolver'a kaydedilir.
  void _onPointerSignal(PointerSignalEvent e) {
    if (e is! PointerScrollEvent || !_scroll.hasClients) return;
    final pos = _scroll.position;
    if (pos.maxScrollExtent <= 0) return;
    GestureBinding.instance.pointerSignalResolver.register(e, (ev) {
      final s = ev as PointerScrollEvent;
      final d = s.scrollDelta.dx.abs() > s.scrollDelta.dy.abs()
          ? s.scrollDelta.dx
          : s.scrollDelta.dy;
      final target =
          (pos.pixels + d).clamp(pos.minScrollExtent, pos.maxScrollExtent);
      if (target != pos.pixels) _scroll.jumpTo(target);
    });
  }

  /// Aktif sekme değişince (yeni sekme, Ctrl+Tab, dosya açma) görünür alana
  /// kaydırılır; çok sekme varken aktif sekme ekran dışında kalmaz.
  void _revealActive(EditorProvider ed) {
    final id = ed.activeTab?.id;
    if (id == null || id == _lastActiveId) return;
    _lastActiveId = id;
    _revealTab(ed, id, 6);
    // Yeni açılan sekme giriş animasyonuyla (160 ms) sıfır genişlikten
    // büyür; ilk karede kaydırılacak alan henüz yoktur. Animasyon bitince
    // bir kez daha hizala.
    Future.delayed(const Duration(milliseconds: 200), () {
      if (mounted && ed.activeTab?.id == id) _revealTab(ed, id, 6);
    });
  }

  void _revealTab(EditorProvider ed, String id, int retries) {
    // Kare planlı değilse (ör. gecikmeli çağrı) geri çağrı hiç çalışmazdı.
    WidgetsBinding.instance.ensureVisualUpdate();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scroll.hasClients || retries <= 0) return;
      final pos = _scroll.position;
      final ctx = _tabKeys[id]?.currentContext;
      final box = ctx?.findRenderObject();
      double? target;
      if (box is RenderBox && box.attached) {
        final viewport = RenderAbstractViewport.maybeOf(box);
        if (viewport == null) return;
        // 0: sekme sol kenarda, 1: sekme sağ kenarda olacak ofsetler.
        final start = viewport.getOffsetToReveal(box, 0).offset;
        final end = viewport.getOffsetToReveal(box, 1).offset;
        if (pos.pixels > start) {
          target = start;
        } else if (pos.pixels < end) {
          target = end;
        } else {
          return; // tamamen görünür
        }
      } else {
        // Liste tembel kurulur: ekran dışındaki sekme henüz oluşturulmamış
        // olabilir. Tahmini konuma atla; sonraki karede kesin hizalanır.
        final idx = ed.tabs.indexWhere((t) => t.id == id);
        if (idx < 0 || ed.tabs.length < 2) return;
        target = pos.maxScrollExtent * idx / (ed.tabs.length - 1);
      }
      final clamped = target.clamp(pos.minScrollExtent, pos.maxScrollExtent);
      if ((clamped - pos.pixels).abs() > 0.5) _scroll.jumpTo(clamped);
      // Liste uzunluğu tahminiydi ya da hedef sınırın ötesindeydi: bir sonraki
      // karede tekrar kontrol et.
      _revealTab(ed, id, retries - 1);
    });
  }

  Widget _buildTab(
      BuildContext context, EditorProvider ed, ThemeData theme, int i) {
    final t = ed.tabs[i];
    final active = i == ed.activeIndex;
    final closing = _closing.contains(t.id);
    final key = _tabKeys.putIfAbsent(t.id, () => GlobalKey());

    return _TabAnim(
      key: ValueKey(t.id),
      closing: closing,
      animateIn: _shown.add(t.id),
      onClosed: () {
        if (!mounted) return;

        final idx = ed.tabs.indexWhere((x) => x.id == t.id);

        setState(() {
          _closing.remove(t.id);
          _tabKeys.remove(t.id);
          _shown.remove(t.id);
        });

        if (idx >= 0) ed.closeTab(idx);
        // Kapanan sekmenin breakpoint'leri unutulur; hata ayıklanan sekme
        // kapandıysa oturum da durdurulur.
        if (idx >= 0 && !ed.tabs.any((x) => x.id == t.id)) {
          final bp = context.read<BreakpointProvider>();
          if (bp.debugTabId == t.id && bp.debugging) bp.stop();
          bp.forgetTab(t.id);
        }
      },
      child: MouseRegion(
        key: key,
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: closing ? null : () => ed.setActive(i),
          child: Container(
            margin: const EdgeInsets.only(top: 7, bottom: 7, right: 2),
            padding: const EdgeInsets.symmetric(horizontal: 10.5),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainer,
              borderRadius: BorderRadius.circular(3),
              border: Border.all(
                color: active
                    ? theme.colorScheme.primary
                    : theme.colorScheme.outlineVariant,
              ),
            ),
            child: Row(children: [
              Text(
                t.name,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: active ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
              if (t.dirty)
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Container(
                    width: 6,
                    height: 6,
                    decoration: const BoxDecoration(
                      color: Colors.amber,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              const SizedBox(width: 8),
              MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: closing ? null : () => _requestClose(ed, i),
                  child: const Icon(Icons.close, size: 12),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ed = context.watch<EditorProvider>();
    final theme = Theme.of(context);
    _revealActive(ed);

    // Sekme yüksekliği = çubuk yüksekliği - üst/alt boşluk (7 + 7) = 33.
    // Yatay kaydırma çubuğu alttaki 7 px'lik boşlukta durur; sekmelerin
    // üzerine binmez.
    return Container(
      height: 47,
      padding: EdgeInsets.zero,
      color: theme.colorScheme.surfaceContainer,
      child: Row(children: [
        Expanded(
          key: _listAreaKey,
          child: Listener(
            onPointerSignal: _onPointerSignal,
            child: ScrollConfiguration(
              // Masaüstünde otomatik eklenen ikinci kaydırma çubuğunu kapat.
              behavior:
                  ScrollConfiguration.of(context).copyWith(scrollbars: false),
              child: RawScrollbar(
                controller: _scroll,
                thumbVisibility: true,
                thickness: 4,
                radius: const Radius.circular(2),
                mainAxisMargin: 2,
                crossAxisMargin: 1,
                interactive: true,
                thumbColor: theme.colorScheme.onSurface.withOpacity(0.28),
                child: ReorderableListView.builder(
                  scrollController: _scroll,
                  scrollDirection: Axis.horizontal,
                  buildDefaultDragHandles: false,
                  itemCount: ed.tabs.length,
                  // Sürüklenen sekme: hafif gölgeli, şeffaf yüzey.
                  proxyDecorator: (child, index, animation) => Material(
                    type: MaterialType.transparency,
                    elevation: 4,
                    shadowColor: Colors.black54,
                    child: child,
                  ),
                  // Sürüklenen sekme sekme çubuğunun dışına (hatta pencerenin
                  // ötesine) taşıp kaybolabiliyordu: artık sekme alanının
                  // sınırları içinde tutuluyor. Kenara dayandığında liste
                  // yine otomatik kayar.
                  dragBoundaryProvider: (_) =>
                      _TabDragBoundary.of(_listAreaKey),
                  onReorder: (from, to) {
                    // ReorderableListView, öğe sağa taşınırken hedefi
                    // "eski konum çıkarılmadan önceki" indeksle verir.
                    if (to > from) to -= 1;
                    ed.moveTab(from, to);
                  },
                  itemBuilder: (ctx, i) {
                    final t = ed.tabs[i];
                    // Sol tıkla sürükleyince yer değiştirir; kısa tık yine
                    // sekmeyi seçer (sürükleme ancak hareket eşiği aşılınca
                    // başlar).
                    return ReorderableDragStartListener(
                      key: ValueKey('tab-${t.id}'),
                      index: i,
                      enabled: !_closing.contains(t.id),
                      child: _buildTab(ctx, ed, theme, i),
                    );
                  },
                ),
              ),
            ),
          ),
        ),
        IconButton(
          tooltip: 'Yeni Sekme (Ctrl+T)',
          visualDensity: VisualDensity.compact,
          icon: const Icon(Icons.add, size: 16),
          onPressed: () => ed.createUntitled(context: context),
        ),
      ]),
    );
  }
}

/// Sürüklenen sekmeyi sekme alanının içinde tutar (genel/global koordinat).
///
/// Flutter'ın hazır `DragBoundary` temsilcisi, sürüklenen öğe sınırdan
/// genişse (çok uzun dosya adı / dar pencere) hata fırlatıyor; bu sürüm o
/// durumda öğeyi sol kenara hizalar.
class _TabDragBoundary extends DragBoundaryDelegate<Rect> {
  final Rect bounds;
  _TabDragBoundary(this.bounds);

  static _TabDragBoundary? of(GlobalKey key) {
    final box = key.currentContext?.findRenderObject();
    if (box is! RenderBox || !box.hasSize || !box.attached) return null;
    final topLeft = box.localToGlobal(Offset.zero);
    return _TabDragBoundary(topLeft & box.size);
  }

  @override
  bool isWithinBoundary(Rect r) =>
      r.left >= bounds.left &&
      r.right <= bounds.right &&
      r.top >= bounds.top &&
      r.bottom <= bounds.bottom;

  @override
  Rect nearestPositionWithinBoundary(Rect r) {
    final maxLeft = math.max(bounds.left, bounds.right - r.width);
    final maxTop = math.max(bounds.top, bounds.bottom - r.height);
    return Rect.fromLTWH(
      r.left.clamp(bounds.left, maxLeft).toDouble(),
      r.top.clamp(bounds.top, maxTop).toDouble(),
      r.width,
      r.height,
    );
  }
}

// ============================================================================
// GUTTER (breakpoint + fold ikonları)
// ============================================================================

class EditorGutter extends StatelessWidget {
  final ScrollController controller;
  final int lineCount;
  final Set<int> breakpoints;
  final int? currentLine;
  final ValueChanged<int> onToggle;
  final ValueChanged<int> onFoldTap;
  final Map<int, String> foldIcons;
  final double lineHeight;
  final double fontSize;
  const EditorGutter({
    super.key,
    required this.controller,
    required this.lineCount,
    required this.breakpoints,
    required this.currentLine,
    required this.onToggle,
    required this.onFoldTap,
    required this.foldIcons,
    required this.lineHeight,
    required this.fontSize,
  });
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final double heightRatio = fontSize <= 0 ? 1.4 : lineHeight / fontSize;
    final numberStrut = StrutStyle(
      fontFamily: kMonoFontFamily,
      fontFamilyFallback: kMonoFontFallback,
      fontSize: fontSize,
      height: heightRatio,
      forceStrutHeight: true,
      leadingDistribution: TextLeadingDistribution.even,
    );
    return Container(
      width: 60,
      color: theme.colorScheme.surfaceContainer,
      child: ScrollConfiguration(
        behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
        child: ListView.builder(
          controller: controller,
          physics: const NeverScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: lineCount,
          itemExtent: lineHeight,
          itemBuilder: (ctx, i) {
            final line = i + 1;
            final hasBp = breakpoints.contains(line);
            final isCur = currentLine == line;
            final fold = foldIcons[line];
            return MouseRegion(
              cursor: SystemMouseCursors.click,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => fold != null ? onFoldTap(line) : onToggle(line),
                child: Container(
                  height: lineHeight,
                  color: isCur
                      ? Colors.amber.withOpacity(0.16)
                      : Colors.transparent,
                  child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(
                          width: 14,
                          child: Center(
                            child: fold != null
                                ? Text(fold,
                                    style: TextStyle(
                                        fontSize: fontSize,
                                        color: theme.colorScheme.onSurface
                                            .withOpacity(0.7)))
                                : const SizedBox.shrink(),
                          ),
                        ),
                        SizedBox(
                          width: 12,
                          child: Center(
                            child: Container(
                              width: 9,
                              height: 9,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: isCur
                                    ? Colors.amber
                                    : hasBp
                                        ? Colors.redAccent
                                        : Colors.transparent,
                              ),
                            ),
                          ),
                        ),
                        Expanded(
                          child: SizedBox(
                            height: lineHeight,
                            child: Align(
                              alignment: Alignment.topRight,
                              child: Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: Text('$line',
                                    textAlign: TextAlign.right,
                                    style: TextStyle(
                                        fontFamily: kMonoFontFamily,
                                        fontFamilyFallback: kMonoFontFallback,
                                        fontSize: fontSize,
                                        height: heightRatio,
                                      color: theme.colorScheme.onSurface
                                        .withOpacity(0.72)),
                                    strutStyle: numberStrut,
                                    textScaler: TextScaler.noScaling),
                              ),
                            ),
                          ),
                        ),
                      ]),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

// ============================================================================
// MİNİMAP
// ============================================================================

class _MinimapPainter extends CustomPainter {
  final List<String> lines;
  final double scrollOffset;
  final double maxScrollExtent;
  final double viewportHeight;
  final TextStyle textStyle;
  final AppSyntaxPalette syntax;
  final Color textColor;
  final Color viewColor;
  final Color viewBorderColor;
  // Gerçek kod editörlerindeki minimap'lerin yaptığı gibi: satır yüksekliği
  // dosya uzunluğundan BAĞIMSIZ, sabit ve küçük bir değerdir. Kısa bir
  // dosyada bu, önizlemenin sadece üst kısmı kaplayıp geri kalanını boş
  // bırakması demektir (eskiden `per = size.height / lines.length` ile
  // satırlar tüm alana zorla geriliyor, 4 satırlık bir dosya bile koca bir
  // tek renkli bloğa dönüşüyordu).
  static const double _targetPer = 9.0;
  static const double _minPer = 4.0;

  static double perFor(int lineCount, double height) {
    if (lineCount <= 0) return 0;
    if (lineCount * _targetPer <= height) return _targetPer;
    return math.max(_minPer, height / lineCount);
  }

  static double contentHeightFor(int lineCount, double height) =>
      math.max(height, lineCount * perFor(lineCount, height));

  /// Minimap içeriğinin kendi kaydırma ofseti (editör kaydırmasıyla orantılı).
  static double minimapScrollFor(
      int lineCount, double height, double scrollOffset, double maxScroll) {
    final overflow = contentHeightFor(lineCount, height) - height;
    if (overflow <= 0 || maxScroll <= 0) return 0;
    return overflow * (scrollOffset / maxScroll).clamp(0.0, 1.0);
  }
  _MinimapPainter({
    required this.lines,
    required this.scrollOffset,
    required this.maxScrollExtent,
    required this.viewportHeight,
    required this.textStyle,
    required this.syntax,
    required this.textColor,
    required this.viewColor,
    required this.viewBorderColor,
  });
  @override
  void paint(Canvas canvas, Size size) {
    if (lines.isEmpty) return;
    final per = perFor(lines.length, size.height);
    final contentHeight = contentHeightFor(lines.length, size.height);
    final minimapStyle = textStyle.copyWith(
      fontSize: math.max(5.5, math.min(7.0, per * 2.2)),
      height: 1.0,
    );
    // Uzun dosyada minimap içeriği yüksekliği aşar: VS Code'daki gibi
    // minimap de editörle orantılı kayar ve YALNIZCA görünen satırlar dizilir
    // (eskiden 20.000 satırın hepsi her kaydırma karesinde diziliyordu).
    final mmScroll = minimapScrollFor(
        lines.length, size.height, scrollOffset, maxScrollExtent);
    final first = (mmScroll / per).floor().clamp(0, lines.length).toInt();
    final last =
        ((mmScroll + size.height) / per).ceil().clamp(0, lines.length).toInt();
    for (var i = first; i < last; i++) {
      final raw = lines[i];
      final y = i * per - mmScroll;
      if (raw.trim().isEmpty) continue;
      final painter = TextPainter(
        text: TextSpan(
          style: minimapStyle,
          children: SyntaxHighlightingController._tokenize(
            raw,
            syntax,
            minimapStyle,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
        textScaler: TextScaler.noScaling,
      )..layout(maxWidth: math.max(1, size.width - 4));
      painter.paint(
        canvas,
        Offset(2, y + math.max(0, (per - painter.height) / 2)),
      );
      painter.dispose();
    }
    // Görünen alan göstergesi (mavi çerçeve) yalnızca dosyanın tamamı zaten
    // tek ekrana sığmıyorsa çizilir; aksi halde küçük bir içerik bloğunun
    // tamamını kaplayan anlamsız bir dikdörtgen olurdu.
    if (contentHeight > 0) {
      final total = maxScrollExtent + viewportHeight;
      final vh = total <= 0
          ? contentHeight
          : (contentHeight * viewportHeight / total)
              .clamp(math.min(per, contentHeight), contentHeight)
              .toDouble();
      final fraction = maxScrollExtent <= 0
          ? 0.0
          : (scrollOffset / maxScrollExtent).clamp(0.0, 1.0);
      final y = (contentHeight - vh) * fraction - mmScroll;
      final rect = Rect.fromLTWH(0.5, y, size.width - 1, vh);
      canvas.drawRect(rect, Paint()..color = viewColor);
      canvas.drawRect(
        rect,
        Paint()
          ..color = viewBorderColor
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _MinimapPainter old) =>
      old.lines.length != lines.length ||
      old.scrollOffset != scrollOffset ||
      old.maxScrollExtent != maxScrollExtent ||
      old.viewportHeight != viewportHeight ||
      old.textStyle != textStyle ||
      old.syntax != syntax ||
      !identical(old.lines, lines);
}

class _EditorIndicatorPainter extends CustomPainter {
  final ValueNotifier<re.CodeIndicatorValue?> notifier;
  re.CodeIndicatorValue? get value => notifier.value;
  final Set<int> breakpoints;
  final int? currentLine;
  final Map<int, String> foldIcons;
  final Color normalColor;
  final Color breakpointColor;
  final Color currentColor;
  final double fontSize;

  _EditorIndicatorPainter({
    required this.notifier,
    required this.breakpoints,
    required this.currentLine,
    required this.foldIcons,
    required this.normalColor,
    required this.breakpointColor,
    required this.currentColor,
    required this.fontSize,
  }) : super(repaint: notifier);

  @override
  void paint(Canvas canvas, Size size) {
    final paragraphs = value?.paragraphs;
    if (paragraphs == null) return;
    for (final paragraph in paragraphs) {
      final line = paragraph.index + 1;
      final center =
          Offset(size.width / 2, paragraph.top + paragraph.height / 2);
      if (breakpoints.contains(line) || currentLine == line) {
        canvas.drawCircle(
          center,
          4,
          Paint()..color = currentLine == line ? currentColor : breakpointColor,
        );
      }
      final fold = foldIcons[line];
      if (fold != null) {
        final painter = TextPainter(
          text: TextSpan(
            text: fold,
            style: TextStyle(fontSize: fontSize, color: normalColor),
          ),
          textDirection: TextDirection.ltr,
          textScaler: TextScaler.noScaling,
        )..layout(maxWidth: size.width);
        painter.paint(
          canvas,
          Offset((size.width - painter.width) / 2, paragraph.top),
        );
        painter.dispose();
      }
    }
  }

  @override
  bool shouldRepaint(covariant _EditorIndicatorPainter old) =>
      old.notifier != notifier ||
      old.breakpoints != breakpoints ||
      old.currentLine != currentLine ||
      old.foldIcons != foldIcons ||
      old.normalColor != normalColor ||
      old.breakpointColor != breakpointColor ||
      old.currentColor != currentColor ||
      old.fontSize != fontSize;
}

class Minimap extends StatelessWidget {
  final List<String> lines;
  final ScrollController textScroll;
  const Minimap({super.key, required this.lines, required this.textScroll});
  void _jump(double localY, double height) {
    if (!textScroll.hasClients || height <= 0) return;
    final contentH = _MinimapPainter.contentHeightFor(lines.length, height);
    if (contentH <= 0) return;
    final viewport = textScroll.position.viewportDimension;
    final maxScroll = textScroll.position.maxScrollExtent;
    final total = maxScroll + viewport;
    final viewportRatio = total <= 0 ? 1.0 : viewport / total;
    // Ekrandaki y, minimap içerik koordinatına çevrilir (minimap kayıyorsa).
    final contentY = localY +
        _MinimapPainter.minimapScrollFor(
            lines.length, height, textScroll.offset, maxScroll);
    final target = (contentY - contentH * viewportRatio / 2)
        .clamp(0.0, contentH)
        .toDouble();
    final movable = contentH * (1 - viewportRatio);
    final fraction = movable <= 0 ? 0.0 : target / movable;
    textScroll.jumpTo(fraction.clamp(0.0, 1.0) * maxScroll);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final syntax = theme.extension<AppSyntaxPalette>();
    return Container(
      width: 90,
      color: theme.colorScheme.surfaceContainer,
      child: AnimatedBuilder(
        animation: textScroll,
        builder: (context, _) => LayoutBuilder(builder: (c, con) {
          final h = con.maxHeight;
          final extent =
              textScroll.hasClients ? textScroll.position.maxScrollExtent : 0.0;
          final off = textScroll.hasClients ? textScroll.offset : 0.0;
          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onVerticalDragUpdate: (d) => _jump(d.localPosition.dy, h),
            onTapDown: (d) => _jump(d.localPosition.dy, h),
            child: CustomPaint(
              size: Size(90, h),
              painter: _MinimapPainter(
                lines: lines,
                scrollOffset: off,
                maxScrollExtent: extent,
                viewportHeight: h,
                textStyle: const TextStyle(
                  fontFamily: kMonoFontFamily,
                  fontFamilyFallback: kMonoFontFallback,
                  fontSize: 7,
                ),
                syntax: syntax ?? AppSyntaxPalette.fallback,
                textColor: theme.colorScheme.onSurface.withOpacity(0.62),
                viewColor: theme.colorScheme.primary.withOpacity(0.14),
                viewBorderColor: theme.colorScheme.primary.withOpacity(0.4),
              ),
            ),
          );
        }),
      ),
    );
  }
}

// ============================================================================
// BUL / DEĞİŞTİR
// ============================================================================

class FindWidget extends StatefulWidget {
  final Size bounds;
  const FindWidget({super.key, required this.bounds});
  @override
  State<FindWidget> createState() => _FindWidgetState();
}

class _FindWidgetState extends State<FindWidget> {
  final _fc = TextEditingController();
  final _rc = TextEditingController();
  final _focus = FocusNode();
  String _info = '';
  String? _lastInfoQuery;
  String? _lastInfoText;
  int _seenFocusTick = -1;
  @override
  void initState() {
    super.initState();
    _fc.addListener(_updateInfo);
  }

  /// Ctrl+F / Ctrl+H her basıldığında (kutu zaten açık olsa bile) odağı
  /// arama kutusuna alır ve içeriği seçer; editör odaktayken `autofocus`
  /// tek başına odağı devralmıyordu.
  void _handleFocusRequest(int tick) {
    if (tick == _seenFocusTick) return;
    _seenFocusTick = tick;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final seed = context.read<UiProvider>().consumeFindSeed();
      if (seed != null && seed.isNotEmpty) _fc.text = seed;
      _focus.requestFocus();
      _fc.selection =
          TextSelection(baseOffset: 0, extentOffset: _fc.text.length);
    });
  }

  @override
  void dispose() {
    _fc.removeListener(_updateInfo);
    _fc.dispose();
    _rc.dispose();
    _focus.dispose();
    super.dispose();
  }

  TextEditingController? get _ed => context.read<EditorProvider>().uiController;

  /// Bulunan bir eşleşmeyi [c] üzerine PROGRAMATIK olarak uygular. Eskiden
  /// bu ham `c.value =`/`c.selection =` atamasıydı; fold-koruması bazen
  /// bunu sessizce iptal ediyordu (eşleşme hiç görünmüyor ya da normal
  /// metin seçimiyle karışıyordu). Ayrıca gerçek editöre (re.CodeEditor)
  /// yansıması için senkronizasyon da gerekir.
  void _applyProgrammatic(TextEditingController c, TextEditingValue v) {
    if (c is SyntaxHighlightingController) {
      c.setProgrammaticValue(v);
    } else {
      c.value = v;
    }
  }

  void _updateInfo() {
    final t = _ed?.text ?? '';
    final q = _fc.text;
    // Dinleyici imleç/seçim hareketlerinde de tetiklenir; sorgu ve metin
    // aynıysa tüm metni yeniden taramaya gerek yok.
    if (q == _lastInfoQuery && identical(t, _lastInfoText)) return;
    _lastInfoQuery = q;
    _lastInfoText = t;
    context.read<UiProvider>().setFindQuery(q);
    if (q.isEmpty) {
      setState(() => _info = '');
      return;
    }
    // NOT: Türkçe İ/I/ı/i karışıklığından kaçınmak için AYNI eşleştirme
    // mantığı (SyntaxHighlightingController.findAllMatches) kullanılıyor;
    // böylece buradaki sayaç, editördeki vurgulanan eşleşme sayısıyla
    // HER ZAMAN birebir tutarlı.
    final n = SyntaxHighlightingController.findAllMatches(t, q).length;
    setState(() => _info = '$n eşleşme');
  }

  void _next({bool back = false, bool inclusive = false}) {
    final c = _ed;
    final q = _fc.text;
    if (c == null || q.isEmpty) return;
    final t = c.text;
    final matches = SyntaxHighlightingController.findAllMatches(t, q);
    if (matches.isEmpty) {
      setState(() => _info = 'Bulunamadı');
      return;
    }
    final curStart = c.selection.isValid ? c.selection.start : -1;
    List<int> target;
    if (back) {
      target = matches.lastWhere((m) => m[0] < curStart,
          orElse: () => matches.last);
    } else {
      // inclusive: değiştirmeden sonra imlecin hemen bitişiğindeki eşleşme
      // de sayılır ("ababab" içinde art arda değiştirmede biri atlanıyordu).
      target = matches.firstWhere(
          (m) => inclusive ? m[0] >= curStart : m[0] > curStart,
          orElse: () => matches.first);
    }
    _applyProgrammatic(
      c,
      TextEditingValue(
        text: t,
        selection: TextSelection(baseOffset: target[0], extentOffset: target[1]),
      ),
    );
    setState(() => _info = '${matches.length} eşleşme');
  }

  void _replaceOne() {
    final c = _ed;
    final q = _fc.text;
    final r = _rc.text;
    if (c == null || q.isEmpty) return;
    final sel = c.selection;
    if (sel.isValid &&
        sel.start != sel.end &&
        SyntaxHighlightingController.findAllMatches(
                c.text.substring(sel.start, sel.end), q)
            .isNotEmpty &&
        (sel.end - sel.start) == q.length) {
      final nt = c.text.replaceRange(sel.start, sel.end, r);
      _applyProgrammatic(
        c,
        TextEditingValue(
          text: nt,
          selection: TextSelection.collapsed(offset: sel.start + r.length),
        ),
      );
      context.read<EditorProvider>().syncFromView();
      _next(inclusive: true);
      return;
    }
    _next();
  }

  void _replaceAll() {
    final c = _ed;
    final q = _fc.text;
    final r = _rc.text;
    if (c == null || q.isEmpty) return;
    // Katlı bölgeler önce açılır: hem gizli koddaki eşleşmeler de
    // değiştirilir, hem de yer tutucu satırlarına dokunan değişiklik
    // reddedilip yine de "değiştirildi" denmez.
    context.read<EditorProvider>().unfoldAll?.call();
    final matches = SyntaxHighlightingController.findAllMatches(c.text, q);
    if (matches.isEmpty) {
      setState(() => _info = 'Bulunamadı');
      return;
    }
    // Sondan başa doğru değiştir: daha önceki eşleşmelerin offsetlerini
    // bozmadan ilerlemenin en güvenli yolu budur.
    var nt = c.text;
    for (final m in matches.reversed) {
      nt = nt.replaceRange(m[0], m[1], r);
    }
    _applyProgrammatic(
      c,
      TextEditingValue(text: nt, selection: const TextSelection.collapsed(offset: 0)),
    );
    context.read<EditorProvider>().syncFromView();
    setState(() => _info = c.text == nt
        ? '${matches.length} adet değiştirildi'
        : 'Değiştirilemedi');
  }

  @override
  Widget build(BuildContext context) {
    // UiProvider'ı tümüyle izlemek, her imleç hareketinde (setCursor) bu
    // kutuyu yeniden kurduruyordu; yalnızca ilgili alanlar izleniyor.
    final ui = context.read<UiProvider>();
    final findOffset = context.select<UiProvider, Offset>((u) => u.findOffset);
    final replaceMode =
        context.select<UiProvider, bool>((u) => u.findReplaceMode);
    _handleFocusRequest(
        context.select<UiProvider, int>((u) => u.findFocusTick));
    final theme = Theme.of(context);
    final defaultOffset = Offset(
        (widget.bounds.width - 356).clamp(0, widget.bounds.width).toDouble(),
        6);
    final offset = findOffset == Offset.zero ? defaultOffset : findOffset;
    return Positioned(
      left: offset.dx,
      top: offset.dy,
      child: Focus(
        onKeyEvent: (node, event) {
          if (event is KeyDownEvent &&
              event.logicalKey == LogicalKeyboardKey.escape) {
            ui.closeFind();
            return KeyEventResult.handled;
          }
          return KeyEventResult.ignored;
        },
        child: Container(
          width: 350,
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHigh,
            border: Border.all(color: theme.colorScheme.outlineVariant),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onPanUpdate: (d) {
                final cur = ui.findOffset;
                var base = cur == Offset.zero ? defaultOffset : cur;
                base = base + d.delta;
                final dx = base.dx.clamp(
                    0.0,
                    (widget.bounds.width - 350)
                        .clamp(0.0, widget.bounds.width));
                final dy = base.dy.clamp(
                    0.0,
                    (widget.bounds.height - 110)
                        .clamp(0.0, widget.bounds.height));
                ui.setFindOffset(Offset(dx.toDouble(), dy.toDouble()));
              },
              child: MouseRegion(
                cursor: SystemMouseCursors.grab,
                child: SizedBox(
                  height: 16,
                  child: Row(children: [
                    const Icon(Icons.drag_indicator, size: 12),
                    const SizedBox(width: 6),
                    const Text('Bul / Değiştir',
                        style: TextStyle(fontSize: 11)),
                    const Spacer(),
                    MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: GestureDetector(
                        onTap: () => ui.closeFind(),
                        child: const Icon(Icons.close, size: 12),
                      ),
                    ),
                  ]),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _fc,
                  focusNode: _focus,
                  autofocus: true,
                  style: const TextStyle(fontSize: 12),
                  decoration:
                      const InputDecoration(hintText: 'Bul', isDense: true),
                  // Enter: sonraki eşleşme; odak kutuda kalır (varsayılan
                  // davranış odağı bırakıyordu). Sayaç güncellemesi _fc
                  // dinleyicisinde yapılır (eskiden onChanged ile çift
                  // tarama yapılıyordu).
                  onEditingComplete: () {},
                  onSubmitted: (_) {
                    _next();
                    _focus.requestFocus();
                  },
                ),
              ),
              IconButton(
                tooltip: 'Önceki',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.arrow_upward, size: 14),
                onPressed: () => _next(back: true),
              ),
              IconButton(
                tooltip: 'Sonraki',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.arrow_downward, size: 14),
                onPressed: _next,
              ),
            ]),
            if (replaceMode) ...[
              const SizedBox(height: 4),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _rc,
                    style: const TextStyle(fontSize: 12),
                    decoration: const InputDecoration(
                        hintText: 'Değiştir', isDense: true),
                  ),
                ),
                IconButton(
                  tooltip: 'Değiştir',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.find_replace, size: 14),
                  onPressed: _replaceOne,
                ),
                IconButton(
                  tooltip: 'Tümünü Değiştir',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.done_all, size: 14),
                  onPressed: _replaceAll,
                ),
              ]),
            ],
            if (_info.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(_info, style: const TextStyle(fontSize: 10))),
              ),
          ]),
        ),
      ),
    );
  }
}

// ============================================================================
// KOD EDİTÖRÜ (fold + minimap + otomatik parantez + zoom)
// ============================================================================

/// Katlanmış görünümde bir metin düzenlemesinden sonra katlama yer
/// tutucularının yeni satırlarını hesaplar (saf fonksiyon; birim testli).
///
/// [harita]: görünüm satırı (0 tabanlı) -> katlama kimliği.
/// [yerTutucu]: kimliğin yer tutucu satır metni (yoksa null).
///
/// Değişen bölge iki hizalamayla denenir: önce ortak başlangıç, sonra ortak
/// son. Yer tutucunun hemen önüne tam satır eklemek (katlı bloğun başlık
/// satırının sonunda Enter) ilk hizalamada yer tutucuya "dokunmuş" görünür;
/// ikincisinde görünmez. Yeni metinde doğrulanan ilk sonuç döner. Hiçbiri
/// geçerli değilse harita null'dır ve [dokunulan] düzenlemenin dokunduğu
/// katlamaları içerir.
({Map<int, int>? harita, List<int> dokunulan}) katlamaHaritasiniKaydir(
  Map<int, int> harita,
  String eski,
  String yeni,
  String? Function(int id) yerTutucu,
) {
  int satirSay(String t, int son) {
    var n = 0;
    for (var i = t.indexOf('\n'); i >= 0 && i < son; i = t.indexOf('\n', i + 1)) {
      n++;
    }
    return n;
  }

  bool gecerli(Map<int, int> h) {
    final lines = yeni.split('\n');
    if (h.length != harita.length) return false;
    for (final e in h.entries) {
      final y = yerTutucu(e.value);
      if (y == null || e.key < 0 || e.key >= lines.length) return false;
      if (lines[e.key] != y) return false;
    }
    return true;
  }

  final minLen = math.min(eski.length, yeni.length);
  final delta = satirSay(yeni, yeni.length) - satirSay(eski, eski.length);
  var dokunulanIlk = const <int>[];
  for (final sondanOnce in [false, true]) {
    var p = 0;
    var s = 0;
    if (!sondanOnce) {
      while (p < minLen && eski.codeUnitAt(p) == yeni.codeUnitAt(p)) {
        p++;
      }
      while (s < minLen - p &&
          eski.codeUnitAt(eski.length - 1 - s) ==
              yeni.codeUnitAt(yeni.length - 1 - s)) {
        s++;
      }
    } else {
      while (s < minLen &&
          eski.codeUnitAt(eski.length - 1 - s) ==
              yeni.codeUnitAt(yeni.length - 1 - s)) {
        s++;
      }
      while (p < minLen - s && eski.codeUnitAt(p) == yeni.codeUnitAt(p)) {
        p++;
      }
    }
    final basSatir = satirSay(eski, p);
    final bitSatir = satirSay(eski, eski.length - s);
    final sonuc = <int, int>{};
    final dokunulan = <int>[];
    harita.forEach((satir, id) {
      if (satir < basSatir) {
        sonuc[satir] = id;
      } else if (satir > bitSatir) {
        sonuc[satir + delta] = id;
      } else {
        dokunulan.add(id);
      }
    });
    if (dokunulan.isEmpty) {
      if (gecerli(sonuc)) return (harita: sonuc, dokunulan: const <int>[]);
    } else if (dokunulanIlk.isEmpty) {
      dokunulanIlk = dokunulan;
    }
  }
  return (harita: null, dokunulan: dokunulanIlk);
}

class _Fold {
  final int id;
  final int startModel;
  final int endModel;
  final String hidden;
  final int lineCount;
  // Yer tutucu satırın girintisi: katlanan gövdenin girinti seviyesi.
  final String indent;
  _Fold({
    required this.id,
    required this.startModel,
    required this.endModel,
    required this.hidden,
    required this.lineCount,
    this.indent = '',
  });
}

// re_editor'ın o an ekranda çizdiği satırları (CodeIndicatorValue) editör
// dışına taşıyan köprü. indicatorBuilder her çağrıldığında kaynak bildiriciye
// bağlanır; editörün üstündeki kılavuz katmanı bu köprüyü dinler.
class _ParagraphsBridge extends ChangeNotifier {
  ValueNotifier<re.CodeIndicatorValue?>? _source;
  re.CodeIndicatorValue? get value => _source?.value;

  void attach(ValueNotifier<re.CodeIndicatorValue?> source) {
    if (identical(source, _source)) return;
    _source?.removeListener(notifyListeners);
    _source = source;
    source.addListener(notifyListeners);
  }

  @override
  void dispose() {
    _source?.removeListener(notifyListeners);
    _source = null;
    super.dispose();
  }
}

// VS Code'daki gibi sütun çizgileri (girinti kılavuzları) ve "boundary"
// kipinde boşluk göstergesi (baştaki/sondaki boşluklar ve 2+ boşluk dizileri;
// kelimeler arasındaki tek boşluklar çizilmez). Konumlar re_editor'ın gerçekte
// çizdiği satır paragraflarından alınır; böylece kaydırma, kelime kaydırma ve
// orantılı fontlarla da hizalama doğru kalır. Yalnızca görünen satırlar
// işlenir.
class _EditorGuidePainter extends CustomPainter {
  final _ParagraphsBridge bridge;
  final re.CodeLineEditingController controller;
  final GlobalKey indicatorKey;
  final bool showGuides;
  final bool showWhitespace;
  final int indentUnit;
  final double spaceWidth;
  final Color guideColor;
  final Color activeGuideColor;
  final Color whitespaceColor;

  // Boş satırların girintisini ve etkin bloğu bulurken taranacak en fazla
  // satır sayısı (dev dosyalarda boyama maliyetini sınırlar).
  static const int _scanLimit = 400;
  static const int _blockScanLimit = 3000;
  static const int _maxWhitespaceLine = 2000;

  _EditorGuidePainter({
    required this.bridge,
    required this.controller,
    required this.indicatorKey,
    required this.showGuides,
    required this.showWhitespace,
    required this.indentUnit,
    required this.spaceWidth,
    required this.guideColor,
    required this.activeGuideColor,
    required this.whitespaceColor,
  }) : super(repaint: Listenable.merge([bridge, controller]));

  static bool _isWs(int c) => c == 0x20 || c == 0x09;

  /// Satırın girinti genişliği (sütun). Boş / yalnızca boşluk satırı: -1.
  static int indentCols(String s, int unit) {
    var cols = 0;
    for (var i = 0; i < s.length; i++) {
      final c = s.codeUnitAt(i);
      if (c == 0x20) {
        cols++;
      } else if (c == 0x09) {
        cols += unit - (cols % unit);
      } else {
        return cols;
      }
    }
    return -1;
  }

  /// Dosyanın girinti birimini, ardışık satırlar arasındaki en sık görülen
  /// girinti artışından tahmin eder (VS Code'un yaklaşımına benzer).
  static int detectIndentUnit(List<String> lines, {int fallback = 4}) {
    final counts = <int, int>{};
    var prev = 0;
    final n = math.min(lines.length, 5000);
    for (var i = 0; i < n; i++) {
      final cols = indentCols(lines[i], 4);
      if (cols < 0) continue;
      final d = cols - prev;
      if (d >= 2 && d <= 8) counts[d] = (counts[d] ?? 0) + 1;
      prev = cols;
    }
    if (counts.isEmpty) return fallback;
    var best = fallback;
    var bestCount = 0;
    counts.forEach((d, c) {
      if (c > bestCount || (c == bestCount && d < best)) {
        best = d;
        bestCount = c;
      }
    });
    return best;
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (!showGuides && !showWhitespace) return;
    final paragraphs = bridge.value?.paragraphs;
    if (paragraphs == null || paragraphs.isEmpty) return;
    final codeLines = controller.codeLines;
    final lineCount = codeLines.length;
    if (lineCount == 0) return;

    // Kod alanı, satır numarası/gösterge sütununun sağında başlar.
    final box = indicatorKey.currentContext?.findRenderObject();
    final left = box is RenderBox && box.hasSize ? box.size.width : 0.0;
    final unit = indentUnit <= 0 ? 4 : indentUnit;

    final cache = <int, int>{};
    int indentOf(int i) =>
        cache.putIfAbsent(i, () => indentCols(codeLines[i].text, unit));

    // Boş satırlar, üst ve alt komşu dolu satırların küçük olan girintisini
    // alır: blok içindeki boş satırlarda çizgi kesilmez, blok bitiminde uzamaz.
    int effectiveIndent(int i) {
      final own = indentOf(i);
      if (own >= 0) return own;
      var above = 0, below = 0;
      for (var k = i - 1; k >= 0 && i - k <= _scanLimit; k--) {
        final v = indentOf(k);
        if (v >= 0) {
          above = v;
          break;
        }
      }
      for (var k = i + 1; k < lineCount && k - i <= _scanLimit; k++) {
        final v = indentOf(k);
        if (v >= 0) {
          below = v;
          break;
        }
      }
      return math.min(above, below);
    }

    // İmlecin bulunduğu bloğun kılavuzu (VS Code'daki "etkin" çizgi).
    int? activeCol;
    var activeStart = -1, activeEnd = -1;
    if (showGuides) {
      final c = controller.selection.extentIndex.clamp(0, lineCount - 1);
      final ci = effectiveIndent(c);
      var nextIndent = -1;
      for (var k = c + 1; k < lineCount && k - c <= _scanLimit; k++) {
        final v = indentOf(k);
        if (v >= 0) {
          nextIndent = v;
          break;
        }
      }
      int? col;
      var from = c;
      if (indentOf(c) >= 0 && nextIndent > ci) {
        // İmleç blok başlığında (ör. "eğer ...:"): altındaki gövde etkin.
        col = ci;
        from = c + 1;
      } else if (ci > 0) {
        col = ((ci - 1) ~/ unit) * unit;
      }
      if (col != null && from < lineCount) {
        var s = from;
        while (s > 0 && from - s < _blockScanLimit) {
          final v = indentOf(s - 1);
          if (v >= 0 && v <= col) break;
          s--;
        }
        var e = from;
        while (e + 1 < lineCount && e - from < _blockScanLimit) {
          final v = indentOf(e + 1);
          if (v >= 0 && v <= col) break;
          e++;
        }
        while (e > s && indentOf(e) < 0) {
          e--;
        }
        activeCol = col;
        activeStart = s;
        activeEnd = e;
      }
    }

    final guidePaint = Paint()
      ..color = guideColor
      ..strokeWidth = 1;
    final activePaint = Paint()
      ..color = activeGuideColor
      ..strokeWidth = 1;
    final wsPaint = Paint()
      ..color = whitespaceColor
      ..strokeWidth = 1;

    canvas.save();
    canvas.clipRect(Rect.fromLTRB(left, 0, size.width, size.height));
    for (final p in paragraphs) {
      final i = p.index;
      if (i < 0 || i >= lineCount) continue;
      if (p.bottom < 0 || p.top > size.height) continue;
      final x0 = left + p.offset.dx;
      if (showGuides) {
        final cols = effectiveIndent(i);
        final levels = (cols + unit - 1) ~/ unit;
        for (var l = 0; l < levels; l++) {
          final col = l * unit;
          final x = (x0 + col * spaceWidth).floorToDouble() + 0.5;
          final active =
              col == activeCol && i >= activeStart && i <= activeEnd;
          canvas.drawLine(Offset(x, p.top), Offset(x, p.bottom),
              active ? activePaint : guidePaint);
        }
      }
      if (showWhitespace) {
        _paintWhitespace(canvas, p, codeLines[i].text, Offset(x0, p.top),
            wsPaint);
      }
    }
    canvas.restore();
  }

  void _paintWhitespace(Canvas canvas, re.CodeLineRenderParagraph p,
      String text, Offset origin, Paint paint) {
    final n = text.length;
    if (n == 0 || n > _maxWhitespaceLine) return;
    var lead = 0;
    while (lead < n && _isWs(text.codeUnitAt(lead))) {
      lead++;
    }
    var trail = n;
    while (trail > lead && _isWs(text.codeUnitAt(trail - 1))) {
      trail--;
    }
    final lh = p.preferredLineHeight;
    var k = 0;
    while (k < n) {
      if (!_isWs(text.codeUnitAt(k))) {
        k++;
        continue;
      }
      var e = k;
      while (e < n && _isWs(text.codeUnitAt(e))) {
        e++;
      }
      if (k < lead || e > trail || e - k >= 2) {
        Offset? a = p.paragraph.getOffset(TextPosition(offset: k));
        for (var j = k; j < e && a != null; j++) {
          final b = p.paragraph.getOffset(TextPosition(offset: j + 1));
          // Kelime kaydırmada b bir alt satıra düşebilir.
          final ax = origin.dx + a.dx;
          final bx = b != null && b.dy == a.dy
              ? origin.dx + b.dx
              : ax + spaceWidth;
          final cy = origin.dy + a.dy + lh / 2;
          if (text.codeUnitAt(j) == 0x09) {
            final end = bx - 2;
            canvas.drawLine(Offset(ax + 2, cy), Offset(end, cy), paint);
            canvas.drawLine(Offset(end - 3, cy - 3), Offset(end, cy), paint);
            canvas.drawLine(Offset(end - 3, cy + 3), Offset(end, cy), paint);
          } else {
            canvas.drawCircle(Offset((ax + bx) / 2, cy), 1.1, paint);
          }
          a = b;
        }
      }
      k = e;
    }
  }

  @override
  bool shouldRepaint(covariant _EditorGuidePainter old) =>
      !identical(old.bridge, bridge) ||
      !identical(old.controller, controller) ||
      old.indicatorKey != indicatorKey ||
      old.showGuides != showGuides ||
      old.showWhitespace != showWhitespace ||
      old.indentUnit != indentUnit ||
      old.spaceWidth != spaceWidth ||
      old.guideColor != guideColor ||
      old.activeGuideColor != activeGuideColor ||
      old.whitespaceColor != whitespaceColor;
}

class CodeEditor extends StatefulWidget {
  const CodeEditor({super.key});
  @override
  State<CodeEditor> createState() => _CodeEditorState();
}

/// re_editor'ın varsayılan kısayollarından, uygulamanın kendi global
/// kısayollarıyla ÇAKIŞANLARI çıkarır. Global tuş dinleyicisi `true` döndürse
/// bile Flutter tuşu odak ağacına yine iletir; bu yüzden Alt+↑/↓ satırı iki
/// kez taşıyor, Ctrl+T yeni sekme açarken mevcut dosyada iki harfin yerini
/// sessizce değiştiriyordu (transpose), Ctrl+/ yorumu açıp geri kapatıyordu.
class _CakismasizKisayollar extends re.CodeShortcutsActivatorsBuilder {
  const _CakismasizKisayollar();

  static String _anahtar(SingleActivator s) =>
      '${s.trigger.keyId}|${s.control}|${s.shift}|${s.alt}|${s.meta}';

  static final Set<String> _uygulama = {
    for (final a in buildAppActions())
      if (a.activator != null) _anahtar(a.activator!),
  };

  @override
  List<ShortcutActivator>? build(re.CodeShortcutType type) {
    final varsayilan =
        const re.DefaultCodeShortcutsActivatorsBuilder().build(type);
    if (varsayilan == null) return null;
    return [
      for (final a in varsayilan)
        if (a is! SingleActivator || !_uygulama.contains(_anahtar(a))) a,
    ];
  }
}

class _CodeEditorState extends State<CodeEditor> {
  static final RegExp _wordPattern =
      RegExp(r'[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*$');
  static const Map<String, String> _pairs = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'",
  };
  final SyntaxHighlightingController _ctrl = SyntaxHighlightingController();
  late final re.CodeLineEditingController _reCtrl;
  late final re.CodeScrollController _reScroll;
  late final FocusNode _focus;
  final ScrollController _textScroll = ScrollController();
  final ScrollController _hScroll = ScrollController();
  final ScrollController _gutterScroll = ScrollController();
  Timer? _debounce;
  Timer? _syntaxTimer;
  Timer? _widthTimer;
  Timer? _foldTimer;
  EditorProvider? _editor;
  UiProvider? _ui;
  BackendService? _backend;
  String? _loadedPath;
  int _loadedRev = -1;
  int _reqId = 0;
  bool _preserveView = false;
  bool _syncingRe = false;
  List<Map<String, String>> _suggestions = [];
  Offset? _sugOffset;
  bool _sugVisible = false;
  int _selIndex = 0;
  double _contentWidth = 0;
  Size _vpSize = const Size(800, 600);
  final Map<int, _Fold> _folds = {};
  final Map<int, int> _foldViewByLine = {};
  // Sütun çizgileri / boşluk göstergesi katmanı için.
  final _ParagraphsBridge _paragraphs = _ParagraphsBridge();
  final GlobalKey _indicatorKey = GlobalKey();
  String? _indentUnitText;
  int _indentUnit = 4;
  String? _spaceWidthKey;
  double _spaceWidth = 8;
  // Son build'deki metin: build() yalnızca metin değişince tekrarlanır
  // (minimap, katlama ikonları); salt imleç hareketi / kaydırma rebuild
  // gerektirmez.
  String? _builtText;
  bool _rebuildScheduled = false;
  Timer? _rebuildTimer;
  int _nextFoldId = 1;
  List<Map<String, int>> _foldRegions = [];
  // NOT: Eskiden burada State'e özel bir `bool _programmaticTextChange`
  // bayrağı vardı. Artık bu durumu controller'ın kendisi tutuyor (bkz.
  // SyntaxHighlightingController.isProgrammaticChange); böylece State
  // dışındaki kod da (toggleComment, duplicateCurrentLine, moveCurrentLine,
  // jumpToLine) aynı korumadan güvenle yararlanabiliyor.
  TextEditingValue? _lastValidValue;
  void _withPreservedView(VoidCallback fn) {
    final was = _preserveView;
    _preserveView = true;
    try {
      fn();
    } finally {
      _preserveView = was;
    }
  }

  bool _reSelectionMatches(re.CodeLineSelection s) {
    final cur = _reCtrl.selection;
    return cur.baseIndex == s.baseIndex &&
        cur.baseOffset == s.baseOffset &&
        cur.extentIndex == s.extentIndex &&
        cur.extentOffset == s.extentOffset;
  }

  int _fullCaretOffset() {
    final viewText = _ctrl.text;
    if (viewText.isEmpty) return 0;

    final viewOff = (_ctrl.selection.isValid ? _ctrl.selection.baseOffset : 0)
        .clamp(0, viewText.length)
        .toInt();
    if (_folds.isEmpty) return viewOff;

    final viewLines = viewText.split('\n');

    int remaining = viewOff;
    int viewLine = 0;

    while (viewLine < viewLines.length - 1 &&
        remaining > viewLines[viewLine].length) {
      remaining -= viewLines[viewLine].length + 1;
      viewLine++;
    }

    final col = remaining;

    int full = 0;

    for (int i = 0; i < viewLine; i++) {
      final f = _folds[_foldViewByLine[i]];
      if (f != null && viewLines[i] == _foldPlaceholder(f)) {
        full += f.hidden.length + 1;
      } else {
        full += viewLines[i].length + 1;
      }
    }

    final currentFold = _folds[_foldViewByLine[viewLine]];
    if (currentFold != null &&
        viewLines[viewLine] == _foldPlaceholder(currentFold)) {
      return full;
    }

    return full + math.min(col, viewLines[viewLine].length);
  }

  @override
  void initState() {
    super.initState();
    _reCtrl = re.CodeLineEditingController(
      spanBuilder: ({
        required context,
        required index,
        required codeLine,
        required textSpan,
        required style,
      }) {
        final palette = Theme.of(context).extension<AppSyntaxPalette>() ??
            AppSyntaxPalette.fallback;
        final baseSpans = SyntaxHighlightingController._tokenize(
          codeLine.text,
          palette,
          style,
        );
        // === Arama vurgusu ===================================================
        // Eskiden arama eşleşmesi sadece _ctrl.selection'a atanıyordu, yani
        // görsel olarak NORMAL metin seçimiyle birebir aynıydı ve koyu
        // temada ayırt edilemiyordu. Artık TÜM eşleşmeler ve (varsa) aktif
        // eşleşme, sözdizimi renklendirmesiyle BİRLİKTE, seçim renginden
        // bağımsız amber/turuncu bir arka planla gösteriliyor.
        final ui = Provider.of<UiProvider>(context, listen: false);
        final query = ui.findOpen ? ui.findQuery : '';
        if (query.isEmpty) {
          return TextSpan(style: style, children: baseSpans);
        }
        int? activeStart, activeEnd;
        final sel = _reCtrl.selection;
        if (sel.isValid &&
            sel.baseIndex == index &&
            sel.extentIndex == index) {
          final s = math.min(sel.baseOffset, sel.extentOffset);
          final e = math.max(sel.baseOffset, sel.extentOffset);
          if (e - s == query.length &&
              s >= 0 &&
              e <= codeLine.text.length &&
              SyntaxHighlightingController.findAllMatches(
                      codeLine.text.substring(s, e), query)
                  .isNotEmpty) {
            activeStart = s;
            activeEnd = e;
          }
        }
        return TextSpan(
          style: style,
          children: SyntaxHighlightingController.applyFindHighlight(
            baseSpans,
            codeLine.text,
            query,
            activeStart: activeStart,
            activeEnd: activeEnd,
            matchBackground: palette.matchBackground,
            activeMatchBackground: palette.activeMatchBackground,
          ),
        );
      },
    );
    _reScroll = re.CodeScrollController(
      verticalScroller: _textScroll,
      horizontalScroller: _hScroll,
    );
    _focus = FocusNode(onKeyEvent: _handleKeyEvent);
    _textScroll.addListener(_onTextScroll);
    _hScroll.addListener(_onHScroll);
    _ctrl.addListener(_onControllerChange);
    // KÖK NEDEN DÜZELTMESİ (tıklama/seçim kayması): `re.CodeEditor`'ın
    // `onChanged:` parametresi SADECE metin değiştiğinde tetiklenir.
    // Kullanıcı sadece bir satıra TIKLAYIP imleci taşıdığında (metin aynı
    // kalır) bu hiç tetiklenmiyordu; _ctrl.selection eski konumda kalıyor,
    // hemen ardından yazılan karakter (özellikle oto-parantez/tırnak
    // mantığı) yanlış konuma uygulanıyordu. _reCtrl'nin kendi değişiklik
    // bildirimini de dinleyerek, METİN AYNI OLSA BİLE her seçim/imleç
    // değişikliğinde _ctrl'yi güncel tutuyoruz.
    _reCtrl.addListener(_onReSelectionOrTextChange);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    final ed = context.read<EditorProvider>();

    if (_editor != ed) {
      _editor?.removeListener(_onEd);
      ed.addListener(_onEd);
      _editor = ed;
      _sync();
    }

    final ui = context.read<UiProvider>();

    if (_ui != ui) {
      _ui?.removeListener(_onUiChange);
      ui.addListener(_onUiChange);
      _ui = ui;
    }

    _backend = context.read<BackendService>();

    ed.uiController = _ctrl;
    ed.caretOffsetProvider = _fullCaretOffset;
    ed.revealModelLine = _revealModelLine;
    ed.caretModelLine = _caretModelLine;
    ed.pushViewContent = _pushContent;
    ed.unfoldAll = _unfoldAll;
    ed.editorFocusNode = _focus;
  }

  void _unfoldAll() {
    for (final id in _folds.keys.toList()) {
      _unfold(id);
    }
  }

  // Arama kutusuna yazarken (editöre hiç dokunmadan) vurgunun HEMEN
  // görünmesi için: UiProvider.findQuery/findOpen değiştiğinde, re_editor'ın
  // görünen satırları yeniden çizmesini (spanBuilder'ı tekrar çağırmasını)
  // tetikleyecek zararsız bir "dürtme" yapıyoruz. _reCtrl'nin kendi
  // seçimini kendisine yeniden atamak, metni/anlamı DEĞİŞTİRMEDEN
  // notifyListeners() tetikler.
  String _lastSyncedFindQuery = '';
  bool _lastSyncedFindOpen = false;
  void _onUiChange() {
    final ui = _ui;
    if (ui == null) return;
    if (ui.findQuery == _lastSyncedFindQuery &&
        ui.findOpen == _lastSyncedFindOpen) {
      return;
    }
    final closed = _lastSyncedFindOpen && !ui.findOpen;
    _lastSyncedFindQuery = ui.findQuery;
    _lastSyncedFindOpen = ui.findOpen;
    if (!mounted) return;
    _reCtrl.selection = _reCtrl.selection;
    // Bul kutusu kapanınca (Esc / X) klavye odağı editöre geri döner.
    if (closed) _focus.requestFocus();
  }

  @override
  void dispose() {
    _editor?.removeListener(_onEd);
    _ui?.removeListener(_onUiChange);

    if (_editor?.uiController == _ctrl) _editor?.uiController = null;
    // Sekme değişiminde YENİ editör önce kurulur, eski sonra yok edilir:
    // sahiplik kontrolü olmadan eski editör yenisinin kancasını siliyordu.
    if (_editor?.caretOffsetProvider == _fullCaretOffset) {
      _editor?.caretOffsetProvider = null;
    }
    if (_editor?.pushViewContent == _pushContent) {
      _editor?.pushViewContent = null;
    }
    if (_editor?.unfoldAll == _unfoldAll) {
      _editor?.unfoldAll = null;
    }
    if (_editor?.editorFocusNode == _focus) {
      _editor?.editorFocusNode = null;
    }
    if (_editor?.revealModelLine == _revealModelLine) {
      _editor?.revealModelLine = null;
    }
    if (_editor?.caretModelLine == _caretModelLine) {
      _editor?.caretModelLine = null;
    }

    _debounce?.cancel();
    _syntaxTimer?.cancel();
    _widthTimer?.cancel();
    _foldTimer?.cancel();
    _rebuildTimer?.cancel();

    _textScroll.removeListener(_onTextScroll);
    _hScroll.removeListener(_onHScroll);
    _ctrl.removeListener(_onControllerChange);
    _reCtrl.removeListener(_onReSelectionOrTextChange);

    _paragraphs.dispose();
    _ctrl.dispose();
    _reCtrl.dispose();
    _reScroll.dispose();
    _focus.dispose();

    _textScroll.dispose();
    _hScroll.dispose();
    _gutterScroll.dispose();

    super.dispose();
  }

  // ------------------------------------------------------------------
  // KATLAMA (FOLD)
  // ------------------------------------------------------------------
  String _foldPlaceholder(_Fold f) =>
      '${f.indent}${f.lineCount} satır kadar kod katlanıldı.';

  /// Katlanan gövdenin girintisi: ilk dolu gövde satırının baştaki
  /// boşlukları; gövde tamamen boşsa başlığın girintisi + bir seviye.
  static String _foldIndent(String header, List<String> body) {
    String lead(String l) {
      var i = 0;
      while (i < l.length && (l[i] == ' ' || l[i] == '\t')) {
        i++;
      }
      return l.substring(0, i);
    }

    for (final l in body) {
      if (l.trim().isNotEmpty) return lead(l);
    }
    final h = lead(header);
    return '$h${h.contains('\t') ? '\t' : '    '}';
  }

  /// Görünüm metnini katlanmış bölgelerle birlikte tam metne çevirir.
  String fullText() {
    // Katlama yoksa görünüm metni zaten tam metindir (kopyalama yok).
    if (_folds.isEmpty) return _ctrl.text;
    final lines = _ctrl.text.split('\n');
    final out = <String>[];
    for (var i = 0; i < lines.length; i++) {
      final f = _folds[_foldViewByLine[i]];
      if (f != null && lines[i] == _foldPlaceholder(f)) {
        out.addAll(f.hidden.split('\n'));
        continue;
      }
      out.add(lines[i]);
    }
    return out.join('\n');
  }

  // Görünüm <-> model satır eşlemesi önbelleği (breakpoint ve hata ayıklama
  // satırları MODEL satırıdır; katlama varken görünüm satırı farklıdır).
  String? _vmText;
  int _vmFoldKey = -1;
  List<int> _vmCache = const [];
  Map<int, int> _mvCache = const {};

  void _ensureViewModel() {
    final foldKey = Object.hashAll(_folds.keys);
    if (identical(_vmText, _ctrl.text) && _vmFoldKey == foldKey) return;
    _vmText = _ctrl.text;
    _vmFoldKey = foldKey;
    _vmCache = _viewModelStart();
    final mv = <int, int>{};
    for (var i = 0; i < _vmCache.length; i++) {
      final m = _vmCache[i];
      if (m > 0) {
        mv[m] = i + 1;
      } else {
        // Katlanmış bölgedeki satırlar yer tutucu satırda gösterilir.
        final f = _folds[-m];
        var start = 1;
        for (var k = i - 1; k >= 0; k--) {
          if (_vmCache[k] > 0) {
            start = _vmCache[k] + 1;
            break;
          }
        }
        final n = f?.lineCount ?? 1;
        for (var x = 0; x < n; x++) {
          mv[start + x] = i + 1;
        }
      }
    }
    _mvCache = mv;
  }

  /// Görünüm satırı -> model satırı (katlama yer tutucusu: null).
  int? _viewToModelLine(int viewLine) {
    _ensureViewModel();
    if (viewLine < 1 || viewLine > _vmCache.length) return null;
    final m = _vmCache[viewLine - 1];
    return m > 0 ? m : null;
  }

  int? _modelToViewLine(int modelLine) {
    _ensureViewModel();
    if (_folds.isEmpty) return modelLine;
    return _mvCache[modelLine];
  }

  Set<int> _modelSetToView(Set<int> lines) {
    if (_folds.isEmpty || lines.isEmpty) return lines;
    return {
      for (final l in lines)
        if (_modelToViewLine(l) case final v?) v,
    };
  }

  void _revealModelLine(int modelLine) {
    if (!mounted) return;
    final v = _modelToViewLine(modelLine);
    if (v != null) jumpToLineIn(_ctrl, v);
  }

  int _caretModelLine() {
    final view = cursorLineOf(_ctrl);
    return _viewToModelLine(view) ?? view;
  }

  /// Görünüm satırı -> model satır numarası (marker satırı: -id).
  List<int> _viewModelStart() {
    if (_folds.isEmpty) {
      final n = _lineNumber(_ctrl.text, _ctrl.text.length);
      return List<int>.generate(n, (i) => i + 1);
    }
    final res = <int>[];
    var model = 1;
    final lines = _ctrl.text.split('\n');
    for (var i = 0; i < lines.length; i++) {
      final f = _folds[_foldViewByLine[i]];
      if (f != null && lines[i] == _foldPlaceholder(f)) {
        res.add(-f.id);
        model += f.lineCount;
      } else {
        res.add(model);
        model++;
      }
    }
    return res;
  }

  void _scheduleFoldRefresh() {
    _foldTimer?.cancel();
    // Büyük dosyada tüm metni backend'e daha seyrek gönder.
    final delay = Duration(milliseconds: _isBigFile ? 1500 : 600);
    _foldTimer = Timer(delay, () async {
      final backend = _backend;
      if (backend == null || !backend.isConnected) return;
      try {
        final r = await backend.call('fold_bolgeleri', {'kod': fullText()});
        final list = <Map<String, int>>[];
        for (final b in (r['bolgeler'] as List? ?? [])) {
          if (b is Map) {
            final m = Map<String, dynamic>.from(b);
            list.add({
              's': (m['baslangic'] as num? ?? 0).toInt(),
              'e': (m['bitis'] as num? ?? 0).toInt(),
            });
          }
        }
        if (!mounted) return;
        // Bölgeler değişmediyse editörü yeniden kurma.
        var same = list.length == _foldRegions.length;
        for (var i = 0; same && i < list.length; i++) {
          same = list[i]['s'] == _foldRegions[i]['s'] &&
              list[i]['e'] == _foldRegions[i]['e'];
        }
        if (!same) setState(() => _foldRegions = list);
      } catch (_) {}
    });
  }

  // _foldIcons önbelleği: metin, bölgeler ve katlamalar değişmedikçe aynı
  // harita döner (gösterge ressamı da gereksiz yere yeniden çizmez).
  String? _foldIconsText;
  List<Map<String, int>>? _foldIconsRegions;
  int _foldIconsFoldKey = -1;
  Map<int, String> _foldIconsCache = const {};

  Map<int, String> _foldIcons() {
    final foldKey = Object.hashAll(_folds.keys);
    if (identical(_foldIconsText, _ctrl.text) &&
        identical(_foldIconsRegions, _foldRegions) &&
        _foldIconsFoldKey == foldKey) {
      return _foldIconsCache;
    }
    final vm = _viewModelStart();
    final folded =
        _folds.values.map((f) => '${f.startModel}:${f.endModel}').toSet();
    // Bölge başlangıcı -> bitişi: satır başına tüm bölgeleri taramak
    // (satır x bölge) büyük dosyalarda çok pahalıydı.
    final regionEnd = <int, int>{};
    for (final r in _foldRegions) {
      regionEnd.putIfAbsent(r['s']!, () => r['e']!);
    }
    final icons = <int, String>{};
    for (var i = 0; i < vm.length; i++) {
      final v = vm[i];
      if (v < 0) {
        icons[i + 1] = '⋯';
        continue;
      }
      final e = regionEnd[v];
      if (e != null) {
        icons[i + 1] = folded.contains('$v:$e') ? '▶' : '▼';
      }
    }
    _foldIconsText = _ctrl.text;
    _foldIconsRegions = _foldRegions;
    _foldIconsFoldKey = foldKey;
    _foldIconsCache = icons;
    return icons;
  }

  void _applyView(String text, int caret) {
    // _fold/_unfold katlama haritasını kendisi günceller; dinleyicideki
    // otomatik harita kaydırması bu değişiklikte çalışmamalı.
    _haritaElleYonetiliyor = true;
    try {
      _ctrl.setProgrammaticValue(TextEditingValue(
        text: text,
        selection: TextSelection.collapsed(offset: caret.clamp(0, text.length)),
      ));
    } finally {
      _haritaElleYonetiliyor = false;
    }
    _lastValidValue = _ctrl.value;
    // re_editor'ın kendi geri alma geçmişi katlamayı bilmez: Ctrl+Z, artık
    // var olmayan bir katlamanın yer tutucusunu içeren eski metne dönüp onu
    // kod olarak dosyaya yazdırabiliyordu. Katlama/açma sonrası geçmiş
    // temizlenir.
    _reCtrl.clearHistory();
    _pushContent();
    setState(() {});
  }

  // Katlama haritası (görünüm satırı -> katlama) her metin değişikliğinde
  // güncellenir. Eskiden kullanıcı düzenlemeleri "programatik" işaretli
  // geldiği için koruma hiç çalışmıyor, harita da kaydırılmıyordu: katlanmış
  // bir bloğun üstünde Enter'a basmak yer tutucu satırını kod olarak
  // dosyaya yazıp gizli kodu SİLİYORDU.
  bool _haritaElleYonetiliyor = false;
  List<int> _dokunulanKatlamalar = const [];

  bool _katlamaHaritasiniGuncelle() {
    if (_folds.isEmpty || _haritaElleYonetiliyor) return true;
    final onceki = _lastValidValue?.text;
    final yeni = _ctrl.text;
    if (onceki == null || identical(onceki, yeni) || onceki == yeni) {
      return _foldViewValid();
    }
    final harita = _foldMapAfterEdit(onceki, yeni);
    if (harita == null) return false;
    // Harita yalnızca yeni metinde doğrulandıktan sonra uygulanır.
    _foldViewByLine
      ..clear()
      ..addAll(harita);
    return true;
  }

  /// Düzenlemeden sonra yer tutucuların yeni satırları (bkz.
  /// [katlamaHaritasiniKaydir]). Düzenleme bir yer tutucuya dokunduysa null
  /// döner ve dokunulan katlamalar [_dokunulanKatlamalar]'a yazılır.
  Map<int, int>? _foldMapAfterEdit(String eski, String yeni) {
    final sonuc = katlamaHaritasiniKaydir(
      _foldViewByLine,
      eski,
      yeni,
      (id) {
        final f = _folds[id];
        return f == null ? null : _foldPlaceholder(f);
      },
    );
    if (sonuc.harita != null) return sonuc.harita;
    _dokunulanKatlamalar =
        sonuc.dokunulan.isNotEmpty ? sonuc.dokunulan : _folds.keys.toList();
    return null;
  }

  /// Yer tutucuya dokunan düzenleme reddedildikten sonra o katlamalar açılır
  /// (VS Code'daki gibi): kullanıcı gizli kodu görüp düzenleyebilir.
  void _dokunulanKatlamalariAc() {
    final ids = _dokunulanKatlamalar;
    _dokunulanKatlamalar = const [];
    if (ids.isEmpty) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      for (final id in ids) {
        _unfold(id);
      }
    });
  }

  bool _foldViewValid() {
    if (_folds.isEmpty) return _foldViewByLine.isEmpty;
    final lines = _ctrl.text.split('\n');
    final seen = <int>{};
    for (final entry in _foldViewByLine.entries) {
      if (entry.key < 0 || entry.key >= lines.length) return false;
      final f = _folds[entry.value];
      if (f == null ||
          !seen.add(entry.value) ||
          lines[entry.key] != _foldPlaceholder(f)) {
        return false;
      }
    }
    return seen.length == _folds.length;
  }

  void _restoreValidFoldView() {
    final v = _lastValidValue;
    if (v == null) return;
    _ctrl.setProgrammaticValue(v);
    _reCtrl.clearHistory(); // bkz. _applyView
    _pushContent();
    _hideSug();
    if (mounted) setState(() {});
  }

  void _fold(int headerIdx, int s, int e) {
    if (e <= s) return;
    for (final f in _folds.values) {
      if (!(e < f.startModel || s > f.endModel)) return;
    }
    final vm = _viewModelStart();
    var bodyEnd = headerIdx;
    for (var i = headerIdx + 1; i < vm.length; i++) {
      final val = vm[i];
      if (val < 0) return;
      if (val > e) break;
      bodyEnd = i;
    }
    if (bodyEnd == headerIdx) return;
    final lines = _ctrl.text.split('\n');
    final bodyLines = lines.sublist(headerIdx + 1, bodyEnd + 1);
    final hidden = bodyLines.join('\n');
    final fold = _Fold(
      id: _nextFoldId++,
      startModel: s,
      endModel: e,
      hidden: hidden,
      lineCount: bodyEnd - headerIdx,
      indent: _foldIndent(lines[headerIdx], bodyLines),
    );
    lines.removeRange(headerIdx + 1, bodyEnd + 1);
    lines.insert(headerIdx + 1, _foldPlaceholder(fold));
    _folds[fold.id] = fold;
    final removedCount = bodyEnd - headerIdx;
    final shifted = <int, int>{};
    for (final entry in _foldViewByLine.entries) {
      if (entry.key > bodyEnd) {
        shifted[entry.key - removedCount] = entry.value;
      } else if (entry.key <= headerIdx) {
        shifted[entry.key] = entry.value;
      }
    }
    shifted[headerIdx + 1] = fold.id;
    _foldViewByLine
      ..clear()
      ..addAll(shifted);
    var caret = 0;
    for (var i = 0; i <= headerIdx; i++) {
      caret += lines[i].length + 1;
    }
    _applyView(lines.join('\n'), caret - 1);
  }

  void _unfold(int id) {
    final f = _folds[id];
    if (f == null) return;
    final lines = _ctrl.text.split('\n');
    int? foldLine;
    for (final entry in _foldViewByLine.entries) {
      if (entry.value == id) {
        foldLine = entry.key;
        break;
      }
    }
    if (foldLine == null || foldLine >= lines.length) return;
    _folds.remove(id);
    lines.removeAt(foldLine);
    final hiddenLines = f.hidden.split('\n');
    lines.insertAll(foldLine, hiddenLines);
    final shifted = <int, int>{};
    final insertedCount = hiddenLines.length - 1;
    for (final entry in _foldViewByLine.entries) {
      if (entry.value == id) continue;
      if (entry.key > foldLine) {
        shifted[entry.key + insertedCount] = entry.value;
      } else {
        shifted[entry.key] = entry.value;
      }
    }
    _foldViewByLine
      ..clear()
      ..addAll(shifted);
    var caret = 0;
    for (var k = 0; k < foldLine; k++) {
      caret += lines[k].length + 1;
    }
    _applyView(lines.join('\n'), caret);
  }

  void _onFoldTap(int viewLine) {
    final vm = _viewModelStart();
    final idx = viewLine - 1;
    if (idx < 0 || idx >= vm.length) return;
    final v = vm[idx];
    if (v < 0) {
      _unfold(-v);
      return;
    }
    final icon = _foldIcons()[viewLine];
    if (icon == '▶') {
      for (final f in _folds.values.toList()) {
        if (f.startModel == v) {
          _unfold(f.id);
          return;
        }
      }
    } else if (icon == '▼') {
      for (final r in _foldRegions) {
        if (r['s'] == v) {
          _fold(idx, r['s']!, r['e']!);
          return;
        }
      }
    }
  }

  // ------------------------------------------------------------------
  // EDİTÖR OLAYLARI
  // ------------------------------------------------------------------
  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent) return KeyEventResult.ignored;

    if (_sugVisible) {
      if (event.logicalKey == LogicalKeyboardKey.escape) {
        _hideSug();
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
        setState(
          () => _selIndex = math.min(_selIndex + 1, _suggestions.length - 1),
        );
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
        setState(() => _selIndex = math.max(_selIndex - 1, 0));
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.tab ||
          event.logicalKey == LogicalKeyboardKey.enter) {
        if (_suggestions.isNotEmpty) {
          _acceptSug(_suggestions[_selIndex]['label']!);
        }
        return KeyEventResult.handled;
      }

      return KeyEventResult.ignored;
    }

    // Windows'ta AltGr, Ctrl+Alt olarak bildirilir. Türkçe Q klavyede
    // AltGr ile yazılan | [ ] { } karakterleri eskiden "Ctrl" kısayolu sayılıp
    // yutuluyor (AltGr+- yakınlaştırmayı küçültüyordu) ve parantez
    // otomatik kapatma çalışmıyordu.
    final ctrlPressed = HardwareKeyboard.instance.isControlPressed &&
        !HardwareKeyboard.instance.isAltPressed;
    final shiftPressed = HardwareKeyboard.instance.isShiftPressed;

    if (ctrlPressed) {
      if (event.logicalKey == LogicalKeyboardKey.enter) {
        _insertEmptyLine(below: !shiftPressed);
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.keyV && shiftPressed) {
        _pasteBelow();
        return KeyEventResult.handled;
      }

      if (event.character == '"') {
        _wrapSelection('"');
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.equal ||
          event.logicalKey == LogicalKeyboardKey.numpadAdd) {
        _zoom(1);
        return KeyEventResult.handled;
      }

      if (event.logicalKey == LogicalKeyboardKey.minus ||
          event.logicalKey == LogicalKeyboardKey.numpadSubtract) {
        _zoom(-1);
        return KeyEventResult.handled;
      }
    }

    if (!ctrlPressed) {
      final ch = event.character;

      if (ch != null && ch.isNotEmpty) {
        final sel = _ctrl.selection;
        final hasSel = sel.isValid && !sel.isCollapsed;

        if (_pairs.containsKey(ch)) {
          if (hasSel) {
            _withPreservedView(() => _wrapSelection(ch));
            return KeyEventResult.handled;
          }

          final t = _ctrl.text;
          final pos = sel.isValid ? sel.baseOffset : t.length;

          if (ch == _pairs[ch] && pos < t.length && t[pos] == ch) {
            _withPreservedView(() {
              _ctrl.runProgrammatic(
                () => _ctrl.selection = TextSelection.collapsed(offset: pos + 1),
              );
            });
            return KeyEventResult.handled;
          }

          final close = _pairs[ch]!;

          _withPreservedView(() {
            _ctrl.setProgrammaticValue(
              TextEditingValue(
                text: t.replaceRange(pos, pos, ch + close),
                selection: TextSelection.collapsed(offset: pos + 1),
              ),
            );
          });

          _pushContent();
          return KeyEventResult.handled;
        }

        if (_pairs.values.contains(ch)) {
          final t = _ctrl.text;
          final pos = sel.isValid ? sel.baseOffset : t.length;

          if (pos < t.length && t[pos] == ch) {
            _withPreservedView(() {
              _ctrl.runProgrammatic(
                () => _ctrl.selection = TextSelection.collapsed(offset: pos + 1),
              );
            });
            return KeyEventResult.handled;
          }
        }
      }
    }

    if (event.logicalKey == LogicalKeyboardKey.tab) {
      _indent(shiftPressed);
      return KeyEventResult.handled;
    }

    return KeyEventResult.ignored;
  }

  void _pushContent() {
    // Son savunma hattı: katlama haritası tutarsızsa tam metin yanlış
    // kurulur (yer tutucu kod olarak yazılır, gizli kod kaybolur); o durumda
    // sekme içeriği hiç güncellenmez.
    if (_folds.isNotEmpty && !_foldViewValid()) return;
    _editor?.updateContent(fullText());
  }

  /// (satır, sütun) -> mutlak ofset. `split` yerine yerel `indexOf`
  /// atlamalarıyla çalışır; büyük dosyalarda bellek ayırmaz.
  static int _absOffset(String text, int lineIndex, int column) {
    var off = 0;
    for (var i = 0; i < lineIndex; i++) {
      final nl = text.indexOf('\n', off);
      if (nl < 0) {
        off = text.length;
        break;
      }
      off = nl + 1;
    }
    return (off + column).clamp(0, text.length).toInt();
  }

  /// Mutlak ofset -> re_editor konumu (satır, sütun); bellek ayırmaz.
  static re.CodeLineSelection _toCodePos(String text, int offset) {
    final target = offset.clamp(0, text.length).toInt();
    var line = 0;
    var start = 0;
    while (true) {
      final nl = text.indexOf('\n', start);
      if (nl < 0 || nl >= target) break;
      start = nl + 1;
      line++;
    }
    return re.CodeLineSelection.collapsed(index: line, offset: target - start);
  }

  // re_editor -> _ctrl yönünde en son aktarılan metin/seçim/değer. Aynı
  // değişiklik için ikinci kez (onChanged + dinleyici) ya da geri yönde
  // (_ctrl -> re_editor) tüm belgeyi yeniden kurup karşılaştırmamak için
  // kimlik (identical) kontrolü yapılır.
  String? _mirrorText;
  TextSelection? _mirrorSel;
  re.CodeLineEditingValue? _lastReValue;
  // _mirrorText'e karşılık gelen re_editor satır listesi: aynı nesneyse
  // (salt imleç/seçim hareketi) metin yeniden birleştirilmez.
  re.CodeLines? _mirrorLines;

  void _syncReText() {
    if (_syncingRe) return;

    final text = _ctrl.text;
    final selection = _ctrl.selection;

    // Değer zaten re_editor'dan geldiyse eşitler; hiçbir şey yapma.
    if (identical(text, _mirrorText) && selection == _mirrorSel) return;

    final codeSel = selection.isValid
        ? () {
            final b = _toCodePos(text, selection.baseOffset);
            final e = selection.extentOffset == selection.baseOffset
                ? b
                : _toCodePos(text, selection.extentOffset);
            return re.CodeLineSelection(
              baseIndex: b.baseIndex,
              baseOffset: b.baseOffset,
              extentIndex: e.baseIndex,
              extentOffset: e.baseOffset,
            );
          }()
        : null;

    final textSame = identical(text, _mirrorText) || _reCtrl.text == text;
    final selSame = codeSel == null || _reSelectionMatches(codeSel);

    if (textSame && selSame) return;

    final preserve = _preserveView;

    final double? v = preserve && _textScroll.hasClients
        ? _textScroll.offset
        : null;

    final double? h = preserve && _hScroll.hasClients
        ? _hScroll.offset
        : null;

    _syncingRe = true;
    _reCtrl.removeListener(_onReSelectionOrTextChange);

    try {
      if (!textSame) {
        _reCtrl.text = text;
      }

      if (codeSel != null && (!textSame || !selSame)) {
        _reCtrl.selection = codeSel;
      }
    } finally {
      _reCtrl.addListener(_onReSelectionOrTextChange);
      _syncingRe = false;
    }
    _mirrorText = text;
    _mirrorSel = selection;
    _lastReValue = _reCtrl.value;
    _mirrorLines = _reCtrl.codeLines;

    if (preserve && !textSame && (v != null || h != null)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;

        if (v != null && _textScroll.hasClients) {
          _textScroll.jumpTo(
            v.clamp(0.0, _textScroll.position.maxScrollExtent),
          );
        }

        if (h != null && _hScroll.hasClients) {
          _hScroll.jumpTo(
            h.clamp(0.0, _hScroll.position.maxScrollExtent),
          );
        }
      });
    }
  }

  void _onReChanged(re.CodeLineEditingValue value) {
    if (_syncingRe) return;

    // Aynı değişiklik hem onChanged hem dinleyiciden gelir; ikincisini
    // ucuzca atla.
    final reValue = _reCtrl.value;
    if (identical(reValue, _lastReValue)) return;
    _lastReValue = reValue;

    // _reCtrl.text her erişimde tüm belgeyi birleştirir: satır listesi
    // değişmediyse (salt imleç hareketi) önceki metni kullan, değiştiyse
    // tek kez al.
    final reLines = reValue.codeLines;
    final reText = identical(reLines, _mirrorLines) && _mirrorText != null
        ? _mirrorText!
        : _reCtrl.text;
    final s = _reCtrl.selection;
    final base = _absOffset(reText, s.baseIndex, s.baseOffset);
    final extent = (s.extentIndex == s.baseIndex &&
            s.extentOffset == s.baseOffset)
        ? base
        : _absOffset(reText, s.extentIndex, s.extentOffset);

    final sameText =
        identical(_ctrl.text, reText) || _ctrl.text == reText;
    if (sameText &&
        _ctrl.selection.baseOffset == base &&
        _ctrl.selection.extentOffset == extent) {
      return;
    }

    final text = sameText ? _ctrl.text : reText;
    final sel = TextSelection(baseOffset: base, extentOffset: extent);
    _mirrorText = text;
    _mirrorSel = sel;
    _mirrorLines = reLines;

    _ctrl.runProgrammatic(() {
      _ctrl.value = TextEditingValue(text: text, selection: sel);
      // Yalnızca metin değiştiyse içerik/öneri işlemleri tetiklenir;
      // salt imleç hareketinde gereksiz.
      if (!sameText) _onChanged(_ctrl.text);
    });
  }

  // DÜZELTME (tıklama/seçim kayması kök nedeni): `onChanged:` yalnızca
  // METİN değiştiğinde tetiklenir. Kullanıcı sadece bir satıra TIKLAYIP
  // imleci taşıdığında (metin aynı kalır) bu asla çağrılmıyordu; sonuç
  // olarak _ctrl.selection ESKİ konumda kalıyor, hemen ardından yazılan
  // karakter (özellikle parantez/tırnak mantığı) YANLIŞ konuma
  // uygulanıyordu. _reCtrl'nin kendi ChangeNotifier mekanizmasını
  // dinleyerek METİN DEĞİŞMESE BİLE her seçim/imleç değişikliğinde
  // _ctrl'yi güncel tutuyoruz.
  void _onReSelectionOrTextChange() {
    // Asıl eşitlik kontrolü _onReChanged'in başında yapılır; burada
    // sadece tetikleyici bir köprü.
    _onReChanged(_reCtrl.value);
  }

  void _insertEmptyLine({required bool below}) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final pos = sel.isValid ? sel.baseOffset : t.length;
    final anchor = below ? _lineEnd(t, pos) : _lineStart(t, pos);
    final nt = t.replaceRange(anchor, anchor, '\n');
    _ctrl.setProgrammaticValue(TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: anchor + 1),
    ));
    _pushContent();
  }

  Future<void> _pasteBelow() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final txt = data?.text;
    if (txt == null || txt.isEmpty || !mounted) return;
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final pos = sel.isValid ? sel.baseOffset : t.length;
    final le = _lineEnd(t, pos);
    final nt = t.replaceRange(le, le, '\n$txt');
    _ctrl.setProgrammaticValue(TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: le + 1 + txt.length),
    ));
    _pushContent();
  }

  void _wrapSelection(String q) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    if (!sel.isValid || sel.isCollapsed) return;
    final inner = t.substring(sel.start, sel.end);
    final nt = t.replaceRange(sel.start, sel.end, '$q$inner$q');
    _ctrl.setProgrammaticValue(TextEditingValue(
      text: nt,
      selection:
          TextSelection(baseOffset: sel.start + 1, extentOffset: sel.end + 1),
    ));
    _pushContent();
  }

  Future<void> _zoom(int d) async {
    final s = context.read<SettingsProvider>();
    final cur = s.getInt('yazi_boyutu', fallback: 14);
    final nv = (cur + d).clamp(8, 32);
    if (nv == cur) return;
    await s.setValue('yazi_boyutu', nv);
    if (mounted) setState(() {});
  }

  void _indent(bool out) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    if (!sel.isValid || sel.isCollapsed) {
      if (out) {
        final ls = _lineStart(t, sel.baseOffset);
        final rest = t.substring(ls);
        int remove = 0;
        if (rest.startsWith('  ')) {
          remove = 2;
        } else if (rest.startsWith(' ')) {
          remove = 1;
        }
        if (remove > 0) {
          _ctrl.runProgrammatic(() {
            _ctrl.value = TextEditingValue(
              text: t.replaceRange(ls, ls + remove, ''),
              selection: TextSelection.collapsed(
                  offset: math.max(ls, sel.baseOffset - remove)),
            );
            _onChanged(_ctrl.text);
          });
        }
      } else {
        _ctrl.runProgrammatic(() {
          _ctrl.value = TextEditingValue(
            text: t.replaceRange(sel.start, sel.start, '  '),
            selection: TextSelection.collapsed(offset: sel.start + 2),
          );
          _onChanged(_ctrl.text);
        });
      }
      return;
    }
    final ls = _lineStart(t, sel.start);
    final le = _lineEnd(t, sel.end);
    final lines = t.substring(ls, le).split('\n');
    final newLines = <String>[];
    var delta = 0;
    for (var i = 0; i < lines.length; i++) {
      if (out) {
        if (lines[i].startsWith('  ')) {
          newLines.add(lines[i].substring(2));
          if (i == 0) delta -= 2;
        } else if (lines[i].startsWith(' ')) {
          newLines.add(lines[i].substring(1));
          if (i == 0) delta -= 1;
        } else {
          newLines.add(lines[i]);
        }
      } else {
        newLines.add('  ${lines[i]}');
        if (i == 0) delta += 2;
      }
    }
    final nb = newLines.join('\n');
    _ctrl.runProgrammatic(() {
      _ctrl.value = TextEditingValue(
        text: t.replaceRange(ls, le, nb),
        selection: TextSelection(
          baseOffset: math.max(0, sel.start + delta),
          extentOffset: math.max(0, sel.end + (nb.length - (le - ls))),
        ),
      );
      _onChanged(_ctrl.text);
    });
  }

  void _onEd() {
    if (mounted) {
      _sync();
      setState(() {});
    }
  }

  void _sync() {
    final ed = _editor;
    if (ed == null) return;

    final pendingCaret = ed.consumePendingCaret();
    final a = ed.activeTab;

    if (a == null || a.path == kSettingsPath) {
      if (_loadedPath != null) {
        // Katlamalar metin değişmeden ÖNCE temizlenir: dinleyici eski
        // katlamaları yeni metne uygulamaya çalışmasın.
        _folds.clear();
        _foldViewByLine.clear();
        _foldRegions = [];

        _ctrl.runProgrammatic(() => _ctrl.clear());
        _syncReText();
        _lastValidValue = _ctrl.value;

        _loadedPath = null;
        _loadedRev = ed.revision;

        _hideSug();
      }
      return;
    }

    if (_loadedPath != a.path || _loadedRev != ed.revision) {
      // Katlamalar metin değişmeden ÖNCE temizlenir (bkz. yukarı).
      _folds.clear();
      _foldViewByLine.clear();
      _foldRegions = [];

      _ctrl.runProgrammatic(() => _ctrl.text = a.content);
      _syncReText();
      _lastValidValue = _ctrl.value;

      _loadedPath = a.path;
      _loadedRev = ed.revision;

      final off = (pendingCaret ?? 0).clamp(0, _ctrl.text.length).toInt();

      _ctrl.runProgrammatic(() {
        _ctrl.selection = TextSelection.collapsed(offset: off);
      });

      _syncReText();
      _lastValidValue = _ctrl.value;

      _hideSug();
      _scheduleWidth();
      _scheduleFoldRefresh();

      if (pendingCaret != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _ensureCaretVisible();
        });
      }
    } else if (pendingCaret != null) {
      final off = pendingCaret.clamp(0, _ctrl.text.length).toInt();

      _ctrl.runProgrammatic(() {
        _ctrl.selection = TextSelection.collapsed(offset: off);
      });

      _syncReText();

      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _ensureCaretVisible();
      });
    }
  }

  void _onTextScroll() {
    // Not: Eskiden burada setState() vardı ve her kaydırma pikselinde tüm
    // editör ağacı yeniden kuruluyordu. build() kaydırma ofsetine bağlı
    // değil; minimap kendi AnimatedBuilder'ı ile, kılavuz katmanı ise
    // re_editor'ın satır bildirimiyle güncelleniyor.
    _syncGutter();
    if (_sugVisible) _hideSug();
  }

  void _onHScroll() {
    if (_sugVisible) _hideSug();
  }

  void _onControllerChange() {
    if (!_katlamaHaritasiniGuncelle()) {
      _restoreValidFoldView();
      _dokunulanKatlamalariAc();
      return;
    }

    final metinDegisti =
        _lastValidValue != null && _lastValidValue!.text != _ctrl.text;
    _lastValidValue = _ctrl.value;
    _syncReText();

    // Uygulamanın kendi komutları (Ctrl+/, Alt+↑/↓, Ctrl+Shift+D …) metni
    // yalnızca _ctrl üzerinde değiştirir; sekme içeriği burada güncellenir.
    // Aksi hâlde Kaydet / Çalıştır / sekme değişimi eski metni kullanıyordu.
    // (re_editor yolundan gelen değişiklikte ikinci çağrı etkisizdir.)
    if (metinDegisti && !_haritaElleYonetiliyor) _pushContent();

    if (_sugVisible) _hideSug();

    final ui = _ui;
    if (ui != null) {
      final offset = _ctrl.selection.isValid ? _ctrl.selection.baseOffset : 0;
      ui.setCursor(
        _lineNumber(_ctrl.text, offset),
        _columnNumber(_ctrl.text, offset),
      );
    }

    if (!_preserveView) {
      _ensureCaretVisible();
    }

    if (_ctrl.text != _builtText) {
      _scheduleRebuild();
      _scheduleSyntaxCheck();
      _scheduleWidth();
      _scheduleFoldRefresh();
    }
  }

  void _scheduleRebuild() {
    // Büyük dosyada her tuş vuruşunda minimap/katlama ikonlarını yeniden
    // hesaplamak yerine yazma durunca (200 ms) tek seferde güncelle.
    if (_isBigFile) {
      _rebuildTimer?.cancel();
      _rebuildTimer = Timer(const Duration(milliseconds: 200), () {
        if (mounted && _ctrl.text != _builtText) setState(() {});
      });
      return;
    }
    if (_rebuildScheduled) return;
    _rebuildScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _rebuildScheduled = false;
      if (mounted && _ctrl.text != _builtText) setState(() {});
    });
    WidgetsBinding.instance.ensureVisualUpdate();
  }

  void _syncGutter() {
    if (!_gutterScroll.hasClients) return;
    final t =
        _textScroll.offset.clamp(0.0, _gutterScroll.position.maxScrollExtent);
    if ((_gutterScroll.offset - t).abs() > 0.5) _gutterScroll.jumpTo(t);
  }

  double _lineHeight() {
    final strut = _strut();
    return strut.fontSize! * strut.height!;
  }

  double _fs() {
    final s =
        context.read<SettingsProvider>().getInt('yazi_boyutu', fallback: 14);
    return s <= 0 ? 14 : s.toDouble();
  }

  TextStyle _style() {
    final family =
        context.read<SettingsProvider>().getString('yazi_tipi', fallback: '');
    return TextStyle(
      fontFamily: family.trim().isNotEmpty ? family.trim() : kMonoFontFamily,
      fontFamilyFallback: kMonoFontFallback,
      fontSize: _fs(),
      height: 1.4,
      color: Theme.of(context).colorScheme.onSurface,
    );
  }

  StrutStyle _strut() {
    final family =
        context.read<SettingsProvider>().getString('yazi_tipi', fallback: '');
    return StrutStyle(
      fontFamily: family.trim().isNotEmpty ? family.trim() : kMonoFontFamily,
      fontFamilyFallback: kMonoFontFallback,
      fontSize: _fs(),
      height: 1.4,
      forceStrutHeight: true,
      leadingDistribution: TextLeadingDistribution.even,
    );
  }

  void _ensureCaretVisible() {
    if (!_textScroll.hasClients) return;
    final off = _ctrl.selection.isValid ? _ctrl.selection.baseOffset : 0;
    final lh = _lineHeight();
    final line = _lineNumber(_ctrl.text, off);
    final top = (line - 1) * lh;
    final vp = _vpSize.height;
    double o = _textScroll.offset;
    if (top < o) {
      o = top;
    } else if (top + lh > o + vp) {
      o = top + lh - vp;
    }
    o = o.clamp(0.0, _textScroll.position.maxScrollExtent);
    if ((o - _textScroll.offset).abs() > 1) _textScroll.jumpTo(o);
    if (!_hScroll.hasClients) return;
    final ls = _lineStart(_ctrl.text, off);
    final prefix = _ctrl.text.substring(ls, off.clamp(ls, _ctrl.text.length));
    final tp = TextPainter(
        text: TextSpan(text: prefix, style: _style()),
        textDirection: TextDirection.ltr)
      ..layout();
    final x = tp.width;
    final vw = math.max(80.0, _vpSize.width - 24);
    double ho = _hScroll.offset;
    if (x < ho) {
      ho = x;
    } else if (x > ho + vw) {
      ho = x - vw;
    }
    ho = ho.clamp(0.0, _hScroll.position.maxScrollExtent);
    if ((ho - _hScroll.offset).abs() > 1) _hScroll.jumpTo(ho);
  }

  void _scheduleWidth() {
    _widthTimer?.cancel();
    if (_ctrl.text.length > 200000) {
      if (_contentWidth != 0) setState(() => _contentWidth = 0);
      return;
    }
    _widthTimer = Timer(const Duration(milliseconds: 120), () {
      if (!mounted) return;
      final tp = TextPainter(
          text: TextSpan(text: _ctrl.text, style: _style()),
          textDirection: TextDirection.ltr)
        ..layout();
      final w = tp.width + 32;
      if ((w - _contentWidth).abs() > 4) {
        setState(() => _contentWidth = w);
      }
    });
  }

  String _contextWindow() => _contextWindowWithOffset().text;

  /// Büyük dosyada imlecin çevresindeki ±150 satır ve bu pencerenin dosyadaki
  /// başlangıç satırı (0 tabanlı kaydırma). Backend'den dönen satır
  /// numaraları pencereye göredir; gösterirken bu kaydırma eklenir.
  ({String text, int lineOffset}) _contextWindowWithOffset() {
    final full = fullText();
    if (full.length < 50000) return (text: full, lineOffset: 0);
    final off = _ctrl.selection.isValid ? _ctrl.selection.baseOffset : 0;
    final start = _lineStart(full, off);
    var ls = start;
    var line = _lineNumber(full, start);
    var target = line - 150;
    while (target > 1 && ls > 0) {
      ls = _lineStart(full, ls - 1);
      target--;
    }
    var le = _lineEnd(full, off);
    target = line + 150;
    while (target > line && le < full.length) {
      le = _lineEnd(full, le + 1);
      target--;
    }
    return (text: full.substring(ls, le), lineOffset: _lineNumber(full, ls) - 1);
  }

  /// Backend'in {satir, mesaj} kaydını durum çubuğu metnine çevirir.
  /// (Eskiden Map'in kendisi toString ile yazılıyordu: "{satir: 2, ...}".)
  static String _satirliMesaj(dynamic kayit, int lineOffset) {
    if (kayit is! Map) return kayit?.toString() ?? '';
    final mesaj = (kayit['mesaj']?.toString() ?? '')
        .replaceFirst(RegExp(r'^Satır \d+(, sütun \d+)?: '), '');
    final satir = kayit['satir'];
    final s = satir is num ? satir.toInt() + lineOffset : null;
    return s != null ? 'Satır $s: $mesaj' : mesaj;
  }

  bool get _isBigFile => _ctrl.text.length >= 50000;
  void _hideSug() {
    _reqId++;
    if (!_sugVisible && _suggestions.isEmpty) return;
    _suggestions = [];
    _sugVisible = false;
    _sugOffset = null;
    _selIndex = 0;
    if (mounted) setState(() {});
  }

  void _onChanged(String v) {
    // DÜZELTME: burası da _onControllerChange ile AYNI eski (artık
    // kullanılmayan) State bayrağını kontrol ediyordu — ikinci, bağımsız
    // bir "sessizce atlama" kaynağıydı. Artık controller'ın kendi
    // durumuna bakıyor.
    // Harita _onControllerChange'de güncellendi; burada yalnızca son bir
    // tutarlılık denetimi yapılır (geçersizse gizli kod asla yazılmaz).
    if (_folds.isNotEmpty && !_foldViewValid()) {
      _restoreValidFoldView();
      return;
    }
    _pushContent();
    _hideSug();
    _debounce?.cancel();
    _debounce = Timer(Duration(milliseconds: _isBigFile ? 700 : 250), _reqSug);
  }

  Future<void> _reqSug() async {
    if (!mounted) return;
    final settings = context.read<SettingsProvider>();
    if (!settings.getBool('otomatik_tamamlama', fallback: true))
      return _hideSug();
    final backend = context.read<BackendService>();
    if (!backend.isConnected) return _hideSug();
    final code = _ctrl.text;
    final sel = _ctrl.selection;
    final cur =
        sel.isValid ? sel.baseOffset.clamp(0, code.length) : code.length;
    final before = code.substring(0, cur);
    final match = _wordPattern.firstMatch(before);
    if (match == null) return _hideSug();
    final word = match.group(0)!;
    if (word.length < 2) return _hideSug();
    final reqId = ++_reqId;
    try {
      final r = await backend.call('tamamlama_onerileri', {
        'kelime': word,
        'kod': _contextWindow(),
      });
      if (!mounted || reqId != _reqId) return;
      final raw = r['oneriler'];
      final items = <Map<String, String>>[];
      if (raw is List) {
        for (var i in raw) {
          if (i is Map) {
            final m = Map<String, dynamic>.from(i);
            final k = m['kelime']?.toString();
            if (k != null && k.isNotEmpty) {
              items.add({'icon': m['ikon']?.toString() ?? '•', 'label': k});
            }
          }
        }
      }
      if (items.isEmpty) return _hideSug();
      final style = _style();
      final lh = _lineHeight();
      final linesBefore = before.split('\n');
      final li = linesBefore.length - 1;
      final lt = linesBefore.last;
      final painter = TextPainter(
          text: TextSpan(text: lt, style: style),
          textDirection: TextDirection.ltr)
        ..layout();
      _suggestions = items;
      _selIndex = 0;
      final double maxLeft = math.max(0.0, _vpSize.width - 260);
      final double maxTop = math.max(0.0, _vpSize.height - 60);
      _sugOffset = Offset(
        (8 + painter.width - _hScroll.offset).clamp(0.0, maxLeft).toDouble(),
        ((li + 1) * lh - _textScroll.offset + 8).clamp(0.0, maxTop).toDouble(),
      );
      _sugVisible = true;
      setState(() {});
    } catch (_) {
      if (mounted && reqId == _reqId) _hideSug();
    }
  }

  void _acceptSug(String w) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final cur = sel.isValid ? sel.baseOffset.clamp(0, t.length) : t.length;
    final before = t.substring(0, cur);
    final after = t.substring(cur);
    final match = _wordPattern.firstMatch(before);
    if (match == null) return;
    final nt = before.substring(0, match.start) + w + after;
    _ctrl.runProgrammatic(() {
      _ctrl.value = TextEditingValue(
        text: nt,
        selection: TextSelection.collapsed(offset: match.start + w.length),
      );
      _onChanged(nt);
    });
    _syncReText();
    _hideSug();
    _focus.requestFocus();
  }

  void _scheduleSyntaxCheck() {
    _syntaxTimer?.cancel();
    _syntaxTimer =
        Timer(Duration(milliseconds: _isBigFile ? 1500 : 800), () async {
      final backend = _backend;
      final ui = _ui;
      if (backend == null || ui == null || !backend.isConnected) return;
      final kod = fullText();
      if (kod.trim().isEmpty) {
        ui.setSyntaxStatus('');
        return;
      }
      try {
        final w = _contextWindowWithOffset();
        final r = await backend.call('syntax_kontrol', {'kod': w.text});
        final hatalar = r['hatalar'];
        final uyarilar = r['uyarilar'];
        if (r['basarili'] != true) {
          if (hatalar is List && hatalar.isNotEmpty) {
            ui.setSyntaxStatus(_satirliMesaj(hatalar.first, w.lineOffset),
                tooltip: hatalar
                    .map((h) => _satirliMesaj(h, w.lineOffset))
                    .join('\n'));
          } else if (r['ok'] == false) {
            // Denetim backend'de çalışamadı (kod hatası değil): yanıltıcı bir
            // "Sözdizimi hatası" yazmak yerine durumu boş bırak.
            ui.setSyntaxStatus('');
          } else {
            ui.setSyntaxStatus('Sözdizimi hatası');
          }
        } else if (uyarilar is List && uyarilar.isNotEmpty) {
          // TürKod komutu ad olarak kullanılmış (ör. "toplam = 0"): kod
          // geçerli ama o komut bu dosyada çalışmaz -> uyarı.
          final ilk = _satirliMesaj(uyarilar.first, w.lineOffset);
          final ek = uyarilar.length > 1 ? ' (+${uyarilar.length - 1})' : '';
          ui.setSyntaxStatus('⚠ $ilk$ek',
              tooltip: uyarilar
                  .map((u) => '⚠ ${_satirliMesaj(u, w.lineOffset)}')
                  .join('\n'));
        } else {
          ui.setSyntaxStatus('✓ Sözdizimi doğru');
        }
      } catch (_) {
        ui.setSyntaxStatus('');
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final active = _editor?.activeTab;
    final bp = context.watch<BreakpointProvider>();
    // UiProvider her imleç hareketinde bildirim yapar; editörün tamamını
    // bunun için yeniden kurmamak adına yalnızca findOpen izlenir.
    final findOpen = context.select<UiProvider, bool>((u) => u.findOpen);
    final settings = context.watch<SettingsProvider>();
    final theme = Theme.of(context);
    context.watch<LanguageProvider>();
    _builtText = _ctrl.text;
    if (active == null || active.path == kSettingsPath) {
      return Container(color: theme.colorScheme.surface);
    }
    final style = _style();
    final viewBreakpoints = _modelSetToView(bp.breakpointsFor(active.id));
    final pausedModel = bp.pausedLineFor(active.id);
    final viewPausedLine =
        pausedModel == null ? null : _modelToViewLine(pausedModel);
    // Satır listesi yalnızca gerektiğinde (minimap / girinti tespiti) ve
    // metin başına bir kez bölünür.
    List<String>? viewLinesCache;
    List<String> viewLines() => viewLinesCache ??= _ctrl.text.split('\n');
    final foldIcons = _foldIcons();
    final showMinimap = settings.getBool('minimap');
    final showLineNumbers =
        settings.getBool('satir_numaralari', fallback: true);
    final wrapEnabled = settings.getBool('kelime_sar');
    final showGuides = settings.getBool('sutun_cizgileri', fallback: true);
    final showWhitespace = settings.getBool('bosluk_gostergesi');
    final needsIndicator = showLineNumbers || showGuides || showWhitespace;
    if (showGuides && _indentUnitText != _ctrl.text) {
      _indentUnitText = _ctrl.text;
      _indentUnit = _EditorGuidePainter.detectIndentUnit(viewLines());
    }
    final spaceKey = '${style.fontFamily}|${style.fontSize}';
    if (spaceKey != _spaceWidthKey) {
      _spaceWidthKey = spaceKey;
      final tp = TextPainter(
        text: TextSpan(text: '        ', style: style),
        textDirection: TextDirection.ltr,
        textScaler: TextScaler.noScaling,
      )..layout();
      _spaceWidth = tp.width / 8;
      tp.dispose();
    }
    return MediaQuery(
      data: MediaQuery.of(context).copyWith(
        textScaler: TextScaler.noScaling,
      ),
      child: Container(
        color: theme.colorScheme.surface,
        child: Listener(
          onPointerSignal: (e) {
            if (e is PointerScrollEvent &&
                HardwareKeyboard.instance.isControlPressed) {
              _zoom(e.scrollDelta.dy < 0 ? 1 : -1);
            }
          },
          child: Row(children: [
            Expanded(
              child: LayoutBuilder(builder: (c, con) {
                final vp = con.biggest;
                _vpSize = vp;
                final editorSurface = re.CodeEditor(
                  shortcutsActivatorsBuilder: const _CakismasizKisayollar(),
                  controller: _reCtrl,
                  focusNode: _focus,
                  scrollController: _reScroll,
                  onChanged: _onReChanged,
                  wordWrap: wrapEnabled,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 8,
                  ),
                  style: re.CodeEditorStyle(
                    fontSize: style.fontSize,
                    fontFamily: style.fontFamily,
                    fontFamilyFallback: style.fontFamilyFallback,
                    fontHeight: 1.4,
                    textColor: theme.colorScheme.onSurface,
                    backgroundColor: theme.colorScheme.surface,
                    selectionColor: theme.colorScheme.primary.withOpacity(0.7),
                    highlightColor: theme.colorScheme.primary.withOpacity(0.18),
                    cursorColor: theme.colorScheme.primary,
                  ),
                  // Satır numaraları kapalı olsa bile sütun çizgileri / boşluk
                  // göstergesi için re_editor'ın satır konum bildiricisine
                  // ihtiyaç var; bu durumda 0 genişlikli bir gösterge verilir.
                  indicatorBuilder: needsIndicator
                      ? (context, editingController, chunkController,
                          notifier) {
                          _paragraphs.attach(notifier);
                          return KeyedSubtree(
                            key: _indicatorKey,
                            child: !showLineNumbers
                                ? const SizedBox(width: 0)
                                : GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTapUp: (details) {
                              final paragraphs = notifier.value?.paragraphs;
                              if (paragraphs == null || paragraphs.isEmpty) {
                                return;
                              }
                              final y = details.localPosition.dy;
                              re.CodeLineRenderParagraph? hit;
                              var closestDistance = double.infinity;
                              for (final paragraph in paragraphs) {
                                if (y >= paragraph.top &&
                                    y < paragraph.bottom) {
                                  hit = paragraph;
                                  break;
                                }
                                final distance = y < paragraph.top
                                    ? paragraph.top - y
                                    : y - paragraph.bottom;
                                if (distance < closestDistance) {
                                  closestDistance = distance;
                                  hit = paragraph;
                                }
                              }
                              final line = (hit?.index ?? -1) + 1;
                              if (line < 1 ||
                                  line > _reCtrl.codeLines.length) {
                                return;
                              }
                              final foldIcons = _foldIcons();
                              if (foldIcons[line] != null) {
                                _onFoldTap(line);
                              } else {
                                final model = _viewToModelLine(line);
                                if (model != null) bp.toggle(active.id, model);
                              }
                            },
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Builder(builder: (context) => SizedBox(
                                    width: 16,
                                    child: CustomPaint(
                                      painter: _EditorIndicatorPainter(
                                        notifier: notifier,
                                        breakpoints: viewBreakpoints,
                                        currentLine: viewPausedLine,
                                        foldIcons: foldIcons,
                                        normalColor:
                                            theme.colorScheme.onSurface,
                                        breakpointColor: Colors.redAccent,
                                        currentColor: Colors.amber,
                                        fontSize: style.fontSize ?? 14,
                                      ),
                                    ),
                                  ),
                                ),
                                re.DefaultCodeLineNumber(
                                  controller: editingController,
                                  notifier: notifier,
                                  textStyle: TextStyle(
                                    fontFamily: style.fontFamily,
                                    fontFamilyFallback:
                                        style.fontFamilyFallback,
                                    fontSize: style.fontSize,
                                    color: theme.brightness == Brightness.light
                                        ? const Color(0xFF4B5563)
                                        : theme.colorScheme.onSurface
                                            .withOpacity(0.72),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          );
                        }
                      : null,
                );
                return Stack(children: [
                  Positioned.fill(child: editorSurface),
                  if (viewPausedLine != null && needsIndicator)
                    Positioned.fill(
                      child: IgnorePointer(
                        child: CustomPaint(
                          painter: _DebugLinePainter(
                            bridge: _paragraphs,
                            line: viewPausedLine,
                            color: Colors.amber.withOpacity(0.16),
                          ),
                        ),
                      ),
                    ),
                  if (showGuides || showWhitespace)
                    Positioned.fill(
                      child: IgnorePointer(
                        child: RepaintBoundary(
                          child: CustomPaint(
                            painter: _EditorGuidePainter(
                              bridge: _paragraphs,
                              controller: _reCtrl,
                              indicatorKey: _indicatorKey,
                              showGuides: showGuides,
                              showWhitespace: showWhitespace,
                              indentUnit: _indentUnit,
                              spaceWidth: _spaceWidth,
                              guideColor: theme.colorScheme.onSurface
                                  .withOpacity(0.13),
                              activeGuideColor: theme.colorScheme.onSurface
                                  .withOpacity(0.38),
                              whitespaceColor: theme.colorScheme.onSurface
                                  .withOpacity(0.30),
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (_sugVisible && _sugOffset != null)
                    Positioned(
                      left: _sugOffset!.dx,
                      top: _sugOffset!.dy,
                      child: TapRegion(
                        onTapOutside: (_) => _hideSug(),
                        child: Container(
                          constraints: const BoxConstraints(
                            minWidth: 220,
                            maxWidth: 320,
                            maxHeight: 220,
                          ),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.surfaceContainerHigh,
                            border:
                                Border.all(color: theme.colorScheme.outline),
                            borderRadius: BorderRadius.circular(3),
                          ),
                          child: ListView.builder(
                            padding: const EdgeInsets.symmetric(vertical: 2),
                            shrinkWrap: true,
                            itemCount: _suggestions.length,
                            itemBuilder: (c2, i) {
                              final it = _suggestions[i];
                              final selected = i == _selIndex;
                              return MouseRegion(
                                cursor: SystemMouseCursors.click,
                                onEnter: (_) {
                                  if (_selIndex != i) {
                                    setState(() => _selIndex = i);
                                  }
                                },
                                child: GestureDetector(
                                  onTap: () => _acceptSug(it['label']!),
                                  child: Container(
                                    color: selected
                                        ? theme.colorScheme.primary
                                            .withOpacity(0.25)
                                        : Colors.transparent,
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    child: Row(
                                      children: [
                                        Text(
                                          it['icon']!,
                                          style: const TextStyle(fontSize: 12),
                                        ),
                                        const SizedBox(width: 6),
                                        Expanded(
                                          child: Text(
                                            it['label']!,
                                            overflow: TextOverflow.ellipsis,
                                            style:
                                                const TextStyle(fontSize: 12),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      ),
                    ),
                  if (findOpen) FindWidget(bounds: vp),
                  if (bp.debugging)
                    const Positioned(
                      right: 16,
                      bottom: 12,
                      child: DebugPanel(),
                    ),
                ]);
              }),
            ),
            if (showMinimap) Minimap(lines: viewLines(), textScroll: _textScroll),
          ]),
        ),
      ),
    );
  }
}

// ============================================================================
// HATA AYIKLAYICI PANELİ (editörün üstünde yüzen araç çubuğu + değişkenler)
// ============================================================================

/// Durulan satırı editör genişliğince vurgular (yalnızca oluk noktası
/// gözden kaçabiliyordu).
class _DebugLinePainter extends CustomPainter {
  final _ParagraphsBridge bridge;
  final int line;
  final Color color;
  _DebugLinePainter({
    required this.bridge,
    required this.line,
    required this.color,
  }) : super(repaint: bridge);

  @override
  void paint(Canvas canvas, Size size) {
    final paragraphs = bridge.value?.paragraphs;
    if (paragraphs == null) return;
    for (final p in paragraphs) {
      if (p.index + 1 == line) {
        canvas.drawRect(
          Rect.fromLTWH(0, p.top, size.width, p.height),
          Paint()..color = color,
        );
        canvas.drawRect(
          Rect.fromLTWH(0, p.top, 3, p.height),
          Paint()..color = color.withOpacity(1),
        );
        break;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DebugLinePainter old) =>
      old.line != line || old.color != color || old.bridge != bridge;
}

class DebugPanel extends StatefulWidget {
  const DebugPanel({super.key});
  @override
  State<DebugPanel> createState() => _DebugPanelState();
}

class _DebugPanelState extends State<DebugPanel> {
  bool _expanded = true;
  final Set<String> _open = {};

  static const Map<String, String> _reasons = {
    'breakpoint': 'Breakpoint',
    'adim': 'Adım',
    'baslangic': 'Başlangıç',
    'duraklat': 'Duraklatıldı',
  };

  Widget _btn(IconData icon, String tip, Color color, VoidCallback? onTap) {
    return IconButton(
      tooltip: tip,
      visualDensity: VisualDensity.compact,
      iconSize: 18,
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 30, minHeight: 30),
      color: color,
      onPressed: onTap,
      icon: Icon(icon),
    );
  }

  Widget _varTile(ThemeData theme, DebugVar v, String keyPrefix, int depth) {
    final key = '$keyPrefix/${v.name}';
    final expandable = v.children.isNotEmpty;
    final open = _open.contains(key);
    final mono = TextStyle(
      fontFamily: kMonoFontFamily,
      fontFamilyFallback: kMonoFontFallback,
      fontSize: 11.5,
      color: theme.colorScheme.onSurface,
    );
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      InkWell(
        onTap: expandable
            ? () => setState(() => open ? _open.remove(key) : _open.add(key))
            : null,
        child: Padding(
          padding: EdgeInsets.only(left: 6.0 + depth * 14, right: 6, top: 2, bottom: 2),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(
              width: 14,
              child: expandable
                  ? Icon(open ? Icons.expand_more : Icons.chevron_right, size: 14)
                  : null,
            ),
            Flexible(
              child: Text.rich(
                TextSpan(children: [
                  TextSpan(
                      text: v.name,
                      style: mono.copyWith(
                          color: theme.colorScheme.primary,
                          fontWeight: FontWeight.w600)),
                  TextSpan(
                      text: '  ${v.type}${v.length != null ? ' (${v.length})' : ''}',
                      style: mono.copyWith(
                          fontSize: 10.5,
                          color: theme.colorScheme.onSurface.withOpacity(0.55))),
                  TextSpan(text: ' = ', style: mono),
                  TextSpan(text: v.value, style: mono),
                ]),
                maxLines: open ? 6 : 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ]),
        ),
      ),
      if (open)
        for (final c in v.children) _varTile(theme, c, key, depth + 1),
    ]);
  }

  Widget _section(ThemeData theme, String title, List<Widget> children) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 2),
        child: Text(title,
            style: theme.textTheme.labelSmall?.copyWith(
                fontWeight: FontWeight.w700,
                letterSpacing: 0.4,
                color: theme.colorScheme.onSurface.withOpacity(0.7))),
      ),
      ...children,
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final bp = context.watch<BreakpointProvider>();
    if (!bp.debugging) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final paused = bp.paused;
    final status = bp.starting
        ? 'Başlatılıyor…'
        : paused
            ? '${_reasons[bp.stopReason] ?? 'Durdu'} • Satır ${bp.currentLine}'
                '${bp.currentFunction.isNotEmpty && bp.currentFunction != 'ana program' ? ' • ${bp.currentFunction}()' : ''}'
            : 'Çalışıyor…';

    void wrap(Future<void> Function() f) {
      f().then((_) {
        if (bp.notice != null && context.mounted) {
          final n = bp.notice!;
          bp.clearNotice();
          showAppSnackbar(context, n);
        }
      });
    }

    return Material(
      elevation: 6,
      color: theme.colorScheme.surfaceContainerHigh,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        width: 340,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: theme.colorScheme.outlineVariant),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 2, 2, 2),
            child: Row(children: [
              Icon(Icons.bug_report,
                  size: 16,
                  color: paused ? Colors.amber : const Color(0xFFEC407A)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(status,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(fontWeight: FontWeight.w600)),
              ),
              if (!paused)
                const SizedBox(
                    width: 12,
                    height: 12,
                    child: CircularProgressIndicator(strokeWidth: 1.6)),
              _btn(_expanded ? Icons.expand_less : Icons.expand_more,
                  _expanded ? 'Değişkenleri gizle' : 'Değişkenleri göster',
                  theme.colorScheme.onSurface,
                  () => setState(() => _expanded = !_expanded)),
            ]),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              _btn(Icons.play_arrow, 'Devam (F5)', const Color(0xFF9CCC65),
                  paused ? () => wrap(bp.continueRun) : null),
              _btn(Icons.pause, 'Duraklat (F6)', const Color(0xFFFFCA28),
                  !paused && !bp.starting ? () => wrap(bp.pause) : null),
              _btn(Icons.redo, 'Adım At (F10)', const Color(0xFF42A5F5),
                  paused ? () => wrap(bp.step) : null),
              _btn(Icons.subdirectory_arrow_right, 'İçine Gir (F11)',
                  const Color(0xFF26C6DA), paused ? () => wrap(bp.stepInto) : null),
              _btn(Icons.subdirectory_arrow_left, 'Dışına Çık (Shift+F11)',
                  const Color(0xFF7E57C2), paused ? () => wrap(bp.stepOut) : null),
              _btn(Icons.stop, 'Durdur (Shift+F5)', const Color(0xFFEF5350),
                  () => wrap(bp.stop)),
            ]),
          ),
          if (_expanded && paused) ...[
            const Divider(height: 1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 300),
              child: SingleChildScrollView(
                padding: const EdgeInsets.only(bottom: 6),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (bp.locals.isNotEmpty)
                    _section(theme, 'YEREL DEĞİŞKENLER', [
                      for (final v in bp.locals) _varTile(theme, v, 'y', 0),
                    ]),
                  _section(theme, 'KÜRESEL DEĞİŞKENLER', [
                    if (bp.globals.isEmpty)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 2, 8, 2),
                        child: Text('(henüz değişken yok)',
                            style: theme.textTheme.bodySmall),
                      ),
                    for (final v in bp.globals) _varTile(theme, v, 'k', 0),
                  ]),
                  if (bp.stack.length > 1)
                    _section(theme, 'ÇAĞRI YIĞINI', [
                      for (final f in bp.stack)
                        InkWell(
                          onTap: () => context
                              .read<EditorProvider>()
                              .revealModelLine
                              ?.call(f.line),
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(20, 2, 8, 2),
                            child: Text('${f.function}  •  satır ${f.line}',
                                style: theme.textTheme.bodySmall),
                          ),
                        ),
                    ]),
                ]),
              ),
            ),
          ],
        ]),
      ),
    );
  }
}

// ============================================================================
// TERMİNAL
// ============================================================================

class TerminalPanel extends StatefulWidget {
  const TerminalPanel({super.key});
  @override
  State<TerminalPanel> createState() => _TerminalPanelState();
}

class _TerminalPanelState extends State<TerminalPanel> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final FocusNode _inputFocus = FocusNode(debugLabel: 'terminal-girdi');
  int _seenFocusTick = -1;
  String? _lastOutput;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  /// Program çalıştırıldığında (UiProvider.focusTerminal) odağı komut
  /// satırına alır. Panel o an yeni açılıyorsa istek ilk karede tüketilir.
  void _handleFocusRequest(int tick) {
    if (tick == _seenFocusTick) return;
    _seenFocusTick = tick;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (context.read<UiProvider>().consumeTerminalFocus()) {
        _inputFocus.requestFocus();
      }
    });
  }

  /// Çıktı değiştiğinde en alta kaydırır; kullanıcı yukarı kaydırıp eski
  /// çıktıyı okuyorsa konumuna dokunmaz (eskiden HER rebuild'de, ör. yazı
  /// boyutu değişince bile, zorla en alta atlanıyordu).
  void _autoScroll(String output) {
    if (identical(output, _lastOutput)) return;
    final prev = _lastOutput;
    _lastOutput = output;
    final shrank = prev != null && output.length < prev.length;
    final atBottom = !_scroll.hasClients ||
        _scroll.position.pixels >= _scroll.position.maxScrollExtent - 24;
    if (!atBottom && !shrank) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scroll.hasClients) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
      }
    });
  }

  Future<void> _zoomTerminal(BuildContext context, int d) async {
    final s = context.read<SettingsProvider>();
    final cur = s.getDouble('terminal_yazi_boyutu', fallback: 13);
    final nv = (cur + d).clamp(8, 28);
    if (nv == cur) return;
    await s.setValue('terminal_yazi_boyutu', nv.round());
  }

  @override
  Widget build(BuildContext context) {
    final term = context.watch<TerminalProvider>();
    final conn = context.watch<ConnectionProvider>().connected;
    final settings = context.watch<SettingsProvider>();
    final theme = Theme.of(context);
    final termFontSize =
        settings.getDouble('terminal_yazi_boyutu', fallback: 13);
    _handleFocusRequest(
        context.select<UiProvider, int>((u) => u.terminalFocusTick));
    final output = term.output;
    _autoScroll(output);
    return Container(
      color: theme.colorScheme.surface,
      child: Column(children: [
        Container(
          height: 28,
          color: theme.colorScheme.surfaceContainer,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(children: [
            Icon(Icons.terminal,
                size: 13, color: theme.colorScheme.onSurface.withOpacity(0.7)),
            const SizedBox(width: 6),
            Text('TERMİNAL',
                style: theme.textTheme.labelLarge
                    ?.copyWith(letterSpacing: 0.5, fontSize: 10)),
            if (term.isRunning) ...[
              const SizedBox(width: 8),
              const SizedBox(
                  width: 10,
                  height: 10,
                  child: CircularProgressIndicator(strokeWidth: 2)),
            ],
            const Spacer(),
            IconButton(
              tooltip: 'Yazıyı Küçült (Ctrl+Tekerlek)',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.zoom_out, size: 14),
              onPressed: () => _zoomTerminal(context, -1),
            ),
            IconButton(
              tooltip: 'Yazıyı Büyüt (Ctrl+Tekerlek)',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.zoom_in, size: 14),
              onPressed: () => _zoomTerminal(context, 1),
            ),
            IconButton(
              tooltip: 'Temizle',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.delete_sweep, size: 14),
              onPressed: term.clear,
            ),
            IconButton(
              tooltip: 'Kapat',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close, size: 14),
              onPressed: () => context.read<UiProvider>().toggleTerminal(),
            ),
          ]),
        ),
        Expanded(
          child: Listener(
            onPointerSignal: (e) {
              if (e is PointerScrollEvent &&
                  HardwareKeyboard.instance.isControlPressed) {
                _zoomTerminal(context, e.scrollDelta.dy < 0 ? 1 : -1);
              }
            },
            child: Scrollbar(
              controller: _scroll,
              thumbVisibility: true,
              thickness: 10,
              child: SingleChildScrollView(
                controller: _scroll,
                padding: const EdgeInsets.only(
                    left: 8, right: 14, top: 4, bottom: 4),
                child: SizedBox(
                  width: double.infinity,
                  child: SelectableText(output,
                      style: TextStyle(
                          fontFamily: kMonoFontFamily,
                          fontFamilyFallback: kMonoFontFallback,
                          fontSize: termFontSize,
                          height: 1.35)),
                ),
              ),
            ),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
          decoration: BoxDecoration(
              border: Border(
                  top: BorderSide(color: theme.colorScheme.outlineVariant))),
          child: Row(children: [
            Text('> ',
                style: TextStyle(
                    fontFamily: kMonoFontFamily,
                    fontFamilyFallback: kMonoFontFallback,
                    color: theme.colorScheme.primary,
                    fontSize: termFontSize)),
            Expanded(
              child: TextField(
                controller: _input,
                focusNode: _inputFocus,
                enabled: conn,
                style: TextStyle(
                    fontFamily: kMonoFontFamily,
                    fontFamilyFallback: kMonoFontFallback,
                    fontSize: termFontSize),
                decoration: const InputDecoration(
                    isDense: true,
                    border: InputBorder.none,
                    hintText: 'Komut...'),
                // Enter sonrası odak terminalde kalsın (varsayılan davranış
                // odağı bırakıyordu; art arda komut/girdi yazılamıyordu).
                onEditingComplete: () {},
                onSubmitted: (v) {
                  // Çalışan program girdi bekliyorsa boş satır da gönderilir
                  // ("Devam için Enter'a basın" eskiden hiç ilerlemiyordu).
                  if (term.isRunning || v.trim().isNotEmpty) {
                    term.sendCommand(v);
                    _input.clear();
                  }
                  _inputFocus.requestFocus();
                },
              ),
            ),
          ]),
        ),
      ]),
    );
  }
}

// ============================================================================
// AI PANELİ
// ============================================================================

class AiChatBubble extends StatelessWidget {
  final AiMessage message;
  const AiChatBubble({super.key, required this.message});
  Future<void> _applyCode(BuildContext context, String kod) async {
    final ed = context.read<EditorProvider>();
    final choice = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Kodu Uygula'),
        content: const Text('AI kodunu nasıl uygulamak istersin?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, 'replace'),
              child: const Text('Üzerine Yaz')),
          TextButton(
              onPressed: () => Navigator.pop(dc, 'insert'),
              child: const Text('İmlece Ekle')),
          OutlinedButton(
              onPressed: () => Navigator.pop(dc, 'tab'),
              child: const Text('Yeni Sekme')),
          TextButton(
              onPressed: () => Navigator.pop(dc), child: const Text('Vazgeç')),
        ],
      ),
    );
    if (!context.mounted || choice == null) return;
    if (choice == 'replace') {
      ed.replaceActiveContent(kod);
      showAppSnackbar(context, 'AI kodu uygulandı', kind: SnackKind.success);
    } else if (choice == 'insert') {
      final c = ed.uiController;
      if (c == null) return;
      final t = c.text;
      final pos = c.selection.isValid ? c.selection.baseOffset : t.length;
      // Programatik uygulanır ve tam (katlamaları açılmış) metin aktarılır:
      // eskiden görünüm metni sekmeye yazılıyor, katlı kod kayboluyordu.
      _setControllerValueProgrammatic(
        c,
        TextEditingValue(
          text: t.replaceRange(pos, pos, kod),
          selection: TextSelection.collapsed(offset: pos + kod.length),
        ),
      );
      ed.syncFromView();
      showAppSnackbar(context, 'AI kodu imlece eklendi',
          kind: SnackKind.success);
    } else if (choice == 'tab') {
      ed.createUntitled(
        name: 'ai_kod.trpy',
        content: kod,
        context: context,
      );
      showAppSnackbar(context, 'AI kodu yeni sekmede açıldı',
          kind: SnackKind.success);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == AiRole.user;
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: theme.colorScheme.outlineVariant, width: 1),
        ),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(isUser ? 'SİZ' : 'AI',
            style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.6,
                color: isUser
                    ? theme.colorScheme.primary
                    : theme.colorScheme.onSurface.withOpacity(0.6))),
        const SizedBox(height: 4),
        ...message.parts.map((part) {
          if (part.type == 'kod') {
            return Container(
              margin: const EdgeInsets.symmetric(vertical: 4),
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainer,
                border: Border.all(color: theme.colorScheme.outlineVariant),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Text((part.language?.isEmpty ?? true) ? 'kod' : part.language!,
                          style: TextStyle(
                              fontSize: 10,
                              color: theme.colorScheme.onSurface
                                  .withOpacity(0.6))),
                      const Spacer(),
                      MouseRegion(
                        cursor: SystemMouseCursors.click,
                        child: GestureDetector(
                          onTap: () => Clipboard.setData(
                              ClipboardData(text: part.content)),
                          child: const Icon(Icons.copy, size: 12),
                        ),
                      ),
                      const SizedBox(width: 8),
                      MouseRegion(
                        cursor: SystemMouseCursors.click,
                        child: GestureDetector(
                          onTap: () => _applyCode(context, part.content),
                          child: const Icon(Icons.open_in_new, size: 12),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 4),
                    SelectableText(part.content,
                        style: const TextStyle(
                            fontFamily: kMonoFontFamily,
                            fontFamilyFallback: kMonoFontFallback,
                            fontSize: 12,
                            height: 1.35)),
                  ]),
            );
          }
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: SelectableText(part.content,
                style: const TextStyle(fontSize: 13, height: 1.35)),
          );
        }),
      ]),
    );
  }
}

class _AiHintChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool enabled;
  final VoidCallback onTap;
  const _AiHintChip({
    required this.icon,
    required this.label,
    required this.enabled,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return MouseRegion(
      cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHigh,
            border: Border.all(color: theme.colorScheme.outlineVariant),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon,
                size: 13,
                color: enabled
                    ? theme.colorScheme.primary
                    : theme.colorScheme.onSurface.withOpacity(0.35)),
            const SizedBox(width: 5),
            Text(label,
                style: TextStyle(
                    fontSize: 11.5,
                    color: enabled
                        ? theme.colorScheme.onSurface
                        : theme.colorScheme.onSurface.withOpacity(0.35))),
          ]),
        ),
      ),
    );
  }
}

class AiPanel extends StatefulWidget {
  const AiPanel({super.key});
  @override
  State<AiPanel> createState() => _AiPanelState();
}

class _AiPanelState extends State<AiPanel> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ai = context.watch<AiProvider>();
    final conn = context.watch<ConnectionProvider>().connected;
    final theme = Theme.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
    String currentCode() => context.read<EditorProvider>().activeContent.value;
    return Container(
      color: theme.colorScheme.surfaceContainer,
      child: Column(children: [
        Container(
          height: 30,
          color: theme.colorScheme.surfaceContainer,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(children: [
            Icon(Icons.auto_awesome,
                size: 14, color: theme.colorScheme.primary),
            const SizedBox(width: 6),
            Expanded(
                child: Text('AI ASİSTAN',
                    style: theme.textTheme.labelLarge
                        ?.copyWith(letterSpacing: 0.5, fontSize: 10))),
            IconButton(
              tooltip: 'Açıkla',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.lightbulb_outline, size: 14),
              onPressed:
                  conn && !ai.loading ? () => ai.explain(currentCode()) : null,
            ),
            IconButton(
              tooltip: 'Optimize',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.bolt, size: 14),
              onPressed:
                  conn && !ai.loading ? () => ai.optimize(currentCode()) : null,
            ),
            IconButton(
              tooltip: 'Temizle',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.delete_outline, size: 14),
              onPressed: conn && !ai.loading ? ai.clear : null,
            ),
          ]),
        ),
        Divider(height: 1, color: theme.colorScheme.outlineVariant),
        Expanded(
          child: ai.messages.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome,
                            size: 32,
                            color: theme.colorScheme.primary.withOpacity(0.7)),
                        const SizedBox(height: 12),
                        Text('AI Asistanına Hoş Geldiniz',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        Text(
                          conn
                              ? 'Kodunuz hakkında soru sorun, açıklama isteyin\n'
                                  'veya optimizasyon önerileri alın.'
                              : 'AI özelliklerini kullanmak için backend '
                                  'bağlantısının kurulmasını bekleyin.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: 12,
                              color:
                                  theme.colorScheme.onSurface.withOpacity(0.6)),
                        ),
                        const SizedBox(height: 14),
                        Wrap(
                          alignment: WrapAlignment.center,
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            _AiHintChip(
                              icon: Icons.lightbulb_outline,
                              label: 'Açıkla',
                              enabled: conn && !ai.loading,
                              onTap: () => ai.explain(currentCode()),
                            ),
                            _AiHintChip(
                              icon: Icons.bolt,
                              label: 'Optimize et',
                              enabled: conn && !ai.loading,
                              onTap: () => ai.optimize(currentCode()),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                )
              : ListView.builder(
                  controller: _scroll,
                  itemCount: ai.messages.length + (ai.loading ? 1 : 0),
                  itemBuilder: (c, i) => i < ai.messages.length
                      ? AiChatBubble(message: ai.messages[i])
                      : const Padding(
                          padding:
                              EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          child: LinearProgressIndicator(minHeight: 2)),
                ),
        ),
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
              border: Border(
                  top: BorderSide(color: theme.colorScheme.outlineVariant))),
          child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Expanded(
              // Çok satırlı alanda onSubmitted masaüstünde hiç tetiklenmez;
              // Enter yeni satır ekliyordu. Enter gönderir, Shift+Enter yeni
              // satır ekler.
              child: CallbackShortcuts(
                bindings: {
                  const SingleActivator(LogicalKeyboardKey.enter): () {
                    final t = _input.text.trim();
                    if (t.isNotEmpty && conn && !ai.loading) {
                      ai.ask(t, kod: currentCode());
                      _input.clear();
                    }
                  },
                  const SingleActivator(LogicalKeyboardKey.numpadEnter): () {
                    final t = _input.text.trim();
                    if (t.isNotEmpty && conn && !ai.loading) {
                      ai.ask(t, kod: currentCode());
                      _input.clear();
                    }
                  },
                },
                child: TextField(
                  controller: _input,
                  enabled: conn && !ai.loading,
                  minLines: 1,
                  maxLines: 4,
                  style: const TextStyle(fontSize: 12.5),
                  decoration: const InputDecoration(
                      hintText: 'Sor... (Shift+Enter: yeni satır)',
                      isDense: true),
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton(
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.send, size: 15),
              onPressed: conn && !ai.loading
                  ? () {
                      final t = _input.text.trim();
                      if (t.isNotEmpty) {
                        ai.ask(t, kod: currentCode());
                        _input.clear();
                      }
                    }
                  : null,
            ),
          ]),
        ),
      ]),
    );
  }
}

// ============================================================================
// AYARLAR SAYFASI
// ============================================================================

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _apiKey = TextEditingController();
  final _sysMsg = TextEditingController();
  final _maxTok = TextEditingController();
  final _fontSearch = TextEditingController();
  final _duzeltmeZamanAsimi = TextEditingController();
  final _duzeltmeMesajAraligi = TextEditingController();
  final _duzeltmeMaksDongu = TextEditingController();
  late String _tema;
  late String _sag;
  late String _model;
  late String _yaziTipi;
  late bool _ai;
  late bool _auto;
  late bool _autoSave;
  late bool _satirNo;
  late bool _kelimeSar;
  late bool _boslukGoster;
  late double _sic;
  late double _fontSize;
  late double _terminalFontSize;
  bool _formReady = false;
  bool _saving = false;
  bool _updatingModels = false;
  bool _fontListOpen = false;
  static final List<String> temalar =
      AppThemeRegistry.definitions.map((e) => e.name).toList();
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    final s = context.read<SettingsProvider>();

    if (!_formReady && s.loaded) {
      _populate(s);
      _formReady = true;
    }
    // Kurulu font listesi açılışta değil, Ayarlar ilk açıldığında istenir.
    if (s.loaded && s.systemFonts.isEmpty && !_fontsRequested) {
      _fontsRequested = true;
      s.refreshSystemFonts();
    }
  }

  bool _fontsRequested = false;
  // Sayfa açıldığındaki boyutlar: kullanıcı kaydırıcıyı oynatmadıysa
  // kaydetmede bu ayarlara dokunulmaz (Ctrl+tekerlek ile sayfa açıkken
  // yapılan yakınlaştırma eskiden eski değerle eziliyordu).
  double _fontSizeIlk = 14;
  double _terminalFontSizeIlk = 13;

  void _populate(SettingsProvider s) {
    _tema = s.getString('tema', fallback: 'Modern Koyu');
    if (!temalar.contains(_tema)) _tema = temalar.first;
    _sag = s.getString('ai_saglayici', fallback: 'OpenAI');
    if (!s.aiModels.containsKey(_sag)) _sag = s.aiModels.keys.first;
    final savedModel = s.getString('ai_model', fallback: '').trim();
    final models = s.aiModels[_sag] ?? [];
    _model = savedModel.isNotEmpty
        ? savedModel
        : (models.isNotEmpty ? models.first : '');
    _apiKey.text = s.getString('ai_api_key');
    _sysMsg.text = s.getString('ai_sistem_mesaji');
    _maxTok.text = s.getInt('ai_max_token', fallback: 4096).toString();
    // Kayıtlı değerler kaydırıcı sınırlarına çekilir: elle düzenlenmiş /
    // eski sürümden kalan ayar dosyasındaki sınır dışı bir değer Slider
    // doğrulamasını patlatıp Ayarlar sayfasını açılamaz hâle getiriyordu.
    _sic = s.getDouble('ai_sicaklik', fallback: 0.7).clamp(0.0, 2.0).toDouble();
    _fontSize =
        s.getInt('yazi_boyutu', fallback: 14).clamp(8, 32).toDouble();
    _fontSizeIlk = _fontSize;
    _ai = s.getBool('ai_aktif');
    _auto = s.getBool('otomatik_tamamlama', fallback: true);
    _autoSave = s.getBool('otomatik_kaydetme');
    _satirNo = s.getBool('satir_numaralari', fallback: true);
    _kelimeSar = s.getBool('kelime_sar');
    _boslukGoster = s.getBool('bosluk_gostergesi');
    _yaziTipi = s.getString('yazi_tipi', fallback: 'Consolas').trim();
    if (_yaziTipi.isEmpty) _yaziTipi = 'Consolas';
    _fontSearch.text = _yaziTipi;
    _terminalFontSize = s
        .getDouble('terminal_yazi_boyutu', fallback: 13)
        .clamp(8.0, 28.0)
        .toDouble();
    _terminalFontSizeIlk = _terminalFontSize;
    _duzeltmeZamanAsimi.text =
        s.getInt('duzeltme_zaman_asimi', fallback: 5).toString();
    _duzeltmeMesajAraligi.text =
        s.getInt('duzeltme_mesaj_araligi', fallback: 100).toString();
    _duzeltmeMaksDongu.text =
        s.getInt('duzeltme_maks_dongu', fallback: 12).toString();
  }

  @override
  void dispose() {
    _apiKey.dispose();
    _sysMsg.dispose();
    _maxTok.dispose();
    _fontSearch.dispose();
    _duzeltmeZamanAsimi.dispose();
    _duzeltmeMesajAraligi.dispose();
    _duzeltmeMaksDongu.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      final s = context.read<SettingsProvider>();
      await s.setValue('tema', _tema);
      await s.setValue('ai_aktif', _ai);
      await s.setValue('ai_saglayici', _sag);
      await s.setValue('ai_model', _model);
      await s.setValue('ai_api_key', _apiKey.text.trim());
      await s.setValue('ai_sistem_mesaji', _sysMsg.text);
      await s.setValue('ai_sicaklik', _sic);
      await s.setValue(
          'ai_max_token', int.tryParse(_maxTok.text.trim()) ?? 4096);
      await s.setValue('otomatik_tamamlama', _auto);
      await s.setValue('otomatik_kaydetme', _autoSave);
      if (_fontSize != _fontSizeIlk) {
        await s.setValue('yazi_boyutu', _fontSize.round());
        _fontSizeIlk = _fontSize;
      }
      await s.setValue('satir_numaralari', _satirNo);
      await s.setValue('kelime_sar', _kelimeSar);
      await s.setValue('bosluk_gostergesi', _boslukGoster);
      await s.setValue('yazi_tipi',
          _yaziTipi.trim().isEmpty ? 'Consolas' : _yaziTipi.trim());
      if (_terminalFontSize != _terminalFontSizeIlk) {
        await s.setValue('terminal_yazi_boyutu', _terminalFontSize.round());
        _terminalFontSizeIlk = _terminalFontSize;
      }
      await s.setValue('duzeltme_zaman_asimi',
          int.tryParse(_duzeltmeZamanAsimi.text.trim()) ?? 5);
      await s.setValue('duzeltme_mesaj_araligi',
          int.tryParse(_duzeltmeMesajAraligi.text.trim()) ?? 100);
      await s.setValue('duzeltme_maks_dongu',
          int.tryParse(_duzeltmeMaksDongu.text.trim()) ?? 12);
      if (mounted) {
        showAppSnackbar(context, 'Ayarlar kaydedildi', kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) {
        showAppSnackbar(context, 'Hata: $e', kind: SnackKind.error);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _updateModels() async {
    if (_updatingModels) return;
    setState(() => _updatingModels = true);
    final s = context.read<SettingsProvider>();
    final backend = context.read<BackendService>();
    try {
      // Backend kayıtlı sağlayıcı/anahtarı kullanır: formda yeni girilen
      // (henüz "Kaydet"e basılmamış) değerler önce kaydedilir.
      await s.setValue('ai_saglayici', _sag);
      await s.setValue('ai_api_key', _apiKey.text.trim());
      await backend.call('ai_modelleri_guncelle');
      await s.refreshModels();
      if (!s.aiModels.containsKey(_sag)) _sag = s.aiModels.keys.first;
      final models = s.aiModels[_sag] ?? [];
      if (!models.contains(_model))
        _model = models.isNotEmpty ? models.first : '';
      if (mounted) {
        setState(() {});
        showAppSnackbar(context, 'Model listesi güncellendi',
            kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) {
        showAppSnackbar(context, 'Model güncelleme hatası: $e',
            kind: SnackKind.error);
      }
    } finally {
      if (mounted) setState(() => _updatingModels = false);
    }
  }

  Widget _card(BuildContext context, IconData icon, String title,
      List<Widget> children) {
    final theme = Theme.of(context);
    // Material (renkli Container değil): içerideki CheckboxListTile'ların
    // üzerine gelme / tıklama efektleri kart arka planının altında
    // kalmasın.
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: theme.colorScheme.surfaceContainer,
        shape: RoundedRectangleBorder(
          side: BorderSide(color: theme.colorScheme.outlineVariant),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
              crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 15, color: theme.colorScheme.primary),
          const SizedBox(width: 8),
          Text(title,
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 10),
        Divider(height: 1, color: theme.colorScheme.outlineVariant),
        const SizedBox(height: 18),
        ...children.map((c) =>
            Padding(padding: const EdgeInsets.only(bottom: 14), child: c)),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = context.watch<SettingsProvider>();
    if (!settings.loaded || !_formReady) {
      return Material(
        color: theme.colorScheme.surface,
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    final providers = settings.aiModels.keys.toList();
    if (!providers.contains(_sag) && providers.isNotEmpty)
      _sag = providers.first;
    final models = List<String>.from(settings.aiModels[_sag] ?? []);
    if (_model.isNotEmpty && !models.contains(_model)) models.add(_model);
    if (models.isEmpty) models.add('');
    if (!models.contains(_model)) _model = models.first;
    // Material: açılır menüler, kaydırıcılar ve metin alanları sayfanın
    // kendi yüzeyine ihtiyaç duyar (Scaffold dışında da güvenle çalışsın).
    return Material(
      color: theme.colorScheme.surface,
      child: Column(children: [
        Container(
          height: 42,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainer,
            border: Border(
                bottom: BorderSide(color: theme.colorScheme.outlineVariant)),
          ),
          child: Row(children: [
            Icon(Icons.settings_outlined,
                size: 15, color: theme.colorScheme.primary),
            const SizedBox(width: 8),
            Text('Ayarlar',
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const Spacer(),
            OutlinedButton(
              onPressed: _updatingModels ? null : _updateModels,
              child: _updatingModels
                  ? const SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Modelleri Güncelle'),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Kaydet ve Uygula'),
            ),
          ]),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 680),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _card(context, Icons.palette_outlined, 'Genel', [
                        DropdownButtonFormField<String>(
                          value: _tema,
                          isExpanded: true,
                          menuMaxHeight: 260,
                          borderRadius: BorderRadius.circular(3),
                          dropdownColor: theme.colorScheme.surfaceContainerHigh,
                          style: TextStyle(
                              color: theme.colorScheme.onSurface, fontSize: 13),
                          decoration: const InputDecoration(
                              labelText: 'Tema', isDense: true),
                          items: temalar
                              .map((t) =>
                                  DropdownMenuItem(value: t, child: Text(t)))
                              .toList(),
                          onChanged: (v) => setState(() => _tema = v ?? _tema),
                        ),
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Yazı Boyutu: ${_fontSize.round()}',
                                  style: const TextStyle(fontSize: 12)),
                              Slider(
                                  value: _fontSize,
                                  min: 8,
                                  max: 32,
                                  divisions: 24,
                                  onChanged: (v) =>
                                      setState(() => _fontSize = v)),
                            ]),
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Yazı Tipi',
                                  style: TextStyle(fontSize: 12)),
                              const SizedBox(height: 4),
                              TapRegion(
                                onTapOutside: (_) {
                                  if (_fontListOpen)
                                    setState(() => _fontListOpen = false);
                                },
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      TextField(
                                        controller: _fontSearch,
                                        style: TextStyle(
                                            fontFamily: _yaziTipi,
                                            fontSize: 13),
                                        decoration: InputDecoration(
                                          isDense: true,
                                          hintText:
                                              'Yazı tipi ara veya tam adını yaz…',
                                          suffixIcon: IconButton(
                                            icon: Icon(_fontListOpen
                                                ? Icons.arrow_drop_up
                                                : Icons.arrow_drop_down),
                                            onPressed: () => setState(() =>
                                                _fontListOpen = !_fontListOpen),
                                          ),
                                        ),
                                        onTap: () => setState(
                                            () => _fontListOpen = true),
                                        onChanged: (v) {
                                          setState(() {
                                            _yaziTipi = v;
                                            _fontListOpen = true;
                                          });
                                        },
                                        onSubmitted: (v) => setState(() {
                                          _yaziTipi = v.trim().isEmpty
                                              ? 'Consolas'
                                              : v.trim();
                                          _fontSearch.text = _yaziTipi;
                                          _fontListOpen = false;
                                        }),
                                      ),
                                      if (_fontListOpen)
                                        Builder(builder: (c) {
                                          final q = _fontSearch.text
                                              .trim()
                                              .toLowerCase();
                                          final source =
                                              settings.systemFonts.isNotEmpty
                                                  ? settings.systemFonts
                                                  : kCommonFonts;
                                          final results = source
                                              .where((f) =>
                                                  q.isEmpty ||
                                                  f.toLowerCase().contains(q))
                                              .toList();
                                          if (results.isEmpty)
                                            return const SizedBox.shrink();
                                          return Container(
                                            margin:
                                                const EdgeInsets.only(top: 4),
                                            constraints: const BoxConstraints(
                                                maxHeight: 200),
                                            child: Material(
                                              color: theme.colorScheme
                                                  .surfaceContainerHigh,
                                              clipBehavior: Clip.antiAlias,
                                              shape: RoundedRectangleBorder(
                                                side: BorderSide(
                                                    color: theme
                                                        .colorScheme.outline),
                                                borderRadius:
                                                    BorderRadius.circular(3),
                                              ),
                                            child: ListView.builder(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                      vertical: 2),
                                              shrinkWrap: true,
                                              itemCount: results.length,
                                              itemBuilder: (c2, i) {
                                                final f = results[i];
                                                return ListTile(
                                                  dense: true,
                                                  title: Text(f,
                                                      style: TextStyle(
                                                          fontFamily: f,
                                                          fontSize: 13)),
                                                  onTap: () => setState(() {
                                                    _yaziTipi = f;
                                                    _fontSearch.text = f;
                                                    _fontListOpen = false;
                                                  }),
                                                );
                                              },
                                            ),
                                            ),
                                          );
                                        }),
                                      Padding(
                                        padding: const EdgeInsets.only(top: 4),
                                        child: Text(
                                          settings.systemFonts.isNotEmpty
                                              ? 'Bu liste, backend tarafından cihazınızda kurulu '
                                                  'yazı tiplerinden okundu (${settings.systemFonts.length} font).'
                                              : 'Cihazdaki font listesi backend\'den henüz alınamadı; '
                                                  'aşağıda yaygın fontlardan oluşan bir öneri listesi '
                                                  'gösteriliyor. Kurulu farklı bir font varsa adını '
                                                  'doğrudan yazabilirsiniz; kurulu değilse otomatik '
                                                  'olarak varsayılan yazı tipine düşülür.',
                                          style: TextStyle(
                                              fontSize: 10.5,
                                              color: theme.colorScheme.onSurface
                                                  .withOpacity(0.55)),
                                        ),
                                      ),
                                    ]),
                              ),
                            ]),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Otomatik Tamamlama'),
                          value: _auto,
                          onChanged: (v) => setState(() => _auto = v ?? false),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Otomatik Kaydetme'),
                          value: _autoSave,
                          onChanged: (v) =>
                              setState(() => _autoSave = v ?? false),
                        ),
                      ]),
                      _card(context, Icons.visibility_outlined,
                          'Editör Görünümü', [
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Satır Numaraları'),
                          value: _satirNo,
                          onChanged: (v) =>
                              setState(() => _satirNo = v ?? true),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Kelime Kaydırma (Word Wrap)'),
                          value: _kelimeSar,
                          onChanged: (v) =>
                              setState(() => _kelimeSar = v ?? false),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Boşluk Göstergesi'),
                          subtitle: const Text(
                              'Satır başı/sonundaki ve art arda gelen boşlukları '
                              'nokta (sekmeleri ok) olarak gösterir.',
                              style: TextStyle(fontSize: 11)),
                          value: _boslukGoster,
                          onChanged: (v) =>
                              setState(() => _boslukGoster = v ?? false),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Sütun Çizgileri'),
                          subtitle: const Text(
                              'Sütunlar arasındaki bağlantıyı gösterir.',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool('sutun_cizgileri',
                              fallback: true),
                          onChanged: (v) =>
                              settings.setValue('sutun_cizgileri', v ?? true),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Minimap'),
                          value: settings.getBool('minimap'),
                          onChanged: (v) =>
                              settings.setValue('minimap', v ?? false),
                        ),
                      ]),
                      _card(context, Icons.terminal, 'Terminal', [
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                  'Terminal Yazı Boyutu: ${_terminalFontSize.round()}',
                                  style: const TextStyle(fontSize: 12)),
                              Slider(
                                  value: _terminalFontSize,
                                  min: 8,
                                  max: 28,
                                  divisions: 20,
                                  onChanged: (v) =>
                                      setState(() => _terminalFontSize = v)),
                              Text(
                                'İpucu: İmleci terminal üzerine getirip Ctrl + fare tekerleği ile '
                                'de boyutu değiştirebilirsiniz.',
                                style: TextStyle(
                                    fontSize: 10.5,
                                    color: theme.colorScheme.onSurface
                                        .withOpacity(0.55)),
                              ),
                            ]),
                      ]),
                      _card(context, Icons.auto_awesome, 'AI Asistan', [
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('AI Aktif'),
                          value: _ai,
                          onChanged: (v) => setState(() => _ai = v ?? false),
                        ),
                        DropdownButtonFormField<String>(
                          value: _sag,
                          isExpanded: true,
                          menuMaxHeight: 260,
                          borderRadius: BorderRadius.circular(3),
                          dropdownColor: theme.colorScheme.surfaceContainerHigh,
                          style: TextStyle(
                              color: theme.colorScheme.onSurface, fontSize: 13),
                          decoration: const InputDecoration(
                              labelText: 'Sağlayıcı', isDense: true),
                          items: providers
                              .map((s) =>
                                  DropdownMenuItem(value: s, child: Text(s)))
                              .toList(),
                          onChanged: (v) {
                            if (v == null || v == _sag) return;
                            setState(() {
                              _sag = v;
                              final list = settings.aiModels[_sag] ?? [];
                              _model = list.isNotEmpty ? list.first : '';
                            });
                          },
                        ),
                        DropdownButtonFormField<String>(
                          value: _model,
                          isExpanded: true,
                          menuMaxHeight: 260,
                          borderRadius: BorderRadius.circular(3),
                          dropdownColor: theme.colorScheme.surfaceContainerHigh,
                          style: TextStyle(
                              color: theme.colorScheme.onSurface, fontSize: 13),
                          decoration: const InputDecoration(
                              labelText: 'Model', isDense: true),
                          items: models
                              .map((m) => DropdownMenuItem(
                                  value: m,
                                  child:
                                      Text(m, overflow: TextOverflow.ellipsis)))
                              .toList(),
                          onChanged: (v) =>
                              setState(() => _model = v ?? _model),
                        ),
                        TextField(
                          controller: _apiKey,
                          obscureText: true,
                          decoration: const InputDecoration(
                              labelText: 'API Key', isDense: true),
                        ),
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Sıcaklık: ${_sic.toStringAsFixed(2)}',
                                  style: const TextStyle(fontSize: 12)),
                              Slider(
                                  value: _sic,
                                  min: 0,
                                  max: 2,
                                  divisions: 40,
                                  onChanged: (v) => setState(() => _sic = v)),
                            ]),
                        TextField(
                          controller: _maxTok,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                              labelText: 'Max Token', isDense: true),
                        ),
                        TextField(
                          controller: _sysMsg,
                          maxLines: 6,
                          style: const TextStyle(fontSize: 12),
                          decoration: const InputDecoration(
                              labelText: 'Sistem Mesajı', isDense: true),
                        ),
                      ]),
                      _card(context, Icons.build_outlined, 'Düzeltme', [
                        // Gelişmiş düzeltme arka planda her zaman açıktır;
                        // kapatılamaz (backend de "false" değerini yok
                        // sayar), bu yüzden burada düğme yoktur.
                        Text(
                          'Gelişmiş düzeltme her zaman etkindir: kod arka '
                          'planda çalıştırılarak yazım, girinti, sözdizimi ve '
                          'tanımsız ad hataları otomatik düzeltilir.',
                          style: TextStyle(
                              fontSize: 11.5,
                              color: theme.colorScheme.onSurface
                                  .withOpacity(0.65)),
                        ),
                        TextField(
                          controller: _duzeltmeZamanAsimi,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                              labelText: 'Zaman Aşımı (saniye)', isDense: true),
                        ),
                        TextField(
                          controller: _duzeltmeMesajAraligi,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                              labelText: 'Mesaj Aralığı (karakter)',
                              isDense: true),
                        ),
                        TextField(
                          controller: _duzeltmeMaksDongu,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                              labelText: 'Maksimum Döngü Sayısı',
                              isDense: true),
                        ),
                      ]),
                    ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

// ============================================================================
// DİALOGLAR
// ============================================================================

class StatsDialog extends StatelessWidget {
  const StatsDialog({super.key});
  @override
  Widget build(BuildContext context) {
    final backend = context.read<BackendService>();
    final kod = context.read<EditorProvider>().activeContent.value;
    return AlertDialog(
      title: const Text('Kod İstatistikleri'),
      content: FutureBuilder<Map<String, dynamic>>(
        future: backend.call('istatistik', {'kod': kod}),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const SizedBox(
                width: 320,
                height: 200,
                child:
                    Center(child: CircularProgressIndicator(strokeWidth: 2)));
          }
          if (snap.hasError) return Text('Hata: ${snap.error}');
          final r = snap.data ?? {};
          final rows = <DataRow>[
            DataRow(cells: [
              const DataCell(Text('Toplam Satır')),
              DataCell(Text('${r['toplam_satir']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Kod Satırı')),
              DataCell(Text('${r['kod_satiri']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Yorum Satırı')),
              DataCell(Text('${r['yorum_satiri']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Boş Satır')),
              DataCell(Text('${r['bos_satir']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Karakter')),
              DataCell(Text('${r['karakter']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Boşluksuz Karakter')),
              DataCell(Text('${r['karakter_bosluksuz']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Fonksiyon')),
              DataCell(Text('${r['fonksiyon_sayisi']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Sınıf')),
              DataCell(Text('${r['sinif_sayisi']}'))
            ]),
            DataRow(cells: [
              const DataCell(Text('Değişken')),
              DataCell(Text('${r['degisken_sayisi']}'))
            ]),
          ];
          return SizedBox(
            width: 340,
            child: DataTable(
              columnSpacing: 24,
              columns: const [
                DataColumn(label: Text('Özellik')),
                DataColumn(label: Text('Değer'))
              ],
              rows: rows,
            ),
          );
        },
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat'))
      ],
    );
  }
}

class TodoDialog extends StatelessWidget {
  const TodoDialog({super.key});
  @override
  Widget build(BuildContext context) {
    final backend = context.read<BackendService>();
    final kod = context.read<EditorProvider>().activeContent.value;
    return AlertDialog(
      title: const Text('TODO / FIXME'),
      content: FutureBuilder<Map<String, dynamic>>(
        future: backend.call('todo_bul', {'kod': kod}),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const SizedBox(
                width: 420,
                height: 260,
                child:
                    Center(child: CircularProgressIndicator(strokeWidth: 2)));
          }
          if (snap.hasError) return Text('Hata: ${snap.error}');
          final todos = (snap.data?['todolar'] as List? ?? []);
          if (todos.isEmpty) {
            return const SizedBox(
                width: 420,
                height: 200,
                child: Center(child: Text('TODO bulunamadı.')));
          }
          return SizedBox(
            width: 460,
            height: 320,
            child: ListView.builder(
              itemCount: todos.length,
              itemBuilder: (c, i) {
                final t = Map<String, dynamic>.from(todos[i] as Map);
                final line = (t['satir'] as num? ?? 0).toInt();
                return ListTile(
                  dense: true,
                  leading: Text(t['tip']?.toString() ?? 'TODO',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  title: Text(t['aciklama']?.toString() ?? ''),
                  subtitle: Text('Satır $line'),
                  trailing: IconButton(
                    tooltip: 'Git',
                    icon: const Icon(Icons.near_me, size: 14),
                    onPressed: () {
                      // TODO satırı dosyadaki (model) satırdır; katlama
                      // varken görünüm satırına çevrilerek gidilir.
                      final ed = context.read<EditorProvider>();
                      final git = ed.revealModelLine;
                      final ctrl = ed.uiController;
                      Navigator.pop(context);
                      if (git != null) {
                        git(line);
                      } else if (ctrl != null) {
                        jumpToLineIn(ctrl, line);
                      }
                    },
                  ),
                );
              },
            ),
          );
        },
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat'))
      ],
    );
  }
}

class CodeSearchDialog extends StatefulWidget {
  const CodeSearchDialog({super.key});
  @override
  State<CodeSearchDialog> createState() => _CodeSearchDialogState();
}

class _CodeSearchDialogState extends State<CodeSearchDialog> {
  final TextEditingController _input = TextEditingController();
  String? result;
  bool loading = false;
  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _translate() async {
    final backend = context.read<BackendService>();
    setState(() {
      loading = true;
      result = null;
    });
    try {
      final r =
          await backend.call('kod_arama_cevir', {'giris': _input.text.trim()});
      final buf = StringBuffer();
      buf.writeln('KELİME KARŞILIKLARI');
      final words = r['kelime_karsiliklari'] as List? ?? [];
      if (words.isEmpty) {
        buf.writeln('(Sözlükte eşleşme bulunamadı)');
      } else {
        for (final w in words) {
          if (w is Map) buf.writeln('${w['kelime']}  →  ${w['karsilik']}');
        }
      }
      buf.writeln();
      buf.writeln('TAM KOD ÇEVRİSİ');
      buf.writeln();
      final tam = r['tam_ceviri']?.toString();
      buf.writeln(tam != null && tam.isNotEmpty ? tam : '(Çevrilemedi)');
      // Yanıt beklenirken pencere kapatılmış olabilir (setState after dispose).
      if (!mounted) return;
      setState(() {
        result = buf.toString();
        loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        result = 'Hata: $e';
        loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Kod Arama - Python ⇄ TürKod'),
      content: SizedBox(
        width: 500,
        height: 380,
        child: Column(children: [
          Row(children: [
            Expanded(
              child: TextField(
                controller: _input,
                decoration: const InputDecoration(
                    hintText: 'örn: print, def, if, while...', isDense: true),
                onSubmitted: (_) => _translate(),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
                onPressed: loading ? null : _translate,
                child: const Text('Çevir')),
          ]),
          const SizedBox(height: 10),
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                border: Border.all(
                    color: Theme.of(context).colorScheme.outlineVariant),
                borderRadius: BorderRadius.circular(3),
              ),
              child: loading
                  ? const Center(
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : SingleChildScrollView(
                      child: SelectableText(result ?? 'Sonuç burada görünecek.',
                          style: const TextStyle(
                              fontFamily: kMonoFontFamily,
                              fontFamilyFallback: kMonoFontFallback,
                              fontSize: 12.5,
                              height: 1.35)),
                    ),
            ),
          ),
        ]),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat'))
      ],
    );
  }
}

class AboutSignDialog extends StatefulWidget {
  const AboutSignDialog({super.key});
  @override
  State<AboutSignDialog> createState() => _AboutSignDialogState();
}

class _AboutSignDialogState extends State<AboutSignDialog> {
  // Doğrulama yalnızca bir kez istenir; eskiden FutureBuilder'a build()
  // içinde yeni bir Future verildiği için her yeniden çizimde (tema,
  // pencere boyutu vb.) doğrulama baştan başlıyordu.
  late final Future<List<Map<String, dynamic>>> _future = () {
    final backend = context.read<BackendService>();
    return Future.wait(
        [backend.call('imza_dogrula'), backend.call('dosya_hash')]);
  }();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('TürKod IDE'),
      content: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const SizedBox(
                width: 400,
                height: 160,
                child:
                    Center(child: CircularProgressIndicator(strokeWidth: 2)));
          }
          if (snap.hasError) return Text('Hata: ${snap.error}');
          final imza = snap.data![0];
          final hash = snap.data![1];
          return SizedBox(
            width: 440,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Profesyonel Türkçe Python Editörü',
                  style: TextStyle(fontSize: 13)),
              const SizedBox(height: 12),
              Text('İmza: ${imza['mesaj']}'),
              Text('Detay: ${imza['detay']}'),
              const SizedBox(height: 8),
              SelectableText('SHA-256: ${hash['hash']}',
                  style: const TextStyle(
                      fontFamily: kMonoFontFamily,
                      fontFamilyFallback: kMonoFontFallback,
                      fontSize: 11)),
            ]),
          );
        },
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat'))
      ],
    );
  }
}

class CommandPaletteDialog extends StatefulWidget {
  const CommandPaletteDialog({super.key});
  @override
  State<CommandPaletteDialog> createState() => _CommandPaletteDialogState();
}

class _CommandPaletteDialogState extends State<CommandPaletteDialog> {
  final TextEditingController _search = TextEditingController();
  String _filter = '';
  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final actions = buildAppActions()
        .where((a) => a.label.toLowerCase().contains(_filter.toLowerCase()))
        .toList();
    return AlertDialog(
      title: const Text('Komut Paleti'),
      content: SizedBox(
        width: 480,
        height: 380,
        child: Column(children: [
          TextField(
            controller: _search,
            autofocus: true,
            decoration:
                const InputDecoration(hintText: 'Komut ara...', isDense: true),
            onChanged: (v) => setState(() => _filter = v),
            // Enter: listedeki ilk komutu çalıştır.
            onSubmitted: (_) {
              if (actions.isNotEmpty) Navigator.pop(context, actions.first);
            },
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: actions.length,
              itemBuilder: (c, i) {
                final a = actions[i];
                return ListTile(
                  dense: true,
                  leading: a.icon == null ? null : Icon(a.icon, size: 15),
                  title: Text(a.label, style: const TextStyle(fontSize: 13)),
                  trailing: Text(a.shortcut,
                      style: TextStyle(
                          fontSize: 11,
                          color: Theme.of(context)
                              .colorScheme
                              .onSurface
                              .withOpacity(0.55))),
                  // Eylem, paletin kapanan bağlamında değil çağıranın
                  // bağlamında çalıştırılır (bkz. view.palette). Eskiden
                  // palet bağlamı bir süre sonra geçersiz kaldığından
                  // "Düzelt"in ilerleme penceresi hiç kapanmıyor, "Klasör
                  // Aç" gibi eylemler sessizce hiçbir şey yapmıyordu.
                  onTap: () => Navigator.pop(context, a),
                );
              },
            ),
          ),
        ]),
      ),
    );
  }
}

// ============================================================================
// DURUM ÇUBUĞU (statusMessage yok)
// ============================================================================

class StatusBar extends StatelessWidget {
  final List<AppAction> actions;
  const StatusBar({super.key, required this.actions});
  @override
  Widget build(BuildContext context) {
    final ui = context.watch<UiProvider>();
    final ed = context.watch<EditorProvider>();
    final theme = Theme.of(context);
    final statusIds = [
      'tools.stats',
      'tools.todo',
      'tools.codesearch',
      'help.about'
    ];
    return Container(
      height: 24,
      color: theme.colorScheme.surfaceContainer,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(children: [
        // Expanded + sağa hizalama: öğeler her zaman en sağda durur. (Önceki
        // Spacer + Flexible(flex: 4) düzeni, metin kısa olduğunda boş alanı
        // dağıtmadığı için satırı ortaya kaydırıyordu.) Uzun hata/uyarı metni
        // "…" ile kısalır; tamamı fare üzerine gelince görünür.
        Expanded(
          child: ui.syntaxStatus.isEmpty
              ? const SizedBox.shrink()
              : Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                    padding: const EdgeInsets.only(right: 12),
                    child: Tooltip(
                      message: ui.syntaxTooltip.isNotEmpty
                          ? ui.syntaxTooltip
                          : ui.syntaxStatus,
                      waitDuration: const Duration(milliseconds: 400),
                      child: Text(ui.syntaxStatus,
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                          style: TextStyle(
                              fontSize: 11,
                              color: ui.syntaxStatus.startsWith('✓')
                                  ? Colors.green
                                  : ui.syntaxStatus.startsWith('⚠')
                                      ? Colors.orange.shade700
                                      : theme.colorScheme.error)),
                    ),
                  ),
                ),
        ),
        Text('Satır ${ui.cursorLine}, Sütun ${ui.cursorColumn}',
            style: TextStyle(
                fontSize: 11,
                color: theme.colorScheme.onSurface.withOpacity(0.8))),
        const SizedBox(width: 12),
        Text(ed.activeTab?.name ?? 'Dosya Yok',
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
                fontSize: 11,
                color: theme.colorScheme.onSurface.withOpacity(0.8))),
        const SizedBox(width: 12),
        Text('UTF-8',
            style: TextStyle(
                fontSize: 11,
                color: theme.colorScheme.onSurface.withOpacity(0.8))),
        for (final id in statusIds)
          Builder(builder: (c) {
            final a = findAction(actions, id);
            if (a == null || a.icon == null) return const SizedBox.shrink();
            return IconButton(
              tooltip: a.label,
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 22, minHeight: 22),
              icon: Icon(a.icon, size: 13),
              onPressed: () => a.run(context),
            );
          }),
      ]),
    );
  }
}

// ============================================================================
// ANA LAYOUT (AI paneli Gezgin ile aynı boyda, animasyonlu paneller)
// ============================================================================

class AppLayout extends StatelessWidget {
  final List<AppAction> actions;
  const AppLayout({super.key, required this.actions});
  @override
  Widget build(BuildContext context) {
    // UiProvider imleç konumu için de bildirim yapar (her tuş vuruşunda);
    // yerleşimin tamamını yeniden kurmamak için yalnızca panel alanları
    // izlenir. Aynı şekilde EditorProvider'dan yalnızca aktif yol izlenir.
    final ui = context.read<UiProvider>();
    context.select<UiProvider, Object>((u) => (
          u.showExplorer,
          u.showAi,
          u.showTerminal,
          u.sidebarWidth,
          u.aiWidth,
          u.terminalHeight,
        ));
    final activePath =
        context.select<EditorProvider, String?>((e) => e.activeTab?.path);
    final isSettings = activePath == kSettingsPath;
    return Column(children: [
      AppTitleBar(actions: actions),
      Expanded(
        child: LayoutBuilder(builder: (context, kisit) {
        // Panel boyutları pencereye sığdırılır: geniş kenar paneliyle AI
        // paneli küçük (ör. yarım ekran) bir pencerede editörü sıfır
        // genişliğe itip taşma (overflow) şeritleri oluşturuyordu.
        const minEditorGenislik = 260.0;
        const tutamaclar = 12.0;
        var kenar = ui.showExplorer ? ui.sidebarWidth : 0.0;
        var aiG = ui.showAi ? ui.aiWidth : 0.0;
        final kullanilabilir = kisit.maxWidth - minEditorGenislik - tutamaclar;
        if (kenar + aiG > kullanilabilir && kenar + aiG > 0) {
          final oran = math.max(0.0, kullanilabilir) / (kenar + aiG);
          kenar *= oran;
          aiG *= oran;
        }
        final kenarIc = ui.showExplorer ? kenar : ui.sidebarWidth;
        final aiIc = ui.showAi ? aiG : ui.aiWidth;
        return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            width: kenar,
            child: ClipRect(
              child: OverflowBox(
                alignment: Alignment.topLeft,
                minWidth: kenarIc,
                maxWidth: kenarIc,
                child: const FileTreePanel(),
              ),
            ),
          ),
          if (ui.showExplorer)
            _HGrip((d) => ui.setSidebarWidth(ui.sidebarWidth + d)),
          Expanded(
            child: LayoutBuilder(builder: (context, ic) {
              // Terminal yüksekliği de sığdırılır (araç çubuğu + sekmeler +
              // en az 100 px editör kalacak şekilde).
              final terminalH = math.max(
                  0.0,
                  math.min(ui.terminalHeight,
                      ic.maxHeight - 38 - 1 - 47 - 6 - 100));
              return Column(
                  mainAxisAlignment: MainAxisAlignment.start, children: [
              TopToolbar(actions: actions),
              Divider(
                  height: 1,
                  color: Theme.of(context).colorScheme.outlineVariant),
              const EditorTabsBar(),
              Expanded(
                child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(
                        child: isSettings
                            ? const SettingsPage()
                            : CodeEditor(key: ValueKey(activePath ?? 'bos')),
                      ),
                    ]),
              ),
              if (ui.showTerminal) ...[
                _VGrip((d) => ui.setTerminalHeight(ui.terminalHeight - d)),
                AnimatedContainer(
                  duration: kAnim,
                  curve: kAnimCurve,
                  height: ui.showTerminal ? terminalH : 0,
                  child: ClipRect(
                    child: OverflowBox(
                        alignment: Alignment.topLeft,
                        minHeight: terminalH,
                        maxHeight: terminalH,
                        child: const TerminalPanel()),
                  ),
                ),
              ],
            ]);
            }),
          ),
          if (ui.showAi) _HGrip((d) => ui.setAiWidth(ui.aiWidth - d)),
          AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            width: aiG,
            child: ClipRect(
              child: OverflowBox(
                alignment: Alignment.topLeft,
                minWidth: aiIc,
                maxWidth: aiIc,
                child: const AiPanel(),
              ),
            ),
          ),
        ]);
        }),
      ),
      StatusBar(actions: actions),
    ]);
  }
}

// ============================================================================
// HOME + APP
// ============================================================================

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  Timer? _autosaveTimer;
  // command-id -> activator eşlemesi build() içinde her seferinde tazelenir;
  // asıl tuş dinleyicisi ise odak nerede olursa olsun (kod editöründeki
  // TextField dahil) tetiklensin diye donanım seviyesinde çalışır.
  Map<ShortcutActivator, VoidCallback> _shortcuts = {};

  // Pencere kapatılırken (X, Alt+F4) kaydedilmemiş dosya değişiklikleri
  // sorulur. Eskiden oturum yalnızca dosya YOLLARINI sakladığından açık bir
  // dosyada yapılan kaydedilmemiş değişiklikler sessizce kayboluyordu.
  late final AppLifecycleListener _cikisDinleyici =
      AppLifecycleListener(onExitRequested: _cikisIstendi);
  bool _cikisSoruluyor = false;

  Future<AppExitResponse> _cikisIstendi() async {
    if (!mounted) return AppExitResponse.exit;
    final ed = context.read<EditorProvider>();
    final kirli = ed.tabs
        .where((t) =>
            t.dirty &&
            t.path != kSettingsPath &&
            !t.path.startsWith('untitled:'))
        .toList();
    if (kirli.isEmpty) {
      // Adsız sekmelerin içeriği oturumda saklanır (yeniden açılınca gelir).
      await ed.saveSessionNow();
      return AppExitResponse.exit;
    }
    if (_cikisSoruluyor) return AppExitResponse.cancel;
    _cikisSoruluyor = true;
    try {
      final adlar = kirli.map((t) => '• ${t.name}').take(8).join('\n');
      final secim = await showDialog<String>(
        context: context,
        builder: (dc) => AlertDialog(
          title: const Text('Kaydedilmemiş değişiklikler'),
          content: Text('Şu dosyalarda kaydedilmemiş değişiklikler var:\n\n'
              '$adlar\n\nÇıkmadan önce kaydedilsin mi?'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dc, 'iptal'),
                child: const Text('İptal')),
            OutlinedButton(
                onPressed: () => Navigator.pop(dc, 'kaydetme'),
                child: const Text('Kaydetmeden Çık')),
            FilledButton(
                onPressed: () => Navigator.pop(dc, 'kaydet'),
                child: const Text('Kaydet ve Çık')),
          ],
        ),
      );
      if (secim == 'kaydet') {
        // Yanıt vermeyen bir backend pencereyi dakikalarca açık tutmasın.
        final ok = await ed
            .saveAllForExit()
            .timeout(const Duration(seconds: 15), onTimeout: () => false);
        if (ok) return AppExitResponse.exit;
        if (mounted) {
          showAppSnackbar(context,
              'Dosyalar kaydedilemedi; çıkış iptal edildi.',
              kind: SnackKind.error);
        }
        return AppExitResponse.cancel;
      }
      if (secim == 'kaydetme') {
        await ed.saveSessionNow();
        return AppExitResponse.exit;
      }
      return AppExitResponse.cancel;
    } finally {
      _cikisSoruluyor = false;
    }
  }

  @override
  void initState() {
    super.initState();
    _cikisDinleyici; // dinleyiciyi oluştur
    _scheduleAutoSave();
    HardwareKeyboard.instance.addHandler(_onHardwareKey);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final backend = context.read<BackendService>();
        await backend.waitUntilConnected();
        await Future.delayed(const Duration(seconds: 3));
        if (!mounted) return;
        await guncellemeKontrolEt(context, backend.call, kaydet: context.read<EditorProvider>().saveAllForExit);
      } catch (_) {}
    });
  }

  // NOT: CallbackShortcuts/Shortcuts widget'ları odak-tabanlı bir ağaçta
  // (Focus node bubbling) çalışır. Kod editöründeki TextField/EditableText
  // odaktayken birçok tuş kombinasyonunu kendi içinde işleyip üst widget'lara
  // hiç iletmiyor; bu yüzden Ctrl+S, Ctrl+F gibi genel kısayollar editör
  // odaktayken tetiklenmiyordu. Çözüm: HardwareKeyboard seviyesinde, odaktan
  // tamamen bağımsız bir dinleyici kullanmak — bu, Flutter'ın normal
  // odak-tabanlı tuş dağıtımından ÖNCE çalışır ve editörün kendi yerel tuş
  // işleyicisiyle (parantez/tırnak otomatik kapama, Tab girinti, Alt+Yukarı/
  // Aşağı vb.) çakışmaz çünkü buradaki kısayolların hiçbiri o kombinasyonlarla
  // örtüşmüyor (hepsi Ctrl/Alt/F-tuşu içeriyor, düz karakter veya salt Tab
  // yok).
  // Yalnızca kod editörü odaktayken anlamlı olan (metni değiştiren)
  // kısayollar: terminal/AI/ayar alanındayken Alt+↑ editörde satır
  // taşıyordu.
  static const Set<String> _yalnizEditorKisayollari = {
    'edit.comment',
    'edit.duplicate',
    'edit.move_up',
    'edit.move_down',
  };
  Map<ShortcutActivator, String> _shortcutIds = {};

  bool _odakEditordeMi() {
    // Editörün KENDİ odak düğümü (ya da onun altı) odaktaysa. Bul/Değiştir
    // kutusu da editörün widget alt ağacında olduğundan eski "ata State"
    // denetimi orada yazarken Alt+↑ ile kod satırı taşınmasına izin veriyordu.
    final node = context.read<EditorProvider>().editorFocusNode;
    final birincil = FocusManager.instance.primaryFocus;
    if (node == null || birincil == null) return false;
    return birincil == node || birincil.ancestors.contains(node);
  }

  bool _onHardwareKey(KeyEvent event) {
    if (event is! KeyDownEvent) return false;
    if (!mounted) return false;
    // Bir pencere (diyalog, komut paleti, açılır menü) açıkken arkadaki
    // uygulamada kısayol çalışmasın: eskiden palet açıkken Ctrl+R kodu
    // çalıştırıyordu. Navigator.canPop bağımlılık kaydetmez (ModalRoute.of
    // her diyalog açılışında tüm kabuğu yeniden kuruyordu).
    if (Navigator.maybeOf(context)?.canPop() ?? false) return false;
    for (final entry in _shortcuts.entries) {
      if (entry.key.accepts(event, HardwareKeyboard.instance)) {
        final id = _shortcutIds[entry.key];
        if (id != null &&
            _yalnizEditorKisayollari.contains(id) &&
            !_odakEditordeMi()) {
          return false;
        }
        entry.value();
        return true;
      }
    }
    return false;
  }

  /// Otomatik kaydetme aralığı ayardan okunur (app.py parity).
  void _scheduleAutoSave() {
    _autosaveTimer?.cancel();
    final secs = context
        .read<SettingsProvider>()
        .getInt('otomatik_kaydetme_aralik', fallback: 30)
        .clamp(5, 600);
    _autosaveTimer = Timer(Duration(seconds: secs), () {
      if (!mounted) return;
      if (context.read<SettingsProvider>().getBool('otomatik_kaydetme')) {
        context.read<EditorProvider>().autoSave();
      }
      _scheduleAutoSave();
    });
  }

  @override
  void dispose() {
    _autosaveTimer?.cancel();
    _cikisDinleyici.dispose();
    HardwareKeyboard.instance.removeHandler(_onHardwareKey);
    super.dispose();
  }

  // Eylem listesi ve ana yerleşim bir kez kurulur. Aynı widget örneği
  // döndürüldüğü için bildirim kutusu (toast) değişimlerinde AppLayout ve
  // altındaki editör yeniden kurulmaz.
  late final List<AppAction> _actions = buildAppActions();
  late final Widget _body = Column(children: [
    const ConnectionBanner(),
    Expanded(child: AppLayout(actions: _actions)),
  ]);

  @override
  Widget build(BuildContext context) {
    _shortcuts = {
      for (final a in _actions)
        if (a.activator != null) a.activator!: () => a.run(context),
    };
    _shortcutIds = {
      for (final a in _actions)
        if (a.activator != null) a.activator!: a.id,
    };

    // Yalnızca bildirim alanları izlenir (eskiden UiProvider'ın tamamı
    // izlendiği için her imleç hareketinde bütün uygulama yeniden
    // kuruluyordu).
    final ui = context.read<UiProvider>();
    context.select<UiProvider, Object?>(
        (u) => (u.toastHistoryOpen, u.toast, u.toastKind, u.toastHistory.length));

    return Focus(
      autofocus: true,
      child: Scaffold(
        body: Stack(children: [
          _body,
          if (ui.toastHistoryOpen)
            Positioned(
              right: 12,
              bottom: 32,
              child: _ToastHistoryPanel(
                items: ui.toastHistory,
                onClose: ui.toggleToastHistory,
                onClear: ui.clearToastHistory,
              ),
            ),
          if (!ui.toastHistoryOpen && ui.toast != null)
            Positioned(
              right: 12,
              bottom: 32,
              child: _ToastBox(
                msg: ui.toast!,
                kind: ui.toastKind,
                onHistory: ui.toggleToastHistory,
                onClose: ui.dismissToast,
              ),
            ),
        ]),
      ),
    );
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Düşük bellekli makineler (ör. 2 GB RAM): uygulama neredeyse hiç görsel
  // kullanmaz; varsayılan 100 MB / 1000 görsellik önbellek sınırı gereksizdir.
  PaintingBinding.instance.imageCache
    ..maximumSizeBytes = 16 << 20
    ..maximumSize = 100;
  runApp(const TurkodApp());
}

class TurkodApp extends StatefulWidget {
  const TurkodApp({super.key});
  @override
  State<TurkodApp> createState() => _TurkodAppState();
}

class _TurkodAppState extends State<TurkodApp> {
  // Backend hazır olana kadar açılış ekranı gösterilir (önce backend, sonra arayüz).
  bool _hazir = false;
  String? _acilisHatasi;

  Future<void> _baslat() async {
    _acilisHatasi = null;
    try {
      if (!await _launcher.launch()) {
        _acilisHatasi = _launcher.sonHata ?? 'Python backend başlatılamadı.';
      }
    } catch (e) {
      _acilisHatasi = '$e';
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

  late final BackendService _backend;
  late final BackendLauncher _launcher;
  @override
  void initState() {
    super.initState();
    _backend = BackendService();
    _launcher = BackendLauncher();
    unawaited(_baslat());
  }

  @override
  void dispose() {
    _launcher.dispose();
    _backend.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_hazir) {
      return AcilisEkrani(
        hata: _acilisHatasi,
        onYenidenDene: () {
          setState(() => _acilisHatasi = null);
          unawaited(_baslat());
        },
        onYineDeAc: _yineDeAc,
      );
    }
    return MultiProvider(
      providers: [
        Provider<BackendService>.value(value: _backend),
        ChangeNotifierProvider(
            create: (_) => ConnectionProvider(_backend, _launcher)),
        ChangeNotifierProvider(create: (_) => UiProvider(_launcher)),
        ChangeNotifierProvider(create: (_) => SettingsProvider(_backend)),
        ChangeNotifierProvider(create: (_) => LanguageProvider(_backend)),
        ChangeNotifierProvider(create: (_) => EditorProvider(_backend)),
        ChangeNotifierProvider(create: (_) => FileTreeProvider(_backend)),
        ChangeNotifierProvider(create: (_) => TerminalProvider(_backend)),
        ChangeNotifierProvider(create: (_) => AiProvider(_backend)),
        ChangeNotifierProvider(
            create: (c) =>
                BreakpointProvider(_backend, c.read<EditorProvider>())),
        ChangeNotifierProvider(create: (_) => FixProvider(_backend)),
      ],
      child: Consumer<SettingsProvider>(
        builder: (context, settings, _) {
          final themeName = settings.getString('tema', fallback: 'Modern Koyu');
          final theme = AppThemeRegistry.build(themeName);
          return MaterialApp(
            title: 'TürKod IDE',
            debugShowCheckedModeBanner: false,
            theme: theme,
            home: const HomeShell(),
          );
        },
      ),
    );
  }
}
