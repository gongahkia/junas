use anyhow::{anyhow, bail, Context, Result};
use privacy_common::{
    detection::{DetectedRegions, TextRegion},
    frame::{RawFrame, TransformedFrame},
    transform::TransformMode,
};
use privacy_core::{
    config::AppConfig,
    detection::{
        expand::expand_and_merge, line_expand::expand_to_end_of_line, ocr::OcrEngine,
        registry::runtime_registry, scanner::scan, whitelist::Whitelist,
    },
    transform::registry::apply_transform,
};
use serde::Deserialize;
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

pub(crate) struct RedactOptions {
    pub input: PathBuf,
    pub output: Option<PathBuf>,
    pub transform_mode: TransformMode,
    pub intensity: f32,
    pub overwrite: bool,
    pub config: AppConfig,
}

pub(crate) struct RedactSummary {
    pub output: PathBuf,
    pub frames: u64,
    pub detected_regions: u64,
}

#[derive(Debug, Clone)]
struct VideoInfo {
    width: u32,
    height: u32,
    fps: f64,
}

#[derive(Debug, Deserialize)]
struct ProbeOutput {
    streams: Vec<ProbeStream>,
}

#[derive(Debug, Deserialize)]
struct ProbeStream {
    width: Option<u32>,
    height: Option<u32>,
    avg_frame_rate: Option<String>,
    r_frame_rate: Option<String>,
}

pub(crate) fn redact_video(options: RedactOptions) -> Result<RedactSummary> {
    if !options.input.exists() {
        bail!("input video does not exist: {}", options.input.display());
    }
    if !options.input.is_file() {
        bail!("input path is not a file: {}", options.input.display());
    }

    let output = options
        .output
        .unwrap_or_else(|| default_output_path(&options.input));
    ensure_output_allowed(&options.input, &output, options.overwrite)?;

    let info = probe_video(&options.input)?;
    let mut decoder = spawn_decoder(&options.input)?;
    let stdout = decoder
        .stdout
        .as_mut()
        .context("ffmpeg decoder stdout unavailable")?;
    let frame_size = frame_size(info.width, info.height)?;
    let mut recorder = privacy_output::recorder::Recorder::start(
        output.to_string_lossy().to_string(),
        info.width,
        info.height,
        rounded_fps(info.fps),
    )?;

    let registry = runtime_registry(&options.config);
    let whitelist = Whitelist::load().unwrap_or_else(|_| Whitelist::empty());
    let min_conf = options.config.detection.min_confidence as f32;
    let mut ocr = OcrEngine::new_with_confidence(None, min_conf)?;
    let mut frames = 0u64;
    let mut detected_regions = 0u64;

    loop {
        let mut pixels = vec![0u8; frame_size];
        if !read_exact_frame(stdout, &mut pixels)? {
            break;
        }

        let frame = RawFrame {
            pixels,
            width: info.width,
            height: info.height,
            timestamp: chrono::Utc::now(),
        };
        let (transformed, regions) = redact_frame_with_ocr(
            &frame,
            &mut ocr,
            &registry,
            &whitelist,
            options.transform_mode,
            options.intensity,
        )?;
        detected_regions += regions as u64;
        recorder.write_frame(&transformed)?;
        frames += 1;
    }

    let decoder_status = decoder.wait().context("waiting for ffmpeg decoder")?;
    let saved = PathBuf::from(recorder.stop()?);
    if !decoder_status.success() {
        bail!("ffmpeg decoder exited with status {decoder_status}");
    }
    if frames == 0 {
        let _ = fs::remove_file(&saved);
        bail!("input video contained no decodable frames");
    }

    Ok(RedactSummary {
        output: saved,
        frames,
        detected_regions,
    })
}

fn default_output_path(input: &Path) -> PathBuf {
    let parent = input.parent().unwrap_or_else(|| Path::new(""));
    let stem = input
        .file_stem()
        .and_then(|s| s.to_str())
        .filter(|s| !s.is_empty())
        .unwrap_or("video");
    let ext = input
        .extension()
        .and_then(|s| s.to_str())
        .filter(|s| !s.is_empty())
        .unwrap_or("mp4");
    parent.join(format!("{stem}.redacted.{ext}"))
}

