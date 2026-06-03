//! Prototype adapter for a future native OBS source/filter plugin.
//!
//! OBS plugins can stage frames as CPU RGBA buffers. This adapter keeps that
//! boundary explicit and reuses Aki's existing transform registry. Detection
//! stays outside this prototype; a native plugin would feed OCR/detection
//! results into `DetectedRegions` before calling this adapter.

use anyhow::{anyhow, Result};
use privacy_common::{
    detection::DetectedRegions,
    frame::{RawFrame, TransformedFrame},
    transform::TransformMode,
};

use crate::transform::registry::apply_transform;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ObsSourceFrame {
    pub pixels: Vec<u8>,
    pub width: u32,
    pub height: u32,
}

impl ObsSourceFrame {
    pub fn new(pixels: Vec<u8>, width: u32, height: u32) -> Result<Self> {
        let expected_len = frame_len(width, height)?;
        if pixels.len() != expected_len {
            return Err(anyhow!(
                "OBS frame buffer length {} does not match {}x{} RGBA length {}",
                pixels.len(),
                width,
                height,
                expected_len
            ));
        }
        Ok(Self {
            pixels,
            width,
            height,
        })
    }

    fn as_raw_frame(&self) -> RawFrame {
        RawFrame {
            pixels: self.pixels.clone(),
            width: self.width,
            height: self.height,
            timestamp: chrono::Utc::now(),
        }
    }
}

pub fn apply_transform_to_obs_frame(
    frame: &ObsSourceFrame,
    regions: &DetectedRegions,
    mode: TransformMode,
    intensity: f32,
) -> Result<ObsSourceFrame> {
    let raw = frame.as_raw_frame();
    let transformed = apply_transform(&raw, regions, mode, intensity)?;
    ObsSourceFrame::try_from(transformed)
}

impl TryFrom<TransformedFrame> for ObsSourceFrame {
    type Error = anyhow::Error;

    fn try_from(frame: TransformedFrame) -> Result<Self> {
        Self::new(frame.pixels, frame.width, frame.height)
    }
}

fn frame_len(width: u32, height: u32) -> Result<usize> {
    width
        .checked_mul(height)
        .and_then(|pixels| pixels.checked_mul(4))
        .map(|bytes| bytes as usize)
        .ok_or_else(|| anyhow!("OBS frame dimensions are too large: {}x{}", width, height))
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::{
        detection::{DetectedRegions, SensitiveMatch, Severity},
        frame::Rect,
        transform::TransformMode,
    };

    #[test]
    fn rejects_invalid_rgba_buffer_length() {
        let err = ObsSourceFrame::new(vec![0; 3], 2, 2).unwrap_err();
        assert!(err.to_string().contains("does not match"));
    }

    #[test]
    fn prototype_applies_existing_pixelate_transform() {
        let frame = ObsSourceFrame::new(gradient_rgba(32, 24), 32, 24).unwrap();
        let regions = DetectedRegions {
            matches: vec![SensitiveMatch {
                bounds: Rect {
                    x: 4,
                    y: 4,
                    width: 16,
                    height: 12,
                },
                pattern_name: "obs-prototype-fixture".to_string(),
                severity: Severity::High,
                snippet: "AKI_***".to_string(),
            }],
        };

        let transformed =
            apply_transform_to_obs_frame(&frame, &regions, TransformMode::Pixelate, 1.0).unwrap();

        assert_eq!(transformed.width, frame.width);
        assert_eq!(transformed.height, frame.height);
        assert_ne!(transformed.pixels, frame.pixels);
    }

    fn gradient_rgba(width: u32, height: u32) -> Vec<u8> {
        let mut pixels = Vec::with_capacity((width * height * 4) as usize);
        for y in 0..height {
            for x in 0..width {
                pixels.push(((x * 7) % 255) as u8);
                pixels.push(((y * 11) % 255) as u8);
                pixels.push((((x + y) * 5) % 255) as u8);
                pixels.push(255);
            }
        }
        pixels
    }
}
