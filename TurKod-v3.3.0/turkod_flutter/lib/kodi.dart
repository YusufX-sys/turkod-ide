// Kodi: kitaptaki sevimli robot programın içinde. Sol şeritteki Kodi
// düğmesiyle (ya da Yardım → Kodi ile Konuş) çalışma alanının köşesine
// kayarak gelir, aynı düğmeyle kayarak gider; basılı tutulup sürüklenerek
// istenen yere taşınır. Konuşma balonundaki yazılar harf harf çıkar. Sorular
// Ayarlar'da "Kodi" görevine atanan yapay zekâyla cevaplanır; Kodi panelleri
// ve dosyaları açabilir, kod yazabilir, komut çalıştırabilir (güvenli
// olmayan işler için kullanıcıdan izin ister).

part of 'main.dart';

const String kKodiSelam = 'Merhaba, ben Kodi!';

/// Kayıtlı sohbet yeniden açılınca Kodi'nin karşılaması (kaydedilmez:
/// eskiden her açılışta bir tane daha birikiyordu).
const String kKodiTekrarHosGeldin = 'Tekrar hoş geldin! Kaldığımız yerden devam edebiliriz.';

enum KodiIfadesi { mutlu, konusuyor, dusunceli, uzgun, dinliyor }

/// Ancak açık bir kod dosyasıyla anlamı olan komutlar (PDF ya da Ayarlar
/// sekmesindeyken "çalıştı" denip hiçbir şey olmuyordu).
const Set<String> kKodiKodIsteyenKomutlar = {
  'run.run',
  'run.debug_start',
  'run.exe',
  'file.save',
  'edit.format',
  'edit.find_replace',
  'tools.fix',
  'tools.convert',
  'tools.stats',
  'tools.todo',
};

/// Selamdan sonra balonda görünen hazır sorular.
const List<String> kKodiHazirSorular = [
  'Kodumu açıklar mısın?',
  'Hatamı bulur musun?',
  'Birlikte bir oyun yazalım!',
  'Kitapta döngüler nerede?',
];

/// Kodi'nin izin istemeden çalıştırabildiği komutlar (yalnızca bir pencere,
/// panel ya da sekme açarlar). Diğerleri (çalıştır, kaydet, biçimlendir ...)
/// için kullanıcıya sorulur.
const Set<String> kKodiGuvenliKomutlar = {
  'file.new_tab',
  'file.open_file',
  'file.recent',
  'file.open',
  'edit.goto_line',
  'edit.find',
  'tools.codesearch',
  'tools.snippets',
  'run.exe',
  'run.exe_kaynak',
  'run.args',
  'update.check',
  'edit.find_replace',
  'edit.find_in_files',
  'tools.stats',
  'tools.todo',
  'tools.shell',
  'tools.local_models',
  'view.split',
  'view.panel_swap',
  'view.panel_reset',
  'view.palette',
  'view.settings',
  'view.problems',
  'view.extensions',
  'view.keybindings',
  'learn.book',
  'help.tour',
};

/// Kodi'nin cevabındaki bir iş: panel aç, dosya aç, sekmeye geç, kod yaz,
/// komut çalıştır. Arka uç doğrular; arayüz uygular.
class KodiEylemi {
  final String tur;
  final Map<String, dynamic> veri;

  /// bekliyor | calisiyor | yapildi | reddedildi | hata. calisiyor: iş
  /// yapılırken (düğmeler kapanır; eskiden ikinci tıklama işi yeniden
  /// yapıyordu, "Vazgeç" de yarıda kalmış gibi görünüp iş yine bitiyordu).
  String durum = 'bekliyor';
  String? sonuc;
  KodiEylemi(this.tur, this.veri);

  factory KodiEylemi.jsondan(Map<String, dynamic> m) =>
      KodiEylemi((m['eylem'] ?? '').toString(), m);

  /// İzin istemeden yapılabilir mi?
  bool get guvenli => guvenliMi(false);

  /// hepSor: kullanıcı Ayarlar → Kodi'de "her işten önce izin istesin" dedi.
  bool guvenliMi(bool hepSor) =>
      !hepSor &&
      (tur == 'panel' ||
          tur == 'dosya_ac' ||
          tur == 'sekme' ||
          tur == 'satira_git' ||
          tur == 'ara' ||
          tur == 'kitap' ||
          tur == 'ayar' ||
          tur == 'ayarlar_ac' ||
          tur == 'eklenti' ||
          tur == 'model_ata' ||
          tur == 'hatirla' ||
          tur == 'unut' ||
          tur == 'rehber' ||
          // Tarayıcı: satın alma, ödeme, silme gibi düğmelerde önce sorulur.
          (tur == 'tarayici' && veri['riskli'] != true) ||
          (tur == 'komut' && kodiKomutuIzinsiz('${veri['id']}')));

  /// İzin kartında sorulan soru (kod yazma dışındaki işler).
  String get izinSorusu {
    final etiket = veri['etiket'] ?? veri['id'] ?? '';
    switch (tur) {
      case 'komut':
        return '**$etiket** komutunu çalıştırayım mı?';
      case 'eklenti':
        return switch ('${veri['durum']}') {
          'kapat' => '**$etiket** eklentisini kapatayım mı?',
          'calistir' => '**$etiket** eklentisini açayım mı?',
          _ => '**$etiket** eklentisini etkinleştireyim mi?',
        };
      case 'ayar':
        final a = kKodiAyarlari['${veri['ad']}'];
        final d = veri['deger'];
        return '**${a?.ad ?? etiket}** ayarını **${a?.goster(d) ?? d}** yapayım mı?';
      case 'model_ata':
        return '**${kAiGorevleri[veri['gorev']] ?? veri['gorev']}** görevine '
            '**${veri['model']}** atayayım mı?';
      case 'ayarlar_ac':
        return 'Ayarlar\'da **${kAyarBolumleri[veri['bolum']] ?? veri['bolum']}** '
            'bölümünü açayım mı?';
      case 'tarayici':
        return switch ('${veri['islem']}') {
          'tikla' => 'Tarayıcıda **"${veri['etiket'] ?? veri['no']}"** düğmesine basayım mı?',
          'yaz' => 'Tarayıcıda **"${veri['etiket'] ?? veri['no']}"** kutusuna '
              '"${veri['metin']}" yazayım mı?',
          'ac' => '**${veri['adres']}** sitesini açayım mı?',
          'ara' => 'Google\'da **"${veri['sorgu']}"** arayayım mı?',
          _ => 'Tarayıcıda bunu yapayım mı?',
        };
      case 'rehber':
        return 'API kurulum rehberini açayım mı?';
      case 'panel':
        return '**${_kKodiPanelAdlari[veri['panel']] ?? veri['panel']}** panelini '
            '${veri['durum'] == 'kapat' ? 'kapatayım' : 'açayım'} mı?';
      case 'dosya_ac':
        return '**${veri['dosya']}** dosyasını açayım mı?';
      case 'sekme':
        return '**${veri['ad']}** sekmesine geçeyim mi?';
      case 'satira_git':
        return '**${veri['satir']}.** satıra gideyim mi?';
      case 'ara':
        return '"${veri['metin']}" ifadesini arayayım mı?';
      case 'kitap':
        return 'Kitabı **${veri['sayfa']}.** sayfada açayım mı?';
    }
    return 'Bunu yapayım mı?';
  }

  String get kod => (veri['kod'] ?? '').toString();

  Map<String, dynamic> json() => {...veri, 'eylem': tur, '_durum': durum, '_sonuc': sonuc};

  static KodiEylemi jsondanTam(Map<String, dynamic> m) {
    final e = KodiEylemi((m['eylem'] ?? '').toString(),
        Map<String, dynamic>.from(m)..remove('_durum')..remove('_sonuc'));
    e.durum = (m['_durum'] ?? 'bekliyor').toString();
    e.sonuc = m['_sonuc']?.toString();
    return e;
  }
}

class KodiMesaji {
  final bool kodiden;
  final String metin;
  final bool hata;

  /// Ayarlar'a gitme düğmesi gösterilsin mi (model atanmamış).
  final bool ayarDugmesi;

  /// Harf harf yazılacak mı (açılıştaki selam ve cevaplar).
  final bool yazilsin;
  final int harfMs;
  final List<KodiEylemi> eylemler;

  /// Kullanıcı mesajıyla giden görüntünün durumu: gitti | desteklenmiyor |
  /// alinamadi (null: görüntü kapalı).
  String? goruntu;

  /// Kodi'nin kendi başına sürdürdüğü adım ("Sayfa açıldı, devam ediyorum").
  final bool otomatik;

  /// Güvenli işleri başlatıldı mı (bir kez başlatılır; balon da sağlayıcı
  /// da başlatabilir, iş iki kez yapılmaz)?
  bool eylemlerBasladi = false;

  /// Sohbet öbür pencereye geçti: buradaki kopyanın işlerini o yapar.
  bool devredildi = false;
  KodiMesaji(this.kodiden, this.metin,
      {this.hata = false,
      this.ayarDugmesi = false,
      this.yazilsin = true,
      this.harfMs = 14,
      this.goruntu,
      this.otomatik = false,
      List<KodiEylemi>? eylemler})
      : eylemler = eylemler ?? [];

  Map<String, dynamic> json() => {
        'kodiden': kodiden,
        'metin': metin,
        'hata': hata,
        'ayar': ayarDugmesi,
        if (goruntu != null) 'goruntu': goruntu,
        if (otomatik) 'otomatik': true,
        'eylemler': [for (final e in eylemler) e.json()],
      };

  /// Pencereler arasında taşınan mesaj yeniden yazılmaz (harf harf değil).
  static KodiMesaji jsondan(Map<String, dynamic> m) => KodiMesaji(
        m['kodiden'] == true,
        (m['metin'] ?? '').toString(),
        hata: m['hata'] == true,
        ayarDugmesi: m['ayar'] == true,
        yazilsin: false,
        goruntu: m['goruntu']?.toString(),
        otomatik: m['otomatik'] == true,
        eylemler: [
          for (final e in (m['eylemler'] as List?) ?? const [])
            if (e is Map) KodiEylemi.jsondanTam(Map<String, dynamic>.from(e)),
        ],
      );
}

/// Masaüstü Kodi penceresinin Windows tarafı (sürükleme, tıklanabilir alan).
const kodiPenceresiKanali = MethodChannel('turkod/kodi_penceresi');

/// Kodi'nin sohbeti ve görünürlüğü. Uygulama boyunca yaşar: paneller yer
/// değiştirince ya da Kodi gidip gelince sohbet kaybolmaz.
class KodiProvider extends ChangeNotifier {
  final BackendService _backend;

  /// Masaüstü Kodi penceresinde mi (TürKod'un ikinci penceresi)?
  final bool pencereKipi;
  KodiProvider(this._backend, {this.pencereKipi = false});

  bool acik = false;
  bool bekliyor = false;
  final List<KodiMesaji> mesajlar = [];

  /// Mikrofonu dinliyor / cevabı sesli okuyor / canlı (eller serbest) sohbet.
  bool dinliyor = false;
  bool konusuyor = false;
  bool canli = false;

  /// Kodi TürKod penceresinin dışında, masaüstünde mi?
  bool masaustunde = false;
  bool masaustuneCikiyor = false;

  /// Kullanıcı Ayarlar → Kodi'de "her işten önce izin istesin" dedi mi?
  bool hepSor = false;

  /// KodiKatmani kurar (ana pencerede): bağlam, ayarlar ve eylemler.
  Map<String, dynamic> Function()? baglamUret;
  bool Function()? dusunmeOku;
  bool Function()? sesliOku;
  Future<void> Function(KodiEylemi e, {String? hedef})? eylemUygula;
  VoidCallback? ayarlarAc;
  Future<void> Function()? ayarlariYenile;

  /// Masaüstü penceresinde: son bağlamdaki etkin sekme bir kod dosyası mı?
  bool uzakKodSekmesiVar = false;

  // --------------------------------------------------------------- köprü
  // Ana pencere ile masaüstü Kodi penceresi TürKod motoru üzerinden konuşur:
  // pencere bağlamı ister, işleri ana pencereye yaptırır; sohbet gidip
  // gelirken taşınır.
  StreamSubscription<BackendEvent>? _kopruOlay;
  int _kopruNo = 0;
  final Map<int, Completer<Map<String, dynamic>>> _kopruBekleyen = {};
  Timer? _donusZamanlayici;
  Timer? _cikisZamanlayici;

  // Masaüstü penceresi önceden, gizli olarak hazırlanır: Flutter'ın ikinci
  // süreçte açılması birkaç saniye sürdüğü için "Masaüstüne çık" denince
  // hazır pencere anında görünür. (Ana pencerede.)
  bool _hazirPencere = false;
  bool _pencereHazirlaniyor = false;
  Timer? _hazirlamaZamanlayici;
  Map<String, dynamic>? _bekleyenGosterme;

  // Sohbetler paneli: kayıtlı sohbetler (en yeni başta).
  bool sohbetlerAcik = false;
  List<Map<String, dynamic>> sohbetListesi = [];
  bool sohbetlerYukleniyor = false;

  Future<void> sohbetlerDegistir() async {
    sohbetlerAcik = !sohbetlerAcik;
    notifyListeners();
    if (sohbetlerAcik) await sohbetleriYukle();
  }

  Future<void> sohbetleriYukle() async {
    // Önce şu anki sohbet kaydedilsin (listede güncel görünsün).
    await sohbetiKaydet(zorla: true);
    sohbetlerYukleniyor = true;
    notifyListeners();
    try {
      final r = await _backend.call('kodi_sohbetler');
      sohbetListesi = [
        for (final s in (r['sohbetler'] as List?) ?? const [])
          if (s is Map) Map<String, dynamic>.from(s)
      ];
    } catch (_) {}
    sohbetlerYukleniyor = false;
    notifyListeners();
  }

