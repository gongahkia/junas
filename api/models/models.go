package models

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/config"
	"github.com/patrickmn/go-cache"
)

const (
	SortPopular = "popular"
	SortNewest  = "newest"
)

var supportedAngles = map[uint]struct{}{
	5:  {},
	10: {},
	15: {},
	20: {},
	25: {},
	30: {},
	35: {},
	40: {},
	45: {},
	50: {},
	55: {},
	60: {},
	65: {},
	70: {},
}

// GradeInfo represents grade information for a specific angle.
type GradeInfo struct {
	Boulder string `json:"boulder" example:"7a/V6"`
	Route   string `json:"route" example:"7c/5.12d"`
}

// ClimbGradesExample provides an example of the grades field structure for Swagger documentation.
type ClimbGradesExample struct {
	Angle40 GradeInfo `json:"40"`
	Angle45 GradeInfo `json:"45"`
	Angle50 GradeInfo `json:"50"`
}

// Climb represents a climb along with its board images.
type Climb struct {
	UUID           string               `json:"uuid" example:"F01419E12672459396CA62E3655ABC46"`
	SetterName     string               `json:"setter_name" example:"jwebxl"`
	ClimbName      string               `json:"climb_name" example:"swooped"`
	Description    string               `json:"description,omitempty" example:"A challenging overhang problem"`
	Frames         string               `json:"frames" example:"p1080r15p1110r15p1131r12"`
	ImageFilenames []string             `gorm:"column:image_filenames;serializer:json" json:"image_filenames"`
	Ascends        int                  `json:"ascends" example:"42"`
	ProductSizeID  uint                 `json:"product_size_id" example:"14"`
	Grades         map[string]GradeInfo `gorm:"-" json:"grades"`
	CreatedAt      string               `json:"created_at" example:"2018-12-06 21:15:01.127371"`
}

// CursorPaginatedClimbsResponse holds cursor-paginated climbs along with images.
type CursorPaginatedClimbsResponse struct {
	Climbs     []Climb `json:"climbs"`
	HasMore    bool    `json:"has_more" example:"true"`
	NextCursor string  `json:"next_cursor,omitempty" example:"eyJzb3J0IjoicG9wdWxhciIsImFzY2VuZHMiOjQyLCJjcmVhdGVkX2F0IjoiMjAyNi0wMS0wMSAwMDowMDowMC4wMDAwMDAiLCJ1dWlkIjoidXVpZC0xIiwicHJvZHVjdF9zaXplX2lkIjoxNH0="`
	PageSize   int     `json:"page_size" example:"10"`
}

// BoardOption represents a board (product_size) option for filtering climbs.
type BoardOption struct {
	ID         uint   `json:"id" example:"14"`
	Name       string `json:"name" example:"7 x 10"`
	KilterName string `json:"kilter_name" example:"Kilter Board Original"`
}

var c = cache.New(7*24*time.Hour, 10*time.Minute)

// CompositeCursor represents the cursor for pagination with all sorting fields.
type CompositeCursor struct {
	Sort          string `json:"sort"`
	Ascends       int    `json:"ascends,omitempty"`
	CreatedAt     string `json:"created_at"`
	UUID          string `json:"uuid"`
	ProductSizeID uint   `json:"product_size_id"`
}

func IsSupportedAngle(angle uint) bool {
	_, exists := supportedAngles[angle]
	return exists
}

func NormalizeSort(value string) string {
	normalized := strings.ToLower(strings.TrimSpace(value))
	switch normalized {
	case "", SortPopular:
		return SortPopular
	case SortNewest:
		return SortNewest
	default:
		return ""
	}
}

func encodeCursor(sort string, climb Climb) string {
	cursor := CompositeCursor{
		Sort:          sort,
		CreatedAt:     climb.CreatedAt,
		UUID:          climb.UUID,
		ProductSizeID: climb.ProductSizeID,
	}
	if sort == SortPopular {
		cursor.Ascends = climb.Ascends
	}

	data, err := json.Marshal(cursor)
	if err != nil {
		return ""
	}

	return base64.URLEncoding.EncodeToString(data)
}

