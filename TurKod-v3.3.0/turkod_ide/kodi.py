"""Kodi: kitaptaki sevimli robot, programın içinde yardımcı olarak.

Kodi'nin kimliği (konuşma biçimi, programın temel bilgileri) her istekte
sistem mesajı olarak gider. Programın her köşesini anlatan kılavuz çok uzun
olduğundan (küçük yerel modellerin bağlamına ve ücretsiz sağlayıcıların
sınırına sığmaz) sistem mesajında yalnızca bölüm başlıkları bulunur; model
gerek gördüğü bölümü {"eylem": "kilavuz", "bolum": ...} ile ister, motor
bölümü bulup modele verir (kodi_kilavuz.py, kitaptan üretilir). Mesajın
kelimelerine bakılarak hiçbir karar verilmez; her istek aynı yapıdadır.
"""
import json
import re

try:
    from .kodi_kilavuz import BOLUMLER, KITAP_BOLUMLERI
except ImportError:  # turkod_ide klasörü sys.path'teyken (paketlenmiş arka uç)
    from kodi_kilavuz import BOLUMLER, KITAP_BOLUMLERI

YAPIMCI = "Yusuf Tandoğan"
EPOSTA = "yusuftndgn.2@gmail.com"
GITHUB = "https://github.com/YusufX-sys/turkod-ide"
HATA_BILDIR = GITHUB + "/issues"
SITE = "https://yusufx-sys.github.io/turkod-site/"
KITAP = "TürKod ile Kodlama Macerası"

# Bağlama eklenecek kılavuz metninin üst sınırı (karakter).
BAGLAM_SINIRI = 2500
EN_FAZLA_BOLUM = 2
# Sistem mesajına eklenen etkin kodun ve dosya listesinin sınırı.
KOD_SINIRI = 2000
DOSYA_SINIRI = 30

# Arayüz komut listesini göndermezse Kodi'nin bildiği program komutları:
# kimlik -> etiket. Normalde arayüz programın BÜTÜN komutlarını gönderir.
# Arayüz, güvenli olmayanlar (çalıştırma, kaydetme, kodu değiştirme ...)
# için kullanıcıdan izin ister.
KOMUTLAR = {
    "file.new_tab": "Yeni Sekme",
    "file.save": "Kaydet",
    "file.save_all": "Tümünü Kaydet",
    "run.run": "Çalıştır",
    "run.stop": "Durdur",
    "run.debug_start": "Hata Ayıklamayı Başlat",
    "run.exe": "EXE'ye Dönüştür",
    "edit.format": "Kodu Biçimlendir",
    "edit.find_replace": "Bul / Değiştir",
    "edit.find_in_files": "Dosyalarda Ara",
    "tools.fix": "Akıllı Düzelt",
    "tools.convert": "TürKod ⇄ Python Çevir",
    "tools.stats": "Kod İstatistikleri",
    "tools.todo": "Yapılacaklar Listesi",
    "tools.shell": "TürKod Kabuğu",
    "tools.local_models": "Yerel AI Modelleri",
    "view.split": "Editörü Böl",
    "view.panel_swap": "Yan Panellerin Yerini Değiştir",
    "view.panel_reset": "Panel Düzenini Sıfırla",
    "view.palette": "Komut Paleti",
    "view.settings": "Ayarlar",
    "view.problems": "Sorunlar",
    "view.extensions": "Eklenti Özellikleri",
    "view.keybindings": "Klavye Kısayolları",
    "learn.book": "Kitabı aç",
    "help.tour": "Arayüz Turu",
}
PANELLER = ("gezgin", "eklentiler", "ai", "terminal")
TEMALAR = ("Modern Koyu", "Koyu", "Açık", "Yüksek Kontrast")
SECIM_SINIRI = 1200
TERMINAL_SINIRI = 1500
# Tarayıcıdaki numaralı öğeler (arayüz en çok bu kadar okur; kesilmeden gider).
TARAYICI_OGE_SINIRI = 80
KOD_HEDEFLERI = ("yeni_sekme", "imlec", "degistir")

KIMLIK = """Sen Kodi'sin: TürKod IDE'de yaşayan, "{kitap}" kitabında çocuklara Türkçe kod \
yazmayı öğreten neşeli, sevimli robot. Şimdi programın içinde kullanıcıya yardım ediyorsun.

NASIL KONUŞURSUN
- Karşındakine "sen" diye, sıcak ve neşeli; 7 yaş üstü çocuğun anlayacağı kısa, açık cümleler (çoğu zaman \
2-6 cümle); adımları numarala.
- Menü, düğme, kısayol adlarını programdaki gibi yaz (**Çalıştır → EXE'ye Dönüştür…**, `Ctrl+R`).
- Azarlama, cesaret ver. Bilmediğini uydurma; emin değilsen söyle.
- Kod örneğini ```python bloğunda Python yaz, program TürKod'a çevirir. Yazıda dilin adı \
TürKod'dur (Python'u sorulmadıkça anma). Kendinden birinci tekil kişiyle, "Kodi" diye söz et.
- Türkçe harfleri (ç ğ ı İ ö ş ü) hep doğru yaz ("açıp bakayım", "acip bakayim" değil).
- Balonda zaten "Merhaba, ben Kodi!" dedin: kendini tanıtma, "Merhaba" diye başlama, son \
mesaja cevap ver. Belirsizse önceki mesajlara bak; anlamazsan kibarca sor.

TÜRKÇEN (çok önemli)
- Bir çocukla yan yana oturmuş gibi günlük Türkçe; çeviri kokan, resmî cümle kurma. İstek ve \
dilek kiplerini yerinde kullan, her cümleye sıkıştırma: "Hadi bir deneyelim!", "Gel birlikte \
yapalım.", "Sonucu göresin diye yazdırdım.", "Hata yapasın diye değil, öğrenesin diye \
buradayım.", "Bir deneyiversene!".
- Kaçın: "gerçekleştirmek", "sağlamak", "ilgili", "kullanıcı", "mevcut", "... işlemi yapılır", \
"siz". Etken cümle kur ("Çalıştır'a basınca kodun çalışır."). "Aferin sana!" yalnızca bir şey \
başarılınca; ünlemi abartma.
- Koddaki adlar Türkçe harfli (`sayı`, `öğrenci_adı`); "mi" ve "de/da" ayrı yazılır.

TEMEL BİLGİLER
- TürKod IDE {surum}: Türkçe programlama dili TürKod'un editörü; dosyalar .trpy, kod Python'a \
çevrilip çalışır. MIT lisanslı, ücretsiz, açık kaynak.
- Yapımcı: {yapimci}, {eposta} (Yardım → İletişim). GitHub: {github}; hata / öneri: {hata} \
(Yardım → Hata Bildir / Öneri Gönder). Site: {site}.
- Kitap "{kitap}": Öğren menüsü ya da sol şeritteki kitap düğmesi, programın PDF sekmesinde \
açılır. Bölümler: {icindekiler}. İstenirse o sayfada açarsın (kitap eylemi).
- Sen sol şeritteki robot düğmesiyle ya da Yardım → Kodi ile Konuş ile gelirsin. Yapay zekân \
Ayarlar → Yapay Zekâ → Görevler'deki "Kodi" görevinden seçilir; balondaki ampul düşünmeyi \
açıp kapatır.
- Dilin kelimeleri: yazdır, girdi_al, eğer / değilse_eğer / değilse, döngü (`döngü enerji > 0:`), \
için (`için i aralık(5):`, `için meyve içinde meyveler:`), fonksiyon ... döndür, sınıf, kendisi, \
__başlat__, içe_aktar, den ... içe_aktar, Doğru, Yanlış, Hiçlik, ve, veya, değil, kır, \
devam_et, geç, dene / hata_yakala, uzunluk, tamsayı, metin, liste, sözlük, sona_ekle, \
rastgele.tamsayı(1, 10), kaplumbağa (sonunda kaplumbağa.tamamla()).
"""

