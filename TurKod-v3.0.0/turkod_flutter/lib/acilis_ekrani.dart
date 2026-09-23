import 'package:flutter/material.dart';

/// Backend hazır olana kadar gösterilen açılış ekranı (önce backend, sonra arayüz).
/// Backend açılamazsa hatayı ve iki düğmeyi gösterir: "Yeniden dene", "Yine de aç".
class AcilisEkrani extends StatelessWidget {
  final String? hata;
  final VoidCallback onYenidenDene;
  final VoidCallback onYineDeAc;

  const AcilisEkrani({
    super.key,
    this.hata,
    required this.onYenidenDene,
    required this.onYineDeAc,
  });

  @override
  Widget build(BuildContext context) {
    const yesil = Color(0xFF2ECC71);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'TürKod IDE',
      theme: ThemeData.dark(useMaterial3: true),
      home: Scaffold(
        backgroundColor: const Color(0xFF0F172A),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'TürKod',
                    style: TextStyle(
                      fontSize: 34,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (hata == null) ...[
                    const Text(
                      'Backend başlatılıyor...',
                      style: TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 16),
                    const ClipRRect(
                      borderRadius: BorderRadius.all(Radius.circular(4)),
                      child: LinearProgressIndicator(
                        minHeight: 8,
                        color: yesil,
                        backgroundColor: Color(0x1FFFFFFF),
                      ),
                    ),
                  ] else ...[
                    const Icon(Icons.error_outline,
                        color: Colors.orange, size: 40),
                    const SizedBox(height: 12),
                    Text(
                      hata!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      r'Ayrıntı: %LOCALAPPDATA%\TurKod\backend.log',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white38, fontSize: 12),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        FilledButton(
                          onPressed: onYenidenDene,
                          child: const Text('Yeniden dene'),
                        ),
                        const SizedBox(width: 12),
                        OutlinedButton(
                          onPressed: onYineDeAc,
                          child: const Text('Yine de aç'),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
