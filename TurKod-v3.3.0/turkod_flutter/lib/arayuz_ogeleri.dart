// Ortak arayüz öğeleri: panel başlıkları, simge düğmeleri, üst satırdaki
// komut arama kutusu ve panel aç/kapat düğmeleri. Bütün paneller aynı
// yükseklik, yazı ve düğme ölçüsünü kullansın diye tek yerde tanımlıdır.

part of 'main.dart';

/// Türkçe büyük harf: 'Eklenti' -> 'EKLENTİ', 'ışık' -> 'IŞIK' (Dart'ın
/// toUpperCase'i i/ı ayrımını bilmez: 'EKLENTI' yazıyordu).
String trBuyuk(String s) =>
    s.replaceAll('i', 'İ').replaceAll('ı', 'I').toUpperCase();

/// Panel başlıklarının ortak yüksekliği (Gezgin, AI, Terminal, Eklentiler).
const double kPanelBaslikYuksekligi = 36;

/// Küçük, kare, üzerine gelince hafifçe boyanan simge düğmesi.
class PanelDugmesi extends StatefulWidget {
  final IconData ikon;
  final String ipucu;
  final VoidCallback? onPressed;
  final bool secili;
  final Color? renk;
  final double boyut;
  final IconData? seciliIkon;
  const PanelDugmesi({
    super.key,
    required this.ikon,
    required this.ipucu,
    required this.onPressed,
    this.secili = false,
    this.renk,
    this.boyut = 16,
    this.seciliIkon,
  });
  @override
  State<PanelDugmesi> createState() => _PanelDugmesiState();
}

class _PanelDugmesiState extends State<PanelDugmesi> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final etkin = widget.onPressed != null;
    final renk = !etkin
        ? cs.onSurface.withValues(alpha: 0.28)
        : widget.secili
            ? cs.primary
            : widget.renk ??
                cs.onSurface.withValues(alpha: _uzerinde ? 0.95 : 0.68);
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
            width: widget.boyut + 12,
            height: widget.boyut + 12,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: widget.secili
                  ? cs.primary.withValues(alpha: 0.16)
                  : _uzerinde && etkin
                      ? cs.onSurface.withValues(alpha: 0.08)
                      : Colors.transparent,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Icon(
                widget.secili && widget.seciliIkon != null
                    ? widget.seciliIkon
                    : widget.ikon,
                size: widget.boyut,
                color: renk),
          ),
        ),
      ),
    );
  }
}

/// Panel başlığı: simge, büyük harfli başlık, isteğe bağlı alt yazı ve
/// sağda düğmeler.
class PanelBasligi extends StatelessWidget {
  final IconData? ikon;
  final String baslik;
  final List<Widget> eylemler;
  final Color? ikonRengi;
  final Widget? ek;

  /// Verilirse başlık tutulup sürüklenerek panel başka bölgeyle yer değiştirir.
  final String? surukleId;
  const PanelBasligi({
    super.key,
    this.ikon,
    required this.baslik,
    this.eylemler = const [],
    this.ikonRengi,
    this.ek,
    this.surukleId,
  });

  static TextStyle stil(BuildContext context) => TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.0,
        color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.78),
      );

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      height: kPanelBaslikYuksekligi,
      padding: const EdgeInsets.only(left: 12, right: 6),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(bottom: BorderSide(color: cs.outlineVariant)),
      ),
      child: Row(children: [
        if (ikon != null) ...[
          Icon(ikon, size: 15, color: ikonRengi ?? cs.primary),
          const SizedBox(width: 7),
        ],
        Expanded(
          child: _suruklenebilir(Row(children: [
            Text(trBuyuk(baslik), style: stil(context)),
            if (ek != null) ...[const SizedBox(width: 8), Flexible(child: ek!)],
            const Spacer(),
          ])),
        ),
        ...eylemler,
      ]),
    );
  }

  Widget _suruklenebilir(Widget w) {
    if (surukleId == null) return w;
    return Tooltip(
      message: 'Taşımak için tutup sürükle',
      waitDuration: const Duration(milliseconds: 900),
      child: PanelSurukleyici(
        id: surukleId!,
        ad: baslik,
        ikon: ikon ?? Icons.drag_indicator,
        child: Container(
            color: Colors.transparent,
            height: kPanelBaslikYuksekligi,
            child: w),
      ),
    );
  }
}

/// Üst satırın ortasındaki "Komut ara…" kutusu: Komut Paleti'ni açar.
class KomutAramaKutusu extends StatefulWidget {
  final List<AppAction> actions;
  const KomutAramaKutusu({super.key, required this.actions});
  @override
  State<KomutAramaKutusu> createState() => _KomutAramaKutusuState();
}

