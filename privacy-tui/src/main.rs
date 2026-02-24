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
        Event::Key(k) => match k.code {
            KeyCode::Char(' ') => app.toggle_pipeline(),
            KeyCode::Char('t') => app.cycle_transform(),
            KeyCode::Char('+') | KeyCode::Char('=') => app.adjust_intensity(0.1),
            KeyCode::Char('-') => app.adjust_intensity(-0.1),
            _ => {}
        },
        Event::Tick => {} // stats updates handled by pipeline threads
    }
}
