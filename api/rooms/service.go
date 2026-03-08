package rooms

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math/rand"
	"sort"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/security"
	"gorm.io/gorm"
)

var (
	ErrForbidden            = errors.New("forbidden")
	ErrRoomNotFound         = errors.New("room not found")
	ErrRoomClosed           = errors.New("room is closed")
	ErrSessionExpired       = errors.New("room session expired")
	ErrSessionInvalid       = errors.New("invalid room session")
	ErrProviderNotConnected = errors.New("provider is not connected")
)

const (
	roomExpiryWindow    = 30 * 24 * time.Hour
	sessionExpiryWindow = 30 * 24 * time.Hour
)

type Viewer struct {
	Room        Room
	Participant RoomParticipant
	Session     RoomSession
}

func (viewer Viewer) IsHost() bool {
	return viewer.Session.Role == hostRole
}

type Service struct {
	hub *Hub
}

func NewService() *Service {
	return &Service{
		hub: NewHub(),
	}
}

func (service *Service) Hub() *Hub {
	return service.hub
}

func (service *Service) Migrate(ctx context.Context) error {
	if config.AppDB == nil {
		return fmt.Errorf("app database is not configured")
	}

	if err := config.AppDB.WithContext(ctx).AutoMigrate(
		&Room{},
		&RoomParticipant{},
		&RoomSession{},
		&RoomProviderConnection{},
		&RoomVote{},
		&RoomQueueEntry{},
		&RoomFinalistEntry{},
		&providers.ProviderCacheEntry{},
	); err != nil {
		return fmt.Errorf("migrate app database: %w", err)
	}

	return service.closeExpiredRooms(ctx)
}

func (service *Service) CreateRoom(
	ctx context.Context,
	providerID providers.ProviderID,
	roomName string,
	displayName string,
	secret providers.SecretPayload,
) (*RoomSnapshot, string, error) {
	if config.AppDB == nil {
		return nil, "", fmt.Errorf("app database is not configured")
	}
	if _, err := providers.Get(providerID); err != nil {
		return nil, "", err
	}

	if err := service.closeExpiredRooms(ctx); err != nil {
		return nil, "", err
	}

	connectionState, connectionRecord, err := service.prepareProviderConnection(ctx, providerID, secret)
	if err != nil {
		return nil, "", err
	}

	roomName = normalizeRoomName(roomName)
	displayName = normalizeDisplayName(displayName, "Host")
	roomSlug, err := security.NewOpaqueToken()
	if err != nil {
		return nil, "", err
	}
	hostSessionID, err := security.NewOpaqueToken()
	if err != nil {
		return nil, "", err
	}

	now := time.Now().UTC()
	room := Room{
		Slug:         roomSlug,
		Name:         roomName,
		ProviderID:   string(providerID),
		Status:       roomStatusOpen,
		Version:      1,
		LastActiveAt: now,
	}
	participant := RoomParticipant{
		DisplayName: displayName,
		Role:        hostRole,
		Status:      participantStatusWatching,
		LastSeenAt:  now,
	}
	session := RoomSession{
		ID:        hostSessionID,
		Role:      hostRole,
		ExpiresAt: now.Add(sessionExpiryWindow),
	}

	err = config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&room).Error; err != nil {
			return err
		}
		participant.RoomID = room.ID
		if err := tx.Create(&participant).Error; err != nil {
			return err
		}
		session.RoomID = room.ID
		session.ParticipantID = participant.ID
		if err := tx.Create(&session).Error; err != nil {
			return err
		}
		connectionRecord.RoomID = room.ID
		return tx.Create(connectionRecord).Error
	})
	if err != nil {
		return nil, "", err
	}

	snapshot, err := service.buildSnapshot(ctx, room.Slug, &Viewer{
		Room:        room,
		Participant: participant,
		Session:     session,
	})
	if err != nil {
		return nil, "", err
	}
	snapshot.Connection = connectionState

	return snapshot, hostSessionID, nil
}

func (service *Service) JoinRoom(
	ctx context.Context,
	roomSlug string,
	displayName string,
) (*RoomSnapshot, string, error) {
	if config.AppDB == nil {
		return nil, "", fmt.Errorf("app database is not configured")
	}
	if err := service.closeExpiredRooms(ctx); err != nil {
		return nil, "", err
	}

	room, err := service.findRoom(ctx, roomSlug)
	if err != nil {
		return nil, "", err
	}
	if room.Status != roomStatusOpen {
		return nil, "", ErrRoomClosed
	}

	displayName = normalizeDisplayName(displayName, "")
	if displayName == "" {
		return nil, "", fmt.Errorf("display name is required")
	}

	var existingCount int64
	if err := config.AppDB.WithContext(ctx).Model(&RoomParticipant{}).
		Where("room_id = ? AND lower(display_name) = ?", room.ID, strings.ToLower(displayName)).
		Count(&existingCount).Error; err != nil {
		return nil, "", err
	}
	if existingCount > 0 {
		return nil, "", fmt.Errorf("display name is already taken")
	}

	sessionID, err := security.NewOpaqueToken()
	if err != nil {
		return nil, "", err
	}

	now := time.Now().UTC()
	participant := RoomParticipant{
		RoomID:      room.ID,
		DisplayName: displayName,
		Role:        participantRole,
		Status:      participantStatusWatching,
		LastSeenAt:  now,
	}
	session := RoomSession{
		ID:        sessionID,
		RoomID:    room.ID,
		Role:      participantRole,
		ExpiresAt: now.Add(sessionExpiryWindow),
	}

	err = config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&participant).Error; err != nil {
			return err
		}
		session.ParticipantID = participant.ID
		if err := tx.Create(&session).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, room)
	})
	if err != nil {
		return nil, "", err
	}
	service.hub.Broadcast(EventPayload{Type: "room.updated", RoomSlug: room.Slug, Version: room.Version})

	snapshot, err := service.buildSnapshot(ctx, roomSlug, &Viewer{
		Room:        *room,
		Participant: participant,
		Session:     session,
	})
	if err != nil {
		return nil, "", err
	}

	return snapshot, sessionID, nil
}

