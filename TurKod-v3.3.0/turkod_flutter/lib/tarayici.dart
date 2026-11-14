// IDE içindeki tarayıcı (Görünüm → Tarayıcı): Microsoft Edge WebView2 ile
// sayfalar TürKod'un içinde, bir sekmede açılır. Kodi tarayıcıyı yönetebilir:
// site açar, Google'da arar, sayfayı okur, bir öğeye ekrandaki "Kodi imleci"
// ile gidip tıklar, kutulara yazar, kaydırır. Şifre alanlarına hiç yazmaz;
// satın alma, ödeme, silme gibi düğmelerde önce izin ister.
//
// API kurulum rehberi de burada: tarayıcıda sağlayıcının anahtar sayfası açılır,
// yanda adım adım rehber durur; kullanıcı anahtarı kendisi oluşturup
// yapıştırır, TürKod bağlar ve modeli seçer.
part of 'main.dart';

const String kTarayiciAnaSayfa = 'https://www.google.com';
const String kGroqAnahtarSayfasi = 'https://console.groq.com/keys';

/// Adres çubuğuna ya da Kodi'den gelen yazıyı adrese çevirir: adres gibi
/// değilse Google'da aranır.
String tarayiciAdresi(String yazi) {
  final s = yazi.trim();
  if (s.isEmpty) return kTarayiciAnaSayfa;
  if (RegExp(r'^[a-zA-Z][a-zA-Z0-9+.-]*://').hasMatch(s)) return s;
  if (!s.contains(' ') && RegExp(r'^[^\s/]+\.[a-zA-Z]{2,}(?:[/:?#].*)?$').hasMatch(s)) {
    return 'https://$s';
  }
  if (s.toLowerCase() == 'google') return kTarayiciAnaSayfa;
  return 'https://www.google.com/search?q=${Uri.encodeQueryComponent(s)}';
}

// Sayfanın görünen, tıklanabilir öğelerine numara verir; Kodi bunları görür.
const String _kOgeBetigi = r'''
(() => {
  const gorunur = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
  // Numaralar sayfa boyunca sabittir: Kodi'nin gördüğü numara, tıklandığında
  // da aynı öğedir (sayfa yeniden okununca numara kaymaz).
  let enBuyuk = 0;
  document.querySelectorAll('[data-kodi-no]').forEach(e => {
    enBuyuk = Math.max(enBuyuk, +e.getAttribute('data-kodi-no') || 0); });
  const secici = 'a[href],button,input:not([type=hidden]),textarea,select,[role=button],[role=link],[role=tab],[role=menuitem],[contenteditable=true],summary';
  const liste = []; let sayi = 0;
  // Önce sayfanın asıl içeriği (arama sonuçları, makale ...), sonra geri kalanı:
  // üst menüdeki bağlantılar listeyi doldurup sonuçları dışarıda bırakıyordu.
  const ana = document.querySelector('main,[role=main],#search,#main,#content,article');
  const sirali = [...(ana ? ana.querySelectorAll(secici) : []), ...document.querySelectorAll(secici)];
  const gorulen = new Set();
  for (const e of sirali) {
    if (gorulen.has(e)) continue;
    gorulen.add(e);
    if (sayi >= 80) break;
    if (!gorunur(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.bottom < -innerHeight || r.top > innerHeight * 3) continue;
    let m = (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') ||
             e.title || e.alt || '').trim().replace(/\s+/g, ' ').slice(0, 70);
    if (!m && e.tagName === 'INPUT') m = e.name || e.type || 'kutu';
    if (!m) continue;
    // Bağlantının gittiği site (Kodi doğru sonucu seçebilsin).
    if (e.tagName === 'A' && e.href) {
      try { const h = new URL(e.href).hostname.replace(/^www\./, '');
            if (h && h !== location.hostname.replace(/^www\./, '')) m += ' (' + h + ')'; } catch (_) {}
    }
    let no = +e.getAttribute('data-kodi-no') || 0;
    if (!no) { no = ++enBuyuk; e.setAttribute('data-kodi-no', String(no)); }
    liste.push({no: no, tur: e.tagName.toLowerCase() + (e.type ? ':' + e.type : ''), metin: m,
                sifre: e.type === 'password'});
    sayi++;
  }
  const ozet = (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').slice(0, 1200);
  return {url: location.href, baslik: document.title, ozet: ozet, ogeler: liste};
})()
''';

/// Kodi'nin tarayıcıda gördüğü bir öğe.
class TarayiciOgesi {
  final int no;
  final String tur;
  final String metin;
  final bool sifre;
  const TarayiciOgesi(this.no, this.tur, this.metin, this.sifre);
  Map<String, dynamic> json() => {'no': no, 'tur': tur, 'metin': metin, if (sifre) 'sifre': true};
}

/// Tarayıcının tek örneği: sekme kapanıp açılınca sayfa kaybolmaz; Kodi
/// sekme görünmezken de ona erişir.
class TarayiciDurumu extends ChangeNotifier {
  TarayiciDurumu._();
  static final TarayiciDurumu ornek = TarayiciDurumu._();

  WebviewController? _c;
  Future<void>? _baslatma;
  bool hazir = false;
  String? hata;
  String adres = '';
  String baslik = '';
  bool yukleniyor = false;
  bool geriVar = false;
  bool ileriVar = false;

  /// Kodi'nin sayfa üstündeki imleci (sekmeye göre konum) ve notu.
  Offset? imlec;
  String? imlecNotu;
  bool tiklama = false;

