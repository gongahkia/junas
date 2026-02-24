use anyhow::Result;
use privacy_common::{detection::DetectedRegions, frame::RawFrame};

pub trait SensitivityDetector: Send {
    fn detect(&mut self, frame: &RawFrame) -> Result<DetectedRegions>;
}

pub mod default_patterns;
pub mod expand;
pub mod pii_patterns;
pub mod incremental;
pub mod ocr;
pub mod patterns;
pub mod scanner;
