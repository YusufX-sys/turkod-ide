"""Kitabın "TürKod IDE tam kılavuzu" bölümünün içeriği.

Program değişince burayı güncelleyip `python tools/kitap/kilavuz_ekle.py`
çalıştırın (ayrıntılar: belgeler/KITAP_BAKIM.md).

Dil: kitabın geri kalanı gibi çocuğa "sen" diye, sıcak ve benzetmeli konuşur;
Kodi konuşma balonları ve Mini Görev kutuları kullanılır. Kuru, resmî kullanım
kılavuzu dili kullanmayın. "(Büyükler için)" sayfalarda bile ton samimidir.

Her sayfa: (başlık, alt başlık, [bloklar]). Blok türleri (kitap_araclari.Sayfa):
  ("paragraf", metin)                      **kalın**, `kod` biçimi kullanılabilir
  ("baslik", metin)                        mor ara başlık
  ("maddeler", [metin, ...])
  ("tablo", [başlıklar], [[hücreler]], [sütun oranları])
  ("kutu", "gorev" | "bilgi" | "ipucu" | "dikkat", metin)
  ("kod", "dosya.trpy", [satırlar])        koyu kod kutusu
  ("terminal", [satırlar])                 terminal çıktısı kutusu
  ("resim", "dosya.png", "alt yazı", en_fazla_yükseklik[, genişlik])   goruntuler/ içinden
  ("kodi", metin)                          Kodi robotu ve konuşma balonu
Bir sayfa taşarsa betik hangi sayfanın taştığını söyler; içeriği bölün.
Sürüm bilgisi: TürKod IDE 3.2.0 kaynak koduna göre yazıldı (2026-11-03: EXE'ye Dönüştür, sekme başına terminal).
"""

BOLUM_NO = 21
BOLUM_ADI = "TürKod IDE tam kılavuzu"

