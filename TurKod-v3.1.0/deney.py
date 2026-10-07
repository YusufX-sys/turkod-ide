from turkod_ide.dictionary import SOZLUK, SOZLUK_TXT_YOLU

print("OKUNAN SOZLUK DOSYASI:", SOZLUK_TXT_YOLU)
print("yeni_sayfa:", SOZLUK.get(r"\byeni_sayfa\b"))
print("dikdörtgen_çiz:", SOZLUK.get(r"\bdikdörtgen_çiz\b"))
print("dolgu:", SOZLUK.get(r"\bdolgu\b"))
