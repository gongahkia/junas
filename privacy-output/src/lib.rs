use anyhow::Result;
use privacy_common::frame::TransformedFrame;
use std::path::PathBuf;

pub trait OutputSink: Send {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()>;
    fn close(&mut self) -> Result<()>;
}

#[cfg(target_os = "linux")]
pub mod v4l2;

#[cfg(target_os = "macos")]
pub mod coremedia;

pub mod audio;
pub mod autodetect;
pub mod mjpeg;
pub mod obs_websocket;
pub mod recorder;
pub mod tray;
pub mod twitch;

/// Which output sink to use.
#[derive(Debug, Clone)]
pub enum SinkKind {
    /// v4l2loopback device (Linux only)
    V4l2(String),
    /// CoreMediaIO virtual camera (macOS only)
    CoreMedia,
    /// HTTP MJPEG stream (all platforms)
    HttpMjpeg(u16),
    /// OBS WebSocket v5 (planned): setup Browser Source pointing to MJPEG endpoint
    Obs(u16),
    /// Twitch RTMP output (planned): stream filtered output to rtmp://live.twitch.tv/app/<key>
    Twitch,
    /// Direct local MP4 recording through ffmpeg.
    Mp4 {
        path: PathBuf,
        fps: u32,
        overwrite: bool,
    },
}

/// Create the appropriate `OutputSink` boxed trait object from a `SinkKind`.
pub fn create_sink(kind: SinkKind) -> Result<Box<dyn OutputSink>> {
    match kind {
        #[cfg(target_os = "linux")]
        SinkKind::V4l2(path) => Ok(Box::new(v4l2::V4l2Sink::new(path))),

        #[cfg(target_os = "macos")]
        SinkKind::CoreMedia => Ok(Box::new(coremedia::CoreMediaSink::new())),

        SinkKind::HttpMjpeg(port) => Ok(Box::new(mjpeg::MjpegSink::new(port)?)),

        SinkKind::Obs(mjpeg_port) => {
            // attempt OBS Browser Source setup; fall back to MJPEG sink regardless
            if let Err(e) = obs_websocket::ObsClient::default_local().connect_and_setup(mjpeg_port)
            {
                log::warn!(
                    "OBS WebSocket setup failed ({e}), falling back to MJPEG on :{mjpeg_port}"
                );
            }
            Ok(Box::new(mjpeg::MjpegSink::new(mjpeg_port)?))
        }

        SinkKind::Twitch => {
            // planned: RTMP output via ffmpeg/gstreamer to rtmp://live.twitch.tv/app/<key>
            anyhow::bail!("Twitch RTMP output is not yet implemented; planned feature")
        }

        SinkKind::Mp4 {
            path,
            fps,
            overwrite,
        } => Ok(Box::new(recorder::Mp4Sink::new(path, fps, overwrite)?)),

        // Fall through for unsupported platform/kind combos
        #[allow(unreachable_patterns)]
        _ => {
            // fall back to HTTP MJPEG
            Ok(Box::new(mjpeg::MjpegSink::new(mjpeg::DEFAULT_PORT)?))
        }
    }
}
