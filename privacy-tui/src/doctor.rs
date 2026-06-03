use anyhow::Result;
use privacy_core::{config::AppConfig, detection::ocr::OcrEngine};
use std::{
    fmt,
    net::{SocketAddr, TcpStream},
    path::Path,
    time::Duration,
};

pub(crate) struct DoctorOptions {
    pub check_obs: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DoctorStatus {
    Pass,
    Warn,
    Fail,
}

impl DoctorStatus {
    fn label(self) -> &'static str {
        match self {
            Self::Pass => "PASS",
            Self::Warn => "WARN",
            Self::Fail => "FAIL",
        }
    }
}

impl fmt::Display for DoctorStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.label())
    }
}

#[derive(Debug, Clone)]
struct DoctorCheck {
    status: DoctorStatus,
    name: &'static str,
    detail: String,
    remediation: &'static str,
}

impl DoctorCheck {
    fn pass(name: &'static str, detail: impl Into<String>, remediation: &'static str) -> Self {
        Self {
            status: DoctorStatus::Pass,
            name,
            detail: detail.into(),
            remediation,
        }
    }

    fn warn(name: &'static str, detail: impl Into<String>, remediation: &'static str) -> Self {
        Self {
            status: DoctorStatus::Warn,
            name,
            detail: detail.into(),
            remediation,
        }
    }

    fn fail(name: &'static str, detail: impl Into<String>, remediation: &'static str) -> Self {
        Self {
            status: DoctorStatus::Fail,
            name,
            detail: detail.into(),
            remediation,
        }
    }
}

pub(crate) fn run_doctor(options: DoctorOptions) -> Result<()> {
    let cfg = AppConfig::load().unwrap_or_default();
    let checks = build_checks(&cfg, options.check_obs);
    print_report(&checks);
    Ok(())
}

fn build_checks(cfg: &AppConfig, force_obs: bool) -> Vec<DoctorCheck> {
    vec![
        check_local_only(force_obs),
        check_tesseract_data(),
        check_screen_capture_permission(),
        check_coremedia_dal(),
        check_virtual_camera(),
        check_obs_reachability(cfg, force_obs),
    ]
}

fn print_report(checks: &[DoctorCheck]) {
    println!("Aki doctor (local-only diagnostics)");
    println!("No telemetry is collected or uploaded. Screen pixels and OCR text are not printed.");
    println!();
    for check in checks {
        println!("{:<4} {}", check.status, check.name);
        println!("     {}", check.detail);
        if !check.remediation.is_empty() {
            println!("     fix: {}", check.remediation);
        }
    }
    println!();
    let pass = checks
        .iter()
        .filter(|c| c.status == DoctorStatus::Pass)
        .count();
    let warn = checks
        .iter()
        .filter(|c| c.status == DoctorStatus::Warn)
        .count();
    let fail = checks
        .iter()
        .filter(|c| c.status == DoctorStatus::Fail)
        .count();
    println!("Summary: {pass} pass, {warn} warn, {fail} fail");
}

fn check_local_only(force_obs: bool) -> DoctorCheck {
    let detail = if force_obs {
        "Doctor runs locally; --obs only opens a TCP connection to 127.0.0.1:4455."
    } else {
        "Doctor runs locally and does not send diagnostics, screenshots, OCR text, or logs."
    };
    DoctorCheck::pass("Telemetry", detail, "")
}

fn check_tesseract_data() -> DoctorCheck {
    let path_hint = tessdata_path_hint();
    match OcrEngine::new(None) {
        Ok(_) => DoctorCheck::pass(
            "Tesseract data path",
            format!("Tesseract initialized successfully. {path_hint}"),
            "If OCR later fails, install tesseract data and set TESSDATA_PREFIX to the tessdata directory.",
        ),
        Err(error) => DoctorCheck::fail(
            "Tesseract data path",
            format!("Tesseract could not initialize English OCR: {error:#}. {path_hint}"),
            "Install Tesseract and English traineddata. On macOS: `brew install tesseract`. On Ubuntu: `sudo apt-get install tesseract-ocr`.",
        ),
    }
}

fn tessdata_path_hint() -> String {
    if let Ok(prefix) = std::env::var("TESSDATA_PREFIX") {
        return format!("TESSDATA_PREFIX is set to {prefix}.");
    }
    let candidates = [
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tessdata",
    ];
    if let Some(path) = candidates.iter().find(|p| {
        let eng = Path::new(p).join("eng.traineddata");
        eng.exists()
    }) {
        return format!("Found English traineddata at {path}.");
    }
    "No common tessdata directory was found; relying on Tesseract defaults.".to_string()
}

#[cfg(target_os = "macos")]
fn check_screen_capture_permission() -> DoctorCheck {
    match privacy_core::capture::window_picker::list_windows() {
        Ok(windows) if !windows.is_empty() => DoctorCheck::pass(
            "ScreenCaptureKit permission",
            format!("ScreenCaptureKit can enumerate {} capturable window(s).", windows.len()),
            "",
        ),
        Ok(_) => DoctorCheck::warn(
            "ScreenCaptureKit permission",
            "ScreenCaptureKit returned no capturable windows.",
            "Open System Settings > Privacy & Security > Screen Recording and allow the terminal or Aki app, then restart it.",
        ),
        Err(error) => DoctorCheck::fail(
            "ScreenCaptureKit permission",
            format!("Could not enumerate capturable windows: {error:#}."),
            "Grant Screen Recording permission to the terminal or Aki app, then run `aki list-windows` to confirm.",
        ),
    }
}

