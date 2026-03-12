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
	coHostRole      = "co_host"
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
	AssistantMode      string `gorm:"not null;default:manual"`
	SurfaceID          string
	SurfaceKind        string
	SurfaceName        string
	SurfaceDescription string
	SurfaceContextJSON string
	CurrentClimbID     string
	CurrentClimbJSON   string
	FistBumpsEnabled   bool      `gorm:"column:emoji_reactions_enabled;not null"`
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

type RoomQueueEntry struct {
	ID                   uint   `gorm:"primaryKey"`
	RoomID               uint   `gorm:"index:idx_room_queue_climb,unique;index;not null"`
	ClimbID              string `gorm:"index:idx_room_queue_climb,unique;not null"`
	AddedByParticipantID uint   `gorm:"index;not null"`
	Status               string `gorm:"index;not null"`
	Position             int    `gorm:"index;not null"`
	ClimbJSON            string
	CreatedAt            time.Time
	UpdatedAt            time.Time
}

type RoomFinalistEntry struct {
	ID                   uint   `gorm:"primaryKey"`
	RoomID               uint   `gorm:"index:idx_room_finalist_climb,unique;index;not null"`
	ClimbID              string `gorm:"index:idx_room_finalist_climb,unique;not null"`
	AddedByParticipantID uint   `gorm:"index;not null"`
	Position             int    `gorm:"index;not null"`
	ClimbJSON            string
	CreatedAt            time.Time
	UpdatedAt            time.Time
}

type RoomSessionSummary struct {
	ID               uint   `gorm:"primaryKey"`
	RoomID           uint   `gorm:"uniqueIndex;not null"`
	RoomSlug         string `gorm:"index;not null"`
	RoomName         string
	ProviderID       string `gorm:"index;not null"`
	SurfaceName      string
	SurfaceKind      string
	ParticipantCount int
	RecapShareID     string `gorm:"uniqueIndex"`
	TopVotedJSON     string
	FinalQueueJSON   string
	FinalistsJSON    string
	ClosedAt         time.Time `gorm:"index;not null"`
	CreatedAt        time.Time
	UpdatedAt        time.Time
}

type AnalyticsEvent struct {
	ID             uint   `gorm:"primaryKey"`
	RoomID         *uint  `gorm:"index"`
	RoomSlug       string `gorm:"index"`
	EventName      string `gorm:"index;not null"`
	Source         string `gorm:"index;not null"`
	ViewerRole     string `gorm:"index"`
	Route          string
	PropertiesJSON string
	CreatedAt      time.Time `gorm:"index;not null"`
}

type RoomSessionRecap struct {
	ID          uint      `gorm:"primaryKey"`
	RoomID      uint      `gorm:"uniqueIndex;not null"`
	ShareID     string    `gorm:"uniqueIndex;not null"`
	RoomSlug    string    `gorm:"index;not null"`
	PayloadJSON string    `gorm:"not null"`
	ClosedAt    time.Time `gorm:"index;not null"`
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

type SoloPlanSnapshot struct {
	ID          uint   `gorm:"primaryKey"`
	ShareID     string `gorm:"uniqueIndex;not null"`
	ProviderID  string `gorm:"index;not null"`
	Title       string `gorm:"not null"`
	Notes       string
	SurfaceID   string
	SurfaceName string
	SurfaceKind string
	ContextJSON string
	FiltersJSON string
	ClimbsJSON  string `gorm:"not null"`
	OpenPath    string
	CreatedBy   string
	CreatedAt   time.Time `gorm:"index;not null"`
	UpdatedAt   time.Time
}

type FeedbackEntry struct {
	ID           uint   `gorm:"primaryKey"`
	RoomID       *uint  `gorm:"index"`
	RoomSlug     string `gorm:"index"`
	ShareID      string `gorm:"index"`
	PromptFamily string `gorm:"index;not null"`
	Sentiment    string `gorm:"not null"`
	Message      string
	Route        string
	MetadataJSON string
	CreatedAt    time.Time `gorm:"index;not null"`
}

type ParticipantView struct {
	ID          uint   `json:"id"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
	Status      string `json:"status"`
	IsOnline    bool   `json:"is_online"`
}

type PermissionView struct {
	ManageSession      bool `json:"manage_session"`
	ManageSurface      bool `json:"manage_surface"`
	ManageQueue        bool `json:"manage_queue"`
	ManageFinalists    bool `json:"manage_finalists"`
	EditRoomSettings   bool `json:"edit_room_settings"`
	ManageParticipants bool `json:"manage_participants"`
	AssignCoHosts      bool `json:"assign_co_hosts"`
	CloseRoom          bool `json:"close_room"`
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

type SessionSummaryClimbView struct {
	Position  int                     `json:"position,omitempty"`
	Status    string                  `json:"status,omitempty"`
	AddedBy   string                  `json:"added_by,omitempty"`
	VoteCount int                     `json:"vote_count,omitempty"`
	Climb     providers.ProviderClimb `json:"climb"`
}

type SessionSummaryView struct {
	RoomSlug         string                    `json:"room_slug"`
	RoomName         string                    `json:"room_name,omitempty"`
	ProviderID       providers.ProviderID      `json:"provider_id"`
	SurfaceName      string                    `json:"surface_name,omitempty"`
	SurfaceKind      string                    `json:"surface_kind,omitempty"`
	ParticipantCount int                       `json:"participant_count"`
	RecapShareID     string                    `json:"recap_share_id,omitempty"`
	ClosedAt         time.Time                 `json:"closed_at"`
	TopVoted         []SessionSummaryClimbView `json:"top_voted"`
	FinalQueue       []SessionSummaryClimbView `json:"final_queue"`
	Finalists        []SessionSummaryClimbView `json:"finalists"`
}

type AssistantSuggestionView struct {
	Source     string                  `json:"source"`
	ReadyCount int                     `json:"ready_count"`
	Climb      providers.ProviderClimb `json:"climb"`
}

type AssistantStateView struct {
	Mode       string                   `json:"mode"`
	Message    string                   `json:"message,omitempty"`
	Suggestion *AssistantSuggestionView `json:"suggestion,omitempty"`
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
	Slug             string                            `json:"slug"`
	RoomName         string                            `json:"room_name,omitempty"`
	Status           string                            `json:"status"`
	ProviderID       providers.ProviderID              `json:"provider_id"`
	Version          int64                             `json:"version"`
	Surface          *providers.ProviderSurface        `json:"surface,omitempty"`
	Connection       providers.ProviderConnectionState `json:"connection"`
	CurrentClimb     *providers.ProviderClimb          `json:"current_climb,omitempty"`
	Participants     []ParticipantView                 `json:"participants"`
	Finalists        []FinalistEntryView               `json:"finalists"`
	Queue            []QueueEntryView                  `json:"queue"`
	VoteCounts       map[string]int                    `json:"vote_counts"`
	MyVotes          []string                          `json:"my_votes"`
	FistBumpsEnabled bool                              `json:"fist_bumps_enabled"`
	CanManage        bool                              `json:"can_manage"`
	Permissions      PermissionView                    `json:"permissions"`
	DisplayName      string                            `json:"display_name,omitempty"`
	Assistant        AssistantStateView                `json:"assistant"`
}

type EventPayload struct {
	Type      string          `json:"type"`
	RoomSlug  string          `json:"room_slug"`
	Version   int64           `json:"version"`
	Resources []EventResource `json:"resources,omitempty"`
}
