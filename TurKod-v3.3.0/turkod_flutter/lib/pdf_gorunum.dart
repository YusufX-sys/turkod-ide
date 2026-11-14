// PDF sekmesi: .pdf dosyaları metin olarak değil, sayfa sayfa görüntülenir.
// Yakınlaştırma / uzaklaştırma, sayfa gezinme ve sığdırma düğmeleri vardır.
// Sağdaki tutamaç sürüklenerek belge hızla gezilir; sayfa kutusuna numara
// yazılıp Enter'a basılınca o sayfaya gidilir.

part of 'main.dart';

class PdfSekmesi extends StatefulWidget {
  final String yol;
  const PdfSekmesi({super.key, required this.yol});

  /// Bir PDF'i belli bir sayfada açma isteği (ör. Kodi "kitabı 35. sayfada
  /// aç" dediğinde). Sekme hazırsa hemen, değilse açılınca o sayfaya gider.
  static final sayfaIstegi = ValueNotifier<({String yol, int sayfa})?>(null);
  @override
  State<PdfSekmesi> createState() => _PdfSekmesiState();
}

class _PdfSekmesiState extends State<PdfSekmesi> {
  final _ctrl = PdfViewerController();
  final _odak = FocusNode(debugLabel: 'pdf');
  final _sayfaKutusu = TextEditingController();
  final _sayfaOdak = FocusNode(debugLabel: 'pdf-sayfa');
  int? _sayfa;
  int _sayfaSayisi = 0;
  double _yakinlik = 1;
  bool _hazir = false;

