//! User-defined custom sensitivity patterns loaded from
//! `~/.config/ascii-privacy/patterns.toml`.
//!
//! File format:
//! ```toml
//! [[pattern]]
//! name = "my_secret"
//! regex = "MY_SECRET=[A-Za-z0-9]+"
//! severity = "high"   # high | medium | low
//! ```

use anyhow::{Context, Result};
use privacy_common::detection::{PatternCategory, Severity};
use serde::Deserialize;
use std::path::{Path, PathBuf};

use super::patterns::SensitivityPattern;

fn config_path() -> PathBuf {
    dirs_or_home().join("ascii-privacy/patterns.toml")
}

fn dirs_or_home() -> PathBuf {
    // prefer XDG_CONFIG_HOME, fall back to ~/.config
    std::env::var("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| dirs_sys_home().join(".config"))
}

fn dirs_sys_home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

#[derive(Deserialize)]
struct PatternFile {
    #[serde(default, rename = "pattern")]
    patterns: Vec<UserPatternEntry>,
}

#[derive(Deserialize)]
struct UserPatternEntry {
    name: String,
    regex: String,
    #[serde(default)]
    severity: SeverityStr,
}

#[derive(Deserialize, Default)]
#[serde(rename_all = "lowercase")]
enum SeverityStr {
    High,
    #[default]
    Medium,
    Low,
}

impl From<SeverityStr> for Severity {
    fn from(s: SeverityStr) -> Self {
        match s {
            SeverityStr::High => Severity::High,
            SeverityStr::Medium => Severity::Medium,
            SeverityStr::Low => Severity::Low,
        }
    }
}

/// Load user-defined patterns from the default config path.
/// Returns an empty vec if the file doesn't exist; propagates parse/regex errors.
pub fn load_user_patterns() -> Result<Vec<SensitivityPattern>> {
    load_from_path(&config_path())
}

/// Load user-defined patterns from a given TOML file path.
pub fn load_from_path(path: &Path) -> Result<Vec<SensitivityPattern>> {
    if !path.exists() {
        return Ok(vec![]);
    }
    let content =
        std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
    let file: PatternFile =
        toml::from_str(&content).with_context(|| format!("parsing {}", path.display()))?;

    let patterns = file
        .patterns
        .into_iter()
        .map(|entry| {
            SensitivityPattern::new(
                entry.name,
                &entry.regex,
                entry.severity.into(),
                PatternCategory::Token, // user patterns default to Token category
            )
        })
        .collect();

    Ok(patterns)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn loads_valid_toml() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(
            f,
            r#"
[[pattern]]
name = "my_token"
regex = "tok_[a-z]{{8}}"
severity = "high"
"#
        )
        .unwrap();
        let patterns = load_from_path(f.path()).unwrap();
        assert_eq!(patterns.len(), 1);
        assert_eq!(patterns[0].name, "my_token");
        assert!(patterns[0].is_match("tok_abcdefgh"));
    }

    #[test]
    fn missing_file_returns_empty() {
        let result = load_from_path(Path::new("/nonexistent/path.toml")).unwrap();
        assert!(result.is_empty());
    }
}
