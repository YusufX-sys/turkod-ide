#include "flutter_window.h"

#include <flutter/standard_method_codec.h>

#include <optional>

#include "flutter/generated_plugin_registrant.h"
#include "utils.h"

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

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
  ::SetPropW(GetHandle(), kTurKodPencereOzelligi, reinterpret_cast<HANDLE>(1));

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
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
