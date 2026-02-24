//! Application state shared across all TUI components.

use crate::control_server::ControlState;
use privacy_common::{frame::Rect, transform::TransformMode};
use privacy_core::detection::{
    default_patterns::default_registry,
    patterns::PatternRegistry,
    pii_patterns::pii_patterns,
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
#[derive(Debug, Clone, Default)]
pub struct PipelineStats {
    pub actual_fps: f32,
    pub capture_latency_ms: f32,
    pub ocr_latency_ms: f32,
    pub transform_latency_ms: f32,
    pub output_latency_ms: f32,
    pub dropped_frames: u64,
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
        Self { enabled: false, cells: HashMap::new() }
    }

    /// Record a detection hit for the given rect (frame coords).
    pub fn record_hit(&mut self, r: &Rect, frame_w: u32, frame_h: u32) {
        if frame_w == 0 || frame_h == 0 { return; }
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
        while entry.front().map(|t| now.duration_since(*t) > HEATMAP_WINDOW).unwrap_or(false) {
            entry.pop_front();
        }
        // cap at 30 hits → 1.0
        (entry.len() as f32 / 30.0).min(1.0)
    }

    pub fn grid_dims() -> (u8, u8) { (HEATMAP_GRID_X, HEATMAP_GRID_Y) }
}

impl Default for HeatmapState {
    fn default() -> Self { Self::new() }
}

/// Per-pattern detection statistics.
#[derive(Debug, Clone, Default)]
pub struct PatternStats {
    pub name: String,
    pub total_hits: u64,
    pub last_region: Option<Rect>,
}

/// Detection statistics overlay state.
pub struct StatsOverlayState {
    pub open: bool,
    pub pattern_stats: HashMap<String, PatternStats>,
    pub total_regions_this_frame: u32,
    pub peak_regions: u32,
}

impl StatsOverlayState {
    pub fn new() -> Self {
        Self { open: false, pattern_stats: HashMap::new(), total_regions_this_frame: 0, peak_regions: 0 }
    }

    pub fn record(&mut self, pattern_name: &str, bounds: Option<Rect>) {
        let s = self.pattern_stats.entry(pattern_name.to_string()).or_insert_with(|| PatternStats { name: pattern_name.to_string(), ..Default::default() });
        s.total_hits += 1;
        if let Some(b) = bounds { s.last_region = Some(b); }
    }
}

impl Default for StatsOverlayState {
    fn default() -> Self { Self::new() }
}

/// Latency history for sparkline (last 120 frames, ms per frame).
pub const LATENCY_HISTORY_LEN: usize = 120;

pub struct App {
    pub running: bool,
    pub pipeline_state: PipelineState,
    pub transform_mode: TransformMode,
    pub transform_intensity: f32,
    pub stats: PipelineStats,
    pub log_entries: Vec<LogEntry>,
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
    /// Shared state with the WebSocket control server.
    pub control_state: Arc<ControlState>,
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
        Self {
            running: true,
            pipeline_state: PipelineState::Running,
            transform_mode: TransformMode::default(),
            transform_intensity: 1.0,
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
            window_selector: crate::ui::window_selector::WindowSelectorState::new(),
            pattern_manager: crate::ui::pattern_manager::PatternManagerState::new(),
            pattern_registry: {
                let mut r = default_registry();
                r.patterns.extend(pii_patterns());
                r
            },
            heatmap: HeatmapState::new(),
            stats_overlay: StatsOverlayState::new(),
            latency_history: VecDeque::with_capacity(LATENCY_HISTORY_LEN),
            first_detection_flash: None,
            recording_started_at: None,
            active_profile: None,
            profile_names: Vec::new(),
            control_state: ControlState::new(TransformMode::default(), 1.0),
        }
    }

    pub fn toggle_pipeline(&mut self) {
        self.pipeline_state = match self.pipeline_state {
            PipelineState::Running => PipelineState::Paused,
            PipelineState::Paused => PipelineState::Running,
        };
    }

    pub fn cycle_transform(&mut self) {
        self.prev_tx_preview_pixels = self.tx_preview_pixels.clone(); // snapshot for crossfade
        self.transition_frames_left = 10;
        self.transform_mode = self.transform_mode.next();
        *self.control_state.transform_mode.lock().unwrap() = self.transform_mode; // sync
    }

    /// Advance crossfade counter by one tick; call once per Event::Tick.
    /// Also drains any pending commands from the WebSocket control server.
    pub fn tick_transition(&mut self) {
        if self.transition_frames_left > 0 {
            self.transition_frames_left -= 1;
        }
        // apply pending pause/resume from control server
        if let Ok(mut g) = self.control_state.pending_pause.try_lock() {
            if let Some(paused) = g.take() {
                self.pipeline_state = if paused {
                    PipelineState::Paused
                } else {
                    PipelineState::Running
                };
            }
        }
        // apply pending mode switch from control server (with crossfade)
        if let Ok(mut g) = self.control_state.pending_mode.try_lock() {
            if let Some(mode) = g.take() {
                self.prev_tx_preview_pixels = self.tx_preview_pixels.clone();
                self.transition_frames_left = 10;
                self.transform_mode = mode;
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
                let blended = prev.iter().zip(curr.iter())
                    .map(|(&p, &c)| (p as f32 * old_w + c as f32 * new_w) as u8)
                    .collect();
                Some(blended)
            }
            _ => self.tx_preview_pixels.clone(),
        }
    }

    pub fn adjust_intensity(&mut self, delta: f32) {
        self.transform_intensity = (self.transform_intensity + delta).clamp(0.0, 1.0);
        *self.control_state.intensity.lock().unwrap() = self.transform_intensity; // sync
    }

    pub fn push_log(&mut self, entry: LogEntry) {
        if self.log_entries.len() >= 50 {
            self.log_entries.remove(0);
        }
        if self.first_detection_flash.is_none() {
            self.first_detection_flash = Some(Instant::now()); // flash on first detection
        }
        self.stats_overlay.record(&entry.pattern_name, entry.bounds.clone());
        self.log_entries.push(entry);
    }

    /// Switch to profile at 1-based index (from `1-9` keybindings).
    pub fn switch_profile(&mut self, idx: usize) {
        if idx == 0 || idx > self.profile_names.len() { return; }
        let name = self.profile_names[idx - 1].clone();
        log::info!("switching to profile: {name}");
        self.active_profile = Some(name);
    }

    pub fn record_latency(&mut self, ms: u64) {
        if self.latency_history.len() >= LATENCY_HISTORY_LEN {
            self.latency_history.pop_front();
        }
        self.latency_history.push_back(ms);
    }
}

impl Default for App {
    fn default() -> Self { Self::new() }
}
