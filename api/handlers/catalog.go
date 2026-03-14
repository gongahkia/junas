package handlers

import (
	"errors"
	"net/http"

	"github.com/go-playground/form/v4"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/models"
)

type catalogBootstrapParams struct {
	Cursor   string `form:"cursor"`
	PageSize int    `form:"page_size,default=200"`
}

type catalogDeltaParams struct {
	AfterToken string `form:"after_token"`
}

func GetKilterCatalogManifest(w http.ResponseWriter, r *http.Request) {
	if config.KilterDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "kilter runtime data is not available")
		return
	}

	manifest, err := models.GetCatalogManifest()
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "failed to retrieve catalog manifest")
		return
	}

	writeJSON(w, http.StatusOK, manifest)
}

func GetKilterCatalogBootstrap(w http.ResponseWriter, r *http.Request) {
	if config.KilterDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "kilter runtime data is not available")
		return
	}

	var params catalogBootstrapParams
	if err := decoder.Decode(&params, r.URL.Query()); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid query parameters")
		return
	}

	response, err := models.ListCatalogBootstrap(params.Cursor, params.PageSize)
	if err != nil {
		if errors.Is(err, models.ErrInvalidCursor) {
			writeJSONError(w, http.StatusBadRequest, "invalid pagination cursor")
			return
		}
		writeJSONError(w, http.StatusInternalServerError, "failed to retrieve catalog bootstrap")
		return
	}

	writeJSON(w, http.StatusOK, response)
}

func GetKilterCatalogDelta(w http.ResponseWriter, r *http.Request) {
	if config.KilterDB == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "kilter runtime data is not available")
		return
	}

	var params catalogDeltaParams
	if err := form.NewDecoder().Decode(&params, r.URL.Query()); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid query parameters")
		return
	}

	response, err := models.ListCatalogDelta(params.AfterToken)
	if err != nil {
		if errors.Is(err, models.ErrInvalidCursor) {
			writeJSONError(w, http.StatusBadRequest, "invalid pagination cursor")
			return
		}
		writeJSONError(w, http.StatusInternalServerError, "failed to retrieve catalog delta")
		return
	}

	writeJSON(w, http.StatusOK, response)
}
