"""TürKod Akıllı Düzeltme Motoru.

Dışarıdan hiçbir yapay zekâ servisine bağlanmaz; tamamen yerel çalışır. Ama
bir yapay zekâ asistanı gibi davranır: kodu okur, sorunları teşhis eder,
her sorun için birden fazla olası düzeltme üretir, bunları kodu gerçekten
derleyip / çalıştırarak sınar, en iyi sonucu seçer ve yaptığı her şeyi
gerekçesi ve güven puanıyla birlikte açıklar.

Aşamalar
--------
1. Okuma        : kod istatistikleri, yapı (fonksiyon / sınıf / değişken).
2. Ön temizlik  : karışık sekme/boşluk, "değilse eğer" gibi ayrık yazılmış
                  anahtar kelimeler, sözlüğe dayalı yazım hataları.
3. Sözdizimi    : hata satırı için aday düzeltmeler üretilir (iki nokta,
                  girinti, parantez, tırnak, virgül, operatör, eksik
                  parantezli çağrı, akıllı tırnak ...). Her aday derlenerek
                  puanlanır; hatayı ortadan kaldıran ya da en ileri taşıyan
                  aday seçilir (küçük bir arama).
4. Anlam        : girdi_al() ile okunan metnin sayı gibi kullanılması gibi
                  çalışma hatası vermeyen ama yanlış sonuç üreten durumlar.
5. Çalışma      : kod güvenli kipte (girdi beklemeden, uyumadan) çalıştırılır;
                  hata türüne göre adaylar üretilir (tanımsız ad, eksik
                  içe aktarma, metin + sayı birleştirme, yanlış metot adı,
                  eksik 'kendisi', 'küresel' eksikliği ...). Her aday yeniden
                  çalıştırılarak doğrulanır; işe yaramayan geri alınır.
6. İnceleme     : otomatik düzeltilmeyen ama dikkat edilmesi gereken
                  durumlar (sonsuz döngü riski, ulaşılamayan kod, yanlış
                  argüman sayısı, kullanılmayan değişken ...).
7. Rapor        : düzeltmeler, öneriler, kod sağlık puanı, son doğrulama.

Sonuç sözlüğü eski ``gelismis_duzelt`` biçimiyle uyumludur (kod, diff,
degisiklikler, son_mesaj, dogrulama) ve ek olarak ``rapor`` alanı içerir.
"""
import ast
import builtins
import difflib
import hashlib
import re
import subprocess
import time

try:
    from .converter import MODUL_CEVIRILERI, turkce_kodu_donustur
    from .dictionary import SOZLUK, TERS_SOZLUK, _block_words, _keyword_words, kullanici_tanimlari
except ImportError:
    from converter import MODUL_CEVIRILERI, turkce_kodu_donustur
    from dictionary import SOZLUK, TERS_SOZLUK, _block_words, _keyword_words, kullanici_tanimlari


ID = r"[^\W\d]\w*"
_ID_RE = re.compile(ID)
_METIN_RE = re.compile(
    r'[rRbBfFuU]{0,2}"""[\s\S]*?"""|[rRbBfFuU]{0,2}\'\'\'[\s\S]*?\'\'\''
    r'|[rRbBfFuU]{0,2}"(?:[^"\\\n]|\\.)*"|[rRbBfFuU]{0,2}\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*')
_ACAN = {"(": ")", "[": "]", "{": "}"}
_KAPAYAN = {v: k for k, v in _ACAN.items()}

# Kod çalıştırmada girdi beklenmesini ve uyumayı engelleyen tek satırlık ön ek.
_KONTROL_ON_EKI = (
    "import builtins as _tk_b, time as _tk_t; "
    "_tk_b.input = lambda *a, **k: '1'; "
    "_tk_t.sleep = lambda *a, **k: None"
)


def _tr(py_ad, varsayilan):
    """Python adının TürKod karşılığı (ör. 'int' -> 'tamsayı')."""
    deger = TERS_SOZLUK.get(py_ad)
    return deger if isinstance(deger, str) and deger else varsayilan


