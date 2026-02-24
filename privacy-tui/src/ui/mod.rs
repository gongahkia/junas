//! TUI rendering: 4-zone layout with top bar, left/right previews, and bottom panel.

pub mod braille;
pub mod detection_log;
pub mod stats_bar;

use crate::app::{App, PipelineState};
use ratatui::{
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

pub fn render(frame: &mut Frame, app: &App) {
    let area = frame.area();

    // ── vertical split: top bar | content | bottom bar ───────────────────────
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),  // top bar
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

    // left: raw capture preview (placeholder braille widget)
    let raw_block = Block::default()
        .title(" Raw Capture ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    frame.render_widget(raw_block, cols[0]);

    // right: transformed output preview
    let tx_block = Block::default()
        .title(" Transformed ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Blue));
    frame.render_widget(tx_block, cols[1]);

    // ── bottom panel ─────────────────────────────────────────────────────────
    detection_log::render(frame, app, rows[2]);
}