func (service *Service) Authenticate(
	ctx context.Context,
	roomSlug string,
	sessionID string,
	requiredRole string,
) (*Viewer, error) {
	if err := service.closeExpiredRooms(ctx); err != nil {
		return nil, err
	}

	room, err := service.findRoom(ctx, roomSlug)
	if err != nil {
		return nil, err
	}

	var session RoomSession
	if err := config.AppDB.WithContext(ctx).Where("id = ? AND room_id = ?", sessionID, room.ID).
		First(&session).Error; err != nil {
		return nil, ErrSessionInvalid
	}
	if session.ExpiresAt.Before(time.Now().UTC()) {
		return nil, ErrSessionExpired
	}
	if requiredRole != "" && session.Role != requiredRole {
		return nil, ErrForbidden
	}

	var participant RoomParticipant
	if err := config.AppDB.WithContext(ctx).Where("id = ? AND room_id = ?", session.ParticipantID, room.ID).
		First(&participant).Error; err != nil {
		return nil, fmt.Errorf("participant not found")
	}

	now := time.Now().UTC()
	if err := config.AppDB.WithContext(ctx).Model(&participant).Updates(map[string]any{
		"last_seen_at": now,
		"updated_at":   now,
	}).Error; err != nil {
		slog.Warn("failed to update participant last_seen_at", "error", err, "participant_id", participant.ID)
	}
	if err := config.AppDB.WithContext(ctx).Model(&room).Update("last_active_at", now).Error; err != nil {
		slog.Warn("failed to update room last_active_at", "error", err, "room_slug", room.Slug)
	}
	participant.LastSeenAt = now
	room.LastActiveAt = now

	return &Viewer{
		Room:        *room,
		Participant: participant,
		Session:     session,
	}, nil
}

func (service *Service) GetSnapshot(ctx context.Context, viewer *Viewer) (*RoomSnapshot, error) {
	return service.buildSnapshot(ctx, viewer.Room.Slug, viewer)
}

func (service *Service) UpdateRoomName(
	ctx context.Context,
	viewer *Viewer,
	roomName string,
) (*RoomSnapshot, error) {
	if !viewer.IsHost() {
		return nil, ErrForbidden
	}

	roomName = normalizeRoomName(roomName)
	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&Room{}).
			Where("id = ?", viewer.Room.ID).
			Update("name", roomName).Error; err != nil {
			return err
		}
		viewer.Room.Name = roomName
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return nil, err
	}
	service.hub.Broadcast(EventPayload{
		Type:     "room.updated",
		RoomSlug: viewer.Room.Slug,
		Version:  viewer.Room.Version,
	})

	return service.buildSnapshot(ctx, viewer.Room.Slug, viewer)
}

func (service *Service) ConnectProvider(
	ctx context.Context,
	viewer *Viewer,
	secret providers.SecretPayload,
) (providers.ProviderConnectionState, error) {
	if !viewer.IsHost() {
		return providers.ProviderConnectionState{}, ErrForbidden
	}

	connectionState, connection, err := service.prepareProviderConnection(
		ctx,
		providers.ProviderID(viewer.Room.ProviderID),
		secret,
	)
	if err != nil {
		return providers.ProviderConnectionState{}, err
	}
	connection.RoomID = viewer.Room.ID
	if err := config.AppDB.WithContext(ctx).Where(RoomProviderConnection{RoomID: viewer.Room.ID}).
		Assign(*connection).FirstOrCreate(connection).Error; err != nil {
		return providers.ProviderConnectionState{}, err
	}

	if err := service.incrementRoom(viewer.Room.Slug, "provider.connected"); err != nil {
		return providers.ProviderConnectionState{}, err
	}

	return connectionState, nil
}

