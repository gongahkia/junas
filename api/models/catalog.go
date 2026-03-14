package models

import (
	"crypto/sha1"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/config"
)

const (
	defaultCatalogBootstrapPageSize = 200
	maxCatalogBootstrapPageSize     = 500
)

type CatalogManifest struct {
	Revision           string `json:"revision"`
	GeneratedAt        string `json:"generated_at"`
	ClimbCount         int    `json:"climb_count"`
	ImageCount         int    `json:"image_count"`
	EstimatedBytes     int64  `json:"estimated_bytes"`
	RequiresFullResync bool   `json:"requires_full_resync"`
}

type CatalogClimb struct {
	UUID             string               `json:"uuid"`
	SetterName       string               `json:"setter_name"`
	ClimbName        string               `json:"climb_name"`
	Description      string               `json:"description,omitempty"`
	Frames           string               `json:"frames"`
	ImageFilenames   []string             `gorm:"column:image_filenames;serializer:json" json:"image_filenames"`
	HighlightedHolds []HighlightedHold    `gorm:"-" json:"highlighted_holds,omitempty"`
	ProductSizeID    uint                 `json:"product_size_id"`
	CreatedAt        string               `json:"created_at"`
	Grades           map[string]GradeInfo `gorm:"-" json:"grades"`
	Ascends          map[string]int       `gorm:"-" json:"ascends"`
}

type CatalogBootstrapResponse struct {
	Manifest   CatalogManifest `json:"manifest"`
	Boards     []BoardOption   `json:"boards"`
	Climbs     []CatalogClimb  `json:"climbs"`
	SyncToken  string          `json:"sync_token,omitempty"`
	HasMore    bool            `json:"has_more"`
	NextCursor string          `json:"next_cursor,omitempty"`
	PageSize   int             `json:"page_size"`
}

type CatalogDeltaResponse struct {
	Manifest           CatalogManifest `json:"manifest"`
	Climbs             []CatalogClimb  `json:"climbs"`
	NextToken          string          `json:"next_token,omitempty"`
	RequiresFullResync bool            `json:"requires_full_resync"`
}

type catalogBootstrapCursor struct {
	Offset int `json:"offset"`
}

type catalogDeltaToken struct {
	BoardSignature string `json:"board_signature"`
	CreatedAt      string `json:"created_at"`
	UUID           string `json:"uuid"`
	ProductSizeID  uint   `json:"product_size_id"`
}

type catalogWatermark struct {
	CreatedAt     string
	UUID          string
	ProductSizeID uint
}

type catalogClimbStatsRow struct {
	ClimbUUID   string
	Angle       int
	Ascends     int
	BoulderName string
	RouteName   string
}

func GetCatalogManifest() (*CatalogManifest, error) {
	boards, err := GetBoardOptions()
	if err != nil {
		return nil, err
	}

	boardSignature := signatureForBoards(boards)
	imageFilenames, err := listCatalogImageFilenames()
	if err != nil {
		return nil, err
	}

	climbCount := 0
	for _, board := range boards {
		climbCount += board.ClimbCount
	}

	estimatedBytes, generatedAt, err := catalogStorageSummary(imageFilenames)
	if err != nil {
		return nil, err
	}

	watermark, err := latestCatalogWatermark()
	if err != nil {
		return nil, err
	}

	revision := signatureForParts(
		generatedAt,
		boardSignature,
		fmt.Sprintf("%d", climbCount),
		fmt.Sprintf("%d", len(imageFilenames)),
		fmt.Sprintf("%d", estimatedBytes),
		watermark.CreatedAt,
		watermark.UUID,
		fmt.Sprintf("%d", watermark.ProductSizeID),
	)

	return &CatalogManifest{
		Revision:           revision,
		GeneratedAt:        generatedAt,
		ClimbCount:         climbCount,
		ImageCount:         len(imageFilenames),
		EstimatedBytes:     estimatedBytes,
		RequiresFullResync: false,
	}, nil
}

