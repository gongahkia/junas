//! Top status bar: app name, FPS, processing latencies, output status, transform mode.

use crate::app::{App, PipelineState};
use privacy_common::transform::TransformMode;
use privacy_output::SinkKind;
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
    let pipeline_icon = match app.pipeline_state {
        PipelineState::Running => "●",
        PipelineState::Paused => "⏸",
    };

    let s = &app.stats;
    let total_lat = s.capture_latency_ms + s.ocr_latency_ms + s.transform_latency_ms + s.output_latency_ms;

    let rec_span = if let Some(t) = app.recording_started_at {
        let secs = t.elapsed().as_secs();
        Span::styled(
            format!(" ● REC {:02}:{:02} ", secs / 60, secs % 60),
            Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
        )
    } else {
        Span::raw("")
    };

    let line = Line::from(vec![
        Span::styled(" aki ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw("│ "),
        Span::styled(pipeline_icon, Style::default().fg(pipeline_color)),
        Span::raw(format!(
            " {:.1}fps  │  cap:{:.0}ms ocr:{:.0}ms tx:{:.0}ms out:{:.0}ms tot:{:.0}ms  │  {:?} {:.0}%",
            s.actual_fps,
            s.capture_latency_ms,
            s.ocr_latency_ms,
            s.transform_latency_ms,
            s.output_latency_ms,
            total_lat,
            app.transform_mode,
            app.transform_intensity * 100.0,
        )),
        {
            let neural_status = if app.transform_mode == TransformMode::Neural {
                if privacy_core::transform::neural::model_path().exists() {
                    Span::styled(" [neural:ready]", Style::default().fg(Color::Green))
                } else {
                    Span::styled(" [neural:unavailable]", Style::default().fg(Color::Red))
                }
            } else {
                Span::raw("")
            };
            neural_status
        },
        Span::raw(format!(
            "  │  drop:{}  grid:{}x{} q:{:.0}% ",
            s.dropped_frames,
            s.ocr_grid_cols,
            s.ocr_grid_rows,
            s.quality_scale * 100.0,
        )),
        rec_span,
        {
            let sink_str = match &app.active_sink_kind {
                Some(SinkKind::V4l2(dev)) => format!("  │  sink:v4l2:{}", dev),
                Some(SinkKind::CoreMedia) => "  │  sink:coremedia".to_string(),
                Some(SinkKind::HttpMjpeg(port)) => format!("  │  sink:mjpeg:{}", port),
                Some(SinkKind::Obs(port)) => format!("  │  sink:obs:{}", port),
                Some(SinkKind::Twitch) => "  │  sink:twitch(planned)".to_string(),
                None => String::new(),
            };
            Span::styled(sink_str, Style::default().fg(Color::DarkGray))
        },
    ]);

    if let Some(ref err) = app.capture_error {
        let err_line = Line::from(vec![
            Span::styled(" capture failed: ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
            Span::raw(err.clone()),
        ]);
        frame.render_widget(Paragraph::new(err_line), area);
        return;
    }
    frame.render_widget(Paragraph::new(line), area);
}