  /// Sığdırma kipi: 'genislik' | 'sayfa' | 'serbest' (elle yakınlaştırıldı).
  /// Görünüm boyutu değişince (pencere açılırken büyür, panel açılıp
  /// kapanır) sayfa bu kipe göre yeniden sığdırılır; eskiden açılışta küçük
  /// pencereye göre hesaplanan ölçek kalıyor, sayfanın sağı kesiliyordu.
  String _kip = 'genislik';
  Timer? _yenidenSigdir;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_yakinlikGuncelle);
    PdfSekmesi.sayfaIstegi.addListener(_sayfaIstegi);
  }

  /// Bu PDF için bekleyen sayfa isteği varsa (görüntüleyici hazırken) uygular.
  void _sayfaIstegi() {
    final istek = PdfSekmesi.sayfaIstegi.value;
    if (istek == null || !_hazir || !mounted) return;
    if (!p.equals(istek.yol, widget.yol)) return;
    PdfSekmesi.sayfaIstegi.value = null;
    _sayfayaGit(istek.sayfa);
  }

  @override
  void dispose() {
    PdfSekmesi.sayfaIstegi.removeListener(_sayfaIstegi);
    _ctrl.removeListener(_yakinlikGuncelle);
    _yenidenSigdir?.cancel();
    _odak.dispose();
    _sayfaKutusu.dispose();
    _sayfaOdak.dispose();
    super.dispose();
  }

  void _yakinlikGuncelle() {
    if (!mounted || !_ctrl.isReady) return;
    final z = _ctrl.currentZoom;
    if ((z - _yakinlik).abs() > 0.001) setState(() => _yakinlik = z);
  }

  // Her adımda %25 (paketin kendi basamakları sığdırma ölçeğinde takılıyordu).
  Future<void> _yakinlas() => _olcekle(1.25);
  Future<void> _uzaklas() => _olcekle(1 / 1.25);

  Future<void> _olcekle(double kat) async {
    if (!_ctrl.isReady) return;
    _kip = 'serbest';
    final hedef = (_ctrl.currentZoom * kat).clamp(_ctrl.minScale, _ctrl.maxScale);
    await _ctrl.setZoom(_ctrl.centerPosition, hedef.toDouble());
  }

  Future<void> _genisligeSigdir() async {
    _kip = 'genislik';
    if (_ctrl.isReady) await _ctrl.setZoom(_ctrl.centerPosition, _ctrl.coverScale);
  }

  Future<void> _sayfayiSigdir() async {
    _kip = 'sayfa';
    if (!_ctrl.isReady) return;
    await _ctrl.setZoom(
        _ctrl.centerPosition, _ctrl.alternativeFitScale ?? _ctrl.minScale);
  }

  Future<void> _sayfayaGit(int n) async {
    if (!_ctrl.isReady || _sayfaSayisi == 0) return;
    await _ctrl.goToPage(pageNumber: n.clamp(1, _sayfaSayisi));
  }

  /// Sayfa kutusu, yazılırken değil, sayfa değişince güncellenir.
  void _sayfaKutusunuGuncelle() {
    if (_sayfaOdak.hasFocus) return;
    final metin = '${_sayfa ?? 1}';
    if (_sayfaKutusu.text != metin) _sayfaKutusu.text = metin;
  }

  void _sayfaKutusuGonder(String metin) {
    final n = int.tryParse(metin.trim());
    if (n != null) _sayfayaGit(n);
    _odak.requestFocus();
    setState(_sayfaKutusunuGuncelle);
  }

  /// Ctrl + fare tekerleği: yakınlaştırır / uzaklaştırır.
  void _tekerlek(PointerSignalEvent e) {
    if (e is! PointerScrollEvent || !HardwareKeyboard.instance.isControlPressed) {
      return;
    }
    GestureBinding.instance.pointerSignalResolver.register(e, (ev) {
      final s = ev as PointerScrollEvent;
      if (s.scrollDelta.dy < 0) {
        _yakinlas();
      } else {
        _uzaklas();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final koyu = Theme.of(context).brightness == Brightness.dark;
    final cubuk = Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(bottom: BorderSide(color: cs.outlineVariant)),
      ),
      child: Row(children: [
        const Icon(Icons.picture_as_pdf_rounded, size: 18, color: Color(0xFFEF4444)),
        const SizedBox(width: 8),
        // Kalan bütün genişlik adındır (Flexible + Spacer yarıya bölüyor,
        // uzun adlar gereksiz yere kısalıyordu).
        Expanded(
          child: Text(p.basename(widget.yol),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: cs.onSurface)),
        ),
        const SizedBox(width: 8),
        // Sayfa gezinme
        PanelDugmesi(
          ikon: Icons.keyboard_arrow_up_rounded,
          ipucu: 'Önceki sayfa',
          onPressed: _hazir && (_sayfa ?? 1) > 1
              ? () => _sayfayaGit((_sayfa ?? 1) - 1)
              : null,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: !_hazir
              ? Text('Yükleniyor…',
                  style: TextStyle(fontSize: 12, color: cs.onSurface.withValues(alpha: 0.8)))
              : Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('Sayfa ',
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurface.withValues(alpha: 0.8))),
                  // Numarayı yaz, Enter'a bas: o sayfaya gidilir.
                  Tooltip(
                    message: 'Sayfa numarasını yaz, Enter\'a bas',
                    child: SizedBox(
                      width: 46,
                      height: 26,
                      child: TextField(
                        controller: _sayfaKutusu,
                        focusNode: _sayfaOdak,
                        textAlign: TextAlign.center,
                        keyboardType: TextInputType.number,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                        style: TextStyle(fontSize: 12, color: cs.onSurface),
                        decoration: InputDecoration(
                          isDense: true,
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
                          filled: true,
                          fillColor: cs.surfaceContainerHighest,
                          border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(6),
                              borderSide: BorderSide(color: cs.outlineVariant)),
                          enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(6),
                              borderSide: BorderSide(color: cs.outlineVariant)),
                        ),
                        onTap: () => _sayfaKutusu.selection = TextSelection(
                            baseOffset: 0, extentOffset: _sayfaKutusu.text.length),
                        onSubmitted: _sayfaKutusuGonder,
                        onTapOutside: (_) {
                          _sayfaOdak.unfocus();
                          setState(_sayfaKutusunuGuncelle);
                        },
                      ),
                    ),
                  ),
                  Text(' / $_sayfaSayisi',
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurface.withValues(alpha: 0.8))),
                ]),
        ),
        PanelDugmesi(
          ikon: Icons.keyboard_arrow_down_rounded,
          ipucu: 'Sonraki sayfa',
          onPressed: _hazir && (_sayfa ?? 1) < _sayfaSayisi
              ? () => _sayfayaGit((_sayfa ?? 1) + 1)
              : null,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: SizedBox(
              height: 20, child: VerticalDivider(width: 1, color: cs.outlineVariant)),
        ),
        // Yakınlaştırma
        PanelDugmesi(
          ikon: Icons.zoom_out_rounded,
          ipucu: 'Uzaklaştır (Ctrl + -)',
          onPressed: _hazir ? _uzaklas : null,
        ),
        Container(
          width: 58,
          alignment: Alignment.center,
          child: Text('%${(_yakinlik * 100).round()}',
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: cs.onSurface.withValues(alpha: 0.85))),
        ),
        PanelDugmesi(
          ikon: Icons.zoom_in_rounded,
          ipucu: 'Yakınlaştır (Ctrl + +)',
          onPressed: _hazir ? _yakinlas : null,
        ),
        const SizedBox(width: 4),
        PanelDugmesi(
          ikon: Icons.fit_screen_outlined,
          ipucu: 'Genişliğe sığdır (Ctrl + 0)',
          onPressed: _hazir ? _genisligeSigdir : null,
        ),
        PanelDugmesi(
          ikon: Icons.crop_portrait_rounded,
          ipucu: 'Bütün sayfayı göster',
          onPressed: _hazir ? _sayfayiSigdir : null,
        ),
      ]),
    );

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.equal, control: true): _yakinlas,
        const SingleActivator(LogicalKeyboardKey.numpadAdd, control: true): _yakinlas,
        const SingleActivator(LogicalKeyboardKey.minus, control: true): _uzaklas,
        const SingleActivator(LogicalKeyboardKey.numpadSubtract, control: true):
            _uzaklas,
        const SingleActivator(LogicalKeyboardKey.digit0, control: true):
            _genisligeSigdir,
        const SingleActivator(LogicalKeyboardKey.pageDown): () =>
            _sayfayaGit((_sayfa ?? 1) + 1),
        const SingleActivator(LogicalKeyboardKey.pageUp): () =>
            _sayfayaGit((_sayfa ?? 1) - 1),
        const SingleActivator(LogicalKeyboardKey.home): () => _sayfayaGit(1),
        const SingleActivator(LogicalKeyboardKey.end): () => _sayfayaGit(_sayfaSayisi),
      },
      child: Focus(
        focusNode: _odak,
        autofocus: true,
        child: Column(children: [
          cubuk,
          Expanded(
            child: Listener(
              onPointerSignal: _tekerlek,
              onPointerDown: (_) => _odak.requestFocus(),
              child: PdfViewer.file(
                widget.yol,
                controller: _ctrl,
                params: PdfViewerParams(
                  margin: 14,
                  backgroundColor:
                      koyu ? const Color(0xFF2B2F36) : const Color(0xFFE5E7EB),
                  // Boyut derleme sırasında da değişebilir: sığdırma sonraya
                  // ertelenir (ard arda değişimlerde bir kez yapılır).
                  onViewSizeChanged: (yeni, eski, c) {
                    if (eski == null || _kip == 'serbest') return;
                    if ((yeni.width - eski.width).abs() < 1 &&
                        (yeni.height - eski.height).abs() < 1) {
                      return;
                    }
                    _yenidenSigdir?.cancel();
                    _yenidenSigdir = Timer(const Duration(milliseconds: 150), () {
                      if (!mounted || !_ctrl.isReady) return;
                      _kip == 'sayfa' ? _sayfayiSigdir() : _genisligeSigdir();
                    });
                  },
                  onViewerReady: (doc, c) {
                    if (!mounted) return;
                    setState(() {
                      _hazir = true;
                      _sayfaSayisi = doc.pages.length;
                      _sayfa = c.pageNumber ?? 1;
                      _yakinlik = c.currentZoom;
                      _sayfaKutusunuGuncelle();
                    });
                    _sayfaIstegi();
                  },
                  onPageChanged: (n) {
                    if (mounted && n != null) {
                      setState(() {
                        _sayfa = n;
                        _sayfaKutusunuGuncelle();
                      });
                    }
                  },
                  // Sağdaki kaydırma tutamacı: sürüklenerek belge hızla
                  // gezilir, üstünde o anki sayfa yazar.
                  viewerOverlayBuilder: (context, size, handleLinkTap) => [
                    PdfViewerScrollThumb(
                      controller: _ctrl,
                      orientation: ScrollbarOrientation.right,
                      thumbSize: const Size(46, 30),
                      margin: 4,
                      thumbBuilder: (context, boyut, sayfa, c) => MouseRegion(
                        cursor: SystemMouseCursors.grab,
                        child: Tooltip(
                          message: 'Sürükleyerek hızla gez',
                          waitDuration: const Duration(milliseconds: 600),
                          child: Container(
                            decoration: BoxDecoration(
                              color: cs.primary,
                              borderRadius: BorderRadius.circular(8),
                              boxShadow: const [
                                BoxShadow(color: Color(0x55000000), blurRadius: 6,
                                    offset: Offset(0, 2)),
                              ],
                            ),
                            alignment: Alignment.center,
                            child: Text('${sayfa ?? ''}',
                                style: TextStyle(
                                    color: cs.onPrimary,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700)),
                          ),
                        ),
                      ),
                    ),
                  ],
                  errorBannerBuilder: (context, hata, _, __) => Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text('PDF açılamadı: $hata',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: cs.error)),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}
