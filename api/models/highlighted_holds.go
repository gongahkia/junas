package models

import (
	"fmt"
	"math"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"

	"github.com/lczm/kilter-together/api/config"
)

type HighlightedHold struct {
	Position int     `json:"position" example:"1096"`
	X        float64 `json:"x" example:"77.3"`
	Y        float64 `json:"y" example:"42.1"`
	Role     string  `json:"role" example:"start"`
	Color    string  `json:"color" example:"#00DD00"`
}

type boardLED struct {
	X int
	Y int
}

type boardBounds struct {
	MinX int
	MaxX int
	MinY int
	MaxY int
}

type roleStyle struct {
	Name  string
	Color string
}

var (
	frameHoldPattern = regexp.MustCompile(`p(\d+)r(\d+)`)

	highlightCacheMu    sync.RWMutex
	boardPlacementCache = map[uint]map[int]boardLED{}
	boardBoundsCache    = map[uint]boardBounds{}
	roleStyleCache      = map[uint]map[int]roleStyle{}
)

func populateClimbHighlightedHolds(climbs []Climb) error {
	if len(climbs) == 0 {
		return nil
	}

	boardIDs := make(map[uint]struct{}, len(climbs))
	for _, climb := range climbs {
		if climb.ProductSizeID != 0 && strings.TrimSpace(climb.Frames) != "" {
			boardIDs[climb.ProductSizeID] = struct{}{}
		}
	}
	if len(boardIDs) == 0 {
		return nil
	}

	if err := ensureHighlightedHoldMetadata(boardIDs); err != nil {
		return err
	}

	for climbIndex := range climbs {
		climbs[climbIndex].HighlightedHolds = highlightedHoldsForClimb(climbs[climbIndex])
	}

	return nil
}

func highlightedHoldsForClimb(climb Climb) []HighlightedHold {
	highlightCacheMu.RLock()
	placementsByID := boardPlacementCache[climb.ProductSizeID]
	bounds := boardBoundsCache[climb.ProductSizeID]
	rolesByID := roleStyleCache[climb.ProductSizeID]
	highlightCacheMu.RUnlock()

	if len(placementsByID) == 0 {
		return nil
	}

	width := bounds.MaxX - bounds.MinX
	height := bounds.MaxY - bounds.MinY
	if width <= 0 || height <= 0 {
		return nil
	}

	matches := frameHoldPattern.FindAllStringSubmatch(climb.Frames, -1)
	if len(matches) == 0 {
		return nil
	}

	holdsByPosition := make(map[int]HighlightedHold, len(matches))
	for _, match := range matches {
		position, err := strconv.Atoi(match[1])
		if err != nil {
			continue
		}
		roleID, err := strconv.Atoi(match[2])
		if err != nil {
			continue
		}

		placement, exists := placementsByID[position]
		if !exists {
			continue
		}

		role := rolesByID[roleID]
		x := roundTo((float64(placement.X-bounds.MinX)/float64(width))*100, 3)
		y := roundTo((float64(bounds.MaxY-placement.Y)/float64(height))*100, 3)
		holdsByPosition[position] = HighlightedHold{
			Position: position,
			X:        clampPercentage(x),
			Y:        clampPercentage(y),
			Role:     role.Name,
			Color:    normalizeHexColor(role.Color),
		}
	}

	positions := make([]int, 0, len(holdsByPosition))
	for position := range holdsByPosition {
		positions = append(positions, position)
	}
	sort.Ints(positions)

	holds := make([]HighlightedHold, 0, len(positions))
	for _, position := range positions {
		holds = append(holds, holdsByPosition[position])
	}
	return holds
}