func (service *Service) prepareProviderConnection(
	ctx context.Context,
	providerID providers.ProviderID,
	secret providers.SecretPayload,
) (providers.ProviderConnectionState, *RoomProviderConnection, error) {
	provider, err := providers.Get(providerID)
	if err != nil {
		return providers.ProviderConnectionState{}, nil, err
	}

	metadata, err := provider.ValidateConnection(ctx, secret)
	if err != nil {
		return providers.ProviderConnectionState{}, nil, err
	}

	if strings.TrimSpace(config.GetRuntimeConfig().EncryptionKey) == "" {
		return providers.ProviderConnectionState{}, nil, fmt.Errorf("KILTER_TOGETHER_ENCRYPTION_KEY is required")
	}

	secretBytes, err := json.Marshal(secret)
	if err != nil {
		return providers.ProviderConnectionState{}, nil, err
	}
	metadataBytes, err := json.Marshal(metadata)
	if err != nil {
		return providers.ProviderConnectionState{}, nil, err
	}
	encryptedSecret, err := security.EncryptString(config.GetRuntimeConfig().EncryptionKey, string(secretBytes))
	if err != nil {
		return providers.ProviderConnectionState{}, nil, err
	}

	now := time.Now().UTC()
	return providers.ProviderConnectionState{
			ProviderID: providerID,
			Metadata:   metadata,
			Connected:  true,
		}, &RoomProviderConnection{
			ProviderID:       string(providerID),
			SecretCiphertext: encryptedSecret,
			MetadataJSON:     string(metadataBytes),
			LastValidatedAt:  now,
		}, nil
}

func (service *Service) ListSurfaces(
	ctx context.Context,
	viewer *Viewer,
	filters providers.SurfaceFilter,
) ([]providers.ProviderSurface, error) {
	provider, secret, err := service.providerForRoom(ctx, &viewer.Room)
	if err != nil {
		return nil, err
	}

	return provider.ListSurfaces(ctx, secret, filters)
}

func (service *Service) SetSurface(
	ctx context.Context,
	viewer *Viewer,
	surfaceID string,
	contextMap map[string]string,
) (*providers.ProviderSurface, error) {
	if !viewer.IsHost() {
		return nil, ErrForbidden
	}

	provider, secret, err := service.providerForRoom(ctx, &viewer.Room)
	if err != nil {
		return nil, err
	}

	filters := providers.SurfaceFilter{
		ParentID: contextMap["parent_id"],
	}
	surfaces, err := provider.ListSurfaces(ctx, secret, filters)
	if err != nil {
		return nil, err
	}

	var selected *providers.ProviderSurface
	for _, surface := range surfaces {
		if surface.ID == surfaceID {
			copySurface := surface
			selected = &copySurface
			break
		}
	}
	if selected == nil {
		return nil, fmt.Errorf("surface %s not found", surfaceID)
	}

	contextBytes, err := json.Marshal(contextMap)
	if err != nil {
		return nil, err
	}

	err = config.AppDB.WithContext(ctx).Model(&Room{}).
		Where("id = ?", viewer.Room.ID).
		Updates(map[string]any{
			"surface_id":           surfaceID,
			"surface_kind":         selected.Kind,
			"surface_name":         selected.Name,
			"surface_description":  selected.Description,
			"surface_context_json": string(contextBytes),
			"updated_at":           time.Now().UTC(),
		}).Error
	if err != nil {
		return nil, err
	}

	if err := service.incrementRoom(viewer.Room.Slug, "surface.updated"); err != nil {
		return nil, err
	}

	return selected, nil
}

func (service *Service) ListCatalogClimbs(
	ctx context.Context,
	viewer *Viewer,
	search string,
	sortKey string,
	cursor string,
	pageSize int,
) (*CatalogClimbsResponse, error) {
	provider, secret, err := service.providerForRoom(ctx, &viewer.Room)
	if err != nil {
		return nil, err
	}
	if viewer.Room.SurfaceID == "" {
		return nil, fmt.Errorf("room surface has not been selected")
	}

	contextMap := decodeContextMap(viewer.Room.SurfaceContextJSON)
	climbs, err := provider.ListClimbs(ctx, secret, providers.ListClimbsInput{
		SurfaceID: viewer.Room.SurfaceID,
		Context:   contextMap,
		Search:    search,
		Sort:      sortKey,
		Cursor:    cursor,
		PageSize:  pageSize,
	})
	if err != nil {
		return nil, err
	}

	voteCounts, myVotes, err := service.voteData(ctx, viewer.Room.ID, viewer.Participant.ID)
	if err != nil {
		return nil, err
	}

	return &CatalogClimbsResponse{
		Climbs:     climbs.Climbs,
		HasMore:    climbs.HasMore,
		NextCursor: climbs.NextCursor,
		PageSize:   climbs.PageSize,
		VoteCounts: voteCounts,
		MyVotes:    myVotes,
	}, nil
}

func (service *Service) GetCatalogClimb(
	ctx context.Context,
	viewer *Viewer,
	climbID string,
) (*CatalogClimbResponse, error) {
	provider, secret, err := service.providerForRoom(ctx, &viewer.Room)
	if err != nil {
		return nil, err
	}

	climb, err := provider.GetClimb(ctx, secret, providers.ListClimbsInput{
		SurfaceID: viewer.Room.SurfaceID,
		Context:   decodeContextMap(viewer.Room.SurfaceContextJSON),
	}, climbID)
	if err != nil {
		return nil, err
	}

	voteCounts, myVotes, err := service.voteData(ctx, viewer.Room.ID, viewer.Participant.ID)
	if err != nil {
		return nil, err
	}

	var queueEntryCount int64
	if err := config.AppDB.WithContext(ctx).Model(&RoomQueueEntry{}).
		Where("room_id = ? AND climb_id = ?", viewer.Room.ID, climbID).
		Count(&queueEntryCount).Error; err != nil {
		return nil, err
	}

	return &CatalogClimbResponse{
		Climb:     *climb,
		VoteCount: voteCounts[climbID],
		MyVote:    slicesContains(myVotes, climbID),
		IsQueued:  queueEntryCount > 0,
	}, nil
}

