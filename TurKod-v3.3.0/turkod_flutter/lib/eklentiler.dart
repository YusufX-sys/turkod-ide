// Eklenti Özellikleri: sol çubuktaki yapboz simgesiyle açılan panel.
//
// Panelin üstünde her zaman kullanılabilen Yerel AI Modelleri bölümü, altında
// programa sonradan eklenen küçük, isteğe bağlı özellikler ("eklentiler")
// bulunur. Programın zaten var olan özellikleri (çevirici, biçimlendirme ...)
// burada eklenti olarak sunulmaz. Eklentiler "Yükle" ile etkinleştirilir
// (ayar: eklentiler).
part of 'main.dart';

class EklentiTanimi {
  final String id;
  final String ad;
  final String aciklama;
  final IconData ikon;
  final Color renk;

  /// Önce kurulması gereken eklenti.
  final String? gerekli;

  /// Kuruluyken panelde gösterilen ana eylem.
  final String? acEtiketi;
  final void Function(BuildContext context)? ac;
  const EklentiTanimi({
    required this.id,
    required this.ad,
    required this.aciklama,
    required this.ikon,
    required this.renk,
    this.gerekli,
    this.acEtiketi,
    this.ac,
  });
}

const String kEklentiParcaciklar = 'parcaciklar';
const String kEklentiOdak = 'odak_zamanlayici';
const String kEklentiMarkdown = 'markdown_onizleme';
const String kEklentiKaralama = 'karalama_defteri';
const String kEklentiGorev = 'gunun_gorevi';

final List<EklentiTanimi> kEklentiler = [
  const EklentiTanimi(
    id: kEklentiParcaciklar,
    ad: 'Kod Parçacıkları',
    aciklama: 'Sık kullanılan TürKod kalıplarını (oyun döngüsü, dosya okuma, '
        'girdi doğrulama, sınıf ...) tek tıkla imlece ekle; kendi '
        'parçacıklarını kaydet.',
    ikon: Icons.widgets_outlined,
    renk: Color(0xFFFFA726),
    acEtiketi: 'Parçacıklar',
    ac: parcaciklariAc,
  ),
  const EklentiTanimi(
    id: kEklentiOdak,
    ad: 'Odak Zamanlayıcı',
    aciklama: 'Durum çubuğuna Pomodoro sayacı ekler: 25 dakika çalış, 5 '
        'dakika mola. Tıkla: başlat/duraklat, sağ tık: sıfırla.',
    ikon: Icons.timer_outlined,
    renk: Color(0xFFEF5350),
  ),
  const EklentiTanimi(
    id: kEklentiMarkdown,
    ad: 'Markdown Önizleme',
    aciklama: 'README ve not dosyalarını (.md) başlık, liste, tablo ve kod '
        'bloklarıyla biçimli önizler.',
    ikon: Icons.article_outlined,
    renk: Color(0xFF42A5F5),
    acEtiketi: 'Etkin dosyayı önizle',
    ac: markdownOnizle,
  ),
  const EklentiTanimi(
    id: kEklentiKaralama,
    ad: 'Karalama Defteri',
    aciklama: 'Ders notların, yapılacaklar ya da deneme kodları için '
        'kendiliğinden kaydedilen küçük bir not defteri.',
    ikon: Icons.sticky_note_2_outlined,
    renk: Color(0xFFFFCA28),
    acEtiketi: 'Defteri aç',
    ac: karalamaDefteriniAc,
  ),
  const EklentiTanimi(
    id: kEklentiGorev,
    ad: 'Günün Görevi',
    aciklama: 'Her gün yeni, kısa bir TürKod alıştırması önerir; tek tıkla '
        'yeni sekmede başlatırsın.',
    ikon: Icons.emoji_events_outlined,
    renk: Color(0xFF66BB6A),
    acEtiketi: 'Bugünün görevi',
    ac: gununGoreviniAc,
  ),
];

EklentiTanimi? eklentiBul(String id) {
  for (final e in kEklentiler) {
    if (e.id == id) return e;
  }
  return null;
}

/// Eklenti kurulu değilse kullanıcıya sorar; kurarsa true.
Future<bool> eklentiGerekli(BuildContext context, String id) async {
  final s = context.read<SettingsProvider>();
  if (s.eklentiYuklu(id)) return true;
  final e = eklentiBul(id);
  if (e == null) return false;
  final kur = await showDialog<bool>(
    context: context,
    builder: (dc) => AlertDialog(
      title: Text('"${e.ad}" eklentisi etkin değil'),
      content: Text('${e.aciklama}\n\nŞimdi etkinleştirilsin mi?'),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(dc, false), child: const Text('Vazgeç')),
        FilledButton(
            onPressed: () => Navigator.pop(dc, true), child: const Text('Etkinleştir')),
      ],
    ),
  );
  if (kur != true || !context.mounted) return false;
  await eklentiKur(context, id);
  return true;
}

/// bildir: işlem bildirimle de söylensin mi (Kodi yaptığında balonuna not
/// düştüğü için bildirim gösterilmez).
Future<void> eklentiKur(BuildContext context, String id, {bool bildir = true}) async {
  final s = context.read<SettingsProvider>();
  final e = eklentiBul(id);
  try {
    if (e?.gerekli != null && !s.eklentiYuklu(e!.gerekli!)) {
      await s.eklentiAyarla(e.gerekli!, true);
    }
    await s.eklentiAyarla(id, true);
    if (bildir && context.mounted) {
      showAppSnackbar(context, '"${e?.ad ?? id}" etkinleştirildi', kind: SnackKind.success);
    }
  } catch (err) {
    if (context.mounted) {
      showAppSnackbar(context, 'Etkinleştirilemedi: $err', kind: SnackKind.error);
    }
  }
}

Future<void> eklentiKaldir(BuildContext context, String id, {bool bildir = true}) async {
  final s = context.read<SettingsProvider>();
  try {
    await s.eklentiAyarla(id, false);
    // Bu eklentiye bağlı olanlar da kaldırılır.
    for (final e in kEklentiler) {
      if (e.gerekli == id && s.eklentiYuklu(e.id)) {
        await s.eklentiAyarla(e.id, false);
      }
    }
    if (bildir && context.mounted) {
      showAppSnackbar(context, '"${eklentiBul(id)?.ad ?? id}" devre dışı bırakıldı');
    }
  } catch (err) {
    if (context.mounted) {
      showAppSnackbar(context, 'Devre dışı bırakılamadı: $err', kind: SnackKind.error);
    }
  }
}

// ============================================================================
// SOL AKTİVİTE ÇUBUĞU
// ============================================================================

class AktiviteCubugu extends StatelessWidget {
  const AktiviteCubugu({super.key});

  static void _eylem(BuildContext context, String id) {
    final a = findAction(buildAppActions(), id);
    if (a != null) a.run(context);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final ui = context.read<UiProvider>();
    final (acik, panel) = context
        .select<UiProvider, (bool, String)>((u) => (u.showExplorer, u.solPanel));
    // Yalnızca bu sürümde bulunan eklentiler sayılır (eski ayar kayıtları değil).
    final kodiAcik = context.select<KodiProvider, bool>((k) => k.acik);
    final tarayiciAcik = context
        .select<EditorProvider, bool>((e) => e.activeTab?.path == kTarayiciPath);
    final eklentiSayisi = context.select<SettingsProvider, int>(
        (s) => kEklentiler.where((e) => s.eklentiYuklu(e.id)).length);

    Widget dugme(IconData ikon, String ipucu, VoidCallback onTap,
        {bool secili = false, Key? key, int rozet = 0, IconData? seciliIkon}) {
      return Tooltip(
        key: key,
        message: ipucu,
        waitDuration: const Duration(milliseconds: 400),
        preferBelow: false,
        child: _AktiviteDugmesi(
          secili: secili,
          onTap: onTap,
          child: Badge(
            isLabelVisible: rozet > 0,
            backgroundColor: cs.primary,
            label: Text('$rozet', style: const TextStyle(fontSize: 9)),
            offset: const Offset(4, -5),
            child: Icon(secili && seciliIkon != null ? seciliIkon : ikon,
                size: 21,
                color: secili ? cs.primary : cs.onSurface.withValues(alpha: 0.6)),
          ),
        ),
      );
    }

    return Container(
      width: 48,
      decoration: BoxDecoration(
        color: cs.surfaceContainerHigh,
        border: Border(right: BorderSide(color: cs.outlineVariant)),
      ),
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(children: [
        dugme(Icons.folder_copy_outlined, 'Gezgin (dosyalar)',
            () => ui.solPanelSec('gezgin'),
            secili: acik && panel == 'gezgin', seciliIkon: Icons.folder_copy),
        dugme(Icons.manage_search_rounded,
            kisayolluIpucu('Dosyalarda Ara', 'edit.find_in_files'),
            () => _eylem(context, 'edit.find_in_files')),
        dugme(Icons.extension_outlined,
            'Eklenti Özellikleri (yerel AI modelleri, eklentiler)',
            () => ui.solPanelSec('eklentiler'),
            secili: acik && panel == 'eklentiler',
            seciliIkon: Icons.extension,
            rozet: eklentiSayisi),
        dugme(Icons.menu_book_outlined, '$kKitapAdi (Kitap)',
            () => _eylem(context, 'learn.book')),
        dugme(Icons.public_outlined, 'Tarayıcı (internette gez, Kodi de kullanabilir)',
            () => _eylem(context, 'view.browser'),
            secili: tarayiciAcik, seciliIkon: Icons.public),
        // Kodi: basınca kitaptaki robot editörün köşesine kayarak gelir.
        Tooltip(
          message: kodiAcik
              ? 'Kodi gitsin'
              : kisayolluIpucu(
                  'Kodi ile konuş (programla ilgili her şeyi sorabilirsin)', 'help.kodi'),
          waitDuration: const Duration(milliseconds: 400),
          preferBelow: false,
          child: _AktiviteDugmesi(
            secili: kodiAcik,
            onTap: () => context.read<KodiProvider>().degistir(),
            child: KodiSimgesi(boyut: 26, soluk: !kodiAcik),
          ),
        ),
        const Spacer(),
        dugme(Icons.keyboard_command_key,
            kisayolluIpucu('TürKod Kabuğu (komut satırı, dersler)', 'tools.shell'),
            () => turkodKabuguAc(context)),
        dugme(Icons.settings_outlined, 'Ayarlar',
            () => context.read<EditorProvider>().openSettings(),
            key: TurHedefleri.ayarlar),
      ]),
    );
  }
}

