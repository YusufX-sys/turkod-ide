// İlk açılışta (ve Yardım > Arayüz Turu ile) gösterilen arayüz turu:
// ekran karartılır, anlatılan bölge aydınlık bir pencereyle vurgulanır,
// yanında açıklama kutusu durur ve kutudan bölgeye bir ok uzanır.
import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Ayar anahtarları (backend ayar dosyasında saklanır).
const String kTurHerAcilista = 'arayuz_turu_her_acilista';
const String kTurGoruldu = 'arayuz_turu_goruldu';

/// Turun gösterdiği arayüz bölgeleri. Ana yerleşim bu anahtarları ilgili
/// widget'lara verir; görünmeyen (kapalı) paneller turda atlanır.
class TurHedefleri {
  TurHedefleri._();
  static final menu = GlobalKey(debugLabel: 'tur.menu');
  static final yardimMenusu = GlobalKey(debugLabel: 'tur.yardim');
  static final ayarlar = GlobalKey(debugLabel: 'tur.ayarlar');
  static final aracCubugu = GlobalKey(debugLabel: 'tur.arac');
  static final calistir = GlobalKey(debugLabel: 'tur.calistir');
  static final duzelt = GlobalKey(debugLabel: 'tur.duzelt');
  static final hataAyikla = GlobalKey(debugLabel: 'tur.debug');
  static final gezgin = GlobalKey(debugLabel: 'tur.gezgin');
  static final sekmeler = GlobalKey(debugLabel: 'tur.sekmeler');
  static final editor = GlobalKey(debugLabel: 'tur.editor');
  static final terminal = GlobalKey(debugLabel: 'tur.terminal');
  static final ai = GlobalKey(debugLabel: 'tur.ai');
  static final durum = GlobalKey(debugLabel: 'tur.durum');
}

class TurAdimi {
  final GlobalKey? hedef;
  final IconData ikon;
  final String baslik;
  final String metin;
  final String? ipucu;
  const TurAdimi({
    this.hedef,
    required this.ikon,
    required this.baslik,
    required this.metin,
    this.ipucu,
  });
}