SAYFALAR = [
    # ------------------------------------------------------------------ 1
    ("TürKod IDE tam kılavuzu", "Haydi programın her köşesini birlikte keşfedelim!", [
        ("paragraf", "Bölüm 4'te IDE'yi kuş bakışı gezmiştik. Şimdi daha yakından bakma zamanı! Bu bölümde "
                     "programdaki **her düğmeyi, her menüyü, her gizli köşeyi** tek tek tanıyacağız. Hepsini bir "
                     "oturuşta okumana gerek yok: bir düğmeyi merak ettiğinde buraya dön. Resimlerin hepsi "
                     "programın gerçek ekranından alındı."),
        ("resim", "genel_ekran.png", "TürKod IDE çalışırken: solda Gezgin, ortada editör ve terminal, sağda AI Asistan",
         330),
        ("paragraf", "Resimde tahmin oyunu çalışıyor. Program terminalden \"Tahminin:\" diye soruyor, biz de en "
                     "alttaki satıra cevabımızı yazıyoruz. Tıpkı bilgisayarla sohbet etmek gibi!"),
        ("kodi", "Ben de ilk açtığımda biraz kaybolmuştum. Merak etme, sayfa sayfa gezeceğiz. Hazır mısın?"),
    ]),
    # ------------------------------------------------------------------ 1b
    ("Ekranın bölümleri", "Her bölgenin bir görevi var.", [
        ("paragraf", "TürKod'un ekranı bir okul sırası gibi düzenlidir: defterin ortada, çantan solda, "
                     "yardımcı arkadaşın sağda. İşte bölgeler:"),
        ("tablo", ["Bölge", "Nerede?", "Ne işe yarar?"], [
            ["Menü çubuğu", "En üstte", "Komutlar (Dosya, Düzenle ...), \"Komut ara…\" kutusu ve panel düğmeleri"],
            ["Aktivite çubuğu", "En solda, ince şerit", "Gezgin, Ara, Eklentiler, Kitap, Kabuk ve Ayarlar düğmeleri"],
            ["Yan panel", "Solda", "Dosyaların ya da eklentiler"],
            ["Araç çubuğu", "Editörün üstünde", "En çok kullanılan komutlar, tek tıkla"],
            ["Sekmeler", "Editörün üstünde", "Açık dosyaların adları"],
            ["Editör", "Ortada", "Kodu yazdığın defter"],
            ["Terminal", "Editörün altında", "Programın konuştuğu, senin cevap verdiğin yer"],
            ["AI Asistan", "Sağda", "Yapay zekâ yardımcın"],
            ["Durum çubuğu", "En altta", "Programın durumu (Hazır, çalışıyor ...), satır, sütun, dosya adı ve \"kodum doğru mu?\" bilgisi"],
        ], [1.1, 1.2, 2.6]),
        ("paragraf", "Panellerin kenarını fareyle tutup çekersen büyür ya da küçülür. En üst satırın sağındaki "
                     "üç küçük düğme Gezgin'i, Terminal'i ve AI Asistan'ı açıp kapatır; açık olan panelin düğmesi "
                     "mavi yanar. TürKod bu düzeni hatırlar; ertesi gün açtığında her şey bıraktığın gibi durur."),
        ("kutu", "ipucu", "**Yardım → Arayüz Turu** seni 14 adımda ekranın her köşesine götürür. Tur programı ilk "
                          "açtığında kendiliğinden başlar. Ok tuşları ya da Enter ile ilerle, Esc ile kapat."),
        ("resim", "arayuz_turu.png", "Arayüz Turu'nun 4. adımı: Çalıştır ve Durdur düğmelerini gösteriyor", 140),
    ]),
    # ------------------------------------------------------------------ 1c
    ("Ekranı kendine göre düzenle", "Panellerin yerini sen seç.", [
        ("paragraf", "Odanı nasıl sevdiğin gibi yerleştiriyorsan, TürKod'un panellerini de öyle yerleştirebilirsin. "
                     "Gezgin solda, AI Asistan sağda durmak zorunda değil! İki yolu var:"),
        ("baslik", "1. Sürükle ve bırak"),
        ("paragraf", "Bir panelin başlığını (örneğin **GEZGİN** yazısını) fareyle tut ve başka bir bölgenin üstüne "
                     "götür. Bırakacağın bölge mavi bir çerçeveyle parlar ve \"... ile yer değiştir\" yazar. "
                     "Fareyi bırakınca iki bölge yer değiştirir. Editörü de böyle yana alabilirsin."),
        ("resim", "panel_tasima.png", "Gezgin paneli editörün üstüne sürükleniyor", 170),
        ("baslik", "2. Panel düzeni menüsü"),
        ("paragraf", "En üst satırın en sağındaki küçük kareli düğmeye bas. Dört hazır düzenden birini seç: "
                     "Gezgin solda AI sağda, AI solda Gezgin sağda, ikisi de sağda ya da ikisi de solda."),
        ("resim", "panel_duzeni.png", "Panel düzeni menüsü: seçili düzenin yanında tik var", 115),
        ("kutu", "ipucu", "Karıştırdın mı? **Görünüm → Panel Düzenini Sıfırla** her şeyi ilk hâline döndürür."),
    ]),
    # ------------------------------------------------------------------ 2
    ("Açılış ve bildirimler", "Program seninle nasıl konuşur?", [
        ("baslik", "Açılış ekranı"),
        ("paragraf", "TürKod açılırken \"Program başlatılıyor...\" yazısını ve dolan bir çubuk görürsün. Bu "
                     "sırada program, kodlarını çalıştıracak gizli yardımcısını (arka ucu) uyandırır. Bir sorun "
                     "çıkarsa **Yeniden dene** ya da **Yine de aç** düğmeleri gelir. Ne olduğunu büyüklerin "
                     "`%LOCALAPPDATA%\\TurKod\\backend.log` dosyasında okuyabilir."),
        ("paragraf", "Program çalışırken bu yardımcıyla bağlantı koparsa üstte **kırmızı bir şerit** belirir. "
                     "Telaşlanma: TürKod kendi kendine yeniden bağlanmayı dener. İstersen şeritteki **Yeniden "
                     "başlat** düğmesine sen de basabilirsin."),
        ("baslik", "Bildirimler"),
        ("paragraf", "\"Kaydedildi\" gibi kısa haberler sağ altta belirip kaybolur. Kaçırdıysan sorun değil: "
                     "mesajın yanındaki **zil** düğmesi eski haberlerin hepsini saatleriyle gösterir. **Temizle** "
                     "ile listeyi boşaltırsın."),
        ("resim", "bildirim.png", "Bir bildirim: yanında zil (geçmiş) ve kapatma düğmesi", 40, 260),
        ("kodi", "Bildirimler benim sana fısıldadığım küçük notlar gibi. Bir şeyi kaydettim mi, bir şey ters "
                 "gitti mi, hep oradan söylerim!"),
    ]),
    # ------------------------------------------------------------------ 2b
    ("Karşılama ekranı", "Hiç dosya açık değilken seni neler bekliyor?", [
        ("paragraf", "Bütün sekmeleri kapattığında editörün yerinde boş bir sayfa durmaz: TürKod seni bir "
                     "**karşılama ekranıyla** selamlar. Burası bir oyunun ana menüsü gibidir; nereden "
                     "başlayacağını sen seçersin."),
        ("resim", "karsilama.png", "Karşılama ekranı: başlangıç kartları ve son dosyalar", 300),
        ("maddeler", [
            "**Başla** kartları: Yeni Dosya, Dosya Aç, Klasör Aç, Kitabı Oku, Arayüz Turu ve Komut Paleti. "
                "Bir karta tıklaman yeter. Farenin okunu kartın üstünde beklet, kısayolunu da gösterir.",
            "**Son Dosyalar**: en son açtığın dosyalar. Adına tıklayınca kaldığın yerden devam edersin.",
            "**Günün İpucu**: her gün yeni bir püf noktası öğretir.",
        ]),
        ("kodi", "Ben her sabah önce Günün İpucu'na bakıyorum. Dün Ctrl+Alt+Aşağı ile iki satıra birden "
                 "yazmayı öğrendim!"),
    ]),
    # ------------------------------------------------------------------ 2c
    ("Aktivite çubuğu", "En soldaki ince şerit.", [
        ("paragraf", "Ekranın en solundaki ince şeritte yedi düğme var. Bunlar odalar arasındaki kapılar gibi: "
                     "hangisine basarsan o odaya geçersin. Seçili düğmenin solunda mavi bir çizgi yanar."),
        ("tablo", ["Düğme", "Ne yapar?"], [
            ["Gezgin (dosyalar)", "Dosya panelini açar. Panel zaten açıksa tekrar basınca kapanır."],
            ["Ara (büyüteç)", "Dosyalarda Ara penceresini açar: bir kelimeyi bütün dosyalarında bulur."],
            ["Eklenti Özellikleri", "Yerel yapay zekâ modelleri ve eklentiler paneli. Üstündeki küçük sayı, kaç "
                                    "eklentinin açık olduğunu söyler."],
            ["Kitap", "Bu kitabı programın içinde, yeni bir sekmede açar."],
            ["Kodi (robot yüzü)", "Beni çağırır! Bir daha basınca kayarak giderim."],
            ["TürKod Kabuğu (alttaki)", "Komut satırını ve dersleri açar. Kabuk sayfalarında ayrıntısı var."],
            ["Ayarlar (alttaki dişli)", "Ayarlar sekmesini açar."],
        ], [1.3, 3]),
        ("resim", "eklentiler.png", "Aktivite çubuğundaki yapboz düğmesine basınca açılan Eklenti Özellikleri paneli",
         272),
        ("kutu", "gorev", "Şeritteki düğmelere sırayla bas. Hangileri sol paneli değiştiriyor, hangileri bir pencere açıyor?"),
    ]),
    # ------------------------------------------------------------------ 2d
    ("Kodi seninle!", "Kitaptaki robot arkadaşın programın içinde de var.", [
        ("paragraf", "Bu kitapta sana yol gösteren Kodi benim. Artık programın içinde de seninleyim! Sol şeritteki "
                     "**robot yüzlü düğmeye** ya da `F1`'e bas: editörün sağ alt köşesine "
                     "kayarak gelirim, el sallarım ve konuşma balonumda seni selamlarım. Yazılarım bir anda değil, "
                     "**harf harf** çıkar; tıpkı karşında konuşuyormuşum gibi."),
        ("resim", "kodi_selam_dusunme.png", "Solda Kodi selam veriyor, sağda bir soru üzerine düşünüyor", 230),
        ("maddeler", [
            "Sorunu balonun altındaki kutuya yaz ve `Enter`'a bas.",
            "Cevabını hazırlarken düşünürüm: bir elim öbür kolumun dirseğini tutar, öbür elim çenemde. "
                "\"Düşünüyorum...\" ya da \"Hemen bakıyorum...\" derim. Cevabı yazarken ağzım oynar.",
            "Yazmamı beklemek istemezsen balona tıkla: cevabın tamamı hemen görünür.",
            "**Ampul düğmesi** düşünmeyi açar ya da kapatır. Açıkken daha uzun düşünür, kapalıyken hemen cevap veririm.",
            "**Yeni sohbet** düğmesi yeni bir sohbet açar, **X** düğmesi ya da sol şeritteki düğme beni gönderir. "
                "Beni her çağırışında yeni bir sohbetle, \"Merhaba, ben Kodi!\" diye gelirim.",
            "Beni başka bir yere mi koymak istiyorsun? **Üstüme bas ve sürükle.** Yerimi unutmam; "
                "**çift tıklarsan** eski köşeme dönerim. Pencerenin dışına sürüklersen masaüstüne çıkarım!",
            "Balonum çok mu yer kaplıyor? Köşesindeki **çizgili tutamacı** sürükleyip onu daraltıver ya da "
                "büyütüver; sohbet sığmazsa yanda kaydırma çubuğu çıkar. Tutamaca çift tıklarsan eski boyutuna döner.",
        ]),
    ]),
    # ------------------------------------------------------------------ 2e
    ("Kodi'ye neler sorabilirsin?", "Programın her köşesini biliyorum!", [
        ("paragraf", "Bana programla ilgili her şeyi sorabilirsin: bir menünün nerede olduğunu, bir düğmenin ne işe "
                     "yaradığını, kodundaki bir hatayı, bu kitabı ya da TürKod'u kimin yaptığını. Kod örneği "
                     "verirsem onu hep TürKod ile yazarım."),
        ("resim", "kodi_cevap.png", "Kodi, programı EXE yapmanın yolunu anlatıyor", 250),
        ("maddeler", [
            "\"Programımı nasıl EXE yaparım?\" ya da \"TürKod'u kim yaptı?\"",
            "**Hatamı bulur musun?** Terminaldeki hatayı ve kodunu görürüm, hangi satırda ne olduğunu söylerim.",
            "Kodundan bir parçayı seçip \"bunu açıklar mısın?\" diyebilirsin; seçtiğini görürüm.",
            "Selamdan sonra çıkan **hazır soru düğmelerine** basman da yeter.",
            "Cevabımı beklemek istemezsen gönder düğmesinin yerine gelen kırmızı **Vazgeç**'e bas.",
        ]),
        ("kutu", "bilgi", "**Büyükler için:** Kodi'nin konuştuğu yapay zekâ, Ayarlar → **Yapay Zekâ: Görevler**'deki "
                          "**Kodi (yardımcı robot)** satırından seçilir. **Otomatik** kalırsa AI Paneli sohbet "
                          "modeli kullanılır. Hiç model yoksa Kodi bunu söyler ve **Ayarları aç** düğmesini gösterir."),
    ]),
    # ------------------------------------------------------------------ 2f
    ("Kodi senin için iş yapar", "Söyle, panel açayım, kod yazayım!", [
        ("paragraf", "Ben yalnızca konuşmam, iş de yaparım! \"Terminali aç\", \"notlar.md dosyasını aç\", "
                     "\"bana 1'den 5'e sayan bir program yaz\" dersen hemen yardıma koşarım."),
        ("resim", "kodi_eylem.png", "Kodi terminali açtı, kodu yazmak için izin istiyor", 185),
        ("tablo", ["Ne isteyebilirsin?", "Ben ne yaparım?"], [
            ["Bir paneli açıp kapatmak", "Hemen yaparım: Gezgin, Eklentiler, AI Asistan, Terminal."],
            ["Bir dosyayı ya da sekmeyi açmak", "Projendeki dosyayı açarım ya da o sekmeye geçerim."],
            ["Bir satıra gitmek, bir şey aramak", "Hemen götürürüm: \"40. satıra git\", \"yazdır nerede geçiyor?\""],
            ["Kitapta bir konuyu bulmak", "Kitabı o sayfada açarım: \"kitapta döngüler nerede?\""],
            ["Temayı, yazı boyutunu değiştirmek", "Hemen yaparım: \"temayı açık yap\", \"yazıyı büyüt\"."],
            ["Kod yazmak", "Kodu **AI Asistan**'a yazdırıp sorarım: **Yeni sekmede aç** mı, **İmlece ekle** "
                           "mi? Sonra harf harf yazarım."],
            ["Çalıştırmak, kaydetmek, düzeltmek", "Önce sorarım: **İzin ver** ya da **Vazgeç**."],
        ], [1.7, 3]),
        ("paragraf", "Yaptığım her işin altına küçük bir not düşerim (**Terminal açıldı** gibi). Yazdığım "
                     "programlar balonu doldurmaz, editörüne gider. Kısa örnek kodların sağ üstündeki iki düğme "
                     "kodu yeni sekmede açar ya da imlecinin olduğu yere ekler."),
        ("kodi", "Senin kodunu senden izin almadan asla değiştirmem. Söz!"),
    ]),
    # ------------------------------------------------------------------ 2f2
    ("Kodi programı yönetir", "Menüler, eklentiler, ayarlar: hepsini bilirim!", [
        ("paragraf", "Programın **her menü komutunu**, **her eklentisini** ve **ayarlarını** yönetebilirim. "
                     "Ne istediğini söylemen yeter; düğmeyi aramana gerek kalmaz."),
        ("resim", "kodi_yonetim.png", "Kodi sekmeye geçti, EXE panelini açtı, Ayarlar'da kendi bölümünü gösterdi",
         290),
        ("tablo", ["Şöyle de", "Ben ne yaparım?"], [
            ["\"EXE panelini aç\", \"kısayolları göster\"", "O pencereyi açarım (menülerdeki her komut olur)."],
            ["\"Kod Parçacıklarını etkinleştir\"", "Eklentiyi açarım; \"karalama defterini aç\" dersen penceresini de."],
            ["\"mini haritayı kapat\", \"temayı açık yap\"", "Ayarı hemen değiştiririm."],
            ["\"Ayarlarda Kodi bölümünü aç\"", "Ayarlar'ı açıp o bölüme götürürüm."],
            ["\"AI Paneli sohbet modelini değiştir\"", "Görevlere yapay zekâ modeli atarım."],
        ], [1.9, 2.7]),
        ("kodi", "Bir cümlede birkaç iş isteyebilirsin (\"tarayıcıyı aç ve projenin GitHub sayfasına git\" "
                 "gibi); hepsini sırayla yaparım. Açtığım sayfaya bakıp işime kendim devam ederim. "
                 "Bana henüz yapay zekâ bağlanmamışsa yalnızca \"terminali aç\" gibi kısa işleri yaparım."),
    ]),
    # ------------------------------------------------------------------ 2f3
    ("Kodi'nin yetkileri", "Neleri yapabileceğime sen karar verirsin. (Büyüklerle birlikte)", [
        ("paragraf", "Ayarlar → **Kodi** bölümünde benim neleri yapabileceğimi seçersin. Bu bölümü yalnızca "
                     "sen değiştirebilirsin; ben dokunamam, değiştirmemi istesen bile."),
        ("resim", "ayarlar_kodi.png", "Ayarlar → Kodi: Kodi'nin yetkileri", 215),
        ("maddeler", [
            "**Ayarları değiştirebilsin:** tema, yazı boyutu, editör seçenekleri, yapay zekâ modelleri.",
            "**Eklentileri açıp kapatabilsin:** Kod Parçacıkları, Odak Zamanlayıcı ...",
            "**Program komutlarını çalıştırabilsin:** menülerdeki her komut. Çalıştırmak, kaydetmek gibi "
                "işlerden önce yine sana sorarım.",
            "**Her işten önce izin istesin:** panel açmak gibi küçük işlerde bile önce \"yapayım mı?\" derim.",
        ]),
        ("kutu", "bilgi", "**Büyükler için:** Bir yetki kapalıyken o işi isterseniz Kodi yapamayacağını ve "
                          "Ayarlar → Kodi'den açılabileceğini söyler. API anahtarlarını, kısayolları ve "
                          "Kodi'nin kendi yetkilerini Kodi hiçbir zaman değiştiremez."),
    ]),
    # ------------------------------------------------------------------ 2f4
    ("Sohbetlerin", "Eski sohbetlerine dön, yenisini aç.", [
        ("paragraf", "Beni her çağırışında yeni bir sohbet açılır, \"Merhaba, ben Kodi!\" diye gelirim. Eski "
                     "sohbetlerimiz kaybolmaz: hepsi saklanır, program kapanıp açılsa da durur. Masaüstündeyken "
                     "konuştuklarımız da saklanır."),
        ("resim", "kodi_sohbetler.png", "Sohbetler paneli: Yeni sohbet düğmesi ve kayıtlı sohbetler", 230),
        ("maddeler", [
            "Balonumdaki **Sohbetler** düğmesi (iki konuşma balonu) bütün sohbetlerimizi listeler: en yenisi "
                "en üstte, her birinin tarihi ve kaç mesaj olduğu yazar.",
            "Bir sohbete tıklarsan o sohbet açılır, kaldığımız yerden sürdürürüz.",
            "**Yeni sohbet** düğmesine basınca \"Merhaba, ben Kodi!\" diye yeni bir sohbete başlarım; eskisi "
                "listede durur. Çöp kutusu düğmesi bir sohbeti siler.",
        ]),
        ("kutu", "bilgi", "**Büyükler için:** Ayarlar → Kodi'de \"Sohbet kaydedilsin\" kapatılırsa yeni sohbetler "
                          "saklanmaz; **Bütün sohbetleri sil** düğmesi kayıtlı sohbetlerin hepsini siler."),
    ]),
    # ------------------------------------------------------------------ 2f5
    ("Kodi seni hatırlar", "Adını, sevdiklerini unutmam!", [
        ("paragraf", "Bana kendinden bir şey söylersen ya da \"**bunu hatırla**\" dersen not alırım: adını, "
                     "en sevdiğin rengi, hangi oyunu yazmak istediğini ... Balonumda \"Hatırladım: ...\" diye "
                     "küçük bir not görürsün. Bir şeyi unutmamı istersen \"**şunu unut**\" demen yeter."),
        ("tablo", ["Şöyle de", "Ben ne yaparım?"], [
            ["\"Adım Ece, bunu hatırla\"", "Not alırım; sonraki sohbetlerde de bilirim."],
            ["\"En sevdiğim rengi unut\"", "O notu silerim."],
            ["\"Benim en sevdiğim renk neydi?\"", "Hafızama bakıp söylerim."],
        ], [1.9, 2.7]),
        ("kutu", "dikkat", "Şifreni, adresini, telefon numaranı ya da e-postanı bana söyleme. Söylesen de "
                           "hatırlamam; bunları kimseyle paylaşmamalısın."),
        ("kutu", "bilgi", "**Büyükler için:** Ayarlar → **Kodi** bölümünde \"Sohbet kaydedilsin\" ve \"Kodi beni "
                          "hatırlasın\" seçenekleri ve **Hafızayı yönet…** (notları tek tek ya da hepsini silmek) "
                          "düğmesi var. Kodi bu ayarları kendisi değiştiremez. Sohbet ve notlar "
                          "yalnızca bu bilgisayarda (`kullanıcı klasörü\\.turkod`) saklanır."),
    ]),
    # ------------------------------------------------------------------ 2f6
    ("Kodi ekranını görür", "İstersen ne gördüğünü bana da gösterebilirsin.", [
        ("paragraf", "Bana bir şey sorarken ekranında ne olduğunu da görmemi ister misin? Balonumdaki **kamera** "
                     "düğmesine bas: her basışta sırayla şunlardan birine geçer."),
        ("tablo", ["Düğme", "Ne olur?"], [
            ["Üstü çizili kamera", "Görüntü gönderilmez (her zaman böyle başlar)."],
            ["Pencere", "Mesajınla birlikte TürKod penceresinin görüntüsü de gider."],
            ["Ekran", "Bütün ekranın görüntüsü gider."],
        ], [1.6, 3]),
        ("paragraf", "Görüntü gidince mesajının altında \"Görüntü de gönderildi\" yazar. Bağlı yapay zekâ "
                     "görüntü göremiyorsa \"seçili model görüntü göremiyor\" yazar; o zaman yalnızca yazdıklarını "
                     "anlarım."),
        ("kutu", "dikkat", "Ekranında özel bir şey varken (bir mesaj, şifre, kişisel bilgi) görüntü göndermeyi "
                           "kapat. Görüntü, yapay zekâ sağlayıcısına gider."),
        ("kutu", "bilgi", "**Büyükler için:** Aynı ayar Ayarlar → Kodi → \"Mesajla birlikte görüntü gönder\" "
                          "satırında da var. Görüntü göremeyen bir modelle (ör. gpt-oss) çalışmaz; görsel destekleyen "
                          "bir model gerekir (ör. GPT-4o mini, Gemini, Claude)."),
    ]),
    # ------------------------------------------------------------------ 2f7
    ("TürKod'daki tarayıcı", "İnterneti TürKod'dan çıkmadan gez.", [
        ("paragraf", "Sol şeritteki **dünya** düğmesi (ya da **Görünüm → Tarayıcı**) TürKod'un içinde bir tarayıcı "
                     "sekmesi açar. Sayfalar gerçek bir tarayıcıdaki gibi çalışır. Üstte geri, ileri, "
                     "yenile ve Google düğmeleri ile adres çubuğu var: bir adres yaz (ör. `wikipedia.org`) ya da "
                     "aramak istediğini yaz, `Enter`'a bas."),
        ("resim", "tarayici_kodi.png", "Kodi Google'da aradı, sonuçları okudu ve GitHub sayfasına tıkladı", 260),
        ("tablo", ["Bana şöyle de", "Ben ne yaparım?"], [
            ["\"google'ı aç\", \"youtube.com'u aç\"", "Siteyi hemen açarım."],
            ["\"Google'da kaplumbağa çizimi ara\"", "Google'da ararım."],
            ["\"... ara ve ilk sonuca tıkla\"", "Arar, sonucu okur, kendi imlecimle tıklarım; açılan sayfaya bakıp işime devam ederim."],
            ["\"Arama kutusuna merhaba yaz\"", "Kutuya yazarım; istersen gönderirim."],
            ["\"Aşağı kaydır\", \"geri git\"", "Sayfayı kaydırır, geri ya da ileri giderim."],
        ], [2.0, 2.6]),
        ("kodi", "Tıklarken mor imlecimi sayfada görürsün. Şifre kutularına asla yazmam; satın alma, ödeme ya da "
                 "silme gibi bir düğmeye basmadan önce de sana sorarım."),
        ("kutu", "ipucu", "Sayfadayken de `Ctrl+Shift+P`, `F1` gibi TürKod kısayolları çalışır. Sekmeyi "
                          "kapatınca tarayıcı tamamen kapanır."),
    ]),
    # ------------------------------------------------------------------ 2f8
    ("Kurulum rehberi", "Yapay zekâ yoksa Kodi seni adım adım götürür.", [
        ("paragraf", "Bana henüz bir yapay zekâ bağlanmamışsa balonumda **Kurulum rehberi** düğmesi çıkar. Ona "
                     "basınca tarayıcıda Groq'un anahtar sayfası açılır, yanında da üç adımlı rehber durur."),
        ("resim", "kurulum_rehberi.png", "Kurulum rehberi: solda Groq'un sayfası, sağda adımlar", 255),
        ("maddeler", [
            "**1.** Groq'a giriş yap ya da hesap aç (bir büyüğünle).",
            "**2.** \"Create API Key\" düğmesine bas; ben o düğmeyi mor imlecimle gösteririm. Çıkan anahtarı kopyala.",
            "**3.** Anahtarı rehberdeki kutuya yapıştır ve **Bağla**'ya bas. Ben modeli seçer, her şeyi ayarlarım.",
        ]),
        ("kutu", "ipucu", "Rehberi istediğin zaman tarayıcının sağ üstündeki **anahtar** düğmesinden ya da "
                          "Ayarlar → Kodi → **API kurulum rehberi**'nden açabilirsin. Anahtar yanlışsa ayarlarına "
                          "hiç dokunmam, ne olduğunu söylerim."),
    ]),
    # ------------------------------------------------------------------ 2g
    ("Kodi ile sesli konuş", "Sen söyle, ben dinleyeyim; ben söyleyeyim, sen dinle!", [
        ("paragraf", "Yazmaktan yoruldun mu? Benimle **konuşabilirsin** de! Balonumun altındaki **mikrofon** "
                     "düğmesine bas ve sorunu söyle. Sen susunca anlarım, söylediğini yazıya çeviririm ve "
                     "cevaplarım. Dinlerken gözlerim kocaman açılır, kulağımın yanında ses dalgaları çıkar."),
        ("resim", "kodi_sesli.png", "Kodi cevabını sesli okuyor: alttaki şeritte \"Konuşuyorum...\" yazıyor", 300),
        ("maddeler", [
            "**Hoparlör düğmesi** (sesli cevap) açıkken cevaplarımı sana sesli okurum. Şeritteki kare düğme beni susturur.",
            "**Canlı sohbet** düğmesi (konuşan kişi): sen konuşursun, ben cevaplarım, sonra yine dinlerim; tıpkı "
                "telefonda konuşur gibi. Üç kez üst üste sessiz kalırsan dinlemeyi bırakırım.",
            "Kodları sesli okumam, \"Kodu balona yazdım\" derim; onlara balondan bakarsın.",
        ]),
        ("kutu", "bilgi", "**Büyükler için:** Kodi'nin kulağı Ayarlar'daki bir **Groq** (ücretsiz) ya da **OpenAI** "
                          "anahtarıyla çalışır: söylenen ses, yazıya çevrilmek için o sağlayıcıya gönderilir. Anahtar "
                          "yoksa Kodi bunu söyler ve Ayarları aç düğmesini gösterir. Kodi'nin sesi Windows'un Türkçe "
                          "konuşma sesidir, internet istemez. Mikrofonun Windows'ta açık olmalı."),
    ]),
    # ------------------------------------------------------------------ 2h
    ("Kodi masaüstünde", "TürKod'un dışına da çıkabilirim!", [
        ("paragraf", "Beni TürKod penceresinin **dışına sürükle**: kenardan taştığımda \"Bırak, masaüstüne "
                     "çıkayım!\" derim. Bırakınca hemen kendi küçük penceremle masaüstüne çıkarım. "
                     "Balonumdaki **Masaüstüne çık** düğmesi (kutudan çıkan ok) de aynı işi yapar."),
        ("resim", "kodi_masaustu.png", "Kodi TürKod penceresinin kenarından taşıyor: \"Bırak, masaüstüne çıkayım!\"",
         250),
        ("maddeler", [
            "Masaüstünde de aynı Kodi'yim: aynı balon, aynı düğmeler, sesli ve canlı sohbet. Dosya açmak, kod "
                "yazmak, kitabı açmak gibi işleri yine TürKod'da yaparım.",
            "Hep öteki pencerelerin üstünde dururum. Benimle balonum arasındaki boşluğa tıklarsan alttaki "
                "pencereye tıklamış olursun.",
            "Taşımak için üstüme bas ve sürükle; nereye bırakırsan orada dururum.",
            "Geri dönmem için **TürKod'a dön** düğmesine bas ya da üstüme çift tıkla. Sohbetimiz kaybolmaz!",
        ]),
        ("kodi", "Bir oyun yazarken ya da internette bir şey okurken beni yanına al. Takıldığın an buradayım!"),
    ]),
    # ------------------------------------------------------------------ 3
    ("Dosya menüsü", "Kodlarını açmak, saklamak, kapatmak.", [
        ("paragraf", "Menüler, komutların dizildiği raflar gibidir. Bir menünün adına tıklarsan raf açılır. "
                     "Her komutun sağında gri renkle **kısayolu** yazar: menüyü hiç açmadan aynı işi yapan tuş "
                     "birleşimi. Menüler soldan sağa şöyle: Dosya, Düzenle, Görünüm, Çalıştır, Araçlar, Öğren, "
                     "Yardım, Güncelleştirmeler."),
        ("tablo", ["Komut", "Kısayol", "Ne yapar?"], [
            ["Yeni Sekme", "`Ctrl+T`", "\"Adsız-1.trpy\" adında boş bir sayfa açar."],
            ["Dosya Aç", "`Ctrl+O`", "Bilgisayarından bir dosya seçip açar."],
            ["Son Dosyalar", "`Ctrl+Shift+O`", "En son açtığın dosyaların listesi. Birine tıkla, açılsın."],
            ["Klasör Aç", "", "Bir klasörü proje klasörün yapar; içindekiler Gezgin'de görünür."],
            ["Kaydet", "`Ctrl+S`", "Yazdıklarını saklar. İlk kez kaydederken dosyaya ad verirsin."],
            ["Tümünü Kaydet", "`Ctrl+Shift+S`", "Değişen bütün sekmeleri birden saklar."],
            ["Farklı Kaydet", "", "Aynı kodu başka bir adla ya da başka bir yere saklar."],
            ["Sekmeyi Kapat", "`Ctrl+W`", "Sekmeyi kapatır. Kaydetmediysen önce sorar."],
        ], [1.2, 1.1, 2.6]),
        ("resim", "menu_dosya.png", "Açık Dosya menüsü: komutlar solda, kısayolları sağda", 140),
        ("kutu", "ipucu", "Ayarlar'da **Otomatik Kaydetme**'yi açarsan TürKod dosyalarını birkaç saniyede bir "
                          "(5-600 saniye arası) kendiliğinden kaydeder. Emeğin asla kaybolmaz!"),
    ]),
    # ------------------------------------------------------------------ 4
    ("Düzenle menüsü", "Yazdığın kodu değiştirmenin kısa yolları.", [
        ("paragraf", "Bu menü, kalemtıraşın ve silginin bulunduğu kalem kutun gibidir:"),
        ("tablo", ["Komut", "Kısayol", "Ne yapar?"], [
            ["Geri Al / Yinele", "`Ctrl+Z` / `Ctrl+Y`", "Son yaptığını geri alır / geri getirir."],
            ["Kes / Kopyala / Yapıştır", "`Ctrl+X` `C` `V`", "Seçtiğini panoya alır ve başka yere koyar."],
            ["Tümünü Seç", "`Ctrl+A`", "Bütün kodu seçer."],
            ["Satıra Git…", "`Ctrl+G`", "Numarasını yazdığın satıra ışınlar."],
            ["Bul", "`Ctrl+F`", "Kodun içinde arama kutusunu açar."],
            ["Bul / Değiştir", "`Ctrl+H`", "Bulduğunu başka bir şeyle değiştirir."],
            ["Dosyalarda Ara", "`Ctrl+Shift+F`", "Proje klasöründeki bütün dosyalarda arar."],
            ["Tanıma Git", "`F12`", "Üstünde durduğun adın nerede tanımlandığını gösterir, başka dosyada bile."],
            ["Alta / Üste İmleç Ekle", "`Ctrl+Alt+↓` / `↑`", "Bir satır altına ya da üstüne ikinci imleç koyar."],
            ["Sonraki Eşleşmeyi Seçime Ekle", "`Ctrl+D`", "Kelimeyi seçer; her basışta bir sonrakini de ekler."],
            ["Tüm Eşleşmeleri Seç", "`Ctrl+Shift+L`", "Kelimenin her yerini birden seçer."],
            ["Adı Değiştir…", "`F2`", "Bir adı kodun her yerinde birden değiştirir."],
            ["Kodu Biçimlendir", "`Shift+Alt+F`", "Girintileri ve boşlukları toparlar."],
            ["Yorum Aç/Kapat", "`Ctrl+/`", "Seçili satırların başına # koyar ya da kaldırır."],
            ["Satırı Çoğalt", "`Ctrl+Shift+D`", "Satırın bir kopyasını hemen altına ekler."],
            ["Satırı Yukarı / Aşağı Taşı", "`Alt+↑` / `Alt+↓`", "Satırı bir üste ya da alta kaydırır."],
            ["AI Önerisi İste (hayalet kod)", "`Ctrl+Shift+Space`", "Yapay zekâdan hemen öneri ister."],
        ], [1.45, 1.15, 2.4]),
        ("kutu", "bilgi", "**Adı Değiştir** çok akıllıdır: yazıların ve yorumların içine dokunmaz. Bir "
                          "fonksiyonun içindeki kutunun adını değiştirirsen yalnızca o fonksiyonda değişir."),
    ]),
    # ------------------------------------------------------------------ 5
    ("Görünüm menüsü", "Ekranda neyin görüneceğine sen karar ver.", [
        ("tablo", ["Komut", "Kısayol", "Ne yapar?"], [
            ["Sorunlar", "`Ctrl+Shift+M`", "Koddaki hataların listesi. Birine tıkla, o satıra git."],
            ["Gezgin Aç/Kapat", "", "Soldaki paneli gösterir ya da saklar."],
            ["AI Panelini Aç/Kapat", "","Sağdaki AI Asistan'ı gösterir ya da saklar."],
            ["Terminal Aç/Kapat", "`Ctrl+J`", "Alttaki terminali gösterir ya da saklar."],
            ["Editörü Böl (Yan Yana)", "`Ctrl+\\`", "Editörü ikiye böler; iki dosyaya aynı anda bakarsın."],
            ["Yan Panellerin Yerini Değiştir", "", "Gezgin ile AI Asistan'ın yerlerini değiştirir."],
            ["Panel Düzenini Sıfırla", "", "Panelleri ilk yerlerine geri koyar."],
            ["Sekmeyi Sola / Sağa Taşı", "`Ctrl+Shift+PageUp` / `PageDown`", "Sekmenin yerini değiştirir."],
            ["Komut Paleti", "`Ctrl+Shift+P`", "Bütün komutları adıyla arayıp çalıştırırsın."],
            ["Klavye Kısayolları…", "", "Kısayolları görür, istersen değiştirirsin."],
            ["Ayarlar", "", "Ayarlar sekmesini açar."],
            ["Eklenti Özellikleri", "`Ctrl+Shift+X`", "Eklentiler panelini açar."],
            ["Markdown Önizleme", "`Ctrl+Shift+V`", ".md not dosyasını süslü hâliyle gösterir (eklenti açıksa)."],
        ], [1.4, 1.5, 2.3]),
        ("baslik", "Komut Paleti: sihirli arama kutusu"),
        ("paragraf", "Bir komutun hangi menüde olduğunu unuttun mu? `Ctrl+Shift+P`'ye bas ve adının bir "
                     "parçasını yaz, örneğin \"kay\". Liste hemen daralır; Enter'a basınca ilk komut çalışır. "
                     "Sanki programa \"kaydet bunu!\" diye seslenmek gibi."),
        ("kutu", "ipucu", "Türk klavyesinde `Ctrl+/` yerine `Ctrl+Shift+7` ya da sayı tuşlarındaki `/` da olur. "
                          "Editörü bölmek için Görünüm menüsünü ya da Komut Paleti'ni kullan; istersen "
                          "Klavye Kısayolları'ndan kendi tuşunu ata. AltGr ile `\\` yazınca editör bölünmez, "
                          "karakter yazılır."),
    ]),
    # ------------------------------------------------------------------ 6
    ("Çalıştır menüsü", "Kodunu başlat, durdur, adım adım izle.", [
        ("tablo", ["Komut", "Kısayol", "Ne yapar?"], [
            ["Çalıştır", "`Ctrl+R`", "Kodunu çalıştırır, seni terminale götürür."],
            ["Durdur", "", "Çalışan programı durdurur."],
            ["Kesme Noktası Aç/Kapat", "`F9`", "Satıra kırmızı bir durak koyar ya da kaldırır."],
            ["Koşullu Kesme Noktası…", "`Shift+F9`", "Yalnızca bir şart doğruysa duran durak."],
            ["Çalıştırma Argümanları…", "", "Programa başlarken vereceğin bilgileri yazarsın."],
            ["EXE'ye Dönüştür…", "", "Programını her bilgisayarda çalışan bir EXE dosyası yapar."],
            ["EXE'nin Kaynak Kodunu Aç…", "", "Bir TürKod EXE'sinin kodunu yeni sekmede açar."],
            ["Tüm Kesme Noktalarını Kaldır", "", "Sekmedeki bütün durakları siler."],
            ["Hata Ayıklamayı Başlat / Devam", "`F5`", "Adım adım izlemeyi başlatır; duraktaysa devam eder."],
            ["Adım At", "`F10`", "Bir satır ilerler (fonksiyonun içine girmeden)."],
            ["İçine Gir", "`F11`", "Satırdaki fonksiyonun içine girer."],
            ["Dışına Çık", "`Shift+F11`", "Bulunduğun fonksiyondan çıkana kadar çalışır."],
            ["İmlece Kadar Çalıştır", "`Ctrl+F10`", "İmlecin durduğu satıra kadar gidip bekler."],
            ["Devam", "", "Bir sonraki durağa kadar çalışır."],
            ["Duraklat", "`F6`", "Programı olduğu yerde dondurur."],
            ["Hata Ayıklamayı Durdur", "`Shift+F5`", "Adım adım izlemeyi bitirir."],
        ], [1.5, 1.0, 2.5]),
        ("paragraf", "Program bitmeden Çalıştır'a yine basarsan eskisi kapanır, yenisi baştan başlar. Dosyanı "
                     "kaydettiysen program kendi klasöründe çalışır; böylece aynı klasördeki resimleri ve "
                     "dosyaları bulabilir."),
        ("kodi", "Kesme noktaları, hata ayıklayıcı... Kulağa karışık geliyor, değil mi? İleride kendi sayfasında "
                 "oyun gibi anlatacağım!"),
    ]),
    # ------------------------------------------------------------------ 7
    ("Araçlar, Öğren, Yardım", "Yardımcı aletler ve öğrenme köşesi.", [
        ("baslik", "Araçlar"),
        ("tablo", ["Komut", "Ne yapar?"], [
            ["TürKod ⇄ Python Çevir", "Dosyanın tamamını öbür dile çevirip yeni sekmede açar. Hangi dilde "
                                      "yazdığını kendisi anlar."],
            ["Düzelt", "Akıllı Düzelt'i çağırır: hataları bulur ve düzeltir."],
            ["Kod İstatistikleri", "Kaç satır, kaç yorum, kaç fonksiyon yazdığını sayar."],
            ["Yapılacaklar Listesi", "Yorumlara bıraktığın YAPILACAK notlarını toplar; Git ile oraya gidersin."],
            ["Kod Arama Çevirici", "Bir Python kelimesinin (print, def ...) TürKod karşılığını bulur."],
            ["TürKod Kabuğu… `Ctrl+Shift+K`", "Komut satırını programın içinde ya da ayrı pencerede açar."],
            ["Yerel AI Modelleri…", "Bilgisayarında çalışan ücretsiz yapay zekâları yönetir."],
            ["Kod Parçacıkları… `Ctrl+Shift+J`", "Hazır kod kalıplarını ekler (Parçacıklar eklentisi açıksa)."],
        ], [1.6, 3]),
        ("baslik", "Öğren"),
        ("maddeler", [
            "**TürKod ile Kodlama Macerası (Kitap)**: Şu an okuduğun bu kitabı yeni bir sekmede açar. Merhaba!",
            "**Dokümantasyon Sitesi**: yusufx-sys.github.io/turkod-site adresini açar.",
        ]),
        ("baslik", "Yardım ve Güncelleştirmeler"),
        ("maddeler", [
            "**Arayüz Turu**: ekranı adım adım tanıtan turu başlatır.",
            "**Kodi ile Konuş** (`F1`): beni çağırır ya da gönderir.",
            "**GitHub Sayfası** ve **Hata Bildir / Öneri Gönder**: programın internet sayfasını açar.",
            "**İletişim**: TürKod'u yapan kişiye e-posta yazmak için taslak hazırlar.",
            "**Lisanslar** ve **Hakkında / İmza**: lisans, sürüm ve dijital imza bilgisi.",
            "**Güncelleştirmeleri Denetle**: TürKod'un yeni sürümü çıkmış mı diye bakar.",
        ]),
    ]),
    # ------------------------------------------------------------------ 7b
    ("Menüler resimlerle", "Raflar açılınca böyle görünür.", [
        ("paragraf", "Bir menünün adına tıkla, raf aşağı açılsın. Bir komuta tıklarsan çalışır; vazgeçersen "
                     "`Esc`'e bas. Sağdaki gri yazılar, kısayolları hatırlaman için orada."),
        ("resim", "menuler_1.png", "Düzenle, Görünüm ve Çalıştır menüleri", 360),
        ("resim", "menuler_2.png", "Araçlar, Öğren, Güncelleştirmeler ve Yardım menüleri", 150),
        ("kutu", "gorev", "Menüleri tek tek aç ve bu resimlerle karşılaştır. Hiçbir şeyi bozmazsın, merak etme!"),
    ]),
    # ------------------------------------------------------------------ 8
    ("Araç çubuğu", "Tek tıkla iş yapan sihirli düğmeler.", [
        ("paragraf", "Editörün hemen üstünde, ortada renkli düğmeler durur. Düğmeler üç kutuya ayrılmıştır; "
                     "her rengin bir anlamı var: yeşil başlatır, kırmızı durdurur, turuncu hata avlar."),
        ("resim", "arac_cubugu.png", "Araç çubuğu: dosya, çalıştırma ve araç kutuları", 40),
        ("tablo", ["Grup", "Düğmeler"], [
            ["Dosya", "Dosya Aç, Klasör Aç, Kaydet, Farklı Kaydet"],
            ["Çalıştırma", "Çalıştır (yeşil), Durdur (kırmızı kare; program çalışırken yanar), Hata Ayıkla (turuncu uğur böceği)"],
            ["Araçlar", "Çevir (TürKod ⇄ Python, mor oklar), Düzelt (sarı sihirli değnek), Bul / Değiştir (pembe)"],
            ["Hata ayıklarken", "Adım At, İçine Gir, Dışına Çık, Durdur: yalnızca hata ayıklarken belirir"],
        ], [1, 3]),
        ("paragraf", "Bir düğmenin ne olduğunu unuttun mu? Farenin okunu üstünde biraz beklet: adını ve "
                     "kısayolunu yazan küçük bir not çıkar. Soluk görünen düğme o an kullanılamaz; örneğin "
                     "Durdur, yalnızca bir program çalışırken renklenir."),
        ("kutu", "bilgi", "Editör darsa, örneğin Gezgin ve AI Asistan ikisi de açıkken, düğmelerin yazıları "
                          "saklanır, yalnızca simgeleri kalır. Çalıştır'ın yazısı hep görünür. Yine sığmazsa "
                          "fare tekerleğini çevirerek gizli düğmeleri görürsün."),
        ("paragraf", "Komut Paleti'ni ve panel düğmelerini en üst satırda bulursun: ortadaki **Komut ara…** "
                     "kutusuna tıkla ya da `Ctrl+Shift+P`'ye bas."),
        ("resim", "komut_paleti.png", "Komut Paleti: \"kay\" yazınca kaydetme komutları geldi",
         178),
    ]),
    # ------------------------------------------------------------------ 8b
    ("Gezgin paneli", "Dosyalarının durduğu oyuncak dolabı.", [
        ("paragraf", "Gezgin, açtığın klasörün içini gösterir: her kod dosyan burada bir rafta durur. Üstteki "
                     "dört düğme **Yeni Dosya**, **Yeni Klasör**, **Klasör Aç** ve **Yenile**'dir. Hemen altında "
                     "açık klasörün adı büyük harflerle yazar. Klasöre tıklarsan yanındaki ok döner ve klasör açılır "
                     "ya da kapanır; dosyaya tıklarsan editörde açılır. Dosyalar türlerine göre farklı simgelerle "
                     "görünür: kod dosyası `<>`, not dosyası sayfa, resim fotoğraf, PDF kırmızı sayfa, EXE "
                     "küçük kareler."),
        ("paragraf", "Bir dosyaya **sağ tıklarsan** küçük bir menü çıkar: Yeni Dosya, Yeni Klasör, Yeniden "
                     "Adlandır, Sil, Yenile. Yeni dosya için TürKod \"yeni.trpy\" adını önerir, sen istediğin adı "
                     "verirsin. Açık bir dosyanın adını değiştirirsen sekmesinin adı da değişir."),
        ("resim", "gezgin_sag_tik.png", "Gezgin'de bir dosyaya sağ tıklayınca açılan menü", 250),
        ("kutu", "bilgi", "Gezgin'den sildiğin dosyalar kaybolmaz, **Geri Dönüşüm Kutusu**'na gider. Yanlışlıkla "
                          "sildiysen oradan geri alabilirsin. USB bellek gibi kutusu olmayan yerlerde TürKod "
                          "silmeden önce sana sorar. Adı noktayla başlayan gizli dosyalar gösterilmez; çok "
                          "kalabalık klasörlerde ilk 300 dosya listelenir."),
    ]),
    # ------------------------------------------------------------------ 8c
    ("PDF dosyalarını okumak", "Kitabını kodunun yanında aç.", [
        ("paragraf", "Gezgin'de bir PDF dosyasına tıklarsan TürKod onu yeni bir sekmede **sayfa sayfa** gösterir, "
                     "tıpkı bir kitap gibi. Örneğin bu kitabı proje klasörüne koyarsan bir sekmede kitabı okur, "
                     "öbür sekmede kodunu yazarsın."),
        ("resim", "pdf_sekmesi.png", "Bu kitap, TürKod'un içinde bir PDF sekmesinde açık", 215),
        ("tablo", ["Ne yapmak istiyorsun?", "Nasıl?"], [
            ["Sayfa değiştirmek", "Üstteki oklar, `PageUp` / `PageDown` ya da fare tekerleği"],
            ["Bir sayfaya atlamak", "Sayfa kutusuna numarayı yaz, `Enter`'a bas (`Home` / `End`: ilk / son sayfa)"],
            ["Hızla gezinmek", "Sağdaki renkli tutamacı yukarı aşağı sürükle; üstünde sayfa numarası yazar"],
            ["Yakınlaştırmak", "Artılı büyüteç, `Ctrl` + fare tekerleği ya da `Ctrl+=`"],
            ["Uzaklaştırmak", "Eksili büyüteç, `Ctrl` + fare tekerleği ya da `Ctrl+-`"],
            ["Genişliğe sığdırmak", "Çerçeve düğmesi ya da `Ctrl+0`"],
            ["Bütün sayfayı görmek", "En sağdaki dikdörtgen düğme"],
        ], [1.5, 3]),
        ("paragraf", "Yüzde yazısı ne kadar büyüttüğünü söyler. PDF yalnızca okunur, içine yazamazsın."),
        ("kodi", "Ben kitabı hep bir sekmede açık tutuyorum. Bir örneği okuyup hemen yandaki sekmede deniyorum!"),
    ]),
    # ------------------------------------------------------------------ 9
    ("Editör: yazarken yardımcılar", "Sen yazarken editör seni izler ve yardım eder.", [
        ("paragraf", "Editör sıradan bir defter değil, seni izleyen akıllı bir defter! Sen yazarken arka planda "
                     "şunları yapar:"),
        ("maddeler", [
            "**Renkli yazı**: komutlar, yazılar, sayılar ve yorumlar ayrı renklere boyanır.",
            "**Canlı denetim**: yazmayı bıraktıktan yaklaşık 1 saniye sonra kodunu kontrol eder. Hatalı satırın "
                "zemini kırmızı olur, hatanın altı dalgalı çizgiyle çizilir.",
            "**Parantez eşi**: imleç bir parantezin yanındayken onun eşi de parlar.",
            "**Otomatik kapama**: ( [ { ya da tırnak açınca kapanışı da kendiliğinden gelir. Kapanışı sen de "
                "yazarsan imleç üstünden atlar. Bir yazıyı seçip parantez ya da tırnak yazarsan seçim içine alınır.",
            "**Otomatik girinti**: iki noktayla (:) biten satırdan sonra Enter'a basınca yeni satır 4 boşluk "
                "içeriden başlar.",
            "`Tab` / `Shift+Tab`: satırı ya da seçili satırları bir basamak içeri / dışarı alır.",
            "`Ctrl+Enter` altına, `Ctrl+Shift+Enter` üstüne boş satır açar.",
            "**Büyüteç**: `Ctrl` + fare tekerleği, `Ctrl+=` ya da `Ctrl+-` yazıyı 8 ile 32 arasında büyütüp "
                "küçültür. Seçtiğin boyut hatırlanır.",
            "**Kelime açıklaması**: fareyi bir kelimenin üstünde biraz beklet; ne işe yaradığını anlatan bir "
                "kutu çıkar. Kendi adların için \"Sizin tanımladığınız fonksiyon (satır 3)\" gibi bilgi verir. "
                "(Kelime Kaydırma açıkken bu kutu çıkmaz.)",
        ]),
        ("resim", "editor_hata.png", "4. satırda iki nokta unutulmuş: satır kırmızı, durum çubuğu "
                                     "\"Satır 4: ':' bekleniyor\" diyor", 140),
    ]),
    # ------------------------------------------------------------------ 9b
    ("Editörün uyarıları", "Program çalışmadan önce bile seni uyarır.", [
        ("paragraf", "Canlı denetim yalnızca yazım hatalarını yakalamaz. Kodu çalıştırmadan önce iki sinsi "
                     "sorunu daha haber verir:"),
        ("maddeler", [
            "**Tanımsız ad**: hiç oluşturmadığın bir kutuyu kullanırsan \"'x' tanımlı değil. Bunu mu demek "
                "istediniz: 'y'?\" der ve doğrusunu tahmin eder.",
            "**Komutu bozan kutu adı**: örneğin `toplam = 0` yazarsan, artık `toplam()` komutu çalışmaz. TürKod "
                "bunu fark edip seni uyarır.",
        ]),
        ("kutu", "dikkat", "Kırmızı satır görürsen panik yok! Önce durum çubuğundaki açıklamayı oku; çoğu zaman "
                           "unutulan bir iki nokta ya da parantezdir."),
        ("kodi", "Ben sen yazarken hep yanındayım. Bir şey ters gidince satırı kırmızıya boyarım ki gözünden "
                 "kaçmasın!"),
        ("kutu", "gorev", "Bir satırın sonundaki iki noktayı sil ve satırın nasıl kırmızılaştığını izle. Sonra "
                          "iki noktayı geri koy: kırmızı kayboldu mu?"),
    ]),
    # ------------------------------------------------------------------ 10
    ("Tamamlama ve hayalet kod", "Sen yazarken TürKod kelimenin devamını tahmin eder.", [
        ("baslik", "Öneri listesi"),
        ("paragraf", "Bir kelimenin ilk iki harfini yazdığın anda küçük bir liste açılır (en fazla 15 öneri). "
                     "`↑` / `↓` ile seç, `Tab` ya da `Enter` ile ekle; `Esc` listeyi kapatır. Liste şöyle dizilir:"),
        ("maddeler", [
            "önce senin oluşturduğun kutular ve fonksiyonlar,",
            "sonra yeni başlayanların en çok kullandığı kelimeler,",
            "satır başındaysan **kod kalıpları**: eğer, eğer/değilse, için-aralık, için-liste, döngü, fonksiyon, "
                "sınıf, dene/hata_yakala, dosya açma, sayı girdisi... Bütün bir bloğu ekler, imleci içine koyar,",
            "en sonda sözlükteki diğer TürKod kelimeleri.",
        ]),
        ("resim", "tamamlama.png", "\"yaz\" yazınca açılan öneri listesi", 145),
        ("paragraf", "Bir kutunun adından sonra nokta koyarsan (`meyveler.`) o kutuya uyan komutlar gelir: "
                     "listeler için `sona_ekle`, yazılar için `büyük_harf` gibi. `içe_aktar` ile eklediğin "
                     "kütüphanelerin komutları da gelir. Türkçe harfsiz yazsan da (`yazdir`) TürKod anlar, ama "
                     "listede hep Türkçe yazımı gösterir."),
    ]),
    # ------------------------------------------------------------------ 10b
    ("Hayalet kod", "Yapay zekânın gri fısıltıları.", [
        ("paragraf", "Ayarlar'da bir yapay zekâ modeli **Otomatik tamamlama (hayalet kod)** görevine atandıysa, "
                     "yazmayı bıraktığında imlecin arkasında gri, eğik yazıyla bir öneri belirir. Bir hayalet gibi "
                     "silik durur; beğenirsen gerçeğe dönüştürürsün:"),
        ("tablo", ["Tuş", "Ne yapar?"], [
            ["`Tab`", "Önerinin tamamını kabul eder."],
            ["`Ctrl+→`", "Yalnızca bir kelimesini kabul eder."],
            ["`Esc`", "Öneriyi kapatır."],
            ["`Ctrl+Shift+Space`", "Beklemeden hemen öneri ister."],
        ], [1.2, 3]),
        ("kutu", "bilgi", "Hayalet kod kelimenin ortasında çıkmaz; orası öneri listesinin işi. Satır bittiyse "
                          "öneri bir alt satırdan, doğru girintiyle başlar. Ne kadar bekleyeceği Ayarlar'dan 100-1500 "
                          "milisaniye arasında ayarlanır."),
        ("kodi", "Hayalet kod çok yardımcıdır ama her önerisi doğru olmayabilir. Kabul etmeden önce oku, olur mu?"),
    ]),
    # ------------------------------------------------------------------ 11
    ("Bul ve Değiştir", "Uzun kodlarda kaybolmamak için.", [
        ("paragraf", "`Ctrl+F` editörün üstünde yüzen bir arama kutusu açar; başlığından tutup istediğin yere "
                     "taşıyabilirsin. Aradığın şeyi yaz: bütün eşleşmeler sarıya, bulunduğun eşleşme turuncuya "
                     "boyanır. Enter ya da **Sonraki** okuyla sıradakine, **Önceki** ile geriye gidersin."),
        ("resim", "bul_degistir.png", "\"sayı\" araması: 11 eşleşme sarı, bulunan turuncu", 165),
        ("tablo", ["Düğme", "Anlamı"], [
            ["`Aa`", "Büyük/küçük harf duyarlı: \"Puan\" ile \"puan\" farklı sayılır."],
            ["`ab`", "Tam kelime: \"say\" ararken \"sayı\" bulunmaz."],
            ["`.*`", "Düzenli ifade: büyükler için gelişmiş arama kalıpları ($1, $2 ile değiştirme)."],
            ["Değiştir / Tümünü Değiştir", "`Ctrl+H` ile çıkan satır: bulunanı bir tane ya da hepsini değiştirir."],
        ], [1.2, 3.3]),
        ("paragraf", "Bir kelimeyi seçip `Ctrl+F`'ye basarsan kelime kendiliğinden kutuya yazılır. Kutunun "
                     "altında \"11 eşleşme\" ya da \"Bulunamadı\" gibi bilgiler görünür."),
        ("kutu", "gorev", "Tahmin oyununda `sayı` kelimesini ara. Kaç eşleşme buldun?"),
    ]),
    # ------------------------------------------------------------------ 11b
    ("Çoklu imleç ve katlama", "Aynı anda birçok yere yazmak, kodu toplamak.", [
        ("baslik", "Çoklu imleç"),
        ("paragraf", "Aynı şeyi beş satıra birden yazman gerekiyor mu? `Alt` tuşunu basılı tutup her satıra tıkla; "
                     "her yerde yanıp sönen bir imleç belirir. `Ctrl+Alt+↓`, `Ctrl+D` ve `Ctrl+Shift+L` da imleç "
                     "ekler. Ne yazarsan bütün imleçlere birden gider, tıpkı aynı anda beş kalemle yazmak gibi. "
                     "`Esc` fazla imleçleri kaldırır."),
        ("baslik", "Satır numaraları ve katlama"),
        ("paragraf", "Satır numarasına tıklarsan o satıra kırmızı bir durak (kesme noktası) koyarsın; sağ "
                     "tıklarsan koşullu durak penceresi açılır. Numaraların yanındaki ▼ okları bir bloğu (eğer, "
                     "için, fonksiyon ...) akordeon gibi **katlar**: blok \"N satır katlandı\" yazısına "
                     "dönüşür. Katlanmış yerde bir şey değiştirirsen blok yeniden açılır."),
        ("kodi", "Uzun kodlarda katlama benim en sevdiğim özellik. Bitirdiğin blokları katla, sadece "
                 "üzerinde çalıştığın yer kalsın!"),
        ("kutu", "gorev", "Tahmin oyunundaki `döngü` satırının yanındaki ▼ okuna tıkla. Kaç satır katlandı?"),
    ]),
    # ------------------------------------------------------------------ 12
    ("Sekmeler ve bölünmüş görünüm", "Birçok dosyayla rahat çalışmak.", [
        ("baslik", "Sekmeler"),
        ("maddeler", [
            "Sekme adının yanındaki **sarı nokta** \"bu dosya kaydedilmedi\" demek.",
            "**×** sekmeyi kapatır; kaydetmediysen Vazgeç / Kapat / Kaydet diye sorar.",
            "Sekmeleri fareyle sürükleyip sıralarını değiştirebilirsin. Çok sekme varsa fare tekerleği şeridi "
                "kaydırır. **+** düğmesi yeni sekme açar.",
            "Aynı adlı iki dosya açarsan TürKod karışmasın diye sekmeye farklı bir ad önerir.",
        ]),
        ("baslik", "Editörü bölmek ve mini harita"),
        ("paragraf", "`Ctrl+\\` editörün sağına ikinci bir bölme açar. Bölmenin üstündeki listeden hangi sekmeyi "
                     "göstereceğini seçersin; iki taraftaki yazı her zaman aynıdır. **Mini Harita** açıksa sağ "
                     "kenarda kodunun kuş bakışı resmi görünür; tıklayıp sürükleyerek kodda gezinirsin."),
        ("resim", "bolunmus_gorunum.png", "Ctrl+\\ ile bölünmüş editör: aynı dosya yan yana", 200),
    ]),
    # ------------------------------------------------------------------ 12b
    ("Seni koruyan uyarılar", "TürKod emeğini korumak için hep tetikte.", [
        ("maddeler", [
            "Kaydetmediğin dosya varken programı kapatırsan TürKod seni durdurur: **Vazgeç / Kaydetmeden Çık / "
                "Kaydet ve Çık**.",
            "Açık dosyan başka bir programla değiştirildiyse kaydederken \"Dosya diskte değişti\" diye uyarır.",
            "Program beklenmedik şekilde kapanırsa bir sonraki açılışta kaydetmediğin değişiklikler "
                "**kurtarılır** ve bunu söyleyen bir mesaj çıkar. Açık sekmelerin de "
                "aynen geri gelir.",
            "TürKod dosyanı kaydederken eski yazı kodlamasını ve satır sonlarını korur. Kaydetme yarıda kesilse "
                "bile eski dosyan bozulmaz.",
        ]),
        ("kutu", "ipucu", "**Kaydederken biçimlendir** ayarını açarsan her kayıtta kodunun girintileri ve "
                          "boşlukları kendiliğinden toparlanır."),
        ("kodi", "Ben de bir kere kaydetmeden kapatmıştım, bütün oyunum gitti sanmıştım. Neyse ki TürKod "
                 "kurtardı! Yine de sık sık `Ctrl+S`'ye basmayı unutma."),
    ]),
    # ------------------------------------------------------------------ 13
    ("Durum çubuğu ve Sorunlar", "En alttaki ince şerit sana hep bilgi verir.", [
        ("tablo", ["Durum çubuğunda", "Anlamı"], [
            ["Hazır / Program çalışıyor / Hata ayıklanıyor", "En soldaki rozet: programın o anki durumu. Çalışırken yeşil, hata ayıklarken turuncu yanar."],
            ["✓ Sözdizimi doğru (yeşil)", "Kodunda yazım hatası yok. Harika!"],
            ["⚠ ... (turuncu)", "Uyarı var: kod çalışır ama bir sorun olabilir."],
            ["Satır N: ... (kırmızı)", "Yazım hatası var. Üstüne tıklarsan Sorunlar listesi açılır."],
            ["Odak Zamanlayıcı", "Ders çalışma saati (yalnızca bu eklenti açıksa)."],
            ["Satır X, Sütun Y", "İmlecin tam yeri."],
            ["Dosya adı", "Açık sekmenin adı (yoksa \"Dosya Yok\")."],
            ["UTF-8", "Yazı kodlaması: Türkçe harflerin doğru saklandığını gösterir."],
            ["Simgeler", "Kod İstatistikleri, Yapılacaklar Listesi, Kod Arama Çevirici, Hakkında / İmza."],
        ], [1.5, 3]),
        ("baslik", "Sorunlar listesi"),
        ("paragraf", "`Ctrl+Shift+M`'ye bas ya da durum çubuğundaki kırmızı yazıya tıkla: \"Sorunlar\" penceresi "
                     "açılır. Her hata satır numarasıyla yazılır; birine tıklarsan editör seni o satıra götürür. "
                     "Hiç sorun yoksa \"Bu dosyada sorun yok.\" der."),
        ("resim", "sorunlar.png", "Sorunlar penceresi: hatanın açıklaması ve satırı", 160),
        ("kutu", "bilgi", "Çok uzun dosyalarda (5000 satırdan fazla) editör yavaşlamasın diye yalnızca hızlı bir "
                          "kontrol yapılır."),
    ]),
    # ------------------------------------------------------------------ 14
    ("Terminal", "Programının konuştuğu, senin de cevap verdiğin yer.", [
        ("paragraf", "Terminal, programınla sohbet ettiğin pencere. Program bir şey yazınca burada görürsün; "
                     "bir şey sorunca cevabını alttaki satıra yazarsın. Üstteki düğmeler:"),
        ("tablo", ["Düğme", "Ne yapar?"], [
            ["TürKod Kabuğu", "Program çalışmıyorken görünür; kabuğu terminalin içinde açar."],
            ["Ayrı pencere simgesi", "TürKod Kabuğu'nu ayrı bir pencerede açar."],
            ["Hatayı AI ile açıkla", "Program hatayla bitince çıkar; hatayı yapay zekâya anlattırır."],
            ["Yazıyı Küçült / Büyüt", "Terminal yazısını 8-28 arasında küçültür ya da büyütür (Ctrl+tekerlek de olur)."],
            ["Tüm çıktıyı kopyala", "Terminaldeki bütün yazıyı panoya alır."],
            ["Temizle / Kapat", "Terminali temizler / saklar."],
        ], [1.4, 3]),
        ("baslik", "Alttaki yazma satırı"),
        ("maddeler", [
            "Program **çalışırken** yazdığın her satır programa cevap olarak gider (`girdi_al` böyle çalışır). "
                "Boş Enter bile gönderilir.",
            "Program **çalışmıyorken** yazdıkların bilgisayara komut olarak gider (örneğin `dir`, `cd`).",
            "`↑` / `↓` daha önce yazdığın son 100 komutu geri getirir.",
            "Hiçbir şey seçili değilken `Ctrl+C` çalışan programı durdurur.",
        ]),
    ]),
    # ------------------------------------------------------------------ 14b
    ("Terminalin mesajları", "Terminal kendi de bir şeyler söyler.", [
        ("tablo", ["Mesaj", "Anlamı"], [
            ["[Program 1 koduyla sonlandı]", "Program hatayla bitti. Sorunsuz biterse bu satır hiç çıkmaz."],
            ["[Durduruldu]", "Programı sen durdurdun."],
            ["[Program durduruldu (Ctrl+C)]", "Ctrl+C ile durdurdun."],
            ["[... kesildi ...]", "Çıktı çok uzadı; eski kısmı kısaltıldı."],
        ], [1.6, 3]),
        ("paragraf", "Program çalışırken TERMİNAL yazısının yanında dönen bir simge görürsün: \"Ben hâlâ "
                     "çalışıyorum\" demektir. Program bir şey sorduysa cevabını alttaki satıra yazıp Enter'a bas, "
                     "program devam etsin."),
        ("kodi", "Terminal benim sesim gibidir. Programın ne düşündüğünü hep orada söylerim!"),
        ("kutu", "gorev", "Tahmin oyununu çalıştır ve üç tahmin yap. Sonra programı `Ctrl+C` ile yarıda "
                          "durdurmayı dene. Terminal ne yazdı?"),
    ]),
    # ------------------------------------------------------------------ 14c
    ("Her sekmenin kendi terminali", "Her dosyanın kendi konuşma defteri var.", [
        ("paragraf", "Sınıfta her öğrencinin kendi defteri olur, değil mi? TürKod'da da **her sekmenin kendi "
                     "terminali** vardır. Bir sekmede yazdığın komutlar, programın çıktısı ve `↑` ile geri "
                     "getirdiğin eski komutlar yalnızca o sekmenin terminalinde durur."),
        ("maddeler", [
            "Başka bir sekmeye geçince, o sekmenin terminali daha önce açıldıysa **o terminal görünür**; "
            "açılmadıysa terminal paneli kapanır. Geri döndüğünde eski terminalin her şeyiyle yerinde bekler.",
            "Terminali `Ctrl+J` ile açıp kapattığında yalnızca o sekmeninkini açıp kapatırsın.",
            "`cd` ile girdiğin klasör de her sekmede ayrı hatırlanır.",
            "**Ayarlar** sekmesinin terminali yoktur. Oradayken terminal açılmaz; bir kod sekmesine geç.",
        ]),
        ("baslik", "Program başka sekmede çalışırken"),
        ("paragraf", "Aynı anda tek bir program çalışabilir. Bir sekmede oyunun çalışırken başka bir sekmenin "
                     "terminalini açarsan başlıkta **Program \"oyun.trpy\" sekmesinde çalışıyor** yazar. Bu "
                     "terminale yazdıkların oyuna gitmez, burada komut olarak çalışır."),
        ("tablo", ["Mesaj", "Anlamı"], [
            ["[Başka bir sekmede program başlatıldığı için bu program durduruldu]",
             "Başka sekmede Çalıştır'a bastın; eski program kapandı."],
        ], [2.4, 2.2]),
        ("kutu", "gorev", "İki dosya aç. Birinde tahmin oyununu çalıştır, sonra öbür sekmeye geç. Terminal ne "
                          "oldu? Geri dönünce oyunun seni hâlâ bekliyor mu?"),
    ]),
    # ------------------------------------------------------------------ 15
    ("Terminal komutları", "Terminalde TürKod'a özel komutlar da var.", [
        ("paragraf", "Terminale `turkod --yardim` yazarsan bütün komutları görürsün. En kullanışlıları:"),
        ("tablo", ["Komut", "Ne yapar?"], [
            ["`turkod dosya.trpy`", "Bir TürKod dosyasını çalıştırır."],
            ["`turkod --kontrol dosya.trpy`", "Yazım hatası var mı diye bakar."],
            ["`turkod --duzelt dosya.trpy`", "Akıllı Düzelt uygular (`--yaz` eklersen dosyaya kaydeder)."],
            ["`turkod --bicimlendir dosya.trpy`", "Kodu toparlar (`--yaz` ile kaydeder)."],
            ["`turkod --python dosya.trpy`", "Kodun Python hâlini gösterir."],
            ["`turkod --turkod dosya.py`", "Python dosyasını TürKod'a çevirir."],
            ["`turkod --cevir \"yazdır(1)\"`", "Tek bir satırı çevirir."],
            ["`turkod --anlam yazdır`", "Bir kelimenin anlamını söyler."],
            ["`turkod --dersler`", "Kabuktaki dersleri listeler."],
            ["`turkod kabuk`", "TürKod Kabuğu'nu açar."],
            ["`turkod exe_yap dosya.trpy`", "Programı EXE yapar (seçenekler: `turkod exe_yap --yardim`)."],
            ["`turkod kaynak oyun.exe`", "Bir TürKod EXE'sinin kodunu gösterir."],
            ["`turkod --surum`", "Sürümü gösterir."],
        ], [1.8, 2.6]),
        ("kutu", "gorev", "Terminale `turkod --anlam yazdır` yaz. TürKod sana ne anlattı?"),
    ]),
    # ------------------------------------------------------------------ 15b
    ("Türkçe pip: kütüphane kurmak", "Programına yeni oyuncaklar ekle. (Büyüklerle birlikte)", [
        ("paragraf", "Kütüphaneler, başkalarının yazıp paylaştığı hazır kod kutularıdır. Python'un kütüphanelerini "
                     "Türkçe komutlarla kurabilirsin. Kurulanlar `%LOCALAPPDATA%\\TurKod\\pip_packages` klasörüne "
                     "gider."),
        ("tablo", ["Komut", "Ne yapar?"], [
            ["`pip yükle paket`", "Kütüphane kurar."],
            ["`pip güncelle paket` / `pip sil paket`", "Günceller / kaldırır."],
            ["`pip listele` / `pip eskiler`", "Kurulu olanları / eskimiş olanları listeler."],
            ["`pip bilgi paket` / `pip ara kelime`", "Bilgi gösterir / arar."],
            ["`pip dondur`, `denetle`, `indir`, `sürüm`", "Diğer pip işleri. Yalnızca `pip` yazınca hepsinin "
                                                          "yardımı çıkar."],
        ], [1.9, 2.5]),
        ("kutu", "dikkat", "Kütüphane kurarken internetten dosya indirilir. Bunu mutlaka bir büyüğünle birlikte yap."),
    ]),
    # ------------------------------------------------------------------ 16
    ("Çıktı ve hata mesajları", "TürKod sana hep Türkçe konuşur.", [
        ("paragraf", "`yazdır` ekranda Doğru, Yanlış ve Hiçlik'i Türkçe gösterir; listelerin ve sözlüklerin "
                     "içindekiler de öyle. Bir hata olduğunda da TürKod sana Türkçe ne olduğunu anlatır:"),
        ("kod", "hata.trpy", ['puan = 5', 'yazdır(puann + 1)']),
        ("terminal", ['==================================================',
                      '[HATA]: Tanımsız İsim Hatası',
                      'Satır Numarası: 2',
                      "Açıklama: 'puann' adında bir değişken/fonksiyon tanımlı değil! Bunu mu",
                      "demek istediniz: 'puan'?",
                      '==================================================']),
        ("maddeler", [
            "**[HATA]** hatanın türünü, **Satır Numarası** hatanın senin kodunda nerede olduğunu, **Açıklama** "
                "ne olduğunu söyler.",
            "Hata başka bir .trpy dosyandaysa bir de **Dosya:** satırı çıkar.",
            "\"Bunu mu demek istediniz\" büyük/küçük harf farkını (`doğru` → `Doğru`), eksik parçayı (`girdi` → "
                "`girdi_al`) ve benzeyen adları yakalar.",
        ]),
        ("kutu", "ipucu", "Mesajı anlamadın mı? Terminaldeki **Hatayı AI ile açıkla** düğmesine bas."),
    ]),
    # ------------------------------------------------------------------ 17
    ("Pencereli programlar", "Kaplumbağa, pencere, oyun: hepsi Türkçe konuşur.", [
        ("paragraf", "Kaplumbağa, tkinter (pencere), pygame ve ursina (oyun) programları ayrı bir pencere açar. "
                     "Terminal yine çalışır, programın yazdıklarını ve senin cevaplarını taşır. Üstelik bu "
                     "kütüphanelere renkleri ve seçenekleri Türkçe söyleyebilirsin:"),
        ("kod", "renkler.trpy", ['içe_aktar kaplumbağa', '', 'kaplumbağa.şekil("kaplumbağa")',
                                 'kaplumbağa.hız("en_hızlı")', 'kaplumbağa.kalem_rengi("turuncu")',
                                 'kaplumbağa.çember(50)', 'kaplumbağa.tamamla()']),
        ("resim", "kaplumbaga_penceresi.png", "Kaplumbağa programı çalışınca ayrı bir çizim penceresi açılır", 250),
        ("paragraf", "Programının penceresi görev çubuğunda da kendini belli eder: TürKod yıldızlı, yeşil "
                     "\"oynat\" düğmeli simgeyi görürsen o senin çalışan programındır. Kendi simgeni koyarsan "
                     "(ör. pygame'de `pygame.display.set_icon(...)`) seninki görünür."),
    ]),
    # ------------------------------------------------------------------ 17b
    ("Türkçe değerler", "Renkleri, şekilleri, tuşları Türkçe yaz.", [
        ("tablo", ["Tür", "Türkçe değerlerden örnekler"], [
            ["Renkler", "kırmızı, yeşil, mavi, sarı, turuncu, mor, pembe, lacivert, turkuaz, açık_mavi, koyu_yeşil, "
                        "altın ..."],
            ["Kaplumbağa şekli", "kaplumbağa, ok, daire, kare, üçgen, klasik"],
            ["Kaplumbağa hızı", "en_hızlı, hızlı, normal, yavaş, en_yavaş"],
            ["Hizalama, yazı", "sol, orta, sağ; kalın, italik, altı_çizili"],
            ["Tuş adları", "yukarı, aşağı, sol, sağ, boşluk, giriş, kaçış, geri_sil, sekme"],
        ], [1.3, 3.3]),
        ("paragraf", "Değerleri `açık_mavi`, `acik_mavi` ya da `Açık Mavi` diye yazabilirsin; TürKod hepsini "
                     "anlar. Bazı kütüphanelerin İngilizce bilgi mesajları da terminalde Türkçeye çevrilir."),
        ("kutu", "bilgi", "`tamamla()` çizim bitince pencerenin açık kalmasını sağlar. Pencereyi kapatınca "
                          "program da biter."),
        ("kutu", "gorev", "`renkler.trpy` örneğindeki rengi \"lacivert\", şekli \"ok\" yap ve çalıştır."),
    ]),
    # ------------------------------------------------------------------ 18
    ("Kendi modüllerin", "Kodunu dosyalara bölmek.", [
        ("paragraf", "Kodun uzayınca onu dosyalara bölebilirsin, tıpkı oyuncaklarını ayrı kutulara koymak gibi. "
                     "Aynı klasördeki başka bir .trpy dosyasını `içe_aktar` ile kullanırsın. Bunun için iki "
                     "dosya da **kaydedilmiş** olmalı."),
        ("kod", "selam.trpy", ['fonksiyon merhaba(isim):', '    döndür f"Merhaba {isim}!"']),
        ("kod", "ana.trpy", ['içe_aktar selam', '', 'yazdır(selam.merhaba("Deniz"))']),
        ("terminal", ["Merhaba Deniz!"]),
        ("paragraf", "`den selam içe_aktar merhaba` da yazabilirsin. Alt klasörlerdeki paketler "
                     "(`paket/__init__.trpy`) da çalışır."),
        ("kutu", "gorev", "Gezgin'deki `selam.trpy` dosyasına `hoşça_kal(isim)` adında yeni bir fonksiyon ekle "
                          "ve onu başka bir dosyadan çağır."),
    ]),
    # ------------------------------------------------------------------ 18b
    ("Çalıştırma argümanları", "Programına başlarken bilgi vermek. (Meraklılar için)", [
        ("paragraf", "**Çalıştır → Çalıştırma Argümanları…** penceresine programa başlarken vereceğin bilgileri "
                     "yazarsın, örneğin `veri.txt --ayrintili \"iki kelime\"`. Tırnak içindekiler tek bilgi sayılır. "
                     "Program bunları `sistem.argümanlar` listesinde bulur:"),
        ("kod", "argumanlar.trpy", ['içe_aktar sistem', 'yazdır(sistem.argümanlar[1:])']),
        ("kodi", "Argümanlar, programına çantasına koyup yolladığın notlar gibi. Program açılınca çantasına "
                 "bakar ve notları okur!"),
    ]),
    # ------------------------------------------------------------------ 19
    ("Akıllı Düzelt", "Hatalarını bulup düzelten sihirli değnek.", [
        ("paragraf", "Araç çubuğundaki sihirli değnek (**Düzelt**) kodunu inceler ve hataları düzeltmeye çalışır. "
                     "İnternete ihtiyacı yoktur. Neler yapabilir?"),
        ("maddeler", [
            "Karışık girintileri, eğri tırnakları ve görünmez karakterleri temizler.",
            "Ayrık yazılmış kelimeleri birleştirir (`değilse eğer` → `değilse_eğer`), yazım yanlışlarını düzeltir "
                "(`yazdir` → `yazdır`, `eger` → `eğer`).",
            "Unutulan iki noktayı, `=` yerine `==`'yi, `=<` gibi ters işaretleri, eksik parantez, virgül ya da "
                "tırnakları onarır.",
            "`girdi_al` ile alınan sayıyı `tamsayı()` içine alır; `x = x.sona_ekle(...)` gibi yanlışları düzeltir.",
            "Kodu güvenli bir köşede deneyip çıkan hataları (tanımsız ad, yazı + sayı, eksik `kendisi` ...) "
                "düzeltir. İşe yaramayan düzeltmeyi geri alır.",
            "Kendisi dokunmadığı şüpheli yerleri söyler: çıkışı olmayan `döngü Doğru`, sıfıra bölme, hiç "
                "kullanılmayan kutu gibi.",
        ]),
        ("baslik", "Önce izin ister"),
        ("paragraf", "Kodun dosya silme, internete bağlanma gibi riskli işler yapıyorsa düzeltici önce sorar: "
                     "\"Kod çalıştırılsın mı?\" **Çalıştırarak düzelt** ya da **Çalıştırmadan düzelt**'i seçersin."),
        ("kutu", "dikkat", "Düzeltici bazen ne demek istediğini yanlış anlayabilir. Uygulamadan önce farklara bir "
                           "göz at."),
    ]),
    # ------------------------------------------------------------------ 19b
    ("Akıllı Düzelt raporu", "Düzelticinin sana verdiği karne.", [
        ("paragraf", "Düzeltici işini bitirince bir rapor gösterir. Aşağıdakinde iki hata bulmuş: 4. satırda "
                     "unutulan iki noktayı eklemiş, 2. satırda yanlış yazılan `puann` adını `puan` yapmış. Her "
                     "düzeltmenin yanında ne kadar emin olduğu yazıyor (%95, %82). \"Satır 4\" yazısına tıklarsan "
                     "o satıra gidersin."),
        ("resim", "akilli_duzelt.png", "Akıllı Düzeltme Raporu: kod sağlığı, güven ve yapılan düzeltmeler", 360),
        ("paragraf", "**Düşünce sürecini göster** düzelticinin adım adım neler denediğini, **Kod farklarını "
                     "göster** eski ve yeni kodu yan yana gösterir. Sonunda karar senin: **Uygula**, **Yeni "
                     "Sekmede Aç** ya da **Reddet**."),
    ]),
    # ------------------------------------------------------------------ 20
    ("Hata ayıklayıcı: kesme noktaları", "Programı istediğin yerde durdur, içine bak.", [
        ("paragraf", "Hata ayıklayıcı, programını bir filmi yavaş çekimde izler gibi **satır satır** "
                     "oynatmanı sağlar. Böylece kutuların içinde o an ne olduğunu görürsün. Önce programın "
                     "durmasını istediğin satıra bir **kesme noktası** (durak) koy: `F9`'a bas ya da satır "
                     "numarasına tıkla. Kırmızı bir nokta belirir."),
        ("kod", "sayac.trpy", ['toplam_sayı = 0', 'meyveler = ["elma", "armut", "kiraz"]', 'için i aralık(5):',
                               '    toplam_sayı = toplam_sayı + i', 'yazdır(toplam_sayı)']),
        ("paragraf", "4. satıra kesme noktası koyup `F5`'e bas. Program o satıra gelince durur, satır sarıya "
                     "boyanır ve küçük bir panel açılır. `F5`'e her bastığında döngü bir tur döner: `i` ve "
                     "`toplam_sayı` kutularının değiştiğini izle!"),
        ("resim", "hata_ayiklayici.png", "Kesme noktasında durmuş program: sarı satır ve değişkenler", 200),
    ]),
    # ------------------------------------------------------------------ 20b
    ("Koşullu kesme noktası", "Programa \"ancak şu olunca dur\" demek.", [
        ("paragraf", "Bazen program bir satırdan yüz kere geçer ama sen yalnızca bir anı merak edersin. Satır "
                     "numarasına sağ tıkla (ya da `Shift+F9`): bir pencere açılır. Buraya TürKod ile bir şart yaz, "
                     "örneğin `i == 3`. Program yalnızca şart doğruyken durur."),
        ("paragraf", "Aynı penceredeki \"Kaçıncı geçişte durulsun?\" kutusuna 4 yazarsan program o satıra "
                     "dördüncü gelişinde durur."),
        ("kutu", "ipucu", "Hiç kesme noktası koymadan `F10`'a basarsan program ilk satırda durur. `Ctrl+F10` "
                          "imlecin olduğu satıra kadar çalıştırır."),
        ("kodi", "Hata ayıklayıcı benim süper gücüm! Kodun içine girip her kutuya tek tek bakabiliyorum. "
                 "Hataları böyle yakalıyorum."),
        ("kutu", "gorev", "`sayac.trpy`'de 4. satıra `i == 3` şartlı bir kesme noktası koy. Program durduğunda "
                          "`toplam_sayı` kaç?"),
    ]),
    # ------------------------------------------------------------------ 21
    ("Hata ayıklama paneli", "Durduğunda neler görürsün, neler yapabilirsin?", [
        ("paragraf", "Hata ayıklarken editörün sağ altında küçük bir panel çıkar. Üstünde neden durduğu "
                     "(Kesme noktası, Adım, Başlangıç, Duraklatıldı ya da Yakalanmamış hata), satır numarası ve "
                     "fonksiyonun adı yazar."),
        ("tablo", ["Düğme", "Kısayol", "Ne yapar?"], [
            ["Devam", "`F5`", "Bir sonraki durağa kadar çalışır."],
            ["Duraklat", "`F6`", "Çalışırken durdurur."],
            ["Adım At", "`F10`", "Bir sonraki satıra geçer."],
            ["İçine Gir", "`F11`", "Fonksiyonun içine girer."],
            ["Dışına Çık", "`Shift+F11`", "Fonksiyondan çıkana kadar çalışır."],
            ["Durdur", "`Shift+F5`", "Hata ayıklamayı bitirir."],
        ], [1, 1, 3]),
        ("tablo", ["Panel bölümü", "Ne gösterir?"], [
            ["İfade kutusu", "Bir TürKod ifadesi yaz (`toplam_sayı * 2`), **Değerlendir** ile sonucunu gör."],
            ["İZLEME", "**İzlemeye ekle** dediğin ifadeler; her durakta yeniden hesaplanır."],
            ["YEREL DEĞİŞKENLER", "Bulunduğun fonksiyonun kutuları. Listeler açılıp kapanır."],
            ["KÜRESEL DEĞİŞKENLER", "Programın genel kutuları."],
            ["ÇAĞRI YIĞINI", "Hangi fonksiyon hangisini çağırdı? Birine tıklarsan onun kutularını görürsün."],
        ], [1.4, 3]),
        ("paragraf", "Bir kutunun yanındaki kalem simgesiyle (**Değeri değiştir**) program dururken kutuya yeni "
                     "bir değer koyabilirsin, örneğin `Doğru` ya da `sayaç + 1`. Program hatayla durursa panelde "
                     "kırmızı bir şerit hatayı gösterir. Çıktı ve girdi yine terminalde çalışır."),
    ]),
    # ------------------------------------------------------------------ 22
    ("AI Asistan paneli", "Sağdaki yapay zekâ arkadaşın.", [
        ("tablo", ["Düğme", "Ne yapar?"], [
            ["Beyin simgesi", "Düşünme açık: model cevaplamadan önce düşünür (yavaş ama dikkatli). Kapalı: hızlı cevap."],
            ["Açıkla (ampul)", "Açık dosyandaki kodu satır satır anlatır."],
            ["Optimize (şimşek)", "Kodu daha derli toplu yapmak için öneri verir."],
            ["Temizle (çöp kutusu)", "Sohbeti siler."],
            ["Model satırı", "Hangi yapay zekânın çalıştığını gösterir. Tıklarsan Ayarlar açılır."],
        ], [1.3, 3.3]),
        ("resim", "ai_paneli.png", "Henüz model kurulmamışken AI Asistan paneli", 195),
        ("paragraf", "Alttaki **Sor...** kutusuna sorunu yaz ve Enter'a bas (`Shift+Enter` yeni satır açar). "
                     "Sorunla birlikte açık dosyandaki kod da gider, böylece yapay zekâ neyden bahsettiğini bilir. "
                     "Cevaplardaki kodlar hep TürKod olarak gösterilir."),
    ]),
    # ------------------------------------------------------------------ 22b
    ("AI cevaplarıyla çalışmak", "Cevabı nasıl kullanırsın?", [
        ("maddeler", [
            "Her cevabın yanında bir **kopyala** düğmesi var. Düşünen modellerde \"Düşündü\" bölümünü açıp nasıl "
                "düşündüğünü okuyabilirsin.",
            "Cevaptaki kod kutularında **Koda uygula** düğmesi var: Üzerine Yaz, İmlece Ekle ya da Yeni Sekme.",
            "Bir şey ters giderse **Yeniden dene**, **AI ayarları** ve **Yerel model kur** düğmeleri çıkar.",
            "Hiç model kurulu değilse panelde **Ücretsiz yerel model kur** düğmesi görünür.",
        ]),
        ("kutu", "dikkat", "Yapay zekâ bazen yanılır. Önce kendin dene, sonra sor; verdiği cevabı da bir "
                           "büyüğünle birlikte kontrol et."),
        ("kodi", "AI Asistan bana çok benzer ama daha çok konuşur! Ondan bir öğretmen gibi yardım iste: "
                 "\"Bunu bana açıklar mısın?\" diye sormak, \"Bunu benim yerime yaz\" demekten çok daha çok öğretir."),
        ("kutu", "gorev", "AI kuruluysa **Açıkla** düğmesine basıp tahmin oyununu anlatmasını iste."),
    ]),
    # ------------------------------------------------------------------ 23
    ("Yapay zekâ görevleri", "Hangi iş için hangi model? (Büyüklerle birlikte)", [
        ("paragraf", "Yapay zekânın her işi ayrı bir **görev**dir ve her göreve ayrı bir model atanabilir. "
                     "Model atanmamış görev kapalıdır. Bunları Ayarlar → **Yapay Zekâ: Görevler** bölümünde seçersin:"),
        ("tablo", ["Görev", "Nerede kullanılır?"], [
            ["Otomatik tamamlama (hayalet kod)", "Editördeki gri öneriler."],
            ["AI Paneli sohbet", "Sağdaki paneldeki sorular."],
            ["Kod açıklama / optimize", "Açıkla ve Optimize düğmeleri."],
            ["Hata açıklama", "Terminaldeki Hatayı AI ile açıkla düğmesi."],
            ["Akıllı Düzelt (AI aşaması)", "Düzeltici kendi başına çözemezse son çare."],
            ["Kodi (yardımcı robot)", "Kodi'nin konuşma balonu. Otomatik'te AI Paneli sohbet modelini kullanır."],
        ], [1.8, 2.8]),
        ("resim", "ayarlar_ai_gorevler.png",
         "Ayarlar → Yapay Zekâ: Görevler (burada hepsi Kapalı, Kodi AI Paneli modelini kullanıyor)", 260),
    ]),
    # ------------------------------------------------------------------ 23b
    ("Sağlayıcı bağlamak", "İnternetteki ya da bilgisayarındaki modeller. (Büyüklerle birlikte)", [
        ("paragraf", "Ayarlar → **Yapay Zekâ: Modeller** → **Sağlayıcı bağla** bölümünde 200'den fazla yapay zekâ "
                     "sağlayıcısından birini seçebilirsin (OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, "
                     "OpenRouter ...). API anahtarını gir, **Bağlantıyı Test Et** ve **Bağla ve modelleri seç** de. "
                     "OpenAI uyumlu özel bir adres, LM Studio ya da bilgisayardaki bir llama.cpp sunucusu da olur."),
        ("maddeler", [
            "Ortak ayarlar: **Sıcaklık** (0-2; yükseldikçe daha yaratıcı), **En Fazla Token** (cevap uzunluğu), "
                "**Sistem Mesajı**.",
            "**Model düşünsün** düşünebilen modellerin akıl yürütmesini açar.",
            "**Bağlantıyı kes** sağlayıcının anahtarını, modellerini ve görev atamalarını siler.",
        ]),
        ("resim", "ayarlar_ai_modeller.png", "Ayarlar → Yapay Zekâ: Modeller: mevcut modeller ve sağlayıcı bağlama",
         250),
        ("kutu", "bilgi", "API anahtarları bilgisayarda Windows'un şifrelemesiyle saklanır; yalnızca sizin "
                          "kullanıcı hesabınız açabilir. İnternete gönderilen kod, dosyanın yalnızca son kısmıdır."),
    ]),
    # ------------------------------------------------------------------ 23c
    ("Ücretsiz Groq anahtarı almak", "Kodi'ye sıfırdan bir beyin bulalım. (Büyüklerle birlikte)", [
        ("paragraf", "**Groq**, yapay zekâ modellerini çok hızlı çalıştıran bir sağlayıcıdır. Ücretsiz bir hesap "
                     "her gün belirli sayıda soru sorma hakkı verir; bu Kodi'ye de AI Asistan'a da yeter. Hesabı "
                     "bir büyüğün açmalı."),
        ("resim", "groq_giris.png", "console.groq.com: hesap açma ve giriş sayfası", 215),
        ("maddeler", [
            "**1.** Tarayıcıda `console.groq.com` adresine gir.",
            "**2.** **Continue with Google**, **Continue with GitHub** ya da e-posta adresinle hesap aç. E-postayla "
                "açarsan kutuna gelen bağlantıya tıkla.",
            "**3.** Üstteki **API Keys** sayfasına geç ve **Create API Key** düğmesine bas. Anahtara bir ad ver "
                "(örneğin \"TürKod\") ve oluştur.",
            "**4.** Çıkan anahtarı (`gsk_` ile başlar) hemen kopyala. Groq onu **yalnızca bir kez** gösterir.",
        ]),
        ("kutu", "dikkat", "API anahtarı bir şifre gibidir: kimseyle paylaşma, ekran görüntüsünde gösterme. "
                           "Yanlışlıkla paylaşırsan Groq'ta **API Keys** sayfasından silip yenisini oluştur."),
    ]),
    # ------------------------------------------------------------------ 23d
    ("Groq'u TürKod'a bağlamak", "Anahtarı yapıştır, modelleri seç.", [
        ("paragraf", "**5.** TürKod'da Ayarlar → **Yapay Zekâ: Modeller** → **Sağlayıcı bağla** bölümüne git. "
                     "Sağlayıcı kutusuna `groq` yaz ve listeden **Groq**'u seç."),
        ("resim", "groq_saglayici.png", "Sağlayıcı kutusuna \"groq\" yazınca Groq çıkıyor", 95),
        ("paragraf", "**6.** Kopyaladığın anahtarı **API Anahtarı (Groq)** kutusuna yapıştır. **Bağlantıyı Test Et** "
                     "ile dene, sonra **Bağla ve modelleri seç**'e bas."),
        ("resim", "groq_form.png", "Anahtar yapıştırıldı (noktalarla gizlenir), sıra Bağla ve modelleri seç'te", 150),
        ("paragraf", "**7.** Açılan pencerede Groq'un modelleri sıralanır. Kullanmak istediklerini işaretle ve "
                     "**Kaydet**'e bas. Örneğin `openai/gpt-oss-20b` hem hızlı hem akıllıdır."),
        ("resim", "groq_model_sec.png", "Groq modelleri: işaretlenenler görevlerde seçilebilir", 185),
    ]),
    # ------------------------------------------------------------------ 23e
    ("Modeli görevlere atamak", "Son adım: hangi iş hangi modelle?", [
        ("paragraf", "**8.** Ayarlar → **Yapay Zekâ: Görevler** bölümünde **AI Paneli sohbet** satırından Groq "
                     "modelini seç. Öteki görevlere de istediğin modeli seçebilirsin."),
        ("resim", "groq_gorevler.png", "Görevlere Groq modelleri atandı; Kodi Otomatik, AI Paneli sohbet modelini kullanıyor",
         185),
        ("paragraf", "**Kodi (yardımcı robot)** satırı **Otomatik** kalırsa Kodi her zaman AI Paneli sohbetinin "
                     "modelini kullanır; yanında hangi model olduğu yazar. Sohbet modelini değiştirirsen Kodi de "
                     "onunla değişir. Kodi'ye ayrı bir model istersen o satırdan seç."),
        ("kutu", "ipucu", "Groq anahtarı Kodi'nin **kulağını** da açar: mikrofonla konuştuğunda sesini yazıya Groq "
                          "çevirir. Groq'ta her modelin kendi soru hakkı vardır. 7. adımda birkaç model "
                          "işaretlersen, birinin hakkı dolunca Kodi beklemeden öbürüyle devam eder."),
        ("kodi", "Hepsi bu kadar! Şimdi sol şeritten beni çağır ve ilk sorunu sor."),
    ]),
    # ------------------------------------------------------------------ 24
    ("Yerel AI modelleri", "İnternetsiz, ücretsiz, bilgisayarında yaşayan yapay zekâ.", [
        ("paragraf", "**Araçlar → Yerel AI Modelleri…** (ya da Eklenti Özellikleri → Model Yöneticisi) "
                     "bilgisayarına küçük yapay zekâ modelleri indirmeni sağlar. Bir kez indirdikten sonra internet "
                     "olmadan çalışırlar ve kodun bilgisayarından hiç çıkmaz."),
        ("resim", "yerel_ai.png", "Yerel AI Modelleri: bilgisayara uygun hafif modeller öneriliyor", 150),
        ("tablo", ["Bölüm", "Ne yapar?"], [
            ["Donanım satırı", "Bilgisayarının belleğini, işlemcisini ve ekran kartını gösterir. NVIDIA kartta "
                               "işler hızlanır (CUDA)."],
            ["Motor", "Modelleri çalıştıran parçayı kurar (**Motoru kur**; yaklaşık 8 MB). **Kaldır** ile silinir."],
            ["Depolama", "Modellerin duracağı klasörü seçersin; her sürücünün boş yeri gösterilir."],
            ["Önerilen", "Bilgisayarına uygun modeller. **İndir** ile indirilir; yarıda kalan indirme kaldığı "
                         "yerden devam eder."],
            ["İndirilenler", "**AI Panelinde kullan**, **Görev ata (Ayarlar)**, **Sil**. \"Kodi için uygun\" "
                             "rozeti, modelin Kodi'yle konuşacak kadar geniş bir hafızası olduğunu gösterir."],
            ["Tüm modeller / Ara", "Hugging Face'te GGUF modelleri arar; \"Yalnızca uygun olanlar\" süzgeci var."],
        ], [1.2, 3.4]),
    ]),
    # ------------------------------------------------------------------ 24b
    ("Yerel model kurmak", "İlk yapay zekânı birlikte kuralım.", [
        ("maddeler", [
            "**1.** Araçlar → Yerel AI Modelleri penceresini aç.",
            "**2.** Motor kurulu değilse **Motoru kur**'a bas ve bitmesini bekle.",
            "**3.** **Önerilen** sekmesindeki en hafif modelin yanındaki **İndir**'e bas.",
            "**4.** İndirme bitince **İndirilenler** sekmesinde **AI Panelinde kullan**'a bas.",
            "**5.** Sağdaki AI Asistan'a \"Merhaba!\" yaz. İlk cevap biraz gecikebilir, model uyanıyor!",
        ]),
        ("kutu", "bilgi", "Büyükler için: arama ve öneri listesi uygunsuz içerikli modelleri (sansürsüz, "
                          "yetişkin içerikli, rol yapma vb.) kendiliğinden gizler. Yerel model sunucusu yalnızca bu "
                          "bilgisayardan erişilebilir ve program kapanınca durur."),
        ("kutu", "ipucu", "Bilgisayarın güçlüyse daha büyük modeller daha iyi cevap verir; ama önce küçükle başla."),
        ("kodi", "Yerel model, bilgisayarına taşınan küçük bir arkadaş gibi. İnternet kesilse bile seninle "
                 "konuşmaya devam eder!"),
    ]),
    # ------------------------------------------------------------------ 25
    ("Ayarlar: görünüm ve editör", "TürKod'u kendine göre süsle.", [
        ("paragraf", "Ayarlar bir sekme olarak açılır. Bazı ayarlar ancak üstteki **Kaydet ve Uygula** "
                     "düğmesine basınca etkinleşir (tema, yazı, otomatik tamamlama ve kaydetme, satır numaraları, "
                     "kelime kaydırma, boşluk göstergesi, terminal yazısı, AI ortak ayarları, Düzeltme). Diğerleri "
                     "hemen uygulanır."),
        ("tablo", ["Ayar", "Ne işe yarar?"], [
            ["Tema", "Modern Koyu, Koyu, Açık ya da Yüksek Kontrast."],
            ["Yazı Boyutu / Yazı Tipi", "Editör yazısının boyutu (8-32) ve bilgisayarındaki yazı tiplerinden biri."],
            ["Otomatik Tamamlama", "Öneri listesini açar ya da kapatır."],
            ["Otomatik Kaydetme", "Dosyaları belli aralıkla (5-600 saniye) kendiliğinden kaydeder."],
            ["Satır Numaraları", "Soldaki numaraları gösterir."],
            ["Kelime Kaydırma", "Uzun satırları ekrana sığacak şekilde alta kaydırır."],
            ["Boşluk Göstergesi", "Boşlukları soluk noktalarla gösterir."],
            ["Girinti Kılavuzları", "Girinti basamaklarını ince dikey çizgilerle gösterir."],
            ["Mini Harita", "Sağdaki kuş bakışı kod resmi."],
            ["Girinti genişliği", "Bir girinti kaç boşluk olsun: 2, 4 ya da 8."],
            ["Kaydederken biçimlendir", "Her kayıtta kodu toparlar."],
            ["Girintiyi dosyadan algıla", "Dosya hangi girintiyle yazıldıysa onu kullanır."],
            ["Terminal Yazı Boyutu", "Terminal yazısının boyutu (8-28)."],
        ], [1.5, 3]),
        ("resim", "ayarlar_genel.png", "Ayarlar sekmesinin Genel bölümü", 170),
    ]),
    # ------------------------------------------------------------------ 26
    ("Ayarlar: diğerleri", "Tur, Windows bağlantıları, düzeltici.", [
        ("tablo", ["Bölüm", "İçindekiler"], [
            ["Arayüz Turu", "**Her açılışta göster** ve **Turu şimdi başlat**."],
            ["Sistem Entegrasyonu", "**.trpy dosyalarını TürKod ile ilişkilendir** (çift tıklayınca çalışır, sağ "
                                    "tıkta \"Editör ile aç\") ve **TürKod'u PATH'e ekle** (her terminalde `turkod` "
                                    "komutu). Yönetici izni gerekmez."],
            ["Yapay Zekâ: Görevler / Modeller", "Önceki sayfalarda anlattık. Hayalet kodun bekleme süresi ve çok "
                                                "satırlı öneri de buradadır."],
            ["Düzeltme", "Akıllı Düzelt'in deneme süresi (saniye), mesaj aralığı ve en fazla deneme sayısı."],
        ], [1.4, 3.2]),
        ("kodi", "Ayarları kurcalamaktan korkma! Bir şeyi beğenmezsen aynı yerden eski hâline döndürebilirsin."),
        ("kutu", "gorev", "Temayı **Açık** yap, Kaydet ve Uygula'ya bas. Hangisini daha çok sevdin? Sonra "
                          "istersen **Modern Koyu**'ya geri dön."),
    ]),
    # ------------------------------------------------------------------ 26b
    ("Klavye kısayollarını değiştirmek", "Tuşlar senin sözünü dinlesin.", [
        ("paragraf", "Görünüm → **Klavye Kısayolları…** (ya da Ayarlar'daki düğme) bütün komutları kısayollarıyla "
                     "listeler. Bir komutun yanındaki kaleme bas, istediğin tuş birleşimine bas, **Ata** de. O tuş "
                     "başka bir komutta kullanılıyorsa \"Kısayol kullanımda\" uyarısı çıkar. **Varsayılana "
                     "döndür** tek komutu, **Tümünü Sıfırla** hepsini eski hâline getirir. Yeni kısayol menülerde "
                     "ve araç çubuğunda da görünür."),
        ("resim", "klavye_kisayollari.png", "Klavye Kısayolları penceresi: kalemle değiştir, okla varsayılana döndür",
         260),
        ("kutu", "dikkat", "Yorum, satır çoğaltma, satır taşıma, çoklu imleç, `F2`, `F12` gibi kısayollar yalnızca "
                           "imleç editördeyken çalışır. Açık bir pencere varken kısayollar çalışmaz."),
    ]),
    # ------------------------------------------------------------------ 27
    ("Eklenti Özellikleri", "İstediğin ek özellikleri aç, kapat.", [
        ("paragraf", "Aktivite çubuğundaki yapboz düğmesi (ya da `Ctrl+Shift+X`) eklentiler panelini açar. En "
                     "üstte Yerel AI Modelleri kartı, altında eklentiler durur. **Etkinleştir** ile açar, **Devre "
                     "dışı bırak** ile kapatırsın. Kapalı bir eklentinin özelliğini kullanmak istersen TürKod "
                     "\"açayım mı?\" diye sorar."),
        ("tablo", ["Eklenti", "Ne yapar?"], [
            ["Kod Parçacıkları", "Hazır kod kalıpları: ana program, sayı tahmin oyunu, doğrulamalı sayı girdisi, "
                                 "dosya okuma/yazma, numaralı döngü, sözlük döngüsü, sınıf, hata yakalama, bekleme. "
                                 "**Seçili kodu parçacık yap** ile kendi kalıplarını da eklersin."],
            ["Odak Zamanlayıcı", "Durum çubuğunda 25 dakikalık çalışma saati, sonra 5 dakika mola (her 4 turda 15). "
                                 "Tıklayınca başlar/duraklar, sağ tıklayınca sıfırlanır."],
            ["Markdown Önizleme", ".md not dosyalarını başlıkları, listeleri ve tablolarıyla süslü gösterir."],
            ["Karalama Defteri", "Kendini kaydeden bir not defteri; **İmlece ekle** ile notunu koda koyar."],
            ["Günün Görevi", "Her gün yeni bir programlama görevi ve ipucu. **Başka görev** ya da **Yeni sekmede "
                             "başla**."],
        ], [1.2, 3.4]),
        ("kutu", "gorev", "Günün Görevi eklentisini aç ve bugünün görevini çözmeye çalış!"),
    ]),
    # ------------------------------------------------------------------ 28
    ("TürKod Kabuğu", "Kodu satır satır deneyeceğin oyun alanı.", [
        ("paragraf", "Kabuk, tek satırlık kodları hemen denediğin bir oyun alanıdır. Aktivite çubuğundan, "
                     "`Ctrl+Shift+K` ile ya da terminaldeki **TürKod Kabuğu** düğmesiyle açılır. `TürKod>` yazısının "
                     "yanına bir satır yaz, Enter'a bas, sonuç hemen gelsin! Bloklar (`eğer`, `için` ...) boş bir "
                     "satır gelene kadar devam eder. Kutuların kabuk açık kaldıkça unutulmaz."),
        ("resim", "kabuk.png", "Terminalde TürKod Kabuğu: anlam yazdır ve dersler komutları", 230),
        ("baslik", "Kabuktaki 10 ders"),
        ("paragraf", "1 Ekrana yazdırma, 2 Değişkenler, 3 Kullanıcıdan girdi alma, 4 Karar verme (eğer), "
                     "5 Döngüler (için / döngü), 6 Listeler, 7 Fonksiyonlar, 8 Sözlükler, 9 Hataları yakalama, "
                     "10 Sınıflar. Her dersin bir açıklaması, örneği ve görevi var: `ders 5` dersi gösterir, "
                     "`dene 5` örneğini çalıştırır."),
    ]),
    # ------------------------------------------------------------------ 28b
    ("Kabuk komutları", "TürKod Kabuğu'nda yazabileceğin komutlar.", [
        ("tablo", ["Komut", "Ne yapar?"], [
            ["`yardım`", "Komutları listeler."],
            ["`dersler` / `ders 3` / `dene 3`", "Dersleri listeler / 3. dersi gösterir / örneğini çalıştırır."],
            ["`anlam yazdır`", "Kelimenin anlamını söyler. Python kelimesi yazarsan (`print`) TürKod karşılığını "
                               "bulur."],
            ["`çevir` / `pyçevir`", "TürKod → Python / Python → TürKod çevirir."],
            ["`çalıştır dosya.trpy`", "Bir dosyayı çalıştırır."],
            ["`kontrol`, `düzelt`, `biçimlendir`, `pythona`", "Dosyayı denetler, düzeltir, toparlar, Python hâlini "
                                                              "gösterir."],
            ["`exe_yap dosya.trpy` / `kaynak oyun.exe`", "Programı EXE yapar / EXE'nin kodunu gösterir."],
            ["`değişkenler` / `sıfırla`", "Kutuları listeler / hepsini siler."],
            ["`temizle`, `editör`, `sürüm`, `çıkış`", "Ekranı temizler, editörü açar, sürümü söyler, çıkar."],
            ["`logo`", "TürKod logosunu harflerle bütün terminale kocaman çizer."],
        ], [1.7, 2.9]),
        ("kutu", "ipucu", "Bir komutla aynı adda bir kutun varsa satırın başına nokta koy: `.yardım` her zaman "
                          "komut olarak çalışır."),
        ("kutu", "gorev", "Kabuğu aç ve `ders 1` yaz. Sonra `dene 1` ile örneğini çalıştır."),
    ]),
    # ------------------------------------------------------------------ 29
    ("Python ile köprü", "İnternetteki Python kodlarını TürKod'a çevir.", [
        ("baslik", "TürKod ⇄ Python Çevir"),
        ("paragraf", "Bu düğme açık dosyanın hangi dilde yazıldığını kendisi anlar ve öbür dile çevirip yeni bir "
                     "sekmede açar (\"cevrilmis.py\" ya da \"cevrilmis.trpy\"). İnternette bulduğun bir Python "
                     "kodunu TürKod'a çevirmek için birebir:"),
        ("kod", "python_kodu.py", ['for sayı in range(3):', '    print(sayı)']),
        ("kod", "cevrilmis.trpy", ['için sayı aralık(3):', '    yazdır(sayı)']),
        ("baslik", "Kod Arama Çevirici"),
        ("paragraf", "Araçlar menüsünden ya da durum çubuğundan açılır. Kutuya `print` ya da `def` gibi bir Python "
                     "kelimesi veya kodu yazıp **Çevir**'e bas: \"KELİME KARŞILIKLARI\" her kelimenin TürKod "
                     "karşılığını, \"TAM KOD ÇEVRİSİ\" kodun tamamını gösterir."),
        ("resim", "kod_arama.png", "Kod Arama Çevirici: print → yazdır", 140),
    ]),
    # ------------------------------------------------------------------ 29b
    ("İstatistik ve yapılacaklar", "Kodunu say, notlarını topla.", [
        ("paragraf", "**Kod İstatistikleri** kodunda kaç satır, kaç yorum, kaç karakter, kaç fonksiyon, sınıf ve "
                     "kutu olduğunu sayar. Ne kadar çok yazdığını görmek çok keyifli!"),
        ("paragraf", "**Yapılacaklar Listesi** yorumlarına bıraktığın `# YAPILACAK: ...` gibi notları toplar. "
                     "Büyük harfle yazılmış YAPILACAK ve DÜZELT kelimelerini tanır; İngilizce TODO ve FIXME de "
                     "olur. Bir notun yanındaki **Git** düğmesi seni o satıra götürür."),
        ("kod", "notlu.trpy", ['# YAPILACAK: oyuna puan tablosu ekle', 'yazdır("Oyun başlıyor!")']),
        ("kodi", "Yarım bıraktığın işleri `# YAPILACAK:` ile not et. Ertesi gün Yapılacaklar Listesi'ne bakınca "
                 "nerede kaldığını hemen hatırlarsın!"),
        ("kutu", "gorev", "Kodunun başına bir `# YAPILACAK:` notu yaz ve Yapılacaklar Listesi'nde göründüğünü "
                          "kontrol et."),
    ]),
    # ------------------------------------------------------------------ 30
    ("Programı Windows'tan kullanmak", "IDE'yi açmadan da TürKod çalışır.", [
        ("paragraf", "Ayarlar'da dosya ilişkilendirmesi açıksa bir .trpy dosyasına **çift tıkladığında** kodun "
                     "koyu renkli küçük bir TürKod penceresinde çalışır. Hata satırları kırmızı görünür."),
        ("tablo", ["Tuş", "Pencerede ne yapar?"], [
            ["`F5` / `Ctrl+R`", "Yeniden çalıştırır."],
            ["`Ctrl+C`", "Hiçbir şey seçili değilken programı durdurur."],
            ["`Ctrl+E`", "Dosyayı editörde açar."],
            ["`Ctrl+L`", "Ekranı temizler."],
            ["`↑` / `↓`", "Önceki cevapların arasında gezer."],
            ["`Esc`", "Pencereyi kapatır."],
        ], [1, 3]),
        ("kutu", "ipucu", "Bitirdiğin bir oyunu arkadaşına göstermek için TürKod'u açmana gerek yok: dosyaya çift "
                          "tıklaman yeter! Arkadaşının bilgisayarında TürKod yoksa oyununu EXE yap (sonraki "
                          "sayfa)."),
    ]),
    # ------------------------------------------------------------------ 30a
    ("Programını EXE yapmak", "Oyununu TürKod'u olmayan arkadaşına hediye et!", [
        ("paragraf", "Bir oyun yaptın ve arkadaşına göstermek istiyorsun ama onun bilgisayarında TürKod yok. "
                     "Sorun değil! **Çalıştır → EXE'ye Dönüştür…** programını bir **EXE** dosyasına çevirir. "
                     "EXE, Windows'un \"çift tıkla, çalışsın\" dediği dosyadır; içine programın ve onu çalıştıracak "
                     "her şey konur, tıpkı bir hediye paketi gibi."),
        ("resim", "exe_paneli.png", "EXE'ye Dönüştür paneli: ad, kaydedileceği klasör ve programın açılış biçimi",
         350),
        ("maddeler", [
            "**EXE'nin adı:** boş bırakırsan kod dosyanın adı kullanılır.",
            "**Kaydedileceği klasör:** Gözat ile seç; boşsa EXE kod dosyanın yanına konur.",
            "**Program nasıl açılsın?** TürKod terminali, siyah Windows konsolu ya da hiç terminal olmadan. "
            "Programın `girdi_al` ile soru soruyorsa \"Terminal olmadan\"ı seçme: cevabı yazacak yer olmaz.",
        ]),
        ("kodi", "Dosyanı kaydetmeyi unuttuysan dert etme: panel açılmadan önce TürKod onu senin için kaydeder."),
    ]),
    # ------------------------------------------------------------------ 30b
    ("EXE seçenekleri", "Tikleri işaretle, komut kendini yazsın.", [
        ("paragraf", "Panelin alt kısmında birkaç seçenek daha var. Her tik attığında en alttaki **Çalışacak "
                     "komut** kutusu kendiliğinden değişir. **EXE'ye Dönüştür** düğmesi bu komutu sekmenin "
                     "terminalinde çalıştırır; birkaç dakika sonra EXE hazırdır."),
        ("resim", "exe_paneli_alt.png", "Seçenekler, simge, eklenecek dosyalar ve canlı değişen komut", 330),
        ("tablo", ["Paneldeki seçenek", "Komuttaki hâli"], [
            ["EXE'nin adı / kaydedileceği klasör", "`--ad \"Oyunum\"` / `--kayit-yeri \"C:\\Oyunlar\"`"],
            ["Windows konsolunda / Terminal olmadan", "`--windows-konsolu` / `--terminalsiz`"],
            ["Kaynak koduna bakılabilsin", "`--kaynak-acik`"],
            ["Tek dosya yerine klasör yap", "`--klasorlu`"],
            ["Program bitince pencere kapanmasın", "`--sonda-bekle`"],
            ["Simge / Dosya ekle", "`--simge simge.ico` / `--dosya-ekle resimler`"],
        ], [2.2, 2.4]),
    ]),
    # ------------------------------------------------------------------ 30c
    ("EXE'yi terminalden yapmak", "Aynı işi tek bir komutla da yapabilirsin.", [
        ("paragraf", "Paneldeki komutu terminale ya da TürKod Kabuğu'na kendin de yazabilirsin. Seçenekler "
                     "`--` ile başlar. Kabukta baştaki `turkod` kelimesini yazmasan da olur:"),
        ("terminal", [
            '> turkod exe_yap sayi_tahmin.trpy --ad "Sayı Tahmin Oyunu" --kaynak-acik',
            "[EXE] sayi_tahmin.trpy -> Sayı Tahmin Oyunu.exe",
            "[EXE] Paketleniyor; bu işlem birkaç dakika sürebilir...",
            "[EXE] Kod ve kullandığı kütüphaneler inceleniyor...",
            "[EXE] Python dosyaları paketleniyor...",
            "[EXE] Program dosyaları birleştiriliyor...",
            "[EXE] EXE dosyası oluşturuluyor...",
            "[EXE] Hazır! (51 sn, 32.9 MB)",
        ]),
        ("paragraf", "Bütün seçenekleri görmek için `turkod exe_yap --yardim` yaz. Programın resim ya da ses "
                     "kullanıyorsa `--dosya-ekle` ile onları da EXE'nin içine koy; yoksa program arkadaşının "
                     "bilgisayarında onları bulamaz. Unutursan TürKod seni uyarır: kodunda adı geçen ama "
                     "eklenmemiş dosyalar için `[UYARI]` satırı yazar."),
        ("kutu", "dikkat", "İlk EXE'yi yaparken TürKod, EXE yapma aracını (PyInstaller) internetten bir kere "
                           "indirir. Bu yüzden ilk seferde internet gerekir ve biraz daha uzun sürer."),
        ("kutu", "ipucu", "Bir sorun çıkarsa TürKod onu da Türkçe anlatır (\"Simge dosyası bulunamadı\", "
                          "\"İnternete bağlanılamadı\" ...). Çevirisini henüz bilmediği bir ileti olursa onu "
                          "\"İngilizce\" diye ayrıca gösterir; büyüklerden yardım isteyebilirsin."),
        ("kodi", "EXE yapılırken bilgisayar biraz düşünür. Bir bardak su içip gel, paketin hazır olsun!"),
    ]),
    # ------------------------------------------------------------------ 30d
    ("EXE çalışınca", "Arkadaşın çift tıkladığında ne görür?", [
        ("paragraf", "\"TürKod terminalinde\" seçtiysen EXE, IDE'deki gibi koyu renkli bir TürKod penceresinde "
                     "açılır. Program soru sorunca cevap alttaki satıra yazılır; hatalar Türkçe ve kırmızıdır. "
                     "Kullandığın kütüphanelerin İngilizce iletileri de (ör. pygame'in \"Hello from the pygame "
                     "community\" selamı) hem bu pencerede hem Windows konsolunda Türkçe görünür."),
        ("resim", "exe_terminali.png", "Sayı Tahmin Oyunu.exe çalışırken: altta Kaynak kodu, Durdur, Yeniden "
                                       "başlat ve Kapat düğmeleri", 150),
        ("baslik", "EXE'nin kaynak koduna bakmak"),
        ("paragraf", "**Kaynak koduna bakılabilsin** işaretliyse EXE'nin içindeki TürKod kodunu görebilirsin: "
                     "penceredeki **Kaynak kodu** düğmesiyle, **Çalıştır → EXE'nin Kaynak Kodunu Aç…** ile "
                     "(kod yeni bir sekmede açılır) ya da terminalde:"),
        ("terminal", [
            '> turkod kaynak "Sayı Tahmin Oyunu.exe"',
            "içe_aktar rastgele",
            "",
            "gizli = rastgele.tamsayı(1, 10)",
        ]),
        ("paragraf", "Sonuna `--kaydet` eklersen kod bir .trpy dosyasına kaydedilir. İşaretli değilse EXE "
                     "\"Bu programın kaynak kodu gizli\" der: içinde yalnızca kodunun bilgisayarın anladığı "
                     "derlenmiş hâli vardır."),
        ("kutu", "gorev", "Merhaba Dünya programını \"Kaynak koduna bakılabilsin\" işaretli olarak EXE yap. Sonra "
                          "`turkod kaynak` ile kodunu geri getir!"),
    ]),
    # ------------------------------------------------------------------ 30b
    ("Güncellemeler ve imza", "TürKod kendini nasıl yeniler?", [
        ("paragraf", "TürKod açıldıktan birkaç saniye sonra sessizce yeni bir sürüm çıkmış mı diye bakar. Çıktıysa "
                     "yenilikleriyle birlikte **Yükle** ya da **Atla** diye sorar. İndirilen kurulum dosyası, "
                     "kurulumdan önce iki kez kontrol edilir (dijital imza ve SHA-256 özeti); açık dosyaların da "
                     "önce kaydedilir."),
        ("baslik", "Hakkında / İmza"),
        ("paragraf", "Bu pencere TürKod'un sürümünü, lisansını ve **dijital imzasını** gösterir. İmza, bir mektubun "
                     "üstündeki mühür gibidir: program dosyalarının yolda kimse tarafından değiştirilmediğini "
                     "kanıtlar."),
        ("resim", "hakkinda.png", "Hakkında penceresinin üst kısmı: sürüm ve bağlantılar", 110),
        ("kutu", "dikkat", "Güncellemeyi ve kurulumu bir büyüğünle birlikte yap. TürKod'u yalnızca resmî siteden indir."),
    ]),
    # ------------------------------------------------------------------ 31
    ("Kısayol kopya kâğıdı", "En çok kullanacağın tuşlar bir arada.", [
        ("tablo", ["Tuş", "İş", "Tuş", "İş"], [
            ["`Ctrl+R`", "Çalıştır", "`Ctrl+S`", "Kaydet"],
            ["`Ctrl+T`", "Yeni sekme", "`Ctrl+O`", "Dosya aç"],
            ["`Ctrl+W`", "Sekmeyi kapat", "`Ctrl+Shift+S`", "Tümünü kaydet"],
            ["`Ctrl+Z` / `Ctrl+Y`", "Geri al / yinele", "`Ctrl+/`", "Yorum aç/kapat"],
            ["`Ctrl+F`", "Bul", "`Ctrl+H`", "Bul / Değiştir"],
            ["`Ctrl+G`", "Satıra git", "`Ctrl+Shift+F`", "Dosyalarda ara"],
            ["`F2`", "Adı değiştir", "`F12`", "Tanıma git"],
            ["`Shift+Alt+F`", "Biçimlendir", "`Ctrl+Shift+D`", "Satırı çoğalt"],
            ["`Alt+↑` / `Alt+↓`", "Satırı taşı", "`Ctrl+D`", "Sonraki eşleşme"],
            ["`Ctrl+J`", "Terminal aç/kapat", "`Ctrl+\\`", "Editörü böl"],
            ["`Ctrl+Shift+P`", "Komut paleti", "`Ctrl+Shift+M`", "Sorunlar"],
            ["`Ctrl+Shift+K`", "TürKod Kabuğu", "`Ctrl+Shift+X`", "Eklentiler"],
            ["`F9`", "Kesme noktası", "`F5`", "Hata ayıkla / devam"],
            ["`F10` / `F11`", "Adım at / içine gir", "`Shift+F5`", "Hata ayıklamayı durdur"],
            ["`Ctrl+Shift+Space`", "AI önerisi", "`Tab`", "Öneriyi kabul et"],
            ["`Ctrl` + tekerlek", "Yakınlaştır", "`Esc`", "Kutuyu / öneriyi kapat"],
            ["`F1`", "Kodi'yi çağır", "", ""],
        ], [1.25, 1.35, 1.25, 1.35]),
        ("kutu", "gorev", "Bu sayfadaki her kısayolu bir kere dene. Hangisini en çok kullanacağını düşünüyorsun?"),
        ("kodi", "Tebrikler, programın her köşesini gezdin! Artık TürKod'u benim kadar iyi tanıyorsun. "
                 "Haydi şimdi kendi oyununu yazma zamanı!"),
    ]),
]