fn ensure_output_allowed(input: &Path, output: &Path, overwrite: bool) -> Result<()> {
    if paths_refer_to_same_file(input, output) {
        bail!(
            "refusing to overwrite input video; choose a different --output path: {}",
            output.display()
        );
    }
    if output.exists() && !overwrite {
        bail!(
            "output already exists: {} (pass --overwrite to replace it)",
            output.display()
        );
    }
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() && !parent.exists() {
            fs::create_dir_all(parent)
                .with_context(|| format!("creating output directory {}", parent.display()))?;
        }
    }
    Ok(())
}

fn paths_refer_to_same_file(input: &Path, output: &Path) -> bool {
    match (input.canonicalize(), output.canonicalize()) {
        (Ok(a), Ok(b)) => a == b,
        _ => input == output,
    }
}

fn probe_video(input: &Path) -> Result<VideoInfo> {
    let output = Command::new("ffprobe")
        .args([
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,r_frame_rate",
            "-of",
            "json",
        ])
        .arg(input)
        .output()
        .context("running ffprobe - install ffmpeg/ffprobe to use `aki redact`")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!("ffprobe failed for {}: {}", input.display(), stderr.trim());
    }

    let probe: ProbeOutput =
        serde_json::from_slice(&output.stdout).context("parsing ffprobe JSON output")?;
    let stream = probe
        .streams
        .first()
        .ok_or_else(|| anyhow!("no video stream found in {}", input.display()))?;
    let width = stream
        .width
        .filter(|w| *w > 0)
        .ok_or_else(|| anyhow!("ffprobe did not report a valid width"))?;
    let height = stream
        .height
        .filter(|h| *h > 0)
        .ok_or_else(|| anyhow!("ffprobe did not report a valid height"))?;
    let fps = stream
        .avg_frame_rate
        .as_deref()
        .and_then(parse_fps)
        .or_else(|| stream.r_frame_rate.as_deref().and_then(parse_fps))
        .unwrap_or(30.0);

    Ok(VideoInfo { width, height, fps })
}

fn parse_fps(raw: &str) -> Option<f64> {
    if let Some((num, den)) = raw.split_once('/') {
        let num = num.parse::<f64>().ok()?;
        let den = den.parse::<f64>().ok()?;
        if den <= 0.0 {
            return None;
        }
        let fps = num / den;
        return (fps > 0.0).then_some(fps);
    }
    let fps = raw.parse::<f64>().ok()?;
    (fps > 0.0).then_some(fps)
}

fn rounded_fps(fps: f64) -> u32 {
    fps.round().clamp(1.0, 240.0) as u32
}