func decodeCursor(cursorStr string) (*CompositeCursor, error) {
	if cursorStr == "" {
		return nil, nil
	}

	data, err := base64.URLEncoding.DecodeString(cursorStr)
	if err != nil {
		return nil, fmt.Errorf("decode cursor: %w", err)
	}

	var cursor CompositeCursor
	if err := json.Unmarshal(data, &cursor); err != nil {
		return nil, fmt.Errorf("unmarshal cursor: %w", err)
	}
	cursor.Sort = NormalizeSort(cursor.Sort)
	if cursor.Sort == "" {
		cursor.Sort = SortPopular
	}

	return &cursor, nil
}

func GetPaginatedClimbs(
	cursor string,
	pageSize int,
	nameFilter string,
	setterFilter string,
	boardID uint,
	angle uint,
	sort string,
) (*CursorPaginatedClimbsResponse, error) {
	cacheKey := fmt.Sprintf(
		"climbs-cursor-%s-%d-%s-%s-%d-%d-%s",
		cursor,
		pageSize,
		nameFilter,
		setterFilter,
		boardID,
		angle,
		sort,
	)
	if x, found := c.Get(cacheKey); found {
		return x.(*CursorPaginatedClimbsResponse), nil
	}

	normalizedSort := NormalizeSort(sort)
	if normalizedSort == "" {
		normalizedSort = SortPopular
	}

	namePattern := "%" + strings.TrimSpace(nameFilter) + "%"
	setterPattern := "%" + strings.TrimSpace(setterFilter) + "%"

	cursorData, err := decodeCursor(cursor)
	if err != nil {
		return nil, fmt.Errorf("invalid cursor: %w", err)
	}
	if cursorData != nil && cursorData.Sort != normalizedSort {
		return nil, fmt.Errorf("cursor sort %q does not match requested sort %q", cursorData.Sort, normalizedSort)
	}

	query := strings.Builder{}
	query.WriteString(`
SELECT
  c.uuid,
  c.setter_username AS setter_name,
  c.name AS climb_name,
  c.description,
  c.frames,
  c.created_at,
  ps.id AS product_size_id,
  JSON_GROUP_ARRAY(DISTINCT psl.image_filename) AS image_filenames,
  COALESCE(cs.ascensionist_count, 0) AS ascends
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
JOIN climb_stats cs ON c.uuid = cs.climb_uuid AND cs.angle = ?
WHERE c.is_listed = 1
  AND c.name LIKE ?
  AND c.setter_username LIKE ?`)

	args := []interface{}{angle, namePattern, setterPattern}
	if boardID != 0 {
		query.WriteString("\n  AND ps.id = ?")
		args = append(args, boardID)
	}

	cursorCondition, cursorArgs := buildCursorCondition(normalizedSort, cursorData)
	if cursorCondition != "" {
		query.WriteString("\n  AND ")
		query.WriteString(cursorCondition)
		args = append(args, cursorArgs...)
	}

	query.WriteString(`
GROUP BY c.uuid, ps.id, cs.ascensionist_count
ORDER BY `)
	query.WriteString(orderByForSort(normalizedSort))
	query.WriteString(`
LIMIT ?`)
	args = append(args, pageSize+1)

	var climbs []Climb
	if err := config.KilterDB.Raw(query.String(), args...).Scan(&climbs).Error; err != nil {
		return nil, fmt.Errorf("fetch climbs: %w", err)
	}

	hasMore := len(climbs) > pageSize
	if hasMore {
		climbs = climbs[:pageSize]
	}

	if err := populateClimbGrades(climbs); err != nil {
		return nil, fmt.Errorf("populate grades: %w", err)
	}

	var nextCursor string
	if hasMore && len(climbs) > 0 {
		nextCursor = encodeCursor(normalizedSort, climbs[len(climbs)-1])
	}

	resp := &CursorPaginatedClimbsResponse{
		Climbs:     climbs,
		HasMore:    hasMore,
		NextCursor: nextCursor,
		PageSize:   pageSize,
	}
	c.Set(cacheKey, resp, time.Hour)
	return resp, nil
}

