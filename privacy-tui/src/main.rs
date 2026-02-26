mod app;
mod control_server;
mod event;
mod shutdown;
mod tui;
mod ui;

use anyhow::Result;
use clap::{Parser, Subcommand};
use event::{next_event, Event, is_quit};
use std::time::{Duration, Instant};

const TICK_RATE: Duration = Duration::from_millis(100); // 10 Hz

#[derive(Parser)]
#[command(name = "aki", about = "Real-time privacy filter for screen capture")]
struct Cli {
    /// Run without TUI (headless mode) — log stats to file, output to virtual camera only.
    #[arg(long)]
    headless: bool,
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
    /// Capture 10 frames, run detection, print summary of found sensitive regions.
    TestScreen,
    /// Run detection pipeline self-test against synthetic sensitive data.
    SelfTest,
}

fn main() -> Result<()> {
    env_logger::init();
    let cli = Cli::parse();
    if cli.headless {
        return cmd_headless();
    }
    match cli.command.unwrap_or(Command::Run) {
        Command::Run => cmd_run(),
        Command::ListWindows => cmd_list_windows(),
        Command::TestPatterns { text } => cmd_test_patterns(&text),
        Command::CheckOutput => cmd_check_output(),
        Command::TestScreen => cmd_test_screen(),
        Command::SelfTest => cmd_self_test(),
    }
}

/// Headless mode: full pipeline without TUI; logs stats to XDG config dir; Ctrl-C to stop.
fn cmd_headless() -> Result<()> {
    use crossbeam_channel::bounded;
    use privacy_common::frame::TransformedFrame;
    use privacy_core::{
        detection::{default_patterns::default_registry, pii_patterns::pii_patterns},
        pipeline_runner::spawn_pipeline,
    };
    use privacy_output::{autodetect::detect_best_sink, create_sink};
    use std::sync::{Arc, Mutex, atomic::{AtomicBool, Ordering}};

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    ctrlc::set_handler(move || { r.store(false, Ordering::SeqCst); })
        .unwrap_or_else(|_| log::warn!("failed to set Ctrl-C handler"));

    let sink_kind = detect_best_sink(9876);
    let sink = Arc::new(Mutex::new(create_sink(sink_kind)?));
    let mut registry = default_registry();
    registry.patterns.extend(pii_patterns());
    let source = create_capture_source(None);
    let (out_tx, out_rx) = bounded::<TransformedFrame>(8);
    let handle = spawn_pipeline(source, None, registry, out_tx)?;

    // stats log path
    let stats_path = {
        let base = std::env::var("XDG_CONFIG_HOME")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|_| {
                std::path::PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".config")
            });
        let dir = base.join("ascii-privacy").join("sessions");
        let _ = std::fs::create_dir_all(&dir);
        let ts = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        dir.join(format!("headless_{ts}.log"))
    };
    log::info!("headless mode: stats → {}", stats_path.display());

    let mut frame_count = 0u64;
    let mut fps_start = Instant::now();
    let mut last_log = Instant::now();

    while running.load(Ordering::SeqCst) {
        match out_rx.recv_timeout(Duration::from_millis(200)) {
            Ok(frame) => {
                if let Ok(mut s) = sink.lock() { let _ = s.write_frame(&frame); }
                frame_count += 1;
            }
            Err(_) => {}
        }
        // log stats every 5 seconds
        if last_log.elapsed() >= Duration::from_secs(5) {
            let elapsed = fps_start.elapsed().as_secs_f32();
            let fps = if elapsed > 0.0 { frame_count as f32 / elapsed } else { 0.0 };
            let dropped = handle.state.dropped_frames.load(Ordering::Relaxed);
            let line = format!(
                "[{}] fps={:.1} frames={} dropped={}\n",
                chrono::Utc::now().to_rfc3339(),
                fps, frame_count, dropped,
            );
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&stats_path) {
                use std::io::Write;
                let _ = f.write_all(line.as_bytes());
            }
            log::info!("headless: {}", line.trim());
            last_log = Instant::now();
        }
    }

    handle.shutdown();
    log::info!("headless mode stopped");
    Ok(())
}