#[cfg(not(target_os = "macos"))]
fn check_screen_capture_permission() -> DoctorCheck {
    DoctorCheck::warn(
        "ScreenCaptureKit permission",
        "ScreenCaptureKit is macOS-only and is not required on this platform.",
        "On macOS, grant Screen Recording permission to the terminal or Aki app before using screen capture.",
    )
}

#[cfg(target_os = "macos")]
fn check_coremedia_dal() -> DoctorCheck {
    let dal_dir = Path::new("/Library/CoreMediaIO/Plug-Ins/DAL");
    if dal_dir.is_dir() {
        DoctorCheck::pass(
            "CoreMediaIO DAL state",
            format!("CoreMediaIO DAL directory exists at {}.", dal_dir.display()),
            "",
        )
    } else {
        DoctorCheck::warn(
            "CoreMediaIO DAL state",
            format!(
                "CoreMediaIO DAL directory is missing at {}.",
                dal_dir.display()
            ),
            "Install OBS Virtual Camera or use `--output mjpeg` as a browser-source fallback.",
        )
    }
}

#[cfg(not(target_os = "macos"))]
fn check_coremedia_dal() -> DoctorCheck {
    DoctorCheck::warn(
        "CoreMediaIO DAL state",
        "CoreMediaIO DAL is macOS-only and is not required on this platform.",
        "On macOS, install OBS Virtual Camera if you need virtual-camera output.",
    )
}

#[cfg(target_os = "macos")]
fn check_virtual_camera() -> DoctorCheck {
    if privacy_output::coremedia::CoreMediaSink::is_available() {
        DoctorCheck::pass(
            "Virtual camera installation",
            "A compatible OBS/CoreMediaIO virtual camera plugin was found.",
            "",
        )
    } else {
        DoctorCheck::warn(
            "Virtual camera installation",
            "No compatible OBS/CoreMediaIO virtual camera plugin was found.",
            "Install OBS Virtual Camera, then restart Aki. If you do not need a virtual camera, use MJPEG output.",
        )
    }
}

#[cfg(target_os = "linux")]
fn check_virtual_camera() -> DoctorCheck {
    if let Some(path) = find_v4l2_loopback() {
        DoctorCheck::pass(
            "Virtual camera installation",
            format!("Found v4l2loopback device at {path}."),
            "",
        )
    } else {
        DoctorCheck::warn(
            "Virtual camera installation",
            "No v4l2loopback device was found under /sys/class/video4linux.",
            "Install and load v4l2loopback, or use MJPEG output if a virtual camera is not required.",
        )
    }
}

#[cfg(not(any(target_os = "macos", target_os = "linux")))]
fn check_virtual_camera() -> DoctorCheck {
    DoctorCheck::warn(
        "Virtual camera installation",
        "No platform-specific virtual-camera check is implemented for this OS.",
        "Use MJPEG output if a native virtual camera is unavailable.",
    )
}

#[cfg(target_os = "linux")]
fn find_v4l2_loopback() -> Option<String> {
    let entries = std::fs::read_dir("/sys/class/video4linux").ok()?;
    for entry in entries.flatten() {
        let name_file = entry.path().join("name");
        if let Ok(name) = std::fs::read_to_string(&name_file) {
            if name.trim().contains("Dummy") || name.trim().contains("v4l2loopback") {
                let dev = format!("/dev/{}", entry.file_name().to_string_lossy());
                if Path::new(&dev).exists() {
                    return Some(dev);
                }
            }
        }
    }
    None
}

fn check_obs_reachability(cfg: &AppConfig, force_obs: bool) -> DoctorCheck {
    let configured_for_obs = cfg.output.sink.eq_ignore_ascii_case("obs");
    if !force_obs && !configured_for_obs {
        return DoctorCheck::warn(
            "OBS WebSocket reachability",
            "OBS output is not configured, so the local OBS reachability check was skipped.",
            "Run `aki doctor --obs` when using OBS, and enable OBS WebSocket on 127.0.0.1:4455.",
        );
    }

    let addr = SocketAddr::from(([127, 0, 0, 1], 4455));
    match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(_) => DoctorCheck::pass(
            "OBS WebSocket reachability",
            "Reached OBS WebSocket at 127.0.0.1:4455.",
            "",
        ),
        Err(error) => DoctorCheck::warn(
            "OBS WebSocket reachability",
            format!("Could not reach OBS WebSocket at 127.0.0.1:4455: {error}."),
            "Start OBS and enable Tools > WebSocket Server Settings, or use MJPEG output without OBS automation.",
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_labels_are_stable() {
        assert_eq!(DoctorStatus::Pass.label(), "PASS");
        assert_eq!(DoctorStatus::Warn.label(), "WARN");
        assert_eq!(DoctorStatus::Fail.label(), "FAIL");
    }

    #[test]
    fn obs_check_skips_when_not_relevant() {
        let cfg = AppConfig::default();
        let check = check_obs_reachability(&cfg, false);
        assert_eq!(check.status, DoctorStatus::Warn);
        assert_eq!(check.name, "OBS WebSocket reachability");
        assert!(check.detail.contains("skipped"));
    }

    #[test]
    fn local_only_check_mentions_no_uploads() {
        let check = check_local_only(false);
        assert_eq!(check.status, DoctorStatus::Pass);
        assert!(check.detail.contains("does not send diagnostics"));
    }
}
