import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../app_info.dart';

const contactName = 'Lukasz';
const contactEmail = 'acardo1985@gmail.com';

Future<void> showContactDialog(BuildContext context) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Kontakt'),
      content: const SelectableText(
        '$contactName\n$contactEmail',
        style: TextStyle(fontSize: 16),
      ),
      actions: [
        TextButton(
          onPressed: () async {
            await Clipboard.setData(const ClipboardData(text: contactEmail));
            if (ctx.mounted) {
              ScaffoldMessenger.of(ctx).showSnackBar(
                const SnackBar(content: Text('Skopiowano adres e-mail')),
              );
            }
          },
          child: const Text('Kopiuj e-mail'),
        ),
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Zamknij')),
      ],
    ),
  );
}

class AppDrawer extends StatelessWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          const DrawerHeader(
            decoration: BoxDecoration(color: Color(0xFF1565C0)),
            child: Align(
              alignment: Alignment.bottomLeft,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    appName,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 2),
                  Text(
                    'wersja $appVersionName',
                    style: TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.home),
            title: const Text('Start'),
            onTap: () {
              Navigator.pop(context);
              context.go('/');
            },
          ),
          ListTile(
            leading: const Icon(Icons.local_fire_department),
            title: const Text('Powtórka trudnych'),
            onTap: () {
              Navigator.pop(context);
              context.push('/hardest');
            },
          ),
          ListTile(
            leading: const Icon(Icons.bar_chart),
            title: const Text('Statystyki'),
            onTap: () {
              Navigator.pop(context);
              context.push('/stats');
            },
          ),
          ListTile(
            leading: const Icon(Icons.slideshow),
            title: const Text('Slideshow'),
            onTap: () {
              Navigator.pop(context);
              context.push('/slideshow');
            },
          ),
          ListTile(
            leading: const Icon(Icons.storage),
            title: const Text('Baza Pytań'),
            onTap: () {
              Navigator.pop(context);
              context.push('/database');
            },
          ),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Ustawienia'),
            onTap: () {
              Navigator.pop(context);
              context.push('/settings');
            },
          ),
          ListTile(
            leading: const Icon(Icons.menu_book_outlined),
            title: const Text('Manual'),
            onTap: () {
              Navigator.pop(context);
              context.push('/manual');
            },
          ),
          ListTile(
            leading: const Icon(Icons.mail_outline),
            title: const Text('Kontakt'),
            onTap: () {
              Navigator.pop(context);
              showContactDialog(context);
            },
          ),
        ],
      ),
    );
  }
}
