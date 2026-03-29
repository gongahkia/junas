import 'package:flutter/material.dart';

import '../models/provider_models.dart';

class ProviderDescriptor {
  const ProviderDescriptor({
    required this.id,
    required this.label,
    required this.icon,
    required this.accentColor,
    required this.roomSupported,
    required this.soloSupported,
    required this.surfaceHierarchy,
  });

  final String id;
  final String label;
  final IconData icon;
  final Color accentColor;
  final bool roomSupported;
  final bool soloSupported;
  final String surfaceHierarchy;

  ProviderCapability toCapability() {
    return ProviderCapability(
      id: id,
      label: label,
      roomSupported: roomSupported,
      soloSupported: soloSupported,
      surfaceHierarchy: surfaceHierarchy,
      authFields: const <ProviderAuthField>[],
    );
  }
}

const List<ProviderDescriptor> providerRegistry = <ProviderDescriptor>[
  ProviderDescriptor(
    id: 'kilter',
    label: 'Kilter',
    icon: Icons.grid_view_rounded,
    accentColor: Color(0xFF23533F),
    roomSupported: true,
    soloSupported: true,
    surfaceHierarchy: 'board',
  ),
  ProviderDescriptor(
    id: 'crux',
    label: 'Crux',
    icon: Icons.layers_outlined,
    accentColor: Color(0xFFC7682F),
    roomSupported: true,
    soloSupported: true,
    surfaceHierarchy: 'hierarchy',
  ),
  ProviderDescriptor(
    id: 'cornifer',
    label: 'Cornifer',
    icon: Icons.hub_outlined,
    accentColor: Color(0xFF6B4E16),
    roomSupported: true,
    soloSupported: true,
    surfaceHierarchy: 'hierarchy',
  ),
];

ProviderDescriptor providerDescriptorFor(String providerId) {
  for (final ProviderDescriptor descriptor in providerRegistry) {
    if (descriptor.id == providerId) {
      return descriptor;
    }
  }
  return ProviderDescriptor(
    id: providerId,
    label: providerId.toUpperCase(),
    icon: Icons.extension_outlined,
    accentColor: const Color(0xFF475569),
    roomSupported: true,
    soloSupported: true,
    surfaceHierarchy: 'board',
  );
}

String providerLabel(String providerId) =>
    providerDescriptorFor(providerId).label;
