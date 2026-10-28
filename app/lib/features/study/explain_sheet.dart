import 'package:flutter/material.dart';

import '../../domain/explain_prompt.dart';

Future<void> showExplainSheet(BuildContext context, String explanation) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) {
      final maxH = MediaQuery.sizeOf(ctx).height * 0.75;
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 8, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Wyjaśnienie',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(ctx),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const Text(
                'Informacja edukacyjna — nie stanowi porady prawnej.',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
              const SizedBox(height: 12),
              ConstrainedBox(
                constraints: BoxConstraints(maxHeight: maxH),
                child: SingleChildScrollView(
                  child: Text(
                    explanation,
                    style: TextStyle(
                      fontSize: 16,
                      color: explanation.trimLeft().startsWith(explainWarningPrefix)
                          ? Theme.of(ctx).colorScheme.error
                          : null,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}
