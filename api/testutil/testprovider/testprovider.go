package testprovider

import (
	"context"
	"encoding/base64"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/lczm/kilter-together/api/providers"
)

type Provider struct {
	IDValue  providers.ProviderID
	Surfaces []providers.ProviderSurface
	Climbs   []providers.ProviderClimb
}

func New(id providers.ProviderID) *Provider {
	prefix := string(id)
	return &Provider{
		IDValue: id,
		Surfaces: []providers.ProviderSurface{
			{ID: "wall-alpha", Kind: "wall", Name: "Alpha Wall"},
			{ID: "wall-beta", Kind: "wall", Name: "Beta Wall"},
		},
		Climbs: []providers.ProviderClimb{
			{
				ID:             prefix + ":alpha",
				ExternalID:     "alpha",
				ProviderID:     id,
				SurfaceID:      "wall-alpha",
				Name:           "Alpha Arete",
				Description:    "Compression on small holds",
				SetterName:     "Setter A",
				PrimaryGrade:   "V5",
				SecondaryGrade: "6C+",
				CreatedAt:      "2026-01-03T00:00:00Z",
				Popularity:     8,
				Media: []providers.ClimbMedia{
					{URL: "/images/alpha.png", Kind: "image"},
				},
			},
			{
				ID:             prefix + ":beta",
				ExternalID:     "beta",
				ProviderID:     id,
				SurfaceID:      "wall-alpha",
				Name:           "Beta Crimp",
				Description:    "Precise crimp climbing",
				SetterName:     "Setter B",
				PrimaryGrade:   "V6",
				SecondaryGrade: "7A",
				CreatedAt:      "2026-02-10T00:00:00Z",
				Popularity:     15,
				Media: []providers.ClimbMedia{
					{URL: "/images/beta.png", Kind: "image"},
				},
			},
			{
				ID:             prefix + ":gamma",
				ExternalID:     "gamma",
				ProviderID:     id,
				SurfaceID:      "wall-beta",
				Name:           "Gamma Slab",
				Description:    "Slow and technical",
				SetterName:     "Setter C",
				PrimaryGrade:   "V3",
				SecondaryGrade: "6A",
				CreatedAt:      "2026-03-01T00:00:00Z",
				Popularity:     4,
				Media: []providers.ClimbMedia{
					{URL: "/images/gamma.png", Kind: "image"},
				},
			},
		},
	}
}

func (provider *Provider) ID() providers.ProviderID {
	return provider.IDValue
}

func (provider *Provider) ValidateConnection(_ context.Context, secret providers.SecretPayload) (map[string]string, error) {
	if strings.TrimSpace(secret["token"]) == "" {
		return nil, fmt.Errorf("token is required")
	}
	return map[string]string{
		"account_label": "Test Host",
	}, nil
}

func (provider *Provider) ListSurfaces(
	_ context.Context,
	_ providers.SecretPayload,
	filters providers.SurfaceFilter,
) ([]providers.ProviderSurface, error) {
	if filters.ParentID == "" {
		return append([]providers.ProviderSurface{}, provider.Surfaces...), nil
	}

	filtered := make([]providers.ProviderSurface, 0)
	for _, surface := range provider.Surfaces {
		if surface.ParentID == filters.ParentID {
			filtered = append(filtered, surface)
		}
	}
	return filtered, nil
}

func (provider *Provider) ListClimbs(
	_ context.Context,
	_ providers.SecretPayload,
	input providers.ListClimbsInput,
) (*providers.PaginatedClimbs, error) {
	filtered := make([]providers.ProviderClimb, 0)
	query := strings.ToLower(strings.TrimSpace(input.Search))
	for _, climb := range provider.Climbs {
		if input.SurfaceID != "" && climb.SurfaceID != input.SurfaceID {
			continue
		}
		if query != "" {
			if !strings.Contains(strings.ToLower(climb.Name), query) &&
				!strings.Contains(strings.ToLower(climb.Description), query) &&
				!strings.Contains(strings.ToLower(climb.SetterName), query) {
				continue
			}
		}
		filtered = append(filtered, climb)
	}

	sort.Slice(filtered, func(i, j int) bool {
		if strings.EqualFold(input.Sort, "newest") {
			if filtered[i].CreatedAt == filtered[j].CreatedAt {
				return filtered[i].ID < filtered[j].ID
			}
			return filtered[i].CreatedAt > filtered[j].CreatedAt
		}
		if filtered[i].Popularity == filtered[j].Popularity {
			return filtered[i].ID < filtered[j].ID
		}
		return filtered[i].Popularity > filtered[j].Popularity
	})

	pageSize := input.PageSize
	if pageSize <= 0 {
		pageSize = 10
	}
	offset := decodeOffset(input.Cursor)
	if offset > len(filtered) {
		offset = len(filtered)
	}
	end := offset + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	response := &providers.PaginatedClimbs{
		Climbs:   append([]providers.ProviderClimb{}, filtered[offset:end]...),
		HasMore:  end < len(filtered),
		PageSize: pageSize,
	}
	if response.HasMore {
		response.NextCursor = encodeOffset(end)
	}
	return response, nil
}

func (provider *Provider) GetClimb(
	_ context.Context,
	_ providers.SecretPayload,
	input providers.ListClimbsInput,
	climbID string,
) (*providers.ProviderClimb, error) {
	for _, climb := range provider.Climbs {
		if climb.ID != climbID {
			continue
		}
		if input.SurfaceID != "" && climb.SurfaceID != input.SurfaceID {
			return nil, fmt.Errorf("climb %s not found on surface %s", climbID, input.SurfaceID)
		}
		copyClimb := climb
		return &copyClimb, nil
	}
	return nil, fmt.Errorf("climb %s not found", climbID)
}

func (provider *Provider) RefreshCatalog(_ context.Context, _ providers.SecretPayload, _ map[string]string) error {
	return nil
}

func encodeOffset(offset int) string {
	return base64.RawURLEncoding.EncodeToString([]byte(strconv.Itoa(offset)))
}

func decodeOffset(cursor string) int {
	if strings.TrimSpace(cursor) == "" {
		return 0
	}
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return 0
	}
	offset, err := strconv.Atoi(string(raw))
	if err != nil || offset < 0 {
		return 0
	}
	return offset
}
