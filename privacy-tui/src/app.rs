//! Application state shared across all TUI components.

use crate::{control_server::ControlState, foreground};
use privacy_common::{frame::Rect, transform::TransformMode};
use privacy_core::{
    config::AppConfig,
    detection::{
        patterns::PatternRegistry,
        profiles::{
            apply_detector_profile, detector_profile_from_name, select_detector_profile,
            DetectorProfileKind,
        },
        registry::runtime_registry,
    },
};
use std::{
    collections::{HashMap, VecDeque},
    sync::Arc,
    time::{Duration, Instant},
};

/// Pipeline running state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PipelineState {
    Running,
    Paused,
}

/// Aggregate pipeline statistics updated each tick.
#[derive(Debug, Clone)]
pub struct PipelineStats {
    pub actual_fps: f32,
    pub capture_latency_ms: f32,
    pub ocr_latency_ms: f32,
    pub transform_latency_ms: f32,
    pub output_latency_ms: f32,
    pub dropped_frames: u64,
    /// adaptive quality scale (1.0 = full, 0.8 = reduced)
    pub quality_scale: f32,
    /// current adaptive OCR grid dimensions
    pub ocr_grid_cols: u32,
    pub ocr_grid_rows: u32,
}

impl Default for PipelineStats {
    fn default() -> Self {
        Self {
            actual_fps: 0.0,
            capture_latency_ms: 0.0,
            ocr_latency_ms: 0.0,
            transform_latency_ms: 0.0,
            output_latency_ms: 0.0,
            dropped_frames: 0,
            quality_scale: 1.0,
            ocr_grid_cols: privacy_core::detection::incremental::GRID_COLS,
            ocr_grid_rows: privacy_core::detection::incremental::GRID_ROWS,
        }
    }
}

const HEATMAP_GRID_X: u8 = 20;
const HEATMAP_GRID_Y: u8 = 15;
const HEATMAP_WINDOW: Duration = Duration::from_secs(60);

/// Detection frequency heatmap over a 60-second sliding window.
pub struct HeatmapState {
    pub enabled: bool,
    /// key: (grid_x, grid_y), value: ring buffer of hit timestamps
    pub cells: HashMap<(u8, u8), VecDeque<Instant>>,
}

impl HeatmapState {
    pub fn new() -> Self {
        Self {
            enabled: false,
            cells: HashMap::new(),
        }
    }

    /// Record a detection hit for the given rect (frame coords).
    #[allow(dead_code)]
    pub fn record_hit(&mut self, r: &Rect, frame_w: u32, frame_h: u32) {
        if frame_w == 0 || frame_h == 0 {
            return;
        }
        let cx = ((r.x + r.width / 2) as f32 / frame_w as f32 * HEATMAP_GRID_X as f32) as u8;
        let cy = ((r.y + r.height / 2) as f32 / frame_h as f32 * HEATMAP_GRID_Y as f32) as u8;
        let cx = cx.min(HEATMAP_GRID_X - 1);
        let cy = cy.min(HEATMAP_GRID_Y - 1);
        let entry = self.cells.entry((cx, cy)).or_default();
        entry.push_back(Instant::now());
    }

    /// Evict timestamps older than HEATMAP_WINDOW and return heat (0.0-1.0) for a cell.
    pub fn heat(&mut self, gx: u8, gy: u8) -> f32 {
        let now = Instant::now();
        let entry = self.cells.entry((gx, gy)).or_default();
        while entry
            .front()
            .map(|t| now.duration_since(*t) > HEATMAP_WINDOW)
            .unwrap_or(false)
        {
            entry.pop_front();
        }
        // cap at 30 hits → 1.0
        (entry.len() as f32 / 30.0).min(1.0)
    }

    pub fn grid_dims() -> (u8, u8) {
        (HEATMAP_GRID_X, HEATMAP_GRID_Y)
    }
}

impl Default for HeatmapState {
    fn default() -> Self {
        Self::new()
    }
}

/// Per-pattern detection statistics.
#[derive(Debug, Clone, Default)]
#[allow(dead_code)]
pub struct PatternStats {
    pub name: String,
    pub total_hits: u64,
    pub last_region: Option<Rect>,
}

