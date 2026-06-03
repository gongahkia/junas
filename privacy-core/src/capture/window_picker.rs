//! Platform-agnostic window and display enumeration.
//! Returns visible windows with id, title, bounds, and display index for TUI selection.

use anyhow::Result;
use privacy_common::frame::{Rect, WindowInfo};

/// A physical monitor / display.
#[derive(Debug, Clone)]
pub struct DisplayInfo {
    pub index: usize,
    pub id: u32,
    pub name: String,
    pub bounds: Rect,
    pub is_primary: bool,
}

/// Enumerate all currently visible windows on the current platform.
pub fn list_windows() -> Result<Vec<WindowInfo>> {
    #[cfg(target_os = "macos")]
    {
        use privacy_common::frame::Rect;
        use screencapturekit::shareable_content::SCShareableContent;
        let content = SCShareableContent::with_options()
            .on_screen_windows_only()
            .get()
            .map_err(|e| anyhow::anyhow!("{:?}", e))?;
        Ok(content
            .windows()
            .into_iter()
            .map(|w| {
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
            })
            .collect())
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

/// Enumerate physical displays with their index so the TUI can show e.g. "[1] Built-in Retina".
pub fn list_displays() -> Result<Vec<DisplayInfo>> {
    #[cfg(target_os = "macos")]
    {
        use core_graphics::display::CGDisplay;
        use screencapturekit::shareable_content::SCShareableContent;
        let content = SCShareableContent::get()
            .map_err(|e| anyhow::anyhow!("SCShareableContent::get: {:?}", e))?;
        let primary = CGDisplay::main().id;
        let displays = content
            .displays()
            .into_iter()
            .enumerate()
            .map(|(idx, display)| {
                let id = display.display_id();
                let b = display.frame();
                DisplayInfo {
                    index: idx,
                    id,
                    name: format!("Display {} (id={})", idx + 1, id),
                    bounds: Rect {
                        x: b.origin.x.max(0.0) as u32,
                        y: b.origin.y.max(0.0) as u32,
                        width: b.size.width as u32,
                        height: b.size.height as u32,
                    },
                    is_primary: id == primary,
                }
            })
            .collect();
        Ok(displays)
    }

    #[cfg(target_os = "linux")]
    {
        // X11: use XineramaQueryScreens or RandR for display info
        Ok(vec![DisplayInfo {
            index: 0,
            id: 0,
            name: "Display 0 (X11)".into(),
            bounds: Rect {
                x: 0,
                y: 0,
                width: 1920,
                height: 1080,
            },
            is_primary: true,
        }])
    }

    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
    {
        Ok(vec![])
    }
}