class _KomutAramaKutusuState extends State<KomutAramaKutusu> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final a = findAction(widget.actions, 'view.palette');
    final kisayol = a == null ? '' : OzelKisayollar.goster(a.shortcut);
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _uzerinde = true),
      onExit: (_) => setState(() => _uzerinde = false),
      child: GestureDetector(
        onTap: a == null ? null : () => a.run(context),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          height: 26,
          constraints: const BoxConstraints(maxWidth: 380),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: _uzerinde ? cs.surfaceContainerHigh : cs.surface,
            borderRadius: BorderRadius.circular(7),
            border: Border.all(
                color: _uzerinde
                    ? cs.primary.withValues(alpha: 0.6)
                    : cs.outlineVariant),
          ),
          child: Row(children: [
            Icon(Icons.search_rounded,
                size: 15, color: cs.onSurface.withValues(alpha: 0.55)),
            const SizedBox(width: 7),
            Expanded(
              child: Text('Komut ara…',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: 12.5,
                      color: cs.onSurface.withValues(alpha: 0.55))),
            ),
            if (kisayol.isNotEmpty)
              Text(kisayol,
                  style: TextStyle(
                      fontSize: 10.5,
                      color: cs.onSurface.withValues(alpha: 0.4))),
          ]),
        ),
      ),
    );
  }
}

/// Üst satırın sağındaki panel düğmeleri: Gezgin, Terminal, AI Asistan.
class DuzenDugmeleri extends StatelessWidget {
  const DuzenDugmeleri({super.key});
  @override
  Widget build(BuildContext context) {
    final ui = context.read<UiProvider>();
    final (gezgin, terminal, ai) = context.select<UiProvider, (bool, bool, bool)>(
        (u) => (u.showExplorer, u.showTerminal, u.showAi));
    return Row(mainAxisSize: MainAxisSize.min, children: [
      PanelDugmesi(
        ikon: Icons.view_sidebar_outlined,
        ipucu: kisayolluIpucu('Gezgin', 'view.explorer'),
        secili: gezgin,
        onPressed: ui.toggleExplorer,
      ),
      const SizedBox(width: 2),
      PanelDugmesi(
        ikon: Icons.call_to_action_outlined,
        ipucu: kisayolluIpucu('Terminal', 'view.terminal'),
        secili: terminal,
        onPressed: ui.toggleTerminal,
      ),
      const SizedBox(width: 2),
      PanelDugmesi(
        ikon: Icons.auto_awesome_outlined,
        ipucu: kisayolluIpucu('AI Asistan', 'view.ai'),
        secili: ai,
        onPressed: ui.toggleAi,
      ),
      const SizedBox(width: 6),
      const PanelDuzeniMenusu(),
    ]);
  }
}

/// Durum çubuğunun solundaki rozet: program çalışıyor mu, hata ayıklanıyor
/// mu, TürKod motoru bağlı mı.
class DurumRozeti extends StatelessWidget {
  const DurumRozeti({super.key});
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final bagli = context.select<ConnectionProvider, bool>((c) => c.connected);
    final calisiyor = context.select<TerminalProvider, bool>((t) => t.isRunning);
    final (hata, durakli) = context
        .select<BreakpointProvider, (bool, bool)>((b) => (b.debugging, b.paused));
    final (IconData ikon, String metin, Color renk) = !bagli
        ? (Icons.cloud_off_rounded, 'Bağlantı yok', const Color(0xFFEF4444))
        : hata
            ? (Icons.bug_report_rounded,
                durakli ? 'Hata ayıklama: durakladı' : 'Hata ayıklanıyor',
                const Color(0xFFF97316))
            : calisiyor
                ? (Icons.play_arrow_rounded, 'Program çalışıyor',
                    const Color(0xFF22C55E))
                : (Icons.check_circle_outline_rounded, 'Hazır',
                    cs.onSurface.withValues(alpha: 0.65));
    final vurgulu = !bagli || hata || calisiyor;
    return AnimatedContainer(
      duration: kAnim,
      height: 20,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: vurgulu ? renk.withValues(alpha: 0.16) : Colors.transparent,
        borderRadius: BorderRadius.circular(5),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(ikon, size: 13, color: renk),
        const SizedBox(width: 5),
        Text(metin,
            style: TextStyle(
                fontSize: 11,
                fontWeight: vurgulu ? FontWeight.w600 : FontWeight.normal,
                color: vurgulu ? renk : cs.onSurface.withValues(alpha: 0.7))),
      ]),
    );
  }
}

