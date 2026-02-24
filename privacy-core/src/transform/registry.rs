//! Transformation registry: enum TransformMode with factory returning a trait object.

use anyhow::Result;
use privacy_common::{
    detection::{DetectedRegions, SensitiveMatch, Severity, PatternCategory},
    frame::{RawFrame, Rect, TransformedFrame},
    transform::TransformMode,
};
use rayon::prelude::*;
use std::time::Instant;

use super::{
    ascii::apply_ascii, blur::apply_blur, cartoon::apply_cartoon,
    neural::apply_neural, pixelate::apply_pixelate,
};

/// >30ms per region triggers cartoon fallback for that frame
const NEURAL_LATENCY_GUARD_MS: u128 = 30;

/// Check if rect `r` overlaps any zone in the list.
fn in_any_zone(r: &privacy_common::frame::Rect, zones: &[privacy_common::frame::Rect]) -> bool {
    zones.iter().any(|z| {
        r.x < z.x + z.width && r.x + r.width > z.x &&
        r.y < z.y + z.height && r.y + r.height > z.y
    })
}

/// Apply the selected `TransformMode` to the frame at the detected regions.
/// Respects safe_zones (never redact) and always_redact_zones (always redact).
/// `intensity` is in [0.0, 1.0]. Returns a `TransformedFrame`.
pub fn apply_transform(
    frame: &RawFrame,
    regions: &DetectedRegions,
    mode: TransformMode,
    intensity: f32,
) -> Result<TransformedFrame> {
    apply_transform_with_zones(frame, regions, mode, intensity, &[], &[])
}

pub fn apply_transform_with_zones(
    frame: &RawFrame,
    regions: &DetectedRegions,
    mode: TransformMode,
    intensity: f32,
    safe_zones: &[Rect],
    always_redact_zones: &[Rect],
) -> Result<TransformedFrame> {
    let pixels_snapshot = frame.pixels.clone();
    let mut pixels = pixels_snapshot.clone();
    let w = frame.width;
    let h = frame.height;

    // synthetic matches for always-redact zones
    let always_matches: Vec<SensitiveMatch> = always_redact_zones.iter()
        .map(|z| SensitiveMatch {
            bounds: z.clone(),
            pattern_name: "always_redact_zone".into(),
            severity: Severity::High,
            snippet: "***".into(),
        })
        .collect();

    // combine pattern matches (excluding safe zones) with always-redact synthetic matches
    let combined: Vec<&SensitiveMatch> = regions.matches.iter()
        .filter(|m| !in_any_zone(&m.bounds, safe_zones))
        .chain(always_matches.iter())
        .collect();

    // process all valid regions in parallel, collect (bounds, transformed_pixels)
    let valid: Vec<_> = combined.iter()
        .filter(|m| {
            let r = &m.bounds;
            r.x + r.width <= w && r.y + r.height <= h && r.width > 0 && r.height > 0
        })
        .collect();

    let transformed: Vec<_> = valid.par_iter().map(|&&m| {
        let m = m;
        let r = &m.bounds;
        let mut region_pixels = extract_region(&pixels_snapshot, w, r.x, r.y, r.width, r.height);
        match mode {
            TransformMode::Blur => apply_blur(&mut region_pixels, r.width, r.height, 15.0, intensity),
            TransformMode::Pixelate => apply_pixelate(&mut region_pixels, r.width, r.height, intensity),
            TransformMode::Cartoon => apply_cartoon(&mut region_pixels, r.width, r.height, intensity),
            TransformMode::Ascii => apply_ascii(&mut region_pixels, r.width, r.height, intensity),
            TransformMode::Neural => {
                let t0 = Instant::now();
                let ok = apply_neural(&mut region_pixels, r.width, r.height, intensity).is_ok();
                let elapsed = t0.elapsed().as_millis();
                if !ok || elapsed > NEURAL_LATENCY_GUARD_MS {
                    if elapsed > NEURAL_LATENCY_GUARD_MS {
                        log::warn!("neural inference {}ms > {}ms budget, cartoon fallback", elapsed, NEURAL_LATENCY_GUARD_MS);
                    }
                    let mut fallback = extract_region(&pixels_snapshot, w, r.x, r.y, r.width, r.height);
                    apply_cartoon(&mut fallback, r.width, r.height, intensity);
                    return (r, fallback);
                }
            }
        }
        (r, region_pixels)
    }).collect();

    // sequential merge back into full-frame buffer (write ordering doesn't matter for non-overlapping regions)
    for (r, region_pixels) in transformed {
        paste_region(&mut pixels, w, r.x, r.y, r.width, r.height, &region_pixels);
    }

    Ok(TransformedFrame {
        pixels,
        width: w,
        height: h,
        timestamp: frame.timestamp,
    })
}

fn extract_region(pixels: &[u8], frame_w: u32, rx: u32, ry: u32, rw: u32, rh: u32) -> Vec<u8> {
    let fw = frame_w as usize;
    let row_bytes = rw as usize * 4;
    let mut out = Vec::with_capacity(rh as usize * row_bytes);
    for row in 0..rh as usize {
        let start = ((ry as usize + row) * fw + rx as usize) * 4;
        out.extend_from_slice(&pixels[start..start + row_bytes]);
    }
    out
}

fn paste_region(pixels: &mut [u8], frame_w: u32, rx: u32, ry: u32, rw: u32, rh: u32, src: &[u8]) {
    let fw = frame_w as usize;
    let row_bytes = rw as usize * 4;
    for row in 0..rh as usize {
        let dst_start = ((ry as usize + row) * fw + rx as usize) * 4;
        let src_start = row * row_bytes;
        pixels[dst_start..dst_start + row_bytes]
            .copy_from_slice(&src[src_start..src_start + row_bytes]);
    }
}
