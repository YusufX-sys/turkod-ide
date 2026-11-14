#include "flutter_window.h"

#include <flutter/standard_method_codec.h>

#include <dwmapi.h>

#include <optional>

#include "flutter/generated_plugin_registrant.h"
#include "utils.h"

FlutterWindow::FlutterWindow(const flutter::DartProject& project, bool kodi_kipi,
                             bool kodi_gizli)
    : project_(project), kodi_kipi_(kodi_kipi), kodi_gizli_(kodi_gizli) {}

namespace {

BOOL CALLBACK AnaPencereyiBul(HWND hwnd, LPARAM lparam) {
  if (::GetPropW(hwnd, kTurKodPencereOzelligi)) {
    *reinterpret_cast<HWND*>(lparam) = hwnd;
    return FALSE;
  }
  return TRUE;
}

HWND AnaPencere() {
  HWND hedef = nullptr;
  ::EnumWindows(AnaPencereyiBul, reinterpret_cast<LPARAM>(&hedef));
  return hedef;
}

// Pencerenin saydam olmayan alanı yalnızca Flutter'ın çizdiği yerdir:
// DWM çerçeveyi bütün pencereye yayar, zemin saydam kalır.
void SaydamYap(HWND hwnd) {
  MARGINS kenar = {-1, -1, -1, -1};
  ::DwmExtendFrameIntoClientArea(hwnd, &kenar);
  struct AccentPolicy {
    int durum;
    int bayrak;
    unsigned int renk;
    int animasyon;
  };
  struct CompositionData {
    int ozellik;
    void* veri;
    SIZE_T boyut;
  };
  using SetWca = BOOL(WINAPI*)(HWND, CompositionData*);
  if (auto user32 = ::GetModuleHandleW(L"user32.dll")) {
    if (auto islev = reinterpret_cast<SetWca>(
            ::GetProcAddress(user32, "SetWindowCompositionAttribute"))) {
      AccentPolicy politika = {2 /* TRANSPARENTGRADIENT */, 2, 0x00000000, 0};
      CompositionData veri = {19 /* WCA_ACCENT_POLICY */, &politika, sizeof(politika)};
      islev(hwnd, &veri);
    }
  }
}

}  // namespace