  /// Panelden bir sohbet açılır; şu anki sohbet kaydedilip yerine o gelir.
  Future<void> sohbetAc(String no) async {
    if (bekliyor) return;
    await sohbetiKaydet(zorla: true);
    try {
      final r = await _backend.call('kodi_sohbet_yukle', {'no': no});
      if (r['ok'] != true) return;
      _sohbetiAl(r['mesajlar']);
      for (final m in mesajlar) {
        for (final e in m.eylemler) {
          if (e.durum == 'bekliyor' || e.durum == 'calisiyor') {
            e.durum = 'reddedildi';
            e.sonuc = 'Bu iş yapılmadı';
          }
        }
      }
      _sonKayit = jsonEncode(_sohbet);
      sohbetlerAcik = false;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> sohbetSil(String no) async {
    final etkin = sohbetListesi.any((s) => s['no'] == no && s['etkin'] == true);
    try {
      final r = await _backend.call('kodi_sohbet_sil', {'no': no});
      sohbetListesi = [
        for (final s in (r['sohbetler'] as List?) ?? const [])
          if (s is Map) Map<String, dynamic>.from(s)
      ];
    } catch (_) {}
    if (etkin) _yeniSayfa();
    notifyListeners();
  }

  /// Bütün sohbetleri siler (Ayarlar → Kodi).
  Future<void> tumSohbetleriSil() async {
    try {
      await _backend.call('kodi_sohbet_sil', {'hepsi': true});
    } catch (_) {}
    sohbetListesi = [];
    _yeniSayfa();
    notifyListeners();
  }

  /// Yeni sohbet sayfası: Kodi baştan selam verir ("Merhaba, ben Kodi!", sonra
  /// yardım cümlesi). [selamla] false ise selam, Kodi yerine varınca verilir.
  void _yeniSayfa({bool selamla = true}) {
    mesajlar.clear();
    _selamVerildi = false;
    if (selamla && acik) selamVer();
    _sonKayit = jsonEncode(_sohbet);
  }

  /// Kodi kapatılıp yeniden çağrılınca: o anki sohbet kaydedilir (Sohbetler
  /// panelinde kalır), Kodi yeni sohbetle gelir.
  void _yeniSohbeteGec() {
    if (pencereKipi || bekliyor) return;
    if (mesajlar.isEmpty) return;
    final eski = mesajlar.any((m) => !m.kodiden);
    final kaydet = eski ? sohbetiKaydet(zorla: true) : Future<void>.value();
    _yeniSayfa(selamla: false);
    sohbetlerAcik = false;
    // Motor tarafında da yeni sohbet: eski kayıt yazıldıktan sonra.
    kaydet.whenComplete(() => _backend.call('kodi_temizle').catchError((_) => <String, dynamic>{}));
  }

  /// KodiKatmani kurar (ana pencerede): API kurulum rehberini açar.
  VoidCallback? rehberAcici;

  /// API kurulum rehberi: tarayıcıda anahtar sayfası ve yanında adımlar.
  void rehberiAc() {
    if (pencereKipi) {
      _kopruGonder({'tur': 'rehber'});
      kodiPenceresiKanali.invokeMethod('anaPencereyiOneGetir').catchError((_) => null);
      return;
    }
    rehberAcici?.call();
  }

  /// Kurulum rehberi bitti: Kodi sevinir, sohbete geçer. Kodi kapalıysa bu
  /// cümle, çağrılınca selamdan sonra gelir.
  String? _bekleyenKurulum;
  void kurulumBitti(String model) {
    if (!acik) {
      _bekleyenKurulum = model;
      return;
    }
    mesajlar.add(_kurulumMesaji(model));
    notifyListeners();
  }

  KodiMesaji _kurulumMesaji(String model) => KodiMesaji(true,
      'Yaşasın, beynim hazır! Artık **$model** ile konuşuyorum. Hadi bana ilk sorunu sor!',
      harfMs: 30);

  /// Kodi'nin kendi başına sürdürdüğü tarayıcı adımları. Kodi iş bitene
  /// kadar sürdürür (eskiden 3 adımda kesiliyordu: "bir oyun aç" arama
  /// sonuçlarında kalıyordu); bu sınır yalnızca bir sayfada takılıp sonsuza
  /// dek dönmesine karşıdır.
  int _otomatikAdim = 0;
  static const int enFazlaOtomatikAdim = 12;

  /// Tarayıcıda sayfa açıldı: Kodi yeni sayfayı görüp işine devam eder.
  /// Masaüstündeki Kodi de devam eder (eskiden masaüstündeyken tarayıcı
  /// işi ilk adımda kalıyordu): sayfayı ana pencere okur, soruyu masaüstü
  /// penceresi sorar.
  Future<void> otomatikDevam() async {
    if (!_devamEdebilir() || _otomatikAdim >= enFazlaOtomatikAdim) return;
    _otomatikAdim++;
    final no = _istek;
    if (!pencereKipi) {
      await kTarayici.yuklenmeyiBekle();
      await kTarayici.sayfayiOku();
    }
    // Sayfa beklenirken (12 sn'ye kadar) kullanıcı yeni bir şey sorduysa,
    // Kodi'yi kapattıysa ya da masaüstüne çıkardıysa eski işe dönülmez
    // (eskiden yine "isteğime devam et" gönderiliyordu).
    if (no != _istek || !_devamEdebilir()) return;
    await sor('Sayfa açıldı, isteğime devam et.', otomatik: true);
  }

  bool _devamEdebilir() => acik && !masaustunde && !masaustuneCikiyor && !bekliyor;

  // Kalıcı sohbet: balondaki mesajlar diske kaydedilir (ana pencerede).
  Timer? _kayitZamanlayici;
  String _sonKayit = '';
  bool _sohbetYuklendi = false;

  /// Program açılınca: Kodi her açılışta yeni bir sohbetle ("Merhaba, ben
  /// Kodi!") gelir; eski sohbetler Sohbetler panelinde durur. Motor bağlanınca
  /// yeni (boş) sohbet açılır ve kayıt başlar.
  Future<void> sohbetiYukle() async {
    if (pencereKipi || _sohbetYuklendi) return;
    try {
      // Program açılırken motor henüz bağlanmamış olabilir: bağlanınca açılır.
      await _backend.waitUntilConnected();
      final r = await _backend.call('kodi_temizle');
      // Kayıt yalnızca motor gerçekten cevap verince açılır.
      _sohbetYuklendi = r['ok'] == true;
    } catch (_) {}
  }

  /// Sohbeti hemen kaydeder (ayar değişince, program kapanırken). zorla:
  /// açılış yüklemesi bitmemiş olsa da (Sohbetler paneli).
  Future<void> sohbetiKaydet({bool zorla = false}) async {
    if (pencereKipi) {
      // Masaüstü penceresi: sohbet ana pencereye gider, o kaydeder.
      final json = jsonEncode(_sohbet);
      if (json == _sonKayit) return;
      _sonKayit = json;
      _kopruGonder({'tur': 'sohbet', 'mesajlar': _sohbet});
      return;
    }
    if (!_sohbetYuklendi && !zorla) return;
    _kayitZamanlayici?.cancel();
    final json = jsonEncode(_sohbet);
    if (json == _sonKayit) return;
    _sonKayit = json;
    try {
      await _backend.call('kodi_sohbet_kaydet', {'mesajlar': _sohbet});
    } catch (_) {
      _sonKayit = '';
    }
  }

  /// Sağlayıcı atıldı mı (geç biten işler bildirim göndermesin)?
  bool _atildi = false;

  @override
  void notifyListeners() {
    if (_atildi) return;
    super.notifyListeners();
    // Her değişiklikten bir saniye sonra (harf harf yazarken her harfte değil).
    if (bekliyor) return;
    // Kodi masaüstündeyken ana penceredeki sohbet eskidir: kaydedilmez.
    if (!pencereKipi && _sohbetYuklendi && !masaustunde) {
      _kayitZamanlayici?.cancel();
      _kayitZamanlayici = Timer(const Duration(seconds: 1), sohbetiKaydet);
    } else if (pencereKipi && acik) {
      // Masaüstü penceresi: sohbet ana pencereye de gider (o kaydeder);
      // Kodi masaüstündeyken program kapansa da sohbet kaybolmaz.
      _kayitZamanlayici?.cancel();
      _kayitZamanlayici = Timer(const Duration(seconds: 1), () {
        final json = jsonEncode(_sohbet);
        if (json == _sonKayit) return;
        _sonKayit = json;
        _kopruGonder({'tur': 'sohbet', 'mesajlar': _sohbet});
      });
    }
  }

  /// Masaüstü penceresinde: gizli bekleme süresi dolunca pencere kapanır.
  Timer? _beklemeZamanlayici;
  static const _beklemeSuresi = Duration(minutes: 20);

  @override
  void dispose() {
    _atildi = true;
    _kopruOlay?.cancel();
    _donusZamanlayici?.cancel();
    _cikisZamanlayici?.cancel();
    _hazirlamaZamanlayici?.cancel();
    _beklemeZamanlayici?.cancel();
    _kayitZamanlayici?.cancel();
    super.dispose();
  }

  Future<void> kopruKaydol() async {
    _kopruOlay ??= _backend.events.listen((e) {
      if (e.name == 'kodi_kopru') _kopruMesaji(Map<String, dynamic>.from(e.data));
    });
    await _backend.call('kodi_kopru_kayit', {'rol': pencereKipi ? 'kodi' : 'ana'});
  }

  void _kopruGonder(Map<String, dynamic> veri) {
    _backend
        .call('kodi_kopru_gonder', {'rol': pencereKipi ? 'ana' : 'kodi', 'veri': veri})
        .catchError((_) => <String, dynamic>{});
  }

  /// Süresi dolduktan sonra gelen cevaplar (bir süre daha beklenir).
  final Map<int, void Function(Map<String, dynamic>)> _kopruGecCevap = {};

  Future<Map<String, dynamic>> _kopruIste(Map<String, dynamic> veri,
      {Duration sure = const Duration(seconds: 30),
      void Function(Map<String, dynamic> cevap)? gecCevap}) {
    final no = ++_kopruNo;
    final c = Completer<Map<String, dynamic>>();
    _kopruBekleyen[no] = c;
    _kopruGonder({...veri, 'no': no});
    return c.future.timeout(sure, onTimeout: () {
      _kopruBekleyen.remove(no);
      if (gecCevap != null) {
        // Eskiden geç gelen gerçek cevap atılıyordu: iş yapılmışken Kodi
        // "TürKod cevap vermedi" diyordu.
        _kopruGecCevap[no] = gecCevap;
        Timer(const Duration(minutes: 10), () => _kopruGecCevap.remove(no));
      }
      return <String, dynamic>{};
    });
  }

  void _yanitla(Map<String, dynamic> m, Map<String, dynamic> veri) =>
      _kopruGonder({...veri, 'yanit_no': m['no']});

  void _sohbetiAl(Object? liste) {
    if (liste is! List) return;
    mesajlar
      ..clear()
      ..addAll([
        for (final m in liste)
          if (m is Map) KodiMesaji.jsondan(Map<String, dynamic>.from(m)),
      ]);
    // Öbür pencerede sürmekte olan işin sonucu bu kopyaya gelmez: dönen
    // simgeyle sonsuza dek beklemesin.
    for (final m in mesajlar) {
      for (final e in m.eylemler) {
        if (e.durum == 'calisiyor') {
          e.durum = 'yapildi';
          e.sonuc = 'Öbür pencerede yapılıyordu';
        }
      }
    }
    if (mesajlar.isNotEmpty) _selamVerildi = true;
  }

  List<Map<String, dynamic>> get _sohbet =>
      [for (final m in mesajlar) if (m.metin != kKodiTekrarHosGeldin) m.json()];

  Future<void> _kopruMesaji(Map<String, dynamic> m) async {
    if (!pencereKipi) _pencereTemas = DateTime.now();
    final yanit = m['yanit_no'];
    if (yanit is int) {
      final c = _kopruBekleyen.remove(yanit);
      if (c != null) {
        c.complete(m);
      } else {
        _kopruGecCevap.remove(yanit)?.call(m);
      }
      return;
    }
    switch (m['tur']) {
      // --- ana pencere ---
      case 'hazir':
        // Masaüstü penceresi çizilmeye hazır: Kodi şimdi oraya geçer (o ana
        // kadar TürKod'da görünmeye devam eder, arada boşluk olmaz).
        _cikisZamanlayici?.cancel();
        canli = false;
        _sesleriDurdur();
        masaustuneCikiyor = false;
        masaustunde = true;
        acik = false;
        // Yazılmakta olan cevabın güvenli işlerini artık masaüstü Kodi yapar
        // (eskiden hiç yapılmıyordu: balon kapanınca yazma yarıda kalıyordu).
        _devret();
        _yanitla(m, {'mesajlar': _sohbet, 'hep_sor': hepSor});
        notifyListeners();
      case 'baglam_iste':
        _yanitla(m, {'veri': baglamUret?.call() ?? const <String, dynamic>{}});
      case 'eylem':
        final e = KodiEylemi.jsondanTam(Map<String, dynamic>.from(m['eylem'] as Map));
        await eylemUygula?.call(e, hedef: m['hedef']?.toString());
        _yanitla(m, {'durum': e.durum, 'sonuc': e.sonuc});
      case 'ayarlar_ac':
        ayarlarAc?.call();
      case 'rehber':
        rehberAcici?.call();
      case 'sohbet':
        // Masaüstündeki sohbet: ana pencerede tutulur ve kaydedilir.
        if (masaustunde) {
          _sohbetiAl(m['mesajlar']);
          await sohbetiKaydet();
        }
      case 'beklemede':
        // Masaüstü penceresi gizli olarak hazır.
        _hazirlamaZamanlayici?.cancel();
        _pencereHazirlaniyor = false;
        _hazirPencere = true;
        final istek = _bekleyenGosterme;
        if (istek != null && masaustuneCikiyor) {
          _bekleyenGosterme = null;
          _hazirPencere = false;
          _kopruGonder({'tur': 'goster', ...istek});
        }
      case 'geri_don':
      case 'kapandi':
        _donusZamanlayici?.cancel();
        _sohbetiAl(m['mesajlar']);
        if (m['hep_sor'] is bool) hepSor = m['hep_sor'] as bool;
        masaustunde = false;
        acik = m['tur'] == 'geri_don';
        await ayarlariYenile?.call();
        notifyListeners();
        // Masaüstü Kodi'nin yazmayı bitiremediği cevabın güvenli işleri.
        _bekleyenleriBaslat();
      case 'kapaniyor':
        // Gizli bekleyen pencere süresi dolunca kendini kapattı.
        if (!masaustunde) {
          _hazirPencere = false;
          _pencereSureci = null;
        }
      // --- masaüstü penceresi ---
      case 'kapan':
        // Ana pencere yeni bir masaüstü penceresi açıyor: gizli bekleyen
        // eski pencere kapanır (iki pencere birden bellekte kalmasın).
        if (pencereKipi && !acik) {
          _beklemeZamanlayici?.cancel();
          await kodiPenceresiKanali.invokeMethod('kapat').catchError((_) => null);
        }
      case 'don':
        masaustundenDon();
      case 'goster':
        await _gizliPencereyiGoster(m['x'], m['y']);
    }
  }

  /// Ana pencerede: masaüstü penceresini gizlice hazırlar (Kodi açılınca).
  Future<void> masaustunuHazirla() async {
    if (pencereKipi || !Platform.isWindows || _hazirPencere || _pencereHazirlaniyor ||
        masaustunde) {
      return;
    }
    _pencereHazirlaniyor = true;
    try {
      await kopruKaydol();
      await _pencereSureciniBaslat(gizli: true);
    } catch (_) {
      _pencereHazirlaniyor = false;
      return;
    }
    // Hiç "beklemede" demezse bir sonraki istekte yeniden denenir.
    _hazirlamaZamanlayici?.cancel();
    _hazirlamaZamanlayici = Timer(const Duration(seconds: 60), () {
      _pencereHazirlaniyor = false;
    });
  }

  /// Ana pencerede: en son başlatılan masaüstü Kodi süreci ve ondan son
  /// haber alınan an. Yeni pencere açılmadan önce eskisi kapatılır: eskiden
  /// hazır pencere 2,5 sn'de cevap vermeyince (ya da 60 sn'de "beklemede"
  /// demeyince) ikinci bir süreç açılıyor, ikisi birden bellekte kalıyordu.
  Process? _pencereSureci;
  DateTime? _pencereTemas;

  void _eskiPencereyiKapat() {
    // Kayıtlı (köprüye bağlı) pencere kendini kapatır.
    _kopruGonder({'tur': 'kapan'});
    final s = _pencereSureci;
    final temas = _pencereTemas;
    _pencereSureci = null;
    _hazirPencere = false;
    // Henüz köprüye bağlanamamış (yavaş açılan) süreç doğrudan kapatılır.
    // Yalnızca yakın zamanda haber alınmışsa: kendi kendine kapanan (20 dk
    // bekleyip) bir sürecin numarası başka bir programa geçmiş olabilir.
    if (s != null &&
        temas != null &&
        DateTime.now().difference(temas) < const Duration(minutes: 19)) {
      try {
        Process.killPid(s.pid);
      } catch (_) {}
    }
  }

  Future<void> _pencereSureciniBaslat({bool gizli = false, Map<String, dynamic>? konum}) async {
    final url = await AppConfig.wsUrl;
    _eskiPencereyiKapat();
    _pencereTemas = DateTime.now();
    _pencereSureci = await Process.start(
      Platform.resolvedExecutable,
      [
        '--kodi-penceresi',
        if (gizli) '--kodi-gizli',
        '--kodi-url',
        url,
        if (konum != null && konum['ok'] == true) ...[
          '--kodi-x',
          '${konum['x']}',
          '--kodi-y',
          '${konum['y']}'
        ],
      ],
      mode: ProcessStartMode.detached,
    );
  }

  /// Masaüstü penceresinde: gizli bekleyen pencere imlecin yanında görünür.
  Future<void> _gizliPencereyiGoster(Object? x, Object? y) async {
    _beklemeZamanlayici?.cancel();
    final r = await _kopruIste({'tur': 'hazir'});
    _sohbetiAl(r['mesajlar']);
    if (r['hep_sor'] is bool) hepSor = r['hep_sor'] as bool;
    acik = true;
    notifyListeners();
    _bekleyenleriBaslat();
    // Balon ve robot çizilsin, tıklanabilir alan ayarlansın; sonra görünür.
    await Future<void>.delayed(const Duration(milliseconds: 180));
    await kodiPenceresiKanali
        .invokeMethod('goster', [if (x is int && y is int) ...[x, y]])
        .catchError((_) => null);
  }

  /// Kodi'yi masaüstüne çıkarır: TürKod'un ikinci, saydam, hep üstte duran
  /// penceresi açılır. İçinde aynı Kodi, aynı balon ve aynı düğmeler vardır.
  Future<bool> masaustuneCik() async {
    if (pencereKipi || masaustunde || masaustuneCikiyor) return masaustunde;
    masaustuneCikiyor = true;
    notifyListeners();
    try {
      // Bırakıldığı yer hemen alınır.
      Map<String, dynamic> konum = const {};
      try {
        konum = await _backend.call('kodi_imlec_konumu');
      } catch (_) {}
      await kopruKaydol();
      final yer = {if (konum['ok'] == true) ...{'x': konum['x'], 'y': konum['y']}};
      if (_hazirPencere) {
        // Hazır bekleyen pencere anında görünür; cevap vermezse (kapanmışsa)
        // yeni bir pencere açılır (eskisi önce kapatılır).
        _hazirPencere = false;
        _kopruGonder({'tur': 'goster', ...yer});
        Timer(const Duration(milliseconds: 4000), () {
          if (masaustuneCikiyor && !masaustunde) {
            _pencereSureciniBaslat(konum: konum).catchError((_) {});
          }
        });
      } else if (_pencereHazirlaniyor) {
        // Hazırlanmakta: hazır olur olmaz görünsün.
        _bekleyenGosterme = yer;
      } else {
        await _pencereSureciniBaslat(konum: konum);
      }
    } catch (e) {
      masaustuneCikiyor = false;
      mesajlar.add(KodiMesaji(true, 'Eyvah, masaüstüne çıkamadım: $e', hata: true));
      notifyListeners();
      return false;
    }
    // Pencere "hazır" diyene kadar Kodi burada kalır; hiç demezse vazgeçilir.
    _cikisZamanlayici?.cancel();
    _cikisZamanlayici = Timer(const Duration(seconds: 25), () {
      if (!masaustuneCikiyor) return;
      masaustuneCikiyor = false;
      mesajlar.add(KodiMesaji(true, 'Eyvah, masaüstü pencerem açılamadı. Burada kalıyorum!',
          hata: true));
      notifyListeners();
    });
    return true;
  }

  /// Kodi'yi TürKod penceresine geri getirir (iki pencereden de çağrılabilir).
  void masaustundenDon() {
    if (pencereKipi) {
      _pencereyiKapat('geri_don');
      kodiPenceresiKanali.invokeMethod('anaPencereyiOneGetir').catchError((_) => null);
      return;
    }
    if (!masaustunde) return;
    _kopruGonder({'tur': 'don'});
    // Pencere cevap vermezse (kapanmışsa) Kodi yine de geri gelir.
    _donusZamanlayici?.cancel();
    _donusZamanlayici = Timer(const Duration(seconds: 3), () {
      if (!masaustunde) return;
      masaustunde = false;
      acik = true;
      notifyListeners();
    });
  }

  /// Masaüstü penceresi TürKod'a döner: pencere kapanmaz, gizlenip bir
  /// sonraki "Masaüstüne çık" için hazır bekler.
  void _pencereyiKapat(String tur) {
    canli = false;
    _canliNesil++;
    _sesleriDurdur();
    // Bekleyen güvenli işleri bundan sonra ana pencere yapar.
    _devret();
    _kopruGonder({'tur': tur, 'mesajlar': _sohbet, 'hep_sor': hepSor});
    Future.delayed(const Duration(milliseconds: 250), () async {
      await kodiPenceresiKanali.invokeMethod('gizle').catchError((_) => null);
      acik = false;
      notifyListeners();
      _beklemeyeGec();
    });
  }

  void _beklemeyeGec() {
    _kopruGonder({'tur': 'beklemede'});
    _beklemeZamanlayici?.cancel();
    _beklemeZamanlayici = Timer(_beklemeSuresi, () {
      // Ana pencere bilsin: bir sonraki "Masaüstüne çık"ta yenisini açar.
      _backend
          .call('kodi_kopru_gonder', {
            'rol': 'ana',
            'veri': {'tur': 'kapaniyor'}
          })
          .timeout(const Duration(seconds: 2))
          .catchError((_) => <String, dynamic>{})
          .whenComplete(
              () => kodiPenceresiKanali.invokeMethod('kapat').catchError((_) => null));
    });
  }

  /// Masaüstü penceresi açılırken: sohbet ana pencereden alınır. gizli:
  /// önceden hazırlanan pencere, "goster" gelene kadar bekler.
  Future<void> pencereyiBaslat({bool gizli = false}) async {
    await kopruKaydol();
    if (gizli) {
      _beklemeyeGec();
      return;
    }
    final r = await _kopruIste({'tur': 'hazir'});
    _sohbetiAl(r['mesajlar']);
    if (r['hep_sor'] is bool) hepSor = r['hep_sor'] as bool;
    acik = true;
    notifyListeners();
    _bekleyenleriBaslat();
  }

  /// Bir eylemi uygular: ana pencerede doğrudan, masaüstü penceresinde ana
  /// pencereye yaptırarak.
  ///
  /// İş yapılırken durumu "calisiyor"dur (hemen, beklemeden konur): ikinci
  /// tıklama ya da ikinci başlatma yok sayılır. Eskiden izin kartının
  /// düğmeleri iş sürerken de açıktı; iki tıklamada kod iki kez yazılıyor,
  /// iki sekme açılıyor, komut iki kez çalışıyordu.
  Future<void> eylemiUygula(KodiEylemi e, {String? hedef}) async {
    if (e.durum == 'calisiyor') return;
    final kod = e.tur == 'kod_yaz';
    // Editöre aynı anda iki kod akmasın (kod bloğundaki düğmeye iki kez
    // basılınca da).
    if (kod && _kodYaziliyor) return;
    if (kod) _kodYaziliyor = true;
    e.durum = 'calisiyor';
    e.sonuc = null;
    notifyListeners();
    try {
      if (pencereKipi) {
        // Tarayıcı işleri uzun sürebilir (sayfanın yüklenmesi, okunması,
        // WebView2'nin açılması): eskiden 30 sn sonra "TürKod cevap vermedi"
        // deniyordu, iş yapılmış olsa bile.
        final r = await _kopruIste({'tur': 'eylem', 'eylem': e.json(), 'hedef': hedef},
            sure: const Duration(seconds: 120),
            gecCevap: (g) => _gecEylemCevabi(e, g));
        if (r.isEmpty) {
          e.durum = 'hata';
          e.sonuc = _kCevapYok;
          notifyListeners();
        } else {
          _eylemCevabiniAl(e, r);
        }
        return;
      }
      await eylemUygula?.call(e, hedef: hedef);
    } finally {
      if (kod) _kodYaziliyor = false;
      if (e.durum == 'calisiyor') {
        e.durum = 'hata';
        e.sonuc ??= 'Bu işi yapamadım';
        notifyListeners();
      }
    }
  }

  bool _kodYaziliyor = false;
  static const String _kCevapYok = 'TürKod cevap vermedi';

  /// Masaüstü penceresinde: ana pencerenin yaptığı işin sonucu.
  void _eylemCevabiniAl(KodiEylemi e, Map<String, dynamic> r) {
    e.durum = (r['durum'] ?? 'hata').toString();
    if (e.durum == 'calisiyor' || e.durum == 'bekliyor') e.durum = 'hata';
    e.sonuc = (r['sonuc'] ?? _kCevapYok).toString();
    notifyListeners();
    // Tarayıcı işi ana pencerede yapıldı (sayfa da okundu): Kodi yeni
    // sayfaya bakıp işine burada devam eder.
    if (e.tur == 'tarayici' && e.durum == 'yapildi' && e.veri['devam'] == true) {
      Future<void>.delayed(const Duration(milliseconds: 200), otomatikDevam);
    }
  }

  /// Süre dolduktan sonra gelen cevap: iş hâlâ balonda "cevap vermedi"
  /// diye duruyorsa gerçek sonuç yazılır.
  void _gecEylemCevabi(KodiEylemi e, Map<String, dynamic> r) {
    if (e.durum != 'hata' || e.sonuc != _kCevapYok) return;
    if (!mesajlar.any((m) => m.eylemler.any((x) => identical(x, e)))) return;
    _eylemCevabiniAl(e, r);
  }

  /// Bir cevabın güvenli işlerini (panel, dosya, sekme ...) SIRAYLA yapar;
  /// izin isteyenler kartta bekler. Bir mesajın işleri bir kez başlatılır.
  /// Eskiden hepsi aynı anda başlıyordu: "oyun.trpy'yi aç, 12. satıra git"
  /// denince satıra önceki sekmede gidiliyordu, tarayıcıda da "aç" bitmeden
  /// eski sayfaya tıklanıyordu.
  Future<void> eylemleriBaslat(KodiMesaji m) async {
    if (m.eylemlerBasladi || _atildi) return;
    m.eylemlerBasladi = true;
    for (final e in m.eylemler) {
      // Sohbet öbür pencereye geçtiyse kalan işleri o yapar.
      if (m.devredildi || _atildi) return;
      if (e.durum != 'bekliyor' || !e.guvenliMi(hepSor)) continue;
      await eylemiUygula(e);
    }
  }

  /// Henüz başlatılmamış güvenli işleri yapar: Kodi cevabı harf harf yazmayı
  /// bitirmeden kapatılınca, masaüstüne çıkınca ya da sohbet öbür pencereden
  /// gelince (eskiden bu işler hiç yapılmıyor, "onay bekliyor" kalıyordu).
  Future<void> _bekleyenleriBaslat() async {
    for (final m in List.of(mesajlar)) {
      if (!m.eylemlerBasladi) await eylemleriBaslat(m);
    }
  }

  /// Sohbet öbür pencereye gidiyor: buradaki kopyanın işlerini artık o yapar.
  void _devret() {
    for (final m in mesajlar) {
      m.eylemlerBasladi = true;
      m.devredildi = true;
    }
  }

  void ayarlariAc() {
    if (pencereKipi) {
      _kopruGonder({'tur': 'ayarlar_ac'});
      kodiPenceresiKanali.invokeMethod('anaPencereyiOneGetir').catchError((_) => null);
      return;
    }
    ayarlarAc?.call();
  }

  Future<Map<String, dynamic>?> _baglamAl() async {
    if (!pencereKipi) return baglamUret?.call();
    final r = await _kopruIste({'tur': 'baglam_iste'});
    final v = r['veri'];
    if (v is! Map) return null;
    final b = Map<String, dynamic>.from(v);
    uzakKodSekmesiVar = b['kod_sekmesi'] == true;
    return b;
  }

  // ------------------------------------------------------------------ ses
  void _sesleriDurdur() {
    if (dinliyor) {
      _backend.call('kodi_dinlemeyi_durdur').catchError((_) => <String, dynamic>{});
    }
    if (konusuyor) {
      _backend.call('kodi_sus').catchError((_) => <String, dynamic>{});
    }
  }

  /// Cevabı Kodi'nin sesiyle okur (bitene ya da susturulana dek bekler).
  Future<void> seslendir(String metin) async {
    if (metin.trim().isEmpty) return;
    konusuyor = true;
    notifyListeners();
    try {
      final r = await _backend.call('kodi_seslendir', {'metin': metin});
      if (r['ok'] != true && r['hata'] != null) {
        mesajlar.add(KodiMesaji(true, r['hata'].toString(), hata: true, yazilsin: false));
      }
    } catch (_) {
    } finally {
      konusuyor = false;
      notifyListeners();
    }
  }

  void sus() {
    if (konusuyor) _backend.call('kodi_sus').catchError((_) => <String, dynamic>{});
  }

  /// Mikrofonu bir kez dinler: söylenen yazıya çevrilir. Kimse konuşmazsa
  /// null; hata olursa Kodi söyler ve null döner (hata=true).
  Future<({String? metin, bool hata})> _kulak() async {
    sus();
    dinliyor = true;
    notifyListeners();
    Map<String, dynamic> r;
    try {
      r = await _backend.call('kodi_dinle');
    } catch (e) {
      r = {'ok': false, 'hata': 'Eyvah, TürKod motoruna ulaşamadım ($e)'};
    }
    dinliyor = false;
    if (r['ok'] != true) {
      final m = KodiMesaji(true, (r['hata'] ?? 'Seni duyamadım.').toString(),
          hata: r['anahtar_yok'] != true, ayarDugmesi: r['anahtar_yok'] == true, harfMs: 20);
      mesajlar.add(m);
      notifyListeners();
      return (metin: null, hata: true);
    }
    notifyListeners();
    final metin = (r['metin'] ?? '').toString().trim();
    return (metin: metin.isEmpty ? null : metin, hata: false);
  }

  /// Mikrofon düğmesi: bir kez dinler ve duyduğunu sorar. Dinlerken
  /// basılırsa dinlemeyi bırakır.
  Future<void> dinle() async {
    if (dinliyor) {
      _backend.call('kodi_dinlemeyi_durdur').catchError((_) => <String, dynamic>{});
      return;
    }
    if (bekliyor) return;
    final r = await _kulak();
    if (r.hata) return;
    if (r.metin == null) {
      final m = KodiMesaji(true,
          'Bir şey duyamadım. Mikrofona biraz yakın konuşup bir daha deneyiver!',
          harfMs: 20);
      mesajlar.add(m);
      notifyListeners();
      return;
    }
    await sor(r.metin!);
  }

  /// Canlı sohbet: Kodi dinler, cevaplar, sesli okur ve yeniden dinler.
  void canliDegistir() {
    canli = !canli;
    // Her açılış yeni bir döngü kuşağıdır: hızlıca kapatıp açınca eski
    // döngü (dinlemede beklerken) yeniden canlı görüp sürmez. Eskiden iki
    // döngü birden dinliyor, iki kez selam veriyordu.
    _canliNesil++;
    notifyListeners();
    if (canli) {
      _canliDongu(_canliNesil);
    } else {
      _sesleriDurdur();
    }
  }

  int _canliNesil = 0;

  Future<void> _canliDongu(int nesil) async {
    bool surmeli() => canli && nesil == _canliNesil;
    final m = KodiMesaji(true,
        'Canlı sohbet açık! Konuş, seni dinliyorum. Bitirmek istersen aynı düğmeye basıver.',
        harfMs: 20);
    mesajlar.add(m);
    notifyListeners();
    await seslendir('Canlı sohbet açık! Konuş, seni dinliyorum.');
    var sessiz = 0;
    while (surmeli() && (acik || masaustunde)) {
      final r = await _kulak();
      if (!surmeli()) break;
      if (r.hata) {
        canli = false;
        break;
      }
      if (r.metin == null) {
        if (++sessiz >= 3) {
          canli = false;
          final n = KodiMesaji(true,
              'Bir süredir sesini duymadım, canlı sohbeti kapattım. İstediğinde yeniden açabilirsin!',
              harfMs: 20);
          mesajlar.add(n);
        }
        continue;
      }
      sessiz = 0;
      await sor(r.metin!);
    }
    // Yalnızca son döngü canlı sohbeti kapatır (yenisi sürüyorsa dokunmaz).
    if (nesil != _canliNesil) return;
    canli = false;
    notifyListeners();
  }

  /// Selam bir kez verilir; sonraki gelişlerde Kodi yalnızca el sallar.
  bool _selamVerildi = false;

  /// Her soru bir numara alır; "Vazgeç"ten sonra gelen eski cevap atılır.
  int _istek = 0;

  /// Kullanıcı daha bir şey sormadı mı (hazır soru çipleri gösterilir)?
  bool get henuzSorulmadi => !mesajlar.any((m) => !m.kodiden);

  /// Bekleyen soruyu bırakır (cevap gelse de gösterilmez).
  void vazgec() {
    if (!bekliyor && !dinliyor && !konusuyor && !canli) return;
    canli = false;
    _sesleriDurdur();
    if (!bekliyor) return notifyListeners();
    _istek++;
    bekliyor = false;
    mesajlar.add(KodiMesaji(true,
        'Peki, vazgeçtim! Başka bir şey sormak istersen buradayım.',
        harfMs: 25));
    notifyListeners();
  }

  void degistir() => masaustunde
      ? masaustundenDon()
      : acik
          ? kapat()
          : ac();

  void ac() {
    if (masaustunde) return masaustundenDon();
    if (acik) return;
    // Kodi her çağrılışta yeni sohbetle ve "Merhaba, ben Kodi!" diye gelir.
    _yeniSohbeteGec();
    acik = true;
    notifyListeners();
    if (!pencereKipi && !Platform.environment.containsKey('FLUTTER_TEST')) {
      // Kodi'nin gelişini yavaşlatmasın diye biraz sonra.
      Future.delayed(const Duration(seconds: 3), () {
        if (acik) masaustunuHazirla();
      });
    }
  }

  void kapat() {
    if (pencereKipi) return _pencereyiKapat('kapandi');
    if (masaustunde) {
      _kopruGonder({'tur': 'don'});
      masaustunde = false;
    }
    if (!acik) return;
    canli = false;
    _sesleriDurdur();
    acik = false;
    notifyListeners();
    // Cevap daha harf harf yazılırken kapatıldıysa güvenli işleri yine
    // yapılır (eskiden "bekliyor" kalıyor, Kodi'ye "onay bekliyor" deniyordu).
    _bekleyenleriBaslat();
  }

  /// Bir eylemin durumu değişti (balon yeniden çizilsin).
  void yenile() => notifyListeners();

  /// Kodi yerine vardığında (kayma bitince) çağrılır.
  void selamVer() {
    if (_selamVerildi) return;
    _selamVerildi = true;
    mesajlar.add(KodiMesaji(true, kKodiSelam, harfMs: 55));
    notifyListeners();
  }

  /// Kodi'ye bağlı bir yapay zekâ var mı (KodiKatmani kurar)?
  bool Function()? modelVarOku;

  /// İlk selam yazılıp bitince ikinci cümle gelir.
  void selamDevam() {
    if (mesajlar.length != 1 || mesajlar.first.metin != kKodiSelam) return;
    final kurulum = _bekleyenKurulum;
    if (kurulum != null) {
      _bekleyenKurulum = null;
      mesajlar.add(_kurulumMesaji(kurulum));
      notifyListeners();
      return;
    }
    if (modelVarOku != null && modelVarOku!() == false) {
      // Yapay zekâ yok: kurulum rehberi düğmesiyle.
      mesajlar.add(KodiMesaji(true,
          'Bana henüz bir yapay zekâ bağlanmamış, o yüzden sorularını cevaplayamıyorum. '
          'Gel birlikte kuralım: ücretsiz bir anahtar alıp TürKod\'a koyacağız, modeli ben '
          'seçeceğim. İki dakika sürer!',
          ayarDugmesi: true,
          harfMs: 28));
      notifyListeners();
      return;
    }
    mesajlar.add(KodiMesaji(true,
        'Yardıma ihtiyacın var mı? Programla, kodunla ya da kitapla ilgili '
        'ne istersen sorabilirsin. Senin için panel ya da dosya açabilir, kod '
        'yazabilirim. Hadi, birlikte yapalım; yardımcı olabilirim!',
        harfMs: 32));
    notifyListeners();
  }

  Future<void> sor(String soru,
      {bool? dusunme, Map<String, dynamic>? baglam, bool otomatik = false}) async {
    soru = soru.trim();
    if (soru.isEmpty || bekliyor) return;
    if (!otomatik) _otomatikAdim = 0;
    sohbetlerAcik = false;
    dusunme ??= dusunmeOku?.call() ?? false;
    // Bekleme, bağlam alınmadan ÖNCE başlar: masaüstü penceresinde bağlam ana
    // pencereden gelir (30 sn'ye kadar sürebilir); eskiden bu arada Enter'a
    // yeniden basılınca ikinci soru gidiyor, ilk cevap atılıyordu, "Vazgeç"
    // de çalışmıyordu.
    final soruMesaji = KodiMesaji(false, soru, yazilsin: false, otomatik: otomatik);
    mesajlar.add(soruMesaji);
    bekliyor = true;
    final no = ++_istek;
    notifyListeners();
    try {
      baglam ??= await _baglamAl();
      if (no != _istek) return; // kullanıcı vazgeçti
      final yetkiler = baglam?['yetkiler'];
      hepSor = yetkiler is Map && yetkiler['hep_sor'] == true;
      final r = await _backend.call('kodi_sor', {
        'mesaj': soru,
        'dusunme': dusunme,
        if (baglam != null) 'baglam': baglam,
        // Kodi'nin kendi sürdürdüğü tarayıcı adımı: sınıra takılırsa motor
        // hata göstermeden daha uzun bekler.
        if (otomatik) 'otomatik': true,
      });
      if (no != _istek) return; // kullanıcı vazgeçti
      soruMesaji.goruntu = r['goruntu']?.toString();
      if (r['ok'] == true) {
        final eylemler = [
          for (final e in (r['eylemler'] as List?) ?? const [])
            // _durum: motorun kendi yaptığı işler (hatırlamak, unutmak).
            if (e is Map) KodiEylemi.jsondanTam(Map<String, dynamic>.from(e)),
        ];
        var metin = (r['cevap'] ?? '').toString().trim();
        if (metin.isEmpty && eylemler.isNotEmpty) metin = 'Hemen yapıvereyim!';
        final cevap = KodiMesaji(true, metin, eylemler: eylemler);
        mesajlar.add(cevap);
      } else {
        mesajlar.add(KodiMesaji(
            true, (r['hata'] ?? 'Hay aksi, bir şeyler ters gitti.').toString(),
            hata: r['model_yok'] != true, ayarDugmesi: r['model_yok'] == true));
      }
    } catch (e) {
      if (no != _istek) return;
      // Motor cevap verdi ama iş olmadı (BackendException): onun iletisi
      // Kodi'nin diliyle hazırlanmıştır. Yalnızca gerçekten ulaşılamadıysa
      // "motor" denir.
      final ileti = e is BackendException ? e.message : '';
      mesajlar.add(KodiMesaji(
          true,
          ileti.startsWith('Zaman aşımı')
              ? 'Cevabım çok uzun sürdü. Bir daha sorar mısın?'
              : ileti.isEmpty || ileti.startsWith('TürKod motoru bağlı değil')
                  ? 'Eyvah, TürKod motoruna ulaşamadım. Birazdan bir daha deneyiver, '
                      'olur mu?'
                  : ileti,
          hata: true));
    } finally {
      if (no == _istek) {
        bekliyor = false;
        notifyListeners();
      }
    }
    if (no != _istek) return;
    // Kodi cevap beklerken kapatıldıysa cevap balonda yazılmaz: güvenli
    // işleri burada başlatılır.
    if (!acik && !masaustunde) _bekleyenleriBaslat();
    final son = mesajlar.isEmpty ? null : mesajlar.last;
    if (son != null && son.kodiden && (canli || (sesliOku?.call() ?? false))) {
      await seslendir(son.metin);
    }
  }

  /// Yeni sohbet: şu anki sohbet kaydedilir (Sohbetler panelinde kalır).
  Future<void> temizle() async {
    if (bekliyor) return;
    await sohbetiKaydet(zorla: true);
    _yeniSayfa();
    sohbetlerAcik = false;
    notifyListeners();
    try {
      await _backend.call('kodi_temizle');
    } catch (_) {}
  }
}

// ============================================================================
// ROBOT ÇİZİMİ
// ============================================================================

const _kKodiMor = Color(0xFF7C5CF5);
const _kKodiMorKoyu = Color(0xFF5B3FD9);
const _kKodiCamgobegi = Color(0xFF22D3EE);
const _kKodiCamgobegiKoyu = Color(0xFF0EA5C6);
const _kKodiPembe = Color(0xFFEC4899);
const _kKodiEkran = Color(0xFF0F172A);

/// Kodi'yi 100 x 130'luk bir kutuda çizer (boyuta göre ölçeklenir).
/// [t]: 0-1 arası dönen zaman (salınma, anten ışığı, el sallama, düşünce
/// baloncukları); [goz]: 1 açık, 0 kapalı (göz kırpma); [agiz]: konuşurken
/// 0-1 ağız açıklığı.
class KodiRessami extends CustomPainter {
  final KodiIfadesi ifade;
  final double t;
  final double goz;
  final double agiz;
  final bool elSalla;
  final bool sadeceBas;

  /// Robot yatay aynalanır (düşünme pozu sola dönük); göğüsteki "</>" yazısı
  /// ters dönmez.
  final bool aynala;
  const KodiRessami({
    this.ifade = KodiIfadesi.mutlu,
    this.t = 0,
    this.goz = 1,
    this.agiz = 0,
    this.elSalla = false,
    this.sadeceBas = false,
    this.aynala = false,
  });

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    if (sadeceBas) {
      // Simge: yalnızca baş (x 10-90, y 0-64 bölgesi).
      final s = math.min(size.width / 80, size.height / 64);
      canvas.translate((size.width - 80 * s) / 2, (size.height - 64 * s) / 2);
      canvas.scale(s);
      canvas.translate(-10, 0);
    } else {
      final s = math.min(size.width / 100, size.height / 130);
      canvas.translate((size.width - 100 * s) / 2, (size.height - 130 * s) / 2);
      canvas.scale(s);
      if (aynala) {
        // 100 birimlik çizim alanı x = 50 çizgisine göre aynalanır.
        canvas.translate(100, 0);
        canvas.scale(-1, 1);
      }
    }
    final sal = sadeceBas ? 0.0 : math.sin(t * 2 * math.pi) * 2.2;

    if (!sadeceBas) {
      // Gölge (salınmayla küçülüp büyür).
      canvas.drawOval(
          Rect.fromCenter(center: const Offset(50, 125), width: 46 - sal, height: 7),
          Paint()..color = Colors.black.withValues(alpha: 0.22));
    }
    canvas.save();
    canvas.translate(0, sal);
    if (!sadeceBas) _govde(canvas);
    _bas(canvas);
    if (!sadeceBas && ifade == KodiIfadesi.dusunceli) _dusunmeKollari(canvas);
    canvas.restore();
    if (ifade == KodiIfadesi.dusunceli && !sadeceBas) _dusunceBaloncuklari(canvas);
    if (ifade == KodiIfadesi.dinliyor && !sadeceBas) _sesDalgalari(canvas, sal);
    canvas.restore();
  }

  /// Göğüsteki "</>" yazısı bir kez ölçülür (her karede değil).
  static final TextPainter _kodYazisi = TextPainter(
    text: const TextSpan(
        text: '</>',
        style: TextStyle(
            color: _kKodiCamgobegi,
            fontSize: 11,
            fontWeight: FontWeight.w800,
            fontFamily: 'Consolas')),
    textDirection: TextDirection.ltr,
  )..layout();

  void _govde(Canvas c) {
    final mor = Paint()..color = _kKodiMor;
    final morKoyu = Paint()..color = _kKodiMorKoyu;
    // Bacaklar ve ayaklar.
    c.drawRRect(RRect.fromLTRBR(35, 100, 43, 112, const Radius.circular(3)), morKoyu);
    c.drawRRect(RRect.fromLTRBR(57, 100, 65, 112, const Radius.circular(3)), morKoyu);
    c.drawRRect(RRect.fromLTRBR(29, 109, 47, 118, const Radius.circular(5)), mor);
    c.drawRRect(RRect.fromLTRBR(53, 109, 71, 118, const Radius.circular(5)), mor);
    // Boyun.
    c.drawRect(const Rect.fromLTRB(44, 58, 56, 68), morKoyu);
    // Kollar (gövdenin arkasında başlar).
    final kol = Paint()
      ..color = _kKodiMor
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    // Düşünürken kollar gövdenin önündedir (bkz. _dusunmeKollari).
    if (ifade == KodiIfadesi.dusunceli) {
      // kollar sonra çizilir
    } else {
      // Sol kol: aşağıda, hafifçe sallanır.
      final solEl = Offset(13, 93 + math.sin(t * 2 * math.pi) * 1.5);
      c.drawLine(const Offset(26, 74), solEl, kol);
      c.drawCircle(solEl, 5.5, Paint()..color = _kKodiPembe);
    }
    // Sağ kol: el sallar, yoksa aşağıda.
    if (ifade == KodiIfadesi.dusunceli) {
      // kollar sonra çizilir
    } else if (elSalla) {
      final aci = -1.25 + math.sin(t * 4 * math.pi) * 0.38;
      const omuz = Offset(74, 74);
      final el = omuz + Offset(math.cos(aci), math.sin(aci)) * 26;
      c.drawLine(omuz, el, kol);
      c.drawCircle(el, 5.5, Paint()..color = _kKodiPembe);
    } else {
      final el = Offset(87, 93 - math.sin(t * 2 * math.pi) * 1.5);
      c.drawLine(const Offset(74, 74), el, kol);
      c.drawCircle(el, 5.5, Paint()..color = _kKodiPembe);
    }
    // Gövde.
    final govde = RRect.fromLTRBR(24, 64, 76, 104, const Radius.circular(11));
    c.drawRRect(
        govde,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF67E8F9), _kKodiCamgobegiKoyu],
          ).createShader(govde.outerRect));
    // Göğüsteki ekran ve </> işareti.
    c.drawRRect(RRect.fromLTRBR(33, 72, 67, 94, const Radius.circular(5)),
        Paint()..color = _kKodiEkran);
    final tp = _kodYazisi;
    c.save();
    if (aynala) {
      // Yazı aynalanmasın: x = 50 çevresinde yeniden çevrilir.
      c.translate(100, 0);
      c.scale(-1, 1);
    }
    tp.paint(c, Offset(50 - tp.width / 2, 83 - tp.height / 2));
    c.restore();
  }

  void _bas(Canvas c) {
    // Anten ve ışığı.
    c.drawLine(
        const Offset(50, 19),
        const Offset(50, 8),
        Paint()
          ..color = _kKodiMorKoyu
          ..strokeWidth = 3
          ..strokeCap = StrokeCap.round);
    final isik = 0.35 + 0.35 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 2));
    c.drawCircle(const Offset(50, 6), 8,
        Paint()..color = _kKodiPembe.withValues(alpha: isik * 0.45));
    c.drawCircle(const Offset(50, 6), 4.8, Paint()..color = _kKodiPembe);
    // Kulaklar.
    c.drawCircle(const Offset(17, 40), 6.5, Paint()..color = _kKodiMorKoyu);
    c.drawCircle(const Offset(83, 40), 6.5, Paint()..color = _kKodiMorKoyu);
    // Kafa.
    final kafa = RRect.fromLTRBR(18, 17, 82, 62, const Radius.circular(17));
    c.drawRRect(
        kafa,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF9B7BFF), _kKodiMorKoyu],
          ).createShader(kafa.outerRect));
    // Yüz ekranı.
    c.drawRRect(RRect.fromLTRBR(25, 24, 75, 55, const Radius.circular(12)),
        Paint()..color = _kKodiEkran);
    // Yanaklar.
    final yanak = Paint()..color = const Color(0xFFF472B6).withValues(alpha: 0.75);
    c.drawCircle(const Offset(31, 47), 3.4, yanak);
    c.drawCircle(const Offset(69, 47), 3.4, yanak);
    _gozler(c);
    _agiz(c);
  }

  void _gozler(Canvas c) {
    final dolu = Paint()..color = _kKodiCamgobegi;
    final cizgi = Paint()
      ..color = _kKodiCamgobegi
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    for (final x in const [40.0, 60.0]) {
      switch (ifade) {
        case KodiIfadesi.mutlu:
          if (goz < 0.5) {
            c.drawLine(Offset(x - 4, 37), Offset(x + 4, 37), cizgi);
          } else {
            // Gülen gözler: ^ ^
            final p = Path()
              ..moveTo(x - 5, 39)
              ..quadraticBezierTo(x, 31, x + 5, 39);
            c.drawPath(p, cizgi);
          }
        case KodiIfadesi.konusuyor:
          c.drawOval(
              Rect.fromCenter(
                  center: Offset(x, 37), width: 9, height: math.max(1.5, 10 * goz)),
              dolu);
          if (goz > 0.5) {
            c.drawCircle(Offset(x + 1.8, 35), 1.6, Paint()..color = Colors.white);
          }
        case KodiIfadesi.dusunceli:
          // Yukarı, sağa bakan gözler (diğer ifadelerdeki gibi göz bebeksiz);
          // sol göz hafif kısık.
          c.drawOval(
              Rect.fromCenter(
                  center: Offset(x + 1.5, 35.5),
                  width: 9,
                  height: math.max(1.5, (x < 50 ? 6.5 : 9) * goz)),
              dolu);
          // Kalkık kaş.
          if (x > 50) {
            final kas = Path()
              ..moveTo(x - 5, 29.5)
              ..quadraticBezierTo(x, 26.5, x + 5, 29.5);
            c.drawPath(kas, cizgi..strokeWidth = 2);
            cizgi.strokeWidth = 3;
          }
        case KodiIfadesi.uzgun:
          c.drawOval(
              Rect.fromCenter(
                  center: Offset(x, 38), width: 8, height: math.max(1.5, 8 * goz)),
              dolu);
        case KodiIfadesi.dinliyor:
          // Kocaman açılmış, dikkatle dinleyen gözler.
          c.drawOval(
              Rect.fromCenter(
                  center: Offset(x, 37), width: 10, height: math.max(1.5, 11 * goz)),
              dolu);
      }
    }
  }

  void _agiz(Canvas c) {
    final cizgi = Paint()
      ..color = _kKodiCamgobegi
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.6
      ..strokeCap = StrokeCap.round;
    switch (ifade) {
      case KodiIfadesi.mutlu:
        final p = Path()
          ..moveTo(42, 46)
          ..quadraticBezierTo(50, 53, 58, 46);
        c.drawPath(p, cizgi);
      case KodiIfadesi.konusuyor:
        c.drawRRect(
            RRect.fromRectAndRadius(
                Rect.fromCenter(
                    center: const Offset(50, 48), width: 11, height: 2.5 + 6 * agiz),
                const Radius.circular(4)),
            Paint()..color = _kKodiCamgobegi);
      case KodiIfadesi.dusunceli:
        final p = Path()
          ..moveTo(46, 49)
          ..quadraticBezierTo(51, 47, 56, 48.5);
        c.drawPath(p, cizgi);
      case KodiIfadesi.uzgun:
        final p = Path()
          ..moveTo(43, 50)
          ..quadraticBezierTo(50, 45, 57, 50);
        c.drawPath(p, cizgi);
      case KodiIfadesi.dinliyor:
        c.drawCircle(const Offset(50, 48.5), 2.6, Paint()..color = _kKodiCamgobegi);
    }
  }

  /// Düşünme pozu: sağ elin dirseği sol elde, sağ el çenede (parmaklarıyla
  /// çenesine hafifçe vurur). Kollar gövdenin ve başın önünde çizilir.
  void _dusunmeKollari(Canvas c) {
    final kol = Paint()
      ..color = _kKodiMor
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    final el = Paint()..color = _kKodiPembe;
    final golge = Paint()
      ..color = _kKodiMorKoyu
      ..strokeWidth = 8.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    final vurus = math.max(0.0, math.sin(t * 2 * math.pi * 3)) * 1.6;
    // Sağ kol: omuzdan dirseğe (gövdenin önünde), dirsekten çeneye.
    const sagOmuz = Offset(74, 75);
    const dirsek = Offset(63, 95);
    final cene = Offset(56.5, 63.5 - vurus);
    // Sol kol: omuzdan gövdenin önüne, avucu sağ dirseğin altında.
    const solOmuz = Offset(26, 75);
    const solDirsek = Offset(31, 96);
    const tutan = Offset(61, 99);
    // Kolları birbirinden ayırmak için koyu kenar.
    for (final (a, b) in [(sagOmuz, dirsek), (dirsek, cene), (solOmuz, solDirsek), (solDirsek, tutan)]) {
      c.drawLine(a, b, golge);
    }
    c.drawLine(sagOmuz, dirsek, kol);
    c.drawLine(solOmuz, solDirsek, kol);
    c.drawLine(solDirsek, tutan, kol);
    c.drawCircle(tutan, 5.5, el);
    c.drawLine(dirsek, cene, kol);
    c.drawCircle(cene, 5.5, el);
  }

  /// Dinlerken kulağın yanında beliren ses dalgaları.
  void _sesDalgalari(Canvas c, double sal) {
    for (var i = 0; i < 3; i++) {
      final faz = ((t * 3) - i * 0.25) % 1.0;
      if (faz > 0.75) continue;
      final r = 7.0 + i * 4.5;
      c.drawArc(
          Rect.fromCircle(center: Offset(8, 40 + sal), radius: r),
          math.pi * 0.8,
          math.pi * 0.4,
          false,
          Paint()
            ..color = _kKodiCamgobegi.withValues(alpha: 0.9 - i * 0.25)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.2
            ..strokeCap = StrokeCap.round);
    }
  }

  void _dusunceBaloncuklari(Canvas c) {
    // Sırayla beliren üç baloncuk (sağ üstte).
    const merkezler = [Offset(86, 20), Offset(92, 11), Offset(97, 2)];
    const yaricap = [2.4, 3.4, 4.4];
    for (var i = 0; i < 3; i++) {
      final faz = ((t * 2) - i * 0.22) % 1.0;
      final a = faz < 0.6 ? (faz / 0.6) : 1 - (faz - 0.6) / 0.4;
      c.drawCircle(merkezler[i], yaricap[i],
          Paint()..color = _kKodiCamgobegi.withValues(alpha: 0.25 + 0.6 * a));
    }
  }

  @override
  bool shouldRepaint(KodiRessami e) =>
      e.ifade != ifade ||
      e.t != t ||
      e.goz != goz ||
      e.agiz != agiz ||
      e.elSalla != elSalla ||
      e.aynala != aynala;
}

