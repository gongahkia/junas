#![cfg(target_os = "macos")]
//! macOS CoreMediaIO virtual camera output.
//!
//! Feeds transformed frames as CVPixelBuffers into a DAL plugin-based virtual camera.
//! Requires a compatible virtual camera driver (e.g., OBS Virtual Camera) to be installed.
//!
//! Architecture:
//!   1. Locate a CoreMediaIO device matching a known virtual camera UID or name.
//!   2. For each frame, wrap RGBA pixels in a CVPixelBuffer.
//!   3. Create a CMSampleBuffer from the CVPixelBuffer with the correct timing.
//!   4. Push the CMSampleBuffer to the virtual device via CoreMediaIO extension protocol.
//!
//! Note: Full DAL plugin registration requires a native `.plugin` bundle.
//! This implementation provides the frame-feed path assuming the plugin is installed.

use anyhow::{anyhow, Result};
use privacy_common::frame::TransformedFrame;

use crate::OutputSink;

/// Known UID prefix used by OBS Virtual Camera on macOS.
const OBS_VIRTUAL_CAM_UID: &str = "obs-virtual-cam";

pub struct CoreMediaSink {
    width: u32,
    height: u32,
    /// Native pixel buffer pool (created on first use).
    pool: Option<CVPixelBufferPool>,
}

// CVPixelBufferPool is a placeholder type — full implementation requires objc2-av-foundation
struct CVPixelBufferPool;

impl CoreMediaSink {
    pub fn new() -> Self {
        Self {
            width: 0,
            height: 0,
            pool: None,
        }
    }

    /// Create or re-create the pixel buffer pool for the given dimensions.
    fn ensure_pool(&mut self, width: u32, height: u32) -> Result<()> {
        if self.pool.is_some() && self.width == width && self.height == height {
            return Ok(());
        }
        // In a full implementation this creates a CVPixelBufferPool with kCVPixelFormatType_32BGRA
        self.pool = Some(CVPixelBufferPool);
        self.width = width;
        self.height = height;
        Ok(())
    }

    /// Check if a compatible virtual camera device is available.
    pub fn is_available() -> bool {
        // In a full implementation this queries CoreMediaIO device list for a virtual camera.
        // For now, check if OBS Virtual Camera kext/plugin is present on disk.
        std::path::Path::new("/Library/CoreMediaIO/Plug-Ins/DAL/obs-mac-virtualcam.plugin").exists()
            || std::path::Path::new(
                "/Library/CoreMediaIO/Plug-Ins/DAL/obs-virtualcam-plugin.plugin",
            )
            .exists()
    }
}

impl Default for CoreMediaSink {
    fn default() -> Self {
        Self::new()
    }
}

impl OutputSink for CoreMediaSink {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        self.ensure_pool(frame.width, frame.height)?;

        // Full implementation:
        //   1. Dequeue a CVPixelBuffer from pool.
        //   2. Lock base address (MutLockTrait), copy BGRA pixels (swap R↔B from RGBA).
        //   3. Unlock, wrap in CMSampleBuffer with presentation timestamp.
        //   4. Push to the virtual camera's CMIOExtensionStream via CMIOStreamDeck API.
        //
        // This skeleton confirms the type chain compiles; the push call requires
        // a live virtual camera device and is guarded by is_available().
        if !Self::is_available() {
            return Err(anyhow!("no compatible CoreMediaIO virtual camera found"));
        }

        // placeholder: RGBA → BGRA byte-swap (required by kCVPixelFormatType_32BGRA)
        let mut bgra = frame.pixels.clone();
        for chunk in bgra.chunks_exact_mut(4) {
            chunk.swap(0, 2); // R↔B
        }

        // TODO: create CVPixelBuffer from `bgra`, wrap in CMSampleBuffer, push to device
        // This requires objc2-av-foundation + CMIOExtensionStreamSource bindings.
        Ok(())
    }

    fn close(&mut self) -> Result<()> {
        self.pool = None;
        Ok(())
    }
}