fn export_session_log(app: &app::App) {
    use serde_json::{json, Value};
    let entries: Vec<Value> = app.log_entries.iter().map(|e| json!({
        "timestamp": e.timestamp.to_rfc3339(),
        "pattern": e.pattern_name,
        "severity": format!("{:?}", e.severity),
        "snippet": e.snippet,
        "bounds": e.bounds.as_ref().map(|b| json!({"x":b.x,"y":b.y,"w":b.width,"h":b.height})),
    })).collect();
    let ts = chrono::Utc::now().format("%Y%m%d_%H%M%S");
    let sessions_dir = {
        let base = std::env::var("XDG_CONFIG_HOME")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|_| {
                std::path::PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".config")
            });
        base.join("ascii-privacy").join("sessions")
    };
    let _ = std::fs::create_dir_all(&sessions_dir);
    let path = sessions_dir.join(format!("aki_session_{ts}.json"));
    match std::fs::write(&path, serde_json::to_string_pretty(&entries).unwrap_or_default()) {
        Ok(_) => log::info!("session log exported to {}", path.display()),
        Err(e) => log::error!("export failed: {e}"),
    }
}

fn cmd_run() -> Result<()> {
    use privacy_output::{autodetect::detect_best_sink, create_sink, tray};
    use std::sync::{Arc, Mutex};
    let mut terminal = tui::init()?;
    let mut app = app::App::new();
    control_server::spawn(Arc::clone(&app.control_state), control_server::DEFAULT_CONTROL_PORT);
    let sink_kind = detect_best_sink(9876);
    let sink = Arc::new(Mutex::new(create_sink(sink_kind)?));
    let mut handle = spawn_capture_pipeline(&mut app, Arc::clone(&sink))?;
    // spawn macOS tray icon (no-op on other platforms)
    let (tray_tx, tray_rx) = std::sync::mpsc::channel::<bool>();
    let _ = tray::spawn_tray(tray_rx);
    let _ = tray_tx.send(true); // signal running
    let result = run_with_pipeline_restart(&mut terminal, &mut app, &sink, &mut handle);
    let _ = tray_tx.send(false); // signal stopped
    tui::restore()?;
    shutdown::ordered_shutdown(Some(handle), Some(sink))?;
    result
}

fn spawn_capture_pipeline(
    app: &mut app::App,
    sink: std::sync::Arc<std::sync::Mutex<Box<dyn privacy_output::OutputSink>>>,
) -> Result<privacy_core::pipeline_runner::PipelineHandle> {
    use crossbeam_channel::bounded;
    use privacy_common::frame::TransformedFrame;
    use privacy_core::pipeline_runner::spawn_pipeline;
    let (out_tx, out_rx) = bounded::<TransformedFrame>(8);
    let source = create_capture_source(app.selected_window_id);
    let registry = app.pattern_registry.clone();
    let handle = spawn_pipeline(source, None, registry, out_tx)?;
    app.pipeline_shared_state = Some(std::sync::Arc::clone(&handle.state));
    let (preview_tx, preview_rx) = bounded::<app::PreviewUpdate>(2);
    app.preview_rx = Some(preview_rx);
    std::thread::Builder::new()
        .name("aki-sink".into())
        .spawn(move || {
            let mut frame_count = 0u64;
            let mut fps_start = std::time::Instant::now();
            let mut current_fps = 0.0f32;
            while let Ok(frame) = out_rx.recv() {
                if let Ok(mut s) = sink.lock() {
                    let _ = s.write_frame(&frame);
                }
                frame_count += 1;
                let elapsed = fps_start.elapsed().as_secs_f32();
                if elapsed >= 1.0 {
                    current_fps = frame_count as f32 / elapsed;
                    frame_count = 0;
                    fps_start = std::time::Instant::now();
                }
                let _ = preview_tx.try_send(app::PreviewUpdate {
                    pixels: frame.pixels.clone(),
                    width: frame.width,
                    height: frame.height,
                    fps: current_fps,
                });
            }
        })?;
    Ok(handle)
}

