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
        whitelist::Whitelist,
    },
    pipeline::{PipelineChannels, CHANNEL_CAPACITY},
    transform::registry::{apply_transform, apply_transform_full},
};
use crossbeam_channel::{RecvTimeoutError, Sender};
use privacy_common::{
    detection::DetectedRegions,
    frame::TransformedFrame,
    transform::TransformMode,
};
use std::{
    sync::{
        atomic::{AtomicBool, AtomicU32, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

/// 30fps frame budget in ms
const FRAME_BUDGET_MS: u128 = 33;
/// Minimum OCR grid dimensions under load
const MIN_GRID: u32 = 2;

/// Shared mutable state accessible across threads.
pub struct SharedState {
    pub running: AtomicBool,
    pub paused: AtomicBool,
    pub transform_mode: Mutex<TransformMode>,
    pub transform_intensity: Mutex<f32>,
    pub registry: Mutex<PatternRegistry>,
    /// adaptive quality: target OCR grid cols/rows (0 = default)
    pub target_grid_cols: AtomicU32,
    pub target_grid_rows: AtomicU32,
    /// adaptive quality scale multiplier applied to transform intensity [0.5..1.0]
    pub quality_scale: Mutex<f32>,
    /// whitelist of safe strings — scanner skips matching regions
    pub whitelist: Mutex<Whitelist>,
    /// crossfade: previous mode during transition (None = no transition active)
    pub transition_from: Mutex<Option<TransformMode>>,
    /// crossfade: frames remaining in transition (0 = no transition)
    pub transition_frames: AtomicU32,
}

impl SharedState {
    pub fn new(registry: PatternRegistry) -> Arc<Self> {
        let whitelist = Whitelist::load().unwrap_or_else(|_| Whitelist::empty());
        Arc::new(Self {
            running: AtomicBool::new(true),
            paused: AtomicBool::new(false),
            transform_mode: Mutex::new(TransformMode::default()),
            transform_intensity: Mutex::new(1.0),
            registry: Mutex::new(registry),
            target_grid_cols: AtomicU32::new(GRID_COLS),
            target_grid_rows: AtomicU32::new(GRID_ROWS),
            quality_scale: Mutex::new(1.0),
            transition_from: Mutex::new(None),
            transition_frames: AtomicU32::new(0),
            whitelist: Mutex::new(whitelist),
        })
    }

    /// Switch transform mode with a 10-frame crossfade transition.
    pub fn begin_mode_transition(&self, new_mode: TransformMode) {
        let old = *self.transform_mode.lock().unwrap();
        *self.transition_from.lock().unwrap() = Some(old);
        self.transition_frames.store(10, Ordering::SeqCst);
        *self.transform_mode.lock().unwrap() = new_mode;
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
    let min_conf = crate::config::AppConfig::load()
        .unwrap_or_default()
        .detection
        .min_confidence as f32;
    let det_thread = thread::Builder::new()
        .name("aki-detect".into())
        .spawn(move || {
            let ocr_engine = match OcrEngine::new_with_confidence(ocr_data_path.as_deref(), min_conf) {
                Ok(o) => o,
                Err(_) => return,
            };
            let mut ocr = IncrementalOcr::new(ocr_engine, GRID_COLS, GRID_ROWS);
            while state_d.running.load(Ordering::Relaxed) {
                // apply adaptive grid if it changed
                let tgt_cols = state_d.target_grid_cols.load(Ordering::Relaxed);
                let tgt_rows = state_d.target_grid_rows.load(Ordering::Relaxed);
                if tgt_cols != ocr.cols() || tgt_rows != ocr.rows() {
                    ocr.resize_grid(tgt_cols, tgt_rows);
                }
                match raw_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok(frame) => {
                        let t0 = Instant::now();
                        let regions = match ocr.extract(&frame) {
                            Ok(text_regions) => {
                                let reg = state_d.registry.lock().unwrap();
                                let wl = state_d.whitelist.lock().unwrap();
                                let matches = scan(&text_regions, &reg, &wl);
                                drop(wl);
                                let merged = expand_and_merge(
                                    matches, frame.width, frame.height, 0.10,
                                );
                                DetectedRegions { matches: merged }
                            }
                            Err(_) => DetectedRegions::default(),
                        };
                        let elapsed = t0.elapsed().as_millis();
                        // adaptive quality scaling: reduce grid if over budget
                        if elapsed > FRAME_BUDGET_MS {
                            let cur_cols = state_d.target_grid_cols.load(Ordering::Relaxed);
                            let cur_rows = state_d.target_grid_rows.load(Ordering::Relaxed);
                            if cur_cols > MIN_GRID || cur_rows > MIN_GRID {
                                state_d.target_grid_cols.store(cur_cols.saturating_sub(1).max(MIN_GRID), Ordering::Relaxed);
                                state_d.target_grid_rows.store(cur_rows.saturating_sub(1).max(MIN_GRID), Ordering::Relaxed);
                                *state_d.quality_scale.lock().unwrap() = 0.8;
                                log::warn!("adaptive quality: detection {}ms > {}ms budget, grid {}x{}", elapsed, FRAME_BUDGET_MS, cur_cols.saturating_sub(1).max(MIN_GRID), cur_rows.saturating_sub(1).max(MIN_GRID));
                            }
                        } else if elapsed < FRAME_BUDGET_MS / 2 {
                            // recovery: gradually increase grid back toward defaults
                            let cur_cols = state_d.target_grid_cols.load(Ordering::Relaxed);
                            let cur_rows = state_d.target_grid_rows.load(Ordering::Relaxed);
                            if cur_cols < GRID_COLS || cur_rows < GRID_ROWS {
                                state_d.target_grid_cols.store((cur_cols + 1).min(GRID_COLS), Ordering::Relaxed);
                                state_d.target_grid_rows.store((cur_rows + 1).min(GRID_ROWS), Ordering::Relaxed);
                                *state_d.quality_scale.lock().unwrap() = 1.0;
                            }
                        }
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
                if state_t.paused.load(Ordering::Relaxed) {
                    thread::sleep(Duration::from_millis(50));
                    continue;
                }
                match detection_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok((frame, regions)) => {
                        let mode = *state_t.transform_mode.lock().unwrap();
                        let base_intensity = *state_t.transform_intensity.lock().unwrap();
                        let qscale = *state_t.quality_scale.lock().unwrap();
                        let intensity = (base_intensity * qscale).clamp(0.0, 1.0);
                        // crossfade: if transition active, blend old and new transforms
                        let t_frames = state_t.transition_frames.load(Ordering::Relaxed);
                        let from_mode = *state_t.transition_from.lock().unwrap();
                        let result = if t_frames > 0 {
                            if let Some(old_mode) = from_mode {
                                let old_alpha = t_frames as f32 / 10.0; // old weight (1.0→0.0)
                                let new_alpha = 1.0 - old_alpha;
                                let old_frame = apply_transform_full(
                                    &frame, &regions, old_mode, intensity, &[], &[], 1.0,
                                );
                                let new_frame = apply_transform_full(
                                    &frame, &regions, mode, intensity, &[], &[], 1.0,
                                );
                                state_t.transition_frames.fetch_sub(1, Ordering::Relaxed);
                                match (old_frame, new_frame) {
                                    (Ok(o), Ok(n)) => {
                                        // pixel-blend old * old_alpha + new * new_alpha
                                        let blended: Vec<u8> = o.pixels.iter().zip(n.pixels.iter())
                                            .map(|(&op, &np)| (op as f32 * old_alpha + np as f32 * new_alpha) as u8)
                                            .collect();
                                        Ok(TransformedFrame { pixels: blended, width: o.width, height: o.height, timestamp: o.timestamp })
                                    }
                                    (_, Ok(n)) => Ok(n),
                                    (Ok(o), _) => Ok(o),
                                    _ => Err(anyhow::anyhow!("both transforms failed")),
                                }
                            } else {
                                apply_transform(&frame, &regions, mode, intensity)
                            }
                        } else {
                            apply_transform(&frame, &regions, mode, intensity)
                        };
                        let result = result.unwrap_or_else(|_| TransformedFrame {
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
