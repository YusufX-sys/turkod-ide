"""Ayar yonetimi."""
import json
import os


class AyarlarYoneticisi:
    def __init__(self):
        self.dosya_yolu = os.path.join(os.path.expanduser("~"), ".turkod_ayarlar.json")
        self.varsayilanlar = {
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
           "ai_sistem_mesaji": """Sen bir Python kodlama asistanisin. Kullanici TürKod (Türkçe'ye çevrilmiş özel Python) yazıyor.
            Sen ise Python değil ``` python ``` arasına Python yaz.
            KURALLAR:
            - Kod verirken MUTLAKA ```python ve ``` arasina yaz.
            - Aciklama kismi duz metin, kod kismi ayri blok olmali.
            -Sadece Python kodları ver başka bir dil kullanamazsın.
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
            except:
                pass

    def kaydet(self):
        try:
            with open(self.dosya_yolu, "w", encoding="utf-8") as f:
                json.dump(self.ayarlar, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get(self, anahtar):
        return self.ayarlar.get(anahtar, self.varsayilanlar.get(anahtar))

    def set(self, anahtar, deger):
        self.ayarlar[anahtar] = deger
        self.kaydet()
