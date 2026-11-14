// Kodi hata düzeltmeleri: işlerin sırayla ve bir kez yapılması, yarıda kalan
// cevabın işleri, masaüstü köprüsünün geç cevabı, katlı kodun korunması için
// imleç hesabı, Markdown önbelleği.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart' as app;
import 'package:turkod_ide/markdown_gorunum.dart';

/// Köprü mesajlarını yakalayan, olayları elle gönderilen sahte arka uç.
class _KopruBackend extends app.BackendService {
  final olaylar = StreamController<app.BackendEvent>.broadcast();
  final gonderilen = <Map<String, dynamic>>[];
  final komutlar = <String>[];

  @override
  Stream<app.BackendEvent> get events => olaylar.stream;

  @override
  Future<Map<String, dynamic>> call(String command,
      [Map<String, dynamic> params = const {}]) {
    komutlar.add(command);
    if (command == 'kodi_kopru_gonder') {
      gonderilen.add(Map<String, dynamic>.from(params['veri'] as Map));
    }
    return Future.value({'ok': true});
  }

  void cevapla(Map<String, dynamic> veri) =>
      olaylar.add(app.BackendEvent(name: 'kodi_kopru', data: veri));
}

app.KodiEylemi _panel(String p) =>
    app.KodiEylemi('panel', {'eylem': 'panel', 'panel': p, 'durum': 'ac'});

