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
	"github.com/lczm/kilter-together/api/migrations"
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
	ErrFistBumpsOff         = errors.New("fist bumps are disabled for this room")
	ErrClimbNotQueued       = errors.New("climb is not queued in this room")
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

func (viewer Viewer) IsCoHost() bool {
	return viewer.Session.Role == coHostRole
}

func (viewer Viewer) CanManageSession() bool {
	return viewer.IsHost() || viewer.IsCoHost()
}

func (viewer Viewer) CanManageSurface() bool {
	return viewer.CanManageSession()
}

func (viewer Viewer) CanManageQueue() bool {
	return viewer.CanManageSession()
}

func (viewer Viewer) CanManageFinalists() bool {
	return viewer.CanManageSession()
}

func (viewer Viewer) CanEditRoomSettings() bool {
	return viewer.IsHost()
}

func (viewer Viewer) CanManageParticipants() bool {
	return viewer.IsHost()
}

func (viewer Viewer) CanAssignCoHosts() bool {
	return viewer.IsHost()
}

func (viewer Viewer) CanCloseRoom() bool {
	return viewer.IsHost()
}

type Service struct {
	store     RoomStore
	hub       EventBus
	fistBumps *FistBumpStore
}

func NewService() *Service {
	return NewServiceWithDeps(defaultRoomStore(), NewHub(), NewFistBumpStore())
}

func NewServiceWithDeps(store RoomStore, hub EventBus, fistBumps *FistBumpStore) *Service {
	return &Service{
		store:     store,
		hub:       hub,
		fistBumps: fistBumps,
	}
}

func (service *Service) Hub() EventBus {
	return service.hub
}

func (service *Service) Migrate(ctx context.Context) error {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return fmt.Errorf("app database is not configured")
	}

	if err := migrations.Apply(ctx, db); err != nil {
		return fmt.Errorf("migrate app database: %w", err)
	}

	return nil
}

func (service *Service) CreateRoom(
	ctx context.Context,
	providerID providers.ProviderID,
	roomName string,
	displayName string,
	secret providers.SecretPayload,
	fistBumpsEnabled bool,
) (*RoomSnapshot, string, error) {
	if _, err := mustStoreDB(service.store, ctx); err != nil {
		return nil, "", fmt.Errorf("app database is not configured")
	}
	if _, err := providers.Get(providerID); err != nil {
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
		Slug:             roomSlug,
		Name:             roomName,
		ProviderID:       string(providerID),
		Status:           roomStatusOpen,
		AssistantMode:    assistantModeManual,
		FistBumpsEnabled: fistBumpsEnabled,
		Version:          1,
		LastActiveAt:     now,
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

	err = service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
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
	if _, err := mustStoreDB(service.store, ctx); err != nil {
		return nil, "", fmt.Errorf("app database is not configured")
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
	if err := service.store.WithContext(ctx).Model(&RoomParticipant{}).
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

	err = service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
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
	service.broadcastRoomEvent(room, participant.ID, "room.updated", ResourceRoom, ResourceParticipants)

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
	room, err := service.findRoom(ctx, roomSlug)
	if err != nil {
		return nil, err
	}
	if room.Status != roomStatusOpen || service.isRoomExpired(room, time.Now().UTC()) {
		return nil, ErrRoomClosed
	}

	var session RoomSession
	if err := service.store.WithContext(ctx).Where("id = ? AND room_id = ?", sessionID, room.ID).
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
	if err := service.store.WithContext(ctx).Where("id = ? AND room_id = ?", session.ParticipantID, room.ID).
		First(&participant).Error; err != nil {
		return nil, fmt.Errorf("participant not found")
	}

	now := time.Now().UTC()
	if err := service.store.WithContext(ctx).Model(&participant).Updates(map[string]any{
		"last_seen_at": now,
		"updated_at":   now,
	}).Error; err != nil {
		slog.Warn("failed to update participant last_seen_at", "error", err, "participant_id", participant.ID)
	}
	if err := service.store.WithContext(ctx).Model(&room).Update("last_active_at", now).Error; err != nil {
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
	if !viewer.CanEditRoomSettings() {
		return nil, ErrForbidden
	}

	roomName = normalizeRoomName(roomName)
	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
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
	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "room.updated", ResourceRoom)

	return service.buildSnapshot(ctx, viewer.Room.Slug, viewer)
}

func (service *Service) SetFistBumpsEnabled(
	ctx context.Context,
	viewer *Viewer,
	enabled bool,
) (*RoomSnapshot, error) {
	if !viewer.CanEditRoomSettings() {
		return nil, ErrForbidden
	}

	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&Room{}).
			Where("id = ?", viewer.Room.ID).
			Update("emoji_reactions_enabled", enabled).Error; err != nil {
			return err
		}
		viewer.Room.FistBumpsEnabled = enabled
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return nil, err
	}
	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "room.updated", ResourceRoom)

	return service.buildSnapshot(ctx, viewer.Room.Slug, viewer)
}