fn spawn_decoder(input: &Path) -> Result<std::process::Child> {
    Command::new("ffmpeg")
        .args(["-hide_banner", "-loglevel", "error", "-i"])
        .arg(input)
        .args([
            "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .context("running ffmpeg decoder - install ffmpeg/ffprobe to use `aki redact`")
}

fn frame_size(width: u32, height: u32) -> Result<usize> {
    let pixels = width
        .checked_mul(height)
        .and_then(|p| p.checked_mul(4))
        .ok_or_else(|| anyhow!("video dimensions are too large: {width}x{height}"))?;
    Ok(pixels as usize)
}

fn read_exact_frame(reader: &mut impl Read, buf: &mut [u8]) -> Result<bool> {
    let mut offset = 0usize;
    while offset < buf.len() {
        match reader
            .read(&mut buf[offset..])
            .context("reading decoded frame")?
        {
            0 if offset == 0 => return Ok(false),
            0 => bail!("ffmpeg decoder ended with a partial frame"),
            n => offset += n,
        }
    }
    Ok(true)
}

fn redact_frame_with_ocr(
    frame: &RawFrame,
    ocr: &mut OcrEngine,
    registry: &privacy_core::detection::patterns::PatternRegistry,
    whitelist: &Whitelist,
    mode: TransformMode,
    intensity: f32,
) -> Result<(TransformedFrame, usize)> {
    let text_regions = ocr.extract(frame).unwrap_or_default();
    redact_frame_with_regions(frame, &text_regions, registry, whitelist, mode, intensity)
}

fn redact_frame_with_regions(
    frame: &RawFrame,
    text_regions: &[TextRegion],
    registry: &privacy_core::detection::patterns::PatternRegistry,
    whitelist: &Whitelist,
    mode: TransformMode,
    intensity: f32,
) -> Result<(TransformedFrame, usize)> {
    let matches = scan(text_regions, registry, whitelist);
    let merged = expand_and_merge(matches, frame.width, frame.height, 0.10);
    let merged = expand_to_end_of_line(merged, frame.width);
    let regions = DetectedRegions { matches: merged };
    let count = regions.matches.len();
    let transformed = apply_transform(frame, &regions, mode, intensity)?;
    Ok((transformed, count))
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::{detection::TextRegion, frame::Rect};
    use privacy_core::detection::{default_patterns::default_registry, whitelist::Whitelist};
    use std::io::Write;
    use tempfile::tempdir;

    #[test]
    fn default_output_inserts_redacted_before_extension() {
        let path = Path::new("/tmp/demo.mov");
        assert_eq!(
            default_output_path(path),
            PathBuf::from("/tmp/demo.redacted.mov")
        );
    }

    #[test]
    fn output_guard_rejects_input_path_and_existing_output_without_overwrite() {
        let dir = tempdir().unwrap();
        let input = dir.path().join("input.mov");
        let output = dir.path().join("input.redacted.mov");
        fs::write(&input, b"input").unwrap();
        fs::write(&output, b"output").unwrap();

        assert!(ensure_output_allowed(&input, &input, true).is_err());
        assert!(ensure_output_allowed(&input, &output, false).is_err());
        assert!(ensure_output_allowed(&input, &output, true).is_ok());
    }

    #[test]
    fn fixture_video_frame_redacts_detected_secret_region() {
        let frame = fixture_video_frame();
        let regions = vec![TextRegion {
            text: "SECRET_KEY=aki_fixture_value".to_string(),
            bounds: Rect {
                x: 8,
                y: 8,
                width: 48,
                height: 24,
            },
            confidence: 99.0,
        }];

        let (redacted, count) = redact_frame_with_regions(
            &frame,
            &regions,
            &default_registry(),
            &Whitelist::empty(),
            TransformMode::Pixelate,
            1.0,
        )
        .unwrap();

        assert_eq!(count, 1);
        assert_ne!(redacted.pixels, frame.pixels);
    }

    #[test]
    fn generated_video_file_is_processed_to_output() {
        if !tool_available("ffmpeg") || !tool_available("ffprobe") {
            eprintln!("skipping offline video test because ffmpeg/ffprobe is unavailable");
            return;
        }

        let dir = tempdir().unwrap();
        let input = dir.path().join("blank.mp4");
        let output = dir.path().join("blank.redacted.mp4");
        write_blank_video(&input).unwrap();

        let summary = redact_video(RedactOptions {
            input,
            output: Some(output.clone()),
            transform_mode: TransformMode::Pixelate,
            intensity: 1.0,
            overwrite: false,
            config: AppConfig::default(),
        })
        .unwrap();

        assert_eq!(summary.frames, 1);
        assert_eq!(summary.detected_regions, 0);
        assert_eq!(summary.output, output);
        assert!(summary.output.exists());
    }

    fn fixture_video_frame() -> RawFrame {
        let width = 80u32;
        let height = 48u32;
        let mut pixels = Vec::with_capacity((width * height * 4) as usize);
        for y in 0..height {
            for x in 0..width {
                pixels.push(((x * 3) % 255) as u8);
                pixels.push(((y * 5) % 255) as u8);
                pixels.push((((x + y) * 2) % 255) as u8);
                pixels.push(255);
            }
        }
        RawFrame {
            pixels,
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

    fn write_blank_video(path: &Path) -> Result<()> {
        let width = 64u32;
        let height = 48u32;
        let mut child = Command::new("ffmpeg")
            .args([
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgba",
                "-video_size",
                &format!("{width}x{height}"),
                "-framerate",
                "1",
                "-i",
                "pipe:0",
                "-frames:v",
                "1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
            ])
            .arg(path)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .context("spawning ffmpeg fixture writer")?;

        let frame = vec![255u8; (width * height * 4) as usize];
        child
            .stdin
            .as_mut()
            .context("ffmpeg fixture stdin unavailable")?
            .write_all(&frame)
            .context("writing fixture frame")?;
        drop(child.stdin.take());
        let status = child.wait().context("waiting for ffmpeg fixture writer")?;
        if !status.success() {
            bail!("ffmpeg fixture writer exited with status {status}");
        }
        Ok(())
    }
}
