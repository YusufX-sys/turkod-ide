<img width="692" height="388" alt="TürKod v2 1 0" src="https://github.com/user-attachments/assets/06663826-136b-448e-8b52-8c87ed27f7c5" />

<img width="500" height="500" alt="TürKod-Logo" src="https://github.com/user-attachments/assets/853c8706-0b35-461b-82f3-242d1ac541af" />

# 🇹🇷 TürKod IDE

TürKod IDE, kodlamaya yeni başlayan öğrenciler için tasarlanmış, tamamen Türkçe komutlarla çalışan, sade arayüzlü ve yapay zeka asistanı destekli bir geliştirme ortamıdır.

**Amaç:** Yazılıma yeni başlayan öğrencilerin ve gençlerin kodlama mantığını kendi ana dillerinde kavramalarını kolaylaştırmak. Proje tamamen eğitim odaklıdır.

## 🚀 Özellikler

- **Tamamen Türkçe Sözlük & Komut Yapısı:** Kodlama terimlerini Türkçe karşılıklarıyla öğrenin. Tam sözlük için [TürKod Sözlüğü.txt](./TürKod%20Sözlüğü.txt) dosyasına bakın.
- **Sade Arayüz:** Karmaşık menülerden uzak, öğrenci odaklı tasarım.
- **Yapay Zeka Asistanı:** TürKod sözlüğüne erişimi olan, kod yazmaya yardımcı olan dahili asistan.
- **RSA Dijital İmza Doğrulaması:** Kod ve uygulama bütünlüğü RSA ile imzalanır.

## 📦 Kurulum ve Çalıştırma

### 1. Hazır Çalıştırılabilir Sürüm (.exe)

Python kurmadan çalıştırmak için [Releases](../../releases) sayfasından en son sürümü indirin ve `TürKod IDE.exe` dosyasını çalıştırın.

### 2. Kaynak Koddan Çalıştırma (.py)

```bash
git clone https://github.com/YusufX-sys/turkod-ide.git
cd "turkod-ide/TürKod v2.1.0 py"
python "TürKod IDE.py"
```

> Not: Gereksinimler için [requirements](./requirements.txt) dosyasına bakın.
> Ayrıca sözlükte yer alan kütüphaneleri kullanmak için ayrı şekilde yüklemeniz gereklidir.

## 🔗 İlgili Bağlantılar

- Proje sitesi: https://yusufx-sys.github.io/turkod-site/
- Site kaynak kodu: https://github.com/YusufX-sys/turkod-site

## 🔐 Güvenlik ve RSA İmza

Bu projedeki çalıştırılabilir ve kaynak kod dosyaları RSA-2048 ile imzalanmıştır. İmza doğrulaması için `build/turkod_public.pem` anahtarı kullanılabilir.

## Sorumluluk Reddi

Bu yazılım eğitim ve deneysel amaçlıdır. Kullanımından doğabilecek veri kaybı, sistem hatası veya güvenlik sorunlarından geliştirici (Yusuf Tandoğan) sorumlu tutulamaz. Lisans detayları için [LICENSE](./LICENSE) dosyasına bakın.

© 2026 Yusuf Tandoğan
