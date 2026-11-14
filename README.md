<div align="center">

<img width="220" alt="TürKod logosu" src="https://github.com/user-attachments/assets/853c8706-0b35-461b-82f3-242d1ac541af" />

# TürKod IDE

**Kodlamayı ana dilinde öğren.** Türkçe komutlarla Python yazdıran, çocuklar ve yeni başlayanlar için tasarlanmış, yapay zekâ destekli bir geliştirme ortamı.

[![Sürüm](https://img.shields.io/badge/s%C3%BCr%C3%BCm-3.3.0-0b7285)](../../releases/latest)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-2b8a3e)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-1971c2)](../../releases/latest)
[![Katkılar açık](https://img.shields.io/badge/katk%C4%B1lar-a%C3%A7%C4%B1k-e8590c)](./CONTRIBUTING.md)

[**İndir**](../../releases/latest) · [**Proje sitesi**](https://turkod.pages.dev/) · [**3.3'te neler yeni?**](https://turkod.pages.dev/whats-new/) · [**Sözlük**](https://turkod.pages.dev/learn/sozluk/) · [**Hata bildir**](../../issues/new/choose)

<img width="800" alt="TürKod IDE ekran görüntüsü" src="https://github.com/user-attachments/assets/d4e2c6f7-99ca-4c09-8e9e-1c0cabbd447c" />

</div>

---

## TürKod nedir?

TürKod, Python'un gücünü Türkçe anahtar kelimelerle sunan bir programlama dili ve o dil
için yazılmış bir IDE'dir. Yazdığın `.trpy` kodu arka planda Python'a çevrilip çalıştırılır;
hatalar da Türkçe açıklanır.

```python
isim = girdi_al("Adın ne? ")
için i içinde aralık(3):
    yazdır(f"Merhaba {isim}! ({i + 1})")

eğer uzunluk(isim) > 5:
    yazdır("Ne güzel uzun bir isim!")
değilse:
    yazdır("Kısa ve öz!")
```

**Amaç:** Yazılıma yeni başlayan öğrencilerin kodlama mantığını kendi ana dillerinde
kavramalarını kolaylaştırmak. Proje tamamen eğitim odaklıdır ve kâr amacı gütmez.

> Bu proje ile Microsoft Store'daki "Türkod Stüdyosu" uygulaması arasında isim
> benzerliği dışında hiçbir bağ yoktur.

## Öne çıkanlar

| Özellik | Açıklama |
|---|---|
| 🇹🇷 **Türkçe dil** | 3000'e yakın Türkçe karşılık: anahtar kelimeler, yerleşik fonksiyonlar, `kaplumbağa`, `tkinter`, `pygame`, `ursina`, `math`, `random`… Türkçe harfsiz yazım (`icin`, `sayi`) da çalışır. |
| 🤖 **Kodi, yapay zekâ arkadaşı** | Programın içindeki robot Kodi soruları cevaplar, hatayı bulur, kod yazar, menüleri ve ayarları yönetir, sesli konuşur, masaüstüne çıkar. |
| ✨ **Hayalet kod ve Akıllı Düzelt** | VS Code tarzı satır içi tamamlama; hataları yerelde deneyerek düzelten Akıllı Düzelt. |
| 🧠 **Yerel ve bulut modeller** | 220+ sağlayıcı (Groq, OpenAI, Anthropic, Gemini…) ya da internetsiz çalışan yerel GGUF modelleri (llama.cpp, NVIDIA GPU desteği). |
| 🐞 **Gerçek hata ayıklayıcı** | Kesme noktası, koşullu kesme noktası, izleme ifadeleri, çağrı yığını. |
| 📦 **EXE'ye Dönüştür** | Programını TürKod kurulu olmayan bilgisayarlarda da çalışan bir `.exe` dosyasına dönüştür. |
| 📖 **Kitap içinde** | "TürKod ile Kodlama Macerası" kitabı programla gelir, kendi PDF görüntüleyicisinde açılır. |
| 🖥️ **Terminal ve komut satırı** | Her sekmeye ayrı terminal, TürKod Kabuğu, `turkod dosya.trpy`, `--cevir`, `--duzelt`, `--anlam`… |
| 🔁 **Python ⇄ TürKod çeviri** | Var olan Python kodunu tek tıkla TürKod'a, TürKod'u Python'a çevir. |
| 🔐 **İmzalı ve doğrulanabilir** | Uygulama dosyaları, kaynak kod ve güncellemeler RSA-PSS ile imzalanır. |

## Kurulum

1. [Releases](../../releases/latest) sayfasından `TurKod-Setup-3.3.0.exe` dosyasını (yaklaşık 128 MB) indir.
2. Çalıştır. Kurulum yönetici izni istemez; tek kullanıcı için `%LOCALAPPDATA%\Programs` altına kurulur.
3. Kurulumdaki seçenekler:
   - **PATH'e ekle** (varsayılan açık): terminalde `turkod oyun.trpy` yazabilirsin.
   - **.trpy dosyalarını ilişkilendir** (varsayılan açık): `.trpy` dosyasına çift tıklayınca program çalışır.
   - **Masaüstü kısayolu** (varsayılan kapalı).

Kurulumla birlikte Başlat menüsüne **TürKod**, **TürKod Terminali** ve
**TürKod ile Kodlama Macerası (Kitap)** kısayolları eklenir. Yeni sürüm çıktığında program
güncellemeyi kendisi bulur, imzasını doğrulayıp kurar.

> Kurulum dosyası şu an ticari bir kod imzalama sertifikasıyla imzalı değildir; Windows
> SmartScreen uyarı gösterebilir. "Ek bilgi" → "Yine de çalıştır" ile devam edebilirsin.
> Dosyanın SHA-256 özeti her sürümün `latest.json` dosyasında yayınlanır.

**Gereksinimler:** Windows 10 veya 11 (64 bit). Ayrıca Python kurmana gerek yok; TürKod
kendi Python'unu getirir.

## Proje yapısı

```
TurKod-v3.3.0/
├── turkod_flutter/   Windows masaüstü arayüzü (Flutter / Dart)
├── turkod_ide/       Python arka ucu: çevirici, tokenizer, AST katmanı, hata ayıklayıcı,
│                     Akıllı Düzelt, Kodi, yapay zekâ ve yerel model yönetimi, WebSocket sunucusu
├── tests/            Birim ve uçtan uca testler
├── tools/            Sözlük denetimi, kitap araçları, yardımcı betikler
├── belgeler/         Kitap (PDF), lisanslar, sorumluluk reddi
└── turkod.iss        Inno Setup kurulum betiği
```

Arayüz açılışta arka ucu (`turkod_backend.exe`) kendi alt süreci olarak başlatır ve
WebSocket üzerinden (`ws://127.0.0.1:<port>/ws`) haberleşir. Arayüz kapandığında arka uç
ve çalıştırdığı tüm alt süreçler kendiliğinden sonlandırılır.

## Kaynaktan derleme

Gereksinimler: Windows 10/11, Flutter SDK (stable), Python 3.12 (64 bit), Visual Studio 2022
veya üstü ("Desktop development with C++" ve Windows SDK), Inno Setup 6.6+. Derleme sırasında
en az 8 GB RAM ve otomatik yönetilen sayfa dosyası önerilir (Dart derleyicisi bellek ister).

```powershell
git clone https://github.com/YusufX-sys/turkod-ide.git
cd turkod-ide/TurKod-v3.3.0
powershell -ExecutionPolicy Bypass -File .\hazirla_ve_derle.ps1
```

Betik ortamı denetler, Flutter arayüzünü ve Python arka ucunu derler, kullanıcı kodları
için ayrı bir Python ortamı hazırlar, paketi imzalar ve `dist\TurKod-Setup-X.Y.Z.exe`
kurulum dosyasını üretir. Adım adım anlatım:
[`nasıl-build-edilir.txt`](./TurKod-v3.3.0/nas%C4%B1l-build-edilir.txt).

> Kendi derlemeni imzalamak için kendi anahtar çiftini üretmen gerekir
> (`python manifest_imzala.py --anahtar-uret <yol>`); resmî özel anahtar depoda yer almaz.

### Testler

```powershell
cd TurKod-v3.3.0
python -m unittest discover -s tests
python tools\tablo_tutarlilik.py     # sözlük tutarlılık denetimi
```

## Güvenlik ve bütünlük

- Paketlenmiş uygulama, `turkod_ide.manifest.json` içindeki dosya listesi ve SHA-256
  özetleriyle kendi bütünlüğünü doğrular; manifest RSA-PSS ile imzalıdır
  (bkz. `turkod_ide/signing.py`).
- Kaynak kod da aynı yöntemle imzalıdır. Deponun bu hâlinin geliştirici tarafından
  onaylandığını özel anahtar olmadan doğrulayabilirsin:
  ```powershell
  cd TurKod-v3.3.0
  python kaynak_imzala.py --dogrula
  ```
- Güncelleme bildirimleri (`latest.json`) de aynı anahtarla imzalanır; imza geçersizse
  uygulama güncellemeyi reddeder.

Bir güvenlik açığı bulduysan lütfen herkese açık issue açma; [SECURITY.md](./SECURITY.md)
dosyasındaki adımları izle.

## Katkıda bulunma

Hata bildirimleri, sözlük önerileri, belge düzeltmeleri ve kod katkıları memnuniyetle
karşılanır. Başlamadan önce [CONTRIBUTING.md](./CONTRIBUTING.md) ve
[Davranış Kuralları](./CODE_OF_CONDUCT.md)'nı oku.

## Bağlantılar

- Proje sitesi: https://turkod.pages.dev/
- 3.3 yenilikleri: https://turkod.pages.dev/whats-new/
- Site kaynak kodu: https://github.com/YusufX-sys/turkod-site
- Sözdizimi davranışları: https://turkod.pages.dev/learn/sozdizimi-davranislari/

## Lisans ve sorumluluk reddi

TürKod [MIT Lisansı](./LICENSE) ile dağıtılır. Üçüncü taraf bileşenlerin lisansları
`TurKod-v3.3.0/belgeler/UCUNCU_TARAF_LISANSLARI.txt` dosyasındadır.

Bu yazılım eğitim ve deneysel amaçlıdır. Kullanımından doğabilecek veri kaybı, sistem
hatası veya güvenlik sorunlarından geliştirici sorumlu tutulamaz.

© 2026 Yusuf Tandoğan