/// Detection statistics overlay state.
pub struct StatsOverlayState {
    pub open: bool,
    pub pattern_stats: HashMap<String, PatternStats>,
    #[allow(dead_code)]
    pub total_regions_this_frame: u32,
    pub peak_regions: u32,
}

impl StatsOverlayState {
    pub fn new() -> Self {
        Self {
            open: false,
            pattern_stats: HashMap::new(),
            total_regions_this_frame: 0,
            peak_regions: 0,
        }
    }

    #[allow(dead_code)]
    pub fn record(&mut self, pattern_name: &str, bounds: Option<Rect>) {
        let s = self
            .pattern_stats
            .entry(pattern_name.to_string())
            .or_insert_with(|| PatternStats {
                name: pattern_name.to_string(),
                ..Default::default()
            });
        s.total_hits += 1;
        if let Some(b) = bounds {
            s.last_region = Some(b);
        }
    }
}

impl Default for StatsOverlayState {
    fn default() -> Self {
        Self::new()
    }
}

/// Latency history for sparkline (last 120 frames, ms per frame).
pub const LATENCY_HISTORY_LEN: usize = 120;

/// Preview frame update sent from the pipeline background thread.
pub struct PreviewUpdate {
    pub pixels: Vec<u8>,
    pub width: u32,
    pub height: u32,
    pub fps: f32,
    pub output_latency_ms: f32,
}

pub struct App {
    pub running: bool,
    pub pipeline_state: PipelineState,
    pub transform_mode: TransformMode,
    pub transform_intensity: f32,
    pub stats: PipelineStats,
    pub log_entries: Vec<LogEntry>,
    #[allow(dead_code)]
    pub started_at: Instant,
    /// Raw capture preview pixels (RGBA, half-res).
    pub raw_preview_pixels: Option<Vec<u8>>,
    /// Transformed output preview pixels (RGBA, half-res).
    pub tx_preview_pixels: Option<Vec<u8>>,
    /// Snapshot of tx pixels before last mode switch (for crossfade).
    pub prev_tx_preview_pixels: Option<Vec<u8>>,
    /// Frames remaining in mode-switch crossfade (0 = inactive, counts down 10→0).
    pub transition_frames_left: u8,
    pub preview_width: u32,
    pub preview_height: u32,
    /// Currently selected capture window id (None = full screen).
    pub selected_window_id: Option<u64>,
    /// Title for the selected capture window, used as a fallback when foreground app detection is unavailable.
    pub selected_window_title: Option<String>,
    pub window_selector: crate::ui::window_selector::WindowSelectorState,
    pub pattern_manager: crate::ui::pattern_manager::PatternManagerState,
    pub pattern_registry: PatternRegistry,
    pub heatmap: HeatmapState,
    pub stats_overlay: StatsOverlayState,
    /// Frame-level latency history (ms) for sparkline
    pub latency_history: VecDeque<u64>,
    /// Flash raw-preview border red on first detection
    pub first_detection_flash: Option<Instant>,
    /// Recording start time (Some = currently recording)
    pub recording_started_at: Option<Instant>,
    /// Active profile name (None = default)
    pub active_profile: Option<String>,
    /// Available profile names (loaded from config)
    pub profile_names: Vec<String>,
    /// Active detector profile selected from foreground app, override, or disabled state.
    pub detector_profile: DetectorProfileKind,
    /// Source for active detector profile: auto, override, or disabled.
    pub detector_profile_source: String,
    /// Foreground app name observed during the most recent auto-profile check.
    pub detector_profile_app: String,
    /// Foreground window title observed during the most recent auto-profile check.
    pub detector_profile_window: String,
    /// Automatic detector profile selection enabled by config.
    pub auto_detector_profiles_enabled: bool,
    /// Optional config override for detector profile selection.
    pub detector_profile_override: Option<DetectorProfileKind>,
    /// Minimum interval between foreground app checks.
    pub foreground_profile_interval: Duration,
    /// Last foreground app profile check.
    pub last_foreground_profile_check: Instant,
    /// Shared state with the WebSocket control server.
    pub control_state: Arc<ControlState>,
    /// Receives preview frame updates from the pipeline background thread.
    pub preview_rx: Option<crossbeam_channel::Receiver<PreviewUpdate>>,
    /// Set true when window selector confirms a new window, triggering pipeline restart.
    pub pipeline_restart_needed: bool,
    /// Active recorder (Some = recording in progress).
    pub recorder: Option<privacy_output::recorder::Recorder>,
    /// Reference to pipeline SharedState for reading adaptive quality metrics.
    pub pipeline_shared_state: Option<std::sync::Arc<privacy_core::pipeline_runner::SharedState>>,
    /// Most recent capture error message (None = ok).
    pub capture_error: Option<String>,
    /// Scroll offset for detection log (0 = most recent).
    pub log_scroll_offset: usize,
    /// Help overlay visibility.
    pub help_open: bool,
    /// Active output sink kind (for status bar display).
    pub active_sink_kind: Option<privacy_output::SinkKind>,
    /// Use PTY capture instead of screen capture.
    pub use_pty: bool,
}

