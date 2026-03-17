package providers

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/config"
)

const cruxBaseURL = "https://www.cruxapp.ca"

type ProviderCacheEntry struct {
	ID         uint   `gorm:"primaryKey"`
	ProviderID string `gorm:"index:idx_provider_cache_key,unique"`
	CacheKey   string `gorm:"index:idx_provider_cache_key,unique"`
	Payload    string
	ExpiresAt  time.Time `gorm:"index"`
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

type CruxProvider struct {
	httpClient *http.Client
}

func NewCruxProvider() *CruxProvider {
	return &CruxProvider{
		httpClient: &http.Client{Timeout: 15 * time.Second},
	}
}

func (provider *CruxProvider) ID() ProviderID {
	return ProviderCrux
}

func (provider *CruxProvider) ValidateConnection(
	ctx context.Context,
	secret SecretPayload,
) (map[string]string, error) {
	token := normalizeCruxToken(secret["token"])
	if token == "" {
		return nil, fmt.Errorf("crux token is required")
	}

	var user cruxUser
	if err := provider.getJSON(ctx, token, "/api/v1/users/me", &user); err != nil {
		return nil, err
	}

	return map[string]string{
		"user_id": strconv.Itoa(user.ID),
		"name":    user.Name,
	}, nil
}

func (provider *CruxProvider) ListSurfaces(
	ctx context.Context,
	secret SecretPayload,
	filters SurfaceFilter,
) ([]ProviderSurface, error) {
	token := normalizeCruxToken(secret["token"])
	if token == "" {
		return nil, fmt.Errorf("crux token is required")
	}

	if filters.ParentID == "" {
		var user cruxUser
		if err := provider.getCachedJSON(ctx, token, "crux:user:me", 5*time.Minute, "/api/v1/users/me", &user); err != nil {
			return nil, err
		}

		seen := map[string]struct{}{}
		surfaces := make([]ProviderSurface, 0)
		for _, gym := range append(user.AdministratedGyms, user.ViewedGyms...) {
			if _, exists := seen[gym.URLSlug]; exists || gym.URLSlug == "" {
				continue
			}
			seen[gym.URLSlug] = struct{}{}
			surfaces = append(surfaces, ProviderSurface{
				ID:          gym.URLSlug,
				Kind:        "gym",
				Name:        gym.Name,
				Description: gym.Location,
				Meta: map[string]string{
					"gym_slug":  gym.URLSlug,
					"parent_id": gym.URLSlug,
				},
			})
		}
		sort.Slice(surfaces, func(i, j int) bool {
			return strings.ToLower(surfaces[i].Name) < strings.ToLower(surfaces[j].Name)
		})
		return surfaces, nil
	}

	var walls []cruxWall
	path := fmt.Sprintf("/api/v1/gyms/%s/gym_walls", filters.ParentID)
	if err := provider.getCachedJSON(ctx, token, "crux:gym:"+filters.ParentID+":walls", 5*time.Minute, path, &walls); err != nil {
		return nil, err
	}

	surfaces := make([]ProviderSurface, 0, len(walls))
	for _, wall := range walls {
		description := "Wall"
		if wall.AngleAdjustable {
			description = fmt.Sprintf(
				"Adjustable wall (%s-%s degrees)",
				intPointerString(wall.MinimumAngle),
				intPointerString(wall.MaximumAngle),
			)
		}
		surfaces = append(surfaces, ProviderSurface{
			ID:          strconv.Itoa(wall.ID),
			Kind:        "wall",
			Name:        wall.Name,
			Description: description,
			ParentID:    filters.ParentID,
			Meta: map[string]string{
				"gym_slug":         filters.ParentID,
				"parent_id":        filters.ParentID,
				"wall_id":          strconv.Itoa(wall.ID),
				"angle_adjustable": strconv.FormatBool(wall.AngleAdjustable),
			},
		})
	}

	return surfaces, nil
}

func (provider *CruxProvider) ListClimbs(
	ctx context.Context,
	secret SecretPayload,
	input ListClimbsInput,
) (*PaginatedClimbs, error) {
	token := normalizeCruxToken(secret["token"])
	if token == "" {
		return nil, fmt.Errorf("crux token is required")
	}

	gymSlug := strings.TrimSpace(input.Context["gym_slug"])
	if gymSlug == "" {
		gymSlug = strings.TrimSpace(input.SurfaceID)
	}
	if gymSlug == "" {
		return nil, fmt.Errorf("crux gym slug is required")
	}

	customKey := "crux:gym:" + gymSlug + ":climbs:custom"
	officialKey := "crux:gym:" + gymSlug + ":climbs:official"
	var customClimbs []cruxClimb
	if err := provider.getCachedJSON(
		ctx,
		token,
		customKey,
		5*time.Minute,
		fmt.Sprintf("/api/v1/gyms/%s/climbs/custom", gymSlug),
		&customClimbs,
	); err != nil {
		return nil, err
	}
	var officialClimbs []cruxClimb
	if err := provider.getCachedJSON(
		ctx,
		token,
		officialKey,
		5*time.Minute,
		fmt.Sprintf("/api/v1/gyms/%s/climbs/official", gymSlug),
		&officialClimbs,
	); err != nil {
		return nil, err
	}

	for index := range customClimbs {
		customClimbs[index].Source = "custom"
	}
	for index := range officialClimbs {
		officialClimbs[index].Source = "official"
	}

	allClimbs := append(customClimbs, officialClimbs...)
	filtered := make([]cruxClimb, 0, len(allClimbs))
	searchLower := strings.ToLower(strings.TrimSpace(input.Search))
	setterLower := strings.ToLower(strings.TrimSpace(input.Setter))
	gradeMinLower := strings.ToLower(strings.TrimSpace(input.GradeMin))
	gradeMaxLower := strings.ToLower(strings.TrimSpace(input.GradeMax))
	for _, climb := range allClimbs {
		if searchLower != "" && !strings.Contains(strings.ToLower(climb.Name), searchLower) &&
			!strings.Contains(strings.ToLower(stringPointerValue(climb.Description)), searchLower) {
			continue
		}
		if setterLower != "" && !strings.Contains(strings.ToLower(stringPointerValue(climb.SetterName)), setterLower) {
			continue
		}
		if gradeMinLower != "" || gradeMaxLower != "" {
			g := strings.ToLower(stringPointerValue(climb.Grade))
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

	sortCruxClimbs(filtered, input.Sort)

	pageSize := input.PageSize
	if pageSize <= 0 {
		pageSize = 10
	}

	offset, err := decodeOffsetCursor(input.Cursor)
	if err != nil {
		return nil, err
	}
	if offset > len(filtered) {
		offset = len(filtered)
	}
	end := offset + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}
	window := filtered[offset:end]

	var nextCursor string
	hasMore := end < len(filtered)
	if hasMore {
		nextCursor = encodeOffsetCursor(end)
	}

	return &PaginatedClimbs{
		Climbs:     mapCruxClimbs(window, gymSlug),
		HasMore:    hasMore,
		NextCursor: nextCursor,
		PageSize:   pageSize,
	}, nil
}

func (provider *CruxProvider) GetClimb(
	ctx context.Context,
	secret SecretPayload,
	input ListClimbsInput,
	climbID string,
) (*ProviderClimb, error) {
	token := normalizeCruxToken(secret["token"])
	if token == "" {
		return nil, fmt.Errorf("crux token is required")
	}

	externalID, err := parseCruxClimbID(climbID)
	if err != nil {
		return nil, err
	}

	var climb cruxClimb
	if err := provider.getCachedJSON(
		ctx,
		token,
		"crux:climb:"+strconv.Itoa(externalID),
		5*time.Minute,
		fmt.Sprintf("/api/v1/climbs/%d", externalID),
		&climb,
	); err != nil {
		return nil, err
	}

	gymSlug := strings.TrimSpace(input.Context["gym_slug"])
	if gymSlug == "" {
		gymSlug = strings.TrimSpace(climb.GymSlug)
	}
	if gymSlug != "" {
		provider.annotateCruxClimbSource(ctx, token, gymSlug, &climb)
	}

	mapped := mapCruxClimbs([]cruxClimb{climb}, gymSlug)
	if len(mapped) == 0 {
		return nil, fmt.Errorf("crux climb %s not found", climbID)
	}
	return &mapped[0], nil
}

func (provider *CruxProvider) RefreshCatalog(
	ctx context.Context,
	secret SecretPayload,
	scope map[string]string,
) error {
	token := normalizeCruxToken(secret["token"])
	if token == "" {
		return fmt.Errorf("crux token is required")
	}

	if config.AppDB == nil {
		return nil
	}

	gymSlug := strings.TrimSpace(scope["gym_slug"])
	query := config.AppDB.WithContext(ctx).Where("provider_id = ?", string(ProviderCrux))
	if gymSlug != "" {
		query = query.Where("cache_key LIKE ?", "%"+gymSlug+"%")
	}

	return query.Delete(&ProviderCacheEntry{}).Error
}

func (provider *CruxProvider) getCachedJSON(
	ctx context.Context,
	token string,
	cacheKey string,
	ttl time.Duration,
	path string,
	target any,
) error {
	if config.AppDB != nil {
		var entry ProviderCacheEntry
		err := config.AppDB.WithContext(ctx).Where(
			"provider_id = ? AND cache_key = ? AND expires_at > ?",
			string(ProviderCrux),
			cacheKey,
			time.Now().UTC(),
		).First(&entry).Error
		if err == nil {
			RecordCacheHit(ProviderCrux)
			return json.Unmarshal([]byte(entry.Payload), target)
		}
	}
	RecordCacheMiss(ProviderCrux)

	var raw json.RawMessage
	if err := provider.getJSON(ctx, token, path, &raw); err != nil {
		return err
	}
	if err := json.Unmarshal(raw, target); err != nil {
		return fmt.Errorf("decode crux payload %s: %w", path, err)
	}

	if config.AppDB != nil {
		entry := ProviderCacheEntry{
			ProviderID: string(ProviderCrux),
			CacheKey:   cacheKey,
			Payload:    string(raw),
			ExpiresAt:  time.Now().UTC().Add(ttl),
		}
		_ = config.AppDB.WithContext(ctx).Where(
			ProviderCacheEntry{ProviderID: entry.ProviderID, CacheKey: entry.CacheKey},
		).Assign(entry).FirstOrCreate(&entry).Error
		RecordCacheWrite(ProviderCrux)
	}

	return nil
}

func (provider *CruxProvider) getJSON(
	ctx context.Context,
	token string,
	path string,
	target any,
) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, cruxBaseURL+path, nil)
	if err != nil {
		return fmt.Errorf("create crux request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Accept", "application/json")

	response, err := provider.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("request crux %s: %w", path, err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(io.LimitReader(response.Body, 512))
		return fmt.Errorf("crux %s returned %s: %s", path, response.Status, string(bodyBytes))
	}

	if err := json.NewDecoder(response.Body).Decode(target); err != nil {
		return fmt.Errorf("decode crux response %s: %w", path, err)
	}

	return nil
}

type cruxUser struct {
	ID                int       `json:"id"`
	Name              string    `json:"name"`
	AdministratedGyms []cruxGym `json:"administrated_gyms"`
	ViewedGyms        []cruxGym `json:"viewed_gyms"`
}

type cruxGym struct {
	ID       int     `json:"id"`
	Name     string  `json:"name"`
	URLSlug  string  `json:"url_slug"`
	Location string  `json:"location"`
	IconURL  *string `json:"icon_url"`
}

type cruxWall struct {
	ID              int     `json:"id"`
	Name            string  `json:"name"`
	AngleAdjustable bool    `json:"angle_adjustable"`
	MinimumAngle    *int    `json:"minimum_angle"`
	MaximumAngle    *int    `json:"maximum_angle"`
	ImageURL        *string `json:"image_url"`
}

type cruxClimb struct {
	ID            int     `json:"id"`
	Name          string  `json:"name"`
	Description   *string `json:"description"`
	Grade         *string `json:"grade"`
	Angle         *string `json:"angle"`
	Color         *string `json:"color"`
	FootRules     *string `json:"foot_rules"`
	SetterName    *string `json:"setter_name"`
	CreatedAt     string  `json:"created_at"`
	ImageURL      *string `json:"image_url"`
	UneditedImage *string `json:"unedited_image_url"`
	NumberOfSends int     `json:"number_of_sends"`
	GymSlug       string  `json:"gym_slug"`
	GymName       string  `json:"gym_name"`
	Source        string  `json:"-"`
}

func sortCruxClimbs(climbs []cruxClimb, sortKey string) {
	if sortKey == "newest" {
		sort.SliceStable(climbs, func(i, j int) bool {
			return climbs[i].CreatedAt > climbs[j].CreatedAt
		})
		return
	}

	sort.SliceStable(climbs, func(i, j int) bool {
		if climbs[i].NumberOfSends == climbs[j].NumberOfSends {
			return climbs[i].CreatedAt > climbs[j].CreatedAt
		}
		return climbs[i].NumberOfSends > climbs[j].NumberOfSends
	})
}

func mapCruxClimbs(climbs []cruxClimb, fallbackGymSlug string) []ProviderClimb {
	mapped := make([]ProviderClimb, 0, len(climbs))
	for _, climb := range climbs {
		gymSlug := climb.GymSlug
		if gymSlug == "" {
			gymSlug = fallbackGymSlug
		}
		mediaURL := stringPointerValue(climb.ImageURL)
		if mediaURL == "" {
			mediaURL = stringPointerValue(climb.UneditedImage)
		}
		media := []ClimbMedia{}
		if mediaURL != "" {
			media = append(media, ClimbMedia{
				URL:  mediaURL,
				Kind: "image",
			})
		}

		mapped = append(mapped, ProviderClimb{
			ID:             fmt.Sprintf("crux:%d", climb.ID),
			ExternalID:     strconv.Itoa(climb.ID),
			ProviderID:     ProviderCrux,
			SurfaceID:      gymSlug,
			Name:           climb.Name,
			Description:    stringPointerValue(climb.Description),
			SetterName:     stringPointerValue(climb.SetterName),
			PrimaryGrade:   stringPointerValue(climb.Grade),
			SecondaryGrade: stringPointerValue(climb.Angle),
			CreatedAt:      climb.CreatedAt,
			Popularity:     climb.NumberOfSends,
			Media:          media,
			Meta: map[string]string{
				"gym_slug":     gymSlug,
				"gym_name":     climb.GymName,
				"source":       climb.Source,
				"source_label": cruxSourceLabel(climb.Source),
				"color":        stringPointerValue(climb.Color),
				"foot_rules":   stringPointerValue(climb.FootRules),
			},
		})
	}

	return mapped
}

func intPointerString(value *int) string {
	if value == nil {
		return "?"
	}
	return strconv.Itoa(*value)
}

func stringPointerValue(value *string) string {
	if value == nil {
		return ""
	}

	return strings.TrimSpace(*value)
}

func cruxSourceLabel(source string) string {
	switch strings.TrimSpace(strings.ToLower(source)) {
	case "official":
		return "Official"
	case "custom":
		return "Custom"
	default:
		return ""
	}
}

func (provider *CruxProvider) annotateCruxClimbSource(
	ctx context.Context,
	token string,
	gymSlug string,
	climb *cruxClimb,
) {
	if climb == nil || gymSlug == "" {
		return
	}

	customKey := "crux:gym:" + gymSlug + ":climbs:custom"
	var customClimbs []cruxClimb
	if err := provider.getCachedJSON(
		ctx,
		token,
		customKey,
		5*time.Minute,
		fmt.Sprintf("/api/v1/gyms/%s/climbs/custom", gymSlug),
		&customClimbs,
	); err == nil {
		for _, candidate := range customClimbs {
			if candidate.ID == climb.ID {
				climb.Source = "custom"
				return
			}
		}
	}

	officialKey := "crux:gym:" + gymSlug + ":climbs:official"
	var officialClimbs []cruxClimb
	if err := provider.getCachedJSON(
		ctx,
		token,
		officialKey,
		5*time.Minute,
		fmt.Sprintf("/api/v1/gyms/%s/climbs/official", gymSlug),
		&officialClimbs,
	); err == nil {
		for _, candidate := range officialClimbs {
			if candidate.ID == climb.ID {
				climb.Source = "official"
				return
			}
		}
	}
}

func normalizeCruxToken(rawToken string) string {
	token := strings.TrimSpace(rawToken)
	if strings.HasPrefix(strings.ToLower(token), "bearer ") {
		return strings.TrimSpace(token[len("bearer "):])
	}

	return token
}

func encodeOffsetCursor(offset int) string {
	return base64.RawURLEncoding.EncodeToString([]byte(strconv.Itoa(offset)))
}

func decodeOffsetCursor(cursor string) (int, error) {
	if strings.TrimSpace(cursor) == "" {
		return 0, nil
	}

	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return 0, fmt.Errorf("invalid crux cursor: %w", err)
	}
	offset, err := strconv.Atoi(string(raw))
	if err != nil {
		return 0, fmt.Errorf("invalid crux cursor offset: %w", err)
	}
	if offset < 0 {
		return 0, fmt.Errorf("invalid crux cursor offset %d", offset)
	}
	return offset, nil
}

func parseCruxClimbID(climbID string) (int, error) {
	var externalID int
	if _, err := fmt.Sscanf(climbID, "crux:%d", &externalID); err != nil {
		return 0, fmt.Errorf("invalid crux climb id %q", climbID)
	}
	return externalID, nil
}