  /// Son okunan sayfa: adres, başlık, kısa metin, numaralı öğeler.
  Map<String, dynamic> sonBilgi = const {};

  /// API kurulum rehberi açık mı (tarayıcı sekmesinin yanında)?
  bool rehberAcik = false;

  WebviewController? get denetci => hazir ? _c : null;

  // --------------------------------------------------------------------------
  // Pencereli sayfa (VS Code'un tümleşik tarayıcısı gibi): WebView2 TürKod
  // penceresinin içinde kendi penceresiyle çizilir; fare, tekerlek, kaydırma
  // çubuğu ve klavye doğrudan sayfaya gider. Flutter öğeleri bu pencerenin
  // üstüne çizilemediği için:
  //  - Kodi ve balonu sayfanın üstündeyken oralar pencereden kesilir;
  //  - menü ya da iletişim kutusu açılınca sayfanın anlık görüntüsü konur,
  //    gerçek sayfa gizlenir (kapanınca geri gelir).
  // --------------------------------------------------------------------------

  /// Sayfa alanı (Flutter görünümüne göre, mantıksal piksel) ve ölçek.
  Rect? _alan;
  double _dpr = 1;

  /// Tarayıcı sekmesi ekranda mı?
  bool _sekmede = false;

  /// Açık menü / iletişim kutusu sayısı (bkz. TarayiciOrtuGozlemcisi).
  int _ortu = 0;

  /// Kodi gibi sayfanın üstündeki Flutter öğeleri (mantıksal, genel).
  List<Rect> _ustOgeler = const [];

  /// Gizliyken yerine gösterilen anlık görüntü (PNG).
  Uint8List? onizleme;

  bool _gorunurNative = false;
  Rect? _sonBildirilen;
  String _sonKesik = '';

  bool get _gorunmeli => hazir && _sekmede && _ortu == 0 && !_askida && _alan != null;

  /// Sayfa alanının yeri değişti (TarayiciSekmesi her çizimde bildirir).
  void alaniBildir(Rect alan, double dpr) {
    if (_alan == alan && _dpr == dpr) return;
    _alan = alan;
    _dpr = dpr;
    _yerlestir();
  }

  void _yerlestir() {
    final c = _c;
    final a = _alan;
    if (c == null || !hazir || a == null) return;
    final f = Rect.fromLTRB(
        (a.left * _dpr).roundToDouble(),
        (a.top * _dpr).roundToDouble(),
        (a.right * _dpr).roundToDouble(),
        (a.bottom * _dpr).roundToDouble());
    if (f != _sonBildirilen) {
      _sonBildirilen = f;
      c.setWindowBounds(f).catchError((_) {});
    }
    _kesikleriUygula();
    _gorunurlukUygula();
  }

  /// Kodi (robot ve balon) gibi sayfanın üstünde durması gereken öğeler.
  void ustOgeleriBildir(List<Rect> ogeler) {
    _ustOgeler = ogeler;
    _kesikleriUygula();
  }

  void _kesikleriUygula() {
    final c = _c;
    final a = _alan;
    if (c == null || !hazir || a == null) return;
    final kesikler = <Rect>[
      for (final o in _ustOgeler)
        if (o.overlaps(a))
          Rect.fromLTRB(
              (o.left - a.left) * _dpr,
              (o.top - a.top) * _dpr,
              (o.right - a.left) * _dpr,
              (o.bottom - a.top) * _dpr),
    ];
    final imza = kesikler.map((r) => '${r.left.round()},${r.top.round()},${r.right.round()},${r.bottom.round()}').join(';');
    if (imza == _sonKesik) return;
    final ilkKesik =
        (_sonKesik.isEmpty || _sonKesik == _kGizliKesik) && kesikler.isNotEmpty;
    _sonKesik = imza;
    c.setClipRects(kesikler).catchError((_) {});
    // Kesik yerlerde (Kodi'nin çevresinde) sayfanın görüntüsü görünsün diye
    // anlık görüntü arada bir tazelenir; kesik yoksa gerek kalmaz.
    if (kesikler.isEmpty) {
      _altZamanlayici?.cancel();
      _altZamanlayici = null;
    } else if (_altZamanlayici == null) {
      _altZamanlayici =
          Timer.periodic(const Duration(milliseconds: 1500), (_) => _altGoruntuAl());
    }
    if (ilkKesik) _altGoruntuAl();
  }

  /// Sekme gizlenince: bir sonraki kesik (boş bile olsa) yeniden uygulanır.
  static const String _kGizliKesik = '#gizli';

  /// Kodi'nin altında kalan yerlerde gösterilen sayfa görüntüsü.
  Uint8List? altGoruntu;
  Timer? _altZamanlayici;
  bool _altAliniyor = false;

  Future<void> _altGoruntuAl() async {
    final c = _c;
    if (c == null || !hazir || !_gorunurNative || _altAliniyor) return;
    _altAliniyor = true;
    try {
      final r = await c.capturePreview().timeout(const Duration(seconds: 1));
      if (r != null && _gorunurNative) {
        altGoruntu = r;
        super.notifyListeners();
      }
    } catch (_) {
    } finally {
      _altAliniyor = false;
    }
  }

