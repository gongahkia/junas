use anyhow::Result;
use privacy_common::{detection::DetectedRegions, frame::RawFrame};

pub trait SensitivityDetector: Send {
    fn detect(&mut self, frame: &RawFrame) -> Result<DetectedRegions>;
}

pub mod default_patterns;
pub mod expand;
pub mod frame_diff;
pub use frame_diff::FrameDiff;
pub mod incremental;
pub mod line_expand;
pub mod ocr;
pub mod patterns;
pub mod pii_patterns;
pub mod scanner;
pub mod training;
pub mod user_patterns;
pub mod whitelist;
