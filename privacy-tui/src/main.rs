mod app;
mod control_server;
mod demo;
mod event;
mod logging;
mod offline_redact;
mod shutdown;
mod tui;
mod ui;

use anyhow::{bail, Result};
use clap::{Parser, Subcommand, ValueEnum};
use event::{is_quit, next_event, Event};
use privacy_common::transform::TransformMode;
use std::path::PathBuf;
use std::time::{Duration, Instant};

const TICK_RATE: Duration = Duration::from_millis(100); // 10 Hz

#[derive(Parser)]
#[command(name = "aki", about = "Real-time privacy filter for screen capture")]
struct Cli {
    /// Run without TUI (headless mode) — log stats to file, output to virtual camera only.
    #[arg(long)]
    headless: bool,
    /// Capture source for sidecar/headless runs.
    #[arg(long, value_enum)]
    source: Option<CliSource>,
    /// Use PTY capture (compatibility alias for --source pty).
    #[arg(long)]
    pty: bool,
    /// Initial transform mode for sidecar/headless runs.
    #[arg(long, value_enum)]
    transform: Option<CliTransform>,
    /// Output sink preference for sidecar/headless runs.
    #[arg(long, value_enum)]
    output: Option<CliOutput>,
    /// HTTP MJPEG port used when the output sink needs one.
    #[arg(long, default_value_t = 9876)]
    http_port: u16,
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum CliTransform {
    Blur,
    Pixelate,
    Cartoon,
    Ascii,
    Neural,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum CliSource {
    Screen,
    Pty,
}

impl CliSource {
    fn uses_pty(self) -> bool {
        matches!(self, CliSource::Pty)
    }

    fn protocol_value(self) -> &'static str {
        match self {
            CliSource::Screen => "screen",
            CliSource::Pty => "pty",
        }
    }
}

impl From<CliTransform> for TransformMode {
    fn from(value: CliTransform) -> Self {
        match value {
            CliTransform::Blur => TransformMode::Blur,
            CliTransform::Pixelate => TransformMode::Pixelate,
            CliTransform::Cartoon => TransformMode::Cartoon,
            CliTransform::Ascii => TransformMode::Ascii,
            CliTransform::Neural => TransformMode::Neural,
        }
    }
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum CliOutput {
    Auto,
    Coremedia,
    Mjpeg,
    Obs,
}

#[derive(Debug, Subcommand)]
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
    /// Print a rolling screen of deterministic fake secrets and PII-shaped fixtures.
    Demo {
        /// Number of frames to render. Use 0 to keep rolling until interrupted.
        #[arg(long, default_value_t = 0)]
        frames: u32,
        /// Delay between rolling frames.
        #[arg(long, default_value_t = 750)]
        interval_ms: u64,
        /// Do not clear the terminal before each frame.
        #[arg(long)]
        no_clear: bool,
    },
    /// Redact an existing local video file and write a new redacted output.
    Redact {
        /// Input video file to redact.
        input: PathBuf,
        /// Output video path. Defaults to <input-stem>.redacted.<ext>.
        #[arg(short, long)]
        output: Option<PathBuf>,
        /// Transform mode to apply to detected regions. Defaults to config.
        #[arg(long, value_enum)]
        transform: Option<CliTransform>,
        /// Transform intensity in the range 0.0 to 1.0. Defaults to config.
        #[arg(long)]
        intensity: Option<f32>,
        /// Allow replacing an existing output file. The input file is never overwritten.
        #[arg(long)]
        overwrite: bool,
    },
}

fn main() -> Result<()> {
    let log_path = logging::init()?;
    log::info!("log file ready at {}", log_path.display());
    let cli = Cli::parse();
    let source = resolve_source(cli.source, cli.pty)?;
    log::info!(
        "cli parsed headless={} source={} command={:?}",
        cli.headless,
        source.protocol_value(),
        cli.command
    );
    if cli.headless {
        return cmd_headless(source, cli.transform, cli.output, cli.http_port);
    }
    match cli.command.unwrap_or(Command::Run) {
        Command::Run => cmd_run(source.uses_pty()),
        Command::ListWindows => cmd_list_windows(),
        Command::TestPatterns { text } => cmd_test_patterns(&text),
        Command::CheckOutput => cmd_check_output(),
        Command::TestScreen => cmd_test_screen(),
        Command::SelfTest => cmd_self_test(),
        Command::Demo {
            frames,
            interval_ms,
            no_clear,
        } => demo::run_demo(demo::DemoOptions {
            frames,
            interval_ms,
            no_clear,
        }),
        Command::Redact {
            input,
            output,
            transform,
            intensity,
            overwrite,
        } => cmd_redact(input, output, transform, intensity, overwrite),
    }
}

fn resolve_source(source: Option<CliSource>, pty: bool) -> Result<CliSource> {
    match (source, pty) {
        (Some(CliSource::Screen), true) => bail!("--source screen cannot be combined with --pty"),
        (Some(source), _) => Ok(source),
        (None, true) => Ok(CliSource::Pty),
        (None, false) => Ok(CliSource::Screen),
    }
}

/// Headless mode: full pipeline without TUI; logs stats to XDG config dir; Ctrl-C to stop.
fn cmd_headless(
    source_choice: CliSource,
    transform: Option<CliTransform>,
    output: Option<CliOutput>,
    http_port: u16,
) -> Result<()> {
    use crossbeam_channel::bounded;
    use privacy_common::frame::TransformedFrame;
    use privacy_core::{
        config::AppConfig, detection::registry::runtime_registry, pipeline_runner::spawn_pipeline,
    };
    use privacy_output::{autodetect::detect_best_sink, create_sink, SinkKind};
    use std::sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    };

