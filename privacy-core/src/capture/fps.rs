//! Frame rate controller: regulate capture to target FPS, track actual FPS and dropped frames.

use std::time::{Duration, Instant};

/// Minimum/maximum allowed FPS.
pub const FPS_MIN: u32 = 15;
pub const FPS_MAX: u32 = 60;
pub const FPS_DEFAULT: u32 = 30;

pub struct FrameRateController {
    pub target_fps: u32,
    frame_interval: Duration,
    last_frame_time: Option<Instant>,
    /// circular buffer of delivery times for actual-FPS calculation (last 60 frames)
    delivery_times: Vec<Instant>,
    delivery_idx: usize,
    pub dropped_frames: u64,
}

impl FrameRateController {
    pub fn new(fps: u32) -> Self {
        let fps = fps.clamp(FPS_MIN, FPS_MAX);
        Self {
            target_fps: fps,
            frame_interval: Duration::from_nanos(1_000_000_000 / fps as u64),
            last_frame_time: None,
            delivery_times: Vec::with_capacity(60),
            delivery_idx: 0,
            dropped_frames: 0,
        }
    }

    /// Should be called before attempting to capture a frame.
    /// Sleeps if necessary to maintain target FPS.
    /// Returns true if a new frame should be captured, false if we should skip.
    pub fn should_capture(&mut self) -> bool {
        let now = Instant::now();
        match self.last_frame_time {
            None => {
                self.last_frame_time = Some(now);
                true
            }
            Some(last) => {
                let elapsed = now.duration_since(last);
                if elapsed >= self.frame_interval {
                    self.last_frame_time = Some(now);
                    true
                } else {
                    // sleep for the remainder of the interval
                    std::thread::sleep(self.frame_interval - elapsed);
                    self.last_frame_time = Some(Instant::now());
                    true
                }
            }
        }
    }

    /// Record a successfully delivered frame.
    pub fn record_delivery(&mut self) {
        let now = Instant::now();
        if self.delivery_times.len() < 60 {
            self.delivery_times.push(now);
        } else {
            self.delivery_times[self.delivery_idx % 60] = now;
        }
        self.delivery_idx += 1;
    }

    /// Record a dropped frame (pipeline backpressure).
    pub fn record_drop(&mut self) {
        self.dropped_frames += 1;
    }

    /// Calculate actual FPS from the last 60 delivered frame timestamps.
    /// Returns 0.0 if fewer than 2 frames have been delivered.
    pub fn actual_fps(&self) -> f32 {
        let n = self.delivery_times.len();
        if n < 2 {
            return 0.0;
        }
        // find oldest and newest in the circular buffer
        let oldest = self.delivery_times.iter().copied().min().unwrap();
        let newest = self.delivery_times.iter().copied().max().unwrap();
        let span = newest.duration_since(oldest).as_secs_f32();
        if span <= 0.0 {
            0.0
        } else {
            (n as f32 - 1.0) / span
        }
    }

    /// Reset FPS stats (e.g., after pause/resume).
    pub fn reset_stats(&mut self) {
        self.delivery_times.clear();
        self.delivery_idx = 0;
        self.dropped_frames = 0;
        self.last_frame_time = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clamps_fps() {
        let c = FrameRateController::new(5);
        assert_eq!(c.target_fps, FPS_MIN);
        let c = FrameRateController::new(200);
        assert_eq!(c.target_fps, FPS_MAX);
    }

    #[test]
    fn actual_fps_zero_on_start() {
        let c = FrameRateController::new(30);
        assert_eq!(c.actual_fps(), 0.0);
    }
}