func (service *Service) ConnectProvider(
	ctx context.Context,
	viewer *Viewer,
	secret providers.SecretPayload,
) (providers.ProviderConnectionState, error) {
	if !viewer.CanEditRoomSettings() {
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
	if err := service.store.WithContext(ctx).Where(RoomProviderConnection{RoomID: viewer.Room.ID}).
		Assign(*connection).FirstOrCreate(connection).Error; err != nil {
		return providers.ProviderConnectionState{}, err
	}

	if err := service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "provider.connected", ResourceRoom, ResourceConnection, ResourceCatalog); err != nil {
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
	if !viewer.CanManageSurface() {
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

	err = service.store.WithContext(ctx).Model(&Room{}).
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

	if err := service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "surface.updated", ResourceRoom, ResourceSurface, ResourceCatalog); err != nil {
		return nil, err
	}
	viewer.Room.SurfaceID = selected.ID
	viewer.Room.SurfaceKind = selected.Kind
	viewer.Room.SurfaceName = selected.Name
	viewer.Room.SurfaceDescription = selected.Description
	viewer.Room.SurfaceContextJSON = string(contextBytes)

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

	isQueued, err := service.isClimbQueued(ctx, viewer.Room.ID, climbID)
	if err != nil {
		return nil, err
	}

	return &CatalogClimbResponse{
		Climb:     *climb,
		VoteCount: voteCounts[climbID],
		MyVote:    slicesContains(myVotes, climbID),
		IsQueued:  isQueued,
	}, nil
}

func (service *Service) ToggleVote(ctx context.Context, viewer *Viewer, climbID string) error {
	room, err := service.findRoom(ctx, viewer.Room.Slug)
	if err != nil {
		return err
	}
	if room.Status != roomStatusOpen {
		return ErrRoomClosed
	}
	if !room.FistBumpsEnabled {
		return ErrFistBumpsOff
	}

	if _, err := service.getRoomClimb(ctx, &viewer.Room, climbID); err != nil {
		return err
	}
	isQueued, err := service.isClimbQueued(ctx, viewer.Room.ID, climbID)
	if err != nil {
		return err
	}
	if !isQueued {
		return ErrClimbNotQueued
	}

	service.fistBumps.Toggle(viewer.Room.ID, viewer.Participant.ID, climbID)

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "votes.updated", ResourceVotes)
}

func (service *Service) isClimbQueued(ctx context.Context, roomID uint, climbID string) (bool, error) {
	var queueEntryCount int64
	if err := service.store.WithContext(ctx).Model(&RoomQueueEntry{}).
		Where("room_id = ? AND climb_id = ?", roomID, climbID).
		Count(&queueEntryCount).Error; err != nil {
		return false, err
	}

	return queueEntryCount > 0, nil
}

func (service *Service) AddQueueEntry(ctx context.Context, viewer *Viewer, climbID string) error {
	climb, err := service.getRoomClimb(ctx, &viewer.Room, climbID)
	if err != nil {
		return err
	}

	if _, err := service.addQueueEntryRecord(ctx, viewer.Room.ID, viewer.Participant.ID, climb); err != nil {
		return err
	}

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "queue.updated", ResourceQueue, ResourceVotes)
}

func (service *Service) AddFinalist(ctx context.Context, viewer *Viewer, climbID string) error {
	if !viewer.CanManageFinalists() {
		return ErrForbidden
	}
	climb, err := service.getRoomClimb(ctx, &viewer.Room, climbID)
	if err != nil {
		return err
	}

	var existingCount int64
	if err := service.store.WithContext(ctx).Model(&RoomFinalistEntry{}).
		Where("room_id = ? AND climb_id = ?", viewer.Room.ID, climbID).
		Count(&existingCount).Error; err != nil {
		return err
	}
	if existingCount > 0 {
		return fmt.Errorf("climb is already a finalist")
	}

	var maxPosition int
	if err := service.store.WithContext(ctx).Model(&RoomFinalistEntry{}).
		Where("room_id = ?", viewer.Room.ID).
		Select("COALESCE(MAX(position), 0)").
		Scan(&maxPosition).Error; err != nil {
		slog.Warn("failed to get max finalist position", "error", err, "room_id", viewer.Room.ID)
	}

	if err := service.store.WithContext(ctx).Create(&RoomFinalistEntry{
		RoomID:               viewer.Room.ID,
		ClimbID:              climbID,
		AddedByParticipantID: viewer.Participant.ID,
		Position:             maxPosition + 1,
		ClimbJSON:            mustEncodeProviderClimb(climb),
	}).Error; err != nil {
		return err
	}

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "finalists.updated", ResourceFinalists)
}

