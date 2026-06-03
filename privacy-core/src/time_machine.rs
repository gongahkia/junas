//! Prototype ring buffer for local-recording retroactive redaction.
//!
//! This is intentionally separate from live output. It can re-render buffered
//! frames before a local recording is finalized, but it cannot unsend frames
//! that already went to a livestream, virtual camera, or MJPEG client.

use anyhow::{anyhow, Result};
use privacy_common::{
    detection::{DetectedRegions, SensitiveMatch},
    frame::{RawFrame, TransformedFrame},
    transform::TransformMode,
};
use std::collections::VecDeque;

use crate::transform::registry::apply_transform;

#[derive(Debug, Clone)]
pub struct BufferedFrame {
    pub frame: RawFrame,
    pub regions: DetectedRegions,
}

#[derive(Debug)]
pub struct TimeMachineBuffer {
    capacity_frames: usize,
    frames: VecDeque<BufferedFrame>,
}

impl TimeMachineBuffer {
    pub fn new(seconds: u32, fps: u32) -> Self {
        let capacity_frames = seconds.saturating_mul(fps).max(1) as usize;
        Self {
            capacity_frames,
            frames: VecDeque::with_capacity(capacity_frames),
        }
    }

    pub fn capacity_frames(&self) -> usize {
        self.capacity_frames
    }

    pub fn len(&self) -> usize {
        self.frames.len()
    }

    pub fn is_empty(&self) -> bool {
        self.frames.is_empty()
    }

    pub fn push(&mut self, frame: RawFrame, regions: DetectedRegions) {
        if self.frames.len() == self.capacity_frames {
            self.frames.pop_front();
        }
        self.frames.push_back(BufferedFrame { frame, regions });
    }

    pub fn add_manual_region_to_recent(&mut self, region: SensitiveMatch, recent_frames: usize) {
        let count = recent_frames.min(self.frames.len());
        let start = self.frames.len().saturating_sub(count);
        for buffered in self.frames.iter_mut().skip(start) {
            buffered.regions.matches.push(region.clone());
        }
    }

    pub fn render_retroactive(
        &self,
        mode: TransformMode,
        intensity: f32,
    ) -> Result<Vec<TransformedFrame>> {
        self.frames
            .iter()
            .map(|buffered| apply_transform(&buffered.frame, &buffered.regions, mode, intensity))
            .collect()
    }

    pub fn estimated_memory_bytes(&self) -> Result<u64> {
        let Some(first) = self.frames.front() else {
            return Ok(0);
        };
        estimate_raw_rgba_memory_bytes(first.frame.width, first.frame.height, self.capacity_frames)
    }
}

pub fn estimate_raw_rgba_memory_bytes(width: u32, height: u32, frames: usize) -> Result<u64> {
    let frame_bytes = width
        .checked_mul(height)
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or_else(|| anyhow!("frame dimensions are too large: {}x{}", width, height))?
        as u64;
    frame_bytes
        .checked_mul(frames as u64)
        .ok_or_else(|| anyhow!("frame buffer estimate overflowed"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::{detection::Severity, frame::Rect};

    #[test]
    fn buffer_keeps_only_recent_frames() {
        let mut buffer = TimeMachineBuffer::new(1, 2);
        buffer.push(solid_frame(1, 4, 4), DetectedRegions::default());
        buffer.push(solid_frame(2, 4, 4), DetectedRegions::default());
        buffer.push(solid_frame(3, 4, 4), DetectedRegions::default());

        assert_eq!(buffer.capacity_frames(), 2);
        assert_eq!(buffer.len(), 2);
        assert_eq!(buffer.frames.front().unwrap().frame.pixels[0], 2);
    }

    #[test]
    fn estimates_raw_rgba_memory() {
        let bytes = estimate_raw_rgba_memory_bytes(1920, 1080, 30 * 30).unwrap();
        assert_eq!(bytes, 1920 * 1080 * 4 * 900);
    }

    #[test]
    fn manual_region_retroactively_transforms_buffered_frames() {
        let mut buffer = TimeMachineBuffer::new(30, 1);
        let original = gradient_frame(32, 24);
        buffer.push(original.clone(), DetectedRegions::default());
        buffer.add_manual_region_to_recent(manual_match(), 1);

        let rendered = buffer
            .render_retroactive(TransformMode::Pixelate, 1.0)
            .unwrap();

        assert_eq!(rendered.len(), 1);
        assert_ne!(rendered[0].pixels, original.pixels);
    }

    #[test]
    fn empty_buffer_reports_zero_memory() {
        let buffer = TimeMachineBuffer::new(30, 30);
        assert_eq!(buffer.estimated_memory_bytes().unwrap(), 0);
    }

    fn manual_match() -> SensitiveMatch {
        SensitiveMatch {
            bounds: Rect {
                x: 4,
                y: 4,
                width: 16,
                height: 12,
            },
            pattern_name: "manual-time-machine-region".to_string(),
            severity: Severity::High,
            snippet: "manual".to_string(),
        }
    }

    fn solid_frame(value: u8, width: u32, height: u32) -> RawFrame {
        RawFrame {
            pixels: vec![value; (width * height * 4) as usize],
            width,
            height,
            timestamp: chrono::Utc::now(),
        }
    }

    fn gradient_frame(width: u32, height: u32) -> RawFrame {
        let mut pixels = Vec::with_capacity((width * height * 4) as usize);
        for y in 0..height {
            for x in 0..width {
                pixels.push(((x * 7) % 255) as u8);
                pixels.push(((y * 11) % 255) as u8);
                pixels.push((((x + y) * 5) % 255) as u8);
                pixels.push(255);
            }
        }
        RawFrame {
            pixels,
            width,
            height,
            timestamp: chrono::Utc::now(),
        }
    }
}