/// Panel başlığını sürüklenebilir yapar: başlık tutulup başka bir bölgenin
/// (Gezgin, editör, AI Asistan) üstüne bırakılınca ikisi yer değiştirir.
class PanelSurukleyici extends StatelessWidget {
  final String id;
  final String ad;
  final IconData ikon;
  final Widget child;
  const PanelSurukleyici(
      {super.key,
      required this.id,
      required this.ad,
      required this.ikon,
      required this.child});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Draggable<String>(
      data: id,
      dragAnchorStrategy: pointerDragAnchorStrategy,
      feedback: Material(
        color: Colors.transparent,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: cs.primary,
            borderRadius: BorderRadius.circular(8),
            boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 12)],
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(ikon, size: 15, color: cs.onPrimary),
            const SizedBox(width: 7),
            Text('$ad paneli taşınıyor',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: cs.onPrimary)),
          ]),
        ),
      ),
      childWhenDragging: Opacity(opacity: 0.45, child: child),
      child: MouseRegion(cursor: SystemMouseCursors.grab, child: child),
    );
  }
}

/// Bir ana bölge (Gezgin / editör / AI Asistan): üstüne panel sürüklenince
/// vurgulanır, bırakılınca iki bölge yer değiştirir.
class _PanelBirakmaAlani extends StatelessWidget {
  final String id;
  final Widget child;
  const _PanelBirakmaAlani({required this.id, required this.child});

  static const _adlar = {
    'gezgin': 'Gezgin',
    'editor': 'Editör',
    'ai': 'AI Asistan'
  };

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return DragTarget<String>(
      onWillAcceptWithDetails: (d) => d.data != id,
      onAcceptWithDetails: (d) =>
          context.read<UiProvider>().panelleriDegistir(d.data, id),
      builder: (context, adaylar, _) {
        if (adaylar.isEmpty) return child;
        return Stack(fit: StackFit.passthrough, children: [
          child,
          Positioned.fill(
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  color: cs.primary.withValues(alpha: 0.14),
                  border: Border.all(color: cs.primary, width: 2),
                ),
                alignment: Alignment.center,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: cs.primary,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('${_adlar[id] ?? id} ile yer değiştir',
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: cs.onPrimary)),
                ),
              ),
            ),
          ),
        ]);
      },
    );
  }
}

/// Sağ üstteki "Panel düzeni" menüsü: hazır yerleşimler.
class PanelDuzeniMenusu extends StatelessWidget {
  const PanelDuzeniMenusu({super.key});

  static const _duzenler = <(String, String, IconData, List<String>)>[
    (
      'varsayilan',
      'Gezgin solda, AI sağda',
      Icons.view_quilt_outlined,
      ['gezgin', 'editor', 'ai']
    ),
    ('ters', 'AI solda, Gezgin sağda', Icons.swap_horiz_rounded,
        ['ai', 'editor', 'gezgin']),
    ('sag', 'İkisi de sağda', Icons.align_horizontal_right_rounded,
        ['editor', 'gezgin', 'ai']),
    ('sol', 'İkisi de solda', Icons.align_horizontal_left_rounded,
        ['gezgin', 'ai', 'editor']),
  ];

  @override
  Widget build(BuildContext context) {
    final ui = context.read<UiProvider>();
    final sira = context.select<UiProvider, List<String>>((u) => u.panelSirasi);
    final cs = Theme.of(context).colorScheme;
    return PopupMenuButton<String>(
      tooltip: 'Panel düzeni',
      position: PopupMenuPosition.under,
      offset: const Offset(0, 4),
      onSelected: (k) {
        for (final dz in _duzenler) {
          if (dz.$1 == k) ui.panelSirasiAyarla(dz.$4);
        }
      },
      itemBuilder: (c) => [
        for (final dz in _duzenler)
          PopupMenuItem<String>(
            value: dz.$1,
            height: 34,
            child: Row(children: [
              Icon(dz.$3,
                  size: 17,
                  color: listEquals(sira, dz.$4)
                      ? cs.primary
                      : cs.onSurface.withValues(alpha: 0.7)),
              const SizedBox(width: 10),
              Expanded(
                  child: Text(dz.$2, style: const TextStyle(fontSize: 13))),
              if (listEquals(sira, dz.$4))
                Icon(Icons.check_rounded, size: 16, color: cs.primary),
            ]),
          ),
        const PopupMenuDivider(height: 8),
        PopupMenuItem<String>(
          enabled: false,
          height: 30,
          child: Text(
              'İpucu: panel başlığını tutup başka bir\nbölgenin üstüne sürükleyebilirsin.',
              style: TextStyle(
                  fontSize: 11.5, color: cs.onSurface.withValues(alpha: 0.6))),
        ),
      ],
      child: const IgnorePointer(
        child: PanelDugmesi(
            ikon: Icons.dashboard_customize_outlined,
            ipucu: '',
            onPressed: _bos),
      ),
    );
  }

  static void _bos() {}
}