List<TurAdimi> varsayilanTurAdimlari() => [
      const TurAdimi(
        ikon: Icons.waving_hand_outlined,
        baslik: "TürKod IDE'ye hoş geldin!",
        metin: 'Bu kısa turda ekrandaki bölümleri tek tek tanıyacağız. '
            'Yaklaşık bir dakika sürer.',
        ipucu: 'İleri için → ya da Enter, geri için ←, turu kapatmak için Esc.',
      ),
      TurAdimi(
        hedef: TurHedefleri.menu,
        ikon: Icons.menu,
        baslik: 'Menü çubuğu',
        metin: 'Dosya, Düzenle, Görünüm, Çalıştır, Araçlar, Öğren ve Yardım '
            'menülerindeki tüm komutlar burada. Bir menüye tıklayınca '
            'kısayolları da yanında görürsün.',
      ),
      TurAdimi(
        hedef: TurHedefleri.aracCubugu,
        ikon: Icons.handyman_outlined,
        baslik: 'Araç çubuğu',
        metin: 'En sık kullanılan komutlar tek tıkla: yeni dosya, aç, kaydet, '
            'çevir, düzelt, bul ve hata ayıklama düğmeleri.',
        ipucu: 'Fareyi bir düğmenin üstünde bekletirsen adını ve kısayolunu '
            'gösterir.',
      ),
      TurAdimi(
        hedef: TurHedefleri.calistir,
        ikon: Icons.play_arrow_rounded,
        baslik: 'Çalıştır ve Durdur',
        metin: 'Yeşil ok kodunu çalıştırır (Ctrl+R), kırmızı kare çalışan '
            'programı durdurur.',
      ),
      TurAdimi(
        hedef: TurHedefleri.duzelt,
        ikon: Icons.auto_fix_high,
        baslik: 'Akıllı düzeltme',
        metin: 'Kodunda yazım ya da girinti hatası varsa bu düğme hataları bulup '
            'düzeltmeyi dener ve ne değiştirdiğini anlatır.',
      ),
      TurAdimi(
        hedef: TurHedefleri.hataAyikla,
        ikon: Icons.bug_report_outlined,
        baslik: 'Hata ayıklayıcı',
        metin: 'Programı adım adım çalıştırıp değişkenlerin değerlerini '
            'izleyebilirsin (F5). Satır numarasına tıklayarak kesme noktası '
            'koyarsın.',
      ),
      TurAdimi(
        hedef: TurHedefleri.gezgin,
        ikon: Icons.folder_outlined,
        baslik: 'Gezgin',
        metin: 'Proje klasöründeki dosyalar burada. Bir dosyaya tıklayınca '
            'editörde açılır; sağ tıkla yeni dosya ya da klasör oluşturabilirsin.',
      ),
      TurAdimi(
        hedef: TurHedefleri.sekmeler,
        ikon: Icons.tab_outlined,
        baslik: 'Sekmeler',
        metin: 'Açık dosyaların her biri bir sekme. Kaydedilmemiş sekmede adın '
            'yanında bir nokta görünür. + ile yeni sekme açılır (Ctrl+T).',
      ),
      TurAdimi(
        hedef: TurHedefleri.editor,
        ikon: Icons.edit_note,
        baslik: 'Editör',
        metin: 'Kodunu buraya yazarsın. Komutlar renklenir, yazarken öneriler '
            'çıkar; sözdizimi hatası olan satır kırmızıyla işaretlenir.',
      ),
      TurAdimi(
        hedef: TurHedefleri.terminal,
        ikon: Icons.terminal,
        baslik: 'Terminal',
        metin: 'Programının çıktısı burada görünür. Program bir şey sorarsa '
            'cevabını buraya yazıp Enter\'a basarsın.',
      ),
      TurAdimi(
        hedef: TurHedefleri.ai,
        ikon: Icons.auto_awesome,
        baslik: 'AI Asistan',
        metin: 'Takıldığın yerde kodunu açıklatabilir ya da soru sorabilirsin. '
            'Ayarlar\'dan bir yapay zekâ sağlayıcısı seçmen gerekir.',
      ),
      TurAdimi(
        hedef: TurHedefleri.durum,
        ikon: Icons.info_outline,
        baslik: 'Durum çubuğu',
        metin: 'İmlecin satır ve sütunu, dosya adı ve "Sözdizimi doğru" '
            'bilgisi burada.',
      ),
      TurAdimi(
        hedef: TurHedefleri.ayarlar,
        ikon: Icons.settings_outlined,
        baslik: 'Ayarlar',
        metin: 'Tema, yazı boyutu, otomatik kaydetme ve AI ayarları burada. '
            'Bu turun her açılışta gösterilip gösterilmeyeceğini de buradan '
            'seçebilirsin.',
      ),
      TurAdimi(
        hedef: TurHedefleri.yardimMenusu,
        ikon: Icons.flag_outlined,
        baslik: 'Hazırsın!',
        metin: 'Turu istediğin zaman Yardım > Arayüz Turu ile yeniden '
            'açabilirsin. Şimdi ilk programını yazma zamanı!',
      ),
    ];

bool _turAcik = false;

/// Turu gösterir; tamamlanınca ya da atlanınca döner.
/// [herAcilista]: "Her açılışta göster" kutusunun başlangıç değeri;
/// kutu değiştikçe [herAcilistaKaydet] çağrılır.
Future<void> arayuzTurunuGoster(
  BuildContext context, {
  required bool herAcilista,
  required Future<void> Function(bool) herAcilistaKaydet,
  List<TurAdimi>? adimlar,
}) async {
  if (_turAcik) return;
  _turAcik = true;
  try {
    await showGeneralDialog<void>(
      context: context,
      barrierDismissible: false,
      barrierColor: Colors.transparent,
      barrierLabel: 'Arayüz turu',
      transitionDuration: const Duration(milliseconds: 260),
      pageBuilder: (c, a1, a2) => _TurKatmani(
        adimlar: adimlar ?? varsayilanTurAdimlari(),
        herAcilista: herAcilista,
        herAcilistaKaydet: herAcilistaKaydet,
      ),
      transitionBuilder: (c, anim, a2, child) =>
          FadeTransition(opacity: anim, child: child),
    );
  } finally {
    _turAcik = false;
  }
}

// ---------------------------------------------------------------------------

enum _Yer { alt, ust, sag, sol, ic, orta }

class _TurKatmani extends StatefulWidget {
  final List<TurAdimi> adimlar;
  final bool herAcilista;
  final Future<void> Function(bool) herAcilistaKaydet;
  const _TurKatmani({
    required this.adimlar,
    required this.herAcilista,
    required this.herAcilistaKaydet,
  });

