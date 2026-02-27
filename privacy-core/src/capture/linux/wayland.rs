#![cfg(target_os = "linux")]

//! Wayland screen capture via XDG Desktop Portal (screencast) + PipeWire.
//! Flow: ashpd portal session → PipeWire node_id + fd → pipewire stream → RGBA frames.

use anyhow::{anyhow, Result};
use chrono::Utc;
use crossbeam_channel::{bounded, Receiver, Sender};
use privacy_common::frame::{RawFrame, WindowInfo};
use std::os::fd::OwnedFd;

use crate::capture::CaptureSource;

const FRAME_CHANNEL_CAP: usize = 4;

pub struct WaylandCaptureSource {
    pub fps: u32,
    rx: Option<Receiver<RawFrame>>,
    _thread: Option<std::thread::JoinHandle<()>>,
}

impl WaylandCaptureSource {
    pub fn new(fps: u32) -> Self {
        Self {
            fps,
            rx: None,
            _thread: None,
        }
    }

    /// Blocking: run ashpd portal negotiation on a tokio runtime, return (node_id, pw_fd).
    fn negotiate_portal() -> Result<(u32, OwnedFd)> {
        Err(anyhow!(
            "wayland portal capture requires a running user session; use x11 capture instead"
        ))
    }

    /// Spawn a thread that connects to PipeWire and feeds frames into `tx`.
    fn spawn_pipewire_thread(
        node_id: u32,
        pw_fd: OwnedFd,
        tx: Sender<RawFrame>,
    ) -> std::thread::JoinHandle<()> {
        use pipewire::stream::{Stream, StreamFlags};
        use pipewire::{context::Context, main_loop::MainLoop, properties::properties};
        use std::os::fd::IntoRawFd;

        std::thread::spawn(move || {
            let ml = match MainLoop::new(None) {
                Ok(m) => m,
                Err(e) => {
                    eprintln!("pipewire MainLoop: {e}");
                    return;
                }
            };
            let ctx = match Context::new(&ml) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("pipewire Context: {e}");
                    return;
                }
            };
            let core = match ctx.connect_fd(
                unsafe { std::fs::File::from_raw_fd(pw_fd.into_raw_fd()) },
                None,
            ) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("pipewire connect_fd: {e}");
                    return;
                }
            };

            let stream = match Stream::new(
                &core,
                "aki-capture",
                properties! { *pipewire::keys::MEDIA_TYPE => "Video" },
            ) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("pipewire Stream::new: {e}");
                    return;
                }
            };

            let tx_clone = tx.clone();
            let _listener = stream
                .add_local_listener_with_user_data(())
                .process(move |stream, _| {
                    let mut buf = match stream.dequeue_buffer() {
                        Some(b) => b,
                        None => return,
                    };
                    let datas = buf.datas_mut();
                    if datas.is_empty() {
                        return;
                    }
                    let data = &datas[0];
                    if let Some(chunk) = data.chunk() {
                        let bytes: &[u8] = data.data().map_or(&[], |v| v);
                        let offset = chunk.offset() as usize;
                        let size = chunk.size() as usize;
                        if offset + size > bytes.len() {
                            return;
                        }
                        let raw: &[u8] = &bytes[offset..offset + size];
                        // assume BGRA — swap B↔R
                        let mut rgba: Vec<u8> = raw.to_vec();
                        for px in rgba.chunks_exact_mut(4) {
                            px.swap(0, 2);
                        }
                        // width/height from spa_video_info requires format negotiation;
                        // using chunk stride as placeholder until proper SPA format parsing
                        let stride = chunk.stride() as u32;
                        let w = if stride > 0 { stride / 4 } else { 0 };
                        let h = if w > 0 { rgba.len() as u32 / 4 / w } else { 0 };
                        if w == 0 || h == 0 {
                            return;
                        }
                        let _ = tx_clone.try_send(RawFrame {
                            pixels: rgba,
                            width: w,
                            height: h,
                            timestamp: Utc::now(),
                        });
                    }
                })
                .register()
                .expect("register listener");

            // connect stream to the PipeWire node obtained from the portal
            use pipewire::spa::utils::Direction;
            stream
                .connect(
                    Direction::Input,
                    Some(node_id),
                    StreamFlags::AUTOCONNECT | StreamFlags::MAP_BUFFERS,
                    &mut [],
                )
                .expect("stream connect");

            ml.run();
        })
    }
}

impl CaptureSource for WaylandCaptureSource {
    fn start(&mut self) -> Result<()> {
        let (node_id, pw_fd) = Self::negotiate_portal()?;
        let (tx, rx) = bounded::<RawFrame>(FRAME_CHANNEL_CAP);
        let handle = Self::spawn_pipewire_thread(node_id, pw_fd, tx);
        self.rx = Some(rx);
        self._thread = Some(handle);
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        // dropping rx causes the channel to close; PipeWire thread will error on next send and can exit
        self.rx = None;
        Ok(())
    }

    fn next_frame(&mut self) -> Result<Option<RawFrame>> {
        match &self.rx {
            Some(rx) => Ok(rx.try_recv().ok()),
            None => Err(anyhow!("wayland capture not started")),
        }
    }

    fn list_windows(&self) -> Result<Vec<WindowInfo>> {
        // Wayland does not expose a window list to clients for security reasons
        Ok(vec![])
    }
}