/// Canlı Kodi: salınır, göz kırpar, konuşurken ağzı oynar.
class KodiRobotu extends StatefulWidget {
  final KodiIfadesi ifade;
  final bool elSalla;
  final double boy;

  /// Düşünme pozu sola dönük çizilsin mi (pencerenin ortası soldaysa).
  final bool solaBak;
  const KodiRobotu(
      {super.key,
      this.ifade = KodiIfadesi.mutlu,
      this.elSalla = false,
      this.boy = 120,
      this.solaBak = false});
  @override
  State<KodiRobotu> createState() => _KodiRobotuState();
}

class _KodiRobotuState extends State<KodiRobotu> with TickerProviderStateMixin {
  // Hareket zamanı (0-1, 2,6 sn'de bir döner). Ekran her karede (60/sn) değil,
  // daha seyrek çizilir: Flutter'da tek bir şey kıpırdasa bile bütün pencere
  // yeniden birleştirilir; Kodi'nin hafif salınması için 60 kare gereksiz.
  //  - konuşurken / düşünürken / dinlerken / el sallarken: 24 kare/sn
  //  - boşta: 12 kare/sn; uzun süre bir şey olmazsa salınma durur.
  static const _devir = 2600;
  static const _etkinAralik = Duration(milliseconds: 42);
  static const _bostaAralik = Duration(milliseconds: 83);
  static const _dinlenmeSuresi = Duration(seconds: 20);
  final _zaman = ValueNotifier<double>(0);
  final _saat = Stopwatch()..start();
  Timer? _zamanZamanlayici;
  Duration? _aralik;
  DateTime _sonEtkinlik = DateTime.now();

