"""TurKod sozluk ve kelime altyapisi."""
import ast
import json
import os
import re
import sys
import keyword as _keyword

# 1. Yolları .paths modülünden al (FONKSİYON OLDUKLARI İÇİN PARANTEZ İLE ÇAĞIR)
try:
    from .paths import calisma_yolu, kaynak_yolu
    # Fonksiyonları çağırıp sonuçlarını değişkenlere ata
    _CALISMA_YOLU = calisma_yolu()
    _KAYNAK_YOLU = kaynak_yolu()
except ImportError:
    # Eğer paths modülü yoksa veya import edilemiyorsa varsayılanları kullan
    _CALISMA_YOLU = os.path.expanduser("~")
    _KAYNAK_YOLU = os.path.dirname(os.path.abspath(__file__))

# 2. Dosya yollarını tanımla (Düzeltilmiş değişken isimlerini kullan)
if getattr(sys, 'frozen', False):
    _base_path = sys._MEIPASS
else:
    _base_path = os.path.dirname(os.path.abspath(__file__))

SOZLUK_TXT_YOLU = os.path.join(_base_path, "TurKod_Sozluk.txt")

# Alternatif yol kontrolü (PyInstaller onedir modunda turkod_ide/ altına paketlenir)
if not os.path.exists(SOZLUK_TXT_YOLU):
    SOZLUK_TXT_YOLU = os.path.join(_KAYNAK_YOLU, "TurKod_Sozluk.txt")
if not os.path.exists(SOZLUK_TXT_YOLU):
    # PyInstaller onedir: exe_dir/turkod_ide/TurKod_Sozluk.txt
    _exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else _base_path
    SOZLUK_TXT_YOLU = os.path.join(_exe_dir, "turkod_ide", "TurKod_Sozluk.txt")
if not os.path.exists(SOZLUK_TXT_YOLU):
    # Son çare: MEIPASS/turkod_ide/
    if getattr(sys, 'frozen', False):
        SOZLUK_TXT_YOLU = os.path.join(sys._MEIPASS, "turkod_ide", "TurKod_Sozluk.txt")

# Cache dosyası (json) - Kullanıcı klasörü
# Önbellek biçimi değişti ({imza, kelimeler}); yeni dosya adı, aynı kullanıcı
# klasörünü paylaşan eski bir TürKod sürümünün (liste bekleyen) yeni dosyayı
# okuyup otomatik tamamlamayı bozmasını önler.
CACHE_JSON_YOLU = os.path.join(_CALISMA_YOLU, ".turkod_kelimeler_v2.json")

# 3. Cache Geçersizleştirme Mantığı
def _cache_temizle():
    """Sözlük txt dosyası cache'den yeniyse eski cache'i siler."""
    try:
        if os.path.exists(SOZLUK_TXT_YOLU) and os.path.exists(CACHE_JSON_YOLU):
            if os.path.getmtime(SOZLUK_TXT_YOLU) > os.path.getmtime(CACHE_JSON_YOLU):
                os.remove(CACHE_JSON_YOLU)
    except OSError:
        pass

# Uygulama başlarken kontrol et
_cache_temizle()


def _ascii_katlanmis(yazi):
    """Türkçe karakterleri ASCII eşdeğerlerine çevirir."""
    if not isinstance(yazi, str):
        return yazi
    return yazi.translate(str.maketrans({
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U",
    }))


def _sozluk_ascii_takma_adlari(sozluk):
    """Türkçe anahtarların ASCII takma adlarını döner; kanonik yazım korunur."""
    eklenen = {}
    uyari = []
    for anahtar in list(sozluk.keys()):
        if not isinstance(anahtar, str):
            continue
        if not any(h in anahtar for h in "çğıöşüÇĞİÖŞÜ"):
            continue
        takma = _ascii_katlanmis(anahtar)
        if takma == anahtar:
            continue
        if takma in sozluk:
            mevcut = sozluk[takma]
            # Aynı ASCII karşılığına sahip iki farklı kanonik anahtar
            # doğrudan "takma ad" değil, ayrı amaçlı kelimelerdir (eskiden
            # devre_dışı -> disabled ve devre_disi -> deactivate böyleydi;
            # deactivate artık devre_dışı_bırak). Bu durumda otomatik alias
            # eklemeyi atlayıp sadece gerçek çakışma durumlarında uyarı veririz.
            if mevcut != sozluk[anahtar]:
                continue
            uyari.append(f"{anahtar} -> {takma}")
            continue
        if takma in eklenen:
            mevcut = eklenen[takma]
            if mevcut != sozluk[anahtar]:
                continue
            uyari.append(f"{anahtar} -> {takma}")
            continue
        eklenen[takma] = sozluk[anahtar]
    return eklenen, uyari


def _sozluk_yukle():
    """
    TürKod sözlüğünü yükle.

    Yukarıda bulunan SOZLUK_TXT_YOLU kullanılır. Eskiden bu fonksiyon dosyayı
    ayrı (ve farklı sıralı, çalışma dizinine de bakan) bir aramayla buluyordu;
    önbellek imzası ise SOZLUK_TXT_YOLU'nun boyutuna bakıyordu. İki arama farklı
    dosyaları bulduğunda önbellek yanlış sözlüğe göre doğrulanıyordu.
    """
    try:
        yol = SOZLUK_TXT_YOLU
        if not os.path.exists(yol):
            print(f"[TurKod] Sözlük dosyası bulunamadı: {yol}")
            return {}

        with open(yol, "r", encoding="utf-8") as f:
            icerik = f.read()
        
        bas = icerik.find("{")
        son = icerik.rfind("}") + 1
        if bas != -1 and son > bas:
            return ast.literal_eval(icerik[bas:son])
            
    except Exception as e:
        print(f"[TurKod] Sözlük yüklenemedi: {e}")
    
    return {}

SOZLUK = _sozluk_yukle()
SOZLUK_TAKMA_ADLAR = set()
SOZLUK_TAKMA_ADLARI_UYARI = []

if SOZLUK:
    _eklenen_takma, _uyari_listesi = _sozluk_ascii_takma_adlari(SOZLUK)
    SOZLUK.update(_eklenen_takma)
    SOZLUK_TAKMA_ADLAR = set(_eklenen_takma.keys())
    SOZLUK_TAKMA_ADLARI_UYARI = _uyari_listesi
    if _uyari_listesi:
        print(f"[TurKod] ASCII takma ad çakışması: {len(_uyari_listesi)} adet. Örnek: {_uyari_listesi[:3]}")

