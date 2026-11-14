import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart' as app;

void main() {
  group('EXE paneli komutu', () {
    test('varsayılan seçenekler yalnızca dosyayı yazar', () {
      expect(app.ExeAyarlari().komut(r'C:\Kod\oyun.trpy'),
          r'turkod exe_yap C:\Kod\oyun.trpy');
    });

    test('tikler -- ile başlayan seçeneklere dönüşür', () {
      final a = app.ExeAyarlari()
        ..ad = 'Uzay Oyunu'
        ..kayitYeri = r'C:\Oyun Klasörü'
        ..pencere = app.ExePencere.konsol
        ..kaynakAcik = true
        ..klasorlu = true
        ..sondaBekle = true
        ..simge = 'simge.ico'
        ..ekler.addAll(['resimler', 'ses dosyası.wav']);
      // Sıra Python'daki exe_donusturucu.komut_metni ile aynıdır
      // (tests/test_exe_donusturucu.py geri ayrıştırmayı sınar).
      expect(
          a.komut(r'C:\Kod\uzay oyunu.trpy'),
          r'turkod exe_yap "C:\Kod\uzay oyunu.trpy" --ad "Uzay Oyunu" '
          r'--kayit-yeri "C:\Oyun Klasörü" --windows-konsolu --kaynak-acik '
          r'--klasorlu --sonda-bekle --simge simge.ico --dosya-ekle resimler '
          r'--dosya-ekle "ses dosyası.wav"');
    });

    test('tırnaklı yolun sonundaki ters eğik çizgi ikilenir', () {
      // "C:\Oyun Klasörü\" yazılırsa \" kapanış tırnağını kaçırıyordu.
      final a = app.ExeAyarlari()..kayitYeri = r'C:\Oyun Klasörü\';
      expect(a.komut('a.trpy'),
          r'turkod exe_yap a.trpy --kayit-yeri "C:\Oyun Klasörü\\"');
      final b = app.ExeAyarlari()..kayitYeri = r'D:\';
      expect(b.komut('a.trpy'), r'turkod exe_yap a.trpy --kayit-yeri D:\');
    });

    test('göreli kayıt klasörü kod dosyasının klasörüne göre gösterilir', () {
      // Arka uçtaki exe_yap ile aynı kural (önizleme ile gerçek yer aynı olsun).
      const kod = r'C:\Kodlar\Oyun';
      expect(app.exeKayitKlasoru(kod, ''), kod);
      expect(app.exeKayitKlasoru(kod, '  '), kod);
      expect(app.exeKayitKlasoru(kod, 'EXE'), r'C:\Kodlar\Oyun\EXE');
      expect(app.exeKayitKlasoru(kod, r'..\Hazır\'), r'C:\Kodlar\Hazır');
      expect(app.exeKayitKlasoru(kod, r'D:\Oyunlar'), r'D:\Oyunlar');
      expect(app.exeKayitKlasoru(kod, r'\Oyunlar'), r'C:\Oyunlar');
    }, testOn: 'windows');

    test('sonda bekle yalnızca Windows konsolunda yazılır', () {
      final a = app.ExeAyarlari()
        ..pencere = app.ExePencere.yok
        ..sondaBekle = true;
      expect(a.komut('a.trpy'), 'turkod exe_yap a.trpy --terminalsiz');
    });
  });

  group('Her sekmenin kendi terminali', () {
    test('sekme değişince o sekmenin terminali açılır ya da kapanır', () {
      final ui = app.UiProvider();
      ui.sekmeDegisti('tab_1', false);
      ui.toggleTerminal();
      expect(ui.showTerminal, isTrue);

      ui.sekmeDegisti('tab_2', false);
      expect(ui.showTerminal, isFalse, reason: 'tab_2 terminal açmadı');

      ui.revealTerminal();
      ui.toggleTerminal();
      expect(ui.showTerminal, isFalse);

      ui.sekmeDegisti('tab_1', false);
      expect(ui.showTerminal, isTrue, reason: 'tab_1 terminali açık kalmıştı');
    });

    test('Ayarlar sekmesinin terminali yok', () {
      final ui = app.UiProvider();
      ui.sekmeDegisti('tab_1', false);
      ui.focusTerminal();
      ui.sekmeDegisti('ayarlar', true);
      expect(ui.showTerminal, isFalse);
      ui.toggleTerminal();
      ui.revealTerminal();
      expect(ui.showTerminal, isFalse);
      ui.sekmeDegisti('tab_1', false);
      expect(ui.showTerminal, isTrue);
    });

    test('kayıtlı düzen açılıştaki sekmeye uygulanır', () {
      final ui = app.UiProvider();
      ui.applyLayout({'terminal': true});
      ui.sekmeDegisti('tab_1', false);
      expect(ui.showTerminal, isTrue);
      ui.sekmeDegisti('tab_2', false);
      expect(ui.showTerminal, isFalse);
    });

    test('kapanan sekmenin terminal bilgisi silinir', () {
      final ui = app.UiProvider();
      ui.sekmeDegisti('tab_1', false);
      ui.toggleTerminal();
      ui.sekmeDegisti('tab_2', false);
      ui.sekmeleriTemizle({'tab_2'});
      ui.sekmeDegisti('tab_1', false);
      expect(ui.showTerminal, isFalse);
    });
  });
}