  late final AnimationController _kirp = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 180));
  Timer? _kirpZamanlayici;
  final _rastgele = math.Random();

  bool get _etkin => widget.ifade != KodiIfadesi.mutlu || widget.elSalla;

  @override
  void initState() {
    super.initState();
    _kirpmayiKur();
    _hiziAyarla();
  }

  @override
  void didUpdateWidget(KodiRobotu eski) {
    super.didUpdateWidget(eski);
    if (eski.ifade != widget.ifade || eski.elSalla != widget.elSalla) {
      _sonEtkinlik = DateTime.now();
      _hiziAyarla();
    }
  }

  void _hiziAyarla() {
    final aralik = _etkin ? _etkinAralik : _bostaAralik;
    if (aralik == _aralik && _zamanZamanlayici != null) return;
    _aralik = aralik;
    _zamanZamanlayici?.cancel();
    _zamanZamanlayici = Timer.periodic(aralik, (_) {
      if (!mounted) return;
      if (!_etkin && DateTime.now().difference(_sonEtkinlik) > _dinlenmeSuresi) {
        // Dinleniyor: salınma durur (göz kırpma sürer).
        _zamanZamanlayici?.cancel();
        _zamanZamanlayici = null;
        return;
      }
      _zaman.value = (_saat.elapsedMilliseconds % _devir) / _devir;
    });
  }

  void _kirpmayiKur() {
    _kirpZamanlayici = Timer(
        Duration(milliseconds: 2200 + _rastgele.nextInt(2600)), () async {
      if (!mounted) return;
      await _kirp.forward();
      if (!mounted) return;
      await _kirp.reverse();
      if (mounted) _kirpmayiKur();
    });
  }

  @override
  void dispose() {
    _kirpZamanlayici?.cancel();
    _zamanZamanlayici?.cancel();
    _zaman.dispose();
    _kirp.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Kodi kendi çizim katmanında: kıpırdadıkça yalnızca o yeniden çizilir.
    return RepaintBoundary(
     child: SizedBox(
      width: widget.boy * 100 / 130,
      height: widget.boy,
      child: AnimatedBuilder(
        animation: Listenable.merge([_zaman, _kirp]),
        builder: (context, _) {
          final t = _zaman.value;
          // Konuşurken ağız saniyede ~6 kez açılıp kapanır.
          final agiz = widget.ifade == KodiIfadesi.konusuyor
              ? (0.5 + 0.5 * math.sin(t * 2 * math.pi * 15)).clamp(0.0, 1.0)
              : 0.0;
          return CustomPaint(
            painter: KodiRessami(
              ifade: widget.ifade,
              t: t,
              goz: 1 - _kirp.value,
              agiz: agiz,
              elSalla: widget.elSalla,
              aynala: widget.solaBak && widget.ifade == KodiIfadesi.dusunceli,
            ),
          );
        },
      ),
     ),
    );
  }
}

/// Sol şerit için küçük Kodi yüzü.
class KodiSimgesi extends StatelessWidget {
  final double boyut;
  final bool soluk;
  const KodiSimgesi({super.key, this.boyut = 24, this.soluk = false});
  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: soluk ? 0.75 : 1,
      child: SizedBox(
        width: boyut,
        height: boyut,
        child: const CustomPaint(painter: KodiRessami(sadeceBas: true)),
      ),
    );
  }
}

// ============================================================================
// KODİ KATMANI: robot + konuşma balonu
// ============================================================================

/// Çalışma alanının üstünde duran Kodi katmanı. Kodi açılınca sağdan kayarak
/// gelir, kapanınca kayarak gider. Basılı tutup sürüklenince taşınır (yeri
/// hatırlanır), çift tıklanınca varsayılan yerine döner. Katmanın boş
/// kısımları tıklamaları alttaki panellere geçirir.
class KodiKatmani extends StatefulWidget {
  /// Varsayılan yer: alanın sağ kenarından ve alt kenarından uzaklık
  /// (editörün sağ altı, terminalin üstü).
  final double varsayilanSag;
  final double varsayilanAlt;

  /// Masaüstü penceresinde: robot hep sağ altta; basılı tutup sürükleyince
  /// pencerenin kendisi taşınır.
  final bool pencereKipi;
  const KodiKatmani(
      {super.key, this.varsayilanSag = 20, this.varsayilanAlt = 8, this.pencereKipi = false});
  @override
  State<KodiKatmani> createState() => _KodiKatmaniState();
}

