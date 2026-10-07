import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:re_editor/re_editor.dart' as re;

void main() {
  testWidgets('30 taps map to exact columns in a 20,000-line document',
      (tester) async {
    const fontSize = 14.0;
    const line = 'abcdefghij';
    final lines = List<String>.generate(
      20000,
      (index) => line,
    );
    final document = re.CodeLineEditingController.fromText(lines.join('\n'));
    final scroll = re.CodeScrollController();
    re.CodeIndicatorValueNotifier? indicator;
    const style = TextStyle(fontFamily: 'monospace', fontSize: fontSize);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: re.CodeEditor(
          controller: document,
          scrollController: scroll,
          autofocus: false,
          wordWrap: false,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          style: const re.CodeEditorStyle(
            fontFamily: 'monospace',
            fontSize: fontSize,
            fontHeight: 1.4,
          ),
          indicatorBuilder: (_, __, ___, notifier) {
            indicator = notifier;
            return const SizedBox.shrink();
          },
        ),
      ),
    ));
    await tester.pumpAndSettle();

    final targetLines = <int>{1, 10000, 20000};
    final random = Random(42);
    while (targetLines.length < 30) {
      targetLines.add(random.nextInt(20000) + 1);
    }

    for (final targetLine in targetLines) {
      final column = random.nextInt(line.length + 1);
      scroll.makeVisible(
        re.CodeLinePosition(index: targetLine - 1, offset: column),
      );
      await tester.pumpAndSettle();
      final paragraphs = indicator?.value?.paragraphs ?? const [];
      re.CodeLineRenderParagraph? paragraph;
      for (final visible in paragraphs) {
        if (visible.index == targetLine - 1) {
          paragraph = visible;
          break;
        }
      }
      if (paragraph == null) {
        final lineHeight =
            paragraphs.isNotEmpty ? paragraphs.first.height : fontSize * 1.4;
        final position = scroll.verticalScroller.position;
        final targetOffset = ((targetLine - 1) * lineHeight)
            .clamp(0.0, position.maxScrollExtent);
        scroll.verticalScroller.jumpTo(targetOffset);
        await tester.pumpAndSettle();
        for (final visible in indicator?.value?.paragraphs ?? const []) {
          if (visible.index == targetLine - 1) {
            paragraph = visible;
            break;
          }
        }
      }
      expect(paragraph, isNotNull, reason: 'line $targetLine became visible');
      final measure = TextPainter(
        text: const TextSpan(text: line, style: style),
        textDirection: TextDirection.ltr,
        textScaler: TextScaler.noScaling,
      )..layout();
      final x = 8 +
          measure
              .getOffsetForCaret(TextPosition(offset: column), Rect.zero)
              .dx +
          1;
      final paragraphPosition = paragraph!.getPosition(
        Offset(x - paragraph.offset.dx, paragraph.height / 2),
      );
      expect(paragraphPosition.offset, column,
          reason: 'paragraph x mapping for line $targetLine');
      final editorOrigin = tester.getTopLeft(find.byType(re.CodeEditor));
      final yWithinLine = targetLine.isEven ? 2.0 : paragraph.height - 2;
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 350)),
      );
      await tester.tapAt(
        editorOrigin + Offset(x, paragraph.top + yWithinLine),
      );
      await tester.pumpAndSettle();
      expect(document.selection.baseIndex, targetLine - 1,
          reason: 'line $targetLine');
      expect(document.selection.baseOffset, column,
          reason: 'column $column on line $targetLine');
      measure.dispose();
    }

    scroll.dispose();
    document.dispose();
  });
}
