//! Transformation registry: enum TransformMode with factory returning a trait object.

use anyhow::Result;
use privacy_common::{
    detection::DetectedRegions,
    frame::{RawFrame, TransformedFrame},
    transform::TransformMode,
};

use super::{
    ascii::apply_ascii, blur::apply_blur, cartoon::apply_cartoon, pixelate::apply_pixelate,
};

/// Apply the selected `TransformMode` to the frame at the detected regions.
/// `intensity` is in [0.0, 1.0]. Returns a `TransformedFrame`.
pub fn apply_transform(
    frame: &RawFrame,
    regions: &DetectedRegions,
    mode: TransformMode,
    intensity: f32,
) -> Result<TransformedFrame> {
    let mut pixels = frame.pixels.clone();
    let w = frame.width;
    let h = frame.height;

    for m in &regions.matches {
        let r = &m.bounds;
        if r.x + r.width > w || r.y + r.height > h || r.width == 0 || r.height == 0 {
            continue;
        }
        // extract region sub-slice (row-contiguous copy)
        let mut region_pixels = extract_region(&pixels, w, r.x, r.y, r.width, r.height);

        match mode {
            TransformMode::Blur => apply_blur(&mut region_pixels, r.width, r.height, 15.0, intensity),
            TransformMode::Pixelate => apply_pixelate(&mut region_pixels, r.width, r.height, intensity),
            TransformMode::Cartoon => apply_cartoon(&mut region_pixels, r.width, r.height, intensity),
            TransformMode::Ascii => apply_ascii(&mut region_pixels, r.width, r.height, intensity),
        }

        // write transformed region back into full-frame pixels
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
