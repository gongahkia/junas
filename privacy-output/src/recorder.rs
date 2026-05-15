//! Frame recorder: pipes RGBA frames to an ffmpeg subprocess → MP4 output.
//! Start/stop via Recorder::start() / Recorder::stop().

use anyhow::{Context, Result};
use privacy_common::frame::TransformedFrame;
use std::{
    io::Write,
    process::{Child, ChildStdin, Command, Stdio},
    time::Instant,
};

pub struct Recorder {
    proc: Child,
    stdin: ChildStdin,
    pub path: String,
    pub started_at: Instant,
}

impl Recorder {
    /// Spawn an ffmpeg process writing to `path` (e.g. "recording.mp4").
    /// `width`/`height` must match the frames that will be fed via `write_frame`.
    pub fn start(path: impl Into<String>, width: u32, height: u32, fps: u32) -> Result<Self> {
        let path = path.into();
        let mut child = Command::new("ffmpeg")
            .args([
                "-y", // overwrite output
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgba",
                "-video_size",
                &format!("{}x{}", width, height),
                "-framerate",
                &fps.to_string(),
                "-i",
                "pipe:0", // read from stdin
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "23",
                &path,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .context("spawning ffmpeg — ensure ffmpeg is installed")?;
        let stdin = child.stdin.take().context("ffmpeg stdin unavailable")?;
        Ok(Self {
            proc: child,
            stdin,
            path,
            started_at: Instant::now(),
        })
    }

    /// Feed a frame to ffmpeg's stdin.
    pub fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        self.stdin
            .write_all(&frame.pixels)
            .context("writing frame to ffmpeg")?;
        Ok(())
    }

    /// Flush stdin, wait for ffmpeg to finish encoding.
    pub fn stop(mut self) -> Result<String> {
        drop(self.stdin); // close stdin → ffmpeg will flush and exit
        self.proc.wait().context("waiting for ffmpeg to finish")?;
        Ok(self.path)
    }
}
