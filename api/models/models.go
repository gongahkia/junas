package models

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lczm/boardbuddy/api/config"
	"github.com/patrickmn/go-cache"
)

// GradeInfo represents grade information for a specific angle
type GradeInfo struct {
	Boulder string `json:"boulder" example:"7a/V6"`  // Boulder grade in format "grade/V-scale"
	Route   string `json:"route" example:"7c/5.12d"` // Route grade in format "grade/YDS"
}

// ClimbGradesExample provides an example of the grades field structure for Swagger documentation
type ClimbGradesExample struct {
	Angle40 GradeInfo `json:"40"`
	Angle45 GradeInfo `json:"45"`
	Angle50 GradeInfo `json:"50"`
}

// Climb represents a climb along with its board images.
type Climb struct {
	UUID           string               `json:"uuid" example:"F01419E12672459396CA62E3655ABC46"`      // Unique identifier for the climb
	SetterName     string               `json:"setter_name" example:"jwebxl"`                         // Username of the climb setter
	ClimbName      string               `json:"climb_name" example:"swooped"`                         // Name/title of the climb
	Description    string               `json:"description" example:"A challenging overhang problem"` // Optional description
	Frames         string               `json:"frames" example:"p1080r15p1110r15p1131r12"`            // Hold positions and rotations
	ImageFilenames []string             `gorm:"column:image_filenames;serializer:json" json:"image_filenames"`
	Ascends        int                  `json:"ascends" example:"0"`
	ProductSizeID  uint                 `json:"product_size_id" example:"1"`                     // Board/product size identifier
	Grades         map[string]GradeInfo `json:"grades"`                                          // Map of angle to grade info
	CreatedAt      string               `json:"created_at" example:"2018-12-06 21:15:01.127371"` // Creation timestamp
}

// CursorPaginatedClimbsResponse holds cursor-paginated climbs along with images.
type CursorPaginatedClimbsResponse struct {
	Climbs     []Climb `json:"climbs"`                                                     // Array of climb objects
	HasMore    bool    `json:"has_more" example:"true"`                                    // Whether more pages are available
	NextCursor string  `json:"next_cursor,omitempty" example:"2025-05-24 04:07:17.406545"` // Cursor for next page (composite: ascends:created_at:uuid:product_size_id)
	PageSize   int     `json:"page_size" example:"10"`                                     // Number of items per page
}

// BoardOption represents a board (product_size) option for filtering climbs.
type BoardOption struct {
	ID         uint   `json:"id" example:"1"`                              // Unique board identifier
	Name       string `json:"name" example:"Original 12x12"`               // Human-readable board name
	KilterName string `json:"kilter_name" example:"Kilter Board original"` // The board type
}

var c = cache.New(7*24*time.Hour, 10*time.Minute)

// CompositeCursor represents the cursor for pagination with all sorting fields
type CompositeCursor struct {
	Ascends       int    `json:"ascends"`
	CreatedAt     string `json:"created_at"`
	UUID          string `json:"uuid"`
	ProductSizeID uint   `json:"product_size_id"`
}

// encodeCursor creates a base64-encoded cursor from the sorting fields
func encodeCursor(ascends int, createdAt, uuid string, productSizeID uint) string {
	cursor := CompositeCursor{
		Ascends:       ascends,
		CreatedAt:     createdAt,
		UUID:          uuid,
		ProductSizeID: productSizeID,
	}

	data, err := json.Marshal(cursor)
	if err != nil {
		return ""
	}

	return base64.URLEncoding.EncodeToString(data)
}

// decodeCursor decodes a base64-encoded cursor back to its components
func decodeCursor(cursorStr string) (*CompositeCursor, error) {
	if cursorStr == "" {
		return nil, nil
	}

	// Handle legacy timestamp-only cursors for backward compatibility
	if !strings.Contains(cursorStr, "{") && len(strings.Split(cursorStr, "-")) >= 3 {
		// This looks like a timestamp, treat as legacy cursor
		return &CompositeCursor{
			Ascends:       -1, // Use -1 to indicate legacy cursor
			CreatedAt:     cursorStr,
			UUID:          "",
			ProductSizeID: 0,
		}, nil
	}

	data, err := base64.URLEncoding.DecodeString(cursorStr)
	if err != nil {
		// Try treating as legacy timestamp cursor
		return &CompositeCursor{
			Ascends:       -1,
			CreatedAt:     cursorStr,
			UUID:          "",
			ProductSizeID: 0,
		}, nil
	}

	var cursor CompositeCursor
	if err := json.Unmarshal(data, &cursor); err != nil {
		return nil, fmt.Errorf("invalid cursor format: %w", err)
	}

	return &cursor, nil
}