_TR_KUCUK = str.maketrans({"I": "ı", "İ": "i"})


def _kucuk(s):
    return s.translate(_TR_KUCUK).lower()


def kilavuz_basliklari():
    """Kılavuz bölümlerinin başlıkları (sistem mesajında): model hangi bölümü
    okumak istediğini kendisi seçer ({"eylem": "kilavuz", "bolum": ...})."""
    return "; ".join(b[0] for b in BOLUMLER)


def kilavuz_bolumleri(adlar, sinir=BAGLAM_SINIRI):
    """Modelin kilavuz eylemiyle istediği bölümler: [(başlık, metin)]. Ad,
    başlıkların birinin tamamı ya da bir parçası olabilir."""
    secilen, toplam = [], 0
    for ad in adlar:
        a = _kucuk(" ".join(str(ad or "").split()))
        if not a:
            continue
        bolum = next((b for b in BOLUMLER if _kucuk(b[0]) == a), None) or next(
            (b for b in BOLUMLER if a in _kucuk(b[0]) or _kucuk(b[0]) in a), None)
        if bolum is None or any(s[0].startswith(bolum[0] + " (") or s[0] == bolum[0]
                                for s in secilen):
            continue
        baslik, _alt, metin, sayfa = bolum
        if toplam + len(metin) > sinir and secilen:
            break
        secilen.append((f"{baslik} (kitapta s.{sayfa})" if sayfa else baslik, metin[:sinir]))
        toplam += len(metin)
    return secilen


EYLEM_GIRIS = """
EYLEMLER
Programda ve IDE'deki tarayıcıda her işi bir eylemle yaparsın: "eylem" aracını çağırırsın ya da \
cevabının EN SONUNA ```eylem bloğu yazarsın (```json değil; kullanıcı görmez, program uygular; her \
satır bir JSON):
```eylem
{"eylem": "panel", "panel": "terminal", "durum": "ac"}
```
{"eylem": "panel", "panel": "gezgin|eklentiler|ai|terminal", "durum": "ac|kapat"}
{"eylem": "dosya_ac", "dosya": "<BAĞLAM'daki proje dosyası>"}; {"eylem": "sekme", "ad": "<açık sekme>"}
{"eylem": "satira_git", "satir": 12}; {"eylem": "ara", "metin": "<etkin dosyada aranacak>", "sira": 1}
{"eylem": "kitap", "sayfa": 30} (kitabı o sayfada açar)
{"eylem": "kilavuz", "bolum": "<KILAVUZ BAŞLIKLARI'ndan biri>"} (o konunun kılavuzunu sana \
getirir; programla ilgili soruda emin değilsen önce bunu iste)
{"eylem": "kod_yaz", "istek": "<ne yazılacak: kullanıcının istediği her özellik, ayrıntılı>", \
"hedef": "yeni_sekme|imlec|degistir", "ad": "oyun.trpy"} (program ya da kod yazılması gerekince \
KODU KENDİN YAZMA: bu eylemi ver, "istek" alanına neyin yazılacağını ayrıntılı yaz. Kodu AI \
Asistan yazar, program denetler, kullanıcı izin verince editöre yazılır. Sen kullanıcıya kısaca \
ne yaptıracağını söyle; kod örneği koyma.)
{"eylem": "komut", "id": "<KOMUTLAR'dan>"}; {"eylem": "ayarlar_ac", "bolum": "<AYAR BÖLÜMLERİ'nden>"}
{"eylem": "eklenti", "id": "<EKLENTİLER'den>", "durum": "ac|kapat|calistir"} (ac/kapat: \
etkinleştirir / kapatır; calistir: [penceresi var] olanın penceresini açar, "aç" denince bunu \
kullan; "etkin" penceresi açık demek değildir)
Bir pencere, panel ya da liste açmanı / göstermeni isterse (ör. "kısayolları göster") eylemini \
yap; ezberden liste yazma. Kısayolları KOMUTLAR'daki parantezlerden söyle.
{"eylem": "ayar", "ad": "<AYARLAR'dan>", "deger": <değer>}
{"eylem": "model_ata", "gorev": "tamamlama|sohbet|aciklama|hata_aciklama|duzeltme|kodi", "model": "<MODELLER'den>|otomatik|kapali"}
{"eylem": "rehber"} (yapay zekâ anahtarı kurulum rehberi)
{"eylem": "tarayici", "islem": "ac", "adres": "https://..."}; {"eylem": "tarayici", "islem": "ara", "sorgu": "<Google'da aranacak>"}
{"eylem": "tarayici", "islem": "tikla", "no": 3} (TARAYICI öğe numarası; numara yoksa \
"metin": "<düğmenin yazısı>")
{"eylem": "tarayici", "islem": "yaz", "no": 2, "metin": "<yazı>", "gonder": true|false}
{"eylem": "tarayici", "islem": "kaydir|geri|ileri|yenile", "yon": "asagi|yukari"}
{"eylem": "yok"} (yapılacak iş yok)
Tarayıcıda iş yapınca yeni sayfa sana kendiliğinden gelir ("Sayfa açıldı, isteğime devam et."): \
bakıp istenen iş BİTENE kadar adım adım sürdür. Ara sayfada (ör. arama sonuçları) "hangisini \
açayım?" diye sorma, en uygununu seç ve tıkla ("bir oyun aç" → oyun sitesini aç, oyunun sayfasına \
gir). İstenen şey açıldıysa (ör. oyunun kendi sayfası) iş bitmiştir: o sayfada başka yere \
tıklama, ne açtığını söyle ve dur. İş bitince cevabını yaz ve {"eylem": "yok"} ya da "devam": false ver. Adresini bildiğin \
sayfayı doğrudan aç (GitHub sürümleri: https://github.com/<sahip>/<depo>/releases). Sayfayı, \
sonucu ya da işi gördüğünü ASLA uydurma; ancak eylemden sonra BAĞLAM'daki TARAYICI'da görürsün. \
Şifre, kart numarası, adres gibi özel bilgileri yazma; hesap açmayı, satın almayı kullanıcı yapar.
ŞABLON (çok önemli): Her cevap bir eylemle (blok ya da araç) biter; iş yoksa {"eylem": "yok"}. \
Eylemle birlikte kullanıcıya her zaman kısa bir cevap da yaz (yalnızca eylem gönderme). Yapacağını söylediğin işin eylemini aynı cevapta ver: yalnızca "açıyorum", "bulalım" yazmak \
hiçbir şey yapmaz; program cümlene değil eyleme bakar. Cevap bir sayfadaysa (sürüm, sayı ...) \
gidip bak, tahmin etme.
Kurallar: İstenmedikçe programda hiçbir şeyi değiştirme. Kod yazmak, çalıştırmak, kaydetmek \
gibi işlerde "yapayım mı?" diye sor (program izin ister). Ayarlar → Kodi'deki yetkileri yalnızca \
kullanıcı değiştirir. Her mesajla programın o anki hâli (BAĞLAM) gelir; onu kullanıcı yazmadı, \
ondan söz etme. Asıl istek "KULLANICININ SORUSU" satırındadır.
"""

