//! ML-based neural style transfer via ONNX Runtime (ort crate).
//! Uses AnimeGAN v2 to stylize sensitive regions into anime/cartoon aesthetic.
//! Session is cached process-wide (OnceLock) — loaded once on first call.

use anyhow::{Context, Result};
use ndarray::Array4;
use ort::{inputs, session::Session, value::TensorRef};
use std::{
    path::PathBuf,
    sync::Mutex,
};

/// Build an ONNX session with the preferred execution provider.
/// Falls back to CPU if the requested EP fails to initialise.
fn build_session_with_ep(accel: &str, path: &std::path::Path) -> Result<Session> {
    let effective = if accel == "auto" {
        #[cfg(target_os = "macos")] { "coreml" }
        #[cfg(not(target_os = "macos"))] { "cpu" }
    } else {
        accel
    };
    // ort v2 EP registration — falls back to CPU when EP libs absent
    let builder = Session::builder().context("building ONNX session")?;
    let session = match effective {
        "coreml" => {
            // CoreML EP: macOS / iOS hardware acceleration
            builder
                .with_execution_providers([
                    ort::execution_providers::CoreMLExecutionProvider::default().build(),
                ])
                .unwrap_or_else(|e| {
                    log::warn!("CoreML EP unavailable ({e}), using CPU");
                    Session::builder().expect("session builder")
                })
                .commit_from_file(path)
                .context("loading ONNX model (CoreML)")?
        }
        "cuda" => {
            builder
                .with_execution_providers([
                    ort::execution_providers::CUDAExecutionProvider::default().build(),
                ])
                .unwrap_or_else(|e| {
                    log::warn!("CUDA EP unavailable ({e}), using CPU");
                    Session::builder().expect("session builder")
                })
                .commit_from_file(path)
                .context("loading ONNX model (CUDA)")?
        }
        _ => builder.commit_from_file(path).context("loading ONNX model (CPU)")?,
    };
    Ok(session)
}

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

// Safety: ort::Session is Send + Sync in v2; we only access via Mutex.
unsafe impl Send for NeuralStyleTransfer {}

impl NeuralStyleTransfer {
    /// Load the ONNX model from model_path(). Auto-downloads if absent.
    pub fn load() -> Result<Self> {
        let path = model_path();
        // attempt auto-download; non-fatal if network unavailable
        if let Err(e) = super::model_download::ensure_model(&path) {
            log::warn!("model auto-download failed: {e}");
        }
        if !path.exists() {
            anyhow::bail!("AnimeGAN v2 model not found at {}; download first", path.display());
        }
        let accel_guard = ACCELERATOR.lock().unwrap();
        let accel = accel_guard.as_deref().unwrap_or("auto");
        let session = build_session_with_ep(accel, &path)?;
        let input_name = session.inputs().first()
            .map(|i| i.name().to_string())
            .unwrap_or_else(|| "input".into());
        Ok(Self { session, input_name })
    }

    /// Run inference on an RGBA pixel region; returns stylized RGBA pixels.
    pub fn run(&mut self, pixels: &[u8], width: u32, height: u32) -> Result<Vec<u8>> {
        let h = height as usize;
        let w = width as usize;
        // normalize to [-1, 1] RGB float (drop alpha), NCHW layout
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
        let outputs = self.session.run(inp).context("ONNX inference failed")?;
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

/// Accelerator preference: "auto" | "cuda" | "coreml" | "cpu".
static ACCELERATOR: Mutex<Option<String>> = Mutex::new(None);

/// Call once at startup (before any inference) to set the preferred EP.
pub fn configure_accelerator(accel: impl Into<String>) {
    if let Ok(mut g) = ACCELERATOR.lock() { *g = Some(accel.into()); }
}

// process-level session cache — Mutex<Option<...>> allows retry after model download
static SESSION: Mutex<Option<NeuralStyleTransfer>> = Mutex::new(None);

/// Apply neural style transfer to an RGBA pixel buffer in-place.
/// `intensity` blends between original (0.0) and fully stylized (1.0).
/// Returns Err if model is unavailable (caller should fallback to cartoon).
pub fn apply_neural(pixels: &mut Vec<u8>, width: u32, height: u32, intensity: f32) -> Result<()> {
    let mut guard = SESSION.lock().unwrap();
    // lazy-load: attempt to load model if not yet loaded
    if guard.is_none() {
        *guard = NeuralStyleTransfer::load().ok();
    }
    let sess = guard.as_mut().ok_or_else(|| anyhow::anyhow!("model not available"))?;
    let stylized = sess.run(pixels, width, height)?;
    let alpha = intensity.clamp(0.0, 1.0);
    let beta = 1.0 - alpha;
    for (orig, styled) in pixels.iter_mut().zip(stylized.iter()) {
        *orig = ((*orig as f32) * beta + (*styled as f32) * alpha) as u8;
    }
    Ok(())
}
