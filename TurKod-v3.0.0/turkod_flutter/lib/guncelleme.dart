import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

/// backend.call ile aynı imza (main.dart'ı import etmemek için).
typedef BackendCagri = Future<Map<String, dynamic>> Function(String command,
    [Map<String, dynamic> params]);

const Color _yesil = Color(0xFF2ECC71);

/// Güncelleme denetimi.
///
/// * Açılışta (sessiz: true): yeni sürüm varsa "Yeni sürüm yayınlandı" paneli çıkar.
///   Daha önce "Atla" denen sürüm için tekrar sorulmaz.
/// * "Güncelleştirmeler > Güncelleştirmeleri Denetle" (sessiz: false): yeni sürüm
///   varsa aynı panel, yoksa "Programınız Güncel" paneli çıkar.
/// * [kaydet]: Yükle'ye basılınca, uygulama kapanmadan ÖNCE çağrılır. false dönerse
///   (bir dosya yazılamadıysa) güncelleme iptal edilir.
Future<void> guncellemeKontrolEt(
  BuildContext context,
  BackendCagri cagir, {
  Future<bool> Function()? kaydet,
  bool sessiz = true,
}) async {
  Map<String, dynamic> r;
  try {
    r = await cagir('guncelleme_kontrol');
  } catch (e) {
    if (!sessiz && context.mounted) {
      await _bilgiPaneli(
        context,
        ikon: Icons.error_outline,
        ikonRenk: Colors.orange,
        baslik: 'Güncelleme denetlenemedi',
        metin: _hataMetni(e),
      );
    }
    return;
  }
  if (!context.mounted) return;

  final mevcut = (r['mevcut'] ?? '').toString();
  if (r['guncelleme_var'] != true) {
    if (!sessiz) {
      await _bilgiPaneli(
        context,
        ikon: Icons.check_circle_outline,
        ikonRenk: _yesil,
        baslik: 'Programınız Güncel',
        metin: mevcut.isEmpty ? '' : 'Kurulu sürüm: $mevcut',
      );
    }
    return;
  }

  final yeni = (r['yeni'] ?? '').toString();
  if (sessiz && yeni.isNotEmpty && yeni == _atlananOku()) return;

  final yukle = await _yeniSurumPaneli(
      context, mevcut, yeni, (r['notlar'] ?? '').toString());
  if (!yukle) {
    _atlananYaz(yeni);
    return;
  }
  if (!context.mounted) return;
  await _guncelle(context, cagir, kaydet);
}

// ---------------------------------------------------------------------------
// Atlanan sürüm
// ---------------------------------------------------------------------------
File _atlananDosya() {
  final s = Platform.pathSeparator;
  final taban =
      Platform.environment['LOCALAPPDATA'] ?? Directory.systemTemp.path;
  return File('$taban${s}TurKod${s}atlanan_surum.txt');
}

String _atlananOku() {
  try {
    final f = _atlananDosya();
    return f.existsSync() ? f.readAsStringSync().trim() : '';
  } catch (_) {
    return '';
  }
}

void _atlananYaz(String surum) {
  try {
    final f = _atlananDosya();
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(surum);
  } catch (_) {}
}

String _hataMetni(Object e) {
  try {
    final m = (e as dynamic).message;
    if (m is String && m.isNotEmpty) return m;
  } catch (_) {}
  return e.toString();
}

