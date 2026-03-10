import { config } from "@/config";
import type { ProviderCapability, ProviderId } from "@/types";

const BASE_CAPABILITIES: ProviderCapability[] = [
  {
    id: "kilter",
    label: "Kilter",
    room_supported: true,
    solo_supported: true,
    surface_hierarchy: "board",
    auth_fields: [
      {
        key: "username",
        label: "Kilter username",
        type: "text",
        placeholder: "Kilter username",
        autocomplete: "username",
      },
      {
        key: "password",
        label: "Kilter password",
        type: "password",
        placeholder: "Kilter password",
        autocomplete: "current-password",
      },
    ],
  },
  {
    id: "crux",
    label: "Crux",
    room_supported: true,
    solo_supported: false,
    surface_hierarchy: "nested",
    auth_fields: [
      {
        key: "token",
        label: "Crux API token",
        type: "password",
        placeholder: "Crux API token or Bearer value",
      },
    ],
  },
];

export function fallbackProviderCapabilities(): ProviderCapability[] {
  if (!config.app.enableTestProvider) {
    return BASE_CAPABILITIES;
  }

  return [
    ...BASE_CAPABILITIES,
    {
      id: "test",
      label: "Test provider",
      room_supported: true,
      solo_supported: false,
      surface_hierarchy: "nested",
      auth_fields: [
        {
          key: "token",
          label: "Test provider token",
          type: "text",
          placeholder: "test-token",
        },
      ],
    },
  ];
}

export function getProviderCapability(
  providerId: ProviderId,
  capabilities: ProviderCapability[]
): ProviderCapability | undefined {
  return capabilities.find((capability) => capability.id === providerId);
}

export function getRoomProviderCapabilities(
  capabilities: ProviderCapability[]
): ProviderCapability[] {
  return capabilities.filter((capability) => capability.room_supported);
}

export function getProviderLabel(
  providerId: ProviderId,
  capabilities: ProviderCapability[]
): string {
  return getProviderCapability(providerId, capabilities)?.label ?? providerId;
}

export function usesNestedSurfaceHierarchy(
  providerId: ProviderId,
  capabilities: ProviderCapability[]
): boolean {
  return (
    getProviderCapability(providerId, capabilities)?.surface_hierarchy === "nested"
  );
}