/// Sol şeritteki tek düğme: seçiliyken solda renkli çizgi ve boyalı kare,
/// üzerine gelince hafif vurgu.
class _AktiviteDugmesi extends StatefulWidget {
  final bool secili;
  final VoidCallback onTap;
  final Widget child;
  const _AktiviteDugmesi(
      {required this.secili, required this.onTap, required this.child});
  @override
  State<_AktiviteDugmesi> createState() => _AktiviteDugmesiState();
}

class _AktiviteDugmesiState extends State<_AktiviteDugmesi> {
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _uzerinde = true),
      onExit: (_) => setState(() => _uzerinde = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: SizedBox(
          width: 48,
          height: 46,
          child: Stack(alignment: Alignment.center, children: [
            AnimatedContainer(
              duration: kAnim,
              curve: kAnimCurve,
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: widget.secili
                    ? cs.primary.withValues(alpha: 0.16)
                    : _uzerinde
                        ? cs.onSurface.withValues(alpha: 0.07)
                        : Colors.transparent,
                borderRadius: BorderRadius.circular(9),
              ),
            ),
            Positioned(
              left: 0,
              child: AnimatedContainer(
                duration: kAnim,
                curve: kAnimCurve,
                width: 3,
                height: widget.secili ? 22 : 0,
                decoration: BoxDecoration(
                  color: cs.primary,
                  borderRadius: const BorderRadius.horizontal(
                      right: Radius.circular(3)),
                ),
              ),
            ),
            widget.child,
          ]),
        ),
      ),
    );
  }
}

// ============================================================================
// EKLENTİ ÖZELLİKLERİ PANELİ
// ============================================================================

class EklentilerPaneli extends StatefulWidget {
  const EklentilerPaneli({super.key});
  @override
  State<EklentilerPaneli> createState() => _EklentilerPaneliState();
}

class _EklentilerPaneliState extends State<EklentilerPaneli> {
  String _ara = '';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = context.watch<SettingsProvider>();
    final q = _ara.toLowerCase();
    final liste = kEklentiler
        .where((e) =>
            q.isEmpty ||
            e.ad.toLowerCase().contains(q) ||
            e.aciklama.toLowerCase().contains(q))
        .toList();
    final yuklu = liste.where((e) => s.eklentiYuklu(e.id)).toList();
    final digerleri = liste.where((e) => !s.eklentiYuklu(e.id)).toList();

    Widget baslik(String metin) => Padding(
          padding: const EdgeInsets.fromLTRB(10, 12, 10, 4),
          child: Text(metin,
              style: theme.textTheme.labelSmall?.copyWith(
                  letterSpacing: 0.6,
                  color: theme.colorScheme.onSurface.withOpacity(0.6))),
        );

    return Container(
      color: theme.colorScheme.surfaceContainer,
      child: Column(children: [
        const PanelBasligi(
            ikon: Icons.extension_outlined,
            baslik: 'Eklenti Özellikleri',
            surukleId: 'gezgin'),
        const SizedBox(height: 6),
        // Yerel AI her zaman kullanılabilir (kurulan bir eklenti değildir).
        const _YerelAiKarti(),
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 0, 8, 4),
          child: TextField(
            style: const TextStyle(fontSize: 12.5),
            decoration: const InputDecoration(
                isDense: true,
                prefixIcon: Icon(Icons.search, size: 16),
                hintText: 'Eklenti ara…'),
            onChanged: (v) => setState(() => _ara = v.trim()),
          ),
        ),
        Expanded(
          child: ListView(padding: const EdgeInsets.only(bottom: 12), children: [
            if (yuklu.isNotEmpty) ...[
              baslik('ETKİN EKLENTİLER (${yuklu.length})'),
              for (final e in yuklu) _EklentiKarti(e, yuklu: true),
            ],
            if (digerleri.isNotEmpty) ...[
              baslik('KULLANILABİLİR EKLENTİLER'),
              for (final e in digerleri) _EklentiKarti(e, yuklu: false),
            ],
            if (liste.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Eşleşen eklenti yok.', textAlign: TextAlign.center),
              ),
          ]),
        ),
      ]),
    );
  }
}

/// Panelin üstündeki kalıcı Yerel AI bölümü: atanmış görevlerin özeti ve
/// Model Yöneticisi düğmesi.
class _YerelAiKarti extends StatelessWidget {
  const _YerelAiKarti();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = context.watch<SettingsProvider>();
    final atanan = {
      for (final a in s.gorevAtamalari.values)
        if (a.yerel) a.model,
    };
    const renk = Color(0xFF7E57C2);
    return Container(
      margin: const EdgeInsets.fromLTRB(8, 0, 8, 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: renk.withOpacity(0.10),
        border: Border.all(color: renk.withOpacity(0.45)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.memory, size: 17, color: renk),
          SizedBox(width: 8),
          Expanded(
            child: Text('Yerel AI Modelleri',
                style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
          ),
        ]),
        const SizedBox(height: 4),
        Text(
          'Bilgisayarında internetsiz çalışan ücretsiz modeller (llama.cpp): '
          'donanımına ve diskine göre öner, indir, sil. Görevler Ayarlar\'da atanır.',
          style: TextStyle(
              fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.7)),
        ),
        const SizedBox(height: 4),
        Text(
          atanan.isEmpty
              ? 'Henüz göreve atanmış model yok.'
              : 'Kullanılan model: ${atanan.join(', ')}',
          overflow: TextOverflow.ellipsis,
          maxLines: 2,
          style: const TextStyle(fontSize: 10.5),
        ),
        const SizedBox(height: 6),
        FilledButton.tonalIcon(
          style: FilledButton.styleFrom(
              visualDensity: VisualDensity.compact,
              textStyle: const TextStyle(fontSize: 12)),
          onPressed: () => yerelModelYoneticisiniAc(context),
          icon: const Icon(Icons.tune, size: 15),
          label: const Text('Model Yöneticisi'),
        ),
      ]),
    );
  }
}

class _EklentiKarti extends StatelessWidget {
  final EklentiTanimi e;
  final bool yuklu;
  const _EklentiKarti(this.e, {required this.yuklu});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = context.read<SettingsProvider>();
    final gerekliAd = e.gerekli == null ? null : eklentiBul(e.gerekli!)?.ad;
    final gerekliEksik = e.gerekli != null && !s.eklentiYuklu(e.gerekli!);
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
                color: e.renk.withOpacity(0.18),
                borderRadius: BorderRadius.circular(6)),
            child: Icon(e.ikon, size: 17, color: e.renk),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(e.ad,
                style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
          ),
          if (yuklu)
            Icon(Icons.check_circle, size: 14, color: Colors.green.shade400),
        ]),
        const SizedBox(height: 6),
        Text(e.aciklama,
            style: TextStyle(
                fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.7))),
        if (gerekliEksik && gerekliAd != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Gerekli: $gerekliAd (birlikte etkinleştirilir)',
                style: TextStyle(fontSize: 10.5, color: theme.colorScheme.primary)),
          ),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 4, children: [
          if (!yuklu)
            FilledButton.tonal(
              style: FilledButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  textStyle: const TextStyle(fontSize: 12)),
              onPressed: () => eklentiKur(context, e.id),
              child: const Text('Etkinleştir'),
            ),
          if (yuklu && e.ac != null)
            FilledButton.tonal(
              style: FilledButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  textStyle: const TextStyle(fontSize: 12)),
              onPressed: () => e.ac!(context),
              child: Text(e.acEtiketi ?? 'Aç'),
            ),
          if (yuklu)
            TextButton(
              style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  textStyle: const TextStyle(fontSize: 12)),
              onPressed: () => eklentiKaldir(context, e.id),
              child: const Text('Devre dışı bırak'),
            ),
        ]),
      ]),
    );
  }
}

// ============================================================================
// YEREL MODEL YÖNETİCİSİ (llama-cpp-python)
// ============================================================================

/// Ayarlar sayfasında kaydırılacak bölüm ('ai_gorevler').
final ValueNotifier<String?> ayarlarHedefi = ValueNotifier<String?>(null);

/// Ayarlar → Yapay Zekâ: Görevler'i açar (görev ataması orada yapılır).
void aiGorevAyarlariniAc(BuildContext context) {
  ayarlarHedefi.value = 'ai_gorevler';
  context.read<EditorProvider>().openSettings();
}

/// Yerel model indirme / silme penceresi (Eklenti Özellikleri).
Future<void> yerelModelYoneticisiniAc(BuildContext context) async {
  final s = context.read<SettingsProvider>();
  await showDialog<void>(
    context: context,
    builder: (_) => const YerelModelYoneticisi(),
  );
  // İndirilen modeller Ayarlar → Görevler listesine yansısın.
  await s.refreshModels().catchError((_) {});
}

String _gb(num? v) => v == null ? '?' : '${v.toStringAsFixed(v < 10 ? 1 : 0)} GB';

String _sayiKisa(num n) {
  if (n >= 1e6) return '${(n / 1e6).toStringAsFixed(1).replaceAll('.', ',')} milyon';
  if (n >= 1e3) return '${(n / 1e3).round()} bin';
  return '$n';
}

/// "kullanıcı/depo/dosya.gguf" -> "dosya.gguf" (yüklü model adı).
String _dosyaAdi(String kimlik) => kimlik.split('/').last;

class YerelModelYoneticisi extends StatefulWidget {
  /// Ayarlar sayfasının içinde (pencere değil) gösterilir.
  final bool gomulu;
  const YerelModelYoneticisi({super.key, this.gomulu = false});
  @override
  State<YerelModelYoneticisi> createState() => _YerelModelYoneticisiState();
}

