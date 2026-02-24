//! Bottom panel: scrollable detection log (last 50 entries) + keybind help.

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

    // ── scrollable detection log (last 50 entries, most recent first) ─────────
    let log_height = cols[0].height.saturating_sub(2) as usize; // subtract border rows
    let items: Vec<ListItem> = app
        .log_entries
        .iter()
        .rev()
        .take(50)
        .take(log_height)
        .map(|e| {
            let sev_color = match e.severity {
                Severity::High => Color::Red,
                Severity::Medium => Color::Yellow,
                Severity::Low => Color::Cyan,
            };
            let sev_label = match e.severity {
                Severity::High => "HIGH  ",
                Severity::Medium => "MED   ",
                Severity::Low => "LOW   ",
            };
            let ts = e.timestamp.format("%H:%M:%S").to_string();
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!("{ts} "),
                    Style::default().fg(Color::DarkGray),
                ),
                Span::styled(
                    sev_label,
                    Style::default()
                        .fg(sev_color)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(
                    format!("{:<16} ", e.pattern_name),
                    Style::default().fg(Color::White),
                ),
                Span::styled(
                    e.snippet.clone(),
                    Style::default().fg(Color::DarkGray),
                ),
            ]))
        })
        .collect();

    let log_widget = List::new(items).block(
        Block::default()
            .title(format!(" Detections ({}) ", app.log_entries.len()))
            .borders(Borders::ALL),
    );
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
