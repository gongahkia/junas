//! Auto-detection of virtual camera availability.
//! Selects the best available output sink for the current platform.

use crate::{mjpeg::DEFAULT_PORT, SinkKind};

/// Probe available output sinks and return the best `SinkKind` in priority order:
/// 1. Platform-native virtual camera (v4l2loopback / CoreMediaIO)
/// 2. HTTP MJPEG fallback
///
/// Logs which sink was selected.
pub fn detect_best_sink(http_port: u16) -> SinkKind {
    #[cfg(target_os = "linux")]
    {
        if let Some(path) = find_v4l2_loopback() {
            log::info!("output: using v4l2loopback at {}", path);
            return SinkKind::V4l2(path);
        }
    }

    #[cfg(target_os = "macos")]
    {
        if crate::coremedia::CoreMediaSink::is_available() {
            log::info!("output: using CoreMediaIO virtual camera");
            return SinkKind::CoreMedia;
        }
    }

    log::info!("output: falling back to HTTP MJPEG on port {}", http_port);
    SinkKind::HttpMjpeg(http_port)
}

/// Shorthand with default HTTP port.
pub fn detect() -> SinkKind {
    detect_best_sink(DEFAULT_PORT)
}

/// On Linux, scan /dev/video* for v4l2loopback devices.
/// Returns the path of the first loopback device found, or None.
#[cfg(target_os = "linux")]
fn find_v4l2_loopback() -> Option<String> {
    use std::fs;
    // v4l2loopback devices are typically /dev/video10, /dev/video20, etc.
    // We probe by reading the device driver name via /sys/class/video4linux/videoN/name.
    let Ok(entries) = fs::read_dir("/sys/class/video4linux") else {
        return None;
    };
    for entry in entries.flatten() {
        let name_file = entry.path().join("name");
        if let Ok(name) = fs::read_to_string(&name_file) {
            if name.trim().contains("Dummy") || name.trim().contains("v4l2loopback") {
                let dev = format!("/dev/{}", entry.file_name().to_string_lossy());
                if std::path::Path::new(&dev).exists() {
                    return Some(dev);
                }
            }
        }
    }
    None
}
