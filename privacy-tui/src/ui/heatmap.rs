//! Sensitivity heatmap overlay: `h` key toggles.
//! Shows detection frequency per screen region over the last 60s.
//! Red = frequent matches, Blue = never matched.

use crate::app::App;
use ratatui::{
    layout::Rect,
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

/// Render the heatmap overlay inside `area` (replaces raw preview content when enabled).
pub fn render(frame: &mut Frame, app: &mut App, area: Rect) {
    let (gx, gy) = crate::app::HeatmapState::grid_dims();
    let inner = {
        let block = Block::default()
            .title(" Heatmap (60s) — red=frequent blue=never  [h=close] ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Yellow));
        let inner = block.inner(area);
        frame.render_widget(block, area);
        inner
    };

    if inner.width == 0 || inner.height == 0 { return; }

    let cell_w = inner.width as f32 / gx as f32;
    let cell_h = inner.height as f32 / gy as f32;
    // build text lines for the grid
    let mut lines: Vec<Line<'static>> = Vec::with_capacity(inner.height as usize);
    for row in 0..inner.height {
        let mut spans = Vec::new();
        for col in 0..inner.width {
            let gx_idx = (col as f32 / cell_w) as u8;
            let gy_idx = (row as f32 / cell_h) as u8;
            let heat = app.heatmap.heat(gx_idx.min(gx - 1), gy_idx.min(gy - 1));
            let color = heat_to_color(heat);
            spans.push(Span::styled("█", Style::default().fg(color)));
        }
        lines.push(Line::from(spans));
    }
    let para = Paragraph::new(lines);
    frame.render_widget(para, inner);
}

/// Map heat [0.0-1.0] to a color: blue → cyan → green → yellow → red.
fn heat_to_color(heat: f32) -> Color {
    if heat < 0.05 {
        Color::Blue
    } else if heat < 0.25 {
        Color::Cyan
    } else if heat < 0.5 {
        Color::Green
    } else if heat < 0.75 {
        Color::Yellow
    } else {
        Color::Red
    }
}