#[derive(Debug, Clone)]
pub struct LogEntry {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub pattern_name: String,
    pub severity: privacy_common::detection::Severity,
    pub snippet: String,
    pub bounds: Option<Rect>,
}

impl App {
    pub fn new() -> Self {
        let cfg = AppConfig::load().unwrap_or_default();
        let transform_mode = match cfg.transform.mode.as_str() {
            "cartoon" => TransformMode::Cartoon,
            "ascii" => TransformMode::Ascii,
            "pixelate" => TransformMode::Pixelate,
            "neural" => TransformMode::Neural,
            _ => TransformMode::Blur,
        };
        let transform_intensity = cfg.transform.intensity.clamp(0.0, 1.0);
        let profile_names: Vec<String> = cfg.profiles.keys().cloned().collect();
        let mut pattern_registry = runtime_registry(&cfg);
        let detector_profile_override =
            detector_profile_from_name(&cfg.foreground_profiles.override_profile);
        let detector_profile = detector_profile_override.unwrap_or(DetectorProfileKind::Broad);
        apply_detector_profile(&mut pattern_registry, detector_profile);
        let foreground_profile_interval = Duration::from_millis(
            cfg.foreground_profiles
                .update_interval_ms
                .clamp(250, 10_000),
        );
        Self {
            running: true,
            pipeline_state: PipelineState::Running,
            transform_mode,
            transform_intensity,
            stats: PipelineStats::default(),
            log_entries: Vec::new(),
            started_at: Instant::now(),
            raw_preview_pixels: None,
            tx_preview_pixels: None,
            prev_tx_preview_pixels: None,
            transition_frames_left: 0,
            preview_width: 0,
            preview_height: 0,
            selected_window_id: None,
            selected_window_title: None,
            window_selector: crate::ui::window_selector::WindowSelectorState::new(),
            pattern_manager: crate::ui::pattern_manager::PatternManagerState::new(),
            pattern_registry,
            heatmap: HeatmapState::new(),
            stats_overlay: StatsOverlayState::new(),
            latency_history: VecDeque::with_capacity(LATENCY_HISTORY_LEN),
            first_detection_flash: None,
            recording_started_at: None,
            active_profile: None,
            profile_names,
            detector_profile,
            detector_profile_source: if detector_profile_override.is_some() {
                "override".to_string()
            } else if cfg.foreground_profiles.enabled {
                "auto".to_string()
            } else {
                "disabled".to_string()
            },
            detector_profile_app: String::new(),
            detector_profile_window: String::new(),
            auto_detector_profiles_enabled: cfg.foreground_profiles.enabled,
            detector_profile_override,
            foreground_profile_interval,
            last_foreground_profile_check: Instant::now(),
            control_state: ControlState::new(transform_mode, transform_intensity),
            preview_rx: None,
            pipeline_restart_needed: false,
            recorder: None,
            pipeline_shared_state: None,
            capture_error: None,
            log_scroll_offset: 0,
            help_open: false,
            active_sink_kind: None,
            use_pty: false,
        }
    }

