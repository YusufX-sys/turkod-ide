# Güvenlik Politikası

## Desteklenen sürümler

Güvenlik düzeltmeleri yalnızca en son sürüme yapılır.

| Sürüm | Destek |
|---|---|
| 3.3.x | ✅ |
| < 3.3 | ❌ |

## Güvenlik açığı bildirme

Lütfen güvenlik açıklarını **herkese açık issue olarak açma.**

- Tercih edilen yol: GitHub'daki **Security → Report a vulnerability** düğmesiyle
  gizli bir bildirim gönder.
- Ya da e-posta: **yusuftndgn.2@gmail.com** (konu satırına "TürKod güvenlik" yaz).

Bildiriminde şunlar olsun:

- Etkilenen TürKod sürümü ve Windows sürümü
- Sorunun açıklaması ve olası etkisi
- Yeniden üretme adımları (varsa örnek `.trpy` dosyası)

Bildirimini birkaç gün içinde yanıtlamaya çalışırım. Sorun doğrulanırsa düzeltme
yayımlanana kadar ayrıntılar gizli tutulur; istersen sürüm notlarında adınla teşekkür
edilir.

## İmza ve bütünlük

TürKod; uygulama dosyalarını, kaynak kodu ve güncelleme bildirimlerini RSA-PSS
(SHA-256) ile imzalar. Ortak anahtar `TurKod-v3.3.0/turkod_ide/signing.py`
dosyasındadır. Kaynak kodun imzasını özel anahtar olmadan doğrulamak için:

```powershell
cd TurKod-v3.3.0
python kaynak_imzala.py --dogrula
```

İmzası doğrulanamayan bir kurulum dosyası ya da kaynak kod görürsen lütfen bildir.