# Yeniden adlandırılan sözlük kelimelerinin eski yazımları (eski -> yeni).
# Eski adla yazılmış kod çevrilmeye devam eder; ancak bunlar takma ad sayılır:
# otomatik tamamlamada görünmez ve ters çeviride (Python -> TürKod) seçilmez.
ESKI_ADLAR = {
    'BirlikTip': 'BirleşimTip',
    'HTTPHata': 'HTTPHatası',
    'Kaydedici': 'KancaKaydedici',
    'Nihai_Tip': 'NihaiTip',
    'Protokol_Tip': 'ProtokolTip',
    'Sabit_Tip': 'SabitTip',
    'SatırEşleşme': 'SatırEşleştirici',
    'SeçmeliTip': 'İsteğeBağlıTip',
    'SınıfDeğişkeni_Tip': 'SınıfDeğişkeniTip',
    'YanıtHatası': 'İstekHatası',
    '_bölge_açıkmı': '_bölge_açık_mı',
    '_diger_argümanlar': '_diğer_argümanlar',
    '_zorunlu_kimlik': '_kimlik_bilgilerini_zorla',
    'agirisi': 'öğrenme_oranı',
    'aglayici_sınıf': 'akış_sınıfı',
    'agrega_ileti_mesajları_görme': 'abonelik_mesajlarını_yoksay',
    'aktarim_büyüklüğü': 'aktarım_büyüklüğü',
    'aktarim_oranı': 'aktarım_oranı',
    'aktif_sayı': 'etkin_iş_parçacığı_sayısı',
    'akışına_yaz': 'akışa_yaz',
    'akışından_oku': 'akıştan_oku',
    'al_veri': 'veri_al',
    'alana_kadar_al': 'koşul_sürdükçe_al',
    'alt_bilgi_ofset': 'alt_bilgi_ötelemesi',
    'alt_kayıtlar': 'alt_anahtarlar',
    'alt_sınıf_mi': 'alt_sınıf_mı',
    'altaire_tablosu': 'altair_grafiği',
    'altdizim': 'alt_küme',
    'anahtar_ön_ek': 'anahtar_ön_eki',
    'anahtarveyapati': 'anahtar_veya_desen',
    'animasyon_döngü': 'animasyon_döngüsü',
    'anlatan_bileşenler': 'etiketleyen_bileşenler',
    'anlik_bekleme_süresi': 'yoklama_zaman_aşımı',
    'araya_interpolasyon_mu': 'ara_değerlenmiş_mi',
    'arsiv_aç': 'arşiv_aç',
    'arsiv_oluştur': 'arşiv_oluştur',
    'asenkron_bytelar_girdi_çıktı_yük': 'eşzamansız_bayt_gç_yük',
    'asenkron_bytelar_yük': 'eşzamansız_bayt_yük',
    'asenkron_fonksiyon': 'eşzamansız_fonksiyon',
    'asenkron_iterlenebilir_yük': 'eşzamansız_yinelenebilir_yük',
    'asenkron_metin_okuyucu_yük': 'eşzamansız_tamponlu_okuyucu_yük',
    'asenkron_yinelenebilir_yük': 'eşzamansız_yinelenebilir_yük',
    'asenkron_çözücü': 'eşzamansız_çözücü',
    'at_küme': 'kümeden_at',
    'atla_altbilgi': 'alt_bilgiyi_atla',
    'atla_başlık': 'başlığı_atla',
    'atla_satırlar': 'atlanacak_satırlar',
    'atla_yok': 'eksikleri_atla',
    'aws_erişim_anahtari': 'aws_erişim_anahtarı',
    'aylik_sınır': 'aylık_sınır',
    'azure_ad_simgelesi': 'azure_ad_tokeni',
    'azure_ad_simgelesi_sağlayıcı': 'azure_ad_token_sağlayıcısı',
    'azure_endpoint': 'azure_uç_noktası',
    'aç_ifadeyi': 'ifadeyi_aç',
    'ağ_çiz': 'ızgara_çiz',
    'ağırlıklı_bozunma': 'ağırlık_bozunması',
    'bakışlar': 'arama_tabloları',
    'basılı_tuş': 'basılı_tuşlar',
    'bağlama_harita_arayüzü': 'zincir_harita_vekili',
    'bağlantı_anahtari': 'bağlantı_anahtarı',
    'bağlantı_mi': 'bağlantı_mı',
    'bağlantı_süresi': 'canlı_tutma_zaman_aşımı',
    'bağlantı_tekrar_dene': 'bağlantı_yeniden_deneme',
    'bağlantı_zaman_asimi': 'bağlantı_zaman_aşımı',
    'bağıntılı_adım': 'göreli_adım',
    'başlangıç_indeks': 'başlangıç_indeksi',
    'başlangıç_mi': 'başlangıç_mı',
    'başlangıç_satır': 'başlangıç_satırı',
    'başlangıç_sütun': 'başlangıç_sütunu',
    'başlatmadan_sonra': 'başlattıktan_sonra',
    'başlık_grafik': 'grafik_başlığı',
    'başlık_mi': 'başlık_mı',
    'başlık_satiri': 'başlık_satırı',
    'baştan_at': 'koşul_sürdükçe_at',
    'bekle_eşzamansız': 'eşzamansız_bekle',
    'bellek': 'tutamaç',
    'bic': 'yineleyici_dilimle',
    'bir_kez_çağrıldı_mi': 'bir_kez_çağrıldı_mı',
    'birleştir_pd': 'art_arda_birleştir',
    'bit_xor': 'bit_özel_veya',
    'bitiş_indeks': 'bitiş_indeksi',
    'bitiş_sütun': 'bitiş_sütunu',
    'boş_eleman_kapama_ön_ek': 'boş_eleman_kapama_ön_eki',
    'boş_oznitelikler_mantıksal': 'boş_öznitelikler_mantıksal',
    'boş_token_id': 'başlangıç_token_id',
    'byte': 'bayt',
    'byte_dizisi': 'bayt_dizisi',
    'büyük_mu': 'büyük_mü',
    'c_boş': 'c_boş_işaretçi',
    'curume_oranı': 'bozunma_oranı',
    'cython_çift_çift_mesafeyi_aktif_et': 'cython_ikili_mesafeyi_etkinleştir',
    'daha_büyük_mu': 'daha_büyük_mü',
    'daha_küçük_mu': 'daha_küçük_mü',
    'dakikalik_sınır': 'dakikalık_sınır',
    'damga_zaman': 'damgadan_tarih',
    'dağılım_gamma': 'dağılım_gama',
    'depo_hesabı': '_depo_hesabı',
    'depo_seçenekleri_endpoint_url_sahip_mi': '_depo_seçeneklerinde_uç_nokta_url_var_mı',
    'depolama_kapla': 'depolamayı_sar',
    'derece_çevrimi': 'radyandan_dereceye',
    'derleyici_sürüm': 'derleyici_sürümü',
    'değişim_zamanı': 'değişince',
    'değiştirilebilir_dizi': 'DeğiştirilebilirDiziTip',
    'değiştirilebilir_eşleştirme': 'DeğiştirilebilirEşlemeTip',
    'değiştirilebilir_küme': 'DeğiştirilebilirKümeTip',
    'dikkat_olasılığı_düşme': 'dikkat_olasılıkları_bırakma_olasılığı',
    'dikkat_yönlendirme': 'dikkat_sapması',
    'diskikodlama': 'hariç_kodlamalar',
    'diskten_önce': 'diske_yazmadan_önce',
    'dizi': 'DiziTip',
    'dizi_api_gönder': 'dizi_api_yönlendir',
    'dizin_sütun': 'indeks_sütunu',
    'dizin_sütunları': 'indeks_sütunları',
    'dizin_tipi': 'indeks_tipi',
    'django_bağlantısı': 'django_adresleri',
    'django_formu': 'django_formları',
    'django_görünümü': 'django_görünümleri',
    'django_migrasyonu': 'django_migrasyonları',
    'django_uygulama': 'django_uygulaması',
    'django_şablonu': 'django_şablonları',
    'docker_ağ': 'docker_ağları',
    'docker_hacim': 'docker_birimleri',
    'dolgu_boş': 'boşlukları_doldur',
    'dondurulmus_bileşenler': 'dondurulmuş_bileşenler',
    'donme_göster': 'yükleniyor_göster',
    'dosya_dialogu': 'dosya_diyaloğu',
    'dosya_kabulü': 'dosya_kabul_et',
    'dosya_metadatasini_kopyala': 'dosya_meta_verisini_kopyala',
    'durum_bağlam': 'durum_bağlamı',
    'durum_metodu': 'statik_metot',
    'dön_dict': 'sözlük_döndür',
    'dönüştür_np': 'tür_dönüştürme',
    'dönüşüm_Aimv2GörselKonfig': 'aimv2_görsel_yapılandırması',
    'dönüşüm_Aimv2MetinKonfig': 'aimv2_metin_yapılandırması',
    'dönüşüm_Aimv2MetinModel': 'aimv2_metin_modeli',
    'dönüşüm_Aimv2Model': 'aimv2_modeli',
    'dönüşüm_Aimv2OnHazirModel': 'aimv2_ön_eğitilmiş_modeli',
    'düz_değerler_özellikleri': 'düz_değerler_belirtimi',
    'editör_kamera': 'düzenleyici_kamerası',
    'ekle_küme': 'kümeye_ekle',
    'ekle_parça': 'parça_ekle',
    'ekle_saniye': 'saniye_bekle',
    'ekleme_modu': 'sona_ekle',
    'eklenti_afmoe_modeli': 'afmoe_modeli',
    'eklenti_afmoe_nedensel_lm': 'afmoe_nedensel_dil_modeli',
    'eklenti_afmoe_yapılandırma': 'afmoe_yapılandırması',
    'eklenti_afmoe_ön_egitilmis_modeli': 'afmoe_ön_eğitilmiş_modeli',
    'eklenti_aimv2_yapılandırma': 'aimv2_yapılandırması',
    'eklenti_ekle': 'eklenen_token',
    'elekman': 'eleman_nesnesi',
    'elekman_şekli': 'eleman_şekli',
    'elekmanlar': 'eleman_nesneleri',
    'eleman_kilidi_tanımı': 'kritik_bölüm_tanımı',
    'eleman_özelliği': 'eleman_belirtimi',
    'element_sınıfları': 'eleman_sınıfları',
    'engelleyici_ayarla': 'engelleme_ayarla',
    'eos_token_id': 'bitiş_token_id',
    'eve_git': 'ev_dizini',
    'eğitim_corpus': 'eğitim_derlemi',
    'eşleştirme': 'EşlemeTip',
    'faktoriyel': 'faktöriyel',
    'fare_aşağı_yukarı': 'fare_bas_bırak',
    'fare_basılı': 'fare_basılınca',
    'fare_bırakma': 'fare_bırakılınca',
    'fare_giriş': 'fare_üstüne_gelince',
    'fare_çıkış': 'fare_üstünden_çıkınca',
    'filtrele_ile': 'alana_göre_süz',
    'flask_flash_mesajı': 'flask_anlık_mesaj',
    'flask_gönder_dosya': 'flask_dosya_gönder',
    'flask_şablon_render': 'flask_şablonu_işle',
    'foreign_key': 'YabancıAnahtar',
    'forma_verisi': 'form_verisi',
    'format_değişkenleri': 'biçim_değişkenleri',
    'full_so_sürüm': 'tam_so_sürümü',
    'gamma_fonk': 'gama_fonksiyonu',
    'gamma_log': 'gama_logaritma',
    'gelişim_corpus': 'geliştirme_derlemi',
    'genişlet_sekme': 'sekmeleri_genişlet',
    'gereksiz': 'isteğe_bağlı',
    'geçici_işletim_sistemi_dizini': 'geçici_dizin_yolu',
    'giriş_dosyasi': 'giriş_dosyası',
    'git_id': 'git_kimliği',
    'git_koordinat': 'konuma_git',
    'gizli_düşme_olasılığı': 'gizli_bırakma_olasılığı',
    'gizli_etkinlik': 'gizli_aktivasyon',
    'global_dikkat_her_n_katman': 'küresel_dikkat_her_n_katman',
    'gönder_eposta': 'eposta_gönder',
    'gönder_mesaj': 'mesaj_gönder',
    'gönder_veri': 'veri_gönder',
    'görme': 'görünürlük',
    'görsel_konfig': 'görsel_yapılandırması',
    'güncelle_sarmalayici': 'güncelle_sarmalayıcı',
    'güncelleme_önce': 'güncellemeden_önce',
    'güvenli_bağlantısı': 'güvenli_bağlantı',
    'güvenli_token_byte': 'güvenli_token_bayt',
    'güvenli_token_hex': 'güvenli_token_onaltılık',
    'güvenlik_ayarlari': 'güvenlik_ayarları',
    'güvenlik_gruplari': 'güvenlik_grupları',
    'güvenlik_kurali': 'güvenlik_kuralı',
    'güvenlik_kurallari': 'güvenlik_kuralları',
    'güvenlik_politikasi': 'güvenlik_politikası',
    'harf_değiştir': 'büyük_küçük_değiştir',
    'harf_mı': 'harf_mi',
    'harf_sayı_mi': 'harf_sayı_mı',
    'harf_sırası': 'sözlük_sıralaması',
    'hash_değeri': 'özet_değeri',
    'hata_fonksiyonu_t': 'tümleyen_hata_fonksiyonu',
    'hepsi_eşit_mi': 'hepsi_yakın_mı',
    'hepsini_getir_glob': 'desenle_bul',
    'hepsini_getir_rglob': 'alt_dizinlerde_desenle_bul',
    'hepsini_sorgula': 'sorgula',
    'her_kaç_dönen_kaydet': 'her_dönemde_kaydet',
    'her_kaç_kaydet': 'her_n_adımda_kaydet',
    'host_basi_sınır': 'ana_bilgisayar_başına_sınır',
    'iceri_yerleştir': 'konuma_ekle',
    'ileti_şablonu': 'mesaj_kutusu',
    'import_kapsamı': 'içe_aktarma_kapsamı',
    'imza': 'sinyal_numarası',
    'indeks_maksimum': 'en_büyüğün_indeksi',
    'indeks_minimum': 'en_küçüğün_indeksi',
    'indeks_yoksay': 'indeksi_yoksay',
    'inssa': 'inşa_edici',
    'ip_uzatma_parametreleri': 'döner_konum_parametreleri',
    'isil_düzenle': 'ısınma_başlat',
    'iso_format': 'iso_biçimi',
    'istemci_ara_yuzu_tipi': 'istemci_ara_katman_tipi',
    'istemci_bağlayıcı_dns_hata': 'istemci_bağlayıcı_dns_hatası',
    'istemci_bağlayıcı_hata': 'istemci_bağlayıcı_hatası',
    'istemci_bağlayıcı_sertifika_hata': 'istemci_bağlayıcı_sertifika_hatası',
    'istemci_bağlayıcı_ssl_hata': 'istemci_bağlayıcı_ssl_hatası',
    'istemci_max_büyüklüğü': 'istemci_maks_büyüklüğü',
    'istemci_vekil_bağlantı_hata': 'istemci_vekil_bağlantı_hatası',
    'istisna_bilgi': 'istisna_bilgisi',
    'iten_başlıkları': 'istek_başlıkları',
    'iten_verisi': 'istek_verileri',
    'iten_yöntemi': 'istek_yöntemi',
    'itirilebilir': 'yinelenebilir_değer',
    'iz_kalınlığı': 'çizgi_kalınlığı',
    'iz_stili': 'çizgi_stili',
    'iz_surer': 'izler',
    'izdusum': 'eşle',
    'izleyici_kapat': 'izleyici_ayarla',
    'içe_aktar_builtin': 'içe_aktar_özel',
    'içerik_uzunlugu': 'içerik_uzunluğu',
    'işle': 'iş_tanımı',
    'işle_yükümlülüğü': 'iş_yükü_kimliği',
    'işlem_kesme': 'işlem_yalıtımı',
    'işleme': 'işaretleme',
    'işlemi_teyit_et': 'işlemi_onayla',
    'işletim_sistemi_hata': 'işletim_sistemi_hatası',
    'joystick_sistemi': 'oyun_kolu_sistemi',
    'json_şema_input_tipi': 'json_şema_girdi_tipi',
    'kalıcı_son_tarih': 'canlı_tutma_süresi_sonu',
    'kapalı_temizleme_aktif': 'kapalıları_temizlemeyi_etkinleştir',
    'katisa': 'katı_mod',
    'katman_norm_eps': 'katman_norm_hata_payı',
    'katmanlama_büyüklüğü': 'gömme_büyüklüğü',
    'katı_teknik_geçerme': '_katı_yanıt_doğrulama',
    'katılma_tarihi': 'kayıt_tarihi',
    'katılım_bekle': 'bitmesini_bekle',
    'kaynakkodlama': 'kaynak_kodlaması',
    'kayıt_tipi': 'excel_lehçesi',
    'kelime_gomme_bağla': 'kelime_gömmelerini_bağla',
    'kesme': 'kısayol',
    'kestane': 'bordo',
    'kirli_sprite': 'kirli_hareketli_resim',
    'kitaplık_sürümü': 'kütüphane_sürümü',
    'kivy_anahtar': 'kivy_açma_kapama',
    'kivy_izgara_yerleşimi': 'kivy_ızgara_yerleşimi',
    'komut_hatasında': 'betik_hatasında',
    'komut_yolu': 'betik_yolu',
    'komut_çalıştır': 'betik_çalıştır',
    'koordinat': 'koordinatlar',
    'kopya_kaydedici': 'kopya_kayıt_defteri',
    'kopya_oluştur': 'yineleyici_çoğalt',
    'kopyala_derin': 'derin_kopyala',
    'korpuslar': 'derlemler',
    'kullanıcı_grup': 'kullanıcı_grubu',
    'kullanım_miktari': 'kullanım_miktarı',
    'kumulatif_çarpım': 'kümülatif_çarpım',
    'kümesi': 'KümeTip',
    'küçük_mu': 'küçük_mü',
    'kırma_noktası': 'kesme_noktası',
    'kırp_sıfır': 'tam_kısım',
    'kısa_kesme_esigi': 'kırpma_eşiği',
    'kısmı_fonksiyon': 'kısmi_fonksiyon',
    'kısmı_metot': 'kısmi_metot',
    'lineer_regresyon': 'doğrusal_regresyon',
    'log_dosyası': 'günlük_dosyası',
    'log_ekran_görüntüsü': 'ekran_görüntüsünü_günlükle',
    'logaritma_ölçek_baslama_değeri': 'logit_ölçek_başlangıç_değeri',
    'loglayıcı': 'kaydedici',
    'maks_girdiler': 'maks_girdi_sayısı',
    'maksimum_dene': 'maks_deneme',
    'maksimum_sıkıştırma_büyüklüğü': 'maks_sıkıştırma_açma_büyüklüğü',
    'maksimum_token': 'maks_token',
    'max_adım': 'maks_adım',
    'max_büyüklük_hata_sınıfı': 'maks_büyüklük_hata_sınıfı',
    'max_dönem': 'maks_dönem',
    'max_dönen': 'maks_dönem',
    'max_karakter': 'maks_karakter',
    'max_logaritma_ölçek': 'maks_logit_ölçek',
    'max_logit_ölçek': 'maks_logit_ölçek',
    'max_tamsayı': 'maks_tamsayı',
    'max_unicode': 'maks_unicode',
    'max_uzunluk': 'maks_uzunluk',
    'max_yükleme_boyutu': 'maks_yükleme_boyutu',
    'mel_cepleri_sayısı': 'mel_kutusu_sayısı',
    'mesaj_ve_istisna': 'mesaj_veya_istisna',
    'meta_veri_yonlendirmesini_aktif_et': 'meta_veri_yönlendirmesini_etkinleştir',
    'mimari': 'mimariler',
    'min_boyut': 'en_az_boyut',
    'mlp_ölçüt': 'mlp_sapması',
    'mod_ist': 'istatistik_modu',
    'moe_ara_sözlük_büyüklüğü': 'moe_ara_büyüklük',
    'müşteri': 'istemci',
    'nan_boş': 'nan_boşa_çevir',
    'nokta_ışık': 'nokta_ışığı',
    'null_kısıt': 'boş_değer_kısıtı',
    'odeyi_kullan': 'önbellek_kullan',
    'ofset': 'öteleme',
    'oku_izni': 'okuma_izni',
    'olay_baloncuk': 'olay_kabarcıklanma',
    'olay_bağlantıkesildi': 'olay_bağlantı_kesildi',
    'olay_başla': 'olay_başlangıcı',
    'olay_bitir': 'olay_bitişi',
    'olay_büyüt': 'olay_boyutlandır',
    'olay_devam_ediyor': 'olay_sürdürüldü',
    'olay_dinle': 'olay_işleyicisi',
    'olay_durdurulmuş': 'olay_duraklatıldı',
    'olay_fare_basili_bırakma': 'olay_fare_bırakma',
    'olay_fare_basılı_bırakma': 'olay_fare_bırakma',
    'olay_giriş': 'olay_girdi',
    'olay_hata': 'olay_hatası',
    'olay_hata_işlem': 'olay_hata_işleme',
    'olay_ilklem': 'olay_ilerleme',
    'olay_iptal': 'olay_durdurma',
    'olay_iptali': 'olay_iptal_edildi',
    'olay_tamamlanmış': 'olay_tamamlandı',
    'olay_tetikleyici': 'çağır',
    'olay_tuş_basili_bırakma': 'olay_tuş_bırakma',
    'olay_tuş_basili_tutma': 'olay_tuş_basılı_tutma',
    'olay_tuş_basılı_bırakma': 'olay_tuş_bırakma',
    'olay_tuş_basımı': 'olay_tuşa_basma',
    'olay_tıkla': 'olay_tıklama',
    'olay_yeniden_başla': 'olay_yeniden_başladı',
    'olay_çift_tıkla': 'olay_çift_tıklama',
    'olay_özel': 'olay_varsayılan',
    'one_çıkar': 'öne_ekle',
    'orta_yazılım': 'ara_katman',
    'ortam_doğru': 'ortama_güven',
    'ortam_kur': 'ortam_değişkeni_ayarla',
    'oto_başlıkları_atla': 'otomatik_başlıkları_atla',
    'oto_init_otonom_anahtar': '_oto_başlatma_işlenmemiş_anahtar',
    'otomatik_kullanım': '_otomatik_kullanım',
    'otomatik_çalıştır': 'otomatik_çal',
    'oyasam_süresi': 'yaşam_süresi',
    'oylayici': 'açılır_kutu',
    'oyutlandirilabilir_mi': 'boyutlandırılabilir_mi',
    'pad_token_id': 'dolgu_token_id',
    'paralel_sınır': 'eşzamanlı_sınır',
    'parametre_ile_çağrıldı_mi': 'parametre_ile_çağrıldı_mı',
    'parola_işlevleri': 'özet_fonksiyonları',
    'parça_anahtarlari': 'bölüm_anahtarları',
    'parça_anahtarları': 'bölüm_anahtarları',
    'parça_büyüklüğü': 'yama_büyüklüğü',
    'parça_büyüklüğü_beslenme': 'ileri_besleme_parça_büyüklüğü',
    'parça_dizininde': 'bölüm_içi_indeks',
    'parçalı_sıra': 'düzensiz_derece',
    'perde': 'ses_perdesi',
    'pipe_yaratıldıktan_sonra': 'işlem_hattı_oluşturulduktan_sonra',
    'popülasyon_sapma': 'popülasyon_standart_sapması',
    'popülasyon_varyans': 'popülasyon_varyansı',
    'postakodu': 'posta_kodu',
    'pozisyon_katmanı_büyüklüğü': 'maks_konum_gömmeleri',
    'primary_key': 'birincil_anahtar',
    'pytest_bilgi': '_pytest_mi',
    'qkv_ölçüt': 'qkv_sapması',
    'qt_kutu_yerleşimi_h': 'qt_yatay_kutu_yerleşimi',
    'qt_kutu_yerleşimi_v': 'qt_dikey_kutu_yerleşimi',
    'radyan_çevrimi': 'dereceden_radyana',
    'redis_ekle': 'redis_ayarla',
    'redis_küme': 'redis_kümesi',
    'redis_sona_al': 'redis_sondan_al',
    'redis_süre_ekle': 'redis_süreli_ayarla',
    'render_modu': 'işleme_modu',
    'rolu_devral': 'rolü_üstlen',
    'satır_sonu': 'bitiş_satırı',
    'sayfa_komutu': 'sayfa_betiği',
    'sayfa_num': 'sayfa_no',
    'sayı_mi': 'sayı_mı',
    'schema_asimlar': 'şema_geçersiz_kılmaları',
    'sembolleştirilmiş_dosya': 'şifrelenmiş_dosya',
    'serbest_bırakma': 'bırakılınca',
    'serpilme_grafiği': 'dağılım_grafiği',
    'sertifika_hata': 'sertifika_hatası',
    'ses_kabulü': 'ses_kabul_et',
    'seçim_al': 'seçili_olanlar',
    'seçim_kipi': 'seçim_modu',
    'silme_modu': 'öğe_sil',
    'simbol': 'sembol',
    'simboller': 'semboller',
    'simge_pozisyonu': 'simge_konumu',
    'skor_ağırlıkları': 'puan_ağırlıkları',
    'so_sürüm': 'so_sürümü',
    'soket_aile_inet': 'soket_ailesi_ipv4',
    'soket_aile_inet6': 'soket_ailesi_ipv6',
    'soket_tipi_dgram': 'soket_türü_veri_paketi',
    'soket_tipi_stream': 'soket_türü_akış',
    'sonlu_olsun': 'sonlu_varsay',
    'sonraki_say': 'sonraki_kayan_sayı',
    'sonraki_ulp': 'son_basamak_birimi',
    'sorgu_filtre': 'sorgu_filtresi',
    'sorgu_grupla': 'sorgu_gruplaması',
    'sorgu_ofset': 'sorgu_ötelemesi',
    'sorgu_sınır': 'sorgu_sınırı',
    'sorgu_sırala': 'sorgu_sıralaması',
    'spot_ışık': 'spot_ışığı',
    'sprit': 'hareketli_resim',
    'streamlit_buton': 'streamlit_düğme',
    'sözlük_büyüklüğü': 'kelime_dağarcığı_büyüklüğü',
    'sözlük_veri': 'kelime_dağarcığı_verisi',
    'sürekli': 'kalıcı',
    'süreç_bilgisi': 'sistem_bilgisi',
    'sütunlar_pd': 'sütunlar',
    'süz_yalancı': 'süz_yanlışları',
    'sıfır_kodu': 'dönüş_kodu',
    'sıkıştırma_çöz': 'sıkıştırmayı_aç',
    'sınıf_temizle_test': 'sınıf_sonrası_temizle',
    'sınır_kalinligi': 'sınır_kalınlığı',
    'sırala_anahtari': 'sıralama_anahtarı',
    'sırala_builtin': 'sıralanmış',
    'sırala_değerler': 'değerlere_göre_sırala',
    'sırala_indeks': 'indekse_göre_sırala',
    'tam_so_sürüm': 'tam_so_sürümü',
    'tanım_değil': 'sayı_değil',
    'tanım_değil_mi': 'sayı_değil_mi',
    'tanımlayıcı_mi': 'tanımlayıcı_mı',
    'tar_aç': 'açık',
    'tar_oku': 'hepsini_çıkar',
    'tekil_kısıt': 'tekillik_kısıtı',
    'tekrar_dene_sayısı': 'tekrar_deneme_sayısı',
    'tekrar_düşür': 'tekrarları_at',
    'temizle_test': 'test_sonrası_temizle',
    'tensor_dizisi_adı': 'tensör_dizisi_adı',
    'ters_çevir_builtin': 'ters_çevrilmiş',
    'test_belge_öğesi': 'test_belge_testi_öğesi',
    'test_dosya': 'test_dosyası',
    'test_fikstür_ara_hatası': 'test_fikstür_arama_hatası',
    'test_istisnabilgi': 'test_istisna_bilgisi',
    'tip_kontrol': 'tip_kontrolü',
    'tip_sözlük_büyüklüğü': 'tip_dağarcığı_büyüklüğü',
    'token2vec_başlat': 'tok2vec_başlat',
    'token_oluştur': 'tokenleştirici_oluştur',
    'topla_eşzamansız': 'eşzamansız_topla',
    'toplu_gradiyan': 'gradyan_biriktir',
    'toplu_işlem': 'toplu_işleyici',
    'torch_adım_atla': 'torch_adım_at',
    'torch_sıfırla': 'torch_gradyan_sıfırla',
    'transformers_sürüm': 'transformers_sürümü',
    'transpoz': 'devrik',
    'tür_enum': 'tür_numaralandırması',
    'tıklama_zamanı': 'tıklanınca',
    'uds': 'unix_soketi',
    'url_kodu_çöz': 'url_kodunu_çöz',
    'urlyolu': 'url_yolu',
    'ursina_ikon': 'ursina_simge',
    'ursina_ikon_rengi': 'ursina_simge_rengi',
    'ursina_metin_içerik': 'ursina_metin_içeriği',
    'ursina_metin_köken': 'ursina_metin_kökeni',
    'uygulama_istisnalarini_oluştur': 'uygulama_istisnalarını_fırlat',
    'uygunluk_mu': 'doğruluk_değeri',
    'uzantı_ad': 'uzantı_adı',
    'varlık_cezası': 'bulunma_cezası',
    'varsayılan_başlık': 'varsayılan_başlıklar',
    'varsayılan_kısıt': 'varsayılan_değer_kısıtı',
    'varsayılanları_iade_et': 'varsayılanları_geri_yükle',
    'veri_getir': 'birini_getir',
    'veritabanı_kullanıcı': 'veritabanı_kullanıcısı',
    'veritabanı_port': 'veritabanı_bağlantı_noktası',
    'veritabanı_sunucu': 'veritabanı_sunucusu',
    'veritabanı_şifre': 'veritabanı_şifresi',
    'versiyon_bilgisi': 'sürüm_bilgisi',
    'webhook_gizli': 'webhook_sırrı',
    'x_ofset': 'x_öteleme',
    'xml_rpc_istemci': 'xml_rpc_sunucu_vekili',
    'y_ofset': 'y_öteleme',
    'yakınsa': 'yakın_mı',
    'yalnızca_degisenleri_yazdır': 'yalnızca_değişenleri_yazdır',
    'yalnızca_çözümle': 'yalnızca_ayrıştır',
    'yanlış_mi_iddia_et': 'yanlış_mı_iddia_et',
    'yansima_boyutu': 'izdüşüm_boyutu',
    'yanıt_bağlantı_geçmişi': 'yanıt_geçmişi',
    'yanıt_kurabiyeleri': 'yanıt_çerezleri',
    'yapılan_deneme': 'yapılan_deneme_sayısı',
    'yaratmadan_sonra': 'oluşturduktan_sonra',
    'yaratmadan_önce': 'oluşturmadan_önce',
    'yatay_pencere': 'kayan_pencere',
    'yatay_çubuk_grafigi': 'yatay_çubuk_grafiği',
    'yaygın_isim': 'paylaşılan_ad',
    'yaygınlık': 'bırakma_oranı',
    'yazı_izni': 'yazma_izni',
    'yeniden_boyutlandır': 'yeniden_boyutlandırılabilir',
    'yenileme_biçimi': 'yenileme_modu',
    'yetki_kontrol': 'yetki_kontrolü',
    'yigil': 'iz_kaydı',
    'yigil_trace': 'yığın_izi',
    'yillik_sınır': 'yıllık_sınır',
    'yinelenebilir': 'YinelenebilirTip',
    'yineleyici_tip': 'YineleyiciTip',
    'yok_değer': 'eksik_değer',
    'yok_değerler': 'eksik_değerler',
    'yol_ayır': 'uzantıyı_ayır',
    'yol_ölçeği': 'yönlendirme_ölçeği',
    'yoğunluk': 'hassasiyet',
    'yuvayı_kalıcı': 'soket_canlı_tut',
    'yuvayı_kalıcı_seçenekleri': 'soket_canlı_tut_seçenekleri',
    'yuvayı_türü': 'soket_türü',
    'yönetim_akışı': 'yönetici_api_anahtarı',
    'yönler': 'rotalar',
    'yüz': 'profil_resmi',
    'yüzde_100_bekle': 'devam100_bekle',
    'yüzde_100_devam': 'devam100',
    'zaman_aşımı_seviyesi': 'zaman_aşımı_tavan_eşiği',
    'zaman_değişim': 'değiştirilme_zamanı',
    'zaman_erişim': 'erişim_zamanı',
    'zaman_oluşturma': 'oluşturulma_zamanı',
    'zayıf_anahtar_sözlük': 'zayıf_anahtarlı_sözlük',
    'zayıf_sözlük': 'zayıf_değerli_sözlük',
    'zeytin': 'zeytin_yeşili',
    'zip_oku': 'oku',
    'zip_yaz': 'yaz',
    'zıpla_uzun': 'en_uzuna_eşle',
    'çalışma_bellek': 'çalışma_belleği',
    'çalıştır_izni': 'çalıştırma_izni',
    'çarpışma_giriş': 'çarpışma_başlayınca',
    'çarpışma_çıkış': 'çarpışma_bitince',
    'çay_renk': 'koyu_turkuaz',
    'çağrıldı_mi': 'çağrıldı_mı',
    'çağır_tekrarlı': 'tekrarlı_çağır',
    'çevirim_tablo': 'çeviri_tablosu',
    'çevre_al': 'ortam_değişkeni_al',
    'çevre_değişkenleri': 'ortam_değişkenleri',
    'çift_çift_mesafe_parça_büyüklüğü': 'ikili_mesafe_parça_büyüklüğü',
    'çiftler': 'bağlama_noktaları',
    'çimen_renk': 'limon_yeşili',
    'çoklu_veri_getir': 'birkaçını_getir',
    'çubuk_grafigi': 'çubuk_grafiği',
    'çözme': 'kod_çözme',
    'çözücü_anahtar_argümanları': 'ayrıştırıcı_anahtar_argümanları',
    'çözücü_argüman_isimleri': 'ayrıştırıcı_anahtar_argümanları',
    'çözücü_argümanları': 'ayrıştırıcı_argümanları',
    'çıktı_değiştir': 'çıktı_değişimine_izin_ver',
    'çıktı_gizli_durumlari': 'çıktı_gizli_durumları',
    'çıktı_yönlendirme_logiti': 'çıktı_yönlendirici_logitleri',
    'çıktısı_kontrol_et': 'çıktıyı_kontrol_et',
    'çıkış_dosyasi': 'çıkış_dosyası',
    'ön_bellek': 'önbellek',
    'ön_bellek_lru': 'önbellek_lru',
    'önbellek_fabrikasi': 'önbellek_fabrikası',
    'öncesi_sıra': 'öncelik_kuyruğu',
    'örgü_editörü': 'örgü_düzenleyicisi',
    'özellik_adı': 'özellik',
    'özellik_var_mi': 'özellik_var_mı',
    'özelliği': 'belirtim',
    'özet_onalti_al': 'özet_onaltılık_al',
    'özeti': 'özetle',
    'üreteci': 'ÜreteçTip',
    'üssü': 'üs_al',
    'üst_eksi_1': 'üstel_eksi_1',
    'şablon_render': 'şablonu_işle',
    'şablon_seç': 'şablon_al',
    'şart_np': 'koşula_göre_seç',
    'şekil_metni': 'şablon_metni',
    'şekil_çıkar': 'şekil_çıkarsa',
    'şema_uzunlugu_bul': 'şema_uzunluğu_bul',
}

