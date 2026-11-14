"""Ayar yonetimi."""
import base64
import json
import os
import shutil
import sys
import tempfile
import threading
import time

_DPAPI_ONEKI = "dpapi:"


def _dpapi(veri, coz):
    """Windows DPAPI: veri yalnızca aynı Windows kullanıcısı tarafından
    çözülebilir. Windows dışında ya da hata olursa None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        tampon = ctypes.create_string_buffer(veri, len(veri))
        giris = _Blob(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
        cikis = _Blob()
        islev = crypt32.CryptUnprotectData if coz else crypt32.CryptProtectData
        # 0x1 = CRYPTPROTECT_UI_FORBIDDEN
        if not islev(ctypes.byref(giris), None, None, None, None, 0x1,
                     ctypes.byref(cikis)):
            return None
        try:
            return ctypes.string_at(cikis.pbData, cikis.cbData)
        finally:
            kernel32.LocalFree(cikis.pbData)
    except Exception:
        return None


def _sifrele(deger):
    if isinstance(deger, dict):
        # Sağlayıcı başına anahtarlar ({sağlayıcı: anahtar}).
        return {k: _sifrele(v) for k, v in deger.items()}
    if not isinstance(deger, str) or not deger or deger.startswith(_DPAPI_ONEKI):
        return deger
    sifreli = _dpapi(deger.encode("utf-8"), coz=False)
    if sifreli is None:
        return deger
    return _DPAPI_ONEKI + base64.b64encode(sifreli).decode("ascii")


def _coz(deger):
    if isinstance(deger, dict):
        return {k: _coz(v) for k, v in deger.items()}
    if not isinstance(deger, str) or not deger.startswith(_DPAPI_ONEKI):
        return deger
    try:
        acik = _dpapi(base64.b64decode(deger[len(_DPAPI_ONEKI):]), coz=True)
    except Exception:
        acik = None
    # Çözülemiyorsa (başka kullanıcı/bilgisayar) anahtar boş sayılır; kullanıcı
    # ayarlardan yeniden girer.
    return acik.decode("utf-8") if acik is not None else ""


class AyarlarYoneticisi:
    # Kullanıcı tarafından değiştirilemeyen, her zaman bu değerde tutulan
    # ayarlar. Gelişmiş düzeltme arka planda daima açıktır; eski sürümlerden
    # kalan "false" kayıtları ve set() denemeleri yok sayılır.
    SABIT_AYARLAR = {"gelismis_duzeltme": True}
    # Diskte düz metin durmaması gereken ayarlar (DPAPI ile şifrelenir;
    # bellekte ve arayüzde açık hâliyle kullanılır).
    GIZLI_AYARLAR = ("ai_api_key", "ai_api_anahtarlari")

    def __init__(self):
        self._kilit = threading.RLock()
        # Diske yazılamamış (kaydet başarısız) değerler: diskten birleştirme
        # bunların üstüne eski disk değerini yazmasın diye ayrıca tutulur.
        self._bekleyenler = {}
        self.dosya_yolu = os.path.join(os.path.expanduser("~"), ".turkod_ayarlar.json")
        self.varsayilanlar = {
            "gelismis_duzeltme": True,
            "duzeltme_zaman_asimi": 5,
            "duzeltme_mesaj_araligi": 100,
            "duzeltme_maks_dongu": 12,
            "tema": "Modern Koyu",
            "otomatik_tamamlama": True,
            "otomatik_kaydetme": False,
            "otomatik_kaydetme_aralik": 30,
            "yazi_boyutu": 14,
            "yazi_tipi": "Consolas",
            "satir_numaralari": True,
            "bosluk_gostergesi": True,
            "kelime_sar": False,
            "minimap": False,
            "girinti_boyutu": 4,
            "girinti_algila": True,
            "kisayollar": {},
            "ai_aktif": False,
            "ai_saglayici": "openai",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
            # Sağlayıcı başına API anahtarları {katalog kimliği: anahtar}.
            "ai_api_anahtarlari": {},
            # "Özel (OpenAI uyumlu)" sağlayıcının adresi.
            "ai_ozel_url": "",
            # Görev -> yerel (llama.cpp) model dosyası; bu görevlerde bulut yerine kullanılır.
            "yerel_ai_gorevleri": {},
            # Eklentiler panelinden kurulan eklentilerin kimlikleri.
            "eklentiler": [],
           "ai_sistem_mesaji": """Sen bir Python kodlama asistanısın. Kullanıcı TürKod (Türkçe Python) kullanıyor ancak sen her zaman STANDART PYTHON kodu üretmelisin.

