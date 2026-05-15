//! HTTP MJPEG fallback output: serves transformed frames as a multipart/x-mixed-replace stream
//! at `http://127.0.0.1:<port>/stream` (default port 9876).
//! Universal fallback consumable as an OBS Browser Source.

use anyhow::{anyhow, Result};
use image::{ImageFormat, RgbaImage};
use privacy_common::frame::TransformedFrame;
use std::{
    io::{Cursor, Write},
    net::TcpListener,
    sync::{Arc, Mutex},
    thread,
};

use crate::OutputSink;

pub const DEFAULT_PORT: u16 = 9876;
const BOUNDARY: &str = "frame";

/// Shared frame state for the HTTP server thread.
type SharedFrame = Arc<Mutex<Option<Vec<u8>>>>;

pub struct MjpegSink {
    port: u16,
    latest_jpeg: SharedFrame,
    _server_thread: Option<thread::JoinHandle<()>>,
}

impl MjpegSink {
    pub fn new(port: u16) -> Result<Self> {
        let latest_jpeg: SharedFrame = Arc::new(Mutex::new(None));
        let lj = latest_jpeg.clone();

        let listener = TcpListener::bind(format!("127.0.0.1:{port}"))
            .map_err(|e| anyhow!("bind 127.0.0.1:{port}: {e}"))?;
        listener.set_nonblocking(false).ok();

        let handle = thread::spawn(move || {
            for stream in listener.incoming() {
                let Ok(mut stream) = stream else { continue };
                let lj = lj.clone();
                thread::spawn(move || {
                    // send HTTP header
                    let header = format!(
                        "HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary={BOUNDARY}\r\n\r\n"
                    );
                    if stream.write_all(header.as_bytes()).is_err() {
                        return;
                    }

                    loop {
                        let frame_bytes = {
                            let guard = lj.lock().unwrap();
                            guard.clone()
                        };
                        if let Some(jpeg) = frame_bytes {
                            let part = format!(
                                "--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {}\r\n\r\n",
                                jpeg.len()
                            );
                            if stream.write_all(part.as_bytes()).is_err() {
                                return;
                            }
                            if stream.write_all(&jpeg).is_err() {
                                return;
                            }
                            if stream.write_all(b"\r\n").is_err() {
                                return;
                            }
                        }
                        thread::sleep(std::time::Duration::from_millis(33)); // ~30fps
                    }
                });
            }
        });

        Ok(Self {
            port,
            latest_jpeg,
            _server_thread: Some(handle),
        })
    }

    pub fn stream_url(&self) -> String {
        format!("http://127.0.0.1:{}/stream", self.port)
    }
}

impl OutputSink for MjpegSink {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        let img = RgbaImage::from_raw(frame.width, frame.height, frame.pixels.clone())
            .ok_or_else(|| anyhow!("invalid frame {}x{}", frame.width, frame.height))?;
        let mut buf = Vec::new();
        img.write_to(&mut Cursor::new(&mut buf), ImageFormat::Jpeg)
            .map_err(|e| anyhow!("JPEG encode: {e}"))?;
        *self.latest_jpeg.lock().unwrap() = Some(buf);
        Ok(())
    }

    fn close(&mut self) -> Result<()> {
        // server thread will exit when the main process exits
        Ok(())
    }
}
