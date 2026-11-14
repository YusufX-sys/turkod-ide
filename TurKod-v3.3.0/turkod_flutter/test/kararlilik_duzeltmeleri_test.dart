import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:turkod_ide/main.dart' as app;

/// Bağlı görünen, komutları kaydeden sahte arka uç. Dosya komutları gerçek
/// geçici dosyalara yazar / okur.
class _Sahte extends app.BackendService {
  final komutlar = <String>[];
  final parametreler = <Map<String, dynamic>>[];

  /// true iken ayar okuma istekleri başarısız olur.
  bool ayarHatasi = false;

  /// true iken oturum yazılamaz (bağlantı yok gibi).
  bool oturumHatasi = false;

  /// Aynı anda süren oturum yazımlarının en yüksek sayısı.
  int _surenOturum = 0, enCokOturum = 0;
  final oturumYuku = <Map<String, dynamic>>[];

  Map<String, dynamic> Function(Map<String, dynamic> params)? ogeSil;

  @override
  bool get isConnected => true;

  @override
  Future<void> waitUntilConnected() async {}

  @override
  Future<Map<String, dynamic>> call(String command,
      [Map<String, dynamic> params = const {}]) async {
    komutlar.add(command);
    parametreler.add(params);
    switch (command) {
      case 'ayarlar_tumu':
        if (ayarHatasi) throw app.BackendException('bağlı değil');
        return {
          'ok': true,
          'ayarlar': {
            'tema': 'Modern Koyu',
            'ai_api_anahtarlari': {'openai': 'gizli'},
          },
        };
      case 'ayar_get':
        if (ayarHatasi) throw app.BackendException('bağlı değil');
        return {'ok': true, 'deger': null};
      case 'oturum_oku':
        return {'ok': true};
      case 'oturum_kaydet':
        _surenOturum++;
        if (_surenOturum > enCokOturum) enCokOturum = _surenOturum;
        try {
          await Future<void>.delayed(const Duration(milliseconds: 20));
          if (oturumHatasi) throw app.BackendException('bağlı değil');
          oturumYuku.add(params);
          return {'ok': true};
        } finally {
          _surenOturum--;
        }
      case 'dosya_oku':
        final yol = params['yol'] as String;
        return {
          'ok': true,
          'yol': yol,
          'isim': p.basename(yol),
          'icerik': File(yol).readAsStringSync(),
        };
      case 'dosya_kaydet':
        File(params['yol'] as String)
            .writeAsStringSync(params['icerik'] as String);
        return {'ok': true};
      case 'oge_sil':
        final f = ogeSil;
        if (f == null) return {'ok': true};
        final r = f(params);
        if (r['ok'] == false) throw app.BackendException.fromResult(r);
        return r;
    }
    return {'ok': true};
  }
}

