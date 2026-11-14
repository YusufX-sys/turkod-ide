"""Kitaptaki (TürKod ile Kodlama Macerası) kod örneklerini, Flutter arayüzünün
kullandığı WebSocket protokolüyle gerçek arka uçta çalıştırır ve çıktıyı
kitaptaki çıktıyla karşılaştırır. Ayrıca her örneği Python'a ve geri TürKod'a
çevirip önerilen (kanonik) yazımdan sapmaları listeler: kitaptaki yazım,
çeviricinin ürettiğinden farklıysa kitap eskimiş demektir.

Kitapta bir örnek değişirse buradaki ORNEKLER listesini de güncelleyin.
Kullanım (proje kökünde): python tools/kitap/kitap_ornek_testi.py"""
import asyncio, os, sys
PROJE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJE, "tests"))
sys.path.insert(0, PROJE)
import e2e_backend as e2e
from turkod_ide.converter import turkce_kodu_donustur, python_kodu_turkceye_cevir

D = "için"

ORNEKLER = [
    ("ilk-programım", 'yazdır("Merhaba, dünya!")', [], "Merhaba, dünya!"),
    ("kodi", 'yazdır("Merhaba!")\nyazdır("Ben Kodi, bir robotum.")\nyazdır("Seninle tanıştığıma sevindim!")', [],
     "Merhaba!\nBen Kodi, bir robotum.\nSeninle tanıştığıma sevindim!"),
    ("yorum", '# Bu satırı bilgisayar okumaz\nyazdır("Bu satırı okur!")', [], "Bu satırı okur!"),
    ("altsatir", 'yazdır("Birinci satır\\nİkinci satır")', [], "Birinci satır\nİkinci satır"),
    ("kutular", 'isim = "Deniz"\nyaş = 7\nyazdır(isim)\nyazdır(yaş)', [], "Deniz\n7"),
    ("değiştir", 'puan = 5\nyazdır(puan)\npuan = 10\nyazdır(puan)', [], "5\n10"),
    ("artır", 'puan = 5\npuan = puan + 1\nyazdır(puan)\npuan += 4\nyazdır(puan)', [], "6\n10"),
    ("birleştir", 'isim = "Deniz"\nyaş = 7\nyazdır(f"Ben {isim}, {yaş} yaşındayım.")', [], "Ben Deniz, 7 yaşındayım."),
    ("tür-sor", 'yazdır(tip("elma"))\nyazdır(tip(7))\nyazdır(tip(3.5))\nyazdır(tip(Doğru))\nyazdır(tip([1, 2, 3]))', [],
     "<class 'str'>\n<class 'int'>\n<class 'float'>\n<class 'bool'>\n<class 'list'>"),
    ("dönüştür", 'a = "7"\nb = tamsayı(a) + 1\nyazdır(b)\nyazdır(tip(a))\nyazdır(tip(b))', [], "8\n<class 'str'>\n<class 'int'>"),
    ("yapıştır", 'yaş = 7\nyazdır("Yaşım: " + metin(yaş))\nyazdır(f"Yaşım: {yaş}")', [], "Yaşım: 7\nYaşım: 7"),
    ("hesap", 'yazdır(6 + 4)\nyazdır(6 - 4)\nyazdır(6 * 4)\nyazdır(8 / 2)\nyazdır(7 // 2)\nyazdır(7 % 2)\nyazdır(2 ** 3)', [],
     "10\n2\n24\n4.0\n3\n1\n8"),
    ("sıra", 'yazdır(2 + 3 * 4)\nyazdır((2 + 3) * 4)', [], "14\n20"),
    ("ondalık", 'boy = 1.25\nyazdır(boy * 2)\nyazdır(yuvarla(3.7))\nyazdır(yuvarla(3.14159, 2))\nyazdır(mutlak(-7))', [],
     "2.5\n4\n3.14\n7"),
    ("kütüphane", 'içe_aktar matematik\n\nyazdır(matematik.karekök(16))\nyazdır(yuvarla(matematik.pi_sayısı, 2))', [], "4.0\n3.14"),
    ("yazı-oyunu", 'ad = "deniz"\nyazdır(ad.büyük_harf())\nyazdır(ad.baş_harf_büyük())\nyazdır(uzunluk(ad))\nyazdır("MERHABA".küçük_harf())', [],
     "DENIZ\nDeniz\n5\nmerhaba"),
    ("harf", 'ad = "kedi"\nyazdır(ad[0])\nyazdır(ad[3])\nyazdır(ad[-1])\nyazdır(uzunluk(ad))', [], "k\ni\ni\n4"),
    ("çoğalt", 'yazdır("Kodi" + " " + "robot")\nyazdır("Ha" * 3)\nyazdır("-" * 10)', [], "Kodi robot\nHaHaHa\n----------"),
    ("içinde", 'yazdır("ed" içinde "kedi")\nyazdır("z" içinde "kedi")', [], "Doğru\nYanlış"),
    ("merhaba", 'isim = girdi_al("Adın ne? ")\nyazdır(f"Merhaba {isim}!")', ["Deniz"], "Merhaba Deniz!"),
    ("yaş", 'yaş = tamsayı(girdi_al("Kaç yaşındasın? "))\nyazdır(f"Gelecek yıl {yaş + 1} yaşında olacaksın!")', ["7"],
     "Gelecek yıl 8 yaşında olacaksın!"),
    ("yapışma", 'a = girdi_al("Bir sayı yaz: ")\nyazdır(a + "1")', ["7"], "71"),
    ("sohbet", 'ad = girdi_al("Merhaba! Adın ne? ")\nrenk_adı = girdi_al("En sevdiğin renk ne? ")\nyaş = tamsayı(girdi_al("Kaç yaşındasın? "))\n\n'
     'yazdır(f"Memnun oldum {ad}!")\nyazdır(f"Ben de {renk_adı} rengini severim.")\nyazdır(f"5 yıl sonra {yaş + 5} yaşında olacaksın.")',
     ["Deniz", "mavi", "7"], "Memnun oldum Deniz!\nBen de mavi rengini severim.\n5 yıl sonra 12 yaşında olacaksın."),
    ("eğer", 'yaş = 8\neğer yaş >= 7:\n    yazdır("Okula gidebilirsin!")', [], "Okula gidebilirsin!"),
    ("değilse", 'hava = "yağmurlu"\neğer hava == "güneşli":\n    yazdır("Parka gidelim!")\ndeğilse:\n    yazdır("Evde oyun oynayalım!")', [],
     "Evde oyun oynayalım!"),
    ("madalya", 'puan = 75\neğer puan >= 90:\n    yazdır("Harika! Altın madalya!")\ndeğilse_eğer puan >= 60:\n    yazdır("Güzel! Gümüş madalya!")\n'
     'değilse:\n    yazdır("Bir daha dene, olur!")', [], "Güzel! Gümüş madalya!"),
    ("iki-eşittir", 'yaş = 7\neğer yaş == 7:\n    yazdır("Yedi yaşındasın!")', [], "Yedi yaşındasın!"),
    ("hız-treni", 'yaş = 8\nboy = 130\neğer yaş >= 7 ve boy >= 120:\n    yazdır("Hız treni seni bekliyor!")', [], "Hız treni seni bekliyor!"),
    ("veya-değil", 'güneş = Yanlış\nyağmur = Doğru\neğer güneş veya yağmur:\n    yazdır("Dışarıda hava değişik!")\neğer değil güneş:\n'
     '    yazdır("Güneş yok, ceket giy!")', [], "Dışarıda hava değişik!\nGüneş yok, ceket giy!"),
    ("zıpla", f'{D} i aralık(5):\n    yazdır("Zıpla!")', [], "Zıpla!\n" * 4 + "Zıpla!"),
    ("sayaç", f'{D} i aralık(3):\n    yazdır(i)', [], "0\n1\n2"),
    ("roket", f'{D} sayı aralık(5, 0, -1):\n    yazdır(sayı)\nyazdır("Fırla!")', [], "5\n4\n3\n2\n1\nFırla!"),
    ("enerji", 'enerji = 3\ndöngü enerji > 0:\n    yazdır(f"Enerji: {enerji}")\n    enerji = enerji - 1\nyazdır("Uyku zamanı!")', [],
     "Enerji: 3\nEnerji: 2\nEnerji: 1\nUyku zamanı!"),
    ("kır", f'{D} sayı aralık(1, 10):\n    eğer sayı == 4:\n        kır\n    yazdır(sayı)', [], "1\n2\n3"),
    ("devam", f'{D} sayı aralık(1, 6):\n    eğer sayı == 3:\n        devam_et\n    yazdır(sayı)', [], "1\n2\n4\n5"),
    ("içiçe", f'{D} satır aralık(1, 4):\n    {D} sütun aralık(1, 4):\n        yazdır(f"{{satır}} x {{sütun}} = {{satır * sütun}}")\n    yazdır("---")', [],
     "\n".join(f"{a} x {b} = {a*b}" + ("\n---" if b == 3 else "") for a in range(1, 4) for b in range(1, 4))),
    ("meyveler", 'meyveler = ["elma", "armut", "kiraz"]\nyazdır(meyveler)\nyazdır(uzunluk(meyveler))', [], "['elma', 'armut', 'kiraz']\n3"),
    ("vagon-oku", 'meyveler = ["elma", "armut", "kiraz"]\nyazdır(meyveler[0])\nyazdır(meyveler[2])\nyazdır(meyveler[-1])', [], "elma\nkiraz\nkiraz"),
    ("vagon-ekle", 'meyveler = ["elma", "armut"]\nmeyveler.sona_ekle("kiraz")\nyazdır(meyveler)', [], "['elma', 'armut', 'kiraz']"),
    ("sıralama", 'meyveler = ["elma", "armut"]\nmeyveler.sona_ekle("kiraz")\nyazdır(meyveler)\nmeyveler.sırala()\nyazdır(meyveler)\n'
     'meyveler.tersine_çevir()\nyazdır(meyveler)', [],
     "['elma', 'armut', 'kiraz']\n['armut', 'elma', 'kiraz']\n['kiraz', 'elma', 'armut']"),
    ("notlar", 'notlar = [70, 85, 100]\nyazdır(toplam(notlar))\nyazdır(en_büyük(notlar))\nyazdır(en_küçük(notlar))', [], "255\n100\n70"),
    ("dolaş", f'meyveler = ["elma", "armut", "kiraz"]\n{D} meyve içinde meyveler:\n    yazdır(f"Ben {{meyve}} seviyorum!")', [],
     "Ben elma seviyorum!\nBen armut seviyorum!\nBen kiraz seviyorum!"),
    ("liste-içinde", 'meyveler = ["elma", "armut", "kiraz"]\nyazdır("armut" içinde meyveler)\nyazdır("muz" içinde meyveler)', [], "Doğru\nYanlış"),
    ("selamla", 'fonksiyon selamla(isim):\n    yazdır(f"Merhaba {isim}!")\n\nselamla("Deniz")\nselamla("Ada")', [], "Merhaba Deniz!\nMerhaba Ada!"),
    ("kare", 'fonksiyon kare(x):\n    döndür x * x\n\nyazdır(kare(4))\nyazdır(kare(7))', [], "16\n49"),
    ("topla-iki", 'fonksiyon topla(a, b):\n    döndür a + b\n\nsonuç = topla(3, 4)\nyazdır(f"Sonuç: {sonuç}")', [], "Sonuç: 7"),
    ("varsayılan", 'fonksiyon selamla(isim, mesaj="Merhaba"):\n    yazdır(f"{mesaj} {isim}!")\n\nselamla("Deniz")\nselamla("Ada", "Selam")', [],
     "Merhaba Deniz!\nSelam Ada!"),
    ("hata1", 'yazdır(isim)', [], "Tanımsız İsim Hatası"),
    ("hata3", 'yazdır(10 / 0)', [], "Sıfıra Bölme Hatası"),
    ("hata4", 'yaş = 7\nyazdır("Yaşım: " + yaş)', [], "Veri Tipi Hatası"),
    ("hata6", 'liste = [1, 2, 3]\nyazdır(liste[10])', [], "Liste İndeks Hatası"),
    ("yaş-kahramanı", 'yaş = tamsayı(girdi_al("Kaç yaşındasın? "))\neğer yaş < 3:\n    yazdır("Bebek kod kahramanı!")\ndeğilse_eğer yaş < 13:\n'
     '    yazdır("Çocuk kod kahramanı!")\ndeğilse:\n    yazdır("Büyük kod kahramanı!")', ["7"], "Çocuk kod kahramanı!"),
    ("alışveriş", 'alışveriş = ["süt", "ekmek"]\nalışveriş.sona_ekle("elma")\nalışveriş.sona_ekle("çilek")\nalışveriş.sırala()\n'
     'yazdır(f"Alacaklarım: {alışveriş}")\nyazdır(f"Toplam {uzunluk(alışveriş)} şey")', [],
     "Alacaklarım: ['ekmek', 'elma', 'süt', 'çilek']\nToplam 4 şey"),
    ("çarpım-tablosu", f'sayı = tamsayı(girdi_al("Hangi sayının tablosu? "))\n{D} i aralık(1, 11):\n    yazdır(f"{{sayı}} x {{i}} = {{sayı * i}}")', ["4"],
     "\n".join(f"4 x {i} = {4*i}" for i in range(1, 11))),
    ("tahmin", 'gizli_sayı = 6\ntahmin = tamsayı(girdi_al("1-10 arası bir sayı tahmin et: "))\n\neğer tahmin == gizli_sayı:\n    yazdır("Bildin! Tebrikler!")\n'
     'değilse_eğer tahmin < gizli_sayı:\n    yazdır("Daha büyük bir sayı dene.")\ndeğilse:\n    yazdır("Daha küçük bir sayı dene.")', ["4"],
     "Daha büyük bir sayı dene."),
    ("rastgele", 'içe_aktar rastgele\ngizli_sayı = rastgele.tamsayı(1, 10)\nyazdır(1 <= gizli_sayı <= 10)', [], "Doğru"),
    ("bilmece7", 'x = 4\neğer x > 3 ve x < 10:\n    yazdır("Evet")\ndeğilse:\n    yazdır("Hayır")', [], "Evet"),
    ("bilmece8", 'ad = "ada"\nyazdır(ad.büyük_harf())', [], "ADA"),
]
# Pencere açan kaplumbağa örneği yalnızca çevrilir (çalıştırılmaz).
KAPLUMBAGA = ('içe_aktar kaplumbağa\n\niçin i aralık(4):\n    kaplumbağa.ileri(100)\n'
              '    kaplumbağa.sağa_dön(90)\n\nkaplumbağa.tamamla()')


def kanonik_farklar():
    print("=== Gidiş-dönüş (TürKod -> Python -> TürKod) farkları ===")
    for ad, kod, _, _ in ORNEKLER + [("kare-çiz", KAPLUMBAGA, [], "")]:
        py = turkce_kodu_donustur(kod)
        geri = python_kodu_turkceye_cevir(py)
        if geri.strip() != kod.strip():
            print(f"--- {ad}\n  kitap: {kod!r}\n  kanon: {geri!r}")
    print("kare-çiz Python:\n" + turkce_kodu_donustur(KAPLUMBAGA))


async def senaryolar(c):
    for ad, kod, girdiler, beklenen in ORNEKLER:
        r, bitti, cikti = await e2e.calistir_ve_bekle(c, kod, girdiler)
        temiz = cikti.replace("\r", "")
        ok = bitti is not None and beklenen in temiz
        e2e.kaydet(ad, ok, "" if ok else f"çıktı={temiz[-300:]!r}")


e2e.senaryolar = senaryolar
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kanonik_farklar()
    basarili = asyncio.run(e2e.ana())
    sys.exit(0 if basarili else 1)
