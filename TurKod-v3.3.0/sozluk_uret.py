"""TurKod_Sozluk.txt dosyasindan site icin Markdown sozluk sayfasi uretir."""
import ast
import re
from pathlib import Path

KAYNAK = Path(r"turkod_ide/TurKod_Sozluk.txt")  # kendi yoluna gore duzelt
HEDEF = Path("sozluk.md")

icerik = KAYNAK.read_text(encoding="utf-8")
bas = icerik.find("{")
son = icerik.rfind("}") + 1
sozluk = ast.literal_eval(icerik[bas:son])

satirlar = [
    "---",
    "title: Sözlük",
    "description: TürKod anahtar kelimelerinin ve fonksiyonlarının tam listesi.",
    "---",
    "",
    "Bu sayfa `TurKod_Sozluk.txt` dosyasından otomatik üretilir. Elle düzenlemeyin.",
    "",
    "Türkçe karakterli kelimeler Türkçe karakter olmadan da yazılabilir: "
    "`yazdır` yerine `yazdir`, `akış` yerine `akis` gibi. Bu yazımlar "
    "tabloda ayrıca listelenmez.",
    "",
    "| TürKod | Python |",
    "|---|---|",
]

for desen, hedef in sorted(sozluk.items()):
    kelime = desen.replace(r"\b", "").strip('"').strip("'")
    satirlar.append(f"| `{kelime}` | `{hedef}` |")

HEDEF.write_text("\n".join(satirlar), encoding="utf-8")
print(f"{len(sozluk)} kelime yazildi -> {HEDEF}")
