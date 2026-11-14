import 'package:flutter_test/flutter_test.dart';
import 'package:turkod_ide/main.dart' as app;

void main() {
  test('görev ataması açılır liste değerine çevrilip geri okunur', () {
    const a = app.AiAtama('groq', 'llama:3.3-70b');
    expect(app.AiAtama.anahtardan(a.anahtar), a);
    expect(app.AiAtama.anahtardan(''), isNull);
    expect(app.AiAtama.coz({'saglayici': 'yerel', 'model': 'm.gguf'})?.yerel, isTrue);
    expect(app.AiAtama.coz({'saglayici': 'groq', 'model': ''}), isNull);
  });

  test('bağlı sağlayıcılar: anahtarı ya da listede modeli olanlar', () {
    expect(
        app.bagliSaglayicilariBul({'groq': 'k', 'openai': '', 'yerel': 'x'}, const [
          app.AiAtama('deepseek', 'd'),
          app.AiAtama('groq', 'g'),
          app.AiAtama('yerel', 'm.gguf'),
        ]),
        ['groq', 'deepseek']);
  });

  test('bağlantı hataları anlaşılır Türkçeye çevrilir', () {
    expect(
        app.baglantiHatasiAciklamasi(
            "HTTPSConnectionPool(host='api.groq.com'): Max retries exceeded "
            '(NameResolutionError ... getaddrinfo failed)'),
        contains('internet'));
    expect(app.baglantiHatasiAciklamasi('HTTP 401: Invalid API Key'),
        contains('API anahtarı'));
  });

  test('model etiketi "Sağlayıcı • Model" biçimindedir', () {
    final s = app.SettingsProvider(app.BackendService());
    expect(s.atamaEtiketi(const app.AiAtama('yerel', 'qwen.gguf')),
        'TürKod Yerel • qwen.gguf');
    expect(s.atamaEtiketi(const app.AiAtama('groq', 'llama-3.3-70b-versatile')),
        'groq • llama-3.3-70b-versatile');
  });
}
