import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

void main() {
  group('parantezEsi', () {
    test('basit eşleşme iki yönde', () {
      const t = 'yazdır(uzunluk(x))';
      expect(parantezEsi(t, 6), 17);
      expect(parantezEsi(t, 17), 6);
      expect(parantezEsi(t, 14), 16);
    });

    test('farklı parantez türleri', () {
      const t = 'd = {"a": [1, (2)]}';
      expect(parantezEsi(t, 4), t.length - 1);
      expect(parantezEsi(t, 10), 17);
    });

    test('metin ve yorum içindekiler sayılmaz', () {
      const t = 'yazdır(")" + "(")  # )';
      expect(parantezEsi(t, 6), 16);
      expect(parantezEsi(t, 8), isNull);
    });

    test('üç tırnaklı metin atlanır', () {
      const t = 'x = ("""\n)\n""")';
      expect(parantezEsi(t, 4), t.length - 1);
    });

    test('kapanmamış ya da parantez olmayan konum', () {
      expect(parantezEsi('yazdır(1', 6), isNull);
      expect(parantezEsi('abc', 1), isNull);
      expect(parantezEsi('a)', 1), isNull);
    });
  });

  test('applyCharHighlight yalnızca seçilen sütunları boyar', () {
    const renk = Color(0xFF00FF00);
    final spans = SyntaxHighlightingController.applyCharHighlight(
      const [TextSpan(text: 'f(x)'), TextSpan(text: ' + 1')],
      {1, 3},
      renk,
    );
    final metin = spans.map((s) => (s as TextSpan).text).join();
    expect(metin, 'f(x) + 1');
    final boyali = spans
        .whereType<TextSpan>()
        .where((s) => s.style?.backgroundColor == renk)
        .map((s) => s.text)
        .toList();
    expect(boyali, ['(', ')']);
  });
}
