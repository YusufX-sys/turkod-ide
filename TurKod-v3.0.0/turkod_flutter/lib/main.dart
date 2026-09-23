import 'dart:async';
import 'guncelleme.dart';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/gestures.dart'; // PointerScrollEvent buradan gelir
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path/path.dart' as p;
import 'package:re_editor/re_editor.dart' as re;
import 'acilis_ekrani.dart';

// ============================================================================
// SABİTLER
// ============================================================================
const String kMonoFontFamily = 'Consolas';
const List<String> kMonoFontFallback = ['Menlo', 'Courier New', 'monospace'];

/// Ayarlar sekmesi özel bir sekmedir; dosya gibi davranmaz.
const String kSettingsPath = 'internal:settings';

/// Terminal çıktısı için maksimum karakter sayısı.
const int kMaxTermChars = 500000;

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
  final String path;
  final String name;
  String content;
  bool dirty;
  EditorTab({
    required this.path,
    required this.name,
    required this.content,
    this.dirty = false,
  });
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

class FixResult {
  final String code;
  final String diff;
  final List<String> changes;
  FixResult({required this.code, required this.diff, required this.changes});
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

  static Future<String> get wsUrl async {
    final port = await discoverPort();
    return 'ws://127.0.0.1:$port/ws';
  }

    /// Backend exe yolu (kurulum düzeni: <exe>\backend\turkod_backend.exe).
  static String get backendExe => p.join(
      p.dirname(Platform.resolvedExecutable), 'backend', 'turkod_backend.exe');

  /// Paketlenmiş backend: <uygulama klasörü>\backend\turkod_backend.exe
  static String get packagedBackendExe => p.join(
      p.dirname(Platform.resolvedExecutable), 'backend', 'turkod_backend.exe');

  /// EXE modunda mı çalışıyoruz? backend\turkod_backend.exe yanımızdaysa evet.
  /// (`flutter run` sırasında bu dosya olmadığından geliştirme moduna düşer.)
  static bool get isExeMode =>
      Platform.isWindows && File(packagedBackendExe).existsSync();


  /// Dev modda repo kökü: flutter projesinin üst klasörü.
  static String get _repoKok => p.dirname(Directory.current.path);

  /// Backend başlatma komutu.
  static List<String> backendCommand() {
    if (isExeMode) {
      // --parent-pid: arayüz (bu süreç) hangi yolla kapanırsa kapansın backend
      // kendini ve çalıştırdığı programları kapatır.
      return [packagedBackendExe, '--backend', '--parent-pid', '$pid'];
    }
    if (Platform.isWindows) return ['python', '-u', '-m', 'turkod_ide.server'];
    return ['python3', '-u', '-m', 'turkod_ide.server'];
  }

  /// Backend çalışma dizini (dev modda repo kökü gerekli).
  static String backendWorkingDir() =>
    isExeMode ? p.dirname(backendExe) : _repoKok;
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
            final konum = satir != null
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
    _channel!.sink
        .add(jsonEncode({'id': id, 'command': command, 'params': params}));
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

class BackendLauncher {
  Process? _process;
  bool _startedByUs = false;
  final StreamController<String> errors = StreamController.broadcast();
  Future<void> launch() async {
    if (!AppConfig.isExeMode && await _isServerRunning()) return;
    try {
      // Önceki oturumdan kalan (ölü) port dosyası yeni backend'in portuyla karışmasın.
      final eski = File(AppConfig._portFile);
      if (eski.existsSync()) eski.deleteSync();
    } catch (_) {}
    try {
      if (AppConfig.isExeMode) {
        // Her arayüz kendi backend'ini BOŞ bir porta açar: önceki oturumlardan kalan
        // backend'lere ya da bayat port dosyasına takılmaz.
        final s = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
        AppConfig._portOverride = s.port;
        await s.close();
      }
      final cmd = AppConfig.backendCommand();
      if (AppConfig._portOverride != null) {
        cmd.addAll(['--port', '${AppConfig._portOverride}']);
      }
      _process = await Process.start(
        cmd.first,
        cmd.skip(1).toList(),
        workingDirectory: AppConfig.backendWorkingDir(),
        mode: ProcessStartMode.detachedWithStdio,
      );
      _startedByUs = true;
    } catch (e) {
      errors.add('Python backend başlatılamadı: $e');
      return;
    }
    final ok = await _waitForPort();
    if (!ok) {
      errors.add('Python backend başlatılamadı: sunucu portu açılamadı '
          '(server.py çalışıyor mu?)');
    }
  }

