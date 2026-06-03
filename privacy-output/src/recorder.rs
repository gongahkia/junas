//! Frame recorder: pipes RGBA frames to an ffmpeg subprocess → MP4 output.
//! Start/stop via Recorder::start() / Recorder::stop().

use anyhow::{bail, Context, Result};
use privacy_common::frame::TransformedFrame;
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    time::Instant,
};

use crate::OutputSink;

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
        Self::start_with_overwrite(path, width, height, fps, true)
    }

    pub fn start_with_overwrite(
        path: impl Into<String>,
        width: u32,
        height: u32,
        fps: u32,
        overwrite: bool,
    ) -> Result<Self> {
        let path = path.into();
        let video_size = format!("{}x{}", width, height);
        let fps = fps.to_string();
        let overwrite_flag = if overwrite { "-y" } else { "-n" };
        let mut child = Command::new("ffmpeg")
            .args([
                "-hide_banner",
                "-loglevel",
                "error",
                overwrite_flag,
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgba",
                "-video_size",
                &video_size,
                "-framerate",
                &fps,
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
        let status = self.proc.wait().context("waiting for ffmpeg to finish")?;
        if !status.success() {
            bail!("ffmpeg encoder exited with status {status}");
        }
        Ok(self.path)
    }
}

pub struct Mp4Sink {
    path: PathBuf,
    fps: u32,
    overwrite: bool,
    recorder: Option<Recorder>,
    width: u32,
    height: u32,
}

impl Mp4Sink {
    pub fn new(path: impl Into<PathBuf>, fps: u32, overwrite: bool) -> Result<Self> {
        let path = path.into();
        validate_mp4_output_path(&path, overwrite)?;
        Ok(Self {
            path,
            fps: fps.clamp(1, 240),
            overwrite,
            recorder: None,
            width: 0,
            height: 0,
        })
    }

    pub fn output_path(&self) -> &Path {
        &self.path
    }

    pub fn is_started(&self) -> bool {
        self.recorder.is_some()
    }

    fn start_for_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        validate_frame_shape(frame)?;
        validate_mp4_output_path(&self.path, self.overwrite)?;
        let recorder = Recorder::start_with_overwrite(
            self.path.to_string_lossy().to_string(),
            frame.width,
            frame.height,
            self.fps,
            self.overwrite,
        )?;
        self.width = frame.width;
        self.height = frame.height;
        self.recorder = Some(recorder);
        Ok(())
    }
}

impl OutputSink for Mp4Sink {
    fn write_frame(&mut self, frame: &TransformedFrame) -> Result<()> {
        validate_frame_shape(frame)?;
        if self.recorder.is_none() {
            self.start_for_frame(frame)?;
        }
        if frame.width != self.width || frame.height != self.height {
            bail!(
                "MP4 sink cannot change frame size mid-recording: started at {}x{}, got {}x{}",
                self.width,
                self.height,
                frame.width,
                frame.height
            );
        }
        let recorder = self
            .recorder
            .as_mut()
            .context("MP4 recorder did not start")?;
        recorder.write_frame(frame)
    }

    fn close(&mut self) -> Result<()> {
        if let Some(recorder) = self.recorder.take() {
            recorder.stop()?;
        }
        Ok(())
    }
}

fn validate_mp4_output_path(path: &Path, overwrite: bool) -> Result<()> {
    if path.as_os_str().is_empty() {
        bail!("MP4 output path must be explicit");
    }
    let extension = path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or_default();
    if !extension.eq_ignore_ascii_case("mp4") {
        bail!("MP4 output path must end in .mp4: {}", path.display());
    }
    if path.is_dir() {
        bail!("MP4 output path is a directory: {}", path.display());
    }
    if path.exists() && !overwrite {
        bail!(
            "MP4 output already exists: {} (pass --record-overwrite to replace it)",
            path.display()
        );
    }
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)
                .with_context(|| format!("creating MP4 output directory {}", parent.display()))?;
        }
    }
    Ok(())
}

fn validate_frame_shape(frame: &TransformedFrame) -> Result<()> {
    let expected = frame
        .width
        .checked_mul(frame.height)
        .and_then(|pixels| pixels.checked_mul(4))
        .context("MP4 frame dimensions are too large")? as usize;
    if frame.pixels.len() != expected {
        bail!(
            "invalid RGBA frame for MP4 sink: {} bytes for {}x{} frame, expected {}",
            frame.pixels.len(),
            frame.width,
            frame.height,
            expected
        );
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Stdio;
    use tempfile::tempdir;

    #[test]
    fn mp4_sink_requires_mp4_extension() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("recording.mov");

        assert!(Mp4Sink::new(path, 30, false).is_err());
    }

    #[test]
    fn mp4_sink_rejects_existing_output_without_overwrite() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("recording.mp4");
        fs::write(&path, b"existing").unwrap();

        assert!(Mp4Sink::new(&path, 30, false).is_err());
        assert!(Mp4Sink::new(&path, 30, true).is_ok());
    }

    #[test]
    fn mp4_sink_starts_lazily() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("nested").join("recording.mp4");
        let mut sink = Mp4Sink::new(&path, 30, false).unwrap();

        assert_eq!(sink.output_path(), path.as_path());
        assert!(!sink.is_started());
        assert!(!path.exists());
        sink.close().unwrap();
        assert!(!path.exists());
    }

    #[test]
    fn mp4_sink_writes_generated_frame_when_ffmpeg_available() {
        if !tool_available("ffmpeg") {
            eprintln!("skipping MP4 sink smoke test because ffmpeg is unavailable");
            return;
        }

        let dir = tempdir().unwrap();
        let path = dir.path().join("recording.mp4");
        let mut sink = Mp4Sink::new(&path, 1, false).unwrap();
        let frame = solid_frame(64, 48);

        sink.write_frame(&frame).unwrap();
        assert!(sink.is_started());
        sink.close().unwrap();

        assert!(path.exists());
        assert!(fs::metadata(path).unwrap().len() > 0);
    }

    fn solid_frame(width: u32, height: u32) -> TransformedFrame {
        TransformedFrame {
            pixels: vec![200u8; (width * height * 4) as usize],
            width,
            height,
            timestamp: chrono::Utc::now(),
        }
    }

    fn tool_available(name: &str) -> bool {
        Command::new(name)
            .arg("-version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}
