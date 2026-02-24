//! Training data collector: save false-positive regions for pattern improvement.
//! User marks a region as "safe" (false positive) via keybinding;
//! the region's raw pixels and match metadata are saved to a dataset directory.

use anyhow::Result;
use privacy_common::{detection::SensitiveMatch, frame::RawFrame};
use std::path::PathBuf;

/// Default dataset directory.
pub fn dataset_dir() -> PathBuf {
    let cache = std::env::var("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".cache"));
    cache.join("ascii-privacy").join("training-data")
}

/// Save a false-positive region to the dataset.
/// Writes raw RGBA PNG + JSON metadata alongside it.
pub fn save_false_positive(frame: &RawFrame, m: &SensitiveMatch) -> Result<PathBuf> {
    let dir = dataset_dir();
    std::fs::create_dir_all(&dir)?;

    let ts = chrono::Utc::now().format("%Y%m%d_%H%M%S_%3f");
    let stem = format!("fp_{ts}_{}", m.pattern_name.replace('/', "_"));

    // extract region pixels
    let r = &m.bounds;
    let fw = frame.width as usize;
    let row_bytes = r.width as usize * 4;
    let mut region_pixels = Vec::with_capacity(r.height as usize * row_bytes);
    for row in 0..r.height as usize {
        let start = ((r.y as usize + row) * fw + r.x as usize) * 4;
        if start + row_bytes <= frame.pixels.len() {
            region_pixels.extend_from_slice(&frame.pixels[start..start + row_bytes]);
        }
    }

    // save PNG via image crate
    let png_path = dir.join(format!("{stem}.png"));
    let img = image::RgbaImage::from_raw(r.width, r.height, region_pixels)
        .ok_or_else(|| anyhow::anyhow!("could not create image from region"))?;
    img.save(&png_path)?;

    // save JSON metadata
    let meta = serde_json::json!({
        "timestamp": chrono::Utc::now().to_rfc3339(),
        "pattern_name": m.pattern_name,
        "severity": format!("{:?}", m.severity),
        "snippet": m.snippet,
        "bounds": {"x": r.x, "y": r.y, "w": r.width, "h": r.height},
        "label": "false_positive",
    });
    let json_path = dir.join(format!("{stem}.json"));
    std::fs::write(&json_path, serde_json::to_string_pretty(&meta)?)?;

    log::info!("false positive saved: {}", png_path.display());
    Ok(png_path)
}