func (service *Service) ReorderFinalists(ctx context.Context, viewer *Viewer, entryIDs []uint) error {
	if !viewer.CanManageFinalists() {
		return ErrForbidden
	}

	var entries []RoomFinalistEntry
	if err := service.store.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
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
		if err := service.store.WithContext(ctx).Model(&entry).Update("position", index+1).Error; err != nil {
			return err
		}
	}

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "finalists.updated", ResourceFinalists)
}

func (service *Service) DeleteFinalist(ctx context.Context, viewer *Viewer, entryID uint) error {
	if !viewer.CanManageFinalists() {
		return ErrForbidden
	}

	if err := service.store.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		Delete(&RoomFinalistEntry{}).Error; err != nil {
		return err
	}

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "finalists.updated", ResourceFinalists)
}

func (service *Service) PickRandom(
	ctx context.Context,
	viewer *Viewer,
	source string,
) (*providers.ProviderClimb, error) {
	if !viewer.CanManageFinalists() {
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
	if !viewer.CanManageQueue() {
		return ErrForbidden
	}
	if status != queueStatusCurrent && status != queueStatusNext {
		return fmt.Errorf("invalid promotion status %q", status)
	}
	climb, err := service.getRoomClimb(ctx, &viewer.Room, climbID)
	if err != nil {
		return err
	}

	err = service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		entry, err := service.ensureQueueEntryRecord(tx, viewer.Room.ID, viewer.Participant.ID, climb)
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
				Updates(map[string]any{
					"current_climb_id":   climbID,
					"current_climb_json": entry.ClimbJSON,
				}).Error; err != nil {
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

	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "queue.updated", ResourceQueue, ResourceCurrentClimb, ResourceVotes)
	return nil
}

func (service *Service) ReorderQueue(ctx context.Context, viewer *Viewer, entryIDs []uint) error {
	if !viewer.CanManageQueue() {
		return ErrForbidden
	}

	var entries []RoomQueueEntry
	if err := service.store.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
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
		if err := service.store.WithContext(ctx).Model(&entry).Update("position", index+1).Error; err != nil {
			return err
		}
	}

	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "queue.updated", ResourceQueue, ResourceVotes)
}

func (service *Service) UpdateQueueEntryStatus(
	ctx context.Context,
	viewer *Viewer,
	entryID uint,
	status string,
) error {
	if !viewer.CanManageQueue() {
		return ErrForbidden
	}
	if status != queueStatusQueued && status != queueStatusNext && status != queueStatusCurrent && status != queueStatusDone {
		return fmt.Errorf("invalid queue status %q", status)
	}

	var entry RoomQueueEntry
	if err := service.store.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		First(&entry).Error; err != nil {
		return fmt.Errorf("queue entry not found")
	}
	entryClimbJSON := entry.ClimbJSON
	if status == queueStatusCurrent && strings.TrimSpace(entryClimbJSON) == "" {
		climb, err := service.getRoomClimb(ctx, &viewer.Room, entry.ClimbID)
		if err != nil {
			return err
		}
		entryClimbJSON = mustEncodeProviderClimb(climb)
	}

	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if status == queueStatusCurrent {
			if err := tx.Model(&RoomQueueEntry{}).
				Where("room_id = ? AND status = ?", viewer.Room.ID, queueStatusCurrent).
				Update("status", queueStatusQueued).Error; err != nil {
				return err
			}
			if err := tx.Model(&Room{}).
				Where("id = ?", viewer.Room.ID).
				Updates(map[string]any{
					"current_climb_id":   entry.ClimbID,
					"current_climb_json": entryClimbJSON,
				}).Error; err != nil {
				return err
			}
			if entry.ClimbJSON != entryClimbJSON {
				if err := tx.Model(&entry).Update("climb_json", entryClimbJSON).Error; err != nil {
					return err
				}
				entry.ClimbJSON = entryClimbJSON
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
				Updates(map[string]any{
					"current_climb_id":   "",
					"current_climb_json": "",
				}).Error; err != nil {
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

	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "queue.updated", ResourceQueue, ResourceCurrentClimb, ResourceVotes)
	return nil
}

func (service *Service) DeleteQueueEntry(ctx context.Context, viewer *Viewer, entryID uint) error {
	if !viewer.CanManageQueue() {
		return ErrForbidden
	}
	var entry RoomQueueEntry
	if err := service.store.WithContext(ctx).Where("id = ? AND room_id = ?", entryID, viewer.Room.ID).
		First(&entry).Error; err != nil {
		return fmt.Errorf("queue entry not found")
	}

	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Delete(&entry).Error; err != nil {
			return err
		}
		if viewer.Room.CurrentClimbID == entry.ClimbID {
			if err := tx.Model(&Room{}).Where("id = ?", viewer.Room.ID).
				Updates(map[string]any{
					"current_climb_id":   "",
					"current_climb_json": "",
				}).Error; err != nil {
				return err
			}
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}

	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "queue.updated", ResourceQueue, ResourceCurrentClimb, ResourceVotes)
	return nil
}

func (service *Service) ClearVotes(ctx context.Context, viewer *Viewer) error {
	if !viewer.CanManageQueue() {
		return ErrForbidden
	}
	service.fistBumps.Clear(viewer.Room.ID)
	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "votes.updated", ResourceVotes)
}