    pub fn toggle_pipeline(&mut self) {
        self.pipeline_state = match self.pipeline_state {
            PipelineState::Running => PipelineState::Paused,
            PipelineState::Paused => PipelineState::Running,
        };
        let paused = matches!(self.pipeline_state, PipelineState::Paused);
        log::info!("pipeline toggle -> paused={paused}");
        self.control_state
            .paused
            .store(paused, std::sync::atomic::Ordering::SeqCst);
        if let Some(ps) = self.pipeline_shared_state.clone() {
            ps.paused.store(paused, std::sync::atomic::Ordering::SeqCst);
        }
    }

    pub fn cycle_transform(&mut self) {
        self.prev_tx_preview_pixels = self.tx_preview_pixels.clone(); // snapshot for crossfade
        self.transition_frames_left = 10;
        self.transform_mode = self.transform_mode.next();
        log::info!("transform cycle -> {:?}", self.transform_mode);
        *self.control_state.transform_mode.lock().unwrap() = self.transform_mode;
        if let Some(ref ps) = self.pipeline_shared_state {
            ps.begin_mode_transition(self.transform_mode);
        }
    }

    /// Bind a freshly spawned pipeline state to the app and push current controls into it.
    pub fn attach_pipeline_state(
        &mut self,
        state: std::sync::Arc<privacy_core::pipeline_runner::SharedState>,
    ) {
        let paused = matches!(self.pipeline_state, PipelineState::Paused);
        log::info!(
            "attach_pipeline_state paused={} mode={:?} intensity={:.2} patterns={}",
            paused,
            self.transform_mode,
            self.transform_intensity,
            self.pattern_registry.patterns.len()
        );
        state
            .paused
            .store(paused, std::sync::atomic::Ordering::SeqCst);
        *state.transform_mode.lock().unwrap() = self.transform_mode;
        *state.transform_intensity.lock().unwrap() = self.transform_intensity;
        *state.registry.lock().unwrap() = self.pattern_registry.clone();
        self.pipeline_shared_state = Some(state);
    }

    /// Push current pattern registry edits to the live detection thread.
    pub fn sync_pattern_registry_to_pipeline(&self) {
        if let Some(ref ps) = self.pipeline_shared_state {
            log::info!(
                "sync pattern registry -> {} patterns",
                self.pattern_registry.patterns.len()
            );
            *ps.registry.lock().unwrap() = self.pattern_registry.clone();
        }
    }

