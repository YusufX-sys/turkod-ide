import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/editor/editor_search.dart';

void main() {
  test('case-insensitive Turkish matches retain original offsets', () {
    const text = 'İstanbul ISPARTA ığdır';

    final istanbul = EditorSearch.findMatches(text, 'istanbul');
    final isparta = EditorSearch.findMatches(text, 'ısparta');
    final igdir = EditorSearch.findMatches(text, 'ığdır');

    expect(istanbul.map((match) => [match.start, match.end]), [
      [0, 8]
    ]);
    expect(isparta.map((match) => [match.start, match.end]), [
      [9, 16]
    ]);
    expect(igdir.map((match) => [match.start, match.end]), [
      [17, 22]
    ]);
    expect(EditorSearch.findMatches(text, 'i').length, 1);
  });

  test('whole-word search uses original text boundaries', () {
    const text = "Ali'nin alidesi ali";

    final matches = EditorSearch.findMatches(text, 'ali', wholeWord: true);

    expect(matches.map((match) => [match.start, match.end]), [
      [0, 3],
      [16, 19]
    ]);
  });

  test('native search regex preserves Turkish case pairs and word bounds', () {
    const text = "İstanbul ISPARTA ığdır Ali'nin";
    final pattern = EditorSearch.regexPattern('istanbul');
    final ispartaPattern = EditorSearch.regexPattern('ısparta');
    final wholeWordPattern = EditorSearch.regexPattern('ali', wholeWord: true);

    expect(RegExp(pattern, unicode: true).firstMatch(text)?.start, 0);
    expect(RegExp(ispartaPattern, unicode: true).firstMatch(text)?.start, 9);
    expect(
      RegExp(wholeWordPattern, unicode: true).firstMatch(text)?.start,
      23,
    );
  });
}
