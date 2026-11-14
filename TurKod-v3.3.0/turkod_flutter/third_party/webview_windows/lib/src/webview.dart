import 'dart:async';
import 'dart:convert';
import 'dart:ui';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'enums.dart';
import 'cursor.dart';

class HistoryChanged {
  final bool canGoBack;
  final bool canGoForward;
  const HistoryChanged(this.canGoBack, this.canGoForward);
}

typedef PermissionRequestedDelegate
    = FutureOr<WebviewPermissionDecision> Function(
        String url, WebviewPermissionKind permissionKind, bool isUserInitiated);

typedef ScriptID = String;

/// Attempts to translate a button constant such as [kPrimaryMouseButton]
/// to a [PointerButton]
PointerButton getButton(int value) {
  switch (value) {
    case kPrimaryMouseButton:
      return PointerButton.primary;
    case kSecondaryMouseButton:
      return PointerButton.secondary;
    case kTertiaryButton:
      return PointerButton.tertiary;
    default:
      return PointerButton.none;
  }
}

const String _pluginChannelPrefix = 'io.jns.webview.win';
const MethodChannel _pluginChannel = MethodChannel(_pluginChannelPrefix);

class WebviewValue {
  const WebviewValue({
    required this.isInitialized,
  });

  final bool isInitialized;

  WebviewValue copyWith({
    bool? isInitialized,
  }) {
    return WebviewValue(
      isInitialized: isInitialized ?? this.isInitialized,
    );
  }

  WebviewValue.uninitialized()
      : this(
          isInitialized: false,
        );
}

/// Controls a WebView and provides streams for various change events.
class WebviewController extends ValueNotifier<WebviewValue> {
  /// Explicitly initializes the underlying WebView environment
  /// using  an optional [browserExePath], an optional [userDataPath]
  /// and optional Chromium command line arguments [additionalArguments].
  ///
  /// The environment is shared between all WebviewController instances and
  /// can be initialized only once. Initialization must take place before any
  /// WebviewController is created/initialized.
  ///
  /// Throws [PlatformException] if the environment was initialized before.
  static Future<void> initializeEnvironment(
      {String? userDataPath,
      String? browserExePath,
      String? additionalArguments}) async {
    return _pluginChannel
        .invokeMethod('initializeEnvironment', <String, dynamic>{
      'userDataPath': userDataPath,
      'browserExePath': browserExePath,
      'additionalArguments': additionalArguments
    });
  }

  /// Get the browser version info including channel name if it is not the
  /// WebView2 Runtime.
  /// Returns [null] if the webview2 runtime is not installed.
  static Future<String?> getWebViewVersion() async {
    return _pluginChannel.invokeMethod<String>('getWebViewVersion');
  }

  late Completer<void> _creatingCompleter;
  int _textureId = 0;
  bool _isDisposed = false;

  Future<void> get ready => _creatingCompleter.future;

  PermissionRequestedDelegate? _permissionRequested;

  late MethodChannel _methodChannel;
  late EventChannel _eventChannel;
  StreamSubscription? _eventStreamSubscription;

  final StreamController<String> _urlStreamController =
      StreamController<String>();

  /// A stream reflecting the current URL.
  Stream<String> get url => _urlStreamController.stream;

  final StreamController<LoadingState> _loadingStateStreamController =
      StreamController<LoadingState>.broadcast();
  final StreamController<WebErrorStatus> _onLoadErrorStreamController =
      StreamController<WebErrorStatus>();

  /// A stream reflecting the current loading state.
  Stream<LoadingState> get loadingState => _loadingStateStreamController.stream;

  /// A stream reflecting the navigation error when navigation completed with an error.
  Stream<WebErrorStatus> get onLoadError => _onLoadErrorStreamController.stream;

  final StreamController<HistoryChanged> _historyChangedStreamController =
      StreamController<HistoryChanged>();

  /// A stream reflecting the current history state.
  Stream<HistoryChanged> get historyChanged =>
      _historyChangedStreamController.stream;

  final StreamController<String> _securityStateChangedStreamController =
      StreamController<String>();

  /// A stream reflecting the current security state.
  Stream<String> get securityStateChanged =>
      _securityStateChangedStreamController.stream;