class _YerelModelYoneticisiState extends State<YerelModelYoneticisi> {
  Map<String, dynamic>? _durum;
  Map<String, dynamic>? _oneriler;
  Map<String, dynamic> _indirmeler = {};
  List<Map<String, dynamic>>? _aramaSonucu;
  String? _hata;
  bool _aramada = false;
  bool _yalnizUygun = true;
  bool _gunlukAcik = false;
  Timer? _indirmeIzleyici;
  Timer? _motorIzleyici;
  final _araCtrl = TextEditingController();
  final _dizinCtrl = TextEditingController();
  final _dizinOdak = FocusNode();

  BackendService get _backend => context.read<BackendService>();

  @override
  void initState() {
    super.initState();
    _yukle();
  }

  @override
  void dispose() {
    _indirmeIzleyici?.cancel();
    _motorIzleyici?.cancel();
    _araCtrl.dispose();
    _dizinCtrl.dispose();
    _dizinOdak.dispose();
    super.dispose();
  }

  Map get _motor => (_durum?['motor'] as Map?) ?? const {};
  Map get _depolama =>
      (_durum?['depolama'] as Map?) ?? (_oneriler?['depolama'] as Map?) ?? const {};
  Map get _donanim =>
      (_durum?['donanim'] as Map?) ?? (_oneriler?['donanim'] as Map?) ?? const {};
  bool get _motorHazir => _motor['etkin'] != null;
  bool get _kuruluyor => (_motor['kurulum'] as Map?)?['durum'] == 'kuruluyor';

  Future<void> _yukle({bool tazele = false}) async {
    setState(() => _hata = null);
    try {
      final d = await _backend.call('yerel_ai_durum', {'tazele': tazele});
      if (mounted) {
        setState(() => _durum = d);
        // Klasör alanı, kullanıcı o an yazmıyorsa güncel klasörü gösterir.
        final dizin = (d['depolama'] as Map?)?['model_dizini']?.toString();
        if (dizin != null && !_dizinOdak.hasFocus) _dizinCtrl.text = dizin;
      }
      if (mounted && _kuruluyor) _motoruIzle();
    } catch (e) {
      if (mounted) setState(() => _hata = 'Durum okunamadı: $e');
    }
    try {
      final o = await _backend.call('yerel_ai_oneriler', {'tazele': tazele});
      if (mounted) setState(() => _oneriler = o);
    } catch (e) {
      if (mounted) setState(() => _hata = 'Öneriler alınamadı: $e');
    }
    await _indirmeleriOku();
  }

  // -- Motor ------------------------------------------------------------------

  Future<void> _motorKur({String? tur}) async {
    try {
      final r = await _backend.call('yerel_ai_motor_kur', {if (tur != null) 'tur': tur});
      if (r['ok'] == false) throw BackendException(r['hata']?.toString() ?? 'Hata');
      if (mounted) _motoruIzle();
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kurulamadı: $e', kind: SnackKind.error);
    }
  }

  void _motoruIzle() {
    // Eskiden panel kapandıktan sonra (await dönüşünde) çağrılınca
    // setState hata veriyor, zamanlayıcı hiç durmayıp her 1,5 sn'de
    // arka uca soruyordu. Bağlı değilken zamanlayıcı kurulmaz.
    _motorIzleyici?.cancel();
    _motorIzleyici = null;
    if (!mounted) return;
    _motorIzleyici = Timer.periodic(const Duration(milliseconds: 1500), (t) async {
      if (!mounted) {
        t.cancel();
        return;
      }
      try {
        final m = await _backend.call('yerel_ai_motor_durumu');
        if (!mounted) {
          t.cancel();
          return;
        }
        setState(() => _durum = {...?_durum, 'motor': m});
        final kurulum = (m['kurulum'] as Map?) ?? const {};
        final durum = kurulum['durum'];
        if (durum != 'kuruluyor') {
          t.cancel();
          if (identical(_motorIzleyici, t)) _motorIzleyici = null;
          final cpuyaDustu = kurulum['cpuya_dustu'] == true;
          showAppSnackbar(
              context,
              durum != 'tamam'
                  ? 'Motor kurulamadı; ayrıntılar günlükte.'
                  : cpuyaDustu
                      ? 'Ekran kartı sürümü çalışmadı, işlemci sürümü kuruldu.'
                      : 'Yerel AI motoru kuruldu (${m['etkin'] == 'cuda' ? 'ekran kartı / CUDA' : 'işlemci / CPU'}).',
              kind: durum != 'tamam'
                  ? SnackKind.error
                  : cpuyaDustu
                      ? SnackKind.info
                      : SnackKind.success);
        }
      } catch (_) {}
    });
    setState(() {});
  }

