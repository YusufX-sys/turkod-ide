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
HWND AcikEditoruBul() {
  HWND hedef = nullptr;
  for (int deneme = 0; deneme < 60 && !hedef; ++deneme) {  // ~15 sn
    ::EnumWindows(EditorPenceresiBul, reinterpret_cast<LPARAM>(&hedef));
    if (!hedef) {
      ::Sleep(250);
    }
  }
  return hedef;
}

void OneGetir(HWND hedef) {
  // Gezgin'den başlatılan bu süreç ön plana getirme hakkına sahiptir.
  if (::IsIconic(hedef)) {
    ::ShowWindow(hedef, SW_RESTORE);
  }
  ::SetForegroundWindow(hedef);
}

bool AcikEditoreGonder(const std::vector<std::wstring>& dosyalar) {
  HWND hedef = AcikEditoruBul();
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
  OneGetir(hedef);
  return true;
}

// "--ad değer" biçimindeki tam sayı seçeneği.
int SayiSecenegi(const wchar_t* ad, int varsayilan) {
  int argc = 0;
  wchar_t** argv = ::CommandLineToArgvW(::GetCommandLineW(), &argc);
  int sonuc = varsayilan;
  if (argv) {
    for (int i = 1; i + 1 < argc; ++i) {
      if (std::wstring(argv[i]) == ad) {
        sonuc = _wtoi(argv[i + 1]);
      }
    }
    ::LocalFree(argv);
  }
  return sonuc;
}

}  // namespace

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  // Tek editör örneği: "Editör ile aç" ya da `turkod --editor dosya` açık bir
  // editör varken yeni pencere açmaz, dosyayı o editörde yeni sekmede açar.
  // Mutex tutamağı süreç boyunca açık kalır (kapanınca sistem bırakır).
  // Masaüstü Kodi: aynı programın ikinci, küçük, saydam penceresi (TürKod
  // penceresinin dışına sürüklenen Kodi). Tek örnek denetimine girmez.
  const bool kodi_kipi =
      std::wstring(::GetCommandLineW()).find(L"--kodi-penceresi") != std::wstring::npos;
  // Ayrı test profiliyle (TURKOD_TEST_PROFIL) açılan kopya kendi ayar
  // klasörünü kullanır; açık editörü öne getirip kapanmaz.
  const bool test_profili =
      ::GetEnvironmentVariableW(L"TURKOD_TEST_PROFIL", nullptr, 0) > 0;
  if (!kodi_kipi && !test_profili) {
    ::CreateMutexW(nullptr, FALSE, L"Local\\TurKod.Editor.TekOrnek");
  }
  const bool baska_ornek_var =
      !kodi_kipi && !test_profili && ::GetLastError() == ERROR_ALREADY_EXISTS;
  // Dosyasız açılışta da ikinci pencere açılmaz, açık olan öne getirilir:
  // iki pencere ayrı backend'lerle aynı ayar dosyasına "son_oturum" yazıyor,
  // son kapanan kazandığı için adsız sekmelerin içeriği kayboluyordu.
  if (baska_ornek_var) {
    const std::vector<std::wstring> dosyalar = DosyaArgumanlari();
    if (dosyalar.empty()) {
      if (HWND acik = AcikEditoruBul()) {
        OneGetir(acik);
        return EXIT_SUCCESS;
      }
    } else if (AcikEditoreGonder(dosyalar)) {
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

  const bool kodi_gizli =
      kodi_kipi &&
      std::wstring(::GetCommandLineW()).find(L"--kodi-gizli") != std::wstring::npos;
  FlutterWindow window(project, kodi_kipi, kodi_gizli);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(kodi_kipi ? 440 : 1280, kodi_kipi ? 760 : 720);
  if (!window.Create(kodi_kipi ? L"Kodi" : L"TürKod IDE - Profesyonel Türkçe Programlama Dili",
                     origin, size)) {
    return EXIT_FAILURE;
  }
  if (kodi_kipi) {
    window.KodiPenceresiniHazirla(SayiSecenegi(L"--kodi-x", 800),
                                  SayiSecenegi(L"--kodi-y", 600));
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
