import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

// Katlanmış görünüm: 0 "eğer x:", 1 yer tutucu (katlama 7), 2 "son".
const String yt = '    3 satır kadar kod katlanıldı.';
const String gorunum = 'eğer x:\n$yt\nson';
String? yerTutucu(int id) => id == 7 ? yt : (id == 8 ? yt : null);

({Map<int, int>? harita, List<int> dokunulan}) kaydir(String yeni,
        {Map<int, int> harita = const {1: 7}, String eski = gorunum}) =>
    katlamaHaritasiniKaydir(harita, eski, yeni, yerTutucu);

void main() {
  test('üstte yazmak haritayı değiştirmez', () {
    expect(kaydir('eğer xy:\n$yt\nson').harita, {1: 7});
  });

  test('üste satır eklemek yer tutucuyu aşağı kaydırır', () {
    expect(kaydir('yeni\neğer x:\n$yt\nson').harita, {2: 7});
  });

  test('başlık satırının sonunda Enter reddedilmez', () {
    expect(kaydir('eğer x:\n    \n$yt\nson').harita, {2: 7});
    expect(kaydir('eğer x:\n\n$yt\nson').harita, {2: 7});
  });

  test('alttaki satırda yazmak haritayı korur', () {
    expect(kaydir('eğer x:\n$yt\nsonx').harita, {1: 7});
  });

  test('yer tutucuyu düzenlemek reddedilir ve katlama bildirilir', () {
    final r = kaydir('eğer x:\n${yt}a\nson');
    expect(r.harita, isNull);
    expect(r.dokunulan, [7]);
  });

  test('sonraki satırın başında Backspace (birleştirme) reddedilir', () {
    final r = kaydir('eğer x:\n${yt}son');
    expect(r.harita, isNull);
    expect(r.dokunulan, [7]);
  });

  test('yer tutucuyu kapsayan seçimi silmek reddedilir', () {
    final r = kaydir('eğer son');
    expect(r.harita, isNull);
  });

  test('çok satırlı yapıştırma üstte kaydırır', () {
    expect(kaydir('a\nb\nc\neğer x:\n$yt\nson').harita, {4: 7});
  });

  test('aynı metinli iki yer tutucu ayrı ayrı izlenir', () {
    const eski = 'eğer a:\n$yt\neğer b:\n$yt\nson';
    final r = katlamaHaritasiniKaydir(
        {1: 7, 3: 8}, eski, 'x\n$eski', yerTutucu);
    expect(r.harita, {2: 7, 4: 8});
    final r2 = katlamaHaritasiniKaydir(
        {1: 7, 3: 8}, eski, 'eğer a:\n$yt\neğer b:\n$yt\nson\nek', yerTutucu);
    expect(r2.harita, {1: 7, 3: 8});
  });

  test('aradaki satırı silmek alttaki yer tutucuyu yukarı kaydırır', () {
    const eski = 'eğer a:\n$yt\nara\neğer b:\n$yt';
    final r = katlamaHaritasiniKaydir(
        {1: 7, 4: 8}, eski, 'eğer a:\n$yt\neğer b:\n$yt', yerTutucu);
    expect(r.harita, {1: 7, 3: 8});
  });
}
