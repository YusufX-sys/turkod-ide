import 'dart:async';
import 'guncelleme.dart';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' show AppExitResponse;
import 'package:flutter/foundation.dart' show listEquals, mapEquals;
import 'package:flutter/gestures.dart'; // PointerScrollEvent buradan gelir
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show RenderAbstractViewport, RenderProxyBox;
import 'package:flutter/scheduler.dart' show SchedulerBinding;
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:provider/provider.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path/path.dart' as p;
import 'package:re_editor/re_editor.dart' as re;
import 'package:webview_windows/webview_windows.dart'
    show LoadingState, WebviewController, WebviewPopupWindowPolicy;
import 'acilis_ekrani.dart';
import 'arayuz_turu.dart';
import 'markdown_gorunum.dart';
import 'yardim.dart';

part 'eklentiler.dart';
part 'exe_donusturme.dart';
part 'karsilama.dart';
part 'arayuz_ogeleri.dart';
part 'pdf_gorunum.dart';
part 'kodi.dart';
part 'kodi_kontrol.dart';
part 'tarayici.dart';

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

/// IDE içindeki tarayıcı sekmesi (Görünüm → Tarayıcı).
const String kTarayiciPath = 'internal:browser';

/// Dosya olmayan sekmeler (Ayarlar, Tarayıcı): kaydedilmez, editör değildir.
bool ozelSekmeMi(String? yol) => yol != null && yol.startsWith('internal:');

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
/// Backend'e ulaşılamazsa gösterilen küçük liste. Asıl liste backend'in
/// internetten (models.dev) indirdiği katalogdan gelir (200+ sağlayıcı).
const Map<String, List<String>> kFallbackAiModels = {
  'yerel': [],
  'openai': ['gpt-5-mini', 'gpt-4o-mini'],
  'anthropic': ['claude-sonnet-5-5', 'claude-haiku-4-5'],
  'google': ['gemini-2.5-flash'],
  'groq': ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'],
};

/// Ağ / API hata metnini kısa ve anlaşılır bir Türkçe açıklamaya çevirir.
String baglantiHatasiAciklamasi(String hata) {
  final h = hata.toLowerCase();
  if (h.contains('getaddrinfo') ||
      h.contains('nameresolution') ||
      h.contains('max retries') ||
      h.contains('connection') ||
      h.contains('timed out') ||
      h.contains('timeout')) {
    return 'sağlayıcıya ulaşılamadı; internet bağlantını kontrol et';
  }
  if (h.contains('401') || h.contains('403') || h.contains('unauthorized') ||
      h.contains('invalid api key') || h.contains('api key')) {
    return 'API anahtarı geçersiz ya da yetkisiz';
  }
  if (h.contains('429')) return 'istek sınırı aşıldı; biraz sonra tekrar dene';
  return hata.length > 120 ? '${hata.substring(0, 120)}…' : hata;
}

/// Anahtarı kayıtlı ya da listede modeli olan sağlayıcılar (TürKod Yerel hariç).
List<String> bagliSaglayicilariBul(Object? anahtarlar, List<AiAtama> modeller) {
  final ids = <String>[];
  if (anahtarlar is Map) {
    anahtarlar.forEach((k, v) {
      final id = k.toString();
      if ((v?.toString() ?? '').trim().isNotEmpty && id != 'yerel' && !ids.contains(id)) {
        ids.add(id);
      }
    });
  }
  for (final a in modeller) {
    if (!a.yerel && !ids.contains(a.saglayici)) ids.add(a.saglayici);
  }
  return ids;
}

/// Görevi yapacak yapay zekâ: sağlayıcı (katalog kimliği; "yerel": TürKod
/// Yerel / llama.cpp) + model. Ayarlar → Yapay Zekâ: Görevler'de atanır.
class AiAtama {
  final String saglayici;
  final String model;
  const AiAtama(this.saglayici, this.model);

  bool get yerel => saglayici == 'yerel';

  /// Açılır liste değeri.
  String get anahtar => '$saglayici\u0001$model';

  static AiAtama? anahtardan(String? k) {
    final i = k?.indexOf('\u0001') ?? -1;
    return i > 0 ? AiAtama(k!.substring(0, i), k.substring(i + 1)) : null;
  }

  static AiAtama? coz(Object? v) {
    if (v is! Map) return null;
    final s = v['saglayici']?.toString().trim() ?? '';
    final m = v['model']?.toString().trim() ?? '';
    return s.isEmpty || m.isEmpty ? null : AiAtama(s, m);
  }

  Map<String, String> toJson() => {'saglayici': saglayici, 'model': model};

  @override
  bool operator ==(Object other) =>
      other is AiAtama && other.saglayici == saglayici && other.model == model;

  @override
  int get hashCode => Object.hash(saglayici, model);
}

/// Sohbet tabanlı yapay zekâ görevleri (otomatik tamamlama ayrıca).
const Map<String, String> kBulutGorevleri = {
  'sohbet': 'AI Paneli sohbet',
  'aciklama': 'Kod açıklama / optimize',
  'hata_aciklama': 'Hata açıklama',
  'duzeltme': 'Akıllı Düzelt (AI aşaması)',
  'kodi': 'Kodi (yardımcı robot)',
};

/// Ayarlar → Yapay Zekâ: Görevler'deki tüm görevler.
const Map<String, String> kAiGorevleri = {
  'tamamlama': 'Otomatik tamamlama (hayalet kod)',
  ...kBulutGorevleri,
};

/// Eski ayar dosyalarındaki görünen sağlayıcı adları -> katalog kimliği.
const Map<String, String> kEskiSaglayiciAdlari = {
  'OpenAI': 'openai',
  'Groq': 'groq',
  'Gemini': 'google',
  'Claude': 'anthropic',
  // Ollama desteği kaldırıldı; yerine TürKod'un kendi llama.cpp motoru.
  'ollama': 'yerel',
};

/// AI sağlayıcısı (backend kataloğundan).
class AiSaglayici {
  final String id;
  final String ad;
  final bool yerel;
  final bool anahtarGerekli;
  final String doc;
  final String api;
  const AiSaglayici({
    required this.id,
    required this.ad,
    this.yerel = false,
    this.anahtarGerekli = true,
    this.doc = '',
    this.api = '',
  });

  factory AiSaglayici.fromJson(Map m) => AiSaglayici(
        id: m['id']?.toString() ?? '',
        ad: m['ad']?.toString() ?? m['id']?.toString() ?? '',
        yerel: m['yerel'] == true,
        anahtarGerekli: m['anahtar_gerekli'] != false,
        doc: m['doc']?.toString() ?? '',
        api: m['api']?.toString() ?? '',
      );
}

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
        'İşlem tamamlanamadı.';
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

  /// Backend klasörü 300 öğede keser; gösterilmeyen öğe sayısı.
  int fazlaOge;
  FileNode({
    required this.name,
    required this.path,
    required this.isDir,
    this.children = const [],
    this.expanded = false,
    this.loaded = false,
    this.fazlaOge = 0,
  });
}

int _fazlaOge(Map<String, dynamic> r) => (r['fazla_oge'] as num?)?.toInt() ?? 0;

/// Yol bir PDF dosyası mı?
bool pdfYoluMu(String yol) => yol.toLowerCase().endsWith('.pdf');

class EditorTab {
  static int _seq = 0;

  final String id;
  final String path;
  final String name;
  String content;
  bool dirty;

  /// Çalıştırırken programa verilecek argümanlar (sys.argv[1:]); boşluklarla
  /// ayrılır, tırnaklı parçalar tek argümandır.
  String runArgs;

  EditorTab({
    String? id,
    required this.path,
    required this.name,
    required this.content,
    this.dirty = false,
    this.runArgs = '',
  }) : id = id ?? 'tab_${_seq++}';

  bool get isUntitled => path.startsWith('untitled:');

  /// PDF dosyası: metin olarak açılmaz, görüntüleyicide gösterilir ve asla
  /// kaydedilmez.
  bool get isPdf => pdfYoluMu(path);

  /// Kayıtlı bir dosyaysa yolu (program o klasörde çalışır), değilse null.
  String? get filePath => isUntitled || ozelSekmeMi(path) ? null : path;
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

  /// Yanıtı üreten sağlayıcı / model (ör. "Groq · llama-3.3-70b").
  final String kaynak;

  /// Hata yanıtı mı (yeniden dene düğmesi gösterilir).
  final bool hata;

  /// Akıl yürüten modellerin düşünme süreci (yanıttan ayrılmış).
  final String dusunce;
  AiMessage(
      {required this.role,
      required this.parts,
      this.kaynak = '',
      this.hata = false,
      this.dusunce = ''});

  /// Mesajın düz metni (kopyalama için; kod blokları ``` ile).
  String get duzMetin => parts
      .map((p) => p.type == 'kod'
          ? '```${p.language ?? ''}\n${p.content}\n```'
          : p.content)
      .join('\n\n');
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
  // İstek numarası -> komut adı (hata metninde istek numarası yerine
  // komutun kendisi gösterilsin).
  final Map<int, String> _komutAdlari = {};
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
        final komut = _komutAdlari.remove(id);
        if (c.isCompleted) return;
        if (msg['ok'] == true) {
          c.complete(msg['result'] is Map
              ? Map<String, dynamic>.from(msg['result'] as Map)
              : {});
        } else {
          c.completeError(BackendException(_extractError(msg, komut), data: msg));
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
  String _extractError(Map<String, dynamic> msg, [String? komut]) {
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
    return komut == null
        ? 'İşlem tamamlanamadı.'
        : 'İşlem tamamlanamadı ($komut).';
  }

  void _onDone() {
    if (_disposed) return;
    _isConnected = false;
    _connectionState.add(false);
    for (var c in _pending.values) {
      if (!c.isCompleted) c.completeError(BackendException('Bağlantı koptu'));
    }
    _pending.clear();
    _komutAdlari.clear();
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
      throw BackendException('TürKod motoru bağlı değil');
    }
    final id = _nextId++;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _komutAdlari[id] = command;
    try {
      _channel!.sink
          .add(jsonEncode({'id': id, 'command': command, 'params': params}));
    } catch (e) {
      // Soket kapanmış ama _onDone henüz çalışmamış: istek sahipsiz kalıp
      // yakalanmamış bir async hataya dönüşmesin.
      _pending.remove(id);
      _komutAdlari.remove(id);
      throw BackendException('TürKod motoru bağlı değil');
    }
    return completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
      _pending.remove(id);
      _komutAdlari.remove(id);
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
        environment: {
          'TURKOD_TOKEN': anahtar,
          // Yalnızca otomatik testler: ayarlar/oturum gerçek kullanıcı
          // klasörü yerine verilen sandbox klasöründe tutulur.
          if (Platform.environment['TURKOD_TEST_PROFIL'] case final String profil
              when profil.isNotEmpty) ...{'USERPROFILE': profil, 'HOME': profil},
        },
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
      return _basarisiz('TürKod motoru başlatılamadı: $e');
    }

    final acildi = await _waitForPort(bitti.future);
    if (!identical(_process, proc)) return false; // bu arada yeniden başlatıldı
    if (!acildi) {
      final kapandi = bitti.isCompleted;
      _oncekiniKapat();
      final ayrinti = _sonCikti.isEmpty ? '' : '\n\n${_sonCikti.join('\n')}';
      return _basarisiz(kapandi
          ? 'TürKod motoru başlatılamadı: hemen kapandı.$ayrinti'
          : 'TürKod motoru başlatılamadı: 60 sn içinde açılmadı.$ayrinti');
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
    sonHata = 'TürKod motoru beklenmedik biçimde kapandı.';
    durum.value = BackendDurum.durdu;
    unawaited(_otomatikYenidenBaslat());
  }

  Future<void> _otomatikYenidenBaslat() async {
    final simdi = DateTime.now();
    _otomatikBaslatmalar
        .removeWhere((t) => simdi.difference(t) > _otomatikPencere);
    if (_otomatikBaslatmalar.length >= _maksOtomatik) {
      sonHata = 'TürKod motoru art arda kapandı; otomatik yeniden başlatma durduruldu.';
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

/// Düzenle → Satıra Git (Ctrl+G): satır numarası sorup imleci oraya taşır.
Future<void> satiraGit(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final t = ed.activeTab;
  if (t == null || ozelSekmeMi(t.path) || t.isPdf) return;
  final toplam = '\n'.allMatches(t.content).length + 1;
  final satir = await showDialog<int>(
    context: context,
    builder: (_) => _SatiraGitDialog(toplam: toplam),
  );
  if (satir == null || !context.mounted) return;
  final goster = ed.revealModelLine;
  if (goster != null) {
    goster(satir);
  } else if (ed.uiController case final c?) {
    jumpToLineIn(c, satir);
  }
  ed.editorFocusNode?.requestFocus();
}

/// Denetleyici pencereyle birlikte (kapanma animasyonu bitince) yok edilir;
/// showDialog döner dönmez dispose etmek "kullanılmış denetleyici" hatası
/// veriyordu.
class _SatiraGitDialog extends StatefulWidget {
  final int toplam;
  const _SatiraGitDialog({required this.toplam});
  @override
  State<_SatiraGitDialog> createState() => _SatiraGitDialogState();
}

class _SatiraGitDialogState extends State<_SatiraGitDialog> {
  final _girdi = TextEditingController();
  String? _hata;

  @override
  void dispose() {
    _girdi.dispose();
    super.dispose();
  }

  void _onayla() {
    final n = int.tryParse(_girdi.text.trim());
    if (n == null || n < 1 || n > widget.toplam) {
      setState(() =>
          _hata = '1 ile ${widget.toplam} arasında bir satır numarası yazın');
      return;
    }
    Navigator.pop(context, n);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Satıra Git'),
      content: SizedBox(
        width: 320,
        child: TextField(
          controller: _girdi,
          autofocus: true,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: InputDecoration(
            labelText: 'Satır numarası (1 - ${widget.toplam})',
            errorText: _hata,
          ),
          onSubmitted: (_) => _onayla(),
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Vazgeç')),
        FilledButton(onPressed: _onayla, child: const Text('Git')),
      ],
    );
  }
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
    // Gezgin kısayolu: başka bir sol panel (Eklentiler) açıksa Gezgin'e geçer.
    if (showExplorer && solPanel != 'gezgin') {
      solPanel = 'gezgin';
    } else {
      showExplorer = !showExplorer;
      solPanel = 'gezgin';
    }
    notifyListeners();
  }

  /// Sol kenar panelinde gösterilen bölüm: "gezgin" | "eklentiler".
  String solPanel = 'gezgin';

  /// Aktivite çubuğu: aynı simgeye yeniden tıklamak paneli kapatır.
  void solPanelSec(String id) {
    if (showExplorer && solPanel == id) {
      showExplorer = false;
    } else {
      showExplorer = true;
      solPanel = id;
    }
    notifyListeners();
  }

  /// Bölünmüş görünümün sağ bölmesinde gösterilen sekme (kapalıysa null).
  String? yanSekmeId;

  void yanSekmeAyarla(String? id) {
    if (yanSekmeId == id) return;
    yanSekmeId = id;
    notifyListeners();
  }

  void toggleAi() {
    showAi = !showAi;
    notifyListeners();
  }

  /// Ana bölgelerin soldan sağa sırası: "gezgin" (sol kenar paneli),
  /// "editor" (editör + terminal), "ai" (AI Asistan). Paneller başlıklarından
  /// sürüklenerek ya da Görünüm menüsünden yer değiştirir.
  static const List<String> varsayilanPanelSirasi = ['gezgin', 'editor', 'ai'];
  List<String> panelSirasi = List.of(varsayilanPanelSirasi);

  /// [suruklenen] bölgeyi [hedef] bölgenin yerine koyar (ikisi yer değiştirir).
  void panelleriDegistir(String suruklenen, String hedef) {
    final i = panelSirasi.indexOf(suruklenen);
    final j = panelSirasi.indexOf(hedef);
    if (i < 0 || j < 0 || i == j) return;
    panelSirasi = List.of(panelSirasi)
      ..[i] = hedef
      ..[j] = suruklenen;
    notifyListeners();
  }

  /// Gezgin ile AI Asistan'ın yerini değiştirir (editör ortada kalır).
  void yanPanelleriDegistir() => panelleriDegistir('gezgin', 'ai');

  void panelSirasiAyarla(List<String> sira) {
    if (sira.length != 3 || !varsayilanPanelSirasi.every(sira.contains)) return;
    panelSirasi = List.of(sira);
    notifyListeners();
  }

  void panelSirasiniSifirla() {
    panelSirasi = List.of(varsayilanPanelSirasi);
    notifyListeners();
  }

  bool get panelSirasiVarsayilan =>
      listEquals(panelSirasi, varsayilanPanelSirasi);

  // Her sekmenin kendi terminali vardır: hangi sekmede terminalin açık
  // olduğu burada tutulur. Sekme değişince o sekmenin terminali açılır ya da
  // (açılmamışsa) panel kapanır. Ayarlar sekmesinin terminali yoktur.
  final Map<String, bool> _sekmeTerminali = {};
  String _aktifSekme = '';
  bool _ayarlarSekmesi = false;

  /// Açılışta geri yüklenen düzen henüz bir sekmeye uygulanmadıysa.
  bool? _ilkSekmeTerminali;

  /// TerminalProvider.sekmeleriIzle çağırır.
  void sekmeDegisti(String id, bool ayarlar) {
    if (id == _aktifSekme && ayarlar == _ayarlarSekmesi) return;
    _aktifSekme = id;
    _ayarlarSekmesi = ayarlar;
    if (!ayarlar && _ilkSekmeTerminali != null) {
      _sekmeTerminali[id] = _ilkSekmeTerminali!;
      _ilkSekmeTerminali = null;
    }
    showTerminal = !ayarlar && (_sekmeTerminali[id] ?? false);
    notifyListeners();
  }

  /// Kapanan sekmelerin terminal bilgisini siler.
  void sekmeleriTemizle(Set<String> kimlikler) {
    _sekmeTerminali.removeWhere((k, _) => k.isNotEmpty && !kimlikler.contains(k));
  }

  bool _terminalAcilabilir() {
    if (!_ayarlarSekmesi) return true;
    showToast('Ayarlar sekmesinin terminali yok; bir kod sekmesine geç.',
        SnackKind.info);
    return false;
  }

  void _terminalAyarla(bool acik) {
    showTerminal = acik;
    _sekmeTerminali[_aktifSekme] = acik;
  }

  void toggleTerminal() {
    if (!showTerminal && !_terminalAcilabilir()) return;
    _terminalAyarla(!showTerminal);
    notifyListeners();
  }

  /// Terminali (kapalıysa) odağı taşımadan açar.
  void revealTerminal() {
    if (showTerminal || !_terminalAcilabilir()) return;
    _terminalAyarla(true);
    notifyListeners();
  }

  /// Terminali (kapalıysa) açar ve klavye odağını komut satırına taşır.
  void focusTerminal() {
    if (!_terminalAcilabilir()) return;
    _terminalAyarla(true);
    _terminalFocusPending = true;
    terminalFocusTick++;
    notifyListeners();
  }

  bool consumeTerminalFocus() {
    final v = _terminalFocusPending;
    _terminalFocusPending = false;
    return v;
  }

  /// Panel düzeni (görünürlük + boyutlar); ayarlara kaydedilip açılışta
  /// geri yüklenir.
  Map<String, dynamic> layoutSnapshot() => {
        'gezgin': showExplorer,
        'sol_panel': solPanel,
        'ai': showAi,
        'terminal': showTerminal,
        'gezgin_genislik': sidebarWidth.round(),
        'ai_genislik': aiWidth.round(),
        'terminal_yukseklik': terminalHeight.round(),
        'panel_sirasi': panelSirasi,
      };

  void applyLayout(Object? raw) {
    if (raw is! Map) return;
    double? d(Object? v) => v is num ? v.toDouble() : null;
    bool? b(Object? v) => v is bool ? v : null;
    showExplorer = b(raw['gezgin']) ?? showExplorer;
    final panel = raw['sol_panel'];
    if (panel == 'gezgin' || panel == 'eklentiler') solPanel = panel as String;
    showAi = b(raw['ai']) ?? showAi;
    final sira = raw['panel_sirasi'];
    if (sira is List &&
        sira.length == 3 &&
        varsayilanPanelSirasi.every(sira.contains)) {
      panelSirasi = [for (final s in sira) '$s'];
    }
    final terminal = b(raw['terminal']);
    if (terminal != null) {
      // Kayıtlı düzendeki terminal, açılıştaki (ilk kod) sekmesinin
      // terminalidir.
      if (_aktifSekme.isEmpty || _ayarlarSekmesi) {
        _ilkSekmeTerminali = terminal;
        if (!_ayarlarSekmesi) showTerminal = terminal;
      } else {
        _terminalAyarla(terminal);
      }
    }
    sidebarWidth = (d(raw['gezgin_genislik']) ?? sidebarWidth).clamp(180, 420).toDouble();
    aiWidth = (d(raw['ai_genislik']) ?? aiWidth).clamp(280, 640).toDouble();
    terminalHeight =
        (d(raw['terminal_yukseklik']) ?? terminalHeight).clamp(120, 480).toDouble();
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

  /// Durum çubuğundaki ayrıntı (fare üzerine gelince tüm hata/uyarılar).
  String syntaxTooltip = '';

  /// Etkin dosyanın sorunları (hatalar ve uyarılar); Sorunlar penceresi ve
  /// editördeki dalgalı çizgiler bunu kullanır.
  List<Sorun> sorunlar = const [];

  void setSorunlar(List<Sorun> liste) {
    if (listEquals(liste, sorunlar)) return;
    sorunlar = liste;
    notifyListeners();
  }

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

  /// Bul seçenekleri (FindOptions) değişti: vurgular yeniden çizilir.
  int findOptionsVersion = 0;
  void bumpFindOptions() {
    findOptionsVersion++;
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

  /// Katalogdaki sağlayıcılar (öncelikli olanlar başta); boşsa yedek liste.
  List<AiSaglayici> aiSaglayicilar = [
    for (final id in kFallbackAiModels.keys)
      AiSaglayici(id: id, ad: id, yerel: id == 'yerel', anahtarGerekli: id != 'yerel'),
  ];

  /// Katalog kaynağı: "internet" | "disk" | "yedek".
  String aiKatalogKaynagi = 'yedek';

  AiSaglayici? saglayici(String id) {
    for (final s in aiSaglayicilar) {
      if (s.id == id) return s;
    }
    return null;
  }

  /// Kayıtlı sağlayıcı kimliği (eski "OpenAI"/"Claude" adları çevrilir).
  String get aiSaglayiciId {
    final ham = getString('ai_saglayici', fallback: 'openai');
    return kEskiSaglayiciAdlari[ham] ?? ham;
  }

  /// Görev -> atanmış sağlayıcı + model (atanmamış görev kapalıdır).
  Map<String, AiAtama> get gorevAtamalari {
    final v = _values['ai_gorev_atamalari'];
    final sonuc = <String, AiAtama>{};
    if (v is Map) {
      v.forEach((g, a) {
        final atama = AiAtama.coz(a);
        if (atama != null) sonuc[g.toString()] = atama;
      });
    }
    return sonuc;
  }

  AiAtama? gorevAtamasi(String gorev) => gorevAtamalari[gorev];

  /// Kodi'nin gerçekten kullandığı model: kendi görevi, yoksa AI Paneli
  /// sohbet modeli ("otomatik").
  AiAtama? get kodiAtamasi => gorevAtamasi('kodi') ?? gorevAtamasi('sohbet');

  String saglayiciAdi(String id) =>
      id == 'yerel' ? 'TürKod Yerel' : (saglayici(id)?.ad ?? id);

  /// "{Sağlayıcı ismi} • {Model ismi}".
  String atamaEtiketi(AiAtama a) => '${saglayiciAdi(a.saglayici)} • ${a.model}';

  /// Atamanın çalışması için anahtar gerekiyorsa girilmiş mi?
  bool atamaHazir(AiAtama a) {
    if (a.yerel) return true;
    final s = saglayici(a.saglayici);
    if (s == null || s.yerel || !s.anahtarGerekli) return true;
    return aiAnahtari(a.saglayici).isNotEmpty;
  }

  /// Ayarlar'da eklenen bulut modelleri.
  List<AiAtama> get aiBulutModelleri {
    final v = _values['ai_bulut_modelleri'];
    if (v is! List) return const [];
    final liste = <AiAtama>[];
    for (final a in v) {
      final atama = AiAtama.coz(a);
      if (atama != null && !liste.contains(atama)) liste.add(atama);
    }
    return liste;
  }

  /// Bağlı sağlayıcılar: API anahtarı kaydedilmiş ya da listede modeli olan
  /// bulut / yerel sunucu sağlayıcıları (sırası korunur).
  List<String> get bagliSaglayicilar =>
      bagliSaglayicilariBul(_values['ai_api_anahtarlari'], aiBulutModelleri);

  /// Görevlere atanabilen tüm modeller: bulut listesi + indirilmiş yerel modeller.
  List<AiAtama> get tumAiModelleri => [
        ...aiBulutModelleri,
        for (final m in aiModels['yerel'] ?? const <String>[]) AiAtama('yerel', m),
      ];

  Future<void> gorevAta(String gorev, AiAtama? a) async {
    final m = {for (final e in gorevAtamalari.entries) e.key: e.value.toJson()};
    a == null ? m.remove(gorev) : m[gorev] = a.toJson();
    await setValue('ai_gorev_atamalari', m);
  }

  /// Sohbet bilgisayardaki bir modelle mi yapılıyor (simge için)?
  bool get aiYerelMi {
    final a = gorevAtamasi('sohbet');
    return a != null && (a.yerel || (saglayici(a.saglayici)?.yerel ?? false));
  }

  /// AI paneli başlığında gösterilen etkin kaynak.
  String get aiOzet {
    final a = gorevAtamasi('sohbet');
    return a == null ? 'AI kapalı' : atamaEtiketi(a);
  }

  /// Sağlayıcı başına kayıtlı API anahtarı (eski tek anahtar yedek).
  String aiAnahtari(String id) {
    final m = _values['ai_api_anahtarlari'];
    if (m is Map && (m[id]?.toString() ?? '').isNotEmpty) return m[id].toString();
    return id == aiSaglayiciId ? getString('ai_api_key') : '';
  }

  /// Bir göreve (tamamlama, sohbet ...) atanmış yerel model.
  String? yerelGorevModeli(String gorev) {
    final a = gorevAtamasi(gorev);
    return a != null && a.yerel ? a.model : null;
  }

  /// Hayalet kod (AI tamamlama) bir modele atanmış ve kullanılabilir mi?
  bool get aiTamamlamaHazir {
    final a = gorevAtamasi('tamamlama');
    return a != null && atamaHazir(a);
  }

  /// Eklentiler panelinden kurulmuş eklentiler.
  Set<String> get eklentiler {
    final v = _values['eklentiler'];
    return v is List ? v.map((e) => e.toString()).toSet() : <String>{};
  }

  bool eklentiYuklu(String id) => eklentiler.contains(id);

  Future<void> eklentiAyarla(String id, bool yuklu) async {
    final yeni = eklentiler;
    yuklu ? yeni.add(id) : yeni.remove(id);
    await setValue('eklentiler', yeni.toList()..sort());
  }

  List<String> systemFonts = [];
  String fontsSource = '';
  bool _loaded = false;
  bool get loaded => _loaded;
  SettingsProvider(this._backend) {
    _init();
  }

  // Açılışta ayarlar okunamadıysa (backend yeniden başladı, istekler düştü)
  // bağlantı her geri geldiğinde yeniden denenir; eskiden oturum boyunca boş
  // değerlerle kalınıyordu.
  bool _okundu = false;
  StreamSubscription<bool>? _baglantiSub;

  Future<void> _init() async {
    _baglantiSub = _backend.connectionStream.listen((bagli) {
      if (bagli && !_okundu) unawaited(load().catchError((_) {}));
    });
    try {
      await _backend.waitUntilConnected();
      await load();
    } catch (_) {}
  }

  @override
  void dispose() {
    _baglantiSub?.cancel();
    _yenidenDeneTimer?.cancel();
    super.dispose();
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
      // Girinti genişliği (2/4/8) ve dosyadaki girintiyi algılama.
      'girinti_boyutu', 'girinti_algila',
      // Kullanıcının değiştirdiği klavye kısayolları {eylem kimliği: tuş}.
      'kisayollar',
      // Panel görünürlüğü ve boyutları (UiProvider.layoutSnapshot).
      'panel_duzeni',
      // Arayüz turu: ilk açılışta bir kez, istenirse her açılışta gösterilir.
      kTurHerAcilista, kTurGoruldu,
      // Sağlayıcı başına anahtarlar, özel adres, yerel model görevleri,
      // kurulu eklentiler ve eklenti ayarları.
      'ai_api_anahtarlari', 'ai_ozel_url', 'yerel_ai_gorevleri', 'eklentiler',
      'odak_suresi_dk', 'kod_parcaciklari', 'karalama_notlari',
      // Ayarlar → Editör: .trpy dosyası kaydedilirken biçimlendirilir.
      'kaydederken_bicimlendir',
      // Hayalet kod (Ayarlar → AI Kod Tamamlama).
      'ai_bulut_gorevleri', 'ai_dusunme', 'ai_gorev_atamalari', 'ai_bulut_modelleri',
      // Kodi (yardımcı robot) düşünsün mü, nerede duruyor?
      'kodi_dusunme', 'kodi_konum', 'kodi_balon', 'kodi_sesli',
      // Kodi'nin yetkileri (Ayarlar → Kodi; yalnızca kullanıcı değiştirir).
      kKodiYetkiAyar, kKodiYetkiEklenti, kKodiYetkiKomut, kKodiHepSor,
      kKodiSohbetKaydet, kKodiHafiza, kKodiGoruntu, kKodiYetkiTarayici,
      'ai_tamamlama_acik', 'ai_tamamlama_kaynagi', 'ai_tamamlama_saglayici',
      'ai_tamamlama_model', 'ai_tamamlama_gecikme', 'ai_tamamlama_cok_satir',
    ];
    // Aynı anda iki okuma (açılış + bağlantı geri geldi) birbirini ezmesin.
    final suren = _okuma;
    if (suren != null) return suren;
    final f = _oku(keys);
    _okuma = f;
    try {
      await f;
    } finally {
      _okuma = null;
    }
  }

  Future<void>? _okuma;
  Timer? _yenidenDeneTimer;
  int _denemeSayisi = 0;

  /// Ayarlar gerçekten (tamamı) okundu mu? Eskiden okuma başarısız olsa da
  /// [loaded] true oluyor, Ayarlar sayfası boş/varsayılan değerlerle
  /// açılıp "Kaydet" ile kullanıcının API anahtarlarını ve tüm ayarlarını
  /// siliyordu; panel düzeni ve arayüz turu da okunmamış değerlere göre
  /// karar veriyordu. Artık [loaded] yalnızca tam okumadan sonra true olur.
  bool get okundu => _okundu;

  Future<void> _oku(List<String> keys) async {
    // Tüm ayarlar tek istekle alınır (eskiden anahtar başına ayrı istek:
    // ~25 gidiş-dönüş). Başarısız olursa eski yönteme düşülür.
    var tam = false;
    var biri = false;
    try {
      final r = await _backend.call('ayarlar_tumu');
      final m = r['ayarlar'];
      if (m is Map) {
        for (final k in keys) {
          _values[k] = m[k];
        }
        tam = true;
      }
    } catch (_) {}
    if (!tam) {
      var eksik = false;
      for (final k in keys) {
        try {
          final r = await _backend.call('ayar_get', {'anahtar': k});
          _values[k] = r['deger'];
          biri = true;
        } catch (_) {
          eksik = true;
        }
      }
      // Eskiden tek bir anahtar okunabildiyse "okundu" sayılıp eksikler
      // bir daha hiç denenmiyordu.
      tam = !eksik;
    }
    _okundu = tam;
    if (tam) {
      _yenidenDeneTimer?.cancel();
      _denemeSayisi = 0;
      await refreshModels(silent: true);
      // Font listesi burada (açılışta) istenmez: Ayarlar sayfası açılınca
      // yüklenir. Düşük donanımda açılışı ve belleği gereksiz yere yoruyordu.
      _loaded = true;
      notifyListeners();
      return;
    }
    // Kısmi okumada gelen değerler (tema, yazı boyutu...) yine de uygulanır
    // ama ayarlar "yüklendi" sayılmaz; kısa bir süre sonra yeniden denenir.
    if (biri) notifyListeners();
    _yenidenDenePlanla();
  }

  void _yenidenDenePlanla() {
    _yenidenDeneTimer?.cancel();
    if (!_backend.isConnected) return; // bağlantı gelince dinleyici dener
    _denemeSayisi++;
    // 2, 4, 8, 16, 30, 30 ... saniye
    final sn = _denemeSayisi >= 5 ? 30 : (1 << _denemeSayisi);
    _yenidenDeneTimer = Timer(Duration(seconds: sn), () {
      if (!_okundu && _backend.isConnected) {
        unawaited(load().catchError((_) {}));
      }
    });
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
      final s = r['saglayicilar'];
      if (s is List && s.isNotEmpty) {
        aiSaglayicilar = [
          for (final e in s)
            if (e is Map) AiSaglayici.fromJson(e),
        ];
      }
      final k = r['katalog'];
      if (k is Map) aiKatalogKaynagi = k['kaynak']?.toString() ?? aiKatalogKaynagi;
      if (!silent) notifyListeners();
    } catch (_) {}
  }

  Future<void> setValue(String key, dynamic value) async {
    await _backend.call('ayar_set', {'anahtar': key, 'deger': value});
    _values[key] = value;
    notifyListeners();
  }

  /// Anında kaydedilen ayarlar için: kaydedilemezse (TürKod motoru bağlı
  /// değilken) kullanıcıya söylenir. Eskiden kutu sessizce eski hâlinde
  /// kalıyor, arka planda yakalanmamış hata oluşuyordu.
  Future<void> setValueBildir(BuildContext context, String key, dynamic value) =>
      setValue(key, value).catchError((Object e) {
        if (context.mounted) {
          showAppSnackbar(context, 'Ayar kaydedilemedi: $e', kind: SnackKind.error);
        }
      });

  /// Birden çok ayarı birlikte kaydeder; arayüz yalnızca bir kez yeniden
  /// kurulur. (Ayarlar sayfası eskiden ~20 ayrı setValue ile tüm uygulamayı
  /// ~20 kez yeniden kuruyordu.) Kaydedilemeyen ayar varsa ilk hata atılır,
  /// kaydedilenler yine de uygulanır.
  Future<void> setValues(Map<String, dynamic> values) async {
    Object? ilkHata;
    await Future.wait(values.entries.map((e) async {
      try {
        await _backend.call('ayar_set', {'anahtar': e.key, 'deger': e.value});
        _values[e.key] = e.value;
      } catch (err) {
        ilkHata ??= err;
      }
    }));
    notifyListeners();
    if (ilkHata != null) throw ilkHata!;
  }
}

class LanguageProvider extends ChangeNotifier {
  final BackendService _backend;
  bool loaded = false;
  StreamSubscription<bool>? _baglantiSub;
  bool _yukleniyor = false;
  LanguageProvider(this._backend) {
    // İlk deneme düşerse (backend açılışta yeniden başladı) vurgulama oturum
    // boyunca kurulmuyordu: bağlantı her geri geldiğinde yeniden denenir.
    _baglantiSub = _backend.connectionStream.listen((bagli) {
      if (bagli && !loaded) unawaited(_init());
    });
    _init();
  }

  @override
  void dispose() {
    _baglantiSub?.cancel();
    super.dispose();
  }

  Future<void> _init() async {
    if (_yukleniyor || loaded) return;
    _yukleniyor = true;
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
    } catch (_) {
    } finally {
      _yukleniyor = false;
    }
  }
}

class EditorProvider extends ChangeNotifier {
  final BackendService _backend;
  final List<EditorTab> _tabs = [];
  final ValueNotifier<String> activeContent = ValueNotifier<String>('');
  int _active = -1;
  int _revision = 0;
  int _untitledCounter = 1;
  bool _sessionLoaded = false, _sessionLoading = false;
  StreamSubscription<bool>? _oturumBaglantiSub;
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

  /// Editörün geri al / yinele işlemleri (editör kurulu değilse null).
  VoidCallback? undo;
  VoidCallback? redo;

  /// Düzenle menüsünden kes / kopyala / yapıştır / tümünü seç (klavyede
  /// Ctrl+X/C/V/A editörün kendi kısayollarıdır).
  VoidCallback? kes;
  VoidCallback? kopyala;
  VoidCallback? yapistir;
  VoidCallback? tumunuSec;

  /// Çoklu imleç komutları ('asagi', 'yukari', 'sonraki', 'tumu', 'temizle');
  /// editör kurulu değilse null.
  void Function(String komut)? cokluImlec;

  /// Sekme çubuğunun "kapat" akışı (kaydedilmemişse sorar); Ctrl+W kullanır.
  Future<void> Function(int index)? sekmeKapatIste;

  /// Oturuma sekme başına ek bilgi yazmak / okumak için (breakpoint'ler).
  Map<String, dynamic> Function(String tabId)? sessionExtras;
  void Function(String tabId, Map<String, dynamic> data)? restoreExtras;

  /// Son açılan / kaydedilen dosyalar (en yenisi başta).
  final List<String> recentFiles = [];
  static const int _maxRecent = 15;

  void _rememberRecent(String path) {
    if (path.startsWith('untitled:') || ozelSekmeMi(path)) return;
    recentFiles.removeWhere((x) => p.equals(x, path));
    recentFiles.insert(0, path);
    if (recentFiles.length > _maxRecent) {
      recentFiles.removeRange(_maxRecent, recentFiles.length);
    }
    _backend
        .call('ayar_set', {'anahtar': 'son_dosyalar', 'deger': recentFiles})
        .catchError((_) => <String, dynamic>{});
  }

  void forgetRecent(String path) {
    recentFiles.removeWhere((x) => p.equals(x, path));
    _backend
        .call('ayar_set', {'anahtar': 'son_dosyalar', 'deger': recentFiles})
        .catchError((_) => <String, dynamic>{});
    notifyListeners();
  }

  Future<void> _loadRecent() async {
    try {
      final r = await _backend.call('ayar_get', {'anahtar': 'son_dosyalar'});
      final l = r['deger'];
      if (l is List) {
        recentFiles
          ..clear()
          ..addAll(l.map((e) => e.toString()).where((e) => e.isNotEmpty));
      }
    } catch (_) {}
  }

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
    // Kanal backend'i beklemeden bağlanır: editör açılırken gelen dosyalar
    // Windows tarafında takılı kalmaz, burada oturum hazır olana kadar bekler.
    unawaited(_tekOrnekKanaliniBagla());
    _init();
  }
  final Completer<void> _oturumHazir = Completer<void>();
  Future<void> _init() async {
    try {
      await _backend.waitUntilConnected();
      await _loadRecent();
      await loadSession();
    } catch (_) {}
    for (final yol in kAcilisDosyalari) {
      try {
        await openFile(yol);
      } catch (_) {}
    }
    kAcilisDosyalari = const [];
    if (!_oturumHazir.isCompleted) _oturumHazir.complete();
    // Açılışta oturum okunamadıysa (bağlantı koptu, backend yeniden başladı)
    // bağlantı her geri geldiğinde yeniden denenir.
    _oturumBaglantiSub = _backend.connectionStream.listen((bagli) {
      if (bagli && !_sessionLoaded) unawaited(loadSession());
    });
    if (_backend.isConnected && !_sessionLoaded) unawaited(loadSession());
  }

  /// Editör zaten açıkken "Editör ile aç" yeni pencere açmaz: Windows tarafı
  /// (runner/main.cpp) dosyaları bu pencereye iletir; burada sekme olarak açılır.
  static const _tekOrnekKanali = MethodChannel('turkod/tek_ornek');

  Future<void> _tekOrnekKanaliniBagla() async {
    Future<void> ac(Object? liste) async {
      if (liste is! List || liste.isEmpty) return;
      await _oturumHazir.future;
      for (final yol in liste) {
        try {
          await openFile(p.normalize(yol.toString()));
        } catch (_) {}
      }
    }

    _tekOrnekKanali.setMethodCallHandler((call) async {
      if (call.method == 'dosyalariAc') await ac(call.arguments);
      return null;
    });
    try {
      // O ana kadar biriken (editör açılırken gelen) dosyalar.
      await ac(await _tekOrnekKanali.invokeMethod<List<Object?>>('hazir'));
    } catch (_) {
      // Windows dışı / test ortamı: kanal yok.
    }
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
            child: const Text('Vazgeç'),
          ),
        ],
      ),
    );

    if (choice == 'yes') return suggested;
    return null;
  }
  void _rememberActiveCaret() {
    final t = activeTab;
    if (t == null || ozelSekmeMi(t.path)) return;

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
    if (_sessionLoaded || _sessionLoading) return;
    _sessionLoading = true;
    try {
      final r = await _backend.call('oturum_oku');
      final ham = r['son_oturum'];
      final rawList = ham is List ? ham : const [];
      // Kaydedilen listedeki her girdinin hangi sekmeyi oluşturduğu: açılamayan
      // (silinmiş) dosyalar aktif sekme sırasını kaydırmasın.
      final restoredIds = <String?>[];
      var kurtarilanSayisi = 0;

      for (final e in rawList) {
        final onceki = _tabs.length;
        try {
          if (e is String) {
            if (!ozelSekmeMi(e)) {
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

            if (yol != null && yol.isNotEmpty && !ozelSekmeMi(yol)) {
              final yedek = m['yedek'];
              try {
                await openFile(
                  yol,
                  makeActive: false,
                  saveSession: false,
                );
              } catch (_) {
                if (yedek is! String) rethrow;
              }
              if (yedek is String) {
                _yedegiUygula(yol, isim, yedek, m['yedek_zaman'], onceki);
                kurtarilanSayisi++;
              }
            } else if (isim != null && isim.isNotEmpty) {
              await createUntitled(
                name: isim,
                content: icerik,
                setActive: false,
                saveSession: false,
              );
            }
            if (_tabs.length > onceki) _restoreTabExtras(_tabs.last, m);
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
      if (kurtarilanSayisi > 0) {
        kurtarilanDegisiklik.value = kurtarilanSayisi;
      }
      _revision++;
      notifyListeners();
    } catch (_) {
    } finally {
      _sessionLoading = false;
    }
  }

  /// Çökmeden kurtarılan kaydedilmemiş değişiklik sayısı (arayüz bildirir).
  final ValueNotifier<int> kurtarilanDegisiklik = ValueNotifier(0);

  /// Kurtarma yedeğini sekmeye uygular. Dosya yedekten sonra diskte
  /// değiştiyse (kaydedildi) yedek eskidir, uygulanmaz. Dosya silinmiş ya da
  /// açılamıyorsa yedek adsız bir sekmede açılır; değişiklik kaybolmaz.
  void _yedegiUygula(String yol, String? isim, String yedek, Object? zaman,
      int oncekiSekmeSayisi) {
    if (_tabs.length > oncekiSekmeSayisi && _tabs.last.path == yol) {
      final t = _tabs.last;
      int? simdi;
      try {
        simdi = File(yol).lastModifiedSync().millisecondsSinceEpoch;
      } catch (_) {}
      if (zaman is num && simdi != null && simdi != zaman.toInt()) return;
      if (t.content == yedek) return;
      t.content = yedek;
      t.dirty = true;
      return;
    }
    _tabs.add(EditorTab(
      path: 'untitled:${DateTime.now().microsecondsSinceEpoch}',
      name: '${isim ?? p.basename(yol)} (kurtarılan)',
      content: yedek,
      dirty: true,
    ));
  }

  /// Breakpoint sağlayıcısı henüz kurulmadıysa geri yüklenen ek bilgiler
  /// (breakpoint'ler) burada bekler; sağlayıcı kurulunca [takePendingExtras]
  /// ile alır.
  final Map<String, Map<String, dynamic>> _pendingExtras = {};

  Map<String, Map<String, dynamic>> takePendingExtras() {
    final m = Map<String, Map<String, dynamic>>.from(_pendingExtras);
    _pendingExtras.clear();
    return m;
  }

  void _restoreTabExtras(EditorTab t, Map<String, dynamic> m) {
    final imlec = m['imlec'];
    if (imlec is num) {
      _caretMemory[t.path] = imlec.toInt().clamp(0, t.content.length).toInt();
    }
    final arg = m['argumanlar'];
    if (arg is String) t.runArgs = arg;
    final cb = restoreExtras;
    if (cb != null) {
      cb(t.id, m);
    } else {
      _pendingExtras[t.id] = m;
    }
  }

  /// Kaydedilen sekme listesi Ayarlar sekmesini içermez; aktif sıra da o
  /// listeye göre hesaplanmalı (eskiden Ayarlar sekmesi soldayken geri
  /// yüklemede yanlış sekme aktif oluyordu).
  Map<String, dynamic> _sessionPayload({bool yedekler = true}) {
    _rememberActiveCaret();
    final kayitli = _tabs.where((t) => !ozelSekmeMi(t.path)).toList();
    final aktifId = activeTab?.id;
    final sira = kayitli.indexWhere((t) => t.id == aktifId);
    Map<String, dynamic> ek(EditorTab t) => {
          if (_caretMemory[t.path] != null) 'imlec': _caretMemory[t.path],
          if (t.runArgs.isNotEmpty) 'argumanlar': t.runArgs,
          ...?sessionExtras?.call(t.id),
        };
    // Kurtarma yedeği: kaydedilmemiş dosya değişiklikleri de oturuma yazılır.
    // Eskiden yalnızca dosya yolu saklandığından çökme / elektrik kesintisinde
    // (otomatik kayıt varsayılan olarak kapalı) bu değişiklikler kayboluyordu.
    // 'yedek_zaman': yedek alınırken dosyanın diskteki değişme zamanı; dosya
    // sonradan kaydedildiyse eski yedek geri yüklenmez.
    Map<String, dynamic> yedek(EditorTab t) {
      if (!yedekler || !t.dirty) return const {};
      int? zaman;
      try {
        zaman = File(t.path).lastModifiedSync().millisecondsSinceEpoch;
      } catch (_) {}
      return {'yedek': t.content, 'yedek_zaman': zaman};
    }

    return {
      'sekmeler': kayitli
          .map((t) => t.path.startsWith('untitled:')
              ? {'yol': null, 'isim': t.name, 'icerik': t.content, ...ek(t)}
              : {'yol': t.path, 'isim': t.name, 'icerik': null, ...yedek(t), ...ek(t)})
          .toList(),
      'aktif_sira': sira < 0 ? 0 : sira,
    };
  }

  /// Sekmenin argümanlarını değiştirir (oturuma kaydedilir).
  void setRunArgs(String tabId, String args) {
    final i = _tabs.indexWhere((t) => t.id == tabId);
    if (i < 0) return;
    _tabs[i].runArgs = args.trim();
    notifyListeners();
    _saveSession();
  }

  /// Oturum yazımları sıraya konur. Eskiden istekler backend'de paralel
  /// işlendiğinden 2 sn'lik yedek zamanlayıcısının isteği "Kaydetmeden
  /// Çık"tan SONRA bitip atılan değişiklikleri bir sonraki açılışta geri
  /// getirebiliyor, sekme listesiyle aktif sekme farklı isteklerden
  /// karışabiliyordu. İçerik, sıra gelince (en güncel hâliyle) hazırlanır.
  Future<void> _oturumZinciri = Future<void>.value();

  Future<bool> _oturumYaz(Map<String, dynamic> Function() icerik) {
    final sonuc = Completer<bool>();
    _oturumZinciri = _oturumZinciri.then((_) async {
      try {
        await _backend
            .call('oturum_kaydet', icerik())
            .timeout(const Duration(seconds: 10));
        sonuc.complete(true);
      } catch (_) {
        sonuc.complete(false);
      }
    });
    return sonuc.future;
  }

  /// "Kaydetmeden Çık" seçildi: bundan sonra kurtarma yedeği yazılmaz.
  bool _yedekKapali = false;

  /// Oturum yazıldıysa true. Bağlantı yoksa false döner (eskiden hata
  /// sessizce yutuluyor, çıkışta adsız sekmeler sorulmadan kayboluyordu).
  Future<bool> _saveSession({bool yedekler = true}) {
    _yedekTimer?.cancel();
    // Kayıtlı oturum henüz okunmadıysa (backend açılışta yanıt vermedi ya da
    // yükleme sürüyor) yazılmaz: eksik sekme listesi, adsız sekmeleri ve
    // kurtarma yedeklerini tutan kayıtlı oturumun üzerine yazıyordu.
    if (!_sessionLoaded) return Future<bool>.value(false);
    return _oturumYaz(
        () => _sessionPayload(yedekler: yedekler && !_yedekKapali));
  }

  /// Yazmaya ara verildikten kısa süre sonra oturum (kurtarma yedeğiyle)
  /// kaydedilir; çökme olursa en fazla son ~2 saniye kaybolur.
  Timer? _yedekTimer;
  static const Duration _yedekGecikmesi = Duration(seconds: 2);
  void _yedekZamanla() {
    _yedekTimer?.cancel();
    if (_yedekKapali) return;
    _yedekTimer = Timer(_yedekGecikmesi, _saveSession);
  }

  /// Çıkışta oturumu (adsız sekmelerin içeriği dahil) kaydeder. Backend
  /// yanıt vermezse pencerenin kapanmasını engellememek için kısa süre
  /// beklenir. Oturum yazılabildiyse true döner.
  /// [yedekler]: false ise kaydedilmemiş değişikliklerin yedeği silinir
  /// ("Kaydetmeden Çık": kullanıcı bilerek attığı değişikliği geri görmesin).
  Future<bool> saveSessionNow({bool yedekler = true}) async {
    if (!yedekler) {
      _yedekKapali = true;
      _yedekTimer?.cancel();
    }
    final ok = await _saveSession(yedekler: yedekler)
        .timeout(const Duration(seconds: 3), onTimeout: () => false);
    // Çıkılamadıysa (pencere açık kalıyor) yedekleme yeniden çalışsın.
    if (!ok) _yedekKapali = false;
    return ok;
  }

  /// İçinde yazı olan adsız sekmeler: yalnızca oturumda saklanırlar.
  List<EditorTab> get adsizIcerikliSekmeler => _tabs
      .where((t) =>
          t.path.startsWith('untitled:') && t.content.trim().isNotEmpty)
      .toList();

  // Aynı dosyaya yapılan kayıtlar sıraya konur: komutlar backend'de paralel
  // işlendiğinden otomatik kayıt ile Ctrl+S ters sırada bitip diske ESKİ
  // içeriği yazabiliyordu.
  final Map<String, Future<void>> _saveChains = {};

  Future<void> _writeFile(String path, String content) {
    // PDF sekmesinde metin yoktur; yazmak dosyayı bozardı.
    if (pdfYoluMu(path)) return Future<void>.value();
    final onceki = _saveChains[path] ?? Future<void>.value();
    // Diskteki değişme zamanı yazmayla AYNI adımda kaydedilir: eskiden ayrı
    // bir then() içindeydi; hızlı iki Ctrl+S'te (ya da otomatik kayıtla
    // çakışınca) ikinci kayıt, ilk yazma diske ulaşmış ama zamanı henüz
    // kaydedilmemişken bakıp yersiz "Dosya diskte değişti" soruyordu.
    final yazma = onceki.then((_) async {
      final r = await _backend
          .call('dosya_kaydet', {'yol': path, 'icerik': content});
      _diskZamaniniKaydet(path);
      return r;
    });
    _saveChains[path] = yazma.then<void>((_) {}, onError: (_) {});
    // Kaydedilen dosyanın eski yedeği oturumdan kalksın.
    yazma.then((_) => _yedekZamanla(), onError: (_) {});
    return yazma.then<void>((r) {
      // Dosya özgün kodlamasıyla (ör. cp1254) yazılamadıysa backend UTF-8'e
      // geçip uyarır; kullanıcı bunu bilmeli.
      final uyari = r['uyari']?.toString();
      if (uyari != null && uyari.isNotEmpty) kayitUyarisi?.call(uyari);
    });
  }

  /// Dosya diskte yok mu (gezginde / dışarıdan silinmiş ya da taşınmış)?
  static bool _diskteYok(String yol) {
    try {
      return !File(yol).existsSync();
    } catch (_) {
      return false;
    }
  }

  /// Silinmiş bir dosya Ctrl+S ile kaydedilmek istendi: true dönerse dosya
  /// yeniden oluşturulur. Atanmamışsa yeniden oluşturulur.
  Future<bool> Function(EditorTab t)? silinenDosyaSor;

  /// Farklı Kaydet'in hedefi, kaydedilmemiş değişiklikleri olan [digeri]
  /// sekmesinde açık: true dönerse üzerine yazılır ve o sekme kapanır.
  /// Atanmamışsa kaydedilmez (değişiklik sessizce kaybolmasın).
  Future<bool> Function(EditorTab digeri)? farkliKaydetHedefKirliSor;

  /// Kayıt sırasında backend'in döndürdüğü uyarıyı gösterir (arayüz atar).
  void Function(String mesaj)? kayitUyarisi;

  // Açık dosyaların diskteki son bilinen değişme zamanı (ms). Başka bir
  // program dosyayı değiştirdiyse kaydetmeden önce sorulur; eskiden Ctrl+S ve
  // otomatik kayıt o değişikliği uyarmadan eziyordu.
  final Map<String, int> _diskZamani = {};

  /// Kaydedilecek dosya diskte dışarıdan değişmişse çağrılır; true dönerse
  /// dosyanın üzerine yazılır. Atanmamışsa üzerine yazılmaz.
  Future<bool> Function(EditorTab t)? diskCakismasiSor;

  static int? _diskZamaniOku(String yol) {
    try {
      return File(yol).lastModifiedSync().millisecondsSinceEpoch;
    } catch (_) {
      return null;
    }
  }

  void _diskZamaniniKaydet(String yol) {
    final z = _diskZamaniOku(yol);
    if (z == null) {
      _diskZamani.remove(p.canonicalize(yol));
    } else {
      _diskZamani[p.canonicalize(yol)] = z;
    }
  }

  /// Dosya, IDE'nin son okuduğu / yazdığı andan sonra diskte değiştiyse true.
  bool diskteDegisti(String yol) {
    final bilinen = _diskZamani[p.canonicalize(yol)];
    if (bilinen == null) return false;
    final z = _diskZamaniOku(yol);
    return z != null && z != bilinen;
  }

  /// Dışarıdan değişen dosyaları denetler (pencere yeniden odaklanınca):
  /// kaydedilmemiş değişikliği olmayan sekmeler diskten yeniden yüklenir;
  /// kirli sekmeler bırakılır, çakışma kaydederken sorulur.
  Future<void> diskiDenetle() async {
    for (final t in List<EditorTab>.from(_tabs)) {
      if (t.filePath == null || t.dirty || !diskteDegisti(t.path)) continue;
      try {
        final r = await _backend.call('dosya_oku', {'yol': t.path});
        final yeni = r['icerik']?.toString();
        if (yeni == null || t.dirty || !_tabs.contains(t)) continue;
        _diskZamaniniKaydet(t.path);
        if (yeni == t.content) continue;
        final eski = t.content;
        t.content = yeni;
        onContentEdited?.call(t.id, eski, yeni);
        if (identical(activeTab, t)) activeContent.value = yeni;
        _revision++;
        notifyListeners();
      } catch (_) {}
    }
  }

  /// Dosya dışarıdan değiştiyse kullanıcıya sorar; yazılabilirse true.
  Future<bool> _cakismaYoksaYaz(EditorTab t) async {
    // Bu dosyaya kendi yazmamız sürüyorsa önce o bitsin (bkz. _writeFile).
    final suren = _saveChains[t.path];
    if (suren != null) await suren;
    // Açıldığı sırada diskte olan dosya artık yoksa (silindi / taşındı)
    // sessizce yeniden oluşturulmaz; sorulur.
    if (t.filePath != null &&
        _diskZamani.containsKey(p.canonicalize(t.path)) &&
        _diskteYok(t.path)) {
      final sor = silinenDosyaSor;
      return sor == null || await sor(t);
    }
    if (!diskteDegisti(t.path)) return true;
    final sor = diskCakismasiSor;
    return sor != null && await sor(t);
  }

  Future<void> openFile(
    String path, {
    bool makeActive = true,
    bool saveSession = true,
    BuildContext? context,
  }) async {
    // p.equals: Windows'ta büyük/küçük harf ve ayırıcı farkı aynı dosyadır
    // (komut satırı, tek örnek kanalı ve gezgin farklı yazımla gönderebilir).
    final idx = _tabs.indexWhere((t) => p.equals(t.path, path));

    if (idx >= 0) {
      if (makeActive) setActive(idx);
      return;
    }

    // PDF: içerik okunmaz, sekme görüntüleyiciyle açılır.
    final r = pdfYoluMu(path)
        ? <String, dynamic>{'yol': path, 'isim': p.basename(path), 'icerik': ''}
        : await _backend.call('dosya_oku', {'yol': path});

    var name = r['isim']?.toString() ?? p.basename(path);
    final resolvedPath = r['yol']?.toString() ?? path;

    // Okuma sürerken aynı dosya (çift tıklama / iki hızlı seçim) zaten
    // açılmış olabilir: ikinci sekme açılmaz; ikisinden biri kaydedilince
    // diğerindeki değişiklikler sessizce eziliyordu.
    final simdi = _tabs.indexWhere(
        (t) => p.equals(t.path, resolvedPath) || p.equals(t.path, path));
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
    _diskZamaniniKaydet(resolvedPath);
    if (saveSession) _rememberRecent(resolvedPath);

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

  /// [dirty]: içerik kaydedilmemiş yeni bir sonuçsa (Çevir / Düzelt "yeni
  /// sekmede aç") true; sekme kapatılırken kaydetme sorulur.
  Future<void> createUntitled({
    String? name,
    String content = '',
    bool setActive = true,
    bool saveSession = true,
    bool dirty = false,
    BuildContext? context,
  }) async {
    String? desiredOrNull = name;
    if (desiredOrNull == null) {
      // Oturumdan geri yüklenen "Untitled-N" sekmeleri sayacı ilerletmiyordu;
      // Ctrl+T ad çakışması penceresi açıyordu.
      do {
        desiredOrNull = 'Adsız-${_untitledCounter++}.trpy';
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
        dirty: dirty,
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

  /// IDE içindeki tarayıcı sekmesini açar (varsa ona geçer).
  void openBrowser() {
    final i = _tabs.indexWhere((t) => t.path == kTarayiciPath);
    if (i >= 0) {
      setActive(i);
      return;
    }
    _tabs.add(EditorTab(path: kTarayiciPath, name: 'Tarayıcı', content: ''));
    _rememberActiveCaret();
    _active = _tabs.length - 1;
    activeContent.value = '';
    _pendingCaretOffset = null;
    _revision++;
    notifyListeners();
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
    if (t == null || ozelSekmeMi(t.path) || t.content == val) return;
    final old = t.content;
    t.content = val;
    activeContent.value = val;
    onContentEdited?.call(t.id, old, val);
    _yedekZamanla();
    if (!t.dirty) {
      t.dirty = true;
      notifyListeners();
    }
  }

  void replaceActiveContent(String val) {
    final t = activeTab;
    if (t == null || ozelSekmeMi(t.path)) return;
    final old = t.content;
    t.content = val;
    t.dirty = true;
    activeContent.value = val;
    if (old != val) onContentEdited?.call(t.id, old, val);
    _yedekZamanla();
    _revision++;
    notifyListeners();
  }

  /// [tabId] sekmesinin içeriğini değiştirir (aktif olmasa da). Uzun süren
  /// işlemler (Akıllı Düzeltme) sonucu, işlem başladığında aktif olan sekmeye
  /// yazmak için kullanılır; eskiden o sırada aktif olan sekmeye yazılıyordu.
  /// Sekme kapatılmışsa false.
  bool replaceContentOf(String tabId, String val) {
    final i = _tabs.indexWhere((t) => t.id == tabId);
    if (i < 0) return false;
    final t = _tabs[i];
    // PDF'in ve özel sekmelerin metni yoktur; yazılırsa sekme kirli olur.
    if (t.isPdf || ozelSekmeMi(t.path)) return false;
    if (i == _active) {
      replaceActiveContent(val);
      return true;
    }
    final old = t.content;
    if (old == val) return true;
    t.content = val;
    t.dirty = true;
    onContentEdited?.call(t.id, old, val);
    // Yan bölmedeki (etkin olmayan sekme) düzenlemeler de kurtarma
    // yedeğine girsin; eskiden çökmede kayboluyordu.
    _yedekZamanla();
    notifyListeners();
    return true;
  }

  /// Gezginde bir dosya / klasör yeniden adlandırıldı: o yoldaki (ya da o
  /// klasörün altındaki) açık sekmelerin yolları güncellenir.
  void renamePath(String oldPath, String newPath) {
    var changed = false;
    for (var i = 0; i < _tabs.length; i++) {
      final t = _tabs[i];
      if (t.filePath == null) continue;
      String? yeni;
      if (p.equals(t.path, oldPath)) {
        yeni = newPath;
      } else if (p.isWithin(oldPath, t.path)) {
        yeni = p.join(newPath, p.relative(t.path, from: oldPath));
      }
      if (yeni == null) continue;
      var name = p.basename(yeni);
      while (_tabs.any((x) => x.id != t.id && x.name == name)) {
        name = suggestUniqueName(name);
      }
      _tabs[i] = EditorTab(
        id: t.id,
        path: yeni,
        name: name,
        content: t.content,
        dirty: t.dirty,
        runArgs: t.runArgs,
      );
      if (_caretMemory.containsKey(t.path)) {
        _caretMemory[yeni] = _caretMemory.remove(t.path)!;
      }
      changed = true;
    }
    for (var i = 0; i < recentFiles.length; i++) {
      if (p.equals(recentFiles[i], oldPath)) recentFiles[i] = newPath;
    }
    if (changed) {
      notifyListeners();
      _saveSession();
    }
  }

  /// Gezginde silinen dosyanın (ya da klasörün altındaki dosyaların) açık
  /// sekmeleri kaydedilmemiş sayılır: içerik kaybolmaz, kapatırken sorulur.
  void markDeleted(String path) {
    var changed = false;
    for (final t in _tabs) {
      if (t.filePath == null) continue;
      if (p.equals(t.path, path) || p.isWithin(path, t.path)) {
        t.dirty = true;
        changed = true;
      }
    }
    recentFiles.removeWhere((x) => p.equals(x, path) || p.isWithin(path, x));
    if (changed) notifyListeners();
  }

  /// Kaydedildiyse true; kullanıcı Farklı Kaydet'i iptal ettiyse false.
  Future<bool> saveTab(int index) async {
    if (index < 0 || index >= _tabs.length) return false;
    final t = _tabs[index];
    if (ozelSekmeMi(t.path) || t.isPdf) return false;
    if (t.path.startsWith('untitled:')) {
      return saveAsTab(index);
    }
    if (!await _cakismaYoksaYaz(t)) return false;
    if (kaydederkenBicimlendir != null &&
        kaydederkenBicimlendir!() &&
        t.path.toLowerCase().endsWith('.trpy')) {
      await _bicimlendir(index);
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

  /// Etkin editörde hayalet kod önerisi ister (Ctrl+Shift+Boşluk).
  VoidCallback? hayaletIste;

  /// Ayarlar → "Kaydederken biçimlendir" açık mı (HomeShell bağlar).
  bool Function()? kaydederkenBicimlendir;

  /// Sekmenin içeriğini backend'in biçimlendiricisinden geçirir. Hata olursa
  /// (sözdizimi hatalı kod) içerik olduğu gibi kaydedilir.
  Future<void> _bicimlendir(int index) async {
    final t = _tabs[index];
    try {
      final r = await _backend.call('kodu_bicimlendir', {'kod': t.content});
      final yeni = r['kod']?.toString();
      if (yeni == null || yeni == t.content || index >= _tabs.length ||
          _tabs[index] != t) {
        return;
      }
      if (index == _active && uiController != null) {
        final c = uiController!;
        final imlec = c.selection.isValid
            ? c.selection.baseOffset.clamp(0, yeni.length)
            : yeni.length;
        _setControllerValueProgrammatic(
            c,
            TextEditingValue(
                text: yeni, selection: TextSelection.collapsed(offset: imlec)));
        syncFromView();
      } else {
        t.content = yeni;
      }
    } catch (_) {}
  }

  Future<bool> saveAsTab(int index, {BuildContext? context}) async {
    if (index < 0 || index >= _tabs.length) return false;

    final t = _tabs[index];
    if (ozelSekmeMi(t.path) || t.isPdf) return false;

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

    // Hedef dosya başka bir sekmede kaydedilmemiş değişikliklerle açıksa
    // önce sorulur: eskiden o sekme sorulmadan kapatılıp değişiklikleri
    // kayboluyordu.
    final kirliHedef = _tabs
        .where((x) =>
            x.id != t.id &&
            x.dirty &&
            !ozelSekmeMi(x.path) &&
            p.equals(x.path, path))
        .firstOrNull;
    if (kirliHedef != null) {
      final sor = farkliKaydetHedefKirliSor;
      if (sor == null || !await sor(kirliHedef)) return false;
    }

    final snap = t.content;
    await _writeFile(path, snap);

    // Hedef dosya başka bir sekmede açıksa o sekme kapatılır (kullanıcı
    // dosyanın üzerine yazmayı onayladı): eskiden aynı yola iki sekme kalıyor,
    // eski sekme sonraki kayıtta (Ctrl+S, çıkışta "Kaydet") yeni içeriği
    // eskisiyle değiştiriyordu.
    for (var i = _tabs.length - 1; i >= 0; i--) {
      final x = _tabs[i];
      if (x.id != t.id && !ozelSekmeMi(x.path) && p.equals(x.path, path)) {
        await closeTab(i);
      }
    }

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
      runArgs: guncel.runArgs,
    );
    _rememberRecent(path);

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

    final kapanan = _tabs.removeAt(index);
    if (kapanan.path == kTarayiciPath) kTarayici.kapat();

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
  /// Tüm kaydedilmemiş sekmeleri kaydeder (adsız sekmeler için Farklı
  /// Kaydet sorulur). Kaydedilen sekme sayısını döndürür.
  Future<int> saveAll({BuildContext? context}) async {
    var sayi = 0;
    for (final t in List<EditorTab>.from(_tabs)) {
      if (ozelSekmeMi(t.path) || !t.dirty) continue;
      final i = _tabs.indexOf(t);
      if (i < 0) continue;
      final kaydedildi = t.path.startsWith('untitled:')
          ? await saveAsTab(i, context: context)
          : await saveTab(i);
      if (kaydedildi) sayi++;
    }
    return sayi;
  }

  Future<bool> saveAllForExit() async {
    try {
      for (final t in List<EditorTab>.from(_tabs)) {
        if (ozelSekmeMi(t.path) ||
            t.path.startsWith('untitled:') ||
            !t.dirty) {
          continue;
        }
        if (!await _cakismaYoksaYaz(t)) return false;
        final snap = t.content;
        await _writeFile(t.path, snap);
        if (t.content == snap) t.dirty = false;
      }
      // Diğer oturum yazımlarıyla aynı sıradan geçer (bkz. _oturumYaz).
      final ok = await _oturumYaz(_sessionPayload);
      notifyListeners();
      return ok;
    } catch (_) {
      return false;
    }
  }


  /// Kaydedilmemiş tüm dosya sekmelerini yazar (yalnızca aktif sekmeyi değil).
  /// Diskte dışarıdan değişen dosyalar sessizce ezilmez; kirli kalır.
  /// Diskte artık olmayan (gezginde silinen / taşınan) dosyalar da yazılmaz:
  /// eskiden otomatik kayıt silinen dosyayı geri oluşturuyordu. Yeniden
  /// oluşturmak yalnızca Ctrl+S ile (sorularak) yapılır.
  void autoSave() {
    for (final t in List<EditorTab>.from(_tabs)) {
      if (!t.dirty || t.filePath == null || t.isPdf) continue;
      if (_diskteYok(t.path)) continue;
      if (diskteDegisti(t.path)) continue;
      final snap = t.content;
      _writeFile(t.path, snap).then((_) {
        // Kayıt sürerken yazılan tuşlar "kaydedildi" sayılmasın.
        if (t.content == snap) t.dirty = false;
        notifyListeners();
      }).catchError((_) {});
    }
  }

  @override
  void dispose() {
    _yedekTimer?.cancel();
    _oturumBaglantiSub?.cancel();
    kurtarilanDegisiklik.dispose();
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
        fazlaOge: _fazlaOge(r),
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
        node.fazlaOge = _fazlaOge(r);
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

  FileNode? _find(FileNode? node, String path) {
    if (node == null) return null;
    if (p.equals(node.path, path)) return node;
    for (final c in node.children) {
      if (c.isDir && (p.equals(c.path, path) || p.isWithin(c.path, path))) {
        return _find(c, path);
      }
    }
    return null;
  }

  /// Bir klasörün içeriğini yeniden okur; alt klasörlerin açık/kapalı
  /// durumu korunur.
  Future<void> reloadDir(String dir) async {
    final node = _find(_root, dir);
    if (node == null || !node.loaded) return;
    try {
      final r = await _backend.call('dosya_agaci', {'dizin': node.path});
      final eski = {for (final c in node.children) c.path: c};
      node.children = [
        for (final c in _parse(r['ogeler']))
          if (eski[c.path] != null && eski[c.path]!.isDir == c.isDir)
            eski[c.path]!
          else
            c,
      ];
      node.fazlaOge = _fazlaOge(r);
      node.expanded = true;
    } catch (_) {}
    notifyListeners();
  }

  /// Yeni dosya / klasör oluşturur; hata metni ya da null döner.
  Future<(String?, String?)> create(String dir, String name,
      {bool folder = false}) async {
    try {
      final r = await _backend.call(
          'oge_olustur', {'dizin': dir, 'ad': name, 'klasor': folder});
      await reloadDir(dir);
      return (null, r['yol']?.toString());
    } on BackendException catch (e) {
      return (e.message, null);
    } catch (e) {
      return (e.toString(), null);
    }
  }

  /// Yeniden adlandırır; (hata, yeni_yol) döner.
  Future<(String?, String?)> rename(FileNode node, String newName) async {
    try {
      final r = await _backend
          .call('oge_yeniden_adlandir', {'yol': node.path, 'ad': newName});
      await reloadDir(p.dirname(node.path));
      return (null, r['yol']?.toString());
    } on BackendException catch (e) {
      return (e.message, null);
    } catch (e) {
      return (e.toString(), null);
    }
  }

  /// Geri Dönüşüm Kutusu'na taşır; hata metni ya da null döner.
  Future<String?> delete(FileNode node) async => (await sil(node)).hata;

  /// Siler. Sürücüde Geri Dönüşüm Kutusu yoksa (USB bellek, ağ sürücüsü)
  /// backend silmez, [kaliciGerekir] true ve [hata] içinde soruyu döndürür;
  /// kullanıcı onaylarsa [kalici] true ile yeniden çağrılır.
  Future<({String? hata, bool kaliciGerekir, bool kalici})> sil(FileNode node,
      {bool kalici = false}) async {
    try {
      final r = await _backend.call(
          'oge_sil', {'yol': node.path, if (kalici) 'kalici': true});
      await reloadDir(p.dirname(node.path));
      return (hata: null, kaliciGerekir: false, kalici: r['kalici'] == true);
    } on BackendException catch (e) {
      return (
        hata: e.message,
        kaliciGerekir: !kalici && e.data?['kalici_gerekir'] == true,
        kalici: false,
      );
    } catch (e) {
      return (hata: e.toString(), kaliciGerekir: false, kalici: false);
    }
  }
}

/// Bir sekmenin terminali: kendi çıktısı, komut geçmişi ve son hatası.
class TerminalOturumu {
  final StringBuffer cikti = StringBuffer();
  String? _ciktiOnbellek;
  String get metin => _ciktiOnbellek ??= cikti.toString();

  String? _satirlarKaynagi;
  List<String> _satirlar = const [];

  /// Terminale yazılan komut / girdi geçmişi (Yukarı / Aşağı ok ile gezilir).
  final List<String> gecmis = [];

  /// Son çalıştırmanın Türkçe hata bloğu ("[HATA]: ..." satırından itibaren)
  /// ve çalıştırılan kod; "Hatayı AI ile açıkla" düğmesi bunları kullanır.
  String? sonHata;
  String sonKod = '';

  List<String> get satirlar {
    final o = metin;
    if (!identical(o, _satirlarKaynagi)) {
      _satirlarKaynagi = o;
      _satirlar = o.isEmpty ? const [] : o.split('\n');
      // Sondaki "\n"in ürettiği boş satır gösterilmez.
      if (_satirlar.length > 1 && _satirlar.last.isEmpty) {
        _satirlar = _satirlar.sublist(0, _satirlar.length - 1);
      }
    }
    return _satirlar;
  }

  void temizle() {
    cikti.clear();
    _ciktiOnbellek = null;
  }

  void ekle(String s) {
    _ciktiOnbellek = null;
    cikti.write(s);
    // Sınır aşılınca sınırın 3/4'üne kırpılır. Eskiden tam sınıra
    // kırpıldığından, dolu terminalde HER çıktı parçası 200 bin karakterlik
    // tamponu baştan kopyalıyordu; döngüde yazdıran programlarda arayüz
    // iş parçacığı bununla meşgul olup IDE donuyordu.
    if (cikti.length > kMaxTermChars) {
      final s = cikti.toString();
      var bas = s.length - kMaxTermChars * 3 ~/ 4;
      final nl = s.indexOf('\n', bas);
      if (nl >= 0 && nl < s.length - 1) bas = nl + 1;
      final keep = s.substring(bas);
      cikti
        ..clear()
        ..write('[... kesildi ...]\n')
        ..write(keep);
    }
  }

  void sonHatayiBul() {
    final o = metin;
    final i = o.lastIndexOf('[HATA]:');
    if (i < 0) return;
    final son = o.indexOf('\n=====', i);
    sonHata = (son < 0 ? o.substring(i) : o.substring(i, son)).trim();
  }
}

/// Terminaller. Her editör sekmesinin kendi terminal oturumu vardır (Ayarlar
/// sekmesinin yoktur); görünen, etkin sekmenin oturumudur. Backend aynı anda
/// tek program çalıştırır: o programın çıktısı onu başlatan sekmenin
/// ("sahip") terminaline gider, başka bir sekmede yazılan komutlar ona girdi
/// olarak değil o sekmenin kabuk komutu olarak gider.
class TerminalProvider extends ChangeNotifier {
  /// Kullanıcının programı / hata ayıklamayı durdurduğu an: hemen ardından
  /// gelen sıfır olmayan çıkış kodu hata olarak yazılmaz.
  static DateTime? _durdurmaZamani;
  static void durdurmaIstendi() => _durdurmaZamani = DateTime.now();

  final BackendService _backend;
  late final StreamSubscription<BackendEvent> _sub;
  bool _running = false;
  Timer? _notifyTimer;
  // Yoğun çıktıda (ör. döngü içinde yazdır) her parça için ayrı rebuild
  // yapmak yerine bildirimler ~1 kareye (16 ms) toplanır.
  static const Duration _notifyDelay = Duration(milliseconds: 16);

  final Map<String, TerminalOturumu> _oturumlar = {};
  String _aktif = '';
  bool _ayarlarda = false;

  /// Çalışan programı (ya da TürKod Kabuğu'nu) başlatan sekmenin kimliği.
  String _sahip = '';

  TerminalOturumu _oturum(String id) =>
      _oturumlar.putIfAbsent(id, TerminalOturumu.new);
  TerminalOturumu get _etkin => _oturum(_aktif);

  /// Görünen terminalin (etkin sekmenin) kimliği.
  String get aktifOturum => _aktif;
  String get sahipOturum => _sahip;

  String get output => _etkin.metin;

  /// Çıktının satırları (terminal yalnızca görünen satırları çizer).
  List<String> get lines => _etkin.satirlar;
  List<String> get history => _etkin.gecmis;
  String? get sonHata => _etkin.sonHata;
  String get sonKod => _etkin.sonKod;

  /// Bu sekmenin terminalinde program çalışıyor.
  bool get isRunning => _running && _sahip == _aktif;

  /// Program başka bir sekmenin terminalinde çalışıyor.
  bool get programBaskaSekmede => _running && _sahip != _aktif;

  late final StreamSubscription<bool> _connSub;
  TerminalProvider(this._backend) {
    _sub = _backend.events.listen(_onEvent);
    // Backend bağlantısı koparsa (çökme, yeniden başlatma) çalışan program da
    // onunla birlikte kapanmıştır; "calistirma_bitti" hiç gelmeyeceğinden
    // terminal "çalışıyor" durumunda takılı kalmasın.
    _connSub = _backend.connectionStream.listen((bagli) {
      // Yeniden başlayan backend bildirilen boyutları bilmez.
      if (!bagli) _gonderilenBoyut.clear();
      if (bagli) unawaited(_boyutuGonder(_aktif));
      if (!bagli && _running) {
        _running = false;
        _oturum(_sahip)
            .ekle('\n[TürKod motoruyla bağlantı koptu; program sonlandırıldı]\n');
        notifyListeners();
      }
    });
  }

  /// Etkin sekmeyi izler: her sekmenin terminali ayrıdır, kapanan sekmenin
  /// terminali (ve çalışan programı) kapatılır.
  void sekmeleriIzle(EditorProvider ed, UiProvider ui) {
    void guncelle() {
      final t = ed.activeTab;
      final ayarlar = ozelSekmeMi(t?.path);
      final id = t?.id ?? '';
      ui.sekmeDegisti(id, ayarlar);
      final kimlikler = {for (final x in ed.tabs) x.id};
      for (final k in _oturumlar.keys
          .where((k) => k.isNotEmpty && !kimlikler.contains(k))
          .toList()) {
        _oturumuKapat(k);
      }
      ui.sekmeleriTemizle(kimlikler);
      if (id != _aktif || ayarlar != _ayarlarda) {
        _aktif = id;
        _ayarlarda = ayarlar;
        notifyListeners();
      }
    }

    ed.addListener(guncelle);
    guncelle();
  }

  void _oturumuKapat(String id) {
    _oturumlar.remove(id);
    if (_running && _sahip == id) {
      // Sekmesi kapanan programın çıktısını gösterecek yer kalmadı.
      _running = false;
      _backend
          .call('calistir_durdur', {'oturum': id})
          .catchError((_) => <String, dynamic>{});
    }
    _backend
        .call('calistir_durdur', {'oturum': id, 'yalnizca_kabuk': true})
        .catchError((_) => <String, dynamic>{});
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
      _oturum(_sahip).ekle(_filtrele(e.data['metin']?.toString() ?? ''));
      final boy = e.data['boy'];
      if (boy is num) _onaylanacak += boy.toInt();
      // Onay, çıktıyı üreten sürece gider (debug oturumu ya da yeni
      // çalıştırma eski bir pid'le onaylanıp kilitlenmesin).
      final pid = e.data['pid'];
      if (pid is num) _calisanPid = pid.toInt();
      _scheduleNotify();
    } else if (e.name == 'calistirma_bitti') {
      _running = false;
      _kabukModu = false;
      // Normal bitişte ek satır yazılmaz (bitiş, dönen göstergenin
      // kaybolmasından anlaşılır); yalnızca hatalı çıkış kodu bildirilir.
      final kod = e.data['cikis_kodu'];
      final kodSayi = kod is num ? kod.toInt() : int.tryParse('$kod');
      // Kullanıcı Durdur'a bastıysa çıkış kodu (taskkill: 1) hata gibi
      // gösterilmez; eskiden "[Durduruldu]" ardından "[Program 1 koduyla
      // sonlandı]" da yazıyordu.
      final durduruldu = _durdurmaZamani != null &&
          DateTime.now().difference(_durdurmaZamani!) < const Duration(seconds: 10);
      _durdurmaZamani = null;
      if (kodSayi != null && kodSayi != 0 && !durduruldu) {
        final o = _oturum(_sahip);
        o.sonHatayiBul();
        o.ekle('\n[Program $kodSayi koduyla sonlandı]\n');
      }
      notifyListeners();
    } else if (e.name == 'terminal_cikti') {
      // Kabuk komutunun çıktısı komutu yazan sekmenin terminaline gider.
      final oturum = e.data['oturum']?.toString() ?? _aktif;
      final o = _oturumlar[oturum];
      if (o == null) return; // sekme kapanmış
      o.ekle(e.data['metin']?.toString() ?? '');
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
    _onayiPlanla();
  }

  // --- Akış kontrolü (geri basınç) -----------------------------------
  // IDLE'da her print arayüze eşzamanlı bir çağrıdır; CMD'de WriteConsole
  // konsol yazıyı işleyene kadar döner: program arayüzden hızlı yazamaz.
  // Burada çıktı EKRANA ÇİZİLDİKTEN sonra (sonraki kare bitince) backend'e
  // onaylanır; backend onaylanmamış çıktı penceresi dolunca programın
  // çıktısını okumayı bırakır ve program yavaşlar. Eskiden çıktı sınırsız
  // hızla gelip arayüzü donduruyordu.
  int _onaylanacak = 0;
  int? _calisanPid;
  bool _onayPlanli = false;

  Timer? _onayYedek;

  void _onayGonder() {
    _onayPlanli = false;
    _onayYedek?.cancel();
    final miktar = _onaylanacak;
    if (miktar <= 0) return;
    _onaylanacak = 0;
    _backend
        .call('cikti_onay', {'pid': _calisanPid, 'miktar': miktar})
        .catchError((_) => <String, dynamic>{});
  }

  void _onayiPlanla() {
    if (_onayPlanli || _onaylanacak <= 0) return;
    _onayPlanli = true;
    WidgetsBinding.instance.addPostFrameCallback((_) => _onayGonder());
    WidgetsBinding.instance.scheduleFrame();
    // Pencere simge durumundayken kare çizilmez; program yine de (CMD'deki
    // gibi) çalışmaya devam etsin diye onay en geç 250 ms'de gönderilir.
    _onayYedek?.cancel();
    _onayYedek = Timer(const Duration(milliseconds: 250), _onayGonder);
  }

  /// Etkin sekme çalışan programın sahibi olur. Program başka bir sekmede
  /// çalışıyorsa backend onu durdurur; o sekmenin terminaline not düşülür.
  void _sahiplen() {
    if (_running && _sahip != _aktif) {
      _oturumlar[_sahip]?.ekle(
          '\n[Başka bir sekmede program başlatıldığı için bu program durduruldu]\n');
    }
    _sahip = _aktif;
  }

  /// [dosya]: sekmenin kayıtlı yolu (program o klasörde çalışır, yandaki
  /// .trpy dosyaları içe aktarılabilir); [args]: programın argümanları.
  Future<void> run(String kod, {String? dosya, String args = ''}) async {
    if (_ayarlarda) return;
    _sahiplen();
    _kabukModu = false;
    final o = _etkin
      ..temizle()
      ..sonHata = null
      ..sonKod = kod;
    _running = true;
    _onaylanacak = 0;
    _calisanPid = null;
    notifyListeners();
    try {
      final r = await _backend.call('calistir', {
        'kod': kod,
        if (dosya != null) 'dosya': dosya,
        if (args.trim().isNotEmpty) 'argumanlar': args,
        'akis_kontrolu': true,
      });
      // call() zaten yanıtın "result" kısmını döndürür.
      final pid = r['pid'];
      if (pid is num) _calisanPid = pid.toInt();
    } on BackendException catch (e) {
      _running = false;
      // Hazırlık sırasında Durdur'a basıldı: hata değil; "[Durduruldu]"
      // satırını stop() zaten yazar.
      if (e.data?['iptal'] != true) o.ekle('[Hata] ${e.message}\n');
    } catch (e) {
      _running = false;
      o.ekle('[Hata] $e\n');
    } finally {
      notifyListeners();
    }
  }

  /// Backend'de başka bir yoldan (ör. hata ayıklayıcı) başlatılan bir
  /// programın çıktısı için terminali hazırlar.
  void beginRun() {
    _sahiplen();
    _etkin
      ..temizle()
      ..sonHata = null;
    _running = true;
    notifyListeners();
  }

  /// TürKod Kabuğu'nu terminalde başlatır. Kabuk çalışan bir program gibi
  /// davranır: yazılanlar ona gider, Durdur / Ctrl+C kapatır.
  /// Terminalde TürKod Kabuğu çalışıyor.
  bool _kabukModu = false;

  Future<void> kabukBaslat() async {
    if (_ayarlarda) return;
    _sahiplen();
    _kabukModu = true;
    final o = _etkin
      ..temizle()
      ..sonHata = null
      ..sonKod = '';
    _running = true;
    _onaylanacak = 0;
    _calisanPid = null;
    notifyListeners();
    try {
      // Kabuk ve içinde çalışan komutlar terminalin boyutunu bilsin.
      final oturum = _aktif;
      _gonderilenBoyut.remove(oturum);
      await _boyutuGonder(oturum);
      final r = await _backend.call('kabuk_baslat', {'oturum': oturum});
      final pid = r['pid'];
      if (pid is num) _calisanPid = pid.toInt();
    } catch (e) {
      _running = false;
      o.ekle('[Hata] TürKod Kabuğu başlatılamadı: $e\n');
    } finally {
      notifyListeners();
    }
  }

  /// [beginRun] sonrası program hiç başlatılamadıysa.
  void endRun([String? message]) {
    _running = false;
    if (message != null) _oturum(_sahip).ekle('$message\n');
    notifyListeners();
  }

  /// Bu sekmenin programını ya da (program yoksa / başka sekmedeyse) bu
  /// sekmenin terminalinde süren kabuk komutlarını durdurur.
  Future<void> stop() async {
    final o = _etkin;
    durdurmaIstendi();
    try {
      await _backend.call('calistir_durdur', {
        'oturum': _aktif,
        if (programBaskaSekmede) 'yalnizca_kabuk': true,
      });
      o.ekle('[Durduruldu]\n');
    } catch (_) {
      // Backend'e ulaşılamıyorsa program da onunla birlikte kapanmıştır.
      if (!_backend.isConnected) _running = false;
    }
    notifyListeners();
  }

  // ------------------------------------------------------- terminal boyutu
  // Terminalin görünen boyutu (karakter hücresi olarak). Backend bunu
  // terminalde başlatılan süreçlere COLUMNS / LINES olarak verir; böylece
  // ör. "turkod logo" IDE terminalini tam doldurur. Boru üzerinden çalışan
  // süreç terminal boyutunu kendisi öğrenemez.
  (int, int)? _boyut;
  final Map<String, (int, int)> _gonderilenBoyut = {};

  /// Terminal görünümünün boyutu [sutun] x [satir] karakter oldu (panel
  /// gecikmeli çağırır). Görünen oturuma hemen bildirilir.
  void boyutBildir(int sutun, int satir) {
    if (sutun < 10 || satir < 3) return; // backend sınırlarının altı
    _boyut = (sutun.clamp(10, 1000).toInt(), satir.clamp(3, 500).toInt());
    unawaited(_boyutuGonder(_aktif));
  }

  /// [oturum] için son gönderilen boyut farklıysa backend'e bildirir.
  Future<void> _boyutuGonder(String oturum) async {
    final b = _boyut;
    if (b == null || _gonderilenBoyut[oturum] == b) return;
    if (!_backend.isConnected) return;
    try {
      await _backend.call('terminal_boyutu',
          {'oturum': oturum, 'sutun': b.$1, 'satir': b.$2}).timeout(
          const Duration(seconds: 2));
      _gonderilenBoyut[oturum] = b;
    } catch (_) {}
  }

  static const int _maxHistory = 100;

  void _addHistory(String cmd) {
    final h = _etkin.gecmis;
    if (cmd.trim().isEmpty) return;
    if (h.isNotEmpty && h.last == cmd) return;
    h.add(cmd);
    if (h.length > _maxHistory) h.removeAt(0);
  }

  Future<void> sendCommand(String cmd) async {
    if (_ayarlarda) return;
    final programa = isRunning;
    // Program çalışırken boş satır geçerli bir girdidir; kabuk komutu boş
    // olamaz.
    if (!programa && cmd.trim().isEmpty) return;
    _addHistory(cmd);
    final o = _etkin;
    // Çalışan programa girdi gönderiliyorsa konsoldaki gibi yalnızca yazılan
    // metin görünür; kabuk komutunda "> komut" biçiminde yazılır. TürKod
    // Kabuğu boş satırı sessizce yok sayar; yankılanırsa boş satır kalıyordu.
    if (!(_kabukModu && programa && cmd.trim().isEmpty)) {
      o.ekle(programa ? '$cmd\n' : '> $cmd\n');
    }
    notifyListeners();
    final oturum = _aktif;
    try {
      // Boyut değiştiyse komuttan önce bildirilir (yalnızca kabuk komutu
      // yeni süreç başlatır; çalışan programa giden girdi için gerekmez).
      if (!programa) await _boyutuGonder(oturum);
      await _backend.call('terminal_komut', {
        'komut': cmd,
        'oturum': oturum,
        // Program başka bir sekmenin terminalinde çalışıyor: komut ona
        // girdi olarak gitmesin, bu terminalde çalışsın.
        if (!programa) 'programa': false,
      });
    } catch (e) {
      o.ekle('[Hata] $e\n');
    }
    notifyListeners();
  }

  void clear() {
    _etkin.temizle();
    notifyListeners();
  }

  @override
  void dispose() {
    _notifyTimer?.cancel();
    _onayYedek?.cancel();
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

  static String _kaynak(Map<String, dynamic> r) {
    final s = r['kaynak_saglayici']?.toString() ?? '';
    final m = r['kaynak_model']?.toString() ?? '';
    return [s, m].where((e) => e.isNotEmpty).join(' • ');
  }

  /// Son başarısız isteği yeniden göndermek için.
  Future<void> Function()? _sonIstek;

  /// Kullanıcı balonunu ekler, isteği gönderir, yanıtı (ya da hatayı) ekler.
  /// Eskiden Açıkla / Optimize isteklerinde kullanıcı balonu eklenmiyor,
  /// sohbette yanıtın neye ait olduğu anlaşılmıyordu.
  Future<void> _gonder(String? kullaniciMetni, String komut,
      Map<String, dynamic> params) async {
    if (_loading) return;
    if (kullaniciMetni != null) {
      _messages.add(AiMessage(
          role: AiRole.user,
          parts: [AiPart(type: 'metin', content: kullaniciMetni)]));
    }
    _loading = true;
    notifyListeners();
    _sonIstek = null;
    try {
      final r = await _backend.call(komut, params);
      _messages.add(AiMessage(
          role: AiRole.assistant,
          parts: _parseParts(r),
          kaynak: _kaynak(r),
          dusunce: r['dusunce']?.toString() ?? ''));
    } catch (e) {
      _sonIstek = () => _gonder(null, komut, params);
      _messages.add(AiMessage(
          role: AiRole.assistant,
          hata: true,
          parts: [AiPart(type: 'metin', content: '⚠️ $e')]));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  bool get yenidenDenenebilir => _sonIstek != null && !_loading;

  Future<void> yenidenDene() async {
    final istek = _sonIstek;
    if (istek == null || _loading) return;
    // Hata balonu kaldırılır; istek aynı parametrelerle tekrarlanır.
    if (_messages.isNotEmpty && _messages.last.hata) _messages.removeLast();
    await istek();
  }

  Future<void> ask(String msg, {String? kod}) async {
    if (msg.trim().isEmpty) return;
    await _gonder(msg, 'ai_sor', {'mesaj': msg, if (kod != null) 'kod': kod});
  }

  Future<void> explain(String kod) async {
    if (kod.trim().isEmpty) return;
    await _gonder('Bu kodu açıklar mısın?', 'ai_kodu_acikla', {'kod': kod});
  }

  /// Terminaldeki son çalışma hatasını yapay zekâya açıklatır.
  Future<void> explainError(String kod, String hata) async {
    if (hata.trim().isEmpty) return;
    await _gonder('Bu hatayı açıklar mısın?\n```\n$hata\n```', 'ai_hata_acikla',
        {'kod': kod, 'hata': hata});
  }

  Future<void> optimize(String kod) async {
    if (kod.trim().isEmpty) return;
    await _gonder('Bu kodu optimize eder misin?', 'ai_kodu_optimize', {'kod': kod});
  }

  Future<void> clear() async {
    try {
      await _backend.call('ai_temizle');
    } catch (_) {}
    _messages.clear();
    _sonIstek = null;
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
  final int index;
  const DebugFrame(this.function, this.line, [this.index = 0]);
}

/// İzleme ifadesi ve son değerlendirme sonucu.
class DebugWatch {
  final String expr;
  final String? value;
  final String? error;
  const DebugWatch(this.expr, {this.value, this.error});
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

  /// Sekme başına koşullu breakpoint'ler: {satır: TürKod koşulu}.
  final Map<String, Map<int, String>> _conds = {};

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

  /// Programı durduran yakalanmamış hata (stopReason == 'hata' iken).
  String? stopError;

  /// Değişkenleri gösterilen çağrı yığını çerçevesi (0 = en içteki).
  int selectedFrame = 0;

  /// İzleme ifadeleri (oturumlar arasında korunur) ve son değerleri.
  final List<String> _watchExprs = [];
  List<DebugWatch> watches = const [];

  late final StreamSubscription<bool> _connSub;

  BreakpointProvider(this._backend, [this._editor]) {
    _sub = _backend.events.listen(_onEvent);
    _editor?.onContentEdited = adjustForEdit;
    // Oturumdan geri yüklenen breakpoint'ler.
    _editor?.sessionExtras = _sessionExtras;
    _editor?.restoreExtras = _restoreExtras;
    _editor?.takePendingExtras().forEach(_restoreExtras);
    // Backend bağlantısı koparsa oturum da bitmiştir (süreç backend'in
    // alt sürecidir); arayüz "hata ayıklanıyor" durumunda takılı kalmasın.
    _connSub = _backend.connectionStream.listen((bagli) {
      if (!bagli && _debugging) {
        _endSession();
        notice = 'TürKod motoruyla bağlantı koptu; hata ayıklama sonlandırıldı.';
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

  /// Yerel bir .trpy modülünde durulduysa o dosyanın yolu (ana dosyadaysa
  /// null). Backend 'dosya' alanını yalnızca modüldeyken gönderir.
  String? _pausedFile;

  /// Bu sekmede şu an durulan satır (yoksa null).
  int? pausedLineFor(String? tabId) {
    if (!paused || tabId == null || _currentLine <= 0) return null;
    final dosya = _pausedFile;
    if (dosya == null) return tabId == _debugTabId ? _currentLine : null;
    // Modüldeki satır ana dosyada değil, modülün sekmesinde vurgulanır.
    final t = _editor?.tabs.where((t) => t.id == tabId).firstOrNull;
    return t != null && p.equals(t.path, dosya) ? _currentLine : null;
  }

  void clearNotice() {
    if (notice != null) {
      notice = null;
      notifyListeners();
    }
  }

  // ----------------------------------------------------------------- oturum kaydı
  Map<String, dynamic> _sessionExtras(String tabId) {
    final set = _bps[tabId];
    if (set == null || set.isEmpty) return const {};
    final conds = _conds[tabId] ?? const <int, String>{};
    return {
      'breakpointler': set.toList()..sort(),
      if (conds.isNotEmpty)
        'kosullar': {for (final e in conds.entries) '${e.key}': e.value},
    };
  }

  void _restoreExtras(String tabId, Map<String, dynamic> m) {
    final l = m['breakpointler'];
    if (l is! List || l.isEmpty) return;
    final set = _bps.putIfAbsent(tabId, () => <int>{});
    for (final x in l) {
      final n = x is num ? x.toInt() : int.tryParse('$x');
      if (n != null && n > 0) set.add(n);
    }
    final k = m['kosullar'];
    if (k is Map) {
      final conds = _conds.putIfAbsent(tabId, () => <int, String>{});
      k.forEach((key, v) {
        final n = int.tryParse('$key');
        if (n != null && set.contains(n) && '$v'.trim().isNotEmpty) {
          conds[n] = '$v'.trim();
        }
      });
    }
    notifyListeners();
  }

  // ---------------------------------------------------------------- breakpoint
  void toggle(String? tabId, int line) {
    if (tabId == null || line < 1) return;
    final set = _bps.putIfAbsent(tabId, () => <int>{});
    if (!set.remove(line)) {
      set.add(line);
    } else {
      _conds[tabId]?.remove(line);
    }
    _syncSession(tabId);
    notifyListeners();
  }

  /// Satırın koşulu (koşulsuz breakpoint ya da breakpoint yoksa null).
  String? conditionFor(String? tabId, int line) =>
      tabId == null ? null : _conds[tabId]?[line];

  Map<int, String> conditionsFor(String? tabId) =>
      tabId == null ? const {} : Map.unmodifiable(_conds[tabId] ?? const {});

  /// Koşullu breakpoint koyar / koşulu değiştirir. Boş koşul, breakpoint'i
  /// koşulsuz bırakır.
  void setCondition(String? tabId, int line, String condition) {
    if (tabId == null || line < 1) return;
    _bps.putIfAbsent(tabId, () => <int>{}).add(line);
    final c = condition.trim();
    final conds = _conds.putIfAbsent(tabId, () => <int, String>{});
    if (c.isEmpty) {
      conds.remove(line);
    } else {
      conds[line] = c;
    }
    _syncSession(tabId);
    notifyListeners();
  }

  void clearAll([String? tabId]) {
    if (tabId == null) {
      _bps.clear();
      _conds.clear();
    } else {
      _bps.remove(tabId);
      _conds.remove(tabId);
    }
    if (_debugTabId != null) _syncSession(_debugTabId!);
    notifyListeners();
  }

  void forgetTab(String tabId) {
    _bps.remove(tabId);
    _conds.remove(tabId);
  }

  /// Koşul kaydı "#N#ifade" biçiminde isabet sayısı da taşıyabilir
  /// (N. geçişte dur). İfade boş olabilir.
  static final RegExp _isabetDeseni = RegExp(r'^#(\d+)#');

  static (int?, String) kosulAyristir(String? kayit) {
    final k = kayit ?? '';
    final m = _isabetDeseni.firstMatch(k);
    if (m == null) return (null, k);
    return (int.tryParse(m.group(1)!), k.substring(m.end));
  }

  static String kosulBirlestir(int? isabet, String ifade) =>
      isabet != null && isabet > 1 ? '#$isabet#${ifade.trim()}' : ifade.trim();

  Map<String, String> _condPayload(String tabId) {
    final set = _bps[tabId] ?? const <int>{};
    return {
      for (final e in (_conds[tabId] ?? const <int, String>{}).entries)
        if (set.contains(e.key) && kosulAyristir(e.value).$2.isNotEmpty)
          '${e.key}': kosulAyristir(e.value).$2,
    };
  }

  Map<String, int> _hitPayload(String tabId) {
    final set = _bps[tabId] ?? const <int>{};
    return {
      for (final e in (_conds[tabId] ?? const <int, String>{}).entries)
        if (set.contains(e.key) && kosulAyristir(e.value).$1 != null)
          '${e.key}': kosulAyristir(e.value).$1!,
    };
  }

  /// Çalışan oturum bu sekmeye aitse breakpoint değişikliğini hemen iletir
  /// (program yeniden başlatılmadan breakpoint eklenip kaldırılabilir).
  void _syncSession(String tabId) {
    if (!_debugging || tabId != _debugTabId) return;
    final gecici = _geciciSatir;
    final lines = {...?_bps[tabId], if (gecici != null) gecici}.toList()
      ..sort();
    _backend.call('debug_breakpoint_ayarla', {
      'satirlar': lines,
      'kosullar': _condPayload(tabId),
      'isabetler': _hitPayload(tabId),
    }).catchError((_) => <String, dynamic>{});
  }

  // ----------------------------------------------------------------- izleme
  List<String> get watchExpressions => List.unmodifiable(_watchExprs);

  void addWatch(String expr) {
    final e = expr.trim();
    if (e.isEmpty || _watchExprs.contains(e)) return;
    _watchExprs.add(e);
    watches = [...watches, DebugWatch(e)];
    _syncWatches();
    notifyListeners();
  }

  void removeWatch(String expr) {
    if (!_watchExprs.remove(expr)) return;
    watches = watches.where((w) => w.expr != expr).toList();
    _syncWatches();
    notifyListeners();
  }

  void _syncWatches() {
    if (!_debugging) return;
    _backend
        .call('debug_izle', {'ifadeler': _watchExprs})
        .catchError((_) => <String, dynamic>{});
  }

  void _applyWatchResults(Object? raw) {
    if (raw is! List) return;
    final sonuc = <String, DebugWatch>{};
    for (final e in raw) {
      if (e is! Map) continue;
      final expr = e['ifade']?.toString() ?? '';
      sonuc[expr] = DebugWatch(expr,
          value: e['deger']?.toString(), error: e['hata']?.toString());
    }
    watches = [for (final x in _watchExprs) sonuc[x] ?? DebugWatch(x)];
  }

  /// Duraklamış programda bir TürKod ifadesini seçili çerçevede
  /// değerlendirir; (değer, hata) döner.
  Future<(String?, String?)> evaluate(String expr) async {
    if (!paused) return (null, 'Program duraklatılmış değil.');
    try {
      final r = await _backend.call(
          'debug_degerlendir', {'ifade': expr, 'cerceve': selectedFrame});
      return (r['deger']?.toString(), null);
    } on BackendException catch (e) {
      return (null, e.message);
    } catch (e) {
      return (null, e.toString());
    }
  }

  /// Çağrı yığınından bir çerçeve seçer; değişkenler o çerçeveninkiyle
  /// değişir ve editör o satıra gider.
  /// Duraklamış programda [name] değişkenine yeni değer verir ([expr] bir
  /// TürKod ifadesidir); başarıda değişken listesi yenilenir. Hata metni ya
  /// da null döner.
  Future<String?> setVariable(String name, String expr) async {
    if (!paused) return 'Program duraklatılmış değil.';
    try {
      await _backend.call('debug_degisken_ata',
          {'ad': name, 'ifade': expr, 'cerceve': selectedFrame});
    } on BackendException catch (e) {
      return e.message;
    } catch (e) {
      return e.toString();
    }
    final indeks = selectedFrame < stack.length ? stack[selectedFrame].index : 0;
    try {
      await _backend.call('debug_cerceve', {'indeks': indeks});
    } catch (_) {}
    return null;
  }

  Future<void> selectFrame(int index) async {
    if (!paused || index < 0 || index >= stack.length) return;
    selectedFrame = index;
    notifyListeners();
    final line = stack[index].line;
    final ed = _editor;
    if (ed != null && ed.activeTab?.id == _debugTabId) {
      ed.revealModelLine?.call(line);
    }
    try {
      await _backend.call('debug_cerceve', {'indeks': stack[index].index});
    } catch (_) {}
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
    final conds = _conds[tabId];
    final newConds = <int, String>{};
    for (final b in set) {
      int? hedef;
      if (b < startLine || (b == startLine && !atLineStart)) {
        hedef = b;
      } else if (delta < 0 && b > startLine && b <= oldEndLine) {
        // Silinen satırlardaki breakpoint, birleşilen satıra taşınır.
        hedef = startLine;
      } else {
        final n = b + delta;
        if (n >= 1 && n <= newLines + 1) hedef = n;
      }
      if (hedef == null) continue;
      updated.add(hedef);
      final c = conds?[b];
      if (c != null) newConds.putIfAbsent(hedef, () => c);
    }
    set
      ..clear()
      ..addAll(updated);
    if (conds != null) {
      conds
        ..clear()
        ..addAll(newConds);
    }
    _syncSession(tabId);
    notifyListeners();
  }

  // ----------------------------------------------------------------- oturum
  void _onEvent(BackendEvent e) {
    switch (e.name) {
      case 'debug_durdu':
        if (!_debugging) return;
        _paused = true;
        if (_geciciSatir != null) {
          _geciciSatir = null;
          final tabId = _debugTabId;
          if (tabId != null) _syncSession(tabId);
        }
        _currentLine = (e.data['satir'] as num?)?.toInt() ?? 0;
        final dosya = e.data['dosya']?.toString();
        _pausedFile = dosya == null || dosya.isEmpty ? null : dosya;
        stopReason = e.data['neden']?.toString() ?? '';
        currentFunction = e.data['fonksiyon']?.toString() ?? '';
        locals = DebugVar.listFrom(e.data['yerel']);
        globals = DebugVar.listFrom(e.data['kuresel']);
        stopError = stopReason == 'hata' ? e.data['hata']?.toString() : null;
        selectedFrame = 0;
        final yigin = e.data['yigin'] as List? ?? const [];
        stack = [
          for (var i = 0; i < yigin.length; i++)
            if (yigin[i] is Map)
              DebugFrame(
                  (yigin[i] as Map)['fonksiyon']?.toString() ?? '?',
                  ((yigin[i] as Map)['satir'] as num?)?.toInt() ?? 0,
                  ((yigin[i] as Map)['indeks'] as num?)?.toInt() ?? i),
        ];
        _applyWatchResults(e.data['izlenenler']);
        _revealCurrentLine();
        notifyListeners();
        break;
      case 'debug_izlenenler':
        if (!_debugging) return;
        _applyWatchResults(e.data['izlenenler']);
        notifyListeners();
        break;
      case 'debug_cerceve':
        if (!paused) return;
        locals = DebugVar.listFrom(e.data['yerel']);
        globals = DebugVar.listFrom(e.data['kuresel']);
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

  /// "İmlece Kadar Çalıştır" için geçici durma satırı: ilk duruşta kalkar.
  int? _geciciSatir;

  /// Duraklatılmışken programı [line] satırına kadar çalıştırır.
  Future<void> runToLine(int line) async {
    if (!_debugging || !_paused) return;
    _geciciSatir = line;
    final tabId = _debugTabId;
    if (tabId != null) _syncSession(tabId);
    await continueRun();
  }

  void _endSession() {
    _geciciSatir = null;
    _debugging = false;
    _paused = false;
    _currentLine = 0;
    _pausedFile = null;
    stopReason = '';
    stopError = null;
    selectedFrame = 0;
    currentFunction = '';
    locals = const [];
    globals = const [];
    stack = const [];
    watches = [for (final x in _watchExprs) DebugWatch(x)];
  }

  /// Durulan satırı editörde gösterir; gerekirse hata ayıklanan sekmeye geçer.
  void _revealCurrentLine() {
    final ed = _editor;
    if (ed == null || _currentLine < 1) return;
    final dosya = _pausedFile;
    if (dosya != null) {
      // İçine girilen yerel modül: dosyası açılır (açıksa o sekmeye geçilir)
      // ve satıra gidilir; eskiden modülün satırı ana dosyada vurgulanıyordu.
      final line = _currentLine;
      ed.openFile(dosya).then((_) {
        WidgetsBinding.instance.addPostFrameCallback((_) =>
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (!p.equals(ed.activeTab?.path ?? '', dosya)) return;
              final reveal = ed.revealModelLine;
              if (reveal != null) {
                reveal(line);
              } else if (ed.uiController != null) {
                jumpToLineIn(ed.uiController!, line);
              }
            }));
        WidgetsBinding.instance.ensureVisualUpdate();
        notifyListeners();
      }).catchError((_) {});
      return;
    }
    final tabId = _debugTabId;
    if (tabId == null) return;
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
    String? dosya,
    String args = '',
    int? geciciSatir,
  }) async {
    if (tabId == null) return;
    if (kod.trim().isEmpty) {
      notice = 'Kod boş';
      notifyListeners();
      return;
    }
    if (_starting) return;
    _starting = true;
    _baslarkenDurduruldu = false;
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
      _geciciSatir = geciciSatir;
      if (geciciSatir != null && !lines.contains(geciciSatir)) {
        lines
          ..add(geciciSatir)
          ..sort();
      }
      final r = await _backend.call('debug_baslat', {
        'kod': kod,
        'breakpointler': lines,
        'ilk_satirda_dur': stepIn,
        'kosullar': _condPayload(tabId),
        'isabetler': _hitPayload(tabId),
        'izlenenler': _watchExprs,
        if (dosya != null) 'dosya': dosya,
        if (args.trim().isNotEmpty) 'argumanlar': args,
        'akis_kontrolu': true,
      });
      _sessionId = r['oturum']?.toString();
      if (_baslarkenDurduruldu) {
        // Hazırlanırken Durdur'a basıldı ama backend yine de oturumu
        // başlattı: arayüz "çalışıyor" görünmesin, süreç de kalmasın.
        _endSession();
        notice = 'Hata ayıklama başlamadan durduruldu.';
        try {
          await _backend.call('debug_durdur');
        } catch (_) {}
        return;
      }
      notice = r['ilk_satirda_dur'] == true && lines.isEmpty
          ? 'Kesme noktası yok: program ilk satırda duraklatıldı (F10 ile adım atın).'
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
      notice = e.data?['iptal'] == true
          ? 'Hata ayıklama başlamadan durduruldu.'
          : e.message;
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

  /// Oturum hazırlanırken (debug_baslat yanıtı gelmeden) Durdur'a basıldı.
  bool _baslarkenDurduruldu = false;

  Future<void> stop() async {
    if (!_debugging) return;
    TerminalProvider.durdurmaIstendi();
    if (_starting) _baslarkenDurduruldu = true;
    // Arayüz hemen "durdu" durumuna geçer; yanıt beklenirken gelen
    // "debug_durdu" olayı hayalet bir "duraklatıldı" oturumu açmasın.
    _endSession();
    notifyListeners();
    var iptal = false;
    try {
      final r = await _backend.call('debug_durdur');
      // Backend henüz hazırlanan bir oturumu iptal etti.
      iptal = r['iptal'] == true;
    } catch (_) {}
    _endSession();
    notice = iptal || _baslarkenDurduruldu
        ? 'Hata ayıklama başlamadan durduruldu.'
        : 'Hata ayıklama durduruldu.';
    notifyListeners();
  }

  @override
  void dispose() {
    _sub.cancel();
    _connSub.cancel();
    if (_editor?.onContentEdited == adjustForEdit) {
      _editor?.onContentEdited = null;
    }
    if (_editor?.sessionExtras == _sessionExtras) {
      _editor?.sessionExtras = null;
      _editor?.restoreExtras = null;
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

  /// Bu eylemi sağlayan eklenti; kurulu değilse menüde ve komut paletinde
  /// gösterilmez (kısayolu yine çalışır ve kurulmasını önerir).
  final String? eklenti;
  const AppAction({
    required this.id,
    required this.label,
    this.menu,
    this.shortcut = '',
    this.activator,
    this.icon,
    required this.run,
    this.eklenti,
  });

  bool gorunur(BuildContext context) =>
      eklenti == null || context.read<SettingsProvider>().eklentiYuklu(eklenti!);
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
  final ed = context.read<EditorProvider>();
  final k = ed.activeContent.value;
  if (k.isEmpty) {
    showAppSnackbar(context, 'Kod boş', kind: SnackKind.error);
    return;
  }
  final tab = ed.activeTab;
  // Terminali açar ve klavye odağını komut satırına taşır; böylece program
  // girdi beklediğinde kullanıcı doğrudan yazabilir.
  context.read<UiProvider>().focusTerminal();
  context
      .read<TerminalProvider>()
      .run(k, dosya: tab?.filePath, args: tab?.runArgs ?? '');
}

/// Aktif sekmenin program argümanlarını sorar.
Future<void> _runArgsDialog(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final tab = ed.activeTab;
  if (tab == null || ozelSekmeMi(tab.path) || tab.isPdf) {
    showAppSnackbar(context, 'Bir kod sekmesi aç', kind: SnackKind.error);
    return;
  }
  final sonuc = await showDialog<String>(
    context: context,
    builder: (_) => DenetleyiciliDialog(
      metin: tab.runArgs,
      builder: (dc, ctrl) => AlertDialog(
        title: const Text('Çalıştırma Argümanları'),
        content: SizedBox(
          width: 460,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('"${tab.name}" çalıştırılırken programa verilecek argümanlar '
                  '(sys.argv). Boşlukla ayırın; boşluk içeren argümanı tırnak '
                  'içine alın.'),
              const SizedBox(height: 10),
              TextField(
                controller: ctrl,
                autofocus: true,
                style: const TextStyle(fontFamily: kMonoFontFamily),
                decoration: const InputDecoration(
                  hintText: 'ör. veri.txt --ayrintili "iki kelime"',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                onSubmitted: (v) => Navigator.pop(dc, v),
              ),
              const SizedBox(height: 10),
              Text(
                tab.filePath == null
                    ? 'Not: Sekme kaydedilmediği için program geçici bir '
                        'klasörde çalışır. Kaydettikten sonra dosyanın klasöründe '
                        'çalışır ve yanındaki .trpy dosyalarını içe aktarabilir.'
                    : 'Program "${p.dirname(tab.filePath!)}" klasöründe çalışır.',
                style: Theme.of(dc).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc), child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, ctrl.text),
              child: const Text('Kaydet')),
        ],
      ),
    ),
  );
  if (sonuc != null) ed.setRunArgs(tab.id, sonuc);
}

/// Satıra koşullu breakpoint koyar / koşulunu düzenler.
Future<void> showBreakpointConditionDialog(
    BuildContext context, String? tabId, int line) async {
  if (tabId == null || line < 1) return;
  final bp = context.read<BreakpointProvider>();
  final varMi = bp.breakpointsFor(tabId).contains(line);
  final sonuc = await showDialog<String>(
    context: context,
    builder: (_) => _KosulluBreakpointDialog(
        line: line,
        baslangic: bp.conditionFor(tabId, line) ?? '',
        varMi: varMi),
  );
  if (sonuc == null) return;
  if (sonuc == '\u0000sil') {
    if (bp.breakpointsFor(tabId).contains(line)) bp.toggle(tabId, line);
    return;
  }
  bp.setCondition(tabId, line, sonuc);
}

/// Koşullu breakpoint penceresi. Controller'ı pencerenin kendisi tutar ve
/// kendi dispose()'unda bırakır: showDialog döner dönmez dispose etmek,
/// Esc ile kapanırken kapanış animasyonu sürerken hâlâ ekranda olan
/// TextField'ı bozuk bırakıyor ve "_dependents.isEmpty" hatası veriyordu.
class _KosulluBreakpointDialog extends StatefulWidget {
  const _KosulluBreakpointDialog(
      {required this.line, required this.baslangic, required this.varMi});
  final int line;
  final String baslangic;
  final bool varMi;

  @override
  State<_KosulluBreakpointDialog> createState() =>
      _KosulluBreakpointDialogState();
}

class _KosulluBreakpointDialogState extends State<_KosulluBreakpointDialog> {
  late final (int?, String) _ilk =
      BreakpointProvider.kosulAyristir(widget.baslangic);
  late final TextEditingController ctrl = TextEditingController(text: _ilk.$2);
  late final TextEditingController isabetCtrl =
      TextEditingController(text: _ilk.$1?.toString() ?? '');

  String _sonuc() => BreakpointProvider.kosulBirlestir(
      int.tryParse(isabetCtrl.text.trim()), ctrl.text);

  @override
  void dispose() {
    ctrl.dispose();
    isabetCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext dc) {
    final line = widget.line;
    final varMi = widget.varMi;
    return AlertDialog(
      title: Text('Satır $line: Koşullu Kesme Noktası'),
      content: SizedBox(
        width: 440,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Program bu satırda yalnızca koşul doğruysa durur. '
                'Boş bırakırsan her seferinde durur.'),
            const SizedBox(height: 10),
            TextField(
              controller: ctrl,
              autofocus: true,
              style: const TextStyle(fontFamily: kMonoFontFamily),
              decoration: const InputDecoration(
                hintText: 'ör. i == 5   ya da   uzunluk(liste) > 3',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              onSubmitted: (_) => Navigator.pop(dc, _sonuc()),
            ),
            const SizedBox(height: 12),
            const Text('Kaçıncı geçişte durulsun? (boş = her geçişte; koşul '
                'varsa koşulun doğru olduğu geçişler sayılır)'),
            const SizedBox(height: 6),
            SizedBox(
              width: 140,
              child: TextField(
                controller: isabetCtrl,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(
                  hintText: 'ör. 5',
                  suffixText: '. geçiş',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                onSubmitted: (_) => Navigator.pop(dc, _sonuc()),
              ),
            ),
          ],
        ),
      ),
      actions: [
        if (varMi)
          TextButton(
              onPressed: () => Navigator.pop(dc, '\u0000sil'),
              child: const Text('Kesme Noktasını Kaldır')),
        TextButton(
            onPressed: () => Navigator.pop(dc), child: const Text('Vazgeç')),
        FilledButton(
            onPressed: () => Navigator.pop(dc, _sonuc()),
            child: const Text('Tamam')),
      ],
    );
  }
}

/// Son açılan dosyalar listesi.
Future<void> _recentFilesDialog(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final secilen = await showDialog<String>(
    context: context,
    builder: (dc) => AlertDialog(
      title: const Text('Son Dosyalar'),
      content: SizedBox(
        width: 520,
        height: 360,
        child: ed.recentFiles.isEmpty
            ? const Center(child: Text('Henüz dosya açılmadı.'))
            : ListView(
                children: [
                  for (final f in ed.recentFiles)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.description_outlined, size: 18),
                      title: Text(p.basename(f)),
                      subtitle: Text(p.dirname(f),
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                      onTap: () => Navigator.pop(dc, f),
                    ),
                ],
              ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(dc), child: const Text('Kapat')),
      ],
    ),
  );
  if (secilen == null || !context.mounted) return;
  try {
    await ed.openFile(secilen, context: context);
  } catch (e) {
    ed.forgetRecent(secilen);
    if (context.mounted) {
      showAppSnackbar(context, 'Dosya açılamadı: $e', kind: SnackKind.error);
    }
  }
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
  if (!context.mounted) return;

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
  // Sonuç, düzeltmenin BAŞLADIĞI sekmeye uygulanır (araya sekme değişimi
  // girerse eskiden o an aktif olan başka bir dosyanın üzerine yazılıyordu).
  final kaynakSekme = ed.activeTab?.id;
  if (kod.isEmpty || kaynakSekme == null) {
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
      fix.clearPending();
      if (ed.replaceContentOf(kaynakSekme, result.code)) {
        showAppSnackbar(context, 'Düzeltmeler uygulandı',
            kind: SnackKind.success);
      } else {
        // Kaynak sekme bu arada kapatıldı: sonuç kaybolmasın.
        ed.createUntitled(
          name: 'duzeltilmis.trpy',
          content: result.code,
          dirty: true,
          context: context,
        );
        showAppSnackbar(context, 'Kaynak sekme kapalı; sonuç yeni sekmede açıldı',
            kind: SnackKind.success);
      }
    } else if (choice == 'tab') {
      ed.createUntitled(
        name: 'duzeltilmis.trpy',
        content: result.code,
        dirty: true,
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
    if (!context.mounted) return;
    ed.createUntitled(
      name: 'cevrilmis${r['uzanti'] ?? '.trpy'}',
      content: r['sonuc']?.toString() ?? '',
      dirty: true,
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
void _debugStart(BuildContext context, {bool stepIn = false, int? geciciSatir}) {
  final ed = context.read<EditorProvider>();
  final tab = ed.activeTab;
  if (tab == null || ozelSekmeMi(tab.path) || tab.isPdf) {
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
    await bp.start(
        tabId: tab.id,
        kod: kod,
        stepIn: stepIn,
        dosya: tab.filePath,
        args: tab.runArgs,
        geciciSatir: geciciSatir);
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

/// Kullanıcının değiştirdiği kısayollar: {eylem kimliği: "Ctrl+Shift+K"};
/// boş metin kısayolu kaldırır. Ayar ('kisayollar') yüklenince doldurulur.
class OzelKisayollar {
  static Map<String, String> tablo = const {};
  static int surum = 0;

  static void ayarla(Object? ham) {
    final yeni = <String, String>{
      if (ham is Map)
        for (final e in ham.entries) '${e.key}': '${e.value ?? ''}',
    };
    if (mapEquals(yeni, tablo)) return;
    tablo = yeni;
    surum++;
  }

  static const Map<String, LogicalKeyboardKey> _ozelTuslar = {
    'Up': LogicalKeyboardKey.arrowUp,
    'Down': LogicalKeyboardKey.arrowDown,
    'Left': LogicalKeyboardKey.arrowLeft,
    'Right': LogicalKeyboardKey.arrowRight,
    'PageUp': LogicalKeyboardKey.pageUp,
    'PageDown': LogicalKeyboardKey.pageDown,
    'Enter': LogicalKeyboardKey.enter,
    'Space': LogicalKeyboardKey.space,
    'Tab': LogicalKeyboardKey.tab,
    'Delete': LogicalKeyboardKey.delete,
    'Home': LogicalKeyboardKey.home,
    'End': LogicalKeyboardKey.end,
    '/': LogicalKeyboardKey.slash,
  };

  static String tusAdi(LogicalKeyboardKey k) {
    for (final e in _ozelTuslar.entries) {
      if (e.value == k) return e.key;
    }
    final etiket = k.keyLabel;
    return etiket.length == 1 ? etiket.toUpperCase() : etiket;
  }

  static const _gorunenTuslar = {
    'Up': 'Yukarı',
    'Down': 'Aşağı',
    'Left': 'Sol',
    'Right': 'Sağ',
    'Space': 'Boşluk',
    'PageUp': 'Sayfa Yukarı',
    'PageDown': 'Sayfa Aşağı',
    'Delete': 'Sil',
    'Arrow Up': 'Yukarı',
    'Arrow Down': 'Aşağı',
    'Arrow Left': 'Sol',
    'Arrow Right': 'Sağ',
    'Page Up': 'Sayfa Yukarı',
    'Page Down': 'Sayfa Aşağı',
  };

  /// Menüde ve listelerde gösterilen kısayol: "Ctrl+Alt+Down" ->
  /// "Ctrl+Alt+Aşağı". Kayıtlı biçim (ayar dosyası) değişmez.
  static String goster(String kisayol) => kisayol.isEmpty
      ? kisayol
      : kisayol.split('+').map((p) => _gorunenTuslar[p.trim()] ?? p).join('+');

  /// SingleActivator -> "Ctrl+Shift+K".
  static String metin(SingleActivator a) => [
        if (a.control) 'Ctrl',
        if (a.shift) 'Shift',
        if (a.alt) 'Alt',
        if (a.meta) 'Win',
        tusAdi(a.trigger),
      ].join('+');

  /// "Ctrl+Shift+K" -> SingleActivator (çözülemezse null).
  static SingleActivator? coz(String metin) {
    final parcalar = metin.split('+').map((p) => p.trim()).toList();
    if (parcalar.isEmpty || parcalar.last.isEmpty) return null;
    final tusMetni = parcalar.removeLast();
    LogicalKeyboardKey? tus = _ozelTuslar[tusMetni];
    if (tus == null) {
      for (final k in LogicalKeyboardKey.knownLogicalKeys) {
        if (k.keyLabel.toUpperCase() == tusMetni.toUpperCase()) {
          tus = k;
          break;
        }
      }
    }
    if (tus == null) return null;
    final m = parcalar.map((p) => p.toLowerCase()).toSet();
    return SingleActivator(tus,
        control: m.contains('ctrl'),
        shift: m.contains('shift'),
        alt: m.contains('alt'),
        meta: m.contains('win'));
  }

  static List<AppAction> uygula(List<AppAction> eylemler) {
    if (tablo.isEmpty) return eylemler;
    return [
      for (final a in eylemler)
        if (!tablo.containsKey(a.id))
          a
        else
          AppAction(
            id: a.id,
            label: a.label,
            menu: a.menu,
            icon: a.icon,
            run: a.run,
            activator: coz(tablo[a.id]!),
            shortcut: coz(tablo[a.id]!) == null ? '' : tablo[a.id]!,
            // Eskiden düşüyordu: kısayolu değiştirilen eklenti eylemi,
            // eklenti kurulu değilken de menüde görünüyordu.
            eklenti: a.eklenti,
          ),
    ];
  }
}

List<AppAction> buildAppActions() =>
    OzelKisayollar.uygula(_varsayilanEylemler());

Map<String, String>? _guncelKisayollar;
int _guncelKisayolSurumu = -1;

/// İpucu metni: "Adım At (F10)". Kısayol, kullanıcının Klavye Kısayolları
/// penceresinde değiştirdiği tuşu gösterir (eskiden hep varsayılan yazıyordu).
String kisayolluIpucu(String etiket, String eylemId) {
  if (_guncelKisayollar == null || _guncelKisayolSurumu != OzelKisayollar.surum) {
    _guncelKisayollar = {for (final a in buildAppActions()) a.id: a.shortcut};
    _guncelKisayolSurumu = OzelKisayollar.surum;
  }
  final k = _guncelKisayollar![eylemId] ?? '';
  return k.isEmpty ? etiket : '$etiket (${OzelKisayollar.goster(k)})';
}

/// Kısayolları değiştirme penceresi.
Future<void> kisayolPenceresiniAc(BuildContext context) =>
    showDialog(context: context, builder: (_) => const KisayolDialog());

class KisayolDialog extends StatefulWidget {
  const KisayolDialog({super.key});
  @override
  State<KisayolDialog> createState() => _KisayolDialogState();
}

class _KisayolDialogState extends State<KisayolDialog> {
  final _varsayilan = {for (final a in _varsayilanEylemler()) a.id: a};
  late Map<String, String> _tablo = Map.of(OzelKisayollar.tablo);
  String _filtre = '';

  String _gecerli(AppAction a) => _tablo.containsKey(a.id)
      ? _tablo[a.id]!
      : (a.activator == null ? '' : OzelKisayollar.metin(a.activator!));

  Future<void> _kaydet() async {
    OzelKisayollar.ayarla(_tablo);
    await context.read<SettingsProvider>().setValue('kisayollar', _tablo);
  }

  Future<void> _degistir(AppAction a) async {
    final yeni = await showDialog<String>(
        context: context, builder: (_) => _TusYakalaDialog(eylem: a.label));
    if (yeni == null || !mounted) return;
    final cakisan = _varsayilan.values
        .where((b) => b.id != a.id && yeni.isNotEmpty && _gecerli(b) == yeni)
        .toList();
    if (cakisan.isNotEmpty) {
      final devam = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Kısayol kullanımda'),
          content: Text("$yeni şu anda '${cakisan.first.label}' için kullanılıyor. "
              'Oradan kaldırılıp buraya atansın mı?'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('Vazgeç')),
            FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('Ata')),
          ],
        ),
      );
      if (devam != true) return;
      for (final b in cakisan) {
        _tablo[b.id] = '';
      }
    }
    setState(() {
      final varsayilan = _varsayilan[a.id]?.activator;
      if (varsayilan != null && OzelKisayollar.metin(varsayilan) == yeni) {
        _tablo.remove(a.id);
      } else {
        _tablo[a.id] = yeni;
      }
    });
    await _kaydet();
  }

  @override
  Widget build(BuildContext context) {
    final eylemler = _varsayilan.values
        .where((a) =>
            _filtre.isEmpty ||
            a.label.toLowerCase().contains(_filtre.toLowerCase()) ||
            _gecerli(a).toLowerCase().contains(_filtre.toLowerCase()))
        .toList();
    return AlertDialog(
      title: const Text('Klavye Kısayolları'),
      content: SizedBox(
        width: 600,
        height: 460,
        child: Column(children: [
          TextField(
            decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search, size: 18),
                hintText: 'Komut ya da tuş ara',
                isDense: true),
            onChanged: (v) => setState(() => _filtre = v),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: eylemler.length,
              itemBuilder: (c, i) {
                final a = eylemler[i];
                final ozel = _tablo.containsKey(a.id);
                final tus = _gecerli(a);
                return ListTile(
                  dense: true,
                  leading: Icon(a.icon ?? Icons.bolt, size: 18),
                  title: Text(a.label),
                  subtitle: a.menu == null ? null : Text(a.menu!),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(tus.isEmpty ? '—' : OzelKisayollar.goster(tus),
                        style: TextStyle(
                            fontFamily: kMonoFontFamily,
                            fontWeight:
                                ozel ? FontWeight.bold : FontWeight.normal)),
                    IconButton(
                      tooltip: 'Değiştir',
                      icon: const Icon(Icons.edit_outlined, size: 16),
                      onPressed: () => _degistir(a),
                    ),
                    IconButton(
                      tooltip: 'Varsayılana döndür',
                      icon: const Icon(Icons.restart_alt, size: 16),
                      onPressed: ozel
                          ? () async {
                              setState(() => _tablo.remove(a.id));
                              await _kaydet();
                            }
                          : null,
                    ),
                  ]),
                );
              },
            ),
          ),
        ]),
      ),
      actions: [
        TextButton(
          onPressed: _tablo.isEmpty
              ? null
              : () async {
                  setState(() => _tablo = {});
                  await _kaydet();
                },
          child: const Text('Tümünü Sıfırla'),
        ),
        FilledButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat')),
      ],
    );
  }
}

/// Bir tuş birleşimini yakalar: "Ctrl+Shift+K" ya da kaldırmak için "".
class _TusYakalaDialog extends StatefulWidget {
  const _TusYakalaDialog({required this.eylem});
  final String eylem;
  @override
  State<_TusYakalaDialog> createState() => _TusYakalaDialogState();
}

class _TusYakalaDialogState extends State<_TusYakalaDialog> {
  final FocusNode _odak = FocusNode();
  String? _yakalanan;

  static final Set<LogicalKeyboardKey> _degistiriciler = {
    LogicalKeyboardKey.controlLeft, LogicalKeyboardKey.controlRight,
    LogicalKeyboardKey.shiftLeft, LogicalKeyboardKey.shiftRight,
    LogicalKeyboardKey.altLeft, LogicalKeyboardKey.altRight,
    LogicalKeyboardKey.metaLeft, LogicalKeyboardKey.metaRight,
  };

  @override
  void dispose() {
    _odak.dispose();
    super.dispose();
  }

  KeyEventResult _tus(FocusNode _, KeyEvent e) {
    if (e is! KeyDownEvent || _degistiriciler.contains(e.logicalKey)) {
      return KeyEventResult.handled;
    }
    if (e.logicalKey == LogicalKeyboardKey.escape) {
      Navigator.pop(context);
      return KeyEventResult.handled;
    }
    final k = HardwareKeyboard.instance;
    setState(() => _yakalanan = OzelKisayollar.metin(SingleActivator(
        e.logicalKey,
        control: k.isControlPressed,
        shift: k.isShiftPressed,
        alt: k.isAltPressed,
        meta: k.isMetaPressed)));
    return KeyEventResult.handled;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text("'${widget.eylem}' için tuşa basın"),
      content: Focus(
        focusNode: _odak,
        autofocus: true,
        onKeyEvent: _tus,
        child: Container(
          width: 320,
          height: 70,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: Border.all(color: Theme.of(context).colorScheme.primary),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(_yakalanan ?? 'Tuş birleşimine basın… (Esc: vazgeç)',
              style: const TextStyle(fontFamily: kMonoFontFamily, fontSize: 16)),
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context, ''),
            child: const Text('Kısayolu kaldır')),
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Vazgeç')),
        FilledButton(
            onPressed: _yakalanan == null
                ? null
                : () => Navigator.pop(context, _yakalanan),
            child: const Text('Ata')),
      ],
    );
  }
}

List<AppAction> _varsayilanEylemler() {
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
      id: 'file.recent',
      label: 'Son Dosyalar',
      menu: 'Dosya',
      shortcut: 'Ctrl+Shift+O',
      activator: const SingleActivator(LogicalKeyboardKey.keyO,
          control: true, shift: true),
      icon: Icons.history,
      run: (c) => _recentFilesDialog(c),
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
      id: 'file.save_all',
      label: 'Tümünü Kaydet',
      menu: 'Dosya',
      shortcut: 'Ctrl+Shift+S',
      activator: const SingleActivator(LogicalKeyboardKey.keyS,
          control: true, shift: true),
      icon: Icons.save_alt,
      run: (c) async {
        try {
          final n = await c.read<EditorProvider>().saveAll(context: c);
          if (c.mounted) {
            showAppSnackbar(
                c, n == 0 ? 'Kaydedilecek değişiklik yok' : '$n dosya kaydedildi',
                kind: n == 0 ? SnackKind.info : SnackKind.success);
          }
        } catch (e) {
          if (c.mounted) {
            showAppSnackbar(c, 'Kaydetme hatası: $e', kind: SnackKind.error);
          }
        }
      },
    ),
    AppAction(
      id: 'file.close_tab',
      label: 'Sekmeyi Kapat',
      menu: 'Dosya',
      shortcut: 'Ctrl+W',
      activator: const SingleActivator(LogicalKeyboardKey.keyW, control: true),
      icon: Icons.close,
      run: (c) {
        final ed = c.read<EditorProvider>();
        final i = ed.activeIndex;
        if (i < 0) return;
        final iste = ed.sekmeKapatIste;
        if (iste != null) {
          iste(i);
        } else {
          ed.closeTab(i);
        }
      },
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
    // Ctrl+Z / Ctrl+Y editörün kendisinde çalışır; menü ve komut paletinden
    // erişim için burada kısayolsuz kayıtlıdır.
    AppAction(
      id: 'edit.undo',
      label: 'Geri Al',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Z',
      icon: Icons.undo,
      run: (c) => c.read<EditorProvider>().undo?.call(),
    ),
    AppAction(
      id: 'edit.redo',
      label: 'Yinele',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Y',
      icon: Icons.redo,
      run: (c) => c.read<EditorProvider>().redo?.call(),
    ),
    AppAction(
      id: 'edit.cut',
      label: 'Kes',
      menu: 'Düzenle',
      shortcut: 'Ctrl+X',
      icon: Icons.content_cut,
      run: (c) => c.read<EditorProvider>().kes?.call(),
    ),
    AppAction(
      id: 'edit.copy',
      label: 'Kopyala',
      menu: 'Düzenle',
      shortcut: 'Ctrl+C',
      icon: Icons.content_copy,
      run: (c) => c.read<EditorProvider>().kopyala?.call(),
    ),
    AppAction(
      id: 'edit.paste',
      label: 'Yapıştır',
      menu: 'Düzenle',
      shortcut: 'Ctrl+V',
      icon: Icons.content_paste,
      run: (c) => c.read<EditorProvider>().yapistir?.call(),
    ),
    AppAction(
      id: 'edit.select_all',
      label: 'Tümünü Seç',
      menu: 'Düzenle',
      shortcut: 'Ctrl+A',
      icon: Icons.select_all,
      run: (c) => c.read<EditorProvider>().tumunuSec?.call(),
    ),
    AppAction(
      id: 'edit.goto_line',
      label: 'Satıra Git…',
      menu: 'Düzenle',
      shortcut: 'Ctrl+G',
      activator: const SingleActivator(LogicalKeyboardKey.keyG, control: true),
      icon: Icons.low_priority,
      run: (c) => satiraGit(c),
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
      id: 'edit.find_in_files',
      label: 'Dosyalarda Ara',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Shift+F',
      activator: const SingleActivator(LogicalKeyboardKey.keyF,
          control: true, shift: true),
      icon: Icons.manage_search,
      run: (c) async {
        final ed = c.read<EditorProvider>();
        final ctrl = ed.uiController;
        final sel = ctrl?.selection;
        final secili = ctrl != null && sel != null && sel.isValid && !sel.isCollapsed
            ? ctrl.text.substring(sel.start, sel.end)
            : null;
        final hedef = await showDialog<({String yol, int satir})>(
          context: c,
          builder: (_) => DosyalardaAraDialog(
              baslangic: secili != null && !secili.contains('\n') ? secili : null),
        );
        if (hedef != null && c.mounted) {
          await dosyadaSatiraGit(c, hedef.yol, hedef.satir);
        }
      },
    ),
    AppAction(
      id: 'edit.goto_definition',
      label: 'Tanıma Git',
      menu: 'Düzenle',
      shortcut: 'F12',
      activator: const SingleActivator(LogicalKeyboardKey.f12),
      icon: Icons.call_made,
      run: (c) => tanimaGit(c),
    ),
    AppAction(
      id: 'edit.cursor_below',
      label: 'Alta İmleç Ekle',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Alt+Down',
      activator: const SingleActivator(LogicalKeyboardKey.arrowDown,
          control: true, alt: true),
      icon: Icons.keyboard_double_arrow_down,
      run: (c) => c.read<EditorProvider>().cokluImlec?.call('asagi'),
    ),
    AppAction(
      id: 'edit.cursor_above',
      label: 'Üste İmleç Ekle',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Alt+Up',
      activator: const SingleActivator(LogicalKeyboardKey.arrowUp,
          control: true, alt: true),
      icon: Icons.keyboard_double_arrow_up,
      run: (c) => c.read<EditorProvider>().cokluImlec?.call('yukari'),
    ),
    AppAction(
      id: 'edit.select_next',
      label: 'Sonraki Eşleşmeyi Seçime Ekle',
      menu: 'Düzenle',
      shortcut: 'Ctrl+D',
      activator: const SingleActivator(LogicalKeyboardKey.keyD, control: true),
      icon: Icons.playlist_add,
      run: (c) => c.read<EditorProvider>().cokluImlec?.call('sonraki'),
    ),
    AppAction(
      id: 'edit.select_all_matches',
      label: 'Tüm Eşleşmeleri Seç',
      menu: 'Düzenle',
      shortcut: 'Ctrl+Shift+L',
      activator: const SingleActivator(LogicalKeyboardKey.keyL,
          control: true, shift: true),
      icon: Icons.select_all,
      run: (c) => c.read<EditorProvider>().cokluImlec?.call('tumu'),
    ),
    AppAction(
      id: 'edit.rename',
      label: 'Adı Değiştir…',
      menu: 'Düzenle',
      shortcut: 'F2',
      activator: const SingleActivator(LogicalKeyboardKey.f2),
      icon: Icons.drive_file_rename_outline,
      run: (c) => adiDegistir(c),
    ),
    AppAction(
      id: 'edit.format',
      label: 'Kodu Biçimlendir',
      menu: 'Düzenle',
      shortcut: 'Shift+Alt+F',
      activator: const SingleActivator(LogicalKeyboardKey.keyF,
          shift: true, alt: true),
      icon: Icons.format_align_left,
      run: (c) => koduBicimlendir(c),
    ),
    AppAction(
      id: 'view.problems',
      label: 'Sorunlar',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+M',
      activator: const SingleActivator(LogicalKeyboardKey.keyM,
          control: true, shift: true),
      icon: Icons.report_problem_outlined,
      run: (c) => sorunlariGoster(c),
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
      label: 'AI Panelini Aç/Kapat',
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
      id: 'view.split',
      label: 'Editörü Böl (Yan Yana)',
      menu: 'Görünüm',
      shortcut: 'Ctrl+\\',
      activator:
          const SingleActivator(LogicalKeyboardKey.backslash, control: true),
      icon: Icons.vertical_split,
      run: (c) {
        final ui = c.read<UiProvider>();
        final ed = c.read<EditorProvider>();
        if (ui.yanSekmeId != null) {
          ui.yanSekmeAyarla(null);
        } else if (ed.activeTab != null &&
            !ozelSekmeMi(ed.activeTab!.path) &&
            !ed.activeTab!.isPdf) {
          ui.yanSekmeAyarla(ed.activeTab!.id);
        } else if (ed.activeTab != null && ed.activeTab!.isPdf) {
          showAppSnackbar(c, 'PDF dosyaları bölünmüş görünümde açılamaz.');
        }
      },
    ),
    AppAction(
      id: 'view.panel_swap',
      label: 'Yan Panellerin Yerini Değiştir',
      menu: 'Görünüm',
      icon: Icons.swap_horiz_rounded,
      run: (c) => c.read<UiProvider>().yanPanelleriDegistir(),
    ),
    AppAction(
      id: 'view.panel_reset',
      label: 'Panel Düzenini Sıfırla',
      menu: 'Görünüm',
      icon: Icons.restart_alt_rounded,
      run: (c) => c.read<UiProvider>().panelSirasiniSifirla(),
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
      id: 'view.keybindings',
      label: 'Klavye Kısayolları…',
      menu: 'Görünüm',
      icon: Icons.keyboard_outlined,
      run: (c) => kisayolPenceresiniAc(c),
    ),
    AppAction(
      id: 'view.settings',
      label: 'Ayarlar',
      menu: 'Görünüm',
      icon: Icons.settings_outlined,
      run: (c) => c.read<EditorProvider>().openSettings(),
    ),
    AppAction(
      id: 'view.browser',
      label: 'Tarayıcı',
      menu: 'Görünüm',
      icon: Icons.public_rounded,
      run: (c) => c.read<EditorProvider>().openBrowser(),
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
      label: 'Kesme Noktası Aç/Kapat',
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
      id: 'run.breakpoint_condition',
      label: 'Koşullu Kesme Noktası…',
      menu: 'Çalıştır',
      shortcut: 'Shift+F9',
      activator: const SingleActivator(LogicalKeyboardKey.f9, shift: true),
      icon: Icons.filter_alt_outlined,
      run: (c) {
        final ed = c.read<EditorProvider>();
        final ctrl = ed.uiController;
        if (ctrl == null) return;
        final line = ed.caretModelLine?.call() ?? cursorLineOf(ctrl);
        showBreakpointConditionDialog(c, ed.activeTab?.id, line);
      },
    ),
    AppAction(
      id: 'run.args',
      label: 'Çalıştırma Argümanları…',
      menu: 'Çalıştır',
      icon: Icons.tune,
      run: (c) => _runArgsDialog(c),
    ),
    AppAction(
      id: 'run.exe',
      label: "EXE'ye Dönüştür…",
      menu: 'Çalıştır',
      icon: Icons.inventory_2_outlined,
      run: (c) => exeDonusturmePaneliAc(c),
    ),
    AppAction(
      id: 'run.exe_kaynak',
      label: "EXE'nin Kaynak Kodunu Aç…",
      menu: 'Çalıştır',
      icon: Icons.source_outlined,
      run: (c) => exeKaynaginiAc(c),
    ),
    AppAction(
      id: 'run.breakpoint_clear',
      label: 'Tüm Kesme Noktalarını Kaldır',
      menu: 'Çalıştır',
      icon: Icons.layers_clear_outlined,
      run: (c) => c
          .read<BreakpointProvider>()
          .clearAll(c.read<EditorProvider>().activeTab?.id),
    ),
    AppAction(
      id: 'run.debug_start',
      label: 'Hata Ayıklamayı Başlat / Devam',
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
      id: 'run.debug_run_to_cursor',
      label: 'İmlece Kadar Çalıştır',
      menu: 'Çalıştır',
      shortcut: 'Ctrl+F10',
      activator: const SingleActivator(LogicalKeyboardKey.f10, control: true),
      icon: Icons.vertical_align_bottom,
      run: (c) {
        final ed = c.read<EditorProvider>();
        final ctrl = ed.uiController;
        if (ctrl == null) return;
        final line = ed.caretModelLine?.call() ?? cursorLineOf(ctrl);
        final bp = c.read<BreakpointProvider>();
        if (bp.paused) {
          _debugWrap(c, (b) => b.runToLine(line));
        } else if (!bp.debugging) {
          _debugStart(c, geciciSatir: line);
        }
      },
    ),
    AppAction(
      id: 'run.debug_continue',
      label: 'Devam',
      // Menüde "Hata Ayıklamayı Başlat / Devam" (F5) aynı işi yapıyor; bu
      // eylem yalnız araç çubuğunda ve Komut Paleti'nde.
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
      label: 'Hata Ayıklamayı Durdur',
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
      label: 'Yapılacaklar Listesi',
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
      id: 'tools.shell',
      label: 'TürKod Kabuğu (komut satırı)…',
      menu: 'Araçlar',
      shortcut: 'Ctrl+Shift+K',
      activator: const SingleActivator(LogicalKeyboardKey.keyK,
          control: true, shift: true),
      icon: Icons.keyboard_command_key,
      run: (c) => turkodKabuguAc(c),
    ),
    AppAction(
      id: 'view.extensions',
      label: 'Eklenti Özellikleri',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+X',
      activator: const SingleActivator(LogicalKeyboardKey.keyX,
          control: true, shift: true),
      icon: Icons.extension_outlined,
      run: (c) => c.read<UiProvider>().solPanelSec('eklentiler'),
    ),
    AppAction(
      id: 'tools.local_models',
      label: 'Yerel AI Modelleri…',
      menu: 'Araçlar',
      icon: Icons.memory,
      run: (c) => yerelModelYoneticisiniAc(c),
    ),
    AppAction(
      id: 'edit.ai_complete',
      label: 'AI Önerisi İste (hayalet kod)',
      menu: 'Düzenle',
      // Ctrl+Shift+Boşluk bazı masaüstü uygulamalarının genel kısayolu
      // (tuş IDE'ye hiç ulaşmıyordu).
      shortcut: 'Ctrl+Shift+Space',
      activator: const SingleActivator(LogicalKeyboardKey.space,
          control: true, shift: true),
      icon: Icons.auto_awesome,
      run: (c) => aiOnerisiIste(c),
    ),
    AppAction(
      id: 'tools.snippets',
      label: 'Kod Parçacıkları…',
      menu: 'Araçlar',
      shortcut: 'Ctrl+Shift+J',
      activator: const SingleActivator(LogicalKeyboardKey.keyJ,
          control: true, shift: true),
      icon: Icons.widgets_outlined,
      eklenti: kEklentiParcaciklar,
      run: (c) => parcaciklariAc(c),
    ),
    AppAction(
      id: 'view.md_preview',
      label: 'Markdown Önizleme',
      menu: 'Görünüm',
      shortcut: 'Ctrl+Shift+V',
      activator: const SingleActivator(LogicalKeyboardKey.keyV,
          control: true, shift: true),
      icon: Icons.article_outlined,
      eklenti: kEklentiMarkdown,
      run: (c) => markdownOnizle(c),
    ),
    AppAction(
      id: 'learn.book',
      label: '$kKitapAdi (Kitap)',
      menu: 'Öğren',
      icon: Icons.menu_book_outlined,
      run: (c) => kitabiAc(c),
    ),
    AppAction(
      id: 'learn.docs',
      label: 'Dokümantasyon Sitesi',
      menu: 'Öğren',
      icon: Icons.public,
      run: (c) => baglantiAc(c, kSiteUrl),
    ),
    AppAction(
      id: 'help.tour',
      label: 'Arayüz Turu',
      menu: 'Yardım',
      icon: Icons.tour_outlined,
      run: (c) => arayuzTurunuBaslat(c),
    ),
    AppAction(
      id: 'help.kodi',
      label: 'Kodi ile Konuş',
      menu: 'Yardım',
      icon: Icons.smart_toy_outlined,
      activator: const SingleActivator(LogicalKeyboardKey.f1),
      run: (c) => c.read<KodiProvider>().degistir(),
    ),
    AppAction(
      id: 'help.github',
      label: 'GitHub Sayfası',
      menu: 'Yardım',
      icon: Icons.code,
      run: (c) => baglantiAc(c, kGithubUrl),
    ),
    AppAction(
      id: 'help.issue',
      label: 'Hata Bildir / Öneri Gönder',
      menu: 'Yardım',
      icon: Icons.bug_report_outlined,
      run: (c) => baglantiAc(c, kHataBildirUrl),
    ),
    AppAction(
      id: 'help.contact',
      label: 'İletişim ($kEposta)',
      menu: 'Yardım',
      icon: Icons.mail_outline,
      run: (c) => epostaYaz(c),
    ),
    AppAction(
      id: 'help.licenses',
      label: 'Lisanslar',
      menu: 'Yardım',
      icon: Icons.gavel_outlined,
      run: (c) => lisanslariGoster(c),
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

/// Arayüz turunu açar ve "her açılışta göster" ayarını kutuya bağlar.
/// Tur bir kez görüldü olarak işaretlenir (ilk açılışta yeniden çıkmaz).
Future<void> arayuzTurunuBaslat(BuildContext context) async {
  final ayarlar = context.read<SettingsProvider>();
  await arayuzTurunuGoster(
    context,
    herAcilista: ayarlar.getBool(kTurHerAcilista),
    herAcilistaKaydet: (v) => ayarlar.setValueBildir(context, kTurHerAcilista, v),
  );
  if (!ayarlar.getBool(kTurGoruldu)) {
    try {
      await ayarlar.setValue(kTurGoruldu, true);
    } catch (_) {}
  }
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
  final Color typeColor;
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
    required this.typeColor,
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
    typeColor: Color(0xFF38BDF8),
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
    Color? typeColor,
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
      typeColor: typeColor ?? this.typeColor,
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
      typeColor: Color.lerp(typeColor, other.typeColor, t)!,
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
        typeColor: Color(0xFF4EC9B0),
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
        typeColor: Color(0xFF075A70),
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
    // Az gören kullanıcılar ve projektör için: saf siyah zemin, beyaz metin,
    // sarı vurgu; tüm renkler siyah üzerinde WCAG AAA (7:1) kontrastındadır.
    AppThemeDefinition(
      name: 'Yüksek Kontrast',
      brightness: Brightness.dark,
      primary: Color(0xFFFFD600),
      onPrimary: Color(0xFF000000),
      surface: Color(0xFF000000),
      surfaceLow: Color(0xFF000000),
      surfaceContainer: Color(0xFF0A0A0A),
      surfaceHigh: Color(0xFF1A1A1A),
      onSurface: Color(0xFFFFFFFF),
      outline: Color(0xFFFFFFFF),
      outlineVariant: Color(0xFFBDBDBD),
      hover: Color(0xFF262626),
      syntax: AppSyntaxPalette(
        keyword: Color(0xFF6FC3FF),
        string: Color(0xFFFFB86C),
        number: Color(0xFFB5FF8A),
        comment: Color(0xFFA6E3A1),
        function: Color(0xFFFFFF66),
        typeColor: Color(0xFF4EEAC9),
        variable: Color(0xFFFFFFFF),
        operatorColor: Color(0xFFFFFFFF),
        punctuation: Color(0xFFFFFFFF),
        matchBackground: Color(0x99FFD600),
        activeMatchBackground: Color(0xFFFF9800),
        activeMatchBorder: Color(0xFFFFFFFF),
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
          borderRadius: BorderRadius.circular(6),
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
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: def.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: def.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: def.primary),
        ),
      ),
      dialogTheme: DialogThemeData(
        elevation: 0,
        backgroundColor: def.surfaceContainer,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
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
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          elevation: 0,
          shadowColor: Colors.transparent,
          side: BorderSide(color: def.outlineVariant),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          textStyle: const TextStyle(fontSize: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
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
      popupMenuTheme: PopupMenuThemeData(
        color: def.surfaceContainer,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: BorderSide(color: def.outline),
        ),
      ),
      // İnce, yuvarlak kaydırma çubukları (editör, listeler, paneller).
      scrollbarTheme: ScrollbarThemeData(
        thickness: const WidgetStatePropertyAll(7),
        radius: const Radius.circular(8),
        thumbColor: WidgetStateProperty.resolveWith((s) =>
            def.onSurface.withValues(
                alpha: s.contains(WidgetState.hovered) ||
                        s.contains(WidgetState.dragged)
                    ? 0.40
                    : 0.22)),
      ),
      extensions: [def.syntax],
    );
  }
}

// ============================================================================
// SYNTAX HIGHLIGHTING
// ============================================================================

const _kAcanParantez = '([{';
const _kKapayanParantez = ')]}';

/// [konum]daki parantezin eşinin konumu (yoksa null). Metin ve yorum
/// içindeki parantezler sayılmaz; üç tırnaklı metinler de atlanır.
int? parantezEsi(String t, int konum) {
  if (konum < 0 || konum >= t.length) return null;
  if (!_kAcanParantez.contains(t[konum]) &&
      !_kKapayanParantez.contains(t[konum])) {
    return null;
  }
  final yigin = <int>[];
  var i = 0;
  while (i < t.length) {
    final ch = t[i];
    if (ch == '#') {
      final son = t.indexOf('\n', i);
      if (son < 0) break;
      i = son;
      continue;
    }
    if (ch == '"' || ch == "'") {
      final uclu = t.startsWith(ch * 3, i);
      final bitis = uclu ? ch * 3 : ch;
      var j = i + bitis.length;
      while (j < t.length) {
        if (t[j] == '\\') {
          j += 2;
          continue;
        }
        if (!uclu && t[j] == '\n') break;
        if (t.startsWith(bitis, j)) break;
        j++;
      }
      // İmleç metnin içindeyse parantez eşleştirilmez.
      if (konum >= i && konum < j) return null;
      i = j + bitis.length;
      continue;
    }
    final ac = _kAcanParantez.indexOf(ch);
    if (ac >= 0) {
      yigin.add(i);
    } else {
      final kapa = _kKapayanParantez.indexOf(ch);
      if (kapa >= 0) {
        if (yigin.isEmpty || t[yigin.last] != _kAcanParantez[kapa]) {
          if (i == konum) return null;
        } else {
          final acan = yigin.removeLast();
          if (acan == konum) return i;
          if (i == konum) return acan;
        }
      }
    }
    i++;
  }
  return null;
}

/// Çoklu imleç düzenlemesinin sonucu.
class CokluDuzenleme {
  final String metin;
  final TextSelection birincil;
  final List<TextSelection> ekler;
  const CokluDuzenleme(this.metin, this.birincil, this.ekler);
}

/// Birincil imleçte yapılan düzenlemeyi ([eski] → [yeni]) ek imleçlere
/// de uygular. Düzenleme "imlecin b karakter önünden a karakter sonrasına
/// kadarını sil, yerine şunu yaz" diye modellenir; böylece yazma, silme,
/// otomatik parantez ve Enter'daki girinti aynı kuralla yansır. Model
/// kurulamazsa (çok büyük / imleçten uzak değişiklik, örtüşen imleçler)
/// null döner; çağıran taraf ek imleçleri bırakır.
CokluDuzenleme? cokluDuzenle(String eski, TextSelection eskiSecim, String yeni,
    TextSelection yeniSecim, List<TextSelection> ekler) {
  if (!eskiSecim.isValid || !yeniSecim.isValid || ekler.isEmpty) return null;
  final s = eskiSecim.start.clamp(0, eski.length).toInt();
  final e = eskiSecim.end.clamp(0, eski.length).toInt();
  // Ortak önek/sonek yeni imlecin ötesine taşmamalı: "hel|lo"da Backspace
  // sonrası önek "hel" çıkıyor, yeni imleç (2) bölgenin dışında kalıyor ve
  // ek imleçler düşüyordu (çift harf ve girinti boşluklarında hep oluyordu).
  final ys = yeniSecim.start.clamp(0, yeni.length).toInt();
  final ye = yeniSecim.end.clamp(0, yeni.length).toInt();
  var p = 0;
  final pMax = math.min(math.min(s, yeni.length), ys);
  while (p < pMax && eski.codeUnitAt(p) == yeni.codeUnitAt(p)) {
    p++;
  }
  var q = 0;
  final qMax = math.min(eski.length - e, yeni.length - math.max(p, ye));
  while (q < qMax &&
      eski.codeUnitAt(eski.length - 1 - q) ==
          yeni.codeUnitAt(yeni.length - 1 - q)) {
    q++;
  }
  final once = s - p;
  final sonra = (eski.length - q) - e;
  final eklenen = yeni.substring(p, yeni.length - q);
  if (once > 64 || sonra > 64 || eklenen.length > 20000) return null;
  final gBase = yeniSecim.baseOffset - p;
  final gExt = yeniSecim.extentOffset - p;
  if (gBase < 0 || gBase > eklenen.length || gExt < 0 || gExt > eklenen.length) {
    return null;
  }
  final bolgeler = <(int, int, bool)>[(p, eski.length - q, true)];
  for (final x in ekler) {
    final bas = x.start - once;
    final son = x.end + sonra;
    if (bas < 0 || son > eski.length) return null;
    bolgeler.add((bas, son, false));
  }
  bolgeler.sort((x, y) => x.$1.compareTo(y.$1));
  for (var i = 1; i < bolgeler.length; i++) {
    final onceki = bolgeler[i - 1];
    if (bolgeler[i].$1 < onceki.$2 ||
        (bolgeler[i].$1 == onceki.$1 && bolgeler[i].$2 == onceki.$2)) {
      return null;
    }
  }
  final sb = StringBuffer();
  var son = 0, kayma = 0;
  TextSelection? birincil;
  final yeniEkler = <TextSelection>[];
  for (final r in bolgeler) {
    sb.write(eski.substring(son, r.$1));
    final bas = r.$1 + kayma;
    sb.write(eklenen);
    final secim =
        TextSelection(baseOffset: bas + gBase, extentOffset: bas + gExt);
    if (r.$3) {
      birincil = secim;
    } else {
      yeniEkler.add(secim);
    }
    kayma += eklenen.length - (r.$2 - r.$1);
    son = r.$2;
  }
  sb.write(eski.substring(son));
  return CokluDuzenleme(sb.toString(), birincil!, yeniEkler);
}

/// Ek imleçleri / seçimleri çizer (birincil imleci re_editor çizer).
class _EkImlecPainter extends CustomPainter {
  final _ParagraphsBridge bridge;
  final GlobalKey indicatorKey;
  final List<(int, int, int, int)> secimler; // satır1, sütun1, satır2, sütun2
  final Color renk;
  _EkImlecPainter(this.bridge, this.indicatorKey, this.secimler, this.renk)
      : super(repaint: bridge);

  @override
  void paint(Canvas canvas, Size size) {
    final paragraphs = bridge.value?.paragraphs;
    if (paragraphs == null || secimler.isEmpty) return;
    final box = indicatorKey.currentContext?.findRenderObject();
    final left = box is RenderBox && box.hasSize ? box.size.width : 0.0;
    final imlec = Paint()..color = renk;
    final secim = Paint()..color = renk.withValues(alpha: 0.28);
    canvas.save();
    canvas.clipRect(Rect.fromLTRB(left, 0, size.width, size.height));
    for (final p in paragraphs) {
      for (final s in secimler) {
        if (s.$1 > p.index || s.$3 < p.index) continue;
        final bas = s.$1 == p.index ? s.$2 : 0;
        final son = s.$3 == p.index ? s.$4 : p.paragraph.length;
        final x0 = left + p.offset.dx;
        if (bas != son) {
          for (final r in p.paragraph.getRangeRects(
              TextRange(start: math.min(bas, son), end: math.max(bas, son)))) {
            canvas.drawRect(r.shift(Offset(x0, p.top)), secim);
          }
        }
        if (s.$3 == p.index) {
          final o = p.paragraph.getOffset(TextPosition(offset: s.$4)) ??
              Offset.zero;
          canvas.drawRect(
              Rect.fromLTWH(x0 + o.dx, p.top + o.dy, 2,
                  p.preferredLineHeight),
              imlec);
        }
      }
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_EkImlecPainter old) =>
      !listEquals(old.secimler, secimler) || old.renk != renk;
}

/// Hayalet kod: AI önerisini imleçten başlayarak gri/italik çizer. İlk satır
/// imlecin olduğu yerde; satırın geri kalanı (kapanış parantezi vb.) önerinin
/// sağına kaydırılarak yeniden çizilir. Sonraki satırlar alttaki satırların
/// üzerine (editör zeminiyle örtülerek) çizilir: VS Code'daki gibi araya
/// eklenmiş satırlar görünür; belge değişmez.
class _HayaletPainter extends CustomPainter {
  final _ParagraphsBridge bridge;
  final GlobalKey indicatorKey;
  final int satir;
  final int sutun;
  final String metin;
  final String satirSonu;
  final TextStyle stil;
  final Color normalRenk;
  final Color zemin;
  final Color ipucuRengi;
  _HayaletPainter({
    required this.bridge,
    required this.indicatorKey,
    required this.satir,
    required this.sutun,
    required this.metin,
    required this.satirSonu,
    required this.stil,
    required this.normalRenk,
    required this.zemin,
    required this.ipucuRengi,
  }) : super(repaint: bridge);

  TextPainter _tp(String s, TextStyle st) =>
      TextPainter(text: TextSpan(text: s, style: st), textDirection: TextDirection.ltr)
        ..layout();

  @override
  void paint(Canvas canvas, Size size) {
    final paragraphs = bridge.value?.paragraphs;
    if (paragraphs == null) return;
    re.CodeLineRenderParagraph? p;
    for (final x in paragraphs) {
      if (x.index == satir) {
        p = x;
        break;
      }
    }
    if (p == null) return;
    final box = indicatorKey.currentContext?.findRenderObject();
    final left = box is RenderBox && box.hasSize ? box.size.width : 0.0;
    final x0 = left + p.offset.dx;
    final o = p.paragraph.getOffset(TextPosition(offset: sutun)) ?? Offset.zero;
    final lh = p.preferredLineHeight;
    final zeminBoya = Paint()..color = zemin;
    canvas.save();
    canvas.clipRect(Rect.fromLTRB(left, 0, size.width, size.height));

    final satirlar = metin.split('\n');
    final y0 = p.top + o.dy;
    final ilk = _tp(satirlar.first, stil);
    var sonX = x0 + o.dx + ilk.width;
    if (satirSonu.isNotEmpty) {
      final son = _tp(satirSonu, stil.copyWith(color: normalRenk, fontStyle: FontStyle.normal));
      canvas.drawRect(Rect.fromLTWH(x0 + o.dx, y0, ilk.width + son.width + 6, lh), zeminBoya);
      ilk.paint(canvas, Offset(x0 + o.dx, y0));
      son.paint(canvas, Offset(sonX, y0));
      sonX += son.width;
    } else {
      ilk.paint(canvas, Offset(x0 + o.dx, y0));
    }
    var sonY = y0;
    for (var i = 1; i < satirlar.length; i++) {
      final y = y0 + lh * i;
      canvas.drawRect(Rect.fromLTRB(left, y, size.width, y + lh), zeminBoya);
      final tp = _tp(satirlar[i], stil);
      tp.paint(canvas, Offset(x0, y));
      sonX = x0 + tp.width;
      sonY = y;
    }
    final ipucu = _tp(
        '   Tab ↹ kabul · Esc',
        stil.copyWith(
            fontSize: (stil.fontSize ?? 14) * 0.72,
            fontStyle: FontStyle.normal,
            color: ipucuRengi));
    ipucu.paint(canvas, Offset(sonX, sonY + (lh - ipucu.height) / 2));
    canvas.restore();
  }

  @override
  bool shouldRepaint(_HayaletPainter old) =>
      old.metin != metin ||
      old.satir != satir ||
      old.sutun != sutun ||
      old.satirSonu != satirSonu ||
      old.stil != stil;
}

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
    if (FindOptions.regex) {
      final re = FindOptions.compile(needle);
      if (re == null) return const [];
      for (final m in re.allMatches(haystack)) {
        if (m.end == m.start) continue; // boş eşleşmeler (ör. "a*") atlanır
        if (FindOptions.wholeWord &&
            !FindOptions.isWordBoundary(haystack, m.start, m.end)) {
          continue;
        }
        out.add([m.start, m.end]);
      }
      return out;
    }
    final cs = FindOptions.caseSensitive;
    for (var i = 0; i + needle.length <= haystack.length; i++) {
      var ok = true;
      for (var j = 0; j < needle.length; j++) {
        final a = haystack[i + j], b = needle[j];
        if (cs ? a != b : !_trCharEquals(a, b)) {
          ok = false;
          break;
        }
      }
      if (ok &&
          FindOptions.wholeWord &&
          !FindOptions.isWordBoundary(haystack, i, i + needle.length)) {
        ok = false;
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

  /// Satırdaki tek tek karakterlere (eşleşen parantezler) arka plan verir.
  static List<InlineSpan> applyCharHighlight(
      List<InlineSpan> spans, Set<int> sutunlar, Color arkaPlan) {
    if (sutunlar.isEmpty) return spans;
    final sonuc = <InlineSpan>[];
    var pos = 0;
    for (final s in spans) {
      final metin = s is TextSpan ? s.text : null;
      if (s is! TextSpan || metin == null || metin.isEmpty) {
        sonuc.add(s);
        continue;
      }
      var parcaBasi = 0;
      for (var k = 0; k < metin.length; k++) {
        if (!sutunlar.contains(pos + k)) continue;
        if (k > parcaBasi) {
          sonuc.add(TextSpan(
              text: metin.substring(parcaBasi, k), style: s.style));
        }
        sonuc.add(TextSpan(
          text: metin[k],
          style: (s.style ?? const TextStyle()).copyWith(
              backgroundColor: arkaPlan, fontWeight: FontWeight.bold),
        ));
        parcaBasi = k + 1;
      }
      if (parcaBasi < metin.length) {
        sonuc.add(TextSpan(text: metin.substring(parcaBasi), style: s.style));
      }
      pos += metin.length;
    }
    return sonuc;
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
          style = base.copyWith(color: palette.typeColor);
        } else if (_builtins.contains(lower)) {
          style = base.copyWith(color: palette.function);
        } else if (_isFunctionCall(text, m.end)) {
          style = base.copyWith(color: palette.function);
        } else if (_isType(token)) {
          style = base.copyWith(color: palette.typeColor);
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
        ? 'TürKod motoru yeniden başlatılıyor...'
        : durdu
            ? '${conn.sonHata ?? 'TürKod motoru çalışmıyor.'} '
                r'Ayrıntı: %LOCALAPPDATA%\TurKod\backend.log'
            : 'TürKod motoruyla bağlantı yok; yeniden bağlanılıyor...';
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
    'Öğren',
    'Yardım',
    'Güncelleştirmeler'
  ];
  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      for (final g in _groups)
        KeyedSubtree(
         key: g == 'Yardım' ? TurHedefleri.yardimMenusu : null,
         child: PopupMenuButton<String>(
          tooltip: '',
          position: PopupMenuPosition.under,
          offset: const Offset(0, 2),
          color: Theme.of(context).colorScheme.surfaceContainerHigh,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
            side: BorderSide(color: Theme.of(context).colorScheme.outline),
          ),
          // Uzun eylem adları + kısayol dar menüde taşıyordu.
          constraints: const BoxConstraints(minWidth: 240, maxWidth: 460),
          onSelected: (id) {
            final a = findAction(actions, id);
            if (a != null) a.run(context);
          },
          itemBuilder: (c) => actions
              .where((a) => a.menu == g && a.gorunur(context))
              .map((a) => PopupMenuItem<String>(
                    value: a.id,
                    height: 30,
                    child: Row(children: [
                      Expanded(
                        child: Text(a.label,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13)),
                      ),
                      const SizedBox(width: 24),
                      Text(OzelKisayollar.goster(a.shortcut),
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
    // Üst satır: logo + menüler | ortada komut arama | sağda panel düğmeleri.
    return Container(
      height: 38,
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        border: Border(
            bottom: BorderSide(color: theme.colorScheme.outlineVariant)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10),
      child: Row(children: [
        Image.asset('assets/icon/app_icon.png',
            width: 20,
            height: 20,
            filterQuality: FilterQuality.medium,
            errorBuilder: (_, __, ___) => Icon(Icons.terminal_rounded,
                size: 18, color: theme.colorScheme.primary)),
        const SizedBox(width: 8),
        Text('TürKod',
            style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800, letterSpacing: -0.2)),
        const SizedBox(width: 12),
        KeyedSubtree(
            key: TurHedefleri.menu, child: _MenuBar(actions: actions)),
        const SizedBox(width: 12),
        Expanded(
          child: Align(
            alignment: Alignment.center,
            child: KomutAramaKutusu(actions: actions),
          ),
        ),
        const SizedBox(width: 12),
        const DuzenDugmeleri(),
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

  static const Map<String, IconData> _ikonlar = {
    'file.open_file': Icons.file_open_outlined,
    'file.open': Icons.folder_open_outlined,
    'file.save': Icons.save_outlined,
    'file.save_as': Icons.save_as_outlined,
    'run.run': Icons.play_arrow_rounded,
    'run.stop': Icons.stop_rounded,
    'run.debug_start': Icons.bug_report_outlined,
    'tools.convert': Icons.swap_horiz_rounded,
    'tools.fix': Icons.auto_fix_high_outlined,
    'edit.find_replace': Icons.find_replace_rounded,
    'run.debug_step': Icons.redo_rounded,
    'run.debug_step_into': Icons.subdirectory_arrow_right_rounded,
    'run.debug_step_out': Icons.subdirectory_arrow_left_rounded,
    'run.debug_stop': Icons.stop_circle_outlined,
  };

  // Anlamlı renkler; açık temada okunaklı olsun diye koyulaştırılır.
  static const Color _mavi = Color(0xFF38BDF8);
  static const Color _kehribar = Color(0xFFF59E0B);
  static const Color _camgobegi = Color(0xFF14B8A6);
  static const Color _yesil = Color(0xFF22C55E);
  static const Color _kirmizi = Color(0xFFEF4444);
  static const Color _turuncu = Color(0xFFF97316);
  static const Color _mor = Color(0xFF818CF8);
  static const Color _sari = Color(0xFFEAB308);
  static const Color _pembe = Color(0xFFF472B6);

  static String _ipucu(AppAction a) => a.shortcut.isEmpty
      ? a.label
      : '${a.label} (${OzelKisayollar.goster(a.shortcut)})';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final koyu = theme.brightness == Brightness.dark;
    Color ton(Color c) => koyu ? c : Color.lerp(c, Colors.black, 0.28)!;
    final calisiyor = context.select<TerminalProvider, bool>((t) => t.isRunning);
    final (hataAyikliyor, durakli) = context
        .select<BreakpointProvider, (bool, bool)>((b) => (b.debugging, b.paused));

    return LayoutBuilder(builder: (context, kisit) {
      // Genişlik azaldıkça yazılar sırayla gizlenir (simgeler ve ipuçları kalır).
      final w = kisit.maxWidth;
      final calistirmaYazili = w >= 560;
      final araclarYazili = w >= 760;

      Widget dugme(String id, Color renk,
          {String? yazi, bool dolu = false, bool etkin = true, Key? key}) {
        final a = findAction(actions, id);
        if (a == null) return const SizedBox.shrink();
        return _AracDugmesi(
          key: key,
          ikon: _ikonlar[id] ?? a.icon ?? Icons.circle_outlined,
          yazi: yazi,
          renk: ton(renk),
          dolu: dolu,
          ipucu: _ipucu(a),
          onPressed: etkin ? () => a.run(context) : null,
        );
      }

      Widget grup(List<Widget> ogeler) => Container(
            margin: const EdgeInsets.symmetric(horizontal: 4),
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: cs.outlineVariant),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: ogeler),
          );

      final gruplar = <Widget>[
        grup([
          dugme('file.open_file', _mavi),
          dugme('file.open', _kehribar),
          dugme('file.save', _camgobegi),
          dugme('file.save_as', _camgobegi),
        ]),
        grup([
          dugme('run.run', _yesil,
              yazi: 'Çalıştır', dolu: true, key: TurHedefleri.calistir),
          dugme('run.stop', _kirmizi,
              yazi: calistirmaYazili ? 'Durdur' : null,
              etkin: calisiyor || hataAyikliyor,
              dolu: calisiyor),
          dugme('run.debug_start', _turuncu,
              yazi: calistirmaYazili ? (hataAyikliyor ? 'Devam' : 'Hata Ayıkla') : null,
              etkin: !hataAyikliyor || durakli,
              dolu: hataAyikliyor,
              key: TurHedefleri.hataAyikla),
        ]),
        if (hataAyikliyor)
          grup([
            dugme('run.debug_step', _mavi, etkin: durakli),
            dugme('run.debug_step_into', _mavi, etkin: durakli),
            dugme('run.debug_step_out', _mavi, etkin: durakli),
            dugme('run.debug_stop', _kirmizi),
          ]),
        grup([
          dugme('tools.convert', _mor, yazi: araclarYazili ? 'Çevir' : null),
          dugme('tools.fix', _sari,
              yazi: araclarYazili ? 'Düzelt' : null, key: TurHedefleri.duzelt),
          dugme('edit.find_replace', _pembe),
        ]),
      ];
      return Container(
        height: 46,
        decoration: BoxDecoration(
          color: cs.surfaceContainer,
          border: Border(bottom: BorderSide(color: cs.outlineVariant)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 6),
        child: _YatayKaydirma(
          child: Row(
              key: TurHedefleri.aracCubugu,
              mainAxisSize: MainAxisSize.min,
              children: gruplar),
        ),
      );
    });
  }
}

/// Araç çubuğu düğmesi: renkli simge, isteğe bağlı yazı; "dolu" ise renkli
/// zemin ve çerçeve. Üzerine gelince kendi renginde hafifçe boyanır.
class _AracDugmesi extends StatefulWidget {
  final IconData ikon;
  final String? yazi;
  final Color renk;
  final bool dolu;
  final String ipucu;
  final VoidCallback? onPressed;
  const _AracDugmesi({
    super.key,
    required this.ikon,
    required this.renk,
    required this.ipucu,
    required this.onPressed,
    this.yazi,
    this.dolu = false,
  });
  @override
  State<_AracDugmesi> createState() => _AracDugmesiState();
}

class _AracDugmesiState extends State<_AracDugmesi> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final etkin = widget.onPressed != null;
    final renk = etkin ? widget.renk : cs.onSurface.withValues(alpha: 0.3);
    final zemin = !etkin
        ? Colors.transparent
        : widget.dolu
            ? widget.renk.withValues(alpha: _uzerinde ? 0.30 : 0.20)
            : _uzerinde
                ? widget.renk.withValues(alpha: 0.13)
                : Colors.transparent;
    return Tooltip(
      message: widget.ipucu,
      waitDuration: const Duration(milliseconds: 400),
      child: MouseRegion(
        cursor: etkin ? SystemMouseCursors.click : SystemMouseCursors.basic,
        onEnter: (_) => setState(() => _uzerinde = true),
        onExit: (_) => setState(() => _uzerinde = false),
        child: GestureDetector(
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 120),
            height: 32,
            padding: EdgeInsets.symmetric(horizontal: widget.yazi == null ? 7 : 10),
            margin: const EdgeInsets.symmetric(horizontal: 1),
            decoration: BoxDecoration(
              color: zemin,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                  color: widget.dolu && etkin
                      ? widget.renk.withValues(alpha: 0.65)
                      : Colors.transparent),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(widget.ikon, size: 18, color: renk),
              if (widget.yazi != null) ...[
                const SizedBox(width: 6),
                Text(widget.yazi!,
                    style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: etkin
                            ? (widget.dolu ? renk : cs.onSurface.withValues(alpha: 0.9))
                            : renk)),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

/// Yatay kaydırılabilen satır: içerik sığmazsa altta ince bir kaydırma
/// çubuğu görünür (dar pencerede araç çubuğunun gizli düğmeleri eskiden
/// fark edilmiyordu). Fare tekerleği de yatay kaydırır.
class _YatayKaydirma extends StatefulWidget {
  final Widget child;
  const _YatayKaydirma({required this.child});
  @override
  State<_YatayKaydirma> createState() => _YatayKaydirmaState();
}

class _YatayKaydirmaState extends State<_YatayKaydirma> {
  final _ctrl = ScrollController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _tekerlek(PointerSignalEvent e) {
    if (e is! PointerScrollEvent || !_ctrl.hasClients) return;
    final pos = _ctrl.position;
    if (pos.maxScrollExtent <= 0) return;
    final hedef = (pos.pixels + e.scrollDelta.dy + e.scrollDelta.dx)
        .clamp(pos.minScrollExtent, pos.maxScrollExtent);
    _ctrl.jumpTo(hedef);
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerSignal: _tekerlek,
      child: ScrollbarTheme(
        data: Theme.of(context)
            .scrollbarTheme
            .copyWith(thickness: const WidgetStatePropertyAll(3)),
        child: Scrollbar(
          controller: _ctrl,
          thumbVisibility: true,
          child: LayoutBuilder(
            // İçerik sığarsa ortalanır, sığmazsa kaydırılır.
            builder: (context, c) => SingleChildScrollView(
              controller: _ctrl,
              scrollDirection: Axis.horizontal,
              child: ConstrainedBox(
                constraints: BoxConstraints(minWidth: c.maxWidth),
                child: Center(child: widget.child),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ============================================================================
// DOSYA GEZGİNİ
// ============================================================================

/// Gezgin için ad soran pencere (yeni dosya / klasör, yeniden adlandırma).
Future<String?> _askName(BuildContext context, String title, String initial,
    {String? hint}) async {
  // Uzantıdan önceki kısım seçili gelir (VS Code gibi).
  final nokta = initial.lastIndexOf('.');
  final sonuc = await showDialog<String>(
    context: context,
    builder: (_) => DenetleyiciliDialog(
      metin: initial,
      secimSonu: nokta > 0 ? nokta : initial.length,
      builder: (dc, ctrl) => AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: 380,
          child: TextField(
            controller: ctrl,
            autofocus: true,
            decoration: InputDecoration(
                hintText: hint, border: const OutlineInputBorder(), isDense: true),
            onSubmitted: (v) => Navigator.pop(dc, v),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc), child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, ctrl.text),
              child: const Text('Tamam')),
        ],
      ),
    ),
  );
  final ad = sonuc?.trim();
  return ad == null || ad.isEmpty ? null : ad;
}

Future<void> _explorerCreate(BuildContext context, String dir,
    {required bool folder}) async {
  final ad = await _askName(context, folder ? 'Yeni Klasör' : 'Yeni Dosya',
      folder ? '' : 'yeni.trpy',
      hint: folder ? 'klasör adı' : 'dosya adı (ör. oyun.trpy)');
  if (ad == null || !context.mounted) return;
  final (hata, yol) =
      await context.read<FileTreeProvider>().create(dir, ad, folder: folder);
  if (!context.mounted) return;
  if (hata != null) {
    showAppSnackbar(context, hata, kind: SnackKind.error);
  } else if (!folder && yol != null) {
    await context.read<EditorProvider>().openFile(yol, context: context);
  }
}

Future<void> _explorerRename(BuildContext context, FileNode node) async {
  final ad = await _askName(context, 'Yeniden Adlandır', node.name);
  if (ad == null || ad == node.name || !context.mounted) return;
  final (hata, yeni) = await context.read<FileTreeProvider>().rename(node, ad);
  if (!context.mounted) return;
  if (hata != null) {
    showAppSnackbar(context, hata, kind: SnackKind.error);
  } else if (yeni != null) {
    context.read<EditorProvider>().renamePath(node.path, yeni);
  }
}

Future<void> _explorerDelete(BuildContext context, FileNode node) async {
  final onay = await showDialog<bool>(
    context: context,
    builder: (dc) => AlertDialog(
      title: Text(node.isDir ? 'Klasörü sil' : 'Dosyayı sil'),
      content: Text('"${node.name}"${node.isDir ? ' ve içindekiler' : ''} '
          'Geri Dönüşüm Kutusu\'na taşınsın mı?'),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(dc, false),
            child: const Text('Vazgeç')),
        FilledButton(
            onPressed: () => Navigator.pop(dc, true), child: const Text('Sil')),
      ],
    ),
  );
  if (onay != true || !context.mounted) return;
  final agac = context.read<FileTreeProvider>();
  var sonuc = await agac.sil(node);
  if (!context.mounted) return;
  // Bu sürücüde Geri Dönüşüm Kutusu yok: kalıcı silme ayrıca onaylanır.
  if (sonuc.kaliciGerekir) {
    final kalici = await showDialog<bool>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Kalıcı olarak silinsin mi?'),
        content: Text(sonuc.hata ??
            'Bu sürücüde geri dönüşüm kutusu yok; dosya kalıcı olarak '
                'silinecek. Silinsin mi?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, false),
              child: const Text('Vazgeç')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: Theme.of(dc).colorScheme.error,
                  foregroundColor: Theme.of(dc).colorScheme.onError),
              onPressed: () => Navigator.pop(dc, true),
              child: const Text('Kalıcı Olarak Sil')),
        ],
      ),
    );
    if (kalici != true || !context.mounted) return;
    sonuc = await agac.sil(node, kalici: true);
    if (!context.mounted) return;
  }
  if (sonuc.hata != null) {
    showAppSnackbar(context, sonuc.hata!, kind: SnackKind.error);
  } else {
    context.read<EditorProvider>().markDeleted(node.path);
    showAppSnackbar(
        context,
        sonuc.kalici
            ? '"${node.name}" kalıcı olarak silindi'
            : '"${node.name}" Geri Dönüşüm Kutusu\'na taşındı',
        kind: SnackKind.success);
  }
}

/// Gezgin sağ tık menüsü. [node] null ise kök klasör içindir.
Future<void> _explorerMenu(
    BuildContext context, FileNode? node, Offset position) async {
  final tree = context.read<FileTreeProvider>();
  final root = tree.root;
  if (root == null) return;
  final dir = node == null
      ? root.path
      : node.isDir
          ? node.path
          : p.dirname(node.path);
  final overlay = Overlay.of(context).context.findRenderObject() as RenderBox;
  PopupMenuItem<String> item(String v, IconData icon, String label) =>
      PopupMenuItem<String>(
        value: v,
        height: 34,
        child: Row(children: [
          Icon(icon, size: 16),
          const SizedBox(width: 10),
          Text(label, style: const TextStyle(fontSize: 13)),
        ]),
      );
  final secim = await showMenu<String>(
    context: context,
    position: RelativeRect.fromRect(
        position & const Size(1, 1), Offset.zero & overlay.size),
    items: [
      item('dosya', Icons.note_add_outlined, 'Yeni Dosya'),
      item('klasor', Icons.create_new_folder_outlined, 'Yeni Klasör'),
      if (node != null) ...[
        const PopupMenuDivider(),
        item('ad', Icons.drive_file_rename_outline, 'Yeniden Adlandır'),
        item('sil', Icons.delete_outline, 'Sil'),
      ],
      const PopupMenuDivider(),
      item('yenile', Icons.refresh, 'Yenile'),
    ],
  );
  if (!context.mounted || secim == null) return;
  switch (secim) {
    case 'dosya':
      await _explorerCreate(context, dir, folder: false);
    case 'klasor':
      await _explorerCreate(context, dir, folder: true);
    case 'ad':
      await _explorerRename(context, node!);
    case 'sil':
      await _explorerDelete(context, node!);
    case 'yenile':
      await tree.reloadDir(dir);
  }
}

/// Gezgin satırı: üzerine gelince hafif vurgu, seçiliyse solda renkli
/// çizgi ve boyalı zemin.
class _GezginSatiri extends StatefulWidget {
  final bool secili;
  final Widget child;
  const _GezginSatiri({required this.secili, required this.child});
  @override
  State<_GezginSatiri> createState() => _GezginSatiriState();
}

class _GezginSatiriState extends State<_GezginSatiri> {
  bool _uzerinde = false;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return MouseRegion(
      onEnter: (_) => setState(() => _uzerinde = true),
      onExit: (_) => setState(() => _uzerinde = false),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        decoration: BoxDecoration(
          color: widget.secili
              ? cs.primary.withValues(alpha: 0.14)
              : _uzerinde
                  ? cs.onSurface.withValues(alpha: 0.06)
                  : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        child: widget.child,
      ),
    );
  }
}

/// Gezgin boşken gösterilen açıklama (ve varsa düğme).
class _GezginBos extends StatelessWidget {
  final IconData ikon;
  final String metin;
  final String? dugme;
  final VoidCallback? onPressed;
  const _GezginBos(
      {required this.ikon, required this.metin, this.dugme, this.onPressed});
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(ikon, size: 34, color: cs.onSurface.withValues(alpha: 0.3)),
          const SizedBox(height: 10),
          Text(metin,
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 12.5,
                  height: 1.4,
                  color: cs.onSurface.withValues(alpha: 0.6))),
          if (dugme != null) ...[
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onPressed,
              icon: const Icon(Icons.folder_open_outlined, size: 16),
              label: Text(dugme!),
            ),
          ],
        ]),
      ),
    );
  }
}

class FileTreePanel extends StatelessWidget {
  const FileTreePanel({super.key});
  static const Color _folderColor = Color(0xFFE8A33D);

  /// Dosya türüne göre simge (eskiden hepsi aynı sayfa simgesiydi).
  IconData _fileIcon(String n) {
    final l = n.toLowerCase();
    if (l.endsWith('.trpy')) return Icons.code_rounded;
    if (l.endsWith('.py')) return Icons.terminal_rounded;
    if (l.endsWith('.md')) return Icons.article_outlined;
    if (l.endsWith('.txt')) return Icons.notes_rounded;
    if (l.endsWith('.pdf')) return Icons.picture_as_pdf_outlined;
    if (l.endsWith('.json') || l.endsWith('.yaml') || l.endsWith('.yml')) {
      return Icons.data_object_rounded;
    }
    if (l.endsWith('.exe')) return Icons.apps_rounded;
    if (l.endsWith('.png') ||
        l.endsWith('.jpg') ||
        l.endsWith('.jpeg') ||
        l.endsWith('.gif') ||
        l.endsWith('.ico')) {
      return Icons.image_outlined;
    }
    if (l.endsWith('.mp3') || l.endsWith('.wav') || l.endsWith('.ogg')) {
      return Icons.music_note_outlined;
    }
    return Icons.insert_drive_file_outlined;
  }
  Color _fileColor(String n) {
    final l = n.toLowerCase();
    if (l.endsWith('.trpy')) return const Color(0xFF4EC9B0);
    if (l.endsWith('.py')) return const Color(0xFF569CD6);
    if (l.endsWith('.dart')) return const Color(0xFF42A5F5);
    if (l.endsWith('.json')) return const Color(0xFFE5C07B);
    if (l.endsWith('.md')) return const Color(0xFF9E9E9E);
    if (l.endsWith('.pdf')) return const Color(0xFFEF4444);
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
          onSecondaryTapDown: (d) => _explorerMenu(ctx, node, d.globalPosition),
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
          child: _GezginSatiri(
            secili: isActive,
            child: Padding(
            padding: EdgeInsets.only(
                left: 6.0 + depth * 14, right: 8, top: 4, bottom: 4),
            child: Row(children: [
              // Klasörlerde açılıp kapanma oku; dosyalarda aynı genişlikte boşluk.
              SizedBox(
                width: 16,
                child: node.isDir
                    ? AnimatedRotation(
                        turns: node.expanded ? 0.25 : 0,
                        duration: kAnim,
                        child: Icon(Icons.chevron_right_rounded,
                            size: 16,
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.55)),
                      )
                    : null,
              ),
              const SizedBox(width: 2),
              Icon(
                node.isDir
                    ? (node.expanded
                        ? Icons.folder_open_rounded
                        : Icons.folder_rounded)
                    : _fileIcon(node.name),
                size: 16,
                color: node.isDir ? _folderColor : _fileColor(node.name),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(node.name,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: 13,
                        color: isActive ? theme.colorScheme.primary : null,
                        fontWeight:
                            isActive ? FontWeight.w600 : FontWeight.normal)),
              ),
            ]),
          ),
          ),
        ),
      ),
      if (node.isDir && node.expanded) ...[
        ...node.children.map((c) => _buildNode(ctx, c, depth + 1, activePath)),
        if (node.fazlaOge > 0) _fazlaSatiri(theme, node.fazlaOge, depth + 1),
      ],
    ]);
  }

  /// Klasör kesildiyse kullanıcı bunu bilsin (eskiden kalan dosyalar
  /// sessizce görünmüyordu).
  Widget _fazlaSatiri(ThemeData theme, int sayi, int depth) => Padding(
        padding:
            EdgeInsets.only(left: 8.0 + depth * 14, right: 8, top: 4, bottom: 4),
        child: Text('… $sayi öğe daha gösterilmiyor',
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
                fontSize: 12,
                fontStyle: FontStyle.italic,
                color: theme.colorScheme.onSurfaceVariant)),
      );

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
        PanelBasligi(
          ikon: Icons.folder_copy_outlined,
          baslik: 'Gezgin',
          surukleId: 'gezgin',
          eylemler: [
            PanelDugmesi(
              ikon: Icons.note_add_outlined,
              ipucu: 'Yeni Dosya',
              onPressed: conn && tree.root != null
                  ? () => _explorerCreate(context, tree.root!.path, folder: false)
                  : null,
            ),
            PanelDugmesi(
              ikon: Icons.create_new_folder_outlined,
              ipucu: 'Yeni Klasör',
              onPressed: conn && tree.root != null
                  ? () => _explorerCreate(context, tree.root!.path, folder: true)
                  : null,
            ),
            PanelDugmesi(
              ikon: Icons.folder_open_outlined,
              ipucu: 'Klasör Aç',
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
            PanelDugmesi(
              ikon: Icons.refresh_rounded,
              ipucu: 'Yenile',
              onPressed: conn ? tree.refresh : null,
            ),
          ],
        ),
        // Açık proje klasörünün adı (VS Code gibi).
        if (conn && tree.root != null)
          Tooltip(
            message: tree.root!.path,
            waitDuration: const Duration(milliseconds: 500),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 10, 2),
              child: Row(children: [
                Icon(Icons.inventory_2_outlined,
                    size: 14,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.6)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                      trBuyuk(p.basename(tree.root!.path)),
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.6,
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.7))),
                ),
              ]),
            ),
          ),
        Expanded(
          child: !conn
              ? const _GezginBos(
                  ikon: Icons.cloud_off_outlined,
                  metin: 'TürKod motoruna bağlanılıyor…',
                )
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
                          ? _GezginBos(
                              ikon: Icons.folder_off_outlined,
                              metin: 'Henüz bir klasör açmadın.\nKodlarının '
                                  'durduğu klasörü seç.',
                              dugme: 'Klasör Aç',
                              onPressed: () async {
                                final d = await FilePicker.platform
                                    .getDirectoryPath();
                                if (d != null && context.mounted) {
                                  await context
                                      .read<FileTreeProvider>()
                                      .setProjectDirectory(d);
                                }
                              },
                            )
                          : GestureDetector(
                              // Boş alana sağ tık: kök klasörde yeni öğe.
                              behavior: HitTestBehavior.translucent,
                              onSecondaryTapDown: (d) =>
                                  _explorerMenu(context, null, d.globalPosition),
                              child: ListView(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 4),
                                children: [
                                  ...tree.root!.children.map((c) =>
                                      _buildNode(context, c, 0, activePath)),
                                  if (tree.root!.fazlaOge > 0)
                                    _fazlaSatiri(Theme.of(context),
                                        tree.root!.fazlaOge, 0),
                                ],
                              ),
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

  EditorProvider? _ed;

  @override
  void initState() {
    super.initState();
    _ed = context.read<EditorProvider>()
      ..sekmeKapatIste = (i) => _requestClose(_ed!, i);
  }

  @override
  void dispose() {
    if (_ed?.sekmeKapatIste != null) _ed!.sekmeKapatIste = null;
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

  static IconData _sekmeSimgesi(String yol) {
    if (yol == kSettingsPath) return Icons.settings_outlined;
    if (yol == kTarayiciPath) return Icons.public_rounded;
    final k = yol.toLowerCase();
    if (k.endsWith('.trpy') || k.startsWith('untitled:')) return Icons.code;
    if (k.endsWith('.py')) return Icons.terminal;
    if (k.endsWith('.md')) return Icons.article_outlined;
    if (k.endsWith('.pdf')) return Icons.picture_as_pdf_outlined;
    return Icons.description_outlined;
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
          child: AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            margin: const EdgeInsets.only(top: 7, bottom: 7, right: 3),
            padding: const EdgeInsets.symmetric(horizontal: 10.5),
            decoration: BoxDecoration(
              // Etkin sekme ana renkle hafifçe boyanır; ötekiler sönük kalır.
              color: active
                  ? theme.colorScheme.primary.withValues(alpha: 0.14)
                  : theme.colorScheme.surfaceContainer,
              borderRadius: BorderRadius.circular(7),
              border: Border.all(
                color: active
                    ? theme.colorScheme.primary
                    : theme.colorScheme.outlineVariant,
              ),
            ),
            child: Row(children: [
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Icon(_sekmeSimgesi(t.path),
                    size: 13,
                    color: active
                        ? theme.colorScheme.primary
                        : theme.colorScheme.onSurface.withValues(alpha: 0.5)),
              ),
              Text(
                t.name,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: active ? FontWeight.w600 : FontWeight.normal,
                  color: active
                      ? theme.colorScheme.onSurface
                      : theme.colorScheme.onSurface.withValues(alpha: 0.72),
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
          tooltip: kisayolluIpucu('Yeni Sekme', 'file.new_tab'),
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
  /// Koşullu breakpoint'ler (turuncu çizilir).
  final Set<int> conditional;
  final int? currentLine;
  final Map<int, String> foldIcons;
  final Color normalColor;
  final Color breakpointColor;
  final Color currentColor;
  final double fontSize;

  _EditorIndicatorPainter({
    required this.notifier,
    required this.breakpoints,
    this.conditional = const {},
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
          Paint()
            ..color = currentLine == line
                ? currentColor
                : conditional.contains(line)
                    ? Colors.orange
                    : breakpointColor,
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
      old.conditional != conditional ||
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

/// Bul / Değiştir seçenekleri. Eşleştirme hem Bul kutusunda hem editör
/// vurgusunda aynı fonksiyonla (findAllMatches) yapıldığı için tek yerde,
/// statik tutulur; değişince UiProvider.findOptionsVersion artar.
class FindOptions {
  static bool caseSensitive = false;
  static bool wholeWord = false;
  static bool regex = false;

  static String? _reSrc;
  static bool? _reCase;
  static RegExp? _re;

  /// Geçersiz desen için null (ör. kapanmamış parantez).
  static RegExp? compile(String pattern) {
    if (_reSrc == pattern && _reCase == caseSensitive) return _re;
    _reSrc = pattern;
    _reCase = caseSensitive;
    try {
      // multiLine: vurgu satır satır, sayaç ve "Tümünü Değiştir" bütün metin
      // üzerinde çalışır; ^ ve $ ikisinde de satır başı/sonu demek olmalı
      // (eskiden ^ yalnızca belge başında eşleşip vurguyla uyuşmuyordu).
      _re = RegExp(pattern,
          caseSensitive: caseSensitive, unicode: true, multiLine: true);
    } catch (_) {
      _re = null;
    }
    return _re;
  }

  static bool _isWordChar(int c) =>
      (c >= 0x30 && c <= 0x39) ||
      (c >= 0x41 && c <= 0x5A) ||
      (c >= 0x61 && c <= 0x7A) ||
      c == 0x5F ||
      c >= 0xC0; // Türkçe harfler (ç, ğ, ı, İ, ö, ş, ü ...) dahil

  static bool isWordBoundary(String s, int start, int end) =>
      (start == 0 || !_isWordChar(s.codeUnitAt(start - 1))) &&
      (end >= s.length || !_isWordChar(s.codeUnitAt(end)));

  /// Değiştirme metni: regex kipinde $1, $2 ... grupları yerine konur.
  static String replacementFor(String text, int start, String needle, String repl) {
    if (!regex) return repl;
    final re = compile(needle);
    final m = re?.matchAsPrefix(text, start);
    if (m == null) return repl;
    return repl.replaceAllMapped(RegExp(r'\$(\d+)|\$\$'), (g) {
      if (g.group(0) == r'$$') return r'$';
      final n = int.parse(g.group(1)!);
      return n <= m.groupCount ? (m.group(n) ?? '') : g.group(0)!;
    });
  }
}

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
    if (FindOptions.regex && FindOptions.compile(q) == null) {
      setState(() => _info = 'Geçersiz düzenli ifade');
      return;
    }
    final n = SyntaxHighlightingController.findAllMatches(t, q).length;
    setState(() => _info = '$n eşleşme');
  }

  void _toggleOption(void Function() degistir) {
    setState(degistir);
    FindOptions.compile(''); // derlenmiş desen önbelleğini geçersiz kıl
    _lastInfoQuery = null; // sayaç yeniden hesaplansın
    _updateInfo();
    context.read<UiProvider>().bumpFindOptions();
  }

  Widget _optionButton(String label, String tip, bool on, VoidCallback onTap) {
    final theme = Theme.of(context);
    return Tooltip(
      message: tip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(3),
        child: Container(
          width: 24,
          height: 22,
          alignment: Alignment.center,
          margin: const EdgeInsets.only(left: 2),
          decoration: BoxDecoration(
            color: on ? theme.colorScheme.primary.withOpacity(0.22) : null,
            border: Border.all(
                color: on
                    ? theme.colorScheme.primary
                    : theme.colorScheme.outlineVariant),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text(label,
              style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                  fontFamily: kMonoFontFamily,
                  color: on ? theme.colorScheme.primary : null)),
        ),
      ),
    );
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
    if (c == null || q.isEmpty) return;
    final sel = c.selection;
    // Seçim, metindeki eşleşmelerden biriyle BİREBİR örtüşüyorsa değiştirilir
    // (regex / tam kelime kipinde eşleşme uzunluğu sorgudan farklı olabilir).
    if (sel.isValid &&
        sel.start != sel.end &&
        SyntaxHighlightingController.findAllMatches(c.text, q)
            .any((m) => m[0] == sel.start && m[1] == sel.end)) {
      final r = FindOptions.replacementFor(c.text, sel.start, q, _rc.text);
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
    final eski = c.text;
    var nt = eski;
    for (final m in matches.reversed) {
      nt = nt.replaceRange(
          m[0], m[1], FindOptions.replacementFor(eski, m[0], q, _rc.text));
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
        (widget.bounds.width - 416).clamp(0, widget.bounds.width).toDouble(),
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
          width: 410,
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
                    (widget.bounds.width - 410)
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
              _optionButton('Aa', 'Büyük/küçük harf duyarlı',
                  FindOptions.caseSensitive,
                  () => _toggleOption(() =>
                      FindOptions.caseSensitive = !FindOptions.caseSensitive)),
              _optionButton('ab', 'Tam kelime', FindOptions.wholeWord,
                  () => _toggleOption(
                      () => FindOptions.wholeWord = !FindOptions.wholeWord)),
              _optionButton('.*', 'Düzenli ifade (regex)', FindOptions.regex,
                  () => _toggleOption(
                      () => FindOptions.regex = !FindOptions.regex)),
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

/// Blok açan satırda (":" ile biten; sondaki yorum yok sayılır) imleçteki
/// Enter'ın sonucu: yeni satır bir girinti seviyesi içeriden başlar ve
/// imlecin sağındaki metin oraya taşınır. Blok açmayan satırda null.
@visibleForTesting
TextEditingValue? blokAcanSatirdaYeniSatir(String t, int pos, int birim) {
  pos = pos.clamp(0, t.length).toInt();
  final ls = t.lastIndexOf('\n', pos == 0 ? 0 : pos - 1) + 1;
  final once = t.substring(ls, pos);
  // Yorum (metin dışındaki ilk '#') atılır: "x = 1  # not:" blok açmaz.
  var kod = once;
  String? tirnak;
  for (var i = 0; i < once.length; i++) {
    final c = once[i];
    if (tirnak != null) {
      if (c == '\\') {
        i++;
      } else if (c == tirnak) {
        tirnak = null;
      }
    } else if (c == '"' || c == "'") {
      tirnak = c;
    } else if (c == '#') {
      kod = once.substring(0, i);
      break;
    }
  }
  final girinti = RegExp(r'^[ \t]*').stringMatch(once) ?? '';
  if (!kod.trimRight().endsWith(':')) {
    // "döndür x" / "kır" / "devam_et" / "geç" / "hata_fırlat ..." bloğu
    // bitirir: satır sonunda Enter, bir seviye dışarıdan başlar (VS Code /
    // Python davranışı). Eskiden girinti korunuyor, sonraki kod ulaşılamaz
    // yere yazılıyordu.
    if (pos != t.length && t[pos] != '\n' && t[pos] != '\r') return null;
    final bitiren =
        RegExp(r'^[ \t]+(döndür|kır|devam_et|geç|hata_fırlat)(\s.*)?$');
    if (!bitiren.hasMatch(kod.trimRight())) return null;
    final dis = girinti.length > birim
        ? girinti.substring(0, girinti.length - birim)
        : '';
    final ekle = '\n$dis';
    return TextEditingValue(
      text: t.replaceRange(pos, pos, ekle),
      selection: TextSelection.collapsed(offset: pos + ekle.length),
    );
  }
  var le = t.indexOf('\n', pos);
  if (le < 0) le = t.length;
  final sag = t.substring(pos, le);
  final kesilen = sag.length - sag.trimLeft().length;
  final ekle = '\n$girinti${' ' * birim}';
  return TextEditingValue(
    text: t.replaceRange(pos, pos + kesilen, ekle),
    selection: TextSelection.collapsed(offset: pos + ekle.length),
  );
}

class CodeEditor extends StatefulWidget {
  const CodeEditor({super.key, this.sekmeYolu});

  /// Bu editörün gösterdiği sekmenin yolu (editör bu yolla anahtarlanır).
  /// Başka bir sekmeye geçilince eski editör, kaldırılmadan önce yeni
  /// sekmenin bekleyen imleç konumunu tüketmesin diye kullanılır.
  final String? sekmeYolu;
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

  static int _surum = -1;
  static Set<String> _onbellek = const {};

  // Kullanıcı kısayolları değiştirdiğinde yeniden hesaplanır.
  static Set<String> get _uygulama {
    if (_surum != OzelKisayollar.surum) {
      _surum = OzelKisayollar.surum;
      _onbellek = {
        for (final a in buildAppActions())
          if (a.activator != null) _anahtar(a.activator!),
      };
    }
    return _onbellek;
  }

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
  // Sözdizimi paleti editörün kendi build'inde okunur: re_editor'ın satır
  // oluşturucusuna verdiği bağlam tema değişimini izlemiyor ve açılışta
  // gelen varsayılan temanın renklerinde kalıyordu.
  AppSyntaxPalette _palet = AppSyntaxPalette.fallback;
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
  Timer? _debounce;

  // --- Hayalet kod (satır içi AI önerisi, VS Code gibi) ---------------------
  // Öneri belgeye EKLENMEZ; editörün üstüne gri çizilir (_HayaletPainter).
  // Tab kabul eder, Ctrl+→ kelime kelime kabul eder, Esc kapatır; önerinin
  // başıyla aynı karakterler yazılırsa öneri tüketilerek kalanı gösterilir.
  String? _hayalet;
  int _hayaletKonum = -1;
  String _hayaletMetni = '';
  Timer? _hayaletZamanlayici;
  int _hayaletNo = 0;
  bool _hayaletUygulaniyor = false;
  bool _hayaletSuruyor = false;
  bool _hayaletBekleyen = false;
  late final VoidCallback _hayaletIsteyici = () => _hayaletIste(zorla: true);
  int _hayaletOncekiUzunluk = 0;
  Timer? _syntaxTimer;
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
  /// Sözdizimi denetiminin bulduğu ilk hatanın MODEL satırı (yoksa null);
  /// editörde kırmızı şeritle gösterilir.
  int? _errorModelLine;

  // Parantez eşleşmesi önbelleği: [satır1, sütun1, satır2, sütun2] (görünüm
  // satırları). spanBuilder her satır için çağrıldığından metin ve imleç
  // değişmedikçe yeniden hesaplanmaz.
  List<int>? _parantezCifti;
  String? _parantezMetni;
  int _parantezSatir = -1, _parantezSutun = -1;

  List<int>? _parantezCiftiHesapla() {
    final sel = _reCtrl.selection;
    if (!sel.isCollapsed) return null;
    final metin = _reCtrl.text;
    if (identical(metin, _parantezMetni) || metin == _parantezMetni) {
      if (sel.baseIndex == _parantezSatir && sel.baseOffset == _parantezSutun) {
        return _parantezCifti;
      }
    }
    _parantezMetni = metin;
    _parantezSatir = sel.baseIndex;
    _parantezSutun = sel.baseOffset;
    _parantezCifti = null;
    if (metin.length > 300000) return null;
    final satirlar = metin.split('\n');
    if (sel.baseIndex < 0 || sel.baseIndex >= satirlar.length) return null;
    var satirBasi = 0;
    for (var i = 0; i < sel.baseIndex; i++) {
      satirBasi += satirlar[i].length + 1;
    }
    final imlec = satirBasi + sel.baseOffset;
    int? konum;
    bool parantezMi(int p) =>
        p >= 0 &&
        p < metin.length &&
        (_kAcanParantez.contains(metin[p]) ||
            _kKapayanParantez.contains(metin[p]));
    if (parantezMi(imlec - 1) && imlec - 1 >= satirBasi) {
      konum = imlec - 1;
    } else if (parantezMi(imlec)) {
      konum = imlec;
    }
    if (konum == null) return null;
    final es = parantezEsi(metin, konum);
    if (es == null) return null;
    List<int> satirSutun(int p) {
      final s = '\n'.allMatches(metin.substring(0, p)).length;
      final bas = metin.lastIndexOf('\n', p - 1) + 1;
      return [s, p - bas];
    }

    _parantezCifti = [...satirSutun(konum), ...satirSutun(es)];
    return _parantezCifti;
  }
  Size _vpSize = const Size(800, 600);
  final Map<int, _Fold> _folds = {};
  final Map<int, int> _foldViewByLine = {};
  // Sütun çizgileri / boşluk göstergesi katmanı için.
  final _ParagraphsBridge _paragraphs = _ParagraphsBridge();
  final GlobalKey _indicatorKey = GlobalKey();
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
        final palette = _palet;
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
        // === Parantez eşleşmesi =============================================
        final cift = _parantezCifti;
        final parantezSutunlari = <int>{
          if (cift != null && cift[0] == index) cift[1],
          if (cift != null && cift[2] == index) cift[3],
        };
        final parantezRengi =
            Theme.of(context).colorScheme.primary.withValues(alpha: 0.28);
        if (query.isEmpty) {
          return TextSpan(
            style: style,
            children: _sorunCizgileri(
                SyntaxHighlightingController.applyCharHighlight(
                    baseSpans, parantezSutunlari, parantezRengi),
                index,
                codeLine.text),
          );
        }
        int? activeStart, activeEnd;
        final sel = _reCtrl.selection;
        if (sel.isValid &&
            sel.baseIndex == index &&
            sel.extentIndex == index) {
          final s = math.min(sel.baseOffset, sel.extentOffset);
          final e = math.max(sel.baseOffset, sel.extentOffset);
          if (e > s &&
              s >= 0 &&
              e <= codeLine.text.length &&
              SyntaxHighlightingController.findAllMatches(
                      codeLine.text, query)
                  .any((m) => m[0] == s && m[1] == e)) {
            activeStart = s;
            activeEnd = e;
          }
        }
        final bulunan = TextSpan(
          style: style,
          children: SyntaxHighlightingController.applyCharHighlight(
            SyntaxHighlightingController.applyFindHighlight(
              baseSpans,
              codeLine.text,
              query,
              activeStart: activeStart,
              activeEnd: activeEnd,
              matchBackground: palette.matchBackground,
              activeMatchBackground: palette.activeMatchBackground,
            ),
            parantezSutunlari,
            parantezRengi,
          ),
        );
        return TextSpan(
          style: style,
          children: _sorunCizgileri(
              (bulunan.children ?? const <InlineSpan>[]).toList(),
              index,
              codeLine.text),
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
    ed.hayaletIste = _hayaletIsteyici;
    ed.caretOffsetProvider = _fullCaretOffset;
    ed.revealModelLine = _revealModelLine;
    ed.caretModelLine = _caretModelLine;
    ed.pushViewContent = _pushContent;
    ed.unfoldAll = _unfoldAll;
    ed.editorFocusNode = _focus;
    ed.undo = _undo;
    ed.redo = _redo;
    ed.kes = _kes;
    ed.kopyala = _kopyala;
    ed.yapistir = _yapistir;
    ed.tumunuSec = _tumunuSec;
    ed.cokluImlec = _cokluImlecKomutu;
  }

  void _kes() {
    _reCtrl.cut();
    _focus.requestFocus();
  }

  void _kopyala() {
    _reCtrl.copy();
    _focus.requestFocus();
  }

  void _yapistir() {
    _reCtrl.paste();
    _focus.requestFocus();
  }

  void _tumunuSec() {
    _reCtrl.selectAll();
    _focus.requestFocus();
  }

  // Menü / komut paletinden geri al / yinele (Ctrl+Z / Ctrl+Y editörün
  // kendi kısayollarıdır; değişiklik normal düzenleme yoluyla eşitlenir).
  void _undo() {
    if (_reCtrl.canUndo) _reCtrl.undo();
    _focus.requestFocus();
  }

  void _redo() {
    if (_reCtrl.canRedo) _reCtrl.redo();
    _focus.requestFocus();
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
  int _lastSyncedFindOptions = 0;
  void _onUiChange() {
    final ui = _ui;
    if (ui == null) return;
    if (ui.findQuery == _lastSyncedFindQuery &&
        ui.findOpen == _lastSyncedFindOpen &&
        ui.findOptionsVersion == _lastSyncedFindOptions) {
      return;
    }
    final closed = _lastSyncedFindOpen && !ui.findOpen;
    _lastSyncedFindQuery = ui.findQuery;
    _lastSyncedFindOpen = ui.findOpen;
    _lastSyncedFindOptions = ui.findOptionsVersion;
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
    if (_editor?.hayaletIste == _hayaletIsteyici) _editor?.hayaletIste = null;
    _hayaletZamanlayici?.cancel();
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
    // Temizlenmezse Ayarlar sekmesindeyken / tüm sekmeler kapalıyken Ctrl+D
    // yok edilmiş editörün denetleyicilerine dokunuyordu.
    if (_editor?.cokluImlec == _cokluImlecKomutu) {
      _editor?.cokluImlec = null;
    }
    if (_editor?.undo == _undo) {
      _editor?.undo = null;
      _editor?.redo = null;
      _editor?.kes = null;
      _editor?.kopyala = null;
      _editor?.yapistir = null;
      _editor?.tumunuSec = null;
    }

    _debounce?.cancel();
    _syntaxTimer?.cancel();
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

    super.dispose();
  }

  // ------------------------------------------------------------------
  // KATLAMA (FOLD)
  // ------------------------------------------------------------------
  String _foldPlaceholder(_Fold f) =>
      '${f.indent}${f.lineCount} satır katlandı';

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
    if (v == null) return;
    jumpToLineIn(_ctrl, v);
    // Gidilen satır görünümün ortasına getirilir: eskiden yalnızca görünür
    // olacak kadar kaydırılıyor, satır en kenarda (Kodi'nin balonu ya da
    // görünür alanın hemen dışında) kalabiliyordu. İmleç ortada olduğundan
    // editör ayrıca kaydırmaz.
    if (_textScroll.hasClients) {
      final pos = _textScroll.position;
      final lh = _lineHeight();
      final hedef = (v - 1) * lh + 8 + lh / 2 - pos.viewportDimension / 2;
      _textScroll.jumpTo(hedef.clamp(0.0, pos.maxScrollExtent).toDouble());
    }
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
        final gonderilen = fullText();
        final r = await backend.call('fold_bolgeleri', {'kod': gonderilen});
        // Komutlar backend'de paralel işlenir: eski isteğin geç gelen yanıtı
        // yeni bölgeleri bayat değerlerle ezmesin.
        if (!mounted || fullText() != gonderilen) return;
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

    // Hayalet kod: Tab kabul, Ctrl+→ kelime kelime kabul, Esc kapatır.
    // (Öneri listesi açıkken Tab listeye gider.)
    if (_hayalet != null && !_sugVisible) {
      final k = event.logicalKey;
      final hk = HardwareKeyboard.instance;
      if (k == LogicalKeyboardKey.tab && !hk.isShiftPressed && !hk.isControlPressed) {
        _hayaletKabul();
        return KeyEventResult.handled;
      }
      if (k == LogicalKeyboardKey.escape) {
        _hayaletKapat();
        return KeyEventResult.handled;
      }
      if (k == LogicalKeyboardKey.arrowRight && hk.isControlPressed && !hk.isShiftPressed) {
        _hayaletKabul(kelime: true);
        return KeyEventResult.handled;
      }
    }

    if (_ekImlecler.isNotEmpty &&
        event.logicalKey == LogicalKeyboardKey.escape &&
        !_sugVisible) {
      _ekImlecleriAyarla(const []);
      return KeyEventResult.handled;
    }

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
          _acceptSug(_suggestions[_selIndex]);
        }
        return KeyEventResult.handled;
      }

      // Parantez/tırnak tuşları öneri listesi açıkken de otomatik kapatma
      // ve kapanışın üzerinden geçme kuralına uyar: eskiden yazdır("x") yazınca
      // ("x" sonrası liste açıldığından) kapanış tırnağı yeni bir çift açıyor,
      // satır sonunda fazladan ") kalıyordu. Liste kapatılıp aşağıda işlenir.
      final c = event.character;
      if (c == null || !(_pairs.containsKey(c) || _pairs.containsValue(c))) {
        return KeyEventResult.ignored;
      }
      _hideSug();
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

    if ((event.logicalKey == LogicalKeyboardKey.enter ||
            event.logicalKey == LogicalKeyboardKey.numpadEnter) &&
        !ctrlPressed &&
        !shiftPressed &&
        !HardwareKeyboard.instance.isAltPressed &&
        _blokAcanSatirdaYeniSatir()) {
      return KeyEventResult.handled;
    }

    return KeyEventResult.ignored;
  }

  /// "eğer x:" / "için i içinde ...:" gibi blok açan satırda Enter: yeni satır
  /// bir seviye içeriden başlar (VS Code / Python davranışı). Eskiden yalnızca
  /// önceki girinti kopyalanıyor, gövde girintisiz kalıyor ve editör hemen
  /// "girintili blok bekleniyor" hatası gösteriyordu. Blok açmayan satırda
  /// false döner; Enter editörün varsayılan davranışına bırakılır.
  bool _blokAcanSatirdaYeniSatir() {
    final sel = _ctrl.selection;
    if (!sel.isValid || !sel.isCollapsed) return false;
    final yeni = blokAcanSatirdaYeniSatir(
        _ctrl.text, sel.baseOffset, _currentTabUnit);
    if (yeni == null) return false;
    _ctrl.runProgrammatic(() {
      _ctrl.value = yeni;
      _onChanged(_ctrl.text);
    });
    return true;
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
    // Satırlar çizilmeden önce (aynı karede) parantez eşi güncellenir.
    _parantezCiftiHesapla();
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
    await s.setValueBildir(context, 'yazi_boyutu', nv);
    if (mounted) setState(() {});
  }

  /// Tab / Shift+Tab girinti birimi: dosyada kullanılan birim (yoksa 4).
  /// Eskiden Tab her zaman 2 boşluk ekliyordu; Enter sonrası otomatik
  /// girinti ve katlama 4 boşluk (ya da dosyanın birimi) kullandığından
  /// aynı blokta karışık girinti (IndentationError) oluşuyordu.
  String? _tabUnitText;
  int _tabUnit = 4;
  /// Ayarlardaki girinti genişliği; "dosyadan algıla" açıksa dosyada
  /// girinti yoksa bu değer kullanılır.
  int get _ayarGirintisi {
    final s = context.read<SettingsProvider>();
    return s.getInt('girinti_boyutu', fallback: 4).clamp(2, 8).toInt();
  }

  int get _currentTabUnit {
    final t = _ctrl.text;
    final ayar = _ayarGirintisi;
    if (!context.read<SettingsProvider>().getBool('girinti_algila',
        fallback: true)) {
      return ayar;
    }
    if (!identical(t, _tabUnitText) || ayar != _tabUnitAyar) {
      _tabUnitText = t;
      _tabUnitAyar = ayar;
      _tabUnit = _EditorGuidePainter.detectIndentUnit(t.split('\n'),
              fallback: ayar)
          .clamp(2, 8)
          .toInt();
    }
    return _tabUnit;
  }

  int _tabUnitAyar = 4;

  /// Satır başındaki en fazla [unit] boşluğu (ya da bir sekme) siler; silinen
  /// karakter sayısı.
  static int _dedentCount(String line, int unit) {
    if (line.startsWith('\t')) return 1;
    var n = 0;
    while (n < unit && n < line.length && line.codeUnitAt(n) == 0x20) {
      n++;
    }
    return n;
  }

  void _indent(bool out) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final unit = _currentTabUnit;
    final pad = ' ' * unit;
    if (!sel.isValid || sel.isCollapsed) {
      if (out) {
        final ls = _lineStart(t, sel.baseOffset);
        final remove = _dedentCount(t.substring(ls, _lineEnd(t, ls)), unit);
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
        // İmleç sütunu bir sonraki girinti durağına tamamlanır.
        final col = sel.start - _lineStart(t, sel.start);
        final ekle = ' ' * (unit - col % unit);
        _ctrl.runProgrammatic(() {
          _ctrl.value = TextEditingValue(
            text: t.replaceRange(sel.start, sel.start, ekle),
            selection: TextSelection.collapsed(offset: sel.start + ekle.length),
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
        final n = _dedentCount(lines[i], unit);
        newLines.add(lines[i].substring(n));
        if (i == 0) delta -= n;
      } else {
        newLines.add('$pad${lines[i]}');
        if (i == 0) delta += unit;
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

    final a = ed.activeTab;
    // Başka bir sekmeye geçildi: bu editör bir sonraki karede yerini yeni
    // sekmenin editörüne bırakacak. Eskiden burada yeni sekmenin bekleyen
    // imleç konumu tüketiliyor (metni de boşuna yükleniyordu), yeni editör
    // null alıp imleci dosyanın başına koyuyordu.
    final benim = widget.sekmeYolu;
    if (benim != null && a != null && a.path != benim) return;
    final pendingCaret = ed.consumePendingCaret();

    if (a == null || ozelSekmeMi(a.path)) {
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
    // Çoklu imleç: düzenleme ek imleçlere uygulandıysa iç içe çağrılan
    // dinleyici geri kalan işleri zaten yaptı.
    if (_cokluDegisiklik()) return;

    final metinDegisti =
        _lastValidValue != null && _lastValidValue!.text != _ctrl.text;
    _lastValidValue = _ctrl.value;
    _syncReText();
    _hayaletDegisiklik(metinDegisti);

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
      _scheduleFoldRefresh();
    }
  }


  void _hayaletKapat() {
    _hayaletZamanlayici?.cancel();
    _hayaletNo++;
    if (_hayalet != null && mounted) setState(() => _hayalet = null);
  }

  /// Her metin/imleç değişikliğinde: öneriyi tüketir ya da kapatır, yazma
  /// sürüyorsa yeni öneri planlar.
  void _hayaletDegisiklik(bool metinDegisti) {
    if (_hayaletUygulaniyor) return;
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final imlec = sel.isValid && sel.isCollapsed ? sel.baseOffset : -1;
    final h = _hayalet;
    if (h != null) {
      final eski = _hayaletMetni;
      final eklenen = t.length - eski.length;
      if (metinDegisti &&
          eklenen > 0 &&
          _hayaletKonum >= 0 &&
          _hayaletKonum <= eski.length &&
          imlec == _hayaletKonum + eklenen &&
          t.startsWith(eski.substring(0, _hayaletKonum)) &&
          t.substring(imlec) == eski.substring(_hayaletKonum)) {
        final yazilan = t.substring(_hayaletKonum, imlec);
        if (h.startsWith(yazilan) && h.length > yazilan.length) {
          setState(() {
            _hayalet = h.substring(yazilan.length);
            _hayaletKonum = imlec;
            _hayaletMetni = t;
          });
          return;
        }
      } else if (!metinDegisti && imlec == _hayaletKonum && t == _hayaletMetni) {
        return;
      }
      setState(() => _hayalet = null);
    }
    if (metinDegisti) {
      // Yeni satıra geçildiyse (Enter) öneri hemen istenir.
      final yeniSatir = t.length > _hayaletOncekiUzunluk &&
          imlec > 0 &&
          t.substring(0, imlec).trimRight().length < imlec &&
          t.lastIndexOf('\n', imlec - 1) >= 0 &&
          t.substring(t.lastIndexOf('\n', imlec - 1) + 1, imlec).trim().isEmpty;
      _hayaletOncekiUzunluk = t.length;
      _hayaletPlanla(hemen: yeniSatir);
    } else {
      _hayaletZamanlayici?.cancel();
      _hayaletNo++;
    }
  }

  void _hayaletPlanla({bool zorla = false, bool hemen = false}) {
    _hayaletZamanlayici?.cancel();
    final s = context.read<SettingsProvider>();
    if (!s.aiTamamlamaHazir) return;
    final ms = zorla
        ? 0
        : hemen
            ? 60
            : s.getInt('ai_tamamlama_gecikme', fallback: 300).clamp(80, 3000);
    _hayaletZamanlayici =
        Timer(Duration(milliseconds: ms), () => _hayaletIste(zorla: zorla));
  }

  Future<void> _hayaletIste({bool zorla = false}) async {
    if (!mounted) return;
    if (!zorla && !_focus.hasFocus) return;
    if (_ekImlecler.isNotEmpty || _folds.isNotEmpty) return;
    final sel = _ctrl.selection;
    if (!sel.isValid || !sel.isCollapsed) return;
    final backend = _backend;
    if (backend == null || !backend.isConnected) return;
    // Aynı anda tek istek: yerel model istekleri sıraya girer; yazma
    // sürerken biriken istekler yerine en son durum için bir istek gider.
    if (_hayaletSuruyor) {
      _hayaletBekleyen = true;
      return;
    }
    final t = _ctrl.text;
    final imlec = sel.baseOffset.clamp(0, t.length);
    final no = ++_hayaletNo;
    if (zorla) _ui?.flashStatus('✨ AI önerisi hazırlanıyor…');
    _hayaletSuruyor = true;
    try {
      final r = await backend.call('ai_hayalet_tamamla', {
        'once': t.substring(math.max(0, imlec - 6000), imlec),
        'sonra': t.substring(imlec, math.min(t.length, imlec + 2000)),
        'dosya': context.read<EditorProvider>().activeTab?.name,
        'zorla': zorla,
      });
      if (!mounted || no != _hayaletNo) return;
      // Bu arada yazıldıysa ya da imleç kaydıysa öneri eskimiştir.
      if (_ctrl.text != t || _ctrl.selection.baseOffset != imlec) return;
      final oneri = r['oneri']?.toString() ?? '';
      if (oneri.isEmpty) {
        if (zorla) _ui?.flashStatus('AI bir öneri üretmedi');
        return;
      }
      setState(() {
        _hayalet = oneri;
        _hayaletKonum = imlec;
        _hayaletMetni = t;
      });
    } catch (e) {
      if (zorla && mounted) {
        showAppSnackbar(context, 'AI önerisi: $e', kind: SnackKind.error);
      }
    } finally {
      _hayaletSuruyor = false;
      if (_hayaletBekleyen && mounted) {
        _hayaletBekleyen = false;
        _hayaletPlanla();
      }
    }
  }

  static final RegExp _hayaletKelime =
      RegExp(r'^(\s*[A-Za-z0-9_ÇŞĞÜÖİçşğüöı]+|\s*[^\sA-Za-z0-9_ÇŞĞÜÖİçşğüöı]+|\s+)');

  /// Öneriyi (ya da Ctrl+→ ile yalnızca sonraki kelimeyi) imlece yazar.
  void _hayaletKabul({bool kelime = false}) {
    final h = _hayalet;
    if (h == null) return;
    final t = _ctrl.text;
    final pos = _hayaletKonum;
    if (pos < 0 || pos > t.length || t != _hayaletMetni) {
      _hayaletKapat();
      return;
    }
    final ek = kelime ? (_hayaletKelime.firstMatch(h)?.group(0) ?? h) : h;
    final kalan = h.substring(ek.length);
    final nt = t.replaceRange(pos, pos, ek);
    _hayaletUygulaniyor = true;
    try {
      _ctrl.runProgrammatic(() {
        _ctrl.value = TextEditingValue(
            text: nt, selection: TextSelection.collapsed(offset: pos + ek.length));
        _onChanged(nt);
      });
      _syncReText();
    } finally {
      _hayaletUygulaniyor = false;
    }
    setState(() {
      if (kalan.isEmpty) {
        _hayalet = null;
      } else {
        _hayalet = kalan;
        _hayaletKonum = pos + ek.length;
        _hayaletMetni = nt;
      }
    });
    _focus.requestFocus();
    // Tümü kabul edilince yazmaya devam ediliyormuş gibi sıradaki öneri istenir.
    if (kalan.isEmpty) _hayaletPlanla();
  }

  Widget _hayaletKatmani(ThemeData theme) {
    final t = _ctrl.text;
    final konum = _hayaletKonum.clamp(0, t.length);
    final satirBasi = konum == 0 ? 0 : t.lastIndexOf('\n', konum - 1) + 1;
    final satirSonuIdx = t.indexOf('\n', konum);
    var satir = 0;
    for (var i = 0; i < satirBasi; i++) {
      if (t.codeUnitAt(i) == 10) satir++;
    }
    return Positioned.fill(
      child: IgnorePointer(
        child: CustomPaint(
          painter: _HayaletPainter(
            bridge: _paragraphs,
            indicatorKey: _indicatorKey,
            satir: satir,
            sutun: konum - satirBasi,
            metin: _hayalet!,
            satirSonu: t.substring(konum, satirSonuIdx < 0 ? t.length : satirSonuIdx),
            stil: _style().copyWith(
                height: 1.4,
                fontStyle: FontStyle.italic,
                color: theme.colorScheme.onSurface.withOpacity(0.42)),
            normalRenk: theme.colorScheme.onSurface,
            zemin: theme.colorScheme.surface,
            ipucuRengi: theme.colorScheme.primary.withOpacity(0.75),
          ),
        ),
      ),
    );
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
  void _setErrorLine(int? line) {
    if (!mounted || line == _errorModelLine) return;
    setState(() => _errorModelLine = line != null && line > 0 ? line : null);
  }

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
    final word = match?.group(0) ?? '';
    // Kelimeden önceki satır parçası: 'liste.' ile bitiyorsa nesnenin
    // metotları istenir; bu durumda henüz harf yazılmamış olabilir.
    final once = before.substring(
        before.lastIndexOf('\n') + 1, before.length - word.length);
    final uyeErisimi = RegExp(r'[A-Za-z0-9_ÇŞĞÜÖİçşğüöı)\]]\.$').hasMatch(once);
    if (!uyeErisimi && word.length < 2) return _hideSug();
    final reqId = ++_reqId;
    try {
      final r = await backend.call('tamamlama_onerileri', {
        'kelime': word,
        'kod': _contextWindow(),
        'once': once,
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
              items.add({
                'icon': m['ikon']?.toString() ?? '•',
                'label': k,
                if (m['sablon'] is String) 'sablon': m['sablon'] as String,
              });
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

  void _acceptSug(Map<String, String> oneri) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    final cur = sel.isValid ? sel.baseOffset.clamp(0, t.length) : t.length;
    final before = t.substring(0, cur);
    final after = t.substring(cur);
    final match = _wordPattern.firstMatch(before);
    // Nokta sonrası öneride henüz harf yazılmamış olabilir: imleçte ekle.
    final start = match?.start ?? cur;
    var w = oneri['ham'] ?? oneri['label']!;
    var imlec = w.length;
    final sablon = oneri['sablon'];
    if (sablon != null && oneri['ham'] == null) {
      // Kod şablonu: "\t" bir girinti düzeyi; alt satırlar bulunulan satırın
      // girintisiyle başlar; imleç "$0" işaretinin yerine konur.
      final satirBasi = before.lastIndexOf('\n') + 1;
      final girinti =
          RegExp(r'^[ \t]*').firstMatch(before.substring(satirBasi))!.group(0)!;
      final birim = ' ' * _currentTabUnit;
      w = sablon
          .replaceAll('\t', birim)
          .replaceAll('\n', '\n$girinti');
      imlec = w.indexOf(r'$0');
      if (imlec < 0) {
        imlec = w.length;
      } else {
        w = w.replaceFirst(r'$0', '');
      }
    }
    final nt = before.substring(0, start) + w + after;
    _ctrl.runProgrammatic(() {
      _ctrl.value = TextEditingValue(
        text: nt,
        selection: TextSelection.collapsed(offset: start + imlec),
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
        _setErrorLine(null);
        ui.setSyntaxStatus('');
        _sorunlariAyarla(const []);
        return;
      }
      try {
        final w = _contextWindowWithOffset();
        final r = await backend.call('syntax_kontrol', {'kod': w.text});
        // Yanıt gelene kadar sekme değişmiş (editör yeniden kuruldu) ya da
        // metin düzenlenmiş olabilir: bayat sonuç Sorunlar listesini ve durum
        // çubuğunu ezmesin (yeni metin için zaten yeni denetim zamanlandı).
        if (!mounted || fullText() != kod) return;
        final hatalar = r['hatalar'];
        final uyarilar = r['uyarilar'];
        Sorun? sorun(Object? h, bool hata) {
          if (h is! Map) return null;
          final satir = h['satir'];
          if (satir is! num) return null;
          final sutun = h['sutun'];
          return Sorun(
            satir: satir.toInt() + w.lineOffset,
            sutun: sutun is num ? sutun.toInt() : null,
            ad: hata ? null : h['ad']?.toString(),
            hata: hata,
            mesaj: _satirliMesaj(h, w.lineOffset),
          );
        }

        _sorunlariAyarla([
          if (hatalar is List) ...hatalar.map((h) => sorun(h, true)).nonNulls,
          if (uyarilar is List && r['basarili'] == true)
            ...uyarilar.map((u) => sorun(u, false)).nonNulls,
        ]);
        if (r['basarili'] != true) {
          if (hatalar is List && hatalar.isNotEmpty) {
            final ilk = hatalar.first;
            final satir = ilk is Map ? ilk['satir'] : null;
            _setErrorLine(
                satir is num ? satir.toInt() + w.lineOffset : null);
            ui.setSyntaxStatus(_satirliMesaj(hatalar.first, w.lineOffset),
                tooltip: hatalar
                    .map((h) => _satirliMesaj(h, w.lineOffset))
                    .join('\n'));
          } else if (r['ok'] == false) {
            // Denetim backend'de çalışamadı (kod hatası değil): yanıltıcı bir
            // "Sözdizimi hatası" yazmak yerine durumu boş bırak.
            _setErrorLine(null);
            ui.setSyntaxStatus('');
          } else {
            ui.setSyntaxStatus('Sözdizimi hatası');
          }
        } else if (uyarilar is List && uyarilar.isNotEmpty) {
          _setErrorLine(null);
          // TürKod komutu ad olarak kullanılmış (ör. "toplam = 0"): kod
          // geçerli ama o komut bu dosyada çalışmaz -> uyarı.
          final ilk = _satirliMesaj(uyarilar.first, w.lineOffset);
          final ek = uyarilar.length > 1 ? ' (+${uyarilar.length - 1})' : '';
          ui.setSyntaxStatus('⚠ $ilk$ek',
              tooltip: uyarilar
                  .map((u) => '⚠ ${_satirliMesaj(u, w.lineOffset)}')
                  .join('\n'));
        } else {
          _setErrorLine(null);
          ui.setSyntaxStatus('✓ Sözdizimi doğru');
        }
      } catch (_) {
        ui.setSyntaxStatus('');
      }
    });
  }

  // ------------------------------------------------------ çoklu imleç
  /// Birincil imleç dışındaki imleçler / seçimler (görünüm metninde).
  List<TextSelection> _ekImlecler = const [];
  TextEditingValue? _cokluOnceki;
  bool _cokluUyguluyor = false;
  bool _altTiklama = false;

  void _ekImlecleriAyarla(List<TextSelection> liste) {
    if (listEquals(liste, _ekImlecler)) return;
    if (mounted) setState(() => _ekImlecler = liste);
  }

  /// _onControllerChange başında çağrılır: birincil imleçteki düzenleme ek
  /// imleçlere yansıtılır. Düzenleme uygulandıysa true döner.
  bool _cokluDegisiklik() {
    final onceki = _cokluOnceki;
    _cokluOnceki = _ctrl.value;
    if (_ekImlecler.isEmpty || _cokluUyguluyor || onceki == null) return false;
    if (onceki.text == _ctrl.text) {
      // Salt imleç hareketi (tıklama, ok tuşu): Alt+Tık değilse ek imleçler
      // bırakılır (VS Code'daki gibi Esc'e gerek kalmadan).
      if (onceki.selection != _ctrl.selection) {
        if (_altTiklama) {
          _altTiklama = false;
        } else {
          _ekImlecleriAyarla(const []);
        }
      }
      return false;
    }
    final sonuc = cokluDuzenle(onceki.text, onceki.selection, _ctrl.text,
        _ctrl.selection, _ekImlecler);
    if (sonuc == null) {
      _ekImlecleriAyarla(const []);
      return false;
    }
    _cokluUyguluyor = true;
    try {
      _ekImlecler = sonuc.ekler;
      _ctrl.runProgrammatic(() {
        _ctrl.value =
            TextEditingValue(text: sonuc.metin, selection: sonuc.birincil);
        _onChanged(_ctrl.text);
      });
      _syncReText();
    } finally {
      _cokluUyguluyor = false;
    }
    if (mounted) setState(() {});
    return true;
  }

  void _cokluSecimUygula(TextSelection birincil, List<TextSelection> ekler) {
    _cokluUyguluyor = true;
    try {
      _ekImlecler = ekler;
      _ctrl.runProgrammatic(() {
        _ctrl.value = _ctrl.value.copyWith(selection: birincil);
      });
      _syncReText();
      _cokluOnceki = _ctrl.value;
    } finally {
      _cokluUyguluyor = false;
    }
    if (mounted) setState(() {});
    _focus.requestFocus();
  }

  void _cokluImlecKomutu(String komut) {
    final t = _ctrl.text;
    final sel = _ctrl.selection;
    if (!sel.isValid) return;
    switch (komut) {
      case 'temizle':
        _ekImlecleriAyarla(const []);
        return;
      case 'asagi':
      case 'yukari':
        // Aynı sütunda bir alt / üst satıra imleç eklenir.
        final c = sel.extentOffset;
        final satirBasi = _lineStart(t, c);
        final sutun = c - satirBasi;
        int hedefBasi;
        if (komut == 'asagi') {
          final satirSonu = _lineEnd(t, c);
          if (satirSonu >= t.length) return;
          hedefBasi = satirSonu + 1;
        } else {
          if (satirBasi == 0) return;
          hedefBasi = _lineStart(t, satirBasi - 1);
        }
        final hedefSonu = _lineEnd(t, hedefBasi);
        final yeni = TextSelection.collapsed(
            offset: math.min(hedefBasi + sutun, hedefSonu));
        _cokluSecimUygula(yeni, [..._ekImlecler, TextSelection.collapsed(offset: c)]);
        return;
      case 'sonraki':
      case 'tumu':
        // Seçili metin (yoksa imleçteki kelime) seçilir; 'sonraki' bir
        // sonraki geçişi, 'tumu' bütün geçişleri seçime ekler.
        var aranan = sel.isCollapsed ? '' : t.substring(sel.start, sel.end);
        var mevcut = sel;
        if (aranan.isEmpty) {
          final harf = RegExp(r'[A-Za-z0-9_ÇŞĞÜÖİçşğüöı]');
          var b = sel.baseOffset, e = sel.baseOffset;
          while (b > 0 && harf.hasMatch(t[b - 1])) {
            b--;
          }
          while (e < t.length && harf.hasMatch(t[e])) {
            e++;
          }
          if (e <= b) return;
          aranan = t.substring(b, e);
          mevcut = TextSelection(baseOffset: b, extentOffset: e);
          if (komut == 'sonraki') {
            _cokluSecimUygula(mevcut, _ekImlecler);
            return;
          }
        }
        final konumlar = <int>[];
        for (var i = t.indexOf(aranan); i >= 0; i = t.indexOf(aranan, i + 1)) {
          konumlar.add(i);
        }
        if (konumlar.length < 2) return;
        TextSelection secim(int i) =>
            TextSelection(baseOffset: i, extentOffset: i + aranan.length);
        if (komut == 'tumu') {
          _cokluSecimUygula(mevcut, [
            for (final i in konumlar)
              if (i != mevcut.start) secim(i)
          ]);
          return;
        }
        final alinan = {mevcut.start, for (final x in _ekImlecler) x.start};
        int? sonraki;
        for (final i in [...konumlar.where((i) => i > mevcut.start), ...konumlar]) {
          if (!alinan.contains(i)) {
            sonraki = i;
            break;
          }
        }
        if (sonraki == null) return;
        _cokluSecimUygula(secim(sonraki), [..._ekImlecler, mevcut]);
        return;
    }
  }

  List<(int, int, int, int)> _ekImlecSatirlari() {
    final t = _ctrl.text;
    return [
      for (final s in _ekImlecler)
        if (s.isValid && s.end <= t.length)
          () {
            final b = _toCodePos(t, s.start);
            final e = _toCodePos(t, s.end);
            return (b.baseIndex, b.baseOffset, e.baseIndex, e.baseOffset);
          }(),
    ];
  }

  /// Dalgalı çizgiler: sözdizimi denetiminin bulduğu hata / uyarılar.
  List<Sorun> _sorunlar = const [];

  void _sorunlariAyarla(List<Sorun> liste) {
    _ui?.setSorunlar(liste);
    if (listEquals(liste, _sorunlar)) return;
    _sorunlar = liste;
    // Görünen satırların yeniden çizilmesi için zararsız dürtme.
    if (mounted) _reCtrl.selection = _reCtrl.selection;
  }

  /// Görünüm satırındaki sorun aralıklarına dalgalı alt çizgi ekler.
  List<InlineSpan> _sorunCizgileri(
      List<InlineSpan> spans, int gorunumSatiri, String metin) {
    if (_sorunlar.isEmpty) return spans;
    final model = _viewToModelLine(gorunumSatiri + 1);
    if (model == null) return spans;
    final hataAraliklari = <List<int>>[];
    final uyariAraliklari = <List<int>>[];
    for (final s in _sorunlar) {
      if (s.satir != model) continue;
      (s.hata ? hataAraliklari : uyariAraliklari).addAll(s.araliklar(metin));
    }
    if (hataAraliklari.isEmpty && uyariAraliklari.isEmpty) return spans;
    final sonuc = <InlineSpan>[];
    var pos = 0;
    for (final sp in spans) {
      final t = sp is TextSpan ? sp.text : null;
      if (sp is! TextSpan || t == null || t.isEmpty) {
        sonuc.add(sp);
        continue;
      }
      final kesimler = <int>{0, t.length};
      for (final a in [...hataAraliklari, ...uyariAraliklari]) {
        if (a[0] > pos && a[0] < pos + t.length) kesimler.add(a[0] - pos);
        if (a[1] > pos && a[1] < pos + t.length) kesimler.add(a[1] - pos);
      }
      final sirali = kesimler.toList()..sort();
      for (var k = 0; k < sirali.length - 1; k++) {
        final bas = pos + sirali[k];
        final bit = pos + sirali[k + 1];
        bool icinde(List<List<int>> l) =>
            l.any((a) => bas >= a[0] && bit <= a[1]);
        final renk = icinde(hataAraliklari)
            ? Colors.redAccent
            : icinde(uyariAraliklari)
                ? Colors.orange
                : null;
        final stil = renk == null
            ? sp.style
            : (sp.style ?? const TextStyle()).copyWith(
                decoration: TextDecoration.underline,
                decorationStyle: TextDecorationStyle.wavy,
                decorationColor: renk,
              );
        sonuc.add(TextSpan(
            text: t.substring(sirali[k], sirali[k + 1]), style: stil));
      }
      pos += t.length;
    }
    return sonuc;
  }

  // ------------------------------------------------ üzerine gelince açıklama
  Timer? _ipucuZamanlayici;
  Offset? _ipucuKonumu;
  String? _ipucuKelimesi;
  String? _ipucuBaslik;
  String? _ipucuAciklama;
  int _ipucuIstek = 0;

  void _ipucunuGizle() {
    _ipucuZamanlayici?.cancel();
    _ipucuIstek++;
    if (_ipucuBaslik != null || _ipucuKelimesi != null) {
      setState(() {
        _ipucuBaslik = null;
        _ipucuAciklama = null;
        _ipucuKelimesi = null;
      });
    }
  }

  /// Fare konumundaki kelime (yoksa null). Konumlar re_editor'ın gerçekte
  /// çizdiği satır paragraflarından alınır.
  String? _konumdakiKelime(Offset yerel) {
    final paragraphs = _paragraphs.value?.paragraphs;
    if (paragraphs == null) return null;
    final box = _indicatorKey.currentContext?.findRenderObject();
    final left = box is RenderBox && box.hasSize ? box.size.width : 0.0;
    for (final p in paragraphs) {
      if (yerel.dy < p.top || yerel.dy >= p.bottom) continue;
      if (p.index < 0 || p.index >= _reCtrl.codeLines.length) return null;
      final x = yerel.dx - left - p.offset.dx;
      if (x < 0 || x > p.paragraph.width) return null;
      final metin = _reCtrl.codeLines[p.index].text;
      final konum = p.paragraph.getPosition(Offset(x, yerel.dy - p.top)).offset;
      final harf = RegExp(r'[A-Za-z0-9_ÇŞĞÜÖİçşğüöı]');
      var bas = konum.clamp(0, metin.length).toInt();
      var bit = bas;
      while (bas > 0 && harf.hasMatch(metin[bas - 1])) {
        bas--;
      }
      while (bit < metin.length && harf.hasMatch(metin[bit])) {
        bit++;
      }
      if (bit <= bas || RegExp(r'^\d').hasMatch(metin.substring(bas, bit))) {
        return null;
      }
      return metin.substring(bas, bit);
    }
    return null;
  }

  void _ipucuFareHareketi(Offset yerel) {
    final kelime = _konumdakiKelime(yerel);
    if (kelime == _ipucuKelimesi && _ipucuBaslik != null) return;
    _ipucuZamanlayici?.cancel();
    if (_ipucuBaslik != null) _ipucunuGizle();
    if (kelime == null) return;
    _ipucuZamanlayici = Timer(const Duration(milliseconds: 650), () async {
      final backend = _backend;
      if (!mounted || backend == null || !backend.isConnected) return;
      final istek = ++_ipucuIstek;
      try {
        final r = await backend.call('kelime_aciklamasi',
            {'kelime': kelime, 'kod': _contextWindow()});
        if (!mounted || istek != _ipucuIstek) return;
        final baslik = r['baslik']?.toString();
        if (baslik == null || baslik.isEmpty) return;
        setState(() {
          _ipucuKelimesi = kelime;
          _ipucuKonumu = yerel;
          _ipucuBaslik = baslik;
          _ipucuAciklama = r['aciklama']?.toString();
        });
      } catch (_) {}
    });
  }

  Widget _ipucuKutusu(ThemeData theme) {
    final konum = _ipucuKonumu ?? Offset.zero;
    final maxLeft = math.max(0.0, _vpSize.width - 380);
    return Positioned(
      left: (konum.dx + 8).clamp(0.0, maxLeft).toDouble(),
      top: konum.dy + 18,
      child: IgnorePointer(
        child: Material(
          elevation: 6,
          borderRadius: BorderRadius.circular(6),
          color: theme.colorScheme.surfaceContainerHigh,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_ipucuBaslik ?? '',
                      style: const TextStyle(
                          fontFamily: 'Consolas',
                          fontWeight: FontWeight.bold,
                          fontSize: 12)),
                  if ((_ipucuAciklama ?? '').isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(_ipucuAciklama!, style: const TextStyle(fontSize: 12)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
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
    _palet = theme.extension<AppSyntaxPalette>() ?? AppSyntaxPalette.fallback;
    context.watch<LanguageProvider>();
    _builtText = _ctrl.text;
    if (active == null || ozelSekmeMi(active.path)) {
      return Container(color: theme.colorScheme.surface);
    }
    final style = _style();
    final viewBreakpoints = _modelSetToView(bp.breakpointsFor(active.id));
    final viewConditional =
        _modelSetToView(bp.conditionsFor(active.id).keys.toSet());
    final viewErrorLine = _errorModelLine == null
        ? null
        : _modelToViewLine(_errorModelLine!);
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
    // Hayalet kod da satır konumlarını kullanır (satır numaraları kapalıyken bile).
    final needsIndicator =
        showLineNumbers || showGuides || showWhitespace || _hayalet != null;
    if (showGuides) _indentUnit = _currentTabUnit;
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
                            // Sağ tık: koşullu breakpoint.
                            onSecondaryTapUp: (details) {
                              final paragraphs = notifier.value?.paragraphs;
                              if (paragraphs == null) return;
                              final y = details.localPosition.dy;
                              for (final paragraph in paragraphs) {
                                if (y >= paragraph.top && y < paragraph.bottom) {
                                  final model =
                                      _viewToModelLine(paragraph.index + 1);
                                  if (model != null) {
                                    showBreakpointConditionDialog(
                                        context, active.id, model);
                                  }
                                  return;
                                }
                              }
                            },
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
                                        conditional: viewConditional,
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
                  Positioned.fill(
                    child: Listener(
                      // Alt+Tık: önceki imleç yerinde kalır, tıklanan yere
                      // yeni (birincil) imleç gelir.
                      onPointerDown: (e) {
                        if (e.buttons == kPrimaryMouseButton &&
                            HardwareKeyboard.instance.isAltPressed &&
                            _ctrl.selection.isValid) {
                          final onceki = _ctrl.selection;
                          if (!_ekImlecler.contains(onceki)) {
                            _ekImlecler = [..._ekImlecler, onceki];
                          }
                          _altTiklama = true;
                          setState(() {});
                        }
                      },
                      child: MouseRegion(
                        onHover: wrapEnabled
                            ? null
                            : (e) => _ipucuFareHareketi(e.localPosition),
                        onExit: (_) => _ipucunuGizle(),
                        child: editorSurface,
                      ),
                    ),
                  ),
                  if (_ekImlecler.isNotEmpty)
                    Positioned.fill(
                      child: IgnorePointer(
                        child: CustomPaint(
                          painter: _EkImlecPainter(
                              _paragraphs,
                              _indicatorKey,
                              _ekImlecSatirlari(),
                              theme.colorScheme.primary),
                        ),
                      ),
                    ),
                  if (_hayalet != null && !_sugVisible && needsIndicator)
                    _hayaletKatmani(theme),
                  if (_ipucuBaslik != null) _ipucuKutusu(theme),
                  if (viewErrorLine != null &&
                      viewErrorLine != viewPausedLine &&
                      needsIndicator)
                    Positioned.fill(
                      child: IgnorePointer(
                        child: CustomPaint(
                          painter: _DebugLinePainter(
                            bridge: _paragraphs,
                            line: viewErrorLine,
                            color: Colors.redAccent.withOpacity(0.13),
                          ),
                        ),
                      ),
                    ),
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
                                  onTap: () => _acceptSug(it),
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
  final TextEditingController _expr = TextEditingController();
  String? _evalText;
  bool _evalError = false;

  static const Map<String, String> _reasons = {
    'breakpoint': 'Kesme noktası',
    'adim': 'Adım',
    'baslangic': 'Başlangıç',
    'duraklat': 'Duraklatıldı',
    'hata': 'Yakalanmamış hata',
  };

  @override
  void dispose() {
    _expr.dispose();
    super.dispose();
  }

  Future<void> _evaluate(BreakpointProvider bp) async {
    final ifade = _expr.text.trim();
    if (ifade.isEmpty) return;
    final (deger, hata) = await bp.evaluate(ifade);
    if (!mounted) return;
    setState(() {
      _evalError = hata != null;
      _evalText = hata != null ? hata : '$ifade = $deger';
    });
  }

  void _addWatch(BreakpointProvider bp) {
    final ifade = _expr.text.trim();
    if (ifade.isEmpty) return;
    bp.addWatch(ifade);
    _expr.clear();
  }

  Widget _watchTile(ThemeData theme, BreakpointProvider bp, DebugWatch w) {
    final mono = TextStyle(
      fontFamily: kMonoFontFamily,
      fontFamilyFallback: kMonoFontFallback,
      fontSize: 11.5,
      color: theme.colorScheme.onSurface,
    );
    return Padding(
      padding: const EdgeInsets.only(left: 20, right: 2),
      child: Row(children: [
        Expanded(
          child: Text.rich(
            TextSpan(children: [
              TextSpan(
                  text: w.expr,
                  style: mono.copyWith(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.w600)),
              TextSpan(text: ' = ', style: mono),
              TextSpan(
                  text: w.error ?? w.value ?? '…',
                  style: w.error != null
                      ? mono.copyWith(color: theme.colorScheme.error)
                      : mono),
            ]),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        _btn(Icons.close, 'İzlemeden kaldır',
            theme.colorScheme.onSurface.withOpacity(0.6),
            () => bp.removeWatch(w.expr)),
      ]),
    );
  }

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
            if (depth == 0 && context.read<BreakpointProvider>().paused)
              InkWell(
                onTap: () => _degeriDegistir(v),
                child: Tooltip(
                  message: 'Değeri değiştir',
                  child: Padding(
                    padding: const EdgeInsets.only(left: 4),
                    child: Icon(Icons.edit_outlined,
                        size: 12,
                        color: theme.colorScheme.onSurface.withValues(alpha: 0.6)),
                  ),
                ),
              ),
          ]),
        ),
      ),
      if (open)
        for (final c in v.children) _varTile(theme, c, key, depth + 1),
    ]);
  }

  Future<void> _degeriDegistir(DebugVar v) async {
    final yeni = await showDialog<String>(
      context: context,
      builder: (_) => MetinGirisDialog(
        baslik: "'${v.name}' değişkenine yeni değer",
        baslangic: v.value,
        ipucu: 'TürKod ifadesi: 42, "metin", Doğru, [1, 2], sayaç + 1',
        dugme: 'Değiştir',
        esGenislik: true,
      ),
    );
    if (yeni == null || yeni.trim().isEmpty || !mounted) return;
    final hata =
        await context.read<BreakpointProvider>().setVariable(v.name, yeni);
    if (!mounted) return;
    showAppSnackbar(context, hata ?? "'${v.name}' güncellendi",
        kind: hata == null ? SnackKind.success : SnackKind.error);
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
              _btn(Icons.play_arrow, kisayolluIpucu('Devam', 'run.debug_start'), const Color(0xFF9CCC65),
                  paused ? () => wrap(bp.continueRun) : null),
              _btn(Icons.pause, kisayolluIpucu('Duraklat', 'run.debug_pause'), const Color(0xFFFFCA28),
                  !paused && !bp.starting ? () => wrap(bp.pause) : null),
              _btn(Icons.redo, kisayolluIpucu('Adım At', 'run.debug_step'), const Color(0xFF42A5F5),
                  paused ? () => wrap(bp.step) : null),
              _btn(Icons.subdirectory_arrow_right, kisayolluIpucu('İçine Gir', 'run.debug_step_into'),
                  const Color(0xFF26C6DA), paused ? () => wrap(bp.stepInto) : null),
              _btn(Icons.subdirectory_arrow_left, kisayolluIpucu('Dışına Çık', 'run.debug_step_out'),
                  const Color(0xFF7E57C2), paused ? () => wrap(bp.stepOut) : null),
              _btn(Icons.stop, kisayolluIpucu('Durdur', 'run.debug_stop'), const Color(0xFFEF5350),
                  () => wrap(bp.stop)),
            ]),
          ),
          if (_expanded && paused) ...[
            const Divider(height: 1),
            if (bp.stopError != null)
              Container(
                width: double.infinity,
                color: theme.colorScheme.errorContainer,
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 4),
                child: Text(
                  '${bp.stopError!}\nDeğişkenleri incele; Devam / Durdur '
                  'programı bitirir.',
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onErrorContainer),
                ),
              ),
            // İfade değerlendirme / izlemeye ekleme.
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 2, 0),
              child: Row(children: [
                Expanded(
                  child: TextField(
                    controller: _expr,
                    style: const TextStyle(
                        fontFamily: kMonoFontFamily, fontSize: 12),
                    decoration: const InputDecoration(
                      isDense: true,
                      hintText: 'İfade (Enter: değerlendir)',
                      border: InputBorder.none,
                    ),
                    onSubmitted: (_) => _evaluate(bp),
                  ),
                ),
                _btn(Icons.play_circle_outline, 'Değerlendir',
                    theme.colorScheme.primary, () => _evaluate(bp)),
                _btn(Icons.visibility_outlined, 'İzlemeye ekle',
                    theme.colorScheme.primary, () => _addWatch(bp)),
              ]),
            ),
            if (_evalText != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 0, 8, 4),
                child: SelectableText(
                  _evalText!,
                  maxLines: 4,
                  style: TextStyle(
                    fontFamily: kMonoFontFamily,
                    fontSize: 11.5,
                    color: _evalError
                        ? theme.colorScheme.error
                        : theme.colorScheme.onSurface,
                  ),
                ),
              ),
            const Divider(height: 1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 300),
              child: SingleChildScrollView(
                padding: const EdgeInsets.only(bottom: 6),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (bp.watches.isNotEmpty)
                    _section(theme, 'İZLEME', [
                      for (final w in bp.watches) _watchTile(theme, bp, w),
                    ]),
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
                    _section(theme, 'ÇAĞRI YIĞINI (değişkenleri için tıklayın)', [
                      for (var i = 0; i < bp.stack.length; i++)
                        InkWell(
                          onTap: () => bp.selectFrame(i),
                          child: Container(
                            width: double.infinity,
                            color: i == bp.selectedFrame
                                ? theme.colorScheme.primary.withOpacity(0.12)
                                : null,
                            padding: const EdgeInsets.fromLTRB(20, 2, 8, 2),
                            child: Text(
                                '${bp.stack[i].function}  •  satır ${bp.stack[i].line}',
                                style: theme.textTheme.bodySmall?.copyWith(
                                    fontWeight: i == bp.selectedFrame
                                        ? FontWeight.w700
                                        : null)),
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

/// Terminal çıktı listesinin iç boşluğu (sağdaki 14: kaydırma çubuğu).
const EdgeInsets kTerminalCiktiBoslugu =
    EdgeInsets.only(left: 8, right: 14, top: 4, bottom: 4);

/// [alan] piksel boyutundaki terminal görünümüne [stil] yazısıyla kaç sütun ×
/// kaç satır sığar? Eş aralıklı yazı tipinde bir hücre 'M' harfiyle ölçülür.
(int, int) terminalKarakterBoyutu(Size alan, TextStyle stil,
    {TextScaler textScaler = TextScaler.noScaling,
    EdgeInsets bosluk = kTerminalCiktiBoslugu}) {
  final tp = TextPainter(
    text: TextSpan(text: 'MMMMMMMMMM', style: stil),
    textDirection: TextDirection.ltr,
    textScaler: textScaler,
    maxLines: 1,
  )..layout();
  final hucreG = tp.width / 10;
  final hucreY = tp.height;
  tp.dispose();
  if (hucreG <= 0 || hucreY <= 0) return (0, 0);
  final g = alan.width - bosluk.horizontal;
  final y = alan.height - bosluk.vertical;
  return (math.max(0, g ~/ hucreG), math.max(0, y ~/ hucreY));
}

class _TerminalPanelState extends State<TerminalPanel> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  late final FocusNode _inputFocus =
      FocusNode(debugLabel: 'terminal-girdi', onKeyEvent: _onInputKey);
  int _seenFocusTick = -1;

  /// Geçmişte gezilen konum (null: geçmişte değil, yazılan satırda).
  int? _historyPos;
  String _draft = '';

  void _setInput(String v) {
    _input.value = TextEditingValue(
        text: v, selection: TextSelection.collapsed(offset: v.length));
  }

  /// Yukarı / Aşağı: önceki komutlar; Ctrl+C (seçim yokken): çalışan
  /// programı durdurur.
  KeyEventResult _onInputKey(FocusNode node, KeyEvent e) {
    if (e is! KeyDownEvent && e is! KeyRepeatEvent) return KeyEventResult.ignored;
    final term = context.read<TerminalProvider>();
    final h = term.history;
    final k = e.logicalKey;
    if (k == LogicalKeyboardKey.arrowUp && h.isNotEmpty) {
      if (_historyPos == null) {
        _draft = _input.text;
        _historyPos = h.length - 1;
      } else if (_historyPos! > 0) {
        _historyPos = _historyPos! - 1;
      }
      _setInput(h[_historyPos!]);
      return KeyEventResult.handled;
    }
    if (k == LogicalKeyboardKey.arrowDown && _historyPos != null) {
      if (_historyPos! < h.length - 1) {
        _historyPos = _historyPos! + 1;
        _setInput(h[_historyPos!]);
      } else {
        _historyPos = null;
        _setInput(_draft);
      }
      return KeyEventResult.handled;
    }
    if (k == LogicalKeyboardKey.keyC &&
        HardwareKeyboard.instance.isControlPressed &&
        _input.selection.isCollapsed &&
        term.isRunning) {
      term.stop();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  void dispose() {
    _boyutTimer?.cancel();
    _input.dispose();
    _scroll.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  // Görünen boyut (karakter) değişince ~200 ms sonra backend'e bildirilir
  // (panel sürüklenirken her karede istek gitmesin).
  Timer? _boyutTimer;
  (int, int)? _olculenBoyut;

  void _boyutuOlc(Size alan, TextStyle stil, TextScaler olcek) {
    if (!alan.width.isFinite || !alan.height.isFinite) return;
    final b = terminalKarakterBoyutu(alan, stil, textScaler: olcek);
    if (b == _olculenBoyut) return;
    _olculenBoyut = b;
    _boyutTimer?.cancel();
    _boyutTimer = Timer(const Duration(milliseconds: 200), () {
      if (mounted) context.read<TerminalProvider>().boyutBildir(b.$1, b.$2);
    });
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

  Future<void> _zoomTerminal(BuildContext context, int d) async {
    final s = context.read<SettingsProvider>();
    final cur = s.getDouble('terminal_yazi_boyutu', fallback: 13);
    final nv = (cur + d).clamp(8, 28);
    if (nv == cur) return;
    await s.setValueBildir(context, 'terminal_yazi_boyutu', nv.round());
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
    final lines = term.lines;
    final lineStyle = TextStyle(
        fontFamily: kMonoFontFamily,
        fontFamilyFallback: kMonoFontFallback,
        fontSize: termFontSize,
        height: 1.35);
    return Container(
      color: theme.colorScheme.surface,
      child: Column(children: [
        // Başlık, öteki panellerle aynı yükseklik ve yazı stilinde.
        Container(
          height: kPanelBaslikYuksekligi,
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainer,
            border: Border(
                top: BorderSide(color: theme.colorScheme.outlineVariant),
                bottom: BorderSide(color: theme.colorScheme.outlineVariant)),
          ),
          padding: const EdgeInsets.only(left: 12, right: 6),
          // Düğmeler sağa yaslı: boş alanın hepsi soldaki Expanded'a gider.
          // Eskiden "Hatayı AI ile açıkla" Flexible(flex: 20) içindeydi; boş
          // alanın 20/21'i ona ayrılıp kullanılmayınca düğmeler sola kayıyordu.
          // Dar panelde yazılı düğmeler yalnızca simgeye döner (taşma olmaz).
          child: LayoutBuilder(builder: (_, baslikKisit) {
            final genis = baslikKisit.maxWidth >= 660;
            return Row(children: [
            Icon(Icons.terminal_rounded,
                size: 15, color: theme.colorScheme.primary),
            const SizedBox(width: 7),
            Text('TERMİNAL', style: PanelBasligi.stil(context)),
            if (term.isRunning) ...[
              const SizedBox(width: 8),
              const SizedBox(
                  width: 10,
                  height: 10,
                  child: CircularProgressIndicator(strokeWidth: 2)),
            ],
            Expanded(
              child: !term.programBaskaSekmede
                  ? const SizedBox.shrink()
                  : Padding(
                  padding: const EdgeInsets.only(left: 10),
                  child: Tooltip(
                    message: 'Her sekmenin kendi terminali vardır. Buraya '
                        'yazılanlar o programa gitmez, bu terminalde komut '
                        'olarak çalışır.',
                    child: Text(
                      () {
                        final sahip = context
                            .read<EditorProvider>()
                            .tabs
                            .where((t) => t.id == term.sahipOturum)
                            .firstOrNull;
                        return sahip == null
                            ? 'Program başka bir sekmede çalışıyor'
                            : 'Program "${sahip.name}" sekmesinde çalışıyor';
                      }(),
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurface.withOpacity(0.6)),
                    ),
                  ),
                ),
              ),
            if (!term.isRunning)
              () {
                final kabukAc = conn
                    ? () {
                        term.kabukBaslat();
                        _inputFocus.requestFocus();
                      }
                    : null;
                return genis
                    ? TextButton.icon(
                        style: TextButton.styleFrom(
                            visualDensity: VisualDensity.compact,
                            textStyle: const TextStyle(fontSize: 11)),
                        icon: const Icon(Icons.keyboard_command_key, size: 14),
                        label: const Text('TürKod Kabuğu'),
                        onPressed: kabukAc,
                      )
                    : IconButton(
                        tooltip: 'TürKod Kabuğu',
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.keyboard_command_key, size: 14),
                        onPressed: kabukAc,
                      );
              }(),
            IconButton(
              tooltip: 'TürKod Kabuğu\'nu ayrı pencerede aç',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.open_in_new, size: 14),
              // Eskiden hata yutuluyordu: pencere açılmazsa hiçbir şey olmuyordu.
              onPressed: conn
                  ? () => context
                          .read<BackendService>()
                          .call('kabuk_penceresi')
                          .then((r) {
                        if (r['ok'] != true && context.mounted) {
                          showAppSnackbar(context, 'Kabuk penceresi açılamadı.',
                              kind: SnackKind.error);
                        }
                      }).catchError((Object e) {
                        if (context.mounted) {
                          showAppSnackbar(context, 'Kabuk penceresi açılamadı: $e',
                              kind: SnackKind.error);
                        }
                      })
                  : null,
            ),
            // Dar panelde yalnızca simge kalır; eskiden başlık taşıyor, sağdaki
            // kapat düğmesi kesiliyordu.
            if (term.sonHata != null && !term.isRunning)
              () {
                void aiIleAcikla() {
                  final ui = context.read<UiProvider>();
                  if (!ui.showAi) ui.toggleAi();
                  final kod = term.sonKod.isNotEmpty
                      ? term.sonKod
                      : context.read<EditorProvider>().activeContent.value;
                  context.read<AiProvider>().explainError(kod, term.sonHata!);
                }

                return genis
                    ? TextButton.icon(
                        style: TextButton.styleFrom(
                            visualDensity: VisualDensity.compact,
                            textStyle: const TextStyle(fontSize: 11)),
                        icon: const Icon(Icons.auto_awesome, size: 14),
                        label: const Text('Hatayı AI ile açıkla',
                            overflow: TextOverflow.ellipsis, maxLines: 1),
                        onPressed: aiIleAcikla,
                      )
                    : IconButton(
                        tooltip: 'Hatayı AI ile açıkla',
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.auto_awesome, size: 14),
                        onPressed: aiIleAcikla,
                      );
              }(),
            IconButton(
              tooltip: 'Yazıyı Küçült (Ctrl+Tekerlek)',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.zoom_out_rounded, size: 16),
              onPressed: () => _zoomTerminal(context, -1),
            ),
            IconButton(
              tooltip: 'Yazıyı Büyüt (Ctrl+Tekerlek)',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.zoom_in_rounded, size: 16),
              onPressed: () => _zoomTerminal(context, 1),
            ),
            IconButton(
              tooltip: 'Tüm çıktıyı kopyala',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.copy_all_rounded, size: 16),
              onPressed: term.output.isEmpty
                  ? null
                  : () {
                      Clipboard.setData(ClipboardData(text: term.output));
                      showAppSnackbar(context, 'Terminal çıktısı kopyalandı',
                          kind: SnackKind.success);
                    },
            ),
            IconButton(
              tooltip: 'Temizle',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.delete_sweep_outlined, size: 16),
              onPressed: term.clear,
            ),
            IconButton(
              tooltip: 'Kapat',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close_rounded, size: 16),
              onPressed: () => context.read<UiProvider>().toggleTerminal(),
            ),
          ]);
          }),
        ),
        Expanded(
          child: LayoutBuilder(builder: (lc, kisit) {
            _boyutuOlc(kisit.biggest, lineStyle, MediaQuery.textScalerOf(lc));
            return Listener(
            onPointerSignal: (e) {
              if (e is PointerScrollEvent &&
                  HardwareKeyboard.instance.isControlPressed) {
                _zoomTerminal(context, e.scrollDelta.dy < 0 ? 1 : -1);
              }
            },
            // Yalnızca görünen satırlar çizilir. Eskiden tüm çıktı (200 bin
            // karaktere kadar) tek bir SelectableText olarak her çıktı
            // parçasında yeniden diziliyordu: çok yazdıran programlarda IDE
            // işlemciyi meşgul ediyor, çalışan oyunun karelerini takıltıyordu.
            // reverse: en alt satır 0. konumda; yeni çıktı geldiğinde altta
            // kalınır, kendiliğinden kaydırma gerekmez.
            // Align + shrinkWrap: çıktı paneli doldurana kadar liste içerik
            // boyunda kalır ve üste yaslanır (eskiden reverse yüzünden ilk
            // satırlar panelin en altında beliriyordu). Panel dolunca liste
            // tam yüksekliğe ulaşır ve davranış öncekiyle aynıdır.
            child: Scrollbar(
              controller: _scroll,
              thumbVisibility: true,
              thickness: 10,
              child: SelectionArea(
                child: Align(
                  alignment: Alignment.topLeft,
                  child: ListView.builder(
                    controller: _scroll,
                    reverse: true,
                    shrinkWrap: true,
                    padding: kTerminalCiktiBoslugu,
                    itemCount: lines.length,
                    itemBuilder: (_, i) =>
                        Text(lines[lines.length - 1 - i], style: lineStyle),
                  ),
                ),
              ),
            ),
          );
          }),
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
                decoration: InputDecoration(
                    isDense: true,
                    border: InputBorder.none,
                    hintText: term.isRunning
                        ? 'Programa / kabuğa girdi… (Ctrl+C: durdur)'
                        : 'Komut… (↑/↓: geçmiş, "turkod --yardim": TürKod komutları)'),
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
                  _historyPos = null;
                  _draft = '';
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
    final soluk = theme.colorScheme.onSurface.withOpacity(0.6);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isUser ? theme.colorScheme.primary.withOpacity(0.06) : null,
        border: Border(
          bottom: BorderSide(color: theme.colorScheme.outlineVariant, width: 1),
        ),
      ),
      // Markdown metni Text.rich ile çizilir; seçilip kopyalanabilmesi için
      // balonun tamamı tek bir seçim alanıdır.
      child: SelectionArea(
       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(isUser ? 'SİZ' : 'AI',
              style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.6,
                  color: isUser
                      ? theme.colorScheme.primary
                      : message.hata
                          ? theme.colorScheme.error
                          : soluk)),
          if (message.kaynak.isNotEmpty) ...[
            const SizedBox(width: 6),
            Flexible(
              child: Text(message.kaynak,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 10, color: soluk.withOpacity(0.45))),
            ),
          ],
          const Spacer(),
          if (!isUser)
            SelectionContainer.disabled(
              child: IconButton(
                tooltip: 'Yanıtı kopyala',
                visualDensity: VisualDensity.compact,
                iconSize: 13,
                icon: const Icon(Icons.copy_all),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: message.duzMetin));
                  showAppSnackbar(context, 'Yanıt kopyalandı',
                      kind: SnackKind.success);
                },
              ),
            ),
        ]),
        const SizedBox(height: 2),
        // Model düşündüyse düşünce, yanıtın üstünde açılıp kapanan bir
        // baloncukta durur (kapalı başlar).
        if (message.dusunce.isNotEmpty) _DusunceBolumu(metin: message.dusunce),
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
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Text(part.content,
                          style: const TextStyle(
                              fontFamily: kMonoFontFamily,
                              fontFamilyFallback: kMonoFontFallback,
                              fontSize: 12,
                              height: 1.35)),
                    ),
                  ]),
            );
          }
          // Metin parçaları Markdown olarak çizilir (başlık, liste, kalın,
          // tablo ...). Eskiden "**kalın**" gibi işaretler olduğu gibi
          // görünüyordu. Kullanıcı mesajı da Markdown'dır (``` blokları).
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: MarkdownGorunum(
              part.content,
              yaziBoyutu: 13,
              baglanti: (url) => baglantiAc(context, url),
              kodEylemleri: isUser
                  ? null
                  : (c, kod, dil) => IconButton(
                        tooltip: 'Koda uygula',
                        visualDensity: VisualDensity.compact,
                        iconSize: 13,
                        icon: const Icon(Icons.open_in_new),
                        onPressed: () => _applyCode(c, kod),
                      ),
            ),
          );
        }),
        if (message.hata)
          SelectionContainer.disabled(
            child: Builder(builder: (c) {
              final ai = c.watch<AiProvider>();
              return Wrap(spacing: 6, children: [
                if (ai.yenidenDenenebilir)
                  TextButton.icon(
                    icon: const Icon(Icons.refresh, size: 15),
                    label: const Text('Yeniden dene'),
                    onPressed: ai.yenidenDene,
                  ),
                TextButton.icon(
                  icon: const Icon(Icons.settings_outlined, size: 15),
                  label: const Text('AI ayarları'),
                  onPressed: () => c.read<EditorProvider>().openSettings(),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.extension_outlined, size: 15),
                  label: const Text('Yerel model kur'),
                  onPressed: () => yerelModelYoneticisiniAc(c),
                ),
              ]);
            }),
          ),
       ]),
      ),
    );
  }
}

/// AI yanıtındaki düşünme süreci: başlığa tıklayınca açılır/kapanır.
class _DusunceBolumu extends StatefulWidget {
  final String metin;
  const _DusunceBolumu({required this.metin});
  @override
  State<_DusunceBolumu> createState() => _DusunceBolumuState();
}

class _DusunceBolumuState extends State<_DusunceBolumu> {
  bool _acik = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final soluk = theme.colorScheme.onSurface.withOpacity(0.55);
    final kelime = widget.metin.split(RegExp(r'\s+')).where((k) => k.isNotEmpty).length;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SelectionContainer.disabled(
          child: InkWell(
            onTap: () => setState(() => _acik = !_acik),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.psychology_outlined, size: 14, color: soluk),
                const SizedBox(width: 4),
                Text(_acik ? 'Düşünme süreci' : 'Düşündü · $kelime kelime',
                    style: TextStyle(fontSize: 11, color: soluk)),
                Icon(_acik ? Icons.expand_less : Icons.expand_more, size: 15, color: soluk),
              ]),
            ),
          ),
        ),
        if (_acik)
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 0, 4, 6),
            child: Text(widget.metin,
                style: TextStyle(
                    fontSize: 11.5,
                    height: 1.35,
                    fontStyle: FontStyle.italic,
                    color: soluk)),
          ),
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

  /// Son kaydırılan mesaj sayısı: sohbet yalnızca yeni mesaj geldiğinde en
  /// alta iner. Eskiden her yeniden çizimde en alta atlıyor, kullanıcı uzun
  /// bir yanıtı yukarı kaydırıp okuyamıyordu.
  int _kaydirilanSayi = -1;

  void _gerekirseAltaKaydir(int sayi) {
    if (sayi == _kaydirilanSayi) return;
    _kaydirilanSayi = sayi;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(_scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180), curve: Curves.easeOut);
    });
  }

  @override
  Widget build(BuildContext context) {
    final ai = context.watch<AiProvider>();
    final conn = context.watch<ConnectionProvider>().connected;
    final ozet = context.select<SettingsProvider, String>((s) => s.aiOzet);
    final yerelMi = context.select<SettingsProvider, bool>((s) => s.aiYerelMi);
    final theme = Theme.of(context);
    _gerekirseAltaKaydir(ai.messages.length + (ai.loading ? 1 : 0));
    String currentCode() => context.read<EditorProvider>().activeContent.value;
    return Container(
      color: theme.colorScheme.surfaceContainer,
      child: Column(children: [
        PanelBasligi(
          ikon: Icons.auto_awesome,
          baslik: 'AI Asistan',
          surukleId: 'ai',
          eylemler: [
            // Modelin düşünmesini (akıl yürütme) açar/kapatır. Kapalıyken
            // destekleyen modeller düşünmeden, daha hızlı yanıt verir.
            Builder(builder: (c) {
              final acik = c.select<SettingsProvider, bool>(
                  (s) => s.getBool('ai_dusunme'));
              return PanelDugmesi(
                ikon: Icons.psychology_alt_outlined,
                seciliIkon: Icons.psychology,
                secili: acik,
                ipucu: acik
                    ? 'Düşünme açık: model yanıtlamadan önce düşünür (yavaş). Kapat'
                    : 'Düşünme kapalı: model düşünmeden yanıtlar (hızlı). Aç',
                onPressed: () {
                  final s = c.read<SettingsProvider>();
                  s.setValue('ai_dusunme', !acik).catchError((_) {});
                  showAppSnackbar(
                      c,
                      !acik
                          ? 'Düşünme açık: düşünen modeller yanıtlamadan önce düşünecek.'
                          : 'Düşünme kapalı: modeller düşünmeden, daha hızlı yanıtlayacak.');
                },
              );
            }),
            PanelDugmesi(
              ikon: Icons.lightbulb_outline,
              ipucu: 'Kodu açıkla',
              onPressed:
                  conn && !ai.loading ? () => ai.explain(currentCode()) : null,
            ),
            PanelDugmesi(
              ikon: Icons.bolt_rounded,
              ipucu: 'Kodu iyileştir (optimize et)',
              onPressed:
                  conn && !ai.loading ? () => ai.optimize(currentCode()) : null,
            ),
            PanelDugmesi(
              ikon: Icons.delete_sweep_outlined,
              ipucu: 'Sohbeti temizle',
              onPressed: conn && !ai.loading ? ai.clear : null,
            ),
          ],
        ),
        // Etkin sağlayıcı / model: renkli noktalı küçük kart; tıklayınca AI
        // ayarları açılır.
        Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
          child: Material(
            color: theme.colorScheme.surface,
            borderRadius: BorderRadius.circular(8),
            child: InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: () => context.read<EditorProvider>().openSettings(),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: theme.colorScheme.outlineVariant),
                ),
                child: Row(children: [
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: ozet == 'AI kapalı'
                          ? theme.colorScheme.onSurface.withValues(alpha: 0.3)
                          : const Color(0xFF22C55E),
                    ),
                  ),
                  const SizedBox(width: 7),
                  Icon(
                      ozet == 'AI kapalı'
                          ? Icons.cloud_off_outlined
                          : yerelMi
                              ? Icons.computer
                              : Icons.cloud_outlined,
                      size: 13,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6)),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(ozet,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 11.5,
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.75))),
                  ),
                  Icon(Icons.tune_rounded,
                      size: 14,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.5)),
                ]),
              ),
            ),
          ),
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
                        Text('AI Asistanına Hoş Geldin',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        Text(
                          conn
                              ? 'Kodun hakkında soru sor, açıklama iste\n'
                                  'ya da iyileştirme önerileri al.'
                              : 'AI özelliklerini kullanmak için TürKod motorunun '
                                  'açılmasını bekle.',
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
                            if (ozet == 'AI kapalı')
                              _AiHintChip(
                                icon: Icons.computer,
                                label: 'Ücretsiz yerel model kur',
                                enabled: conn,
                                onTap: () => yerelModelYoneticisiniAc(context),
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

/// Bir sağlayıcının modellerinden birden çoğunu seçtirir (aranabilir).
class _ModelSecimPenceresi extends StatefulWidget {
  final String baslik;
  final String aciklama;
  final List<String> modeller;
  final Set<String> secili;
  const _ModelSecimPenceresi({
    required this.baslik,
    required this.aciklama,
    required this.modeller,
    required this.secili,
  });

  @override
  State<_ModelSecimPenceresi> createState() => _ModelSecimPenceresiState();
}

class _ModelSecimPenceresiState extends State<_ModelSecimPenceresi> {
  late final Set<String> _secili = {...widget.secili};
  late final List<String> _modeller = [...widget.modeller];
  final _ara = TextEditingController();

  @override
  void dispose() {
    _ara.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final q = _ara.text.trim().toLowerCase();
    final liste = q.isEmpty
        ? _modeller
        : _modeller.where((m) => m.toLowerCase().contains(q)).toList();
    final yeniAd = q.isNotEmpty && !_modeller.any((m) => m.toLowerCase() == q);
    return AlertDialog(
      title: Text(widget.baslik),
      content: SizedBox(
        width: 560,
        height: 460,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(widget.aciklama, style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 8),
          TextField(
            controller: _ara,
            autofocus: true,
            decoration: const InputDecoration(
                isDense: true,
                prefixIcon: Icon(Icons.search, size: 17),
                hintText: 'Model ara ya da adını yaz…'),
            onChanged: (_) => setState(() {}),
          ),
          if (yeniAd)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                icon: const Icon(Icons.add, size: 16),
                label: Text('"${_ara.text.trim()}" adlı modeli ekle'),
                onPressed: () => setState(() {
                  final m = _ara.text.trim();
                  _modeller.insert(0, m);
                  _secili.add(m);
                  _ara.clear();
                }),
              ),
            ),
          const SizedBox(height: 4),
          Text('${_secili.length} seçili · ${liste.length} model',
              style: const TextStyle(fontSize: 11)),
          Expanded(
            child: ListView.builder(
              itemCount: liste.length,
              itemBuilder: (_, i) {
                final m = liste[i];
                return CheckboxListTile(
                  dense: true,
                  visualDensity: VisualDensity.compact,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(m, style: const TextStyle(fontSize: 13)),
                  value: _secili.contains(m),
                  onChanged: (v) =>
                      setState(() => v == true ? _secili.add(m) : _secili.remove(m)),
                );
              },
            ),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Vazgeç')),
        FilledButton(
            onPressed: () => Navigator.pop(context, _secili), child: const Text('Kaydet')),
      ],
    );
  }
}

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _apiKey = TextEditingController();
  final _ozelUrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _sagCtrl = TextEditingController();

  /// Otomatik tamamlama gecikmesi kaydırıcısı (bırakınca kaydedilir).
  double _tamGecikme = 300;

  /// Sağlayıcı başına anahtarlar (form içi kopya; Kaydet'te yazılır).
  final Map<String, String> _anahtarlar = {};
  final _sysMsg = TextEditingController();
  final _maxTok = TextEditingController();
  final _fontSearch = TextEditingController();
  final _duzeltmeZamanAsimi = TextEditingController();
  final _duzeltmeMesajAraligi = TextEditingController();
  final _duzeltmeMaksDongu = TextEditingController();
  final _autoSaveInterval = TextEditingController();
  late String _tema;
  late String _sag;
  late String _model;
  late String _yaziTipi;
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
  bool _testingAi = false;

  /// Formdaki sağlayıcı/model/anahtarla gerçek, çok kısa bir istek gönderir.
  Future<void> _testAi() async {
    if (_testingAi) return;
    final s = context.read<SettingsProvider>();
    if (!s.loaded || !_formReady) return;
    setState(() => _testingAi = true);
    final backend = context.read<BackendService>();
    try {
      // Backend kayıtlı değerleri kullanır: formdakiler önce kaydedilir.
      await s.setValues(_aiDegerleri());
      final r = await backend.call('ai_baglanti_test');
      if (mounted) {
        showAppSnackbar(
            context, 'Bağlantı başarılı (${r['saglayici']} / ${r['model']})',
            kind: SnackKind.success);
      }
    } on BackendException catch (e) {
      if (mounted) {
        showAppSnackbar(context, 'Bağlantı kurulamadı: ${e.message}',
            kind: SnackKind.error);
      }
    } catch (e) {
      if (mounted) {
        showAppSnackbar(context, 'Bağlantı kurulamadı: $e',
            kind: SnackKind.error);
      }
    } finally {
      if (mounted) setState(() => _testingAi = false);
    }
  }
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
    if (!_entegrasyonIstendi) {
      _entegrasyonIstendi = true;
      _entegrasyonYukle();
    }
    // Model Yöneticisi kapalıyken biten indirmeler de görev listelerine
    // yansısın: yerel modeller sayfa her açıldığında yeniden okunur.
    if (s.loaded && !_modellerIstendi) {
      _modellerIstendi = true;
      s.refreshModels().catchError((_) {});
    }
  }

  bool _fontsRequested = false;
  bool _modellerIstendi = false;

  // PATH / .trpy ilişkilendirme (kurulum sihirbazındaki seçeneklerin aynısı).
  // Ayar dosyasında değil Windows kayıt defterinde durur; anında uygulanır.
  Map<String, dynamic>? _entegrasyon;
  bool _entegrasyonIstendi = false;
  bool _entegrasyonMesgul = false;

  Future<void> _entegrasyonYukle() async {
    try {
      final r =
          await context.read<BackendService>().call('sistem_entegrasyonu');
      if (mounted) setState(() => _entegrasyon = Map<String, dynamic>.from(r));
    } catch (e) {
      if (mounted) {
        setState(() => _entegrasyon = {
              'destekleniyor': false,
              'neden': 'Durum okunamadı: $e',
            });
      }
    }
  }

  Future<void> _entegrasyonAyarla(String anahtar, bool deger) async {
    if (_entegrasyonMesgul) return;
    setState(() => _entegrasyonMesgul = true);
    try {
      final r = await context
          .read<BackendService>()
          .call('sistem_entegrasyonu_ayarla', {anahtar: deger});
      final yeni = Map<String, dynamic>.from(r);
      if (!mounted) return;
      setState(() => _entegrasyon = yeni);
      final sistemde = anahtar == 'path'
          ? yeni['path_sistemde'] == true
          : yeni['iliski_sistemde'] == true;
      if (!deger && sistemde) {
        showAppSnackbar(
            context,
            'Bu ayar yönetici kurulumunda tüm kullanıcılar için yapılmış; '
            'kapatmak için TürKod kurulumunu yeniden çalıştırıp seçeneğin '
            'işaretini kaldırın.',
            kind: SnackKind.info);
      } else {
        showAppSnackbar(
            context,
            anahtar == 'path'
                ? (deger
                    ? "TürKod PATH'e eklendi. Yeni açılan terminallerde "
                        '"turkod dosya.trpy" komutu çalışır.'
                    : "TürKod PATH'ten çıkarıldı.")
                : (deger
                    ? '.trpy dosyaları TürKod ile ilişkilendirildi.'
                    : '.trpy ilişkilendirmesi kaldırıldı.'),
            kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) {
        showAppSnackbar(context, 'Uygulanamadı: $e', kind: SnackKind.error);
      }
    } finally {
      if (mounted) setState(() => _entegrasyonMesgul = false);
    }
  }

  // Sayfa açıldığındaki boyutlar: kullanıcı kaydırıcıyı oynatmadıysa
  // kaydetmede bu ayarlara dokunulmaz (Ctrl+tekerlek ile sayfa açıkken
  // yapılan yakınlaştırma eskiden eski değerle eziliyordu).
  double _fontSizeIlk = 14;
  double _terminalFontSizeIlk = 13;

  void _populate(SettingsProvider s) {
    _tema = s.getString('tema', fallback: 'Modern Koyu');
    if (!temalar.contains(_tema)) _tema = temalar.first;
    _sag = s.aiSaglayiciId;
    final savedModel = s.getString('ai_model', fallback: '').trim();
    final models = s.aiModels[_sag] ?? [];
    _model = savedModel.isNotEmpty
        ? savedModel
        : (models.isNotEmpty ? models.first : '');
    _modelCtrl.text = _model;
    _sagCtrl.text = s.saglayici(_sag)?.ad ?? _sag;
    _anahtarlar.clear();
    final kayitli = s.get<dynamic>('ai_api_anahtarlari');
    if (kayitli is Map) {
      kayitli.forEach((k, v) => _anahtarlar[k.toString()] = v?.toString() ?? '');
    }
    _apiKey.text = s.aiAnahtari(_sag);
    _ozelUrl.text = s.getString('ai_ozel_url');
    _tamGecikme =
        s.getInt('ai_tamamlama_gecikme', fallback: 300).clamp(100, 1500).toDouble();
    _sysMsg.text = s.getString('ai_sistem_mesaji');
    _maxTok.text = s.getInt('ai_max_token', fallback: 4096).toString();
    // Kayıtlı değerler kaydırıcı sınırlarına çekilir: elle düzenlenmiş /
    // eski sürümden kalan ayar dosyasındaki sınır dışı bir değer Slider
    // doğrulamasını patlatıp Ayarlar sayfasını açılamaz hâle getiriyordu.
    _sic = s.getDouble('ai_sicaklik', fallback: 0.7).clamp(0.0, 2.0).toDouble();
    _fontSize =
        s.getInt('yazi_boyutu', fallback: 14).clamp(8, 32).toDouble();
    _fontSizeIlk = _fontSize;
    _auto = s.getBool('otomatik_tamamlama', fallback: true);
    _autoSave = s.getBool('otomatik_kaydetme');
    _autoSaveInterval.text = s
        .getInt('otomatik_kaydetme_aralik', fallback: 30)
        .clamp(5, 600)
        .toString();
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

  /// Formdaki AI seçimleri (sağlayıcı, model, anahtarlar, özel adres).
  Map<String, dynamic> _aiDegerleri() {
    final anahtar = _apiKey.text.trim();
    _anahtarlar[_sag] = anahtar;
    _model = _modelCtrl.text.trim();
    return {
      'ai_saglayici': _sag,
      'ai_model': _model,
      // Eski tek anahtar alanı seçili sağlayıcının anahtarını taşır.
      'ai_api_key': anahtar,
      'ai_api_anahtarlari': Map<String, String>.from(_anahtarlar)
        ..removeWhere((_, v) => v.isEmpty),
      'ai_ozel_url': _ozelUrl.text.trim(),
    };
  }

  /// Sağlayıcı değişince formdaki anahtar o sağlayıcınınkiyle değişir.
  void _saglayiciSec(SettingsProvider settings, String id) {
    if (id == _sag) return;
    setState(() {
      _anahtarlar[_sag] = _apiKey.text.trim();
      _sag = id;
      _apiKey.text = _anahtarlar[id] ?? '';
      final list = settings.aiModels[id] ?? [];
      _model = list.isNotEmpty ? list.first : '';
      _modelCtrl.text = _model;
      _sagCtrl.text = settings.saglayici(id)?.ad ?? id;
    });
    // Yerel sunucuların modelleri canlı sorgulanır.
    if (settings.saglayici(id)?.yerel ?? false) {
      settings.refreshModels().then((_) {
        if (!mounted || _sag != id) return;
        final list = settings.aiModels[id] ?? [];
        if (_modelCtrl.text.isEmpty && list.isNotEmpty) {
          setState(() => _modelCtrl.text = _model = list.first);
        }
      });
    }
  }

  @override
  void initState() {
    super.initState();
    ayarlarHedefi.addListener(_hedefDegisti);
    kodiAyarDegisti.addListener(_kodiAyarDegisti);
  }

  /// Sayfa zaten açıkken bir bölüme gitmek istendi (Kodi, model yöneticisi).
  void _hedefDegisti() {
    if (mounted && ayarlarHedefi.value != null) setState(() {});
  }

  /// Kodi bir ayarı değiştirdi: form yeni değerleri göstersin; yoksa
  /// "Kaydet ve Uygula" eski değerleri geri yazardı.
  void _kodiAyarDegisti() {
    final s = context.read<SettingsProvider>();
    if (mounted && s.loaded) setState(() => _populate(s));
  }

  @override
  void dispose() {
    ayarlarHedefi.removeListener(_hedefDegisti);
    kodiAyarDegisti.removeListener(_kodiAyarDegisti);
    _apiKey.dispose();
    _ozelUrl.dispose();
    _modelCtrl.dispose();
    _sagCtrl.dispose();
    _sysMsg.dispose();
    _maxTok.dispose();
    _fontSearch.dispose();
    _duzeltmeZamanAsimi.dispose();
    _duzeltmeMesajAraligi.dispose();
    _duzeltmeMaksDongu.dispose();
    _autoSaveInterval.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    // Ayarlar okunmadan doldurulmuş bir form kaydedilirse kayıtlı ayarlar
    // (API anahtarları dahil) varsayılanlarla ezilirdi.
    if (!context.read<SettingsProvider>().loaded || !_formReady) {
      showAppSnackbar(context,
          'Ayarlar henüz okunamadı; bağlantı gelince yeniden dene.',
          kind: SnackKind.error);
      return;
    }
    setState(() => _saving = true);
    try {
      final s = context.read<SettingsProvider>();
      // Sınır denetimi: 0 / eksi / çok büyük değerler olduğu gibi kaydediliyordu.
      // Zaman aşımı × döngü sayısı, istek zaman aşımına (5 dk) sığmalı;
      // yoksa arayüz "Zaman aşımı" derken backend çalışmayı sürdürüyordu.
      final zamanAsimi =
          (int.tryParse(_duzeltmeZamanAsimi.text.trim()) ?? 5).clamp(1, 60);
      final maksDongu = (int.tryParse(_duzeltmeMaksDongu.text.trim()) ?? 12)
          .clamp(1, math.max(1, 240 ~/ zamanAsimi));
      final degerler = <String, dynamic>{
        'tema': _tema,
        // Görev atamaları (ai_gorev_atamalari) ve model listesi Görevler/Modeller
        // kartında seçildiği anda kaydedilir; burada yalnızca sağlayıcı formu.
        ..._aiDegerleri(),
        'ai_sistem_mesaji': _sysMsg.text,
        'ai_sicaklik': _sic,
        'ai_max_token':
            (int.tryParse(_maxTok.text.trim()) ?? 4096).clamp(64, 32768),
        'otomatik_tamamlama': _auto,
        'otomatik_kaydetme': _autoSave,
        'otomatik_kaydetme_aralik':
            (int.tryParse(_autoSaveInterval.text.trim()) ?? 30).clamp(5, 600),
        if (_fontSize != _fontSizeIlk) 'yazi_boyutu': _fontSize.round(),
        'satir_numaralari': _satirNo,
        'kelime_sar': _kelimeSar,
        'bosluk_gostergesi': _boslukGoster,
        'yazi_tipi': _yaziTipi.trim().isEmpty ? 'Consolas' : _yaziTipi.trim(),
        if (_terminalFontSize != _terminalFontSizeIlk)
          'terminal_yazi_boyutu': _terminalFontSize.round(),
        'duzeltme_zaman_asimi': zamanAsimi,
        'duzeltme_mesaj_araligi':
            (int.tryParse(_duzeltmeMesajAraligi.text.trim()) ?? 100)
                .clamp(0, 5000),
        'duzeltme_maks_dongu': maksDongu,
      };
      await s.setValues(degerler);
      _fontSizeIlk = _fontSize;
      _terminalFontSizeIlk = _terminalFontSize;
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
      await s.setValues(_aiDegerleri());
      final r = await backend.call('ai_modelleri_guncelle');
      await s.refreshModels();
      final models = s.aiModels[_sag] ?? [];
      if (_model.isEmpty || (models.isNotEmpty && !models.contains(_model))) {
        _model = models.isNotEmpty ? models.first : '';
        _modelCtrl.text = _model;
      }
      if (mounted) {
        setState(() {});
        final canli = r['canli'] == true;
        final hata = r['hata']?.toString();
        showAppSnackbar(
            context,
            '${s.aiSaglayicilar.length} sağlayıcı internetten güncellendi'
            '${canli ? '; ${models.length} model sağlayıcıdan canlı alındı' : ''}'
            '${hata != null && hata.isNotEmpty ? ' (canlı liste alınamadı: $hata)' : ''}',
            kind: hata == null || hata.isEmpty ? SnackKind.success : SnackKind.info);
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


  /// Görevler kartı (model yöneticisindeki "Görev ata" buraya kaydırır).
  final GlobalKey _gorevlerKey = GlobalKey(debugLabel: 'ayarlar.ai_gorevler');

  /// Kartların anahtarları (başlık -> anahtar): Kodi ya da model yöneticisi
  /// Ayarlar'ın bir bölümüne gidebilsin.
  final Map<String, GlobalKey> _kartAnahtarlari = {};

  void _hedefeKaydir() {
    final hedef = ayarlarHedefi.value;
    final baslik = hedef == null ? null : kAyarBolumleri[hedef];
    if (baslik == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final c = hedef == 'ai_gorevler'
          ? _gorevlerKey.currentContext
          : _kartAnahtarlari[baslik]?.currentContext;
      if (c == null || !mounted) return;
      ayarlarHedefi.value = null;
      Scrollable.ensureVisible(c,
          duration: const Duration(milliseconds: 350), curve: Curves.easeOut);
    });
  }

  /// Ayarlar → Kodi: Kodi'nin neleri yapabileceği. Kodi bunları kendisi
  /// değiştiremez (kodi_kontrol.dart: kKodiYasakAyarOnekleri).
  List<Widget> _kodiYetkiSatirlari(ThemeData theme) {
    final s = context.watch<SettingsProvider>();
    Widget satir(String anahtar, String baslik, String aciklama,
            {bool varsayilan = true}) =>
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(baslik),
          subtitle: Text(aciklama, style: const TextStyle(fontSize: 11.5)),
          value: s.getBool(anahtar, fallback: varsayilan),
          onChanged: (v) => s.setValueBildir(context, anahtar, v ?? varsayilan),
        );
    return [
      Text(
        'Kodi, sen isteyince programı senin için yönetebilir: menü komutlarını '
        'çalıştırır, eklentileri açar, ayarları değiştirir. Neleri yapabileceğini '
        'buradan seçersin; bu bölümü yalnızca sen değiştirebilirsin, Kodi değiştiremez.',
        style: TextStyle(
            fontSize: 11.5, color: theme.colorScheme.onSurface.withOpacity(0.65)),
      ),
      satir(kKodiYetkiAyar, 'Ayarları değiştirebilsin',
          'Tema, yazı boyutu, editör seçenekleri, yapay zekâ görevlerinin modelleri ...'),
      satir(kKodiYetkiEklenti, 'Eklentileri açıp kapatabilsin',
          'Kod Parçacıkları, Odak Zamanlayıcı, Karalama Defteri ...'),
      satir(kKodiYetkiKomut, 'Program komutlarını çalıştırabilsin',
          'Menülerdeki her komut: EXE\'ye Dönüştür, Klavye Kısayolları, Bul / Değiştir ... '
              'Çalıştırmak, kaydetmek gibi işlerden önce yine izin ister.'),
      satir(kKodiYetkiTarayici, 'Tarayıcıyı yönetebilsin',
          'IDE içindeki tarayıcıda site açar, arar, tıklar, yazar. Şifre kutularına yazmaz; '
              'satın alma, ödeme, silme gibi düğmelerden önce izin ister.'),
      satir(kKodiHepSor, 'Her işten önce izin istesin',
          'Panel ya da pencere açmak gibi küçük işlerde bile önce sorar.',
          varsayilan: false),
      const Divider(height: 20),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('Sohbet kaydedilsin'),
        subtitle: const Text('Program kapanıp açılınca Kodi ile sohbetin kaldığı yerden sürer.',
            style: TextStyle(fontSize: 11.5)),
        value: s.getBool(kKodiSohbetKaydet, fallback: true),
        onChanged: (v) async {
          await s.setValueBildir(context, kKodiSohbetKaydet, v ?? true);
          // Kapatılınca kayıtlı sohbet hemen silinir.
          if (context.mounted) await context.read<KodiProvider>().sohbetiKaydet();
        },
      ),
      satir(kKodiHafiza, 'Kodi beni hatırlasın',
          'Adın, sevdiğin şeyler gibi söylediklerini hatırlar ("bunu hatırla", "unut"). Şifre, '
              'adres, telefon gibi özel bilgileri hiç hatırlamaz.'),
      Wrap(spacing: 8, runSpacing: 8, children: [
        OutlinedButton.icon(
          icon: const Icon(Icons.psychology_outlined, size: 16),
          label: const Text('Hafızayı yönet…'),
          onPressed: () => kodiHafizaPenceresi(context),
        ),
        OutlinedButton.icon(
          icon: const Icon(Icons.delete_sweep_outlined, size: 16),
          label: const Text('Bütün sohbetleri sil'),
          onPressed: () async {
            final evet = await showDialog<bool>(
              context: context,
              builder: (dc) => AlertDialog(
                title: const Text('Bütün sohbetler silinsin mi?'),
                content: const Text('Kodi ile yaptığın bütün kayıtlı sohbetler silinir. '
                    'Bu geri alınamaz. (Kodi\'nin hafızası ayrıdır, silinmez.)'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(dc, false), child: const Text('Vazgeç')),
                  FilledButton(onPressed: () => Navigator.pop(dc, true), child: const Text('Sil')),
                ],
              ),
            );
            if (evet != true || !context.mounted) return;
            await context.read<KodiProvider>().tumSohbetleriSil();
            if (context.mounted) {
              showAppSnackbar(context, 'Kodi ile bütün sohbetler silindi', kind: SnackKind.success);
            }
          },
        ),
      ]),
      const Divider(height: 20),
      DropdownButtonFormField<String>(
        value: const {'kapali', 'pencere', 'ekran'}.contains(s.getString(kKodiGoruntu))
            ? s.getString(kKodiGoruntu)
            : 'kapali',
        isExpanded: true,
        decoration: const InputDecoration(
            labelText: 'Mesajla birlikte görüntü gönder', isDense: true),
        items: const [
          DropdownMenuItem(value: 'kapali', child: Text('Kapalı')),
          DropdownMenuItem(value: 'pencere', child: Text('TürKod penceresinin görüntüsü')),
          DropdownMenuItem(value: 'ekran', child: Text('Bütün ekranın görüntüsü')),
        ],
        onChanged: (v) => s.setValueBildir(context, kKodiGoruntu, v ?? 'kapali'),
      ),
      const SizedBox(height: 4),
      Text(
        'Açıkken Kodi\'ye yazdığın her mesajla görüntü de yapay zekâya gider; Kodi ekranda '
        'ne olduğunu görür. Yalnızca görüntü görebilen modellerle çalışır. Ekranda özel bir şey '
        'varken kapat. Kodi\'nin balonundaki kamera düğmesiyle de açılıp kapanır.',
        style: TextStyle(fontSize: 11.5, color: theme.colorScheme.onSurface.withOpacity(0.65)),
      ),
      Align(
        alignment: Alignment.centerLeft,
        child: TextButton.icon(
          icon: const Icon(Icons.key_rounded, size: 16),
          label: const Text('API kurulum rehberi'),
          onPressed: () => kodiKurulumRehberi(context),
        ),
      ),
    ];
  }

  Future<void> _gorevAta(SettingsProvider s, String gorev, AiAtama? a) async {
    try {
      await s.gorevAta(gorev, a);
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
    }
    if (mounted) setState(() {});
  }

  Widget _gorevSatiri(SettingsProvider s, String gorev, String ad) {
    final secili = s.gorevAtamasi(gorev);
    final modeller = s.tumAiModelleri;
    final ogeler = <DropdownMenuItem<String>>[
      DropdownMenuItem(
          value: '',
          // Kodi'ye model atanmazsa AI Paneli sohbet modeliyle konuşur;
          // hangi model olduğu açıkça yazılır.
          child: Text(
              gorev != 'kodi'
                  ? 'Kapalı'
                  : s.gorevAtamasi('sohbet') == null
                      ? 'Otomatik (AI Paneli sohbeti kapalı)'
                      : 'Otomatik: ${s.atamaEtiketi(s.gorevAtamasi('sohbet')!)}',
              overflow: TextOverflow.ellipsis)),
      for (final a in [...modeller, if (secili != null && !modeller.contains(secili)) secili])
        DropdownMenuItem(
          value: a.anahtar,
          child: Row(children: [
            Icon(a.yerel || (s.saglayici(a.saglayici)?.yerel ?? false)
                    ? Icons.computer
                    : Icons.cloud_outlined,
                size: 15),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                  '${s.atamaEtiketi(a)}${modeller.contains(a) ? '' : ' (listede yok)'}',
                  overflow: TextOverflow.ellipsis),
            ),
          ]),
        ),
    ];
    final eksikAnahtar = secili != null && !s.atamaHazir(secili);
    final kodiModelsiz =
        gorev == 'kodi' && secili == null && s.gorevAtamasi('sohbet') == null;
    return Row(children: [
      SizedBox(width: 210, child: Text(ad, style: const TextStyle(fontSize: 13))),
      Expanded(
        child: DropdownButtonFormField<String>(
          key: ValueKey('gorev-$gorev-${secili?.anahtar}-${modeller.length}'),
          initialValue: secili?.anahtar ?? '',
          isExpanded: true,
          isDense: true,
          decoration: InputDecoration(
            isDense: true,
            errorText: eksikAnahtar
                ? '${s.saglayiciAdi(secili.saglayici)} için API anahtarı girilmemiş'
                : kodiModelsiz
                    ? 'Kodi konuşamaz: bir model seç ya da AI Paneli sohbetini aç'
                    : null,
          ),
          items: ogeler,
          onChanged: (v) {
            final a = AiAtama.anahtardan(v);
            if (a != secili) _gorevAta(s, gorev, a);
          },
        ),
      ),
    ]);
  }

  /// Formdaki sağlayıcı + modeli "Mevcut modeller" listesine ekler.
  Future<void> _modelEkle(SettingsProvider s) async {
    final model = _modelCtrl.text.trim();
    if (model.isEmpty) {
      showAppSnackbar(context, 'Önce bir model seç ya da adını yaz.', kind: SnackKind.error);
      return;
    }
    final yeni = AiAtama(_sag, model);
    final liste = s.aiBulutModelleri;
    final eklendi = !liste.contains(yeni);
    // İlk model: boştaki sohbet görevleri buna atanır (sonra değiştirilebilir).
    final bosGorevler = [
      for (final g in kBulutGorevleri.keys)
        if (g != 'kodi' && s.gorevAtamasi(g) == null) g,
    ];
    final ilk = liste.isEmpty;
    final atamalar = {for (final e in s.gorevAtamalari.entries) e.key: e.value.toJson()};
    if (ilk) {
      for (final g in bosGorevler) {
        atamalar[g] = yeni.toJson();
      }
    }
    try {
      await s.setValues({
        ..._aiDegerleri(),
        'ai_bulut_modelleri': [
          for (final a in liste) a.toJson(),
          if (eklendi) yeni.toJson(),
        ],
        if (ilk) 'ai_gorev_atamalari': atamalar,
      });
      if (mounted) {
        setState(() {});
        showAppSnackbar(
            context,
            eklendi
                ? '${s.atamaEtiketi(yeni)} eklendi'
                    '${ilk && bosGorevler.isNotEmpty ? ' ve boştaki görevlere atandı' : ''}. '
                    'Görevleri yukarıdan değiştirebilirsin.'
                : '${s.atamaEtiketi(yeni)} zaten listede (anahtar güncellendi).',
            kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _modelKaldir(SettingsProvider s, AiAtama a) async {
    final atamalar = {
      for (final e in s.gorevAtamalari.entries)
        if (e.value != a) e.key: e.value.toJson(),
    };
    try {
      await s.setValues({
        'ai_bulut_modelleri': [
          for (final m in s.aiBulutModelleri)
            if (m != a) m.toJson(),
        ],
        'ai_gorev_atamalari': atamalar,
      });
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
    }
  }

  /// Modelleri canlı alınan sağlayıcı (düğmede bekleme göstergesi).
  String? _modelGetirilen;

  /// Formdaki sağlayıcıyı (anahtarıyla) bağlar ve modellerini seçtirir.
  Future<void> _saglayiciBagla(SettingsProvider s) async {
    final secili = s.saglayici(_sag);
    if ((secili?.anahtarGerekli ?? true) &&
        !(secili?.yerel ?? false) &&
        _apiKey.text.trim().isEmpty) {
      showAppSnackbar(context, '${secili?.ad ?? _sag} için API anahtarını gir.',
          kind: SnackKind.error);
      return;
    }
    try {
      await s.setValues(_aiDegerleri());
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
      return;
    }
    if (mounted) await _modelSec(s, _sag);
  }

  /// Bağlı bir sağlayıcının modellerini canlı alıp seçtirir; seçilenler
  /// "Mevcut modeller" listesine girer, seçimi kaldırılanlar çıkar.
  Future<void> _modelSec(SettingsProvider s, String id) async {
    if (_modelGetirilen != null) return;
    final backend = context.read<BackendService>();
    final ad = s.saglayiciAdi(id);
    String? hata;
    var canli = false;
    setState(() => _modelGetirilen = id);
    try {
      final r = await backend.call(
          'ai_modelleri_guncelle', {'saglayici': id, 'katalog': false});
      canli = r['canli'] == true;
      hata = r['hata']?.toString();
      await s.refreshModels();
    } catch (e) {
      hata = '$e';
    }
    if (!mounted) return;
    setState(() => _modelGetirilen = null);
    final tumu = List<String>.from(s.aiModels[id] ?? const <String>[]);
    final onceki = {
      for (final a in s.aiBulutModelleri)
        if (a.saglayici == id) a.model,
    };
    for (final m in onceki) {
      if (!tumu.contains(m)) tumu.insert(0, m);
    }
    final secim = await showDialog<Set<String>>(
      context: context,
      builder: (_) => _ModelSecimPenceresi(
        baslik: '$ad modelleri',
        aciklama: canli
            ? '${tumu.length} model sağlayıcıdan canlı alındı. Görevlerde kullanmak '
                'istediklerini işaretle.'
            : 'Canlı liste alınamadı${hata != null && hata.isNotEmpty ? ' (${baglantiHatasiAciklamasi(hata)})' : ''}; '
                'katalogdaki modeller gösteriliyor. Listede olmayan bir model adını '
                'aşağıya yazıp ekleyebilirsin.',
        modeller: tumu,
        secili: onceki,
      ),
    );
    if (secim == null || !mounted) return;
    final eski = s.aiBulutModelleri;
    final ilk = eski.isEmpty;
    final yeniListe = [
      for (final a in eski)
        if (a.saglayici != id || secim.contains(a.model)) a,
      for (final m in secim)
        if (!onceki.contains(m)) AiAtama(id, m),
    ];
    final atamalar = <String, dynamic>{
      for (final e in s.gorevAtamalari.entries)
        if (e.value.yerel || yeniListe.contains(e.value) ||
            !s.aiBulutModelleri.contains(e.value))
          e.key: e.value.toJson(),
    };
    // İlk eklenen model boştaki sohbet görevlerine atanır (sonra değiştirilebilir).
    if (ilk && yeniListe.isNotEmpty) {
      for (final g in kBulutGorevleri.keys) {
        // Kodi otomatik kalır: AI Paneli sohbet modelini izler.
        if (g == 'kodi') continue;
        atamalar.putIfAbsent(g, () => yeniListe.first.toJson());
      }
    }
    try {
      await s.setValues({
        'ai_bulut_modelleri': [for (final a in yeniListe) a.toJson()],
        'ai_gorev_atamalari': atamalar,
      });
      if (mounted) {
        setState(() {});
        showAppSnackbar(context, '$ad: ${secim.length} model listede.',
            kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _baglantiKes(SettingsProvider s, String id) async {
    final ad = s.saglayiciAdi(id);
    final onay = await showDialog<bool>(
      context: context,
      builder: (dc) => AlertDialog(
        title: Text('$ad bağlantısı kesilsin mi?'),
        content: const Text('API anahtarı, listedeki modelleri ve bu modellere '
            'verilmiş görevler kaldırılır.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dc, false), child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, true), child: const Text('Bağlantıyı kes')),
        ],
      ),
    );
    if (onay != true || !mounted) return;
    try {
      await context.read<BackendService>().call('ai_baglanti_kes', {'saglayici': id});
      _anahtarlar.remove(id);
      if (_sag == id) _apiKey.clear();
      await s.load();
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaldırılamadı: $e', kind: SnackKind.error);
    }
  }

  /// Bağlı sağlayıcılar: her birinden ayrı modeller seçilebilir.
  Widget _bagliSaglayicilar(BuildContext context, SettingsProvider s) {
    final theme = Theme.of(context);
    final ids = s.bagliSaglayicilar;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Bağlı sağlayıcılar (${ids.length})',
          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      if (ids.isEmpty)
        Text('Henüz bağlı sağlayıcı yok. Aşağıdan bir sağlayıcı seçip API anahtarını '
            'girerek bağla; istediğin kadar sağlayıcı bağlayabilirsin.',
            style: TextStyle(
                fontSize: 11.5, color: theme.colorScheme.onSurface.withOpacity(0.65))),
      for (final id in ids)
        Container(
          margin: const EdgeInsets.only(bottom: 4),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            border: Border.all(color: theme.colorScheme.outlineVariant),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Row(children: [
            Icon((s.saglayici(id)?.yerel ?? false) ? Icons.computer : Icons.link,
                size: 17, color: theme.colorScheme.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(s.saglayiciAdi(id),
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                Text(
                    '${s.aiAnahtari(id).isNotEmpty ? 'API anahtarı kayıtlı' : 'Anahtarsız'} · '
                    '${s.aiBulutModelleri.where((a) => a.saglayici == id).length} model listede',
                    style: TextStyle(
                        fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.6))),
              ]),
            ),
            TextButton.icon(
              style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              icon: _modelGetirilen == id
                  ? const SizedBox(
                      width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.checklist, size: 16),
              label: Text(_modelGetirilen == id ? 'Modeller alınıyor…' : 'Model seç'),
              onPressed: _modelGetirilen != null ? null : () => _modelSec(s, id),
            ),
            IconButton(
              tooltip: 'Bağlantıyı kes',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.link_off, size: 17),
              onPressed: () => _baglantiKes(s, id),
            ),
          ]),
        ),
    ]);
  }

  /// Mevcut modeller: nerede çalıştığı (yerel / sağlayıcı) ve hangi görevlerde
  /// kullanıldığı.
  Widget _mevcutModeller(BuildContext context, SettingsProvider s) {
    final theme = Theme.of(context);
    final atamalar = s.gorevAtamalari;
    final modeller = s.tumAiModelleri;
    Widget satir(AiAtama a) {
      final yerelSunucu = s.saglayici(a.saglayici)?.yerel ?? false;
      final gorevler = [
        for (final e in atamalar.entries)
          if (e.value == a) kAiGorevleri[e.key] ?? e.key,
        if (!atamalar.containsKey('kodi') && atamalar['sohbet'] == a) 'Kodi (otomatik)',
      ];
      final konum = a.yerel
          ? 'Yerel · bu bilgisayarda (llama.cpp)'
          : yerelSunucu
              ? 'Yerel sunucu · ${s.saglayiciAdi(a.saglayici)}'
              : 'Bulut · ${s.saglayiciAdi(a.saglayici)}'
                  '${s.atamaHazir(a) ? '' : ' · API anahtarı yok'}';
      return Container(
        margin: const EdgeInsets.only(bottom: 4),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          border: Border.all(color: theme.colorScheme.outlineVariant),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Row(children: [
          Icon(a.yerel || yerelSunucu ? Icons.computer : Icons.cloud_outlined,
              size: 17, color: theme.colorScheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SelectableText(s.atamaEtiketi(a),
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              Text(
                  '$konum · ${gorevler.isEmpty ? 'görev atanmamış' : gorevler.join(', ')}',
                  style: TextStyle(
                      fontSize: 11,
                      color: s.atamaHazir(a)
                          ? theme.colorScheme.onSurface.withOpacity(0.6)
                          : theme.colorScheme.error)),
            ]),
          ),
          if (a.yerel)
            TextButton(
              style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              onPressed: () => yerelModelYoneticisiniAc(context),
              child: const Text('Yönet'),
            )
          else
            IconButton(
              tooltip: 'Listeden kaldır',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close, size: 17),
              onPressed: () => _modelKaldir(s, a),
            ),
        ]),
      );
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Mevcut modeller (${modeller.length})',
          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      if (modeller.isEmpty)
        Text(
            'Henüz model yok. Aşağıdan bir sağlayıcı ve model ekle ya da '
            'Eklenti Özellikleri → Yerel AI Modelleri\'nden ücretsiz bir model indir.',
            style: TextStyle(
                fontSize: 11.5, color: theme.colorScheme.onSurface.withOpacity(0.65))),
      for (final a in modeller) satir(a),
      Align(
        alignment: Alignment.centerLeft,
        child: TextButton.icon(
          style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
          icon: const Icon(Icons.download_outlined, size: 16),
          label: const Text('Yerel model indir (Eklenti Özellikleri)'),
          onPressed: () => yerelModelYoneticisiniAc(context),
        ),
      ),
    ]);
  }

  Widget _card(BuildContext context, IconData icon, String title,
      List<Widget> children) {
    final theme = Theme.of(context);
    // Material (renkli Container değil): içerideki CheckboxListTile'ların
    // üzerine gelme / tıklama efektleri kart arka planının altında
    // kalmasın.
    return Padding(
      key: _kartAnahtarlari.putIfAbsent(title, () => GlobalKey(debugLabel: 'ayarlar.$title')),
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

  List<Widget> _entegrasyonSatirlari(ThemeData theme) {
    final d = _entegrasyon;
    final notStili = TextStyle(
        fontSize: 10.5, color: theme.colorScheme.onSurface.withOpacity(0.55));
    if (d == null) {
      return [
        const Align(
            alignment: Alignment.centerLeft,
            child: SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2))),
      ];
    }
    final destek = d['destekleniyor'] == true;
    final etkin = destek && !_entegrasyonMesgul;
    return [
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('.trpy dosyalarını TürKod ile ilişkilendir'),
        subtitle: const Text(
            'Çift tıklayınca çalıştır, sağ tıkta "Editör ile aç".',
            style: TextStyle(fontSize: 11)),
        value: d['iliskilendir'] == true,
        onChanged:
            etkin ? (v) => _entegrasyonAyarla('iliskilendir', v ?? false) : null,
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text("TürKod'u PATH'e ekle"),
        subtitle: const Text(
            'Terminalde "turkod dosya.trpy" komutu.',
            style: TextStyle(fontSize: 11)),
        value: d['path'] == true,
        onChanged: etkin ? (v) => _entegrasyonAyarla('path', v ?? false) : null,
      ),
      Text(
        destek
            ? 'Kurulumdaki seçeneklerle aynıdır; değişiklik hemen uygulanır '
                '(Kaydet gerekmez). PATH değişikliği yalnızca yeni açılan '
                'terminallerde geçerli olur.'
            : (d['neden']?.toString() ?? 'Bu cihazda kullanılamıyor.'),
        style: notStili,
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = context.watch<SettingsProvider>();
    if (!settings.loaded || !_formReady) {
      // Ayarlar okunana kadar form gösterilmez (yanlışlıkla boş değerlerle
      // kaydedilmesin); okununca didChangeDependencies formu doldurur.
      return Material(
        color: theme.colorScheme.surface,
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(strokeWidth: 2),
              SizedBox(height: 12),
              Text('Ayarlar okunuyor… Bağlantı kurulunca sayfa açılacak.'),
            ],
          ),
        ),
      );
    }
    _hedefeKaydir();
    final providers = settings.aiSaglayicilar;
    final secili = settings.saglayici(_sag);
    final models = List<String>.from(settings.aiModels[_sag] ?? []);
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
                                              ? 'Bu liste, bilgisayarında kurulu '
                                                  'yazı tiplerinden okundu (${settings.systemFonts.length} font).'
                                              : 'Bilgisayardaki yazı tipi listesi henüz alınamadı; '
                                                  'aşağıda yaygın fontlardan oluşan bir öneri listesi '
                                                  'gösteriliyor. Kurulu farklı bir font varsa adını '
                                                  'doğrudan yazabilirsin; kurulu değilse otomatik '
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
                        if (_autoSave)
                          TextField(
                            controller: _autoSaveInterval,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                                labelText:
                                    'Otomatik kaydetme aralığı (saniye, 5–600)',
                                isDense: true),
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
                          title: const Text('Girinti Kılavuzları'),
                          subtitle: const Text(
                              'Girintili blokların solunda, hangi satırların aynı bloğa ait olduğunu gösteren ince dikey çizgiler.',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool('sutun_cizgileri',
                              fallback: true),
                          onChanged: (v) =>
                              settings.setValueBildir(context, 'sutun_cizgileri', v ?? true),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Mini Harita'),
                          value: settings.getBool('minimap'),
                          onChanged: (v) =>
                              settings.setValueBildir(context, 'minimap', v ?? false),
                        ),
                        Row(children: [
                          const Expanded(
                              child: Text('Girinti genişliği (boşluk)')),
                          SegmentedButton<int>(
                            segments: const [
                              ButtonSegment(value: 2, label: Text('2')),
                              ButtonSegment(value: 4, label: Text('4')),
                              ButtonSegment(value: 8, label: Text('8')),
                            ],
                            selected: {
                              settings.getInt('girinti_boyutu', fallback: 4)
                            },
                            onSelectionChanged: (v) =>
                                settings.setValueBildir(context, 'girinti_boyutu', v.first),
                          ),
                        ]),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Kaydederken biçimlendir'),
                          subtitle: const Text(
                              '.trpy dosyası kaydedilirken girinti ve boşluklar '
                              'düzenlenir (Kodu Biçimlendir ile aynı).',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool('kaydederken_bicimlendir'),
                          onChanged: (v) => settings
                              .setValue('kaydederken_bicimlendir', v ?? false)
                              .catchError((_) {}),
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Girintiyi dosyadan algıla'),
                          subtitle: const Text(
                              'Açık dosya farklı bir girinti kullanıyorsa ona uyulur; '
                              'kapalıysa her zaman yukarıdaki genişlik kullanılır.',
                              style: TextStyle(fontSize: 11)),
                          value:
                              settings.getBool('girinti_algila', fallback: true),
                          onChanged: (v) =>
                              settings.setValueBildir(context, 'girinti_algila', v ?? true),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.keyboard_outlined, size: 16),
                            label: const Text('Klavye Kısayolları…'),
                            onPressed: () => kisayolPenceresiniAc(context),
                          ),
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
                                'de boyutu değiştirebilirsin.',
                                style: TextStyle(
                                    fontSize: 10.5,
                                    color: theme.colorScheme.onSurface
                                        .withOpacity(0.55)),
                              ),
                            ]),
                      ]),
                      _card(context, Icons.tour_outlined, 'Arayüz Turu', [
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Her açılışta göster'),
                          subtitle: const Text(
                              'Program her açıldığında ekrandaki bölümleri '
                              'tanıtan turu başlatır. Kapalıyken tur yalnızca '
                              'ilk açılışta gösterilir.',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool(kTurHerAcilista),
                          onChanged: (v) => settings
                              .setValue(kTurHerAcilista, v ?? false)
                              .catchError((_) {}),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            icon: const Icon(Icons.play_circle_outline, size: 18),
                            label: const Text('Turu şimdi başlat'),
                            onPressed: () => arayuzTurunuBaslat(context),
                          ),
                        ),
                      ]),
                      _card(context, Icons.integration_instructions_outlined,
                          'Sistem Entegrasyonu', _entegrasyonSatirlari(theme)),
                      _card(context, Icons.smart_toy_outlined, 'Kodi',
                          _kodiYetkiSatirlari(theme)),
                      // Yapay zekâ ayarları: her göreve ayrı model atanır
                      // (yerel modeller Eklenti Özellikleri'nden indirilir).
                      KeyedSubtree(
                        key: _gorevlerKey,
                        child: _card(context, Icons.hub_outlined, 'Yapay Zekâ: Görevler', [
                        Text(
                          'Her göreve istediğin modeli ata: farklı sağlayıcılardan farklı '
                          'modeller ya da bilgisayarındaki yerel modeller. Liste "Sağlayıcı • '
                          'Model" biçimindedir; seçim hemen uygulanır.',
                          style: TextStyle(
                              fontSize: 11.5,
                              color: theme.colorScheme.onSurface.withOpacity(0.65)),
                        ),
                        for (final g in kAiGorevleri.entries)
                          _gorevSatiri(settings, g.key, g.value),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Model düşünsün (akıl yürütme)'),
                          subtitle: const Text(
                              'Kapalıyken düşünen modeller düşünmeden, daha hızlı yanıtlar. '
                              'AI panelindeki beyin düğmesiyle aynıdır.',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool('ai_dusunme'),
                          onChanged: (v) => settings
                              .setValue('ai_dusunme', v ?? false)
                              .catchError((_) {}),
                        ),
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                  'Otomatik tamamlama gecikmesi: ${_tamGecikme.round()} ms '
                                  '(yazmayı bıraktıktan sonra)',
                                  style: const TextStyle(fontSize: 12)),
                              Slider(
                                  value: _tamGecikme,
                                  min: 100,
                                  max: 1500,
                                  divisions: 14,
                                  onChanged: (v) => setState(() => _tamGecikme = v),
                                  onChangeEnd: (v) => settings
                                      .setValue('ai_tamamlama_gecikme', v.round())
                                      .catchError((_) {})),
                            ]),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Çok satırlı otomatik tamamlama'),
                          subtitle: const Text(
                              'Kapalıyken yalnızca bulunulan satır tamamlanır (daha hızlı). '
                              'Tab: kabul · Ctrl+→: kelime kelime · Esc: kapat · '
                              'Ctrl+Shift+Boşluk: öneri iste.',
                              style: TextStyle(fontSize: 11)),
                          value: settings.getBool('ai_tamamlama_cok_satir', fallback: true),
                          onChanged: (v) => settings
                              .setValue('ai_tamamlama_cok_satir', v ?? true)
                              .catchError((_) {}),
                        ),
                      ])),
                      _card(context, Icons.cloud_outlined, 'Yapay Zekâ: Modeller', [
                        _mevcutModeller(context, settings),
                        const Divider(height: 18),
                        _bagliSaglayicilar(context, settings),
                        const Divider(height: 18),
                        const Text('Sağlayıcı bağla (sağlayıcı + API anahtarı)',
                            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                        // 200+ sağlayıcı: yazarak aranır.
                        LayoutBuilder(builder: (c, k) {
                          return DropdownMenu<String>(
                            key: ValueKey('sag-${providers.length}'),
                            width: k.maxWidth,
                            controller: _sagCtrl,
                            initialSelection: _sag,
                            enableFilter: true,
                            enableSearch: true,
                            requestFocusOnTap: true,
                            menuHeight: 320,
                            label: Text(
                                'Sağlayıcı (${providers.length}) — yazarak ara'),
                            leadingIcon: Icon(
                                secili?.yerel ?? false
                                    ? Icons.computer
                                    : Icons.cloud_outlined,
                                size: 16),
                            dropdownMenuEntries: [
                              for (final p in providers)
                                if (p.id != 'yerel')
                                DropdownMenuEntry<String>(
                                  value: p.id,
                                  label: p.ad,
                                  leadingIcon: Icon(
                                      p.yerel
                                          ? Icons.computer
                                          : Icons.cloud_outlined,
                                      size: 14),
                                ),
                            ],
                            onSelected: (v) {
                              if (v != null) _saglayiciSec(settings, v);
                            },
                          );
                        }),
                        Text(
                          settings.aiKatalogKaynagi == 'internet'
                              ? 'Sağlayıcı ve model listesi internetten (models.dev) '
                                  'güncel olarak alındı.'
                              : settings.aiKatalogKaynagi == 'disk'
                                  ? 'Sağlayıcı listesi son indirilen katalogdan; '
                                      '"Modelleri Güncelle" ile yenileyebilirsin.'
                                  : 'İnternete bağlanılamadı; kısa bir yedek liste '
                                      'gösteriliyor. "Modelleri Güncelle" ile yeniden dene.',
                          style: TextStyle(
                              fontSize: 10.5,
                              color: theme.colorScheme.onSurface.withOpacity(0.55)),
                        ),
                        if (_sag == 'ozel')
                          TextField(
                            controller: _ozelUrl,
                            decoration: const InputDecoration(
                                labelText:
                                    'API adresi (OpenAI uyumlu, ör. http://127.0.0.1:8000/v1)',
                                isDense: true),
                          ),
                        // Listede olmayan model adı da yazılabilir.
                        LayoutBuilder(builder: (c, k) {
                          return DropdownMenu<String>(
                            key: ValueKey('model-$_sag-${models.length}'),
                            width: k.maxWidth,
                            controller: _modelCtrl,
                            enableFilter: true,
                            requestFocusOnTap: true,
                            menuHeight: 300,
                            label: Text(models.isEmpty
                                ? 'Model (adını yazın)'
                                : 'Model (${models.length}) — seç ya da yaz'),
                            dropdownMenuEntries: [
                              for (final m in models)
                                DropdownMenuEntry<String>(value: m, label: m),
                            ],
                            onSelected: (v) {
                              if (v != null) setState(() => _model = v);
                            },
                          );
                        }),
                        if (secili?.yerel ?? false)
                          Row(children: [
                            Expanded(
                              child: Text(
                                models.isEmpty
                                    ? '${secili!.ad} çalışmıyor ya da yüklü model yok.'
                                    : '${secili!.ad}: ${models.length} yüklü model. '
                                        'Anahtar gerekmez, internet gerekmez.',
                                style: const TextStyle(fontSize: 11.5),
                              ),
                            ),
                            TextButton.icon(
                              icon: const Icon(Icons.download_outlined, size: 16),
                              label: const Text('Model Yöneticisi'),
                              onPressed: () => yerelModelYoneticisiniAc(context),
                            ),
                          ])
                        else
                          TextField(
                            controller: _apiKey,
                            obscureText: true,
                            decoration: InputDecoration(
                              labelText: secili?.anahtarGerekli ?? true
                                  ? 'API Anahtarı (${secili?.ad ?? _sag})'
                                  : 'API Anahtarı (isteğe bağlı)',
                              isDense: true,
                              suffixIcon: (secili?.doc ?? '').isEmpty
                                  ? null
                                  : IconButton(
                                      tooltip: 'Anahtar / belgeler sayfasını aç',
                                      icon: const Icon(Icons.open_in_new, size: 16),
                                      onPressed: () =>
                                          baglantiAc(context, secili!.doc),
                                    ),
                            ),
                          ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: OutlinedButton.icon(
                            icon: _testingAi
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2))
                                : const Icon(Icons.wifi_tethering, size: 16),
                            label: const Text('Bağlantıyı Test Et'),
                            onPressed: _testingAi ? null : _testAi,
                          ),
                        ),
                        Wrap(spacing: 8, runSpacing: 6, children: [
                          FilledButton.icon(
                            icon: _modelGetirilen == _sag
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(strokeWidth: 2))
                                : const Icon(Icons.link, size: 16),
                            label: Text(_modelGetirilen == _sag
                                ? 'Modeller alınıyor…'
                                : 'Bağla ve modelleri seç'),
                            onPressed: _modelGetirilen != null
                                ? null
                                : () => _saglayiciBagla(settings),
                          ),
                          OutlinedButton.icon(
                            icon: const Icon(Icons.add, size: 16),
                            label: const Text('Yalnızca yukarıdaki modeli ekle'),
                            onPressed: () => _modelEkle(settings),
                          ),
                        ]),
                        const Divider(height: 18),
                        const Text('Tüm modeller için ortak ayarlar',
                            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
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
                              labelText: 'En Fazla Token', isDense: true),
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

/// Editörde dalgalı çizgiyle gösterilen bir hata ya da uyarı. [satir]
/// dosyadaki (model) satırdır; [ad] verilmişse satırdaki o ad, yoksa
/// [sutun]daki kelime çizilir.
@immutable
class Sorun {
  final int satir;
  final int? sutun;
  final String? ad;
  final bool hata;
  final String mesaj;
  const Sorun({
    required this.satir,
    this.sutun,
    this.ad,
    required this.hata,
    required this.mesaj,
  });

  static final RegExp _harf = RegExp(r'[A-Za-z0-9_ÇŞĞÜÖİçşğüöı]');

  /// Satır metninde çizilecek [başlangıç, bitiş) aralıkları.
  List<List<int>> araliklar(String satirMetni) {
    final n = satirMetni.length;
    if (n == 0) return const [];
    final ad = this.ad;
    if (ad != null && ad.isNotEmpty) {
      final sonuc = <List<int>>[];
      var i = satirMetni.indexOf(ad);
      while (i >= 0) {
        final once = i > 0 && _harf.hasMatch(satirMetni[i - 1]);
        final son = i + ad.length < n && _harf.hasMatch(satirMetni[i + ad.length]);
        if (!once && !son) sonuc.add([i, i + ad.length]);
        i = satirMetni.indexOf(ad, i + ad.length);
      }
      if (sonuc.isNotEmpty) return sonuc;
    }
    var bas = ((sutun ?? 1) - 1).clamp(0, n - 1).toInt();
    // Hata satır sonundaysa (ör. eksik ':') son karakter çizilir.
    if (bas >= n) bas = n - 1;
    var bit = bas;
    while (bit < n && _harf.hasMatch(satirMetni[bit])) {
      bit++;
    }
    if (bit == bas) {
      // Kelime değilse: satırın kalanı (boşluklar hariç), en az 1 karakter.
      bit = satirMetni.trimRight().length;
      if (bit <= bas) bit = bas + 1;
    }
    return [
      [bas, bit.clamp(bas + 1, n).toInt()]
    ];
  }

  @override
  bool operator ==(Object other) =>
      other is Sorun &&
      other.satir == satir &&
      other.sutun == sutun &&
      other.ad == ad &&
      other.hata == hata &&
      other.mesaj == mesaj;

  @override
  int get hashCode => Object.hash(satir, sutun, ad, hata, mesaj);
}

/// Etkin dosyadaki tüm hata ve uyarıları listeler (Ctrl+Shift+M).
class SorunlarDialog extends StatelessWidget {
  const SorunlarDialog({super.key});
  @override
  Widget build(BuildContext context) {
    final sorunlar = context.watch<UiProvider>().sorunlar;
    final theme = Theme.of(context);
    return AlertDialog(
      title: Text('Sorunlar (${sorunlar.length})'),
      content: SizedBox(
        width: 560,
        height: 340,
        child: sorunlar.isEmpty
            ? const Center(child: Text('Bu dosyada sorun yok. 👍'))
            : ListView.builder(
                itemCount: sorunlar.length,
                itemBuilder: (c, i) {
                  final s = sorunlar[i];
                  return ListTile(
                    dense: true,
                    leading: Icon(
                      s.hata ? Icons.error_outline : Icons.warning_amber,
                      size: 18,
                      color: s.hata
                          ? theme.colorScheme.error
                          : Colors.orange.shade700,
                    ),
                    title: Text(s.mesaj, style: const TextStyle(fontSize: 13)),
                    subtitle: Text('Satır ${s.satir}'),
                    onTap: () => Navigator.pop(context, s.satir),
                  );
                },
              ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat')),
      ],
    );
  }
}

Future<void> sorunlariGoster(BuildContext context) async {
  final satir = await showDialog<int>(
      context: context, builder: (_) => const SorunlarDialog());
  if (satir != null && context.mounted) {
    await dosyadaSatiraGit(context, null, satir);
  }
}

/// Bir TextEditingController'ı pencerenin ömrü boyunca tutan sarmalayıcı:
/// controller pencerenin kendi dispose()'unda bırakılır. showDialog döner
/// dönmez bırakmak, kapanış animasyonu sürerken ekranda olan TextField'ı
/// bozuyordu.
class DenetleyiciliDialog extends StatefulWidget {
  final String metin;
  final int? secimSonu;
  final Widget Function(BuildContext context, TextEditingController ctrl)
      builder;
  const DenetleyiciliDialog(
      {super.key, required this.metin, this.secimSonu, required this.builder});
  @override
  State<DenetleyiciliDialog> createState() => _DenetleyiciliDialogState();
}

class _DenetleyiciliDialogState extends State<DenetleyiciliDialog> {
  late final TextEditingController _ctrl = TextEditingController(
      text: widget.metin)
    ..selection = widget.secimSonu == null
        ? TextSelection.collapsed(offset: widget.metin.length)
        : TextSelection(baseOffset: 0, extentOffset: widget.secimSonu!);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.builder(context, _ctrl);
}

/// Tek satırlık metin isteyen pencere. Controller'ı pencerenin kendisi tutar
/// ve kendi dispose()'unda bırakır: showDialog döner dönmez bırakmak, kapanış
/// animasyonu sürerken hâlâ ekranda olan TextField'ı bozuyordu ("used after
/// being disposed" / "_dependents.isEmpty").
class MetinGirisDialog extends StatefulWidget {
  final String baslik;
  final String baslangic;
  final String? etiket;
  final String? ipucu;
  final String dugme;
  final bool esGenislik;
  const MetinGirisDialog({
    super.key,
    required this.baslik,
    this.baslangic = '',
    this.etiket,
    this.ipucu,
    this.dugme = 'Tamam',
    this.esGenislik = false,
  });
  @override
  State<MetinGirisDialog> createState() => _MetinGirisDialogState();
}

class _MetinGirisDialogState extends State<MetinGirisDialog> {
  late final TextEditingController _girdi =
      TextEditingController(text: widget.baslangic)
        ..selection = TextSelection(
            baseOffset: 0, extentOffset: widget.baslangic.length);

  @override
  void dispose() {
    _girdi.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.baslik),
      content: TextField(
        controller: _girdi,
        autofocus: true,
        style: widget.esGenislik
            ? const TextStyle(fontFamily: kMonoFontFamily)
            : null,
        decoration: InputDecoration(
            labelText: widget.etiket, helperText: widget.ipucu),
        onSubmitted: (v) => Navigator.pop(context, v),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Vazgeç')),
        FilledButton(
            onPressed: () => Navigator.pop(context, _girdi.text),
            child: Text(widget.dugme)),
      ],
    );
  }
}

/// F2: imleçteki adı dosyanın her yerinde değiştirir.
Future<void> adiDegistir(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final eski = imlectekiKelime(ed.uiController);
  if (eski == null || !RegExp(r'^[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*$')
      .hasMatch(eski)) {
    showAppSnackbar(context, 'Önce değiştirilecek adın üzerine tıkla.',
        kind: SnackKind.info);
    return;
  }
  final yeni = (await showDialog<String>(
    context: context,
    builder: (_) => MetinGirisDialog(
      baslik: "'$eski' adını değiştir",
      baslangic: eski,
      etiket: 'Yeni ad',
      dugme: 'Değiştir',
    ),
  ))
      ?.trim();
  if (yeni == null || yeni.isEmpty || yeni == eski || !context.mounted) return;
  // İmlecin konumu (1 tabanlı) gönderilir: yerel bir değişkense backend
  // yalnızca o fonksiyonda değiştirir (eskiden başka fonksiyonlardaki aynı
  // adlı yereller de değişiyordu).
  final kod = ed.activeContent.value;
  final ofs = ed.caretOffsetProvider?.call();
  int? satir, sutun;
  if (ofs != null && ofs >= 0 && ofs <= kod.length) {
    final once = kod.substring(0, ofs);
    satir = '\n'.allMatches(once).length + 1;
    sutun = ofs - (once.lastIndexOf('\n') + 1) + 1;
  }
  try {
    final r = await context.read<BackendService>().call('ad_degistir', {
      'kod': kod,
      'eski': eski,
      'yeni': yeni,
      if (satir != null && sutun != null) ...{'satir': satir, 'sutun': sutun},
    });
    final yeniKod = r['kod']?.toString();
    if (yeniKod == null || !context.mounted) return;
    ed.unfoldAll?.call();
    ed.replaceActiveContent(yeniKod);
    showAppSnackbar(context, "'$eski' → '$yeni' (${r['sayi']} yer)",
        kind: SnackKind.success);
  } on BackendException catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, e.message, kind: SnackKind.error);
    }
  }
}

/// Shift+Alt+F: etkin dosyayı biçimlendirir (girinti, boşluklar).
Future<void> koduBicimlendir(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final tab = ed.activeTab;
  if (tab == null || ozelSekmeMi(tab.path) || tab.isPdf) return;
  try {
    final r = await context
        .read<BackendService>()
        .call('kodu_bicimlendir', {'kod': ed.activeContent.value});
    if (!context.mounted) return;
    if (r['degisti'] != true) {
      showAppSnackbar(context, 'Kod zaten düzenli', kind: SnackKind.info);
      return;
    }
    ed.unfoldAll?.call();
    ed.replaceActiveContent(r['kod']?.toString() ?? ed.activeContent.value);
    showAppSnackbar(context, 'Kod biçimlendirildi', kind: SnackKind.success);
  } on BackendException catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, e.message, kind: SnackKind.error);
    }
  }
}

/// Bölünmüş görünümün sağ bölmesi: seçilen sekmeyi sözdizimi renkli olarak
/// gösterir ve düzenlenebilir. Değişiklikler aynı sekmeye yazılır; sol
/// editörde de aynı dosya açıksa iki taraf eşit kalır.
class YanEditor extends StatefulWidget {
  final String tabId;
  const YanEditor({super.key, required this.tabId});
  @override
  State<YanEditor> createState() => _YanEditorState();
}

class _YanEditorState extends State<YanEditor> {
  late final EditorProvider _ed = context.read<EditorProvider>();
  late final re.CodeLineEditingController _ctrl;
  final re.CodeScrollController _kaydirma = re.CodeScrollController();
  bool _yaziyor = false;
  AppSyntaxPalette _palet = AppSyntaxPalette.fallback;

  /// Bölmede gösterilebilecek metin sekmesi. PDF ve özel sekmeler (Ayarlar,
  /// Tarayıcı) bölmede açılmaz: eskiden PDF'in boş "metni" düzenlenebiliyor,
  /// PDF sekmesi kirli görünüp kapatırken "Kaydet" ile hiç kapanmıyordu.
  EditorTab? get _sekme {
    for (final t in _ed.tabs) {
      if (t.id == widget.tabId) {
        return t.isPdf || ozelSekmeMi(t.path) ? null : t;
      }
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _ctrl = re.CodeLineEditingController(
      spanBuilder: ({
        required context,
        required index,
        required codeLine,
        required textSpan,
        required style,
      }) {
        final palette = _palet;
        return TextSpan(
          style: style,
          children:
              SyntaxHighlightingController._tokenize(codeLine.text, palette, style),
        );
      },
    );
    _ctrl.text = _sekme?.content ?? '';
    _ed.addListener(_disaridanDegisti);
    // updateContent, sekme zaten kirliyse notifyListeners çağırmaz; ana
    // editördeki her tuş vuruşu yalnızca activeContent'ten duyulur. Bu
    // dinlenmezse yan bölme bayat metni sekmeye geri yazar (veri kaybı).
    _ed.activeContent.addListener(_disaridanDegisti);
  }

  @override
  void dispose() {
    _ed.activeContent.removeListener(_disaridanDegisti);
    _ed.removeListener(_disaridanDegisti);
    _ctrl.dispose();
    _kaydirma.dispose();
    super.dispose();
  }

  void _disaridanDegisti() {
    final t = _sekme;
    if (t == null) {
      // Sekme kapandı: bölme de kapanır.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.read<UiProvider>().yanSekmeAyarla(null);
      });
      return;
    }
    if (_yaziyor || t.content == _ctrl.text) return;
    final sel = _ctrl.selection;
    _ctrl.text = t.content;
    final satirSayisi = _ctrl.codeLines.length;
    if (sel.baseIndex < satirSayisi) {
      final uzunluk = _ctrl.codeLines[sel.baseIndex].text.length;
      _ctrl.selection = re.CodeLineSelection.collapsed(
          index: sel.baseIndex, offset: math.min(sel.baseOffset, uzunluk));
    }
    if (mounted) setState(() {});
  }

  void _degisti(re.CodeLineEditingValue v) {
    final t = _sekme;
    if (t == null || t.content == _ctrl.text) return;
    _yaziyor = true;
    try {
      _ed.replaceContentOf(t.id, _ctrl.text);
    } finally {
      _yaziyor = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    _palet = theme.extension<AppSyntaxPalette>() ?? AppSyntaxPalette.fallback;
    final settings = context.watch<SettingsProvider>();
    final sekmeler = context
        .select<EditorProvider, List<EditorTab>>((e) => e.tabs)
        .where((t) => !ozelSekmeMi(t.path) && !t.isPdf)
        .toList();
    final secili = _sekme;
    final boyut = settings.getDouble('yazi_boyutu', fallback: 14);
    final font = settings.getString('yazi_tipi', fallback: 'Consolas');
    return Container(
      color: theme.colorScheme.surface,
      child: Column(children: [
        Container(
          height: 30,
          color: theme.colorScheme.surfaceContainer,
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Row(children: [
            const Icon(Icons.vertical_split, size: 14),
            const SizedBox(width: 6),
            Expanded(
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  isDense: true,
                  isExpanded: true,
                  value: secili?.id,
                  style: theme.textTheme.bodySmall,
                  items: [
                    for (final t in sekmeler)
                      DropdownMenuItem(
                          value: t.id,
                          child: Text('${t.name}${t.dirty ? ' •' : ''}',
                              overflow: TextOverflow.ellipsis)),
                  ],
                  onChanged: (id) =>
                      context.read<UiProvider>().yanSekmeAyarla(id),
                ),
              ),
            ),
            IconButton(
              tooltip: 'Bölmeyi kapat',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close, size: 14),
              onPressed: () => context.read<UiProvider>().yanSekmeAyarla(null),
            ),
          ]),
        ),
        Expanded(
          child: secili == null
              ? const SizedBox.shrink()
              : re.CodeEditor(
                  controller: _ctrl,
                  scrollController: _kaydirma,
                  onChanged: _degisti,
                  wordWrap: settings.getBool('kelime_sar'),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                  style: re.CodeEditorStyle(
                    fontSize: boyut,
                    fontFamily: font,
                    fontHeight: 1.4,
                    textColor: theme.colorScheme.onSurface,
                    backgroundColor: theme.colorScheme.surface,
                    selectionColor:
                        theme.colorScheme.primary.withValues(alpha: 0.5),
                    cursorColor: theme.colorScheme.primary,
                  ),
                  indicatorBuilder:
                      (context, editingController, chunkController, notifier) =>
                          re.DefaultCodeLineNumber(
                    controller: editingController,
                    notifier: notifier,
                    textStyle: TextStyle(
                      fontFamily: font,
                      fontSize: boyut,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ),
        ),
      ]),
    );
  }
}

/// [yol] dosyasını (null ise etkin sekmeyi) açar ve dosyadaki [satir]a gider.
Future<void> dosyadaSatiraGit(BuildContext context, String? yol, int satir) async {
  final ed = context.read<EditorProvider>();
  void git() {
    final reveal = ed.revealModelLine;
    if (reveal != null) {
      reveal(satir);
    } else if (ed.uiController != null) {
      jumpToLineIn(ed.uiController!, satir);
    }
  }

  if (yol == null || ed.activeTab?.path == yol) {
    git();
    return;
  }
  await ed.openFile(yol, context: context);
  // Sekme değişince editör içeriği bir sonraki karede yüklenir.
  WidgetsBinding.instance.addPostFrameCallback(
      (_) => WidgetsBinding.instance.addPostFrameCallback((_) => git()));
  WidgetsBinding.instance.ensureVisualUpdate();
}

/// İmlecin üzerindeki (ya da hemen solundaki) tanımlayıcı.
String? imlectekiKelime(TextEditingController? ctrl) {
  if (ctrl == null) return null;
  final t = ctrl.text;
  final sel = ctrl.selection;
  if (!sel.isValid) return null;
  if (!sel.isCollapsed) {
    final secili = t.substring(sel.start, sel.end).trim();
    return secili.isEmpty ? null : secili;
  }
  final harf = RegExp(r'[A-Za-z0-9_ÇŞĞÜÖİçşğüöı]');
  var bas = sel.baseOffset.clamp(0, t.length).toInt();
  var son = bas;
  while (bas > 0 && harf.hasMatch(t[bas - 1])) {
    bas--;
  }
  while (son < t.length && harf.hasMatch(t[son])) {
    son++;
  }
  if (son <= bas) return null;
  return t.substring(bas, son);
}

/// F12 / Tanıma Git: imleçteki adın tanımlandığı satıra (gerekirse yerel
/// .trpy modülüne) gider.
Future<void> tanimaGit(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final ad = imlectekiKelime(ed.uiController);
  if (ad == null) {
    showAppSnackbar(context, 'Önce bir adın üzerine tıkla.',
        kind: SnackKind.info);
    return;
  }
  final yol = ed.activeTab?.path;
  try {
    final r = await context.read<BackendService>().call('tanim_bul', {
      'kod': ed.activeContent.value,
      'ad': ad,
      if (yol != null && !yol.startsWith('untitled:') && !ozelSekmeMi(yol))
        'dosya': yol,
    });
    final satir = (r['satir'] as num?)?.toInt();
    if (satir == null || !context.mounted) return;
    await dosyadaSatiraGit(context, r['yol']?.toString(), satir);
  } on BackendException catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, e.message, kind: SnackKind.info);
    }
  } catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, 'Tanım bulunamadı: $e', kind: SnackKind.error);
    }
  }
}

/// Proje klasöründeki tüm dosyalarda arama (Ctrl+Shift+F).
class DosyalardaAraDialog extends StatefulWidget {
  final String? baslangic;
  const DosyalardaAraDialog({super.key, this.baslangic});
  @override
  State<DosyalardaAraDialog> createState() => _DosyalardaAraDialogState();
}

class _DosyalardaAraDialogState extends State<DosyalardaAraDialog> {
  late final TextEditingController _sorgu =
      TextEditingController(text: widget.baslangic ?? '');
  bool _buyukKucuk = false, _tamKelime = false, _regex = false;
  bool _yukleniyor = false, _kesildi = false;
  String? _hata;
  List<Map<String, dynamic>> _sonuclar = const [];
  Timer? _gecikme;

  @override
  void initState() {
    super.initState();
    if (_sorgu.text.isNotEmpty) _ara();
  }

  @override
  void dispose() {
    _gecikme?.cancel();
    _sorgu.dispose();
    super.dispose();
  }

  void _gecikmeliAra() {
    _gecikme?.cancel();
    _gecikme = Timer(const Duration(milliseconds: 350), _ara);
  }

  /// Her aramada artar; yalnızca en son isteğin yanıtı gösterilir. Eskiden
  /// yalnızca sorgu metnine bakılıyordu: "Aa" / "Tam kelime" değiştirilince
  /// eski seçeneklerle gelen geç yanıt yenisinin üzerine yazılıyordu.
  int _istekNo = 0;

  Future<void> _ara() async {
    final no = ++_istekNo;
    final sorgu = _sorgu.text;
    if (sorgu.isEmpty) {
      // Arama sürerken kutu temizlendiyse gösterge sonsuza dek dönmesin.
      setState(() {
        _sonuclar = const [];
        _hata = null;
        _kesildi = false;
        _yukleniyor = false;
      });
      return;
    }
    setState(() {
      _yukleniyor = true;
      _hata = null;
    });
    try {
      final r = await context.read<BackendService>().call('dosyalarda_ara', {
        'dizin': context.read<FileTreeProvider>().root?.path,
        'sorgu': sorgu,
        'buyuk_kucuk': _buyukKucuk,
        'tam_kelime': _tamKelime,
        'regex': _regex,
      });
      if (!mounted || no != _istekNo) return;
      setState(() {
        _sonuclar = [
          for (final x in (r['sonuclar'] as List? ?? const []))
            if (x is Map) Map<String, dynamic>.from(x)
        ];
        _kesildi = r['kesildi'] == true;
        _yukleniyor = false;
      });
    } on BackendException catch (e) {
      if (!mounted || no != _istekNo) return;
      setState(() {
        _hata = e.message;
        _sonuclar = const [];
        _yukleniyor = false;
      });
    } catch (e) {
      if (!mounted || no != _istekNo) return;
      setState(() {
        _hata = '$e';
        _yukleniyor = false;
      });
    }
  }

  Widget _secenek(String etiket, String ipucu, bool deger, ValueChanged<bool> d) {
    return Tooltip(
      message: ipucu,
      child: FilterChip(
        label: Text(etiket, style: const TextStyle(fontSize: 12)),
        selected: deger,
        visualDensity: VisualDensity.compact,
        onSelected: (v) {
          setState(() => d(v));
          _ara();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final kok = context.read<FileTreeProvider>().root?.path;
    final dosyaSayisi = _sonuclar.map((s) => s['yol']).toSet().length;
    return AlertDialog(
      title: const Text('Dosyalarda Ara'),
      content: SizedBox(
        width: 640,
        height: 440,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _sorgu,
              autofocus: true,
              decoration: InputDecoration(
                hintText: 'Aranacak metin',
                prefixIcon: const Icon(Icons.search, size: 18),
                isDense: true,
                helperText: kok == null ? 'Önce bir klasör aç.' : kok,
                helperMaxLines: 1,
              ),
              onChanged: (_) => _gecikmeliAra(),
              onSubmitted: (_) => _ara(),
            ),
            const SizedBox(height: 8),
            Wrap(spacing: 6, children: [
              _secenek('Aa', 'Büyük/küçük harf duyarlı', _buyukKucuk,
                  (v) => _buyukKucuk = v),
              _secenek('Tam kelime', 'Yalnızca tam kelime', _tamKelime,
                  (v) => _tamKelime = v),
              _secenek('.*', 'Düzenli ifade', _regex, (v) => _regex = v),
            ]),
            const SizedBox(height: 8),
            if (_yukleniyor) const LinearProgressIndicator(minHeight: 2),
            if (_hata != null)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text(_hata!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            if (_hata == null && !_yukleniyor && _sorgu.text.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  _sonuclar.isEmpty
                      ? 'Sonuç yok.'
                      : '$dosyaSayisi dosyada ${_sonuclar.length} sonuç'
                          '${_kesildi ? ' (ilk sonuçlar gösteriliyor)' : ''}',
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            Expanded(
              child: ListView.builder(
                itemCount: _sonuclar.length,
                itemBuilder: (c, i) {
                  final s = _sonuclar[i];
                  final yol = s['yol']?.toString() ?? '';
                  final satir = (s['satir'] as num? ?? 1).toInt();
                  final gosterilen = kok != null && yol.startsWith(kok)
                      ? yol.substring(kok.length).replaceFirst(RegExp(r'^[\\/]'), '')
                      : yol;
                  return ListTile(
                    dense: true,
                    visualDensity: VisualDensity.compact,
                    title: Text(s['metin']?.toString() ?? '',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontFamily: 'Consolas')),
                    subtitle: Text('$gosterilen : $satir',
                        style: const TextStyle(fontSize: 11)),
                    // Pencere kapandıktan sonra açan bağlam dosyaya gider.
                    onTap: () => Navigator.pop(
                        context, (yol: yol, satir: satir)),
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Kapat')),
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
      title: const Text('Yapılacaklar (YAPILACAK / TODO)'),
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
                child: Center(
                    child: Text('Yapılacak notu bulunamadı.\n'
                        'Yoruma "# YAPILACAK: ..." yazabilirsin.',
                        textAlign: TextAlign.center)));
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
    return Future.wait([
      backend.call('imza_dogrula'),
      backend.call('dosya_hash'),
      // Eski bir backend 'surum'u bilmiyorsa pencere yine açılsın.
      backend.call('surum').catchError((_) => <String, dynamic>{}),
    ]);
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
          final surum = snap.data![2]['surum']?.toString();
          return SizedBox(
            width: 440,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Profesyonel Türkçe Python Editörü',
                  style: TextStyle(fontSize: 13)),
              if (surum != null && surum.isNotEmpty) ...[
                const SizedBox(height: 4),
                SelectableText('Sürüm $surum',
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600)),
              ],
              const SizedBox(height: 4),
              const Text('© 2026 Yusuf Tandoğan — MIT Lisansı',
                  style: TextStyle(fontSize: 12)),
              const SizedBox(height: 8),
              const YardimBaglantilari(),
              const SizedBox(height: 8),
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
        .where((a) =>
            a.gorunur(context) &&
            a.label.toLowerCase().contains(_filter.toLowerCase()))
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
                  trailing: Text(OzelKisayollar.goster(a.shortcut),
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
    // Ayarlar sekmesinde önceki dosyanın sözdizimi durumu ve imleç konumu
    // gösterilmez (eskiden Ayarlar açıkken başka dosyanın hatası yazıyordu).
    // Hiç sekme yokken (karşılama ekranı) de imleç konumu gösterilmez.
    final ayarlarSekmesi = ed.activeTab == null ||
        ozelSekmeMi(ed.activeTab?.path) ||
        ed.activeTab!.isPdf;
    final statusIds = [
      'tools.stats',
      'tools.todo',
      'tools.codesearch',
      'help.about'
    ];
    return Container(
      height: 26,
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        border: Border(
            top: BorderSide(color: theme.colorScheme.outlineVariant)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(children: [
        const DurumRozeti(),
        const SizedBox(width: 8),
        // Expanded + sağa hizalama: öğeler her zaman en sağda durur. (Önceki
        // Spacer + Flexible(flex: 4) düzeni, metin kısa olduğunda boş alanı
        // dağıtmadığı için satırı ortaya kaydırıyordu.) Uzun hata/uyarı metni
        // "…" ile kısalır; tamamı fare üzerine gelince görünür.
        Expanded(
          child: ui.syntaxStatus.isEmpty || ayarlarSekmesi
              ? const SizedBox.shrink()
              : Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                    padding: const EdgeInsets.only(right: 12),
                    child: Tooltip(
                      message: ui.syntaxTooltip.isNotEmpty
                          ? '${ui.syntaxTooltip}\n(Tıklayın: Sorunlar listesi)'
                          : ui.syntaxStatus,
                      waitDuration: const Duration(milliseconds: 400),
                      child: InkWell(
                        onTap: ui.sorunlar.isEmpty
                            ? null
                            : () => sorunlariGoster(context),
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
        ),
        if (context.select<SettingsProvider, bool>(
            (s) => s.eklentiYuklu(kEklentiOdak))) ...[
          const OdakZamanlayici(),
          const SizedBox(width: 8),
        ],
        // Satır gibi sütun da 1'den başlar (eskiden "Satır 1, Sütun 0").
        if (!ayarlarSekmesi) ...[
          Text('Satır ${ui.cursorLine}, Sütun ${ui.cursorColumn + 1}',
              style: TextStyle(
                  fontSize: 11,
                  color: theme.colorScheme.onSurface.withOpacity(0.8))),
          const SizedBox(width: 12),
        ],
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
        const SizedBox(width: 8),
        for (final id in statusIds)
          Builder(builder: (c) {
            final a = findAction(actions, id);
            if (a == null || a.icon == null) return const SizedBox.shrink();
            return IconButton(
              tooltip: a.label,
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 24, minHeight: 22),
              icon: Icon(a.icon, size: 14),
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
          u.solPanel,
          u.showAi,
          u.showTerminal,
          u.sidebarWidth,
          u.aiWidth,
          u.terminalHeight,
          u.yanSekmeId,
          u.panelSirasi,
        ));
    final activePath =
        context.select<EditorProvider, String?>((e) => e.activeTab?.path);
    // Ayarlar ve Tarayıcı: terminal ve yan editör yoktur.
    final isSettings = ozelSekmeMi(activePath);
    // Her sekmenin kendi terminali: panel sekmeye göre yeniden kurulur
    // (yarım yazılmış komut, kaydırma konumu sekmeler arasında karışmaz).
    final terminalOturumu =
        context.select<TerminalProvider, String>((t) => t.aktifOturum);
    return Column(children: [
      AppTitleBar(actions: actions),
      Expanded(
        child: LayoutBuilder(builder: (context, kisit) {
        // Panel boyutları pencereye sığdırılır: geniş kenar paneliyle AI
        // paneli küçük (ör. yarım ekran) bir pencerede editörü sıfır
        // genişliğe itip taşma (overflow) şeritleri oluşturuyordu.
        const minEditorGenislik = 260.0;
        // Tutamaçlar + sol aktivite çubuğu (44 px).
        const tutamaclar = 12.0 + 48.0;
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
        final sira = ui.panelSirasi;
        final editorSirasi = sira.indexOf('editor');
        final gezginBolgesi = _PanelBirakmaAlani(
          id: 'gezgin',
          child: AnimatedContainer(
            key: TurHedefleri.gezgin,
            duration: kAnim,
            curve: kAnimCurve,
            width: kenar,
            child: ClipRect(
              child: OverflowBox(
                alignment: Alignment.topLeft,
                minWidth: kenarIc,
                maxWidth: kenarIc,
                child: ui.solPanel == 'eklentiler'
                    ? const EklentilerPaneli()
                    : const FileTreePanel(),
              ),
            ),
          ),
        );
        final editorBolgesi = Expanded(
          child: _PanelBirakmaAlani(
            id: 'editor',
            child: LayoutBuilder(builder: (context, ic) {
              // Terminal yüksekliği de sığdırılır (araç çubuğu + sekmeler +
              // en az 100 px editör kalacak şekilde).
              final terminalH = math.max(
                  0.0,
                  math.min(ui.terminalHeight,
                      ic.maxHeight - 46 - 1 - 47 - 6 - 100));
              return Column(
                  mainAxisAlignment: MainAxisAlignment.start, children: [
              TopToolbar(actions: actions),
              KeyedSubtree(
                  key: TurHedefleri.sekmeler, child: const EditorTabsBar()),
              Expanded(
                child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(
                        child: KeyedSubtree(
                          key: TurHedefleri.editor,
                          child: activePath == kTarayiciPath
                              ? const TarayiciSekmesi()
                              : isSettings
                              ? const SettingsPage()
                              : activePath == null
                                  // Hiç sekme yokken boş editör yerine
                                  // karşılama ekranı.
                                  ? const KarsilamaEkrani()
                                  : pdfYoluMu(activePath)
                                      // PDF: sayfa görüntüleyici.
                                      ? PdfSekmesi(
                                          key: ValueKey(activePath),
                                          yol: activePath)
                                      : CodeEditor(
                                          key: ValueKey(activePath),
                                          sekmeYolu: activePath),
                        ),
                      ),
                      if (ui.yanSekmeId != null && !isSettings) ...[
                        VerticalDivider(
                            width: 1,
                            color: Theme.of(context).colorScheme.outlineVariant),
                        Expanded(
                          child: YanEditor(
                              key: ValueKey(ui.yanSekmeId),
                              tabId: ui.yanSekmeId!),
                        ),
                      ],
                    ]),
              ),
              if (ui.showTerminal && !isSettings) ...[
                _VGrip((d) => ui.setTerminalHeight(ui.terminalHeight - d)),
                AnimatedContainer(
                  key: TurHedefleri.terminal,
                  duration: kAnim,
                  curve: kAnimCurve,
                  height: ui.showTerminal ? terminalH : 0,
                  child: ClipRect(
                    child: OverflowBox(
                        alignment: Alignment.topLeft,
                        minHeight: terminalH,
                        maxHeight: terminalH,
                        child: TerminalPanel(
                            key: ValueKey('terminal:$terminalOturumu'))),
                  ),
                ),
              ],
            ]);
            }),
          ),
        );
        final aiBolgesi = _PanelBirakmaAlani(
          id: 'ai',
          child: AnimatedContainer(
            key: TurHedefleri.ai,
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
        );
        // Yan panelin tutamacı editöre bakan kenarındadır; panel editörün
        // sağındaysa sağa çekmek paneli daraltır.
        Widget? tutamac(String id) {
          final acik = id == 'gezgin' ? ui.showExplorer : ui.showAi;
          if (!acik) return null;
          final solda = sira.indexOf(id) < editorSirasi;
          return _HGrip((d) {
            final fark = solda ? d : -d;
            if (id == 'gezgin') {
              ui.setSidebarWidth(ui.sidebarWidth + fark);
            } else {
              ui.setAiWidth(ui.aiWidth + fark);
            }
          });
        }

        final cocuklar = <Widget>[
          // Aktivite çubuğu her zaman en solda.
          const AktiviteCubugu(),
        ];
        for (var k = 0; k < sira.length; k++) {
          final id = sira[k];
          if (id == 'editor') {
            cocuklar.add(editorBolgesi);
            continue;
          }
          final bolge = id == 'gezgin' ? gezginBolgesi : aiBolgesi;
          final t = tutamac(id);
          if (k < editorSirasi) {
            cocuklar.add(bolge);
            if (t != null) cocuklar.add(t);
          } else {
            if (t != null) cocuklar.add(t);
            cocuklar.add(bolge);
          }
        }
        // Kodi bütün çalışma alanının üstünde durur (sürüklenip her yere
        // taşınabilir). Varsayılan yeri: editörün sağ altı, terminalin üstü.
        var sagdaKalan = 0.0;
        for (var k = editorSirasi + 1; k < sira.length; k++) {
          final id = sira[k];
          if (id == 'gezgin' ? ui.showExplorer : ui.showAi) {
            sagdaKalan += (id == 'gezgin' ? kenar : aiG) + 8;
          }
        }
        final terminalAcik = ui.showTerminal && !isSettings;
        final terminalH = math.max(
            0.0, math.min(ui.terminalHeight, kisit.maxHeight - 46 - 1 - 47 - 6 - 100));
        return Stack(children: [
          Positioned.fill(
            child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: cocuklar),
          ),
          Positioned.fill(
            child: KodiKatmani(
              varsayilanSag: sagdaKalan + 22,
              varsayilanAlt: terminalAcik ? terminalH + 14 : 8,
            ),
          ),
        ]);
        }),
      ),
      KeyedSubtree(
          key: TurHedefleri.durum, child: StatusBar(actions: actions)),
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

  // Panel düzeni: ayarlar yüklenince bir kez uygulanır; sonra değiştikçe
  // (sürükleme bitince) kısa bir gecikmeyle kaydedilir.
  bool _duzenUygulandi = false;
  Timer? _duzenTimer;
  String _sonDuzen = '';
  SettingsProvider? _ayarlar;
  UiProvider? _uiDuzen;

  void _ayarlarDegisti() {
    final s = _ayarlar;
    // Otomatik kayıt aralığı değiştiyse zamanlayıcı hemen yeniden kurulur
    // (eskiden yeni değer, eski aralık dolunca — en geç 10 dk sonra — geçiyordu).
    if (s != null && s.loaded && _otoKayitAraligi() != _kurulanAralik) {
      _scheduleAutoSave();
    }
    if (_duzenUygulandi || s == null || !s.loaded) return;
    _duzenUygulandi = true;
    final kayitli = s.get<dynamic>('panel_duzeni');
    if (kayitli is Map) {
      _sonDuzen = jsonEncode(kayitli);
      _uiDuzen?.applyLayout(kayitli);
    }
  }

  void _duzenDegisti() {
    if (!_duzenUygulandi) return;
    final ui = _uiDuzen;
    if (ui == null) return;
    final simdi = jsonEncode(ui.layoutSnapshot());
    if (simdi == _sonDuzen) return;
    _duzenTimer?.cancel();
    _duzenTimer = Timer(const Duration(milliseconds: 800), () {
      if (!mounted) return;
      _sonDuzen = simdi;
      _ayarlar
          ?.setValues({'panel_duzeni': ui.layoutSnapshot()})
          .catchError((_) {});
    });
  }
  // command-id -> activator eşlemesi build() içinde her seferinde tazelenir;
  // asıl tuş dinleyicisi ise odak nerede olursa olsun (kod editöründeki
  // TextField dahil) tetiklensin diye donanım seviyesinde çalışır.
  Map<ShortcutActivator, VoidCallback> _shortcuts = {};

  // Pencere kapatılırken (X, Alt+F4) kaydedilmemiş dosya değişiklikleri
  // sorulur. Eskiden oturum yalnızca dosya YOLLARINI sakladığından açık bir
  // dosyada yapılan kaydedilmemiş değişiklikler sessizce kayboluyordu.
  // onResume: pencere yeniden odaklanınca başka programların değiştirdiği
  // açık dosyalar denetlenir.
  late final AppLifecycleListener _cikisDinleyici = AppLifecycleListener(
      onExitRequested: _cikisIstendi,
      onResume: () {
        if (mounted) unawaited(context.read<EditorProvider>().diskiDenetle());
      });

  void _kayitUyarisi(String mesaj) {
    if (mounted) showAppSnackbar(context, mesaj, kind: SnackKind.info);
  }

  /// Kaydedilecek dosya başka bir program tarafından değiştirilmişse sorar.
  Future<bool> _diskCakismasiSor(EditorTab t) async {
    if (!mounted) return false;
    final secim = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Dosya diskte değişti'),
        content: Text('"${t.name}" siz açtıktan sonra başka bir program '
            'tarafından değiştirildi.\n\nDiskteki sürümün üzerine yazılsın mı?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, 'iptal'),
              child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, 'yaz'),
              child: const Text('Üzerine Yaz')),
        ],
      ),
    );
    return secim == 'yaz';
  }

  /// Kaydedilecek dosya diskten silinmiş / taşınmışsa yeniden oluşturulsun mu?
  Future<bool> _silinenDosyaSor(EditorTab t) async {
    if (!mounted) return false;
    final secim = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Dosya artık diskte yok'),
        content: Text('"${t.name}" silinmiş ya da başka bir yere taşınmış.\n\n'
            'Yazdıkların kaybolmasın diye dosya aynı yerde yeniden '
            'oluşturulsun mu?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, 'iptal'),
              child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, 'yaz'),
              child: const Text('Yeniden Oluştur')),
        ],
      ),
    );
    return secim == 'yaz';
  }

  /// Farklı Kaydet'in hedefi kaydedilmemiş başka bir sekmede açık.
  Future<bool> _farkliKaydetHedefKirliSor(EditorTab digeri) async {
    if (!mounted) return false;
    final secim = await showDialog<String>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Dosya başka bir sekmede açık'),
        content: Text('"${digeri.name}" başka bir sekmede açık ve orada '
            'kaydedilmemiş değişiklikler var.\n\nÜzerine yazarsan o sekme '
            'kapanır ve oradaki değişiklikler kaybolur. Üzerine yazılsın mı?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dc, 'iptal'),
              child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(dc, 'yaz'),
              child: const Text('Üzerine Yaz')),
        ],
      ),
    );
    return secim == 'yaz';
  }
  bool _cikisSoruluyor = false;

  ValueNotifier<int>? _kurtarma;
  void _kurtarmaBildir() {
    final n = _kurtarma?.value ?? 0;
    if (n <= 0 || !mounted) return;
    _kurtarma!.value = 0;
    showAppSnackbar(
        context,
        'Program beklenmedik şekilde kapanmıştı: $n dosyadaki kaydedilmemiş '
        'değişiklik kurtarıldı. Kaydetmeyi unutma.',
        kind: SnackKind.success);
  }

  Future<AppExitResponse> _cikisIstendi() async {
    if (!mounted) return AppExitResponse.exit;
    final ed = context.read<EditorProvider>();
    final kirli = ed.tabs
        .where((t) =>
            t.dirty &&
            !ozelSekmeMi(t.path) &&
            !t.path.startsWith('untitled:'))
        .toList();
    if (_cikisSoruluyor) return AppExitResponse.cancel;
    if (kirli.isEmpty) {
      // Adsız sekmelerin içeriği oturumda saklanır (yeniden açılınca gelir).
      final ok = await ed.saveSessionNow();
      if (ok || ed.adsizIcerikliSekmeler.isEmpty) return AppExitResponse.exit;
      return _oturumYazilamadiSor(ed);
    }
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
                child: const Text('Vazgeç')),
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
        final ok = await ed.saveSessionNow(yedekler: false);
        if (ok || ed.adsizIcerikliSekmeler.isEmpty) {
          return AppExitResponse.exit;
        }
        _cikisSoruluyor = false;
        return await _oturumYazilamadiSor(ed);
      }
      return AppExitResponse.cancel;
    } finally {
      _cikisSoruluyor = false;
    }
  }

  /// Oturum yazılamadı (backend bağlantısı yok): adsız sekmelerdeki yazılar
  /// yalnızca oturumda saklandığından pencere kapanırsa kaybolur. Eskiden
  /// hata yutuluyor ve program sormadan kapanıyordu.
  Future<AppExitResponse> _oturumYazilamadiSor(EditorProvider ed) async {
    if (!mounted || _cikisSoruluyor) return AppExitResponse.cancel;
    _cikisSoruluyor = true;
    try {
      final adsiz = ed.adsizIcerikliSekmeler;
      final adlar = adsiz.map((t) => '• ${t.name}').take(8).join('\n');
      final secim = await showDialog<String>(
        context: context,
        builder: (dc) => AlertDialog(
          title: const Text('Adsız sekmeler saklanamadı'),
          content: Text(
              'TürKod şu an arka planla bağlantı kuramıyor, bu yüzden '
              'adsız sekmelerdeki yazıların saklanamadı:\n\n$adlar\n\n'
              'Pencere kapanırsa bu yazılar kaybolur. Pencereyi açık tutup '
              'birazdan yeniden dene ya da yazılarını panoya kopyala.'),
          actions: [
            OutlinedButton(
                onPressed: () => Navigator.pop(dc, 'cik'),
                child: const Text('Yine de Çık')),
            TextButton(
                onPressed: () => Navigator.pop(dc, 'kopyala'),
                child: const Text('Panoya Kopyala')),
            FilledButton(
                onPressed: () => Navigator.pop(dc, 'kal'),
                child: const Text('Açık Kalsın')),
          ],
        ),
      );
      if (secim == 'cik') return AppExitResponse.exit;
      if (secim == 'kopyala') {
        final metin = adsiz
            .map((t) => '# ----- ${t.name} -----\n${t.content}')
            .join('\n\n');
        await Clipboard.setData(ClipboardData(text: metin));
        if (mounted) {
          showAppSnackbar(
              context,
              'Adsız sekmelerdeki yazılar panoya kopyalandı. Bir yere '
              'yapıştırıp sakladıktan sonra pencereyi kapatabilirsin.',
              kind: SnackKind.success);
        }
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
    _ayarlar = context.read<SettingsProvider>()..addListener(_ayarlarDegisti);
    _uiDuzen = context.read<UiProvider>()..addListener(_duzenDegisti);
    _kurtarma = context.read<EditorProvider>().kurtarilanDegisiklik
      ..addListener(_kurtarmaBildir);
    final ayarlar = _ayarlar!;
    context.read<EditorProvider>()
      ..diskCakismasiSor = _diskCakismasiSor
      ..silinenDosyaSor = _silinenDosyaSor
      ..farkliKaydetHedefKirliSor = _farkliKaydetHedefKirliSor
      ..kayitUyarisi = _kayitUyarisi
      ..kaydederkenBicimlendir =
          (() => ayarlar.getBool('kaydederken_bicimlendir'));
    // Oturum bu pencereden önce yüklendiyse bildirim kaçmasın.
    WidgetsBinding.instance.addPostFrameCallback((_) => _kurtarmaBildir());
    _ayarlarDegisti();
    _scheduleAutoSave();
    HardwareKeyboard.instance.addHandler(_onHardwareKey);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final backend = context.read<BackendService>();
        await backend.waitUntilConnected();
        // Arayüz turu güncelleme penceresinden önce gösterilir ve bitmesi
        // beklenir (iki pencere üst üste açılmasın).
        await _turuGerekirseGoster();
        if (!mounted) return;
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
  // Çoklu imleç, yeniden adlandırma (F2: gezginde dosya adı değiştirir),
  // biçimlendirme ve tanıma git de editöre özgüdür: eskiden terminalde /
  // AI panelinde / gezginde basılınca tuş yutulup editöre uygulanıyordu.
  static const Set<String> _yalnizEditorKisayollari = {
    'edit.comment',
    'edit.duplicate',
    'edit.move_up',
    'edit.move_down',
    'edit.cursor_below',
    'edit.cursor_above',
    'edit.select_next',
    'edit.select_all_matches',
    'edit.rename',
    'edit.format',
    'edit.goto_definition',
    'edit.ai_complete',
  };
  Map<ShortcutActivator, String> _shortcutIds = {};

  // Varsayılan Ctrl+/ ve Ctrl+\ Türkçe Q klavyede basılamıyor: '/' Shift+7,
  // '\' AltGr (Ctrl+Alt) ile üretilir, SingleActivator ise değiştiricileri
  // birebir ister. Kullanıcı kısayolu değiştirmediyse eşdeğerleri de çalışır.
  static List<ShortcutActivator> _klavyeAlternatifleri(AppAction a) {
    if (a.id == 'edit.comment' && a.shortcut == 'Ctrl+/') {
      return const [
        SingleActivator(LogicalKeyboardKey.numpadDivide, control: true),
        SingleActivator(LogicalKeyboardKey.digit7, control: true, shift: true),
        CharacterActivator('/', control: true),
      ];
    }
    if (a.id == 'view.split' && a.shortcut == 'Ctrl+\\') {
      return const [
        CharacterActivator('\\', control: true),
        CharacterActivator('\\', control: true, alt: true),
      ];
    }
    return const [];
  }

  bool _odakEditordeMi() {
    // Editörün KENDİ odak düğümü (ya da onun altı) odaktaysa. Bul/Değiştir
    // kutusu da editörün widget alt ağacında olduğundan eski "ata State"
    // denetimi orada yazarken Alt+↑ ile kod satırı taşınmasına izin veriyordu.
    final node = context.read<EditorProvider>().editorFocusNode;
    final birincil = FocusManager.instance.primaryFocus;
    if (node == null || birincil == null) return false;
    return birincil == node || birincil.ancestors.contains(node);
  }

  static bool _altGrKarakteriMi(KeyEvent event) {
    final kb = HardwareKeyboard.instance;
    final c = event.character;
    if (c == null || c.isEmpty) return false;
    if (!kb.isControlPressed || !kb.isAltPressed) return false;
    // Denetim karakterleri (Ctrl+harf) yazı değildir.
    return c.runes.every((r) => r >= 0x20 && r != 0x7f);
  }

  bool _yaziAlaniOdaktaMi() {
    if (_odakEditordeMi()) return true;
    final ctx = FocusManager.instance.primaryFocus?.context;
    if (ctx == null) return false;
    return ctx.widget is EditableText ||
        ctx.findAncestorStateOfType<EditableTextState>() != null;
  }

  bool _aktifDosyaMarkdownMu() {
    final ad = (context.read<EditorProvider>().activeTab?.name ?? '').toLowerCase();
    return ad.endsWith('.md') || ad.endsWith('.markdown');
  }

  bool _onHardwareKey(KeyEvent event) {
    if (event is! KeyDownEvent) return false;
    if (!mounted) return false;
    // Bir pencere (diyalog, komut paleti, açılır menü) açıkken arkadaki
    // uygulamada kısayol çalışmasın: eskiden palet açıkken Ctrl+R kodu
    // çalıştırıyordu. Navigator.canPop bağımlılık kaydetmez (ModalRoute.of
    // her diyalog açılışında tüm kabuğu yeniden kuruyordu).
    if (Navigator.maybeOf(context)?.canPop() ?? false) return false;
    // AltGr, Windows'ta Ctrl+Alt olarak bildirilir. Türkçe Q klavyede '\', '@',
    // '{', '[' gibi karakterler AltGr ile yazılır; yazı alanındayken bunlar
    // kısayol sayılırsa karakter yazılamaz (eskiden '\' yazmak editörü
    // bölüyordu). Yazı alanında AltGr ile karakter üreten tuş yazıya kalır.
    if (_altGrKarakteriMi(event) && _yaziAlaniOdaktaMi()) return false;
    for (final entry in _shortcuts.entries) {
      if (entry.key.accepts(event, HardwareKeyboard.instance)) {
        final id = _shortcutIds[entry.key];
        if (id != null &&
            _yalnizEditorKisayollari.contains(id) &&
            !_odakEditordeMi()) {
          return false;
        }
        // Ctrl+Shift+V editörde "alta yapıştır"dır; Markdown önizlemesi bu
        // tuşla yalnız Markdown dosyasında açılır (eskiden .trpy dosyasında
        // hem yapıştırıp hem önizleme açıyordu). Menüden her zaman açılır.
        if (id == 'view.md_preview' &&
            _odakEditordeMi() &&
            !_aktifDosyaMarkdownMu()) {
          return false;
        }
        entry.value();
        return true;
      }
    }
    return false;
  }

  /// İlk açılışta (tur hiç görülmediyse) ya da "Her açılışta göster" açıksa
  /// arayüz turunu gösterir.
  Future<void> _turuGerekirseGoster() async {
    final ayarlar = context.read<SettingsProvider>();
    if (!ayarlar.loaded) {
      final yuklendi = Completer<void>();
      void dinle() {
        if (ayarlar.loaded && !yuklendi.isCompleted) yuklendi.complete();
      }

      ayarlar.addListener(dinle);
      try {
        await yuklendi.future.timeout(const Duration(seconds: 20));
      } on TimeoutException {
        return;
      } finally {
        ayarlar.removeListener(dinle);
      }
    }
    if (!mounted) return;
    final goster =
        !ayarlar.getBool(kTurGoruldu) || ayarlar.getBool(kTurHerAcilista);
    if (!goster) return;
    // Panel düzeni ve oturum yerine otursun.
    await Future.delayed(const Duration(milliseconds: 900));
    if (!mounted) return;
    if (Navigator.maybeOf(context)?.canPop() ?? false) return;
    await arayuzTurunuBaslat(context);
  }

  int _otoKayitAraligi() => context
      .read<SettingsProvider>()
      .getInt('otomatik_kaydetme_aralik', fallback: 30)
      .clamp(5, 600)
      .toInt();
  int? _kurulanAralik;

  /// Otomatik kaydetme aralığı ayardan okunur (app.py parity).
  void _scheduleAutoSave() {
    _autosaveTimer?.cancel();
    final secs = _otoKayitAraligi();
    _kurulanAralik = secs;
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
    _duzenTimer?.cancel();
    _ayarlar?.removeListener(_ayarlarDegisti);
    _kurtarma?.removeListener(_kurtarmaBildir);
    _uiDuzen?.removeListener(_duzenDegisti);
    final ed = context.read<EditorProvider>();
    if (ed.diskCakismasiSor == _diskCakismasiSor) ed.diskCakismasiSor = null;
    if (ed.kayitUyarisi == _kayitUyarisi) ed.kayitUyarisi = null;
    _cikisDinleyici.dispose();
    HardwareKeyboard.instance.removeHandler(_onHardwareKey);
    super.dispose();
  }

  // Eylem listesi ve ana yerleşim bir kez kurulur. Aynı widget örneği
  // döndürüldüğü için bildirim kutusu (toast) değişimlerinde AppLayout ve
  // altındaki editör yeniden kurulmaz.
  List<AppAction> _actions = buildAppActions();
  late Widget _body = _govdeKur();
  int _kisayolSurumu = OzelKisayollar.surum;

  Widget _govdeKur() => Column(children: [
        const ConnectionBanner(),
        Expanded(child: AppLayout(actions: _actions)),
      ]);

  /// Kullanıcı kısayolları değiştirdiyse eylemler ve gövde yeniden kurulur.
  void _kisayollariYenile() {
    if (_kisayolSurumu == OzelKisayollar.surum) return;
    _kisayolSurumu = OzelKisayollar.surum;
    _actions = buildAppActions();
    _body = _govdeKur();
  }

  @override
  Widget build(BuildContext context) {
    OzelKisayollar.ayarla(
        context.select<SettingsProvider, Object?>((s) => s.get<dynamic>('kisayollar')));
    _kisayollariYenile();
    _shortcuts = {
      for (final a in _actions) ...{
        if (a.activator != null) a.activator!: () => a.run(context),
        for (final alt in _klavyeAlternatifleri(a)) alt: () => a.run(context),
      },
    };
    _shortcutIds = {
      for (final a in _actions) ...{
        if (a.activator != null) a.activator!: a.id,
        for (final alt in _klavyeAlternatifleri(a)) alt: a.id,
      },
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

/// Komut satırından verilen dosyalar (Gezgin'de "Editör ile aç" / `turkod --editor x.trpy`).
/// Oturum geri yüklendikten sonra açılır ve etkin sekme olur.
List<String> kAcilisDosyalari = const [];

void main(List<String> args) {
  // Masaüstü Kodi penceresi: aynı programın küçük, saydam ikinci penceresi.
  if (args.contains('--kodi-penceresi')) {
    WidgetsFlutterBinding.ensureInitialized();
    kodiPenceresiniCalistir(args);
    return;
  }
  kAcilisDosyalari = args
      .where((a) => a.isNotEmpty && !a.startsWith('--'))
      .map((a) => p.normalize(p.absolute(a)))
      .where((a) => File(a).existsSync())
      .toList();
  WidgetsFlutterBinding.ensureInitialized();
  // Kitap (Öğren menüsü, sol şerit, karşılama) program içinde PDF sekmesinde
  // açılır; eskiden Windows'un PDF okuyucusu açılıyordu.
  pdfSekmesiAcici = (context, yol) async {
    if (!context.mounted) return false;
    try {
      final ed = context.read<EditorProvider>();
      // Hakkında gibi bir pencereden açıldıysa önce pencere kapanır ki sekme
      // görünsün.
      Navigator.of(context, rootNavigator: true)
          .popUntil((r) => r.isFirst);
      await ed.openFile(yol);
      return true;
    } catch (_) {
      return false;
    }
  };
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
        _acilisHatasi = _launcher.sonHata ?? 'TürKod motoru başlatılamadı.';
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
        // lazy: false — her sekmenin kendi terminali vardır; sağlayıcı sekme
        // değişimlerini ilk okunmayı beklemeden izlemeye başlamalı.
        ChangeNotifierProvider(
            lazy: false,
            create: (c) => TerminalProvider(_backend)
              ..sekmeleriIzle(c.read<EditorProvider>(), c.read<UiProvider>())),
        ChangeNotifierProvider(create: (_) => AiProvider(_backend)),
        ChangeNotifierProvider(create: (_) => KodiProvider(_backend)),
        // lazy: false — breakpoint'ler sekme düzenlemeleriyle kaydırılır ve
        // oturumdan geri yüklenir; sağlayıcı ilk okunana kadar kurulmazsa bu
        // bağlantılar o ana kadar hiç yapılmıyordu.
        ChangeNotifierProvider(
            lazy: false,
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
            locale: kTurkce,
            supportedLocales: const [kTurkce],
            localizationsDelegates: GlobalMaterialLocalizations.delegates,
            // Menü / iletişim kutusu açılınca tarayıcı sayfası anlık görüntüye geçer.
            navigatorObservers: [kTarayiciOrtuGozlemcisi],
            home: const HomeShell(),
          );
        },
      ),
    );
  }
}
