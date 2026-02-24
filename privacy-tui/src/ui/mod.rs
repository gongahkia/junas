//! TUI rendering: 4-zone layout with top bar, left/right previews, and bottom panel.

pub mod braille;
pub mod detection_log;
pub mod stats_bar;
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
            Constraint::Length(6),
        ])
        .split(area);

    stats_bar::render(frame, app, rows[0]);

    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(rows[1]);

    braille::render_preview(
        frame,
        app.raw_preview_pixels.as_deref(),
        app.preview_width,
        app.preview_height,
        "Raw Capture",
        Color::DarkGray,
        cols[0],
    );

    braille::render_preview(
        frame,
        app.tx_preview_pixels.as_deref(),
        app.preview_width,
        app.preview_height,
        "Transformed",
        Color::Blue,
        cols[1],
    );

    detection_log::render(frame, app, rows[2]);

    window_selector::render(frame, &mut app.window_selector);
}
