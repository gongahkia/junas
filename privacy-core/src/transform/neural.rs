//! ML-based neural style transfer via ONNX Runtime (ort crate).
//! Uses AnimeGAN v2 to stylize sensitive regions into anime/cartoon aesthetic.

use anyhow::{Context, Result};
use ndarray::Array4;
use ort::{inputs, session::Session, value::TensorRef};
use std::path::PathBuf;

/// Returns the expected model cache path.
pub fn model_path() -> PathBuf {
    let cache = std::env::var("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".cache")
        });
    cache.join("ascii-privacy").join("models").join("animegan_v2.onnx")
}

/// Loaded AnimeGAN v2 session.
pub struct NeuralStyleTransfer {
    session: Session,
    input_name: String,
}

impl NeuralStyleTransfer {
    /// Load the ONNX model. Returns error if model file is absent.
    pub fn load() -> Result<Self> {
        let path = model_path();
        if !path.exists() {
            anyhow::bail!("AnimeGAN v2 model not found at {}; run download first", path.display());
        }
        let session = Session::builder()
            .context("building ONNX session")?
            .commit_from_file(&path)
            .context("loading ONNX model")?;
        let input_name = session.inputs().first()
            .map(|i| i.name().to_string())
            .unwrap_or_else(|| "input".into());
        Ok(Self { session, input_name })
    }

    /// Run inference on an RGBA pixel region.
    /// Returns stylized RGBA pixels of the same dimensions.
    pub fn run(&mut self, pixels: &[u8], width: u32, height: u32) -> Result<Vec<u8>> {
        let h = height as usize;
        let w = width as usize;
        // normalize to [-1, 1] RGB float (drop alpha), layout NCHW
        let mut arr = Array4::<f32>::zeros((1, 3, h, w));
        for y in 0..h {
            for x in 0..w {
                let base = (y * w + x) * 4;
                arr[[0, 0, y, x]] = pixels[base] as f32 / 127.5 - 1.0; // R
                arr[[0, 1, y, x]] = pixels[base + 1] as f32 / 127.5 - 1.0; // G
                arr[[0, 2, y, x]] = pixels[base + 2] as f32 / 127.5 - 1.0; // B
            }
        }
        let tensor = TensorRef::from_array_view(arr.view())
            .context("creating input tensor")?;
        let inp = inputs![self.input_name.as_str() => tensor];
        let outputs = self.session.run(inp)
            .context("ONNX inference failed")?;
        let out_arr = outputs[0]
            .try_extract_array::<f32>()
            .context("extracting output tensor")?;
        // convert NCHW output back to RGBA u8
        let mut result = vec![255u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                let base = (y * w + x) * 4;
                result[base] = (out_arr[[0, 0, y, x]].clamp(-1.0, 1.0) * 127.5 + 127.5) as u8;
                result[base + 1] = (out_arr[[0, 1, y, x]].clamp(-1.0, 1.0) * 127.5 + 127.5) as u8;
                result[base + 2] = (out_arr[[0, 2, y, x]].clamp(-1.0, 1.0) * 127.5 + 127.5) as u8;
                result[base + 3] = pixels[base + 3]; // preserve original alpha
            }
        }
        Ok(result)
    }
}

/// Apply neural style transfer to an RGBA pixel buffer in-place.
/// `intensity` blends between original (0.0) and stylized (1.0).
pub fn apply_neural(pixels: &mut Vec<u8>, width: u32, height: u32, intensity: f32) -> Result<()> {
    let mut session = NeuralStyleTransfer::load()?;
    let stylized = session.run(pixels, width, height)?;
    let alpha = intensity.clamp(0.0, 1.0);
    let beta = 1.0 - alpha;
    for (orig, styled) in pixels.iter_mut().zip(stylized.iter()) {
        *orig = ((*orig as f32) * beta + (*styled as f32) * alpha) as u8;
    }
    Ok(())
}