    pub fn detector_profile_label(&self) -> &'static str {
        self.detector_profile.name()
    }

    pub fn refresh_foreground_profile(&mut self) {
        let selected_title = self.selected_window_title.as_deref();
        let (profile, source, context) = if !self.auto_detector_profiles_enabled {
            (
                DetectorProfileKind::Broad,
                "disabled",
                foreground::ForegroundContext::fallback(selected_title),
            )
        } else if let Some(profile) = self.detector_profile_override {
            (
                profile,
                "override",
                foreground::ForegroundContext::fallback(selected_title),
            )
        } else if self.use_pty {
            let context = foreground::ForegroundContext::terminal_pty();
            (
                select_detector_profile(&context.app_name, &context.window_title),
                "auto",
                context,
            )
        } else {
            let context = foreground::detect(selected_title);
            (
                select_detector_profile(&context.app_name, &context.window_title),
                "auto",
                context,
            )
        };
        self.apply_detector_profile_selection(profile, source, context);
    }

    pub fn tick_foreground_profile(&mut self) {
        if self.last_foreground_profile_check.elapsed() < self.foreground_profile_interval {
            return;
        }
        self.last_foreground_profile_check = Instant::now();
        self.refresh_foreground_profile();
    }

    fn apply_detector_profile_selection(
        &mut self,
        profile: DetectorProfileKind,
        source: &'static str,
        context: foreground::ForegroundContext,
    ) {
        let unchanged = self.detector_profile == profile
            && self.detector_profile_source == source
            && self.detector_profile_app == context.app_name
            && self.detector_profile_window == context.window_title;
        if unchanged {
            return;
        }
        log::info!(
            "detector profile selected profile={} source={} app='{}' window='{}' description='{}'",
            profile.name(),
            source,
            context.app_name,
            context.window_title,
            profile.description()
        );
        apply_detector_profile(&mut self.pattern_registry, profile);
        self.detector_profile = profile;
        self.detector_profile_source = source.to_string();
        self.detector_profile_app = context.app_name;
        self.detector_profile_window = context.window_title;
        self.sync_pattern_registry_to_pipeline();
    }

    /// Advance crossfade counter by one tick; call once per Event::Tick.
    /// Also drains any pending commands from the WebSocket control server.
    pub fn tick_transition(&mut self) {
        if self.transition_frames_left > 0 {
            self.transition_frames_left -= 1;
        }
        // drain preview updates from pipeline background thread
        if let Some(ref rx) = self.preview_rx {
            while let Ok(upd) = rx.try_recv() {
                if upd.fps > 0.0 {
                    self.stats.actual_fps = upd.fps;
                }
                self.stats.output_latency_ms = upd.output_latency_ms;
                self.preview_width = upd.width;
                self.preview_height = upd.height;
                // feed frame to recorder if active
                if let Some(ref mut rec) = self.recorder {
                    let tf = privacy_common::frame::TransformedFrame {
                        pixels: upd.pixels.clone(),
                        width: upd.width,
                        height: upd.height,
                        timestamp: chrono::Utc::now(),
                    };
                    let _ = rec.write_frame(&tf);
                }
                self.tx_preview_pixels = Some(upd.pixels);
            }
        }
        // update adaptive quality stats and capture errors from pipeline SharedState
        if let Some(ps) = self.pipeline_shared_state.clone() {
            use std::sync::atomic::Ordering;
            self.stats.capture_latency_ms = ps.capture_latency_ms.load(Ordering::Relaxed) as f32;
            self.stats.ocr_latency_ms = ps.ocr_latency_ms.load(Ordering::Relaxed) as f32;
            self.stats.transform_latency_ms =
                ps.transform_latency_ms.load(Ordering::Relaxed) as f32;
            self.stats.quality_scale = *ps.quality_scale.lock().unwrap();
            self.stats.ocr_grid_cols = ps.target_grid_cols.load(Ordering::Relaxed);
            self.stats.ocr_grid_rows = ps.target_grid_rows.load(Ordering::Relaxed);
            self.stats.dropped_frames = ps.dropped_frames.load(Ordering::Relaxed);
            self.stats_overlay.total_regions_this_frame =
                ps.last_regions_count.load(Ordering::Relaxed);
            self.stats_overlay.peak_regions = ps.peak_regions_count.load(Ordering::Relaxed);
            if let Ok(mut raw) = ps.latest_raw_preview.try_lock() {
                if let Some(frame) = raw.take() {
                    self.preview_width = frame.width;
                    self.preview_height = frame.height;
                    self.raw_preview_pixels = Some(frame.pixels);
                }
            }
            if let Ok(mut queue) = ps.detection_events.try_lock() {
                let events: Vec<_> = queue.drain(..).collect();
                drop(queue);
                if !events.is_empty() {
                    self.control_state
                        .redaction_count
                        .fetch_add(events.len() as u64, std::sync::atomic::Ordering::Relaxed);
                }
                for event in events {
                    self.heatmap
                        .record_hit(&event.bounds, self.preview_width, self.preview_height);
                    self.push_log(LogEntry {
                        timestamp: event.timestamp,
                        pattern_name: event.pattern_name,
                        severity: event.severity,
                        snippet: event.snippet,
                        bounds: Some(event.bounds),
                    });
                }
            }
            self.control_state.actual_fps_milli.store(
                (self.stats.actual_fps.max(0.0) * 1000.0) as u32,
                Ordering::Relaxed,
            );
            self.control_state
                .dropped_frames
                .store(self.stats.dropped_frames, Ordering::Relaxed);
            if let Ok(mut err) = ps.capture_error.try_lock() {
                if err.is_some() {
                    self.capture_error = err.take();
                }
            }
        }
        let total_latency = self.stats.capture_latency_ms
            + self.stats.ocr_latency_ms
            + self.stats.transform_latency_ms
            + self.stats.output_latency_ms;
        if total_latency > 0.0 {
            self.record_latency(total_latency as u64);
        }
        self.tick_foreground_profile();
        // apply pending pause/resume from control server
        if let Ok(mut g) = self.control_state.pending_pause.try_lock() {
            if let Some(paused) = g.take() {
                log::info!("control pending pause consumed -> paused={paused}");
                self.pipeline_state = if paused {
                    PipelineState::Paused
                } else {
                    PipelineState::Running
                };
                self.control_state
                    .paused
                    .store(paused, std::sync::atomic::Ordering::SeqCst);
                if let Some(ref ps) = self.pipeline_shared_state {
                    ps.paused.store(paused, std::sync::atomic::Ordering::SeqCst);
                }
            }
        }
        // apply pending mode switch from control server (with crossfade)
        if let Ok(mut g) = self.control_state.pending_mode.try_lock() {
            if let Some(mode) = g.take() {
                log::info!("control pending mode consumed -> {:?}", mode);
                self.prev_tx_preview_pixels = self.tx_preview_pixels.clone();
                self.transition_frames_left = 10;
                self.transform_mode = mode;
                *self.control_state.transform_mode.lock().unwrap() = mode;
                if let Some(ref ps) = self.pipeline_shared_state {
                    ps.begin_mode_transition(mode);
                }
            }
        }
    }

    /// Returns blended transformed pixels during transition, current pixels otherwise.
    pub fn blended_tx_pixels(&self) -> Option<Vec<u8>> {
        if self.transition_frames_left == 0 {
            return self.tx_preview_pixels.clone();
        }
        let old_w = self.transition_frames_left as f32 / 10.0; // old weight
        let new_w = 1.0 - old_w;
        match (&self.prev_tx_preview_pixels, &self.tx_preview_pixels) {
            (Some(prev), Some(curr)) if prev.len() == curr.len() => {
                let blended = prev
                    .iter()
                    .zip(curr.iter())
                    .map(|(&p, &c)| (p as f32 * old_w + c as f32 * new_w) as u8)
                    .collect();
                Some(blended)
            }
            _ => self.tx_preview_pixels.clone(),
        }
    }

    pub fn adjust_intensity(&mut self, delta: f32) {
        self.transform_intensity = (self.transform_intensity + delta).clamp(0.0, 1.0);
        log::info!(
            "intensity adjust delta={delta:.2} -> {:.2}",
            self.transform_intensity
        );
        *self.control_state.intensity.lock().unwrap() = self.transform_intensity;
        if let Some(ref ps) = self.pipeline_shared_state {
            *ps.transform_intensity.lock().unwrap() = self.transform_intensity;
        }
    }

    #[allow(dead_code)]
    pub fn push_log(&mut self, entry: LogEntry) {
        if self.log_entries.len() >= 50 {
            self.log_entries.remove(0);
        }
        if self.first_detection_flash.is_none() {
            self.first_detection_flash = Some(Instant::now()); // flash on first detection
        }
        self.stats_overlay
            .record(&entry.pattern_name, entry.bounds.clone());
        self.log_entries.push(entry);
    }

    /// Switch to profile at 1-based index (from `1-9` keybindings).
    pub fn switch_profile(&mut self, idx: usize) {
        if idx == 0 || idx > self.profile_names.len() {
            return;
        }
        let name = self.profile_names[idx - 1].clone();
        log::info!("switching to profile: {name}");
        if let Ok(cfg) = AppConfig::load() {
            if let Some(profile) = cfg.profiles.get(&name) {
                self.transform_mode = match profile.transform_mode.as_str() {
                    "cartoon" => privacy_common::transform::TransformMode::Cartoon,
                    "ascii" => privacy_common::transform::TransformMode::Ascii,
                    "pixelate" => privacy_common::transform::TransformMode::Pixelate,
                    "neural" => privacy_common::transform::TransformMode::Neural,
                    _ => privacy_common::transform::TransformMode::Blur,
                };
                self.transform_intensity = profile.intensity.clamp(0.0, 1.0);
                log::info!(
                    "profile applied name={} mode={:?} intensity={:.2}",
                    name,
                    self.transform_mode,
                    self.transform_intensity
                );
                *self.control_state.transform_mode.lock().unwrap() = self.transform_mode;
                *self.control_state.intensity.lock().unwrap() = self.transform_intensity;
                if let Some(ref ps) = self.pipeline_shared_state {
                    ps.begin_mode_transition(self.transform_mode);
                    *ps.transform_intensity.lock().unwrap() = self.transform_intensity;
                }
            }
        }
        self.active_profile = Some(name);
    }

    #[allow(dead_code)]
    pub fn record_latency(&mut self, ms: u64) {
        if self.latency_history.len() >= LATENCY_HISTORY_LEN {
            self.latency_history.pop_front();
        }
        self.latency_history.push_back(ms);
    }
}

