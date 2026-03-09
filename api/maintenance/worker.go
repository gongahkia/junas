package maintenance

import (
	"context"
	"log/slog"
	"time"

	"github.com/lczm/kilter-together/api/observability"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
)

const (
	roomSweepInterval    = 5 * time.Minute
	sessionSweepInterval = 5 * time.Minute
	cacheSweepInterval   = time.Hour
)

type RoomMaintainer interface {
	CloseExpiredRooms(ctx context.Context) error
	PruneExpiredSessions(ctx context.Context) error
}

func Start(ctx context.Context, service RoomMaintainer) {
	runJob(ctx, "rooms", roomSweepInterval, service.CloseExpiredRooms)
	runJob(ctx, "sessions", sessionSweepInterval, service.PruneExpiredSessions)
	runJob(ctx, "provider_cache", cacheSweepInterval, func(inner context.Context) error {
		_, err := providers.PruneExpiredCache(inner)
		return err
	})
}

func runJob(ctx context.Context, job string, interval time.Duration, run func(context.Context) error) {
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			if err := run(ctx); err != nil {
				observability.RecordMaintenanceRun(job, err)
				slog.Warn("maintenance job failed", "job", job, "error", err)
			} else {
				observability.RecordMaintenanceRun(job, nil)
			}

			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
			}
		}
	}()
}

var _ RoomMaintainer = (*rooms.Service)(nil)
