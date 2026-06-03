use anyhow::Result;
use std::{
    io::{self, Write},
    thread,
    time::Duration,
};

pub(crate) struct DemoOptions {
    pub frames: u32,
    pub interval_ms: u64,
    pub no_clear: bool,
}

const FAKE_ROWS: &[&str] = &[
    "DEMO_SECRET_KEY=AKI_FAKE_SECRET_DO_NOT_USE_0001",
    "DEMO_API_TOKEN=AKI_FAKE_TOKEN_DO_NOT_USE_0002",
    "DEMO_PASSWORD=AKI_FAKE_PASSWORD_DO_NOT_USE_0003",
    "DEMO_EMAIL=demo-user@example.invalid",
    "DEMO_IPV4=203.0.113.42",
    "DEMO_IPV6=2001:db8::42",
    "DEMO_JWT=AKI_FAKE_HEADER.AKI_FAKE_PAYLOAD.AKI_FAKE_SIGNATURE",
    "DEMO_NOTE=all values on this screen are fake fixtures",
];
const VALUE_WIDTH: usize = 72;
const BORDER: &str =
    "+--------------------------------------------------------------------------+\n";

pub(crate) fn run_demo(options: DemoOptions) -> Result<()> {
    let mut stdout = io::stdout();
    let mut frame = 0u32;
    loop {
        if !options.no_clear {
            write!(stdout, "\x1b[2J\x1b[H")?;
        }
        write!(stdout, "{}", render_demo_frame(frame))?;
        stdout.flush()?;

        frame = frame.wrapping_add(1);
        if options.frames > 0 && frame >= options.frames {
            break;
        }
        if options.interval_ms > 0 {
            thread::sleep(Duration::from_millis(options.interval_ms));
        }
    }
    Ok(())
}

pub(crate) fn render_demo_frame(frame: u32) -> String {
    let offset = (frame as usize) % FAKE_ROWS.len();
    let mut out = String::new();
    out.push_str("AKI DEMO - FAKE SECRET REPRODUCTION SOURCE\n");
    out.push_str("All values are deterministic fake fixtures. Do not paste real secrets here.\n\n");
    out.push_str(&format!("frame={frame:04}  mode=rolling-fixtures\n"));
    out.push_str(BORDER);
    for row_idx in 0..FAKE_ROWS.len() {
        let value = FAKE_ROWS[(offset + row_idx) % FAKE_ROWS.len()];
        out.push_str(&format!("| {value:<width$} |\n", width = VALUE_WIDTH));
    }
    out.push_str(BORDER);
    out.push('\n');
    out.push_str(
        "Use this terminal window as a safe screen-share, screenshot, or bug-report fixture.\n",
    );
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::{detection::TextRegion, frame::Rect};
    use privacy_core::{
        config::AppConfig,
        detection::{registry::runtime_registry, scanner::scan, whitelist::Whitelist},
    };

    #[test]
    fn frame_rendering_is_deterministic() {
        assert_eq!(render_demo_frame(3), render_demo_frame(3));
    }

    #[test]
    fn frame_marks_values_as_fake() {
        let frame = render_demo_frame(0);
        assert!(frame.contains("AKI DEMO"));
        assert!(frame.contains("FAKE"));
        assert!(frame.contains("AKI_FAKE_SECRET_DO_NOT_USE"));
        assert!(frame.contains("example.invalid"));
        assert!(frame.contains("203.0.113.42"));
    }

    #[test]
    fn rolling_frame_changes_row_order() {
        assert_ne!(render_demo_frame(0), render_demo_frame(1));
    }

    #[test]
    fn frame_text_matches_default_detector_registry() {
        let text = render_demo_frame(0);
        let regions = [TextRegion {
            text,
            bounds: Rect {
                x: 0,
                y: 0,
                width: 800,
                height: 300,
            },
            confidence: 99.0,
        }];
        let registry = runtime_registry(&AppConfig::default());
        let matches = scan(&regions, &registry, &Whitelist::empty());

        assert!(matches.iter().any(|m| m.pattern_name == "secret_keyword"));
        assert!(matches.iter().any(|m| m.pattern_name == "email"));
        assert!(matches.iter().any(|m| m.pattern_name == "ipv4"));
    }
}