    log::info!(
        "starting headless mode source={}",
        source_choice.protocol_value()
    );
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    ctrlc::set_handler(move || {
        r.store(false, Ordering::SeqCst);
    })
    .unwrap_or_else(|_| log::warn!("failed to set Ctrl-C handler"));

    let output_choice = output.unwrap_or(CliOutput::Auto);
    let sink_kind = match output_choice {
        CliOutput::Auto => detect_best_sink(http_port),
        CliOutput::Coremedia => SinkKind::CoreMedia,
        CliOutput::Mjpeg => SinkKind::HttpMjpeg(http_port),
        CliOutput::Obs => SinkKind::Obs(http_port),
    };
    let output_label = sink_kind_label(&sink_kind);
    let sink = Arc::new(Mutex::new(create_sink(sink_kind)?));
    let cfg = AppConfig::load().unwrap_or_default();
    let initial_mode = transform
        .map(TransformMode::from)
        .unwrap_or_else(|| transform_mode_from_config(&cfg.transform.mode));
    let initial_intensity = cfg.transform.intensity.clamp(0.0, 1.0);
    let control_state = control_server::ControlState::new(initial_mode, initial_intensity);
    control_state.set_source(source_choice.protocol_value());
    control_state.set_output(&output_label);
    control_server::spawn(
        Arc::clone(&control_state),
        control_server::DEFAULT_CONTROL_PORT,
    );
    let registry = runtime_registry(&cfg);
    let source = create_capture_source(None, source_choice.uses_pty());
    let (out_tx, out_rx) = bounded::<TransformedFrame>(8);
    let handle = spawn_pipeline(source, None, registry, out_tx)?;
    *handle.state.transform_mode.lock().unwrap() = initial_mode;
    *handle.state.transform_intensity.lock().unwrap() = initial_intensity;

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
    let fps_start = Instant::now();
    let mut last_log = Instant::now();

