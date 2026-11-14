// EXE'ye Dönüştür: açık programı her Windows bilgisayarda çalışan bir EXE
// dosyasına çeviren panel (Çalıştır menüsü).
//
// Panel seçenekleri tiklerle seçtirir ve altta, seçimlere göre canlı değişen
// komutu gösterir. "EXE'ye Dönüştür" bu komutu sekmenin terminalinde
// çalıştırır; aynı komut terminale ya da TürKod Kabuğu'na elle de yazılabilir.
// Komutun kendisi backend'dedir: turkod_ide/exe_donusturucu.py (SECENEKLER
// listesi buradaki bayraklarla aynı olmalı).
part of 'main.dart';

enum ExePencere { turkod, konsol, yok }

class ExeAyarlari {
  String ad = '';
  String kayitYeri = '';
  ExePencere pencere = ExePencere.turkod;
  bool kaynakAcik = false;
  bool klasorlu = false;
  bool sondaBekle = false;
  String simge = '';
  final List<String> ekler = [];

  /// Tırnak içindeki sondaki "\" ikilenir: Windows komut satırında
  /// `"C:\Oyun Klasörü\"` biçimindeki \" kapanış tırnağını kaçırıyor,
  /// sonraki seçenekler klasör adına karışıyordu.
  static String _tirnak(String s) {
    if (s.isNotEmpty && !RegExp(r'[\s&|<>^]').hasMatch(s)) return s;
    final sondaki = s.length - s.replaceFirst(RegExp(r'\\+$'), '').length;
    return '"$s${'\\' * sondaki}"';
  }

  /// [dosya]: .trpy dosyasının yolu. Python tarafındaki
  /// exe_donusturucu.komut_metni ile aynı sırayı üretir.
  String komut(String dosya) {
    final k = <String>['turkod', 'exe_yap', _tirnak(dosya)];
    if (ad.trim().isNotEmpty) k.addAll(['--ad', _tirnak(ad.trim())]);
    if (kayitYeri.trim().isNotEmpty) {
      k.addAll(['--kayit-yeri', _tirnak(kayitYeri.trim())]);
    }
    if (pencere == ExePencere.konsol) k.add('--windows-konsolu');
    if (pencere == ExePencere.yok) k.add('--terminalsiz');
    if (kaynakAcik) k.add('--kaynak-acik');
    if (klasorlu) k.add('--klasorlu');
    if (sondaBekle && pencere == ExePencere.konsol) k.add('--sonda-bekle');
    if (simge.trim().isNotEmpty) k.addAll(['--simge', _tirnak(simge.trim())]);
    for (final e in ekler) {
      k.addAll(['--dosya-ekle', _tirnak(e)]);
    }
    return k.join(' ');
  }
}

/// EXE'nin kaydedileceği klasör: boşsa kod dosyasının klasörü; göreli bir
/// yol kod dosyasının klasörüne göre çözülür (exe_donusturucu.exe_yap ile
/// aynı kural; "\Oyunlar" gibi kök-göreli yol o sürücünün köküne göre).
String exeKayitKlasoru(String kodKlasoru, String kayitYeri) {
  final k = kayitYeri.trim();
  if (k.isEmpty) return kodKlasoru;
  if (p.isRootRelative(k)) {
    return p.normalize(p.join(p.rootPrefix(kodKlasoru), k.substring(1)));
  }
  return p.normalize(p.join(kodKlasoru, k));
}

/// Panelde son seçilen ayarlar (dosya yoluna göre; program açık kaldıkça).
final Map<String, ExeAyarlari> _exeAyarHafizasi = {};

