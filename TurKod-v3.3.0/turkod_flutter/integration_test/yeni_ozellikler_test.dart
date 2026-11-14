// Gerçek TürKod uygulamasını (gerçek Python arka ucuyla) açıp v3.2.x'te
// eklenen özellikleri kullanıcı gibi dener; her madde için RAPOR satırı yazar.
//
// ÇALIŞTIRMA (ayarlar boş bir klasöre yönlendirilmeden test durur):
//   set TURKOD_TEST_PROFIL=<boş bir klasör>\turkod_yeni_...
//   flutter test integration_test/yeni_ozellikler_test.dart -d windows
// TURKOD_EKRAN_BETIGI verilirse (PowerShell betiği) önemli adımlarda
// pencerenin ekran görüntüsü alınır.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:re_editor/re_editor.dart' as re;
import 'package:turkod_ide/main.dart' as app;

final _sonuclar = <(String, bool)>[];

void _yaz(String madde, bool gecti, [String ayrinti = '']) {
  _sonuclar.add((madde, gecti));
  // ignore: avoid_print
  print('RAPOR|${gecti ? "GEÇTİ" : "KALDI"}|$madde|$ayrinti');
}

Future<void> _bekle(WidgetTester t, Duration d) async {
  final son = DateTime.now().add(d);
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 50));
    await Future<void>.delayed(const Duration(milliseconds: 50));
  }
}

Future<bool> _kosulBekle(WidgetTester t, bool Function() kosul,
    {int sn = 20}) async {
  final son = DateTime.now().add(Duration(seconds: sn));
  while (DateTime.now().isBefore(son)) {
    await t.pump(const Duration(milliseconds: 100));
    await Future<void>.delayed(const Duration(milliseconds: 100));
    if (kosul()) return true;
  }
  return false;
}

Future<void> _ekran(String ad) async {
  final betik = Platform.environment['TURKOD_EKRAN_BETIGI'];
  if (betik == null || betik.isEmpty) return;
  final cikti = p.join(p.dirname(betik), 'ekran_$ad.png');
  await Process.run('powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', betik, cikti]);
}

Future<void> _tuslar(WidgetTester t, LogicalKeyboardKey tus,
    {bool ctrl = false, bool shift = false, bool alt = false}) async {
  if (ctrl) await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  if (shift) await t.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
  if (alt) await t.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
  await t.sendKeyEvent(tus);
  if (alt) await t.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
  if (shift) await t.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
  if (ctrl) await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
  await _bekle(t, const Duration(milliseconds: 700));
}

