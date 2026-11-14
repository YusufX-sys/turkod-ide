// Kodi'nin programı yönetmesi: menü komutları, eklentiler, ayarlar, yapay
// zekâ görev atamaları ve Ayarlar'ın bölümleri. Kodi bunları yalnızca
// kullanıcı isteyince yapar; neleri yapabileceği Ayarlar → Kodi bölümündeki
// yetkilerle belirlenir ve o yetkileri yalnızca kullanıcı değiştirebilir.
part of 'main.dart';

const String kKodiYetkiAyar = 'kodi_yetki_ayar';
const String kKodiYetkiEklenti = 'kodi_yetki_eklenti';
const String kKodiYetkiKomut = 'kodi_yetki_komut';
const String kKodiHepSor = 'kodi_hep_sor';
const String kKodiSohbetKaydet = 'kodi_sohbet_kaydet';
const String kKodiHafiza = 'kodi_hafiza';
const String kKodiGoruntu = 'kodi_goruntu';
const String kKodiYetkiTarayici = 'kodi_yetki_tarayici';

/// Ayarlar → Kodi → "Hafızayı yönet": Kodi'nin hatırladıkları, tek tek ya da
/// hepsi birden silinir.
Future<void> kodiHafizaPenceresi(BuildContext context) async {
  final backend = context.read<BackendService>();
  List<Map<String, dynamic>> notlar = [];
  String? hata;
  Future<void> yukle([Map<String, dynamic>? r]) async {
    try {
      r ??= await backend.call('kodi_hafiza');
      notlar = [
        for (final n in (r['notlar'] as List? ?? const []))
          if (n is Map) Map<String, dynamic>.from(n)
      ];
      hata = null;
    } catch (e) {
      hata = '$e';
    }
  }

  await yukle();
  if (!context.mounted) return;
  await showDialog<void>(
    context: context,
    builder: (dc) => StatefulBuilder(
      builder: (dc, yenile) {
        Future<void> sil({String? metin, bool hepsi = false}) async {
          try {
            final r = await backend.call('kodi_hafiza_sil', {'metin': metin, 'hepsi': hepsi});
            await yukle(r);
          } catch (e) {
            hata = '$e';
          }
          yenile(() {});
        }

        return AlertDialog(
          title: const Text('Kodi\'nin hafızası'),
          content: SizedBox(
            width: 440,
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              Text(
                'Kodi senin hakkında yalnızca bunları hatırlıyor. Şifre, adres, telefon gibi '
                'özel bilgileri hiç hatırlamaz.',
                style: Theme.of(dc).textTheme.bodySmall,
              ),
              const SizedBox(height: 8),
              if (hata != null) Text('Okunamadı: $hata'),
              if (notlar.isEmpty && hata == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Kodi henüz hiçbir şey hatırlamıyor.'),
                ),
              Flexible(
                child: ListView(shrinkWrap: true, children: [
                  for (final n in notlar)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.lightbulb_outline, size: 18),
                      title: Text('${n['metin']}'),
                      subtitle: n['tarih'] == null ? null : Text('${n['tarih']}'),
                      trailing: IconButton(
                        tooltip: 'Unut',
                        icon: const Icon(Icons.delete_outline, size: 18),
                        onPressed: () => sil(metin: '${n['metin']}'),
                      ),
                    ),
                ]),
              ),
            ]),
          ),
          actions: [
            if (notlar.isNotEmpty)
              TextButton(onPressed: () => sil(hepsi: true), child: const Text('Hepsini unut')),
            FilledButton(onPressed: () => Navigator.pop(dc), child: const Text('Kapat')),
          ],
        );
      },
    ),
  );
}

/// Kodi'nin hiçbir zaman değiştiremeyeceği ayarlar (kendi yetkileri, API
/// anahtarları, kısayollar).
const List<String> kKodiYasakAyarOnekleri = [
  'kodi_yetki',
  kKodiHepSor,
  'kodi_hafiza',
  'kodi_sohbet',
  'ai_api',
  'kisayollar',
];

/// Kodi'nin çalıştırmadığı komutlar: kendini çağırmak ve yalnızca editörde
/// klavyeyle anlamı olan ayrıntılar (kes, kopyala, imleç ekle, hata ayıklama
/// adımları). Yapay zekâya da gönderilmezler (istek küçük kalsın).
const Set<String> kKodiYasakKomutlar = {
  'help.kodi',
  'edit.cut',
  'edit.copy',
  'edit.paste',
  'edit.select_all',
  'edit.cursor_below',
  'edit.cursor_above',
  'edit.select_next',
  'edit.select_all_matches',
  'edit.move_up',
  'edit.move_down',
  'edit.duplicate',
  'edit.comment',
  'edit.ai_complete',
  'view.tab_left',
  'view.tab_right',
  'run.debug_step',
  'run.debug_step_into',
  'run.debug_step_out',
  'run.debug_run_to_cursor',
  'run.debug_continue',
  'run.debug_pause',
};

