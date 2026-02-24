use anyhow::Result;
use privacy_common::{detection::DetectedRegions, frame::{RawFrame, TransformedFrame}};

pub trait Transformer: Send {
    fn transform(&self, frame: &RawFrame, regions: &DetectedRegions, intensity: f32) -> Result<TransformedFrame>;
}

pub mod ascii;
pub mod blur;
pub mod cartoon;
pub mod compositor;
pub mod intensity;
pub mod neural;
pub mod pixelate;
pub mod registry;
