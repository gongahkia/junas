//! TUI rendering: 4-zone layout with top bar, left/right previews, and bottom panel.

pub mod braille;
pub mod detection_log;
pub mod stats_bar;

use crate::app::{App, PipelineState};
use ratatui::{
    layout::{Constraint, Direction, Layout},
    style::Color,
    Frame,
};

pub fn render(frame: &mut Frame, app: &App) {
    let area = frame.area();

    // ── vertical split: top bar | content | bottom panel ─────────────────────
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),  // top stats bar
            Constraint::Min(0),     // main content
            Constraint::Length(6),  // bottom panel
        ])
        .split(area);

    // ── top bar ──────────────────────────────────────────────────────────────
    stats_bar::render(frame, app, rows[0]);

    // ── content: left (raw) | right (transformed) ───────────────────────────
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(rows[1]);

    // left: raw capture preview
    braille::render_preview(
        frame,
        app.raw_preview_pixels.as_deref(),
        app.preview_width,
        app.preview_height,
        "Raw Capture",
        Color::DarkGray,
        cols[0],
    );

    // right: transformed output preview
    braille::render_preview(
        frame,
        app.tx_preview_pixels.as_deref(),
        app.preview_width,
        app.preview_height,
        "Transformed",
        Color::Blue,
        cols[1],
    );

    // ── bottom panel ─────────────────────────────────────────────────────────
    detection_log::render(frame, app, rows[2]);
}