  @override
  State<_TurKatmani> createState() => _TurKatmaniState();
}

class _TurKatmaniState extends State<_TurKatmani>
    with SingleTickerProviderStateMixin {
  static const double _kutuGenislik = 360;
  static const double _okBoslugu = 46;
  static const double _kenar = 16;

  late final AnimationController _nabiz = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1400))
    ..repeat(reverse: true);
  final FocusNode _odak = FocusNode(debugLabel: 'arayuz-turu');
  final GlobalKey _kutuAnahtari = GlobalKey();
  Size _kutuBoyutu = const Size(_kutuGenislik, 230);
  late bool _herAcilista = widget.herAcilista;
  int _sira = 0;
  Timer? _olcum;

  @override
  void initState() {
    super.initState();
    // Paneller açılış animasyonuyla büyüyebildiği için hedefler kısa süre
    // yeniden ölçülür; pencere boyutu değişince de build yeniden çalışır.
    _olcum = Timer.periodic(const Duration(milliseconds: 250), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _olcum?.cancel();
    _nabiz.dispose();
    _odak.dispose();
    super.dispose();
  }

  static Rect? _hedefDikdortgeni(GlobalKey? k, Size ekran) {
    if (k == null) return null;
    final ro = k.currentContext?.findRenderObject();
    if (ro is! RenderBox || !ro.attached || !ro.hasSize) return null;
    final r = ro.localToGlobal(Offset.zero) & ro.size;
    final gorunen = r.intersect(Offset.zero & ekran);
    if (gorunen.width < 6 || gorunen.height < 6) return null;
    return gorunen;
  }

  /// Şu an ekranda olan adımlar (kapalı paneller atlanır).
  List<(TurAdimi, Rect?)> _gorunenAdimlar(Size ekran) => [
        for (final a in widget.adimlar)
          if (a.hedef == null)
            (a, null)
          else if (_hedefDikdortgeni(a.hedef, ekran) case final Rect r)
            (a, r),
      ];

  void _kapat() {
    if (mounted) Navigator.of(context).pop();
  }

  void _ileri(int toplam) {
    if (_sira >= toplam - 1) {
      _kapat();
    } else {
      setState(() => _sira++);
    }
  }

  void _geri() {
    if (_sira > 0) setState(() => _sira--);
  }

  KeyEventResult _tus(FocusNode n, KeyEvent e, int toplam) {
    if (e is! KeyDownEvent) return KeyEventResult.ignored;
    final k = e.logicalKey;
    if (k == LogicalKeyboardKey.escape) {
      _kapat();
    } else if (k == LogicalKeyboardKey.arrowRight ||
        k == LogicalKeyboardKey.enter ||
        k == LogicalKeyboardKey.numpadEnter ||
        k == LogicalKeyboardKey.space) {
      _ileri(toplam);
    } else if (k == LogicalKeyboardKey.arrowLeft) {
      _geri();
    } else {
      return KeyEventResult.ignored;
    }
    return KeyEventResult.handled;
  }

  void _kutuyuOlc() {
    final ro = _kutuAnahtari.currentContext?.findRenderObject();
    if (ro is RenderBox && ro.hasSize && ro.size != _kutuBoyutu) {
      setState(() => _kutuBoyutu = ro.size);
    }
  }

  /// Açıklama kutusunun yeri, sol üst köşesi ve okun başlangıç/bitişi.
  (_Yer, Offset, Offset?, Offset?) _yerlesim(Rect? hedef, Size ekran) {
    final kw = math.min(_kutuGenislik, ekran.width - 2 * _kenar);
    final kh = _kutuBoyutu.height;
    double yatay(double merkez) =>
        (merkez - kw / 2).clamp(_kenar, math.max(_kenar, ekran.width - kw - _kenar));
    double dikey(double merkez) =>
        (merkez - kh / 2).clamp(_kenar, math.max(_kenar, ekran.height - kh - _kenar));

    if (hedef == null) {
      return (
        _Yer.orta,
        Offset((ekran.width - kw) / 2, (ekran.height - kh) / 2),
        null,
        null
      );
    }
    final h = hedef.inflate(8);
    final gerekenDikey = kh + _okBoslugu + _kenar;
    final gerekenYatay = kw + _okBoslugu + _kenar;
    final altBosluk = ekran.height - h.bottom;
    final ustBosluk = h.top;
    final sagBosluk = ekran.width - h.right;
    final solBosluk = h.left;
    final buyuk = hedef.width * hedef.height > ekran.width * ekran.height * 0.25;

    if (!buyuk && altBosluk >= gerekenDikey) {
      final sol = yatay(hedef.center.dx);
      final ust = h.bottom + _okBoslugu;
      final bas = Offset((sol + kw / 2).clamp(sol + 30, sol + kw - 30), ust);
      final son = Offset(
          hedef.center.dx.clamp(hedef.left + 6, hedef.right - 6), h.bottom + 2);
      return (_Yer.alt, Offset(sol, ust), bas, son);
    }
    if (!buyuk && ustBosluk >= gerekenDikey) {
      final sol = yatay(hedef.center.dx);
      final ust = h.top - _okBoslugu - kh;
      final bas = Offset((sol + kw / 2).clamp(sol + 30, sol + kw - 30), ust + kh);
      final son = Offset(
          hedef.center.dx.clamp(hedef.left + 6, hedef.right - 6), h.top - 2);
      return (_Yer.ust, Offset(sol, ust), bas, son);
    }
    if (sagBosluk >= gerekenYatay) {
      final ust = dikey(hedef.center.dy);
      final sol = h.right + _okBoslugu;
      final bas = Offset(sol, (ust + 40).clamp(ust + 20, ust + kh - 20));
      final son = Offset(
          h.right + 2, bas.dy.clamp(hedef.top + 10, hedef.bottom - 10));
      return (_Yer.sag, Offset(sol, ust), bas, son);
    }
    if (solBosluk >= gerekenYatay) {
      final ust = dikey(hedef.center.dy);
      final sol = h.left - _okBoslugu - kw;
      final bas = Offset(sol + kw, (ust + 40).clamp(ust + 20, ust + kh - 20));
      final son = Offset(
          h.left - 2, bas.dy.clamp(hedef.top + 10, hedef.bottom - 10));
      return (_Yer.sol, Offset(sol, ust), bas, son);
    }
    // Hedef ekranın büyük kısmını kaplıyor (ör. editör): kutu hedefin
    // içine, alt kısma konur; ok hedefin sol üstündeki kod alanını gösterir.
    final sol = yatay(hedef.center.dx + hedef.width * 0.12);
    final ust = (hedef.bottom - kh - 28)
        .clamp(hedef.top + 90, math.max(hedef.top + 90, ekran.height - kh - _kenar))
        .toDouble();
    final bas = Offset(sol + 36, ust);
    final son = Offset(hedef.left + math.min(140.0, hedef.width * 0.25),
        hedef.top + math.min(48.0, hedef.height * 0.2));
    return (_Yer.ic, Offset(sol, ust), bas, son);
  }

  @override
  Widget build(BuildContext context) {
    final ekran = MediaQuery.sizeOf(context);
    final adimlar = _gorunenAdimlar(ekran);
    if (adimlar.isEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _kapat());
      return const SizedBox.shrink();
    }
    if (_sira >= adimlar.length) _sira = adimlar.length - 1;
    final (adim, hedef) = adimlar[_sira];
    final (yer, kutuKonumu, okBas, okSon) = _yerlesim(hedef, ekran);
    final tema = Theme.of(context);
    final vurgu = tema.colorScheme.primary;
    final delik = hedef == null
        ? Rect.fromCenter(center: ekran.center(Offset.zero), width: 0, height: 0)
        : hedef.inflate(6);
    WidgetsBinding.instance.addPostFrameCallback((_) => _kutuyuOlc());

    return Focus(
      focusNode: _odak,
      autofocus: true,
      onKeyEvent: (n, e) => _tus(n, e, adimlar.length),
      child: Stack(children: [
        // Karartma + aydınlık pencere + nabız gibi atan çerçeve.
        Positioned.fill(
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () {},
            child: TweenAnimationBuilder<Rect?>(
              tween: RectTween(end: delik),
              duration: const Duration(milliseconds: 380),
              curve: Curves.easeInOutCubic,
              builder: (c, r, _) => AnimatedBuilder(
                animation: _nabiz,
                builder: (c, _) => CustomPaint(
                  painter: _KarartmaBoyaci(
                    delik: r ?? delik,
                    vurgu: vurgu,
                    nabiz: _nabiz.value,
                  ),
                ),
              ),
            ),
          ),
        ),
        // Ok
        if (okBas != null && okSon != null)
          Positioned.fill(
            child: IgnorePointer(
              child: TweenAnimationBuilder<double>(
                key: ValueKey('ok-$_sira-${yer.name}'),
                tween: Tween(begin: 0, end: 1),
                duration: const Duration(milliseconds: 420),
                curve: Curves.easeOutCubic,
                builder: (c, t, _) => CustomPaint(
                  painter: _OkBoyaci(
                    bas: okBas,
                    son: okSon,
                    yer: yer,
                    renk: vurgu,
                    ilerleme: t,
                  ),
                ),
              ),
            ),
          ),
        // Açıklama kutusu
        AnimatedPositioned(
          duration: const Duration(milliseconds: 380),
          curve: Curves.easeInOutCubic,
          left: kutuKonumu.dx,
          top: kutuKonumu.dy,
          width: math.min(_kutuGenislik, ekran.width - 2 * _kenar),
          child: _AciklamaKutusu(
            key: _kutuAnahtari,
            adim: adim,
            sira: _sira,
            toplam: adimlar.length,
            herAcilista: _herAcilista,
            onHerAcilista: (v) {
              setState(() => _herAcilista = v);
              widget.herAcilistaKaydet(v).catchError((_) {});
            },
            onIleri: () => _ileri(adimlar.length),
            onGeri: _sira > 0 ? _geri : null,
            onAtla: _kapat,
          ),
        ),
      ]),
    );
  }
}