/// Ayarlar sayfasının bölümleri: kimlik -> kartın başlığı.
const Map<String, String> kAyarBolumleri = {
  'genel': 'Genel',
  'editor': 'Editör Görünümü',
  'terminal': 'Terminal',
  'tur': 'Arayüz Turu',
  'entegrasyon': 'Sistem Entegrasyonu',
  'kodi': 'Kodi',
  'ai_gorevler': 'Yapay Zekâ: Görevler',
  'ai_modeller': 'Yapay Zekâ: Modeller',
  'duzeltme': 'Düzeltme',
};

/// Kodi bir ayarı değiştirince artar: açık Ayarlar sayfası formunu yeniler
/// (yoksa "Kaydet ve Uygula" eski değeri geri yazardı).
final ValueNotifier<int> kodiAyarDegisti = ValueNotifier<int>(0);

/// Komut izin istemeden mi çalışır (yalnızca bir pencere, panel ya da sekme
/// açar)? Çalıştırma, kaydetme, kodu değiştirme gibi işler için sorulur.
bool kodiKomutuIzinsiz(String id) =>
    kKodiGuvenliKomutlar.contains(id) ||
    id.startsWith('view.') ||
    id.startsWith('learn.') ||
    id.startsWith('help.');

/// Kodi'nin değiştirebildiği bir ayar.
class KodiAyari {
  final String ad;

  /// bool | sayi | secim | metin
  final String tur;
  final num enAz;
  final num enCok;
  final bool ondalik;
  final List<num>? izinliSayilar;
  final List<String> Function()? secenekler;
  const KodiAyari(this.ad, this.tur,
      {this.enAz = 0,
      this.enCok = 0,
      this.ondalik = false,
      this.izinliSayilar,
      this.secenekler});

  /// Değeri ayarın türüne çevirir; olmuyorsa Kodi'nin söyleyeceği bir
  /// açıklama fırlatır.
  Object dogrula(Object? v) {
    switch (tur) {
      case 'bool':
        if (v is bool) return v;
        final s = '$v'.trim().toLowerCase();
        if (const {'true', 'evet', 'açık', 'acik', 'aç', 'ac', '1', 'on'}.contains(s)) {
          return true;
        }
        if (const {'false', 'hayır', 'hayir', 'kapalı', 'kapali', 'kapat', '0', 'off'}
            .contains(s)) {
          return false;
        }
        throw '"$ad" için açık ya da kapalı demelisin';
      case 'sayi':
        final n = v is num ? v : num.tryParse('$v'.trim().replaceAll(',', '.'));
        if (n == null) throw '"$ad" için bir sayı gerekiyor';
        if (izinliSayilar != null) {
          if (!izinliSayilar!.contains(n)) {
            throw '"$ad" yalnızca ${izinliSayilar!.join(', ')} olabilir';
          }
          return n.round();
        }
        final c = n.clamp(enAz, enCok);
        return ondalik ? c.toDouble() : c.round();
      case 'secim':
        final liste = secenekler?.call() ?? const <String>[];
        final s = '$v'.trim().toLowerCase();
        for (final x in liste) {
          if (x.toLowerCase() == s) return x;
        }
        throw '"$v" diye bir seçenek yok (${liste.join(', ')})';
      default:
        final s = '$v'.trim();
        if (s.isEmpty || s.length > 80) throw '"$ad" için geçerli bir değer ver';
        return s;
    }
  }

  /// Değerin kullanıcıya gösterilen hâli.
  String goster(Object? v) => v is bool ? (v ? 'açık' : 'kapalı') : '$v';

  Map<String, dynamic> json(Object? deger) => {
        'ad': ad,
        'tur': tur,
        'deger': deger,
        if (tur == 'secim') 'secenekler': secenekler?.call() ?? const <String>[],
        if (tur == 'sayi' && izinliSayilar != null) 'secenekler': izinliSayilar,
        if (tur == 'sayi') 'min': izinliSayilar?.first ?? enAz,
        if (tur == 'sayi') 'max': izinliSayilar?.last ?? enCok,
      };
}

