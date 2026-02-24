//! Platform-agnostic window enumeration.
//! Returns visible windows with id, title, and bounds for TUI selection.

use anyhow::Result;
use privacy_common::frame::WindowInfo;

/// Enumerate all currently visible windows on the current platform.
pub fn list_windows() -> Result<Vec<WindowInfo>> {
    #[cfg(target_os = "macos")]
    {
        use screencapturekit::shareable_content::SCShareableContent;
        use privacy_common::frame::Rect;
        let content = SCShareableContent::with_options()
            .on_screen_windows_only()
            .get()
            .map_err(|e| anyhow::anyhow!("{:?}", e))?;
        Ok(content.windows().into_iter().map(|w| {
            let f = w.get_frame();
            WindowInfo {
                id: w.window_id() as u64,
                title: w.title(),
                bounds: Rect {
                    x: f.origin.x as u32,
                    y: f.origin.y as u32,
                    width: f.size.width as u32,
                    height: f.size.height as u32,
                },
            }
        }).collect())
    }

    #[cfg(target_os = "linux")]
    {
        use super::linux::x11::X11CaptureSource;
        use super::linux::x11::X11CaptureTarget;
        use crate::capture::CaptureSource;
        let src = X11CaptureSource::new(X11CaptureTarget::Root, 0);
        src.list_windows()
    }

    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
    {
        Ok(vec![])
    }
}
