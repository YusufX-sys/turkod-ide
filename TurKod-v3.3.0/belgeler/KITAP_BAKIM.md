# Kitap bakım kılavuzu (Claude için)

Bu dosya, programda bir güncelleme yapıldıktan sonra **TürKod ile Kodlama Macerası**
kitabının programla uyumlu tutulması içindir. Programın kullanıcıya görünen bir
yerini (menü, kısayol, ayar, komut adı, sözlük kelimesi, hata mesajı ...) değiştiren
her işten sonra aşağıdaki kontrol listesini uygula.

## Kitap nerede, nasıl açılıyor?

| Ne | Nerede |
|---|---|
| Kitap (tek kaynak) | `belgeler/TurKod_ile_Kodlama_Macerasi.pdf` |
| Derleme kopyası | `dist/TurKod/belgeler/` (derleme sırasında kopyalanır; elle güncelleme) |
| Programda açılışı | **Öğren → TürKod ile Kodlama Macerası (Kitap)**: `turkod_flutter/lib/yardim.dart` (`kKitapDosyasi`) |
| Araçlar | `tools/kitap/` (aşağıda) |

Kitabın **kaynak dosyası yok**. ReportLab ile üretilmiş, sonra PyMuPDF ile
düzenlenmiştir. PDF'e gömülü fontlar Unicode eşlemesi olmayan alt kümelerdir; yeni
metin `tools/kitap/fontlar/` içindeki tam DejaVu fontlarıyla yazılır (lisans:
`LICENSE_DEJAVU`).

## Araçlar (`tools/kitap/`)

| Dosya | Ne işe yarar? |
|---|---|
| `kitap_araclari.py` | Ortak kütüphane: kitabın renkleri/ölçüleri, sayfa şablonu, paragraf, tablo, renkli kutular, kod ve terminal kutusu, ekran görüntüsü, Kodi konuşma balonu, `satir_degistir` (var olan bir satırı aynı stille yeniden yazar), `sayfa_numarasi_yaz`. Fontta olmayan karakter (emoji) ya da sığmayan başlık hata verir. Font kısa adları her çalıştırmada benzersizdir; sabit ad kullanma (sayfadaki eski, alt kümeye indirilmiş font yeniden kullanılır ve rakamlar bozuk çıkar). |
| `kilavuz_icerik.py` | Bölüm 21 "TürKod IDE tam kılavuzu" içeriği (her sayfa: başlık, alt başlık, bloklar). **Arayüz değişince burayı düzenle.** |
| `kilavuz_ekle.py` | Bölüm 21'i kitaba ekler/yeniler. Tekrar çalıştırılabilir: eski "BÖLÜM 21" sayfalarını silip yeniden üretir, sertifikadan önce koyar, İçindekiler'i ve sertifika sayfa numarasını günceller. `--png KLASOR` değişen sayfaları resim olarak çizer. |
| `kodi_bilgisi_uret.py` | Kılavuzu (`kilavuz_icerik.py`) programdaki Kodi'nin bilgi dosyasına (`turkod_ide/kodi_kilavuz.py`) çevirir. Kodi her soruda ilgili bölümleri buradan seçip yapay zekâya verir. **`kilavuz_ekle.py`'den sonra her seferinde çalıştır.** Kodi'nin kimliği ve temel bilgileri (yapımcı, bağlantılar, dilin temel kelimeleri) `turkod_ide/kodi.py` içindedir; bunlar değişirse oraya da bak. |
| `kitap_ornek_testi.py` | Kitaptaki kod örneklerini Flutter arayüzünün WebSocket protokolüyle gerçek arka uçta çalıştırıp çıktıyı karşılaştırır; ayrıca TürKod → Python → TürKod gidiş-dönüşünde önerilen yazımdan sapmaları listeler. |
| `ekran_araci.py` | Ekran görüntüleri için programı başlatır, pencereyi sabit boyuta getirir, tıklar, tuşa basar, yakalar. |
| `goruntuler/` | Bölüm 21'deki ekran görüntüleri (PNG). |

Komutlar proje kökünde çalıştırılır:

```bash
python tools/kitap/kitap_ornek_testi.py
```

```bash
python tools/kitap/kilavuz_ekle.py --png "%TEMP%\kitap_png"
```

## Kitabın yapısı

