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

/// Which output sink to use.
#[derive(Debug, Clone)]
pub enum SinkKind {
    /// v4l2loopback device (Linux only)
    V4l2(String),
    /// CoreMediaIO virtual camera (macOS only)
    CoreMedia,
    /// HTTP MJPEG stream (all platforms)
    HttpMjpeg(u16),
}

/// Create the appropriate `OutputSink` boxed trait object from a `SinkKind`.
pub fn create_sink(kind: SinkKind) -> Result<Box<dyn OutputSink>> {
    match kind {
        #[cfg(target_os = "linux")]
        SinkKind::V4l2(path) => Ok(Box::new(v4l2::V4l2Sink::new(path))),

        #[cfg(target_os = "macos")]
        SinkKind::CoreMedia => Ok(Box::new(coremedia::CoreMediaSink::new())),

        SinkKind::HttpMjpeg(port) => Ok(Box::new(mjpeg::MjpegSink::new(port)?)),

        // Fall through for unsupported platform/kind combos
        #[allow(unreachable_patterns)]
        _ => {
            // fall back to HTTP MJPEG
            Ok(Box::new(mjpeg::MjpegSink::new(mjpeg::DEFAULT_PORT)?))
        }
    }
}