func ListCatalogBootstrap(cursor string, pageSize int) (*CatalogBootstrapResponse, error) {
	if pageSize <= 0 {
		pageSize = defaultCatalogBootstrapPageSize
	}
	if pageSize > maxCatalogBootstrapPageSize {
		pageSize = maxCatalogBootstrapPageSize
	}

	offset, err := decodeCatalogBootstrapCursor(cursor)
	if err != nil {
		return nil, fmt.Errorf("%w: %w", ErrInvalidCursor, err)
	}

	manifest, err := GetCatalogManifest()
	if err != nil {
		return nil, err
	}

	boards, err := GetBoardOptions()
	if err != nil {
		return nil, err
	}
	boardSignature := signatureForBoards(boards)

	climbs, err := listCatalogBootstrapClimbs(offset, pageSize+1)
	if err != nil {
		return nil, err
	}

	hasMore := len(climbs) > pageSize
	if hasMore {
		climbs = climbs[:pageSize]
	}

	nextCursor := ""
	if hasMore {
		nextCursor = encodeCatalogBootstrapCursor(offset + pageSize)
	}

	syncToken := ""
	latest, err := latestCatalogWatermark()
	if err != nil {
		return nil, err
	}
	if latest.UUID != "" {
		syncToken = encodeCatalogDeltaToken(catalogDeltaToken{
			BoardSignature: boardSignature,
			CreatedAt:      latest.CreatedAt,
			UUID:           latest.UUID,
			ProductSizeID:  latest.ProductSizeID,
		})
	}

	return &CatalogBootstrapResponse{
		Manifest:   *manifest,
		Boards:     boards,
		Climbs:     climbs,
		SyncToken:  syncToken,
		HasMore:    hasMore,
		NextCursor: nextCursor,
		PageSize:   pageSize,
	}, nil
}

func ListCatalogDelta(afterToken string) (*CatalogDeltaResponse, error) {
	manifest, err := GetCatalogManifest()
	if err != nil {
		return nil, err
	}

	boards, err := GetBoardOptions()
	if err != nil {
		return nil, err
	}
	boardSignature := signatureForBoards(boards)

	token, err := decodeCatalogDeltaToken(afterToken)
	if err != nil {
		return nil, fmt.Errorf("%w: %w", ErrInvalidCursor, err)
	}
	if token != nil && token.BoardSignature != "" && token.BoardSignature != boardSignature {
		return &CatalogDeltaResponse{
			Manifest:           *manifest,
			Climbs:             constCatalogClimbs(),
			NextToken:          "",
			RequiresFullResync: true,
		}, nil
	}

	climbs, err := listCatalogDeltaClimbs(token)
	if err != nil {
		return nil, err
	}

	nextToken := afterToken
	if latest, ok := latestCatalogClimbToken(climbs); ok {
		nextToken = encodeCatalogDeltaToken(catalogDeltaToken{
			BoardSignature: boardSignature,
			CreatedAt:      latest.CreatedAt,
			UUID:           latest.UUID,
			ProductSizeID:  latest.ProductSizeID,
		})
	} else if token == nil {
		latest, err := latestCatalogWatermark()
		if err != nil {
			return nil, err
		}
		if latest.UUID != "" {
			nextToken = encodeCatalogDeltaToken(catalogDeltaToken{
				BoardSignature: boardSignature,
				CreatedAt:      latest.CreatedAt,
				UUID:           latest.UUID,
				ProductSizeID:  latest.ProductSizeID,
			})
		}
	}

	return &CatalogDeltaResponse{
		Manifest:           *manifest,
		Climbs:             climbs,
		NextToken:          nextToken,
		RequiresFullResync: false,
	}, nil
}