class _KodiKatmaniState extends State<KodiKatmani>
    with SingleTickerProviderStateMixin {
  late final AnimationController _kayma = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 700));
  late final Animation<double> _egri = CurvedAnimation(
      parent: _kayma, curve: Curves.easeOutBack, reverseCurve: Curves.easeInCubic);
  final _yaziDurumu = _KodiYaziDurumu();
  late final KodiProvider _kodi;
  bool _oncekiAcik = false;
  bool _vardi = false; // kayma bitti: balon açılır
  bool _elSalla = false;
  Timer? _zamanlayici;

  /// Sürüklenirken robotun sol üst köşesi.
  Offset? _surukle;
  Offset _surukleBaslangic = Offset.zero;

  /// Taşınmış yer (alana göre oran); ayardan da okunur.
  Offset? _kesir;
  bool _varsayilanaDondu = false;

  /// Balonun elle verilen boyutu (köşedeki tutamaçla); null: içeriğe göre.
  Size? _balonBoyutu;
  bool _balonVarsayilan = false;
  Size _boyutBaslangic = Size.zero;

  final _balonAnahtari = GlobalKey(debugLabel: 'kodi-balon');
  final _robotAnahtari = GlobalKey(debugLabel: 'kodi-robot');
  String _sonBolge = '';

  /// Masaüstü penceresi: yalnızca robot ve balon tıklanabilir, aradaki saydam
  /// alanda tıklamalar alttaki pencerelere geçer.
  void _bolgeyiGuncelle() {
    if (!widget.pencereKipi || !mounted) return;
    final parcalar = <List<double>>[];
    for (final (anahtar, yaricap) in [(_robotAnahtari, 0.0), (_balonAnahtari, 18.0)]) {
      final kutu = anahtar.currentContext?.findRenderObject();
      if (kutu is! RenderBox || !kutu.hasSize) continue;
      final o = kutu.localToGlobal(Offset.zero);
      parcalar.add([o.dx - 2, o.dy - 2, kutu.size.width + 4, kutu.size.height + 4, yaricap]);
    }
    if (parcalar.isEmpty) return;
    final imza = parcalar.map((e) => e.map((x) => x.round()).join(',')).join(';');
    if (imza == _sonBolge) return;
    _sonBolge = imza;
    kodiPenceresiKanali.invokeMethod('bolge', parcalar).catchError((_) => null);
  }

  /// Ana pencere: tarayıcı sayfası ayrı bir pencerede çizildiği için Kodi'nin
  /// (robot ve balon) olduğu yerler o pencereden kesilir; Kodi sayfanın
  /// üstünde görünür kalır.
  Timer? _tarayiciZamanlayici;
  void _tarayiciyaBildir() {
    if (!mounted || !kTarayici.hazir) return;
    final ogeler = <Rect>[];
    if (_kodi.acik && !_kodi.masaustunde) {
      for (final anahtar in [_robotAnahtari, _balonAnahtari]) {
        final kutu = anahtar.currentContext?.findRenderObject();
        if (kutu is! RenderBox || !kutu.hasSize || !kutu.attached) continue;
        final o = kutu.localToGlobal(Offset.zero);
        ogeler.add((o & kutu.size).inflate(1));
      }
    }
    kTarayici.ustOgeleriBildir(ogeler);
  }

  /// Sürüklenirken robotun sınırlanmamış yeri: pencerenin dışına taşarsa
  /// Kodi masaüstüne çıkar.
  bool _disarida = false;
  Offset _surukleFareIlk = Offset.zero;
  Timer? _bolgeZamanlayici;

  @override
  void initState() {
    super.initState();
    _kodi = context.read<KodiProvider>();
    _kodi.addListener(_kodiDegisti);
    // Kodi masaüstündeyken de sorular bağlamla cevaplansın, işler yapılsın.
    _kodi.dusunmeOku = () => context.read<SettingsProvider>().getBool('kodi_dusunme');
    _kodi.sesliOku = () => context.read<SettingsProvider>().getBool('kodi_sesli');
    if (!widget.pencereKipi) {
      _kodi.baglamUret = () => kodiBaglami(context);
      _kodi.eylemUygula = (e, {hedef}) => kodiEylemUygula(context, e, hedef: hedef);
      _kodi.ayarlarAc = () => context.read<EditorProvider>().openSettings();
      _kodi.ayarlariYenile = () => context.read<SettingsProvider>().load();
      // Ayarlar yüklenmeden "yapay zekâ yok" denmez.
      _kodi.modelVarOku = () {
        final s = context.read<SettingsProvider>();
        return !s.loaded || s.kodiAtamasi != null;
      };
      _kodi.rehberAcici = () => kodiKurulumRehberi(context);
      _kodi.sohbetiYukle();
      if (!Platform.environment.containsKey('FLUTTER_TEST')) {
        _tarayiciZamanlayici =
            Timer.periodic(const Duration(milliseconds: 80), (_) => _tarayiciyaBildir());
      }
    } else {
      // Balon büyüyüp küçüldükçe (yeni mesaj, kod kutusu, onay kartı)
      // tıklanabilir alan da onunla birlikte değişsin.
      _bolgeZamanlayici =
          Timer.periodic(const Duration(milliseconds: 120), (_) => _bolgeyiGuncelle());
    }
    if (_kodi.acik) {
      _oncekiAcik = true;
      _gel();
    }
  }

  @override
  void dispose() {
    _kodi.removeListener(_kodiDegisti);
    _zamanlayici?.cancel();
    _bolgeZamanlayici?.cancel();
    _tarayiciZamanlayici?.cancel();
    _kayma.dispose();
    _yaziDurumu.dispose();
    super.dispose();
  }

  void _kodiDegisti() {
    if (!mounted || _kodi.acik == _oncekiAcik) return;
    _oncekiAcik = _kodi.acik;
    _kodi.acik ? _gel() : _git();
  }

  void _gel() {
    _zamanlayici?.cancel();
    setState(() {
      _vardi = false;
      _elSalla = true;
    });
    _kayma.forward().then((_) {
      if (!mounted || !_kodi.acik) return;
      setState(() => _vardi = true);
      // Selam, balon kurulduktan sonra gelir ki harf harf yazılsın.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _kodi.selamVer();
      });
      _zamanlayici = Timer(const Duration(milliseconds: 2600), () {
        if (mounted) setState(() => _elSalla = false);
      });

    });
  }

  void _git() {
    _zamanlayici?.cancel();
    setState(() => _elSalla = false);
    // Balon robotla birlikte kayarak gider; kayma bitince kaldırılır.
    _kayma.reverse().then((_) {
      if (mounted && !_kodi.acik) setState(() => _vardi = false);
    });
  }

  Offset? _ayardakiKesir(Object? ayar) {
    if (_varsayilanaDondu) return null;
    if (_kesir != null) return _kesir;
    if (ayar is List && ayar.length == 2 && ayar[0] is num && ayar[1] is num) {
      return Offset((ayar[0] as num).toDouble(), (ayar[1] as num).toDouble());
    }
    return null;
  }

  Size? _ayardakiBoyut(Object? ayar) {
    if (_balonVarsayilan) return null;
    if (_balonBoyutu != null) return _balonBoyutu;
    if (ayar is List && ayar.length == 2 && ayar[0] is num && ayar[1] is num) {
      return Size((ayar[0] as num).toDouble(), (ayar[1] as num).toDouble());
    }
    return null;
  }

  void _boyutuKaydet(Size? s) {
    context
        .read<SettingsProvider>()
        .setValue('kodi_balon', s == null ? null : [s.width.round(), s.height.round()])
        .catchError((_) {});
  }

  void _konumuKaydet(Offset? kesir) {
    final s = context.read<SettingsProvider>();
    s
        .setValue('kodi_konum', kesir == null ? null : [kesir.dx, kesir.dy])
        .catchError((_) {});
  }

  @override
  Widget build(BuildContext context) {
    final acik = context.select<KodiProvider, bool>((k) => k.acik);
    final cikiyor = context.select<KodiProvider, bool>((k) => k.masaustuneCikiyor);
    final ayar =
        context.select<SettingsProvider, Object?>((s) => s.get<dynamic>('kodi_konum'));
    final boyutAyari =
        context.select<SettingsProvider, Object?>((s) => s.get<dynamic>('kodi_balon'));
    if (!acik && _kayma.isDismissed) return const SizedBox.shrink();
    if (widget.pencereKipi) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _bolgeyiGuncelle());
    }
    return ChangeNotifierProvider<_KodiYaziDurumu>.value(
      value: _yaziDurumu,
      child: LayoutBuilder(builder: (context, kisit) {
        final w = kisit.maxWidth;
        final h = kisit.maxHeight;
        final rh = h < 420 ? 92.0 : 116.0;
        final rw = rh * 100 / 130;
        double sinirla(double v, double lo, double hi) =>
            v.clamp(lo, math.max(lo, hi)).toDouble();

        final kesir = widget.pencereKipi ? null : _ayardakiKesir(ayar);
        var konum = _surukle ??
            (kesir != null
                ? Offset(kesir.dx * (w - rw), kesir.dy * (h - rh))
                : Offset(w - widget.varsayilanSag - rw,
                    h - widget.varsayilanAlt - rh));
        konum = Offset(sinirla(konum.dx, 4, w - rw - 4), sinirla(konum.dy, 4, h - rh - 4));

        // Balon, robotun üstünde mi altında mı daha çok yer varsa oraya açılır.
        final ustte = konum.dy >= h - (konum.dy + rh);
        final boyut = _ayardakiBoyut(boyutAyari);
        final bw = sinirla(boyut?.width ?? 380, math.min(260, w - 16), w - 16);
        final bSol = sinirla(konum.dx + rw - bw + 6, 8, w - bw - 8);
        final kuyrukX = sinirla(konum.dx + rw / 2 - bSol, 26, bw - 26);
        final yer = ustte ? konum.dy - 6 : h - (konum.dy + rh) - 6;
        // Balonun en fazla yüksekliği: robotun yanındaki yer; yer çok azsa
        // en az 140 (pencere ona da yetmiyorsa pencere kadar). Eskiden yer
        // azken 140'lık balon pencerenin üstünden taşıyor, başlıktaki
        // düğmeler (kapat ...) erişilemez oluyordu: balon artık pencerenin
        // içinde kalacak kadar kaydırılır (gerekirse robotun üstüne biner).
        final balonYer = math.max(yer, math.max(0.0, math.min(140.0, h - 12)));
        final bh = boyut == null
            ? null
            : sinirla(boyut.height, math.min(180, yer), balonYer);
        final balonUst = math.min(konum.dy + rh + 2, h - 4 - (bh ?? balonYer));
        final balonAlt = math.min(h - konum.dy + 2, h - 4 - (bh ?? balonYer));

        final robot = RawGestureDetector(
          gestures: {
            // Basılı tutup beklemeden, fare kımıldar kımıldamaz sürüklenir
            // (eskiden yarım saniyeye yakın basılı tutmak gerekiyordu; aceleci
            // kullanıcıda sürükleme hiç başlamıyordu).
            PanGestureRecognizer:
                GestureRecognizerFactoryWithHandlers<PanGestureRecognizer>(
              // down: robot basılan noktadan itibaren fareyi birebir izler.
              () => PanGestureRecognizer()..dragStartBehavior = DragStartBehavior.down,
              (r) {
                r.onStart = (s) {
                  _surukleFareIlk = s.globalPosition;
                  if (widget.pencereKipi) {
                    // Pencerenin kendisi taşınır (Windows'un taşıma döngüsü).
                    // Bırakıldığı yerde kalır: eskiden TürKod'un üstüne
                    // bırakılınca geri dönüyordu; TürKod ekranın çoğunu
                    // kapladığı için Kodi'yi taşımak isteyen kullanıcı onu
                    // "kayboldu" sanıyordu. Geri dönmek: düğme ya da çift tık.
                    kodiPenceresiKanali.invokeMethod<bool>('surukle').catchError((_) => null);
                    return;
                  }
                  setState(() {
                    _surukle = konum;
                    _surukleBaslangic = konum;
                  });
                };
                r.onUpdate = (d) {
                  if (widget.pencereKipi || _surukle == null) return;
                  setState(() {
                    final ham = _surukleBaslangic + (d.globalPosition - _surukleFareIlk);
                    _surukle = ham;
                    // Robotun yarıya yakını pencerenin dışındaysa: masaüstü.
                    _disarida = ham.dx < -rw * 0.4 ||
                        ham.dy < -rh * 0.4 ||
                        ham.dx > w - rw * 0.6 ||
                        ham.dy > h - rh * 0.6;
                  });
                };
                r.onEnd = (_) {
                  if (widget.pencereKipi || _surukle == null) return;
                  if (_disarida) {
                    setState(() {
                      _surukle = null;
                      _disarida = false;
                    });
                    _kodi.masaustuneCik();
                    return;
                  }
                  final son = _surukle ?? konum;
                  final yeni = Offset(
                    w - rw <= 0 ? 0 : (sinirla(son.dx, 4, w - rw - 4) / (w - rw)),
                    h - rh <= 0 ? 0 : (sinirla(son.dy, 4, h - rh - 4) / (h - rh)),
                  );
                  setState(() {
                    _surukle = null;
                    _kesir = yeni;
                    _varsayilanaDondu = false;
                  });
                  _konumuKaydet(yeni);
                };
                // Sürükleme yarıda kesilirse (pencere odağı gitti ...) Kodi
                // "sürükleniyor" hâlinde takılı kalmaz, yerine döner.
                r.onCancel = () {
                  if (_surukle == null && !_disarida) return;
                  setState(() {
                    _surukle = null;
                    _disarida = false;
                  });
                };
              },
            ),
            DoubleTapGestureRecognizer:
                GestureRecognizerFactoryWithHandlers<DoubleTapGestureRecognizer>(
              () => DoubleTapGestureRecognizer(),
              (r) => r.onDoubleTap = () {
                if (widget.pencereKipi) return _kodi.masaustundenDon();
                setState(() {
                  _kesir = null;
                  _varsayilanaDondu = true;
                });
                _konumuKaydet(null);
              },
            ),
          },
          child: MouseRegion(
            cursor: _surukle != null
                ? SystemMouseCursors.grabbing
                : SystemMouseCursors.grab,
            child: AnimatedScale(
              scale: _surukle != null ? 1.08 : 1,
              duration: const Duration(milliseconds: 150),
              child: _KodiCanli(
                  boy: rh,
                  elSalla: _elSalla || _surukle != null,
                  // Düşünürken pencerenin ortasına bakar (eskiden hep sağa
                  // bakıyor, sağ köşedeyken duvara dönüyordu). Masaüstünde
                  // TürKod'un yeri bilinmez: balonuna bakar.
                  solaBak: widget.pencereKipi
                      ? bSol + bw / 2 < konum.dx + rw / 2
                      : konum.dx + rw / 2 > w / 2),
            ),
          ),
        );

        return AnimatedBuilder(
          animation: _egri,
          builder: (context, child) {
            final t = _egri.value;
            return Opacity(
              opacity: t.clamp(0.0, 1.0),
              child: Transform.translate(
                  offset: Offset((1 - t) * (w - konum.dx + 30), 0), child: child),
            );
          },
          child: Stack(children: [
            if (_vardi)
              Positioned(
                left: bSol,
                width: bw,
                top: ustte ? null : math.max(4.0, balonUst),
                bottom: ustte ? math.max(4.0, balonAlt) : null,
                child: TweenAnimationBuilder<double>(
                  key: _balonAnahtari,
                  tween: Tween(begin: 0, end: 1),
                  duration: const Duration(milliseconds: 280),
                  curve: Curves.easeOutBack,
                  builder: (context, v, child) => Transform.scale(
                    scale: 0.6 + 0.4 * v,
                    alignment: Alignment(
                        (kuyrukX / bw) * 2 - 1, ustte ? 1 : -1),
                    child: Opacity(opacity: v.clamp(0.0, 1.0), child: child),
                  ),
                  child: _KodiBalonu(
                    enFazlaYukseklik: balonYer,
                    sabitYukseklik: bh,
                    kuyrukX: kuyrukX,
                    kuyrukAltta: ustte,
                    // Köşedeki tutamaç: balon robotun üstündeyse sol üstte
                    // (yukarı/sola çekince büyür), altındaysa sol altta.
                    onBoyutBasla: (s) => _boyutBaslangic = s,
                    onBoyutDegis: (toplam) => setState(() {
                      _balonVarsayilan = false;
                      _balonBoyutu = Size(
                        _boyutBaslangic.width - toplam.dx,
                        _boyutBaslangic.height + (ustte ? -toplam.dy : toplam.dy),
                      );
                    }),
                    onBoyutBitti: () {
                      final s = _balonBoyutu;
                      if (s != null) {
                        // Kaydedilen boyut ekrana sığan boyuttur.
                        final kayit = Size(
                            sinirla(s.width, math.min(260, w - 16), w - 16),
                            sinirla(s.height, math.min(180, yer), balonYer));
                        setState(() => _balonBoyutu = kayit);
                        _boyutuKaydet(kayit);
                      }
                    },
                    onBoyutSifirla: () {
                      setState(() {
                        _balonBoyutu = null;
                        _balonVarsayilan = true;
                      });
                      _boyutuKaydet(null);
                    },
                  ),
                ),
              ),
            Positioned(
              key: _robotAnahtari,
              left: konum.dx,
              top: konum.dy,
              width: rw,
              height: rh,
              child: robot,
            ),
            if ((_disarida && _surukle != null) || cikiyor)
              Positioned(
                left: sinirla(konum.dx - 60, 4, w - 220),
                top: sinirla(konum.dy - 34, 4, h - 30),
                child: IgnorePointer(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                        color: _kKodiMor, borderRadius: BorderRadius.circular(10)),
                    child: Text(
                        cikiyor ? 'Masaüstüne çıkıyorum…' : 'Bırak, masaüstüne çıkayım!',
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600)),
                  ),
                ),
              ),
          ]),
        );
      }),
    );
  }
}

/// Sohbetin durumuna göre ifadesi değişen robot.
class _KodiCanli extends StatelessWidget {
  final double boy;
  final bool elSalla;
  final bool solaBak;
  const _KodiCanli({required this.boy, required this.elSalla, this.solaBak = false});

  @override
  Widget build(BuildContext context) {
    final k = context.watch<KodiProvider>();
    final yaziyor = context.watch<_KodiYaziDurumu>().yaziyor;
    final son = k.mesajlar.isEmpty ? null : k.mesajlar.last;
    final ifade = k.dinliyor
        ? KodiIfadesi.dinliyor
        // Cevap beklenirken ("Düşünüyorum" / "Hemen bakıyorum") Kodi konuşmaz,
        // düşünür: eli çenesinde, ağzı oynamaz.
        : k.bekliyor
        ? KodiIfadesi.dusunceli
        : yaziyor || k.konusuyor
            ? KodiIfadesi.konusuyor
            : (son != null && son.kodiden && son.hata)
                ? KodiIfadesi.uzgun
                : KodiIfadesi.mutlu;
    final robot = KodiRobotu(
        ifade: ifade, elSalla: elSalla && !k.bekliyor, boy: boy, solaBak: solaBak);
    // Masaüstü penceresinde ipucu baloncuğu tıklanabilir alanın dışına taşar.
    if (k.pencereKipi) return robot;
    return Tooltip(
      message: 'Kodi: üstüne basıp sürükleyerek taşıyabilirsin, '
          'çift tıklayınca yerine döner',
      waitDuration: const Duration(milliseconds: 1200),
      child: robot,
    );
  }
}

