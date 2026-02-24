use anyhow::Result;
use privacy_common::frame::TransformedFrame;

pub trait OutputSink: Send {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()>;
    fn close(&mut self) -> Result<()>;
}

#[cfg(target_os = "linux")]
pub mod v4l2;

#[cfg(target_os = "macos")]
pub mod coremedia;

pub mod mjpeg;
