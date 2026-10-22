#ifndef RUNNER_FLUTTER_WINDOW_H_
#define RUNNER_FLUTTER_WINDOW_H_

#include <flutter/dart_project.h>
#include <flutter/encodable_value.h>
#include <flutter/flutter_view_controller.h>
#include <flutter/method_channel.h>

#include <memory>
#include <string>
#include <vector>

// Tek editör örneği: ikinci bir turkod_flutter.exe ("Editör ile aç") dosya
// yollarını WM_COPYDATA ile açık pencereye gönderir ve kapanır. Pencere bu
// özellikle (SetProp) tanınır; veri bu kimlikle işaretlenir.
constexpr const wchar_t kTurKodPencereOzelligi[] = L"TurKod.Editor";
constexpr ULONG_PTR kTurKodDosyaAcKimligi = 0x544B4431;  // 'TKD1'

#include "win32_window.h"

// A window that does nothing but host a Flutter view.
class FlutterWindow : public Win32Window {
 public:
  // Creates a new FlutterWindow hosting a Flutter view running |project|.
  explicit FlutterWindow(const flutter::DartProject& project);
  virtual ~FlutterWindow();

 protected:
  // Win32Window:
  bool OnCreate() override;
  void OnDestroy() override;
  LRESULT MessageHandler(HWND window, UINT const message, WPARAM const wparam,
                         LPARAM const lparam) noexcept override;

 private:
  // The project to run.
  flutter::DartProject project_;

  // The Flutter instance hosted by this window.
  std::unique_ptr<flutter::FlutterViewController> flutter_controller_;

  // Dart tarafına dosya açma isteklerini ileten kanal ("turkod/tek_ornek").
  std::unique_ptr<flutter::MethodChannel<flutter::EncodableValue>> tek_ornek_kanali_;
  // Dart hazır olmadan gelen dosyalar burada bekler; Dart "hazir" deyince alır.
  std::vector<std::string> bekleyen_dosyalar_;
  bool dart_hazir_ = false;

  void DosyalariAc(std::vector<std::string> dosyalar);
};

#endif  // RUNNER_FLUTTER_WINDOW_H_