/// Balondaki yazının harf harf yazılıp yazılmadığı (robotun ağzı oynasın).
class _KodiYaziDurumu extends ChangeNotifier {
  bool _yaziyor = false;
  bool _kapandi = false;
  bool get yaziyor => _yaziyor;
  set yaziyor(bool v) {
    if (v == _yaziyor || _kapandi) return;
    _yaziyor = v;
    notifyListeners();
  }

  @override
  void dispose() {
    _kapandi = true;
    super.dispose();
  }
}

class _KodiBalonu extends StatefulWidget {
  final double enFazlaYukseklik;

  /// Elle verilmiş yükseklik (kuyruk dahil); null: içeriğe göre büyür.
  final double? sabitYukseklik;
  final double kuyrukX;
  final bool kuyrukAltta;
  final void Function(Size baslangic)? onBoyutBasla;
  final void Function(Offset toplam)? onBoyutDegis;
  final VoidCallback? onBoyutBitti;
  final VoidCallback? onBoyutSifirla;
  const _KodiBalonu(
      {required this.enFazlaYukseklik,
      this.sabitYukseklik,
      required this.kuyrukX,
      required this.kuyrukAltta,
      this.onBoyutBasla,
      this.onBoyutDegis,
      this.onBoyutBitti,
      this.onBoyutSifirla});
  @override
  State<_KodiBalonu> createState() => _KodiBalonuState();
}

class _KodiBalonuState extends State<_KodiBalonu> {
  final _girdi = TextEditingController();
  final _odak = FocusNode(debugLabel: 'kodi');
  final _kaydirma = ScrollController();
  late final KodiProvider _kodi;
  bool _oncekiBekliyor = false;
  late final _KodiYaziDurumu _yaziDurumu;

  /// Harf harf yazılan son mesaj ve şimdiye kadar yazılan harf sayısı.
  KodiMesaji? _yazilan;
  int _harf = 0;
  Timer? _yaziZamanlayici;
  int _gorulenMesaj = 0;

  @override
  void initState() {
    super.initState();
    _kodi = context.read<KodiProvider>();
    _yaziDurumu = context.read<_KodiYaziDurumu>();
    _gorulenMesaj = _kodi.mesajlar.length;
    // Yeni mesajlar sağlayıcı dinlenerek yakalanır (eskiden her çizimden
    // sonra bakılıp liste en alta kaydırılıyordu; kare bittikten sonra
    // yerleşimi bozmak fare izleyicisinde hata zinciri başlatıyordu).
    _kodi.addListener(_kodiDegisti);
  }

  @override
  void dispose() {
    _kodi.removeListener(_kodiDegisti);
    _yaziZamanlayici?.cancel();
    // Cevap yazılırken balon kapandıysa güvenli işleri yine yapılır
    // (eskiden hiç yapılmıyordu). Ağaç kilitliyken bildirim gitmesin diye
    // biraz sonra; sağlayıcı bir kez başlatır.
    final yarim = _yazilan;
    if (yarim != null && !yarim.eylemlerBasladi) {
      final k = _kodi;
      Future.microtask(() => k.eylemleriBaslat(yarim));
    }
    // Balon yarıda kapanırsa robotun ağzı açık kalmasın.
    final yd = _yaziDurumu;
    Future.microtask(() => yd.yaziyor = false);
    _girdi.dispose();
    _odak.dispose();
    _kaydirma.dispose();
    super.dispose();
  }

  /// Ters listede en alt = 0. Kaydırma, içinde bulunulan kare tamamen
  /// bittikten sonra yapılır (kare sonrası geri çağrıda yerleşimi bozmak fare
  /// izleyicisinde hataya yol açıyordu).
  void _enAltaDon() {
    scheduleMicrotask(() {
      if (mounted && _kaydirma.hasClients && _kaydirma.offset > 0) {
        _kaydirma.jumpTo(0);
      }
    });
  }

  void _kodiDegisti() {
    if (!mounted) return;
    final m = _kodi.mesajlar;
    if (m.length < _gorulenMesaj) _gorulenMesaj = 0; // yeni sohbet
    if (m.length > _gorulenMesaj || (_kodi.bekliyor && !_oncekiBekliyor)) {
      _enAltaDon();
    }
    _oncekiBekliyor = _kodi.bekliyor;
    if (m.length > _gorulenMesaj) {
      final yeni = m.sublist(_gorulenMesaj);
      _gorulenMesaj = m.length;
      for (final x in yeni.reversed) {
        if (x.kodiden && x.yazilsin) {
          _yazmayaBasla(x);
          break;
        }
      }
    }
    setState(() {});
  }

  void _yazmayaBasla(KodiMesaji m) {
    _yaziZamanlayici?.cancel();
    final onceki = _yazilan;
    if (onceki != null && _harf < onceki.metin.length) {
      _eylemleriBaslat(onceki);
    }
    _yazilan = m;
    _harf = 0;
    _yaziDurumu.yaziyor = true;
    // Uzun cevaplar daha hızlı yazılır (en fazla ~6 saniye sürer).
    final adim = math.max(1, (m.metin.length * m.harfMs / 6000).ceil());
    _yaziZamanlayici = Timer.periodic(Duration(milliseconds: m.harfMs), (zaman) {
      if (!mounted) return zaman.cancel();
      setState(() => _harf = math.min(m.metin.length, _harf + adim));
      if (_harf >= m.metin.length) {
        zaman.cancel();
        _yaziBitti();
      }
    });
  }

  void _yaziyiTamamla() {
    final m = _yazilan;
    if (m == null || _harf >= m.metin.length) return;
    _yaziZamanlayici?.cancel();
    setState(() => _harf = m.metin.length);
    _yaziBitti();
  }

  void _yaziBitti() {
    _yaziDurumu.yaziyor = false;
    final m = _yazilan;
    if (m != null) _eylemleriBaslat(m);
    if (_kodi.mesajlar.length == 1) {
      // "Merhaba, ben Kodi!" bitti: kısa bir duraklamadan sonra devam.
      Timer(const Duration(milliseconds: 650), () {
        if (mounted) _kodi.selamDevam();
      });
    }
  }

  /// Cevap yazılınca güvenli eylemler (panel, dosya, sekme ...) sırayla
  /// yapılır; diğerleri izin kartıyla bekler.
  void _eylemleriBaslat(KodiMesaji m) => _kodi.eylemleriBaslat(m);

  bool get _kodSekmesiVar =>
      _kodi.pencereKipi ? _kodi.uzakKodSekmesiVar : kodiKodSekmesiVar(context);

  Future<void> _uygula(KodiEylemi e, {String? hedef}) =>
      _kodi.eylemiUygula(e, hedef: hedef);

  void _reddet(KodiEylemi e) {
    // Yapılmakta olan iş "Vazgeçildi" diye işaretlenmez (iş yine biter).
    if (e.durum != 'bekliyor') return;
    e.durum = 'reddedildi';
    e.sonuc = 'Vazgeçildi';
    _kodi.yenile();
  }

  void _gonder({String? hazir}) {
    final s = context.read<SettingsProvider>();
    final metin = (hazir ?? _girdi.text).trim();
    if (metin.isEmpty || _kodi.bekliyor) return;
    _yaziyiTamamla();
    if (hazir == null) _girdi.clear();
    _kodi.sor(metin, dusunme: s.getBool('kodi_dusunme'));
    _odak.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final k = _kodi;
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final koyu = theme.brightness == Brightness.dark;
    final zemin = koyu
        ? Color.alphaBlend(cs.primary.withValues(alpha: 0.06), cs.surfaceContainerHigh)
        : Colors.white;
    final kenar = cs.primary.withValues(alpha: koyu ? 0.45 : 0.35);
    final dusunme = context.select<SettingsProvider, bool>(
        (s) => s.getBool('kodi_dusunme'));
    final sesli = context.select<SettingsProvider, bool>((s) => s.getBool('kodi_sesli'));
    final goruntu = context.select<SettingsProvider, String>(
        (s) => s.getString(kKodiGoruntu, fallback: 'kapali'));
    final model = context.select<SettingsProvider, String?>((s) {
      final a = s.kodiAtamasi;
      return a == null ? null : s.atamaEtiketi(a);
    });

    final baloncuklar = <Widget>[];
    for (var i = 0; i < k.mesajlar.length && i < _gorulenMesaj; i++) {
      final m = k.mesajlar[i];
      final buMu = identical(m, _yazilan);
      final yaziliyor = buMu && _harf < m.metin.length;
      baloncuklar.add(m.kodiden
          ? _KodiSozu(
              mesaj: m,
              metin: buMu ? m.metin.substring(0, _harf) : m.metin,
              imlec: yaziliyor,
              kodSekmesiVar: _kodSekmesiVar,
              onIzin: _uygula,
              onRet: _reddet,
            )
          : _SeninSozun(metin: m.metin, goruntu: m.goruntu, otomatik: m.otomatik));
    }
    if (k.bekliyor) baloncuklar.add(_KodiDusunuyor(dusunme: dusunme));
    // Daha hiçbir şey sorulmadıysa, selam yazılıp bitince hazır sorular.
    final selamBitti = k.mesajlar.isNotEmpty &&
        (k.mesajlar.length >= 2 || k.mesajlar.first.metin != kKodiSelam) &&
        (_yazilan == null || _harf >= _yazilan!.metin.length);
    if (!k.bekliyor && k.henuzSorulmadi && selamBitti && _gorulenMesaj == k.mesajlar.length) {
      baloncuklar.add(Padding(
        padding: const EdgeInsets.only(top: 6, bottom: 2),
        child: Wrap(spacing: 6, runSpacing: 6, children: [
          for (final soru in kKodiHazirSorular)
            ActionChip(
              label: Text(soru, style: const TextStyle(fontSize: 12)),
              avatar: const Icon(Icons.chat_bubble_outline_rounded, size: 14),
              visualDensity: VisualDensity.compact,
              side: BorderSide(color: _kKodiMor.withValues(alpha: 0.45)),
              backgroundColor: _kKodiMor.withValues(alpha: 0.10),
              onPressed: () => _gonder(hazir: soru),
            ),
        ]),
      ));
    }

    final sabit = widget.sabitYukseklik;
    final balon = Container(
      constraints: sabit != null
          ? BoxConstraints.tightFor(height: sabit)
          : BoxConstraints(maxHeight: widget.enFazlaYukseklik),
      child: CustomPaint(
        painter: _BalonKuyrugu(
            zemin: zemin, kenar: kenar, x: widget.kuyrukX, altta: widget.kuyrukAltta),
        child: Container(
          margin: EdgeInsets.only(
              bottom: widget.kuyrukAltta ? 10 : 0, top: widget.kuyrukAltta ? 0 : 10),
          decoration: BoxDecoration(
            color: zemin,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: kenar, width: 1.4),
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withValues(alpha: koyu ? 0.45 : 0.16),
                  blurRadius: 18,
                  offset: const Offset(0, 6)),
            ],
          ),
          child: Column(
              mainAxisSize: sabit != null ? MainAxisSize.max : MainAxisSize.min,
              children: [
            // Başlık: ad, düşünme düğmesi, yeni sohbet, kapat.
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 6, 0),
              child: Row(children: [
                Text('Kodi',
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: koyu ? const Color(0xFFB9A6FF) : _kKodiMorKoyu)),
                const SizedBox(width: 6),
                Tooltip(
                  message: model == null
                      ? 'Kodi\'ye bağlı bir yapay zekâ yok (Ayarlar → Yapay Zekâ: Görevler)'
                      : 'Kodi şu modelle konuşuyor: $model',
                  child: Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(
                        color: model == null
                            ? cs.error
                            : k.bekliyor
                                ? const Color(0xFFF59E0B)
                                : const Color(0xFF22C55E),
                        shape: BoxShape.circle),
                  ),
                ),
                const SizedBox(width: 8),
                // Balon daraltılınca düğmeler taşmaz, alt satıra akar (eskiden
                // tek satıra sıkışıp balonun dışına taşıyordu).
                Expanded(
                  child: Wrap(alignment: WrapAlignment.end, children: [
                PanelDugmesi(
                  ikon: k.sohbetlerAcik ? Icons.forum_rounded : Icons.forum_outlined,
                  ipucu: 'Sohbetler: eski sohbetlerin, yeni sohbet',
                  secili: k.sohbetlerAcik,
                  onPressed: k.bekliyor ? null : k.sohbetlerDegistir,
                ),
                PanelDugmesi(
                  ikon: switch (goruntu) {
                    'pencere' => Icons.web_asset_rounded,
                    'ekran' => Icons.desktop_windows_outlined,
                    _ => Icons.no_photography_outlined,
                  },
                  ipucu: switch (goruntu) {
                    'pencere' => 'Mesajla TürKod penceresinin görüntüsü gidiyor. '
                        'Bas: bütün ekran.',
                    'ekran' => 'Mesajla bütün ekranın görüntüsü gidiyor. Bas: kapat.',
                    _ => 'Görüntü gönderilmiyor. Bas: mesajla TürKod penceresinin '
                        'görüntüsü gitsin.',
                  },
                  secili: goruntu != 'kapali',
                  onPressed: () => context
                      .read<SettingsProvider>()
                      .setValue(kKodiGoruntu, switch (goruntu) {
                        'kapali' => 'pencere',
                        'pencere' => 'ekran',
                        _ => 'kapali',
                      })
                      .catchError((_) {}),
                ),
                PanelDugmesi(
                  ikon: k.canli
                      ? Icons.record_voice_over_rounded
                      : Icons.record_voice_over_outlined,
                  ipucu: k.canli
                      ? 'Canlı sohbet açık: Kodi dinler, cevaplar, yine dinler. Kapatmak için bas.'
                      : 'Canlı sohbet: elini klavyeye sürmeden Kodi ile konuş',
                  secili: k.canli,
                  onPressed: k.canliDegistir,
                ),
                PanelDugmesi(
                  ikon: sesli ? Icons.volume_up_rounded : Icons.volume_off_rounded,
                  ipucu: sesli
                      ? 'Sesli cevap açık: Kodi cevaplarını okur. Kapatmak için bas.'
                      : 'Sesli cevap kapalı: açarsan Kodi cevaplarını sesli okur',
                  secili: sesli,
                  onPressed: () {
                    if (sesli) k.sus();
                    context
                        .read<SettingsProvider>()
                        .setValue('kodi_sesli', !sesli)
                        .catchError((_) {});
                  },
                ),
                PanelDugmesi(
                  ikon: dusunme
                      ? Icons.lightbulb_rounded
                      : Icons.lightbulb_outline_rounded,
                  ipucu: dusunme
                      ? 'Düşünme açık: Kodi cevap vermeden önce düşünür (daha yavaş). '
                          'Kapatmak için bas.'
                      : 'Düşünme kapalı: Kodi hemen cevap verir. Açmak için bas.',
                  secili: dusunme,
                  onPressed: () => context
                      .read<SettingsProvider>()
                      .setValue('kodi_dusunme', !dusunme)
                      .catchError((_) {}),
                ),
                PanelDugmesi(
                  ikon: Icons.restart_alt_rounded,
                  ipucu: 'Yeni sohbet',
                  onPressed: k.bekliyor ? null : () => k.temizle(),
                ),
                k.pencereKipi
                    ? PanelDugmesi(
                        ikon: Icons.login_rounded,
                        ipucu: 'TürKod\'a dön (Kodi\'ye çift tıklamak da olur)',
                        onPressed: k.masaustundenDon,
                      )
                    : PanelDugmesi(
                        ikon: Icons.open_in_new_rounded,
                        ipucu: 'Masaüstüne çık (TürKod penceresinin dışında dursun). '
                            'Kodi\'yi pencerenin dışına sürükleyerek de çıkarabilirsin.',
                        onPressed: k.masaustuneCik,
                      ),
                PanelDugmesi(
                  ikon: Icons.close_rounded,
                  ipucu: 'Kodi gitsin',
                  onPressed: k.kapat,
                ),
                  ]),
                ),
              ]),
            ),
            Divider(
                height: 8,
                indent: 12,
                endIndent: 12,
                color: cs.outlineVariant.withValues(alpha: 0.7)),
            if (k.sohbetlerAcik)
              Flexible(
                fit: sabit != null ? FlexFit.tight : FlexFit.loose,
                child: _SohbetlerPaneli(kodi: k),
              )
            else
            Flexible(
              fit: sabit != null ? FlexFit.tight : FlexFit.loose,
              child: GestureDetector(
                behavior: HitTestBehavior.translucent,
                // Balona tıklayınca yazı beklemeden tamamlanır.
                onTap: _yaziyiTamamla,
                child: SelectionArea(
                  // Yeni mesajda seçim sıfırlanır: yazı seçiliyken liste en
                  // alta dönmüyor, yeni mesaj görünmüyordu.
                  key: ValueKey(k.mesajlar.length),
                  // Sohbet sığmayınca sağda kaydırma çubuğu görünür.
                  child: Scrollbar(
                    controller: _kaydirma,
                    thumbVisibility: true,
                    // Ters liste: en yeni mesaj hep altta görünür.
                    child: ListView(
                      controller: _kaydirma,
                      reverse: true,
                      shrinkWrap: sabit == null,
                      padding: const EdgeInsets.fromLTRB(14, 6, 18, 6),
                      children: baloncuklar.reversed.toList(),
                    ),
                  ),
                ),
              ),
            ),
            if (k.dinliyor || k.konusuyor)
              _SesSeridi(
                dinliyor: k.dinliyor,
                onDur: k.dinliyor ? k.dinle : k.sus,
              ),
            // Soru kutusu.
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 2, 8, 10),
              child: Row(children: [
                Expanded(
                  child: CallbackShortcuts(
                    bindings: {
                      const SingleActivator(LogicalKeyboardKey.enter): _gonder,
                      const SingleActivator(LogicalKeyboardKey.numpadEnter): _gonder,
                      const SingleActivator(LogicalKeyboardKey.escape): k.kapat,
                    },
                    child: TextField(
                      controller: _girdi,
                      focusNode: _odak,
                      minLines: 1,
                      maxLines: 4,
                      enabled: !k.bekliyor,
                      style: const TextStyle(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: k.bekliyor
                            ? 'Kodi cevaplıyor…'
                            : 'Kodi\'ye bir şey sor…',
                        hintStyle: TextStyle(
                            fontSize: 12.5,
                            color: cs.onSurface.withValues(alpha: 0.5)),
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 9),
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: BorderSide(color: cs.outlineVariant)),
                        enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: BorderSide(color: cs.outlineVariant)),
                        focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide:
                                const BorderSide(color: _kKodiMor, width: 1.5)),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                IconButton(
                  tooltip: k.dinliyor
                      ? 'Dinlemeyi bırak'
                      : 'Sesle sor: bas ve konuş, susunca Kodi anlar',
                  style: IconButton.styleFrom(
                    foregroundColor: k.dinliyor ? const Color(0xFFEF4444) : _kKodiMor,
                    minimumSize: const Size(34, 34),
                  ),
                  iconSize: 19,
                  onPressed: k.bekliyor || k.canli ? null : k.dinle,
                  icon: Icon(k.dinliyor ? Icons.mic_rounded : Icons.mic_none_rounded),
                ),
                IconButton.filled(
                  tooltip: k.bekliyor ? 'Vazgeç (cevabı bekleme)' : 'Gönder (Enter)',
                  style: IconButton.styleFrom(
                    backgroundColor:
                        k.bekliyor ? const Color(0xFFEF4444) : _kKodiMor,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(34, 34),
                  ),
                  iconSize: 17,
                  onPressed: k.bekliyor ? k.vazgec : _gonder,
                  icon: Icon(k.bekliyor ? Icons.stop_rounded : Icons.send_rounded),
                ),
              ]),
            ),
          ]),
        ),
      ),
    );
    if (widget.onBoyutDegis == null) return balon;
    final ust = widget.kuyrukAltta; // balon robotun üstünde: tutamaç sol üstte
    return Stack(children: [
      balon,
      Positioned(
        left: 3,
        top: ust ? 3 : null,
        bottom: ust ? null : 3,
        child: _BoyutTutamaci(
          ust: ust,
          onBasla: () {
            final s = context.size;
            if (s != null) widget.onBoyutBasla?.call(s);
          },
          onDegis: widget.onBoyutDegis!,
          onBitti: widget.onBoyutBitti,
          onSifirla: widget.onBoyutSifirla,
        ),
      ),
    ]);
  }
}

