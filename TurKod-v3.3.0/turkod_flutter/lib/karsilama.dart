// Karşılama ekranı: hiç sekme açık değilken editör alanında gösterilir.
// Hızlı başlangıç kartları, son dosyalar ve günün ipucu.

part of 'main.dart';

/// Karşılama ekranındaki ipuçları (her açılışta biri gösterilir).
const List<String> kKarsilamaIpuclari = [
  'Kodunu çalıştırmak için Ctrl+R\'ye bas; sonuç aşağıdaki terminalde görünür.',
  'Bir komutun nerede olduğunu unuttun mu? Ctrl+Shift+P ile Komut Paleti\'ni aç ve adını yaz.',
  'Hatalı kodda Akıllı Düzelt (sihirli değnek) hataları senin için bulur ve düzeltir.',
  'Satır numarasına tıklayınca kesme noktası koyarsın; F5 ile programı adım adım izlersin.',
  'Yorumuna "# YAPILACAK:" yaz, Araçlar → Yapılacaklar Listesi\'nde hepsini gör.',
  'F12 ile bir fonksiyonun tanımlandığı satıra atlarsın; F2 ile adını her yerde değiştirirsin.',
  'Ctrl+Alt+Aşağı ile alttaki satıra ikinci bir imleç ekler, iki satıra birden yazarsın.',
  'Çalıştır → EXE\'ye Dönüştür ile oyununu arkadaşlarının bilgisayarında da çalıştırabilirsin.',
];

class KarsilamaEkrani extends StatelessWidget {
  const KarsilamaEkrani({super.key});

  static void _calistir(BuildContext context, String id) {
    for (final a in buildAppActions()) {
      if (a.id == id) {
        a.run(context);
        return;
      }
    }
  }

  static String _kisayol(String id) {
    for (final a in buildAppActions()) {
      if (a.id == id) return OzelKisayollar.goster(a.shortcut);
    }
    return '';
  }

  Future<void> _sonDosyayiAc(BuildContext context, String yol) async {
    final ed = context.read<EditorProvider>();
    try {
      await ed.openFile(yol, context: context);
    } catch (e) {
      ed.forgetRecent(yol);
      if (context.mounted) {
        showAppSnackbar(context, 'Dosya açılamadı: $e', kind: SnackKind.error);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final ed = context.watch<EditorProvider>();
    final son = ed.recentFiles.take(6).toList();
    final ipucu =
        kKarsilamaIpuclari[DateTime.now().day % kKarsilamaIpuclari.length];

    const kartlar = <_BaslaKarti>[
      _BaslaKarti(Icons.note_add_outlined, 'Yeni Dosya',
          'Boş bir sayfayla başla', Color(0xFF3B82F6), 'file.new_tab'),
      _BaslaKarti(Icons.file_open_outlined, 'Dosya Aç',
          'Kaydettiğin bir kodu aç', Color(0xFF10B981), 'file.open_file'),
      _BaslaKarti(Icons.folder_open_outlined, 'Klasör Aç',
          'Projeni Gezgin\'de gör', Color(0xFFF59E0B), 'file.open'),
      _BaslaKarti(Icons.menu_book_outlined, 'Kitabı Oku',
          'Kodi ile kodlamayı öğren', Color(0xFFA855F7), 'learn.book'),
      _BaslaKarti(Icons.explore_outlined, 'Arayüz Turu',
          'Ekranı adım adım tanı', Color(0xFFEC4899), 'help.tour'),
      _BaslaKarti(Icons.keyboard_command_key, 'Komut Paleti',
          'Her komutu adıyla bul', Color(0xFF06B6D4), 'view.palette'),
    ];

    return Container(
      color: cs.surface,
      child: LayoutBuilder(builder: (context, c) {
        final genis = c.maxWidth >= 640;
        return SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 36),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Başlık
                  Row(children: [
                    Container(
                      width: 64,
                      height: 64,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(18),
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            cs.primary.withValues(alpha: 0.30),
                            const Color(0xFFA855F7).withValues(alpha: 0.22),
                          ],
                        ),
                        border: Border.all(
                            color: cs.primary.withValues(alpha: 0.35)),
                      ),
                      padding: const EdgeInsets.all(10),
                      child: Image.asset('assets/icon/app_icon.png',
                          filterQuality: FilterQuality.medium,
                          errorBuilder: (_, __, ___) =>
                              Icon(Icons.code, size: 36, color: cs.primary)),
                    ),
                    const SizedBox(width: 18),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('TürKod IDE',
                              style: theme.textTheme.headlineMedium?.copyWith(
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.5,
                                  color: cs.onSurface)),
                          const SizedBox(height: 2),
                          Text('Türkçe kodla, hayal ettiğini yap!',
                              style: theme.textTheme.titleSmall?.copyWith(
                                  color: cs.onSurface.withValues(alpha: 0.65))),
                        ],
                      ),
                    ),
                  ]),
                  const SizedBox(height: 32),
                  const _BolumBasligi('Başla'),
                  const SizedBox(height: 10),
                  GridView(
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: c.maxWidth >= 560 ? 3 : 2,
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      mainAxisExtent: 66,
                    ),
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    children: [
                      for (final k in kartlar)
                        _BaslaKartiWidget(
                          kart: k,
                          kisayol: _kisayol(k.eylem),
                          onTap: () => _calistir(context, k.eylem),
                        ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Flex(
                    direction: genis ? Axis.horizontal : Axis.vertical,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Flexible(
                        flex: genis ? 3 : 0,
                        fit: genis ? FlexFit.tight : FlexFit.loose,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const _BolumBasligi('Son Dosyalar'),
                            const SizedBox(height: 8),
                            if (son.isEmpty)
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 8),
                                child: Text(
                                    'Henüz dosya açmadın. Yeni Dosya ile ilk '
                                    'programını yaz!',
                                    style: TextStyle(
                                        fontSize: 13,
                                        color: cs.onSurface
                                            .withValues(alpha: 0.6))),
                              ),
                            for (final f in son)
                              _SonDosyaSatiri(
                                yol: f,
                                onTap: () => _sonDosyayiAc(context, f),
                              ),
                          ],
                        ),
                      ),
                      SizedBox(width: genis ? 20 : 0, height: genis ? 0 : 20),
                      Flexible(
                        flex: genis ? 2 : 0,
                        fit: genis ? FlexFit.tight : FlexFit.loose,
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color:
                                const Color(0xFFF59E0B).withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                                color: const Color(0xFFF59E0B)
                                    .withValues(alpha: 0.35)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(children: [
                                const Icon(Icons.lightbulb_outline,
                                    size: 18, color: Color(0xFFF59E0B)),
                                const SizedBox(width: 6),
                                Text('Günün İpucu',
                                    style: theme.textTheme.titleSmall?.copyWith(
                                        fontWeight: FontWeight.w700,
                                        color: const Color(0xFFF59E0B))),
                              ]),
                              const SizedBox(height: 8),
                              Text(ipucu,
                                  style: TextStyle(
                                      fontSize: 13,
                                      height: 1.45,
                                      color: cs.onSurface
                                          .withValues(alpha: 0.85))),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }
}