func listCatalogBootstrapClimbs(offset int, limit int) ([]CatalogClimb, error) {
	if offset < 0 {
		offset = 0
	}

	var climbs []CatalogClimb
	query := `
SELECT
  c.uuid,
  c.setter_username AS setter_name,
  c.name AS climb_name,
  c.description,
  c.frames,
  c.created_at,
  ps.id AS product_size_id,
  JSON_GROUP_ARRAY(DISTINCT psl.image_filename) AS image_filenames
FROM climbs c
JOIN layouts l ON c.layout_id = l.id
JOIN products p ON l.product_id = p.id
JOIN product_sizes ps ON (
  ps.product_id = l.product_id AND
  ps.edge_left <= c.edge_left AND
  ps.edge_right >= c.edge_right AND
  ps.edge_bottom <= c.edge_bottom AND
  ps.edge_top >= c.edge_top
)
JOIN product_sizes_layouts_sets psl ON psl.product_size_id = ps.id AND psl.layout_id = l.id
WHERE c.is_listed = 1
  AND p.is_listed = 1
  AND p.name LIKE 'Kilter Board%'
GROUP BY c.uuid, ps.id
ORDER BY c.created_at ASC, c.uuid ASC, ps.id ASC
LIMIT ? OFFSET ?`

	if err := config.KilterDB.Raw(query, limit, offset).Scan(&climbs).Error; err != nil {
		return nil, fmt.Errorf("fetch catalog climbs: %w", err)
	}
	return populateCatalogClimbMetadata(climbs)
}

func listCatalogDeltaClimbs(token *catalogDeltaToken) ([]CatalogClimb, error) {
	var climbs []CatalogClimb
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
  JSON_GROUP_ARRAY(DISTINCT psl.image_filename) AS image_filenames
FROM climbs c
JOIN layouts l ON c.layout_id = l.id
JOIN products p ON l.product_id = p.id
JOIN product_sizes ps ON (
  ps.product_id = l.product_id AND
  ps.edge_left <= c.edge_left AND
  ps.edge_right >= c.edge_right AND
  ps.edge_bottom <= c.edge_bottom AND
  ps.edge_top >= c.edge_top
)
JOIN product_sizes_layouts_sets psl ON psl.product_size_id = ps.id AND psl.layout_id = l.id
WHERE c.is_listed = 1
  AND p.is_listed = 1
  AND p.name LIKE 'Kilter Board%'`)

	args := []interface{}{}
	if token != nil {
		query.WriteString(`
  AND (
    c.created_at > ? OR
    (c.created_at = ? AND c.uuid > ?) OR
    (c.created_at = ? AND c.uuid = ? AND ps.id > ?)
  )`)
		args = append(
			args,
			token.CreatedAt,
			token.CreatedAt, token.UUID,
			token.CreatedAt, token.UUID, token.ProductSizeID,
		)
	}

	query.WriteString(`
GROUP BY c.uuid, ps.id
ORDER BY c.created_at ASC, c.uuid ASC, ps.id ASC`)

	if err := config.KilterDB.Raw(query.String(), args...).Scan(&climbs).Error; err != nil {
		return nil, fmt.Errorf("fetch catalog delta climbs: %w", err)
	}
	return populateCatalogClimbMetadata(climbs)
}

func populateCatalogClimbMetadata(climbs []CatalogClimb) ([]CatalogClimb, error) {
	if len(climbs) == 0 {
		return constCatalogClimbs(), nil
	}

	for index := range climbs {
		climbs[index].ImageFilenames = normalizeCatalogImageFilenames(climbs[index].ImageFilenames)
		climbs[index].Grades = map[string]GradeInfo{}
		climbs[index].Ascends = map[string]int{}
	}

	if err := populateCatalogClimbStats(climbs); err != nil {
		return nil, err
	}
	populateCatalogHighlightedHolds(climbs)
	return climbs, nil
}

func populateCatalogClimbStats(climbs []CatalogClimb) error {
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
	if len(climbUUIDs) == 0 {
		return nil
	}

	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(climbUUIDs)), ",")
	query := fmt.Sprintf(`
SELECT
  cs.climb_uuid,
  cs.angle,
  COALESCE(cs.ascensionist_count, 0) AS ascends,
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

	var results []catalogClimbStatsRow
	if err := config.KilterDB.Raw(query, args...).Scan(&results).Error; err != nil {
		return fmt.Errorf("fetch catalog climb stats: %w", err)
	}

	for _, result := range results {
		gradeInfo := GradeInfo{
			Boulder: result.BoulderName,
			Route:   result.RouteName,
		}
		for _, index := range climbIndexesByUUID[result.ClimbUUID] {
			climbs[index].Grades[fmt.Sprintf("%d", result.Angle)] = gradeInfo
			climbs[index].Ascends[fmt.Sprintf("%d", result.Angle)] = result.Ascends
		}
	}

	return nil
}

