import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/editor/editor_formatter.dart';

void main() {
  TextEditingValue caret(String text, int offset) => TextEditingValue(
        text: text,
        selection: TextSelection.collapsed(offset: offset),
      );

  TextEditingValue type(TextEditingValue value, String character) {
    final selection = value.selection;
    final text = value.text.replaceRange(
      selection.start,
      selection.end,
      character,
    );
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(
        offset: selection.start + character.length,
      ),
    );
  }

  for (final pair in EditorFormatter.pairs.entries) {
    test('autocloses ${pair.key} and overtypes ${pair.value}', () {
      final opened = EditorFormatter.formatChange(
        caret('', 0),
        type(caret('', 0), pair.key),
      );
      expect(opened?.text, '${pair.key}${pair.value}');
      expect(opened?.selection.baseOffset, pair.key.length);

      final skipped = EditorFormatter.formatChange(
        opened!,
        type(opened, pair.value),
      );
      expect(skipped?.text, opened.text);
      expect(skipped?.selection.baseOffset, 2);
    });

    test('surrounds selection with ${pair.key}', () {
      final oldValue = TextEditingValue(
        text: 'abc',
        selection: const TextSelection(baseOffset: 1, extentOffset: 2),
      );
      final formatted = EditorFormatter.formatChange(
        oldValue,
        type(oldValue, pair.key),
      );
      expect(formatted?.text, 'a${pair.key}b${pair.value}c');
      expect(formatted?.selection,
          const TextSelection(baseOffset: 2, extentOffset: 3));
    });
  }

  test('backspace removes an empty pair', () {
    final oldValue = caret('()', 1);
    final newValue = caret(')', 0);

    final formatted = EditorFormatter.formatChange(oldValue, newValue);

    expect(formatted?.text, '');
    expect(formatted?.selection.baseOffset, 0);
  });

  test('does not close before a word or after a quote apostrophe', () {
    expect(
      EditorFormatter.formatChange(
          caret('word', 0), type(caret('word', 0), '(')),
      isNull,
    );
    expect(
      EditorFormatter.formatChange(
        caret('Ali', 3),
        type(caret('Ali', 3), "'"),
      ),
      isNull,
    );
  });

  test('does not auto-format while IME composition is active', () {
    final oldValue = TextEditingValue(
      text: 'a',
      selection: const TextSelection.collapsed(offset: 1),
      composing: const TextRange(start: 0, end: 1),
    );

    expect(
      EditorFormatter.formatChange(oldValue, type(oldValue, '(')),
      isNull,
    );
  });

  test('Enter indents after colon and expands tabs consistently', () {
    final value = caret('\tif ready:', 10);

    final formatted = EditorFormatter.formatEnter(value, tabWidth: 4);

    expect(formatted.text, '\tif ready:\n        ');
    expect(formatted.selection.baseOffset, formatted.text.length);
  });

  test('Tab uses configured width and Shift+Tab restores selected lines', () {
    final original = TextEditingValue(
      text: '  first\n\tsecond\nthird',
      selection: const TextSelection(baseOffset: 0, extentOffset: 21),
    );

    final indented = EditorFormatter.formatIndent(
      original,
      outdent: false,
      tabWidth: 4,
    );
    final outdented = EditorFormatter.formatIndent(
      indented,
      outdent: true,
      tabWidth: 4,
    );

    expect(indented.text, '      first\n    \tsecond\n    third');
    expect(outdented.text, original.text);
    expect(outdented.selection.isValid, isTrue);
  });

  test('single-line Tab inserts four spaces and Shift+Tab removes them', () {
    final original = caret('value', 2);
    final indented = EditorFormatter.formatIndent(original, outdent: false);
    final outdented = EditorFormatter.formatIndent(indented, outdent: true);

    expect(indented.text, '    value');
    expect(outdented.text, 'value');
  });
}
