// Gerçek TürKod uygulamasını (gerçek backend ile) açıp eksik olduğu düşünülen
// özellikleri kullanıcı gibi dener ve bir rapor yazar.
//
// ÇALIŞTIRMA (ayarlar sandbox'a yönlendirilmeden çalıştırılırsa test durur):
//   set USERPROFILE=<boş bir klasör>\turkod_eksik_...
//   flutter test integration_test/eksikler_test.dart -d windows
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:re_editor/re_editor.dart' as re;
import 'package:turkod_ide/main.dart' as app;

final _rapor = <String>[];
void _yaz(String madde, bool eksik, String ayrinti) {
  final satir = 'RAPOR|${eksik ? "EKSİK" : "VAR"}|$madde|$ayrinti';
  _rapor.add(satir);
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

Future<bool> _bulanaKadar(WidgetTester t, Finder f, {int sn = 60}) async {
  final son = DateTime.now().add(Duration(seconds: sn));
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 100));
    await Future<void>.delayed(const Duration(milliseconds: 100));
    if (f.evaluate().isNotEmpty) return true;
  }
  return false;
}

List<String> _metinler(Finder kok) => [
      for (final e in find.descendant(of: kok, matching: find.byType(Text)).evaluate())
        ((e.widget as Text).data ?? (e.widget as Text).textSpan?.toPlainText() ?? '')
    ].where((s) => s.trim().isNotEmpty).toList();

Future<List<String>> _menuAc(WidgetTester t, String ad) async {
  await t.tap(find.text(ad).first);
  await _bekle(t, const Duration(milliseconds: 600));
  final ogeler = <String>[];
  for (final e in find.byWidgetPredicate((w) => w is PopupMenuItem).evaluate()) {
    ogeler.addAll(_metinler(find.byWidget(e.widget)));
  }
  await t.sendKeyEvent(LogicalKeyboardKey.escape);
  await _bekle(t, const Duration(milliseconds: 400));
  return ogeler;
}