func GetPaginatedClimbs(cursor string, pageSize int, nameFilter string, boardID uint, angle uint) (*CursorPaginatedClimbsResponse, error) {
	cacheKey := fmt.Sprintf("climbs-cursor-%s-%d-%s-%d-%d", cursor, pageSize, nameFilter, boardID, angle)
	if x, found := c.Get(cacheKey); found {
		return x.(*CursorPaginatedClimbsResponse), nil
	}

	nameFilter = strings.TrimSpace(nameFilter)
	likePattern := "%" + nameFilter + "%"

	// Decode the cursor
	cursorData, err := decodeCursor(cursor)
	if err != nil {
		return nil, fmt.Errorf("invalid cursor: %w", err)
	}

	// Build the cursor condition for pagination
	cursorCondition := ""
	var args []interface{}

	if cursorData == nil {
		// First page - no cursor condition
		args = []interface{}{likePattern}
	} else if cursorData.Ascends == -1 {
		// Legacy cursor - use old timestamp-based pagination for backward compatibility
		cursorCondition = "AND c.created_at < ?"
		args = []interface{}{likePattern, cursorData.CreatedAt}
	} else {
		// New composite cursor - create condition based on all sort fields
		cursorCondition = `AND (
			cs.ascensionist_count < ? OR
			(cs.ascensionist_count = ? AND c.created_at < ?) OR
			(cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid < ?) OR
			(cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid = ? AND ps.id > ?)
		)`
		args = []interface{}{
			likePattern,
			cursorData.Ascends,                       // cs.ascensionist_count < ?
			cursorData.Ascends, cursorData.CreatedAt, // (cs.ascensionist_count = ? AND c.created_at < ?)
			cursorData.Ascends, cursorData.CreatedAt, cursorData.UUID, // (cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid < ?)
			cursorData.Ascends, cursorData.CreatedAt, cursorData.UUID, cursorData.ProductSizeID, // (cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid = ? AND ps.id > ?)
		}
	}

	// Join climb_stats for specific angle and select per-angle ascends
	query := fmt.Sprintf(`
SELECT
  c.uuid,
  c.setter_username AS setter_name,
  c.name AS climb_name,
  c.description,
  c.frames,
  c.created_at,
  ps.id AS product_size_id,
  JSON_GROUP_ARRAY(psl.image_filename) AS image_filenames,
  cs.ascensionist_count AS ascends
FROM climbs c
JOIN layouts l ON c.layout_id = l.id
JOIN product_sizes ps ON (
  ps.product_id = l.product_id AND
  ps.edge_left <= c.edge_left AND
  ps.edge_right >= c.edge_right AND
  ps.edge_bottom <= c.edge_bottom AND
  ps.edge_top >= c.edge_top
)
JOIN product_sizes_layouts_sets psl ON psl.product_size_id = ps.id AND psl.layout_id = l.id
JOIN climb_stats cs ON c.uuid = cs.climb_uuid AND cs.angle = %d
WHERE c.is_listed = 1
  AND c.name LIKE ?
  %s
  %s
GROUP BY c.uuid, ps.id
ORDER BY ascends DESC, c.created_at DESC, c.uuid DESC, ps.id
LIMIT ?`, angle, cursorCondition, optionalBoardFilterSQL(boardID))

	args = append(args, pageSize+1) // Get one extra to check for more pages

	var climbs []Climb
	if err := config.KilterDB.Raw(query, args...).Scan(&climbs).Error; err != nil {
		return nil, fmt.Errorf("fetch climbs: %w", err)
	}

	// Check if there are more pages
	hasMore := len(climbs) > pageSize
	if hasMore {
		climbs = climbs[:pageSize]
	}

	// Fetch grades for all climbs
	if err := populateClimbGrades(climbs, angle); err != nil {
		return nil, fmt.Errorf("populate grades: %w", err)
	}

	// Get next cursor from the last item using composite cursor
	var nextCursor string
	if hasMore && len(climbs) > 0 {
		lastClimb := climbs[len(climbs)-1]
		nextCursor = encodeCursor(lastClimb.Ascends, lastClimb.CreatedAt, lastClimb.UUID, lastClimb.ProductSizeID)
	}

	resp := &CursorPaginatedClimbsResponse{
		Climbs:     climbs,
		HasMore:    hasMore,
		NextCursor: nextCursor,
		PageSize:   pageSize,
	}

	// Cache for shorter time since this is more dynamic
	c.Set(cacheKey, resp, 1*time.Hour)
	return resp, nil
}

