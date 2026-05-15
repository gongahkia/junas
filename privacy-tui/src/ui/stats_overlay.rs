//! Detection statistics overlay: `s` key toggles.
//! Shows per-pattern hit counts, regions/frame, busiest zones.

use crate::app::App;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame,
};

pub fn render(frame: &mut Frame, app: &App, _area: Rect) {
    if !app.stats_overlay.open {
        return;
    }
    let full = frame.area();
    let popup = centered_rect(60, 70, full);

    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(0), Constraint::Length(4)])
        .split(popup);

    let mut entries: Vec<(&String, u64)> = app
        .stats_overlay
        .pattern_stats
        .iter()
        .map(|(k, v)| (k, v.total_hits))
        .collect();
    entries.sort_by(|a, b| b.1.cmp(&a.1));

    let items: Vec<ListItem> = entries
        .iter()
        .map(|(name, hits)| {
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!("{:<24}", name),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(
                    format!("{:>6} hits", hits),
                    Style::default().fg(Color::Cyan),
                ),
            ]))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .title(" Detection Stats (s=close) ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Cyan)),
    );
    frame.render_widget(list, rows[0]);

    let summary = Paragraph::new(vec![Line::from(format!(
        " total patterns with hits: {}  peak regions/frame: {}",
        app.stats_overlay.pattern_stats.len(),
        app.stats_overlay.peak_regions
    ))])
    .block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray)),
    );
    frame.render_widget(summary, rows[1]);
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let vert = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - percent_y) / 2),
            Constraint::Percentage(percent_y),
            Constraint::Percentage((100 - percent_y) / 2),
        ])
        .split(r);
    let horiz = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - percent_x) / 2),
            Constraint::Percentage(percent_x),
            Constraint::Percentage((100 - percent_x) / 2),
        ])
        .split(vert[1]);
    horiz[1]
}