func (service *Service) UpdateParticipantStatus(ctx context.Context, viewer *Viewer, status string) error {
	normalizedStatus := normalizeParticipantStatus(status)
	if !isValidParticipantStatus(normalizedStatus) {
		return fmt.Errorf("invalid participant status %q", status)
	}

	if err := service.store.WithContext(ctx).Model(&RoomParticipant{}).
		Where("id = ? AND room_id = ?", viewer.Participant.ID, viewer.Room.ID).
		Update("status", normalizedStatus).Error; err != nil {
		return err
	}

	viewer.Participant.Status = normalizedStatus
	return service.incrementRoom(ctx, viewer.Room.Slug, viewer.Participant.ID, "participants.updated", ResourceParticipants)
}

func (service *Service) UpdateParticipantRole(
	ctx context.Context,
	viewer *Viewer,
	participantID uint,
	role string,
) error {
	if !viewer.CanAssignCoHosts() {
		return ErrForbidden
	}

	normalizedRole := normalizeParticipantRole(role)
	if normalizedRole != participantRole && normalizedRole != coHostRole {
		return fmt.Errorf("invalid participant role %q", role)
	}

	var participant RoomParticipant
	if err := service.store.WithContext(ctx).
		Where("id = ? AND room_id = ?", participantID, viewer.Room.ID).
		First(&participant).Error; err != nil {
		return fmt.Errorf("participant not found")
	}
	if participant.Role == hostRole {
		return fmt.Errorf("host role cannot be reassigned")
	}
	if participant.Role == normalizedRole {
		return nil
	}

	if err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&participant).Update("role", normalizedRole).Error; err != nil {
			return err
		}
		if err := tx.Model(&RoomSession{}).
			Where("room_id = ? AND participant_id = ?", viewer.Room.ID, participantID).
			Update("role", normalizedRole).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	}); err != nil {
		return err
	}

	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "participants.updated", ResourceParticipants)
	return nil
}

func (service *Service) CloseRoom(ctx context.Context, viewer *Viewer) error {
	if !viewer.CanCloseRoom() {
		return ErrForbidden
	}
	room, err := service.findRoom(ctx, viewer.Room.Slug)
	if err != nil {
		return err
	}
	viewer.Room = *room
	now := time.Now().UTC()
	voteCounts, _ := service.fistBumps.VoteData(viewer.Room.ID, 0)
	err = service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&Room{}).
			Where("id = ?", viewer.Room.ID).
			Updates(map[string]any{
				"status":         roomStatusClosed,
				"closed_at":      now,
				"last_active_at": now,
			}).Error; err != nil {
			return err
		}
		if err := service.recordAnalyticsEventTx(tx, AnalyticsEventInput{
			RoomSlug:   viewer.Room.Slug,
			EventName:  "room.close",
			Source:     "server",
			ViewerRole: viewer.Session.Role,
		}); err != nil {
			return err
		}
		if err := service.persistRoomSessionSummary(tx, &viewer.Room, now, voteCounts); err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return err
	}
	viewer.Room.Status = roomStatusClosed
	viewer.Room.ClosedAt = &now
	service.fistBumps.Clear(viewer.Room.ID)
	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "room.closed", ResourceRoom, ResourceParticipants, ResourceQueue, ResourceFinalists, ResourceVotes, ResourceCurrentClimb)
	return nil
}

func (service *Service) ListRecentSessionSummaries(
	ctx context.Context,
	limit int,
) ([]SessionSummaryView, error) {
	if limit <= 0 {
		limit = 6
	}
	if limit > 24 {
		limit = 24
	}

	var summaries []RoomSessionSummary
	if err := service.store.WithContext(ctx).
		Order("closed_at DESC").
		Limit(limit).
		Find(&summaries).Error; err != nil {
		return nil, err
	}

	result := make([]SessionSummaryView, 0, len(summaries))
	for _, summary := range summaries {
		result = append(result, sessionSummaryView(summary))
	}

	return result, nil
}

