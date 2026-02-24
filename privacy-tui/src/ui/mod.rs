//! TUI rendering: 4-zone layout with top bar, left/right previews, and bottom panel.

pub mod braille;
pub mod detection_log;
pub mod heatmap;
pub mod latency_graph;
pub mod pattern_manager;
pub mod stats_bar;
pub mod stats_overlay;
pub mod window_selector;

use crate::app::App;
use ratatui::{
    layout::{Constraint, Direction, Layout},
    style::Color,
    Frame,
};

pub fn render(frame: &mut Frame, app: &mut App) {
    let area = frame.area();

    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Min(0),
            Constraint::Length(4),  // latency sparkline
            Constraint::Length(6),
        ])
        .split(area);

    stats_bar::render(frame, app, rows[0]);

    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(rows[1]);


    if app.heatmap.enabled {
        heatmap::render(frame, app, cols[0]);
    } else {
        // flash raw-preview border red on first detection (2s)
        let raw_border = if app.first_detection_flash
            .map(|t| t.elapsed().as_secs() < 2)
            .unwrap_or(false)
        { Color::Red } else { Color::DarkGray };
        braille::render_preview(
            frame,
            app.raw_preview_pixels.as_deref(),
            app.preview_width,
            app.preview_height,
            "Raw Capture",
            raw_border,
            cols[0],
        );
    }

    braille::render_preview(
        frame,
        app.tx_preview_pixels.as_deref(),
        app.preview_width,
        app.preview_height,
        "Transformed",
        Color::Blue,
        cols[1],
    );

    latency_graph::render(frame, app, rows[2]);
    detection_log::render(frame, app, rows[3]);

    window_selector::render(frame, &mut app.window_selector);
    pattern_manager::render(frame, &mut app.pattern_manager, &app.pattern_registry);
    stats_overlay::render(frame, app, rows[3]);
}