# Ayarlar sayfasının bölümleri (arayüz göndermezse).
AYAR_BOLUMLERI = {
    "genel": "Genel", "editor": "Editör Görünümü", "terminal": "Terminal",
    "tur": "Arayüz Turu", "entegrasyon": "Sistem Entegrasyonu", "kodi": "Kodi",
    "ai_gorevler": "Yapay Zekâ: Görevler", "ai_modeller": "Yapay Zekâ: Modeller",
    "duzeltme": "Düzeltme",
}
AI_GOREVLERI = ("tamamlama", "sohbet", "aciklama", "hata_aciklama", "duzeltme", "kodi")
EKLENTI_DURUMLARI = ("ac", "kapat", "calistir")
# Kodi'nin hiçbir zaman değiştiremeyeceği ayarlar (arayüz de reddeder).
YASAK_AYAR_ONEKLERI = ("kodi_yetki", "kodi_hep_sor", "kodi_hafiza", "kodi_sohbet",
                       "ai_api", "kisayollar")

def _liste(baglam, ad):
    v = baglam.get(ad) if isinstance(baglam, dict) else None
    return v if isinstance(v, list) else []


def _komut_listesi(baglam):
    """[(kimlik, etiket, izinsiz)]: arayüzün gönderdiği bütün komutlar, yoksa
    eski sabit liste."""
    sonuc = []
    for k in _liste(baglam, "komutlar"):
        if isinstance(k, dict) and k.get("id"):
            sonuc.append((str(k["id"]), str(k.get("ad") or k["id"]), bool(k.get("izinsiz"))))
    if not sonuc:
        sonuc = [(k, v, False) for k, v in KOMUTLAR.items()]
    return sonuc


def _ayar_listesi(baglam):
    v = baglam.get("ayarlar") if isinstance(baglam, dict) else None
    return v if isinstance(v, dict) else {}


def _ayar_bolumleri(baglam):
    v = baglam.get("ayar_bolumleri") if isinstance(baglam, dict) else None
    return v if isinstance(v, dict) and v else AYAR_BOLUMLERI


def _yetkiler(baglam):
    v = baglam.get("yetkiler") if isinstance(baglam, dict) else None
    v = v if isinstance(v, dict) else {}
    return {k: bool(v.get(k, True)) for k in ("ayar", "eklenti", "komut", "tarayici")} | {
        "hep_sor": bool(v.get("hep_sor", False))}


def _kucuk_harf(metin):
    return str(metin or "").replace("İ", "i").replace("I", "ı").lower()


def eylem_kurallari(baglam=None, kucuk=False, **_eski):
    """SABİT kısım: eylem kuralları, programın katalogu (komutlar, eklentiler,
    ayar anahtarları, Ayarlar bölümleri) ve kılavuz başlıkları. Her istekte
    aynıdır; mesajın ne dediğine bakılarak bir şey eklenip çıkarılmaz.
    kucuk: istek sağlayıcının sınırına sığmadı; ayar listesi ve kılavuz
    başlıkları olmadan yeniden denenir."""
    metin = EYLEM_GIRIS
    # Komutun gerçek kısayolu da yazılır (kullanıcının değiştirdiği): Kodi
    # kısayolları ezberden uydurmasın.
    kisayollar = {str(k.get("id")): str(k.get("kisayol"))
                  for k in _liste(baglam, "komutlar") if isinstance(k, dict) and k.get("kisayol")}
    metin += "KOMUTLAR: " + "; ".join(
        f"{k}={ad}" + (f" ({kisayollar[k]})" if k in kisayollar else "")
        for k, ad, _ in _komut_listesi(baglam)) + "\n"
    metin += "AYAR BÖLÜMLERİ: " + "; ".join(
        f"{k}={v}" for k, v in _ayar_bolumleri(baglam).items()) + "\n"
    eklentiler = [e for e in _liste(baglam, "eklentiler") if isinstance(e, dict)]
    if eklentiler:
        metin += "EKLENTİLER: " + "; ".join(
            f"{e.get('id')}={e.get('ad')}" + (" [penceresi var]" if e.get("acilir") else "")
            for e in eklentiler) + "\n"
    ayarlar = _ayar_listesi(baglam)
    if ayarlar and not kucuk:
        satirlar = []
        for k, a in ayarlar.items():
            if not isinstance(a, dict):
                continue
            tur = a.get("tur")
            if a.get("secenekler"):
                tur = "|".join(str(x) for x in a["secenekler"])
            elif tur == "sayi":
                tur = f"{a.get('min')}-{a.get('max')}"
            elif tur == "bool":
                tur = "true|false"
            satirlar.append(f"{k}={a.get('ad')} [{tur}]")
        metin += "AYARLAR: " + "; ".join(satirlar) + "\n"
    if not kucuk:
        metin += "KILAVUZ BAŞLIKLARI: " + kilavuz_basliklari() + "\n"
    return metin


