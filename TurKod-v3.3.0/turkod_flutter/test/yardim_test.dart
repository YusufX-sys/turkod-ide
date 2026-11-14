import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:turkod_ide/yardim.dart';

void main() {
  test('belge, kurulum klasöründe ya da üst klasörlerde bulunur', () {
    final kok = Directory.systemTemp.createTempSync('turkod_belge_');
    addTearDown(() => kok.deleteSync(recursive: true));
    final belgeler = Directory(p.join(kok.path, 'belgeler'))..createSync();
    File(p.join(belgeler.path, kKitapDosyasi)).writeAsStringSync('%PDF');

    // Kurulum: <kurulum>\turkod_flutter.exe yanında belgeler\
    expect(belgeYolu(kKitapDosyasi, baslangic: kok.path),
        p.join(belgeler.path, kKitapDosyasi));

    // Geliştirme: build\windows\x64\runner\Release içinden yukarı doğru
    final derin = Directory(p.join(kok.path, 'build', 'windows', 'x64', 'runner', 'Release'))
      ..createSync(recursive: true);
    expect(belgeYolu(kKitapDosyasi, baslangic: derin.path),
        p.join(belgeler.path, kKitapDosyasi));

    expect(belgeYolu('olmayan.pdf', baslangic: derin.path), isNull);
  });

  test('projedeki belgeler gerçekten var', () {
    final proje = p.dirname(Directory.current.path);
    for (final ad in [kKitapDosyasi, 'LISANS.txt', 'SORUMLULUK_REDDI.txt',
        'UCUNCU_TARAF_LISANSLARI.txt']) {
      expect(File(p.join(proje, 'belgeler', ad)).existsSync(), isTrue, reason: ad);
    }
  });
}