/// Kodi'nin değiştirebildiği ayarlar (anahtar -> tanım). Yetkiler, API
/// anahtarları, sistem mesajı ve kısayollar burada yoktur.
final Map<String, KodiAyari> kKodiAyarlari = {
  'tema': KodiAyari('Tema', 'secim', secenekler: () => _SettingsPageState.temalar),
  'yazi_boyutu': const KodiAyari('Editör yazı boyutu', 'sayi', enAz: 8, enCok: 32),
  'terminal_yazi_boyutu':
      const KodiAyari('Terminal yazı boyutu', 'sayi', enAz: 8, enCok: 28),
  'yazi_tipi': const KodiAyari('Editör yazı tipi', 'metin'),
  'satir_numaralari': const KodiAyari('Satır numaraları', 'bool'),
  'kelime_sar': const KodiAyari('Kelime kaydırma', 'bool'),
  'bosluk_gostergesi': const KodiAyari('Boşluk göstergesi', 'bool'),
  'minimap': const KodiAyari('Mini harita', 'bool'),
  'sutun_cizgileri': const KodiAyari('Girinti kılavuzları', 'bool'),
  'girinti_boyutu':
      const KodiAyari('Girinti genişliği', 'sayi', izinliSayilar: [2, 4, 8]),
  'girinti_algila': const KodiAyari('Girintiyi dosyadan algıla', 'bool'),
  'kaydederken_bicimlendir': const KodiAyari('Kaydederken biçimlendir', 'bool'),
  'otomatik_tamamlama': const KodiAyari('Otomatik tamamlama (öneri listesi)', 'bool'),
  'otomatik_kaydetme': const KodiAyari('Otomatik kaydetme', 'bool'),
  'otomatik_kaydetme_aralik':
      const KodiAyari('Otomatik kaydetme aralığı (saniye)', 'sayi', enAz: 5, enCok: 600),
  'ai_tamamlama_cok_satir': const KodiAyari('Çok satırlı hayalet kod', 'bool'),
  'ai_tamamlama_gecikme':
      const KodiAyari('Hayalet kod gecikmesi (milisaniye)', 'sayi', enAz: 100, enCok: 1500),
  'ai_dusunme': const KodiAyari('Yapay zekâ modelleri düşünsün', 'bool'),
  'ai_sicaklik': const KodiAyari('Yapay zekâ sıcaklığı (yaratıcılık)', 'sayi',
      enAz: 0, enCok: 2, ondalik: true),
  'ai_max_token':
      const KodiAyari('Yapay zekâ en fazla token', 'sayi', enAz: 64, enCok: 32768),
  'kodi_dusunme': const KodiAyari('Kodi düşünsün', 'bool'),
  'kodi_sesli': const KodiAyari('Kodi cevaplarını sesli okusun', 'bool'),
  kTurHerAcilista: const KodiAyari('Arayüz turu her açılışta gösterilsin', 'bool'),
};

bool kodiYetkisiVar(SettingsProvider s, String anahtar) =>
    s.getBool(anahtar, fallback: true);

/// İşe Ayarlar → Kodi'de izin verilmemişse nedeni; izin varsa null.
String? kodiYetkiEngeli(SettingsProvider s, KodiEylemi e) {
  const yer = 'Ayarlar → Kodi bölümünden açabilirsin';
  switch (e.tur) {
    case 'ayar':
      final ad = '${e.veri['ad']}';
      if (kKodiYasakAyarOnekleri.any(ad.startsWith)) {
        return 'Bu ayarı yalnızca sen değiştirebilirsin';
      }
      if (!kodiYetkisiVar(s, kKodiYetkiAyar)) {
        return 'Ayarları değiştirmeme izin verilmemiş; $yer';
      }
    case 'model_ata':
      if (!kodiYetkisiVar(s, kKodiYetkiAyar)) {
        return 'Ayarları değiştirmeme izin verilmemiş; $yer';
      }
    case 'eklenti':
      if (!kodiYetkisiVar(s, kKodiYetkiEklenti)) {
        return 'Eklentileri yönetmeme izin verilmemiş; $yer';
      }
    case 'tarayici':
      if (!kodiYetkisiVar(s, kKodiYetkiTarayici)) {
        return 'Tarayıcıyı yönetmeme izin verilmemiş; $yer';
      }
    case 'komut':
      if (kKodiYasakKomutlar.contains('${e.veri['id']}')) return 'Bu komutu çalıştıramam';
      if (!kodiYetkisiVar(s, kKodiYetkiKomut)) {
        return 'Program komutlarını çalıştırmama izin verilmemiş; $yer';
      }
  }
  return null;
}