func (service *Service) ToggleVote(ctx context.Context, viewer *Viewer, climbID string) error {
	if _, err := service.getRoomClimb(ctx, &viewer.Room, climbID); err != nil {
		return err
	}

	var existing RoomVote
	err := config.AppDB.WithContext(ctx).Where(
		"room_id = ? AND participant_id = ? AND climb_id = ?",
		viewer.Room.ID,
		viewer.Participant.ID,
		climbID,
	).First(&existing).Error
	if err == nil {
		if err := config.AppDB.WithContext(ctx).Delete(&existing).Error; err != nil {
			return err
		}
	} else if errors.Is(err, gorm.ErrRecordNotFound) {
		if err := config.AppDB.WithContext(ctx).Create(&RoomVote{
			RoomID:        viewer.Room.ID,
			ParticipantID: viewer.Participant.ID,
			ClimbID:       climbID,
		}).Error; err != nil {
			return err
		}
	} else {
		return err
	}

	return service.incrementRoom(viewer.Room.Slug, "votes.updated")
}

func (service *Service) AddQueueEntry(ctx context.Context, viewer *Viewer, climbID string) error {
	if _, err := service.getRoomClimb(ctx, &viewer.Room, climbID); err != nil {
		return err
	}

	if _, err := service.addQueueEntryRecord(ctx, viewer.Room.ID, viewer.Participant.ID, climbID); err != nil {
		return err
	}

	return service.incrementRoom(viewer.Room.Slug, "queue.updated")
}

func (service *Service) AddFinalist(ctx context.Context, viewer *Viewer, climbID string) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	if _, err := service.getRoomClimb(ctx, &viewer.Room, climbID); err != nil {
		return err
	}

	var existingCount int64
	if err := config.AppDB.WithContext(ctx).Model(&RoomFinalistEntry{}).
		Where("room_id = ? AND climb_id = ?", viewer.Room.ID, climbID).
		Count(&existingCount).Error; err != nil {
		return err
	}
	if existingCount > 0 {
		return fmt.Errorf("climb is already a finalist")
	}

	var maxPosition int
	if err := config.AppDB.WithContext(ctx).Model(&RoomFinalistEntry{}).
		Where("room_id = ?", viewer.Room.ID).
		Select("COALESCE(MAX(position), 0)").
		Scan(&maxPosition).Error; err != nil {
		slog.Warn("failed to get max finalist position", "error", err, "room_id", viewer.Room.ID)
	}

	if err := config.AppDB.WithContext(ctx).Create(&RoomFinalistEntry{
		RoomID:               viewer.Room.ID,
		ClimbID:              climbID,
		AddedByParticipantID: viewer.Participant.ID,
		Position:             maxPosition + 1,
	}).Error; err != nil {
		return err
	}

	return service.incrementRoom(viewer.Room.Slug, "finalists.updated")
}

func (service *Service) ReorderFinalists(ctx context.Context, viewer *Viewer, entryIDs []uint) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}

	var entries []RoomFinalistEntry
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
		Order("position ASC").Find(&entries).Error; err != nil {
		return err
	}

	if len(entries) != len(entryIDs) {
		return fmt.Errorf("finalist reorder payload does not match room finalists")
	}

	entryByID := make(map[uint]RoomFinalistEntry, len(entries))
	for _, entry := range entries {
		entryByID[entry.ID] = entry
	}
	for index, entryID := range entryIDs {
		entry, exists := entryByID[entryID]
		if !exists {
			return fmt.Errorf("finalist entry %d does not belong to room", entryID)
		}
		if err := config.AppDB.WithContext(ctx).Model(&entry).Update("position", index+1).Error; err != nil {
			return err
		}
	}

	return service.incrementRoom(viewer.Room.Slug, "finalists.updated")
}

func (service *Service) DeleteFinalist(ctx context.Context, viewer *Viewer, entryID uint) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}

	if err := config.AppDB.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		Delete(&RoomFinalistEntry{}).Error; err != nil {
		return err
	}

	return service.incrementRoom(viewer.Room.Slug, "finalists.updated")
}

func (service *Service) PickRandom(
	ctx context.Context,
	viewer *Viewer,
	source string,
) (*providers.ProviderClimb, error) {
	if !viewer.IsHost() {
		return nil, ErrForbidden
	}

	switch source {
	case "", "auto":
		climb, err := service.pickRandomFinalist(ctx, viewer)
		if err == nil {
			return climb, nil
		}
		if !errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, err
		}
		return service.pickRandomTopVoted(ctx, viewer)
	case "finalists":
		return service.pickRandomFinalist(ctx, viewer)
	case "top_voted":
		return service.pickRandomTopVoted(ctx, viewer)
	default:
		return nil, fmt.Errorf("invalid random pick source %q", source)
	}
}