/// Çalıştır → EXE'ye Dönüştür…
Future<void> exeDonusturmePaneliAc(BuildContext context) async {
  final ed = context.read<EditorProvider>();
  final tab = ed.activeTab;
  if (tab == null || ozelSekmeMi(tab.path)) {
    showAppSnackbar(context, 'EXE yapmak için bir kod sekmesi aç',
        kind: SnackKind.error);
    return;
  }
  if (tab.content.trim().isEmpty) {
    showAppSnackbar(context, 'Kod boş', kind: SnackKind.error);
    return;
  }
  // EXE kaydedilmiş dosyadan yapılır (yanındaki modüller ve dosyalar da
  // bulunsun diye); kaydedilmemiş değişiklikler önce kaydedilir.
  if (tab.isUntitled || tab.dirty) {
    final kaydedildi = await ed.saveActive();
    if (!kaydedildi || !context.mounted) {
      if (context.mounted) {
        showAppSnackbar(context, 'EXE yapmak için önce dosyayı kaydet',
            kind: SnackKind.error);
      }
      return;
    }
  }
  final dosya = ed.activeTab?.filePath;
  if (dosya == null || !context.mounted) return;
  final term = context.read<TerminalProvider>();
  // Komut bu sekmenin terminalinde çalışır; çalışan program varsa ona girdi
  // olarak giderdi (TürKod Kabuğu ise komutu kendisi anlar).
  if (term.isRunning && !term._kabukModu) {
    showAppSnackbar(context, 'Önce bu sekmede çalışan programı durdur',
        kind: SnackKind.error);
    return;
  }
  final ayar = _exeAyarHafizasi.putIfAbsent(dosya, ExeAyarlari.new);
  final komut = await showDialog<String>(
    context: context,
    builder: (_) => ExeDonusturmePaneli(dosya: dosya, ayar: ayar),
  );
  if (komut == null || !context.mounted) return;
  context.read<UiProvider>().focusTerminal();
  await context.read<TerminalProvider>().sendCommand(komut);
}

/// Çalıştır → EXE'nin Kaynak Kodunu Aç…: "Kaynak koduna bakılabilsin"
/// seçilerek yapılmış bir TürKod EXE'sinin kodunu yeni sekmede açar.
Future<void> exeKaynaginiAc(BuildContext context) async {
  final r = await FilePicker.platform.pickFiles(
    dialogTitle: 'Kaynak koduna bakılacak EXE',
    type: FileType.custom,
    allowedExtensions: const ['exe'],
  );
  final yol = r?.files.single.path;
  if (yol == null || !context.mounted) return;
  showAppSnackbar(context, '${p.basename(yol)} okunuyor…');
  final backend = context.read<BackendService>();
  final ed = context.read<EditorProvider>();
  try {
    final sonuc = await backend.call('exe_kaynagi', {'yol': yol});
    final kaynak = sonuc['kaynak']?.toString() ?? '';
    await ed.createUntitled(
      name: '${p.basenameWithoutExtension(yol)} (EXE kaynağı).trpy',
      content: kaynak,
      dirty: true,
    );
    if (context.mounted) {
      showAppSnackbar(context, 'EXE\'nin TürKod kodu yeni sekmede açıldı',
          kind: SnackKind.success);
    }
  } on BackendException catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, e.message, kind: SnackKind.error);
    }
  } catch (e) {
    if (context.mounted) {
      showAppSnackbar(context, 'EXE okunamadı: $e', kind: SnackKind.error);
    }
  }
}

class ExeDonusturmePaneli extends StatefulWidget {
  final String dosya;
  final ExeAyarlari ayar;
  const ExeDonusturmePaneli(
      {super.key, required this.dosya, required this.ayar});
  @override
  State<ExeDonusturmePaneli> createState() => _ExeDonusturmePaneliState();
}

class _ExeDonusturmePaneliState extends State<ExeDonusturmePaneli> {
  late final ExeAyarlari a = widget.ayar;
  late final TextEditingController _ad = TextEditingController(text: a.ad);
  late final TextEditingController _kayit =
      TextEditingController(text: a.kayitYeri);
  late final TextEditingController _simge =
      TextEditingController(text: a.simge);

  String get _klasor => p.dirname(widget.dosya);
  String get _varsayilanAd => p.basenameWithoutExtension(widget.dosya);

  @override
  void dispose() {
    _ad.dispose();
    _kayit.dispose();
    _simge.dispose();
    super.dispose();
  }

  /// Kod dosyasının klasöründeki yollar göreli yazılır (komut kısa kalsın).
  String _goreli(String yol) =>
      p.isWithin(_klasor, yol) ? p.relative(yol, from: _klasor) : yol;

  Future<void> _kayitYeriSec() async {
    final d = await FilePicker.platform.getDirectoryPath(
        dialogTitle: 'EXE\'nin kaydedileceği klasör',
        initialDirectory: _kayit.text.isEmpty ? _klasor : _kayit.text);
    if (d == null || !mounted) return;
    setState(() => _kayit.text = a.kayitYeri = d);
  }

  Future<void> _simgeSec() async {
    final r = await FilePicker.platform.pickFiles(
        dialogTitle: 'EXE simgesi (.ico)',
        initialDirectory: _klasor,
        type: FileType.custom,
        allowedExtensions: const ['ico']);
    final yol = r?.files.single.path;
    if (yol == null || !mounted) return;
    setState(() => _simge.text = a.simge = _goreli(yol));
  }