fn run_with_pipeline_restart(
    terminal: &mut tui::Tui,
    app: &mut app::App,
    sink: &std::sync::Arc<std::sync::Mutex<Box<dyn privacy_output::OutputSink>>>,
    handle: &mut privacy_core::pipeline_runner::PipelineHandle,
) -> Result<()> {
    use std::mem;
    while app.running {
        terminal.draw(|frame| ui::render(frame, app))?;
        let ev = next_event(TICK_RATE)?;
        if is_quit(&ev) { app.running = false; break; }
        handle_event(app, ev);
        if app.pipeline_restart_needed {
            app.pipeline_restart_needed = false;
            let new_handle = spawn_capture_pipeline(app, std::sync::Arc::clone(sink))?;
            let old = mem::replace(handle, new_handle);
            old.shutdown();
        }
    }
    Ok(())
}

fn create_capture_source(window_id: Option<u64>) -> Box<dyn privacy_core::capture::CaptureSource + Send> {
    #[cfg(target_os = "macos")]
    {
        use privacy_core::capture::macos::{CaptureTarget, MacosCaptureSource};
        let target = window_id.map(CaptureTarget::Window).unwrap_or(CaptureTarget::Display(0));
        return Box::new(MacosCaptureSource::new(target, 30));
    }
    #[allow(unreachable_code)]
    { let _ = window_id; panic!("platform not supported"); }
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
        whitelist::Whitelist,
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

fn cmd_self_test() -> Result<()> {
    use privacy_core::detection::{
        default_patterns::default_registry,
        pii_patterns::pii_patterns,
        scanner::scan,
        whitelist::Whitelist,
    };
    println!("aki self-test: verifying detection pipeline against synthetic data");
    let test_cases = [
        ("AWS key", "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"),
        ("GitHub token", "GITHUB_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a"),
        ("IP address", "Server at 192.168.1.1"),
        ("Email", "contact: user@example.com"),
        ("SSH private key", "-----BEGIN RSA PRIVATE KEY-----"),
    ];
    let mut registry = default_registry();
    registry.patterns.extend(pii_patterns());
    let mut passed = 0;
    let total = test_cases.len();
    for (label, input) in &test_cases {
        let mut dummy_region = vec![privacy_common::detection::TextRegion {
            text: input.to_string(),
            bounds: privacy_common::frame::Rect { x: 0, y: 0, width: 100, height: 20 },
            confidence: 95.0,
        }];
        let matches = scan(&dummy_region, &registry, &Whitelist::empty());
        if matches.is_empty() {
            println!("  FAIL  {label}");
        } else {
            println!("  PASS  {label} → {} match(es)", matches.len());
            passed += 1;
        }
    }
    println!("\nself-test: {passed}/{total} passed (readiness: {:.0}%)", passed as f32 / total as f32 * 100.0);
    Ok(())
}

fn cmd_test_screen() -> Result<()> {
    use privacy_core::detection::{
        default_patterns::default_registry,
        incremental::{IncrementalOcr, GRID_COLS, GRID_ROWS},
        ocr::OcrEngine,
        pii_patterns::pii_patterns,
        scanner::scan,
        expand::expand_and_merge,
        whitelist::Whitelist,
    };
    use privacy_core::capture::{window_picker::list_windows, CaptureSource};
    println!("test-screen: listing windows to select capture target...");
    let windows = list_windows()?;
    if windows.is_empty() {
        println!("no capturable windows found");
        return Ok(());
    }
    println!("using first available window: {:?}", windows[0].title);
    let ocr = OcrEngine::new(None)?;
    let mut incremental = IncrementalOcr::new(ocr, GRID_COLS, GRID_ROWS);
    let mut registry = default_registry();
    registry.patterns.extend(pii_patterns());
    let mut total_matches = 0usize;
    println!("capturing 10 frames for analysis...");
    // start a real capture from the first available window
    let mut source = create_capture_source(Some(windows[0].id));
    source.start()?;
    for i in 0..10 {
        // poll for a real frame (timeout ~500ms)
        let frame = {
            let mut f = None;
            for _ in 0..50 {
                if let Ok(Some(raw)) = source.next_frame() { f = Some(raw); break; }
                std::thread::sleep(std::time::Duration::from_millis(10));
            }
            f.unwrap_or_else(|| privacy_common::frame::RawFrame {
                pixels: vec![0u8; 640 * 480 * 4],
                width: 640, height: 480, timestamp: chrono::Utc::now(),
            })
        };
        let (fw, fh) = (frame.width, frame.height);
        let regions = incremental.extract(&frame).unwrap_or_default();
        let matches = scan(&regions, &registry, &Whitelist::empty());
        let merged = expand_and_merge(matches, fw, fh, 0.10);
        total_matches += merged.len();
        println!("  frame {}: {} sensitive regions", i + 1, merged.len());
        for m in &merged {
            println!("    [{:?}] {} @ ({},{} {}x{})", m.severity, m.pattern_name, m.bounds.x, m.bounds.y, m.bounds.width, m.bounds.height);
        }
    }
    let _ = source.stop();
    println!("\ntest-screen complete: {} total sensitive regions across 10 frames", total_matches);
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
                        if let Some(id) = id {
                            app.selected_window_id = Some(id);
                            app.pipeline_restart_needed = true;
                        }
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
                    KeyCode::Char(']') => app.pattern_manager.cycle_severity(&mut app.pattern_registry),
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
                KeyCode::Char('h') => app.heatmap.enabled = !app.heatmap.enabled,
                KeyCode::Char('s') => app.stats_overlay.open = !app.stats_overlay.open,
                KeyCode::Char('r') => {
                    if app.recorder.is_some() {
                        if let Some(rec) = app.recorder.take() {
                            match rec.stop() {
                                Ok(path) => log::info!("recording saved: {path}"),
                                Err(e) => log::error!("recorder stop: {e}"),
                            }
                        }
                        app.recording_started_at = None;
                    } else {
                        let w = app.preview_width.max(640);
                        let h = app.preview_height.max(480);
                        let ts = chrono::Utc::now().format("%Y%m%d_%H%M%S");
                        let path = format!("aki_recording_{ts}.mp4");
                        match privacy_output::recorder::Recorder::start(&path, w, h, 30) {
                            Ok(rec) => {
                                app.recorder = Some(rec);
                                app.recording_started_at = Some(std::time::Instant::now());
                            }
                            Err(e) => log::error!("recorder start: {e}"),
                        }
                    }
                }
                KeyCode::Char('f') => {
                    if let (Some(entry), Some(ref pixels)) = (app.log_entries.last(), &app.tx_preview_pixels) {
                        let frame = privacy_common::frame::RawFrame {
                            pixels: pixels.clone(),
                            width: app.preview_width,
                            height: app.preview_height,
                            timestamp: chrono::Utc::now(),
                        };
                        let m = privacy_common::detection::SensitiveMatch {
                            bounds: entry.bounds.clone().unwrap_or(privacy_common::frame::Rect { x: 0, y: 0, width: 100, height: 20 }),
                            pattern_name: entry.pattern_name.clone(),
                            severity: entry.severity,
                            snippet: entry.snippet.clone(),
                        };
                        match privacy_core::detection::training::save_false_positive(&frame, &m) {
                            Ok(p) => log::info!("false positive saved: {}", p.display()),
                            Err(e) => log::error!("save_false_positive: {e}"),
                        }
                    }
                }
                KeyCode::Char('e') => export_session_log(&app),
                KeyCode::Char(c @ '1'..='9') => {
                    let idx = (c as u8 - b'0') as usize;
                    app.switch_profile(idx);
                }
                _ => {}
            }
        }
        Event::Tick => app.tick_transition(),
    }
}