Future<void> _bekle([int ms = 60]) =>
    Future<void>.delayed(Duration(milliseconds: ms));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Ayarlar okunamazsa', () {
    test('yüklendi sayılmaz; okununca yüklenir', () async {
      final b = _Sahte()..ayarHatasi = true;
      final s = app.SettingsProvider(b);
      addTearDown(s.dispose);
      await s.load();
      expect(s.loaded, isFalse);
      expect(s.okundu, isFalse);

      b.ayarHatasi = false;
      await s.load();
      expect(s.loaded, isTrue);
      expect(s.okundu, isTrue);
      expect(s.get<dynamic>('ai_api_anahtarlari'), {'openai': 'gizli'});
    });

    testWidgets('Ayarlar sayfası form göstermez (kaydedilemez)',
        (tester) async {
      final b = app.BackendService(); // hiç bağlanmaz
      final s = app.SettingsProvider(b);
      addTearDown(() {
        s.dispose();
        b.dispose();
      });
      await tester.pumpWidget(MultiProvider(
        providers: [
          Provider<app.BackendService>.value(value: b),
          ChangeNotifierProvider<app.SettingsProvider>.value(value: s),
        ],
        child: MaterialApp(
          theme: app.AppThemeRegistry.build('Modern Koyu'),
          home: const app.SettingsPage(),
        ),
      ));
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.textContaining('Ayarlar okunuyor'), findsOneWidget);
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
    });
  });

  group('Editör', () {
    late Directory dizin;
    setUp(() => dizin = Directory.systemTemp.createTempSync('turkod_test'));
    tearDown(() {
      try {
        dizin.deleteSync(recursive: true);
      } catch (_) {}
    });

    test('otomatik kayıt silinen dosyayı yeniden oluşturmaz', () async {
      final b = _Sahte();
      final ed = app.EditorProvider(b);
      addTearDown(ed.dispose);
      await _bekle();
      final dosya = File(p.join(dizin.path, 'a.trpy'))..writeAsStringSync('x');
      await ed.openFile(dosya.path);
      ed.updateContent('yeni');
      dosya.deleteSync();
      ed.markDeleted(dosya.path);
      ed.autoSave();
      await _bekle();
      expect(dosya.existsSync(), isFalse);
      expect(b.komutlar, isNot(contains('dosya_kaydet')));
      expect(ed.activeTab!.dirty, isTrue);
    });

    test('silinen dosya Ctrl+S ile sorulmadan yeniden oluşturulmaz', () async {
      final b = _Sahte();
      final ed = app.EditorProvider(b);
      addTearDown(ed.dispose);
      await _bekle();
      final dosya = File(p.join(dizin.path, 'b.trpy'))..writeAsStringSync('x');
      await ed.openFile(dosya.path);
      ed.updateContent('yeni');
      dosya.deleteSync();
      var soruldu = 0;
      ed.silinenDosyaSor = (_) async {
        soruldu++;
        return false;
      };
      expect(await ed.saveActive(), isFalse);
      expect(dosya.existsSync(), isFalse);
      ed.silinenDosyaSor = (_) async => true;
      expect(await ed.saveActive(), isTrue);
      expect(dosya.readAsStringSync(), 'yeni');
      expect(soruldu, 1);
    });

    test('art arda iki kayıt yersiz çakışma sormaz', () async {
      final b = _Sahte();
      final ed = app.EditorProvider(b);
      addTearDown(ed.dispose);
      await _bekle();
      final dosya = File(p.join(dizin.path, 'c.trpy'))..writeAsStringSync('x');
      await ed.openFile(dosya.path);
      var cakisma = 0;
      ed.diskCakismasiSor = (_) async {
        cakisma++;
        return true;
      };
      ed.updateContent('bir');
      final k1 = ed.saveActive();
      ed.updateContent('iki');
      final k2 = ed.saveActive();
      await Future.wait([k1, k2]);
      expect(cakisma, 0);
      expect(dosya.readAsStringSync(), 'iki');
    });

    test('oturum yazımları sıraya girer, Kaydetmeden Çık yedeği atar',
        () async {
      final b = _Sahte();
      final ed = app.EditorProvider(b);
      addTearDown(ed.dispose);
      await _bekle();
      final dosya = File(p.join(dizin.path, 'd.trpy'))..writeAsStringSync('x');
      await ed.openFile(dosya.path);
      ed.updateContent('kaydedilmeyecek');
      final id = ed.activeTab!.id;
      ed.setRunArgs(id, '1');
      ed.setRunArgs(id, '2');
      final ok = await ed.saveSessionNow(yedekler: false);
      await _bekle(300);
      expect(ok, isTrue);
      expect(b.enCokOturum, 1);
      final son = b.oturumYuku.last['sekmeler'] as List;
      expect((son.first as Map).containsKey('yedek'), isFalse);
    });

    test('oturum yazılamazsa false döner; adsız sekme bilinir', () async {
      final b = _Sahte();
      final ed = app.EditorProvider(b);
      addTearDown(ed.dispose);
      await _bekle();
      await ed.createUntitled(content: 'merhaba');
      b.oturumHatasi = true;
      expect(await ed.saveSessionNow(), isFalse);
      expect(ed.adsizIcerikliSekmeler, hasLength(1));
    });
  });

  test('Geri dönüşüm kutusu yoksa kalıcı silme sorulur', () async {
    final b = _Sahte()
      ..ogeSil = (prm) => prm['kalici'] == true
          ? {'ok': true, 'kalici': true}
          : {
              'ok': false,
              'kalici_gerekir': true,
              'yol': prm['yol'],
              'hata': 'Kalıcı silinsin mi?',
            };
    final agac = app.FileTreeProvider(b);
    addTearDown(agac.dispose);
    final node = app.FileNode(name: 'x.trpy', path: 'E:/x.trpy', isDir: false);
    final r1 = await agac.sil(node);
    expect(r1.kaliciGerekir, isTrue);
    expect(r1.hata, 'Kalıcı silinsin mi?');
    final r2 = await agac.sil(node, kalici: true);
    expect(r2.hata, isNull);
    expect(r2.kalici, isTrue);
  });

  test('terminal boyutu bildirilir; kabuktan önce gönderilir', () async {
    final b = _Sahte();
    final t = app.TerminalProvider(b);
    addTearDown(t.dispose);
    t.boyutBildir(120, 30);
    await _bekle(10);
    t.boyutBildir(120, 30); // değişmedi: yeniden gönderilmez
    await _bekle(10);
    expect(b.komutlar.where((k) => k == 'terminal_boyutu'), hasLength(1));
    final prm = b.parametreler[b.komutlar.indexOf('terminal_boyutu')];
    expect(prm['sutun'], 120);
    expect(prm['satir'], 30);
    await t.kabukBaslat();
    final i = b.komutlar.indexOf('kabuk_baslat');
    expect(i, greaterThan(0));
    expect(b.komutlar[i - 1], 'terminal_boyutu');
  });

  test('terminal karakter boyutu piksel boyutundan hesaplanır', () {
    const stil = TextStyle(fontSize: 13, height: 1.35);
    final kucuk = app.terminalKarakterBoyutu(const Size(400, 200), stil);
    final buyuk = app.terminalKarakterBoyutu(const Size(800, 400), stil);
    expect(kucuk.$1, greaterThan(10));
    expect(kucuk.$2, greaterThan(3));
    expect(buyuk.$1, greaterThan(kucuk.$1));
    expect(buyuk.$2, greaterThan(kucuk.$2));
  });
}
