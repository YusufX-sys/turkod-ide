"""Ayar yonetimi."""
import json
import os


class AyarlarYoneticisi:
    def __init__(self):
        self.dosya_yolu = os.path.join(os.path.expanduser("~"), ".turkod_ayarlar.json")
        self.varsayilanlar = {
            "gelismis_duzeltme": False,
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
                    self.ayarlar.update(kayitli)
            except Exception:
                pass

    def kaydet(self):
        try:
            with open(self.dosya_yolu, "w", encoding="utf-8") as f:
                json.dump(self.ayarlar, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, anahtar, varsayilan=None):
        return self.ayarlar.get(
            anahtar,
            self.varsayilanlar.get(anahtar, varsayilan)
        )

    def set(self, anahtar, deger):
        self.ayarlar[anahtar] = deger
        self.kaydet()
