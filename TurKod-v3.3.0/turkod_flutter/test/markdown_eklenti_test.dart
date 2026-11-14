import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:turkod_ide/main.dart' as app;
import 'package:turkod_ide/markdown_gorunum.dart';

class _AyarlarSahte extends app.SettingsProvider {
  _AyarlarSahte(super.backend);
  final Set<String> kurulu = {};

  @override
  bool get loaded => true;

  @override
  Set<String> get eklentiler => kurulu;

  @override
  Future<void> eklentiAyarla(String id, bool yuklu) async {
    yuklu ? kurulu.add(id) : kurulu.remove(id);
    notifyListeners();
  }
}

String _duzMetin(Widget w) {
  final parcalar = <String>[];
  void gez(InlineSpan s) {
    if (s is TextSpan) {
      if (s.text != null) parcalar.add(s.text!);
      for (final c in s.children ?? const <InlineSpan>[]) {
        gez(c);
      }
    }
  }

  if (w is RichText) gez(w.text);
  return parcalar.join();
}

void main() {
  group('markdownAyristir', () {
    test('başlık, liste, alıntı, çizgi, tablo ve kod bloğu', () {
      final b = markdownAyristir('''
## Başlık

Paragraf **kalın** metin.

- bir
  - iç içe
- [x] bitti
1. birinci
2. ikinci

> alıntı

---

| Ad | Puan |
|----|-----:|
| Ali | 90 |

```python
print(1)
```''');
      final turler = b.map((e) => e.tur).toList();
      expect(turler, [
        MdTur.baslik,
        MdTur.paragraf,
        MdTur.liste,
        MdTur.alinti,
        MdTur.cizgi,
        MdTur.tablo,
        MdTur.kod,
      ]);
      expect(b[0].duzey, 2);
      final liste = b[2].liste;
      expect(liste.map((o) => o.metin).toList(),
          ['bir', 'iç içe', 'bitti', 'birinci', 'ikinci']);
      expect(liste[1].duzey, 1);
      expect(liste[2].gorev, isTrue);
      expect(liste[3].numara, 1);
      expect(b[5].tablo, [
        ['Ad', 'Puan'],
        ['Ali', '90'],
      ]);
      expect(b[6].dil, 'python');
      expect(b[6].metin, 'print(1)');
    });

    test('kapanmamış kod bloğu metni yutmaz, sonuna kadar kod sayılır', () {
      final b = markdownAyristir('Metin\n```\nx = 1');
      expect(b.last.tur, MdTur.kod);
      expect(b.last.metin, 'x = 1');
    });
  });

  test('satır içi biçimler', () {
    final spanlar = markdownSatirIci(
        'a **kalın** _eğik_ `kod` ~~sil~~ [site](https://x.y) snake_case_ad',
        const TextStyle(),
        kodZemin: Colors.black,
        baglantiRengi: Colors.blue);
    TextSpan bul(String metin) => spanlar
        .whereType<TextSpan>()
        .firstWhere((s) => s.text == metin);
    expect(bul('kalın').style!.fontWeight, FontWeight.w700);
    expect(bul('eğik').style!.fontStyle, FontStyle.italic);
    expect(bul('kod').style!.fontFamily, 'Consolas');
    expect(bul('sil').style!.decoration, TextDecoration.lineThrough);
    expect(bul('site').style!.decoration, TextDecoration.underline);
    // Alt çizgili tanımlayıcılar italik sanılmaz.
    expect(spanlar.whereType<TextSpan>().last.text, endsWith('snake_case_ad'));
  });

  test('biçim işaretleri kalkar, aradaki boşluklar korunur', () {
    final spanlar = markdownSatirIci('**Kalın** ve _eğik_ ile `kod` dene',
        const TextStyle(),
        kodZemin: Colors.black, baglantiRengi: Colors.blue);
    final metin = spanlar.whereType<TextSpan>().map((s) => s.text).join();
    expect(metin, 'Kalın ve eğik ile kod dene');
  });

  testWidgets('MarkdownGorunum işaretleri göstermez', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: MarkdownGorunum('# Merhaba\n\n**kalın** ve *eğik*')),
    ));
    final metinler = tester
        .widgetList<RichText>(find.byType(RichText))
        .map(_duzMetin)
        .join('|');
    expect(metinler, contains('Merhaba'));
    expect(metinler, contains('kalın ve eğik'));
    expect(metinler, isNot(contains('**')));
    expect(metinler, isNot(contains('#')));
  });

  testWidgets('Eklentiler paneli: yükle ve kaldır', (tester) async {
    final backend = app.BackendService();
    final ayarlar = _AyarlarSahte(backend);
    addTearDown(() {
      ayarlar.dispose();
      backend.dispose();
    });
    final ui = app.UiProvider();
    addTearDown(ui.dispose);
    await tester.binding.setSurfaceSize(const Size(400, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(MultiProvider(
      providers: [
        Provider<app.BackendService>.value(value: backend),
        ChangeNotifierProvider<app.SettingsProvider>.value(value: ayarlar),
        ChangeNotifierProvider<app.UiProvider>.value(value: ui),
      ],
      child: MaterialApp(
        theme: app.AppThemeRegistry.build('Modern Koyu'),
        home: const Scaffold(body: app.EklentilerPaneli()),
      ),
    ));

    expect(app.kEklentiler.length, greaterThanOrEqualTo(5));
    expect(find.text('Etkinleştir'), findsNWidgets(app.kEklentiler.length));

    // Programın zaten var olan özellikleri eklenti olarak sunulmaz.
    expect(find.text('EKLENTİ ÖZELLİKLERİ'), findsOneWidget);
    expect(find.textContaining('Dönüştürücü'), findsNothing);
    expect(find.textContaining('Biçimlendir'), findsNothing);
    // Yerel AI her zaman görünür; yüklenip kaldırılan bir eklenti değildir.
    expect(find.text('Model Yöneticisi'), findsOneWidget);

    Finder kartDugmesi(String ad, String dugme) => find.descendant(
        of: find.ancestor(of: find.text(ad), matching: find.byType(Container)).first,
        matching: find.text(dugme));

    await tester.tap(kartDugmesi('Karalama Defteri', 'Etkinleştir'));
    await tester.pumpAndSettle();
    expect(ayarlar.kurulu, {'karalama_defteri'});
    expect(find.textContaining('ETKİN EKLENTİLER (1)'), findsOneWidget);

    await tester.tap(kartDugmesi('Karalama Defteri', 'Devre dışı bırak'));
    await tester.pumpAndSettle();
    expect(ayarlar.kurulu, isEmpty);
    // Bildirim kutusunun kapanma zamanlayıcısı dolsun.
    await tester.pump(const Duration(seconds: 7));
  });
}