func populateCatalogHighlightedHolds(climbs []CatalogClimb) {
	proxy := make([]Climb, len(climbs))
	for index, climb := range climbs {
		proxy[index] = Climb{
			UUID:          climb.UUID,
			Frames:        climb.Frames,
			ProductSizeID: climb.ProductSizeID,
		}
	}

	if err := populateClimbHighlightedHolds(proxy); err != nil {
		return
	}

	for index := range proxy {
		climbs[index].HighlightedHolds = proxy[index].HighlightedHolds
	}
}

func latestCatalogClimbToken(climbs []CatalogClimb) (catalogWatermark, bool) {
	if len(climbs) == 0 {
		return catalogWatermark{}, false
	}

	last := climbs[len(climbs)-1]
	return catalogWatermark{
		CreatedAt:     last.CreatedAt,
		UUID:          last.UUID,
		ProductSizeID: last.ProductSizeID,
	}, true
}

func latestCatalogWatermark() (catalogWatermark, error) {
	type watermarkRow struct {
		CreatedAt     string `json:"created_at"`
		UUID          string `json:"uuid"`
		ProductSizeID uint   `json:"product_size_id"`
	}

	var row watermarkRow
	query := `
SELECT
  c.created_at,
  c.uuid,
  ps.id AS product_size_id
FROM climbs c
JOIN layouts l ON c.layout_id = l.id
JOIN products p ON l.product_id = p.id
JOIN product_sizes ps ON (
  ps.product_id = l.product_id AND
  ps.edge_left <= c.edge_left AND
  ps.edge_right >= c.edge_right AND
  ps.edge_bottom <= c.edge_bottom AND
  ps.edge_top >= c.edge_top
)
WHERE c.is_listed = 1
  AND p.is_listed = 1
  AND p.name LIKE 'Kilter Board%'
GROUP BY c.uuid, ps.id
ORDER BY c.created_at DESC, c.uuid DESC, ps.id DESC
LIMIT 1`
	if err := config.KilterDB.Raw(query).Scan(&row).Error; err != nil {
		return catalogWatermark{}, fmt.Errorf("fetch catalog watermark: %w", err)
	}
	return catalogWatermark(row), nil
}

func listCatalogImageFilenames() ([]string, error) {
	type imageRow struct {
		ImageFilename string `json:"image_filename"`
	}

	var rows []imageRow
	query := `
SELECT DISTINCT psl.image_filename
FROM product_sizes_layouts_sets psl
JOIN product_sizes ps ON ps.id = psl.product_size_id
JOIN products p ON p.id = ps.product_id
WHERE p.is_listed = 1
  AND ps.is_listed = 1
  AND p.name LIKE 'Kilter Board%'
  AND psl.image_filename <> ''`
	if err := config.KilterDB.Raw(query).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("fetch catalog image filenames: %w", err)
	}

	unique := map[string]struct{}{}
	filenames := make([]string, 0, len(rows))
	for _, row := range rows {
		baseName := filepath.Base(strings.TrimSpace(row.ImageFilename))
		if baseName == "" {
			continue
		}
		if _, exists := unique[baseName]; exists {
			continue
		}
		unique[baseName] = struct{}{}
		filenames = append(filenames, baseName)
	}
	return filenames, nil
}