func (service *Service) PromoteClimb(
	ctx context.Context,
	viewer *Viewer,
	climbID string,
	status string,
) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	if status != queueStatusCurrent && status != queueStatusNext {
		return fmt.Errorf("invalid promotion status %q", status)
	}
	if _, err := service.getRoomClimb(ctx, &viewer.Room, climbID); err != nil {
		return err
	}

	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		entry, err := service.ensureQueueEntryRecord(tx, viewer.Room.ID, viewer.Participant.ID, climbID)
		if err != nil {
			return err
		}

		if status == queueStatusCurrent {
			if err := tx.Model(&RoomQueueEntry{}).
				Where("room_id = ? AND status = ?", viewer.Room.ID, queueStatusCurrent).
				Update("status", queueStatusQueued).Error; err != nil {
				return err
			}
			if err := tx.Model(&Room{}).
				Where("id = ?", viewer.Room.ID).
				Update("current_climb_id", climbID).Error; err != nil {
				return err
			}
		}

		if status == queueStatusNext {
			if err := tx.Model(&RoomQueueEntry{}).
				Where("room_id = ? AND status = ?", viewer.Room.ID, queueStatusNext).
				Update("status", queueStatusQueued).Error; err != nil {
				return err
			}
		}

		if err := tx.Model(entry).Update("status", status).Error; err != nil {
			return err
		}

		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}

	service.hub.Broadcast(EventPayload{Type: "queue.updated", RoomSlug: viewer.Room.Slug, Version: viewer.Room.Version})
	return nil
}

func (service *Service) ReorderQueue(ctx context.Context, viewer *Viewer, entryIDs []uint) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}

	var entries []RoomQueueEntry
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
		Order("position ASC").Find(&entries).Error; err != nil {
		return err
	}

	if len(entries) != len(entryIDs) {
		return fmt.Errorf("queue reorder payload does not match room queue")
	}

	entryByID := make(map[uint]RoomQueueEntry, len(entries))
	for _, entry := range entries {
		entryByID[entry.ID] = entry
	}
	for index, entryID := range entryIDs {
		entry, exists := entryByID[entryID]
		if !exists {
			return fmt.Errorf("queue entry %d does not belong to room", entryID)
		}
		if err := config.AppDB.WithContext(ctx).Model(&entry).Update("position", index+1).Error; err != nil {
			return err
		}
	}

	return service.incrementRoom(viewer.Room.Slug, "queue.updated")
}

func (service *Service) UpdateQueueEntryStatus(
	ctx context.Context,
	viewer *Viewer,
	entryID uint,
	status string,
) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	if status != queueStatusQueued && status != queueStatusNext && status != queueStatusCurrent && status != queueStatusDone {
		return fmt.Errorf("invalid queue status %q", status)
	}

	var entry RoomQueueEntry
	if err := config.AppDB.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		First(&entry).Error; err != nil {
		return fmt.Errorf("queue entry not found")
	}

	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if status == queueStatusCurrent {
			if err := tx.Model(&RoomQueueEntry{}).
				Where("room_id = ? AND status = ?", viewer.Room.ID, queueStatusCurrent).
				Update("status", queueStatusQueued).Error; err != nil {
				return err
			}
			if err := tx.Model(&Room{}).
				Where("id = ?", viewer.Room.ID).
				Update("current_climb_id", entry.ClimbID).Error; err != nil {
				return err
			}
		}
		if status == queueStatusNext {
			if err := tx.Model(&RoomQueueEntry{}).
				Where("room_id = ? AND status = ?", viewer.Room.ID, queueStatusNext).
				Update("status", queueStatusQueued).Error; err != nil {
				return err
			}
		}
		if status == queueStatusDone && viewer.Room.CurrentClimbID == entry.ClimbID {
			if err := tx.Model(&Room{}).
				Where("id = ?", viewer.Room.ID).
				Update("current_climb_id", "").Error; err != nil {
				return err
			}
		}
		if err := tx.Model(&entry).Update("status", status).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}

	service.hub.Broadcast(EventPayload{Type: "queue.updated", RoomSlug: viewer.Room.Slug, Version: viewer.Room.Version})
	return nil
}

func (service *Service) DeleteQueueEntry(ctx context.Context, viewer *Viewer, entryID uint) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	var entry RoomQueueEntry
	if err := config.AppDB.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		First(&entry).Error; err != nil {
		return fmt.Errorf("queue entry not found")
	}

	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Delete(&entry).Error; err != nil {
			return err
		}
		if viewer.Room.CurrentClimbID == entry.ClimbID {
			if err := tx.Model(&Room{}).Where("id = ?", viewer.Room.ID).
				Update("current_climb_id", "").Error; err != nil {
				return err
			}
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}

	service.hub.Broadcast(EventPayload{Type: "queue.updated", RoomSlug: viewer.Room.Slug, Version: viewer.Room.Version})
	return nil
}

func (service *Service) ClearVotes(ctx context.Context, viewer *Viewer) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).Delete(&RoomVote{}).Error; err != nil {
		return err
	}
	return service.incrementRoom(viewer.Room.Slug, "votes.updated")
}

func (service *Service) UpdateParticipantStatus(ctx context.Context, viewer *Viewer, status string) error {
	normalizedStatus := normalizeParticipantStatus(status)
	if !isValidParticipantStatus(normalizedStatus) {
		return fmt.Errorf("invalid participant status %q", status)
	}

	if err := config.AppDB.WithContext(ctx).Model(&RoomParticipant{}).
		Where("id = ? AND room_id = ?", viewer.Participant.ID, viewer.Room.ID).
		Update("status", normalizedStatus).Error; err != nil {
		return err
	}

	viewer.Participant.Status = normalizedStatus
	return service.incrementRoom(viewer.Room.Slug, "participants.updated")
}

