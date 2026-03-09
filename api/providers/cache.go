package providers

import (
	"context"
	"fmt"
	"time"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/observability"
)

func RecordCacheHit(providerID ProviderID) {
	observability.RecordProviderCache(string(providerID), "hit")
}

func RecordCacheMiss(providerID ProviderID) {
	observability.RecordProviderCache(string(providerID), "miss")
}

func RecordCacheWrite(providerID ProviderID) {
	observability.RecordProviderCache(string(providerID), "write")
}

func RecordCachePrune(providerID ProviderID, count int64) {
	if count > 0 {
		observability.RecordProviderCache(string(providerID), "prune")
	}
}

func PruneExpiredCache(ctx context.Context) (int64, error) {
	if config.AppDB == nil {
		return 0, nil
	}

	result := config.AppDB.WithContext(ctx).
		Where("expires_at <= ?", time.Now().UTC()).
		Delete(&ProviderCacheEntry{})
	if result.Error != nil {
		return 0, fmt.Errorf("prune provider cache: %w", result.Error)
	}
	RecordCachePrune(ProviderCrux, result.RowsAffected)
	return result.RowsAffected, nil
}
