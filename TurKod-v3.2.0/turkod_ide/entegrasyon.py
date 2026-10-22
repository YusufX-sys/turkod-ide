"""Windows sistem entegrasyonu: PATH'teki `turkod` komutu ve .trpy dosya ilişkilendirmesi.

Kurulum sihirbazındaki iki seçeneğin (turkod.iss [Tasks] "path" / "iliskilendir")
uygulama içinden açılıp kapatılabilen karşılığı. Sürüm güncellemesiyle gelen
cihazlarda bu görevler hiç seçilmemiş olabiliyordu; Ayarlar sayfası buradan düzeltir.

Yönetici izni istemez: her şey kullanıcı kayıt defterine (HKCU) yazılır. HKCU\\Software
\\Classes, HKLM'dekinin önüne geçer; kullanıcı PATH'i sistem PATH'ine eklenir.
Yönetici kurulumunun HKLM'ye yazdığı girdiler buradan silinemez (durumda bildirilir).
Kayıtların biçimi turkod.iss [Registry] / [Code] PATH bölümüyle aynıdır.
"""
import os
import sys

try:
    import winreg
except ImportError:  # Windows dışı (geliştirme)
    winreg = None

_ORTAM_ANAHTARI = "Environment"
_SISTEM_ORTAM_ANAHTARI = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
_SINIFLAR = r"Software\Classes"
_PROGID = "TurKod.Program"


def _paketli_mi():
    return bool(getattr(sys, "frozen", False))


def _yollar():
    """Kurulum klasöründeki dosyalar. Yalnızca paketli (kurulmuş) uygulamada anlamlı."""
    backend = os.path.dirname(os.path.abspath(sys.executable))
    uygulama = os.path.dirname(backend)
    ic = getattr(sys, "_MEIPASS", os.path.join(backend, "_internal"))
    return {
        "backend_dizini": backend,
        "editor_exe": os.path.join(uygulama, "turkod_flutter.exe"),
        "backend_exe": os.path.join(backend, "turkod_backend.exe"),
        "ikon": os.path.join(ic, "editor-logo.ico"),
    }


def _ayni_yol(a, b):
    return os.path.normcase(a.strip().rstrip("\\/")) == os.path.normcase(b.strip().rstrip("\\/"))


# --------------------------------------------------------------------------
# PATH
# --------------------------------------------------------------------------
def _path_oku(kok, anahtar):
    """(değer, tür) döndürür; değer yoksa ("", REG_EXPAND_SZ)."""
    try:
        with winreg.OpenKey(kok, anahtar, 0, winreg.KEY_READ) as k:
            deger, tur = winreg.QueryValueEx(k, "Path")
    except FileNotFoundError:
        return "", winreg.REG_EXPAND_SZ
    if tur not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(deger, str):
        raise RuntimeError("PATH değeri beklenmeyen türde; değiştirilmedi.")
    return deger, tur


def _path_iceriyor(deger, dizin):
    return any(_ayni_yol(p, dizin) for p in deger.split(";") if p.strip())


def _ortam_degisti_bildir():
    """Yeni açılan terminallerin güncel PATH'i görmesi için WM_SETTINGCHANGE yayını."""
    try:
        import ctypes
        from ctypes import wintypes
        sonuc = wintypes.DWORD()
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, ctypes.byref(sonuc))
    except Exception:
        pass


def _path_ayarla(ekle):
    dizin = _yollar()["backend_dizini"]
    eski, tur = _path_oku(winreg.HKEY_CURRENT_USER, _ORTAM_ANAHTARI)
    parcalar = [p for p in eski.split(";") if p.strip() and not _ayni_yol(p, dizin)]
    if ekle:
        parcalar.append(dizin)
    yeni = ";".join(parcalar)
    if yeni == eski:
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _ORTAM_ANAHTARI, 0,
                            winreg.KEY_SET_VALUE) as k:
        if yeni:
            winreg.SetValueEx(k, "Path", 0, tur, yeni)
        else:
            try:
                winreg.DeleteValue(k, "Path")
            except FileNotFoundError:
                pass
    _ortam_degisti_bildir()


# --------------------------------------------------------------------------
# .trpy ilişkilendirme
# --------------------------------------------------------------------------
def _deger_oku(kok, anahtar, ad=""):
    try:
        with winreg.OpenKey(kok, anahtar, 0, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, ad)[0]
    except OSError:
        return None


def _yaz(anahtar, ad, deger):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _SINIFLAR + "\\" + anahtar, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, ad, 0, winreg.REG_SZ, deger)


def _agac_sil(kok, anahtar):
    """Anahtarı alt anahtarlarıyla siler (yoksa sessizce geçer)."""
    try:
        with winreg.OpenKey(kok, anahtar, 0, winreg.KEY_READ) as k:
            altlar = []
            i = 0
            while True:
                try:
                    altlar.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
        for alt in altlar:
            _agac_sil(kok, anahtar + "\\" + alt)
        winreg.DeleteKey(kok, anahtar)
    except FileNotFoundError:
        pass


def _bossa_sil(kok, anahtar):
    try:
        winreg.DeleteKey(kok, anahtar)   # alt anahtarı varsa OSError: dokunma
    except OSError:
        pass