- s.1 kapak, s.2 "Merhaba, ben Kodi!", s.3 İçindekiler (bölümler).
- s.4 **"İçindekiler: Bölüm 21"**: kılavuzun her sayfası numarasıyla (`kilavuz_ekle.py` üretir).
- s.5-57: Bölüm 1-20 (asıl ders içeriği; elle düzenlenen sayfalar). Bölüm 4 (s.9-14) IDE'yi kısaca tanıtır.
- s.58 ve sonrası: **Bölüm 21 "TürKod IDE tam kılavuzu"** (`kilavuz_ekle.py` üretir, elle düzenleme; içerik `kilavuz_icerik.py`).
- Son sayfa: sertifika.
- Her bölüm sayfasının sol üstünde "BÖLÜM N" hapı vardır; araçlar sayfaları buna göre bulur. Bölüm 21'in şablonu "BÖLÜM 16" sayfasıdır (içeriği silinip arka planı kopyalanır).
- `kilavuz_ekle.py` her çalıştığında: s.4'ü ve Bölüm 21'i yeniden üretir, **bütün sayfa numaralarını** (kapak hariç) baştan yazar ve s.3'teki numaraları bölümlerin gerçek yerinden ("BÖLÜM N" hapının ilk göründüğü sayfa) hesaplar. Bu yüzden sayfa eklemek/silmek numaraları bozmaz; ama s.3'e yeni bir satır gerekiyorsa (yeni bölüm) betiği de güncelle.
- Kitapta bir sayfayı elle değiştirdikten sonra da `kilavuz_ekle.py` çalıştır (numaralar ve içindekiler tazelenir) ve sayfa numarası denetimini yap:
  ```python
  import pymupdf
  d = pymupdf.open("belgeler/TurKod_ile_Kodlama_Macerasi.pdf")
  for i, p in enumerate(d):
      nums = [s["text"] for b in p.get_text("dict")["blocks"] for l in b.get("lines", [])
              for s in l["spans"] if s["bbox"][1] > 800 and s["bbox"][0] > 520 and s["text"].strip().isdigit()]
      if i and nums != [str(i + 1)]:
          print("hatalı numara", i + 1, nums)
  ```

## Program değişince kontrol listesi

1. **Neyin değiştiğini bul.** `turkod_flutter/lib/` (menü etiketleri `_varsayilanEylemler()`, kısayollar, ayarlar, paneller), `turkod_ide/server.py` komutları, `turkod_ide/TurKod_Sozluk.txt` ve `dictionary.py` `ESKI_ADLAR` (yeniden adlandırılan kelimeler), `runner.py` hata mesajları, `kabuk.py` komut/dersleri.
2. **Sözlükte ad değiştiyse** kitabın metninde eski adı ara ve düzelt:
   ```python
   import pymupdf
   d = pymupdf.open("belgeler/TurKod_ile_Kodlama_Macerasi.pdf")
   for i, p in enumerate(d, 1):
       if "eski_ad" in p.get_text():
           print(i)
   ```
   Bölüm 1-20'deki bir satırı `kitap_araclari.satir_degistir(page, "satırın tam metni", [(yeni_metin, stil_alinacak_span_no), ...])` ile düzelt; sonra `doc.subset_fonts()` ve `doc.save(...)`. Bölüm 21'deyse `kilavuz_icerik.py`'yi düzenle.
3. **`kitap_ornek_testi.py` çalıştır.** Bütün örnekler geçmeli; "gidiş-dönüş farkları" listesi boş olmalı. Fark varsa kitap eskimiş bir yazım öğretiyordur: kitabı çeviricinin ürettiği yazıma göre düzelt. Kitapta örnek değiştirirsen bu dosyadaki `ORNEKLER` listesini de güncelle.
4. **Arayüz değiştiyse** `kilavuz_icerik.py`'yi güncelle ve etkilenen **ekran görüntülerini yeniden al** (aşağıda), sonra `kilavuz_ekle.py` ve `kodi_bilgisi_uret.py` çalıştır. Bölüm 4'teki (s.9-14) eski ekran görüntüleri de etkileniyorsa kullanıcıya söyle.
5. **Gözle kontrol et:** `--png` ile çizilen sayfalara bak (taşan yazı, üst üste binen öğe, boş kutu).
6. `python -m unittest discover -s tests -p "test_*.py"` ve `python tools/tablo_tutarlilik.py` geçmeli.
7. `dist/` kopyasına dokunma (derlemede kopyalanır). `turkod_ide` değiştiyse manifest imzasını kullanıcı `manifest_imzala.py` ile yeniden atar.