// get all listed boards
func GetBoardOptions() ([]BoardOption, error) {
	cacheKey := "boardOptions"
	if x, found := c.Get(cacheKey); found {
		return x.([]BoardOption), nil
	}
	var boards []BoardOption
	query := `
SELECT
  ps.id   AS id,
  ps.name AS name,
  p.name  AS kilter_name
FROM product_sizes AS ps
JOIN products AS p
  ON ps.product_id = p.id
WHERE ps.is_listed = 1
  AND p.is_listed  = 1
  AND p.name IN ('Kilter Board Homewall', 'Kilter Board Original')
  AND ps.id IN (14, 17, 8, 10, 19, 27, 7, 28, 24, 25)
ORDER BY ps.position;`
	if err := config.KilterDB.Raw(query).Scan(&boards).Error; err != nil {
		return nil, fmt.Errorf("fetch boards: %w", err)
	}
	c.Set(cacheKey, boards, cache.NoExpiration)
	return boards, nil
}

// helper to use for in-query sql
// optionalBoardFilterSQL returns SQL snippet to filter
func optionalBoardFilterSQL(boardID uint) string {
	if boardID == 0 {
		return ""
	}
	return fmt.Sprintf("AND ps.id = %d", boardID)
}

// populateClimbGrades fetches and populates grade information for a list of climbs, filtered by angle
func populateClimbGrades(climbs []Climb, angle uint) error {
	if len(climbs) == 0 {
		return nil
	}

	// Initialize grades map for each climb
	for i := range climbs {
		climbs[i].Grades = make(map[string]GradeInfo)
	}

	// Extract unique climb UUIDs for batch fetching
	uniqueUUIDs := make(map[string]bool)
	climbIndexMap := make(map[string][]int) // UUID -> slice indices

	for i, climb := range climbs {
		uniqueUUIDs[climb.UUID] = true
		climbIndexMap[climb.UUID] = append(climbIndexMap[climb.UUID], i)
	}

	// Convert to slice for query
	climbUUIDs := make([]string, 0, len(uniqueUUIDs))
	for uuid := range uniqueUUIDs {
		climbUUIDs = append(climbUUIDs, uuid)
	}

	// Build placeholders for IN clause
	placeholders := strings.Repeat("?,", len(climbUUIDs))
	placeholders = placeholders[:len(placeholders)-1] // Remove trailing comma

	// Query to get climb stats with grade information
	query := fmt.Sprintf(`
SELECT 
	cs.climb_uuid,
	cs.angle,
	cs.display_difficulty,
	dg.boulder_name,
	dg.route_name
FROM climb_stats cs
JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INTEGER) = dg.difficulty
WHERE cs.climb_uuid IN (%s) AND cs.angle = ?
ORDER BY cs.climb_uuid`, placeholders)

	// Convert climbUUIDs to interface{} slice for the query
	args := make([]interface{}, len(climbUUIDs)+1)
	for i, uuid := range climbUUIDs {
		args[i] = uuid
	}
	args[len(climbUUIDs)] = angle

	// Execute query
	type GradeResult struct {
		ClimbUUID   string  `db:"climb_uuid"`
		Angle       int     `db:"angle"`
		Difficulty  float64 `db:"display_difficulty"`
		BoulderName string  `db:"boulder_name"`
		RouteName   string  `db:"route_name"`
	}

	var results []GradeResult
	if err := config.KilterDB.Raw(query, args...).Scan(&results).Error; err != nil {
		return fmt.Errorf("fetch climb grades: %w", err)
	}

	// Populate grades for each climb
	for _, result := range results {
		if indices, exists := climbIndexMap[result.ClimbUUID]; exists {
			angleStr := fmt.Sprintf("%d", result.Angle)
			gradeInfo := GradeInfo{
				Boulder: result.BoulderName,
				Route:   result.RouteName,
			}

			// Set grades for all climbs with this UUID (there will be multiple for different product sizes)
			for _, idx := range indices {
				// only specified angle present
				climbs[idx].Grades[angleStr] = gradeInfo
			}
		}
	}

	return nil
}
