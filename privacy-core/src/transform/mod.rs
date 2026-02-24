use anyhow::Result;
use privacy_common::{detection::DetectedRegions, frame::{RawFrame, TransformedFrame}};

pub trait Transformer: Send {
    fn transform(&self, frame: &RawFrame, regions: &DetectedRegions, intensity: f32) -> Result<TransformedFrame>;
}

pub mod blur;
pub mod pixelate;
pub mod cartoon;
pub mod ascii;
pub mod compositor;
