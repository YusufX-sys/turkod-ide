import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/editor/editor_indentation.dart';

void main() {
  test('blank lines inherit the next non-empty line indentation', () {
    const lines = ['    first', '', '', '\t second', '  last'];

    expect(EditorIndentGuides.visibleLevels(lines, 0, lines.length),
        [1, 1, 1, 1, 0]);
  });

  test('tabs advance to the configured tab stop', () {
    expect(EditorIndentGuides.indentColumns('\t\tvalue', tabWidth: 4), 8);
    expect(EditorIndentGuides.indentColumns(' \t value', tabWidth: 4), 5);
    expect(EditorIndentGuides.visibleLevels(['\t\tvalue'], 0, 1), [2]);
  });
}
