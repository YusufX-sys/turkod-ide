<img width="500" height="500" alt="TürKod-Logo" src="https://github.com/user-attachments/assets/853c8706-0b35-461b-82f3-242d1ac541af" />

<img width="692" height="388" alt="TürKod v2 1 0" src="https://github.com/user-attachments/assets/06663826-136b-448e-8b52-8c87ed27f7c5" />


# 🇹🇷 TürKod IDE

TürKod IDE, kodlamaya yeni başlayan öğrenciler için tasarlanmış, tamamen Türkçe komutlarla çalışan, sade arayüzlü ve yapay zeka asistanı destekli bir geliştirme ortamıdır.

**Amaç:** Yazılıma yeni başlayan öğrencilerin ve gençlerin kodlama mantığını kendi ana dillerinde kavramalarını kolaylaştırmak. Proje tamamen eğitim odaklıdır.

> Not: Bu proje ile Microsoft Store'da yer alan "Türkod Stüdyosu" uygulaması arasında isim benzerliği dışında herhangi bir bağ bulunmamaktadır.

## 🚀 Özellikler

- **Tamamen Türkçe Sözlük & Komut Yapısı:** Kodlama terimlerini Türkçe karşılıklarıyla öğrenin. Tam sözlük için [TürKod Sözlüğü.txt](./TürKod%20Sözlüğü.txt) dosyasına bakın.
- **Sade Arayüz:** Karmaşık menülerden uzak, öğrenci odaklı tasarım.
- **Yapay Zeka Asistanı:** TürKod sözlüğüne erişimi olan, kod yazmaya yardımcı olan dahili asistan.
- **RSA Dijital İmza Doğrulaması:** Kod ve uygulama bütünlüğü RSA ile imzalanır.

## 📦 Kurulum
 
En güncel sürümü [Releases](../../releases/latest) sayfasından indirin
(`TurKod-Setup-X.Y.Z.exe`) ve çalıştırın. Kurulum yönetici izni istemez, tek
kullanıcı için `%LOCALAPPDATA%` altına kurulur.
 
> Kurulum dosyası şu an ticari bir kod imzalama sertifikasıyla imzalı değildir;
> Windows SmartScreen bir uyarı gösterebilir. "Ek bilgi" → "Yine de çalıştır"
> ile devam edebilirsiniz. Dosyanın SHA-256 özeti her sürümün `latest.json`
> dosyasında yayınlanır.
 
## 👨‍💻 Mimari
 
```
turkod_flutter/   Windows masaüstü arayüzü (Flutter)
turkod_ide/       Python arka ucu: çevirici, tokenizer, AST doğrulama,
                   hata ayıklayıcı, AI entegrasyonu, WebSocket sunucusu
```
 
Arayüz açılışta arka ucu (`turkod_backend.exe`) kendi alt süreci olarak başlatır
ve WebSocket üzerinden (`ws://127.0.0.1:<port>/ws`) haberleşir. Arayüz
kapandığında arka uç ve çalıştırdığı tüm alt süreçler otomatik sonlandırılır.
 
## 🔐 Güvenlik ve bütünlük
 
- Paketlenmiş uygulama, `turkod_ide.manifest.json` içindeki dosya listesi ve
  SHA-256 özetleriyle kendi bütünlüğünü doğrular; manifest RSA-PSS ile
  imzalanmıştır (bkz. `turkod_ide/signing.py`).
- Kaynak kod da aynı yöntemle ayrıca imzalanabilir (bkz. `kaynak_imzala.py`) —
  bu, deponun belirli bir hâlinin geliştirici tarafından onaylandığını
  doğrulamak isteyenler içindir.
- Güncelleme bildirimleri (`latest.json`) de aynı anahtarla imzalanır; uygulama
  imza geçersizse güncellemeyi reddeder.
## ℹ Geliştirici için: kaynaktan derleme
 
Gereksinimler: Windows 10/11, Flutter SDK, Python 3.12, PyInstaller, Inno Setup 6,
Visual Studio (C++ araçları).
 
```powershell
git clone https://github.com/YusufX-sys/turkod-ide.git
cd turkod-ide/TurKod-v3.0.0
powershell -ExecutionPolicy Bypass -File .\hazirla_ve_derle.ps1
```
 
Betik sırasıyla ortamı denetler, Flutter arayüzünü ve Python arka ucunu derler,
kullanıcı kodları için ayrı bir Python ortamı hazırlar, paketi imzalar ve
`dist\TurKod-Setup-X.Y.Z.exe` kurulum dosyasını üretir. Ayrıntılı seçenekler
için betiğin başındaki açıklamaya bakın.

## 🔗 İlgili Bağlantılar

- Proje sitesi: https://yusufx-sys.github.io/turkod-site/
- Site kaynak kodu: https://github.com/YusufX-sys/turkod-site

## Sorumluluk Reddi

Bu yazılım eğitim ve deneysel amaçlıdır. Kullanımından doğabilecek veri kaybı, sistem hatası veya güvenlik sorunlarından geliştirici (Yusuf Tandoğan) sorumlu tutulamaz. Lisans detayları için [LICENSE](./LICENSE) dosyasına bakın.

© 2026 Yusuf Tandoğan