  Future<void> _dosyaEkle({required bool klasor}) async {
    String? yol;
    if (klasor) {
      yol = await FilePicker.platform.getDirectoryPath(
          dialogTitle: 'EXE\'ye eklenecek klasör', initialDirectory: _klasor);
    } else {
      final r = await FilePicker.platform.pickFiles(
          dialogTitle: 'EXE\'ye eklenecek dosya', initialDirectory: _klasor);
      yol = r?.files.single.path;
    }
    if (yol == null || !mounted) return;
    final g = _goreli(yol);
    if (!a.ekler.contains(g)) setState(() => a.ekler.add(g));
  }

  Widget _baslik(String metin) {
    final t = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 4),
      child: Text(metin,
          style: t.textTheme.labelLarge
              ?.copyWith(color: t.colorScheme.primary, letterSpacing: 0.3)),
    );
  }

  Widget _pencereSecenegi(ExePencere deger, String baslik, String aciklama) =>
      RadioListTile<ExePencere>(
        dense: true,
        contentPadding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        value: deger,
        title: Text(baslik),
        subtitle: Text(aciklama),
      );

  Widget _tik(bool deger, ValueChanged<bool> degisti, String baslik,
          String aciklama, {bool etkin = true}) =>
      CheckboxListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        controlAffinity: ListTileControlAffinity.leading,
        value: deger,
        onChanged: etkin ? (v) => setState(() => degisti(v ?? false)) : null,
        title: Text(baslik),
        subtitle: Text(aciklama),
      );

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final komut = a.komut(widget.dosya);
    final hedefKlasor = exeKayitKlasoru(_klasor, a.kayitYeri);
    // İpuçları (boş alanda görünen varsayılanlar) yazılmış değerle
    // karışmasın diye soluk gösterilir.
    final ipucu = TextStyle(color: t.colorScheme.onSurface.withValues(alpha: 0.4));
    final ad = a.ad.trim().isEmpty ? _varsayilanAd : a.ad.trim();
    final hedef = a.klasorlu
        ? p.join(hedefKlasor, ad, '$ad.exe')
        : p.join(hedefKlasor, '$ad.exe');
    return AlertDialog(
      titlePadding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      title: Row(children: [
        Icon(Icons.inventory_2_outlined, color: t.colorScheme.primary),
        const SizedBox(width: 10),
        const Text('EXE\'ye Dönüştür'),
      ]),
      content: SizedBox(
        width: 640,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Programın, TürKod kurulu olmayan her Windows bilgisayarda '
                'çift tıklanınca çalışan bir EXE dosyasına dönüşür.',
                style: t.textTheme.bodySmall,
              ),
              const SizedBox(height: 4),
              Text(p.basename(widget.dosya),
                  style: t.textTheme.bodySmall?.copyWith(
                      fontFamily: kMonoFontFamily,
                      color: t.colorScheme.onSurface.withValues(alpha: 0.6))),
              _baslik('Ad ve yer'),
              TextField(
                controller: _ad,
                decoration: InputDecoration(
                  labelText: 'EXE\'nin adı',
                  hintText: _varsayilanAd,
                  hintStyle: ipucu,
                  isDense: true,
                  floatingLabelBehavior: FloatingLabelBehavior.always,
                  suffixText: '.exe',
                ),
                onChanged: (v) => setState(() => a.ad = v),
              ),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _kayit,
                    decoration: InputDecoration(
                      labelText: 'Kaydedileceği klasör',
                      hintText: '$_klasor (kod dosyasının klasörü)',
                      hintStyle: ipucu,
                      isDense: true,
                      floatingLabelBehavior: FloatingLabelBehavior.always,
                    ),
                    onChanged: (v) => setState(() => a.kayitYeri = v),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  icon: const Icon(Icons.folder_open, size: 16),
                  label: const Text('Gözat'),
                  onPressed: _kayitYeriSec,
                ),
              ]),
              _baslik('Program nasıl açılsın?'),
              RadioGroup<ExePencere>(
                groupValue: a.pencere,
                onChanged: (v) => setState(() => a.pencere = v!),
                child: Column(children: [
                  _pencereSecenegi(ExePencere.turkod, 'TürKod terminalinde',
                      'Koyu TürKod terminal penceresi açılır; yazdır çıktısı '
                      've girdi_al orada görünür. Hatalar Türkçe ve renklidir.'),
                  _pencereSecenegi(ExePencere.konsol, 'Windows konsolunda',
                      'Klasik siyah Windows komut penceresinde çalışır.'),
                  _pencereSecenegi(ExePencere.yok, 'Terminal olmadan',
                      'Hiç terminal açılmaz; yalnızca programın kendi '
                      'penceresi görünür (oyunlar, kaplumbağa çizimleri, '
                      'pencereli uygulamalar). Hata olursa ileti kutusunda '
                      'gösterilir.'),
                ]),
              ),
              _baslik('Seçenekler'),
              _tik(a.kaynakAcik, (v) => a.kaynakAcik = v,
                  'Kaynak koduna bakılabilsin',
                  'EXE\'nin TürKod kodu "turkod kaynak program.exe" komutuyla '
                  'ya da Çalıştır → EXE\'nin Kaynak Kodunu Aç ile görülebilir. '
                  'İşaretlenmezse kodun yalnızca derlenmiş hâli konur.'),
              _tik(a.klasorlu, (v) => a.klasorlu = v,
                  'Tek dosya yerine klasör yap',
                  'Program daha hızlı açılır, ama başka bilgisayara bütün '
                  'klasör kopyalanmalı.'),
              _tik(a.sondaBekle, (v) => a.sondaBekle = v,
                  'Program bitince pencere kapanmasın',
                  'Windows konsolu "Kapatmak için Enter\'a basın" der '
                  '(yalnızca Windows konsolunda).',
                  etkin: a.pencere == ExePencere.konsol),
              _baslik('Simge ve dosyalar'),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _simge,
                    decoration: InputDecoration(
                      labelText: 'Simge (.ico, isteğe bağlı)',
                      hintText: 'TürKod simgesi',
                      hintStyle: ipucu,
                      isDense: true,
                      floatingLabelBehavior: FloatingLabelBehavior.always,
                    ),
                    onChanged: (v) => setState(() => a.simge = v),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  icon: const Icon(Icons.image_outlined, size: 16),
                  label: const Text('Seç'),
                  onPressed: _simgeSec,
                ),
              ]),
              const SizedBox(height: 10),
              Text(
                'Programın kullandığı resim, ses gibi dosyalar EXE\'nin içine '
                'konur; program onları kendi klasöründeymiş gibi bulur.',
                style: t.textTheme.bodySmall,
              ),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in a.ekler)
                  InputChip(
                    label: Text(e),
                    visualDensity: VisualDensity.compact,
                    onDeleted: () => setState(() => a.ekler.remove(e)),
                  ),
                ActionChip(
                  avatar: const Icon(Icons.note_add_outlined, size: 16),
                  label: const Text('Dosya ekle'),
                  visualDensity: VisualDensity.compact,
                  onPressed: () => _dosyaEkle(klasor: false),
                ),
                ActionChip(
                  avatar: const Icon(Icons.create_new_folder_outlined, size: 16),
                  label: const Text('Klasör ekle'),
                  visualDensity: VisualDensity.compact,
                  onPressed: () => _dosyaEkle(klasor: true),
                ),
              ]),
              _baslik('Çalışacak komut'),
              Container(
                padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
                decoration: BoxDecoration(
                  color: t.colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: t.colorScheme.outlineVariant),
                ),
                child: Row(children: [
                  Expanded(
                    child: SelectableText(
                      komut,
                      style: const TextStyle(
                          fontFamily: kMonoFontFamily,
                          fontFamilyFallback: kMonoFontFallback,
                          fontSize: 12.5,
                          height: 1.4),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Komutu kopyala',
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(Icons.copy, size: 16),
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: komut));
                      showAppSnackbar(context, 'Komut kopyalandı',
                          kind: SnackKind.success);
                    },
                  ),
                ]),
              ),
              const SizedBox(height: 6),
              Text(
                'Bu komutu terminale ya da TürKod Kabuğu\'na yazarak da aynı '
                'EXE\'yi yapabilirsin. Seçenekler: turkod exe_yap --yardim',
                style: t.textTheme.bodySmall?.copyWith(
                    color: t.colorScheme.onSurface.withValues(alpha: 0.65)),
              ),
              const SizedBox(height: 4),
              Text(
                'Oluşacak dosya: $hedef',
                style: t.textTheme.bodySmall?.copyWith(
                    color: t.colorScheme.onSurface.withValues(alpha: 0.65)),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Vazgeç'),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.inventory_2_outlined, size: 18),
          label: const Text('EXE\'ye Dönüştür'),
          onPressed: () => Navigator.pop(context, komut),
        ),
      ],
    );
  }
}
