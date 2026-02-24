//! Top status bar: app name, FPS, output status, transform mode, intensity.

use crate::app::{App, PipelineState};
use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

pub fn render(frame: &mut Frame, app: &App, area: Rect) {
    let pipeline_color = match app.pipeline_state {
        PipelineState::Running => Color::Green,
        PipelineState::Paused => Color::Yellow,
    };
    let pipeline_label = match app.pipeline_state {
        PipelineState::Running => "●",
        PipelineState::Paused => "⏸",
    };

    let line = Line::from(vec![
        Span::styled(" aki ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw("│ "),
        Span::styled(pipeline_label, Style::default().fg(pipeline_color)),
        Span::raw(format!(
            " {:.1} fps  │  {:?}  {:.0}%  │  drop:{}  lat:{:.0}ms ",
            app.stats.actual_fps,
            app.transform_mode,
            app.transform_intensity * 100.0,
            app.stats.dropped_frames,
            app.stats.capture_latency_ms + app.stats.ocr_latency_ms + app.stats.transform_latency_ms,
        )),
    ]);

    frame.render_widget(Paragraph::new(line), area);
}
