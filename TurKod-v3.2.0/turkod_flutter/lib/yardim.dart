// Öğrenme kitabı, lisanslar ve dış bağlantılar (Öğren / Yardım menüleri).
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;

const String kGithubUrl = 'https://github.com/YusufX-sys/turkod-ide';
const String kHataBildirUrl = '$kGithubUrl/issues';
const String kSiteUrl = 'https://yusufx-sys.github.io/turkod-site/';
const String kEposta = 'yusuftndgn.2@gmail.com';
const String kKitapDosyasi = 'TurKod_ile_Kodlama_Macerasi.pdf';
const String kKitapAdi = 'TürKod ile Kodlama Macerası';

/// Kurulumda belgeler, programın yanındaki "belgeler" klasöründedir
/// (build_release.ps1 kopyalar). Geliştirme sırasında exe derleme
/// klasöründe çalıştığından üst klasörlerde de aranır.
@visibleForTesting
String? belgeYolu(String ad, {String? baslangic}) {
  var dizin = baslangic ?? p.dirname(Platform.resolvedExecutable);
  for (var i = 0; i < 9; i++) {
    final aday = p.join(dizin, 'belgeler', ad);
    if (File(aday).existsSync()) return aday;
    final ust = p.dirname(dizin);
    if (ust == dizin) break;
    dizin = ust;
  }
  return null;
}

/// Bağlantıyı, e-postayı (mailto:) ya da dosyayı Windows'un varsayılan
/// uygulamasıyla açar (tarayıcı, e-posta istemcisi, PDF okuyucu).
Future<bool> disaridaAc(String hedef) async {
  try {
    if (Platform.isWindows) {
      // cmd "start" yerine: & ve boşluk içeren yollar/bağlantılar bölünmez.
      await Process.start('rundll32', ['url.dll,FileProtocolHandler', hedef],
          mode: ProcessStartMode.detached);
    } else if (Platform.isMacOS) {
      await Process.start('open', [hedef], mode: ProcessStartMode.detached);
    } else {
      await Process.start('xdg-open', [hedef], mode: ProcessStartMode.detached);
    }
    return true;
  } catch (_) {
    return false;
  }
}

void _bildir(BuildContext context, String mesaj) {
  if (!context.mounted) return;
  ScaffoldMessenger.maybeOf(context)
      ?.showSnackBar(SnackBar(content: Text(mesaj)));
}

Future<void> baglantiAc(BuildContext context, String url) async {
  if (!await disaridaAc(url) && context.mounted) {
    _bildir(context, 'Açılamadı: $url');
  }
}

Future<void> epostaYaz(BuildContext context) async {
  final konu = Uri.encodeComponent('TürKod IDE hakkında');
  if (!await disaridaAc('mailto:$kEposta?subject=$konu') && context.mounted) {
    _bildir(context, 'E-posta uygulaması açılamadı. Adres: $kEposta');
  }
}

/// Programla gelen kitabı açar; bulunamazsa dokümantasyon sitesine yönlendirir.
Future<void> kitabiAc(BuildContext context) async {
  final yol = belgeYolu(kKitapDosyasi);
  if (yol != null && await disaridaAc(yol)) return;
  if (!context.mounted) return;
  _bildir(context,
      '$kKitapAdi kitabı bulunamadı; dokümantasyon sitesi açılıyor.');
  await disaridaAc(kSiteUrl);
}

const String _kMitMetni = """MIT License

Copyright (c) 2026 Yusuf Tandoğan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""";

String _belgeOku(String ad, String yedek) {
  final yol = belgeYolu(ad);
  if (yol == null) return yedek;
  try {
    var metin = File(yol).readAsStringSync();
    if (metin.startsWith('\uFEFF')) metin = metin.substring(1);
    return metin.replaceAll('\r\n', '\n').trim();
  } catch (_) {
    return yedek;
  }
}

bool _lisanslarKayitli = false;

/// Python tarafı bileşenlerin listesini Flutter'ın (gelişmiş) lisans
/// sayfasına ekler; Flutter/Dart paketleri zaten oradadır.
void lisanslariKaydet() {
  if (_lisanslarKayitli) return;
  _lisanslarKayitli = true;
  LicenseRegistry.addLicense(() async* {
    final metin = _belgeOku('UCUNCU_TARAF_LISANSLARI.txt', '');
    if (metin.isNotEmpty) {
      yield LicenseEntryWithLineBreaks(
          ['Python çalışma zamanı ve backend paketleri'], metin);
    }
  });
}

/// Yardım -> Lisanslar: yalnızca TürKod IDE'nin lisansı. Eskiden Flutter'ın
/// lisans sayfası açılıyor, kullanıcı yüzlerce İngilizce bileşen lisansı
/// (abseil-cpp, angle, ...) arasında kayboluyordu. Bileşen lisansları
/// (açık kaynak lisanslarının gereği olarak) küçük bir bağlantıyla erişilebilir
/// kalır.
void lisanslariGoster(BuildContext context) {
  final lisans = _belgeOku('LISANS.txt', _kMitMetni);
  showDialog<void>(
    context: context,
    builder: (dc) {
      final tema = Theme.of(dc);
      return AlertDialog(
        title: const Text('TürKod IDE Lisansı'),
        content: SizedBox(
          width: 560,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'TürKod IDE ücretsiz ve açık kaynaklıdır (MIT Lisansı). '
                'Programı kullanabilir, kopyalayabilir, değiştirebilir ve '
                'paylaşabilirsiniz; tek koşul bu lisans metnini korumaktır. '
                'Program "olduğu gibi", garantisiz sunulur.',
                style: TextStyle(fontSize: 13),
              ),
              const SizedBox(height: 12),
              Flexible(
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: tema.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: SingleChildScrollView(
                    child: SelectableText(lisans,
                        style: const TextStyle(fontSize: 11.5, height: 1.35)),
                  ),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              lisanslariKaydet();
              showLicensePage(
                context: dc,
                applicationName: 'TürKod IDE',
                applicationLegalese: '© 2026 Yusuf Tandoğan — MIT Lisansı',
              );
            },
            child: Text('Diğer açık kaynak lisansları',
                style: TextStyle(
                    fontSize: 12,
                    color: tema.colorScheme.onSurface.withOpacity(0.6))),
          ),
          FilledButton(
              onPressed: () => Navigator.pop(dc), child: const Text('Kapat')),
        ],
      );
    },
  );
}

/// Hakkında penceresindeki bağlantı düğmeleri.
class YardimBaglantilari extends StatelessWidget {
  const YardimBaglantilari({super.key});

  @override
  Widget build(BuildContext context) {
    Widget dugme(IconData ikon, String etiket, VoidCallback f) => TextButton.icon(
          onPressed: f,
          icon: Icon(ikon, size: 16),
          label: Text(etiket, style: const TextStyle(fontSize: 12)),
        );
    return Wrap(spacing: 4, runSpacing: 0, children: [
      dugme(Icons.menu_book_outlined, 'Kitap', () => kitabiAc(context)),
      dugme(Icons.public, 'Dokümantasyon', () => baglantiAc(context, kSiteUrl)),
      dugme(Icons.code, 'GitHub', () => baglantiAc(context, kGithubUrl)),
      dugme(Icons.bug_report_outlined, 'Hata bildir',
          () => baglantiAc(context, kHataBildirUrl)),
      dugme(Icons.mail_outline, kEposta, () => epostaYaz(context)),
      dugme(Icons.gavel_outlined, 'Lisanslar', () => lisanslariGoster(context)),
    ]);
  }
}