  Future<void> _motorKaldir() async {
    final onay = await showDialog<bool>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Motor kaldırılsın mı?'),
        content: const Text('İndirilen modeller silinmez; yeniden kurunca kullanılabilir.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dc, false), child: const Text('Vazgeç')),
          FilledButton(onPressed: () => Navigator.pop(dc, true), child: const Text('Kaldır')),
        ],
      ),
    );
    if (onay != true || !mounted) return;
    await _backend.call('yerel_ai_motor_kaldir').catchError((_) => <String, dynamic>{});
    await _yukle();
  }

  // -- Depolama ---------------------------------------------------------------

  Future<void> _modelDiziniAyarla(String? dizin) async {
    try {
      final r = await _backend.call('yerel_ai_model_dizini', {'dizin': dizin ?? ''});
      if (r['ok'] == false) throw BackendException(r['hata']?.toString() ?? 'Hata');
      await _yukle();
      if (mounted) {
        showAppSnackbar(context, 'Yeni modeller şuraya indirilecek: ${_depolama['model_dizini']}',
            kind: SnackKind.success);
      }
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Klasör değiştirilemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _klasorSec() async {
    final yol = await FilePicker.platform
        .getDirectoryPath(dialogTitle: 'Yerel AI modellerinin indirileceği klasör');
    if (yol != null && mounted) await _modelDiziniAyarla(yol);
  }

  // -- İndirme ----------------------------------------------------------------

  Future<void> _indirmeleriOku() async {
    try {
      final r = await _backend.call('yerel_ai_indirme_durumu');
      final m = r['indirmeler'];
      if (!mounted || m is! Map) return;
      final yeni = Map<String, dynamic>.from(m);
      for (final e in yeni.entries) {
        final d = e.value is Map ? e.value as Map : const {};
        final eski = _indirmeler[e.key];
        final eskiDurum = eski is Map ? eski['durum'] : null;
        if (d['durum'] == 'tamam' && eskiDurum != 'tamam') {
          unawaited(_indirmeBitti(e.key));
        }
      }
      setState(() => _indirmeler = yeni);
      final suren = yeni.values.any((v) => v is Map && v['durum'] == 'indiriliyor');
      if (suren) {
        _indirmeIzleyici ??=
            Timer.periodic(const Duration(seconds: 1), (_) => _indirmeleriOku());
      } else {
        _indirmeIzleyici?.cancel();
        _indirmeIzleyici = null;
      }
    } catch (_) {}
  }

  /// Hafif model indirildiyse ve tamamlama görevi boşsa ona, sohbet modeli
  /// indirildiyse ve sohbet görevi boşsa ona atanır (kullanıcı değiştirebilir).
  Future<void> _indirmeBitti(String kimlik) async {
    final s = context.read<SettingsProvider>();
    bool icinde(String grup) =>
        (_oneriler?[grup] as List? ?? []).any((m) => m is Map && m['ad'] == kimlik);
    final dosya = _dosyaAdi(kimlik);
    String? atanan;
    if (icinde('hafif') && s.gorevAtamasi('tamamlama') == null) {
      await s.gorevAta('tamamlama', AiAtama('yerel', dosya)).catchError((_) {});
      atanan = 'otomatik tamamlama';
    } else if (icinde('buyuk') && s.gorevAtamasi('sohbet') == null) {
      await s.gorevAta('sohbet', AiAtama('yerel', dosya)).catchError((_) {});
      atanan = 'AI Paneli sohbeti';
    }
    await _backend
        .call('yerel_ai_indirme_temizle', {'ad': kimlik}).catchError((_) => <String, dynamic>{});
    await _yukle();
    // Ayarlar → Görevler'deki model listesine yansısın.
    if (mounted) await context.read<SettingsProvider>().refreshModels().catchError((_) {});
    if (mounted) {
      showAppSnackbar(
          context, '$dosya indirildi${atanan != null ? ' ve $atanan için seçildi' : ''}.',
          kind: SnackKind.success);
    }
  }

  Future<void> _indir(Map m) async {
    try {
      final r = await _backend.call('yerel_ai_indir', {
        'ad': m['ad'],
        'baslik': m['baslik'],
        'parametre_b': m['parametre_b'],
      });
      if (r['ok'] == false) throw BackendException(r['hata']?.toString() ?? 'Hata');
      await _indirmeleriOku();
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'İndirilemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _iptal(String kimlik) async {
    await _backend
        .call('yerel_ai_indirme_iptal', {'ad': kimlik}).catchError((_) => <String, dynamic>{});
    await _backend
        .call('yerel_ai_indirme_temizle', {'ad': kimlik}).catchError((_) => <String, dynamic>{});
    await _indirmeleriOku();
  }

  Future<void> _sil(String ad) async {
    final onay = await showDialog<bool>(
      context: context,
      builder: (dc) => AlertDialog(
        title: const Text('Model silinsin mi?'),
        content: Text('"$ad" bilgisayardan silinecek. Gerekirse yeniden indirilebilir.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dc, false), child: const Text('Vazgeç')),
          FilledButton(onPressed: () => Navigator.pop(dc, true), child: const Text('Sil')),
        ],
      ),
    );
    if (onay != true || !mounted) return;
    try {
      final r = await _backend.call('yerel_ai_sil', {'ad': ad});
      if (r['ok'] == false) throw BackendException(r['hata']?.toString() ?? 'Hata');
      if (!mounted) return;
      // Backend görev atamalarını temizledi; arayüzdeki kopya da yenilenir.
      await context.read<SettingsProvider>().load();
      await _yukle();
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Silinemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _aiPanelindeKullan(String ad) async {
    final s = context.read<SettingsProvider>();
    try {
      await s.gorevAta('sohbet', AiAtama('yerel', ad));
      await s.refreshModels();
      if (mounted) {
        showAppSnackbar(
            context,
            _motorHazir
                ? 'AI Paneli artık "$ad" modelini kullanıyor.'
                : 'AI Paneli "$ad" modelini kullanacak; önce yerel AI motorunu kur.',
            kind: _motorHazir ? SnackKind.success : SnackKind.info);
      }
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Kaydedilemedi: $e', kind: SnackKind.error);
    }
  }

  Future<void> _ara() async {
    final q = _araCtrl.text.trim();
    if (q.isEmpty) {
      setState(() => _aramaSonucu = null);
      return;
    }
    setState(() => _aramada = true);
    try {
      final r = await _backend.call('yerel_ai_ara', {'sorgu': q});
      final l = r['modeller'];
      if (mounted) {
        setState(() => _aramaSonucu = [
              for (final m in (l is List ? l : const []))
                if (m is Map) Map<String, dynamic>.from(m),
            ]);
      }
    } catch (e) {
      if (mounted) showAppSnackbar(context, 'Arama yapılamadı: $e', kind: SnackKind.error);
    } finally {
      if (mounted) setState(() => _aramada = false);
    }
  }

  Set<String> get _yukluAdlar => {
        for (final m in (_durum?['yuklu'] as List? ?? const []))
          if (m is Map) (m['ad']?.toString() ?? '').toLowerCase(),
      };

  // -- Görünüm --------------------------------------------------------------

  Widget _bilgi(ThemeData theme, IconData i, String baslik, String deger,
          {Color? renk}) =>
      Padding(
        padding: const EdgeInsets.only(right: 18),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(i, size: 15, color: renk ?? theme.colorScheme.primary),
          const SizedBox(width: 5),
          Text('$baslik: ', style: const TextStyle(fontSize: 11.5)),
          Flexible(
            child: Text(deger,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700)),
          ),
        ]),
      );

  Widget _donanimSeridi(ThemeData theme) {
    final d = _donanim;
    if (d.isEmpty) return const LinearProgressIndicator(minHeight: 2);
    final gpular = (d['gpu'] as List? ?? const [])
        .whereType<Map>()
        .map((g) => '${g['ad']} (${_gb(g['vram_gb'] as num?)})')
        .join(', ');
    final hiz = (d['hizlandirma'] as Map?) ?? const {};
    final cuda = hiz['tur'] == 'cuda';
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(runSpacing: 4, children: [
        _bilgi(theme, Icons.memory, 'RAM',
            '${_gb(d['ram_toplam_gb'] as num?)} (boş ${_gb(d['ram_bos_gb'] as num?)})'),
        _bilgi(theme, Icons.developer_board, 'İşlemci', '${d['cekirdek']} çekirdek'),
        _bilgi(theme, Icons.videogame_asset_outlined, 'Ekran kartı',
            gpular.isEmpty ? 'yok' : gpular),
      ]),
      const SizedBox(height: 4),
      Row(children: [
        Icon(cuda ? Icons.bolt : Icons.developer_board,
            size: 15, color: cuda ? Colors.green.shade400 : Colors.orange.shade400),
        const SizedBox(width: 5),
        Text(cuda ? 'Hızlandırma: ekran kartı (CUDA) — ' : 'Hızlandırma yok — ',
            style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700)),
        Expanded(
          child: Text(hiz['aciklama']?.toString() ?? '',
              style: const TextStyle(fontSize: 11.5)),
        ),
      ]),
    ]);
  }

  Widget _motorSeridi(ThemeData theme) {
    final m = _motor;
    if (m.isEmpty) return const SizedBox.shrink();
    final kurulum = (m['kurulum'] as Map?) ?? const {};
    final kurulu = (m['kurulu'] as Map?) ?? const {};
    final etkin = m['etkin']?.toString();
    final onerilenCuda = m['onerilen'] == 'cuda';
    final cudaHata = m['cuda_hata'] is Map ? m['cuda_hata'] as Map : null;
    final gunluk = (kurulum['gunluk'] as List? ?? const []).map((e) => '$e').toList();
    final sunucu = (m['sunucu'] as Map?) ?? const {};

    Widget kutu(List<Widget> cocuklar, {Color? renk}) => Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: (renk ?? theme.colorScheme.primary).withOpacity(0.08),
            border: Border.all(color: (renk ?? theme.colorScheme.primary).withOpacity(0.4)),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: cocuklar),
        );

    final gunlukGorunumu = [
      if (gunluk.isNotEmpty)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
            onPressed: () => setState(() => _gunlukAcik = !_gunlukAcik),
            child: Text(_gunlukAcik ? 'Günlüğü gizle' : 'Günlüğü göster'),
          ),
        ),
      if (_gunlukAcik && gunluk.isNotEmpty)
        Container(
          height: 110,
          color: theme.colorScheme.surfaceContainerHighest,
          padding: const EdgeInsets.all(6),
          child: SingleChildScrollView(
            reverse: true,
            child: SelectableText(gunluk.join('\n'),
                style: const TextStyle(
                    fontFamily: kMonoFontFamily,
                    fontFamilyFallback: kMonoFontFallback,
                    fontSize: 10.5)),
          ),
        ),
    ];

    if (_kuruluyor) {
      return kutu([
        Row(children: [
          const SizedBox(
              width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
                'Yerel AI motoru kuruluyor (${kurulum['tur'] == 'cuda' ? 'ekran kartı / CUDA' : 'işlemci / CPU'})… '
                '${kurulum['asama'] ?? ''}',
                style: const TextStyle(fontSize: 12)),
          ),
        ]),
        const SizedBox(height: 6),
        const LinearProgressIndicator(minHeight: 2),
        ...gunlukGorunumu,
      ]);
    }
    if (etkin == null) {
      final hata = kurulum['durum'] == 'hata' ? kurulum['hata']?.toString() : null;
      return kutu([
        Row(children: [
          Icon(hata != null ? Icons.error_outline : Icons.info_outline,
              color: hata != null ? theme.colorScheme.error : theme.colorScheme.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              hata ??
                  'Yerel modelleri çalıştırmak için llama.cpp motoru (llama-cpp-python) '
                      'bir kez kurulmalı. Bu bilgisayar için '
                      '${onerilenCuda ? 'ekran kartı (NVIDIA CUDA)' : 'işlemci (CPU)'} sürümü '
                      'seçildi (~${m['indirme_mb']} MB). Modeller şimdiden indirilebilir.',
              style: const TextStyle(fontSize: 12),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: _motorKur,
            icon: const Icon(Icons.download, size: 16),
            label: Text(hata != null ? 'Yeniden dene' : 'Motoru kur'),
          ),
        ]),
        ...gunlukGorunumu,
      ], renk: hata != null ? theme.colorScheme.error : null);
    }
    final bilgi = (kurulu[etkin] as Map?) ?? const {};
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Icon(Icons.check_circle, size: 15, color: Colors.green.shade400),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            'Motor kurulu: llama-cpp-python ${bilgi['surum'] ?? ''} '
            '(${etkin == 'cuda' ? 'ekran kartı / CUDA' : 'işlemci / CPU'}) · sunucu '
            '${sunucu['calisiyor'] == true ? 'çalışıyor' : 'ilk istekte başlar'}. '
            'Modeller internetsiz çalışır.',
            style: const TextStyle(fontSize: 11.5),
          ),
        ),
        // Ekran kartı sürümü daha önce bu bilgisayarda çalışmadıysa büyük
        // düğme yeniden gösterilmez (eskiden her basışta aynı döngü yaşanıyordu).
        if (onerilenCuda && etkin != 'cuda' && cudaHata == null)
          TextButton(
              onPressed: () => _motorKur(tur: 'cuda'),
              child: const Text('Ekran kartı sürümünü kur')),
        TextButton(onPressed: _motorKaldir, child: const Text('Kaldır')),
      ]),
      if (onerilenCuda && etkin != 'cuda' && cudaHata != null)
        Padding(
          padding: const EdgeInsets.only(left: 21),
          child: Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Ekran kartı sürümü bu bilgisayarda çalışmadı: '
                '${cudaHata['neden'] ?? 'bilinmeyen hata'}'
                '${(cudaHata['tarih'] ?? '').toString().isNotEmpty ? ' (${cudaHata['tarih']})' : ''}. '
                'İşlemci sürümü kullanılıyor.',
                style: TextStyle(
                    fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.65)),
              ),
              TextButton(
                style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    textStyle: const TextStyle(fontSize: 11)),
                onPressed: () => _motorKur(tur: 'cuda'),
                child: const Text('Yeniden dene'),
              ),
            ],
          ),
        ),
      ...gunlukGorunumu,
    ]);
  }

  Widget _depolamaKarti(ThemeData theme) {
    final dep = _depolama;
    final suruculer = (dep['suruculer'] as List? ?? const []).whereType<Map>().toList();
    if (suruculer.isEmpty) return const SizedBox.shrink();
    final notlar = (dep['notlar'] as List? ?? const []).map((e) => '$e').toList();
    final onerilenDizin = dep['onerilen_dizin']?.toString();
    final varsayilan = dep['model_dizini'] == dep['varsayilan_model_dizini'];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Icon(Icons.storage, size: 15, color: theme.colorScheme.primary),
        const SizedBox(width: 5),
        const Text('Depolama', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
      ]),
      const SizedBox(height: 6),
      // Klasör yolu seçilip kopyalanabilir ve elle düzenlenebilir (Enter ya da ✓).
      TextField(
        controller: _dizinCtrl,
        focusNode: _dizinOdak,
        style: const TextStyle(
            fontSize: 12, fontFamily: kMonoFontFamily, fontFamilyFallback: kMonoFontFallback),
        decoration: InputDecoration(
          isDense: true,
          labelText: 'Model klasörü',
          suffixIcon: Row(mainAxisSize: MainAxisSize.min, children: [
            IconButton(
              tooltip: 'Kopyala',
              iconSize: 16,
              icon: const Icon(Icons.copy),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: _dizinCtrl.text));
                showAppSnackbar(context, 'Klasör yolu kopyalandı', kind: SnackKind.success);
              },
            ),
            IconButton(
              tooltip: 'Bu klasörü kullan',
              iconSize: 16,
              icon: const Icon(Icons.check),
              onPressed: () => _modelDiziniAyarla(_dizinCtrl.text.trim()),
            ),
          ]),
        ),
        onSubmitted: (v) => _modelDiziniAyarla(v.trim()),
      ),
      Wrap(spacing: 4, children: [
        TextButton.icon(
          style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
          onPressed: _klasorSec,
          icon: const Icon(Icons.folder_open, size: 16),
          label: const Text('Klasör seç…'),
        ),
        TextButton.icon(
          style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
          onPressed: varsayilan ? null : () => _modelDiziniAyarla(null),
          icon: const Icon(Icons.settings_backup_restore, size: 16),
          label: const Text('Varsayılana çevir'),
        ),
        if (onerilenDizin != null)
          TextButton.icon(
            style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
            onPressed: () => _modelDiziniAyarla(onerilenDizin),
            icon: const Icon(Icons.drive_file_move_outline, size: 16),
            label: Text('${onerilenDizin.substring(0, 1)}: sürücüsüne geç'),
          ),
      ]),
      for (final s in suruculer)
        Padding(
          padding: const EdgeInsets.only(top: 3),
          child: Row(children: [
            SizedBox(
              width: 92,
              child: Text(
                  '${s['harf']}: ${s['tur'] == '?' ? '' : s['tur']}${s['model_surucusu'] == true ? ' ◀' : ''}',
                  style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: s['model_surucusu'] == true ? FontWeight.w700 : null)),
            ),
            SizedBox(
              width: 160,
              child: LinearProgressIndicator(
                minHeight: 6,
                value: ((s['toplam_gb'] as num? ?? 1) - (s['bos_gb'] as num? ?? 0)) /
                    math.max(1, (s['toplam_gb'] as num? ?? 1)),
                color: (s['kullanilabilir_gb'] as num? ?? 0) < 5
                    ? theme.colorScheme.error
                    : theme.colorScheme.primary,
                backgroundColor: theme.colorScheme.surfaceContainerHighest,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                '${_gb(s['bos_gb'] as num?)} boş / ${_gb(s['toplam_gb'] as num?)} · '
                'modeller için kullanılabilir: ${_gb(s['kullanilabilir_gb'] as num?)} '
                '(${_gb(s['ayrilan_gb'] as num?)} ${s['sistem'] == true ? 'Windows' : 'güvenlik'} payı)',
                style: const TextStyle(fontSize: 11),
              ),
            ),
          ]),
        ),
      for (final n in notlar)
        Padding(
          padding: const EdgeInsets.only(top: 3),
          child: Text('• $n',
              style: TextStyle(fontSize: 11, color: Colors.orange.shade400)),
        ),
    ]);
  }

  /// "Kodi için uygun" (yeşil) / "Kodi için bağlamı küçük (4K)" (turuncu);
  /// bağlam bilinmiyorsa hiçbir şey. Kodi isteği en az 8K bağlam ister.
  Widget? _kodiRozeti(Map m) {
    final uygun = m['kodi_uygun'];
    if (uygun is! bool) return null;
    final baglam = (m['baglam'] as num? ?? 0);
    final renk = uygun ? Colors.green.shade600 : Colors.orange.shade700;
    final metin = uygun
        ? 'Kodi için uygun'
        : 'Kodi için bağlamı küçük (${(baglam / 1024).round()}K)';
    return Tooltip(
      message: uygun
          ? 'Bağlamı Kodi\'nin uzun istekleri için yeterli (en az 8K).'
          : 'Kodi istekleri ~8K bağlam ister; bu model Kodi\'de "bağlam aşıldı" hatası verebilir.',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(
          color: renk.withOpacity(0.12),
          border: Border.all(color: renk.withOpacity(0.5)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(metin,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 10, color: renk, fontWeight: FontWeight.w600)),
      ),
    );
  }

  Widget _modelKarti(ThemeData theme, Map m, {String? etiket}) {
    final kimlik = m['ad']?.toString() ?? '';
    final dosya = m['dosya']?.toString() ?? _dosyaAdi(kimlik);
    final yuklu = _yukluAdlar.contains(dosya.toLowerCase());
    final ind = _indirmeler[kimlik];
    final indiriliyor = ind is Map && ind['durum'] == 'indiriliyor';
    final indirmeHatasi = ind is Map && ind['durum'] == 'hata' ? ind['hata'] : null;
    final uygun = m['uygun'] != false;
    final hizli = m['hizli'] == true;
    final rozetRenk = !uygun
        ? theme.colorScheme.error
        : hizli
            ? Colors.green.shade600
            : Colors.blue.shade400;
    final ayrinti = [
      if (m['parametre_b'] != null) '${m['parametre_b']}B parametre',
      '~${_gb(m['boyut_gb'] as num?)} disk',
      if ((m['nicem'] ?? '').toString().isNotEmpty) m['nicem'],
      if ((m['indirme'] as num? ?? 0) > 0) '${_sayiKisa(m['indirme'] as num)} indirme',
      if ((m['baglam'] as num? ?? 0) > 0) '${((m['baglam'] as num) / 1024).round()}K bağlam',
    ].join(' · ');
    final toplam = ind is Map ? (ind['toplam'] as num? ?? 0) : 0;
    final tamam = ind is Map ? (ind['tamamlanan'] as num? ?? 0) : 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainer,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              if (etiket != null) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                      color: theme.colorScheme.primary.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8)),
                  child: Text(etiket,
                      style: TextStyle(fontSize: 10, color: theme.colorScheme.primary)),
                ),
                const SizedBox(width: 6),
              ],
              if (m['kodlama'] == true) ...[
                const Icon(Icons.code, size: 13),
                const SizedBox(width: 4),
              ],
              Flexible(
                child: Text(m['baslik']?.toString() ?? dosya,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ),
            ]),
            const SizedBox(height: 3),
            Text(ayrinti,
                style: TextStyle(
                    fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.65))),
            const SizedBox(height: 3),
            Row(children: [
              Icon(uygun ? (hizli ? Icons.bolt : Icons.check) : Icons.block,
                  size: 12, color: rozetRenk),
              const SizedBox(width: 4),
              Flexible(
                child: Text(m['gerekce']?.toString() ?? '',
                    style: TextStyle(fontSize: 11, color: rozetRenk)),
              ),
            ]),
            if (_kodiRozeti(m) case final rozet?) ...[
              const SizedBox(height: 4),
              rozet,
            ],
            if (indiriliyor) ...[
              const SizedBox(height: 6),
              LinearProgressIndicator(
                value: ((ind['yuzde'] as num?) ?? 0) > 0 ? (ind['yuzde'] as num) / 100 : null,
                minHeight: 3,
              ),
              const SizedBox(height: 2),
              Text(
                  toplam > 0
                      ? '%${ind['yuzde']} · ${(tamam / 1048576).round()} / ${(toplam / 1048576).round()} MB'
                      : '${ind['asama'] ?? ''}',
                  style: const TextStyle(fontSize: 10.5)),
            ],
            if (indirmeHatasi != null)
              Text('İndirme hatası: $indirmeHatasi',
                  style: TextStyle(fontSize: 11, color: theme.colorScheme.error)),
          ]),
        ),
        const SizedBox(width: 8),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          if (yuklu)
            Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.check_circle, size: 15, color: Colors.green.shade400),
              const SizedBox(width: 4),
              const Text('Yüklü', style: TextStyle(fontSize: 12)),
            ])
          else if (indiriliyor)
            TextButton(onPressed: () => _iptal(kimlik), child: const Text('Vazgeç'))
          else if (uygun)
            FilledButton.tonalIcon(
              onPressed: () => _indir(m),
              icon: const Icon(Icons.download, size: 15),
              label: const Text('İndir'),
            )
          else
            Tooltip(
              message: 'Bu bilgisayar ya da disk için uygun değil; yine de indirilebilir.',
              child: OutlinedButton.icon(
                onPressed: () => _indir(m),
                icon: const Icon(Icons.download, size: 15),
                label: const Text('Yine de indir'),
              ),
            ),
          if ((m['sayfa'] ?? '').toString().isNotEmpty)
            TextButton(
              style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact, textStyle: const TextStyle(fontSize: 11)),
              onPressed: () => baglantiAc(context, m['sayfa'].toString()),
              child: const Text('Model sayfası'),
            ),
        ]),
      ]),
    );
  }

  Widget _onerilenler(ThemeData theme) {
    final o = _oneriler;
    if (o == null) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    final hafif = (o['hafif'] as List? ?? const []).whereType<Map>().toList();
    final buyuk = (o['buyuk'] as List? ?? const []).whereType<Map>().toList();
    final kaynak = o['kaynak']?.toString() ?? '';
    final kullanilabilir = (o['depolama'] as Map?)?['kullanilabilir_gb'];
    Widget bolum(String baslik, String alt) => Padding(
          padding: const EdgeInsets.only(top: 10, bottom: 6),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(baslik, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
            Text(alt,
                style: TextStyle(
                    fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.6))),
          ]),
        );
    return ListView(padding: const EdgeInsets.only(right: 4), children: [
      Text(
        '${kaynak == 'yedek' ? 'İnternete bağlanılamadı; yerleşik öneri listesi gösteriliyor. ' : 'Öneriler Hugging Face\'teki en çok indirilen modellerden seçildi. '}'
        'Bellek, ekran kartı ve model klasörünün diskindeki kullanılabilir alan '
        '(${_gb(kullanilabilir as num?)}) dikkate alındı. Önerilenlerin hepsi '
        '${_gb(o['onerilen_toplam_gb'] as num?)} tutar'
        '${o['hepsi_sigar'] == true ? '.' : '; hepsi birden sığmaz, ihtiyacın olanı indir.'}',
        style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.6)),
      ),
      bolum('Hafif modeller — basit görevler',
          'Otomatik tamamlama, kısa açıklamalar. Hızlı, az bellek ve disk ister.'),
      if (hafif.isEmpty)
        const Text('Belleğe ve diske sığan hafif model bulunamadı; Depolama bölümünden '
            'başka bir sürücü seç.'),
      for (final m in hafif) _modelKarti(theme, m, etiket: 'Hafif'),
      bolum('Sohbet modelleri — AI Paneli',
          'Soru-cevap, kod yazma, hata açıklama. Bu bilgisayara sığan en güçlüler.'),
      if (buyuk.isEmpty)
        const Text('Belleğe ve diske sığan sohbet modeli bulunamadı; Depolama bölümünden '
            'başka bir sürücü seç.'),
      for (final m in buyuk) _modelKarti(theme, m, etiket: 'Sohbet'),
    ]);
  }

  Widget _yukluler(ThemeData theme) {
    final yuklu = (_durum?['yuklu'] as List? ?? const []).whereType<Map>().toList();
    final gorevAdlari =
        Map<String, dynamic>.from((_durum?['gorev_adlari'] as Map?) ?? const {});
    final s = context.watch<SettingsProvider>();
    if (_durum == null) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (yuklu.isEmpty) {
      return const Center(
        child: Text('Henüz indirilmiş model yok. "Önerilen" sekmesinden bir model indir.',
            textAlign: TextAlign.center),
      );
    }
    return ListView(children: [
      Text(
        'İndirilen modeller Ayarlar → Yapay Zekâ: Görevler listesinde "TürKod Yerel • '
        'model" olarak çıkar; görevleri orada ata (internet ve API anahtarı gerekmez).'
        '${_motorHazir ? '' : ' Modelleri kullanmak için önce yerel AI motorunu kur.'}',
        style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.6)),
      ),
      const SizedBox(height: 8),
      for (final m in yuklu)
        Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainer,
            border: Border.all(color: theme.colorScheme.outlineVariant),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.smart_toy_outlined, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(m['baslik']?.toString() ?? m['ad']?.toString() ?? '',
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ),
              Text(
                  [
                    if ((m['parametre'] ?? '').toString().isNotEmpty) m['parametre'],
                    _gb(m['boyut_gb'] as num?),
                    if ((m['nicem'] ?? '').toString().isNotEmpty) m['nicem'],
                  ].join(' · '),
                  style: const TextStyle(fontSize: 11)),
              const SizedBox(width: 6),
              TextButton.icon(
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                onPressed: () => _aiPanelindeKullan(m['ad'].toString()),
                icon: const Icon(Icons.chat_outlined, size: 15),
                label: const Text('AI Panelinde kullan'),
              ),
              IconButton(
                tooltip: 'Sil',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.delete_outline, size: 17),
                onPressed: () => _sil(m['ad'].toString()),
              ),
            ]),
            Wrap(
              spacing: 8,
              runSpacing: 3,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                    [
                      m['ad']?.toString() ?? '',
                      if ((m['baglam'] as num? ?? 0) > 0)
                        '${((m['baglam'] as num) / 1024).round()}K bağlam',
                    ].join(' · '),
                    style: TextStyle(
                        fontSize: 10.5, color: theme.colorScheme.onSurface.withOpacity(0.5))),
                if (_kodiRozeti(m) case final rozet?) rozet,
              ],
            ),
            const SizedBox(height: 6),
            Row(children: [
              Expanded(
                child: Text(
                  () {
                    final kullanan = [
                      for (final e in s.gorevAtamalari.entries)
                        if (e.value == AiAtama('yerel', m['ad'].toString()))
                          (gorevAdlari[e.key] ?? e.key).toString(),
                    ];
                    return kullanan.isEmpty
                        ? 'Henüz bir göreve atanmadı.'
                        : 'Görevler: ${kullanan.join(', ')}';
                  }(),
                  style: const TextStyle(fontSize: 11.5),
                ),
              ),
              TextButton.icon(
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                onPressed: () {
                  Navigator.of(context).maybePop();
                  aiGorevAyarlariniAc(context);
                },
                icon: const Icon(Icons.hub_outlined, size: 15),
                label: const Text('Görev ata (Ayarlar)'),
              ),
            ]),
          ]),
        ),
    ]);
  }

  Widget _tumModeller(ThemeData theme) {
    final kaynak = _aramaSonucu ??
        (_oneriler?['tumu'] as List? ?? const [])
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
    final liste =
        _yalnizUygun ? kaynak.where((m) => m['uygun'] != false).toList() : kaynak;
    return Column(children: [
      Row(children: [
        Expanded(
          child: TextField(
            controller: _araCtrl,
            decoration: InputDecoration(
              isDense: true,
              prefixIcon: const Icon(Icons.search, size: 17),
              hintText: 'Hugging Face\'te GGUF model ara (ör. llama, qwen, gemma, phi)…',
              suffixIcon: _aramada
                  ? const Padding(
                      padding: EdgeInsets.all(10),
                      child: SizedBox(
                          width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2)))
                  : null,
            ),
            onSubmitted: (_) => _ara(),
          ),
        ),
        const SizedBox(width: 8),
        FilterChip(
          label: const Text('Yalnızca uygun olanlar', style: TextStyle(fontSize: 11.5)),
          selected: _yalnizUygun,
          onSelected: (v) => setState(() => _yalnizUygun = v),
        ),
      ]),
      const SizedBox(height: 8),
      Expanded(
        child: liste.isEmpty
            ? const Center(child: Text('Model bulunamadı.'))
            : ListView.builder(
                itemCount: liste.length,
                itemBuilder: (c, i) => _modelKarti(theme, liste[i]),
              ),
      ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final boyut = MediaQuery.sizeOf(context);
    final yukluSayi = (_durum?['yuklu'] as List?)?.length ?? 0;
    final icerik = SizedBox(
        width: widget.gomulu ? null : math.min(1000, boyut.width * 0.94),
        height: widget.gomulu ? 820 : math.min(780, boyut.height * 0.92),
        child: DefaultTabController(
          length: 3,
          child: Padding(
            padding: widget.gomulu
                ? EdgeInsets.zero
                : const EdgeInsets.fromLTRB(16, 12, 16, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                if (!widget.gomulu) ...[
                Icon(Icons.memory, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text('Yerel AI Modelleri',
                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(width: 8),
                Text('llama.cpp',
                    style: TextStyle(
                        fontSize: 11, color: theme.colorScheme.onSurface.withOpacity(0.5))),
                ],
                const Spacer(),
                IconButton(
                  tooltip: 'Donanımı, depolamayı ve önerileri yenile (internetten)',
                  icon: const Icon(Icons.refresh),
                  onPressed: () => _yukle(tazele: true),
                ),
                if (!widget.gomulu)
                  IconButton(
                    tooltip: 'Kapat',
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
              ]),
              const SizedBox(height: 6),
              _donanimSeridi(theme),
              const SizedBox(height: 8),
              _depolamaKarti(theme),
              const SizedBox(height: 8),
              _motorSeridi(theme),
              if (_hata != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(_hata!, style: TextStyle(color: theme.colorScheme.error)),
                ),
              const SizedBox(height: 6),
              TabBar(
                isScrollable: true,
                tabAlignment: TabAlignment.start,
                tabs: [
                  const Tab(text: 'Önerilen'),
                  Tab(text: 'İndirilenler ($yukluSayi)'),
                  const Tab(text: 'Tüm modeller / Ara'),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: TabBarView(children: [
                  _onerilenler(theme),
                  _yukluler(theme),
                  _tumModeller(theme),
                ]),
              ),
            ]),
          ),
        ),
    );
    if (widget.gomulu) return icerik;
    return Dialog(insetPadding: const EdgeInsets.all(24), child: icerik);
  }
}

// ============================================================================
// AI ÖNERİSİ İSTE (Ctrl+Shift+Boşluk)
// ============================================================================

/// Hayalet kod önerisini hemen ister (Ctrl+Shift+Boşluk). Ayarlanmamışsa
/// Ayarlar → AI Kod Tamamlama açılır.
Future<void> aiOnerisiIste(BuildContext context) async {
  final s = context.read<SettingsProvider>();
  if (!s.aiTamamlamaHazir) {
    showAppSnackbar(context,
        'AI kod tamamlama ayarlanmamış: Ayarlar → AI Kod Tamamlama bölümünden '
        'yerel model ya da API seç.');
    context.read<EditorProvider>().openSettings();
    return;
  }
  context.read<EditorProvider>().hayaletIste?.call();
}

// ============================================================================
// KARALAMA DEFTERİ
// ============================================================================

Future<void> karalamaDefteriniAc(BuildContext context) async {
  if (!await eklentiGerekli(context, kEklentiKaralama)) return;
  if (!context.mounted) return;
  await showDialog<void>(context: context, builder: (_) => const _KaralamaDialog());
}

class _KaralamaDialog extends StatefulWidget {
  const _KaralamaDialog();
  @override
  State<_KaralamaDialog> createState() => _KaralamaDialogState();
}

class _KaralamaDialogState extends State<_KaralamaDialog> {
  late final TextEditingController _ctrl = TextEditingController(
      text: context.read<SettingsProvider>().getString('karalama_notlari'));
  Timer? _kayit;
  String _durum = '';

  void _degisti(String _) {
    _kayit?.cancel();
    setState(() => _durum = 'Kaydediliyor…');
    _kayit = Timer(const Duration(milliseconds: 800), _kaydet);
  }

  Future<void> _kaydet() async {
    _kayit?.cancel();
    try {
      await context.read<SettingsProvider>().setValue('karalama_notlari', _ctrl.text);
      if (mounted) setState(() => _durum = 'Kaydedildi');
    } catch (e) {
      if (mounted) setState(() => _durum = 'Kaydedilemedi: $e');
    }
  }

  @override
  void dispose() {
    if (_kayit?.isActive ?? false) {
      _kayit!.cancel();
      // Pencere kapanırken bekleyen değişiklik kaybolmasın.
      context
          .read<SettingsProvider>()
          .setValue('karalama_notlari', _ctrl.text)
          .catchError((_) {});
    }
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: const Row(children: [
        Icon(Icons.sticky_note_2_outlined, size: 18),
        SizedBox(width: 8),
        Text('Karalama Defteri'),
      ]),
      content: SizedBox(
        width: 640,
        height: 420,
        child: Container(
          decoration: BoxDecoration(
              border: Border.all(color: theme.colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(3)),
          child: TextField(
            controller: _ctrl,
            autofocus: true,
            maxLines: null,
            expands: true,
            onChanged: _degisti,
            style: const TextStyle(
                fontFamily: kMonoFontFamily, fontFamilyFallback: kMonoFontFallback, fontSize: 13),
            decoration: const InputDecoration(
                border: InputBorder.none,
                contentPadding: EdgeInsets.all(10),
                hintText: 'Notlar, yapılacaklar, deneme kodları…'),
          ),
        ),
      ),
      actions: [
        Text(_durum, style: const TextStyle(fontSize: 11)),
        TextButton(
          onPressed: _ctrl.text.trim().isEmpty
              ? null
              : () {
                  imleceEkle(context, _ctrl.text);
                  Navigator.pop(context);
                },
          child: const Text('İmlece ekle'),
        ),
        FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Kapat')),
      ],
    );
  }
}

// ============================================================================
// GÜNÜN GÖREVİ
// ============================================================================

/// (başlık, açıklama, ipucu)
const List<(String, String, String)> kGunlukGorevler = [
  ('Çarpım tablosu', '1\'den 10\'a kadar seçilen bir sayının çarpım tablosunu yazdır.',
      'için i içinde aralık(1, 11): ...'),
  ('Tek mi çift mi?', 'Kullanıcıdan bir sayı al; tek mi çift mi olduğunu yazdır.',
      'sayı % 2 == 0 ise çifttir.'),
  ('En büyük sayı', 'Beş sayılık bir listenin en büyüğünü en_büyük() kullanmadan bul.',
      'Bir değişkende şimdiye kadarki en büyüğü tut.'),
  ('Ters çevir', 'Kullanıcının yazdığı kelimeyi tersten yazdır.', 'metin[::-1]'),
  ('Sesli harfler', 'Bir cümledeki sesli harfleri say.', 'için harf içinde cümle: ...'),
  ('Not ortalaması', 'Üç notun ortalamasını hesapla; 50 ve üstüyse "Geçti" yaz.',
      'toplam(notlar) / uzunluk(notlar)'),
  ('Sayı tahmini', '1–20 arasında rastgele bir sayı tut, kullanıcı bulana kadar ipucu ver.',
      'içe_aktar rastgele · rastgele.rastgele_tamsayı(1, 20)'),
  ('Asal sayı mı?', 'Girilen sayının asal olup olmadığını bul.',
      '2\'den sayıya kadar bölenleri dene.'),
  ('Faktöriyel', 'Bir fonksiyon yaz: faktöriyel(5) → 120.', 'fonksiyon ... döndür ...'),
  ('Alışveriş listesi', 'Kullanıcı "bitti" yazana kadar ürün al, sonunda listeyi yazdır.',
      'döngü Doğru: ... kır'),
  ('Harf notu', '0–100 arası puanı AA/BA/BB… harf notuna çevir.',
      'eğer / değilse_eğer zinciri'),
  ('Kelime sayacı', 'Bir cümlede her kelimenin kaç kez geçtiğini sözlükle say.',
      'sayılar[kelime] = sayılar.getir(kelime, 0) + 1'),
  ('Sıcaklık çevirici', 'Santigrat dereceyi Fahrenhayta çevir: F = C × 9/5 + 32.',
      'ondalıklı(girdi_al(...))'),
  ('Fibonacci', 'İlk 15 Fibonacci sayısını yazdır.', 'a, b = b, a + b'),
  ('Banka hesabı', 'para_yatır ve para_çek metotları olan bir Hesap sınıfı yaz.',
      'sınıf Hesap: ... __başlat__(kendisi)'),
];

int _gorevSirasi(DateTime gun) =>
    gun.difference(DateTime(2026, 1, 1)).inDays % kGunlukGorevler.length;

Future<void> gununGoreviniAc(BuildContext context) async {
  if (!await eklentiGerekli(context, kEklentiGorev)) return;
  if (!context.mounted) return;
  var sira = _gorevSirasi(DateTime.now());
  await showDialog<void>(
    context: context,
    builder: (dc) => StatefulBuilder(builder: (dc, setDurum) {
      final g = kGunlukGorevler[sira];
      return AlertDialog(
        title: Row(children: [
          const Icon(Icons.emoji_events_outlined, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text('Günün Görevi: ${g.$1}')),
        ]),
        content: SizedBox(
          width: 460,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start,
              children: [
            Text(g.$2, style: const TextStyle(fontSize: 14)),
            const SizedBox(height: 10),
            Text('İpucu: ${g.$3}',
                style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(dc).colorScheme.onSurface.withOpacity(0.65))),
          ]),
        ),
        actions: [
          TextButton(
            onPressed: () => setDurum(() => sira = (sira + 1) % kGunlukGorevler.length),
            child: const Text('Başka görev'),
          ),
          TextButton(onPressed: () => Navigator.pop(dc), child: const Text('Kapat')),
          FilledButton(
            onPressed: () {
              context.read<EditorProvider>().createUntitled(
                    name: 'gorev.trpy',
                    content: '# Günün Görevi: ${g.$1}\n# ${g.$2}\n# İpucu: ${g.$3}\n\n',
                    context: context,
                  );
              Navigator.pop(dc);
            },
            child: const Text('Yeni sekmede başla'),
          ),
        ],
      );
    }),
  );
}