/// Balonun köşesindeki boyutlandırma tutamacı: sürükleyince genişlik ve
/// yükseklik değişir, çift tıklayınca varsayılana döner.
class _BoyutTutamaci extends StatefulWidget {
  final bool ust;
  final VoidCallback onBasla;
  final void Function(Offset toplam) onDegis;
  final VoidCallback? onBitti;
  final VoidCallback? onSifirla;
  const _BoyutTutamaci(
      {required this.ust,
      required this.onBasla,
      required this.onDegis,
      this.onBitti,
      this.onSifirla});
  @override
  State<_BoyutTutamaci> createState() => _BoyutTutamaciState();
}

class _BoyutTutamaciState extends State<_BoyutTutamaci> {
  Offset _toplam = Offset.zero;
  bool _uzerinde = false;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Tooltip(
      message: 'Balonu büyütmek ya da küçültmek için sürükle '
          '(çift tıkla: varsayılan boyut)',
      waitDuration: const Duration(milliseconds: 800),
      child: MouseRegion(
        cursor: widget.ust
            ? SystemMouseCursors.resizeUpLeftDownRight
            : SystemMouseCursors.resizeUpRightDownLeft,
        onEnter: (_) => setState(() => _uzerinde = true),
        onExit: (_) => setState(() => _uzerinde = false),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanStart: (_) {
            _toplam = Offset.zero;
            widget.onBasla();
          },
          onPanUpdate: (d) {
            _toplam += d.delta;
            widget.onDegis(_toplam);
          },
          onPanEnd: (_) => widget.onBitti?.call(),
          onDoubleTap: widget.onSifirla,
          child: SizedBox(
            width: 18,
            height: 18,
            child: CustomPaint(
              painter: _TutamacRessami(
                  renk: cs.onSurface.withValues(alpha: _uzerinde ? 0.75 : 0.35),
                  ust: widget.ust),
            ),
          ),
        ),
      ),
    );
  }
}

class _TutamacRessami extends CustomPainter {
  final Color renk;
  final bool ust;
  const _TutamacRessami({required this.renk, required this.ust});

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = renk
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round;
    // Köşeye bakan üç kısa çapraz çizgi.
    for (final k in const [5.0, 9.5, 14.0]) {
      if (ust) {
        canvas.drawLine(Offset(3, 3 + k), Offset(3 + k, 3), p);
      } else {
        canvas.drawLine(Offset(3, size.height - 3 - k),
            Offset(3 + k, size.height - 3), p);
      }
    }
  }

  @override
  bool shouldRepaint(_TutamacRessami e) => e.renk != renk || e.ust != ust;
}

/// Balonun robota doğru uzanan kuyruğu (balon üstteyse altta, alttaysa üstte).
class _BalonKuyrugu extends CustomPainter {
  final Color zemin;
  final Color kenar;
  final double x;
  final bool altta;
  const _BalonKuyrugu(
      {required this.zemin, required this.kenar, required this.x, required this.altta});

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    if (!altta) {
      // Üstteki kuyruk: aynı şekil dikey çevrilir.
      canvas.translate(0, size.height);
      canvas.scale(1, -1);
    }
    final y = size.height - 11;
    final p = Path()
      ..moveTo(x - 12, y)
      ..quadraticBezierTo(x + 4, y + 4, x + 10, y + 11)
      ..quadraticBezierTo(x + 4, y + 2, x + 8, y)
      ..close();
    canvas.drawPath(p, Paint()..color = zemin);
    canvas.drawPath(
        Path()
          ..moveTo(x - 12, y + 0.7)
          ..quadraticBezierTo(x + 4, y + 4, x + 10, y + 11)
          ..quadraticBezierTo(x + 4, y + 2, x + 8, y + 0.7),
        Paint()
          ..color = kenar
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_BalonKuyrugu e) =>
      e.zemin != zemin || e.kenar != kenar || e.x != x || e.altta != altta;
}

class _KodiSozu extends StatelessWidget {
  final KodiMesaji mesaj;
  final String metin;
  final bool imlec;
  final bool kodSekmesiVar;
  final Future<void> Function(KodiEylemi e, {String? hedef}) onIzin;
  final void Function(KodiEylemi e) onRet;
  const _KodiSozu(
      {required this.mesaj,
      required this.metin,
      required this.imlec,
      required this.kodSekmesiVar,
      required this.onIzin,
      required this.onRet});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        MarkdownGorunum(
          imlec ? '$metin▍' : metin,
          yaziBoyutu: 13.5,
          baglanti: (url) => baglantiAc(context, url),
          // Kodi'nin kod bloklarının altında: yeni sekmede aç, imlece ekle.
          kodEylemleri: imlec
              ? null
              : (c, kod, dil) => Row(mainAxisSize: MainAxisSize.min, children: [
                    PanelDugmesi(
                      ikon: Icons.tab_rounded,
                      ipucu: 'Yeni sekmede aç',
                      onPressed: () => onIzin(
                          KodiEylemi('kod_yaz', {'kod': kod, 'hedef': 'yeni_sekme'}),
                          hedef: 'yeni_sekme'),
                    ),
                    PanelDugmesi(
                      ikon: Icons.input_rounded,
                      ipucu: 'İmlecin olduğu yere ekle',
                      onPressed: kodSekmesiVar
                          ? () => onIzin(
                              KodiEylemi('kod_yaz', {'kod': kod, 'hedef': 'imlec'}),
                              hedef: 'imlec')
                          : null,
                    ),
                  ]),
        ),
        if (mesaj.ayarDugmesi && !imlec)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Wrap(spacing: 6, runSpacing: 6, children: [
              FilledButton.icon(
                onPressed: () => context.read<KodiProvider>().rehberiAc(),
                style: FilledButton.styleFrom(backgroundColor: _kKodiMor),
                icon: const Icon(Icons.key_rounded, size: 16),
                label: const Text('Kurulum rehberi'),
              ),
              FilledButton.tonalIcon(
                onPressed: () => context.read<KodiProvider>().ayarlariAc(),
                icon: const Icon(Icons.settings_outlined, size: 16),
                label: const Text('Ayarları aç'),
              ),
            ]),
          ),
        if (!imlec)
          for (final e in mesaj.eylemler)
            _EylemKarti(
                eylem: e,
                kodSekmesiVar: kodSekmesiVar,
                onIzin: onIzin,
                onRet: onRet),
      ]),
    );
  }
}

/// Kodi'nin bir eylemi: yapıldıysa küçük bir not, izin gerekiyorsa sorusu ve
/// düğmeleriyle bir kart.
class _EylemKarti extends StatelessWidget {
  final KodiEylemi eylem;
  final bool kodSekmesiVar;
  final Future<void> Function(KodiEylemi e, {String? hedef}) onIzin;
  final void Function(KodiEylemi e) onRet;
  const _EylemKarti(
      {required this.eylem,
      required this.kodSekmesiVar,
      required this.onIzin,
      required this.onRet});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final e = eylem;
    if (e.durum == 'calisiyor') {
      // İş yapılıyor: düğmeler yok (ikinci tıklama işi yeniden yapıyordu).
      return Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(children: [
          const SizedBox(
              width: 13,
              height: 13,
              child: CircularProgressIndicator(strokeWidth: 2, color: _kKodiMor)),
          const SizedBox(width: 8),
          Flexible(
            child: Text('Yapıyorum…',
                style: TextStyle(
                    fontSize: 12, color: cs.onSurface.withValues(alpha: 0.75))),
          ),
        ]),
      );
    }
    if (e.durum != 'bekliyor') {
      final (ikon, renk) = switch (e.durum) {
        'yapildi' => (Icons.check_circle_rounded, const Color(0xFF22C55E)),
        'hata' => (Icons.error_outline_rounded, cs.error),
        _ => (Icons.do_not_disturb_on_outlined, cs.onSurface.withValues(alpha: 0.5)),
      };
      return Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(children: [
          Icon(ikon, size: 15, color: renk),
          const SizedBox(width: 6),
          Flexible(
            child: Text(e.sonuc ?? '',
                style: TextStyle(
                    fontSize: 12, color: cs.onSurface.withValues(alpha: 0.75))),
          ),
        ]),
      );
    }
    // Birazdan kendiliğinden yapılır.
    if (e.guvenliMi(context.read<KodiProvider>().hepSor)) return const SizedBox.shrink();

    final kod = e.tur == 'kod_yaz';
    final satir = kod ? '\n'.allMatches(e.kod.trimRight()).length + 1 : 0;
    final soru = kod
        ? (e.veri['yazan'] != null
            // Kodi kodu arka planda AI Asistan'a yazdırdı.
            ? '**${e.veri['yazan']}** kodu hazırladı ($satir satır). Senin için yazayım mı?'
            : 'Bu kodu ($satir satır) senin için yazayım mı?')
        : e.izinSorusu;
    final hedef = (e.veri['hedef'] ?? 'yeni_sekme').toString();
    Widget dugme(String yazi, IconData ikon, VoidCallback? f, {bool ana = false}) =>
        Padding(
          padding: const EdgeInsets.only(right: 6, top: 6),
          child: ana
              ? FilledButton.icon(
                  onPressed: f,
                  style: FilledButton.styleFrom(
                      backgroundColor: _kKodiMor,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6)),
                  icon: Icon(ikon, size: 15),
                  label: Text(yazi, style: const TextStyle(fontSize: 12)))
              : OutlinedButton.icon(
                  onPressed: f,
                  style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6)),
                  icon: Icon(ikon, size: 15),
                  label: Text(yazi, style: const TextStyle(fontSize: 12))),
        );
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.fromLTRB(10, 8, 6, 8),
      decoration: BoxDecoration(
        color: _kKodiMor.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _kKodiMor.withValues(alpha: 0.35)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.front_hand_rounded, size: 15, color: _kKodiPembe),
          const SizedBox(width: 6),
          Expanded(child: MarkdownGorunum(soru, yaziBoyutu: 12.5)),
        ]),
        Wrap(children: [
          if (kod) ...[
            dugme('Yeni sekmede aç', Icons.tab_rounded,
                () => onIzin(e, hedef: 'yeni_sekme'),
                ana: hedef == 'yeni_sekme'),
            dugme('İmlece ekle', Icons.input_rounded,
                kodSekmesiVar ? () => onIzin(e, hedef: 'imlec') : null,
                ana: hedef == 'imlec'),
            if (hedef == 'degistir')
              dugme('Dosyanın yerine yaz', Icons.find_replace_rounded,
                  kodSekmesiVar ? () => onIzin(e, hedef: 'degistir') : null,
                  ana: true),
          ] else
            dugme('İzin ver', Icons.check_rounded, () => onIzin(e), ana: true),
          dugme('Vazgeç', Icons.close_rounded, () => onRet(e)),
        ]),
      ]),
    );
  }
}

class _SeninSozun extends StatelessWidget {
  final String metin;
  final String? goruntu;
  final bool otomatik;
  const _SeninSozun({required this.metin, this.goruntu, this.otomatik = false});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final soluk = TextStyle(fontSize: 11, color: cs.onSurface.withValues(alpha: 0.6));
    if (otomatik) {
      // Kodi'nin kendi sürdürdüğü adım: kullanıcı yazmadı.
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Icon(Icons.subdirectory_arrow_right_rounded, size: 14, color: soluk.color),
          const SizedBox(width: 4),
          Text('Sayfa açıldı, Kodi devam ediyor', style: soluk),
        ]),
      );
    }
    final not = switch (goruntu) {
      'gitti' => (Icons.photo_camera_outlined, 'Görüntü de gönderildi'),
      'desteklenmiyor' => (Icons.no_photography_outlined,
          'Görüntü gönderilmedi: seçili model görüntü göremiyor'),
      'alinamadi' => (Icons.no_photography_outlined, 'Görüntü alınamadı'),
      _ => null,
    };
    if (not != null) {
      return Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        _SeninSozun(metin: metin),
        Padding(
          padding: const EdgeInsets.only(bottom: 2),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(not.$1, size: 12, color: soluk.color),
            const SizedBox(width: 3),
            Flexible(child: Text(not.$2, style: soluk)),
          ]),
        ),
      ]);
    }
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(left: 36, top: 4, bottom: 4),
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
        decoration: BoxDecoration(
          color: _kKodiMor.withValues(alpha: 0.16),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(14),
            topRight: Radius.circular(14),
            bottomLeft: Radius.circular(14),
            bottomRight: Radius.circular(4),
          ),
        ),
        child: Text(metin, style: TextStyle(fontSize: 13, color: cs.onSurface)),
      ),
    );
  }
}

/// Sohbetler paneli: yeni sohbet ve kayıtlı sohbetler (aç, sil).
class _SohbetlerPaneli extends StatelessWidget {
  final KodiProvider kodi;
  const _SohbetlerPaneli({required this.kodi});

  static String _tarih(String s) {
    // "2026-11-07 12:40" -> "7.11 12:40"
    final m = RegExp(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})').firstMatch(s);
    return m == null ? s : '${int.parse(m[3]!)}.${int.parse(m[2]!)} ${m[4]}';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final k = kodi;
    final kayitKapali =
        !context.select<SettingsProvider, bool>((s) => s.getBool(kKodiSohbetKaydet, fallback: true));
    return ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.fromLTRB(10, 4, 10, 8),
      children: [
        FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: _kKodiMor),
          icon: const Icon(Icons.add_comment_outlined, size: 16),
          label: const Text('Yeni sohbet'),
          onPressed: k.temizle,
        ),
        const SizedBox(height: 6),
        if (kayitKapali)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text('Sohbet kaydı kapalı (Ayarlar → Kodi): yeni sohbetler saklanmaz.',
                style: TextStyle(fontSize: 11.5, color: cs.onSurface.withValues(alpha: 0.65))),
          ),
        if (k.sohbetlerYukleniyor && k.sohbetListesi.isEmpty)
          const Padding(
            padding: EdgeInsets.all(12),
            child: Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))),
          )
        else if (k.sohbetListesi.isEmpty)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text('Henüz kayıtlı bir sohbet yok.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12.5, color: cs.onSurface.withValues(alpha: 0.65))),
          ),
        for (final s in k.sohbetListesi)
          Material(
            color: s['etkin'] == true ? _kKodiMor.withValues(alpha: 0.14) : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => k.sohbetAc('${s['no']}'),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(10, 6, 2, 6),
                child: Row(children: [
                  Icon(s['etkin'] == true ? Icons.chat_rounded : Icons.chat_bubble_outline_rounded,
                      size: 15, color: _kKodiMor),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${s['baslik']}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                      Text('${_tarih('${s['guncelleme']}')} · ${s['mesaj_sayisi']} mesaj',
                          style: TextStyle(
                              fontSize: 11, color: cs.onSurface.withValues(alpha: 0.6))),
                    ]),
                  ),
                  PanelDugmesi(
                    ikon: Icons.delete_outline_rounded,
                    ipucu: 'Bu sohbeti sil',
                    onPressed: () => k.sohbetSil('${s['no']}'),
                  ),
                ]),
              ),
            ),
          ),
      ],
    );
  }
}

/// Cevap beklenirken: "Düşünüyorum..." (noktalar sırayla belirir).
class _KodiDusunuyor extends StatefulWidget {
  final bool dusunme;
  const _KodiDusunuyor({required this.dusunme});
  @override
  State<_KodiDusunuyor> createState() => _KodiDusunuyorState();
}

class _KodiDusunuyorState extends State<_KodiDusunuyor> {
  int _nokta = 0;
  int _harf = 0;
  Timer? _zaman;

  String get _yazi => widget.dusunme ? 'Düşünüyorum' : 'Hemen bakıyorum';

  @override
  void initState() {
    super.initState();
    _zaman = Timer.periodic(const Duration(milliseconds: 70), (_) {
      if (!mounted) return;
      setState(() {
        if (_harf < _yazi.length) {
          _harf++;
        } else {
          _nokta = (_nokta + 1) % 24; // ~her 420 ms'de bir nokta
        }
      });
    });
  }

  @override
  void dispose() {
    _zaman?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final noktalar = _harf < _yazi.length ? '' : '.' * (1 + (_nokta ~/ 6) % 3);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Icon(widget.dusunme ? Icons.psychology_alt_outlined : Icons.bolt_rounded,
            size: 16, color: _kKodiCamgobegiKoyu),
        const SizedBox(width: 6),
        Text('${_yazi.substring(0, math.min(_harf, _yazi.length))}$noktalar',
            style: TextStyle(
                fontSize: 13.5,
                fontStyle: FontStyle.italic,
                color: cs.onSurface.withValues(alpha: 0.75))),
      ]),
    );
  }
}

// ============================================================================
// KODİ: EYLEMLER VE BAĞLAM
// ============================================================================

const _kKodiPanelAdlari = {
    'gezgin': 'Gezgin',
    'eklentiler': 'Eklenti Özellikleri',
    'ai': 'AI Asistan',
    'terminal': 'Terminal',
  };

/// Etkin sekme bir kod dosyası mı (PDF ya da Ayarlar değil)?
bool kodiKodSekmesiVar(BuildContext context) {
  final t = context.read<EditorProvider>().activeTab;
  return t != null && !ozelSekmeMi(t.path) && !t.isPdf;
}