  final StreamController<String> _titleStreamController =
      StreamController<String>();

  /// A stream reflecting the current document title.
  Stream<String> get title => _titleStreamController.stream;

  final StreamController<SystemMouseCursor> _cursorStreamController =
      StreamController<SystemMouseCursor>.broadcast();

  /// A stream reflecting the current cursor style.
  Stream<SystemMouseCursor> get _cursor => _cursorStreamController.stream;

  final StreamController<dynamic> _webMessageStreamController =
      StreamController<dynamic>();

  Stream<dynamic> get webMessage => _webMessageStreamController.stream;

  final StreamController<bool>
      _containsFullScreenElementChangedStreamController =
      StreamController<bool>.broadcast();

  /// A stream reflecting whether the document currently contains full-screen elements.
  Stream<bool> get containsFullScreenElementChanged =>
      _containsFullScreenElementChangedStreamController.stream;

  WebviewController() : super(WebviewValue.uninitialized());

  /// TürKod: pencereli kipte mi kuruldu (bkz. [initialize])?
  bool windowed = false;

  /// Initializes the underlying platform view.
  ///
  /// TürKod: [windowed] true ise WebView2 kendi penceresiyle, TürKod
  /// penceresindeki bir taşıyıcı alt pencerede çizilir (görüntü kopyalanmaz;
  /// fare, tekerlek, kaydırma çubuğu ve klavye doğrudan sayfaya gider). Yeri
  /// [setWindowBounds] ile verilir; [Webview] bileşeni kullanılmaz.
  Future<void> initialize({bool windowed = false}) async {
    if (_isDisposed) {
      return Future<void>.value();
    }
    this.windowed = windowed;
    _creatingCompleter = Completer<void>();
    try {
      final reply = await _pluginChannel.invokeMapMethod<String, dynamic>(
          'initialize', windowed ? {'windowed': true} : null);

      _textureId = reply!['textureId'];
      _methodChannel = MethodChannel('$_pluginChannelPrefix/$_textureId');
      _eventChannel = EventChannel('$_pluginChannelPrefix/$_textureId/events');
      _eventStreamSubscription =
          _eventChannel.receiveBroadcastStream().listen((event) {
        final map = event as Map<dynamic, dynamic>;
        switch (map['type']) {
          case 'urlChanged':
            _urlStreamController.add(map['value']);
            break;
          case 'onLoadError':
            final value = WebErrorStatus.values[map['value']];
            _onLoadErrorStreamController.add(value);
            break;
          case 'loadingStateChanged':
            final value = LoadingState.values[map['value']];
            _loadingStateStreamController.add(value);
            break;
          case 'historyChanged':
            final value = HistoryChanged(
                map['value']['canGoBack'], map['value']['canGoForward']);
            _historyChangedStreamController.add(value);
            break;
          case 'securityStateChanged':
            _securityStateChangedStreamController.add(map['value']);
            break;
          case 'titleChanged':
            _titleStreamController.add(map['value']);
            break;
          case 'cursorChanged':
            _cursorStreamController.add(getCursorByName(map['value']));
            break;
          case 'webMessageReceived':
            try {
              final message = json.decode(map['value']);
              _webMessageStreamController.add(message);
            } catch (ex) {
              _webMessageStreamController.addError(ex);
            }
            break;
          case 'containsFullScreenElementChanged':
            _containsFullScreenElementChangedStreamController.add(map['value']);
            break;
        }
      });

      _methodChannel.setMethodCallHandler((call) {
        if (call.method == 'permissionRequested') {
          return _onPermissionRequested(
              call.arguments as Map<dynamic, dynamic>);
        }

        throw MissingPluginException('Unknown method ${call.method}');
      });

      value = value.copyWith(isInitialized: true);
      _creatingCompleter.complete();
    } on PlatformException catch (e) {
      _creatingCompleter.completeError(e);
    }

    return _creatingCompleter.future;
  }

