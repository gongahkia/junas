package handlers

import (
	"net/http"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/runtimeinfo"
)

func GetRuntimeStatus(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, runtimeinfo.Snapshot(config.GetRuntimeConfig()))
}