if SOZLUK:
    _eksik_eski = []
    for _eski, _yeni in ESKI_ADLAR.items():
        _eski_desen = rf"\b{_eski}\b"
        _yeni_desen = rf"\b{_yeni}\b"
        if _yeni_desen not in SOZLUK:
            _eksik_eski.append(_yeni)
            continue
        if _eski_desen in SOZLUK:
            continue
        SOZLUK[_eski_desen] = SOZLUK[_yeni_desen]
        SOZLUK_TAKMA_ADLAR.add(_eski_desen)
    if _eksik_eski:
        print(f"[TurKod] ESKI_ADLAR sözlükte olmayan kelimeye işaret ediyor: {_eksik_eski[:5]}")

if not SOZLUK:
    print("[TurKod] UYARI: Sözlük dosyası bulunamadı veya boş!")

TERS_SOZLUK_ONCELIK = {
    # Genel dosya/metin metotları: eskiden "dosya.write" -> "dosya.zip_yaz",
    # "','.join" -> "','.katılım_bekle" gibi yanıltıcı karşılıklara gidiyordu.
    "write": "yaz",
    "read": "oku",
    "join": "birleştir",
    "min": "minimum",
    "max": "maksimum",
    "abs": "mutlak",
    "round": "yuvarla",
    "open": "açık",
    "font": "yazı_tipi",
    "append": "sona_ekle",
    "math": "matematik",
    "render": "yazı_oluştur",
    "remove": "kaldır",
    "get": "getir",
    "format": "biçimle",
    "forward": "ileri",
    "Button": "düğme",
    "Text": "metin_alanı",
    "input": "girdi_al",
    "set": "küme",
    "compile": "derle",
    "quit": "oyun_kapat",
    "wait": "eşzamansız_bekle",
    # Bu hedefler birden fazla Türkçe kelimeye bağlı; en yaygın kullanım seçilir.
    "mode": "kip",                 # open(..., mode=) (istatistik modu değil)
    "tail": "son_satırlar",        # df.tail() (xml_kuyruk değil)
    "Slider": "ursina_kaydırıcı",
    "max_length": "maks_uzunluk",
    "stop": "bitiş",
    "step": "adım",
    "save": "kaydet",
    "autoplay": "otomatik_çal",
    "on_click": "tıklanınca",
    "delay": "gecikme",
    "event_handler": "olay_işleyicisi",
    "origin": "köken",
    # Aşağıdakiler birden fazla Türkçe anahtara bağlı hedeflerdir; ters
    # çeviride (Python -> TürKod) hangisinin seçileceğini netleştirir.
    # Bu, ambiguity'i sadece TEK hedef için giderir; SOZLUK'taki kaynak
    # çakışmanın kendisini ortadan kaldırmaz (bkz. not aşağıda).
    "title": "başlık_yap",
    "update": "güncelle",
    "text": "xml_metin",
    "icon": "simge",
    "color": "renk",
    "size": "boyut",
    "scene": "sahne",
    "invoke": "çağır",
    "grid": "ızgarala",
    "run": "çalıştır_oyun",
    "delete": "öğe_sil",
    # "column" -> "sütun_no" ile tutarlı olsun (eskiden grid(row=0, column=1)
    # -> ızgarala(satır=0, sütun_no=1) üretiyordu).
    "row": "satır_no",
    "geometry": "geometri",
    "fg": "ön_renk_kısa",
    # Eskiden tek karşılıkları başka kütüphaneye aitti: Image.new -> hmac_yeni,
    # img.load() -> json_yükle, vektör.length() -> ses_uzunluğu,
    # oyuncu.speed -> hız_ayarla.
    "new": "yeni",
    "load": "yükle",
    "length": "uzunluğu",
    "speed": "hız",
    "transpose": "devriğini_al",
    # numpy/pandas ".shape" -> "şekil" (eskiden "biçim" seçiliyordu;
    # "biçim" daha çok format anlamında okunur).
    "shape": "şekil",
}