func GetBoardOptions() ([]BoardOption, error) {
	cacheKey := "boardOptions"
	if x, found := c.Get(cacheKey); found {
		return x.([]BoardOption), nil
	}

	var boards []BoardOption
	query := `
SELECT
  ps.id AS id,
  ps.name AS name,
  p.name AS kilter_name
FROM product_sizes AS ps
JOIN products AS p
  ON ps.product_id = p.id
WHERE ps.is_listed = 1
  AND p.is_listed = 1
  AND p.name LIKE 'Kilter Board%'
ORDER BY p.name, ps.position, ps.id`
	if err := config.KilterDB.Raw(query).Scan(&boards).Error; err != nil {
		return nil, fmt.Errorf("fetch boards: %w", err)
	}

	c.Set(cacheKey, boards, cache.NoExpiration)
	return boards, nil
}

func orderByForSort(sort string) string {
	if sort == SortNewest {
		return "c.created_at DESC, c.uuid DESC, ps.id"
	}

	return "ascends DESC, c.created_at DESC, c.uuid DESC, ps.id"
}

func buildCursorCondition(sort string, cursor *CompositeCursor) (string, []interface{}) {
	if cursor == nil {
		return "", nil
	}

	if sort == SortNewest {
		return `(
  c.created_at < ? OR
  (c.created_at = ? AND c.uuid < ?) OR
  (c.created_at = ? AND c.uuid = ? AND ps.id > ?)
)`, []interface{}{
				cursor.CreatedAt,
				cursor.CreatedAt, cursor.UUID,
				cursor.CreatedAt, cursor.UUID, cursor.ProductSizeID,
			}
	}

	return `(
  cs.ascensionist_count < ? OR
  (cs.ascensionist_count = ? AND c.created_at < ?) OR
  (cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid < ?) OR
  (cs.ascensionist_count = ? AND c.created_at = ? AND c.uuid = ? AND ps.id > ?)
)`, []interface{}{
			cursor.Ascends,
			cursor.Ascends, cursor.CreatedAt,
			cursor.Ascends, cursor.CreatedAt, cursor.UUID,
			cursor.Ascends, cursor.CreatedAt, cursor.UUID, cursor.ProductSizeID,
		}
}

func populateClimbGrades(climbs []Climb) error {
	if len(climbs) == 0 {
		return nil
	}

	for index := range climbs {
		climbs[index].Grades = make(map[string]GradeInfo)
	}

	uniqueUUIDs := make(map[string]struct{}, len(climbs))
	climbIndexesByUUID := make(map[string][]int, len(climbs))
	for index, climb := range climbs {
		uniqueUUIDs[climb.UUID] = struct{}{}
		climbIndexesByUUID[climb.UUID] = append(climbIndexesByUUID[climb.UUID], index)
	}

	climbUUIDs := make([]string, 0, len(uniqueUUIDs))
	for uuid := range uniqueUUIDs {
		climbUUIDs = append(climbUUIDs, uuid)
	}

	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(climbUUIDs)), ",")
	query := fmt.Sprintf(`
SELECT
  cs.climb_uuid,
  cs.angle,
  dg.boulder_name,
  dg.route_name
FROM climb_stats cs
JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INTEGER) = dg.difficulty
WHERE cs.climb_uuid IN (%s)
ORDER BY cs.climb_uuid, cs.angle`, placeholders)

	args := make([]interface{}, 0, len(climbUUIDs))
	for _, uuid := range climbUUIDs {
		args = append(args, uuid)
	}

	type gradeResult struct {
		ClimbUUID   string
		Angle       int
		BoulderName string
		RouteName   string
	}

	var results []gradeResult
	if err := config.KilterDB.Raw(query, args...).Scan(&results).Error; err != nil {
		return fmt.Errorf("fetch climb grades: %w", err)
	}

	for _, result := range results {
		indexes := climbIndexesByUUID[result.ClimbUUID]
		gradeInfo := GradeInfo{
			Boulder: result.BoulderName,
			Route:   result.RouteName,
		}
		for _, index := range indexes {
			climbs[index].Grades[fmt.Sprintf("%d", result.Angle)] = gradeInfo
		}
	}

	return nil
}