// ============================================================================
// KOD PARÇACIKLARI
// ============================================================================

/// Yerleşik TürKod parçacıkları. "$0" imlecin konacağı yerdir.
const List<(String, String)> kYerlesikParcaciklar = [
  (
    'Ana program',
    'fonksiyon ana():\n    \$0\n\n\neğer __isim__ == "__main__":\n    ana()\n',
  ),
  (
    'Sayı tahmin oyunu',
    'içe_aktar rastgele\n\nsayı = rastgele.rastgele_tamsayı(1, 100)\ndeneme = 0\n'
        'döngü Doğru:\n    tahmin = tamsayı(girdi_al("Tahminin: "))\n    deneme += 1\n'
        '    eğer tahmin < sayı:\n        yazdır("Daha büyük!")\n'
        '    değilse_eğer tahmin > sayı:\n        yazdır("Daha küçük!")\n'
        '    değilse:\n        yazdır(f"Bildin! {deneme} denemede.")\n        kır\n',
  ),
  (
    'Sayı girdisi (doğrulamalı)',
    'döngü Doğru:\n    dene:\n        sayı = tamsayı(girdi_al("Bir sayı yaz: "))\n        kır\n'
        '    hata_yakala DeğerHatası:\n        yazdır("Lütfen bir sayı yaz!")\n\$0',
  ),
  (
    'Dosya okuma',
    'ile açık("dosya.txt", "r", kodlama="utf-8") olarak dosya:\n'
        '    için satır içinde dosya:\n        yazdır(satır.kırp())\n\$0',
  ),
  (
    'Dosyaya yazma',
    'ile açık("çıktı.txt", "w", kodlama="utf-8") olarak dosya:\n'
        '    dosya.yaz("Merhaba\\n")\n\$0',
  ),
  (
    'Liste üzerinde numaralı döngü',
    'için sıra, öğe içinde sıralı_numaralandır(liste, 1):\n    yazdır(sıra, öğe)\n\$0',
  ),
  (
    'Sözlük üzerinde döngü',
    'için anahtar, değer içinde sözlük_adı.öğeler():\n    yazdır(anahtar, değer)\n\$0',
  ),
  (
    'Sınıf',
    'sınıf Hayvan:\n    fonksiyon __başlat__(kendisi, ad):\n        kendisi.ad = ad\n\n'
        '    fonksiyon konuş(kendisi):\n        \$0\n',
  ),
  (
    'Hata yakalama',
    'dene:\n    \$0\nhata_yakala İstisna olarak hata:\n    yazdır("Hata:", hata)\n',
  ),
  (
    'Bekleme (saniye)',
    'içe_aktar zaman\n\nzaman.uyu(1)\n\$0',
  ),
];

