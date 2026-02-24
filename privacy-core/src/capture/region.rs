//! Capture region selection: window_id or manual rect, with RGBA frame cropping.

use anyhow::{anyhow, Result};
use privacy_common::frame::{RawFrame, Rect};

/// What region to capture.
#[derive(Debug, Clone)]
pub enum CaptureRegion {
    /// Capture a specific window by id.
    Window(u64),
    /// Capture a manually specified rect (absolute screen coords).
    ManualRect(Rect),
    /// Capture the full output of the underlying source (no crop).
    Full,
}

/// Crop an RGBA (4 bytes/pixel, row-major) frame to `region`.
/// Returns a new `RawFrame` with only the cropped pixels.
pub fn crop_frame(frame: &RawFrame, region: &Rect) -> Result<RawFrame> {
    let rx = region.x;
    let ry = region.y;
    let rw = region.width;
    let rh = region.height;

    if rx + rw > frame.width || ry + rh > frame.height {
        return Err(anyhow!(
            "crop region {}x{}+{},{} exceeds frame {}x{}",
            rw, rh, rx, ry, frame.width, frame.height
        ));
    }

    let stride = frame.width as usize * 4;
    let row_bytes = rw as usize * 4;
    let mut pixels = Vec::with_capacity(rh as usize * row_bytes);

    for row in 0..rh as usize {
        let src_start = (ry as usize + row) * stride + rx as usize * 4;
        pixels.extend_from_slice(&frame.pixels[src_start..src_start + row_bytes]);
    }

    Ok(RawFrame {
        pixels,
        width: rw,
        height: rh,
        timestamp: frame.timestamp,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn crop_center_2x2() {
        // 4x4 RGBA frame filled with sequential bytes
        let w = 4u32;
        let h = 4u32;
        let pixels: Vec<u8> = (0..w * h * 4).map(|i| i as u8).collect();
        let frame = RawFrame { pixels, width: w, height: h, timestamp: Utc::now() };

        let region = Rect { x: 1, y: 1, width: 2, height: 2 };
        let cropped = crop_frame(&frame, &region).unwrap();
        assert_eq!(cropped.width, 2);
        assert_eq!(cropped.height, 2);
        // row 1 col 1 offset = (1*4 + 1) * 4 = 20
        assert_eq!(cropped.pixels[0], frame.pixels[20]);
        // row 1 of cropped starts at byte 8 (2 pixels * 4 bytes/pixel)
        assert_eq!(cropped.pixels[8], frame.pixels[36]); // (2*16 + 1*4) = 36
    }

    #[test]
    fn crop_out_of_bounds_errors() {
        let frame = RawFrame {
            pixels: vec![0u8; 16 * 4],
            width: 4, height: 4,
            timestamp: Utc::now(),
        };
        let region = Rect { x: 3, y: 3, width: 2, height: 2 };
        assert!(crop_frame(&frame, &region).is_err());
    }
}