def _ters_sozluk_olustur():
    ters_sozluk = {}
    for desen, python_karsiligi in SOZLUK.items():
        if desen in SOZLUK_TAKMA_ADLAR:
            continue
        tr_kelime = desen.replace(r'\b', '').strip('"').strip("'")
        py_kelime = python_karsiligi.strip('"').strip("'")
        # Noktalı hedefler (örn. "mouse.x", "tf.constant") burada elenir.
        # Bunlar bağlamsız tek kelimeye indirgenirse yanlış/parçalı ters
        # çeviri üretir (örn. "mouse.x" -> "fare_x" değil "mouse.fare_x"
        # gibi bir şeye karışabilir); noktalı API'ler modül/nesne tablolarına
        # aittir, converter.py bunları ayrıca ters çevirir.
        if '.' in py_kelime:
            continue
        if tr_kelime and py_kelime and ' ' not in tr_kelime and len(py_kelime) > 1:
            ters_sozluk.setdefault(py_kelime, tr_kelime)
    # Öncelikli karşılıkları zorla. Yalnızca Türkçe kelime sözlükte gerçekten
    # bu Python adına çevriliyorsa uygulanır; aksi halde (kelime yeniden
    # adlandırıldıysa vb.) gidiş-dönüş çeviri sessizce bozulurdu.
    # Eski (takma ad olmuş) bir kelime de seçilmez.
    for py, tr in TERS_SOZLUK_ONCELIK.items():
        desen = rf"\b{tr}\b"
        if (py in ters_sozluk and desen not in SOZLUK_TAKMA_ADLAR
                and SOZLUK.get(desen, "").strip() == py):
            ters_sozluk[py] = tr
    return ters_sozluk