func ensureHighlightedHoldMetadata(boardIDs map[uint]struct{}) error {
	missingBoardIDs := make([]uint, 0, len(boardIDs))

	highlightCacheMu.RLock()
	for boardID := range boardIDs {
		if len(boardPlacementCache[boardID]) == 0 || len(roleStyleCache[boardID]) == 0 {
			missingBoardIDs = append(missingBoardIDs, boardID)
		}
	}
	highlightCacheMu.RUnlock()

	if len(missingBoardIDs) == 0 {
		return nil
	}

	placementRows, err := fetchBoardPlacements(missingBoardIDs)
	if err != nil {
		if isMissingHighlightTableError(err) {
			return nil
		}
		return err
	}
	roleRows, err := fetchRoleStyles(missingBoardIDs)
	if err != nil {
		if isMissingHighlightTableError(err) {
			return nil
		}
		return err
	}

	placementsByBoard := make(map[uint]map[int]boardLED, len(missingBoardIDs))
	boundsByBoard := make(map[uint]boardBounds, len(missingBoardIDs))
	for _, boardID := range missingBoardIDs {
		boundsByBoard[boardID] = boardBounds{
			MinX: math.MaxInt,
			MaxX: math.MinInt,
			MinY: math.MaxInt,
			MaxY: math.MinInt,
		}
	}

	for _, row := range placementRows {
		if _, exists := placementsByBoard[row.ProductSizeID]; !exists {
			placementsByBoard[row.ProductSizeID] = make(map[int]boardLED)
		}
		placementsByBoard[row.ProductSizeID][row.PlacementID] = boardLED{
			X: row.X,
			Y: row.Y,
		}

		bounds := boundsByBoard[row.ProductSizeID]
		if row.X < bounds.MinX {
			bounds.MinX = row.X
		}
		if row.X > bounds.MaxX {
			bounds.MaxX = row.X
		}
		if row.Y < bounds.MinY {
			bounds.MinY = row.Y
		}
		if row.Y > bounds.MaxY {
			bounds.MaxY = row.Y
		}
		boundsByBoard[row.ProductSizeID] = bounds
	}

	roleStylesByBoard := make(map[uint]map[int]roleStyle, len(missingBoardIDs))
	for _, row := range roleRows {
		if _, exists := roleStylesByBoard[row.ProductSizeID]; !exists {
			roleStylesByBoard[row.ProductSizeID] = make(map[int]roleStyle)
		}
		roleStylesByBoard[row.ProductSizeID][row.RoleID] = roleStyle{
			Name:  row.Name,
			Color: normalizeHexColor(row.ScreenColor),
		}
	}

	highlightCacheMu.Lock()
	defer highlightCacheMu.Unlock()
	for _, boardID := range missingBoardIDs {
		if placements := placementsByBoard[boardID]; len(placements) > 0 {
			boardPlacementCache[boardID] = placements
			boardBoundsCache[boardID] = boundsByBoard[boardID]
		}
		if roles := roleStylesByBoard[boardID]; len(roles) > 0 {
			roleStyleCache[boardID] = roles
		}
	}

	return nil
}

type ledRow struct {
	ProductSizeID uint
	PlacementID   int
	X             int
	Y             int
}

func fetchBoardPlacements(boardIDs []uint) ([]ledRow, error) {
	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(boardIDs)), ",")
	query := fmt.Sprintf(`
SELECT
  ps.id AS product_size_id,
  p.id AS placement_id,
  h.x,
  h.y
FROM product_sizes ps
JOIN layouts l ON l.product_id = ps.product_id
JOIN placements p ON p.layout_id = l.id
JOIN holes h ON h.id = p.hole_id
WHERE ps.id IN (%s)`, placeholders)

	args := make([]interface{}, 0, len(boardIDs))
	for _, boardID := range boardIDs {
		args = append(args, boardID)
	}

	var rows []ledRow
	if err := config.KilterDB.Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("fetch board placements: %w", err)
	}

	return rows, nil
}

type roleRow struct {
	ProductSizeID uint
	RoleID        int
	Name          string
	ScreenColor   string
}

func fetchRoleStyles(boardIDs []uint) ([]roleRow, error) {
	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(boardIDs)), ",")
	query := fmt.Sprintf(`
SELECT
  ps.id AS product_size_id,
  pr.id AS role_id,
  pr.name,
  pr.screen_color
FROM product_sizes ps
JOIN placement_roles pr ON pr.product_id = ps.product_id
WHERE ps.id IN (%s)`, placeholders)

	args := make([]interface{}, 0, len(boardIDs))
	for _, boardID := range boardIDs {
		args = append(args, boardID)
	}

	var rows []roleRow
	if err := config.KilterDB.Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("fetch role styles: %w", err)
	}

	return rows, nil
}

func normalizeHexColor(value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "#00DD00"
	}
	if strings.HasPrefix(trimmed, "#") {
		return strings.ToUpper(trimmed)
	}
	return "#" + strings.ToUpper(trimmed)
}

func roundTo(value float64, precision int) float64 {
	pow := math.Pow(10, float64(precision))
	return math.Round(value*pow) / pow
}

func clampPercentage(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 100 {
		return 100
	}
	return value
}

func isMissingHighlightTableError(err error) bool {
	if err == nil {
		return false
	}

	return strings.Contains(err.Error(), "no such table: leds") ||
		strings.Contains(err.Error(), "no such table: placements") ||
		strings.Contains(err.Error(), "no such table: holes") ||
		strings.Contains(err.Error(), "no such table: layouts") ||
		strings.Contains(err.Error(), "no such table: placement_roles") ||
		strings.Contains(err.Error(), "no such table: product_sizes")
}