/// Kodi'ye gönderilen bağlamın yönetim kısmı: komutlar, eklentiler,
/// ayarlar, modeller ve yetkiler.
Map<String, dynamic> kodiYonetimBaglami(BuildContext context) {
  final s = context.read<SettingsProvider>();
  String atama(String gorev) {
    final a = s.gorevAtamasi(gorev);
    if (a != null) return s.atamaEtiketi(a);
    return gorev == 'kodi' ? 'Otomatik' : 'Kapalı';
  }

  return {
    'komutlar': [
      for (final a in buildAppActions())
        if (!kKodiYasakKomutlar.contains(a.id) && a.gorunur(context))
          {
            'id': a.id,
            'ad': a.label.isEmpty ? a.id : a.label,
            'izinsiz': kodiKomutuIzinsiz(a.id),
            // Gerçek (kullanıcının değiştirdiği) kısayol: Kodi kısayolları
            // ezberden uydurmasın.
            if (a.shortcut.isNotEmpty) 'kisayol': OzelKisayollar.goster(a.shortcut),
          }
    ],
    'eklentiler': [
      for (final x in kEklentiler)
        {
          'id': x.id,
          'ad': x.ad,
          'aciklama': x.aciklama,
          'etkin': s.eklentiYuklu(x.id),
          'acilir': x.ac != null,
        }
    ],
    'ayar_bolumleri': kAyarBolumleri,
    'ayarlar': {
      for (final g in kKodiAyarlari.entries) g.key: g.value.json(s.get<dynamic>(g.key))
    },
    'modeller': [for (final a in s.tumAiModelleri) s.atamaEtiketi(a)],
    'gorev_atamalari': {for (final g in kAiGorevleri.keys) g: atama(g)},
    'yetkiler': {
      'ayar': kodiYetkisiVar(s, kKodiYetkiAyar),
      'eklenti': kodiYetkisiVar(s, kKodiYetkiEklenti),
      'komut': kodiYetkisiVar(s, kKodiYetkiKomut),
      'tarayici': kodiYetkisiVar(s, kKodiYetkiTarayici),
      'hep_sor': s.getBool(kKodiHepSor),
    },
  };
}

/// Yönetim eylemleri (ayar, Ayarlar bölümü, eklenti, model, komut).
/// Uygulanmadıysa false döner (eylem başka bir türdür).
Future<bool> kodiYonetimEylemi(BuildContext context, KodiEylemi e) async {
  final s = context.read<SettingsProvider>();
  switch (e.tur) {
    case 'ayar':
      final ad = '${e.veri['ad']}';
      final a = kKodiAyarlari[ad];
      if (a == null) throw 'Bu ayarı değiştiremem';
      final deger = a.dogrula(e.veri['deger']);
      await s.setValue(ad, deger);
      kodiAyarDegisti.value++;
      e.sonuc = '${a.ad}: ${a.goster(deger)}';
      return true;
    case 'ayarlar_ac':
      final b = '${e.veri['bolum']}';
      if (!kAyarBolumleri.containsKey(b)) throw 'Ayarlar\'da böyle bir bölüm yok';
      ayarlarHedefi.value = b;
      context.read<EditorProvider>().openSettings();
      e.sonuc = 'Ayarlar açıldı: ${kAyarBolumleri[b]}';
      return true;
    case 'eklenti':
      final id = '${e.veri['id']}';
      final x = eklentiBul(id);
      if (x == null) throw '"$id" diye bir eklenti yok';
      switch ('${e.veri['durum']}') {
        case 'kapat':
          if (!s.eklentiYuklu(id)) {
            e.sonuc = '${x.ad} zaten kapalı';
          } else {
            await eklentiKaldir(context, id, bildir: false);
            // Eskiden kapatma olmasa da (hata) "devre dışı bırakıldı"
            // deniyordu: sonuç ayarlardan yeniden okunur.
            if (s.eklentiYuklu(id)) throw '${x.ad} eklentisini kapatamadım';
            e.sonuc = '${x.ad} devre dışı bırakıldı';
          }
        case 'calistir':
          if (!s.eklentiYuklu(id)) {
            await eklentiKur(context, id, bildir: false);
            if (!s.eklentiYuklu(id)) throw '${x.ad} eklentisini etkinleştiremedim';
          }
          if (!context.mounted) return true;
          if (x.ac == null) {
            e.sonuc = '${x.ad} etkin; ayrı bir penceresi yok';
          } else {
            x.ac!(context);
            e.sonuc = '${x.ad} açıldı';
          }
        default:
          if (s.eklentiYuklu(id)) {
            e.sonuc = '${x.ad} zaten etkin';
          } else {
            await eklentiKur(context, id, bildir: false);
            if (!s.eklentiYuklu(id)) throw '${x.ad} eklentisini etkinleştiremedim';
            e.sonuc = '${x.ad} etkinleştirildi';
          }
      }
      return true;
    case 'model_ata':
      final g = '${e.veri['gorev']}';
      if (!kAiGorevleri.containsKey(g)) throw 'Böyle bir yapay zekâ görevi yok';
      final m = '${e.veri['model']}'.trim();
      final k = m.toLowerCase();
      AiAtama? atama;
      if (!const {'otomatik', 'kapali', 'kapalı', 'yok'}.contains(k)) {
        for (final a in s.tumAiModelleri) {
          if (s.atamaEtiketi(a).toLowerCase() == k || a.model.toLowerCase() == k) {
            atama = a;
            break;
          }
        }
        if (atama == null) {
          throw '"$m" diye bir model bulamadım; önce Ayarlar → Yapay Zekâ: '
              'Modeller\'den eklemelisin';
        }
      }
      await s.gorevAta(g, atama);
      kodiAyarDegisti.value++;
      e.sonuc = '${kAiGorevleri[g]}: '
          '${atama == null ? (g == 'kodi' ? 'Otomatik' : 'Kapalı') : s.atamaEtiketi(atama)}';
      return true;
    case 'komut':
      final kimlik = '${e.veri['id']}';
      if (kKodiKodIsteyenKomutlar.contains(kimlik) && !kodiKodSekmesiVar(context)) {
        throw 'Önce bir kod dosyası açmalısın';
      }
      final a = findAction(buildAppActions(), kimlik);
      if (a == null) throw 'Bu komut bulunamadı';
      a.run(context);
      e.sonuc = 'Komut çalıştı: ${a.label.isEmpty ? kimlik : a.label}';
      return true;
    case 'rehber':
      kodiKurulumRehberi(context);
      e.sonuc = 'Kurulum rehberi açıldı';
      return true;
    case 'tarayici':
      e.sonuc = await kodiTarayiciEylemi(context, e);
      return true;
  }
  return false;
}