class _BaslaKarti {
  final IconData ikon;
  final String baslik;
  final String aciklama;
  final Color renk;
  final String eylem;
  const _BaslaKarti(
      this.ikon, this.baslik, this.aciklama, this.renk, this.eylem);
}

class _BolumBasligi extends StatelessWidget {
  final String metin;
  const _BolumBasligi(this.metin);
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Text(trBuyuk(metin),
        style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
            color: cs.onSurface.withValues(alpha: 0.55)));
  }
}

class _BaslaKartiWidget extends StatefulWidget {
  final _BaslaKarti kart;
  final String kisayol;
  final VoidCallback onTap;
  const _BaslaKartiWidget(
      {required this.kart, required this.kisayol, required this.onTap});
  @override
  State<_BaslaKartiWidget> createState() => _BaslaKartiWidgetState();
}

class _BaslaKartiWidgetState extends State<_BaslaKartiWidget> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final k = widget.kart;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _uzerinde = true),
      onExit: (_) => setState(() => _uzerinde = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Tooltip(
          message: widget.kisayol.isEmpty
              ? k.baslik
              : '${k.baslik} (${widget.kisayol})',
          waitDuration: const Duration(milliseconds: 500),
          child: AnimatedContainer(
            duration: kAnim,
            curve: kAnimCurve,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: _uzerinde
                  ? k.renk.withValues(alpha: 0.10)
                  : cs.surfaceContainer,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: _uzerinde
                      ? k.renk.withValues(alpha: 0.60)
                      : cs.outlineVariant),
            ),
            child: Row(children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: k.renk.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(k.ikon, size: 20, color: k.renk),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Flexible(
                        child: Text(k.baslik,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 13.5,
                                fontWeight: FontWeight.w700,
                                color: cs.onSurface)),
                      ),
                    ]),
                    const SizedBox(height: 2),
                    Text(k.aciklama,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 11.5,
                            color: cs.onSurface.withValues(alpha: 0.6))),
                  ],
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _SonDosyaSatiri extends StatefulWidget {
  final String yol;
  final VoidCallback onTap;
  const _SonDosyaSatiri({required this.yol, required this.onTap});
  @override
  State<_SonDosyaSatiri> createState() => _SonDosyaSatiriState();
}

class _SonDosyaSatiriState extends State<_SonDosyaSatiri> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final kod = widget.yol.toLowerCase().endsWith('.trpy');
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _uzerinde = true),
      onExit: (_) => setState(() => _uzerinde = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: kAnim,
          margin: const EdgeInsets.only(bottom: 4),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: _uzerinde ? cs.surfaceContainerHigh : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(children: [
            Icon(
                kod
                    ? Icons.code
                    : pdfYoluMu(widget.yol)
                        ? Icons.picture_as_pdf_outlined
                        : Icons.description_outlined,
                size: 16,
                color: kod
                    ? cs.primary
                    : pdfYoluMu(widget.yol)
                        ? const Color(0xFFEF4444)
                        : cs.onSurface.withValues(alpha: 0.6)),
            const SizedBox(width: 10),
            Text(p.basename(widget.yol),
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _uzerinde ? cs.primary : cs.onSurface)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(p.dirname(widget.yol),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: 11.5,
                      color: cs.onSurface.withValues(alpha: 0.45))),
            ),
          ]),
        ),
      ),
    );
  }
}