class _AciklamaKutusu extends StatelessWidget {
  final TurAdimi adim;
  final int sira, toplam;
  final bool herAcilista;
  final ValueChanged<bool> onHerAcilista;
  final VoidCallback onIleri;
  final VoidCallback? onGeri;
  final VoidCallback onAtla;
  const _AciklamaKutusu({
    super.key,
    required this.adim,
    required this.sira,
    required this.toplam,
    required this.herAcilista,
    required this.onHerAcilista,
    required this.onIleri,
    required this.onGeri,
    required this.onAtla,
  });

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final cs = tema.colorScheme;
    final son = sira == toplam - 1;
    return Material(
      color: cs.surfaceContainerHigh,
      elevation: 12,
      shadowColor: Colors.black,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: cs.primary.withValues(alpha: 0.55), width: 1.2),
        ),
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
        child: AnimatedSize(
          duration: const Duration(milliseconds: 200),
          alignment: Alignment.topCenter,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 200),
            child: Column(
              key: ValueKey(sira),
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Container(
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      color: cs.primary.withValues(alpha: 0.16),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(adim.ikon, size: 17, color: cs.primary),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(adim.baslik,
                        style: tema.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700)),
                  ),
                  Text('${sira + 1} / $toplam',
                      style: tema.textTheme.labelSmall?.copyWith(
                          color: cs.onSurface.withValues(alpha: 0.6))),
                ]),
                const SizedBox(height: 10),
                Text(adim.metin,
                    style: tema.textTheme.bodyMedium?.copyWith(height: 1.4)),
                if (adim.ipucu != null) ...[
                  const SizedBox(height: 8),
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(Icons.lightbulb_outline, size: 15, color: cs.tertiary),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(adim.ipucu!,
                          style: tema.textTheme.bodySmall?.copyWith(
                              color: cs.onSurface.withValues(alpha: 0.75))),
                    ),
                  ]),
                ],
                const SizedBox(height: 12),
                // İlerleme noktaları
                Row(children: [
                  for (var i = 0; i < toplam; i++)
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      margin: const EdgeInsets.only(right: 4),
                      width: i == sira ? 16 : 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: i <= sira
                            ? cs.primary
                            : cs.onSurface.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                ]),
                const SizedBox(height: 6),
                Row(children: [
                  Expanded(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(6),
                      onTap: () => onHerAcilista(!herAcilista),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        SizedBox(
                          width: 30,
                          height: 30,
                          child: Checkbox(
                            value: herAcilista,
                            visualDensity: VisualDensity.compact,
                            onChanged: (v) => onHerAcilista(v ?? false),
                          ),
                        ),
                        Flexible(
                          child: Text('Her açılışta göster',
                              overflow: TextOverflow.ellipsis,
                              style: tema.textTheme.bodySmall),
                        ),
                      ]),
                    ),
                  ),
                ]),
                const SizedBox(height: 4),
                Row(children: [
                  if (!son)
                    TextButton(onPressed: onAtla, child: const Text('Turu atla')),
                  const Spacer(),
                  if (onGeri != null)
                    OutlinedButton(onPressed: onGeri, child: const Text('Geri')),
                  const SizedBox(width: 8),
                  FilledButton(
                    autofocus: true,
                    onPressed: onIleri,
                    child: Text(son ? 'Bitir' : 'İleri'),
                  ),
                ]),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _KarartmaBoyaci extends CustomPainter {
  final Rect delik;
  final Color vurgu;
  final double nabiz;
  _KarartmaBoyaci({required this.delik, required this.vurgu, required this.nabiz});

  @override
  void paint(Canvas canvas, Size size) {
    final tum = Offset.zero & size;
    final yaricap = Radius.circular(delik.isEmpty ? 0 : 10);
    final pencere = RRect.fromRectAndRadius(delik, yaricap);
    final karartma = Path.combine(
      PathOperation.difference,
      Path()..addRect(tum),
      Path()..addRRect(pencere),
    );
    canvas.drawPath(karartma, Paint()..color = Colors.black.withValues(alpha: 0.72));
    if (delik.isEmpty) return;
    // Dış parıltı ve çerçeve (nabız gibi atar).
    canvas.drawRRect(
      pencere.inflate(2 + 4 * nabiz),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6
        ..color = vurgu.withValues(alpha: 0.18 + 0.22 * (1 - nabiz))
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
    );
    canvas.drawRRect(
      pencere,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.4
        ..color = vurgu,
    );
  }

  @override
  bool shouldRepaint(_KarartmaBoyaci o) =>
      o.delik != delik || o.vurgu != vurgu || o.nabiz != nabiz;
}

