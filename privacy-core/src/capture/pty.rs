//! PTY-based capture: wraps user's shell in a PTY, intercepts terminal output byte stream,
//! renders to a virtual terminal (vt100 crate), captures rendered framebuffer.
//! OS-independent — no screen capture permissions needed.

use anyhow::{Context, Result};
use privacy_common::frame::{RawFrame, WindowInfo};
use std::{
    io::Read,
    sync::{Arc, Mutex},
};

use super::CaptureSource;

/// Simulated terminal dimensions.
const PTY_COLS: u16 = 220;
const PTY_ROWS: u16 = 50;
/// Rendered pixel dimensions (8px per char cell).
const CELL_W: u32 = 8;
const CELL_H: u32 = 16;

/// PTY-based capture source using portable-pty + vt100 for rendering.
pub struct PtyCaptureSource {
    shell: String,
    parser: Arc<Mutex<vt100::Parser>>,
    child: Option<Box<dyn portable_pty::Child + Send>>,
    reader: Option<Box<dyn std::io::Read + Send>>,
}

impl PtyCaptureSource {
    /// Create a PTY source wrapping the given shell (e.g. "/bin/zsh").
    pub fn new(shell: impl Into<String>) -> Self {
        let parser = vt100::Parser::new(PTY_ROWS, PTY_COLS, 1024);
        Self {
            shell: shell.into(),
            parser: Arc::new(Mutex::new(parser)),
            child: None,
            reader: None,
        }
    }

    /// Detect the user's default shell.
    pub fn default_shell() -> String {
        std::env::var("SHELL").unwrap_or_else(|_| "/bin/sh".into())
    }
}

impl CaptureSource for PtyCaptureSource {
    fn start(&mut self) -> Result<()> {
        use portable_pty::{native_pty_system, CommandBuilder, PtySize};
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: PTY_ROWS,
                cols: PTY_COLS,
                pixel_width: 0,
                pixel_height: 0,
            })
            .context("opening PTY")?;
        let mut cmd = CommandBuilder::new(&self.shell);
        cmd.arg("--login");
        let child = pair
            .slave
            .spawn_command(cmd)
            .context("spawning shell in PTY")?;
        let reader = pair
            .master
            .try_clone_reader()
            .context("cloning PTY reader")?;
        self.child = Some(child);
        self.reader = Some(reader);
        log::info!("PTY capture started (shell={})", self.shell);
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        self.reader = None;
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
        }
        Ok(())
    }

    fn next_frame(&mut self) -> Result<Option<RawFrame>> {
        let reader = match self.reader.as_mut() {
            Some(r) => r,
            None => return Ok(None),
        };
        let mut buf = vec![0u8; 4096];
        let n = match reader.read(&mut buf) {
            Ok(0) | Err(_) => return Ok(None),
            Ok(n) => n,
        };
        // feed bytes to vt100 parser
        let mut parser = self.parser.lock().unwrap();
        parser.process(&buf[..n]);
        // render framebuffer
        let screen = parser.screen();
        let w = PTY_COLS as u32 * CELL_W;
        let h = PTY_ROWS as u32 * CELL_H;
        let mut pixels = vec![0u8; (w * h * 4) as usize];
        // simple rendering: map vt100 color to RGBA for each character cell
        for row in 0..PTY_ROWS as usize {
            for col in 0..PTY_COLS as usize {
                let cell = screen.cell(row as u16, col as u16);
                let (r, g, b) = cell
                    .map(|c| vt100_fg_to_rgb(c.fgcolor()))
                    .unwrap_or((204, 204, 204));
                let px_x = col as u32 * CELL_W;
                let px_y = row as u32 * CELL_H;
                for dy in 0..CELL_H {
                    for dx in 0..CELL_W {
                        let idx = ((px_y + dy) * w + (px_x + dx)) as usize * 4;
                        pixels[idx] = r;
                        pixels[idx + 1] = g;
                        pixels[idx + 2] = b;
                        pixels[idx + 3] = 255;
                    }
                }
            }
        }
        Ok(Some(RawFrame {
            pixels,
            width: w,
            height: h,
            timestamp: chrono::Utc::now(),
        }))
    }

    fn list_windows(&self) -> Result<Vec<WindowInfo>> {
        Ok(vec![WindowInfo {
            id: 0,
            title: format!("PTY: {}", self.shell),
            bounds: privacy_common::frame::Rect {
                x: 0,
                y: 0,
                width: PTY_COLS as u32 * CELL_W,
                height: PTY_ROWS as u32 * CELL_H,
            },
        }])
    }
}

/// Convert vt100 color to RGB tuple.
fn vt100_fg_to_rgb(color: vt100::Color) -> (u8, u8, u8) {
    match color {
        vt100::Color::Default => (204, 204, 204),
        vt100::Color::Idx(i) => ansi_256_to_rgb(i),
        vt100::Color::Rgb(r, g, b) => (r, g, b),
    }
}

/// ANSI 256-color index to RGB.
fn ansi_256_to_rgb(idx: u8) -> (u8, u8, u8) {
    // standard 16 colors
    const ANSI16: [(u8, u8, u8); 16] = [
        (0, 0, 0),
        (170, 0, 0),
        (0, 170, 0),
        (170, 85, 0),
        (0, 0, 170),
        (170, 0, 170),
        (0, 170, 170),
        (170, 170, 170),
        (85, 85, 85),
        (255, 85, 85),
        (85, 255, 85),
        (255, 255, 85),
        (85, 85, 255),
        (255, 85, 255),
        (85, 255, 255),
        (255, 255, 255),
    ];
    if (idx as usize) < ANSI16.len() {
        return ANSI16[idx as usize];
    }
    if idx >= 232 {
        let g = (idx - 232) * 10 + 8;
        return (g, g, g);
    }
    let i = idx - 16;
    let r = (i / 36) * 51;
    let g = ((i % 36) / 6) * 51;
    let b = (i % 6) * 51;
    (r, g, b)
}
