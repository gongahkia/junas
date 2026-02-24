//! Window selector overlay: press `w` to list windows, j/k to navigate, Enter to select.

use privacy_common::frame::WindowInfo;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState},
    Frame,
};

pub struct WindowSelectorState {
    pub open: bool,
    pub windows: Vec<WindowInfo>,
    pub list_state: ListState,
}

impl WindowSelectorState {
    pub fn new() -> Self {
        Self { open: false, windows: vec![], list_state: ListState::default() }
    }

    pub fn open(&mut self, windows: Vec<WindowInfo>) {
        self.windows = windows;
        self.list_state.select(Some(0));
        self.open = true;
    }

    pub fn close(&mut self) { self.open = false; }

    pub fn move_up(&mut self) {
        if self.windows.is_empty() { return; }
        let i = self.list_state.selected().unwrap_or(0);
        self.list_state.select(Some(if i == 0 { self.windows.len() - 1 } else { i - 1 }));
    }

    pub fn move_down(&mut self) {
        if self.windows.is_empty() { return; }
        let i = self.list_state.selected().unwrap_or(0);
        self.list_state.select(Some((i + 1) % self.windows.len()));
    }

    pub fn selected_window(&self) -> Option<&WindowInfo> {
        self.list_state.selected().and_then(|i| self.windows.get(i))
    }
}

impl Default for WindowSelectorState {
    fn default() -> Self { Self::new() }
}

/// Render the window selector overlay centred in the terminal.
pub fn render(frame: &mut Frame, state: &mut WindowSelectorState) {
    if !state.open { return; }

    let area = frame.area();
    let popup = centered_rect(60, 70, area);

    let items: Vec<ListItem> = state.windows.iter().map(|w| {
        ListItem::new(Line::from(vec![
            Span::styled(
                format!("{:>6}  ", w.id),
                Style::default().fg(Color::DarkGray),
            ),
            Span::raw(w.title.clone()),
            Span::styled(
                format!("  {}×{}", w.bounds.width, w.bounds.height),
                Style::default().fg(Color::DarkGray),
            ),
        ]))
    }).collect();

    let list = List::new(items)
        .block(
            Block::default()
                .title(" Select Window (Enter=select  Esc=cancel) ")
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Yellow)),
        )
        .highlight_style(Style::default().bg(Color::Blue).add_modifier(Modifier::BOLD));

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