TERS_SOZLUK = _ters_sozluk_olustur()

def _sozluk_kelime(desen):
    return desen.replace(r"\b", "").strip().strip('"').strip("'")

_PY_KEYWORDS = set(_keyword.kwlist) | {"True", "False", "None"}

_BLOCK_VALUES = {
    "def", "class", "while", "if", "elif", "else",
    "try", "except", "finally"
}

_keyword_words = set()
_builtin_words = set()
_block_words = set()

for _desen, _hedef in SOZLUK.items():
    _kelime = _sozluk_kelime(_desen)
    _hedef = _hedef.strip()

    if not _kelime or " " in _kelime or "." in _kelime:
        continue

    if _hedef in _PY_KEYWORDS:
        _keyword_words.add(_kelime)
    else:
        _builtin_words.add(_kelime)

    if _hedef in _BLOCK_VALUES:
        _block_words.add(_kelime)

_block_words.update([
    "fonksiyon", "sınıf", "döngü", "için", "eğer", "değilse_eğer", "değilse",
    "dene", "hata_yakala", "sonunda"
])

def _regex_compile(words):
    words = sorted(words, key=len, reverse=True)
    if not words:
        return re.compile(r"(?!)")
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")

TURKOD_KEYWORD_RE = _regex_compile(_keyword_words)
TURKOD_BUILTIN_RE = _regex_compile(_builtin_words)