/// Metni imlecin bulunduğu satırın girintisine uydurup imlece ekler.
void imleceEkle(BuildContext context, String parca) {
  final ed = context.read<EditorProvider>();
  final c = ed.uiController;
  if (c == null) {
    showAppSnackbar(context, 'Önce bir dosya aç.');
    return;
  }
  final t = c.text;
  final bas = c.selection.isValid ? c.selection.start.clamp(0, t.length) : t.length;
  final son = c.selection.isValid ? c.selection.end.clamp(0, t.length) : t.length;
  final satirBasi = t.lastIndexOf('\n', bas == 0 ? 0 : bas - 1) + 1;
  final girinti = RegExp(r'^[ \t]*').firstMatch(t.substring(satirBasi, bas))!.group(0)!;
  var metin = parca.replaceAll('\n', '\n$girinti');
  var imlec = metin.indexOf(r'$0');
  if (imlec >= 0) {
    metin = metin.replaceFirst(r'$0', '');
  } else {
    imlec = metin.length;
  }
  _setControllerValueProgrammatic(
    c,
    TextEditingValue(
      text: t.replaceRange(bas, son, metin),
      selection: TextSelection.collapsed(offset: bas + imlec),
    ),
  );
  ed.syncFromView();
}

Future<void> parcaciklariAc(BuildContext context) async {
  if (!await eklentiGerekli(context, kEklentiParcaciklar)) return;
  if (!context.mounted) return;
  final secilen = await showDialog<String>(
      context: context, builder: (_) => const _ParcacikDialog());
  if (secilen != null && context.mounted) imleceEkle(context, secilen);
}