// ---------------------------------------------------------------------------
// Güncelleme akışı: indir + doğrula -> kaydet -> kurulumu başlat -> çık
// ---------------------------------------------------------------------------
Future<void> _guncelle(BuildContext context, BackendCagri cagir,
    Future<bool> Function()? kaydet) async {
  final ilerleme = ValueNotifier<double?>(0);
  final metin = ValueNotifier<String>('Güncelleme indiriliyor...');

  unawaited(showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _IlerlemePaneli(ilerleme: ilerleme, metin: metin),
  ));

  void kapat() {
    if (context.mounted) Navigator.of(context, rootNavigator: true).pop();
  }

  String? yol;
  String? hata;
  try {
    await cagir('guncelleme_indir_baslat');
    while (true) {
      await Future<void>.delayed(const Duration(milliseconds: 300));
      final d = await cagir('guncelleme_indir_durum');
      final durum = (d['durum'] ?? '').toString();
      final toplam = d['toplam'] is num ? (d['toplam'] as num).toDouble() : 0.0;
      final indirilen =
          d['indirilen'] is num ? (d['indirilen'] as num).toDouble() : 0.0;
      if (toplam > 0) {
        ilerleme.value = (indirilen / toplam).clamp(0.0, 1.0).toDouble();
        metin.value =
            'Güncelleme indiriliyor... %${(indirilen / toplam * 100).floor()}';
      } else {
        ilerleme.value = null;
      }
      if (durum == 'bitti') {
        yol = (d['yol'] ?? '').toString();
        break;
      }
      if (durum == 'hata') {
        hata = (d['hata'] ?? 'Bilinmeyen hata').toString();
        break;
      }
      if (durum == 'yok') {
        hata = 'İndirme başlatılamadı.';
        break;
      }
    }
  } catch (e) {
    hata = _hataMetni(e);
  }

  if (hata != null || yol == null || yol.isEmpty) {
    kapat();
    if (context.mounted) {
      await _bilgiPaneli(
        context,
        ikon: Icons.error_outline,
        ikonRenk: Colors.orange,
        baslik: 'Güncelleme indirilemedi',
        metin: hata ?? 'Kurulum dosyası bulunamadı.',
      );
    }
    return;
  }

  // Sekmeler ve kodlar KAYDEDİLMEDEN uygulama kapatılmaz.
  ilerleme.value = null;
  metin.value = 'Dosyalarınız kaydediliyor...';
  if (kaydet != null) {
    bool kaydedildi;
    try {
      kaydedildi = await kaydet();
    } catch (_) {
      kaydedildi = false;
    }
    if (!kaydedildi) {
      kapat();
      if (context.mounted) {
        await _bilgiPaneli(
          context,
          ikon: Icons.error_outline,
          ikonRenk: Colors.orange,
          baslik: 'Güncelleme iptal edildi',
          metin: 'Açık dosyalarınız kaydedilemedi. Dosyaları kaydedip '
              'güncellemeyi tekrar deneyin.',
        );
      }
      return;
    }
  }

  metin.value = 'Güncelleme başlatılıyor...';
  try {
    await _kurulumuBaslat(yol);
  } catch (e) {
    kapat();
    if (context.mounted) {
      await _bilgiPaneli(
        context,
        ikon: Icons.error_outline,
        ikonRenk: Colors.orange,
        baslik: 'Güncelleme başlatılamadı',
        metin: _hataMetni(e),
      );
    }
    return;
  }

  // Kurulum ayrı süreçte sürüyor; uygulama kapanır.
  exit(0);
}

/// Kurulumu sessiz modda başlatır ve "TürKod Güncelleniyor..." penceresini açar.
/// Kurulumu bu (Flutter) süreç başlatır: backend'in alt süreci olsaydı, uygulama
/// kapanırken onunla birlikte sonlandırılırdı.
Future<void> _kurulumuBaslat(String kurulumYolu) async {
  final kurulum = await Process.start(
    kurulumYolu,
    const ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS'],
    mode: ProcessStartMode.detached,
  );

  // Pencere açılamazsa (örn. PowerShell kısıtlıysa) güncelleme yine de sürer.
  try {
    final betik = File(
        '${Directory.systemTemp.path}${Platform.pathSeparator}turkod_guncelleme_arayuz.ps1');
    // UTF-8 BOM: Windows PowerShell 5.1 Türkçe karakterleri doğru okusun.
    await betik.writeAsBytes([0xEF, 0xBB, 0xBF, ...utf8.encode(_arayuzBetigi)]);
    final sistem = Platform.environment['SystemRoot'] ?? r'C:\Windows';
    await Process.start(
      '$sistem\\System32\\WindowsPowerShell\\v1.0\\powershell.exe',
      [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-WindowStyle',
        'Hidden',
        '-File',
        betik.path,
        '-KurulumPid',
        '${kurulum.pid}',
        '-UygulamaExe',
        Platform.resolvedExecutable,
      ],
      mode: ProcessStartMode.detached,
    );
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Paneller
// ---------------------------------------------------------------------------
Widget _panel(
  BuildContext ctx, {
  required IconData ikon,
  required Color ikonRenk,
  required String baslik,
  String altMetin = '',
  String notlar = '',
  String ipucu = '',
  required List<Widget> butonlar,
}) {
  final tema = Theme.of(ctx);
  final soluk = tema.colorScheme.onSurface.withValues(alpha: 0.7);
  return Dialog(
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(ikon, size: 42, color: ikonRenk),
            const SizedBox(height: 12),
            Text(
              baslik,
              textAlign: TextAlign.center,
              style: tema.textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            if (altMetin.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(altMetin,
                  textAlign: TextAlign.center, style: tema.textTheme.bodyMedium),
            ],
            if (notlar.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 140),
                child: SingleChildScrollView(
                  child: Text(notlar.trim(),
                      textAlign: TextAlign.center,
                      style: tema.textTheme.bodySmall),
                ),
              ),
            ],
            if (ipucu.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(ipucu,
                  textAlign: TextAlign.center,
                  style: tema.textTheme.bodySmall?.copyWith(color: soluk)),
            ],
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: butonlar,
            ),
          ],
        ),
      ),
    ),
  );
}

Future<bool> _yeniSurumPaneli(
    BuildContext context, String mevcut, String yeni, String notlar) async {
  final r = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => _panel(
      ctx,
      ikon: Icons.system_update_alt,
      ikonRenk: Theme.of(ctx).colorScheme.primary,
      baslik: 'Yeni sürüm yayınlandı',
      altMetin: mevcut.isEmpty
          ? 'TürKod $yeni'
          : 'TürKod $yeni  (kurulu sürüm: $mevcut)',
      notlar: notlar,
      ipucu:
          'Sonrasında da "Güncelleştirmeler" panelinden güncelleyebilirsiniz.',
      butonlar: [
        FilledButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Yükle'),
        ),
        const SizedBox(width: 12),
        OutlinedButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Atla'),
        ),
      ],
    ),
  );
  return r == true;
}

