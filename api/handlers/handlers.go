package handlers

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/go-playground/form/v4"
	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/models"
)

var decoder = form.NewDecoder()

type GetClimbsParams struct {
	Cursor   string `form:"cursor"`
	PageSize int    `form:"page_size,default=10"`
	Name     string `form:"name"`
	Setter   string `form:"setter"`
	BoardID  uint   `form:"board_id"`
	Angle    uint   `form:"angle"`
	Sort     string `form:"sort,default=popular"`
}

// GetClimbs handles GET /api/climbs?cursor=&page_size=&name=&setter=&board_id=&angle=&sort=
// @Summary Get paginated climbs
// @Description Retrieve a paginated list of listed Kilter Board climbs with filtering, sorting, and cursor-based pagination.
// @Tags climbs
// @Accept json
// @Produce json
// @Param cursor query string false "Pagination cursor returned by the previous page" Example(eyJzb3J0IjoicG9wdWxhciIsImFzY2VuZHMiOjQyLCJjcmVhdGVkX2F0IjoiMjAyNi0wMS0wMSAwMDowMDowMC4wMDAwMDAiLCJ1dWlkIjoidXVpZC0xIiwicHJvZHVjdF9zaXplX2lkIjoxNH0=)
// @Param page_size query int false "Number of items per page (1-100)" default(10) minimum(1) maximum(100) Example(10)
// @Param name query string false "Filter climbs by climb name (partial match)" Example(swooped)
// @Param setter query string false "Filter climbs by setter username (partial match)" Example(jwebxl)
// @Param board_id query int false "Filter climbs by board/product size ID" Example(14)
// @Param angle query int true "Filter climbs by board angle (supported angles: 5-70)" Example(40)
// @Param sort query string false "Sort order for the result set" Enums(popular,newest) default(popular)
// @Success 200 {object} models.CursorPaginatedClimbsResponse "Successfully retrieved climbs"
// @Failure 400 {object} map[string]string "Bad request - invalid parameters"
// @Failure 500 {object} map[string]string "Internal server error"
// @Router /climbs [get]
func GetClimbs(w http.ResponseWriter, r *http.Request) {
	if config.KilterDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "kilter runtime data is not available")
		return
	}

	var params GetClimbsParams
	err := decoder.Decode(&params, r.URL.Query())
	if err != nil {
		slog.Warn("failed to decode query params", "error", err)
		writeJSONError(w, http.StatusBadRequest, "invalid query parameters")
		return
	}

	if len(params.Name) > 200 {
		params.Name = params.Name[:200]
	}
	if len(params.Setter) > 200 {
		params.Setter = params.Setter[:200]
	}

	pageSize := params.PageSize
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 10
	}

	if !models.IsSupportedAngle(params.Angle) {
		writeJSONError(w, http.StatusBadRequest, "angle is required and must be one of 5,10,15,20,25,30,35,40,45,50,55,60,65,70")
		return
	}

	sort := models.NormalizeSort(params.Sort)
	if sort == "" {
		writeJSONError(w, http.StatusBadRequest, "sort must be one of: popular, newest")
		return
	}

	resp, err := models.GetPaginatedClimbs(
		params.Cursor,
		pageSize,
		params.Name,
		params.Setter,
		params.BoardID,
		params.Angle,
		sort,
	)
	if err != nil {
		if errors.Is(err, models.ErrInvalidCursor) {
			writeJSONError(w, http.StatusBadRequest, "invalid pagination cursor")
			return
		}
		slog.Error("failed to retrieve climbs", "error", err)
		writeJSONError(w, http.StatusInternalServerError, "failed to retrieve climbs")
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
	if config.KilterDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "kilter runtime data is not available")
		return
	}

	boards, err := models.GetBoardOptions()
	if err != nil {
		slog.Error("failed to retrieve board options", "error", err)
		writeJSONError(w, http.StatusInternalServerError, "failed to retrieve board options")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(struct {
		Boards []models.BoardOption `json:"boards"`
	}{Boards: boards})
}

func Healthz(w http.ResponseWriter, r *http.Request) {
	Readyz(w, r)
}

func Livez(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status": "ok",
	})
}

func Readyz(w http.ResponseWriter, r *http.Request) {
	runtimeConfig := config.GetRuntimeConfig()
	if config.AppDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "app database is not configured")
		return
	}

	if !runtimeConfig.EnableTestProvider {
		if err := bootstrap.RuntimeReady(runtimeConfig.DBPath, runtimeConfig.ImageDir, runtimeConfig.StatePath); err != nil {
			writeJSONError(w, http.StatusServiceUnavailable, err.Error())
			return
		}
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status": "ok",
	})
}

func Metrics(w http.ResponseWriter, r *http.Request) {
	if metricsHandler == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "metrics are unavailable")
		return
	}
	metricsHandler.ServeHTTP(w, r)
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
		writeJSONError(w, http.StatusBadRequest, "filename is required")
		return
	}

	// Sanitize filename to prevent directory traversal
	filename = filepath.Base(filename)
	if strings.Contains(filename, "..") || strings.Contains(filename, "/") {
		writeJSONError(w, http.StatusBadRequest, "invalid filename")
		return
	}

	// Construct the file path
	imagePath := filepath.Join(config.GetRuntimeConfig().ImageDir, filename)

	// Serve the file
	http.ServeFile(w, r, imagePath)
}
