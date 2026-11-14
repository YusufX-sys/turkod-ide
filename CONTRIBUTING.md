# TürKod'a Katkıda Bulunma

TürKod'a ilgin için teşekkürler! Bu proje, kodlamaya yeni başlayanların Türkçe
öğrenebilmesi için var; her katkı bu amaca hizmet eder.

## Nasıl katkı verebilirim?

- **Hata bildir:** [Issues](../../issues/new/choose) sayfasından "Hata bildirimi"
  şablonunu kullan. Hatayı üreten küçük bir `.trpy` örneği çok işe yarar.
- **Sözlük önerisi:** Eksik ya da yanlış bir Türkçe karşılık mı gördün? "Sözlük
  önerisi" şablonunu kullan.
- **Özellik öner:** "Özellik isteği" şablonuyla neye ihtiyaç duyduğunu anlat.
- **Kod veya belge gönder:** Aşağıdaki adımlarla bir Pull Request aç.

## Geliştirme ortamı

1. Depoyu fork'la ve klonla.
2. Gereksinimler: Windows 10/11, Python 3.12, Flutter SDK (stable), Visual Studio 2022 veya üstü
   "Desktop development with C++".
3. Python paketleri:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Ayrıntılı derleme adımları: `TurKod-v3.3.0/nasıl-build-edilir.txt`.

## Değişiklik yaparken

- **Testler:** Göndermeden önce testleri çalıştır:
  ```powershell
  cd TurKod-v3.3.0
  python -m unittest discover -s tests
  python tools\tablo_tutarlilik.py
  ```
  Yeni bir özellik ya da hata düzeltmesi için mümkünse test ekle.
- **Sözlük değişiklikleri:** `turkod_ide/TurKod_Sozluk.txt` ve ilgili tablolar
  değiştiğinde `tools/tablo_tutarlilik.py` temiz geçmelidir. Karşılıklar çocukların
  anlayacağı, doğal Türkçe olmalı; eski adları silmek yerine geriye dönük uyumluluk
  için koru.
- **Satır sonları:** Dosyaların mevcut satır sonlarını (LF/CRLF) ve UTF-8 kodlamasını
  koru. `turkod_ide/` klasörü imzalıdır; `.gitattributes` bu klasörde satır sonu
  dönüştürmeyi kapatır.
- **İmza:** `turkod_ide/` altındaki bir dosyayı değiştirmek `turkod_ide.manifest.json`
  imzasını geçersiz kılar. Bu beklenen bir durumdur; imzayı yayın sırasında proje
  sahibi yeniler. Pull Request'inde manifest dosyalarına dokunma.
- **Kullanıcıya görünen metinler** Türkçe olmalı. Menü, kısayol ya da ayar değişirse
  kitap (`belgeler/`) da güncellenmelidir (bkz. `belgeler/KITAP_BAKIM.md`).

## Pull Request süreci

1. `main` dalından yeni bir dal aç (`duzeltme/kaplumbaga-baslik` gibi).
2. Küçük ve odaklı değişiklikler gönder; bir PR tek bir konuyu çözsün.
3. PR şablonundaki kontrol listesini doldur.
4. İnceleme sonrası istenen değişiklikleri aynı dala gönder.

## Davranış kuralları

Bu projeye katılan herkes [Davranış Kuralları](./CODE_OF_CONDUCT.md)'na uymayı kabul eder.

## Lisans

Gönderdiğin katkılar projenin [MIT Lisansı](./LICENSE) altında yayımlanır.