impl Default for App {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crossbeam_channel::bounded;
    use privacy_common::detection::Severity;
    use privacy_core::{
        detection::default_patterns::default_registry,
        pipeline_runner::{PipelineDetectionEvent, SharedState},
    };
    use std::sync::atomic::Ordering;

    fn preview_update(pixel: u8, output_latency_ms: f32) -> PreviewUpdate {
        PreviewUpdate {
            pixels: vec![pixel, pixel, pixel, 255],
            width: 1,
            height: 1,
            fps: 30.0,
            output_latency_ms,
        }
    }

    #[test]
    fn tick_transition_uses_true_raw_preview() {
        let mut app = App::new();
        let state = SharedState::new(default_registry());
        *state.latest_raw_preview.lock().unwrap() = Some(privacy_common::frame::RawFrame {
            pixels: vec![10, 11, 12, 255],
            width: 1,
            height: 1,
            timestamp: chrono::Utc::now(),
        });
        app.pipeline_shared_state = Some(state.clone());
        let (tx, rx) = bounded(1);
        tx.send(preview_update(20, 2.0)).unwrap();
        app.preview_rx = Some(rx);

        app.tick_transition();

        assert_eq!(app.tx_preview_pixels, Some(vec![20, 20, 20, 255]));
        assert_eq!(app.raw_preview_pixels, Some(vec![10, 11, 12, 255]));
        assert!(state.latest_raw_preview.lock().unwrap().is_none());
    }