/// Kodi'nin bir eylemini uygular (balondan da, masaüstü Kodi'den de).
Future<void> kodiEylemUygula(BuildContext context, KodiEylemi e, {String? hedef}) async {
    final ed = context.read<EditorProvider>();
    final ui = context.read<UiProvider>();
    try {
      final engel = kodiYetkiEngeli(context.read<SettingsProvider>(), e);
      if (engel != null) throw engel;
      final yonetim = !const {'ayar', 'ayarlar_ac', 'eklenti', 'model_ata', 'komut',
                'tarayici', 'rehber'}
              .contains(e.tur)
          ? false
          : await kodiYonetimEylemi(context, e);
      if (!yonetim) switch (e.tur) {
        case 'panel':
          final p = e.veri['panel'].toString();
          final ac = e.veri['durum'] != 'kapat';
          if (p == 'gezgin' || p == 'eklentiler') {
            final acikMi = ui.showExplorer && ui.solPanel == p;
            if (acikMi != ac) ui.solPanelSec(p);
          } else if (p == 'ai') {
            if (ui.showAi != ac) ui.toggleAi();
          } else if (p == 'terminal') {
            if (ac) {
              ui.revealTerminal();
            } else if (ui.showTerminal) {
              ui.toggleTerminal();
            }
          }
          e.sonuc = '${_kKodiPanelAdlari[p] ?? p} ${ac ? 'açıldı' : 'kapandı'}';
        case 'dosya_ac':
          var yol = e.veri['dosya'].toString();
          final kok = context.read<FileTreeProvider>().root?.path;
          if (kok == null) throw 'Açık bir proje klasörü yok';
          if (!p.isAbsolute(yol)) yol = p.join(kok, yol);
          yol = p.normalize(yol);
          // Yalnız proje klasöründeki dosyalar (yapay zekâ başka bir yeri
          // açmak istese bile).
          if (!p.isWithin(kok, yol)) {
            throw 'Yalnızca proje klasöründeki dosyaları açabilirim';
          }
          if (!File(yol).existsSync()) {
            throw '${p.basename(yol)} bulunamadı';
          }
          await ed.openFile(yol, context: context);
          e.sonuc = '${p.basename(yol)} açıldı';
        case 'sekme':
          final ad = e.veri['ad'].toString();
          final i = ed.tabs.indexWhere((t) => t.name == ad);
          if (i < 0) throw '"$ad" sekmesi açık değil';
          ed.setActive(i);
          e.sonuc = '$ad sekmesine geçildi';
        case 'satira_git':
        case 'ara':
          if (!kodiKodSekmesiVar(context)) throw 'Açık bir kod dosyası yok';
          final metin = ed.activeContent.value;
          final toplam = '\n'.allMatches(metin).length + 1;
          int satir;
          if (e.tur == 'satira_git') {
            satir = int.tryParse('${e.veri['satir']}') ?? 0;
            if (satir < 1 || satir > toplam) {
              throw 'Dosyada $toplam satır var; $satir. satır yok';
            }
            e.sonuc = '$satir. satıra gidildi';
          } else {
            final aranan = e.veri['metin'].toString();
            // Türkçe büyük/küçük harf duyarsız; harf sayısı değişmez (İ→i, I→ı),
            // bulunan konumlar asıl metindekiyle aynı kalır.
            String kucuk(String s) =>
                s.replaceAll('İ', 'i').replaceAll('I', 'ı').toLowerCase();
            final govde = kucuk(metin);
            final hedef = kucuk(aranan);
            final yerler = <int>[];
            for (var i = govde.indexOf(hedef); i >= 0; i = govde.indexOf(hedef, i + 1)) {
              yerler.add(i);
            }
            if (yerler.isEmpty) throw '"$aranan" bu dosyada bulunamadı';
            final sira = (int.tryParse('${e.veri['sira']}') ?? 1).clamp(1, yerler.length);
            satir = '\n'.allMatches(metin.substring(0, yerler[sira - 1])).length + 1;
            e.sonuc = '"$aranan" $satir. satırda bulundu'
                '${yerler.length > 1 ? ' (${yerler.length} eşleşmenin $sira.)' : ''}';
          }
          final goster = ed.revealModelLine;
          if (goster != null) {
            goster(satir);
          } else if (ed.uiController case final c?) {
            jumpToLineIn(c, satir);
          }
          ed.editorFocusNode?.requestFocus();
        case 'kitap':
          final yol = belgeYolu(kKitapDosyasi);
          if (yol == null) throw 'Kitabı bulamadım';
          final sayfa = int.tryParse('${e.veri['sayfa']}') ?? 1;
          PdfSekmesi.sayfaIstegi.value = (yol: yol, sayfa: sayfa);
          await ed.openFile(yol);
          e.sonuc = 'Kitap $sayfa. sayfada açıldı';
        case 'kod_yaz':
          // Kod, izin verilince editöre canlı (harf harf akarak) yazılır.
          final kod = e.kod;
          switch (hedef ?? e.veri['hedef'] ?? 'yeni_sekme') {
            case 'imlec':
              final c = ed.uiController;
              if (!kodiKodSekmesiVar(context) || c == null) throw 'Açık bir kod dosyası yok';
              final yer = _kodYeri(ed, c);
              if (yer.gorunumTam) {
                await _koduCanliYaz(ed, c, yer.once, yer.sonra, kod);
              } else {
                // Görünüm dosyayla eşleşmedi: kod doğrudan dosya metnine
                // (katlı kod korunarak) bir kerede yazılır.
                ed.replaceActiveContent(yer.once + kod + yer.sonra);
              }
              e.sonuc = 'Kod imlecin olduğu yere eklendi';
            case 'degistir':
              final c = ed.uiController;
              if (!kodiKodSekmesiVar(context)) throw 'Açık bir kod dosyası yok';
              // Katlamalar açılmadan bütün metin değiştirilirse katlama
              // haritası bozulur, sekme güncellenmezdi.
              if (c == null || !_kodYeri(ed, c).gorunumTam) {
                ed.replaceActiveContent(kod);
              } else {
                await _koduCanliYaz(ed, c, '', '', kod);
              }
              e.sonuc = 'Dosyadaki kod yenisiyle değiştirildi';
            default:
              await ed.createUntitled(
                name: (e.veri['ad'] ?? 'kodi_kodu.trpy').toString(),
                context: context,
              );
              // Editör yeni sekmeye geçsin, sonra kod yazılmaya başlansın.
              await WidgetsBinding.instance.endOfFrame;
              final c = ed.uiController;
              if (c == null || !context.mounted || !kodiKodSekmesiVar(context)) {
                ed.replaceActiveContent(kod);
              } else {
                await _koduCanliYaz(ed, c, '', '', kod);
              }
              e.sonuc = 'Kod yeni bir sekmeye yazıldı';
          }
      }
      e.durum = 'yapildi';
    } catch (hata) {
      e.durum = 'hata';
      e.sonuc = hata.toString();
    }
    if (context.mounted) context.read<KodiProvider>().yenile();
}

/// Model (dosyadaki gerçek) metinde [satir]. satırın (1'den başlar)
/// [sutun]. harfinin ofseti; satır kısaysa satırın sonu, satır yoksa metnin
/// sonu.
int kodiModelOfseti(String metin, int satir, int sutun) {
  var bas = 0;
  for (var i = 1; i < satir; i++) {
    final nl = metin.indexOf('\n', bas);
    if (nl < 0) return metin.length;
    bas = nl + 1;
  }
  var son = metin.indexOf('\n', bas);
  if (son < 0) son = metin.length;
  return (bas + math.max(0, sutun)).clamp(bas, son).toInt();
}

/// Kodi'nin kodu yazacağı yer: imlecin önü ve arkası, DOSYADAKİ GERÇEK
/// metne göre. Editörün görünüm metninde katlı bölgeler tek bir yer tutucu
/// satırdır, gizli kod yoktur: eskiden kod bu metne göre yazılıyor, yazarken
/// sekme değiştirilince görünüm metni dosyaya konuyor ve katlı kod
/// siliniyordu (kaydedince dosyadan da). Artık önce katlamalar açılır.
/// gorunumTam: katlamalar açıldıktan sonra görünüm dosya metniyle aynı
/// (kod canlı yazılabilir); değilse kod dosya metnine bir kerede konur.
({String once, String sonra, bool gorunumTam}) _kodYeri(
    EditorProvider ed, TextEditingController c) {
  final t = c.text;
  final pos = (c.selection.isValid ? c.selection.baseOffset : t.length)
      .clamp(0, t.length)
      .toInt();
  // İmlecin dosyadaki satırı ve sütunu (katlamalar açılınca imleç kayar).
  final sutun = pos - (pos == 0 ? 0 : t.lastIndexOf('\n', pos - 1) + 1);
  int? modelSatir;
  try {
    modelSatir = ed.caretModelLine?.call();
  } catch (_) {}
  // Görünümdeki son değişiklikler sekmeye geçsin (katlı kod dahil tam metin).
  ed.syncFromView();
  final katli = t != ed.activeTab?.content;
  if (katli) ed.unfoldAll?.call();
  final model = ed.activeTab?.content ?? c.text;
  final i = !katli
      ? pos.clamp(0, model.length).toInt()
      : modelSatir != null && modelSatir > 0
          ? kodiModelOfseti(model, modelSatir, sutun)
          : model.length;
  return (
    once: model.substring(0, i),
    sonra: model.substring(i),
    gorunumTam: c.text == model,
  );
}

/// Kodi'nin yazdığı kodu editöre canlı yazar: [once] ile [sonra] arasına,
/// parça parça (en çok ~2,5 sn; uzun kodda bir karede daha çok harf), imleç
/// ve görünüm yazılan yeri izler. Ardışık değişiklikler editörün geri alma
/// geçmişinde tek kayıt olur (Ctrl+Z bir kerede geri alır). Yazarken başka
/// sekmeye geçilirse kodun tamamı yine başladığı sekmeye konur. [once] ve
/// [sonra] dosyanın GERÇEK metninden gelmelidir (bkz. [_kodYeri]); görünüm
/// metni sekmeye yazılırsa katlı kod silinir.
Future<void> _koduCanliYaz(EditorProvider ed, TextEditingController c, String once,
    String sonra, String kod) async {
  final sekme = ed.activeTab?.id;
  final adim = math.max(3, (kod.length / 150).ceil());
  var n = 0;
  var kare = 0;
  while (n < kod.length) {
    n = math.min(kod.length, n + adim);
    // Emoji gibi iki parçalı harfler bölünmesin.
    if (n < kod.length && (kod.codeUnitAt(n - 1) & 0xFC00) == 0xD800) n++;
    final yazilan = once + kod.substring(0, n);
    _setControllerValueProgrammatic(
        c,
        TextEditingValue(
            text: yazilan + sonra, selection: TextSelection.collapsed(offset: yazilan.length)));
    if (++kare % 6 == 0 || n == kod.length) {
      ed.revealModelLine?.call('\n'.allMatches(yazilan).length + 1);
    }
    await Future<void>.delayed(const Duration(milliseconds: 16));
    if (c.text != yazilan + sonra) {
      // Yazarken sekme değişti (ya da sekme kapandı): kod başladığı sekmeye
      // eksiksiz konur. Kullanıcı aynı sekmeye yazdıysa ona dokunulmaz.
      if (sekme != null && ed.activeTab?.id != sekme) {
        ed.replaceContentOf(sekme, once + kod + sonra);
      }
      return;
    }
  }
  ed.syncFromView();
}

/// Kodi'ye her soruda gönderilen arayüz durumu.
Map<String, dynamic> kodiBaglami(BuildContext context) {
    final ed = context.read<EditorProvider>();
    final ui = context.read<UiProvider>();
    final kok = context.read<FileTreeProvider>().root;
    final aktif = ed.activeTab;
    final dosyalar = <String>[];
    void gez(FileNode n, String onek, int derinlik) {
      for (final c in n.children) {
        if (dosyalar.length >= 60) return;
        dosyalar.add('$onek${c.name}${c.isDir ? '/' : ''}');
        if (c.isDir && c.loaded && derinlik < 2) {
          gez(c, '$onek${c.name}/', derinlik + 1);
        }
      }
    }

    if (kok != null) gez(kok, '', 0);
    var kod = '';
    var secim = '';
    int? imlecSatir;
    if (aktif != null && !ozelSekmeMi(aktif.path) && !aktif.isPdf) {
      kod = ed.activeContent.value;
      if (kod.length > 2400) kod = kod.substring(0, 2400);
      final c = ed.uiController;
      if (c != null && c.selection.isValid && !c.selection.isCollapsed) {
        secim = c.selection.textInside(c.text);
      }
      try {
        imlecSatir = ed.caretModelLine?.call();
      } catch (_) {}
    }
    final term = context.read<TerminalProvider>();
    var terminal = term.output;
    if (terminal.length > 1500) terminal = terminal.substring(terminal.length - 1500);
    return {
      'sekmeler': [
        for (final t in ed.tabs)
          if (!ozelSekmeMi(t.path)) t.name
      ],
      'aktif_sekme': aktif?.path == kSettingsPath ? 'Ayarlar' : aktif?.name,
      'aktif_kod': kod,
      'kod_sekmesi': kodiKodSekmesiVar(context),
      if (secim.trim().isNotEmpty) 'secili_kod': secim,
      if (imlecSatir != null) 'imlec_satir': imlecSatir,
      if (terminal.trim().isNotEmpty) 'terminal': terminal,
      if (term.sonHata != null) 'son_hata': term.sonHata,
      'sorunlar': [
        for (final s in ui.sorunlar.take(10))
          'Satır ${s.satir}: ${s.mesaj}${s.hata ? '' : ' (uyarı)'}'
      ],
      'proje': kok?.path,
      'dosyalar': dosyalar,
      'paneller': {
        'gezgin': ui.showExplorer && ui.solPanel == 'gezgin',
        'eklentiler': ui.showExplorer && ui.solPanel == 'eklentiler',
        'ai': ui.showAi,
        'terminal': ui.showTerminal,
      },
      ...kodiYonetimBaglami(context),
      // Tarayıcı sekmesi açıksa: sayfa ve numaralı öğeler.
      if (kTarayici.hazir && ed.tabs.any((t) => t.path == kTarayiciPath))
        'tarayici': {
          ...kTarayici.sonBilgi,
          'acik': aktif?.path == kTarayiciPath,
        },
      // Kodi'nin son yaptığı işler ve sonuçları: bir önceki adımda ne olduğunu
      // bilsin (sohbet geçmişinde yalnızca konuşma var).
      'son_islemler': kodiSonIslemler(context.read<KodiProvider>().mesajlar),
    };
  }

/// Son 6 işin kısa özeti ("tarayici tikla: "Releases" tıklandı", "panel: HATA: ...").
List<String> kodiSonIslemler(List<KodiMesaji> mesajlar) {
  final liste = <String>[];
  for (final m in mesajlar) {
    for (final e in m.eylemler) {
      final ad = e.tur == 'tarayici' ? 'tarayici ${e.veri['islem'] ?? ''}' : e.tur;
      final durum = switch (e.durum) {
        'yapildi' => e.sonuc ?? 'yapıldı',
        'hata' => 'HATA: ${e.sonuc ?? 'olmadı'}',
        'reddedildi' => 'kullanıcı istemedi',
        'calisiyor' => 'yapılıyor',
        _ => 'onay bekliyor',
      };
      liste.add('$ad: $durum');
    }
  }
  return liste.length > 6 ? liste.sublist(liste.length - 6) : liste;
}

/// Dinlerken ya da konuşurken balonun altında beliren şerit.
class _SesSeridi extends StatefulWidget {
  final bool dinliyor;
  final VoidCallback onDur;
  const _SesSeridi({required this.dinliyor, required this.onDur});
  @override
  State<_SesSeridi> createState() => _SesSeridiState();
}

class _SesSeridiState extends State<_SesSeridi> with SingleTickerProviderStateMixin {
  late final AnimationController _a =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat();

  @override
  void dispose() {
    _a.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final renk = widget.dinliyor ? const Color(0xFFEF4444) : _kKodiCamgobegiKoyu;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 6),
      padding: const EdgeInsets.fromLTRB(10, 4, 4, 4),
      decoration: BoxDecoration(
        color: renk.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(children: [
        AnimatedBuilder(
          animation: _a,
          builder: (_, __) => Row(children: [
            for (var i = 0; i < 4; i++)
              Container(
                width: 3,
                height: 6 + 10 * (0.5 + 0.5 * math.sin((_a.value + i * 0.2) * 2 * math.pi)),
                margin: const EdgeInsets.only(right: 3),
                decoration: BoxDecoration(
                    color: renk, borderRadius: BorderRadius.circular(2)),
              ),
          ]),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
              widget.dinliyor
                  ? 'Dinliyorum… Konuşmayı bitirince kendim anlarım.'
                  : 'Konuşuyorum…',
              style: TextStyle(fontSize: 12, color: cs.onSurface.withValues(alpha: 0.8))),
        ),
        PanelDugmesi(
          ikon: Icons.stop_rounded,
          ipucu: widget.dinliyor ? 'Dinlemeyi bırak' : 'Sus',
          onPressed: widget.onDur,
        ),
      ]),
    );
  }
}

// ============================================================================
// MASAÜSTÜ KODİ PENCERESİ (TürKod'un ikinci penceresi)
// ============================================================================

/// `turkod_flutter.exe --kodi-penceresi --kodi-url ws://...` ile açılır.
/// Pencere saydamdır; içinde uygulamadakiyle aynı Kodi ve balon vardır.
Future<void> kodiPenceresiniCalistir(List<String> args) async {
  String? deger(String ad) {
    final i = args.indexOf(ad);
    return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
  }

  final url = deger('--kodi-url');
  if (url != null) {
    final u = Uri.parse(url);
    AppConfig._portOverride = u.port;
    AppConfig._token = u.queryParameters['token'] ?? '';
  }
  final backend = BackendService();
  unawaited(backend.connect());
  try {
    await backend.waitUntilConnected().timeout(const Duration(seconds: 15));
  } catch (_) {
    exit(0);
  }
  // TürKod kapanınca motor da kapanır: pencere de kapanır.
  backend.connectionStream.listen((bagli) {
    if (!bagli) exit(0);
  });
  final ayarlar = SettingsProvider(backend);
  await ayarlar.load();
  final kodi = KodiProvider(backend, pencereKipi: true);
  runApp(MultiProvider(
    providers: [
      Provider<BackendService>.value(value: backend),
      ChangeNotifierProvider<SettingsProvider>.value(value: ayarlar),
      ChangeNotifierProvider<KodiProvider>.value(value: kodi),
    ],
    child: const _KodiPenceresiUygulamasi(),
  ));
  await kodi.pencereyiBaslat(gizli: args.contains('--kodi-gizli'));
}

class _KodiPenceresiUygulamasi extends StatelessWidget {
  const _KodiPenceresiUygulamasi();

  @override
  Widget build(BuildContext context) {
    final tema = context.select<SettingsProvider, String>(
        (s) => s.getString('tema', fallback: 'Modern Koyu'));
    final temel = AppThemeRegistry.build(tema);
    return MaterialApp(
      title: 'Kodi',
      debugShowCheckedModeBanner: false,
      color: Colors.transparent,
      theme: temel.copyWith(scaffoldBackgroundColor: Colors.transparent),
      locale: kTurkce,
      supportedLocales: const [kTurkce],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const Scaffold(
        backgroundColor: Colors.transparent,
        body: SizedBox.expand(
          child: KodiKatmani(pencereKipi: true, varsayilanSag: 10, varsayilanAlt: 6),
        ),
      ),
    );
  }
}