class _OkBoyaci extends CustomPainter {
  final Offset bas, son;
  final _Yer yer;
  final Color renk;
  final double ilerleme;
  _OkBoyaci({
    required this.bas,
    required this.son,
    required this.yer,
    required this.renk,
    required this.ilerleme,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Hafif kavisli bir yol: kontrol noktası iki ucun ortasından yana kayık.
    final orta = Offset.lerp(bas, son, 0.5)!;
    final yon = son - bas;
    final uzunluk = yon.distance;
    if (uzunluk < 4) return;
    final dik = Offset(-yon.dy, yon.dx) / uzunluk;
    final kavis = math.min(60.0, uzunluk * 0.25);
    final kontrol = orta + dik * (yer == _Yer.sol || yer == _Yer.ust ? -kavis : kavis);
    final yol = Path()
      ..moveTo(bas.dx, bas.dy)
      ..quadraticBezierTo(kontrol.dx, kontrol.dy, son.dx, son.dy);

    final metrik = yol.computeMetrics().first;
    final cizilen = metrik.extractPath(0, metrik.length * ilerleme);
    final kalem = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..color = renk;
    canvas.drawPath(
        cizilen,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 7
          ..strokeCap = StrokeCap.round
          ..color = Colors.black.withValues(alpha: 0.35));
    canvas.drawPath(cizilen, kalem);
    // Başlangıçta küçük bir daire.
    canvas.drawCircle(bas, 4.5, Paint()..color = renk);
    if (ilerleme < 0.98) return;
    // Uçta ok başı (eğrinin son yönüne göre).
    final t = metrik.getTangentForOffset(metrik.length)!;
    final aci = math.atan2(t.vector.dy, t.vector.dx);
    const boy = 14.0;
    const genis = 0.48;
    final uc = son;
    final sol = uc - Offset(math.cos(aci - genis), math.sin(aci - genis)) * boy;
    final sag = uc - Offset(math.cos(aci + genis), math.sin(aci + genis)) * boy;
    final bas2 = Path()
      ..moveTo(uc.dx, uc.dy)
      ..lineTo(sol.dx, sol.dy)
      ..lineTo(sag.dx, sag.dy)
      ..close();
    canvas.drawPath(bas2, Paint()..color = renk);
  }

  @override
  bool shouldRepaint(_OkBoyaci o) =>
      o.bas != bas || o.son != son || o.ilerleme != ilerleme || o.renk != renk;
}
