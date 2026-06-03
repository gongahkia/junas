//! Localhost WebSocket control server — exposes pipeline commands for the macOS sidecar shell.
//!
//! Listens on ws://127.0.0.1:9877 (default).
//! JSON protocol:
//!   → {"cmd":"pause"}
//!   → {"cmd":"resume"}
//!   → {"cmd":"set_transform","mode":"blur|pixelate|cartoon|ascii|neural"}
//!   → {"cmd":"stats"}
//! Responses are JSON with {"ok":bool,...}.

use privacy_common::transform::TransformMode;
use serde_json::json;
use std::sync::{
    atomic::{AtomicBool, AtomicU32, AtomicU64, AtomicUsize, Ordering},
    Arc, Mutex,
};
use tungstenite::{accept, Message};

pub const DEFAULT_CONTROL_PORT: u16 = 9877;

/// Shared state mutated by the control server and polled by the TUI each tick.
pub struct ControlState {
    pub paused: AtomicBool,
    pub transform_mode: Mutex<TransformMode>,
    pub intensity: Mutex<f32>,
    /// Pending mode switch requested via WebSocket (consumed once by TUI on tick).
    pub pending_mode: Mutex<Option<TransformMode>>,
    /// Pending pause/resume change (None = no change, Some(bool) = new paused value).
    pub pending_pause: Mutex<Option<bool>>,
    /// Latest observed pipeline FPS multiplied by 1000.
    pub actual_fps_milli: AtomicU32,
    /// Total redaction events observed by the active process.
    pub redaction_count: AtomicU64,
    /// Latest dropped-frame count from the active pipeline.
    pub dropped_frames: AtomicU64,
    /// Capture source selected when the active sidecar process was launched.
    source: Mutex<String>,
    /// Output sink selected when the active sidecar process was launched.
    output: Mutex<String>,
}

impl ControlState {
    pub fn new(mode: TransformMode, intensity: f32) -> Arc<Self> {
        Arc::new(Self {
            paused: AtomicBool::new(false),
            transform_mode: Mutex::new(mode),
            intensity: Mutex::new(intensity),
            pending_mode: Mutex::new(None),
            pending_pause: Mutex::new(None),
            actual_fps_milli: AtomicU32::new(0),
            redaction_count: AtomicU64::new(0),
            dropped_frames: AtomicU64::new(0),
            source: Mutex::new("screen".to_string()),
            output: Mutex::new("auto".to_string()),
        })
    }

    pub fn set_source(&self, source: &str) {
        *self.source.lock().unwrap() = source.to_string();
    }

    pub fn set_output(&self, output: &str) {
        *self.output.lock().unwrap() = output.to_string();
    }
}

/// Spawn control server background thread. Non-blocking.
pub fn spawn(state: Arc<ControlState>, port: u16) {
    std::thread::Builder::new()
        .name("aki-control".into())
        .spawn(move || run_server(state, port))
        .ok();
}

const MAX_CONNECTIONS: usize = 10;

fn run_server(state: Arc<ControlState>, port: u16) {
    let listener = match std::net::TcpListener::bind(format!("127.0.0.1:{port}")) {
        Ok(l) => l,
        Err(e) => {
            log::error!("control server: bind 127.0.0.1:{port} failed: {e}");
            return;
        }
    };
    log::info!("control server: ws://127.0.0.1:{port}");
    let conn_count = Arc::new(AtomicUsize::new(0));
    for stream in listener.incoming() {
        match stream {
            Ok(s) => {
                let cur = conn_count.load(Ordering::Relaxed);
                if cur >= MAX_CONNECTIONS {
                    log::warn!(
                        "control server: connection limit ({MAX_CONNECTIONS}) reached, dropping"
                    );
                    drop(s);
                    continue;
                }
                conn_count.fetch_add(1, Ordering::Relaxed);
                let st = Arc::clone(&state);
                let counter = Arc::clone(&conn_count);
                std::thread::spawn(move || {
                    handle_client(s, st);
                    counter.fetch_sub(1, Ordering::Relaxed);
                });
            }
            Err(e) => log::warn!("control server: accept error: {e}"),
        }
    }
}