ZORUNLU KURALLAR:
1. Tüm kod bloklarını MUTLAKA ```python ile başlat ve ``` ile kapat.
2. Kod bloğu dışında ASLA kod yazma. Açıklamalar düz metin olmalı.
3. YALNIZCA Python 3.x sözdizimi kullan. JavaScript, C++, Java, SQL, HTML, CSS veya başka hiçbir dilde kod üretme.
4. TürKod kelimesi (fonksiyon, yazdır, eğer vb.) ASLA kullanma. Sadece def, print, if gibi standart Python anahtar kelimeleri kullan.
5. Eğer kullanıcı başka bir dil isterse, bunu reddet ve sadece Python verebileceğini belirt.
6. Kod bloğunun dil etiketi her zaman 'python' olmalı. Boş bırakma, 'py' yazma, 'türkod' yazma.

DOĞRU FORMAT:
Açıklama metni burada.

```python
def ornek():
    print("Merhaba")
            """,
            "ai_sicaklik": 0.7,
            # Hayalet kod (satır içi AI tamamlama): kaynak "yerel" | "api".
            # Bulut sağlayıcısının yaptığı görevler (yerel model atanmamışsa).
            "ai_bulut_gorevleri": ["sohbet", "aciklama", "hata_aciklama", "duzeltme"],
            # Düşünen modeller (akıl yürütme) düşünsün mü? Kapalı: daha hızlı yanıt.
            "ai_dusunme": False,
            # Kodi (yardımcı robot) düşünsün mü? Balonundaki ampul düğmesi.
            "kodi_dusunme": False,
            # Kodi'nin taşındığı yer [x, y] (alana göre oran); None: varsayılan köşe.
            "kodi_konum": None,
            # Kodi'nin konuşma balonunun elle verilen boyutu [genişlik, yükseklik].
            "kodi_balon": None,
            # Kodi cevaplarını sesli okusun mu?
            "kodi_sesli": False,
            # Kodi'nin yetkileri (Ayarlar → Kodi). Kodi bunları kendisi değiştiremez.
            "kodi_yetki_ayar": True,
            "kodi_yetki_eklenti": True,
            "kodi_yetki_komut": True,
            "kodi_hep_sor": False,
            # Kodi'nin sohbeti diske kaydedilsin mi, Kodi kullanıcıyı hatırlasın mı?
            "kodi_sohbet_kaydet": True,
            "kodi_hafiza": True,
            # Kodi'ye mesajla birlikte görüntü: kapali | pencere | ekran.
            "kodi_goruntu": "kapali",
            # Kodi IDE içindeki tarayıcıyı yönetebilsin mi?
            "kodi_yetki_tarayici": True,
            "ai_tamamlama_acik": True,
            "ai_tamamlama_kaynagi": "yerel",
            "ai_tamamlama_saglayici": "",
            "ai_tamamlama_model": "",
            "ai_tamamlama_gecikme": 300,
            "ai_tamamlama_cok_satir": True,
            "ai_max_token": 4096,
            # Görev -> {"saglayici": katalog kimliği ("yerel": TürKod Yerel), "model": ad}.
            # Atanmamış görev kapalıdır. None: eski ayarlardan ilk açılışta türetilir.
            "ai_gorev_atamalari": None,
            # Kullanıcının seçtiği bulut modelleri [{"saglayici", "model"}] (Ayarlar).
            "ai_bulut_modelleri": None,
            "son_proje_dizini": os.path.expanduser("~"),
            "son_dosyalar": []
        }
        self.ayarlar = self.varsayilanlar.copy()
        self.yukle()

    def yukle(self):
        if os.path.exists(self.dosya_yolu):
            try:
                with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                    kayitli = json.load(f)
                if isinstance(kayitli, dict):
                    self.ayarlar.update(self._gizlileri_coz(kayitli))
            except Exception:
                # Bozuk dosya: ilk set() varsayılanlarla üzerine yazıp tüm
                # ayarları (API anahtarı dahil) kalıcı olarak siliyordu.
                # Kurtarılabilsin diye önce yedeklenir.
                try:
                    shutil.copy2(self.dosya_yolu, self.dosya_yolu + ".bozuk")
                except OSError:
                    pass
        self.ayarlar.update(self.SABIT_AYARLAR)

    def _gizlileri_coz(self, kayit):
        kayit = dict(kayit)
        for anahtar in self.GIZLI_AYARLAR:
            if anahtar in kayit:
                kayit[anahtar] = _coz(kayit[anahtar])
        return kayit

    def _diskten_birlestir(self):
        """Diskteki güncel ayarları belleğe alır. Aynı anda açık iki pencere
        (iki backend) her set()'te tüm anlık kopyasını yazdığından, eski
        pencere diğerinin kaydettiği API anahtarını / oturumu siliyordu."""
        try:
            with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                disk = json.load(f)
            if isinstance(disk, dict):
                self.ayarlar.update(self._gizlileri_coz(disk))
                self.ayarlar.update(self.SABIT_AYARLAR)
        except Exception:
            pass
        # Eskiden kaydedilemeyen değer "sonraki set()'te yeniden denenir"
        # deniyordu ama burada diskteki eski değer onun üstüne yazılıyor,
        # değişiklik bir sonraki ayar değişikliğinde kayboluyordu.
        self.ayarlar.update(self._bekleyenler)

    def kaydet(self):
        # Komutlar ayrı iş parçacıklarında çalışır. Eskiden dosya önce
        # boşaltılıp sonra yazılıyordu; eşzamanlı bir set() sözlüğü değiştirince
        # json.dump yarıda kalıyor, dosya bozuluyor ve bir sonraki açılışta
        # TÜM ayarlar (API anahtarı dahil) sessizce kayboluyordu. Artık kilit
        # altında anlık kopya geçici dosyaya yazılıp atomik olarak taşınıyor.
        with self._kilit:
            gecici = None
            try:
                anlik = dict(self.ayarlar)
                for anahtar in self.GIZLI_AYARLAR:
                    if anahtar in anlik:
                        anlik[anahtar] = _sifrele(anlik[anahtar])
                veri = json.dumps(anlik, ensure_ascii=False, indent=2)
                # Benzersiz geçici dosya: aynı anda çalışan iki backend
                # (iki pencere) aynı .tmp dosyasına yazmasın.
                fd, gecici = tempfile.mkstemp(
                    prefix=".turkod_ayarlar_", suffix=".tmp",
                    dir=os.path.dirname(self.dosya_yolu) or None)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(veri)
                for deneme in range(5):
                    try:
                        os.replace(gecici, self.dosya_yolu)
                        gecici = None
                        break
                    except PermissionError:
                        # Antivirüs / başka süreç dosyayı kısa süre tutuyor.
                        time.sleep(0.05 * (deneme + 1))
                # Taşınamazsa yerinde yazılmaz: yarıda kalan bir yerinde yazma
                # dosyayı bozuyordu. Değer bellekte kalır, sonraki set()'te
                # yeniden denenir; çağırana başarısızlık bildirilir (eskiden
                # ayar_set yine ok: True dönüyordu).
                return gecici is None
            except Exception:
                return False
            finally:
                if gecici is not None:
                    try:
                        os.unlink(gecici)
                    except OSError:
                        pass

    def get(self, anahtar, varsayilan=None):
        return self.ayarlar.get(
            anahtar,
            self.varsayilanlar.get(anahtar, varsayilan)
        )

    def set(self, anahtar, deger):
        if anahtar in self.SABIT_AYARLAR:
            deger = self.SABIT_AYARLAR[anahtar]
        with self._kilit:
            self._diskten_birlestir()
            self.ayarlar[anahtar] = deger
            # Diske yazılabildiyse True (değer her durumda bellekte kalır).
            if self.kaydet():
                self._bekleyenler.clear()
                return True
            self._bekleyenler[anahtar] = deger
            return False
