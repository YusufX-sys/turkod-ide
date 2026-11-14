"""turkod_flutter/lib/main.dart dosyasını gerektiğinde parçalara böler ve
parçalardan tam dosyayı yeniden üretir.

main.dart kalıcı olarak bölünmez; tek dosya olarak kalır. Büyük bir
düzenleme gerektiğinde:

    python tools/main_dart_parcala.py bol          # parçalara ayır
    ... tools/main_dart_parcalar/*.dart dosyalarını düzenle ...
    python tools/main_dart_parcala.py birlestir    # main.dart'ı yeniden üret
    python tools/main_dart_parcala.py temizle      # parça klasörünü sil

Diğer komutlar:

    python tools/main_dart_parcala.py liste        # bölümleri satır aralığıyla listele
    python tools/main_dart_parcala.py dogrula      # böl+birleştir bayt bayt aynı mı?

Bölme noktaları dosyadaki bölüm başlıklarıdır:

    // ============================================================================
    // BÖLÜM ADI
    // ============================================================================

Parçalar bu başlıkların ilk satırından başlar; birleştirme parçaları sıra
dosyasındaki (_sira.json) sırayla, hiçbir şey eklemeden uç uca ekler. Satır
sonları (LF/CRLF) ve kodlama aynen korunur.

Güvenlik: bölmeden sonra main.dart başka yoldan değiştirildiyse 'birlestir'
bu değişiklikleri ezmemek için durur (--zorla ile geçilebilir). Birleştirme
öncesi eski main.dart, parça klasörüne yedeklenir.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_DART = os.path.join(KOK, 'turkod_flutter', 'lib', 'main.dart')
PARCA_DIZINI = os.path.join(KOK, 'tools', 'main_dart_parcalar')
SIRA_DOSYASI = '_sira.json'
YEDEK_DOSYASI = '_main.dart.yedek'

_CIZGI = re.compile(rb'^// ={20,}\s*$')
_BASLIK = re.compile(rb'^// (?!=)(.+?)\s*$')


def _oku(yol):
    with open(yol, 'rb') as f:
        return f.read()


def _yaz(yol, veri):
    with open(yol, 'wb') as f:
        f.write(veri)


def _ozet(veri):
    return hashlib.sha256(veri).hexdigest()


def _satirlar(veri):
    # keepends: LF/CRLF aynen korunur, birleştirme bayt bayt aynı olur.
    return veri.splitlines(keepends=True)


def _slug(baslik):
    tr = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
    s = baslik.translate(tr)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return s[:40] or 'bolum'


def bolumleri_bul(veri):
    """[(baslangic_satiri, baslik)] döndürür (0 tabanlı)."""
    satirlar = _satirlar(veri)
    bolumler = []
    for i in range(len(satirlar) - 2):
        if (_CIZGI.match(satirlar[i]) and _BASLIK.match(satirlar[i + 1])
                and _CIZGI.match(satirlar[i + 2])):
            baslik = _BASLIK.match(satirlar[i + 1]).group(1).decode('utf-8')
            bolumler.append((i, baslik))
    return bolumler


def _parcalar(veri):
    satirlar = _satirlar(veri)
    bolumler = bolumleri_bul(veri)
    noktalar = [(0, 'BASLANGIC')]
    for bas, baslik in bolumler:
        if bas == 0:
            noktalar[0] = (0, baslik)
        else:
            noktalar.append((bas, baslik))
    sonuc = []
    for n, (bas, baslik) in enumerate(noktalar):
        son = noktalar[n + 1][0] if n + 1 < len(noktalar) else len(satirlar)
        ad = '%02d_%s.dart' % (n, _slug(baslik))
        sonuc.append((ad, baslik, bas, son, b''.join(satirlar[bas:son])))
    return sonuc


def komut_liste(_):
    veri = _oku(MAIN_DART)
    for ad, baslik, bas, son, _p in _parcalar(veri):
        print('%-45s %6d-%-6d (%5d satır)  %s' % (ad, bas + 1, son, son - bas, baslik))
    return 0


def komut_bol(args):
    if os.path.isdir(PARCA_DIZINI) and os.listdir(PARCA_DIZINI) and not args.zorla:
        print('HATA: %s zaten dolu. Önce "birlestir" ya da "temizle" çalıştırın '
              '(veya --zorla).' % PARCA_DIZINI)
        return 1
    if os.path.isdir(PARCA_DIZINI):
        shutil.rmtree(PARCA_DIZINI)
    os.makedirs(PARCA_DIZINI)
    veri = _oku(MAIN_DART)
    parcalar = _parcalar(veri)
    for ad, _b, _s, _e, icerik in parcalar:
        _yaz(os.path.join(PARCA_DIZINI, ad), icerik)
    sira = {
        'kaynak': os.path.relpath(MAIN_DART, KOK).replace('\\', '/'),
        'kaynak_sha256': _ozet(veri),
        'parcalar': [{'dosya': ad, 'baslik': b, 'sha256': _ozet(i)}
                     for ad, b, _s, _e, i in parcalar],
    }
    with open(os.path.join(PARCA_DIZINI, SIRA_DOSYASI), 'w', encoding='utf-8') as f:
        json.dump(sira, f, ensure_ascii=False, indent=2)
    print('%d parça yazıldı: %s' % (len(parcalar), PARCA_DIZINI))
    return 0


def _birlesik(sira):
    parcalar = []
    for p in sira['parcalar']:
        yol = os.path.join(PARCA_DIZINI, p['dosya'])
        if not os.path.isfile(yol):
            raise SystemExit('HATA: parça eksik: %s' % yol)
        parcalar.append(_oku(yol))
    return b''.join(parcalar)


def komut_birlestir(args):
    sira_yolu = os.path.join(PARCA_DIZINI, SIRA_DOSYASI)
    if not os.path.isfile(sira_yolu):
        print('HATA: %s yok. Önce "bol" çalıştırın.' % sira_yolu)
        return 1
    with open(sira_yolu, encoding='utf-8') as f:
        sira = json.load(f)
    mevcut = _oku(MAIN_DART)
    if _ozet(mevcut) != sira['kaynak_sha256'] and not args.zorla:
        print('HATA: main.dart bölmeden sonra başka yoldan değiştirilmiş; '
              'birleştirme o değişiklikleri ezer. Yine de yazmak için --zorla.')
        return 1
    yeni = _birlesik(sira)
    degisen = [p['dosya'] for p in sira['parcalar']
               if _ozet(_oku(os.path.join(PARCA_DIZINI, p['dosya']))) != p['sha256']]
    if yeni == mevcut:
        print('Değişiklik yok; main.dart aynı.')
    else:
        _yaz(os.path.join(PARCA_DIZINI, YEDEK_DOSYASI), mevcut)
        _yaz(MAIN_DART, yeni)
        print('main.dart yeniden üretildi (%d bayt). Değişen parçalar: %s'
              % (len(yeni), ', '.join(degisen) or '-'))
    # Bir sonraki birleştirme için referansı güncelle; parçalarla çalışmaya
    # devam edilebilir.
    sira['kaynak_sha256'] = _ozet(yeni)
    for p in sira['parcalar']:
        p['sha256'] = _ozet(_oku(os.path.join(PARCA_DIZINI, p['dosya'])))
    with open(sira_yolu, 'w', encoding='utf-8') as f:
        json.dump(sira, f, ensure_ascii=False, indent=2)
    if args.temizle:
        shutil.rmtree(PARCA_DIZINI)
        print('Parça klasörü silindi.')
    return 0


def komut_temizle(_):
    if os.path.isdir(PARCA_DIZINI):
        shutil.rmtree(PARCA_DIZINI)
        print('Silindi: %s' % PARCA_DIZINI)
    else:
        print('Parça klasörü zaten yok.')
    return 0


def komut_dogrula(_):
    veri = _oku(MAIN_DART)
    parcalar = _parcalar(veri)
    tekrar = b''.join(p[4] for p in parcalar)
    if tekrar != veri:
        print('HATA: böl+birleştir kaynağı aynen üretmedi!')
        return 1
    print('Tamam: %d parça, %d bayt, bayt bayt aynı.' % (len(parcalar), len(veri)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    alt = ap.add_subparsers(dest='komut', required=True)
    alt.add_parser('liste', help='bölümleri listele')
    b = alt.add_parser('bol', help='main.dart\'ı parçalara ayır')
    b.add_argument('--zorla', action='store_true', help='dolu parça klasörünü sil')
    m = alt.add_parser('birlestir', help='parçalardan main.dart üret')
    m.add_argument('--zorla', action='store_true',
                   help='main.dart dışarıdan değişmiş olsa bile yaz')
    m.add_argument('--temizle', action='store_true',
                   help='birleştirdikten sonra parça klasörünü sil')
    alt.add_parser('temizle', help='parça klasörünü sil')
    alt.add_parser('dogrula', help='bölme/birleştirme bayt bayt aynı mı')
    args = ap.parse_args(argv)
    return {
        'liste': komut_liste, 'bol': komut_bol, 'birlestir': komut_birlestir,
        'temizle': komut_temizle, 'dogrula': komut_dogrula,
    }[args.komut](args)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