func (service *Service) RemoveParticipant(ctx context.Context, viewer *Viewer, participantID uint) error {
	if !viewer.CanManageParticipants() {
		return ErrForbidden
	}
	if participantID == viewer.Participant.ID {
		return fmt.Errorf("host cannot remove themselves")
	}

	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("room_id = ? AND participant_id = ?", viewer.Room.ID, participantID).Delete(&RoomSession{}).Error; err != nil {
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
	service.fistBumps.ClearParticipant(viewer.Room.ID, participantID)

	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "participants.updated", ResourceParticipants, ResourceQueue, ResourceFinalists, ResourceVotes)
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
	if err := service.store.WithContext(ctx).Where("room_id = ?", room.ID).
		Order("created_at ASC").Find(&participants).Error; err != nil {
		return nil, err
	}

	var queueEntries []RoomQueueEntry
	if err := service.store.WithContext(ctx).Where("room_id = ?", room.ID).
		Order("position ASC, created_at ASC").Find(&queueEntries).Error; err != nil {
		return nil, err
	}

	var finalistEntries []RoomFinalistEntry
	if err := service.store.WithContext(ctx).Where("room_id = ?", room.ID).
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
		Slug:             room.Slug,
		RoomName:         room.Name,
		Status:           room.Status,
		ProviderID:       providers.ProviderID(room.ProviderID),
		Version:          room.Version,
		Connection:       connectionState,
		Participants:     make([]ParticipantView, 0, len(participants)),
		Finalists:        make([]FinalistEntryView, 0, len(finalistEntries)),
		Queue:            make([]QueueEntryView, 0, len(queueEntries)),
		VoteCounts:       map[string]int{},
		FistBumpsEnabled: room.FistBumpsEnabled,
		CanManage:        viewer != nil && viewer.CanManageSession(),
	}

	if viewer != nil {
		snapshot.DisplayName = viewer.Participant.DisplayName
		snapshot.Permissions = PermissionView{
			ManageSession:      viewer.CanManageSession(),
			ManageSurface:      viewer.CanManageSurface(),
			ManageQueue:        viewer.CanManageQueue(),
			ManageFinalists:    viewer.CanManageFinalists(),
			EditRoomSettings:   viewer.CanEditRoomSettings(),
			ManageParticipants: viewer.CanManageParticipants(),
			AssignCoHosts:      viewer.CanAssignCoHosts(),
			CloseRoom:          viewer.CanCloseRoom(),
		}
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
			Role:        normalizeParticipantRole(participant.Role),
			Status:      normalizeParticipantStatus(participant.Status),
			IsOnline:    participant.LastSeenAt.After(time.Now().UTC().Add(-2 * time.Minute)),
		})
	}

	voteParticipantID := uint(0)
	if viewer != nil {
		voteParticipantID = viewer.Participant.ID
	}
	voteCounts, myVotes, err := service.voteData(ctx, room.ID, voteParticipantID)
	if err != nil {
		return nil, err
	}
	snapshot.VoteCounts = voteCounts
	if viewer != nil {
		snapshot.MyVotes = myVotes
	}

	participantNameByID := map[uint]string{}
	for _, participant := range participants {
		participantNameByID[participant.ID] = participant.DisplayName
	}

	var (
		provider     providers.Provider
		secret       providers.SecretPayload
		providerErr  error
		providerInit bool
	)
	loadProvider := func() bool {
		if providerInit {
			return providerErr == nil
		}

		providerInit = true
		if !connectionState.Connected || room.SurfaceID == "" {
			providerErr = ErrProviderNotConnected
			return false
		}

		provider, secret, providerErr = service.providerForRoom(ctx, room)
		return providerErr == nil
	}
	resolveClimb := func(climbID string, cachedJSON string) *providers.ProviderClimb {
		if climb := decodeProviderClimb(cachedJSON); climb != nil {
			return climb
		}
		if !loadProvider() {
			return nil
		}
		climb, err := provider.GetClimb(ctx, secret, providers.ListClimbsInput{
			SurfaceID: room.SurfaceID,
			Context:   decodeContextMap(room.SurfaceContextJSON),
		}, climbID)
		if err != nil {
			return nil
		}
		return climb
	}

	if room.CurrentClimbID != "" {
		snapshot.CurrentClimb = resolveClimb(room.CurrentClimbID, room.CurrentClimbJSON)
	}

	for _, entry := range queueEntries {
		climb := resolveClimb(entry.ClimbID, entry.ClimbJSON)
		if climb == nil {
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
		climb := resolveClimb(entry.ClimbID, entry.ClimbJSON)
		if climb == nil {
			continue
		}
		snapshot.Finalists = append(snapshot.Finalists, FinalistEntryView{
			ID:       entry.ID,
			Position: entry.Position,
			AddedBy:  participantNameByID[entry.AddedByParticipantID],
			Climb:    *climb,
		})
	}

	snapshot.Assistant = buildAssistantState(room, snapshot)

	return snapshot, nil
}

