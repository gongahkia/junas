//! Latency sparkline: last 120 frames processing time.
//! Spikes above 33ms (30fps budget) are rendered in red.

use crate::app::App;
use ratatui::{
    layout::Rect,
    style::{Color, Style},
    symbols,
    widgets::{Block, Borders, Sparkline},
    Frame,
};

const FRAME_BUDGET_MS: u64 = 33;

pub fn render(frame: &mut Frame, app: &App, area: Rect) {
    let data: Vec<u64> = app.latency_history.iter().copied().collect();
    let max = data.iter().copied().max().unwrap_or(FRAME_BUDGET_MS).max(FRAME_BUDGET_MS);
    // color red if any recent sample exceeds budget
    let over_budget = data.iter().any(|&v| v > FRAME_BUDGET_MS);
    let bar_color = if over_budget { Color::Red } else { Color::Green };

    let sparkline = Sparkline::default()
        .block(
            Block::default()
                .title(format!(" Latency (last {}f  max:{}ms  budget:{}ms) ", data.len(), max, FRAME_BUDGET_MS))
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray)),
        )
        .data(&data)
        .max(max)
        .style(Style::default().fg(bar_color))
        .bar_set(symbols::bar::NINE_LEVELS);
    frame.render_widget(sparkline, area);
}