_block_words = sorted(_block_words, key=len, reverse=True)

TURKOD_BLOK_RE = re.compile(
    r"^(?:" + "|".join(re.escape(w) for w in _block_words) + r")\b",
    re.MULTILINE
)

def _sozlukten_python_kelime(py, fallback):
    for _desen, _hedef in SOZLUK.items():
        if _hedef.strip() == py:
            return _sozluk_kelime(_desen)
    return fallback

FONKSIYON_KW = _sozlukten_python_kelime("def", "fonksiyon")
SINIF_KW = _sozlukten_python_kelime("class", "sınıf")

def sozlukten_kelime_listesi():
    """SOZLUK'ten temiz Türkçe kelime listesi çıkar - önbellekli"""
    
    # Önbellek, sözlüğün o anki içeriğine bağlı bir imzayla doğrulanır.
    # Eskiden yalnızca dosya tarihine bakılıyordu: tarihi korunarak kurulan
    # yeni bir sürüm eski kelime listesini, bir kez başarısız yüklenen sözlük
    # ise sonsuza dek BOŞ listeyi kullanmaya devam ediyordu.
    try:
        boyut = os.path.getsize(SOZLUK_TXT_YOLU)
    except OSError:
        boyut = -1
    imza = f"{len(SOZLUK)}|{len(SOZLUK_TAKMA_ADLAR)}|{boyut}"
    if os.path.exists(CACHE_JSON_YOLU):
        try:
            with open(CACHE_JSON_YOLU, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if (isinstance(veri, dict) and veri.get("imza") == imza
                    and veri.get("kelimeler")):
                return veri["kelimeler"]
        except Exception:
            pass
    
    # Cache yoksa veya geçersizse oluştur
    kelimeler = set()
    for desen in SOZLUK.keys():
        if desen in SOZLUK_TAKMA_ADLAR:
            continue
        if '.' in desen:
            continue
        kelime = desen.replace(r'\b', '').strip()
        kelime = kelime.strip('"').strip("'")
        if kelime and ' ' not in kelime and '.' not in kelime:
            kelimeler.add(kelime)
    
    sonuc = sorted(list(kelimeler))

    if sonuc:  # boş liste (sözlük yüklenemedi) asla önbelleğe yazılmaz
        try:
            # Klasör yoksa oluştur (calisma_yolu garanti değilse)
            os.makedirs(os.path.dirname(CACHE_JSON_YOLU), exist_ok=True)
            with open(CACHE_JSON_YOLU, "w", encoding="utf-8") as f:
                json.dump({"imza": imza, "kelimeler": sonuc}, f, ensure_ascii=False)
        except Exception:
            pass
    
    return sonuc

TURKCE_KELIMELER = sozlukten_kelime_listesi()

print(f"[TurKod] {len(TURKCE_KELIMELER)} kelime otomatik tamamlama icin yuklendi")
# === KULLANICI TANIMLARI (değişken/fonksiyon adları) ===
KIMLIK = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*"

# Kullanıcı bu adları kendi değişkeni olarak tanımlasa bile çevrilmeleri gerekir:
# dil sözdizimine ait anahtar kelimeler ve dunder karşılıkları (başlat_özel -> __init__).
KORUNMAYAN_KELIMELER = {
    _sozluk_kelime(_desen)
    for _desen, _hedef in SOZLUK.items()
    if _hedef.strip() in _PY_KEYWORDS or _hedef.strip().startswith("__")
}

# Framework'lerin özel metot adları kullanıcı tanımı olarak korunmamalı;
# aksi halde sözlük çevirisi uygulanmaz ve Ursina/Pygame bu metotları çağırırken bulamaz.
_OZEL_METOT_HEDEFLERI = {
    "update", "input", "awake", "on_enable", "on_disable",
    "on_destroy", "run", "quit",
}
KORUNMAYAN_KELIMELER.update({
    _sozluk_kelime(_desen)
    for _desen, _hedef in SOZLUK.items()
    if _hedef.strip() in _OZEL_METOT_HEDEFLERI
})


def _parantez_derinligi_haritasi(kod):
    """Her karakter konumu için ( [ { derinliğini döner (string/yorum kabaca atlanır).

    `^\\s*isim\\s*=` gibi satır-başı regex'leri, çok satırlı bir çağrının
    içinde (derinlik > 0) tek başına duran bir kwarg satırını ("dolgu=...,")
    gerçek bir üst düzey atamayla ayırt edemez. Bu harita, eşleşmenin
    derinlik 0'da olup olmadığını kontrol etmek için kullanılır.
    """
    derinlikler = [0] * (len(kod) + 1)
    derinlik = 0
    tirnak = None
    i = 0
    n = len(kod)
    while i < n:
        c = kod[i]
        derinlikler[i] = derinlik
        if tirnak:
            if c == '\\':
                i += 2
                continue
            if c == tirnak:
                tirnak = None
        elif c in ('"', "'"):
            tirnak = c
        elif c == '#':
            # Yorumun geri kalanını atla (derinlik değişmez, satır sonuna kadar).
            while i < n and kod[i] != '\n':
                derinlikler[i] = derinlik
                i += 1
            continue
        elif c in '([{':
            derinlik += 1
        elif c in ')]}':
            derinlik = max(0, derinlik - 1)
        i += 1
    derinlikler[n] = derinlik
    return derinlikler


def _ust_duzey_eslesmeler(desen, kod, flags=0):
    """re.findall ile aynı, ama yalnızca derinlik 0'daki eşleşmeleri döner."""
    derinlikler = _parantez_derinligi_haritasi(kod)
    sonuc = []
    for m in re.finditer(desen, kod, flags):
        if derinlikler[m.start()] == 0:
            sonuc.append(m.group(1) if m.groups() else m.group(0))
    return sonuc


def yalniz_oznitelik_adlari(kod):
    """Yalnızca kendisi.X / self.X özniteliği olarak tanımlanan adlar.
    Bu adlar çıplak kullanımda (uzunluk(...)) korunmamalı: eskiden
    'kendisi.uzunluk = 3' dosyadaki tüm 'uzunluk(...)' çağrılarını
    çeviriden muaf tutuyor, çalışma zamanında NameError veriyordu."""
    oz = set(re.findall(rf'\b(?:self|kendisi)\.({KIMLIK})\b', kod))
    if not oz:
        return set()
    return oz - kullanici_tanimlari(kod, oznitelikler=False)


def kullanici_tanimlari(kod, oznitelikler=True):
    """Kodda kullanıcının tanımladığı tüm isimleri döndürür.
    Çevirici ve yerel düzeltme bu isimlere dokunmaz."""
    tanimlar = set()
    # fonksiyon / sınıf adları
    tanimlar.update(re.findall(
        rf'\b{re.escape(FONKSIYON_KW)}\s+({KIMLIK})\s*\(', kod))
    # "sınıf A:" ve kalıtımlı "sınıf A(Temel):" biçimleri
    tanimlar.update(re.findall(
        rf'\b{re.escape(SINIF_KW)}\s+({KIMLIK})\s*[:(]', kod))
    # atama hedefleri: =, +=, -=, *=, /=, //=, %=, **=
    # NOT: Yalnızca parantez/köşeli parantez/süslü parantez derinliği 0 olan
    # eşleşmeler kabul edilir; aksi halde çok satırlı bir fonksiyon çağrısı
    # içindeki "dolgu=(0.8, 0.9, 1)," gibi bir kwarg satırı, üst düzey bir
    # değişken ataması sanılıp yanlışlıkla çeviriden muaf tutulurdu.
    tanimlar.update(_ust_duzey_eslesmeler(
        rf'^[ \t]*({KIMLIK})\s*(?:\+=|-=|\*=|/=|//=|%=|\*\*=|=(?!=))',
        kod, re.MULTILINE))
    # çoklu atama: a, b = ...
    for grup in _ust_duzey_eslesmeler(
            rf'^[ \t]*((?:\*?{KIMLIK}\s*,\s*)+\*?{KIMLIK})\s*=(?!=)', kod, re.MULTILINE):
        tanimlar.update(p.strip().lstrip('*') for p in grup.split(',') if p.strip())
    # döngü değişkenleri: için i aralık(...), için x, y içinde ..., döngü i aralık(...)
    # Virgülle ayrılmış tüm değişkenler yakalanır; 'döngü' kalıbı da kapsanır.
    # 'döngü doğru:' gibi kalıplar sonra 'içinde'/'aralık(' gelmediği için eşleşmez.
    for grup in re.findall(
            rf'\b(?:için|döngü)\s+((?:{KIMLIK}\s*,\s*)*{KIMLIK})\s+(?:içinde|aralık\s*\()',
            kod):
        tanimlar.update(p.strip() for p in grup.split(',') if p.strip())
    # Liste üreteçleri: [x için x içinde liste] veya [x için x içinde liste eğer ...]
    tanimlar.update(re.findall(rf'\[[^\[\]]*?[^\s\[\]]\s+için\s+({KIMLIK})\s+içinde', kod))
    # takma adlar: içe_aktar X olarak Y, ile X olarak Y
    tanimlar.update(re.findall(rf'\bolarak\s+({KIMLIK})', kod))
    # nesne öznitelikleri
    if oznitelikler:
        tanimlar.update(re.findall(rf'\bself\.({KIMLIK})\b', kod))
        tanimlar.update(re.findall(rf'\bkendisi\.({KIMLIK})\b', kod))
    # fonksiyon parametreleri
    for grup in re.findall(
            rf'\b{re.escape(FONKSIYON_KW)}\s+{KIMLIK}\s*\(([^)]*)\)', kod):
        for p in grup.split(','):
            # "*argümanlar", "**sözlük", "x: int = 3" biçimleri de desteklenir.
            p = p.strip().split('=')[0].split(':')[0].strip().lstrip('*').strip()
            if p and p not in ("self", "kendisi"):
                tanimlar.add(p)
    # with ... as ... kalıbı
    tanimlar.update(re.findall(rf'\bile\b\s+.*?\s+olarak\s+({KIMLIK})\b', kod))
    # except ... as ... kalıbı
    tanimlar.update(re.findall(rf'\bhata_yakala\b\s+.*?\s+olarak\s+({KIMLIK})\b', kod))
    return tanimlar - KORUNMAYAN_KELIMELER
