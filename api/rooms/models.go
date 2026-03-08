package rooms

import (
	"time"

	"github.com/lczm/kilter-together/api/providers"
)

const (
	HostCookieName        = "kt_host_session"
	ParticipantCookieName = "kt_participant_session"

	roomStatusOpen   = "open"
	roomStatusClosed = "closed"

	queueStatusQueued  = "queued"
	queueStatusNext    = "next"
	queueStatusCurrent = "current"
	queueStatusDone    = "done"

	hostRole        = "host"
	participantRole = "participant"

	participantStatusWatching = "watching"
	participantStatusReady    = "ready"
	participantStatusResting  = "resting"
	participantStatusAway     = "away"
)

type Room struct {
	ID                 uint   `gorm:"primaryKey"`
	Slug               string `gorm:"uniqueIndex;not null"`
	Name               string `gorm:"index"`
	ProviderID         string `gorm:"index;not null"`
	Status             string `gorm:"index;not null"`
	SurfaceID          string
	SurfaceKind        string
	SurfaceName        string
	SurfaceDescription string
	SurfaceContextJSON string
	CurrentClimbID     string
	Version            int64     `gorm:"not null;default:1"`
	LastActiveAt       time.Time `gorm:"index;not null"`
	ClosedAt           *time.Time
	CreatedAt          time.Time
	UpdatedAt          time.Time
}

type RoomParticipant struct {
	ID          uint      `gorm:"primaryKey"`
	RoomID      uint      `gorm:"index:idx_room_display_name,unique;not null"`
	DisplayName string    `gorm:"index:idx_room_display_name,unique;not null"`
	Role        string    `gorm:"index;not null"`
	Status      string    `gorm:"index;not null;default:watching"`
	LastSeenAt  time.Time `gorm:"index;not null"`
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

type RoomSession struct {
	ID            string    `gorm:"primaryKey"`
	RoomID        uint      `gorm:"index;not null"`
	ParticipantID uint      `gorm:"index;not null"`
	Role          string    `gorm:"index;not null"`
	ExpiresAt     time.Time `gorm:"index;not null"`
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

type RoomProviderConnection struct {
	ID               uint   `gorm:"primaryKey"`
	RoomID           uint   `gorm:"uniqueIndex;not null"`
	ProviderID       string `gorm:"index;not null"`
	SecretCiphertext string `gorm:"not null"`
	MetadataJSON     string
	LastValidatedAt  time.Time `gorm:"index;not null"`
	CreatedAt        time.Time
	UpdatedAt        time.Time
}

type RoomVote struct {
	ID            uint   `gorm:"primaryKey"`
	RoomID        uint   `gorm:"index:idx_room_vote_unique,unique;not null"`
	ParticipantID uint   `gorm:"index:idx_room_vote_unique,unique;not null"`
	ClimbID       string `gorm:"index:idx_room_vote_unique,unique;not null"`
	CreatedAt     time.Time
}

type RoomQueueEntry struct {
	ID                   uint   `gorm:"primaryKey"`
	RoomID               uint   `gorm:"index:idx_room_queue_climb,unique;index;not null"`
	ClimbID              string `gorm:"index:idx_room_queue_climb,unique;not null"`
	AddedByParticipantID uint   `gorm:"index;not null"`
	Status               string `gorm:"index;not null"`
	Position             int    `gorm:"index;not null"`
	CreatedAt            time.Time
	UpdatedAt            time.Time
}

type RoomFinalistEntry struct {
	ID                   uint   `gorm:"primaryKey"`
	RoomID               uint   `gorm:"index:idx_room_finalist_climb,unique;index;not null"`
	ClimbID              string `gorm:"index:idx_room_finalist_climb,unique;not null"`
	AddedByParticipantID uint   `gorm:"index;not null"`
	Position             int    `gorm:"index;not null"`
	CreatedAt            time.Time
	UpdatedAt            time.Time
}

type ParticipantView struct {
	ID          uint   `json:"id"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
	Status      string `json:"status"`
	IsOnline    bool   `json:"is_online"`
}

type QueueEntryView struct {
	ID       uint                    `json:"id"`
	Status   string                  `json:"status"`
	Position int                     `json:"position"`
	AddedBy  string                  `json:"added_by"`
	Climb    providers.ProviderClimb `json:"climb"`
}

type FinalistEntryView struct {
	ID       uint                    `json:"id"`
	Position int                     `json:"position"`
	AddedBy  string                  `json:"added_by"`
	Climb    providers.ProviderClimb `json:"climb"`
}

type CatalogClimbsResponse struct {
	Climbs     []providers.ProviderClimb `json:"climbs"`
	HasMore    bool                      `json:"has_more"`
	NextCursor string                    `json:"next_cursor,omitempty"`
	PageSize   int                       `json:"page_size"`
	VoteCounts map[string]int            `json:"vote_counts"`
	MyVotes    []string                  `json:"my_votes"`
}

type CatalogClimbResponse struct {
	Climb     providers.ProviderClimb `json:"climb"`
	VoteCount int                     `json:"vote_count"`
	MyVote    bool                    `json:"my_vote"`
	IsQueued  bool                    `json:"is_queued"`
}

type RoomSnapshot struct {
	Slug         string                            `json:"slug"`
	RoomName     string                            `json:"room_name,omitempty"`
	Status       string                            `json:"status"`
	ProviderID   providers.ProviderID              `json:"provider_id"`
	Version      int64                             `json:"version"`
	Surface      *providers.ProviderSurface        `json:"surface,omitempty"`
	Connection   providers.ProviderConnectionState `json:"connection"`
	CurrentClimb *providers.ProviderClimb          `json:"current_climb,omitempty"`
	Participants []ParticipantView                 `json:"participants"`
	Finalists    []FinalistEntryView               `json:"finalists"`
	Queue        []QueueEntryView                  `json:"queue"`
	VoteCounts   map[string]int                    `json:"vote_counts"`
	MyVotes      []string                          `json:"my_votes"`
	CanManage    bool                              `json:"can_manage"`
	DisplayName  string                            `json:"display_name,omitempty"`
}

type EventPayload struct {
	Type     string `json:"type"`
	RoomSlug string `json:"room_slug"`
	Version  int64  `json:"version"`
}
