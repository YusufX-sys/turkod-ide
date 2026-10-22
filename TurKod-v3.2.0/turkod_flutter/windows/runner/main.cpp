#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>
#include <shellapi.h>

#include <string>
#include <vector>

#include "flutter_window.h"
#include "utils.h"

namespace {

// Komut satırındaki dosya yolları (seçenekler hariç), tam yol olarak.
std::vector<std::wstring> DosyaArgumanlari() {
  std::vector<std::wstring> dosyalar;
  int argc = 0;
  wchar_t** argv = ::CommandLineToArgvW(::GetCommandLineW(), &argc);
  if (!argv) {
    return dosyalar;
  }
  for (int i = 1; i < argc; ++i) {
    std::wstring arg = argv[i];
    if (arg.empty() || arg.rfind(L"--", 0) == 0) {
      continue;
    }
    wchar_t tam[MAX_PATH * 4];
    DWORD n = ::GetFullPathNameW(arg.c_str(), MAX_PATH * 4, tam, nullptr);
    std::wstring yol = (n > 0 && n < MAX_PATH * 4) ? std::wstring(tam, n) : arg;
    DWORD oz = ::GetFileAttributesW(yol.c_str());
    if (oz != INVALID_FILE_ATTRIBUTES && !(oz & FILE_ATTRIBUTE_DIRECTORY)) {
      dosyalar.push_back(yol);
    }
  }
  ::LocalFree(argv);
  return dosyalar;
}

BOOL CALLBACK EditorPenceresiBul(HWND hwnd, LPARAM lparam) {
  if (::GetPropW(hwnd, kTurKodPencereOzelligi)) {
    *reinterpret_cast<HWND*>(lparam) = hwnd;
    return FALSE;
  }
  return TRUE;
}

// Açık bir TürKod editörü varsa dosyaları ona gönderir. Editör yeni açılıyorsa
// penceresinin oluşmasını kısa bir süre bekler. Gönderildiyse true.
bool AcikEditoreGonder(const std::vector<std::wstring>& dosyalar) {
  HWND hedef = nullptr;
  for (int deneme = 0; deneme < 60 && !hedef; ++deneme) {  // ~15 sn
    ::EnumWindows(EditorPenceresiBul, reinterpret_cast<LPARAM>(&hedef));
    if (!hedef) {
      ::Sleep(250);
    }
  }
  if (!hedef) {
    return false;
  }
  std::wstring veri;
  for (const auto& d : dosyalar) {
    veri += d;
    veri.push_back(L'\0');
  }
  COPYDATASTRUCT cds{};
  cds.dwData = kTurKodDosyaAcKimligi;
  cds.cbData = static_cast<DWORD>(veri.size() * sizeof(wchar_t));
  cds.lpData = veri.data();
  DWORD_PTR sonuc = 0;
  if (!::SendMessageTimeoutW(hedef, WM_COPYDATA, 0, reinterpret_cast<LPARAM>(&cds),
                             SMTO_ABORTIFHUNG, 5000, &sonuc) || sonuc != TRUE) {
    return false;
  }
  // Gezgin'den başlatılan bu süreç ön plana getirme hakkına sahiptir.
  if (::IsIconic(hedef)) {
    ::ShowWindow(hedef, SW_RESTORE);
  }
  ::SetForegroundWindow(hedef);
  return true;
}

}  // namespace

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  // Tek editör örneği: "Editör ile aç" ya da `turkod --editor dosya` açık bir
  // editör varken yeni pencere açmaz, dosyayı o editörde yeni sekmede açar.
  // Mutex tutamağı süreç boyunca açık kalır (kapanınca sistem bırakır).
  ::CreateMutexW(nullptr, FALSE, L"Local\\TurKod.Editor.TekOrnek");
  const bool baska_ornek_var = ::GetLastError() == ERROR_ALREADY_EXISTS;
  if (baska_ornek_var) {
    const std::vector<std::wstring> dosyalar = DosyaArgumanlari();
    if (!dosyalar.empty() && AcikEditoreGonder(dosyalar)) {
      return EXIT_SUCCESS;
    }
  }

  // Attach to console when present (e.g., 'flutter run') or create a
  // new console when running with a debugger.
  if (!::AttachConsole(ATTACH_PARENT_PROCESS) && ::IsDebuggerPresent()) {
    CreateAndAttachConsole();
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  std::vector<std::string> command_line_arguments =
      GetCommandLineArguments();

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));

  FlutterWindow window(project);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(1280, 720);
  if (!window.Create(L"TürKod IDE - Profesyonel Türkçe Programlama Dili", origin, size)) {
    return EXIT_FAILURE;
  }
  window.SetQuitOnClose(true);

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  return EXIT_SUCCESS;
}
