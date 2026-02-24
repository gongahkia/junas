use anyhow::Result;
use privacy_common::frame::{RawFrame, WindowInfo};

pub trait CaptureSource: Send {
    fn start(&mut self) -> Result<()>;
    fn stop(&mut self) -> Result<()>;
    fn next_frame(&mut self) -> Result<Option<RawFrame>>;
    fn list_windows(&self) -> Result<Vec<WindowInfo>>;
}

#[cfg(target_os = "macos")]
pub mod macos;

#[cfg(target_os = "linux")]
pub mod linux;
#[cfg(target_os = "linux")]
pub use linux::x11::X11CaptureSource;

pub mod fps;
pub mod pty;
pub mod region;
pub mod window_picker;
