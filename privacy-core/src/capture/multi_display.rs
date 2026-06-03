use anyhow::{anyhow, bail, Context, Result};
use privacy_common::frame::{RawFrame, WindowInfo};

use super::CaptureSource;

/// One selected display and its platform capture source.
pub struct DisplayCapture {
    pub label: String,
    source: Box<dyn CaptureSource + Send>,
    last_frame: Option<RawFrame>,
}

impl DisplayCapture {
    pub fn new(label: impl Into<String>, source: Box<dyn CaptureSource + Send>) -> Self {
        Self {
            label: label.into(),
            source,
            last_frame: None,
        }
    }
}

/// Captures multiple displays and emits a single side-by-side RGBA frame.
pub struct MultiDisplayCaptureSource {
    displays: Vec<DisplayCapture>,
}

impl MultiDisplayCaptureSource {
    pub fn new(displays: Vec<DisplayCapture>) -> Self {
        Self { displays }
    }

    pub fn display_count(&self) -> usize {
        self.displays.len()
    }
}

impl CaptureSource for MultiDisplayCaptureSource {
    fn start(&mut self) -> Result<()> {
        if self.displays.is_empty() {
            bail!("multi-display capture requires at least one display");
        }

        for idx in 0..self.displays.len() {
            if let Err(err) = self.displays[idx].source.start() {
                for display in self.displays.iter_mut().take(idx) {
                    let _ = display.source.stop();
                }
                bail!("starting {}: {err}", self.displays[idx].label);
            }
        }
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        let mut first_error = None;
        for display in &mut self.displays {
            if let Err(err) = display.source.stop() {
                first_error.get_or_insert_with(|| anyhow!("stopping {}: {err}", display.label));
            }
            display.last_frame = None;
        }
        if let Some(err) = first_error {
            return Err(err);
        }
        Ok(())
    }

    fn next_frame(&mut self) -> Result<Option<RawFrame>> {
        let mut updated = false;
        for display in &mut self.displays {
            match display.source.next_frame() {
                Ok(Some(frame)) => {
                    display.last_frame = Some(frame);
                    updated = true;
                }
                Ok(None) => {}
                Err(err) => bail!("reading {}: {err}", display.label),
            }
        }

        if !updated {
            return Ok(None);
        }

        let frames: Vec<_> = self
            .displays
            .iter()
            .map(|display| display.last_frame.as_ref())
            .collect();
        let Some(frames) = frames.into_iter().collect::<Option<Vec<_>>>() else {
            return Ok(None);
        };
        Ok(Some(compose_horizontal(&frames)?))
    }

    fn list_windows(&self) -> Result<Vec<WindowInfo>> {
        Ok(Vec::new())
    }
}

pub fn compose_horizontal(frames: &[&RawFrame]) -> Result<RawFrame> {
    if frames.is_empty() {
        bail!("cannot compose zero display frames");
    }

    let width = frames.iter().try_fold(0u32, |sum, frame| {
        sum.checked_add(frame.width)
            .ok_or_else(|| anyhow!("multi-display width overflowed"))
    })?;
    let height = frames
        .iter()
        .map(|frame| frame.height)
        .max()
        .context("cannot compose zero display frames")?;
    let output_len = rgba_len(width, height)? as usize;
    let mut pixels = vec![0u8; output_len];
    for chunk in pixels.chunks_exact_mut(4) {
        chunk[3] = 255;
    }

    let mut x_offset = 0u32;
    for frame in frames {
        let expected = rgba_len(frame.width, frame.height)? as usize;
        if frame.pixels.len() != expected {
            bail!(
                "display frame has {} bytes for {}x{}, expected {}",
                frame.pixels.len(),
                frame.width,
                frame.height,
                expected
            );
        }
        copy_frame(&mut pixels, width, frame, x_offset)?;
        x_offset += frame.width;
    }

    Ok(RawFrame {
        pixels,
        width,
        height,
        timestamp: chrono::Utc::now(),
    })
}

pub fn estimate_raw_rgba_bytes_per_second(displays: &[(u32, u32)], fps: u32) -> Result<u64> {
    let cost = estimate_composited_canvas(displays)?;
    cost.composited_bytes
        .checked_mul(fps as u64)
        .ok_or_else(|| anyhow!("multi-display throughput estimate overflowed"))
}

