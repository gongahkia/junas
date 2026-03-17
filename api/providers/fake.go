package providers

import (
	"context"
	"encoding/base64"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

type FakeProvider struct {
	Surfaces []ProviderSurface
	Climbs   []ProviderClimb
}

func NewFakeProvider() *FakeProvider {
	return &FakeProvider{
		Surfaces: []ProviderSurface{
			{ID: "gym-test", Kind: "gym", Name: "Test Gym"},
			{
				ID:       "wall-alpha",
				Kind:     "wall",
				Name:     "Alpha Wall",
				ParentID: "gym-test",
				Meta: map[string]string{
					"gym_slug":  "gym-test",
					"parent_id": "gym-test",
				},
			},
			{
				ID:       "wall-beta",
				Kind:     "wall",
				Name:     "Beta Wall",
				ParentID: "gym-test",
				Meta: map[string]string{
					"gym_slug":  "gym-test",
					"parent_id": "gym-test",
				},
			},
		},
		Climbs: []ProviderClimb{
			{
				ID:             "test:alpha",
				ExternalID:     "alpha",
				ProviderID:     ProviderTest,
				SurfaceID:      "wall-alpha",
				Name:           "Alpha Arete",
				Description:    "Compression on small holds",
				SetterName:     "Setter A",
				PrimaryGrade:   "V5",
				SecondaryGrade: "6C+",
				CreatedAt:      "2026-01-03T00:00:00Z",
				Popularity:     8,
				Media:          []ClimbMedia{{URL: "/api/images/alpha.png", Kind: "image"}},
			},
			{
				ID:             "test:beta",
				ExternalID:     "beta",
				ProviderID:     ProviderTest,
				SurfaceID:      "wall-alpha",
				Name:           "Beta Crimp",
				Description:    "Precise crimp climbing",
				SetterName:     "Setter B",
				PrimaryGrade:   "V6",
				SecondaryGrade: "7A",
				CreatedAt:      "2026-02-10T00:00:00Z",
				Popularity:     15,
				Media:          []ClimbMedia{{URL: "/api/images/beta.png", Kind: "image"}},
			},
			{
				ID:             "test:gamma",
				ExternalID:     "gamma",
				ProviderID:     ProviderTest,
				SurfaceID:      "wall-beta",
				Name:           "Gamma Slab",
				Description:    "Slow and technical",
				SetterName:     "Setter C",
				PrimaryGrade:   "V3",
				SecondaryGrade: "6A",
				CreatedAt:      "2026-03-01T00:00:00Z",
				Popularity:     4,
				Media:          []ClimbMedia{{URL: "/api/images/gamma.png", Kind: "image"}},
			},
		},
	}
}

func (provider *FakeProvider) ID() ProviderID {
	return ProviderTest
}

func (provider *FakeProvider) ValidateConnection(_ context.Context, secret SecretPayload) (map[string]string, error) {
	if strings.TrimSpace(secret["token"]) == "" {
		return nil, fmt.Errorf("token is required")
	}
	return map[string]string{
		"account_label": "Test Host",
	}, nil
}

func (provider *FakeProvider) ListSurfaces(
	_ context.Context,
	secret SecretPayload,
	filters SurfaceFilter,
) ([]ProviderSurface, error) {
	if err := requireFakeToken(secret); err != nil {
		return nil, err
	}

	if filters.ParentID == "" {
		filtered := make([]ProviderSurface, 0)
		for _, surface := range provider.Surfaces {
			if surface.ParentID == "" {
				filtered = append(filtered, surface)
			}
		}
		return filtered, nil
	}

	filtered := make([]ProviderSurface, 0)
	for _, surface := range provider.Surfaces {
		if surface.ParentID == filters.ParentID {
			filtered = append(filtered, surface)
		}
	}
	return filtered, nil
}

func (provider *FakeProvider) ListClimbs(
	_ context.Context,
	secret SecretPayload,
	input ListClimbsInput,
) (*PaginatedClimbs, error) {
	if err := requireFakeToken(secret); err != nil {
		return nil, err
	}

	filtered := make([]ProviderClimb, 0)
	query := strings.ToLower(strings.TrimSpace(input.Search))
	gradeMinLower := strings.ToLower(strings.TrimSpace(input.GradeMin))
	gradeMaxLower := strings.ToLower(strings.TrimSpace(input.GradeMax))
	for _, climb := range provider.Climbs {
		if input.SurfaceID != "" && climb.SurfaceID != input.SurfaceID {
			continue
		}
		if query != "" &&
			!strings.Contains(strings.ToLower(climb.Name), query) &&
			!strings.Contains(strings.ToLower(climb.Description), query) &&
			!strings.Contains(strings.ToLower(climb.SetterName), query) {
			continue
		}
		if gradeMinLower != "" || gradeMaxLower != "" {
			g := strings.ToLower(climb.PrimaryGrade)
			if g == "" {
				continue
			}
			if gradeMinLower != "" && g < gradeMinLower {
				continue
			}
			if gradeMaxLower != "" && g > gradeMaxLower {
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
	offset := decodeFakeOffset(input.Cursor)
	if offset > len(filtered) {
		offset = len(filtered)
	}
	end := offset + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	response := &PaginatedClimbs{
		Climbs:   append([]ProviderClimb{}, filtered[offset:end]...),
		HasMore:  end < len(filtered),
		PageSize: pageSize,
	}
	if response.HasMore {
		response.NextCursor = encodeFakeOffset(end)
	}
	return response, nil
}

func (provider *FakeProvider) GetClimb(
	_ context.Context,
	secret SecretPayload,
	input ListClimbsInput,
	climbID string,
) (*ProviderClimb, error) {
	if err := requireFakeToken(secret); err != nil {
		return nil, err
	}

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

func (provider *FakeProvider) RefreshCatalog(_ context.Context, _ SecretPayload, _ map[string]string) error {
	return nil
}

func requireFakeToken(secret SecretPayload) error {
	if strings.TrimSpace(secret["token"]) == "" {
		return fmt.Errorf("token is required")
	}
	return nil
}

func encodeFakeOffset(offset int) string {
	return base64.RawURLEncoding.EncodeToString([]byte(strconv.Itoa(offset)))
}

func decodeFakeOffset(cursor string) int {
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

func RegisterTestProviderIfEnabled(enabled bool) {
	if enabled {
		Register(NewFakeProvider())
	}
}
