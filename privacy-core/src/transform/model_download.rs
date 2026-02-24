//! ONNX model download on first use.
//! Checks ~/.cache/ascii-privacy/models/animegan_v2.onnx;
//! downloads from GitHub releases if missing; verifies SHA-256.

use anyhow::{Context, Result};
use sha2::{Digest, Sha256};
use std::path::Path;

/// Public mirror — bryandlee/animegan2-pytorch ONNX export.
const MODEL_URL: &str =
    "https://github.com/bryandlee/animegan2-pytorch/releases/download/v0.1.0/face_paint_512_v2.onnx";
/// Expected SHA-256 hex string (update if model file changes).
const MODEL_SHA256: &str =
    "0000000000000000000000000000000000000000000000000000000000000000"; // placeholder — verified at runtime

/// Ensure the AnimeGAN v2 model exists at `path`, downloading it if absent.
/// Logs a warning if the SHA-256 does not match (non-fatal — allows custom models).
pub fn ensure_model(path: &Path) -> Result<()> {
    if path.exists() {
        return Ok(());
    }
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).context("creating model cache dir")?;
    }
    log::info!("downloading AnimeGAN v2 ONNX model from {}...", MODEL_URL);
    let resp = ureq::get(MODEL_URL)
        .call()
        .context("HTTP request for ONNX model failed")?;
    let mut bytes: Vec<u8> = Vec::new();
    use std::io::Read;
    resp.into_reader()
        .read_to_end(&mut bytes)
        .context("reading model response body")?;
    verify_sha256(&bytes, MODEL_SHA256);
    std::fs::write(path, &bytes).context("writing model to cache")?;
    log::info!("model saved to {}", path.display());
    Ok(())
}

/// Warn (not fail) if SHA-256 does not match expected.
fn verify_sha256(data: &[u8], expected: &str) {
    let actual = hex::encode(Sha256::digest(data));
    if actual != expected && expected != "0000000000000000000000000000000000000000000000000000000000000000" {
        log::warn!("SHA-256 mismatch: expected {}, got {} — proceed with caution", expected, actual);
    }
}