void main() {
  test('kodiModelOfseti: satır ve sütun dosyadaki gerçek metne göre', () {
    const metin = 'a = 1\neğer a:\n    yazdır(a)\nb = 2';
    expect(app.kodiModelOfseti(metin, 1, 0), 0);
    expect(app.kodiModelOfseti(metin, 2, 4), 'a = 1\neğer'.length);
    // Sütun satırdan uzunsa satırın sonu.
    expect(app.kodiModelOfseti(metin, 1, 99), 'a = 1'.length);
    // Olmayan satır: metnin sonu.
    expect(app.kodiModelOfseti(metin, 9, 0), metin.length);
    expect(app.kodiModelOfseti(metin, 4, 5), metin.length);
  });

  testWidgets('Güvenli işler sırayla ve bir kez yapılır', (tester) async {
    final kodi = app.KodiProvider(app.BackendService());
    final kayit = <String>[];
    final bitir = <String, Completer<void>>{};
    kodi.eylemUygula = (e, {hedef}) async {
      final p = '${e.veri['panel']}';
      kayit.add('başla $p');
      await (bitir[p] = Completer<void>()).future;
      e.durum = 'yapildi';
      kayit.add('bitti $p');
    };
    final m = app.KodiMesaji(true, 'Tamam', eylemler: [_panel('gezgin'), _panel('ai')]);
    kodi.mesajlar.add(m);

    final f1 = kodi.eylemleriBaslat(m);
    final f2 = kodi.eylemleriBaslat(m); // ikinci başlatma yok sayılır
    await tester.pump();
    // İkincisi birincisi bitmeden başlamaz (eskiden hepsi aynı anda başlıyordu).
    expect(kayit, ['başla gezgin']);
    expect(m.eylemler[0].durum, 'calisiyor');
    expect(m.eylemler[1].durum, 'bekliyor');

    bitir['gezgin']!.complete();
    await tester.pump();
    expect(kayit, ['başla gezgin', 'bitti gezgin', 'başla ai']);
    bitir['ai']!.complete();
    await f1;
    await f2;
    expect(kayit.where((k) => k.startsWith('başla')).length, 2);
    expect(m.eylemler.every((e) => e.durum == 'yapildi'), isTrue);
  });

  testWidgets('İş sürerken ikinci tıklama işi yeniden yapmaz', (tester) async {
    final kodi = app.KodiProvider(app.BackendService());
    var kac = 0;
    final bitir = Completer<void>();
    kodi.eylemUygula = (e, {hedef}) async {
      kac++;
      await bitir.future;
      e.durum = 'yapildi';
      e.sonuc = 'Kod imlecin olduğu yere eklendi';
    };
    final e = app.KodiEylemi('kod_yaz', {'eylem': 'kod_yaz', 'kod': 'yazdır(1)'});
    final f = kodi.eylemiUygula(e, hedef: 'imlec');
    expect(e.durum, 'calisiyor'); // beklemeden işaretlenir
    await kodi.eylemiUygula(e, hedef: 'imlec');
    // Kod bloğundaki düğmeye ikinci kez basılması (yeni bir eylem) da.
    await kodi.eylemiUygula(
        app.KodiEylemi('kod_yaz', {'eylem': 'kod_yaz', 'kod': 'yazdır(1)'}),
        hedef: 'imlec');
    expect(kac, 1);
    expect(app.kodiSonIslemler([app.KodiMesaji(true, 'x', eylemler: [e])]),
        ['kod_yaz: yapılıyor']);
    bitir.complete();
    await f;
    expect(e.durum, 'yapildi');
    expect(kac, 1);
  });

  testWidgets('Kodi kapatılınca yazılmakta olan cevabın güvenli işleri yapılır',
      (tester) async {
    final kodi = app.KodiProvider(app.BackendService());
    final yapilan = <String>[];
    kodi.eylemUygula = (e, {hedef}) async {
      yapilan.add(e.tur);
      e.durum = 'yapildi';
    };
    kodi.acik = true;
    final izinli = app.KodiEylemi(
        'komut', {'eylem': 'komut', 'id': 'run.run', 'etiket': 'Çalıştır'});
    kodi.mesajlar.add(app.KodiMesaji(true, 'Açıyorum', eylemler: [_panel('ai'), izinli]));
    kodi.kapat();
    await tester.pump();
    expect(yapilan, ['panel']);
    // İzin isteyen iş kendiliğinden yapılmaz.
    expect(izinli.durum, 'bekliyor');
  });

  testWidgets('Masaüstü penceresi: bağlam beklenirken ikinci soru gitmez, vazgeçilir',
      (tester) async {
    final b = _KopruBackend();
    final kodi = app.KodiProvider(b, pencereKipi: true);
    kodi.acik = true;
    unawaited(kodi.sor('Birinci soru'));
    // Bağlam ana pencereden gelmeden önce de bekliyor.
    expect(kodi.bekliyor, isTrue);
    unawaited(kodi.sor('İkinci soru'));
    await tester.pump();
    expect(kodi.mesajlar.where((m) => !m.kodiden).length, 1);
    kodi.vazgec();
    expect(kodi.bekliyor, isFalse);
    await tester.pump(const Duration(seconds: 31));
    // Vazgeçilen soru motora hiç gitmez.
    expect(b.komutlar, isNot(contains('kodi_sor')));
  });

  testWidgets('Masaüstü penceresi: uzun iş için bekler, geç gelen cevabı da yazar',
      (tester) async {
    final b = _KopruBackend();
    final kodi = app.KodiProvider(b, pencereKipi: true);
    await kodi.kopruKaydol();
    final e = app.KodiEylemi('tarayici', {'eylem': 'tarayici', 'islem': 'tikla', 'no': 3});
    kodi.mesajlar.add(app.KodiMesaji(true, 'Basıyorum', eylemler: [e]));
    final f = kodi.eylemiUygula(e);
    await tester.pump();
    final no = b.gonderilen.lastWhere((v) => v['tur'] == 'eylem')['no'];

    // 30 sn eskiden "cevap vermedi" için yetiyordu; artık iş sürüyor.
    await tester.pump(const Duration(seconds: 40));
    expect(e.durum, 'calisiyor');
    await tester.pump(const Duration(seconds: 90));
    await f;
    expect(e.durum, 'hata');
    expect(e.sonuc, 'TürKod cevap vermedi');

    // Geç gelen gerçek cevap uygulanır.
    b.cevapla({'yanit_no': no, 'durum': 'yapildi', 'sonuc': '"Oyna" tıklandı'});
    await tester.pump();
    expect(e.durum, 'yapildi');
    expect(e.sonuc, '"Oyna" tıklandı');
    kodi.dispose();
    await tester.pump(const Duration(minutes: 11));
  });

  testWidgets('Masaüstüne geçen sohbetin bekleyen işlerini masaüstü Kodi yapar',
      (tester) async {
    final b = _KopruBackend();
    final ana = app.KodiProvider(b);
    await ana.kopruKaydol();
    final yapilan = <String>[];
    ana.eylemUygula = (e, {hedef}) async {
      yapilan.add(e.tur);
      e.durum = 'yapildi';
    };
    ana.acik = true;
    ana.mesajlar.add(app.KodiMesaji(true, 'Açıyorum', eylemler: [_panel('ai')]));
    // Masaüstü penceresi hazır dedi: sohbet oraya gider.
    b.cevapla({'tur': 'hazir', 'no': 7});
    await tester.pump();
    final yanit = b.gonderilen.lastWhere((v) => v['yanit_no'] == 7);
    expect(yanit['hep_sor'], isFalse);
    // Ana pencerede balon kapanırken işler buradan başlatılmaz (masaüstü yapar).
    await ana.eylemleriBaslat(ana.mesajlar.last);
    expect(yapilan, isEmpty);
    final giden = (yanit['mesajlar'] as List).last as Map;
    expect(((giden['eylemler'] as List).first as Map)['_durum'], 'bekliyor');

    // Masaüstü Kodi kapandı, sohbet geri geldi: bekleyen iş ana pencerede yapılır.
    b.cevapla({'tur': 'kapandi', 'mesajlar': yanit['mesajlar'], 'hep_sor': false});
    await tester.pump();
    await tester.pump();
    expect(yapilan, ['panel']);
  });

  testWidgets('Markdown: bağlantılı metin defalarca çizilir, tanıyıcılar atılır',
      (tester) async {
    const metin = 'Bak: [kitap](https://ornek.org) ve **kalın**';
    expect(identical(markdownAyristirOnbellekli(metin), markdownAyristirOnbellekli(metin)),
        isTrue);
    String? acilan;
    for (var i = 0; i < 20; i++) {
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              body: MarkdownGorunum('$metin ${i.isEven ? '' : 'https://x.org/$i'}',
                  baglanti: (u) => acilan = u))));
    }
    // Yalnızca bağlantıdan oluşan metin: başına dokunmak bağlantıya dokunmaktır.
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: Center(
                child: SizedBox(
                    width: 200,
                    child: MarkdownGorunum('[kitap](https://ornek.org)',
                        baglanti: (u) => acilan = u))))));
    await tester.tapAt(tester.getTopLeft(find.textContaining('kitap', findRichText: true)) +
        const Offset(6, 6));
    expect(acilan, 'https://ornek.org');
    await tester.pumpWidget(const SizedBox());
    expect(tester.takeException(), isNull);
  });
}
