# main.dart bölündükten sonra etkinleştirilecek testler

Bu testler henüz var olmayan `lib/editor/` katmanını tanımlar:

| Test | Beklediği dosya / sınıf |
|---|---|
| `editor_controller_test.dart` | `lib/editor/editor_controller.dart` → `EditorController` |
| `editor_formatter_test.dart` | `lib/editor/editor_formatter.dart` → `EditorFormatter` |
| `editor_indentation_test.dart` | `lib/editor/editor_indentation.dart` → `EditorIndentGuides` |
| `editor_search_test.dart` | `lib/editor/editor_search.dart` → `EditorSearch` |

Bu dosyalar `test/` içindeyken derlenemedikleri için `flutter test` her seferinde
kırmızı çıkıyordu. Editör kodu `main.dart`'tan `lib/editor/` altına taşındığında
bu testleri `test/` klasörüne geri koyun.