    #[test]
    fn tick_transition_drains_detection_events_and_updates_overlay_state() {
        let mut app = App::new();
        app.preview_width = 100;
        app.preview_height = 100;
        let state = SharedState::new(default_registry());
        state.last_regions_count.store(2, Ordering::Relaxed);
        state.peak_regions_count.store(5, Ordering::Relaxed);
        {
            let mut q = state.detection_events.lock().unwrap();
            q.push_back(PipelineDetectionEvent {
                timestamp: chrono::Utc::now(),
                pattern_name: "github_token".to_string(),
                severity: Severity::High,
                snippet: "ghp_***".to_string(),
                bounds: Rect {
                    x: 10,
                    y: 10,
                    width: 20,
                    height: 10,
                },
            });
        }
        app.pipeline_shared_state = Some(state);

        app.tick_transition();

        assert_eq!(app.log_entries.len(), 1);
        assert_eq!(app.stats_overlay.total_regions_this_frame, 2);
        assert_eq!(app.stats_overlay.peak_regions, 5);
        assert!(app.heatmap.cells.values().any(|hits| !hits.is_empty()));
    }

    #[test]
    fn tick_transition_records_total_latency_samples() {
        let mut app = App::new();
        let state = SharedState::new(default_registry());
        state.capture_latency_ms.store(10, Ordering::Relaxed);
        state.ocr_latency_ms.store(5, Ordering::Relaxed);
        state.transform_latency_ms.store(6, Ordering::Relaxed);
        app.pipeline_shared_state = Some(state);
        let (tx, rx) = bounded(1);
        tx.send(preview_update(30, 4.0)).unwrap();
        app.preview_rx = Some(rx);

        app.tick_transition();

        assert_eq!(app.stats.capture_latency_ms, 10.0);
        assert_eq!(app.stats.ocr_latency_ms, 5.0);
        assert_eq!(app.stats.transform_latency_ms, 6.0);
        assert_eq!(app.stats.output_latency_ms, 4.0);
        assert_eq!(app.latency_history.back().copied(), Some(25));
    }
}
