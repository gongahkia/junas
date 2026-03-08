package handlers

import (
	"encoding/json"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/go-playground/form/v4"
	"github.com/lczm/boardbuddy/api/config"
	"github.com/lczm/boardbuddy/api/models"
)

var decoder = form.NewDecoder()

type GetClimbsParams struct {
	Cursor   string `form:"cursor"`
	PageSize int    `form:"page_size,default=10"`
	Name     string `form:"name"`
	BoardID  uint   `form:"board_id"`
	Angle    uint   `form:"angle"`
}

// GetClimbs handles GET /api/climbs?cursor=&page_size=&name=&board_id=&angle=
// @Summary Get paginated climbs
// @Description Retrieve a paginated list of climbing routes with optional filtering. Uses cursor-based pagination for efficient navigation through large datasets.
// @Tags climbs
// @Accept json
// @Produce json
// @Param cursor query string false "Pagination cursor (timestamp for next page)" Example(2025-05-24 04:07:17.406545)
// @Param page_size query int false "Number of items per page (1-100)" default(10) minimum(1) maximum(100) Example(10)
// @Param name query string false "Filter climbs by name (partial match)" Example(swooped)
// @Param board_id query int false "Filter climbs by board/product size ID" Example(1)
// @Param angle query int false "Filter climbs by angle (5-70 degrees)" Example(45)
// @Success 200 {object} models.CursorPaginatedClimbsResponse "Successfully retrieved climbs"
// @Failure 400 {object} map[string]string "Bad request - invalid parameters"
// @Failure 500 {object} map[string]string "Internal server error"
// @Router /climbs [get]
func GetClimbs(w http.ResponseWriter, r *http.Request) {
	var params GetClimbsParams
	err := decoder.Decode(&params, r.URL.Query())
	if err != nil {
		http.Error(w, "Failed to decode query params: "+err.Error(), http.StatusBadRequest)
		return
	}

	pageSize := params.PageSize
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 10
	}

	var angle uint
	if params.Angle >= 5 && params.Angle <= 70 {
		angle = params.Angle
	}

	resp, err := models.GetPaginatedClimbs(params.Cursor, pageSize, params.Name, params.BoardID, angle)
	if err != nil {
		http.Error(w, "Failed to retrieve climbs: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GetBoardOptions handles GET /api/boards to retrieve all board options
// @Summary Get available board options
// @Description Retrieve all available board/product size options for filtering climbs. Returns a list of board configurations with their IDs and human-readable names.
// @Tags boards
// @Accept json
// @Produce json
// @Success 200 {object} map[string][]models.BoardOption "Successfully retrieved board options"
// @Failure 500 {object} map[string]string "Internal server error"
// @Example 200 application/json {"boards":[{"id":1,"name":"Original 12x12"},{"id":2,"name":"Original 16x12"},{"id":3,"name":"Home 7x10"}]}
// @Router /boards [get]
func GetBoardOptions(w http.ResponseWriter, r *http.Request) {
	boards, err := models.GetBoardOptions()
	if err != nil {
		http.Error(w, "Failed to retrieve board options: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(struct {
		Boards []models.BoardOption `json:"boards"`
	}{Boards: boards})
}

func Healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "ok",
	})
}

// ServeImage handles GET /api/images/{filename}
// @Summary Serve board layout images
// @Description Serve static image files for board layouts and holds. Images are used to display the physical board layout with hold positions for each climb.
// @Tags images
// @Accept json
// @Produce image/png,image/jpeg,image/gif
// @Param filename path string true "Image filename" Example(original-16x12-bolt-ons-v2.png)
// @Success 200 {file} file "Successfully served image file"
// @Failure 400 {object} map[string]string "Bad request - invalid filename"
// @Failure 404 {object} map[string]string "Not found - image file does not exist"
// @Example 400 application/json {"error":"Invalid filename"}
// @Example 404 application/json {"error":"File not found"}
// @Router /images/{filename} [get]
func ServeImage(w http.ResponseWriter, r *http.Request) {
	filename := chi.URLParam(r, "filename")
	if filename == "" {
		http.Error(w, "Filename is required", http.StatusBadRequest)
		return
	}

	// Sanitize filename to prevent directory traversal
	filename = filepath.Base(filename)
	if strings.Contains(filename, "..") || strings.Contains(filename, "/") {
		http.Error(w, "Invalid filename", http.StatusBadRequest)
		return
	}

	// Construct the file path
	imagePath := filepath.Join(config.GetRuntimeConfig().ImageDir, filename)

	// Serve the file
	http.ServeFile(w, r, imagePath)
}
