//! Full keybinding help overlay: `?` key toggles.

use crate::app::App;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

pub fn render(frame: &mut Frame, app: &App, _area: Rect) {
    if !app.help_open { return; }
    let full = frame.area();
    let popup = centered_rect(50, 80, full);
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(0), Constraint::Length(1)])
        .split(popup);
    let keys: &[(&str, &str)] = &[
        ("w",     "window picker"),
        ("p",     "pattern manager"),
        ("Space", "pause / resume"),
        ("t",     "cycle transform mode"),
        ("+/-",   "adjust intensity"),
        ("h",     "toggle heatmap"),
        ("s",     "toggle stats overlay"),
        ("r",     "start / stop recording"),
        ("e",     "export session log"),
        ("f",     "mark last detection as false positive"),
        ("1-9",   "switch profile"),
        ("j / k", "scroll detection log (older / newer)"),
        ("?",     "toggle this help"),
        ("q",     "quit"),
    ];
    let items: Vec<Line> = keys.iter().map(|(key, desc)| {
        Line::from(vec![
            Span::styled(format!("  {:<8}", key), Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled(format!(" {}", desc), Style::default().fg(Color::White)),
        ])
    }).collect();
    let para = Paragraph::new(items)
        .block(Block::default()
            .title(" Keybindings  [any key to close] ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Cyan)));
    frame.render_widget(para, rows[0]);
    let hint = Paragraph::new(Line::from(Span::styled(
        " press any key to dismiss ",
        Style::default().fg(Color::DarkGray),
    )));
    frame.render_widget(hint, rows[1]);
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
