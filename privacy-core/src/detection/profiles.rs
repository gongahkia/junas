//! Foreground-app detector profiles.
//!
//! Profiles intentionally control detector pattern enablement only. They do not
//! change capture strategy or inspect browser DOM; the browser profile remains
//! an OCR-based fallback so it fits Aki's pixel-first architecture.

use privacy_common::detection::PatternCategory;

use super::patterns::PatternRegistry;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DetectorProfileKind {
    Broad,
    Secrets,
    Pii,
    Browser,
}

impl DetectorProfileKind {
    pub fn name(self) -> &'static str {
        match self {
            Self::Broad => "broad",
            Self::Secrets => "secrets",
            Self::Pii => "pii",
            Self::Browser => "browser",
        }
    }

    pub fn description(self) -> &'static str {
        match self {
            Self::Broad => "all default secret and PII detectors",
            Self::Secrets => "secret-heavy rules for terminals and shells",
            Self::Pii => "email and PII rules for chat surfaces",
            Self::Browser => "broad OCR profile for browsers; no DOM inspection",
        }
    }
}

pub fn detector_profile_from_name(name: &str) -> Option<DetectorProfileKind> {
    match name.trim().to_ascii_lowercase().as_str() {
        "broad" | "editor" | "default" => Some(DetectorProfileKind::Broad),
        "secrets" | "terminal" | "terminals" => Some(DetectorProfileKind::Secrets),
        "pii" | "chat" | "slack" | "discord" => Some(DetectorProfileKind::Pii),
        "browser" | "browsers" => Some(DetectorProfileKind::Browser),
        "" | "auto" => None,
        _ => None,
    }
}

pub fn select_detector_profile(app_name: &str, window_title: &str) -> DetectorProfileKind {
    let haystack = format!("{} {}", app_name, window_title).to_ascii_lowercase();

    if contains_any(
        &haystack,
        &[
            "terminal",
            "iterm",
            "ghostty",
            "alacritty",
            "warp",
            "wezterm",
            "kitty",
            "tmux",
            "zsh",
            "bash",
            "fish",
        ],
    ) {
        return DetectorProfileKind::Secrets;
    }

    if contains_any(&haystack, &["slack", "discord", "messages", "teams"]) {
        return DetectorProfileKind::Pii;
    }

    if contains_any(
        &haystack,
        &[
            "visual studio code",
            "vscode",
            "vs code",
            "cursor",
            "xcode",
            "zed",
        ],
    ) {
        return DetectorProfileKind::Broad;
    }

    if contains_any(
        &haystack,
        &[
            "safari", "chrome", "firefox", "arc", "brave", "edge", "browser",
        ],
    ) {
        return DetectorProfileKind::Browser;
    }

    DetectorProfileKind::Broad
}

pub fn apply_detector_profile(registry: &mut PatternRegistry, profile: DetectorProfileKind) {
    for pattern in &mut registry.patterns {
        pattern.enabled = match profile {
            DetectorProfileKind::Broad => true,
            DetectorProfileKind::Secrets => matches!(
                pattern.category,
                PatternCategory::EnvVar
                    | PatternCategory::Token
                    | PatternCategory::Password
                    | PatternCategory::ApiKey
            ),
            DetectorProfileKind::Pii => matches!(pattern.category, PatternCategory::Pii),
            DetectorProfileKind::Browser => true,
        };
    }
}

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| haystack.contains(needle))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::detection::{registry::runtime_registry, scanner::scan, whitelist::Whitelist};
    use privacy_common::{detection::TextRegion, frame::Rect};

    #[test]
    fn classifies_terminals_as_secrets() {
        assert_eq!(
            select_detector_profile("Ghostty", "zsh - project"),
            DetectorProfileKind::Secrets
        );
    }

    #[test]
    fn classifies_chat_as_pii() {
        assert_eq!(
            select_detector_profile("Slack", "general"),
            DetectorProfileKind::Pii
        );
        assert_eq!(
            select_detector_profile("Discord", "support"),
            DetectorProfileKind::Pii
        );
    }

    #[test]
    fn classifies_editors_and_browsers() {
        assert_eq!(
            select_detector_profile("Cursor", "main.rs"),
            DetectorProfileKind::Broad
        );
        assert_eq!(
            select_detector_profile("Safari", "Aki docs"),
            DetectorProfileKind::Browser
        );
    }

    #[test]
    fn pii_profile_disables_secret_patterns() {
        let mut registry = runtime_registry(&crate::config::AppConfig::default());
        apply_detector_profile(&mut registry, DetectorProfileKind::Pii);

        let regions = [text_region(
            "user@example.invalid SECRET_KEY=aki_fixture_value",
        )];
        let matches = scan(&regions, &registry, &Whitelist::empty());

        assert!(matches.iter().any(|m| m.pattern_name == "email"));
        assert!(!matches.iter().any(|m| m.pattern_name == "secret_keyword"));
    }

    #[test]
    fn secrets_profile_disables_pii_patterns() {
        let mut registry = runtime_registry(&crate::config::AppConfig::default());
        apply_detector_profile(&mut registry, DetectorProfileKind::Secrets);

        let regions = [text_region(
            "user@example.invalid SECRET_KEY=aki_fixture_value",
        )];
        let matches = scan(&regions, &registry, &Whitelist::empty());

        assert!(matches
            .iter()
            .any(|m| m.pattern_name == "env_var_assignment"));
        assert!(!matches.iter().any(|m| m.pattern_name == "email"));
    }

    fn text_region(text: &str) -> TextRegion {
        TextRegion {
            text: text.to_string(),
            bounds: Rect {
                x: 0,
                y: 0,
                width: 400,
                height: 40,
            },
            confidence: 99.0,
        }
    }
}
