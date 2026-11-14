import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart' show SingleActivator;
import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

TextSelection imlec(int i) => TextSelection.collapsed(offset: i);

void main() {
  group('cokluDuzenle', () {
    test('yazma tüm imleçlere yansır', () {
      // "a|\nb|\nc|" -> her satır sonuna "x"
      const eski = 'a\nb\nc';
      final r = cokluDuzenle(eski, imlec(1), 'ax\nb\nc', imlec(2),
          [imlec(3), imlec(5)]);
      expect(r, isNotNull);
      expect(r!.metin, 'ax\nbx\ncx');
      expect(r.birincil, imlec(2));
      expect(r.ekler, [imlec(5), imlec(8)]);
    });

    test('geri silme tüm imleçlerde bir karakter siler', () {
      const eski = 'ab\ncd\nef';
      final r = cokluDuzenle(eski, imlec(2), 'a\ncd\nef', imlec(1),
          [imlec(5), imlec(8)]);
      expect(r!.metin, 'a\nc\ne');
      expect(r.ekler, [imlec(3), imlec(5)]);
    });

    test('çift harften sonra geri silme ek imleçleri düşürmez', () {
      // "hel|lo\nhel|lo": önek imleci aşınca model kurulamıyordu.
      const eski = 'hello\nhello';
      final r =
          cokluDuzenle(eski, imlec(3), 'helo\nhello', imlec(2), [imlec(9)]);
      expect(r, isNotNull);
      expect(r!.metin, 'helo\nhelo');
      expect(r.ekler, [imlec(7)]);
    });

    test('girinti boşluklarında geri silme', () {
      const eski = '    a\n    b';
      final r =
          cokluDuzenle(eski, imlec(4), '   a\n    b', imlec(3), [imlec(10)]);
      expect(r!.metin, '   a\n   b');
      expect(r.ekler, [imlec(8)]);
    });

    test('otomatik parantez imleci arada bırakır', () {
      const eski = 'f\ng';
      final r =
          cokluDuzenle(eski, imlec(1), 'f()\ng', imlec(2), [imlec(3)]);
      expect(r!.metin, 'f()\ng()');
      expect(r.ekler, [imlec(6)]);
    });

    test('seçimler yazılan metinle değiştirilir', () {
      const eski = 'ali ve ali';
      final r = cokluDuzenle(
          eski,
          const TextSelection(baseOffset: 0, extentOffset: 3),
          'veli ve ali',
          imlec(4),
          [const TextSelection(baseOffset: 7, extentOffset: 10)]);
      expect(r!.metin, 'veli ve veli');
      expect(r.ekler, [imlec(12)]);
    });

    test('Enter ve girinti yansır', () {
      const eski = 'eğer a:\neğer b:';
      final r = cokluDuzenle(
          eski, imlec(7), 'eğer a:\n    \neğer b:', imlec(12), [imlec(15)]);
      expect(r!.metin, 'eğer a:\n    \neğer b:\n    ');
    });

    test('örtüşen imleçlerde ya da uzak değişiklikte null', () {
      expect(cokluDuzenle('abc', imlec(1), 'axbc', imlec(2), [imlec(1)]),
          isNull);
      // Değişiklik imlecin çok uzağında (ör. geri al): model kurulamaz.
      final uzun = 'x' * 200;
      expect(
          cokluDuzenle(uzun, imlec(199), 'y${uzun.substring(1)}', imlec(199),
              [imlec(10)]),
          isNull);
    });
  });

  group('Sorun.araliklar', () {
    test('ad verilmişse satırdaki tüm tam kelime geçişleri', () {
      const s = Sorun(satir: 1, ad: 'sayı', hata: false, mesaj: '');
      expect(s.araliklar('yazdır(sayı, sayılar, sayı)'), [
        [7, 11],
        [22, 26]
      ]);
    });

    test('sütundaki kelime ya da satırın kalanı', () {
      const s = Sorun(satir: 1, sutun: 8, hata: true, mesaj: '');
      expect(s.araliklar('yazdır(tanimsiz)'), [
        [7, 15]
      ]);
      const s2 = Sorun(satir: 1, sutun: 10, hata: true, mesaj: '');
      expect(s2.araliklar('eğer x > '), [
        [8, 9]
      ]);
    });
  });

  group('OzelKisayollar', () {
    test('metin ve çözümleme birbirinin tersi', () {
      for (final a in const [
        SingleActivator(LogicalKeyboardKey.keyK, control: true, shift: true),
        SingleActivator(LogicalKeyboardKey.f5),
        SingleActivator(LogicalKeyboardKey.arrowDown, control: true, alt: true),
        SingleActivator(LogicalKeyboardKey.slash, control: true),
      ]) {
        final m = OzelKisayollar.metin(a);
        final c = OzelKisayollar.coz(m);
        expect(c?.trigger, a.trigger, reason: m);
        expect((c?.control, c?.shift, c?.alt), (a.control, a.shift, a.alt));
      }
      expect(OzelKisayollar.coz(''), isNull);
    });

    test('ayarlanan kısayol eylemin tuşunu değiştirir', () {
      OzelKisayollar.ayarla({'file.save': 'Ctrl+Alt+S', 'run.run': ''});
      addTearDown(() => OzelKisayollar.ayarla(const {}));
      final eylemler = {for (final a in buildAppActions()) a.id: a};
      expect(eylemler['file.save']!.shortcut, 'Ctrl+Alt+S');
      expect(eylemler['file.save']!.activator?.alt, isTrue);
      expect(eylemler['run.run']!.activator, isNull);
    });
  });

  test('isabet sayısı koşul kaydında saklanır', () {
    final k = BreakpointProvider.kosulBirlestir(5, 'i > 2');
    expect(k, '#5#i > 2');
    expect(BreakpointProvider.kosulAyristir(k), (5, 'i > 2'));
    expect(BreakpointProvider.kosulAyristir('i > 2'), (null, 'i > 2'));
    expect(BreakpointProvider.kosulBirlestir(1, 'x'), 'x');
  });
}
