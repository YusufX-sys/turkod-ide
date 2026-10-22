// Kritik düzeltmeleri gerçek uygulamada (gerçek backend ile) dener.
//
// İki aşama, aynı sandbox klasörüyle art arda çalıştırılır:
//   TURKOD_TEST_PROFIL=<...\turkod_eksik_x>  TURKOD_TEST_ASAMA=1  flutter test integration_test/duzeltmeler_test.dart -d windows
//   TURKOD_TEST_PROFIL=<aynı klasör>          TURKOD_TEST_ASAMA=2  flutter test integration_test/duzeltmeler_test.dart -d windows
// 1. aşamanın sonunda uygulama çıkış akışı olmadan kapanır (çökme gibi);
// 2. aşama kaydedilmemiş değişikliklerin kurtarıldığını denetler.
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

Future<bool> _bulanaKadar(WidgetTester t, Finder f, {int sn = 60}) async {
  final son = DateTime.now().add(Duration(seconds: sn));
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 100));
    await Future<void>.delayed(const Duration(milliseconds: 100));
    if (f.evaluate().isNotEmpty) return true;
  }
  return false;
}

Future<void> _menu(WidgetTester t, String menu, String oge) async {
  await t.tap(find.text(menu).first);
  await _bekle(t, const Duration(milliseconds: 600));
  await t.tap(find.text(oge).last);
  await _bekle(t, const Duration(milliseconds: 700));
}

Future<List<String>> _menuOgeleri(WidgetTester t, String menu) async {
  await t.tap(find.text(menu).first);
  await _bekle(t, const Duration(milliseconds: 600));
  final ogeler = [
    for (final e in find.byWidgetPredicate((w) => w is PopupMenuItem).evaluate())
      for (final m in find.descendant(of: find.byWidget(e.widget), matching: find.byType(Text)).evaluate())
        (m.widget as Text).data ?? ''
  ];
  await t.sendKeyEvent(LogicalKeyboardKey.escape);
  await _bekle(t, const Duration(milliseconds: 400));
  return ogeler;
}