  void _gorunurlukUygula() {
    final c = _c;
    if (c == null || !hazir) return;
    final g = _gorunmeli;
    if (g == _gorunurNative) return;
    _gorunurNative = g;
    c.setWindowVisible(g).catchError((_) {});
    if (g && onizleme != null) {
      // Gerçek sayfa geri geldi: görüntü bir kare sonra kaldırılır.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_gorunurNative) {
          onizleme = null;
          super.notifyListeners();
        }
      });
    }
  }

  /// Sayfanın üstüne bir menü / iletişim kutusu açıldı ya da kapandı.
  Future<void> ortuDegisti(int fark) async {
    final once = _ortu;
    _ortu = math.max(0, _ortu + fark);
    if (once == 0 && _ortu > 0 && _gorunurNative) {
      // Önce sayfanın görüntüsü alınır (gizlenince alınamaz), sonra gizlenir.
      final c = _c;
      Uint8List? resim;
      try {
        resim = await c?.capturePreview().timeout(const Duration(milliseconds: 250));
      } catch (_) {}
      if (resim != null && _ortu > 0) {
        onizleme = resim;
        super.notifyListeners();
      }
    }
    _gorunurlukUygula();
  }

  /// Tarayıcı sekmesi ekrana geldi ya da gitti.
  void sekmedeMi(bool sekmede) {
    if (_sekmede == sekmede) return;
    _sekmede = sekmede;
    if (!sekmede) {
      _alan = null;
      _sonBildirilen = null;
      // Eskiden sekme gizlenince görüntü zamanlayıcısı durmuyor, büyük sayfa
      // görüntüsü bellekte kalıyordu. Sekme yeniden görününce kesikler
      // baştan uygulanır ve zamanlayıcı yeniden kurulur.
      _altZamanlayici?.cancel();
      _altZamanlayici = null;
      _sonKesik = _kGizliKesik;
      if (altGoruntu != null) {
        altGoruntu = null;
        super.notifyListeners();
      }
    }
    _gorunurlukUygula();
  }

  /// Kodi'nin imleci sayfanın içinde çizilir (pencerenin üstüne Flutter
  /// çizemez); imleç ya da notu değişince sayfaya yazılır.
  String _sonImlec = '';

  @override
  void notifyListeners() {
    super.notifyListeners();
    _imleciSayfayaYaz();
  }

  void _imleciSayfayaYaz() {
    final c = _c;
    if (c == null || !hazir) return;
    final i = imlec;
    final imza = i == null ? '' : '${i.dx.round()},${i.dy.round()},$imlecNotu,$tiklama';
    if (imza == _sonImlec) return;
    _sonImlec = imza;
    final betik = i == null
        ? "(() => { const k = document.getElementById('__kodi_imlec'); if (k) k.remove(); })()"
        : _kImlecBetigi
            .replaceAll('__X__', i.dx.toStringAsFixed(1))
            .replaceAll('__Y__', i.dy.toStringAsFixed(1))
            .replaceAll('__NOT__', jsonEncode(imlecNotu ?? ''))
            .replaceAll('__TIK__', tiklama ? 'true' : 'false');
    c.executeScript(betik).catchError((_) => null);
  }

  /// Tarayıcı sekmesi görünmüyorken WebView askıya alınır (sayfa betikleri
  /// durur); sekme kapatılınca tamamen kapatılır.
  bool _askida = false;
  int _kusak = 0;
  final List<StreamSubscription<dynamic>> _abonelikler = [];

  Future<void> baslat() => _baslatma ??= _baslat();

  Future<void> _baslat() async {
    final kusak = _kusak;
    WebviewController? yeni;
    try {
      final c = WebviewController();
      yeni = c;
      await c.initialize(windowed: true);
      if (kusak != _kusak) {
        // Hazırlanırken sekme kapatıldı.
        await c.dispose();
        return;
      }
      await c.setPopupWindowPolicy(WebviewPopupWindowPolicy.sameWindow);
      if (kusak != _kusak) {
        // Eskiden yalnızca initialize'dan sonra bakılıyordu: sekme bu arada
        // kapatılırsa eski denetçi yine kuruluyor, Edge süreçleri açık
        // kalıyordu.
        await c.dispose();
        return;
      }
      _gorunurNative = false;
      _sonBildirilen = null;
      _sonKesik = '';
      _sonImlec = '';
      _abonelikler.addAll([
        c.url.listen((u) {
          adres = u;
          notifyListeners();
        }),
        c.title.listen((t) {
          baslik = t;
          notifyListeners();
        }),
        c.historyChanged.listen((h) {
          geriVar = h.canGoBack;
          ileriVar = h.canGoForward;
          notifyListeners();
        }),
        c.loadingState.listen((s) {
          yukleniyor = s == LoadingState.loading;
          notifyListeners();
          if (s == LoadingState.navigationCompleted) _sayfaYuklendi();
        }),
      ]);
      _c = c;
      _askida = false;
      hazir = true;
      hata = null;
      notifyListeners();
      _yerlestir();
      await c.loadUrl(rehberAcik ? kGroqAnahtarSayfasi : kTarayiciAnaSayfa);
    } catch (e) {
      if (kusak != _kusak) {
        // Sekme kapatılmışken gelen hata: yarım kalan denetçi kapatılır, hata
        // gösterilmez (yeni açılış kendi denetçisini kurar).
        if (!identical(_c, yeni)) {
          try {
            await yeni?.dispose();
          } catch (_) {}
        }
        return;
      }
      _baslatma = null;
      hata = 'Tarayıcı açılamadı. Bilgisayarda Microsoft Edge WebView2 kurulu olmalı '
          '(Windows 10/11\'de genellikle vardır). Ayrıntı: $e';
      notifyListeners();
    }
  }

  Future<void> _sayfaYuklendi() async {
    imlec = null;
    imlecNotu = null;
    notifyListeners();
    await sayfayiOku();
    if (rehberAcik) await rehberIpucu();
  }

  /// Sayfanın öğelerini numaralar ve Kodi için özetler.
  Future<Map<String, dynamic>> sayfayiOku() async {
    final c = denetci;
    if (c == null) return const {};
    // "Yüklendi" denince belge bazen henüz boştur (başlık ve metin yok):
    // sayfa dolana kadar kısa aralıklarla yeniden okunur (en çok ~4 sn).
    for (var deneme = 0; deneme < 8; deneme++) {
      try {
        final r = await c.executeScript(_kOgeBetigi);
        if (r is Map) {
          sonBilgi = Map<String, dynamic>.from(r);
          final dolu = '${sonBilgi['ozet'] ?? ''}'.trim().isNotEmpty ||
              (sonBilgi['ogeler'] is List && (sonBilgi['ogeler'] as List).isNotEmpty);
          if (dolu) break;
        }
      } catch (_) {}
      await Future<void>.delayed(const Duration(milliseconds: 500));
    }
    return sonBilgi;
  }

  /// Sayfa yüklenmesi bitene kadar bekler (en çok [sure]).
  Future<void> yuklenmeyiBekle([Duration sure = const Duration(seconds: 8)]) async {
    final bitis = DateTime.now().add(sure);
    await Future<void>.delayed(const Duration(milliseconds: 300));
    while (yukleniyor && DateTime.now().isBefore(bitis)) {
      await Future<void>.delayed(const Duration(milliseconds: 150));
    }
  }

  Future<void> git(String yazi) async {
    await baslat();
    await denetci?.loadUrl(tarayiciAdresi(yazi));
  }

  Future<void> geri() async => denetci?.goBack();
  Future<void> ileri() async => denetci?.goForward();
  Future<void> yenile() async => denetci?.reload();

  Future<void> kaydir(bool asagi) async {
    await denetci?.executeScript(
        'window.scrollBy({top: ${asagi ? '' : '-'}innerHeight * 0.8, behavior: "smooth"})');
    await Future<void>.delayed(const Duration(milliseconds: 400));
    await sayfayiOku();
  }

  /// Öğenin ortası (sayfa koordinatı) ve özellikleri; öğe görünür yere kaydırılır.
  Future<Map<String, dynamic>?> _oge(int no) async {
    final c = denetci;
    if (c == null) return null;
    final r = await c.executeScript('''
(() => { const e = document.querySelector('[data-kodi-no="$no"]'); if (!e) return null;
  e.scrollIntoView({block: 'center', inline: 'center'});
  const r = e.getBoundingClientRect();
  return {x: r.left + r.width / 2, y: r.top + r.height / 2, sifre: e.type === 'password',
          metin: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim()
                   .replace(/\\s+/g, ' ').slice(0, 60)}; })()''');
    return r is Map ? Map<String, dynamic>.from(r) : null;
  }

  /// Kodi imleci öğeye gider (görünsün diye yavaşça), sonra iş yapılır.
  Future<Map<String, dynamic>> _imleciGotur(int no, String not) async {
    final o = await _oge(no);
    if (o == null) throw 'Sayfada $no numaralı öğe yok (sayfa değişmiş olabilir)';
    imlec = Offset((o['x'] as num).toDouble(), (o['y'] as num).toDouble());
    imlecNotu = not;
    notifyListeners();
    await Future<void>.delayed(const Duration(milliseconds: 650));
    return o;
  }

  Future<void> _tiklamaGoster() async {
    tiklama = true;
    notifyListeners();
    await Future<void>.delayed(const Duration(milliseconds: 220));
    tiklama = false;
    notifyListeners();
  }

  Future<String> tikla(int no) async {
    final o = await _imleciGotur(no, 'Tıklıyorum');
    await _tiklamaGoster();
    await denetci?.executeScript('''
(() => { const e = document.querySelector('[data-kodi-no="$no"]'); if (!e) return;
  e.focus(); e.click(); })()''');
    await yuklenmeyiBekle(const Duration(seconds: 4));
    await sayfayiOku();
    return '"${o['metin'] ?? no}" tıklandı';
  }

  /// Öğe numarası olmadan, yazısıyla tıklar ("Releases"): sayfadaki
  /// bağlantı ve düğmeler arasında yazısı tam tutan (yoksa içeren) en kısa
  /// öğe bulunur, ona numara verilip her zamanki gibi tıklanır.
  Future<String> yazisiylaTikla(String yazi) async {
    final c = denetci;
    if (c == null) throw 'Tarayıcı açık değil';
    final r = await c.executeScript('''
(() => { const aranan = ${jsonEncode(yazi)}.toLowerCase().replace(/\\s+/g, ' ').trim();
  const secici = 'a[href],button,[role=button],[role=link],[role=tab],[role=menuitem],summary,input[type=submit],input[type=button]';
  const yazisi = e => (e.innerText || e.value || e.getAttribute('aria-label') || e.title || '')
    .toLowerCase().replace(/\\s+/g, ' ').trim();
  const adaylar = [...document.querySelectorAll(secici)].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; });
  const tam = adaylar.filter(e => yazisi(e) === aranan);
  const icinde = adaylar.filter(e => yazisi(e).includes(aranan));
  const liste = (tam.length ? tam : icinde).sort((a, b) => yazisi(a).length - yazisi(b).length);
  const e = liste[0]; if (!e) return null;
  let no = +e.getAttribute('data-kodi-no') || 0;
  if (!no) { let enBuyuk = 0; document.querySelectorAll('[data-kodi-no]').forEach(x => {
      enBuyuk = Math.max(enBuyuk, +x.getAttribute('data-kodi-no') || 0); });
    no = enBuyuk + 1; e.setAttribute('data-kodi-no', String(no)); }
  return no; })()''');
    final no = r is num ? r.toInt() : null;
    if (no == null) throw 'Sayfada "$yazi" yazan bir düğme ya da bağlantı bulamadım';
    return tikla(no);
  }

  Future<String> yaz(int no, String metin, {bool gonder = false}) async {
    final o = await _imleciGotur(no, 'Yazıyorum');
    if (o['sifre'] == true) throw 'Şifre kutularına yazmam; şifreni kendin yazmalısın';
    await _tiklamaGoster();
    final m = jsonEncode(metin);
    final sonuc = await denetci?.executeScript('''
(() => { const e = document.querySelector('[data-kodi-no="$no"]'); if (!e) return 'yok';
  if (e.type === 'password') return 'sifre';
  e.focus();
  if (e.isContentEditable) { e.textContent = $m; }
  else { const p = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
         Object.getOwnPropertyDescriptor(p, 'value').set.call(e, $m); }
  e.dispatchEvent(new Event('input', {bubbles: true}));
  e.dispatchEvent(new Event('change', {bubbles: true}));
  if (${gonder ? 'true' : 'false'}) {
    if (e.form) { e.form.requestSubmit ? e.form.requestSubmit() : e.form.submit(); }
    else { ['keydown', 'keypress', 'keyup'].forEach(t => e.dispatchEvent(new KeyboardEvent(t,
      {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}))); }
  }
  return 'ok'; })()''');
    if (sonuc == 'sifre') throw 'Şifre kutularına yazmam; şifreni kendin yazmalısın';
    if (sonuc == 'yok') throw 'Sayfada $no numaralı öğe yok';
    if (gonder) await yuklenmeyiBekle(const Duration(seconds: 6));
    await sayfayiOku();
    return gonder ? 'Yazıldı ve gönderildi' : 'Yazıldı';
  }

  /// Rehber: sayfada aranan yazılı bir düğmeyi vurgular ve Kodi imlecini
  /// oraya götürür (tıklamaz; kullanıcı kendisi tıklar).
  Future<bool> vurgula(List<String> yazilar, String not) async {
    final c = denetci;
    if (c == null) return false;
    final r = await c.executeScript('''
(() => { const aranan = ${jsonEncode(yazilar)}.map(s => s.toLowerCase());
  const adaylar = [...document.querySelectorAll('button,a,[role=button]')];
  const e = adaylar.find(x => { const t = (x.innerText || '').trim().toLowerCase();
    return t && aranan.some(a => t.includes(a)); });
  if (!e) return null;
  e.scrollIntoView({block: 'center'});
  e.style.outline = '3px solid #7C5CF5'; e.style.outlineOffset = '3px';
  e.style.boxShadow = '0 0 0 6px rgba(124,92,245,.35)';
  const r = e.getBoundingClientRect();
  return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()''');
    if (r is! Map) return false;
    imlec = Offset((r['x'] as num).toDouble(), (r['y'] as num).toDouble());
    imlecNotu = not;
    notifyListeners();
    return true;
  }

  /// Rehberde, açık sayfaya göre ipucu: anahtar sayfasında düğmeyi gösterir.
  Future<void> rehberIpucu() async {
    if (!adres.contains('console.groq.com')) return;
    await Future<void>.delayed(const Duration(milliseconds: 900));
    // Giriş sayfasında bir şey gösterilmez (hesap açmayı kullanıcı kendisi yapar);
    // anahtar sayfasında "Create API Key" düğmesi gösterilir.
    if (!await vurgula(['Create API Key'], 'Buna bas')) {
      imlec = null;
      imlecNotu = null;
      notifyListeners();
    }
  }

  void rehberiAc() {
    rehberAcik = true;
    notifyListeners();
    if (hazir) {
      if (!adres.contains('console.groq.com')) {
        git(kGroqAnahtarSayfasi);
      } else {
        rehberIpucu();
      }
    }
  }

  void rehberiKapat() {
    rehberAcik = false;
    notifyListeners();
  }

  /// Sekme görünmez olunca: WebView kare üretmeyi ve betik çalıştırmayı bırakır.
  Future<void> askiyaAl() async {
    final c = _c;
    if (c == null || !hazir || _askida) return;
    _askida = true;
    _gorunurlukUygula();
    try {
      await c.suspend();
    } catch (_) {}
  }

  /// Sekme yeniden görünür olunca (ya da Kodi tarayıcıda iş yapacakken).
  Future<void> uyandir() async {
    final c = _c;
    if (c == null || !hazir || !_askida) return;
    _askida = false;
    try {
      await c.resume();
    } catch (_) {}
    // resume WebView'i görünür yapar; taşıyıcının durumu yeniden uygulanır.
    _gorunurNative = !_gorunmeli;
    _gorunurlukUygula();
  }

  /// Tarayıcı sekmesi kapatılınca WebView ve arkasındaki Edge süreçleri kapatılır.
  Future<void> kapat() async {
    _kusak++;
    final c = _c;
    if (c != null && hazir) {
      // Pencere hemen kaybolsun (kapatma biraz sürebilir).
      c.setWindowVisible(false).catchError((_) {});
    }
    _gorunurNative = false;
    _alan = null;
    _sonBildirilen = null;
    _sonKesik = '';
    _sonImlec = '';
    onizleme = null;
    altGoruntu = null;
    _altZamanlayici?.cancel();
    _altZamanlayici = null;
    for (final a in _abonelikler) {
      await a.cancel();
    }
    _abonelikler.clear();
    _c = null;
    _baslatma = null;
    hazir = false;
    _askida = false;
    hata = null;
    adres = '';
    baslik = '';
    yukleniyor = false;
    geriVar = false;
    ileriVar = false;
    imlec = null;
    imlecNotu = null;
    tiklama = false;
    sonBilgi = const {};
    rehberAcik = false;
    notifyListeners();
    if (c == null) return;
    // Webview bileşeni ağaçtan çıktıktan sonra kapatılır.
    await WidgetsBinding.instance.endOfFrame;
    try {
      await c.dispose();
    } catch (_) {}
  }
}

