package providers

type AuthField struct {
	Key          string `json:"key"`
	Label        string `json:"label"`
	Type         string `json:"type"`
	Placeholder  string `json:"placeholder,omitempty"`
	AutoComplete string `json:"autocomplete,omitempty"`
}

type Capability struct {
	ID               ProviderID   `json:"id"`
	Label            string       `json:"label"`
	RoomSupported    bool         `json:"room_supported"`
	SoloSupported    bool         `json:"solo_supported"`
	SurfaceHierarchy string       `json:"surface_hierarchy"`
	AuthFields       []AuthField  `json:"auth_fields"`
}

func SupportedCapabilities() []Capability {
	providerIDs := Supported()
	capabilities := make([]Capability, 0, len(providerIDs))
	for _, providerID := range providerIDs {
		if capability, ok := capabilityForProvider(providerID); ok {
			capabilities = append(capabilities, capability)
		}
	}

	return capabilities
}

func capabilityForProvider(providerID ProviderID) (Capability, bool) {
	switch providerID {
	case ProviderKilter:
		return Capability{
			ID:               ProviderKilter,
			Label:            "Kilter",
			RoomSupported:    true,
			SoloSupported:    true,
			SurfaceHierarchy: "board",
			AuthFields: []AuthField{
				{
					Key:          "username",
					Label:        "Kilter username",
					Type:         "text",
					Placeholder:  "Kilter username",
					AutoComplete: "username",
				},
				{
					Key:          "password",
					Label:        "Kilter password",
					Type:         "password",
					Placeholder:  "Kilter password",
					AutoComplete: "current-password",
				},
			},
		}, true
	case ProviderCrux:
		return Capability{
			ID:               ProviderCrux,
			Label:            "Crux",
			RoomSupported:    true,
			SoloSupported:    false,
			SurfaceHierarchy: "nested",
			AuthFields: []AuthField{
				{
					Key:         "token",
					Label:       "Crux API token",
					Type:        "password",
					Placeholder: "Crux API token or Bearer value",
				},
			},
		}, true
	case ProviderTest:
		return Capability{
			ID:               ProviderTest,
			Label:            "Test provider",
			RoomSupported:    true,
			SoloSupported:    false,
			SurfaceHierarchy: "nested",
			AuthFields: []AuthField{
				{
					Key:         "token",
					Label:       "Test provider token",
					Type:        "text",
					Placeholder: "test-token",
				},
			},
		}, true
	default:
		return Capability{}, false
	}
}