class _ParcacikDialog extends StatefulWidget {
  const _ParcacikDialog();
  @override
  State<_ParcacikDialog> createState() => _ParcacikDialogState();
}

class _ParcacikDialogState extends State<_ParcacikDialog> {
  String _ara = '';
  int _secili = 0;

  List<(String, String, bool)> _liste(SettingsProvider s) {
    final kullanici = s.get<dynamic>('kod_parcaciklari');
    return [
      if (kullanici is List)
        for (final p in kullanici)
          if (p is Map) (p['ad']?.toString() ?? '', p['kod']?.toString() ?? '', true),
      for (final p in kYerlesikParcaciklar) (p.$1, p.$2, false),
    ];
  }

  Future<void> _seciliKaydet() async {
    final s = context.read<SettingsProvider>();
    final c = context.read<EditorProvider>().uiController;
    final secim = c != null && c.selection.isValid && !c.selection.isCollapsed
        ? c.selection.textInside(c.text)
        : '';
    if (secim.trim().isEmpty) {
      showAppSnackbar(context, 'Önce editörde parçacık yapılacak kodu seç.');
      return;
    }
    final ad = await _askName(context, 'Parçacık adı', 'Yeni parçacık');
    if (ad == null || !mounted) return;
    final eski = s.get<dynamic>('kod_parcaciklari');
    final yeni = [
      {'ad': ad, 'kod': secim},
      if (eski is List) ...eski,
    ];
    await s.setValue('kod_parcaciklari', yeni);
    if (mounted) setState(() {});
  }