def _normalize(metin):
    return metin.translate(str.maketrans({
        "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    })).lower()


def maskele(metin):
    """Metin içeriklerini \\x01 ile, yorumları boşlukla maskeler (uzunluk ve
    satır yapısı korunur). Böylece kalıp aramaları metinlerin / yorumların
    içine takılmaz; tırnaklar yerinde kaldığı için metin değerleri yine de
    tanınabilir."""
    def degistir(m):
        s = m.group(0)
        if s.startswith("#"):
            return " " * len(s)
        bas_m = re.match(r"[rRbBfFuU]{0,2}(\"\"\"|'''|\"|')", s)
        bas = bas_m.end()
        son = len(s) - len(bas_m.group(1))
        ic = "".join("\n" if ch == "\n" else "\x01" for ch in s[bas:son])
        return s[:bas] + ic + s[son:]
    return _METIN_RE.sub(degistir, metin)


def _girinti(satir):
    return len(satir) - len(satir.lstrip(" \t"))


def _eslesen_kapanis(maskeli, ac_konum):
    """maskeli[ac_konum] açılış parantezinin kapanış konumu (yoksa -1)."""
    derinlik = 0
    for i in range(ac_konum, len(maskeli)):
        ch = maskeli[i]
        if ch in _ACAN:
            derinlik += 1
        elif ch in _KAPAYAN:
            derinlik -= 1
            if derinlik == 0:
                return i
    return -1


class Bulgu:
    """Bir düzeltme ya da öneri."""

    __slots__ = ("satir", "baslik", "aciklama", "guven", "kategori", "seviye", "oneri")

    def __init__(self, satir, baslik, aciklama="", guven=0.9, kategori="genel",
                 seviye="bilgi", oneri=""):
        self.satir = satir
        self.baslik = baslik
        self.aciklama = aciklama
        self.guven = guven
        self.kategori = kategori
        self.seviye = seviye
        self.oneri = oneri

    def sozluk(self):
        return {
            "satir": self.satir,
            "baslik": self.baslik,
            "aciklama": self.aciklama,
            "guven": int(round(self.guven * 100)),
            "kategori": self.kategori,
            "seviye": self.seviye,
            "oneri": self.oneri,
        }

    def metin(self):
        onek = f"Satır {self.satir}: " if self.satir else ""
        return f"• {onek}{self.baslik}"


class AkilliDuzeltici:
    """IDECore'un yardımcılarını kullanan akıllı düzeltme motoru."""

    MAKS_SOZDIZIMI = 250
    MAKS_ADAY_CALISTIRMA = 5

    # Ayrık yazıldığında (ör. "değilse eğer") birleştirilen kelimeler. Bu
    # biçimler hiçbir zaman geçerli kod olmadığından birleştirme güvenlidir.
    _EK_BIRLESIK = (
        "girdi_al", "sona_ekle", "büyük_harf", "küçük_harf", "nesne_mi",
        "isimsiz", "başlat_özel",
    )

    _CAGRILABILIR_KOMUTLAR = ("yazdır", "yazdir")

    def __init__(self, core, progress_callback=None, calistir=True):
        self.core = core
        self.progress_callback = progress_callback
        self.duzeltmeler = []
        self.uyarilar = []
        self.dusunceler = []
        self._uyari_anahtarlari = set()
        self._calisma_onbellek = {}
        self.calistirma_sayisi = 0
        self.zaman_asimi = max(1, core._sayi_ayar("duzeltme_zaman_asimi", 5))
        self.maks_calisma = max(1, core._sayi_ayar("duzeltme_maks_dongu", 12))
        aralik = core._sayi_ayar("duzeltme_mesaj_araligi", 100)
        self._mesaj_bekleme = max(0, min(aralik, 250)) / 1000.0
        self.python_exe, self.python_hata = core._python_exe_bul()
        if not calistir:
            # Riskli kod (dosya silme, ağ, ...) ve kullanıcı izin vermedi:
            # tüm çalışma testleri atlanır, yalnızca statik düzeltme yapılır.
            self.python_exe = None
            self.python_hata = "Güvenlik nedeniyle kod çalıştırılmadı."

    # ------------------------------------------------------------------
    # İletişim
    # ------------------------------------------------------------------
    def dusun(self, metin, bekle=True):
        """Kullanıcıya 'düşünce akışı' iletir."""
        self.dusunceler.append(metin)
        if self.progress_callback:
            if bekle and self._mesaj_bekleme:
                time.sleep(self._mesaj_bekleme)
            self.core._guvenli_callback(self.progress_callback, metin)

    def _duzeltme_ekle(self, bulgu):
        self.duzeltmeler.append(bulgu)
        guven = int(round(bulgu.guven * 100))
        self.dusun(f"🔧 {bulgu.metin()[2:]}  (güven %{guven})")

    def _uyari_ekle(self, satir, mesaj, oneri="", seviye="uyari", kategori="inceleme"):
        anahtar = (satir, mesaj)
        if anahtar in self._uyari_anahtarlari:
            return
        self._uyari_anahtarlari.add(anahtar)
        self.uyarilar.append(Bulgu(satir, mesaj, oneri=oneri, seviye=seviye,
                                   kategori=kategori, guven=1.0))

    # ------------------------------------------------------------------
    # Çeviri / derleme / çalıştırma
    # ------------------------------------------------------------------
    @staticmethod
    def _hash(kod):
        return hashlib.sha256(kod.encode("utf-8")).hexdigest()

    @staticmethod
    def _cevir(kod):
        try:
            return turkce_kodu_donustur(kod)
        except Exception:
            return None

    def _sozdizimi_durumu(self, kod):
        """None: sorunsuz; değilse {'satir', 'mesaj', 'tip'}."""
        py = self._cevir(kod)
        if py is None:
            return {"satir": 1, "mesaj": "kod Python'a çevrilemedi", "tip": "CeviriHatasi"}
        try:
            ast.parse(py)
        except SyntaxError as e:
            return {"satir": max(1, e.lineno or 1), "mesaj": str(e.msg or ""),
                    "tip": type(e).__name__}
        except (ValueError, RecursionError) as e:
            return {"satir": 1, "mesaj": str(e), "tip": type(e).__name__}
        return None

    @staticmethod
    def _degisen_satirlar(eski, yeni):
        """yeni koddaki, eskisine göre değişmiş / eklenmiş satır numaraları."""
        a, b = eski.split("\n"), yeni.split("\n")
        degisen = set()
        for etiket, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if etiket in ("replace", "insert"):
                degisen.update(range(j1 + 1, j2 + 1))
            elif etiket == "delete":
                degisen.add(j1 + 1)
        return degisen

    def _degerlendir(self, eski_kod, yeni_kod, eski_durum=False):
        """Bir değişikliğin sözdizimi açısından değerini ölçer.

        Python bir dosyadaki hataların yalnızca ilkini (ve belirteç hatalarını
        diğerlerinden önce) bildirdiği için "hata satırı ilerledi mi" ölçütü
        yanıltıcıdır: bir hatayı düzeltmek daha yukarıdaki başka bir hatayı
        görünür kılabilir. Ölçüt: eski hata ortadan kalktı mı ve değişikliğin
        DOKUNDUĞU satırlarda yeni bir hata doğdu mu?

        Döner: None (reddet) ya da büyük olanı daha iyi bir puan.
        """
        if eski_durum is False:
            eski_durum = self._sozdizimi_durumu(eski_kod)
        yeni_durum = self._sozdizimi_durumu(yeni_kod)
        if yeni_durum is None:
            return (3, 0)
        if yeni_durum["tip"] == "CeviriHatasi":
            return None
        if eski_durum is None:
            return None  # derlenen kodu bozdu
        if eski_durum["tip"] == "CeviriHatasi":
            return (2, 0)
        degisen = self._degisen_satirlar(eski_kod, yeni_kod)
        kayma = yeni_kod.count("\n") - eski_kod.count("\n")
        ayni_hata = (yeni_durum["mesaj"] == eski_durum["mesaj"] and
                     yeni_durum["satir"] in (eski_durum["satir"], eski_durum["satir"] + kayma))
        if ayni_hata:
            return None
        if yeni_durum["satir"] in degisen:
            # Düzeltilen satırda hâlâ hata var: yalnızca aynı satırda farklı
            # bir hataya geçildiyse (adım adım ilerleme) zayıf bir ilerlemedir.
            if yeni_durum["satir"] == eski_durum["satir"]:
                return (1, 0)
            return None
        return (2, 0)

    def _kabul_edilebilir(self, eski_kod, yeni_kod):
        """Ön temizlik dönüşümleri için: kodu kötüleştirmiyor mu?"""
        eski_durum = self._sozdizimi_durumu(eski_kod)
        if eski_durum is None:
            return self._sozdizimi_durumu(yeni_kod) is None
        yeni_durum = self._sozdizimi_durumu(yeni_kod)
        if yeni_durum is None:
            return True
        if yeni_durum["tip"] == "CeviriHatasi" and eski_durum["tip"] != "CeviriHatasi":
            return False
        return yeni_durum["satir"] not in self._degisen_satirlar(eski_kod, yeni_kod) \
            or (yeni_durum["satir"] == eski_durum["satir"])

    def _calistir(self, kod):
        """Kodu güvenli kipte çalıştırır; sonucu önbelleğe alır.

        durum: ok | hata | zaman_asimi | sozdizimi | ceviri | atlandi
        """
        anahtar = self._hash(kod)
        if anahtar in self._calisma_onbellek:
            return self._calisma_onbellek[anahtar]

        py = self._cevir(kod)
        if py is None:
            sonuc = {"durum": "ceviri"}
        else:
            try:
                agac = ast.parse(py)
            except SyntaxError as e:
                sonuc = {"durum": "sozdizimi", "satir": e.lineno or 1, "mesaj": str(e.msg)}
            else:
                if self._arayuz_programi_mi(agac):
                    # Pencere açan programlar güvenli kipte hep zaman aşımına
                    # uğrar (yanlış "sonsuz döngü" uyarısı) ve ekranda pencere
                    # açar; bunlarda çalışma testi yapılmaz.
                    sonuc = {"durum": "atlandi", "arayuz": True}
                else:
                    sonuc = self._python_calistir(py)
        self._calisma_onbellek[anahtar] = sonuc
        return sonuc

    _ARAYUZ_MODULLERI = {
        "turtle", "tkinter", "pygame", "ursina", "kivy", "PyQt5", "PyQt6",
        "PySide2", "PySide6", "wx", "arcade", "pyglet", "customtkinter",
        "matplotlib", "cv2", "pyautogui",
    }

    @classmethod
    def _arayuz_programi_mi(cls, agac):
        for d in ast.walk(agac):
            if isinstance(d, ast.Import):
                adlar = [a.name for a in d.names]
            elif isinstance(d, ast.ImportFrom) and d.module:
                adlar = [d.module]
            else:
                continue
            if any(ad.split(".")[0] in cls._ARAYUZ_MODULLERI for ad in adlar):
                return True
        return False

    def _python_calistir(self, py):
        if not self.python_exe:
            return {"durum": "atlandi"}
        tam = _KONTROL_ON_EKI + "\n" + py
        self.calistirma_sayisi += 1
        try:
            sonuc, temp_path = self.core._kontrol_calistir(self.python_exe, tam, self.zaman_asimi)
        except subprocess.TimeoutExpired:
            return {"durum": "zaman_asimi"}
        except Exception as e:
            return {"durum": "atlandi", "mesaj": str(e)}

        if sonuc.returncode == 0:
            return {"durum": "ok"}
        stderr = sonuc.stderr or ""
        son = ""
        for satir in reversed(stderr.splitlines()):
            if satir.strip():
                son = satir.strip()
                break
        m = re.match(r"^([\w.]+)(?::\s*(.*))?$", son)
        tip = m.group(1).split(".")[-1] if m else "Hata"
        mesaj = (m.group(2) or "") if m else son
        if "Error" not in tip and "Exception" not in tip and "Exit" not in tip:
            # Traceback'siz çıkış (ör. çık(1)).
            return {"durum": "ok", "cikis": sonuc.returncode}
        satir = self.core._hata_satiri(stderr, temp_path, 1)
        return {"durum": "hata", "tip": tip, "mesaj": mesaj, "satir": satir,
                "son": son, "stderr": stderr}

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _satirlar(kod):
        return kod.split("\n")

    @staticmethod
    def _satir_degistir(kod, satir_no, yeni):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        if satirlar[satir_no - 1] == yeni:
            return None
        satirlar[satir_no - 1] = yeni
        return "\n".join(satirlar)

    def _girinti_birimi(self, kod):
        return self.core._girinti_birimi(kod.split("\n"))

    def _ice_aktarma_ekle(self, kod, modul):
        """'içe_aktar modul' satırını mevcut içe aktarmaların altına ekler."""
        satirlar = kod.split("\n")
        if re.search(rf"^\s*(?:içe_aktar|ice_aktar)\s+{re.escape(modul)}\b", kod, re.M):
            return None
        yer = 0
        for i, s in enumerate(satirlar):
            temiz = s.strip()
            if re.match(r"^(?:içe_aktar|ice_aktar|den|from|import)\b", temiz) and _girinti(s) == 0:
                yer = i + 1
            elif temiz and not temiz.startswith("#") and yer:
                break
        satirlar.insert(yer, f"{_tr('import', 'içe_aktar')} {modul}")
        return "\n".join(satirlar)

    @staticmethod
    def _modul_var_mi(modul_tr):
        """TürKod modül adının Python karşılığı kurulu mu (yaklaşık)."""
        import importlib.util
        py = MODUL_CEVIRILERI.get(modul_tr, modul_tr)
        try:
            return importlib.util.find_spec(str(py).split(".")[0]) is not None
        except (ImportError, ValueError):
            return False

    def _sozluk(self):
        return self.core._sozluk_duz_harita()

    def _tanimlar(self, kod):
        try:
            return set(kullanici_tanimlari(kod))
        except Exception:
            return set()

    @staticmethod
    def _py_agaci(kod):
        try:
            py = turkce_kodu_donustur(kod)
            return ast.parse(py), py
        except Exception:
            return None, None

    # ==================================================================
    # ANA AKIŞ
    # ==================================================================
    def calistir(self, kod):
        baslangic = time.time()
        orijinal = (kod or "").replace("\r\n", "\n").replace("\r", "\n")
        if not orijinal.strip():
            return {"ok": False, "hata": "Düzeltilecek kod bulunamadı."}
        kod = orijinal

        self._okuma(kod)
        kod = self._on_temizlik(kod)
        kod = self._sozdizimi_asamasi(kod)
        sozdizimi_temiz = self._sozdizimi_durumu(kod) is None
        if sozdizimi_temiz:
            kod = self._anlam_asamasi(kod)
            kod = self._calisma_asamasi(kod)
            self._inceleme_asamasi(kod)
        son = self._son_dogrulama(kod)
        return self._rapor(orijinal, kod, son, time.time() - baslangic)

    # ------------------------------------------------------------------
    # 1. Okuma
    # ------------------------------------------------------------------
    def _okuma(self, kod):
        satirlar = kod.split("\n")
        dolu = sum(1 for s in satirlar if s.strip() and not s.strip().startswith("#"))
        fonk = len(re.findall(r"^\s*fonksiyon\s+" + ID, kod, re.M))
        sinif = len(re.findall(r"^\s*(?:sınıf|sinif)\s+" + ID, kod, re.M))
        parcalar = [f"{len(satirlar)} satır ({dolu} kod satırı)"]
        if fonk:
            parcalar.append(f"{fonk} fonksiyon")
        if sinif:
            parcalar.append(f"{sinif} sınıf")
        self.dusun("🧠 Kodu okuyorum: " + ", ".join(parcalar) + ".")

    # ------------------------------------------------------------------
    # 2. Ön temizlik
    # ------------------------------------------------------------------
    def _on_temizlik(self, kod):
        self.dusun("🔍 Yazım ve biçim sorunlarını tarıyorum…")

        # a) Karışık sekme / boşluk girintisi.
        satirlar = kod.split("\n")
        if any(s[:1] == " " for s in satirlar) and any(s[:1] == "\t" for s in satirlar):
            kod = "\n".join(
                s[:_girinti(s)].expandtabs(4) + s[_girinti(s):] for s in satirlar)
            self._duzeltme_ekle(Bulgu(
                None, "Karışık sekme/boşluk girintisi boşluğa çevrildi",
                "Aynı dosyada hem sekme hem boşlukla girinti yapılması Python'da "
                "'inconsistent use of tabs' hatasına yol açar.",
                0.97, "girinti"))

        # b) Görünmez / yanlış karakterler (kopyala-yapıştır kaynaklı).
        kod = self._garip_karakterler(kod)

        # c) Ayrık yazılmış anahtar kelimeler ("değilse eğer" -> "değilse_eğer").
        kod = self._ayrik_kelimeler(kod)

        # d) Sözlüğe göre yazım hataları ('yazdir' -> 'yazdır', 'eger' -> 'eğer').
        try:
            _, ham_degisiklikler = self.core._kodu_yerel_duzelt(kod)
        except Exception:
            ham_degisiklikler = set()
        degisiklikler = self._yazim_filtrele(kod, ham_degisiklikler)
        yeni = kod
        if degisiklikler:
            satirlar = yeni.split("\n")
            for eski, dogru in degisiklikler:
                satirlar = [ad_degistir(s, eski, dogru) for s in satirlar]
            yeni = "\n".join(satirlar)
        if degisiklikler and yeni != kod and self._kabul_edilebilir(kod, yeni):
            tanimlar = self._kod_tanimlari(kod)
            maskeli = maskele(kod).split("\n")
            for eski, dogru in sorted(degisiklikler):
                satir = None
                for i, s in enumerate(maskeli, 1):
                    if re.search(rf"(?<![\w]){re.escape(eski)}(?![\w])", s):
                        satir = i
                        break
                neden = (f"'{eski}' tanımlı değil; koddaki en yakın ad '{dogru}'."
                         if dogru in tanimlar else
                         f"'{eski}' TürKod sözlüğünde yok; en yakın komut '{dogru}'.")
                self._duzeltme_ekle(Bulgu(
                    satir, f"Yazım: '{eski}' → '{dogru}'", neden, 0.85, "yazim"))
            kod = yeni
        return kod

    def _kod_tanimlari(self, kod):
        """Kullanıcının tanımladığı adlar (atama, fonksiyon, sınıf, parametre,
        döngü değişkeni, takma ad). Tanım satırı bozuk olsa bile (ör.
        'fonksiyon selam:') bulunur."""
        tanimlar = set(self._tanimlar(kod))
        maskeli = maskele(kod)
        desenler = (
            rf"^\s*({ID})\s*(?:[-+*/%]|//|\*\*)?=(?!=)",
            rf"\b(?:fonksiyon|sınıf|sinif)\s+({ID})",
            rf"\b(?:için|icin)\s+({ID})",
            rf"\bolarak\s+({ID})",
        )
        for d in desenler:
            tanimlar.update(re.findall(d, maskeli, re.M))
        for m in re.finditer(rf"\bfonksiyon\s+{ID}\s*\(([^)\n]*)\)?", maskeli):
            tanimlar.update(re.findall(ID, m.group(1)))
        return tanimlar

    def _yazim_filtrele(self, kod, degisiklikler):
        """Sözlük tabanlı yazım düzeltmelerini akıllıca süzer:
        * Kullanıcının kendi tanımladığı adlara dokunulmaz.
        * Yanlış yazılan ad, kullanıcının bir değişkenine daha yakınsa sözlük
          kelimesi yerine o değişken seçilir ('sayc' -> 'sayac', 'Sayaç' değil).
        """
        if not degisiklikler:
            return []
        tanimlar = self._kod_tanimlari(kod)
        sonuc = []
        for eski, dogru in sorted(degisiklikler):
            if eski in tanimlar:
                continue
            yakin = self.core._en_yakin_eslesme(eski, sorted(tanimlar), cutoff=0.75)
            if yakin and yakin[0] != eski:
                oran_kullanici = difflib.SequenceMatcher(
                    None, _normalize(eski), _normalize(yakin[0])).ratio()
                oran_sozluk = difflib.SequenceMatcher(
                    None, _normalize(eski), _normalize(dogru)).ratio()
                if oran_kullanici >= oran_sozluk:
                    dogru = yakin[0]
            if dogru != eski:
                sonuc.append((eski, dogru))
        return sonuc

    _GARIP = {
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
        "‘": "'", "’": "'", "‚": "'",
        " ": " ", " ": " ", " ": " ", "​": "", "﻿": "",
        "−": "-", "–": "-", "×": "*", "÷": "/",
    }

    def _garip_karakterler(self, kod):
        maskeli = maskele(kod)
        cikti = []
        degisen_satirlar = set()
        satir = 1
        for ch_m, ch in zip(maskeli, kod):
            if ch == "\n":
                satir += 1
            # Tırnaklar maskede de kalır; metin İÇİNDEKİ karakterlere dokunma.
            if ch_m != "\x01" and ch in self._GARIP:
                cikti.append(self._GARIP[ch])
                degisen_satirlar.add(satir)
            else:
                cikti.append(ch)
        if not degisen_satirlar:
            return kod
        yeni = "".join(cikti)
        # Bu karakterler metin dışında hiçbir zaman geçerli olmadığından
        # dönüşüm her zaman güvenlidir; yalnızca çeviriyi bozmadığı denetlenir.
        if self._cevir(yeni) is None and self._cevir(kod) is not None:
            return kod
        ilk = min(degisen_satirlar)
        ek = f" (+{len(degisen_satirlar) - 1} satır daha)" if len(degisen_satirlar) > 1 else ""
        self._duzeltme_ekle(Bulgu(
            ilk, f"Akıllı tırnak / görünmez karakter düzeltildi{ek}",
            "Kelime işlemciden kopyalanan “ ” ‘ ’ tırnakları, bölünmez boşluk ve "
            "benzeri karakterler Python'da 'invalid character' hatası verir.",
            0.95, "karakter"))
        return yeni

    def _ayrik_kelimeler(self, kod):
        kelimeler = set()
        for k in list(_keyword_words) + list(_block_words) + list(self._EK_BIRLESIK):
            if "_" in k and not k.startswith("_") and k.count("_") <= 2:
                kelimeler.add(k)
        if not kelimeler:
            return kod
        maskeli = maskele(kod)
        degisimler = []
        for k in sorted(kelimeler, key=len, reverse=True):
            parca = [re.escape(p) for p in k.split("_")]
            desen = r"(?<![\w])" + r"[ \t]+".join(parca) + r"(?![\w])"
            for m in re.finditer(desen, maskeli):
                if any(m.start() < b and a < m.end() for a, b, _ in degisimler):
                    continue
                degisimler.append((m.start(), m.end(), k))
        if not degisimler:
            return kod
        yeni = kod
        for a, b, k in sorted(degisimler, reverse=True):
            yeni = yeni[:a] + k + yeni[b:]
        if not self._kabul_edilebilir(kod, yeni):
            return kod
        for a, _, k in sorted(degisimler):
            satir = kod.count("\n", 0, a) + 1
            self._duzeltme_ekle(Bulgu(
                satir, f"Ayrık yazılmış komut birleştirildi: '{k.replace('_', ' ')}' → '{k}'",
                "TürKod'da çok kelimeli komutlar alt çizgiyle tek kelime olarak yazılır.",
                0.96, "yazim"))
        return yeni

    # ------------------------------------------------------------------
    # 3. Sözdizimi
    # ------------------------------------------------------------------
    def _sozdizimi_asamasi(self, kod):
        durum = self._sozdizimi_durumu(kod)
        if durum is None:
            self.dusun("✅ Sözdizimi temiz görünüyor.")
            return kod
        self.dusun("🧩 Sözdizimi hatalarını çözüyorum…")
        gorulen = {self._hash(kod)}
        for _ in range(self.MAKS_SOZDIZIMI):
            durum = self._sozdizimi_durumu(kod)
            if durum is None:
                self.dusun("✅ Tüm sözdizimi hataları giderildi.")
                return kod
            if durum["tip"] == "CeviriHatasi":
                self._uyari_ekle(None, "Kod Python'a çevrilemedi.", seviye="hata")
                return kod
            satir, mesaj = durum["satir"], durum["mesaj"]
            self.dusun(f"⚠️ Satır {satir}: {self._mesaj_turkce(mesaj)}")

            adaylar = self._sozdizimi_adaylari(kod, satir, mesaj)
            en_iyi = None
            for sira, (aday_kod, bulgu) in enumerate(adaylar):
                if aday_kod is None or aday_kod == kod:
                    continue
                h = self._hash(aday_kod)
                if h in gorulen:
                    continue
                puan = self._degerlendir(kod, aday_kod, durum)
                if puan is None:
                    continue
                # Eşit puanda: daha az satıra dokunan, sonra daha güvenilir
                # (listede önce gelen) aday.
                dokunulan = len(self._degisen_satirlar(kod, aday_kod))
                anahtar = (puan, -dokunulan, -sira)
                if en_iyi is None or anahtar > en_iyi[0]:
                    en_iyi = (anahtar, aday_kod, bulgu)
            gecerli = [a for a in adaylar if a[0] is not None and a[0] != kod]
            if en_iyi is None:
                self._cozulemeyen_sozdizimi(kod, satir, mesaj)
                return kod
            if len(gecerli) > 1:
                self.dusun(f"💡 {len(gecerli)} olası çözümü denedim; en iyisini seçtim.", bekle=False)
            _, kod, bulgu = en_iyi
            gorulen.add(self._hash(kod))
            self._duzeltme_ekle(bulgu)
        return kod

    @staticmethod
    def _mesaj_turkce(mesaj):
        ceviri = (
            (r"expected ':'", "':' bekleniyordu"),
            (r"invalid syntax\. Perhaps you forgot a comma\?", "geçersiz yazım (virgül eksik olabilir)"),
            (r"invalid syntax", "geçersiz yazım"),
            (r"'(.)' was never closed", r"'\1' kapatılmamış"),
            (r"unmatched '(.)'", r"fazladan '\1'"),
            (r"closing parenthesis '(.)' does not match opening parenthesis '(.)'",
             r"'\1' kapanışı '\2' açılışıyla eşleşmiyor"),
            (r"expected an indented block.*", "girintili blok bekleniyordu"),
            (r"unexpected indent", "beklenmeyen girinti"),
            (r"unindent does not match any outer indentation level", "girinti seviyesi uyuşmuyor"),
            (r"unterminated string literal.*", "kapatılmamış metin (tırnak eksik)"),
            (r"unterminated triple-quoted string literal.*", "kapatılmamış çok satırlı metin"),
            (r"invalid character.*", "geçersiz karakter"),
            (r"Missing parentheses in call to '(\w+)'.*", r"'\1' çağrısında parantez eksik"),
            (r"expected '\('", "'(' bekleniyordu"),
            (r"cannot assign to .*", "buraya atama yapılamaz"),
            (r"'return' outside function", "'döndür' fonksiyon dışında"),
            (r"'break' outside loop", "'kır' döngü dışında"),
            (r"'continue' not properly in loop", "'devam_et' döngü dışında"),
        )
        for desen, tr in ceviri:
            if re.search(desen, mesaj):
                return re.sub(desen, tr, mesaj)
        return mesaj

    def _cozulemeyen_sozdizimi(self, kod, satir, mesaj):
        satirlar = kod.split("\n")
        metin = satirlar[satir - 1].strip() if 0 < satir <= len(satirlar) else ""
        oneri = ""
        try:
            kw = self.core._anahtar_kelime_tanimi(kod, satir)
        except Exception:
            kw = None
        if kw:
            mesaj_tr = kw["mesaj"]
            oneri = "Değişkene başka bir ad verin (ör. sonuna '_değer' ekleyin)."
            satir = kw["satir"] or satir
        else:
            mesaj_tr = f"Satır {satir}: {self._mesaj_turkce(mesaj)}"
            if "outside function" in mesaj:
                oneri = "'döndür' yalnızca bir fonksiyonun içinde kullanılabilir."
            elif "outside loop" in mesaj or "not properly in loop" in mesaj:
                oneri = "'kır' / 'devam_et' yalnızca bir döngünün içinde kullanılabilir."
            elif metin:
                oneri = f"Bu satırı kontrol edin: {metin[:80]}"
        self.dusun(f"🤔 Satır {satir}'deki hatayı güvenle düzeltemedim; öneri olarak bildiriyorum.")
        self._uyari_ekle(satir, mesaj_tr, oneri, seviye="hata", kategori="sozdizimi")

    # --- aday üreticiler ----------------------------------------------
    def _sozdizimi_adaylari(self, kod, satir, mesaj):
        m = mesaj.lower()
        adaylar = []

        def ekle(sonuc, baslik, aciklama, guven, kategori="sozdizimi", satir_no=None):
            if sonuc is None:
                return
            if isinstance(sonuc, tuple):
                sonuc = sonuc[0]
            adaylar.append((sonuc, Bulgu(satir_no or satir, baslik, aciklama, guven, kategori)))

        core = self.core
        satir_listesi = [satir] + ([satir - 1] if satir > 1 else [])

        if "indent" in m or "tab" in m:
            ekle(core._girinti_hatasi_duzelt(kod, satir, mesaj), "Girinti düzeltildi",
                 "Python'da bloklar girintiyle belirlenir; satırın girintisi "
                 "üstündeki bloğa göre hizalandı.", 0.9, "girinti")

        for s in satir_listesi:
            ekle(core._iki_nokta_duzelt(kod, s), "Eksik ':' eklendi",
                 "Blok başlatan komutlar (eğer, döngü, için, fonksiyon, sınıf …) "
                 "satır sonunda ':' ister.", 0.95, satir_no=s)

        if "'=='" in m or "cannot assign" in m or "invalid syntax" in m:
            ekle(core._esittir_duzelt(kod, satir), "Koşulda '=' → '==' yapıldı",
                 "'=' atama, '==' karşılaştırmadır; koşullarda karşılaştırma gerekir.",
                 0.9)

        ekle(self._operator_duzelt(kod, satir), "Operatör yazımı düzeltildi",
             "'=<', '=>', '<>' gibi yazımlar geçersizdir; doğrusu '<=', '>=', '!='.",
             0.93)

        if "missing parentheses" in m or "invalid syntax" in m:
            for s in satir_listesi:
                ekle(self._cagri_parantezi_ekle(kod, s), "Çağrıya parantez eklendi",
                     "Fonksiyon çağrılarında argümanlar parantez içinde yazılır: "
                     "yazdır(\"merhaba\").", 0.92, satir_no=s)

        if "expected '('" in m:
            ekle(self._fonksiyon_parantezi(kod, satir), "Fonksiyon tanımına '()' eklendi",
                 "Parametresi olmasa bile fonksiyon adından sonra '()' yazılmalıdır.",
                 0.95)

        if "comma" in m or "invalid syntax" in m:
            for s in satir_listesi:
                ekle(self._virgul_ekle(kod, s), "Eksik virgüller eklendi",
                     "Liste / çağrı içindeki değerler virgülle ayrılmalıdır.", 0.85,
                     satir_no=s)

        if "never closed" in m or "unexpected eof" in m or "invalid syntax" in m or "expected" in m:
            for s in range(satir, max(0, satir - 6), -1):
                for yeni, baslik in self._parantez_kapat_adaylari(kod, s):
                    ekle(yeni, baslik,
                         "Açılan her parantez kapatılmalıdır; kapanış en uygun yere eklendi.",
                         0.88, satir_no=s)

        if "unmatched" in m or "does not match" in m:
            ekle(self._fazla_kapanis_sil(kod, satir), "Fazladan kapanış parantezi silindi",
                 "Bu satırda açılmamış bir parantez kapatılıyordu.", 0.88)
            ekle(self._yanlis_kapanis_duzelt(kod, satir), "Yanlış tür kapanış parantezi düzeltildi",
                 "'(' ile açılan ')' ile, '[' ile açılan ']' ile kapanmalıdır.", 0.9)

        if "unterminated" in m or "eol" in m or "invalid syntax" in m:
            ekle(self._tirnak_duzelt(kod, satir), "Eksik / uyumsuz tırnak düzeltildi",
                 "Metinler aynı tür tırnakla açılıp kapanmalıdır.", 0.88)

        # Mevcut genel düzeltici (son çare).
        ekle(core._sozdizimi_duzelt(kod, satir, mesaj), "Sözdizimi hatası düzeltildi",
             "Hata satırı için bilinen kalıplarla otomatik düzeltme yapıldı.", 0.75)
        return adaylar

    @staticmethod
    def _operator_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        degisim = [("=<", "<="), ("=>", ">="), ("<>", "!="), ("=!", "!="), ("===", "==")]
        yeni = list(satir)
        degisti = False
        for eski, dogru in degisim:
            for mm in re.finditer(re.escape(eski), maskeli):
                a, b = mm.start(), mm.end()
                if eski == "=>" and maskeli[max(0, a - 1):a] in "<>!=":
                    continue
                yeni[a:b] = list(dogru) + [""] * (b - a - len(dogru))
                degisti = True
        if not degisti:
            return None
        satirlar[satir_no - 1] = "".join(yeni)
        return "\n".join(satirlar)

    def _cagri_parantezi_ekle(self, kod, satir_no):
        """yazdır "merhaba"  ->  yazdır("merhaba")"""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        sozluk = self._sozluk()
        m = re.match(rf"^(\s*)({ID})[ \t]+(?![=(\[.,:+\-*/%<>!])(.+?)\s*$", satir)
        if not m:
            return None
        ad = m.group(2)
        hedef = sozluk.get(ad, ad)
        cagrilabilir = (ad in self._CAGRILABILIR_KOMUTLAR
                        or (hasattr(builtins, hedef) and callable(getattr(builtins, hedef))
                            and not isinstance(getattr(builtins, hedef), type)))
        if not cagrilabilir or ad in _keyword_words or ad in _block_words:
            return None
        arguman = m.group(3)
        if arguman.endswith(":"):
            return None
        satirlar[satir_no - 1] = f"{m.group(1)}{ad}({arguman})"
        return "\n".join(satirlar)

    @staticmethod
    def _fonksiyon_parantezi(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        m = re.match(rf"^(\s*fonksiyon\s+{ID})\s*(:?)\s*$", satirlar[satir_no - 1])
        if not m:
            return None
        satirlar[satir_no - 1] = m.group(1) + "():"
        return "\n".join(satirlar)

    def _virgul_ekle(self, kod, satir_no):
        """[1 2 3] -> [1, 2, 3]   /   f(a b) -> f(a, b)"""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        anahtar = set(_keyword_words) | {
            "ve", "veya", "değil", "degil", "içinde", "icinde", "için", "icin", "eğer", "eger",
            "değilse", "degilse", "olarak", "aynı_mı", "ayni_mi", "isimsiz", "and", "or",
            "not", "in", "is", "if", "else", "for", "lambda", "as"}
        ekler = []
        derinlik = 0
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                derinlik += 1
            elif ch in _KAPAYAN:
                derinlik -= 1
            elif ch in " \t" and derinlik > 0:
                j = i
                while j < len(maskeli) and maskeli[j] in " \t":
                    j += 1
                if j >= len(maskeli) or i == 0 or maskeli[i - 1] in " \t":
                    continue
                onceki, sonraki = maskeli[i - 1], maskeli[j]
                atom_son = onceki.isalnum() or onceki in "_)]}\"'\x01"
                atom_bas = sonraki.isalnum() or sonraki in "_([{\"'" or sonraki == "\x01"
                if not (atom_son and atom_bas):
                    continue
                sol = re.search(r"(\w+)$", maskeli[:i])
                sag = re.match(r"(\w+)", maskeli[j:])
                if (sol and sol.group(1) in anahtar) or (sag and sag.group(1) in anahtar):
                    continue
                ekler.append(i)
        if not ekler:
            return None
        yeni = satir
        for i in reversed(ekler):
            yeni = yeni[:i] + "," + yeni[i:]
        satirlar[satir_no - 1] = yeni
        return "\n".join(satirlar)

    @staticmethod
    def _acik_parantezler(maskeli_satir):
        yigin = []
        for ch in maskeli_satir:
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN and yigin and yigin[-1] == _KAPAYAN[ch]:
                yigin.pop()
        return yigin

    def _parantez_kapat_adaylari(self, kod, satir_no):
        """Satırda açılıp kapanmayan parantezleri; aynı satırın sonuna (':'
        varsa ondan önce) ya da devam eden satırların sonuna kapatan adaylar."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return []
        maskeli = maskele(kod).split("\n")
        acik = self._acik_parantezler(maskeli[satir_no - 1])
        if not acik:
            return []
        ek = "".join(_ACAN[c] for c in reversed(acik))
        adaylar = []

        def kapat(i):
            s = satirlar[i].rstrip()
            ms = maskeli[i].rstrip()
            yorum = ""
            if len(ms) < len(s):  # satır sonunda yorum var
                yorum = s[len(ms):]
                s = s[:len(ms)].rstrip()
            if s.endswith(":"):
                yeni = s[:-1] + ek + ":"
            else:
                yeni = s + ek
            kopya = list(satirlar)
            kopya[i] = yeni + yorum
            return "\n".join(kopya)

        adaylar.append((kapat(satir_no - 1), f"Kapatılmamış parantez kapatıldı: {ek}"))
        # Çok satırlı ifade: virgülle biten satırlar boyunca devam et.
        i = satir_no - 1
        while i + 1 < len(satirlar) and satirlar[i].rstrip().endswith((",", "(", "[", "{")) \
                and i - satir_no < 30:
            i += 1
            adaylar.append((kapat(i), f"Çok satırlı ifadenin sonuna {ek} eklendi"))
        return adaylar

    @staticmethod
    def _fazla_kapanis_sil(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        yigin = []
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN:
                if yigin and yigin[-1] == _KAPAYAN[ch]:
                    yigin.pop()
                elif not yigin:
                    satirlar[satir_no - 1] = satir[:i] + satir[i + 1:]
                    return "\n".join(satirlar)
        return None

    @staticmethod
    def _yanlis_kapanis_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        yigin = []
        for i, ch in enumerate(maskeli):
            if ch in _ACAN:
                yigin.append(ch)
            elif ch in _KAPAYAN:
                if yigin and yigin[-1] == _KAPAYAN[ch]:
                    yigin.pop()
                elif yigin:
                    dogru = _ACAN[yigin.pop()]
                    satirlar[satir_no - 1] = satir[:i] + dogru + satir[i + 1:]
                    return "\n".join(satirlar)
        return None

    @staticmethod
    def _tirnak_duzelt(kod, satir_no):
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        govde = satir.rstrip()
        # "abc'  ->  "abc"   (uyumsuz tırnak)
        m = re.search(r"([\"'])([^\"'\n]*)([\"'])", govde)
        if m and m.group(1) != m.group(3):
            temiz = govde[:m.start()] + m.group(1) + m.group(2) + m.group(1) + govde[m.end():]
            if temiz.count('"') % 2 == 0 and temiz.count("'") % 2 == 0:
                satirlar[satir_no - 1] = temiz
                return "\n".join(satirlar)
        for t in ('"', "'"):
            if govde.count(t) % 2 == 1:
                # Kapanış: satır sonundaki ')' / ':' gibi karakterlerden önce.
                k = re.search(r"([)\]}:,]*)$", govde)
                son = k.group(1) if k else ""
                ic = govde[:len(govde) - len(son)] if son else govde
                bas = ic.find(t)
                if son and bas >= 0 and all(c not in ic[bas:] for c in son):
                    yeni = ic + t + son
                else:
                    yeni = govde + t
                satirlar[satir_no - 1] = yeni
                return "\n".join(satirlar)
        return None

    # ------------------------------------------------------------------
    # 4. Anlam (çalışma hatası vermeyen mantık hataları)
    # ------------------------------------------------------------------
    def _anlam_asamasi(self, kod):
        self.dusun("🧪 Kodun mantığını inceliyorum (tip uyumsuzlukları)…")
        yeni = self._girdi_tip_duzelt(kod)
        return yeni

    def _girdi_tip_duzelt(self, kod):
        """girdi_al() her zaman METİN döndürür. Değer sayıyla karşılaştırılıyor
        ya da aritmetikte kullanılıyorsa tamsayı(...)/ondalıklı(...) ile sarılır."""
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return kod

        atamalar = {}     # ad -> [satır]
        diger_atama = set()
        donusturulen = set()
        sayisal = {}      # ad -> "int" | "float"

        def input_mu(dugum):
            return (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name)
                    and dugum.func.id == "input")

        def sayi_mi(dugum):
            if isinstance(dugum, ast.Constant) and type(dugum.value) in (int, float):
                return "float" if isinstance(dugum.value, float) else "int"
            if isinstance(dugum, ast.UnaryOp) and isinstance(dugum.op, (ast.USub, ast.UAdd)):
                return sayi_mi(dugum.operand)
            return None

        for d in ast.walk(agac):
            if isinstance(d, ast.Assign):
                for hedef in d.targets:
                    if isinstance(hedef, ast.Name):
                        if input_mu(d.value):
                            atamalar.setdefault(hedef.id, []).append(d.lineno)
                        else:
                            diger_atama.add(hedef.id)
            elif isinstance(d, (ast.AugAssign, ast.AnnAssign)) and isinstance(d.target, ast.Name):
                diger_atama.add(d.target.id)
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) \
                    and d.func.id in ("int", "float") and d.args \
                    and isinstance(d.args[0], ast.Name):
                donusturulen.add(d.args[0].id)

        if not atamalar:
            return kod

        def isaretle(ad_dugum, diger):
            if isinstance(ad_dugum, ast.Name) and ad_dugum.id in atamalar:
                tur = sayi_mi(diger)
                if tur:
                    onceki = sayisal.get(ad_dugum.id)
                    sayisal[ad_dugum.id] = "float" if "float" in (tur, onceki) else "int"

        for d in ast.walk(agac):
            if isinstance(d, ast.Compare):
                parcalar = [d.left] + list(d.comparators)
                for op, (a, b) in zip(d.ops, zip(parcalar, parcalar[1:])):
                    if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq, ast.NotEq)):
                        isaretle(a, b)
                        isaretle(b, a)
            elif isinstance(d, ast.BinOp) and isinstance(
                    d.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
                # metin * tamsayı geçerli bir metin tekrarıdır (ad * 20);
                # bunu "sayıya çevir" diye yorumlamak doğru programı bozuyordu.
                def tamsayi_sabit(x):
                    return sayi_mi(x) == "int"
                if isinstance(d.op, ast.Mult) and (
                        tamsayi_sabit(d.left) or tamsayi_sabit(d.right)):
                    continue
                isaretle(d.left, d.right)
                isaretle(d.right, d.left)
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "range":
                for arg in d.args:
                    if isinstance(arg, ast.Name) and arg.id in atamalar:
                        sayisal.setdefault(arg.id, "int")

        sozluk = self._sozluk()
        for ad, tur in sorted(sayisal.items()):
            if ad in donusturulen or ad in diger_atama:
                continue
            sarici = _tr("float", "ondalıklı") if tur == "float" else _tr("int", "tamsayı")
            yeni = kod
            satirlar_d = []
            for satir_no in atamalar[ad]:
                sonraki = self._cagriyi_sar(yeni, satir_no, "input", sarici, sozluk)
                if sonraki:
                    yeni = sonraki
                    satirlar_d.append(satir_no)
            if not satirlar_d or self._sozdizimi_durumu(yeni) is not None:
                continue
            onceki = self._calistir(kod)
            sonra = self._calistir(yeni)
            if sonra["durum"] == "hata" and onceki["durum"] != "hata":
                continue
            kod = yeni
            self._duzeltme_ekle(Bulgu(
                satirlar_d[0],
                f"'{ad}' girdisi {sarici}(...) ile sayıya çevrildi",
                f"girdi_al() her zaman metin döndürür; '{ad}' ise sayıyla "
                f"karşılaştırılıyor / hesaplamada kullanılıyor. Çevrilmezse "
                f"'5' > 3 gibi karşılaştırmalar hata verir ya da '2' * 3 = '222' "
                f"gibi yanlış sonuç üretir.",
                0.88, "mantik"))
        return kod

    @staticmethod
    def _cagriyi_sar(kod, satir_no, py_ad, sarici, sozluk):
        """Satırdaki (TürKod karşılığı py_ad olan) çağrıyı sarici(...) içine alır."""
        satirlar = kod.split("\n")
        if not (0 < satir_no <= len(satirlar)):
            return None
        satir = satirlar[satir_no - 1]
        maskeli = maskele(satir)
        for m in re.finditer(rf"({ID})\s*\(", maskeli):
            ad = m.group(1)
            if sozluk.get(ad, ad) != py_ad:
                continue
            onceki = maskeli[:m.start()].rstrip()
            if onceki.endswith("("):
                ic_ad = re.search(rf"({ID})\s*\($", onceki)
                if ic_ad and sozluk.get(ic_ad.group(1), ic_ad.group(1)) in ("int", "float"):
                    return None
            ac = m.end() - 1
            kapa = _eslesen_kapanis(maskeli, ac)
            if kapa < 0:
                return None
            satirlar[satir_no - 1] = (satir[:m.start()] + f"{sarici}(" +
                                      satir[m.start():kapa + 1] + ")" + satir[kapa + 1:])
            return "\n".join(satirlar)
        return None

    # ------------------------------------------------------------------
    # 5. Çalışma zamanı
    # ------------------------------------------------------------------
    def _calisma_asamasi(self, kod):
        if not self.python_exe:
            self.dusun(f"ℹ️ {self.python_hata} Çalışma testi atlandı.")
            return kod
        if self._calistir(kod).get("arayuz"):
            self.dusun("🖼️ Program bir pencere/grafik arayüzü açıyor; güvenlik için "
                       "çalıştırmadan, yalnızca statik olarak inceliyorum.")
            return kod
        self.dusun("▶️ Kodu güvenli kipte çalıştırıp davranışını gözlüyorum…")
        cozulemeyen = set()
        for _ in range(self.maks_calisma):
            sonuc = self._calistir(kod)
            if sonuc["durum"] != "hata":
                if sonuc["durum"] == "zaman_asimi":
                    self._zaman_asimi_bildir(kod)
                return kod
            imza = (sonuc["satir"], sonuc["tip"], sonuc["mesaj"])
            if imza in cozulemeyen:
                return kod
            self.dusun(f"⚠️ Satır {sonuc['satir']}: {sonuc['tip']} — "
                       f"{self._calisma_mesaji(sonuc)}")
            adaylar = self._calisma_adaylari(kod, sonuc)
            secilen = None
            for aday_kod, bulgu in adaylar[:self.MAKS_ADAY_CALISTIRMA]:
                if aday_kod is None or aday_kod == kod:
                    continue
                if self._sozdizimi_durumu(aday_kod) is not None:
                    continue
                yeni = self._calistir(aday_kod)
                kayma = aday_kod.count("\n") - kod.count("\n")
                if self._daha_iyi(yeni, sonuc, kayma):
                    secilen = (aday_kod, bulgu)
                    break
                self.dusun("↩️ Bir çözüm denedim ama sorunu gidermedi; geri aldım.", bekle=False)
            if secilen is None:
                cozulemeyen.add(imza)
                self._calisma_ipucu(kod, sonuc)
                return kod
            kod, bulgu = secilen
            self._duzeltme_ekle(bulgu)
        return kod

    @staticmethod
    def _daha_iyi(yeni, eski, kayma=0):
        """Aday, hatayı gerçekten ilerletti mi?

        kayma: adayın eklediği/sildiği satır sayısı (hata satırları buna göre
        karşılaştırılır; üste bir satır eklenince aynı hata bir alt satırda
        görünür ama bu ilerleme değildir)."""
        if yeni["durum"] in ("ok", "zaman_asimi"):
            return True
        if yeni["durum"] != "hata":
            return False
        modul_hatasi = ("ModuleNotFoundError", "ImportError")
        if yeni["tip"] in modul_hatasi and eski["tip"] not in modul_hatasi:
            return False  # kurulu olmayan bir modül eklenmiş
        satir = yeni["satir"] - kayma if yeni["satir"] > eski["satir"] else yeni["satir"]
        if satir > eski["satir"]:
            return True  # hata daha ileri bir satıra taşındı
        if satir == eski["satir"] and yeni["tip"] == eski["tip"] \
                and yeni["mesaj"] != eski["mesaj"]:
            return True  # aynı satırda sıradaki sorun (ör. ikinci tanımsız ad)
        # Aynı satırda BAŞKA türde hata: düzeltme yeni bir sorun yarattı.
        return False

    @staticmethod
    def _calisma_mesaji(sonuc):
        sozluk = {
            "NameError": "tanımsız bir ad kullanılıyor",
            "TypeError": "veri tipleri uyumsuz",
            "AttributeError": "olmayan bir özellik/metot çağrılıyor",
            "ZeroDivisionError": "sıfıra bölme",
            "IndexError": "liste sınırı aşıldı",
            "KeyError": "sözlükte olmayan anahtar",
            "ValueError": "geçersiz değer",
            "UnboundLocalError": "değişken atanmadan önce kullanılıyor",
            "ModuleNotFoundError": "modül bulunamadı",
            "RecursionError": "sonsuz özyineleme",
        }
        return sozluk.get(sonuc["tip"], sonuc["mesaj"][:120])

    def _zaman_asimi_bildir(self, kod):
        satir = None
        for i, s in enumerate(kod.split("\n"), 1):
            temiz = s.strip()
            if re.match(r"^(döngü|dongu|için|icin)\b", temiz):
                satir = i
                break
        # Güvenli kipte her girdi_al() "1" döndürür; çıkışı kullanıcının
        # yazacağı bir değere (ör. "q") bağlı döngüler bu yüzden hiç bitmez.
        # Bu durum bir hata değil, bilgi olarak bildirilir.
        # Yalnızca gövdesinde girdi okuyan bir döngü varsa: programın başka
        # bir yerinde girdi_al() geçmesi, gerçek bir sonsuz döngüyü gizlememeli.
        girdiye_bagli = False
        agac, _ = self._py_agaci(kod)
        if agac is not None:
            for d in ast.walk(agac):
                if isinstance(d, (ast.While, ast.For)) and any(
                        isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                        and x.func.id == "input"
                        for x in self._dongu_govdesi_dugumleri(d)):
                    girdiye_bagli = True
                    break
        if girdiye_bagli:
            self.dusun("⏳ Program kullanıcı girdisi bekleyen bir döngü içeriyor; "
                       "test girdileriyle süre sınırında bitmedi (bu normal olabilir).")
            self._uyari_ekle(
                satir, "Döngünün bitmesi kullanıcının gireceği değere bağlı",
                "Test sırasında her girdi '1' kabul edildi ve döngü bitmedi; "
                "çıkış koşulunun gerçekten sağlanabildiğinden emin olun.",
                seviye="bilgi", kategori="dongu")
            return
        self.dusun("⏳ Kod süre sınırında bitmedi; sonsuz döngü olabilir.")
        self._uyari_ekle(
            satir, f"Kod {self.zaman_asimi} saniyede bitmedi (sonsuz döngü ya da uzun işlem?)",
            "Döngü koşulunun bir noktada Yanlış olduğundan ya da 'kır' ile "
            "çıkıldığından emin olun.", seviye="uyari", kategori="dongu")

    def _calisma_ipucu(self, kod, sonuc):
        ipucu = None
        for desen, aciklama in self.core._CALISMA_IPUCLARI:
            if re.search(desen, sonuc["son"]):
                ipucu = aciklama
                break
        if sonuc["tip"] == "ModuleNotFoundError":
            mm = re.search(r"No module named '([^']+)'", sonuc["mesaj"])
            ad = mm.group(1).split(".")[0] if mm else "?"
            self._uyari_ekle(None, f"'{ad}' modülü kurulu değil",
                             f"Terminalde: pip yükle {ad}", seviye="hata", kategori="modul")
            self.dusun(f"📦 '{ad}' modülü kurulu değil; kurulum komutunu öneriyorum.")
            return
        if sonuc["tip"] == "IndexError":
            ipucu = "liste/metin sınırı aşıldı; indeks uzunluk(...) - 1'den büyük olamaz."
        self.dusun("🤔 Bu çalışma hatasını otomatik düzeltmek güvenli değil; ipucu bırakıyorum.")
        self._uyari_ekle(sonuc["satir"], f"{sonuc['tip']}: {sonuc['mesaj'][:160]}",
                         ipucu or "Hata satırındaki değerleri kontrol edin.",
                         seviye="hata", kategori="calisma")

    # --- çalışma zamanı aday üreticileri ------------------------------
    def _calisma_adaylari(self, kod, sonuc):
        tip, mesaj, satir = sonuc["tip"], sonuc["mesaj"], sonuc["satir"]
        adaylar = []
        try:
            if tip == "NameError":
                m = re.search(r"name '([^']+)' is not defined", mesaj)
                if m:
                    adaylar += self._nameerror_adaylari(kod, satir, m.group(1))
            elif tip == "UnboundLocalError":
                m = re.search(r"variable '([^']+)'", mesaj)
                if m:
                    adaylar += self._kuresel_adayi(kod, satir, m.group(1))
            elif tip == "TypeError":
                if "can only concatenate str" in mesaj or (
                        "unsupported operand" in mesaj and "str" in mesaj and "+" in mesaj):
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                    adaylar += self._metin_sarma_adayi(kod, satir)
                elif "not supported between instances of" in mesaj and "str" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                elif "unsupported operand" in mesaj and "str" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
                m = re.search(r"(\w+)\(\) takes (\d+) positional arguments? but (\d+)", mesaj)
                if m and int(m.group(3)) == int(m.group(2)) + 1:
                    adaylar += self._kendisi_adayi(kod, m.group(1))
                if "'str' object cannot be interpreted as an integer" in mesaj:
                    adaylar += self._girdi_sarma_adaylari(kod, satir)
            elif tip == "AttributeError":
                m = re.search(r"'(\w+)' object has no attribute '(\w+)'", mesaj)
                if m:
                    adaylar += self._ozellik_adaylari(kod, satir, m.group(1), m.group(2))
        except Exception:
            pass
        return adaylar

    def _nameerror_adaylari(self, kod, satir, hata_adi):
        core = self.core
        satirlar = kod.split("\n")
        satir_metni = satirlar[satir - 1] if 0 < satir <= len(satirlar) else ""
        token, hedef = core._satirdaki_sorunlu_token(satir_metni, hata_adi)
        if token is None:
            tokenlar = re.findall(ID, maskele(satir_metni))
            yakin = core._en_yakin_eslesme(hata_adi, tokenlar, cutoff=0.65)
            if yakin:
                token = yakin[0]
                hedef = self._sozluk().get(token)
        if token is None:
            token = hata_adi
        adaylar = []

        # a) Eksik içe aktarma.
        if token in MODUL_CEVIRILERI:
            adaylar.append((self._ice_aktarma_ekle(kod, token), Bulgu(
                satir, f"Eksik içe aktarma eklendi: içe_aktar {token}",
                f"'{token}' bir modül; kullanılmadan önce içe aktarılması gerekir.",
                0.95, "ice_aktarma")))

        # b) Modül fonksiyonunun modülsüz kullanımı (karekök -> matematik.karekök).
        if hedef:
            son = hedef.split(".")[-1]
            alt = core._py_ciplak_index().get(son) or core._py_ciplak_index().get(hata_adi)
            if alt and not self._modul_var_mi(alt[0]):
                alt = None
            if alt:
                modul_tr, metot_tr = alt
                yeni = re.sub(rf"(?<![\w.]){re.escape(token)}\b", f"{modul_tr}.{metot_tr}",
                              satir_metni, count=1)
                aday = self._satir_degistir(kod, satir, yeni)
                if aday:
                    aday = self._ice_aktarma_ekle(aday, modul_tr) or aday
                    adaylar.append((aday, Bulgu(
                        satir, f"'{token}' → '{modul_tr}.{metot_tr}' (+ içe_aktar {modul_tr})",
                        f"'{token}' '{modul_tr}' modülünün bir fonksiyonu; modül adıyla "
                        f"çağrılmalı ve modül içe aktarılmalıdır.", 0.9, "ice_aktarma")))

        # c) Yazım hatası: tanımlı adlara / TürKod komutlarına en yakın ad.
        tanimlar = self._tanimlar(kod)
        params = set(re.findall(rf"fonksiyon\s+{ID}\s*\(([^)]*)\)", kod))
        for p in params:
            tanimlar |= set(re.findall(ID, p))
        oneriler = core._en_yakin_eslesme(token, sorted(tanimlar - {token}), cutoff=0.72)
        if not oneriler:
            komutlar = [k for k in self._sozluk() if len(k) > 2]
            oneriler = core._en_yakin_eslesme(token, komutlar, cutoff=0.8)
        for dogru in oneriler[:1]:
            aday = self._satir_degistir(kod, satir, ad_degistir(satir_metni, token, dogru))
            adaylar.append((aday, Bulgu(
                satir, f"Tanımsız '{token}' → '{dogru}'",
                f"'{token}' hiçbir yerde tanımlı değil; büyük olasılıkla '{dogru}' "
                f"yazılmak istendi (benzerlik %{int(difflib.SequenceMatcher(None, _normalize(token), _normalize(dogru)).ratio() * 100)}).",
                0.82, "ad")))

        # d) Tırnaksız metin: yazdır(merhaba) -> yazdır("merhaba")
        if not oneriler and token not in tanimlar:
            m = re.search(rf"(\(\s*){re.escape(token)}(\s*\))", satir_metni)
            if m and re.search(r"(yazdır|yazdir)\s*\(\s*" + re.escape(token), satir_metni):
                yeni = satir_metni[:m.start()] + m.group(1) + f'"{token}"' + m.group(2) + satir_metni[m.end():]
                adaylar.append((self._satir_degistir(kod, satir, yeni), Bulgu(
                    satir, f"'{token}' metin olarak tırnağa alındı",
                    "Tanımlı olmayan bu kelime büyük olasılıkla ekrana yazdırılmak "
                    "istenen bir metin; metinler tırnak içinde yazılır.", 0.7, "ad")))

        # e) Tanımlanmadan önce kullanım: ileride atanıyorsa bildir.
        sonra = re.search(rf"^\s*{re.escape(token)}\s*=(?!=)", "\n".join(satirlar[satir:]), re.M)
        if sonra and not adaylar:
            ileri = satir + "\n".join(satirlar[satir:])[:sonra.start()].count("\n") + 1
            self._uyari_ekle(satir, f"'{token}' tanımlanmadan önce kullanılıyor",
                             f"'{token}' ancak satır {ileri}'de tanımlanıyor; tanımı "
                             f"kullanımdan önceye taşıyın.", seviye="hata", kategori="ad")
        return adaylar

    def _kuresel_adayi(self, kod, satir, ad):
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        g = _girinti(satirlar[satir - 1])
        baslik = None
        for i in range(satir - 2, -1, -1):
            s = satirlar[i]
            if s.strip() and _girinti(s) < g and re.match(r"^\s*fonksiyon\b", s):
                baslik = i
                break
            if s.strip() and _girinti(s) == 0:
                break
        if baslik is None:
            return []
        if not re.search(rf"^{re.escape(ad)}\s*=(?!=)", kod, re.M):
            return []
        govde_g = None
        for s in satirlar[baslik + 1:]:
            if s.strip():
                govde_g = _girinti(s)
                break
        if govde_g is None:
            return []
        kopya = list(satirlar)
        kuresel = _tr("global", "küresel")
        kopya.insert(baslik + 1, " " * govde_g + f"{kuresel} {ad}")
        return [("\n".join(kopya), Bulgu(
            baslik + 2, f"'{kuresel} {ad}' eklendi",
            f"Fonksiyon, dışarıda tanımlı '{ad}' değişkenini değiştiriyor. "
            f"Python bunu yeni bir yerel değişken sanar; '{kuresel}' ile dıştaki "
            f"değişkenin kullanılacağı belirtilmelidir.", 0.88, "kapsam"))]

    def _girdi_sarma_adaylari(self, kod, satir):
        """Hata satırında, girdi_al() ile okunmuş ve sayıya çevrilmemiş
        değişkenlerin atamalarını tamsayı(...) ile sarar."""
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        adlar = set(re.findall(ID, maskele(satirlar[satir - 1])))
        sozluk = self._sozluk()
        girdi_kelimeleri = [k for k, v in sozluk.items() if v == "input"] or ["girdi_al"]
        gk = "|".join(re.escape(k) for k in girdi_kelimeleri)
        adaylar = []
        yeni = kod
        sarilan = []
        maskeli = maskele(kod).split("\n")
        for i, s in enumerate(maskeli, 1):
            m = re.match(rf"^\s*({ID})\s*=\s*(?:{gk})\s*\(", s)
            if m and m.group(1) in adlar:
                sonraki = self._cagriyi_sar(yeni, i, "input", _tr("int", "tamsayı"), sozluk)
                if sonraki:
                    yeni = sonraki
                    sarilan.append((i, m.group(1)))
        if sarilan:
            adlar_metin = ", ".join(f"'{a}'" for _, a in sarilan)
            adaylar.append((yeni, Bulgu(
                sarilan[0][0], f"{adlar_metin} girdisi tamsayıya çevrildi",
                "girdi_al() metin döndürür; metin ile sayı arasında işlem / "
                "karşılaştırma yapılamaz.", 0.86, "tip")))
        return adaylar

    def _metin_sarma_adayi(self, kod, satir):
        """"Yaş: " + yaş   ->   "Yaş: " + metin(yaş)"""
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        satir_metni = satirlar[satir - 1]
        maskeli = maskele(satir_metni)
        str_lit = r"[rRbBfFuU]{0,2}(?:\"[^\"\n]*\"|'[^'\n]*')"
        operand = rf"(?<![\w.]){ID}(?:\[[^\[\]]*\])?(?![\w(.\[])"
        if not re.search(str_lit, maskeli) or "+" not in maskeli:
            return []
        metin_kelime = _tr("str", "metin")
        araliklar = set()
        for m in re.finditer(rf"({str_lit}|\))\s*\+\s*({operand})", maskeli):
            araliklar.add(m.span(2))
        for m in re.finditer(rf"({operand})\s*\+\s*(?={str_lit})", maskeli):
            araliklar.add(m.span(1))
        # Zincir: "a" + ad + yaş  -> zincirdeki tüm adlar
        for zincir in re.finditer(rf"(?:(?:{str_lit}|{operand})\s*\+\s*)+(?:{str_lit}|{operand})", maskeli):
            if re.search(str_lit, zincir.group(0)):
                for m in re.finditer(operand, zincir.group(0)):
                    a = zincir.start() + m.start()
                    araliklar.add((a, a + len(m.group(0))))
        tanimlar_str = set()
        for mm in re.finditer(rf"^\s*({ID})\s*=\s*{str_lit}\s*$", maskele(kod), re.M):
            tanimlar_str.add(mm.group(1))
        anahtar = set(_keyword_words) | {"Doğru", "Yanlış", "Hiçlik"}
        secilen = []
        for a, b in sorted(araliklar):
            ad = maskeli[a:b]
            kok = re.match(ID, ad).group(0)
            if kok in tanimlar_str or kok in anahtar or kok == metin_kelime:
                continue
            if any(a < y and x < b for x, y in secilen):
                continue
            secilen.append((a, b))
        if not secilen:
            return []
        yeni = satir_metni
        for a, b in sorted(secilen, reverse=True):
            yeni = yeni[:a] + f"{metin_kelime}(" + yeni[a:b] + ")" + yeni[b:]
        adlar = ", ".join(f"'{satir_metni[a:b]}'" for a, b in secilen)
        return [(self._satir_degistir(kod, satir, yeni), Bulgu(
            satir, f"{adlar} {metin_kelime}(...) ile metne çevrildi",
            "Metin ile sayı '+' ile birleştirilemez; sayı önce metne "
            f"çevrilmelidir ({metin_kelime}(sayı)).", 0.87, "tip"))]

    def _kendisi_adayi(self, kod, fonk_adi):
        satirlar = kod.split("\n")
        ilk_paramlar = re.findall(r"^\s+fonksiyon\s+\w+\s*\(\s*(\w+)", kod, re.M)
        varsayilan = _tr("self", "kendisi")
        kelime = max(set(ilk_paramlar), key=ilk_paramlar.count) if ilk_paramlar else varsayilan
        if kelime not in (varsayilan, "kendi", "self", "kendisi"):
            kelime = varsayilan
        for i, s in enumerate(satirlar):
            m = re.match(rf"^(\s+fonksiyon\s+{re.escape(fonk_adi)}\s*\()(\s*)(\)?)(.*)$", s)
            if not m:
                continue
            if m.group(3):
                yeni = m.group(1) + kelime + ")" + m.group(4)
            else:
                yeni = m.group(1) + kelime + ", " + s[len(m.group(1)) + len(m.group(2)):]
            kopya = list(satirlar)
            kopya[i] = yeni
            return [("\n".join(kopya), Bulgu(
                i + 1, f"'{fonk_adi}' metoduna '{kelime}' parametresi eklendi",
                f"Sınıf içindeki metotlar, nesnenin kendisini ilk parametre olarak "
                f"('{kelime}') alır; eksik olduğunda 'takes 0 positional arguments "
                f"but 1 was given' hatası oluşur.", 0.9, "sinif"))]
        return []

    def _ozellik_adaylari(self, kod, satir, tip_adi, ozellik):
        tipler = {"list": list, "str": str, "dict": dict, "set": set, "tuple": tuple,
                  "int": int, "float": float}
        tip = tipler.get(tip_adi)
        if tip is None:
            return []
        satirlar = kod.split("\n")
        if not (0 < satir <= len(satirlar)):
            return []
        satir_metni = satirlar[satir - 1]
        sozluk = self._sozluk()
        gecerli = {a for a in dir(tip) if not a.startswith("_")}
        # Satırdaki ".kelime" — Python karşılığı hatalı özellik olan.
        token = None
        for m in re.finditer(rf"\.\s*({ID})", maskele(satir_metni)):
            t = m.group(1)
            if sozluk.get(t, t) == ozellik or t == ozellik:
                token = t
                break
        if token is None:
            return []
        adaylar_tr = {tr: py for tr, py in sozluk.items() if py in gecerli and "." not in py}
        for py in gecerli:
            adaylar_tr.setdefault(py, py)
        puanlar = []
        nt = _normalize(token)
        for tr, py in adaylar_tr.items():
            ntr = _normalize(tr)
            oran = max(difflib.SequenceMatcher(None, nt, ntr).ratio(),
                       difflib.SequenceMatcher(None, ozellik.lower(), py.lower()).ratio())
            if nt and (nt in ntr.split("_") or ntr.endswith("_" + nt)):
                oran = max(oran, 0.8)
            puanlar.append((oran, tr.isascii(), tr, py))
        puanlar.sort(key=lambda x: (-x[0], x[1]))
        adaylar = []
        for oran, _, tr, py in puanlar[:3]:
            if oran < 0.6:
                break
            yeni = re.sub(rf"\.\s*{re.escape(token)}\b", f".{tr}", satir_metni, count=1)
            tip_tr = _tr(tip_adi, tip_adi)
            adaylar.append((self._satir_degistir(kod, satir, yeni), Bulgu(
                satir, f"'.{token}' → '.{tr}'",
                f"{tip_tr} türünde '{token}' diye bir metot yok; en yakın karşılık "
                f"'{tr}' ({py}).", round(0.6 + 0.35 * oran, 2), "metot")))
        return adaylar

    # ------------------------------------------------------------------
    # 6. İnceleme (otomatik düzeltilmeyen durumlar)
    # ------------------------------------------------------------------
    def _inceleme_asamasi(self, kod):
        self.dusun("🔎 Son inceleme: döngüler, fonksiyon çağrıları, ulaşılamayan kod…")
        agac, _ = self._py_agaci(kod)
        if agac is None:
            return
        try:
            self._ast_incele(agac, kod)
        except Exception:
            pass
        try:
            for u in self.core._golgeleme_uyarilari(kod):
                self._uyari_ekle(u.get("satir"), u.get("mesaj", "").split(": ", 1)[-1],
                                 "Farklı bir değişken adı kullanın; aksi hâlde bu "
                                 "komut dosyada çalışmaz.", seviye="uyari", kategori="ad")
        except Exception:
            pass

    def _ast_incele(self, agac, kod):
        fonksiyonlar = {}
        for d in ast.walk(agac):
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fonksiyonlar.setdefault(d.name, []).append(d)

        # Aynı ad ile iki kez tanımlanan fonksiyonlar (modül düzeyi).
        gorulen = {}
        for d in agac.body:
            if isinstance(d, (ast.FunctionDef, ast.ClassDef)):
                if d.name in gorulen:
                    self._uyari_ekle(d.lineno, f"'{d.name}' ikinci kez tanımlanıyor",
                                     f"Satır {gorulen[d.name]}'deki tanım geçersiz kalır.",
                                     seviye="uyari", kategori="tanim")
                gorulen[d.name] = d.lineno

        for d in ast.walk(agac):
            # Ulaşılamayan kod.
            for alan in ("body", "orelse", "finalbody"):
                govde = getattr(d, alan, None)
                if not isinstance(govde, list):
                    continue
                for i, ifade in enumerate(govde[:-1]):
                    if isinstance(ifade, (ast.Return, ast.Break, ast.Continue, ast.Raise)):
                        sonraki = govde[i + 1]
                        komut = {ast.Return: "döndür", ast.Break: "kır",
                                 ast.Continue: "devam_et", ast.Raise: "hata_fırlat"}[type(ifade)]
                        self._uyari_ekle(sonraki.lineno, "Bu satıra hiçbir zaman ulaşılamaz",
                                         f"Hemen önündeki '{komut}' bloğu sonlandırıyor.",
                                         seviye="uyari", kategori="akis")
                        break

            # Sonsuz döngü riski.
            if isinstance(d, ast.While):
                # çık()/exit()/sys.exit() da döngüden (programdan) çıkar.
                cikis = any(
                    isinstance(x, (ast.Break, ast.Return, ast.Raise))
                    or (isinstance(x, ast.Call) and (
                        (isinstance(x.func, ast.Name) and x.func.id in ("exit", "quit"))
                        or (isinstance(x.func, ast.Attribute) and x.func.attr == "exit")))
                    for x in self._dongu_govdesi_dugumleri(d))
                sabit_dogru = isinstance(d.test, ast.Constant) and bool(d.test.value)
                if sabit_dogru and not cikis and not self._cagri_var(d):
                    self._uyari_ekle(d.lineno, "'döngü Doğru' içinde çıkış yok (sonsuz döngü)",
                                     "Döngüden çıkmak için bir koşulla 'kır' kullanın.",
                                     seviye="hata", kategori="dongu")
                elif not sabit_dogru and not cikis:
                    adlar = {n.id for n in ast.walk(d.test) if isinstance(n, ast.Name)}
                    degisen = set()
                    for x in self._dongu_govdesi_dugumleri(d):
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                            degisen.add(x.id)
                        elif isinstance(x, ast.AugAssign) and isinstance(x.target, ast.Name):
                            degisen.add(x.target.id)
                    cagri = self._cagri_var(d)
                    if adlar and not (adlar & degisen) and not cagri:
                        liste = ", ".join(sorted(adlar))
                        self._uyari_ekle(d.lineno, f"Döngü koşulundaki {liste} döngü içinde hiç değişmiyor",
                                         "Koşul hiç Yanlış olmayacağından döngü sonsuza kadar "
                                         "sürebilir; döngü içinde değişkeni güncelleyin "
                                         "(ör. sayaç = sayaç + 1).", seviye="hata", kategori="dongu")

            # Kullanıcı fonksiyonlarına yanlış sayıda argüman.
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) \
                    and d.func.id in fonksiyonlar and len(fonksiyonlar[d.func.id]) == 1:
                f = fonksiyonlar[d.func.id][0]
                a = f.args
                if a.vararg or a.kwarg or any(isinstance(x, ast.Starred) for x in d.args) or d.keywords:
                    continue
                toplam = len(a.posonlyargs) + len(a.args)
                en_az = toplam - len(a.defaults)
                verilen = len(d.args)
                if not (en_az <= verilen <= toplam):
                    beklenen = str(toplam) if en_az == toplam else f"{en_az}-{toplam}"
                    self._uyari_ekle(d.lineno,
                                     f"'{d.func.id}' {beklenen} argüman bekliyor, {verilen} verilmiş",
                                     f"Tanım satır {f.lineno}: argüman sayısını tanımla eşleştirin.",
                                     seviye="hata", kategori="cagri")

            # Sıfıra bölme.
            # ("%d" % 0 bir metin biçimlendirmesidir, bölme değil.)
            metin_bicim = isinstance(d, ast.BinOp) and isinstance(d.op, ast.Mod) and (
                isinstance(d.left, (ast.JoinedStr,))
                or (isinstance(d.left, ast.Constant) and isinstance(d.left.value, str)))
            if isinstance(d, ast.BinOp) and isinstance(d.op, (ast.Div, ast.FloorDiv, ast.Mod)) \
                    and not metin_bicim \
                    and isinstance(d.right, ast.Constant) and d.right.value == 0 \
                    and not isinstance(d.right.value, bool):
                self._uyari_ekle(d.lineno, "Sıfıra bölme", "Bölen 0 olamaz.",
                                 seviye="hata", kategori="matematik")

            # Hiçlik / Doğru ile '==' karşılaştırması.
            if isinstance(d, ast.Compare) and len(d.ops) == 1 and isinstance(d.ops[0], (ast.Eq, ast.NotEq)):
                sag = d.comparators[0]
                if isinstance(sag, ast.Constant) and sag.value is None:
                    self._uyari_ekle(d.lineno, "Hiçlik ile '==' karşılaştırması",
                                     "Hiçlik kontrolü için 'aynı_mı Hiçlik' kullanmak daha doğrudur.",
                                     seviye="bilgi", kategori="stil")
                elif isinstance(sag, ast.Constant) and sag.value is True and isinstance(d.ops[0], ast.Eq):
                    self._uyari_ekle(d.lineno, "'== Doğru' gereksiz",
                                     "'eğer x == Doğru:' yerine kısaca 'eğer x:' yazılabilir.",
                                     seviye="bilgi", kategori="stil")

            # Kendine atama.
            if isinstance(d, ast.Assign) and len(d.targets) == 1 \
                    and isinstance(d.targets[0], ast.Name) and isinstance(d.value, ast.Name) \
                    and d.targets[0].id == d.value.id:
                self._uyari_ekle(d.lineno, f"'{d.value.id} = {d.value.id}' hiçbir şey yapmıyor",
                                 seviye="bilgi", kategori="stil")

            # Değiştirilebilir varsayılan argüman.
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for v in d.args.defaults:
                    if isinstance(v, (ast.List, ast.Dict, ast.Set)):
                        self._uyari_ekle(d.lineno,
                                         f"'{d.name}' içinde liste/sözlük varsayılan değer",
                                         "Bu değer tüm çağrılarda paylaşılır; Hiçlik verip "
                                         "fonksiyon içinde oluşturun.", seviye="bilgi",
                                         kategori="stil")
                self._kullanilmayanlar(d)

    @staticmethod
    def _dongu_govdesi_dugumleri(dongu):
        for ifade in dongu.body + dongu.orelse:
            yield from ast.walk(ifade)

    @staticmethod
    def _cagri_var(dongu):
        """Döngü gövdesinde koşulu dolaylı değiştirebilecek bir çağrı var mı?
        Yerleşik fonksiyonlar (yazdır, uzunluk …) değişken değiştiremez;
        kullanıcı fonksiyonları ve metotlar (liste.çıkar() …) değiştirebilir."""
        for ifade in dongu.body:
            for x in ast.walk(ifade):
                if isinstance(x, ast.Call):
                    if isinstance(x.func, ast.Name) and hasattr(builtins, x.func.id) \
                            and x.func.id not in ("exec", "eval", "input"):
                        continue
                    return True
        return False

    def _kullanilmayanlar(self, fonk):
        atanan = {}
        okunan = set()
        kuresel = set()
        for x in ast.walk(fonk):
            if isinstance(x, (ast.Global, ast.Nonlocal)):
                kuresel.update(x.names)
            elif isinstance(x, ast.Name):
                if isinstance(x.ctx, ast.Store):
                    atanan.setdefault(x.id, x.lineno)
                else:
                    okunan.add(x.id)
            elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x is not fonk:
                okunan.update(n.id for n in ast.walk(x) if isinstance(n, ast.Name))
        for ad, satir in atanan.items():
            if ad not in okunan and ad not in kuresel and not ad.startswith("_"):
                self._uyari_ekle(satir, f"'{ad}' değişkenine değer atanıyor ama hiç kullanılmıyor",
                                 "Gereksizse silin; değilse adı doğru yazdığınızdan emin olun.",
                                 seviye="bilgi", kategori="stil")

    # ------------------------------------------------------------------
    # 7. Son doğrulama + rapor
    # ------------------------------------------------------------------
    def _son_dogrulama(self, kod):
        self.dusun("🧾 Son doğrulamayı yapıyorum…")
        durum = self._sozdizimi_durumu(kod)
        if durum is not None:
            return {"durum": "sozdizimi",
                    "metin": f"⚠️ Kalan sözdizimi hatası: Satır {durum['satir']} "
                             f"({self._mesaj_turkce(durum['mesaj'])})"}
        sonuc = self._calistir(kod)
        if sonuc["durum"] == "ok":
            return {"durum": "ok", "metin": "✅ Doğrulandı: kod hatasız çalıştı."}
        if sonuc["durum"] == "zaman_asimi":
            return {"durum": "zaman_asimi",
                    "metin": f"⏳ Son doğrulama {self.zaman_asimi} saniyelik süre sınırına "
                             "takıldı (sonsuz döngü ya da kullanıcı girdisi bekleyen döngü?)."}
        if sonuc["durum"] == "hata":
            return {"durum": "hata",
                    "metin": f"⚠️ Kalan hata: Satır {sonuc['satir']}: {sonuc['son'][:200]}"}
        if sonuc["durum"] == "atlandi":
            neden = ("Program pencere/grafik arayüzü açtığı için"
                     if sonuc.get("arayuz") else "Python bulunamadığı için")
            return {"durum": "atlandi",
                    "metin": f"ℹ️ {neden} yalnızca sözdizimi doğrulandı."}
        return {"durum": sonuc["durum"], "metin": ""}

    def _rapor(self, orijinal, kod, son, sure):
        degisti = kod != orijinal
        hata_uyari = sum(1 for u in self.uyarilar if u.seviye == "hata")
        normal_uyari = sum(1 for u in self.uyarilar if u.seviye == "uyari")
        bilgi = sum(1 for u in self.uyarilar if u.seviye == "bilgi")

        saglik = 100
        if son["durum"] in ("sozdizimi", "hata"):
            saglik -= 35
        elif son["durum"] == "zaman_asimi":
            saglik -= 15
        saglik -= 12 * hata_uyari + 5 * normal_uyari + 1 * bilgi
        saglik = max(0, min(100, saglik))

        if self.duzeltmeler:
            guven = sum(b.guven for b in self.duzeltmeler) / len(self.duzeltmeler)
            if son["durum"] == "ok":
                guven = min(0.99, guven + 0.08)
            elif son["durum"] in ("sozdizimi", "hata"):
                guven -= 0.15
            guven = int(round(max(0.0, min(1.0, guven)) * 100))
        else:
            guven = 100 if son["durum"] == "ok" else 0

        n = len(self.duzeltmeler)
        if n and son["durum"] == "ok":
            ozet = f"{n} sorun buldum ve düzelttim; kod artık hatasız çalışıyor."
        elif n:
            ozet = f"{n} sorunu düzelttim ancak hâlâ dikkat gerektiren bir sorun var."
        elif son["durum"] == "ok" and not hata_uyari:
            ozet = "Kodda düzeltilmesi gereken bir hata bulamadım. 👍"
        elif son["durum"] == "ok":
            ozet = "Kod çalışıyor ama gözden geçirmeniz gereken noktalar var."
        else:
            ozet = "Hatayı güvenle otomatik düzeltemedim; nedenini ve önerimi aşağıda bulabilirsiniz."
        if self.uyarilar:
            ozet += f" {len(self.uyarilar)} öneri/uyarı var."

        self.dusun(f"🏁 Bitti: {ozet}", bekle=False)

        seviye_sira = {"hata": 0, "uyari": 1, "bilgi": 2}
        uyarilar = sorted(self.uyarilar,
                          key=lambda u: (seviye_sira.get(u.seviye, 3), u.satir or 10 ** 9))

        degisiklik_metinleri = [b.metin() for b in self.duzeltmeler]
        degisiklik_metinleri += [
            f"• {('Satır ' + str(u.satir) + ': ') if u.satir else ''}{u.baslik}"
            + (f"\n  İpucu: {u.oneri}" if u.oneri else "")
            for u in uyarilar if u.seviye in ("hata", "uyari")
        ]

        return {
            "ok": True,
            "degisiklik": degisti or bool(degisiklik_metinleri),
            "kod": kod,
            "degisiklikler": degisiklik_metinleri,
            "son_mesaj": "",
            "dogrulama": son["metin"],
            "diff": self.core._diff_olustur(orijinal, kod) if degisti else "",
            "mesaj": ozet,
            "rapor": {
                "ozet": ozet,
                "durum": son["durum"],
                "saglik": saglik,
                "guven": guven,
                "sure_ms": int(sure * 1000),
                "calistirma": self.calistirma_sayisi,
                "duzeltmeler": [b.sozluk() for b in self.duzeltmeler],
                "uyarilar": [u.sozluk() for u in uyarilar],
                "dusunceler": list(self.dusunceler),
            },
        }


def ad_degistir(satir, eski, yeni):
    """Satırda metin/yorum DIŞINDAKİ 'eski' adlarını 'yeni' ile değiştirir."""
    parcalar = re.split(r"(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|#.*$)", satir)
    for i in range(0, len(parcalar), 2):
        parcalar[i] = re.sub(rf"(?<![\w.]){re.escape(eski)}(?![\w])", yeni, parcalar[i])
    return "".join(parcalar)
