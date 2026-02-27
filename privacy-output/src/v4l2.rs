#![cfg(target_os = "linux")]
//! Virtual camera output via v4l2loopback device.
//! Converts RGBA frames to YUYV and writes to /dev/video<N>.

use anyhow::{anyhow, Result};
use privacy_common::frame::TransformedFrame;
use std::path::PathBuf;
use v4l::{format::fourcc::FourCC, prelude::*, Format};

use crate::OutputSink;

pub struct V4l2Sink {
    device_path: PathBuf,
    device: Option<Device>,
    width: u32,
    height: u32,
}

impl V4l2Sink {
    /// Open a v4l2loopback device at `device_path` (e.g., "/dev/video10").
    pub fn new(device_path: impl Into<PathBuf>) -> Self {
        Self {
            device_path: device_path.into(),
            device: None,
            width: 0,
            height: 0,
        }
    }

    fn open_device(&mut self, width: u32, height: u32) -> Result<()> {
        let dev = Device::with_path(&self.device_path)
            .map_err(|e| anyhow!("open {}: {}", self.device_path.display(), e))?;

        // set YUYV format at the desired resolution
        let fmt = Format::new(width, height, FourCC::new(b"YUYV"));
        dev.set_format(&fmt)
            .map_err(|e| anyhow!("set_format: {}", e))?;

        self.device = Some(dev);
        self.width = width;
        self.height = height;
        Ok(())
    }
}

impl OutputSink for V4l2Sink {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        if self.device.is_none() || frame.width != self.width || frame.height != self.height {
            self.open_device(frame.width, frame.height)?;
        }
        let yuyv = rgba_to_yuyv(&frame.pixels, frame.width, frame.height);
        use std::io::Write;
        // v4l2 loopback device accepts raw write() after VIDIOC_S_FMT
        let dev = self.device.as_ref().unwrap();
        // access raw fd for write
        use std::os::unix::io::AsRawFd;
        let fd = dev.as_raw_fd();
        let written = unsafe { libc::write(fd, yuyv.as_ptr() as *const libc::c_void, yuyv.len()) };
        if written < 0 {
            return Err(anyhow!("v4l2 write failed: errno {}", unsafe {
                *libc::__errno_location()
            }));
        }
        Ok(())
    }

    fn close(&mut self) -> Result<()> {
        self.device = None;
        Ok(())
    }
}

/// Convert RGBA pixels to YUYV packed format.
/// YUYV = Y0 U0 Y1 V0 for each pair of pixels.
fn rgba_to_yuyv(rgba: &[u8], width: u32, height: u32) -> Vec<u8> {
    let n = (width * height) as usize;
    let mut yuyv = Vec::with_capacity(n * 2); // 2 bytes per pixel in YUYV
    let mut i = 0;
    while i + 1 < n {
        let r0 = rgba[i * 4] as f32;
        let g0 = rgba[i * 4 + 1] as f32;
        let b0 = rgba[i * 4 + 2] as f32;
        let r1 = rgba[(i + 1) * 4] as f32;
        let g1 = rgba[(i + 1) * 4 + 1] as f32;
        let b1 = rgba[(i + 1) * 4 + 2] as f32;

        let y0 = (0.299 * r0 + 0.587 * g0 + 0.114 * b0)
            .round()
            .clamp(0.0, 255.0) as u8;
        let y1 = (0.299 * r1 + 0.587 * g1 + 0.114 * b1)
            .round()
            .clamp(0.0, 255.0) as u8;
        // U and V averaged over the two pixels
        let u = (-0.169 * r0 - 0.331 * g0 + 0.5 * b0 + 128.0)
            .round()
            .clamp(0.0, 255.0) as u8;
        let v = (0.5 * r0 - 0.419 * g0 - 0.081 * b0 + 128.0)
            .round()
            .clamp(0.0, 255.0) as u8;

        yuyv.extend_from_slice(&[y0, u, y1, v]);
        i += 2;
    }
    // handle odd width
    if n % 2 == 1 {
        let r = rgba[(n - 1) * 4] as f32;
        let g = rgba[(n - 1) * 4 + 1] as f32;
        let b = rgba[(n - 1) * 4 + 2] as f32;
        let y = (0.299 * r + 0.587 * g + 0.114 * b)
            .round()
            .clamp(0.0, 255.0) as u8;
        let u = (-0.169 * r - 0.331 * g + 0.5 * b + 128.0)
            .round()
            .clamp(0.0, 255.0) as u8;
        let v = (0.5 * r - 0.419 * g - 0.081 * b + 128.0)
            .round()
            .clamp(0.0, 255.0) as u8;
        yuyv.extend_from_slice(&[y, u, y, v]);
    }
    yuyv
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn yuyv_output_length() {
        let rgba = vec![255u8, 0, 0, 255, 0, 255, 0, 255]; // 2 pixels
        let out = rgba_to_yuyv(&rgba, 2, 1);
        assert_eq!(out.len(), 4); // 2 pixels → 4 bytes YUYV
    }
}