  Future<void> _sil(String ad) async {
    final s = context.read<SettingsProvider>();
    final eski = s.get<dynamic>('kod_parcaciklari');
    if (eski is! List) return;
    await s.setValue('kod_parcaciklari',
        eski.where((p) => !(p is Map && p['ad'] == ad)).toList());
    if (mounted) setState(() => _secili = 0);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = context.watch<SettingsProvider>();
    final q = _ara.toLowerCase();
    final liste = _liste(s)
        .where((p) => q.isEmpty || p.$1.toLowerCase().contains(q) || p.$2.toLowerCase().contains(q))
        .toList();
    if (_secili >= liste.length) _secili = 0;
    return AlertDialog(
      title: const Text('Kod Parçacıkları'),
      content: SizedBox(
        width: 760,
        height: 420,
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 250,
            child: Column(children: [
              TextField(
                autofocus: true,
                decoration: const InputDecoration(
                    isDense: true, prefixIcon: Icon(Icons.search, size: 16), hintText: 'Ara…'),
                onChanged: (v) => setState(() => _ara = v),
                onSubmitted: (_) {
                  if (liste.isNotEmpty) Navigator.pop(context, liste[_secili].$2);
                },
              ),
              const SizedBox(height: 6),
              Expanded(
                child: ListView.builder(
                  itemCount: liste.length,
                  itemBuilder: (c, i) => ListTile(
                    dense: true,
                    selected: i == _secili,
                    leading: Icon(liste[i].$3 ? Icons.person_outline : Icons.widgets_outlined,
                        size: 16),
                    title: Text(liste[i].$1, style: const TextStyle(fontSize: 12.5)),
                    trailing: liste[i].$3
                        ? IconButton(
                            tooltip: 'Sil',
                            iconSize: 15,
                            icon: const Icon(Icons.delete_outline),
                            onPressed: () => _sil(liste[i].$1),
                          )
                        : null,
                    onTap: () => setState(() => _secili = i),
                  ),
                ),
              ),
            ]),
          ),
          const VerticalDivider(width: 16),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainer,
                  border: Border.all(color: theme.colorScheme.outlineVariant)),
              child: SingleChildScrollView(
                child: SelectableText(
                  liste.isEmpty ? '' : liste[_secili].$2.replaceAll(r'$0', '▌'),
                  style: const TextStyle(
                      fontFamily: kMonoFontFamily,
                      fontFamilyFallback: kMonoFontFallback,
                      fontSize: 12.5),
                ),
              ),
            ),
          ),
        ]),
      ),
      actions: [
        TextButton.icon(
          icon: const Icon(Icons.save_outlined, size: 16),
          label: const Text('Seçili kodu parçacık yap'),
          onPressed: _seciliKaydet,
        ),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Kapat')),
        FilledButton(
          onPressed: liste.isEmpty ? null : () => Navigator.pop(context, liste[_secili].$2),
          child: const Text('İmlece ekle'),
        ),
      ],
    );
  }
}

// ============================================================================
// MARKDOWN ÖNİZLEME
// ============================================================================

Future<void> markdownOnizle(BuildContext context) async {
  if (!await eklentiGerekli(context, kEklentiMarkdown)) return;
  if (!context.mounted) return;
  final ed = context.read<EditorProvider>();
  final ad = ed.activeTab?.name ?? '';
  final icerik = ed.activeContent.value;
  if (icerik.trim().isEmpty) {
    showAppSnackbar(context, 'Önizlenecek içerik yok.');
    return;
  }
  await showDialog<void>(
    context: context,
    builder: (dc) => AlertDialog(
      title: Row(children: [
        const Icon(Icons.article_outlined, size: 18),
        const SizedBox(width: 8),
        Expanded(child: Text('Önizleme — $ad', overflow: TextOverflow.ellipsis)),
      ]),
      content: SizedBox(
        width: 760,
        height: 520,
        child: SingleChildScrollView(
          child: SelectionArea(
            child: MarkdownGorunum(icerik,
                yaziBoyutu: 14, baglanti: (url) => baglantiAc(dc, url)),
          ),
        ),
      ),
      actions: [
        FilledButton(onPressed: () => Navigator.pop(dc), child: const Text('Kapat')),
      ],
    ),
  );
}

// ============================================================================
// ODAK ZAMANLAYICI (durum çubuğu)
// ============================================================================

class OdakZamanlayici extends StatefulWidget {
  const OdakZamanlayici({super.key});
  @override
  State<OdakZamanlayici> createState() => _OdakZamanlayiciState();
}

class _OdakZamanlayiciState extends State<OdakZamanlayici> {
  Timer? _zamanlayici;
  int _kalan = -1; // saniye; -1: başlamadı
  bool _mola = false;
  int _tamamlanan = 0;

  int get _odakSn =>
      context.read<SettingsProvider>().getInt('odak_suresi_dk', fallback: 25).clamp(1, 180) * 60;
  int get _molaSn => (_tamamlanan % 4 == 0 && _tamamlanan > 0 ? 15 : 5) * 60;

  @override
  void dispose() {
    _zamanlayici?.cancel();
    super.dispose();
  }

  void _baslatDuraklat() {
    if (_zamanlayici != null) {
      _zamanlayici!.cancel();
      setState(() => _zamanlayici = null);
      return;
    }
    if (_kalan <= 0) _kalan = _mola ? _molaSn : _odakSn;
    _zamanlayici = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _kalan--);
      if (_kalan > 0) return;
      _zamanlayici?.cancel();
      _zamanlayici = null;
      if (!_mola) _tamamlanan++;
      final mesaj = _mola
          ? 'Mola bitti. Yeni odak süresi için sayaca tıkla.'
          : 'Odak süresi bitti ($_tamamlanan. tur)! Biraz mola ver.';
      _mola = !_mola;
      _kalan = -1;
      showAppSnackbar(context, '⏰ $mesaj', kind: SnackKind.success);
      SystemSound.play(SystemSoundType.alert);
    });
    setState(() {});
  }

  void _sifirla() {
    _zamanlayici?.cancel();
    setState(() {
      _zamanlayici = null;
      _kalan = -1;
      _mola = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final calisiyor = _zamanlayici != null;
    final sn = _kalan < 0 ? (_mola ? _molaSn : _odakSn) : _kalan;
    final metin =
        '${(sn ~/ 60).toString().padLeft(2, '0')}:${(sn % 60).toString().padLeft(2, '0')}';
    final renk = _mola ? Colors.green.shade400 : theme.colorScheme.error;
    return Tooltip(
      message: '${_mola ? 'Mola' : 'Odak'} zamanlayıcı — tıkla: '
          '${calisiyor ? 'duraklat' : 'başlat'}, sağ tık: sıfırla '
          '(tamamlanan: $_tamamlanan)',
      child: InkWell(
        onTap: _baslatDuraklat,
        onSecondaryTap: _sifirla,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(calisiyor ? Icons.timer : Icons.timer_outlined,
                size: 13, color: calisiyor ? renk : null),
            const SizedBox(width: 3),
            Text(metin,
                style: TextStyle(
                    fontSize: 11,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    color: calisiyor ? renk : theme.colorScheme.onSurface.withOpacity(0.8))),
          ]),
        ),
      ),
    );
  }
}

// ============================================================================
// TÜRKOD KABUĞU
// ============================================================================

/// TürKod Kabuğu'nu açar: IDE terminalinde ya da ayrı bir pencerede.
Future<void> turkodKabuguAc(BuildContext context) async {
  final secim = await showDialog<String>(
    context: context,
    builder: (dc) => SimpleDialog(
      title: const Text('TürKod Kabuğu'),
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(24, 0, 24, 8),
          child: Text(
            'CMD tarzı komut satırı: TürKod kodunu satır satır çalıştır, '
            '"dersler" ile TürKod öğren, "düzelt / çalıştır / çevir" komutlarını kullan.',
            style: TextStyle(fontSize: 12),
          ),
        ),
        SimpleDialogOption(
          onPressed: () => Navigator.pop(dc, 'ide'),
          child: const ListTile(
            leading: Icon(Icons.terminal),
            title: Text('Program içinde aç'),
            subtitle: Text('Alttaki terminal panelinde'),
          ),
        ),
        SimpleDialogOption(
          onPressed: () => Navigator.pop(dc, 'pencere'),
          child: const ListTile(
            leading: Icon(Icons.open_in_new),
            title: Text('Ayrı pencerede aç'),
            subtitle: Text('Yeni bir komut penceresi (turkod --kabuk-pencere)'),
          ),
        ),
      ],
    ),
  );
  if (secim == null || !context.mounted) return;
  if (secim == 'ide') {
    context.read<UiProvider>().focusTerminal();
    await context.read<TerminalProvider>().kabukBaslat();
  } else {
    try {
      final r = await context.read<BackendService>().call('kabuk_penceresi');
      if (r['ok'] != true && context.mounted) {
        showAppSnackbar(context, 'Kabuk penceresi açılamadı.', kind: SnackKind.error);
      }
    } catch (e) {
      if (context.mounted) {
        showAppSnackbar(context, 'Kabuk penceresi açılamadı: $e', kind: SnackKind.error);
      }
    }
  }
}