void FlutterWindow::KodiPenceresiniHazirla(int x, int y) {
  HWND hwnd = GetHandle();
  ::SetWindowLongPtrW(hwnd, GWL_STYLE, WS_POPUP | WS_CLIPCHILDREN);
  ::SetWindowLongPtrW(hwnd, GWL_EXSTYLE, WS_EX_TOPMOST | WS_EX_TOOLWINDOW);
  SaydamYap(hwnd);
  const UINT dpi = ::GetDpiForWindow(hwnd);
  const double olcek = dpi / 96.0;
  int genislik = static_cast<int>(440 * olcek);
  int yukseklik = static_cast<int>(760 * olcek);
  // Robot sağ altta durur: fare robotun ortasına gelsin.
  int sol = x - genislik + static_cast<int>(64 * olcek);
  int ust = y - yukseklik + static_cast<int>(70 * olcek);
  HMONITOR ekran = ::MonitorFromPoint(POINT{x, y}, MONITOR_DEFAULTTONEAREST);
  MONITORINFO bilgi{};
  bilgi.cbSize = sizeof(bilgi);
  if (::GetMonitorInfoW(ekran, &bilgi)) {
    const RECT& alan = bilgi.rcWork;
    if (yukseklik > alan.bottom - alan.top) yukseklik = alan.bottom - alan.top;
    if (sol < alan.left) sol = alan.left;
    if (ust < alan.top) ust = alan.top;
    if (sol + genislik > alan.right) sol = alan.right - genislik;
    if (ust + yukseklik > alan.bottom) ust = alan.bottom - yukseklik;
  }
  ::SetWindowPos(hwnd, HWND_TOPMOST, sol, ust, genislik, yukseklik,
                 SWP_FRAMECHANGED | SWP_NOACTIVATE);
}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  // Tek editör örneği: Dart, oturumu yükledikten sonra "hazir" çağırır ve o
  // ana kadar biriken dosyaları alır; sonrakiler "dosyalariAc" ile iletilir.
  tek_ornek_kanali_ =
      std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
          flutter_controller_->engine()->messenger(), "turkod/tek_ornek",
          &flutter::StandardMethodCodec::GetInstance());
  tek_ornek_kanali_->SetMethodCallHandler(
      [this](const flutter::MethodCall<flutter::EncodableValue>& call,
             std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>>
                 result) {
        if (call.method_name() == "hazir") {
          flutter::EncodableList liste;
          for (const auto& d : bekleyen_dosyalar_) {
            liste.push_back(flutter::EncodableValue(d));
          }
          bekleyen_dosyalar_.clear();
          dart_hazir_ = true;
          result->Success(flutter::EncodableValue(liste));
        } else {
          result->NotImplemented();
        }
      });
  if (!kodi_kipi_) {
    ::SetPropW(GetHandle(), kTurKodPencereOzelligi, reinterpret_cast<HANDLE>(1));
  } else {
    // Kodi penceresi: sürükleme (Windows'un kendi pencere taşıma döngüsü),
    // tıklamaların geçtiği alan, TürKod'u öne getirme.
    kodi_kanali_ =
        std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
            flutter_controller_->engine()->messenger(), "turkod/kodi_penceresi",
            &flutter::StandardMethodCodec::GetInstance());
    kodi_kanali_->SetMethodCallHandler(
        [this](const flutter::MethodCall<flutter::EncodableValue>& call,
               std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>>
                   result) {
          HWND hwnd = GetHandle();
          const std::string& ad = call.method_name();
          if (ad == "surukle") {
            ::ReleaseCapture();
            ::SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0);
            // Taşıma bitti: fare TürKod'un üstünde mi bırakıldı?
            POINT fare;
            ::GetCursorPos(&fare);
            bool ustunde = false;
            if (HWND ana = AnaPencere()) {
              RECT r;
              ::GetWindowRect(ana, &r);
              ustunde = !::IsIconic(ana) && ::PtInRect(&r, fare);
            }
            result->Success(flutter::EncodableValue(ustunde));
          } else if (ad == "anaPencereyiOneGetir") {
            if (HWND ana = AnaPencere()) {
              if (::IsIconic(ana)) ::ShowWindow(ana, SW_RESTORE);
              ::SetForegroundWindow(ana);
            }
            result->Success();
          } else if (ad == "bolge") {
            // Yalnızca robot ve balonun alanı tıklanabilir; geri kalanında
            // tıklamalar alttaki pencerelere geçer. [x, y, g, y, yarıçap]...
            const auto* liste = std::get_if<flutter::EncodableList>(call.arguments());
            const double olcek = ::GetDpiForWindow(hwnd) / 96.0;
            HRGN bolge = ::CreateRectRgn(0, 0, 0, 0);
            if (liste) {
              for (const auto& o : *liste) {
                const auto* d = std::get_if<flutter::EncodableList>(&o);
                if (!d || d->size() < 5) continue;
                auto sayi = [&](size_t i) {
                  const auto& v = (*d)[i];
                  if (auto p = std::get_if<double>(&v)) return *p;
                  if (auto p = std::get_if<int32_t>(&v)) return static_cast<double>(*p);
                  return 0.0;
                };
                const int x = static_cast<int>(sayi(0) * olcek);
                const int y = static_cast<int>(sayi(1) * olcek);
                const int g = static_cast<int>(sayi(2) * olcek);
                const int h = static_cast<int>(sayi(3) * olcek);
                const int r = static_cast<int>(sayi(4) * olcek);
                HRGN parca = r > 0 ? ::CreateRoundRectRgn(x, y, x + g + 1, y + h + 1, r * 2, r * 2)
                                   : ::CreateRectRgn(x, y, x + g, y + h);
                ::CombineRgn(bolge, bolge, parca, RGN_OR);
                ::DeleteObject(parca);
              }
            }
            ::SetWindowRgn(hwnd, bolge, TRUE);  // sistem sahiplenir
            result->Success();
          } else if (ad == "kapat") {
            ::PostMessageW(hwnd, WM_CLOSE, 0, 0);
            result->Success();
          } else if (ad == "goster") {
            // Önceden hazırlanmış (gizli) pencere: fare neredeyse orada,
            // odağı çalmadan, hep üstte görünür. [x, y] fiziksel piksel.
            int x = 0, y = 0;
            bool konum_var = false;
            if (const auto* liste = std::get_if<flutter::EncodableList>(call.arguments())) {
              if (liste->size() >= 2) {
                const auto* px = std::get_if<int32_t>(&(*liste)[0]);
                const auto* py = std::get_if<int32_t>(&(*liste)[1]);
                if (px && py) {
                  x = *px;
                  y = *py;
                  konum_var = true;
                }
              }
            }
            if (!konum_var) {
              POINT fare;
              ::GetCursorPos(&fare);
              x = fare.x;
              y = fare.y;
            }
            kodi_gizli_ = false;
            KodiPenceresiniHazirla(x, y);
            ::ShowWindow(hwnd, SW_SHOWNOACTIVATE);
            ::SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
            result->Success();
          } else if (ad == "gizle") {
            // TürKod'a dönünce pencere kapanmaz, gizlenip bir sonraki sefere
            // hazır bekler.
            ::ShowWindow(hwnd, SW_HIDE);
            result->Success();
          } else {
            result->NotImplemented();
          }
        });
  }

  flutter_controller_->engine()->SetNextFrameCallback([this]() {
    // Önceden hazırlanan Kodi penceresi gizli kalır ("goster" bekler).
    if (!kodi_gizli_) this->Show();
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  if (GetHandle()) {
    ::RemovePropW(GetHandle(), kTurKodPencereOzelligi);
  }
  tek_ornek_kanali_ = nullptr;
  kodi_kanali_ = nullptr;
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

void FlutterWindow::DosyalariAc(std::vector<std::string> dosyalar) {
  if (dosyalar.empty()) {
    return;
  }
  if (!dart_hazir_ || !tek_ornek_kanali_) {
    bekleyen_dosyalar_.insert(bekleyen_dosyalar_.end(), dosyalar.begin(),
                              dosyalar.end());
    return;
  }
  flutter::EncodableList liste;
  for (const auto& d : dosyalar) {
    liste.push_back(flutter::EncodableValue(d));
  }
  tek_ornek_kanali_->InvokeMethod(
      "dosyalariAc", std::make_unique<flutter::EncodableValue>(liste));
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  // İkinci örnekten gelen dosyalar: "yol1\0yol2\0" (UTF-16).
  if (message == WM_COPYDATA) {
    const auto* veri = reinterpret_cast<const COPYDATASTRUCT*>(lparam);
    if (veri && veri->dwData == kTurKodDosyaAcKimligi && veri->lpData) {
      const wchar_t* p = static_cast<const wchar_t*>(veri->lpData);
      const size_t uzunluk = veri->cbData / sizeof(wchar_t);
      std::vector<std::string> dosyalar;
      std::wstring parca;
      for (size_t i = 0; i < uzunluk; ++i) {
        if (p[i] == L'\0') {
          if (!parca.empty()) {
            dosyalar.push_back(Utf8FromUtf16(parca.c_str()));
          }
          parca.clear();
        } else {
          parca.push_back(p[i]);
        }
      }
      if (!parca.empty()) {
        dosyalar.push_back(Utf8FromUtf16(parca.c_str()));
      }
      DosyalariAc(std::move(dosyalar));
      return TRUE;
    }
  }

  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