  Future<bool?> _onPermissionRequested(Map<dynamic, dynamic> args) async {
    if (_permissionRequested == null) {
      return null;
    }

    final url = args['url'] as String?;
    final permissionKindIndex = args['permissionKind'] as int?;
    final isUserInitiated = args['isUserInitiated'] as bool?;

    if (url != null && permissionKindIndex != null && isUserInitiated != null) {
      final permissionKind = WebviewPermissionKind.values[permissionKindIndex];
      final decision =
          await _permissionRequested!(url, permissionKind, isUserInitiated);

      switch (decision) {
        case WebviewPermissionDecision.allow:
          return true;
        case WebviewPermissionDecision.deny:
          return false;
        default:
          return null;
      }
    }

    return null;
  }

  @override
  Future<void> dispose() async {
    await _creatingCompleter.future;
    if (!_isDisposed) {
      _isDisposed = true;
      await _eventStreamSubscription?.cancel();
      await _pluginChannel.invokeMethod('dispose', _textureId);
    }
    super.dispose();
  }

  /// Loads the given [url].
  Future<void> loadUrl(String url) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('loadUrl', url);
  }

  /// Loads a document from the given string.
  Future<void> loadStringContent(String content) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('loadStringContent', content);
  }

  /// Reloads the current document.
  Future<void> reload() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('reload');
  }

  /// Stops all navigations and pending resource fetches.
  Future<void> stop() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('stop');
  }

  /// Navigates the WebView to the previous page in the navigation history.
  Future<void> goBack() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('goBack');
  }

  /// Navigates the WebView to the next page in the navigation history.
  Future<void> goForward() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('goForward');
  }

  /// Adds the provided JavaScript [script] to a list of scripts that should be run after the global
  /// object has been created, but before the HTML document has been parsed and before any
  /// other script included by the HTML document is run.
  ///
  /// Returns a [ScriptID] on success which can be used for [removeScriptToExecuteOnDocumentCreated].
  ///
  /// see https://docs.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2?view=webview2-1.0.1264.42#addscripttoexecuteondocumentcreated
  Future<ScriptID?> addScriptToExecuteOnDocumentCreated(String script) async {
    if (_isDisposed) {
      return null;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod<String?>(
        'addScriptToExecuteOnDocumentCreated', script);
  }

  /// Removes the script identified by [scriptId] from the list of registered scripts.
  ///
  /// see https://docs.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2?view=webview2-1.0.1264.42#removescripttoexecuteondocumentcreated
  Future<void> removeScriptToExecuteOnDocumentCreated(ScriptID scriptId) async {
    if (_isDisposed) {
      return null;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod(
        'removeScriptToExecuteOnDocumentCreated', scriptId);
  }

  /// Runs the JavaScript [script] in the current top-level document rendered in
  /// the WebView and returns its result.
  ///
  /// see https://docs.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2?view=webview2-1.0.1264.42#executescript
  Future<dynamic> executeScript(String script) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);

    final data = await _methodChannel.invokeMethod('executeScript', script);
    if (data == null) return null;
    return jsonDecode(data as String);
  }

  /// Posts the given JSON-formatted message to the current document.
  Future<void> postWebMessage(String message) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('postWebMessage', message);
  }

  /// Sets the user agent value.
  Future<void> setUserAgent(String userAgent) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setUserAgent', userAgent);
  }

  /// Clears browser cookies.
  Future<void> clearCookies() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('clearCookies');
  }

  /// Clears browser cache.
  Future<void> clearCache() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('clearCache');
  }

  /// Toggles ignoring cache for each request. If true, cache will not be used.
  Future<void> setCacheDisabled(bool disabled) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setCacheDisabled', disabled);
  }

  /// Opens the Browser DevTools in a separate window
  Future<void> openDevTools() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('openDevTools');
  }

  /// Sets the background color to the provided [color].
  ///
  /// Due to a limitation of the underlying WebView implementation,
  /// semi-transparent values are not supported.
  /// Any non-zero alpha value will be considered as opaque (0xff).
  Future<void> setBackgroundColor(Color color) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod(
        'setBackgroundColor', color.value.toSigned(32));
  }

  /// Sets the zoom factor.
  Future<void> setZoomFactor(double zoomFactor) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setZoomFactor', zoomFactor);
  }

  /// Sets the [WebviewPopupWindowPolicy].
  Future<void> setPopupWindowPolicy(
      WebviewPopupWindowPolicy popupPolicy) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod(
        'setPopupWindowPolicy', popupPolicy.index);
  }

  /// Suspends the web view.
  Future<void> suspend() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('suspend');
  }

  /// Resumes the web view.
  Future<void> resume() async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('resume');
  }

  /// Adds a Virtual Host Name Mapping.
  ///
  /// Please refer to
  /// [Microsofts](https://docs.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_3#setvirtualhostnametofoldermapping)
  /// documentation for more details.
  Future<void> addVirtualHostNameMapping(String hostName, String folderPath,
      WebviewHostResourceAccessKind accessKind) async {
    if (_isDisposed) {
      return;
    }

    return _methodChannel.invokeMethod(
        'setVirtualHostNameMapping', [hostName, folderPath, accessKind.index]);
  }

  /// Removes a Virtual Host Name Mapping.
  ///
  /// Please refer to
  /// [Microsofts](https://docs.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_3#clearvirtualhostnametofoldermapping)
  /// documentation for more details.
  Future<void> removeVirtualHostNameMapping(String hostName) async {
    if (_isDisposed) {
      return;
    }
    return _methodChannel.invokeMethod('clearVirtualHostNameMapping', hostName);
  }

  /// Limits the number of frames per second to the given value.
  Future<void> setFpsLimit([int? maxFps = 0]) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setFpsLimit', maxFps);
  }

  /// Sends a Pointer (Touch) update
  Future<void> _setPointerUpdate(WebviewPointerEventKind kind, int pointer,
      Offset position, double size, double pressure) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setPointerUpdate',
        [pointer, kind.index, position.dx, position.dy, size, pressure]);
  }

  /// Moves the virtual cursor to [position].
  Future<void> _setCursorPos(Offset position) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel
        .invokeMethod('setCursorPos', [position.dx, position.dy]);
  }

  /// Indicates whether the specified [button] is currently down.
  Future<void> _setPointerButtonState(PointerButton button, bool isDown) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setPointerButton',
        <String, dynamic>{'button': button.index, 'isDown': isDown});
  }

  /// Sets the horizontal and vertical scroll delta.
  /// TürKod (pencereli kip): taşıyıcının yeri ve boyu, Flutter görünümüne göre
  /// fiziksel piksel.
  Future<void> setWindowBounds(Rect fiziksel) async {
    if (_isDisposed) return;
    await _methodChannel.invokeMethod('setWindowBounds', [
      fiziksel.left.roundToDouble(),
      fiziksel.top.roundToDouble(),
      fiziksel.width.roundToDouble(),
      fiziksel.height.roundToDouble(),
    ]);
  }

  /// TürKod (pencereli kip): sayfayı gösterir ya da gizler.
  Future<void> setWindowVisible(bool gorunur) async {
    if (_isDisposed) return;
    await _methodChannel.invokeMethod('setWindowVisible', gorunur);
  }

  /// TürKod (pencereli kip): taşıyıcıdan kesilen dikdörtgenler (taşıyıcıya
  /// göre, fiziksel piksel); oralarda alttaki Flutter öğeleri görünür.
  Future<void> setClipRects(List<Rect> fiziksel) async {
    if (_isDisposed) return;
    await _methodChannel.invokeMethod('setClipRects', [
      for (final r in fiziksel) ...[
        r.left.floorToDouble(),
        r.top.floorToDouble(),
        r.right.ceilToDouble(),
        r.bottom.ceilToDouble(),
      ]
    ]);
  }

  /// TürKod: sayfanın o anki görüntüsü (PNG); alınamazsa null.
  Future<Uint8List?> capturePreview() async {
    if (_isDisposed) return null;
    final r = await _methodChannel.invokeMethod<Uint8List>('capturePreview');
    return r;
  }

  /// TürKod: fare tekerleği imlecin altındaki öğeye verilir.
  ///
  /// Yerel yolla (setScrollDelta) gönderilen tekerlek olayı sayfanın sol üst
  /// köşesine gidiyor; imlecin altındaki kaydırılabilir panel (açılır menü,
  /// video ayar paneli ...) değil bütün sayfa kayıyor, sayfa kayınca da açık
  /// menüler kapanıyordu. Burada önce sayfaya o noktada bir `wheel` olayı
  /// verilir (site kendisi işleyebilsin), işlenmezse imlecin altındaki
  /// kaydırılabilir öğe (sonuna geldiyse onu içeren) kaydırılır. Betiğin
  /// ulaşamadığı bir çerçevenin (iframe) üstündeyse yerel yola dönülür.
  Future<void> _tekerlek(Offset konum, double dx, double dy) async {
    if (_isDisposed) return;
    // Flutter'ın bir tekerlek çentiği ~80 birim; tarayıcılarda ~100 CSS pikseli.
    const carpan = 1.25;
    final betik = _kTekerlekBetigi
        .replaceAll('__X__', konum.dx.toStringAsFixed(1))
        .replaceAll('__Y__', konum.dy.toStringAsFixed(1))
        .replaceAll('__DX__', (dx * carpan).toStringAsFixed(1))
        .replaceAll('__DY__', (dy * carpan).toStringAsFixed(1));
    try {
      final r = await executeScript(betik);
      if (r != 'yerel') return;
    } catch (_) {}
    await _setScrollDelta(-dx, -dy);
  }

  Future<void> _setScrollDelta(double dx, double dy) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel.invokeMethod('setScrollDelta', [dx, dy]);
  }

  /// Sets the surface size to the provided [size].
  Future<void> _setSize(Size size, double scaleFactor) async {
    if (_isDisposed) {
      return;
    }
    assert(value.isInitialized);
    return _methodChannel
        .invokeMethod('setSize', [size.width, size.height, scaleFactor]);
  }
}