fn handle_client(stream: std::net::TcpStream, state: Arc<ControlState>) {
    let mut ws = match accept(stream) {
        Ok(w) => w,
        Err(e) => {
            log::debug!("control server: WS handshake failed: {e}");
            return;
        }
    };
    loop {
        let msg = match ws.read() {
            Ok(m) => m,
            Err(_) => break,
        };
        if msg.is_close() {
            break;
        }
        if msg.is_text() || msg.is_binary() {
            let text = msg.to_text().unwrap_or("");
            let resp = dispatch(text, &state);
            if ws.send(Message::Text(resp.into())).is_err() {
                break;
            }
        }
    }
}

fn dispatch(text: &str, state: &ControlState) -> String {
    log::debug!("control server: request payload={text}");
    let v: serde_json::Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(e) => return json!({"ok":false,"error":format!("parse error: {e}")}).to_string(),
    };
    match v.get("cmd").and_then(|c| c.as_str()) {
        Some("pause") => {
            log::info!("control server: cmd=pause");
            state.paused.store(true, Ordering::SeqCst);
            *state.pending_pause.lock().unwrap() = Some(true);
            json!({"ok":true,"cmd":"pause"}).to_string()
        }
        Some("resume") => {
            log::info!("control server: cmd=resume");
            state.paused.store(false, Ordering::SeqCst);
            *state.pending_pause.lock().unwrap() = Some(false);
            json!({"ok":true,"cmd":"resume"}).to_string()
        }
        Some("switch_mode") | Some("set_transform") => {
            let cmd = v
                .get("cmd")
                .and_then(|c| c.as_str())
                .unwrap_or("set_transform");
            let mode_str = v.get("mode").and_then(|m| m.as_str()).unwrap_or("");
            match parse_mode(mode_str) {
                Some(mode) => {
                    log::info!("control server: cmd={cmd} mode={mode_str}");
                    *state.transform_mode.lock().unwrap() = mode;
                    *state.pending_mode.lock().unwrap() = Some(mode);
                    json!({"ok":true,"cmd":cmd,"mode":mode_label(mode)}).to_string()
                }
                None => json!({"ok":false,"error":format!("unknown mode: {mode_str}")}).to_string(),
            }
        }
        Some("get_stats") | Some("stats") => {
            let cmd = v.get("cmd").and_then(|c| c.as_str()).unwrap_or("stats");
            log::debug!("control server: cmd={cmd}");
            let mode = *state.transform_mode.lock().unwrap();
            let intensity = *state.intensity.lock().unwrap();
            let paused = state.paused.load(Ordering::SeqCst);
            let fps = state.actual_fps_milli.load(Ordering::Relaxed) as f32 / 1000.0;
            let redactions = state.redaction_count.load(Ordering::Relaxed);
            let dropped_frames = state.dropped_frames.load(Ordering::Relaxed);
            let source = state.source.lock().unwrap().clone();
            let output = state.output.lock().unwrap().clone();
            json!({
                "ok": true,
                "cmd": cmd,
                "protocol_version": 1,
                "mode": mode_label(mode),
                "intensity": intensity,
                "paused": paused,
                "source": source,
                "output": output,
                "fps": fps,
                "redactions": redactions,
                "dropped_frames": dropped_frames,
            })
            .to_string()
        }
        Some(other) => {
            log::warn!("control server: unknown cmd={other}");
            json!({"ok":false,"error":format!("unknown cmd: {other}")}).to_string()
        }
        None => {
            log::warn!("control server: missing cmd field");
            json!({"ok":false,"error":"missing cmd field"}).to_string()
        }
    }
}

fn parse_mode(s: &str) -> Option<TransformMode> {
    match s.to_lowercase().as_str() {
        "blur" => Some(TransformMode::Blur),
        "pixelate" => Some(TransformMode::Pixelate),
        "cartoon" => Some(TransformMode::Cartoon),
        "ascii" => Some(TransformMode::Ascii),
        "neural" => Some(TransformMode::Neural),
        _ => None,
    }
}

fn mode_label(mode: TransformMode) -> &'static str {
    match mode {
        TransformMode::Blur => "blur",
        TransformMode::Pixelate => "pixelate",
        TransformMode::Cartoon => "cartoon",
        TransformMode::Ascii => "ascii",
        TransformMode::Neural => "neural",
    }
}
