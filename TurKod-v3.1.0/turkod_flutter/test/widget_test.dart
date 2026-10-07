import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/acilis_ekrani.dart';

// Not: TurkodApp burada pompalanmaz; gerçek backend sürecini başlatır.
void main() {
  testWidgets('açılış ekranı başlatılıyor durumunu gösterir', (tester) async {
    await tester.pumpWidget(
      AcilisEkrani(onYenidenDene: () {}, onYineDeAc: () {}),
    );
    expect(find.text('Program başlatılıyor...'), findsOneWidget);
    expect(find.text('Yeniden dene'), findsNothing);
  });

  testWidgets('açılış hatası gösterilir ve düğmeler çalışır', (tester) async {
    var yenidenDene = 0, yineDeAc = 0;
    await tester.pumpWidget(AcilisEkrani(
      hata: 'Python backend başlatılamadı: süreç hemen kapandı.',
      onYenidenDene: () => yenidenDene++,
      onYineDeAc: () => yineDeAc++,
    ));
    expect(find.textContaining('süreç hemen kapandı'), findsOneWidget);

    await tester.tap(find.text('Yeniden dene'));
    await tester.tap(find.text('Yine de aç'));
    expect(yenidenDene, 1);
    expect(yineDeAc, 1);
  });
}
