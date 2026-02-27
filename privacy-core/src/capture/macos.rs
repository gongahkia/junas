#![cfg(target_os = "macos")]

use anyhow::{anyhow, Result};
use chrono::Utc;
use core_media_rs::cm_sample_buffer::CMSampleBuffer;
use core_video_rs::cv_pixel_buffer::lock::LockTrait;
use crossbeam_channel::{bounded, Receiver, Sender};
use privacy_common::frame::{RawFrame, Rect, WindowInfo};
use screencapturekit::{
    shareable_content::SCShareableContent,
    stream::{
        configuration::{pixel_format::PixelFormat, SCStreamConfiguration},
        content_filter::SCContentFilter,
        delegate_trait::SCStreamDelegateTrait,
        output_trait::SCStreamOutputTrait,
        output_type::SCStreamOutputType,
        SCStream,
    },
};

use super::CaptureSource;

const FRAME_CHANNEL_CAP: usize = 4;

struct FrameHandler {
    tx: Sender<RawFrame>,
}

impl SCStreamOutputTrait for FrameHandler {
    fn did_output_sample_buffer(&self, sample: CMSampleBuffer, of_type: SCStreamOutputType) {
        if of_type != SCStreamOutputType::Screen {
            return;
        }
        let px = match sample.get_pixel_buffer() {
            Ok(p) => p,
            Err(_) => return,
        };
        let w = px.get_width();
        let h = px.get_height();
        let guard = match px.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        let bgra: &[u8] = &guard;
        // BGRA → RGBA: swap bytes 0 and 2 in every 4-byte pixel
        let mut rgba = bgra.to_vec();
        for chunk in rgba.chunks_exact_mut(4) {
            chunk.swap(0, 2);
        }
        let _ = self.tx.try_send(RawFrame {
            pixels: rgba,
            width: w,
            height: h,
            timestamp: Utc::now(),
        });
    }
}

struct NullDelegate;
impl SCStreamDelegateTrait for NullDelegate {}

pub struct MacosCaptureSource {
    pub fps: u32,
    pub target: CaptureTarget,
    stream: Option<SCStream>,
    rx: Option<Receiver<RawFrame>>,
}

#[derive(Clone)]
pub enum CaptureTarget {
    Window(u64),
    Display(usize), // index into SCShareableContent::displays()
}

impl MacosCaptureSource {
    pub fn new(target: CaptureTarget, fps: u32) -> Self {
        Self {
            fps,
            target,
            stream: None,
            rx: None,
        }
    }
}

impl CaptureSource for MacosCaptureSource {
    fn start(&mut self) -> Result<()> {
        let content =
            SCShareableContent::get().map_err(|e| anyhow!("SCShareableContent::get: {:?}", e))?;

        let (filter, w, h) = match &self.target {
            CaptureTarget::Window(wid) => {
                let win = content
                    .windows()
                    .into_iter()
                    .find(|w| w.window_id() as u64 == *wid)
                    .ok_or_else(|| anyhow!("window {} not found", wid))?;
                let f = win.get_frame();
                let filter = SCContentFilter::new().with_desktop_independent_window(&win);
                (filter, f.size.width as u32, f.size.height as u32)
            }
            CaptureTarget::Display(idx) => {
                let displays = content.displays();
                let disp = displays
                    .get(*idx)
                    .ok_or_else(|| anyhow!("display {} not found", idx))?;
                let filter = SCContentFilter::new().with_display_excluding_windows(disp, &[]);
                (filter, disp.width(), disp.height())
            }
        };

        let config = SCStreamConfiguration::new()
            .set_width(w)
            .map_err(|e| anyhow!("{:?}", e))?
            .set_height(h)
            .map_err(|e| anyhow!("{:?}", e))?
            .set_pixel_format(PixelFormat::BGRA)
            .map_err(|e| anyhow!("{:?}", e))?
            .set_shows_cursor(false)
            .map_err(|e| anyhow!("{:?}", e))?
            .set_queue_depth(FRAME_CHANNEL_CAP as u32)
            .map_err(|e| anyhow!("{:?}", e))?;

        let (tx, rx) = bounded::<RawFrame>(FRAME_CHANNEL_CAP);
        let mut stream = SCStream::new_with_delegate(&filter, &config, NullDelegate);
        stream.add_output_handler(FrameHandler { tx }, SCStreamOutputType::Screen);
        stream
            .start_capture()
            .map_err(|e| anyhow!("start_capture: {:?}", e))?;

        self.stream = Some(stream);
        self.rx = Some(rx);
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        if let Some(s) = self.stream.take() {
            s.stop_capture().map_err(|e| anyhow!("{:?}", e))?;
        }
        self.rx = None;
        Ok(())
    }

    fn next_frame(&mut self) -> Result<Option<RawFrame>> {
        match &self.rx {
            Some(rx) => Ok(rx.try_recv().ok()),
            None => Err(anyhow!("stream not started")),
        }
    }

    fn list_windows(&self) -> Result<Vec<WindowInfo>> {
        let content = SCShareableContent::with_options()
            .on_screen_windows_only()
            .get()
            .map_err(|e| anyhow!("{:?}", e))?;
        Ok(content
            .windows()
            .into_iter()
            .map(|w| {
                let f = w.get_frame();
                WindowInfo {
                    id: w.window_id() as u64,
                    title: w.title(),
                    bounds: Rect {
                        x: f.origin.x as u32,
                        y: f.origin.y as u32,
                        width: f.size.width as u32,
                        height: f.size.height as u32,
                    },
                }
            })
            .collect())
    }
}