func (service *Service) voteData(ctx context.Context, roomID uint, participantID uint) (map[string]int, []string, error) {
	voteCounts, myVotes := service.fistBumps.VoteData(roomID, participantID)
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
				service.store.WithContext(ctx).Model(&connection).Update("secret_ciphertext", reEncrypted)
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
	if err := service.store.WithContext(ctx).Where("room_id = ?", roomID).First(&connection).Error; err != nil {
		return nil, err
	}
	return &connection, nil
}

func (service *Service) findRoom(ctx context.Context, roomSlug string) (*Room, error) {
	var room Room
	if err := service.store.WithContext(ctx).Where("slug = ?", roomSlug).First(&room).Error; err != nil {
		return nil, ErrRoomNotFound
	}
	if service.isRoomExpired(&room, time.Now().UTC()) {
		room.Status = roomStatusClosed
	}
	return &room, nil
}

func (service *Service) incrementRoom(
	ctx context.Context,
	roomSlug string,
	participantID uint,
	eventType string,
	resources ...EventResource,
) error {
	room, err := service.findRoom(ctx, roomSlug)
	if err != nil {
		return err
	}
	err = service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		return service.bumpRoomVersion(tx, room)
	})
	if err != nil {
		return err
	}
	service.broadcastRoomEvent(room, participantID, eventType, resources...)
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

func (service *Service) CloseExpiredRooms(ctx context.Context) error {
	if service.store == nil {
		return nil
	}

	cutoff := time.Now().UTC().Add(-roomExpiryWindow)
	now := time.Now().UTC()
	var expiredRooms []Room
	if err := service.store.WithContext(ctx).
		Where("status = ? AND last_active_at < ?", roomStatusOpen, cutoff).
		Find(&expiredRooms).Error; err != nil {
		return err
	}
	if len(expiredRooms) == 0 {
		return nil
	}

	for index := range expiredRooms {
		room := expiredRooms[index]
		voteCounts, _ := service.fistBumps.VoteData(room.ID, 0)
		if err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
			if err := tx.Model(&Room{}).
				Where("id = ?", room.ID).
				Updates(map[string]any{
					"status":         roomStatusClosed,
					"closed_at":      now,
					"last_active_at": now,
					"updated_at":     now,
				}).Error; err != nil {
				return err
			}
			if err := service.recordAnalyticsEventTx(tx, AnalyticsEventInput{
				RoomSlug:   room.Slug,
				EventName:  "room.close",
				Source:     "server",
				ViewerRole: "system",
				Properties: map[string]any{"expired": true},
			}); err != nil {
				return err
			}
			return service.persistRoomSessionSummary(tx, &room, now, voteCounts)
		}); err != nil {
			return err
		}
		service.fistBumps.Clear(room.ID)
	}
	return nil
}

