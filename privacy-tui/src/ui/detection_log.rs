//! Bottom panel: detection log + keybind help.

use crate::app::App;
use privacy_common::detection::Severity;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame,
};

pub fn render(frame: &mut Frame, app: &App, area: Rect) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Min(0), Constraint::Length(36)])
        .split(area);

    // ── detection log ────────────────────────────────────────────────────────
    let items: Vec<ListItem> = app.log_entries.iter().rev().take(5).map(|e| {
        let sev_color = match e.severity {
            Severity::High => Color::Red,
            Severity::Medium => Color::Yellow,
            Severity::Low => Color::Cyan,
        };
        let ts = e.timestamp.format("%H:%M:%S").to_string();
        ListItem::new(Line::from(vec![
            Span::styled(format!("{ts} "), Style::default().fg(Color::DarkGray)),
            Span::styled(format!("[{:?}] ", e.severity), Style::default().fg(sev_color)),
            Span::raw(format!("{} — {}", e.pattern_name, e.snippet)),
        ]))
    }).collect();

    let log_widget = List::new(items)
        .block(Block::default().title(" Detections ").borders(Borders::ALL));
    frame.render_widget(log_widget, cols[0]);

    // ── keybind help ─────────────────────────────────────────────────────────
    let help = Paragraph::new(vec![
        Line::from("Space  pause/resume"),
        Line::from("t      cycle transform"),
        Line::from("+/-    intensity"),
        Line::from("w      window picker"),
        Line::from("p      pattern manager"),
        Line::from("q      quit"),
    ])
    .block(Block::default().title(" Keys ").borders(Borders::ALL));
    frame.render_widget(help, cols[1]);
}
