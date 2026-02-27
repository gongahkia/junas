//! Pattern manager overlay: `p` opens, Space toggles enabled, Esc closes.

use privacy_core::detection::patterns::PatternRegistry;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState},
    Frame,
};

pub struct PatternManagerState {
    pub open: bool,
    pub list_state: ListState,
}

impl PatternManagerState {
    pub fn new() -> Self {
        Self {
            open: false,
            list_state: ListState::default(),
        }
    }

    pub fn open(&mut self) {
        self.list_state.select(Some(0));
        self.open = true;
    }

    pub fn close(&mut self) {
        self.open = false;
    }

    pub fn move_up(&mut self, len: usize) {
        if len == 0 {
            return;
        }
        let i = self.list_state.selected().unwrap_or(0);
        self.list_state
            .select(Some(if i == 0 { len - 1 } else { i - 1 }));
    }

    pub fn move_down(&mut self, len: usize) {
        if len == 0 {
            return;
        }
        let i = self.list_state.selected().unwrap_or(0);
        self.list_state.select(Some((i + 1) % len));
    }

    pub fn toggle(&self, registry: &mut PatternRegistry) {
        if let Some(i) = self.list_state.selected() {
            if let Some(p) = registry.patterns.get_mut(i) {
                p.enabled = !p.enabled;
            }
        }
    }

    /// Cycle severity of the selected pattern (Low→Medium→High→Low).
    pub fn cycle_severity(&self, registry: &mut PatternRegistry) {
        if let Some(i) = self.list_state.selected() {
            registry.cycle_severity(i);
        }
    }
}

impl Default for PatternManagerState {
    fn default() -> Self {
        Self::new()
    }
}

pub fn render(frame: &mut Frame, state: &mut PatternManagerState, registry: &PatternRegistry) {
    if !state.open {
        return;
    }

    let area = frame.area();
    let popup = centered_rect(70, 80, area);

    let items: Vec<ListItem> = registry
        .patterns
        .iter()
        .map(|p| {
            let toggle = if p.enabled { "✓" } else { "✗" };
            let toggle_color = if p.enabled { Color::Green } else { Color::Red };
            let sev_color = match p.severity {
                privacy_common::detection::Severity::High => Color::Red,
                privacy_common::detection::Severity::Medium => Color::Yellow,
                privacy_common::detection::Severity::Low => Color::Cyan,
            };
            let regex_preview: String = p.regex.as_str().chars().take(30).collect();
            let regex_preview = if p.regex.as_str().len() > 30 {
                format!("{}…", regex_preview)
            } else {
                regex_preview
            };
            let cat_abbr = match p.category {
                privacy_common::detection::PatternCategory::EnvVar => "ENV",
                privacy_common::detection::PatternCategory::Token => "TOK",
                privacy_common::detection::PatternCategory::Password => "PWD",
                privacy_common::detection::PatternCategory::ApiKey => "API",
                privacy_common::detection::PatternCategory::Pii => "PII",
            };
            ListItem::new(Line::from(vec![
                Span::styled(format!(" {} ", toggle), Style::default().fg(toggle_color)),
                Span::styled(
                    format!("{:<20}", p.name),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(
                    format!("{:<4}", cat_abbr),
                    Style::default().fg(Color::Magenta),
                ),
                Span::raw(" "),
                Span::styled(
                    format!("{:<6}", format!("{:?}", p.severity)),
                    Style::default().fg(sev_color),
                ),
                Span::styled(regex_preview, Style::default().fg(Color::DarkGray)),
            ]))
        })
        .collect();

    let list = List::new(items)
        .block(
            Block::default()
                .title(" Pattern Manager (Space=toggle  ]=severity  j/k=nav  Esc=close) ")
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Magenta)),
        )
        .highlight_style(
            Style::default()
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        );

    frame.render_stateful_widget(list, popup, &mut state.list_state);
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