## Kitabın öğretmesi gereken yazımlar

- Sayı ve liste döngüsü `için` ile: `için i aralık(5):`, `için meyve içinde meyveler:`. `döngü` yalnızca şartlı döngü: `döngü enerji > 0:`.
- Türkçe harfli adlar: `kaplumbağa` (kaplumbaga değil), `sayı` (sayi değil). Türkçe harfsiz yazım çalışır ama kitapta kullanılmaz.
- `kaplumbağa.tamamla()` (eski `çıkışta_bekle`), `kalem_indir()` (eski `kalem_bırak`), `en_büyük` / `en_küçük` (eski `maksimum`), `rastgele.tamsayı(1, 10)`.
- Kesin karşılık için sözlük ve ters çevirici esas alınır: bir Python kodunu `python_kodu_turkceye_cevir` ile çevir; çıkan yazım kitabın kullanacağı yazımdır.
- Kitap metninde emoji kullanma (DejaVu'da yok, kutu olarak çıkar). Başlıklar tek satıra sığmalı (araç denetler).
- **Dil:** kitap 7 yaş ve üzeri çocuklar içindir. Çocuğa "sen" diye, sıcak ve benzetmeli konuş ("Gezgin senin oyuncak dolabın"); kuru, resmî kullanım kılavuzu dili kullanma. Kitabın öğeleri: Kodi konuşma balonu (`("kodi", metin)`), Mini Görev, İpucu, Dikkat, Biliyor muydun? kutuları. Konuların çoğu bir Mini Görev'le biter. Büyüklere yönelik teknik notlar "Büyükler için" diye işaretlenir ama yine samimidir.
- **İçindekiler eksiksiz olmalı:** yeni bir kılavuz sayfası eklenince s.4 kendiliğinden güncellenir; yeni bir bölüm eklenirse s.3'e satırı da eklenmeli.
- Kod örneklerinin çıktısı gerçekten çalıştırılarak doğrulanır; tahmini çıktı yazma.

## Ekran görüntüleri

Görüntüler **güncel kaynaktan derlenmiş** uygulamadan alınır (kurulu sürüm ya da `dist/` eski olabilir).

1. Arayüzü derle (yayın derlemesine dokunmamak için Profile):
   ```bash
   cd turkod_flutter && flutter build windows --profile
   ```
   Çıktı: `turkod_flutter/build/windows/x64/runner/Profile/turkod_flutter.exe`. Yanında `backend\` klasörü olmadığı için uygulama geliştirici kipinde çalışır ve arka ucu kaynaktan başlatır (`python -m turkod_ide.server`).
2. Ayrı bir profil klasörü hazırla (kullanıcının gerçek ayarlarına dokunma). Klasörde `.turkod_ayarlar.json` olsun: `son_proje_dizini` (örnek .trpy dosyaları olan bir klasör), `son_oturum` (açılacak dosyaların yolları), `arayuz_turu_goruldu: true`, `tema: "Modern Koyu"`.
3. Programı başlat ve yönet:
   ```bash
   python tools/kitap/ekran_araci.py baslat turkod_flutter/build/windows/x64/runner/Profile/turkod_flutter.exe PROFIL_KLASORU
   ```
   Sonra `yakala`, `tikla`, `tus`, `yaz`, `kapat` komutları. Pencere 1440x900 fiziksel piksele getirilir. Her `yakala`dan sonra resmi açıp doğru ekranı yakaladığını kontrol et.
4. Görüntüyü `tools/kitap/goruntuler/` içine aynı adla kaydet ve `kilavuz_ekle.py` çalıştır.

Pratik notlar (ilk çekimde öğrenildi):

- Kısayollar ancak pencere odaktayken çalışır: önce `tikla` ile editöre ya da ilgili alana tıkla.
- Kodu `yaz` ile harf harf yazma; editörün otomatik parantez kapatması metni bozar. `yapistir` kullan.
- Diyalogları Komut Paleti ile aç (`tus ctrl+shift+p`, `yaz "Klavye"`, `tus enter`).
- Kişisel bilgi görünen yerleri kes: kullanıcı klasörü yolu (Yerel AI penceresinin üst kısmı), görev çubuğu, masaüstündeki diğer pencereler. Hakkında penceresinin imza satırları geliştirici kipinde "Dosya boyutu değişmiş" der; o kısmı kullanma.
- Menü ve diyalog kutularını kırparken kutuyu taşma dolgusuyla bulmak işe yarar (PIL `ImageDraw.floodfill`, kutunun içinden bir tohum noktası).

| Dosya (`goruntuler/`) | Neyi gösteriyor | Nasıl alındı |
|---|---|---|
| genel_ekran.png | Tüm pencere, tahmin oyunu çalışırken | Çalıştır, terminale 5 ve 8 yazıldı |
| arayuz_turu.png | Turun 4. adımı | Komut Paleti → "Arayüz Turu", 3 kez → |
| bildirim.png | Bildirim baloncuğu | Hata ayıklamayı durdurunca çıkan bildirim, kırpıldı |
| menu_dosya.png, menuler_1.png, menuler_2.png | Açık menüler | Menü adına tıklayıp kırpıldı; 1 ve 2 birleşik pafta |
| arac_cubugu.png | Araç çubuğunun tamamı | AI paneli kapalıyken (sağ üstteki AI düğmesi (1351, 62)) kırpıldı: (466, 86)-(1328, 140). 2026-11-05 ikinci çekim: araç çubuğu ortalandı ve 46 px oldu; editör kırpmaları artık y=198'den başlar, kod satırı n'nin y'si 225 + (n-1)·25 |
| panel_tasima.png | Gezgin başlığı editörün üstüne sürüklenirken (bırakmadan) | Fare (140, 107)'de basılı, (700, 420)'ye taşındı, yakalandı, sonra kendi yerine bırakıldı; (62, 84)-(996, 600) |
| panel_duzeni.png | Panel düzeni menüsü | En sağ üstteki düğme (1392, 62); (1126, 84)-(1414, 330) |
| kodi_selam_dusunme.png | Kodi selam verirken ve düşünürken, yan yana | Sol şeritteki Kodi düğmesi (30, 353); selamdan sonra soru yazıldı. Yapay zekâ olarak yerelde (127.0.0.1) hazır cevap veren taklit bir OpenAI uyumlu sunucu kullanıldı (Ayarlar: "ozel" sağlayıcı, `kodi_dusunme: true`); iki kare (476, 352)-(972, 850). 2026-11-07: sağdaki robot yeni düşünme pozuyla (el çenede, öbür el dirsekte) değiştirildi: `KodiRessami(ifade: dusunceli)` 432x560 saydam çizildi, 1,075 ölçekle (934, 405)'e kondu |
| kodi_eylem.png | Kodi terminali açmış, kodu yazmak için izin istiyor | Taklit sunucuya "1den 5e sayan bir program yaz" soruldu (cevapta eylem bloğu: panel terminal, kod_yaz, komut run.run); terminal açılınca Kodi yukarı çıkar, balon tekerlekle bir adım yukarı kaydırıldı; (440, 80)-(980, 610). Not: Kodi artık bütün çalışma alanının üstünde; çekimden önce profilde `kodi_konum` olmamalı (varsayılan köşe) |
| kodi_cevap.png | Kodi'nin cevabı (TürKod kodlu) | Aynı çekim, cevap yazılıp bitince; (476, 215)-(972, 850) |
| kodi_yonetim.png | Kodi'nin balonu: sekmeye geçti, EXE panelini açtı, Ayarlar'da Kodi bölümünü açtı | 2026-11-06, kullanıcının oturumunda; üç istek yerel komut çözücüyle (yapay zekâsız) yapıldı; balon kırpıldı (ekran 1920x1080: (1262, 118)-(1592, 706)) |
| ayarlar_kodi.png | Ayarlar → Kodi kartı (Kodi'nin yetkileri) | Kodi'ye "Ayarlarda Kodi bölümünü aç" denildi, tekerlekle 2 adım aşağı kaydırıldı; kart kırpıldı ((418, 262)-(1267, 788)) |
| kodi_sesli.png | Masaüstü Kodi'nin balonu, cevabı sesli okurken ("Konuşuyorum..." şeridi) | 2026-11-06, kullanıcının oturumunda (gerçek Groq modeli), sesli cevap açık; "Değişken nedir? Kısaca örnekle anlat" soruldu; yalnızca balon kırpıldı (ekran 1920x1080: (594, 85)-(1072, 865)) |
| kodi_masaustu.png | Kodi TürKod penceresinin kenarından taşarken "Bırak, masaüstüne çıkayım!" | Kodi'ye basılı tutulup pencerenin sağ kenarından dışarı sürüklendi, bırakmadan yakalandı; pencerenin içinde kalan kısım kırpıldı |
| groq_giris.png | console.groq.com hesap açma / giriş sayfası | Uygulama içi tarayıcıda açıldı (giriş yapılmadan), çerez bandı kapatıldı. API Keys sayfasının görüntüsü yok: giriş gerektirir, kişisel hesap görünür |
| groq_saglayici.png, groq_form.png | Sağlayıcı bağla: "groq" araması; anahtar yapıştırılmış form | Deneme profilinde, sahte anahtarla (noktalarla gizli); gerçek anahtar kullanılmadı |
| groq_model_sec.png | Groq modelleri seçim penceresi | Kullanıcının oturumunda; pencerenin boş orta kısmı kesildi (üst 480 px + alt 90 px birleştirildi) |
| groq_gorevler.png | Görevlere Groq modelleri atanmış, Kodi "Otomatik: Groq • ..." | Kullanıcının oturumunda Ayarlar → Yapay Zekâ: Görevler; yarım görünen üst satır kesildi |
| pdf_sekmesi.png | Kitap PDF sekmesinde | Kitap `kitap.pdf` adıyla örnek projeye kopyalandı, Gezgin yenilendi, dosyaya tıklandı; (62, 84)-(996, 860) |
| karsilama.png | Karşılama ekranı (hiç sekme yokken) | Profilde `son_dosyalar` = `C:\Kodlarım` içindeki iki dosya, sekme açık değil; editör alanı (366, 196)-(988, 830) kırpıldı |
| komut_paleti.png | Komut Paleti, "kay" araması | Ctrl+Shift+P |
| gezgin_sag_tik.png | Gezgin sağ tık menüsü | Dosyaya sağ tık |
| editor_hata.png | Kırmızı hata satırı + durum çubuğu | Eksik `:` olan kod yapıştırıldı |
| tamamlama.png | Öneri listesi | Yeni satırda "yaz" |
| bul_degistir.png | Bul / Değiştir, "sayı" | Ctrl+H, Enter |
| bolunmus_gorunum.png | Bölünmüş editör | Ctrl+\ |
| sorunlar.png | Sorunlar penceresi | Ctrl+Shift+M |
| akilli_duzelt.png | Akıllı Düzeltme Raporu | Hatalı kodda Düzelt düğmesi |
| hata_ayiklayici.png | Kesme noktasında durmuş program | 4. satıra kesme noktası, F5, F5 |
| kaplumbaga_penceresi.png | Kaplumbağa çizim penceresi ("TürKod Kaplumbağa" başlığı, program simgesi) | kare_ciz.trpy çalıştırıldı; tam ekran görüntüsünden kırpıldı. 2026-11-04: pencere kısmı, `calistirici.Hazirlik` ile (IDE açılmadan) çalıştırılan programın PrintWindow görüntüsüyle değiştirildi; Tk penceresi DPI'a göre ölçeklenmediği için 1,25 kat büyütüldü |
| ai_paneli.png | Model yokken AI paneli | genel_ekran'dan kırpıldı |
| ayarlar_genel.png, ayarlar_ai_gorevler.png, ayarlar_ai_modeller.png | Ayarlar bölümleri | Ayarlar sekmesi, terminal kapalı, tekerlekle kaydırıldı |
| yerel_ai.png | Yerel AI önerileri | Komut Paleti → "Yerel AI", 20 sn beklendi, alt kısım kırpıldı |
| klavye_kisayollari.png | Klavye Kısayolları | Komut Paleti → "Klavye" |
| eklentiler.png | Eklenti Özellikleri paneli | Aktivite çubuğundaki ikinci düğme |
| kabuk.png | Terminalde TürKod Kabuğu | Terminal büyütüldü, "anlam yazdır" ve "dersler" |
| kod_arama.png | Kod Arama Çevirici | Komut Paleti → "Kod Arama", "print", Çevir |
| hakkinda.png | Hakkında (üst kısım) | Komut Paleti → "Hakkında", imza satırları kesildi |
| exe_paneli.png, exe_paneli_alt.png | EXE'ye Dönüştür paneli (üst / kaydırılmış alt kısım) | Örnek kodlar `C:\Kodlarım` içinde (kişisel yol görünmesin), Komut Paleti → "EXE'ye", ad "Sayı Tahmin Oyunu", Kaynak koduna bakılabilsin işaretli; diyalog kırpıldı |
| exe_terminali.png | EXE'nin TürKod terminal penceresi | Panelden yapılan EXE çalıştırıldı, 7 yazıldı; boş orta kısım kesildi. Pencereyi `MoveWindow` ile taşıma: başlık çubuğu açık renge döner |
| kodi_sohbetler.png | Kodi balonunda Sohbetler paneli | Kodi açıldı, Sohbetler düğmesi; tek kayıtlı sohbet ("Döngü nedir?") |
| tarayici_kodi.png | Tarayıcı sekmesinde GitHub sayfası ve Kodi | "Google'da YusufX-sys turkod-ide github ara ve depoya tıkla"; adres çubuğundan sayfa altına kırpıldı |
| kurulum_rehberi.png | Kurulum rehberi (Groq giriş sayfası + adımlar) | Tarayıcıdaki anahtar düğmesi; giriş yapılmadan, kişisel bilgi görünmeden |

`menuler_1.png`'nin sağ paneli (Çalıştır menüsü) 2026-11-03'te yeniden çekildi: menü açılıp
(383, 20)-(757, 716) bölgesi kırpıldı ve eski panelin yerine (x=860) yapıştırıldı.

### 2026-11-05: yeni arayüzle toplu çekim

Arayüz yenilendi (üst satırda "Komut ara…" ve panel düğmeleri, yeni araç çubuğu, sol şeritte
Ara ve Kitap, Gezgin'de proje adı ve dosya simgeleri, ortak panel başlıkları, durum rozeti).
Şu 24 görüntü yeniden çekildi: genel_ekran, ai_paneli, arayuz_turu, menu_dosya, menuler_1,
menuler_2, komut_paleti, gezgin_sag_tik, bolunmus_gorunum, bul_degistir, editor_hata, sorunlar,
tamamlama, akilli_duzelt, hata_ayiklayici, bildirim, eklentiler, kabuk, klavye_kisayollari,
kod_arama, hakkinda, ayarlar_genel, arac_cubugu, karsilama.

- Örnek proje "Kodlarım" klasörü: `resimler/`, `kare_ciz.trpy`, `notlar.md`, `selam.trpy`,
  `tahmin_oyunu.trpy` (eski görüntüdeki kodun aynısı). Profilde `son_dosyalar` karşılama ekranı
  için `C:\Kodlarım` içindeki iki dosyayı gösterir.
- Menü ve diyalog sınırları elle değil otomatik bulundu: menüler, menüsüz ekranla farkın
  sınırından (`ImageChops.difference(...).getbbox()`); diyaloglar, içlerinden bir noktadan
  `ImageDraw.floodfill` ile. `menuler_1` / `menuler_2` menüler yan yana yapıştırılarak kuruldu.
- `kabuk.png` için terminal, ayar dosyasındaki `panel_duzeni.terminal_yukseklik` 440 yapılarak
  büyütüldü (fareyle sürüklemek otomasyonda tutmuyor).
- Yeniden çekilmeyenler (içerikleri arayüz değişikliğinden etkilenmedi; kullanıcının gerçek AI ve
  EXE kurulumunu gösteriyorlar): ayarlar_ai_gorevler, ayarlar_ai_modeller, yerel_ai, exe_paneli,
  exe_paneli_alt, exe_terminali, kaplumbaga_penceresi.
- **Derleme uyarısı:** Profile derlemesini program açıkken yapma; açık program simge yazı tipini
  kilitler ve Flutter onu sessizce güncellemez (yeni simgeler boş kare çıkar). Koda yeni simge
  eklendiyse derlemeden önce `turkod_flutter\.dart_tool\flutter_build` klasörünü sil.