List<String> _metinler(Finder kok) => [
      for (final e in find
          .descendant(of: kok, matching: find.byType(Text))
          .evaluate())
        ((e.widget as Text).data ??
            (e.widget as Text).textSpan?.toPlainText() ??
            '')
    ].where((s) => s.trim().isNotEmpty).toList();

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('TürKod yeni özellikler — gerçek uygulamada deneme', (t) async {
    final ev = Platform.environment['TURKOD_TEST_PROFIL'] ?? '';
    if (!p.basename(ev).startsWith('turkod_yeni_')) {
      fail('Güvenlik: TURKOD_TEST_PROFIL bir sandbox klasörü değil ($ev).');
    }
    // Arayüz turu gösterilmesin (görülmüş say).
    File(p.join(ev, '.turkod_ayarlar.json')).writeAsStringSync(
        jsonEncode({'arayuz_turu_goruldu': true, 'son_proje_dizini': ev}));
    final proje = Directory(p.join(ev, 'proje'))..createSync();
    File(p.join(proje.path, 'yardimci.trpy'))
        .writeAsStringSync('fonksiyon selam(ad):\n    yazdır("Selam", ad)\n');

    app.main(const []);
    expect(
        await _kosulBekle(t, () => find.text('Dosya').evaluate().isNotEmpty,
            sn: 90),
        isTrue,
        reason: 'Ana pencere açılmadı');
    final ctx = t.element(find.text('Dosya').first);
    final ed = ctx.read<app.EditorProvider>();
    final ui = ctx.read<app.UiProvider>();
    final bp = ctx.read<app.BreakpointProvider>();
    final terminal = ctx.read<app.TerminalProvider>();
    final ayarlar = ctx.read<app.SettingsProvider>();
    final backend = ctx.read<app.BackendService>();
    expect(await _kosulBekle(t, () => backend.isConnected, sn: 60), isTrue,
        reason: 'Arka uç bağlanmadı');
    await _bekle(t, const Duration(seconds: 2));
    await _ekran('01_acilis');

    // ------------------------------------------------ 1) menü öğeleri
    final menuMetni = <String>[];
    for (final m in ['Dosya', 'Düzenle', 'Görünüm', 'Çalıştır']) {
      await t.tap(find.text(m).first);
      await _bekle(t, const Duration(milliseconds: 600));
      for (final e in find
          .byWidgetPredicate((w) => w is PopupMenuItem)
          .evaluate()) {
        menuMetni.addAll(_metinler(find.byWidget(e.widget)));
      }
      if (m == 'Düzenle') await _ekran('02_duzenle_menusu');
      await t.sendKeyEvent(LogicalKeyboardKey.escape);
      await _bekle(t, const Duration(milliseconds: 400));
    }
    final menuler = menuMetni.join(' | ');
    for (final k in [
      'Tümünü Kaydet', 'Dosyalarda Ara', 'Tanıma Git', 'Adı Değiştir',
      'Kodu Biçimlendir', 'Alta İmleç Ekle', 'Tüm Eşleşmeleri Seç',
      'Sorunlar', 'Editörü Böl', 'Klavye Kısayolları', 'İmlece Kadar Çalıştır',
    ]) {
      _yaz('Menüde "$k"', menuler.contains(k));
    }

    // ------------------------------------------------ 2) tanımsız ad uyarısı + dalgalı çizgi
    await ed.createUntitled(content: 'sayi = 5\nyazdır(sayı)\n');
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.byType(re.CodeEditor).first);
    // Sözdizimi denetimi metin değişince çalışır: bir boşluk ekleyip sil.
    ed.uiController!.text = '${ed.uiController!.text} ';
    final uyari = await _kosulBekle(
        t, () => ui.sorunlar.any((s) => !s.hata && s.ad == 'sayı'));
    _yaz('Yazarken tanımsız ad uyarısı', uyari,
        ui.sorunlar.map((s) => s.mesaj).join(' / '));
    _yaz('Durum çubuğunda öneri', ui.syntaxStatus.contains("'sayi'"),
        ui.syntaxStatus);
    await _ekran('03_dalgali_cizgi');
    await _tuslar(t, LogicalKeyboardKey.keyM, ctrl: true, shift: true);
    final sorunPenceresi = find.textContaining('Sorunlar (').evaluate().isNotEmpty;
    _yaz('Sorunlar penceresi (Ctrl+Shift+M)', sorunPenceresi);
    await _ekran('04_sorunlar');
    if (sorunPenceresi) {
      await t.tap(find.text('Kapat').last);
      await _bekle(t, const Duration(milliseconds: 500));
    }

    // ------------------------------------------------ 3) çalıştırma hatası Türkçe + AI düğmesi
    // Çalıştır eylemindeki gibi terminal paneli açılır.
    ui.revealTerminal();
    terminal.run('sayi = 5\nyazdır(sayı)');
    final hataGeldi = await _kosulBekle(
        t, () => !terminal.isRunning && terminal.output.contains('[HATA]'),
        sn: 30);
    _yaz('Çalıştırma hatası Türkçe ad ve öneriyle',
        hataGeldi &&
            terminal.output.contains("'sayı' adında") &&
            terminal.output.contains("'sayi'") &&
            !terminal.output.contains('number'),
        terminal.output.replaceAll('\n', ' ').trim());
    await _bekle(t, const Duration(milliseconds: 500));
    _yaz('Terminalde "Hatayı AI ile açıkla" düğmesi',
        find.text('Hatayı AI ile açıkla').evaluate().isNotEmpty);
    await _ekran('05_terminal_hata');

    // ------------------------------------------------ 4) biçimlendir (Shift+Alt+F)
    await ed.createUntitled(content: 'x=1\neğer x>0 :\n  yazdır( x )');
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.byType(re.CodeEditor).first);
    await _tuslar(t, LogicalKeyboardKey.keyF, shift: true, alt: true);
    final bicimli = await _kosulBekle(t,
        () => ed.activeContent.value == 'x = 1\neğer x > 0:\n    yazdır(x)');
    _yaz('Kodu biçimlendir (Shift+Alt+F)', bicimli,
        jsonEncode(ed.activeContent.value));

    // ------------------------------------------------ 5) adı değiştir (F2)
    ed.uiController!.selection = const TextSelection.collapsed(offset: 0);
    await _bekle(t, const Duration(milliseconds: 300));
    await _tuslar(t, LogicalKeyboardKey.f2);
    final f2Penceresi = find.textContaining("adını değiştir").evaluate().isNotEmpty;
    if (f2Penceresi) {
      await t.enterText(find.byType(TextField).last, 'sayaç');
      await _ekran('06_ad_degistir');
      await t.tap(find.text('Değiştir').last);
    }
    final degisti = await _kosulBekle(
        t, () => ed.activeContent.value.startsWith('sayaç = 1'));
    _yaz('Adı değiştir (F2)', f2Penceresi && degisti,
        jsonEncode(ed.activeContent.value));

    // ------------------------------------------------ 6) çoklu imleç
    await ed.createUntitled(content: 'a\nb\nc');
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.byType(re.CodeEditor).first);
    final c = ed.uiController!;
    c.selection = const TextSelection.collapsed(offset: 1);
    await _bekle(t, const Duration(milliseconds: 300));
    await _tuslar(t, LogicalKeyboardKey.arrowDown, ctrl: true, alt: true);
    await _tuslar(t, LogicalKeyboardKey.arrowDown, ctrl: true, alt: true);
    await _ekran('07_coklu_imlec');
    // Birincil imleçte yazma (klavyeden yazmadaki gibi metin + imleç).
    final s0 = c.selection.baseOffset;
    c.value = TextEditingValue(
        text: c.text.replaceRange(s0, s0, 'x'),
        selection: TextSelection.collapsed(offset: s0 + 1));
    final cokluTamam =
        await _kosulBekle(t, () => ed.activeContent.value == 'ax\nbx\ncx');
    _yaz('Çoklu imleç (Ctrl+Alt+↓ ile yazma)', cokluTamam,
        jsonEncode(ed.activeContent.value));

    // ------------------------------------------------ 7) editörü böl
    await _tuslar(t, LogicalKeyboardKey.backslash, ctrl: true);
    final bolundu = find.byType(app.YanEditor).evaluate().isNotEmpty;
    _yaz('Editörü böl (Ctrl+\\)', bolundu,
        'yanSekmeId=${ui.yanSekmeId} etkin=${ed.activeTab?.id}');
    await _ekran('08_bolunmus');
    await _tuslar(t, LogicalKeyboardKey.backslash, ctrl: true);

    // ------------------------------------------------ 8) üzerine gelince açıklama
    await ed.createUntitled(content: 'yazdır(uzunluk([1, 2]))');
    await _bekle(t, const Duration(seconds: 1));
    final alan = t.getRect(find.byType(re.CodeEditor).first);
    final fare = await t.createGesture(kind: PointerDeviceKind.mouse);
    await fare.addPointer(location: alan.topLeft + const Offset(1, 1));
    var ipucu = false;
    for (var x = 40.0; x < 260 && !ipucu; x += 12) {
      await fare.moveTo(alan.topLeft + Offset(x, 18));
      ipucu = await _kosulBekle(
          t, () => find.textContaining('Python:').evaluate().isNotEmpty,
          sn: 2);
    }
    _yaz('Üzerine gelince açıklama', ipucu,
        ipucu ? _metinler(find.textContaining('Python:')).join(' / ') : '');
    await _ekran('09_aciklama');
    await fare.moveTo(alan.bottomRight + const Offset(50, 50));
    await fare.removePointer();

    // ------------------------------------------------ 9) dosyalarda ara + tanıma git
    final ana = File(p.join(proje.path, 'ana.trpy'))
      ..writeAsStringSync('den yardimci içe_aktar selam\nselam("Ali")\n');
    await ed.openFile(ana.path);
    await _bekle(t, const Duration(seconds: 1));
    final tanim = await backend.call('tanim_bul',
        {'kod': ed.activeContent.value, 'ad': 'selam', 'dosya': ana.path});
    _yaz('Tanıma git yerel modüle', '${tanim['yol']}'.endsWith('yardimci.trpy'),
        '$tanim');
    final ara = await backend.call('dosyalarda_ara',
        {'dizin': proje.path, 'sorgu': 'selam'});
    _yaz('Dosyalarda ara', (ara['sonuclar'] as List).length >= 3,
        '${(ara['sonuclar'] as List).length} sonuç');

    // ------------------------------------------------ 10) hata ayıklayıcı: N. geçiş + değer atama
    await ed.createUntitled(
        content: 'toplam = 0\niçin i içinde aralık(10):\n    toplam += i\n'
            'yazdır("toplam", toplam)');
    await _bekle(t, const Duration(seconds: 1));
    final sekme = ed.activeTab!.id;
    bp.setCondition(sekme, 3, app.BreakpointProvider.kosulBirlestir(4, ''));
    await t.tap(find.byType(re.CodeEditor).first);
    await _tuslar(t, LogicalKeyboardKey.f5);
    final durdu = await _kosulBekle(t, () => bp.paused, sn: 30);
    final i = bp.globals.where((v) => v.name == 'i').map((v) => v.value);
    _yaz('Hata ayıklayıcı 4. geçişte durur', durdu && i.contains('3'),
        'i=${i.join()}');
    await _ekran('10_debug');
    final hata = await bp.setVariable('toplam', '100');
    await _bekle(t, const Duration(seconds: 1));
    final toplam = bp.globals.where((v) => v.name == 'toplam').map((v) => v.value);
    _yaz('Hata ayıklayıcıda değer değiştirme', hata == null && toplam.contains('100'),
        hata ?? 'toplam=${toplam.join()}');
    bp.clearAll(sekme);
    await bp.continueRun();
    final bitti = await _kosulBekle(
        t, () => !bp.debugging && terminal.output.contains('toplam 142'),
        sn: 30);
    _yaz('Atanan değer programa yansır', bitti,
        terminal.output.replaceAll('\n', ' ').trim());

    // ------------------------------------------------ 11) yüksek kontrast tema + kısayol penceresi
    await ayarlar.setValue('tema', 'Yüksek Kontrast');
    await _bekle(t, const Duration(seconds: 1));
    final tema = Theme.of(t.element(find.text('Dosya').first));
    _yaz('Yüksek Kontrast teması', tema.colorScheme.surface == Colors.black,
        '${tema.colorScheme.surface}');
    await _ekran('11_yuksek_kontrast');
    await ayarlar.setValue('tema', 'Modern Koyu');
    await t.tap(find.text('Görünüm').first);
    await _bekle(t, const Duration(milliseconds: 600));
    await t.tap(find.text('Klavye Kısayolları…').last);
    final kisayol = await _kosulBekle(t,
        () => find.text('Klavye Kısayolları').evaluate().isNotEmpty, sn: 5);
    _yaz('Klavye kısayolları penceresi', kisayol);
    await _ekran('12_kisayollar');
    if (kisayol) {
      await t.tap(find.text('Kapat').last);
      await _bekle(t, const Duration(milliseconds: 500));
    }

    // ------------------------------------------------ 12) metin isteyen pencereler
    // Pencere kapanırken metin kutusunun denetleyicisi erken atılırsa
    // Flutter "used after being disposed" istisnası verir ve test düşer.
    await ed.createUntitled(content: 'yazdır("argüman")');
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.text('Çalıştır').first);
    await _bekle(t, const Duration(milliseconds: 600));
    await t.tap(find.text('Çalıştırma Argümanları…').last);
    await _bekle(t, const Duration(milliseconds: 800));
    await t.enterText(find.byType(TextField).last, 'veri.txt --ayrintili');
    await t.tap(find.text('Kaydet').last);
    await _bekle(t, const Duration(seconds: 1));
    _yaz('Çalıştırma Argümanları penceresi',
        ed.activeTab?.runArgs == 'veri.txt --ayrintili',
        'runArgs=${ed.activeTab?.runArgs}');

    await ctx.read<app.FileTreeProvider>().setProjectDirectory(proje.path);
    await _bekle(t, const Duration(seconds: 1));
    await t.tap(find.byTooltip('Yeni Dosya').first);
    await _bekle(t, const Duration(milliseconds: 800));
    await t.enterText(find.byType(TextField).last, 'yeni_dosya.trpy');
    await t.tap(find.text('Tamam').last);
    final olustu = await _kosulBekle(
        t, () => File(p.join(proje.path, 'yeni_dosya.trpy')).existsSync(),
        sn: 10);
    _yaz('Gezginde yeni dosya ad penceresi', olustu);
    await _ekran('13_yeni_dosya');

    final kalan = _sonuclar.where((s) => !s.$2).map((s) => s.$1).toList();
    // ignore: avoid_print
    print('ÖZET|${_sonuclar.length - kalan.length}/${_sonuclar.length} geçti'
        '${kalan.isEmpty ? '' : ' | kalanlar: ${kalan.join(", ")}'}');
    expect(kalan, isEmpty);
  });
}
