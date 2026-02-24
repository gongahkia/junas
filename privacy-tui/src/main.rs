mod app;
mod event;
mod tui;
mod ui;

use anyhow::Result;
use event::{next_event, Event, is_quit};
use std::time::Duration;

const TICK_RATE: Duration = Duration::from_millis(100); // 10 Hz

fn main() -> Result<()> {
    env_logger::init();

    let mut terminal = tui::init()?;
    let mut app = app::App::new();

    let result = run(&mut terminal, &mut app);
    tui::restore()?;
    result
}

fn run(terminal: &mut tui::Tui, app: &mut app::App) -> Result<()> {
    while app.running {
        terminal.draw(|frame| ui::render(frame, app))?;

        let ev = next_event(TICK_RATE)?;
        if is_quit(&ev) {
            app.running = false;
            break;
        }
        handle_event(app, ev);
    }
    Ok(())
}

fn handle_event(app: &mut app::App, ev: Event) {
    use crossterm::event::KeyCode;
    match ev {
        Event::Key(k) => {
            if app.window_selector.open {
                match k.code {
                    KeyCode::Char('j') | KeyCode::Down => app.window_selector.move_down(),
                    KeyCode::Char('k') | KeyCode::Up => app.window_selector.move_up(),
                    KeyCode::Enter => {
                        let id = app.window_selector.selected_window().map(|w| w.id);
                        if let Some(id) = id { app.selected_window_id = Some(id); }
                        app.window_selector.close();
                    }
                    KeyCode::Esc => app.window_selector.close(),
                    _ => {}
                }
                return;
            }
            if app.pattern_manager.open {
                let len = app.pattern_registry.patterns.len();
                match k.code {
                    KeyCode::Char('j') | KeyCode::Down => app.pattern_manager.move_down(len),
                    KeyCode::Char('k') | KeyCode::Up => app.pattern_manager.move_up(len),
                    KeyCode::Char(' ') => app.pattern_manager.toggle(&mut app.pattern_registry),
                    KeyCode::Esc => app.pattern_manager.close(),
                    _ => {}
                }
                return;
            }
            match k.code {
                KeyCode::Char('w') => {
                    let windows = privacy_core::capture::window_picker::list_windows()
                        .unwrap_or_default();
                    app.window_selector.open(windows);
                }
                KeyCode::Char('p') => app.pattern_manager.open(),
                KeyCode::Char(' ') => app.toggle_pipeline(),
                KeyCode::Char('t') => app.cycle_transform(),
                KeyCode::Char('+') | KeyCode::Char('=') => app.adjust_intensity(0.1),
                KeyCode::Char('-') => app.adjust_intensity(-0.1),
                _ => {}
            }
        }
        Event::Tick => {}
    }
}
