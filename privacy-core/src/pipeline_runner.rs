//! Spawns pipeline threads and wires channels with backpressure.
//!
//! Thread layout:
//!   capture_thread  →  raw_tx  →  detection_thread  →  detection_tx
//!   →  transform_thread  →  transformed_tx  →  output_thread

use crate::{
    capture::CaptureSource,
    detection::{
        expand::expand_and_merge,
        incremental::{IncrementalOcr, GRID_COLS, GRID_ROWS},
        line_expand::expand_to_end_of_line,
        ocr::OcrEngine,
        patterns::PatternRegistry,
        scanner::scan,
        whitelist::Whitelist,
    },
    pipeline::PipelineChannels,
    transform::registry::{apply_transform, apply_transform_full},
};
use crossbeam_channel::{RecvTimeoutError, Sender};
use privacy_common::{
    detection::{DetectedRegions, SensitiveMatch, Severity},
    frame::{RawFrame, Rect, TransformedFrame},
    transform::TransformMode,
};
use std::{
    collections::{HashMap, VecDeque},
    sync::{
        atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

/// 30fps frame budget in ms
const FRAME_BUDGET_MS: u128 = 33;
/// Minimum OCR grid dimensions under load
const MIN_GRID: u32 = 2;
/// Publish raw preview at 10Hz to keep clone overhead bounded.
const RAW_PREVIEW_INTERVAL_MS: u64 = 100;
/// Keep only the most recent detection events.
const DETECTION_EVENT_QUEUE_CAP: usize = 256;
/// Suppress duplicate detections for this window.
const DETECTION_DEDUPE_WINDOW_MS: u64 = 1000;
/// Drop stale dedupe entries to keep cache bounded.
const DETECTION_DEDUPE_CACHE_TTL_MS: u64 = 5000;

#[derive(Debug, Clone)]
pub struct PipelineDetectionEvent {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub pattern_name: String,
    pub severity: Severity,
    pub snippet: String,
    pub bounds: Rect,
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
struct DetectionDedupeKey {
    pattern_name: String,
    snippet: String,
    x: u32,
    y: u32,
    width: u32,
    height: u32,
}

impl From<&SensitiveMatch> for DetectionDedupeKey {
    fn from(m: &SensitiveMatch) -> Self {
        Self {
            pattern_name: m.pattern_name.clone(),
            snippet: m.snippet.clone(),
            x: m.bounds.x,
            y: m.bounds.y,
            width: m.bounds.width,
            height: m.bounds.height,
        }
    }
}

fn clamp_ms(v: u128) -> u32 {
    v.min(u32::MAX as u128) as u32
}

fn update_peak_regions(peak: &AtomicU32, current: u32) {
    peak.fetch_max(current, Ordering::Relaxed);
}

fn prune_dedupe_cache(cache: &mut HashMap<DetectionDedupeKey, Instant>, now: Instant) {
    let ttl = Duration::from_millis(DETECTION_DEDUPE_CACHE_TTL_MS);
    cache.retain(|_, last| now.saturating_duration_since(*last) <= ttl);
}

fn should_emit_detection(
    m: &SensitiveMatch,
    dedupe_cache: &mut HashMap<DetectionDedupeKey, Instant>,
    now: Instant,
) -> bool {
    let key = DetectionDedupeKey::from(m);
    let dedupe_window = Duration::from_millis(DETECTION_DEDUPE_WINDOW_MS);
    let should_emit = dedupe_cache
        .get(&key)
        .map(|last| now.saturating_duration_since(*last) >= dedupe_window)
        .unwrap_or(true);
    if should_emit {
        dedupe_cache.insert(key, now);
    }
    should_emit
}

fn push_detection_event(
    queue: &mut VecDeque<PipelineDetectionEvent>,
    event: PipelineDetectionEvent,
) {
    if queue.len() >= DETECTION_EVENT_QUEUE_CAP {
        queue.pop_front();
    }
    queue.push_back(event);
}

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
    /// capture error message (None = ok, Some = failed)
    pub capture_error: Mutex<Option<String>>,
    /// frames dropped due to full channels in any pipeline thread
    pub dropped_frames: AtomicU64,
    /// latest measured capture stage latency in milliseconds
    pub capture_latency_ms: AtomicU32,
    /// latest measured detection stage latency in milliseconds
    pub ocr_latency_ms: AtomicU32,
    /// latest measured transform stage latency in milliseconds
    pub transform_latency_ms: AtomicU32,
    /// low-rate raw preview frame for TUI rendering
    pub latest_raw_preview: Mutex<Option<RawFrame>>,
    /// bounded queue of detection events for TUI overlays/logging
    pub detection_events: Mutex<VecDeque<PipelineDetectionEvent>>,
    /// number of regions detected in the most recent frame
    pub last_regions_count: AtomicU32,
    /// peak regions detected in a single frame this session
    pub peak_regions_count: AtomicU32,
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
            capture_error: Mutex::new(None),
            dropped_frames: AtomicU64::new(0),
            capture_latency_ms: AtomicU32::new(0),
            ocr_latency_ms: AtomicU32::new(0),
            transform_latency_ms: AtomicU32::new(0),
            latest_raw_preview: Mutex::new(None),
            detection_events: Mutex::new(VecDeque::with_capacity(DETECTION_EVENT_QUEUE_CAP)),
            last_regions_count: AtomicU32::new(0),
            peak_regions_count: AtomicU32::new(0),
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
    log::info!(
        "spawn_pipeline ocr_data_path={} registry_patterns={}",
        ocr_data_path.as_deref().unwrap_or("<default>"),
        registry.patterns.len()
    );
    // apply accelerator preference from config before any neural inference
    let accel = crate::config::AppConfig::load()
        .unwrap_or_default()
        .transform
        .accelerator;
    crate::transform::neural::configure_accelerator(accel);
    let channels = PipelineChannels::new();
    let state = SharedState::new(registry);

    // load capture sub-region from config (optional "x,y,w,h")
    let capture_region_rect = crate::config::AppConfig::load()
        .unwrap_or_default()
        .capture
        .region
        .as_deref()
        .and_then(crate::config::parse_rect);

    // ── capture thread ──────────────────────────────────────────────────────
    let raw_tx = channels.raw_tx.clone();
    let state_c = Arc::clone(&state);
    let cap_thread = thread::Builder::new()
        .name("aki-capture".into())
        .spawn(move || {
            log::info!("pipeline thread started: aki-capture");
            if let Err(e) = source.start() {
                log::error!("capture source start failed: {e}");
                *state_c.capture_error.lock().unwrap() = Some(format!("capture failed: {e}"));
                return;
            }
            log::info!("capture source started successfully");
            let mut last_raw_preview = Instant::now()
                .checked_sub(Duration::from_millis(RAW_PREVIEW_INTERVAL_MS))
                .unwrap_or_else(Instant::now);
            while state_c.running.load(Ordering::Relaxed) {
                let cap_start = Instant::now();
                match source.next_frame() {
                    Ok(Some(frame)) => {
                        state_c
                            .capture_latency_ms
                            .store(clamp_ms(cap_start.elapsed().as_millis()), Ordering::Relaxed);
                        let frame = if let Some(ref rect) = capture_region_rect {
                            match crate::capture::region::crop_frame(&frame, rect) {
                                Ok(cropped) => cropped,
                                Err(e) => {
                                    log::warn!("crop_frame: {e}");
                                    frame
                                }
                            }
                        } else {
                            frame
                        };
                        if last_raw_preview.elapsed()
                            >= Duration::from_millis(RAW_PREVIEW_INTERVAL_MS)
                        {
                            if let Ok(mut raw) = state_c.latest_raw_preview.lock() {
                                *raw = Some(frame.clone());
                            }
                            last_raw_preview = Instant::now();
                        }
                        if raw_tx.is_full() {
                            log::trace!("capture decision: raw channel full, dropping frame");
                            state_c.dropped_frames.fetch_add(1, Ordering::Relaxed);
                        } else {
                            let _ = raw_tx.try_send(frame);
                        }
                    }
                    Ok(None) => {
                        state_c
                            .capture_latency_ms
                            .store(clamp_ms(cap_start.elapsed().as_millis()), Ordering::Relaxed);
                        thread::sleep(Duration::from_millis(5));
                    }
                    Err(e) => {
                        state_c
                            .capture_latency_ms
                            .store(clamp_ms(cap_start.elapsed().as_millis()), Ordering::Relaxed);
                        log::error!("capture source next_frame failed: {e}");
                        break;
                    }
                }
            }
            let _ = source.stop();
            log::info!("pipeline thread stopped: aki-capture");
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
            log::info!("pipeline thread started: aki-detect");
            let ocr_engine =
                match OcrEngine::new_with_confidence(ocr_data_path.as_deref(), min_conf) {
                    Ok(o) => o,
                    Err(e) => {
                        log::error!("ocr engine init failed: {e}");
                        return;
                    }
                };
            let mut ocr = IncrementalOcr::new(ocr_engine, GRID_COLS, GRID_ROWS);
            let mut dedupe_cache: HashMap<DetectionDedupeKey, Instant> = HashMap::new();
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
                                let merged =
                                    expand_and_merge(matches, frame.width, frame.height, 0.10);
                                let merged = expand_to_end_of_line(merged, frame.width);
                                DetectedRegions { matches: merged }
                            }
                            Err(_) => DetectedRegions::default(),
                        };
                        let elapsed = t0.elapsed().as_millis();
                        state_d
                            .ocr_latency_ms
                            .store(clamp_ms(elapsed), Ordering::Relaxed);
                        let region_count = regions.matches.len() as u32;
                        state_d
                            .last_regions_count
                            .store(region_count, Ordering::Relaxed);
                        update_peak_regions(&state_d.peak_regions_count, region_count);

                        let now = Instant::now();
                        prune_dedupe_cache(&mut dedupe_cache, now);
                        let now_utc = chrono::Utc::now();
                        let mut events = Vec::new();
                        for m in &regions.matches {
                            if should_emit_detection(m, &mut dedupe_cache, now) {
                                events.push(PipelineDetectionEvent {
                                    timestamp: now_utc,
                                    pattern_name: m.pattern_name.clone(),
                                    severity: m.severity,
                                    snippet: m.snippet.clone(),
                                    bounds: m.bounds.clone(),
                                });
                            }
                        }
                        if !events.is_empty() {
                            if let Ok(mut queue) = state_d.detection_events.lock() {
                                for event in events {
                                    push_detection_event(&mut queue, event);
                                }
                            }
                        }

                        // adaptive quality scaling: reduce grid if over budget
                        if elapsed > FRAME_BUDGET_MS {
                            let cur_cols = state_d.target_grid_cols.load(Ordering::Relaxed);
                            let cur_rows = state_d.target_grid_rows.load(Ordering::Relaxed);
                            if cur_cols > MIN_GRID || cur_rows > MIN_GRID {
                                state_d.target_grid_cols.store(
                                    cur_cols.saturating_sub(1).max(MIN_GRID),
                                    Ordering::Relaxed,
                                );
                                state_d.target_grid_rows.store(
                                    cur_rows.saturating_sub(1).max(MIN_GRID),
                                    Ordering::Relaxed,
                                );
                                *state_d.quality_scale.lock().unwrap() = 0.8;
                                log::warn!(
                                    "adaptive quality: detection {}ms > {}ms budget, grid {}x{}",
                                    elapsed,
                                    FRAME_BUDGET_MS,
                                    cur_cols.saturating_sub(1).max(MIN_GRID),
                                    cur_rows.saturating_sub(1).max(MIN_GRID)
                                );
                            }
                        } else if elapsed < FRAME_BUDGET_MS / 2 {
                            // recovery: gradually increase grid back toward defaults
                            let cur_cols = state_d.target_grid_cols.load(Ordering::Relaxed);
                            let cur_rows = state_d.target_grid_rows.load(Ordering::Relaxed);
                            if cur_cols < GRID_COLS || cur_rows < GRID_ROWS {
                                state_d
                                    .target_grid_cols
                                    .store((cur_cols + 1).min(GRID_COLS), Ordering::Relaxed);
                                state_d
                                    .target_grid_rows
                                    .store((cur_rows + 1).min(GRID_ROWS), Ordering::Relaxed);
                                *state_d.quality_scale.lock().unwrap() = 1.0;
                            }
                        }
                        if detection_tx.is_full() {
                            log::trace!("detect decision: detection channel full, dropping frame");
                            state_d.dropped_frames.fetch_add(1, Ordering::Relaxed);
                        } else {
                            let _ = detection_tx.try_send((frame, regions));
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
            log::info!("pipeline thread stopped: aki-detect");
        })?;

    // ── transform thread ────────────────────────────────────────────────────
    let detection_rx = channels.detection_rx;
    let transformed_tx = channels.transformed_tx.clone();
    let state_t = Arc::clone(&state);
    let tx_thread = thread::Builder::new()
        .name("aki-transform".into())
        .spawn(move || {
            log::info!("pipeline thread started: aki-transform");
            while state_t.running.load(Ordering::Relaxed) {
                if state_t.paused.load(Ordering::Relaxed) {
                    thread::sleep(Duration::from_millis(50));
                    continue;
                }
                match detection_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok((frame, regions)) => {
                        let transform_start = Instant::now();
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
                                    &frame,
                                    &regions,
                                    old_mode,
                                    intensity,
                                    &[],
                                    &[],
                                    1.0,
                                );
                                let new_frame = apply_transform_full(
                                    &frame,
                                    &regions,
                                    mode,
                                    intensity,
                                    &[],
                                    &[],
                                    1.0,
                                );
                                state_t.transition_frames.fetch_sub(1, Ordering::Relaxed);
                                match (old_frame, new_frame) {
                                    (Ok(o), Ok(n)) => {
                                        // pixel-blend old * old_alpha + new * new_alpha
                                        let blended: Vec<u8> = o
                                            .pixels
                                            .iter()
                                            .zip(n.pixels.iter())
                                            .map(|(&op, &np)| {
                                                (op as f32 * old_alpha + np as f32 * new_alpha)
                                                    as u8
                                            })
                                            .collect();
                                        Ok(TransformedFrame {
                                            pixels: blended,
                                            width: o.width,
                                            height: o.height,
                                            timestamp: o.timestamp,
                                        })
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
                        state_t.transform_latency_ms.store(
                            clamp_ms(transform_start.elapsed().as_millis()),
                            Ordering::Relaxed,
                        );
                        if transformed_tx.is_full() {
                            log::trace!(
                                "transform decision: transformed channel full, dropping frame"
                            );
                            state_t.dropped_frames.fetch_add(1, Ordering::Relaxed);
                        } else {
                            let _ = transformed_tx.try_send(result);
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
            log::info!("pipeline thread stopped: aki-transform");
        })?;

    // ── output thread ───────────────────────────────────────────────────────
    let transformed_rx = channels.transformed_rx;
    let state_o = Arc::clone(&state);
    let out_thread = thread::Builder::new()
        .name("aki-output".into())
        .spawn(move || {
            log::info!("pipeline thread started: aki-output");
            while state_o.running.load(Ordering::Relaxed) {
                match transformed_rx.recv_timeout(Duration::from_millis(100)) {
                    Ok(frame) => {
                        if !output_tx.is_full() {
                            let _ = output_tx.try_send(frame);
                        } else {
                            log::trace!("output decision: output channel full, dropping frame");
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => {}
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
            log::info!("pipeline thread stopped: aki-output");
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

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::detection::Severity;

    fn make_match(snippet: &str) -> SensitiveMatch {
        SensitiveMatch {
            bounds: Rect {
                x: 10,
                y: 20,
                width: 30,
                height: 40,
            },
            pattern_name: "token".to_string(),
            severity: Severity::High,
            snippet: snippet.to_string(),
        }
    }

    #[test]
    fn dedupe_suppresses_within_window() {
        let m = make_match("abc***");
        let mut cache = HashMap::new();
        let now = Instant::now();

        assert!(should_emit_detection(&m, &mut cache, now));
        assert!(!should_emit_detection(
            &m,
            &mut cache,
            now + Duration::from_millis(DETECTION_DEDUPE_WINDOW_MS - 1),
        ));
        assert!(should_emit_detection(
            &m,
            &mut cache,
            now + Duration::from_millis(DETECTION_DEDUPE_WINDOW_MS),
        ));
    }

    #[test]
    fn detection_event_queue_is_bounded() {
        let mut q = VecDeque::new();
        for i in 0..(DETECTION_EVENT_QUEUE_CAP + 10) {
            push_detection_event(
                &mut q,
                PipelineDetectionEvent {
                    timestamp: chrono::Utc::now(),
                    pattern_name: format!("p{i}"),
                    severity: Severity::Low,
                    snippet: format!("s{i}"),
                    bounds: Rect {
                        x: i as u32,
                        y: 0,
                        width: 1,
                        height: 1,
                    },
                },
            );
        }
        assert_eq!(q.len(), DETECTION_EVENT_QUEUE_CAP);
        assert_eq!(
            q.front().map(|e| e.pattern_name.clone()),
            Some("p10".to_string())
        );
    }

    #[test]
    fn peak_region_counter_tracks_max() {
        let peak = AtomicU32::new(0);
        update_peak_regions(&peak, 2);
        update_peak_regions(&peak, 1);
        update_peak_regions(&peak, 7);
        assert_eq!(peak.load(Ordering::Relaxed), 7);
    }
}
