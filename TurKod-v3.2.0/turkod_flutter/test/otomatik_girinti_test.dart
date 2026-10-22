import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart';

void main() {
  String? sonuc(String t, int pos) {
    final v = blokAcanSatirdaYeniSatir(t, pos, 4);
    if (v == null) return null;
    expect(v.selection.isCollapsed, isTrue);
    return '${v.text.substring(0, v.selection.baseOffset)}|'
        '${v.text.substring(v.selection.baseOffset)}';
  }

  test('blok açan satır sonunda Enter bir seviye girer', () {
    const t = 'için i içinde aralık(3):';
    expect(sonuc(t, t.length), '$t\n    |');
  });

  test('iç içe bloklarda mevcut girinti korunur', () {
    const t = 'eğer a:\n    döngü Doğru:';
    expect(sonuc(t, t.length), '$t\n        |');
  });

  test('sondaki yorum yok sayılır', () {
    const t = 'fonksiyon f(x):  # açıklama';
    expect(sonuc(t, t.length), '$t\n    |');
  });

  test('imlecin sağındaki metin yeni satıra taşınır', () {
    const t = 'eğer x:   yazdır(x)';
    expect(sonuc(t, 7), 'eğer x:\n    |yazdır(x)');
  });

  test('blok açmayan satırda varsayılan davranış', () {
    expect(blokAcanSatirdaYeniSatir('yazdır("a:")', 12, 4), isNull);
    expect(blokAcanSatirdaYeniSatir('x = 1  # not:', 13, 4), isNull);
    expect(blokAcanSatirdaYeniSatir('', 0, 4), isNull);
    expect(blokAcanSatirdaYeniSatir('yazdır("#") # a:', 16, 4), isNull);
  });

  test('metin içindeki # yorum sayılmaz', () {
    const t = 'eğer s == "#":';
    expect(sonuc(t, t.length), '$t\n    |');
  });

  test('çok satırlı metnin ortasındaki satır', () {
    const t = 'a = 1\neğer a:\nyazdır(a)';
    expect(sonuc(t, 13), 'a = 1\neğer a:\n    |\nyazdır(a)');
  });
}
