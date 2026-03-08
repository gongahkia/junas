package providers

import (
	"context"
	"fmt"
	"path/filepath"
	"strconv"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/models"
)

type KilterProvider struct{}

func NewKilterProvider() *KilterProvider {
	return &KilterProvider{}
}

func (provider *KilterProvider) ID() ProviderID {
	return ProviderKilter
}

func (provider *KilterProvider) ValidateConnection(
	ctx context.Context,
	secret SecretPayload,
) (map[string]string, error) {
	username := secret["username"]
	password := secret["password"]
	if username == "" || password == "" {
		return nil, fmt.Errorf("kilter username and password are required")
	}

	if _, err := bootstrap.Login(ctx, username, password); err != nil {
		return nil, err
	}

	return map[string]string{
		"username": username,
	}, nil
}

func (provider *KilterProvider) ListSurfaces(
	context.Context,
	SecretPayload,
	SurfaceFilter,
) ([]ProviderSurface, error) {
	boards, err := models.GetBoardOptions()
	if err != nil {
		return nil, err
	}

	surfaces := make([]ProviderSurface, 0, len(boards))
	for _, board := range boards {
		surfaces = append(surfaces, ProviderSurface{
			ID:          strconv.Itoa(int(board.ID)),
			Kind:        "board",
			Name:        board.Name,
			Description: board.KilterName,
			Meta: map[string]string{
				"board_id":    strconv.Itoa(int(board.ID)),
				"kilter_name": board.KilterName,
			},
		})
	}

	return surfaces, nil
}

func (provider *KilterProvider) ListClimbs(
	ctx context.Context,
	secret SecretPayload,
	input ListClimbsInput,
) (*PaginatedClimbs, error) {
	_ = ctx
	_ = secret

	boardID, angle, err := parseKilterContext(input.SurfaceID, input.Context)
	if err != nil {
		return nil, err
	}

	climbs, err := models.GetPaginatedClimbs(
		input.Cursor,
		input.PageSize,
		input.Search,
		"",
		boardID,
		angle,
		input.Sort,
	)
	if err != nil {
		return nil, err
	}

	return &PaginatedClimbs{
		Climbs:     mapKilterClimbs(climbs.Climbs, input.SurfaceID, angle),
		HasMore:    climbs.HasMore,
		NextCursor: climbs.NextCursor,
		PageSize:   climbs.PageSize,
	}, nil
}

func (provider *KilterProvider) GetClimb(
	ctx context.Context,
	secret SecretPayload,
	input ListClimbsInput,
	climbID string,
) (*ProviderClimb, error) {
	_ = ctx
	_ = secret

	boardID, angle, err := parseKilterContext(input.SurfaceID, input.Context)
	if err != nil {
		return nil, err
	}

	parsedBoardID, uuid, err := parseKilterClimbID(climbID)
	if err != nil {
		return nil, err
	}
	if parsedBoardID != boardID {
		return nil, fmt.Errorf("climb %s does not belong to board %d", climbID, boardID)
	}

	climb, err := models.GetClimbByUUID(uuid, boardID, angle)
	if err != nil {
		return nil, err
	}

	climbs := mapKilterClimbs([]models.Climb{*climb}, input.SurfaceID, angle)
	if len(climbs) == 0 {
		return nil, fmt.Errorf("climb %s not found", climbID)
	}

	return &climbs[0], nil
}

func (provider *KilterProvider) RefreshCatalog(context.Context, SecretPayload, map[string]string) error {
	return nil
}

func parseKilterContext(surfaceID string, context map[string]string) (uint, uint, error) {
	boardIDValue := surfaceID
	if boardIDValue == "" {
		boardIDValue = context["board_id"]
	}
	if boardIDValue == "" {
		return 0, 0, fmt.Errorf("kilter board id is required")
	}

	boardID64, err := strconv.ParseUint(boardIDValue, 10, 64)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid kilter board id %q", boardIDValue)
	}

	angleValue := context["angle"]
	if angleValue == "" {
		return 0, 0, fmt.Errorf("kilter angle is required")
	}

	angle64, err := strconv.ParseUint(angleValue, 10, 64)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid kilter angle %q", angleValue)
	}

	boardID := uint(boardID64)
	angle := uint(angle64)
	if !models.IsSupportedAngle(angle) {
		return 0, 0, fmt.Errorf("unsupported kilter angle %d", angle)
	}

	return boardID, angle, nil
}

func parseKilterClimbID(climbID string) (uint, string, error) {
	var boardID uint64
	var uuid string
	if _, err := fmt.Sscanf(climbID, "kilter:%d:%s", &boardID, &uuid); err != nil {
		return 0, "", fmt.Errorf("invalid kilter climb id %q", climbID)
	}

	return uint(boardID), uuid, nil
}

func mapKilterClimbs(climbs []models.Climb, surfaceID string, angle uint) []ProviderClimb {
	mapped := make([]ProviderClimb, 0, len(climbs))
	gradeKey := strconv.Itoa(int(angle))
	for _, climb := range climbs {
		grade := climb.Grades[gradeKey]
		media := make([]ClimbMedia, 0, len(climb.ImageFilenames))
		for _, filename := range climb.ImageFilenames {
			media = append(media, ClimbMedia{
				URL:  "/api/images/" + filepath.Base(filename),
				Kind: "image",
			})
		}

		mapped = append(mapped, ProviderClimb{
			ID:             fmt.Sprintf("kilter:%d:%s", climb.ProductSizeID, climb.UUID),
			ExternalID:     climb.UUID,
			ProviderID:     ProviderKilter,
			SurfaceID:      surfaceID,
			Name:           climb.ClimbName,
			Description:    climb.Description,
			SetterName:     climb.SetterName,
			PrimaryGrade:   grade.Boulder,
			SecondaryGrade: grade.Route,
			CreatedAt:      climb.CreatedAt,
			Popularity:     climb.Ascends,
			Media:          media,
			Meta: map[string]string{
				"board_id":    strconv.Itoa(int(climb.ProductSizeID)),
				"angle":       gradeKey,
				"frames":      climb.Frames,
				"ascends":     strconv.Itoa(climb.Ascends),
				"productSize": strconv.Itoa(int(climb.ProductSizeID)),
			},
		})
	}

	return mapped
}