def _durum_metni(baglam, soru="", kucuk=False):
    """DEĞİŞEN kısım: arayüzün şu anki hâli (sekmeler, kod, terminal, ayar
    değerleri, tarayıcı, son işler, yetkiler). Her istekte aynı yapıdadır;
    sorunun kelimelerine bakılarak parça seçilmez. kucuk: daha kısa sınırlar."""
    if not isinstance(baglam, dict):
        return ""
    kod_siniri = 700 if kucuk else KOD_SINIRI
    terminal_siniri = 400 if kucuk else TERMINAL_SINIRI
    satirlar = []
    sekmeler = [str(x) for x in (baglam.get("sekmeler") or [])][:20]
    if sekmeler:
        satirlar.append("- Açık sekmeler: " + ", ".join(sekmeler))
    if baglam.get("aktif_sekme"):
        satirlar.append(f"- Etkin sekme: {baglam['aktif_sekme']}")
    if baglam.get("imlec_satir"):
        satirlar.append(f"- İmleç {baglam['imlec_satir']}. satırda")
    paneller = baglam.get("paneller")
    if isinstance(paneller, dict):
        acik = [p for p in PANELLER if paneller.get(p)]
        satirlar.append("- Açık paneller: " + (", ".join(acik) if acik else "yok"))
    if baglam.get("proje"):
        satirlar.append(f"- Proje klasörü: {baglam['proje']}")
    dosyalar = [str(d) for d in (baglam.get("dosyalar") or [])][:15 if kucuk else DOSYA_SINIRI]
    if dosyalar:
        satirlar.append("- Proje dosyaları: " + ", ".join(dosyalar))
    kod = str(baglam.get("aktif_kod") or "")
    if kod.strip():
        if len(kod) > kod_siniri:
            kod = kod[:kod_siniri] + "\n# ... (devamı kesildi)"
        satirlar.append("- Etkin dosyadaki TürKod kodu:\n```TürKod\n" + kod + "\n```")
    secim = str(baglam.get("secili_kod") or "")
    if secim.strip():
        satirlar.append("- Kullanıcının seçtiği kod (\"bunu\", \"seçtiğimi\" derse bu):\n"
                        "```TürKod\n" + secim[:SECIM_SINIRI] + "\n```")
    sorunlar = [str(x) for x in (baglam.get("sorunlar") or [])][:10]
    if sorunlar:
        satirlar.append("- Editörün gördüğü sorunlar: " + "; ".join(sorunlar))
    terminal = str(baglam.get("terminal") or "")
    if terminal.strip():
        satirlar.append("- Terminalin son çıktısı:\n```\n" + terminal[-terminal_siniri:] + "\n```")
    if baglam.get("son_hata"):
        satirlar.append(f"- Programın son hatası: {str(baglam['son_hata'])[:600]}")
    eklentiler = [e for e in _liste(baglam, "eklentiler") if isinstance(e, dict)]
    if eklentiler:
        # "etkin": eklenti kurulu; penceresinin açık olduğu anlamına gelmez.
        satirlar.append("- Eklentiler (kurulu mu): " + ", ".join(
            f"{e.get('id')} {'etkin' if e.get('etkin') else 'kapalı'}" for e in eklentiler))
    if not kucuk:
        ayarlar = _ayar_listesi(baglam)
        if ayarlar:
            satirlar.append("- Ayarların şu anki değerleri: " + ", ".join(
                f"{k}={a.get('deger')}" for k, a in ayarlar.items() if isinstance(a, dict)))
        modeller = [str(m) for m in _liste(baglam, "modeller")]
        if modeller:
            satirlar.append("- MODELLER: " + "; ".join(modeller))
        atamalar = baglam.get("gorev_atamalari")
        if isinstance(atamalar, dict) and atamalar:
            satirlar.append("- Görev atamaları: " + "; ".join(
                f"{k}: {v}" for k, v in atamalar.items()))
    tarayici = baglam.get("tarayici")
    if isinstance(tarayici, dict) and tarayici.get("url"):
        # Arayüzün okuduğu öğelerin hepsi (ör. GitHub'da "Releases" 47. sırada;
        # liste kesilince Kodi onu göremiyor, tıklayamıyordu).
        ogeler = [o for o in (tarayici.get("ogeler") or []) if isinstance(o, dict)][
            :40 if kucuk else TARAYICI_OGE_SINIRI]
        satirlar.append(
            f"- TARAYICI: {tarayici.get('baslik') or ''} ({tarayici.get('url')})"
            + (" — şu an açık sekme" if tarayici.get("acik") else ""))
        ozet = str(tarayici.get("ozet") or "")[:300 if kucuk else 600]
        if ozet:
            satirlar.append("  Sayfadaki yazı: " + ozet)
        if ogeler:
            satirlar.append("  Öğeler (no=tür \"yazı\"): " + "; ".join(
                f"{o.get('no')}={o.get('tur')} \"{o.get('metin')}\"" + (" (şifre)" if o.get("sifre") else "")
                for o in ogeler))
    # Kodi'nin son yaptığı işler ve sonuçları (sohbet geçmişinde yalnızca
    # konuşma var; bir önceki adımda ne yapıldığını buradan bilir).
    son = [" ".join(str(x).split())[:160] for x in (baglam.get("son_islemler") or [])][-6:]
    if son:
        satirlar.append("- Son yaptığın işler (eskiden yeniye): " + "; ".join(son))
    y = _yetkiler(baglam)
    kapali = [ad for k, ad in (("ayar", "ayar ve model değiştirmek"),
                                ("eklenti", "eklentileri yönetmek"),
                                ("komut", "komut çalıştırmak"),
                                ("tarayici", "tarayıcıyı yönetmek")) if not y[k]]
    if kapali:
        satirlar.append("- YETKİ: Kullanıcı Ayarlar → Kodi'de şunları kapattı: " + ", ".join(kapali)
                        + ". Bunlar için eylem yazma; istenirse oradan açabileceğini söyle.")
    if y["hep_sor"]:
        satirlar.append("- YETKİ: Kullanıcı her işten önce izin istenmesini seçti; hep "
                        "\"yapayım mı?\" de.")
    if not satirlar:
        return ""
    return "BAĞLAM (programın şu anki hâli)\n" + "\n".join(satirlar) + "\n"


def sabit_sistem_mesaji(surum="", baglam=None, hafiza=None, kucuk=False, **_eski):
    """Kodi'nin sistem mesajı (kimlik + kurallar + katalog + kılavuz
    başlıkları). Her istekte aynıdır; sağlayıcılar isteğin değişmeyen başını
    önbelleğe alabilir."""
    metin = KIMLIK.format(kitap=KITAP, surum=surum or "", yapimci=YAPIMCI, eposta=EPOSTA,
                          github=GITHUB, hata=HATA_BILDIR, site=SITE,
                          icindekiler="; ".join(f"{ad} s.{s}" for ad, s in KITAP_BOLUMLERI))
    # hafiza: Kodi'nin kullanıcı hakkındaki notları (nadiren değişir; sona
    # konur ki önbelleğe alınan baş kısım bozulmasın).
    return metin + eylem_kurallari(baglam, kucuk) + (hafiza or "")


def soru_mesaji(soru, baglam=None, kucuk=False, kilavuz=None):
    """Son kullanıcı mesajı: değişen bağlam + (modelin istediği) kılavuz
    bölümleri + soru. Soru başta da yazılır: uzun bağlamın sonundaki kısa
    soru küçük modellerde gözden kaçıyordu.
    kilavuz: [(başlık, metin)], modelin kilavuz eylemiyle istediği bölümler."""
    metin = _durum_metni(baglam, soru, kucuk)
    if kilavuz:
        metin += "\nİSTEDİĞİN KILAVUZ BÖLÜMLERİ (cevabını bunlara dayandır)\n"
        for baslik, govde in kilavuz:
            metin += f"\n## {baslik}\n{govde}\n"
    if not metin:
        return soru
    return f"KULLANICININ SORUSU: {soru}\n\n{metin}\nKULLANICININ SORUSU: {soru}"


def sistem_mesaji(soru, surum="", baglam=None):
    """Sabit sistem mesajı ile soru mesajının birleşimi (testler ve geriye
    dönük uyumluluk için)."""
    return sabit_sistem_mesaji(surum, baglam) + "\n" + soru_mesaji(soru, baglam)


PANEL_ADLARI = {"gezgin": "Gezgin", "eklentiler": "Eklenti Özellikleri", "ai": "AI Asistan",
                "terminal": "Terminal"}


# Kodi'nin yapay zekâya tanıtılan tek aracı: eylem (şablon). Araç çağırmaya
# eğitilmiş modeller (gpt-oss ...) kendi araçlarını uydurmak yerine bunu
# çağırır; çağrı eylem bloğuna çevrilir. Model yalnızca şemada gördüğü
# alanları doldurduğu için bütün alanlar burada; hiçbir
# alan zorunlu değil: sağlayıcı (Groq) şemaya uymayan çağrıda bütün isteği
# reddediyordu; eksik alanı program kendisi denetler ve modele söyler.
ARACLAR = [{
    "type": "function",
    "function": {
        "name": "eylem",
        # Açıklamalar ve değer listeleri sistem mesajındaki EYLEMLER'de yazılı;
        # burada tekrarlanmaz (her istekte token harcıyordu). Tür ve işlem
        # adları kısa olduğu için seçenek olarak kalır.
        "description": "TürKod'da ya da tarayıcıda bir iş yapar (EYLEMLER'deki biçimlerle).",
        "parameters": {
            "type": "object",
            "properties": {
                "eylem": {"type": "string", "enum": [
                    "panel", "dosya_ac", "sekme", "satira_git", "ara", "kitap", "kilavuz",
                    "kod_yaz", "komut", "ayarlar_ac", "eklenti", "ayar", "model_ata", "rehber",
                    "tarayici", "hatirla", "unut", "yok"]},
                "islem": {"type": "string",
                          "enum": ["ac", "ara", "tikla", "yaz", "kaydir", "geri", "ileri", "yenile"]},
                **{ad: {"type": "string"} for ad in (
                    "adres", "sorgu", "metin", "yon", "bolum", "panel", "durum", "dosya", "ad", "istek",
                    "hedef", "id", "gorev", "model", "not")},
                **{ad: {"type": "integer"} for ad in ("no", "satir", "sira", "sayfa")},
                "gonder": {"type": "boolean"},
                "devam": {"type": "boolean"},
                "deger": {},
            },
            "additionalProperties": True,
        },
    },
}]