    while running.load(Ordering::SeqCst) {
        apply_headless_control(&control_state, &handle.state);
        if let Ok(frame) = out_rx.recv_timeout(Duration::from_millis(200)) {
            if let Ok(mut s) = sink.lock() {
                let _ = s.write_frame(&frame);
            }
            frame_count += 1;
        }
        // log stats every 5 seconds
        if last_log.elapsed() >= Duration::from_secs(5) {
            let elapsed = fps_start.elapsed().as_secs_f32();
            let fps = if elapsed > 0.0 {
                frame_count as f32 / elapsed
            } else {
                0.0
            };
            let dropped = handle.state.dropped_frames.load(Ordering::Relaxed);
            control_state
                .actual_fps_milli
                .store((fps.max(0.0) * 1000.0) as u32, Ordering::Relaxed);
            control_state
                .dropped_frames
                .store(dropped, Ordering::Relaxed);
            drain_headless_detection_events(&control_state, &handle.state);
            let line = format!(
                "[{}] fps={:.1} frames={} dropped={}\n",
                chrono::Utc::now().to_rfc3339(),
                fps,
                frame_count,
                dropped,
            );
            if let Ok(mut f) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&stats_path)
            {
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

fn sink_kind_label(sink_kind: &privacy_output::SinkKind) -> String {
    match sink_kind {
        privacy_output::SinkKind::V4l2(path) => format!("v4l2:{path}"),
        privacy_output::SinkKind::CoreMedia => "coremedia".to_string(),
        privacy_output::SinkKind::HttpMjpeg(port) => format!("mjpeg:{port}"),
        privacy_output::SinkKind::Obs(port) => format!("obs:{port}"),
        privacy_output::SinkKind::Twitch => "twitch".to_string(),
    }
}

fn transform_mode_from_config(mode: &str) -> TransformMode {
    match mode {
        "cartoon" => TransformMode::Cartoon,
        "ascii" => TransformMode::Ascii,
        "pixelate" => TransformMode::Pixelate,
        "neural" => TransformMode::Neural,
        _ => TransformMode::Blur,
    }
}

fn runtime_registry_from_disk() -> privacy_core::detection::patterns::PatternRegistry {
    let cfg = privacy_core::config::AppConfig::load().unwrap_or_default();
    privacy_core::detection::registry::runtime_registry(&cfg)
}

fn cmd_redact(
    input: PathBuf,
    output: Option<PathBuf>,
    transform: Option<CliTransform>,
    intensity: Option<f32>,
    overwrite: bool,
) -> Result<()> {
    let cfg = privacy_core::config::AppConfig::load().unwrap_or_default();
    let mode = transform
        .map(TransformMode::from)
        .unwrap_or_else(|| transform_mode_from_config(&cfg.transform.mode));
    let intensity = intensity.unwrap_or(cfg.transform.intensity);
    if !(0.0..=1.0).contains(&intensity) {
        bail!("--intensity must be between 0.0 and 1.0");
    }

    let summary = offline_redact::redact_video(offline_redact::RedactOptions {
        input,
        output,
        transform_mode: mode,
        intensity,
        overwrite,
        config: cfg,
    })?;

    println!(
        "redacted {} frame(s), {} detected region(s)",
        summary.frames, summary.detected_regions
    );
    println!("output: {}", summary.output.display());
    Ok(())
}

fn apply_headless_control(
    control: &control_server::ControlState,
    state: &privacy_core::pipeline_runner::SharedState,
) {
    if let Ok(mut pending) = control.pending_pause.try_lock() {
        if let Some(paused) = pending.take() {
            state
                .paused
                .store(paused, std::sync::atomic::Ordering::SeqCst);
        }
    }
    if let Ok(mut pending) = control.pending_mode.try_lock() {
        if let Some(mode) = pending.take() {
            state.begin_mode_transition(mode);
        }
    }
}

fn drain_headless_detection_events(
    control: &control_server::ControlState,
    state: &privacy_core::pipeline_runner::SharedState,
) {
    if let Ok(mut events) = state.detection_events.try_lock() {
        let count = events.len() as u64;
        events.clear();
        if count > 0 {
            control
                .redaction_count
                .fetch_add(count, std::sync::atomic::Ordering::Relaxed);
        }
    }
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
    match std::fs::write(
        &path,
        serde_json::to_string_pretty(&entries).unwrap_or_default(),
    ) {
        Ok(_) => log::info!("session log exported to {}", path.display()),
        Err(e) => log::error!("export failed: {e}"),
    }
}

fn cmd_run(use_pty: bool) -> Result<()> {
    use privacy_output::{autodetect::detect_best_sink, create_sink, tray};
    use std::sync::{Arc, Mutex};
    log::info!("starting tui mode use_pty={use_pty}");
    let mut terminal = tui::init()?;
    let mut app = app::App::new();
    app.use_pty = use_pty;
    auto_select_initial_window(&mut app);
    let sink_kind = detect_best_sink(9876);
    app.active_sink_kind = Some(sink_kind.clone());
    let sink = Arc::new(Mutex::new(create_sink(sink_kind)?));
    control_server::spawn(
        Arc::clone(&app.control_state),
        control_server::DEFAULT_CONTROL_PORT,
    );
    let mut handle = Some(spawn_capture_pipeline(&mut app, Arc::clone(&sink))?);
    // spawn macOS tray icon (no-op on other platforms)
    let (tray_tx, tray_rx) = std::sync::mpsc::channel::<bool>();
    let _ = tray::spawn_tray(tray_rx);
    let _ = tray_tx.send(true); // signal running
    let result = run_with_pipeline_restart(&mut terminal, &mut app, &sink, &mut handle);
    let _ = tray_tx.send(false); // signal stopped
    tui::restore()?;
    shutdown::ordered_shutdown(handle, Some(sink))?;
    result
}

/// Pick a reasonable initial capture window to avoid display self-capture recursion.
fn auto_select_initial_window(app: &mut app::App) {
    if app.use_pty || app.selected_window_id.is_some() {
        return;
    }
    let windows = privacy_core::capture::window_picker::list_windows().unwrap_or_default();
    if windows.is_empty() {
        log::warn!("auto-select window: no windows found");
        return;
    }

    let min_w = 300u32;
    let min_h = 200u32;
    let ignore_tokens = [
        "aki",
        "ghostty",
        "terminal",
        "iterm",
        "alacritty",
        "warp",
        "wezterm",
        "kitty",
        "tmux",
        "codex",
        "cargo run",
    ];
    let viable: Vec<_> = windows
        .into_iter()
        .filter(|w| w.bounds.width >= min_w && w.bounds.height >= min_h)
        .collect();
    if viable.is_empty() {
        log::warn!(
            "auto-select window: no viable windows >= {}x{}",
            min_w,
            min_h
        );
        return;
    }

    let area = |w: &privacy_common::frame::WindowInfo| -> u64 {
        w.bounds.width as u64 * w.bounds.height as u64
    };
    let pick = viable
        .iter()
        .filter(|w| {
            let t = w.title.to_ascii_lowercase();
            !ignore_tokens.iter().any(|tok| t.contains(tok))
        })
        .max_by_key(|w| area(w))
        .or_else(|| viable.iter().max_by_key(|w| area(w)));

    if let Some(w) = pick {
        app.selected_window_id = Some(w.id);
        log::info!(
            "auto-select window: id={} title='{}' {}x{}",
            w.id,
            w.title,
            w.bounds.width,
            w.bounds.height
        );
    }
}

fn spawn_capture_pipeline(
    app: &mut app::App,
    sink: std::sync::Arc<std::sync::Mutex<Box<dyn privacy_output::OutputSink>>>,
) -> Result<privacy_core::pipeline_runner::PipelineHandle> {
    use crossbeam_channel::bounded;
    use privacy_common::frame::TransformedFrame;
    use privacy_core::pipeline_runner::spawn_pipeline;
    let (out_tx, out_rx) = bounded::<TransformedFrame>(8);
    let source = create_capture_source(app.selected_window_id, app.use_pty);
    let registry = app.pattern_registry.clone();
    log::info!(
        "spawn_capture_pipeline selected_window_id={:?} use_pty={}",
        app.selected_window_id,
        app.use_pty
    );
    let handle = spawn_pipeline(source, None, registry, out_tx)?;
    app.attach_pipeline_state(std::sync::Arc::clone(&handle.state));
    let (preview_tx, preview_rx) = bounded::<app::PreviewUpdate>(2);
    app.preview_rx = Some(preview_rx);
    std::thread::Builder::new()
        .name("aki-sink".into())
        .spawn(move || {
            let mut frame_count = 0u64;
            let mut fps_start = std::time::Instant::now();
            let mut current_fps = 0.0f32;
            while let Ok(frame) = out_rx.recv() {
                let out_t0 = std::time::Instant::now();
                if let Ok(mut s) = sink.lock() {
                    let _ = s.write_frame(&frame);
                }
                let output_latency_ms = out_t0.elapsed().as_secs_f32() * 1000.0;
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
                    output_latency_ms,
                });
            }
        })?;
    Ok(handle)
}

fn run_with_pipeline_restart(
    terminal: &mut tui::Tui,
    app: &mut app::App,
    sink: &std::sync::Arc<std::sync::Mutex<Box<dyn privacy_output::OutputSink>>>,
    handle: &mut Option<privacy_core::pipeline_runner::PipelineHandle>,
) -> Result<()> {
    while app.running {
        terminal.draw(|frame| ui::render(frame, app))?;
        let ev = next_event(TICK_RATE)?;
        if is_quit(&ev) {
            app.running = false;
            break;
        }
        handle_event(app, ev);
        if app.pipeline_restart_needed {
            app.pipeline_restart_needed = false;
            if let Some(old) = handle.take() {
                old.shutdown();
            }
            match spawn_capture_pipeline(app, std::sync::Arc::clone(sink)) {
                Ok(new_handle) => {
                    *handle = Some(new_handle);
                }
                Err(e) => {
                    log::error!("pipeline restart failed: {e}");
                    app.capture_error = Some(format!("pipeline restart failed: {e}"));
                    app.pipeline_state = app::PipelineState::Paused;
                    app.control_state
                        .paused
                        .store(true, std::sync::atomic::Ordering::SeqCst);
                }
            }
        }
    }
    Ok(())
}

fn create_capture_source(
    window_id: Option<u64>,
    use_pty: bool,
) -> Box<dyn privacy_core::capture::CaptureSource + Send> {
    if use_pty {
        use privacy_core::capture::pty::PtyCaptureSource;
        log::debug!("capture source selected: pty");
        return Box::new(PtyCaptureSource::new(PtyCaptureSource::default_shell()));
    }
    #[cfg(target_os = "macos")]
    {
        use privacy_core::capture::macos::{CaptureTarget, MacosCaptureSource};
        let target = window_id
            .map(CaptureTarget::Window)
            .unwrap_or(CaptureTarget::Display(0));
        log::debug!("capture source selected: macos {:?}", window_id);
        return Box::new(MacosCaptureSource::new(target, 30));
    }
    #[allow(unreachable_code)]
    {
        let _ = window_id;
        panic!("platform not supported");
    }
}

fn cmd_list_windows() -> Result<()> {
    let windows = privacy_core::capture::window_picker::list_windows()?;
    if windows.is_empty() {
        println!("no windows found");
        return Ok(());
    }
    println!("{:>8}  {:<40}  WxH", "ID", "TITLE");
    for w in &windows {
        println!(
            "{:>8}  {:<40}  {}x{}",
            w.id, &w.title, w.bounds.width, w.bounds.height
        );
    }
    Ok(())
}

fn cmd_test_patterns(text: &str) -> Result<()> {
    let registry = runtime_registry_from_disk();
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
    use privacy_core::detection::{scanner::scan, whitelist::Whitelist};
    println!("aki self-test: verifying detection pipeline against synthetic data");
    let test_cases = [
        ("AWS key", "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"),
        (
            "GitHub token",
            "GITHUB_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a",
        ),
        ("IP address", "Server at 192.168.1.1"),
        ("Email", "contact: user@example.com"),
        ("SSH private key", "-----BEGIN RSA PRIVATE KEY-----"),
    ];
    let registry = runtime_registry_from_disk();
    let mut passed = 0;
    let total = test_cases.len();
    for (label, input) in &test_cases {
        let dummy_region = vec![privacy_common::detection::TextRegion {
            text: input.to_string(),
            bounds: privacy_common::frame::Rect {
                x: 0,
                y: 0,
                width: 100,
                height: 20,
            },
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
    println!(
        "\nself-test: {passed}/{total} passed (readiness: {:.0}%)",
        passed as f32 / total as f32 * 100.0
    );
    Ok(())
}

fn cmd_test_screen() -> Result<()> {
    use privacy_core::capture::window_picker::list_windows;
    use privacy_core::detection::{
        expand::expand_and_merge,
        incremental::{IncrementalOcr, GRID_COLS, GRID_ROWS},
        ocr::OcrEngine,
        scanner::scan,
        whitelist::Whitelist,
    };
    println!("test-screen: listing windows to select capture target...");
    let windows = list_windows()?;
    if windows.is_empty() {
        println!("no capturable windows found");
        return Ok(());
    }
    println!("using first available window: {:?}", windows[0].title);
    let ocr = OcrEngine::new(None)?;
    let mut incremental = IncrementalOcr::new(ocr, GRID_COLS, GRID_ROWS);
    let registry = runtime_registry_from_disk();
    let mut total_matches = 0usize;
    println!("capturing 10 frames for analysis...");
    // start a real capture from the first available window
    let mut source = create_capture_source(Some(windows[0].id), false);
    source.start()?;
    for i in 0..10 {
        // poll for a real frame (timeout ~500ms)
        let frame = {
            let mut f = None;
            for _ in 0..50 {
                if let Ok(Some(raw)) = source.next_frame() {
                    f = Some(raw);
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(10));
            }
            f.unwrap_or_else(|| privacy_common::frame::RawFrame {
                pixels: vec![0u8; 640 * 480 * 4],
                width: 640,
                height: 480,
                timestamp: chrono::Utc::now(),
            })
        };
        let (fw, fh) = (frame.width, frame.height);
        let regions = incremental.extract(&frame).unwrap_or_default();
        let matches = scan(&regions, &registry, &Whitelist::empty());
        let merged = expand_and_merge(matches, fw, fh, 0.10);
        total_matches += merged.len();
        println!("  frame {}: {} sensitive regions", i + 1, merged.len());
        for m in &merged {
            println!(
                "    [{:?}] {} @ ({},{} {}x{})",
                m.severity, m.pattern_name, m.bounds.x, m.bounds.y, m.bounds.width, m.bounds.height
            );
        }
    }
    let _ = source.stop();
    println!(
        "\ntest-screen complete: {} total sensitive regions across 10 frames",
        total_matches
    );
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
        SinkKind::Obs(port) => println!("OBS WebSocket + MJPEG on port {}", port),
        SinkKind::Twitch => println!("Twitch RTMP (planned — not yet wired)"),
    }
    Ok(())
}

#[allow(dead_code)]
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
            log::trace!("input:key code={:?} modifiers={:?}", k.code, k.modifiers);
            if app.help_open {
                log::debug!("action:close_help_overlay");
                app.help_open = false; // any key closes help
                return;
            }
            if app.window_selector.open {
                match k.code {
                    KeyCode::Char('j') | KeyCode::Down => {
                        log::debug!("action:window_selector.move_down");
                        app.window_selector.move_down()
                    }
                    KeyCode::Char('k') | KeyCode::Up => {
                        log::debug!("action:window_selector.move_up");
                        app.window_selector.move_up()
                    }
                    KeyCode::Enter => {
                        let id = app.window_selector.selected_window().map(|w| w.id);
                        if let Some(id) = id {
                            log::info!("action:window_selector.select window_id={id}");
                            app.selected_window_id = Some(id);
                            app.pipeline_restart_needed = true;
                        }
                        log::debug!("action:window_selector.close");
                        app.window_selector.close();
                    }
                    KeyCode::Esc => {
                        log::debug!("action:window_selector.cancel");
                        app.window_selector.close()
                    }
                    _ => {}
                }
                return;
            }
            if app.pattern_manager.open {
                let len = app.pattern_registry.patterns.len();
                match k.code {
                    KeyCode::Char('j') | KeyCode::Down => {
                        log::debug!("action:pattern_manager.move_down");
                        app.pattern_manager.move_down(len)
                    }
                    KeyCode::Char('k') | KeyCode::Up => {
                        log::debug!("action:pattern_manager.move_up");
                        app.pattern_manager.move_up(len)
                    }
                    KeyCode::Char(' ') => {
                        log::info!("action:pattern_manager.toggle_pattern");
                        app.pattern_manager.toggle(&mut app.pattern_registry);
                        app.sync_pattern_registry_to_pipeline();
                    }
                    KeyCode::Char(']') => {
                        log::info!("action:pattern_manager.cycle_severity");
                        app.pattern_manager
                            .cycle_severity(&mut app.pattern_registry);
                        app.sync_pattern_registry_to_pipeline();
                    }
                    KeyCode::Esc => {
                        log::debug!("action:pattern_manager.close");
                        app.pattern_manager.close()
                    }
                    _ => {}
                }
                return;
            }
            match k.code {
                KeyCode::Char('w') => {
                    log::debug!("action:open_window_selector");
                    let windows =
                        privacy_core::capture::window_picker::list_windows().unwrap_or_default();
                    log::info!("window_selector.loaded count={}", windows.len());
                    app.window_selector.open(windows);
                }
                KeyCode::Char('p') => {
                    log::debug!("action:open_pattern_manager");
                    app.pattern_manager.open()
                }
                KeyCode::Char(' ') => {
                    log::info!("action:toggle_pipeline");
                    app.toggle_pipeline()
                }
                KeyCode::Char('t') => {
                    log::info!("action:cycle_transform");
                    app.cycle_transform()
                }
                KeyCode::Char('+') | KeyCode::Char('=') => {
                    log::info!("action:adjust_intensity delta=+0.1");
                    app.adjust_intensity(0.1)
                }
                KeyCode::Char('-') => {
                    log::info!("action:adjust_intensity delta=-0.1");
                    app.adjust_intensity(-0.1)
                }
                KeyCode::Char('h') => {
                    app.heatmap.enabled = !app.heatmap.enabled;
                    log::info!("action:toggle_heatmap enabled={}", app.heatmap.enabled);
                }
                KeyCode::Char('s') => {
                    app.stats_overlay.open = !app.stats_overlay.open;
                    log::info!(
                        "action:toggle_stats_overlay enabled={}",
                        app.stats_overlay.open
                    );
                }
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
                    if let (Some(entry), Some(ref pixels)) =
                        (app.log_entries.last(), &app.tx_preview_pixels)
                    {
                        log::info!("action:mark_false_positive pattern={}", entry.pattern_name);
                        let frame = privacy_common::frame::RawFrame {
                            pixels: pixels.clone(),
                            width: app.preview_width,
                            height: app.preview_height,
                            timestamp: chrono::Utc::now(),
                        };
                        let m = privacy_common::detection::SensitiveMatch {
                            bounds: entry.bounds.clone().unwrap_or(privacy_common::frame::Rect {
                                x: 0,
                                y: 0,
                                width: 100,
                                height: 20,
                            }),
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
                KeyCode::Char('j') => {
                    let max = app.log_entries.len().saturating_sub(20);
                    app.log_scroll_offset = (app.log_scroll_offset + 1).min(max);
                    log::trace!(
                        "action:detection_log.scroll_down offset={}",
                        app.log_scroll_offset
                    );
                }
                KeyCode::Char('k') => {
                    app.log_scroll_offset = app.log_scroll_offset.saturating_sub(1);
                    log::trace!(
                        "action:detection_log.scroll_up offset={}",
                        app.log_scroll_offset
                    );
                }
                KeyCode::Char('?') => {
                    app.help_open = !app.help_open;
                    log::info!("action:toggle_help enabled={}", app.help_open);
                }
                KeyCode::Char('e') => {
                    log::info!("action:export_session_log");
                    export_session_log(app)
                }
                KeyCode::Char(c @ '1'..='9') => {
                    let idx = (c as u8 - b'0') as usize;
                    log::info!("action:switch_profile index={idx}");
                    app.switch_profile(idx);
                }
                _ => {}
            }
        }
        Event::Tick => app.tick_transition(),
    }
}