Future<void> _bilgiPaneli(
  BuildContext context, {
  required IconData ikon,
  required Color ikonRenk,
  required String baslik,
  String metin = '',
}) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => _panel(
      ctx,
      ikon: ikon,
      ikonRenk: ikonRenk,
      baslik: baslik,
      altMetin: metin,
      butonlar: [
        FilledButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Tamam'),
        ),
      ],
    ),
  );
}

class _IlerlemePaneli extends StatelessWidget {
  final ValueNotifier<double?> ilerleme;
  final ValueNotifier<String> metin;
  const _IlerlemePaneli({required this.ilerleme, required this.metin});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return PopScope(
      canPop: false,
      child: Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 380),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ValueListenableBuilder<String>(
                  valueListenable: metin,
                  builder: (_, t, __) => Text(
                    t,
                    textAlign: TextAlign.center,
                    style: tema.textTheme.titleMedium,
                  ),
                ),
                const SizedBox(height: 18),
                ValueListenableBuilder<double?>(
                  valueListenable: ilerleme,
                  builder: (_, v, __) => ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: v,
                      minHeight: 10,
                      color: _yesil,
                      backgroundColor:
                          tema.colorScheme.onSurface.withValues(alpha: 0.12),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// "TürKod Güncelleniyor..." penceresi (uygulama kapandıktan sonra görünür).
// Windows PowerShell + WinForms: ek kurulum gerektirmez.
// ---------------------------------------------------------------------------
const String _arayuzBetigi = r'''
param(
    [Parameter(Mandatory = $true)][int]$KurulumPid,
    [string]$UygulamaExe = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$yesil = [System.Drawing.Color]::FromArgb(46, 204, 113)
$iz = [System.Drawing.Color]::FromArgb(226, 232, 240)

$form = New-Object System.Windows.Forms.Form
$form.Text = "TürKod"
$form.ClientSize = New-Object System.Drawing.Size(380, 112)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.ControlBox = $false
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::White

$etiket = New-Object System.Windows.Forms.Label
$etiket.Text = "TürKod Güncelleniyor..."
$etiket.Font = New-Object System.Drawing.Font("Segoe UI", 13)
$etiket.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$etiket.SetBounds(10, 16, 360, 34)
$form.Controls.Add($etiket)

$kutu = New-Object System.Windows.Forms.Panel
$kutu.SetBounds(24, 66, 332, 14)
$kutu.BackColor = $iz
$form.Controls.Add($kutu)

$dolgu = New-Object System.Windows.Forms.Panel
$dolgu.SetBounds(0, 0, 0, 14)
$dolgu.BackColor = $yesil
$kutu.Controls.Add($dolgu)

$script:surec = $null
try {
    $script:surec = [System.Diagnostics.Process]::GetProcessById($KurulumPid)
    $null = $script:surec.Handle
} catch {
    $script:surec = $null
}
$script:baslangic = Get-Date
$script:yuzde = 0.0
$script:bitti = $false
$script:bitisZamani = Get-Date
$script:kod = 0

$zaman = New-Object System.Windows.Forms.Timer
$zaman.Interval = 50
$zaman.Add_Tick({
    $gecen = ((Get-Date) - $script:baslangic).TotalSeconds
    if (-not $script:bitti) {
        $bitmis = $true
        if ($script:surec -ne $null) {
            try { $bitmis = $script:surec.HasExited } catch { $bitmis = $true }
        }
        if ($gecen -gt 900) { $bitmis = $true }
        if ($bitmis) {
            $script:bitti = $true
            $script:bitisZamani = Get-Date
            try { $script:kod = $script:surec.ExitCode } catch { $script:kod = 0 }
        }
    }
    if ($script:bitti) {
        $hedef = 100.0
    } else {
        $hedef = 93.0 * (1.0 - [Math]::Exp(-$gecen / 15.0))
    }
    $script:yuzde = $script:yuzde + ($hedef - $script:yuzde) * 0.12
    $dolgu.Width = [int][Math]::Round($kutu.Width * $script:yuzde / 100.0)
    if ($script:bitti -and (((Get-Date) - $script:bitisZamani).TotalSeconds -gt 1.2)) {
        $zaman.Stop()
        $form.Close()
    }
})
$zaman.Start()

[void]$form.ShowDialog()

if ($script:kod -ne 0) {
    [void][System.Windows.Forms.MessageBox]::Show(
        "Güncelleme tamamlanamadı (hata kodu $($script:kod)).`nTürKod önceki sürümle yeniden açılıyor.",
        "TürKod",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning)
    if ($UygulamaExe -and (Test-Path $UygulamaExe)) {
        Start-Process -FilePath $UygulamaExe
    }
}
''';