Future<void> _ctrl(WidgetTester t, LogicalKeyboardKey tus) async {
  await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  await t.sendKeyEvent(tus);
  await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
  await _bekle(t, const Duration(milliseconds: 800));
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Kritik düzeltmeler', (t) async {
    final ev = Platform.environment['TURKOD_TEST_PROFIL'] ?? '';
    final asama = Platform.environment['TURKOD_TEST_ASAMA'] ?? '1';
    if (!p.basename(ev).startsWith('turkod_eksik_')) {
      fail('Güvenlik: TURKOD_TEST_PROFIL bir sandbox klasörü değil ($ev).');
    }
    final dosya1 = File(p.join(ev, 'kaydedilmemis.trpy'));
    final dosya2 = File(p.join(ev, 'kaydedilmis.trpy'));

    app.main(const []);
    expect(await _bulanaKadar(t, find.text('Dosya'), sn: 90), isTrue);
    await _bekle(t, const Duration(seconds: 3));
    final ed = t.element(find.text('Dosya').first).read<app.EditorProvider>();

    if (asama == '1') {
      // --- Menüler
      final duzenle = await _menuOgeleri(t, 'Düzenle');
      for (final k in ['Kes', 'Kopyala', 'Yapıştır', 'Tümünü Seç', 'Satıra Git…']) {
        _kontrol('Düzenle menüsünde "$k"', duzenle.contains(k));
      }
      final dosyaMenu = await _menuOgeleri(t, 'Dosya');
      _kontrol('Dosya menüsünde "Sekmeyi Kapat" (Ctrl+W)',
          dosyaMenu.contains('Sekmeyi Kapat') && dosyaMenu.contains('Ctrl+W'));

      // --- Düzenle menüsünden Tümünü Seç / Kopyala / Kes / Yapıştır
      await ed.createUntitled(content: 'bir\niki\nüç\ndört');
      await _bekle(t, const Duration(seconds: 1));
      await t.tap(find.byType(re.CodeEditor).first);
      await _bekle(t, const Duration(milliseconds: 400));
      await _menu(t, 'Düzenle', 'Tümünü Seç');
      final c = ed.uiController!;
      _kontrol('Menüden Tümünü Seç', c.selection.start == 0 && c.selection.end == c.text.length,
          '${c.selection}');
      await Clipboard.setData(const ClipboardData(text: ''));
      await _menu(t, 'Düzenle', 'Kopyala');
      final pano = (await Clipboard.getData('text/plain'))?.text ?? '';
      _kontrol('Menüden Kopyala', pano == 'bir\niki\nüç\ndört', jsonEncode(pano));
      await _menu(t, 'Düzenle', 'Kes');
      _kontrol('Menüden Kes', ed.activeTab!.content.isEmpty,
          'kalan=${jsonEncode(ed.activeTab!.content)}');
      await _menu(t, 'Düzenle', 'Yapıştır');
      await _bekle(t, const Duration(milliseconds: 500));
      _kontrol('Menüden Yapıştır', ed.activeTab!.content == 'bir\niki\nüç\ndört',
          jsonEncode(ed.activeTab!.content));

      // --- Ctrl+G Satıra Git
      await t.tap(find.byType(re.CodeEditor).first);
      await _ctrl(t, LogicalKeyboardKey.keyG);
      final pencere = find.widgetWithText(AlertDialog, 'Satıra Git');
      _kontrol('Ctrl+G Satıra Git penceresini açar', pencere.evaluate().isNotEmpty);
      if (pencere.evaluate().isNotEmpty) {
        await t.enterText(find.descendant(of: pencere, matching: find.byType(TextField)), '3');
        await t.testTextInput.receiveAction(TextInputAction.done);
        await _bekle(t, const Duration(milliseconds: 800));
        final off = ed.uiController!.selection.baseOffset;
        final satir = '\n'.allMatches(ed.uiController!.text.substring(0, off)).length + 1;
        _kontrol('Satıra Git imleci 3. satıra taşır', satir == 3, 'imleç satırı=$satir');
        // Geçersiz numara: uyarı verip pencere açık kalmalı
        await _ctrl(t, LogicalKeyboardKey.keyG);
        await t.enterText(find.descendant(of: pencere, matching: find.byType(TextField)), '99');
        await t.testTextInput.receiveAction(TextInputAction.done);
        await _bekle(t, const Duration(milliseconds: 600));
        _kontrol('Geçersiz satırda uyarı', find.textContaining('arasında bir satır').evaluate().isNotEmpty);
        await t.tap(find.text('Vazgeç').last);
        await _bekle(t, const Duration(milliseconds: 500));
      }

      // --- Ctrl+W: kaydedilmemiş sekmede soru, kaydedilmişte doğrudan kapatma
      await t.tap(find.byType(re.CodeEditor).first);
      await _ctrl(t, LogicalKeyboardKey.keyW);
      final soru = find.widgetWithText(AlertDialog, 'Kapat');
      _kontrol('Ctrl+W kaydedilmemiş sekmede "kaydedilmemiş" diye sorar', soru.evaluate().isNotEmpty);
      final once = ed.tabs.length;
      if (soru.evaluate().isNotEmpty) {
        await t.tap(find.descendant(of: soru, matching: find.widgetWithText(TextButton, 'Kapat')));
        await _bekle(t, const Duration(seconds: 1));
      }
      _kontrol('Ctrl+W sekmeyi kapatır', ed.tabs.length == once - 1, 'sekme: $once -> ${ed.tabs.length}');

      // --- Hakkında: sürüm
      await _menu(t, 'Yardım', 'Hakkında / İmza');
      await _bulanaKadar(t, find.textContaining('Sürüm '), sn: 15);
      final surumMetni = find.textContaining('Sürüm ').evaluate().map((e) => e.widget).map((w) => w is Text ? w.data ?? '' : w is SelectableText ? w.data ?? '' : w is EditableText ? w.controller.text : '').join(' ');
      _kontrol('Hakkında penceresinde sürüm', surumMetni.contains('3.2.0'), surumMetni);
      await t.tap(find.text('Kapat').last);
      await _bekle(t, const Duration(milliseconds: 500));

      // --- Kurtarma yedeği hazırlığı
      dosya1.writeAsStringSync('yazdır("diskteki eski")\n');
      dosya2.writeAsStringSync('yazdır("2 eski")\n');
      await ed.openFile(dosya2.path);
      await _bekle(t, const Duration(milliseconds: 500));
      ed.updateContent('yazdır("2 KAYDEDILDI")\n');
      await _bekle(t, const Duration(seconds: 3)); // yedek alınır
      await ed.saveActive();                       // sonra kaydedilir
      await _bekle(t, const Duration(seconds: 1));
      await ed.openFile(dosya1.path);
      await _bekle(t, const Duration(milliseconds: 500));
      ed.updateContent('yazdır("KURTARILMALI")\n');
      await ed.createUntitled(content: '');
      await _bekle(t, const Duration(milliseconds: 300));
      ed.updateContent('yazdır("YENI SEKME KURTARILMALI")\n');
      await _bekle(t, const Duration(seconds: 4));
      final ayar = jsonDecode(File(p.join(ev, '.turkod_ayarlar.json')).readAsStringSync());
      final oturum = jsonEncode(ayar['son_oturum']);
      _kontrol('Yazdıktan 4 sn sonra yedek diskte', oturum.contains('KURTARILMALI') &&
          oturum.contains('YENI SEKME KURTARILMALI'));
      _kontrol('Kaydedilen dosyanın yedeği kalmadı', !oturum.contains('2 KAYDEDILDI'));
      // Test burada biter: uygulama çıkış akışı OLMADAN kapanır (çökme benzetimi).
    } else {
      // --- 2. aşama: yeniden açılış
      await _bulanaKadar(t, find.textContaining('kurtarıldı'), sn: 20);
      _kontrol('Kurtarma bildirimi gösterildi',
          find.textContaining('kaydedilmemiş değişiklik kurtarıldı').evaluate().isNotEmpty);
      app.EditorTab? bul(String yol) {
        for (final x in ed.tabs) {
          if (x.path == yol) return x;
        }
        return null;
      }
      final s1 = bul(dosya1.path);
      _kontrol('Kaydedilmemiş dosya değişikliği geri geldi',
          s1 != null && s1.content.contains('KURTARILMALI') && s1.dirty,
          's1=${s1 == null ? "yok" : jsonEncode(s1.content)} kirli=${s1?.dirty}');
      _kontrol('Disk değişmedi (kullanıcı kaydetmeden yazılmadı)',
          dosya1.readAsStringSync().contains('diskteki eski'));
      final yeni = ed.tabs.where((x) => x.content.contains('YENI SEKME KURTARILMALI'));
      _kontrol('Kaydedilmemiş yeni sekme geri geldi', yeni.isNotEmpty);
      final s2 = bul(dosya2.path);
      _kontrol('Kaydedilmiş dosya temiz açıldı (eski yedek uygulanmadı)',
          s2 != null && !s2.dirty && s2.content.contains('2 KAYDEDILDI'),
          's2=${s2 == null ? "yok" : jsonEncode(s2.content)} kirli=${s2?.dirty}');
      // "Kaydetmeden Çık" yedeği silmeli
      await ed.saveSessionNow(yedekler: false);
      final ayar = jsonDecode(File(p.join(ev, '.turkod_ayarlar.json')).readAsStringSync());
      _kontrol('"Kaydetmeden Çık" yedeği siler',
          !jsonEncode(ayar['son_oturum']).contains('"yedek"'));
    }
    File(p.join(ev, 'sonuc_$asama.txt')).writeAsStringSync(_sonuc.join('\n'));
  }, timeout: const Timeout(Duration(minutes: 6)));
}