func (service *Service) CloseRoom(ctx context.Context, viewer *Viewer) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	now := time.Now().UTC()
	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&Room{}).
			Where("id = ?", viewer.Room.ID).
			Updates(map[string]any{
				"status":         roomStatusClosed,
				"closed_at":      now,
				"last_active_at": now,
			}).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}
	service.hub.Broadcast(EventPayload{Type: "room.closed", RoomSlug: viewer.Room.Slug, Version: viewer.Room.Version})
	return nil
}

func (service *Service) RemoveParticipant(ctx context.Context, viewer *Viewer, participantID uint) error {
	if !viewer.IsHost() {
		return ErrForbidden
	}
	if participantID == viewer.Participant.ID {
		return fmt.Errorf("host cannot remove themselves")
	}

	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("room_id = ? AND participant_id = ?", viewer.Room.ID, participantID).Delete(&RoomSession{}).Error; err != nil {
			return err
		}
		if err := tx.Where("room_id = ? AND participant_id = ?", viewer.Room.ID, participantID).Delete(&RoomVote{}).Error; err != nil {
			return err
		}
		if err := tx.Where("room_id = ? AND added_by_participant_id = ? AND status != ?", viewer.Room.ID, participantID, queueStatusCurrent).Delete(&RoomQueueEntry{}).Error; err != nil {
			return err
		}
		if err := tx.Where("room_id = ? AND added_by_participant_id = ?", viewer.Room.ID, participantID).Delete(&RoomFinalistEntry{}).Error; err != nil {
			return err
		}
		if err := tx.Where("id = ? AND room_id = ?", participantID, viewer.Room.ID).Delete(&RoomParticipant{}).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}

	service.hub.Broadcast(EventPayload{Type: "participants.updated", RoomSlug: viewer.Room.Slug, Version: viewer.Room.Version})
	return nil
}

func (service *Service) buildSnapshot(
	ctx context.Context,
	roomSlug string,
	viewer *Viewer,
) (*RoomSnapshot, error) {
	room, err := service.findRoom(ctx, roomSlug)
	if err != nil {
		return nil, err
	}

	var participants []RoomParticipant
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", room.ID).
		Order("created_at ASC").Find(&participants).Error; err != nil {
		return nil, err
	}

	var queueEntries []RoomQueueEntry
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", room.ID).
		Order("position ASC, created_at ASC").Find(&queueEntries).Error; err != nil {
		return nil, err
	}

	var finalistEntries []RoomFinalistEntry
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", room.ID).
		Order("position ASC, created_at ASC").Find(&finalistEntries).Error; err != nil {
		return nil, err
	}

	connectionState := providers.ProviderConnectionState{
		ProviderID: providers.ProviderID(room.ProviderID),
	}
	connection, err := service.getRoomConnection(ctx, room.ID)
	if err == nil {
		connectionState.Connected = true
		connectionState.Metadata = decodeStringMap(connection.MetadataJSON)
	}

	snapshot := &RoomSnapshot{
		Slug:         room.Slug,
		RoomName:     room.Name,
		Status:       room.Status,
		ProviderID:   providers.ProviderID(room.ProviderID),
		Version:      room.Version,
		Connection:   connectionState,
		Participants: make([]ParticipantView, 0, len(participants)),
		Finalists:    make([]FinalistEntryView, 0, len(finalistEntries)),
		Queue:        make([]QueueEntryView, 0, len(queueEntries)),
		VoteCounts:   map[string]int{},
		CanManage:    viewer != nil && viewer.IsHost(),
	}

	if viewer != nil {
		snapshot.DisplayName = viewer.Participant.DisplayName
	}

	if room.SurfaceID != "" {
		surface := &providers.ProviderSurface{
			ID:          room.SurfaceID,
			Kind:        room.SurfaceKind,
			Name:        room.SurfaceName,
			Description: room.SurfaceDescription,
			Meta:        decodeContextMap(room.SurfaceContextJSON),
		}
		snapshot.Surface = surface
	}

	for _, participant := range participants {
		snapshot.Participants = append(snapshot.Participants, ParticipantView{
			ID:          participant.ID,
			DisplayName: participant.DisplayName,
			Role:        participant.Role,
			Status:      normalizeParticipantStatus(participant.Status),
			IsOnline:    participant.LastSeenAt.After(time.Now().UTC().Add(-2 * time.Minute)),
		})
	}

	if viewer != nil {
		voteCounts, myVotes, err := service.voteData(ctx, room.ID, viewer.Participant.ID)
		if err != nil {
			return nil, err
		}
		snapshot.VoteCounts = voteCounts
		snapshot.MyVotes = myVotes
	}

	if connectionState.Connected && room.SurfaceID != "" {
		provider, secret, err := service.providerForRoom(ctx, room)
		if err == nil {
			if room.CurrentClimbID != "" {
				if climb, err := provider.GetClimb(ctx, secret, providers.ListClimbsInput{
					SurfaceID: room.SurfaceID,
					Context:   decodeContextMap(room.SurfaceContextJSON),
				}, room.CurrentClimbID); err == nil {
					snapshot.CurrentClimb = climb
				}
			}

			participantNameByID := map[uint]string{}
			for _, participant := range participants {
				participantNameByID[participant.ID] = participant.DisplayName
			}

			for _, entry := range queueEntries {
				climb, err := provider.GetClimb(ctx, secret, providers.ListClimbsInput{
					SurfaceID: room.SurfaceID,
					Context:   decodeContextMap(room.SurfaceContextJSON),
				}, entry.ClimbID)
				if err != nil {
					continue
				}
				snapshot.Queue = append(snapshot.Queue, QueueEntryView{
					ID:       entry.ID,
					Status:   entry.Status,
					Position: entry.Position,
					AddedBy:  participantNameByID[entry.AddedByParticipantID],
					Climb:    *climb,
				})
			}

			for _, entry := range finalistEntries {
				climb, err := provider.GetClimb(ctx, secret, providers.ListClimbsInput{
					SurfaceID: room.SurfaceID,
					Context:   decodeContextMap(room.SurfaceContextJSON),
				}, entry.ClimbID)
				if err != nil {
					continue
				}
				snapshot.Finalists = append(snapshot.Finalists, FinalistEntryView{
					ID:       entry.ID,
					Position: entry.Position,
					AddedBy:  participantNameByID[entry.AddedByParticipantID],
					Climb:    *climb,
				})
			}
		}
	}

	return snapshot, nil
}

