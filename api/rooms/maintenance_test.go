package rooms

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/lczm/kilter-together/api/config"
)

func newMaintenanceTestService(t *testing.T) *Service {
	t.Helper()

	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		AppDBPath: appDBPath,
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app db: %v", err)
	}

	service := NewService()
	if err := service.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app db: %v", err)
	}

	return service
}

func TestCloseExpiredRoomsClosesInactiveRooms(t *testing.T) {
	service := newMaintenanceTestService(t)

	expiredRoom := Room{
		Slug:         "expired-room",
		ProviderID:   "test",
		Status:       roomStatusOpen,
		Version:      1,
		LastActiveAt: time.Now().UTC().Add(-roomExpiryWindow - time.Hour),
	}
	activeRoom := Room{
		Slug:         "active-room",
		ProviderID:   "test",
		Status:       roomStatusOpen,
		Version:      1,
		LastActiveAt: time.Now().UTC(),
	}
	if err := config.AppDB.Create(&expiredRoom).Error; err != nil {
		t.Fatalf("create expired room: %v", err)
	}
	if err := config.AppDB.Create(&activeRoom).Error; err != nil {
		t.Fatalf("create active room: %v", err)
	}

	if err := service.CloseExpiredRooms(context.Background()); err != nil {
		t.Fatalf("close expired rooms: %v", err)
	}

	var refreshedExpired Room
	if err := config.AppDB.Where("id = ?", expiredRoom.ID).First(&refreshedExpired).Error; err != nil {
		t.Fatalf("reload expired room: %v", err)
	}
	if refreshedExpired.Status != roomStatusClosed || refreshedExpired.ClosedAt == nil {
		t.Fatalf("expected expired room to close, got %#v", refreshedExpired)
	}

	var refreshedActive Room
	if err := config.AppDB.Where("id = ?", activeRoom.ID).First(&refreshedActive).Error; err != nil {
		t.Fatalf("reload active room: %v", err)
	}
	if refreshedActive.Status != roomStatusOpen {
		t.Fatalf("expected active room to remain open, got %#v", refreshedActive)
	}
}

func TestPruneExpiredSessionsDeletesOnlyExpiredSessions(t *testing.T) {
	service := newMaintenanceTestService(t)

	room := Room{
		Slug:         "session-room",
		ProviderID:   "test",
		Status:       roomStatusOpen,
		Version:      1,
		LastActiveAt: time.Now().UTC(),
	}
	if err := config.AppDB.Create(&room).Error; err != nil {
		t.Fatalf("create room: %v", err)
	}
	participant := RoomParticipant{
		RoomID:      room.ID,
		DisplayName: "Guest",
		Role:        participantRole,
		Status:      participantStatusWatching,
		LastSeenAt:  time.Now().UTC(),
	}
	if err := config.AppDB.Create(&participant).Error; err != nil {
		t.Fatalf("create participant: %v", err)
	}

	expiredSession := RoomSession{
		ID:            "expired-session",
		RoomID:        room.ID,
		ParticipantID: participant.ID,
		Role:          participantRole,
		ExpiresAt:     time.Now().UTC().Add(-time.Hour),
	}
	activeSession := RoomSession{
		ID:            "active-session",
		RoomID:        room.ID,
		ParticipantID: participant.ID,
		Role:          participantRole,
		ExpiresAt:     time.Now().UTC().Add(time.Hour),
	}
	if err := config.AppDB.Create(&expiredSession).Error; err != nil {
		t.Fatalf("create expired session: %v", err)
	}
	if err := config.AppDB.Create(&activeSession).Error; err != nil {
		t.Fatalf("create active session: %v", err)
	}

	if err := service.PruneExpiredSessions(context.Background()); err != nil {
		t.Fatalf("prune expired sessions: %v", err)
	}

	var sessionCount int64
	if err := config.AppDB.Model(&RoomSession{}).Count(&sessionCount).Error; err != nil {
		t.Fatalf("count sessions: %v", err)
	}
	if sessionCount != 1 {
		t.Fatalf("expected only active session to remain, got %d", sessionCount)
	}
}
