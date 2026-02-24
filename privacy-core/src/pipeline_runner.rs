//! Spawns pipeline threads and wires channels with backpressure.
//!
//! Thread layout:
//!   capture_thread  →  raw_tx  →  detection_thread  →  detection_tx
//!   →  transform_thread  →  transformed_tx  →  output_thread

use crate::{
    capture::CaptureSource,
    detection::{
        incremental::{IncrementalOcr, GRID_COLS, GRID_ROWS},
        ocr::OcrEngine,
        patterns::PatternRegistry,
        scanner::scan,
        expand::expand_and_merge,
    },
    pipeline::{PipelineChannels, CHANNEL_CAPACITY},
    transform::registry::apply_transform,
};
use crossbeam_channel::{RecvTimeoutError, Sender};
use privacy_common::{
    detection::DetectedRegions,
    frame::TransformedFrame,
    transform::TransformMode,
};
use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::Duration,
};

/// Shared mutable state accessible across threads.
pub struct SharedState {
    pub running: AtomicBool,
    pub transform_mode: Mutex<TransformMode>,
    pub transform_intensity: Mutex<f32>,
    pub registry: Mutex<PatternRegistry>,
}

impl SharedState {
    pub fn new(registry: PatternRegistry) -> Arc<Self> {
        Arc::new(Self {
            running: AtomicBool::new(true),
            transform_mode: Mutex::new(TransformMode::default()),
            transform_intensity: Mutex::new(1.0),
            registry: Mutex::new(registry),
        })
    }
}

/// Spawn all pipeline threads. Returns a handle that stops everything when dropped.
pub struct PipelineHandle {
    pub state: Arc<SharedState>,
    threads: Vec<Option<thread::JoinHandle<()>>>,
}

impl PipelineHandle {
    /// Signal stop and join all threads in pipeline order.
    pub fn shutdown(mut self) {
        self.state.running.store(false, Ordering::SeqCst);
        for h in self.threads.iter_mut() {
            if let Some(handle) = h.take() {
                let _ = handle.join();
            }
        }
    }
}

pub fn spawn_pipeline(
    mut source: Box<dyn CaptureSource + Send>,
    ocr_data_path: Option<String>,
    registry: PatternRegistry,
    output_tx: Sender<TransformedFrame>, // caller reads from here
) -> anyhow::Result<PipelineHandle> {
    let channels = PipelineChannels::new();
    let state = SharedState::new(registry);

    // ── capture thread ──────────────────────────────────────────────────────
    let raw_tx = channels.raw_tx.clone();
    let state_c = Arc::clone(&state);
    let cap_thread = thread::Builder::new()
        .name("aki-capture".into())
        .spawn(move || {
            if source.start().is_err() { return; }
            while state_c.running.load(Ordering::Relaxed) {
                match source.next_frame() {
                    Ok(Some(frame)) => {
                        if raw_tx.is_full() { // drop oldest — discard new
                        } else {
                            let _ = raw_tx.try_send(frame);
                        }
                    }
                    Ok(None) => thread::sleep(Duration::from_millis(5)),
                    Err(_) => break,
                }
            }
            let _ = source.stop();
        })?;

    // ── detection thread ────────────────────────────────────────────────────
    let raw_rx = channels.raw_rx;
    let detection_tx = channels.detection_tx.clone();
    let state_d = Arc::clone(&state);
    let det_thread = thread::Builder::new()
        .name("aki-detect".into())
        .spawn(move || {
            let ocr_engine = match OcrEngine::new(ocr_data_path.as_deref()) {
                Ok(o) => o,
                Err(_) => return,
            };
            let mut ocr = IncrementalOcr::new(ocr_engine, GRID_COLS, GRID_ROWS);
            while state_d.running.load(Ordering::Relaxed) {
                match raw_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok(frame) => {
                        let regions = match ocr.extract(&frame) {
                            Ok(text_regions) => {
                                let reg = state_d.registry.lock().unwrap();
                                let matches = scan(&text_regions, &reg);
                                let merged = expand_and_merge(
                                    matches, frame.width, frame.height, 0.10,
                                );
                                DetectedRegions { matches: merged }
                            }
                            Err(_) => DetectedRegions::default(),
                        };
                        if !detection_tx.is_full() {
                            let _ = detection_tx.try_send((frame, regions));
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
        })?;

    // ── transform thread ────────────────────────────────────────────────────
    let detection_rx = channels.detection_rx;
    let transformed_tx = channels.transformed_tx.clone();
    let state_t = Arc::clone(&state);
    let tx_thread = thread::Builder::new()
        .name("aki-transform".into())
        .spawn(move || {
            while state_t.running.load(Ordering::Relaxed) {
                match detection_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok((frame, regions)) => {
                        let mode = *state_t.transform_mode.lock().unwrap();
                        let intensity = *state_t.transform_intensity.lock().unwrap();
                        let result = apply_transform(&frame, &regions, mode, intensity)
                            .unwrap_or_else(|_| TransformedFrame {
                                pixels: frame.pixels.clone(),
                                width: frame.width,
                                height: frame.height,
                                timestamp: frame.timestamp,
                            });
                        if !transformed_tx.is_full() {
                            let _ = transformed_tx.try_send(result);
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
        })?;

    // ── output thread ───────────────────────────────────────────────────────
    let transformed_rx = channels.transformed_rx;
    let state_o = Arc::clone(&state);
    let out_thread = thread::Builder::new()
        .name("aki-output".into())
        .spawn(move || {
            while state_o.running.load(Ordering::Relaxed) {
                match transformed_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok(frame) => {
                        if !output_tx.is_full() {
                            let _ = output_tx.try_send(frame);
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
        })?;

    Ok(PipelineHandle {
        state,
        threads: vec![
            Some(cap_thread),
            Some(det_thread),
            Some(tx_thread),
            Some(out_thread),
        ],
    })
}

impl Drop for PipelineHandle {
    fn drop(&mut self) {
        self.state.running.store(false, Ordering::SeqCst);
        for h in self.threads.iter_mut() {
            if let Some(handle) = h.take() {
                let _ = handle.join();
            }
        }
    }
}
