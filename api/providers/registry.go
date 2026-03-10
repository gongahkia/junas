package providers

import (
	"fmt"
	"slices"
	"sync"
)

var (
	registryMu sync.RWMutex
	registry   = map[ProviderID]Provider{}
)

func Register(provider Provider) {
	registryMu.Lock()
	defer registryMu.Unlock()
	registry[provider.ID()] = provider
}

func MustRegister(provider Provider) {
	Register(provider)
}

func Get(providerID ProviderID) (Provider, error) {
	registryMu.RLock()
	defer registryMu.RUnlock()

	provider, ok := registry[providerID]
	if !ok {
		return nil, fmt.Errorf("unsupported provider %q", providerID)
	}

	return provider, nil
}

func Supported() []ProviderID {
	registryMu.RLock()
	defer registryMu.RUnlock()

	providers := make([]ProviderID, 0, len(registry))
	for providerID := range registry {
		providers = append(providers, providerID)
	}

	slices.Sort(providers)

	return providers
}