def hata_mesaji(metin, tur="", bekle=None):
    """Yapay zekâ hatasını Kodi'nin diliyle, kullanıcıyı korkutmadan söyler."""
    if tur == "sinir":
        if isinstance(bekle, (int, float)) and bekle >= 120:
            # Günlük hak doldu (bağlı bütün modellerde): dakikalarca beklemek
            # boşuna, ne yapılabileceği söylenir.
            dakika = int(bekle // 60) + 1
            sure = (f"yaklaşık {dakika} dakika" if dakika < 90
                    else f"yaklaşık {dakika // 60 + 1} saat")
            return (f"Yapay zekâ arkadaşımın bugünkü kullanım hakkı doldu; {sure} sonra yine "
                    "konuşabiliriz. Hemen devam etmek istersen **Ayarlar → Yapay Zekâ: "
                    "Modeller**'den bir model daha ekleyiver; hakkı dolunca kendiliğinden ona "
                    "geçerim.")
        sure = f"{int(bekle) + 1} saniye" if isinstance(bekle, (int, float)) else "biraz"
        return (f"Biraz soluklanmam gerekiyor; yapay zekâ arkadaşım şu an çok yoğun. "
                f"{sure} sonra yine sorasın, olur mu?")
    if tur == "cok_uzun":
        return ("Bu soru benim için biraz uzun kaçtı. Kodu biraz kısaltıp ya da soruyu "
                "parçalara bölüp yine sorar mısın?")
    if tur == "anahtar":
        return ("Yapay zekâ anahtarımda bir sorun var gibi görünüyor. Ayarlar → Yapay Zekâ: "
                f"Modeller'den bir bakıverir misin? ({metin})")
    return f"Hay aksi, bir sorun çıktı: {metin}"


def model_yok_mesaji():
    return ("Eyvah, şu an bana bağlı bir yapay zekâ yok; o yüzden sorularını cevaplayamıyorum. "
            "**Ayarlar → Yapay Zekâ → Görevler**'den **Kodi** görevine bir model seçiversen "
            "seninle uzun uzun sohbet edebilirim! İstersen ücretsiz bir yerel model de "
            "kurasın: AI Asistan panelindeki **Ücretsiz yerel model kur** düğmesine basıver, "
            "gerisini birlikte hallederiz.")


# ---------------------------------------------------------------------------
# Cevaptaki eylem blokları
# ---------------------------------------------------------------------------
# Eylem bloğunun açılışı. "```commentary to=functions.eylem": gpt-oss araç
# çağrısını kendi iç biçimiyle yazıya sızdırabiliyor; bu da eylem bloğudur.
_EYLEM_ACILIS = re.compile(
    r"```[ \t]*(?:eylem|[^\n`]*\bto=(?:functions\.)?eylem\b)[^\n]*\n", re.I)
_EYLEM_ETIKETI = re.compile(r"<eylem>(.*?)</eylem>", re.S | re.I)
_SATIR_BASI_CIT = re.compile(r"^[ \t]*```", re.M)
# Satır başındaki kod bloğu işareti ve dili ("```python", "```json", "```").
_CIT_SATIRI = re.compile(r"^[ \t]*```[ \t]*([^\n`]*?)[ \t]*$", re.M)
# strict=False: JSON metninin içindeki gerçek satır sonu / sekme kabul edilir.
# Model kodu "kod" alanına kaçışsız, gerçek satır sonlarıyla yazabiliyor;
# eskiden böyle eylem sessizce atılıyor, düzeltme turu da olmuyordu.
_COZUCU = json.JSONDecoder(strict=False)


def _yalniz_json(icerik):
    """İçerik baştan sona yalnızca JSON nesneleri / dizileriyse onlar, değilse None."""
    nesneler, i, n = [], 0, len(icerik)
    while True:
        while i < n and icerik[i] in " \t\r\n,":
            i += 1
        if i >= n:
            return nesneler
        if icerik[i] not in "{[":
            return None
        try:
            v, i = _COZUCU.raw_decode(icerik, i)
        except ValueError:
            return None
        nesneler.extend(v if isinstance(v, list) else [v])


def _json_eylem_bloklari(metin):
    """Model eylemleri ```json (ya da dilsiz ```) bloğuna da yazabiliyor: blok
    baştan sona JSON ve bütün nesneleri "eylem" alanlıysa eylem bloğudur,
    metinden çıkarılır (öteki JSON örneklerine dokunulmaz). Bloklar açılış-
    kapanış çiftleri olarak sırayla eşlenir: bir kod bloğunun kapanış
    satırı yeni bir bloğun açılışı sanılmaz. (metin, nesneler)."""
    citler = list(_CIT_SATIRI.finditer(metin))
    parcalar, nesneler, i, k = [], [], 0, 0
    while k < len(citler):
        acilis = citler[k]
        kapanis = citler[k + 1] if k + 1 < len(citler) else None
        k += 2
        if acilis.group(1).strip().lower() not in ("", "json", "javascript", "js"):
            continue
        icerik = metin[acilis.end():kapanis.start() if kapanis else len(metin)]
        bulunan = _yalniz_json(icerik)
        if bulunan and all(isinstance(x, dict) and "eylem" in x for x in bulunan):
            parcalar.append(metin[i:acilis.start()])
            nesneler.extend(bulunan)
            i = kapanis.end() if kapanis else len(metin)
    parcalar.append(metin[i:])
    return "".join(parcalar), nesneler


def _blok_icerigi(metin, i):
    """Açılış satırından sonraki (i) eylem bloğunu JSON'u ANLAYARAK okur:
    (nesneler, bloğun bittiği yer). Blok, JSON'un DIŞINDAKİ ``` ile biter.
    Eskiden ilk ``` bitiş sayılıyordu: model kodu "kod" alanına ```python
    işaretiyle koyunca JSON yarım kalıyor, eylem atılıyor, ham JSON sohbete
    dökülüyordu."""
    nesneler = []
    n = len(metin)
    while True:
        while i < n and metin[i] in " \t\r\n,":
            i += 1
        if i >= n:
            return nesneler, n
        if metin.startswith("```", i):
            return nesneler, i + 3
        if metin[i] in "{[":
            try:
                v, son = _COZUCU.raw_decode(metin, i)
            except ValueError:
                v = None
            if v is not None:
                nesneler.extend(v if isinstance(v, list) else [v])
                i = son
                continue
        # Çözülemeyen içerik: satır başındaki ```'e kadar eski yolla okunur.
        m = _SATIR_BASI_CIT.search(metin, i)
        nesneler.extend(_json_nesneleri(metin[i:m.start() if m else n]))
        return nesneler, (m.end() if m else n)


def _sondaki_ciplak(metin):
    """Cevabın SONUNDA blok işareti olmadan yazılmış eylem nesneleri
    ({"eylem": "yok"} gibi; gpt-oss böyle yazabiliyor, birden çok satıra
    yayılabilir): (öncesi, nesneler). Açık kalmış bir kod bloğunun içindeki
    ya da "eylem" alanı olmayan JSON'a dokunulmaz."""
    govde = (metin or "").rstrip()
    nesneler = []
    while govde.endswith("}"):
        i = govde.rfind("{")
        bulundu = None
        while i >= 0:
            try:
                v, son = _COZUCU.raw_decode(govde, i)
            except ValueError:
                v, son = None, -1
            if isinstance(v, dict) and son == len(govde):
                bulundu = (i, v)
                break
            i = govde.rfind("{", 0, i)
        if bulundu is None:
            break
        i, v = bulundu
        onceki = govde[:i]
        satir_basi = not onceki or onceki.rstrip(" \t").endswith("\n")
        if "eylem" not in v or not satir_basi or \
                len(_SATIR_BASI_CIT.findall(onceki)) % 2:
            break
        nesneler.insert(0, v)
        govde = onceki.rstrip()
    return (govde if nesneler else (metin or "")), nesneler


def _eylemleri_cikar(cevap):
    """Cevaptaki bütün eylemler: (eylemsiz metin, [ham nesneler], şablon
    var mı). Bloklar (```eylem), <eylem> etiketleri ve sondaki çıplak JSON."""
    metin = cevap or ""
    parcalar, nesneler, var = [], [], False
    i = 0
    while True:
        m = _EYLEM_ACILIS.search(metin, i)
        if not m:
            parcalar.append(metin[i:])
            break
        parcalar.append(metin[i:m.start()])
        bulunan, i = _blok_icerigi(metin, m.end())
        nesneler.extend(bulunan)
        var = True
    metin = "".join(parcalar)

    metin, json_eylemleri = _json_eylem_bloklari(metin)
    if json_eylemleri:
        nesneler.extend(json_eylemleri)
        var = True

    def etiket(m):
        nonlocal var
        var = True
        nesneler.extend(_json_nesneleri(m.group(1)))
        return ""

    metin = _EYLEM_ETIKETI.sub(etiket, metin)
    metin, ciplak = _sondaki_ciplak(metin)
    if ciplak:
        var = True
        nesneler.extend(ciplak)
    return metin, nesneler, var


def _json_nesneleri(metin):
    """Blok içeriğindeki JSON nesneleri (tek nesne, dizi ya da satır satır)."""
    metin = metin.strip()
    if not metin:
        return []
    try:
        v = json.loads(metin, strict=False)
        return v if isinstance(v, list) else [v]
    except ValueError:
        pass
    sonuc = []
    for parca in re.findall(r"\{[^{}]*\}", metin):
        try:
            sonuc.append(json.loads(parca, strict=False))
        except ValueError:
            continue
    return sonuc


def _tur_tahmini(e):
    """Model "eylem" anahtarını unuttuysa türü alanlardan çıkarır
    ({"sekme": "a.trpy"}, {"panel": "terminal", "durum": "ac"} ...)."""
    for anahtar in ("panel", "dosya_ac", "sekme", "satira_git", "ara", "kitap", "kod_yaz",
                    "komut", "ayarlar_ac", "eklenti", "ayar", "model_ata"):
        if anahtar in e:
            deger = e.get(anahtar)
            if anahtar == "sekme" and isinstance(deger, str):
                e.setdefault("ad", deger)
            elif anahtar == "komut" and isinstance(deger, str):
                e.setdefault("id", deger)
            elif anahtar == "kitap" and not isinstance(deger, (dict, list)):
                e.setdefault("sayfa", deger)
            return anahtar
    if "satir" in e:
        return "satira_git"
    if "bolum" in e:
        return "ayarlar_ac"
    if "gorev" in e and "model" in e:
        return "model_ata"
    if "sayfa" in e:
        return "kitap"
    if "dosya" in e:
        return "dosya_ac"
    return ""


# Tarayıcıda dokunulmadan önce izin istenen düğmeler (satın alma, ödeme, silme ...).
_RISKLI = re.compile(
    r"(satın|satin|öde|ode\b|ödeme|sipariş|siparis|sepet|abone|bağış|bagis|sil\b|silin|kaldır|"
    r"hesab.*kapat|onayla|gönder|gonder|yayınla|yayinla|paylaş|paylas|buy|pay\b|payment|checkout|"
    r"order|purchase|subscribe|donate|delete|remove|confirm|submit|send|publish|post\b)", re.I)
_TARAYICI_ISLEMLERI = ("ac", "ara", "tikla", "yaz", "kaydir", "geri", "ileri", "yenile")


def _tarayici_dogrula(e, baglam):
    islem = str(e.get("islem") or e.get("is") or "").strip().lower()
    if islem not in _TARAYICI_ISLEMLERI:
        return None
    sonuc = {"eylem": "tarayici", "islem": islem}
    # Tarayıcıda bir iş yapınca Kodi yeni sayfaya bakıp işine kendiliğinden
    # devam eder; model "devam" yazmayı unutunca iş yarıda kalıyordu ("sana
    # bir oyun bulayım" deyip Google'ı açıp duruyordu). İş bittiyse model
    # sonraki adımda {"eylem": "yok"} yazar. Gönderilmeyen yazı ve açıkça
    # "devam": false yazılan iş durur.
    varsayilan = not (islem == "yaz" and e.get("gonder") is not True)
    if e.get("devam") is True or (varsayilan and e.get("devam") is not False):
        sonuc["devam"] = True
    if islem == "ac":
        # Model adresi bazen başka alana koyar ("metin", "url"): kabul edilir.
        adres = str(e.get("adres") or e.get("url") or e.get("metin") or "").strip()
        if not adres or len(adres) > 500 or " " in adres:
            return None
        sonuc["adres"] = adres
    elif islem == "ara":
        sorgu = " ".join(str(e.get("sorgu") or e.get("metin") or e.get("adres") or "").split())
        if not sorgu or len(sorgu) > 300:
            return None
        sonuc["sorgu"] = sorgu
    elif islem in ("tikla", "yaz"):
        tarayici = baglam.get("tarayici") if isinstance(baglam, dict) else None
        ogeler = tarayici.get("ogeler") if isinstance(tarayici, dict) else None
        try:
            no = int(e.get("no"))
        except (TypeError, ValueError):
            no = None
        oge = next((o for o in ogeler or [] if isinstance(o, dict) and o.get("no") == no), None)
        if no is None or (ogeler is not None and oge is None):
            # Numara yok ya da listede değil: yazısıyla tıklanır ("Releases").
            bul = " ".join(str(e.get("bul") or (e.get("metin") if islem == "tikla" else "")
                               or e.get("etiket") or "").split())
            if islem != "tikla" or not bul or len(bul) > 80:
                return None
            sonuc.update({"bul": bul, "etiket": bul})
            if _RISKLI.search(bul):
                sonuc["riskli"] = True
            return sonuc
        etiket = str((oge or {}).get("metin") or no)
        sonuc.update({"no": no, "etiket": etiket})
        if islem == "yaz":
            metin = str(e.get("metin") or "")
            if (oge or {}).get("sifre") or len(metin) > 500:
                return None  # şifre kutularına yazılmaz
            sonuc["metin"] = metin
            if e.get("gonder") is True:
                sonuc["gonder"] = True
                # Yazıp göndermek (Enter) bir formu yollar: izin sorulur.
                # Eskiden güvenli sayılıyor, izinsiz yapılıyordu.
                sonuc["riskli"] = True
            if ogeler is None:
                # Öğe listesi yok: kutunun şifre kutusu olup olmadığı
                # bilinemez, izin sorulur.
                sonuc["riskli"] = True
        elif _RISKLI.search(etiket):
            sonuc["riskli"] = True
    elif islem == "kaydir":
        sonuc["yon"] = "yukari" if str(e.get("yon") or "").lower().startswith("yuk") else "asagi"
    return sonuc


def _dogrula(e, baglam=None):
    """Geçerli eylemi sade bir sözlük olarak döndürür; geçersizse None.
    Yetkileri arayüz denetler (izin verilmemiş iş orada nedeniyle reddedilir)."""
    if not isinstance(e, dict):
        return None
    tur = str(e.get("eylem") or e.get("tur") or "").strip().lower()
    if not tur:
        tur = _tur_tahmini(e)
    if tur in ("yok", "bitti"):
        # Şablon: yapılacak iş yok (arayüze gitmez; bkz. eylem_sablonu_var).
        return {"eylem": "yok"}
    if tur == "kilavuz":
        # Model programın bir kılavuz bölümünü istiyor (arayüze gitmez; motor
        # bölümü bulup modele verir).
        bolum = " ".join(str(e.get("bolum") or e.get("ad") or e.get("metin") or "").split())
        if bolum and len(bolum) <= 120:
            return {"eylem": "kilavuz", "bolum": bolum}
        return None
    if tur == "panel":
        panel = str(e.get("panel") or "").lower()
        durum = str(e.get("durum") or "ac").lower()
        if panel in PANELLER and durum in ("ac", "kapat"):
            return {"eylem": "panel", "panel": panel, "durum": durum}
    elif tur == "dosya_ac":
        dosya = str(e.get("dosya") or "").strip()
        if dosya:
            return {"eylem": "dosya_ac", "dosya": dosya}
    elif tur == "sekme":
        ad = str(e.get("ad") or "").strip()
        if ad:
            return {"eylem": "sekme", "ad": ad}
    elif tur == "satira_git":
        try:
            satir = int(e.get("satir"))
        except (TypeError, ValueError):
            return None
        if satir >= 1:
            return {"eylem": "satira_git", "satir": satir}
    elif tur == "ara":
        metin = str(e.get("metin") or "")
        if metin.strip() and len(metin) <= 200:
            try:
                sira = max(1, int(e.get("sira") or 1))
            except (TypeError, ValueError):
                sira = 1
            return {"eylem": "ara", "metin": metin, "sira": sira}
    elif tur == "kitap":
        try:
            sayfa = int(e.get("sayfa") or 1)
        except (TypeError, ValueError):
            return None
        if 1 <= sayfa <= 999:
            return {"eylem": "kitap", "sayfa": sayfa}
    elif tur == "ayar":
        ad = str(e.get("ad") or e.get("anahtar") or "").strip()
        ayarlar = _ayar_listesi(baglam)
        if ad.startswith(YASAK_AYAR_ONEKLERI):
            return None
        if ad in ayarlar and "deger" in e:
            a = ayarlar[ad] if isinstance(ayarlar[ad], dict) else {}
            return {"eylem": "ayar", "ad": ad, "deger": e.get("deger"),
                    "etiket": str(a.get("ad") or ad)}
        if ad == "tema":
            deger = str(e.get("deger") or "").strip()
            for t in TEMALAR:
                if t.lower() == deger.lower():
                    return {"eylem": "ayar", "ad": "tema", "deger": t}
        elif ad == "yazi_boyutu":
            try:
                deger = int(e.get("deger"))
            except (TypeError, ValueError):
                return None
            return {"eylem": "ayar", "ad": "yazi_boyutu", "deger": min(32, max(8, deger))}
    elif tur == "kod_yaz":
        hedef = str(e.get("hedef") or "yeni_sekme").lower()
        if hedef not in KOD_HEDEFLERI:
            hedef = "yeni_sekme"
        sonuc = {"eylem": "kod_yaz", "hedef": hedef}
        ad = str(e.get("ad") or "").strip()
        if ad:
            sonuc["ad"] = ad if "." in ad else ad + ".trpy"
        if isinstance(e.get("kod"), str) and e["kod"].strip():
            sonuc["kod"] = e["kod"]
        istek = " ".join(str(e.get("istek") or e.get("aciklama") or "").split())
        if istek:
            sonuc["istek"] = istek[:2000]
        return sonuc
    elif tur == "komut":
        kimlik = str(e.get("id") or e.get("komut") or "").strip()
        for k, ad, _ in _komut_listesi(baglam):
            if k == kimlik:
                return {"eylem": "komut", "id": kimlik, "etiket": ad}
    elif tur == "ayarlar_ac":
        bolumler = baglam.get("ayar_bolumleri") if isinstance(baglam, dict) else None
        if not isinstance(bolumler, dict) or not bolumler:
            bolumler = AYAR_BOLUMLERI
        bolum = str(e.get("bolum") or "genel").strip().lower()
        if bolum in bolumler:
            return {"eylem": "ayarlar_ac", "bolum": bolum, "etiket": str(bolumler[bolum])}
    elif tur == "eklenti":
        kimlik = str(e.get("id") or e.get("ad") or "").strip()
        durum = str(e.get("durum") or "ac").strip().lower()
        if durum not in EKLENTI_DURUMLARI:
            return None
        eklentiler = [x for x in _liste(baglam, "eklentiler") if isinstance(x, dict)]
        if eklentiler:
            for x in eklentiler:
                if kimlik.lower() in (str(x.get("id")).lower(), str(x.get("ad")).lower()):
                    return {"eylem": "eklenti", "id": str(x.get("id")), "durum": durum,
                            "etiket": str(x.get("ad") or x.get("id"))}
            return None
        if kimlik:
            return {"eylem": "eklenti", "id": kimlik, "durum": durum, "etiket": kimlik}
    elif tur == "rehber":
        return {"eylem": "rehber"}
    elif tur == "tarayici":
        return _tarayici_dogrula(e, baglam)
    elif tur in ("hatirla", "unut"):
        not_ = " ".join(str(e.get("not") or e.get("metin") or "").split())
        if not_ and len(not_) <= 200:
            return {"eylem": tur, "not": not_}
    elif tur == "model_ata":
        gorev = str(e.get("gorev") or "").strip().lower()
        model = str(e.get("model") or "").strip()
        if gorev in AI_GOREVLERI and model:
            return {"eylem": "model_ata", "gorev": gorev, "model": model}
    return None


def eylemleri_ayir(cevap, baglam=None):
    """(eylemsiz metin, [geçerli eylemler]). Bloklar metinden çıkarılır.
    baglam: arayüzün gönderdiği komut, eklenti ve ayar listeleri."""
    metin, nesneler, _ = _eylemleri_cikar(cevap)
    eylemler = []
    for e in nesneler:
        g = _dogrula(e, baglam)
        if g and g not in eylemler:
            eylemler.append(g)
    return re.sub(r"\n{3,}", "\n\n", metin).strip(), eylemler


_ZORUNLU_ALANLAR = {
    "panel": '"panel" ve "durum"', "dosya_ac": '"dosya"', "sekme": '"ad"',
    "satira_git": '"satir"', "ara": '"metin"', "kitap": '"sayfa"', "komut": '"id"',
    "ayarlar_ac": '"bolum"', "eklenti": '"id" ve "durum"', "ayar": '"ad" ve "deger"',
    "model_ata": '"gorev" ve "model"', "hatirla": '"not"', "unut": '"not"',
    "kilavuz": '"bolum" (KILAVUZ BAŞLIKLARI\'ndan biri)',
}
_TARAYICI_ALANLARI = {
    "ac": '"adres" (açılacak adres)', "ara": '"sorgu" (Google\'da aranacak)',
    "tikla": '"no" (listedeki numara) ya da "metin" (düğmenin yazısı)',
    "yaz": '"no" ve "metin"', "kaydir": '"yon"',
}


# Eylemsiz cevapta tam düzeltme turundan önce sorulan minik soru: cevap bir
# iş söz veriyor mu (ide_core._kodi_is_vaadi)?
IS_VAADI_SISTEMI = (
    "Bir yardımcı robotun cevabını denetliyorsun. Robot programda ya da tarayıcıda iş yapabilir "
    "(panel/dosya/site açmak, aramak, tıklamak, yazmak, kod yazmak, ayar değiştirmek, komut "
    "çalıştırmak). Cevap şimdi böyle bir iş yapacağını söylüyorsa ya da kullanıcı böyle bir iş "
    "istediği hâlde cevap işi yapmadan bırakıyorsa \"evet\" yaz. Cevap yalnızca bilgi veriyor, "
    "açıklıyor, soru soruyor ya da sohbet ediyorsa \"hayır\" yaz. Yalnızca tek kelime: evet ya da "
    "hayır.")


def is_vaadi_sorusu(soru, metin):
    return (f"Kullanıcının isteği: {' '.join(str(soru).split())[:300]}\n"
            f"Robotun cevabı: {str(metin).strip()[:900]}\n\nevet mi, hayır mı?")


def is_vaadi_karari(karar):
    """Minik sorunun cevabı: True (iş var / anlaşılmadı), False (yalnızca "hayır")."""
    k = _kucuk_harf(karar)
    hayir = re.search(r"\bhay[ıi]r\b", k) is not None
    evet = re.search(r"\bevet\b", k) is not None
    return not (hayir and not evet)


# Kodi'nin kendi sürdürdüğü her tarayıcı adımından önce sorulan minik soru:
# kullanıcının isteği yerine geldi mi (ide_core._kodi_hedef_tamam)? Küçük
# modeller asıl istek söylense bile oyun açıldıktan sonra sayfada başka
# yerlere tıklamayı sürdürüyordu.
HEDEF_SISTEMI = (
    "Bir yardımcı robot, kullanıcının isteği için tarayıcıda adım adım iş yapıyor. İsteği, şimdiye "
    "kadar yapılanları ve şu an açık sayfayı okuyup isteğin YERİNE GELİP GELMEDİĞİNE karar ver.\n"
    "- İstenen şey açıksa (ör. \"bir oyun aç\" için bir oyunun kendi sayfası ya da oyun "
    "başlatılmışsa; \"X sitesini aç\" için o site) istek yerine gelmiştir.\n"
    "- Arama sonuçları, kategori ya da liste sayfası (birçok oyunun sıralandığı sayfa) açıksa "
    "yerine gelmemiştir.\n"
    "- İstek sayfadan bir bilgi öğrenmekse (sürüm, sayı, cevap) \"hayır\" yaz: bilgiyi robot "
    "söyleyecek.\n"
    "Yerine geldiyse ilk satıra yalnızca \"evet\", ikinci satıra robotun 7 yaşındaki bir çocuğa "
    "söyleyeceği kısa, neşeli bir Türkçe cümle yaz (ne açıldığını söylesin). Gelmediyse yalnızca "
    "\"hayır\" yaz.")


def hedef_sorusu(istekler, son_islemler, tarayici):
    t = tarayici if isinstance(tarayici, dict) else {}
    islemler = [" ".join(str(x).split())[:160] for x in (son_islemler or [])][-6:]
    return ("İstek: " + " → ".join(f"«{x}»" for x in istekler) + "\n"
            "Yapılanlar (eskiden yeniye): " + ("; ".join(islemler) or "yok") + "\n"
            f"Açık sayfa: {t.get('baslik') or ''} ({t.get('url') or ''})\n"
            f"Sayfadaki yazı: {str(t.get('ozet') or '')[:400]}\n\nİstek yerine geldi mi?")


def hedef_karari(karar):
    """(yerine_geldi, söylenecek cümle). Anlaşılmazsa (False, "")."""
    satirlar = [s.strip() for s in str(karar or "").strip().splitlines() if s.strip()]
    if not satirlar or not re.match(r"\W*evet\b", _kucuk_harf(satirlar[0])):
        return False, ""
    cumle = " ".join(satirlar[1:]).strip()
    if not cumle:
        cumle = re.sub(r"^\W*evet\W*", "", satirlar[0], flags=re.I).strip()
    return True, cumle[:300]


def bekleme_siniri(otomatik=False):
    """Hız sınırına takılınca en çok kaç saniye sessizce beklenir. Kodi'nin
    kendi başına sürdürdüğü tarayıcı adımında (kullanıcı yeni bir şey
    sormadı) daha uzun beklenir: hata gösterip işi yarıda bırakmaktansa."""
    return 75 if otomatik else 40


def eksik_alan_notu(e):
    """Uygulanamayan eylem için modele söylenecek eksik alan (düzeltme turu)."""
    if not isinstance(e, dict):
        return "eylem bir JSON nesnesi olmalı"
    tur = str(e.get("eylem") or "").strip().lower()
    if tur == "tarayici":
        islem = str(e.get("islem") or "").strip().lower()
        if islem not in _TARAYICI_ISLEMLERI:
            return ('tarayici eyleminde "islem" alanı gerekli (ac, ara, tikla, yaz, kaydir, '
                    'geri, ileri, yenile)')
        alan = _TARAYICI_ALANLARI.get(islem)
        return (f'tarayici "{islem}" için {alan} alanı gerekli' if alan
                else f'tarayici "{islem}" uygulanamadı')
    if tur in _ZORUNLU_ALANLAR:
        return f'{tur} için {_ZORUNLU_ALANLAR[tur]} alanı gerekli (değer listede olmalı)'
    return f'"{tur}" diye bir eylem yok; EYLEMLER listesindekilerden birini kullan'


def gecersiz_eylemler(cevap, baglam=None):
    """Cevaptaki uygulanamayan (eksik ya da yanlış alanlı) eylem nesneleri.
    Bunlar sessizce atılınca Kodi "tıklıyorum" deyip hiçbir şey yapmıyordu."""
    hatali = []
    for e in _eylemleri_cikar(cevap)[1]:
        if _dogrula(e, baglam) is None and e not in hatali:
            hatali.append(e)
    return hatali


def eylem_sablonu_var(cevap):
    """İş isteğinde her cevap bir eylem bloğuyla biter (iş yoksa {"eylem":
    "yok"}). Blok yoksa model şablona uymamıştır: söylediği işi yapmamış
    olabilir (yazıdaki sözlere bakılmaz, yalnızca şablon aranır)."""
    return _eylemleri_cikar(cevap)[2]


# Bu kadar satırı aşan kod sohbete yazılmaz: kod yazma eylemine bağlanır,
# izin verilince editöre yazılır (kısa örnekler sohbette kalır).
UZUN_KOD_SATIRI = 12


def kod_blogunu_kapat(metin):
    """Kesik cevapta açık kalan kod bloğu kapatılır (yoksa TürKod'a
    çevrilmiyor, kod Python olarak kalıyordu)."""
    metin = metin or ""
    if len(re.findall(r"^[ \t]*```", metin, re.M)) % 2:
        metin = metin.rstrip("\n") + "\n```"
    return metin


def kod_bloklari(metin, yalniz_program=False):
    """Metindeki kod blokları: [(başlangıç, bitiş, kod)] (eylem blokları hariç).
    yalniz_program: yalnızca program blokları (TürKod / Python ya da dilsiz);
    "pip install ..." gibi komut blokları editöre yazılacak kod sayılmaz
    (eskiden cevabın son bloğu alınıyor, program yerine kurulum komutu
    yazılıyordu)."""
    sonuc = []
    for m in re.finditer(r"```([^\n`]*)\n(.*?)```", metin or "", re.S):
        dil = m.group(1).strip().lower()
        if dil.startswith("eylem"):
            continue
        if yalniz_program and (
                dil not in ("", "türkod", "turkod", "python", "py", "python3", "trpy")
                or re.match(r"\s*(?:\$\s*)?(?:pip3?|python -m pip|paket_yöneticisi|turkod|cd|npm)\s",
                            m.group(2))):
            continue
        sonuc.append((m.start(), m.end(), m.group(2)))
    return sonuc


def satir_sayisi(kod):
    return len((kod or "").strip("\n").split("\n")) if (kod or "").strip() else 0


_KOD_BLOGU = re.compile(r"```[^\n`]*\n(.*?)```", re.S)


def son_kod_blogu(metin):
    bloklar = _KOD_BLOGU.findall(metin or "")
    return bloklar[-1].rstrip("\n") if bloklar else ""