/// Kodi'nin tarayıcıda yaptığı işler. Tarayıcı sekmesi açılır, Kodi imleci
/// öğeye gidip tıklar ya da yazar. "devam": sayfa açılınca Kodi yeni sayfayı
/// görüp işine kendisi devam eder (iş bitene kadar).
Future<String> kodiTarayiciEylemi(BuildContext context, KodiEylemi e) async {
  final ed = context.read<EditorProvider>();
  final kodi = context.read<KodiProvider>();
  final t = kTarayici;
  ed.openBrowser();
  await t.baslat();
  if (!t.hazir) throw t.hata ?? 'Tarayıcı açılamadı';
  await t.uyandir();
  final v = e.veri;
  int no() => int.tryParse('${v['no']}') ?? (throw 'Hangi öğe olduğunu bilmiyorum');
  final String sonuc;
  switch ('${v['islem']}') {
    case 'ac':
      await t.git('${v['adres']}');
      sonuc = 'Açıldı: ${v['adres']}';
    case 'ara':
      await t.git('${v['sorgu']}');
      sonuc = 'Google\'da arandı: ${v['sorgu']}';
    case 'tikla':
      // Numara yoksa (öğe listede değil) yazısıyla bulunup tıklanır.
      sonuc = v['no'] == null && '${v['bul'] ?? ''}'.isNotEmpty
          ? await t.yazisiylaTikla('${v['bul']}')
          : await t.tikla(no());
    case 'yaz':
      sonuc = await t.yaz(no(), '${v['metin'] ?? ''}', gonder: v['gonder'] == true);
    case 'kaydir':
      await t.kaydir('${v['yon']}' != 'yukari');
      sonuc = '${v['yon']}' == 'yukari' ? 'Yukarı kaydırıldı' : 'Aşağı kaydırıldı';
    case 'geri':
      await t.geri();
      sonuc = 'Geri gidildi';
    case 'ileri':
      await t.ileri();
      sonuc = 'İleri gidildi';
    case 'yenile':
      await t.yenile();
      sonuc = 'Yenilendi';
    default:
      throw 'Tarayıcıda bunu yapamam';
  }
  if (v['devam'] == true) {
    if (kodi.masaustunde) {
      // Kodi masaüstünde: sayfa burada okunur, Kodi kendi penceresinde
      // (eylemin sonucu ona ulaşınca) devam eder.
      await t.yuklenmeyiBekle();
      await t.sayfayiOku();
    } else {
      // Eylem kartı önce "yapıldı" olsun, sonra Kodi devam etsin.
      Future<void>.delayed(const Duration(milliseconds: 200), kodi.otomatikDevam);
    }
  }
  return sonuc;
}
