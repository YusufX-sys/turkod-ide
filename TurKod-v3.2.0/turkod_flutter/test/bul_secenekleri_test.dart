import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

List<List<int>> bul(String metin, String sorgu) =>
    SyntaxHighlightingController.findAllMatches(metin, sorgu);

void main() {
  tearDown(() {
    FindOptions.caseSensitive = false;
    FindOptions.wholeWord = false;
    FindOptions.regex = false;
  });

  test('varsayılan: büyük/küçük harf duyarsız, Türkçe İ/i eşleşir', () {
    expect(bul('İçin için', 'için').length, 2);
  });

  test('büyük/küçük harf duyarlı', () {
    FindOptions.caseSensitive = true;
    expect(bul('Yaz yaz YAZ', 'yaz'), [
      [4, 7]
    ]);
  });

  test('tam kelime: kelime içindeki eşleşmeler atlanır', () {
    FindOptions.wholeWord = true;
    expect(bul('sayı sayılar _sayı sayı2 sayı.', 'sayı'), [
      [0, 4],
      [25, 29],
    ]);
  });

  test('regex ve grup değiştirme', () {
    FindOptions.regex = true;
    const metin = 'x = 12; y = 7';
    final m = bul(metin, r'(\w) = (\d+)');
    expect(m, [
      [0, 6],
      [8, 13],
    ]);
    expect(FindOptions.replacementFor(metin, 0, r'(\w) = (\d+)', r'$2 -> $1'),
        '12 -> x');
  });

  test('geçersiz regex eşleşme vermez, boş eşleşmeler atlanır', () {
    FindOptions.regex = true;
    expect(bul('abc', '(a'), isEmpty);
    expect(bul('abc', 'z*'), isEmpty);
  });
}