func (service *Service) persistRoomSessionSummary(
	tx *gorm.DB,
	room *Room,
	closedAt time.Time,
	voteCounts map[string]int,
) error {
	if tx == nil || room == nil {
		return nil
	}

	var participants []RoomParticipant
	if err := tx.Where("room_id = ?", room.ID).
		Order("created_at ASC").
		Find(&participants).Error; err != nil {
		return err
	}

	var queueEntries []RoomQueueEntry
	if err := tx.Where("room_id = ?", room.ID).
		Order("position ASC, created_at ASC").
		Find(&queueEntries).Error; err != nil {
		return err
	}

	var finalistEntries []RoomFinalistEntry
	if err := tx.Where("room_id = ?", room.ID).
		Order("position ASC, created_at ASC").
		Find(&finalistEntries).Error; err != nil {
		return err
	}

	participantNameByID := make(map[uint]string, len(participants))
	for _, participant := range participants {
		participantNameByID[participant.ID] = participant.DisplayName
	}

	finalQueue := make([]SessionSummaryClimbView, 0, len(queueEntries))
	queueViewByClimbID := make(map[string]SessionSummaryClimbView, len(queueEntries))
	for _, entry := range queueEntries {
		view := SessionSummaryClimbView{
			Position: entry.Position,
			Status:   entry.Status,
			AddedBy:  participantNameByID[entry.AddedByParticipantID],
			Climb:    summaryProviderClimb(room, entry.ClimbID, entry.ClimbJSON),
		}
		finalQueue = append(finalQueue, view)
		queueViewByClimbID[entry.ClimbID] = view
	}

	finalists := make([]SessionSummaryClimbView, 0, len(finalistEntries))
	for _, entry := range finalistEntries {
		finalists = append(finalists, SessionSummaryClimbView{
			Position: entry.Position,
			AddedBy:  participantNameByID[entry.AddedByParticipantID],
			Climb:    summaryProviderClimb(room, entry.ClimbID, entry.ClimbJSON),
		})
	}

	topVoted := make([]SessionSummaryClimbView, 0, len(voteCounts))
	for climbID, voteCount := range voteCounts {
		if voteCount <= 0 {
			continue
		}
		view, exists := queueViewByClimbID[climbID]
		if !exists {
			view = SessionSummaryClimbView{
				Climb: summaryProviderClimb(room, climbID, ""),
			}
		}
		view.VoteCount = voteCount
		topVoted = append(topVoted, view)
	}
	sort.Slice(topVoted, func(i, j int) bool {
		if topVoted[i].VoteCount != topVoted[j].VoteCount {
			return topVoted[i].VoteCount > topVoted[j].VoteCount
		}
		if topVoted[i].Position != topVoted[j].Position {
			return topVoted[i].Position < topVoted[j].Position
		}
		return topVoted[i].Climb.ID < topVoted[j].Climb.ID
	})

	summary := RoomSessionSummary{
		RoomID:           room.ID,
		RoomSlug:         room.Slug,
		RoomName:         room.Name,
		ProviderID:       room.ProviderID,
		SurfaceName:      room.SurfaceName,
		SurfaceKind:      room.SurfaceKind,
		ParticipantCount: len(participants),
		TopVotedJSON:     mustEncodeSessionSummaryClimbs(topVoted),
		FinalQueueJSON:   mustEncodeSessionSummaryClimbs(finalQueue),
		FinalistsJSON:    mustEncodeSessionSummaryClimbs(finalists),
		ClosedAt:         closedAt,
	}

	var existing RoomSessionSummary
	if err := tx.Where("room_id = ?", room.ID).First(&existing).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			recapShareID, tokenErr := security.NewOpaqueToken()
			if tokenErr != nil {
				return tokenErr
			}
			summary.RecapShareID = recapShareID
			if err := tx.Create(&summary).Error; err != nil {
				return err
			}
			var events []AnalyticsEvent
			if err := tx.Where("room_id = ?", room.ID).Order("created_at ASC").Find(&events).Error; err != nil {
				return err
			}
			return service.persistRoomRecap(tx, room, summary, participants, events)
		}
		return err
	}

	recapShareID := existing.RecapShareID
	if strings.TrimSpace(recapShareID) == "" {
		generatedShareID, tokenErr := security.NewOpaqueToken()
		if tokenErr != nil {
			return tokenErr
		}
		recapShareID = generatedShareID
	}
	summary.RecapShareID = recapShareID

	if err := tx.Model(&existing).Updates(map[string]any{
		"room_slug":         summary.RoomSlug,
		"room_name":         summary.RoomName,
		"provider_id":       summary.ProviderID,
		"surface_name":      summary.SurfaceName,
		"surface_kind":      summary.SurfaceKind,
		"participant_count": summary.ParticipantCount,
		"recap_share_id":    summary.RecapShareID,
		"top_voted_json":    summary.TopVotedJSON,
		"final_queue_json":  summary.FinalQueueJSON,
		"finalists_json":    summary.FinalistsJSON,
		"closed_at":         summary.ClosedAt,
		"updated_at":        time.Now().UTC(),
	}).Error; err != nil {
		return err
	}

	var events []AnalyticsEvent
	if err := tx.Where("room_id = ?", room.ID).Order("created_at ASC").Find(&events).Error; err != nil {
		return err
	}
	return service.persistRoomRecap(tx, room, summary, participants, events)
}

func sessionSummaryView(summary RoomSessionSummary) SessionSummaryView {
	return SessionSummaryView{
		RoomSlug:         summary.RoomSlug,
		RoomName:         summary.RoomName,
		ProviderID:       providers.ProviderID(summary.ProviderID),
		SurfaceName:      summary.SurfaceName,
		SurfaceKind:      summary.SurfaceKind,
		ParticipantCount: summary.ParticipantCount,
		RecapShareID:     summary.RecapShareID,
		ClosedAt:         summary.ClosedAt,
		TopVoted:         decodeSessionSummaryClimbs(summary.TopVotedJSON),
		FinalQueue:       decodeSessionSummaryClimbs(summary.FinalQueueJSON),
		Finalists:        decodeSessionSummaryClimbs(summary.FinalistsJSON),
	}
}