func (service *Service) voteData(ctx context.Context, roomID uint, participantID uint) (map[string]int, []string, error) {
	var votes []RoomVote
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", roomID).Find(&votes).Error; err != nil {
		return nil, nil, err
	}

	voteCounts := make(map[string]int)
	myVotes := make([]string, 0)
	for _, vote := range votes {
		voteCounts[vote.ClimbID]++
		if vote.ParticipantID == participantID {
			myVotes = append(myVotes, vote.ClimbID)
		}
	}
	sort.Strings(myVotes)
	return voteCounts, myVotes, nil
}

func (service *Service) providerForRoom(ctx context.Context, room *Room) (providers.Provider, providers.SecretPayload, error) {
	provider, err := providers.Get(providers.ProviderID(room.ProviderID))
	if err != nil {
		return nil, nil, err
	}
	connection, err := service.getRoomConnection(ctx, room.ID)
	if err != nil {
		return nil, nil, ErrProviderNotConnected
	}

	cfg := config.GetRuntimeConfig()
	decrypted, err := security.DecryptString(cfg.EncryptionKey, connection.SecretCiphertext)
	if err != nil && cfg.PreviousEncryptionKey != "" {
		decrypted, err = security.DecryptString(cfg.PreviousEncryptionKey, connection.SecretCiphertext)
		if err == nil {
			if reEncrypted, reErr := security.EncryptString(cfg.EncryptionKey, decrypted); reErr == nil {
				config.AppDB.WithContext(ctx).Model(&connection).Update("secret_ciphertext", reEncrypted)
			}
		}
	}
	if err != nil {
		return nil, nil, err
	}

	var secret providers.SecretPayload
	if err := json.Unmarshal([]byte(decrypted), &secret); err != nil {
		return nil, nil, err
	}

	return provider, secret, nil
}

func (service *Service) getRoomConnection(ctx context.Context, roomID uint) (*RoomProviderConnection, error) {
	var connection RoomProviderConnection
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", roomID).First(&connection).Error; err != nil {
		return nil, err
	}
	return &connection, nil
}

func (service *Service) findRoom(ctx context.Context, roomSlug string) (*Room, error) {
	var room Room
	if err := config.AppDB.WithContext(ctx).Where("slug = ?", roomSlug).First(&room).Error; err != nil {
		return nil, ErrRoomNotFound
	}
	return &room, nil
}

func (service *Service) incrementRoom(roomSlug string, eventType string) error {
	room, err := service.findRoom(context.Background(), roomSlug)
	if err != nil {
		return err
	}
	err = config.AppDB.WithContext(context.Background()).Transaction(func(tx *gorm.DB) error {
		return service.bumpRoomVersion(tx, room)
	})
	if err != nil {
		return err
	}
	service.hub.Broadcast(EventPayload{Type: eventType, RoomSlug: room.Slug, Version: room.Version})
	return nil
}

func (service *Service) bumpRoomVersion(tx *gorm.DB, room *Room) error {
	room.Version++
	room.LastActiveAt = time.Now().UTC()
	return tx.Model(room).Updates(map[string]any{
		"version":        room.Version,
		"last_active_at": room.LastActiveAt,
		"updated_at":     room.LastActiveAt,
	}).Error
}

func (service *Service) closeExpiredRooms(ctx context.Context) error {
	if config.AppDB == nil {
		return nil
	}

	cutoff := time.Now().UTC().Add(-roomExpiryWindow)
	now := time.Now().UTC()
	return config.AppDB.WithContext(ctx).Model(&Room{}).
		Where("status = ? AND last_active_at < ?", roomStatusOpen, cutoff).
		Updates(map[string]any{
			"status":     roomStatusClosed,
			"closed_at":  now,
			"updated_at": now,
		}).Error
}

