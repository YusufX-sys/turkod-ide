import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:turkod_ide/main.dart' as app;

class _LoadedSettingsProvider extends app.SettingsProvider {
  _LoadedSettingsProvider(super.backend);

  @override
  bool get loaded => true;
}

void main() {
  testWidgets('settings dropdown uses a visible Material surface',
      (tester) async {
    final backend = app.BackendService();
    final settings = _LoadedSettingsProvider(backend);
    addTearDown(() {
      settings.dispose();
      backend.dispose();
    });

    await tester.pumpWidget(MultiProvider(
      providers: [
        Provider<app.BackendService>.value(value: backend),
        ChangeNotifierProvider<app.SettingsProvider>.value(value: settings),
      ],
      child: MaterialApp(
        theme: app.AppThemeRegistry.build('Modern Koyu'),
        home: const app.SettingsPage(),
      ),
    ));

    final dropdown = find.byType(DropdownButtonFormField<String>).first;
    await tester.ensureVisible(dropdown);
    await tester.tap(dropdown);
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });
}