func catalogStorageSummary(imageFilenames []string) (int64, string, error) {
	runtimeConfig := config.GetRuntimeConfig()

	var totalBytes int64
	var generatedAt time.Time

	if info, err := os.Stat(runtimeConfig.DBPath); err == nil {
		totalBytes += info.Size()
		generatedAt = info.ModTime().UTC()
	} else if !os.IsNotExist(err) {
		return 0, "", fmt.Errorf("stat catalog database: %w", err)
	}

	for _, filename := range imageFilenames {
		imagePath := filepath.Join(runtimeConfig.ImageDir, filename)
		info, err := os.Stat(imagePath)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return 0, "", fmt.Errorf("stat catalog image %q: %w", filename, err)
		}
		totalBytes += info.Size()
		if info.ModTime().UTC().After(generatedAt) {
			generatedAt = info.ModTime().UTC()
		}
	}

	if generatedAt.IsZero() {
		generatedAt = time.Now().UTC()
	}

	return totalBytes, generatedAt.Format(time.RFC3339), nil
}

func encodeCatalogBootstrapCursor(offset int) string {
	payload, err := json.Marshal(catalogBootstrapCursor{Offset: offset})
	if err != nil {
		return ""
	}
	return base64.RawURLEncoding.EncodeToString(payload)
}

func decodeCatalogBootstrapCursor(cursor string) (int, error) {
	if strings.TrimSpace(cursor) == "" {
		return 0, nil
	}

	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return 0, fmt.Errorf("decode bootstrap cursor: %w", err)
	}

	var payload catalogBootstrapCursor
	if err := json.Unmarshal(raw, &payload); err != nil {
		return 0, fmt.Errorf("unmarshal bootstrap cursor: %w", err)
	}
	if payload.Offset < 0 {
		return 0, fmt.Errorf("invalid bootstrap cursor offset %d", payload.Offset)
	}
	return payload.Offset, nil
}

func encodeCatalogDeltaToken(token catalogDeltaToken) string {
	payload, err := json.Marshal(token)
	if err != nil {
		return ""
	}
	return base64.RawURLEncoding.EncodeToString(payload)
}

func decodeCatalogDeltaToken(token string) (*catalogDeltaToken, error) {
	if strings.TrimSpace(token) == "" {
		return nil, nil
	}

	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil {
		return nil, fmt.Errorf("decode delta token: %w", err)
	}

	var payload catalogDeltaToken
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, fmt.Errorf("unmarshal delta token: %w", err)
	}
	return &payload, nil
}

func signatureForBoards(boards []BoardOption) string {
	parts := make([]string, 0, len(boards))
	for _, board := range boards {
		parts = append(
			parts,
			fmt.Sprintf(
				"%d|%s|%s|%s|%d",
				board.ID,
				board.Name,
				board.KilterName,
				filepath.Base(board.PreviewImageFilename),
				board.ClimbCount,
			),
		)
	}
	return signatureForParts(parts...)
}

func signatureForParts(parts ...string) string {
	hash := sha1.Sum([]byte(strings.Join(parts, "||")))
	return hex.EncodeToString(hash[:])
}

func normalizeCatalogImageFilenames(filenames []string) []string {
	normalized := make([]string, 0, len(filenames))
	seen := map[string]struct{}{}
	for _, filename := range filenames {
		baseName := filepath.Base(strings.TrimSpace(filename))
		if baseName == "" {
			continue
		}
		if _, exists := seen[baseName]; exists {
			continue
		}
		seen[baseName] = struct{}{}
		normalized = append(normalized, baseName)
	}
	return normalized
}

func constCatalogClimbs() []CatalogClimb {
	return []CatalogClimb{}
}
