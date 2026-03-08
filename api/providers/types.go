package providers

import "context"

type ProviderID string

const (
	ProviderKilter ProviderID = "kilter"
	ProviderCrux   ProviderID = "crux"
)

type SecretPayload map[string]string

type ProviderConnectionState struct {
	ProviderID ProviderID        `json:"provider_id"`
	Metadata   map[string]string `json:"metadata,omitempty"`
	Connected  bool              `json:"connected"`
}

type SurfaceFilter struct {
	ParentID string
}

type ProviderSurface struct {
	ID          string            `json:"id"`
	Kind        string            `json:"kind"`
	Name        string            `json:"name"`
	Description string            `json:"description,omitempty"`
	ParentID    string            `json:"parent_id,omitempty"`
	Meta        map[string]string `json:"meta,omitempty"`
}

type ListClimbsInput struct {
	SurfaceID string
	Context   map[string]string
	Search    string
	Sort      string
	Cursor    string
	PageSize  int
}

type ClimbMedia struct {
	URL  string `json:"url"`
	Kind string `json:"kind"`
}

type HighlightedHold struct {
	Position int     `json:"position"`
	X        float64 `json:"x"`
	Y        float64 `json:"y"`
	Role     string  `json:"role"`
	Color    string  `json:"color"`
}

type ProviderClimb struct {
	ID               string            `json:"id"`
	ExternalID       string            `json:"external_id"`
	ProviderID       ProviderID        `json:"provider_id"`
	SurfaceID        string            `json:"surface_id"`
	Name             string            `json:"name"`
	Description      string            `json:"description,omitempty"`
	SetterName       string            `json:"setter_name,omitempty"`
	PrimaryGrade     string            `json:"primary_grade,omitempty"`
	SecondaryGrade   string            `json:"secondary_grade,omitempty"`
	CreatedAt        string            `json:"created_at,omitempty"`
	Popularity       int               `json:"popularity,omitempty"`
	Media            []ClimbMedia      `json:"media,omitempty"`
	HighlightedHolds []HighlightedHold `json:"highlighted_holds,omitempty"`
	Meta             map[string]string `json:"meta,omitempty"`
}

type PaginatedClimbs struct {
	Climbs     []ProviderClimb `json:"climbs"`
	HasMore    bool            `json:"has_more"`
	NextCursor string          `json:"next_cursor,omitempty"`
	PageSize   int             `json:"page_size"`
}

type Provider interface {
	ID() ProviderID
	ValidateConnection(ctx context.Context, secret SecretPayload) (map[string]string, error)
	ListSurfaces(ctx context.Context, secret SecretPayload, filters SurfaceFilter) ([]ProviderSurface, error)
	ListClimbs(ctx context.Context, secret SecretPayload, input ListClimbsInput) (*PaginatedClimbs, error)
	GetClimb(ctx context.Context, secret SecretPayload, input ListClimbsInput, climbID string) (*ProviderClimb, error)
	RefreshCatalog(ctx context.Context, secret SecretPayload, scope map[string]string) error
}