func (service *Service) PruneExpiredSessions(ctx context.Context) error {
	if service.store == nil {
		return nil
	}

	return service.store.WithContext(ctx).
		Where("expires_at <= ?", time.Now().UTC()).
		Delete(&RoomSession{}).Error
}

func (service *Service) isRoomExpired(room *Room, now time.Time) bool {
	if room == nil {
		return false
	}

	return room.Status == roomStatusOpen && room.LastActiveAt.Before(now.Add(-roomExpiryWindow))
}

func (service *Service) broadcastRoomEvent(
	room *Room,
	participantID uint,
	eventType string,
	resources ...EventResource,
) {
	if room == nil {
		return
	}

	payload := NewEventPayload(eventType, room.Slug, room.Version, resources...)
	service.hub.Broadcast(payload)
	slog.Info("room mutation",
		"room_slug", room.Slug,
		"participant_id", participantID,
		"provider_id", room.ProviderID,
		"event_type", eventType,
		"version", room.Version,
	)
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
	climb *providers.ProviderClimb,
) (*RoomQueueEntry, error) {
	var existingCount int64
	if err := service.store.WithContext(ctx).Model(&RoomQueueEntry{}).
		Where("room_id = ? AND climb_id = ?", roomID, climb.ID).
		Count(&existingCount).Error; err != nil {
		return nil, err
	}
	if existingCount > 0 {
		return nil, fmt.Errorf("climb is already queued")
	}

	var createdEntry *RoomQueueEntry
	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		entry, err := service.ensureQueueEntryRecord(tx, roomID, participantID, climb)
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
	climb *providers.ProviderClimb,
) (*RoomQueueEntry, error) {
	climbJSON := mustEncodeProviderClimb(climb)
	var entry RoomQueueEntry
	err := tx.Where("room_id = ? AND climb_id = ?", roomID, climb.ID).First(&entry).Error
	if err == nil {
		if entry.ClimbJSON != climbJSON {
			if err := tx.Model(&entry).Update("climb_json", climbJSON).Error; err != nil {
				return nil, err
			}
			entry.ClimbJSON = climbJSON
		}
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
		ClimbID:              climb.ID,
		AddedByParticipantID: participantID,
		Status:               queueStatusQueued,
		Position:             maxPosition + 1,
		ClimbJSON:            climbJSON,
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
	if err := service.store.WithContext(ctx).Where("room_id = ?", viewer.Room.ID).
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
	voteCounts, _ := service.fistBumps.VoteData(viewer.Room.ID, 0)
	if len(voteCounts) == 0 {
		return nil, fmt.Errorf("there are no voted climbs to pick from")
	}

	topCount := 0
	for _, count := range voteCounts {
		if count > topCount {
			topCount = count
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

func decodeProviderClimb(raw string) *providers.ProviderClimb {
	if strings.TrimSpace(raw) == "" {
		return nil
	}

	var climb providers.ProviderClimb
	if err := json.Unmarshal([]byte(raw), &climb); err != nil {
		return nil
	}

	return &climb
}

func summaryProviderClimb(room *Room, climbID string, cachedJSON string) providers.ProviderClimb {
	if climb := decodeProviderClimb(cachedJSON); climb != nil {
		return *climb
	}

	providerID := ""
	if room != nil {
		providerID = room.ProviderID
	}

	externalID := climbID
	if providerID != "" && strings.HasPrefix(climbID, providerID+":") {
		externalID = strings.TrimPrefix(climbID, providerID+":")
	}

	return providers.ProviderClimb{
		ID:         climbID,
		ExternalID: externalID,
		ProviderID: providers.ProviderID(providerID),
		Name:       climbID,
	}
}

func mustEncodeSessionSummaryClimbs(climbs []SessionSummaryClimbView) string {
	if len(climbs) == 0 {
		return "[]"
	}

	raw, err := json.Marshal(climbs)
	if err != nil {
		return "[]"
	}
	return string(raw)
}

func decodeSessionSummaryClimbs(raw string) []SessionSummaryClimbView {
	if strings.TrimSpace(raw) == "" {
		return []SessionSummaryClimbView{}
	}

	var climbs []SessionSummaryClimbView
	if err := json.Unmarshal([]byte(raw), &climbs); err != nil {
		return []SessionSummaryClimbView{}
	}

	return climbs
}

func mustEncodeProviderClimb(climb *providers.ProviderClimb) string {
	if climb == nil {
		return ""
	}

	raw, err := json.Marshal(climb)
	if err != nil {
		return ""
	}

	return string(raw)
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

func normalizeParticipantRole(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case hostRole:
		return hostRole
	case coHostRole:
		return coHostRole
	default:
		return participantRole
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
