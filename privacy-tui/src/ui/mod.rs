//! UI rendering stub — layout and widgets filled in subsequent tasks.

use ratatui::Frame;
use crate::app::App;

pub fn render(frame: &mut Frame, app: &App) {
    use ratatui::widgets::{Block, Borders};
    let area = frame.area();
    frame.render_widget(
        Block::default()
            .title(format!(
                " aki | {:?} | {:.0}% | {:.1} fps ",
                app.transform_mode,
                app.transform_intensity * 100.0,
                app.stats.actual_fps
            ))
            .borders(Borders::ALL),
        area,
    );
}
