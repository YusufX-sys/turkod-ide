# TürKod'un webview_windows kopyası

Bu klasör, [webview_windows 0.4.0](https://github.com/jnschulze/flutter-webview-windows)
paketinin (BSD-3-Clause, bkz. `LICENSE`) TürKod için değiştirilmiş kopyasıdır.
`pubspec.yaml` içinde `path:` ile kullanılır; pub.dev'deki sürüm yerine bu derlenir.

## 1. Pencereli kip (asıl değişiklik)

Özgün paket sayfayı görünmez bir pencerede çizip her kareyi yakalayarak Flutter'a
doku (texture) olarak kopyalar; fare ve tekerlek olaylarını da tek tek elle iletir.
Bunun sonuçları: ekran kartı sürekli kopyalama yapar, tekerlek imlecin altındaki
panele değil sayfanın sol üstüne gider (açık menüler kapanır), kaydırma çubuğu ve
sürükleme sorunlu olur.

TürKod artık VS Code'un tümleşik tarayıcısı (Electron WebContentsView) gibi
çalışır: WebView2 kendi penceresiyle (`CreateCoreWebView2Controller`), TürKod
penceresindeki bir taşıyıcı alt pencerede çizilir. Girdi doğrudan Chromium'a gider.

- `initialize({windowed: true})` → `WebviewWindowsPlugin::CreateWindowedInstance`:
  Flutter görünümünün alt penceresi olarak `TurKodWebviewTasiyici` sınıfından bir
  taşıyıcı açılır, denetleyici onun içine kurulur. Köprü dokusuz kurulur
  (`WebviewBridge(messenger, webview, id)`; kimlik 2^40'tan başlar).
- Yeni yöntemler (Dart: `setWindowBounds`, `setWindowVisible`, `setClipRects`,
  `capturePreview`):
  - `setWindowBounds`: taşıyıcının yeri ve boyu (Flutter görünümüne göre fiziksel piksel).
  - `setWindowVisible`: göster / gizle (başka sekme, menü açıkken).
  - `setClipRects`: taşıyıcıdan kesilen yuvarlak köşeli dikdörtgenler; Kodi ve
    balonu sayfanın üstünde görünsün diye (`SetWindowRgn`).
  - `capturePreview`: sayfanın PNG görüntüsü; menü ya da iletişim kutusu açıkken
    gerçek sayfa gizlenir, yerine bu görüntü konur.
- Kısayollar: sayfa odaktayken Ctrl/Alt'lı tuşlar ve F tuşları (F5 dışında)
  `AcceleratorKeyPressed` ile yakalanır, odak Flutter'a verilip tuş ona iletilir.
  Metin düzenleme tuşları (Ctrl+A/C/V/X/Z/Y, oklar, Home/End ...), Ctrl+R,
  yakınlaştırma ve Alt+Sol/Sağ sayfada kalır.
- Dokulu kipte kullanılan yerler (`texture_bridge_`, `composition_controller_`)
  pencereli kipte boş olabileceği için koşula bağlandı.

Dart tarafındaki kullanım: `turkod_flutter/lib/tarayici.dart` (`TarayiciDurumu`,
`_SayfaYeri`, `TarayiciOrtuGozlemcisi`), Kodi kesikleri: `lib/kodi.dart`
(`_tarayiciyaBildir`).

## 2. Fare tekerleği (dokulu kip)

`lib/src/webview.dart`: `_tekerlek`, `_kTekerlekBetigi`. Dokulu kipte tekerlek bir
sayfa betiğiyle imlecin altındaki öğeye verilir (yerel yolla konumlu tekerlek
olayları sayfaya ulaşmıyordu). TürKod artık pencereli kipi kullandığı için bu yol
yalnızca dokulu kipte işe yarar.

## 3. Diğer

- `windows/CMakeLists.txt`: `add_custom_command(TARGET ...)` içindeki geçersiz
  `DEPENDS` satırı kaldırıldı (her derlemede çıkan CMP0175 uyarısı).

Paket güncellenirse bu değişiklikler yeni sürüme yeniden uygulanmalıdır.
