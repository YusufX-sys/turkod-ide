"""Ayar yonetimi."""
import json
import os
import shutil
import tempfile
import threading
import time


class AyarlarYoneticisi:
    # Kullanıcı tarafından değiştirilemeyen, her zaman bu değerde tutulan
    # ayarlar. Gelişmiş düzeltme arka planda daima açıktır; eski sürümlerden
    # kalan "false" kayıtları ve set() denemeleri yok sayılır.
    SABIT_AYARLAR = {"gelismis_duzeltme": True}

    def __init__(self):
        self._kilit = threading.RLock()
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
            "ai_aktif": False,
            "ai_saglayici": "OpenAI",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
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
            "ai_max_token": 4096,
            "son_proje_dizini": os.path.expanduser("~"),
            "son_acik_dosyalar": []
        }
        self.ayarlar = self.varsayilanlar.copy()
        self.yukle()

    def yukle(self):
        if os.path.exists(self.dosya_yolu):
            try:
                with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                    kayitli = json.load(f)
                if isinstance(kayitli, dict):
                    self.ayarlar.update(kayitli)
            except Exception:
                # Bozuk dosya: ilk set() varsayılanlarla üzerine yazıp tüm
                # ayarları (API anahtarı dahil) kalıcı olarak siliyordu.
                # Kurtarılabilsin diye önce yedeklenir.
                try:
                    shutil.copy2(self.dosya_yolu, self.dosya_yolu + ".bozuk")
                except OSError:
                    pass
        self.ayarlar.update(self.SABIT_AYARLAR)

    def _diskten_birlestir(self):
        """Diskteki güncel ayarları belleğe alır. Aynı anda açık iki pencere
        (iki backend) her set()'te tüm anlık kopyasını yazdığından, eski
        pencere diğerinin kaydettiği API anahtarını / oturumu siliyordu."""
        try:
            with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                disk = json.load(f)
            if isinstance(disk, dict):
                self.ayarlar.update(disk)
                self.ayarlar.update(self.SABIT_AYARLAR)
        except Exception:
            pass

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
                # yeniden denenir.
            except Exception:
                pass
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
            self.kaydet()