pub fn estimate_composited_canvas(displays: &[(u32, u32)]) -> Result<CompositedCanvasEstimate> {
    if displays.is_empty() {
        bail!("at least one display is required");
    }
    let width = displays.iter().try_fold(0u32, |sum, (w, _)| {
        sum.checked_add(*w)
            .ok_or_else(|| anyhow!("multi-display width overflowed"))
    })?;
    let height = displays
        .iter()
        .map(|(_, h)| *h)
        .max()
        .context("at least one display is required")?;
    let source_bytes = displays.iter().try_fold(0u64, |sum, (w, h)| {
        sum.checked_add(rgba_len(*w, *h)?)
            .ok_or_else(|| anyhow!("source byte estimate overflowed"))
    })?;
    let composited_bytes = rgba_len(width, height)?;
    Ok(CompositedCanvasEstimate {
        width,
        height,
        source_bytes,
        composited_bytes,
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompositedCanvasEstimate {
    pub width: u32,
    pub height: u32,
    pub source_bytes: u64,
    pub composited_bytes: u64,
}

fn copy_frame(output: &mut [u8], output_width: u32, frame: &RawFrame, x_offset: u32) -> Result<()> {
    let output_stride = output_width as usize * 4;
    let frame_stride = frame.width as usize * 4;
    let x_offset_bytes = x_offset as usize * 4;

    for row in 0..frame.height as usize {
        let src_start = row * frame_stride;
        let dst_start = row * output_stride + x_offset_bytes;
        let src_end = src_start + frame_stride;
        let dst_end = dst_start + frame_stride;
        output
            .get_mut(dst_start..dst_end)
            .context("multi-display copy exceeded output frame bounds")?
            .copy_from_slice(&frame.pixels[src_start..src_end]);
    }
    Ok(())
}

fn rgba_len(width: u32, height: u32) -> Result<u64> {
    width
        .checked_mul(height)
        .and_then(|pixels| pixels.checked_mul(4))
        .map(u64::from)
        .ok_or_else(|| anyhow!("RGBA dimensions are too large: {width}x{height}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn composes_frames_side_by_side() {
        let left = solid_frame(2, 1, [255, 0, 0, 255]);
        let right = solid_frame(1, 2, [0, 0, 255, 255]);

        let composed = compose_horizontal(&[&left, &right]).unwrap();

        assert_eq!(composed.width, 3);
        assert_eq!(composed.height, 2);
        assert_eq!(&composed.pixels[0..4], &[255, 0, 0, 255]);
        assert_eq!(&composed.pixels[4..8], &[255, 0, 0, 255]);
        assert_eq!(&composed.pixels[8..12], &[0, 0, 255, 255]);
        assert_eq!(&composed.pixels[12..16], &[0, 0, 0, 255]);
        assert_eq!(&composed.pixels[20..24], &[0, 0, 255, 255]);
    }

    #[test]
    fn estimates_composited_canvas_cost() {
        let estimate = estimate_composited_canvas(&[(1920, 1080), (2560, 1440)]).unwrap();

        assert_eq!(estimate.width, 4480);
        assert_eq!(estimate.height, 1440);
        assert_eq!(
            estimate.source_bytes,
            (1920 * 1080 * 4 + 2560 * 1440 * 4) as u64
        );
        assert_eq!(estimate.composited_bytes, 4480 * 1440 * 4);
    }

    #[test]
    fn estimates_raw_throughput_at_fps() {
        let bytes = estimate_raw_rgba_bytes_per_second(&[(1920, 1080), (1920, 1080)], 30).unwrap();

        assert_eq!(bytes, 3840 * 1080 * 4 * 30);
    }

    #[test]
    fn rejects_empty_display_estimate() {
        assert!(estimate_composited_canvas(&[]).is_err());
        assert!(compose_horizontal(&[]).is_err());
    }

    fn solid_frame(width: u32, height: u32, rgba: [u8; 4]) -> RawFrame {
        let mut pixels = Vec::with_capacity((width * height * 4) as usize);
        for _ in 0..width * height {
            pixels.extend_from_slice(&rgba);
        }
        RawFrame {
            pixels,
            width,
            height,
            timestamp: chrono::Utc::now(),
        }
    }
}