TarayiciDurumu get kTarayici => TarayiciDurumu.ornek;

/// API kurulum rehberini açar (tarayıcı sekmesinde, sağda rehber paneli).
void kodiKurulumRehberi(BuildContext context) {
  kTarayici.rehberiAc();
  context.read<EditorProvider>().openBrowser();
}

/// Tarayıcı sekmesi: adres çubuğu, sayfa, Kodi imleci ve (açıksa) rehber.
class TarayiciSekmesi extends StatefulWidget {
  const TarayiciSekmesi({super.key});
  @override
  State<TarayiciSekmesi> createState() => _TarayiciSekmesiState();
}

class _TarayiciSekmesiState extends State<TarayiciSekmesi> {
  final _adres = TextEditingController();
  final _adresOdak = FocusNode(debugLabel: 'tarayici-adres');

  @override
  void initState() {
    super.initState();
    kTarayici.addListener(_degisti);
    kTarayici.sekmedeMi(true);
    kTarayici.baslat();
    kTarayici.uyandir();
    _adres.text = kTarayici.adres;
  }

  @override
  void dispose() {
    kTarayici.removeListener(_degisti);
    // Başka sekmeye geçildi ya da sekme kapandı: sayfa gizlenir, boşta
    // beklemesin diye askıya alınır.
    kTarayici.sekmedeMi(false);
    kTarayici.askiyaAl();
    _adres.dispose();
    _adresOdak.dispose();
    super.dispose();
  }