  Future<bool> _isServerRunning() async {
    try {
      final port = await AppConfig.discoverPort(retries: 1, delayMs: 100);
      final s = await Socket.connect('127.0.0.1', port,
          timeout: const Duration(milliseconds: 500));
      await s.close();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> _waitForPort() async {
    for (var i = 0; i < 90; i++) {
      if (await _isServerRunning()) return true;
      await Future.delayed(const Duration(milliseconds: 500));
    }
    return false;
  }

  void dispose() {
    if (!_startedByUs || _process == null) return;
    if (Platform.isWindows) {
      Process.run('taskkill', ['/F', '/T', '/PID', '${_process!.pid}']);
    } else {
      _process!.kill(ProcessSignal.sigterm);
    }
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

int _lineNumber(String text, int offset) =>
    text.substring(0, offset.clamp(0, text.length)).split('\n').length;
int _columnNumber(String text, int offset) => offset - _lineStart(text, offset);
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
  c.value = TextEditingValue(
    text: t.replaceRange(ls, le, nb),
    selection: TextSelection(baseOffset: ls, extentOffset: ls + nb.length),
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
  c.value = TextEditingValue(
    text: nt,
    selection: TextSelection.collapsed(offset: end + block.length + 1),
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
  c.value = TextEditingValue(
    text: nt,
    selection: TextSelection.collapsed(offset: newPos),
  );
}

/// Bir satırın başlangıç offset'ine imleci koyar (listener kaydırmayı yapar).
void jumpToLine(BuildContext context, int line) {
  final c = context.read<EditorProvider>().uiController;
  if (c == null) return;
  final lines = c.text.split('\n');
  if (line < 1 || line > lines.length) return;
  var off = 0;
  for (var i = 0; i < line - 1; i++) {
    off += lines[i].length + 1;
  }
  c.selection = TextSelection.collapsed(offset: off.clamp(0, c.text.length));
}

// ============================================================================
// PROVIDER'LAR
// ============================================================================
class ConnectionProvider extends ChangeNotifier {
  final BackendService _backend;
  late final StreamSubscription<bool> _sub;
  bool _connected = false;
  bool get connected => _connected;
  ConnectionProvider(this._backend) {
    _connected = _backend.isConnected;
    _sub = _backend.connectionStream.listen((c) {
      _connected = c;
      notifyListeners();
    });
  }
  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
}

enum SnackKind { info, success, error }

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
  Offset findOffset = Offset.zero;
  bool findOpen = false;
  bool findReplaceMode = false;
  String findQuery = '';
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

  void setSyntaxStatus(String m) {
    if (syntaxStatus == m) return;
    syntaxStatus = m;
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
    toast = msg;
    toastKind = kind;
    _toastTimer?.cancel();
    _toastTimer = Timer(const Duration(seconds: 4), () {
      toast = null;
      notifyListeners();
    });
    notifyListeners();
  }

  void openFind(bool replace) {
    findOpen = true;
    findReplaceMode = replace;
    notifyListeners();
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
    ];
    for (final k in keys) {
      try {
        final r = await _backend.call('ayar_get', {'anahtar': k});
        _values[k] = r['deger'];
      } catch (_) {}
    }
    await refreshModels(silent: true);
    await refreshSystemFonts(silent: true);
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

  /// Oturum: yol (String eski biçim) veya {yol,isim,icerik} map'i desteklenir.
  Future<void> loadSession() async {
    if (_sessionLoaded) return;
    try {
      final r = await _backend.call('oturum_oku');
      final rawList = r['son_oturum'] as List? ?? [];
      for (final e in rawList) {
        try {
          if (e is String) {
            if (e != kSettingsPath) {
              await openFile(e, makeActive: false, saveSession: false);
            }
          } else if (e is Map) {
            final m = Map<String, dynamic>.from(e);
            final yol = m['yol']?.toString();
            final isim = m['isim']?.toString();
            final icerik = m['icerik']?.toString() ?? '';
            if (yol != null && yol.isNotEmpty && yol != kSettingsPath) {
              await openFile(yol, makeActive: false, saveSession: false);
            } else if (isim != null && isim.isNotEmpty) {
              createUntitled(name: isim, content: icerik, setActive: false);
            }
          }
        } catch (_) {}
      }
      if (_tabs.isNotEmpty) {
        final raw = r['son_oturum_aktif'];
        final idx = raw is int ? raw : int.tryParse(raw.toString()) ?? 0;
        _active = idx.clamp(0, _tabs.length - 1);
        activeContent.value = _tabs[_active].content;
      }
      _sessionLoaded = true;
      _revision++;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> _saveSession() async {
    try {
      await _backend.call('oturum_kaydet', {
        'sekmeler': _tabs
            .where((t) => t.path != kSettingsPath)
            .map((t) => t.path.startsWith('untitled:')
                ? {'yol': null, 'isim': t.name, 'icerik': t.content}
                : {'yol': t.path, 'isim': t.name, 'icerik': null})
            .toList(),
        'aktif_sira': _active < 0 ? 0 : _active,
      });
    } catch (_) {}
  }

  Future<void> openFile(String path,
      {bool makeActive = true, bool saveSession = true}) async {
    final idx = _tabs.indexWhere((t) => t.path == path);
    if (idx >= 0) {
      if (makeActive) setActive(idx);
      return;
    }
    final r = await _backend.call('dosya_oku', {'yol': path});
    _tabs.add(EditorTab(
      path: r['yol']?.toString() ?? path,
      name: r['isim']?.toString() ?? p.basename(path),
      content: r['icerik']?.toString() ?? '',
    ));
    if (makeActive) {
      _active = _tabs.length - 1;
      activeContent.value = _tabs[_active].content;
    }
    _revision++;
    notifyListeners();
    if (saveSession) _saveSession();
  }

  void createUntitled(
      {String? name, String content = '', bool setActive = true}) {
    final n = name ?? 'Untitled-${_untitledCounter++}.trpy';
    _tabs.add(EditorTab(path: 'untitled:$n', name: n, content: content));
    if (setActive) {
      _active = _tabs.length - 1;
      activeContent.value = content;
    }
    _revision++;
    notifyListeners();
    _saveSession();
  }

  void openSettings() {
    final i = _tabs.indexWhere((t) => t.path == kSettingsPath);
    if (i >= 0) {
      setActive(i);
      return;
    }
    _tabs.add(EditorTab(path: kSettingsPath, name: 'Ayarlar', content: ''));
    _active = _tabs.length - 1;
    activeContent.value = '';
    _revision++;
    notifyListeners();
  }

  void setActive(int index) {
    if (index < 0 || index >= _tabs.length || _active == index) return;
    _active = index;
    activeContent.value = _tabs[index].content;
    _revision++;
    notifyListeners();
    _saveSession();
  }

  void updateContent(String val) {
    final t = activeTab;
    if (t == null || t.path == kSettingsPath || t.content == val) return;
    t.content = val;
    activeContent.value = val;
    if (!t.dirty) {
      t.dirty = true;
      notifyListeners();
    }
  }

  void replaceActiveContent(String val) {
    final t = activeTab;
    if (t == null || t.path == kSettingsPath) return;
    t.content = val;
    t.dirty = true;
    activeContent.value = val;
    _revision++;
    notifyListeners();
  }

  Future<void> saveTab(int index) async {
    if (index < 0 || index >= _tabs.length) return;
    final t = _tabs[index];
    if (t.path == kSettingsPath) return;
    if (t.path.startsWith('untitled:')) {
      await saveAsTab(index);
      return;
    }
    await _backend.call('dosya_kaydet', {'yol': t.path, 'icerik': t.content});
    t.dirty = false;
    notifyListeners();
  }

  Future<void> saveActive() async {
    if (_active >= 0) await saveTab(_active);
  }

  Future<void> saveAsTab(int index) async {
    if (index < 0 || index >= _tabs.length) return;
    final t = _tabs[index];
    if (t.path == kSettingsPath) return;
    final path = await FilePicker.platform.saveFile(fileName: t.name);
    if (path == null || path.isEmpty) return;
    await _backend.call('dosya_kaydet', {'yol': path, 'icerik': t.content});
    _tabs[index] =
        EditorTab(path: path, name: p.basename(path), content: t.content);
    activeContent.value = t.content;
    notifyListeners();
    _saveSession();
  }

  Future<void> saveAsActive() async {
    if (_active >= 0) await saveAsTab(_active);
  }

  Future<void> closeTab(int index) async {
    if (index < 0 || index >= _tabs.length) return;
    final wasActive = index == _active;
    _tabs.removeAt(index);
    if (_tabs.isEmpty) {
      _active = -1;
      activeContent.value = '';
    } else if (_active > index) {
      _active--;
      activeContent.value = _tabs[_active].content;
    } else if (wasActive) {
      _active = index.clamp(0, _tabs.length - 1);
      activeContent.value = _tabs[_active].content;
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


  void autoSave() {
    final t = activeTab;
    if (t == null || !t.dirty) return;
    if (t.path.startsWith('untitled:') || t.path == kSettingsPath) return;
    _backend
        .call('dosya_kaydet', {'yol': t.path, 'icerik': t.content}).then((_) {
      t.dirty = false;
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

  Future<void> toggleExpand(FileNode node) async {
    if (!node.isDir) return;
    if (!node.expanded && !node.loaded) {
      try {
        final r = await _backend.call('dosya_agaci', {'dizin': node.path});
        node.children = _parse(r['ogeler']);
        node.loaded = true;
      } catch (_) {
        node.children = [];
        node.loaded = true;
      }
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
  bool _trimmed = false;
  String get output => _output.toString();
  bool get isRunning => _running;
  TerminalProvider(this._backend) {
    _sub = _backend.events.listen(_onEvent);
  }
  void _onEvent(BackendEvent e) {
    if (e.name == 'calistirma_cikti') {
      _append(e.data['metin']?.toString() ?? '');
      notifyListeners();
    } else if (e.name == 'calistirma_bitti') {
      _running = false;
      _append('\n[Süreç ${e.data['cikis_kodu'] ?? '?'} koduyla çıktı]\n');
      notifyListeners();
    } else if (e.name == 'terminal_cikti') {
      _append(e.data['metin']?.toString() ?? '');
      notifyListeners();
    }
  }

  void _append(String s) {
    _output.write(s);
    if (_output.length > kMaxTermChars) {
      final keep = _output.toString().substring(_output.length - kMaxTermChars);
      _output
        ..clear()
        ..write('[... kesildi ...]\n')
        ..write(keep);
      _trimmed = true;
    }
  }

  Future<void> run(String kod) async {
    _output.clear();
    _trimmed = false;
    _running = true;
    _append('> Çalıştırılıyor...\n');
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

  Future<void> stop() async {
    try {
      await _backend.call('calistir_durdur');
      _append('[Durduruldu]\n');
    } catch (_) {}
    notifyListeners();
  }

  Future<void> sendCommand(String cmd) async {
    if (cmd.trim().isEmpty) return;
    _append('> $cmd\n');
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
    _trimmed = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _sub.cancel();
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

class BreakpointProvider extends ChangeNotifier {
  final BackendService _backend;
  final Set<int> _bps = {};
  bool _debugging = false;
  int _currentLine = 0;
  String? notice;
  Set<int> get breakpoints => Set.unmodifiable(_bps);
  bool get debugging => _debugging;
  int get currentLine => _currentLine;
  BreakpointProvider(this._backend) {
    _init();
  }
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      final r = await _backend.call('breakpoint_list');
      _update(r);
      notifyListeners();
    } catch (_) {}
  }

  void _update(Map<String, dynamic> r) {
    _bps.clear();
    if (r['breakpoints'] is List) {
      for (var b in r['breakpoints'] as List) {
        final l = int.tryParse(b.toString());
        if (l != null) _bps.add(l);
      }
    }
    _debugging = r['calistiriliyor'] == true;
    _currentLine = r['mevcut_satir'] is int ? r['mevcut_satir'] as int : 0;
  }

  void clearNotice() {
    if (notice != null) {
      notice = null;
      notifyListeners();
    }
  }

  Future<void> toggle(int line) async {
    try {
      final r = await _backend.call('breakpoint_toggle', {'satir': line});
      _update(r);
    } catch (e) {
      notice = e.toString();
    }
    notifyListeners();
  }

  Future<void> start({String? kod}) async {
    try {
      final r =
          await _backend.call('debug_baslat', {if (kod != null) 'kod': kod});
      _update(r);
      notice = 'Debugger aktif: breakpoint takibi.';
    } catch (e) {
      _debugging = false;
      notice = e.toString();
    }
    notifyListeners();
  }

  Future<void> step() async {
    try {
      final r = await _backend.call('debug_adim');
      _update(r);
    } catch (e) {
      notice = e.toString();
    }
    notifyListeners();
  }

  Future<void> continueRun() async {
    try {
      final r = await _backend.call('debug_devam');
      _update(r);
    } catch (e) {
      notice = e.toString();
    }
    notifyListeners();
  }

  Future<void> stop() async {
    try {
      final r = await _backend.call('debug_durdur');
      _update(r);
    } catch (e) {
      notice = e.toString();
    }
    notifyListeners();
  }
}

class FixProvider extends ChangeNotifier {
  final BackendService _backend;
  late final StreamSubscription<BackendEvent> _sub;
  bool fixing = false;
  String progress = '';
  String? lastError;
  String? infoMessage;
  FixResult? pending;
  FixProvider(this._backend) {
    _sub = _backend.events.listen((e) {
      if (e.name == 'duzelt_progress') {
        progress = e.data['metin']?.toString() ?? '';
        notifyListeners();
      }
    });
  }
  Future<void> runFix(String kod) async {
    if (fixing) return;
    fixing = true;
    progress = 'Başlatıldı...';
    lastError = null;
    infoMessage = null;
    pending = null;
    notifyListeners();
    try {
      final r = await _backend.call('duzelt', {'kod': kod});
      if (r['degisiklik'] == true) {
        pending = FixResult(
          code: r['kod']?.toString() ?? kod,
          diff: r['diff']?.toString() ?? '',
          changes: (r['degisiklikler'] as List? ?? [])
              .map((e) => e.toString())
              .toList(),
        );
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
  ed.saveActive().then((_) {
    if (context.mounted) {
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
  if (!context.read<UiProvider>().showTerminal) {
    context.read<UiProvider>().toggleTerminal();
  }
  context.read<TerminalProvider>().run(k);
}

Future<void> openFilePicker(BuildContext context) async {
  final r = await FilePicker.platform.pickFiles(type: FileType.any);
  if (r != null && r.files.isNotEmpty && r.files.first.path != null) {
    try {
      await context.read<EditorProvider>().openFile(r.files.first.path!);
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
  final fixFuture = fix.runFix(kod);
  unawaited(showDialog(
    context: context,
    barrierDismissible: false,
    builder: (_) => AlertDialog(
      title: const Text('Düzeltme'),
      content: SizedBox(
        width: 300,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const LinearProgressIndicator(),
          const SizedBox(height: 10),
          Consumer<FixProvider>(builder: (_, p, __) => Text(p.progress)),
        ]),
      ),
    ),
  ));
  await fixFuture;
  if (!context.mounted) return;
  Navigator.of(context, rootNavigator: true).pop();
  if (fix.pending != null) {
    final result = fix.pending!;
    final choice = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Değişiklikler'),
        content: SizedBox(
          width: 640,
          height: 460,
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (result.changes.isNotEmpty) ...[
              Text('${result.changes.length} değişiklik:',
                  style: Theme.of(dc).textTheme.labelLarge),
              const SizedBox(height: 4),
              ...result.changes.take(6).map((c) => Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child:
                        Text('• $c', style: Theme.of(dc).textTheme.bodySmall),
                  )),
              const Divider(height: 20),
            ],
            Expanded(
              child: SingleChildScrollView(
                child: SelectableText(result.diff,
                    style: const TextStyle(
                        fontFamily: kMonoFontFamily,
                        fontFamilyFallback: kMonoFontFallback,
                        fontSize: 12)),
              ),
            ),
          ]),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, 'reject'),
              child: const Text('Reddet')),
          OutlinedButton(
              onPressed: () => Navigator.pop(dc, 'tab'),
              child: const Text('Yeni Sekmede Aç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, 'apply'),
              child: const Text('Uygula')),
        ],
      ),
    );
    if (!context.mounted) return;
    if (choice == 'apply') {
      ed.replaceActiveContent(result.code);
      fix.clearPending();
      showAppSnackbar(context, 'Uygulandı', kind: SnackKind.success);
    } else if (choice == 'tab') {
      ed.createUntitled(name: 'duzeltilmis.trpy', content: result.code);
      fix.clearPending();
      showAppSnackbar(context, 'Düzeltilmiş kod yeni sekmede açıldı',
          kind: SnackKind.success);
    } else {
      fix.clearPending();
    }
  } else if (fix.lastError != null) {
    showAppSnackbar(context, fix.lastError!, kind: SnackKind.error);
  } else if (fix.infoMessage != null) {
    showAppSnackbar(context, fix.infoMessage!);
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
        c.read<EditorProvider>().createUntitled();
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
        c.read<EditorProvider>().saveAsActive().then((_) {
          if (c.mounted) {
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
      run: (c) => c.read<UiProvider>().openFind(false),
    ),
    AppAction(
      id: 'edit.find_replace',
      label: 'Bul / Değiştir',
      menu: 'Düzenle',
      shortcut: 'Ctrl+H',
      activator: const SingleActivator(LogicalKeyboardKey.keyH, control: true),
      icon: Icons.find_replace,
      run: (c) => c.read<UiProvider>().openFind(true),
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
      id: 'view.palette',
      label: 'Komut Paleti',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+P',
      activator: const SingleActivator(LogicalKeyboardKey.keyP,
          control: true, shift: true),
      icon: Icons.palette_outlined,
      run: (c) =>
          showDialog(context: c, builder: (_) => const CommandPaletteDialog()),
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
        final ctrl = c.read<EditorProvider>().uiController;
        if (ctrl == null) return;
        final line = cursorLineOf(ctrl);
        c.read<BreakpointProvider>().toggle(line);
      },
    ),
    AppAction(
      id: 'run.debug_start',
      label: 'Debug Başlat',
      menu: 'Çalıştır',
      shortcut: 'F5',
      activator: const SingleActivator(LogicalKeyboardKey.f5),
      icon: Icons.bug_report,
      run: (c) => _debugWrap(c,
          (bp) => bp.start(kod: c.read<EditorProvider>().activeContent.value)),
    ),
    AppAction(
      id: 'run.debug_step',
      label: 'Adım',
      menu: 'Çalıştır',
      shortcut: 'F10',
      activator: const SingleActivator(LogicalKeyboardKey.f10),
      icon: Icons.skip_next,
      run: (c) => _debugWrap(c, (bp) => bp.step()),
    ),
    AppAction(
      id: 'run.debug_continue',
      label: 'Devam',
      menu: 'Çalıştır',
      icon: Icons.fast_forward,
      run: (c) => _debugWrap(c, (bp) => bp.continueRun()),
    ),
    AppAction(
      id: 'run.debug_stop',
      label: 'Debug Durdur',
      menu: 'Çalıştır',
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
  const _ToastBox({required this.msg, required this.kind});
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        border: Border.all(color: theme.colorScheme.outline),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 6),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Text(msg,
              style:
                  TextStyle(fontSize: 12, color: theme.colorScheme.onSurface)),
        ),
      ]),
    );
  }
}

class ConnectionBanner extends StatelessWidget {
  const ConnectionBanner({super.key});
  @override
  Widget build(BuildContext context) {
    final c = context.watch<ConnectionProvider>().connected;
    if (c) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: Colors.red.shade700,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: const Row(children: [
        Icon(Icons.cloud_off, size: 18, color: Colors.white),
        SizedBox(width: 8),
        Expanded(
          child: Text(
              'Backend bağlantısı yok. Python sunucusu başlatılıyor veya kapalı.',
              style: TextStyle(color: Colors.white, fontSize: 13)),
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
  const _TabAnim(
      {super.key,
      required this.child,
      required this.closing,
      required this.onClosed});
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
    } else {
      _c.forward();
    }
  }

  @override
  void didUpdateWidget(covariant _TabAnim old) {
    super.didUpdateWidget(old);
    if (widget.closing && !old.closing) _c.reverse();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_closedFired) return const SizedBox.shrink();
    final curve = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);
    return FadeTransition(
      opacity: curve,
      child: SizeTransition(
        axis: Axis.horizontal,
        sizeFactor: curve,
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
              ctx.read<EditorProvider>().openFile(node.path).catchError((e) {
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
    final activePath = context.watch<EditorProvider>().activeTab?.path;
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
// SEKME ÇUBUĞU (animasyonlu, kirli onaylı)
// ============================================================================
class EditorTabsBar extends StatefulWidget {
  const EditorTabsBar({super.key});
  @override
  State<EditorTabsBar> createState() => _EditorTabsBarState();
}

class _EditorTabsBarState extends State<EditorTabsBar> {
  final Set<String> _closing = {};
  Future<void> _requestClose(EditorProvider ed, int i) async {
    final t = ed.tabs[i];
    if (_closing.contains(t.path)) return;
    if (t.dirty) {
      final a = await showDialog<String>(
        context: context,
        builder: (dc) => AlertDialog(
          title: const Text('Kapat'),
          content: Text('${t.name} kaydedilmemiş.'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dc, 'c'),
                child: const Text('Vazgeç')),
            TextButton(
                onPressed: () => Navigator.pop(dc, 'x'),
                child: const Text('Kapat')),
            FilledButton(
                onPressed: () => Navigator.pop(dc, 's'),
                child: const Text('Kaydet')),
          ],
        ),
      );
      if (!mounted) return;
      if (a == 's') await ed.saveTab(i);
      if (a != 'x' && a != 's') return;
    }
    setState(() => _closing.add(t.path));
  }

  @override
  Widget build(BuildContext context) {
    final ed = context.watch<EditorProvider>();
    final theme = Theme.of(context);
    return Container(
      height: 45,
      padding: EdgeInsets.zero,
      color: theme.colorScheme.surfaceContainer,
      child: Row(children: [
        Expanded(
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: ed.tabs.length,
            itemBuilder: (ctx, i) {
              final t = ed.tabs[i];
              final active = i == ed.activeIndex;
              final closing = _closing.contains(t.path);
              return _TabAnim(
                key: ValueKey(t.path),
                closing: closing,
                onClosed: () {
                  if (!mounted) return;
                  final idx = ed.tabs.indexWhere((x) => x.path == t.path);
                  setState(() => _closing.remove(t.path));
                  if (idx >= 0) ed.closeTab(idx);
                },
                child: MouseRegion(
                  cursor: SystemMouseCursors.click,
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: closing ? null : () => ed.setActive(i),
                    child: Container(
                      margin:
                          const EdgeInsets.only(top: 7, bottom: 7, right: 2),
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(3),
                        border: Border.all(
                            color: active
                                ? theme.colorScheme.primary
                                : theme.colorScheme.outlineVariant),
                      ),
                      child: Row(children: [
                        Text(t.name,
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: active
                                    ? FontWeight.w600
                                    : FontWeight.normal)),
                        if (t.dirty)
                          Padding(
                            padding: const EdgeInsets.only(left: 6),
                            child: Container(
                              width: 6,
                              height: 6,
                              decoration: const BoxDecoration(
                                  color: Colors.amber, shape: BoxShape.circle),
                            ),
                          ),
                        const SizedBox(width: 8),
                        MouseRegion(
                          cursor: SystemMouseCursors.click,
                          child: GestureDetector(
                            onTap: () => _requestClose(ed, i),
                            child: const Icon(Icons.close, size: 12),
                          ),
                        ),
                      ]),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        IconButton(
          tooltip: 'Yeni Sekme (Ctrl+T)',
          visualDensity: VisualDensity.compact,
          icon: const Icon(Icons.add, size: 16),
          onPressed: () => ed.createUntitled(),
        ),
      ]),
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
    for (var i = 0; i < lines.length; i++) {
      final raw = lines[i];
      final y = i * per;
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
      final y = (contentHeight - vh) * fraction;
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
    final target =
        (localY - contentH * viewportRatio / 2).clamp(0.0, contentH).toDouble();
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
  @override
  void initState() {
    super.initState();
    _fc.addListener(_updateInfo);
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
  void _updateInfo() {
    final t = _ed?.text ?? '';
    final q = _fc.text;
    context.read<UiProvider>().setFindQuery(q);
    if (q.isEmpty) {
      setState(() => _info = '');
      return;
    }
    final n = RegExp(RegExp.escape(q)).allMatches(t).length;
    setState(() => _info = '$n eşleşme');
  }

  void _next({bool back = false}) {
    final c = _ed;
    final q = _fc.text;
    if (c == null || q.isEmpty) return;
    final t = c.text;
    final start = back
        ? (c.selection.isValid ? c.selection.start - 1 : t.length)
        : (c.selection.isValid ? c.selection.end : 0);
    var idx = back
        ? t.lastIndexOf(q, start.clamp(0, t.length))
        : t.indexOf(q, start.clamp(0, t.length));
    if (idx < 0) idx = back ? t.lastIndexOf(q) : t.indexOf(q);
    if (idx >= 0) {
      c.selection =
          TextSelection(baseOffset: idx, extentOffset: idx + q.length);
      setState(() =>
          _info = '${RegExp(RegExp.escape(q)).allMatches(t).length} eşleşme');
    } else {
      setState(() => _info = 'Bulunamadı');
    }
  }

  void _replaceOne() {
    final c = _ed;
    final q = _fc.text;
    final r = _rc.text;
    if (c == null || q.isEmpty) return;
    final sel = c.selection;
    if (sel.isValid &&
        sel.start != sel.end &&
        c.text.substring(sel.start, sel.end) == q) {
      c.text = c.text.replaceRange(sel.start, sel.end, r);
      c.selection = TextSelection.collapsed(offset: sel.start + r.length);
      context.read<EditorProvider>().updateContent(c.text);
    }
    _next();
  }

  void _replaceAll() {
    final c = _ed;
    final q = _fc.text;
    final r = _rc.text;
    if (c == null || q.isEmpty) return;
    final count = RegExp(RegExp.escape(q)).allMatches(c.text).length;
    c.text = c.text.replaceAll(q, r);
    context.read<EditorProvider>().updateContent(c.text);
    setState(() => _info = '$count adet değiştirildi');
  }

  @override
  Widget build(BuildContext context) {
    final ui = context.watch<UiProvider>();
    final theme = Theme.of(context);
    final defaultOffset = Offset(
        (widget.bounds.width - 356).clamp(0, widget.bounds.width).toDouble(),
        6);
    final offset = ui.findOffset == Offset.zero ? defaultOffset : ui.findOffset;
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
                var base = ui.findOffset == Offset.zero
                    ? defaultOffset
                    : ui.findOffset;
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
                  onSubmitted: (_) => _next(),
                  onChanged: (_) => _updateInfo(),
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
            if (ui.findReplaceMode) ...[
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
class _Fold {
  final int id;
  final int startModel;
  final int endModel;
  final String hidden;
  final int lineCount;
  _Fold({
    required this.id,
    required this.startModel,
    required this.endModel,
    required this.hidden,
    required this.lineCount,
  });
}

// Boşluk/tab dizilerinin altını çizerek görünür kılar (app.py'deki
// "bosluk_gostergesi" ayarının aynısı). Sadece kaydırmasız (yatay scroll)
// modda kullanılır; monospace karakter genişliği varsayımına dayanır.
class _WhitespacePainter extends CustomPainter {
  final List<String> lines;
  final TextStyle style;
  final double lineHeight;
  final Color color;
  static final RegExp _ws = RegExp(r'[ \t]+');
  _WhitespacePainter({
    required this.lines,
    required this.style,
    required this.lineHeight,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    const leftPad = 8.0; // TextField contentPadding.horizontal ile aynı
    const topPad = 8.0; // TextField contentPadding.vertical ile aynı
    for (var i = 0; i < lines.length; i++) {
      final y = topPad + i * lineHeight + lineHeight - 4;
      if (y > size.height + lineHeight) break;
      if (y < -lineHeight) continue;
      final line = lines[i];
      final matches = _ws.allMatches(line).toList();
      if (matches.isEmpty) continue;
      // ÖNEMLİ: Önceki sürüm `sütun * sabit_karakter_genişliği` varsayımıyla
      // konum hesaplıyordu — bu YALNIZCA gerçek monospace fontlarda doğru
      // sonuç verir. Kullanıcı "Yazı Tipi" ayarından Segoe UI, Comic Sans,
      // Arial gibi orantısal (monospace olmayan) bir font seçtiğinde her
      // karakterin genişliği farklı olduğundan işaretler tamamen alakasız
      // yerlere düşüyordu. Artık satırı GERÇEKTEN dizip (TextPainter) her
      // boşluk dizisinin piksel-doğru başlangıç/bitiş konumunu ölçüyoruz;
      // bu, seçilen font ne olursa olsun doğru sonuç verir.
      final tp = TextPainter(
        text: TextSpan(text: line, style: style),
        textDirection: TextDirection.ltr,
      )..layout();
      for (final m in matches) {
        final x1 = leftPad +
            tp.getOffsetForCaret(TextPosition(offset: m.start), Rect.zero).dx;
        final x2 = leftPad +
            tp.getOffsetForCaret(TextPosition(offset: m.end), Rect.zero).dx;
        canvas.drawLine(Offset(x1, y), Offset(x2, y), paint);
      }
      tp.dispose();
    }
  }

  @override
  bool shouldRepaint(covariant _WhitespacePainter old) =>
      !identical(old.lines, lines) ||
      old.lineHeight != lineHeight ||
      old.style != style ||
      old.color != color;
}

class _FindMatchesPainter extends CustomPainter {
  final String text;
  final String query;
  final TextStyle style;
  final StrutStyle strut;
  final double lineHeight;
  final Color color;

  _FindMatchesPainter({
    required this.text,
    required this.query,
    required this.style,
    required this.strut,
    required this.lineHeight,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (query.isEmpty || text.isEmpty) return;
    final paint = Paint()..color = color;
    final lines = text.split('\n');
    for (var lineIndex = 0; lineIndex < lines.length; lineIndex++) {
      final line = lines[lineIndex];
      for (var column = line.indexOf(query);
          column >= 0;
          column = line.indexOf(query, column + query.length)) {
        final painter = TextPainter(
          text: TextSpan(text: line, style: style),
          textDirection: TextDirection.ltr,
          strutStyle: strut,
          textScaler: TextScaler.noScaling,
        )..layout();
        final left = painter
            .getOffsetForCaret(TextPosition(offset: column), Rect.zero)
            .dx;
        final right = painter
            .getOffsetForCaret(
              TextPosition(offset: column + query.length),
              Rect.zero,
            )
            .dx;
        canvas.drawRect(
          Rect.fromLTWH(left + 8, 8 + lineIndex * lineHeight,
              math.max(1, right - left), lineHeight),
          paint,
        );
        painter.dispose();
      }
    }
  }

  @override
  bool shouldRepaint(covariant _FindMatchesPainter old) =>
      old.text != text ||
      old.query != query ||
      old.style != style ||
      old.strut != strut ||
      old.lineHeight != lineHeight ||
      old.color != color;
}

class CodeEditor extends StatefulWidget {
  const CodeEditor({super.key});
  @override
  State<CodeEditor> createState() => _CodeEditorState();
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
  List<Map<String, String>> _suggestions = [];
  Offset? _sugOffset;
  bool _sugVisible = false;
  int _selIndex = 0;
  double _contentWidth = 0;
  Size _vpSize = const Size(800, 600);
  final Map<int, _Fold> _folds = {};
  final Map<int, int> _foldViewByLine = {};
  int _nextFoldId = 1;
  List<Map<String, int>> _foldRegions = [];
  bool _programmaticTextChange = false;
  TextEditingValue? _lastValidValue;
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
        return TextSpan(
          style: style,
          children: SyntaxHighlightingController._tokenize(
            codeLine.text,
            palette,
            style,
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
    _ui = context.read<UiProvider>();
    _backend = context.read<BackendService>();
    ed.uiController = _ctrl;
  }

  @override
  void dispose() {
    _editor?.removeListener(_onEd);
    if (_editor?.uiController == _ctrl) _editor?.uiController = null;
    _debounce?.cancel();
    _syntaxTimer?.cancel();
    _widthTimer?.cancel();
    _foldTimer?.cancel();
    _textScroll.removeListener(_onTextScroll);
    _hScroll.removeListener(_onHScroll);
    _ctrl.removeListener(_onControllerChange);
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
      '${f.lineCount} satır kadar kod katlanıldı.';

  /// Görünüm metnini katlanmış bölgelerle birlikte tam metne çevirir.
  String fullText() {
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

  /// Görünüm satırı -> model satır numarası (marker satırı: -id).
  List<int> _viewModelStart() {
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
    _foldTimer = Timer(const Duration(milliseconds: 600), () async {
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
        if (mounted) setState(() => _foldRegions = list);
      } catch (_) {}
    });
  }

  Map<int, String> _foldIcons() {
    final vm = _viewModelStart();
    final folded =
        _folds.values.map((f) => '${f.startModel}:${f.endModel}').toSet();
    final icons = <int, String>{};
    for (var i = 0; i < vm.length; i++) {
      final v = vm[i];
      if (v < 0) {
        icons[i + 1] = '⋯';
        continue;
      }
      for (final r in _foldRegions) {
        if (r['s'] == v) {
          icons[i + 1] = folded.contains('${r['s']}:${r['e']}') ? '▶' : '▼';
          break;
        }
      }
    }
    return icons;
  }

  void _applyView(String text, int caret) {
    _programmaticTextChange = true;
    _ctrl.value = TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: caret.clamp(0, text.length)),
    );
    _programmaticTextChange = false;
    _lastValidValue = _ctrl.value;
    _pushContent();
    setState(() {});
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
    _programmaticTextChange = true;
    _ctrl.value = v;
    _programmaticTextChange = false;
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
    final hidden = lines.sublist(headerIdx + 1, bodyEnd + 1).join('\n');
    final fold = _Fold(
      id: _nextFoldId++,
      startModel: s,
      endModel: e,
      hidden: hidden,
      lineCount: bodyEnd - headerIdx,
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
            () => _selIndex = math.min(_selIndex + 1, _suggestions.length - 1));
        return KeyEventResult.handled;
      }
      if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
        setState(() => _selIndex = math.max(_selIndex - 1, 0));
        return KeyEventResult.handled;
      }
      if (event.logicalKey == LogicalKeyboardKey.tab ||
          event.logicalKey == LogicalKeyboardKey.enter) {
        if (_suggestions.isNotEmpty)
          _acceptSug(_suggestions[_selIndex]['label']!);
        return KeyEventResult.handled;
      }
      return KeyEventResult.ignored;
    }
    final ctrlPressed = HardwareKeyboard.instance.isControlPressed;
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
            _wrapSelection(ch);
            return KeyEventResult.handled;
          }
          final t = _ctrl.text;
          final pos = sel.isValid ? sel.baseOffset : t.length;
          if (ch == _pairs[ch] && pos < t.length && t[pos] == ch) {
            _ctrl.selection = TextSelection.collapsed(offset: pos + 1);
            return KeyEventResult.handled;
          }
          final close = _pairs[ch]!;
          _ctrl.value = TextEditingValue(
            text: t.replaceRange(pos, pos, ch + close),
            selection: TextSelection.collapsed(offset: pos + 1),
          );
          _pushContent();
          return KeyEventResult.handled;
        }
        if (_pairs.values.contains(ch)) {
          final t = _ctrl.text;
          final pos = sel.isValid ? sel.baseOffset : t.length;
          if (pos < t.length && t[pos] == ch) {
            _ctrl.selection = TextSelection.collapsed(offset: pos + 1);
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
    _editor?.updateContent(fullText());
  }

  void _syncReText() {
    if (_reCtrl.text == _ctrl.text) return;
    final text = _ctrl.text;
    final selection = _ctrl.selection;
    final lines = text.split('\n');
    re.CodeLineSelection toCodeSelection(int offset) {
      var remaining = offset.clamp(0, text.length).toInt();
      var line = 0;
      while (line < lines.length - 1 && remaining > lines[line].length) {
        remaining -= lines[line].length + 1;
        line++;
      }
      return re.CodeLineSelection.collapsed(index: line, offset: remaining);
    }

    _reCtrl.text = _ctrl.text;
    if (selection.isValid) {
      _reCtrl.selection = re.CodeLineSelection(
        baseIndex: toCodeSelection(selection.baseOffset).baseIndex,
        baseOffset: toCodeSelection(selection.baseOffset).baseOffset,
        extentIndex: toCodeSelection(selection.extentOffset).baseIndex,
        extentOffset: toCodeSelection(selection.extentOffset).baseOffset,
      );
    }
  }

  void _onReChanged(re.CodeLineEditingValue value) {
    if (_ctrl.text == _reCtrl.text) return;
    final lines = _reCtrl.text.split('\n');
    int absoluteOffset(int lineIndex, int column) {
      var offset = 0;
      for (var i = 0; i < lineIndex && i < lines.length; i++) {
        offset += lines[i].length + 1;
      }
      return (offset + column).clamp(0, _reCtrl.text.length).toInt();
    }

    final selection = _reCtrl.selection;
    _programmaticTextChange = true;
    _ctrl.value = TextEditingValue(
      text: _reCtrl.text,
      selection: TextSelection(
        baseOffset: absoluteOffset(selection.baseIndex, selection.baseOffset),
        extentOffset:
            absoluteOffset(selection.extentIndex, selection.extentOffset),
      ),
    );
    _programmaticTextChange = false;
    _onChanged(_ctrl.text);
  }

  void _insertEmptyLine({required bool below}) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final pos = sel.isValid ? sel.baseOffset : t.length;
    final anchor = below ? _lineEnd(t, pos) : _lineStart(t, pos);
    final nt = t.replaceRange(anchor, anchor, '\n');
    _ctrl.value = TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: anchor + 1),
    );
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
    _ctrl.value = TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: le + 1 + txt.length),
    );
    _pushContent();
  }

  void _wrapSelection(String q) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    if (!sel.isValid || sel.isCollapsed) return;
    final inner = t.substring(sel.start, sel.end);
    final nt = t.replaceRange(sel.start, sel.end, '$q$inner$q');
    _ctrl.value = TextEditingValue(
      text: nt,
      selection:
          TextSelection(baseOffset: sel.start + 1, extentOffset: sel.end + 1),
    );
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
          _ctrl.value = TextEditingValue(
            text: t.replaceRange(ls, ls + remove, ''),
            selection: TextSelection.collapsed(
                offset: math.max(ls, sel.baseOffset - remove)),
          );
          _onChanged(_ctrl.text);
        }
      } else {
        _ctrl.value = TextEditingValue(
          text: t.replaceRange(sel.start, sel.start, '  '),
          selection: TextSelection.collapsed(offset: sel.start + 2),
        );
        _onChanged(_ctrl.text);
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
    _ctrl.value = TextEditingValue(
      text: t.replaceRange(ls, le, nb),
      selection: TextSelection(
        baseOffset: math.max(0, sel.start + delta),
        extentOffset: math.max(0, sel.end + (nb.length - (le - ls))),
      ),
    );
    _onChanged(_ctrl.text);
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
    final a = ed.activeTab;
    if (a == null || a.path == kSettingsPath) {
      if (_loadedPath != null) {
        _programmaticTextChange = true;
        _ctrl.clear();
        _syncReText();
        _programmaticTextChange = false;
        _lastValidValue = _ctrl.value;
        _loadedPath = null;
        _loadedRev = ed.revision;
        _folds.clear();
        _foldViewByLine.clear();
        _foldRegions = [];
        _hideSug();
      }
      return;
    }
    if (_loadedPath != a.path || _loadedRev != ed.revision) {
      _programmaticTextChange = true;
      _ctrl.text = a.content;
      _syncReText();
      _programmaticTextChange = false;
      _lastValidValue = _ctrl.value;
      _loadedPath = a.path;
      _loadedRev = ed.revision;
      _folds.clear();
      _foldViewByLine.clear();
      _foldRegions = [];
      _hideSug();
      _scheduleWidth();
      _scheduleFoldRefresh();
    }
  }

  void _onTextScroll() {
    _syncGutter();
    if (_sugVisible) _hideSug();
    setState(() {});
  }

  void _onHScroll() {
    if (_sugVisible) _hideSug();
  }

  void _onControllerChange() {
    if (!_programmaticTextChange && !_foldViewValid()) {
      _restoreValidFoldView();
      return;
    }
    _lastValidValue = _ctrl.value;
    _syncReText();
    if (_sugVisible) _hideSug();
    final ui = _ui;
    if (ui != null) {
      final offset = _ctrl.selection.isValid ? _ctrl.selection.baseOffset : 0;
      ui.setCursor(
          _lineNumber(_ctrl.text, offset), _columnNumber(_ctrl.text, offset));
    }
    _ensureCaretVisible();
    _scheduleSyntaxCheck();
    _scheduleWidth();
    _scheduleFoldRefresh();
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

  String _contextWindow() {
    final full = fullText();
    if (full.length < 50000) return full;
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
    return full.substring(ls, le);
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
    if (!_programmaticTextChange && !_foldViewValid()) {
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
    _ctrl.value = TextEditingValue(
      text: nt,
      selection: TextSelection.collapsed(offset: match.start + w.length),
    );
    _hideSug();
    _onChanged(nt);
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
        final r =
            await backend.call('syntax_kontrol', {'kod': _contextWindow()});
        if (r['basarili'] == true) {
          ui.setSyntaxStatus('✓ Sözdizimi doğru');
        } else {
          final hatalar = r['hatalar'];
          if (hatalar is List && hatalar.isNotEmpty) {
            ui.setSyntaxStatus(hatalar.first.toString());
          } else {
            ui.setSyntaxStatus('Sözdizimi hatası');
          }
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
    final ui = context.watch<UiProvider>();
    final settings = context.watch<SettingsProvider>();
    final theme = Theme.of(context);
    context.watch<LanguageProvider>();
    if (active == null || active.path == kSettingsPath) {
      return Container(color: theme.colorScheme.surface);
    }
    final style = _style();
    final viewLines = _ctrl.text.split('\n');
    final foldIcons = _foldIcons();
    final showMinimap = settings.getBool('minimap');
    final showLineNumbers =
        settings.getBool('satir_numaralari', fallback: true);
    final wrapEnabled = settings.getBool('kelime_sar');
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
                  indicatorBuilder: showLineNumbers
                      ? (context, editingController, chunkController,
                          notifier) {
                          return GestureDetector(
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
                                  line > _ctrl.text.split('\n').length) {
                                return;
                              }
                              final foldIcons = _foldIcons();
                              if (foldIcons[line] != null) {
                                _onFoldTap(line);
                              } else {
                                bp.toggle(line);
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
                                        breakpoints: bp.breakpoints,
                                        currentLine: bp.debugging
                                            ? bp.currentLine
                                            : null,
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
                          );
                        }
                      : null,
                );
                return Stack(children: [
                  Positioned.fill(child: editorSurface),
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
                  if (ui.findOpen) FindWidget(bounds: vp),
                ]);
              }),
            ),
            if (showMinimap) Minimap(lines: viewLines, textScroll: _textScroll),
          ]),
        ),
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
  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
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
                  child: SelectableText(term.output,
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
                enabled: conn,
                style: TextStyle(
                    fontFamily: kMonoFontFamily,
                    fontFamilyFallback: kMonoFontFallback,
                    fontSize: termFontSize),
                decoration: const InputDecoration(
                    isDense: true,
                    border: InputBorder.none,
                    hintText: 'Komut...'),
                onSubmitted: (v) {
                  if (v.trim().isNotEmpty) {
                    term.sendCommand(v);
                    _input.clear();
                  }
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
      c.value = TextEditingValue(
        text: t.replaceRange(pos, pos, kod),
        selection: TextSelection.collapsed(offset: pos + kod.length),
      );
      ed.updateContent(c.text);
      showAppSnackbar(context, 'AI kodu imlece eklendi',
          kind: SnackKind.success);
    } else if (choice == 'tab') {
      ed.createUntitled(name: 'ai_kod.trpy', content: kod);
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
                      Text(part.language ?? 'kod',
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
              child: TextField(
                controller: _input,
                enabled: conn && !ai.loading,
                minLines: 1,
                maxLines: 4,
                style: const TextStyle(fontSize: 12.5),
                decoration:
                    const InputDecoration(hintText: 'Sor...', isDense: true),
                onSubmitted: (_) {
                  final t = _input.text.trim();
                  if (t.isNotEmpty && !ai.loading) {
                    ai.ask(t, kod: currentCode());
                    _input.clear();
                  }
                },
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
  late bool _adv;
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
  }

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
    _sic = s.getDouble('ai_sicaklik', fallback: 0.7);
    _fontSize = s.getInt('yazi_boyutu', fallback: 14).toDouble();
    _ai = s.getBool('ai_aktif');
    _auto = s.getBool('otomatik_tamamlama', fallback: true);
    _autoSave = s.getBool('otomatik_kaydetme');
    _adv = s.getBool('gelismis_duzeltme');
    _satirNo = s.getBool('satir_numaralari', fallback: true);
    _kelimeSar = s.getBool('kelime_sar');
    _boslukGoster = s.getBool('bosluk_gostergesi');
    _yaziTipi = s.getString('yazi_tipi', fallback: 'Consolas').trim();
    if (_yaziTipi.isEmpty) _yaziTipi = 'Consolas';
    _fontSearch.text = _yaziTipi;
    _terminalFontSize = s.getDouble('terminal_yazi_boyutu', fallback: 13);
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
      await s.setValue('gelismis_duzeltme', _adv);
      await s.setValue('yazi_boyutu', _fontSize.round());
      await s.setValue('satir_numaralari', _satirNo);
      await s.setValue('kelime_sar', _kelimeSar);
      await s.setValue('bosluk_gostergesi', _boslukGoster);
      await s.setValue('yazi_tipi',
          _yaziTipi.trim().isEmpty ? 'Consolas' : _yaziTipi.trim());
      await s.setValue('terminal_yazi_boyutu', _terminalFontSize.round());
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
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainer,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
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
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = context.watch<SettingsProvider>();
    if (!settings.loaded || !_formReady) {
      return Container(
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
    return Container(
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
                                            decoration: BoxDecoration(
                                              color: theme.colorScheme
                                                  .surfaceContainerHigh,
                                              border: Border.all(
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
                              'Kelime Kaydırma açıkken bu gösterge devre dışı kalır.',
                              style: TextStyle(fontSize: 11)),
                          value: _boslukGoster,
                          onChanged: (v) =>
                              setState(() => _boslukGoster = v ?? false),
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
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text(
                              'Gelişmiş Düzeltme (kodu arka planda çalıştırır)'),
                          value: _adv,
                          onChanged: (v) => setState(() => _adv = v ?? false),
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
                      Navigator.pop(context);
                      jumpToLine(context, line);
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
      setState(() {
        result = buf.toString();
        loading = false;
      });
    } catch (e) {
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

class AboutSignDialog extends StatelessWidget {
  const AboutSignDialog({super.key});
  @override
  Widget build(BuildContext context) {
    final backend = context.read<BackendService>();
    return AlertDialog(
      title: const Text('TürKod IDE'),
      content: FutureBuilder<List<Map<String, dynamic>>>(
        future: Future.wait(
            [backend.call('imza_dogrula'), backend.call('dosya_hash')]),
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
                  onTap: () {
                    Navigator.pop(context);
                    a.run(context);
                  },
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
        const Spacer(),
        if (ui.syntaxStatus.isNotEmpty) ...[
          Text(ui.syntaxStatus,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 11,
                  color: ui.syntaxStatus.contains('✓')
                      ? Colors.green
                      : theme.colorScheme.error)),
          const SizedBox(width: 12),
        ],
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
    final ui = context.watch<UiProvider>();
    final ed = context.watch<EditorProvider>();
    final isSettings = ed.activeTab?.path == kSettingsPath;
    return Column(children: [
      AppTitleBar(actions: actions),
      Expanded(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            width: ui.showExplorer ? ui.sidebarWidth : 0,
            child: ClipRect(
              child: SizedBox(
                  width: ui.sidebarWidth, child: const FileTreePanel()),
            ),
          ),
          if (ui.showExplorer)
            _HGrip((d) => ui.setSidebarWidth(ui.sidebarWidth + d)),
          Expanded(
            child:
                Column(mainAxisAlignment: MainAxisAlignment.start, children: [
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
                            : CodeEditor(
                                key: ValueKey(ed.activeTab?.path ?? 'bos')),
                      ),
                    ]),
              ),
              if (ui.showTerminal) ...[
                _VGrip((d) => ui.setTerminalHeight(ui.terminalHeight - d)),
                AnimatedContainer(
                  duration: kAnim,
                  curve: kAnimCurve,
                  height: ui.showTerminal ? ui.terminalHeight : 0,
                  child: ClipRect(
                    child: SizedBox(
                        height: ui.terminalHeight,
                        child: const TerminalPanel()),
                  ),
                ),
              ],
            ]),
          ),
          if (ui.showAi) _HGrip((d) => ui.setAiWidth(ui.aiWidth - d)),
          AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            width: ui.showAi ? ui.aiWidth : 0,
            child: ClipRect(
              child: SizedBox(width: ui.aiWidth, child: const AiPanel()),
            ),
          ),
        ]),
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

  @override
  void initState() {
    super.initState();
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
  bool _onHardwareKey(KeyEvent event) {
    if (event is! KeyDownEvent) return false;
    for (final entry in _shortcuts.entries) {
      if (entry.key.accepts(event, HardwareKeyboard.instance)) {
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
    HardwareKeyboard.instance.removeHandler(_onHardwareKey);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final actions = buildAppActions();
    _shortcuts = {
      for (final a in actions)
        if (a.activator != null) a.activator!: () => a.run(context),
    };
    final ui = context.watch<UiProvider>();
    return Focus(
      autofocus: true,
      child: Scaffold(
        body: Stack(children: [
          Column(children: [
            const ConnectionBanner(),
            Expanded(child: AppLayout(actions: actions)),
          ]),
          if (ui.toast != null)
            Positioned(
              right: 12,
              bottom: 32,
              child: _ToastBox(msg: ui.toast!, kind: ui.toastKind),
            ),
        ]),
      ),
    );
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
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
    _acilisHataAbone?.cancel();
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
        ChangeNotifierProvider(create: (_) => ConnectionProvider(_backend)),
        ChangeNotifierProvider(create: (_) => UiProvider(_launcher)),
        ChangeNotifierProvider(create: (_) => SettingsProvider(_backend)),
        ChangeNotifierProvider(create: (_) => LanguageProvider(_backend)),
        ChangeNotifierProvider(create: (_) => EditorProvider(_backend)),
        ChangeNotifierProvider(create: (_) => FileTreeProvider(_backend)),
        ChangeNotifierProvider(create: (_) => TerminalProvider(_backend)),
        ChangeNotifierProvider(create: (_) => AiProvider(_backend)),
        ChangeNotifierProvider(create: (_) => BreakpointProvider(_backend)),
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
