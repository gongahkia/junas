//! Audio passthrough: capture system audio and pass through to virtual microphone.
//! Uses platform APIs (CoreAudio on macOS, PulseAudio/ALSA on Linux).
//! No sensitive audio content is captured or stored by default.

use anyhow::Result;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// Audio passthrough handle — stops when dropped.
pub struct AudioPassthrough {
    running: Arc<AtomicBool>,
    thread: Option<std::thread::JoinHandle<()>>,
}

impl AudioPassthrough {
    /// Start capturing system audio and routing to virtual output.
    /// `device` is the output sink name (None = default).
    pub fn start(device: Option<String>) -> Result<Self> {
        let running = Arc::new(AtomicBool::new(true));
        let r = Arc::clone(&running);
        let thread = std::thread::Builder::new()
            .name("aki-audio".into())
            .spawn(move || audio_loop(r, device))?;
        log::info!("audio passthrough started");
        Ok(Self {
            running,
            thread: Some(thread),
        })
    }

    pub fn stop(mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(t) = self.thread.take() {
            let _ = t.join();
        }
        log::info!("audio passthrough stopped");
    }
}

impl Drop for AudioPassthrough {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
    }
}

fn audio_loop(running: Arc<AtomicBool>, device: Option<String>) {
    log::info!(
        "audio passthrough: using device={}",
        device.as_deref().unwrap_or("default")
    );
    // Platform-specific audio capture and passthrough.
    // Full implementation uses cpal for cross-platform audio I/O:
    //   let host = cpal::default_host();
    //   let input_device = host.default_input_device()?;
    //   let output_device = host.default_output_device()?;
    //   Build streams and copy samples from input → output in callback.
    // Currently implemented as a passthrough stub that logs intent.
    while running.load(Ordering::Relaxed) {
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    log::debug!("audio passthrough loop exited");
}

/// Platform detection for available audio backends.
pub fn detect_audio_backend() -> &'static str {
    #[cfg(target_os = "macos")]
    {
        return "CoreAudio";
    }
    #[cfg(target_os = "linux")]
    {
        return "PulseAudio/ALSA";
    }
    #[allow(unreachable_code)]
    "unknown"
}
