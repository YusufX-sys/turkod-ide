import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

// Her temanın kod renk paleti ThemeData içinden bulunabilmeli. Eskiden
// palette "type" adlı bir alan, ThemeExtension.type'ı ezdiği için palet
// yanlış anahtarla kaydediliyor ve tüm temalar aynı yedek renklerle
// açılıyordu (açık temada değişken adları beyaz zeminde görünmüyordu).
void main() {
  test('her tema kendi sözdizimi paletini taşır', () {
    for (final d in AppThemeRegistry.definitions) {
      final t = AppThemeRegistry.build(d.name);
      final p = t.extension<AppSyntaxPalette>();
      expect(p, isNotNull, reason: d.name);
      expect(p!.string, d.syntax.string, reason: d.name);
      expect(p.variable, d.syntax.variable, reason: d.name);
    }
  });

  test('açık temada değişken rengi zeminle karışmaz', () {
    final t = AppThemeRegistry.build('Açık');
    final p = t.extension<AppSyntaxPalette>()!;
    final zemin = t.colorScheme.surface.computeLuminance();
    final yazi = p.variable.computeLuminance();
    final oran = (zemin + 0.05) / (yazi + 0.05);
    expect(oran, greaterThan(7));
  });
}
