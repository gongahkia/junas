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
}

impl Default for DetectionConfig {
    fn default() -> Self {
        Self {
            ocr_engine: "tesseract".into(),
            min_confidence: 40,
            grid_cells_x: 8,
            grid_cells_y: 6,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct TransformConfig {
    /// "cartoon" | "ascii" | "pixelate" | "blur"
    pub mode: String,
    /// 0.0 – 1.0
    pub intensity: f32,
}

impl Default for TransformConfig {
    fn default() -> Self {
        Self { mode: "blur".into(), intensity: 1.0 }
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

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub capture: CaptureConfig,
    pub detection: DetectionConfig,
    pub transform: TransformConfig,
    pub output: OutputConfig,
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
