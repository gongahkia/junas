//! Application config loaded from ~/.config/ascii-privacy/config.toml.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Returns the config file path (~/.config/ascii-privacy/config.toml).
pub fn config_path() -> PathBuf {
    let base = std::env::var("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_default();
            PathBuf::from(home).join(".config")
        });
    base.join("ascii-privacy").join("config.toml")
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct CaptureConfig {
    /// "macos", "x11", "wayland"
    pub source: String,
    /// Substring match for window title (empty = full screen).
    pub window_title_match: String,
    pub fps: u32,
    /// Optional capture region "x,y,w,h".
    pub region: Option<String>,
}

impl Default for CaptureConfig {
    fn default() -> Self {
        Self {
            source: detect_default_source(),
            window_title_match: String::new(),
            fps: 30,
            region: None,
        }
    }
}

fn detect_default_source() -> String {
    #[cfg(target_os = "macos")] { return "macos".into(); }
    #[cfg(target_os = "linux")] {
        if std::env::var("WAYLAND_DISPLAY").is_ok() { return "wayland".into(); }
        return "x11".into();
    }
    #[allow(unreachable_code)]
    "unknown".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct DetectionConfig {
    /// "tesseract"
    pub ocr_engine: String,
    /// Minimum OCR confidence 0–100.
    pub min_confidence: u32,
    /// Grid columns for incremental OCR.
    pub grid_cells_x: u32,
    /// Grid rows for incremental OCR.
    pub grid_cells_y: u32,
    /// Screen regions (as "x,y,w,h") that are NEVER redacted even if patterns match.
    pub safe_zones: Vec<String>,
    /// Screen regions (as "x,y,w,h") that are ALWAYS transformed regardless of pattern matches.
    pub always_redact_zones: Vec<String>,
}

impl Default for DetectionConfig {
    fn default() -> Self {
        Self {
            ocr_engine: "tesseract".into(),
            min_confidence: 40,
            grid_cells_x: 8,
            grid_cells_y: 6,
            safe_zones: Vec::new(),
            always_redact_zones: Vec::new(),
        }
    }
}

/// Parse a "x,y,w,h" rect string.
pub fn parse_rect(s: &str) -> Option<privacy_common::frame::Rect> {
    let parts: Vec<u32> = s.split(',')
        .map(|p| p.trim().parse().ok())
        .collect::<Option<Vec<_>>>()?;
    if parts.len() != 4 { return None; }
    Some(privacy_common::frame::Rect { x: parts[0], y: parts[1], width: parts[2], height: parts[3] })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct TransformConfig {
    /// "cartoon" | "ascii" | "pixelate" | "blur" | "neural"
    pub mode: String,
    /// 0.0 – 1.0
    pub intensity: f32,
    /// ONNX Runtime execution provider: "auto" | "cuda" | "coreml" | "cpu"
    pub accelerator: String,
    /// Blending alpha for transformed regions (0.0 = transparent, 1.0 = opaque)
    pub region_alpha: f32,
    /// Max neural inference ms before cartoon fallback (default 100ms for CPU)
    pub neural_latency_guard_ms: u64,
}

impl Default for TransformConfig {
    fn default() -> Self {
        Self {
            mode: "blur".into(),
            intensity: 1.0,
            accelerator: "auto".into(),
            region_alpha: 1.0,
            neural_latency_guard_ms: 100,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct OutputConfig {
    /// "v4l2" | "coremedia" | "mjpeg"
    pub sink: String,
    /// Port for MJPEG HTTP server.
    pub http_port: u16,
    /// Device path for v4l2loopback (Linux).
    pub v4l2_device: String,
}

impl Default for OutputConfig {
    fn default() -> Self {
        Self {
            sink: "auto".into(),
            http_port: 9876,
            v4l2_device: "/dev/video2".into(),
        }
    }
}

/// A named profile that overrides transform mode and pattern sets.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ProfileConfig {
    /// Transform mode override: "blur" | "cartoon" | "neural" | etc.
    pub transform_mode: String,
    /// Transform intensity override (0.0–1.0).
    pub intensity: f32,
    /// Optional list of extra pattern names to enable for this profile.
    pub extra_patterns: Vec<String>,
}

impl Default for ProfileConfig {
    fn default() -> Self {
        Self { transform_mode: "blur".into(), intensity: 1.0, extra_patterns: Vec::new() }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub capture: CaptureConfig,
    pub detection: DetectionConfig,
    pub transform: TransformConfig,
    pub output: OutputConfig,
    /// Named profiles: [profiles.streaming], [profiles.pairing], etc.
    pub profiles: std::collections::HashMap<String, ProfileConfig>,
}

impl AppConfig {
    /// Load from default path, returning defaults if file is absent.
    pub fn load() -> Result<Self> {
        Self::load_from(&config_path())
    }

    /// Load from explicit path, returning defaults if file is absent.
    pub fn load_from(path: &std::path::Path) -> Result<Self> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("reading config {}", path.display()))?;
        toml::from_str(&raw)
            .with_context(|| format!("parsing config {}", path.display()))
    }

    /// Write defaults to the config path if the file does not yet exist.
    pub fn write_defaults_if_missing() -> Result<()> {
        let path = config_path();
        if path.exists() { return Ok(()); }
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let content = toml::to_string_pretty(&Self::default())?;
        std::fs::write(&path, content)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_defaults() {
        let cfg = AppConfig::default();
        let s = toml::to_string_pretty(&cfg).unwrap();
        let back: AppConfig = toml::from_str(&s).unwrap();
        assert_eq!(back.capture.fps, cfg.capture.fps);
        assert_eq!(back.detection.min_confidence, cfg.detection.min_confidence);
        assert!((back.transform.intensity - cfg.transform.intensity).abs() < 1e-6);
        assert_eq!(back.output.http_port, cfg.output.http_port);
    }
}
