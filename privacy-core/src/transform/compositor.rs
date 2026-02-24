//! Selective region compositor: apply transformation only to matched regions,
//! leave the rest of the frame untouched.
//! This is the main public entry point for the transform stage.

use anyhow::Result;
use privacy_common::{
    detection::SensitiveMatch,
    frame::{RawFrame, TransformedFrame},
    transform::TransformMode,
};

use super::{
    ascii::apply_ascii, blur::apply_blur, cartoon::apply_cartoon,
    neural::apply_neural, pixelate::apply_pixelate,
};

/// Apply the selected transform to the regions indicated by `matches`,
/// leaving all other pixels in `frame` unchanged.
pub fn apply_regions(
    frame: &RawFrame,
    matches: &[SensitiveMatch],
    mode: TransformMode,
    intensity: f32,
) -> Result<TransformedFrame> {
    let mut pixels = frame.pixels.clone();
    let w = frame.width;
    let h = frame.height;

    for m in matches {
        let r = &m.bounds;
        if r.width == 0 || r.height == 0 || r.x + r.width > w || r.y + r.height > h {
            continue;
        }
        let mut region = extract_region(&pixels, w, r.x, r.y, r.width, r.height);
        match mode {
            TransformMode::Blur => apply_blur(&mut region, r.width, r.height, 15.0, intensity),
            TransformMode::Pixelate => apply_pixelate(&mut region, r.width, r.height, intensity),
            TransformMode::Cartoon => apply_cartoon(&mut region, r.width, r.height, intensity),
            TransformMode::Ascii => apply_ascii(&mut region, r.width, r.height, intensity),
            TransformMode::Neural => {
                if apply_neural(&mut region, r.width, r.height, intensity).is_err() {
                    apply_cartoon(&mut region, r.width, r.height, intensity);
                }
            }
        }
        paste_region(&mut pixels, w, r.x, r.y, r.width, r.height, &region);
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
        let dst = ((ry as usize + row) * fw + rx as usize) * 4;
        let src_off = row * row_bytes;
        pixels[dst..dst + row_bytes].copy_from_slice(&src[src_off..src_off + row_bytes]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::{detection::Severity, frame::Rect};

    fn solid_frame(w: u32, h: u32, r: u8, g: u8, b: u8) -> RawFrame {
        let n = (w * h * 4) as usize;
        let mut pixels = vec![0u8; n];
        for i in 0..w as usize * h as usize {
            pixels[i * 4] = r;
            pixels[i * 4 + 1] = g;
            pixels[i * 4 + 2] = b;
            pixels[i * 4 + 3] = 255;
        }
        RawFrame { pixels, width: w, height: h, timestamp: chrono::Utc::now() }
    }

    fn make_match(x: u32, y: u32, w: u32, h: u32) -> SensitiveMatch {
        SensitiveMatch {
            bounds: Rect { x, y, width: w, height: h },
            pattern_name: "test".into(),
            severity: Severity::High,
            snippet: "test***".into(),
        }
    }

    #[test]
    fn untouched_region_unchanged() {
        let frame = solid_frame(100, 100, 0, 255, 0); // all green
        // transform only the top-left 20x20
        let m = vec![make_match(0, 0, 20, 20)];
        let result = apply_regions(&frame, &m, TransformMode::Pixelate, 1.0).unwrap();
        // pixel at (50, 50) should remain green
        let idx = (50 * 100 + 50) * 4;
        assert_eq!(result.pixels[idx + 1], 255); // green channel
    }
}