class Webview extends StatefulWidget {
  final WebviewController controller;
  final PermissionRequestedDelegate? permissionRequested;
  final double? width;
  final double? height;

  /// An optional scale factor. Defaults to [FlutterView.devicePixelRatio] for
  /// rendering in native resolution.
  /// Setting this to 1.0 will disable high-DPI support.
  /// This should only be needed to mimic old behavior before high-DPI support
  /// was available.
  final double? scaleFactor;

  /// The [FilterQuality] used for scaling the texture's contents.
  /// Defaults to [FilterQuality.none] as this renders in native resolution
  /// unless specifying a [scaleFactor].
  final FilterQuality filterQuality;

  const Webview(this.controller,
      {this.width,
      this.height,
      this.permissionRequested,
      this.scaleFactor,
      this.filterQuality = FilterQuality.none});

  @override
  _WebviewState createState() => _WebviewState();
}

class _WebviewState extends State<Webview> {
  final GlobalKey _key = GlobalKey();
  final _downButtons = <int, PointerButton>{};

  PointerDeviceKind _pointerKind = PointerDeviceKind.unknown;

  MouseCursor _cursor = SystemMouseCursors.basic;

  WebviewController get _controller => widget.controller;

  StreamSubscription? _cursorSubscription;

  @override
  void initState() {
    super.initState();

    // TODO: Refactor callback and event handling and
    // remove this line
    _controller._permissionRequested = widget.permissionRequested;

    // Report initial surface size
    WidgetsBinding.instance.addPostFrameCallback((_) => _reportSurfaceSize());

    _cursorSubscription = _controller._cursor.listen((cursor) {
      setState(() {
        _cursor = cursor;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return (widget.height != null && widget.width != null)
        ? SizedBox(
            key: _key,
            width: widget.width,
            height: widget.height,
            child: _buildInner())
        : SizedBox.expand(key: _key, child: _buildInner());
  }

  Widget _buildInner() {
    return NotificationListener<SizeChangedLayoutNotification>(
        onNotification: (notification) {
          _reportSurfaceSize();
          return true;
        },
        child: SizeChangedLayoutNotifier(
            child: _controller.value.isInitialized
                ? Listener(
                    onPointerHover: (ev) {
                      // ev.kind is for whatever reason not set to touch
                      // even on touch input
                      if (_pointerKind == PointerDeviceKind.touch) {
                        // Ignoring hover events on touch for now
                        return;
                      }
                      _controller._setCursorPos(ev.localPosition);
                    },
                    onPointerDown: (ev) {
                      _pointerKind = ev.kind;
                      if (ev.kind == PointerDeviceKind.touch) {
                        _controller._setPointerUpdate(
                            WebviewPointerEventKind.down,
                            ev.pointer,
                            ev.localPosition,
                            ev.size,
                            ev.pressure);
                        return;
                      }
                      final button = getButton(ev.buttons);
                      _downButtons[ev.pointer] = button;
                      _controller._setPointerButtonState(button, true);
                    },
                    onPointerUp: (ev) {
                      _pointerKind = ev.kind;
                      if (ev.kind == PointerDeviceKind.touch) {
                        _controller._setPointerUpdate(
                            WebviewPointerEventKind.up,
                            ev.pointer,
                            ev.localPosition,
                            ev.size,
                            ev.pressure);
                        return;
                      }
                      final button = _downButtons.remove(ev.pointer);
                      if (button != null) {
                        _controller._setPointerButtonState(button, false);
                      }
                    },
                    onPointerCancel: (ev) {
                      _pointerKind = ev.kind;
                      final button = _downButtons.remove(ev.pointer);
                      if (button != null) {
                        _controller._setPointerButtonState(button, false);
                      }
                    },
                    onPointerMove: (ev) {
                      _pointerKind = ev.kind;
                      if (ev.kind == PointerDeviceKind.touch) {
                        _controller._setPointerUpdate(
                            WebviewPointerEventKind.update,
                            ev.pointer,
                            ev.localPosition,
                            ev.size,
                            ev.pressure);
                      } else {
                        _controller._setCursorPos(ev.localPosition);
                      }
                    },
                    onPointerSignal: (signal) {
                      if (signal is PointerScrollEvent) {
                        _controller._tekerlek(signal.localPosition,
                            signal.scrollDelta.dx, signal.scrollDelta.dy);
                      }
                    },
                    onPointerPanZoomUpdate: (signal) {
                      _controller._setScrollDelta(
                          signal.panDelta.dx, signal.panDelta.dy);
                    },
                    child: MouseRegion(
                        cursor: _cursor,
                        child: Texture(
                          textureId: _controller._textureId,
                          filterQuality: widget.filterQuality,
                        )),
                  )
                : const SizedBox()));
  }

  void _reportSurfaceSize() async {
    final box = _key.currentContext?.findRenderObject() as RenderBox?;
    if (box != null) {
      await _controller.ready;
      unawaited(_controller._setSize(
          box.size, widget.scaleFactor ?? window.devicePixelRatio));
    }
  }

  @override
  void dispose() {
    super.dispose();
    _cursorSubscription?.cancel();
  }
}

// TürKod: tekerleği imlecin altındaki öğeye veren sayfa betiği (bkz. _tekerlek).
// Sonuç: "tamam" ya da betiğin ulaşamadığı bir çerçevede "yerel".
const String _kTekerlekBetigi = r'''
(() => {
  const x = __X__, y = __Y__, dx = __DX__, dy = __DY__;
  let el = document.elementFromPoint(x, y);
  // Gölge DOM'un (web bileşenleri) içine in.
  while (el && el.shadowRoot) {
    const ic = el.shadowRoot.elementFromPoint(x, y);
    if (!ic || ic === el) break;
    el = ic;
  }
  if (!el) { window.scrollBy(dx, dy); return 'tamam'; }
  if (el.tagName === 'IFRAME' || el.tagName === 'FRAME' || el.tagName === 'EMBED' || el.tagName === 'OBJECT') return 'yerel';
  const olay = new WheelEvent('wheel', { clientX: x, clientY: y, deltaX: dx, deltaY: dy,
    deltaMode: 0, bubbles: true, cancelable: true, composed: true, view: window });
  if (!el.dispatchEvent(olay)) return 'tamam';
  const ust = e => e.parentElement || ((e.getRootNode && e.getRootNode() instanceof ShadowRoot) ? e.getRootNode().host : null);
  const tasar = (s, ic, dis) => /(auto|scroll|overlay)/.test(s) && ic > dis + 1;
  for (let e = el; e && e !== document.body && e !== document.documentElement; e = ust(e)) {
    const s = getComputedStyle(e);
    if (!tasar(s.overflowY, e.scrollHeight, e.clientHeight) && !tasar(s.overflowX, e.scrollWidth, e.clientWidth)) continue;
    const t = e.scrollTop, l = e.scrollLeft;
    e.scrollBy(dx, dy);
    if (e.scrollTop !== t || e.scrollLeft !== l) return 'tamam';
  }
  window.scrollBy(dx, dy);
  return 'tamam';
})()
''';