def _iliski_etkin_mi(kok, on_ek):
    """kok\\on_ek altında .trpy -> TurKod.Program ve çalıştırma komutu kayıtlı mı?"""
    if _deger_oku(kok, on_ek + ".trpy") != _PROGID:
        return False
    komut = _deger_oku(kok, on_ek + _PROGID + r"\shell\open\command")
    return bool(komut) and "turkod_backend.exe" in komut.lower()


def _dosya_turu_bildir():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass


def _iliskilendir(ac):
    y = _yollar()
    hk = winreg.HKEY_CURRENT_USER
    if ac:
        ikon = y["ikon"] + ",0"
        _yaz(".trpy", "", _PROGID)
        _yaz(".trpy", "Content Type", "text/plain")
        _yaz(".trpy", "PerceivedType", "text")
        _yaz(r".trpy\OpenWithProgids", _PROGID, "")
        _yaz(_PROGID, "", "TürKod Programı")
        _yaz(_PROGID + r"\DefaultIcon", "", ikon)
        _yaz(_PROGID + r"\shell", "", "open")
        _yaz(_PROGID + r"\shell\open", "", "TürKod ile çalıştır")
        _yaz(_PROGID + r"\shell\open", "Icon", ikon)
        _yaz(_PROGID + r"\shell\open\command", "", f'"{y["backend_exe"]}" --terminal "%1"')
        _yaz(r"Applications\turkod_flutter.exe", "FriendlyAppName", "TürKod Editör")
        _yaz(r"Applications\turkod_flutter.exe\SupportedTypes", ".trpy", "")
        _yaz(r"Applications\turkod_flutter.exe\shell\open\command", "",
             f'"{y["editor_exe"]}" "%1"')
        _yaz(r"SystemFileAssociations\.trpy\shell\TurKod.Editor", "", "Editör ile aç")
        _yaz(r"SystemFileAssociations\.trpy\shell\TurKod.Editor", "Icon",
             y["editor_exe"] + ",0")
        _yaz(r"SystemFileAssociations\.trpy\shell\TurKod.Editor\command", "",
             f'"{y["editor_exe"]}" "%1"')
    else:
        s = _SINIFLAR + "\\"
        if _deger_oku(hk, s + ".trpy") == _PROGID:
            with winreg.OpenKey(hk, s + ".trpy", 0, winreg.KEY_SET_VALUE) as k:
                for ad in ("", "Content Type", "PerceivedType"):
                    try:
                        winreg.DeleteValue(k, ad)
                    except FileNotFoundError:
                        pass
        try:
            with winreg.OpenKey(hk, s + r".trpy\OpenWithProgids", 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, _PROGID)
        except FileNotFoundError:
            pass
        _bossa_sil(hk, s + r".trpy\OpenWithProgids")
        _agac_sil(hk, s + _PROGID)
        _agac_sil(hk, s + r"Applications\turkod_flutter.exe")
        _agac_sil(hk, s + r"SystemFileAssociations\.trpy\shell\TurKod.Editor")
        _bossa_sil(hk, s + r"SystemFileAssociations\.trpy\shell")
        _bossa_sil(hk, s + r"SystemFileAssociations\.trpy")
        # Değeri kalmamış boş .trpy anahtarı da gitsin.
        try:
            with winreg.OpenKey(hk, s + ".trpy", 0, winreg.KEY_READ) as k:
                bos = winreg.QueryInfoKey(k)[1] == 0
            if bos:
                _bossa_sil(hk, s + ".trpy")
        except FileNotFoundError:
            pass
    _dosya_turu_bildir()


# --------------------------------------------------------------------------
# Dış arayüz (server.py komutları)
# --------------------------------------------------------------------------
def durum():
    if winreg is None or not _paketli_mi():
        return {
            "destekleniyor": False,
            "neden": "Bu ayarlar yalnızca kurulmuş TürKod'da (Windows) kullanılabilir.",
        }
    y = _yollar()
    dizin = y["backend_dizini"]
    try:
        kullanici_path = _path_iceriyor(_path_oku(winreg.HKEY_CURRENT_USER, _ORTAM_ANAHTARI)[0], dizin)
    except Exception:
        kullanici_path = False
    try:
        sistem_path = _path_iceriyor(
            _path_oku(winreg.HKEY_LOCAL_MACHINE, _SISTEM_ORTAM_ANAHTARI)[0], dizin)
    except Exception:
        sistem_path = False
    kullanici_iliski = _iliski_etkin_mi(winreg.HKEY_CURRENT_USER, _SINIFLAR + "\\")
    sistem_iliski = _iliski_etkin_mi(winreg.HKEY_LOCAL_MACHINE, _SINIFLAR + "\\")
    return {
        "destekleniyor": True,
        "path": kullanici_path or sistem_path,
        "path_sistemde": sistem_path,
        "iliskilendir": _iliski_etkin_mi(winreg.HKEY_CLASSES_ROOT, ""),
        "iliski_kullanicida": kullanici_iliski,
        "iliski_sistemde": sistem_iliski,
        "path_dizini": dizin,
    }


def ayarla(path=None, iliskilendir=None):
    """Verilen seçenekleri uygular ve güncel durumu döndürür."""
    d = durum()
    if not d.get("destekleniyor"):
        raise RuntimeError(d.get("neden", "Desteklenmiyor"))
    if path is not None:
        _path_ayarla(bool(path))
    if iliskilendir is not None:
        _iliskilendir(bool(iliskilendir))
    return durum()
