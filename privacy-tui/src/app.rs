//! Application state shared across all TUI components.

use privacy_common::transform::TransformMode;
use privacy_core::detection::{
    default_patterns::default_registry,
    patterns::PatternRegistry,
    pii_patterns::pii_patterns,
};
use std::time::Instant;

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
    pub preview_width: u32,
    pub preview_height: u32,
    /// Currently selected capture window id (None = full screen).
    pub selected_window_id: Option<u64>,
    pub window_selector: crate::ui::window_selector::WindowSelectorState,
    pub pattern_manager: crate::ui::pattern_manager::PatternManagerState,
    pub pattern_registry: PatternRegistry,
}

#[derive(Debug, Clone)]
pub struct LogEntry {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub pattern_name: String,
    pub severity: privacy_common::detection::Severity,
    pub snippet: String,
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
        }
    }

    pub fn toggle_pipeline(&mut self) {
        self.pipeline_state = match self.pipeline_state {
            PipelineState::Running => PipelineState::Paused,
            PipelineState::Paused => PipelineState::Running,
        };
    }

    pub fn cycle_transform(&mut self) {
        self.transform_mode = self.transform_mode.next();
    }

    pub fn adjust_intensity(&mut self, delta: f32) {
        self.transform_intensity = (self.transform_intensity + delta).clamp(0.0, 1.0);
    }

    pub fn push_log(&mut self, entry: LogEntry) {
        if self.log_entries.len() >= 50 {
            self.log_entries.remove(0);
        }
        self.log_entries.push(entry);
    }
}

impl Default for App {
    fn default() -> Self { Self::new() }
}