  void _degisti() {
    if (!mounted) return;
    if (!_adresOdak.hasFocus && _adres.text != kTarayici.adres) _adres.text = kTarayici.adres;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final t = kTarayici;
    final cs = Theme.of(context).colorScheme;
    final c = t.denetci;
    final cubuk = Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(bottom: BorderSide(color: cs.outlineVariant)),
      ),
      child: Row(children: [
        PanelDugmesi(
            ikon: Icons.arrow_back_rounded,
            ipucu: 'Geri',
            onPressed: t.geriVar ? t.geri : null),
        PanelDugmesi(
            ikon: Icons.arrow_forward_rounded,
            ipucu: 'İleri',
            onPressed: t.ileriVar ? t.ileri : null),
        PanelDugmesi(
            ikon: t.yukleniyor ? Icons.close_rounded : Icons.refresh_rounded,
            ipucu: t.yukleniyor ? 'Durdur' : 'Yenile',
            onPressed: c == null ? null : (t.yukleniyor ? () => c.stop() : t.yenile)),
        PanelDugmesi(
            ikon: Icons.home_outlined,
            ipucu: 'Google',
            onPressed: c == null ? null : () => t.git(kTarayiciAnaSayfa)),
        const SizedBox(width: 6),
        Expanded(
          child: SizedBox(
            height: 30,
            child: TextField(
              controller: _adres,
              focusNode: _adresOdak,
              style: const TextStyle(fontSize: 12.5),
              decoration: InputDecoration(
                isDense: true,
                hintText: 'Adres yaz ya da Google\'da ara',
                prefixIcon: Icon(
                    t.adres.startsWith('https://') ? Icons.lock_outline : Icons.search_rounded,
                    size: 16),
                prefixIconConstraints: const BoxConstraints(minWidth: 30),
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                filled: true,
                fillColor: cs.surfaceContainerHighest,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(15), borderSide: BorderSide.none),
              ),
              onTap: () =>
                  _adres.selection = TextSelection(baseOffset: 0, extentOffset: _adres.text.length),
              onSubmitted: (s) {
                _adresOdak.unfocus();
                t.git(s);
              },
            ),
          ),
        ),
        const SizedBox(width: 6),
        PanelDugmesi(
          ikon: Icons.key_rounded,
          ipucu: 'API kurulum rehberi (Kodi\'ye yapay zekâ bağla)',
          secili: t.rehberAcik,
          onPressed: t.rehberAcik ? t.rehberiKapat : t.rehberiAc,
        ),
      ]),
    );

    Widget sayfa;
    if (t.hata != null) {
      sayfa = Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(t.hata!, textAlign: TextAlign.center, style: TextStyle(color: cs.error)),
        ),
      );
    } else if (c == null) {
      sayfa = const Center(child: CircularProgressIndicator(strokeWidth: 2));
    } else {
      // Sayfanın kendisi bu alanın üstünde, TürKod penceresinin içindeki
      // ayrı bir pencerede çizilir (bkz. TarayiciDurumu: pencereli sayfa).
      // Burada yalnızca yeri bildirilir; menü ya da iletişim kutusu açıkken
      // sayfanın anlık görüntüsü gösterilir. Kodi'nin imleci sayfanın içinde.
      final onizleme = t.onizleme ?? t.altGoruntu;
      sayfa = _SayfaYeri(
        dpr: MediaQuery.devicePixelRatioOf(context),
        child: onizleme == null
            ? ColoredBox(color: cs.surface)
            : Image.memory(onizleme,
                fit: BoxFit.fill, gaplessPlayback: true, filterQuality: FilterQuality.medium),
      );
    }

    return Column(children: [
      cubuk,
      // Yükleme çubuğu adres çubuğunun altında (sayfanın üstüne çizilemez).
      SizedBox(
        height: 2,
        child: t.yukleniyor ? const LinearProgressIndicator(minHeight: 2) : null,
      ),
      Expanded(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: sayfa),
          if (t.rehberAcik) const SizedBox(width: 330, child: _KurulumRehberi()),
        ]),
      ),
    ]);
  }
}