func (service *Service) getRoomClimb(
	ctx context.Context,
	room *Room,
	climbID string,
) (*providers.ProviderClimb, error) {
	expectedPrefix := room.ProviderID + ":"
	if !strings.HasPrefix(climbID, expectedPrefix) {
		return nil, fmt.Errorf("climb %q does not belong to provider %s", climbID, room.ProviderID)
	}

	provider, secret, err := service.providerForRoom(ctx, room)
	if err != nil {
		return nil, err
	}

	return provider.GetClimb(ctx, secret, providers.ListClimbsInput{
		SurfaceID: room.SurfaceID,
		Context:   decodeContextMap(room.SurfaceContextJSON),
	}, climbID)
}

func (service *Service) addQueueEntryRecord(
	ctx context.Context,
	roomID uint,
	participantID uint,
	climbID string,
) (*RoomQueueEntry, error) {
	var existingCount int64
	if err := config.AppDB.WithContext(ctx).Model(&RoomQueueEntry{}).
		Where("room_id = ? AND climb_id = ?", roomID, climbID).
		Count(&existingCount).Error; err != nil {
		return nil, err
	}
	if existingCount > 0 {
		return nil, fmt.Errorf("climb is already queued")
	}

	var createdEntry *RoomQueueEntry
	err := config.AppDB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		entry, err := service.ensureQueueEntryRecord(tx, roomID, participantID, climbID)
		if err != nil {
			return err
		}
		createdEntry = entry
		return nil
	})
	return createdEntry, err
}

func (service *Service) ensureQueueEntryRecord(
	tx *gorm.DB,
	roomID uint,
	participantID uint,
	climbID string,
) (*RoomQueueEntry, error) {
	var entry RoomQueueEntry
	err := tx.Where("room_id = ? AND climb_id = ?", roomID, climbID).First(&entry).Error
	if err == nil {
		return &entry, nil
	}
	if !errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, err
	}

	var maxPosition int
	if err := tx.Model(&RoomQueueEntry{}).
		Where("room_id = ?", roomID).
		Select("COALESCE(MAX(position), 0)").
		Scan(&maxPosition).Error; err != nil {
		return nil, err
	}

	entry = RoomQueueEntry{
		RoomID:               roomID,
		ClimbID:              climbID,
		AddedByParticipantID: participantID,
		Status:               queueStatusQueued,
		Position:             maxPosition + 1,
	}
	if err := tx.Create(&entry).Error; err != nil {
		return nil, err
	}
	return &entry, nil
}

func (service *Service) pickRandomFinalist(
	ctx context.Context,
	viewer *Viewer,
) (*providers.ProviderClimb, error) {
	var finalists []RoomFinalistEntry
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
		Order("position ASC, created_at ASC").Find(&finalists).Error; err != nil {
		return nil, err
	}
	if len(finalists) == 0 {
		return nil, gorm.ErrRecordNotFound
	}

	selected := finalists[rand.Intn(len(finalists))]
	return service.getRoomClimb(ctx, &viewer.Room, selected.ClimbID)
}

func (service *Service) pickRandomTopVoted(
	ctx context.Context,
	viewer *Viewer,
) (*providers.ProviderClimb, error) {
	var votes []RoomVote
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).Find(&votes).Error; err != nil {
		return nil, err
	}
	if len(votes) == 0 {
		return nil, fmt.Errorf("there are no voted climbs to pick from")
	}

	voteCounts := make(map[string]int)
	topCount := 0
	for _, vote := range votes {
		voteCounts[vote.ClimbID]++
		if voteCounts[vote.ClimbID] > topCount {
			topCount = voteCounts[vote.ClimbID]
		}
	}
	if topCount == 0 {
		return nil, fmt.Errorf("there are no voted climbs to pick from")
	}

	topClimbIDs := make([]string, 0)
	for climbID, count := range voteCounts {
		if count == topCount {
			topClimbIDs = append(topClimbIDs, climbID)
		}
	}
	sort.Strings(topClimbIDs)

	selectedClimbID := topClimbIDs[rand.Intn(len(topClimbIDs))]
	return service.getRoomClimb(ctx, &viewer.Room, selectedClimbID)
}

func normalizeDisplayName(value string, fallback string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return fallback
	}
	return trimmed
}

func normalizeRoomName(value string) string {
	return strings.TrimSpace(value)
}

func decodeContextMap(raw string) map[string]string {
	if strings.TrimSpace(raw) == "" {
		return map[string]string{}
	}

	var contextMap map[string]string
	if err := json.Unmarshal([]byte(raw), &contextMap); err != nil {
		return map[string]string{}
	}
	return contextMap
}

func decodeStringMap(raw string) map[string]string {
	if strings.TrimSpace(raw) == "" {
		return nil
	}

	var result map[string]string
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		return nil
	}
	return result
}

func slicesContains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func normalizeParticipantStatus(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case participantStatusReady:
		return participantStatusReady
	case participantStatusResting:
		return participantStatusResting
	case participantStatusAway:
		return participantStatusAway
	default:
		return participantStatusWatching
	}
}

func isValidParticipantStatus(value string) bool {
	switch value {
	case participantStatusWatching, participantStatusReady, participantStatusResting, participantStatusAway:
		return true
	default:
		return false
	}
}
