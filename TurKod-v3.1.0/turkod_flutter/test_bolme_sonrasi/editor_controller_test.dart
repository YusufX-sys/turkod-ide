import 'dart:math';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:re_editor/re_editor.dart' as re;
import 'package:turkod_ide/editor/editor_controller.dart';

void main() {
  test('normalizes line endings and maps offsets both ways', () {
    final document =
        re.CodeLineEditingController.fromText('first\r\nsecond\rthird');
    final controller = EditorController(document);

    expect(controller.text, 'first\nsecond\nthird');
    expect(EditorController.positionForOffset(controller.text, 6), (1, 0));
    expect(EditorController.positionForOffset(controller.text, 13), (2, 0));
    expect(EditorController.offsetForPosition(controller.text, 2, 2), 15);

    document.dispose();
  });

  test('round-trips 30 positions across a 20,000-line document', () {
    final lines = List<String>.generate(
      20000,
      (index) => 'satir-${index + 1}: İğde\tdeğer',
    );
    final text = lines.join('\n');
    final document = re.CodeLineEditingController.fromText(text);
    final controller = EditorController(document);
    final random = Random(42);
    final targetLines = <int>{1, 10000, 20000};
    while (targetLines.length < 30) {
      targetLines.add(random.nextInt(20000) + 1);
    }

    for (final line in targetLines) {
      final lineText = lines[line - 1];
      final column = random.nextInt(lineText.length + 1);
      final offset = EditorController.offsetForPosition(text, line - 1, column);
      controller.selection = TextSelection.collapsed(offset: offset);
      expect(controller.selection.baseOffset, offset);
      expect(document.selection.baseIndex, line - 1);
      expect(document.selection.baseOffset, column);
    }

    document.dispose();
  });

  test('formatted edit preserves composing and undoes in one step', () {
    final document = re.CodeLineEditingController.fromText('ab');
    final controller = EditorController(document);
    final oldValue = TextEditingValue(
      text: 'ab',
      selection: const TextSelection.collapsed(offset: 1),
    );
    controller.value = TextEditingValue(
      text: 'a()b',
      selection: const TextSelection.collapsed(offset: 2),
      composing: const TextRange(start: 1, end: 3),
    );

    expect(controller.text, 'a()b');
    expect(controller.value.composing, const TextRange(start: 1, end: 3));
    expect(document.canUndo, isTrue);
    document.undo();
    expect(controller.text, oldValue.text);

    document.dispose();
  });
}