/// Sayfa penceresinin yeri: bu bileşenin ekrandaki dikdörtgeni her yerleşim
/// ve çizimden sonra TarayiciDurumu'na bildirilir (pencere oraya taşınır).
class _SayfaYeri extends SingleChildRenderObjectWidget {
  final double dpr;
  const _SayfaYeri({required this.dpr, super.child});

  @override
  RenderObject createRenderObject(BuildContext context) => _SayfaYeriKutusu(dpr);

  @override
  void updateRenderObject(BuildContext context, _SayfaYeriKutusu kutu) {
    kutu.dpr = dpr;
  }
}

class _SayfaYeriKutusu extends RenderProxyBox {
  double dpr;
  bool _bekliyor = false;
  _SayfaYeriKutusu(this.dpr);

  void _bildir() {
    if (_bekliyor) return;
    _bekliyor = true;
    SchedulerBinding.instance.addPostFrameCallback((_) {
      _bekliyor = false;
      if (!attached || !hasSize) return;
      kTarayici.alaniBildir(localToGlobal(Offset.zero) & size, dpr);
    });
  }

  @override
  void performLayout() {
    super.performLayout();
    _bildir();
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    super.paint(context, offset);
    _bildir();
  }
}

/// Sayfanın üstüne açılan menü ve iletişim kutularını sayar: açıkken sayfa
/// penceresi gizlenir, yerine anlık görüntüsü konur (MaterialApp'e eklenir).
class TarayiciOrtuGozlemcisi extends NavigatorObserver {
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    if (previousRoute != null) kTarayici.ortuDegisti(1);
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    if (previousRoute != null) kTarayici.ortuDegisti(-1);
  }

  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) {
    if (previousRoute != null) kTarayici.ortuDegisti(-1);
  }
}

