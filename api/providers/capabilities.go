package providers

type AuthField struct {
	Key          string `json:"key"`
	Label        string `json:"label"`
	Type         string `json:"type"`
	Placeholder  string `json:"placeholder,omitempty"`
	AutoComplete string `json:"autocomplete,omitempty"`
}

type Capability struct {
	ID               ProviderID  `json:"id"`
	Label            string      `json:"label"`
	RoomSupported    bool        `json:"room_supported"`
	SoloSupported    bool        `json:"solo_supported"`
	SurfaceHierarchy string      `json:"surface_hierarchy"`
	AuthFields       []AuthField `json:"auth_fields"`
}

func SupportedCapabilities() []Capability {
	providerIDs := Supported()
	capabilities := make([]Capability, 0, len(providerIDs))
	for _, providerID := range providerIDs {
		if capability, ok := CapabilityForProvider(providerID); ok {
			capabilities = append(capabilities, capability)
		}
	}

	return capabilities
}

func CapabilityForProvider(providerID ProviderID) (Capability, bool) {
	switch providerID {
	case ProviderKilter:
		return Capability{
			ID:               ProviderKilter,
			Label:            "Kilter",
			RoomSupported:    true,
			SoloSupported:    true,
			SurfaceHierarchy: "board",
			AuthFields:       []AuthField{},
		}, true
	case ProviderCrux:
		return Capability{
			ID:               ProviderCrux,
			Label:            "Crux",
			RoomSupported:    true,
			SoloSupported:    true,
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
			SoloSupported:    true,
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

func RequiresProviderSecret(providerID ProviderID) bool {
	capability, ok := CapabilityForProvider(providerID)
	if !ok {
		return true
	}

	return len(capability.AuthFields) > 0
}

func DefaultConnectionState(providerID ProviderID) ProviderConnectionState {
	state := ProviderConnectionState{ProviderID: providerID}
	if !RequiresProviderSecret(providerID) {
		state.Connected = true
	}

	return state
}
