// Tam Türkçe sözlüğü ve çıktı çevirisini gerçek uygulamada (gerçek backend ile)
// dener: programlar editöre yazılır, Çalıştır eylemiyle (TerminalProvider.run)
// çalıştırılır ve terminal çıktısı denetlenir.
//
// ÇALIŞTIRMA (ayarlar boş bir klasöre yönlendirilmeden test durur):
//   set TURKOD_TEST_PROFIL=<boş bir klasör>\turkod_ceviri_...
//   flutter test integration_test/turkce_ceviri_test.dart -d windows
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:turkod_ide/main.dart' as app;

final _sonuc = <String>[];
void _kontrol(String madde, bool gecti, [String ayrinti = '']) {
  final satir = 'SONUÇ|${gecti ? "GEÇTİ" : "KALDI"}|$madde|$ayrinti';
  _sonuc.add(satir);
  // ignore: avoid_print
  print(satir);
}

Future<void> _bekle(WidgetTester t, Duration d) async {
  final son = DateTime.now().add(d);
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 50));
    await Future<void>.delayed(const Duration(milliseconds: 50));
  }
}

Future<bool> _kosulBekle(WidgetTester t, bool Function() kosul, {int sn = 30}) async {
  final son = DateTime.now().add(Duration(seconds: sn));
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 100));
    await Future<void>.delayed(const Duration(milliseconds: 100));
    if (kosul()) return true;
  }
  return false;
}

/// (ad, TürKod kodu, çıktıda bulunması gerekenler, bulunmaması gerekenler)
const _programlar = <(String, String, List<String>, List<String>)>[
  (
    'Yeni modül adları (işletim_sistemi, yol)',
    'içe_aktar işletim_sistemi\n'
        'yazdır(işletim_sistemi.süreç_kimliği_al() > 0, işletim_sistemi.yol.mutlak_mı("C:/a"))\n',
    ['Doğru Doğru'],
    [],
  ),
  (
    'eşleştir / durumunda (match/case)',
    'fonksiyon tür_bul(d):\n'
        '    eşleştir d:\n'
        '        durumunda 1:\n'
        '            döndür "bir"\n'
        '        durumunda _:\n'
        '            döndür "başka"\n'
        'yazdır(tür_bul(1), tür_bul(5))\n',
    ['bir başka'],
    [],
  ),
  (
    'Takma adlı modül (olarak m)',
    'içe_aktar matematik olarak m\nyazdır(m.küpkök(27), m.ondalıklı_kalan(7, 3))\n',
    ['3.0 1.0'],
    [],
  ),
  (
    'den ... içe_aktar',
    'den matematik içe_aktar küpkök\nyazdır(küpkök(8))\n',
    ['2.0'],
    [],
  ),
  (
    'Yeni ad ve takma ad olarak eski ad (jng / json)',
    'içe_aktar json\nyazdır(json.jng_yükle_metin("[1, 2]"), json.json_yükle_metin("[3]"))\n',
    ['[1, 2] [3]'],
    [],
  ),
  (
    'Kısaltmanın Türkçesi (SQLITE_TAMAM)',
    'içe_aktar veritabanı_sqlite\nyazdır(veritabanı_sqlite.SQLITE_TAMAM)\n',
    ['0'],
    [],
  ),
  (
    'zaman modülü',
    'içe_aktar zaman\nyazdır(zaman.performans_sayacı() > 0)\n',
    ['Doğru'],
    ['True'],
  ),
  (
    'Sayı metotları (bit_uzunluğu, baytlara_dönüştür)',
    'yazdır((10).bit_uzunluğu(), (255).baytlara_dönüştür(2, "big"))\n',
    ["4 b'\\x00\\xff'"],
    [],
  ),
  (
    'Yakalanan hata nesnesi Türkçe yazdırılır',
    'dene:\n    [1].kaldır(5)\nhata_yakala DeğerHatası olarak h:\n    yazdır("yakalandı:", h)\n',
    ['yakalandı: silinmek istenen değer listede yok!'],
    ['x not in list'],
  ),
  (
    'Kütüphane hatası Türkçe ad ve mesajla',
    'içe_aktar json\njson.jng_yükle_metin("{bozuk")\n',
    ['[HATA]: JNG Kod Çözme Hatası (json)', 'çift tırnaklı anahtar adı bekleniyordu'],
    ['JSONDecodeError', 'Expecting property name'],
  ),
  (
    'Uyarı satırı Türkçe ve TürKod satırıyla',
    'içe_aktar uyarılar\nuyarılar.uyarı_ver("eski kullanım", KullanımdanKalkmaUyarısı)\n',
    ['Satır 2: Eskimiş Kullanım Uyarısı: eski kullanım', 'uyarılar.uyarı_ver('],
    ['DeprecationWarning', 'warnings.warn'],
  ),
];

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('TürKod tam Türkçe sözlük — gerçek uygulamada deneme', (t) async {
    final ev = Platform.environment['TURKOD_TEST_PROFIL'] ?? '';
    if (!p.basename(ev).startsWith('turkod_ceviri_')) {
      fail('Güvenlik: TURKOD_TEST_PROFIL bir sandbox klasörü değil ($ev).');
    }
    File(p.join(ev, '.turkod_ayarlar.json')).writeAsStringSync(
        jsonEncode({'arayuz_turu_goruldu': true, 'son_proje_dizini': ev}));

    app.main(const []);
    expect(
        await _kosulBekle(t, () => find.text('Dosya').evaluate().isNotEmpty, sn: 90),
        isTrue,
        reason: 'Ana pencere açılmadı');
    final ctx = t.element(find.text('Dosya').first);
    final ed = ctx.read<app.EditorProvider>();
    final ui = ctx.read<app.UiProvider>();
    final terminal = ctx.read<app.TerminalProvider>();
    final backend = ctx.read<app.BackendService>();
    expect(await _kosulBekle(t, () => backend.isConnected, sn: 60), isTrue,
        reason: 'Arka uç bağlanmadı');
    await _bekle(t, const Duration(seconds: 2));

    for (final (ad, kod, olmali, olmamali) in _programlar) {
      await ed.createUntitled(content: kod);
      await _bekle(t, const Duration(milliseconds: 500));
      ui.revealTerminal();
      terminal.run(ed.activeContent.value);
      await _kosulBekle(t, () => terminal.isRunning, sn: 5);
      final bitti = await _kosulBekle(t, () => !terminal.isRunning, sn: 60);
      await _bekle(t, const Duration(milliseconds: 800));
      final cikti = terminal.output;
      final eksik = [for (final s in olmali) if (!cikti.contains(s)) s];
      final fazla = [for (final s in olmamali) if (cikti.contains(s)) s];
      _kontrol(ad, bitti && eksik.isEmpty && fazla.isEmpty,
          '${eksik.isEmpty ? "" : "eksik=$eksik "}${fazla.isEmpty ? "" : "istenmeyen=$fazla "}'
          'çıktı=${jsonEncode(cikti.trim())}');
    }

    File(p.join(ev, 'turkce_ceviri_sonuc.txt')).writeAsStringSync(_sonuc.join('\n'));
    expect(_sonuc.where((s) => s.contains('|KALDI|')), isEmpty,
        reason: _sonuc.join('\n'));
  });
}