final kTarayiciOrtuGozlemcisi = TarayiciOrtuGozlemcisi();

// Kodi'nin sayfanın içinde çizilen imleci (mor ok ve not; tıklarken halka).
const String _kImlecBetigi = r'''
(() => { const x = __X__, y = __Y__, not = __NOT__, tik = __TIK__;
  let k = document.getElementById('__kodi_imlec');
  if (!k) {
    k = document.createElement('div');
    k.id = '__kodi_imlec';
    k.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;' +
      'transition:transform .55s cubic-bezier(.65,0,.35,1);will-change:transform';
    k.innerHTML = '<div class="h" style="position:absolute;left:-11px;top:-12px;width:34px;height:34px;' +
      'border-radius:50%;background:rgba(124,92,245,.35);transform:scale(0);transition:transform .18s"></div>' +
      '<svg width="26" height="30" viewBox="0 0 26 30" style="position:absolute;left:0;top:0;' +
      'filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))"><path d="M3 2 L3 25 L9 19 L13.5 28.5 L17.5 26.6 ' +
      'L13 17.5 L21.5 17.5 Z" fill="#7C5CF5" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>' +
      '<div class="n" style="position:absolute;left:24px;top:22px;background:#7C5CF5;color:#fff;' +
      'font:600 12px Segoe UI,sans-serif;padding:3px 9px;border-radius:10px;white-space:nowrap;' +
      'box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>';
    (document.body || document.documentElement).appendChild(k);
  }
  k.style.transform = 'translate(' + (x - 3) + 'px,' + (y - 2) + 'px)';
  k.querySelector('.h').style.transform = tik ? 'scale(1)' : 'scale(0)';
  const n = k.querySelector('.n');
  n.textContent = not;
  n.style.display = not ? 'block' : 'none';
})()
''';

/// API kurulum rehberi: Groq'tan ücretsiz anahtar al, yapıştır, bağla.
class _KurulumRehberi extends StatefulWidget {
  const _KurulumRehberi();
  @override
  State<_KurulumRehberi> createState() => _KurulumRehberiState();
}

class _KurulumRehberiState extends State<_KurulumRehberi> {
  final _anahtar = TextEditingController();
  bool _gizli = true;
  bool _mesgul = false;
  String? _hata;
  String? _basari;

  @override
  void dispose() {
    _anahtar.dispose();
    super.dispose();
  }

  Future<void> _yapistir() async {
    final v = await Clipboard.getData(Clipboard.kTextPlain);
    if (v?.text != null) setState(() => _anahtar.text = v!.text!.trim());
  }

