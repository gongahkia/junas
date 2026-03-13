package runtimeinfo

import (
	"fmt"
	"math"
	"path/filepath"
	"syscall"
	"time"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
)

type Severity string

const (
	SeverityUnknown  Severity = "unknown"
	SeverityOK       Severity = "ok"
	SeverityWarning  Severity = "warning"
	SeverityCritical Severity = "critical"
)

type StorageView struct {
	Severity        Severity `json:"severity"`
	Message         string   `json:"message"`
	MountPath       string   `json:"mount_path"`
	UsedBytes       uint64   `json:"used_bytes"`
	AvailableBytes  uint64   `json:"available_bytes"`
	TotalBytes      uint64   `json:"total_bytes"`
	UsagePercent    float64  `json:"usage_percent"`
	WarningPercent  int      `json:"warning_percent"`
	CriticalPercent int      `json:"critical_percent"`
}

type StatusView struct {
	Status         Severity    `json:"status"`
	RuntimeReady   bool        `json:"runtime_ready"`
	RuntimeMessage string      `json:"runtime_message,omitempty"`
	Storage        StorageView `json:"storage"`
	GeneratedAt    time.Time   `json:"generated_at"`
}

func Snapshot(runtimeConfig config.RuntimeConfig) *StatusView {
	runtimeReady := config.AppDB != nil
	runtimeMessage := ""
	if !runtimeReady {
		runtimeMessage = "app database is not configured"
	} else if !runtimeConfig.EnableTestProvider {
		if err := bootstrap.RuntimeReady(runtimeConfig.DBPath, runtimeConfig.ImageDir, runtimeConfig.StatePath); err != nil {
			runtimeReady = false
			runtimeMessage = err.Error()
		}
	}

	storage := inspectStorage(runtimeConfig)
	status := storage.Severity
	if !runtimeReady && status != SeverityCritical {
		status = SeverityCritical
	}

	return &StatusView{
		Status:         status,
		RuntimeReady:   runtimeReady,
		RuntimeMessage: runtimeMessage,
		Storage:        storage,
		GeneratedAt:    time.Now().UTC(),
	}
}

func inspectStorage(runtimeConfig config.RuntimeConfig) StorageView {
	mountPath := runtimeConfig.DataDir
	statfs, err := statfsForPath(mountPath)
	if err != nil {
		return StorageView{
			Severity:        SeverityUnknown,
			Message:         fmt.Sprintf("Unable to inspect storage at %s: %v", mountPath, err),
			MountPath:       mountPath,
			WarningPercent:  runtimeConfig.StorageWarnPercent,
			CriticalPercent: runtimeConfig.StorageCriticalPercent,
		}
	}

	totalBytes := statfs.Blocks * uint64(statfs.Bsize)
	availableBytes := statfs.Bavail * uint64(statfs.Bsize)
	if availableBytes > totalBytes {
		availableBytes = totalBytes
	}

	usedBytes := uint64(0)
	if totalBytes > availableBytes {
		usedBytes = totalBytes - availableBytes
	}

	usagePercent := 0.0
	if totalBytes > 0 {
		usagePercent = roundToTenth((float64(usedBytes) / float64(totalBytes)) * 100)
	}

	severity := SeverityOK
	message := fmt.Sprintf("Storage healthy with %.1f%% used and %s free.", usagePercent, humanBytes(availableBytes))
	if usagePercent >= float64(runtimeConfig.StorageCriticalPercent) {
		severity = SeverityCritical
		message = fmt.Sprintf(
			"Storage critically low at %.1f%% used with %s free. New sessions, images, or recaps may fail soon.",
			usagePercent,
			humanBytes(availableBytes),
		)
	} else if usagePercent >= float64(runtimeConfig.StorageWarnPercent) {
		severity = SeverityWarning
		message = fmt.Sprintf(
			"Storage nearing full at %.1f%% used with %s free. Plan a cleanup or volume resize soon.",
			usagePercent,
			humanBytes(availableBytes),
		)
	}

	return StorageView{
		Severity:        severity,
		Message:         message,
		MountPath:       mountPath,
		UsedBytes:       usedBytes,
		AvailableBytes:  availableBytes,
		TotalBytes:      totalBytes,
		UsagePercent:    usagePercent,
		WarningPercent:  runtimeConfig.StorageWarnPercent,
		CriticalPercent: runtimeConfig.StorageCriticalPercent,
	}
}

func statfsForPath(path string) (*syscall.Statfs_t, error) {
	candidates := []string{path, filepath.Dir(path), "."}
	var statfs syscall.Statfs_t
	var lastErr error
	for _, candidate := range candidates {
		if candidate == "" {
			continue
		}
		if err := syscall.Statfs(candidate, &statfs); err == nil {
			return &statfs, nil
		} else {
			lastErr = err
		}
	}

	if lastErr == nil {
		lastErr = fmt.Errorf("no filesystem candidates were available")
	}
	return nil, lastErr
}

func humanBytes(bytes uint64) string {
	if bytes < 1024 {
		return fmt.Sprintf("%d B", bytes)
	}

	units := []string{"KB", "MB", "GB", "TB", "PB"}
	value := float64(bytes)
	unitIndex := -1
	for value >= 1024 && unitIndex < len(units)-1 {
		value /= 1024
		unitIndex++
	}

	return fmt.Sprintf("%.1f %s", value, units[unitIndex])
}

func roundToTenth(value float64) float64 {
	return math.Round(value*10) / 10
}
