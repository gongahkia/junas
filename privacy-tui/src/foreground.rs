#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct ForegroundContext {
    pub app_name: String,
    pub window_title: String,
}

impl ForegroundContext {
    pub(crate) fn terminal_pty() -> Self {
        Self {
            app_name: "Terminal".to_string(),
            window_title: "pty".to_string(),
        }
    }

    pub(crate) fn fallback(window_title: Option<&str>) -> Self {
        Self {
            app_name: String::new(),
            window_title: window_title.unwrap_or_default().to_string(),
        }
    }
}

pub(crate) fn detect(selected_window_title: Option<&str>) -> ForegroundContext {
    detect_platform().unwrap_or_else(|| ForegroundContext::fallback(selected_window_title))
}

#[cfg(target_os = "macos")]
fn detect_platform() -> Option<ForegroundContext> {
    use std::process::Command;

    let output = Command::new("osascript")
        .args([
            "-e",
            "tell application \"System Events\"",
            "-e",
            "set frontApp to first application process whose frontmost is true",
            "-e",
            "set appName to name of frontApp",
            "-e",
            "set windowName to \"\"",
            "-e",
            "try",
            "-e",
            "set windowName to name of front window of frontApp",
            "-e",
            "end try",
            "-e",
            "return appName & linefeed & windowName",
            "-e",
            "end tell",
        ])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    parse_osascript_output(&String::from_utf8_lossy(&output.stdout))
}

#[cfg(not(target_os = "macos"))]
fn detect_platform() -> Option<ForegroundContext> {
    None
}

#[cfg(target_os = "macos")]
fn parse_osascript_output(raw: &str) -> Option<ForegroundContext> {
    let mut lines = raw.lines();
    let app_name = lines.next().unwrap_or_default().trim().to_string();
    let window_title = lines.next().unwrap_or_default().trim().to_string();
    if app_name.is_empty() && window_title.is_empty() {
        return None;
    }
    Some(ForegroundContext {
        app_name,
        window_title,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fallback_uses_selected_window_title() {
        let ctx = ForegroundContext::fallback(Some("main.rs - Cursor"));
        assert_eq!(ctx.app_name, "");
        assert_eq!(ctx.window_title, "main.rs - Cursor");
    }

    #[test]
    fn pty_context_classifies_as_terminal_like_text() {
        let ctx = ForegroundContext::terminal_pty();
        assert_eq!(ctx.app_name, "Terminal");
        assert_eq!(ctx.window_title, "pty");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn parses_osascript_output() {
        let ctx = parse_osascript_output("Safari\nAki docs\n").unwrap();
        assert_eq!(ctx.app_name, "Safari");
        assert_eq!(ctx.window_title, "Aki docs");
    }
}