  Future<void> _bagla() async {
    setState(() {
      _mesgul = true;
      _hata = null;
    });
    try {
      final r = await context
          .read<BackendService>()
          .call('kodi_kurulum', {'saglayici': 'groq', 'anahtar': _anahtar.text});
      if (!mounted) return;
      if (r['ok'] == true) {
        await context.read<SettingsProvider>().load();
        if (!mounted) return;
        _anahtar.clear();
        setState(() => _basari = 'Hazır! Kodi artık ${r['saglayici']} • ${r['model']} ile konuşuyor.');
        context.read<KodiProvider>().kurulumBitti('${r['saglayici']} • ${r['model']}');
      } else {
        setState(() => _hata = '${r['hata'] ?? 'Bağlanamadım.'}');
      }
    } catch (e) {
      if (mounted) setState(() => _hata = e is BackendException ? e.message : '$e');
    } finally {
      if (mounted) setState(() => _mesgul = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final kucuk = TextStyle(fontSize: 12, color: cs.onSurface.withValues(alpha: 0.8), height: 1.35);
    Widget adim(int n, String baslik, String aciklama, [Widget? ek]) => Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CircleAvatar(
                radius: 11,
                backgroundColor: _kKodiMor,
                child: Text('$n',
                    style: const TextStyle(
                        color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700))),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(baslik, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(aciklama, style: kucuk),
                if (ek != null) ...[const SizedBox(height: 6), ek],
              ]),
            ),
          ]),
        );
    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainer,
        border: Border(left: BorderSide(color: cs.outlineVariant)),
      ),
      child: ListView(padding: const EdgeInsets.fromLTRB(14, 12, 14, 14), children: [
        Row(children: [
          const KodiSimgesi(boyut: 26),
          const SizedBox(width: 8),
          const Expanded(
            child: Text('Kodi\'ye beyin bulalım',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          ),
          PanelDugmesi(ikon: Icons.close_rounded, ipucu: 'Rehberi kapat', onPressed: kTarayici.rehberiKapat),
        ]),
        const SizedBox(height: 6),
        Text(
            'Groq\'tan ücretsiz bir anahtar alıp TürKod\'a koyacağız; modeli ben seçerim. '
            'Hesap açma adımını bir büyüğünle yap.',
            style: kucuk),
        const SizedBox(height: 14),
        adim(
            1,
            'Groq\'a giriş yap',
            'Soldaki sayfada Google, GitHub ya da e-postanla hesap aç veya giriş yap.',
            OutlinedButton.icon(
              icon: const Icon(Icons.open_in_browser_rounded, size: 16),
              label: const Text('Groq anahtar sayfasını aç'),
              onPressed: () => kTarayici.git(kGroqAnahtarSayfasi),
            )),
        adim(
            2,
            'Anahtar oluştur ve kopyala',
            '"Create API Key" düğmesine bas, bir ad ver (ör. TürKod), çıkan anahtarı kopyala. '
                'gsk_ ile başlar ve yalnızca bir kez gösterilir.',
            OutlinedButton.icon(
              icon: const Icon(Icons.ads_click_rounded, size: 16),
              label: const Text('Düğmeyi göster'),
              onPressed: kTarayici.rehberIpucu,
            )),
        adim(
            3,
            'Buraya yapıştır ve bağla',
            'Anahtarı kimseyle paylaşma. TürKod onu bu bilgisayarda şifreleyerek saklar.',
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              TextField(
                controller: _anahtar,
                obscureText: _gizli,
                style: const TextStyle(fontSize: 12.5),
                decoration: InputDecoration(
                  isDense: true,
                  hintText: 'gsk_…',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    tooltip: _gizli ? 'Göster' : 'Gizle',
                    icon: Icon(_gizli ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                        size: 18),
                    onPressed: () => setState(() => _gizli = !_gizli),
                  ),
                ),
                onSubmitted: (_) => _mesgul ? null : _bagla(),
              ),
              const SizedBox(height: 6),
              Row(children: [
                OutlinedButton.icon(
                  icon: const Icon(Icons.content_paste_rounded, size: 16),
                  label: const Text('Yapıştır'),
                  onPressed: _mesgul ? null : _yapistir,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: FilledButton.icon(
                    icon: _mesgul
                        ? const SizedBox(
                            width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.link_rounded, size: 16),
                    label: const Text('Bağla'),
                    style: FilledButton.styleFrom(backgroundColor: _kKodiMor),
                    onPressed: _mesgul ? null : _bagla,
                  ),
                ),
              ]),
            ])),
        if (_hata != null)
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
                color: cs.errorContainer, borderRadius: BorderRadius.circular(8)),
            child: Text(_hata!, style: TextStyle(color: cs.onErrorContainer, fontSize: 12.5)),
          ),
        if (_basari != null) ...[
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
                color: const Color(0xFF22C55E).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8)),
            child: Text(_basari!, style: const TextStyle(fontSize: 12.5)),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            icon: const Icon(Icons.smart_toy_outlined, size: 16),
            label: const Text('Kodi ile konuş'),
            style: FilledButton.styleFrom(backgroundColor: _kKodiMor),
            onPressed: () {
              kTarayici.rehberiKapat();
              context.read<KodiProvider>().ac();
            },
          ),
        ],
        const SizedBox(height: 10),
        Text('Başka bir sağlayıcı mı kullanmak istiyorsun? Ayarlar → Yapay Zekâ: Modeller.',
            style: kucuk.copyWith(fontSize: 11.5)),
        TextButton(
          onPressed: () => context.read<EditorProvider>().openSettings(),
          child: const Text('Ayarları aç'),
        ),
      ]),
    );
  }
}
