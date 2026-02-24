mod app;
mod event;
mod shutdown;
mod tui;
mod ui;

use anyhow::Result;
use clap::{Parser, Subcommand};
use event::{next_event, Event, is_quit};
use std::time::Duration;

const TICK_RATE: Duration = Duration::from_millis(100); // 10 Hz

#[derive(Parser)]
#[command(name = "aki", about = "Real-time privacy filter for screen capture")]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Launch TUI + pipeline (default when no subcommand given).
    Run,
    /// Print all available capturable windows.
    ListWindows,
    /// Run sensitivity patterns against provided text.
    TestPatterns {
        /// Text to test against all enabled patterns.
        text: String,
    },
    /// Verify virtual camera output availability.
    CheckOutput,
}

fn main() -> Result<()> {
    env_logger::init();
    let cli = Cli::parse();
    match cli.command.unwrap_or(Command::Run) {
        Command::Run => cmd_run(),
        Command::ListWindows => cmd_list_windows(),
        Command::TestPatterns { text } => cmd_test_patterns(&text),
        Command::CheckOutput => cmd_check_output(),
    }
}

fn cmd_run() -> Result<()> {
    let mut terminal = tui::init()?;
    let mut app = app::App::new();
    let result = run(&mut terminal, &mut app);
    tui::restore()?;
    // ordered shutdown: pipeline handle + output sink are None until pipeline wired at runtime
    shutdown::ordered_shutdown(None, None)?;
    result
}

fn cmd_list_windows() -> Result<()> {
    let windows = privacy_core::capture::window_picker::list_windows()?;
    if windows.is_empty() {
        println!("no windows found");
        return Ok(());
    }
    println!("{:>8}  {:<40}  {}x{}", "ID", "TITLE", "W", "H");
    for w in &windows {
        println!("{:>8}  {:<40}  {}x{}", w.id, &w.title, w.bounds.width, w.bounds.height);
    }
    Ok(())
}

fn cmd_test_patterns(text: &str) -> Result<()> {
    use privacy_core::detection::{
        default_patterns::default_registry,
        pii_patterns::pii_patterns,
    };
    let mut registry = default_registry();
    registry.patterns.extend(pii_patterns());
    let mut hits = 0usize;
    for p in registry.patterns.iter().filter(|p| p.enabled) {
        if let Some(m) = p.find(text) {
            println!("[{:?}] {} → {:?}", p.severity, p.name, m);
            hits += 1;
        }
    }
    if hits == 0 {
        println!("no patterns matched");
    } else {
        println!("\n{} pattern(s) matched", hits);
    }
    Ok(())
}

fn cmd_check_output() -> Result<()> {
    use privacy_output::autodetect::detect_best_sink;
    use privacy_output::SinkKind;
    let sink = detect_best_sink(9876);
    match &sink {
        SinkKind::V4l2(dev) => println!("v4l2loopback available: {}", dev),
        SinkKind::CoreMedia => println!("CoreMediaIO virtual camera available"),
        SinkKind::HttpMjpeg(port) => println!("fallback: MJPEG HTTP on port {}", port),
    }
    Ok(())
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