Future<void> _kisayol(WidgetTester t, LogicalKeyboardKey tus,
    {bool shift = false}) async {
  await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  if (shift) await t.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
  await t.sendKeyEvent(tus);
  if (shift) await t.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
  await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
  await _bekle(t, const Duration(milliseconds: 700));
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('TürKod eksikler — uygulamada deneme', (t) async {
    final ev = Platform.environment['TURKOD_TEST_PROFIL'] ?? '';
    if (!p.basename(ev).startsWith('turkod_eksik_')) {
      fail('Güvenlik: TURKOD_TEST_PROFIL bir sandbox klasörü değil ($ev). '
          'Gerçek ayarlar/oturum bozulmasın diye test çalıştırılmadı.');
    }

    app.main(const []);
    expect(await _bulanaKadar(t, find.text('Dosya'), sn: 90), isTrue,
        reason: 'Ana pencere açılmadı');
    await _bekle(t, const Duration(seconds: 3));
    final ctx = t.element(find.text('Dosya').first);
    final ed = ctx.read<app.EditorProvider>();

    // --- 1) Menüler: Düzenle menüsünde Kes / Kopyala / Yapıştır / Tümünü Seç
    final menuler = <String, List<String>>{};
    for (final m in ['Dosya', 'Düzenle', 'Görünüm', 'Çalıştır', 'Araçlar',
        'Öğren', 'Yardım', 'Güncelleştirmeler']) {
      menuler[m] = await _menuAc(t, m);
      // ignore: avoid_print
      print('MENÜ|$m|${menuler[m]!.join(" ; ")}');
    }
    final duzenle = menuler['Düzenle']!.join(' ');
    for (final k in ['Kes', 'Kopyala', 'Yapıştır', 'Tümünü Seç']) {
      _yaz('Düzenle menüsünde "$k"', !RegExp('\\b$k\\b').hasMatch(duzenle),
          'Düzenle: ${menuler['Düzenle']!.where((s) => !s.startsWith('Ctrl') && !s.startsWith('Alt')).join(", ")}');
    }
    final tum = menuler.values.expand((e) => e).join(' | ');
    for (final (madde, desen) in [
      ('Menüde "Satıra Git"', r'Satır(a)? Git'),
      ('Menüde "Sekmeyi Kapat"', r'Sekmeyi Kapat|Sekme Kapat'),
      ('Menüde "Tümünü Kaydet"', r'Tümünü Kaydet'),
      ('Menüde "Çıkış"', r'Çıkış'),
      ('Menüde örnek programlar / şablonlar', r'Örnek|Şablon'),
      ('Menüde sözlük görüntüleme', r'Sözlük'),
      ('Menüde kodu biçimlendirme', r'Biçimlendir|Düzenle Kodu|Formatla'),
      ('Menüde paket (pip) yönetimi', r'Paket|pip'),
      ('Menüde klavye kısayolları listesi', r'Kısayol'),
    ]) {
      _yaz(madde, !RegExp(desen).hasMatch(tum), '');
    }

    // --- 2) Hakkında penceresinde sürüm numarası
    await t.tap(find.text('Yardım').first);
    await _bekle(t, const Duration(milliseconds: 600));
    await t.tap(find.text('Hakkında / İmza').last);
    await _bulanaKadar(t, find.byType(AlertDialog), sn: 15);
    await _bekle(t, const Duration(seconds: 3)); // imza doğrulaması
    final hakkinda = _metinler(find.byType(AlertDialog));
    _yaz('Hakkında penceresinde sürüm numarası',
        !hakkinda.any((s) => RegExp(r'\d+\.\d+\.\d+').hasMatch(s) && !s.contains('SHA')),
        hakkinda.take(4).join(' / '));
    await t.tap(find.text('Kapat').last);
    await _bekle(t, const Duration(milliseconds: 500));

    // --- 3) Editör kısayolları (gerçek tuş olay hattı üzerinden)
    await ed.createUntitled(content: 'birinci satır\nikinci satır');
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.byType(re.CodeEditor).first);
    await _bekle(t, const Duration(milliseconds: 500));

    await _kisayol(t, LogicalKeyboardKey.keyA);
    final sec = ed.uiController?.selection;
    final tumu = sec != null && !sec.isCollapsed &&
        sec.start == 0 && sec.end == (ed.uiController?.text.length ?? -1);
    _yaz('Editörde Ctrl+A (tümünü seç)', !tumu, 'seçim=$sec');

    await Clipboard.setData(const ClipboardData(text: ''));
    await _kisayol(t, LogicalKeyboardKey.keyC);
    final pano = (await Clipboard.getData('text/plain'))?.text ?? '';
    _yaz('Editörde Ctrl+C (kopyala)', !pano.contains('birinci'), 'pano=${jsonEncode(pano)}');

    final sekmeOnce = ed.tabs.length;
    await _kisayol(t, LogicalKeyboardKey.keyW);
    // Kaydedilmemiş sekmede "kaydet?" sorusu çıkabilir: o da kapatma girişimidir.
    final soru = find.byType(AlertDialog).evaluate().isNotEmpty;
    _yaz('Ctrl+W ile sekme kapatma', ed.tabs.length == sekmeOnce && !soru,
        'sekme: $sekmeOnce -> ${ed.tabs.length}${soru ? " (kaydet sorusu açıldı)" : ""}');
    if (soru) {
      await t.sendKeyEvent(LogicalKeyboardKey.escape);
      await _bekle(t, const Duration(milliseconds: 400));
    }

    await t.tap(find.byType(re.CodeEditor).first);
    await _kisayol(t, LogicalKeyboardKey.keyG);
    final satiraGit = find.byType(AlertDialog).evaluate().isNotEmpty ||
        find.textContaining('Satır').evaluate().length > 3;
    _yaz('Ctrl+G ile satıra git', !find.byType(AlertDialog).evaluate().isNotEmpty,
        satiraGit ? 'pencere açıldı' : 'hiçbir şey olmadı');
    if (find.byType(AlertDialog).evaluate().isNotEmpty) {
      await t.sendKeyEvent(LogicalKeyboardKey.escape);
      await _bekle(t, const Duration(milliseconds: 400));
    }

    // --- 4) Çökme / elektrik kesintisi: kaydedilmemiş değişiklikler nerede?
    final dosya = File(p.join(ev, 'odev.trpy'))..writeAsStringSync('yazdır("eski")\n');
    await ed.openFile(dosya.path);
    await _bekle(t, const Duration(seconds: 1));
    ed.updateContent('yazdır("KAYDEDILMEMIS_DOSYA_DEGISIKLIGI")\n'); // klavyeden yazma yolu
    await ed.createUntitled(content: '');
    await _bekle(t, const Duration(milliseconds: 500));
    ed.updateContent('yazdır("KAYDEDILMEMIS_YENI_SEKME")\n');
    // Kullanıcı yazdıktan sonra 20 sn bekliyor (otomatik kayıt açık olsa 30 sn'de kaydederdi)
    await _bekle(t, const Duration(seconds: 20));
    final ayarDosyasi = File(p.join(ev, '.turkod_ayarlar.json'));
    final ayar = ayarDosyasi.existsSync()
        ? jsonDecode(ayarDosyasi.readAsStringSync()) as Map
        : <String, dynamic>{};
    final oturum = jsonEncode(ayar['son_oturum'] ?? []);
    _yaz('Çökmede kaydedilmemiş DOSYA değişikliği kurtarılır',
        !oturum.contains('KAYDEDILMEMIS_DOSYA_DEGISIKLIGI') &&
            !dosya.readAsStringSync().contains('KAYDEDILMEMIS'),
        'diskteki dosya: ${jsonEncode(dosya.readAsStringSync().trim())}; '
        'otomatik_kaydetme=${ayar['otomatik_kaydetme'] ?? "(varsayılan: kapalı)"}');
    _yaz('Çökmede kaydedilmemiş YENİ SEKME içeriği kurtarılır',
        !oturum.contains('KAYDEDILMEMIS_YENI_SEKME'),
        'oturumdaki sekme sayısı: ${(ayar['son_oturum'] as List?)?.length ?? 0}');

    // --- 5) Ayarlar: varsayılana sıfırlama
    await t.tap(find.text('Görünüm').first);
    await _bekle(t, const Duration(milliseconds: 600));
    await t.tap(find.text('Ayarlar').last);
    await _bekle(t, const Duration(seconds: 2));
    final ayarMetin = _metinler(find.byType(Scaffold).first).join(' | ');
    _yaz('Ayarlarda "varsayılana sıfırla"',
        !RegExp('Sıfırla|Varsayılan').hasMatch(ayarMetin), '');

    // --- 6) Lisanslar penceresi (yeni)
    await t.tap(find.text('Yardım').first);
    await _bekle(t, const Duration(milliseconds: 600));
    await t.tap(find.text('Lisanslar').last);
    await _bulanaKadar(t, find.byType(AlertDialog), sn: 10);
    final lis = _metinler(find.byType(AlertDialog)).join(' ');
    _yaz('Lisanslar penceresi açılıyor (MIT)', !lis.contains('MIT'), '');
    await t.tap(find.text('Kapat').last);
    await _bekle(t, const Duration(milliseconds: 500));

    File(p.join(ev, 'eksikler_raporu.txt')).writeAsStringSync(_rapor.join('\n'));
  }, timeout: const Timeout(Duration(minutes: 6)));
}
