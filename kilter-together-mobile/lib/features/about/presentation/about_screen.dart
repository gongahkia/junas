import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'About Kilter Together',
      subtitle:
          'Why this project exists, and what it is trying to make easier for group board sessions.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Hi, I\'m Gabriel.',
                style: Theme.of(context).textTheme.displayLarge,
              ),
              const SizedBox(height: 16),
              const Text(
                'I built Kilter Together because I wanted board sessions to feel more collaborative than one person scrolling through climbs while everyone else waits to ask for a turn.',
              ),
              const SizedBox(height: 14),
              const Text(
                'The goal is simple: one host connects the provider account, opens a room, and the whole group can vote, queue climbs, and session together from their own phones.',
              ),
              const SizedBox(height: 14),
              const Text(
                'I like software that gets out of the way. This app is meant to make shared decisions around a board feel lighter, clearer, and less awkward.',
              ),
              const SizedBox(height: 18),
              Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: const Color(0xFFF4FBF8),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: const Color(0xFFD7ECE6)),
                ),
                padding: const EdgeInsets.all(18),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'Project links',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 10),
                    SelectableText('https://github.com/gongahkia/kilter-together'),
                    SizedBox(height: 8),
                    SelectableText('https://gabrielongzm.com'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const Text('See you at the gym.'),
            ],
          ),
        ),
      ),
    );
  }
}
