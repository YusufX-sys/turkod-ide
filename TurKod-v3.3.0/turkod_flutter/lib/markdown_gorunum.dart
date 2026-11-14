// Hafif Markdown görüntüleyici (AI yanıtları ve .md önizleme).
//
// Harici paket kullanılmaz (çevrimdışı derleme, küçük boyut). Desteklenenler:
// başlıklar (#…######), kalın/italik/üstü çizili, satır içi kod, bağlantılar,
// madde ve numaralı listeler (iç içe), görev kutuları, alıntı (>), yatay
// çizgi, tablolar ve ``` kod blokları. Metin seçilebilir olsun diye üstte bir
// SelectionArea kullanılmalıdır (AI balonu bunu yapar).
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const String _kMono = 'Consolas';
const List<String> _kMonoYedek = ['Menlo', 'Courier New', 'monospace'];

/// Markdown metnini blok listesine ayırır (test edilebilir, saf Dart).
List<MdBlok> markdownAyristir(String metin) {
  final satirlar = metin.replaceAll('\r\n', '\n').split('\n');
  final bloklar = <MdBlok>[];
  var i = 0;
  final paragraf = <String>[];

  void paragrafiBitir() {
    if (paragraf.isEmpty) return;
    bloklar.add(MdBlok(MdTur.paragraf, metin: paragraf.join('\n')));
    paragraf.clear();
  }

  final baslikRe = RegExp(r'^(#{1,6})\s+(.*?)\s*#*\s*$');
  final listeRe = RegExp(r'^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$');
  final cizgiRe = RegExp(r'^\s{0,3}([-*_])(\s*\1){2,}\s*$');
  final tabloAyiriciRe = RegExp(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$');

  while (i < satirlar.length) {
    final s = satirlar[i];
    final kirpik = s.trimLeft();

    // Kod bloğu
    if (kirpik.startsWith('```') || kirpik.startsWith('~~~')) {
      paragrafiBitir();
      final cit = kirpik.substring(0, 3);
      final dil = kirpik.substring(3).trim();
      final govde = <String>[];
      i++;
      while (i < satirlar.length && !satirlar[i].trimLeft().startsWith(cit)) {
        govde.add(satirlar[i]);
        i++;
      }
      i++; // kapanış
      bloklar.add(MdBlok(MdTur.kod, metin: govde.join('\n'), dil: dil));
      continue;
    }

    if (s.trim().isEmpty) {
      paragrafiBitir();
      i++;
      continue;
    }

    final b = baslikRe.firstMatch(s);
    if (b != null) {
      paragrafiBitir();
      bloklar.add(MdBlok(MdTur.baslik, metin: b.group(2)!, duzey: b.group(1)!.length));
      i++;
      continue;
    }

    if (cizgiRe.hasMatch(s) && paragraf.isEmpty) {
      bloklar.add(MdBlok(MdTur.cizgi));
      i++;
      continue;
    }

    // Tablo: başlık satırı + ayırıcı satır
    if (s.contains('|') &&
        i + 1 < satirlar.length &&
        tabloAyiriciRe.hasMatch(satirlar[i + 1])) {
      paragrafiBitir();
      List<String> hucreler(String satir) {
        var t = satir.trim();
        if (t.startsWith('|')) t = t.substring(1);
        if (t.endsWith('|')) t = t.substring(0, t.length - 1);
        return t.split('|').map((h) => h.trim()).toList();
      }

      final satirListesi = <List<String>>[hucreler(s)];
      i += 2;
      while (i < satirlar.length &&
          satirlar[i].contains('|') &&
          satirlar[i].trim().isNotEmpty) {
        satirListesi.add(hucreler(satirlar[i]));
        i++;
      }
      bloklar.add(MdBlok(MdTur.tablo, tablo: satirListesi));
      continue;
    }

    if (kirpik.startsWith('>')) {
      paragrafiBitir();
      final ic = <String>[];
      while (i < satirlar.length && satirlar[i].trimLeft().startsWith('>')) {
        ic.add(satirlar[i].trimLeft().substring(1).replaceFirst(RegExp(r'^ '), ''));
        i++;
      }
      bloklar.add(MdBlok(MdTur.alinti, cocuklar: markdownAyristir(ic.join('\n'))));
      continue;
    }

    final l = listeRe.firstMatch(s);
    if (l != null) {
      paragrafiBitir();
      final ogeler = <MdListeOgesi>[];
      while (i < satirlar.length) {
        final m = listeRe.firstMatch(satirlar[i]);
        if (m != null) {
          final girinti = m.group(1)!.replaceAll('\t', '    ').length;
          final isaret = m.group(2)!;
          var icerik = m.group(3)!;
          bool? gorev;
          final g = RegExp(r'^\[([ xX])\]\s+').firstMatch(icerik);
          if (g != null) {
            gorev = g.group(1)!.toLowerCase() == 'x';
            icerik = icerik.substring(g.end);
          }
          ogeler.add(MdListeOgesi(
            duzey: girinti ~/ 2,
            numara: RegExp(r'^\d').hasMatch(isaret)
                ? int.tryParse(isaret.substring(0, isaret.length - 1))
                : null,
            metin: icerik,
            gorev: gorev,
          ));
          i++;
        } else if (satirlar[i].trim().isNotEmpty &&
            satirlar[i].startsWith(RegExp(r'\s{2,}')) &&
            ogeler.isNotEmpty) {
          // Önceki maddenin devam satırı
          final son = ogeler.removeLast();
          ogeler.add(MdListeOgesi(
              duzey: son.duzey,
              numara: son.numara,
              gorev: son.gorev,
              metin: '${son.metin} ${satirlar[i].trim()}'));
          i++;
        } else {
          break;
        }
      }
      bloklar.add(MdBlok(MdTur.liste, liste: ogeler));
      continue;
    }

    paragraf.add(s);
    i++;
  }
  paragrafiBitir();
  return bloklar;
}

enum MdTur { paragraf, baslik, kod, liste, alinti, cizgi, tablo }

class MdListeOgesi {
  final int duzey;
  final int? numara;
  final String metin;
  final bool? gorev;
  const MdListeOgesi(
      {required this.duzey, required this.metin, this.numara, this.gorev});
}

class MdBlok {
  final MdTur tur;
  final String metin;
  final int duzey;
  final String dil;
  final List<MdListeOgesi> liste;
  final List<List<String>> tablo;
  final List<MdBlok> cocuklar;
  const MdBlok(this.tur,
      {this.metin = '',
      this.duzey = 0,
      this.dil = '',
      this.liste = const [],
      this.tablo = const [],
      this.cocuklar = const []});
}

/// Ayrıştırılmış metinlerin küçük önbelleği: Kodi harf harf yazarken balon
/// her ~14 ms'de yeniden çizilir; eskiden bütün mesajlar her seferinde
/// baştan ayrıştırılıyordu.
final Map<String, List<MdBlok>> _ayristirmaOnbellegi = {};
const int _kOnbellekBoyu = 96;

/// [markdownAyristir]'ın önbellekli hâli (aynı metin ikinci kez ayrıştırılmaz).
List<MdBlok> markdownAyristirOnbellekli(String metin) {
  final bulunan = _ayristirmaOnbellegi.remove(metin);
  if (bulunan != null) {
    _ayristirmaOnbellegi[metin] = bulunan; // en yeni sona
    return bulunan;
  }
  final bloklar = markdownAyristir(metin);
  _ayristirmaOnbellegi[metin] = bloklar;
  if (_ayristirmaOnbellegi.length > _kOnbellekBoyu) {
    _ayristirmaOnbellegi.remove(_ayristirmaOnbellegi.keys.first);
  }
  return bloklar;
}

/// Satır içi biçimlendirme: **kalın**, *italik*, ~~çizili~~, `kod`, [a](b).
/// [taniyici]: bağlantı dokunuşu için tanıyıcıyı verir (verilmezse her
/// seferinde yenisi kurulur; onu atmak çağırana kalır).
List<InlineSpan> markdownSatirIci(String metin, TextStyle taban,
    {required Color kodZemin,
    required Color baglantiRengi,
    void Function(String url)? baglanti,
    GestureRecognizer Function(String url)? taniyici}) {
  final spanlar = <InlineSpan>[];
  final desen = RegExp(
      r'(`+)(.+?)\1' // satır içi kod
      r'|\*\*(.+?)\*\*|__(.+?)__' // kalın
      r'|~~(.+?)~~' // çizili
      r'|\[([^\]]+)\]\(([^)\s]+)\)' // bağlantı
      r'|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)' // italik *
      r'|(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w])' // italik _
      r'|(https?://[^\s<>()]+[^\s<>().,;:!?])', // çıplak bağlantı
      dotAll: true);
  var son = 0;
  for (final m in desen.allMatches(metin)) {
    if (m.start > son) {
      spanlar.add(TextSpan(text: metin.substring(son, m.start), style: taban));
    }
    if (m.group(2) != null) {
      spanlar.add(TextSpan(
          text: m.group(2),
          style: taban.copyWith(
              fontFamily: _kMono,
              fontFamilyFallback: _kMonoYedek,
              fontSize: (taban.fontSize ?? 13) * 0.95,
              backgroundColor: kodZemin)));
    } else if (m.group(3) != null || m.group(4) != null) {
      spanlar.addAll(markdownSatirIci(m.group(3) ?? m.group(4)!,
          taban.copyWith(fontWeight: FontWeight.w700),
          kodZemin: kodZemin,
          baglantiRengi: baglantiRengi,
          baglanti: baglanti,
          taniyici: taniyici));
    } else if (m.group(5) != null) {
      spanlar.addAll(markdownSatirIci(
          m.group(5)!, taban.copyWith(decoration: TextDecoration.lineThrough),
          kodZemin: kodZemin,
          baglantiRengi: baglantiRengi,
          baglanti: baglanti,
          taniyici: taniyici));
    } else if (m.group(6) != null || m.group(10) != null) {
      final yazi = m.group(6) ?? m.group(10)!;
      final url = m.group(7) ?? m.group(10)!;
      spanlar.add(TextSpan(
        text: yazi,
        style: taban.copyWith(
            color: baglantiRengi, decoration: TextDecoration.underline),
        mouseCursor: SystemMouseCursors.click,
        recognizer: baglanti == null
            ? null
            : taniyici != null
                ? taniyici(url)
                : (TapGestureRecognizer()..onTap = () => baglanti(url)),
      ));
    } else if (m.group(8) != null || m.group(9) != null) {
      spanlar.addAll(markdownSatirIci(m.group(8) ?? m.group(9)!,
          taban.copyWith(fontStyle: FontStyle.italic),
          kodZemin: kodZemin,
          baglantiRengi: baglantiRengi,
          baglanti: baglanti,
          taniyici: taniyici));
    }
    son = m.end;
  }
  if (son < metin.length) {
    spanlar.add(TextSpan(text: metin.substring(son), style: taban));
  }
  return spanlar;
}

class MarkdownGorunum extends StatefulWidget {
  final String metin;
  final double yaziBoyutu;
  final void Function(String url)? baglanti;

  /// Kod blokları için ek düğmeler (ör. AI balonundaki "Uygula").
  final Widget Function(BuildContext context, String kod, String dil)?
      kodEylemleri;

  const MarkdownGorunum(this.metin,
      {super.key, this.yaziBoyutu = 13, this.baglanti, this.kodEylemleri});

  @override
  State<MarkdownGorunum> createState() => _MarkdownGorunumState();
}

class _MarkdownGorunumState extends State<MarkdownGorunum> {
  String get metin => widget.metin;
  double get yaziBoyutu => widget.yaziBoyutu;
  void Function(String url)? get baglanti => widget.baglanti;
  Widget Function(BuildContext context, String kod, String dil)? get kodEylemleri =>
      widget.kodEylemleri;

  // Bağlantı tanıyıcıları adrese göre saklanır ve atılır (eskiden her
  // çizimde yenisi kuruluyor, hiçbiri atılmıyordu; Kodi harf harf yazarken
  // saniyede onlarca tanıyıcı birikiyordu).
  final Map<String, TapGestureRecognizer> _taniyicilar = {};
  final Set<String> _kullanilan = {};
  bool _temizlikBekliyor = false;

  GestureRecognizer _taniyici(String url) {
    _kullanilan.add(url);
    return _taniyicilar.putIfAbsent(
        url, () => TapGestureRecognizer()..onTap = () => widget.baglanti?.call(url));
  }

  /// Bu çizimde kullanılmayan tanıyıcılar kare bitince atılır.
  void _temizligiZamanla() {
    if (_temizlikBekliyor) return;
    _temizlikBekliyor = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _temizlikBekliyor = false;
      if (!mounted) return;
      _taniyicilar.removeWhere((url, t) {
        if (_kullanilan.contains(url)) return false;
        t.dispose();
        return true;
      });
    });
  }

  @override
  void dispose() {
    for (final t in _taniyicilar.values) {
      t.dispose();
    }
    _taniyicilar.clear();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _kullanilan.clear();
    final bloklar = markdownAyristirOnbellekli(metin);
    final sonuc = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [for (final b in bloklar) _blok(context, b)],
    );
    if (_taniyicilar.length > _kullanilan.length) _temizligiZamanla();
    return sonuc;
  }

  TextStyle _taban(BuildContext context) => TextStyle(
      fontSize: yaziBoyutu,
      height: 1.4,
      color: Theme.of(context).colorScheme.onSurface);

  Widget _zengin(BuildContext context, String s, TextStyle stil) {
    final cs = Theme.of(context).colorScheme;
    return Text.rich(TextSpan(
        children: markdownSatirIci(s, stil,
            kodZemin: cs.surfaceContainerHighest,
            baglantiRengi: cs.primary,
            baglanti: baglanti,
            taniyici: baglanti == null ? null : _taniyici)));
  }

  Widget _blok(BuildContext context, MdBlok b) {
    final cs = Theme.of(context).colorScheme;
    final taban = _taban(context);
    switch (b.tur) {
      case MdTur.paragraf:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          // Tek satır sonları Markdown'da boşluktur; AI yanıtlarında ise
          // genellikle bilinçlidir, korunur.
          child: _zengin(context, b.metin, taban),
        );
      case MdTur.baslik:
        final olcek = const [1.45, 1.3, 1.15, 1.05, 1.0, 0.95][b.duzey - 1];
        return Padding(
          padding: EdgeInsets.only(top: b.duzey <= 2 ? 10 : 6, bottom: 4),
          child: _zengin(
              context,
              b.metin,
              taban.copyWith(
                  fontSize: yaziBoyutu * olcek,
                  fontWeight: FontWeight.w700,
                  height: 1.25)),
        );
      case MdTur.cizgi:
        return Divider(height: 14, color: cs.outlineVariant);
      case MdTur.alinti:
        return Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.only(left: 10),
          decoration: BoxDecoration(
              border: Border(left: BorderSide(color: cs.primary, width: 3))),
          child: DefaultTextStyle.merge(
            style: TextStyle(color: cs.onSurface.withValues(alpha: 0.75)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [for (final c in b.cocuklar) _blok(context, c)],
            ),
          ),
        );
      case MdTur.liste:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final o in b.liste)
                Padding(
                  padding: EdgeInsets.only(left: 6.0 + o.duzey * 16, top: 1, bottom: 1),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(
                        width: o.numara != null ? 24 : 16,
                        child: o.gorev != null
                            ? Icon(
                                o.gorev!
                                    ? Icons.check_box
                                    : Icons.check_box_outline_blank,
                                size: yaziBoyutu + 1,
                                color: cs.primary)
                            : Text(
                                o.numara != null
                                    ? '${o.numara}.'
                                    : (o.duzey.isEven ? '•' : '◦'),
                                style: taban.copyWith(
                                    color: cs.primary,
                                    fontWeight: FontWeight.w700)),
                      ),
                      Expanded(child: _zengin(context, o.metin, taban)),
                    ],
                  ),
                ),
            ],
          ),
        );
      case MdTur.tablo:
        final sutun = b.tablo.fold<int>(0, (m, r) => r.length > m ? r.length : m);
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Table(
              defaultColumnWidth: const IntrinsicColumnWidth(),
              border: TableBorder.all(color: cs.outlineVariant, width: 1),
              children: [
                for (var r = 0; r < b.tablo.length; r++)
                  TableRow(
                    decoration: r == 0
                        ? BoxDecoration(color: cs.surfaceContainerHigh)
                        : null,
                    children: [
                      for (var c = 0; c < sutun; c++)
                        Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          child: _zengin(
                              context,
                              c < b.tablo[r].length ? b.tablo[r][c] : '',
                              r == 0
                                  ? taban.copyWith(fontWeight: FontWeight.w700)
                                  : taban),
                        ),
                    ],
                  ),
              ],
            ),
          ),
        );
      case MdTur.kod:
        return Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: cs.surfaceContainer,
            border: Border.all(color: cs.outlineVariant),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                Text(b.dil.isEmpty ? 'kod' : b.dil,
                    style: TextStyle(
                        fontSize: 10, color: cs.onSurface.withValues(alpha: 0.6))),
                const Spacer(),
                if (kodEylemleri != null) kodEylemleri!(context, b.metin, b.dil),
                IconButton(
                  tooltip: 'Kopyala',
                  visualDensity: VisualDensity.compact,
                  iconSize: 13,
                  icon: const Icon(Icons.copy),
                  onPressed: () => Clipboard.setData(ClipboardData(text: b.metin)),
                ),
              ]),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Text(b.metin,
                    style: TextStyle(
                        fontFamily: _kMono,
                        fontFamilyFallback: _kMonoYedek,
                        fontSize: yaziBoyutu - 1,
                        height: 1.35,
                        color: cs.onSurface)),
              ),
            ],
          ),
        );
    }
  }
}
