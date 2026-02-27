//! OCR-based text extraction using Tesseract (via leptess).
//! Accepts RGBA frame, returns TextRegions with text, bounding box, and confidence.

use anyhow::{anyhow, Result};
use image::RgbaImage;
use leptess::{capi::TessPageIteratorLevel_RIL_WORD, LepTess, Variable};
use privacy_common::{
    detection::TextRegion,
    frame::{RawFrame, Rect},
};
use std::io::Cursor;

/// Minimum confidence (0–100) below which word results are discarded.
pub const MIN_CONFIDENCE: f32 = 60.0;

/// OCR engine wrapping a LepTess instance.
pub struct OcrEngine {
    lt: LepTess,
    min_confidence: f32,
}

impl OcrEngine {
    /// Create OCR engine. `data_path` is the tessdata directory; None uses system default.
    pub fn new(data_path: Option<&str>) -> Result<Self> {
        Self::new_with_confidence(data_path, MIN_CONFIDENCE)
    }

    /// Create OCR engine with a custom minimum confidence threshold (0–100).
    pub fn new_with_confidence(data_path: Option<&str>, min_conf: f32) -> Result<Self> {
        let mut lt =
            LepTess::new(data_path, "eng").map_err(|e| anyhow!("Tesseract init: {}", e))?;
        // PSM 6 = single block of text
        lt.set_variable(Variable::TesseditPagesegMode, "6")
            .map_err(|_| anyhow!("failed to set PSM 6"))?;
        Ok(Self {
            lt,
            min_confidence: min_conf,
        })
    }

    /// Run OCR on a raw RGBA frame, return all detected text regions above min confidence.
    pub fn extract(&mut self, frame: &RawFrame) -> Result<Vec<TextRegion>> {
        let rgba_img = RgbaImage::from_raw(frame.width, frame.height, frame.pixels.clone())
            .ok_or_else(|| anyhow!("invalid frame {}x{}", frame.width, frame.height))?;
        let mut buf: Vec<u8> = Vec::new();
        rgba_img
            .write_to(&mut Cursor::new(&mut buf), image::ImageFormat::Tiff)
            .map_err(|e| anyhow!("frame→TIFF: {}", e))?;

        self.lt
            .set_image_from_mem(&buf)
            .map_err(|e| anyhow!("set_image_from_mem: {}", e))?;
        self.lt.recognize();

        let boxes = match self
            .lt
            .get_component_boxes(TessPageIteratorLevel_RIL_WORD, true)
        {
            Some(b) => b,
            None => return Ok(vec![]),
        };

        let mut regions = Vec::with_capacity(boxes.get_n());
        for b in &boxes {
            self.lt.set_rectangle_from_box(&b);
            let text = match self.lt.get_utf8_text() {
                Ok(t) => t.trim().to_owned(),
                Err(_) => continue,
            };
            if text.is_empty() {
                continue;
            }
            let conf = self.lt.mean_text_conf() as f32;
            if conf < self.min_confidence {
                continue;
            }
            let geo = b.get_geometry();
            regions.push(TextRegion {
                text,
                bounds: Rect {
                    x: geo.x.max(0) as u32,
                    y: geo.y.max(0) as u32,
                    width: geo.w.max(0) as u32,
                    height: geo.h.max(0) as u32,
                },
                confidence: conf,
            });
        }
        Ok(regions)
    }
}
